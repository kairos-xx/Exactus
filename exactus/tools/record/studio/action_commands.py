# Copyright (c) 2026 Project contributors
"""Reconfigure an authored action from the Properties panel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, Final, final

from exactus.tools.record.model import EventKind
from exactus.tools.record.studio.selector_commands import updated_event

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import PositionPointerAction, TimelineEvent
    from exactus.tools.record.selectors import SelectorDef


@final
class Constants:
    """Group module-level constants.

    Attributes:
        screenshot_marker: Grouped module constant.

    """

    screenshot_marker: Final[str] = "__screenshot__"


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ActionFields:
    """The normalized settings an action is reconfigured with.

    Attributes:
        label: Label the settings would give a new action.
        payload: Encoded action payload, such as code or a JSON document.
        selector: Element selector the action targets.
        selector_id: Reusable project selector the action targets.
        url: Address the action navigates to or requests.
        method: HTTP method for request actions.
        position_action: Pointer action for absolute-position steps.
        x: Horizontal viewport coordinate.
        y: Vertical viewport coordinate.
        incomplete: Whether required settings are still blank.

    """

    label: str
    payload: str | None
    selector: str | None
    selector_id: str | None
    url: str | None
    method: str | None
    position_action: PositionPointerAction | None
    x: int | None
    y: int | None
    incomplete: bool


def default_label(*, event: TimelineEvent) -> str:
    """Return the label the action's own settings would generate.

    A label that equals this was never renamed by hand, so reconfiguring the
    action may refresh it. A renamed label is left alone.

    Args:
        event: The authored action.

    Returns:
        The label derived from the action's settings.

    """
    url: str | None = event.url
    method: str = event.method or "GET"
    labels: dict[EventKind, str] = {
        EventKind.NOTE: "Capture screenshot"
        if event.payload == Constants.screenshot_marker
        else "Note",
        EventKind.JAVASCRIPT: "JavaScript call",
        EventKind.URL_CHANGE: f"Navigate to {url}" if url else "Navigate",
        EventKind.HTTP_CALL: f"{method} {url}" if url else f"{method} request",
        EventKind.WEBSOCKET_CALL: f"WebSocket {url}"
        if url
        else "WebSocket session",
        EventKind.WAIT: f"Wait for {_payload(event=event).get('condition')}",
        EventKind.VIEWPORT: _viewport_label(document=_payload(event=event)),
        EventKind.POSITION_POINTER: _pointer_label(event=event),
    }
    return labels.get(
        event.kind,
        event.kind.value.replace("_", " ").capitalize(),
    )


def _pointer_label(*, event: TimelineEvent) -> str:
    """Name an absolute-position pointer action.

    Args:
        event: The authored action.

    Returns:
        The label such an action carries, such as ``Click at 4, 9``.

    """
    action: PositionPointerAction | None = event.position_action
    operation: str = action.value.replace("_", " ") if action else "Pointer"
    return f"{operation.capitalize()} at {event.x}, {event.y}"


def _payload(*, event: TimelineEvent) -> dict[str, JsonValue]:
    """Decode an action payload that holds a JSON object.

    Args:
        event: The authored action.

    Returns:
        The object, or an empty one when the payload is not an object.

    """
    try:
        document: JsonValue = loads(s=event.payload or "")
    except JSONDecodeError:
        return {}
    return document if isinstance(document, dict) else {}


def _viewport_label(*, document: dict[str, JsonValue]) -> str:
    """Name a viewport action from its decoded payload.

    Args:
        document: The decoded viewport payload.

    Returns:
        The label a rotate or resize action carries.

    """
    if document.get("action") == "resize":
        return (
            f"Resize viewport to "
            f"{document.get('width')} x {document.get('height')}"
        )
    return "Rotate viewport"


def _chosen_label(
    *,
    event: TimelineEvent,
    fields: ActionFields,
    requested: str,
) -> str:
    """Decide the label an action carries after it is reconfigured.

    A label typed in the form wins. Otherwise a generated label follows the
    new settings, and a label chosen earlier is kept.

    Args:
        event: The action being reconfigured.
        fields: The settings normalized from the form.
        requested: The label the form submitted.

    Returns:
        The label to save.

    """
    if requested and requested != event.label:
        return requested
    if event.label == default_label(event=event):
        return fields.label
    return event.label


def reconfigured_event(
    *,
    event: TimelineEvent,
    fields: ActionFields,
    data: dict[str, JsonValue],
    selectors: tuple[SelectorDef, ...],
) -> TimelineEvent:
    """Apply a full set of action settings to an existing action.

    The result keeps the action's identity, place in the flow, evidence and
    checks. Targeting, pacing and failure policy follow the existing
    ``event.update`` rules, so one form can save both.

    Args:
        event: The action being reconfigured.
        fields: The settings normalized from the form.
        data: The submitted command payload.
        selectors: Stored selectors, which pacing probes must match.

    Returns:
        The reconfigured action; its own validation refuses bad settings.

    """
    label: str = _chosen_label(
        event=event,
        fields=fields,
        requested=str(object=data.get("label") or "").strip(),
    )
    staged: TimelineEvent = replace(
        event,
        label=label,
        selector=fields.selector,
        selector_id=fields.selector_id,
        url=fields.url,
        method=fields.method,
        payload=fields.payload,
        position_action=fields.position_action,
        x=fields.x,
        y=fields.y,
        share_session_cookies=str(
            object=data.get("share_session_cookies") or "false",
        ).lower()
        == "true",
        output_variable=str(object=data.get("output_variable") or "").strip()
        or None,
        incomplete=fields.incomplete,
    )
    return updated_event(
        event=staged,
        data={
            **data,
            "selector": fields.selector or "",
            "selector_id": fields.selector_id or "",
            "payload": fields.payload,
            "url": fields.url or "",
            "output_variable": staged.output_variable or "",
        },
        selectors=selectors,
        label=label,
    )
