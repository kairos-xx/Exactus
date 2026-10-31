#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Demonstrate source-bundle creation on a temporary archive."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from tempfile import TemporaryDirectory

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.zip_components.core import BundleResult, create_bundle


def main() -> int:
    """Bundle ``exactus.packages.steps`` into scratch space and report it.

    Returns:
        ``0`` when the archive was written.

    """
    root: Path = Path(__file__).resolve().parents[4]
    with TemporaryDirectory() as scratch:
        result: BundleResult = create_bundle(
            root=root,
            packages=("steps",),
            output=Path(scratch) / "packages_steps.zip",
        )
        discovered: str = (
            ", ".join(
                f"exactus.packages.{name}"
                for name in result.selection.packages
                if name != "steps"
            )
            or "none"
        )
        _written: int = stdout.write(
            f"Bundle: {result.path.name}\n"
            f"Files: {len(result.files)}\n"
            f"Discovered dependencies: {discovered}\n"
            f"First members: {', '.join(result.files[:5])}\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
