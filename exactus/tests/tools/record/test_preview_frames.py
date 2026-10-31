# Copyright (c) 2026 Project contributors
"""Prove the live preview keeps only matching frames and acknowledges all."""

from __future__ import annotations

from base64 import b64encode
from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import expect_equal
from exactus.tools.record.studio.worker import ManagedBrowserWorker

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from playwright.sync_api import Page

    from exactus.tools.record.store import JsonValue


class _Session:
    """Record the acknowledgements sent to Chromium."""

    def __init__(self) -> None:
        """Start without acknowledgements."""
        self.acknowledged: list[JsonValue] = []

    def send(self, *, method: str, params: dict[str, JsonValue]) -> JsonValue:
        """Remember each acknowledged session identifier.

        Args:
            method: Chromium method name.
            params: Method arguments.

        Returns:
            The recorded acknowledgement payload.

        """
        expect_equal(actual=method, expected="Page.screencastFrameAck")
        self.acknowledged.append(params["sessionId"])

    def on(
        self,
        *,
        event: str,
        f: Callable[[dict[str, JsonValue]], None],
    ) -> None:
        """Ignore subscriptions because frames are delivered directly.

        Args:
            event: Chromium event name.
            f: Frame callback.

        """


def _frame(
    *,
    data: bytes,
    width: int,
    height: int,
    token: int,
) -> dict[str, JsonValue]:
    """Build a screencast frame message.

    Args:
        data: JPEG payload.
        width: Device width reported by Chromium.
        height: Device height reported by Chromium.
        token: Acknowledgement identifier.

    Returns:
        Message shaped like Chromium's `Page.screencastFrame` event.

    """
    return {
        "data": b64encode(s=data).decode(),
        "sessionId": token,
        "metadata": {"deviceWidth": width, "deviceHeight": height},
    }


def test_only_matching_frames_replace_the_preview_and_all_are_acknowledged(
    tmp_path: Path,
) -> None:
    """Reject stale-size and foreign-page frames without stalling Chromium.

    Args:
        tmp_path: Isolated worker output directory.

    """
    worker: ManagedBrowserWorker = ManagedBrowserWorker(output=tmp_path)
    page: Page = cast(typ="Page", val=object())
    other: Page = cast(typ="Page", val=object())
    worker.select_page_for_test(page=page)
    session: _Session = _Session()
    worker.accept_frame(
        page=page,
        session=session,
        message=_frame(data=b"good", width=1440, height=900, token=1),
    )
    expect_equal(actual=worker.preview, expected=b"good")
    # Frame captured before a viewport change: wrong size, so it is dropped.
    worker.accept_frame(
        page=page,
        session=session,
        message=_frame(data=b"stale", width=390, height=844, token=2),
    )
    # Frame from a page that is no longer the active target.
    worker.accept_frame(
        page=other,
        session=session,
        message=_frame(data=b"foreign", width=1440, height=900, token=3),
    )
    # Frame without metadata cannot be proven to match.
    worker.accept_frame(
        page=page,
        session=session,
        message={"data": b64encode(s=b"blind").decode(), "sessionId": 4},
    )
    expect_equal(actual=worker.preview, expected=b"good")
    expect_equal(actual=session.acknowledged, expected=[1, 2, 3, 4])
    next_frame: dict[str, JsonValue] = _frame(
        data=b"next",
        width=1440,
        height=900,
        token=5,
    )
    worker.accept_frame(page=page, session=session, message=next_frame)
    expect_equal(actual=worker.preview, expected=b"next")
