"""Tests for the CSV parser."""

import csv
import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from importer.exceptions import FileFormatError, MissingFileError
from importer.parser import CsvUserParser, RawRow, open_csv

WriteCsv = Callable[[str], Path]


@pytest.fixture
def parser() -> CsvUserParser:
    """Provide a fresh parser for each test."""
    return CsvUserParser()


# --- Reading valid files ---------------------------------------------------


def test_parse_yields_one_raw_row_per_data_row(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv(
        "user_id,name,email\n"
        "1,Ada Lovelace,ada@example.com\n"
        "2,Alan Turing,alan@example.com\n"
    )

    rows = list(parser.parse(path))

    assert rows == [
        RawRow(2, {"user_id": "1", "name": "Ada Lovelace", "email": "ada@example.com"}),
        RawRow(3, {"user_id": "2", "name": "Alan Turing", "email": "alan@example.com"}),
    ]


def test_parse_header_only_file_yields_nothing(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv("user_id,name,email\n")

    assert list(parser.parse(path)) == []


@pytest.mark.parametrize(
    "header",
    [
        "user_id,name,email",
        "USER_ID,Name,EMAIL",
        " user_id , name , email ",
        "﻿user_id,name,email",  # byte order mark added by Excel
        "email,name,user_id",
    ],
)
def test_parse_accepts_header_variations(
    parser: CsvUserParser, write_csv: WriteCsv, header: str
) -> None:
    values = {"user_id": "1", "name": "Ada", "email": "ada@example.com"}
    columns = [column.strip().lower().lstrip("﻿") for column in header.split(",")]
    row = ",".join(values[column] for column in columns)
    path = write_csv(f"{header}\n{row}\n")

    (raw_row,) = parser.parse(path)

    assert raw_row.values == values


def test_parse_strips_whitespace_around_values(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv("user_id,name,email\n  1 ,  Ada  , ada@example.com \n")

    (row,) = parser.parse(path)

    assert row.values == {"user_id": "1", "name": "Ada", "email": "ada@example.com"}


def test_parse_handles_quoted_values_with_commas(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv('user_id,name,email\n1,"Lovelace, Ada",ada@example.com\n')

    (row,) = parser.parse(path)

    assert row.values["name"] == "Lovelace, Ada"


def test_parse_skips_blank_lines_but_keeps_real_line_numbers(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv("user_id,name,email\n\n1,Ada,ada@example.com\n")

    (row,) = parser.parse(path)

    assert row.row_number == 3


def test_parse_ignores_unknown_columns_and_logs_warning(
    parser: CsvUserParser, write_csv: WriteCsv, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_csv("user_id,name,email,age\n1,Ada,ada@example.com,36\n")

    with caplog.at_level(logging.WARNING):
        (row,) = parser.parse(path)

    assert row.values == {"user_id": "1", "name": "Ada", "email": "ada@example.com"}
    assert "Ignoring unknown column(s): age" in caplog.text


# --- Malformed rows (reported, not raised) ---------------------------------


def test_parse_fills_missing_values_with_empty_string(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv("user_id,name,email\n1,Ada\n")

    (row,) = parser.parse(path)

    assert row.values == {"user_id": "1", "name": "Ada", "email": ""}
    assert row.extra_values == ()


def test_parse_collects_values_beyond_the_last_column(
    parser: CsvUserParser, write_csv: WriteCsv
) -> None:
    path = write_csv("user_id,name,email\n1,Ada,ada@example.com,oops,again\n")

    (row,) = parser.parse(path)

    assert row.extra_values == ("oops", "again")


# --- Errors that stop the whole import -------------------------------------


def test_parse_missing_file_raises_missing_file_error(
    parser: CsvUserParser, tmp_path: Path
) -> None:
    path = tmp_path / "does_not_exist.csv"

    with pytest.raises(MissingFileError) as exc_info:
        list(parser.parse(path))

    assert exc_info.value.path == path


def test_parse_directory_raises_file_format_error(
    parser: CsvUserParser, tmp_path: Path
) -> None:
    with pytest.raises(FileFormatError, match="Cannot open"):
        list(parser.parse(tmp_path))


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ("", "is empty"),
        ("user_id,name\n1,Ada\n", "missing required column(s): email"),
        ("id,full_name,mail\n", "user_id, name, email"),
    ],
)
def test_parse_bad_header_raises_file_format_error(
    parser: CsvUserParser, write_csv: WriteCsv, content: str, expected_message: str
) -> None:
    path = write_csv(content)

    with pytest.raises(FileFormatError) as exc_info:
        list(parser.parse(path))

    assert expected_message in str(exc_info.value)


def test_parse_non_utf8_file_raises_file_format_error(
    parser: CsvUserParser, tmp_path: Path
) -> None:
    path = tmp_path / "latin1.csv"
    path.write_bytes("user_id,name,email\n1,José,jose@example.com\n".encode("latin-1"))

    with pytest.raises(FileFormatError, match="Cannot read"):
        list(parser.parse(path))


def test_parse_csv_error_raises_file_format_error(
    parser: CsvUserParser, write_csv: WriteCsv, mocker: MockerFixture
) -> None:
    path = write_csv("user_id,name,email\n")
    mocker.patch("importer.parser.csv.DictReader", side_effect=csv.Error("broken"))

    with pytest.raises(FileFormatError, match="broken"):
        list(parser.parse(path))


# --- The open_csv context manager ------------------------------------------


def test_open_csv_closes_file_after_block(write_csv: WriteCsv) -> None:
    path = write_csv("user_id,name,email\n")

    with open_csv(path) as file:
        assert not file.closed

    assert file.closed


def test_open_csv_closes_file_even_when_block_raises(write_csv: WriteCsv) -> None:
    path = write_csv("user_id,name,email\n")

    with pytest.raises(RuntimeError), open_csv(path) as file:
        raise RuntimeError("something went wrong inside the block")

    assert file.closed
