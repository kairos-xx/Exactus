# Copyright (c) 2026 João Lopes.
"""Object-first API tests."""

from typing import TYPE_CHECKING, ClassVar

import pytest

from exactus.packages.pmanager import (
    Concurrency,
    CounterExecutor,
    Dependency,
    Lifecycle,
    Process,
    ProcessClass,
    ProcessPolicy,
    Spec,
    Specification,
    kill,
    pause,
    process_name,
    receive,
    status,
)
from exactus.packages.pmanager.model import ModelValidationError, ModelValue
from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_none,
    expect_true,
    require,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_object_references_are_retained() -> None:
    """Dependencies retain exact process object identity."""
    spec: Spec = Spec(version=3)
    a: Process = spec.process(
        executor=CounterExecutor(duration_seconds=2),
        name="A",
    )
    b: Process = spec.process(dependencies=[Dependency(target=a)], name="B")
    c: Process = spec.process(name="C")
    e: Process = spec.process(
        children=[c, "B"],
        concurrency=Concurrency(group="fanout", max_running=1),
        name="E",
    )
    expect_true(condition=b.dependencies[0].process is a)
    expect_equal(actual=b.dependencies[0].name, expected="A")
    expect_true(condition=e.children[0] is c)
    expect_true(condition=spec.get(name="A") is a)
    compiled: Specification = spec.to_specification()
    expect_equal(actual=compiled.version, expected=3)
    expect_equal(
        actual=compiled.processes["B"].depends_on[0].process,
        expected="A",
    )


def test_policy_is_compiled() -> None:
    """Policy extension data reaches the serializable model."""
    spec: Spec = Spec()
    spec.process(policy=ProcessPolicy(values={"priority": 7}), name="A")
    expect_equal(
        actual=spec.to_specification().processes["A"].extra["priority"],
        expected=7,
    )


def test_lifecycle_hooks_and_kill_timeout() -> None:
    """Decorators resolve bound worker-side lifecycle hooks."""

    @process_name(name="A")
    class Task(ProcessClass):
        events: ClassVar[list[str]] = []

        @pause
        def on_pause(self) -> None:
            self.events.append("pause")

        @kill
        def before_kill(self) -> None:
            self.events.append("kill")

    task: Task = Task()
    expect_equal(actual=Task.name(), expected="A")
    expect_true(condition=task.invoke_lifecycle(lifecycle=Lifecycle.PAUSE))
    expect_true(
        condition=task.invoke_lifecycle(lifecycle=Lifecycle.KILL, timeout=0.2),
    )
    expect_equal(actual=task.events, expected=["pause", "kill"])


def test_status_decorator_marks_status_hook() -> None:
    """The status decorator registers a query lifecycle hook."""

    class StatusProcess(ProcessClass):
        @staticmethod
        @status
        def current() -> dict[str, int]:
            return {"items": 7}

    instance: StatusProcess = StatusProcess()
    hook: Callable[[], ModelValue] | None = instance.lifecycle_hook(
        lifecycle=Lifecycle.STATUS,
    )
    hook = require(value=hook)
    expect_equal(actual=hook(), expected={"items": 7})


def test_lifecycle_hook_and_broadcast_dispatch() -> None:
    """Exercise lifecycle resolution, dispatch, timeout, and metadata."""
    calls: list[object] = []

    class Worker(ProcessClass):
        @staticmethod
        @pause
        def paused() -> None:
            calls.append("pause")

        @staticmethod
        @receive(topic="topic")
        def event(payload: ModelValue) -> None:
            calls.append(payload)

    worker: Worker = Worker()
    expect_true(
        condition=worker.lifecycle_hook(lifecycle=Lifecycle.PAUSE) is not None,
    )
    expect_none(value=worker.lifecycle_hook(lifecycle=Lifecycle.KILL))
    expect_true(condition=worker.invoke_lifecycle(lifecycle=Lifecycle.KILL))
    expect_true(condition=worker.invoke_lifecycle(lifecycle=Lifecycle.PAUSE))
    worker.receive_broadcast(topic="topic", payload={"x": 1})
    worker.receive_broadcast(topic="other", payload=None)
    expect_equal(actual=calls, expected=["pause", {"x": 1}])
    expect_equal(actual=worker.broadcast(topic="none"), expected=0)
    worker.configure_broadcast(sender=Constant(value=7))
    expect_equal(
        actual=worker.broadcast(scope="global", topic="x", payload=True),
        expected=7,
    )


def test_builder_validation_and_reference_edges() -> None:
    """Exercise builder validation and direct-reference edge cases."""
    for kwargs in ({"duration_seconds": 0}, {"tick_seconds": -1}):
        with pytest.raises(expected_exception=ModelValidationError):
            CounterExecutor(**kwargs)
    with pytest.raises(expected_exception=ModelValidationError):
        Process(name="")
    spec: Spec = Spec(version=4)
    a: Process = spec.process(
        executor=CounterExecutor(),
        policy=ProcessPolicy(values={"x": 1}),
        name="A",
    )
    b: Process = spec.process(dependencies=["A"], name="B")
    dependency: Dependency = b.dependency(target=a)
    expect_true(condition=dependency.process is a)
    expect_equal(actual=dependency.name, expected="A")
    expect_none(value=Dependency(target="A").process)
    expect_true(condition=spec.get(name="A") is a)
    expect_equal(actual=len(spec.processes), expected=2)
    with pytest.raises(expected_exception=ModelValidationError):
        spec.process(name="A")
    with pytest.raises(expected_exception=ModelValidationError):
        spec.get(name="missing")
    other: Process = Spec().process(name="X")
    spec.process(dependencies=[Dependency(target=other)], name="C")
    with pytest.raises(expected_exception=ModelValidationError):
        spec.to_specification()
