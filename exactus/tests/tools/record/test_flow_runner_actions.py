# Copyright (c) 2026 Project contributors
"""Run data, viewport, touch and REST actions in a real Chromium page."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import dumps
from threading import Thread
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.sync_api import Browser, BrowserContext, sync_playwright

from exactus.tests.common.support import expect_equal, private_as
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    EventKind,
    RuntimeVariable,
    TimelineEvent,
    TimelineLayer,
    ValueType,
)
from exactus.tools.record.selector_sandbox import RunStreams
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        page: Grouped module constant.

    """

    page: Final[str] = (
        '<p id="label" data-x="attr-value">Hello</p><input id="number" '
        'value="42"><input id="ratio" value="2.5"><input id="name" '
        'value="Ana"><input id="flag" type="checkbox" checked><ul><li '
        'class="row">a</li><li class="row">b</li></ul><div id="pad" '
        'style="width:300px;height:300px"></div><script>window.touches = '
        "[];for (const type of ['touchstart','touchmove','touchend']) "
        "document.addEventListener(type, () => "
        "window.touches.push(type));</script>"
    )


class _Handler(BaseHTTPRequestHandler):
    """Serve one small JSON document with a marker header."""

    def do_get(self) -> None:
        """Answer every GET with a fixed JSON body."""
        body: bytes = dumps(obj={"id": 7, "name": "Ana"}).encode()
        self.send_response(code=200)
        self.send_header(keyword="Content-Type", value="application/json")
        self.send_header(keyword="X-Test", value="yes")
        self.send_header(keyword="Content-Length", value=str(object=len(body)))
        self.end_headers()
        self.wfile.write(body)

    def __getattr__(self, name: str) -> object:
        """Resolve the ``do_GET`` dispatch name to ``do_get``.

        Args:
            name: Attribute being resolved.

        Returns:
            The GET handler for ``do_GET``.

        Raises:
            AttributeError: For every other missing attribute.

        """
        if name == "do_GET":
            return self.do_get
        raise AttributeError(name)


@pytest.fixture
def server() -> Iterator[str]:
    """Run a local HTTP server for REST actions.

    Yields:
        Base URL of the running server.

    """
    httpd: HTTPServer = HTTPServer(("127.0.0.1", 0), _Handler)
    thread: Thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a touch-enabled Chromium page holding the fixture markup.

    Yields:
        A page with the shared test document loaded.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        context: BrowserContext = browser.new_context(
            viewport={"width": 640, "height": 480},
            has_touch=True,
        )
        page: Page = context.new_page()
        page.set_content(html=Constants.page)
        yield page
        browser.close()


@dataclass(frozen=True, slots=True, kw_only=True)
class _Spec:
    """One authored action, before serialization.

    Attributes:
        index: Position in the flow.
        kind: Action kind.
        selector: Element the action targets.
        url: Address of a request action.
        method: HTTP method of a request action.
        payload: Action payload, usually a JSON specification.
        output_variable: Variable receiving the action result.
        share_session_cookies: Send the request with the page's cookies.

    """

    index: int
    kind: EventKind
    selector: str | None = None
    url: str | None = None
    method: str | None = None
    payload: str | None = None
    output_variable: str | None = None
    share_session_cookies: bool = False


def _event(*, spec: _Spec) -> Event:
    """Serialize one authored action.

    Args:
        spec: The action to serialize.

    Returns:
        The event as workspace JSON.

    """
    event: TimelineEvent = TimelineEvent(
        event_id=f"e{spec.index}",
        flow_id="flow",
        sequence=spec.index,
        elapsed_ms=spec.index * 10,
        layer=TimelineLayer.NETWORK
        if spec.kind is EventKind.HTTP_CALL
        else TimelineLayer.INTERACTION,
        kind=spec.kind,
        label=spec.kind.value,
        selector=spec.selector,
        url=spec.url,
        method=spec.method,
        payload=spec.payload,
        output_variable=spec.output_variable,
        share_session_cookies=spec.share_session_cookies,
    )
    return cast(
        typ="Event",
        val=WorkspaceCodec.event_to_json_value(event=event),
    )


def _run(
    *,
    page: Page,
    tmp_path: Path,
    events: list[Event],
    variables: list[Event] | None = None,
) -> tuple[Event, RunStreams]:
    """Run actions and return the result with the run variables.

    Args:
        page: Page the actions run against.
        tmp_path: Disposable artifact folder.
        events: Actions to run in order.
        variables: Variables the run starts with, as the player receives them.

    Returns:
        The run result and the variables the run produced.

    """
    runner: FlowRunner = FlowRunner(output=tmp_path)
    result: Event = runner.run(
        page=page,
        message=cast(
            typ="Event",
            val={
                "flow_id": "flow",
                "events": cast(typ="JsonValue", val=events),
                "capture_images": False,
                "variables": cast(typ="JsonValue", val=variables or []),
            },
        ),
    )
    streams: RunStreams = private_as(
        owner=runner,
        name="_streams",
        kind=RunStreams,
    )
    return (result, streams)


def test_extract_and_set_variable_actions(page: Page, tmp_path: Path) -> None:
    """Read typed values from the page and author typed variables.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.

    """
    extracts: tuple[tuple[str, str, str, str], ...] = (
        ("text", "#label", "label_text", ""),
        ("int", "#number", "number_value", ""),
        ("float", "#ratio", "ratio_value", ""),
        ("value", "#name", "name_value", ""),
        ("checked", "#flag", "flag_value", ""),
        ("attribute", "#label", "attr_value", "data-x"),
        ("count", ".row", "row_count", ""),
    )
    events: list[Event] = [
        _event(
            spec=_Spec(
                index=index,
                kind=EventKind.EXTRACT_VALUE,
                selector=selector,
                output_variable=variable,
                payload=dumps(
                    obj={"extract": extract, "attribute": attribute},
                ),
            ),
        )
        for index, (extract, selector, variable, attribute) in enumerate(
            iterable=extracts,
        )
    ]
    for offset, (value_type, value, variable) in enumerate(
        iterable=(
            ("boolean", "yes", "is_yes"),
            ("float", "1.5", "as_float"),
            ("integer", "9", "as_int"),
            ("json", '{"a": 1}', "as_json"),
            ("text", "plain {{label_text}}", "as_text"),
        ),
        start=len(events),
    ):
        events.append(
            _event(
                spec=_Spec(
                    index=offset,
                    kind=EventKind.SET_VARIABLE,
                    output_variable=variable,
                    payload=dumps(
                        obj={"value": value, "value_type": value_type},
                    ),
                ),
            ),
        )
    result, streams = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=streams.vars,
        expected={
            "label_text": "Hello",
            "number_value": 42,
            "ratio_value": 2.5,
            "name_value": "Ana",
            "flag_value": True,
            "attr_value": "attr-value",
            "row_count": 2,
            "is_yes": True,
            "as_float": 1.5,
            "as_int": 9,
            "as_json": {"a": 1},
            "as_text": "plain Hello",
        },
    )


def test_viewport_actions_resize_and_rotate(
    page: Page,
    tmp_path: Path,
) -> None:
    """Resize the viewport, then swap its orientation.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.

    """
    events: list[Event] = [
        _event(
            spec=_Spec(
                index=0,
                kind=EventKind.VIEWPORT,
                payload=dumps(
                    obj={"action": "resize", "width": 500, "height": 300},
                ),
            ),
        ),
        _event(
            spec=_Spec(
                index=1,
                kind=EventKind.VIEWPORT,
                payload=dumps(obj={"action": "rotate"}),
            ),
        ),
    ]
    result, _ = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=page.viewport_size,
        expected={"width": 300, "height": 500},
    )


def test_touch_gestures_reach_the_page(page: Page, tmp_path: Path) -> None:
    """Dispatch tap, long press, swipe and pinch to one element.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.

    """
    gestures: tuple[dict[str, object], ...] = (
        {"gesture": "tap"},
        {"gesture": "long_press", "duration_ms": 20},
        {"gesture": "swipe", "direction": "left", "distance": 40},
        {"gesture": "swipe", "direction": "down", "distance": 40},
        {"gesture": "pinch", "scale": 2},
    )
    events: list[Event] = [
        _event(
            spec=_Spec(
                index=index,
                kind=EventKind.GESTURE,
                selector="#pad",
                payload=dumps(obj=gesture),
            ),
        )
        for index, gesture in enumerate(iterable=gestures)
    ]
    result, _ = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"], expected="succeeded")
    seen: list[str] = cast(
        typ="list[str]",
        val=page.evaluate(expression="window.touches"),
    )
    expect_equal(actual="touchstart" in seen, expected=True)
    expect_equal(actual="touchmove" in seen, expected=True)
    expect_equal(actual="touchend" in seen, expected=True)


def test_rest_action_binds_validates_and_records(
    page: Page,
    tmp_path: Path,
    server: str,
) -> None:
    """Send a request with bindings and pass every response check.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.
        server: Base URL of the local server.

    """
    config: dict[str, JsonValue] = {
        "version": 1,
        "body": "",
        "headers": "X-Name: {{who}}",
        "bindings": [
            {"name": "who", "selector": "#name", "extract": "value"},
            {"name": "amount", "selector": "#number", "extract": "int"},
            {"name": "check", "selector": "#flag", "extract": "checked"},
            {
                "name": "attr",
                "selector": "#label",
                "extract": "attribute",
                "attribute": "data-x",
            },
        ],
        "validations": [
            {"kind": "status", "operator": "equals", "expected": "200"},
            {
                "kind": "header",
                "path": "x-test",
                "operator": "contains",
                "expected": "ye",
            },
            {
                "kind": "json",
                "path": "name",
                "operator": "matches",
                "expected": "^A",
            },
            {"kind": "json", "path": "id", "operator": "exists"},
            {"kind": "body", "operator": "contains", "expected": "Ana"},
        ],
    }
    events: list[Event] = [
        _event(
            spec=_Spec(
                index=0,
                kind=EventKind.HTTP_CALL,
                method="GET",
                url=f"{server}/data",
                payload=dumps(obj=config),
                output_variable="response",
            ),
        ),
    ]
    result, streams = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(actual=streams.vars["who"], expected="Ana")
    expect_equal(actual=streams.vars["amount"], expected=42)
    expect_equal(actual=streams.vars["check"], expected=True)
    expect_equal(actual=streams.vars["attr"], expected="attr-value")


def test_rest_action_fails_when_a_check_does_not_hold(
    page: Page,
    tmp_path: Path,
    server: str,
) -> None:
    """Report a failing response check as a failed action.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.
        server: Base URL of the local server.

    """
    config: dict[str, JsonValue] = {
        "version": 1,
        "validations": [
            {"kind": "status", "operator": "equals", "expected": "201"},
        ],
    }
    events: list[Event] = [
        _event(
            spec=_Spec(
                index=0,
                kind=EventKind.HTTP_CALL,
                method="GET",
                url=f"{server}/data",
                payload=dumps(obj=config),
                share_session_cookies=True,
            ),
        ),
    ]
    result, _ = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"] != "succeeded", expected=True)


def _wait(*, index: int, payload: str) -> Event:
    """Build one wait action.

    Args:
        index: Position in the flow.
        payload: Wait condition JSON, or a legacy millisecond count.

    Returns:
        The wait action as workspace JSON.

    """
    return _event(
        spec=_Spec(index=index, kind=EventKind.WAIT, payload=payload),
    )


def test_wait_actions_resolve_every_condition(
    page: Page,
    tmp_path: Path,
) -> None:
    """Wait for an element, text, a script condition and a plain delay.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.

    """
    conditions: tuple[dict[str, object], ...] = (
        {"condition": "element", "value": "#label", "timeout_ms": 500},
        {"condition": "text", "value": "Hello", "timeout_ms": 500},
        {
            "condition": "expression",
            "value": "() => document.readyState === 'complete'",
            "timeout_ms": 500,
        },
    )
    events: list[Event] = [
        _wait(index=index, payload=dumps(obj=condition))
        for index, condition in enumerate(iterable=conditions)
    ]
    events.append(_wait(index=len(events), payload="30"))
    result, _ = _run(page=page, tmp_path=tmp_path, events=events)
    expect_equal(actual=result["status"], expected="succeeded")


def test_wait_actions_fail_on_bad_conditions(
    page: Page,
    tmp_path: Path,
) -> None:
    """Fail clearly when a wait is malformed, unsupported or times out.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.

    """
    for payload in (
        "not json",
        "[1, 2]",
        dumps(obj={"condition": "weather", "value": "x"}),
        dumps(
            obj={
                "condition": "element",
                "value": "#missing",
                "timeout_ms": 50,
            },
        ),
    ):
        result, _ = _run(
            page=page,
            tmp_path=tmp_path,
            events=[_wait(index=0, payload=payload)],
        )
        expect_equal(actual=result["status"] != "succeeded", expected=True)


def test_binding_reads_through_an_extended_selector(
    page: Page,
    tmp_path: Path,
    server: str,
) -> None:
    """Resolve an extended selector binding to exact CSS before reading.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.
        server: Base URL of the local server.

    """
    config: dict[str, JsonValue] = {
        "version": 1,
        "bindings": [
            {
                "name": "second",
                "selector": "ext=sort(.row, -text)",
                "extract": "text",
            },
        ],
    }
    result, streams = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _event(
                spec=_Spec(
                    index=0,
                    kind=EventKind.HTTP_CALL,
                    method="GET",
                    url=f"{server}/data",
                    payload=dumps(obj=config),
                ),
            ),
        ],
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(actual=streams.vars["second"] in {"a", "b"}, expected=True)


def test_binding_fails_when_the_extended_selector_matches_nothing(
    page: Page,
    tmp_path: Path,
    server: str,
) -> None:
    """Fail the request when its extended selector resolves to nothing.

    Args:
        page: Page holding the fixture markup.
        tmp_path: Disposable artifact folder.
        server: Base URL of the local server.

    """
    config: dict[str, JsonValue] = {
        "version": 1,
        "bindings": [
            {
                "name": "gone",
                "selector": "ext=.nothing-here",
                "extract": "text",
            },
        ],
    }
    result, _ = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _event(
                spec=_Spec(
                    index=0,
                    kind=EventKind.HTTP_CALL,
                    method="GET",
                    url=f"{server}/data",
                    payload=dumps(obj=config),
                ),
            ),
        ],
    )
    expect_equal(actual=result["status"] != "succeeded", expected=True)


def test_flow_inputs_are_variables_from_the_first_action(
    page: Page,
    tmp_path: Path,
) -> None:
    """Start a run with a typed flow input that actions can read.

    Args:
        page: Page the actions run against.
        tmp_path: Disposable artifact folder.

    """
    variables: list[Event] = [
        cast(
            typ="Event",
            val=WorkspaceCodec.runtime_variable_to_json_value(
                variable=RuntimeVariable(
                    name="Customer",
                    value_type=ValueType.STRING,
                    value="Ana",
                ),
            ),
        ),
    ]
    result, streams = _run(
        page=page,
        tmp_path=tmp_path,
        events=[
            _event(
                spec=_Spec(
                    index=0,
                    kind=EventKind.SET_VARIABLE,
                    output_variable="Greeting",
                    payload=dumps(
                        obj={
                            "value": "Hello {{Customer}}",
                            "value_type": "text",
                        },
                    ),
                ),
            ),
        ],
        variables=variables,
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(actual=streams.vars["Greeting"], expected="Hello Ana")
