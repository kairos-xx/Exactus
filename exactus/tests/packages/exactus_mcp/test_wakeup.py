# Copyright (c) 2026
"""Validate signed Exactus MCP wake-up behavior."""

from __future__ import annotations

from asyncio import Event as AsyncEvent
from asyncio import run
from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
from json import dumps
from typing import TYPE_CHECKING, Self, final
from urllib.error import URLError
from uuid import UUID

import pytest

from exactus.packages.exactus_mcp.wakeup import (
    MantleWakeStore,
    WakeCommand,
    WakeError,
    WakeResponse,
    WakeServiceLauncher,
    WakeStateStore,
    WakeWatcher,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
    require_type,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from pathlib import Path
    from types import ModuleType, TracebackType

    from exactus.packages.exactus_mcp.mantledb import HttpRequest, UrlResponse


@final
@dataclass(slots=True)
class FakeResponse:
    """Return one synthetic HTTP response body.

    Attributes:
        payload: Raw response body returned by ``read``.

    """

    payload: bytes

    def read(self) -> bytes:
        """Return the configured response body.

        Returns:
            Configured raw response payload.

        """
        return self.payload

    def __enter__(self) -> Self:
        """Enter the synthetic response.

        Returns:
            This response instance.

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
            exc_type: Exception type raised inside the context, when present.
            exc_value: Exception instance raised inside the context, when
                present.
            traceback: Exception traceback raised inside the context, when
                present.

        """


@final
@dataclass(slots=True)
class FakeOpener:
    """Return queued bodies and capture MantleDB requests.

    Attributes:
        bodies: Queued raw response bodies.
        requests: MantleDB requests captured in call order.

    """

    bodies: list[bytes]
    requests: list[HttpRequest] = field(default_factory=list)

    def __call__(self, *, request: HttpRequest, timeout: float) -> UrlResponse:
        """Capture one request and return its synthetic response.

        Args:
            request: MantleDB request to capture.
            timeout: Request timeout accepted by the opener contract.

        Returns:
            Synthetic response containing the next queued body.

        """
        del timeout
        self.requests.append(request)
        return FakeResponse(payload=self.bodies.pop(0))


@final
@dataclass(slots=True)
class FakeWakeStore:
    """Return one deterministic signed command and capture responses.

    Attributes:
        command: Signed wake command returned to the watcher.
        responses: Ready responses captured in publication order.

    """

    command: WakeCommand
    responses: list[WakeResponse] = field(default_factory=list)

    def retrieve_command(self) -> WakeCommand:
        """Return the configured command.

        Returns:
            Configured wake command.

        """
        return self.command

    def publish_response(self, *, response: WakeResponse) -> None:
        """Capture a ready response.

        Args:
            response: Ready response to append.

        """
        self.responses.append(response)


@final
@dataclass(slots=True)
class FakeLauncher:
    """Record service launch requests.

    Attributes:
        calls: Number of service launch requests received.

    """

    calls: int = 0

    async def start_and_resolve(self) -> str:
        """Return one deterministic MCP URL.

        Returns:
            Fixed public MCP endpoint.

        """
        self.calls += 1
        return "https://service.example/mcp"


def _command(
    *,
    key: str,
    identifier: UUID,
    issued_at: int,
) -> dict[str, int | str]:
    """Build one correctly signed wake command document.

    Args:
        key: HMAC signing key.
        identifier: Wake request UUID.
        issued_at: Unix timestamp for the request.

    Returns:
        MantleDB-compatible signed command document.

    """
    command: WakeCommand = WakeCommand(
        identifier=identifier,
        issued_at=issued_at,
    )
    return {
        "id": command.text,
        "issued_at": issued_at,
        "signature": command.signature(key=key),
    }


def test_signed_command_is_verified_and_ready_response_is_bound() -> None:
    """Only the matching fresh signed command produces a signed response."""
    signing_key: str = "wake-only-test-key"
    issued_at: int = 2_000_000_000
    identifier: UUID = UUID(hex="550e8400-e29b-41d4-a716-446655440000")
    opener: FakeOpener = FakeOpener(
        bodies=[
            dumps(
                obj=_command(
                    key=signing_key,
                    identifier=identifier,
                    issued_at=issued_at,
                ),
            ).encode(encoding="utf-8"),
            b"",
        ],
    )
    store: MantleWakeStore = MantleWakeStore(
        namespace="Exactus wake",
        signing_key=signing_key,
        opener=opener,
    )
    command: WakeCommand = store.retrieve_command(
        current_time=float(issued_at),
    )
    response: WakeResponse = WakeResponse(
        identifier=command.identifier,
        url="https://service.example/mcp",
    )
    store.publish_response(response=response)
    expect_equal(actual=command.identifier, expected=identifier)
    expect_equal(
        actual=opener.requests[0].url,
        expected=("https://mantledb.sh/v2/Exactus%20wake/wake/command"),
    )
    response_body: bytes = require_type(
        value=opener.requests[1].data,
        kind=bytes,
    )
    response_text: str = response_body.decode(encoding="utf-8")
    expect_in(
        member=response.signature(key=signing_key),
        container=response_text,
    )


def test_stale_command_is_rejected() -> None:
    """A valid signature cannot be replayed outside the freshness window."""
    signing_key: str = "wake-only-test-key"
    issued_at: int = 2_000_000_000
    identifier: UUID = UUID(hex="550e8400-e29b-41d4-a716-446655440000")
    opener: FakeOpener = FakeOpener(
        bodies=[
            dumps(
                obj=_command(
                    key=signing_key,
                    identifier=identifier,
                    issued_at=issued_at,
                ),
            ).encode(encoding="utf-8"),
        ],
    )
    store: MantleWakeStore = MantleWakeStore(
        namespace="Exactus wake",
        signing_key=signing_key,
        maximum_age=30.0,
        opener=opener,
    )
    with pytest.raises(
        expected_exception=WakeError,
        match="outside the replay window",
    ):
        _ = store.retrieve_command(current_time=float(issued_at + 31))


def test_watcher_deduplicates_completed_uuid(tmp_path: Path) -> None:
    """One UUID starts the fixed service no more than once.

    Args:
        tmp_path: Temporary directory for watcher replay state.

    """
    command: WakeCommand = WakeCommand(
        identifier=UUID(hex="550e8400-e29b-41d4-a716-446655440000"),
        issued_at=2_000_000_000,
    )
    store: FakeWakeStore = FakeWakeStore(command=command)
    launcher: FakeLauncher = FakeLauncher()
    state: WakeStateStore = WakeStateStore(path=tmp_path / "last-id")
    watcher: WakeWatcher = WakeWatcher(
        store=store,
        state=state,
        launcher=launcher,
    )
    first_result: bool = run(main=watcher.poll_once())
    second_result: bool = run(main=watcher.poll_once())
    expect_equal(actual=first_result, expected=True)
    expect_equal(actual=second_result, expected=False)
    expect_equal(actual=launcher.calls, expected=1)
    expect_equal(
        actual=store.responses,
        expected=[
            WakeResponse(
                identifier=command.identifier,
                url="https://service.example/mcp",
            ),
        ],
    )


def test_keep_running_starts_service_before_duplicate_check(
    tmp_path: Path,
) -> None:
    """Remote mode supervises the service even without a fresh wake UUID.

    Args:
        tmp_path: Temporary directory for watcher replay state.

    """
    command: WakeCommand = WakeCommand(
        identifier=UUID(hex="550e8400-e29b-41d4-a716-446655440000"),
        issued_at=2_000_000_000,
    )
    store: FakeWakeStore = FakeWakeStore(command=command)
    launcher: FakeLauncher = FakeLauncher()
    state: WakeStateStore = WakeStateStore(path=tmp_path / "last-id")
    state.write(identifier=command.identifier)
    watcher: WakeWatcher = WakeWatcher(
        store=store,
        state=state,
        launcher=launcher,
        keep_service_running=True,
    )
    result: bool = run(main=watcher.poll_once())
    expect_equal(actual=result, expected=False)
    expect_equal(actual=launcher.calls, expected=1)
    expect_equal(actual=store.responses, expected=[])


def test_discovered_origin_gets_mcp_path() -> None:
    """Normalize an emitted public origin to the MCP endpoint."""
    launcher: WakeServiceLauncher = WakeServiceLauncher(
        command=("unused",),
        discovery_timeout=1.0,
    )
    expect_equal(
        actual=private_call(
            owner=launcher,
            name="_normalize_url",
            url="https://service.example/",
        ),
        expected="https://service.example/mcp",
    )


def test_wake_response_requires_absolute_https() -> None:
    """A wake response URL must be absolute, clean HTTPS."""
    identifier: UUID = UUID(hex="550e8400-e29b-41d4-a716-446655440000")
    for url in (
        "http://service.example/mcp",
        "https://user:secret@service.example/mcp",
        "https://service.example/mcp?token=x",
        "relative/path",
    ):
        with pytest.raises(expected_exception=ValueError, match="HTTPS"):
            _ = WakeResponse(identifier=identifier, url=url)


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ("[]", "must be an object"),
        ('{"id": 1}', "is incomplete"),
        (
            '{"id": "not-a-uuid", "issued_at": 1, "signature": "x"}',
            "UUID is invalid",
        ),
        (
            '{"id": "{550e8400-e29b-41d4-a716-446655440000}",'
            ' "issued_at": 1, "signature": "x"}',
            "canonical UUID v4",
        ),
        (
            '{"id": "550e8400-e29b-41d4-a716-446655440000",'
            ' "issued_at": 2000000000, "signature": "bogus"}',
            "signature is invalid",
        ),
    ],
)
def test_retrieve_command_rejects_malformed_documents(
    document: str,
    match: str,
) -> None:
    """Malformed, unsigned, or non-canonical commands are rejected.

    Args:
        document: Synthetic MantleDB response body.
        match: Expected rejection text.

    """
    opener: FakeOpener = FakeOpener(bodies=[document.encode(encoding="utf-8")])
    store: MantleWakeStore = MantleWakeStore(
        namespace="Exactus wake",
        signing_key="wake-only-test-key",
        opener=opener,
    )
    with pytest.raises(expected_exception=WakeError, match=match):
        _ = store.retrieve_command(current_time=2_000_000_000.0)


def test_transport_failures_surface_as_wake_errors() -> None:
    """Transport and JSON failures become ``WakeError`` reports."""

    def failing_opener(*, request: HttpRequest, timeout: float) -> UrlResponse:
        """Simulate a failing MantleDB transport.

        Args:
            request: Unused request.
            timeout: Unused timeout.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            URLError: Always.

        """
        del request, timeout
        msg: str = "offline"
        raise URLError(reason=msg)

    store: MantleWakeStore = MantleWakeStore(
        namespace="Exactus wake",
        signing_key="wake-only-test-key",
        opener=failing_opener,
    )
    with pytest.raises(expected_exception=WakeError, match="retrieve"):
        _ = store.retrieve_command(current_time=2_000_000_000.0)
    response: WakeResponse = WakeResponse(
        identifier=UUID(hex="550e8400-e29b-41d4-a716-446655440000"),
        url="https://service.example/mcp",
    )
    with pytest.raises(expected_exception=WakeError, match="publish"):
        store.publish_response(response=response)
    garbage: MantleWakeStore = MantleWakeStore(
        namespace="Exactus wake",
        signing_key="wake-only-test-key",
        opener=FakeOpener(bodies=[b"not-json"]),
    )
    with pytest.raises(expected_exception=WakeError, match="JSON"):
        _ = garbage.retrieve_command(current_time=2_000_000_000.0)


def test_state_store_roundtrip_and_invalid_content(tmp_path: Path) -> None:
    """Persisted UUIDs round-trip; absent or invalid state is empty.

    Args:
        tmp_path: Isolated state directory.

    """
    state: WakeStateStore = WakeStateStore(path=tmp_path / "last-id")
    expect_equal(actual=state.read(), expected=None)
    identifier: UUID = UUID(hex="550e8400-e29b-41d4-a716-446655440000")
    state.write(identifier=identifier)
    expect_equal(actual=state.read(), expected=identifier)
    _ = state.path.write_text(data="   \n", encoding="utf-8")
    expect_equal(actual=state.read(), expected=None)
    _ = state.path.write_text(data="not-a-uuid", encoding="utf-8")
    expect_equal(actual=state.read(), expected=None)


def test_launcher_rejects_invalid_startup_settings() -> None:
    """Empty commands, bad timeouts, and bad paths are rejected."""
    with pytest.raises(expected_exception=ValueError, match="empty"):
        _ = WakeServiceLauncher(command=(), discovery_timeout=1.0)
    with pytest.raises(expected_exception=ValueError, match="positive"):
        _ = WakeServiceLauncher(command=("service",), discovery_timeout=0.0)
    with pytest.raises(expected_exception=ValueError, match="start with"):
        _ = WakeServiceLauncher(
            command=("service",),
            discovery_timeout=1.0,
            mcp_path="mcp",
        )


@final
class FakeStdout:
    """Queue output lines for a synthetic child process.

    Attributes:
        _lines: Remaining scripted output lines.
        _hang: Whether reads block forever.

    """

    def __init__(self, *, lines: list[bytes], hang: bool = False) -> None:
        """Configure scripted output.

        Args:
            lines: Queued output lines.
            hang: Whether reads block forever.

        """
        self._lines: list[bytes] = list(lines)
        self._hang: bool = hang

    async def readline(self) -> bytes:
        """Return the next scripted line or end-of-file.

        Returns:
            Scripted line bytes, or empty bytes at end-of-file.

        """
        if self._hang:
            _ = await AsyncEvent().wait()
        if not self._lines:
            return b""
        return self._lines.pop(0)


@final
class FakeProcess:
    """Child-process double with scripted output and exit behavior.

    Attributes:
        returncode: Process exit status once terminated.
        stdout: Scripted combined output stream.
        terminated: Whether ``terminate`` was requested.
        killed: Whether ``kill`` was requested.

    """

    def __init__(
        self,
        *,
        lines: list[bytes] | None,
        code: int = 0,
        hang_wait: bool = False,
    ) -> None:
        """Configure scripted process behavior.

        Args:
            lines: Scripted output lines; ``None`` removes ``stdout``.
            code: Exit status reported after termination.
            hang_wait: Whether ``wait`` blocks until ``kill``.

        """
        self.returncode: int | None = None
        self.stdout: FakeStdout | None = (
            None if lines is None else FakeStdout(lines=lines)
        )
        self._code: int = code
        self._hangs: bool = hang_wait
        self.terminated: bool = False
        self.killed: bool = False

    async def wait(self) -> int:
        """Block until termination and return the exit status.

        Returns:
            Scripted exit status.

        """
        if self._hangs:
            _ = await AsyncEvent().wait()
        if self.returncode is None:
            self.returncode = self._code
        return self.returncode

    def terminate(self) -> None:
        """Record termination and report the scripted exit status."""
        self.terminated = True
        if self.returncode is None:
            self.returncode = self._code

    def kill(self) -> None:
        """Record a forced kill and unblock pending waits."""
        self.killed = True
        self._hangs = False
        self.returncode = -9


def fake_exec_factory(
    *,
    process: FakeProcess,
    calls: list[tuple[object, ...]],
) -> Callable[..., Coroutine[object, object, FakeProcess]]:
    """Build a ``create_subprocess_exec`` double returning one process.

    Args:
        process: Process double returned by each call.
        calls: List recording invocation arguments.

    Returns:
        Async subprocess factory double.

    """

    async def fake_exec(*args: object, **kwargs: object) -> FakeProcess:
        """Record the invocation and return the process double.

        Args:
            *args: Recorded positional arguments.
            **kwargs: Recorded keyword arguments.

        Returns:
            Configured process double.

        """
        del kwargs
        calls.append(args)
        return process

    return fake_exec


def test_launcher_discovers_url_and_reuses_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A launched service publishes its URL once and stays running.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    wakeup_module: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.wakeup",
    )
    process: FakeProcess = FakeProcess(
        lines=[b"booting\n", b"MCP endpoint: https://demo.example/\n"],
    )
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        target=wakeup_module,
        name="create_subprocess_exec",
        value=fake_exec_factory(process=process, calls=calls),
    )
    launcher: WakeServiceLauncher = WakeServiceLauncher(
        command=("service",),
        discovery_timeout=5.0,
    )
    url: str = run(main=launcher.start_and_resolve())
    expect_equal(actual=url, expected="https://demo.example/mcp")
    expect_true(condition=launcher.running)
    again: str = run(main=launcher.start_and_resolve())
    expect_equal(actual=again, expected=url)
    expect_equal(actual=len(calls), expected=1)
    run(main=launcher.close())
    expect_true(condition=process.terminated)
    expect_true(condition=not launcher.running)
    run(main=launcher.close())


def test_launcher_reports_discovery_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing output, early exit, and timeouts become ``WakeError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    wakeup_module: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.wakeup",
    )
    calls: list[tuple[object, ...]] = []
    process_holder: list[FakeProcess] = []

    def launch(*, process: FakeProcess, timeout: float = 5.0) -> None:
        """Start one launcher against a scripted process.

        Args:
            process: Scripted process double.
            timeout: Discovery timeout for the launcher.

        """
        process_holder.clear()
        process_holder.append(process)
        monkeypatch.setattr(
            target=wakeup_module,
            name="create_subprocess_exec",
            value=fake_exec_factory(process=process, calls=calls),
        )
        launcher: WakeServiceLauncher = WakeServiceLauncher(
            command=("service",),
            discovery_timeout=timeout,
        )
        run(main=launcher.start_and_resolve())

    hanging: FakeProcess = FakeProcess(lines=[b"never\n"])
    hanging.stdout = FakeStdout(lines=[], hang=True)
    with pytest.raises(expected_exception=WakeError, match="capture"):
        launch(process=FakeProcess(lines=None))
    with pytest.raises(expected_exception=WakeError, match="exited before"):
        launch(process=FakeProcess(lines=[], code=3))
    with pytest.raises(expected_exception=WakeError, match="Timed out"):
        launch(process=hanging, timeout=0.02)


def test_launcher_close_kills_unresponsive_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child ignoring ``terminate`` is killed after the grace period.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    wakeup_module: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.wakeup",
    )
    process: FakeProcess = FakeProcess(
        lines=[b"MCP endpoint: https://demo.example/\n"],
        hang_wait=True,
    )
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        target=wakeup_module,
        name="create_subprocess_exec",
        value=fake_exec_factory(process=process, calls=calls),
    )
    monkeypatch.setattr(
        target=wakeup_module.Constants,
        name="process_stop_timeout",
        value=0.02,
    )
    launcher: WakeServiceLauncher = WakeServiceLauncher(
        command=("service",),
        discovery_timeout=5.0,
    )
    _ = run(main=launcher.start_and_resolve())
    run(main=launcher.close())
    expect_true(condition=process.terminated)
    expect_true(condition=process.killed)


def test_watcher_run_retries_with_backoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Polling failures are logged and retried with doubled delays.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated state directory.

    """
    wakeup_module: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.wakeup",
    )
    delays: list[float] = []

    async def fake_sleep(*, delay: float) -> None:
        """Record backoff delays and stop after two retries.

        Args:
            delay: Requested sleep delay.

        Raises:
            RuntimeError: After the second recorded delay.

        """
        delays.append(delay)
        if len(delays) > 1:
            msg: str = "stop"
            raise RuntimeError(msg)

    stream: StringIO = StringIO()
    monkeypatch.setattr(target=wakeup_module, name="sleep", value=fake_sleep)
    monkeypatch.setattr(target=wakeup_module, name="stderr", value=stream)

    class FailingStore:
        """Store double whose command retrieval always fails."""

        @staticmethod
        def retrieve_command() -> WakeCommand:
            """Fail retrieval deterministically.

            Raises:
                WakeError: Always.

            """
            msg: str = "boom"
            raise WakeError(msg)

        @staticmethod
        def publish_response(*, response: WakeResponse) -> None:
            """Reject unused responses.

            Args:
                response: Unused ready response.

            """
            del response

    watcher: WakeWatcher = WakeWatcher(
        store=FailingStore(),
        state=WakeStateStore(path=tmp_path / "last-id"),
        launcher=FakeLauncher(),
        poll_interval=1.0,
    )
    with pytest.raises(expected_exception=RuntimeError, match="stop"):
        run(main=watcher.run())
    expect_equal(actual=delays, expected=[2.0, 4.0])
    expect_in(member="exactus-mcp-wakeup: boom", container=stream.getvalue())
