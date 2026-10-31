# Copyright (c) 2026
"""Validate MCP registration and the public HTTP boundary."""

from __future__ import annotations

from asyncio import run
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, final

import pytest
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from exactus.packages.exactus_mcp.activity import (
    ActivitySnapshot,
    ServiceActivity,
)
from exactus.packages.exactus_mcp.runner import (
    CheckResult,
    RemoteTool,
    ReportFormat,
)
from exactus.packages.exactus_mcp.service import (
    BearerAuthMiddleware,
    ExactusMcpService,
    create_application,
    create_server,
)
from exactus.packages.exactus_mcp.state import ServiceState
from exactus.tests.common.support import expect_equal, expect_in, private

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from mcp.server import MCPServer
    from mcp.types import Tool
    from starlette.types import Message, Receive, Scope, Send

    from exactus.packages.exactus_mcp.service import McpJson


class ClientResponse(Protocol):
    """Subset of the test-client response surface used by asset checks."""

    @property
    def status_code(self) -> int:
        """HTTP status code.

        Returns:
            The response status code.

        """
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        """Response headers.

        Returns:
            The response header mapping.

        """
        ...


@final
class FakeRunner:
    """Deterministic runner used at the HTTP and MCP boundaries."""

    @staticmethod
    def list_tools() -> tuple[str, ...]:
        """Return a representative complete catalog.

        Returns:
            Synthetic catalog.

        """
        return ("docs", "lints", "organize")

    @staticmethod
    async def run(
        *,
        tool: RemoteTool,
        includes: tuple[str, ...],
    ) -> CheckResult:
        """Return a deterministic successful result.

        Args:
            tool: Requested safe tool.
            includes: Requested constrained globs.

        Returns:
            Synthetic successful check.

        """
        del includes
        return CheckResult(
            tool=tool,
            exit_code=0,
            status="PASS",
            findings=0,
            report_path=Path("REPORTS/result.json"),
            output="clean",
            report={"status": "PASS", "summary": {"findings_total": 0}},
        )

    @staticmethod
    def read_report(*, tool: RemoteTool, report_format: ReportFormat) -> str:
        """Return deterministic report text.

        Args:
            tool: Requested safe tool.
            report_format: Requested representation.

        Returns:
            Synthetic report body.

        """
        return f"{tool}:{report_format}:clean"


def _state(*, root: Path) -> ServiceState:
    """Create loopback-only service state.

    Args:
        root: Synthetic project root.

    Returns:
        Authenticated test state.

    """
    return ServiceState(
        root=root,
        host="127.0.0.1",
        port=8123,
        access_token=root.name,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
        ),
    )


def test_server_registers_protected_exactus_tools(tmp_path: Path) -> None:
    """The MCP catalog contains all four intended service tools.

    Args:
        tmp_path: Synthetic configured project root.

    """
    service: ExactusMcpService = ExactusMcpService(
        state=_state(root=tmp_path),
        runner=FakeRunner(),
        activity=ServiceActivity(),
    )
    server: MCPServer[None] = create_server(service=service)
    tools: list[Tool] = run(main=server.list_tools())
    names: set[str] = set()
    tool_index: int = 0
    while tool_index < len(tools):
        names.add(tools[tool_index].name)
        tool_index += 1
    expect_equal(
        actual=names,
        expected={
            "get_exactus_status",
            "list_exactus_tools",
            "read_exactus_report",
            "run_exactus_check",
        },
    )


def test_tool_call_updates_visible_activity(tmp_path: Path) -> None:
    """A protected tool call updates the menu's shared activity record.

    Args:
        tmp_path: Synthetic configured project root.

    """
    activity: ServiceActivity = ServiceActivity()
    service: ExactusMcpService = ExactusMcpService(
        state=_state(root=tmp_path),
        runner=FakeRunner(),
        activity=activity,
    )
    _ = run(main=service.list_exactus_tools())
    snapshot: ActivitySnapshot = activity.snapshot()
    expect_equal(actual=snapshot.call_count, expected=1)
    expect_equal(actual=snapshot.active_calls, expected=0)
    expect_equal(actual=snapshot.last_call, expected="list_exactus_tools")


def test_public_page_and_bearer_boundary(tmp_path: Path) -> None:
    """Public metadata is safe while MCP rejects missing credentials.

    Args:
        tmp_path: Synthetic configured project root.

    """
    state: ServiceState = _state(root=tmp_path)
    service: ExactusMcpService = ExactusMcpService(
        state=state,
        runner=FakeRunner(),
        activity=ServiceActivity(),
    )
    client: TestClient
    with TestClient(
        app=create_application(service=service, state=state),
    ) as client:
        page_text: str = client.get(url="/").text
        status_text: str = client.get(url="/api/status").text
        activity_text: str = client.get(url="/api/activity").text
        external_status: int = client.post(url="/mcp").status_code
        unauthorized_status: int = client.post(
            url="/mcp",
            headers={"host": "127.0.0.1"},
        ).status_code
    expect_in(member="Exactus MCP", container=page_text)
    expect_in(
        member='"authentication":"bearer token required"',
        container=status_text,
    )
    expect_equal(actual=external_status, expected=403)
    expect_equal(actual=unauthorized_status, expected=401)
    expect_equal(actual=tmp_path.name in status_text, expected=False)
    expect_in(member='"redaction"', container=activity_text)
    expect_equal(actual=tmp_path.name in activity_text, expected=False)


@final
class FailingRunner:
    """Runner double whose every operation fails deterministically."""

    @staticmethod
    def list_tools() -> tuple[str, ...]:
        """Fail catalog listing.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            RuntimeError: Always.

        """
        msg: str = "catalog broken"
        raise RuntimeError(msg)

    @staticmethod
    async def run(
        *,
        tool: RemoteTool,
        includes: tuple[str, ...],
    ) -> CheckResult:
        """Fail check execution.

        Args:
            tool: Unused tool name.
            includes: Unused include globs.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            RuntimeError: Always.

        """
        del tool, includes
        msg: str = "run broken"
        raise RuntimeError(msg)

    @staticmethod
    def read_report(*, tool: RemoteTool, report_format: ReportFormat) -> str:
        """Fail report reading.

        Args:
            tool: Unused tool name.
            report_format: Unused format.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            RuntimeError: Always.

        """
        del tool, report_format
        msg: str = "report broken"
        raise RuntimeError(msg)


def test_tool_error_paths_record_failures(tmp_path: Path) -> None:
    """Failing runner calls propagate and record activity errors.

    Args:
        tmp_path: Synthetic configured project root.

    """
    activity: ServiceActivity = ServiceActivity()
    service: ExactusMcpService = ExactusMcpService(
        state=_state(root=tmp_path),
        runner=FailingRunner(),
        activity=activity,
    )
    with pytest.raises(expected_exception=RuntimeError, match="catalog"):
        run(main=service.list_exactus_tools())
    with pytest.raises(expected_exception=RuntimeError, match="run"):
        run(main=service.run_exactus_check(tool="docs"))
    with pytest.raises(expected_exception=RuntimeError, match="report"):
        run(main=service.read_exactus_report(tool="docs"))
    snapshot: ActivitySnapshot = activity.snapshot()
    expect_equal(actual=snapshot.call_count, expected=3)
    expect_in(member="failed", container=snapshot.last_error or "")


def test_protected_tool_calls_return_results(tmp_path: Path) -> None:
    """Status, checks, and reports return runner-backed results.

    Args:
        tmp_path: Synthetic configured project root.

    """
    service: ExactusMcpService = ExactusMcpService(
        state=_state(root=tmp_path),
        runner=FakeRunner(),
        activity=ServiceActivity(),
    )
    status: dict[str, str | list[str] | None] = run(
        main=service.get_exactus_status(),
    )
    expect_in(member="runnable_tools", container=status)
    check: dict[str, McpJson] = run(
        main=service.run_exactus_check(tool="docs", includes=["exactus/**"]),
    )
    expect_equal(actual=check["status"], expected="PASS")
    report: str = run(
        main=service.read_exactus_report(tool="docs", report_format="json"),
    )
    expect_equal(actual=report, expected="docs:json:clean")


def test_policy_resources_and_asset_serving(tmp_path: Path) -> None:
    """Policy resources read root files; assets serve allowlisted names.

    Args:
        tmp_path: Synthetic configured project root.

    """
    _ = (tmp_path / "AGENTS.md").write_text(data="policy-a", encoding="utf-8")
    _ = (tmp_path / "AGENTS_EXTENDED.md").write_text(
        data="policy-b",
        encoding="utf-8",
    )
    state: ServiceState = _state(root=tmp_path)
    service: ExactusMcpService = ExactusMcpService(
        state=state,
        runner=FakeRunner(),
        activity=ServiceActivity(),
    )
    expect_equal(actual=run(main=service.agents_policy()), expected="policy-a")
    expect_equal(
        actual=run(main=service.extended_policy()),
        expected="policy-b",
    )
    client: TestClient
    with TestClient(
        app=create_application(service=service, state=state),
    ) as client:
        script: ClientResponse = client.get(url="/assets/app.js")
        style: ClientResponse = client.get(url="/assets/primary.css")
        missing: ClientResponse = client.get(url="/assets/missing.css")
    expect_equal(actual=script.status_code, expected=200)
    expect_in(member="javascript", container=script.headers["content-type"])
    expect_equal(actual=style.status_code, expected=200)
    expect_equal(actual=missing.status_code, expected=404)
    asset_text: Callable[..., str] = cast(
        typ="Callable[..., str]",
        val=private(owner=service, name="_asset_text"),
    )
    with pytest.raises(expected_exception=ValueError, match="unknown"):
        asset_text(name="bogus")


def test_origin_gateway_normalizes_authenticated_scopes() -> None:
    """The origin credential rewrites tunneled scopes for local auth."""
    seen: list[Scope] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        """Record the normalized scope reaching the application.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.

        """
        del receive, send
        seen.append(scope)

    async def receive() -> Message:
        """Return a static ASGI request message.

        Returns:
            Empty request message.

        """
        return {"type": "http.request", "body": b""}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        """Record ASGI response messages.

        Args:
            message: ASGI response message.

        """
        sent.append(message)

    credential: str = "origin-secret"
    middleware: BearerAuthMiddleware = BearerAuthMiddleware(
        app=inner,
        access_token=credential,
    )

    async def invoke(*, scope: Scope) -> None:
        """Drive the middleware for one synthetic scope.

        Args:
            scope: Synthetic ASGI scope.

        """
        await middleware(scope=scope, receive=receive, send=send)

    base: Scope = {"type": "http", "path": "/mcp", "headers": []}
    websocket: Scope = {"type": "websocket", "path": "/mcp"}
    run(main=invoke(scope=websocket))
    expect_equal(actual=len(seen), expected=1)
    run(main=invoke(scope={**base, "path": "/api/status"}))
    expect_equal(actual=len(seen), expected=2)
    external: Scope = {**base, "headers": [(b"host", b"gateway.example")]}
    run(main=invoke(scope=external))
    expect_equal(actual=sent[-2]["status"], expected=403)
    authenticated: Scope = {
        **base,
        "headers": [
            (b"host", b"gateway.example"),
            (b"x-exactus-origin-secret", credential.encode()),
            (b"cookie", b"session=1"),
        ],
    }
    run(main=invoke(scope=authenticated))
    tunneled: Scope = seen[-1]
    pairs: list[tuple[bytes, bytes]] = cast(
        typ="list[tuple[bytes, bytes]]",
        val=tunneled["headers"],
    )
    headers: dict[bytes, bytes] = dict(pairs)
    expect_equal(actual=headers[b"host"], expected=b"127.0.0.1")
    expect_equal(
        actual=headers[b"authorization"],
        expected=b"Bearer origin-secret",
    )
    expect_equal(actual=headers.get(b"cookie"), expected=b"session=1")
    expect_equal(actual=b"x-exactus-origin-secret" in headers, expected=False)
    loopback: Scope = {**base, "headers": [(b"host", b"[::1]:8123")]}
    run(main=invoke(scope=loopback))
    expect_equal(actual=sent[-2]["status"], expected=401)
