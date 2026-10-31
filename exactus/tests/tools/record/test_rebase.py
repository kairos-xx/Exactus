# Copyright (c) 2026 Project contributors
"""Recorded local URLs follow the target; outside addresses never move."""

from __future__ import annotations

import pytest

from exactus.tests.common.support import expect_equal
from exactus.tools.record.model import Target, TargetMode
from exactus.tools.record.rebase import rebase_url


@pytest.mark.parametrize(
    ("url", "origin", "expected"),
    [
        (
            "http://127.0.0.1:8000/cart?id=1#top",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5173/cart?id=1#top",
        ),
        (
            "http://localhost:3000/",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5173/",
        ),
        (
            "http://[::1]:3000/a",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5173/a",
        ),
        (
            "http://127.0.0.1:8000/a",
            "https://staging.example.com",
            "https://staging.example.com/a",
        ),
        (
            "https://example.com/a",
            "http://127.0.0.1:5173",
            "https://example.com/a",
        ),
        (
            "http://127.0.0.1:5173/a",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5173/a",
        ),
        ("http://127.0.0.1:8000/a", None, "http://127.0.0.1:8000/a"),
        ("about:blank", "http://127.0.0.1:5173", "about:blank"),
        ("file:///tmp/a.html", "http://127.0.0.1:5173", "file:///tmp/a.html"),
    ],
)
def test_rebase_url_moves_only_local_addresses(
    url: str,
    origin: str | None,
    expected: str,
) -> None:
    """Local URLs move to the target's origin; everything else stays.

    Args:
        url: Address stored in the flow.
        origin: Origin the service now runs at, when it is running.
        expected: Address the recorded step should end up with.

    """
    expect_equal(actual=rebase_url(url=url, origin=origin), expected=expected)


def test_target_origin_follows_mode_and_port() -> None:
    """An address target and a running service both expose their origin."""
    address: Target = Target(
        mode=TargetMode.URL,
        url="http://localhost",
        port=8080,
    )
    expect_equal(actual=address.origin(), expected="http://localhost:8080")
    service: Target = Target(
        mode=TargetMode.SERVICE,
        command=("python", "app.py"),
    )
    expect_equal(actual=service.origin(), expected=None)
    expect_equal(
        actual=service.origin(service_url="http://127.0.0.1:6001"),
        expected="http://127.0.0.1:6001",
    )
    expect_equal(actual=Target().origin(), expected=None)
