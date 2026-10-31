# Copyright (c) 2026
"""Standard-error capture: ``stderr.log`` transcripts with line counts.

``stderr.log`` keeps the raw bytes a run wrote to standard error;
``StderrRecorder`` counts the captured lines and classifies each as
error, warning or info. ``StderrMirror`` records a Python process's
``sys.stderr`` into ``stderr.log`` while still forwarding it.
"""

from __future__ import annotations

from io import RawIOBase, TextIOWrapper
from os import getpid
from re import IGNORECASE, Pattern
from re import compile as compile_pattern
from sys import modules
from threading import RLock
from typing import TYPE_CHECKING, BinaryIO, Final, Self, TextIO, cast, override

if TYPE_CHECKING:
    from collections.abc import Buffer
    from pathlib import Path
    from types import TracebackType


class StderrTables:
    """Constants of the ``stderr.log`` contract.

    Attributes:
        log_name: Raw transcript file name.
        line_chars: Characters of a pending line kept for
            classification.
        char_bytes: Bytes per kept character buffered for a pending
            line; a line longer than ``line_chars * char_bytes`` bytes
            is classified from its prefix and its remaining bytes are
            skipped.
        error: Pattern marking a line as an error.
        warning: Pattern marking a line as a warning.

    """

    log_name: Final[str] = "stderr.log"
    line_chars: Final[int] = 2000
    char_bytes: Final[int] = 4
    error: Final[Pattern[str]] = compile_pattern(
        pattern=r"\b(error|exception|traceback|fatal|critical)\b",
        flags=IGNORECASE,
    )
    warning: Final[Pattern[str]] = compile_pattern(
        pattern=r"\b(warn|warning|warnings|deprecated|deprecation)\b",
        flags=IGNORECASE,
    )

    @classmethod
    def level(cls: type[Self], *, text: str) -> str:
        """Classify one line of standard error.

        Args:
            text: Line text without its newline.

        Returns:
            ``error``, ``warning`` or ``info``.

        """
        if cls.error.search(string=text):
            return "error"
        if cls.warning.search(string=text):
            return "warning"
        return "info"


class StderrRecorder:
    """Count stream bytes and classify each completed line."""

    def __init__(
        self: Self,
        *,
        line_chars: int = StderrTables.line_chars,
    ) -> None:
        """Start an empty recording.

        Args:
            line_chars: Characters of a pending line kept for
                classification.

        """
        self.line_chars: int = line_chars
        self.bytes: int = 0
        self.lines: int = 0
        self.levels: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
        self._partial: bytearray = bytearray()
        self._partial_limit: int = line_chars * StderrTables.char_bytes
        self._overflow: bool = False
        self._lock: RLock = RLock()

    def feed(self: Self, *, chunk: bytes) -> None:
        """Consume one chunk of the stream.

        Args:
            chunk: Bytes in arrival order.

        """
        with self._lock:
            self.bytes += len(chunk)
            rest: bytes = chunk
            while rest:
                line: bytes
                newline: bytes
                line, newline, rest = rest.partition(b"\n")
                if not self._overflow:
                    room: int = self._partial_limit - len(self._partial)
                    self._partial.extend(line[:room])
                    if len(line) > room:
                        self._close_line(raw=bytes(self._partial))
                        self._partial.clear()
                        self._overflow = True
                if not newline:
                    break
                if self._overflow:
                    self._overflow = False
                    continue
                self._close_line(raw=bytes(self._partial))
                self._partial.clear()

    def finish(self: Self) -> None:
        """Classify a trailing line that has no newline."""
        with self._lock:
            self._overflow = False
            if self._partial:
                self._close_line(raw=bytes(self._partial))
                self._partial.clear()

    def _close_line(self: Self, *, raw: bytes) -> None:
        """Classify one complete line.

        Args:
            raw: Line bytes without the newline.

        """
        text: str = raw.decode(encoding="utf-8", errors="replace").rstrip("\r")
        self.lines += 1
        self.levels[StderrTables.level(text=text)] += 1


def current_stderr() -> TextIO:
    """Return the interpreter's current ``sys.stderr`` stream.

    Returns:
        The stream bound to ``sys.stderr`` right now.

    """
    return cast(typ="TextIO", val=vars(modules["sys"])["stderr"])


def _bind_stderr(*, stream: TextIO) -> None:
    """Rebind the interpreter's ``sys.stderr``.

    Args:
        stream: Stream that ``sys.stderr`` names from now on.

    """
    vars(modules["sys"])["stderr"] = stream


class _MirrorRaw(RawIOBase):
    """Raw byte sink forwarding to a text stream and recording a copy."""

    def __init__(
        self: Self,
        *,
        target: TextIO,
        log: BinaryIO,
        recorder: StderrRecorder,
    ) -> None:
        """Bind the forwarding target and the recording sinks.

        Args:
            target: Stream that keeps receiving every write.
            log: Raw transcript file.
            recorder: Line recorder fed with every write.

        """
        super().__init__()
        self._target: TextIO = target
        self._log: BinaryIO | None = log
        self._recorder: StderrRecorder = recorder
        self._owner: int = getpid()
        self._lock: RLock = RLock()

    @property
    def name(self: Self) -> str:
        """Name the sink like the stream it forwards to.

        Returns:
            A descriptive pseudo file name.

        """
        return "<stderr mirror>"

    @override
    def writable(self: Self) -> bool:
        """Accept writes.

        Returns:
            Always ``True``.

        """
        return True

    @override
    def isatty(self: Self) -> bool:
        """Report the forwarding target's terminal status.

        Returns:
            Whether the target is a terminal.

        """
        return self._target.isatty()

    @override
    def write(self: Self, b: Buffer, /) -> int:
        """Forward one write and record it in the owning process.

        Args:
            b: Bytes written to the text layer.

        Returns:
            Number of bytes consumed.

        """
        data: bytes = bytes(b)
        _ = self._target.write(data.decode(encoding="utf-8", errors="replace"))
        self._target.flush()
        with self._lock:
            if self._log is not None and getpid() == self._owner:
                _ = self._log.write(data)
                self._log.flush()
                self._recorder.feed(chunk=data)
        return len(data)

    def detach_log(self: Self) -> None:
        """Stop recording; later writes are only forwarded."""
        with self._lock:
            if self._log is not None:
                self._log.close()
            self._log = None


class StderrMirror:
    """Record ``sys.stderr`` into a directory while forwarding it.

    Only Python-level writes through ``sys.stderr`` are seen (warnings,
    logging's last-resort handler, tracebacks of threads); descriptor
    ``2`` is left untouched, so child processes and terminals behave as
    before. Writes from forked children are forwarded but not recorded.
    """

    def __init__(self: Self, *, directory: Path) -> None:
        """Choose where ``stderr.log`` lands.

        Args:
            directory: Directory receiving the transcript.

        """
        self.directory: Path = directory
        self.recorder: StderrRecorder = StderrRecorder()
        self._raw: _MirrorRaw | None = None
        self._previous: TextIO | None = None

    def __enter__(self: Self) -> Self:
        """Start recording.

        Returns:
            This mirror.

        """
        self.directory.mkdir(parents=True, exist_ok=True)
        self._previous = current_stderr()
        self._raw = _MirrorRaw(
            target=self._previous,
            log=(self.directory / StderrTables.log_name).open(mode="wb"),
            recorder=self.recorder,
        )
        _bind_stderr(
            stream=TextIOWrapper(
                buffer=self._raw,
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
                write_through=True,
            ),
        )
        return self

    def __exit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore ``sys.stderr`` and close the transcript.

        Args:
            exc_type: Exception type leaving the block, if any.
            exc_value: Exception leaving the block, if any.
            traceback: Traceback of that exception, if any.

        """
        del exc_type, exc_value, traceback
        current_stderr().flush()
        if self._previous is not None:
            _bind_stderr(stream=self._previous)
        if self._raw is not None:
            self._raw.detach_log()
        self.recorder.finish()
