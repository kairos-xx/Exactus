# Copyright (c) 2026 Project contributors
"""Cover live-input validation and read-only target inspection boundaries."""

from __future__ import annotations

from http import HTTPStatus
from json import loads
from sys import executable
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.sync_api import CDPSession, sync_playwright

from exactus.packages.server import local
from exactus.tests.common.support import expect_equal, expect_true
from exactus.tests.tools.record.test_studio_http_contract import (
    authorized,
    await_state,
    edit,
    request,
)
from exactus.tools.record.studio.demo import demo_site
from exactus.tools.record.studio.service import StudioService
from exactus.tools.record.studio.target_inspection import inspect_target
from exactus.tools.record.studio.worker import validate_target_url

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import (
        Browser,
        FloatRect,
        Frame,
        FrameLocator,
        Page,
    )

    from exactus.tests.tools.record.test_studio_http_contract import Reply
    from exactus.tools.record.execution import ExecutionState
    from exactus.tools.record.store import JsonValue
    from exactus.tools.record.studio.controller import StudioController


def test_preview_survives_missing_screencast_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seed a real JPEG even when Chromium never sends a screencast frame.

    Args:
        tmp_path: Isolated service storage directory.
        monkeypatch: Restore the transport method after this regression test.

    """
    original_send: Callable[..., object] = CDPSession.send

    def send(
        session: CDPSession,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> JsonValue:
        """Disable only the frame stream while preserving browser commands.

        Args:
            session: Chromium transport owned by the browser thread.
            method: Protocol method requested by the worker.
            params: Optional protocol method arguments.

        Returns:
            Original protocol response, or an empty acknowledgement.

        """
        if method == "Page.startScreencast":
            return {}
        return cast(
            typ="JsonValue",
            val=original_send(self=session, method=method, params=params),
        )

    monkeypatch.setattr(target=CDPSession, name="send", value=send)
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        edit(service=service, headers=headers, command="demo.open", payload={})
        await_state(service=service, key="target_state", expected="ready")
        deadline: float = monotonic() + 10
        while not service.worker.preview and monotonic() < deadline:
            sleep(0.05)
        preview: Reply = request(
            service=service,
            path="/api/target-preview",
            headers=headers,
        )
        expect_equal(actual=preview.status, expected=200)
        expect_true(condition=preview.body.startswith(b"\xff\xd8"))
        age: str | None = next(
            (
                value
                for key, value in preview.headers.items()
                if key.lower() == "x-frame-age-ms"
            ),
            None,
        )
        expect_true(condition=age is not None and age.isdigit())
        expect_equal(
            actual=len(service.controller.workspace.screenshots),
            expected=0,
        )
    finally:
        service.stop()


@final
class Constants:
    """Group module-level constants.

    Attributes:
        ratio_tolerance: Grouped module constant.
        min_frames: Grouped module constant.
        stale_after_ms: Grouped module constant.

    """

    ratio_tolerance: Final[float] = 0.02
    min_frames: Final[int] = 10
    stale_after_ms: Final[int] = 3000


def jpeg_size(frame: bytes) -> tuple[int, int]:
    """Read pixel dimensions from a JPEG start-of-frame segment.

    Args:
        frame: Complete JPEG bytes.

    Returns:
        Width and height in pixels.

    Raises:
        ValueError: When the JPEG has no frame header.

    """
    cursor: int = 2
    while cursor + 4 <= len(frame):
        marker: int = frame[cursor + 1]
        length: int = int.from_bytes(
            bytes=frame[cursor + 2 : cursor + 4],
            byteorder="big",
        )
        if marker in {192, 193, 194}:
            height: int = int.from_bytes(
                bytes=frame[cursor + 5 : cursor + 7],
                byteorder="big",
            )
            width: int = int.from_bytes(
                bytes=frame[cursor + 7 : cursor + 9],
                byteorder="big",
            )
            return (width, height)
        cursor += 2 + length
    msg: str = "JPEG has no frame header."
    raise ValueError(msg)


def _expect_hit_contains_point(
    *,
    element: dict[str, JsonValue],
    x: float,
    y: float,
) -> None:
    """Require the inspected element bounds to contain the probed point.

    Args:
        element: Inspection payload from the target hit test.
        x: Probed viewport horizontal coordinate.
        y: Probed viewport vertical coordinate.

    """
    rect: JsonValue = element["rect"]
    expect_true(condition=isinstance(rect, dict))
    if not isinstance(rect, dict):
        return
    bounds: dict[str, float] = {
        key: float(value)
        for key, value in rect.items()
        if isinstance(value, (int, float)) and (not isinstance(value, bool))
    }
    rect_keys: set[str] = {"x", "y", "width", "height"}
    expect_true(condition=rect_keys <= bounds.keys())
    if rect_keys <= bounds.keys():
        left, top = (bounds["x"], bounds["y"])
        expect_true(
            condition=left - 1 <= x <= left + bounds["width"] + 1
            and top - 1 <= y <= top + bounds["height"] + 1,
            message=f"{element['selector']} does not contain {x},{y}",
        )


def test_preview_maps_input_after_full_page_screenshot(tmp_path: Path) -> None:
    """Keep preview geometry and hits correct after a full-page capture.

    The shared runner captures full-page screenshots on the previewed page.
    Chromium resizes the page for that capture, so any frame produced meanwhile
    has the wrong geometry. Those frames must never replace the preview.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        edit(service=service, headers=headers, command="demo.open", payload={})
        await_state(service=service, key="target_state", expected="ready")
        edit(service=service, headers=headers, command="run.play", payload={})
        await_state(service=service, key="execution_run_id", expected=None)
        expect_true(condition=bool(service.controller.workspace.screenshots))
        size: JsonValue = service.snapshot()["viewport"]
        expect_true(condition=isinstance(size, dict))
        if not isinstance(size, dict):
            return
        width_value: JsonValue = size["width"]
        height_value: JsonValue = size["height"]
        expect_true(
            condition=isinstance(width_value, int)
            and isinstance(height_value, int),
        )
        if not isinstance(width_value, int) or not isinstance(
            height_value,
            int,
        ):
            return
        page_width, page_height = (width_value, height_value)
        deadline: float = monotonic() + 15
        reply: Reply = request(
            service=service,
            path="/api/target-preview",
            headers=headers,
        )
        while reply.status != HTTPStatus.OK and monotonic() < deadline:
            sleep(0.05)
            reply = request(
                service=service,
                path="/api/target-preview",
                headers=headers,
            )
        expect_equal(actual=reply.status, expected=HTTPStatus.OK)
        width, height = jpeg_size(frame=reply.body)
        aspect_tolerance: float = 0.02
        expect_true(
            condition=abs(width / height - page_width / page_height)
            < aspect_tolerance,
            message=(
                f"Preview {width}x{height} is not {page_width}x{page_height}."
            ),
        )
        for fx, fy in [(0.5, 0.1), (0.25, 0.4), (0.5, 0.5), (0.75, 0.3)]:
            x: float = page_width * fx
            y: float = page_height * fy
            service.controller.receive(
                message={"type": "target_inspection", "element": None},
            )
            edit(
                service=service,
                headers=headers,
                command="browser.input",
                payload={"action": "inspect", "x": x, "y": y, "picked": True},
            )
            deadline = monotonic() + 5
            element: JsonValue = None
            while element is None and monotonic() < deadline:
                seen: JsonValue = service.snapshot().get("target_inspection")
                element = (
                    seen.get("element") if isinstance(seen, dict) else None
                )
                sleep(0.05)
            if not isinstance(element, dict):
                continue
            _expect_hit_contains_point(element=element, x=x, y=y)
    finally:
        service.stop()


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("file:///tmp/private.html", "http:// or https://"),
        ("https:///missing-host", "http:// or https://"),
        ("https://user:secret@example.com/", "login form"),
    ],
)
def test_target_url_rejects_unsafe_destinations(
    url: str,
    message: str,
) -> None:
    """Reject unsupported destinations before queuing a browser operation.

    Args:
        url: Destination that must not reach the managed browser.
        message: Expected explanation for the rejected destination.

    """
    with pytest.raises(expected_exception=ValueError, match=message):
        validate_target_url(url=url)


def test_live_input_boundaries(tmp_path: Path) -> None:
    """Reject invalid input without dispatching it or mutating the document.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        edit(
            service=service,
            headers=headers,
            command="browser.input",
            payload={"action": "key", "key": "Tab"},
            status=400,
        )
        service.controller.receive(
            message={"type": "target_state", "state": "ready"},
        )
        revision: JsonValue = service.snapshot()["revision"]
        payloads: list[dict[str, JsonValue]] = [
            {"action": "unsupported"},
            {"action": "click", "x": -1, "y": 0},
            {"action": "inspect", "x": 0, "y": -1},
            {"action": "wheel", "x": 1, "y": 1, "dx": 2001, "dy": 0},
            {"action": "wheel", "x": 1, "y": 1, "dx": 0, "dy": -2001},
            {"action": "key", "key": "x" * 81},
            {"action": "key", "key": ""},
            {"action": "key", "key": "Enter", "code": 5},
            {"action": "pointer_down", "x": 1, "y": 1, "button": 99},
            {"action": "pointer_move", "x": 1, "y": 1, "buttons": -1},
            {"action": "touch_start", "x": 1, "y": 1, "pointer_id": -1},
        ]
        for payload in payloads:
            edit(
                service=service,
                headers=headers,
                command="browser.input",
                payload=payload,
                status=400,
            )
            expect_equal(
                actual=service.snapshot()["revision"],
                expected=revision,
            )
    finally:
        service.stop()


def test_command_guards_reject_invalid_and_busy_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject stale revisions, malformed inputs and busy-state operations.

    Args:
        tmp_path: Isolated service storage directory.
        monkeypatch: Attribute override supplied by pytest.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        controller: StudioController = service.controller
        expect_equal(
            actual=controller.project_slug,
            expected=controller.library.slug_of(folder=tmp_path),
        )
        revision: int = cast(typ="int", val=service.snapshot()["revision"])
        with pytest.raises(
            expected_exception=ValueError,
            match="Stale editor revision",
        ):
            _ = controller.dispatch(
                command="flow.select",
                payload={"flow_id": "flow-1"},
                revision=revision + 1,
            )
        for parameters, message in (
            ("x", "must be a list"),
            ([1], "must be an object"),
        ):
            with pytest.raises(expected_exception=TypeError, match=message):
                _ = controller.dispatch(
                    command="flow.update",
                    payload={
                        "name": "Flow",
                        "parameters": cast(typ="JsonValue", val=parameters),
                    },
                    revision=revision,
                )
        with pytest.raises(
            expected_exception=ValueError,
            match="Unknown recording",
        ):
            _ = controller.dispatch(
                command="event.add",
                payload={
                    "kind": "javascript",
                    "payload": "1",
                    "recording_group_id": "ghost",
                },
                revision=revision,
            )
        with pytest.raises(expected_exception=ValueError, match="depth 1-10"):
            _ = controller.dispatch(
                command="crawl.start",
                payload={"max_depth": "99"},
                revision=revision,
            )
        with pytest.raises(
            expected_exception=ValueError,
            match="must be a boolean",
        ):
            _ = controller.dispatch(
                command="crawl.start",
                payload={"capture_ui_changes": "yes"},
                revision=revision,
            )
        controller.receive(message={"type": "target_state", "state": "ready"})
        ready_revision: int = cast(
            typ="int",
            val=service.snapshot()["revision"],
        )
        monkeypatch.setattr(
            target=controller,
            name="_execution_state",
            value=cast(typ="ExecutionState", val=object()),
        )
        with pytest.raises(
            expected_exception=ValueError,
            match="Stop playback",
        ):
            _ = controller.dispatch(
                command="browser.input",
                payload={"action": "click", "x": 1, "y": 1},
                revision=ready_revision,
            )
        monkeypatch.setattr(
            target=controller,
            name="_execution_state",
            value=None,
        )
        monkeypatch.setattr(
            target=controller,
            name="_recording_state",
            value="recording",
        )
        for command in ("demo.open", "actions.run", "crawl.start"):
            with pytest.raises(
                expected_exception=ValueError,
                match="active operation",
            ):
                _ = controller.dispatch(
                    command=command,
                    payload={},
                    revision=ready_revision,
                )
    finally:
        service.stop()


def test_input_backpressure_is_reported_and_leaves_document_unchanged(
    tmp_path: Path,
) -> None:
    """Report a full worker queue as a retryable conflict, not a failure.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        service.controller.receive(
            message={"type": "target_state", "state": "ready"},
        )
        wheel: dict[str, JsonValue] = {
            "action": "wheel",
            "x": 1,
            "y": 1,
            "dx": 0,
            "dy": 1,
        }
        revision: JsonValue = service.snapshot()["revision"]
        max_attempts: int = 64
        accepted: int = 0
        while accepted < max_attempts:
            snapshot: dict[str, JsonValue] = service.snapshot()
            reply: Reply = request(
                service=service,
                path="/api/command",
                headers=headers,
                body={
                    "protocol": 1,
                    "id": f"flood-{accepted}",
                    "revision": snapshot["revision"],
                    "command": "browser.input",
                    "payload": wheel,
                },
            )
            if reply.status != HTTPStatus.OK:
                expect_equal(actual=reply.status, expected=HTTPStatus.CONFLICT)
                expect_true(condition=b"WORKER_BUSY" in reply.body)
                break
            accepted += 1
        expect_true(condition=0 < accepted < max_attempts)
        expect_equal(actual=service.snapshot()["revision"], expected=revision)
    finally:
        service.stop()


def test_target_inspection_names_frames_and_survives_detachment() -> None:
    """Report nested-frame hits with page bounds and tolerate navigation."""
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        try:
            page: Page = browser.new_page(
                viewport={"width": 640, "height": 480},
            )
            page.set_content(
                html=(
                    "<p style='margin:0;height:100px'>Top</p><iframe name="
                    "'inner' style='border:0;margin:0;display:block;width:"
                    "300px;height:200px' srcdoc=\"<button id='deep' styl"
                    "e='position:absolute;left:10px;top:20px;width:80px;he"
                    "ight:30px'>Deep</button>\"></iframe>"
                ),
            )
            page.wait_for_selector(selector="iframe")
            inner_frame: Frame | None = page.frame(name="inner")
            expect_true(condition=inner_frame is not None)
            if inner_frame is not None:
                inner_frame.wait_for_selector(selector="#deep")
            result: JsonValue = inspect_target(page=page, x=30, y=100 + 30)
            expect_true(condition=isinstance(result, dict))
            if isinstance(result, dict):
                expect_equal(actual=result["selector"], expected="#deep")
                expect_equal(actual=result["frame"], expected="frame inner")
                expect_true(condition=bool(result["unsupported"]))
                rect: JsonValue = result["rect"]
                expect_true(condition=isinstance(rect, dict))
                if isinstance(rect, dict):
                    frame: FrameLocator = page.frame_locator(selector="iframe")
                    deep: FloatRect | None = frame.locator(
                        selector_or_locator="#deep",
                    ).bounding_box()
                    expect_true(condition=deep is not None)
                    if deep is not None:
                        expect_equal(actual=rect["x"], expected=deep["x"])
                        expect_equal(actual=rect["y"], expected=deep["y"])
                        deep_y: JsonValue = rect["y"]
                        min_frame_top: int = 100
                        expect_true(
                            condition=isinstance(deep_y, (int, float))
                            and deep_y >= min_frame_top,
                        )
            main: JsonValue = inspect_target(page=page, x=5, y=5)
            expect_true(condition=isinstance(main, dict))
            if isinstance(main, dict):
                expect_equal(actual=main["frame"], expected="main page")
                expect_true(condition="unsupported" not in main)
            page.close()
            expect_equal(
                actual=inspect_target(page=page, x=1, y=1),
                expected=None,
            )
        finally:
            browser.close()


def test_target_inspection_is_read_only() -> None:
    """Inspect element identities and bounds without dispatching clicks."""
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        try:
            page: Page = browser.new_page(
                viewport={"width": 640, "height": 480},
            )
            page.set_content(
                html=(
                    "<button id='pick' aria-label='Choose item'>Pick"
                    "</button><button data-testid='second'>Second</button>"
                    "<button name='third'>Third</button><button>"
                    "Fallback</button>"
                ),
            )
            before: str = page.content()
            for selector in [
                "#pick",
                '[data-testid="second"]',
                '[name="third"]',
            ]:
                bounds: FloatRect | None = page.locator(
                    selector=selector,
                ).bounding_box()
                expect_true(condition=bounds is not None)
                if bounds is None:
                    continue
                result: JsonValue = inspect_target(
                    page=page,
                    x=bounds["x"] + bounds["width"] / 2,
                    y=bounds["y"] + bounds["height"] / 2,
                )
                expect_true(condition=isinstance(result, dict))
                if isinstance(result, dict):
                    expect_equal(actual=result["selector"], expected=selector)
                    expect_equal(actual=result["tag"], expected="button")
                    expect_true(condition=bool(result["text"]))
                    expect_equal(actual=result["matches"], expected=1)
                    alternatives: JsonValue = result["alternatives"]
                    expect_true(condition=isinstance(alternatives, list))
                    if isinstance(alternatives, list):
                        strategies: set[str] = {
                            str(object=item["strategy"])
                            for item in alternatives
                            if isinstance(item, dict)
                        }
                        expect_true(condition="css" in strategies)
                        expect_true(condition="role and name" in strategies)
                expect_equal(actual=page.content(), expected=before)
            expect_equal(
                actual=inspect_target(page=page, x=-1, y=-1),
                expected=None,
            )
        finally:
            browser.close()


def test_shared_demo_server_survives_another_service_stop(
    tmp_path: Path,
) -> None:
    """Keep a borrowed demo server alive when another Studio exits.

    Args:
        tmp_path: Isolated service storage directory.

    """
    first: StudioService = StudioService(
        root=tmp_path / "first",
        headless=True,
    )
    second: StudioService = StudioService(
        root=tmp_path / "second",
        headless=True,
    )
    first.start()
    try:
        second.start()
        try:
            first_headers: dict[str, str] = authorized(service=first)
            edit(
                service=first,
                headers=first_headers,
                command="demo.open",
                payload={},
            )
            await_state(service=first, key="target_state", expected="ready")
            record: tuple[int, int] | None = local.reuse_server(
                path=demo_site(),
            )
            expect_true(condition=record is not None)
            if record is None:
                return
            second_headers: dict[str, str] = authorized(service=second)
            edit(
                service=second,
                headers=second_headers,
                command="demo.open",
                payload={},
            )
            await_state(service=second, key="target_state", expected="ready")
        finally:
            second.stop()
        expect_true(condition=local.ping_server(port=record[1]))
    finally:
        first.stop()


def test_selected_profile_reaches_the_real_page_and_bad_ones_are_refused(
    tmp_path: Path,
) -> None:
    """Show the target under a saved profile and refuse unusable settings.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        edit(service=service, headers=headers, command="demo.open", payload={})
        await_state(service=service, key="target_state", expected="ready")
        phone: dict[str, JsonValue] = {
            "id": "phone",
            "name": "Phone",
            "width": 390,
            "height": 844,
            "scale": 3,
            "touch": True,
            "mobile": True,
            "media": {"prefers-color-scheme": "dark"},
        }
        bad_media: tuple[dict[str, JsonValue], ...] = (
            {"monochrome": "2"},
            {"pointer": "coarse"},
            {"x": "y"},
        )
        for bad in bad_media:
            edit(
                service=service,
                headers=headers,
                command="profile.save",
                payload={"profile": {**phone, "media": bad}},
                status=400,
            )
        edit(
            service=service,
            headers=headers,
            command="profile.save",
            payload={"profile": phone},
        )
        edit(
            service=service,
            headers=headers,
            command="viewport.preset",
            payload={"mode": "ghost"},
            status=400,
        )
        edit(
            service=service,
            headers=headers,
            command="viewport.preset",
            payload={"mode": "phone"},
        )
        expect_equal(
            actual=service.snapshot()["viewport"],
            expected={"width": 390, "height": 844},
        )
        phone_ratio: float = 390 / 844
        deadline: float = monotonic() + 15
        shape: tuple[int, int] = (0, 1)
        while (
            abs(shape[0] / shape[1] - phone_ratio) > Constants.ratio_tolerance
            and monotonic() < deadline
        ):
            frame: Reply = request(
                service=service,
                path="/api/target-preview",
                headers=headers,
            )
            if frame.status == HTTPStatus.OK:
                shape = jpeg_size(frame=frame.body)
            sleep(0.05)
        ratio: float = shape[0] / shape[1]
        expect_true(
            condition=abs(ratio - phone_ratio) <= Constants.ratio_tolerance,
            message=f"Preview stayed {shape[0]}x{shape[1]}, not a phone.",
        )
        edit(
            service=service,
            headers=headers,
            command="event.add",
            payload={
                "kind": "javascript",
                "payload": (
                    "() => ({coarse: matchMedia('(pointer: coarse)')"
                    ".matches, dark: matchMedia('(prefers-color-scheme: "
                    "dark)').matches, dpr: devicePixelRatio})"
                ),
            },
        )
        edit(service=service, headers=headers, command="run.play", payload={})
        await_state(service=service, key="execution_run_id", expected=None)
        responses: list[object] = [
            loads(s=record.response_json)
            for run in service.controller.workspace.runs[-1:]
            for record in run.action_records
            if record.response_json is not None
        ]
        seen: dict[str, object] = next(
            (
                item
                for item in responses
                if isinstance(item, dict) and "dpr" in item
            ),
            {},
        )
        expect_equal(
            actual=seen,
            expected={"coarse": True, "dark": True, "dpr": 3},
        )
        edit(
            service=service,
            headers=headers,
            command="flow.update",
            payload={"name": "Flow", "device_scope": "phone"},
        )
        edit(
            service=service,
            headers=headers,
            command="profile.delete",
            payload={"profile_id": "phone"},
            status=400,
        )
        edit(
            service=service,
            headers=headers,
            command="flow.update",
            payload={"name": "Flow", "device_scope": "shared"},
        )
        edit(
            service=service,
            headers=headers,
            command="profile.delete",
            payload={"profile_id": "phone"},
        )
        expect_equal(
            actual=service.snapshot()["device_mode"],
            expected="desktop",
        )
    finally:
        service.stop()


def test_target_is_configured_started_and_opened_through_studio(
    tmp_path: Path,
) -> None:
    """Save a service target, start it, and open the browser on its port.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        server: list[JsonValue] = [
            executable,
            "-m",
            "http.server",
            "0",
            "--bind",
            "127.0.0.1",
        ]
        bad_targets: list[dict[str, JsonValue]] = [
            {"mode": "service", "command": []},
            {"mode": "url", "url": "ftp://example.com"},
            {"mode": "service", "command": server, "cwd": "../x"},
        ]
        for bad in bad_targets:
            edit(
                service=service,
                headers=headers,
                command="target.save",
                payload={"target": bad},
                status=400,
            )
        expect_equal(
            actual=service.controller.workspace.target.url,
            expected="",
        )
        edit(
            service=service,
            headers=headers,
            command="target.save",
            payload={
                "target": {"mode": "service", "command": server, "path": "/"},
            },
        )
        expect_equal(
            actual=service.snapshot()["target_service"],
            expected={"state": "idle"},
        )
        edit(
            service=service,
            headers=headers,
            command="browser.open",
            payload={},
            status=400,
        )
        edit(
            service=service,
            headers=headers,
            command="target.start",
            payload={},
        )
        deadline: float = monotonic() + 30
        state: JsonValue = service.snapshot()["target_service"]
        while (
            isinstance(state, dict)
            and state.get("state") != "running"
            and (monotonic() < deadline)
        ):
            sleep(0.1)
            state = service.snapshot()["target_service"]
        expect_true(
            condition=isinstance(state, dict) and state["state"] == "running",
            message=f"Service state was {state!r}.",
        )
        edit(
            service=service,
            headers=headers,
            command="browser.open",
            payload={},
        )
        await_state(service=service, key="target_state", expected="ready")
        detected: JsonValue = (
            state.get("url") if isinstance(state, dict) else None
        )
        expect_true(
            condition=str(object=service.snapshot()["target_url"]).startswith(
                str(object=detected),
            ),
            message=f"Opened {service.snapshot()['target_url']}.",
        )
        edit(
            service=service,
            headers=headers,
            command="target.stop",
            payload={},
        )
        expect_equal(
            actual=service.snapshot()["target_service"],
            expected={"state": "idle"},
        )
        edit(
            service=service,
            headers=headers,
            command="target.save",
            payload={"target": {"mode": "url", "url": str(object=detected)}},
        )
        edit(
            service=service,
            headers=headers,
            command="target.check",
            payload={},
        )
        checked: JsonValue = service.snapshot()["target_check"]
        expect_true(
            condition=isinstance(checked, dict)
            and checked["state"] in {"unreachable", "reachable"},
        )
    finally:
        service.stop()


def test_a_still_page_never_looks_stale_while_it_is_watched(
    tmp_path: Path,
) -> None:
    """Keep the preview current for a page that does not repaint.

    Chromium sends frames only on change, so the worker renews a watched
    preview itself. The editor dims frames older than three seconds.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        edit(service=service, headers=headers, command="demo.open", payload={})
        await_state(service=service, key="target_state", expected="ready")
        deadline: float = monotonic() + 8
        oldest: int = 0
        seen: int = 0
        while monotonic() < deadline:
            reply: Reply = request(
                service=service,
                path="/api/target-preview",
                headers=headers,
            )
            if reply.status == HTTPStatus.OK:
                seen += 1
                age: str = next(
                    (
                        value
                        for key, value in reply.headers.items()
                        if key.lower() == "x-frame-age-ms"
                    ),
                )
                oldest = max(oldest, int(age))
            sleep(0.25)
        expect_true(condition=seen > Constants.min_frames)
        expect_true(
            condition=oldest < Constants.stale_after_ms,
            message=f"A still page's preview aged to {oldest} ms.",
        )
    finally:
        service.stop()


def test_a_new_project_suggests_the_demo_server_and_start_opens_its_page(
    tmp_path: Path,
) -> None:
    """Offer the demo's own server, start it, and show its page.

    Args:
        tmp_path: Isolated service storage directory.

    """
    service: StudioService = StudioService(root=tmp_path, headless=True)
    service.start()
    try:
        headers: dict[str, str] = authorized(service=service)
        suggestion: JsonValue = service.snapshot()["target_suggestion"]
        expect_true(condition=isinstance(suggestion, dict))
        if not isinstance(suggestion, dict):
            return
        expect_equal(actual=suggestion["mode"], expected="service")
        command: JsonValue = suggestion["command"]
        expect_true(
            condition=isinstance(command, list)
            and str(object=command[1]).endswith("server.py"),
        )
        expect_equal(
            actual=service.controller.workspace.target.mode.value,
            expected="url",
        )
        expect_equal(
            actual=service.snapshot()["target_service"],
            expected={"state": "idle"},
        )
        edit(
            service=service,
            headers=headers,
            command="target.save",
            payload={"target": suggestion},
        )
        expect_equal(
            actual=service.snapshot()["target_suggestion"],
            expected=None,
        )
        edit(
            service=service,
            headers=headers,
            command="target.start",
            payload={"open": True},
        )
        await_state(service=service, key="target_state", expected="ready")
        running: JsonValue = service.snapshot()["target_service"]
        expect_true(
            condition=isinstance(running, dict)
            and running["state"] == "running",
            message=f"Service state was {running!r}.",
        )
        base: str = (
            str(object=running["url"])
            if isinstance(running, dict)
            else "missing"
        )
        expect_true(
            condition=str(object=service.snapshot()["target_url"]).startswith(
                base,
            ),
            message=f"Opened {service.snapshot()['target_url']}, not {base}.",
        )
    finally:
        service.stop()
