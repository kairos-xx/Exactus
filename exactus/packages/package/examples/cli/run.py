#!/usr/bin/env python3
"""Complete CLI example."""

from pathlib import Path
from sys import path as sys_path

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from exactus.packages.package.cli import main


def run_example() -> int:
    """Run all stages through the same CLI parser used by users.

    Returns:
        Exit status code.

    """
    return main(
        arguments=(
            "--build",
            "--bundle",
            "--package",
            "--bundle-target",
            "linux-glibc-amd64",
        ),
    )


if __name__ == "__main__":
    raise SystemExit(run_example())
