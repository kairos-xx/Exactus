# Copyright (c) 2026 João Lopes.
"""Bundled-toolchain inventory and dispatch for ``exactus --external``."""

from pathlib import Path
from sys import path as import_paths

import_paths.append(str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.external.cli import inventory_text, main, run

__all__: tuple[str, ...] = ("inventory_text", "main", "run")
