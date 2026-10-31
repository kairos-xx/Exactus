# Copyright (c) 2026 Project contributors
"""Verify the shared HTTP sender used by runs and by Studio's Send."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import sync_playwright

from exactus.tests.common.support import expect_equal
from exactus.tools.record.http_request import (
    HttpResult,
    PreparedRequest,
    cookie_header,
    send_request,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from playwright.sync_api import APIRequestContext


@pytest.fixture
def api() -> Iterator[APIRequestContext]:
    """Open an isolated request context.

    Yields:
        A request context, disposed afterwards.

    """
    with sync_playwright() as playwright:
        context: APIRequestContext = playwright.request.new_context()
        try:
            yield context
        finally:
            context.dispose()


def test_send_request_returns_parsed_json(
    api: APIRequestContext,
    echo_url: str,
) -> None:
    """A JSON response comes back with status, parsed body and timing.

    Args:
        api: Request context that sends the call.
        echo_url: Echo server address.

    """
    result: HttpResult = send_request(
        context=api,
        request=PreparedRequest(
            method="GET",
            url=echo_url,
            headers={},
            body="",
            timeout_ms=5000,
        ),
    )
    expect_equal(actual=result["status"], expected=200)
    expect_equal(actual=result["json"], expected={"ok": True, "cookie": ""})
    expect_equal(actual=result["elapsed_ms"] >= 0, expected=True)


def test_explicit_cookie_rows_are_sent(
    api: APIRequestContext,
    echo_url: str,
) -> None:
    """Only enabled cookie rows reach the server.

    Args:
        api: Request context that sends the call.
        echo_url: Echo server address.

    """
    header: str | None = cookie_header(
        rows=[
            {"key": "lang", "value": "pt", "enabled": True},
            {"key": "x", "value": "1", "enabled": False},
        ],
    )
    result: HttpResult = send_request(
        context=api,
        request=PreparedRequest(
            method="GET",
            url=echo_url,
            headers={"Cookie": header or ""},
            body="",
            timeout_ms=5000,
        ),
    )
    expect_equal(
        actual=result["json"],
        expected={"ok": True, "cookie": "lang=pt"},
    )
