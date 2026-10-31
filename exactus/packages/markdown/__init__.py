# Copyright (c) 2026
"""Render Markdown reports from JSON through templates and mappings."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from .errors import MappingError, TemplateEngineError

if TYPE_CHECKING:
    from collections.abc import Callable

    from .api import render_report
    from .engine import MarkdownEngine
__all__: list[str] = [
    "MappingError",
    "MarkdownEngine",
    "TemplateEngineError",
    "render_report",
]


def __getattr__(name: str) -> type[MarkdownEngine] | Callable[..., str]:
    """Load the Jinja-backed API only when a caller requests it.

    Args:
        name: Exported attribute name.

    Returns:
        The engine class or report entry point.

    Raises:
        AttributeError: When the name is not exported.

    """
    if name == "MarkdownEngine":
        return import_module(name=".engine", package=__name__).MarkdownEngine
    if name == "render_report":
        return import_module(name=".api", package=__name__).render_report
    msg: str = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
