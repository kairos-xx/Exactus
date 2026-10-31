# Copyright (c) 2026
"""The ``examples/example.py`` demo round-trips a scratch binary."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.zstd_portable.examples import example
from exactus.tests.common.support import expect_equal, expect_in, expect_true

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_progress_renders_status_and_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The progress sink writes the label and formatted percent.

    Args:
        monkeypatch: Redirects the example's bound output stream.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=example, name="stdout", value=buffer)
    example.progress(percent=None, status="loading")
    example.progress(percent=42.5, status="compressing")
    output: str = buffer.getvalue()
    expect_in(member="loading", container=output)
    expect_in(member="compressing", container=output)
    expect_in(member="42.50%", container=output)


def test_create_binary_writes_configured_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source writer emits the exact size in chunk-sized writes.

    Args:
        tmp_path: Isolated scratch destination.
        monkeypatch: Shrinks the demo's payload sizes.

    """
    monkeypatch.setattr(
        target=example.Constants,
        name="source_size",
        value=2_500_000,
    )
    monkeypatch.setattr(
        target=example.Constants,
        name="chunk_size",
        value=1_000_000,
    )
    target: Path = tmp_path / "sample.bin"
    example.create_binary(target=target)
    expect_equal(actual=target.stat().st_size, expected=2_500_000)


def test_example_round_trips_scratch_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo compresses and restores a matching payload.

    Args:
        tmp_path: Isolated working directory for the demo files.
        monkeypatch: Shrinks the payload and captures the transcript.

    """
    monkeypatch.setattr(
        target=example.Constants,
        name="source_size",
        value=2_500_000,
    )
    monkeypatch.setattr(
        target=example.Constants,
        name="chunk_size",
        value=1_000_000,
    )
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=example, name="stdout", value=buffer)
    example.main(directory=tmp_path)
    source: Path = tmp_path / "example.bin"
    restored: Path = tmp_path / "example.restored.bin"
    expect_true(condition=(tmp_path / "example.bin.zst").is_file())
    expect_equal(actual=restored.read_bytes(), expected=source.read_bytes())
    expect_in(
        member="Round-trip verification: PASS",
        container=buffer.getvalue(),
    )
