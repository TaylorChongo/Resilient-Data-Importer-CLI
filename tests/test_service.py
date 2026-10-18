"""Tests for the import service.

Most tests replace the parser, validator and repository with mocks, so they
check only the service's own logic: the order of calls, error handling and
counting. The last test wires up the real components end to end.
"""

import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from importer.exceptions import (
    DuplicateUserError,
    FileFormatError,
    StorageError,
    ValidationError,
)
from importer.models import User
from importer.parser import CsvUserParser, RawRow
from importer.repository import JsonUserRepository
from importer.service import ImportSummary, UserImporter
from importer.validator import UserValidator

CSV_PATH = Path("users.csv")

ROW_2 = RawRow(2, {"user_id": "1", "name": "Ada", "email": "ada@example.com"})
ROW_3 = RawRow(3, {"user_id": "2", "name": "", "email": "alan@example.com"})
ROW_4 = RawRow(4, {"user_id": "1", "name": "Ada", "email": "ada@example.com"})

ADA = User(user_id="1", name="Ada", email="ada@example.com")
GRACE = User(user_id="3", name="Grace", email="grace@example.com")


@pytest.fixture
def parser(mocker: MockerFixture) -> MagicMock:
    """A fake parser; each test decides which rows it returns."""
    mock: MagicMock = mocker.create_autospec(CsvUserParser, instance=True)
    return mock


@pytest.fixture
def validator(mocker: MockerFixture) -> MagicMock:
    """A fake validator; each test decides what it returns or raises."""
    mock: MagicMock = mocker.create_autospec(UserValidator, instance=True)
    return mock


@pytest.fixture
def repository(mocker: MockerFixture) -> MagicMock:
    """A fake repository that records calls instead of touching files."""
    mock: MagicMock = mocker.create_autospec(JsonUserRepository, instance=True)
    return mock


@pytest.fixture
def importer(
    parser: MagicMock, validator: MagicMock, repository: MagicMock
) -> UserImporter:
    """The service under test, wired to the three mocks."""
    return UserImporter(parser, validator, repository)


# --- Successful imports ----------------------------------------------------


def test_run_imports_every_valid_row_and_saves_once(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
) -> None:
    parser.parse.return_value = [ROW_2, ROW_3]
    validator.validate.side_effect = [ADA, GRACE]

    summary = importer.run(CSV_PATH)

    parser.parse.assert_called_once_with(CSV_PATH)
    assert repository.add.call_args_list == [((ADA,),), ((GRACE,),)]
    repository.save.assert_called_once_with()
    assert summary == ImportSummary(imported=2)


def test_run_with_empty_file_does_not_save(
    importer: UserImporter, parser: MagicMock, repository: MagicMock
) -> None:
    parser.parse.return_value = []

    summary = importer.run(CSV_PATH)

    repository.save.assert_not_called()
    assert summary.total == 0


# --- Bad rows are skipped, not fatal ---------------------------------------


def test_run_skips_invalid_rows_and_continues(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser.parse.return_value = [ROW_2, ROW_3]
    validator.validate.side_effect = [ADA, ValidationError(3, "name is required")]

    summary = importer.run(CSV_PATH)

    repository.add.assert_called_once_with(ADA)
    repository.save.assert_called_once_with()
    assert summary == ImportSummary(imported=1, invalid=1)
    assert "Skipped invalid row 3: name is required" in caplog.text


def test_run_skips_duplicate_users_and_continues(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser.parse.return_value = [ROW_2, ROW_4]
    validator.validate.return_value = ADA
    repository.add.side_effect = [None, DuplicateUserError("1")]

    summary = importer.run(CSV_PATH)

    repository.save.assert_called_once_with()
    assert summary == ImportSummary(imported=1, duplicates=1)
    assert "Skipped row 4: user ID '1' already exists" in caplog.text


def test_run_with_only_bad_rows_does_not_save(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
) -> None:
    parser.parse.return_value = [ROW_3]
    validator.validate.side_effect = ValidationError(3, "name is required")

    summary = importer.run(CSV_PATH)

    repository.add.assert_not_called()
    repository.save.assert_not_called()
    assert summary == ImportSummary(invalid=1)


# --- File-level errors abort the import ------------------------------------


def test_run_aborts_without_saving_when_file_is_invalid(
    importer: UserImporter,
    parser: MagicMock,
    repository: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser.parse.side_effect = FileFormatError("missing column: email")

    with pytest.raises(FileFormatError):
        importer.run(CSV_PATH)

    repository.save.assert_not_called()
    assert "Import aborted; no users were saved" in caplog.text


def test_run_does_not_save_rows_read_before_a_file_error(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
) -> None:
    def rows_then_failure(path: Path) -> Iterator[RawRow]:
        yield ROW_2
        raise FileFormatError("file is not valid UTF-8")

    parser.parse.side_effect = rows_then_failure
    validator.validate.return_value = ADA

    with pytest.raises(FileFormatError):
        importer.run(CSV_PATH)

    repository.add.assert_called_once_with(ADA)
    repository.save.assert_not_called()


def test_run_propagates_storage_error_from_save(
    importer: UserImporter,
    parser: MagicMock,
    validator: MagicMock,
    repository: MagicMock,
) -> None:
    parser.parse.return_value = [ROW_2]
    validator.validate.return_value = ADA
    repository.save.side_effect = StorageError("disk full")

    with pytest.raises(StorageError, match="disk full"):
        importer.run(CSV_PATH)


def test_run_always_logs_the_summary(
    importer: UserImporter,
    parser: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser.parse.side_effect = FileFormatError("broken")

    with caplog.at_level(logging.INFO), pytest.raises(FileFormatError):
        importer.run(CSV_PATH)

    assert "Rows processed: 0" in caplog.text


# --- Summary ---------------------------------------------------------------


def test_summary_total_adds_up_all_outcomes() -> None:
    summary = ImportSummary(imported=3, invalid=2, duplicates=1)

    assert summary.total == 6


# --- Real components working together --------------------------------------


def test_run_with_real_components(
    write_csv: Callable[[str], Path], tmp_path: Path
) -> None:
    csv_path = write_csv(
        "user_id,name,email\n"
        "1,Ada Lovelace,ada@example.com\n"
        "2,,alan@example.com\n"
        "3,Grace Hopper,not-an-email\n"
        "1,Ada Again,ada2@example.com\n"
        "4,Alan Turing,alan@example.com\n"
    )
    db_path = tmp_path / "users.json"
    importer = UserImporter(
        CsvUserParser(), UserValidator(), JsonUserRepository(db_path)
    )

    summary = importer.run(csv_path)

    assert summary == ImportSummary(imported=2, invalid=2, duplicates=1)
    saved = json.loads(db_path.read_text(encoding="utf-8"))
    assert [user["user_id"] for user in saved] == ["1", "4"]
