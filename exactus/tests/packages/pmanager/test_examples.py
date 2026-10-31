# Copyright (c) 2026
"""Exercise the bundled pmanager examples as user-facing documentation."""

from __future__ import annotations

from contextlib import suppress
from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.pmanager.examples import run as entrypoint
from exactus.packages.pmanager.examples.api import run as api_example
from exactus.packages.pmanager.examples.api.run import ApplicationWorker
from exactus.packages.pmanager.examples.cli import run as cli_example
from exactus.packages.pmanager.runtime import Client, Descriptor, Discovery
from exactus.tests.common.support import expect_equal, expect_in, expect_true

if TYPE_CHECKING:
    import pytest

    from exactus.packages.pmanager import (
        CounterExecutor,
        Executor,
        Process,
        PythonClassExecutor,
        Spec,
    )


def test_example_entrypoint_delegates_to_api() -> None:
    """The package example shim re-exports the API example ``main``."""
    expect_true(condition=entrypoint.main is api_example.main)


def test_build_spec_defines_the_pipeline_graph() -> None:
    """The demo spec wires source, worker, mirror, and pipeline nodes."""
    spec: Spec = api_example.build_spec()
    names: list[str] = [process.name for process in spec.processes]
    expect_equal(
        actual=names,
        expected=["source", "worker", "mirror", "pipeline"],
    )
    pipeline: Process = spec.get(name="pipeline")
    expect_equal(actual=len(pipeline.children), expected=2)
    worker_executor: (
        CounterExecutor | PythonClassExecutor | Executor | None
    ) = spec.get(name="worker").executor
    expect_true(condition=worker_executor is not None)


def test_cli_example_loads_a_json_specification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI demo validates and renders an explicit JSON spec.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    expect_true(condition=cli_example.Constants.spec.is_file())
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=cli_example, name="stdout", value=buffer)
    expect_equal(actual=cli_example.main(), expected=0)
    output: str = buffer.getvalue()
    expect_in(member="spec:", container=output)
    expect_in(member="processes.json", container=output)
    expect_in(member="--validate", container=output)
    expect_in(member="--status", container=output)
    expect_in(member="--tree", container=output)


def test_api_example_runs_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """The object-API demo creates and observes a real worker.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=api_example, name="stdout", value=buffer)
    try:
        expect_equal(actual=api_example.main(), expected=0)
        output: str = buffer.getvalue()
        expect_in(member="worker/example", container=output)
        expect_in(member="configuration.changed", container=output)
    finally:
        for descriptor in Discovery.all():
            if descriptor.context == "example":
                _kill(descriptor=descriptor)


def _kill(descriptor: Descriptor) -> None:
    """Terminate a leaked example worker so it cannot poison discovery.

    Args:
        descriptor: Worker descriptor to kill.

    """
    with suppress(OSError):
        Client.request(descriptor=descriptor, command="kill")


def test_application_worker_run_records_invocation() -> None:
    """The example worker accepts the documented run signature."""
    worker: ApplicationWorker = ApplicationWorker()
    expect_equal(
        actual=worker.run(count=2, name="t", enabled=False),
        expected=0,
    )
    expect_equal(actual=ApplicationWorker.name(), expected="worker")
