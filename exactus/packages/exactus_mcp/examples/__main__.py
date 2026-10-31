# Copyright (c) 2026
"""Run the Exactus MCP example through the project virtual environment."""

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from sys import path
from typing import cast

file_path: Path = Path(__file__).resolve()
path.insert(0, str(object=file_path.parent.parent.parent))
path.insert(0, str(object=file_path.parent.parent.parent.parent.parent))
switch: Callable[[], None] | None = None
candidate: str
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
    val=import_module(name="exactus.packages.exactus_mcp.examples.run").main,
)
raise SystemExit(main())
