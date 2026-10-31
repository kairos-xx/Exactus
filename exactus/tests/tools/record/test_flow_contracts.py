# Copyright (c) 2026 Project contributors
"""Bind the locked v4 contract files to FLOW.md and the real v3 surface."""

from __future__ import annotations

from json import loads
from pathlib import Path
from re import MULTILINE, findall
from typing import Final, cast, final

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tools.common.json_types import JsonValue
from exactus.tools.record.flow_inventory import build_inventory

type Row = dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        tests: Grouped module constant.
        record: Grouped module constant.
        spec: Grouped module constant.
        document: Grouped module constant.
        action_count: Grouped module constant.
        spec_row_count: Grouped module constant.
        headings: Grouped module constant.
        limits: Grouped module constant.
        void_actions: Grouped module constant.
        action_keys: Grouped module constant.
        slot_keys: Grouped module constant.
        port_keys: Grouped module constant.
        type_aliases: Grouped module constant.
        spec_row_pattern: Grouped module constant.

    """

    tests: Final[Path] = Path(__file__).resolve().parent
    record: Final[Path] = tests.parents[2] / "tools" / "record"
    spec: Final[Path] = tests.parents[3] / "docs" / "todo" / "FLOW.md"
    document: Final[Path] = (
        tests.parents[3] / "docs" / "todo" / "FLOW-CONTRACT.md"
    )
    action_count: Final[int] = 48
    spec_row_count: Final[int] = 43
    headings: Final[tuple[str, ...]] = (
        "## Schema version",
        "## Persisted names",
        "## Unknown-field policy",
        "## Limits",
        "## Type vocabulary",
        "## Stable identity",
        "## Sensitivity",
        "## Evaluation timing",
        "## Receipt package",
        "## Device ownership",
        "## JavaScript compatibility",
        "## Selector and JavaScript contracts",
    )
    limits: Final[tuple[str, ...]] = (
        "max_program_depth",
        "max_nodes_per_flow",
        "max_graph_nodes",
        "max_iterations_default",
        "max_iterations_hard",
        "max_label_chars",
        "max_receipt_bytes",
        "max_receipt_flows",
        "max_value_preview_bytes",
    )
    void_actions: Final[frozenset[str]] = frozenset(
        {
            "pointer",
            "input_text",
            "select_option",
            "check",
            "uncheck",
            "keystroke",
            "wait_duration",
        },
    )
    action_keys: Final[frozenset[str]] = frozenset(
        {
            "id",
            "label",
            "status",
            "spec_row",
            "inputs",
            "outputs",
            "conditional_outputs",
            "dynamic_inputs",
            "dynamic_outputs",
            "structure",
        },
    )
    slot_keys: Final[frozenset[str]] = frozenset(
        {
            "slot",
            "type",
            "required",
            "item_type",
            "many",
            "sensitivity",
            "exposes_to",
        },
    )
    port_keys: Final[frozenset[str]] = frozenset(
        {"port", "type", "item_type", "primary", "nullable", "sensitivity"},
    )
    type_aliases: Final[tuple[tuple[str, str], ...]] = (
        ("variable reference", "variable_ref"),
        ("variable type", "variable_type"),
        ("advanced expression", "expression"),
        ("typed value", "inferred"),
        ("many typed values", "inferred"),
        ("many key/value pairs", "json"),
        ("list/object view", "list"),
        ("json object", "json"),
        ("integer | float", "number"),
        ("inferred nullable/union type", "inferred"),
        ("inferred nullable type", "inferred"),
    )
    spec_row_pattern: Final[str] = "`([a-z_./]+):\\s*([^`]+)`"


def _contract(*, name: str) -> Row:
    """Read one committed contract file.

    Args:
        name: File name inside the contract fixture folder.

    Returns:
        The parsed JSON object.

    """
    path: Path = Constants.tests / "fixtures" / "contract" / name
    return cast(typ="Row", val=loads(s=path.read_text(encoding="utf-8")))


def _rows(*, parent: Row, key: str) -> list[Row]:
    """Return a list of JSON objects stored under a key.

    Args:
        parent: Object that holds the list.
        key: Key of the list.

    Returns:
        The list, or an empty list when the key is absent.

    """
    return cast(typ="list[Row]", val=parent.get(key, []))


def _strings(*, parent: Row, key: str) -> list[str]:
    """Return a list of strings stored under a key.

    Args:
        parent: Object that holds the list.
        key: Key of the list.

    Returns:
        The list of strings.

    """
    return cast(typ="list[str]", val=parent[key])


def _actions() -> list[Row]:
    """Return the action rows of the action contract.

    Returns:
        One mapping per action.

    """
    return _rows(parent=_contract(name="action-contract.json"), key="actions")


def _vocabulary() -> set[str]:
    """Return the contract's type vocabulary.

    Returns:
        Every legal type name.

    """
    return set(
        _strings(parent=_contract(name="action-contract.json"), key="types"),
    )


def _spec_text() -> str:
    """Read the specification.

    Returns:
        The full text of FLOW.md.

    """
    return Constants.spec.read_text(encoding="utf-8")


def _between(*, text: str, start: str, end: str) -> str:
    """Slice the text that follows a start marker, up to an end marker.

    Args:
        text: Text to slice.
        start: Marker after which the slice begins.
        end: Marker, after the start, where it ends.

    Returns:
        The text after ``start`` and before ``end``, markers excluded.

    """
    begin: int = text.index(start) + len(start)
    return text[begin : text.index(end, begin)]


def _spec_table() -> list[tuple[str, str, str]]:
    """Parse the FLOW.md input/output matrix.

    Returns:
        One tuple per row: action cell, required-inputs cell, outputs cell.

    """
    lines: list[str] = _spec_text().splitlines()
    head: int = next(
        (
            index
            for index, line in enumerate(iterable=lines)
            if line.startswith(
                "| Action | Required inputs | Optional inputs |",
            )
        ),
    )
    rows: list[tuple[str, str, str]] = []
    for line in lines[head + 2 :]:
        if not line.startswith("|"):
            break
        cells: list[str] = [
            part.strip() for part in line.strip("|").split(sep="|")
        ]
        rows.append((cells[0], cells[1], " | ".join(cells[3:])))
    return rows


def _normal(*, spec_type: str) -> str:
    """Map the spec's wording of a type to a contract type name.

    Args:
        spec_type: Type text from the spec table.

    Returns:
        The contract type name, or the cleaned text when there is no alias.

    """
    base: str = spec_type.strip().removesuffix("?")
    if base.startswith("list<"):
        return "list"
    if base.startswith("{"):
        return "device_state"
    return dict(Constants.type_aliases).get(base, base)


def test_contract_has_the_spec_counts() -> None:
    """Hold every spec row and the exact number of actions."""
    actions: list[Row] = _actions()
    expect_equal(actual=len(actions), expected=Constants.action_count)
    expect_equal(actual=len(_spec_table()), expected=Constants.spec_row_count)
    spec_rows: set[str] = {
        cast(typ="str", val=row["spec_row"]) for row in actions
    }
    expect_equal(actual=len(spec_rows), expected=Constants.spec_row_count)
    ids: list[str] = [cast(typ="str", val=row["id"]) for row in actions]
    expect_equal(actual=len(ids), expected=len(set(ids)))


def test_actions_are_well_formed() -> None:
    """Enforce the shape rules of actions, slots and ports."""
    vocabulary: set[str] = _vocabulary()
    for row in _actions():
        name: str = str(object=row["id"])
        expect_true(
            condition=set(row) <= Constants.action_keys,
            message=f"{name}: unknown action key",
        )
        expect_in(member=row["status"], container={"v3", "new"})
        slots: list[Row] = _rows(parent=row, key="inputs")
        ports: list[Row] = _rows(parent=row, key="outputs")
        extras: list[Row] = _rows(parent=row, key="conditional_outputs")
        slot_names: list[JsonValue] = [item["slot"] for item in slots]
        port_names: list[JsonValue] = [item["port"] for item in ports + extras]
        expect_equal(actual=len(slot_names), expected=len(set(slot_names)))
        expect_equal(actual=len(port_names), expected=len(set(port_names)))
        for slot in slots:
            expect_true(
                condition=set(slot) <= Constants.slot_keys,
                message=f"{name}: unknown slot key",
            )
            expect_in(member=slot["type"], container=vocabulary)
            expect_true(
                condition=isinstance(slot["required"], bool),
                message=f"{name}.{slot['slot']}: required must be boolean",
            )
            expect_equal(
                actual="item_type" in slot,
                expected=slot["type"] == "list",
            )
            secret: bool = slot.get("sensitivity") in {
                "accepts_secret",
                "secret_only",
            }
            expect_equal(actual="exposes_to" in slot, expected=secret)
        for port in ports + extras:
            expect_true(
                condition=set(port) <= Constants.port_keys,
                message=f"{name}: unknown port key",
            )
            expect_in(member=port["type"], container=vocabulary)
            expect_equal(
                actual="item_type" in port,
                expected=port["type"] == "list",
            )
        primaries: int = sum(1 for port in ports if port.get("primary"))
        expect_true(condition=primaries <= 1, message=name)
        if row.get("dynamic_outputs"):
            expect_equal(actual=ports, expected=[])
        if row.get("dynamic_inputs") and name == "run_flow":
            expect_equal(actual=slots, expected=[])


def test_interaction_actions_publish_nothing() -> None:
    """Forbid a pass-through output on an action that returns void."""
    for row in _actions():
        if row["id"] in Constants.void_actions:
            expect_equal(actual=row["outputs"], expected=[])
            expect_false(condition=bool(row.get("dynamic_outputs")))


def test_contract_covers_exactly_the_v3_catalog() -> None:
    """Mark every palette id `v3` and nothing else as `v3`."""
    catalog: set[str] = set(
        build_inventory(record=Constants.record).catalog_ids,
    )
    marked: set[str] = {
        str(object=row["id"]) for row in _actions() if row["status"] == "v3"
    }
    expect_equal(actual=marked, expected=catalog)


def _check_inputs(*, name: str, action: Row, required: str) -> None:
    """Check an action's required inputs against one spec cell.

    Args:
        name: Spec row name, for failure messages.
        action: Contract action that cites the row.
        required: The row's required-inputs cell.

    """
    vocabulary: set[str] = _vocabulary()
    slots: list[Row] = _rows(parent=action, key="inputs")
    for spec_name, spec_type in findall(
        pattern=Constants.spec_row_pattern,
        string=required,
    ):
        matched: list[Row] = [
            slot
            for slot in slots
            if slot["slot"] in spec_name.split(sep="/")
            and slot["required"] is True
        ]
        expect_true(
            condition=len(matched) == 1,
            message=f"{name}: required input {spec_name}",
        )
        normal: str = _normal(spec_type=spec_type)
        if normal in vocabulary:
            expect_equal(actual=matched[0]["type"], expected=normal)


def _check_outputs(*, name: str, action: Row, outputs: str) -> None:
    """Check an action's outputs against one spec cell.

    Args:
        name: Spec row name, for failure messages.
        action: Contract action that cites the row.
        outputs: The row's outputs cell.

    """
    vocabulary: set[str] = _vocabulary()
    ports: list[Row] = _rows(parent=action, key="outputs")
    extras: list[Row] = _rows(parent=action, key="conditional_outputs")
    for quoted in findall(pattern="`([^`]+)`", string=outputs):
        partitioned: tuple[str, str, str] = quoted.partition(":")
        port_name: str = partitioned[0].strip()
        spec_type: str = partitioned[2]
        if quoted == "void":
            expect_equal(actual=ports, expected=[])
        elif ":" not in quoted:
            if quoted not in vocabulary:
                expect_in(
                    member=quoted,
                    container=[port["port"] for port in extras],
                )
        else:
            found: list[Row] = [
                port for port in ports if port["port"] == port_name
            ]
            expect_true(
                condition=len(found) == 1,
                message=f"{name}: output {port_name}",
            )
            if _normal(spec_type=spec_type) in vocabulary:
                expect_equal(
                    actual=found[0]["type"],
                    expected=_normal(spec_type=spec_type),
                )
            if "nullable" in spec_type or spec_type.endswith("?"):
                expect_equal(actual=found[0].get("nullable"), expected=True)


def test_contract_agrees_with_the_spec_table() -> None:
    """Match each spec row's required inputs and outputs by name and type."""
    by_row: dict[str, list[Row]] = {}
    for action in _actions():
        by_row.setdefault(str(object=action["spec_row"]), []).append(action)
    for name, required, outputs in _spec_table():
        expect_in(member=name, container=by_row)
        for action in by_row[name]:
            _check_inputs(name=name, action=action, required=required)
            _check_outputs(name=name, action=action, outputs=outputs)


def test_secret_rules_are_destination_based() -> None:
    """Allow secrets only where a slot declares the destination."""
    rules: Row = cast(
        typ="Row",
        val=_contract(name="action-contract.json")["secret_rules"],
    )
    expect_equal(
        actual=rules["declassification"],
        expected="none in this release",
    )
    for destination in ("log", "screenshot", "preview", "error", "export"):
        expect_in(
            member=destination,
            container=_strings(
                parent=rules,
                key="always_redacted_or_rejected",
            ),
        )
    exposed: dict[str, list[str]] = {}
    for action in _actions():
        for slot in _rows(parent=action, key="inputs"):
            if "exposes_to" in slot:
                exposed[f"{action['id']}.{slot['slot']}"] = cast(
                    typ="list[str]",
                    val=slot["exposes_to"],
                )
    expect_equal(actual=exposed["input_text.text"], expected=["page"])
    expect_equal(actual=exposed["http_call.body"], expected=["network"])
    expect_equal(actual=exposed["set_variable.value"], expected=[])
    for destinations in exposed.values():
        expect_true(
            condition=not {"log", "screenshot", "error"} & set(destinations),
            message="a slot may never expose a secret to logs or errors",
        )


def test_selector_contract_agrees_with_the_spec() -> None:
    """Match the selector contract to FLOW.md sections 13.5, 13.10, 13.11."""
    contract: Row = _contract(name="selector-contract.json")
    text: str = _spec_text()
    diagnostics: str = _between(text=text, start="### 13.11", end="## 14.")
    expect_equal(
        actual=set(_strings(parent=contract, key="diagnostic_codes")),
        expected=set(findall(pattern="SELECTOR_[A-Z_]+", string=diagnostics)),
    )
    strategy: str = _between(text=text, start="### 13.10", end="### 13.11")
    spec_commands: set[str] = set(
        findall(pattern="selector\\.[a-z]+(?:\\.[a-z]+)*", string=strategy),
    )
    if "selector.repair.plan/apply" in strategy:
        spec_commands.add("selector.repair.apply")
    expect_equal(
        actual=set(_strings(parent=contract, key="commands")),
        expected=spec_commands,
    )
    expression: str = _between(text=text, start="### 13.5", end="### 13.6")
    for key in ("expression_fields", "preview_request_fields"):
        for field in _strings(parent=contract, key=key):
            expect_in(member=f"    {field}:", container=expression)
    modes: str = _between(text=text, start="### 13.6", end="### 13.7")
    for mode in _strings(parent=contract, key="widget_modes"):
        expect_in(member=mode.capitalize(), container=modes)


def test_javascript_contract_agrees_with_the_spec() -> None:
    """Match the JavaScript contract to FLOW.md sections 14.2, 14.3, 14.11."""
    contract: Row = _contract(name="javascript-contract.json")
    text: str = _spec_text()
    strategy: str = _between(text=text, start="### 14.11", end="## 15.")
    expect_equal(
        actual=set(_strings(parent=contract, key="diagnostic_codes")),
        expected=set(findall(pattern="JAVASCRIPT_[A-Z_]+", string=strategy)),
    )
    expect_equal(
        actual=set(_strings(parent=contract, key="commands")),
        expected=set(
            findall(
                pattern="javascript\\.[a-z_]+(?:\\.[a-z_]+)*",
                string=strategy,
            ),
        ),
    )
    schema: str = _between(text=text, start="### 14.2", end="### 14.3")
    for key in ("persisted_fields", "output_declaration_fields"):
        for field in _strings(parent=contract, key=key):
            expect_in(member=f"    {field}:", container=schema)
    for mode in _strings(parent=contract, key="source_modes"):
        expect_in(member=mode, container=schema)
    names: str = _between(
        text=text,
        start="The snippet receives these lexical names only:\n\n```text\n",
        end="```",
    )
    expect_equal(
        actual=set(_strings(parent=contract, key="namespace")),
        expected=set(
            findall(pattern="^(\\w+)\\s", string=names, flags=MULTILINE),
        ),
    )
    runtime: str = _between(
        text=text,
        start="interface ExactusRuntime",
        end="### 14.4",
    )
    members: set[str] = set(
        findall(pattern="readonly (\\w+):", string=runtime),
    )
    members |= set(
        findall(pattern="^\\s+(\\w+)\\(", string=runtime, flags=MULTILINE),
    )
    expect_equal(
        actual=set(_strings(parent=contract, key="runtime_members")),
        expected=members,
    )
    frozen: Row = cast(typ="Row", val=contract["v3_compatibility"])
    test_name: str = str(object=frozen["frozen_by"]).rsplit(
        sep="::",
        maxsplit=1,
    )[1]
    expect_in(
        member=f"def {test_name}",
        container=(Constants.tests / "test_v3_execution.py").read_text(
            encoding="utf-8",
        ),
    )


def test_receipt_contract_agrees_with_the_spec() -> None:
    """Hold the manifest, install record, forbidden content and ownership."""
    receipt: Row = _contract(name="receipt-contract.json")
    text: str = _spec_text()
    manifest: str = _between(
        text=text,
        start="class ReceiptManifest:",
        end="class ReceiptInstallRecord:",
    )
    install: str = _between(
        text=text,
        start="class ReceiptInstallRecord:",
        end="```",
    )
    expect_equal(
        actual=_strings(parent=receipt, key="manifest_fields"),
        expected=findall(
            pattern="^    (\\w+):",
            string=manifest,
            flags=MULTILINE,
        ),
    )
    expect_equal(
        actual=_strings(parent=receipt, key="install_record_fields"),
        expected=findall(
            pattern="^    (\\w+):",
            string=install,
            flags=MULTILINE,
        ),
    )
    expect_equal(
        actual=receipt["file_extension"],
        expected=".exactus-receipt.json",
    )
    for name in _strings(parent=receipt, key="builtin_receipts"):
        expect_in(member=name, container=text)
    expect_equal(
        actual=len(_strings(parent=receipt, key="builtin_receipts")),
        expected=6,
    )
    forbidden: list[str] = _strings(
        parent=receipt,
        key="package_must_not_contain",
    )
    for item in ("project_context", "credential_value", "accepted_baseline"):
        expect_in(member=item, container=forbidden)
    ownership: Row = cast(typ="Row", val=receipt["device_ownership"])
    expect_equal(
        actual=ownership["initial_profile_owner"],
        expected="project_context",
    )
    expect_false(
        condition=bool(ownership["flows_may_override_initial_profile"]),
    )


def test_decision_document_keeps_every_section_and_limit() -> None:
    """Fail when a locked decision disappears from the document."""
    text: str = Constants.document.read_text(encoding="utf-8")
    for heading in Constants.headings:
        expect_in(member=heading, container=text)
    for key in Constants.limits:
        expect_in(member=f"`{key}`", container=text)
    for phrase in (
        "schema version is **4**",
        "accepts_secret",
        "`exposes_to`",
        "selector-contract.json",
        "javascript-contract.json",
    ):
        expect_in(member=phrase, container=text)
