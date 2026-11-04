# Copyright (c) 2026
"""Exercise the prepared event channel before modifying live source."""

from __future__ import annotations

from json import dumps, loads
from pathlib import Path
from sys import executable
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.coverage_tests import progress_plugin
from exactus.tools.coverage_tests.core import CombinedCoverageRunner
from exactus.tools.coverage_tests.event_stream import EventLimits, ShardEvents
from exactus.tools.coverage_tests.progress_plugin import ProgressEvents

if TYPE_CHECKING:
    from subprocess import CompletedProcess

    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.main import Session
    from _pytest.reports import TestReport

    from exactus.tools.common.json_types import JsonValue


def write_event(path: Path, **fields: object) -> None:
    """Append a fixture event.

    Args:
        path: Events output path.
        **fields: JSON fixture record fields.

    """
    with path.open(mode="a", encoding="utf-8") as stream:
        _ = stream.write(
            dumps(obj={"version": 1, **fields})
            + """\

""",
        )


def test_finished_follows_teardown(tmp_path: Path) -> None:
    """A call report alone does not count completion.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    path: Path = tmp_path / "events.jsonl"
    reader: ShardEvents = ShardEvents(path=path)
    write_event(path=path, event="collected", count=2)
    write_event(path=path, event="started", nodeid="test_a.py::test_\u03b1")
    write_event(
        path=path,
        event="report",
        nodeid="test_a.py::test_\u03b1",
        when="call",
        outcome="passed",
    )
    reader.poll()
    expect_true(condition=reader.fraction() == 0)
    expect_true(condition=reader.current == "test_a.py::test_\u03b1")
    write_event(path=path, event="finished", nodeid=reader.current)
    write_event(path=path, event="finished", nodeid=reader.current)
    reader.poll()
    expect_equal(actual=reader.fraction(), expected=0.5)
    expect_true(condition=len(reader.completed) == 1)


def test_partial_record_and_utf8(tmp_path: Path) -> None:
    """Bytes split inside a unicode nodeid survive polling.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    path: Path = tmp_path / "events.jsonl"
    payload: bytes = (
        dumps(
            obj={"version": 1, "event": "started", "nodeid": "test_\u03b1"},
            ensure_ascii=False,
        )
        + """\

"""
    ).encode()
    split: int = payload.index("\u03b1".encode()) + 1
    path.write_bytes(data=payload[:split])
    reader: ShardEvents = ShardEvents(path=path)
    reader.poll()
    expect_true(condition=reader.current == "")
    with path.open(mode="ab") as stream:
        stream.write(payload[split:])
    reader.poll()
    expect_true(condition=reader.current == "test_\u03b1")


@pytest.mark.parametrize("count", [None, True, -1, "2", EventLimits.tests + 1])
def test_invalid_collection_counts(tmp_path: Path, count: object) -> None:
    """Malformed totals never become usable progress.

    Args:
        tmp_path: Isolated event sidecar directory.
        count: Malformed collection count fixture.

    """
    path: Path = tmp_path / "events.jsonl"
    write_event(path=path, event="collected", count=count)
    reader: ShardEvents = ShardEvents(path=path)
    reader.poll()
    expect_true(condition=reader.fraction() is None)


def test_missing_corrupt_and_truncated_files(tmp_path: Path) -> None:
    """Missing, malformed and reset sidecars do not fail a test run.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    path: Path = tmp_path / "events.jsonl"
    reader: ShardEvents = ShardEvents(path=path)
    reader.poll()
    path.write_bytes(
        data=b'not json\n[]\n{"event":"collected"}\n{"version":'
        + b"9" * 5000
        + b"}\n",
    )
    reader.poll()
    expect_true(condition=reader.fraction() is None)
    path.write_bytes(data=b"")
    reader.poll()
    expect_true(condition=reader.disabled)


def test_reader_bounds_partial_line(tmp_path: Path) -> None:
    """A malformed oversized partial line disables optional telemetry.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    path: Path = tmp_path / "events.jsonl"
    path.write_bytes(data=b"x" * (EventLimits.line_bytes + 1))
    reader: ShardEvents = ShardEvents(path=path)
    reader.poll()
    expect_true(condition=reader.disabled)


def test_writer_io_failure_is_optional(tmp_path: Path) -> None:
    """The plugin suppresses missing-parent and permission errors.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    writer: ProgressEvents = ProgressEvents(
        output=tmp_path / "missing" / "events.jsonl",
    )
    writer.pytest_runtest_logstart(
        nodeid="test_a",
        location=("test_a.py", 1, "test_a"),
    )
    writer.pytest_runtest_logfinish(
        nodeid="test_a",
        location=("test_a.py", 1, "test_a"),
    )


def test_real_pytest_plugin_protocol(tmp_path: Path) -> None:
    """Real pytest emits finished events for skips and teardown errors.

    Args:
        tmp_path: Isolated event sidecar directory.

    """
    source: Path = tmp_path / "test_fixture.py"
    source.write_text(
        data="""\
import pytest
from pathlib import Path
@pytest.fixture
def broken():
    raise RuntimeError("setup")
@pytest.fixture
def teardown_error():
    yield
    raise RuntimeError("teardown")
def test_pass(): pass
def test_patched_path_open(monkeypatch):
    def refuse(self, mode):
        raise PermissionError("fixture denies Path.open")
    monkeypatch.setattr(Path, "open", refuse)
@pytest.mark.skip(reason="fixture")
def test_skip(): pass
def test_setup(broken): pass
def test_teardown(teardown_error): pass
@pytest.mark.xfail(reason="fixture")
def test_xfail(): assert False
""",
        encoding="utf-8",
    )
    events: Path = tmp_path / "events.jsonl"
    plugin: Path = (
        Path(__file__).parents[3]
        / "tools"
        / "coverage_tests"
        / "progress_plugin.py"
    )
    destination: Path = tmp_path / "exactus_progress_plugin.py"
    destination.write_bytes(data=plugin.read_bytes())
    result: CompletedProcess[bytes] = CombinedCoverageRunner.execute(
        arguments=(
            "-m",
            "pytest",
            "-p",
            "exactus_progress_plugin",
            "--exactus-events",
            str(object=events),
            str(object=source),
            "-q",
        ),
        cwd=tmp_path,
        program=executable,
    )
    expect_true(
        condition=result.returncode == 1,
        message=str(object=result.stderr.decode()),
    )
    reader: ShardEvents = ShardEvents(path=events)
    reader.poll()
    expect_equal(actual=reader.total, expected=6)
    expect_equal(actual=len(reader.completed), expected=6)
    expect_true(condition=reader.fraction() == 1)
    records: list[dict[str, JsonValue]] = [
        loads(s=line) for line in events.read_text().splitlines()
    ]
    for nodeid in reader.completed:
        selected: list[dict[str, JsonValue]] = [
            record for record in records if record.get("nodeid") == nodeid
        ]
        expect_true(condition=selected[0]["event"] == "started")
        expect_true(condition=selected[-1]["event"] == "finished")


def test_plugin_original_hooks(tmp_path: Path) -> None:
    """Exercise original plugin hooks and their session ownership.

    Args:
        tmp_path: Isolated plugin event destination.

    """
    path: Path = tmp_path / "events"
    options: list[str] = []
    registered: list[ProgressEvents] = []

    def addoption(name: str, **settings: object) -> None:
        """Capture the option contract.

        Args:
            name: Option spelling.
            **settings: Parser action, default, and description.

        """
        expect_equal(actual=settings.get("action"), expected="store")
        expect_equal(actual=settings.get("default"), expected=None)
        expect_true(condition=bool(settings.get("help")))
        options.append(name)

    def getoption(name: str) -> str:
        """Return the configured sidecar.

        Args:
            name: Requested option.

        Returns:
            Sidecar path.

        """
        expect_equal(actual=name, expected="--exactus-events")
        return str(object=path)

    def register(*, plugin: ProgressEvents, name: str) -> None:
        """Capture the session-owned instance.

        Args:
            plugin: Writer instance.
            name: Registration identity.

        """
        expect_equal(actual=name, expected="exactus-progress-events")
        registered.append(plugin)

    progress_plugin.pytest_addoption(
        parser=cast(typ="Parser", val=SimpleNamespace(addoption=addoption)),
    )
    progress_plugin.pytest_configure(
        config=cast(
            typ="Config",
            val=SimpleNamespace(
                getoption=getoption,
                pluginmanager=SimpleNamespace(register=register),
            ),
        ),
    )
    writer: ProgressEvents = registered[0]
    writer.pytest_collection_finish(
        session=cast(typ="Session", val=SimpleNamespace(items=[object()])),
    )
    writer.pytest_runtest_logstart(
        nodeid="test_fixture",
        location=("test.py", 1, "test_fixture"),
    )
    writer.pytest_runtest_logreport(
        report=cast(
            typ="TestReport",
            val=SimpleNamespace(
                nodeid="test_fixture",
                when="setup",
                outcome="skipped",
            ),
        ),
    )
    writer.pytest_runtest_logfinish(
        nodeid="test_fixture",
        location=("test.py", 1, "test_fixture"),
    )
    reader: ShardEvents = ShardEvents(path=path)
    reader.drain()
    expect_equal(actual=reader.fraction(), expected=1.0)
    expect_equal(
        actual=options,
        expected=["--exactus-events", "--exactus-events-total"],
    )
