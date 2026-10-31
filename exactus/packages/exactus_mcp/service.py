# Copyright (c) 2026
"""MCP tools, resources, HTTP routes, and bearer protection for Exactus."""

from __future__ import annotations

from hmac import compare_digest
from importlib.resources import files
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast, final

from mcp.server import MCPServer
from starlette.datastructures import Headers
from starlette.responses import HTMLResponse, JSONResponse, Response

from .runner import CheckResult, RemoteTool, ReportFormat, Runner
from .runner import Constants as RunnerConstants

type McpJson = (
    bool | int | float | str | list["McpJson"] | dict[str, "McpJson"] | None
)
if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from starlette.requests import Request
    from starlette.types import ASGIApp, Receive, Scope, Send

    from exactus.packages.server.json_types import JsonValue

    from .activity import ActivitySnapshot, ServiceActivity
    from .state import ServiceState


@final
class Constants:
    """Group service constants.

    Attributes:
        asset_types: Public asset names and MIME types.
        content_security_policy: Browser policy for the public page.

    """

    asset_types: Final[Mapping[str, str]] = MappingProxyType(
        mapping={
            "app.js": "text/javascript; charset=utf-8",
            "base.css": "text/css; charset=utf-8",
            "catalog.css": "text/css; charset=utf-8",
            "primary.css": "text/css; charset=utf-8",
            "service.css": "text/css; charset=utf-8",
        },
    )
    content_security_policy: Final[str] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "connect-src 'self'; "
        "img-src 'none'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'none'"
    )


@final
class BearerAuthMiddleware:
    """Protect MCP locally and authenticate the Cloudflare origin gateway.

    Attributes:
        origin_header: Header carrying the private origin credential.
        host_header: Header inspected for loopback-only access.
        loopback_hosts: Host values exempt from origin authentication.

    """

    origin_header: Final[bytes] = b"x-exactus-origin-secret"
    host_header: Final[bytes] = b"host"
    loopback_hosts: Final[frozenset[bytes]] = frozenset(
        {b"127.0.0.1", b"localhost", b"[::1]"},
    )

    def __init__(self, *, app: ASGIApp, access_token: str) -> None:
        """Create the local bearer and private-origin boundary.

        Args:
            app: Wrapped ASGI application.
            access_token: Bearer credential required for MCP requests.

        """
        self._app: ASGIApp = app
        self._access_token: str = access_token
        self._secret: bytes = access_token.encode()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Authorize MCP requests and normalize authenticated tunnel hosts.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.

        """
        path: str = str(object=scope.get("path", ""))
        if scope["type"] != "http" or not (
            path == "/mcp" or path.startswith("/mcp/")
        ):
            await self._app(scope, receive, send)
            return
        headers: list[tuple[bytes, bytes]] = list(Headers(scope=scope).raw)
        host: bytes = self._hostname(
            value=self._header(headers=headers, name=self.host_header),
        )
        if host not in self.loopback_hosts:
            supplied: bytes = self._header(
                headers=headers,
                name=self.origin_header,
            )
            if not self._secret or not compare_digest(supplied, self._secret):
                response: JSONResponse = JSONResponse(
                    content={"error": "authenticated origin required"},
                    status_code=403,
                )
                await response(scope=scope, receive=receive, send=send)
                return
            scope = self._normalized_scope(scope=scope, headers=headers)
            headers = list(Headers(scope=scope).raw)
        authorization: bytes = self._header(
            headers=headers,
            name=b"authorization",
        )
        expected: bytes = f"Bearer {self._access_token}".encode()
        if not compare_digest(authorization, expected):
            response = JSONResponse(
                content={"error": "valid bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope=scope, receive=receive, send=send)
            return
        await self._app(scope, receive, send)

    @staticmethod
    def _header(*, headers: list[tuple[bytes, bytes]], name: bytes) -> bytes:
        """Return one request header value.

        Args:
            headers: Raw ASGI header pairs.
            name: Lowercase header name to find.

        Returns:
            Header value, or empty bytes when absent.

        """
        for header_name, value in headers:
            if header_name.lower() == name:
                return value
        return b""

    @staticmethod
    def _hostname(*, value: bytes) -> bytes:
        """Return the host portion of a Host header value.

        Args:
            value: Raw Host header bytes.

        Returns:
            Lowercase hostname without the port.

        """
        lowered: bytes = value.lower()
        if lowered.startswith(b"["):
            closing: int = lowered.find(b"]")
            return lowered[: closing + 1] if closing >= 0 else lowered
        return lowered.split(sep=b":", maxsplit=1)[0]

    def _normalized_scope(
        self,
        *,
        scope: Scope,
        headers: list[tuple[bytes, bytes]],
    ) -> Scope:
        """Rewrite a tunneled scope for trusted local handling.

        Args:
            scope: Authenticated ASGI connection scope.
            headers: Raw ASGI header pairs.

        Returns:
            Scope with a loopback host and refreshed bearer header.

        """
        normalized: Scope = dict(scope)
        filtered: list[tuple[bytes, bytes]] = [
            (name, value)
            for name, value in headers
            if name.lower() not in {self.origin_header, b"authorization"}
        ]
        filtered = [
            (name, b"127.0.0.1" if name.lower() == self.host_header else value)
            for name, value in filtered
        ]
        filtered.append(
            (b"authorization", f"Bearer {self._access_token}".encode()),
        )
        normalized["headers"] = filtered
        return normalized


@final
class ExactusMcpService:
    """Expose Exactus reports through MCP and a public status page."""

    def __init__(
        self,
        *,
        state: ServiceState,
        runner: Runner,
        activity: ServiceActivity,
    ) -> None:
        """Create the service handlers.

        Args:
            state: Per-process URLs, root, token, and transport allowlist.
            runner: Constrained Exactus command boundary.
            activity: Local lifecycle and caller activity sink.

        """
        self._state: ServiceState = state
        self._runner: Runner = runner
        self._activity: ServiceActivity = activity

    @staticmethod
    async def health(_request: Request) -> Response:
        """Return the unauthenticated service health probe.

        Args:
            _request: Incoming public HTTP request.

        Returns:
            Minimal health document without local filesystem data.

        """
        return JSONResponse(content={"status": "ok", "service": "exactus-mcp"})

    async def get_exactus_status(self) -> dict[str, str | list[str] | None]:
        """Return protected service and project status.

        Returns:
            URLs, project root, authentication mode, and runnable tools.

        """
        error: str | None = None
        identifier: int = self._activity.begin_call(
            name="get_exactus_status",
            request_metadata={"argument_count": 0},
        )
        response: dict[str, str | list[str] | None] | None = None
        response_metadata: dict[str, JsonValue] = {}
        try:
            response = {
                "service": "exactus-mcp",
                "status": "online",
                "root": str(object=self._state.root),
                "local_url": self._state.local_url,
                "public_url": self._state.public_url,
                "mcp_url": self._state.mcp_url,
                "authentication": "bearer",
                "runnable_tools": list(RunnerConstants.remote_tools),
            }
            response_metadata = {
                "status": "online",
                "runnable_tool_count": len(RunnerConstants.remote_tools),
            }
        except Exception as exc:
            error = self._call_error(name="get_exactus_status", exc=exc)
            raise
        else:
            return response
        finally:
            self._activity.finish_call(
                identifier=identifier,
                response_metadata=response_metadata,
                error=error,
            )

    async def list_exactus_tools(self) -> dict[str, str | list[str]]:
        """List the complete catalog and remotely runnable subset.

        Returns:
            Complete tool identifiers and the safe remote subset.

        """
        error: str | None = None
        identifier: int = self._activity.begin_call(
            name="list_exactus_tools",
            request_metadata={"argument_count": 0},
        )
        response: dict[str, str | list[str]] | None = None
        response_metadata: dict[str, JsonValue] = {}
        try:
            catalog: list[str] = list(self._runner.list_tools())
            runnable: list[str] = list(RunnerConstants.remote_tools)
            response = {
                "all_tools": catalog,
                "runnable_tools": runnable,
                "note": (
                    "Remote execution is dry, fixed-root, and intentionally "
                    "limited to report-oriented tools."
                ),
            }
            response_metadata = {
                "catalog_count": len(catalog),
                "runnable_count": len(runnable),
            }
        except Exception as exc:
            error = self._call_error(name="list_exactus_tools", exc=exc)
            raise
        else:
            return response
        finally:
            self._activity.finish_call(
                identifier=identifier,
                response_metadata=response_metadata,
                error=error,
            )

    async def run_exactus_check(
        self,
        tool: RemoteTool,
        includes: list[str] | None = None,
    ) -> dict[str, McpJson]:
        """Run a safe Exactus report check against the configured root.

        Args:
            tool: One of the admitted report-oriented Exactus tools.
            includes: Optional repository-relative include globs.

        Returns:
            Exit status, complete JSON report, path, and output tail.

        """
        error: str | None = None
        selected: tuple[str, ...] = tuple(includes or ())
        identifier: int = self._activity.begin_call(
            name="run_exactus_check",
            request_metadata={"tool": tool, "include_count": len(selected)},
        )
        result: CheckResult | None = None
        response_metadata: dict[str, JsonValue] = {}
        try:
            result = await self._runner.run(tool=tool, includes=selected)
            response_metadata = {
                "status": result.status,
                "exit_code": result.exit_code,
                "findings": result.findings,
            }
            return result.to_json()
        except Exception as exc:
            error = self._call_error(name="run_exactus_check", exc=exc)
            raise
        finally:
            self._activity.finish_call(
                identifier=identifier,
                response_metadata=response_metadata,
                error=error,
            )

    async def read_exactus_report(
        self,
        tool: RemoteTool,
        report_format: ReportFormat = "markdown",
    ) -> str:
        """Read the newest generated report for one safe tool.

        Args:
            tool: One of the admitted report-oriented Exactus tools.
            report_format: Markdown or JSON representation.

        Returns:
            Generated report text or a missing-report explanation.

        """
        error: str | None = None
        identifier: int = self._activity.begin_call(
            name="read_exactus_report",
            request_metadata={"tool": tool, "format": report_format},
        )
        report: str | None = None
        response_metadata: dict[str, JsonValue] = {}
        try:
            report = self._runner.read_report(
                tool=tool,
                report_format=report_format,
            )
            response_metadata = {"character_count": len(report)}
        except Exception as exc:
            error = self._call_error(name="read_exactus_report", exc=exc)
            raise
        else:
            return report
        finally:
            self._activity.finish_call(
                identifier=identifier,
                response_metadata=response_metadata,
                error=error,
            )

    async def agents_policy(self) -> str:
        """Return the complete repository AGENTS policy.

        Returns:
            Verbatim ``AGENTS.md`` contents.

        """
        return (self._state.root / "AGENTS.md").read_text(
            encoding="utf-8",
            errors="replace",
        )

    async def extended_policy(self) -> str:
        """Return the complete extended repository policy.

        Returns:
            Verbatim ``AGENTS_EXTENDED.md`` contents.

        """
        return (self._state.root / "AGENTS_EXTENDED.md").read_text(
            encoding="utf-8",
            errors="replace",
        )

    async def landing(self, _request: Request) -> Response:
        """Serve the public Exactus MCP connection page.

        Args:
            _request: Incoming public HTTP request.

        Returns:
            HTML response with a restrictive content security policy.

        """
        return HTMLResponse(
            content=self._asset_text(name="index.html"),
            headers={
                "Content-Security-Policy": Constants.content_security_policy,
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def public_status(self, _request: Request) -> Response:
        """Return public connection metadata without the bearer token.

        Args:
            _request: Incoming public HTTP request.

        Returns:
            Public URL, MCP endpoint, and authentication requirement.

        """
        return JSONResponse(
            content={
                "service": "exactus-mcp",
                "status": "online",
                "public_url": self._state.public_url,
                "mcp_url": self._state.mcp_url,
                "authentication": "bearer token required",
            },
        )

    async def public_activity(self, _request: Request) -> Response:
        """Return redacted MCP activity for the public local dashboard.

        Args:
            _request: Incoming public HTTP request.

        Returns:
            Lifecycle totals and bounded request/response summaries.

        """
        snapshot: ActivitySnapshot = self._activity.snapshot()
        return JSONResponse(
            content={
                "phase": snapshot.phase.value,
                "call_count": snapshot.call_count,
                "active_calls": snapshot.active_calls,
                "last_error": snapshot.last_error,
                "events": self._activity.recent_calls(),
                "redaction": (
                    "Bearer tokens, authorization headers, raw arguments, "
                    "and report bodies are never included."
                ),
            },
        )

    async def asset(self, request: Request) -> Response:
        """Serve one allowlisted stylesheet or script.

        Args:
            request: Request carrying the asset name path parameter.

        Returns:
            Static asset response, or a 404 response.

        """
        name: str = str(object=request.path_params.get("name", ""))
        media_type: str | None = Constants.asset_types.get(name)
        if media_type is None:
            return Response(content="Not found", status_code=404)
        return Response(
            content=self._asset_text(name=name),
            media_type=media_type,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @staticmethod
    def _call_error(*, name: str, exc: Exception) -> str:
        """Return a concise local error for one failed MCP call.

        Args:
            name: Registered MCP tool name.
            exc: Raised tool exception.

        Returns:
            Tool name and exception type without credential-bearing details.

        """
        return f"{name} failed: {type(exc).__name__}"

    @staticmethod
    def _asset_text(*, name: str) -> str:
        """Read one internal web asset.

        Args:
            name: Allowlisted asset filename.

        Returns:
            UTF-8 asset content.

        Raises:
            ValueError: If the requested asset is not an internal asset.

        """
        if name == "index.html" or name in {"app.js", "service.css"}:
            package: str = "exactus.packages.exactus_mcp"
            relative: tuple[str, ...] = ("web", name)
        elif name in {"primary.css", "base.css", "catalog.css"}:
            package = "exactus.packages.widgets.widget_styles"
            relative = (name,)
        else:
            msg: str = f"unknown internal asset: {name}"
            raise ValueError(msg)
        return (
            files(anchor=package)
            .joinpath(*relative)
            .read_text(encoding="utf-8")
        )


def create_server(*, service: ExactusMcpService) -> MCPServer[None]:
    """Create the configured MCP server.

    Args:
        service: Exactus tool, resource, and HTTP route handlers.

    Returns:
        MCP server ready to produce a Streamable HTTP application.

    """
    server: MCPServer[None] = MCPServer(
        name="exactus",
        title="Exactus Engineering",
        description=(
            "Run protected Exactus quality reports and read their evidence."
        ),
        instructions=(
            "Inspect status and policies first. Run checks only when the user "
            "asks; every remote run is dry and fixed to the configured root."
        ),
        version="0.5.0",
    )
    server.add_tool(
        fn=service.get_exactus_status,
        name="get_exactus_status",
        description="Read the protected Exactus service status.",
        structured_output=True,
    )
    server.add_tool(
        fn=service.list_exactus_tools,
        name="list_exactus_tools",
        description="List the full catalog and safe remote subset.",
        structured_output=True,
    )
    server.add_tool(
        fn=service.run_exactus_check,
        name="run_exactus_check",
        description="Run one dry Exactus report check on the fixed root.",
        structured_output=True,
    )
    server.add_tool(
        fn=service.read_exactus_report,
        name="read_exactus_report",
        description="Read the newest Exactus Markdown or JSON report.",
    )
    resource_handler: Callable[[], Awaitable[str]]
    resource_registrar: Callable[
        [Callable[[], Awaitable[str]]],
        Callable[[], Awaitable[str]],
    ]
    resource_registrar = server.resource(
        uri="exactus://policy/agents",
        name="agents-policy",
        title="Complete AGENTS.md policy",
        description="Verbatim canonical repository engineering policy.",
        mime_type="text/markdown",
    )
    resource_handler = service.agents_policy
    _ = resource_registrar(resource_handler)
    resource_registrar = server.resource(
        uri="exactus://policy/extended",
        name="extended-policy",
        title="Complete AGENTS_EXTENDED.md policy",
        description="Verbatim mechanically enforced requirements.",
        mime_type="text/markdown",
    )
    resource_handler = service.extended_policy
    _ = resource_registrar(resource_handler)
    route_handler: Callable[[Request], Awaitable[Response]]
    route_registrar: Callable[
        [Callable[[Request], Awaitable[Response]]],
        Callable[[Request], Awaitable[Response]],
    ]
    route_registrar = server.custom_route(
        path="/",
        methods=["GET"],
        name="landing",
        include_in_schema=False,
    )
    route_handler = service.landing
    _ = route_registrar(route_handler)
    route_registrar = server.custom_route(
        path="/health",
        methods=["GET"],
        name="health",
        include_in_schema=False,
    )
    route_handler = service.health
    _ = route_registrar(route_handler)
    route_registrar = server.custom_route(
        path="/api/status",
        methods=["GET"],
        name="public-status",
        include_in_schema=False,
    )
    route_handler = service.public_status
    _ = route_registrar(route_handler)
    route_registrar = server.custom_route(
        path="/api/activity",
        methods=["GET"],
        name="public-activity",
        include_in_schema=False,
    )
    route_handler = service.public_activity
    _ = route_registrar(route_handler)
    route_registrar = server.custom_route(
        path="/assets/{name}",
        methods=["GET"],
        name="asset",
        include_in_schema=False,
    )
    route_handler = service.asset
    _ = route_registrar(route_handler)
    return server


def create_application(
    *,
    service: ExactusMcpService,
    state: ServiceState,
) -> ASGIApp:
    """Create the bearer-protected Streamable HTTP application.

    Args:
        service: Exactus service handlers.
        state: Per-process transport and authentication state.

    Returns:
        ASGI application exposing public routes and protected ``/mcp``.

    """
    server: MCPServer[None] = create_server(service=service)
    application: ASGIApp = cast(
        typ="ASGIApp",
        val=server.streamable_http_app(
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            transport_security=state.transport_security,
            host=state.host,
        ),
    )
    return BearerAuthMiddleware(
        app=application,
        access_token=state.access_token,
    )
