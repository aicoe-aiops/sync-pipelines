"""S3FileSystem wrapper."""

import os
from contextlib import contextmanager
from itertools import tee
from typing import Callable, Dict, Iterable, Optional

import s3fs  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from s3fs.errors import translate_boto_error  # type: ignore

from .logging import logger


class S3FileSystem:
    """S3FileSystem wrapper."""

    def __init__(self, key: str, secret: str, url: str, path: str) -> None:
        """Access S3 as if it were a file system.

        This exposes a filesystem-like API (ls, cp, open, etc.) on top of S3 storage.

        Args:
            key (str): Access key ID
            secret (str): Access secret key
            url (str): Base S3 URL
            path (str): Base S3 path for lookups
        """
        logger.info("Initializing a remote file system", dict(url=url, path=path))
        self.__base_path = path
        self.secret = secret
        self.key = key
        self.url = url

        self.s3fs = s3fs.S3FileSystem(key=key, secret=secret, client_kwargs=dict(endpoint_url=url))

    @classmethod
    def from_env(cls, prefix: str = "") -> "S3FileSystem":
        """Build an s3fs object from env variables.

        Create s3fs using credentials and paths from environment variables.

        Args:
            prefix (str, optional): prefix of environment variable names. Defaults to ""

        Returns:
            Tuple[S3FileSystem, str]: S3 file system and a base path that should be respected
        """
        try:
            url = os.environ[f"{prefix}_URL"]
            path = os.environ[f"{prefix}_PATH"].rstrip("/")
            key = os.environ[f"{prefix}_ACCESS_KEY_ID"]
            secret = os.environ[f"{prefix}_SECRET_ACCESS_KEY"]
        except KeyError:
            raise EnvironmentError

        return cls(key, secret, url, path)

    def find(
        self,
        path: str = "",
        constraint: Callable = lambda x: True,
        maxdepth: Optional[int] = None,
        withdirs: bool = False,
    ) -> Dict[str, Dict[str, str]]:
        """List files below path.

        Like posix find with additional metedata constrain function.

        Args:
            path (str, optional): Path below __base_path to lookup. Defaults to "".
            constraint (Callable): Constraint function matching on metadata.
                Defaults to all files.
            maxdepth(int, optional): The maximum number of levels to descend.
                Defaults to no limit.
            withdirs(bool, optional): Whether to include directory paths in the
                output. Defaults to False.

        Returns:
            Dict[str, Dict[str, str]]: S3 file key and metadata as a dict
        """
        path = f"{self.__base_path}/{path}" if path else self.__base_path

        # Fix Ceph reporting folders as "type"="file", check for size instead
        if not withdirs:
            _constraint = constraint

            def constraint(meta):
                return meta.get("type", "").lower() != "directory" and _constraint(meta)

        return {
            k.replace(f"{self.__base_path}/", ""): v
            for k, v in self.s3fs.find(path, maxdepth, withdirs, detail=True).items()
            if constraint(v)
        }

    @contextmanager
    def open(self, path: str, mode: str = "rb", **kwargs):
        """Return a file-like object from the filesystem.

        Args:
            path (str): Relative path to file within the __base_path.
            mode (str): Access mode. Defaults to "rb".

        Returns:
            File object
        """
        try:
            with self.s3fs.open(f"{self.__base_path}/{path}", mode, **kwargs) as f:
                yield f
        except ClientError as e:
            raise translate_boto_error(e)

    def info(self, path: str) -> Dict[str, str]:
        """Fetch file object info metadata.

        Args:
            path (str): Relative path to file within the __base_path.

        Returns:
            Dict[str, str]: Object metadata
        """
        return {k.lower(): v for k, v in self.s3fs.info(f"{self.__base_path}/{path}").items()}

    def rm(self, path: str) -> None:
        """Unlink a file.

        Args:
            path (str): Path to file within __base_path.
        """
        return self.s3fs.rm(f"{self.__base_path}/{path}")

    @staticmethod
    def cmp(objects: Iterable[dict]) -> bool:
        """Compare file metadata.

        Match ETag on files.

        Args:
            a_metadata (dict): Object to compare metadata.
            b_metadata (dict): Object to compare metadata.

        Returns:
            bool: True if files match
        """
        a_objects, b_objects = tee(objects)
        next(b_objects, None)

        for a, b in zip(a_objects, b_objects):
            if not a or not b or not a.get("etag", False) or not b.get("etag", False):
                return False

            if "-" in a["etag"] or "-" in b["etag"]:
                logger.warning("ETag is not a MD5 hash, falling back to 'size'")
                if a["size"] != b["size"]:
                    return False

            if a["etag"] != a["etag"]:
                return False
        return True

    def copy(self, source: str, dest: str, dest_base_path: str = None) -> None:
        """Copy files within a bucket.

        Args:
            source (str): Source path
            dest (str): Destination path
            dest_base_path (str, optional): Bucket name and base path to the destinatation within
                the same client
        """
        dest_base_path = dest_base_path or self.__base_path

        return self.s3fs.copy(f"{self.__base_path}/{source}", f"{dest_base_path}/{dest}")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, S3FileSystem):
            return NotImplemented
        return all(getattr(self, attr) == getattr(other, attr) for attr in ("key", "secret", "url"))
