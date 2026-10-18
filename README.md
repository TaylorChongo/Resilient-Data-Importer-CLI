# Resilient Data Importer CLI

A command-line tool that imports user records from a CSV file into a JSON
database. It is built to keep working when the input is messy: missing files,
broken headers, malformed rows and duplicate users are all reported clearly
instead of crashing the program or corrupting the data.

```text
$ importer sample_data/mixed_users.csv
INFO: Importing users from sample_data/mixed_users.csv
WARNING: Skipped invalid row 3: name is required
WARNING: Skipped invalid row 4: invalid email 'donald.example.com'
WARNING: Skipped invalid row 5: invalid user_id '20 04' (use only letters, digits, '-' and '_')
WARNING: Skipped invalid row 6: email is required
WARNING: Skipped invalid row 7: unexpected extra value(s): extra
WARNING: Skipped row 8: user ID '2001' already exists
INFO: Rows processed: 9 (imported: 3, invalid: 5, duplicates: 1)
Imported 3 user(s) into users.json; skipped 5 invalid and 1 duplicate row(s).
```

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
- [Input and output formats](#input-and-output-formats)
- [How errors are handled](#how-errors-are-handled)
- [Project structure](#project-structure)
- [Design](#design)
- [Testing and coverage](#testing-and-coverage)
- [Code quality](#code-quality)
- [Git workflow](#git-workflow)
- [Demo walkthrough](#demo-walkthrough)

## Features

- **Resilient import**: invalid rows and duplicate users are skipped and
  reported; the rest of the file is still imported.
- **All-or-nothing saves**: if the file itself is unusable, nothing is saved.
  The database is written atomically, so a crash can never leave it
  half-written.
- **Clear validation messages** that name the row and list every problem in it.
- **Structured logging** to the terminal, and optionally to a timestamped log
  file.
- **Meaningful exit codes** for use in scripts and pipelines.
- **No runtime dependencies**: only the Python standard library.

## Requirements

- Python 3.11 or newer
- Git

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/TaylorChongo/Resilient-Data-Importer-CLI.git
   cd Resilient-Data-Importer-CLI
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   ```

   | Shell            | Activation command              |
   | ---------------- | ------------------------------- |
   | PowerShell       | `.venv\Scripts\Activate.ps1`    |
   | Git Bash         | `source .venv/Scripts/activate` |
   | macOS / Linux    | `source .venv/bin/activate`     |

3. **Install the development tools and the importer itself**

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

   `pip install -e .` installs the package in editable mode and creates the
   `importer` command.

4. **Enable the pre-commit hooks** (for contributors)

   ```bash
   pre-commit install
   ```

## Usage

```text
importer [-h] [--db DB] [--log-file LOG_FILE] [-v | -q] csv_file
```

| Argument             | Description                                            |
| -------------------- | ------------------------------------------------------ |
| `csv_file`           | CSV file to import (required)                          |
| `--db DB`            | JSON database to update (default: `users.json`)        |
| `--log-file FILE`    | Also write detailed, timestamped logs to this file     |
| `-v`, `--verbose`    | Show every imported row                                |
| `-q`, `--quiet`      | Show only warnings and errors                          |
| `-h`, `--help`       | Show help and exit                                     |

`python -m importer` works exactly like `importer`.

### Examples

```bash
# Import into users.json in the current folder
importer sample_data/valid_users.csv

# Use a different database and keep a log file
importer sample_data/new_users.csv --db team_users.json --log-file import.log

# Show every row that was imported
importer sample_data/valid_users.csv --verbose
```

### Exit codes

| Code | Meaning                                                              |
| ---- | -------------------------------------------------------------------- |
| `0`  | Import finished (bad rows may have been skipped; see the warnings)   |
| `1`  | Import aborted: missing or unreadable CSV, wrong headers, broken database, or unusable log file |
| `2`  | Invalid command-line arguments                                       |

### Output streams

Log messages are written to **stderr** and the one-line result summary to
**stdout**, so `importer users.csv > result.txt` saves only the summary while
warnings still appear on screen.

## Input and output formats

### CSV input

The first line must be a header with the columns `user_id`, `name` and
`email`, in any order:

```csv
user_id,name,email
1001,Ada Lovelace,ada@example.com
1002,"Turing, Alan",alan@example.com
```

- Column names are case-insensitive and may have surrounding spaces.
- Extra columns are ignored with a warning.
- Values may be quoted, so they can contain commas.
- Blank lines are skipped.
- The file must be UTF-8 encoded (the BOM that Excel adds is handled).

### Validation rules

| Field     | Rule                                                     |
| --------- | -------------------------------------------------------- |
| `user_id` | Required; letters, digits, `-` and `_` only; must be unique |
| `name`    | Required                                                 |
| `email`   | Required; must look like `name@domain.tld`               |

Surrounding whitespace is removed from every value. A row with more values
than there are columns is rejected.

### JSON database

The database is a JSON list of users, created on first use:

```json
[
  {
    "user_id": "1001",
    "name": "Ada Lovelace",
    "email": "ada@example.com"
  }
]
```

### Log file

With `--log-file`, each line has a timestamp, level, module and message:

```text
2026-10-18 15:42:07 | INFO     | importer.service | Importing users from users.csv
2026-10-18 15:42:07 | WARNING  | importer.service | Skipped invalid row 3: name is required
```

## How errors are handled

All expected errors inherit from one base class, `ImporterError`, so the CLI
can catch them in one place and show a clean message instead of a traceback.

```text
ImporterError
├── MissingFileError     the CSV file does not exist
├── FileFormatError      the CSV is empty, unreadable or lacks a required column
├── ValidationError      a row contains invalid data
├── DuplicateUserError   a user ID already exists
└── StorageError         the JSON database cannot be read or written
```

| Problem                         | Scope         | Result                               |
| ------------------------------- | ------------- | ------------------------------------ |
| Invalid row                     | one row       | row skipped, warning logged          |
| Duplicate user ID               | one row       | row skipped, warning logged          |
| Missing / empty / unreadable CSV | whole file   | import aborted, nothing saved        |
| Wrong headers                   | whole file    | import aborted, nothing saved        |
| Corrupted database              | whole import  | import aborted, database untouched   |
| Failure while saving            | whole import  | original database kept intact        |

## Project structure

```text
├── src/importer/
│   ├── __main__.py         # enables `python -m importer`
│   ├── cli.py              # argument parsing, exit codes, wiring
│   ├── logging_config.py   # console and log file formats
│   ├── service.py          # UserImporter: runs the import, builds the summary
│   ├── parser.py           # CsvUserParser: reads rows and checks headers
│   ├── validator.py        # UserValidator: turns rows into users
│   ├── repository.py       # JsonUserRepository: loads and saves users
│   ├── models.py           # User dataclass
│   └── exceptions.py       # custom exception hierarchy
├── tests/                  # one test module per source module
├── sample_data/            # example CSV files for trying the tool
├── reports/coverage.txt    # latest test coverage report
├── pyproject.toml          # package metadata and tool configuration
├── requirements.txt        # pinned development dependencies
└── .pre-commit-config.yaml # checks run before every commit
```

## Design

Each component has one responsibility, and the service depends only on
interfaces (`typing.Protocol`), not on concrete classes:

```text
                 ┌──────────────┐
  CSV file ────► │ CsvUserParser│──RawRow──┐
                 └──────────────┘          ▼
                                   ┌───────────────┐   User    ┌────────────────────┐
     cli.main ──creates──────────► │ UserImporter  │─────────► │ JsonUserRepository │──► users.json
                                   └───────────────┘           └────────────────────┘
                                           ▲
                 ┌──────────────┐          │
                 │ UserValidator│──User────┘
                 └──────────────┘
```

- **Single responsibility**: reading, validating, storing and coordinating
  live in separate classes, so each changes for only one reason.
- **Dependency inversion**: `UserImporter` receives its parser, validator and
  repository through its constructor. Tests pass in mocks; another storage
  (for example SQLite) could be added without changing the service.
- **Repository pattern**: only `JsonUserRepository` knows that users are
  stored as JSON.
- **Context managers**: `open_csv` guarantees the input file is closed, and
  `atomic_write` guarantees the database is either fully updated or left
  unchanged.

## Testing and coverage

```bash
# Run all tests
pytest

# Run tests with a coverage report (fails below 90%)
pytest --cov

# Create a browsable HTML report in htmlcov/
pytest --cov --cov-report=html
```

The suite has 105 tests with **100% line and branch coverage**; see
[`reports/coverage.txt`](reports/coverage.txt). It includes:

- **Unit tests** for each component, using `tmp_path` for real temporary
  files and `pytest-mock` to simulate failures such as a full disk.
- **Parametrized tests** for valid and invalid CSV content, rows and emails.
- **Service tests** that replace the parser, validator and repository with
  autospecced mocks.
- **End-to-end tests** that run the CLI with real files and check exit codes,
  terminal output and the resulting database.

## Code quality

| Tool                                       | Purpose                               |
| ------------------------------------------ | ------------------------------------- |
| [Black](https://black.readthedocs.io/)     | PEP 8 formatting                      |
| [Ruff](https://docs.astral.sh/ruff/)       | Linting: bugs, naming, imports        |
| [mypy](https://mypy.readthedocs.io/) (strict) | Static type checking               |
| [pre-commit](https://pre-commit.com/)      | Runs all of the above before each commit |

Run every check manually with:

```bash
pre-commit run --all-files
```

All modules, classes and public functions have Google-style docstrings.

## Git workflow

The project follows **Git Flow**:

- `main` holds released versions only, each tagged (for example `v1.0.0`).
- `develop` collects finished features.
- `feature/*` branches are created from `develop` and merged back through
  pull requests, then deleted.
- `release/*` branches prepare a release and are merged into `main`.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `test:`, `docs:`, `build:`, `chore:`).

## Demo walkthrough

Run these from an empty folder (or delete `users.json` first) to see every
behaviour:

| Command                                         | What it shows                               |
| ----------------------------------------------- | ------------------------------------------- |
| `importer sample_data/valid_users.csv`          | Clean import of 5 users                      |
| `importer sample_data/new_users.csv`            | 2 new users, 2 duplicates of existing users |
| `importer sample_data/mixed_users.csv`          | Every kind of invalid row, plus a duplicate |
| `importer sample_data/wrong_headers.csv`        | Import aborted: missing columns             |
| `importer sample_data/empty.csv`                | Import aborted: empty file                  |
| `importer missing.csv`                          | Import aborted: file not found              |
| `importer sample_data/valid_users.csv -v --log-file import.log` | Verbose output and a log file |
