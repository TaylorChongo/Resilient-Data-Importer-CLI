"""Coordinate the import: parse rows, validate them and store the users."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from importer.exceptions import DuplicateUserError, ImporterError, ValidationError
from importer.models import User
from importer.parser import RawRow
from importer.repository import UserRepository

logger = logging.getLogger(__name__)


class RowParser(Protocol):
    """Interface for anything that can read raw rows from a file."""

    def parse(self, path: Path) -> Iterable[RawRow]:
        """Read the rows of the given file.

        Raises:
            ImporterError: If the file as a whole cannot be read.
        """


class RowValidator(Protocol):
    """Interface for anything that can turn a raw row into a user."""

    def validate(self, row: RawRow) -> User:
        """Build a user from a row.

        Raises:
            ValidationError: If the row contains invalid data.
        """


@dataclass
class ImportSummary:
    """Counts of what happened to the rows during an import.

    Attributes:
        imported: Rows stored as new users.
        invalid: Rows skipped because their data was invalid.
        duplicates: Rows skipped because the user ID already existed.
    """

    imported: int = 0
    invalid: int = 0
    duplicates: int = 0

    @property
    def total(self) -> int:
        """Number of rows processed."""
        return self.imported + self.invalid + self.duplicates


class UserImporter:
    """Import users from a file into a repository.

    Bad rows are skipped and reported without stopping the import. Problems
    with the file as a whole (missing, wrong headers, unreadable) abort the
    import, and in that case nothing is saved.
    """

    def __init__(
        self,
        parser: RowParser,
        validator: RowValidator,
        repository: UserRepository,
    ) -> None:
        """Create an importer from its three collaborators.

        Args:
            parser: Reads raw rows from the input file.
            validator: Turns raw rows into users.
            repository: Stores the users.
        """
        self._parser = parser
        self._validator = validator
        self._repository = repository

    def run(self, path: Path) -> ImportSummary:
        """Import every valid user from the file.

        Args:
            path: Location of the input file.

        Returns:
            Counts of imported and skipped rows.

        Raises:
            ImporterError: If the file cannot be processed or the users
                cannot be saved. No users are saved in that case.
        """
        summary = ImportSummary()
        logger.info("Importing users from %s", path)

        try:
            for row in self._parser.parse(path):
                self._import_row(row, summary)
        except ImporterError:
            logger.error("Import aborted; no users were saved")
            raise
        else:
            if summary.imported:
                self._repository.save()
            else:
                logger.info("No new users to save")
        finally:
            logger.info(
                "Rows processed: %d (imported: %d, invalid: %d, duplicates: %d)",
                summary.total,
                summary.imported,
                summary.invalid,
                summary.duplicates,
            )

        return summary

    def _import_row(self, row: RawRow, summary: ImportSummary) -> None:
        """Validate and store a single row, recording the outcome.

        Args:
            row: The raw row to import.
            summary: Counts to update with the row's outcome.
        """
        try:
            user = self._validator.validate(row)
            self._repository.add(user)
        except ValidationError as err:
            summary.invalid += 1
            logger.warning("Skipped invalid row %d: %s", err.row_number, err.reason)
        except DuplicateUserError as err:
            summary.duplicates += 1
            logger.warning(
                "Skipped row %d: user ID '%s' already exists",
                row.row_number,
                err.user_id,
            )
        else:
            summary.imported += 1
            logger.debug("Imported user '%s' from row %d", user.user_id, row.row_number)
