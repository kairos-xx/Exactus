# Copyright (c) 2026
"""Verify current workspace interchange and selector-based actions."""

from __future__ import annotations

from importlib import import_module
from json import dumps, loads
from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, Final, Protocol, cast, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
    require,
)
from exactus.tools.record import workspace_actions as fs

if TYPE_CHECKING:
    from types import ModuleType
type Report = dict[str, dict[str, object]]


class _Flow(Protocol):
    """Flow shape exposed by the Studio codec.

    Attributes:
        events: Recorded events of the flow.

    """

    events: list[object]


class _Workspace(Protocol):
    """Workspace shape exposed by the Studio codec.

    Attributes:
        flows: Flows held by the workspace.

    """

    flows: list[_Flow]


def _control_key(*, action: fs.Event) -> bool:
    """Tell whether a key action carries the control modifier.

    Args:
        action: Replayable action.

    Returns:
        Whether the action is a key press with ``control`` held.

    """
    modifiers: object = action.get("modifiers")
    return (
        action.get("type") == "key"
        and isinstance(modifiers, dict)
        and (modifiers.get("control") is True)
    )


def _css(value: str) -> fs.Event:
    """Build a target with one CSS candidate.

    Args:
        value: CSS selector.

    Returns:
        The target payload.

    """
    return {"locators": [{"kind": "css", "value": value}]}


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_actions: Grouped module constant.
        pair: Grouped module constant.
        studio_src: Grouped module constant.
        actions: Grouped module constant.

    """

    min_actions: Final[int] = 5
    pair: Final[int] = 2
    studio_src: Final[Path] = Path(__file__).resolve().parents[4]
    actions: Final[list[fs.Event]] = [
        {"type": "focus"},
        {
            "type": "click",
            "target": {"text": "Go", **_css(value="#go")},
            "elapsedMs": 12,
        },
        {"type": "double_click", "target": _css(value="#a")},
        {"type": "right_click", "target": _css(value="#a")},
        {"type": "hover", "target": _css(value="#a")},
        {"type": "check", "target": _css(value="#c")},
        {"type": "uncheck", "target": _css(value="#c")},
        {"type": "fill", "target": _css(value="#n"), "value": "Ada"},
        {"type": "select", "target": _css(value="#s"), "values": ["a", "b"]},
        {"type": "select", "target": _css(value="#s"), "values": "x"},
        {"type": "key", "key": "A", "modifiers": {"control": True}},
        {"type": "key", "key": " "},
        {"type": "scroll", "x": 0, "y": 9},
        {"type": "scroll", "target": _css(value="#box"), "x": 1, "y": 2},
        {
            "type": "drag",
            "source": _css(value="#a"),
            "target": _css(value="#b"),
        },
        {"type": "drag", "target": _css(value="#b")},
        {"type": "navigation", "url": "http://x/"},
        {"type": "wait", "milliseconds": 250},
        {"type": "dialog", "message": "hi"},
        {"type": "click", "target": {"locators": []}},
        {"type": "download"},
    ]


def test_css_selector_candidates() -> None:
    """CSS candidates win; others become attribute selectors."""
    expect_none(value=fs.css_selector(target=None))
    expect_none(value=fs.css_selector(target={}))
    expect_none(value=fs.css_selector(target={"locators": ["x"]}))
    expect_equal(
        actual=fs.css_selector(target=_css(value="#x")),
        expected="#x",
    )
    for kind, extra, expected in (
        ("test_id", {"value": "t"}, '[data-testid="t"]'),
        ("placeholder", {"value": "p"}, '[placeholder="p"]'),
        ("label", {"value": "l"}, '[aria-label="l"]'),
        ("role", {"role": "tab"}, '[role="tab"]'),
    ):
        target: fs.Event = {"locators": [{"kind": kind, **extra}]}
        expect_equal(actual=fs.css_selector(target=target), expected=expected)
    expect_none(value=fs.css_selector(target={"locators": [{"kind": "role"}]}))
    expect_none(
        value=fs.css_selector(target={"locators": [{"kind": "weird"}]}),
    )
    mixed: fs.Event = {
        "locators": [
            {"kind": "role", "role": "button", "name": "Go"},
            {"kind": "css", "value": "#go"},
        ],
    }
    expect_equal(actual=fs.css_selector(target=mixed), expected="#go")


def test_actions_become_valid_events() -> None:
    """Every mapped action yields a schema-valid, ordered event."""
    events: list[fs.Event] = fs.actions_to_events(
        actions=Constants.actions,
        flow_id="f",
    )
    kinds: list[object] = [event["kind"] for event in events]
    expect_equal(actual=kinds[0], expected="click")
    expect_in(member="url_change", container=kinds)
    expect_in(member="keystroke", container=kinds)
    expect_in(member="console", container=kinds)
    expect_equal(
        actual=[event["sequence"] for event in events],
        expected=list(range(len(events))),
    )
    expect_equal(
        actual=len({str(object=event["id"]) for event in events}),
        expected=len(events),
    )
    for event in events:
        fs.validate_event(event=event)
    drag: fs.Event = next(event for event in events if event["kind"] == "drag")
    expect_equal(
        actual=(drag["selector"], drag["payload"]),
        expected=("#a", "#b"),
    )
    scroll: list[fs.Event] = [e for e in events if e["kind"] == "scroll"]
    expect_equal(actual=scroll[0]["selector"], expected="html")


def test_events_roundtrip_to_actions() -> None:
    """Exported events convert back into replayable actions."""
    events: list[fs.Event] = fs.actions_to_events(
        actions=Constants.actions,
        flow_id="f",
    )
    back: list[fs.Event] = [
        a for e in events if (a := fs.event_action(event=e)) is not None
    ]
    types: list[object] = [a["type"] for a in back]
    expect_true(
        condition={
            "click",
            "fill",
            "key",
            "scroll",
            "drag",
            "navigation",
            "wait",
        }
        <= set(types),
    )
    key: fs.Event = next(a for a in back if _control_key(action=a))
    expect_equal(actual=key["key"], expected="A")
    space: fs.Event = fs.KeyChord.parse(chord="Space")
    expect_equal(actual=space["key"], expected=" ")
    expect_equal(actual=fs.KeyChord.parse(chord="")["key"], expected="")
    position: fs.Event | None = fs.event_action(
        event={
            "kind": "position_pointer",
            "position_action": "click",
            "x": 1,
            "y": 2,
        },
    )
    position = require(value=position)
    expect_none(value=fs.event_action(event={"kind": "response"}))
    expect_none(value=fs.event_action(event={"kind": "click"}))
    expect_none(value=fs.event_action(event={"kind": "keystroke"}))
    expect_none(value=fs.event_action(event={"kind": "wait", "payload": "x"}))
    expect_none(value=fs.event_action(event={"kind": "url_change"}))
    expect_none(
        value=fs.event_action(event={"kind": "drag", "selector": "#a"}),
    )
    expect_none(value=fs.event_action(event={"kind": "input_text"}))
    expect_none(value=fs.event_action(event={"kind": "scroll"}))
    bad: fs.Event | None = fs.event_action(
        event={"kind": "scroll", "selector": "#a", "payload": "{bad"},
    )
    bad = require(value=bad)
    expect_equal(actual=(bad["x"], bad["y"]), expected=(0, 0))


def test_workspace_files(tmp_path: Path) -> None:
    """Workspaces are written deterministically and read back.

    Args:
        tmp_path: Per-test temporary directory.

    """
    events: list[fs.Event] = fs.actions_to_events(
        actions=Constants.actions,
        flow_id="f",
    )
    workspace: fs.Event = fs.build_workspace(
        flows=[fs.build_flow(flow_id="f", name="Demo", events=events)],
    )
    path: Path = tmp_path / "w" / "a.pwflow.json"
    fs.write_workspace(path=path, workspace=workspace)
    expect_equal(actual=loads(s=path.read_text())["version"], expected=3)
    expect_true(
        condition=len(fs.load_flow_actions(path=path)) > Constants.min_actions,
    )
    expect_true(condition=bool(fs.load_flow_actions(path=path, flow_id="f")))
    with pytest.raises(
        expected_exception=fs.WorkspaceActionError,
        match="not found",
    ):
        _ = fs.load_flow_actions(path=path, flow_id="nope")
    program: Path = tmp_path / "p.json"
    program.write_text(data=dumps(obj=[{"type": "click"}, 3]))
    expect_equal(
        actual=fs.load_flow_actions(path=program),
        expected=[{"type": "click"}],
    )
    program.write_text(data="{}")
    with pytest.raises(
        expected_exception=fs.WorkspaceActionError,
        match="Unsupported workspace version",
    ):
        _ = fs.load_flow_actions(path=program)
    program.write_text(data=dumps(obj={"flows": [1]}))
    with pytest.raises(expected_exception=fs.WorkspaceActionError):
        _ = fs.load_flow_actions(path=program)


def test_exports_load_in_real_flow_studio(tmp_path: Path) -> None:
    """The bundled Studio's own codec and protocol accept the output.

    Args:
        tmp_path: Per-test temporary directory.

    """
    if not (
        Constants.studio_src
        / "exactus"
        / "tools"
        / "record"
        / "studio"
        / "__main__.py"
    ).is_file():
        pytest.skip(reason="Exactus Record is not bundled")
    sys_path.insert(0, str(object=Constants.studio_src))
    try:
        protocol: ModuleType = import_module(
            name="exactus.tools.record.recorder_protocol",
        )
        store: ModuleType = import_module(name="exactus.tools.record.store")
    finally:
        sys_path.remove(str(object=Constants.studio_src))
    events: list[fs.Event] = fs.actions_to_events(
        actions=Constants.actions,
        flow_id="f",
    )
    path: Path = tmp_path / "x.pwflow.json"
    fs.write_workspace(
        path=path,
        workspace=fs.build_workspace(
            flows=[fs.build_flow(flow_id="f", name="Demo", events=events)],
        ),
    )
    loaded: _Workspace = cast(
        typ="_Workspace",
        val=store.WorkspaceCodec.load(path=path),
    )
    expect_equal(actual=len(loaded.flows[0].events), expected=len(events))
    for event in events:
        line: bytes = fs.encode_message(
            message=fs.bridge_event(event=event, flow_id="f"),
        )
        _ = protocol.RecorderProtocol.decode_event(line=line)


@pytest.mark.parametrize(
    "event",
    [
        {"kind": "click"},
        {"kind": "click", "selector": "#a", "x": 1},
        {"kind": "position_pointer", "selector": "#a"},
        {"kind": "position_pointer", "position_action": "click"},
    ],
)
def test_invalid_events_rejected(event: fs.Event) -> None:
    """Targeting invariants are enforced before sending.

    Args:
        event: Value for ``event``.

    """
    with pytest.raises(expected_exception=fs.WorkspaceActionError):
        fs.validate_event(event=event)
    fs.validate_event(
        event={
            "kind": "position_pointer",
            "position_action": "click",
            "x": 1,
            "y": 2,
        },
    )
