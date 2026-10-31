# Copyright (c) 2026
"""Validate synchronous controls for the Exactus MCP async service."""

from asyncio import to_thread
from pathlib import Path
from queue import Queue
from threading import Event
from typing import final

from exactus.packages.exactus_mcp.activity import ServiceActivity
from exactus.packages.exactus_mcp.cli import RuntimeConfig
from exactus.packages.exactus_mcp.supervisor import ServiceSupervisor
from exactus.tests.common.support import expect_equal, expect_true


def _config(*, root: Path) -> RuntimeConfig:
    """Create loopback-only synthetic service configuration.

    Args:
        root: Existing synthetic project root.

    Returns:
        Configuration suitable for supervisor unit tests.

    """
    return RuntimeConfig(
        root=root,
        host="127.0.0.1",
        port=0,
        access_token=root.name,
        ngrok=False,
        ngrok_command="ngrok",
        ngrok_url=None,
        ngrok_endpoint=None,
        mantledb_namespace=None,
        mantledb_path="url",
        mantledb_timeout=10.0,
        tunnel_timeout=30.0,
        check_timeout=900.0,
        log_level="critical",
        menu_bar=True,
    )


async def _service_runner(
    *,
    config: RuntimeConfig,
    activity: ServiceActivity,
    stop_requested: Event,
) -> int:
    """Run a deterministic service generation until stopped.

    Args:
        config: Synthetic runtime configuration.
        activity: Shared activity record.
        stop_requested: Thread-safe stop request.

    Returns:
        Zero after the stop request arrives.

    """
    activity.mark_running(
        local_url=f"http://{config.host}:6100",
        public_url=None,
    )
    _ = await to_thread(stop_requested.wait)
    activity.mark_stopped()
    return 0


@final
class RestartProbe:
    """Record each deterministic service generation for restart tests."""

    def __init__(self) -> None:
        """Create an empty thread-safe generation queue."""
        self.generations: Queue[int] = Queue()
        self._generation: int = 0

    async def __call__(
        self,
        *,
        config: RuntimeConfig,
        activity: ServiceActivity,
        stop_requested: Event,
    ) -> int:
        """Record one generation and wait for its stop request.

        Args:
            config: Synthetic runtime configuration.
            activity: Shared activity record.
            stop_requested: Thread-safe stop request.

        Returns:
            Zero after the stop request arrives.

        """
        self._generation += 1
        self.generations.put(item=self._generation)
        activity.mark_running(
            local_url=f"http://{config.host}:6100",
            public_url=None,
        )
        _ = await to_thread(stop_requested.wait)
        activity.mark_stopped()
        return 0


def test_supervisor_starts_and_stops_without_blocking(tmp_path: Path) -> None:
    """Start and Stop control one background service generation.

    Args:
        tmp_path: Existing synthetic project root.

    """
    activity: ServiceActivity = ServiceActivity()
    supervisor: ServiceSupervisor = ServiceSupervisor(
        config=_config(root=tmp_path),
        activity=activity,
        service_runner=_service_runner,
    )
    expect_true(condition=supervisor.start())
    expect_equal(actual=supervisor.public_tunnel_enabled, expected=False)
    expect_equal(actual=supervisor.start(), expected=False)
    expect_true(condition=supervisor.stop())
    expect_true(condition=supervisor.shutdown(timeout=2.0))
    expect_equal(actual=supervisor.is_running(), expected=False)


def test_supervisor_serializes_restart_generations(tmp_path: Path) -> None:
    """Restart stops the current service before starting its replacement.

    Args:
        tmp_path: Existing synthetic project root.

    """
    activity: ServiceActivity = ServiceActivity()
    probe: RestartProbe = RestartProbe()
    supervisor: ServiceSupervisor = ServiceSupervisor(
        config=_config(root=tmp_path),
        activity=activity,
        service_runner=probe,
    )
    expect_true(condition=supervisor.start())
    expect_equal(actual=probe.generations.get(timeout=2.0), expected=1)
    expect_true(condition=supervisor.restart())
    expect_equal(actual=probe.generations.get(timeout=2.0), expected=2)
    expect_true(condition=supervisor.shutdown(timeout=2.0))
