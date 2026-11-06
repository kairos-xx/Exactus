"""Stage relocatable, signed Alpine Chromium packages for musl targets."""

from __future__ import annotations

from contextlib import suppress
from os.path import relpath
from pathlib import Path
from subprocess import TimeoutExpired, run
from textwrap import dedent
from typing import TYPE_CHECKING, Final, Literal, final
from uuid import uuid4

if TYPE_CHECKING:
    from typing import BinaryIO


@final
class Constants:
    """Build inputs and relocatable launch settings.

    Attributes:
        install: APK install command run inside the build image.
        launcher: Chromium launcher shell script template.
        node_launcher: Node launcher resolving symlinks into the
            private runtime before exec.
        fonts: Fontconfig configuration for the bundled runtime.

    """

    install: Final[str] = (
        "apk --root /payload --initdb --no-scripts "
        "--keys-dir /etc/apk/keys "
        "--repositories-file /etc/apk/repositories add --no-cache "
        '"$@"; apk --root /payload info -v > /payload/packages.txt'
    )
    launcher: Final[str] = dedent(
        text="""\
    #!/bin/sh
    set -eu
    root=$(CDPATH= cd -- "$(dirname -- "$0")/{relative}" && pwd)
    export LD_LIBRARY_PATH="$root/usr/lib:$root/lib:$root/usr/lib/pulseaudio"
    export FONTCONFIG_FILE="$root/fonts.conf"
    export XDG_DATA_DIRS="$root/usr/share"
    exec "$root/{binary}" "$@"
    """,
    )
    node_launcher: Final[str] = dedent(
        text="""\
    #!/bin/sh
    set -eu
    entry=$0
    while [ -L "$entry" ]; do
      target=$(readlink -- "$entry")
      case "$target" in
        /*) entry=$target ;;
        *) entry=$(dirname -- "$entry")/$target ;;
      esac
    done
    base=$(CDPATH= cd -- "$(dirname -- "$entry")/.." && pwd)
    export LD_LIBRARY_PATH="$base/runtime/usr/lib:$base/runtime/lib"
    exec "$base/bin/node-real" "$@"
    """,
    )
    fonts: Final[str] = dedent(
        text=(
            """\
    <?xml version="1.0"?>
    <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
    <fontconfig><dir prefix="relative">usr/share/fonts</dir><cachedir \
prefix="xdg">fontconfig</cachedir></fontconfig>
    """
        ),
    )


def install_packages(
    *,
    root: Path,
    image: str,
    arch: Literal["amd64", "arm64"],
    packages: tuple[str, ...],
) -> None:
    """Install signature-verified APKs into a relocatable private root.

    Args:
        root: Destination for packages and their dependency closure.
        image: Digest-pinned Alpine build image.
        arch: Target CPU architecture.
        packages: APK package specifications passed without shell expansion.

    Raises:
        subprocess.CalledProcessError: When signed package installation fails.
        subprocess.TimeoutExpired: When package installation exceeds its limit.

    """
    root.mkdir(parents=True)
    container: str = f"exactus-browser-{uuid4().hex}"
    try:
        _ = run(
            args=(
                "docker",
                "run",
                "--rm",
                "--name",
                container,
                "--platform",
                f"linux/{arch}",
                "--mount",
                f"type=bind,source={root.resolve()},target=/payload",
                image,
                "sh",
                "-ec",
                Constants.install,
                "install-packages",
                *packages,
            ),
            check=True,
            timeout=600,
        )
    except (TimeoutExpired, KeyboardInterrupt):
        with suppress(OSError, TimeoutExpired):
            _ = run(
                args=("docker", "rm", "--force", container),
                check=False,
                capture_output=True,
                timeout=30,
            )
        raise
    path: Path
    for path in root.rglob(pattern="*"):
        if path.is_symlink() and Path(path.readlink()).is_absolute():
            target: Path = root / str(object=path.readlink()).lstrip("/")
            path.unlink()
            path.symlink_to(target=relpath(path=target, start=path.parent))


def install_node(
    *,
    stage: Path,
    image: str,
    arch: Literal["amd64", "arm64"],
) -> None:
    """Bundle Node's C++ runtime independently of the browser component.

    Args:
        stage: Node component staging root containing ``node/bin/node``.
        image: Digest-pinned Alpine build image.
        arch: Native Node architecture.

    """
    node: Path = stage / "node"
    install_packages(
        root=node / "runtime",
        image=image,
        arch=arch,
        packages=("libgcc", "libstdc++"),
    )
    executable: Path = node / "bin" / "node"
    _ = executable.rename(target=executable.with_name(name="node-real"))
    _ = executable.write_text(data=Constants.node_launcher, encoding="utf-8")
    executable.chmod(mode=0o755)


def install(
    *,
    stage: Path,
    image: str,
    version: str,
    arch: Literal["amd64", "arm64"],
    revisions: dict[str, str],
) -> None:
    """Install signed packages and expose Playwright's expected entry points.

    Args:
        stage: Chromium component staging root.
        image: Digest-pinned Alpine build image.
        version: Exact Chromium APK version, shared with its headless shell.
        arch: Native target architecture passed to Docker.
        revisions: Browser directory identities from the Playwright catalog.

    Raises:
        ValueError: When a packaged executable has the wrong target ABI.
        subprocess.CalledProcessError: When signed package installation fails.
        subprocess.TimeoutExpired: When package installation exceeds its limit.

    """
    root: Path = stage / "playwright-browsers"
    native: Path = root / "native"
    install_packages(
        root=native,
        image=image,
        arch=arch,
        packages=(
            f"chromium={version}",
            f"chromium-headless-shell={version}",
            "ffmpeg",
            "font-dejavu",
        ),
    )
    _ = (native / "fonts.conf").write_text(
        data=Constants.fonts,
        encoding="utf-8",
    )
    platform: str = "linux64" if arch == "amd64" else "linux-arm64"
    descriptors: dict[str, tuple[str, str]] = {
        "chromium": (f"chrome-{platform}/chrome", "usr/lib/chromium/chrome"),
        "chromium-headless-shell": (
            f"chrome-headless-shell-{platform}/chrome-headless-shell",
            "usr/lib/chromium/chromium-headless-shell",
        ),
        "ffmpeg": ("ffmpeg-linux", "usr/bin/ffmpeg"),
    }
    name: str
    relative: str
    binary: str
    for name, (relative, binary) in descriptors.items():
        executable: Path = native / binary
        stream: BinaryIO
        with executable.open(mode="rb") as stream:
            header: bytes = stream.read(20)
        machine: int = 62 if arch == "amd64" else 183
        if (
            header[:6] != b"\x7fELF\x02\x01"
            or int.from_bytes(bytes=header[18:20], byteorder="little")
            != machine
        ):
            msg: str = f"Wrong {arch} browser ABI: {binary}"
            raise ValueError(msg)
        launcher: Path = (
            root / f"{name.replace('-', '_')}-{revisions[name]}" / relative
        )
        launcher.parent.mkdir(parents=True, exist_ok=True)
        _ = launcher.write_text(
            data=Constants.launcher.format(
                relative=relpath(path=native, start=launcher.parent),
                binary=binary,
            ),
            encoding="utf-8",
        )
        launcher.chmod(mode=0o755)
        (
            root
            / f"{name.replace('-', '_')}-{revisions[name]}"
            / "INSTALLATION_COMPLETE"
        ).touch()
