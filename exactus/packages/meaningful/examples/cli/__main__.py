# Copyright (c) 2026 João Lopes.
"""Execute the meaningful CLI example package."""

from pathlib import Path
from sys import path as import_path

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from exactus.packages.meaningful.examples.cli.run import CliExample

raise SystemExit(CliExample.run())
