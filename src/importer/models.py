"""Data models used throughout the importer."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class User:
    """A validated user record ready to be stored.

    Attributes:
        user_id: Unique identifier of the user, kept as text to preserve
            values such as leading zeros.
        name: Full name of the user.
        email: Email address of the user.
    """

    user_id: str
    name: str
    email: str

    def to_dict(self) -> dict[str, str]:
        """Convert the user into a dictionary suitable for JSON storage.

        Returns:
            A mapping of field names to their values.
        """
        return asdict(self)
