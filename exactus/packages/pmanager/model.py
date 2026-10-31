# Copyright (c) 2026 João Lopes.
"""Validated mutable configuration model for orchestration specifications."""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps, loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, Self, TypedDict, Unpack, cast, final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
type ModelValue = (
    bool
    | int
    | float
    | str
    | list["ModelValue"]
    | dict[str, "ModelValue"]
    | None
)


class ModelValidationError(ValueError):
    """Modelvalidationerror."""


def _non_empty(value: str, field_name: str) -> str:
    """Non empty.

    Args:
        value: Value.
        field_name: Field name.
                        definition: Definition being parsed.

    Raises:
        ModelValidationError: When the operation cannot complete.

    Returns:
        The resulting value.

    """
    if not value.strip():
        msg: str = f"{field_name} cannot be empty."
        raise ModelValidationError(msg)
    return value


@dataclass(init=False)
class ArgumentPolicy:
    """Argumentpolicy."""

    _policy: str
    _values: tuple[str, ...]

    def __init__(
        self,
        policy: str = "inherit",
        values: tuple[str, ...] = (),
    ) -> None:
        """Init.

        Args:
            policy: Policy.
            values: Values.

        """
        self.policy = policy
        self.values = values

    @classmethod
    def from_mapping(cls, data: Mapping[str, ModelValue]) -> Self:
        """From mapping.

        Args:
            data: Data.

        Returns:
            The resulting value.

        """
        raw: ModelValue = data.get("values", [])
        values: tuple[str, ...] = (
            tuple(item for item in raw if isinstance(item, str))
            if isinstance(raw, list)
            else ()
        )
        policy: ModelValue = data.get("policy", "inherit")
        return cls(
            policy=policy if isinstance(policy, str) else "inherit",
            values=values,
        )

    @property
    def policy(self) -> str:
        """Policy.

        Returns:
            The resulting value.

        """
        return self._policy

    @policy.setter
    def policy(self, value: str) -> None:
        """Policy.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        allowed: set[str] = {"inherit", "none", "replace", "merge"}
        if value not in allowed:
            msg: str = f"Invalid argument policy: {value}."
            raise ModelValidationError(msg)
        self._policy = value

    @property
    def values(self) -> tuple[str, ...]:
        """Values.

        Returns:
            The resulting value.

        """
        return self._values

    @values.setter
    def values(self, value: Iterable[ModelValue]) -> None:
        """Values.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                msg: str = "Argument values must contain strings."
                raise ModelValidationError(msg)
            items.append(item)
        self._values = tuple(items)

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        data: dict[str, ModelValue] = {"policy": self.policy}
        if self.values:
            data["values"] = cast(
                typ="list[ModelValue]",
                val=list(self.values),
            )
        return data


@dataclass(init=False)
class Identity:
    """Identity."""

    _include_arguments: bool

    def __init__(self, *, include_arguments: bool = False) -> None:
        """Init.

        Args:
            include_arguments: Include arguments.

        """
        self.include_arguments = include_arguments

    @property
    def include_arguments(self) -> bool:
        """Include arguments.

        Returns:
            The resulting value.

        """
        return self._include_arguments

    @include_arguments.setter
    def include_arguments(self, value: ModelValue) -> None:
        """Include arguments.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, bool):
            msg: str = "include_arguments must be bool."
            raise ModelValidationError(msg)
        self._include_arguments = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {"include_arguments": self.include_arguments}


@dataclass(init=False)
class Timeouts:
    """Timeouts."""

    _run_seconds: float | None
    _dependency_seconds: float | None
    _waiting_seconds: float | None
    _on_timeout: str

    def __init__(
        self,
        run_seconds: float | None = None,
        dependency_seconds: float | None = None,
        waiting_seconds: float | None = None,
        on_timeout: str = "fail",
    ) -> None:
        """Init.

        Args:
            run_seconds: Run seconds.
            dependency_seconds: Dependency seconds.
            waiting_seconds: Waiting seconds.
            on_timeout: On timeout.

        """
        self.run_seconds = run_seconds
        self.dependency_seconds = dependency_seconds
        self.waiting_seconds = waiting_seconds
        self.on_timeout = on_timeout

    @property
    def run_seconds(self) -> float | None:
        """Run seconds.

        Returns:
            The resulting value.

        """
        return self._run_seconds

    @run_seconds.setter
    def run_seconds(self, value: float | None) -> None:
        """Run seconds.

        Args:
            value: Value.

        """
        self._run_seconds = self._seconds(value=value, name="run_seconds")

    @property
    def dependency_seconds(self) -> float | None:
        """Dependency seconds.

        Returns:
            The resulting value.

        """
        return self._dependency_seconds

    @dependency_seconds.setter
    def dependency_seconds(self, value: float | None) -> None:
        """Dependency seconds.

        Args:
            value: Value.

        """
        self._dependency_seconds = self._seconds(
            value=value,
            name="dependency_seconds",
        )

    @property
    def waiting_seconds(self) -> float | None:
        """Set waiting seconds.

        Returns:
            The resulting value.

        """
        return self._waiting_seconds

    @waiting_seconds.setter
    def waiting_seconds(self, value: float | None) -> None:
        """Set waiting seconds.

        Args:
            value: Value.

        """
        self._waiting_seconds = self._seconds(
            value=value,
            name="waiting_seconds",
        )

    @property
    def on_timeout(self) -> str:
        """On timeout.

        Returns:
            The resulting value.

        """
        return self._on_timeout

    @on_timeout.setter
    def on_timeout(self, value: str) -> None:
        """On timeout.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"fail", "cancel", "kill"}:
            msg: str = f"Invalid timeout action: {value}."
            raise ModelValidationError(msg)
        self._on_timeout = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {
            "run_seconds": self.run_seconds,
            "dependency_seconds": self.dependency_seconds,
            "waiting_seconds": self.waiting_seconds,
            "on_timeout": self.on_timeout,
        }

    @staticmethod
    def _seconds(value: float | None, name: str) -> float | None:
        """Seconds.

        Args:
            value: Value.
            name: Name.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        if value is not None and value <= 0:
            msg: str = f"{name} must be positive or None."
            raise ModelValidationError(msg)
        return value


@dataclass(init=False)
class Retry:
    """Retry."""

    _max_attempts: int
    _delay_seconds: float
    _backoff: float
    _max_delay_seconds: float

    def __init__(
        self,
        max_attempts: int = 1,
        delay_seconds: float = 1.0,
        backoff: float = 2.0,
        max_delay_seconds: float = 30.0,
    ) -> None:
        """Init.

        Args:
            max_attempts: Max attempts.
            delay_seconds: Delay seconds.
            backoff: Backoff.
            max_delay_seconds: Max delay seconds.

        """
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.backoff = backoff
        self.max_delay_seconds = max_delay_seconds

    @property
    def max_attempts(self) -> int:
        """Max attempts.

        Returns:
            The resulting value.

        """
        return self._max_attempts

    @max_attempts.setter
    def max_attempts(self, value: ModelValue) -> None:
        """Max attempts.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg: str = "max_attempts must be an int >= 1."
            raise ModelValidationError(msg)
        self._max_attempts = value

    @property
    def delay_seconds(self) -> float:
        """Delay seconds.

        Returns:
            The resulting value.

        """
        return self._delay_seconds

    @delay_seconds.setter
    def delay_seconds(self, value: ModelValue) -> None:
        """Delay seconds.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            msg: str = "delay_seconds must be a number >= 0."
            raise ModelValidationError(msg)
        self._delay_seconds = float(value)

    @property
    def backoff(self) -> float:
        """Backoff.

        Returns:
            The resulting value.

        """
        return self._backoff

    @backoff.setter
    def backoff(self, value: ModelValue) -> None:
        """Backoff.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 1
        ):
            msg: str = "backoff must be a number >= 1."
            raise ModelValidationError(msg)
        self._backoff = float(value)

    @property
    def max_delay_seconds(self) -> float:
        """Max delay seconds.

        Returns:
            The resulting value.

        """
        return self._max_delay_seconds

    @max_delay_seconds.setter
    def max_delay_seconds(self, value: ModelValue) -> None:
        """Max delay seconds.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            msg: str = "max_delay_seconds must be a number >= 0."
            raise ModelValidationError(msg)
        self._max_delay_seconds = float(value)

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {
            "max_attempts": self.max_attempts,
            "delay_seconds": self.delay_seconds,
            "backoff": self.backoff,
            "max_delay_seconds": self.max_delay_seconds,
        }


@dataclass(init=False)
class Executor:
    """Executor."""

    _type: str
    _command: tuple[str, ...]
    _cwd: str | None

    def __init__(
        self,
        type_: str = "counter",
        command: tuple[str, ...] = (),
        cwd: str | None = None,
    ) -> None:
        """Init.

        Args:
            type_: Type.
            command: Command.
            cwd: Cwd.

        """
        self.type_ = type_
        self.command = command
        self.cwd = cwd

    @property
    def type_(self) -> str:
        """Type.

        Returns:
            The resulting value.

        """
        return self._type

    @type_.setter
    def type_(self, value: str) -> None:
        """Type.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"counter", "command", "python", "python_class"}:
            msg: str = f"Invalid executor type: {value}."
            raise ModelValidationError(msg)
        self._type = value

    @property
    def command(self) -> tuple[str, ...]:
        """Command.

        Returns:
            The resulting value.

        """
        return self._command

    @command.setter
    def command(self, value: Iterable[ModelValue]) -> None:
        """Command.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                msg: str = "Executor command must contain strings."
                raise ModelValidationError(msg)
            items.append(item)
        self._command = tuple(items)

    @property
    def cwd(self) -> str | None:
        """Cwd.

        Returns:
            The resulting value.

        """
        return self._cwd

    @cwd.setter
    def cwd(self, value: str | None) -> None:
        """Cwd.

        Args:
            value: Value.

        """
        if value is not None:
            _non_empty(value=value, field_name="cwd")
        self._cwd = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        data: dict[str, ModelValue] = {"type": self.type_}
        if self.command:
            data["command"] = cast(
                typ="list[ModelValue]",
                val=list(self.command),
            )
        if self.cwd is not None:
            data["cwd"] = self.cwd
        return data


@dataclass(init=False)
class ProcessReference:
    """Processreference.

    Attributes:
        arguments: Arguments.

    """

    _process: str
    _scope: str
    _completion: str
    arguments: ArgumentPolicy

    def __init__(
        self,
        process: str,
        scope: str = "context",
        completion: str = "success",
        arguments: ArgumentPolicy | None = None,
    ) -> None:
        """Init.

        Args:
            process: Process.
            scope: Scope.
            completion: Completion.
            arguments: Arguments.

        """
        self.process = process
        self.scope = scope
        self.completion = completion
        self.arguments = arguments or ArgumentPolicy()

    @property
    def process(self) -> str:
        """Process.

        Returns:
            The resulting value.

        """
        return self._process

    @process.setter
    def process(self, value: str) -> None:
        """Process.

        Args:
            value: Value.

        """
        self._process = _non_empty(value=value, field_name="process")

    @property
    def scope(self) -> str:
        """Scope.

        Returns:
            The resulting value.

        """
        return self._scope

    @scope.setter
    def scope(self, value: str) -> None:
        """Scope.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"context", "global"}:
            msg: str = f"Invalid reference scope: {value}."
            raise ModelValidationError(msg)
        self._scope = value

    @property
    def completion(self) -> str:
        """Completion.

        Returns:
            The resulting value.

        """
        return self._completion

    @completion.setter
    def completion(self, value: str) -> None:
        """Completion.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"success", "terminal", "running"}:
            msg: str = f"Invalid completion mode: {value}."
            raise ModelValidationError(msg)
        self._completion = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {
            "process": self.process,
            "scope": self.scope,
            "completion": self.completion,
            "arguments": self.arguments.to_mapping(),
        }


@dataclass(init=False)
class Concurrency:
    """Concurrency."""

    _group: str
    _scope: str
    _max_running: int
    _on_conflict: str
    _queue: str

    def __init__(
        self,
        group: str,
        scope: str = "context",
        max_running: int = 1,
        on_conflict: str = "wait",
        queue: str = "fifo",
    ) -> None:
        """Init.

        Args:
            group: Group.
            scope: Scope.
            max_running: Max running.
            on_conflict: On conflict.
            queue: Queue.

        """
        self.group = group
        self.scope = scope
        self.max_running = max_running
        self.on_conflict = on_conflict
        self.queue = queue

    @property
    def group(self) -> str:
        """Group.

        Returns:
            The resulting value.

        """
        return self._group

    @group.setter
    def group(self, value: str) -> None:
        """Group.

        Args:
            value: Value.

        """
        self._group = _non_empty(value=value, field_name="group")

    @property
    def scope(self) -> str:
        """Scope.

        Returns:
            The resulting value.

        """
        return self._scope

    @scope.setter
    def scope(self, value: str) -> None:
        """Scope.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"context", "global"}:
            msg: str = f"Invalid concurrency scope: {value}."
            raise ModelValidationError(msg)
        self._scope = value

    @property
    def max_running(self) -> int:
        """Max running.

        Returns:
            The resulting value.

        """
        return self._max_running

    @max_running.setter
    def max_running(self, value: ModelValue) -> None:
        """Max running.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg: str = "max_running must be an int >= 1."
            raise ModelValidationError(msg)
        self._max_running = value

    @property
    def on_conflict(self) -> str:
        """On conflict.

        Returns:
            The resulting value.

        """
        return self._on_conflict

    @on_conflict.setter
    def on_conflict(self, value: str) -> None:
        """On conflict.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"wait", "fail"}:
            msg: str = f"Invalid conflict policy: {value}."
            raise ModelValidationError(msg)
        self._on_conflict = value

    @property
    def queue(self) -> str:
        """Queue.

        Returns:
            The resulting value.

        """
        return self._queue

    @queue.setter
    def queue(self, value: str) -> None:
        """Queue.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"fifo", "priority_fifo"}:
            msg: str = f"Invalid queue policy: {value}."
            raise ModelValidationError(msg)
        self._queue = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {
            "group": self.group,
            "scope": self.scope,
            "max_running": self.max_running,
            "on_conflict": self.on_conflict,
            "queue": self.queue,
        }


@dataclass(init=False)
class Resource:
    """Resource."""

    _capacity: int

    def __init__(self, capacity: int = 1) -> None:
        """Init.

        Args:
            capacity: Capacity.

        """
        self.capacity = capacity

    @property
    def capacity(self) -> int:
        """Capacity.

        Returns:
            The resulting value.

        """
        return self._capacity

    @capacity.setter
    def capacity(self, value: ModelValue) -> None:
        """Capacity.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg: str = "capacity must be an int >= 1."
            raise ModelValidationError(msg)
        self._capacity = value

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        return {"capacity": self.capacity}


@dataclass(init=False)
class GlobalConfig:
    """Store validated global defaults, queues, resources, and rules.

    Attributes:
        defaults: Default configuration values.
        rules: Global rule definitions.

    """

    defaults: dict[str, ModelValue]
    _queue_strategy: str
    _resources: dict[str, Resource]
    rules: list[ModelValue]

    def __init__(
        self,
        defaults: dict[str, ModelValue] | None = None,
        queue_strategy: str = "priority_fifo",
        resources: dict[str, Resource] | None = None,
        rules: list[ModelValue] | None = None,
    ) -> None:
        """Initialize validated global configuration.

        Args:
            defaults: Default configuration values.
            queue_strategy: Queue ordering strategy.
            resources: Named resource capacities.
            rules: Global rule definitions.

        """
        self.defaults = dict(defaults or {})
        self.queue_strategy = queue_strategy
        self.resources = dict(resources or {})
        self.rules = list(rules or [])

    @property
    def queue_strategy(self) -> str:
        """Return the queue strategy.

        Returns:
            Configured queue strategy.

        """
        return self._queue_strategy

    @queue_strategy.setter
    def queue_strategy(self, value: str) -> None:
        """Set and validate the queue strategy.

        Args:
            value: Queue strategy.

        Raises:
            ModelValidationError: If the strategy is unsupported.

        """
        if value not in {"fifo", "priority_fifo"}:
            msg: str = f"Invalid queue strategy: {value}."
            raise ModelValidationError(msg)
        self._queue_strategy = value

    @property
    def resources(self) -> dict[str, Resource]:
        """Return configured resources.

        Returns:
            Named resource definitions.

        """
        return self._resources

    @resources.setter
    def resources(
        self,
        value: dict[str, Resource] | dict[ModelValue, ModelValue],
    ) -> None:
        """Set and validate configured resources.

        Args:
            value: Named resource definitions.

        Raises:
            ModelValidationError: If a resource value is invalid.

        """
        validated: dict[str, Resource] = {}
        for name, resource in value.items():
            if not isinstance(name, str) or not isinstance(resource, Resource):
                msg: str = "resources must map names to Resource."
                raise ModelValidationError(msg)
            validated[name] = resource
        self._resources = validated

    def to_mapping(self) -> dict[str, ModelValue]:
        """Serialize global configuration.

        Returns:
            Canonical mapping representation.

        """
        return {
            "defaults": self.defaults,
            "queue": {"strategy": self.queue_strategy},
            "resources": {
                name: resource.to_mapping()
                for name, resource in self.resources.items()
            },
            "rules": self.rules,
        }


class ProcessDefinitionFields(TypedDict, total=False):
    """Process definition fields.

    Attributes:
        extends: Extends.
        executor: Executor.
        depends_on: Depends on.
        children: Children.
        mode: Mode.
        launch: Launch.
        concurrency: Concurrency.
        duration_seconds: Duration seconds.
        tick_seconds: Tick seconds.
        extra: Extra.

    """

    extends: str | None
    executor: Executor | None
    depends_on: list[ProcessReference] | None
    children: list[ProcessReference] | None
    mode: str | None
    launch: str
    concurrency: Concurrency | None
    duration_seconds: float | None
    tick_seconds: float | None
    extra: dict[str, ModelValue] | None


@final
class Constants:
    """Group module-level constants.

    Attributes:
        definition_field_names: Grouped module constant.

    """

    definition_field_names: Final[frozenset[str]] = frozenset(
        {
            "extends",
            "executor",
            "depends_on",
            "children",
            "mode",
            "launch",
            "concurrency",
            "duration_seconds",
            "tick_seconds",
            "extra",
        },
    )


@dataclass(init=False)
class ProcessDefinition:
    """Processdefinition.

    Attributes:
        executor: Executor.
        concurrency: Concurrency.
        extra: Extra.

    """

    _extends: str | None
    executor: Executor | None
    _depends_on: list[ProcessReference]
    _children: list[ProcessReference]
    _mode: str | None
    _launch: str
    concurrency: Concurrency | None
    _duration_seconds: float | None
    _tick_seconds: float | None
    extra: dict[str, ModelValue]

    def __init__(self, **fields: Unpack[ProcessDefinitionFields]) -> None:
        """Init.

        Args:
            fields: Process definition fields.

        Raises:
            TypeError: When an unknown field is provided.

        """
        unknown: list[str] = sorted(
            name
            for name in fields
            if name not in Constants.definition_field_names
        )
        if unknown:
            msg: str = (
                "__init__() got unexpected keyword argument(s): "
                f"{', '.join(repr(name) for name in unknown)}"
            )
            raise TypeError(msg)
        self.extends = fields.get("extends")
        self.executor = fields.get("executor")
        self.depends_on = list(fields.get("depends_on") or [])
        self.children = list(fields.get("children") or [])
        self.mode = fields.get("mode")
        self.launch = fields.get("launch", "parallel")
        self.concurrency = fields.get("concurrency")
        self.duration_seconds = fields.get("duration_seconds")
        self.tick_seconds = fields.get("tick_seconds")
        self.extra = dict(fields.get("extra") or {})

    @property
    def extends(self) -> str | None:
        """Set the inherited template.

        Returns:
            The resulting value.

        """
        return self._extends

    @extends.setter
    def extends(self, value: str | None) -> None:
        """Set the inherited template.

        Args:
            value: Value.

        """
        if value is not None:
            _non_empty(value=value, field_name="extends")
        self._extends = value

    @property
    def mode(self) -> str | None:
        """Mode.

        Returns:
            The resulting value.

        """
        return self._mode

    @mode.setter
    def mode(self, value: str | None) -> None:
        """Mode.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {None, "fanout_join"}:
            msg: str = f"Invalid process mode: {value}."
            raise ModelValidationError(msg)
        self._mode = value

    @property
    def launch(self) -> str:
        """Launch.

        Returns:
            The resulting value.

        """
        return self._launch

    @launch.setter
    def launch(self, value: str) -> None:
        """Launch.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if value not in {"parallel", "serial"}:
            msg: str = f"Invalid launch mode: {value}."
            raise ModelValidationError(msg)
        self._launch = value

    @property
    def duration_seconds(self) -> float | None:
        """Duration seconds.

        Returns:
            The resulting value.

        """
        return self._duration_seconds

    @duration_seconds.setter
    def duration_seconds(self, value: float | None) -> None:
        """Duration seconds.

        Args:
            value: Value.

        """
        self._duration_seconds = self._duration(
            value=value,
            name="duration_seconds",
        )

    @property
    def tick_seconds(self) -> float | None:
        """Tick seconds.

        Returns:
            The resulting value.

        """
        return self._tick_seconds

    @tick_seconds.setter
    def tick_seconds(self, value: float | None) -> None:
        """Tick seconds.

        Args:
            value: Value.

        """
        self._tick_seconds = self._duration(value=value, name="tick_seconds")

    @property
    def depends_on(self) -> list[ProcessReference]:
        """Depends on.

        Returns:
            The resulting value.

        """
        return self._depends_on

    @depends_on.setter
    def depends_on(
        self,
        value: Iterable[ProcessReference | ModelValue],
    ) -> None:
        """Depends on.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        items: list[ProcessReference] = []
        for item in value:
            if not isinstance(item, ProcessReference):
                msg: str = "depends_on requires ProcessReference."
                raise ModelValidationError(msg)
            items.append(item)
        self._depends_on = items

    @property
    def children(self) -> list[ProcessReference]:
        """Children.

        Returns:
            The resulting value.

        """
        return self._children

    @children.setter
    def children(self, value: Iterable[ProcessReference | ModelValue]) -> None:
        """Children.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        items: list[ProcessReference] = []
        for item in value:
            if not isinstance(item, ProcessReference):
                msg: str = "children requires ProcessReference."
                raise ModelValidationError(msg)
            items.append(item)
        self._children = items

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        data: dict[str, ModelValue] = dict(self.extra)
        if self.extends is not None:
            data["extends"] = self.extends
        if self.executor is not None:
            data["executor"] = self.executor.to_mapping()
        if self.depends_on:
            data["depends_on"] = [
                item.to_mapping() for item in self.depends_on
            ]
        if self.children:
            data["children"] = [item.to_mapping() for item in self.children]
        if self.mode is not None:
            data["mode"] = self.mode
        if self.mode is not None or self.children:
            data["launch"] = self.launch
        if self.concurrency is not None:
            data["concurrency"] = self.concurrency.to_mapping()
        if self.duration_seconds is not None:
            data["duration_seconds"] = self.duration_seconds
        if self.tick_seconds is not None:
            data["tick_seconds"] = self.tick_seconds
        return data

    @staticmethod
    def _duration(value: float | None, name: str) -> float | None:
        """Duration.

        Args:
            value: Value.
            name: Name.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        if value is not None and value <= 0:
            msg: str = f"{name} must be positive or None."
            raise ModelValidationError(msg)
        return value


def _spec_version(data: Mapping[str, ModelValue]) -> int:
    """Parse the specification version.

    Args:
        data: Data.

    Raises:
        ModelValidationError: When the version is not an integer.

    Returns:
        The resulting value.

    """
    version: ModelValue = data.get("version", 2)
    if not isinstance(version, int) or isinstance(version, bool):
        msg: str = "version must be an int."
        raise ModelValidationError(msg)
    return version


def _global_config(data: Mapping[str, ModelValue]) -> GlobalConfig:
    """Parse the global configuration section.

    Args:
        data: Data.

    Returns:
        The resulting value.

    """
    global_config: GlobalConfig = GlobalConfig()
    global_raw: ModelValue = data.get("global", {})
    if not isinstance(global_raw, dict):
        return global_config
    queue: ModelValue = global_raw.get("queue", {})
    if isinstance(queue, dict):
        strategy: ModelValue = queue.get("strategy", "priority_fifo")
        if isinstance(strategy, str):
            global_config.queue_strategy = strategy
    resources: ModelValue = global_raw.get("resources", {})
    if isinstance(resources, dict):
        parsed_resources: dict[str, Resource] = {}
        for name, resource in resources.items():
            if isinstance(resource, dict):
                capacity: ModelValue = resource.get("capacity", 1)
                if isinstance(capacity, int):
                    parsed_resources[name] = Resource(capacity=capacity)
        global_config.resources = parsed_resources
    defaults: ModelValue = global_raw.get("defaults", {})
    if isinstance(defaults, dict):
        global_config.defaults = dict(defaults)
    rules: ModelValue = global_raw.get("rules", [])
    if isinstance(rules, list):
        global_config.rules = list(rules)
    return global_config


def _ref_arguments(args_raw: ModelValue) -> ArgumentPolicy:
    """Parse a reference argument policy.

    Args:
        args_raw: Raw arguments.

    Returns:
        The resulting value.

    """
    return (
        ArgumentPolicy.from_mapping(data=args_raw)
        if isinstance(args_raw, dict)
        else ArgumentPolicy()
    )


def _references(
    definition: Mapping[str, ModelValue],
    field_name: str,
) -> list[ProcessReference]:
    """Parse process references from a definition field.

    Args:
        definition: Definition being parsed.
        field_name: Field name.

    Returns:
        The resulting value.

    """
    parsed: list[ProcessReference] = []
    raw_refs: ModelValue = definition.get(field_name, [])
    if not isinstance(raw_refs, list):
        return parsed
    for raw_ref in raw_refs:
        if isinstance(raw_ref, str):
            parsed.append(ProcessReference(process=raw_ref))
            continue
        if not isinstance(raw_ref, dict):
            continue
        process: ModelValue = raw_ref.get("process")
        if not isinstance(process, str):
            continue
        scope: ModelValue = raw_ref.get("scope", "context")
        completion: ModelValue = raw_ref.get("completion", "success")
        parsed.append(
            ProcessReference(
                process=process,
                scope=scope if isinstance(scope, str) else "context",
                completion=completion
                if isinstance(completion, str)
                else "success",
                arguments=_ref_arguments(
                    args_raw=raw_ref.get("arguments", {}),
                ),
            ),
        )
    return parsed


def _executor(raw_definition: Mapping[str, ModelValue]) -> Executor | None:
    """Parse an executor from a definition.

    Args:
        raw_definition: Definition being parsed.

    Returns:
        The resulting value.

    """
    executor_raw: ModelValue = raw_definition.get("executor")
    if not isinstance(executor_raw, dict):
        return None
    executor_type: ModelValue = executor_raw.get("type", "counter")
    command_raw: ModelValue = executor_raw.get("command", [])
    cwd_raw: ModelValue = executor_raw.get("cwd")
    return Executor(
        type_=executor_type if isinstance(executor_type, str) else "counter",
        command=tuple(item for item in command_raw if isinstance(item, str))
        if isinstance(command_raw, list)
        else (),
        cwd=cwd_raw if isinstance(cwd_raw, str) else None,
    )


def _concurrency(
    raw_definition: Mapping[str, ModelValue],
) -> Concurrency | None:
    """Parse a concurrency policy from a definition.

    Args:
        raw_definition: Definition being parsed.

    Returns:
        The resulting value.

    """
    concurrency_raw: ModelValue = raw_definition.get("concurrency")
    if not isinstance(concurrency_raw, dict):
        return None
    group: ModelValue = concurrency_raw.get("group")
    if not isinstance(group, str):
        return None
    scope_value: ModelValue = concurrency_raw.get("scope", "context")
    max_value: ModelValue = concurrency_raw.get("max_running", 1)
    conflict_value: ModelValue = concurrency_raw.get("on_conflict", "wait")
    queue_value: ModelValue = concurrency_raw.get("queue", "fifo")
    return Concurrency(
        group=group,
        scope=scope_value if isinstance(scope_value, str) else "context",
        max_running=max_value
        if isinstance(max_value, int) and (not isinstance(max_value, bool))
        else 1,
        on_conflict=conflict_value
        if isinstance(conflict_value, str)
        else "wait",
        queue=queue_value if isinstance(queue_value, str) else "fifo",
    )


def _definition(key: str, name: str, raw: ModelValue) -> ProcessDefinition:
    """Parse a single process definition.

    Args:
        key: Section key.
        name: Process name.
        raw: Raw definition.

    Raises:
        ModelValidationError: When the definition is not an object.

    Returns:
        The resulting value.

    """
    if not isinstance(raw, dict):
        msg: str = f"{key}.{name} must be an object."
        raise ModelValidationError(msg)
    extends_raw: ModelValue = raw.get("extends")
    mode_raw: ModelValue = raw.get("mode")
    launch_raw: ModelValue = raw.get("launch", "parallel")
    duration_raw: ModelValue = raw.get("duration_seconds")
    tick_raw: ModelValue = raw.get("tick_seconds")
    return ProcessDefinition(
        extends=extends_raw if isinstance(extends_raw, str) else None,
        executor=_executor(raw_definition=raw),
        depends_on=_references(definition=raw, field_name="depends_on"),
        children=_references(definition=raw, field_name="children"),
        mode=mode_raw if isinstance(mode_raw, str) else None,
        launch=launch_raw if isinstance(launch_raw, str) else "parallel",
        concurrency=_concurrency(raw_definition=raw),
        duration_seconds=float(duration_raw)
        if isinstance(duration_raw, (int, float))
        else None,
        tick_seconds=float(tick_raw)
        if isinstance(tick_raw, (int, float))
        else None,
        extra={
            field: value
            for field, value in raw.items()
            if field not in Constants.definition_field_names - {"extra"}
        },
    )


def _definitions(
    data: Mapping[str, ModelValue],
    key: str,
) -> dict[str, ProcessDefinition]:
    """Parse a definition section.

    Args:
        data: Data.
        key: Section key.

    Raises:
        ModelValidationError: When the section is not an object.

    Returns:
        The resulting value.

    """
    raw_definitions: ModelValue = data.get(key, {})
    if not isinstance(raw_definitions, dict):
        msg: str = f"{key} must be an object."
        raise ModelValidationError(msg)
    return {
        name: _definition(key=key, name=name, raw=raw_definition)
        for name, raw_definition in raw_definitions.items()
    }


@dataclass(init=False)
class Specification:
    """Specification."""

    _version: int
    _global_config: GlobalConfig
    _templates: dict[str, ProcessDefinition]
    _processes: dict[str, ProcessDefinition]

    def __init__(
        self,
        version: int = 2,
        global_config: GlobalConfig | None = None,
        templates: dict[str, ProcessDefinition] | None = None,
        processes: dict[str, ProcessDefinition] | None = None,
    ) -> None:
        """Init.

        Args:
            version: Version.
            global_config: Global config.
            templates: Templates.
            processes: Processes.

        """
        self.version = version
        self.global_config = global_config or GlobalConfig()
        self.templates = dict(templates or {})
        self.processes = dict(processes or {})
        self.validate_graph()

    @classmethod
    def from_json(cls, value: str) -> Self:
        """From json.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        raw: ModelValue = loads(s=value)
        if not isinstance(raw, dict):
            msg: str = "Root JSON value must be an object."
            raise ModelValidationError(msg)
        return cls.from_mapping(data=raw)

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """From file.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        return cls.from_json(value=Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_mapping(cls, data: Mapping[str, ModelValue]) -> Self:
        """From mapping.

        Args:
            data: Data.

        Returns:
            The resulting value.

        """
        return cls(
            version=_spec_version(data=data),
            global_config=_global_config(data=data),
            templates=_definitions(data=data, key="templates"),
            processes=_definitions(data=data, key="processes"),
        )

    @property
    def version(self) -> int:
        """Version.

        Returns:
            The resulting value.

        """
        return self._version

    @version.setter
    def version(self, value: ModelValue) -> None:
        """Version.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            msg: str = "version must be a positive int."
            raise ModelValidationError(msg)
        self._version = value

    @property
    def global_config(self) -> GlobalConfig:
        """Global config.

        Returns:
            The resulting value.

        """
        return self._global_config

    @global_config.setter
    def global_config(self, value: GlobalConfig | ModelValue) -> None:
        """Global config.

        Args:
            value: Value.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not isinstance(value, GlobalConfig):
            msg: str = "global_config must be GlobalConfig."
            raise ModelValidationError(msg)
        self._global_config = value

    @property
    def templates(self) -> dict[str, ProcessDefinition]:
        """Templates.

        Returns:
            The resulting value.

        """
        return self._templates

    @templates.setter
    def templates(self, value: dict[str, ProcessDefinition]) -> None:
        """Templates.

        Args:
            value: Value.

        """
        self._templates = self._definitions(
            value=value,
            field_name="templates",
        )

    @property
    def processes(self) -> dict[str, ProcessDefinition]:
        """Set process definitions.

        Returns:
            The resulting value.

        """
        return self._processes

    @processes.setter
    def processes(self, value: dict[str, ProcessDefinition]) -> None:
        """Set process definitions.

        Args:
            value: Value.

        """
        self._processes = self._definitions(
            value=value,
            field_name="processes",
        )

    def validate_graph(self) -> None:
        """Validate graph.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        names: set[str] = set(self.processes)
        templates: set[str] = set(self.templates)
        for name, definition in self.processes.items():
            if (
                definition.extends is not None
                and definition.extends not in templates
            ):
                msg: str = (
                    f"Process {name} extends unknown "
                    f"template {definition.extends}."
                )
                raise ModelValidationError(msg)
            for reference in definition.depends_on + definition.children:
                if reference.process not in names:
                    msg = (
                        f"Process {name} references unknown "
                        f"process {reference.process}."
                    )
                    raise ModelValidationError(msg)

    def to_mapping(self) -> dict[str, ModelValue]:
        """To mapping.

        Returns:
            The resulting value.

        """
        self.validate_graph()
        return {
            "version": self.version,
            "global": self.global_config.to_mapping(),
            "templates": {
                name: value.to_mapping()
                for name, value in self.templates.items()
            },
            "processes": {
                name: value.to_mapping()
                for name, value in self.processes.items()
            },
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """To json.

        Args:
            indent: Indent.

        Returns:
            The resulting value.

        """
        return dumps(indent=indent, obj=self.to_mapping())

    def write(self, path: str | Path) -> Path:
        """Write.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        destination: Path = Path(path).resolve()
        destination.write_text(encoding="utf-8", data=self.to_json() + "\n")
        return destination

    @staticmethod
    def _definitions(
        value: dict[str, ProcessDefinition] | dict[ModelValue, ModelValue],
        field_name: str,
    ) -> dict[str, ProcessDefinition]:
        """Definitions.

        Args:
            value: Value.
            field_name: Field name.
                        definition: Definition being parsed.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        validated: dict[str, ProcessDefinition] = {}
        for name, definition in value.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or (not isinstance(definition, ProcessDefinition))
            ):
                msg: str = f"{field_name} must map names to ProcessDefinition."
                raise ModelValidationError(msg)
            validated[name] = definition
        return validated
