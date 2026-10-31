# Copyright (c) 2026
"""Wake an Exactus MCP service through signed MantleDB commands."""

from __future__ import annotations

from asyncio import (
    Task,
    create_subprocess_exec,
    create_task,
    sleep,
    to_thread,
    wait_for,
)
from asyncio.subprocess import PIPE, STDOUT, Process
from dataclasses import dataclass, field
from hashlib import sha256
from hmac import compare_digest, new
from json import JSONDecodeError, dumps, loads
from re import Match, Pattern
from re import compile as compile_pattern
from sys import stderr
from time import monotonic, time
from typing import TYPE_CHECKING, Final, Protocol, cast, final
from urllib.error import HTTPError, URLError
from urllib.parse import ParseResult, urlparse, urlunsplit
from uuid import UUID

from .mantledb import (
    HttpRequest,
    MantleUrlStore,
    UrlOpener,
    UrlResponse,
    default_url_opener,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from exactus.packages.server.json_types import JsonValue


@final
class Constants:
    """Group signed wake protocol constants.

    Attributes:
        command_domain: HMAC domain separator for wake commands.
        response_domain: HMAC domain separator for ready responses.
        url_pattern: Default public HTTPS URL matcher.
        process_stop_timeout: Grace period before killing an owned child.
        uuid_version: Required UUID protocol version.

    """

    command_domain: Final[str] = "exactus-mcp-wake"
    response_domain: Final[str] = "exactus-mcp-ready"
    url_pattern: Final[str] = r"(?<=MCP endpoint: )https://[^\s<>'\"]+"
    process_stop_timeout: Final[float] = 5.0
    uuid_version: Final[int] = 4


class WakeError(RuntimeError):
    """Report a wake protocol, transport, or launch failure."""


def _signature(*, key: str, fields: tuple[str, ...]) -> str:
    """Return an HMAC-SHA256 signature for domain-separated fields.

    Args:
        key: Secret HMAC key.
        fields: Ordered domain and payload fields.

    Returns:
        Lowercase hexadecimal HMAC-SHA256 digest.

    """
    message: str = "\n".join(fields)
    return new(
        key=key.encode(encoding="utf-8"),
        msg=message.encode(encoding="utf-8"),
        digestmod=sha256,
    ).hexdigest()


@final
@dataclass(frozen=True, slots=True)
class WakeCommand:
    """Represent one authenticated, short-lived wake request.

    Attributes:
        identifier: Fresh request UUID v4.
        issued_at: Unix timestamp used by the replay window.

    """

    identifier: UUID
    issued_at: int

    @property
    def text(self) -> str:
        """Return the canonical request UUID.

        Returns:
            Lowercase canonical UUID text.

        """
        return str(object=self.identifier)

    def signature(self, *, key: str) -> str:
        """Sign this command with the configured wake key.

        Args:
            key: Dedicated wake HMAC key.

        Returns:
            Domain-separated command signature.

        """
        return _signature(
            key=key,
            fields=(
                Constants.command_domain,
                self.text,
                str(object=self.issued_at),
            ),
        )


@final
@dataclass(frozen=True, slots=True)
class WakeResponse:
    """Represent one authenticated ready response.

    Attributes:
        identifier: UUID of the command that started or reused the service.
        url: Discovered public HTTPS MCP endpoint.

    """

    identifier: UUID
    url: str

    @property
    def identifier_text(self) -> str:
        """Return the canonical request UUID.

        Returns:
            Lowercase canonical UUID text.

        """
        return str(object=self.identifier)

    def signature(self, *, key: str) -> str:
        """Sign this response with the configured wake key.

        Args:
            key: Dedicated wake HMAC key.

        Returns:
            Domain-separated ready-response signature.

        """
        return _signature(
            key=key,
            fields=(Constants.response_domain, self.identifier_text, self.url),
        )

    def __post_init__(self) -> None:
        """Require an absolute credential-free HTTPS endpoint."""
        parsed: ParseResult = urlparse(url=self.url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            msg: str = "Wake response URL must be absolute HTTPS."
            raise ValueError(msg)


class WakeStore(Protocol):
    """Contract required by the wake watcher persistence boundary."""

    def retrieve_command(self) -> WakeCommand:
        """Retrieve one authenticated wake command.

        Returns:
            Fresh verified wake command.

        """
        ...

    def publish_response(self, *, response: WakeResponse) -> None:
        """Publish one authenticated ready response.

        Args:
            response: UUID-bound public service response.

        """
        ...


class ServiceLauncher(Protocol):
    """Contract required by the wake watcher process boundary."""

    async def start_and_resolve(self) -> str:
        """Start when needed and return the active public MCP URL.

        Returns:
            Current public HTTPS MCP endpoint.

        """
        ...


@final
@dataclass(frozen=True, slots=True)
class MantleWakeStore:
    """Read signed wake commands and publish matching ready responses.

    Attributes:
        namespace: Private MantleDB namespace.
        signing_key: Dedicated wake HMAC key.
        command_path: MantleDB path carrying wake commands.
        response_path: MantleDB path carrying ready responses.
        timeout: HTTP request timeout in seconds.
        maximum_age: Maximum accepted command age in seconds.
        opener: Injected constrained HTTP transport.

    """

    namespace: str
    signing_key: str = field(repr=False, compare=False)
    command_path: str = "wake/command"
    response_path: str = "wake/response"
    timeout: float = 10.0
    maximum_age: float = 120.0
    opener: UrlOpener = field(
        default=default_url_opener,
        repr=False,
        compare=False,
    )

    def retrieve_command(
        self,
        *,
        current_time: float | None = None,
    ) -> WakeCommand:
        """Retrieve and authenticate the current wake command.

        Args:
            current_time: Injected Unix timestamp for deterministic tests.

        Returns:
            Fresh, canonical, correctly signed UUID command.

        Raises:
            WakeError: If the record is unavailable, malformed, stale, or
                incorrectly signed.

        """
        document: JsonValue = self._retrieve(path=self.command_path)
        if not isinstance(document, dict):
            msg: str = "MantleDB wake command must be an object."
            raise WakeError(msg)
        identifier_value: JsonValue | None = document.get("id")
        issued_at_value: JsonValue | None = document.get("issued_at")
        signature_value: JsonValue | None = document.get("signature")
        if (
            not isinstance(identifier_value, str)
            or not isinstance(issued_at_value, int)
            or isinstance(issued_at_value, bool)
            or not isinstance(signature_value, str)
        ):
            msg = "MantleDB wake command is incomplete."
            raise WakeError(msg)
        try:
            identifier: UUID = UUID(hex=identifier_value)
        except ValueError as exc:
            msg = "MantleDB wake command UUID is invalid."
            raise WakeError(msg) from exc
        command: WakeCommand = WakeCommand(
            identifier=identifier,
            issued_at=issued_at_value,
        )
        if (
            identifier.version != Constants.uuid_version
            or command.text != identifier_value.lower()
        ):
            msg = "MantleDB wake command must use a canonical UUID v4."
            raise WakeError(msg)
        now: float = time() if current_time is None else current_time
        if abs(now - float(command.issued_at)) > self.maximum_age:
            msg = "MantleDB wake command is outside the replay window."
            raise WakeError(msg)
        expected: str = command.signature(key=self.signing_key)
        if not compare_digest(signature_value, expected):
            msg = "MantleDB wake command signature is invalid."
            raise WakeError(msg)
        return command

    def publish_response(self, *, response: WakeResponse) -> None:
        """Publish a signed URL bound to the triggering UUID.

        Args:
            response: Verified public URL and triggering UUID.

        """
        document: dict[str, bool | str] = {
            "id": response.identifier_text,
            "ready": True,
            "signature": response.signature(key=self.signing_key),
            "url": response.url,
        }
        self._write(path=self.response_path, document=document)

    def _endpoint(self, *, path: str) -> str:
        """Return one constrained endpoint in this namespace.

        Args:
            path: Record path below the namespace.

        Returns:
            Absolute MantleDB v2 endpoint.

        """
        return MantleUrlStore(namespace=self.namespace, path=path).endpoint

    def _retrieve(self, *, path: str) -> JsonValue:
        """Retrieve one JSON document from MantleDB.

        Args:
            path: Record path below the namespace.

        Returns:
            Parsed JSON record.

        Raises:
            WakeError: If transport or JSON decoding fails.

        """
        request: HttpRequest = HttpRequest(
            url=self._endpoint(path=path),
            method="GET",
            headers={"Accept": "application/json"},
        )
        response: UrlResponse
        try:
            with self.opener(
                request=request,
                timeout=self.timeout,
            ) as response:
                payload: bytes = response.read()
        except (HTTPError, URLError, OSError) as exc:
            msg: str = f"Unable to retrieve MantleDB wake record: {exc}"
            raise WakeError(msg) from exc
        try:
            return cast(typ="JsonValue", val=loads(s=payload))
        except JSONDecodeError as exc:
            msg = f"MantleDB wake record is invalid JSON: {exc}"
            raise WakeError(msg) from exc

    def _write(self, *, path: str, document: dict[str, bool | str]) -> None:
        """Write one JSON document to MantleDB.

        Args:
            path: Record path below the namespace.
            document: JSON response record to persist.

        Raises:
            WakeError: If the MantleDB write fails.

        """
        request: HttpRequest = HttpRequest(
            url=self._endpoint(path=path),
            method="POST",
            data=dumps(obj=document, sort_keys=True).encode(encoding="utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response: UrlResponse
        try:
            with self.opener(
                request=request,
                timeout=self.timeout,
            ) as response:
                _payload: bytes = response.read()
        except (HTTPError, URLError, OSError) as exc:
            msg: str = f"Unable to publish MantleDB wake response: {exc}"
            raise WakeError(msg) from exc


@final
@dataclass(frozen=True, slots=True)
class WakeStateStore:
    """Persist the last completed wake UUID atomically.

    Attributes:
        path: Private local state-file path.

    """

    path: Path

    def read(self) -> UUID | None:
        """Return the last completed UUID when the state is valid.

        Returns:
            Persisted UUID, or ``None`` for absent or invalid state.

        """
        if not self.path.exists():
            return None
        value: str = self.path.read_text(encoding="utf-8").strip()
        if not value:
            return None
        try:
            return UUID(hex=value)
        except ValueError:
            return None

    def write(self, *, identifier: UUID) -> None:
        """Atomically persist one completed UUID.

        Args:
            identifier: Successfully processed wake UUID.

        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path = self.path.with_suffix(
            suffix=f"{self.path.suffix}.tmp",
        )
        _ = temporary.write_text(data=f"{identifier}\n", encoding="utf-8")
        temporary.replace(target=self.path)


@final
@dataclass(slots=True)
class WakeServiceLauncher:
    """Own a fixed service command and discover its public HTTPS URL.

    Attributes:
        command: Fixed shell-free child argument vector.
        discovery_timeout: Maximum URL discovery duration in seconds.
        mcp_path: Path appended to a discovered public origin.
        url_pattern: Regular expression locating the emitted HTTPS URL.
        environment: Explicit child environment, when configured.

    """

    command: tuple[str, ...]
    discovery_timeout: float
    mcp_path: str = "/mcp"
    url_pattern: str = Constants.url_pattern
    environment: Mapping[str, str] | None = field(default=None, repr=False)
    _process: Process | None = field(default=None, init=False, repr=False)
    _public_url: str | None = field(default=None, init=False, repr=False)
    _drain_task: Task[None] | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _compiled_pattern: Pattern[str] = field(init=False, repr=False)

    @property
    def running(self) -> bool:
        """Return whether the owned service process is alive.

        Returns:
            Whether the child exists and has not exited.

        """
        return self._process is not None and self._process.returncode is None

    async def start_and_resolve(self) -> str:
        """Start the service when needed and return its current MCP URL.

        Returns:
            Current public HTTPS MCP endpoint.

        """
        if self.running and self._public_url is not None:
            return self._public_url
        if self._drain_task is not None:
            await self._drain_task
            self._drain_task = None
        self._public_url = None
        self._process = await create_subprocess_exec(
            *self.command,
            stdin=None,
            stdout=PIPE,
            stderr=STDOUT,
            env=self.environment,
        )
        try:
            self._public_url = await self._discover_url()
        except (OSError, WakeError):
            await self.close()
            raise
        self._drain_task = create_task(coro=self._drain_output())
        return self._public_url

    async def close(self) -> None:
        """Stop the owned service process, if any."""
        process: Process | None = self._process
        self._process = None
        self._public_url = None
        if process is None or process.returncode is not None:
            if self._drain_task is not None:
                await self._drain_task
                self._drain_task = None
            return
        process.terminate()
        try:
            _ = await wait_for(
                fut=process.wait(),
                timeout=Constants.process_stop_timeout,
            )
        except TimeoutError:
            process.kill()
            _ = await process.wait()
        if self._drain_task is not None:
            await self._drain_task
            self._drain_task = None

    def __post_init__(self) -> None:
        """Validate startup settings and compile the URL matcher."""
        if not self.command:
            msg: str = "Wake service command cannot be empty."
            raise ValueError(msg)
        if self.discovery_timeout <= 0:
            msg = "Wake discovery timeout must be positive."
            raise ValueError(msg)
        if not self.mcp_path.startswith("/"):
            msg = "Wake MCP path must start with '/'."
            raise ValueError(msg)
        self._compiled_pattern = compile_pattern(pattern=self.url_pattern)

    async def _discover_url(self) -> str:
        """Read combined service output until an HTTPS URL appears.

        Returns:
            Normalized public HTTPS MCP endpoint.

        Raises:
            WakeError: If the child exits or no URL appears before timeout.

        """
        process: Process | None = self._process
        if process is None or process.stdout is None:
            msg: str = "Unable to capture Exactus MCP service output."
            raise WakeError(msg)
        deadline: float = monotonic() + self.discovery_timeout
        while True:
            remaining: float = deadline - monotonic()
            if remaining <= 0:
                msg = "Timed out waiting for the Exactus MCP public URL."
                raise WakeError(msg)
            try:
                line_bytes: bytes = await wait_for(
                    fut=process.stdout.readline(),
                    timeout=remaining,
                )
            except TimeoutError as exc:
                msg = "Timed out waiting for the Exactus MCP public URL."
                raise WakeError(msg) from exc
            if not line_bytes:
                exit_code: int = await process.wait()
                msg = (
                    "Exactus MCP service exited before publishing a public "
                    f"URL (status {exit_code})."
                )
                raise WakeError(msg)
            line: str = line_bytes.decode(encoding="utf-8", errors="replace")
            match: Match[str] | None = self._compiled_pattern.search(
                string=line,
            )
            if match is not None:
                return self._normalize_url(url=match.group(0))

    async def _drain_output(self) -> None:
        """Drain child output so its pipe cannot block the service."""
        process: Process | None = self._process
        if process is None or process.stdout is None:
            return
        while await process.stdout.readline():
            continue

    def _normalize_url(self, *, url: str) -> str:
        """Normalize a discovered HTTPS origin to an MCP endpoint.

        Args:
            url: URL matched in child output.

        Returns:
            Credential-free HTTPS MCP endpoint.

        Raises:
            WakeError: If the discovered URL is not a valid HTTPS origin.

        """
        parsed: ParseResult = urlparse(url=url.rstrip(".,;)]}"))
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            msg: str = "Discovered Exactus MCP URL is invalid."
            raise WakeError(msg)
        path: str = (
            parsed.path if parsed.path not in ("", "/") else self.mcp_path
        )
        return urlunsplit(
            components=(parsed.scheme, parsed.netloc, path, "", ""),
        )


@final
@dataclass(slots=True)
class WakeWatcher:
    """Poll signed commands and publish the matching ready service URL.

    Attributes:
        store: Signed MantleDB command and response boundary.
        state: Durable completed-UUID store.
        launcher: Fixed local service process boundary.
        poll_interval: Normal polling delay in seconds.
        retry_maximum: Maximum failure-backoff delay in seconds.
        keep_service_running: Whether each polling iteration first ensures the
            fixed child service is alive.

    """

    store: WakeStore
    state: WakeStateStore
    launcher: ServiceLauncher
    poll_interval: float = 3.0
    retry_maximum: float = 30.0
    keep_service_running: bool = False

    async def poll_once(self) -> bool:
        """Process one fresh signed UUID and publish its ready response.

        Returns:
            ``True`` when a fresh UUID was completed, otherwise ``False``.

        """
        public_url: str | None = None
        if self.keep_service_running:
            public_url = await self.launcher.start_and_resolve()
        command: WakeCommand = await to_thread(self.store.retrieve_command)
        if self.state.read() == command.identifier:
            return False
        if public_url is None:
            public_url = await self.launcher.start_and_resolve()
        response: WakeResponse = WakeResponse(
            identifier=command.identifier,
            url=public_url,
        )
        await to_thread(self.store.publish_response, response=response)
        self.state.write(identifier=command.identifier)
        return True

    async def run(self) -> None:
        """Poll forever with bounded retry backoff."""
        delay: float = self.poll_interval
        while True:
            try:
                _ = await self.poll_once()
                delay = self.poll_interval
            except (OSError, ValueError, WakeError) as exc:
                _ = stderr.write(f"exactus-mcp-wakeup: {exc}\n")
                stderr.flush()
                delay = min(delay * 2.0, self.retry_maximum)
            await sleep(delay=delay)
