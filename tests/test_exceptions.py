"""Tests for the custom exception hierarchy."""

from pathlib import Path

import pytest

from importer.exceptions import (
    DuplicateUserError,
    FileFormatError,
    ImporterError,
    MissingFileError,
    StorageError,
    ValidationError,
)


@pytest.mark.parametrize(
    "error",
    [
        MissingFileError(Path("users.csv")),
        FileFormatError("missing column: email"),
        ValidationError(row_number=4, reason="invalid email"),
        DuplicateUserError(user_id="007"),
        StorageError("users.json is corrupted"),
    ],
)
def test_every_error_can_be_caught_as_importer_error(error: ImporterError) -> None:
    with pytest.raises(ImporterError):
        raise error


def test_missing_file_error_keeps_path() -> None:
    path = Path("data") / "users.csv"

    error = MissingFileError(path)

    assert error.path == path
    assert str(path) in str(error)


def test_file_format_error_keeps_message() -> None:
    error = FileFormatError("missing column: email")

    assert str(error) == "missing column: email"


def test_validation_error_keeps_row_and_reason() -> None:
    error = ValidationError(row_number=4, reason="invalid email 'abc'")

    assert error.row_number == 4
    assert error.reason == "invalid email 'abc'"
    assert str(error) == "Row 4: invalid email 'abc'"


def test_duplicate_user_error_keeps_user_id() -> None:
    error = DuplicateUserError(user_id="007")

    assert error.user_id == "007"
    assert "007" in str(error)
