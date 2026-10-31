# Copyright (c) 2026
"""Browser diagnostics retain real script locations and function stacks."""

from __future__ import annotations

from asyncio import run
from http import HTTPStatus
from textwrap import dedent
from typing import Final, final

from playwright import async_api, sync_api

from exactus.tests.common.support import expect_equal, expect_in, expect_true
from exactus.tools.record.diagnostics import (
    DiagnosticCollector,
    DiagnosticEvent,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        script: Grouped module constant.
        page: Grouped module constant.

    """

    script: Final[str] = dedent(
        text=(
            '    function reportProblem() {\n      console.error("console fail'
            'ure");\n    }\n    function throwProblem() {\n      throw new Err'
            'or("uncaught failure");\n    }\n    reportProblem();\n    setTime'
            "out(throwProblem, 0);\n    "
        ),
    )
    page: Final[str] = (
        '<script src="http://diagnostics.test/app.js"></script><img'
        ' src="http://diagnostics.test/missing.png">'
    )


def _verify(*, events: tuple[DiagnosticEvent, ...]) -> None:
    """Require exact source attribution without duplicate console events.

    Args:
        events: Events observed by the actual browser.

    """
    console: list[DiagnosticEvent] = [
        event for event in events if event.message == "console failure"
    ]
    expect_equal(actual=len(console), expected=1)
    expect_equal(
        actual=console[0].file,
        expected="http://diagnostics.test/app.js",
    )
    expect_equal(actual=console[0].line, expected=2)
    expect_equal(actual=console[0].function, expected="reportProblem")
    expect_in(member="reportProblem", container=console[0].stack)
    exceptions: list[DiagnosticEvent] = [
        event for event in events if event.category == "pageerror"
    ]
    expect_equal(actual=len(exceptions), expected=1)
    expect_equal(actual=exceptions[0].line, expected=5)
    expect_equal(actual=exceptions[0].function, expected="throwProblem")
    expect_true(
        condition=any(
            event.category == "http" and event.status == HTTPStatus.NOT_FOUND
            for event in events
        ),
    )
    expect_true(
        condition=any(
            event.category == "console" and "Failed to load" in event.message
            for event in events
        ),
    )


def test_sync_console_and_exception_sources() -> None:
    """Capture source frames, native resource errors and exceptions."""
    with sync_api.sync_playwright() as playwright:
        browser: sync_api.Browser = playwright.chromium.launch()
        try:
            page: sync_api.Page = browser.new_page()
            page.route(
                url="**/app.js",
                handler=lambda route: route.fulfill(
                    body=Constants.script,
                    content_type="application/javascript",
                ),
            )
            page.route(
                url="**/missing.png",
                handler=lambda route: route.fulfill(
                    status=404,
                    body="Missing",
                ),
            )
            collector: DiagnosticCollector = DiagnosticCollector(
                variant="test",
            )
            collector.attach_sync(page=page)
            page.set_content(html=Constants.page)
            page.wait_for_timeout(timeout=100)
            _verify(events=collector.events)
        finally:
            browser.close()


async def _capture_async() -> tuple[DiagnosticEvent, ...]:
    """Run the async discovery capture against the same browser evidence.

    Returns:
        Captured diagnostic events.

    """
    async with async_api.async_playwright() as playwright:
        browser: async_api.Browser = await playwright.chromium.launch()
        try:
            page: async_api.Page = await browser.new_page()

            async def script(route: async_api.Route) -> None:
                """Serve the source script.

                Args:
                    route: Browser script request.

                """
                await route.fulfill(
                    body=Constants.script,
                    content_type="application/javascript",
                )

            async def missing(route: async_api.Route) -> None:
                """Serve a native browser resource error.

                Args:
                    route: Browser image request.

                """
                await route.fulfill(status=404, body="Missing")

            await page.route(url="**/app.js", handler=script)
            await page.route(url="**/missing.png", handler=missing)
            collector: DiagnosticCollector = DiagnosticCollector(
                variant="test",
            )
            await collector.attach_async(page=page)
            await page.set_content(html=Constants.page)
            await page.wait_for_timeout(timeout=100)
            return collector.events
        finally:
            await browser.close()


def test_async_console_and_exception_sources() -> None:
    """Discovery also retains source lines and function names."""
    _verify(events=run(main=_capture_async()))
