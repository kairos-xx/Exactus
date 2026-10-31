# Copyright (c) 2026
"""Persist the active Exactus public URL through MantleDB."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from hmac import compare_digest, new
from http.client import HTTPResponse, HTTPSConnection
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, Final, Protocol, Self, cast, final
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, quote, urlparse

if TYPE_CHECKING:
    from types import TracebackType

    from exactus.packages.server.json_types import JsonValue


@final
class Constants:
    """Group MantleDB transport constants.

    Attributes:
        host: Only host admitted by the default HTTP transport.
        http_error_minimum: First HTTP error status.

    """

    host: Final[str] = "mantledb.sh"
    http_error_minimum: Final[int] = 400


@final
@dataclass(frozen=True, slots=True)
class HttpRequest:
    """Describe one constrained MantleDB HTTP request.

    Attributes:
        url: Absolute MantleDB endpoint.
        method: HTTP method.
        data: Optional request body.
        headers: Explicit request headers.

    """

    url: str
    method: str
    data: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)


class UrlResponse(Protocol):
    """Minimal HTTP response contract used by the URL store."""

    def read(self) -> bytes:
        """Read the response body.

        Returns:
            Response body bytes.

        """
        ...

    def __enter__(self) -> Self:
        """Enter the managed response.

        Returns:
            Active response object.

        """
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the managed response.

        Args:
            exc_type: Active exception type, when present.
            exc_value: Active exception, when present.
            traceback: Active exception traceback, when present.

        """
        ...


class UrlOpener(Protocol):
    """Injected HTTP boundary used by ``MantleUrlStore``."""

    def __call__(self, *, request: HttpRequest, timeout: float) -> UrlResponse:
        """Open one HTTP request.

        Args:
            request: Prepared constrained request.
            timeout: Network timeout in seconds.

        Returns:
            Managed response object.

        """
        ...


@final
@dataclass(slots=True)
class ManagedHttpResponse:
    """Own an HTTPS connection and its active response.

    Attributes:
        connection: HTTPS connection closed with the response.
        response: Active response body.

    """

    connection: HTTPSConnection
    response: HTTPResponse

    def read(self) -> bytes:
        """Read the active response body.

        Returns:
            Response bytes.

        """
        return self.response.read()

    def __enter__(self) -> Self:
        """Enter the managed response.

        Returns:
            Active response wrapper.

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the response and owning connection.

        Args:
            exc_type: Active exception type, when present.
            exc_value: Active exception, when present.
            traceback: Active exception traceback, when present.

        """
        self.response.close()
        self.connection.close()


def default_url_opener(*, request: HttpRequest, timeout: float) -> UrlResponse:
    """Open a MantleDB request through urllib.

    Args:
        request: Prepared constrained request.
        timeout: Network timeout in seconds.

    Returns:
        Managed urllib response.

    Raises:
        URLError: If the request escapes the permitted MantleDB origin.
        HTTPError: If the response reports an error status.

    """
    parsed: ParseResult = urlparse(url=request.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != Constants.host
        or parsed.username is not None
        or parsed.password is not None
    ):
        msg: str = "MantleDB transport only permits https://mantledb.sh"
        raise URLError(reason=msg)
    connection: HTTPSConnection = HTTPSConnection(
        host=Constants.host,
        port=parsed.port,
        timeout=timeout,
    )
    selector: str = parsed.path
    if parsed.query:
        selector = f"{selector}?{parsed.query}"
    connection.request(
        method=request.method,
        url=selector,
        body=request.data,
        headers=request.headers,
    )
    response: HTTPResponse = connection.getresponse()
    if response.status >= Constants.http_error_minimum:
        response.close()
        connection.close()
        raise HTTPError(
            url=request.url,
            code=response.status,
            msg=response.reason,
            hdrs=response.headers,
            fp=None,
        )
    return ManagedHttpResponse(connection=connection, response=response)


@final
@dataclass(frozen=True, slots=True)
class MantleUrlStore:
    """Store and retrieve one public URL using MantleDB.

    Attributes:
        namespace: MantleDB namespace identifying this service.
        path: Record path below the namespace.
        timeout: HTTP request timeout in seconds.
        opener: Injected HTTP transport.
        signing_key: Optional secret authenticating the discovery record.

    """

    namespace: str
    path: str = "url"
    timeout: float = 10.0
    opener: UrlOpener = field(
        default=default_url_opener,
        repr=False,
        compare=False,
    )
    signing_key: str | None = field(default=None, repr=False, compare=False)

    @property
    def endpoint(self) -> str:
        """Return the MantleDB endpoint for this store.

        Returns:
            Escaped MantleDB v2 record endpoint.

        """
        return (
            "https://mantledb.sh/v2/"
            f"{quote(string=self.namespace, safe='')}/"
            f"{quote(string=self.path, safe='/')}"
        )

    def save(self, *, url: str) -> None:
        """Save a URL, overwriting any existing value.

        Args:
            url: URL to persist.

        Raises:
            ValueError: If the URL is empty.
            RuntimeError: If communication with MantleDB fails.

        """
        if not url:
            msg: str = "URL cannot be empty."
            raise ValueError(msg)
        self._write(url=url)

    def update(self, *, url: str) -> None:
        """Update the currently stored URL.

        Args:
            url: New URL to persist.

        Raises:
            ValueError: If the URL is empty.
            RuntimeError: If communication with MantleDB fails.

        """
        self.save(url=url)

    def retrieve(self) -> str:
        """Retrieve the stored URL.

        Returns:
            Stored URL.

        Raises:
            RuntimeError: If communication or signature verification fails.
            TypeError: If the response has no string URL.
            TypeError: If the response payload is not a mapping with a string
                ``url`` member.

        """
        request: HttpRequest = HttpRequest(url=self.endpoint, method="GET")
        response: UrlResponse
        network_exc: HTTPError | URLError | OSError
        try:
            with self.opener(
                request=request,
                timeout=self.timeout,
            ) as response:
                payload: bytes = response.read()
        except (HTTPError, URLError, OSError) as network_exc:
            msg: str = f"Unable to retrieve URL from MantleDB: {network_exc}"
            raise RuntimeError(msg) from network_exc
        json_exc: JSONDecodeError
        try:
            document: JsonValue = cast(typ="JsonValue", val=loads(s=payload))
        except JSONDecodeError as json_exc:
            msg = f"MantleDB returned invalid JSON: {json_exc}"
            raise RuntimeError(msg) from json_exc
        if not isinstance(document, dict):
            msg = "MantleDB response does not contain a valid URL."
            raise TypeError(msg)
        value: JsonValue | None = document.get("url")
        if not isinstance(value, str):
            msg = "MantleDB response does not contain a valid URL."
            raise TypeError(msg)
        if self.signing_key is not None:
            signature: JsonValue | None = document.get("signature")
            expected: str = self._signature(url=value)
            if not isinstance(signature, str) or not compare_digest(
                signature,
                expected,
            ):
                msg = "MantleDB URL signature is missing or invalid."
                raise RuntimeError(msg)
        return value

    def _signature(self, *, url: str) -> str:
        """Sign one discovery URL with the configured secret.

        Args:
            url: Public URL stored in the discovery record.

        Returns:
            Lowercase HMAC-SHA256 digest.

        Raises:
            RuntimeError: If signing is requested without a key.

        """
        if self.signing_key is None:
            msg: str = "MantleDB signing key is not configured."
            raise RuntimeError(msg)
        return new(
            key=self.signing_key.encode(encoding="utf-8"),
            msg=url.encode(encoding="utf-8"),
            digestmod=sha256,
        ).hexdigest()

    def _write(self, *, url: str) -> None:
        """Write a URL to MantleDB.

        Args:
            url: URL to persist.

        Raises:
            RuntimeError: If communication with MantleDB fails.

        """
        document: dict[str, str] = {"url": url}
        if self.signing_key is not None:
            document["signature"] = self._signature(url=url)
        request: HttpRequest = HttpRequest(
            url=self.endpoint,
            data=dumps(obj=document, sort_keys=True).encode(encoding="utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response: UrlResponse
        network_exc: HTTPError | URLError | OSError
        try:
            with self.opener(
                request=request,
                timeout=self.timeout,
            ) as response:
                _payload: bytes = response.read()
        except (HTTPError, URLError, OSError) as network_exc:
            msg: str = f"Unable to save URL to MantleDB: {network_exc}"
            raise RuntimeError(msg) from network_exc
