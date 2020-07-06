import os
import re
from datetime import timedelta

from .logging import logger

REGEX = re.compile(
    "((?P<days>\d+?)d)?"
    "((?P<hours>\d+?)h)?"
    "((?P<minutes>\d+?)m)?"
    "((?P<seconds>\d+?)s)?"
)


def get_timedelta() -> timedelta:
    """Parse string interval from environment to timedelta.

    Returns:
        timedelta: Time delta representing given string.
    """
    try:
        raw_timedelta = os.environ["TIMEDELTA"]
        parts = REGEX.match(raw_timedelta)
        if not parts:
            raise ValueError("Timedelta format is not valid")
    except (KeyError, ValueError):
        raise EnvironmentError

    time_params = {k: int(v) for k, v in parts.groupdict().items() if v}
    return timedelta(**time_params)
