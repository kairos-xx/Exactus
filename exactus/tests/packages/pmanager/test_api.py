# Copyright (c) 2026 João Lopes.
"""Public API contract tests."""

from pathlib import Path
from typing import Final, final

import pytest

from exactus.packages.pmanager import (
    Context,
    ExecutionPlan,
    Orchestrator,
    ProcessKey,
    ProcessNotFoundError,
    State,
)
from exactus.tests.common.support import expect_equal


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "pmanager"
    )


def test_public_api_plan_and_context() -> None:
    """Exercise planning and the context-bound facade."""
    api: Orchestrator = Orchestrator.from_file(
        path=Constants.root / "processes.json",
    )
    context: Context = api.context(name="api-test")
    plan: ExecutionPlan = context.plan(arguments=("--job", "42"), process="E")
    expect_equal(
        actual=plan.root,
        expected=ProcessKey(
            name="E",
            context="api-test",
            arguments=("--job", "42"),
        ),
    )
    expect_equal(
        actual={entry.key.name for entry in plan.entries},
        expected={"A", "B", "C", "D", "E"},
    )


def test_public_api_missing_status() -> None:
    """Expose a stable domain exception instead of transport details."""
    api: Orchestrator = Orchestrator.from_file(
        path=Constants.root / "processes.json",
    )
    with pytest.raises(expected_exception=ProcessNotFoundError):
        api.status(name="A", context="definitely-not-live")


def test_public_state_contract_includes_paused() -> None:
    """Keep PAUSED in the stable public lifecycle model."""
    expect_equal(actual=State.PAUSED.value, expected="paused")
