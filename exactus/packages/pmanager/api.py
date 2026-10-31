# Copyright (c) 2026 João Lopes.
"""Stable Python-first API for the context-aware process orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from json import dumps
from os import close
from pathlib import Path
from tempfile import mkstemp
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, Self, final

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from types import TracebackType

    from exactus.packages.pmanager.lifecycle import ProcessClass
from exactus.packages.pmanager.builder import Process
from exactus.packages.pmanager.builder import Spec as ObjectSpec
from exactus.packages.pmanager.model import Specification
from exactus.packages.pmanager.runtime import (
    Client,
    Descriptor,
    Discovery,
    JsonValue,
    Launcher,
    Spec,
    SpecError,
    State,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        structured_argument_parts: Grouped module constant.

    """

    structured_argument_parts: Final[int] = 2


class OrchestratorError(RuntimeError):
    """Orchestratorerror."""


class ProcessNotFoundError(OrchestratorError):
    """Processnotfounderror."""


class WaitTimeoutError(OrchestratorError):
    """Waittimeouterror."""


class ProcessAction(Enum):
    """Processaction.

    Attributes:
        PAUSE: Pause.
        RESUME: Resume.
        RESET: Reset.
        RESTART: Restart.
        KILL: Kill.
        CANCEL: Cancel.

    """

    PAUSE = "pause"
    RESUME = "start"
    RESET = "reset"
    RESTART = "restart"
    KILL = "kill"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class BroadcastEvent:
    """Broadcastevent.

    Attributes:
        id: Id.
        topic: Topic.
        payload: Payload.
        source: Source.
        context: Context.
        generation: Generation.
        timestamp: Timestamp.

    """

    id: int
    topic: str
    payload: JsonValue
    source: str
    context: str
    generation: int
    timestamp: float


@dataclass(frozen=True, slots=True)
class ProcessKey:
    """Processkey.

    Attributes:
        name: Name.
        context: Context.
        arguments: Arguments.

    """

    name: str
    context: str
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessStatus:
    """Processstatus.

    Attributes:
        key: Key.
        state: State.
        progress: Progress.
        pid: Pid.
        reason: Reason.
        exit_code: Exit code.
        attempts: Attempts.
        generation: Generation.
        children: Children.
        custom_status: Custom status.

    """

    key: ProcessKey
    state: State
    progress: int
    pid: int | None
    reason: str
    exit_code: int | None
    attempts: int
    generation: int
    children: Mapping[str, JsonValue]
    custom_status: JsonValue = None

    @property
    def terminal(self) -> bool:
        """Terminal.

        Returns:
            The resulting value.

        """
        return self.state in {
            State.COMPLETED,
            State.FAILED,
            State.KILLED,
            State.CANCELLED,
        }

    @property
    def successful(self) -> bool:
        """Successful.

        Returns:
            The resulting value.

        """
        return self.state is State.COMPLETED

    @property
    def live(self) -> bool:
        """Live.

        Returns:
            The resulting value.

        """
        return not self.terminal


@dataclass(frozen=True, slots=True)
class ProcessEvent:
    """Processevent.

    Attributes:
        status: Status.
        previous_state: Previous state.

    """

    status: ProcessStatus
    previous_state: State | None


@dataclass(frozen=True, slots=True)
class PlanEntry:
    """Planentry.

    Attributes:
        key: Key.
        action: Action.
        pid: Pid.

    """

    key: ProcessKey
    action: str
    pid: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Executionplan.

    Attributes:
        root: Root.
        entries: Entries.

    """

    root: ProcessKey
    entries: tuple[PlanEntry, ...]


class ProcessHandle:
    """Processhandle."""

    def __init__(self, orchestrator: Orchestrator, key: ProcessKey) -> None:
        """Init.

        Args:
            orchestrator: Orchestrator.
            key: Key.

        """
        self._orchestrator: Orchestrator = orchestrator
        self.key: ProcessKey = key

    def status(self) -> ProcessStatus:
        """Status.

        Returns:
            The resulting value.

        """
        return self._orchestrator.status(
            name=self.key.name,
            context=self.key.context,
        )

    def pause(self, *, recursive: bool = False) -> ProcessStatus:
        """Pause.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.pause(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def resume(self, *, recursive: bool = False) -> ProcessStatus:
        """Resume.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.resume(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def reset(self, *, recursive: bool = False) -> ProcessStatus:
        """Reset.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.reset(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def restart(self, *, recursive: bool = False) -> ProcessStatus:
        """Restart.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.restart(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def kill(self, *, recursive: bool = False) -> ProcessStatus:
        """Kill.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.kill(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def cancel(self, *, recursive: bool = False) -> ProcessStatus:
        """Cancel.

        Args:
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._orchestrator.cancel(
            name=self.key.name,
            context=self.key.context,
            recursive=recursive,
        )

    def wait(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.1,
    ) -> ProcessStatus:
        """Wait.

        Args:
            timeout: Timeout.
            poll_interval: Poll interval.

        Returns:
            The resulting value.

        """
        return self._orchestrator.wait(
            name=self.key.name,
            context=self.key.context,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def watch(
        self,
        *,
        poll_interval: float = 0.25,
        changes_only: bool = True,
    ) -> Iterator[ProcessEvent]:
        """Watch.

        Args:
            poll_interval: Poll interval.
            changes_only: Changes only.

        Returns:
            The resulting value.

        """
        return self._orchestrator.watch(
            name=self.key.name,
            context=self.key.context,
            poll_interval=poll_interval,
            changes_only=changes_only,
        )

    def subscribe(
        self,
        callback: Callable[[ProcessEvent], None],
        *,
        poll_interval: float = 0.25,
        changes_only: bool = True,
    ) -> ProcessStatus:
        """Subscribe.

        Args:
            callback: Callback.
            poll_interval: Poll interval.
            changes_only: Changes only.

        Returns:
            The resulting value.

        """
        return self._orchestrator.subscribe(
            name=self.key.name,
            context=self.key.context,
            callback=callback,
            poll_interval=poll_interval,
            changes_only=changes_only,
        )


class Context:
    """Context."""

    def __init__(self, orchestrator: Orchestrator, name: str) -> None:
        """Init.

        Args:
            orchestrator: Orchestrator.
            name: Name.

        """
        self._orchestrator: Orchestrator = orchestrator
        self.name: str = name

    def create(
        self,
        process: str | Process | type[ProcessClass],
        *,
        arguments: tuple[tuple[JsonValue, ...], dict[str, JsonValue]]
        | Sequence[str] = (),
        restart: bool = False,
    ) -> ProcessHandle:
        """Create.

        Args:
            process: Process.
            arguments: Arguments.
            restart: Restart.

        Returns:
            The resulting value.

        """
        if isinstance(process, Process):
            name: str = process.name
        elif isinstance(process, str):
            name = process
        else:
            name = process.name()
        encoded: Sequence[str]
        if (
            isinstance(arguments, tuple)
            and len(arguments) == Constants.structured_argument_parts
        ):
            positional, keyword = arguments
            if isinstance(positional, tuple) and isinstance(keyword, dict):
                encoded = (
                    "--orchestrator-call="
                    + dumps(
                        separators=(",", ":"),
                        obj={"args": list(positional), "kwargs": keyword},
                    ),
                )
            else:
                encoded = tuple(str(object=value) for value in arguments)
        else:
            encoded = tuple(str(object=value) for value in arguments)
        return self._orchestrator.create(
            name=name,
            context=self.name,
            arguments=encoded,
            restart=restart,
        )

    def get(self, process: str) -> ProcessHandle:
        """Get.

        Args:
            process: Process.

        Returns:
            The resulting value.

        """
        return self._orchestrator.get(name=process, context=self.name)

    def status(self, process: str) -> ProcessStatus:
        """Status.

        Args:
            process: Process.

        Returns:
            The resulting value.

        """
        return self._orchestrator.status(name=process, context=self.name)

    def list(self) -> tuple[ProcessStatus, ...]:
        """List.

        Returns:
            The resulting value.

        """
        return self._orchestrator.list(context=self.name)

    def broadcast(
        self,
        topic: str,
        payload: JsonValue = None,
        *,
        scope: str = "context",
    ) -> int:
        """Publish a live event from this context.

        Args:
            topic: Event topic.
            payload: JSON-compatible event payload.
            scope: Delivery scope.

        Returns:
            Number of workers that accepted the event.

        """
        return self._orchestrator.broadcast(
            topic=topic,
            payload=payload,
            context=self.name,
            scope=scope,
        )

    def broadcasts(
        self,
        *,
        after: int = 0,
        process: str | None = None,
    ) -> tuple[BroadcastEvent, ...]:
        """Broadcasts.

        Args:
            after: After.
            process: Process.

        Returns:
            The resulting value.

        """
        return self._orchestrator.broadcasts(
            context=self.name,
            after=after,
            process=process,
        )

    def watch_broadcasts(
        self,
        *,
        after: int = 0,
        process: str | None = None,
        poll_interval: float = 0.1,
    ) -> Iterator[BroadcastEvent]:
        """Watch broadcasts.

        Args:
            after: After.
            process: Process.
            poll_interval: Poll interval.

        Returns:
            The resulting value.

        """
        return self._orchestrator.watch_broadcasts(
            context=self.name,
            after=after,
            process=process,
            poll_interval=poll_interval,
        )

    def plan(
        self,
        process: str,
        *,
        arguments: Sequence[str] = (),
    ) -> ExecutionPlan:
        """Plan.

        Args:
            process: Process.
            arguments: Arguments.

        Returns:
            The resulting value.

        """
        return self._orchestrator.plan(
            name=process,
            context=self.name,
            arguments=arguments,
        )


class Orchestrator:
    """Orchestrator."""

    _TERMINAL: Final[frozenset[State]] = frozenset(
        {State.COMPLETED, State.FAILED, State.KILLED, State.CANCELLED},
    )

    def __init__(self, spec_path: Path) -> None:
        """Init.

        Args:
            spec_path: Spec path.

        Raises:
            OrchestratorError: When the operation cannot complete.

        """
        self.spec_path: Path = spec_path.resolve()
        try:
            self.spec: Spec = Spec(path=self.spec_path)
        except (SpecError, OSError, ValueError) as error:
            raise OrchestratorError(str(object=error)) from error
        self._launcher: Launcher = Launcher(spec_path=self.spec_path)
        self._owned: set[tuple[str, str]] = set()
        self._closed: bool = False
        self._temporary_spec: Path | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> Orchestrator:
        """From file.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        return cls(spec_path=Path(path))

    @classmethod
    def from_object_spec(cls, specification: ObjectSpec) -> Orchestrator:
        """From object spec.

        Args:
            specification: Specification.

        Returns:
            The resulting value.

        """
        return cls.from_specification(
            specification=specification.to_specification(),
        )

    @classmethod
    def from_specification(cls, specification: Specification) -> Orchestrator:
        """From specification.

        Args:
            specification: Specification.

        Returns:
            The resulting value.

        """
        specification.validate_graph()
        descriptor, temporary_name = mkstemp(
            suffix=".json",
            prefix="orchestrator-",
        )
        close(fd=descriptor)
        path: Path = specification.write(path=temporary_name)
        instance: Orchestrator = cls(spec_path=path)
        instance._temporary_spec = path
        return instance

    @classmethod
    def from_mapping(
        cls,
        specification: Mapping[str, JsonValue],
    ) -> Orchestrator:
        """From mapping.

        Args:
            specification: Specification.

        Returns:
            The resulting value.

        """
        model: Specification = Specification.from_mapping(data=specification)
        return cls.from_specification(specification=model)

    @staticmethod
    def broadcast(
        topic: str,
        payload: JsonValue = None,
        *,
        context: str,
        scope: str = "context",
    ) -> int:
        """Broadcast.

        Args:
            topic: Topic.
            payload: Payload.
            context: Context.
            scope: Scope.

        Raises:
            ProcessNotFoundError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor | None = next(
            (item for item in Discovery.all() if item.context == context),
            None,
        )
        if descriptor is None:
            msg: str = f"No live worker is available in context {context}."
            raise ProcessNotFoundError(msg)
        response: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="broadcast",
            payload={"topic": topic, "payload": payload, "scope": scope},
        )
        delivered: JsonValue = response.get("delivered", 0)
        return delivered if isinstance(delivered, int) else 0

    @staticmethod
    def broadcasts(
        *,
        context: str,
        after: int = 0,
        process: str | None = None,
    ) -> tuple[BroadcastEvent, ...]:
        """Broadcasts.

        Args:
            context: Context.
            after: After.
            process: Process.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor | None = next(
            (
                item
                for item in Discovery.all()
                if item.context == context
                and (process is None or item.name == process)
            ),
            None,
        )
        if descriptor is None:
            return ()
        response: dict[str, JsonValue] = Client.request(
            descriptor=descriptor,
            command="events",
            payload={"after": after},
        )
        raw_events: JsonValue = response.get("events", [])
        if not isinstance(raw_events, list):
            return ()
        events: list[BroadcastEvent] = []
        for value in raw_events:
            if not isinstance(value, dict):
                continue
            event_id: JsonValue = value.get("id")
            topic: JsonValue = value.get("topic")
            source: JsonValue = value.get("source")
            event_context: JsonValue = value.get("context")
            generation: JsonValue = value.get("generation")
            timestamp: JsonValue = value.get("timestamp")
            if not (
                isinstance(event_id, int)
                and isinstance(topic, str)
                and isinstance(source, str)
                and isinstance(event_context, str)
                and isinstance(generation, int)
                and isinstance(timestamp, (int, float))
            ):
                continue
            events.append(
                BroadcastEvent(
                    id=event_id,
                    topic=topic,
                    payload=value.get("payload"),
                    source=source,
                    context=event_context,
                    generation=generation,
                    timestamp=float(timestamp),
                ),
            )
        return tuple(events)

    def close(self, *, kill_owned: bool = True) -> None:
        """Close.

        Args:
            kill_owned: Kill owned.

        """
        if self._closed:
            return
        if kill_owned:
            for name, context in tuple(self._owned):
                if Discovery.find(name=name, context=context) is None:
                    continue
                try:
                    self.kill(name=name, context=context)
                except OrchestratorError:
                    continue
        self._owned.clear()
        if self._temporary_spec is not None:
            self._temporary_spec.unlink(missing_ok=True)
            self._temporary_spec = None
        self._closed = True

    def detach(self, name: str, context: str) -> None:
        """Detach.

        Args:
            name: Name.
            context: Context.

        """
        self._owned.discard((name, context))

    def validate(self) -> None:
        """Validate."""
        self.spec.validate()

    def context(self, name: str) -> Context:
        """Context.

        Args:
            name: Name.

        Returns:
            The resulting value.

        """
        return Context(orchestrator=self, name=name)

    def create(
        self,
        name: str,
        context: str,
        *,
        arguments: Sequence[str] = (),
        restart: bool = False,
    ) -> ProcessHandle:
        """Create.

        Args:
            name: Name.
            context: Context.
            arguments: Arguments.
            restart: Restart.

        Raises:
            OrchestratorError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        args: tuple[str, ...] = tuple(arguments)
        try:
            self._launcher.create(
                name=name,
                context=context,
                process_args=args,
                restart=restart,
            )
        except (SpecError, RuntimeError, OSError, ValueError) as error:
            raise OrchestratorError(str(object=error)) from error
        self._owned.add((name, context))
        return ProcessHandle(
            orchestrator=self,
            key=ProcessKey(name=name, context=context, arguments=args),
        )

    def get(self, name: str, context: str) -> ProcessHandle:
        """Get.

        Args:
            name: Name.
            context: Context.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor | None = Discovery.find(
            name=name,
            context=context,
        )
        arguments: tuple[str, ...] = descriptor.args if descriptor else ()
        return ProcessHandle(
            orchestrator=self,
            key=ProcessKey(name=name, context=context, arguments=arguments),
        )

    def status(self, name: str, context: str) -> ProcessStatus:
        """Status.

        Args:
            name: Name.
            context: Context.

        Raises:
            OrchestratorError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor = self._descriptor(name=name, context=context)
        try:
            data: dict[str, JsonValue] = Client.request(
                descriptor=descriptor,
                command="info",
            )
        except OSError as error:
            raise OrchestratorError(str(object=error)) from error
        return self._status(descriptor=descriptor, data=data)

    def watch_broadcasts(
        self,
        *,
        context: str,
        after: int = 0,
        process: str | None = None,
        poll_interval: float = 0.1,
    ) -> Iterator[BroadcastEvent]:
        """Watch broadcasts.

        Args:
            context: Context.
            after: After.
            process: Process.
            poll_interval: Poll interval.

        Yields:
            The next resulting value.

        """
        cursor: int = after
        while True:
            events: tuple[BroadcastEvent, ...] = self.broadcasts(
                context=context,
                after=cursor,
                process=process,
            )
            for event in events:
                cursor = max(cursor, event.id)
                yield event
            sleep(max(poll_interval, 0.01))

    def list(
        self,
        *,
        context: str | None = None,
        name: str | None = None,
    ) -> tuple[ProcessStatus, ...]:
        """List.

        Args:
            context: Context.
            name: Name.

        Returns:
            The resulting value.

        """
        statuses: list[ProcessStatus] = []
        for descriptor in Discovery.all():
            if context is not None and descriptor.context != context:
                continue
            if name is not None and descriptor.name != name:
                continue
            try:
                statuses.append(
                    self._status(
                        descriptor=descriptor,
                        data=Client.request(
                            descriptor=descriptor,
                            command="info",
                        ),
                    ),
                )
            except OSError:
                continue
        return tuple(statuses)

    def pause(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Pause.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.PAUSE,
            recursive=recursive,
        )

    def resume(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Resume.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.RESUME,
            recursive=recursive,
        )

    def reset(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Reset.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.RESET,
            recursive=recursive,
        )

    def restart(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Restart.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.RESTART,
            recursive=recursive,
        )

    def kill(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Kill.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.KILL,
            recursive=recursive,
        )

    def cancel(
        self,
        name: str,
        context: str,
        *,
        recursive: bool = False,
    ) -> ProcessStatus:
        """Cancel.

        Args:
            name: Name.
            context: Context.
            recursive: Recursive.

        Returns:
            The resulting value.

        """
        return self._apply(
            name=name,
            context=context,
            action=ProcessAction.CANCEL,
            recursive=recursive,
        )

    def wait(
        self,
        name: str,
        context: str,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.1,
    ) -> ProcessStatus:
        """Wait.

        Args:
            name: Name.
            context: Context.
            timeout: Timeout.
            poll_interval: Poll interval.

        Raises:
            WaitTimeoutError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        started: float = monotonic()
        while True:
            status: ProcessStatus = self.status(name=name, context=context)
            if status.terminal:
                return status
            if timeout is not None and monotonic() - started >= timeout:
                msg: str = f"Timed out waiting for {name}/{context}."
                raise WaitTimeoutError(msg)
            sleep(max(poll_interval, 0.01))

    def watch(
        self,
        name: str,
        context: str,
        *,
        poll_interval: float = 0.25,
        changes_only: bool = True,
    ) -> Iterator[ProcessEvent]:
        """Watch.

        Args:
            name: Name.
            context: Context.
            poll_interval: Poll interval.
            changes_only: Changes only.

        Yields:
            The next resulting value.

        """
        previous: ProcessStatus | None = None
        while True:
            status: ProcessStatus = self.status(name=name, context=context)
            changed: bool = (
                previous is None
                or status.state is not previous.state
                or status.progress != previous.progress
                or (status.reason != previous.reason)
                or (status.children != previous.children)
            )
            if changed or not changes_only:
                yield ProcessEvent(
                    status=status,
                    previous_state=previous.state
                    if previous is not None
                    else None,
                )
            if status.terminal:
                return
            previous = status
            sleep(max(poll_interval, 0.01))

    def subscribe(
        self,
        name: str,
        context: str,
        callback: Callable[[ProcessEvent], None],
        *,
        poll_interval: float = 0.25,
        changes_only: bool = True,
    ) -> ProcessStatus:
        """Subscribe.

        Args:
            name: Name.
            context: Context.
            callback: Callback.
            poll_interval: Poll interval.
            changes_only: Changes only.

        Raises:
            OrchestratorError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        final: ProcessStatus | None = None
        for event in self.watch(
            name=name,
            context=context,
            poll_interval=poll_interval,
            changes_only=changes_only,
        ):
            callback(event)
            final = event.status
        if final is None:
            msg: str = f"No events received for {name}/{context}."
            raise OrchestratorError(msg)
        return final

    def plan(
        self,
        name: str,
        context: str,
        *,
        arguments: Sequence[str] = (),
    ) -> ExecutionPlan:
        """Plan.

        Args:
            name: Name.
            context: Context.
            arguments: Arguments.

        Returns:
            The resulting value.

        """
        self.spec.process(name=name)
        entries: list[PlanEntry] = []
        seen: set[str] = set()

        def visit(process: str) -> None:
            """Visit.

            Args:
                process: Process.

            """
            if process in seen:
                return
            seen.add(process)
            descriptor: Descriptor | None = Discovery.find(
                name=process,
                context=context,
            )
            entries.append(
                PlanEntry(
                    key=ProcessKey(
                        name=process,
                        context=context,
                        arguments=tuple(arguments) if process == name else (),
                    ),
                    action="REUSE" if descriptor is not None else "CREATE",
                    pid=descriptor.pid if descriptor is not None else None,
                ),
            )
            for child in self.spec.refs(
                config=self.spec.process(name=process),
            ):
                visit(process=child)

        visit(process=name)
        return ExecutionPlan(
            root=ProcessKey(
                name=name,
                context=context,
                arguments=tuple(arguments),
            ),
            entries=tuple(entries),
        )

    def __enter__(self) -> Self:
        """Enter.

        Raises:
            OrchestratorError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        if self._closed:
            msg: str = "Orchestrator is closed."
            raise OrchestratorError(msg)
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Exit.

        Args:
            _exc_type: Exc type.
            _exc: Exc.
            _traceback: Traceback.

        """
        self.close()

    @staticmethod
    def _descriptor(name: str, context: str) -> Descriptor:
        """Descriptor.

        Args:
            name: Name.
            context: Context.

        Raises:
            ProcessNotFoundError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        descriptor: Descriptor | None = Discovery.find(
            name=name,
            context=context,
        )
        if descriptor is None:
            msg: str = f"No live process {name}/{context}."
            raise ProcessNotFoundError(msg)
        return descriptor

    @staticmethod
    def _status(
        descriptor: Descriptor,
        data: Mapping[str, JsonValue],
    ) -> ProcessStatus:
        """Status.

        Args:
            descriptor: Descriptor.
            data: Data.

        Returns:
            The resulting value.

        """
        state_value: JsonValue = data.get("state", State.STARTING.value)
        try:
            state: State = State(str(object=state_value))
        except ValueError:
            state = State.STARTING
        progress_value: JsonValue = data.get("progress", 0)
        progress: int = (
            int(progress_value)
            if isinstance(progress_value, (int, float))
            else 0
        )
        exit_value: JsonValue = data.get("exit_code")
        exit_code: int | None = (
            int(exit_value) if isinstance(exit_value, (int, float)) else None
        )
        attempts_value: JsonValue = data.get("attempts", 0)
        attempts: int = (
            int(attempts_value)
            if isinstance(attempts_value, (int, float))
            else 0
        )
        generation_value: JsonValue = data.get("generation", 1)
        generation: int = (
            int(generation_value)
            if isinstance(generation_value, (int, float))
            else 1
        )
        children_value: JsonValue = data.get("children", {})
        children: Mapping[str, JsonValue] = (
            children_value if isinstance(children_value, dict) else {}
        )
        return ProcessStatus(
            key=ProcessKey(
                name=descriptor.name,
                context=descriptor.context,
                arguments=descriptor.args,
            ),
            state=state,
            progress=progress,
            pid=descriptor.pid,
            reason=str(object=data.get("reason", "")),
            exit_code=exit_code,
            attempts=attempts,
            generation=generation,
            children=children,
            custom_status=data.get("custom_status"),
        )

    def _apply(
        self,
        name: str,
        context: str,
        action: ProcessAction,
        *,
        recursive: bool,
    ) -> ProcessStatus:
        """Apply.

        Args:
            name: Name.
            context: Context.
            action: Action.
            recursive: Recursive.

        Raises:
            OrchestratorError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        if recursive:
            for child in self.spec.refs(config=self.spec.process(name=name)):
                if Discovery.find(name=child, context=context) is not None:
                    self._apply(
                        name=child,
                        context=context,
                        action=action,
                        recursive=True,
                    )
        descriptor: Descriptor = self._descriptor(name=name, context=context)
        try:
            data: dict[str, JsonValue] = Client.request(
                descriptor=descriptor,
                command=action.value,
            )
        except OSError as error:
            raise OrchestratorError(str(object=error)) from error
        return self._status(descriptor=descriptor, data=data)
