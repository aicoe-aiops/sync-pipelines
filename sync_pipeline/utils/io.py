"""IO helpers."""

import json
from typing import Any


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
