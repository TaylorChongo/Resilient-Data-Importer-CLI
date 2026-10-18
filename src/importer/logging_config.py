"""Configure where and how the importer's log messages are written."""

import logging
from pathlib import Path

# Short format for people reading the terminal.
CONSOLE_FORMAT = "%(levelname)s: %(message)s"

# Detailed format for log files, so each line can be traced and filtered later.
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

PACKAGE_LOGGER = "importer"


def configure_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    """Send the importer's log messages to the terminal and optionally a file.

    Only the "importer" package logger is configured, so log messages from
    other libraries are left alone. Calling this again replaces the previous
    configuration instead of adding duplicate handlers.

    Args:
        level: Minimum level of messages to show, e.g. logging.DEBUG.
        log_file: If given, also append detailed log lines to this file.

    Raises:
        OSError: If the log file cannot be opened.
    """
    logger = logging.getLogger(PACKAGE_LOGGER)
    logger.setLevel(level)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    console = logging.StreamHandler()  # writes to stderr
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)
