#!/usr/bin/env python3
# Copyright (c) 2026
r"""Install the built ``exactus`` executable system-wide.

``exactus --install`` builds the host-platform zipapp into
``bin/release/exactus_<system>_<arch>/`` — the executable, a generated
``MANIFEST.md`` describing it, and a generated ``README.md``, mirroring
``bin/release/exactus_linux_amd64/`` — then copies the executable into the
conventional system location: ``/usr/local/bin/exactus`` on macOS and
Linux, or ``%ProgramFiles%\\\\\\\\exactus`` plus a system ``PATH`` entry on
Windows. ``exactus --uninstall`` reverses the installation.

Installing also materializes every host-platform bundle component from
``exactus/bundle`` and registers their Python site directories through
an ``exactus-bundle.pth`` file in the user site-packages, so a plain
``python`` interpreter can import the bundled dependencies;
uninstalling removes the file.

Installing also registers user-level shell completion for the
``exactus`` command (Bash, Zsh, Fish, PowerShell); uninstalling removes
every exactus-owned registration the completion installer manages.

An existing platform release is reused only while its embedded source
signature still matches the live ``exactus/`` tree; an updated project
triggers a fresh build automatically. When invoked from an already
installed zipapp, the running archive is reinstalled without rebuilding;
``--rebuild`` forces a fresh build and requires the source checkout.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from os import W_OK, access, environ
from pathlib import Path
from platform import libc_ver, machine
from shutil import copy2, rmtree
from site import getusersitepackages
from subprocess import CalledProcessError
from subprocess import run as subprocess_run
from sys import argv, platform, stdout
from typing import TYPE_CHECKING, Final, Protocol, cast, final
from zipfile import is_zipfile

from exactus.bundle.freshness import bundle_stale
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.completion.install import (
    InstallResult,
    InstallStatus,
    Registration,
)
from exactus.packages.completion.install import diagnose as diagnose_completion
from exactus.packages.completion.install import install as install_completion
from exactus.packages.completion.install import (
    uninstall as uninstall_completion,
)
from exactus.packages.completion.profiles import profile_paths
from exactus.packages.package.build import build_check, kept_bundle_leaves
from exactus.packages.package.bundle import Constants as _GroupFinalConstants
from exactus.packages.package.config import load_config
from exactus.tools.common.cli import exactus_bundle_python_paths
from exactus.tools.common.conflict_copies import clear_conflict_copies
from exactus.tools.common.directory_inventory import heal_directory
from exactus.tools.common.sprint import SprintStyle, sprint, sprint_err
from exactus.tools.common.terminal import Constants as TerminalCodes
from exactus.tools.common.terminal import ExactusTerminal

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable, Sequence

    from exactus.packages.completion.model import CompletionShell


class _Winreg(Protocol):
    """Subset of the ``winreg`` module used for PATH management.

    Attributes:
        HKEY_LOCAL_MACHINE: Registry hive constant.
        KEY_READ: Read access mask.
        KEY_SET_VALUE: Value-write access mask.
        OpenKey: Registry key open function.
        QueryValueEx: Registry value read function.
        SetValueEx: Registry value write function.
        CloseKey: Registry key close function.

    """

    HKEY_LOCAL_MACHINE: int
    KEY_READ: int
    KEY_SET_VALUE: int
    OpenKey: Callable[[int, str, int, int], int]
    QueryValueEx: Callable[
        [int, str],
        tuple[str | bytes | int | list[str], int],
    ]
    SetValueEx: Callable[[int, str, int, int, str], None]
    CloseKey: Callable[[int], None]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        bin_dir: Grouped module constant.
        command_name: Grouped module constant.
        posix_install_dir: Grouped module constant.
        windows_root_variable: Grouped module constant.
        windows_root_fallback: Grouped module constant.
        windows_shim: Grouped module constant.
        systems: Grouped module constant.
        architectures: Grouped module constant.
        linux_libc_fallback: Grouped module constant.
        environment_key_path: Grouped module constant.
        progress_steps: Grouped module constant.
        pth_name: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[3]
    bin_dir: Final[Path] = root / "bin" / "release"
    command_name: Final[str] = "exactus"
    posix_install_dir: Final[Path] = Path("/usr/local/bin")
    windows_root_variable: Final[str] = "ProgramFiles"
    windows_root_fallback: Final[str] = "C:/Program Files"
    windows_shim: Final[str] = '@echo off\r\npy -3 "%~dp0exactus" %*\r\n'
    systems: Final[dict[str, str]] = {
        "linux": "linux",
        "darwin": "macos",
        "win32": "windows",
    }
    architectures: Final[dict[str, str]] = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    linux_libc_fallback: Final[str] = "glibc"
    environment_key_path: Final[str] = (
        "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment"
    )
    progress_steps: Final[tuple[tuple[str, float], ...]] = (
        ("dependencies", 0.2),
        ("release", 0.45),
        ("install", 0.15),
        ("completion", 0.2),
    )
    pth_name: Final[str] = "exactus-bundle.pth"


def host_platform() -> tuple[str, str]:
    """Detect the host operating system and architecture.

    Returns:
        The ``(system, architecture)`` pair used for release naming.

    Raises:
        ValueError: The host platform has no supported release mapping.

    """
    system: str | None = Constants.systems.get(platform)
    if system is None:
        msg: str = f"unsupported operating system: {platform}"
        raise ValueError(msg)
    architecture: str | None = Constants.architectures.get(machine().lower())
    if architecture is None:
        msg = f"unsupported architecture: {machine()}"
        raise ValueError(msg)
    return (system, architecture)


def host_target(*, system: str, architecture: str) -> str:
    """Resolve the bundle build target matching the host platform.

    Args:
        system: Operating-system identifier.
        architecture: CPU architecture identifier.

    Returns:
        A ``TARGETS`` key such as ``macos-arm64``.

    Raises:
        ValueError: No bundle target exists for the platform.

    """
    if system == "linux":
        libc: str = libc_ver()[0]
        name: str = (
            f"linux-musl-{architecture}"
            if libc.startswith("musl")
            else f"linux-{Constants.linux_libc_fallback}-{architecture}"
        )
    else:
        name = f"{system}-{architecture}"
    if name not in _GroupFinalConstants.targets:
        msg: str = f"no bundle target for {system}/{architecture}"
        raise ValueError(msg)
    return name


def release_name(*, system: str, architecture: str) -> str:
    """Render the platform release directory name.

    Args:
        system: Operating-system identifier.
        architecture: CPU architecture identifier.

    Returns:
        The ``exactus_<system>_<arch>`` directory name.

    """
    return f"exactus_{system}_{architecture}"


def _running_archive() -> Path | None:
    """Return the running zipapp when invoked from an installed binary.

    Returns:
        The resolved archive path, or ``None`` when running from source.

    """
    entry: Path = Path(argv[0])
    if entry.is_file() and is_zipfile(filename=entry):
        return entry.resolve()
    return None


def _write_release_readme(
    *,
    directory: Path,
    system: str,
    architecture: str,
) -> None:
    """Write the authored README and regenerate its file inventory.

    Args:
        directory: Platform release directory.
        system: Operating-system identifier.
        architecture: CPU architecture identifier.

    """
    _ = (directory / "README.md").write_text(
        data=(
            f"# `{directory.name}/`\n\nStandalone Exactus executable for "
            f"{system} {architecture}.\n"
        ),
        encoding="utf-8",
    )
    heal_directory(directory=directory, entries=sorted(directory.iterdir()))


def build_release(*, system: str, architecture: str) -> Path:
    """Build the host-platform zipapp and release directory contents.

    Args:
        system: Operating-system identifier.
        architecture: CPU architecture identifier.

    Returns:
        The built executable inside ``bin/release/exactus_<system>_<arch>/``.

    """
    _ = clear_conflict_copies(root=Constants.root)
    directory: Path = Constants.bin_dir / release_name(
        system=system,
        architecture=architecture,
    )
    target: Path = directory / Constants.command_name
    build_check(
        target=target,
        kept=kept_bundle_leaves(
            targets=[host_target(system=system, architecture=architecture)],
        ),
        self_test=load_config(root=Constants.root).build.self_test,
    )
    _write_release_readme(
        directory=directory,
        system=system,
        architecture=architecture,
    )
    return target


def _copy_posix(*, source: Path, destination: Path) -> None:
    """Copy the executable into a POSIX system binary directory.

    Escalates through ``sudo install`` when the destination directory is
    not writable by the current user.

    Args:
        source: Built ``exactus`` executable.
        destination: System-wide install path.

    """
    if destination.exists() and source.samefile(other_path=destination):
        return
    if access(path=destination.parent, mode=W_OK):
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = copy2(src=source, dst=destination)
        destination.chmod(mode=493)
        return
    if not destination.parent.is_dir():
        _ = subprocess_run(
            args=["sudo", "mkdir", "-p", str(object=destination.parent)],
            check=True,
        )
    _ = subprocess_run(
        args=[
            "sudo",
            "install",
            "-m",
            "0755",
            str(object=source),
            str(object=destination),
        ],
        check=True,
    )


def _remove_posix(*, destination: Path) -> bool:
    """Remove a POSIX system-wide installation.

    Args:
        destination: System-wide install path.

    Returns:
        Whether an installed executable was removed.

    """
    if not destination.exists():
        return False
    if access(path=destination.parent, mode=W_OK):
        destination.unlink()
        return True
    _ = subprocess_run(
        args=["sudo", "rm", "-f", str(object=destination)],
        check=True,
    )
    return True


def _windows_directory() -> Path:
    r"""Resolve the Windows system install directory.

    Returns:
        The ``%ProgramFiles%\\\\\\\\exactus`` directory.

    """
    root: str = (
        environ.get(Constants.windows_root_variable)
        or Constants.windows_root_fallback
    )
    return Path(root) / Constants.command_name


def _windows_path_entries(
    *,
    writable: bool,
) -> tuple[_Winreg, int, str, int] | None:
    """Open the system environment key and read ``Path``.

    Args:
        writable: Request write access to the registry key.

    Returns:
        The ``winreg`` module, open key, current value, and value kind,
        or ``None`` when the key cannot be opened.

    """
    winreg: _Winreg = cast(typ="_Winreg", val=import_module(name="winreg"))
    access_mask: int = winreg.KEY_READ | (
        winreg.KEY_SET_VALUE if writable else 0
    )
    try:
        key: int = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            Constants.environment_key_path,
            0,
            access_mask,
        )
        value, kind = winreg.QueryValueEx(key, "Path")
    except OSError:
        return None
    return (winreg, key, str(object=value), kind)


def _windows_path_update(*, directory: Path, remove: bool) -> None:
    """Add or remove the install directory in the system ``Path``.

    Args:
        directory: Install directory managed on ``Path``.
        remove: Remove the entry instead of adding it.

    Raises:
        PermissionError: The registry update requires elevation.

    """
    opened: tuple[_Winreg, int, str, int] | None = _windows_path_entries(
        writable=True,
    )
    if opened is None:
        msg: str = "updating the system PATH requires an elevated prompt"
        raise PermissionError(msg)
    winreg, key, value, kind = opened
    registry: _Winreg = winreg
    try:
        entries: list[str] = [entry for entry in value.split(sep=";") if entry]
        needle: str = str(object=directory)
        normalized: str = needle.replace("/", "\\").rstrip("\\").lower()
        kept: list[str] = [
            entry
            for entry in entries
            if entry.replace("/", "\\").rstrip("\\").lower() != normalized
        ]
        present: bool = len(kept) != len(entries)
        if not remove:
            kept = entries if present else [*entries, needle]
        if kept != entries:
            registry.SetValueEx(key, "Path", 0, kind, ";".join(kept))
    finally:
        registry.CloseKey(key)


def _install_windows(*, source: Path) -> Path:
    """Install the executable into ``%ProgramFiles%`` on Windows.

    Args:
        source: Built ``exactus`` executable.

    Returns:
        The installed executable path.

    """
    directory: Path = _windows_directory()
    directory.mkdir(parents=True, exist_ok=True)
    destination: Path = directory / Constants.command_name
    _ = copy2(src=source, dst=destination)
    _ = (directory / f"{Constants.command_name}.cmd").write_text(
        data=Constants.windows_shim,
        encoding="utf-8",
    )
    _windows_path_update(directory=directory, remove=False)
    return destination


def _uninstall_windows() -> Path | None:
    """Remove the Windows system installation.

    Returns:
        The removed install directory, or ``None`` when absent.

    """
    directory: Path = _windows_directory()
    removed: Path | None = None
    if directory.exists():
        rmtree(path=directory)
        removed = directory
    _windows_path_update(directory=directory, remove=True)
    return removed


def _ansi_enabled() -> bool:
    """Report whether standard output accepts ANSI styling.

    Returns:
        ``True`` only for a terminal that is not ``TERM=dumb``.

    """
    return stdout.isatty() and environ.get("TERM", "") != "dumb"


@dataclass(slots=True)
class _Step:
    """Track one checklist row's rendered state.

    Attributes:
        status: Row status tag (``WAITING``, ``RUNNING``, ``PASS``, or
            ``FAIL``).
        fraction: Completion fraction in ``[0, 1]``.
        detail: Trailing status text.
        mark: Failure position marked in the bar, or ``None``.

    """

    status: str = "WAITING"
    fraction: float = 0.0
    detail: str = ""
    mark: float | None = None


@final
class _InstallUi:
    """Render the ``exactus --install`` banner and live step checklist.

    The checklist reuses the pipeline progress block: repaints are
    synchronous, so nothing draws while ``sudo`` owns the terminal for
    a password prompt. Non-terminal output degrades to plain log lines.
    """

    def __init__(self, *, system: str, architecture: str) -> None:
        """Initialize step state and the resolved install target.

        Args:
            system: Operating-system identifier.
            architecture: CPU architecture identifier.

        """
        self._system = system
        self._architecture = architecture
        self._target: Path = (
            _windows_directory() / Constants.command_name
            if system == "windows"
            else Constants.posix_install_dir / Constants.command_name
        )
        self._rows: dict[str, _Step] = {
            name: _Step() for name, _weight in Constants.progress_steps
        }
        self._stage = "preparing"
        self._active = ""

    @property
    def target(self) -> Path:
        """Return the system-wide destination shown in the banner.

        Returns:
            The installed executable path the copy step will create.

        """
        return self._target

    @staticmethod
    def note(*, text: str) -> None:
        """Scroll a log line above the live checklist.

        Args:
            text: Message to print without corrupting the block.

        """
        ExactusTerminal.emit(text=text)

    @staticmethod
    def pause() -> None:
        """Lift the live block so prompts like ``sudo`` own the terminal."""
        ExactusTerminal.clear_progress(lines=0)

    def begin(self) -> None:
        """Print the information banner and paint the empty checklist."""
        styled: bool = _ansi_enabled()
        accent: str = (
            f"{TerminalCodes.bold}{TerminalCodes.cyan}" if styled else ""
        )
        dim: str = TerminalCodes.dim if styled else ""
        reset: str = TerminalCodes.reset if styled else ""
        ExactusTerminal.emit(text=f"{accent}exactus{reset} · install")
        ExactusTerminal.emit(
            text=(
                f"  {dim}platform{reset}  {self._system} {self._architecture}"
            ),
        )
        ExactusTerminal.emit(text=f"  {dim}target{reset}    {self._target}")
        self._paint()

    def start(self, *, step: str, detail: str = "") -> None:
        """Mark a step as running.

        Args:
            step: Checklist step name.
            detail: Trailing status text; the resolved target is shown
                for ``install`` when omitted.

        """
        self._active = step
        row: _Step = self._rows[step]
        row.status = "RUNNING"
        row.detail = detail or (
            str(object=self._target) if step == "install" else ""
        )
        self._stage = row.detail or step
        self._paint()

    def advance(self, *, step: str, fraction: float, detail: str = "") -> None:
        """Update a running step's bar fraction and detail text.

        Args:
            step: Checklist step name.
            fraction: Completion fraction in ``[0, 1]``.
            detail: Optional replacement status text.

        """
        row: _Step = self._rows[step]
        row.fraction = fraction
        if detail:
            row.detail = detail
            self._stage = detail
        self._paint()

    def done(self, *, step: str, detail: str) -> None:
        """Mark a step as finished at full progress.

        Args:
            step: Checklist step name.
            detail: Final status text for the row.

        """
        self._rows[step] = _Step(status="PASS", fraction=1.0, detail=detail)
        if detail:
            self._stage = detail
        if self._active == step:
            self._active = ""
        self._paint()

    def fail(self) -> None:
        """Flag the active step and leave the failed checklist on screen."""
        if self._active:
            row: _Step = self._rows[self._active]
            row.status = "FAIL"
            row.mark = row.fraction
            self._paint()
        ExactusTerminal.restore_cursor()

    def finish(self) -> None:
        """Paint the completed checklist and restore the cursor."""
        self._stage = "done"
        self._paint()
        ExactusTerminal.restore_cursor()

    def _paint(self) -> None:
        """Repaint the checklist block from the current step state."""
        _ = ExactusTerminal.progress(
            title="install",
            global_fraction=sum(
                (
                    weight * self._rows[name].fraction
                    for name, weight in Constants.progress_steps
                ),
            ),
            stage=self._stage,
            tools=tuple(
                (
                    (
                        name,
                        self._rows[name].status,
                        self._rows[name].fraction,
                        self._rows[name].detail,
                        self._rows[name].mark,
                    )
                    for name, _weight in Constants.progress_steps
                ),
            ),
            previous_lines=0,
        )


def _install_completion(
    *,
    destination: Path,
    ui: _InstallUi | None = None,
) -> int:
    """Register user-level shell completion for the installed command.

    Each supported shell profile or provider directory receives the
    managed registration; problems are reported without failing the
    installation itself.

    Args:
        destination: Installed executable the shell adapters invoke.
        ui: Optional install checklist receiving per-shell updates.

    Returns:
        The number of registration locations processed.

    """
    home: Path = Path.home()
    launcher: tuple[str, ...] = (str(object=destination),)
    locations: tuple[tuple[CompletionShell, Path], ...] = tuple(
        profile_paths(home=home, command_name=Constants.command_name),
    )
    total: int = len(locations)
    for index, (shell, profile) in enumerate(iterable=locations):
        if ui is not None:
            ui.advance(
                step="completion",
                fraction=index / max(total, 1),
                detail=f"{index + 1}/{total} {shell.value}",
            )
        try:
            result: InstallResult = install_completion(
                shell=shell,
                command_name=Constants.command_name,
                launcher=launcher,
                home=home,
                registration=Registration(path=profile, revision=""),
            )
        except OSError as exc:
            sprint_err(f"completion[{shell.value}]: {exc}")
            continue
        if result.status in (
            InstallStatus.BROKEN,
            InstallStatus.LAUNCHER_MISSING,
        ):
            sprint_err(f"completion[{shell.value}]: {result.detail}")
        elif ui is not None:
            ui.note(text=f"completion[{shell.value}]: {result.detail}")
        else:
            sprint(f"completion[{shell.value}]: {result.detail}")
    return total


def _uninstall_completion() -> None:
    """Remove every exactus-owned user-level completion registration."""
    home: Path = Path.home()
    launcher: tuple[str, ...] = (Constants.command_name,)
    for diagnosis in diagnose_completion(
        launcher=launcher,
        home=home,
        command_name=Constants.command_name,
    ):
        try:
            result: InstallResult = uninstall_completion(
                shell=diagnosis.shell,
                home=home,
                command_name=Constants.command_name,
                profile=diagnosis.path,
            )
        except OSError as exc:
            sprint_err(f"completion[{diagnosis.shell.value}]: {exc}")
            continue
        if result.changed:
            sprint(f"completion[{diagnosis.shell.value}]: {result.detail}")
        elif result.status == InstallStatus.BROKEN:
            sprint_err(f"completion[{diagnosis.shell.value}]: {result.detail}")


def _release_source(
    *,
    ui: _InstallUi,
    system: str,
    architecture: str,
    rebuild: bool,
) -> Path:
    """Resolve the executable to install, building it when required.

    Args:
        ui: Install checklist receiving step updates.
        system: Operating-system identifier.
        architecture: CPU architecture identifier.
        rebuild: Force a fresh build instead of reusing artifacts.

    Returns:
        The executable path to copy into place.

    Raises:
        ValueError: A rebuild was requested from an installed archive.

    """
    source: Path | None = _running_archive()
    if source is not None and rebuild:
        msg: str = (
            "--rebuild requires the source checkout; run `python "
            "exactus --install --rebuild` there"
        )
        raise ValueError(msg)
    if source is not None:
        ui.done(step="release", detail=f"reusing {source}")
        return source
    candidate: Path = (
        Constants.bin_dir
        / release_name(system=system, architecture=architecture)
        / Constants.command_name
    )
    if (
        candidate.is_file()
        and (not rebuild)
        and (
            not bundle_stale(
                bundle=candidate,
                exactus_dir=Constants.root / "exactus",
            )
        )
    ):
        ui.done(step="release", detail=f"reused {candidate}")
        return candidate
    ui.advance(
        step="release",
        fraction=0.2,
        detail=(
            f"building "
            f"{release_name(system=system, architecture=architecture)}"
        ),
    )
    built: Path = build_release(system=system, architecture=architecture)
    ui.done(step="release", detail=f"built {built}")
    return built


def _install_dependencies(*, ui: _InstallUi) -> int:
    """Materialize host bundle components and register Python site dirs.

    Every component in the host ``exactus/bundle`` leaf is materialized
    into the shared tools cache; components shipping a ``python/`` site
    directory are exposed to any user interpreter through an
    ``exactus-bundle.pth`` file in the user site-packages.

    Args:
        ui: Install checklist receiving step updates.

    Returns:
        The number of Python site directories registered.

    """
    site_dirs: tuple[Path, ...] | None = exactus_bundle_python_paths(
        root=Constants.root,
    )
    if site_dirs is None:
        ui.done(step="dependencies", detail="no host bundle resolved")
        return 0
    ui.advance(
        step="dependencies",
        fraction=0.8,
        detail=f"{len(site_dirs)} site directories",
    )
    site_packages: Path = Path(getusersitepackages())
    site_packages.mkdir(parents=True, exist_ok=True)
    _ = (site_packages / Constants.pth_name).write_text(
        data="".join(f"{site_dir}\n" for site_dir in site_dirs),
        encoding="utf-8",
    )
    ui.done(step="dependencies", detail=f"{len(site_dirs)} site directories")
    return len(site_dirs)


def install_system(*, rebuild: bool = False) -> Path:
    """Build or reuse the release and install it system-wide.

    Args:
        rebuild: Force a fresh build instead of reusing an existing
            ``bin/release/exactus_<system>_<arch>/exactus`` artifact.

    Returns:
        The installed executable path.

    Raises:
        ValueError: A rebuild was requested from an installed archive.

    """
    system, architecture = host_platform()
    ui: _InstallUi = _InstallUi(system=system, architecture=architecture)
    ui.begin()
    try:
        ui.start(step="dependencies", detail="materializing bundle")
        _ = _install_dependencies(ui=ui)
        ui.start(step="release", detail="resolving release")
        source: Path = _release_source(
            ui=ui,
            system=system,
            architecture=architecture,
            rebuild=rebuild,
        )
        ui.start(step="install")
        ui.pause()
        installed: Path = (
            _install_windows(source=source)
            if system == "windows"
            else _install_posix(source=source)
        )
        ui.done(step="install", detail=str(object=installed))
        ui.start(step="completion", detail="registering shell completion")
        profiles: int = _install_completion(destination=installed, ui=ui)
        ui.done(step="completion", detail=f"{profiles} shell profiles")
    except BaseException:
        ui.fail()
        raise
    ui.finish()
    return installed


def _install_posix(*, source: Path) -> Path:
    """Install the executable into the POSIX system binary directory.

    Args:
        source: Built ``exactus`` executable.

    Returns:
        The installed executable path.

    """
    destination: Path = Constants.posix_install_dir / Constants.command_name
    _copy_posix(source=source, destination=destination)
    return destination


def uninstall_system() -> Path | None:
    """Remove the system-wide installation.

    Returns:
        The removed path, or ``None`` when nothing was installed.

    """
    system, _architecture = host_platform()
    _uninstall_completion()
    (Path(getusersitepackages()) / Constants.pth_name).unlink(missing_ok=True)
    if system == "windows":
        return _uninstall_windows()
    destination: Path = Constants.posix_install_dir / Constants.command_name
    if _remove_posix(destination=destination):
        return destination
    return None


def create_parser() -> ArgumentParser:
    """Create the install/uninstall command parser.

    Returns:
        Parser accepting the ``--rebuild`` modifier.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="exactus --install",
        description=(
            "Build the host-platform exactus zipapp into bin"
            "/exactus_<system>_<arch>/ and install the `exactus` "
            "command system-wide, or remove that installation."
        ),
    )
    _ = parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "rebuild the platform zipapp even when its bin/release "
            "artifact already exists"
        ),
    )
    return parser


def run(*, arguments: Sequence[str] = (), uninstall: bool = False) -> int:
    """Run the install or uninstall command.

    Args:
        arguments: Command-line arguments after ``--install``.
        uninstall: Remove the installation instead of installing.

    Returns:
        Process exit status.

    """
    parser: ArgumentParser = create_parser()
    args: Namespace = parser.parse_args(args=tuple(arguments))
    try:
        if uninstall:
            removed: Path | None = uninstall_system()
            if removed is None:
                sprint(f"{Constants.command_name} is not installed")
            else:
                sprint(f"Removed {Constants.command_name} from {removed}")
            return 0
        destination: Path = install_system(rebuild=bool(args.rebuild))
    except (ValueError, OSError, CalledProcessError) as exc:
        sprint_err(f"error: {exc}")
        return 1
    sprint(
        f"Installed {Constants.command_name} to {destination}",
        style=SprintStyle(level="success"),
    )
    return 0
