"""Transfer files."""

import shutil
from itertools import tee
from typing import Any, Dict, Iterable, Iterator, List

import backoff

from .utils import S3File, S3FileSystem, key_formatter, logger


def copy(files: List[S3File]) -> None:
    """Clever copy of S3 objects.

    If both buckets are accessible via the same client, use S3 copy command.
    Otherwise, if the clients differs, use regular copy file func.

    Args:
        client_key_pairs (Iterable[ClientKeyPair]): List of clients and paths to
            where to copy to.

    """
    file_a, file_b = tee(files)
    next(file_b, None)

    for a, b in zip(file_a, file_b):
        log_args = dict(source=dict(client=a.client, key=a.key), destination=dict(client=b.client, key=b.key))
        if a.client == b.client:
            logger.info("Copying within the same clients", log_args)
            a.client.copy(a.client.bucket, a.key, b.client.bucket, b.key)
            continue

        logger.info("Copying to a different client", log_args)
        if a.client.flags == b.client.flags:
            logger.info("Matching flags, files can be copied one to one.", log_args)
            with a.client.open(a.key, "rb") as i, b.client.open(b.key, "wb") as o:
                shutil.copyfileobj(i, o)
                o.flush()
            continue

        logger.info("Flags don't match, copying from source", log_args)
        with files[0].client.open(files[0].key, "rb", **b.client.flags) as i, b.client.open(b.key, "wb") as o:
            shutil.copyfileobj(i, o)
            o.flush()


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
        yield from [S3File(c, source_path) for c in clients]
    else:
        yield S3File(clients[0], source_path)
        for c in clients[1:]:
            if not c.formatter:
                yield S3File(c, source_path)
                continue

            destination_path = key_formatter(source_path, clients[0].formatter, c.formatter, **c.flags)
            yield S3File(c, destination_path)


def verify(files: Iterable[S3File], dry_run: bool = False) -> bool:
    """Compare all transferred files.

    Args:
        files (Iterable[S3File]): Transferred files.

    Returns:
        bool: True if all matches.

    """
    if dry_run:
        logger.info("Skipping verification due to a dry run.")
        return True

    file_a, file_b = tee(files)
    next(file_b, None)

    return all(a == b for a, b in zip(file_a, file_b))


class TransferFailed(Exception):
    """Raised for retry purposes when transfer fails for any reason."""

    pass


@backoff.on_exception(backoff.expo, TransferFailed, max_tries=10, logger=logger)
def _transfer_single_file(
    source_path: str, clients: List[S3FileSystem], idx: int, count: int, dry_run: bool = False
) -> None:
    """Transfer single object between S3s.

    Args:
        source_path (str): Key to the object within the source S3 bucket.
        clients (List[S3FileSystem]): S3 clients to sync between.
        dry_run (bool, optional): Do not execute file transfers, just list what would happen.

    Raises:
        TransferError: In case of transfer or verification failure

    Returns:
        None: Returns if success

    """
    try:
        files = [f for f in calc_s3_files(source_path, clients)]
        logger.info(
            "Transfering file",
            dict(
                idx=idx,
                count=count,
                source=dict(name=files[0].client, key=source_path),
                destinations=[dict(name=f.client, key=f.key) for f in files[1:]],
            ),
        )
        if not dry_run:
            copy(files)

    except:  # noqa: E722
        logger.error("Failed to transfer a file", dict(idx=idx, count=count), exc_info=True)
        raise TransferFailed("Failed to transfer a file")

    logger.info("Verifying file", dict(files=files, idx=idx, count=count))
    if not verify(files, dry_run):
        logger.warning("Verification failed", dict(files=files, idx=idx, count=count))
        raise TransferFailed("Verification failed")

    logger.info("Verified", dict(files=files, idx=idx, count=count))


def send(files_to_transfer: List[Dict[str, Any]], config: Dict[str, Any], count: int, dry_run: bool = False) -> bool:
    """Transfer recent data between S3s, multiple files.

    Args:
        filename (str): Json file that contains list of S3 objects to be transferred.
        config_file (str, optional): Path to configuration file. Defaults to None.
        dry_run (bool, optional): Do not execute file transfers, just list what would happen.

    Returns:
        bool: True if success

    Raises:
        ValueError: Raised when local environment is not set properly
        FileNotFoundError: Raised when there are no files to be transfered (noop)
        IOError: Raised when some files failed to transfer

    """
    try:
        clients = S3FileSystem.from_config_file(config)
    except ValueError:
        raise

    if not files_to_transfer:
        raise FileNotFoundError("No files to transfer")

    failed = []
    count = count or len(files_to_transfer)
    for idx, source_file in enumerate(files_to_transfer):
        try:
            _transfer_single_file(source_file["key"], clients, idx, count, dry_run)
        except TransferFailed:
            logger.error("Max retries reached", dict(file=source_file), exc_info=True)
            failed.append(source_file)
        except KeyError:
            logger.error("Unable to parse file key", dict(file=source_file), exc_info=True)
            failed.append(source_file)

    if failed:
        raise IOError("Some files failed to be transferred", dict(failed_files=failed))
    return True
