# Copyright (c) 2026 Project contributors
"""Verify crawler projects open and replay in browser Studio."""

from __future__ import annotations

from asyncio import run as run_async
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, cast

import pytest
from playwright.sync_api import sync_playwright

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.click_explorer import CaptureVariant, ExplorerOptions
from exactus.tools.record.discovery import discover
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from playwright.sync_api import Browser, Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Flow, TimelineEvent, Workspace
    from exactus.tools.record.workspace_actions import Event


@pytest.fixture
def discovery_target(tmp_path: Path) -> Iterator[str]:
    """Serve a deterministic target revealing two ordered click actions.

    Args:
        tmp_path: Disposable target files.

    Yields:
        Loopback target URL.

    """
    site: Path = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        data=(
            dedent(
                text=(
                    "    <!doctype html><html><body>\n            <main id"
                    '="screen" style="height:400px;background:#eee">\n    '
                    '        <h1 id="outcome">Start</h1>\n            <but'
                    'ton id="first" onclick="this.hidden=true;\n          '
                    "    document.querySelector('#second').hidden=false;\n"
                    "              document.querySelector('#screen').style"
                    ".background='#c00'\">Next</button>\n            <but"
                    'ton id="second" hidden onclick="this.hidden=true;\n  '
                    "            document.querySelector('#outcome').textCo"
                    "ntent='Done';\n              document.querySelector('"
                    "#screen').style.background='#00c'\">Finish</button>"
                    "\n            </main></body></html>"
                ),
            )
        ),
        encoding="utf-8",
    )
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        server_address=("127.0.0.1", 0),
        RequestHandlerClass=partial(
            SimpleHTTPRequestHandler,
            directory=str(object=site),
        ),
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("snapshots", [True, False])
def test_discovery_opens_a_replayable_studio_project(
    discovery_target: str,
    tmp_path: Path,
    *,
    snapshots: bool,
) -> None:
    """Discover clicks, open their project, and replay the exact sequence.

    Args:
        discovery_target: Local deterministic application.
        tmp_path: Disposable project and evidence directory.
        snapshots: Requested capture policy.

    """
    output: Path = tmp_path / "crawl"
    messages: list[Event] = []
    run_async(
        main=discover(
            options=ExplorerOptions(
                url=discovery_target,
                output=output,
                capture_ui_changes=snapshots,
                max_depth=2,
                max_states=3,
                workers=1,
                settle_ms=50,
                width=640,
                height=480,
                variant=CaptureVariant(
                    name="test",
                    width=640,
                    height=480,
                    color_scheme="light",
                    is_mobile=False,
                    has_touch=False,
                    scale=1,
                ),
            ),
            cancelled=lambda: False,
            emit=messages.append,
        ),
    )
    project: Path = output / "discovered.pwflow.json"
    workspace: Workspace = WorkspaceCodec.load(path=project)
    flow: Flow = max(workspace.flows, key=lambda item: len(item.events))
    expect_equal(actual=len(flow.events), expected=6 if snapshots else 3)
    actions: list[TimelineEvent] = [
        event for event in flow.events if event.payload != "__screenshot__"
    ]
    expect_equal(actual=bool(workspace.screenshots), expected=snapshots)
    expect_equal(
        actual=bool(list(output.glob(pattern="*.png"))),
        expected=snapshots,
    )
    expect_equal(
        actual=[event.selector for event in actions],
        expected=[None, "#first", "#second"],
    )
    expect_equal(
        actual=[event.elapsed_ms for event in actions],
        expected=[0, 500, 1000],
    )
    service: StudioService = StudioService(
        root=tmp_path / "studio",
        headless=True,
    )
    service.start()
    try:
        service.controller.receive(message=messages[-1])
        opened: Workspace = service.controller.workspace
        expect_equal(actual=opened.flows, expected=workspace.flows)
        expect_equal(
            actual=service.snapshot()["active_flow_id"],
            expected=flow.flow_id,
        )
        expect_true(
            condition=all(item.flow_id != "flow-1" for item in opened.flows),
        )
        document: dict[str, JsonValue] = cast(
            typ="Event",
            val=WorkspaceCodec.to_json_value(workspace=opened),
        )
        flows: list[dict[str, JsonValue]] = cast(
            typ="list[Event]",
            val=document["flows"],
        )
        selected: dict[str, JsonValue] = next(
            item for item in flows if item["id"] == flow.flow_id
        )
        with sync_playwright() as playwright:
            browser: Browser = playwright.chromium.launch(headless=True)
            try:
                page: Page = browser.new_page()
                result: dict[str, JsonValue] = FlowRunner(
                    output=tmp_path / "replay",
                ).run(
                    page=page,
                    message={
                        "run_id": "crawl-replay",
                        "flow_id": selected["id"],
                        "events": selected["events"],
                        "device_mode": "desktop",
                    },
                )
                expect_equal(actual=result["status"], expected="succeeded")
                expect_equal(
                    actual=page.locator(selector="#outcome").inner_text(),
                    expected="Done",
                )
            finally:
                browser.close()
    finally:
        service.stop()
