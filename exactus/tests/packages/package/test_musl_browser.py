"""Verify native browser payload layout without contacting package mirrors."""

from __future__ import annotations

from subprocess import CompletedProcess, TimeoutExpired
from textwrap import dedent
from typing import TYPE_CHECKING, Literal

import pytest

from exactus.packages.package import musl_browser
from exactus.packages.package.bundle import BundleBuilder, BundleConfig
from exactus.packages.package.bundle import Constants as BundleConstants
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
@pytest.mark.parametrize("corrupt", [False, True])
def test_native_browser_launchers_and_abi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arch: Literal["amd64", "arm64"],
    *,
    corrupt: bool,
) -> None:
    """Stage the right ABI, relative links, fonts and both launch modes.

    Args:
        tmp_path: Isolated payload destination.
        monkeypatch: Replaces the Docker process with a signed-root fixture.
        arch: Target CPU architecture.
        corrupt: Whether the staged executables have an invalid ABI.

    """
    commands: list[tuple[str, ...]] = []
    native: Path = tmp_path / "playwright-browsers" / "native"

    def stage_packages(
        *,
        args: tuple[str, ...],
        check: bool,
        timeout: int,
    ) -> CompletedProcess[str]:
        """Populate a synthetic APK root instead of running Docker.

        Args:
            args: Recorded Docker command.
            check: Required failure propagation.
            timeout: Required bounded build duration.

        Returns:
            Successful synthetic command result.

        """
        commands.append(args)
        expect_true(condition=check)
        expect_true(condition=timeout > 0)
        binary: str
        for binary in (
            "usr/lib/chromium/chrome",
            "usr/lib/chromium/chromium-headless-shell",
            "usr/bin/ffmpeg",
        ):
            path: Path = native / binary
            path.parent.mkdir(parents=True, exist_ok=True)
            machine: int = 0 if corrupt else 62 if arch == "amd64" else 183
            _ = path.write_bytes(
                data=b"\x7fELF\x02\x01"
                + bytes(12)
                + machine.to_bytes(length=2, byteorder="little"),
            )
        (native / "lib").mkdir()
        (native / "lib" / "example.so").symlink_to(
            target="/usr/lib/example.so",
        )
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(target=musl_browser, name="run", value=stage_packages)
    if corrupt:
        with pytest.raises(expected_exception=ValueError, match="browser ABI"):
            musl_browser.install(
                stage=tmp_path,
                image="alpine@sha256:fixture",
                version="156.0.8078.79-r0",
                arch=arch,
                revisions={"chromium": "1248"},
            )
        return
    musl_browser.install(
        stage=tmp_path,
        image="alpine@sha256:fixture",
        version="156.0.8078.79-r0",
        arch=arch,
        revisions={
            "chromium": "1248",
            "chromium-headless-shell": "1248",
            "ffmpeg": "1013",
        },
    )
    expect_in(member=f"linux/{arch}", container=commands[0])
    expect_in(member="alpine@sha256:fixture", container=commands[0])
    expect_true(
        condition=not (native / "lib" / "example.so").readlink().is_absolute(),
    )
    expect_true(condition=(native / "fonts.conf").is_file())
    suffix: str = "linux64" if arch == "amd64" else "linux-arm64"
    path: Path
    for path in (
        tmp_path
        / "playwright-browsers"
        / "chromium-1248"
        / f"chrome-{suffix}"
        / "chrome",
        tmp_path
        / "playwright-browsers"
        / "chromium_headless_shell-1248"
        / f"chrome-headless-shell-{suffix}"
        / "chrome-headless-shell",
        tmp_path / "playwright-browsers" / "ffmpeg-1013" / "ffmpeg-linux",
    ):
        text: str = path.read_text(encoding="utf-8")
        expect_in(member="LD_LIBRARY_PATH", container=text)
        expect_in(member="pulseaudio", container=text)
        expect_true(condition=str(object=tmp_path) not in text)
        expect_equal(actual=path.stat().st_mode & 0o777, expected=0o755)


def test_windows_arm64_ships_the_playwright_x64_browser() -> None:
    """Windows ARM64 includes offline browsers, using OS x64 emulation."""
    expect_equal(
        actual=BundleConstants.targets["windows-arm64"].browsers,
        expected=BundleConstants.windows_browsers,
    )


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_musl_python_driver_keeps_native_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arch: Literal["amd64", "arm64"],
) -> None:
    """Only Playwright's portable driver uses a manylinux wheel.

    Args:
        tmp_path: Isolated component staging root.
        monkeypatch: Records pip commands rather than installing packages.
        arch: Target CPU architecture.

    """
    commands: list[tuple[str, ...]] = []

    def record(*, args: tuple[str, ...], cwd: Path) -> None:
        """Record one pip installation.

        Args:
            args: pip command arguments.
            cwd: Component staging directory.

        """
        expect_equal(actual=cwd, expected=tmp_path)
        commands.append(args)
        if "--no-deps" in args:
            metadata: Path = (
                tmp_path
                / "python"
                / "playwright-1.64.1.dist-info"
                / "METADATA"
            )
            metadata.parent.mkdir(parents=True)
            _ = metadata.write_text(
                data=(
                    dedent(
                        text="""\
    Metadata-Version: 2.1
    Name: playwright
    Version: 1.64.1
    Requires-Dist: pyee<15,>=13
    Requires-Dist: greenlet<4,>=3.1.1
    """,
                    )
                ),
                encoding="utf-8",
            )

    builder: BundleBuilder = BundleBuilder(
        config=BundleConfig(),
        output=tmp_path / "out",
        target=BundleConstants.targets[f"linux-musl-{arch}"],
    )
    monkeypatch.setattr(target=builder, name="_run", value=record)
    private_call(
        owner=builder,
        name="_install_python",
        stage=tmp_path,
        spec=BundleConstants.components["playwright"],
    )
    expect_equal(actual=len(commands), expected=2)
    expect_in(member="--no-deps", container=commands[0])
    expect_in(member="playwright", container=commands[0])
    expect_true(condition="playwright" not in commands[1])
    expect_in(member="greenlet", container=commands[1])
    expect_in(member="pyee<15,>=13", container=commands[1])
    expect_in(member="greenlet<4,>=3.1.1", container=commands[1])
    expect_true(
        condition=any(
            arg.startswith("--platform=musllinux") for arg in commands[1]
        ),
    )
    expect_true(
        condition="browser"
        not in BundleConstants.target_unavailable.get(
            f"linux-musl-{arch}",
            (),
        ),
    )


@pytest.mark.parametrize(
    "interruption",
    [TimeoutExpired(cmd="docker", timeout=600), KeyboardInterrupt()],
)
def test_interrupted_build_removes_only_its_own_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: TimeoutExpired | KeyboardInterrupt,
) -> None:
    """Cancellation cannot orphan the APK installer container.

    Args:
        tmp_path: Isolated payload destination.
        monkeypatch: Replaces Docker with an interrupted process.
        interruption: Timeout or user cancellation to propagate unchanged.

    """
    commands: list[tuple[str, ...]] = []

    def interrupt(
        *,
        args: tuple[str, ...],
        check: bool,
        timeout: int,
        capture_output: bool = False,
    ) -> CompletedProcess[str]:
        """Interrupt installation and record the bounded cleanup command.

        Args:
            args: Docker command being invoked.
            check: Whether command failures must propagate.
            timeout: Required finite process timeout.
            capture_output: Whether cleanup output is captured.

        Returns:
            A successful cleanup command result.

        Raises:
            TimeoutExpired: For the scripted build timeout.
            KeyboardInterrupt: For the scripted cancellation.

        """
        commands.append(args)
        expect_true(condition=timeout > 0)
        if "run" in args:
            raise interruption
        expect_true(condition=not check and capture_output)
        return CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(target=musl_browser, name="run", value=interrupt)
    with pytest.raises(expected_exception=type(interruption)):
        musl_browser.install(
            stage=tmp_path,
            image="alpine@sha256:fixture",
            version="156.0.8078.79-r0",
            arch="arm64",
            revisions={},
        )
    container: str = commands[0][commands[0].index("--name") + 1]
    expect_true(condition=container.startswith("exactus-browser-"))
    expect_equal(
        actual=commands[1],
        expected=("docker", "rm", "--force", container),
    )


def test_node_bundles_its_own_runtime_libraries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node can start before any browser component has been extracted.

    Args:
        tmp_path: Isolated Node component staging root.
        monkeypatch: Replaces signed package installation with a fixture.

    """
    installed: list[tuple[str, ...]] = []

    def record_packages(
        *,
        root: Path,
        image: str,
        arch: Literal["amd64", "arm64"],
        packages: tuple[str, ...],
    ) -> None:
        """Record the independently packaged Node library closure.

        Args:
            root: Destination for runtime libraries.
            image: Pinned Alpine build image.
            arch: Native Node architecture.
            packages: Requested signed packages.

        """
        expect_equal(actual=root, expected=tmp_path / "node" / "runtime")
        expect_equal(actual=image, expected="alpine@sha256:fixture")
        expect_equal(actual=arch, expected="arm64")
        installed.append(packages)

    executable: Path = tmp_path / "node" / "bin" / "node"
    executable.parent.mkdir(parents=True)
    _ = executable.write_bytes(data=b"native-node")
    monkeypatch.setattr(
        target=musl_browser,
        name="install_packages",
        value=record_packages,
    )
    musl_browser.install_node(
        stage=tmp_path,
        image="alpine@sha256:fixture",
        arch="arm64",
    )
    expect_equal(actual=installed, expected=[("libgcc", "libstdc++")])
    expect_equal(
        actual=executable.with_name(name="node-real").read_bytes(),
        expected=b"native-node",
    )
    text: str = executable.read_text(encoding="utf-8")
    expect_in(member="runtime/usr/lib", container=text)
    expect_true(condition=str(object=tmp_path) not in text)
    expect_equal(actual=executable.stat().st_mode & 0o777, expected=0o755)
