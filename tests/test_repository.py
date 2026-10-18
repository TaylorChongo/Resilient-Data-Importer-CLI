"""Tests for the JSON user repository."""

import json
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from importer.exceptions import DuplicateUserError, StorageError
from importer.models import User
from importer.repository import JsonUserRepository, UserRepository, atomic_write

ADA = User(user_id="1", name="Ada Lovelace", email="ada@example.com")
ALAN = User(user_id="2", name="Alan Turing", email="alan@example.com")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide the location of a database file that does not exist yet."""
    return tmp_path / "users.json"


@pytest.fixture
def existing_db(db_path: Path) -> Path:
    """Provide a database file that already contains one user (Ada)."""
    db_path.write_text(json.dumps([ADA.to_dict()]), encoding="utf-8")
    return db_path


def read_json(path: Path) -> object:
    """Load a JSON file for assertions."""
    return json.loads(path.read_text(encoding="utf-8"))


# --- Loading ---------------------------------------------------------------


def test_missing_database_starts_empty(db_path: Path) -> None:
    repository = JsonUserRepository(db_path)

    assert repository.list_all() == []
    assert not db_path.exists()


def test_existing_database_is_loaded(existing_db: Path) -> None:
    repository = JsonUserRepository(existing_db)

    assert repository.list_all() == [ADA]


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ("", "Cannot read"),
        ("not json at all", "Cannot read"),
        ('{"user_id": "1"}', "must contain a JSON list"),
        ("[1, 2]", "record 0 is not a valid user"),
        ('[{"user_id": "1", "name": "Ada"}]', "record 0 is not a valid user"),
        (
            '[{"user_id": 1, "name": "Ada", "email": "ada@example.com"}]',
            "record 0 is not a valid user",
        ),
        (
            '[{"user_id": "1", "name": "A", "email": "a@b.co", "age": "36"}]',
            "record 0 is not a valid user",
        ),
    ],
)
def test_corrupted_database_raises_storage_error(
    db_path: Path, content: str, expected_message: str
) -> None:
    db_path.write_text(content, encoding="utf-8")

    with pytest.raises(StorageError, match=expected_message):
        JsonUserRepository(db_path)


def test_unreadable_database_raises_storage_error(tmp_path: Path) -> None:
    # A directory "exists" but cannot be opened as a file.
    with pytest.raises(StorageError, match="Cannot read"):
        JsonUserRepository(tmp_path)


# --- Adding ----------------------------------------------------------------


def test_add_user_is_listed_but_not_saved_yet(db_path: Path) -> None:
    repository = JsonUserRepository(db_path)

    repository.add(ADA)

    assert repository.list_all() == [ADA]
    assert not db_path.exists()


def test_add_user_already_in_database_raises_duplicate_error(
    existing_db: Path,
) -> None:
    repository = JsonUserRepository(existing_db)
    same_id = User(user_id=ADA.user_id, name="Someone Else", email="else@example.com")

    with pytest.raises(DuplicateUserError) as exc_info:
        repository.add(same_id)

    assert exc_info.value.user_id == ADA.user_id
    assert repository.list_all() == [ADA]


def test_add_same_user_twice_raises_duplicate_error(db_path: Path) -> None:
    repository = JsonUserRepository(db_path)
    repository.add(ADA)

    with pytest.raises(DuplicateUserError):
        repository.add(ADA)


# --- Saving ----------------------------------------------------------------


def test_save_writes_all_users_as_json_list(existing_db: Path) -> None:
    repository = JsonUserRepository(existing_db)
    repository.add(ALAN)

    repository.save()

    assert read_json(existing_db) == [ADA.to_dict(), ALAN.to_dict()]


def test_saved_users_are_loaded_by_a_new_repository(db_path: Path) -> None:
    first = JsonUserRepository(db_path)
    first.add(ADA)
    first.save()

    second = JsonUserRepository(db_path)

    assert second.list_all() == [ADA]


def test_save_keeps_non_ascii_characters_readable(db_path: Path) -> None:
    repository = JsonUserRepository(db_path)
    repository.add(User(user_id="3", name="José Núñez", email="jose@example.com"))

    repository.save()

    assert "José Núñez" in db_path.read_text(encoding="utf-8")


def test_save_into_missing_folder_raises_storage_error(tmp_path: Path) -> None:
    repository = JsonUserRepository(tmp_path / "no_such_folder" / "users.json")
    repository.add(ADA)

    with pytest.raises(StorageError, match="Cannot write"):
        repository.save()


def test_failed_save_leaves_original_file_untouched(
    existing_db: Path, mocker: MockerFixture
) -> None:
    original_content = existing_db.read_text(encoding="utf-8")
    repository = JsonUserRepository(existing_db)
    repository.add(ALAN)
    # Simulate the operating system failing at the very last step.
    mocker.patch.object(Path, "replace", side_effect=OSError("disk full"))

    with pytest.raises(StorageError, match="disk full"):
        repository.save()

    assert existing_db.read_text(encoding="utf-8") == original_content
    assert list(existing_db.parent.iterdir()) == [existing_db]


# --- The atomic_write context manager --------------------------------------


def test_atomic_write_replaces_file_on_success(db_path: Path) -> None:
    db_path.write_text("old", encoding="utf-8")

    with atomic_write(db_path) as file:
        file.write("new")

    assert db_path.read_text(encoding="utf-8") == "new"


def test_atomic_write_keeps_original_when_block_fails(db_path: Path) -> None:
    db_path.write_text("old", encoding="utf-8")

    with pytest.raises(RuntimeError), atomic_write(db_path) as file:
        file.write("half-written")
        raise RuntimeError("crash in the middle of writing")

    assert db_path.read_text(encoding="utf-8") == "old"
    assert list(db_path.parent.iterdir()) == [db_path]


def test_json_repository_satisfies_the_interface(db_path: Path) -> None:
    # mypy checks this assignment; the test documents the intent.
    repository: UserRepository = JsonUserRepository(db_path)

    repository.add(ADA)
    repository.save()

    assert read_json(db_path) == [ADA.to_dict()]
