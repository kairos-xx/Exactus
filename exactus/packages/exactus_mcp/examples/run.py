#!/usr/bin/env python3
# Copyright (c) 2026
"""Run a self-contained authenticated Exactus MCP round trip.

The demonstration starts the real ASGI application on an ephemeral loopback
port, initializes an MCP client with a generated bearer token, lists the MCP
tools and resources, calls ``get_exactus_status``, and then stops the server.
It performs no Exactus report run and creates no public tunnel.
"""

from __future__ import annotations

from asyncio import create_task, sleep
from asyncio import run as run_async
from pathlib import Path
from secrets import token_urlsafe
from sys import stdout
from typing import TYPE_CHECKING, Final, final

from mcp.server.transport_security import TransportSecuritySettings
from uvicorn import Config, Server

from exactus.packages.exactus_mcp.activity import ServiceActivity
from exactus.packages.exactus_mcp.examples.client import (
    Inspection,
    inspect_service,
)
from exactus.packages.exactus_mcp.runner import ExactusCommandRunner
from exactus.packages.exactus_mcp.service import (
    ExactusMcpService,
    create_application,
)
from exactus.packages.exactus_mcp.state import ServiceState
from exactus.packages.server.local import free_port

if TYPE_CHECKING:
    from asyncio import Task

    from starlette.types import ASGIApp


@final
class Constants:
    """Group deterministic example settings.

    Attributes:
        host: Loopback host used by the example.
        startup_timeout: Seconds allowed for Uvicorn startup.
        check_timeout: Unused report-run boundary installed in the service.

    """

    host: Final[str] = "127.0.0.1"
    startup_timeout: Final[float] = 10.0
    check_timeout: Final[float] = 30.0


async def _wait_started(*, server: Server) -> None:
    """Wait until Uvicorn accepts connections.

    Args:
        server: Example Uvicorn server.

    Raises:
        RuntimeError: If startup fails or exceeds the example timeout.

    """
    elapsed: float = 0.0
    while not server.started:
        if server.should_exit:
            msg: str = "example server exited before startup"
            raise RuntimeError(msg)
        if elapsed >= Constants.startup_timeout:
            msg = "example server startup timed out"
            raise RuntimeError(msg)
        await sleep(delay=0.05)
        elapsed += 0.05


async def demonstrate(*, root: Path | None = None) -> Inspection:
    """Start, inspect, and stop one loopback Exactus MCP service.

    Args:
        root: Project root override used by automated tests.

    Returns:
        Authenticated MCP inspection captured before shutdown.

    """
    project_root: Path = root or _default_root()
    port: int = free_port()
    access_token: str = token_urlsafe(nbytes=32)
    origin: str = f"http://{Constants.host}:{port}"
    state: ServiceState = ServiceState(
        root=project_root,
        host=Constants.host,
        port=port,
        access_token=access_token,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[f"{Constants.host}:{port}"],
            allowed_origins=[origin],
        ),
    )
    service: ExactusMcpService = ExactusMcpService(
        state=state,
        runner=ExactusCommandRunner(
            root=project_root,
            timeout=Constants.check_timeout,
        ),
        activity=ServiceActivity(),
    )
    application: ASGIApp = create_application(service=service, state=state)
    server: Server = Server(
        config=Config(
            app=application,
            host=Constants.host,
            port=port,
            log_level="error",
            lifespan="on",
        ),
    )
    server_task: Task[None] = create_task(coro=server.serve())
    try:
        await _wait_started(server=server)
        return await inspect_service(
            url=state.mcp_url,
            access_token=access_token,
        )
    finally:
        server.should_exit = True
        await server_task


def _default_root() -> Path:
    """Resolve the repository root used by the standalone example.

    Returns:
        Exactus source checkout root.

    """
    return Path(__file__).resolve().parents[4]


def main() -> int:
    """Run the self-contained MCP demonstration.

    Returns:
        Zero after the authenticated round trip and clean shutdown.

    """
    inspection: Inspection = run_async(main=demonstrate())
    _ = stdout.write(
        "Authenticated Exactus MCP round trip completed.\n"
        f"Tools: {', '.join(inspection.tools)}\n"
        f"Resources: {', '.join(inspection.resources)}\n"
        f"Status result:\n{inspection.status_json}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
