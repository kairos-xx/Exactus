# Copyright (c) 2026
"""Dispatch ``python -m exactus.bundle`` to the host platform bundle."""
from __future__ import annotations

from pathlib import Path
from subprocess import run
from sys import argv, executable
from sys import path as sys_path

if __package__ in (None, ""):
    sys_path.insert(
        0,
        str(object=Path(__file__).resolve().parents[2]),
    )
from exactus.bundle import host_leaf


def main() -> int:
    """Run the host platform bundle dispatcher.

    Returns:
        Process status forwarded from the selected bundle; ``1`` when
        no bundle exists for this host.

    """
    leaf: Path | None = host_leaf()
    if leaf is None or not (leaf / "__main__.py").is_file():
        return 1
    return run(
        args=[executable, str(object=leaf), *argv[1:]],
        check=False,
    ).returncode
if __name__ == "__main__":
    raise SystemExit(main())
