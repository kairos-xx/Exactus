# Copyright (c) 2026
"""Scope a joined pipeline reset to the tools a request asks to rerun."""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps
from os import getpid
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from exactus import __main__ as exactus_main
from exactus.__main__ import Check, GroupFinalConstants, PipelineRun
from exactus.packages.pmanager.runtime import Descriptor
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    private_call,
    require,
)
from exactus.tools.common.models import ToolRunResult
from exactus.tools.common.pipeline_supervisor import (
    PipelineOwner,
    PipelineRequest,
)
from exactus.tools.common.process_layer.access import authkey
from exactus.tools.common.process_layer.process_control import RunIdentity
from exactus.tools.common.registry import RunClaim, RunRecord, RunRegistry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from exactus.packages.pmanager import ProcessHandle
    from exactus.tools.common.catalog import ToolSpec
    from exactus.tools.common.json_types import JsonValue


@dataclass(frozen=True, slots=True, kw_only=True)
class _Coordinator:
    """Expose the two coordinator members the helper reads.

    Attributes:
        requests_root: Directory holding materialized request files.
        current: Owner reported for the pipeline, when one exists.

    """

    requests_root: Path
    current: PipelineOwner | None

    def owner(self, *, pipeline: str) -> PipelineOwner | None:
        """Return the configured owner regardless of the pipeline.

        Args:
            pipeline: Canonical pipeline identifier, unused here.

        Returns:
            The owner this stand-in was built with.

        """
        del pipeline
        return self.current


@dataclass(frozen=True, slots=True, kw_only=True)
class _Run:
    """Expose the run members the helper reads.

    Attributes:
        pipeline: Canonical pipeline identifier.
        order: Canonical tool ordering of the owner run.
        coordinator: Stand-in owner and request store.

    """

    pipeline: str
    order: tuple[str, ...]
    coordinator: _Coordinator


def _owner(*, fingerprint: str) -> PipelineOwner:
    """Build an owner carrying the given configuration hash.

    Args:
        fingerprint: Effective configuration hash of the owner.

    Returns:
        A running owner record.

    """
    return PipelineOwner(
        pipeline="all",
        run_id="owner-run",
        pid=1,
        fingerprint=fingerprint,
        state="running",
        generation=0,
        started_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _request(
    *,
    request_id: str,
    fingerprint: str,
    plan: dict[str, JsonValue] | None,
) -> PipelineRequest:
    """Build a pending observer request.

    Args:
        request_id: Unique observer identity.
        fingerprint: Requested configuration hash.
        plan: Inline work plan, or ``None`` to force a file lookup.

    Returns:
        A pending request joined to ``owner-run``.

    """
    return PipelineRequest(
        request_id=request_id,
        pipeline="all",
        pipeline_run_id="owner-run",
        fingerprint=fingerprint,
        pid=2,
        tty=None,
        state="pending",
        generation=None,
        requested_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        detail="",
        plan=plan,
    )


def _run(*, root: Path, owner: PipelineOwner | None) -> _Run:
    """Build a run whose canonical order is lints then docs.

    Args:
        root: Directory used as the request store.
        owner: Owner the stand-in coordinator reports.

    Returns:
        A run stand-in for the scoping helper.

    """
    return _Run(
        pipeline="all",
        order=("lints", "docs"),
        coordinator=_Coordinator(requests_root=root, current=owner),
    )


def _roots(
    *,
    run: _Run,
    requests: tuple[PipelineRequest, ...],
) -> object:
    """Call the private scoping helper.

    Args:
        run: Run stand-in.
        requests: Joined requests to scope.

    Returns:
        The helper's result.

    """
    return private_call(
        owner=Check,
        name="_requested_scope",
        run=run,
        requests=requests,
    )


@pytest.mark.parametrize(
    ("identifier", "dependency", "expected"),
    [
        ("coverage_tests", "lints", True),
        ("docs", "lints", True),
        ("lints", "coverage_tests", False),
        ("docs", "coverage_tests", False),
        ("no_such_tool", "lints", False),
    ],
)
def test_tool_dependency_follows_the_catalog(
    *,
    identifier: str,
    dependency: str,
    expected: bool,
) -> None:
    """A tool depends on exactly the prerequisites its spec declares.

    Args:
        identifier: Candidate dependent tool.
        dependency: Candidate prerequisite tool.
        expected: Whether the dependency must settle first.

    """
    expect_equal(
        actual=private_call(
            owner=Check,
            name="_tool_depends_on",
            identifier=identifier,
            dependency=dependency,
        ),
        expected=expected,
    )


def test_scoped_reset_needs_an_owner(tmp_path: Path) -> None:
    """Without an owner there is no scope, so the full plan resets.

    Args:
        tmp_path: Disposable request store.

    """
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=None),
            requests=(
                _request(
                    request_id="a",
                    fingerprint="x",
                    plan={"tools": ["lints"]},
                ),
            ),
        ),
        expected=None,
    )


def test_same_fingerprint_requests_reset_the_full_plan(
    tmp_path: Path,
) -> None:
    """A request matching the owner configuration is not scoped.

    Args:
        tmp_path: Disposable request store.

    """
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="same")),
            requests=(
                _request(
                    request_id="a",
                    fingerprint="same",
                    plan={"tools": ["lints"]},
                ),
            ),
        ),
        expected=None,
    )


def test_inline_plans_union_and_ignore_unknown_tools(
    tmp_path: Path,
) -> None:
    """Roots are the union of requested tools the owner actually runs.

    Args:
        tmp_path: Disposable request store.

    """
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="owner")),
            requests=(
                _request(
                    request_id="a",
                    fingerprint="one",
                    plan={"tools": ["lints", "not_in_order", 7]},
                ),
                _request(
                    request_id="b",
                    fingerprint="two",
                    plan={"tools": ["docs"]},
                ),
            ),
        ),
        expected=(
            {"lints", "docs"},
            dict[str, tuple[str, ...]](),
            set[str](),
        ),
    )


def test_requested_scope_collects_arguments_and_missing_tools(
    tmp_path: Path,
) -> None:
    """Requested CLI arguments and out-of-plan tools join the scope.

    Args:
        tmp_path: Disposable request store.

    """
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="owner")),
            requests=(
                _request(
                    request_id="a",
                    fingerprint="one",
                    plan={
                        "tools": ["lints", "readme"],
                        "arguments": {"lints": ["--verbose"], "bad": 9},
                    },
                ),
            ),
        ),
        expected=(
            {"lints"},
            {"lints": ("--verbose",)},
            {"readme"},
        ),
    )


def test_requested_scope_survives_missing_arguments_block(
    tmp_path: Path,
) -> None:
    """Plans without an arguments map scope to empty overrides.

    Args:
        tmp_path: Disposable request store.

    """
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="owner")),
            requests=(
                _request(
                    request_id="a",
                    fingerprint="one",
                    plan={"tools": ["docs"]},
                ),
            ),
        ),
        expected=(
            {"docs"},
            dict[str, tuple[str, ...]](),
            set[str](),
        ),
    )


def test_plan_is_read_from_the_materialized_request_file(
    tmp_path: Path,
) -> None:
    """A request without an inline plan falls back to its JSON file.

    Args:
        tmp_path: Disposable request store.

    """
    folder: Path = tmp_path / "owner-run"
    folder.mkdir()
    _ = (folder / "a.json").write_text(
        data=dumps(obj={"plan": {"tools": ["docs"]}}),
        encoding="utf-8",
    )
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="owner")),
            requests=(_request(request_id="a", fingerprint="one", plan=None),),
        ),
        expected=(
            {"docs"},
            dict[str, tuple[str, ...]](),
            set[str](),
        ),
    )


@pytest.mark.parametrize(
    "document",
    [
        None,
        "{not json",
        dumps(obj=["plan"]),
        dumps(obj={"plan": "lints"}),
        dumps(obj={"plan": {"tools": "lints"}}),
        dumps(obj={"plan": {}}),
    ],
    ids=[
        "missing-file",
        "invalid-json",
        "non-object-document",
        "non-object-plan",
        "non-list-tools",
        "plan-without-tools",
    ],
)
def test_unusable_plans_fall_back_to_the_full_reset(
    document: str | None,
    tmp_path: Path,
) -> None:
    """Any request whose plan cannot be materialized is not scoped.

    Args:
        document: Request file contents, or ``None`` for no file.
        tmp_path: Disposable request store.

    """
    if document is not None:
        folder: Path = tmp_path / "owner-run"
        folder.mkdir()
        _ = (folder / "a.json").write_text(data=document, encoding="utf-8")
    expect_equal(
        actual=_roots(
            run=_run(root=tmp_path, owner=_owner(fingerprint="owner")),
            requests=(_request(request_id="a", fingerprint="one", plan=None),),
        ),
        expected=None,
    )


def test_observer_scope_result_falls_back_without_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requests with no usable plan defer to the owner's status.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=Check,
        name="exactus_root",
        value=tmp_path,
    )
    plans: tuple[dict[str, JsonValue] | None, ...] = (
        None,
        {"tools": "lints"},
        {"tools": []},
        {"tools": ["ghost"]},
    )
    for plan in plans:
        expect_equal(
            actual=private_call(
                owner=Check,
                name="_observer_scope_result",
                request=_request(
                    request_id="a",
                    fingerprint="one",
                    plan=plan,
                ),
            ),
            expected=None,
        )


def test_observer_scope_result_aggregates_requested_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the requested tools' reports decide an observer's outcome.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=Check,
        name="exactus_root",
        value=tmp_path,
    )
    for tool, status, passed in (
        ("LINTS", "PASS", True),
        ("DOCS", "FAIL", False),
    ):
        folder: Path = tmp_path / tool
        folder.mkdir()
        _ = (folder / "result.json").write_text(
            data=dumps(obj={"status": status, "passed": passed}),
            encoding="utf-8",
        )
    request: PipelineRequest = _request(
        request_id="a",
        fingerprint="one",
        plan={"tools": ["lints"]},
    )
    expect_equal(
        actual=private_call(
            owner=Check,
            name="_observer_scope_result",
            request=request,
        ),
        expected=True,
    )
    request = _request(
        request_id="b",
        fingerprint="one",
        plan={"tools": ["lints", "docs"]},
    )
    expect_equal(
        actual=private_call(
            owner=Check,
            name="_observer_scope_result",
            request=request,
        ),
        expected=False,
    )


def _catalog_tool(*, identifier: str) -> ToolSpec | None:
    """Return one real catalog tool specification.

    Args:
        identifier: Canonical tool name.

    Returns:
        The catalog entry.

    """
    spec: ToolSpec | None = GroupFinalConstants.exactus_catalog.tool(
        identifier=identifier,
    )
    require(value=spec)
    return spec


def _result(*, identifier: str) -> ToolRunResult:
    """Return one passing terminal result placeholder.

    Args:
        identifier: Tool the result belongs to.

    Returns:
        A PASS result with empty report paths.

    """
    empty: Path = Path()
    return ToolRunResult(
        tool=identifier,
        run_id="run",
        pipeline_run_id=None,
        status="PASS",
        passed=True,
        exit_code=0,
        duration_seconds=0.0,
        resume="",
        report=empty,
        report_json=empty,
        report_web=empty,
    )


def test_append_requested_tools_grows_the_plan_by_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-plan tools append after existing waves, ordered by depth.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=((_catalog_tool(identifier="lints"),),),
        ),
    )
    private_call(
        owner=Check,
        name="_append_requested_tools",
        run=run,
        missing={"docs", "readme"},
    )
    expect_equal(actual=run.order, expected=("lints", "docs", "readme"))
    expect_equal(actual=run.group_count, expected=2)
    expect_equal(
        actual={
            identifier: run.groups[identifier] for identifier in run.order
        },
        expected={"lints": 1, "docs": 2, "readme": 2},
    )
    expect_equal(
        actual=sorted(run.pending),
        expected=["docs", "lints", "readme"],
    )
    expect_equal(
        actual=(run.weights["docs"], run.weights["readme"]),
        expected=(0.0, 0.0),
    )


def test_scoped_apply_requeues_roots_dependents_and_retargets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``--lints`` join requeues lints + dependents and applies args.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=(
                (_catalog_tool(identifier="lints"),),
                (
                    _catalog_tool(identifier="docs"),
                    _catalog_tool(identifier="readme"),
                ),
            ),
        ),
    )
    results: dict[str, ToolRunResult] = {
        identifier: _result(identifier=identifier) for identifier in run.order
    }
    run.pending.clear()
    tool_arguments: dict[str, tuple[str, ...]] = dict.fromkeys(run.order, ())
    scope: tuple[set[str], dict[str, tuple[str, ...]], set[str]] = (
        {"lints"},
        {"lints": ("--verbose",)},
        set(),
    )
    private_call(
        owner=Check,
        name="_apply_scoped_requests",
        run=run,
        results=results,
        tool_arguments=tool_arguments,
        scope=scope,
    )
    expect_equal(actual=sorted(results), expected=["readme"])
    expect_equal(actual=sorted(run.pending), expected=["docs", "lints"])
    expect_equal(
        actual=tool_arguments["lints"],
        expected=("--verbose",),
    )


def test_invalidate_releases_dependents_for_a_fresh_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dependent's stale worker is released and requeued, not reset.

    Resetting it would rerun the tool against an in-flight dependency
    and could be adopted as the post-rerun result; releasing it lets
    the scheduler spawn a fresh worker once the dependency settles.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=(
                (_catalog_tool(identifier="lints"),),
                (_catalog_tool(identifier="docs"),),
            ),
        ),
    )
    _ = run.pending.pop("lints")
    _ = run.pending.pop("docs")
    run.handles["docs"] = cast(
        typ="ProcessHandle",
        val=object(),
    )
    run.fractions["docs"] = 0.5
    results: dict[str, ToolRunResult] = {
        "lints": _result(identifier="lints"),
    }
    private_call(
        owner=Check,
        name="_invalidate_tools",
        run=run,
        results=results,
        roots={"lints"},
        descriptors=(),
    )
    expect_equal(actual=sorted(results), expected=[])
    expect_equal(actual=sorted(run.pending), expected=["docs", "lints"])
    expect_equal(actual=sorted(run.handles), expected=[])
    expect_equal(actual=run.fractions["docs"], expected=0.0)
    expect_equal(
        actual=run.activities["docs"].status,
        expected="WAIT",
    )
    expect_equal(
        actual=run.activities["docs"].step,
        expected="waiting for rerun of lints",
    )
    rows: tuple[tuple[str, str, float, str, float | None], ...] = cast(
        typ="tuple[tuple[str, str, float, str, float | None], ...]",
        val=private_call(owner=Check, name="_progress_rows", run=run),
    )
    expect_in(
        member=("docs", "WAIT", 0.0, "waiting for rerun of lints", None),
        container=rows,
    )


def test_invalidate_holds_dependents_of_an_external_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dependent gated on an externally rerun tool is HELD.

    When the invalidating root's rerun lives outside the pipeline —
    an ``exactus --lints`` in another shell — the dependent is held,
    not merely queued: it must not schedule until that outside run
    settles.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=(
                (_catalog_tool(identifier="lints"),),
                (_catalog_tool(identifier="docs"),),
            ),
        ),
    )
    _ = run.pending.pop("lints")
    _ = run.pending.pop("docs")
    run.external["lints"] = RunRecord(
        kind="tool",
        identifier="lints",
        run_id="external-lints",
        pipeline_run_id=None,
        pid=getpid(),
        output=str(object=tmp_path / "LINTS"),
        targets=(),
        status="RUNNING",
        progress=0.5,
        step="all lints",
        detail="",
        created_at="2026-10-12T00:00:00+00:00",
        updated_at="2026-10-12T00:00:00+00:00",
        elapsed_seconds=0.0,
    )
    private_call(
        owner=Check,
        name="_invalidate_tools",
        run=run,
        results={"lints": _result(identifier="lints")},
        roots={"lints"},
        descriptors=(),
    )
    expect_equal(
        actual=run.activities["docs"].status,
        expected="HELD",
    )
    expect_in(member="docs", container=run.held)
    expect_in(member="docs", container=run.redo)
    rows: tuple[tuple[str, str, float, str, float | None], ...] = cast(
        typ="tuple[tuple[str, str, float, str, float | None], ...]",
        val=private_call(owner=Check, name="_progress_rows", run=run),
    )
    expect_in(
        member=("docs", "HELD", 0.0, "waiting for rerun of lints", None),
        container=rows,
    )
    expect_in(
        member=("lints", "REDO*", 0.5, "all lints", None),
        container=rows,
    )


def test_invalidate_keeps_reset_workers_out_of_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gracefully reset worker is the rerun itself, not a queue entry.

    Requeuing a tool whose worker survived the reset would spawn a
    duplicate run; it stays out of ``pending`` until it settles.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """

    class _Check:
        @classmethod
        def retire_worker(
            cls,
            *,
            run: PipelineRun,
            identifier: str,
            descriptors: tuple[Descriptor, ...],
            respawn: bool,
        ) -> None:
            """Reset or release one owned worker for a requeued tool.

            A worker that may keep running receives a graceful pmanager
            reset and keeps its process handle; a worker that must not —
            retargeted, unreachable, superseded externally, or gated on a
            dependency that is itself being rerun — is released so the
            scheduler respawns it.

            Args:
                run: Active pipeline state.
                identifier: Tool whose worker must retire or reset.
                descriptors: Shared pmanager discovery snapshot.
                respawn: Whether the worker must be released so the
                    scheduler respawns it, rather than reset in place.

            """
            _ = (
                cls,
                run,
                identifier,
                descriptors,
                respawn,
            )

    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    monkeypatch.setattr(
        target=Check,
        name="_retire_worker",
        value=_Check.retire_worker,
    )
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=(
                (_catalog_tool(identifier="lints"),),
                (_catalog_tool(identifier="docs"),),
            ),
        ),
    )
    _ = run.pending.pop("lints")
    _ = run.pending.pop("docs")
    run.handles["docs"] = cast(
        typ="ProcessHandle",
        val=object(),
    )
    private_call(
        owner=Check,
        name="_invalidate_tools",
        run=run,
        results={"lints": _result(identifier="lints")},
        roots={"lints"},
        descriptors=(),
    )
    expect_in(member="docs", container=run.handles)
    expect_not_in(member="docs", container=run.pending)


def test_pause_waiting_external_excludes_the_worker_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the owner process freezes, never the pmanager worker chain.

    The supervisor suspends its executor through ``SIGUSR1``; an
    external ``SIGSTOP`` landing while that signal is still queued
    leaves the worker stopped forever once ``SIGCONT`` wakes it.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    captured: dict[str, object] = {}

    def _pause_worker(*, descriptor: Descriptor, owner: str) -> bool:
        """Acquire an owner-scoped pause lease on one worker.

        Args:
            descriptor: Worker receiving the control request.
            owner: Run requiring the worker to remain paused.

        Returns:
            ``True`` when pmanager accepted the pause lease.

        """
        _ = (descriptor, owner)
        return True

    def _pause_tree(
        *,
        pid: int,
        exclude: Iterable[int] = (),
    ) -> None:
        """Suspend a process tree until ``resume_tree`` releases it.

        Unlike ``terminate_tree`` the tree stays registered and alive —
        heartbeats simply stop while the run waits for a pipeline wave.
        Unsupported on platforms without ``SIGSTOP``.

        Args:
            pid: Root process identifier.
            exclude: Process identifiers that must not receive ``SIGSTOP``.
                A worker already suspending itself through pmanager's
                ``SIGUSR1`` hook is one: an external ``SIGSTOP`` landing
                while that signal is still queued leaves the suspend
                handler pending, so the next ``SIGCONT`` wakes the process
                only for the stale handler to stop it again — permanently.

        """
        captured["pid"] = pid
        captured["exclude"] = tuple(exclude)

    def _descendants(*, pid: int) -> tuple[int, ...]:
        """Return descendants.

        Args:
            pid: Pid.

        Returns:
            The resulting value.

        """
        _ = pid
        return (7777, 8888)

    monkeypatch.setattr(
        target=exactus_main,
        name="pause_worker",
        value=_pause_worker,
    )
    monkeypatch.setattr(
        target=exactus_main,
        name="descendants",
        value=_descendants,
    )
    monkeypatch.setattr(
        target=exactus_main,
        name="pause_tree",
        value=_pause_tree,
    )
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=((_catalog_tool(identifier="lints"),),),
        ),
    )
    record: RunRecord = RunRecord(
        kind="tool",
        identifier="lints",
        run_id="external-lints",
        pipeline_run_id=None,
        pid=4321,
        output=str(object=tmp_path / "LINTS"),
        targets=(),
        status="RUNNING",
        progress=0.0,
        step="starting",
        detail="",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        elapsed_seconds=0.0,
    )
    descriptor: Descriptor = Descriptor(
        pid=5555,
        port=1,
        name="lints",
        context="external",
        args=(),
    )
    private_call(
        owner=Check,
        name="_pause_waiting_external",
        run=run,
        identifier="lints",
        record=record,
        descriptor=descriptor,
    )
    expect_equal(
        actual=captured["exclude"],
        expected=(5555, 7777, 8888),
    )
    expect_equal(actual=run.paused["lints"], expected=4321)


def test_retire_worker_releases_retargeted_and_ignores_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only live owned handles are retired; pending tools stay queued.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    run: PipelineRun = cast(
        typ="PipelineRun",
        val=private_call(
            owner=Check,
            name="_new_pipeline_run",
            pipeline="unified",
            run_id="r",
            waves=((_catalog_tool(identifier="lints"),),),
        ),
    )
    private_call(
        owner=Check,
        name="_retire_worker",
        run=run,
        identifier="lints",
        descriptors=(),
        respawn=False,
    )
    expect_equal(actual=sorted(run.handles), expected=[])
    run.handles["lints"] = cast(
        typ="ProcessHandle",
        val=object(),
    )
    private_call(
        owner=Check,
        name="_retire_worker",
        run=run,
        identifier="lints",
        descriptors=(),
        respawn=True,
    )
    expect_equal(actual=sorted(run.handles), expected=[])


def _register_live(
    *,
    registry: RunRegistry,
    identifier: str,
    run_id: str,
    out: Path,
    pid: int,
) -> None:
    """Claim one still-running record in a test registry.

    Args:
        registry: Registry under test.
        identifier: Tool identifier for the record.
        run_id: Run identifier.
        out: Report output directory.
        pid: Owning process identifier; distinct values avoid
            the same-pid reaper between claims.

    """
    _ = registry.claim(
        request=RunClaim(
            kind="tool",
            identifier=identifier,
            run_id=run_id,
            pipeline_run_id=None,
            pid=pid,
            output=out,
            targets=(),
        ),
    )


def test_status_serializes_live_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Check._status`` returns every live record as a JSON dict.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    registry: RunRegistry = RunRegistry(path=tmp_path / ".runtime" / "runs.db")
    _register_live(
        registry=registry,
        identifier="lints",
        run_id="r1",
        out=tmp_path / "LINTS",
        pid=getpid(),
    )
    rows: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(owner=Check, name="_status", names=()),
    )
    require(value=rows)
    row: dict[str, JsonValue] = rows[0]
    expect_equal(actual=row["run_id"], expected="r1")
    expect_equal(actual=row["identifier"], expected="lints")
    expect_equal(actual=row["kind"], expected="tool")
    expect_equal(actual=row["status"], expected="RUNNING")
    expect_not_in(member="process", container=row)
    _ = dumps(obj=rows)


def test_status_filters_named_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Check._status`` resolves NAME operands like ``--clear``.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """

    def _process_exists(*, pid: int) -> bool:
        """Return process exists.

        Args:
            pid: Pid.

        Returns:
            The resulting value.

        """
        _ = pid
        return True

    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    monkeypatch.setattr(
        target="exactus.tools.common.registry.process_exists",
        name=_process_exists,
    )
    registry: RunRegistry = RunRegistry(path=tmp_path / ".runtime" / "runs.db")
    _register_live(
        registry=registry,
        identifier="lints",
        run_id="r1",
        out=tmp_path / "LINTS",
        pid=400001,
    )
    _register_live(
        registry=registry,
        identifier="docs",
        run_id="r2",
        out=tmp_path / "DOCS",
        pid=400002,
    )
    rows: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(owner=Check, name="_status", names=("lints",)),
    )
    expect_equal(
        actual=[row["identifier"] for row in rows],
        expected=["lints"],
    )
    with pytest.raises(expected_exception=ValueError, match="--status"):
        _ = private_call(owner=Check, name="_status", names=("nope",))


def test_status_all_embeds_live_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Check._status_all`` lists identities and their live records.

    Args:
        tmp_path: Disposable results root.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=Check, name="exactus_root", value=tmp_path)
    runs_db: Path = tmp_path / ".runtime" / "runs.db"
    registry: RunRegistry = RunRegistry(path=runs_db)
    _register_live(
        registry=registry,
        identifier="lints",
        run_id="r1",
        out=tmp_path / "LINTS",
        pid=getpid(),
    )
    _ = authkey(runtime=tmp_path / ".runtime")
    identity: RunIdentity = RunIdentity(
        root_pid=getpid(),
        run_id="external-run",
        runs_db=str(object=runs_db),
        created_at=1.0,
        instance_id="i1",
    )

    def _discover(
        *,
        authkey: bytes,
        timeout: float = 0.3,
        workers: int = 32,
        full_scan: bool = True,
    ) -> list[RunIdentity]:
        """Discover running Exactus processes without a registry.

        Args:
            authkey: Shared private authentication secret.
            timeout: Per-socket operation timeout.
            workers: Maximum concurrent interrogation workers.
            full_scan: Whether to include all visible listening processes.

        Returns:
            Verified identities sorted by process identifier.


        """
        _ = (authkey, timeout, workers, full_scan)
        return [identity]

    monkeypatch.setattr(
        target=exactus_main,
        name="discover",
        value=_discover,
    )
    rows: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=private_call(owner=Check, name="_status_all"),
    )
    require(value=rows)
    entry: dict[str, JsonValue] = rows[0]
    expect_equal(actual=entry["run_id"], expected="external-run")
    expect_equal(actual=entry["root_pid"], expected=getpid())
    runs: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=entry["runs"],
    )
    expect_equal(actual=[r["run_id"] for r in runs], expected=["r1"])
    _ = dumps(obj=rows)
