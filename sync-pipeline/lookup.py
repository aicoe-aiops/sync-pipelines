from datetime import datetime, timezone
from json import dump
from sys import argv
from typing import List, Dict, Any

from utils import S3FileSystem, get_timedelta, logger, serialize


KEYS = ("lastmodified", "etag", "key", "type", "size")


def subset_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Select a metadata subset.
    
    Matches the keys listed in KEYS only, so we don't clutter the workflow.

    Args:
        meta (Dict[str, Any]): Metadata map

    Returns:
        Dict[str, Any]: Subset of the metadata
    """
    return {k.lower(): v for k, v in meta.items() if k.lower() in KEYS}


def lookup() -> List[Dict[str, Any]]:
    """Lookup recently modifined files.

    List files on S3 and filter those that were modified in recent history.

    Returns:
        List[dict]: List of recently modified files. Each intem in this list
            contains the file metadata, absolute key and relative path within
            the base path.
    """
    try:
        oldest_date = datetime.now(timezone.utc) - get_timedelta()
        s3 = S3FileSystem.from_env("S3")
    except EnvironmentError:
        logger.error("Environment not set properly, exiting", exc_info=True)
        exit(1)
    constraint = lambda meta: meta["LastModified"] >= oldest_date
    located_files = s3.find(constraint=constraint)

    if not located_files:
        logger.error("No files found in given TIMEDELTA", dict(files=[]))
        exit(1)
    logger.info("Files found", dict(files=list(located_files.keys())))

    # Select a metadata subset, so we don't clutter the workflow
    return [dict(relpath=k, **subset_metadata(v)) for k, v in located_files.items()]


if __name__ == "__main__":
    logger.info("Lookup started")

    try:
        located_files = lookup()
        serialize(located_files, argv[1])
    except:
        logger.error("Unexpected error", exc_info=True)
        exit(1)

    logger.info("Done")
