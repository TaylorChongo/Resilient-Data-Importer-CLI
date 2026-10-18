"""Allow the importer to be run with ``python -m importer``.

Python executes this file only when the package is run as a program, so it
does not need an ``if __name__ == "__main__"`` guard.
"""

import sys

from importer.cli import main

sys.exit(main())
