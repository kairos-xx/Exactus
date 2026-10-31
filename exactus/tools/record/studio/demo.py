# Copyright (c) 2026 Project contributors
"""Create an editable demonstration using the ordinary Studio flow runtime."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from sys import executable
from typing import TYPE_CHECKING

from exactus.tools.record.model import (
    ActionContract,
    AssertionKind,
    AssertionOperator,
    AssertionSpec,
    EventKind,
    Flow,
    FlowEdge,
    Target,
    TargetMode,
    TimelineEvent,
    TimelineLayer,
    Workspace,
)

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec


def demo_site() -> Path:
    """Locate the bundled target application.

    Returns:
        Directory containing the real demo application.

    Raises:
        ValueError: When the source distribution omits the demo assets.

    """
    path: Path = _demo_root() / "static"
    if not (path / "index.html").is_file():
        msg: str = "The bundled demo site is unavailable in this installation."
        raise ValueError(msg)
    return path


def demo_target() -> Target | None:
    """Suggest starting the bundled demo application's own server.

    The command is built from where the demo is installed, so it is correct
    on this machine and is never stored in a project unless the user saves it.

    Returns:
        A service target that picks a free port, or None without the demo.

    """
    try:
        root: Path = _demo_root()
    except ValueError:
        return None
    server: Path = root / "server.py"
    if not server.is_file():
        return None
    return Target(
        mode=TargetMode.SERVICE,
        command=(executable, str(object=server), "--port", "0"),
        path="/",
    )


def _demo_root() -> Path:
    """Resolve demo assets from an installation or a source checkout.

    Returns:
        Directory containing the demo package.

    Raises:
        ValueError: When neither packaged nor checkout assets are available.

    """
    specification: ModuleSpec | None = find_spec(name="demo")
    candidates: tuple[Path, ...] = (
        *(
            (Path(specification.origin).parent,)
            if specification is not None and specification.origin is not None
            else ()
        ),
        Path(__file__).resolve().parents[4] / "demo",
    )
    for candidate in candidates:
        if (candidate / "server.py").is_file() and (
            candidate / "static" / "index.html"
        ).is_file():
            return candidate
    msg: str = "The bundled demo site is unavailable in this installation."
    raise ValueError(msg)


def demo_workspace(*, url: str) -> Workspace:
    """Bind a replayable graph to the demo server's actual runtime URL.

    Args:
        url: Ready loopback server URL.

    Returns:
        Three connected flows with real actions, assertions and screenshots.

    """
    specifications: tuple[
        tuple[str, tuple[tuple[str, str, str, str], ...]],
        ...,
    ] = (
        ("Open demo", (("url_change", "", "Open demo site", "Ready"),)),
        (
            "Explore controls",
            (
                ("click", "#tab-settings", "Open Settings tab", ""),
                ("click", "[data-density]", "Enable compact layout", ""),
                ("click", "[aria-controls='details']", "Show details", ""),
                (
                    "click",
                    "[aria-controls='advanced']",
                    "Show advanced options",
                    "",
                ),
                ("click", "[data-open-preview]", "Open preview dialog", ""),
                ("click", "[data-close-preview]", "Close preview dialog", ""),
            ),
        ),
        (
            "Save and verify",
            (("click", "[data-save-draft]", "Save draft", "Draft saved"),),
        ),
    )
    flows: list[Flow] = []
    visible: dict[str, str] = {
        "#tab-settings": "#panel-settings",
        "[aria-controls='details']": "#details",
        "[aria-controls='advanced']": "#advanced",
        "[data-open-preview]": ".preview",
    }
    for index, (name, steps) in enumerate(iterable=specifications, start=1):
        flow_id: str = f"demo-{index}"
        events: list[TimelineEvent] = []
        for sequence, (kind, selector, label, expected) in enumerate(
            iterable=steps,
        ):
            checks: list[AssertionSpec] = []
            if expected:
                checks.append(
                    AssertionSpec(
                        assertion_id=f"{flow_id}-{sequence}-status",
                        label=f"Status is {expected}",
                        kind=AssertionKind.DOM_TEXT,
                        operator=AssertionOperator.EQUALS,
                        target="[data-status]",
                        expected=expected,
                    ),
                )
            if selector in visible:
                checks.append(
                    AssertionSpec(
                        assertion_id=f"{flow_id}-{sequence}-visible",
                        label="Opened surface is visible",
                        kind=AssertionKind.DOM_VISIBLE,
                        operator=AssertionOperator.EXISTS,
                        target=visible[selector],
                    ),
                )
            events.append(
                TimelineEvent(
                    event_id=f"{flow_id}-{sequence}",
                    flow_id=flow_id,
                    sequence=sequence,
                    elapsed_ms=sequence * 500,
                    layer=TimelineLayer.NAVIGATION
                    if kind == "url_change"
                    else TimelineLayer.INTERACTION,
                    kind=EventKind(kind),
                    label=label,
                    selector=selector or None,
                    url=url if kind == "url_change" else None,
                    contract=ActionContract(postconditions=tuple(checks)),
                ),
            )
        flows.append(
            Flow(
                flow_id=flow_id,
                name=name,
                task_description=name,
                expected_behavior="All demo action assertions pass.",
                notes=(
                    "Run from Open demo to replay the complete graph. "
                    "Record appends target actions to the selected flow."
                ),
                capture_record_images=True,
                capture_play_images=True,
                events=tuple(events),
            ),
        )
    return Workspace(
        flows=tuple(flows),
        edges=(
            FlowEdge(source_flow_id="demo-1", target_flow_id="demo-2"),
            FlowEdge(source_flow_id="demo-2", target_flow_id="demo-3"),
        ),
    )
