"""Transfer files."""

import shutil
from sys import argv
from typing import Iterable, List, Iterator
from itertools import tee

from .utils import S3FileSystem, S3File, logger, KeyFormatter


def copy(clients: Iterable[S3File]) -> None:
    """Clever copy of S3 objects.

    If both buckets are accessible via the same client, use S3 copy command.
    Otherwise, if the clients differs, use regular copy file func.

    Args:
        client_key_pairs (Iterable[ClientKeyPair]): List of clients and paths to
            where to copy to.

    """
    file_a, file_b = tee(clients)
    next(file_b, None)

    for a, b in zip(file_a, file_b):
        if a.client == b.client:
            logger.info("Copying within the same clients")
            a.client.copy(a.key, b.key)
        else:
            logger.info("Copying to a different client")
            with a.client.open(a.key, "rb", **b.client.flags) as i, b.client.open(b.key, "wb") as o:
                shutil.copyfileobj(i, o)


def calc_s3_files(source_path: str, clients: List[S3FileSystem]) -> Iterator[S3File]:
    """Compute new destination keys.

    Use KeyFormatter to determine the destination key based on source key template.

    Args:
        source_path (str): File's original path.
        clients (List[S3FileSystem]): List of all S3 clients.

    Yields:
        Iterator[S3File]: Expected destination location associated with its client.

    """
    if not clients[0].formatter:
        yield from [S3File(c, source_path) for c in clients[1:]]
    else:
        yield S3File(clients[0], source_path)
        for c in clients[1:]:
            if not c.formatter:
                yield S3File(c, source_path)

            destination_path = KeyFormatter(clients[0].formatter, c.formatter, **c.flags).format(source_path)
            yield S3File(c, destination_path)


def verify(files: Iterable[S3File]) -> bool:
    """Compare all transferred files.

    Args:
        files (Iterable[S3File]): Transferred files.

    Returns:
        bool: True if all matches.

    """
    file_a, file_b = tee(files)
    next(file_b, None)

    return all(a == b for a, b in zip(file_a, file_b))


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
        clients = S3FileSystem.from_config_file()
    except EnvironmentError:
        logger.error("Environment not set properly, exiting", exc_info=True)
        return False

    try:
        files = [f for f in calc_s3_files(source_path, clients)]
        logger.info(
            "Transfering file",
            dict(
                source=dict(name=files[0].client, key=source_path),
                destinations=[dict(name=f.client, key=f.key) for f in files[1:]],
            ),
        )
        copy(files)

    except:  # noqa: E722
        logger.error("Failed to transfer a file", exc_info=True)
        return False

    # logger.info("Verify file", dict(files=files))
    # if not verify(files):
    #     logger.warning("Verification failed", dict(files=files))
    #     return False

    # logger.info("Verified", dict(files=files))
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
