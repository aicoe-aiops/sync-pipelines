"""Transfer files with repartitioning.

Deprecated.
"""

import gzip
import hashlib
import re
import shutil
from os import SEEK_END
from sys import argv
from typing import IO, Any, Dict, Match

from .utils import S3FileSystem, logger

REGEX = re.compile(
    r"(?P<date>.*?)/"
    r"(?P<filename>"  # Match all the groups bellow together
    r"(?P<collection>.*)\."
    r"(?P<original_ext>.*)\."
    r"(?P<ext>.*))"
)


def new_key(folder: str, obj: Match[str]) -> str:
    """Compute new S3 key.

    Args:
        folder (str): Folder or path within the collection.
        obj (dict): Parsed key mapping containing collection, file extension, etc...

    Returns:
        str: New key to file object.

    """
    return f"{obj['collection']}/{folder}/" f"{obj['date']}-{obj['collection']}.{obj['original_ext']}"


def calculate_metadata(fileobject: IO[bytes]) -> Dict[str, Any]:
    """Provide metadata-like structure for a file.

    Args:
        fileobject (IO[bytes]): Analyzed file object.

    Returns:
        Dict[str, Any]: Metadata object containing size and MD5 hash in ETag format.

    """
    file_hash = hashlib.md5()
    for chunk in iter(lambda: fileobject.read(file_hash.block_size * 256), b""):
        file_hash.update(chunk)

    fileobject.seek(0, SEEK_END)

    return dict(etag=f'"{file_hash.hexdigest()}"', size=fileobject.tell())


def restructure(relpath: str, etag: str, size: int) -> bool:
    """Sync object to a different S3 bucket with repartitioning.

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

    log_args = dict(relpath=relpath)
    logger.info("Transfering file", log_args)

    # Parse file name, collection, date, etc.
    parsed_key = REGEX.match(relpath)
    if not parsed_key:
        logger.error("Unable to parse key into matching groups", log_args)
        return False

    # Prepare new keys for file destination
    historic_key = new_key("historic", parsed_key)
    latest_key = new_key("latest", parsed_key)

    # Get curent latest files
    current_latest = output_s3.find(f"{parsed_key['collection']}/latest").keys()
    if not current_latest:
        logger.warning(
            "No files in latest folder for collection", dict(collection=parsed_key["collection"]),
        )

    try:
        with input_s3.open(relpath, "rb") as i:
            with gzip.GzipFile(fileobj=i) as content:
                # Get MD5 of the inner GZIPped file
                logger.info("Calculating metadata of the original", log_args)
                metadata = calculate_metadata(content)  # type: ignore

                # Copy source to historic
                logger.info("Transfering to 'historic'", log_args)
                content.seek(0)
                with output_s3.open(historic_key, "wb") as o:
                    shutil.copyfileobj(content, o)

        # Delete other latest files
        for f in current_latest:
            output_s3.rm(f)

        # Copy source to latest
        logger.info("Transfering to 'latest'", log_args)
        output_s3.copy(historic_key, latest_key)

    except (EnvironmentError, IOError):
        logger.error("Failed to transfer a file", exc_info=True)
        return False

    files = (metadata, output_s3.info(historic_key), output_s3.info(latest_key))
    logger.info("Verify file", dict(files=files))
    if not S3FileSystem.cmp(files):
        logger.warning("Verification failed", dict(files=files))
        return False

    logger.info("Verified", dict(files=files))
    return True


if __name__ == "__main__":
    try:
        status = restructure(argv[1], argv[2], int(argv[3]))
    except:  # noqa: F401
        logger.error("Unexpected error during transfer", exc_info=True)
        exit(1)

    if not status:
        logger.error("Failed to sync a file", dict(relpath=argv[1]))
        exit(1)

    logger.info("Successfully synced", dict(relpath=argv[1]))
