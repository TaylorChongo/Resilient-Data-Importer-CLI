"""Fixtures shared by all test modules."""

import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from importer.logging_config import PACKAGE_LOGGER


@pytest.fixture
def write_csv(tmp_path: Path) -> Callable[[str], Path]:
    """Provide a helper that writes text to a temporary CSV file.

    Returns:
        A function that takes the file content and returns the file's path.
    """

    def _write(content: str) -> Path:
        path = tmp_path / "users.csv"
        path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture(autouse=True)
def reset_importer_logger() -> Iterator[None]:
    """Undo any logging configuration a test made, so tests stay independent.

    Handlers are closed as well, which releases log files so the temporary
    folder can be deleted on Windows.
    """
    yield
    logger = logging.getLogger(PACKAGE_LOGGER)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
