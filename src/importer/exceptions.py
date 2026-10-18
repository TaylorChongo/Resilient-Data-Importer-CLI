"""Custom exceptions raised by the importer.

Every exception inherits from ImporterError, so callers can handle all
expected import failures with a single ``except ImporterError`` clause.
"""

from pathlib import Path


class ImporterError(Exception):
    """Base class for all errors raised by the importer."""


class MissingFileError(ImporterError):
    """Raised when the input CSV file does not exist.

    Attributes:
        path: Location of the file that could not be found.
    """

    def __init__(self, path: Path) -> None:
        """Initialise the error with the missing file's path.

        Args:
            path: Location of the file that could not be found.
        """
        self.path = path
        super().__init__(f"File not found: {path}")


class FileFormatError(ImporterError):
    """Raised when the CSV file is unreadable or its headers are wrong."""


class StorageError(ImporterError):
    """Raised when the JSON database cannot be read, parsed or written."""


class ValidationError(ImporterError):
    """Raised when a CSV row contains invalid data.

    Attributes:
        row_number: Line number of the invalid row in the CSV file.
        reason: Explanation of what is wrong with the row.
    """

    def __init__(self, row_number: int, reason: str) -> None:
        """Initialise the error with the row location and reason.

        Args:
            row_number: Line number of the invalid row in the CSV file.
            reason: Explanation of what is wrong with the row.
        """
        self.row_number = row_number
        self.reason = reason
        super().__init__(f"Row {row_number}: {reason}")


class DuplicateUserError(ImporterError):
    """Raised when a user with the same ID already exists in storage.

    Attributes:
        user_id: Identifier of the duplicated user.
    """

    def __init__(self, user_id: str) -> None:
        """Initialise the error with the duplicated user's ID.

        Args:
            user_id: Identifier of the duplicated user.
        """
        self.user_id = user_id
        super().__init__(f"User with ID '{user_id}' already exists")
