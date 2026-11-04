# Copyright (c) 2026
"""Verify transactional pipeline ownership and observer generations."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.pipeline_supervisor import (
    Constants,
    PipelineClaim,
    PipelineCoordinator,
    PipelineOwner,
    PipelineRequest,
)

if TYPE_CHECKING:
    from pathlib import Path


def _alive(*, pid: int) -> bool:
    """Treat positive test process identifiers as live.

    Args:
        pid: Test process identifier.

    Returns:
        Whether the identifier is positive.

    """
    return pid > 0


@pytest.fixture
def coordinator(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> PipelineCoordinator:
    """Create a supervisor whose synthetic processes stay live.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest patching helper.

    Returns:
        Isolated transactional supervisor.

    """
    monkeypatch.setattr(
        target=import_module(name="exactus.tools.common.pipeline_supervisor"),
        name="process_exists",
        value=_alive,
    )
    return PipelineCoordinator(runtime=tmp_path / ".runtime")


def _claim_owner(
    *,
    coordinator: PipelineCoordinator,
    pipeline: str = "unified",
    fingerprint: str = "same",
) -> PipelineClaim:
    """Claim one pipeline owner.

    Args:
        coordinator: Isolated transactional supervisor.
        pipeline: Canonical pipeline identifier.
        fingerprint: Effective configuration hash.

    Returns:
        Owner admission decision.

    """
    claim: PipelineClaim = coordinator.claim(
        pipeline=pipeline,
        run_id=f"owner-{pipeline}",
        pid=101,
        fingerprint=fingerprint,
        tty=None,
    )
    expect_equal(actual=claim.mode, expected="owner")
    return claim


def test_claims_are_isolated_by_pipeline(
    coordinator: PipelineCoordinator,
) -> None:
    """Independent pipeline names elect independent owners.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    unified: PipelineClaim = _claim_owner(coordinator=coordinator)
    fast: PipelineClaim = _claim_owner(
        coordinator=coordinator,
        pipeline="all-fast",
    )
    expect_equal(actual=unified.owner.pipeline, expected="unified")
    expect_equal(actual=fast.owner.pipeline, expected="all-fast")
    expect_false(condition=unified.owner.run_id == fast.owner.run_id)


def test_connection_recreates_schema_after_runtime_reset(
    coordinator: PipelineCoordinator,
) -> None:
    """A deleted database is recreated before the next owner query.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    coordinator.path.unlink()
    expect_equal(
        actual=coordinator.requests(
            pipeline_run_id="interrupted-owner",
            state=Constants.pending,
        ),
        expected=(),
    )


def test_compatible_claim_requests_a_shared_generation(
    coordinator: PipelineCoordinator,
) -> None:
    """A compatible collision observes its owner and requests one reset.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    owner: PipelineClaim = _claim_owner(coordinator=coordinator)
    observer: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="observer",
        pid=202,
        fingerprint="same",
        tty="/dev/test",
    )
    expect_equal(actual=observer.mode, expected="observer")
    expect_equal(actual=observer.owner.run_id, expected=owner.owner.run_id)
    request: PipelineRequest | None = observer.request
    expect_true(condition=request is not None)
    if request is None:
        return
    expect_equal(actual=request.state, expected=Constants.pending)
    expect_false(
        condition=coordinator.seal(
            pipeline="unified",
            run_id=owner.owner.run_id,
        ),
    )
    coordinator.acknowledge(
        requests=(request,),
        generation=2,
        detail="generation 2 started",
    )
    applied: PipelineRequest | None = coordinator.get(request_id="observer")
    expect_true(condition=applied is not None)
    if applied is None:
        return
    expect_equal(actual=applied.state, expected=Constants.applied)
    expect_equal(actual=applied.generation, expected=2)
    expect_true(
        condition=coordinator.seal(
            pipeline="unified",
            run_id=owner.owner.run_id,
        ),
    )


def test_incompatible_and_sealed_claims_wait(
    coordinator: PipelineCoordinator,
) -> None:
    """Sealed owners block joins; different configurations join as observers.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    owner: PipelineClaim = _claim_owner(coordinator=coordinator)
    incompatible: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="different",
        pid=303,
        fingerprint="different",
        tty=None,
    )
    expect_equal(actual=incompatible.mode, expected="observer")
    joined: PipelineRequest | None = incompatible.request
    expect_true(condition=joined is not None)
    if joined is None:
        return
    expect_equal(actual=joined.fingerprint, expected="different")
    coordinator.acknowledge(
        requests=(joined,),
        generation=2,
        detail="generation 2 started",
    )
    expect_true(
        condition=coordinator.seal(
            pipeline="unified",
            run_id=owner.owner.run_id,
        ),
    )
    sealed: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="late",
        pid=404,
        fingerprint="same",
        tty=None,
    )
    expect_equal(actual=sealed.mode, expected="wait")
    expect_equal(actual=sealed.detail, expected="owner is finalizing")


def test_acknowledge_persists_a_merged_plan_fingerprint(
    coordinator: PipelineCoordinator,
) -> None:
    """A merged/retargeted reset stores the new owner plan hash.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    _claim_owner(coordinator=coordinator)
    observer: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="observer",
        pid=202,
        fingerprint="merged",
        tty=None,
    )
    request: PipelineRequest | None = observer.request
    expect_true(condition=request is not None)
    if request is None:
        return
    coordinator.acknowledge(
        requests=(request,),
        generation=2,
        detail="generation 2 started",
        fingerprint="merged-plan-hash",
    )
    stored: PipelineOwner | None = coordinator.owner(pipeline="unified")
    expect_true(condition=stored is not None)
    if stored is None:
        return
    expect_equal(actual=stored.fingerprint, expected="merged-plan-hash")
    expect_equal(actual=stored.generation, expected=2)


def test_acknowledge_without_a_plan_keeps_the_fingerprint(
    coordinator: PipelineCoordinator,
) -> None:
    """A generation-only reset leaves the owner plan hash untouched.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    _ = _claim_owner(coordinator=coordinator)
    observer: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="observer",
        pid=202,
        fingerprint="same",
        tty=None,
    )
    request: PipelineRequest | None = observer.request
    expect_true(condition=request is not None)
    if request is None:
        return
    coordinator.acknowledge(
        requests=(request,),
        generation=2,
        detail="generation 2 started",
    )
    stored: PipelineOwner | None = coordinator.owner(pipeline="unified")
    expect_true(condition=stored is not None)
    if stored is None:
        return
    expect_equal(actual=stored.fingerprint, expected="same")
    expect_equal(actual=stored.generation, expected=2)


def test_terminal_owner_is_observable_and_replaceable(
    coordinator: PipelineCoordinator,
) -> None:
    """Observers see terminal state and a later run can own the pipeline.

    Args:
        coordinator: Isolated transactional supervisor.

    """
    first: PipelineClaim = _claim_owner(coordinator=coordinator)
    expect_true(
        condition=coordinator.seal(
            pipeline="unified",
            run_id=first.owner.run_id,
        ),
    )
    coordinator.finish(
        pipeline="unified",
        run_id=first.owner.run_id,
        state="DONE",
    )
    terminal: PipelineOwner | None = coordinator.owner(pipeline="unified")
    expect_true(condition=terminal is not None)
    if terminal is None:
        return
    expect_equal(actual=terminal.state, expected="DONE")
    second: PipelineClaim = coordinator.claim(
        pipeline="unified",
        run_id="next-owner",
        pid=505,
        fingerprint="new",
        tty=None,
    )
    expect_equal(actual=second.mode, expected="owner")
    expect_equal(actual=second.owner.run_id, expected="next-owner")
