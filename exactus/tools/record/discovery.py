# Copyright (c) 2026 Project contributors
"""Convert bounded crawler discoveries into editable flow documents."""

from __future__ import annotations

from asyncio import CancelledError, Task, create_task, sleep
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from PIL import Image

from exactus.tools.record.click_explorer import (
    ClickExplorer,
    ClickTarget,
    ExplorerOptions,
    StateNode,
)
from exactus.tools.record.diagnostics import DiagnosticCollector
from exactus.tools.record.project_assets import embed_assets
from exactus.tools.record.workspace_actions import (
    actions_to_events,
    build_flow,
    build_workspace,
    write_workspace,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.tools.record.json_types import JsonValue
    from exactus.tools.record.workspace_actions import Event


@dataclass(frozen=True)
class CrawlRequest:
    """Configure target discovery and the resulting Studio project.

    Attributes:
        url: Initial target URL.
        max_depth: Maximum action depth.
        max_states: Maximum distinct UI states.
        capture_ui_changes: Persist UI snapshots and replay checkpoints.
        follow_links: Follow navigable links.
        click_controls: Activate buttons and other interactive controls.
        include_selector: Optional CSS selector restricting candidates.

    """

    url: str
    max_depth: int = 2
    max_states: int = 20
    capture_ui_changes: bool = True
    follow_links: bool = True
    click_controls: bool = True
    include_selector: str | None = None


async def discover(
    *,
    options: ExplorerOptions,
    cancelled: Callable[[], bool],
    emit: Callable[[Event], None],
) -> None:
    """Explore a bounded target and publish replayable flows.

    Args:
        options: Bounded exploration configuration.
        cancelled: Cooperative cancellation predicate.
        emit: Service event callback.

    Raises:
        CancelledError: When discovery is cancelled.

    """
    explorer: ClickExplorer = ClickExplorer(options=options)
    task: Task[tuple[StateNode, ...]] = create_task(coro=explorer.run())
    try:
        while not task.done():
            if cancelled():
                task.cancel()
                emit({"type": "crawl_state", "state": "cancelled"})
                return
            emit({"type": "crawl_state", "state": "running"})
            await sleep(delay=0.25)
        states: tuple[StateNode, ...] = await task
        flows: list[Event] = []
        screenshots: list[Event] = []
        prefixes: dict[tuple[ClickTarget, ...], StateNode] = {
            state.path: state for state in states
        }
        for state in states:
            if any(not target.selector for target in state.path):
                continue
            flow, images = discovered_flow(
                state=state,
                options=options,
                prefixes=prefixes,
                flow_number=len(flows) + 1,
            )
            flows.append(flow)
            screenshots.extend(images)
        document: dict[str, JsonValue] = build_workspace(flows=flows)
        document["screenshots"] = cast(typ="JsonValue", val=screenshots)
        document = embed_assets(
            document=document,
            resolve=lambda shot: Path(str(object=shot["path"])),
        )
        write_workspace(
            path=options.output / "discovered.pwflow.json",
            workspace=document,
        )
        emit(
            {
                "type": "crawl_result",
                "workspace": document,
                "state": "completed",
                "count": len(flows),
                "diagnostics": [
                    DiagnosticCollector.serialize(event=event)
                    for event in explorer.diagnostics
                ],
            },
        )
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except CancelledError:
            if not cancelled():
                raise


def discovered_flow(
    *,
    state: StateNode,
    options: ExplorerOptions,
    prefixes: dict[tuple[ClickTarget, ...], StateNode],
    flow_number: int,
) -> tuple[Event, list[Event]]:
    """Build an editable action sequence with optional UI checkpoints.

    Args:
        state: Discovered click path.
        options: Capture policy and output directory.
        prefixes: Captured states matching intermediate path prefixes.
        flow_number: Display number within the generated project.

    Returns:
        Current-schema flow and its recorded screenshot metadata.

    """
    screenshots: list[Event] = []
    flow_id: str = f"crawl-{uuid4().hex}"
    actions: list[Event] = [
        {"type": "navigation", "url": options.url, "elapsedMs": 0},
    ]
    actions.extend(
        {
            "type": "click",
            "target": {
                "locators": [{"kind": "css", "value": target.selector}],
            },
            "elapsedMs": (index + 1) * 500,
        }
        for index, target in enumerate(iterable=state.path)
        if target.selector
    )
    events: list[dict[str, JsonValue]] = actions_to_events(
        actions=actions,
        flow_id=flow_id,
    )
    if options.capture_ui_changes:
        sequence: list[Event] = []
        for index, action in enumerate(iterable=events):
            sequence.append(action)
            checkpoint: Event = {
                **action,
                "id": f"{flow_id}-shot-{index}",
                "kind": "note",
                "layer": "timing",
                "label": "Capture UI change",
                "selector": None,
                "url": None,
                "payload": "__screenshot__",
            }
            sequence.append(checkpoint)
            prefix_state: StateNode | None = prefixes.get(
                tuple(state.path[:index]),
            )
            if prefix_state is not None and prefix_state.screenshot:
                image: Path = options.output / prefix_state.screenshot
                with Image.open(fp=image) as pixels:
                    width, height = pixels.size
                screenshots.append(
                    {
                        "id": f"{flow_id}-snapshot-{index}",
                        "flow_id": flow_id,
                        "event_id": checkpoint["id"],
                        "phase": "record",
                        "path": str(object=image.resolve()),
                        "width": width,
                        "height": height,
                        "sha256": sha256(data=image.read_bytes()).hexdigest(),
                    },
                )
        events = sequence
        for index, event in enumerate(iterable=events):
            event["sequence"] = index
    flow: dict[str, JsonValue] = build_flow(
        flow_id=flow_id,
        name=f"Discovered state {flow_number}",
        events=events,
        notes=(
            "Discovered click sequence. Timeline positions use "
            "500 ms spacing; crawl timings are not measured."
        ),
    )
    return flow, screenshots
