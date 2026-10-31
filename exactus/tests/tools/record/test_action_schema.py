# Copyright (c) 2026 Project contributors
"""Verify typed action bindings and stable input/output identities."""

from __future__ import annotations

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.record.action_schema import (
    ActionInputBinding,
    ActionOutputReference,
    ActionSchema,
    BindingKind,
    EvaluationTiming,
    ExposureDestination,
    FlowValueType,
    InputSlot,
    LiteralBindingValue,
    OutputPort,
    PortSensitivity,
    SlotSensitivity,
    hard_dependency_ids,
)
from exactus.tools.record.model import ValueType

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group test constants.

    Attributes:
        contract: Locked action contract.
        added_runtime_types: Runtime types added by schema version 4.

    """

    contract: Final[Path] = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "contract"
        / "action-contract.json"
    )
    added_runtime_types: Final[frozenset[str]] = frozenset(
        {"url", "selector", "duration", "artifact", "list", "void"},
    )


def test_value_vocabulary_matches_the_locked_contract() -> None:
    """Keep the production value categories aligned with the contract."""
    document: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=Constants.contract.read_text(encoding="utf-8")),
    )
    expect_equal(
        actual={item.value for item in FlowValueType},
        expected=set(cast(typ="list[str]", val=document["types"])),
    )
    expect_true(
        condition=Constants.added_runtime_types.issubset(
            {item.value for item in ValueType},
        ),
    )


def test_action_output_identity_ignores_paths_and_display_metadata() -> None:
    """Use producer and port IDs as the only stable source identity."""
    direct: ActionOutputReference = ActionOutputReference(
        producer_id="fetch-user",
        port_id="json",
    )
    nested: ActionOutputReference = ActionOutputReference(
        producer_id="fetch-user",
        port_id="json",
        path=("profile", "name"),
        getter="text",
    )
    expect_equal(actual=direct.source_id, expected="fetch-user/json")
    expect_equal(actual=nested.source_id, expected=direct.source_id)


def test_binding_accepts_json_null_as_a_real_literal() -> None:
    """Distinguish an authored null from a missing binding payload."""
    binding: ActionInputBinding = ActionInputBinding(
        kind=BindingKind.LITERAL,
        literal=LiteralBindingValue(value=None),
    )
    expect_true(condition=binding.literal is not None)
    literal: LiteralBindingValue = cast(
        typ="LiteralBindingValue",
        val=binding.literal,
    )
    expect_equal(actual=literal.value, expected=None)


def test_binding_rejects_multiple_or_mismatched_payloads() -> None:
    """Reject ambiguous persisted binding documents before execution."""
    with pytest.raises(expected_exception=ValueError, match="exactly one"):
        ActionInputBinding(
            kind=BindingKind.LITERAL,
            literal=LiteralBindingValue(value="hello"),
            variable_id="customer-name",
        )
    with pytest.raises(expected_exception=ValueError, match="does not match"):
        ActionInputBinding(
            kind=BindingKind.VARIABLE,
            template="Hello {{customer-name}}",
        )


def test_dependency_ids_follow_first_use_order() -> None:
    """Expose hard dependencies used to order and move action blocks."""
    bindings: tuple[ActionInputBinding, ...] = tuple(
        ActionInputBinding(
            kind=BindingKind.ACTION_OUTPUT,
            action_output=ActionOutputReference(
                producer_id=producer_id,
                port_id="result",
            ),
        )
        for producer_id in ("open", "extract", "open")
    )
    expect_equal(
        actual=hard_dependency_ids(bindings=bindings),
        expected=("open", "extract"),
    )


def test_slot_enforces_secret_and_retry_capabilities() -> None:
    """Authorize secrets by destination and retries by slot declaration."""
    page_text: InputSlot = InputSlot(
        slot_id="text",
        value_type=FlowValueType.STRING,
        required=True,
        sensitivity=SlotSensitivity.ACCEPTS_SENSITIVE,
        exposes_to=frozenset({ExposureDestination.PAGE}),
    )
    public_label: InputSlot = InputSlot(
        slot_id="label",
        value_type=FlowValueType.STRING,
        required=True,
    )
    expect_true(condition=page_text.accepts_secret(secret=True))
    expect_false(condition=public_label.accepts_secret(secret=True))
    expect_false(
        condition=page_text.accepts_timing(
            timing=EvaluationTiming.EACH_ATTEMPT,
        ),
    )


def test_schema_rejects_ambiguous_ports() -> None:
    """Keep the action's default result and source IDs unambiguous."""
    first: OutputPort = OutputPort(
        port_id="value",
        value_type=FlowValueType.STRING,
        primary=True,
        sensitivity=PortSensitivity.INHERITED,
    )
    second: OutputPort = OutputPort(
        port_id="other",
        value_type=FlowValueType.STRING,
        primary=True,
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="multiple primary",
    ):
        ActionSchema(action_id="extract", inputs=(), outputs=(first, second))


def test_output_reference_rejects_empty_identity_parts() -> None:
    """Require usable producer, port, path and getter identities."""
    with pytest.raises(expected_exception=ValueError, match="port IDs"):
        ActionOutputReference(producer_id=" ", port_id="json")
    with pytest.raises(expected_exception=ValueError, match="empty parts"):
        ActionOutputReference(
            producer_id="fetch-user",
            port_id="json",
            path=("profile", ""),
        )
    with pytest.raises(expected_exception=ValueError, match="getters"):
        ActionOutputReference(
            producer_id="fetch-user",
            port_id="json",
            getter=" ",
        )


def test_binding_reports_its_producer_dependency() -> None:
    """Name the action that must run before an output-consuming binding."""
    reference: ActionOutputReference = ActionOutputReference(
        producer_id="fetch-user",
        port_id="json",
    )
    bound: ActionInputBinding = ActionInputBinding(
        kind=BindingKind.ACTION_OUTPUT,
        action_output=reference,
    )
    free: ActionInputBinding = ActionInputBinding(
        kind=BindingKind.VARIABLE,
        variable_id="token",
    )
    expect_equal(actual=bound.hard_dependency_id, expected="fetch-user")
    expect_equal(actual=free.hard_dependency_id, expected=None)


def test_binding_rejects_blank_text_payloads() -> None:
    """Reject whitespace-only variable, template and prompt payloads."""
    with pytest.raises(expected_exception=ValueError, match="cannot be empty"):
        ActionInputBinding(kind=BindingKind.VARIABLE, variable_id=" ")
    with pytest.raises(expected_exception=ValueError, match="cannot be empty"):
        ActionInputBinding(kind=BindingKind.TEMPLATE, template="")
    with pytest.raises(expected_exception=ValueError, match="cannot be empty"):
        ActionInputBinding(kind=BindingKind.PROMPT, prompt=" ")


def test_slot_rejects_inconsistent_definitions() -> None:
    """Reject empty IDs, void types and mismatched secret/list metadata."""
    with pytest.raises(expected_exception=ValueError, match="slot IDs"):
        InputSlot(slot_id=" ", value_type=FlowValueType.STRING, required=True)
    with pytest.raises(expected_exception=ValueError, match="void"):
        InputSlot(
            slot_id="nothing",
            value_type=FlowValueType.VOID,
            required=False,
        )
    with pytest.raises(expected_exception=ValueError, match=r"[Pp]ublic"):
        InputSlot(
            slot_id="label",
            value_type=FlowValueType.STRING,
            required=False,
            exposes_to=frozenset({ExposureDestination.PAGE}),
        )
    with pytest.raises(expected_exception=ValueError, match="item type"):
        InputSlot(
            slot_id="names",
            value_type=FlowValueType.STRING,
            required=False,
            item_type=FlowValueType.STRING,
        )


def test_port_rejects_inconsistent_definitions() -> None:
    """Reject empty IDs, void types and non-list item metadata."""
    with pytest.raises(expected_exception=ValueError, match="port IDs"):
        OutputPort(port_id=" ", value_type=FlowValueType.STRING)
    with pytest.raises(expected_exception=ValueError, match=r"[Vv]oid"):
        OutputPort(port_id="nothing", value_type=FlowValueType.VOID)
    with pytest.raises(expected_exception=ValueError, match="item type"):
        OutputPort(
            port_id="names",
            value_type=FlowValueType.STRING,
            item_type=FlowValueType.STRING,
        )


def test_schema_rejects_empty_and_duplicate_identities() -> None:
    """Keep schema, slot and port identities non-empty and unique."""
    slot: InputSlot = InputSlot(
        slot_id="label",
        value_type=FlowValueType.STRING,
        required=False,
    )
    port: OutputPort = OutputPort(
        port_id="value",
        value_type=FlowValueType.STRING,
    )
    with pytest.raises(expected_exception=ValueError, match="schema IDs"):
        ActionSchema(action_id=" ", inputs=(), outputs=())
    with pytest.raises(expected_exception=ValueError, match="duplicate input"):
        ActionSchema(action_id="extract", inputs=(slot, slot), outputs=())
    with pytest.raises(
        expected_exception=ValueError,
        match="duplicate output",
    ):
        ActionSchema(action_id="extract", inputs=(), outputs=(port, port))
