"""Lookup files to transfer."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator

from .utils import S3FileSystem, S3ConfigSelector, logger, read_general_config

KEYS = ("last_modified", "e_tag", "key", "size")
DEFAULT_TIMEDELTA = "1d"


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


def list_source(config: Dict[str, Any], backfill=False) -> Generator[Dict[str, Any], None, None]:
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
    s3 = S3FileSystem.from_config_file(config, S3ConfigSelector["source"])[0]

    if backfill:
        constraint = lambda _: True  # noqa: E731
    else:
        constraint = lambda obj: obj.last_modified >= oldest_date  # noqa: E731

    is_files = False
    # Select a metadata subset, so we don't clutter the workflow
    for obj in s3.find(constraint=constraint):
        if not is_files:
            logger.info("Files found")
            is_files = True

        yield {k: getattr(obj, k) for k in KEYS}

    if not is_files:
        raise FileNotFoundError("No files found in given TIMEDELTA")
