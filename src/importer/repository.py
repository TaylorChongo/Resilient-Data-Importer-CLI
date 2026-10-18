"""Store users in a JSON file acting as a simple database.

This module follows the repository pattern: the rest of the program talks
to the UserRepository interface and never needs to know that the data
ends up in a JSON file.
"""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
from typing import Any, Protocol, TextIO

from importer.exceptions import DuplicateUserError, StorageError
from importer.models import User

logger = logging.getLogger(__name__)

USER_FIELDS = frozenset(field.name for field in fields(User))


class UserRepository(Protocol):
    """Interface that any user storage must provide."""

    def add(self, user: User) -> None:
        """Stage a new user to be saved.

        Raises:
            DuplicateUserError: If a user with the same ID already exists.
        """

    def save(self) -> None:
        """Persist all staged users.

        Raises:
            StorageError: If the users cannot be written.
        """


@contextmanager
def atomic_write(path: Path) -> Iterator[TextIO]:
    """Write a file so that it is either fully updated or left untouched.

    Content is first written to a temporary file next to the target. Only
    when writing succeeds is the temporary file renamed over the target,
    which the operating system performs as a single step. If anything fails,
    the temporary file is removed and the original file is unchanged.

    Args:
        path: The file to create or replace.

    Yields:
        A text file open for writing.

    Raises:
        OSError: If the temporary file cannot be created or renamed.
    """
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            yield file
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


class JsonUserRepository:
    """User storage backed by a JSON file.

    The file holds a list of user objects. It is read once when the
    repository is created; new users are kept in memory until save() is
    called, so a failed import never leaves a half-written database.
    """

    def __init__(self, path: Path) -> None:
        """Load existing users from the JSON file, if it exists.

        Args:
            path: Location of the JSON database file.

        Raises:
            StorageError: If the file exists but cannot be read or does not
                contain a valid list of users.
        """
        self._path = path
        self._users = self._load()

    def add(self, user: User) -> None:
        """Stage a new user to be saved.

        Args:
            user: The user to add.

        Raises:
            DuplicateUserError: If a user with the same ID is already stored
                or was already added.
        """
        if user.user_id in self._users:
            raise DuplicateUserError(user.user_id)
        self._users[user.user_id] = user

    def save(self) -> None:
        """Write all users to the JSON file atomically.

        Raises:
            StorageError: If the file cannot be written.
        """
        records = [user.to_dict() for user in self._users.values()]
        try:
            with atomic_write(self._path) as file:
                json.dump(records, file, indent=2, ensure_ascii=False)
                file.write("\n")
        except OSError as err:
            raise StorageError(f"Cannot write {self._path}: {err}") from err
        logger.debug("Saved %d user(s) to %s", len(records), self._path)

    def list_all(self) -> list[User]:
        """Return every stored user, including ones not yet saved.

        Returns:
            The users in the order they were added.
        """
        return list(self._users.values())

    def _load(self) -> dict[str, User]:
        """Read the users currently stored in the JSON file.

        Returns:
            The stored users, keyed by user ID. Empty if there is no file yet.

        Raises:
            StorageError: If the file cannot be read or parsed.
        """
        if not self._path.exists():
            logger.info("No database at %s yet; a new one will be created", self._path)
            return {}

        try:
            with self._path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, ValueError) as err:
            # ValueError covers both invalid JSON and invalid UTF-8.
            raise StorageError(f"Cannot read {self._path}: {err}") from err

        return self._parse_records(data)

    def _parse_records(self, data: Any) -> dict[str, User]:
        """Convert decoded JSON into users, checking its structure.

        Args:
            data: The decoded content of the JSON file.

        Returns:
            The users, keyed by user ID.

        Raises:
            StorageError: If the data is not a list of valid user objects.
        """
        if not isinstance(data, list):
            raise StorageError(f"{self._path} must contain a JSON list of users")

        users: dict[str, User] = {}
        for index, record in enumerate(data):
            if not _is_valid_record(record):
                raise StorageError(f"{self._path}: record {index} is not a valid user")
            user = User(**record)
            users[user.user_id] = user
        return users


def _is_valid_record(record: Any) -> bool:
    """Check that a decoded JSON value has exactly the User fields, as text.

    Args:
        record: One element of the decoded JSON list.

    Returns:
        True if the record can safely be turned into a User.
    """
    return (
        isinstance(record, dict)
        and record.keys() == USER_FIELDS
        and all(isinstance(value, str) for value in record.values())
    )
