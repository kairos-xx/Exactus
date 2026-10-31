# Copyright (c) 2026 Project contributors
"""Editor commands for selectors, apart from the large controller."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final
from uuid import uuid4

from exactus.tools.record.selector_engine import world_for
from exactus.tools.record.selector_probes import (
    condition_vocabulary,
    validate_condition,
)
from exactus.tools.record.selector_resolver import Resolution, SelectorResolver
from exactus.tools.record.selector_usage import (
    SelectorUsage,
    dangling_references,
    usage_index,
)
from exactus.tools.record.selectors import (
    RunMode,
    SelectorCodec,
    SelectorDef,
    TargetScope,
    ValidatedOn,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import (
        ActionContract,
        TimelineEvent,
        Workspace,
    )
    from exactus.tools.record.selectors import Pace
    from exactus.tools.record.store import FlowStore


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_test_matches: Grouped module constant.
        stats_script: Grouped module constant.

    """

    max_test_matches: Final[int] = 200
    stats_script: Final[str] = dedent(
        text=(
            "    \n    args => {\n      const Engine = globalThis.__EXACTUS_ES"
            "__;\n      const engine = new Engine(document, { deep: true });\n"
            "      for (const [name, expression] of Object.entries(args.defini"
            "tions)) {\n        try { engine.define(name, expression); } catch"
            " { /* reported by the test */ }\n      }\n      try {\n        re"
            "turn { ok: true, stats: engine.stats(args.expression, { variables"
            ": args.variables }) };\n      } catch (error) {\n        return {"
            ' ok: false, message: String(error.message).split("\\n")[0], code:'
            " error.code ?? null };\n      }\n    }\n    "
        ),
    )


def _text(*, data: dict[str, JsonValue], key: str) -> str:
    """Return a required, non-blank string field.

    Args:
        data: Command payload.
        key: Field name.

    Returns:
        The trimmed text.

    Raises:
        ValueError: When the field is missing or blank.

    """
    value: JsonValue = data.get(key)
    if not isinstance(value, str) or not value.strip():
        msg: str = f"{key} must be a non-empty string."
        raise ValueError(msg)
    return value.strip()


def _expected_count(*, data: dict[str, JsonValue]) -> int | None:
    """Read the expected match count from a command.

    Args:
        data: Command payload; a missing, empty or ``"any"`` value means
            one or more.

    Returns:
        The exact count, or ``None``.

    Raises:
        ValueError: When the value is not a non-negative integer.

    """
    value: JsonValue = data.get("expected_count", 1)
    if value is None or value in {"", "any"}:
        return None
    try:
        count: int = int(str(object=value))
    except ValueError as error:
        msg: str = "expected_count must be a whole number or 'any'."
        raise ValueError(msg) from error
    if count < 0:
        msg = "expected_count cannot be negative."
        raise ValueError(msg)
    return count


def _checks(*, data: dict[str, JsonValue]) -> tuple[str, ...]:
    """Read the checks list from a command.

    Args:
        data: Command payload.

    Returns:
        Non-blank check expressions.

    Raises:
        ValueError: When ``checks`` is not a list of text.

    """
    value: JsonValue = data.get("checks", [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        msg: str = "checks must be a list of text."
        raise ValueError(msg)
    return tuple(
        item.strip()
        for item in cast(typ="list[str]", val=value)
        if item.strip()
    )


def save_selector(*, store: FlowStore, data: dict[str, JsonValue]) -> None:
    """Create a selector, or edit one in place.

    Editing keeps references working. A new name is applied through a rename
    so expressions and conditions that mention the old name follow it. A
    changed expression clears the pages it was validated on, because they no
    longer vouch for it.

    Args:
        store: Project store.
        data: ``name``, ``expression``, ``expected_count``, ``checks`` and,
            when editing, ``selector_id``.

    """
    name: str = _text(data=data, key="name")
    expression: str = _text(data=data, key="expression")
    count: int | None = _expected_count(data=data)
    checks: tuple[str, ...] = _checks(data=data)
    selector_id: JsonValue = data.get("selector_id")
    if not selector_id:
        store.upsert_selector(
            selector=SelectorDef(
                selector_id=f"sel-{uuid4().hex[:8]}",
                name=name,
                expression=expression,
                expected_count=count,
                checks=checks,
            ),
        )
        return
    existing: SelectorDef = store.get_selector(
        selector_id=str(object=selector_id),
    )
    if existing.name != name:
        _ = store.rename_selector(selector_id=existing.selector_id, name=name)
        existing = store.get_selector(selector_id=existing.selector_id)
    store.upsert_selector(
        selector=replace(
            existing,
            expression=expression,
            expected_count=count,
            checks=checks,
            validated_on=existing.validated_on
            if existing.expression == expression
            else (),
        ),
    )


def delete_selector(*, store: FlowStore, data: dict[str, JsonValue]) -> None:
    """Delete a selector, refusing when it is in use unless forced.

    Args:
        store: Project store.
        data: ``selector_id`` and optionally ``force``.

    """
    store.delete_selector(
        selector_id=_text(data=data, key="selector_id"),
        force=data.get("force") is True,
    )


def _pace(
    *,
    value: JsonValue,
    selectors: tuple[SelectorDef, ...],
) -> Pace | None:
    """Parse and validate a pace sent by the editor.

    Args:
        value: Pace object, or ``None``/empty to clear it.
        selectors: Stored selectors, which probe names must match.

    Returns:
        The pace, or ``None``.

    """
    if not value:
        return None
    pace: Pace | None = SelectorCodec.pace_from_json(value=value)
    if pace is not None and pace.until is not None:
        validate_condition(expression=pace.until, selectors=selectors)
    return pace


def updated_event(
    *,
    event: TimelineEvent,
    data: dict[str, JsonValue],
    selectors: tuple[SelectorDef, ...],
    label: str,
) -> TimelineEvent:
    """Apply an ``event.update`` command to an action in one validated step.

    The basic fields (selector, payload, address) always come from the
    payload, as the step form sends them every time. The targeting fields
    (selector reference, scope, run mode, pauses, sandbox, failure policy,
    output variable, guard) change only when present, so older forms keep
    working. Everything is
    applied together, so swapping an inline selector for a reference never
    passes through an invalid state.

    Args:
        event: The action being edited.
        data: Command payload.
        selectors: Stored selectors, which probe names must match.
        label: The action's new label.

    Returns:
        The updated action; its own validation rejects bad combinations.

    """
    reference: JsonValue = data.get("selector_id", event.selector_id)
    contract: ActionContract = event.contract
    if "continue_on_failure" in data:
        contract = replace(
            contract,
            continue_on_failure=data["continue_on_failure"] is True,
        )
    if "pace" in data:
        contract = replace(
            contract,
            pace=_pace(value=data["pace"], selectors=selectors),
        )
    return replace(
        event,
        label=label,
        selector=str(object=data["selector"])
        if data.get("selector")
        else None,
        payload=str(object=data["payload"])
        if data.get("payload") is not None
        else None,
        url=str(object=data["url"]) if data.get("url") else None,
        selector_id=str(object=reference) if reference else None,
        targets=TargetScope(str(object=data["targets"]))
        if "targets" in data
        else event.targets,
        run_mode=RunMode(str(object=data["run_mode"]))
        if "run_mode" in data
        else event.run_mode,
        pace_between=_pace(value=data["pace_between"], selectors=selectors)
        if "pace_between" in data
        else event.pace_between,
        sandbox=data["sandbox"] is True
        if "sandbox" in data
        else event.sandbox,
        output_variable=str(object=data["output_variable"]).strip() or None
        if "output_variable" in data
        else event.output_variable,
        when_expression=str(object=data["when_expression"]).strip() or None
        if "when_expression" in data
        else event.when_expression,
        contract=contract,
    )


def selector_view(*, workspace: Workspace) -> dict[str, JsonValue]:
    """Describe the project's selectors for the editor.

    Args:
        workspace: The project.

    Returns:
        The selectors, what depends on each, and broken references.

    """
    index: dict[str, SelectorUsage] = usage_index(workspace=workspace)
    return {
        "selectors": [
            SelectorCodec.selector_to_json(item=item)
            for item in workspace.selectors
        ],
        "selector_usage": {
            selector_id: {
                "actions": [
                    {"flow_id": flow_id, "event_id": event_id}
                    for flow_id, event_id in usage.actions
                ],
                "flows": usage.flow_count,
                "selectors": list(usage.selectors),
                "conditions": usage.conditions,
            }
            for selector_id, usage in index.items()
        },
        "condition_vocabulary": cast(
            typ="JsonValue",
            val=condition_vocabulary(workspace=workspace),
        ),
        "selector_problems": [
            {"flow_id": flow_id, "event_id": event_id, "selector_id": ref}
            for flow_id, event_id, ref in dangling_references(
                workspace=workspace,
            )
        ],
    }


def test_message(
    *,
    data: dict[str, JsonValue],
    selectors: tuple[SelectorDef, ...],
) -> dict[str, JsonValue]:
    """Build the worker message that tests an expression in the live page.

    Args:
        data: ``expression``, ``expected_count``, ``checks`` and optionally
            ``selector_id`` of the selector being edited.
        selectors: Stored selectors, so their names resolve.

    Returns:
        A ``selector_test`` input for the browser worker.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val={
            "action": "selector_test",
            "expression": _text(data=data, key="expression"),
            "expected_count": _expected_count(data=data),
            "checks": list(_checks(data=data)),
            "selector_id": cast(
                typ="JsonValue",
                val=data.get("selector_id") or None,
            ),
            "variables": cast(
                typ="JsonValue",
                val=data.get("variables") or {},
            ),
            "selectors": [
                SelectorCodec.selector_to_json(item=item) for item in selectors
            ],
        },
    )


def _stats(
    *,
    page: Page,
    selectors: tuple[SelectorDef, ...],
    message: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Ask the engine for per-node statistics of the expression.

    Args:
        page: The managed target page.
        selectors: Stored selectors, so their names resolve.
        message: The ``selector_test`` message.

    Returns:
        ``{"ok": True, "stats": ...}`` or ``{"ok": False, "message", "code"}``.

    """
    reply: JsonValue = world_for(page=page).call(
        function=Constants.stats_script,
        argument={
            "expression": str(object=message["expression"]),
            "definitions": {item.name: item.expression for item in selectors},
            "variables": cast(
                typ="JsonValue",
                val=message.get("variables") or {},
            ),
        },
    )
    return cast(typ="dict[str, JsonValue]", val=reply)


def run_selector_test(
    *,
    page: Page,
    message: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Resolve an expression in the page and describe the result.

    Args:
        page: The managed target page.
        message: A ``selector_test`` message from ``test_message``.

    Returns:
        Counts, per-match CSS and rectangles, and the cause when it failed.

    """
    items: JsonValue = message.get("selectors")
    selectors: tuple[SelectorDef, ...] = SelectorCodec.from_json_value(
        value={"version": 1, "selectors": items},
    )
    expected: JsonValue = message.get("expected_count")
    resolution: Resolution = SelectorResolver(
        page=page,
        selectors=selectors,
        timeout_ms=1500,
    ).resolve(
        expression=str(object=message["expression"]),
        expected_count=None if expected is None else int(str(object=expected)),
        checks=tuple(
            str(object=item)
            for item in cast(typ="list[JsonValue]", val=message["checks"])
        ),
    )
    matches: list[JsonValue] = [
        {
            "index": match.index,
            "css": match.css,
            "css_error": match.css_error,
            "rect": cast(typ="JsonValue", val=match.rect),
            "tag": match.evidence.get("tag"),
            "text": match.evidence.get("text"),
            "failed": list(match.failed_checks),
        }
        for match in resolution.matches[: Constants.max_test_matches]
    ]
    return cast(
        typ="dict[str, JsonValue]",
        val={
            "expression": resolution.expression,
            "selector_id": message.get("selector_id"),
            "ok": resolution.ok,
            "count": resolution.count,
            "expected_count": resolution.expected_count,
            "elapsed_ms": resolution.elapsed_ms,
            "polls": resolution.polls,
            "error": resolution.error,
            "definition_errors": list(resolution.definition_errors),
            "cause": resolution.cause(),
            "url": page.url,
            "matches": matches,
            "stats": _stats(page=page, selectors=selectors, message=message),
        },
    )


def record_validation(
    *,
    store: FlowStore,
    result: dict[str, JsonValue],
) -> bool:
    """Remember a successful test on the selector that was tested.

    Args:
        store: Project store.
        result: A result from ``run_selector_test``.

    Returns:
        True when a stored selector was updated.

    """
    selector_id: JsonValue = result.get("selector_id")
    if result.get("ok") is not True or not selector_id:
        return False
    try:
        selector: SelectorDef = store.get_selector(
            selector_id=str(object=selector_id),
        )
    except ValueError:
        return False
    if selector.expression != result.get("expression"):
        return False
    url: str = str(object=result["url"])
    seen: ValidatedOn = ValidatedOn(
        url=url,
        at=datetime.now(tz=UTC).astimezone().isoformat(timespec="seconds"),
        matches=int(str(object=result["count"])),
    )
    kept: tuple[ValidatedOn, ...] = tuple(
        item for item in selector.validated_on if item.url != url
    )
    store.upsert_selector(
        selector=replace(selector, validated_on=(*kept, seen)),
    )
    return True
