#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""JSON-specification pmanager CLI example launcher."""

from __future__ import annotations

from pathlib import Path
from sys import path
from typing import Final, final

if __package__ in {None, ""}:
    path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from subprocess import CompletedProcess, run
from sys import executable, stdout


@final
class Constants:
    """Group module-level constants.

    Attributes:
        spec: Grouped module constant.

    """

    spec: Final[Path] = Path(__file__).with_name(name="processes.json")


def main() -> int:
    """Load a JSON process specification through representative CLI calls.

    Returns:
        First failing command exit code or zero.

    """
    spec: Path = Constants.spec
    stdout.write(f"spec: {spec}\n")
    stdout.flush()
    commands: tuple[tuple[str, ...], ...] = (
        (
            executable,
            "-m",
            "exactus.packages.pmanager",
            "--validate",
            "--spec",
            str(object=spec),
        ),
        (
            executable,
            "-m",
            "exactus.packages.pmanager",
            "--status",
            "--spec",
            str(object=spec),
        ),
        (
            executable,
            "-m",
            "exactus.packages.pmanager",
            "--tree",
            "--spec",
            str(object=spec),
        ),
    )
    for command in commands:
        stdout.write("$ " + " ".join(command) + "\n")
        stdout.flush()
        completed: CompletedProcess[bytes] = run(check=False, args=command)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
