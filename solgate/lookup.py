"""Lookup files to transfer."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .utils import S3FileSystem, logger, read_general_config

KEYS = ("lastmodified", "etag", "key", "type", "size")
DEFAULT_TIMEDELTA = "1d"


def subset_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Select a metadata subset.

    Matches the keys listed in KEYS only, so we don't clutter the workflow.

    Args:
        meta (Dict[str, Any]): Metadata map

    Returns:
        Dict[str, Any]: Subset of the metadata

    """
    return {k.lower(): v for k, v in meta.items() if k.lower() in KEYS}


# fmt: off
REGEX = re.compile(
    r"((?P<days>\d+?)d)?\W*"
    r"((?P<hours>\d+?)h)?\W*"
    r"((?P<minutes>\d+?)m)?\W*"
    r"((?P<seconds>\d+?)s)?"
)
# fmt: on


def parse_timedelta(timestr: str) -> timedelta:
    """Parse string interval from environment to timedelta.

    Args:
        timestr (str): String to parse as a timedelta.

    Returns:
        timedelta: Time delta representing given string.

    """
    parts = REGEX.match(timestr)

    time_params = {k: int(v) for k, v in parts.groupdict().items() if v}  # type: ignore

    if not time_params:
        raise ValueError("Timedelta format is not valid")

    return timedelta(**time_params)


def list_source(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lookup recently modifined files.

    List files on S3 and filter those that were modified in recent history.

    Args:
        timestr (str): Timedelta represented as a string.
        config_file (str, optional): Path to configuration file.

    Returns:
        List[dict]: List of recently modified files. Each item in this list
            contains the file metadata, absolute key and relative path within
            the base path.

    """
    general_config = read_general_config(**config)

    oldest_date = datetime.now(timezone.utc) - parse_timedelta(general_config.get("timedelta", DEFAULT_TIMEDELTA))
    s3 = S3FileSystem.from_config_file(config)[0]

    constraint = lambda meta: meta["LastModified"] >= oldest_date  # noqa: E731

    is_files = False
    # Select a metadata subset, so we don't clutter the workflow
    for k, v in s3.find(constraint=constraint):
        if not is_files:
            logger.info("Files found")
            is_files = True

        yield dict(relpath=k, **subset_metadata(v))

    if not is_files:
        raise FileNotFoundError("No files found in given TIMEDELTA")
