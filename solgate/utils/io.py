"""IO helpers."""

import json
import re
from pathlib import Path

from yaml import load as yaml_load

try:
    from yaml import CLoader as Loader
except ImportError:  # pragma nocover
    from yaml import Loader  # type: ignore

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache, partial
from string import Formatter
from typing import Any, Dict, Iterator

load = partial(yaml_load, Loader=Loader)

CREDS_FILENAME_FORMAT = "{0}.creds.yaml"
CREDS_FILE_KEYS = ["aws_access_key_id", "aws_secret_access_key"]


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

        return super().default(o)


def serialize(obj: Any, filename: str) -> None:
    """Serialize python object to json file.

    Args:
        obj (Any): Python object to serialize.
        filename (str): Local filename, where the JSON will be stored.

    """
    with open(filename, "w") as f:
        json.dump(obj, f, cls=CustomEncoder)


def deserialize(filename: str) -> Any:
    """Deserialize json file to Python object.

    Args:
        filename (str): File name or path.

    Returns:
        Any: Pythonic object

    """
    with open(filename, "r") as f:
        return json.load(f)


def _read_yaml_file(filename) -> Dict[str, Any]:
    """Read a file.

    Args:
        filename (str, optional): Configuration file location. Defaults to None.

    Returns:
        Dict[str, Any]: Pythonic representation of the config file.

    """
    with open(filename) as f:
        config = load(f)

    if not isinstance(config, dict) or not config.keys():
        raise IOError(f"Invalid config file {filename}")

    return config


def _fetch_creds(path: Path, config: Dict[str, Any]):
    """Fetch credentials for a config section if necessary.

    In case the `config` doesn't feature the credentials already, try loading them from a local file within
    the config folder `path`. Updates the original `config` dict.

    Args:
        path (Path):Configuration file location.
        config (Dict[str, str]): Config section specific to a s3 location.

    Raises:
        IOError: Raised when the credentials file doesn't contain the proper data.

    """
    if set(config.keys()).issuperset(CREDS_FILE_KEYS):
        return

    creds = _read_creds_file(path, config["name"])
    config.update(creds)

    if not set(config.keys()).issuperset(CREDS_FILE_KEYS):
        raise IOError(f"Invalid credentials file for {config['name']}")


@lru_cache
def _read_creds_file(path: Path, kind: str) -> Dict[str, str]:
    """Read and memoize a credentials file.

    Allows to specify unique ID within each 'kind' (dot separated). If the file containing this ID is not found, it
    fallbacks to the default file for each kind.

    Args:
        path (Path): Configuration file location.
        kind(str): 'source' or 'destination.XYZ' expected. The filename is derived from it using CREDS_FILENAME_FORMAT
            template.

    Returns:
        Dict[str, str]: A dict with the credentials file content.

    Examples:
    >>> _read_creds_file('/etc/solgate', 'source')
    # reads /etc/solgate/source.creds.yaml
    >>> _read_creds_file('/etc/solgate', 'destination.1')
    # reads /etc/solgate/destination.1.creds.yaml, if not found, fallbacks to /etc/solgate/destination.creds.yaml

    """
    try:
        return _read_yaml_file(path / CREDS_FILENAME_FORMAT.format(kind))
    except FileNotFoundError:
        if "." in kind:
            return _read_creds_file(path, kind.split(".")[0])
        raise


def read_s3_config(filename: str, path: Path) -> Iterator[dict]:
    """Read YAML file and parse S3 clients related configuration.

    Args:
        filename (str): Configuration file name.
        path (Path): Configuration file location.

    Yields:
        Iterator[dict]: Section name and content dict pair.

    """
    config = _read_yaml_file(path / filename)
    source = dict(name="source", **config.get("source", {}))
    _fetch_creds(path, source)
    yield source

    for idx, s in enumerate(config.get("destinations", [])):
        destination = dict(name=f"destination.{idx}", **s)
        _fetch_creds(path, destination)
        yield destination


def read_general_config(filename: str, path: Path) -> Dict[str, Any]:
    """Read INI file and parse general configuration.

    Args:
        filename (str): Configuration file name.
        path (Path): Configuration file location.

    Returns:
        Dict[str, Any]: General configuration section data.

    """
    config = _read_yaml_file(path / filename)

    config.pop("source", None)
    config.pop("destinations", None)

    return config


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


@lru_cache(1)
def _default_attributes():
    now = datetime.now()
    return dict(
        datetime=now.isoformat(),
        date=now.date().isoformat(),
        **{k: f"{getattr(now, k):02}" for k in ("year", "month", "day", "hour", "minute", "second")},
        weekday=str(now.weekday()),
    )


def key_formatter(key: str, source_formatter: str = "", destination_formatter: str = "", **kwargs: dict) -> str:
    """Transform key applying format.

    Uses source and destination formatter to transform the original key into a new object key.

    Args:
        key (str): Original key.
        source_formatter (str, optional): Formatter string. Defaults to "".
        destination_formatter (str, optional): Formatter string. Defaults to "".

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
        KeyError: When the key doesn't match the source formatter, we can't proceed.

    Returns:
        str: Key in new format.

    """
    if not source_formatter or not destination_formatter:
        if kwargs.get("unpack"):
            source_formatter = destination_formatter = "{all}"
        else:
            return key

    parser = _create_parser(source_formatter)
    suffix_pattern = r"\..{2,3}$" if kwargs.get("unpack") else r"$"
    pattern = re.compile(parser.pattern.pattern + suffix_pattern)

    match = pattern.match(key)
    if not match:
        raise KeyError("Key doesn't match the expected source format")

    attributes = _default_attributes().copy()
    attributes.update({k: match[k] for k in parser.attributes})

    return destination_formatter.format(**attributes)
