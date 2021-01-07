"""Solgate Exceptions registry module."""

from collections import namedtuple
from click import ClickException, BadParameter


class NoFilesToSyncError(ClickException):
    """An exception that Click raises when there's no files to be synced."""

    exit_code = 3


class FilesFailedToSyncError(ClickException):
    """An exception that Click raises when the sync was not fully successfull but no other exception was raised."""

    exit_code = 4


ExceptionWithErrorCode = namedtuple("ExceptionWithErrorCode", ["msg", "type"])

EXIT_CODES = {
    1: ExceptionWithErrorCode("Unexpected runtime error", ClickException),
    2: ExceptionWithErrorCode("Misconfiguration", BadParameter),
    3: ExceptionWithErrorCode("No new payloads found", NoFilesToSyncError),
    4: ExceptionWithErrorCode("Some files failed to sync", FilesFailedToSyncError),
}
