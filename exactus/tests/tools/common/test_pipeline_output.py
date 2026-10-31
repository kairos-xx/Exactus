# Copyright (c) 2026
"""Pipeline output lives under ``EXACTUS_RESULTS/PIPELINES/``."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import replace
from importlib import import_module
from json import dumps, loads
from os import getpid, kill
from pathlib import Path
from signal import SIGCONT
from subprocess import Popen, check_output
from threading import Event, Lock, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.__main__ import Check
from exactus.packages.pmanager.runtime import Descriptor, Discovery
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    private,
    private_call,
    require_type,
)
from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityFile,
    ActivityHeartbeat,
    ActivityLog,
    ActivityProgress,
)
from exactus.tools.common.catalog import Constants, ToolSpec
from exactus.tools.common.models import ToolActivity, ToolRunResult
from exactus.tools.common.pipeline_supervisor import PipelineCoordinator
from exactus.tools.common.registry import RunClaim, RunRecord, RunRegistry
from exactus.tools.common.stderr_capture import StderrRecorder
from exactus.tools.common.terminal import ExactusTerminal

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.tools.common.json_types import JsonValue


@pytest.fixture
def results_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the orchestrator at a throwaway ``EXACTUS_RESULTS`` tree.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    Returns:
        The temporary ``EXACTUS_RESULTS`` directory.

    """
    exactus_root: Path = tmp_path / "EXACTUS_RESULTS"
    monkeypatch.setattr(target=Check, name="root", value=tmp_path)
    monkeypatch.setattr(target=Check, name="exactus_root", value=exactus_root)
    monkeypatch.delenv(name="EXACTUS_REGISTRY", raising=False)
    return exactus_root


def _path(*, name: str, **arguments: object) -> Path:
    """Call one path-returning private ``Check`` helper.

    Args:
        name: Helper name.
        **arguments: Keyword arguments of the helper.

    Returns:
        The returned path.

    """
    return require_type(
        value=private_call(owner=Check, name=name, **arguments),
        kind=Path,
    )


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


def _lints() -> ToolSpec:
    """Return the ``lints`` tool specification.

    Returns:
        The catalog entry.

    """
    return require_type(
        value=Constants.exactus_catalog.tool(identifier="lints"),
        kind=ToolSpec,
    )


def _claim_owner_run_id() -> str:
    """Claim the test pipeline and return its owner run identity.

    Returns:
        Newly claimed owner run identifier.

    """
    claim: object = private_call(
        owner=Check,
        name="_claim_pipeline",
        pipeline="self",
    )
    expect_true(condition=bool(private(owner=claim, name="owner")))
    return require_type(value=private(owner=claim, name="run_id"), kind=str)


def _positive_pid(*, pid: int) -> bool:
    """Treat positive fake process identifiers as live.

    Args:
        pid: Process identifier under test.

    Returns:
        Whether the identifier is positive.

    """
    return pid > 0


def test_pipeline_paths(results_root: Path) -> None:
    """Reports, activity and the ownership record move under PIPELINES.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    pipelines: Path = results_root / "PIPELINES"
    expect_equal(
        actual=_path(name="_pipeline_output", pipeline="all-fast"),
        expected=pipelines / "ALL_FAST",
    )
    expect_equal(
        actual=_path(name="_activity_path", pipeline="unified"),
        expected=pipelines / "UNIFIED" / "ARTIFACTS" / "@activity.json",
    )
    expect_equal(
        actual=_path(name="_owner_path", pipeline="self"),
        expected=pipelines / "SELF" / "ARTIFACTS" / "owner.json",
    )
    clear_target: Callable[..., Path | None] = cast(
        typ="Callable[..., Path | None]",
        val=private(owner=Check, name="_clear_target"),
    )
    expect_equal(
        actual=clear_target(name="unified"),
        expected=pipelines / "UNIFIED",
    )


def test_legacy_pipeline_output_is_removed(results_root: Path) -> None:
    """Only an old pipeline report directory is deleted, never a tool's.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    legacy: Path = results_root / "UNIFIED"
    legacy.mkdir(parents=True)
    _ = (legacy / "result.json").write_text(
        data=dumps(obj={"kind": "pipeline"}),
    )
    other: Path = results_root / "SELF"
    other.mkdir()
    _ = (other / "result.json").write_text(data=dumps(obj={"kind": "tool"}))
    _ = private_call(
        owner=Check,
        name="_remove_legacy_output",
        pipeline="unified",
    )
    _ = private_call(
        owner=Check,
        name="_remove_legacy_output",
        pipeline="self",
    )
    expect_false(condition=legacy.exists())
    expect_true(condition=other.is_dir())


def test_pipeline_activity_and_ownership(results_root: Path) -> None:
    """The pipeline publishes the fixed activity schema and its owner file.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    legacy_owner: Path = results_root / ".runtime" / "pipeline.json"
    legacy_owner.parent.mkdir(parents=True)
    _ = legacy_owner.write_text(data=dumps(obj={"status": "DONE"}))
    run_id: str = _claim_owner_run_id()
    expect_false(condition=legacy_owner.exists())
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id=run_id,
        waves=((_lints(),),),
    )
    _ = private_call(
        owner=Check,
        name="_publish_pipeline_owner",
        pipeline="self",
        run_id=run_id,
    )
    _ = private_call(
        owner=Check,
        name="_publish_activity",
        run=run,
        current_group=1,
        status="RUNNING",
    )
    activity: ActivityDocument = require_type(
        value=ActivityFile.read(
            path=_path(name="_activity_path", pipeline="self"),
        ),
        kind=ActivityDocument,
    )
    expect_equal(actual=activity.kind, expected="pipeline")
    expect_equal(actual=activity.status, expected="RUNNING")
    expect_true(condition=activity.heartbeat.alive)
    expect_equal(actual=activity.progress.step, expected="group 1/1")
    expect_equal(
        actual=[event.message for event in activity.events],
        expected=["started: 1 tools in 1 dependency groups"],
    )
    expect_equal(
        actual=[item["name"] for item in activity.items],
        expected=["lints"],
    )
    _ = private_call(
        owner=Check,
        name="_touch_pipeline",
        pipeline="self",
        run_id=run_id,
    )
    owner: dict[str, JsonValue] = _json(
        path=_path(name="_owner_path", pipeline="self"),
    )
    expect_equal(actual=owner["schema"], expected="exactus-run/v1")
    expect_equal(actual=owner["status"], expected="RUNNING")
    expect_equal(actual=owner["step"], expected="group 1/1")
    expect_equal(actual=owner["total"], expected=1)
    _ = private_call(
        owner=Check,
        name="_finish_pipeline",
        pipeline="self",
        run_id=run_id,
        passed=True,
        elapsed_seconds=1.0,
    )
    expect_equal(
        actual=_json(path=_path(name="_owner_path", pipeline="self"))[
            "status"
        ],
        expected="DONE",
    )


def test_claim_pipeline_joins_owner_without_terminating_it(
    results_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-pipeline claimant requests reset without replacing its owner.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        monkeypatch: Pytest patching helper.

    """
    owner: Path = _path(name="_owner_path", pipeline="self")
    owner.parent.mkdir(parents=True, exist_ok=True)
    _ = owner.write_text(
        data=dumps(
            obj={
                "schema": "exactus-run/v1",
                "kind": "pipeline",
                "name": "self",
                "status": "RUNNING",
                "run_id": "old-run",
                "pid": 424242,
                "extra": {"tty": "/dev/ttys099"},
            },
        ),
        encoding="utf-8",
    )
    killed: list[tuple[int, bool]] = []

    def fake_kill(*, pid: int, replaced: bool = False) -> None:
        """Record terminations instead of signalling.

        Args:
            pid: Process identifier that would be killed.
            replaced: Whether the kill marks a replacement.

        """
        killed.append((pid, replaced))

    monkeypatch.setattr(
        target=import_module(name="exactus.__main__"),
        name="terminate_tree",
        value=fake_kill,
    )
    monkeypatch.setattr(
        target=ExactusTerminal,
        name="tty_name",
        value=staticmethod(lambda: "/dev/ttys100"),
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.tools.common.pipeline_supervisor"),
        name="process_exists",
        value=_positive_pid,
    )
    coordinator: PipelineCoordinator = PipelineCoordinator(
        runtime=results_root / ".runtime",
    )
    _ = coordinator.claim(
        pipeline="self",
        run_id="old-run",
        pid=424242,
        fingerprint="test-default",
        tty="/dev/ttys099",
    )
    claim: object = private_call(
        owner=Check,
        name="_claim_pipeline",
        pipeline="self",
    )
    expect_false(condition=bool(private(owner=claim, name="owner")))
    expect_equal(
        actual=private(owner=claim, name="run_id"),
        expected="old-run",
    )
    expect_equal(actual=killed, expected=[])
    request: object = require_type(
        value=private(owner=claim, name="request"),
        kind=object,
    )
    expect_equal(
        actual=private(owner=request, name="tty"),
        expected="/dev/ttys100",
    )


def _write_unified(*, results_root: Path) -> Path:
    """Publish a finished UNIFIED activity whose ``lints`` entry failed.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    Returns:
        The written ``@activity.json`` path.

    """
    path: Path = (
        results_root / "PIPELINES" / "UNIFIED" / "ARTIFACTS" / "@activity.json"
    )
    ActivityFile.write(
        path=path,
        document=ActivityDocument(
            kind="pipeline",
            name="unified",
            status="FAIL",
            heartbeat=ActivityHeartbeat(phase="finished"),
            progress=ActivityProgress(completed=1, total=1, fraction=0.5),
            items=({"name": "lints", "status": "FAIL", "progress": 0.5},),
        ),
    )
    lints: Path = results_root / "LINTS"
    lints.mkdir(parents=True)
    _ = (lints / "result.json").write_text(
        data=dumps(
            obj={"status": "PASS", "run_id": "r", "duration_seconds": 2.0},
        ),
    )
    return path


def test_heal_reads_pipeline_activity_files(results_root: Path) -> None:
    """Failed entries adopt newer tool reports under PIPELINES.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    path: Path = _write_unified(results_root=results_root)
    _ = private_call(owner=Check, name="_heal_activity_files")
    healed: ActivityDocument = require_type(
        value=ActivityFile.read(path=path),
        kind=ActivityDocument,
    )
    expect_equal(actual=healed.status, expected="DONE")
    expect_equal(actual=healed.items[0]["status"], expected="PASS")
    expect_equal(actual=healed.items[0]["run_id"], expected="r")


def test_unified_refresh_completes_the_progress_block(
    results_root: Path,
) -> None:
    """Refreshing UNIFIED marks the nested progress block complete.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    path: Path = _write_unified(results_root=results_root)
    lints: Path = results_root / "LINTS"
    _ = private_call(
        owner=Check,
        name="_refresh_unified_activity",
        path=path,
        results=(
            ToolRunResult(
                tool="lints",
                run_id="r",
                pipeline_run_id=None,
                status="PASS",
                passed=True,
                exit_code=0,
                duration_seconds=2.0,
                resume="",
                report=lints / "result.md",
                report_json=lints / "result.json",
                report_web=lints / "result_web" / "index.html",
            ),
        ),
        reports={"lints": _json(path=lints / "result.json")},
    )
    refreshed: ActivityDocument = require_type(
        value=ActivityFile.read(path=path),
        kind=ActivityDocument,
    )
    expect_equal(actual=refreshed.status, expected="DONE")
    expect_equal(actual=refreshed.progress.fraction, expected=1.0)
    expect_equal(
        actual=_json(path=path)["progress"],
        expected={
            "completed": 1,
            "total": 1,
            "fraction": 1.0,
            "percent": 100.0,
            "step": "",
            "current": "",
        },
    )


def test_pipeline_report_links_tool_web_reports(results_root: Path) -> None:
    """Aggregate metadata links tools relative to the pipeline web report.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    lints: Path = results_root / "LINTS"
    metadata: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            owner=Check,
            name="_metadata",
            result=ToolRunResult(
                tool="lints",
                run_id="r",
                pipeline_run_id=None,
                status="PASS",
                passed=True,
                exit_code=0,
                duration_seconds=1.0,
                resume="",
                report=lints / "result.md",
                report_json=lints / "result.json",
                report_web=lints / "result_web" / "index.html",
            ),
            output=_path(name="_pipeline_output", pipeline="unified"),
        ),
    )
    expect_equal(
        actual=metadata["report_web_href"],
        expected="../../../LINTS/result_web/index.html",
    )
    expect_in(member="report_web", container=metadata)


@pytest.mark.parametrize(
    ("before", "after"),
    [("PASS", "FAIL"), ("FAIL", "PASS")],
)
def test_live_pipeline_marks_replaced_reports(
    results_root: Path,
    before: str,
    after: str,
) -> None:
    """Refresh successful and failed tools when their reports change.

    Args:
        results_root: Isolated report directory.
        before: Pipeline's original result.
        after: New report result.

    """
    activity: ToolActivity = ToolActivity(
        name="lints",
        run_id="original",
        group=1,
        position=1,
        status=before,
        progress=1.0,
        step="complete",
        started_at=None,
        finished_at=None,
        elapsed_seconds=1.0,
    )
    run: SimpleNamespace = SimpleNamespace(
        report_stamps={},
        order=("lints",),
        activities={"lints": activity},
        fractions={"lints": 1.0},
        fail_marks={},
        external={},
    )
    output: Path = results_root / "LINTS"
    output.mkdir(parents=True)
    (output / "result.json").write_text(
        data=dumps(obj={"run_id": "replacement", "status": after}),
    )
    refreshed: ToolActivity = require_type(
        value=private_call(
            owner=Check,
            name="_refresh_activity",
            run=run,
            activity=activity,
        ),
        kind=ToolActivity,
    )
    expect_true(condition=refreshed.report_updated)
    expect_equal(actual=refreshed.status, expected=after)
    run.activities["lints"] = refreshed
    rows: tuple[tuple[str, str, float, str, float | None], ...] = cast(
        typ="tuple[tuple[str, str, float, str, float | None], ...]",
        val=private_call(owner=Check, name="_progress_rows", run=run),
    )
    expect_equal(
        actual=rows,
        expected=(
            ("lints", after + "*", 1.0, after.lower() + " 1.000s", None),
        ),
    )


def test_pipeline_does_not_wait_without_reruns(results_root: Path) -> None:
    """The rerun gate returns at once when no same-tool run is live.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    del results_root
    run_id: str = _claim_owner_run_id()
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id=run_id,
        waves=((_lints(),),),
    )
    private_call(owner=Check, name="_await_reruns", run=run)


def test_pipeline_waits_for_same_tool_reruns(
    results_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rerun of a pipeline tool blocks results until it finishes.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        monkeypatch: Pytest patching helper.

    """
    run_id: str = _claim_owner_run_id()
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id=run_id,
        waves=((_lints(),),),
    )
    stages: list[str] = []

    def fake_progress(*, stage: str, **_fields: object) -> int:
        """Record repaint stages instead of touching the terminal.

        Args:
            stage: Stage label the pipeline is repainting.
            **_fields: Remaining progress call fields.

        Returns:
            Zero rendered lines.

        """
        stages.append(stage)
        return 0

    monkeypatch.setattr(
        target=ExactusTerminal,
        name="progress",
        value=staticmethod(fake_progress),
    )
    registry: RunRegistry = RunRegistry(
        path=results_root / ".runtime" / "runs.db",
    )
    _ = registry.claim(
        request=RunClaim(
            kind="tool",
            identifier="lints",
            run_id="rerun",
            pipeline_run_id=None,
            pid=getpid(),
            output=results_root / "LINTS",
            targets=(),
        ),
    )
    done: Event = Event()

    def wait() -> None:
        """Run the rerun gate and flag completion."""
        private_call(owner=Check, name="_await_reruns", run=run)
        done.set()

    waiter: Thread = Thread(target=wait)
    waiter.start()
    sleep(0.5)
    expect_true(condition=waiter.is_alive())
    expect_in(member="waiting for lints to complete", container=stages)
    registry.finish(run_id="rerun", status="DONE", elapsed_seconds=0.1)
    waiter.join(timeout=5)
    expect_false(condition=waiter.is_alive())
    expect_true(condition=done.is_set())


def _docs() -> ToolSpec:
    """Return the ``docs`` tool specification.

    Returns:
        The catalog entry.

    """
    return require_type(
        value=Constants.exactus_catalog.tool(identifier="docs"),
        kind=ToolSpec,
    )


def test_global_fraction_normalizes_each_task_before_aggregation() -> None:
    """Large internal work totals cannot dominate other pipeline tasks."""
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id="pipe",
        waves=((_lints(), _docs()),),
    )
    fractions: dict[str, float] = cast(
        typ="dict[str, float]",
        val=private(owner=run, name="fractions"),
    )
    fractions.update({"lints": 0.5, "docs": 1.0})
    expect_equal(
        actual=private_call(owner=Check, name="_global_fraction", run=run),
        expected=0.75,
    )
    activities: dict[str, ToolActivity] = cast(
        typ="dict[str, ToolActivity]",
        val=private(owner=run, name="activities"),
    )
    activities["lints"] = replace(activities["lints"], hierarchy={"total": 8})
    activities["docs"] = replace(activities["docs"], hierarchy={"total": 375})
    expect_equal(
        actual=round(
            number=cast(
                typ="float",
                val=private_call(
                    owner=Check,
                    name="_global_fraction",
                    run=run,
                ),
            ),
            ndigits=3,
        ),
        expected=0.75,
    )


def test_failed_analysis_does_not_block_ready_tool(results_root: Path) -> None:
    """Analysis findings do not prevent a ready dependent from running.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id="pipe",
        waves=((_lints(),), (_docs(),)),
    )
    pending: dict[str, ToolSpec] = cast(
        typ="dict[str, ToolSpec]",
        val=private(owner=run, name="pending"),
    )
    del pending["lints"]
    lints_output: Path = results_root / "LINTS"
    failed: ToolRunResult = ToolRunResult(
        tool="lints",
        run_id="pipe:lints",
        pipeline_run_id="pipe",
        status="FAIL",
        passed=False,
        exit_code=1,
        duration_seconds=0.1,
        resume="lint failed",
        report=lints_output / "result.md",
        report_json=lints_output / "result.json",
        report_web=lints_output / "result_web" / "index.html",
    )
    results: dict[str, ToolRunResult] = {"lints": failed}
    external: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private(owner=run, name="external"),
    )
    external["docs"] = RunRecord(
        kind="tool",
        identifier="docs",
        run_id="external-docs",
        pipeline_run_id=None,
        pid=getpid(),
        output=str(object=results_root / "DOCS"),
        targets=(),
        status="RUNNING",
        progress=0.0,
        step="starting",
        detail="",
        created_at="2026-10-12T00:00:00+00:00",
        updated_at="2026-10-12T00:00:00+00:00",
        elapsed_seconds=0.0,
    )
    private_call(
        owner=Check,
        name="_schedule_ready_tools",
        run=run,
        results=results,
        tool_arguments={},
        descriptors={},
    )
    adopted: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private(owner=run, name="adopted"),
    )
    expect_in(member="docs", container=adopted)
    expect_false(condition="docs" in results)
    expect_false(condition=bool(pending))


def _claim(*, results_root: Path, request: RunClaim) -> RunRegistry:
    """Register one live run against the isolated results root.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        request: Ownership facts to claim.

    Returns:
        The registry that recorded the claim.

    """
    registry: RunRegistry = RunRegistry(
        path=results_root / ".runtime" / "runs.db",
    )
    _ = registry.claim(request=request)
    return registry


def _claim_run(
    *,
    results_root: Path,
    kind: str,
    identifier: str,
    run_id: str,
    pid: int | None = None,
) -> RunRegistry:
    """Claim one run with the default output directory.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        kind: Run kind: ``tool`` or ``pipeline``.
        identifier: Tool or pipeline identifier.
        run_id: Run identifier to claim.
        pid: Live process identifier; defaults to this process.

    Returns:
        The registry that recorded the claim.

    """
    return _claim(
        results_root=results_root,
        request=RunClaim(
            kind=kind,
            identifier=identifier,
            run_id=run_id,
            pipeline_run_id=None,
            pid=pid if pid is not None else getpid(),
            output=results_root / identifier.upper(),
            targets=(),
        ),
    )


def _pipeline_activity(
    *,
    results_root: Path,
    current_group: int | None,
) -> None:
    """Publish a RUNNING SELF activity carrying ``current_group``.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        current_group: Dependency wave marker to publish.

    """
    ActivityFile.write(
        path=results_root
        / "PIPELINES"
        / "SELF"
        / "ARTIFACTS"
        / "@activity.json",
        document=ActivityDocument(
            kind="pipeline",
            name="self",
            status="RUNNING",
            heartbeat=ActivityHeartbeat(phase="running"),
            progress=ActivityProgress(),
            extra={"current_group": current_group},
        ),
    )


def test_gate_blocks_until_the_pipeline_reaches_the_tool_group(
    results_root: Path,
) -> None:
    """A later-group tool launched standalone waits behind the pipeline.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    entrypoint: object = import_module(name="exactus.tools.common.execution")
    locks: dict[str, int] = cast(
        typ="dict[str, int]",
        val=private_call(
            owner=entrypoint,
            name="_pipeline_locks",
            analyzer="docs",
        ),
    )
    expect_equal(
        actual=locks,
        expected={"self": 2, "all-fast": 2, "unified": 2},
    )
    gate: Callable[..., object] = cast(
        typ="Callable[..., object]",
        val=private(owner=entrypoint, name="_pipeline_gate"),
    )
    registry: RunRegistry = _claim(
        results_root=results_root,
        request=RunClaim(
            kind="pipeline",
            identifier="self",
            run_id="pipe",
            pipeline_run_id=None,
            pid=getpid(),
            output=results_root / "PIPELINES" / "SELF",
            targets=(),
        ),
    )
    expect_equal(
        actual=gate(registry=registry, locks={"self": 2}),
        expected="waiting for self to start",
    )
    _pipeline_activity(results_root=results_root, current_group=1)
    expect_equal(
        actual=gate(registry=registry, locks={"self": 2}),
        expected="waiting for self group 1",
    )
    expect_none(value=gate(registry=registry, locks={"self": 1}))
    _pipeline_activity(results_root=results_root, current_group=2)
    expect_none(value=gate(registry=registry, locks={"self": 2}))


def test_pipeline_pauses_and_releases_prelaunched_tools(
    results_root: Path,
) -> None:
    """A pre-launched later-group run is paused until its wave arrives.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    sleeper: Popen[bytes] = Popen(args=("sleep", "60"))
    activity_path: Path = (
        results_root / "DOCS" / "ARTIFACTS" / "@activity.json"
    )
    ActivityFile.write(
        path=activity_path,
        document=ActivityDocument(
            kind="tool",
            name="docs",
            status="RUNNING",
            run_id="ext-docs",
            heartbeat=ActivityHeartbeat(pid=sleeper.pid, phase="running"),
            progress=ActivityProgress(
                completed=1,
                total=2,
                fraction=0.5,
                step="scan",
                hierarchy={
                    "level": "task",
                    "state": "RUNNING",
                    "children": [],
                },
            ),
        ),
    )
    try:
        _ = _claim_run(
            results_root=results_root,
            kind="tool",
            identifier="docs",
            run_id="ext-docs",
            pid=sleeper.pid,
        )
        run: object = private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="self",
            run_id="pipe",
            waves=((_lints(),), (_docs(),)),
        )
        private_call(owner=Check, name="_pause_ahead_tools", run=run)
        paused: dict[str, int] = cast(
            typ="dict[str, int]",
            val=private(owner=run, name="paused"),
        )
        expect_equal(actual=paused, expected={"docs": sleeper.pid})
        activity: ActivityDocument = require_type(
            value=ActivityFile.read(path=activity_path),
            kind=ActivityDocument,
        )
        expect_equal(actual=activity.status, expected="PAUSED")
        expect_equal(actual=activity.heartbeat.phase, expected="paused")
        expect_equal(actual=activity.progress.step, expected="paused")
        rows: tuple[tuple[str, str, float, str, float | None], ...] = cast(
            typ="tuple[tuple[str, str, float, str, float | None], ...]",
            val=private_call(owner=Check, name="_progress_rows", run=run),
        )
        expect_equal(
            actual=rows[1],
            expected=(
                "docs",
                "PAUSED*",
                0.0,
                "waiting for dependencies",
                None,
            ),
        )
        private_call(owner=Check, name="_release_group", run=run, group=1)
        expect_equal(actual=paused, expected={"docs": sleeper.pid})
        private_call(owner=Check, name="_release_group", run=run, group=2)
        expect_equal(actual=paused, expected={})
        activity = require_type(
            value=ActivityFile.read(path=activity_path),
            kind=ActivityDocument,
        )
        expect_equal(actual=activity.status, expected="RUNNING")
        expect_equal(actual=activity.heartbeat.phase, expected="running")
    finally:
        with suppress(ProcessLookupError):
            kill(sleeper.pid, SIGCONT)
        sleeper.terminate()
        _ = sleeper.wait(timeout=5)


def _fixed_descriptor(
    cls: type[Discovery],
    *,
    name: str,
    context: str,
) -> Descriptor:
    """Stand in for ``Discovery.find`` with a live local descriptor.

    Args:
        cls: Bound ``Discovery`` class, unused.
        name: Requested worker name.
        context: Requested worker context.

    Returns:
        A descriptor pointing at this process.

    """
    del cls
    return Descriptor(
        pid=getpid(),
        port=0,
        name=name,
        context=context,
        args=(),
    )


def _held_release(*, descriptor: Descriptor, owner: str) -> bool:
    """Stand in for ``resume_worker`` while another owner holds the lease.

    Args:
        descriptor: Worker descriptor, unused.
        owner: Releasing pipeline owner, unused.

    Returns:
        Always ``False``: the worker stays paused.

    """
    del descriptor, owner
    return False


def _granted_release(*, descriptor: Descriptor, owner: str) -> bool:
    """Stand in for ``resume_worker`` once every lease owner released.

    Args:
        descriptor: Worker descriptor, unused.
        owner: Releasing pipeline owner, unused.

    Returns:
        Always ``True``: the worker resumed.

    """
    del descriptor, owner
    return True


def test_release_group_keeps_paused_run_while_lease_is_held(
    results_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run whose pause lease another owner still holds stays tracked.

    Dropping the entry would leave the frozen process displayed as
    ``RUNNING*`` forever; keeping it lets a later wave retry the
    release.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        monkeypatch: Pytest patching helper.

    """
    sleeper: Popen[bytes] = Popen(args=("sleep", "60"))
    activity_path: Path = (
        results_root / "DOCS" / "ARTIFACTS" / "@activity.json"
    )
    ActivityFile.write(
        path=activity_path,
        document=ActivityDocument(
            kind="tool",
            name="docs",
            status="RUNNING",
            run_id="ext-docs",
            heartbeat=ActivityHeartbeat(pid=sleeper.pid, phase="running"),
            progress=ActivityProgress(
                completed=1,
                total=2,
                fraction=0.5,
                step="scan",
                hierarchy={
                    "level": "task",
                    "state": "RUNNING",
                    "children": [],
                },
            ),
        ),
    )
    try:
        _ = _claim_run(
            results_root=results_root,
            kind="tool",
            identifier="docs",
            run_id="ext-docs",
            pid=sleeper.pid,
        )
        run: object = private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="self",
            run_id="pipe",
            waves=((_lints(),), (_docs(),)),
        )
        private_call(owner=Check, name="_pause_ahead_tools", run=run)
        paused: dict[str, int] = cast(
            typ="dict[str, int]",
            val=private(owner=run, name="paused"),
        )
        expect_equal(actual=paused, expected={"docs": sleeper.pid})
        monkeypatch.setattr(
            target=Discovery,
            name="find",
            value=classmethod(_fixed_descriptor),
        )
        main_module: object = import_module(name="exactus.__main__")
        monkeypatch.setattr(
            target=main_module,
            name="resume_worker",
            value=_held_release,
        )
        private_call(owner=Check, name="_release_group", run=run, group=2)
        expect_equal(actual=paused, expected={"docs": sleeper.pid})
        monkeypatch.setattr(
            target=main_module,
            name="resume_worker",
            value=_granted_release,
        )
        private_call(owner=Check, name="_release_group", run=run, group=2)
        expect_equal(actual=paused, expected={})
    finally:
        with suppress(ProcessLookupError):
            kill(sleeper.pid, SIGCONT)
        sleeper.terminate()
        _ = sleeper.wait(timeout=5)


def test_pause_tree_exclude_leaves_target_running() -> None:
    """``pause_tree`` never stops pids owned by another pause mechanism."""
    sleeper: Popen[bytes] = Popen(args=("sleep", "60"))
    try:
        process_control: object = import_module(
            name="exactus.tools.common.process_control",
        )
        private_call(
            owner=process_control,
            name="pause_tree",
            pid=sleeper.pid,
            exclude=(sleeper.pid,),
        )
        sleep(0.1)
        running: str = check_output(
            args=("ps", "-o", "stat=", "-p", str(object=sleeper.pid)),
            text=True,
        )
        expect_not_in(member="T", container=running)
    finally:
        with suppress(ProcessLookupError):
            kill(sleeper.pid, SIGCONT)
        sleeper.terminate()
        _ = sleeper.wait(timeout=5)


def test_pause_tree_suspends_then_resume_tree_continues() -> None:
    """``pause_tree`` freezes a process and ``resume_tree`` frees it."""
    sleeper: Popen[bytes] = Popen(args=("sleep", "60"))
    try:
        process_control: object = import_module(
            name="exactus.tools.common.process_control",
        )
        private_call(owner=process_control, name="pause_tree", pid=sleeper.pid)
        sleep(0.1)
        stopped: str = check_output(
            args=("ps", "-o", "stat=", "-p", str(object=sleeper.pid)),
            text=True,
        )
        expect_in(member="T", container=stopped)
        private_call(
            owner=process_control,
            name="resume_tree",
            pid=sleeper.pid,
        )
        sleep(0.1)
        running: str = check_output(
            args=("ps", "-o", "stat=", "-p", str(object=sleeper.pid)),
            text=True,
        )
        expect_not_in(member="T", container=running)
    finally:
        with suppress(ProcessLookupError):
            kill(sleeper.pid, SIGCONT)
        sleeper.terminate()
        _ = sleeper.wait(timeout=5)


def test_progress_rows_overlay_external_run_progress(
    results_root: Path,
) -> None:
    """A running external member shows live progress in its row.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    registry: RunRegistry = _claim_run(
        results_root=results_root,
        kind="tool",
        identifier="docs",
        run_id="ext-docs",
    )
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id="pipe",
        waves=((_lints(),), (_docs(),)),
    )
    external: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private_call(owner=Check, name="_external_tools", run=run),
    )
    expect_in(member="docs", container=external)
    cast(
        typ="dict[str, RunRecord]",
        val=private(owner=run, name="external"),
    ).update(external)
    rows: tuple[tuple[str, str, float, str, float | None], ...] = cast(
        typ="tuple[tuple[str, str, float, str, float | None], ...]",
        val=private_call(owner=Check, name="_progress_rows", run=run),
    )
    expect_equal(
        actual=rows[1],
        expected=("docs", "RUNNING*", 0.0, "starting", None),
    )
    del registry


def test_wave_adopts_and_drains_an_external_run(
    results_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live external member run is adopted instead of duplicated.

    The wave drain waits for the external run, then reconciles its
    report as a ``PASS*`` result.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.
        monkeypatch: Pytest patching helper.

    """
    registry: RunRegistry = _claim_run(
        results_root=results_root,
        kind="tool",
        identifier="docs",
        run_id="ext-docs",
    )
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id="pipe",
        waves=((_lints(),), (_docs(),)),
    )
    seen: list[tuple[tuple[str, str, float, str, float | None], ...]] = []

    def fake_progress(*, tools: object, **_fields: object) -> int:
        """Record rendered rows instead of touching the terminal.

        Args:
            tools: Rendered ``(tool, status, fraction, detail)`` rows.
            **_fields: Remaining progress call fields.

        Returns:
            Zero rendered lines.

        """
        seen.append(
            cast(
                typ=("tuple[tuple[str, str, float, str, float | None], ...]"),
                val=tools,
            ),
        )
        return 0

    monkeypatch.setattr(
        target=ExactusTerminal,
        name="progress",
        value=staticmethod(fake_progress),
    )
    external: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private_call(owner=Check, name="_external_tools", run=run),
    )
    cast(
        typ="dict[str, RunRecord]",
        val=private(owner=run, name="adopted"),
    ).update(external)
    results: dict[str, ToolRunResult] = {}
    done: Event = Event()

    def drain() -> None:
        """Drain the wave and flag completion."""
        while cast(
            typ="dict[str, RunRecord]",
            val=private(owner=run, name="adopted"),
        ):
            refreshed: dict[str, RunRecord] = cast(
                typ="dict[str, RunRecord]",
                val=private_call(owner=Check, name="_external_tools", run=run),
            )
            live_external: dict[str, RunRecord] = cast(
                typ="dict[str, RunRecord]",
                val=private(owner=run, name="external"),
            )
            live_external.clear()
            live_external.update(refreshed)
            private_call(
                owner=Check,
                name="_drain_adopted",
                run=run,
                external=refreshed,
                results=results,
            )
            _ = fake_progress(
                tools=private_call(
                    owner=Check,
                    name="_progress_rows",
                    run=run,
                ),
            )
            sleep(0.05)
        done.set()

    waiter: Thread = Thread(target=drain)
    waiter.start()
    sleep(0.5)
    expect_true(condition=waiter.is_alive())
    expect_true(
        condition=any(
            row[0] == "docs" and row[1] == "RUNNING*"
            for rows in seen
            for row in rows
        ),
    )
    docs: Path = results_root / "DOCS"
    docs.mkdir(parents=True, exist_ok=True)
    _ = (docs / "result.json").write_text(
        data=dumps(
            obj={
                "run_id": "ext-docs",
                "status": "PASS",
                "passed": True,
                "duration_seconds": 1.5,
            },
        ),
    )
    registry.finish(run_id="ext-docs", status="DONE", elapsed_seconds=0.1)
    waiter.join(timeout=5)
    expect_false(condition=waiter.is_alive())
    expect_true(condition=done.is_set())
    adopted: ToolRunResult = require_type(
        value=results["docs"],
        kind=ToolRunResult,
    )
    expect_true(condition=adopted.passed)
    expect_true(condition=adopted.replaced_after_execution)


def test_adopted_progress_resets_on_superseding_run(
    results_root: Path,
) -> None:
    """A newer external run resets the adopted tool's progress share.

    Within one ``run_id`` the fraction only moves forward; when the
    live external record points at a newer run the baseline drops so
    the GLOBAL bar regresses and refills with the superseding run.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    _ = _claim_run(
        results_root=results_root,
        kind="tool",
        identifier="docs",
        run_id="ext-docs-1",
    )
    run: object = private_call(
        owner=Check,
        name="_new_pipeline_run",
        pipeline="self",
        run_id="pipe",
        waves=((_lints(),), (_docs(),)),
    )
    external: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private_call(owner=Check, name="_external_tools", run=run),
    )
    cast(
        typ="dict[str, RunRecord]",
        val=private(owner=run, name="adopted"),
    ).update(external)
    cast(typ="dict[str, float]", val=private(owner=run, name="fractions"))[
        "docs"
    ] = 0.9
    results: dict[str, ToolRunResult] = {}
    private_call(
        owner=Check,
        name="_drain_adopted",
        run=run,
        external=external,
        results=results,
    )
    expect_equal(
        actual=cast(
            typ="dict[str, float]",
            val=private(owner=run, name="fractions"),
        )["docs"],
        expected=0.9,
    )
    _ = _claim_run(
        results_root=results_root,
        kind="tool",
        identifier="docs",
        run_id="ext-docs-2",
    )
    superseded: dict[str, RunRecord] = cast(
        typ="dict[str, RunRecord]",
        val=private_call(owner=Check, name="_external_tools", run=run),
    )
    private_call(
        owner=Check,
        name="_drain_adopted",
        run=run,
        external=superseded,
        results=results,
    )
    expect_equal(
        actual=cast(
            typ="dict[str, float]",
            val=private(owner=run, name="fractions"),
        )["docs"],
        expected=0.0,
    )
    expect_equal(
        actual=cast(
            typ="dict[str, RunRecord]",
            val=private(owner=run, name="adopted"),
        )["docs"].run_id,
        expected="ext-docs-2",
    )


def test_standalone_run_waits_at_the_group_gate(results_root: Path) -> None:
    """A standalone later-group run holds until the pipeline catches up.

    The run stays claimed while gated, so the pipeline can adopt it.

    Args:
        results_root: Temporary ``EXACTUS_RESULTS`` directory.

    """
    entrypoint: object = import_module(name="exactus.tools.common.execution")
    _ = _claim(
        results_root=results_root,
        request=RunClaim(
            kind="pipeline",
            identifier="self",
            run_id="pipe",
            pipeline_run_id=None,
            pid=getpid(),
            output=results_root / "PIPELINES" / "SELF",
            targets=(),
        ),
    )
    _pipeline_activity(results_root=results_root, current_group=1)
    context: object = private_call(
        owner=entrypoint,
        name="_RunContext",
        output=results_root / "DOCS",
        analyzer="docs",
        started_at="",
        started=monotonic(),
        interrupted=Event(),
        stop=Event(),
        write_lock=Lock(),
        registry=RunRegistry(path=results_root / ".runtime" / "runs.db"),
        run_id="ext-docs",
        pipeline_run_id=None,
        previous_duration_seconds=None,
        log=ActivityLog(),
        stderr=StderrRecorder(),
    )
    done: Event = Event()

    def gate() -> None:
        """Wait at the pipeline group gate and flag its release."""
        private_call(
            owner=entrypoint,
            name="_await_pipeline_gate",
            context=context,
        )
        done.set()

    waiter: Thread = Thread(target=gate)
    waiter.start()
    sleep(0.5)
    expect_true(condition=waiter.is_alive())
    _pipeline_activity(results_root=results_root, current_group=2)
    waiter.join(timeout=5)
    expect_false(condition=waiter.is_alive())
    expect_true(condition=done.is_set())
