# Copyright (c) 2026 Project contributors
"""Run snippets in the isolated sandbox, alone and from the flow runner."""

from __future__ import annotations

from dataclasses import replace
from textwrap import dedent
from time import monotonic
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.sync_api import Browser, sync_playwright

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
)
from exactus.tools.record.flow_runner import FlowRunner
from exactus.tools.record.model import (
    ActionRunRecord,
    ActionRunStatus,
    EventKind,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.selector_sandbox import (
    RunStreams,
    SandboxCall,
    SandboxResult,
    merge,
    run_sandbox,
)
from exactus.tools.record.selectors import (
    RunMode,
    SelectorCodec,
    SelectorDef,
    TargetScope,
)
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
        parallel_budget_s: Grouped module constant.
        html: Grouped module constant.
        cards: Grouped module constant.

    """

    parallel_budget_s: Final[float] = 0.5
    html: Final[str] = dedent(
        text=(
            '    \n    <p class="card" id="c1">one</p><p class="card" id="c2">'
            'two</p>\n    <p class="card" id="c3">three</p>\n    <script>windo'
            "w.appState = 1;</script>\n    "
        ),
    )
    cards: Final[SelectorDef] = SelectorDef(
        selector_id="sel-cards",
        name="cards",
        expression="sort(.card, textContent)",
        expected_count=3,
    )


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a disposable page with three paragraphs.

    Yields:
        A Chromium page with a global the sandbox must not see.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        opened: Page = browser.new_page()
        opened.set_content(html=Constants.html)
        yield opened
        browser.close()


def _call(*, script: str, indices: tuple[int, ...] = (0,)) -> SandboxCall:
    """Describe a snippet run over the three cards.

    Args:
        script: Snippet source.
        indices: Targets to run on.

    Returns:
        The call.

    """
    return SandboxCall(
        script=script,
        flow_id="flow-a",
        action_id="act-1",
        run_id="run-1",
        targets=("#c1", "#c2", "#c3"),
        indices=indices,
        count=3,
    )


def _once(*, page: Page, script: str, streams: RunStreams) -> SandboxResult:
    """Run a snippet once and store its log entries.

    Args:
        page: Page with the cards.
        script: Snippet source.
        streams: Run-wide streams.

    Returns:
        The snippet's result.

    """
    result: SandboxResult = run_sandbox(
        page=page,
        call=_call(script=script),
        streams=streams,
        selectors=(Constants.cards,),
    )[0]
    merge(
        streams=streams,
        result=result,
        flow_id="flow-a",
        action_id="act-1",
        unit=None,
    )
    return result


def test_document_resolves_stored_selector_names(page: Page) -> None:
    """Let a snippet use a stored selector without stamping the page.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    result: SandboxResult = _once(
        page=page,
        script=(
            "document.querySelector('[extended-selector=\"cards\"]').textConte"
            "nt"
        ),
        streams=streams,
    )
    expect_equal(actual=result.value, expected="one")
    expect_equal(
        actual=page.evaluate(
            expression="document.querySelectorAll('[extended-selector]').length",
        ),
        expected=0,
    )
    both: SandboxResult = _once(
        page=page,
        script=(
            "window.document.querySelectorAll("
            "'sort(.card, -textContent)').length"
        ),
        streams=streams,
    )
    expect_equal(actual=both.value, expected=3)


def test_snippets_get_the_flow_context(page: Page) -> None:
    """Expose ids, targets and the current target.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    result: SandboxResult = run_sandbox(
        page=page,
        call=_call(
            script=(
                "[__EXACTUS_FLOW__.id, __EXACTUS_FLOW__.actionId, "
                "__EXACTUS_FLOW__.index, __EXACTUS_FLOW__.targets.length, "
                "__EXACTUS_FLOW__.target.id]"
            ),
            indices=(2,),
        ),
        streams=streams,
    )[0]
    expect_equal(actual=result.value, expected=["flow-a", "act-1", 2, 3, "c3"])


def test_streams_and_vars_persist_between_snippets(page: Page) -> None:
    """Keep what a snippet stored and logged for the next one.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    _ = _once(
        page=page,
        script=(
            "__EXACTUS_FLOW__.vars.seen = 7; "
            "__EXACTUS_FLOW__.log('first', {a: 1}); "
            "__EXACTUS_FLOW__.warn('careful'); "
            "__EXACTUS_FLOW__.error('boom')"
        ),
        streams=streams,
    )
    second: SandboxResult = _once(
        page=page,
        script=(
            "[__EXACTUS_FLOW__.vars.seen, __EXACTUS_FLOW__.logs.length, "
            "__EXACTUS_FLOW__.warnings[0].message, "
            "__EXACTUS_FLOW__.errors[0].message]"
        ),
        streams=streams,
    )
    expect_equal(actual=second.value, expected=[7, 1, "careful", "boom"])
    expect_equal(
        actual=[entry["level"] for entry in streams.entries],
        expected=["log", "warn", "error"],
    )
    expect_equal(
        actual=streams.entries[0]["message"],
        expected='first {"a":1}',
    )
    expect_equal(actual=streams.entries[1]["source"], expected="snippet")


def test_both_snippet_styles_work_and_errors_are_reported(page: Page) -> None:
    """Accept an expression or a function body, and surface throws.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    expect_equal(
        actual=_once(page=page, script="1 + 1", streams=streams).value,
        expected=2,
    )
    expect_equal(
        actual=_once(
            page=page,
            script="const x = 20; return x + 1;",
            streams=streams,
        ).value,
        expected=21,
    )
    thrown: SandboxResult = _once(
        page=page,
        script="__EXACTUS_FLOW__.assert(false, 'nope')",
        streams=streams,
    )
    expect_equal(actual=thrown.error, expected="nope")
    syntax: SandboxResult = _once(page=page, script="{", streams=streams)
    expect_none(value=syntax.value)
    expect_in(member="Unexpected", container=str(object=syntax.error))


def test_the_sandbox_is_separate_from_the_page(page: Page) -> None:
    """Hide page globals from snippets and snippet globals from the page.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    seen: SandboxResult = _once(
        page=page,
        script="typeof window.appState",
        streams=streams,
    )
    expect_equal(actual=seen.value, expected="undefined")
    _ = _once(
        page=page,
        script="window.leak = 1; globalThis.__EXACTUS_FLOW__.x = 1",
        streams=streams,
    )
    expect_equal(
        actual=page.evaluate(
            expression="typeof window.leak + typeof __EXACTUS_FLOW__",
        ),
        expected="undefinedundefined",
    )
    document_text: SandboxResult = _once(
        page=page,
        script="document.body.children.length > 0",
        streams=streams,
    )
    expect_true(condition=cast(typ="bool", val=document_text.value))


def test_canonical_exactus_runtime_exposes_context_and_variables(
    page: Page,
) -> None:
    """Expose frozen project, flow, page and device facts to snippets.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams(vars={"customerId": 42})
    result: SandboxResult = run_sandbox(
        page=page,
        call=SandboxCall(
            script=(
                "return {"
                "project: exactus.project.id, "
                "flow: exactus.flow.id, "
                "action: exactus.action.kind, "
                "url: exactus.page.url, "
                "width: exactus.device.viewport.width, "
                "customer: exactus.vars.get('customerId')"
                "}"
            ),
            flow_id="flow-a",
            flow_name="Checkout",
            action_id="act-1",
            action_kind="javascript",
            action_label="Read context",
            run_id="run-1",
            project_id="shop",
            project_name="Shop",
            context_id="desktop",
            context_name="Desktop",
        ),
        streams=streams,
    )[0]
    value: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=result.value,
    )
    expect_equal(actual=value["project"], expected="shop")
    expect_equal(actual=value["flow"], expected="flow-a")
    expect_equal(actual=value["action"], expected="javascript")
    expect_equal(actual=value["url"], expected="about:blank")
    expect_true(condition=cast(typ="int", val=value["width"]) > 0)
    expect_equal(actual=value["customer"], expected=42)


def test_targets_run_at_the_same_time(page: Page) -> None:
    """Overlap the waits of all targets inside one evaluation.

    Args:
        page: Page with the cards.

    """
    streams: RunStreams = RunStreams()
    started: float = monotonic()
    results: tuple[SandboxResult, ...] = run_sandbox(
        page=page,
        call=_call(
            script=(
                "await new Promise((done) => setTimeout(done, 300)); "
                "return __EXACTUS_FLOW__.target.id"
            ),
            indices=(0, 1, 2),
        ),
        streams=streams,
    )
    elapsed: float = monotonic() - started
    expect_equal(
        actual=[result.value for result in results],
        expected=["c1", "c2", "c3"],
    )
    expect_true(condition=elapsed < Constants.parallel_budget_s)


def _script_event(*, payload: str) -> TimelineEvent:
    """Build a sandboxed JavaScript action over the stored cards selector.

    Args:
        payload: Snippet source.

    Returns:
        An action targeting every card.

    """
    return TimelineEvent(
        event_id="js",
        flow_id="flow-a",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.JAVASCRIPT,
        label="Script",
        selector_id="sel-cards",
        targets=TargetScope.ALL,
        sandbox=True,
        payload=payload,
    )


def _run(*, page: Page, tmp_path: Path, event: TimelineEvent) -> list[Event]:
    """Run one action through the flow runner.

    Args:
        page: Page with the cards.
        tmp_path: Evidence directory.
        event: The action.

    Returns:
        Its action records.

    """
    result: Event = FlowRunner(output=tmp_path, timeout_ms=800).run(
        page=page,
        message={
            "flow_id": "flow-a",
            "events": [WorkspaceCodec.event_to_json_value(event=event)],
            "selectors": [
                SelectorCodec.selector_to_json(item=Constants.cards),
            ],
        },
    )
    return cast(typ="list[Event]", val=result["action_records"])


def test_sequential_targets_each_run_the_snippet(
    page: Page,
    tmp_path: Path,
) -> None:
    """Run the snippet once per card, in order, with its own log entries.

    Args:
        page: Page with the cards.
        tmp_path: Evidence directory.

    """
    records: list[Event] = _run(
        page=page,
        tmp_path=tmp_path,
        event=_script_event(
            payload=(
                "__EXACTUS_FLOW__.log(__EXACTUS_FLOW__.target.id); "
                "__EXACTUS_FLOW__.target.dataset.seen = '1'; "
                "return __EXACTUS_FLOW__.index"
            ),
        ),
    )
    expect_equal(
        actual=[record["response"] for record in records],
        expected=[0, 1, 2],
    )
    expect_equal(
        actual=[
            dig(document=record, path=("streams", 0, "message"))
            for record in records
        ],
        expected=["c1", "c3", "c2"],
    )
    expect_equal(
        actual=page.evaluate(
            expression="document.querySelectorAll('[data-seen]').length",
        ),
        expected=3,
    )


def test_parallel_targets_run_together_and_report_each(
    page: Page,
    tmp_path: Path,
) -> None:
    """Overlap the targets but still record one result per target.

    Args:
        page: Page with the cards.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _script_event(
            payload=(
                "await new Promise((done) => setTimeout(done, 300)); "
                "return __EXACTUS_FLOW__.target.id"
            ),
        ),
        run_mode=RunMode.PARALLEL,
    )
    started: float = monotonic()
    records: list[Event] = _run(page=page, tmp_path=tmp_path, event=event)
    expect_true(
        condition=monotonic() - started < Constants.parallel_budget_s + 1,
    )
    expect_equal(
        actual=[record["response"] for record in records],
        expected=["c1", "c3", "c2"],
    )
    expect_equal(
        actual=[
            dig(document=record, path=("unit", "index")) for record in records
        ],
        expected=[0, 1, 2],
    )


def test_a_throwing_snippet_fails_with_a_cause_and_an_error_entry(
    page: Page,
    tmp_path: Path,
) -> None:
    """Record the failure in both the cause and the error stream.

    Args:
        page: Page with the cards.
        tmp_path: Evidence directory.

    """
    event: TimelineEvent = replace(
        _script_event(payload="__EXACTUS_FLOW__.assert(false, 'bad card')"),
        targets=TargetScope.FIRST,
    )
    records: list[Event] = _run(page=page, tmp_path=tmp_path, event=event)
    expect_equal(actual=records[0]["status"], expected="failed")
    expect_equal(
        actual=dig(document=records[0], path=("cause", "message")),
        expected="bad card",
    )
    streams: list[object] = dig_list(document=records[0], path=("streams",))
    expect_equal(
        actual=dig(document=streams[0], path=("source",)),
        expected="tool",
    )
    expect_equal(
        actual=dig(document=streams[0], path=("level",)),
        expected="error",
    )
    expect_in(
        member="bad card",
        container=str(object=dig(document=streams[0], path=("message",))),
    )
    expect_false(condition=records[0]["status"] == "succeeded")


def test_streams_are_persisted_on_the_record() -> None:
    """Round-trip streams through the record codec."""
    record: ActionRunRecord = ActionRunRecord(
        event_id="e",
        flow_id="f",
        status=ActionRunStatus.SUCCEEDED,
        attempt=1,
        started_ms=0,
        finished_ms=1,
        response_json="null",
        streams_json='[{"level": "log", "message": "hi"}]',
    )
    value: JsonValue = WorkspaceCodec.action_record_to_json_value(
        record=record,
    )
    expect_equal(
        actual=WorkspaceCodec.action_record_from_json_value(value=value),
        expected=record,
    )
