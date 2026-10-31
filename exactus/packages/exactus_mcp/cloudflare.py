# Copyright (c) 2026
"""Publish Exactus MCP through a stable OAuth Cloudflare Worker."""

from __future__ import annotations

from asyncio import StreamReader, create_subprocess_exec, sleep, wait_for
from asyncio import run as run_async
from asyncio.subprocess import PIPE, STDOUT, Process
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from os import environ, urandom
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from shutil import which
from sys import executable, stdout
from time import monotonic
from typing import TYPE_CHECKING, Final, Self, final

from httpx2 import AsyncClient, HTTPError, Response

if TYPE_CHECKING:
    from collections.abc import Mapping
from .environment import EnvironmentLoader


@final
class Constants:
    """Group module-level constants.

    Attributes:
        worker_url_key: Grouped module constant.
        control_credential_key: Grouped module constant.
        cloudflared_key: Grouped module constant.
        startup_timeout_key: Grouped module constant.
        restart_delay_key: Grouped module constant.
        tunnel_url_pattern: Grouped module constant.
        worker_url_pattern: Grouped module constant.
        kv_id_pattern: Grouped module constant.
        kv_placeholder: Grouped module constant.
        oauth_secret_key: Grouped module constant.
        wrangler_version: Grouped module constant.

    """

    worker_url_key: Final[str] = "EXACTUS_MCP_CLOUDFLARE_WORKER_URL"
    control_credential_key: Final[str] = (
        "EXACTUS_MCP_CLOUDFLARE_CONTROL_SECRET"
    )
    cloudflared_key: Final[str] = "EXACTUS_MCP_CLOUDFLARED"
    startup_timeout_key: Final[str] = (
        "EXACTUS_MCP_CLOUDFLARE_STARTUP_TIMEOUT_SECONDS"
    )
    restart_delay_key: Final[str] = (
        "EXACTUS_MCP_CLOUDFLARE_RESTART_DELAY_SECONDS"
    )
    tunnel_url_pattern: Final[Pattern[str]] = compile_pattern(
        pattern="https://[a-zA-Z0-9-]+\\.trycloudflare\\.com",
    )
    worker_url_pattern: Final[Pattern[str]] = compile_pattern(
        pattern="https://[a-zA-Z0-9.-]+\\.workers\\.dev",
    )
    kv_id_pattern: Final[Pattern[str]] = compile_pattern(
        pattern="[a-f0-9]{32}",
    )
    kv_placeholder: Final[str] = "REPLACE_WITH_KV_NAMESPACE_ID"
    oauth_secret_key: Final[str] = (
        "EXACTUS_MCP_CLOUDFLARE_OAUTH_LOGIN" + "_SECRET"
    )
    wrangler_version: Final[str] = "4.45.0"


@dataclass(frozen=True, slots=True)
class CloudflareConfig:
    """Configure stable Worker routing to an ephemeral Quick Tunnel.

    Attributes:
        worker_url: Stable HTTPS Worker origin fronting the tunnel.
        control_secret: Bearer credential shared with the Worker.
        cloudflared: Quick Tunnel executable name or path.
        startup_timeout_seconds: Maximum tunnel/server startup wait.
        restart_delay_seconds: Delay before restarting a dropped tunnel.

    """

    worker_url: str
    control_secret: str
    cloudflared: str = "cloudflared"
    startup_timeout_seconds: float = 30.0
    restart_delay_seconds: float = 1.0

    @classmethod
    def from_mapping(cls, *, values: Mapping[str, str]) -> Self:
        """Build publication settings from environment values.

        Args:
            values: Environment-style mapping with Cloudflare keys.

        Returns:
            Validated publication configuration.

        """
        config: Self = cls(
            worker_url=values.get(Constants.worker_url_key, "").rstrip("/"),
            control_secret=values.get(Constants.control_credential_key, ""),
            cloudflared=values.get(Constants.cloudflared_key, "cloudflared"),
            startup_timeout_seconds=cls._float_value(
                values=values,
                key=Constants.startup_timeout_key,
                default=30.0,
            ),
            restart_delay_seconds=cls._float_value(
                values=values,
                key=Constants.restart_delay_key,
                default=1.0,
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Reject incomplete or unsafe publication configuration.

        Raises:
            ValueError: If the URL, secret, or timing values are invalid.

        """
        if not self.worker_url.startswith("https://"):
            msg: str = f"{Constants.worker_url_key} must be an HTTPS URL"
            raise ValueError(msg)
        if not self.control_secret:
            msg = f"{Constants.control_credential_key} must not be empty"
            raise ValueError(msg)
        if self.startup_timeout_seconds <= 0:
            msg = "Cloudflare startup timeout must be positive"
            raise ValueError(msg)
        if self.restart_delay_seconds < 0:
            msg = "Cloudflare restart delay must not be negative"
            raise ValueError(msg)

    @staticmethod
    def _float_value(
        *,
        values: Mapping[str, str],
        key: str,
        default: float,
    ) -> float:
        """Parse one numeric environment value.

        Args:
            values: Environment-style mapping to read.
            key: Setting name to parse.
            default: Fallback used when the key is absent.

        Returns:
            Parsed floating-point value.

        Raises:
            ValueError: If the configured value is not numeric.

        """
        raw: str = values.get(key, str(object=default))
        try:
            return float(raw)
        except ValueError as error:
            msg: str = f"{key} must be numeric"
            raise ValueError(msg) from error


class CloudflareBootstrapper:
    """Provision the Worker, KV namespace, and secrets when required."""

    def __init__(self, *, root: Path, values: dict[str, str]) -> None:
        """Store project and environment state.

        Args:
            root: Repository root containing the bridge package.
            values: Mutable environment values updated by bootstrap.

        """
        self._root: Path = root
        self._values: dict[str, str] = values
        self._bridge: Path = root / "exactus/packages/exactus_mcp/bridge"
        self._wrangler: Path = self._bridge / "wrangler.toml"
        self._env: Path = root / ".env"

    async def ensure(self) -> None:
        """Create all persistent Cloudflare resources and local credentials."""
        await self._ensure_prerequisites()
        worker_url: str = self._values.get(
            Constants.worker_url_key,
            "",
        ).strip()
        control_secret: str = self._values.get(
            Constants.control_credential_key,
            "",
        ).strip()
        oauth_secret: str = self._values.get(
            Constants.oauth_secret_key,
            "",
        ).strip()
        namespace_ready: bool = self._namespace_id() is not None
        if (
            worker_url.startswith("https://")
            and control_secret
            and namespace_ready
        ):
            return
        self._require_tool(name="npx")
        await self._ensure_login()
        if not namespace_ready:
            await self._create_namespace()
        if not control_secret:
            control_secret = self._secret()
        if not oauth_secret:
            oauth_secret = self._secret()
        worker_url = await self._deploy()
        await self._put_secret(name="CONTROL_SECRET", value=control_secret)
        await self._put_secret(name="OAUTH_LOGIN_SECRET", value=oauth_secret)
        self._values[Constants.worker_url_key] = worker_url
        self._values[Constants.control_credential_key] = control_secret
        self._values[Constants.oauth_secret_key] = oauth_secret
        self._write_env()
        _ = stdout.write(
            f"Cloudflare bootstrap complete. OAuth "
            f"login credential was saved securely in {self._env}.\n",
        )
        stdout.flush()

    @staticmethod
    def _secret() -> str:
        """Generate a high-entropy URL-safe credential.

        Returns:
            Base64url credential without padding.

        """
        encoded: bytes = urlsafe_b64encode(s=urandom(32))
        return encoded.decode(encoding="ascii").rstrip("=")

    @staticmethod
    def _require_tool(*, name: str) -> None:
        """Reject bootstrap when a required executable is unavailable.

        Args:
            name: Executable resolved through PATH.

        Raises:
            RuntimeError: If the executable cannot be found.

        """
        if which(cmd=name) is not None:
            return
        msg: str = f"Required executable not found: {name}"
        raise RuntimeError(msg)

    @staticmethod
    async def _ensure_prerequisites() -> None:
        """Install CLI prerequisites through Homebrew when possible.

        Raises:
            RuntimeError: If a prerequisite is missing and cannot be
                installed.

        """
        for name in ("npx", "cloudflared"):
            if which(cmd=name) is not None:
                continue
            brew: str | None = which(cmd="brew")
            if brew is None:
                msg: str = (
                    f"{name} is required. Install Node.js and "
                    "cloudflared, or install Homebrew so Exactus "
                    "can provision them automatically."
                )
                raise RuntimeError(msg)
            package: str = "node" if name == "npx" else "cloudflared"
            process: Process = await create_subprocess_exec(
                brew,
                "install",
                package,
            )
            code: int = await process.wait()
            if code != 0 or which(cmd=name) is None:
                msg = f"Automatic installation failed for {package}"
                raise RuntimeError(msg)

    def _namespace_id(self) -> str | None:
        """Return configured KV namespace ID, excluding the template value.

        Returns:
            Namespace ID, or ``None`` while the placeholder remains.

        Raises:
            FileNotFoundError: If the Worker configuration is missing.

        """
        if not self._wrangler.is_file():
            msg: str = f"Missing Worker configuration: {self._wrangler}"
            raise FileNotFoundError(msg)
        content: str = self._wrangler.read_text(encoding="utf-8")
        if Constants.kv_placeholder in content:
            return None
        match: Match[str] | None = Constants.kv_id_pattern.search(
            string=content,
        )
        return match.group(0) if match is not None else None

    async def _ensure_login(self) -> None:
        """Reuse Wrangler authentication or launch its browser login flow.

        Raises:
            RuntimeError: If Wrangler authentication fails.

        """
        result: tuple[int, str] = await self._run_wrangler(
            arguments=("whoami",),
        )
        if result[0] == 0:
            return
        login: tuple[int, str] = await self._run_wrangler(arguments=("login",))
        if login[0] != 0:
            msg: str = "Cloudflare Wrangler authentication failed"
            raise RuntimeError(msg)

    async def _create_namespace(self) -> None:
        """Create ROUTING KV and persist its generated ID in wrangler.toml.

        Raises:
            RuntimeError: If creation fails, no ID is returned, or the
                placeholder disappears.

        """
        code, output = await self._run_wrangler(
            arguments=("kv", "namespace", "create", "ROUTING"),
        )
        if code != 0:
            msg: str = f"Unable to create Cloudflare KV namespace:\n{output}"
            raise RuntimeError(msg)
        match: Match[str] | None = Constants.kv_id_pattern.search(
            string=output,
        )
        if match is None:
            msg = f"Wrangler did not return a KV namespace ID:\n{output}"
            raise RuntimeError(msg)
        content: str = self._wrangler.read_text(encoding="utf-8")
        if Constants.kv_placeholder not in content:
            msg = "KV placeholder disappeared before it could be replaced"
            raise RuntimeError(msg)
        self._wrangler.write_text(
            data=content.replace(
                Constants.kv_placeholder,
                match.group(0),
                count=1,
            ),
            encoding="utf-8",
        )

    async def _deploy(self) -> str:
        """Deploy the Worker and return its permanent workers.dev origin.

        Returns:
            HTTPS workers.dev origin for the deployed Worker.

        Raises:
            RuntimeError: If deployment fails and no URL can be resolved.

        """
        code, output = await self._run_wrangler(arguments=("deploy",))
        if code != 0:
            msg: str = f"Cloudflare Worker deployment failed:\n{output}"
            raise RuntimeError(msg)
        match: Match[str] | None = Constants.worker_url_pattern.search(
            string=output,
        )
        if match is None:
            configured: str = self._values.get(
                Constants.worker_url_key,
                "",
            ).rstrip("/")
            if configured.startswith("https://"):
                return configured
            msg = f"Wrangler did not report the Worker URL:\n{output}"
            raise RuntimeError(msg)
        return match.group(0).rstrip("/")

    async def _put_secret(self, *, name: str, value: str) -> None:
        """Upload one generated secret without placing it in process argv.

        Args:
            name: Worker secret name.
            value: Secret payload piped to Wrangler stdin.

        Raises:
            RuntimeError: If Wrangler rejects the secret upload.

        """
        code, output = await self._run_wrangler(
            arguments=("secret", "put", name),
            input_text=f"{value}\n",
        )
        if code != 0:
            msg: str = f"Unable to configure Worker secret {name}:\n{output}"
            raise RuntimeError(msg)

    async def _run_wrangler(
        self,
        *,
        arguments: tuple[str, ...],
        input_text: str | None = None,
    ) -> tuple[int, str]:
        """Run the pinned Wrangler CLI and capture non-secret output.

        Args:
            arguments: Wrangler subcommand arguments.
            input_text: Optional stdin payload for secret upload.

        Returns:
            Exit code and combined Wrangler output.

        """
        process: Process = await create_subprocess_exec(
            "npx",
            "--yes",
            f"wrangler@{Constants.wrangler_version}",
            *arguments,
            cwd=self._bridge,
            stdin=PIPE if input_text is not None else None,
            stdout=PIPE,
            stderr=STDOUT,
        )
        input_bytes: bytes | None = None
        if input_text is not None:
            input_bytes = input_text.encode(encoding="utf-8")
        output_bytes, _ = await process.communicate(input=input_bytes)
        return (process.returncode or 0, output_bytes.decode(errors="replace"))

    def _write_env(self) -> None:
        """Persist generated configuration with owner-only permissions."""
        existing: dict[str, str] = {}
        if self._env.is_file():
            for line in self._env.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key:
                    existing[key] = value
        existing.update(
            {
                Constants.worker_url_key: self._values[
                    Constants.worker_url_key
                ],
                Constants.control_credential_key: self._values[
                    Constants.control_credential_key
                ],
                Constants.oauth_secret_key: self._values[
                    Constants.oauth_secret_key
                ],
            },
        )
        content: str = "".join(
            (f"{key}={value}\n" for key, value in sorted(existing.items())),
        )
        self._env.write_text(data=content, encoding="utf-8")
        self._env.chmod(mode=384)


class PublicationSupervisor:
    """Own Exactus MCP and continuously republish Quick Tunnel URLs."""

    def __init__(
        self,
        *,
        config: CloudflareConfig,
        root: Path,
        port: int,
    ) -> None:
        """Store publication configuration.

        Args:
            config: Validated Worker routing and credential settings.
            root: Repository root served by the local MCP process.
            port: Fixed loopback port for the local MCP server.

        """
        self._config: CloudflareConfig = config
        self._root: Path = root
        self._port: int = port

    @staticmethod
    async def stop(*, process: Process | None) -> None:
        """Terminate one owned child process.

        Args:
            process: Managed subprocess, or ``None`` when not started.

        """
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            _ = await process.wait()
        except ProcessLookupError:
            return

    async def run(self) -> int:
        """Run Exactus MCP and its self-healing Cloudflare tunnel.

        Returns:
            Local server exit code.

        """
        cloudflared: str = self.resolve_cloudflared()
        server: Process = await create_subprocess_exec(
            executable,
            "-m",
            "exactus.packages.exactus_mcp",
            "--root",
            str(object=self._root),
            "--port",
            str(object=self._port),
            "--access-token",
            self._config.control_secret,
            "--no-ngrok",
            "--no-menu-bar",
        )
        tunnel: Process | None = None
        try:
            await self.wait_for_server(server=server)
            while server.returncode is None:
                tunnel = await self.start_tunnel(cloudflared=cloudflared)
                backend_url: str = await self.read_tunnel_url(tunnel=tunnel)
                await self.publish(backend_url=backend_url)
                _ = stdout.write(f"Ready: {self._config.worker_url}/mcp\n")
                stdout.flush()
                _ = await tunnel.wait()
                if server.returncode is None:
                    await sleep(delay=self._config.restart_delay_seconds)
        finally:
            await self.stop(process=tunnel)
            await self.stop(process=server)
        return server.returncode or 0

    def resolve_cloudflared(self) -> str:
        """Resolve the configured cloudflared executable.

        Returns:
            Absolute or PATH-resolved executable path.

        Raises:
            ValueError: If no cloudflared executable can be resolved.

        """
        configured: Path = Path(self._config.cloudflared).expanduser()
        if configured.parent != Path() and configured.is_file():
            return str(object=configured)
        resolved: str | None = which(cmd=self._config.cloudflared)
        if resolved is not None:
            return resolved
        msg: str = f"cloudflared not found; set {Constants.cloudflared_key}"
        raise ValueError(msg)

    async def start_tunnel(self, *, cloudflared: str) -> Process:
        """Start one anonymous Quick Tunnel to the loopback server.

        Args:
            cloudflared: Resolved tunnel executable.

        Returns:
            Running cloudflared subprocess.

        """
        local_url: str = f"http://127.0.0.1:{self._port}"
        return await create_subprocess_exec(
            cloudflared,
            "tunnel",
            "--url",
            local_url,
            "--no-autoupdate",
            stdout=PIPE,
            stderr=STDOUT,
        )

    async def read_tunnel_url(self, *, tunnel: Process) -> str:
        """Read the assigned trycloudflare URL from cloudflared output.

        Args:
            tunnel: Running cloudflared subprocess.

        Returns:
            Assigned HTTPS Quick Tunnel URL.

        Raises:
            RuntimeError: If the tunnel exits before assigning a URL.
            TimeoutError: If no URL appears before the startup deadline.

        """
        stream: StreamReader | None = tunnel.stdout
        if stream is None:
            msg: str = "cloudflared output stream is unavailable"
            raise RuntimeError(msg)
        deadline: float = monotonic() + self._config.startup_timeout_seconds
        while monotonic() < deadline:
            remaining: float = deadline - monotonic()
            line_bytes: bytes = await wait_for(
                fut=stream.readline(),
                timeout=remaining,
            )
            if not line_bytes and tunnel.returncode is not None:
                msg = "cloudflared exited before assigning a tunnel URL"
                raise RuntimeError(msg)
            match: Match[str] | None = Constants.tunnel_url_pattern.search(
                string=line_bytes.decode(errors="replace"),
            )
            if match is not None:
                return match.group(0)
        msg = "timed out waiting for cloudflared tunnel URL"
        raise TimeoutError(msg)

    async def publish(self, *, backend_url: str) -> None:
        """Publish the active tunnel URL to the stable Worker.

        Args:
            backend_url: Current Quick Tunnel origin.

        """
        endpoint: str = f"{self._config.worker_url}/_control/backend"
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._config.control_secret}",
        }
        async with AsyncClient(
            timeout=self._config.startup_timeout_seconds,
        ) as client:
            response: Response = await client.post(
                url=endpoint,
                headers=headers,
                json={"url": backend_url},
            )
            _ = response.raise_for_status()

    async def wait_for_server(self, *, server: Process) -> None:
        """Wait until the local Exactus health endpoint succeeds.

        Args:
            server: Local Exactus MCP subprocess.

        Raises:
            RuntimeError: If the server exits before becoming healthy.
            TimeoutError: If the health endpoint does not respond in time.

        """
        deadline: float = monotonic() + self._config.startup_timeout_seconds
        health_url: str = f"http://127.0.0.1:{self._port}/health"
        async with AsyncClient(timeout=1.0) as client:
            while monotonic() < deadline:
                if server.returncode is not None:
                    msg: str = "Exactus MCP exited during startup"
                    raise RuntimeError(msg)
                try:
                    response: Response = await client.get(url=health_url)
                    if response.is_success:
                        return
                except HTTPError:
                    pass
                await sleep(delay=0.1)
        msg = "timed out waiting for Exactus MCP health endpoint"
        raise TimeoutError(msg)


def configured_port(*, root: Path) -> int:
    """Read the fixed MCP port from the project pyproject.toml.

    Args:
        root: Repository root containing pyproject.toml.

    Returns:
        Configured port, or the default when unset or invalid.

    """
    default_port: Final[int] = 6100
    maximum_port: Final[int] = 65535
    path: Path = root / "pyproject.toml"
    if not path.is_file():
        return default_port
    section: str = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped: str = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section != "[tool.exactus.mcp]":
            continue
        key, separator, raw_value = stripped.partition("=")
        if key.strip() != "port" or not separator:
            continue
        value: str = raw_value.partition("#")[0].strip()
        try:
            port: int = int(value)
        except ValueError:
            return default_port
        return port if 0 < port <= maximum_port else default_port
    return default_port


def main() -> int:
    """Run the automatic Exactus Cloudflare publication stack.

    Returns:
        Process exit status.

    """
    loaded: Path | None = EnvironmentLoader.load(values=environ)
    if loaded is not None:
        _ = stdout.write(f"Loaded configuration: {loaded}\n")
        stdout.flush()
    root: Path = Path.cwd().resolve()

    async def start() -> int:
        """Bootstrap credentials, then run the publication supervisor.

        Returns:
            Supervisor exit code.

        """
        values: dict[str, str] = dict(environ)
        bootstrapper: CloudflareBootstrapper = CloudflareBootstrapper(
            root=root,
            values=values,
        )
        await bootstrapper.ensure()
        config: CloudflareConfig = CloudflareConfig.from_mapping(values=values)
        supervisor: PublicationSupervisor = PublicationSupervisor(
            config=config,
            root=root,
            port=configured_port(root=root),
        )
        return await supervisor.run()

    try:
        return run_async(main=start())
    except KeyboardInterrupt:
        return 0
