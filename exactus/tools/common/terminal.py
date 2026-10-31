#!/usr/bin/env python3
# Copyright (c) 2026
"""Responsive ANSI terminal presentation for exactus execution."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from os import O_RDWR, O_WRONLY, environ, set_blocking
from os import close as os_close
from os import fdopen as os_fdopen
from os import get_terminal_size as fd_terminal_size
from os import name as os_name
from os import open as os_open
from os import read as os_read
from os import write as os_write
from pathlib import Path
from re import Match, Pattern, sub
from re import compile as re_compile
from shutil import get_terminal_size
from subprocess import run as subprocess_run
from sys import stdout
from threading import RLock
from time import monotonic, sleep
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast, final

from exactus.tools.common.sprint import sprint
from exactus.tools.common.terminal_progress import Settings as ProgressSettings
from exactus.tools.common.terminal_progress import TerminalProgress

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TextIO


class _TermiosModule(Protocol):
    """Subset of the ``termios`` module used by the raw-mode probe.

    Attributes:
        TCSANOW: Change-timing selector applying updates immediately.
        error: Exception raised by termios operations.

    """

    TCSANOW: int
    error: type[Exception]

    def tcgetattr(self, fd: int, /) -> list[int | list[bytes | int]]:
        """Return the termios attributes for `fd`.

        Args:
            fd: File descriptor to inspect.

        Returns:
            The attribute list in ``tcsetattr`` layout.

        """
        ...

    def tcsetattr(
        self,
        fd: int,
        when: int,
        attributes: list[int | list[bytes | int]],
        /,
    ) -> None:
        """Apply `attributes` to `fd` as selected by `when`.

        Args:
            fd: File descriptor to update.
            when: Change-timing selector such as ``TCSANOW``.
            attributes: Attribute list previously read by ``tcgetattr``.

        """
        ...


class _SetRaw(Protocol):
    """``tty.setraw`` callable surface used by the raw-mode probe."""

    def __call__(self, fd: int, when: int = 2) -> None:
        """Put `fd` into raw mode as of `when`.

        Args:
            fd: Terminal file descriptor to modify.
            when: Change-timing selector such as ``TCSADRAIN``.

        """
        ...


try:
    termios: _TermiosModule | None = cast(
        typ="_TermiosModule",
        val=cast(typ="object", val=import_module(name="termios")),
    )
    setraw: _SetRaw | None = getattr(import_module(name="tty"), "setraw", None)
except ImportError:
    termios = None
    setraw = None


@final
class Constants:
    """Group module-level constants.

    Attributes:
        reset: Grouped module constant.
        bold: Grouped module constant.
        dim: Grouped module constant.
        green: Grouped module constant.
        red: Grouped module constant.
        cyan: Grouped module constant.
        yellow: Grouped module constant.
        clear: Grouped module constant.
        up: Grouped module constant.
        erase_screen: Grouped module constant.
        erase_below: Grouped module constant.
        hide_cursor: Grouped module constant.
        show_cursor: Grouped module constant.
        sync_begin: Grouped module constant.
        sync_end: Grouped module constant.
        ansi: Grouped module constant.
        live_lock: Grouped module constant.
        dsr_pattern: Grouped module constant.
        dsr_timeout: Grouped module constant.
        o_noctty: Grouped module constant.
        o_nonblock: Grouped module constant.
        failed: Grouped module constant.

    """

    reset: Final[str] = "\x1b[0m"
    bold: Final[str] = "\x1b[1m"
    dim: Final[str] = "\x1b[2m"
    green: Final[str] = "\x1b[32m"
    red: Final[str] = "\x1b[31m"
    cyan: Final[str] = "\x1b[36m"
    yellow: Final[str] = "\x1b[33m"
    clear: Final[str] = "\x1b[2K"
    up: Final[str] = "\x1b[1A"
    erase_screen: Final[str] = "\x1b[2J\x1b[3J\x1b[H"
    erase_below: Final[str] = "\x1b[J"
    hide_cursor: Final[str] = "\x1b[?25l"
    show_cursor: Final[str] = "\x1b[?25h"
    sync_begin: Final[str] = "\x1b[?2026h"
    sync_end: Final[str] = "\x1b[?2026l"
    ansi: Final[Pattern[str]] = re_compile(pattern="\\033\\[[0-9;?]*[A-Za-z]")
    live_lock: Final[RLock] = RLock()
    dsr_pattern: Final[Pattern[bytes]] = re_compile(
        pattern=b"\\x1b\\[(\\d+);(\\d+)R",
    )
    dsr_timeout: Final[float] = 0.4
    o_noctty: Final[int] = getattr(import_module(name="os"), "O_NOCTTY", 0)
    o_nonblock: Final[int] = getattr(import_module(name="os"), "O_NONBLOCK", 0)
    failed: Final[frozenset[str]] = frozenset({"FAIL", "INTERRUPT", "TIMEOUT"})


@dataclass(frozen=True, slots=True)
class ResultRow:
    """Represent result row.

    Attributes:
        tool: Tool.
        status: Status.
        duration_seconds: Duration seconds.
        resume: Resume.
        report: Report.
        stats: File and finding counts shown next to the status.

    """

    tool: str
    status: str
    duration_seconds: float
    resume: str
    report: str = ""
    stats: str = ""


class ExactusTerminal:
    """Render the only user-facing exactus terminal protocol."""

    _plain_seen: ClassVar[dict[str, str]] = {}
    _plain_stage: ClassVar[str] = ""
    _cursor_supported: ClassVar[bool | None] = None
    _rendered_lines: ClassVar[tuple[str, ...] | None] = None
    _live_width: ClassVar[int] = 0
    _mirrors: ClassVar[list[TextIO]] = []
    _mirror_frames: ClassVar[dict[int, tuple[str, ...] | None]] = {}
    _mirror_paths: ClassVar[set[str]] = set()
    _standalone_progresses: ClassVar[dict[int, TerminalProgress]] = {}

    @classmethod
    def clear_screen(cls) -> None:
        """Erase the interactive screen and scrollback before a run.

        Non-terminal output is left untouched. POSIX terminals accept
        ANSI erase sequences directly; Windows consoles clear through
        ``cmd /c cls`` because legacy ``conhost`` hosts lack virtual
        terminal processing and would print the escapes literally.

        """
        cls._rendered_lines = None
        cls._plain_seen.clear()
        cls._plain_stage = ""
        if not stdout.isatty():
            return
        if os_name == "nt":
            _ = subprocess_run(args=("cmd", "/c", "cls"), check=False)
        elif cls._supports_cursor():
            sprint(Constants.erase_screen, end="")

    @classmethod
    def emit(cls, *, text: str, stream: TextIO | None = None) -> None:
        """Print log text without corrupting a live progress block.

        Background writers (such as a mirrored server log) must use this
        instead of writing directly: the block is lifted, the text is
        scrolled above it, and the block is redrawn beneath.

        Args:
            text: Text to print; a trailing newline is added if missing.
            stream: Destination when no block is live (default stdout).

        """
        line: str = text if text.endswith("\n") else f"{text}\n"
        with Constants.live_lock:
            if cls._rendered_lines is None:
                target: TextIO = stream or stdout
                _ = target.write(line)
                target.flush()
                for mirror in cls._mirrors:
                    with suppress(OSError, ValueError):
                        _ = mirror.write(line)
                        mirror.flush()
                return
            stdout.flush()
            cls._paint(frame=cls._rendered_lines, above=line)

    @classmethod
    def progress(
        cls,
        *,
        title: str,
        global_fraction: float,
        stage: str,
        tools: tuple[tuple[str, str, float, str, float | None], ...],
        previous_lines: int,
    ) -> int:
        """Repaint the live pipeline block in place.

        Every line is clipped one column short of the terminal width so
        no row ever wraps, which keeps the cursor arithmetic exact.

        Args:
            title: Title.
            global_fraction: Global fraction.
            stage: Stage.
            tools: ``(tool, status, fraction, detail, mark)`` rows
                covering every tool in the run — running, finished, and
                waiting entries stay visible for the whole pipeline;
                ``mark`` is the fraction where the tool failed, or
                ``None`` when it has not failed.
            previous_lines: Kept for API compatibility; the renderer
                tracks what is on screen itself.

        Returns:
            Number of lines in the live block.

        """
        del previous_lines
        if not stdout.isatty() and (not cls._mirrors):
            return 0
        if stdout.isatty() and (not cls._supports_cursor()):
            plain: int = cls._plain_progress(
                title=title,
                stage=stage,
                tools=tools,
            )
            if not cls._mirrors:
                return plain
        width: int = max(
            20,
            min(get_terminal_size(fallback=(100, 24)).columns - 1, 160),
        )
        bar_width: int = max(10, min(32, width - 60))
        detail_width: int = max(1, width - bar_width - 44)
        stage_text: str = cls._fit(value=stage, width=detail_width)
        last_cell: int = max(bar_width - 1, 0)
        total: int = len(tools)
        global_marks: frozenset[int] = frozenset(
            round(number=((index + mark) / total) * last_cell)
            for index, (_, _, _, _, mark) in enumerate(iterable=tools)
            if mark is not None and total
        )
        lines: list[str] = [
            f"{Constants.bold}{Constants.cyan}{title}{Constants.reset}",
            (
                f"  {Constants.bold}{'GLOBAL':<29}{Constants.reset}"
                f" [{
                    cls._bar(
                        fraction=global_fraction,
                        issue=any(
                            cls._issue_status(status=status)
                            for _, status, _, _, _ in tools
                        ),
                        bar_width=bar_width,
                        markers=global_marks,
                    )
                }]"
                f" {global_fraction * 100:6.2f}% "
                f" {Constants.dim}{stage_text}{Constants.reset}"
            ),
        ]
        lines.extend(
            (
                f"  {cls._tag(value=status)} "
                f" {cls._fit(value=tool, width=18):<18}"
                f" [{
                    cls._bar(
                        fraction=fraction,
                        issue=cls._issue_status(status=status),
                        bar_width=bar_width,
                        markers=frozenset({round(number=mark * last_cell)})
                        if mark is not None
                        else frozenset(),
                    )
                }]"
                f" {fraction * 100:6.2f}% "
                f" {cls._fit(value=detail, width=detail_width)}"
                for tool, status, fraction, detail, mark in tools
            ),
        )
        if any((status.endswith("*") for _, status, _, _, _ in tools)):
            lines.append("  * Report updated while this pipeline was running.")
        frame: tuple[str, ...] = tuple(
            cls._clip(value=line, width=width) for line in lines
        )
        with Constants.live_lock:
            if frame != cls._rendered_lines or width != cls._live_width:
                cls._live_width = width
                cls._paint(frame=frame)
        return len(frame)

    @classmethod
    def clear_progress(cls, *, lines: int) -> None:
        """Remove the live block and restore the cursor.

        Args:
            lines: Kept for API compatibility; the renderer tracks what
                is on screen itself.

        """
        del lines
        cls._plain_seen.clear()
        cls._plain_stage = ""
        cls._finish_standalone_progresses()
        with Constants.live_lock:
            if cls._rendered_lines is not None or cls._mirrors:
                cls._paint(frame=None)
            cls._rendered_lines = None
            cls._live_width = 0

    @classmethod
    def standalone_progress(
        cls,
        *,
        tool: str,
        fraction: float,
        step: str,
    ) -> None:
        """Repaint the single standalone progress row in place.

        Args:
            tool: Tool.
            fraction: Fraction.
            step: Step.

        """
        if not stdout.isatty() and (not cls._mirrors):
            return
        streams: list[TextIO] = []
        if stdout.isatty():
            streams.append(stdout)
        streams.extend(cls._mirrors)
        for stream in streams:
            stream_id: int = id(stream)
            progress: TerminalProgress | None = cls._standalone_progresses.get(
                stream_id,
            )
            if progress is None:
                progress = TerminalProgress(
                    label=tool,
                    width="100%-4",
                    settings=ProgressSettings(hide_cursor=True),
                    stream=stream,
                ).start()
                cls._standalone_progresses[stream_id] = progress
            progress.set_progress(value=fraction, message=step)

    @classmethod
    def finish_standalone_progress(cls, *, failed: bool = False) -> None:
        """Clear the standalone progress row before final results.

        Args:
            failed: Whether the run ended in an issue; the cell the bar
                had reached is marked red while it animates to full.

        """
        if failed:
            for progress in cls._standalone_progresses.values():
                progress.flag_issue()
        cls._finish_standalone_progresses()

    @classmethod
    def mirror_tty(cls, *, path: str) -> bool:
        """Attach a replaced run's terminal as a live-progress mirror.

        Args:
            path: Terminal device path recorded by the replaced run.

        Returns:
            Whether the device was attached; empty paths, this run's own
            terminal, already-mirrored devices, and non-terminal paths
            are refused.

        """
        if not path or path == cls.tty_name() or path in cls._mirror_paths:
            return False
        stream: TextIO | None = None
        with suppress(OSError, ValueError):
            if Path(path).is_char_device():
                stream = os_fdopen(
                    fd=os_open(
                        path=path,
                        flags=O_WRONLY
                        | Constants.o_noctty
                        | Constants.o_nonblock,
                    ),
                    mode="w",
                    encoding="utf-8",
                )
        if stream is None:
            return False
        cls._mirror_paths.add(path)
        cls._mirrors.append(stream)
        cls._mirror_frames[id(stream)] = None
        return True

    @classmethod
    def detach_mirrors(cls, *, note: str = "") -> None:
        """Detach every mirrored terminal, restoring its cursor.

        Args:
            note: Optional line left behind after the mirrored live
                block is erased, explaining where the run continued.

        """
        for stream in cls._mirrors:
            cls._paint_stream(
                stream=stream,
                previous=cls._mirror_frames.get(id(stream)),
                frame=None,
            )
            if note:
                with suppress(OSError, ValueError):
                    _ = stream.write(note)
                    stream.flush()
            with suppress(OSError, ValueError):
                stream.close()
        cls._mirrors.clear()
        cls._mirror_frames.clear()
        cls._mirror_paths.clear()

    @classmethod
    def results(cls, *, title: str, rows: tuple[ResultRow, ...]) -> None:
        """Handle results.

        Args:
            title: Title.
            rows: Rows.

        """
        width: int = cls._width()
        rule: str = "─" * width
        passed: int = sum(row.status.rstrip("*") == "PASS" for row in rows)
        failed: int = len(rows) - passed
        overall: str = "PASS" if rows and failed == 0 else "FAIL"
        heading: str = cls._fit(value=title, width=width)
        sprint(
            (
                f"{Constants.bold}"
                f"{Constants.cyan}"
                f"{heading}"
                f"{Constants.reset}"
                f"\n"
                f"{Constants.dim}"
                f"{rule}"
                f"{Constants.reset}"
                f"\nResult  "
                f"{cls._status(value=overall)}"
                f"    Tools  "
                f"{len(rows)}"
                f"    Passed  "
                f"{passed}"
                f"    Failed  "
                f"{failed}"
                f"\n"
            ),
            end="",
        )
        if rows:
            sprint(f"{Constants.dim}{rule}{Constants.reset}\n", end="")
            name_width: int = min(
                28,
                max(12, *(len(row.tool) for row in rows)),
            )
            for row in rows:
                fitted: str = cls._fit(value=row.tool, width=name_width)
                sprint(
                    f"{fitted:<{name_width}} "
                    f" {cls._status(value=row.status):<20} "
                    f" {row.duration_seconds:>9.3f}s\n",
                    end="",
                )
            sprint(
                (
                    f"{Constants.dim}"
                    f"{rule}"
                    f"{Constants.reset}"
                    f"\n"
                    f"{Constants.bold}"
                    f"Resumes"
                    f"{Constants.reset}"
                    f"\n"
                ),
                end="",
            )
            for row in rows:
                sprint(
                    f"  {row.tool}: {cls._status(value=row.status)}",
                    end="",
                )
                if row.stats.strip():
                    sprint(
                        f"    {Constants.dim}"
                        f"{cls._fit(value=row.stats.strip(), width=width)}"
                        f"{Constants.reset}",
                        end="",
                    )
                sprint("\n", end="")
                if row.status.rstrip("*") != "PASS" and row.resume.strip():
                    for line in row.resume.strip().splitlines():
                        resume: str = cls._fit(value=line, width=width - 4)
                        sprint(
                            f"    {Constants.dim}{resume}{Constants.reset}\n",
                            end="",
                        )
                if row.report:
                    report: str = cls._fit(value=row.report, width=width - 2)
                    sprint(
                        f"  {Constants.dim}{report}{Constants.reset}\n\n",
                        end="",
                    )
        sprint(f"{Constants.dim}{rule}{Constants.reset}\n", end="")

    @staticmethod
    def restore_cursor() -> None:
        """Make the cursor visible again (safe to call at any time)."""
        if stdout.isatty():
            with suppress(OSError, ValueError):
                _ = stdout.write(Constants.show_cursor)
                stdout.flush()

    @staticmethod
    def tty_name() -> str | None:
        """Return the device path of the terminal behind ``stdout``.

        The path identifies this run's display to a later invocation:
        a replacing run opens it and keeps repainting live progress
        there, so a replaced run's terminal never shows a frozen block.

        Returns:
            Terminal device path such as ``/dev/ttys003``, or ``None``
            when stdout is not a terminal or the platform has no tty
            naming.

        """
        ttyname: Callable[[int], str] | None = getattr(
            import_module(name="os"),
            "ttyname",
            None,
        )
        if ttyname is None or not stdout.isatty():
            return None
        with suppress(OSError, ValueError):
            return ttyname(stdout.fileno())
        return None

    @classmethod
    def _supports_cursor(cls) -> bool:
        """Return whether the terminal honors ANSI cursor movement.

        ``isatty()`` alone is not sufficient: PTY-backed log panes and
        ``TERM=dumb`` environments accept output but silently ignore
        ``CSI A``/erase sequences, so repaint loops would append a fresh
        block on every poll. Capability is probed once per process by
        issuing a device-status report on the controlling terminal —
        real emulators answer ``CSI row ; col R`` while capture-only
        panes stay silent.

        Returns:
            The resulting value.

        """
        if cls._cursor_supported is None:
            cls._cursor_supported = cls._probe_cursor()
        return cls._cursor_supported

    @classmethod
    def _clip(cls, *, value: str, width: int) -> str:
        """Truncate colored text to ``width`` visible columns.

        Escape sequences are copied through untouched so colors never
        bleed; a reset is appended whenever the line was cut.

        Args:
            value: Possibly colored text.
            width: Maximum visible columns.

        Returns:
            Text that never wraps at ``width`` columns.

        """
        if cls._visible(value=value) <= width:
            return value
        out: list[str] = []
        shown: int = 0
        index: int = 0
        while index < len(value) and shown < width - 1:
            match: Match[str] | None = Constants.ansi.match(
                string=value,
                pos=index,
            )
            if match is not None:
                out.append(match.group())
                index = match.end()
                continue
            out.append(value[index])
            shown += 1
            index += 1
        return f"{''.join(out)}…{Constants.reset}"

    @classmethod
    def _rows(cls, *, frame: tuple[str, ...], columns: int) -> int:
        """Return the physical terminal rows a printed frame occupies.

        Lines printed at an older, wider size may wrap after a resize, so
        the count is recomputed against the current column count.

        Args:
            frame: Lines of the frame on screen.
            columns: Current terminal width.

        Returns:
            Physical rows, at least one per line.

        """
        return sum(
            max(1, -(-cls._visible(value=line) // max(columns, 1)))
            for line in frame
        )

    @classmethod
    def _paint_stream(
        cls,
        *,
        stream: TextIO,
        previous: tuple[str, ...] | None,
        frame: tuple[str, ...] | None,
        above: str = "",
    ) -> None:
        """Repaint the live block on one stream, logging ``above`` it.

        The whole update is one write: jump to the block's first row,
        erase everything below, print ``above`` (scrolling it into the
        log) and then the new frame. Synchronized-output markers make
        supporting terminals swap the frame atomically (no flicker);
        others ignore them.

        Args:
            stream: Output stream that receives the repaint.
            previous: Frame currently shown on that stream, if any.
            frame: New block lines, or ``None`` to remove the block.
            above: Text emitted before the block, newline-terminated.

        """
        columns: int = cls._columns(stream=stream)
        rows: int = (
            cls._rows(frame=previous, columns=columns) if previous else 0
        )
        parts: list[str] = [Constants.sync_begin]
        parts.append(f"\x1b[{rows}F" if rows else "\r")
        parts.append(Constants.erase_below)
        parts.append(above)
        if frame:
            parts.append(Constants.hide_cursor)
            parts.extend(f"{line}\n" for line in frame)
        else:
            parts.append(Constants.show_cursor)
        parts.append(Constants.sync_end)
        with suppress(OSError, ValueError):
            _ = stream.write("".join(parts))
            stream.flush()

    @classmethod
    def _paint(cls, *, frame: tuple[str, ...] | None, above: str = "") -> None:
        """Repaint the live block on stdout and every mirrored terminal.

        Mirrors keep a replaced run's terminal showing this run's live
        block; each stream remembers its own last frame so the repaint
        cursor arithmetic stays exact per terminal.

        Args:
            frame: New block lines, or ``None`` to remove the block.
            above: Text emitted before the block, newline-terminated.

        """
        if stdout.isatty() and cls._supports_cursor():
            cls._paint_stream(
                stream=stdout,
                previous=cls._rendered_lines,
                frame=frame,
                above=above,
            )
            cls._rendered_lines = frame or None
        for stream in cls._mirrors:
            if not above and cls._mirror_frames.get(id(stream)) == frame:
                continue
            cls._paint_stream(
                stream=stream,
                previous=cls._mirror_frames.get(id(stream)),
                frame=frame,
                above=above,
            )
            cls._mirror_frames[id(stream)] = frame or None

    @classmethod
    def _plain_progress(
        cls,
        *,
        title: str,
        stage: str,
        tools: tuple[tuple[str, str, float, str, float | None], ...],
    ) -> int:
        """Emit one appended line per tool-state transition.

        Terminals without cursor control cannot repaint a block, so the
        live view degrades to a change log: a stage heading whenever the
        group advances, and one line when a tool leaves ``WAITING`` or
        reaches a new status. ``WAITING`` rows stay silent to avoid
        flooding the output on the first poll.

        Args:
            title: Title.
            stage: Stage.
            tools: ``(tool, status, fraction, detail, mark)`` rows.

        Returns:
            ``0`` — nothing is repainted, so there are no lines to lift.

        """
        if stage != cls._plain_stage:
            cls._plain_stage = stage
            sprint(f"{title} · {stage}")
        updated: bool = False
        for tool, status, _fraction, detail, _mark in tools:
            if status == "WAITING" or cls._plain_seen.get(tool) == status:
                continue
            cls._plain_seen[tool] = status
            sprint(f"  {status.lower():<9} {tool}  {detail}")
            updated |= status.endswith("*")
        if updated:
            sprint("  * Report updated while this pipeline was running.")
        return 0

    @classmethod
    def _finish_standalone_progresses(cls) -> None:
        """Finish and remove any active standalone progress bars."""
        for progress in list(cls._standalone_progresses.values()):
            progress.finish()
        cls._standalone_progresses.clear()

    @staticmethod
    def _probe_cursor() -> bool:
        """Return probe cursor.

        Returns:
            The resulting value.

        """
        if not stdout.isatty():
            return False
        if os_name == "nt":
            return True
        if environ.get("TERM", "") == "dumb":
            return False
        return dsr_reply()

    @staticmethod
    def _width() -> int:
        """Return width.

        Returns:
            The resulting value.

        """
        return max(48, min(get_terminal_size(fallback=(100, 24)).columns, 160))

    @staticmethod
    def _fit(*, value: str, width: int) -> str:
        """Return fit.

        Args:
            value: Value.
            width: Width.

        Returns:
            The resulting value.

        """
        if len(value) <= width:
            return value
        return f"{value[: max(width - 1, 1)]}…"

    @staticmethod
    def _status(*, value: str) -> str:
        """Return status.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        color: str = (
            Constants.green
            if value.rstrip("*") in {"PASS", "DONE"}
            else (
                Constants.red
                if value.rstrip("*") == "FAIL"
                else Constants.yellow
            )
        )
        return f"{color}{Constants.bold}{value}{Constants.reset}"

    @staticmethod
    def _tag(*, value: str) -> str:
        """Return a fixed-width colored status tag for a progress row.

        Args:
            value: Tool activity status.

        Returns:
            The resulting value.

        """
        color: str = (
            Constants.green
            if value.rstrip("*") in {"PASS", "DONE"}
            else (
                Constants.red
                if value.rstrip("*") in {"FAIL", "INTERRUPT", "TIMEOUT"}
                else Constants.dim
                if value == "WAITING"
                else Constants.yellow
            )
        )
        label: str = (
            "RUN"
            if value == "RUNNING"
            else "WAIT"
            if value == "WAITING"
            else value
        )
        return f"{color}{Constants.bold}{label:<9}{Constants.reset}"

    @staticmethod
    def _visible(*, value: str) -> int:
        """Return the printable width of ``value`` without ANSI escapes.

        Args:
            value: Possibly colored text.

        Returns:
            Number of terminal columns the text occupies.

        """
        return len(sub(pattern=Constants.ansi, repl="", string=value))

    @staticmethod
    def _columns(*, stream: TextIO) -> int:
        """Return the column count of the terminal behind ``stream``.

        Args:
            stream: ``stdout`` itself or a mirrored terminal device.

        Returns:
            Terminal width, falling back to the environment default.

        """
        if stream is stdout:
            return get_terminal_size(fallback=(100, 24)).columns
        with suppress(OSError, ValueError):
            return fd_terminal_size(stream.fileno()).columns
        return get_terminal_size(fallback=(100, 24)).columns

    @staticmethod
    def _bar(
        *,
        fraction: float,
        issue: bool,
        bar_width: int,
        markers: frozenset[int] = frozenset(),
    ) -> str:
        """Render one progress bar of ``bar_width`` cells.

        Args:
            fraction: Completion in ``[0, 1]``.
            issue: Whether the row ended in an issue; its filled cells
                render red while the empty part stays dimmed.
            bar_width: Number of cells inside the bar.
            markers: Cell indexes replaced by a red ``x`` marking where
                a failure happened inside the bar.

        Returns:
            Filled and empty cells with the empty part dimmed and
            failure cells marked.

        """
        clamped: float = min(max(fraction, 0.0), 1.0)
        filled: int = round(number=clamped * bar_width)
        if not markers:
            empty: str = "░" * (bar_width - filled)
            fill: str = (
                f"{Constants.red}{'█' * filled}"
                if issue and filled
                else "█" * filled
            )
            return f"{fill}{Constants.dim}{empty}{Constants.reset}"
        parts: list[str] = []
        for index in range(bar_width):
            if index in markers:
                parts.append(f"{Constants.red}{Constants.bold}x")
            elif index < filled:
                parts.append(f"{Constants.red}█" if issue else "█")
            else:
                parts.append(f"{Constants.dim}░")
        return f"{''.join(parts)}{Constants.reset}"

    @staticmethod
    def _issue_status(*, status: str) -> bool:
        """Return whether a progress status carries an error marker.

        Args:
            status: Progress-row status.

        Returns:
            Whether its completed cells should render red.

        """
        normalized: str = status.rstrip("*")
        return normalized in Constants.failed or normalized.endswith("!")


def dsr_reply() -> bool:
    """Return whether ``stdout`` accepts ANSI cursor positioning.

    The query is written to ``stdout`` rather than ``/dev/tty`` so a log
    pane or proxy cannot report cursor support for a different terminal.
    The probe then verifies that a cursor move changes the reported
    position; a terminal that answers ``CSI 6 n`` but ignores cursor
    controls falls back to the transition log.

    Returns:
        The resulting value.

    """
    try:
        descriptor: int = os_open(
            path="/dev/tty",
            flags=O_RDWR | Constants.o_noctty,
        )
        output: int = stdout.fileno()
    except (OSError, ValueError):
        return False
    try:
        return dsr_cursor_moves(descriptor=descriptor, output=output)
    finally:
        os_close(fd=descriptor)


def dsr_cursor_moves(*, descriptor: int, output: int) -> bool:
    """Verify one reversible cursor move against the output terminal.

    Args:
        descriptor: Read descriptor for the controlling terminal.
        output: Descriptor that receives ANSI cursor controls.

    Returns:
        Whether the reported cursor position changed as requested.

    """
    if termios is None or setraw is None:
        return False
    try:
        previous: list[int | list[bytes | int]] = termios.tcgetattr(descriptor)
    except (OSError, termios.error):
        return False
    try:
        _ = setraw(fd=descriptor)
        set_blocking(descriptor, False)
        position: tuple[int, int] | None = _dsr_position(
            descriptor=descriptor,
            output=output,
        )
        if position is None:
            return False
        row, column = position
        if column > 1:
            command: bytes = b"\x1b[1D"
            restore: bytes = b"\x1b[1C"
            expected: int = column - 1
        else:
            command = b"\x1b[1C"
            restore = b"\x1b[1D"
            expected = 2
        try:
            _ = os_write(output, command)
            moved: tuple[int, int] | None = _dsr_position(
                descriptor=descriptor,
                output=output,
            )
        finally:
            with suppress(OSError):
                _ = os_write(output, restore)
    except (OSError, termios.error):
        return False
    else:
        return moved == (row, expected)
    finally:
        with suppress(OSError, termios.error):
            termios.tcsetattr(descriptor, termios.TCSANOW, previous)


def _dsr_position(*, descriptor: int, output: int) -> tuple[int, int] | None:
    """Write ``CSI 6 n`` and return the ``CSI row ; col R`` position.

    Args:
        descriptor: Read descriptor for the controlling terminal.
        output: Descriptor that receives the cursor position request.

    Returns:
        The reported ``(row, column)``, or ``None`` after a timeout.

    """
    _ = os_write(output, b"\x1b[6n")
    response: bytes = b""
    match: Match[bytes] | None = None
    deadline: float = monotonic() + Constants.dsr_timeout
    while monotonic() < deadline and match is None:
        try:
            response += os_read(descriptor, 64)
        except BlockingIOError:
            sleep(0.01)
        match = Constants.dsr_pattern.search(string=response)
    if match is None:
        return None
    return (int(match[1]), int(match[2]))
