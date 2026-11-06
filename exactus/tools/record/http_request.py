# Copyright (c) 2026 Project contributors
"""Send one REST request; shared by flow runs and Studio's Send."""

from __future__ import annotations

from dataclasses import dataclass
from json import loads
from time import perf_counter
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from playwright.sync_api import APIRequestContext, APIResponse

    from exactus.tools.common.json_types import JsonValue


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedRequest:
    """A request whose variables are already expanded.

    Attributes:
        method: HTTP method, such as ``GET``.
        url: Absolute request URL.
        headers: Header names and values, including ``Cookie`` when set.
        body: Request body; empty sends none.
        timeout_ms: Time limit for the whole exchange.

    """

    method: str
    url: str
    headers: Mapping[str, str]
    body: str
    timeout_ms: float


class HttpResult(TypedDict):
    """What a sent request returned.

    Attributes:
        status: HTTP status code.
        url: Final URL after redirects.
        headers: Response headers.
        body: Response body text.
        json: The body parsed as JSON, or the body text when it is not JSON.
        elapsed_ms: Wall time of the exchange.

    """

    status: int
    url: str
    headers: dict[str, str]
    body: str
    json: JsonValue
    elapsed_ms: int


def cookie_header(*, rows: JsonValue) -> str | None:
    """Join the enabled cookie rows of a request into a ``Cookie`` value.

    Args:
        rows: Authored rows ``{key, value, enabled}``.

    Returns:
        ``name=value`` pairs joined by ``"; "``, or None when none apply.

    """
    if not isinstance(rows, list):
        return None
    pairs: list[str] = [
        f"{row.get('key')}={row.get('value') or ''}"
        for row in rows
        if isinstance(row, dict)
        and row.get("enabled") is not False
        and str(object=row.get("key") or "").strip()
    ]
    return "; ".join(pairs) or None


def send_request(
    *,
    context: APIRequestContext,
    request: PreparedRequest,
) -> HttpResult:
    """Send a prepared request and describe the response.

    Args:
        context: Request context whose cookies and network apply; the
            caller owns and disposes it.
        request: The expanded request.

    Returns:
        Status, final URL, headers, body, parsed body and elapsed time.

    """
    started: float = perf_counter()
    response: APIResponse = context.fetch(
        url_or_request=request.url,
        method=request.method,
        headers=dict(request.headers),
        data=request.body or None,
        timeout=request.timeout_ms,
    )
    text: str = response.text()
    elapsed_ms: int = round(number=(perf_counter() - started) * 1000)
    parsed: JsonValue
    try:
        parsed = cast(typ="JsonValue", val=loads(s=text))
    except ValueError:
        parsed = text
    return {
        "status": response.status,
        "url": response.url,
        "headers": dict(response.headers),
        "body": text,
        "json": parsed,
        "elapsed_ms": elapsed_ms,
    }
