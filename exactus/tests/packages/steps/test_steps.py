# Copyright (c) 2026
"""Exercise the reusable timestamped step trace."""

from __future__ import annotations

from io import StringIO, TextIOBase
from re import match
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Final, final

from exactus.packages.steps import StepLog, core, main, span, step_log, trace
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    private,
    require_type,
    set_private,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


@final
class Constants:
    """Group module-level constants.

    Attributes:
        stamp: Grouped module constant.

    """

    stamp: Final[str] = (
        "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}[+-]\\d{2}:\\d{2} "
        "\\+\\s*\\d+\\.\\d{3}s "
    )


@final
class _FailingStream:
    """Stream stub whose writes and flushes always fail."""

    @staticmethod
    def write(text: str) -> int:
        """Fail unconditionally.

        Args:
            text: Ignored payload.

        Returns:
            Never reached; the function always raises.

        Raises:
            OSError: Always, to exercise stream-failure handling.

        """
        del text
        msg: str = "write failed"
        raise OSError(msg)

    @staticmethod
    def flush() -> None:
        """Fail unconditionally.

        Raises:
            OSError: Always, to exercise stream-failure handling.

        """
        msg: str = "flush failed"
        raise OSError(msg)


def _trace_lines(*, path: Path) -> list[str]:
    """Read one trace file into lines.

    Args:
        path: Trace file to read.

    Returns:
        Written step lines.

    """
    return path.read_text(encoding="utf-8").splitlines()


def test_trace_is_a_noop_without_an_active_log() -> None:
    """Forward nothing and raise nothing when no log is active."""
    expect_none(value=core.Constants.active)
    trace(step="orphan step", depth=2)
    expect_none(value=core.Constants.active)


def test_step_log_writes_timestamped_depth_lines(tmp_path: Path) -> None:
    """Write one timestamped, depth-indented line per recorded step.

    Args:
        tmp_path: Pytest temporary directory.

    """
    destination: Path = tmp_path / "out" / "steps.txt"
    with step_log(path=destination) as log:
        trace(step="demo: run start")
        log.write(step="stage: collect", depth=1)
        trace(step="collect: app.py — passed", depth=4)
    lines: list[str] = _trace_lines(path=destination)
    expect_equal(actual=len(lines), expected=3)
    for line in lines:
        expect_true(
            condition=match(pattern=Constants.stamp, string=line) is not None,
            message=f"missing timestamp prefix: {line!r}",
        )
    expect_true(condition=lines[0].endswith("demo: run start"))
    expect_true(condition=lines[1].endswith("  stage: collect"))
    expect_true(
        condition=lines[2].endswith("        collect: app.py — passed"),
    )


def test_nested_step_log_reuses_the_active_log(tmp_path: Path) -> None:
    """Reuse the outer log instead of truncating or reopening.

    Args:
        tmp_path: Pytest temporary directory.

    """
    outer_path: Path = tmp_path / "outer" / "steps.txt"
    inner_path: Path = tmp_path / "inner" / "steps.txt"
    with step_log(path=outer_path) as outer:
        trace(step="outer: before")
        with step_log(path=inner_path) as inner:
            expect_true(condition=inner is outer)
            trace(step="inner: nested event")
        trace(step="outer: after")
    expect_false(condition=inner_path.exists())
    lines: list[str] = _trace_lines(path=outer_path)
    expect_equal(actual=len(lines), expected=3)
    expect_in(member="inner: nested event", container=lines[1])


def test_step_log_context_resets_active_and_closes(tmp_path: Path) -> None:
    """Deactivate the log and close its stream when the context exits.

    Args:
        tmp_path: Pytest temporary directory.

    """
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination) as log:
        expect_true(condition=core.Constants.active is log)
    expect_none(value=core.Constants.active)
    expect_none(value=private(owner=log, name="_stream"))


def test_step_log_degrades_when_destination_cannot_open(
    tmp_path: Path,
) -> None:
    """Disable the log silently when the file cannot be created.

    Args:
        tmp_path: Pytest temporary directory.

    """
    blocker: Path = tmp_path / "blocker"
    blocker.write_text(data="file", encoding="utf-8")
    log: StepLog = StepLog(path=blocker / "sub" / "steps.txt")
    expect_none(value=private(owner=log, name="_stream"))
    log.write(step="lost step")
    log.close()


def test_write_failure_disables_the_stream(tmp_path: Path) -> None:
    """Drop the stream after one failed write without raising.

    Args:
        tmp_path: Pytest temporary directory.

    """
    log: StepLog = StepLog(path=tmp_path / "steps.txt")
    original: TextIOBase = require_type(
        value=private(owner=log, name="_stream"),
        kind=TextIOBase,
    )
    original.close()
    set_private(owner=log, name="_stream", value=_FailingStream())
    log.write(step="boom")
    expect_none(value=private(owner=log, name="_stream"))
    log.write(step="ignored")
    log.close()


def test_write_false_discards_every_step(tmp_path: Path) -> None:
    """``[tool.steps] write = false`` never creates the trace file.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.steps]\nwrite = false\n",
        encoding="utf-8",
    )
    destination: Path = tmp_path / "out" / "steps.txt"
    with step_log(path=destination) as log:
        trace(step="discarded step", depth=1)
    expect_false(condition=destination.exists())
    expect_none(value=private(owner=log, name="_stream"))
    log.close()


def test_write_true_records_steps(tmp_path: Path) -> None:
    """``[tool.steps] write = true`` keeps the trace file enabled.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.steps]\nwrite = true\n",
        encoding="utf-8",
    )
    destination: Path = tmp_path / "out" / "steps.txt"
    with step_log(path=destination):
        trace(step="recorded step", depth=1)
    expect_true(condition=destination.is_file())
    expect_in(
        member="recorded step",
        container=_trace_lines(path=destination)[0],
    )


def test_pyproject_without_steps_section_keeps_writing(tmp_path: Path) -> None:
    """A pyproject without ``[tool.steps]`` leaves writing enabled.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data='[project]\nname = "demo"\n',
        encoding="utf-8",
    )
    destination: Path = tmp_path / "out" / "steps.txt"
    with step_log(path=destination):
        trace(step="recorded step")
    expect_true(condition=destination.is_file())


def test_main_writes_a_demonstration_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write and print the package demonstration trace.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=core, name="stdout", value=sink)
    destination: Path = tmp_path / "demo" / "steps.txt"
    expect_equal(actual=main(path=destination), expected=0)
    rendered: str = destination.read_text(encoding="utf-8")
    expect_in(member="steps: demonstration run", container=rendered)
    expect_in(member="  stage: collect", container=rendered)
    expect_in(member="steps: demonstration finished", container=rendered)
    output: str = sink.getvalue()
    expect_in(member="step trace:", container=output)
    expect_in(member="stage: report", container=output)


def test_span_writes_begin_and_measured_end_lines(tmp_path: Path) -> None:
    """A span pairs a plain begin line with a ``@dur`` end line.

    Args:
        tmp_path: Pytest temporary directory.

    """
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        with span(step="stage: build", depth=1):
            trace(step="build: inside", depth=2)
        trace(step="exec: tool — exit 0", duration=1.5)
    lines: list[str] = _trace_lines(path=destination)
    expect_equal(actual=len(lines), expected=4)
    expect_true(condition=lines[0].endswith("  stage: build @span=1"))
    expect_true(condition=lines[1].endswith("    build: inside"))
    expect_true(
        condition=match(
            pattern=r".*  stage: build — done @span=1 @dur=\d+\.\d{3}s$",
            string=lines[2],
        )
        is not None,
    )
    expect_true(condition=lines[3].endswith("exec: tool — exit 0 @dur=1.500s"))


def test_worker_threads_are_tagged_and_main_is_not(tmp_path: Path) -> None:
    """Only non-main threads receive an ``@thread`` trailer.

    Args:
        tmp_path: Pytest temporary directory.

    """
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        trace(step="main: step")
        worker: Thread = Thread(
            target=trace,
            kwargs={"step": "pool: step"},
            name="Pool Worker 3",
        )
        worker.start()
        worker.join()
    lines: list[str] = _trace_lines(path=destination)
    expect_true(condition=lines[0].endswith("main: step"))
    expect_true(
        condition=lines[1].endswith("pool: step @thread=Pool_Worker_3"),
    )


def test_span_without_an_active_log_only_runs_the_body() -> None:
    """Spans are transparent when tracing is not active."""
    ran: list[bool] = []
    with span(step="orphan"):
        ran.append(True)
    expect_equal(actual=ran, expected=[True])


def test_configured_sampling_writes_resource_lines(tmp_path: Path) -> None:
    """``[tool.steps] sample`` adds ``~sample`` lines with usage fields.

    Args:
        tmp_path: Pytest temporary directory.

    """
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.steps]\nsample = 0.05\n",
        encoding="utf-8",
    )
    destination: Path = tmp_path / "ARTIFACTS" / "steps.txt"
    with step_log(path=destination):
        trace(step="work: begin")
        sleep(0.4)
    lines: list[str] = _trace_lines(path=destination)
    samples: list[str] = [line for line in lines if "~sample " in line]
    expect_true(condition=bool(samples))
    for field in ("cpu=", "rss=", "threads=", "read=", "write="):
        expect_in(member=field, container=samples[0])
    expect_false(condition=any("@thread" in line for line in samples))


def test_sampling_is_off_without_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``[tool.steps] sample`` key means no resource lines.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    destination: Path = tmp_path / "steps.txt"
    with step_log(path=destination):
        trace(step="work: begin")
        sleep(0.2)
    expect_false(
        condition=any(
            "~sample" in line for line in _trace_lines(path=destination)
        ),
    )
