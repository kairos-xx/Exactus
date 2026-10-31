# Copyright (c) 2026
"""Validate public URL and transport allowlist state."""

from pathlib import Path

import pytest
from mcp.server.transport_security import TransportSecuritySettings

from exactus.packages.exactus_mcp.state import ServiceState
from exactus.tests.common.support import expect_equal, expect_in


def _state() -> ServiceState:
    """Create isolated service state.

    Returns:
        Loopback-only state ready for URL tests.

    """
    root: Path = Path("/project")
    return ServiceState(
        root=root,
        host="127.0.0.1",
        port=8123,
        access_token=root.name,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:8123"],
            allowed_origins=["http://127.0.0.1:8123"],
        ),
    )


def test_expose_adds_public_origin_to_transport_security() -> None:
    """The ngrok host and origin become admitted transport values."""
    state: ServiceState = _state()
    state.expose(public_url="https://exactus.ngrok-free.app/path")
    expect_equal(
        actual=state.public_url,
        expected="https://exactus.ngrok-free.app",
    )
    expect_equal(
        actual=state.mcp_url,
        expected="https://exactus.ngrok-free.app/mcp",
    )
    expect_in(
        member="exactus.ngrok-free.app",
        container=state.transport_security.allowed_hosts,
    )


def test_expose_rejects_non_https_origin() -> None:
    """Public exposure requires ngrok HTTPS."""
    state: ServiceState = _state()
    with pytest.raises(
        expected_exception=ValueError,
        match="HTTPS public origin",
    ):
        state.expose(public_url="http://example.test")
