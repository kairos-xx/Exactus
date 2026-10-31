# Copyright (c) 2026
"""Mutable per-process state for the Exactus MCP service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final
from urllib.parse import ParseResult, urlparse

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.server.transport_security import TransportSecuritySettings


@final
@dataclass(slots=True)
class ServiceState:
    """Describe one running Exactus MCP service.

    Attributes:
        root: Project root exposed to the protected MCP tools.
        host: Loopback interface receiving local HTTP traffic.
        port: Loopback TCP port receiving local HTTP traffic.
        access_token: Bearer token protecting the MCP endpoint.
        transport_security: Mutable MCP host/origin allowlist.

    """

    root: Path
    host: str
    port: int
    access_token: str
    transport_security: TransportSecuritySettings
    _public_urls: list[str] = field(default_factory=list, repr=False)

    @property
    def local_url(self) -> str:
        """Return the local HTTP origin.

        Returns:
            Loopback origin serving the status page and MCP endpoint.

        """
        return f"http://{self.host}:{self.port}"

    @property
    def public_url(self) -> str | None:
        """Return the active public HTTPS origin when exposed.

        Returns:
            Ngrok origin, or ``None`` before tunnel startup.

        """
        return self._public_urls[0] if self._public_urls else None

    @property
    def mcp_url(self) -> str:
        """Return the preferred MCP endpoint URL.

        Returns:
            Public MCP URL after ngrok starts, otherwise the local URL.

        """
        origin: str = self.public_url or self.local_url
        return f"{origin}/mcp"

    def expose(self, *, public_url: str) -> None:
        """Record the public origin and admit it to transport checks.

        Args:
            public_url: HTTPS origin allocated by ngrok.

        Raises:
            ValueError: If the URL is not an HTTPS origin.

        """
        parsed: ParseResult = urlparse(url=public_url)
        if parsed.scheme != "https" or not parsed.netloc:
            msg: str = "ngrok must provide an HTTPS public origin"
            raise ValueError(msg)
        origin: str = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.netloc not in self.transport_security.allowed_hosts:
            self.transport_security.allowed_hosts.append(parsed.netloc)
        if origin not in self.transport_security.allowed_origins:
            self.transport_security.allowed_origins.append(origin)
        if self._public_urls:
            self._public_urls[0] = origin
        else:
            self._public_urls.append(origin)
