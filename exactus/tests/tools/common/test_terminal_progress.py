# Copyright (c) 2026
"""Determinate and indeterminate terminal progress rendering."""

from __future__ import annotations

from io import StringIO

import pytest

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.common.terminal_progress import (
    ProgressMode,
    Settings,
    TerminalProgress,
)


def _fast() -> Settings:
    """Return animation settings that converge immediately.

    Returns:
        Settings with instant smoothing and a high frame rate.

    """
    return Settings(fps=60.0, smoothing_seconds=0.01)


def test_width_expressions_and_rejections() -> None:
    """Responsive width expressions parse; malformed ones raise."""
    stream: StringIO = StringIO()
    for width in ("100%", "80%-5", "100 %-4"):
        progress: TerminalProgress = TerminalProgress(
            width=width,
            stream=stream,
            settings=_fast(),
        )
        progress.close()
    for invalid in (0, "junk", "abc%", "0%", "150%", "50%--3"):
        with pytest.raises(expected_exception=ValueError, match=r"\S+"):
            _ = TerminalProgress(
                width=invalid,
                stream=stream,
                settings=_fast(),
            )


def test_settings_validation() -> None:
    """Non-positive animation settings raise ``ValueError``."""
    stream: StringIO = StringIO()
    for settings in (
        Settings(fps=0.0),
        Settings(smoothing_seconds=0.0),
        Settings(min=0.0),
        Settings(pulse_width=0),
    ):
        with pytest.raises(expected_exception=ValueError, match=r"\S+"):
            _ = TerminalProgress(width=4, stream=stream, settings=settings)


def test_determinate_lifecycle() -> None:
    """Determinate progress animates, restarts, and finishes cleanly."""
    stream: StringIO = StringIO()
    progress: TerminalProgress = TerminalProgress(
        width=10,
        label="Job",
        settings=_fast(),
        stream=stream,
    )
    expect_equal(actual=progress.progress, expected=0.0)
    expect_equal(actual=progress.mode, expected=ProgressMode.DETERMINATE)
    _ = progress.start()
    _ = progress.start()
    _ = progress.set_progress(value=1.5, message="clamped")
    expect_equal(actual=progress.progress, expected=1.0)
    _ = progress.set_percent(percent=50)
    expect_equal(actual=progress.progress, expected=0.5)
    progress.finish(message="done")
    progress.close()
    rendered: str = stream.getvalue()
    expect_in(member="\x1b[?25l", container=rendered)
    expect_in(member="\x1b[?25h", container=rendered)
    expect_in(member="Job", container=rendered)
    with pytest.raises(expected_exception=RuntimeError):
        progress.start()


def test_indeterminate_mode_and_auto_start() -> None:
    """Indeterminate mode auto-starts and switches modes freely."""
    stream: StringIO = StringIO()
    progress: TerminalProgress = TerminalProgress(
        width="100%",
        settings=_fast(),
        stream=stream,
    )
    _ = progress.set_indeterminate(message="working")
    expect_equal(actual=progress.mode, expected=ProgressMode.INDETERMINATE)
    _ = progress.set_message(message="still working")
    _ = progress.start(indeterminate=True)
    progress.close()
    expect_in(member="--.--%", container=stream.getvalue())


def test_context_manager_closes() -> None:
    """Entering starts rendering; leaving closes and restores the cursor."""
    stream: StringIO = StringIO()
    with TerminalProgress(
        width=4,
        stream=stream,
        settings=_fast(),
    ) as progress:
        expect_equal(actual=progress.mode, expected=ProgressMode.DETERMINATE)
        _ = progress.set_progress(value=0.25)
    expect_in(member="\x1b[?25h", container=stream.getvalue())
