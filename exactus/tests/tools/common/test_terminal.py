# Copyright (c) 2026
"""ANSI terminal rendering, progress painting, and cursor probing."""

from __future__ import annotations

from contextlib import suppress
from io import StringIO
from os import close, pipe, read, set_blocking, ttyname, write
from pty import openpty
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, NoReturn, final

import pytest

from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_not_in,
    expect_true,
    private,
    private_call,
    private_clear,
    private_result,
    set_private,
)
from exactus.tools.common import terminal as tm
from exactus.tools.common.terminal import ExactusTerminal, ResultRow

if TYPE_CHECKING:
    from collections.abc import Iterator


class Tty(StringIO):
    """A string stream that claims to be a terminal."""

    def isatty(self) -> bool:
        """Report terminal attachment.

        Returns:
            Always true.

        """
        return not self.closed

    def fileno(self) -> NoReturn:
        """Raise like a stream without a descriptor.

        Raises:
            ValueError: Always.

        """
        msg: str = f"{type(self).__name__} has no descriptor"
        raise ValueError(msg)


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> Iterator[Tty]:
    """Replace the module stdout with a terminal-like stream.

    Args:
        monkeypatch: Pytest patching helper.

    Yields:
        The fake terminal.

    """
    stream: Tty = Tty()
    monkeypatch.setattr(target=tm, name="stdout", value=stream)

    def sprint_stub(
        *values: object,
        end: str = "\n",
        **options: object,
    ) -> None:
        """Write printed values straight into the fake stream.

        Args:
            *values: Values to print.
            end: Line terminator.
            **options: Ignored print options.

        """
        del options
        _ = stream.write("".join(str(object=item) for item in values) + end)

    monkeypatch.setattr(target=tm, name="sprint", value=sprint_stub)
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="_cursor_supported",
        value=True,
    )
    set_private(owner=ExactusTerminal, name="_rendered_lines", value=None)
    private_clear(owner=ExactusTerminal, name="_plain_seen")
    yield stream
    set_private(owner=ExactusTerminal, name="_rendered_lines", value=None)


@pytest.fixture
def plain(monkeypatch: pytest.MonkeyPatch) -> StringIO:
    """Replace the module stdout with a non-terminal stream.

    Args:
        monkeypatch: Pytest patching helper.

    Returns:
        The captured stream.

    """
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=tm, name="stdout", value=stream)

    def sprint_stub(
        *values: object,
        end: str = "\n",
        **options: object,
    ) -> None:
        """Write printed values straight into the fake stream.

        Args:
            *values: Values to print.
            end: Line terminator.
            **options: Ignored print options.

        """
        del options
        _ = stream.write("".join(str(object=item) for item in values) + end)

    monkeypatch.setattr(target=tm, name="sprint", value=sprint_stub)
    return stream


@final
class Constants:
    """Group module-level constants.

    Attributes:
        red: Grouped module constant.
        yellow: Grouped module constant.
        reset: Grouped module constant.
        dim: Grouped module constant.
        hide_cursor: Grouped module constant.
        show_cursor: Grouped module constant.
        erase_screen: Grouped module constant.
        min_width: Grouped module constant.
        max_width: Grouped module constant.
        tools: Grouped module constant.

    """

    red: Final[str] = "\x1b[31m"
    yellow: Final[str] = "\x1b[33m"
    reset: Final[str] = "\x1b[0m"
    dim: Final[str] = "\x1b[2m"
    hide_cursor: Final[str] = "\x1b[?25l"
    show_cursor: Final[str] = "\x1b[?25h"
    erase_screen: Final[str] = "\x1b[2J\x1b[3J\x1b[H"
    min_width: Final[int] = 48
    max_width: Final[int] = 160
    tools: Final[tuple[tuple[str, str, float, str, float | None], ...]] = (
        ("lints", "RUNNING", 0.5, "ruff", None),
        ("docs", "WAITING", 0.0, "", None),
        ("readme", "PASS", 1.0, "done", None),
        ("docs", "FAIL", 1.0, "bad", 0.75),
        ("cov", "TIMEOUT", 0.2, "slow", 0.2),
    )


def _progress(*, fraction: float, stage: str) -> int:
    """Paint the standard progress block.

    Args:
        fraction: Global completion fraction.
        stage: Stage label.

    Returns:
        Number of lines in the live block.

    """
    return ExactusTerminal.progress(
        title="Run",
        global_fraction=fraction,
        stage=stage,
        tools=Constants.tools,
        previous_lines=0,
    )


def test_helpers() -> None:
    """Width fitting, ANSI measuring, clipping and row counting."""
    expect_equal(
        actual=private_call(
            owner=ExactusTerminal,
            name="_fit",
            value="abcdef",
            width=4,
        ),
        expected="abc…",
    )
    expect_equal(
        actual=private_call(
            owner=ExactusTerminal,
            name="_fit",
            value="ab",
            width=4,
        ),
        expected="ab",
    )
    colored: str = f"{Constants.red}hello world{Constants.reset}"
    expect_equal(
        actual=private_call(
            owner=ExactusTerminal,
            name="_visible",
            value=colored,
        ),
        expected=11,
    )
    clipped: str = private_result(
        owner=ExactusTerminal,
        name="_clip",
        kind=str,
        value=colored,
        width=6,
    )
    expect_true(condition=clipped.endswith("…" + Constants.reset))
    expect_equal(
        actual=private_call(
            owner=ExactusTerminal,
            name="_clip",
            value="ab",
            width=6,
        ),
        expected="ab",
    )
    expect_equal(
        actual=private_call(
            owner=ExactusTerminal,
            name="_rows",
            frame=("a" * 25, "b"),
            columns=10,
        ),
        expected=4,
    )
    width: int = private_result(owner=ExactusTerminal, name="_width", kind=int)
    expect_true(condition=Constants.min_width <= width <= Constants.max_width)
    expect_in(
        member="PASS",
        container=private_result(
            owner=ExactusTerminal,
            name="_status",
            kind=str,
            value="PASS",
        ),
    )
    expect_in(
        member=Constants.red,
        container=private_result(
            owner=ExactusTerminal,
            name="_status",
            kind=str,
            value="FAIL",
        ),
    )
    expect_in(
        member=Constants.yellow,
        container=private_result(
            owner=ExactusTerminal,
            name="_status",
            kind=str,
            value="X",
        ),
    )
    for value in ("RUNNING", "WAITING", "PASS", "FAIL", "INTERRUPT", "X"):
        expect_true(
            condition=bool(
                private_call(owner=ExactusTerminal, name="_tag", value=value),
            ),
        )


def test_bar_is_contiguous_and_marks_issues_red() -> None:
    """Aggregate bars fill continuously and propagate issue color."""
    bar: str = private_result(
        owner=ExactusTerminal,
        name="_bar",
        kind=str,
        fraction=0.3,
        issue=False,
        bar_width=10,
    )
    expect_equal(
        actual=bar,
        expected=(f"███{Constants.dim}░░░░░░░{Constants.reset}"),
    )
    expect_equal(
        actual=private_result(
            owner=ExactusTerminal,
            name="_bar",
            kind=str,
            fraction=0.5,
            issue=True,
            bar_width=4,
        ),
        expected=(f"{Constants.red}██{Constants.dim}░░{Constants.reset}"),
    )


def test_results_table(plain: StringIO) -> None:
    """Results render a summary, rows, and report paths.

    Args:
        plain: Captured non-terminal stream.

    """
    rows: tuple[ResultRow, ResultRow] = (
        ResultRow(
            tool="lints",
            status="PASS",
            duration_seconds=1.5,
            resume="ok",
            report="EXACTUS_RESULTS/LINTS/result.md",
        ),
        ResultRow(
            tool="docs" * 12,
            status="FAIL",
            duration_seconds=0.25,
            resume="bad",
        ),
    )
    ExactusTerminal.results(title="Title", rows=rows)
    text: str = plain.getvalue()
    expect_in(member="Passed  1", container=text)
    expect_in(member="Failed  1", container=text)
    expect_in(member="Resumes", container=text)
    expect_in(member="lints:", container=text)
    expect_in(member="lints", container=text)
    plain.truncate(0)
    ExactusTerminal.results(title="Empty", rows=())
    expect_in(member="FAIL", container=plain.getvalue())


def test_progress_requires_tty(plain: StringIO) -> None:
    """Non-terminal output draws nothing.

    Args:
        plain: Captured non-terminal stream.

    """
    expect_equal(
        actual=ExactusTerminal.progress(
            title="t",
            global_fraction=0.5,
            stage="s",
            tools=Constants.tools,
            previous_lines=0,
        ),
        expected=0,
    )
    ExactusTerminal.standalone_progress(tool="x", fraction=0.1, step="s")
    ExactusTerminal.finish_standalone_progress()
    ExactusTerminal.restore_cursor()
    ExactusTerminal.clear_screen()
    expect_equal(actual=plain.getvalue(), expected="")


def test_progress_paints_and_repaints(tty: Tty) -> None:
    """The live block is painted once and replaced on change.

    Args:
        tty: Captured terminal-like stream.

    """
    count: int = _progress(fraction=0.25, stage="wave 1")
    expect_equal(actual=count, expected=len(Constants.tools) + 2)
    first: str = tty.getvalue()
    _ = _progress(fraction=0.25, stage="wave 1")
    expect_equal(actual=tty.getvalue(), expected=first)
    _ = _progress(fraction=0.75, stage="wave 1")
    expect_not_equal(actual=tty.getvalue(), expected=first)
    ExactusTerminal.emit(text="log line")
    expect_in(member="log line", container=tty.getvalue())
    ExactusTerminal.clear_progress(lines=0)
    expect_none(value=private(owner=ExactusTerminal, name="_rendered_lines"))
    out: StringIO = StringIO()
    ExactusTerminal.emit(text="direct\n", stream=out)
    expect_equal(actual=out.getvalue(), expected="direct\n")


def test_progress_marks_failure_cells(tty: Tty) -> None:
    """A failed tool paints a red x at its failure fraction.

    Args:
        tty: Captured terminal-like stream.

    """
    _ = ExactusTerminal.progress(
        title="Run",
        global_fraction=0.6,
        stage="settled 2/3",
        tools=(
            ("lints", "PASS", 1.0, "done", None),
            ("docs", "FAIL", 1.0, "bad", 0.5),
            ("readme", "RUNNING", 0.3, "audit", None),
        ),
        previous_lines=0,
    )
    text: str = tty.getvalue()
    marked: str = "\x1b[31m\x1b[1mx"
    expect_in(member=marked, container=text)
    global_row: str = next(
        line for line in text.splitlines() if "GLOBAL" in line
    )
    expect_in(member="x", container=global_row)
    ExactusTerminal.clear_progress(lines=0)


def test_plain_progress_logs_transitions(
    tty: Tty,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminals without cursor control get an appended change log.

    Args:
        tty: Captured terminal-like stream.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="_cursor_supported",
        value=False,
    )
    expect_equal(actual=_progress(fraction=0.1, stage="a"), expected=0)
    first: str = tty.getvalue()
    expect_in(member="running", container=first)
    expect_not_in(member="waiting", container=first)
    _ = _progress(fraction=0.1, stage="a")
    expect_equal(actual=tty.getvalue(), expected=first)


def test_standalone_progress_and_cursor(tty: Tty) -> None:
    """Standalone rows hide and restore the cursor.

    Args:
        tty: Captured terminal-like stream.

    """
    ExactusTerminal.standalone_progress(tool="docs", fraction=2.0, step="go")
    expect_in(member=Constants.hide_cursor, container=tty.getvalue())
    expect_in(member="docs", container=tty.getvalue())
    ExactusTerminal.finish_standalone_progress()
    ExactusTerminal.restore_cursor()
    expect_in(member=Constants.show_cursor, container=tty.getvalue())
    ExactusTerminal.clear_screen()
    expect_in(member=Constants.erase_screen, container=tty.getvalue())


def test_clear_screen_on_windows(
    tty: Tty,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows consoles clear through ``cmd /c cls``.

    Args:
        tty: Captured terminal-like stream.
        monkeypatch: Pytest patching helper.

    """
    calls: list[tuple[str, ...]] = []

    def record_call(*, args: tuple[str, ...], check: bool) -> None:
        """Record the command instead of running it.

        Args:
            args: Command line.
            check: Ignored flag.

        """
        del check
        calls.append(args)

    monkeypatch.setattr(target=tm, name="os_name", value="nt")
    monkeypatch.setattr(target=tm, name="subprocess_run", value=record_call)
    ExactusTerminal.clear_screen()
    expect_equal(actual=calls, expected=[("cmd", "/c", "cls")])
    expect_equal(actual=tty.getvalue(), expected="")


def test_probe_cursor_branches(
    tty: Tty,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The capability probe honors platform and TERM.

    Args:
        tty: Captured terminal-like stream.
        monkeypatch: Pytest patching helper.

    """

    def probe() -> object:
        """Run the private capability probe.

        Returns:
            Whether cursor control is supported.

        """
        return private_call(owner=ExactusTerminal, name="_probe_cursor")

    monkeypatch.setattr(target=tm, name="os_name", value="nt")
    expect_true(condition=bool(probe()))
    monkeypatch.setattr(target=tm, name="os_name", value="posix")
    monkeypatch.setenv(name="TERM", value="dumb")
    expect_false(condition=bool(probe()))
    monkeypatch.setenv(name="TERM", value="xterm")
    monkeypatch.setattr(
        target=tm,
        name="dsr_reply",
        value=Constant(value=True),
    )
    expect_true(condition=bool(probe()))
    monkeypatch.undo()
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="_cursor_supported",
        value=None,
    )
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="_probe_cursor",
        value=staticmethod(Constant(value=False)),
    )
    expect_false(
        condition=bool(
            private_call(owner=ExactusTerminal, name="_supports_cursor"),
        ),
    )
    expect_true(condition=bool(tty))


def test_probe_without_tty(plain: StringIO) -> None:
    """A non-terminal stdout never supports cursor control.

    Args:
        plain: Captured non-terminal stream.

    """
    expect_false(
        condition=bool(
            private_call(owner=ExactusTerminal, name="_probe_cursor"),
        ),
    )
    expect_false(condition=bool(plain.getvalue()))


def test_dsr_reply_without_descriptor(
    tty: Tty,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing /dev/tty or stdout descriptors disable cursor support.

    Args:
        tty: Captured terminal-like stream.
        monkeypatch: Pytest patching helper.

    """
    expect_false(condition=tm.dsr_reply())
    monkeypatch.setattr(target=tm, name="os_open", value=Constant(value=99999))
    expect_false(condition=tm.dsr_reply())
    expect_true(condition=bool(tty))


def _terminal_emulator(
    master: int,
    out_read: int,
    *,
    column: int,
    answer: bool,
) -> Thread:
    """Start a thread acting as the terminal on the other side.

    Args:
        master: PTY master descriptor feeding the slave's input.
        out_read: Read end of the pipe the probe writes cursor codes to.
        column: Initial cursor column.
        answer: Whether to reply to position requests.

    Returns:
        The started daemon thread.

    """

    def loop() -> None:
        """Answer cursor requests until the probe closes its pipe."""
        col: int = column
        while True:
            data: bytes = read(out_read, 64)
            if not data:
                return
            for chunk in data.replace(b"\x1b[", b"\n\x1b[").split(sep=b"\n"):
                if chunk == b"\x1b[6n" and answer:
                    write(master, f"\x1b[3;{col}R".encode())
                elif chunk == b"\x1b[1D":
                    col -= 1
                elif chunk == b"\x1b[1C":
                    col += 1

    thread: Thread = Thread(target=loop, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize(
    ("column", "answer", "expected"),
    [(5, True, True), (1, True, True), (5, False, False)],
)
def test_dsr_cursor_moves(
    *,
    column: int,
    answer: bool,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cursor probing succeeds only against a responsive terminal.

    Args:
        column: Parametrized initial cursor column.
        answer: Parametrized terminal reply behavior.
        expected: Parametrized expected outcome.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=tm.Constants, name="dsr_timeout", value=0.3)
    master, slave = openpty()
    out_read, out_write = pipe()
    thread: Thread = _terminal_emulator(
        master=master,
        out_read=out_read,
        column=column,
        answer=answer,
    )
    try:
        expect_true(
            condition=tm.dsr_cursor_moves(descriptor=slave, output=out_write)
            is expected,
        )
    finally:
        close(fd=out_write)
        thread.join(timeout=2)
        for descriptor in (out_read, master, slave):
            close(fd=descriptor)


def test_dsr_cursor_moves_without_termios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing termios support disables the probe.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=tm, name="termios", value=None)
    expect_false(condition=tm.dsr_cursor_moves(descriptor=0, output=1))


def test_dsr_cursor_moves_bad_descriptor() -> None:
    """A non-terminal descriptor is rejected."""
    r, w = pipe()
    try:
        expect_false(condition=tm.dsr_cursor_moves(descriptor=r, output=w))
    finally:
        close(fd=r)
        close(fd=w)


@pytest.mark.parametrize("cursor", [True, False])
def test_refreshed_report_status_and_legend(
    tty: Tty,
    monkeypatch: pytest.MonkeyPatch,
    *,
    cursor: bool,
) -> None:
    """Explain marked reports in both live and plain terminal output.

    Args:
        tty: Captured terminal stream.
        monkeypatch: Test patch manager.
        cursor: Whether live repainting is available.

    """
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="_cursor_supported",
        value=cursor,
    )
    _ = ExactusTerminal.progress(
        title="unified",
        global_fraction=0.5,
        stage="running",
        tools=(
            ("lints", "PASS*", 1.0, "complete", None),
            ("docs", "FAIL*", 1.0, "complete", 0.5),
        ),
        previous_lines=0,
    )
    text: str = tty.getvalue().lower()
    expect_in(member="pass*", container=text)
    expect_in(member="fail*", container=text)
    expect_in(
        member="* report updated while this pipeline was running.",
        container=text,
    )


def _pty_drain(*, master: int) -> list[bytes]:
    """Drain a PTY master on a daemon thread like a real terminal.

    A terminal emulator continuously consumes output; without a reader
    the slave's tiny output queue fills and even a non-blocking write
    drops frames. The returned list collects chunks until the slave is
    closed.

    Args:
        master: Read end opposite the mirrored slave device.

    Returns:
        The shared chunk list accumulating everything written.

    """
    chunks: list[bytes] = []

    def loop() -> None:
        """Consume master output until the slave side closes."""
        set_blocking(master, False)
        while True:
            try:
                chunk: bytes = read(master, 65536)
            except BlockingIOError:
                sleep(0.01)
                continue
            except OSError:
                return
            if not chunk:
                return
            chunks.append(chunk)

    Thread(target=loop, daemon=True).start()
    return chunks


def _pty_text(*, chunks: list[bytes], timeout: float = 2.0) -> str:
    """Wait for mirror output collected by :func:`_pty_drain`.

    Args:
        chunks: Shared chunk list filled by the drain thread.
        timeout: Maximum wait for the first chunk after the mark.

    Returns:
        Everything written to the mirror since the call started.

    """
    mark: int = len(chunks)
    deadline: float = monotonic() + timeout
    while len(chunks) == mark and monotonic() < deadline:
        sleep(0.01)
    quiet: float = monotonic() + 0.1
    seen: int = len(chunks)
    while monotonic() < quiet and monotonic() < deadline:
        if len(chunks) != seen:
            seen = len(chunks)
            quiet = monotonic() + 0.1
        sleep(0.005)
    return b"".join(chunks[mark:]).decode(errors="replace")


def _pty_until(
    *,
    chunks: list[bytes],
    members: tuple[str, ...],
    start: int,
    timeout: float = 5.0,
) -> str:
    """Wait until every expected member appears in output since ``start``.

    Output is read from a fixed chunk index taken *before* the action
    under test, so chunks the drain thread appends before this helper
    runs are never lost to a late mark.

    Args:
        chunks: Shared chunk list filled by the drain thread.
        members: Substrings that must all appear before returning early.
        start: Chunk index captured before the action produced output.
        timeout: Maximum total wait in seconds.

    Returns:
        Decoded output since ``start``, complete or partial on timeout.

    """
    deadline: float = monotonic() + timeout
    text: str = ""
    while monotonic() < deadline:
        text = b"".join(chunks[start:]).decode(errors="replace")
        if all(member in text for member in members):
            return text
        sleep(0.01)
    return text


def test_tty_name_requires_real_terminal(tty: Tty, plain: StringIO) -> None:
    """``tty_name`` only reports the device for a true terminal.

    Args:
        tty: Terminal-like stream without a descriptor.
        plain: Non-terminal stream.

    """
    del tty, plain
    expect_none(value=ExactusTerminal.tty_name())


def test_mirror_tty_attaches_and_detaches(plain: StringIO) -> None:
    """A replaced run's terminal keeps showing live progress.

    Even with ``stdout`` redirected, the frame painted by
    :meth:`ExactusTerminal.progress` reaches the device recorded by the
    replaced run, ``emit`` lines land on it, and detaching erases the
    block while restoring the cursor.

    Args:
        plain: Non-terminal stream standing in for the new run.

    """
    master, slave = openpty()
    try:
        chunks: list[bytes] = _pty_drain(master=master)
        path: str = ttyname(slave)
        expect_true(condition=ExactusTerminal.mirror_tty(path=path))
        expect_false(condition=ExactusTerminal.mirror_tty(path=path))
        expect_false(condition=ExactusTerminal.mirror_tty(path=""))
        expect_false(
            condition=ExactusTerminal.mirror_tty(path="pyproject.toml"),
        )
        _ = ExactusTerminal.progress(
            title="t",
            global_fraction=0.5,
            stage="s",
            tools=Constants.tools,
            previous_lines=0,
        )
        text: str = _pty_text(chunks=chunks)
        expect_in(member="GLOBAL", container=text)
        expect_in(member="lints", container=text)
        ExactusTerminal.emit(text="note")
        _ = ExactusTerminal.progress(
            title="t",
            global_fraction=0.75,
            stage="s",
            tools=Constants.tools,
            previous_lines=0,
        )
        text = _pty_text(chunks=chunks)
        expect_in(member="note", container=text)
        expect_in(member="75.00%", container=text)
        detach_mark: int = len(chunks)
        ExactusTerminal.detach_mirrors(note="moved\n")
        text = _pty_until(
            chunks=chunks,
            members=(Constants.show_cursor, "moved"),
            start=detach_mark,
        )
        expect_in(member=Constants.show_cursor, container=text)
        expect_in(member="moved", container=text)
        expect_true(condition=len(plain.getvalue()) > 0)
    finally:
        ExactusTerminal.detach_mirrors()
        for descriptor in (master, slave):
            with suppress(OSError):
                close(fd=descriptor)


def test_mirror_tty_skips_own_terminal(
    plain: StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The new run never mirrors back onto its own display.

    Args:
        plain: Non-terminal stream.
        monkeypatch: Pytest patching helper.

    """
    del plain
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="tty_name",
        value=staticmethod(Constant(value="/dev/fake-tty")),
    )
    expect_false(condition=ExactusTerminal.mirror_tty(path="/dev/fake-tty"))
