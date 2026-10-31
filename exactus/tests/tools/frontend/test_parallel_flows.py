# Copyright (c) 2026
"""Verify concurrent real-browser replay and ordered workflow evidence."""

from __future__ import annotations

from json import dumps
from threading import Barrier, Lock
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record import run
from exactus.tools.record.workspace_actions import (
    Event,
    actions_to_events,
    build_flow,
    build_workspace,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue


def test_parallel_flows_overlap_and_preserve_isolation_and_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlap bounded workers with isolated pages and monotonic progress.

    Args:
        tmp_path: Workspace and runtime artifact directory.
        monkeypatch: Instrument the real workflow executor.

    """
    identities: list[str] = [f"flow-{index}" for index in range(4)]
    flows: list[Event] = [
        build_flow(
            flow_id=identity,
            name=identity,
            events=actions_to_events(
                actions=[{"type": "navigation", "url": "about:blank"}],
                flow_id=identity,
            ),
        )
        for identity in identities
    ]
    path: Path = tmp_path / "parallel.pwflow.json"
    path.write_text(
        data=dumps(obj=build_workspace(flows=flows)),
        encoding="utf-8",
    )
    barrier: Barrier = Barrier(parties=2, timeout=15)
    lock: Lock = Lock()
    active: int = 0
    maximum: int = 0
    execute: Callable[..., Event] = run.FlowRunner.run
    progress: list[Event] = []

    def overlapping_run(
        self: run.FlowRunner,
        *,
        page: Page,
        message: Event,
    ) -> Event:
        """Require another live browser before replaying the real actions.

        Args:
            self: Real flow executor.
            page: Worker-local browser page.
            message: Recorded flow and action definitions.

        Returns:
            Real execution evidence.

        """
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            page.evaluate(
                expression="value => { window.name = value; }",
                arg=message["flow_id"],
            )
            barrier.wait()
            expect_equal(
                actual=page.evaluate(expression="window.name"),
                expected=message["flow_id"],
            )
            return execute(self=self, page=page, message=message)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(
        target=run.FlowRunner,
        name="run",
        value=overlapping_run,
    )
    report: Event = run.run_workspace(
        path=path,
        output=tmp_path / "out",
        browser=run.BrowserOptions(workers=2, emit=progress.append),
    )
    expect_equal(actual=report["status"], expected="succeeded")
    expect_equal(actual=maximum, expected=2)
    results: JsonValue = report["flows"]
    expect_true(condition=isinstance(results, list))
    if isinstance(results, list):
        expect_equal(
            actual=[
                item["flow_id"] for item in results if isinstance(item, dict)
            ],
            expected=identities,
        )
    expect_equal(actual=progress[-1]["completed"], expected=4)
    fractions: list[float] = [
        float(str(object=item["fraction"])) for item in progress
    ]
    expect_equal(actual=fractions, expected=sorted(fractions))
    expect_equal(actual=fractions[-1], expected=1.0)
    expect_true(condition=all(value < 1 for value in fractions[:-1]))
    expect_true(condition=(tmp_path / "out/junit.xml").is_file())


def test_workers_must_be_positive(tmp_path: Path) -> None:
    """Reject invalid concurrency before accessing the saved workspace.

    Args:
        tmp_path: Unused workspace location.

    """
    with pytest.raises(expected_exception=ValueError, match="positive"):
        run.run_workspace(
            path=tmp_path / "missing.json",
            output=tmp_path / "out",
            browser=run.BrowserOptions(workers=0),
        )
