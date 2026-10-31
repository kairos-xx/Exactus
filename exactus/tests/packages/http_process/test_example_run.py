# Copyright (c) 2026
"""Cover the bundled ``http_process`` example entry point."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import TYPE_CHECKING, Final, final

from exactus.packages import http_process as http_package
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    import pytest


@final
class Constants:
    """Group module-level constants.

    Attributes:
        example: Grouped module constant.

    """

    example: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "http_process"
        / "examples"
        / "run.py"
    )


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry with a stub runner.

    Args:
        monkeypatch: Pytest patching helper.

    """
    events: list[str] = []
    output: StringIO = StringIO()

    class HttpProcessStub:
        """Stand-in for the real ``HttpProcess`` runner."""

        def __init__(self, *, command: list[str]) -> None:
            """Record the requested server command.

            Args:
                command: Server command tokens.

            """
            events.append(f"init:{command[0]}")

        @staticmethod
        def start() -> None:
            """Record the runner startup."""
            events.append("start")

        @staticmethod
        def wait_for_http() -> tuple[str, ...]:
            """Return one synthetic discovered server.

            Returns:
                A single synthetic server description.

            """
            events.append("wait")
            return ("server:one",)

        @staticmethod
        def stop() -> None:
            """Record the runner shutdown."""
            events.append("stop")

    monkeypatch.setattr(
        target=http_package,
        name="HttpProcess",
        value=HttpProcessStub,
    )
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(
        actual=events,
        expected=[
            f"init:{modules['sys'].executable}",
            "start",
            "wait",
            "stop",
        ],
    )
    expect_in(member="server:one", container=output.getvalue())
