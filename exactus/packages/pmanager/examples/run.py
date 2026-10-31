#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Run the comprehensive pmanager API example directly or as a package."""

from __future__ import annotations

from pathlib import Path
from sys import path

if __package__ in {None, ""}:
    path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.packages.pmanager.examples.api.run import main

if __name__ == "__main__":
    raise SystemExit(main())
