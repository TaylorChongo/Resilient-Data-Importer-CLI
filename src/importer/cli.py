"""Command-line interface for the importer."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from importer.exceptions import ImporterError
from importer.logging_config import configure_logging
from importer.parser import CsvUserParser
from importer.repository import JsonUserRepository
from importer.service import ImportSummary, UserImporter
from importer.validator import UserValidator

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
# Exit code 2 (wrong command-line arguments) is produced by argparse itself.

DEFAULT_DATABASE = Path("users.json")


def build_parser() -> argparse.ArgumentParser:
    """Define the command-line arguments.

    Returns:
        The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="importer",
        description="Import users from a CSV file into a JSON database.",
        epilog="The CSV file needs the columns: user_id, name, email.",
    )
    parser.add_argument("csv_file", type=Path, help="CSV file to import")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"JSON database file to update (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="also write detailed, timestamped logs to this file",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show every imported row",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="show only warnings and errors",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the importer from the command line.

    Args:
        argv: Command-line arguments without the program name. Defaults to
            the arguments the program was started with.

    Returns:
        The process exit code: 0 on success, 1 if the import failed.
    """
    args = build_parser().parse_args(argv)

    try:
        configure_logging(_log_level(args), args.log_file)
    except OSError as err:
        print(f"ERROR: cannot open log file {args.log_file}: {err}", file=sys.stderr)
        return EXIT_FAILURE

    try:
        importer = UserImporter(
            CsvUserParser(), UserValidator(), JsonUserRepository(args.db)
        )
        summary = importer.run(args.csv_file)
    except ImporterError as err:
        logger.error("%s", err)
        return EXIT_FAILURE

    print(_format_summary(summary, args.db))
    return EXIT_SUCCESS


def _log_level(args: argparse.Namespace) -> int:
    """Choose the logging level from the verbosity flags.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The logging level to use.
    """
    if args.verbose:
        return logging.DEBUG
    if args.quiet:
        return logging.WARNING
    return logging.INFO


def _format_summary(summary: ImportSummary, database: Path) -> str:
    """Describe the outcome of an import in one line.

    Args:
        summary: Counts of what happened to the rows.
        database: The JSON database that was updated.

    Returns:
        A human-readable summary.
    """
    return (
        f"Imported {summary.imported} user(s) into {database}; "
        f"skipped {summary.invalid} invalid and {summary.duplicates} duplicate row(s)."
    )
