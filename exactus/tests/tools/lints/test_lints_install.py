# Copyright (c) 2026
"""Installer paths of the lints core, exercised with fake subprocesses."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, Final

import pytest

from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_true,
    private_call,
)
from exactus.tools.lints import core

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
LintExactus: Final[type[core.LintExactus]] = core.LintExactus


class FakeSystem:
    """Record commands and report configurable availability."""

    def __init__(self, *, present: set[str], returncode: int = 0) -> None:
        """Store which executables exist and the install exit status.

        Args:
            present: Executable names ``which`` should resolve.
            returncode: Exit status of every fake command.

        """
        self.present: set[str] = present
        self.returncode: int = returncode
        self.commands: list[tuple[str, ...]] = []

    def which(self, *, cmd: str) -> str | None:
        """Return a fake path for known executables.

        Args:
            cmd: Executable name.

        Returns:
            A path string, or ``None`` when absent.

        """
        return f"/fake/{cmd}" if cmd in self.present else None

    def run(
        self,
        *,
        args: Sequence[str],
        **_: object,
    ) -> CompletedProcess[str]:
        """Record one command and return a canned result.

        Args:
            args: Command line.
            **_: Ignored subprocess options.

        Returns:
            Completed process with the configured status.

        """
        self.commands.append(tuple(str(object=arg) for arg in args))
        return CompletedProcess(
            args=args,
            returncode=self.returncode,
            stdout="out",
            stderr="err",
        )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeSystem,
    host: str,
    action: Callable[[], object],
) -> None:
    """Patch the core module and invoke ``action``.

    Args:
        monkeypatch: Pytest patching helper.
        fake: Fake system state.
        host: Value returned by ``platform.system``.
        action: Callable under test; its return value is ignored.

    """
    monkeypatch.setattr(target=core, name="which", value=fake.which)
    monkeypatch.setattr(target=core, name="run", value=fake.run)
    monkeypatch.setattr(target=core, name="system", value=Constant(value=host))
    action()


def test_install_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing installer command raises with its output.

    Args:
        monkeypatch: Pytest patching helper.

    """
    fake: FakeSystem = FakeSystem(present=set(), returncode=3)
    monkeypatch.setattr(target=core, name="run", value=fake.run)
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Installation failed",
    ):
        private_call(
            owner=LintExactus,
            name="_install",
            command=("x", "y"),
            cwd=Path.cwd(),
        )


def test_ensure_node_noop_when_npm_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is installed when npm already exists.

    Args:
        monkeypatch: Pytest patching helper.

    """
    fake: FakeSystem = FakeSystem(present={"npm"})
    _install(
        monkeypatch=monkeypatch,
        fake=fake,
        host="Darwin",
        action=lambda: private_call(
            owner=LintExactus,
            name="_ensure_node",
            cwd=Path.cwd(),
            writer=StringIO(),
        ),
    )
    expect_false(condition=bool(fake.commands))


def test_ensure_node_unsupported_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown operating systems are rejected.

    Args:
        monkeypatch: Pytest patching helper.

    """
    fake: FakeSystem = FakeSystem(present=set())
    with pytest.raises(expected_exception=RuntimeError, match="Unsupported"):
        _install(
            monkeypatch=monkeypatch,
            fake=fake,
            host="Plan9",
            action=lambda: private_call(
                owner=LintExactus,
                name="_ensure_node",
                cwd=Path.cwd(),
                writer=StringIO(),
            ),
        )


@pytest.mark.parametrize(
    ("host", "tools", "needle"),
    [
        ("Darwin", {"brew"}, "brew"),
        ("Windows", {"winget"}, "winget"),
        ("Windows", {"choco"}, "choco"),
        ("Linux", {"apt-get"}, "apt-get"),
        ("Linux", {"dnf"}, "dnf"),
        ("Linux", {"pacman"}, "pacman"),
        ("Linux", {"zypper"}, "zypper"),
    ],
)
def test_node_installers_run_expected_commands(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    tools: set[str],
    needle: str,
) -> None:
    """Each platform installer issues its package-manager command.

    npm never appears, so the final visibility check fails afterwards.

    Args:
        monkeypatch: Pytest patching helper.
        host: Value for ``host``.
        tools: Value for ``tools``.
        needle: Value for ``needle``.

    """
    fake: FakeSystem = FakeSystem(present=tools)
    with pytest.raises(
        expected_exception=RuntimeError,
        match="npm is not visible",
    ):
        _install(
            monkeypatch=monkeypatch,
            fake=fake,
            host=host,
            action=lambda: private_call(
                owner=LintExactus,
                name="_ensure_node",
                cwd=Path.cwd(),
                writer=StringIO(),
            ),
        )
    expect_true(condition=any(needle in command for command in fake.commands))


@pytest.mark.parametrize("host", ["Darwin", "Windows", "Linux"])
def test_node_installer_without_manager(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
) -> None:
    """A missing package manager gives an actionable error.

    Args:
        monkeypatch: Pytest patching helper.
        host: Value for ``host``.

    """
    fake: FakeSystem = FakeSystem(present=set())
    with pytest.raises(
        expected_exception=RuntimeError,
        match=r"Node\.js is missing",
    ):
        _install(
            monkeypatch=monkeypatch,
            fake=fake,
            host=host,
            action=lambda: private_call(
                owner=LintExactus,
                name="_ensure_node",
                cwd=Path.cwd(),
                writer=StringIO(),
            ),
        )


def test_ensure_tools_installs_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Python and Node tools are installed through pip and npm.

    Args:
        monkeypatch: Pytest patching helper.

    """
    fake: FakeSystem = FakeSystem(present={"npm"}, returncode=0)
    monkeypatch.setattr(
        target=core,
        name="resolve_exactus_tool_bundle",
        value=Constant(value=None),
    )
    required: frozenset[str] = frozenset(
        {
            *(command for command, _ in core.Constants.python_packages),
            *(command for command, _ in core.Constants.node_packages),
            "eslint",
        },
    )
    fake_rc: FakeSystem = FakeSystem(present={"npm"})
    _install(
        monkeypatch=monkeypatch,
        fake=fake_rc,
        host="Darwin",
        action=lambda: private_call(
            owner=LintExactus,
            name="_ensure_tools",
            cwd=Path.cwd(),
            writer=StringIO(),
            required=required,
        ),
    )
    flat: list[str] = [" ".join(command) for command in fake_rc.commands]
    expect_true(condition=any("pip install" in line for line in flat))
    expect_true(condition=any("npm install -g" in line for line in flat))
    expect_false(condition=bool(fake.commands))


def test_ensure_tools_skips_when_bundle_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An offline bundle short-circuits all installation.

    Args:
        monkeypatch: Pytest patching helper.

    """
    fake: FakeSystem = FakeSystem(present=set())
    monkeypatch.setattr(
        target=core,
        name="resolve_exactus_tool_bundle",
        value=Constant(value=Path.cwd()),
    )
    _install(
        monkeypatch=monkeypatch,
        fake=fake,
        host="Linux",
        action=lambda: private_call(
            owner=LintExactus,
            name="_ensure_tools",
            cwd=Path.cwd(),
            writer=StringIO(),
            required=frozenset({"ruff"}),
        ),
    )
    expect_false(condition=bool(fake.commands))


def test_sudo_prefix_and_refresh_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Privilege prefix follows euid and PATH gains Node locations.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=core, name="geteuid", value=Constant(value=0))
    expect_equal(
        actual=private_call(owner=LintExactus, name="_sudo_prefix"),
        expected=(),
    )
    monkeypatch.setattr(
        target=core,
        name="geteuid",
        value=Constant(value=1000),
    )
    expect_equal(
        actual=private_call(owner=LintExactus, name="_sudo_prefix"),
        expected=("sudo",),
    )
    monkeypatch.setenv(name="PATH", value="/bin")
    private_call(owner=LintExactus, name="_refresh_path")
    expect_true(condition=core.environ["PATH"].endswith("/bin"))
