# Copyright (c) 2026
"""Run the public completion example against the standalone grammar."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from exactus.packages.completion import protocol
from exactus.packages.completion.examples import run as completion_example
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    import pytest


def test_completion_example(monkeypatch: pytest.MonkeyPatch) -> None:
    """The standalone grammar provides both flag and pipeline candidates.

    Args:
        monkeypatch: Restore the example and protocol output streams.

    """
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=completion_example, name="stdout", value=stream)
    monkeypatch.setattr(target=protocol, name="stdout", value=stream)
    expect_equal(actual=completion_example.main(), expected=0)
    output: str = stream.getvalue()
    expect_in(member="--lints", container=output)
    expect_in(member="Pipeline names:", container=output)
    expect_in(member="unified", container=output)
