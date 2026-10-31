# Copyright (c) 2026
"""Discover current-user completion profiles across supported shells."""

from __future__ import annotations

from json import loads
from os import environ
from pathlib import Path
from shutil import which
from subprocess import CompletedProcess, TimeoutExpired, run
from sys import platform
from typing import TYPE_CHECKING

from .model import CompletionShell

if TYPE_CHECKING:
    from .json_types import JsonValue


def profile_paths(
    *,
    home: Path,
    command_name: str,
) -> tuple[tuple[CompletionShell, Path], ...]:
    """Find supported user profiles without changing login-file precedence.

    Args:
        home: User home directory.
        command_name: Registered command name.

    Returns:
        Shell and registration path pairs.

    """
    login: Path = next(
        (
            home / name
            for name in (".bash_profile", ".bash_login", ".profile")
            if (home / name).is_file()
        ),
        home / ".bash_profile",
    )
    config: Path = Path(environ.get("XDG_CONFIG_HOME") or home / ".config")
    zsh: Path = Path(environ.get("ZDOTDIR") or home)
    paths: list[tuple[CompletionShell, Path]] = [
        (CompletionShell.BASH, home / ".bashrc"),
        (CompletionShell.BASH, login),
        (CompletionShell.ZSH, zsh / ".zshrc"),
        (
            CompletionShell.FISH,
            config / "fish" / "completions" / f"{command_name}.fish",
        ),
    ]
    # Ask each installed PowerShell for its actual Documents/config location.
    for command in ("pwsh", "powershell"):
        if home.resolve() != Path.home().resolve():
            break
        executable: str | None = which(cmd=command)
        if executable is None:
            continue
        try:
            result: CompletedProcess[str] = run(
                args=[
                    executable,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "$PROFILE.CurrentUserAllHosts | ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            profile: JsonValue = loads(
                s=result.stdout.strip().lstrip("\ufeff"),
            )
            if result.returncode == 0 and isinstance(profile, str) and profile:
                paths.append((CompletionShell.POWERSHELL, Path(profile)))
        except (OSError, ValueError, TimeoutExpired):
            continue
    if not any(shell == CompletionShell.POWERSHELL for shell, _ in paths):
        directories: tuple[Path, Path] | tuple[Path] = (
            (
                home / "Documents" / "PowerShell",
                home / "Documents" / "WindowsPowerShell",
            )
            if platform == "win32"
            else (config / "powershell",)
        )
        paths.extend(
            (CompletionShell.POWERSHELL, directory / "profile.ps1")
            for directory in directories
        )
    return tuple(dict.fromkeys(paths))
