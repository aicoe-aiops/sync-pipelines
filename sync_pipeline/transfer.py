import shutil
from datetime import datetime, timezone
from sys import argv
from typing import Dict, Iterable
from itertools import tee
from dataclasses import dataclass

from utils import S3FileSystem, logger


@dataclass
class ClientKeyPair:
    s3: S3FileSystem
    key: str


def copy(client_key_pairs: Iterable[ClientKeyPair]) -> None:
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


def transfer(relpath: str, etag: str, size: int) -> bool:
    """Transfer recent data between S3s.

    Arguments:
        relpath(str): Relative path in object S3 key 
        etag(str): E-Tag hash of the object
        size(str): Size of the object in bytes

    Returns:
        bool: True if success 
    """
    try:
        input_s3 = S3FileSystem.from_env("INPUT")
        output_s3 = S3FileSystem.from_env("OUTPUT")
    except EnvironmentError:
        logger.error("Environment not set properly, exiting", exc_info=True)
        return False

    logger.info("Transfering file", dict(relpath=relpath))
    try:
        copy((ClientKeyPair(input_s3, relpath), ClientKeyPair(output_s3, relpath)))
    except:
        logger.error("Failed to transfer a file", exc_info=True)
        return False

    files = [dict(etag=etag, size=size), output_s3.info(relpath)]
    logger.info("Verify file", dict(files=files))
    if not S3FileSystem.cmp(files):
        logger.warning("Verification failed", dict(files=files))
        return False

    logger.info("Verified", dict(files=files))
    return True


if __name__ == "__main__":
    try:
        success = transfer(argv[1], argv[2], int(argv[3]))
    except:
        logger.error("Unexpected error during transfer", exc_info=True)
        exit(1)

    if not success:
        logger.error("Failed to perform a full sync", dict(relpath=argv[1]))
        exit(1)
    logger.info("Successfully synced all files", dict(relpath=argv[1]))
