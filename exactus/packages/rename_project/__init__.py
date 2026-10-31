# Copyright (c) 2026
"""Rename a project: root directory, files, and its name inside text."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from sys import path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .rename_project import main
__all__: list[str] = ["main"]


def __getattr__(name: str) -> Callable[..., int]:
    """Load the CLI entry point only when a caller requests it.

    Args:
        name: Exported attribute name.

    Returns:
        The ``main`` callable.

    Raises:
        AttributeError: When the name is not exported.

    """
    if name == "main":
        directory: Path = Path(__file__).resolve().parent
        for extra in (directory, directory.parent.parent.parent):
            location: str = str(object=extra)
            if location not in path:
                path.insert(0, location)
        return import_module(name=".rename_project", package=__name__).main
    msg: str = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
