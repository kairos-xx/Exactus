# Copyright (c) 2026
"""User-level completion install, uninstall and diagnosis.

Registration uses a dedicated provider file where the shell loads
one automatically (Fish) or a clearly delimited managed block inside
the user profile where it does not (``~/.bashrc`` and ``~/.zshrc`` —
provider directories are not loaded without extra packages or
``fpath`` entries — and the PowerShell profile). Only exactus-owned
content is ever written or removed; unrelated user completion
content is left untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from re import Match, search
from shlex import quote
from shutil import which
from sys import platform
from typing import TYPE_CHECKING, Final, NamedTuple, final

from .model import CompletionShell
from .profiles import profile_paths
from .protocol import Constants as _GroupFinalConstants
from .shells import render

if TYPE_CHECKING:
    from pathlib import Path


def _block_begin(*, command_name: str) -> str:
    """Return the managed-block opening marker for one command.

    Args:
        command_name: Registered command name.

    Returns:
        The profile-block opening marker owned by the command.

    """
    return f"# >>> {command_name} completion >>>"


def _block_end(*, command_name: str) -> str:
    """Return the managed-block closing marker for one command.

    Args:
        command_name: Registered command name.

    Returns:
        The profile-block closing marker owned by the command.

    """
    return f"# <<< {command_name} completion <<<"


@final
class Constants:
    """Group module-level constants.

    Attributes:
        protocol_marker: Grouped module constant.

    """

    protocol_marker: Final[str] = "# Completion protocol:"


"Marker comment carrying the installed script's protocol version."


class ShellInstallKind(Enum):
    """How a shell consumes its registration script.

    Attributes:
        PROVIDER_FILE: A dedicated script discovered by the shell.
        PROFILE_BLOCK: A managed block in the user's profile.

    """

    PROVIDER_FILE = "provider-file"
    "A dedicated file the shell discovers automatically."
    PROFILE_BLOCK = "profile-block"
    "A managed block appended to the user's profile."


class InstallStatus(Enum):
    """Health of one shell's completion registration.

    Attributes:
        HEALTHY: Compatible installed registration.
        MISSING: Absent registration.
        STALE: Incompatible protocol version.
        BROKEN: Corrupted managed registration.
        LAUNCHER_MISSING: Unresolvable completion launcher.

    """

    HEALTHY = "healthy"
    "Installed with a compatible protocol version."
    MISSING = "missing"
    "Never installed, or cleanly absent."
    STALE = "stale"
    "Installed with an incompatible protocol version."
    BROKEN = "broken"
    "exactus-owned content exists but is corrupted."
    LAUNCHER_MISSING = "launcher-missing"
    "Installed, but the completion launcher cannot resolve."


@dataclass(frozen=True, slots=True)
class ShellDiagnosis:
    """Diagnostic result for one shell.

    Attributes:
        shell: The inspected shell.
        status: Registration health.
        path: Provider file or profile inspected.
        detail: Human-readable explanation.

    """

    shell: CompletionShell
    status: InstallStatus
    path: Path
    detail: str


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Outcome of an install or uninstall operation.

    Attributes:
        shell: The affected shell.
        status: Resulting registration health.
        path: Provider file or profile touched.
        changed: Whether filesystem content changed.
        detail: Human-readable explanation.

    """

    shell: CompletionShell
    status: InstallStatus
    path: Path
    changed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class Registration:
    """Describe a startup registration destination and bundle revision.

    Attributes:
        path: User profile or provider destination.
        revision: Fingerprint identifying the current bundle.
        aliases: Additional invocation names to register.

    """

    path: Path
    revision: str
    aliases: tuple[str, ...] = ()


class _Layout(NamedTuple):
    """Install location for one shell.

    Attributes:
        kind: Registration strategy.
        path: Provider script or profile destination.

    """

    kind: ShellInstallKind
    path: Path


def _powershell_profile(*, home: Path) -> Path:
    """Return the conventional user PowerShell profile path.

    Args:
        home: User home directory.

    Returns:
        The pwsh profile location for the host platform.

    """
    if platform == "win32":
        return (
            home
            / "Documents"
            / "PowerShell"
            / "Microsoft.PowerShell_profile.ps1"
        )
    return home / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"


def _layout(
    *,
    shell: CompletionShell,
    home: Path,
    command_name: str,
) -> _Layout:
    """Return the registration location for a shell.

    Args:
        shell: Target shell.
        home: User home directory.
        command_name: Registered command name.

    Returns:
        Kind and filesystem path of the registration.

    """
    if shell == CompletionShell.BASH:
        return _Layout(
            kind=ShellInstallKind.PROFILE_BLOCK,
            path=home / ".bashrc",
        )
    if shell == CompletionShell.ZSH:
        return _Layout(
            kind=ShellInstallKind.PROFILE_BLOCK,
            path=home / ".zshrc",
        )
    if shell == CompletionShell.FISH:
        return _Layout(
            kind=ShellInstallKind.PROVIDER_FILE,
            path=home
            / ".config"
            / "fish"
            / "completions"
            / f"{command_name}.fish",
        )
    return _Layout(
        kind=ShellInstallKind.PROFILE_BLOCK,
        path=_powershell_profile(home=home),
    )


def _extract_block(*, text: str, command_name: str) -> str | None:
    """Extract the managed block from profile text.

    Args:
        text: Profile file content.
        command_name: Registered command name.

    Returns:
        The block including its markers, or ``None`` when absent.

    """
    begin_marker: str = _block_begin(command_name=command_name)
    end_marker: str = _block_end(command_name=command_name)
    begin: int = text.find(begin_marker)
    end: int = text.find(end_marker)
    if begin == -1 or end == -1 or end < begin:
        return None
    return text[begin : end + len(end_marker)]


def _script_protocol(*, text: str) -> int | None:
    """Read the protocol version marker from installed content.

    Args:
        text: Installed script or block content.

    Returns:
        The declared protocol version, or ``None`` when unmarked.

    """
    marker: Match[str] | None = search(
        pattern=f"{Constants.protocol_marker} (\\d+)",
        string=text,
    )
    return int(marker[1]) if marker is not None else None


def _installed_content(*, layout: _Layout, command_name: str) -> str | None:
    """Return installed command-owned content for a layout.

    Args:
        layout: Registration location.
        command_name: Registered command name.

    Returns:
        Provider-file content or profile block text, or ``None``.

    """
    if not layout.path.is_file():
        return None
    try:
        text: str = layout.path.read_text(encoding="utf-8")
    except OSError:
        return None
    if layout.kind == ShellInstallKind.PROVIDER_FILE:
        return text if Constants.protocol_marker in text else None
    return _extract_block(text=text, command_name=command_name)


def _classify(
    *,
    shell: CompletionShell,
    layout: _Layout,
    launcher: tuple[str, ...],
    command_name: str,
) -> ShellDiagnosis:
    """Diagnose one shell's registration state.

    Args:
        shell: Target shell.
        layout: Registration location.
        launcher: Executable and fixed arguments.
        command_name: Registered command name.

    Returns:
        The shell's diagnostic result.

    """
    content: str | None = _installed_content(
        layout=layout,
        command_name=command_name,
    )
    if content is None:
        if layout.path.is_file() and (
            layout.kind == ShellInstallKind.PROVIDER_FILE
            or _block_begin(command_name=command_name)
            in layout.path.read_text(encoding="utf-8")
        ):
            return ShellDiagnosis(
                shell=shell,
                status=InstallStatus.BROKEN,
                path=layout.path,
                detail="exactus-owned completion content is corrupted",
            )
        return ShellDiagnosis(
            shell=shell,
            status=InstallStatus.MISSING,
            path=layout.path,
            detail="not installed",
        )
    installed: int | None = _script_protocol(text=content)
    if installed is None:
        return ShellDiagnosis(
            shell=shell,
            status=InstallStatus.BROKEN,
            path=layout.path,
            detail="completion content lacks a protocol marker",
        )
    if installed != _GroupFinalConstants.protocol_version:
        return ShellDiagnosis(
            shell=shell,
            status=InstallStatus.STALE,
            path=layout.path,
            detail=(
                f"protocol {installed} installed; "
                f"{_GroupFinalConstants.protocol_version} required — reinstall"
            ),
        )
    if which(cmd=launcher[0]) is None:
        return ShellDiagnosis(
            shell=shell,
            status=InstallStatus.LAUNCHER_MISSING,
            path=layout.path,
            detail=f"launcher not on PATH: {launcher[0]!r}",
        )
    return ShellDiagnosis(
        shell=shell,
        status=InstallStatus.HEALTHY,
        path=layout.path,
        detail="installed",
    )


def _registration_script(
    *,
    shell: CompletionShell,
    command_name: str,
    launcher: tuple[str, ...],
    registration: Registration | None,
) -> str:
    """Render registered invocation names and their revision marker.

    Args:
        shell: Target shell.
        command_name: Primary command name.
        launcher: Completion endpoint invocation.
        registration: Optional startup metadata.

    Returns:
        Deterministic completion script.

    """
    script: str = render(
        shell=shell,
        command_name=command_name,
        launcher=launcher,
    )
    if registration is not None:
        for alias in registration.aliases:
            if alias != command_name:
                script += render(
                    shell=shell,
                    command_name=alias,
                    launcher=launcher,
                )
        if registration.revision:
            script += f"# Completion bundle: {registration.revision}\n"
    return script


def install(
    *,
    shell: CompletionShell,
    command_name: str,
    launcher: tuple[str, ...],
    home: Path,
    registration: Registration | None = None,
) -> InstallResult:
    """Install or refresh one shell's registration.

    Args:
        shell: Target shell.
        command_name: Registered command name.
        launcher: Executable and fixed arguments.
        home: User home directory.
        registration: Startup destination and bundle fingerprint.

    Returns:
        The installation result.

    """
    layout: _Layout = _layout(
        shell=shell,
        home=home,
        command_name=command_name,
    )
    if registration is not None:
        layout = _Layout(kind=layout.kind, path=registration.path)
    script: str = _registration_script(
        shell=shell,
        command_name=command_name,
        launcher=launcher,
        registration=registration,
    )
    if layout.kind == ShellInstallKind.PROVIDER_FILE:
        existing: str = ""
        if layout.path.is_file():
            existing = layout.path.read_text(encoding="utf-8")
            if Constants.protocol_marker not in existing:
                return InstallResult(
                    shell=shell,
                    status=InstallStatus.BROKEN,
                    path=layout.path,
                    changed=False,
                    detail=(
                        "refusing to overwrite a file that is not "
                        "exactus-managed"
                    ),
                )
        layout.path.parent.mkdir(parents=True, exist_ok=True)
        changed: bool = not layout.path.is_file() or existing != script
        if changed:
            _ = layout.path.write_text(data=script, encoding="utf-8")
        return InstallResult(
            shell=shell,
            status=InstallStatus.HEALTHY,
            path=layout.path,
            changed=changed,
            detail=f"installed {layout.path}",
        )
    prelude: str = (
        "autoload -Uz compinit && compinit\n"
        if shell == CompletionShell.ZSH
        else ""
    )
    if shell == CompletionShell.BASH:
        script = (
            f'if [ -n "${{BASH_VERSION:-}}" ]; then\neval '
            f"{quote(s=script)}\nfi\n"
        )
    block_start: str = _block_begin(command_name=command_name)
    block_end: str = _block_end(command_name=command_name)
    block: str = f"{block_start}\n{prelude}{script}{block_end}\n"
    encoding: str = (
        "utf-8-sig" if shell == CompletionShell.POWERSHELL else "utf-8"
    )
    prior: str = (
        layout.path.read_text(encoding=encoding)
        if layout.path.is_file()
        else ""
    )
    managed: str | None = _extract_block(text=prior, command_name=command_name)
    if managed is None and (
        _block_begin(command_name=command_name) in prior
        or _block_end(command_name=command_name) in prior
    ):
        return InstallResult(
            shell=shell,
            status=InstallStatus.BROKEN,
            path=layout.path,
            changed=False,
            detail="refusing to replace an incomplete managed block",
        )
    updated: str = (
        prior.replace(managed, block.rstrip("\n"))
        if managed is not None
        else prior
        + (("\n" if prior and (not prior.endswith("\n")) else "") + block)
    )
    layout.path.parent.mkdir(parents=True, exist_ok=True)
    changed = prior != updated
    if changed:
        _ = layout.path.write_text(data=updated, encoding=encoding)
    return InstallResult(
        shell=shell,
        status=InstallStatus.HEALTHY,
        path=layout.path,
        changed=changed,
        detail=f"updated managed block in {layout.path}",
    )


def uninstall(
    *,
    shell: CompletionShell,
    home: Path,
    command_name: str,
    profile: Path | None = None,
) -> InstallResult:
    """Remove one shell's command-owned registration.

    Args:
        shell: Target shell.
        home: User home directory.
        command_name: Registered command name.
        profile: Explicit registration path to remove.

    Returns:
        The removal result.

    """
    layout: _Layout = _layout(
        shell=shell,
        home=home,
        command_name=command_name,
    )
    if profile is not None:
        layout = _Layout(kind=layout.kind, path=profile)
    if layout.kind == ShellInstallKind.PROVIDER_FILE:
        if not layout.path.is_file():
            return InstallResult(
                shell=shell,
                status=InstallStatus.MISSING,
                path=layout.path,
                changed=False,
                detail="not installed",
            )
        existing: str = layout.path.read_text(encoding="utf-8")
        if Constants.protocol_marker not in existing:
            return InstallResult(
                shell=shell,
                status=InstallStatus.BROKEN,
                path=layout.path,
                changed=False,
                detail="refusing to delete a file that is not exactus-managed",
            )
        layout.path.unlink()
        return InstallResult(
            shell=shell,
            status=InstallStatus.MISSING,
            path=layout.path,
            changed=True,
            detail=f"removed {layout.path}",
        )
    if not layout.path.is_file():
        return InstallResult(
            shell=shell,
            status=InstallStatus.MISSING,
            path=layout.path,
            changed=False,
            detail="not installed",
        )
    prior: str = layout.path.read_text(encoding="utf-8")
    managed: str | None = _extract_block(text=prior, command_name=command_name)
    if managed is None:
        return InstallResult(
            shell=shell,
            status=InstallStatus.MISSING,
            path=layout.path,
            changed=False,
            detail="no managed block present",
        )
    updated: str = prior.replace(managed, "").replace("\n\n\n", "\n\n")
    layout.path.write_text(data=updated, encoding="utf-8")
    return InstallResult(
        shell=shell,
        status=InstallStatus.MISSING,
        path=layout.path,
        changed=True,
        detail=f"removed managed block from {layout.path}",
    )


def diagnose(
    *,
    launcher: tuple[str, ...],
    home: Path,
    command_name: str,
) -> tuple[ShellDiagnosis, ...]:
    """Diagnose registration health for every supported shell.

    Args:
        launcher: Executable and fixed arguments.
        home: User home directory.
        command_name: Registered command name.

    Returns:
        One diagnosis per supported shell.

    """
    locations: tuple[tuple[CompletionShell, Path], ...] = tuple(
        dict.fromkeys(
            [
                (
                    shell,
                    _layout(
                        shell=shell,
                        home=home,
                        command_name=command_name,
                    ).path,
                )
                for shell in CompletionShell
            ]
            + list(profile_paths(home=home, command_name=command_name)),
        ),
    )
    return tuple(
        (
            _classify(
                shell=shell,
                layout=_Layout(
                    kind=_layout(
                        shell=shell,
                        home=home,
                        command_name=command_name,
                    ).kind,
                    path=profile,
                ),
                launcher=launcher,
                command_name=command_name,
            )
            for shell, profile in locations
        ),
    )
