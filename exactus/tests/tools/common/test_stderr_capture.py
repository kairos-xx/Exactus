# Copyright (c) 2026
"""Standard-error capture: line counts, levels and the mirror."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, TextIO, cast

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    private,
    require_type,
)
from exactus.tools.common.stderr_capture import (
    StderrMirror,
    StderrRecorder,
    StderrTables,
    current_stderr,
)

if TYPE_CHECKING:
    from pathlib import Path
    from threading import RLock

    import pytest


def test_recorder_splits_chunks_into_lines() -> None:
    """Lines spanning chunks are counted once and classified."""
    recorder: StderrRecorder = StderrRecorder()
    recorder.feed(chunk=b"Warning: slow\r\nhal")
    recorder.feed(chunk=b"f line\nTraceback (most")
    recorder.feed(chunk=b" recent call last):")
    recorder.finish()
    expect_equal(actual=recorder.lines, expected=3)
    expect_equal(actual=recorder.bytes, expected=59)
    expect_equal(
        actual=recorder.levels,
        expected={"error": 1, "warning": 1, "info": 1},
    )


def test_pending_line_buffer_is_capped() -> None:
    """A newline-free flood is classified once from its bounded prefix."""
    recorder: StderrRecorder = StderrRecorder(line_chars=5)
    limit: int = 5 * StderrTables.char_bytes
    recorder.feed(chunk=b"x" * (limit * 3))
    expect_equal(
        actual=len(
            require_type(
                value=private(owner=recorder, name="_partial"),
                kind=bytearray,
            ),
        ),
        expected=0,
    )
    recorder.feed(chunk=b"y" * limit + b"\nnext\ntail")
    recorder.finish()
    expect_equal(actual=recorder.lines, expected=3)
    expect_equal(
        actual=recorder.levels,
        expected={"error": 0, "warning": 0, "info": 3},
    )


def test_recorder_lock_is_reentrant() -> None:
    """A signal handler may record while the main thread holds the lock."""
    recorder: StderrRecorder = StderrRecorder()
    lock: RLock = cast(typ="RLock", val=private(owner=recorder, name="_lock"))
    with lock:
        expect_true(
            condition=lock.acquire(blocking=False),
            message="the recorder lock must be reentrant",
        )
        lock.release()
        recorder.feed(chunk=b"inside\n")
        recorder.finish()
        expect_equal(actual=recorder.lines, expected=1)


def test_mirror_records_and_forwards_sys_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror records writes while the original stream still gets them.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    terminal: StringIO = StringIO()
    monkeypatch.setattr(target="sys.stderr", name=terminal)
    with StderrMirror(directory=tmp_path / "ARTIFACTS") as mirror:
        late: TextIO = current_stderr()
        expect_false(condition=late is terminal)
        _ = late.write("warning: first\n")
        _ = late.write("second")
    expect_true(condition=current_stderr() is terminal)
    _ = late.write("after exit\n")
    expect_equal(actual=mirror.recorder.lines, expected=2)
    expect_equal(
        actual=mirror.recorder.levels,
        expected={"error": 0, "warning": 1, "info": 1},
    )
    expect_equal(
        actual=(tmp_path / "ARTIFACTS" / "stderr.log").read_text(),
        expected="warning: first\nsecond",
    )
    expect_false(condition=(tmp_path / "ARTIFACTS" / "stderr.json").exists())
    expect_equal(
        actual=terminal.getvalue(),
        expected="warning: first\nsecondafter exit\n",
    )
