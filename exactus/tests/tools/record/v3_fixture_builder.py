# Copyright (c) 2026 Project contributors
"""Write the frozen version-3 workspace fixtures used by migration tests.

Run ``python -m exactus.tests.tools.record.v3_fixture_builder FOLDER
BASE.pwflow.json`` to regenerate the files; commit the result.
"""

from __future__ import annotations

from copy import deepcopy
from json import dumps, loads
from pathlib import Path
from sys import argv
from typing import Final, cast, final

from exactus.tools.common.json_types import JsonValue
from exactus.tools.record.store import WorkspaceCodec

type Document = dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        sourced: Grouped module constant.
        edge_modes: Grouped module constant.
        condition: Grouped module constant.

    """

    sourced: Final[frozenset[str]] = frozenset({"environment", "secret"})
    edge_modes: Final[tuple[str, ...]] = (
        "always",
        "condition",
        "fallback",
        "retry",
        "finally",
    )
    condition: Final[str] = "__EXACTUS_FLOW__.vars.Count > 1"


def _event(*, template: Document, index: int, **fields: JsonValue) -> Document:
    """Copy the template action and override the given fields.

    Args:
        template: A valid, assertion-free action document.
        index: Position in the flow; also names the action.
        **fields: Document keys to override.

    Returns:
        The new action document.

    """
    event: Document = deepcopy(x=template)
    event.update(
        {"id": f"fx-{index}", "sequence": index, "elapsed_ms": index * 100},
    )
    event.update(fields)
    return event


def build(*, base: Document) -> dict[str, Document]:
    """Derive every frozen fixture from the demo workspace.

    Args:
        base: The demo workspace document.

    Returns:
        Fixture name to raw (not yet canonicalized) document.

    """
    flows: list[Document] = cast(typ="list[Document]", val=base["flows"])
    first: Document = cast(typ="list[Document]", val=flows[0]["events"])[0]
    template: Document = deepcopy(x=first)
    template.update(
        {"kind": "javascript", "layer": "interaction", "url": None},
    )
    cast(typ="Document", val=template["contract"])["postconditions"] = []
    edges: list[Document] = cast(typ="list[Document]", val=base["edges"])
    flow_id: str = cast(typ="str", val=flows[0]["id"])
    fixtures: dict[str, Document] = {}
    chain: Document = deepcopy(x=base)
    cast(typ="list[Document]", val=chain["flows"])[0]["events"] = [
        _event(
            template=template,
            index=0,
            kind="set_variable",
            label="Set count",
            payload=dumps(obj={"value": "3", "value_type": "integer"}),
            output_variable="Count",
        ),
        _event(
            template=template,
            index=1,
            label="Add one",
            payload="__EXACTUS_FLOW__.vars.Count + 1",
            output_variable="Next",
            sandbox=True,
            when_expression="__EXACTUS_FLOW__.vars.Count > 1",
        ),
        _event(
            template=template,
            index=2,
            kind="set_variable",
            label="Describe",
            payload=dumps(obj={"value": "n={{Next}}", "value_type": "string"}),
            output_variable="Label",
        ),
    ]
    fixtures["guards-and-chain"] = chain
    modes: Document = deepcopy(x=base)
    modes["edges"] = [
        dict(
            edges[0],
            mode=mode,
            priority=priority,
            condition_expression=Constants.condition
            if mode == "condition"
            else None,
        )
        for priority, mode in enumerate(iterable=Constants.edge_modes)
    ]
    fixtures["edges-all-modes"] = modes
    scopes: Document = deepcopy(x=base)
    scopes["variables"] = [
        {
            "name": f"V {scope}",
            "value_type": "string",
            "scope": scope,
            "flow_id": flow_id if scope == "flow" else None,
            "default_value": None if scope in Constants.sourced else "x",
            "source_name": f"SRC_{scope}".upper()
            if scope in Constants.sourced
            else None,
        }
        for scope in ("flow", "run", "workspace", "environment", "secret")
    ]
    fixtures["variables-all-scopes"] = scopes
    legacy: Document = deepcopy(x=base)
    cast(typ="list[Document]", val=legacy["flows"])[0]["events"] = [
        _event(template=template, index=0, label="Fetch", payload="7"),
        _event(
            template=template,
            index=1,
            label="Use",
            payload="{{previous}}",
            receive_previous=True,
        ),
    ]
    fixtures["legacy-receive-previous"] = legacy
    return fixtures


def canonical(*, document: Document) -> Document:
    """Pass a document through the codec so it holds only canonical keys.

    Args:
        document: A loadable version-3 workspace document.

    Returns:
        The codec's own serialization of that workspace.

    """
    return cast(
        typ="Document",
        val=WorkspaceCodec.to_json_value(
            workspace=WorkspaceCodec.from_json_value(value=document),
        ),
    )


def main() -> None:
    """Write fixtures to the folder named by the first argument."""
    target: Path = Path(argv[1])
    base: Document = cast(
        typ="Document",
        val=loads(s=Path(argv[2]).read_text(encoding="utf-8")),
    )
    target.mkdir(parents=True, exist_ok=True)
    for name, document in build(base=base).items():
        frozen: Document = (
            document
            if name.startswith("legacy")
            else canonical(document=document)
        )
        (target / f"{name}.pwflow.json").write_text(
            data=dumps(obj=frozen, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
