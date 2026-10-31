# Copyright (c) 2026 Project contributors
"""Workspace loading rejects unreadable, unsupported, and duplicated data."""

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from exactus.tools.record.model import (
    Flow,
    FlowEdge,
    ValueType,
    VariableDefinition,
    VariableScope,
    Workspace,
)
from exactus.tools.record.store import (
    JsonValue,
    WorkspaceCodec,
    WorkspaceError,
)


def _document(*, tmp_path: Path) -> dict[str, JsonValue]:
    """Build a complete current-schema document for rejection cases.

    Args:
        tmp_path: Tmp path.

    Returns:
        The resulting value.

    """
    _ = tmp_path
    workspace: Workspace = Workspace(
        flows=(
            Flow(
                flow_id="a",
                name="A",
                task_description="",
                expected_behavior="",
                notes="",
            ),
        ),
        edges=(),
    )
    variable: VariableDefinition = VariableDefinition(
        name="x",
        value_type=ValueType.STRING,
        scope=VariableScope.WORKSPACE,
        default_value="a",
    )
    workspace = replace(workspace, variables=(variable,))
    return cast(
        typ="dict[str, JsonValue]",
        val=WorkspaceCodec.to_json_value(workspace=workspace),
    )


def test_load_rejects_unreadable_files(tmp_path: Path) -> None:
    """Missing files and malformed JSON become ``WorkspaceError``.

    Args:
        tmp_path: Tmp path.

    """
    with pytest.raises(expected_exception=WorkspaceError):
        WorkspaceCodec.load(path=tmp_path / "missing.json")
    broken: Path = tmp_path / "broken.json"
    broken.write_text(data="{not json", encoding="utf-8")
    with pytest.raises(expected_exception=WorkspaceError):
        WorkspaceCodec.load(path=broken)


def test_unsupported_version_is_rejected(tmp_path: Path) -> None:
    """Unknown workspace versions are refused.

    Args:
        tmp_path: Tmp path.

    """
    document: dict[str, JsonValue] = _document(tmp_path=tmp_path)
    document["version"] = 999
    with pytest.raises(expected_exception=WorkspaceError):
        WorkspaceCodec.from_json_value(value=document)


def test_duplicate_flow_ids_are_rejected(tmp_path: Path) -> None:
    """Two flows with one identifier cannot be loaded.

    Args:
        tmp_path: Tmp path.

    """
    document: dict[str, JsonValue] = _document(tmp_path=tmp_path)
    flows: list[JsonValue] = cast(typ="list[JsonValue]", val=document["flows"])
    document["flows"] = [flows[0], flows[0]]
    with pytest.raises(expected_exception=WorkspaceError):
        WorkspaceCodec.from_json_value(value=document)


def test_duplicate_variable_names_are_rejected(tmp_path: Path) -> None:
    """Two variables with one name cannot be loaded.

    Args:
        tmp_path: Tmp path.

    """
    document: dict[str, JsonValue] = _document(tmp_path=tmp_path)
    variables: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=document["variables"],
    )
    document["variables"] = [variables[0], variables[0]]
    with pytest.raises(expected_exception=WorkspaceError):
        WorkspaceCodec.from_json_value(value=document)


def test_duplicate_flow_edges_are_rejected() -> None:
    """Duplicate transitions cannot be imported as an ambiguous graph."""
    first: Flow = Flow(
        flow_id="a",
        name="A",
        task_description="",
        expected_behavior="",
        notes="",
    )
    second: Flow = replace(first, flow_id="b", name="B")
    edge: FlowEdge = FlowEdge(source_flow_id="a", target_flow_id="b")
    workspace: Workspace = Workspace(flows=(first, second), edges=(edge,))
    document: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=WorkspaceCodec.to_json_value(workspace=workspace),
    )
    edges: list[JsonValue] = cast(typ="list[JsonValue]", val=document["edges"])
    document["edges"] = [edges[0], edges[0]]
    with pytest.raises(
        expected_exception=WorkspaceError,
        match="duplicate Flow edges",
    ):
        WorkspaceCodec.from_json_value(value=document)
