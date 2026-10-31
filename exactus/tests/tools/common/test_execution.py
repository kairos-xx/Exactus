# Copyright (c) 2026
"""The shared exactus execution wrapper, fallbacks, and crash recording."""

from __future__ import annotations

from json import dumps, loads
from os import environ, getppid
from pathlib import Path
from subprocess import run
from sys import executable
from threading import Event, Lock
from time import monotonic
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.packages.pmanager.runtime import Descriptor
from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
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
from exactus.tools.common.models import ToolRequest, ToolRunResult
from exactus.tools.common.registry import RunClaim, RunRecord, RunRegistry
from exactus.tools.common.stderr_capture import StderrRecorder

if TYPE_CHECKING:
    from collections.abc import Callable
    from subprocess import CompletedProcess

    from exactus.tools.common.execution import ExactusRunIds
    from exactus.tools.common.json_types import JsonValue


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["exactus", "--x"])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        progress_json: Grouped module constant.

    """

    progress_json: Final[str] = (
        '{"progress": 5, "completed": 2, "total": 3, "step": "s", "detail":'
        ' "d"}'
    )


def test_exited_dependent_is_reset_without_checkpoint_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exited streaming worker cannot stall a prerequisite forever.

    Args:
        tmp_path: Isolated registry and output root.
        monkeypatch: Replace process discovery and control calls.

    """
    record: RunRecord = RunRecord(
        kind="tool",
        identifier="kwargs_typehints",
        run_id="kwargs-run",
        pipeline_run_id="pipeline",
        pid=42,
        output=str(object=tmp_path / "KWARGS_TYPEHINTS"),
        targets=(),
        status="RUNNING",
        progress=0.0,
        step="starting",
        detail="",
        created_at="2026-10-12T00:00:00+00:00",
        updated_at="2026-10-12T00:00:00+00:00",
        elapsed_seconds=0.0,
    )
    descriptor: Descriptor = Descriptor(
        pid=41,
        port=9000,
        name="kwargs_typehints",
        context="workspace/pipeline",
        args=(),
    )
    commands: list[str] = []

    def dependents(
        *,
        registry: RunRegistry,
        analyzer: str,
        run_id: str,
    ) -> tuple[RunRecord, ...]:
        """Return the stale dependent regardless of query fields.

        Args:
            registry: Query registry.
            analyzer: Prerequisite analyzer.
            run_id: Prerequisite run identifier.

        Returns:
            One exited dependent represented by a stale live row.

        """
        _ = (registry, analyzer, run_id)
        return (record,)

    def descriptor_for(*, record: RunRecord) -> Descriptor:
        """Return the test descriptor.

        Args:
            record: Dependent registry row.

        Returns:
            Descriptor accepted by the fake client.

        """
        _ = record
        return descriptor

    def request(
        *,
        descriptor: Descriptor,
        command: str,
        payload: JsonValue = None,
    ) -> dict[str, JsonValue]:
        """Record control calls and report an exited worker.

        Args:
            descriptor: Target worker descriptor.
            command: Control command.
            payload: Optional command payload.

        Returns:
            Exited worker information for the info request.

        """
        _ = (descriptor, payload)
        commands.append(command)
        return (
            {"exit_code": 0, "custom_status": {}} if command == "info" else {}
        )

    monkeypatch.setattr(target=ent, name="_dependent_runs", value=dependents)
    monkeypatch.setattr(
        target=ent,
        name="_worker_descriptor",
        value=descriptor_for,
    )
    monkeypatch.setattr(target=ent.Client, name="request", value=request)
    context: object = private_call(
        owner=ent,
        name="_RunContext",
        output=tmp_path / "LINTS",
        analyzer="lints",
        started_at="",
        started=monotonic(),
        interrupted=Event(),
        stop=Event(),
        write_lock=Lock(),
        registry=RunRegistry(path=tmp_path / "runs.db"),
        run_id="lints-run",
        pipeline_run_id=None,
        previous_duration_seconds=None,
        log=ActivityLog(),
        stderr=StderrRecorder(),
    )
    private_call(owner=ent, name="_pause_live_dependents", context=context)
    expect_equal(actual=commands, expected=["event", "info", "reset"])


def _write_activity(
    *,
    output: Path,
    status: str,
    pid: int | None = None,
    run_id: str | None = None,
) -> None:
    """Publish one ``@activity.json`` document for a fake earlier run.

    Args:
        output: Report directory receiving ``ARTIFACTS/@activity.json``.
        status: Run status.
        pid: Owning process recorded in the heartbeat block.
        run_id: Run identifier.

    """
    ActivityFile.write(
        path=output / "ARTIFACTS" / "@activity.json",
        document=ActivityDocument(
            kind="tool",
            name="demo",
            status=status,
            run_id=run_id,
            heartbeat=ActivityHeartbeat(pid=pid, alive=status == "RUNNING"),
        ),
    )


def _progress_fields(*, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize a progress payload through the private helper.

    Args:
        payload: Raw progress payload.

    Returns:
        The normalized fields.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=private_call(owner=ent, name="_progress_fields", payload=payload),
    )


def _execute(
    main: Callable[[], int],
    out: Path,
    run_ids: ExactusRunIds | None = None,
) -> ToolRunResult:
    """Run ``main`` through the wrapper.

    Args:
        main: Analyzer callable.
        out: Report directory.
        run_ids: Optional injected run identifiers.

    Returns:
        The run result.

    """
    return ent.execute_exactus(
        analyzer="demo",
        title="Demo Exactus",
        main=main,
        output=out,
        run_ids=run_ids,
    )


def test_success_without_report_gets_fallback(tmp_path: Path) -> None:
    """A silent successful analyzer still produces a report bundle.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DEMO"
    result: ToolRunResult = _execute(main=lambda: 0, out=out)
    expect_true(condition=result.passed)
    expect_equal(actual=result.status, expected="PASS")
    expect_true(condition=(out / "result.md").is_file())
    expect_true(condition=(out / "result.json").is_file())
    for name in ("@activity.json", "stderr.log", "stdout.log"):
        expect_true(
            condition=(out / "ARTIFACTS" / name).is_file(),
            message=name,
        )
    expect_false(condition=(out / "ARTIFACTS" / "heartbeat.json").exists())


class FdStream:
    """Stream wrapper exposing a real process descriptor."""

    def __init__(self, descriptor: int) -> None:
        """Remember the descriptor.

        Args:
            descriptor: Process-level descriptor number.

        """
        self.descriptor = descriptor

    def fileno(self) -> int:
        """Return the descriptor.

        Returns:
            The wrapped descriptor.

        """
        return self.descriptor

    def flush(self) -> None:
        """Accept flushes."""


def test_output_streams_are_captured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stdout and stderr tails land in the fallback transcript logs.

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
    out: Path = tmp_path / "out"

    def noisy() -> int:
        """Print to both standard streams in a child process.

        Returns:
            Zero.

        """
        run(
            args=[
                executable,
                "-c",
                "import sys;print('OUT');print('ERR',file=sys.stderr)",
            ],
            check=True,
        )
        return 1

    result: ToolRunResult = _execute(main=noisy, out=out)
    expect_false(condition=result.passed)
    expect_in(
        member="OUT",
        container=(out / "ARTIFACTS" / "stdout.log").read_text(),
    )
    expect_in(
        member="ERR",
        container=(out / "ARTIFACTS" / "stderr.log").read_text(),
    )


@pytest.mark.parametrize(
    ("raiser", "status", "needle"),
    [
        (
            lambda: (_ for _ in ()).throw(ValueError("bad")),
            1,
            "ValueError: bad",
        ),
        (lambda: (_ for _ in ()).throw(KeyError("k")), 1, "KeyError"),
        (
            lambda: (_ for _ in ()).throw(ExceptionGroup("g", [OSError("x")])),
            1,
            "ExceptionGroup",
        ),
        (lambda: (_ for _ in ()).throw(SystemExit(3)), 3, "SystemExit: 3"),
        (
            lambda: (_ for _ in ()).throw(SystemExit("msg")),
            1,
            "SystemExit: msg",
        ),
        (lambda: (_ for _ in ()).throw(SystemExit(None)), 0, ""),
        (
            lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            130,
            "KeyboardInterrupt",
        ),
    ],
)
def test_exceptions_become_failed_reports(
    raiser: Callable[[], int],
    status: int,
    needle: str,
    tmp_path: Path,
) -> None:
    """Every kind of analyzer failure is reported rather than lost.

    Args:
        raiser: Value for ``raiser``.
        status: Value for ``status``.
        needle: Value for ``needle``.
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "out"
    result: ToolRunResult = _execute(main=raiser, out=out)
    expect_equal(actual=result.exit_code, expected=status)
    report: str = (out / "result.md").read_text(encoding="utf-8")
    expect_in(member=needle, container=report)


def test_analyzer_written_reports_are_kept(tmp_path: Path) -> None:
    """Reports written by the analyzer are stamped, not replaced.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "out"

    def analyzer() -> int:
        """Write report files the way an analyzer does.

        Returns:
            The analyzer exit status.

        """
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.md").write_text(data="# Mine\n\n- Status: **PASS**\n")
        (out / "result.json").write_text(data=dumps(obj={"title": "Mine"}))
        (out / "extra.json").write_text(data='{"k": 1}')
        (out / "note.txt").write_text(data="hello")
        (out / "result_web").mkdir()
        (out / "result_web" / "index.html").write_text(data="<html></html>")
        return 0

    result: ToolRunResult = _execute(main=analyzer, out=out)
    expect_true(condition=result.passed)
    expect_in(member="# Mine", container=(out / "result.md").read_text())
    payload: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(out / "result.json").read_text()),
    )
    expect_equal(actual=payload["status"], expected="PASS")
    expect_true(
        condition=(out / "ARTIFACTS" / "extra.json").is_file()
        or (out / "extra.json").is_file(),
    )


def test_web_data_payload_is_stamped(tmp_path: Path) -> None:
    """Analyzer-provided ``result_web/data.json`` gains run status fields.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "out"

    def analyzer() -> int:
        """Write report files the way an analyzer does.

        Returns:
            The analyzer exit status.

        """
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.md").write_text(data="# T\n\n- Status: **PASS**\n")
        (out / "result.json").write_text(data="{}")
        (out / "result_web").mkdir()
        (out / "result_web" / "data.json").write_text(
            data=dumps(obj={"title": "T"}),
        )
        return 0

    result: ToolRunResult = _execute(main=analyzer, out=out)
    expect_true(condition=result.passed)
    data: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(out / "result_web" / "data.json").read_text(encoding="utf-8"),
        ),
    )
    expect_equal(actual=data["status"], expected="PASS")
    expect_equal(actual=data["tool"], expected="demo")
    expect_true(condition="duration_seconds" in data)
    script: str = (out / "result_web" / "data.js").read_text(encoding="utf-8")
    expect_in(member="window.__REPORT_DATA__", container=script)
    expect_in(member='"status": "PASS"', container=script)


def test_failed_analyzer_stamps_existing_reports(tmp_path: Path) -> None:
    """A failing run overwrites status in analyzer-provided reports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "out"

    def analyzer() -> int:
        """Write report files, then fail.

        Returns:
            The analyzer exit status.

        """
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.md").write_text(data="# T\n\n- Status: **PASS**\n")
        (out / "result.json").write_text(data="{}")
        (out / "result_web").mkdir()
        (out / "result_web" / "index.html").write_text(
            data="<html><body>PASS</body></html>",
        )
        return 2

    result: ToolRunResult = _execute(main=analyzer, out=out)
    expect_equal(actual=result.exit_code, expected=2)
    expect_in(member="FAIL", container=(out / "result.md").read_text())


def test_terminal_summary_and_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without orchestration the wrapper prints its own summary.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Per-test temporary directory.

    """
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED")
    out: Path = tmp_path / "out"
    ids: ExactusRunIds = ent.ExactusRunIds(
        run_id="r" * 32,
        pipeline_run_id="p" * 32,
    )
    result: ToolRunResult = _execute(main=lambda: 0, out=out, run_ids=ids)
    expect_equal(actual=result.run_id, expected="r" * 32)
    expect_equal(actual=result.pipeline_run_id, expected="p" * 32)
    expect_none(value=environ.get("EXACTUS_TOOL"))


def test_run_exactus_returns_exit_code(tmp_path: Path) -> None:
    """``run_exactus`` reports the analyzer exit status.

    Args:
        tmp_path: Per-test temporary directory.

    """
    code: int = ent.run_exactus(analyzer="demo", title="Demo", main=lambda: 4)
    expect_equal(actual=code, expected=4)
    expect_true(
        condition=(
            tmp_path / "EXACTUS_RESULTS" / "DEMO" / "result.md"
        ).is_file(),
    )


def test_report_output_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--report-output`` is consumed from argv.

    Args:
        tmp_path: Isolated working directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=ent,
        name="argv",
        value=["c", "--report-output", "somewhere", "z"],
    )
    expect_equal(
        actual=private_call(owner=ent, name="_report_output", analyzer="x"),
        expected=Path("somewhere"),
    )
    expect_equal(actual=ent.argv, expected=["c", "z"])
    expect_equal(
        actual=private_call(
            owner=ent,
            name="_report_output",
            analyzer="my-tool",
        ),
        expected=tmp_path / "EXACTUS_RESULTS" / "MY_TOOL",
    )
    expect_equal(
        actual=private_call(
            owner=ent,
            name="_report_output",
            analyzer="lints",
        ),
        expected=tmp_path / "EXACTUS_RESULTS" / "LINTS",
    )
    expect_equal(
        actual=private_call(
            owner=ent,
            name="_report_output",
            analyzer="coverage_tests",
        ),
        expected=tmp_path / "EXACTUS_RESULTS" / "COVERAGE_TESTS",
    )
    monkeypatch.setattr(
        target=ent,
        name="argv",
        value=["c", "--report-output"],
    )
    with pytest.raises(expected_exception=ValueError, match="requires a path"):
        private_call(owner=ent, name="_report_output", analyzer="x")


def test_prepare_output_cleans_and_preserves(tmp_path: Path) -> None:
    """Old output is emptied; read-only trees are forced writable.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "O"
    nested: Path = out / "sub"
    nested.mkdir(parents=True)
    (nested / "f.txt").write_text(data="x")
    nested.chmod(mode=365)
    stale: Path = tmp_path / "O.preserved-old"
    stale.mkdir()
    private_call(owner=ent, name="_prepare_output", output=out, run_id="abc")
    expect_true(condition=out.exists())
    expect_true(condition=out.is_dir())
    expect_false(condition=(out / "sub").exists())
    expect_false(condition=stale.exists())
    private_call(owner=ent, name="_prepare_output", output=out, run_id="abc")
    expect_true(condition=out.exists())
    expect_true(condition=out.is_dir())
    link_target: Path = tmp_path / "t"
    link_target.write_text(data="x")
    link: Path = tmp_path / "L"
    link.symlink_to(target=link_target)
    private_call(owner=ent, name="_prepare_output", output=link, run_id="abc")
    expect_false(condition=link.exists())
    plain_file: Path = tmp_path / "F"
    plain_file.write_text(data="x")
    private_call(
        owner=ent,
        name="_prepare_output",
        output=plain_file,
        run_id="abc",
    )
    expect_false(condition=plain_file.exists())


def test_prepare_output_moves_aside_when_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An undeletable child forces the directory aside with a preserved name.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    out: Path = tmp_path / "O"
    out.mkdir()
    (out / "child_dir").mkdir()

    def refuse(*, path: Path) -> None:
        """Refuse to remove the directory.

        Args:
            path: Directory the caller tried to remove.

        Raises:
            OSError: Always.

        """
        raise OSError(str(object=path))

    monkeypatch.setattr(target=ent, name="_remove_tree", value=refuse)
    private_call(owner=ent, name="_prepare_output", output=out, run_id="abc")
    expect_true(condition=(tmp_path / "O.preserved-abc").is_dir())
    (tmp_path / "O2").mkdir()
    first: Path = require_type(
        value=private_call(
            owner=ent,
            name="_preserved_output",
            output=tmp_path / "O",
            run_id="abc",
        ),
        kind=Path,
    )
    expect_equal(actual=first.name, expected="O.preserved-abc-2")


def test_progress_helpers() -> None:
    """Progress payloads are normalized defensively."""
    fields: dict[str, JsonValue] = _progress_fields(
        payload=cast(
            typ="dict[str, JsonValue]",
            val=loads(s=Constants.progress_json),
        ),
    )
    expect_equal(actual=fields["progress"], expected=1.0)
    expect_equal(actual=fields["completed"], expected=2)
    odd: dict[str, JsonValue] = _progress_fields(
        payload={"progress": True, "completed": "x", "total": None, "step": 1},
    )
    expect_equal(
        actual=odd,
        expected={
            "progress": 0.0,
            "completed": 0,
            "total": 0,
            "step": "running",
            "detail": "",
        },
    )


def test_report_snapshot_and_emitted(tmp_path: Path) -> None:
    """Only new or rewritten md and json pairs count as emitted.

    Args:
        tmp_path: Per-test temporary directory.

    """
    before: dict[Path, tuple[int, int]] = cast(
        typ="dict[Path, tuple[int, int]]",
        val=private_call(owner=ent, name="_report_snapshot", output=tmp_path),
    )
    (tmp_path / "@activity.json").write_text(data="{}")
    (tmp_path / "a.md").write_text(data="x")
    expect_false(
        condition=bool(
            private_call(
                owner=ent,
                name="_report_emitted",
                output=tmp_path,
                before=before,
            ),
        ),
    )
    (tmp_path / "a.json").write_text(data="{}")
    expect_true(
        condition=bool(
            private_call(
                owner=ent,
                name="_report_emitted",
                output=tmp_path,
                before=before,
            ),
        ),
    )


def test_terminate_live_run_ignores_missing_or_finished(
    tmp_path: Path,
) -> None:
    """Only RUNNING activity documents with integer pids are acted upon.

    Args:
        tmp_path: Per-test temporary directory.

    """
    private_call(owner=ent, name="_terminate_live_run", output=tmp_path)
    _write_activity(output=tmp_path, status="DONE", pid=1)
    private_call(owner=ent, name="_terminate_live_run", output=tmp_path)
    _write_activity(output=tmp_path, status="RUNNING")
    private_call(owner=ent, name="_terminate_live_run", output=tmp_path)
    pulse: Path = tmp_path / "ARTIFACTS" / "@activity.json"
    for payload in (
        {"status": "RUNNING", "heartbeat": {"pid": True}},
        {"status": "RUNNING", "pid": 1},
    ):
        pulse.write_text(data=dumps(obj=payload))
        private_call(owner=ent, name="_terminate_live_run", output=tmp_path)


def test_conflicting_run_is_terminated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live runs conflicting on the output directory are terminated.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    killed: list[int] = []

    def record_kill(*, pid: int, replaced: bool) -> None:
        """Record a terminate request instead of killing anything.

        Args:
            pid: Process id that would have been terminated.
            replaced: Whether another exactus claimed the output.

        """
        expect_true(condition=replaced)
        killed.append(pid)

    monkeypatch.setattr(target=ent, name="terminate_tree", value=record_kill)
    out: Path = tmp_path / "out"
    first: RunRegistry = RunRegistry.for_output(output=out)
    expect_equal(
        actual=first.claim(
            request=RunClaim(
                kind="tool",
                identifier="demo",
                run_id="b" * 32,
                pipeline_run_id=None,
                pid=getppid(),
                output=out,
                targets=(str(object=out.resolve()),),
            ),
        ),
        expected=(),
    )
    _ = private_call(
        owner=ent,
        name="_claim_run",
        analyzer="demo",
        output=out,
        run_id="a" * 32,
        pipeline_run_id=None,
    )
    expect_equal(actual=killed, expected=[getppid()])


def test_registry_unavailable_falls_back_to_activity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a registry ``@activity.json`` names the process to stop.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    killed: list[int] = []

    def record_kill(*, pid: int, replaced: bool) -> None:
        """Record a terminate request instead of killing anything.

        Args:
            pid: Process id that would have been terminated.
            replaced: Whether another exactus claimed the output.

        """
        expect_true(condition=replaced)
        killed.append(pid)

    monkeypatch.setattr(target=ent, name="terminate_tree", value=record_kill)
    blocker: Path = tmp_path / "blocker"
    blocker.write_text(data="x")
    monkeypatch.setenv(
        name="EXACTUS_REGISTRY",
        value=str(object=blocker / "runs.db"),
    )
    out: Path = tmp_path / "out"
    _write_activity(output=out, status="RUNNING", pid=4242)
    _ = private_call(
        owner=ent,
        name="_claim_run",
        analyzer="demo",
        output=out,
        run_id="a" * 32,
        pipeline_run_id=None,
    )
    expect_equal(actual=killed, expected=[4242])


def test_fallback_markdown_truncates_and_lists(tmp_path: Path) -> None:
    """Fallback reports include errors, tails and artifacts.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "out"
    (out / "sub").mkdir(parents=True)
    (out / "sub" / "data.json").write_text(data='{"a": 1}')
    (out / "sub" / "bad.json").write_text(data="{bad")
    (out / ".hidden").write_text(data="x")
    artifacts: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(
            owner=ent,
            name="_report_artifacts",
            output=out,
            stem="result",
        ),
    )
    expect_equal(
        actual=[item["name"] for item in artifacts],
        expected=["bad.json", "data.json"],
    )
    private_call(
        owner=ent,
        name="_write_fallback_report",
        result=ent.FallbackResult(
            output=out,
            analyzer="demo",
            title="Demo",
            status=1,
            command="cmd",
            elapsed_seconds=1.0,
            stdout_tail="o" * 100,
            stderr_tail="e",
            error="boom",
        ),
    )
    text: str = (out / "result.md").read_text()
    expect_in(member="boom", container=text)
    expect_in(member="data.json", container=text)


def test_stream_capture_failure_is_tolerated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streams without descriptors are simply not captured.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """

    class NoFd:
        """Stream lacking a file descriptor."""

        @staticmethod
        def fileno() -> int:
            """Fail like an in-memory stream.

            Raises:
                OSError: Always.

            """
            raise OSError

        def flush(self) -> None:
            """Accept flushes."""

    monkeypatch.setattr(target=ent, name="stdout", value=NoFd())
    tees: object = private_call(
        owner=ent,
        name="_capture_streams",
        output=tmp_path,
    )
    expect_equal(actual=tees, expected=())
    expect_equal(
        actual=private_call(owner=ent, name="_stop_streams", tees=tees),
        expected=("", ""),
    )


def test_crashed_exactus_records_failure(tmp_path: Path) -> None:
    """A dead worker still yields a report and failed result.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DEMO"
    request: ToolRequest = ToolRequest(
        identifier="demo",
        output=out,
        arguments=(),
        run_id="c" * 32,
        project_root=tmp_path,
    )
    result: ToolRunResult = ent.crashed_exactus(
        request=request,
        title="Demo",
        crash=ent.CrashDetails(pid=99999, exit_code=1, elapsed_seconds=0.5),
    )
    expect_false(condition=result.passed)
    expect_in(member="exited before reporting", container=result.resume)
    expect_true(condition=(out / "result.md").is_file())
    interrupted: ToolRunResult = ent.crashed_exactus(
        request=request,
        title="Demo",
        crash=ent.CrashDetails(pid=None, exit_code=-15, elapsed_seconds=0.5),
    )
    expect_equal(actual=interrupted.status, expected="INTERRUPT")


def test_crashed_exactus_respects_reclaimed_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a newer run owns the directory nothing is rewritten.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    out: Path = tmp_path / "O"
    request: ToolRequest = ToolRequest(
        identifier="demo",
        output=out,
        arguments=(),
        run_id="d" * 32,
        project_root=tmp_path,
    )
    monkeypatch.setattr(
        target=ent,
        name="_output_reclaimed",
        value=Constant(value=True),
    )
    result: ToolRunResult = ent.crashed_exactus(
        request=request,
        title="Demo",
        crash=ent.CrashDetails(pid=1, exit_code=0, elapsed_seconds=0.1),
    )
    expect_equal(actual=result.exit_code, expected=1)
    expect_false(condition=out.exists())


def test_output_reclaimed_detection(tmp_path: Path) -> None:
    """Activity documents of other runs mark the directory as reclaimed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "O"
    expect_false(
        condition=bool(
            private_call(
                owner=ent,
                name="_output_reclaimed",
                output=out,
                run_id="a",
            ),
        ),
    )
    _write_activity(output=out, status="RUNNING", run_id="b")
    expect_true(
        condition=bool(
            private_call(
                owner=ent,
                name="_output_reclaimed",
                output=out,
                run_id="a",
            ),
        ),
    )
    expect_false(
        condition=bool(
            private_call(
                owner=ent,
                name="_output_reclaimed",
                output=out,
                run_id="b",
            ),
        ),
    )


def test_signal_during_run_records_interrupt(tmp_path: Path) -> None:
    """SIGTERM mid-run leaves an INTERRUPT activity and kills the run.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = Path(__file__).resolve().parents[4]
    # A stale replacement marker left behind by an earlier terminated run
    # (``exactus-replaced-<pid>.json`` survives PID reuse) would make the
    # signal handler exit before recording INTERRUPT, so the subprocess
    # drops any marker addressed to its own PID before running.
    script: str = (
        f"import os, signal, sys\nsys.path[:0] = [{str(object=root)!r}]\n"
        "import pathlib, tempfile\n"
        "marker = pathlib.Path(tempfile.gettempdir()) /"
        " f'exactus-replaced-{os.getpid()}.json'\n"
        "marker.unlink(missing_ok=True)\n"
        "from exactus.tools.common.execution import execute_exactus\ndef"
        " main():\n    os.kill(os.getpid(), signal.SIGTERM)\n    import time;"
        " time.sleep(30)\n    return 0\nexecute_exactus(analyzer='sig',"
        " title='Sig', main=main)\n"
    )
    # Inside a pipeline or tool run the ambient ``EXACTUS_*`` variables point
    # at the live shared registry; the child must not inherit them or its
    # ``execute_exactus`` run would claim another run's identity and be
    # subject to external kill/replacement during startup.
    child_env: dict[str, str] = {
        key: value
        for key, value in environ.items()
        if not key.startswith("EXACTUS_")
    }
    child_env["EXACTUS_ORCHESTRATED"] = "1"
    done: CompletedProcess[bytes] = run(
        args=[executable, "-c", script],
        cwd=tmp_path,
        env=child_env,
        check=False,
        capture_output=True,
        timeout=60,
    )
    expect_not_equal(actual=done.returncode, expected=0)
    pulse: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(
                tmp_path
                / "EXACTUS_RESULTS"
                / "SIG"
                / "ARTIFACTS"
                / "@activity.json"
            ).read_text(),
        ),
    )
    expect_equal(actual=pulse["status"], expected="INTERRUPT")
    heartbeat: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=require_type(value=pulse["heartbeat"], kind=dict),
    )
    expect_equal(
        actual=(heartbeat["alive"], heartbeat["phase"]),
        expected=(False, "interrupted"),
    )


def test_previous_duration_propagates_to_reports_and_activity(
    tmp_path: Path,
) -> None:
    """A second run records the first run's duration everywhere visible.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DEMO"

    def analyzer() -> int:
        """Write report files the way a legacy analyzer does.

        Returns:
            The analyzer exit status.

        """
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.md").write_text(data="# T\n")
        (out / "result.json").write_text(data=dumps(obj={"title": "T"}))
        (out / "result_web").mkdir(exist_ok=True)
        (out / "result_web" / "data.json").write_text(
            data=dumps(obj={"title": "T"}),
        )
        return 0

    first: ToolRunResult = _execute(main=analyzer, out=out)
    expect_true(condition=first.passed)
    result: ToolRunResult = _execute(main=analyzer, out=out)
    expect_true(condition=result.passed)
    payload: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(out / "result.json").read_text()),
    )
    previous_duration: float = round(number=first.duration_seconds, ndigits=3)
    expect_equal(
        actual=payload["previous_duration_seconds"],
        expected=previous_duration,
    )
    web: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(out / "result_web" / "data.json").read_text(encoding="utf-8"),
        ),
    )
    expect_equal(
        actual=web["previous_duration_seconds"],
        expected=previous_duration,
    )
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_in(
        member=f"- Previous run: **{previous_duration:.3f}s**",
        container=markdown,
    )
    activity_document: ActivityDocument | None = ActivityFile.read(
        path=out / "ARTIFACTS" / "@activity.json",
    )
    expect_true(condition=activity_document is not None)
    if activity_document is not None:
        expect_equal(
            actual=activity_document.extra.get("previous_duration_seconds"),
            expected=previous_duration,
        )


def test_help_preserves_existing_exactus_evidence(tmp_path: Path) -> None:
    """Keep saved failures intact when a tool only displays CLI help.

    Args:
        tmp_path: Isolated report root and working directory.

    """
    output: Path = tmp_path / "FRONTEND"
    output.mkdir()
    report: Path = output / "result.json"
    evidence: bytes = b'{"status":"FAIL","findings":[{"rule":"SCR001"}]}\n'
    _ = report.write_bytes(data=evidence)
    script: Path = (
        Path(__file__).resolve().parents[4] / "exactus/tools/frontend/main.py"
    )
    result: CompletedProcess[str] = run(
        args=[
            executable,
            str(object=script),
            "--help",
            "--report-output",
            str(object=output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=result.returncode, expected=0)
    expect_in(member="--workspace", container=result.stdout)
    expect_equal(actual=report.read_bytes(), expected=evidence)
    expect_false(condition=(output / "ARTIFACTS").exists())
