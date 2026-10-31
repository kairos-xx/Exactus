# Copyright (c) 2026
"""Animated terminal progress bar with responsive determinate modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import pi, sin
from shutil import get_terminal_size
from sys import stdout
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import TYPE_CHECKING, Final, Self, TextIO, final

if TYPE_CHECKING:
    from types import TracebackType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        ansi_red: Grouped module constant.
        ansi_reset: Grouped module constant.

    """

    ansi_red: Final = "\x1b[31m"
    ansi_reset: Final = "\x1b[0m"


class ProgressMode(Enum):
    """Available progress rendering modes.

    Attributes:
        DETERMINATE: Bar fills toward a known completion fraction.
        INDETERMINATE: A moving pulse signals ongoing work.

    """

    DETERMINATE = auto()
    "Bar fills toward a known completion fraction."
    INDETERMINATE = auto()
    "A moving pulse signals ongoing work."


@dataclass(frozen=True, slots=True)
class Settings:
    """Configure progress animation and rendering.

    Attributes:
        fill: Character used for completed determinate cells.
        empty: Character used for incomplete cells.
        head: Character used at the leading edge of determinate progress.
        pulse: Character used by the indeterminate moving segment.
        fps: Maximum number of animation frames rendered per second.
        smoothing_seconds: Approximate duration of determinate transitions.
        min: Difference below which determinate progress snaps to its target.
        max: Largest percentage accepted by responsive width expressions.
        pulse_width: Preferred width of the indeterminate moving segment.
        hide_cursor: Whether to hide the terminal cursor while rendering.

    """

    fill: str = "█"
    empty: str = "░"
    head: str = "▓"
    pulse: str = "█"
    fps: float = 30.0
    smoothing_seconds: float = 0.35
    min: float = 0.0005
    max: float = 100.0
    pulse_width: int = 4
    hide_cursor: bool = True


class TerminalProgress:
    """Render a smoothly animated, resize-aware progress bar on one line.

    Calls to :meth:`set_progress` change only the target value. A background
    thread interpolates the displayed value toward that target, so jumps such
    as 10 to 70 percent are animated instead of rendered instantaneously.

    The same instance can switch between determinate and indeterminate modes.
    A fixed integer ``width`` controls only the cells inside the bar. A string
    width is terminal-relative and controls the maximum width of the complete
    rendered line, including label, brackets, percentage, and status message.

    Responsive widths are recalculated for every animation frame. Therefore,
    resizing the terminal automatically grows or shrinks the bar without
    restarting the renderer. Frames are always constrained to the current
    terminal width to prevent the progress renderer itself from wrapping and
    leaving extra physical terminal rows behind.

    Supported responsive expressions are ``"100%"``, ``"100%-4"``, ``"80%"``,
    and ``"80%-5"``. Whitespace around the expression is ignored.

    Args:
        width: Fixed bar-cell width, or a responsive terminal-width expression.
        label: Text displayed before the progress bar.
        settings: Optional animation and rendering settings.
        stream: Text stream receiving terminal output.

    Raises:
        ValueError: If width or a settings value is invalid.

    """

    def __init__(
        self,
        *,
        width: int | str = 36,
        label: str = "",
        settings: Settings | None = None,
        stream: TextIO = stdout,
    ) -> None:
        """Initialize a terminal progress renderer.

        Args:
            width: Fixed number of cells inside the bar, or a responsive
                expression such as ``"100%-4"``. Responsive expressions define
                the maximum width of the entire rendered line.
            label: Text displayed before the progress bar.
            settings: Optional immutable rendering settings.
            stream: Text stream to which ANSI progress frames are written.

        Raises:
            ValueError: If width or any numeric setting is outside its valid
                range.

        """
        self._settings: Settings = settings or Settings()
        self._fixed_width: int | None
        self._width_percent: float | None
        self._width_offset: int
        if isinstance(width, int):
            if width < 1:
                msg: str = "width must be at least 1"
                raise ValueError(msg)
            self._fixed_width = width
            self._width_percent = None
            self._width_offset = 0
        else:
            self._fixed_width = None
            self._width_percent, self._width_offset = self._parse_width(
                width=width,
            )
        if self._settings.fps <= 0.0:
            msg = "fps must be greater than 0"
            raise ValueError(msg)
        if self._settings.smoothing_seconds <= 0.0:
            msg = "smoothing_seconds must be greater than 0"
            raise ValueError(msg)
        if self._settings.min <= 0.0:
            msg = "min must be greater than 0"
            raise ValueError(msg)
        if self._settings.pulse_width < 1:
            msg = "pulse_width must be at least 1"
            raise ValueError(msg)
        self._frame_seconds: float = 1.0 / self._settings.fps
        self._smoothing_seconds: float = self._settings.smoothing_seconds
        self._label: str = label
        self._fill: str = self._settings.fill
        self._empty: str = self._settings.empty
        self._head: str = self._settings.head
        self._pulse: str = self._settings.pulse
        self._pulse_width: int = self._settings.pulse_width
        self._stream: TextIO = stream
        self._hide_cursor: bool = self._settings.hide_cursor
        self._mode: ProgressMode = ProgressMode.DETERMINATE
        self._target: float = 0.0
        self._displayed: float = 0.0
        self._pulse_phase: float = 0.0
        self._message: str = ""
        self._lock: Lock = Lock()
        self._stop_event: Event = Event()
        self._wake_event: Event = Event()
        self._thread: Thread | None = None
        self._is_started, self._is_closed = (False, False)
        self._last_rendered: str = ""
        self._last_terminal_columns: int = self._terminal_columns()
        self._issue_marks: set[float] = set()

    @property
    def progress(self) -> float:
        """Current target progress in the inclusive range 0..1.

        Returns:
            The target fraction most recently set, clamped to 0..1.

        """
        with self._lock:
            return self._target

    @property
    def mode(self) -> ProgressMode:
        """Current rendering mode.

        Returns:
            The active determinate or indeterminate rendering mode.

        """
        with self._lock:
            return self._mode

    def start(self, *, indeterminate: bool = False) -> Self:
        """Start background rendering.

        Args:
            indeterminate: Whether to start in indeterminate mode.

        Returns:
            This progress renderer for fluent use.

        Raises:
            RuntimeError: If the progress renderer has already been closed.

        """
        with self._lock:
            if self._is_closed:
                msg: str = "a closed progress bar cannot be restarted"
                raise RuntimeError(msg)
            if self._is_started:
                self._mode = (
                    ProgressMode.INDETERMINATE
                    if indeterminate
                    else ProgressMode.DETERMINATE
                )
                self._wake_event.set()
                return self
            self._mode = (
                ProgressMode.INDETERMINATE
                if indeterminate
                else ProgressMode.DETERMINATE
            )
            self._is_started = True
            thread: Thread = Thread(
                target=self._run,
                name="terminal-progress",
                daemon=True,
            )
            self._thread = thread
        if self._hide_cursor:
            self._write(text="\x1b[?25l")
        thread.start()
        return self

    def set_progress(
        self,
        value: float,
        *,
        message: str | None = None,
    ) -> Self:
        """Set a determinate target and animate smoothly toward it.

        Args:
            value: Target progress. Values are clamped to the range 0..1.
            message: Optional trailing status text.

        Returns:
            This progress renderer for fluent use.

        """
        with self._lock:
            self._target = min(1.0, max(0.0, value))
            self._mode = ProgressMode.DETERMINATE
            if message is not None:
                self._message = message
            self._wake_event.set()
        self._ensure_started()
        return self

    def set_percent(
        self,
        percent: float,
        *,
        message: str | None = None,
    ) -> Self:
        """Set determinate progress using a percentage.

        Args:
            percent: Target percentage. Values are clamped to 0..100.
            message: Optional trailing status text.

        Returns:
            This progress renderer for fluent use.

        """
        return self.set_progress(
            value=percent / self._settings.max,
            message=message,
        )

    def set_indeterminate(self, *, message: str | None = None) -> Self:
        """Switch to the continuously animated indeterminate state.

        Args:
            message: Optional trailing status text.

        Returns:
            This progress renderer for fluent use.

        """
        with self._lock:
            self._mode = ProgressMode.INDETERMINATE
            if message is not None:
                self._message = message
            self._wake_event.set()
        self._ensure_started()
        return self

    def flag_issue(self, *, at: float | None = None) -> Self:
        """Mark the frontier cell red where an issue was found.

        The flagged position keeps its mark while the bar continues
        filling, so a failure mid-run leaves a red cell at the fraction
        the run had reached.

        Args:
            at: Fraction in ``[0, 1]`` whose cell is marked; defaults
                to the current progress target.

        Returns:
            This progress renderer for fluent use.

        """
        with self._lock:
            mark: float = (
                self._target if at is None else min(1.0, max(0.0, at))
            )
            self._issue_marks.add(mark)
            self._wake_event.set()
        self._ensure_started()
        return self

    def set_message(self, message: str) -> Self:
        """Update the trailing status message without changing progress.

        Args:
            message: New trailing status text.

        Returns:
            This progress renderer for fluent use.

        """
        with self._lock:
            self._message = message
            self._wake_event.set()
        self._ensure_started()
        return self

    def finish(self, *, message: str | None = None) -> None:
        """Animate to exactly 100 percent and close the progress renderer.

        Args:
            message: Optional final trailing status text.

        """
        self.set_progress(value=1.0, message=message)
        while True:
            with self._lock:
                if self._displayed >= 1.0 - self._settings.min:
                    self._displayed = 1.0
                    frame: str = self._render_locked()
                    break
            self._stop_event.wait(timeout=self._frame_seconds)
        self._render(text=frame)
        self.close()

    def close(self) -> None:
        """Stop rendering, restore the cursor, and preserve the final frame."""
        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
            thread: Thread | None = self._thread
        self._stop_event.set()
        self._wake_event.set()
        if thread is not None and thread is not current_thread():
            thread.join(timeout=max(1.0, self._smoothing_seconds * 4.0))
        self._write(text="\r\x1b[K")
        if self._last_rendered:
            self._write(text=self._last_rendered)
        self._write(text="\x1b[?25h\n" if self._hide_cursor else "\n")

    def __enter__(self) -> Self:
        """Start rendering when entering a context manager.

        Returns:
            This started progress renderer.

        """
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close rendering when leaving a context manager.

        Args:
            exc_type: Exception type raised in the managed block, if any.
            exc_value: Exception instance raised in the managed block, if any.
            traceback: Exception traceback raised in the managed block, if any.

        """
        del exc_type, exc_value, traceback
        self.close()

    @staticmethod
    def _parse_width(*, width: str) -> tuple[float, int]:
        """Parse a responsive terminal-width expression.

        Args:
            width: Expression in ``PERCENT%`` or ``PERCENT%-OFFSET`` form.

        Returns:
            Percentage multiplier and non-negative column offset.

        Raises:
            ValueError: If the expression is malformed or outside its range.

        """
        normalized: str = width.replace(" ", "")
        percent_text: str
        offset_text: str
        if "%-" in normalized:
            percent_text, offset_text = normalized.split(sep="%-", maxsplit=1)
        elif normalized.endswith("%"):
            percent_text = normalized[:-1]
            offset_text = "0"
        else:
            msg: str = "responsive width must use PERCENT% or PERCENT%-OFFSET"
            raise ValueError(msg)
        try:
            percent: float = float(percent_text)
            offset: int = int(offset_text)
        except ValueError as error:
            msg = f"invalid responsive width: {width!r}"
            raise ValueError(msg) from error
        if not 0.0 < percent <= Settings().max:
            msg = "responsive width percent must be greater than 0 and <= 100"
            raise ValueError(msg)
        if offset < 0:
            msg = "responsive width offset cannot be negative"
            raise ValueError(msg)
        return (percent / 100.0, offset)

    @staticmethod
    def _clip_visible(*, text: str, limit: int) -> str:
        """Truncate a frame without cutting ANSI escape sequences.

        Issue marks embed color escapes inside the bar; a naive slice
        could split an escape and corrupt the terminal, so escapes are
        copied verbatim and only printable cells count toward the limit.

        Args:
            text: Complete rendered frame.
            limit: Maximum printable columns.

        Returns:
            Frame truncated to at most ``limit`` visible cells.

        """
        if len(text) <= limit:
            return text
        out: list[str] = []
        shown: int = 0
        index: int = 0
        while index < len(text) and shown < limit:
            if text[index] == "\x1b":
                end: int = text.find("m", index)
                if end != -1:
                    out.append(text[index : end + 1])
                    index = end + 1
                    continue
            out.append(text[index])
            shown += 1
            index += 1
        return "".join(out)

    def _ensure_started(self) -> None:
        """Start the renderer if it has not already been started."""
        with self._lock:
            should_start: bool = not self._is_started
            mode: ProgressMode = self._mode
        if should_start:
            self.start(indeterminate=mode is ProgressMode.INDETERMINATE)

    def _run(self) -> None:
        """Render animation frames until the progress renderer is closed."""
        previous_time: float = monotonic()
        while not self._stop_event.is_set():
            current_time: float = monotonic()
            elapsed: float = max(0.0, current_time - previous_time)
            previous_time = current_time
            with self._lock:
                if self._mode is ProgressMode.DETERMINATE:
                    difference: float = self._target - self._displayed
                    interpolation: float = min(
                        1.0,
                        elapsed / self._smoothing_seconds,
                    )
                    self._displayed += difference * interpolation
                    if abs(difference) < self._settings.min:
                        self._displayed = self._target
                else:
                    self._pulse_phase = (
                        self._pulse_phase + elapsed / self._smoothing_seconds
                    ) % 2.0
                frame: str = self._render_locked()
            self._render(text=frame)
            self._wake_event.wait(timeout=self._frame_seconds)
            self._wake_event.clear()

    def _render_locked(self) -> str:
        """Build one frame while the state lock is held.

        Returns:
            Complete frame constrained to the current terminal width.

        """
        terminal_columns: int = self._terminal_columns()
        line_limit: int = self._line_limit(terminal_columns=terminal_columns)
        prefix: str = f"{self._label} " if self._label else ""
        suffix: str = (
            f" {self._displayed * 100.0:6.2f}%"
            if self._mode is ProgressMode.DETERMINATE
            else "   --.--%"
        )
        message: str = f"  {self._message}" if self._message else ""
        fixed_cells: int = len(prefix) + 2 + len(suffix) + len(message)
        width: int = (
            self._fixed_width
            if self._fixed_width is not None
            else max(1, line_limit - fixed_cells)
        )
        if self._fixed_width is not None:
            width = min(width, max(1, terminal_columns - fixed_cells))
        bar: str = (
            self._determinate_bar(width=width)
            if self._mode is ProgressMode.DETERMINATE
            else self._indeterminate_bar(width=width)
        )
        frame: str = f"{prefix}[{bar}]{suffix}{message}"
        return self._clip_visible(text=frame, limit=line_limit)

    def _determinate_bar(self, *, width: int) -> str:
        """Build the determinate bar body.

        Args:
            width: Number of cells available inside the bar.

        Returns:
            Determinate bar body with exactly ``width`` cells.

        """
        completed: int = min(width, int(self._displayed * width))
        has_head: bool = 0 < completed < width
        fill_count: int = completed - 1 if has_head else completed
        marks: set[int] = {
            min(width - 1, max(0, int(mark * width)))
            for mark in self._issue_marks
        }
        cells: list[str] = [
            f"{Constants.ansi_red}{self._fill}{Constants.ansi_reset}"
            if index in marks
            else self._fill
            for index in range(fill_count)
        ]
        if has_head:
            cells.append(
                f"{Constants.ansi_red}{self._head}{Constants.ansi_reset}"
                if fill_count in marks
                else self._head,
            )
        return "".join(cells) + self._empty * (width - completed)

    def _indeterminate_bar(self, *, width: int) -> str:
        """Build the indeterminate moving pulse.

        Args:
            width: Number of cells available inside the bar.

        Returns:
            Indeterminate bar body with exactly ``width`` cells.

        """
        pulse_width: int = min(self._pulse_width, width)
        travel: int = width - pulse_width
        normalized: float = 0.5 - 0.5 * sin((self._pulse_phase - 0.5) * pi)
        start: int = int(normalized * travel)
        return (
            self._empty * start
            + self._pulse * pulse_width
            + self._empty * (width - start - pulse_width)
        )

    def _line_limit(self, *, terminal_columns: int) -> int:
        """Calculate the maximum rendered line width.

        Args:
            terminal_columns: Current number of terminal columns.

        Returns:
            Maximum frame width after applying the responsive expression. One
            spare terminal column is retained to avoid auto-wrap at the right
            margin on terminals that wrap immediately at the final column.

        """
        safe_columns: int = max(1, terminal_columns - 1)
        if self._width_percent is None:
            return safe_columns
        return max(
            1,
            min(
                safe_columns,
                int(terminal_columns * self._width_percent)
                - self._width_offset,
            ),
        )

    def _terminal_columns(self) -> int:
        """Return the current terminal width with a deterministic fallback.

        Returns:
            Current terminal width in columns, or 80 when the stream does not
            expose a usable terminal file descriptor.

        """
        try:
            self._stream.fileno()
        except (AttributeError, OSError, ValueError):
            return 80
        return get_terminal_size(fallback=(80, 24)).columns

    def _render(self, *, text: str) -> None:
        """Render a changed frame and account for terminal resizing.

        Args:
            text: Complete frame to display.

        """
        terminal_columns: int = self._terminal_columns()
        has_resized: bool = terminal_columns != self._last_terminal_columns
        if text != self._last_rendered or has_resized:
            self._last_terminal_columns = terminal_columns
            self._last_rendered = text
            self._write(text=f"\r\x1b[K{text}")

    def _write(self, *, text: str) -> None:
        """Write terminal output and flush it immediately.

        Args:
            text: ANSI control sequence or visible terminal text.

        """
        self._stream.write(text)
        self._stream.flush()
