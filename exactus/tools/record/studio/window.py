# Copyright (c) 2026 Project contributors
"""Resolve the Studio browser-window setting from CLI and pyproject."""

from __future__ import annotations

from argparse import ArgumentParser, BooleanOptionalAction
from typing import TYPE_CHECKING

from exactus.tools.common.config import (
    ConfigError,
    discovery_from_environment,
    stacked,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.config import ConfigFile
    from exactus.tools.common.json_types import JsonValue


def add_window_argument(*, parser: ArgumentParser) -> None:
    """Register ``--window`` / ``--no-window`` on a Studio parser.

    The default is ``None`` so an absent flag defers to ``pyproject.toml``.

    Args:
        parser: Parser receiving the option.

    """
    _ = parser.add_argument(
        "--window",
        action=BooleanOptionalAction,
        default=None,
        help=(
            "Open the managed browser window with Studio and stop Studio "
            "when that window is closed (default: [tool.exactus.record] "
            "window, else false)."
        ),
    )


def resolve_window(*, flag: bool | None, start: Path) -> bool:
    """Combine the CLI flag with ``[tool.exactus.record] window``.

    Args:
        flag: Parsed ``--window`` value, or None when not given.
        start: Directory where pyproject discovery begins.

    Returns:
        Whether Studio is bound to the lifetime of a browser window.

    """
    if flag is not None:
        return flag
    try:
        files: tuple[ConfigFile, ...] = discovery_from_environment(start=start)
    except ConfigError:
        return False
    configured: JsonValue | None = stacked(files=files, path=("record",)).get(
        "window",
    )
    return configured is True
