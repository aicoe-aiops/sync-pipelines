"""Common logging setup for logstash."""

import logging
import sys
from logstash_formatter import LogstashFormatterV1  # type: ignore


def create_logger() -> logging.Logger:
    """Set up logstash formatted logger.

    Returns:
        logging.Logger: Python logger for __name__

    """
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(LogstashFormatterV1())
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]

    return logger


logger = create_logger()
