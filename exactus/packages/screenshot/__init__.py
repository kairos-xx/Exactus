# Copyright (c) 2026
"""Capture script package.

Provide screenshot acquisition and image similarity comparison.
Browser recording, discovery, and execution live in ``exactus.tools.record``.
"""

from .capture_screen import (
    Capture,
    CaptureScreenDefaults,
    CaptureSpec,
    Js,
    Screenshot,
    SnapshotCapture,
)

__all__: list[str] = [
    "Capture",
    "CaptureScreenDefaults",
    "CaptureSpec",
    "Js",
    "Screenshot",
    "SnapshotCapture",
]
