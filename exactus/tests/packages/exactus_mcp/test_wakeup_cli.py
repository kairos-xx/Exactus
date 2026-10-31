# Copyright (c) 2026
"""Validate the wake watcher command-line lifecycle actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, final

import pytest

from exactus.packages.exactus_mcp import wakeup_cli
from exactus.packages.exactus_mcp.startup import StartupStatus
from exactus.tests.common.support import expect_equal, expect_in, expect_not_in

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from exactus.packages.exactus_mcp.startup import WatcherSecrets


@final
@dataclass(slots=True)
class FakeManager:
    """Record native watcher lifecycle operations.

    Attributes:
        secrets_path: Private installed secrets-file path.
        running: Whether the fake watcher reports a running state.
        installs: Recorded installation calls.
        uninstalls: Number of uninstall requests.

    """

    secrets_path: Path
    running: bool = False
    installs: list[tuple[tuple[str, ...], WatcherSecrets]] = field(
        default_factory=list,
    )
    uninstalls: int = 0

    def install(
        self,
        *,
        program_arguments: tuple[str, ...],
        secrets: WatcherSecrets,
    ) -> StartupStatus:
        """Record an installation request.

        Args:
            program_arguments: Shell-free watcher command vector.
            secrets: Private watcher credentials.

        Returns:
            Installed-and-running status.

        """
        self.installs.append((program_arguments, secrets))
        return StartupStatus(
            backend="test",
            installed=True,
            loaded=True,
            running=True,
            process_identifier=42,
        )

    def uninstall(self) -> StartupStatus:
        """Record an uninstall request.

        Returns:
            Fully removed status.

        """
        self.uninstalls += 1
        return StartupStatus(
            backend="test",
            installed=False,
            loaded=False,
            running=False,
            process_identifier=None,
        )

    def status(self) -> StartupStatus:
        """Return the configured running state.

        Returns:
            Status reflecting ``running``.

        """
        return StartupStatus(
            backend="test",
            installed=True,
            loaded=True,
            running=self.running,
            process_identifier=42 if self.running else None,
        )


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate environment defaults and project configuration.

    Args:
        monkeypatch: Environment and working-directory replacement.
        tmp_path: Empty working directory without ``pyproject.toml``.

    """
    for variable in (
        "EXACTUS_MCP_ACCESS_TOKEN",
        "EXACTUS_MCP_MANTLEDB_NAMESPACE",
        "EXACTUS_MCP_MANTLEDB_PATH",
        "EXACTUS_MCP_WAKE_KEY",
    ):
        monkeypatch.delenv(name=variable, raising=False)
    monkeypatch.chdir(path=tmp_path)


def _fake_manager(
    *,
    monkeypatch: pytest.MonkeyPatch,
    running: bool = False,
) -> FakeManager:
    """Install a recording manager at the lifecycle boundary.

    Args:
        monkeypatch: Module boundary replacement.
        running: Running state reported by ``status``.

    Returns:
        Recording fake manager.

    """
    manager: FakeManager = FakeManager(
        secrets_path=Path("/state/test.secrets.json"),
        running=running,
    )

    def build(*, label: str) -> FakeManager:
        """Return the recording manager for any label.

        Args:
            label: Native service label ignored by the fake.

        Returns:
            Recording fake manager.

        """
        del label
        return manager

    monkeypatch.setattr(target=wakeup_cli, name="_manager", value=build)
    return manager


def _streams(*, monkeypatch: pytest.MonkeyPatch) -> tuple[StringIO, StringIO]:
    """Replace the module's output streams with in-memory buffers.

    Args:
        monkeypatch: Stream boundary replacement.

    Returns:
        Captured standard output and error buffers.

    """
    output: StringIO = StringIO()
    error: StringIO = StringIO()
    monkeypatch.setattr(target=wakeup_cli, name="stdout", value=output)
    monkeypatch.setattr(target=wakeup_cli, name="stderr", value=error)
    return (output, error)


def _fake_run(*, main: Coroutine[object, object, int]) -> int:
    """Close the watcher coroutine and report a clean shutdown.

    Args:
        main: Async watcher coroutine.

    Returns:
        Zero for graceful watcher shutdown.

    """
    main.close()
    return 0


def test_main_status_reports_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """The status action prints lifecycle state and reflects running.

    Args:
        monkeypatch: Module boundary replacement.

    """
    output, _ = _streams(monkeypatch=monkeypatch)
    _fake_manager(monkeypatch=monkeypatch, running=True)
    expect_equal(actual=wakeup_cli.main(arguments=("status",)), expected=0)
    text: str = output.getvalue()
    expect_in(member="Backend: test", container=text)
    expect_in(member="Running: yes", container=text)
    expect_in(member="PID: 42", container=text)


def test_main_status_stopped_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stopped watcher reports nonzero and hides the PID.

    Args:
        monkeypatch: Module boundary replacement.

    """
    output, _ = _streams(monkeypatch=monkeypatch)
    _fake_manager(monkeypatch=monkeypatch, running=False)
    expect_equal(actual=wakeup_cli.main(arguments=("status",)), expected=1)
    text: str = output.getvalue()
    expect_in(member="Running: no", container=text)
    expect_in(member="PID: none", container=text)


def test_main_uninstall_removes_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uninstall action removes the native service definition.

    Args:
        monkeypatch: Module boundary replacement.

    """
    manager: FakeManager = _fake_manager(monkeypatch=monkeypatch)
    expect_equal(actual=wakeup_cli.main(arguments=("uninstall",)), expected=0)
    expect_equal(actual=manager.uninstalls, expected=1)


def test_main_install_persists_secret_free_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install persists a watcher command without inline secrets.

    Args:
        monkeypatch: Module boundary replacement.

    """
    manager: FakeManager = _fake_manager(monkeypatch=monkeypatch)
    result: int = wakeup_cli.main(
        arguments=(
            "install",
            "--keep-service-running",
            "--mantledb-namespace",
            "ns",
            "--wake-key",
            "wake-secret",
            "--access-token",
            "bearer-secret",
            "--",
            "python",
            "-m",
            "service",
        ),
    )
    expect_equal(actual=result, expected=0)
    expect_equal(actual=len(manager.installs), expected=1)
    program_arguments, secrets = manager.installs[0]
    expect_in(member="run", container=program_arguments)
    expect_in(member="ns", container=program_arguments)
    expect_in(member="service", container=program_arguments)
    expect_in(member="--keep-service-running", container=program_arguments)
    expect_not_in(member="wake-secret", container=program_arguments)
    expect_not_in(member="bearer-secret", container=program_arguments)
    expect_equal(actual=secrets.wake_key, expected="wake-secret")


def test_main_run_validates_and_starts_watcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The run action validates configuration before starting the watcher.

    Args:
        monkeypatch: Event-loop boundary replacement.

    """
    monkeypatch.setattr(target=wakeup_cli, name="run_async", value=_fake_run)
    expect_equal(
        actual=wakeup_cli.main(
            arguments=(
                "--mantledb-namespace",
                "ns",
                "--wake-key",
                "wake-secret",
                "--access-token",
                "bearer-secret",
                "--",
                "python",
                "-m",
                "service",
            ),
        ),
        expected=0,
    )


def test_main_run_loads_secrets_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A private secrets file supplies credentials without shell history.

    Args:
        monkeypatch: Event-loop boundary replacement.
        tmp_path: Isolated directory for the secrets file.

    """
    monkeypatch.setattr(target=wakeup_cli, name="run_async", value=_fake_run)
    secrets_path: Path = tmp_path / "secrets.json"
    _ = secrets_path.write_text(
        data=dumps(obj={"wake_key": "k", "access_token": "t"}),
        encoding="utf-8",
    )
    secrets_path.chmod(mode=0o600)
    expect_equal(
        actual=wakeup_cli.main(
            arguments=(
                "run",
                "--mantledb-namespace",
                "ns",
                "--secrets-file",
                str(object=secrets_path),
                "--",
                "svc",
            ),
        ),
        expected=0,
    )


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        (("run",), "MANTLEDB_NAMESPACE is required"),
        (
            ("run", "--mantledb-namespace", "ns", "--", "svc"),
            "WAKE_KEY and EXACTUS_MCP_ACCESS_TOKEN are required",
        ),
        (
            (
                "run",
                "--mantledb-namespace",
                "ns",
                "--wake-key",
                "k",
                "--access-token",
                "t",
            ),
            "fixed service command is required",
        ),
        (
            (
                "run",
                "--mantledb-namespace",
                "ns",
                "--wake-key",
                "k",
                "--access-token",
                "t",
                "--poll-interval",
                "0",
                "--",
                "svc",
            ),
            "must be positive",
        ),
        (
            (
                "run",
                "--mantledb-namespace",
                "ns",
                "--wake-key",
                "k",
                "--access-token",
                "t",
                "--poll-interval",
                "10",
                "--retry-maximum",
                "5",
                "--",
                "svc",
            ),
            "retry maximum cannot be smaller",
        ),
    ],
)
def test_main_reports_validation_failures(
    arguments: tuple[str, ...],
    match: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid lifecycle input is reported without a traceback.

    Args:
        arguments: Raw command-line vector.
        match: Required fragment of the reported error.
        monkeypatch: Stream boundary replacement.

    """
    _, error = _streams(monkeypatch=monkeypatch)
    expect_equal(actual=wakeup_cli.main(arguments=arguments), expected=1)
    text: str = error.getvalue()
    expect_in(member="exactus-mcp-wakeup: ", container=text)
    expect_in(member=match, container=text)


def test_main_lists_effective_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare --config prints effective settings with secrets redacted.

    Args:
        monkeypatch: Stream boundary replacement.

    """
    output, _ = _streams(monkeypatch=monkeypatch)
    expect_equal(actual=wakeup_cli.main(arguments=("--config",)), expected=0)
    text: str = output.getvalue()
    expect_in(member='"command-path": "wake/command"', container=text)
    expect_in(member='"wake-key": null', container=text)


def test_main_loads_json_config_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JSON config file seeds watcher defaults before CLI overrides.

    Args:
        tmp_path: Isolated directory for the JSON config.
        monkeypatch: Lifecycle manager boundary replacement.

    """
    config: Path = tmp_path / "wakeup.json"
    _ = config.write_text(
        data=dumps(
            obj={
                "mantledb-namespace": "from-json",
                "command-path": "custom/command",
            },
        ),
        encoding="utf-8",
    )
    manager: FakeManager = _fake_manager(monkeypatch=monkeypatch)
    result: int = wakeup_cli.main(
        arguments=(
            "install",
            "--wake-key",
            "k",
            "--access-token",
            "t",
            "--config",
            str(object=config),
            "--",
            "svc",
        ),
    )
    expect_equal(actual=result, expected=0)
    program_arguments, _secrets = manager.installs[0]
    expect_in(member="from-json", container=program_arguments)
    expect_in(member="custom/command", container=program_arguments)


def test_main_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interrupting the watcher exits cleanly with status zero.

    Args:
        monkeypatch: Event-loop boundary replacement.

    """

    def interrupted(*, main: Coroutine[object, object, int]) -> int:
        """Close the watcher coroutine and raise an interrupt.

        Args:
            main: Async watcher coroutine.

        Returns:
            Never returns; always interrupts.

        Raises:
            KeyboardInterrupt: Always, to simulate Ctrl+C.

        """
        main.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(target=wakeup_cli, name="run_async", value=interrupted)
    expect_equal(
        actual=wakeup_cli.main(
            arguments=(
                "run",
                "--mantledb-namespace",
                "ns",
                "--wake-key",
                "k",
                "--access-token",
                "t",
                "--",
                "svc",
            ),
        ),
        expected=0,
    )
