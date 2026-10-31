# Copyright (c) 2026
"""Validate native watcher lifecycle definitions without changing the host."""

from __future__ import annotations

from dataclasses import dataclass, field
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, final

import pytest

from exactus.packages.exactus_mcp.startup import (
    StartupStatus,
    StartupWatcherManager,
    WatcherSecrets,
    default_startup_manager,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path


@final
@dataclass(slots=True)
class FakeNativeRunner:
    """Emulate launchd, systemd, and Task Scheduler state transitions.

    Attributes:
        active: Whether the emulated native service is currently active.
        commands: Native command argument vectors captured by the runner.

    """

    active: bool = False
    commands: list[tuple[str, ...]] = field(default_factory=list)

    def __call__(self, *, arguments: tuple[str, ...]) -> CompletedProcess[str]:
        """Return deterministic state for one native lifecycle command.

        Args:
            arguments: Native command argument vector to emulate.

        Returns:
            Synthetic completed-process state for the command.

        """
        self.commands.append(arguments)
        output: str = ""
        if arguments[:2] == ("launchctl", "bootstrap"):
            self.active = True
        elif arguments[:2] == ("launchctl", "bootout"):
            self.active = False
        elif arguments[:2] == ("launchctl", "print"):
            output = "state = running\npid = 4321\n" if self.active else ""
            return self._result(
                arguments=arguments,
                returncode=0 if self.active else 1,
                stdout=output,
            )
        elif "enable" in arguments:
            self.active = True
        elif "disable" in arguments:
            self.active = False
        elif "show" in arguments:
            output = (
                "LoadState=loaded\nActiveState=active\nMainPID=4321\n"
                if self.active
                else "LoadState=not-found\nActiveState=inactive\nMainPID=0\n"
            )
        elif "/Create" in arguments or "/Run" in arguments:
            self.active = True
        elif "/Delete" in arguments or "/End" in arguments:
            self.active = False
        elif "/Query" in arguments:
            output = "Status: Running\n" if self.active else ""
            return self._result(
                arguments=arguments,
                returncode=0 if self.active else 1,
                stdout=output,
            )
        return self._result(arguments=arguments, returncode=0, stdout=output)

    @staticmethod
    def _result(
        *,
        arguments: tuple[str, ...],
        returncode: int,
        stdout: str,
    ) -> CompletedProcess[str]:
        """Build one completed-process result.

        Args:
            arguments: Command argument vector represented by the result.
            returncode: Synthetic process exit status.
            stdout: Synthetic standard output.

        Returns:
            Completed-process value with empty standard error.

        """
        return CompletedProcess(
            args=arguments,
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )


def _manager(
    *,
    tmp_path: Path,
    platform_name: str,
    runner: FakeNativeRunner,
) -> StartupWatcherManager:
    """Create an isolated manager for one target platform.

    Args:
        tmp_path: Temporary home directory for generated files.
        platform_name: Platform identifier to emulate.
        runner: Fake native command runner to inject.

    Returns:
        Startup manager isolated from the live host.

    """
    manager: StartupWatcherManager = default_startup_manager(
        label="com.exactus.test-wakeup",
        home=tmp_path,
        platform_name=platform_name,
    )
    manager.command_runner = runner
    manager.user_identifier = 501
    return manager


@pytest.mark.parametrize(
    argnames=("platform_name", "backend"),
    argvalues=[
        ("darwin", "launchd"),
        ("linux", "systemd-user"),
        ("win32", "task-scheduler"),
    ],
)
def test_native_install_status_and_uninstall(
    tmp_path: Path,
    platform_name: str,
    backend: str,
) -> None:
    """Every supported platform installs, reports, and removes the watcher.

    Args:
        tmp_path: Temporary home directory for generated files.
        platform_name: Platform identifier under test.
        backend: Expected native startup backend name.

    """
    runner: FakeNativeRunner = FakeNativeRunner()
    wake_key: str = "wake-test-key"
    access_token: str = f"mcp-{tmp_path.name}"
    manager: StartupWatcherManager = _manager(
        tmp_path=tmp_path,
        platform_name=platform_name,
        runner=runner,
    )
    installed: StartupStatus = manager.install(
        program_arguments=("python", "-m", "watcher", "run"),
        secrets=WatcherSecrets(wake_key=wake_key, access_token=access_token),
    )
    expect_equal(actual=installed.backend, expected=backend)
    expect_true(condition=installed.installed)
    expect_true(condition=installed.running)
    expect_true(condition=manager.secrets_path.is_file())
    expect_in(
        member=wake_key,
        container=manager.secrets_path.read_text(encoding="utf-8"),
    )
    definition: str = manager.definition_path.read_text(encoding="utf-8")
    expect_not_in(member=wake_key, container=definition)
    expect_not_in(member=access_token, container=definition)
    removed: StartupStatus = manager.uninstall()
    expect_equal(actual=removed.installed, expected=False)
    expect_equal(actual=removed.running, expected=False)
    expect_equal(actual=manager.secrets_path.exists(), expected=False)


def test_linux_definition_quotes_each_argument(tmp_path: Path) -> None:
    """Linux startup persists a direct argument vector rather than a shell.

    Args:
        tmp_path: Temporary home directory for generated files.

    """
    runner: FakeNativeRunner = FakeNativeRunner()
    manager: StartupWatcherManager = _manager(
        tmp_path=tmp_path,
        platform_name="linux",
        runner=runner,
    )
    _ = manager.install(
        program_arguments=(
            "/usr/bin/python3",
            "--value",
            "with spaces",
            "100%",
        ),
        secrets=WatcherSecrets(
            wake_key="wake-test-key",
            access_token=tmp_path.name,
        ),
    )
    definition: str = manager.definition_path.read_text(encoding="utf-8")
    expect_in(
        member=(
            'ExecStart="/usr/bin/python3" "--value" "with spaces" "100%%"'
        ),
        container=definition,
    )
