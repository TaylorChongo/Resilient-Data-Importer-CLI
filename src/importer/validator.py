"""Turn raw CSV rows into validated User objects."""

import re

from importer.exceptions import ValidationError
from importer.models import User
from importer.parser import REQUIRED_COLUMNS, RawRow

# Deliberately simple: one "@", no spaces, and a dot in the domain part.
# Fully validating email addresses is notoriously complex; this catches
# the typos that actually happen in spreadsheets.
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# Letters, digits, hyphens and underscores, e.g. "42", "007" or "emp-1029".
USER_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


class UserValidator:
    """Check raw rows and convert the valid ones into users."""

    def validate(self, row: RawRow) -> User:
        """Validate a raw row and build a User from it.

        All problems in the row are collected and reported together, so the
        person fixing the file sees everything that is wrong at once.

        Args:
            row: The unvalidated row produced by the parser.

        Returns:
            A User built from the row's values.

        Raises:
            ValidationError: If the row has any invalid or missing values.
        """
        problems = self._find_problems(row)
        if problems:
            raise ValidationError(row.row_number, "; ".join(problems))

        return User(
            user_id=row.values["user_id"],
            name=row.values["name"],
            email=row.values["email"],
        )

    @staticmethod
    def _find_problems(row: RawRow) -> list[str]:
        """List everything that is wrong with a row.

        Args:
            row: The unvalidated row produced by the parser.

        Returns:
            A description of each problem found; empty if the row is valid.
        """
        problems: list[str] = []

        if row.extra_values:
            problems.append(f"unexpected extra value(s): {', '.join(row.extra_values)}")

        for column in REQUIRED_COLUMNS:
            if not row.values[column]:
                problems.append(f"{column} is required")

        user_id = row.values["user_id"]
        if user_id and not USER_ID_PATTERN.fullmatch(user_id):
            problems.append(
                f"invalid user_id '{user_id}' "
                "(use only letters, digits, '-' and '_')"
            )

        email = row.values["email"]
        if email and not EMAIL_PATTERN.fullmatch(email):
            problems.append(f"invalid email '{email}'")

        return problems
