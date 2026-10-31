# Copyright (c) 2026 Project contributors
"""Real-browser coverage of Studio functional tests and screenshot evidence."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from json import dumps
from pathlib import Path
from runpy import run_path
from sys import modules
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest
from defusedxml.ElementTree import parse
from playwright.sync_api import Browser, BrowserContext, sync_playwright

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    ActionContract,
    AssertionKind,
    AssertionOperator,
    AssertionSpec,
    EventKind,
    Flow,
    NetworkExpectation,
    OutputBinding,
    OutputSource,
    TimelineEvent,
    TimelineLayer,
    ValueType,
)
from exactus.tools.record.recorder_protocol import RecorderProtocol
from exactus.tools.record.run import BrowserOptions, main, run_workspace
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.workspace_actions import (
    Event,
    actions_to_events,
    build_flow,
    build_workspace,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from xml.etree.ElementTree import Element, ElementTree

    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue


@pytest.fixture
def page() -> Iterator[Page]:
    """Create an isolated real Chromium page for each behavioral test.

    Yields:
        A fresh page from a disposable browser context.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        context: BrowserContext = browser.new_context(
            viewport={"width": 640, "height": 480},
        )
        yield context.new_page()
        browser.close()


def _target(*, selector: str) -> dict[str, JsonValue]:
    """Return a CSS selector target payload.

    Args:
        selector: Selector for this operation.

    Returns:
        CSS locator target payload.

    """
    return {"locators": [{"kind": "css", "value": selector}]}


def _events() -> list[Event]:
    """Build an ordered program preserving selection and checkbox semantics.

    Returns:
        Action events derived from the test form.

    """
    return actions_to_events(
        actions=cast(
            typ="list[dict[str, JsonValue]]",
            val=[
                {"type": "check", "target": _target(selector="#check")},
                {"type": "check", "target": _target(selector="#check")},
                {
                    "type": "select",
                    "target": _target(selector="#choice"),
                    "values": ["a,b", "c"],
                },
                {"type": "click", "target": _target(selector="#go")},
            ],
        ),
        flow_id="test",
    )


def _contract(*, expected: str, retry_count: int = 0) -> Event:
    """Serialize a contract through the canonical codec.

    Args:
        expected: Text the assertion expects to find.
        retry_count: Times to retry a failing assertion.

    Returns:
        The last event with an attached assertion contract.

    """
    event: TimelineEvent = (
        WorkspaceCodec.from_json_value(
            value=build_workspace(
                flows=[
                    build_flow(flow_id="test", name="Test", events=_events()),
                ],
            ),
        )
        .flows[0]
        .events[-1]
    )
    contract: ActionContract = ActionContract(
        postconditions=(
            AssertionSpec(
                assertion_id="check-result",
                label="Result text",
                kind=AssertionKind.DOM_TEXT,
                operator=AssertionOperator.CONTAINS,
                target="#result",
                expected=expected,
                timeout_ms=150,
            ),
        ),
        retry_count=retry_count,
    )
    return cast(
        typ="Event",
        val=WorkspaceCodec.event_to_json_value(
            event=event.with_contract(contract=contract),
        ),
    )


def test_semantic_replay_and_durable_evidence(
    page: Page,
    tmp_path: Path,
) -> None:
    """Checks stay idempotent; option values and evidence survive replay.

    Args:
        page: Browser page for replay and assertions.
        tmp_path: Isolated test filesystem.

    """
    html: str = (
        '<input id="check" type="checkbox">'
        '<select id="choice" multiple>'
        '<option value="a,b">AB</option>'
        '<option value="c">C</option>'
        "</select>"
        '<button id="go" onclick="'
        "setTimeout("
        "() => document.querySelector('#result').textContent='Ready', 40"
        ")"
        '">Go</button>'
        '<p id="result"></p>'
    )
    page.set_content(html=html)
    events: list[Event] = _events()
    events[-1] = _contract(expected="Ready")
    evidence: list[Event] = []
    runner: FlowRunner = FlowRunner(output=tmp_path, emit=evidence.append)
    result: Event = runner.run(
        page=page,
        message=cast(
            typ="Event",
            val={
                "flow_id": "test",
                "events": cast(typ="JsonValue", val=events),
                "capture_images": True,
            },
        ),
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_true(condition=page.locator(selector="#check").is_checked())
    expect_equal(
        actual=page.locator(selector="#choice").evaluate(
            expression=(
                "node => Array.from(node.selectedOptions, x => x.value)"
            ),
        ),
        expected=["a,b", "c"],
    )
    shots: list[Event] = [
        item for item in evidence if item["type"] == "screenshot"
    ]
    expect_equal(actual=len(shots), expected=4)
    for item in evidence:
        RecorderProtocol.decode_message(line=dumps(obj=item).encode())
    for shot in shots:
        data: bytes = Path(str(object=shot["path"])).read_bytes()
        expect_equal(
            actual=sha256(data=data).hexdigest(),
            expected=shot["sha256"],
        )
    repeat: Event = runner.run(
        page=page,
        message=cast(
            typ="Event",
            val={
                "flow_id": "test",
                "events": cast(typ="JsonValue", val=events),
                "capture_images": True,
            },
        ),
    )
    expect_equal(actual=repeat["status"], expected="succeeded")
    paths: list[JsonValue] = [
        item["path"] for item in evidence if item["type"] == "screenshot"
    ]
    expect_equal(actual=len(set(paths)), expected=len(paths))


def test_failed_contract_retries_then_skips_and_captures(
    page: Page,
    tmp_path: Path,
) -> None:
    """A failed assertion retries, captures images and blocks later actions.

    Args:
        page: Browser page for replay and assertions.
        tmp_path: Isolated test filesystem.

    """
    page.set_content(
        html='<button id="go">Go</button><p id="result">Wrong</p>',
    )
    event: Event = _contract(expected="Ready", retry_count=1)
    events: list[Event] = [event, {**event, "id": "later", "sequence": 5}]
    evidence: list[Event] = []
    result: Event = FlowRunner(output=tmp_path, emit=evidence.append).run(
        page=page,
        message=cast(
            typ="Event",
            val={
                "flow_id": "test",
                "capture_images": True,
                "events": cast(typ="JsonValue", val=events),
            },
        ),
    )
    expect_equal(actual=result["status"], expected="failed")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["failed", "failed", "skipped"],
    )
    expect_equal(
        actual=len(
            [item for item in evidence if item["type"] == "screenshot"],
        ),
        expected=2,
    )


def test_navigation_and_ci_reports(tmp_path: Path) -> None:
    """A workspace navigates, verifies the page, and writes CI evidence.

    Args:
        tmp_path: Isolated test filesystem.

    """
    html: Path = tmp_path / "page.html"
    html.write_text(
        data="<title>Recorded page</title>"
        '<button id="go">Go</button>'
        '<p id="result">Ready</p>',
    )
    navigation: Event = actions_to_events(
        actions=cast(
            typ="list[dict[str, JsonValue]]",
            val=[{"type": "navigation", "url": html.as_uri()}],
        ),
        flow_id="test",
    )[0]
    check: Event = _contract(expected="Ready")
    flow: Event = build_flow(
        flow_id="test",
        name="Test",
        events=[navigation, check],
    )
    flow.update(parameters=[], outputs=[])
    review_check: Event = dict(check)
    review_check["id"] = "review-check"
    review_check["flow_id"] = "review"
    review: Event = build_flow(
        flow_id="review",
        name="Review",
        events=[review_check],
    )
    review.update(parameters=[], outputs=[])
    document: Event = build_workspace(flows=[flow, review])
    document["edges"] = [
        {
            "source": "test",
            "target": "review",
            "mode": "always",
            "condition_expression": None,
            "priority": 0,
            "max_traversals": 1,
        },
    ]
    document.update(
        version=3,
        variables=[],
        checkpoint_definitions=[],
        checkpoint_artifacts=[],
        runs=[],
    )
    navigation["contract"] = {
        "preconditions": [],
        "postconditions": [],
        "outputs": [],
        "retry_count": 0,
        "retry_delay_ms": 0,
        "continue_on_failure": False,
    }
    path: Path = tmp_path / "test.pwflow.json"
    path.write_text(data=dumps(obj=document))
    report: Event = run_workspace(
        path=path,
        output=tmp_path / "out",
        browser=BrowserOptions(screenshots=True),
    )
    expect_equal(actual=report["status"], expected="succeeded")
    results: JsonValue = report["flows"]
    expect_true(condition=isinstance(results, list) and len(results) == 1)
    if isinstance(results, list) and isinstance(results[0], dict):
        records: JsonValue = results[0]["action_records"]
        transitions: JsonValue = results[0]["transitions"]
        expect_true(condition=isinstance(records, list))
        expect_true(condition=isinstance(transitions, list))
        if isinstance(records, list) and isinstance(transitions, list):
            expect_equal(actual=len(records), expected=3)
            expect_equal(actual=len(transitions), expected=1)
    tree: ElementTree[Element[str] | None] = parse(
        source=tmp_path / "out/junit.xml",
    )
    root: Element[str] | None = tree.getroot()
    expect_true(condition=root is not None)
    if root is None:
        return
    expect_equal(actual=root.get(key="failures"), expected="0")
    expect_true(condition=(tmp_path / "out/result.json").is_file())


def test_empty_test_is_rejected(page: Page, tmp_path: Path) -> None:
    """An empty flow cannot masquerade as a passed functional test.

    Args:
        page: Browser page for replay and assertions.
        tmp_path: Isolated test filesystem.

    """
    with pytest.raises(
        expected_exception=ValueError,
        match="at least one step",
    ):
        FlowRunner(output=tmp_path).run(
            page=page,
            message=cast(typ="Event", val={"events": []}),
        )


def test_ui_response_expectations_and_explicit_screenshot(
    page: Page,
    tmp_path: Path,
) -> None:
    """Observe a UI-caused response and capture an authored checkpoint.

    Args:
        page: Browser page for replay and assertions.
        tmp_path: Isolated test filesystem.

    """
    page.route(
        url="https://studio.test/**",
        handler=lambda route: route.fulfill(
            status=200,
            body='{"saved":true}',
            content_type="application/json",
            headers={"access-control-allow-origin": "*"},
        ),
    )
    page.set_content(
        html=(
            '<button id="go" onclick="fetch(\'https://studio.test'
            "/api')\">Save</button>"
        ),
    )
    flow: Flow = WorkspaceCodec.from_json_value(
        value=build_workspace(
            flows=[build_flow(flow_id="test", name="Test", events=_events())],
        ),
    ).flows[0]
    event: TimelineEvent = flow.events[-1].with_expectations(
        expectations=(
            NetworkExpectation(
                expectation_id="saved",
                label="Save returned 200",
                method="GET",
                url_pattern="https://studio.test/api",
                expected_status=200,
                timeout_ms=200,
            ),
        ),
    )
    checkpoint: TimelineEvent = TimelineEvent(
        event_id="image",
        flow_id="test",
        sequence=5,
        elapsed_ms=0,
        layer=TimelineLayer.TIMING,
        kind=EventKind.NOTE,
        label="Capture saved state",
        payload="__screenshot__",
    )
    evidence: list[Event] = []
    result: Event = FlowRunner(output=tmp_path, emit=evidence.append).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                WorkspaceCodec.event_to_json_value(event=event),
                WorkspaceCodec.event_to_json_value(event=checkpoint),
            ],
        },
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(
        actual=len(
            [item for item in evidence if item["type"] == "screenshot"],
        ),
        expected=1,
    )
    expect_true(
        condition=any(
            item["type"] == "expectation_result" and item["outcome"] == "pass"
            for item in evidence
        ),
    )


def test_browser_state_assertions(page: Page, tmp_path: Path) -> None:
    """Verify DOM, storage, cookies, URL, title and JavaScript contracts.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    page.route(
        url="https://studio.test/**",
        handler=lambda route: route.fulfill(
            body=(
                "<title>Saved</title>"
                '<p id="result" data-state="ready">Saved</p>'
            ),
            content_type="text/html",
        ),
    )
    page.goto(url="https://studio.test/state")
    page.evaluate(
        expression="localStorage.setItem('draft','Saved'); "
        "sessionStorage.setItem('draft','Saved'); "
        "document.cookie='draft=Saved'",
    )
    specs: tuple[AssertionSpec, ...] = (
        AssertionSpec(
            assertion_id="url",
            label="url",
            kind=AssertionKind.URL,
            expected="/state",
            operator=AssertionOperator.CONTAINS,
        ),
        AssertionSpec(
            assertion_id="title",
            label="title",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.TITLE,
            expected="Saved",
        ),
        AssertionSpec(
            assertion_id="local",
            label="local",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.LOCAL_STORAGE,
            target="draft",
            expected="Saved",
        ),
        AssertionSpec(
            assertion_id="session",
            label="session",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.SESSION_STORAGE,
            target="draft",
            expected="Saved",
        ),
        AssertionSpec(
            assertion_id="cookie",
            label="cookie",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.COOKIE,
            target="draft",
            expected="Saved",
        ),
        AssertionSpec(
            assertion_id="js",
            label="js",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.JAVASCRIPT,
            target="document.title",
            expected="Saved",
        ),
        AssertionSpec(
            assertion_id="count",
            label="count",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.DOM_COUNT,
            target="#result",
            expected="1",
        ),
        AssertionSpec(
            assertion_id="visible",
            label="visible",
            kind=AssertionKind.DOM_VISIBLE,
            target="#result",
            operator=AssertionOperator.EXISTS,
        ),
        AssertionSpec(
            assertion_id="hidden",
            label="hidden",
            kind=AssertionKind.DOM_HIDDEN,
            target="#missing",
            operator=AssertionOperator.EXISTS,
        ),
        AssertionSpec(
            assertion_id="attribute",
            label="attribute",
            operator=AssertionOperator.EQUALS,
            kind=AssertionKind.DOM_ATTRIBUTE,
            target="#result",
            attribute="data-state",
            expected="ready",
        ),
    )
    event: TimelineEvent = TimelineEvent(
        event_id="state",
        flow_id="test",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.TIMING,
        kind=EventKind.NOTE,
        label="Check state",
        contract=ActionContract(postconditions=specs),
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [WorkspaceCodec.event_to_json_value(event=event)],
        },
    )
    expect_equal(actual=result["status"], expected="succeeded")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=len(cast(typ="list[JsonValue]", val=records[0]["assertions"])),
        expected=len(specs),
    )


@pytest.mark.parametrize(
    "feature",
    ["outputs", "restore_checkpoint_artifact_id"],
)
def test_unsupported_flow_configuration_is_rejected(
    page: Page,
    tmp_path: Path,
    feature: str,
) -> None:
    """Reject unsupported configuration instead of reporting a false pass.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.
        feature: Unsupported authored flow capability.

    """
    with pytest.raises(expected_exception=ValueError, match="not supported"):
        FlowRunner(output=tmp_path).run(
            page=page,
            message={
                "events": cast(typ="JsonValue", val=_events()),
                feature: "requested",
            },
        )


def test_failed_workspace_writes_junit_and_selection_error(
    tmp_path: Path,
) -> None:
    """Publish failed-flow evidence and reject missing flow selections.

    Args:
        tmp_path: Workspace and output directory.

    """
    path: Path = tmp_path / "empty.pwflow.json"
    path.write_text(
        data=dumps(
            obj=build_workspace(
                flows=[build_flow(flow_id="empty", name="Empty", events=[])],
            ),
        ),
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=ValueError, match="not found"):
        run_workspace(path=path, output=tmp_path / "missing", flow_id="absent")
    report: Event = run_workspace(
        path=path,
        output=tmp_path / "failed",
        url="about:blank",
    )
    expect_equal(actual=report["status"], expected="failed")
    tree: ElementTree[Element[str] | None] = parse(
        source=tmp_path / "failed/junit.xml",
    )
    root: Element[str] | None = tree.getroot()
    expect_true(condition=root is not None)
    if root is not None:
        expect_equal(actual=root.get(key="failures"), expected="1")
        expect_true(condition=root.find(path="testcase/failure") is not None)


def test_cancelled_flows_keep_state_distinct_in_json_and_junit(
    tmp_path: Path,
) -> None:
    """Cancellation reports ``cancelled`` per flow, never ``failed``.

    Args:
        tmp_path: Workspace and output directory.

    """
    path: Path = tmp_path / "two.pwflow.json"

    def note(*, flow_id: str) -> Event:
        """Return one decodable event for ``flow_id``.

        Args:
            flow_id: Owning Flow identifier.

        Returns:
            Serialized Timeline event.

        """
        return cast(
            typ="Event",
            val=WorkspaceCodec.event_to_json_value(
                event=TimelineEvent(
                    event_id=f"{flow_id}-note",
                    flow_id=flow_id,
                    sequence=0,
                    elapsed_ms=0,
                    layer=TimelineLayer.TIMING,
                    kind=EventKind.NOTE,
                    label="Note",
                    contract=ActionContract(),
                ),
            ),
        )

    path.write_text(
        data=dumps(
            obj=build_workspace(
                flows=[
                    build_flow(
                        flow_id="one",
                        name="One",
                        events=[note(flow_id="one")],
                    ),
                    build_flow(
                        flow_id="two",
                        name="Two",
                        events=[note(flow_id="two")],
                    ),
                ],
            ),
        ),
        encoding="utf-8",
    )
    report: Event = run_workspace(
        path=path,
        output=tmp_path / "cancelled",
        url="about:blank",
        browser=BrowserOptions(cancelled=lambda: True),
    )
    expect_equal(actual=report["status"], expected="cancelled")
    flows: list[Event] = cast(typ="list[Event]", val=report["flows"])
    expect_equal(
        actual=[flow["status"] for flow in flows],
        expected=["cancelled", "cancelled"],
    )
    tree: ElementTree[Element[str] | None] = parse(
        source=tmp_path / "cancelled/junit.xml",
    )
    root: Element[str] | None = tree.getroot()
    expect_true(condition=root is not None)
    if root is not None:
        expect_equal(actual=root.get(key="failures"), expected="0")
        cases: list[Element[str]] = root.findall(path="testcase")
        expect_equal(actual=len(cases), expected=2)
        for case in cases:
            expect_true(condition=case.find(path="skipped") is not None)
            expect_true(condition=case.find(path="failure") is None)


def test_flow_cli_reports_failure_and_rejects_invalid_viewport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return CI failure status and validate viewport CLI arguments.

    Args:
        tmp_path: Workspace and output directory.
        monkeypatch: CLI argument overrides.

    """
    path: Path = tmp_path / "empty.pwflow.json"
    path.write_text(
        data=dumps(
            obj=build_workspace(
                flows=[build_flow(flow_id="empty", name="Empty", events=[])],
            ),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "flow-run",
            str(object=path),
            "--flow",
            "empty",
            "--output",
            str(object=tmp_path / "cli"),
            "--width",
            "640",
            "--height",
            "480",
            "--url",
            "about:blank",
            "--screenshots",
        ],
    )
    expect_equal(actual=main(), expected=1)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["flow-run", str(object=path), "--width", "0"],
    )
    with pytest.raises(expected_exception=SystemExit) as failure:
        main()
    expect_equal(actual=failure.value.code, expected=2)


def _note(
    *,
    event_id: str,
    sequence: int = 1,
    contract: ActionContract | None = None,
    payload: str = "",
) -> Event:
    """Serialize one no-op NOTE step through the canonical codec.

    Args:
        event_id: Step identifier.
        sequence: Replay position.
        contract: Optional contract attached to the step.
        payload: Optional payload, such as ``__screenshot__``.

    Returns:
        Serialized Flow event.

    """
    event: TimelineEvent = TimelineEvent(
        event_id=event_id,
        flow_id="test",
        sequence=sequence,
        elapsed_ms=0,
        layer=TimelineLayer.TIMING,
        kind=EventKind.NOTE,
        label="Note",
        payload=payload,
    )
    if contract is not None:
        event = event.with_contract(contract=contract)
    return cast(
        typ="Event",
        val=WorkspaceCodec.event_to_json_value(event=event),
    )


def test_console_and_invalid_selector_assertions_fail(
    page: Page,
    tmp_path: Path,
) -> None:
    """Unsupported and broken assertions fail instead of crashing the run.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    page.set_content(html="<p>ok</p>")
    console: Event = _note(
        event_id="console",
        contract=ActionContract(
            postconditions=(
                AssertionSpec(
                    assertion_id="console",
                    label="console",
                    kind=AssertionKind.CONSOLE,
                    operator=AssertionOperator.EXISTS,
                ),
            ),
        ),
    )
    broken: Event = _note(
        event_id="broken",
        sequence=2,
        contract=ActionContract(
            postconditions=(
                AssertionSpec(
                    assertion_id="broken",
                    label="broken",
                    kind=AssertionKind.DOM_VISIBLE,
                    operator=AssertionOperator.EXISTS,
                    target="div >>",
                    timeout_ms=120,
                ),
            ),
        ),
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={"flow_id": "test", "events": [console, broken]},
    )
    expect_equal(actual=result["status"], expected="failed")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["failed", "skipped"],
    )
    expect_true(condition="not supported" in str(object=records[0]["error"]))


def test_output_bindings_and_unsupported_steps_fail(
    page: Page,
    tmp_path: Path,
) -> None:
    """Output bindings are skipped; non-action steps report failures.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    bound: Event = _note(
        event_id="bound",
        contract=ActionContract(
            continue_on_failure=True,
            outputs=(
                OutputBinding(
                    name="saved",
                    value_type=ValueType.STRING,
                    source=OutputSource.JAVASCRIPT,
                    expression="document.title",
                ),
            ),
        ),
    )
    unsupported: TimelineEvent = TimelineEvent(
        event_id="unsupported",
        flow_id="test",
        sequence=2,
        elapsed_ms=0,
        layer=TimelineLayer.TIMING,
        kind=EventKind.URL_CHANGE,
        label="Observed URL change",
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                bound,
                WorkspaceCodec.event_to_json_value(event=unsupported),
            ],
        },
    )
    expect_equal(actual=result["status"], expected="failed")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(actual=records[0]["status"], expected="succeeded")
    expect_equal(actual=records[0]["outputs"], expected=[])
    expect_true(
        condition="Unsupported executable step"
        in str(object=records[1]["error"]),
    )


def test_http_call_actions_share_or_isolate_cookies(
    page: Page,
    demo_url: str,
    tmp_path: Path,
) -> None:
    """HTTP steps replay against shared or fresh request contexts.

    Args:
        page: Isolated real browser page.
        demo_url: Served demo site base URL.
        tmp_path: Evidence directory.

    """
    shared: TimelineEvent = TimelineEvent(
        event_id="shared",
        flow_id="test",
        sequence=1,
        elapsed_ms=0,
        layer=TimelineLayer.NETWORK,
        kind=EventKind.HTTP_CALL,
        label="Shared request",
        url=demo_url,
        method="GET",
        share_session_cookies=True,
    )
    isolated: TimelineEvent = replace(
        shared,
        event_id="isolated",
        sequence=2,
        share_session_cookies=False,
    )
    mismatch: TimelineEvent = replace(
        shared,
        event_id="mismatch",
        sequence=3,
    ).with_contract(contract=ActionContract(continue_on_failure=True))
    mismatch = mismatch.with_expectations(
        expectations=(
            NetworkExpectation(
                expectation_id="status",
                label="Status is 999",
                expected_status=999,
                timeout_ms=100,
            ),
        ),
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                WorkspaceCodec.event_to_json_value(event=shared),
                WorkspaceCodec.event_to_json_value(event=mismatch),
                WorkspaceCodec.event_to_json_value(event=isolated),
            ],
        },
    )
    expect_equal(actual=result["status"], expected="failed")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_equal(
        actual=[record["status"] for record in records],
        expected=["succeeded", "warning", "succeeded"],
    )


def test_http_response_capture_feeds_the_next_request(
    page: Page,
    demo_url: str,
    tmp_path: Path,
) -> None:
    """Publish a typed response value before the next action is expanded.

    Args:
        page: Isolated real browser page.
        demo_url: Served demo site base URL.
        tmp_path: Evidence directory.

    """
    capture: TimelineEvent = TimelineEvent(
        event_id="capture-status",
        flow_id="test",
        sequence=1,
        elapsed_ms=0,
        layer=TimelineLayer.NETWORK,
        kind=EventKind.HTTP_CALL,
        label="Capture status",
        url=demo_url,
        method="GET",
        payload=dumps(
            obj={
                "version": 2,
                "captures": [
                    {
                        "source": "status",
                        "name": "Response Status",
                        "value_type": "integer",
                        "required": True,
                    },
                ],
            },
        ),
    )
    consume: TimelineEvent = replace(
        capture,
        event_id="consume-status",
        sequence=2,
        label="Use status",
        payload=dumps(
            obj={
                "version": 2,
                "query": [
                    {
                        "enabled": True,
                        "key": "captured",
                        "value": "{{Response Status}}",
                    },
                ],
            },
        ),
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                WorkspaceCodec.event_to_json_value(event=capture),
                WorkspaceCodec.event_to_json_value(event=consume),
            ],
        },
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    response: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=records[1]["response"],
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_true(
        condition=str(object=response["url"]).endswith("?captured=200"),
    )


def test_websocket_response_capture_feeds_the_next_action(
    page: Page,
    tmp_path: Path,
) -> None:
    """Collect socket frames and expose selected JSON as a typed variable.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    page.set_content(
        html=(
            dedent(
                text=(
                    "    <script>\n    class ExactusFakeSocket extends Eve"
                    "ntTarget {\n      constructor(url, protocols) {\n    "
                    "    super();\n        this.url = url;\n        this.p"
                    "rotocol = Array.isArray(protocols) ? protocols[0] ?? "
                    '"" : "";\n        queueMicrotask(() => this.dispatchE'
                    'vent(new Event("open")));\n      }\n      send(messag'
                    "e) {\n        this.sent = message;\n        queueMicr"
                    'otask(() => this.dispatchEvent(new MessageEvent("mess'
                    'age", {\n          data: JSON.stringify({payload: {to'
                    "tal: 12.5}})\n        })));\n      }\n      close(cod"
                    "e, reason) {\n        queueMicrotask(() => this.dispa"
                    'tchEvent(\n          new CloseEvent("close", {code, r'
                    "eason})\n        ));\n      }\n    }\n    window.WebS"
                    "ocket = ExactusFakeSocket;\n    </script>"
                ),
            )
        ),
    )
    socket: TimelineEvent = TimelineEvent(
        event_id="socket",
        flow_id="test",
        sequence=1,
        elapsed_ms=0,
        layer=TimelineLayer.WEBSOCKET,
        kind=EventKind.WEBSOCKET_CALL,
        label="Read live total",
        url="wss://stream.example.test/live",
        payload=dumps(
            obj={
                "version": 2,
                "protocols": ["updates.v1"],
                "message": '{"type":"subscribe"}',
                "receive_count": 1,
                "timeout_ms": 1000,
                "captures": [
                    {
                        "source": "message_json",
                        "path": "payload.total",
                        "name": "Live Total",
                        "value_type": "float",
                        "required": True,
                    },
                ],
            },
        ),
    )
    consume: TimelineEvent = TimelineEvent(
        event_id="consume",
        flow_id="test",
        sequence=2,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.SET_VARIABLE,
        label="Copy live total",
        payload=dumps(obj={"value": "{{Live Total}}", "value_type": "float"}),
        output_variable="Copied Total",
    )
    result: Event = FlowRunner(output=tmp_path).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [
                WorkspaceCodec.event_to_json_value(event=socket),
                WorkspaceCodec.event_to_json_value(event=consume),
            ],
        },
    )
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    socket_response: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=records[0]["response"],
    )
    expect_equal(actual=result["status"], expected="succeeded")
    expect_equal(actual=socket_response["protocol"], expected="updates.v1")
    expect_equal(actual=records[1]["response"], expected=12.5)


def test_network_expectation_timeout_is_reported(
    page: Page,
    tmp_path: Path,
) -> None:
    """A UI action whose response never matches reports a timeout.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    page.route(
        url="https://studio.test/**",
        handler=lambda route: route.fulfill(
            status=200,
            body="{}",
            content_type="application/json",
            headers={"access-control-allow-origin": "*"},
        ),
    )
    page.set_content(
        html='<button id="go" '
        "onclick=\"fetch('https://studio.test/api')\">Save</button>",
    )
    flow: Flow = WorkspaceCodec.from_json_value(
        value=build_workspace(
            flows=[build_flow(flow_id="test", name="Test", events=_events())],
        ),
    ).flows[0]
    click: TimelineEvent = flow.events[-1].with_expectations(
        expectations=(
            NetworkExpectation(
                expectation_id="saved",
                label="Save returned 999",
                method="GET",
                url_pattern="https://studio.test/api",
                expected_status=999,
                timeout_ms=150,
            ),
        ),
    )
    evidence: list[Event] = []
    result: Event = FlowRunner(output=tmp_path, emit=evidence.append).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [WorkspaceCodec.event_to_json_value(event=click)],
        },
    )
    expect_equal(actual=result["status"], expected="failed")
    expect_true(
        condition=any(
            item["type"] == "expectation_result"
            and item["outcome"] == "timeout"
            for item in evidence
        ),
    )


def test_screenshot_capture_failures_mark_the_step(
    page: Page,
    tmp_path: Path,
) -> None:
    """Artifact directories that cannot be created fail the step.

    Args:
        page: Isolated real browser page.
        tmp_path: Evidence directory.

    """
    page.set_content(html="<p>ok</p>")
    blocked: Path = tmp_path / "blocked"
    blocked.write_text(data="not a directory", encoding="utf-8")
    result: Event = FlowRunner(output=blocked).run(
        page=page,
        message={
            "flow_id": "test",
            "events": [_note(event_id="shot", payload="__screenshot__")],
        },
    )
    expect_equal(actual=result["status"], expected="failed")
    records: list[Event] = cast(
        typ="list[Event]",
        val=result["action_records"],
    )
    expect_true(condition="Screenshot:" in str(object=records[0]["error"]))


def test_module_entrypoint_runs_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the CLI module with real failed-flow evidence.

    Args:
        tmp_path: Workspace and output directory.
        monkeypatch: Command-line arguments for the fresh module.

    """
    path: Path = tmp_path / "empty.pwflow.json"
    path.write_text(
        data=dumps(
            obj=build_workspace(
                flows=[build_flow(flow_id="empty", name="Empty", events=[])],
            ),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "flow-run",
            str(object=path),
            "--output",
            str(object=tmp_path / "out"),
        ],
    )
    with pytest.raises(expected_exception=SystemExit) as finished:
        run_path(
            path_name=str(
                object=Path(__file__).resolve().parents[4]
                / "exactus/tools/record/run.py",
            ),
            run_name="__main__",
        )
    expect_equal(actual=finished.value.code, expected=1)
    expect_true(condition=(tmp_path / "out/junit.xml").is_file())
