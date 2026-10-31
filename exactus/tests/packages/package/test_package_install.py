"""Tests for system-wide installation of the built executable."""

from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile

import pytest

from exactus.packages.completion.install import (
    InstallResult,
    InstallStatus,
    Registration,
    ShellDiagnosis,
)
from exactus.packages.completion.model import CompletionShell
from exactus.packages.package import install
from exactus.packages.package.install import (
    Constants,
    build_release,
    create_parser,
    host_platform,
    host_target,
    install_system,
    release_name,
    run,
    uninstall_system,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    fail,
    private_call,
    private_result,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable
pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures(
    "isolated_completion",
)


@pytest.fixture
def isolated_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep completion probes away from the real user home.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """

    def no_profiles(
        *,
        home: Path,
        command_name: str,
    ) -> tuple[tuple[CompletionShell, Path], ...]:
        """Return no shell registration locations.

        Args:
            home: User home directory.
            command_name: Registered command name.

        Returns:
            An empty location list.

        """
        del home, command_name
        return ()

    def no_diagnoses(
        *,
        launcher: tuple[str, ...],
        home: Path,
        command_name: str,
    ) -> tuple[ShellDiagnosis, ...]:
        """Return no shell diagnoses.

        Args:
            launcher: Executable and fixed arguments.
            home: User home directory.
            command_name: Registered command name.

        Returns:
            An empty diagnosis list.

        """
        del launcher, home, command_name
        return ()

    monkeypatch.setattr(
        target=install,
        name="profile_paths",
        value=no_profiles,
    )
    monkeypatch.setattr(
        target=install,
        name="diagnose_completion",
        value=no_diagnoses,
    )


def _platform(
    *,
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    arch: str,
    libc: tuple[str, str] = ("glibc", "2.39"),
) -> None:
    """Patch the host platform probes inside the install module.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        system: Value replacing ``sys.platform``.
        arch: Value returned by ``platform.machine``.
        libc: Value returned by ``platform.libc_ver``.

    """

    def fake_machine() -> str:
        """Return the patched machine identifier.

        Returns:
            The architecture under test.

        """
        return arch

    def fake_libc_ver() -> tuple[str, str]:
        """Return the patched libc identity.

        Returns:
            The libc name and version under test.

        """
        return libc

    monkeypatch.setattr(target=install, name="platform", value=system)
    monkeypatch.setattr(target=install, name="machine", value=fake_machine)
    monkeypatch.setattr(target=install, name="libc_ver", value=fake_libc_ver)


def _fake_winreg(
    *,
    path_value: str = "C:\\Windows",
    recorded: list[tuple[str, object]] | None = None,
    fail_open: bool = False,
) -> ModuleType:
    """Build a recording stand-in for the ``winreg`` module.

    Args:
        path_value: Registry ``Path`` value returned by ``QueryValueEx``.
        recorded: Optional sink receiving ``("set", value)`` and
            ``("close", key)`` records.
        fail_open: Whether ``OpenKey`` raises ``OSError``.

    Returns:
        A module-shaped object exposing the used ``winreg`` surface.

    """
    log: list[tuple[str, object]] = recorded if recorded is not None else []

    def open_key(hive: object, path: str, reserved: int, mask: int) -> object:
        """Return a token key or raise when access is denied.

        Args:
            hive: Registry hive constant.
            path: Key path.
            reserved: Reserved argument.
            mask: Access mask.

        Returns:
            An opaque key token.

        Raises:
            OSError: When access is denied.

        """
        del hive, path, reserved, mask
        if fail_open:
            msg: str = "denied"
            raise OSError(msg)
        return "key-token"

    def query_value(key: object, name: str) -> tuple[str, int]:
        """Return the configured ``Path`` value.

        Args:
            key: Open key token.
            name: Value name.

        Returns:
            The stored value and a synthetic kind.

        """
        del key, name
        return (path_value, 7)

    def set_value(
        key: object,
        name: str,
        reserved: int,
        kind: object,
        value: str,
    ) -> None:
        """Record a ``SetValueEx`` write.

        Args:
            key: Open key token.
            name: Value name.
            reserved: Reserved argument.
            kind: Value kind.
            value: Value written.

        """
        del key, name, reserved, kind
        log.append(("set", value))

    def close_key(key: object) -> None:
        """Record a ``CloseKey`` call.

        Args:
            key: Open key token.

        """
        log.append(("close", key))

    fake: SimpleNamespace = SimpleNamespace(
        KEY_READ=1,
        KEY_SET_VALUE=2,
        HKEY_LOCAL_MACHINE="HKLM",
        OpenKey=open_key,
        QueryValueEx=query_value,
        SetValueEx=set_value,
        CloseKey=close_key,
    )
    return cast(typ="ModuleType", val=fake)


def _fake_module_importer(*, module: ModuleType) -> object:
    """Return an ``import_module`` stand-in producing ``module``.

    Args:
        module: Fake module returned for ``winreg``.

    Returns:
        A callable matching ``import_module`` keyword use.

    """

    def importer(*, name: str) -> ModuleType:
        """Return the fake module for ``winreg``.

        Args:
            name: Requested module name.

        Returns:
            The configured fake module.

        """
        del name
        return module

    return importer


def _stub_build(*, binary: Path) -> Callable[..., Path]:
    """Return the given binary without building anything.

    Args:
        binary: Pre-existing fake binary.

    Returns:
        A ``build_release`` stand-in returning the binary unchanged.

    """

    def fake_build_release(*, system: str, architecture: str) -> Path:
        """Pretend to build a release.

        Args:
            system: Operating-system identifier.
            architecture: CPU architecture identifier.

        Returns:
            The pre-existing binary path.

        """
        del system, architecture
        return binary

    return fake_build_release


def _deny_access(*, path: object, mode: int) -> bool:
    """Refuse every filesystem write check.

    Args:
        path: Path whose access is checked.
        mode: Access mode checked.

    Returns:
        Always ``False``.

    """
    del path, mode
    return False


def test_host_platform_maps_known_systems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Known ``sys.platform``/machine pairs map to release identifiers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    cases: tuple[tuple[str, str, str, str], ...] = (
        ("darwin", "arm64", "macos", "arm64"),
        ("darwin", "x86_64", "macos", "amd64"),
        ("linux", "aarch64", "linux", "arm64"),
        ("linux", "x86_64", "linux", "amd64"),
        ("win32", "AMD64", "windows", "amd64"),
        ("win32", "ARM64", "windows", "arm64"),
    )
    for raw_system, raw_arch, system, arch in cases:
        _platform(monkeypatch=monkeypatch, system=raw_system, arch=raw_arch)
        expect_equal(actual=host_platform(), expected=(system, arch))


def test_host_platform_rejects_unknown_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized ``sys.platform`` raises ``ValueError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _platform(monkeypatch=monkeypatch, system="freebsd", arch="amd64")
    with pytest.raises(
        expected_exception=ValueError,
        match="unsupported operating system",
    ):
        _ = host_platform()


def test_host_platform_rejects_unknown_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognized machine identifier raises ``ValueError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _platform(monkeypatch=monkeypatch, system="darwin", arch="riscv64")
    with pytest.raises(
        expected_exception=ValueError,
        match="unsupported architecture",
    ):
        _ = host_platform()


def test_host_target_selects_linux_libc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux targets pick the musl or glibc bundle variant.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    expect_equal(
        actual=host_target(system="linux", architecture="amd64"),
        expected="linux-glibc-amd64",
    )
    _platform(
        monkeypatch=monkeypatch,
        system="linux",
        arch="amd64",
        libc=("musl", "1.2"),
    )
    expect_equal(
        actual=host_target(system="linux", architecture="amd64"),
        expected="linux-musl-amd64",
    )


def test_host_target_selects_simple_names() -> None:
    """Non-Linux systems map straight onto ``<system>-<arch>``."""
    expect_equal(
        actual=host_target(system="macos", architecture="arm64"),
        expected="macos-arm64",
    )
    expect_equal(
        actual=host_target(system="windows", architecture="amd64"),
        expected="windows-amd64",
    )


def test_host_target_rejects_unsupported() -> None:
    """A system without a bundle target raises ``ValueError``."""
    with pytest.raises(
        expected_exception=ValueError,
        match="no bundle target",
    ):
        _ = host_target(system="plan9", architecture="amd64")


def test_release_name_matches_bin_layout() -> None:
    """Release directories follow the ``exactus_<os>_<arch>`` scheme."""
    expect_equal(
        actual=release_name(system="linux", architecture="amd64"),
        expected="exactus_linux_amd64",
    )
    expect_equal(
        actual=release_name(system="macos", architecture="arm64"),
        expected="exactus_macos_arm64",
    )


def test_running_archive_detects_zipapp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A file zipapp entry point resolves to its archive path.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    archive: Path = tmp_path / "exactus"
    zipped: ZipFile = ZipFile(file=archive, mode="w")
    zipped.writestr(zinfo_or_arcname="__main__.py", data="")
    zipped.close()
    monkeypatch.setattr(
        target=install,
        name="argv",
        value=[str(object=archive)],
    )
    expect_equal(
        actual=private_result(
            owner=install,
            name="_running_archive",
            kind=Path,
        ),
        expected=archive.resolve(),
    )


def test_running_archive_ignores_source_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Directories and non-zip files are not treated as archives.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    script: Path = tmp_path / "runner.py"
    _ = script.write_text(data="print(1)\n", encoding="utf-8")
    monkeypatch.setattr(
        target=install,
        name="argv",
        value=[str(object=script)],
    )
    expect_none(
        value=private_result(
            owner=install,
            name="_running_archive",
            kind=object,
        ),
    )
    monkeypatch.setattr(
        target=install,
        name="argv",
        value=[str(object=tmp_path)],
    )
    expect_none(
        value=private_result(
            owner=install,
            name="_running_archive",
            kind=object,
        ),
    )


def test_build_release_never_writes_archive(tmp_path: Path) -> None:
    """Release directories ship ``MANIFEST.md`` instead of tarballs.

    Args:
        tmp_path: Isolated filesystem root.

    """
    directory: Path = tmp_path / "exactus_macos_arm64"
    directory.mkdir()
    binary: Path = directory / "exactus"
    _ = binary.write_bytes(data=b"#!/usr/bin/env python3\n")
    manifest: object = private_call(
        owner=install,
        name="_write_release_readme",
        directory=directory,
        system="macos",
        architecture="arm64",
    )
    expect_none(value=manifest)
    expect_true(
        condition=(directory / "README.md").is_file(),
        message="missing release README",
    )
    expect_equal(actual=list(directory.glob(pattern="*.tar.gz")), expected=[])


def test_build_release_produces_full_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A staged build leaves executable, archive, and README together.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """

    def fake_check(*, target: Path, kept: object, self_test: bool) -> None:
        """Write a placeholder executable instead of building.

        Args:
            target: Destination executable.
            kept: Bundle leaves retained by target filtering.
            self_test: Self-diagnostic opt-in flag.

        """
        del kept, self_test
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_bytes(data=b"pyz")
        _ = (target.parent / "MANIFEST.md").write_text(
            data="# manifest\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        target=Constants,
        name="bin_dir",
        value=tmp_path / "bin",
    )
    monkeypatch.setattr(target=install, name="build_check", value=fake_check)

    def no_cleanup(*, root: Path) -> None:
        """Skip conflict-copy cleanup.

        Args:
            root: Project root that would be cleaned.

        """
        del root

    monkeypatch.setattr(
        target=install,
        name="clear_conflict_copies",
        value=no_cleanup,
    )
    binary: Path = build_release(system="macos", architecture="arm64")
    directory: Path = binary.parent
    expect_equal(actual=directory.name, expected="exactus_macos_arm64")
    expect_true(condition=binary.is_file(), message="missing binary")
    expect_true(
        condition=(directory / "MANIFEST.md").is_file(),
        message="missing release manifest",
    )
    expect_equal(actual=list(directory.glob(pattern="*.tar.gz")), expected=[])
    readme: Path = directory / "README.md"
    expect_true(condition=readme.is_file(), message="missing README.md")
    expect_in(
        member="exactus:inventory",
        container=readme.read_text(encoding="utf-8"),
    )


def test_install_posix_copies_into_system_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A writable system directory receives the executable.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    source: Path = tmp_path / "exactus"
    _ = source.write_bytes(data=b"pyz")
    destination: Path = private_result(
        owner=install,
        name="_install_posix",
        kind=Path,
        source=source,
    )
    expect_equal(actual=destination, expected=system_bin / "exactus")
    expect_true(condition=destination.is_file(), message="not installed")
    expect_equal(actual=destination.stat().st_mode & 0o777, expected=0o755)


def test_install_posix_skips_same_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reinstalling the running archive is a no-op copy.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    destination: Path = system_bin / "exactus"
    _ = destination.write_bytes(data=b"installed")
    private_result(
        owner=install,
        name="_install_posix",
        kind=Path,
        source=destination,
    )
    expect_equal(actual=destination.read_bytes(), expected=b"installed")


def test_install_posix_escalates_through_sudo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unwritable destination goes through ``sudo install``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    monkeypatch.setattr(target=install, name="access", value=_deny_access)
    commands: list[list[str]] = []

    def fake_run(*, args: list[str], check: bool) -> CompletedProcess[bytes]:
        """Record the escalated command instead of running it.

        Args:
            args: Command that would run.
            check: Whether failures raise.

        Returns:
            A successful completed process.

        """
        del check
        commands.append(args)
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(target=install, name="subprocess_run", value=fake_run)
    source: Path = tmp_path / "exactus"
    _ = source.write_bytes(data=b"pyz")
    destination: Path = private_result(
        owner=install,
        name="_install_posix",
        kind=Path,
        source=source,
    )
    expect_equal(actual=len(commands), expected=1)
    expect_equal(actual=commands[0][:3], expected=["sudo", "install", "-m"])
    expect_in(member=str(object=source), container=commands[0])
    expect_in(member=str(object=destination), container=commands[0])


def test_install_posix_creates_missing_dir_via_sudo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing destination directory is created with ``sudo mkdir``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    missing: Path = tmp_path / "missing" / "bin"
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=missing,
    )
    commands: list[list[str]] = []

    def fake_run(*, args: list[str], check: bool) -> CompletedProcess[bytes]:
        """Record escalated commands and materialize directories.

        Args:
            args: Command that would run.
            check: Whether failures raise.

        Returns:
            A successful completed process.

        """
        del check
        commands.append(args)
        if args[1] == "mkdir":
            Path(args[-1]).mkdir(parents=True)
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(target=install, name="subprocess_run", value=fake_run)
    source: Path = tmp_path / "exactus"
    _ = source.write_bytes(data=b"pyz")
    private_result(
        owner=install,
        name="_install_posix",
        kind=Path,
        source=source,
    )
    expect_equal(actual=commands[0][1], expected="mkdir")
    expect_equal(actual=commands[1][1], expected="install")


def test_remove_posix_reports_absent_and_removes(tmp_path: Path) -> None:
    """Removal reports a missing install and deletes a present one.

    Args:
        tmp_path: Isolated filesystem root.

    """
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    destination: Path = system_bin / "exactus"
    expect_false(
        condition=bool(
            private_result(
                owner=install,
                name="_remove_posix",
                kind=object,
                destination=destination,
            ),
        ),
        message="unexpected removal",
    )
    _ = destination.write_bytes(data=b"pyz")
    expect_true(
        condition=bool(
            private_result(
                owner=install,
                name="_remove_posix",
                kind=object,
                destination=destination,
            ),
        ),
        message="install not removed",
    )
    expect_false(
        condition=destination.exists(),
        message="file still installed",
    )


def test_remove_posix_escalates_through_sudo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unwritable removal escalates to ``sudo rm``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    destination: Path = system_bin / "exactus"
    _ = destination.write_bytes(data=b"pyz")
    monkeypatch.setattr(target=install, name="access", value=_deny_access)
    commands: list[list[str]] = []

    def fake_run(*, args: list[str], check: bool) -> CompletedProcess[bytes]:
        """Record the escalated removal command.

        Args:
            args: Command that would run.
            check: Whether failures raise.

        Returns:
            A successful completed process.

        """
        del check
        commands.append(args)
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(target=install, name="subprocess_run", value=fake_run)
    expect_true(
        condition=bool(
            private_result(
                owner=install,
                name="_remove_posix",
                kind=object,
                destination=destination,
            ),
        ),
        message="removal skipped",
    )
    expect_equal(actual=commands[0][:3], expected=["sudo", "rm", "-f"])
    expect_true(condition=destination.exists(), message="fake removed file")


def test_windows_directory_prefers_program_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Windows root honors ``ProgramFiles`` and its fallback.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.setenv(name="ProgramFiles", value="D:/Programs")
    expect_equal(
        actual=private_result(
            owner=install,
            name="_windows_directory",
            kind=Path,
        ),
        expected=Path("D:/Programs") / "exactus",
    )
    monkeypatch.delenv(name="ProgramFiles")
    expect_equal(
        actual=private_result(
            owner=install,
            name="_windows_directory",
            kind=Path,
        ),
        expected=Path("C:/Program Files") / "exactus",
    )


def test_windows_path_update_adds_and_removes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The registry ``Path`` gains and loses the install directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    recorded: list[tuple[str, object]] = []
    directory: Path = Path("C:/Program Files/exactus")
    value: list[str] = ["C:\\Windows"]

    def fake_entries(*, writable: bool) -> tuple[ModuleType, int, str, int]:
        """Return the recording winreg stand-in.

        Args:
            writable: Whether write access was requested.

        Returns:
            The fake module, key token, value, and kind.

        """
        del writable
        return (
            _fake_winreg(path_value=value[0], recorded=recorded),
            0,
            value[0],
            7,
        )

    monkeypatch.setattr(
        target=install,
        name="_windows_path_entries",
        value=fake_entries,
    )
    private_result(
        owner=install,
        name="_windows_path_update",
        kind=object,
        directory=directory,
        remove=False,
    )
    expect_equal(actual=recorded[0][1], expected=f"C:\\Windows;{directory}")
    value[0] = f"C:\\Windows;{directory}"
    private_result(
        owner=install,
        name="_windows_path_update",
        kind=object,
        directory=directory,
        remove=True,
    )
    sets: list[object] = [
        payload for kind_, payload in recorded if kind_ == "set"
    ]
    expect_equal(actual=sets[1], expected="C:\\Windows")


def test_windows_path_update_skips_existing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory already on ``Path`` produces no registry write.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    recorded: list[tuple[str, object]] = []
    existing: str = "C:\\Windows;C:\\Program Files\\exactus"

    def fake_entries(*, writable: bool) -> tuple[ModuleType, int, str, int]:
        """Return a registry already containing the directory.

        Args:
            writable: Whether write access was requested.

        Returns:
            The fake module, key token, value, and kind.

        """
        del writable
        return (
            _fake_winreg(path_value=existing, recorded=recorded),
            0,
            existing,
            7,
        )

    monkeypatch.setattr(
        target=install,
        name="_windows_path_entries",
        value=fake_entries,
    )
    private_result(
        owner=install,
        name="_windows_path_update",
        kind=object,
        directory=Path("C:/Program Files/exactus"),
        remove=False,
    )
    writes: list[object] = [
        payload for kind_, payload in recorded if kind_ == "set"
    ]
    expect_false(
        condition=bool(writes),
        message="registry written unnecessarily",
    )


def test_windows_path_update_requires_write_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused registry open surfaces as ``PermissionError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """

    def denied_entries(
        *,
        writable: bool,
    ) -> tuple[ModuleType, int, str, int] | None:
        """Refuse every registry open.

        Args:
            writable: Whether write access was requested.

        Returns:
            Always ``None``.

        """
        del writable
        return None

    monkeypatch.setattr(
        target=install,
        name="_windows_path_entries",
        value=denied_entries,
    )
    with pytest.raises(expected_exception=PermissionError, match="elevated"):
        private_result(
            owner=install,
            name="_windows_path_update",
            kind=object,
            directory=Path("C:/Program Files/exactus"),
            remove=False,
        )


def test_windows_path_entries_open_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``OSError`` during registry access returns ``None``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.setattr(
        target=install,
        name="import_module",
        value=_fake_module_importer(module=_fake_winreg(fail_open=True)),
    )
    expect_none(
        value=private_result(
            owner=install,
            name="_windows_path_entries",
            kind=object,
            writable=True,
        ),
    )


def test_install_windows_writes_pyz_and_shim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows install stages the pyz, the ``.cmd`` shim, and PATH.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setenv(name="ProgramFiles", value=str(object=tmp_path))
    recorded: list[tuple[str, object]] = []

    def fake_entries(*, writable: bool) -> tuple[ModuleType, int, str, int]:
        """Return the recording winreg stand-in.

        Args:
            writable: Whether write access was requested.

        Returns:
            The fake module, key token, value, and kind.

        """
        del writable
        return (
            _fake_winreg(path_value="C:\\Windows", recorded=recorded),
            0,
            "C:\\Windows",
            7,
        )

    monkeypatch.setattr(
        target=install,
        name="_windows_path_entries",
        value=fake_entries,
    )
    source: Path = tmp_path / "source" / "exactus"
    source.parent.mkdir()
    _ = source.write_bytes(data=b"pyz")
    destination: Path = private_result(
        owner=install,
        name="_install_windows",
        kind=Path,
        source=source,
    )
    directory: Path = tmp_path / "exactus"
    expect_equal(actual=destination, expected=directory / "exactus")
    expect_true(condition=destination.is_file(), message="pyz missing")
    shim: Path = directory / "exactus.cmd"
    expect_true(condition=shim.is_file(), message="shim missing")
    expect_in(
        member="%~dp0exactus",
        container=shim.read_text(encoding="utf-8"),
    )
    expect_equal(actual=recorded[0][1], expected=f"C:\\Windows;{directory}")


def test_uninstall_windows_removes_directory_and_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows uninstall drops the directory and its PATH entry.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.setenv(name="ProgramFiles", value=str(object=tmp_path))
    directory: Path = tmp_path / "exactus"
    directory.mkdir()
    _ = (directory / "exactus").write_bytes(data=b"pyz")
    recorded: list[tuple[str, object]] = []
    existing: str = f"C:\\Windows;{directory}"

    def fake_entries(*, writable: bool) -> tuple[ModuleType, int, str, int]:
        """Return a registry already containing the directory.

        Args:
            writable: Whether write access was requested.

        Returns:
            The fake module, key token, value, and kind.

        """
        del writable
        return (
            _fake_winreg(path_value=existing, recorded=recorded),
            0,
            existing,
            7,
        )

    monkeypatch.setattr(
        target=install,
        name="_windows_path_entries",
        value=fake_entries,
    )
    removed: Path | None = cast(
        typ="Path | None",
        val=private_call(owner=install, name="_uninstall_windows"),
    )
    expect_equal(actual=removed, expected=directory)
    expect_false(condition=directory.exists(), message="dir remains")
    expect_equal(actual=recorded[0][1], expected="C:\\Windows")


def test_install_system_uses_existing_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An up-to-date platform binary installs without rebuilding.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    release_dir: Path = tmp_path / "exactus_linux_amd64"
    release_dir.mkdir()
    binary: Path = release_dir / "exactus"
    _ = binary.write_bytes(data=b"pyz")
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )

    def fresh_bundle(*, bundle: Path, exactus_dir: Path) -> bool:
        """Report the release as up to date.

        Args:
            bundle: Executable zipapp being checked.
            exactus_dir: Live package directory compared against.

        Returns:
            Always ``False``.

        """
        del bundle, exactus_dir
        return False

    monkeypatch.setattr(
        target=install,
        name="bundle_stale",
        value=fresh_bundle,
    )

    def guard_build(*, system: str, architecture: str) -> Path:
        """Fail if a rebuild was attempted.

        Args:
            system: Operating-system identifier.
            architecture: CPU architecture identifier.

        Returns:
            Never returns.

        """
        del system, architecture
        fail(message="unexpected rebuild")

    monkeypatch.setattr(
        target=install,
        name="build_release",
        value=guard_build,
    )
    destination: Path = install_system()
    expect_equal(actual=destination, expected=system_bin / "exactus")
    expect_equal(actual=destination.read_bytes(), expected=b"pyz")


def test_install_system_rebuilds_stale_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A platform binary older than the sources gets rebuilt.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    release_dir: Path = tmp_path / "exactus_linux_amd64"
    release_dir.mkdir()
    _ = (release_dir / "exactus").write_bytes(data=b"stale")
    rebuilt: Path = tmp_path / "rebuilt" / "exactus"
    rebuilt.parent.mkdir()
    _ = rebuilt.write_bytes(data=b"fresh")
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )

    def stale_bundle(*, bundle: Path, exactus_dir: Path) -> bool:
        """Report the release as outdated.

        Args:
            bundle: Executable zipapp being checked.
            exactus_dir: Live package directory compared against.

        Returns:
            Always ``True``.

        """
        del bundle, exactus_dir
        return True

    monkeypatch.setattr(
        target=install,
        name="bundle_stale",
        value=stale_bundle,
    )
    monkeypatch.setattr(
        target=install,
        name="build_release",
        value=_stub_build(binary=rebuilt),
    )
    destination: Path = install_system()
    expect_equal(actual=destination.read_bytes(), expected=b"fresh")


def test_install_system_rebuild_flag_forces_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--rebuild`` builds a fresh binary even when one exists.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    release_dir: Path = tmp_path / "exactus_linux_amd64"
    release_dir.mkdir()
    _ = (release_dir / "exactus").write_bytes(data=b"stale")
    rebuilt: Path = tmp_path / "rebuilt" / "exactus"
    rebuilt.parent.mkdir()
    _ = rebuilt.write_bytes(data=b"fresh")
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    monkeypatch.setattr(
        target=install,
        name="build_release",
        value=_stub_build(binary=rebuilt),
    )
    destination: Path = install_system(rebuild=True)
    expect_equal(actual=destination.read_bytes(), expected=b"fresh")


def test_install_system_reinstalls_running_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An installed zipapp reinstalls itself without building.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    archive: Path = tmp_path / "exactus-pyz"
    zipped: ZipFile = ZipFile(file=archive, mode="w")
    zipped.writestr(zinfo_or_arcname="__main__.py", data="")
    zipped.close()
    monkeypatch.setattr(
        target=install,
        name="argv",
        value=[str(object=archive)],
    )
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    monkeypatch.setattr(
        target=install,
        name="build_release",
        value=_stub_build(binary=archive),
    )
    destination: Path = install_system()
    expect_equal(
        actual=destination.read_bytes(),
        expected=archive.read_bytes(),
    )


def test_install_system_rejects_bundled_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--rebuild`` from an installed archive raises ``ValueError``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    archive: Path = tmp_path / "exactus-pyz"
    zipped: ZipFile = ZipFile(file=archive, mode="w")
    zipped.writestr(zinfo_or_arcname="__main__.py", data="")
    zipped.close()
    monkeypatch.setattr(
        target=install,
        name="argv",
        value=[str(object=archive)],
    )
    with pytest.raises(expected_exception=ValueError, match="source checkout"):
        _ = install_system(rebuild=True)


def test_install_system_dispatches_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows hosts route installation to the Program Files path.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="win32", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    binary: Path = tmp_path / "exactus_windows_amd64" / "exactus"
    binary.parent.mkdir(parents=True)
    _ = binary.write_bytes(data=b"pyz")
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    seen: list[Path] = []

    def fake_install(*, source: Path) -> Path:
        """Record the Windows install target.

        Args:
            source: Built ``exactus`` executable.

        Returns:
            The source path unchanged.

        """
        seen.append(source)
        return source

    monkeypatch.setattr(
        target=install,
        name="_install_windows",
        value=fake_install,
    )
    destination: Path = install_system()
    expect_equal(actual=destination, expected=binary)
    expect_equal(actual=seen[0], expected=binary)


def test_uninstall_system_reports_missing_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Uninstalling with nothing installed returns ``None``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=tmp_path / "bin",
    )
    expect_none(value=uninstall_system())


def test_uninstall_system_removes_posix_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A present POSIX install is removed and reported.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    system_bin: Path = tmp_path / "bin"
    system_bin.mkdir()
    destination: Path = system_bin / "exactus"
    _ = destination.write_bytes(data=b"pyz")
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    expect_equal(actual=uninstall_system(), expected=destination)
    expect_false(condition=destination.exists(), message="still installed")


def test_uninstall_system_dispatches_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows hosts route uninstall to the Program Files path.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="win32", arch="amd64")
    directory: Path = tmp_path / "exactus"

    def windows_dir() -> Path:
        """Return the staged install directory.

        Returns:
            The temporary install directory.

        """
        return directory

    def skip_path_update(*, directory: Path, remove: bool) -> None:
        """Skip the registry update.

        Args:
            directory: Install directory managed on ``Path``.
            remove: Whether the entry would be removed.

        """
        del directory, remove

    monkeypatch.setattr(
        target=install,
        name="_windows_directory",
        value=windows_dir,
    )
    monkeypatch.setattr(
        target=install,
        name="_windows_path_update",
        value=skip_path_update,
    )
    expect_none(value=uninstall_system())


def test_create_parser_accepts_rebuild() -> None:
    """The parser exposes the ``--rebuild`` modifier."""
    parser: ArgumentParser = create_parser()
    args: Namespace = parser.parse_args(args=["--rebuild"])
    expect_true(condition=bool(args.rebuild), message="not parsed")
    args = parser.parse_args(args=[])
    expect_false(condition=bool(args.rebuild), message="unexpected default")


def _record_output(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[str], list[str]]:
    """Capture ``sprint``/``sprint_err`` messages into lists.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The standard and error message lists.

    """
    out_lines: list[str] = []
    err_lines: list[str] = []

    def fake_sprint(*args: object, **kwargs: object) -> None:
        """Record standard output text.

        Args:
            *args: Printed values.
            **kwargs: Ignored print options.

        """
        del kwargs
        out_lines.append(" ".join(str(object=arg) for arg in args))

    def fake_sprint_err(*args: object, **kwargs: object) -> None:
        """Record error output text.

        Args:
            *args: Printed values.
            **kwargs: Ignored print options.

        """
        del kwargs
        err_lines.append(" ".join(str(object=arg) for arg in args))

    monkeypatch.setattr(target=install, name="sprint", value=fake_sprint)
    monkeypatch.setattr(
        target=install,
        name="sprint_err",
        value=fake_sprint_err,
    )
    return (out_lines, err_lines)


def _record_terminal(
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[str], list[dict[str, object]], list[bool], list[int]]:
    """Replace ``ExactusTerminal`` with a frame and output recorder.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        ``(emitted, frames, restored, cleared)`` — emitted lines,
        keyword payloads of each ``progress`` repaint, cursor-restore
        flags, and the ``lines`` seen by ``clear_progress``.

    """
    emitted: list[str] = []
    frames: list[dict[str, object]] = []
    restored: list[bool] = []
    cleared: list[int] = []

    def fake_emit(*, text: str, stream: object = None) -> None:
        """Record an emitted line.

        Args:
            text: Emitted text.
            stream: Ignored destination.

        """
        del stream
        emitted.append(text)

    def fake_progress(**kwargs: object) -> int:
        """Record one progress repaint payload.

        Args:
            **kwargs: ``ExactusTerminal.progress`` arguments.

        Returns:
            The frame's row count.

        """
        frames.append(kwargs)
        return 0

    def fake_clear_progress(*, lines: int) -> None:
        """Record a live-block removal.

        Args:
            lines: Reported block height.

        """
        cleared.append(lines)

    def fake_restore_cursor() -> None:
        """Record a cursor restore."""
        restored.append(True)

    monkeypatch.setattr(
        target=install,
        name="ExactusTerminal",
        value=SimpleNamespace(
            emit=fake_emit,
            progress=fake_progress,
            clear_progress=fake_clear_progress,
            restore_cursor=fake_restore_cursor,
        ),
    )
    return (emitted, frames, restored, cleared)


def _stage_release_reuse(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    contents: bytes = b"pyz",
) -> Path:
    """Stage an up-to-date release and a writable install directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.
        contents: Payload of the staged release binary.

    Returns:
        The staged system binary directory.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    release_dir: Path = tmp_path / "exactus_linux_amd64"
    release_dir.mkdir()
    _ = (release_dir / "exactus").write_bytes(data=contents)
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )

    def fresh_bundle(*, bundle: Path, exactus_dir: Path) -> bool:
        """Report the staged release as up to date.

        Args:
            bundle: Executable zipapp being checked.
            exactus_dir: Live package directory compared against.

        Returns:
            Always ``False``.

        """
        del bundle, exactus_dir
        return False

    monkeypatch.setattr(
        target=install,
        name="bundle_stale",
        value=fresh_bundle,
    )
    return system_bin


def test_run_reports_install_and_uninstall(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The command prints installed and removed locations.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    out_lines, _err_lines = _record_output(monkeypatch=monkeypatch)
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    release_dir: Path = tmp_path / "exactus_linux_amd64"
    release_dir.mkdir()
    _ = (release_dir / "exactus").write_bytes(data=b"pyz")
    system_bin: Path = tmp_path / "usr" / "local" / "bin"
    system_bin.mkdir(parents=True)
    monkeypatch.setattr(target=Constants, name="bin_dir", value=tmp_path)
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=system_bin,
    )
    expect_equal(actual=run(), expected=0)
    expect_in(member="Installed exactus to", container=out_lines[0])
    expect_equal(actual=run(uninstall=True), expected=0)
    expect_in(member="Removed exactus from", container=out_lines[1])
    expect_equal(actual=run(uninstall=True), expected=0)
    expect_in(member="is not installed", container=out_lines[2])


def test_run_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures surface as an error line and a nonzero status.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    _out_lines, err_lines = _record_output(monkeypatch=monkeypatch)

    def broken_install(*, rebuild: bool) -> Path:
        """Fail installation unconditionally.

        Args:
            rebuild: Ignored.

        Returns:
            Never returns.

        Raises:
            PermissionError: Always.

        """
        del rebuild
        msg: str = "denied"
        raise PermissionError(msg)

    monkeypatch.setattr(
        target=install,
        name="install_system",
        value=broken_install,
    )
    expect_equal(actual=run(), expected=1)
    expect_in(member="error: denied", container=err_lines[0])

    def failed_build(*, rebuild: bool) -> Path:
        """Fail like an aborted ``sudo install``.

        Args:
            rebuild: Ignored.

        Returns:
            Never returns.

        Raises:
            CalledProcessError: Always.

        """
        del rebuild
        raise CalledProcessError(returncode=1, cmd="sudo install")

    monkeypatch.setattr(
        target=install,
        name="install_system",
        value=failed_build,
    )
    expect_equal(actual=run(), expected=1)
    expect_in(member="error:", container=err_lines[1])


def test_install_completion_registers_each_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every shell location receives the managed registration.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    out_lines, _err_lines = _record_output(monkeypatch=monkeypatch)
    destination: Path = tmp_path / "exactus"
    profiles: tuple[tuple[CompletionShell, Path], ...] = (
        (CompletionShell.BASH, tmp_path / ".bashrc"),
        (CompletionShell.FISH, tmp_path / "exactus.fish"),
    )
    recorded: list[tuple[str, tuple[str, ...], Path]] = []

    def fake_profiles(
        *,
        home: Path,
        command_name: str,
    ) -> tuple[tuple[CompletionShell, Path], ...]:
        """Return the staged registration locations.

        Args:
            home: User home directory.
            command_name: Registered command name.

        Returns:
            The staged shell/path pairs.

        """
        del home, command_name
        return profiles

    def fake_install(
        *,
        shell: CompletionShell,
        command_name: str,
        launcher: tuple[str, ...],
        home: Path,
        registration: Registration,
    ) -> InstallResult:
        """Record one registration call.

        Args:
            shell: Target shell.
            command_name: Registered command name.
            launcher: Executable and fixed arguments.
            home: User home directory.
            registration: Startup destination metadata.

        Returns:
            A healthy install result.

        """
        del command_name, home
        recorded.append((shell.value, launcher, registration.path))
        return InstallResult(
            shell=shell,
            status=InstallStatus.HEALTHY,
            path=registration.path,
            changed=True,
            detail=f"installed {registration.path}",
        )

    monkeypatch.setattr(
        target=install,
        name="profile_paths",
        value=fake_profiles,
    )
    monkeypatch.setattr(
        target=install,
        name="install_completion",
        value=fake_install,
    )
    private_call(
        owner=install,
        name="_install_completion",
        destination=destination,
    )
    expect_equal(actual=len(recorded), expected=2)
    expect_equal(actual=recorded[0][1], expected=(str(object=destination),))
    expect_equal(actual=recorded[0][0], expected="bash")
    expect_in(member="completion[bash]:", container=out_lines[0])


def test_install_completion_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Broken and failing registrations warn without aborting.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _out_lines, err_lines = _record_output(monkeypatch=monkeypatch)
    calls: list[str] = []

    def fake_profiles(
        *,
        home: Path,
        command_name: str,
    ) -> tuple[tuple[CompletionShell, Path], ...]:
        """Return two staged locations.

        Args:
            home: User home directory.
            command_name: Registered command name.

        Returns:
            Bash and Zsh locations.

        """
        del home, command_name
        return (
            (CompletionShell.BASH, tmp_path / ".bashrc"),
            (CompletionShell.ZSH, tmp_path / ".zshrc"),
        )

    def fake_install(
        *,
        shell: CompletionShell,
        command_name: str,
        launcher: tuple[str, ...],
        home: Path,
        registration: Registration,
    ) -> InstallResult:
        """Break the first shell and fail the second.

        Args:
            shell: Target shell.
            command_name: Registered command name.
            launcher: Executable and fixed arguments.
            home: User home directory.
            registration: Startup destination metadata.

        Returns:
            A broken result for Bash.

        Raises:
            OSError: For the Zsh registration.

        """
        del command_name, launcher, home, registration
        calls.append(shell.value)
        if shell == CompletionShell.BASH:
            return InstallResult(
                shell=shell,
                status=InstallStatus.BROKEN,
                path=tmp_path / ".bashrc",
                changed=False,
                detail="refusing to overwrite foreign content",
            )
        msg: str = "no write access"
        raise OSError(msg)

    monkeypatch.setattr(
        target=install,
        name="profile_paths",
        value=fake_profiles,
    )
    monkeypatch.setattr(
        target=install,
        name="install_completion",
        value=fake_install,
    )
    private_call(
        owner=install,
        name="_install_completion",
        destination=tmp_path / "exactus",
    )
    expect_equal(actual=len(calls), expected=2)
    expect_in(member="refusing to overwrite", container=err_lines[0])
    expect_in(member="no write access", container=err_lines[1])


def test_uninstall_completion_removes_registrations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Diagnosed registrations are removed and reported.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    out_lines, _err_lines = _record_output(monkeypatch=monkeypatch)
    profiles: tuple[tuple[CompletionShell, Path], ...] = (
        (CompletionShell.BASH, tmp_path / ".bashrc"),
        (CompletionShell.ZSH, tmp_path / ".zshrc"),
    )
    removed: list[Path] = []

    def fake_diagnose(
        *,
        launcher: tuple[str, ...],
        home: Path,
        command_name: str,
    ) -> tuple[ShellDiagnosis, ...]:
        """Diagnose the staged locations as installed.

        Args:
            launcher: Executable and fixed arguments.
            home: User home directory.
            command_name: Registered command name.

        Returns:
            Healthy diagnoses for both profiles.

        """
        del launcher, home, command_name
        return tuple(
            ShellDiagnosis(
                shell=shell,
                status=InstallStatus.HEALTHY,
                path=profile,
                detail="installed",
            )
            for shell, profile in profiles
        )

    def fake_uninstall(
        *,
        shell: CompletionShell,
        home: Path,
        command_name: str,
        profile: Path | None,
    ) -> InstallResult:
        """Record one removal and drop the Bash block.

        Args:
            shell: Target shell.
            home: User home directory.
            command_name: Registered command name.
            profile: Registration path being removed.

        Returns:
            A missing result marking the removal.

        """
        del home, command_name
        if profile is None:
            fail(message="no profile")
        removed.append(profile)
        return InstallResult(
            shell=shell,
            status=InstallStatus.MISSING,
            path=profile,
            changed=True,
            detail=f"removed managed block from {profile}",
        )

    monkeypatch.setattr(
        target=install,
        name="diagnose_completion",
        value=fake_diagnose,
    )
    monkeypatch.setattr(
        target=install,
        name="uninstall_completion",
        value=fake_uninstall,
    )
    private_call(owner=install, name="_uninstall_completion")
    expect_equal(actual=len(removed), expected=2)
    expect_equal(actual=removed[0], expected=profiles[0][1])
    expect_in(member="removed managed block", container=out_lines[0])


def test_install_system_registers_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """System installation also installs the user completions.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    monkeypatch.setattr(target=install, name="argv", value=["exactus"])
    destination: Path = tmp_path / "bin" / "exactus"
    destination.parent.mkdir(parents=True)
    _ = destination.write_bytes(data=b"pyz")
    completed: list[Path] = []

    def fake_posix(*, source: Path) -> Path:
        """Pretend the copy succeeded.

        Args:
            source: Built ``exactus`` executable.

        Returns:
            The staged destination.

        """
        del source
        return destination

    def fake_completion(*, destination: Path, ui: object = None) -> int:
        """Record the completion registration destination.

        Args:
            destination: Installed executable path.
            ui: Ignored checklist handle.

        Returns:
            No processed profiles.

        """
        del ui
        completed.append(destination)
        return 0

    monkeypatch.setattr(
        target=install,
        name="build_release",
        value=_stub_build(binary=destination),
    )
    monkeypatch.setattr(
        target=install,
        name="_install_posix",
        value=fake_posix,
    )
    monkeypatch.setattr(
        target=install,
        name="_install_completion",
        value=fake_completion,
    )
    expect_equal(actual=install_system(), expected=destination)
    expect_equal(actual=completed, expected=[destination])


def test_uninstall_system_removes_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """System uninstall removes completions even with no binary.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _platform(monkeypatch=monkeypatch, system="linux", arch="amd64")
    removed: list[bool] = []

    def fake_completion() -> None:
        """Record the completion removal."""
        removed.append(True)

    monkeypatch.setattr(
        target=install,
        name="_uninstall_completion",
        value=fake_completion,
    )
    monkeypatch.setattr(
        target=Constants,
        name="posix_install_dir",
        value=tmp_path / "bin",
    )
    expect_none(value=uninstall_system())
    expect_equal(actual=removed, expected=[True])


def test_ansi_enabled_requires_capable_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ANSI styling requires a terminal that is not ``TERM=dumb``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    expect_false(
        condition=private_result(
            owner=install,
            name="_ansi_enabled",
            kind=bool,
        ),
        message="non-tty stdout must not be styled",
    )

    def tty() -> bool:
        """Report a terminal-backed stream.

        Returns:
            Always ``True``.

        """
        return True

    monkeypatch.setattr(
        target=install,
        name="stdout",
        value=SimpleNamespace(isatty=tty),
    )
    monkeypatch.setenv(name="TERM", value="dumb")
    expect_false(
        condition=private_result(
            owner=install,
            name="_ansi_enabled",
            kind=bool,
        ),
        message="dumb terminals must not be styled",
    )
    monkeypatch.setenv(name="TERM", value="xterm-256color")
    expect_true(
        condition=private_result(
            owner=install,
            name="_ansi_enabled",
            kind=bool,
        ),
        message="capable terminals should be styled",
    )


def test_install_system_paints_banner_and_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--install`` emits the banner and repaints the step checklist.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    emitted, frames, restored, cleared = _record_terminal(
        monkeypatch=monkeypatch,
    )
    system_bin: Path = _stage_release_reuse(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    destination: Path = install_system()
    expect_equal(actual=destination, expected=system_bin / "exactus")
    expect_in(member="exactus", container=emitted[0])
    expect_in(member="install", container=emitted[0])
    expect_in(member="linux amd64", container=emitted[1])
    expect_in(member=str(object=system_bin), container=emitted[2])
    for line in emitted:
        expect_true(
            condition="\x1b" not in line,
            message=f"escape leaked into non-tty output: {line!r}",
        )
    first_tools: object = frames[0]["tools"]
    first_statuses: tuple[object, ...] = tuple(
        row[1]
        for row in cast(
            typ="tuple[tuple[str, str, float, str, float | None], ...]",
            val=first_tools,
        )
    )
    expect_equal(
        actual=first_statuses,
        expected=("WAITING", "WAITING", "WAITING", "WAITING"),
    )
    final: dict[str, object] = frames[-1]
    expect_equal(actual=final["stage"], expected="done")
    expect_equal(actual=final["global_fraction"], expected=1.0)
    final_statuses: tuple[object, ...] = tuple(
        row[1]
        for row in cast(
            typ="tuple[tuple[str, str, float, str, float | None], ...]",
            val=final["tools"],
        )
    )
    expect_equal(
        actual=final_statuses,
        expected=("PASS", "PASS", "PASS", "PASS"),
    )
    expect_true(condition=bool(restored), message="cursor never restored")
    expect_true(
        condition=bool(cleared),
        message="block never lifted for the privileged copy",
    )


def test_install_system_marks_failed_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed stage leaves its row FAIL-marked and the cursor freed.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _emitted, frames, restored, _cleared = _record_terminal(
        monkeypatch=monkeypatch,
    )
    _ = _stage_release_reuse(monkeypatch=monkeypatch, tmp_path=tmp_path)

    def broken_copy(*, source: Path) -> Path:
        """Fail like an aborted ``sudo install``.

        Args:
            source: Ignored release executable.

        Returns:
            Never returns.

        Raises:
            CalledProcessError: Always.

        """
        del source
        raise CalledProcessError(returncode=1, cmd="sudo install")

    monkeypatch.setattr(
        target=install,
        name="_install_posix",
        value=broken_copy,
    )
    with pytest.raises(expected_exception=CalledProcessError):
        _ = install_system()
    failing: dict[str, object] | None = None
    for frame in frames:
        tools: tuple[tuple[str, str, float, str, float | None], ...] = cast(
            typ="tuple[tuple[str, str, float, str, float | None], ...]",
            val=frame["tools"],
        )
        if any(row[1] == "FAIL" for row in tools):
            failing = frame
    if failing is None:
        fail(message="no frame marked the failed step")
    tools = cast(
        typ="tuple[tuple[str, str, float, str, float | None], ...]",
        val=failing["tools"],
    )
    marked: tuple[tuple[str, str, float, str, float | None], ...] = tuple(
        row for row in tools if row[1] == "FAIL"
    )
    expect_equal(actual=marked[0][0], expected="install")
    expect_true(
        condition=marked[0][4] is not None,
        message="failed step carries no failure mark",
    )
    expect_true(
        condition=bool(restored),
        message="cursor never restored after failure",
    )


def test_install_system_drives_ui_sequence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``install_system`` walks the checklist steps in order.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    calls: list[tuple[object, ...]] = []

    class RecorderUi:
        """Record the checklist calls ``install_system`` performs."""

        def __init__(self, *, system: str, architecture: str) -> None:
            """Record construction with the detected platform.

            Args:
                system: Operating-system identifier.
                architecture: CPU architecture identifier.

            """
            calls.append(("init", system, architecture))

        @staticmethod
        def begin() -> None:
            """Record the banner paint."""
            calls.append(("begin",))

        @staticmethod
        def start(*, step: str, detail: str = "") -> None:
            """Record a step start.

            Args:
                step: Checklist step name.
                detail: Trailing status text.

            """
            calls.append(("start", step, detail))

        @staticmethod
        def advance(*, step: str, fraction: float, detail: str = "") -> None:
            """Record a step update.

            Args:
                step: Checklist step name.
                fraction: Completion fraction.
                detail: Replacement status text.

            """
            calls.append(("advance", step, fraction, detail))

        @staticmethod
        def done(*, step: str, detail: str) -> None:
            """Record a step completion.

            Args:
                step: Checklist step name.
                detail: Final status text.

            """
            calls.append(("done", step, detail))

        @staticmethod
        def note(*, text: str) -> None:
            """Record a scrolled log line.

            Args:
                text: Message text.

            """
            calls.append(("note", text))

        @staticmethod
        def pause() -> None:
            """Record the live block being lifted."""
            calls.append(("pause",))

        @staticmethod
        def fail() -> None:
            """Record a failure flag."""
            calls.append(("fail",))

        @staticmethod
        def finish() -> None:
            """Record the checklist completion."""
            calls.append(("finish",))

    monkeypatch.setattr(target=install, name="_InstallUi", value=RecorderUi)
    system_bin: Path = _stage_release_reuse(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    destination: Path = install_system()
    expect_equal(actual=destination, expected=system_bin / "exactus")
    names: tuple[object, ...] = tuple(call[0] for call in calls)
    expect_equal(actual=names[0], expected="init")
    expect_equal(actual=names[1], expected="begin")
    expect_equal(actual=names[-1], expected="finish")
    expect_in(
        member=("start", "release", "resolving release"),
        container=calls,
    )
    reused: Path = tmp_path / "exactus_linux_amd64" / "exactus"
    expect_in(member=("done", "release", f"reused {reused}"), container=calls)
    expect_in(member=("pause",), container=calls)
    expect_in(
        member=("start", "completion", "registering shell completion"),
        container=calls,
    )
    expect_true(
        condition=("fail",) not in calls,
        message="healthy install flagged a failure",
    )
    install_index: int = names.index("pause")
    done_install: int = next(
        index
        for index, call in enumerate(iterable=calls)
        if call[:2] == ("done", "install")
    )
    expect_true(
        condition=install_index < done_install,
        message="privileged copy must run while the block is lifted",
    )


def test_install_completion_advances_ui(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Per-shell registration updates the checklist and returns a count.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    _record_terminal(monkeypatch=monkeypatch)
    advances: list[tuple[object, ...]] = []
    notes: list[str] = []

    def fake_advance(*, step: str, fraction: float, detail: str = "") -> None:
        """Record a checklist fraction update.

        Args:
            step: Checklist step name.
            fraction: Completion fraction.
            detail: Replacement status text.

        """
        advances.append((step, fraction, detail))

    def fake_note(*, text: str) -> None:
        """Record a scrolled log line.

        Args:
            text: Message text.

        """
        notes.append(text)

    ui: SimpleNamespace = SimpleNamespace(advance=fake_advance, note=fake_note)
    profiles: tuple[tuple[CompletionShell, Path], ...] = (
        (CompletionShell.BASH, tmp_path / ".bashrc"),
        (CompletionShell.ZSH, tmp_path / ".zshrc"),
    )

    def fake_profiles(
        *,
        home: Path,
        command_name: str,
    ) -> tuple[tuple[CompletionShell, Path], ...]:
        """Return the staged registration locations.

        Args:
            home: User home directory.
            command_name: Registered command name.

        Returns:
            The staged shell/path pairs.

        """
        del home, command_name
        return profiles

    def fake_install(
        *,
        shell: CompletionShell,
        command_name: str,
        launcher: tuple[str, ...],
        home: Path,
        registration: Registration,
    ) -> InstallResult:
        """Report a healthy registration.

        Args:
            shell: Target shell.
            command_name: Registered command name.
            launcher: Executable and fixed arguments.
            home: User home directory.
            registration: Startup destination metadata.

        Returns:
            A healthy install result.

        """
        del command_name, launcher, home
        return InstallResult(
            shell=shell,
            status=InstallStatus.HEALTHY,
            path=registration.path,
            changed=True,
            detail=f"installed {registration.path}",
        )

    monkeypatch.setattr(
        target=install,
        name="profile_paths",
        value=fake_profiles,
    )
    monkeypatch.setattr(
        target=install,
        name="install_completion",
        value=fake_install,
    )
    processed: int = cast(
        typ="int",
        val=private_call(
            owner=install,
            name="_install_completion",
            destination=tmp_path / "exactus",
            ui=ui,
        ),
    )
    expect_equal(actual=processed, expected=2)
    expect_equal(actual=len(advances), expected=2)
    expect_equal(actual=advances[0][0], expected="completion")
    expect_equal(actual=advances[0][1], expected=0.0)
    expect_equal(actual=advances[1][1], expected=0.5)
    expect_equal(actual=len(notes), expected=2)
    expect_in(member="completion[bash]:", container=notes[0])
