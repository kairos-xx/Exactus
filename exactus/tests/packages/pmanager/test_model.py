# Copyright (c) 2026 João Lopes.
"""Typed specification model contract tests."""

from pathlib import Path
from typing import cast

import pytest

from exactus.packages.pmanager import (
    ArgumentPolicy,
    Concurrency,
    Executor,
    GlobalConfig,
    Identity,
    ModelValidationError,
    Orchestrator,
    ProcessDefinition,
    ProcessReference,
    Resource,
    Retry,
    Specification,
    Timeouts,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    require_type,
)


def test_mutable_validated_properties() -> None:
    """Every public assignment is revalidated."""
    model: Specification = Specification()
    model.version = 3
    expect_equal(actual=model.version, expected=3)
    with pytest.raises(expected_exception=ModelValidationError):
        model.version = 0
    resource: Resource = Resource(capacity=2)
    resource.capacity = 4
    expect_equal(actual=resource.capacity, expected=4)
    with pytest.raises(expected_exception=ModelValidationError):
        resource.capacity = 0
    concurrency: Concurrency = Concurrency(group="gpu", max_running=1)
    with pytest.raises(expected_exception=ModelValidationError):
        concurrency.max_running = 0


def test_round_trip_existing_specification() -> None:
    """Existing JSON becomes a typed lossless model."""
    model: Specification = Specification.from_file(
        path=Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "pmanager"
        / "processes.json",
    )
    expect_equal(actual=model.version, expected=2)
    expect_equal(
        actual=set(model.processes),
        expected={"A", "B", "C", "D", "E"},
    )
    concurrency: Concurrency = require_type(
        value=model.processes["C"].concurrency,
        kind=Concurrency,
    )
    expect_equal(actual=concurrency.max_running, expected=1)
    rebuilt: Specification = Specification.from_mapping(
        data=model.to_mapping(),
    )
    expect_equal(actual=rebuilt.to_mapping(), expected=model.to_mapping())


def test_programmatic_graph_and_orchestrator() -> None:
    """Build a complete graph without authoring JSON."""
    model: Specification = Specification(
        version=3,
        global_config=GlobalConfig(resources={"gpu": Resource(capacity=1)}),
        processes={
            "A": ProcessDefinition(executor=Executor(type_="counter")),
            "B": ProcessDefinition(
                executor=Executor(type_="counter"),
                depends_on=[ProcessReference(process="A")],
            ),
        },
    )
    expect_equal(actual=model.version, expected=3)
    expect_equal(
        actual=model.processes["B"].depends_on[0].process,
        expected="A",
    )
    api: Orchestrator = Orchestrator.from_specification(specification=model)
    try:
        expect_true(condition=api.spec_path.exists())
    finally:
        api.close(kill_owned=False)
    expect_false(condition=api.spec_path.exists())


def test_graph_validation_rejects_unknown_reference() -> None:
    """Unknown dependencies fail before runtime."""
    with pytest.raises(expected_exception=ModelValidationError):
        Specification(
            processes={
                "B": ProcessDefinition(
                    depends_on=[ProcessReference(process="missing")],
                ),
            },
        )


def test_validation_branches_and_serializers(tmp_path: Path) -> None:
    """Exercise mutable validation and serializer branches.

    Args:
        tmp_path: Test input.

    """
    policy: ArgumentPolicy = ArgumentPolicy(policy="merge", values=("a",))
    expect_equal(actual=policy.to_mapping()["values"], expected=["a"])
    expect_equal(
        actual=ArgumentPolicy.from_mapping(
            data={"policy": 3, "values": "bad"},
        ).policy,
        expected="inherit",
    )
    for callback in (
        lambda: ArgumentPolicy(policy="bad"),
        lambda: ArgumentPolicy(values=cast(typ="tuple[str, ...]", val=(1,))),
        lambda: Identity(include_arguments=cast(typ="bool", val=1)),
        lambda: Timeouts(run_seconds=0),
        lambda: Timeouts(dependency_seconds=-1),
        lambda: Timeouts(waiting_seconds=0),
        lambda: Timeouts(on_timeout="bad"),
        lambda: Retry(max_attempts=0),
        lambda: Retry(delay_seconds=-1),
        lambda: Retry(backoff=0),
        lambda: Retry(max_delay_seconds=-1),
        lambda: Executor(type_="bad"),
        lambda: Executor(command=cast(typ="tuple[str, ...]", val=(1,))),
        lambda: Executor(cwd=""),
    ):
        with pytest.raises(expected_exception=ModelValidationError):
            callback()
    expect_equal(
        actual=Identity(include_arguments=True).to_mapping()[
            "include_arguments"
        ],
        expected=True,
    )
    expect_equal(
        actual=Timeouts(
            run_seconds=1,
            dependency_seconds=2,
            waiting_seconds=3,
        ).to_mapping()["run_seconds"],
        expected=1,
    )
    expect_equal(
        actual=Retry(max_attempts=2).to_mapping()["max_attempts"],
        expected=2,
    )
    expect_true(
        condition=Executor(
            type_="command",
            command=("echo",),
            cwd="/",
        ).to_mapping()["command"]
        == ["echo"],
    )
    model: Specification = Specification(
        version=3,
        processes={"A": ProcessDefinition()},
    )
    target: Path = tmp_path / "spec.json"
    expect_equal(actual=model.write(path=target), expected=target.resolve())
    expect_equal(
        actual=Specification.from_json(value=model.to_json()).version,
        expected=3,
    )
    with pytest.raises(expected_exception=ModelValidationError):
        Specification.from_json(value="[]")
    with pytest.raises(expected_exception=ModelValidationError):
        Specification.from_mapping(data={"version": True})


def test_reference_concurrency_resource_validation() -> None:
    """Exercise nested model validation branches."""
    reference: ProcessReference = ProcessReference(
        process="A",
        scope="global",
        completion="terminal",
    )
    expect_equal(actual=reference.to_mapping()["process"], expected="A")
    concurrency: Concurrency = Concurrency(
        group="workers",
        scope="global",
        max_running=2,
        on_conflict="fail",
        queue="priority_fifo",
    )
    expect_equal(actual=concurrency.to_mapping()["max_running"], expected=2)
    expect_equal(
        actual=Resource(capacity=2).to_mapping()["capacity"],
        expected=2,
    )
    for callback in (
        lambda: ProcessReference(process=""),
        lambda: ProcessReference(process="A", scope="bad"),
        lambda: ProcessReference(process="A", completion="bad"),
        lambda: Concurrency(group=""),
        lambda: Concurrency(group="x", scope="bad"),
        lambda: Concurrency(group="x", max_running=0),
        lambda: Concurrency(group="x", on_conflict="bad"),
        lambda: Concurrency(group="x", queue="bad"),
        lambda: Resource(capacity=0),
    ):
        with pytest.raises(expected_exception=ModelValidationError):
            callback()


def test_global_and_process_definition_validation() -> None:
    """Exercise remaining global and process validation paths."""
    config: GlobalConfig = GlobalConfig(
        resources={"gpu": Resource(capacity=2)},
    )
    expect_equal(
        actual=config.to_mapping()["resources"],
        expected={"gpu": {"capacity": 2}},
    )
    for callback in (
        lambda: GlobalConfig(queue_strategy="bad"),
        lambda: GlobalConfig(
            resources=cast(typ="dict[str, Resource]", val={"gpu": 1}),
        ),
        lambda: ProcessDefinition(extends=""),
        lambda: ProcessDefinition(mode="bad"),
        lambda: ProcessDefinition(launch="bad"),
        lambda: ProcessDefinition(duration_seconds=0),
        lambda: ProcessDefinition(tick_seconds=-1),
    ):
        with pytest.raises(expected_exception=ModelValidationError):
            callback()
