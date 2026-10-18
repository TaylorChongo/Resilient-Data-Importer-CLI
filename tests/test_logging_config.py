"""Tests for the logging configuration."""

import logging
from pathlib import Path

from importer.logging_config import PACKAGE_LOGGER, configure_logging


def test_configure_logging_sets_level_and_console_handler() -> None:
    configure_logging(logging.WARNING)

    logger = logging.getLogger(PACKAGE_LOGGER)
    assert logger.level == logging.WARNING
    assert len(logger.handlers) == 1


def test_configure_logging_twice_does_not_duplicate_handlers() -> None:
    configure_logging()
    configure_logging()

    assert len(logging.getLogger(PACKAGE_LOGGER).handlers) == 1


def test_configure_logging_writes_detailed_lines_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "import.log"
    configure_logging(logging.INFO, log_file)

    logging.getLogger("importer.example").info("hello from a test")

    line = log_file.read_text(encoding="utf-8").strip()
    # e.g. "2026-10-18 15:42:07 | INFO     | importer.example | hello from a test"
    timestamp, level, name, message = line.split(" | ")
    assert len(timestamp) == len("2026-10-18 15:42:07")
    assert level.strip() == "INFO"
    assert name == "importer.example"
    assert message == "hello from a test"
