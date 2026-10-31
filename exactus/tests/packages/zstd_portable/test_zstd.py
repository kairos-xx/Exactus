# Copyright (c) 2026
"""Tests of the portable Zstandard CLI wrapper."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from re import compile as re_compile
from stat import S_IXUSR
from sys import modules
from typing import TYPE_CHECKING, Final, cast, final
from zipfile import ZipFile

if TYPE_CHECKING:
    from types import ModuleType
import pytest

from exactus.bundle import zstd_portable as packaged_zstd
from exactus.packages.zstd_portable import (
    OpenMode,
    Zstd,
    ZstdOptions,
    export_binary,
    export_package,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_equal,
    private_as,
    private_call,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        complete: Grouped module constant.
        read_chunk: Grouped module constant.
        payload: Grouped module constant.
        source_name: Grouped module constant.

    """

    complete: Final[float] = 100.0
    read_chunk: Final[int] = 64
    payload: Final[bytes] = b"exactus-offline-bundle\x00" * 4096 + bytes(
        range(256),
    )
    source_name: Final[str] = "exactus.packages.zstd_portable"


zstd_module: ModuleType = import_module(name=Constants.source_name)


@pytest.fixture(
    autouse=True,
    params=(Constants.source_name, packaged_zstd.__name__),
)
def wrapper_module(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise both distributed copies through identical public IO contracts.

    Args:
        request: Selected distribution module.
        monkeypatch: Restore imported helpers after each test.

    """
    selected: ModuleType = (
        packaged_zstd
        if request.param != Constants.source_name
        else import_module(name=Constants.source_name)
    )
    if selected is not zstd_module:
        monkeypatch.setattr(
            target=selected,
            name="__file__",
            value=zstd_module.__file__,
        )
    name: str
    for name in (
        "OpenMode",
        "Zstd",
        "ZstdOptions",
        "export_binary",
        "export_package",
    ):
        monkeypatch.setattr(
            target=modules[__name__],
            name=name,
            value=getattr(selected, name),
        )
    monkeypatch.setattr(
        target=modules[__name__],
        name="zstd_module",
        value=selected,
    )


@pytest.mark.parametrize(
    ("os_name", "machine", "expected"),
    [
        ("darwin", "amd64", ("darwin", "x86_64")),
        ("linux", "aarch64", ("linux", "arm64")),
        ("windows", "i686", ("windows", "x86")),
    ],
)
def test_platform_normalization(
    os_name: str,
    machine: str,
    expected: tuple[str, str],
) -> None:
    """Normalize common architecture aliases in every distributed wrapper.

    Args:
        os_name: Input operating-system name.
        machine: Input architecture name.
        expected: Normalized target key.

    """
    expect_equal(
        actual=private_call(
            owner=zstd_module,
            name="_normalize",
            os_name=os_name,
            machine=machine,
        ),
        expected=expected,
    )


def test_platform_normalization_rejects_unknown_values() -> None:
    """Reject unsupported CPUs and operating systems explicitly."""
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported CPU",
    ):
        _ = private_call(
            owner=zstd_module,
            name="_normalize",
            os_name="linux",
            machine="riscv64",
        )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported OS",
    ):
        _ = private_call(
            owner=zstd_module,
            name="_normalize",
            os_name="plan9",
            machine="amd64",
        )


def _require(*, condition: bool, msg: str) -> None:
    """Fail the test when ``condition`` is false.

    Args:
        condition: Expression that must hold.
        msg: Failure detail.

    Raises:
        AssertionError: When ``condition`` is false.

    """
    if not condition:
        raise AssertionError(msg)


def _roundtrip(*, target: Path, payload: bytes = Constants.payload) -> None:
    """Compress then decompress ``payload`` through real ``zstd``.

    Args:
        target: Destination ``.zst`` path.
        payload: Bytes to compress and verify.

    """
    with Zstd(file=target, options=ZstdOptions(level=3)) as writer:
        _ = writer.write(payload)
    _require(condition=target.is_file(), msg="Compressed output missing.")
    restored: bytes = b""
    with Zstd(file=target, mode="r") as reader:
        restored = reader.read()
    expect_equal(actual=restored, expected=payload)


def test_options_validation(tmp_path: Path) -> None:
    """Reject out-of-range modes and option values.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "payload.zst"
    for mode in ("x", "a", "rw"):
        with pytest.raises(
            expected_exception=ValueError,
            match="Unsupported mode",
        ):
            Zstd(file=target, mode=cast(typ="OpenMode", val=mode))
    for options in (
        ZstdOptions(level=0),
        ZstdOptions(level=23),
        ZstdOptions(threads=-1),
        ZstdOptions(expected_size=-1),
    ):
        with pytest.raises(expected_exception=ValueError, match="must be"):
            Zstd(file=target, options=options)
    instance: Zstd = Zstd(file=target, mode="rb")
    _require(condition=instance.readable(), msg="rb must be readable.")
    _require(condition=not instance.writable(), msg="rb must not be writable.")
    _require(
        condition=instance.progress is None,
        msg="Unopened reader must report unknown progress.",
    )
    other: Zstd = Zstd(file=target, mode="wb")
    _require(condition=other.writable(), msg="wb must be writable.")
    _require(condition=not other.readable(), msg="wb must not be readable.")


def test_roundtrip_and_counters(tmp_path: Path) -> None:
    """Compress and decompress through real ``zstd`` end to end.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "nested" / "payload.zst"
    seen: list[tuple[float | None, str]] = []

    def _progress(percent: float | None, status: str) -> None:
        """Record one progress emission.

        Args:
            percent: Reported completion percent.
            status: Reported status label.

        """
        seen.append((percent, status))

    writer: Zstd = Zstd(
        file=target,
        options=ZstdOptions(
            level=1,
            threads=1,
            progress=_progress,
            expected_size=len(Constants.payload),
        ),
        cache=tmp_path / "cli-cache",
    )
    _require(condition=not writer.closed, msg="Stream starts open.")
    writer.open()
    _require(condition=writer.progress == 0.0, msg="No bytes written yet.")
    expect_equal(
        actual=writer.write(data=Constants.payload[:100]),
        expected=100,
    )
    writer.flush()
    _ = writer.write(data=bytearray(Constants.payload[100:]))
    _require(
        condition=writer.progress is not None and writer.progress > 0.0,
        msg="Expected progress after writes.",
    )
    writer.close()
    _require(condition=writer.closed, msg="Stream must be closed.")
    expect_equal(actual=writer.bytes_written, expected=len(Constants.payload))
    statuses: list[str] = [status for _, status in seen]
    expect_in(member="started", container=statuses)
    expect_in(member="compressing", container=statuses)
    expect_in(member="complete", container=statuses)
    _require(
        condition=seen[-1][0] == Constants.complete,
        msg="Completion must report 100 percent.",
    )
    head: bytearray = bytearray(10)
    tail: bytearray = bytearray(len(Constants.payload) - 10)
    with Zstd(file=target, mode="rb") as reader:
        expect_equal(actual=reader.readinto(buffer=head), expected=10)
        expect_equal(
            actual=reader.readinto(buffer=tail),
            expected=len(Constants.payload) - 10,
        )
        expect_equal(actual=reader.read(), expected=b"")
    expect_equal(actual=bytes(head + tail), expected=Constants.payload)
    _require(
        condition=reader.bytes_read == len(Constants.payload),
        msg="Decompressed byte counter mismatch.",
    )
    _require(
        condition=reader.progress == Constants.complete,
        msg="Fully consumed input must report 100 percent.",
    )
    writer.close()
    _require(condition=writer.closed, msg="Second close is a no-op.")


def test_zero_expected_size(tmp_path: Path) -> None:
    """Report full progress when the expected size is zero.

    Args:
        tmp_path: Per-test temporary directory.

    """
    writer: Zstd = Zstd(
        file=tmp_path / "empty.zst",
        options=ZstdOptions(expected_size=0),
    )
    _require(
        condition=writer.progress == Constants.complete,
        msg="Zero-length input must report complete.",
    )
    writer.close()


def test_open_guards(tmp_path: Path) -> None:
    """Reject double-open and open-after-close.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "payload.zst"
    writer: Zstd = Zstd(file=target)
    writer.open()
    with pytest.raises(expected_exception=RuntimeError, match="already open"):
        writer.open()
    writer.close()
    with pytest.raises(expected_exception=RuntimeError, match="closed"):
        writer.open()


def test_stream_method_guards(tmp_path: Path) -> None:
    """Reject stream calls that violate mode or lifecycle.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "payload.zst"
    writer: Zstd = Zstd(file=target)
    with pytest.raises(expected_exception=RuntimeError, match="not open"):
        _ = writer.write(data=b"x")
    with pytest.raises(expected_exception=RuntimeError, match="not open"):
        writer.flush()
    with pytest.raises(expected_exception=RuntimeError, match="not readable"):
        _ = writer.readinto(buffer=bytearray(4))
    reader: Zstd = Zstd(file=target, mode="r")
    with pytest.raises(expected_exception=RuntimeError, match="not writable"):
        _ = reader.write(data=b"x")
    with pytest.raises(expected_exception=RuntimeError, match="not writable"):
        reader.flush()
    _roundtrip(target=target, payload=b"short")
    writer.open()
    with pytest.raises(expected_exception=RuntimeError, match="not readable"):
        _ = writer.read()
    writer.close()


def test_missing_compressed_input(tmp_path: Path) -> None:
    """Raise ``FileNotFoundError`` for absent compressed input.

    Args:
        tmp_path: Per-test temporary directory.

    """
    reader: Zstd = Zstd(file=tmp_path / "absent.zst", mode="r")
    with pytest.raises(expected_exception=FileNotFoundError):
        reader.open()
    existing: Path = tmp_path / "existing.zst"
    existing.write_bytes(data=b"x")
    with pytest.raises(expected_exception=FileExistsError):
        Zstd(file=existing, overwrite=False).open()


def test_partial_read_close(tmp_path: Path) -> None:
    """Terminate the decompressor on early caller-driven close.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "payload.zst"
    _roundtrip(target=target)
    reader: Zstd = Zstd(file=target, mode="r")
    reader.open()
    expect_equal(
        actual=len(reader.read(size=Constants.read_chunk)),
        expected=Constants.read_chunk,
    )
    reader.close()
    _require(condition=reader.closed, msg="Stream must be closed.")
    _require(
        condition=reader.bytes_read == Constants.read_chunk,
        msg="Counter must stop at the partial read.",
    )


def test_expected_size_mismatch(tmp_path: Path) -> None:
    """Fail close when written bytes differ from ``expected_size``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    writer: Zstd = Zstd(
        file=tmp_path / "payload.zst",
        options=ZstdOptions(expected_size=len(Constants.payload) + 1),
    )
    writer.open()
    _ = writer.write(data=Constants.payload)
    with pytest.raises(
        expected_exception=RuntimeError,
        match=re_compile(pattern="Expected \\d+ bytes"),
    ):
        writer.close()


def test_corrupt_stream_fails(tmp_path: Path) -> None:
    """Fail close when the decompressor exits nonzero.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "broken.zst"
    target.write_bytes(data=b"not-a-zstandard-frame" * 4096)
    reader: Zstd = Zstd(file=target, mode="r")
    reader.open()
    _ = reader.read()
    with pytest.raises(expected_exception=RuntimeError, match="zstd failed"):
        reader.close()


def test_context_exit_failures(tmp_path: Path) -> None:
    """Propagate close failures and preserve active exceptions.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "broken.zst"
    target.write_bytes(data=b"still-not-a-frame")
    with (
        pytest.raises(expected_exception=RuntimeError),
        Zstd(file=target, mode="r") as reader,
    ):
        _ = reader.read()
    reader: Zstd = Zstd(file=target, mode="r")
    reader.open()
    _ = reader.read()
    with pytest.raises(expected_exception=RuntimeError):
        private_call(
            owner=reader,
            name="__exit__",
            _exc_type=None,
            _exc_value=None,
            _traceback=None,
        )
    reader = Zstd(file=target, mode="r")
    reader.open()
    _ = reader.read()
    propagated: object = private_call(
        owner=reader,
        name="__exit__",
        _exc_type=AssertionError,
        _exc_value=AssertionError(),
        _traceback=None,
    )
    expect_equal(actual=propagated, expected=False)


def test_executable_cache(tmp_path: Path) -> None:
    """Extract the native binary once and reuse the digest cache.

    Args:
        tmp_path: Per-test temporary directory.

    """
    cache: Path = tmp_path / "cache"
    for _ in range(2):
        executable: object = private_call(
            owner=Zstd(file=tmp_path / "p.zst", cache=cache),
            name="_get_executable",
        )
        _require(
            condition=isinstance(executable, Path),
            msg="Executable path must be a Path.",
        )
        path: Path = Path(str(object=executable))
        _require(condition=path.is_file(), msg="Extracted executable missing.")
        _require(
            condition=bool(path.stat().st_mode & S_IXUSR),
            msg="Extracted executable lacks the user-exec bit.",
        )
        _require(
            condition=(path.parent / ".sha256").is_file(),
            msg="Digest marker missing.",
        )


def test_unsupported_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject unknown CPU, OS, and target combinations.

    Args:
        monkeypatch: Fixture patching platform probes.

    """
    monkeypatch.setattr(
        target=zstd_module,
        name="machine",
        value=lambda: "mips64",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported CPU",
    ):
        private_call(owner=Zstd(file="x.zst"), name="_get_executable")
    monkeypatch.setattr(
        target=zstd_module,
        name="machine",
        value=lambda: "x86_64",
    )
    monkeypatch.setattr(
        target=zstd_module,
        name="system",
        value=lambda: "Haiku",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported OS",
    ):
        private_call(owner=Zstd(file="x.zst"), name="_get_executable")
    monkeypatch.setattr(
        target=zstd_module,
        name="system",
        value=lambda: "Darwin",
    )
    targets: dict[tuple[str, str], tuple[str, str]] = cast(
        typ="dict[tuple[str, str], tuple[str, str]]",
        val=private_as(owner=zstd_module.Constants, name="targets", kind=dict),
    )
    monkeypatch.setitem(
        dic=targets,
        name=("darwin", "x86_64"),
        value=("missing-payload.zip", "zstd"),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Missing native payload",
    ):
        private_call(owner=Zstd(file="x.zst"), name="_get_executable")
    monkeypatch.delitem(dic=targets, name=("darwin", "x86_64"))
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported platform",
    ):
        private_call(owner=Zstd(file="x.zst"), name="_get_executable")


def test_invalid_payload_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject malformed or overfilled native payload archives.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Fixture retargeting the payload root.

    """
    package: Path = tmp_path / "zstd_portable"
    payload_dir: Path = package / "bin"
    payload_dir.mkdir(parents=True)
    monkeypatch.setattr(
        target=zstd_module,
        name="__file__",
        value=str(object=package / "__init__.py"),
    )
    monkeypatch.setattr(
        target=Zstd,
        name="_target",
        value=staticmethod(lambda: ("linux", "x86_64")),
    )
    archive: Path = payload_dir / "linux-x86_64.zip"
    archive.write_bytes(data=b"definitely not a zip")
    owner: Zstd = Zstd(file="x.zst", cache=tmp_path / "cache")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Invalid native payload",
    ):
        private_call(owner=owner, name="_get_executable")
    with ZipFile(file=archive, mode="w") as zipped:
        zipped.writestr(zinfo_or_arcname="zstd", data=b"bin")
        zipped.writestr(zinfo_or_arcname="extra.txt", data=b"no")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="must contain only",
    ):
        private_call(owner=owner, name="_get_executable")


def test_feed_and_stderr_without_process(tmp_path: Path) -> None:
    """Return early when feed and drain helpers lack a process.

    Args:
        tmp_path: Per-test temporary directory.

    """
    instance: Zstd = Zstd(file=tmp_path / "p.zst", mode="r")
    private_call(owner=instance, name="_feed_compressed_input")
    private_call(owner=instance, name="_read_stderr")
    expect_equal(
        actual=private_call(owner=instance, name="_error_message"),
        expected="zstd failed.",
    )


def test_stderr_details_in_failure(tmp_path: Path) -> None:
    """Surface child stderr inside the close failure message.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "broken.zst"
    target.write_bytes(data=b"not-a-zstandard-frame" * 2048)
    reader: Zstd = Zstd(file=target, mode="r")
    reader.open()
    _ = reader.read()
    with pytest.raises(expected_exception=RuntimeError) as captured:
        reader.close()
    expect_not_equal(actual=str(object=captured.value), expected="")


def test_large_corrupt_input_feeds_until_pipe_breaks(tmp_path: Path) -> None:
    """Report input-streaming failure on a dead decompressor.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "huge-broken.zst"
    target.write_bytes(data=b"0" * (8 * 1024 * 1024))
    reader: Zstd = Zstd(file=target, mode="r")
    reader.open()
    _ = reader.read()
    with pytest.raises(expected_exception=RuntimeError):
        reader.close()


def test_export_binary(tmp_path: Path) -> None:
    """Stage a native CLI binary for an explicit target platform.

    Args:
        tmp_path: Per-test temporary directory.

    """
    staged: Path = export_binary(
        os_name="linux",
        machine="amd64",
        target=tmp_path / "linux",
    )
    expect_equal(actual=staged.name, expected="zstd")
    _require(condition=staged.is_file(), msg="Binary must be staged.")
    _require(
        condition=staged.stat().st_mode & S_IXUSR != 0,
        msg="Binary must be executable.",
    )
    windows: Path = export_binary(
        os_name="windows",
        machine="x86_64",
        target=tmp_path / "windows",
    )
    expect_equal(actual=windows.name, expected="zstd.exe")
    _require(condition=windows.is_file(), msg="Windows binary must be staged.")


def test_export_binary_rejects_unsupported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject platforms without a normalized payload entry.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Fixture retargeting a payload entry.

    """
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported OS",
    ):
        export_binary(os_name="haiku", machine="amd64", target=tmp_path / "os")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported CPU",
    ):
        export_binary(
            os_name="linux",
            machine="mips64",
            target=tmp_path / "cpu",
        )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Unsupported platform",
    ):
        export_binary(
            os_name="linux",
            machine="x86",
            target=tmp_path / "target",
        )
    targets: dict[tuple[str, str], tuple[str, str]] = cast(
        typ="dict[tuple[str, str], tuple[str, str]]",
        val=private_as(owner=zstd_module.Constants, name="targets", kind=dict),
    )
    monkeypatch.setitem(
        dic=targets,
        name=("windows", "arm64"),
        value=("missing-payload.zip", "zstd.exe"),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="Missing native payload",
    ):
        export_binary(
            os_name="windows",
            machine="arm64",
            target=tmp_path / "missing",
        )


@pytest.mark.parametrize(
    ("os_name", "machine"),
    [("linux", "x86_64"), ("darwin", "arm64"), ("windows", "amd64")],
)
def test_exported_package_readmes(
    tmp_path: Path,
    os_name: str,
    machine: str,
) -> None:
    """Document the exported wrapper and its selected native payload.

    Args:
        tmp_path: Export destination.
        os_name: Target operating system.
        machine: Target architecture.

    """
    package: Path = export_package(
        os_name=os_name,
        machine=machine,
        target=tmp_path,
    )
    expect_in(
        member="bin/README.md",
        container=(package / "README.md").read_text(),
    )
    native: Path = next((package / "bin").glob(pattern="*.zip"))
    expect_in(
        member=native.name,
        container=(package / "bin" / "README.md").read_text(),
    )
