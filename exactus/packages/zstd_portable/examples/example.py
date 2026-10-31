"""Binary streaming compression/decompression progress demo."""

from os import urandom
from pathlib import Path
from sys import stdout
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from exactus.packages.zstd_portable import Zstd, ZstdOptions
else:
    try:
        from zstd_portable import Zstd, ZstdOptions
    except ImportError:
        from exactus.packages.zstd_portable import Zstd, ZstdOptions


@final
class Constants:
    """Group module-level constants.

    Attributes:
        mib: Grouped module constant.
        source_size: Grouped module constant.
        chunk_size: Grouped module constant.

    """

    mib: Final[int] = 1024 * 1024
    source_size: Final[int] = 500 * mib
    chunk_size: Final[int] = 1 * mib


def progress(percent: float | None, status: str) -> None:
    """Display Zstandard operation progress.

    Args:
        percent: Completion percent, or ``None`` when unknown.
        status: Short status label describing the current operation.

    """
    if percent is None:
        stdout.write(f"\r{status:<16}")
    else:
        stdout.write(f"\r{status:<16} {percent:6.2f}%")
    stdout.flush()


def create_binary(target: Path) -> None:
    """Create the configured binary file without a large allocation.

    Args:
        target: File created in one-megabyte random chunks.

    """
    remaining: int = Constants.source_size
    with target.open(mode="wb") as output:
        while remaining:
            size: int = min(Constants.chunk_size, remaining)
            output.write(urandom(size))
            remaining -= size


def _round_trip(*, directory: Path) -> None:
    """Compress, restore and verify a scratch binary in ``directory``.

    Args:
        directory: Writable scratch directory receiving the demo files.

    Raises:
        RuntimeError: When the restored data differs from the source.

    """
    source: Path = directory / "example.bin"
    compressed: Path = directory / "example.bin.zst"
    restored: Path = directory / "example.restored.bin"
    stdout.write(
        f"Creating exactly {Constants.source_size // Constants.mib} MiB of"
        " binary data...\n",
    )
    create_binary(target=source)
    stdout.write(f"Source: {source} ({source.stat().st_size:,} bytes)\n\n")
    options: ZstdOptions = ZstdOptions(
        expected_size=source.stat().st_size,
        progress=progress,
    )
    with (
        source.open(mode="rb") as input_stream,
        Zstd(file=compressed, mode="w", options=options) as archive,
    ):
        while chunk := input_stream.read(Constants.chunk_size):
            archive.write(chunk)
    stdout.write("\n")
    stdout.write(
        f"Compressed: {compressed} ({compressed.stat().st_size:,} bytes)\n\n",
    )
    with (
        Zstd(
            file=compressed,
            mode="r",
            options=ZstdOptions(progress=progress),
        ) as archive,
        restored.open(mode="wb") as output,
    ):
        while chunk := archive.read(size=Constants.chunk_size):
            output.write(chunk)
    stdout.write("\n")
    stdout.write(f"Restored: {restored} ({restored.stat().st_size:,} bytes)\n")
    if source.read_bytes() != restored.read_bytes():
        msg: str = "Round-trip verification failed."
        raise RuntimeError(msg)
    stdout.write("Round-trip verification: PASS\n")


def main(*, directory: Path | None = None) -> None:
    """Run a binary Zstandard round-trip with live progress.

    Args:
        directory: Scratch directory for the demo files; a fresh
            temporary directory is used when omitted so invocations
            never litter the caller's working directory.

    """
    if directory is not None:
        _round_trip(directory=directory)
        return
    with TemporaryDirectory() as scratch:
        _round_trip(directory=Path(scratch))


if __name__ == "__main__":
    main()
