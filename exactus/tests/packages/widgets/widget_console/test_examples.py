# Copyright (c) 2026
"""Coverage for the console widget demo server launcher."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_module
from typing import Final, final

import pytest

from exactus.packages.server import local
from exactus.packages.widgets.widget_console.examples import run
from exactus.tests.common.support import expect_equal, expect_in, expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        assets: Grouped module constant.

    """

    root: Final[Path] = Path(run.__file__).resolve().parents[3]
    assets: Final[tuple[str, ...]] = (
        "widgets/widget_console/examples/web/index.html",
        "widgets/widget_console/examples/web/code.js",
        "widgets/widget_console/examples/web/demo.css",
        "widgets/widget_console/index.js",
        "widgets/widget_console/style.css",
    )


def _never_ready(**_options: object) -> bool:
    """Report an unavailable server.

    Args:
        **_options: Readiness arguments.

    Returns:
        False for the simulated startup failure.

    """
    return False


def _always_ready(**_options: object) -> bool:
    """Report a ready server.

    Args:
        **_options: Readiness arguments.

    Returns:
        True for the simulated healthy startup.

    """
    return True


def _no_reuse(**_options: object) -> None:
    """Simulate a missing recorded server.

    Args:
        **_options: Reuse lookup arguments.

    """
    return


def _fake_spawn(**_options: object) -> tuple[int, str, bool]:
    """Simulate a freshly spawned server.

    Args:
        **_options: Spawn arguments.

    Returns:
        A fabricated ``(pid, origin, reused)`` triple.

    """
    return (4321, "http://127.0.0.1:1/", False)


def test_demo_assets_exist() -> None:
    """Every file the demo page loads is present beside the launcher."""
    for asset in Constants.assets:
        expect_true(condition=(Constants.root / asset).is_file())


def test_start_demo_reuses_a_recorded_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded server short-circuits the spawn path.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """

    def _recorded(**_options: object) -> tuple[int, int]:
        """Report an already-running demo server.

        Args:
            **_options: Reuse lookup arguments.

        Returns:
            A fabricated ``(pid, port)`` pair.

        """
        return (1234, 5678)

    monkeypatch.setattr(target=local, name="reuse_server", value=_recorded)
    expect_equal(
        actual=run.start_demo(log=tmp_path / "demo.log"),
        expected=(
            "http://127.0.0.1:5678/widgets/widget_console/examples/web/index.h"
            "tml"
        ),
    )


def test_start_demo_spawns_and_waits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh spawn waits for readiness and returns the demo URL.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=local, name="reuse_server", value=_no_reuse)
    monkeypatch.setattr(target=local, name="serve", value=_fake_spawn)
    monkeypatch.setattr(target=local, name="wait_ready", value=_always_ready)
    expect_equal(
        actual=run.start_demo(log=tmp_path / "demo.log"),
        expected="http://127.0.0.1:1/widgets/widget_console/examples/web/index.html",
    )


def test_start_demo_replaces_unready_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminate and clear a spawned server that never answers.

    Args:
        tmp_path: Per-test scratch directory.
        monkeypatch: Pytest patching helper.

    """
    terminated: list[int] = []
    cleared: list[Path] = []

    def _terminate(*, pid: int) -> None:
        """Record a terminated process id.

        Args:
            pid: Process handed to the killer.

        """
        terminated.append(pid)

    def _clear(*, path: Path) -> None:
        """Record a cleared server state.

        Args:
            path: Served root directory.

        """
        cleared.append(path)

    monkeypatch.setattr(target=local, name="reuse_server", value=_no_reuse)
    monkeypatch.setattr(target=local, name="serve", value=_fake_spawn)
    monkeypatch.setattr(target=local, name="wait_ready", value=_never_ready)
    monkeypatch.setattr(target=local, name="clear_server_state", value=_clear)
    monkeypatch.setattr(target=run, name="terminate_tree", value=_terminate)
    with pytest.raises(expected_exception=RuntimeError, match="ready"):
        run.start_demo(log=tmp_path / "demo.log")
    expect_equal(actual=terminated, expected=[4321])
    expect_equal(actual=cleared, expected=[Constants.root])


def test_main_prints_url_and_opens_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print the demo URL and hand it to the system browser.

    Args:
        monkeypatch: Pytest patching helper.

    """
    opened: list[str] = []
    sink: StringIO = StringIO()

    def _fixed_demo(**_options: object) -> str:
        """Simulate a ready demo server.

        Args:
            **_options: Launch arguments.

        Returns:
            The fixed demo URL.

        """
        return (
            "http://127.0.0.1:9/widgets/widget_console/examples/web/index.html"
        )

    class _Session:
        """Record a browser launch and close immediately."""

        @staticmethod
        def open(*, url: str) -> None:
            """Record the URL handed to the browser.

            Args:
                url: URL handed to the browser.

            """
            opened.append(url)

        @staticmethod
        def wait_closed(*, timeout: float | None = None) -> bool:
            """Simulate the user closing the browser.

            Args:
                timeout: Maximum wait, ignored by the fake.

            Returns:
                True because the fake browser is already closed.

            """
            return timeout is None

        def close(self) -> None:
            """Release nothing; the fake owns no browser."""

    monkeypatch.setattr(target=run, name="start_demo", value=_fixed_demo)
    monkeypatch.setattr(target=run, name="BrowserSession", value=_Session)
    monkeypatch.setattr(target=run, name="stdout", value=sink)
    expect_equal(actual=run.main(), expected=0)
    expect_equal(
        actual=opened,
        expected=[
            (
                "http://127.0.0.1:9/widgets/widget_console/examples/web/index."
                "html"
            ),
        ],
    )
    expect_in(
        member="http://127.0.0.1:9/widgets/widget_console/examples/web/index.html",
        container=sink.getvalue(),
    )


def test_module_entrypoint_invokes_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the examples module forwards to ``run.main``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []

    def _main() -> int:
        """Record the entrypoint invocation.

        Returns:
            Zero for the simulated run.

        """
        calls.append("main")
        return 0

    monkeypatch.setattr(target=run, name="main", value=_main)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_module(
            mod_name="exactus.packages.widgets.widget_console.examples",
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=calls, expected=["main"])
