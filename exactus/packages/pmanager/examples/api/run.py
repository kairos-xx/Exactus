#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Comprehensive object-first pmanager API example."""

from __future__ import annotations

from pathlib import Path
from sys import path

if __package__ in {None, ""}:
    path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from contextlib import suppress
from sys import stdout
from typing import TYPE_CHECKING

from exactus.packages.pmanager import (
    Concurrency,
    Context,
    CounterExecutor,
    Dependency,
    Orchestrator,
    Process,
    ProcessClass,
    ProcessHandle,
    ProcessPolicy,
    ProcessStatus,
    PythonClassExecutor,
    Spec,
    kill,
    pause,
    process_name,
    receive,
    resume,
    status,
)
from exactus.packages.pmanager.runtime import Client, Discovery

if TYPE_CHECKING:
    from exactus.packages.pmanager.model import ModelValue
    from exactus.packages.pmanager.runtime import Descriptor


@process_name(name="worker")
class ApplicationWorker(ProcessClass):
    """Example Python worker with lifecycle and broadcast integration."""

    @staticmethod
    @status
    def current_status() -> dict[str, str | bool]:
        """Return application-specific live status.

        Returns:
            Custom health and phase fields.

        """
        return {"phase": "working", "healthy": True}

    @pause
    def on_pause(self) -> None:
        """Handle cooperative pause."""
        self.broadcast(topic="worker.lifecycle", payload={"state": "paused"})

    @resume
    def on_resume(self) -> None:
        """Handle cooperative resume."""
        self.broadcast(topic="worker.lifecycle", payload={"state": "running"})

    @receive(topic="configuration.changed")
    def configuration_changed(self, payload: ModelValue) -> None:
        """Receive a live event from another worker or orchestrator.

        Args:
            payload: Broadcast payload.

        """
        self.broadcast(topic="configuration.acknowledged", payload=payload)

    @kill
    def before_kill(self) -> None:
        """Perform bounded graceful work before the mandatory hard kill."""
        self.broadcast(
            topic="worker.lifecycle",
            payload={"state": "terminating"},
        )

    def run(
        self,
        count: int = 1,
        *,
        name: str = "example",
        enabled: bool = True,
    ) -> int:
        """Run the example workload.

        Args:
            count: Number of example items.
            name: Logical workload name.
            enabled: Whether work is enabled.

        Returns:
            Process exit code.

        """
        self.broadcast(
            topic="worker.started",
            payload={"count": count, "name": name, "enabled": enabled},
        )
        return 0


def build_spec() -> Spec:
    """Build a mixed counter/class process graph with object references.

    Returns:
        Complete object-first specification.

    """
    spec: Spec = Spec(version=3)
    source: Process = spec.process(
        executor=CounterExecutor(duration_seconds=2, tick_seconds=0.1),
        policy=ProcessPolicy(values={"on_create": {"running": "reuse"}}),
        name="source",
    )
    worker: Process = spec.process(
        executor=PythonClassExecutor(process_class=ApplicationWorker),
        dependencies=[Dependency(target=source)],
        name="worker",
    )
    mirror: Process = spec.process(
        executor=CounterExecutor(duration_seconds=1, tick_seconds=0.1),
        name="mirror",
    )
    spec.process(
        children=[worker, mirror],
        concurrency=Concurrency(
            group="example:pipeline",
            scope="global",
            max_running=1,
        ),
        name="pipeline",
    )
    return spec


def _sweep() -> None:
    """Kill leftover ``example`` workers so re-runs start clean."""
    descriptor: Descriptor
    for descriptor in Discovery.all():
        if descriptor.context == "example":
            with suppress(OSError):
                Client.request(descriptor=descriptor, command="kill")


def main() -> int:
    """Exercise creation, monitoring, broadcasts, planning, and cleanup.

    Returns:
        Example process exit code.

    """
    _sweep()
    try:
        spec: Spec = build_spec()
        with Orchestrator.from_object_spec(specification=spec) as api:
            context: Context = api.context(name="example")
            handle: ProcessHandle = context.create(
                arguments=((3,), {"name": "demo", "enabled": True}),
                process=ApplicationWorker,
            )
            current: ProcessStatus = handle.status()
            stdout.write(
                f"{current.key.name}/{current.key.context}: "
                f"{current.state.value} {current.custom_status}\n",
            )
            context.broadcast(
                topic="configuration.changed",
                payload={"revision": 2},
            )
            for event in context.broadcasts(after=0):
                stdout.write(f"{event.topic}: {event.payload}\n")
    finally:
        _sweep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
