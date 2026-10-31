# Copyright (c) 2026 João Lopes.
"""Detached runner for Python ProcessClass executors."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from importlib import import_module
from json import dumps, loads
from operator import attrgetter
from os import getpid
from os import kill as os_kill
from secrets import compare_digest
from signal import SIGCONT, SIGHUP, SIGINT, SIGSTOP, SIGTERM, SIGUSR1, signal
from socket import (
    AF_INET,
    SO_REUSEADDR,
    SOCK_STREAM,
    SOL_SOCKET,
    create_connection,
    socket,
)
from sys import argv
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType, ModuleType

    from exactus.packages.pmanager.model import ModelValue
from exactus.packages.pmanager.lifecycle import Lifecycle, ProcessClass


def _resolve(module_name: str, qualname: str) -> type[ProcessClass]:
    """Resolve.

    Args:
        module_name: Module name.
        qualname: Qualname.

    Raises:
        TypeError: When the operation cannot complete.

    Returns:
        The resulting value.

    """
    value: ModuleType | type[ProcessClass] | object = import_module(
        name=module_name,
    )
    for part in qualname.split(sep="."):
        value = getattr(value, part)
    if not isinstance(value, type) or not issubclass(value, ProcessClass):
        msg: str = f"{module_name}.{qualname} is not a ProcessClass."
        raise TypeError(msg)
    return value


def _call_arguments(
    values: list[str],
) -> tuple[tuple[ModelValue, ...], dict[str, ModelValue]]:
    """Call arguments.

    Args:
        values: Values.

    Returns:
        The resulting value.

    """
    prefix: str = "--orchestrator-call="
    for value in values:
        if not value.startswith(prefix):
            continue
        raw: ModelValue = loads(s=value[len(prefix) :])
        if not isinstance(raw, dict):
            break
        args: ModelValue = raw.get("args", [])
        kwargs: ModelValue = raw.get("kwargs", {})
        if isinstance(args, list) and isinstance(kwargs, dict):
            return (tuple(args), dict(kwargs))
    return (tuple(values), {})


def _control_value(values: list[str], name: str) -> str | None:
    """Control value.

    Args:
        values: Values.
        name: Name.

    Returns:
        The resulting value.

    """
    prefix: str = f"--orchestrator-{name}="
    return next(
        (value[len(prefix) :] for value in values if value.startswith(prefix)),
        None,
    )


def _run_status_hook(hook: Callable[[], ModelValue]) -> ModelValue:
    """Invoke a status hook, translating failures into an error mapping.

    Args:
        hook: Hook.

    Returns:
        The hook result, or a mapping describing the hook failure.

    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future: Future[ModelValue] = pool.submit(hook)
        error: BaseException | None = future.exception()
        if error is None or not isinstance(error, Exception):
            return future.result()
        return {"status_hook_error": str(object=error)}


def _status_server(instance: ProcessClass, port: int, token: str) -> None:
    """Status server.

    Args:
        instance: Instance.
        port: Port.
        token: Token.

    """
    server: socket = socket(family=AF_INET, type=SOCK_STREAM)
    server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(4)
    while True:
        connection, _ = server.accept()
        with connection:
            raw: bytes = connection.recv(1048576)
            try:
                request: ModelValue = loads(s=raw.decode())
            except ValueError:
                request = {}
            request_token: ModelValue = (
                request.get("token") if isinstance(request, dict) else None
            )
            valid: bool = isinstance(request_token, str) and compare_digest(
                token,
                request_token,
            )
            response: ModelValue = {}
            if valid:
                hook: Callable[[], ModelValue] | None = (
                    instance.lifecycle_hook(lifecycle=Lifecycle.STATUS)
                )
                if hook is not None:
                    response = _run_status_hook(hook=hook)
            try:
                payload: bytes = dumps(obj=response).encode() + b"\n"
            except (TypeError, ValueError):
                payload = (
                    dumps(
                        obj={
                            "status_hook_error": (
                                "@status result is not JSON serializable."
                            ),
                        },
                    ).encode()
                    + b"\n"
                )
            connection.sendall(payload)


def _broadcast_sender(
    port: int,
    token: str,
) -> Callable[[str, ModelValue, str], int]:
    """Broadcast sender.

    Args:
        port: Port.
        token: Token.

    Returns:
        The resulting value.

    """

    def send(topic: str, payload: ModelValue, scope: str) -> int:
        """Send.

        Args:
            topic: Topic.
            payload: Payload.
            scope: Scope.

        Returns:
            The resulting value.

        """
        request: dict[str, ModelValue] = {
            "protocol": 2,
            "token": token,
            "command": "broadcast",
            "payload": {"topic": topic, "payload": payload, "scope": scope},
        }
        try:
            with create_connection(
                timeout=1.0,
                address=("127.0.0.1", port),
            ) as connection:
                connection.sendall((dumps(obj=request) + "\n").encode())
                data: bytes = connection.recv(1048576)
            response: ModelValue = loads(
                s=data.split(sep=b"\n", maxsplit=1)[0].decode(),
            )
        except (OSError, ValueError, TypeError):
            return 0
        if not isinstance(response, dict):
            return 0
        delivered: ModelValue = response.get("delivered", 0)
        return delivered if isinstance(delivered, int) else 0

    return send


def _event_receiver(instance: ProcessClass, port: int, token: str) -> None:
    """Event receiver.

    Args:
        instance: Instance.
        port: Port.
        token: Token.

    """
    cursor: int = 0
    while True:
        request: dict[str, ModelValue] = {
            "protocol": 2,
            "token": token,
            "command": "events",
            "payload": {"after": cursor},
        }
        try:
            with create_connection(
                timeout=1.0,
                address=("127.0.0.1", port),
            ) as connection:
                connection.sendall((dumps(obj=request) + "\n").encode())
                data: bytes = connection.recv(1048576)
            response: ModelValue = loads(
                s=data.split(sep=b"\n", maxsplit=1)[0].decode(),
            )
            if isinstance(response, dict):
                events: ModelValue = response.get("events", [])
                if isinstance(events, list):
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        event_id: ModelValue = event.get("id")
                        topic: ModelValue = event.get("topic")
                        if isinstance(event_id, int):
                            cursor = max(cursor, event_id)
                        if isinstance(topic, str):
                            instance.receive_broadcast(
                                topic=topic,
                                payload=event.get("payload"),
                            )
        except (OSError, ValueError, TypeError):
            pass
        sleep(0.1)


def main() -> int:
    """Run the command-line entry point.

    Returns:
        The resulting value.

    """
    if len(argv) < len(("runner", "module", "class")):
        return 2
    cls: type[ProcessClass] = _resolve(module_name=argv[1], qualname=argv[2])
    instance: ProcessClass = cls()
    worker_port: str | None = _control_value(
        values=argv[3:],
        name="worker-port",
    )
    worker_token: str | None = _control_value(
        values=argv[3:],
        name="worker-token",
    )
    if worker_port is not None and worker_token is not None:
        instance.configure_broadcast(
            sender=_broadcast_sender(
                port=int(worker_port),
                token=worker_token,
            ),
        )
        Thread(
            target=_event_receiver,
            args=(instance, int(worker_port), worker_token),
            daemon=True,
        ).start()
    port_value: str | None = _control_value(
        values=argv[3:],
        name="control-port",
    )
    token: str | None = _control_value(values=argv[3:], name="control-token")
    if port_value is not None and token is not None:
        Thread(
            target=_status_server,
            args=(instance, int(port_value), token),
            daemon=True,
        ).start()

    def finish(lifecycle: Lifecycle) -> None:
        """Finish.

        Args:
            lifecycle: Lifecycle.

        Raises:
            SystemExit: When the operation cannot complete.

        """
        instance.invoke_lifecycle(lifecycle=lifecycle)
        raise SystemExit(0)

    signal(
        signalnum=SIGTERM,
        handler=lambda _signal, _frame: finish(lifecycle=Lifecycle.KILL),
    )
    signal(
        signalnum=SIGINT,
        handler=lambda _signal, _frame: finish(lifecycle=Lifecycle.CANCEL),
    )
    signal(
        signalnum=SIGHUP,
        handler=lambda _signal, _frame: finish(lifecycle=Lifecycle.RESET),
    )

    def suspend(_signal: int, _frame: FrameType | None) -> None:
        """Suspend.

        Args:
            _signal: Signal.
            _frame: Frame.

        """
        instance.invoke_lifecycle(lifecycle=Lifecycle.PAUSE)
        os_kill(getpid(), SIGSTOP)

    signal(signalnum=SIGUSR1, handler=suspend)
    signal(
        signalnum=SIGCONT,
        handler=lambda _signal, _frame: instance.invoke_lifecycle(
            lifecycle=Lifecycle.RESUME,
        ),
    )
    args, kwargs = _call_arguments(values=argv[3:])
    runner: Callable[..., ModelValue] = cast(
        typ="Callable[..., ModelValue]",
        val=attrgetter("run")(instance),
    )
    result: ModelValue = runner(*args, **kwargs)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
