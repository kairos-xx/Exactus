# Copyright (c) 2026
"""Result models, progress documents, the process API, and runtime."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from json import dumps, loads
from os import getpid
from pathlib import Path
from sys import path as sys_path
from threading import Barrier, get_native_id
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    require,
)
from exactus.tools.common import runtime as rt
from exactus.tools.common.api import ExactusApi
from exactus.tools.common.catalog import Constants, ToolSpec
from exactus.tools.common.models import (
    PipelineActivity,
    ToolActivity,
    ToolRequest,
    ToolRunResult,
    result_stats,
)
from exactus.tools.common.progress import RunDocument, RunItem
from exactus.tools.common.registry import RunClaim, RunRegistry
from exactus.tools.common.tool_worker import (
    ExactusTool,
    WorkerRequest,
    worker_arguments,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from exactus.tools.common.runtime import LaneProgress


def _result(tmp_path: Path) -> ToolRunResult:
    """Build a result for ``tmp_path``.

    Args:
        tmp_path: Report directory.

    Returns:
        The result.

    """
    return ToolRunResult(
        tool="demo",
        run_id="r1",
        pipeline_run_id=None,
        status="PASS",
        passed=True,
        exit_code=0,
        duration_seconds=1.0,
        resume="ok",
        report=tmp_path / "result.md",
        report_json=tmp_path / "result.json",
        report_web=tmp_path / "result_web" / "index.html",
    )


def test_from_report_reads_fields_and_falls_back(tmp_path: Path) -> None:
    """Report payloads override the fallback only with valid types.

    Args:
        tmp_path: Per-test temporary directory.

    """
    base: ToolRunResult = _result(tmp_path=tmp_path)
    good: ToolRunResult = ToolRunResult.from_report(
        payload={
            "tool": "other",
            "run_id": "r2",
            "pipeline_run_id": "p",
            "status": "FAIL",
            "passed": False,
            "duration_seconds": 2,
            "resume": "bad",
        },
        output=tmp_path,
        fallback=base,
    )
    expect_equal(
        actual=(good.tool, good.run_id, good.status),
        expected=("other", "r2", "FAIL"),
    )
    expect_equal(actual=good.exit_code, expected=1)
    expect_true(condition=good.replaced_after_execution)
    junk: ToolRunResult = ToolRunResult.from_report(
        payload={"tool": 1, "run_id": 2, "status": 3, "passed": "x"},
        output=tmp_path,
        fallback=base,
    )
    expect_equal(actual=junk.tool, expected="demo")
    expect_true(condition=junk.passed)
    expect_equal(
        actual=ToolRunResult.from_report(
            payload=[1],
            output=tmp_path,
            fallback=base,
        ).tool,
        expected="demo",
    )
    expect_true(condition=base.replaced().replaced_after_execution)


def test_reconcile_variants(tmp_path: Path) -> None:
    """Reports from other runs mark the result as replaced.

    Args:
        tmp_path: Per-test temporary directory.

    """
    base: ToolRunResult = _result(tmp_path=tmp_path)
    expect_equal(actual=ExactusApi.reconcile(result=base), expected=base)
    (tmp_path / "result.json").write_text(data=dumps(obj={"run_id": "r1"}))
    expect_equal(actual=ExactusApi.reconcile(result=base), expected=base)
    (tmp_path / "result.json").write_text(
        data=dumps(obj={"run_id": "zzz", "status": "FAIL", "passed": False}),
    )
    replaced: ToolRunResult = ExactusApi.reconcile(result=base)
    expect_true(condition=replaced.replaced_after_execution)
    expect_equal(actual=replaced.run_id, expected="zzz")
    (tmp_path / "result.json").write_text(data="{bad")
    expect_true(
        condition=ExactusApi.reconcile(result=base).replaced_after_execution,
    )
    (tmp_path / "result.json").write_text(data="[1]")
    expect_true(
        condition=ExactusApi.reconcile(result=base).replaced_after_execution,
    )


def test_result_stats_summarizes_files_and_severities(tmp_path: Path) -> None:
    """The resume stats join affected/total files and severity counts.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_equal(
        actual=result_stats(report_json=tmp_path / "missing.json"),
        expected="",
    )
    report: Path = tmp_path / "result.json"
    _ = report.write_text(
        data=dumps(
            obj={
                "summary": {
                    "targets_analyzed": 220,
                    "findings_total": 3,
                    "severity": {"warning": 3},
                },
                "findings": [
                    {"severity": "warning", "file": "a.py"},
                    {"severity": "warning", "path": "a.py"},
                    {"severity": "warning", "target": "b.py"},
                ],
            },
        ),
    )
    expect_equal(
        actual=result_stats(report_json=report),
        expected="2 files with issues / 220 files · 3 warnings",
    )
    _ = report.write_text(
        data=dumps(
            obj={
                "summary": {"targets_analyzed": 10, "findings_total": 1},
                "findings": [{"severity": "error"}],
            },
        ),
    )
    expect_equal(
        actual=result_stats(report_json=report),
        expected="0 files with issues / 10 files · 1 error",
    )


def test_activity_payloads() -> None:
    """Activities serialize to the uniform run-document schema."""
    tool: ToolActivity = ToolActivity(
        name="lints",
        run_id="t",
        group=1,
        position=1,
        status="RUNNING",
        progress=0.5,
        step="s",
        started_at="a",
        finished_at=None,
        elapsed_seconds=1.0,
    )
    expect_equal(actual=tool.payload()["position"], expected=1)
    pipe: PipelineActivity = PipelineActivity(
        name="unified",
        run_id="p",
        status="RUNNING",
        progress=0.1,
        completed=0,
        total=1,
        step="x",
        detail="d",
        current_group=None,
        group_count=2,
        started_at="a",
        finished_at=None,
        elapsed_seconds=1.0,
        updated_at="u",
        pid=1,
        items=(tool,),
    )
    payload: object = pipe.payload()
    expect_equal(
        actual=dig(document=payload, path=("schema",)),
        expected="exactus/activity/v1",
    )
    expect_equal(
        actual=len(dig_list(document=payload, path=("items",))),
        expected=1,
    )
    expect_equal(
        actual=dig(document=payload, path=("heartbeat", "phase")),
        expected="running",
    )
    expect_equal(
        actual=dig(document=payload, path=("progress", "percent")),
        expected=10.0,
    )
    expect_equal(
        actual=dig(document=payload, path=("extra", "group_count")),
        expected=2,
    )
    doc: object = RunDocument(
        kind="tool",
        name="n",
        status="DONE",
        items=(RunItem(name="i", status="DONE"), {"name": "raw"}),
    ).payload()
    expect_equal(
        actual=[
            dig(document=item, path=("name",))
            for item in dig_list(document=doc, path=("items",))
        ],
        expected=["i", "raw"],
    )


@pytest.fixture
def progress_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset the process-local progress channel around a test.

    Args:
        monkeypatch: Pytest patching helper.

    Yields:
        Control while the progress channel is isolated.

    """
    monkeypatch.setenv(name="EXACTUS_TOOL", value="demo")
    monkeypatch.setenv(name="EXACTUS_RUN_ID", value="rid")
    rt.clear_progress()
    yield
    rt.clear_progress()


def test_progress_is_current_and_spanned(progress_state: None) -> None:
    """Published fractions reflect current work and honor spans.

    Args:
        progress_state: Isolated process-local progress state.

    """
    _ = progress_state
    rt.publish_progress(
        progress=rt.Progress(
            state="RUNNING",
            completed=5,
            total=10,
            step="a",
            span=(0.5, 1.0),
        ),
    )
    expect_equal(actual=rt.current_progress()["progress"], expected=0.75)
    rt.emit_progress(state="RUNNING", completed=1, total=10, step="b")
    expect_equal(actual=rt.current_progress()["progress"], expected=0.1)
    rt.publish_progress(
        progress=rt.Progress(
            state="DONE",
            completed=-1,
            total=0,
            step="c",
            share=2.0,
            span=(0.0, 1.0),
        ),
    )
    expect_equal(actual=rt.current_progress()["progress"], expected=1.0)


def test_progress_without_run_identity() -> None:
    """Standalone progress remains available in process memory."""
    rt.clear_progress()
    rt.emit_progress(state="RUNNING", completed=1, total=2, step="x")
    expect_equal(actual=rt.current_progress()["progress"], expected=0.5)
    expect_equal(
        actual=rt.Progress(state="S", completed=1, total=4, step="x").fraction,
        expected=0.25,
    )


def test_lane_progress_counts() -> None:
    """Lanes share one monotonically increasing counter."""
    lanes: LaneProgress = rt.LaneProgress(total=0)
    expect_equal(actual=lanes.total, expected=1)
    expect_equal(actual=lanes.completed, expected=0)
    expect_equal(actual=lanes.advance(), expected=1)
    expect_equal(actual=lanes.advance(), expected=2)
    expect_equal(actual=lanes.completed, expected=2)


def test_provisional_release_opens_dependent_file_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lints release lets kwargs read a file before lints terminates.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest environment patching helper.

    """
    database: Path = tmp_path / "runs.db"
    registry: RunRegistry = RunRegistry(path=database)
    source: Path = tmp_path / "source.py"
    source.write_text(data="value: int = 1\n", encoding="utf-8")
    expect_equal(
        actual=registry.claim(
            request=RunClaim(
                kind="tool",
                identifier="lints",
                run_id="lints-run",
                pipeline_run_id="pipeline",
                pid=getpid(),
                output=tmp_path / "LINTS",
                targets=(str(object=tmp_path.resolve()),),
            ),
        ),
        expected=(),
    )
    monkeypatch.setenv(name="EXACTUS_REGISTRY", value=str(object=database))
    monkeypatch.setenv(name="EXACTUS_TOOL", value="lints")
    monkeypatch.setenv(name="EXACTUS_RUN_ID", value="lints-run")
    rt.release_activities(items=[source], stable=False)
    expect_equal(
        actual=registry.activity_state(
            run_id="lints-run",
            item=str(object=source.resolve()),
        ),
        expected="released",
    )
    monkeypatch.setenv(name="EXACTUS_TOOL", value="kwargs_typehints")
    monkeypatch.setenv(name="EXACTUS_RUN_ID", value="kwargs-run")
    lanes: LaneProgress = rt.LaneProgress(total=1)
    lanes.begin(item=str(object=source))
    expect_equal(actual=lanes.finish(item=str(object=source)), expected=1)


@pytest.fixture
def worker_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Isolate process-wide state mutated by the worker entry.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    Yields:
        The project root used by the worker.

    """
    monkeypatch.chdir(path=tmp_path)
    for name in (
        "EXACTUS_ORCHESTRATED",
        "EXACTUS_RUN_ID",
        "EXACTUS_PIPELINE_RUN_ID",
        "PYTHONPATH",
        "PLAYWRIGHT_BROWSERS_PATH",
    ):
        monkeypatch.setenv(name=name, value="")
    _ = (tmp_path / "README.md").write_text(data="# x\n")
    with patch(target="sys.path", new=list(sys_path)):
        yield tmp_path


def _spec() -> ToolSpec:
    """Return the catalog's readme tool.

    Returns:
        The tool spec.

    """
    return require(value=Constants.exactus_catalog.tool(identifier="readme"))


def _thread_identity(_index: int, *, barrier: Barrier) -> tuple[int, int]:
    """Return process and native-thread identities after all lanes start.

    Args:
        _index: Lane index, used only to give ``map`` one item per lane.
        barrier: Synchronization barrier proving concurrent thread lanes.

    Returns:
        Current process and native thread identifiers.

    """
    _ = barrier.wait()
    return (getpid(), get_native_id())


def main(*, arguments: tuple[str, ...]) -> int:
    """Exercise a file-style thread pool inside a detached worker process.

    Args:
        arguments: First value is the evidence JSON path.

    Returns:
        Zero after writing worker and thread identities.

    """
    barrier: Barrier = Barrier(parties=4)
    with ThreadPoolExecutor(max_workers=4) as pool:
        identities: list[tuple[int, int]] = list(
            pool.map(partial(_thread_identity, barrier=barrier), range(4)),
        )
    _ = Path(arguments[0]).write_text(data=dumps(obj=identities))
    return 0


@pytest.mark.parametrize("pipeline_id", [None, "p" * 32])
def test_worker_runs_tool_and_writes_result(
    pipeline_id: str | None,
    worker_env: Path,
) -> None:
    """The pmanager worker executes a tool and writes its report.

    Args:
        pipeline_id: Value for ``pipeline_id``.
        worker_env: Value for ``worker_env``.

    """
    request: ToolRequest = ToolRequest(
        identifier="readme",
        output=worker_env / "EXACTUS_RESULTS" / "README",
        arguments=(str(object=worker_env),),
        run_id="w" * 32,
        pipeline_run_id=pipeline_id,
        project_root=worker_env,
    )
    worker_request: WorkerRequest = cast(
        typ="WorkerRequest",
        val=worker_arguments(request=request, spec=_spec())[1]["request"],
    )
    expect_equal(actual=ExactusTool().run(request=worker_request), expected=0)
    report: Path = request.output / "result.json"
    expect_true(condition=report.is_file())
    expect_in(member='"run_id": "' + "w" * 32, container=report.read_text())


def test_run_tool_spawns_isolated_worker(worker_env: Path) -> None:
    """A real worker process produces and returns a result.

    Args:
        worker_env: Value for ``worker_env``.

    """
    request: ToolRequest = ToolRequest(
        identifier="readme",
        output=worker_env / "EXACTUS_RESULTS" / "README",
        arguments=(str(object=worker_env),),
        run_id="x" * 32,
        project_root=worker_env,
    )
    result: ToolRunResult = ExactusApi.run_tool(request=request, spec=_spec())
    expect_equal(actual=result.tool, expected="readme")
    expect_true(condition=result.report_json.is_file())


def test_detached_worker_owns_its_file_threads(worker_env: Path) -> None:
    """File-level threads execute inside their independent tool process.

    Args:
        worker_env: Isolated project root.

    """
    evidence: Path = worker_env / "thread-evidence.json"
    threaded: ToolSpec = ToolSpec(
        identifier="threaded",
        module=__name__,
        script=__file__,
        output="THREADED",
    )
    result: ToolRunResult = ExactusApi.run_tool(
        request=ToolRequest(
            identifier="threaded",
            output=worker_env / "EXACTUS_RESULTS" / "THREADED",
            arguments=(str(object=evidence),),
            run_id="t" * 32,
            project_root=worker_env,
        ),
        spec=threaded,
    )
    identities: list[list[int]] = cast(
        typ="list[list[int]]",
        val=loads(s=evidence.read_text()),
    )
    expect_true(condition=result.passed)
    expect_equal(
        actual=len({identity[0] for identity in identities}),
        expected=1,
    )
    expect_true(condition=identities[0][0] != getpid())
    expect_equal(
        actual=len({identity[1] for identity in identities}),
        expected=4,
    )


def test_run_tool_reports_crashed_worker(worker_env: Path) -> None:
    """A worker that dies before reporting yields a failed result.

    Args:
        worker_env: Value for ``worker_env``.

    """
    bogus: ToolSpec = ToolSpec(
        identifier="ghost",
        module="no_such_module_xyz",
        script="x.py",
        output="GHOST",
    )
    request: ToolRequest = ToolRequest(
        identifier="ghost",
        output=worker_env / "EXACTUS_RESULTS" / "GHOST",
        arguments=(),
        run_id="y" * 32,
        project_root=worker_env,
    )
    result: ToolRunResult = ExactusApi.run_tool(request=request, spec=bogus)
    expect_false(condition=result.passed)
    expect_in(member="exited before reporting", container=result.resume)
    expect_true(condition=Path(result.report).is_file())
