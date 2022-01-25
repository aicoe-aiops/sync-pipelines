"""S3FileSystem wrapper."""

from contextlib import contextmanager
from dataclasses import dataclass
from gzip import GzipFile
from typing import Any, Callable, Dict, List, Optional, Iterable, Generator, Tuple

import s3fs  # type: ignore
import boto3

from .io import read_s3_config
from .logging import logger

DEFAULT_ENDPOINTS = dict(source="https://s3.amazonaws.com/", destination="https://s3.upshift.redhat.com/")

s3fs.S3FileSystem.read_timeout = 18000

S3ConfigSelector = {"source": ("source",), "destination": ("destination",), "all": ("source", "destination")}


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
        parsed_path = base_path.split("/", 1)
        self.bucket = parsed_path.pop(0)
        self.path = "/".join(parsed_path).rstrip("/")

        self.aws_secret_access_key = aws_secret_access_key
        self.aws_access_key_id = aws_access_key_id
        self.formatter = str(kwargs.pop("formatter", ""))
        self.flags = kwargs

        self.s3fs = s3fs.S3FileSystem(
            key=self.aws_access_key_id,
            secret=self.aws_secret_access_key,
            client_kwargs=dict(endpoint_url=self.endpoint_url),
        )
        self.s3_client = boto3.resource(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            endpoint_url=self.endpoint_url,
        )
        self.boto3 = self.s3_client.Bucket(self.__base_path.split("/")[0])

    @classmethod
    def from_config_file(
        cls, config: Dict[str, Any], selector: Iterable[str] = S3ConfigSelector["all"]
    ) -> List["S3FileSystem"]:
        """Instantiate S3fs objects from config file.

        Create s3fs using credentials and paths from config files.

        Args:
            filename (str, optional): Configuration file location. Defaults to None.

        Returns:
            Iterable["S3FileSystem"]: S3 file system clients.

        """
        try:
            config_list = read_s3_config(selector=selector, **config)
            return [cls(**config) for config in config_list]
        except TypeError:
            raise ValueError("Config file not parseable.")

    def find(
        self, path: str = "", constraint: Callable = lambda x: True
    ) -> Generator[Tuple[str, Dict[str, str]], None, None]:
        """List files below path.

        Like posix find with additional metedata constrain function.

        Args:
            path (str, optional): Path below __base_path to lookup. Defaults to "".
            constraint (Callable): Constraint function matching on metadata.
                Defaults to all files.

        Returns:
            Dict[str, Dict[str, str]]: S3 file key and metadata as a dict

        """
        path = (f"{self.path}/{path}" if path else self.path).strip("/")

        if path:
            iterator = self.boto3.objects.filter(Prefix=f"{path}/")
        else:
            iterator = self.boto3.objects.all()

        for obj in iterator:
            if constraint(obj):
                yield obj

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

    def copy(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str) -> None:
        """Copy files within a bucket.

        Args:
            source_bucket (str): Source bucket
            source_key (str): Source key within bucket
            dest_bucket (str): Destination bucket
            dest_key (str): Destination key within destination bucket

        """

        if dest_key is None or dest_key == '':
            dest_key = source_key
        copy_source = {
            'Bucket': source_bucket,
            'Key': '/'.join([self.path, source_key]).lstrip('/')
        }
        return self.s3_client.meta.client.copy(copy_source, dest_bucket, '/'.join([self.path, dest_key]).lstrip('/'))

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

    def __repr__(self):
        """Use self.name as an identifier."""
        return f"S3FileSystem(name='{self.name}')"


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
