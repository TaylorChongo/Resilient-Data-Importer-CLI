"""Tests for the user validator."""

import pytest

from importer.exceptions import ValidationError
from importer.models import User
from importer.parser import RawRow
from importer.validator import UserValidator


@pytest.fixture
def validator() -> UserValidator:
    """Provide a fresh validator for each test."""
    return UserValidator()


def make_row(
    user_id: str = "1",
    name: str = "Ada Lovelace",
    email: str = "ada@example.com",
    extra_values: tuple[str, ...] = (),
    row_number: int = 2,
) -> RawRow:
    """Build a RawRow that is valid unless a field is overridden."""
    values = {"user_id": user_id, "name": name, "email": email}
    return RawRow(row_number, values, extra_values)


def test_validate_valid_row_returns_user(validator: UserValidator) -> None:
    user = validator.validate(make_row())

    assert user == User(user_id="1", name="Ada Lovelace", email="ada@example.com")


@pytest.mark.parametrize("user_id", ["1", "007", "emp-1029", "A_42"])
def test_validate_accepts_valid_user_ids(
    validator: UserValidator, user_id: str
) -> None:
    assert validator.validate(make_row(user_id=user_id)).user_id == user_id


@pytest.mark.parametrize(
    "email",
    ["ada@example.com", "ada.lovelace+news@mail.example.co.uk", "A@B.IO"],
)
def test_validate_accepts_valid_emails(validator: UserValidator, email: str) -> None:
    assert validator.validate(make_row(email=email)).email == email


@pytest.mark.parametrize(
    ("row", "expected_reason"),
    [
        (make_row(user_id=""), "user_id is required"),
        (make_row(name=""), "name is required"),
        (make_row(email=""), "email is required"),
        (make_row(user_id="12 34"), "invalid user_id '12 34'"),
        (make_row(user_id="id#1"), "invalid user_id 'id#1'"),
        (make_row(email="ada.example.com"), "invalid email 'ada.example.com'"),
        (make_row(email="ada@example"), "invalid email 'ada@example'"),
        (make_row(email="ada@@example.com"), "invalid email 'ada@@example.com'"),
        (make_row(email="ada @example.com"), "invalid email 'ada @example.com'"),
        (make_row(extra_values=("oops",)), "unexpected extra value(s): oops"),
    ],
)
def test_validate_invalid_row_raises_validation_error(
    validator: UserValidator, row: RawRow, expected_reason: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(row)

    assert expected_reason in exc_info.value.reason


def test_validate_error_reports_the_row_number(validator: UserValidator) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(make_row(email="", row_number=7))

    assert exc_info.value.row_number == 7
    assert str(exc_info.value) == "Row 7: email is required"


def test_validate_reports_all_problems_at_once(validator: UserValidator) -> None:
    row = make_row(name="", email="not-an-email", extra_values=("x",))

    with pytest.raises(ValidationError) as exc_info:
        validator.validate(row)

    assert exc_info.value.reason == (
        "unexpected extra value(s): x; "
        "name is required; "
        "invalid email 'not-an-email'"
    )
