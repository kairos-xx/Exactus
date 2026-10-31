# Copyright (c) 2026
"""Validate runnable Exactus MCP examples."""

from __future__ import annotations

from asyncio import run
from importlib import import_module
from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.exactus_mcp.examples.run import demonstrate
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    import pytest

    from exactus.packages.exactus_mcp.examples.client import Inspection


def test_self_contained_example_completes_authenticated_round_trip(
    tmp_path: Path,
) -> None:
    """The local example discovers tools and resources, then terminates.

    Args:
        tmp_path: Synthetic project root exposed during the round trip.

    """
    inspection: Inspection = run(main=demonstrate(root=tmp_path))
    expect_equal(
        actual=set(inspection.tools),
        expected={
            "get_exactus_status",
            "list_exactus_tools",
            "read_exactus_report",
            "run_exactus_check",
        },
    )
    expect_equal(
        actual=set(inspection.resources),
        expected={"exactus://policy/agents", "exactus://policy/extended"},
    )
    expect_in(member=str(object=tmp_path), container=inspection.status_json)


def test_client_requires_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``EXACTUS_MCP_ACCESS_TOKEN`` the client exits with two.

    Args:
        monkeypatch: Pytest process-state fixture.

    """
    client: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.examples.client",
    )
    monkeypatch.delenv(name="EXACTUS_MCP_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["exactus-mcp-client", "https://service.example/mcp"],
    )
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=client, name="stderr", value=stream)
    result: int = client.main()
    expect_equal(actual=result, expected=2)
    expect_in(member="EXACTUS_MCP_ACCESS_TOKEN", container=stream.getvalue())


def test_client_prints_inspection_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful inspection prints tools, resources, and status.

    Args:
        monkeypatch: Pytest process-state fixture.

    """
    client: ModuleType = import_module(
        name="exactus.packages.exactus_mcp.examples.client",
    )
    inspection: Inspection = client.Inspection(
        tools=("docs", "lints"),
        resources=("exactus://policy/agents",),
        status_json='{"status": "online"}',
    )

    async def fake_inspect(*, url: str, access_token: str) -> Inspection:
        """Return a canned inspection without network access.

        Args:
            url: Recorded endpoint URL.
            access_token: Recorded bearer token.

        Returns:
            Canned inspection result.

        """
        seen.extend((url, access_token))
        return inspection

    seen: list[str] = []
    monkeypatch.setattr(
        target=client,
        name="inspect_service",
        value=fake_inspect,
    )
    monkeypatch.setenv(name="EXACTUS_MCP_ACCESS_TOKEN", value="bearer-value")
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["exactus-mcp-client", "https://service.example/mcp"],
    )
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=client, name="stdout", value=stream)
    result: int = client.main()
    expect_equal(actual=result, expected=0)
    expect_equal(
        actual=seen,
        expected=["https://service.example/mcp", "bearer-value"],
    )
    output: str = stream.getvalue()
    expect_in(member="  - docs\n  - lints", container=output)
    expect_in(member="  - exactus://policy/agents", container=output)
    expect_in(member='{"status": "online"}', container=output)
