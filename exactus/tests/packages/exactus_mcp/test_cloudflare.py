# Copyright (c) 2026
"""Tests for Exactus Cloudflare publication."""

from __future__ import annotations

from asyncio import create_subprocess_exec
from asyncio import run as run_async
from asyncio.subprocess import Process
from sys import executable
from textwrap import dedent
from typing import TYPE_CHECKING, Final, Self, cast, final
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx2 import HTTPError

from exactus.packages.exactus_mcp import cloudflare as cloudflare_module
from exactus.packages.exactus_mcp.cloudflare import (
    CloudflareBootstrapper,
    CloudflareConfig,
    PublicationSupervisor,
    configured_port,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
    private,
    private_call,
    require_type,
    set_private,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from pathlib import Path
    from types import TracebackType


def await_private(
    *,
    owner: object,
    member: str,
    **arguments: object,
) -> object:
    """Call a private coroutine and return its result.

    Args:
        owner: Instance or class holding the coroutine.
        member: Coroutine name, including its leading underscore.
        **arguments: Keyword arguments forwarded to the coroutine.

    Returns:
        The coroutine result.

    """
    callable_: Callable[..., Coroutine[object, object, object]] = cast(
        typ="Callable[..., Coroutine[object, object, object]]",
        val=private(owner=owner, name=member),
    )
    return run_async(main=callable_(**arguments))


@final
class Constants:
    """Group module-level constants.

    Attributes:
        credential: Grouped module constant.

    """

    credential: Final[str] = "fixture-value"


def test_config_from_mapping() -> None:
    """Parse and normalize Cloudflare environment configuration."""
    config: CloudflareConfig = CloudflareConfig.from_mapping(
        values={
            "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": (
                "https://router.example.workers.dev/"
            ),
            "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET": Constants.credential,
        },
    )
    expect_equal(
        actual=config.worker_url,
        expected="https://router.example.workers.dev",
    )
    expect_equal(actual=config.control_secret, expected=Constants.credential)


def test_config_rejects_insecure_worker() -> None:
    """Reject a non-HTTPS stable Worker URL."""
    with pytest.raises(expected_exception=ValueError, match="HTTPS"):
        _ = CloudflareConfig.from_mapping(
            values={
                "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "http://example.test",
                "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET": Constants.credential,
            },
        )


def test_configured_port_reads_project(tmp_path: Path) -> None:
    """Read the fixed local upstream port from pyproject.toml.

    Args:
        tmp_path: Per-test scratch directory.

    """
    path: Path = tmp_path / "pyproject.toml"
    _ = path.write_text(
        data="[tool.exactus.mcp]\nport = 6123\n",
        encoding="utf-8",
    )
    expect_equal(actual=configured_port(root=tmp_path), expected=6123)


def test_quick_tunnel_url_detection(tmp_path: Path) -> None:
    """Discover the assigned HTTPS Quick Tunnel URL from process output.

    Args:
        tmp_path: Per-test scratch directory.

    """
    script: Path = tmp_path / "cloudflared"
    _ = script.write_text(
        data=(
            dedent(
                text=(
                    "    #!/usr/bin/env python3\n    print('INF booting', "
                    "flush=True)\n    print('INF https://calm-river.tryclo"
                    "udflare.com', flush=True)\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    script.chmod(mode=448)
    supervisor: PublicationSupervisor = PublicationSupervisor(
        config=CloudflareConfig(
            worker_url="https://router.example.workers.dev",
            control_secret=Constants.credential,
            cloudflared=str(object=script),
        ),
        root=tmp_path,
        port=6100,
    )

    async def exercise() -> str:
        """Start a tunnel and read its assigned URL.

        Returns:
            HTTPS Quick Tunnel URL emitted by the fixture process.

        """
        tunnel: Process = await supervisor.start_tunnel(
            cloudflared=str(object=script),
        )
        url: str = await supervisor.read_tunnel_url(tunnel=tunnel)
        _ = await tunnel.wait()
        return url

    expect_equal(
        actual=run_async(main=exercise()),
        expected="https://calm-river.trycloudflare.com",
    )


@final
class FakeHttpResponse:
    """Stand in for an ``httpx2`` response returned by the test client."""

    def __init__(self, *, is_success: bool = True) -> None:
        """Store the response status.

        Args:
            is_success: Whether the response reports success.

        """
        self.is_success: bool = is_success

    def raise_for_status(self) -> None:
        """Accept the simulated successful response."""


@final
class FakeHttpClient:
    """Capture requests made through the injected HTTP client."""

    def __init__(self, *, timeout: float) -> None:
        """Store the configured timeout and empty call log.

        Args:
            timeout: Timeout passed to the client constructor.

        """
        self.timeout: float = timeout
        self.gets: list[str] = []
        self.posts: list[dict[str, object]] = []
        self.get_steps: list[object] = []

    async def get(self, *, url: str) -> FakeHttpResponse:
        """Record a GET request and replay the next scripted step.

        Args:
            url: Requested health endpoint.

        Returns:
            Scripted fake response.

        Raises:
            HTTPError: If no scripted response remains.

        """
        self.gets.append(url)
        if not self.get_steps:
            msg: str = "no scripted response"
            raise HTTPError(message=msg)
        step: object = self.get_steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        return require_type(value=step, kind=FakeHttpResponse)

    async def post(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json: dict[str, str],
    ) -> FakeHttpResponse:
        """Record a POST request and return success.

        Args:
            url: Requested control endpoint.
            headers: Request headers.
            json: JSON payload.

        Returns:
            Successful fake response.

        """
        self.posts.append({"url": url, "headers": headers, "json": json})
        return FakeHttpResponse()

    async def __aenter__(self) -> Self:
        """Enter the fake client.

        Returns:
            This client instance.

        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the no-op client.

        Args:
            exc_type: Active exception type, when present.
            exc_value: Active exception, when present.
            traceback: Active exception traceback, when present.

        """
        del exc_type, exc_value, traceback


def _patched_client(
    *,
    monkeypatch: pytest.MonkeyPatch,
    client: FakeHttpClient,
) -> None:
    """Inject ``client`` wherever the module builds an HTTP client.

    Args:
        monkeypatch: Module boundary replacement.
        client: Fake client returned for every construction.

    """

    def build(*, timeout: float) -> FakeHttpClient:
        """Return the injected client regardless of the requested timeout.

        Args:
            timeout: Timeout passed to the client constructor.

        Returns:
            The injected fake client.

        """
        client.timeout = timeout
        return client

    monkeypatch.setattr(
        target=cloudflare_module,
        name="AsyncClient",
        value=build,
    )


def _tool_present(*, cmd: str) -> str:
    """Return a synthetic executable path for any requested tool.

    Args:
        cmd: Executable name resolved through PATH.

    Returns:
        Synthetic absolute executable path.

    """
    return f"/bin/{cmd}"


def _tool_missing(*, cmd: str) -> None:
    """Report every executable as missing from PATH.

    Args:
        cmd: Executable name that is never found.

    """
    del cmd


def call_private(*, owner: object, member: str, **arguments: object) -> object:
    """Call a private synchronous callable and return its result.

    Args:
        owner: Instance or class holding the callable.
        member: Callable name, including its leading underscore.
        **arguments: Keyword arguments forwarded to the callable.

    Returns:
        Whatever the callable returns.

    """
    callable_: Callable[..., object] = cast(
        typ="Callable[..., object]",
        val=private(owner=owner, name=member),
    )
    return callable_(**arguments)


def _supervisor(
    *,
    root: Path,
    cloudflared: str = "missing-cloudflared",
    startup_timeout: float = 0.2,
) -> PublicationSupervisor:
    """Build a supervisor with a stable test configuration.

    Args:
        root: Synthetic project root.
        cloudflared: Configured executable name or path.
        startup_timeout: Startup deadline in seconds.

    Returns:
        Configured publication supervisor.

    """
    return PublicationSupervisor(
        config=CloudflareConfig(
            worker_url="https://router.example.workers.dev",
            control_secret=Constants.credential,
            cloudflared=cloudflared,
            startup_timeout_seconds=startup_timeout,
        ),
        root=root,
        port=6100,
    )


def _bridge(*, root: Path) -> Path:
    """Create the bridge package directory and return ``wrangler.toml``.

    Args:
        root: Synthetic project root.

    Returns:
        Worker configuration path inside the created bridge package.

    """
    bridge: Path = root / "exactus/packages/exactus_mcp/bridge"
    bridge.mkdir(parents=True)
    return bridge / "wrangler.toml"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"EXACTUS_MCP_CLOUDFLARE_STARTUP_TIMEOUT_SECONDS": "abc"}, "numeric"),
        ({"EXACTUS_MCP_CLOUDFLARE_STARTUP_TIMEOUT_SECONDS": "0"}, "positive"),
        (
            {"EXACTUS_MCP_CLOUDFLARE_RESTART_DELAY_SECONDS": "-1"},
            "must not be negative",
        ),
    ],
)
def test_config_rejects_invalid_values(
    overrides: dict[str, str],
    match: str,
) -> None:
    """Numeric timing settings must parse and stay within safe bounds.

    Args:
        overrides: Environment-style settings replacing the defaults.
        match: Required fragment of the validation error.

    """
    values: dict[str, str] = {
        "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "https://router.workers.dev",
        "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET": Constants.credential,
        **overrides,
    }
    with pytest.raises(expected_exception=ValueError, match=match):
        _ = CloudflareConfig.from_mapping(values=values)


def test_config_rejects_empty_control_secret() -> None:
    """The shared control credential must not be empty."""
    with pytest.raises(
        expected_exception=ValueError,
        match="must not be empty",
    ):
        _ = CloudflareConfig.from_mapping(
            values={
                "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "https://x.workers.dev",
            },
        )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (None, 6100),
        ("[other]\nport = 7000\n", 6100),
        ("[tool.exactus.mcp]\nport = abc\n", 6100),
        ("[tool.exactus.mcp]\nport = 70000\n", 6100),
        ("[tool.exactus.mcp]\nport = 0\n", 6100),
        ("[tool.exactus.mcp]\nnoequals\nport = 6123\n", 6123),
        ("[tool.exactus.mcp]\nother = 1\nport = 6123\n", 6123),
        ("[tool.exactus.mcp]\nport = 6123 # fixed\n", 6123),
    ],
)
def test_configured_port_edge_cases(
    tmp_path: Path,
    body: str | None,
    expected: int,
) -> None:
    """Missing, misplaced, malformed, and out-of-range ports fall back.

    Args:
        tmp_path: Synthetic project root.
        body: Optional ``pyproject.toml`` content.
        expected: Required resolved port.

    """
    if body is not None:
        _ = (tmp_path / "pyproject.toml").write_text(
            data=body,
            encoding="utf-8",
        )
    expect_equal(actual=configured_port(root=tmp_path), expected=expected)


def test_bootstrapper_reads_namespace_state(tmp_path: Path) -> None:
    """Namespace detection distinguishes missing, pending, and ready files.

    Args:
        tmp_path: Synthetic project root.

    """
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="Missing Worker configuration",
    ):
        private_call(owner=boot, name="_namespace_id")
    wrangler: Path = _bridge(root=tmp_path)
    _ = wrangler.write_text(
        data='kv_namespaces=[{id="REPLACE_WITH_KV_NAMESPACE_ID"}]',
        encoding="utf-8",
    )
    expect_none(value=private_call(owner=boot, name="_namespace_id"))
    identifier: str = "0123456789abcdef0123456789abcdef"
    _ = wrangler.write_text(
        data=f'kv_namespaces=[{{id="{identifier}"}}]',
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(owner=boot, name="_namespace_id"),
        expected=identifier,
    )


def test_bootstrapper_requires_prerequisite_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing prerequisites without Homebrew abort bootstrap safely.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: PATH lookup replacement.

    """
    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=_tool_missing,
    )
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    with pytest.raises(expected_exception=RuntimeError, match="is required"):
        await_private(owner=boot, member="_ensure_prerequisites")


def test_bootstrapper_ensure_skips_provisioned_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fully configured environment performs no provisioning work.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: PATH lookup replacement.

    """
    _ = _bridge(root=tmp_path).write_text(
        data='kv_namespaces=[{id="0123456789abcdef0123456789abcdef"}]',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=_tool_present,
    )
    values: dict[str, str] = {
        "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "https://router.workers.dev",
        "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET": Constants.credential,
    }
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values=values,
    )
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(side_effect=AssertionError("must not run")),
    )
    run_async(main=boot.ensure())


def test_bootstrapper_provisions_missing_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap creates the namespace, deploys, and stores secrets locally.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: PATH lookup replacement.

    """
    wrangler: Path = _bridge(root=tmp_path)
    _ = wrangler.write_text(
        data='kv_namespaces=[{id="REPLACE_WITH_KV_NAMESPACE_ID"}]',
        encoding="utf-8",
    )
    _ = (tmp_path / ".env").write_text(data="OTHER=keep\n", encoding="utf-8")
    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=_tool_present,
    )
    calls: list[tuple[str, ...]] = []

    async def fake_wrangler(
        *,
        arguments: tuple[str, ...],
        input_text: str | None = None,
    ) -> tuple[int, str]:
        """Replay deterministic Wrangler responses.

        Args:
            arguments: Wrangler subcommand arguments.
            input_text: Optional secret stdin payload.

        Returns:
            Scripted exit code and output.

        """
        del input_text
        calls.append(arguments)
        if arguments == ("whoami",):
            return (0, "account")
        if arguments[:3] == ("kv", "namespace", "create"):
            return (0, 'id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"')
        if arguments == ("deploy",):
            return (0, "Deployed to https://app-example.workers.dev")
        if arguments[:2] == ("secret", "put"):
            return (0, "ok")
        return (9, "unexpected wrangler call")

    values: dict[str, str] = {}
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values=values,
    )
    set_private(owner=boot, name="_run_wrangler", value=fake_wrangler)
    run_async(main=boot.ensure())
    expect_equal(
        actual=values["EXACTUS_MCP_CLOUDFLARE_WORKER_URL"],
        expected="https://app-example.workers.dev",
    )
    expect_true(
        condition=bool(values["EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET"]),
    )
    expect_true(
        condition=bool(values[cloudflare_module.Constants.oauth_secret_key]),
    )
    wrangler_text: str = wrangler.read_text(encoding="utf-8")
    expect_in(
        member="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        container=wrangler_text,
    )
    env_text: str = (tmp_path / ".env").read_text(encoding="utf-8")
    expect_in(member="OTHER=keep", container=env_text)
    expect_in(member="EXACTUS_MCP_CLOUDFLARE_WORKER_URL=", container=env_text)
    mode: int = (tmp_path / ".env").stat().st_mode & 0o777
    expect_equal(actual=mode, expected=0o600)
    expect_in(member=("deploy",), container=calls)


def test_bootstrapper_requires_login_success(tmp_path: Path) -> None:
    """A failed Wrangler login aborts bootstrap.

    Args:
        tmp_path: Synthetic project root.

    """
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(return_value=(1, "denied")),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="authentication failed",
    ):
        await_private(owner=boot, member="_ensure_login")


@pytest.mark.parametrize(
    ("result", "body", "match"),
    [
        ((1, "boom"), None, "Unable to create"),
        ((0, "no identifier"), None, "did not return"),
        (
            (0, 'id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'),
            'kv_namespaces=[{id="already"}]',
            "placeholder disappeared",
        ),
    ],
)
def test_bootstrapper_namespace_creation_failures(
    tmp_path: Path,
    result: tuple[int, str],
    body: str | None,
    match: str,
) -> None:
    """Namespace creation failures never silently continue bootstrap.

    Args:
        tmp_path: Synthetic project root.
        result: Scripted Wrangler response.
        body: Optional ``wrangler.toml`` replacement content.
        match: Required fragment of the raised error.

    """
    wrangler: Path = _bridge(root=tmp_path)
    _ = wrangler.write_text(
        data=(
            'kv_namespaces=[{id="REPLACE_WITH_KV_NAMESPACE_ID"}]'
            if body is None
            else body
        ),
        encoding="utf-8",
    )
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(return_value=result),
    )
    with pytest.raises(expected_exception=RuntimeError, match=match):
        await_private(owner=boot, member="_create_namespace")


def test_bootstrapper_deploy_fallback_and_failures(tmp_path: Path) -> None:
    """Deploy falls back to a configured URL and reports real failures.

    Args:
        tmp_path: Synthetic project root.

    """
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(return_value=(1, "build failed")),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="deployment failed",
    ):
        await_private(owner=boot, member="_deploy")
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(return_value=(0, "no url")),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="did not report",
    ):
        await_private(owner=boot, member="_deploy")
    boot2: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={
            "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "https://conf.workers.dev",
        },
    )
    set_private(
        owner=boot2,
        name="_run_wrangler",
        value=AsyncMock(return_value=(0, "no url")),
    )
    expect_equal(
        actual=await_private(owner=boot2, member="_deploy"),
        expected="https://conf.workers.dev",
    )


def test_bootstrapper_secret_upload_failure(tmp_path: Path) -> None:
    """A rejected secret upload reports the failing secret name.

    Args:
        tmp_path: Synthetic project root.

    """
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    set_private(
        owner=boot,
        name="_run_wrangler",
        value=AsyncMock(return_value=(1, "denied")),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unable to configure Worker secret TOKEN",
    ):
        await_private(
            owner=boot,
            member="_put_secret",
            name="TOKEN",
            value="v",
        )


def test_supervisor_resolves_cloudflared(tmp_path: Path) -> None:
    """Executable resolution accepts real files and rejects missing tools.

    Args:
        tmp_path: Synthetic project root.

    """
    script: Path = tmp_path / "cloudflared"
    _ = script.write_text(data="#!/bin/sh\n", encoding="utf-8")
    expect_equal(
        actual=_supervisor(
            root=tmp_path,
            cloudflared=str(object=script),
        ).resolve_cloudflared(),
        expected=str(object=script),
    )
    with pytest.raises(expected_exception=ValueError, match="not found"):
        _supervisor(root=tmp_path).resolve_cloudflared()


def test_supervisor_stop_is_idempotent() -> None:
    """Stopping ignores missing or already-exited child processes."""
    run_async(main=PublicationSupervisor.stop(process=None))
    exited: MagicMock = MagicMock(spec=Process)
    exited.returncode = 0
    run_async(main=PublicationSupervisor.stop(process=exited))
    exited.terminate.assert_not_called()
    running: MagicMock = MagicMock(spec=Process)
    running.returncode = None
    running.wait = AsyncMock(return_value=0)
    run_async(main=PublicationSupervisor.stop(process=running))
    running.terminate.assert_called_once_with()


def test_read_tunnel_url_requires_output_stream(tmp_path: Path) -> None:
    """A tunnel without stdout cannot report its assigned URL.

    Args:
        tmp_path: Synthetic project root.

    """
    supervisor: PublicationSupervisor = _supervisor(root=tmp_path)
    tunnel: MagicMock = MagicMock(spec=Process)
    tunnel.stdout = None
    with pytest.raises(expected_exception=RuntimeError, match="output stream"):
        run_async(main=supervisor.read_tunnel_url(tunnel=tunnel))


def test_read_tunnel_url_reports_early_exit(tmp_path: Path) -> None:
    """A tunnel that exits without a URL is a startup failure.

    Args:
        tmp_path: Synthetic project root.

    """
    supervisor: PublicationSupervisor = _supervisor(root=tmp_path)
    tunnel: MagicMock = MagicMock(spec=Process)
    tunnel.returncode = 9
    tunnel.stdout = MagicMock()
    tunnel.stdout.readline = AsyncMock(return_value=b"")
    with pytest.raises(expected_exception=RuntimeError, match="exited before"):
        run_async(main=supervisor.read_tunnel_url(tunnel=tunnel))


def test_wait_for_server_reports_early_exit(tmp_path: Path) -> None:
    """A server exiting during startup surfaces immediately.

    Args:
        tmp_path: Synthetic project root.

    """
    supervisor: PublicationSupervisor = _supervisor(root=tmp_path)
    server: MagicMock = MagicMock(spec=Process)
    server.returncode = 3
    with pytest.raises(
        expected_exception=RuntimeError,
        match="exited during startup",
    ):
        run_async(main=supervisor.wait_for_server(server=server))


def test_wait_for_server_retries_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient health-check failures are retried until healthy.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: HTTP client boundary replacement.

    """
    client: FakeHttpClient = FakeHttpClient(timeout=1.0)
    client.get_steps.extend(
        [
            HTTPError(message="offline"),
            FakeHttpResponse(is_success=False),
            FakeHttpResponse(),
        ],
    )
    _patched_client(monkeypatch=monkeypatch, client=client)
    supervisor: PublicationSupervisor = _supervisor(
        root=tmp_path,
        startup_timeout=5.0,
    )
    server: MagicMock = MagicMock(spec=Process)
    server.returncode = None
    run_async(main=supervisor.wait_for_server(server=server))
    expect_equal(actual=len(client.gets), expected=3)
    expect_in(member="/health", container=client.gets[0])


def test_wait_for_server_times_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server that never becomes healthy exhausts the deadline.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: HTTP client boundary replacement.

    """
    client: FakeHttpClient = FakeHttpClient(timeout=1.0)
    _patched_client(monkeypatch=monkeypatch, client=client)
    supervisor: PublicationSupervisor = _supervisor(root=tmp_path)
    server: MagicMock = MagicMock(spec=Process)
    server.returncode = None
    with pytest.raises(expected_exception=TimeoutError, match="health"):
        run_async(main=supervisor.wait_for_server(server=server))


def test_publish_posts_backend_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publishing sends the tunnel URL with the bearer credential.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: HTTP client boundary replacement.

    """
    client: FakeHttpClient = FakeHttpClient(timeout=1.0)
    _patched_client(monkeypatch=monkeypatch, client=client)
    supervisor: PublicationSupervisor = _supervisor(root=tmp_path)
    run_async(
        main=supervisor.publish(
            backend_url="https://calm-river.trycloudflare.com",
        ),
    )
    expect_equal(actual=len(client.posts), expected=1)
    post: dict[str, object] = client.posts[0]
    expect_equal(
        actual=post["url"],
        expected="https://router.example.workers.dev/_control/backend",
    )
    headers: dict[str, str] = cast(typ="dict[str, str]", val=post["headers"])
    expect_equal(
        actual=headers["Authorization"],
        expected=f"Bearer {Constants.credential}",
    )
    payload: dict[str, str] = cast(typ="dict[str, str]", val=post["json"])
    expect_equal(
        actual=payload["url"],
        expected="https://calm-river.trycloudflare.com",
    )


def test_require_tool_accepts_present_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool resolution succeeds when the executable exists.

    Args:
        monkeypatch: PATH lookup replacement.

    """
    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=_tool_present,
    )
    call_private(
        owner=CloudflareBootstrapper,
        member="_require_tool",
        name="npx",
    )


def test_bootstrapper_installs_missing_prerequisite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing tool is installed through Homebrew when available.

    Args:
        monkeypatch: PATH lookup and subprocess boundary replacement.

    """
    installed: list[str] = []

    def fake_which(*, cmd: str) -> str | None:
        """Report ``cloudflared`` missing until its install completes.

        Args:
            cmd: Executable name resolved through PATH.

        Returns:
            Synthetic path, or ``None`` while ``cloudflared`` is missing.

        """
        if cmd == "cloudflared" and "cloudflared" not in installed:
            return None
        return f"/bin/{cmd}"

    process: MagicMock = MagicMock(spec=Process)
    process.wait = AsyncMock(return_value=0)

    async def fake_exec(*args: object, **kwargs: object) -> Process:
        """Record the Homebrew install and return a finished process.

        Args:
            *args: Positional process arguments.
            **kwargs: Keyword process arguments.

        Returns:
            Mocked finished process.

        """
        del kwargs
        installed.append(str(object=args[-1]))
        return cast(typ="Process", val=process)

    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=fake_which,
    )
    monkeypatch.setattr(
        target=cloudflare_module,
        name="create_subprocess_exec",
        value=fake_exec,
    )
    await_private(owner=CloudflareBootstrapper, member="_ensure_prerequisites")
    expect_in(member="cloudflared", container=installed)


def test_bootstrapper_reports_failed_prerequisite_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed Homebrew install aborts bootstrap with a clear error.

    Args:
        monkeypatch: PATH lookup and subprocess boundary replacement.

    """

    def only_brew(*, cmd: str) -> str | None:
        """Report Homebrew present and every other tool missing.

        Args:
            cmd: Executable name resolved through PATH.

        Returns:
            Synthetic brew path, or ``None`` for other tools.

        """
        return "/bin/brew" if cmd == "brew" else None

    monkeypatch.setattr(
        target=cloudflare_module,
        name="which",
        value=only_brew,
    )
    process: MagicMock = MagicMock(spec=Process)
    process.wait = AsyncMock(return_value=1)
    monkeypatch.setattr(
        target=cloudflare_module,
        name="create_subprocess_exec",
        value=AsyncMock(return_value=process),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Automatic installation failed",
    ):
        await_private(
            owner=CloudflareBootstrapper,
            member="_ensure_prerequisites",
        )


def test_bootstrapper_login_reuses_existing_auth(tmp_path: Path) -> None:
    """An authenticated Wrangler session skips the login flow.

    Args:
        tmp_path: Synthetic project root.

    """
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    whoami: AsyncMock = AsyncMock(return_value=(0, "account"))
    set_private(owner=boot, name="_run_wrangler", value=whoami)
    await_private(owner=boot, member="_ensure_login")
    expect_equal(actual=whoami.call_count, expected=1)


def test_bootstrapper_wrangler_invocation_uses_pinned_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrangler runs through npx in the bridge directory with stdin support.

    Args:
        tmp_path: Synthetic project root.
        monkeypatch: Subprocess boundary replacement.

    """
    bridge: Path = _bridge(root=tmp_path).parent
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_exec(*args: object, **kwargs: object) -> Process:
        """Spawn a real Python child echoing its stdin payload.

        Args:
            *args: Positional process arguments.
            **kwargs: Keyword process arguments.

        Returns:
            Real finished-or-running subprocess handle.

        """
        captured.append((args, dict(kwargs)))
        return await create_subprocess_exec(
            executable,
            "-c",
            "import sys;sys.stdout.write(sys.stdin.read() or 'ok')",
            stdin=cast(typ="int | None", val=kwargs.get("stdin")),
            stdout=cast(typ="int | None", val=kwargs.get("stdout")),
            stderr=cast(typ="int | None", val=kwargs.get("stderr")),
        )

    monkeypatch.setattr(
        target=cloudflare_module,
        name="create_subprocess_exec",
        value=fake_exec,
    )
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values={},
    )
    result: object = await_private(
        owner=boot,
        member="_run_wrangler",
        arguments=("secret", "put", "TOKEN"),
        input_text="payload\n",
    )
    expect_equal(actual=result, expected=(0, "payload\n"))
    command: tuple[object, ...] = captured[0][0]
    expect_equal(actual=command[0], expected="npx")
    expect_equal(actual=command[2], expected="wrangler@4.45.0")
    expect_equal(actual=command[-1], expected="TOKEN")
    expect_equal(actual=captured[0][1].get("cwd"), expected=bridge)


def test_read_tunnel_url_times_out(tmp_path: Path) -> None:
    """A silent tunnel exhausts the startup deadline.

    Args:
        tmp_path: Synthetic project root.

    """
    supervisor: PublicationSupervisor = _supervisor(
        root=tmp_path,
        startup_timeout=0.05,
    )
    tunnel: MagicMock = MagicMock(spec=Process)
    tunnel.returncode = None
    tunnel.stdout = MagicMock()
    tunnel.stdout.readline = AsyncMock(return_value=b"noise\n")
    with pytest.raises(expected_exception=TimeoutError, match="timed out"):
        run_async(main=supervisor.read_tunnel_url(tunnel=tunnel))


def test_supervisor_stop_tolerates_vanished_process() -> None:
    """A child exiting between terminate and wait is not an error."""
    process: MagicMock = MagicMock(spec=Process)
    process.returncode = None
    process.wait = AsyncMock(side_effect=ProcessLookupError())
    run_async(main=PublicationSupervisor.stop(process=process))
    process.terminate.assert_called_once_with()


def test_bootstrapper_writes_env_without_existing_file(tmp_path: Path) -> None:
    """Generated configuration is written with owner-only permissions.

    Args:
        tmp_path: Synthetic project root.

    """
    values: dict[str, str] = {
        "EXACTUS_MCP_CLOUDFLARE_WORKER_URL": "https://app.workers.dev",
        "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET": "control",
        cloudflare_module.Constants.oauth_secret_key: "oauth",
    }
    boot: CloudflareBootstrapper = CloudflareBootstrapper(
        root=tmp_path,
        values=values,
    )
    call_private(owner=boot, member="_write_env")
    env_path: Path = tmp_path / ".env"
    env_text: str = env_path.read_text(encoding="utf-8")
    expect_in(
        member="EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET",
        container=env_text,
    )
    mode: int = env_path.stat().st_mode & 0o777
    expect_equal(actual=mode, expected=0o600)


@pytest.mark.parametrize(
    ("run_result", "expected"),
    [(5, 5), (KeyboardInterrupt(), 0)],
)
def test_main_delegates_to_async_stack(
    monkeypatch: pytest.MonkeyPatch,
    run_result: int | KeyboardInterrupt,
    expected: int,
) -> None:
    """The entrypoint returns the async result or a clean interrupt exit.

    Args:
        monkeypatch: Environment loader and event-loop boundary replacement.
        run_result: Scripted async outcome.
        expected: Required process exit status.

    """
    loader: MagicMock = MagicMock()
    loader.load.return_value = None
    monkeypatch.setattr(
        target=cloudflare_module,
        name="EnvironmentLoader",
        value=loader,
    )

    def fake_run(*, main: Coroutine[object, object, int]) -> int:
        """Close the stacked coroutine and return the scripted outcome.

        Args:
            main: Async publication stack coroutine.

        Returns:
            Scripted exit status.

        """
        main.close()
        if isinstance(run_result, BaseException):
            raise run_result
        return run_result

    monkeypatch.setattr(
        target=cloudflare_module,
        name="run_async",
        value=fake_run,
    )
    expect_equal(actual=cloudflare_module.main(), expected=expected)
