#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Run both public meaningful demonstrations."""

from pathlib import Path
from sys import path as import_path

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.packages.meaningful.examples.api.run import ApiExample
from exactus.packages.meaningful.examples.cli.run import CliExample


def main() -> int:
    """Execute the API example followed by the CLI example.

    Returns:
        The CLI example process status.

    """
    ApiExample.run()
    return CliExample.run()


if __name__ == "__main__":
    raise SystemExit(main())
