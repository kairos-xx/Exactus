"""Run the project-python example with the project virtual environment."""

from collections.abc import Callable
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from sys import path
from typing import cast

file_path: Path = Path(__file__).resolve()
if find_spec(name="exactus") is None:
    path.insert(0, str(object=file_path.parents[4]))
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
main: Callable[[], int] = cast(
    typ="Callable[[], int]",
    val=import_module(
        name="exactus.packages.project_python.examples.run",
    ).main,
)
raise SystemExit(main())
