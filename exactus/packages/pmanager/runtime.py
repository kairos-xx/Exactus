# Copyright (c) 2026 João Lopes.
"""Context-aware process orchestrator.

Runtime discovery uses the process table without a persistent registry.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from json import dumps, loads
from os import getpid
from os import kill as signal_process
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from signal import SIGHUP, SIGINT, SIGTERM, SIGUSR1
from socket import (
    AF_INET,
    SO_REUSEADDR,
    SOCK_STREAM,
    SOL_SOCKET,
    create_connection,
    socket,
)
from subprocess import Popen
from sys import argv, executable, stderr, stdout
from textwrap import dedent
from threading import Event, Lock, Thread
from time import monotonic, sleep, time
from typing import Final, cast, final

from exactus.packages.pmanager._platform import ProcessBackend, backend


@final
class Constants:
    """Constants.

    Attributes:
        host: Host.
        marker: Marker.
        poll: Poll.
        bar_width: Bar width.
        spec_name: Spec name.
        spec_version: Spec version.
        percent_complete: Percent complete.
        ipc_max_bytes: Ipc max bytes.
        protocol_version: Protocol version.
        kill_grace: Kill grace.

    """

    host: Final[str] = "127.0.0.1"
    marker: Final[str] = "--orchestrator-worker=v2"
    poll: Final[float] = 0.1
    bar_width: Final[int] = 36
    spec_name: Final[str] = "processes.json"
    spec_version: Final[int] = 2
    percent_complete: Final[int] = 100
    ipc_max_bytes: Final[int] = 1048576
    protocol_version: Final[int] = 2
    kill_grace: Final[float] = 5.0


type JsonValue = (
    str
    | int
    | float
    | bool
    | list["JsonValue"]
    | dict[str, "JsonValue"]
    | None
)


class State(Enum):
    """State.

    Attributes:
        STARTING: Starting.
        RUNNING: Running.
        PAUSED: Paused.
        WAITING_DEPENDENCY: Waiting dependency.
        WAITING_CONCURRENCY: Waiting concurrency.
        WAITING_RESOURCE: Waiting resource.
        WAITING_CHILDREN: Waiting children.
        COMPLETED: Completed.
        FAILED: Failed.
        STOPPING: Stopping.
        KILLED: Killed.
        CANCELLED: Cancelled.

    """

    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_DEPENDENCY = "waiting_dependency"
    WAITING_CONCURRENCY = "waiting_concurrency"
    WAITING_RESOURCE = "waiting_resource"
    WAITING_CHILDREN = "waiting_children"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    KILLED = "killed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Descriptor:
    """Descriptor.

    Attributes:
        pid: Pid.
        port: Port.
        name: Name.
        context: Context.
        args: Args.
        token: Token.

    """

    pid: int
    port: int
    name: str
    context: str
    args: tuple[str, ...]
    token: str = ""


@dataclass(slots=True)
class Runtime:
    """Runtime.

    Attributes:
        name: Name.
        context: Context.
        args: Args.
        progress: Progress.
        state: State.
        reason: Reason.
        exit_code: Exit code.
        attempts: Attempts.
        generation: Generation.
        children: Children.

    """

    name: str
    context: str
    args: tuple[str, ...]
    progress: int = 0
    state: State = State.STARTING
    reason: str = ""
    exit_code: int | None = None
    attempts: int = 0
    generation: int = 1
    children: dict[str, JsonValue] = field(default_factory=dict)


class SpecError(RuntimeError):
    """Specerror."""


class Spec:
    """Spec."""

    def __init__(self, path: Path) -> None:
        """Init.

        Args:
            path: Path.

        Raises:
            SpecError: When the operation cannot complete.

        """
        self.path: Path = path
        raw: JsonValue = loads(s=path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg: str = "Specification root must be an object."
            raise SpecError(msg)
        self.raw: dict[str, JsonValue] = raw
        self.processes: dict[str, dict[str, JsonValue]] = self._normalize()
        self.validate()

    @staticmethod
    def refs(config: dict[str, JsonValue]) -> tuple[str, ...]:
        """Refs.

        Args:
            config: Config.

        Returns:
            The resulting value.

        """
        refs: list[str] = []
        for key in ("depends_on", "children"):
            value: JsonValue = config.get(key, [])
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, str):
                    refs.append(item)
                elif isinstance(item, dict):
                    process_value: JsonValue = item.get("process")
                    if isinstance(process_value, str):
                        refs.append(process_value)
        return tuple(refs)

    def validate(self) -> None:
        """Validate.

        Raises:
            SpecError: When the operation cannot complete.

        """
        version: JsonValue = self.raw.get("version")
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            msg: str = "Specification version must be a positive integer."
            raise SpecError(msg)
        for name, config in self.processes.items():
            for ref in self.refs(config=config):
                if ref not in self.processes:
                    msg = f"{name!r} references unknown process {ref!r}."
                    raise SpecError(msg)
                if ref == name:
                    msg = f"{name!r} cannot depend on itself."
                    raise SpecError(msg)
        self._check_cycles()

    def process(self, name: str) -> dict[str, JsonValue]:
        """Process.

        Args:
            name: Name.

        Raises:
            SpecError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        try:
            return self.processes[name]
        except KeyError as error:
            msg: str = f"Unknown process {name!r}."
            raise SpecError(msg) from error

    @classmethod
    def _merge(
        cls,
        base: dict[str, JsonValue],
        override: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Merge.

        Args:
            base: Base.
            override: Override.

        Returns:
            The resulting value.

        """
        result: dict[str, JsonValue] = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                prior: JsonValue = result[key]
                prior_dict: dict[str, JsonValue] = cast(
                    typ="dict[str, JsonValue]",
                    val=prior,
                )
                result[key] = cls._merge(base=prior_dict, override=value)
            else:
                result[key] = value
        return result

    def _normalize(self) -> dict[str, dict[str, JsonValue]]:
        """Normalize.

        Raises:
            SpecError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        global_value: JsonValue = self.raw.get("global", {})
        templates_value: JsonValue = self.raw.get("templates", {})
        processes_value: JsonValue = self.raw.get("processes", {})
        if (
            not isinstance(global_value, dict)
            or not isinstance(templates_value, dict)
            or (not isinstance(processes_value, dict))
        ):
            msg: str = "global, templates, and processes must be objects."
            raise SpecError(msg)
        defaults_value: JsonValue = global_value.get("defaults", {})
        if not isinstance(defaults_value, dict):
            msg = "global.defaults must be an object."
            raise SpecError(msg)
        result: dict[str, dict[str, JsonValue]] = {}
        for name, value in processes_value.items():
            if not isinstance(value, dict):
                msg = f"Process {name!r} must be an object."
                raise SpecError(msg)
            merged: dict[str, JsonValue] = dict(defaults_value)
            extends: JsonValue = value.get("extends")
            if isinstance(extends, str):
                template: JsonValue = templates_value.get(extends)
                if not isinstance(template, dict):
                    msg = f"Unknown template {extends!r}."
                    raise SpecError(msg)
                merged = self._merge(base=merged, override=template)
            result[name] = self._merge(
                base=merged,
                override={
                    key: item
                    for key, item in value.items()
                    if key != "extends"
                },
            )
        return result

    def _check_cycles(self) -> None:
        """Reject specifications with cyclic process references."""
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            """Visit.

            Args:
                name: Name.

            Raises:
                SpecError: When the operation cannot complete.

            """
            if name in visiting:
                msg: str = f"Dependency cycle detected at {name!r}."
                raise SpecError(msg)
            if name in visited:
                return
            visiting.add(name)
            for ref in self.refs(config=self.processes[name]):
                visit(name=ref)
            visiting.remove(name)
            visited.add(name)

        for name in self.processes:
            visit(name=name)


class Discovery:
    """Discovery."""

    @classmethod
    def find(cls, name: str, context: str) -> Descriptor | None:
        """Find.

        Args:
            name: Name.
            context: Context.

        Returns:
            The resulting value.

        """
        return next(
            (
                item
                for item in cls.all()
                if item.name == name and item.context == context
            ),
            None,
        )

    @staticmethod
    def all() -> tuple[Descriptor, ...]:
        """All.

        Returns:
            The resulting value.

        """
        found: list[Descriptor] = []
        process_backend: ProcessBackend = backend()
        for pid, command in process_backend.command_lines():
            if Constants.marker not in command:
                continue
            parts: list[str] = command.split()
            try:
                port: int = int(
                    next(
                        item.split(sep="=", maxsplit=1)[1]
                        for item in parts
                        if item.startswith("--worker-port=")
                    ),
                )
                name: str = next(
                    item.split(sep="=", maxsplit=1)[1]
                    for item in parts
                    if item.startswith("--worker-name=")
                )
                context: str = next(
                    item.split(sep="=", maxsplit=1)[1]
                    for item in parts
                    if item.startswith("--worker-context=")
                )
                encoded: str = next(
                    (
                        item.split(sep="=", maxsplit=1)[1]
                        for item in parts
                        if item.startswith("--worker-args=")
                    ),
                    "[]",
                )
                args_value: JsonValue = loads(s=encoded)
                args_tuple: tuple[str, ...] = (
                    tuple(str(object=item) for item in args_value)
                    if isinstance(args_value, list)
                    else ()
                )
                token: str = next(
                    (
                        item.split(sep="=", maxsplit=1)[1]
                        for item in parts
                        if item.startswith("--worker-token=")
                    ),
                    "",
                )
                found.append(
                    Descriptor(
                        pid=pid,
                        port=port,
                        name=name,
                        context=context,
                        args=args_tuple,
                        token=token,
                    ),
                )
            except (ValueError, StopIteration):
                continue
        return tuple(found)


class Client:
    """Client."""

    @staticmethod
    def request(
        descriptor: Descriptor,
        command: str,
        *,
        payload: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Request.

        Args:
            descriptor: Descriptor.
            command: Command.
            payload: Payload.

        Raises:
            RuntimeError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        message: dict[str, JsonValue] = {
            "protocol": Constants.protocol_version,
            "token": descriptor.token,
            "command": command,
        }
        if payload is not None:
            message["payload"] = payload
        with create_connection(
            timeout=2.0,
            address=(Constants.host, descriptor.port),
        ) as connection:
            connection.sendall(
                (dumps(separators=(",", ":"), obj=message) + "\n").encode(),
            )
            data: bytes = b""
            while b"\n" not in data:
                block: bytes = connection.recv(65536)
                if not block:
                    break
                data += block
                if len(data) > Constants.ipc_max_bytes:
                    msg: str = "IPC response exceeded 1 MiB."
                    raise RuntimeError(msg)
        value: JsonValue = (
            loads(s=data.split(sep=b"\n", maxsplit=1)[0].decode())
            if data
            else {}
        )
        return value if isinstance(value, dict) else {}


class Launcher:
    """Launcher."""

    def __init__(self, spec_path: Path) -> None:
        """Init.

        Args:
            spec_path: Spec path.

        """
        self.spec_path: Path = spec_path
        self.spec: Spec = Spec(path=spec_path)

    def create(
        self,
        name: str,
        context: str,
        process_args: tuple[str, ...],
        *,
        restart: bool = False,
        policy_key: str = "on_create",
    ) -> Descriptor:
        """Create.

        Args:
            name: Name.
            context: Context.
            process_args: Process args.
            restart: Restart.
            policy_key: Policy key.

        Raises:
            RuntimeError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        self.spec.process(name=name)
        existing: Descriptor | None = Discovery.find(
            name=name,
            context=context,
        )
        if existing is not None:
            control_command: str = "restart" if restart else "reuse"
            if not restart:
                info: dict[str, JsonValue] = Client.request(
                    descriptor=existing,
                    command="info",
                )
                state_value: JsonValue = info.get("state", State.RUNNING.value)
                state_key: str = str(object=state_value)
                config: dict[str, JsonValue] = self.spec.process(name=name)
                policy_value: JsonValue = config.get(policy_key, {})
                if isinstance(policy_value, dict):
                    selected: JsonValue = policy_value.get(state_key, "reuse")
                    if isinstance(selected, str):
                        control_command = selected
            control_command = {
                "start": "start",
                "resume": "start",
                "reset_start": "restart",
                "reset": "restart",
                "restart": "restart",
                "reuse": "info",
            }.get(control_command, "info")
            Client.request(
                payload=cast(
                    typ="dict[str, JsonValue]",
                    val={"args": list(process_args)},
                ),
                descriptor=existing,
                command=control_command,
            )
            return existing
        listener: socket = socket(family=AF_INET, type=SOCK_STREAM)
        listener.bind((Constants.host, 0))
        port: int = int(listener.getsockname()[1])
        listener.close()
        encoded_args: str = dumps(
            separators=(",", ":"),
            obj=list(process_args),
        )
        token: str = token_urlsafe(nbytes=32)
        command: list[str] = [
            executable,
            "-m",
            "exactus.packages.pmanager.runtime",
            Constants.marker,
            f"--worker-port={port}",
            f"--worker-name={name}",
            f"--worker-context={context}",
            f"--worker-token={token}",
            f"--worker-args={encoded_args}",
            f"--spec={self.spec_path.resolve()}",
        ]
        backend().spawn(command=command)
        deadline: float = monotonic() + 15.0
        while monotonic() < deadline:
            descriptor: Descriptor | None = Discovery.find(
                name=name,
                context=context,
            )
            if descriptor is not None:
                try:
                    Client.request(descriptor=descriptor, command="info")
                except OSError:
                    sleep(0.05)
                    continue
                return descriptor
            sleep(0.05)
        msg: str = f"Worker {name}/{context} did not become IPC-ready."
        raise RuntimeError(msg)


class Worker:
    """Worker."""

    def __init__(
        self,
        runtime: Runtime,
        spec: Spec,
        port: int,
        token: str = "",
    ) -> None:
        """Init.

        Args:
            runtime: Runtime.
            spec: Spec.
            port: Port.
            token: Token.

        """
        self.runtime: Runtime = runtime
        self.spec: Spec = spec
        self.port: int = port
        self.token: str = token
        self.stop: Event = Event()
        self.pause: Event = Event()
        self.pause_owners: set[str] = set()
        self.lock: Lock = Lock()
        self.started_at: float = monotonic()
        self.executor_process: Popen[bytes] | None = None
        self.class_control_port: int | None = None
        self.class_control_token: str | None = None
        self.broadcast_sequence: int = 0
        self.broadcast_events: deque[dict[str, JsonValue]] = deque(maxlen=1024)

    def snapshot(self) -> dict[str, JsonValue]:
        """Snapshot.

        Returns:
            The resulting value.

        """
        with self.lock:
            return cast(
                typ="dict[str, JsonValue]",
                val={
                    "process": self.runtime.name,
                    "context": self.runtime.context,
                    "pid": getpid(),
                    "progress": self.runtime.progress,
                    "state": self.runtime.state.value,
                    "reason": self.runtime.reason,
                    "exit_code": self.runtime.exit_code,
                    "attempts": self.runtime.attempts,
                    "generation": self.runtime.generation,
                    "args": list(self.runtime.args),
                    "children": self.runtime.children,
                    "pause_owners": sorted(self.pause_owners),
                },
            )

    def refs(self, key: str) -> tuple[str, ...]:
        """Refs.

        Args:
            key: Key.

        Returns:
            The resulting value.

        """
        config: dict[str, JsonValue] = self.spec.process(
            name=self.runtime.name,
        )
        value: JsonValue = config.get(key, [])
        refs: list[str] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    refs.append(item)
                elif isinstance(item, dict):
                    process_value: JsonValue = item.get("process")
                    if isinstance(process_value, str):
                        refs.append(process_value)
        return tuple(refs)

    def execute(self) -> None:
        """Execute."""
        generation: int = self.runtime.generation
        config: dict[str, JsonValue] = self.spec.process(
            name=self.runtime.name,
        )
        if config.get("mode") == "fanout_join":
            success: bool = self._run_fanout()
        else:
            success = True
            for dependency in self.refs(key="depends_on"):
                if not self._wait_for(
                    label=dependency,
                    descriptor=self._ensure(name=dependency),
                ):
                    success = False
                    break
            if success:
                self._admit_concurrency()
                executor_value: JsonValue = config.get(
                    "executor",
                    {"type": "counter"},
                )
                executor_config: dict[str, JsonValue] = (
                    executor_value
                    if isinstance(executor_value, dict)
                    else {"type": "counter"}
                )
                executor_type: JsonValue = executor_config.get(
                    "type",
                    "counter",
                )
                success = (
                    self._run_command(executor_config=executor_config)
                    if executor_type in ("command", "python", "python_class")
                    else self._run_counter()
                )
        if generation != self.runtime.generation:
            return
        if self.stop.is_set():
            self._set(state=State.KILLED)
        else:
            self._set(state=State.COMPLETED if success else State.FAILED)
            if success:
                with self.lock:
                    self.runtime.progress = Constants.percent_complete

    def serve(self) -> None:
        """Serve."""
        server: socket = socket(family=AF_INET, type=SOCK_STREAM)
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind((Constants.host, self.port))
        server.listen(32)
        server.settimeout(Constants.poll)
        Thread(target=self.execute, daemon=True).start()
        while not self.stop.is_set():
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            with connection:
                request: JsonValue = self._read_request(connection=connection)
                response: dict[str, JsonValue] = self._respond(request=request)
                connection.sendall(
                    (
                        dumps(separators=(",", ":"), obj=response) + "\n"
                    ).encode(),
                )
        server.close()

    @staticmethod
    def _read_request(connection: socket) -> JsonValue:
        """Read one newline-terminated JSON request.

        Args:
            connection: Connection.

        Returns:
            The resulting value.

        """
        data: bytes = b""
        while b"\n" not in data:
            block: bytes = connection.recv(65536)
            if not block:
                break
            data += block
            if len(data) > Constants.ipc_max_bytes:
                break
        try:
            return (
                loads(s=data.split(sep=b"\n", maxsplit=1)[0].decode())
                if data
                else {}
            )
        except ValueError:
            return {}

    @staticmethod
    def _payload(request: JsonValue) -> JsonValue:
        """Extract the request payload.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        return request.get("payload") if isinstance(request, dict) else None

    @staticmethod
    def _escalate(process: Popen[bytes]) -> None:
        """Escalate a stubborn process to a hard kill.

        Args:
            process: Process.

        """
        deadline: float = monotonic() + Constants.kill_grace
        while process.poll() is None and monotonic() < deadline:
            sleep(Constants.poll)
        if process.poll() is None:
            process.kill()

    def _class_status(self) -> JsonValue:
        """Class status.

        Returns:
            The resulting value.

        """
        if self.class_control_port is None or self.class_control_token is None:
            return {}
        try:
            with create_connection(
                timeout=0.5,
                address=(Constants.host, self.class_control_port),
            ) as connection:
                connection.sendall(
                    dumps(obj={"token": self.class_control_token}).encode(),
                )
                connection.settimeout(0.5)
                data: bytes = connection.recv(Constants.ipc_max_bytes)
            value: JsonValue = loads(
                s=data.split(sep=b"\n", maxsplit=1)[0].decode(),
            )
        except (OSError, ValueError):
            return {}
        else:
            return value

    def _set(self, state: State, reason: str = "") -> None:
        """Set.

        Args:
            state: State.
            reason: Reason.

        """
        with self.lock:
            self.runtime.state = state
            self.runtime.reason = reason

    def _ensure(self, name: str, *, restart_live: bool = False) -> Descriptor:
        """Ensure.

        Args:
            name: Name.
            restart_live: Restart live.

        Returns:
            The resulting value.

        """
        launcher: Launcher = Launcher(spec_path=self.spec.path)
        existing: Descriptor | None = Discovery.find(
            name=name,
            context=self.runtime.context,
        )
        if existing is not None and (not restart_live):
            return existing
        return launcher.create(
            restart=restart_live and existing is not None,
            policy_key="on_dependency_request",
            name=name,
            context=self.runtime.context,
            process_args=self.runtime.args,
        )

    def _wait_for(self, descriptor: Descriptor, label: str) -> bool:
        """Wait for.

        Args:
            descriptor: Descriptor.
            label: Label.

        Returns:
            The resulting value.

        """
        self._set(state=State.WAITING_DEPENDENCY, reason=label)
        while not self.stop.is_set():
            current: Descriptor | None = Discovery.find(
                name=descriptor.name,
                context=descriptor.context,
            )
            if current is None:
                return False
            try:
                info: dict[str, JsonValue] = Client.request(
                    descriptor=current,
                    command="info",
                )
                state: JsonValue = info.get("state")
                if state == State.COMPLETED.value:
                    return True
                if state in (
                    State.FAILED.value,
                    State.KILLED.value,
                    State.CANCELLED.value,
                ):
                    return False
            except OSError:
                sleep(Constants.poll)
            sleep(Constants.poll)
        return False

    def _admit_concurrency(self) -> None:
        """Admit concurrency."""
        config: dict[str, JsonValue] = self.spec.process(
            name=self.runtime.name,
        )
        value: JsonValue = config.get("concurrency")
        if not isinstance(value, dict):
            return
        maximum: JsonValue = value.get("max_running", 1)
        limit: int = int(maximum) if isinstance(maximum, (int, float)) else 1
        scope: JsonValue = value.get("scope", "context")
        group: JsonValue = value.get("group", f"process:{self.runtime.name}")
        while not self.stop.is_set():
            blockers: int = 0
            for descriptor in Discovery.all():
                if descriptor.pid == self.snapshot()["pid"]:
                    continue
                if (
                    scope == "context"
                    and descriptor.context != self.runtime.context
                ):
                    continue
                other: dict[str, JsonValue] = self.spec.process(
                    name=descriptor.name,
                )
                other_concurrency: JsonValue = other.get("concurrency")
                other_group: JsonValue = (
                    other_concurrency.get(
                        "group",
                        f"process:{descriptor.name}",
                    )
                    if isinstance(other_concurrency, dict)
                    else f"process:{descriptor.name}"
                )
                if other_group != group:
                    continue
                try:
                    state: JsonValue = Client.request(
                        descriptor=descriptor,
                        command="info",
                    ).get("state")
                    if state == State.RUNNING.value:
                        blockers += 1
                except OSError:
                    continue
            if blockers < limit:
                return
            self._set(
                state=State.WAITING_CONCURRENCY,
                reason=str(object=group),
            )
            sleep(Constants.poll)

    def _run_counter(self) -> bool:
        """Run counter.

        Returns:
            The resulting value.

        """
        config: dict[str, JsonValue] = self.spec.process(
            name=self.runtime.name,
        )
        duration_value: JsonValue = config.get("duration_seconds", 100)
        tick_value: JsonValue = config.get("tick_seconds", 1)
        duration: float = (
            float(duration_value)
            if isinstance(duration_value, (int, float))
            else 100.0
        )
        tick: float = (
            float(tick_value) if isinstance(tick_value, (int, float)) else 1.0
        )
        self._set(state=State.RUNNING)
        generation: int = self.runtime.generation
        while (
            self.runtime.progress < Constants.percent_complete
            and (not self.stop.is_set())
            and (generation == self.runtime.generation)
        ):
            if self.pause.is_set():
                self._set(state=State.PAUSED)
                sleep(Constants.poll)
                continue
            self._set(state=State.RUNNING)
            sleep(max(tick, 0.01))
            with self.lock:
                self.runtime.progress = min(
                    100,
                    self.runtime.progress
                    + max(1, round(number=100 * tick / max(duration, tick))),
                )
        return not self.stop.is_set()

    def _run_command(self, executor_config: dict[str, JsonValue]) -> bool:
        """Run command.

        Args:
            executor_config: Executor config.

        Returns:
            The resulting value.

        """
        command_value: JsonValue = executor_config.get("command")
        if not isinstance(command_value, list) or not all(
            isinstance(item, str) for item in command_value
        ):
            self.runtime.exit_code = 2
            return False
        command: list[str] = [str(object=item) for item in command_value]
        if executor_config.get("type") == "python_class":
            listener: socket = socket(family=AF_INET, type=SOCK_STREAM)
            listener.bind((Constants.host, 0))
            self.class_control_port = int(listener.getsockname()[1])
            listener.close()
            self.class_control_token = token_urlsafe(nbytes=32)
            command.extend(
                (
                    f"--orchestrator-control-port={self.class_control_port}",
                    f"--orchestrator-control-token={self.class_control_token}",
                    f"--orchestrator-worker-port={self.port}",
                    f"--orchestrator-worker-token={self.token}",
                ),
            )
        command.extend(self.runtime.args)
        cwd_value: JsonValue = executor_config.get("cwd")
        self._set(state=State.RUNNING)
        process: Popen[bytes] = Popen(
            cwd=str(object=cwd_value) if isinstance(cwd_value, str) else None,
            args=command,
        )
        self.executor_process = process
        if self.pause.is_set() and process.poll() is None:
            backend().pause(pid=process.pid)
            self._set(
                state=State.PAUSED,
                reason="waiting for " + ", ".join(sorted(self.pause_owners)),
            )
        generation: int = self.runtime.generation
        while (
            process.poll() is None
            and (not self.stop.is_set())
            and (generation == self.runtime.generation)
        ):
            sleep(Constants.poll)
        if process.poll() is None:
            process.terminate()
        self.runtime.exit_code = process.wait()
        self.executor_process = None
        self.class_control_port = None
        self.class_control_token = None
        return self.runtime.exit_code == 0

    def _run_fanout(self) -> bool:
        """Run fanout.

        Returns:
            The resulting value.

        """
        children: tuple[str, ...] = self.refs(key="children")
        self._set(state=State.WAITING_CHILDREN, reason="children")
        descriptors: dict[str, Descriptor] = {}
        for child in children:
            existing: Descriptor | None = Discovery.find(
                name=child,
                context=self.runtime.context,
            )
            descriptors[child] = self._ensure(
                restart_live=existing is not None,
                name=child,
            )
        while not self.stop.is_set():
            done: int = 0
            failed: bool = False
            snapshots: dict[str, JsonValue] = {}
            for child in descriptors:
                current: Descriptor | None = Discovery.find(
                    name=child,
                    context=self.runtime.context,
                )
                if current is None:
                    failed = True
                    snapshots[child] = {
                        "state": State.FAILED.value,
                        "progress": 0,
                        "reason": "child disappeared before completion",
                    }
                    continue
                try:
                    info: dict[str, JsonValue] = Client.request(
                        descriptor=current,
                        command="info",
                    )
                    snapshots[child] = info
                    state: JsonValue = info.get("state")
                    done += int(state == State.COMPLETED.value)
                    failed = failed or state in (
                        State.FAILED.value,
                        State.KILLED.value,
                        State.CANCELLED.value,
                    )
                except OSError:
                    pass
            with self.lock:
                self.runtime.children = snapshots
            if failed:
                return False
            if done == len(children):
                return True
            sleep(Constants.poll)
        return False

    def _enqueue_broadcast(
        self,
        event: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Enqueue broadcast.

        Args:
            event: Event.

        Returns:
            The resulting value.

        """
        with self.lock:
            self.broadcast_sequence += 1
            stored: dict[str, JsonValue] = dict(event)
            stored["id"] = self.broadcast_sequence
            self.broadcast_events.append(stored)
        return stored

    def _broadcast(
        self,
        payload: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Broadcast.

        Args:
            payload: Payload.

        Returns:
            The resulting value.

        """
        topic: JsonValue = payload.get("topic")
        if not isinstance(topic, str) or not topic:
            return {"error": "broadcast topic must be a non-empty string"}
        scope: JsonValue = payload.get("scope", "context")
        event: dict[str, JsonValue] = {
            "topic": topic,
            "payload": payload.get("payload"),
            "source": self.runtime.name,
            "context": self.runtime.context,
            "generation": self.runtime.generation,
            "timestamp": time(),
        }
        delivered: int = 0
        for descriptor in Discovery.all():
            if (
                scope != "global"
                and descriptor.context != self.runtime.context
            ):
                continue
            if descriptor.pid == getpid():
                self._enqueue_broadcast(event=event)
                delivered += 1
                continue
            try:
                Client.request(
                    descriptor=descriptor,
                    command="event",
                    payload=event,
                )
                delivered += 1
            except OSError:
                continue
        return {"delivered": delivered, "event": event}

    def _command(self, request: JsonValue) -> str:
        """Authenticate a request and extract its command.

        Args:
            request: Request.

        Returns:
            The command for authenticated requests, else an empty string.

        """
        if not isinstance(request, dict):
            return ""
        protocol: JsonValue = request.get("protocol")
        request_token: JsonValue = request.get("token")
        if not (
            protocol == Constants.protocol_version
            and isinstance(request_token, str)
            and compare_digest(self.token, request_token)
        ):
            return ""
        return str(object=request.get("command", ""))

    def _executor_is_class(self) -> bool:
        """Report whether the process uses a python_class executor.

        Returns:
            The resulting value.

        """
        config: dict[str, JsonValue] = self.spec.process(
            name=self.runtime.name,
        )
        executor: JsonValue = config.get("executor")
        return (
            isinstance(executor, dict)
            and executor.get("type") == "python_class"
        )

    def _respond(self, request: JsonValue) -> dict[str, JsonValue]:
        """Dispatch an authenticated request to its command handler.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        command: str = self._command(request=request)
        if command in ("info", "live"):
            response: dict[str, JsonValue] = self._cmd_info(command=command)
        elif command == "broadcast":
            response = self._cmd_broadcast(request=request)
        elif command == "event":
            response = self._cmd_event(request=request)
        elif command == "events":
            response = self._cmd_events(request=request)
        elif command == "pause":
            response = self._cmd_pause(request=request)
        elif command == "start":
            response = self._cmd_start(request=request)
        elif command in ("reset", "restart", "create"):
            response = self._cmd_restart(request=request)
        elif command in ("kill", "cancel"):
            response = self._cmd_terminate(command=command)
        else:
            response = {"error": f"unknown command {command}"}
        return response

    def _cmd_info(self, command: str) -> dict[str, JsonValue]:
        """Report a snapshot, enriched with class status for info.

        Args:
            command: Command.

        Returns:
            The resulting value.

        """
        response: dict[str, JsonValue] = self.snapshot()
        if command == "info":
            response["custom_status"] = self._class_status()
        return response

    def _cmd_broadcast(self, request: JsonValue) -> dict[str, JsonValue]:
        """Handle a broadcast request.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        payload_value: JsonValue = self._payload(request=request)
        return (
            self._broadcast(payload=payload_value)
            if isinstance(payload_value, dict)
            else {"error": "broadcast payload must be an object"}
        )

    def _cmd_event(self, request: JsonValue) -> dict[str, JsonValue]:
        """Handle an event enqueue request.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        payload_value: JsonValue = self._payload(request=request)
        return (
            self._enqueue_broadcast(event=payload_value)
            if isinstance(payload_value, dict)
            else {"error": "event payload must be an object"}
        )

    def _cmd_events(self, request: JsonValue) -> dict[str, JsonValue]:
        """Handle a broadcast event listing request.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        payload_value: JsonValue = self._payload(request=request)
        after_value: JsonValue = (
            payload_value.get("after", 0)
            if isinstance(payload_value, dict)
            else 0
        )
        after: int = int(after_value) if isinstance(after_value, int) else 0
        with self.lock:
            events: list[JsonValue] = []
            for event in self.broadcast_events:
                event_id: JsonValue = event.get("id")
                if isinstance(event_id, int) and event_id > after:
                    events.append(event)
        return {"events": events, "latest": self.broadcast_sequence}

    def _pause_owner(self, *, request: JsonValue) -> str:
        """Return the requester holding one pause lease.

        Args:
            request: Authenticated control request.

        Returns:
            Explicit owner, or the legacy global-owner marker.

        """
        payload: JsonValue = self._payload(request=request)
        owner: JsonValue = (
            payload.get("owner") if isinstance(payload, dict) else None
        )
        return owner if isinstance(owner, str) and owner else "*"

    def _cmd_pause(self, *, request: JsonValue) -> dict[str, JsonValue]:
        """Handle a pause request.

        Args:
            request: Authenticated control request.

        Returns:
            The resulting value.

        """
        already_paused: bool = self.pause.is_set()
        with self.lock:
            self.pause_owners.add(self._pause_owner(request=request))
        self.pause.set()
        process: Popen[bytes] | None = self.executor_process
        if (
            not already_paused
            and process is not None
            and process.poll() is None
        ):
            if self._executor_is_class():
                signal_process(process.pid, SIGUSR1)
            else:
                backend().pause(pid=process.pid)
        self._set(
            state=State.PAUSED,
            reason="waiting for " + ", ".join(sorted(self.pause_owners)),
        )
        return self.snapshot()

    def _cmd_start(self, *, request: JsonValue) -> dict[str, JsonValue]:
        """Handle a start request.

        Args:
            request: Authenticated control request.

        Returns:
            The resulting value.

        """
        owner: str = self._pause_owner(request=request)
        with self.lock:
            if owner == "*":
                self.pause_owners.clear()
            else:
                self.pause_owners.discard(owner)
            remaining: tuple[str, ...] = tuple(sorted(self.pause_owners))
        if remaining:
            self.pause.set()
            self._set(
                state=State.PAUSED,
                reason="waiting for " + ", ".join(remaining),
            )
            return self.snapshot()
        process: Popen[bytes] | None = self.executor_process
        if process is not None and process.poll() is None:
            backend().resume(pid=process.pid)
        self.pause.clear()
        self._set(state=State.RUNNING)
        return self.snapshot()

    def _cmd_restart(self, request: JsonValue) -> dict[str, JsonValue]:
        """Handle a reset, restart or create request.

        Args:
            request: Request.

        Returns:
            The resulting value.

        """
        process: Popen[bytes] | None = self.executor_process
        if process is not None and process.poll() is None:
            if self._executor_is_class():
                signal_process(process.pid, SIGHUP)
            else:
                process.terminate()
        with self.lock:
            self.runtime.progress = 0
            self.runtime.exit_code = None
            self.runtime.generation += 1
            payload_value: JsonValue = self._payload(request=request)
            if isinstance(payload_value, dict):
                args_value: JsonValue = payload_value.get("args")
                if isinstance(args_value, list):
                    self.runtime.args = tuple(
                        str(object=item) for item in args_value
                    )
        if self.pause_owners:
            self.pause.set()
        else:
            self.pause.clear()
        Thread(target=self.execute, daemon=True).start()
        return self.snapshot()

    def _cmd_terminate(self, command: str) -> dict[str, JsonValue]:
        """Handle a kill or cancel request.

        Args:
            command: Command.

        Returns:
            The resulting value.

        """
        process: Popen[bytes] | None = self.executor_process
        if process is not None and process.poll() is None:
            if self._executor_is_class():
                signal_process(
                    process.pid,
                    SIGINT if command == "cancel" else SIGTERM,
                )
                if command == "kill":
                    self._escalate(process=process)
            else:
                process.terminate()
        if command == "cancel":
            self._set(state=State.CANCELLED)
        response: dict[str, JsonValue] = self.snapshot()
        self.stop.set()
        return response


class Cli:
    """Cli.

    Attributes:
        CONTROL: Control.
        OBSERVE_COMMANDS: Observe commands.

    """

    CONTROL: Final[set[str]] = {
        "--kill",
        "-k",
        "--pause",
        "-p",
        "--start",
        "-s",
        "--reset",
        "-r",
        "--info",
        "-i",
        "--live",
        "-l",
        "--recursive",
        "--json",
        "--dry-run",
    }
    OBSERVE_COMMANDS: Final[dict[str, str]] = {
        "-k": "kill",
        "--kill": "kill",
        "-p": "pause",
        "--pause": "pause",
        "-s": "start",
        "--start": "start",
        "-r": "reset",
        "--reset": "reset",
        "-i": "info",
        "--info": "info",
        "-l": "live",
        "--live": "live",
    }

    @classmethod
    def split_args(
        cls,
        values: list[str],
    ) -> tuple[list[str], tuple[str, ...]]:
        """Split args.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        if "--args" not in values and "-a" not in values:
            return (values, ())
        index: int = min(
            values.index(flag) for flag in ("--args", "-a") if flag in values
        )
        head: list[str] = values[:index]
        payload: list[str] = []
        tail: list[str] = values[index + 1 :]
        i: int = 0
        while i < len(tail):
            token: str = tail[i]
            if token in cls.CONTROL:
                head.append(token)
            else:
                payload.append(token)
            i += 1
        return (head, tuple(payload))

    @classmethod
    def main(cls, values: list[str]) -> int:
        """Run the command-line entry point.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        if Constants.marker in values:
            return cls._worker(values=values)
        args, process_args = cls.split_args(values=values[1:])
        if "--help" in args or "-h" in args:
            stdout.write(
                dedent(
                    text=(
                        "    pmanager: --spec PATH --create PROCESS CONTEX"
                        "T | --observe PROCESS CONTEXT | --status | --tree"
                        " [CONTEXT] | --validate [--args ...]\n    "
                    ),
                ),
            )
            return 0
        spec_path: Path = cls._spec_path(args=args)
        spec: Spec = Spec(path=spec_path)
        informational: int | None = cls._informational(args=args, spec=spec)
        if informational is not None:
            return informational
        target: int | tuple[str, str, list[str]] = cls._target(
            args=args,
            spec=spec,
            script=Path(values[0]).resolve(),
        )
        if isinstance(target, int):
            return target
        name, context, remaining = target
        if "--dry-run" in remaining:
            return cls._dry_run(
                spec=spec,
                name=name,
                context=context,
                process_args=process_args,
            )
        descriptor: Descriptor = Launcher(spec_path=spec_path).create(
            name=name,
            context=context,
            process_args=process_args,
        )
        stdout.write(f"{descriptor.pid}\n")
        return 0

    @staticmethod
    def render(info: dict[str, JsonValue]) -> str:
        """Render.

        Args:
            info: Info.

        Returns:
            The resulting value.

        """
        progress_value: JsonValue = info.get("progress", 0)
        progress: int = (
            int(progress_value)
            if isinstance(progress_value, (int, float))
            else 0
        )
        filled: int = round(number=Constants.bar_width * progress / 100)
        empty: int = Constants.bar_width - filled
        state: JsonValue = info.get("state", "")
        return f"[{'█' * filled}{'░' * empty}] {progress:3d}% {state}"

    @staticmethod
    def tree(spec: Spec, context: str) -> str:
        """Tree.

        Args:
            spec: Spec.
            context: Context.

        Returns:
            The resulting value.

        """
        referenced: set[str] = set()
        for config in spec.processes.values():
            referenced.update(Spec.refs(config=config))
        roots: list[str] = [
            name for name in spec.processes if name not in referenced
        ]

        def branch(name: str, prefix: str, *, last: bool) -> list[str]:
            """Branch.

            Args:
                name: Name.
                prefix: Prefix.
                last: Last.

            Returns:
                The resulting value.

            """
            descriptor: Descriptor | None = Discovery.find(
                name=name,
                context=context,
            )
            status: str = "absent"
            if descriptor is not None:
                try:
                    info: dict[str, JsonValue] = Client.request(
                        descriptor=descriptor,
                        command="info",
                    )
                    state: JsonValue = info.get("state")
                    progress: JsonValue = info.get("progress", 0)
                    status = f"{state} {progress}% PID {descriptor.pid}"
                except OSError:
                    status = "unreachable"
            lines: list[str] = [
                f"{prefix}{('└── ' if last else '├── ')}{name} [{status}]",
            ]
            refs: tuple[str, ...] = Spec.refs(config=spec.process(name=name))
            child_prefix: str = prefix + ("    " if last else "│   ")
            for idx, ref in enumerate(iterable=refs):
                lines.extend(
                    branch(
                        name=ref,
                        prefix=child_prefix,
                        last=idx == len(refs) - 1,
                    ),
                )
            return lines

        lines: list[str] = [context]
        for idx, root in enumerate(iterable=roots):
            lines.extend(
                branch(name=root, prefix="", last=idx == len(roots) - 1),
            )
        return "\n".join(lines)

    @classmethod
    def _informational(cls, args: list[str], spec: Spec) -> int | None:
        """Run a non-launching informational command when requested.

        Args:
            args: Args.
            spec: Spec.

        Returns:
            Exit code for informational commands, else None.

        """
        if "--validate" in args:
            stdout.write(f"valid: {len(spec.processes)} processes\n")
            return 0
        if "--tree" in args:
            idx: int = cls._index(values=args, target="--tree")
            context: str = args[idx + 1] if idx + 1 < len(args) else "default"
            stdout.write(cls.tree(spec=spec, context=context) + "\n")
            return 0
        if "--status" in args:
            return cls._status(args=args)
        return None

    @classmethod
    def _target(
        cls,
        args: list[str],
        spec: Spec,
        script: Path,
    ) -> int | tuple[str, str, list[str]]:
        """Resolve a launch target or run an observation command.

        Args:
            args: Args.
            spec: Spec.
            script: Script.

        Raises:
            SpecError: When the operation cannot complete.

        Returns:
            The launch target or the observation exit code.

        """
        wrapper_name: str | None = (
            script.stem if script.stem in spec.processes else None
        )
        if wrapper_name is not None:
            if not args:
                msg: str = "A context argument is required."
                raise SpecError(msg)
            return (wrapper_name, args[0], args[1:])
        for flag in ("-c", "--create"):
            if flag in args:
                idx: int = cls._index(values=args, target=flag)
                name, context = args[idx + 1 : idx + 3]
                return (name, context, args[:idx] + args[idx + 3 :])
        for flag in ("-o", "--observe"):
            if flag in args:
                idx = cls._index(values=args, target=flag)
                if idx + 2 >= len(args):
                    msg = "Logical observation requires PROCESS CONTEXT."
                    raise SpecError(msg)
                name, context = args[idx + 1 : idx + 3]
                return cls._observe(
                    name=name,
                    context=context,
                    remaining=args[:idx] + args[idx + 3 :],
                )
        msg = (
            "Use --create PROCESS CONTEXT, --observe PROCESS CONTEXT, "
            "--status, --tree, or --validate."
        )
        raise SpecError(msg)

    @classmethod
    def _observe(cls, name: str, context: str, remaining: list[str]) -> int:
        """Send an observation command to a live worker.

        Args:
            name: Name.
            context: Context.
            remaining: Remaining arguments.

        Raises:
            SpecError: When no live worker matches.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor | None = Discovery.find(
            name=name,
            context=context,
        )
        if descriptor is None:
            msg: str = f"No live worker {name}/{context}."
            raise SpecError(msg)
        command: str = next(
            (
                cls.OBSERVE_COMMANDS[item]
                for item in remaining
                if item in cls.OBSERVE_COMMANDS
            ),
            "info",
        )
        if command == "live":
            return cls._live(name=name, context=context, descriptor=descriptor)
        info: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command=command,
        )
        stdout.write(
            (
                dumps(indent=2, obj=info)
                if "--json" in remaining
                else cls.render(info=info)
            )
            + "\n",
        )
        return 0

    @classmethod
    def _live(cls, name: str, context: str, descriptor: Descriptor) -> int:
        """Stream live worker status until completion.

        Args:
            name: Name.
            context: Context.
            descriptor: Descriptor.

        Returns:
            The resulting value.

        """
        try:
            while Discovery.find(name=name, context=context) is not None:
                info: dict[str, JsonValue] = Client.request(
                    descriptor=descriptor,
                    command="info",
                )
                stdout.write("\r" + cls.render(info=info))
                stdout.flush()
                if info.get("state") in (
                    State.COMPLETED.value,
                    State.FAILED.value,
                    State.KILLED.value,
                ):
                    break
                sleep(1)
            stdout.write("\n")
        except (KeyboardInterrupt, BrokenPipeError):
            return 0
        return 0

    @staticmethod
    def _index(values: list[str], target: str) -> int:
        """Index.

        Args:
            values: Values.
            target: Target.

        Raises:
            ValueError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        index: int = 0
        while index < len(values):
            if values[index] == target:
                return index
            index += 1
        raise ValueError(target)

    @staticmethod
    def _spec_path(args: list[str]) -> Path:
        """Remove ``--spec`` options and resolve the selected JSON file.

        Args:
            args: CLI arguments, modified in place.

        Raises:
            SpecError: When an option omits its required file path.

        Returns:
            JSON specification path.

        """
        spec_path: Path = Path(__file__).with_name(name=Constants.spec_name)
        index: int = 0
        while index < len(args):
            value: str = args[index]
            if value.startswith("--spec="):
                selected: str = value.removeprefix("--spec=")
                if not selected:
                    msg: str = "--spec requires a JSON file path."
                    raise SpecError(msg)
                spec_path = Path(selected).expanduser()
                del args[index]
                continue
            if value == "--spec":
                if index + 1 >= len(args) or args[index + 1].startswith("-"):
                    msg = "--spec requires a JSON file path."
                    raise SpecError(msg)
                spec_path = Path(args[index + 1]).expanduser()
                del args[index : index + 2]
                continue
            index += 1
        return spec_path

    @staticmethod
    def _worker(values: list[str]) -> int:
        """Run the detached worker selected by the launch marker.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        options: dict[str, str] = {}
        for value in values:
            if value.startswith(("--worker-", "--spec=")):
                key, item = value[2:].split(sep="=", maxsplit=1)
                options[key] = item
        worker_spec: Spec = Spec(path=Path(options["spec"]))
        args_value: JsonValue = loads(s=options.get("worker-args", "[]"))
        worker_args: tuple[str, ...] = (
            tuple(str(object=item) for item in args_value)
            if isinstance(args_value, list)
            else ()
        )
        Worker(
            spec=worker_spec,
            port=int(options["worker-port"]),
            token=options.get("worker-token", ""),
            runtime=Runtime(
                name=options["worker-name"],
                context=options["worker-context"],
                args=worker_args,
            ),
        ).serve()
        return 0

    @staticmethod
    def _status(args: list[str]) -> int:
        """Print status for every live worker.

        Args:
            args: Args.

        Returns:
            The resulting value.

        """
        rows: list[dict[str, JsonValue]] = []
        for descriptor in Discovery.all():
            try:
                rows.append(
                    Client.request(descriptor=descriptor, command="info"),
                )
            except OSError:
                continue
        output: str = (
            dumps(indent=2, obj=rows)
            if "--json" in args
            else "\n".join(
                f"{row.get('process')}/{row.get('context')} "
                f"{row.get('state')} {row.get('progress')}%"
                for row in rows
            )
        )
        stdout.write(output + "\n")
        return 0

    @staticmethod
    def _dry_run(
        spec: Spec,
        name: str,
        context: str,
        process_args: tuple[str, ...],
    ) -> int:
        """Print the launch plan without creating workers.

        Args:
            spec: Spec.
            name: Name.
            context: Context.
            process_args: Process args.

        Returns:
            The resulting value.

        """
        refs: tuple[str, ...] = Spec.refs(config=spec.process(name=name))
        stdout.write(f"PLAN {name}/{context}\n")
        existing: Descriptor | None = Discovery.find(
            name=name,
            context=context,
        )
        action: str = "REUSE/RESET" if existing else "CREATE"
        stdout.write(f"  action: {action}\n")
        for ref in refs:
            current: Descriptor | None = Discovery.find(
                name=ref,
                context=context,
            )
            child_action: str = (
                f"REUSE PID {current.pid}" if current else "CREATE"
            )
            stdout.write(f"  {ref}/{context}: {child_action}\n")
        stdout.write(f"  args: {list(process_args)!r}\n")
        return 0


def main() -> int:
    """Run the command-line entry point.

    Returns:
        The resulting value.

    """
    try:
        return Cli.main(values=argv)
    except (SpecError, RuntimeError, OSError, ValueError) as error:
        stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
