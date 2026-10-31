#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Run ``exactus.packages.performance`` through the project's virtualenv."""

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from sys import argv, path
from typing import cast

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
main: Callable[..., int] = cast(
    typ="Callable[..., int]",
    val=import_module(
        name="exactus.packages.performance.cli",
    ).PerformanceCli.run,
)
raise SystemExit(main(arguments=tuple(argv[1:])))
