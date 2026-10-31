# Copyright (c) 2026
"""Unit tests for the detached class-runner entry module."""

from __future__ import annotations

from json import dumps, loads
from signal import SIGCONT, SIGHUP, SIGINT, SIGSTOP, SIGTERM, SIGUSR1
from socket import AF_INET, SOCK_STREAM, create_connection, socket
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.packages.pmanager import class_runner as runner
from exactus.packages.pmanager.lifecycle import (
    Lifecycle,
    ProcessClass,
    process_name,
    receive,
    status,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    fail,
    private,
    private_call,
    require_type,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType
    from typing import Protocol

    from exactus.packages.pmanager.model import ModelValue

    class SignalHandler(Protocol):
        """Describe a signal handler callable with named parameters."""

        def __call__(self, *, _signal: int, _frame: FrameType | None) -> None:
            """Handle one signal."""


@final
class Constants:
    """Group module-level constants.

    Attributes:
        auth_tag: Grouped module constant.
        poll_interval: Grouped module constant.
        poll_timeout: Grouped module constant.

    """

    auth_tag: Final[str] = "secret"
    poll_interval: Final[float] = 0.05
    poll_timeout: Final[float] = 5.0


@process_name(name="runner-stub")
class RunnerStub(ProcessClass):
    """Recording worker used by the class-runner tests."""

    def __init__(self) -> None:
        """Init."""
        super().__init__()
        self.calls: list[
            tuple[tuple[ModelValue, ...], dict[str, ModelValue]]
        ] = []
        self.received: list[tuple[str, ModelValue]] = []

    @status
    def probe(self) -> dict[str, str]:
        """Report a fixed custom status payload.

        Returns:
            Status mapping returned by the status server.

        """
        self.received.append(("status", "probe"))
        return {"state": "ready"}

    @receive(topic="demo.topic")
    def on_demo(self, payload: ModelValue) -> None:
        """Record a demo broadcast event.

        Args:
            payload: Event payload.

        """
        self.received.append(("demo.topic", payload))

    def run(self, *args: ModelValue, **kwargs: ModelValue) -> int:
        """Record the invocation arguments and report success.

        Args:
            args: Positional workload arguments.
            kwargs: Keyword workload arguments.

        Returns:
            Process exit code.

        """
        self.calls.append((args, kwargs))
        return 0


class SignalRecorder:
    """Capture signal handler registrations without installing them."""

    def __init__(self) -> None:
        """Init."""
        self.handlers: dict[int, Callable[[int, FrameType | None], None]] = {}

    def emit(self, *, signalnum: int) -> None:
        """Invoke the recorded handler for a signal.

        Args:
            signalnum: Signal whose handler runs.

        """
        handler: SignalHandler = cast(
            typ="SignalHandler",
            val=self.handlers[signalnum],
        )
        handler(_signal=signalnum, _frame=None)

    def __call__(
        self,
        signalnum: int,
        handler: Callable[[int, FrameType | None], None],
    ) -> None:
        """Record one registration.

        Args:
            signalnum: Signal.
            handler: Handler.

        """
        self.handlers[signalnum] = handler


class ThreadStub:
    """Record thread construction without starting any work."""

    def __init__(
        self,
        *,
        target: Callable[..., ModelValue],
        args: tuple[ModelValue, ...] = (),
        daemon: bool = False,
    ) -> None:
        """Init.

        Args:
            target: Target.
            args: Args.
            daemon: Daemon.

        """
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False

    def start(self) -> None:
        """Mark the thread as started without launching it."""
        self.started = True


def _free_port() -> int:
    """Pick an unused loopback TCP port.

    Returns:
        Port that was free when probed.

    """
    with socket(family=AF_INET, type=SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return require_type(value=probe.getsockname()[1], kind=int)


def _probe(*, port: int) -> bool:
    """Return whether a TCP connect to the port succeeds.

    Args:
        port: Server port.

    Returns:
        True when the port accepts connections.

    """
    try:
        with create_connection(timeout=0.2, address=("127.0.0.1", port)):
            return True
    except OSError:
        return False


def _await(predicate: Callable[[], bool]) -> None:
    """Poll a predicate until it holds or the timeout expires.

    Args:
        predicate: Condition checked each poll interval.

    """
    deadline: float = monotonic() + Constants.poll_timeout
    while not predicate():
        if monotonic() > deadline:
            fail(message="Timed out waiting for condition.")
        sleep(Constants.poll_interval)


def _request(*, port: int, payload: str) -> ModelValue:
    """Send one JSON request and decode the first response line.

    Args:
        port: Server port.
        payload: Raw JSON payload.

    Returns:
        Decoded response value.

    """
    with create_connection(
        timeout=Constants.poll_timeout,
        address=("127.0.0.1", port),
    ) as connection:
        connection.sendall(payload.encode())
        data: bytes = connection.recv(1048576)
    return loads(s=data.split(sep=b"\n", maxsplit=1)[0].decode())


def _returns_ok() -> ModelValue:
    """Return a fixed status payload.

    Returns:
        Status mapping.

    """
    return {"state": "ok"}


def _raise_hook() -> ModelValue:
    """Fail as a status hook would.

    Returns:
        Never reached; the function always raises.

    Raises:
        RuntimeError: Always.

    """
    msg: str = "hook failed"
    raise RuntimeError(msg)


def _control_value(*, values: list[str], name: str) -> ModelValue:
    """Read an ``--orchestrator-<name>=`` value through the private helper.

    Args:
        values: Argument vector.
        name: Control name.

    Returns:
        The configured value or ``None``.

    """
    control: Callable[[list[str], str], ModelValue] = cast(
        typ="Callable[[list[str], str], ModelValue]",
        val=private(owner=runner, name="_control_value"),
    )
    return control(values, name)


def _make_threads(*, threads: list[ThreadStub]) -> Callable[..., ThreadStub]:
    """Return a ``Thread`` replacement recording into ``threads``.

    Args:
        threads: Recording list.

    Returns:
        Callable matching the ``Thread`` keyword constructor.

    """

    def make(**kwargs: ModelValue) -> ThreadStub:
        """Record a thread construction.

        Args:
            kwargs: ``Thread`` constructor arguments.

        Returns:
            Recorded stub thread.

        """
        thread: ThreadStub = ThreadStub(
            target=cast(
                typ="Callable[..., ModelValue]",
                val=kwargs.get("target"),
            ),
            args=cast(
                typ="tuple[ModelValue, ...]",
                val=kwargs.get("args", ()),
            ),
            daemon=kwargs.get("daemon", False) is True,
        )
        threads.append(thread)
        return thread

    return make


def test_resolve_returns_process_class() -> None:
    """A ProcessClass qualname resolves to the class object."""
    resolved: type[ProcessClass] = cast(
        typ="type[ProcessClass]",
        val=private_call(
            owner=runner,
            name="_resolve",
            module_name="exactus.tests.packages.pmanager.test_class_runner",
            qualname="RunnerStub",
        ),
    )
    expect_true(condition=resolved is RunnerStub)


def test_resolve_rejects_non_process_class() -> None:
    """A non-ProcessClass attribute raises ``TypeError``."""
    with pytest.raises(expected_exception=TypeError, match="ProcessClass"):
        _ = private_call(
            owner=runner,
            name="_resolve",
            module_name="exactus.tests.packages.pmanager.test_class_runner",
            qualname="Constants",
        )


def _call_arguments(
    *,
    values: list[str],
) -> tuple[tuple[ModelValue, ...], dict[str, ModelValue]]:
    """Parse orchestrator call arguments through the private helper.

    Args:
        values: Argument vector.

    Returns:
        Positional and keyword call arguments.

    """
    return cast(
        typ="tuple[tuple[ModelValue, ...], dict[str, ModelValue]]",
        val=private_call(owner=runner, name="_call_arguments", values=values),
    )


def test_call_arguments_plain_values() -> None:
    """Without the call marker, argv passes through positionally."""
    expected: tuple[tuple[ModelValue, ...], dict[str, ModelValue]] = (
        ("a", "b"),
        {},
    )
    expect_equal(actual=_call_arguments(values=["a", "b"]), expected=expected)


def test_call_arguments_parses_orchestrator_call() -> None:
    """The ``--orchestrator-call`` JSON supplies args and kwargs."""
    encoded: str = dumps(obj={"args": [1, "x"], "kwargs": {"k": True}})
    expect_equal(
        actual=_call_arguments(values=[f"--orchestrator-call={encoded}"]),
        expected=((1, "x"), {"k": True}),
    )


def test_call_arguments_ignores_non_mapping() -> None:
    """A non-object call payload falls back to positional argv."""
    expected: tuple[tuple[ModelValue, ...], dict[str, ModelValue]] = (
        ("--orchestrator-call=[1, 2]",),
        {},
    )
    expect_equal(
        actual=_call_arguments(values=["--orchestrator-call=[1, 2]"]),
        expected=expected,
    )


def test_call_arguments_rejects_bad_members() -> None:
    """Non-list args or non-mapping kwargs fall back to argv."""
    encoded: str = dumps(obj={"args": "x", "kwargs": {}})
    expected: tuple[tuple[ModelValue, ...], dict[str, ModelValue]] = (
        (f"--orchestrator-call={encoded}",),
        {},
    )
    expect_equal(
        actual=_call_arguments(values=[f"--orchestrator-call={encoded}"]),
        expected=expected,
    )


def test_control_value() -> None:
    """``--orchestrator-<name>=`` values resolve or return ``None``."""
    values: list[str] = ["--orchestrator-worker-port=1234", "plain"]
    expect_equal(
        actual=_control_value(values=values, name="worker-port"),
        expected="1234",
    )
    expect_equal(
        actual=_control_value(values=values, name="control-token"),
        expected=None,
    )


def test_run_status_hook_returns_result() -> None:
    """A successful hook returns its model value."""
    expect_equal(
        actual=private_call(
            owner=runner,
            name="_run_status_hook",
            hook=_returns_ok,
        ),
        expected={"state": "ok"},
    )


def test_run_status_hook_translates_errors() -> None:
    """A failing hook yields an error mapping instead of raising."""
    result: dict[str, ModelValue] = cast(
        typ="dict[str, ModelValue]",
        val=private_call(
            owner=runner,
            name="_run_status_hook",
            hook=_raise_hook,
        ),
    )
    expect_in(member="status_hook_error", container=result)


def _serve_status(*, instance: ProcessClass, port: int, token: str) -> None:
    """Start the private status server on a daemon thread.

    Args:
        instance: Process instance.
        port: Port.
        token: Token.

    """
    Thread(
        target=cast(
            typ="Callable[[], None]",
            val=private(owner=runner, name="_status_server"),
        ),
        args=(instance, port, token),
        daemon=True,
    ).start()

    def ready() -> bool:
        """Return whether the status port accepts connections.

        Returns:
            True once the server is listening.

        """
        return _probe(port=port)

    _await(predicate=ready)


def test_status_server_answers_requests() -> None:
    """The status server authenticates and serves hook payloads."""
    token: str = Constants.auth_tag
    port: int = _free_port()
    _serve_status(instance=RunnerStub(), port=port, token=token)
    denied: ModelValue = _request(
        port=port,
        payload=dumps(obj={"token": "wrong"}),
    )
    expect_equal(actual=denied, expected={})
    invalid: ModelValue = _request(port=port, payload="not json")
    expect_equal(actual=invalid, expected={})
    granted: ModelValue = _request(
        port=port,
        payload=dumps(obj={"token": token}),
    )
    expect_equal(actual=granted, expected={"state": "ready"})


def test_status_server_reports_non_serializable() -> None:
    """A non-JSON hook result yields the serialization error payload."""

    class NotJsonWorker(ProcessClass):
        """Worker whose status hook returns a non-JSON value."""

        @status
        def bad(self) -> ModelValue:
            """Return a set containing ``self``, which JSON cannot encode.

            Returns:
                Unserializable marker.

            """
            return cast(typ="ModelValue", val={self})

    token: str = Constants.auth_tag
    port: int = _free_port()
    _serve_status(instance=NotJsonWorker(), port=port, token=token)
    response: ModelValue = _request(
        port=port,
        payload=dumps(obj={"token": token}),
    )
    expect_equal(
        actual=response,
        expected={
            "status_hook_error": "@status result is not JSON serializable.",
        },
    )


def _broadcast_sender(
    *,
    port: int,
    token: str,
) -> Callable[[str, ModelValue, str], int]:
    """Build the private broadcast sender through reflection.

    Args:
        port: Port.
        token: Token.

    Returns:
        Bound send callable.

    """
    return cast(
        typ="Callable[[str, ModelValue, str], int]",
        val=private_call(
            owner=runner,
            name="_broadcast_sender",
            port=port,
            token=token,
        ),
    )


def test_broadcast_sender_delivers() -> None:
    """The sender posts the broadcast and returns its delivery count."""
    listener: socket = socket(family=AF_INET, type=SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port: int = require_type(value=listener.getsockname()[1], kind=int)

    def serve_once() -> None:
        """Answer a single broadcast request with ``delivered: 2``."""
        connection, _ = listener.accept()
        with connection:
            _ = connection.recv(1048576)
            connection.sendall(b'{"delivered": 2}\n')

    server: Thread = Thread(target=serve_once, daemon=True)
    server.start()
    send: Callable[[str, ModelValue, str], int] = _broadcast_sender(
        port=port,
        token=Constants.auth_tag,
    )
    delivered: int = send("topic", {"k": 1}, "context")
    server.join(timeout=Constants.poll_timeout)
    listener.close()
    expect_equal(actual=delivered, expected=2)


def test_broadcast_sender_fails_closed() -> None:
    """An unreachable orchestrator reports zero deliveries."""
    send: Callable[[str, ModelValue, str], int] = _broadcast_sender(
        port=_free_port(),
        token=Constants.auth_tag,
    )
    expect_equal(actual=send("topic", None, "context"), expected=0)


def test_event_receiver_dispatches() -> None:
    """The receiver polls the events endpoint and dispatches topics."""
    instance: RunnerStub = RunnerStub()
    listener: socket = socket(family=AF_INET, type=SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    port: int = require_type(value=listener.getsockname()[1], kind=int)
    served: list[bool] = [False]

    def serve_events() -> None:
        """Answer polls, delivering one demo event on the first."""
        for _ in range(50):
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            with connection:
                _ = connection.recv(1048576)
                if served[0]:
                    connection.sendall(b'{"events": []}\n')
                    continue
                served[0] = True
                connection.sendall(
                    b'{"events": [{"id": 1, "topic": "demo.topic",'
                    b' "payload": {"n": 1}}]}\n',
                )

    def received() -> bool:
        """Return whether the demo event arrived.

        Returns:
            True once ``instance.received`` holds an entry.

        """
        return bool(instance.received)

    server: Thread = Thread(target=serve_events, daemon=True)
    server.start()
    Thread(
        target=cast(
            typ="Callable[[], None]",
            val=private(owner=runner, name="_event_receiver"),
        ),
        args=(instance, port, "token"),
        daemon=True,
    ).start()
    _await(predicate=received)
    listener.close()
    expect_equal(actual=instance.received, expected=[("demo.topic", {"n": 1})])


def test_main_requires_module_and_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing ``module class`` arguments exit with usage status.

    Args:
        monkeypatch: Replaces the module argv binding.

    """
    monkeypatch.setattr(target=runner, name="argv", value=["runner"])
    expect_equal(actual=runner.main(), expected=2)


def test_main_runs_class_with_orchestrator_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner wires broadcast/status threads, signals, and argv.

    Args:
        monkeypatch: Replaces argv, signal, thread, and kill hooks.

    """
    signals: SignalRecorder = SignalRecorder()
    threads: list[ThreadStub] = []
    killed: list[tuple[int, int]] = []

    def record_kill(pid: int, sig: int) -> None:
        """Record a ``kill`` call.

        Args:
            pid: Process id.
            sig: Signal.

        """
        killed.append((pid, sig))

    monkeypatch.setattr(target=runner, name="signal", value=signals)
    monkeypatch.setattr(target=runner, name="os_kill", value=record_kill)
    monkeypatch.setattr(
        target=runner,
        name="Thread",
        value=_make_threads(threads=threads),
    )
    encoded: str = dumps(obj={"args": [3], "kwargs": {"name": "demo"}})
    monkeypatch.setattr(
        target=runner,
        name="argv",
        value=[
            "runner",
            "exactus.tests.packages.pmanager.test_class_runner",
            "RunnerStub",
            f"--orchestrator-call={encoded}",
            "--orchestrator-worker-port=1",
            "--orchestrator-worker-token=t",
            "--orchestrator-control-port=2",
            "--orchestrator-control-token=x",
        ],
    )
    expect_equal(actual=runner.main(), expected=0)
    expect_equal(actual=len(threads), expected=2)
    expect_true(condition=all(thread.started for thread in threads))
    expect_in(member=SIGTERM, container=signals.handlers)
    expect_in(member=SIGINT, container=signals.handlers)
    expect_in(member=SIGHUP, container=signals.handlers)
    expect_in(member=SIGUSR1, container=signals.handlers)
    expect_in(member=SIGCONT, container=signals.handlers)


def test_signal_handlers_invoke_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signal handlers drive pause/kill/cancel/reset/resume hooks.

    Args:
        monkeypatch: Replaces argv, signal, and kill hooks.

    """
    lifecycle_calls: list[Lifecycle] = []
    original_invoke: Callable[..., bool] = ProcessClass.invoke_lifecycle

    def record_invoke(
        self: ProcessClass,
        lifecycle: Lifecycle,
        timeout: float | None = None,
    ) -> bool:
        """Record the lifecycle and invoke the real hook.

        Args:
            self: Instance.
            lifecycle: Lifecycle.
            timeout: Timeout.

        Returns:
            The resulting value.

        """
        lifecycle_calls.append(lifecycle)
        return original_invoke(self=self, lifecycle=lifecycle, timeout=timeout)

    killed: list[int] = []

    def record_kill(_pid: int, sig: int) -> None:
        """Record a ``kill`` call.

        Args:
            _pid: Process id (unused).
            sig: Signal.

        """
        killed.append(sig)

    monkeypatch.setattr(
        target=ProcessClass,
        name="invoke_lifecycle",
        value=record_invoke,
    )
    signals: SignalRecorder = SignalRecorder()
    monkeypatch.setattr(target=runner, name="signal", value=signals)
    monkeypatch.setattr(target=runner, name="os_kill", value=record_kill)
    monkeypatch.setattr(
        target=runner,
        name="argv",
        value=[
            "runner",
            "exactus.tests.packages.pmanager.test_class_runner",
            "RunnerStub",
        ],
    )
    expect_equal(actual=runner.main(), expected=0)
    with pytest.raises(expected_exception=SystemExit) as caught:
        signals.emit(signalnum=SIGTERM)
    expect_equal(actual=caught.value.code, expected=0)
    with pytest.raises(expected_exception=SystemExit):
        signals.emit(signalnum=SIGINT)
    with pytest.raises(expected_exception=SystemExit):
        signals.emit(signalnum=SIGHUP)
    signals.emit(signalnum=SIGUSR1)
    signals.emit(signalnum=SIGCONT)
    expect_equal(actual=killed, expected=[SIGSTOP])
    expect_true(
        condition={
            Lifecycle.KILL,
            Lifecycle.CANCEL,
            Lifecycle.RESET,
            Lifecycle.PAUSE,
            Lifecycle.RESUME,
        }
        <= set(lifecycle_calls),
    )
