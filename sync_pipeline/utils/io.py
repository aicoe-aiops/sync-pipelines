"""IO helpers."""

import json
import os
import re
from datetime import datetime
from string import Formatter
from typing import Any, Dict


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


class KeyFormatter:
    """S3 key transformation parser and formatter."""

    def __init__(self, source_formatter: str, destination_formatter: str):
        """S3 key formatter for repartitioning.

        Transforms original keys into a new ones, allowing for variable substitution and rearrangement.

        Args:
            source_formatter (str): Pythonic f-string description of the original key used for parsing variables
                out of the key.
            destination_formatter (str): Pythonic f-string used to format the key into its final form.

        """
        self.source_parser = re.compile(r"^" + re.sub(r"{(.*?)}", r"(?P<\g<1>>.*?)", source_formatter) + "$")

        param_names = lambda formatter: set(str(p[1]) for p in Formatter().parse(formatter) if p[1])  # noqa: E731

        self.source_params = param_names(source_formatter)
        self.destination_formatter = destination_formatter
        self.destination_params = param_names(destination_formatter)
        self.kwargs = self._generated_kwargs()

    @classmethod
    def from_env(cls, source_prefix: str, destination_prefix: str) -> "KeyFormatter":
        """Initialize KeyFormatter from env variables.

        Args:
            source_prefix (str): Prefixes the environment variable for the source formatter.
            destination_prefix (str): Prefixes the environment variable for the destination formatter.

        Raises:
            EnvironmentError:  In case the expected keys are missing from environment, this error is raised.

        Returns:
            KeyFormatter: Properly initialized KeyFormatter instance.

        """
        try:
            source_formatter = os.environ[f"{source_prefix}_FORMATTER"]
            destination_formatter = os.environ[f"{destination_prefix}_FORMATTER"]
        except KeyError:
            raise EnvironmentError
        return cls(source_formatter, destination_formatter)

    def _generated_kwargs(self) -> Dict[str, Any]:
        """Compute new default values for format variables.

        Returns:
            Dict[str, Any]: Default kwargs used for format method.

        """
        kwargs = dict()

        now = datetime.now()
        for p in self.destination_params - self.source_params:
            # Support `datetime` itself
            if p == "datetime":
                kwargs[p] = now.isoformat()
            # Support `datetime` attributes
            if hasattr(now, p):
                attr = getattr(now, p)
                kwargs[p] = attr().isoformat() if callable(attr) else attr

        return kwargs

    def format(self, key: str) -> str:
        """Form a new key based on original key from argument.

        Replace and restructure key to represent the proper new form.

        Args:
            key (str): Original key.

        Returns:
            str: Formatted new key.

        """
        match = self.source_parser.match(key)
        if not match:
            raise AttributeError("Key doesn't match the expected source format")

        self.kwargs.update({k: match[k] for k in self.source_params})

        return self.destination_formatter.format(**self.kwargs)
