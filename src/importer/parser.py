"""Read raw user rows from a CSV file.

The parser only reads the file and checks its structure (headers, encoding).
It does not judge whether the values themselves are valid; that is the job
of the validator.
"""

import csv
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from importer.exceptions import FileFormatError, MissingFileError

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ("user_id", "name", "email")


@dataclass(frozen=True)
class RawRow:
    """A single unvalidated row read from the CSV file.

    Attributes:
        row_number: Line number of the row in the file (the header is line 1).
        values: Value of each required column, stripped of surrounding
            whitespace. A value missing from the row is an empty string.
        extra_values: Values found beyond the last header column, which
            indicate a malformed row.
    """

    row_number: int
    values: dict[str, str]
    extra_values: tuple[str, ...] = ()


@contextmanager
def open_csv(path: Path) -> Iterator[TextIO]:
    """Open a CSV file for reading and guarantee that it gets closed.

    Args:
        path: Location of the CSV file.

    Yields:
        The open text file.

    Raises:
        MissingFileError: If the file does not exist.
        FileFormatError: If the file exists but cannot be opened.
    """
    try:
        # "utf-8-sig" also strips the invisible BOM that Excel adds.
        # newline="" is required by the csv module to handle line breaks.
        file = path.open(encoding="utf-8-sig", newline="")
    except FileNotFoundError as err:
        raise MissingFileError(path) from err
    except OSError as err:
        raise FileFormatError(f"Cannot open {path}: {err}") from err

    logger.debug("Opened %s", path)
    try:
        yield file
    finally:
        file.close()
        logger.debug("Closed %s", path)


class CsvUserParser:
    """Parse user rows from a CSV file."""

    def parse(self, path: Path) -> Iterator[RawRow]:
        """Read the CSV file and yield its rows one at a time.

        Rows are produced lazily, so even very large files are never loaded
        into memory all at once. Blank lines are skipped.

        Args:
            path: Location of the CSV file.

        Yields:
            One RawRow per data row in the file.

        Raises:
            MissingFileError: If the file does not exist.
            FileFormatError: If the file is empty, lacks a required column,
                is not valid UTF-8 or is not valid CSV.
        """
        with open_csv(path) as file:
            try:
                reader = csv.DictReader(file)
                reader.fieldnames = _normalize_headers(reader.fieldnames, path)
                for row in reader:
                    values = {
                        column: (row.get(column) or "").strip()
                        for column in REQUIRED_COLUMNS
                    }
                    extra_values = tuple(row.get(None) or ())
                    yield RawRow(reader.line_num, values, extra_values)
            except (csv.Error, UnicodeDecodeError) as err:
                raise FileFormatError(f"Cannot read {path}: {err}") from err


def _normalize_headers(fieldnames: Sequence[str] | None, path: Path) -> list[str]:
    """Clean up the header row and check that it has the required columns.

    Args:
        fieldnames: Column names as read from the file, or None if the file
            is empty.
        path: Location of the CSV file, used in error messages.

    Returns:
        The column names in lower case without surrounding whitespace.

    Raises:
        FileFormatError: If the file is empty or a required column is missing.
    """
    if fieldnames is None:
        raise FileFormatError(f"{path} is empty")

    headers = [name.strip().lower() for name in fieldnames]

    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise FileFormatError(
            f"{path} is missing required column(s): {', '.join(missing)}"
        )

    ignored = [header for header in headers if header not in REQUIRED_COLUMNS]
    if ignored:
        logger.warning("Ignoring unknown column(s): %s", ", ".join(ignored))

    return headers
