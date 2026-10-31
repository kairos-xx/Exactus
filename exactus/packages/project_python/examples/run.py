#!/usr/bin/env python3
# Copyright (c) 2026
"""Re-execute a repository script under the project virtual environment.

Copy this pattern into a tool's ``__main__.py``: resolve the repository
root, call ``switch_to_project_venv()``, then hand off to the real entry
point. When ``.venv`` exists the process is replaced in place — every
argument is preserved — and the second pass simply returns because the
project interpreter is already active.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from sys import path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType
file_path: Path = Path(__file__).resolve()
path.insert(0, str(object=file_path.parent.parent.parent))
path.insert(0, str(object=file_path.parent.parent.parent.parent.parent))


class _BuildConstants(Protocol):
    """Mutable path attributes exposed by ``package.build.Constants``.

    Attributes:
        check: Executable path the build writes.
        dist: Distribution directory the build populates.
        tree: Manifest file the build refreshes.

    """

    check: Path
    dist: Path
    tree: Path


def main() -> int:
    """Re-exec under ``.venv`` when needed, then run the tool.

    Returns:
        Process exit status.

    """
    switch: Callable[[], None] = import_module(
        name="exactus.packages.project_python",
    ).switch_to_project_venv
    switch()
    build: ModuleType = import_module(name="exactus.packages.package.build")
    tool: Callable[[], int] = build.main
    constants: _BuildConstants | None = getattr(build, "Constants", None)
    if constants is None:
        return tool()
    previous: dict[str, Path] = {
        "check": constants.check,
        "dist": constants.dist,
        "tree": constants.tree,
    }
    with TemporaryDirectory(
        prefix="project-python-example-",
        ignore_cleanup_errors=True,
    ) as scratch:
        scratch_path: Path = Path(scratch)
        constants.check = scratch_path / "bin" / "exactus"
        constants.dist = scratch_path / "build"
        constants.tree = scratch_path / "TREE.txt"
        try:
            return tool()
        finally:
            constants.check = previous["check"]
            constants.dist = previous["dist"]
            constants.tree = previous["tree"]


if __name__ == "__main__":
    raise SystemExit(main())
