# Copyright (c) 2026 João Lopes.
"""Object-first orchestration graph builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from sys import executable
from typing import TYPE_CHECKING, TypedDict, Unpack

from exactus.packages.pmanager.model import (
    Concurrency,
    Executor,
    GlobalConfig,
    ModelValidationError,
    ModelValue,
    ProcessDefinition,
    ProcessReference,
    Specification,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from exactus.packages.pmanager.lifecycle import ProcessClass


@dataclass(frozen=True, slots=True)
class ProcessPolicy:
    """Processpolicy.

    Attributes:
        values: Values.

    """

    values: dict[str, ModelValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CounterExecutor:
    """Counterexecutor.

    Attributes:
        duration_seconds: Duration seconds.
        tick_seconds: Tick seconds.

    """

    duration_seconds: float | None = None
    tick_seconds: float | None = None

    @staticmethod
    def to_executor() -> Executor:
        """To executor.

        Returns:
            The resulting value.

        """
        return Executor(type_="counter")

    def __post_init__(self) -> None:
        """Post init.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        for name, value in (
            ("duration_seconds", self.duration_seconds),
            ("tick_seconds", self.tick_seconds),
        ):
            if value is not None and value <= 0:
                msg: str = f"{name} must be positive or None."
                raise ModelValidationError(msg)


@dataclass(frozen=True, slots=True)
class PythonClassExecutor:
    """Pythonclassexecutor.

    Attributes:
        process_class: Process class.

    """

    process_class: type[ProcessClass]

    def to_executor(self) -> Executor:
        """To executor.

        Returns:
            The resulting value.

        """
        return Executor(
            type_="python_class",
            command=(
                executable,
                "-m",
                "exactus.packages.pmanager.class_runner",
                self.process_class.__module__,
                self.process_class.__qualname__,
            ),
        )


@dataclass(slots=True, eq=False)
class Process:
    """Process.

    Attributes:
        name: Name.
        executor: Executor.
        policy: Policy.
        dependencies: Dependencies.
        children: Children.
        concurrency: Concurrency.

    """

    name: str
    executor: CounterExecutor | PythonClassExecutor | Executor | None = None
    policy: ProcessPolicy | None = None
    dependencies: list[Dependency] = field(default_factory=list)
    children: list[Process | str] = field(default_factory=list)
    concurrency: Concurrency | None = None

    def dependency(
        self,
        target: Process | str,
        *,
        policy: ProcessPolicy | None = None,
    ) -> Dependency:
        """Dependency.

        Args:
            target: Target.
            policy: Policy.

        Returns:
            The resulting value.

        """
        dependency: Dependency = Dependency(target=target, policy=policy)
        self.dependencies.append(dependency)
        return dependency

    def __post_init__(self) -> None:
        """Post init.

        Raises:
            ModelValidationError: When the operation cannot complete.

        """
        if not self.name.strip():
            msg: str = "Process name cannot be empty."
            raise ModelValidationError(msg)


@dataclass(frozen=True, slots=True)
class Dependency:
    """Dependency.

    Attributes:
        target: Target.
        policy: Policy.

    """

    target: Process | str
    policy: ProcessPolicy | None = None

    @property
    def name(self) -> str:
        """Name.

        Returns:
            The resulting value.

        """
        return (
            self.target.name
            if isinstance(self.target, Process)
            else self.target
        )

    @property
    def process(self) -> Process | None:
        """Process.

        Returns:
            The resulting value.

        """
        return self.target if isinstance(self.target, Process) else None


class ProcessOptions(TypedDict, total=False):
    """Processoptions.

    Attributes:
        children: Children.
        concurrency: Concurrency.

    """

    children: Iterable[Process | str]
    concurrency: Concurrency | None


class Spec:
    """Spec."""

    def __init__(
        self,
        *,
        version: int = 2,
        global_config: GlobalConfig | None = None,
    ) -> None:
        """Init.

        Args:
            version: Version.
            global_config: Global config.

        """
        self.version: int = version
        self.global_config: GlobalConfig = global_config or GlobalConfig()
        self._processes: dict[str, Process] = {}

    @property
    def processes(self) -> tuple[Process, ...]:
        """Processes.

        Returns:
            The resulting value.

        """
        return tuple(self._processes.values())

    def process(
        self,
        name: str,
        *,
        executor: CounterExecutor
        | PythonClassExecutor
        | Executor
        | None = None,
        policy: ProcessPolicy | None = None,
        dependencies: Iterable[Dependency | Process | str] = (),
        **options: Unpack[ProcessOptions],
    ) -> Process:
        """Process.

        Args:
            name: Name.
            executor: Executor.
            policy: Policy.
            dependencies: Dependencies.
            options: Options.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        if name in self._processes:
            msg: str = f"Process {name} is already registered."
            raise ModelValidationError(msg)
        node: Process = Process(
            name=name,
            executor=executor,
            policy=policy,
            dependencies=[
                item
                if isinstance(item, Dependency)
                else Dependency(target=item)
                for item in dependencies
            ],
            children=list(options.get("children", ())),
            concurrency=options.get("concurrency"),
        )
        self._processes[name] = node
        return node

    def get(self, name: str) -> Process:
        """Get.

        Args:
            name: Name.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        try:
            return self._processes[name]
        except KeyError as error:
            msg: str = f"Unknown process {name}."
            raise ModelValidationError(msg) from error

    def to_specification(self) -> Specification:
        """To specification.

        Raises:
            ModelValidationError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        definitions: dict[str, ProcessDefinition] = {}
        for node in self._processes.values():
            for dependency in node.dependencies:
                if (
                    dependency.process is not None
                    and self._processes.get(dependency.process.name)
                    is not dependency.process
                ):
                    msg: str = (
                        f"Dependency {dependency.name} is from another Spec."
                    )
                    raise ModelValidationError(msg)
            executor: Executor | None = (
                node.executor.to_executor()
                if isinstance(
                    node.executor,
                    (CounterExecutor, PythonClassExecutor),
                )
                else node.executor
            )
            extra: dict[str, ModelValue] = (
                dict(node.policy.values) if node.policy is not None else {}
            )
            if isinstance(node.executor, CounterExecutor):
                duration: float | None = node.executor.duration_seconds
                tick: float | None = node.executor.tick_seconds
            else:
                duration = None
                tick = None
            definitions[node.name] = ProcessDefinition(
                executor=executor,
                depends_on=[
                    ProcessReference(process=dependency.name)
                    for dependency in node.dependencies
                ],
                children=[
                    ProcessReference(
                        process=child.name
                        if isinstance(child, Process)
                        else child,
                    )
                    for child in node.children
                ],
                mode="fanout_join" if node.children else None,
                concurrency=node.concurrency,
                duration_seconds=duration,
                tick_seconds=tick,
                extra=extra,
            )
        return Specification(
            version=self.version,
            global_config=self.global_config,
            processes=definitions,
        )
