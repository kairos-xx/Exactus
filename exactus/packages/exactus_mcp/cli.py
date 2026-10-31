# Copyright (c) 2026
"""Command line for the Exactus MCP and ngrok service."""

from __future__ import annotations

from argparse import ArgumentParser, BooleanOptionalAction, Namespace
from asyncio import FIRST_COMPLETED, Task, create_task, sleep, to_thread, wait
from asyncio import run as run_async
from dataclasses import dataclass
from importlib import import_module
from json import dumps
from os import environ
from pathlib import Path
from secrets import token_urlsafe
from sys import argv, stderr, stdout
from sys import platform as sys_platform
from threading import Event
from typing import TYPE_CHECKING, Final, Literal, Protocol, cast, final

from mcp.server.transport_security import TransportSecuritySettings
from uvicorn import Config, Server

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.server.local import free_port

from .activity import ServiceActivity
from .mantledb import MantleUrlStore
from .ngrok import NgrokTunnel
from .project_config import (
    ArgumentDefault,
    ConfigSelection,
    select_config,
    service_defaults,
    service_json_defaults,
)
from .runner import ExactusCommandRunner
from .service import ExactusMcpService, create_application
from .state import ServiceState

if TYPE_CHECKING:
    from starlette.types import ASGIApp

    from .supervisor import ServiceRunner


class MenuBarEntryPoint(Protocol):
    """Describe the lazily loaded macOS menu-bar entry point."""

    def __call__(
        self,
        *,
        config: RuntimeConfig,
        service_runner: ServiceRunner,
    ) -> int:
        """Run the menu-bar application and managed MCP service.

        Args:
            config: Validated service configuration.
            service_runner: Async service implementation to supervise.

        Returns:
            Native application exit status.

        """
        ...


@final
class Constants:
    """Group command-line defaults.

    Attributes:
        host: Default loopback interface.
        startup_timeout: Maximum Uvicorn startup wait.
        tunnel_timeout: Maximum ngrok startup wait.
        check_timeout: Maximum remote Exactus check duration.
        maximum_port: Highest valid TCP port.

    """

    host: Final[str] = "127.0.0.1"
    startup_timeout: Final[float] = 20.0
    tunnel_timeout: Final[float] = 30.0
    check_timeout: Final[float] = 900.0
    maximum_port: Final[int] = 65_535


@final
@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Validated service runtime configuration.

    Attributes:
        root: Project root exposed to Exactus.
        host: Loopback bind interface.
        port: TCP port, or zero to choose an ephemeral port.
        access_token: Optional caller-provided bearer token.
        ngrok: Whether to create the public tunnel.
        ngrok_command: Ngrok executable name or path.
        ngrok_url: Optional reserved ngrok URL.
        ngrok_endpoint: Optional named endpoint from ngrok configuration.
        mantledb_namespace: Optional namespace receiving the public URL.
        mantledb_path: Record path within the MantleDB namespace.
        mantledb_timeout: Maximum MantleDB request duration.
        tunnel_timeout: Maximum ngrok startup wait.
        check_timeout: Maximum Exactus check duration.
        log_level: Uvicorn log level.
        menu_bar: Whether to run the native macOS menu-bar controller.

    """

    root: Path
    host: str
    port: int
    access_token: str | None
    ngrok: bool
    ngrok_command: str
    ngrok_url: str | None
    ngrok_endpoint: str | None
    mantledb_namespace: str | None
    mantledb_path: str
    mantledb_timeout: float
    tunnel_timeout: float
    check_timeout: float
    log_level: Literal["critical", "error", "warning", "info", "debug"]
    menu_bar: bool


def _parser(
    *,
    defaults: dict[str, ArgumentDefault] | None = None,
) -> ArgumentParser:
    """Build the command-line parser.

    Args:
        defaults: Validated project configuration defaults.

    Returns:
        Exactus MCP argument parser.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="exactus-mcp",
        description=(
            "Serve protected Exactus MCP tools on loopback and expose the "
            "public status page and MCP endpoint through ngrok."
        ),
    )
    _ = parser.add_argument(
        "--config",
        metavar="JSON",
        nargs="?",
        help=(
            "Load a JSON config; when used alone, print the effective "
            "configuration with secrets redacted."
        ),
    )
    _ = parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root exposed to Exactus (default: current directory).",
    )
    _ = parser.add_argument(
        "--host",
        default=Constants.host,
        help="Loopback bind host (default: 127.0.0.1).",
    )
    _ = parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local port; zero chooses an available port (default: 0).",
    )
    _ = parser.add_argument(
        "--access-token",
        default=environ.get("EXACTUS_MCP_ACCESS_TOKEN"),
        help=(
            "Bearer token; defaults to EXACTUS_MCP_ACCESS_TOKEN or a newly "
            "generated secret. Prefer the environment over command history."
        ),
    )
    _ = parser.add_argument(
        "--ngrok",
        action=BooleanOptionalAction,
        default=True,
        help="Create an ngrok HTTPS tunnel (default: enabled).",
    )
    _ = parser.add_argument(
        "--ngrok-command",
        default="ngrok",
        help="Ngrok executable name or path (default: ngrok).",
    )
    _ = parser.add_argument(
        "--ngrok-url",
        help="Optional reserved ngrok URL or custom domain.",
    )
    _ = parser.add_argument(
        "--ngrok-endpoint",
        help=(
            "Named endpoint from ngrok.yml; its upstream must match --port."
        ),
    )
    _ = parser.add_argument(
        "--mantledb-namespace",
        default=environ.get("EXACTUS_MCP_MANTLEDB_NAMESPACE"),
        help=(
            "Optional MantleDB namespace that receives the active public "
            "ngrok origin."
        ),
    )
    _ = parser.add_argument(
        "--mantledb-path",
        default=environ.get("EXACTUS_MCP_MANTLEDB_PATH", "url"),
        help="MantleDB record path (default: url).",
    )
    _ = parser.add_argument(
        "--mantledb-timeout",
        type=float,
        default=10.0,
        help="Seconds allowed for MantleDB persistence (default: 10).",
    )
    _ = parser.add_argument(
        "--tunnel-timeout",
        type=float,
        default=Constants.tunnel_timeout,
        help="Seconds to wait for ngrok (default: 30).",
    )
    _ = parser.add_argument(
        "--check-timeout",
        type=float,
        default=Constants.check_timeout,
        help="Seconds allowed for each Exactus check (default: 900).",
    )
    _ = parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug"),
        default="info",
        help="Uvicorn log level (default: info).",
    )
    _ = parser.add_argument(
        "--menu-bar",
        action=BooleanOptionalAction,
        default=sys_platform == "darwin",
        help=("Run the native macOS status menu (default: enabled on macOS)."),
    )
    if defaults is not None:
        parser.set_defaults(**defaults)
    return parser


def _configuration_root(*, values: tuple[str, ...]) -> Path:
    """Return the project root needed before full argument parsing.

    Args:
        values: Raw command-line arguments.

    Returns:
        Explicit ``--root`` value or the current directory.

    """
    index: int
    value: str
    for index, value in enumerate(iterable=values):
        if value.startswith("--root="):
            return Path(value.partition("=")[2]).resolve()
        if value == "--root" and index + 1 < len(values):
            return Path(values[index + 1]).resolve()
    return Path.cwd().resolve()


def _has_root_option(*, values: tuple[str, ...]) -> bool:
    """Return whether raw arguments explicitly select a project root.

    Args:
        values: Raw non-configuration command-line arguments.

    Returns:
        Whether ``--root`` or ``--root=...`` occurs.

    """
    return any(
        value == "--root" or value.startswith("--root=") for value in values
    )


def _effective_defaults(
    *,
    selection: ConfigSelection,
) -> dict[str, ArgumentDefault]:
    """Merge built-ins, project TOML, private JSON, and environment values.

    Args:
        selection: Parsed configuration option and remaining arguments.

    Returns:
        Effective parser defaults before explicit CLI overrides.

    """
    json_defaults: dict[str, ArgumentDefault] = (
        {}
        if selection.path is None
        else service_json_defaults(path=selection.path)
    )
    selected_root: ArgumentDefault | None = json_defaults.get("root")
    root: Path = (
        _configuration_root(values=selection.arguments)
        if _has_root_option(values=selection.arguments)
        or not isinstance(selected_root, Path)
        else selected_root.resolve()
    )
    defaults: dict[str, ArgumentDefault] = {
        **service_defaults(root=root),
        **json_defaults,
    }
    environment_defaults: dict[str, str] = {
        key: value
        for key, variable in (
            ("access_token", "EXACTUS_MCP_ACCESS_TOKEN"),
            ("mantledb_namespace", "EXACTUS_MCP_MANTLEDB_NAMESPACE"),
            ("mantledb_path", "EXACTUS_MCP_MANTLEDB_PATH"),
        )
        if (value := environ.get(variable)) is not None
    }
    return {**defaults, **environment_defaults}


def _show_config(*, config: RuntimeConfig) -> None:
    """Print effective service configuration without revealing secrets.

    Args:
        config: Validated effective service configuration.

    """
    redacted: str = "<redacted>"
    payload: dict[str, bool | float | int | str | None] = {
        "root": str(object=config.root),
        "host": config.host,
        "port": config.port,
        "access-token": redacted if config.access_token else None,
        "ngrok": config.ngrok,
        "ngrok-command": config.ngrok_command,
        "ngrok-url": config.ngrok_url,
        "ngrok-endpoint": config.ngrok_endpoint,
        "mantledb-namespace": (
            redacted if config.mantledb_namespace else None
        ),
        "mantledb-path": config.mantledb_path,
        "mantledb-timeout": config.mantledb_timeout,
        "tunnel-timeout": config.tunnel_timeout,
        "check-timeout": config.check_timeout,
        "log-level": config.log_level,
        "menu-bar": config.menu_bar,
    }
    _ = stdout.write(f"{dumps(obj=payload, indent=2, sort_keys=True)}\n")


def _config(*, arguments: Namespace) -> RuntimeConfig:
    """Convert parsed arguments into typed runtime configuration.

    Args:
        arguments: Parsed command-line namespace.

    Returns:
        Typed runtime configuration.

    Raises:
        ValueError: If paths, ports, or timeouts are invalid.

    """
    root: Path = arguments.root.resolve()
    if not root.is_dir():
        msg: str = f"project root is not a directory: {root}"
        raise ValueError(msg)
    port: int = arguments.port
    if port < 0 or port > Constants.maximum_port:
        msg = "port must be between 0 and 65535"
        raise ValueError(msg)
    tunnel_timeout: float = arguments.tunnel_timeout
    check_timeout: float = arguments.check_timeout
    mantledb_timeout: float = arguments.mantledb_timeout
    if tunnel_timeout <= 0 or check_timeout <= 0 or mantledb_timeout <= 0:
        msg = "timeouts must be greater than zero"
        raise ValueError(msg)
    if (
        arguments.ngrok_url is not None
        and arguments.ngrok_endpoint is not None
    ):
        msg = "--ngrok-url and --ngrok-endpoint are mutually exclusive"
        raise ValueError(msg)
    mantledb_namespace: str | None = arguments.mantledb_namespace
    mantledb_path: str = arguments.mantledb_path
    if mantledb_namespace is not None and not mantledb_namespace.strip():
        msg = "MantleDB namespace cannot be empty"
        raise ValueError(msg)
    if not mantledb_path.strip():
        msg = "MantleDB path cannot be empty"
        raise ValueError(msg)
    return RuntimeConfig(
        root=root,
        host=arguments.host,
        port=port,
        access_token=arguments.access_token,
        ngrok=arguments.ngrok,
        ngrok_command=arguments.ngrok_command,
        ngrok_url=arguments.ngrok_url,
        ngrok_endpoint=arguments.ngrok_endpoint,
        mantledb_namespace=mantledb_namespace,
        mantledb_path=mantledb_path,
        mantledb_timeout=mantledb_timeout,
        tunnel_timeout=tunnel_timeout,
        check_timeout=check_timeout,
        log_level=arguments.log_level,
        menu_bar=arguments.menu_bar,
    )


async def _wait_started(*, server: Server, startup_timeout: float) -> None:
    """Wait for Uvicorn to accept requests.

    Args:
        server: Running Uvicorn server.
        startup_timeout: Maximum startup wait.

    Raises:
        RuntimeError: If startup fails or exceeds the timeout.

    """
    elapsed: float = 0.0
    while not server.started:
        if server.should_exit:
            msg: str = "Uvicorn exited before accepting requests"
            raise RuntimeError(msg)
        if elapsed >= startup_timeout:
            msg = f"Uvicorn did not start within {startup_timeout:g} seconds"
            raise RuntimeError(msg)
        await sleep(delay=0.05)
        elapsed += 0.05


async def _wait_for_stop(*, stop_requested: Event) -> None:
    """Wait asynchronously for a thread-safe stop request.

    Args:
        stop_requested: Event set by a local lifecycle controller.

    """
    _ = await to_thread(stop_requested.wait)


def _raise_unexpected_tunnel_exit(*, exit_code: int) -> None:
    """Raise the canonical error for an exited ngrok process.

    Args:
        exit_code: Unexpected ngrok process status.

    Raises:
        RuntimeError: Always.

    """
    msg: str = f"ngrok exited unexpectedly with status {exit_code}"
    raise RuntimeError(msg)


async def _start_tunnel(
    *,
    config: RuntimeConfig,
    state: ServiceState,
    activity: ServiceActivity,
    access_token: str,
) -> NgrokTunnel | None:
    """Start, publish, and record the configured public tunnel.

    Args:
        config: Validated service settings.
        state: Mutable service URL and transport state.
        activity: Shared lifecycle and caller activity sink.
        access_token: Bearer secret used to sign MantleDB discovery.

    Returns:
        Running ngrok tunnel, or ``None`` when exposure is disabled.

    """
    if not config.ngrok:
        return None
    activity.mark_updating(local_url=state.local_url)
    tunnel: NgrokTunnel = await NgrokTunnel.start(
        command=config.ngrok_command,
        upstream_url=state.local_url,
        startup_timeout=config.tunnel_timeout,
        requested_url=config.ngrok_url,
        endpoint_name=config.ngrok_endpoint,
    )
    state.expose(public_url=tunnel.public_url)
    if config.mantledb_namespace is not None:
        store: MantleUrlStore = MantleUrlStore(
            namespace=config.mantledb_namespace,
            path=config.mantledb_path,
            timeout=config.mantledb_timeout,
            signing_key=access_token,
        )
        await to_thread(store.save, url=tunnel.public_url)
    return tunnel


async def _wait_for_runtime(
    *,
    server: Server,
    server_task: Task[None],
    tunnel: NgrokTunnel | None,
    stop_task: Task[None],
    activity: ServiceActivity,
) -> None:
    """Wait for stop, server exit, or unexpected tunnel exit.

    Args:
        server: Running Uvicorn server.
        server_task: Uvicorn serve task.
        tunnel: Optional running ngrok tunnel.
        stop_task: Local controller stop waiter.
        activity: Shared lifecycle state.

    """
    tunnel_task: Task[int] | None = (
        None if tunnel is None else create_task(coro=tunnel.wait())
    )
    tasks: tuple[Task[None] | Task[int], ...] = (
        (server_task, stop_task)
        if tunnel_task is None
        else (server_task, tunnel_task, stop_task)
    )
    done: set[Task[None] | Task[int]] = (
        await wait(fs=tasks, return_when=FIRST_COMPLETED)
    )[0]
    if (
        tunnel_task is not None
        and tunnel_task in done
        and not server_task.done()
    ):
        _raise_unexpected_tunnel_exit(exit_code=tunnel_task.result())
    if stop_task.done() and not server_task.done():
        activity.mark_stopping()
        server.should_exit = True
    await server_task


async def run_service(
    *,
    config: RuntimeConfig,
    activity: ServiceActivity | None = None,
    stop_requested: Event | None = None,
) -> int:
    """Run Uvicorn and ngrok under one lifecycle.

    Args:
        config: Validated service runtime configuration.
        activity: Optional shared lifecycle and caller activity sink.
        stop_requested: Optional thread-safe graceful shutdown request.

    Returns:
        Zero after graceful shutdown.

    Raises:
        RuntimeError: If Uvicorn or ngrok cannot start or exits unexpectedly.

    """
    runtime_activity: ServiceActivity = activity or ServiceActivity()
    runtime_stop: Event = stop_requested or Event()
    runtime_activity.mark_starting()
    port: int = config.port or free_port()
    access_token: str = config.access_token or token_urlsafe(nbytes=32)
    local_hosts: list[str] = [
        config.host,
        f"{config.host}:{port}",
        "127.0.0.1",
        f"127.0.0.1:{port}",
        "localhost",
        f"localhost:{port}",
        "[::1]",
        f"[::1]:{port}",
    ]
    local_origins: list[str] = [
        f"http://{config.host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]
    state: ServiceState = ServiceState(
        root=config.root,
        host=config.host,
        port=port,
        access_token=access_token,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=local_hosts,
            allowed_origins=local_origins,
        ),
    )
    runner: ExactusCommandRunner = ExactusCommandRunner(
        root=config.root,
        timeout=config.check_timeout,
    )
    service: ExactusMcpService = ExactusMcpService(
        state=state,
        runner=runner,
        activity=runtime_activity,
    )
    application: ASGIApp = create_application(service=service, state=state)
    server: Server = Server(
        config=Config(
            app=application,
            host=config.host,
            port=port,
            log_level=config.log_level,
            lifespan="on",
        ),
    )
    server_task: Task[None] = create_task(coro=server.serve())
    tunnel: NgrokTunnel | None = None
    stop_task: Task[None] = create_task(
        coro=_wait_for_stop(stop_requested=runtime_stop),
    )
    failed: bool = False
    try:
        await _wait_started(
            server=server,
            startup_timeout=Constants.startup_timeout,
        )
        tunnel = await _start_tunnel(
            config=config,
            state=state,
            activity=runtime_activity,
            access_token=access_token,
        )
        runtime_activity.mark_running(
            local_url=state.local_url,
            public_url=state.public_url,
        )
        _show_connection(state=state)
        await _wait_for_runtime(
            server=server,
            server_task=server_task,
            tunnel=tunnel,
            stop_task=stop_task,
            activity=runtime_activity,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        failed = True
        runtime_activity.mark_failed(error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        server.should_exit = True
        if tunnel is not None:
            await tunnel.close()
        if not server_task.done():
            await server_task
        if not stop_task.done():
            stop_task.cancel()
        runtime_stop.set()
        if not failed:
            runtime_activity.mark_stopped()
    return 0


def _show_connection(*, state: ServiceState) -> None:
    """Print connection details after both services are ready.

    Args:
        state: Ready service state.

    """
    page_url: str = state.public_url or state.local_url
    _ = stdout.write(
        "\nExactus MCP is ready\n"
        f"Public page: {page_url}/\n"
        f"MCP endpoint: {state.mcp_url}\n"
        f"Bearer token: {state.access_token}\n"
        "Press Ctrl-C to close the MCP server and ngrok tunnel.\n\n",
    )
    stdout.flush()


def _run_macos_menu_bar(*, config: RuntimeConfig) -> int:
    """Load and run the optional native macOS menu-bar adapter.

    Args:
        config: Validated service configuration.

    Returns:
        Menu application exit status.

    """
    module_name: str = f"{__package__}.macos_menu"
    entry_point: MenuBarEntryPoint = cast(
        typ="MenuBarEntryPoint",
        val=import_module(name=module_name).run_menu_bar,
    )
    return entry_point(config=config, service_runner=run_service)


def _require_macos_menu_bar() -> None:
    """Reject the native menu option outside macOS.

    Raises:
        ValueError: If the current platform is not macOS.

    """
    if sys_platform != "darwin":
        msg: str = "--menu-bar is supported only on macOS"
        raise ValueError(msg)


def main() -> int:
    """Parse arguments and run the Exactus MCP service.

    Returns:
        Process exit status.

    """
    exc: OSError | RuntimeError | TypeError | ValueError
    try:
        values: tuple[str, ...] = tuple(argv[1:])
        selection: ConfigSelection = select_config(values=values)
        config: RuntimeConfig = _config(
            arguments=_parser(
                defaults=_effective_defaults(selection=selection),
            ).parse_args(args=selection.arguments),
        )
        if selection.list_only:
            _show_config(config=config)
            return 0
        if config.menu_bar:
            _require_macos_menu_bar()
            return _run_macos_menu_bar(config=config)
        return run_async(main=run_service(config=config))
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _ = stderr.write(f"exactus-mcp: {exc}\n")
        return 1
