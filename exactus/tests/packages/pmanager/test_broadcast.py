# Copyright (c) 2026 João Lopes.
"""Live worker broadcast integration tests."""

from os import getpid
from pathlib import Path
from time import sleep
from typing import Final, final

from exactus.packages.pmanager import (
    BroadcastEvent,
    Orchestrator,
    ProcessHandle,
)
from exactus.packages.pmanager.runtime import Client, Descriptor, Discovery
from exactus.tests.common.support import expect_equal, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_delivered: Grouped module constant.
        root: Grouped module constant.

    """

    min_delivered: Final = 2
    root: Final = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "pmanager"
    )


def test_context_broadcast_reaches_other_worker_and_api() -> None:
    """A broadcast is copied to every live worker in the same context."""
    context: str = f"broadcast-{getpid()}"
    api: Orchestrator = Orchestrator.from_file(
        path=Constants.root / "processes.json",
    )
    first: ProcessHandle = api.context(name=context).create(process="A")
    second: ProcessHandle = api.context(name=context).create(process="D")
    try:
        delivered: int = api.broadcast(
            context=context,
            topic="metrics.tick",
            payload={"value": 7},
        )
        expect_true(condition=delivered >= Constants.min_delivered)
        events: tuple[BroadcastEvent, ...] = api.broadcasts(
            context=context,
            process="D",
        )
        for _attempt in range(19):
            if events:
                break
            sleep(0.05)
            events = api.broadcasts(context=context, process="D")
        expect_equal(actual=len(events), expected=1)
        expect_equal(actual=events[0].topic, expected="metrics.tick")
        expect_equal(actual=events[0].payload, expected={"value": 7})
        expect_equal(actual=events[0].context, expected=context)
        expect_true(
            condition=api.context(name=context)
            .broadcasts(process="A")[0]
            .topic
            == "metrics.tick",
        )
    finally:
        for handle in (first, second):
            descriptor: Descriptor | None = Discovery.find(
                name=handle.key.name,
                context=context,
            )
            if descriptor is not None:
                Client.request(descriptor=descriptor, command="kill")
