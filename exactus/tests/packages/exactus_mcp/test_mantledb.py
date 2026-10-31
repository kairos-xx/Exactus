# Copyright (c) 2026
"""Validate MantleDB URL persistence without network access."""

from __future__ import annotations

from dataclasses import dataclass, field
from email.message import Message
from functools import partial
from hashlib import sha256
from hmac import new
from http.client import HTTPResponse, HTTPSConnection
from typing import TYPE_CHECKING, Self, final
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from exactus.packages.exactus_mcp import mantledb
from exactus.packages.exactus_mcp.mantledb import (
    HttpRequest,
    MantleUrlStore,
    UrlResponse,
    default_url_opener,
)
from exactus.tests.common.support import expect_equal, private_call

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType


@final
@dataclass(slots=True)
class FakeResponse:
    """Return one synthetic HTTP response body.

    Attributes:
        payload: Bytes returned by ``read``.

    """

    payload: bytes

    def read(self) -> bytes:
        """Return the configured body.

        Returns:
            Synthetic response bytes.

        """
        return self.payload

    def __enter__(self) -> Self:
        """Enter the synthetic response.

        Returns:
            Active response.

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the no-op response.

        Args:
            exc_type: Active exception type, when present.
            exc_value: Active exception, when present.
            traceback: Active exception traceback, when present.

        """


@final
@dataclass(slots=True)
class FakeOpener:
    """Record requests and return queued bodies.

    Attributes:
        bodies: Response bodies returned in order.
        requests: Captured request objects.
        timeouts: Captured request timeouts.

    """

    bodies: list[bytes]
    requests: list[HttpRequest] = field(default_factory=list)
    timeouts: list[float] = field(default_factory=list)

    def __call__(self, *, request: HttpRequest, timeout: float) -> UrlResponse:
        """Capture a request and return the next response.

        Args:
            request: Prepared request.
            timeout: Configured timeout.

        Returns:
            Synthetic managed response.

        """
        self.requests.append(request)
        self.timeouts.append(timeout)
        return FakeResponse(payload=self.bodies.pop(0))


def test_store_writes_and_retrieves_public_url() -> None:
    """The store uses escaped endpoints and JSON request bodies."""
    public_url: str = "https://dynamic.ngrok-free.app"
    signing_key: str = "test-only-secret"
    signature: str = new(
        key=signing_key.encode(encoding="utf-8"),
        msg=public_url.encode(encoding="utf-8"),
        digestmod=sha256,
    ).hexdigest()
    opener: FakeOpener = FakeOpener(
        bodies=[
            b"",
            (f'{{"url":"{public_url}","signature":"{signature}"}}').encode(),
        ],
    )
    store: MantleUrlStore = MantleUrlStore(
        namespace="Exactus service",
        path="active/url",
        timeout=3.0,
        opener=opener,
        signing_key=signing_key,
    )
    store.save(url=public_url)
    retrieved: str = store.retrieve()
    expect_equal(actual=retrieved, expected=public_url)
    expect_equal(
        actual=store.endpoint,
        expected="https://mantledb.sh/v2/Exactus%20service/active/url",
    )
    expect_equal(actual=opener.requests[0].method, expected="POST")
    expect_equal(
        actual=opener.requests[0].data,
        expected=(
            f'{{"signature": "{signature}", "url": "{public_url}"}}'
        ).encode(),
    )
    expect_equal(actual=opener.requests[1].method, expected="GET")
    expect_equal(actual=opener.timeouts, expected=[3.0, 3.0])


@pytest.mark.parametrize("body", [b"[]", b"{}", b'{"url":3}'])
def test_store_rejects_invalid_url_payloads(body: bytes) -> None:
    """Decoded values must contain a string URL.

    Args:
        body: Malformed discovery payload.

    """
    with pytest.raises(expected_exception=TypeError, match="valid URL"):
        MantleUrlStore(
            namespace="test",
            opener=FakeOpener(bodies=[body]),
        ).retrieve()


@pytest.mark.parametrize(
    "body",
    [
        b'{"url":"https://example.test"}',
        b'{"url":"https://example.test","signature":3}',
        b'{"url":"https://example.test","signature":"wrong"}',
    ],
)
def test_store_rejects_unsigned_or_tampered_discovery(body: bytes) -> None:
    """A configured signing key requires an authentic string signature.

    Args:
        body: Unauthenticated discovery payload.

    """
    with pytest.raises(expected_exception=RuntimeError, match="signature"):
        MantleUrlStore(
            namespace="test",
            opener=FakeOpener(bodies=[body]),
            signing_key="test-key",
        ).retrieve()


def test_store_updates_unsigned_records_and_rejects_empty_urls() -> None:
    """Unsigned stores support updates but refuse empty records."""
    opener: FakeOpener = FakeOpener(
        bodies=[b"", b'{"url":"https://example.test"}'],
    )
    store: MantleUrlStore = MantleUrlStore(namespace="test", opener=opener)
    with pytest.raises(expected_exception=ValueError, match="cannot be empty"):
        store.save(url="")
    store.update(url="https://example.test")
    expect_equal(actual=store.retrieve(), expected="https://example.test")
    expect_equal(
        actual=opener.requests[0].data,
        expected=b'{"url": "https://example.test"}',
    )
    with pytest.raises(expected_exception=RuntimeError, match="invalid JSON"):
        MantleUrlStore(
            namespace="test",
            opener=FakeOpener(bodies=[b"broken"]),
        ).retrieve()


def test_signature_requires_configured_key() -> None:
    """Signing is impossible without a configured HMAC key."""
    store: MantleUrlStore = MantleUrlStore(
        namespace="test",
        opener=FakeOpener(bodies=[]),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="signing key is not configured",
    ):
        private_call(
            owner=store,
            name="_signature",
            url="https://example.test",
        )


@pytest.mark.parametrize("operation", ["save", "retrieve"])
def test_store_translates_transport_errors(operation: str) -> None:
    """Transport failures retain their cause without pretending success.

    Args:
        operation: Store operation to fail.

    """
    failure: OSError = OSError("offline")
    store: MantleUrlStore = MantleUrlStore(
        namespace="test",
        opener=MagicMock(side_effect=failure),
    )
    invoke: Callable[[], str | None] = (
        partial(store.save, url="https://example.test")
        if operation == "save"
        else store.retrieve
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unable to",
    ) as caught:
        invoke()
    expect_equal(actual=caught.value.__cause__, expected=failure)


@pytest.mark.parametrize(
    "url",
    [
        "http://mantledb.sh/v2/test",
        "https://example.test/v2/test",
        "https://user@mantledb.sh/v2/test",
        "https://user:pass@mantledb.sh/v2/test",
    ],
)
def test_default_transport_rejects_untrusted_origins(url: str) -> None:
    """The default transport cannot be redirected to arbitrary origins.

    Args:
        url: Disallowed request origin.

    """
    with pytest.raises(expected_exception=URLError, match="only permits"):
        default_url_opener(
            request=HttpRequest(url=url, method="GET"),
            timeout=1.0,
        )


@pytest.mark.parametrize("status", [200, 404])
def test_default_transport_owns_response_and_connection(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    """Success and HTTP failures close both owned transport resources.

    Args:
        monkeypatch: HTTPS connection boundary replacement.
        status: Simulated HTTP response status.

    """
    response: MagicMock = MagicMock(spec=HTTPResponse)
    response.status = status
    response.reason = "Not Found"
    response.headers = Message()
    response.read.return_value = b"payload"
    connection: MagicMock = MagicMock(spec=HTTPSConnection)
    connection.getresponse.return_value = response
    factory: MagicMock = MagicMock(return_value=connection)
    monkeypatch.setattr(target=mantledb, name="HTTPSConnection", value=factory)
    request: HttpRequest = HttpRequest(
        url="https://mantledb.sh/v2/test?version=2",
        method="GET",
    )
    if status >= mantledb.Constants.http_error_minimum:
        with pytest.raises(expected_exception=HTTPError, match="404"):
            default_url_opener(request=request, timeout=2.0)
    else:
        with default_url_opener(request=request, timeout=2.0) as opened:
            expect_equal(actual=opened.read(), expected=b"payload")
        path_only: HttpRequest = HttpRequest(
            url="https://mantledb.sh/v2/test",
            method="GET",
        )
        with default_url_opener(request=path_only, timeout=2.0) as opened:
            expect_equal(actual=opened.read(), expected=b"payload")
    expect_equal(
        actual=len(factory.call_args_list),
        expected=1 if status >= mantledb.Constants.http_error_minimum else 2,
    )
    connection.request.assert_any_call(
        method="GET",
        url="/v2/test?version=2",
        body=None,
        headers={},
    )
    if status < mantledb.Constants.http_error_minimum:
        connection.request.assert_any_call(
            method="GET",
            url="/v2/test",
            body=None,
            headers={},
        )
    closes: int = 1 if status >= mantledb.Constants.http_error_minimum else 2
    expect_equal(actual=response.close.call_count, expected=closes)
    expect_equal(actual=connection.close.call_count, expected=closes)
