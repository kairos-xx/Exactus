#!/usr/bin/env python3
# Copyright (c) 2026
"""Run the portable Zstandard round-trip example."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.zstd_portable.examples.example import main as run_example


def main() -> int:
    """Execute the example and return a successful process status.

    Returns:
        Zero after the round-trip completes.

    """
    run_example()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
