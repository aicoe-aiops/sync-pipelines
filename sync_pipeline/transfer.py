"""Transfer files."""

import shutil
from sys import argv
from typing import Iterable
from itertools import tee
from dataclasses import dataclass

from .utils import S3FileSystem, logger, KeyFormatter


@dataclass
class ClientKeyPair:
    """Pair of the client and destination path."""

    s3: S3FileSystem
    key: str


def copy(client_key_pairs: Iterable[ClientKeyPair]) -> None:
    """Clever copy of S3 objects.

    If both buckets are accessible via the same client, use S3 copy command.
    Otherwise, if the clients differs, use regular copy file func.

    Args:
        client_key_pairs (Iterable[ClientKeyPair]): List of clients and paths to
            where to copy to.

    """
    pair_a, pair_b = tee(client_key_pairs)
    next(pair_b, None)

    for a, b in zip(pair_a, pair_b):
        if a.s3 == b.s3:
            logger.info("Copying within the same bucket")
            a.s3.copy(a.key, b.key)
        else:
            logger.info("Copying to a different bucket")
            with a.s3.open(a.key, "rb") as i, b.s3.open(b.key, "wb") as o:
                shutil.copyfileobj(i, o)


def transfer(source_path: str, etag: str, size: int) -> bool:
    """Transfer recent data between S3s.

    Arguments:
        source_path (str): Relative path in object S3 key
        etag (str): E-Tag hash of the object
        size (str): Size of the object in bytes

    Returns:
        bool: True if success

    """
    try:
        input_s3 = S3FileSystem.from_env("INPUT")
        output_s3 = S3FileSystem.from_env("OUTPUT")
        formatter = KeyFormatter.from_env("INPUT", "OUTPUT")

    except EnvironmentError:
        logger.error("Environment not set properly, exiting", exc_info=True)
        return False

    try:
        destination_path = formatter.format(source_path)
        logger.info("Transfering file", dict(source_path=source_path, destination_path=destination_path))
        copy((ClientKeyPair(input_s3, source_path), ClientKeyPair(output_s3, destination_path)))
    except:  # noqa: E722
        logger.error("Failed to transfer a file", exc_info=True)
        return False

    if input_s3.unpack:
        logger.info("Object was unpacked from source, skipping verification")
        return True

    files = (dict(etag=etag, size=size), output_s3.info(destination_path))
    logger.info("Verify file", dict(files=files))
    if not S3FileSystem.cmp(files):
        logger.warning("Verification failed", dict(files=files))
        return False

    logger.info("Verified", dict(files=files))
    return True


if __name__ == "__main__":
    try:
        success = transfer(argv[1], argv[2], int(argv[3]))
    except:  # noqa: E722
        logger.error("Unexpected error during transfer", exc_info=True)
        exit(1)

    if not success:
        logger.error("Failed to perform a full sync", dict(relpath=argv[1]))
        exit(1)
    logger.info("Successfully synced all files", dict(relpath=argv[1]))
