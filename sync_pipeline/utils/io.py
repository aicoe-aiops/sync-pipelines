"""IO helpers."""

import json
import re
from configparser import ConfigParser, SectionProxy
from datetime import datetime
from dataclasses import dataclass
from functools import lru_cache
from string import Formatter
from typing import Any, Iterator, Tuple, Union


class CustomEncoder(json.JSONEncoder):
    """JSON encoder that handles dates and iterations."""

    def default(self, o):
        """Parser for other than native types."""
        try:
            return list(iter(o))
        except TypeError:
            pass

        try:
            return o.isoformat()
        except AttributeError:
            pass

        return super().default(self, o)


def serialize(obj: Any, filename: str) -> None:
    """Serialize python object to json file.

    Args:
        obj (Any): Python object to serialize.
        filename (str): Local filename, where the JSON will be stored.

    """
    with open(filename, "w") as f:
        json.dump(obj, f, cls=CustomEncoder)


def _convert_config_value(section: SectionProxy, key: str) -> Union[str, bool]:
    """Parse ConfigParser's boolean values."""
    try:
        return section.getboolean(key)
    except ValueError:
        return section.get(key)


def read_config(filename: str) -> Iterator[Tuple[str, dict]]:
    """Read INI file and parse values.

    Args:
        filename (str): Config file location.

    Yields:
        Iterator[Tuple[str, dict]]: Section name and content dict pair.

    """
    config = ConfigParser()
    config.read(filename)

    if not config.sections():
        raise IOError(f"Invalid config file {filename}")

    for s in config.sections():
        yield s, {k: _convert_config_value(config[s], k) for k in config[s].keys()}


@dataclass
class Parser:
    """Memoized parser pattern and sources attributes set."""

    attributes: set
    pattern: re.Pattern


def _get_param_names(formatter: str):
    return set(str(p[1]) for p in Formatter().parse(formatter) if p[1])


@lru_cache
def _create_parser(source_formatter: str):
    source_formatter = source_formatter.replace(".", r"\.")
    return Parser(
        _get_param_names(source_formatter), re.compile(r"^" + re.sub(r"{(.*?)}", r"(?P<\g<1>>.*?)", source_formatter))
    )


def _get_additional_pattern(**kwargs):
    return r"\..{2,3}$" if kwargs.get("unpack") else r"$"


@lru_cache(1)
def _default_attributes():
    now = datetime.now()
    return dict(
        datetime=now.isoformat(),
        date=now.date().isoformat(),
        **{k: f"{getattr(now, k):02}" for k in ("year", "month", "day", "hour", "minute", "second")},
        weekday=now.weekday(),
    )


def key_formatter(key: str, source_formatter: str = None, destination_formatter: str = None, **kwargs: dict) -> str:
    """Transform key applying format.

    Uses source and destination formatter to transform the original key into a new object key.

    Args:
        key (str): Original key.
        source_formatter (str, optional): Formatter string. Defaults to None.
        destination_formatter (str, optional): Formatter string. Defaults to None.

    Examples:
        >>> key_formatter("first/second/third.csv.gz", "{a}/{b}/{rest}", "{date}/{a}/{rest}")
        '2020-07-09/first/third.csv.gz'

        >>> key_formatter("first/second/third.csv.gz", "{a}/{b}/{rest}", "{year}/{month}/{day}/{a}/{b}/{rest}")
        '2020/07/09/first/second/third.csv.gz'

        >>> key_formatter("first/second/third.csv.gz", "{a}/{b}/{rest}", "{b}/{a}/{rest}")
        'second/first/third.csv.gz'

        >>> key_formatter("first/second/third.csv.gz", "{a}/{b}/{rest}", "{b}/{a}/{rest}")
        'second/first/third.csv.gz'

        >>> key_formatter("first/second/third.csv.gz", "{a}/{b}/{rest}", "{b}/{a}/{rest}", unpack=True)
        'second/first/third.csv'

    Raises:
        AttributeError: When the key doesn't match the source formatter, we can't proceed.

    Returns:
        str: Key in new format.

    """
    if not source_formatter or not destination_formatter:
        return key

    parser = _create_parser(source_formatter)
    if not kwargs.get("unpack"):
        pattern = re.compile(parser.pattern.pattern + r"$")
    else:
        pattern = re.compile(parser.pattern.pattern + r"\..{2,3}$")

    match = pattern.match(key)
    if not match:
        raise AttributeError("Key doesn't match the expected source format")

    attributes = dict(**_default_attributes(), **{k: match[k] for k in parser.attributes})

    return destination_formatter.format(**attributes)
