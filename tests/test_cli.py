"""End-to-end tests for the command-line interface.

These tests run the real program with real files, exactly as a user would,
and check the exit code, the terminal output and the resulting database.
"""

import json
import runpy
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from importer.cli import EXIT_FAILURE, EXIT_SUCCESS, main

WriteCsv = Callable[[str], Path]

GOOD_CSV = (
    "user_id,name,email\n"
    "1,Ada Lovelace,ada@example.com\n"
    "2,Alan Turing,alan@example.com\n"
    "3,,grace@example.com\n"
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Location for the JSON database used by a test."""
    return tmp_path / "users.json"


def saved_ids(db_path: Path) -> list[str]:
    """Return the user IDs stored in the JSON database."""
    users = json.loads(db_path.read_text(encoding="utf-8"))
    return [user["user_id"] for user in users]


# --- Successful runs -------------------------------------------------------


def test_import_returns_success_and_prints_summary(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv(GOOD_CSV)

    exit_code = main([str(csv_path), "--db", str(db_path)])

    out, err = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert "Imported 2 user(s)" in out
    assert "skipped 1 invalid and 0 duplicate row(s)" in out
    assert "WARNING: Skipped invalid row 4: name is required" in err
    assert saved_ids(db_path) == ["1", "2"]


def test_importing_same_file_twice_reports_duplicates(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv(GOOD_CSV)
    main([str(csv_path), "--db", str(db_path)])
    capsys.readouterr()  # discard the output of the first run

    exit_code = main([str(csv_path), "--db", str(db_path)])

    out, _ = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert "Imported 0 user(s)" in out
    assert "2 duplicate row(s)" in out
    assert saved_ids(db_path) == ["1", "2"]


def test_database_defaults_to_users_json_in_current_folder(
    write_csv: WriteCsv, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = write_csv(GOOD_CSV)
    monkeypatch.chdir(tmp_path)

    main([str(csv_path)])

    assert saved_ids(tmp_path / "users.json") == ["1", "2"]


# --- Failures --------------------------------------------------------------


def test_missing_csv_file_fails_with_clear_message(
    tmp_path: Path, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "nope.csv"

    exit_code = main([str(missing), "--db", str(db_path)])

    _, err = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert f"ERROR: File not found: {missing}" in err
    assert not db_path.exists()


def test_csv_with_wrong_headers_fails(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv("id,full_name\n1,Ada\n")

    exit_code = main([str(csv_path), "--db", str(db_path)])

    _, err = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "missing required column(s): user_id, name, email" in err


def test_corrupted_database_fails_and_is_left_untouched(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv(GOOD_CSV)
    db_path.write_text("{not valid json", encoding="utf-8")

    exit_code = main([str(csv_path), "--db", str(db_path)])

    _, err = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "Cannot read" in err
    assert db_path.read_text(encoding="utf-8") == "{not valid json"


# --- Command-line options --------------------------------------------------


def test_verbose_shows_every_imported_row(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv(GOOD_CSV)

    main([str(csv_path), "--db", str(db_path), "--verbose"])

    _, err = capsys.readouterr()
    assert "DEBUG: Imported user '1' from row 2" in err


def test_quiet_shows_only_warnings_and_errors(
    write_csv: WriteCsv, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = write_csv(GOOD_CSV)

    main([str(csv_path), "--db", str(db_path), "-q"])

    _, err = capsys.readouterr()
    assert "INFO" not in err
    assert "WARNING: Skipped invalid row 4" in err


def test_log_file_receives_timestamped_lines(
    write_csv: WriteCsv, db_path: Path, tmp_path: Path
) -> None:
    csv_path = write_csv(GOOD_CSV)
    log_file = tmp_path / "import.log"

    main([str(csv_path), "--db", str(db_path), "--log-file", str(log_file)])

    log_text = log_file.read_text(encoding="utf-8")
    assert "| INFO     | importer.service | Importing users from" in log_text
    assert "| WARNING  | importer.service | Skipped invalid row 4" in log_text


def test_unusable_log_file_fails_with_clear_message(
    write_csv: WriteCsv,
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    csv_path = write_csv(GOOD_CSV)
    log_file = tmp_path / "no_such_folder" / "import.log"

    exit_code = main([str(csv_path), "--db", str(db_path), "--log-file", str(log_file)])

    _, err = capsys.readouterr()
    assert exit_code == EXIT_FAILURE
    assert "cannot open log file" in err
    assert not db_path.exists()


@pytest.mark.parametrize(
    ("argv", "expected_in_error"),
    [
        ([], "the following arguments are required: csv_file"),
        (["users.csv", "-v", "-q"], "not allowed with argument"),
        (["users.csv", "--unknown"], "unrecognized arguments: --unknown"),
    ],
)
def test_invalid_arguments_exit_with_code_2(
    argv: list[str], expected_in_error: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    _, err = capsys.readouterr()
    assert exc_info.value.code == 2
    assert expected_in_error in err


def test_help_describes_the_tool(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    out, _ = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "Import users from a CSV file into a JSON database." in out
    assert "user_id, name, email" in out


# --- Running as a module ---------------------------------------------------


def test_python_dash_m_importer_runs_the_cli(
    write_csv: WriteCsv, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = write_csv(GOOD_CSV)
    monkeypatch.setattr(sys, "argv", ["importer", str(csv_path), "--db", str(db_path)])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("importer", run_name="__main__")

    assert exc_info.value.code == EXIT_SUCCESS
    assert saved_ids(db_path) == ["1", "2"]
