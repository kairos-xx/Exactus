# Copyright (c) 2026 Project contributors
"""Prove the frozen version-3 workspaces load, round-trip and migrate."""

from __future__ import annotations

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import expect_equal
from exactus.tools.record.store import WorkspaceCodec, WorkspaceError

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import (
        TimelineEvent,
        VariableDefinition,
        Workspace,
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        folder: Grouped module constant.
        canonical: Grouped module constant.

    """

    folder: Final[Path] = Path(__file__).resolve().parent / "fixtures" / "v3"
    canonical: Final[tuple[str, ...]] = (
        "guards-and-chain",
        "edges-all-modes",
        "variables-all-scopes",
    )


def _load(*, name: str) -> Workspace:
    """Load one frozen fixture through the codec.

    Args:
        name: Fixture name without extension.

    Returns:
        The parsed workspace.

    """
    return WorkspaceCodec.load(path=Constants.folder / f"{name}.pwflow.json")


@pytest.mark.parametrize(argnames="name", argvalues=Constants.canonical)
def test_canonical_fixture_round_trips(name: str) -> None:
    """Serialize a canonical fixture back to the very document read.

    Args:
        name: Fixture name without extension.

    """
    path: Path = Constants.folder / f"{name}.pwflow.json"
    document: JsonValue = loads(s=path.read_text(encoding="utf-8"))
    expect_equal(
        actual=WorkspaceCodec.to_json_value(workspace=_load(name=name)),
        expected=document,
    )


def test_edge_modes_are_all_present() -> None:
    """Keep one edge of every transition mode."""
    modes: set[str] = {
        edge.mode.value for edge in _load(name="edges-all-modes").edges
    }
    expect_equal(
        actual=modes,
        expected={"always", "condition", "fallback", "retry", "finally"},
    )


def test_condition_edge_requires_an_expression() -> None:
    """Reject a conditional edge that carries no expression."""
    path: Path = Constants.folder / "edges-all-modes.pwflow.json"
    document: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=path.read_text(encoding="utf-8")),
    )
    for edge in cast(typ="list[dict[str, JsonValue]]", val=document["edges"]):
        if edge["mode"] == "condition":
            edge["condition_expression"] = None
    with pytest.raises(expected_exception=WorkspaceError, match="expression"):
        WorkspaceCodec.from_json_value(value=document)


def test_variable_scopes_are_all_present() -> None:
    """Keep one variable of every persisted scope."""
    variables: tuple[VariableDefinition, ...] = _load(
        name="variables-all-scopes",
    ).variables
    scopes: set[str] = {item.scope.value for item in variables}
    expect_equal(
        actual=scopes,
        expected={"flow", "run", "workspace", "environment", "secret"},
    )


def test_receive_previous_migrates_to_a_named_result() -> None:
    """Name the earlier result and rewrite the reader's token."""
    events: tuple[TimelineEvent, ...] = (
        _load(name="legacy-receive-previous").flows[0].events
    )
    expect_equal(actual=events[0].output_variable, expected="Fetch Result")
    expect_equal(actual=events[1].payload, expected="{{Fetch Result}}")
