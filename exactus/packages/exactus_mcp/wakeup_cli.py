# Copyright (c) 2026
"""Run and manage the signed Exactus MCP wake watcher."""

from __future__ import annotations

from argparse import (
    REMAINDER,
    ArgumentParser,
    BooleanOptionalAction,
    Namespace,
)
from asyncio import run as run_async
from dataclasses import dataclass
from json import dumps
from os import environ
from os import name as os_name
from pathlib import Path
from sys import argv, executable, stderr, stdout
from typing import Final, Protocol, TypedDict, Unpack, cast, final

from exactus.packages.argument_parser import ExactusArgumentParser

from .project_config import (
    ArgumentDefault,
    ConfigSelection,
    select_config,
    wake_defaults,
    wake_json_defaults,
)
from .startup import Constants as StartupConstants
from .startup import (
    StartupStatus,
    StartupWatcherManager,
    WatcherSecrets,
    default_startup_manager,
)
from .wakeup import (
    MantleWakeStore,
    WakeServiceLauncher,
    WakeStateStore,
    WakeWatcher,
)


@final
class Constants:
    """Group wake watcher command-line defaults.

    Attributes:
        default_poll_interval: Normal MantleDB polling delay in seconds.
        default_timeout: MantleDB request timeout in seconds.
        default_discovery_timeout: Maximum child URL discovery duration.
        default_retry_maximum: Maximum polling failure backoff.
        default_maximum_age: Wake-command replay window in seconds.
        actions: Supported lifecycle command names.

    """

    default_poll_interval: Final[float] = 3.0
    default_timeout: Final[float] = 10.0
    default_discovery_timeout: Final[float] = 45.0
    default_retry_maximum: Final[float] = 30.0
    default_maximum_age: Final[float] = 120.0
    actions: Final[frozenset[str]] = frozenset(
        ("install", "run", "status", "uninstall"),
    )


class SubparserArguments(TypedDict, total=False):
    """Describe supported lifecycle subparser construction options.

    Attributes:
        help: One-line action description shown by the parent parser.

    """

    help: str


class SubparserCollection(Protocol):
    """Expose the parser factory used by argparse subcommands."""

    def add_parser(
        self,
        name: str,
        **arguments: Unpack[SubparserArguments],
    ) -> ArgumentParser:
        """Create and return one action parser.

        Args:
            name: Lifecycle action name.
            **arguments: Parser construction options.

        Returns:
            Configured action parser.

        """
        ...


@final
@dataclass(frozen=True, slots=True)
class WakeRuntimeConfig:
    """Validated wake watcher configuration.

    Attributes:
        namespace: Private MantleDB namespace.
        signing_key: Dedicated wake HMAC key.
        access_token: MCP bearer and URL-signing token.
        command_path: MantleDB wake-command path.
        response_path: MantleDB ready-response path.
        url_path: MantleDB bearer-signed URL path.
        state_path: Durable completed-UUID path.
        poll_interval: Normal polling delay in seconds.
        request_timeout: MantleDB request timeout in seconds.
        discovery_timeout: Maximum child URL discovery duration.
        retry_maximum: Maximum polling failure backoff.
        maximum_age: Wake-command replay window in seconds.
        mcp_path: MCP path appended to a discovered origin.
        url_pattern: Regular expression locating emitted HTTPS URLs.
        service_command: Fixed shell-free child argument vector.
        keep_service_running: Whether to supervise the child before any signed
            wake request arrives.

    """

    namespace: str
    signing_key: str
    access_token: str
    command_path: str
    response_path: str
    url_path: str
    state_path: Path
    poll_interval: float
    request_timeout: float
    discovery_timeout: float
    retry_maximum: float
    maximum_age: float
    mcp_path: str
    url_pattern: str
    service_command: tuple[str, ...]
    keep_service_running: bool


def _add_watcher_arguments(
    *,
    parser: ArgumentParser,
    defaults: dict[str, ArgumentDefault] | None,
) -> None:
    """Add arguments shared by direct and installed watcher runs.

    Args:
        parser: Action parser receiving watcher options.
        defaults: Validated project and JSON defaults.

    """
    _ = parser.add_argument(
        "--mantledb-namespace",
        default=environ.get("EXACTUS_MCP_MANTLEDB_NAMESPACE"),
    )
    _ = parser.add_argument(
        "--wake-key",
        default=environ.get("EXACTUS_MCP_WAKE_KEY"),
        help="Wake HMAC key; prefer EXACTUS_MCP_WAKE_KEY over shell history.",
    )
    _ = parser.add_argument(
        "--access-token",
        default=environ.get("EXACTUS_MCP_ACCESS_TOKEN"),
        help=(
            "MCP bearer token inherited by the service; prefer "
            "EXACTUS_MCP_ACCESS_TOKEN over shell history."
        ),
    )
    _ = parser.add_argument(
        "--secrets-file",
        type=Path,
        help="Private secrets file created by the install action.",
    )
    _ = parser.add_argument("--command-path", default="wake/command")
    _ = parser.add_argument("--response-path", default="wake/response")
    _ = parser.add_argument(
        "--url-path",
        default=environ.get("EXACTUS_MCP_MANTLEDB_PATH", "url"),
    )
    _ = parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / ".exactus" / "mcp-wakeup" / "last-id",
    )
    _ = parser.add_argument(
        "--poll-interval",
        type=float,
        default=Constants.default_poll_interval,
    )
    _ = parser.add_argument(
        "--request-timeout",
        type=float,
        default=Constants.default_timeout,
    )
    _ = parser.add_argument(
        "--discovery-timeout",
        type=float,
        default=Constants.default_discovery_timeout,
    )
    _ = parser.add_argument(
        "--retry-maximum",
        type=float,
        default=Constants.default_retry_maximum,
    )
    _ = parser.add_argument(
        "--maximum-age",
        type=float,
        default=Constants.default_maximum_age,
    )
    _ = parser.add_argument("--mcp-path", default="/mcp")
    _ = parser.add_argument(
        "--url-pattern",
        default=r"(?<=MCP endpoint: )https://[^\s<>'\"]+",
    )
    _ = parser.add_argument(
        "--keep-service-running",
        action=BooleanOptionalAction,
        default=False,
        help=(
            "Start the fixed MCP service immediately and restart it after "
            "failure while continuing to process signed wake requests."
        ),
    )
    _ = parser.add_argument(
        "service_command",
        nargs=REMAINDER,
        default=(
            () if defaults is None else defaults.get("service_command", ())
        ),
        help="Fixed local service command, placed after --.",
    )


def _add_label_argument(*, parser: ArgumentParser) -> None:
    """Add the portable native-service label argument.

    Args:
        parser: Lifecycle parser receiving the service label.

    """
    _ = parser.add_argument(
        "--label",
        default=StartupConstants.default_label,
        help="Native user-service identifier.",
    )


def _parser(
    *,
    defaults: dict[str, ArgumentDefault] | None = None,
) -> ArgumentParser:
    """Build the wake watcher lifecycle parser.

    Args:
        defaults: Validated project configuration defaults.

    Returns:
        Parser containing run, install, status, and uninstall actions.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="exactus-mcp-wakeup",
        description=(
            "Run or manage the signed MantleDB watcher through launchd, "
            "systemd user services, or Windows Task Scheduler."
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
    actions: SubparserCollection = cast(
        typ="SubparserCollection",
        val=parser.add_subparsers(dest="action", required=True),
    )
    run_parser: ArgumentParser = actions.add_parser(
        name="run",
        help="Run the watcher in the foreground.",
    )
    _add_watcher_arguments(parser=run_parser, defaults=defaults)
    install_parser: ArgumentParser = actions.add_parser(
        name="install",
        help="Install and start the native user startup service.",
    )
    _add_label_argument(parser=install_parser)
    _add_watcher_arguments(parser=install_parser, defaults=defaults)
    status_parser: ArgumentParser = actions.add_parser(
        name="status",
        help="Show installation, load, running, and PID state.",
    )
    _add_label_argument(parser=status_parser)
    uninstall_parser: ArgumentParser = actions.add_parser(
        name="uninstall",
        help="Stop and remove the startup service and private secrets file.",
    )
    _add_label_argument(parser=uninstall_parser)
    if defaults is not None:
        action_parser: ArgumentParser
        for action_parser in (
            run_parser,
            install_parser,
            status_parser,
            uninstall_parser,
        ):
            action_parser.set_defaults(**defaults)
    return parser


def _secrets(*, arguments: Namespace) -> WatcherSecrets:
    """Resolve secrets from options, environment, or a private file.

    Args:
        arguments: Parsed watcher action arguments.

    Returns:
        Validated wake key and MCP bearer token.

    Raises:
        ValueError: If neither complete inline values nor a secrets file is
            available.

    """
    wake_key_value: str | None = arguments.wake_key
    access_token_value: str | None = arguments.access_token
    if wake_key_value and access_token_value:
        return WatcherSecrets(
            wake_key=wake_key_value,
            access_token=access_token_value,
        )
    secrets_path: Path | None = arguments.secrets_file
    if secrets_path is None:
        msg: str = (
            "EXACTUS_MCP_WAKE_KEY and EXACTUS_MCP_ACCESS_TOKEN are required"
        )
        raise ValueError(msg)
    return WatcherSecrets.load(
        path=secrets_path,
        require_posix_mode=os_name == "posix",
    )


def _config(*, arguments: Namespace) -> WakeRuntimeConfig:
    """Validate parsed wake watcher arguments.

    Args:
        arguments: Parsed run or install action arguments.

    Returns:
        Complete validated watcher configuration.

    Raises:
        ValueError: If required values, intervals, or the fixed command are
            invalid.

    """
    namespace_value: str | None = arguments.mantledb_namespace
    namespace: str = "" if namespace_value is None else namespace_value.strip()
    if not namespace:
        msg: str = "EXACTUS_MCP_MANTLEDB_NAMESPACE is required"
        raise ValueError(msg)
    service_arguments: list[str] = list(arguments.service_command)
    if service_arguments and service_arguments[0] == "--":
        _ = service_arguments.pop(0)
    if not service_arguments:
        msg = "a fixed service command is required after --"
        raise ValueError(msg)
    positive_values: tuple[float, ...] = (
        arguments.poll_interval,
        arguments.request_timeout,
        arguments.discovery_timeout,
        arguments.retry_maximum,
        arguments.maximum_age,
    )
    if any(value <= 0 for value in positive_values):
        msg = "wake intervals and timeouts must be positive"
        raise ValueError(msg)
    if arguments.retry_maximum < arguments.poll_interval:
        msg = "retry maximum cannot be smaller than poll interval"
        raise ValueError(msg)
    secrets: WatcherSecrets = _secrets(arguments=arguments)
    return WakeRuntimeConfig(
        namespace=namespace,
        signing_key=secrets.wake_key,
        access_token=secrets.access_token,
        command_path=arguments.command_path,
        response_path=arguments.response_path,
        url_path=arguments.url_path,
        state_path=arguments.state,
        poll_interval=arguments.poll_interval,
        request_timeout=arguments.request_timeout,
        discovery_timeout=arguments.discovery_timeout,
        retry_maximum=arguments.retry_maximum,
        maximum_age=arguments.maximum_age,
        mcp_path=arguments.mcp_path,
        url_pattern=arguments.url_pattern,
        service_command=tuple(service_arguments),
        keep_service_running=arguments.keep_service_running,
    )


async def run_watcher(*, config: WakeRuntimeConfig) -> int:
    """Build and run the configured wake watcher.

    Args:
        config: Validated watcher configuration.

    Returns:
        Zero after graceful watcher shutdown.

    """
    child_environment: dict[str, str] = dict(environ)
    child_environment["EXACTUS_MCP_ACCESS_TOKEN"] = config.access_token
    child_environment["EXACTUS_MCP_MANTLEDB_NAMESPACE"] = config.namespace
    child_environment["EXACTUS_MCP_MANTLEDB_PATH"] = config.url_path
    launcher: WakeServiceLauncher = WakeServiceLauncher(
        command=config.service_command,
        discovery_timeout=config.discovery_timeout,
        mcp_path=config.mcp_path,
        url_pattern=config.url_pattern,
        environment=child_environment,
    )
    watcher: WakeWatcher = WakeWatcher(
        store=MantleWakeStore(
            namespace=config.namespace,
            signing_key=config.signing_key,
            command_path=config.command_path,
            response_path=config.response_path,
            timeout=config.request_timeout,
            maximum_age=config.maximum_age,
        ),
        state=WakeStateStore(path=config.state_path),
        launcher=launcher,
        poll_interval=config.poll_interval,
        retry_maximum=config.retry_maximum,
        keep_service_running=config.keep_service_running,
    )
    try:
        await watcher.run()
    finally:
        await launcher.close()
    return 0


def _manager(*, label: str) -> StartupWatcherManager:
    """Build the current platform's native startup manager.

    Args:
        label: Stable native user-service identifier.

    Returns:
        Platform-specific watcher lifecycle manager.

    """
    return default_startup_manager(label=label, home=Path.home())


def _run_program_arguments(
    *,
    config: WakeRuntimeConfig,
    secrets_path: Path,
) -> tuple[str, ...]:
    """Build the secret-free watcher command persisted by native startup.

    Args:
        config: Validated watcher configuration.
        secrets_path: Private installed secrets-file path.

    Returns:
        Complete shell-free foreground watcher argument vector.

    """
    program_arguments: tuple[str, ...] = (
        executable,
        "-m",
        "exactus.packages.exactus_mcp.wakeup_cli",
        "run",
        "--mantledb-namespace",
        config.namespace,
        "--secrets-file",
        str(object=secrets_path),
        "--command-path",
        config.command_path,
        "--response-path",
        config.response_path,
        "--url-path",
        config.url_path,
        "--state",
        str(object=config.state_path),
        "--poll-interval",
        str(object=config.poll_interval),
        "--request-timeout",
        str(object=config.request_timeout),
        "--discovery-timeout",
        str(object=config.discovery_timeout),
        "--retry-maximum",
        str(object=config.retry_maximum),
        "--maximum-age",
        str(object=config.maximum_age),
        "--mcp-path",
        config.mcp_path,
        "--url-pattern",
        config.url_pattern,
    )
    if config.keep_service_running:
        program_arguments = (*program_arguments, "--keep-service-running")
    return (*program_arguments, "--", *config.service_command)


def _show_status(*, status: StartupStatus) -> None:
    """Print one stable native watcher status record.

    Args:
        status: Normalized native lifecycle status.

    """
    process_text: str = (
        "none"
        if status.process_identifier is None
        else str(object=status.process_identifier)
    )
    _ = stdout.write(
        f"Backend: {status.backend}\n"
        f"Installed: {'yes' if status.installed else 'no'}\n"
        f"Loaded: {'yes' if status.loaded else 'no'}\n"
        f"Running: {'yes' if status.running else 'no'}\n"
        f"PID: {process_text}\n",
    )


def _arguments(*, values: tuple[str, ...]) -> tuple[str, ...]:
    """Preserve the pre-lifecycle foreground syntax as an implicit run.

    Args:
        values: Raw command-line arguments.

    Returns:
        Arguments with an implicit ``run`` action when needed.

    """
    if (
        not values
        or values[0] in Constants.actions
        or values[0] in ("-h", "--help")
    ):
        return values
    return ("run", *values)


def _effective_defaults(
    *,
    selection: ConfigSelection,
) -> dict[str, ArgumentDefault]:
    """Merge project, private JSON, and environment watcher defaults.

    Args:
        selection: Parsed configuration option and remaining arguments.

    Returns:
        Effective parser defaults before explicit CLI overrides.

    """
    json_defaults: dict[str, ArgumentDefault] = (
        {}
        if selection.path is None
        else wake_json_defaults(path=selection.path)
    )
    defaults: dict[str, ArgumentDefault] = {
        **wake_defaults(root=Path.cwd().resolve()),
        **json_defaults,
    }
    environment_defaults: dict[str, str] = {
        key: value
        for key, variable in (
            ("access_token", "EXACTUS_MCP_ACCESS_TOKEN"),
            ("mantledb_namespace", "EXACTUS_MCP_MANTLEDB_NAMESPACE"),
            ("url_path", "EXACTUS_MCP_MANTLEDB_PATH"),
            ("wake_key", "EXACTUS_MCP_WAKE_KEY"),
        )
        if (value := environ.get(variable)) is not None
    }
    return {**defaults, **environment_defaults}


def _show_effective_config(*, arguments: Namespace) -> None:
    """Print effective watcher settings with credentials redacted.

    Args:
        arguments: Parsed install-shaped configuration namespace.

    """
    redacted: str = "<redacted>"
    service_command: list[str] = list(arguments.service_command)
    if service_command and service_command[0] == "--":
        _ = service_command.pop(0)
    secrets_path: Path | None = arguments.secrets_file
    state_path: Path = arguments.state
    payload: dict[str, bool | float | str | list[str] | None] = {
        "label": arguments.label,
        "mantledb-namespace": (
            redacted if arguments.mantledb_namespace else None
        ),
        "wake-key": redacted if arguments.wake_key else None,
        "access-token": redacted if arguments.access_token else None,
        "secrets-file": (
            None if secrets_path is None else str(object=secrets_path)
        ),
        "command-path": arguments.command_path,
        "response-path": arguments.response_path,
        "url-path": arguments.url_path,
        "state": str(object=state_path),
        "poll-interval": arguments.poll_interval,
        "request-timeout": arguments.request_timeout,
        "discovery-timeout": arguments.discovery_timeout,
        "retry-maximum": arguments.retry_maximum,
        "maximum-age": arguments.maximum_age,
        "mcp-path": arguments.mcp_path,
        "url-pattern": arguments.url_pattern,
        "keep-service-running": arguments.keep_service_running,
        "service-command": service_command,
    }
    _ = stdout.write(f"{dumps(obj=payload, indent=2, sort_keys=True)}\n")


def _execute(*, namespace: Namespace) -> int:
    """Execute one parsed watcher lifecycle action.

    Args:
        namespace: Parsed lifecycle action and configuration.

    Returns:
        Process status for the selected action.

    """
    if namespace.action == "run":
        return run_async(main=run_watcher(config=_config(arguments=namespace)))
    result: int = 0
    manager: StartupWatcherManager = _manager(label=namespace.label)
    if namespace.action == "install":
        config: WakeRuntimeConfig = _config(arguments=namespace)
        installed_status: StartupStatus = manager.install(
            program_arguments=_run_program_arguments(
                config=config,
                secrets_path=manager.secrets_path,
            ),
            secrets=WatcherSecrets(
                wake_key=config.signing_key,
                access_token=config.access_token,
            ),
        )
        _show_status(status=installed_status)
    elif namespace.action == "uninstall":
        _show_status(status=manager.uninstall())
    else:
        current_status: StartupStatus = manager.status()
        _show_status(status=current_status)
        result = 0 if current_status.running else 1
    return result


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Run or manage the native signed wake watcher.

    Args:
        arguments: Injected command-line arguments for tests.

    Returns:
        Process exit status.

    """
    try:
        values: tuple[str, ...] = (
            tuple(argv[1:]) if arguments is None else arguments
        )
        selection: ConfigSelection = select_config(values=values)
        defaults: dict[str, ArgumentDefault] = _effective_defaults(
            selection=selection,
        )
        result: int = 0
        if selection.list_only:
            configuration_namespace: Namespace = _parser(
                defaults=defaults,
            ).parse_args(args=("install",))
            _show_effective_config(arguments=configuration_namespace)
        else:
            namespace: Namespace = _parser(defaults=defaults).parse_args(
                args=_arguments(values=selection.arguments),
            )
            result = _execute(namespace=namespace)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _ = stderr.write(f"exactus-mcp-wakeup: {exc}\n")
        return 1
    else:
        return result


if __name__ == "__main__":
    raise SystemExit(main())
