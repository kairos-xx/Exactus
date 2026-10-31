# Copyright (c) 2026
"""Manage native startup for the Exactus MCP wake watcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from json import dumps, loads
from plistlib import FMT_XML
from plistlib import dumps as dump_plist
from re import Match, search
from subprocess import CompletedProcess, list2cmdline, run
from sys import platform
from typing import TYPE_CHECKING, Final, Protocol, cast, final

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.packages.server.json_types import JsonValue


@final
class Constants:
    """Group native startup manager constants.

    Attributes:
        default_label: Default native user-service identifier.
        private_mode: POSIX mode for the separate secrets file.
        public_mode: POSIX mode for secret-free service definitions.

    """

    default_label: Final[str] = "com.exactus.mcp-wakeup"
    private_mode: Final[int] = 0o600
    public_mode: Final[int] = 0o644


@final
@dataclass(frozen=True, slots=True)
class WatcherSecrets:
    """Hold secrets persisted outside native service definitions.

    Attributes:
        wake_key: Dedicated wake-command HMAC key.
        access_token: Exactus MCP bearer and URL-signing token.

    """

    wake_key: str = field(repr=False)
    access_token: str = field(repr=False)

    @classmethod
    def load(cls, *, path: Path, require_posix_mode: bool) -> WatcherSecrets:
        """Load credentials from a private JSON file.

        Args:
            path: Installed secrets-file path.
            require_posix_mode: Whether to reject group or world permission
                bits.

        Returns:
            Validated watcher credentials.

        Raises:
            TypeError: If the JSON object has invalid member types.
            ValueError: If the POSIX file permissions expose the secrets.

        """
        if require_posix_mode and path.stat().st_mode & 0o077:
            msg: str = f"watcher secrets file is not mode 0600: {path}"
            raise ValueError(msg)
        document: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_bytes()),
        )
        if not isinstance(document, dict):
            msg = "watcher secrets document must be an object"
            raise TypeError(msg)
        wake_key: JsonValue | None = document.get("wake_key")
        access_token: JsonValue | None = document.get("access_token")
        if not isinstance(wake_key, str) or not isinstance(access_token, str):
            msg = "watcher secrets document is incomplete"
            raise TypeError(msg)
        return cls(wake_key=wake_key, access_token=access_token)

    def serialize(self) -> bytes:
        """Serialize credentials for a private JSON file.

        Returns:
            Deterministic UTF-8 JSON bytes.

        """
        return dumps(
            obj={"access_token": self.access_token, "wake_key": self.wake_key},
            sort_keys=True,
        ).encode(encoding="utf-8")

    def __post_init__(self) -> None:
        """Reject empty persisted credentials."""
        if not self.wake_key or not self.access_token:
            msg: str = "wake key and MCP access token are required"
            raise ValueError(msg)


@final
@dataclass(frozen=True, slots=True)
class StartupStatus:
    """Describe native watcher installation and process state.

    Attributes:
        backend: Selected native startup backend.
        installed: Whether the persistent definition exists.
        loaded: Whether the native service manager knows the definition.
        running: Whether the watcher is currently active.
        process_identifier: Watcher PID when the backend exposes it.

    """

    backend: str
    installed: bool
    loaded: bool
    running: bool
    process_identifier: int | None


class CommandRunner(Protocol):
    """Run one local lifecycle command without a shell."""

    def __call__(self, *, arguments: tuple[str, ...]) -> CompletedProcess[str]:
        """Return one completed process result.

        Args:
            arguments: Shell-free native command argument vector.

        Returns:
            Completed native command result.

        """
        ...


def default_command_runner(
    *,
    arguments: tuple[str, ...],
) -> CompletedProcess[str]:
    """Run one native lifecycle command without raising automatically.

    Args:
        arguments: Shell-free native command argument vector.

    Returns:
        Completed native command result with captured text streams.

    """
    return run(args=arguments, check=False, capture_output=True, text=True)


@final
@dataclass(slots=True)
class StartupWatcherManager:
    """Install and inspect the watcher through the native user service API.

    Attributes:
        label: Stable native user-service identifier.
        definition_path: Platform-specific service definition or launcher.
        secrets_path: Private credential file outside the definition.
        stdout_path: Persistent watcher standard-output log.
        stderr_path: Persistent watcher standard-error log.
        platform_name: Python platform identifier selecting the backend.
        user_identifier: POSIX user identifier required by launchd.
        command_runner: Injected shell-free lifecycle command boundary.

    """

    label: str
    definition_path: Path
    secrets_path: Path
    stdout_path: Path
    stderr_path: Path
    platform_name: str = platform
    user_identifier: int = 0
    command_runner: CommandRunner = field(
        default=default_command_runner,
        repr=False,
    )

    @property
    def backend(self) -> str:
        """Return the selected native startup backend.

        Returns:
            ``launchd``, ``systemd-user``, or ``task-scheduler``.

        Raises:
            RuntimeError: If the current platform is unsupported.

        """
        if self.platform_name == "darwin":
            return "launchd"
        if self.platform_name.startswith("linux"):
            return "systemd-user"
        if self.platform_name == "win32":
            return "task-scheduler"
        msg: str = f"unsupported startup platform: {self.platform_name}"
        raise RuntimeError(msg)

    def install(
        self,
        *,
        program_arguments: tuple[str, ...],
        secrets: WatcherSecrets,
    ) -> StartupStatus:
        """Persist and start the watcher through the native backend.

        Args:
            program_arguments: Secret-free watcher argument vector.
            secrets: Credentials written outside the service definition.

        Returns:
            Native status after installation and immediate startup.

        Raises:
            ValueError: If the watcher argument vector is empty.

        """
        if not program_arguments:
            msg: str = "startup program arguments cannot be empty"
            raise ValueError(msg)
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        self.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        self.stderr_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            path=self.secrets_path,
            payload=secrets.serialize(),
            mode=Constants.private_mode,
        )
        if self.backend == "launchd":
            self._install_launchd(program_arguments=program_arguments)
        elif self.backend == "systemd-user":
            self._install_systemd(program_arguments=program_arguments)
        else:
            self._install_windows(program_arguments=program_arguments)
        return self.status()

    def uninstall(self) -> StartupStatus:
        """Stop the watcher and remove its definition and secrets.

        Returns:
            Native status after removal.

        """
        if self.backend == "launchd":
            if self.status().loaded:
                self._run_required(
                    arguments=("launchctl", "bootout", self._launchd_target()),
                )
            self.definition_path.unlink(missing_ok=True)
        elif self.backend == "systemd-user":
            current: StartupStatus = self.status()
            if current.loaded or current.installed:
                self._run_optional(
                    arguments=(
                        "systemctl",
                        "--user",
                        "disable",
                        "--now",
                        self._systemd_unit(),
                    ),
                )
            self.definition_path.unlink(missing_ok=True)
            self._run_required(
                arguments=("systemctl", "--user", "daemon-reload"),
            )
        else:
            self._run_optional(
                arguments=("schtasks.exe", "/End", "/TN", self.label),
            )
            self._run_optional(
                arguments=("schtasks.exe", "/Delete", "/TN", self.label, "/F"),
            )
            self.definition_path.unlink(missing_ok=True)
        self.secrets_path.unlink(missing_ok=True)
        return self.status()

    def status(self) -> StartupStatus:
        """Return current installation and native process state.

        Returns:
            Current normalized native watcher status.

        """
        if self.backend == "launchd":
            return self._launchd_status()
        if self.backend == "systemd-user":
            return self._systemd_status()
        return self._windows_status()

    @staticmethod
    def _atomic_write(*, path: Path, payload: bytes, mode: int) -> None:
        """Write one lifecycle file atomically with an explicit mode.

        Args:
            path: Destination service, launcher, or secrets path.
            payload: Complete file bytes.
            mode: POSIX-compatible permission mode.

        """
        temporary: Path = path.with_suffix(suffix=f"{path.suffix}.tmp")
        temporary.touch(mode=mode, exist_ok=True)
        temporary.chmod(mode=mode)
        temporary.write_bytes(data=payload)
        temporary.chmod(mode=mode)
        temporary.replace(target=path)

    @staticmethod
    def _systemd_quote(*, value: str) -> str:
        """Quote one systemd command argument without invoking a shell.

        Args:
            value: Literal argument value.

        Returns:
            Escaped double-quoted systemd argument.

        """
        escaped: str = (
            value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
        )
        return f'"{escaped}"'

    def _install_launchd(self, *, program_arguments: tuple[str, ...]) -> None:
        """Install a macOS per-user LaunchAgent.

        Args:
            program_arguments: Secret-free watcher argument vector.

        """
        self.definition_path.parent.mkdir(parents=True, exist_ok=True)
        document: dict[str, bool | int | list[str] | str] = {
            "KeepAlive": True,
            "Label": self.label,
            "ProcessType": "Background",
            "ProgramArguments": list(program_arguments),
            "RunAtLoad": True,
            "StandardErrorPath": str(object=self.stderr_path),
            "StandardOutPath": str(object=self.stdout_path),
            "ThrottleInterval": 10,
        }
        self._atomic_write(
            path=self.definition_path,
            payload=dump_plist(value=document, fmt=FMT_XML, sort_keys=True),
            mode=Constants.public_mode,
        )
        if self._launchd_status().loaded:
            self._run_required(
                arguments=("launchctl", "bootout", self._launchd_target()),
            )
        self._run_required(
            arguments=(
                "launchctl",
                "bootstrap",
                f"gui/{self.user_identifier}",
                str(object=self.definition_path),
            ),
        )

    def _install_systemd(self, *, program_arguments: tuple[str, ...]) -> None:
        """Install a Linux per-user systemd service.

        Args:
            program_arguments: Secret-free watcher argument vector.

        """
        self.definition_path.parent.mkdir(parents=True, exist_ok=True)
        command: str = " ".join(
            self._systemd_quote(value=value) for value in program_arguments
        )
        payload: str = (
            "[Unit]\n"
            "Description=Exactus MCP MantleDB wake watcher\n"
            "Wants=network-online.target\n"
            "After=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={command}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n"
            f"StandardOutput=append:{self.stdout_path}\n"
            f"StandardError=append:{self.stderr_path}\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        self._atomic_write(
            path=self.definition_path,
            payload=payload.encode(encoding="utf-8"),
            mode=Constants.public_mode,
        )
        self._run_required(arguments=("systemctl", "--user", "daemon-reload"))
        self._run_required(
            arguments=(
                "systemctl",
                "--user",
                "enable",
                "--now",
                self._systemd_unit(),
            ),
        )

    def _install_windows(self, *, program_arguments: tuple[str, ...]) -> None:
        """Install a Windows per-user logon task and start it now.

        Args:
            program_arguments: Secret-free watcher argument vector.

        """
        self.definition_path.parent.mkdir(parents=True, exist_ok=True)
        launcher: str = (
            '"""Launch the installed Exactus MCP wake watcher."""\n'
            "from subprocess import run\n\n"
            f"arguments = {program_arguments!r}\n"
            "result = run(args=arguments, check=False)\n"
            "raise SystemExit(result.returncode)\n"
        )
        self._atomic_write(
            path=self.definition_path,
            payload=launcher.encode(encoding="utf-8"),
            mode=Constants.public_mode,
        )
        command: str = list2cmdline(
            seq=[program_arguments[0], str(object=self.definition_path)],
        )
        self._run_required(
            arguments=(
                "schtasks.exe",
                "/Create",
                "/TN",
                self.label,
                "/TR",
                command,
                "/SC",
                "ONLOGON",
                "/RL",
                "LIMITED",
                "/F",
            ),
        )
        self._run_required(
            arguments=("schtasks.exe", "/Run", "/TN", self.label),
        )

    def _launchd_status(self) -> StartupStatus:
        """Inspect one macOS LaunchAgent.

        Returns:
            Normalized LaunchAgent status.

        """
        result: CompletedProcess[str] = self.command_runner(
            arguments=("launchctl", "print", self._launchd_target()),
        )
        loaded: bool = result.returncode == 0
        state_match: Match[str] | None = search(
            pattern=r"\bstate\s*=\s*running\b",
            string=result.stdout,
        )
        process_match: Match[str] | None = search(
            pattern=r"\bpid\s*=\s*(\d+)\b",
            string=result.stdout,
        )
        process_identifier: int | None = (
            int(process_match.group(1)) if process_match is not None else None
        )
        return StartupStatus(
            backend=self.backend,
            installed=self.definition_path.is_file(),
            loaded=loaded,
            running=loaded and state_match is not None,
            process_identifier=process_identifier,
        )

    def _systemd_status(self) -> StartupStatus:
        """Inspect one Linux per-user systemd service.

        Returns:
            Normalized systemd user-service status.

        """
        result: CompletedProcess[str] = self.command_runner(
            arguments=(
                "systemctl",
                "--user",
                "show",
                self._systemd_unit(),
                "--property=LoadState",
                "--property=ActiveState",
                "--property=MainPID",
                "--no-pager",
            ),
        )
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key: str
            separator: str
            value: str
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value
        process_text: str = values.get("MainPID", "0")
        process_identifier: int | None = (
            int(process_text)
            if process_text.isdigit() and process_text != "0"
            else None
        )
        loaded: bool = values.get("LoadState") == "loaded"
        return StartupStatus(
            backend=self.backend,
            installed=self.definition_path.is_file(),
            loaded=loaded,
            running=loaded and values.get("ActiveState") == "active",
            process_identifier=process_identifier,
        )

    def _windows_status(self) -> StartupStatus:
        """Inspect one Windows scheduled task.

        Returns:
            Normalized Task Scheduler status.

        """
        result: CompletedProcess[str] = self.command_runner(
            arguments=(
                "schtasks.exe",
                "/Query",
                "/TN",
                self.label,
                "/FO",
                "LIST",
                "/V",
            ),
        )
        installed: bool = result.returncode == 0
        running: bool = bool(
            search(
                pattern=r"(?im)^Status:\s*Running\s*$",
                string=result.stdout,
            ),
        )
        return StartupStatus(
            backend=self.backend,
            installed=installed and self.definition_path.is_file(),
            loaded=installed,
            running=installed and running,
            process_identifier=None,
        )

    def _launchd_target(self) -> str:
        """Return the current user's launchd service target.

        Returns:
            Launchd domain and service target.

        """
        return f"gui/{self.user_identifier}/{self.label}"

    def _systemd_unit(self) -> str:
        """Return the systemd unit name.

        Returns:
            Service label with the ``.service`` suffix.

        """
        return f"{self.label}.service"

    def _run_required(self, *, arguments: tuple[str, ...]) -> None:
        """Run one lifecycle command and surface bounded diagnostics.

        Args:
            arguments: Shell-free native lifecycle command.

        Raises:
            RuntimeError: If the command exits unsuccessfully.

        """
        result: CompletedProcess[str] = self.command_runner(
            arguments=arguments,
        )
        if result.returncode == 0:
            return
        detail: str = result.stderr.strip() or result.stdout.strip()
        msg: str = f"{' '.join(arguments[:2])} failed: {detail}"
        raise RuntimeError(msg)

    def _run_optional(self, *, arguments: tuple[str, ...]) -> None:
        """Run idempotent cleanup whose missing-target failure is harmless.

        Args:
            arguments: Shell-free native cleanup command.

        """
        _result: CompletedProcess[str] = self.command_runner(
            arguments=arguments,
        )


def default_startup_manager(
    *,
    label: str,
    home: Path,
    platform_name: str = platform,
) -> StartupWatcherManager:
    """Build the native startup manager and platform-specific paths.

    Args:
        label: Stable native user-service identifier.
        home: Current user's home directory.
        platform_name: Python platform identifier.

    Returns:
        Manager configured for the selected native backend.

    Raises:
        RuntimeError: If the requested platform is unsupported.

    """
    config_root: Path
    log_root: Path
    definition_path: Path
    if platform_name == "darwin":
        config_root = home / ".config" / "exactus" / "mcp-wakeup"
        log_root = home / "Library" / "Logs" / "Exactus"
        definition_path = home / "Library" / "LaunchAgents" / f"{label}.plist"
    elif platform_name.startswith("linux"):
        config_root = home / ".config" / "exactus" / "mcp-wakeup"
        log_root = home / ".local" / "state" / "exactus" / "mcp-wakeup"
        definition_path = (
            home / ".config" / "systemd" / "user" / f"{label}.service"
        )
    elif platform_name == "win32":
        config_root = home / "AppData" / "Roaming" / "Exactus" / "mcp-wakeup"
        log_root = home / "AppData" / "Local" / "Exactus" / "Logs"
        definition_path = config_root / f"{label}.py"
    else:
        msg: str = f"unsupported startup platform: {platform_name}"
        raise RuntimeError(msg)
    return StartupWatcherManager(
        label=label,
        definition_path=definition_path,
        secrets_path=config_root / f"{label}.secrets.json",
        stdout_path=log_root / f"{label}.stdout.log",
        stderr_path=log_root / f"{label}.stderr.log",
        platform_name=platform_name,
        user_identifier=home.stat().st_uid if platform_name == "darwin" else 0,
    )
