# Copyright (c) 2026
"""Run a script under the project virtual environment.

``python -m exactus.packages.project_python <script> [args...]`` replaces the
interpreter with the repository ``.venv`` when it exists, then executes the
script as ``__main__`` with the remaining arguments.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from runpy import run_path
from sys import argv, path, stderr
from textwrap import dedent
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable
file_path: Path = Path(__file__).resolve()
path.insert(0, str(object=file_path.parent.parent))
path.insert(0, str(object=file_path.parent.parent.parent.parent))
switch: Callable[[], None] | None = None
for candidate in ("exactus.packages.project_python", "project_python"):
    try:
        switch = cast(
            typ="Callable[[], None]",
            val=import_module(name=candidate).switch_to_project_venv,
        )
        break
    except ImportError:
        continue
if switch is not None:
    switch()


def main() -> int:
    """Run ``argv[1]`` as ``__main__`` under the project interpreter.

    Returns:
        ``0`` when the script completes, ``2`` for usage errors.

    """
    _, *arguments = argv
    if not arguments or not Path(arguments[0]).is_file():
        stderr.write(
            dedent(
                text=(
                    "    usage: python -m exactus.packages.project_python "
                    "<script> [args...]\n    "
                ),
            ),
        )
        return 2
    argv[:] = arguments
    run_path(path_name=argv[0], run_name="__main__")
    return 0


raise SystemExit(main())
