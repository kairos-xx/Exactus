# Copyright (c) 2026
"""Verify automatic completion without touching real user profiles."""

from __future__ import annotations

from io import StringIO
from json import dumps
from subprocess import CompletedProcess
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.completion import profiles
from exactus.packages.completion.install import _block_begin
from exactus.packages.completion.model import CompletionShell
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tools.completion import startup
from exactus.tools.completion.main import run as completion_run


@final
class Constants:
    """Group module-level constants.

    Attributes:
        block_begin: Grouped module constant.

    """

    block_begin: Final[str] = _block_begin(command_name="exactus")


if TYPE_CHECKING:
    from pathlib import Path


def _isolate(*, home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set an isolated home and a portable launcher.

    Args:
        home: Temporary home.
        monkeypatch: Patch fixture.

    Returns:
        Fake portable launcher path.

    """
    monkeypatch.setenv(name="ZDOTDIR", value=str(object=home / "zsh"))
    monkeypatch.setenv(
        name="XDG_CONFIG_HOME",
        value=str(object=home / "config"),
    )

    def no_shell(*, cmd: str) -> None:
        """Report that the isolated environment has no PowerShell.

        Args:
            cmd: Ignored executable name.

        """
        _ = cmd

    monkeypatch.setattr(target=profiles, name="which", value=no_shell)
    bundle: Path = home / "check"
    bundle.write_bytes(data=b"#!/usr/bin/env python3\nPKfake-bundle")
    monkeypatch.setattr(
        target=startup,
        name="argv",
        value=[str(object=bundle)],
    )

    def launcher(*, command_name: str) -> tuple[str, ...]:
        """Return the fake bundle's launcher invocation.

        Args:
            command_name: Ignored tool identifier.

        Returns:
            Portable launcher invocation.

        """
        _ = command_name
        return ("python", str(object=bundle))

    monkeypatch.setattr(
        target=startup,
        name="resolve_launcher",
        value=launcher,
    )
    return bundle


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_first_run_refresh_and_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    """Install all supported profiles and refresh only changed content.

    Args:
        tmp_path: Isolated home.
        monkeypatch: Patch fixture.
        platform: Simulated OS.

    """
    bundle: Path = _isolate(home=tmp_path, monkeypatch=monkeypatch)
    monkeypatch.setattr(target=profiles, name="platform", value=platform)
    login: Path = tmp_path / ".profile"
    login.write_text(data="# preserve my login config\n")
    startup.ensure_completion(home=tmp_path)
    paths: list[Path] = [
        path
        for _, path in startup.profile_paths(
            home=tmp_path,
            command_name="exactus",
        )
    ]
    first: dict[Path, tuple[bytes, int]] = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    }
    startup.ensure_completion(home=tmp_path)
    expect_equal(
        actual={
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in paths
        },
        expected=first,
    )
    expect_false(condition=(tmp_path / ".bash_profile").exists())
    expect_in(member="# preserve my login config", container=login.read_text())
    bundle.write_bytes(data=bundle.read_bytes() + b"catalog changed")
    startup.ensure_completion(home=tmp_path)
    for path in paths:
        expect_true(condition=path.read_bytes() != first[path][0])
        if path.name != "exactus.fish":
            expect_equal(
                actual=path.read_text().count(Constants.block_begin),
                expected=1,
            )


def test_foreign_and_broken_profiles_survive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve foreign files and continue after an unwritable target.

    Args:
        tmp_path: Isolated home.
        monkeypatch: Patch fixture.

    """
    _ = _isolate(home=tmp_path, monkeypatch=monkeypatch)
    paths: dict[CompletionShell, Path] = dict(
        startup.profile_paths(home=tmp_path, command_name="exactus"),
    )
    fish: Path = paths[CompletionShell.FISH]
    fish.parent.mkdir(parents=True)
    fish.write_text(data="# my own completer\n")
    zsh: Path = paths[CompletionShell.ZSH]
    zsh.parent.mkdir(parents=True)
    zsh.write_text(data=f"{Constants.block_begin}\n# incomplete\n")
    (tmp_path / ".bashrc").mkdir()
    startup.ensure_completion(home=tmp_path)
    expect_equal(actual=fish.read_text(), expected="# my own completer\n")
    expect_equal(
        actual=zsh.read_text(),
        expected=f"{Constants.block_begin}\n# incomplete\n",
    )
    expect_true(condition=paths[CompletionShell.POWERSHELL].is_file())


def test_source_invocation_does_not_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave developer invocations free of profile mutations.

    Args:
        tmp_path: Isolated home.
        monkeypatch: Patch fixture.

    """
    monkeypatch.setattr(
        target=startup,
        name="argv",
        value=[str(object=tmp_path / "source.py")],
    )
    startup.ensure_completion(home=tmp_path)
    expect_equal(actual=list(tmp_path.iterdir()), expected=[])


def test_management_removes_automatic_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove automatic registrations through the management command.

    Args:
        tmp_path: Isolated home.
        monkeypatch: Patch fixture.

    """
    _ = _isolate(home=tmp_path, monkeypatch=monkeypatch)
    startup.ensure_completion(home=tmp_path)
    locations: tuple[tuple[CompletionShell, Path], ...] = (
        profiles.profile_paths(home=tmp_path, command_name="exactus")
    )
    status: int = completion_run(
        arguments=("all", "--uninstall"),
        home=tmp_path,
        out=StringIO(),
    )
    expect_equal(actual=status, expected=0)
    for _, path in locations:
        expect_false(
            condition=path.is_file()
            and Constants.block_begin in path.read_text(),
        )
    expect_false(condition=dict(locations)[CompletionShell.FISH].exists())


def test_powershell_discovers_redirected_all_host_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Query both installed editions for their redirected profile paths.

    Args:
        tmp_path: Redirected Documents fixture.
        monkeypatch: Patch fixture.

    """

    def executable(*, cmd: str) -> str:
        """Return a fake installed edition.

        Args:
            cmd: Executable name.

        Returns:
            Executable name.

        """
        return cmd

    def query(*, args: list[str], **options: object) -> CompletedProcess[str]:
        """Return the edition's redirected profile.

        Args:
            args: Command arguments.
            options: Subprocess invocation.

        Returns:
            JSON-encoded profile path.

        """
        _ = options
        return CompletedProcess(
            args=args,
            returncode=0,
            stdout=dumps(obj=str(object=tmp_path / args[0] / "profile.ps1")),
        )

    monkeypatch.setattr(target=profiles, name="which", value=executable)
    monkeypatch.setattr(target=profiles, name="run", value=query)
    locations: tuple[tuple[CompletionShell, Path], ...] = (
        profiles.profile_paths(
            home=profiles.Path.home(),
            command_name="exactus",
        )
    )
    actual: list[Path] = [
        path
        for shell, path in locations
        if shell == CompletionShell.POWERSHELL
    ]
    expect_equal(
        actual=actual,
        expected=[
            tmp_path / name / "profile.ps1" for name in ("pwsh", "powershell")
        ],
    )
