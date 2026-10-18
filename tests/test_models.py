"""Tests for the importer data models."""

import dataclasses

import pytest

from importer.models import User


@pytest.fixture
def user() -> User:
    """Provide a sample user for the tests."""
    return User(user_id="007", name="James Bond", email="james@mi6.gov.uk")


def test_user_stores_its_fields(user: User) -> None:
    assert user.user_id == "007"
    assert user.name == "James Bond"
    assert user.email == "james@mi6.gov.uk"


def test_user_is_immutable(user: User) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        user.name = "Someone Else"  # type: ignore[misc]


def test_users_with_same_data_are_equal(user: User) -> None:
    same_user = User(user_id="007", name="James Bond", email="james@mi6.gov.uk")

    assert user == same_user


def test_to_dict_returns_all_fields(user: User) -> None:
    assert user.to_dict() == {
        "user_id": "007",
        "name": "James Bond",
        "email": "james@mi6.gov.uk",
    }
