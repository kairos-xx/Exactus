# Copyright (c) 2026
"""Every tool run leaves ``@activity.json``, ``stderr.log``/``stdout.log``."""

from __future__ import annotations

from json import loads
from os import write
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    private_call,
    require_type,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityFile,
    ActivityHeartbeat,
    ActivityLog,
)
from exactus.tools.common.models import ToolRequest
from exactus.tools.common.runtime import emit_progress

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["exactus"])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


class FdStream:
    """Stream stand-in exposing a real process descriptor."""

    def __init__(self, *, descriptor: int) -> None:
        """Remember the descriptor.

        Args:
            descriptor: Process-level descriptor number.

        """
        self.descriptor: int = descriptor

    def fileno(self) -> int:
        """Return the descriptor.

        Returns:
            The wrapped descriptor.

        """
        return self.descriptor

    def flush(self) -> None:
        """Accept flushes."""


class NoFdStream:
    """Stream stand-in without a descriptor, like an in-memory stream."""

    @staticmethod
    def fileno() -> NoReturn:
        """Fail like an in-memory stream.

        Raises:
            OSError: Always.

        """
        raise OSError

    def flush(self) -> None:
        """Accept flushes."""


def _json(*, path: Path) -> dict[str, JsonValue]:
    """Decode one JSON object file.

    Args:
        path: File to read.

    Returns:
        The decoded object.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=require_type(
            value=loads(s=path.read_text(encoding="utf-8")),
            kind=dict,
        ),
    )


def _messages(*, document: ActivityDocument) -> list[str]:
    """List the event messages of an activity document.

    Args:
        document: Decoded activity document.

    Returns:
        Event messages, oldest first.

    """
    return [event.message for event in document.events]


def _noisy() -> int:
    """Report progress and write two lines to descriptor 2.

    Returns:
        Exit status ``1``.

    """
    emit_progress(
        state="RUNNING",
        completed=1,
        total=2,
        step="scan",
        detail="pkg",
    )
    _ = write(2, b"warning: odd\nerror: broken\n")
    return 1


def test_tool_run_writes_the_three_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run publishes the activity and the raw stderr/stdout transcripts.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=ent,
        name="stdout",
        value=FdStream(descriptor=1),
    )
    monkeypatch.setattr(
        target=ent,
        name="stderr",
        value=FdStream(descriptor=2),
    )
    out: Path = tmp_path / "EXACTUS_RESULTS" / "LINTS"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=_noisy,
        output=out,
    )
    expect_false(condition=result.passed)
    artifacts: Path = out / "ARTIFACTS"
    expect_equal(
        actual=sorted(path.name for path in artifacts.iterdir()),
        expected=["@activity.json", "README.md", "stderr.log", "stdout.log"],
    )
    document: ActivityDocument = require_type(
        value=ActivityFile.read(path=artifacts / "@activity.json"),
        kind=ActivityDocument,
    )
    expect_equal(actual=document.kind, expected="tool")
    expect_equal(actual=document.status, expected="FAIL")
    expect_equal(actual=document.run_id, expected=result.run_id)
    expect_false(condition=document.heartbeat.alive)
    expect_equal(actual=document.heartbeat.phase, expected="finished")
    expect_equal(actual=document.extra, expected={"exit_code": 1})
    expect_equal(actual=document.progress.step, expected="complete")
    messages: list[str] = _messages(document=document)
    expect_equal(actual=messages[0], expected="started: Lints Exactus")
    expect_in(
        member="stderr: 2 lines, 1 error and 1 warning lines",
        container=messages,
    )
    expect_in(member="finished: FAIL (exit status 1)", container=messages[-1])
    expect_equal(
        actual=(artifacts / "stderr.log").read_bytes(),
        expected=b"warning: odd\nerror: broken\n",
    )
    expect_false(condition=(artifacts / "stderr.json").exists())
    listed: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=require_type(
            value=_json(path=out / "result.json")["artifacts"],
            kind=list,
        ),
    )
    expect_equal(
        actual=[
            cast(typ="dict[str, JsonValue]", val=row)["path"] for row in listed
        ],
        expected=[
            "ARTIFACTS/@activity.json",
            "ARTIFACTS/README.md",
            "ARTIFACTS/stderr.log",
            "ARTIFACTS/stdout.log",
        ],
    )


def test_uncaptured_streams_still_get_stderr_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without descriptors the run writes an empty, uncaptured stderr.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=ent, name="stdout", value=NoFdStream())
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DEMO"
    _ = ent.execute_exactus(
        analyzer="demo",
        title="Demo",
        main=_noisy,
        output=out,
    )
    expect_equal(
        actual=(out / "ARTIFACTS" / "stderr.log").read_bytes(),
        expected=b"",
    )
    expect_false(condition=(out / "ARTIFACTS" / "stderr.json").exists())


def test_crash_finalizes_activity_and_stderr(tmp_path: Path) -> None:
    """A dead worker's activity keeps its events and ends ``crashed``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DEMO"
    log: ActivityLog = ActivityLog()
    log.record(message="started: Demo")
    ActivityFile.write(
        path=out / "ARTIFACTS" / "@activity.json",
        document=ActivityDocument(
            kind="tool",
            name="demo",
            status="RUNNING",
            run_id="e" * 32,
            started_at="2026-10-03T10:00:00+00:00",
            heartbeat=ActivityHeartbeat(
                pid=31337,
                alive=True,
                last_beat="2026-10-03T10:00:02+00:00",
                phase="running",
            ),
            events=log.events(),
        ),
    )
    _ = (out / "stderr.log").write_text(data="Fatal Python error: boom\n")
    _ = ent.crashed_exactus(
        request=ToolRequest(
            identifier="demo",
            output=out,
            arguments=(),
            run_id="e" * 32,
            project_root=tmp_path,
        ),
        title="Demo",
        crash=ent.CrashDetails(pid=31337, exit_code=-9, elapsed_seconds=2.5),
    )
    document: ActivityDocument = require_type(
        value=ActivityFile.read(path=out / "ARTIFACTS" / "@activity.json"),
        kind=ActivityDocument,
    )
    expect_equal(actual=document.status, expected="INTERRUPT")
    expect_equal(
        actual=document.heartbeat,
        expected=ActivityHeartbeat(
            pid=31337,
            alive=False,
            last_beat="2026-10-03T10:00:02+00:00",
            phase="crashed",
        ),
    )
    expect_equal(
        actual=document.started_at,
        expected="2026-10-03T10:00:00+00:00",
    )
    expect_equal(
        actual=_messages(document=document),
        expected=[
            "started: Demo",
            "the worker process ended before reporting (exit code -9)",
        ],
    )
    expect_true(condition=(out / "ARTIFACTS" / "stderr.log").is_file())
    expect_false(condition=(out / "ARTIFACTS" / "stderr.json").exists())
    expect_false(condition=(out / "ARTIFACTS" / "heartbeat.json").exists())


def test_nested_reports_stay_out_of_artifacts(tmp_path: Path) -> None:
    """A subdirectory holding ``result.md`` is a report, not evidence.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "COVERAGE_TESTS"
    (out / "COVERAGE").mkdir(parents=True)
    _ = (out / "COVERAGE" / "result.md").write_text(data="# Coverage\n")
    (out / "scratch").mkdir()
    _ = (out / "raw.json").write_text(data="{}\n")
    _ = private_call(
        owner=ent,
        name="_organize_artifacts",
        analyzer="coverage_tests",
        output=out,
    )
    expect_equal(
        actual=sorted(path.name for path in out.iterdir()),
        expected=["ARTIFACTS", "COVERAGE"],
    )
    expect_equal(
        actual=sorted(path.name for path in (out / "ARTIFACTS").iterdir()),
        expected=["raw.json", "scratch"],
    )
