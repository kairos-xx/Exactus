# Copyright (c) 2026 João Lopes.
"""Unified browser lifecycle monitoring."""

from pathlib import Path
from sys import path as import_paths

import_paths.append(str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.browser.lifecycle import (
    BrowserBackend,
    BrowserEvent,
    BrowserEventType,
    BrowserLifecycle,
    ChromeLocator,
    PageState,
)

__all__: tuple[str, ...] = (
    "BrowserBackend",
    "BrowserEvent",
    "BrowserEventType",
    "BrowserLifecycle",
    "ChromeLocator",
    "PageState",
)
