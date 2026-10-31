# Copyright (c) 2026
"""Inspect an authenticated Exactus MCP Streamable HTTP endpoint."""

from __future__ import annotations

from asyncio import run as run_async
from dataclasses import dataclass
from os import environ
from sys import stderr, stdout
from textwrap import dedent
from typing import TYPE_CHECKING, final

from httpx2 import AsyncClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from mcp.client._transport import TransportStreams
    from mcp.types import (
        CallToolResult,
        InputRequiredResult,
        ListResourcesResult,
        ListToolsResult,
        Result,
    )


@final
@dataclass(frozen=True, slots=True)
class Inspection:
    """Summarize one authenticated MCP inspection.

    Attributes:
        tools: Tool names advertised by the service.
        resources: Resource URIs advertised by the service.
        status_json: Structured ``get_exactus_status`` result as JSON.

    """

    tools: tuple[str, ...]
    resources: tuple[str, ...]
    status_json: str


async def inspect_service(*, url: str, access_token: str) -> Inspection:
    """Initialize an MCP session and inspect the Exactus surface.

    Args:
        url: Exactus Streamable HTTP URL ending in ``/mcp``.
        access_token: Bearer token printed by ``exactus-mcp``.

    Returns:
        Tool names, resource URIs, and protected service status.

    """
    headers: dict[str, str] = {"Authorization": f"Bearer {access_token}"}
    http_client: AsyncClient
    streams: TransportStreams
    session: ClientSession
    async with (
        AsyncClient(headers=headers) as http_client,
        streamable_http_client(url=url, http_client=http_client) as streams,
        ClientSession(
            read_stream=streams[0],
            write_stream=streams[1],
        ) as session,
    ):
        _ = await session.initialize()
        tools_result: ListToolsResult = await session.list_tools()
        resources_result: ListResourcesResult = await session.list_resources()
        status_result: (
            CallToolResult | InputRequiredResult | Result
        ) = await session.call_tool(name="get_exactus_status", arguments={})
    tool_names: list[str] = []
    tool_index: int = 0
    while tool_index < len(tools_result.tools):
        tool_names.append(tools_result.tools[tool_index].name)
        tool_index += 1
    resource_uris: list[str] = []
    resource_index: int = 0
    while resource_index < len(resources_result.resources):
        resource_uris.append(
            str(object=resources_result.resources[resource_index].uri),
        )
        resource_index += 1
    return Inspection(
        tools=tuple(tool_names),
        resources=tuple(resource_uris),
        status_json=status_result.model_dump_json(indent=2),
    )


def _parser() -> ArgumentParser:
    """Build the remote-client argument parser.

    Returns:
        Parser accepting one Exactus MCP endpoint URL.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Inspect an Exactus MCP endpoint using the bearer token in "
            "EXACTUS_MCP_ACCESS_TOKEN."
        ),
    )
    _ = parser.add_argument(
        "url",
        help="Streamable HTTP endpoint, for example https://host/mcp.",
    )
    return parser


def main() -> int:
    """Inspect a running Exactus MCP service.

    Returns:
        Zero after a successful inspection, or two when no token is set.

    """
    arguments: Namespace = _parser().parse_args()
    access_token: str | None = environ.get("EXACTUS_MCP_ACCESS_TOKEN")
    if access_token is None:
        _ = stderr.write(
            dedent(
                text=(
                    "    Set EXACTUS_MCP_ACCESS_TOKEN to the token printed"
                    " by exactus-mcp.\n    "
                ),
            ),
        )
        return 2
    inspection: Inspection = run_async(
        main=inspect_service(url=arguments.url, access_token=access_token),
    )
    tool_lines: str = "  - " + "\n  - ".join(inspection.tools)
    resource_lines: str = "  - " + "\n  - ".join(inspection.resources)
    _ = stdout.write(
        f"Tools:\n{tool_lines}\n"
        f"Resources:\n{resource_lines}\n"
        f"Status:\n{inspection.status_json}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
