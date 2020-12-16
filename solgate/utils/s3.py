"""S3FileSystem wrapper."""

from contextlib import contextmanager
from dataclasses import dataclass
from gzip import GzipFile
from typing import Any, Callable, Dict, List, Optional

import s3fs  # type: ignore

from .io import read_s3_config
from .logging import logger

DEFAULT_ENDPOINTS = dict(source="https://s3.amazonaws.com/", destination="https://s3.upshift.redhat.com/")


class S3FileSystem:
    """S3FileSystem wrapper."""

    def __init__(
        self,
        name: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        base_path: str,
        endpoint_url: str = "",
        **kwargs: dict,
    ) -> None:
        """Access S3 as if it were a file system.

        This exposes a filesystem-like API (ls, cp, open, etc.) on top of S3 storage.

        Args:
            aws_access_key_id (str): Access key ID
            aws_secret_access_key (str): Access secret key
            base_path (str): Base S3 path containing Bucket name and optional root folder for data.
            endpoint_url (str, optional): Base S3 URL. If not explicitly set, it defaults to DEFAULT_ENDPOINTS
                ['source'] if kwargs['source'] is True. DEFAULT_ENDPOINTS['destination] otherwise.

        """
        self.name = name
        self.is_source = name == "source"
        self.endpoint_url = endpoint_url
        if not self.endpoint_url:
            self.endpoint_url = DEFAULT_ENDPOINTS["source"] if self.is_source else DEFAULT_ENDPOINTS["destination"]

        logger.info(
            "Initializing a remote file system",
            dict(name=name, endpoint_url=self.endpoint_url, base_path=base_path, is_source=self.is_source),
        )
        self.__base_path = base_path
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_access_key_id = aws_access_key_id
        self.formatter = str(kwargs.pop("formatter", ""))
        self.flags = kwargs

        self.s3fs = s3fs.S3FileSystem(
            key=self.aws_access_key_id,
            secret=self.aws_secret_access_key,
            client_kwargs=dict(endpoint_url=self.endpoint_url),
        )

    @classmethod
    def from_config_file(cls, config: Dict[str, Any]) -> List["S3FileSystem"]:
        """Instantiate S3fs objects from config file.

        Create s3fs using credentials and paths from config files.

        Args:
            filename (str, optional): Configuration file location. Defaults to None.

        Returns:
            Iterable["S3FileSystem"]: S3 file system clients.

        """
        try:
            config_list = read_s3_config(**config)
            return [cls(**config) for config in config_list]
        except TypeError:
            raise EnvironmentError("Config file not parseable.")

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

            constraint = lambda meta: meta.get("type", "").lower() != "directory" and _constraint(meta)  # noqa: E731

        return {
            k.replace(f"{self.__base_path}/", ""): v
            for k, v in self.s3fs.find(path, maxdepth, withdirs, detail=True).items()
            if constraint(v)
        }

    @contextmanager
    def open(self, path: str, mode: str = "rb", **kwargs: Dict[Any, Any]):
        """Return a file-like object from the filesystem.

        Args:
            path (str): Relative path to file within the __base_path.
            mode (str): Access mode. Defaults to "rb".

        Returns:
            File object

        """
        unpack = kwargs.pop("unpack", False)
        if unpack and mode != "rb":
            raise RuntimeError("Unable to unpack on write.")

        with self.s3fs.open(f"{self.__base_path}/{path}", mode, **kwargs) as f:
            if not unpack:
                yield f
            else:
                with GzipFile(fileobj=f) as f_unpacked:
                    yield f_unpacked

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

    def copy(self, source: str, dest: str, dest_base_path: str = None) -> None:
        """Copy files within a bucket.

        Args:
            source (str): Source path
            dest (str): Destination path
            dest_base_path (str, optional): Bucket name and base path to the destinatation within
                the same client

        """
        dest_base_path = dest_base_path or self.__base_path

        return self.s3fs.copy(f"{self.__base_path}/{source}", f"{dest_base_path.rstrip('/')}/{dest}")

    def __eq__(self, other: object) -> bool:
        """Compare S3FileSystem to other objects."""
        if not isinstance(other, S3FileSystem):
            return NotImplemented
        return all(
            getattr(self, attr) == getattr(other, attr)
            for attr in ("aws_secret_access_key", "aws_access_key_id", "endpoint_url", "flags")
        )

    def __str__(self):
        """Use name as a string destriptor for instances."""
        return self.name


@dataclass
class S3File:
    """S3 file represented as a client and location pair."""

    client: S3FileSystem
    key: str
    _info: Optional[dict] = None

    @property
    def info(self) -> dict:
        """Cache file object info as a property."""
        if not self._info:
            self._info = self.client.info(self.key)
        return self._info

    def __eq__(self, other: object) -> bool:
        """Compare S3File to other objects."""
        if not isinstance(other, S3File):
            return NotImplemented

        if self.client.flags != other.client.flags:
            logger.warning("Comparing files that doesn't match client flags - verification skipped.")
            return True

        if "-" in self.info["etag"] or "-" in other.info["etag"]:
            logger.warning("ETag is not a MD5 hash, falling back to 'size'")
            if self.info["size"] != other.info["size"]:
                return False
            return True

        if self.info["etag"] != other.info["etag"]:
            return False

        return True
