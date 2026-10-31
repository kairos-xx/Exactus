# Copyright (c) 2026 Project contributors
"""Convert selector-based recorded actions and current workspace documents."""

from __future__ import annotations

from contextlib import suppress
from json import JSONDecodeError, dumps, loads
from os import fsync
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, ClassVar, Final, cast, final

from exactus.tools.record.action_recorder import Action, JsonValue

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
type Event = dict[str, JsonValue]


class WorkspaceActionError(ValueError):
    """Raised when a Exactus Record file or message violates its schema."""


class ActionSchema:
    """Define selector requirements and the current interchange version.

    Attributes:
        workspace_version: Sole supported workspace schema.
        selector_kinds: Event kinds requiring stable CSS selectors.
        pointer_kinds: Supported pointer action mappings.

    """

    workspace_version: ClassVar[int] = 3
    selector_kinds: ClassVar[frozenset[str]] = frozenset(
        {
            "click",
            "double_click",
            "right_click",
            "hover",
            "drag",
            "scroll",
            "gesture",
            "check",
            "uncheck",
            "select_option",
            "input_text",
        },
    )
    pointer_kinds: ClassVar[dict[str, str]] = {
        "click": "click",
        "double_click": "double_click",
        "right_click": "right_click",
        "hover": "hover",
        "check": "check",
        "uncheck": "uncheck",
    }


def _attribute_selector(*, kind: str, candidate: Action) -> str | None:
    """Express a non-CSS locator candidate as an attribute selector.

    Args:
        kind: Locator strategy recorded by the page script.
        candidate: Locator candidate carrying ``value`` or ``role``.

    Returns:
        A browser-valid CSS selector, or ``None`` when none applies.

    """
    value: JsonValue = candidate.get("value")
    if kind == "role":
        role: JsonValue = candidate.get("role")
        return f"[role={dumps(obj=role)}]" if isinstance(role, str) else None
    if not isinstance(value, str) or not value:
        return None
    attributes: dict[str, str] = {
        "test_id": "data-testid",
        "placeholder": "placeholder",
        "label": "aria-label",
    }
    attribute: str | None = attributes.get(kind)
    return None if attribute is None else f"[{attribute}={dumps(obj=value)}]"


def css_selector(*, target: Action | None) -> str | None:
    """Derive the CSS selector Exactus Record requires from a recorded target.

    Args:
        target: Recorded action target carrying locator candidates.

    Returns:
        The first CSS candidate, else an attribute selector built from the
        strongest other candidate, else ``None``.

    """
    locators: JsonValue = None if target is None else target.get("locators")
    if not isinstance(locators, list):
        return None
    fallback: str | None = None
    for candidate in locators:
        if not isinstance(candidate, dict):
            continue
        kind: str = str(object=candidate.get("kind", "css"))
        value: JsonValue = candidate.get("value")
        if kind == "css" and isinstance(value, str) and value:
            return value
        if fallback is None:
            fallback = _attribute_selector(kind=kind, candidate=candidate)
    return fallback


def _target(*, action: Action, key: str = "target") -> Action | None:
    """Return the dict-valued ``key`` entry of ``action``.

    Args:
        action: Recorded action.
        key: Entry expected to hold a locator-bearing dict.

    Returns:
        The entry as an action mapping, or ``None``.

    """
    value: JsonValue = action.get(key)
    return cast(typ="Action", val=value) if isinstance(value, dict) else None


def _label(*, verb: str, action: Action, selector: str | None) -> str:
    """Compose a short human-readable event label.

    Args:
        verb: Leading verb such as ``Click``.
        action: Recorded action whose target text names the control.
        selector: Selector used as the fallback subject.

    Returns:
        Label text shown on the Studio timeline.

    """
    target: Action | None = _target(action=action)
    text: JsonValue = None if target is None else target.get("text")
    subject: str = text if isinstance(text, str) and text else selector or ""
    return f"{verb} {subject}".strip()


def new_event(
    *,
    event_id: str,
    kind: str,
    layer: str,
    label: str,
    elapsed_ms: int = 0,
) -> Event:
    """Build one workspace event with every schema field present.

    Args:
        event_id: Unique event identifier inside the Flow.
        kind: Studio event kind.
        layer: Timeline layer the event belongs to.
        label: Human-readable timeline label.
        elapsed_ms: Milliseconds since the recording started.

    Returns:
        A current-version workspace event with ``None`` for unused fields.

    """
    return {
        "id": event_id,
        "sequence": 0,
        "elapsed_ms": max(elapsed_ms, 0),
        "layer": layer,
        "kind": kind,
        "label": label,
        "selector": None,
        "url": None,
        "method": None,
        "status": None,
        "payload": None,
        "headers": [],
        "share_session_cookies": False,
        "caused_by_event_id": None,
        "position_action": None,
        "x": None,
        "y": None,
        "end_x": None,
        "end_y": None,
        "expectations": [],
        "contract": {
            "preconditions": [],
            "postconditions": [],
            "outputs": [],
            "retry_count": 0,
            "retry_delay_ms": 0,
            "continue_on_failure": False,
        },
        "initiator_stack": [],
        "attribution_reasons": [],
    }


def _elapsed(*, action: Action) -> int:
    """Return an action's recording-relative time in whole milliseconds.

    Args:
        action: Recorded action.

    Returns:
        Non-negative milliseconds, zero when unrecorded.

    """
    raw: JsonValue = action.get("elapsedMs")
    return round(number=raw) if isinstance(raw, int | float) else 0


def _scroll_payload(*, action: Action) -> str:
    """Serialize a scroll offset as the Studio scroll payload.

    Args:
        action: Recorded ``scroll`` action.

    Returns:
        JSON text ``{"x": ..., "y": ...}``.

    """
    return dumps(
        obj={"x": action.get("x", 0), "y": action.get("y", 0)},
        sort_keys=True,
    )


def action_event(*, action: Action, event_id: str) -> Event | None:
    """Convert one recorded action into a Exactus Record event.

    Args:
        action: Recorded or normalized action.
        event_id: Identifier assigned to the event.

    Returns:
        The event, or ``None`` when Studio has no selector-addressable
        equivalent (noise events, unreachable controls, downloads).

    """
    kind: str = str(object=action.get("type", ""))
    selector: str | None = css_selector(target=_target(action=action))
    elapsed: int = _elapsed(action=action)
    pointer: str | None = ActionSchema.pointer_kinds.get(kind)
    event: Event | None = None
    if pointer is not None and selector is not None:
        verb: str = {"check": "Check", "uncheck": "Uncheck"}.get(
            kind,
            pointer.replace("_", " ").capitalize(),
        )
        event = new_event(
            event_id=event_id,
            kind=pointer,
            layer="interaction",
            label=_label(verb=verb, action=action, selector=selector),
            elapsed_ms=elapsed,
        )
        event["selector"] = selector
    elif kind in {"fill", "contenteditable", "select"} and selector:
        value: JsonValue = action.get(
            "values" if kind == "select" else "value",
        )
        text: str = (
            ",".join(str(object=item) for item in value)
            if isinstance(value, list)
            else str(object=value or "")
        )
        event = new_event(
            event_id=event_id,
            kind="select_option" if kind == "select" else "input_text",
            layer="interaction",
            label=_label(verb="Type into", action=action, selector=selector),
            elapsed_ms=elapsed,
        )
        event["selector"] = selector
        event["payload"] = dumps(obj=value) if kind == "select" else text
    elif kind == "key":
        chord: str = KeyChord.render(action=action)
        event = new_event(
            event_id=event_id,
            kind="keystroke",
            layer="interaction",
            label=f"Press {chord}",
            elapsed_ms=elapsed,
        )
        event["payload"] = chord
    elif kind == "scroll":
        event = new_event(
            event_id=event_id,
            kind="scroll",
            layer="interaction",
            label=_label(verb="Scroll", action=action, selector=selector),
            elapsed_ms=elapsed,
        )
        event["selector"] = selector or "html"
        event["payload"] = _scroll_payload(action=action)
    elif kind == "drag":
        source: str | None = css_selector(
            target=_target(action=action, key="source"),
        )
        if source is not None and selector is not None:
            event = new_event(
                event_id=event_id,
                kind="drag",
                layer="interaction",
                label=f"Drag {source}",
                elapsed_ms=elapsed,
            )
            event["selector"] = source
            event["payload"] = selector
    elif kind == "navigation" and isinstance(action.get("url"), str):
        event = new_event(
            event_id=event_id,
            kind="url_change",
            layer="navigation",
            label=f"Navigate to {action.get('url')}",
            elapsed_ms=elapsed,
        )
        event["url"] = action.get("url")
    elif kind == "wait":
        event = new_event(
            event_id=event_id,
            kind="wait",
            layer="timing",
            label=f"Wait {action.get('milliseconds', 0)} ms",
            elapsed_ms=elapsed,
        )
        event["payload"] = str(object=action.get("milliseconds", 0))
    elif kind == "dialog":
        event = new_event(
            event_id=event_id,
            kind="console",
            layer="console",
            label=f"Dialog: {action.get('message', '')}",
            elapsed_ms=elapsed,
        )
    return event


class KeyChord:
    """Render and parse Playwright key chords such as ``Control+A``."""

    @staticmethod
    def render(*, action: Action) -> str:
        """Render a recorded keypress as a ``Mod+Key`` chord.

        Args:
            action: Recorded ``key`` action.

        Returns:
            The chord text.

        """
        modifiers: JsonValue = action.get("modifiers")
        parts: list[str] = []
        if isinstance(modifiers, dict):
            parts.extend(
                (
                    rendered
                    for name, rendered in Constants.modifiers
                    if modifiers.get(name) is True
                ),
            )
        key: str = str(object=action.get("key", ""))
        parts.append("Space" if key == " " else key)
        return "+".join(parts)

    @staticmethod
    def parse(*, chord: str) -> Action:
        """Split a chord back into a ``key`` action.

        Args:
            chord: Chord text such as ``Control+Shift+K``.

        Returns:
            A ``key`` action with its modifier flags.

        """
        names: list[str] = chord.split(sep="+")
        key: str = names.pop() if names else ""
        modifiers: dict[str, JsonValue] = {
            name: rendered in names for name, rendered in Constants.modifiers
        }
        return {
            "type": "key",
            "key": " " if key == "Space" else key,
            "modifiers": cast(typ="JsonValue", val=modifiers),
        }


def actions_to_events(
    *,
    actions: Sequence[Action],
    flow_id: str,
) -> list[Event]:
    """Convert a recorded program into ordered Exactus Record events.

    Args:
        actions: Recorded or normalized actions.
        flow_id: Identifier prefix for the generated event ids.

    Returns:
        Events with consecutive sequence numbers; unsupported actions are
        dropped.

    """
    events: list[Event] = []
    for action in actions:
        event: Event | None = action_event(
            action=action,
            event_id=f"{flow_id}-e{len(events):04d}",
        )
        if event is not None:
            event["sequence"] = len(events)
            events.append(event)
    return events


def build_flow(
    *,
    flow_id: str,
    name: str,
    events: Sequence[Event],
    notes: str = "",
) -> Event:
    """Assemble one workspace Flow around ``events``.

    Args:
        flow_id: Unique Flow identifier.
        name: Flow name shown in Studio.
        events: Ordered Flow events.
        notes: Free-form notes stored with the Flow.

    Returns:
        A current-version Flow shared across every device mode.

    """
    return {
        "id": flow_id,
        "name": name,
        "task_description": f"Recorded by the exactus as {name}.",
        "expected_behavior": "The recorded interactions replay unchanged.",
        "notes": notes,
        "device_modes": ["shared"],
        "capture_record_images": False,
        "capture_play_images": False,
        "parameters": [],
        "outputs": [],
        "events": cast(typ="JsonValue", val=list(events)),
    }


def build_workspace(*, flows: Sequence[Event]) -> Event:
    """Assemble a current-version workspace holding ``flows``.

    Args:
        flows: Flows produced by :func:`build_flow`.

    Returns:
        The workspace document.

    """
    return {
        "version": ActionSchema.workspace_version,
        "flows": cast(typ="JsonValue", val=list(flows)),
        "edges": [],
        "screenshots": [],
        "variables": [],
        "checkpoint_definitions": [],
        "checkpoint_artifacts": [],
        "runs": [],
    }


def write_workspace(*, path: Path, workspace: Event) -> None:
    """Write a workspace as deterministic UTF-8 JSON.

    Args:
        path: Destination ``.pwflow.json`` file.
        workspace: Workspace document to persist.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = stream.name
            stream.write(
                dumps(
                    obj=workspace,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
            stream.flush()
            fsync(fd=stream.fileno())
            Path(temporary).replace(target=path)
    finally:
        if temporary is not None:
            with suppress(FileNotFoundError):
                Path(temporary).unlink()


def _locator_target(*, selector: str) -> Action:
    """Wrap a CSS selector as a recorded-action target.

    Args:
        selector: CSS selector.

    Returns:
        A target carrying one CSS locator candidate.

    """
    return {"locators": [{"kind": "css", "value": selector}]}


def _payload_offsets(*, payload: JsonValue) -> tuple[JsonValue, JsonValue]:
    """Read ``x``/``y`` scroll offsets from an event payload.

    Args:
        payload: Studio scroll payload text.

    Returns:
        ``(x, y)`` offsets, zero when absent or malformed.

    """
    if isinstance(payload, str):
        with suppress(JSONDecodeError):
            decoded: JsonValue = cast(typ="JsonValue", val=loads(s=payload))
            if isinstance(decoded, dict):
                return (decoded.get("x", 0), decoded.get("y", 0))
    return (0, 0)


def _selector_target(*, event: Event) -> Action | None:
    """Return the event selector wrapped as an action target.

    Args:
        event: Workspace or bridge event.

    Returns:
        A CSS-locator target, or ``None`` when the event has no selector.

    """
    selector: JsonValue = event.get("selector")
    if isinstance(selector, str) and selector:
        return _locator_target(selector=selector)
    return None


def _pointer_action(*, event: Event) -> Action | None:
    """Convert a selector-based pointer event.

    Args:
        event: ``click``-family or ``hover`` event.

    Returns:
        The action, or ``None`` without a selector.

    """
    target: Action | None = _selector_target(event=event)
    if target is None:
        return None
    return {
        "type": str(object=event.get("kind", "")),
        "target": cast(typ="JsonValue", val=target),
    }


def _input_action(*, event: Event) -> Action | None:
    """Convert an ``input_text`` event into a ``fill`` action.

    Args:
        event: ``input_text`` event.

    Returns:
        The action, or ``None`` without a selector.

    """
    target: Action | None = _selector_target(event=event)
    payload: JsonValue = event.get("payload")
    if target is None:
        return None
    return {
        "type": "fill",
        "target": cast(typ="JsonValue", val=target),
        "value": payload if isinstance(payload, str) else "",
    }


def _select_action(*, event: Event) -> Action | None:
    """Restore option values without turning selection into a text fill.

    Args:
        event: Recorded timeline event.


    Returns:
        A ``select`` action, or ``None`` when the event has no selector.

    Raises:
        WorkspaceActionError: When the payload is neither a string nor a list.

    """
    target: Action | None = _selector_target(event=event)
    if target is None:
        return None
    values: JsonValue = cast(
        typ="JsonValue",
        val=loads(s=str(object=event.get("payload") or "[]")),
    )
    if not isinstance(values, (str, list)):
        msg: str = "Select step requires a string or array of option values."
        raise WorkspaceActionError(msg)
    return {"type": "select", "target": target, "values": values}


def _key_action(*, event: Event) -> Action | None:
    """Convert a ``keystroke`` event into a ``key`` action.

    Args:
        event: ``keystroke`` event whose payload is a key chord.

    Returns:
        The action, or ``None`` without a chord.

    """
    payload: JsonValue = event.get("payload")
    if not isinstance(payload, str):
        return None
    return KeyChord.parse(chord=payload)


def _scroll_action(*, event: Event) -> Action | None:
    """Convert a ``scroll`` event into a ``scroll`` action.

    Args:
        event: ``scroll`` event with a JSON offset payload.

    Returns:
        The action, or ``None`` without a selector.

    """
    target: Action | None = _selector_target(event=event)
    if target is None:
        return None
    x, y = _payload_offsets(payload=event.get("payload"))
    return {
        "type": "scroll",
        "target": cast(typ="JsonValue", val=target),
        "x": x,
        "y": y,
    }


def _drag_action(*, event: Event) -> Action | None:
    """Convert a ``drag`` event (source selector, target payload).

    Args:
        event: ``drag`` event.

    Returns:
        The action, or ``None`` when either endpoint is missing.

    """
    source: Action | None = _selector_target(event=event)
    payload: JsonValue = event.get("payload")
    if source is None or not isinstance(payload, str):
        return None
    return {
        "type": "drag",
        "source": cast(typ="JsonValue", val=source),
        "target": cast(typ="JsonValue", val=_locator_target(selector=payload)),
    }


def _navigation_action(*, event: Event) -> Action | None:
    """Convert a ``url_change`` event into a ``navigation`` action.

    Args:
        event: ``url_change`` event.

    Returns:
        The action, or ``None`` without a URL.

    """
    url: JsonValue = event.get("url")
    return {"type": "navigation", "url": url} if isinstance(url, str) else None


def _wait_action(*, event: Event) -> Action | None:
    """Convert a ``wait`` event into a ``wait`` action.

    Args:
        event: ``wait`` event whose payload is milliseconds.

    Returns:
        The action, or ``None`` for a malformed payload.

    """
    payload: JsonValue = event.get("payload")
    if isinstance(payload, str) and payload.isdigit():
        return {"type": "wait", "milliseconds": int(payload)}
    return None


def _position_action(*, event: Event) -> Action:
    """Convert a ``position_pointer`` event.

    Args:
        event: ``position_pointer`` event.

    Returns:
        The coordinate pointer action.

    """
    return {
        "type": "position_pointer",
        "position_action": event.get("position_action"),
        "x": event.get("x"),
        "y": event.get("y"),
    }


def event_action(*, event: Event) -> Action | None:
    """Convert a Exactus Record event back into a replayable action.

    Args:
        event: Workspace or bridge event.

    Returns:
        The action, or ``None`` for observation-only kinds (requests,
        responses, WebSocket traffic, console messages, notes).

    """
    converter: Callable[..., Action | None] | None = (
        Constants.event_actions.get(str(object=event.get("kind", "")))
    )
    return None if converter is None else converter(event=event)


def _sequence(event: Event) -> int:
    """Return an event's integer sequence number for ordering.

    Args:
        event: Workspace event.

    Returns:
        The sequence number, zero when absent or malformed.

    """
    raw: JsonValue = event.get("sequence")
    return raw if isinstance(raw, int) and (not isinstance(raw, bool)) else 0


@final
class Constants:
    """Group module-level constants.

    Attributes:
        coordinate_keys: Grouped module constant.
        modifiers: Grouped module constant.
        event_actions: Grouped module constant.

    """

    coordinate_keys: Final[tuple[str, ...]] = ("x", "y", "end_x", "end_y")
    modifiers: Final[tuple[tuple[str, str], ...]] = (
        ("control", "Control"),
        ("alt", "Alt"),
        ("shift", "Shift"),
        ("meta", "Meta"),
    )
    event_actions: Final[dict[str, Callable[..., Action | None]]] = {
        "click": _pointer_action,
        "double_click": _pointer_action,
        "right_click": _pointer_action,
        "hover": _pointer_action,
        "check": _pointer_action,
        "uncheck": _pointer_action,
        "select_option": _select_action,
        "input_text": _input_action,
        "keystroke": _key_action,
        "scroll": _scroll_action,
        "drag": _drag_action,
        "url_change": _navigation_action,
        "wait": _wait_action,
        "position_pointer": _position_action,
    }


def load_flow_actions(
    *,
    path: Path,
    flow_id: str | None = None,
) -> list[Action]:
    """Load a replayable program from a Studio workspace or action file.

    Args:
        path: ``.pwflow.json`` workspace or ``actions.normalized.json``.
        flow_id: Flow to extract; the first Flow is used when omitted.

    Returns:
        Actions in Flow order.

    Raises:
        WorkspaceActionError: When the file is neither a workspace nor an
            action
            array, or the requested Flow does not exist.

    """
    document: JsonValue = cast(
        typ="JsonValue",
        val=loads(s=path.read_text(encoding="utf-8")),
    )
    if isinstance(document, list):
        return [
            cast(typ="Action", val=item)
            for item in document
            if isinstance(item, dict)
        ]
    if (
        isinstance(document, dict)
        and document.get("version") != ActionSchema.workspace_version
    ):
        msg: str = (
            "Unsupported workspace version. Use the current Studio "
            "project format."
        )
        raise WorkspaceActionError(msg)
    flows: JsonValue = (
        document.get("flows") if isinstance(document, dict) else None
    )
    if not isinstance(flows, list):
        msg = f"{path.name} is neither a workspace nor an action program"
        raise WorkspaceActionError(msg)
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        if flow_id is None or flow.get("id") == flow_id:
            events: JsonValue = flow.get("events")
            ordered: list[Event] = sorted(
                (
                    cast(typ="Event", val=item)
                    for item in (events if isinstance(events, list) else [])
                    if isinstance(item, dict)
                ),
                key=_sequence,
            )
            return [
                action
                for event in ordered
                if (action := event_action(event=event)) is not None
            ]
    msg = f"flow {flow_id!r} not found in {path.name}"
    raise WorkspaceActionError(msg)


def validate_event(*, event: Event) -> None:
    """Enforce Exactus Record's targeting invariants on a bridge event.

    Args:
        event: Event about to be sent (or just decoded).

    Raises:
        WorkspaceActionError: When a DOM action lacks a selector, a coordinate
            appears on a non-positional kind, or a positional pointer
            carries a selector or lacks its coordinates.

    """
    kind: str = str(object=event.get("kind", ""))
    has_coordinates: bool = any(
        event.get(key) is not None for key in Constants.coordinate_keys
    )
    if kind == "position_pointer":
        if event.get("selector") is not None:
            msg: str = "position_pointer events cannot carry a selector"
            raise WorkspaceActionError(msg)
        if (
            event.get("position_action") is None
            or event.get("x") is None
            or event.get("y") is None
        ):
            msg = "position_pointer events require position_action, x and y"
            raise WorkspaceActionError(msg)
        return
    if kind in ActionSchema.selector_kinds and (not event.get("selector")):
        msg = f"{kind} events require a CSS selector"
        raise WorkspaceActionError(msg)
    if has_coordinates:
        msg = "coordinates are only legal on position_pointer events"
        raise WorkspaceActionError(msg)


def encode_message(*, message: Event) -> bytes:
    """Encode one compact NDJSON line.

    Args:
        message: JSON object to send.

    Returns:
        UTF-8 bytes terminated by a newline.

    """
    return (
        dumps(obj=message, ensure_ascii=False, separators=(",", ":")).encode(
            encoding="utf-8",
        )
        + b"\n"
    )


def bridge_event(*, event: Event, flow_id: str) -> Event:
    """Adapt a workspace event to the bridge's inbound event envelope.

    Args:
        event: Workspace event from :func:`action_event`.
        flow_id: Flow the event belongs to.

    Returns:
        A ``type: "event"`` message Studio's protocol accepts.

    """
    msg: Event = {
        key: value
        for key, value in event.items()
        if key not in {"id", "sequence", "expectations", "contract"}
        and value is not None
        and (value != [])
    }
    msg["type"] = "event"
    msg["event_id"] = event["id"]
    msg["flow_id"] = flow_id
    return msg
