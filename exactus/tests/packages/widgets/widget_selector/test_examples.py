# Copyright (c) 2026
"""Exercise the bundled widget_selector demo launcher with stubs."""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from exactus.packages.widgets.widget_selector.examples import run
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path


def test_start_demo_reuses_an_existing_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A recorded server short-circuits the spawn path entirely.

    Args:
        monkeypatch: Replaces the loopback-server helpers.
        tmp_path: Log destination for the unused spawn branch.

    """

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> tuple[int, int]:
            """Report an already-running demo server.

            Args:
                path: Served root directory.

            Returns:
                Synthetic pid/port pair.

            """
            _ = path
            return (1234, 5678)

    monkeypatch.setattr(target=run, name="local", value=LocalStub)
    expect_equal(
        actual=run.start_demo(log=tmp_path / "demo.log"),
        expected=(
            "http://127.0.0.1:5678/widgets/widget_selector/examples/web/index."
            "html"
        ),
    )


def test_start_demo_spawns_and_waits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fresh spawn waits for readiness and returns the demo URL.

    Args:
        monkeypatch: Replaces the loopback-server helpers.
        tmp_path: Log destination for the spawn branch.

    """

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> None:
            """Report that no server is recorded.

            Args:
                path: Served root directory.

            """
            _ = path

        @staticmethod
        def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
            """Return a synthetic spawn result.

            Args:
                path: Served root directory.
                log: Access-log destination.

            Returns:
                Synthetic pid, origin, and reuse flag.

            """
            _ = path
            _ = log
            return (42, "http://127.0.0.1:9000/", False)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as ready.

            Args:
                url: Server origin to probe.
                pid: Spawned process id.

            Returns:
                Always true.

            """
            _ = url
            _ = pid
            return True

    monkeypatch.setattr(target=run, name="local", value=LocalStub)
    expect_equal(
        actual=run.start_demo(log=tmp_path / "demo.log"),
        expected=(
            "http://127.0.0.1:9000/widgets/widget_selector/examples/web/index."
            "html"
        ),
    )


def test_start_demo_terminates_a_server_that_never_readies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed readiness check kills the spawned server and raises.

    Args:
        monkeypatch: Replaces the loopback-server helpers.
        tmp_path: Log destination for the spawn branch.

    """
    killed: list[int] = []
    cleared: list[Path] = []

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> None:
            """Report that no server is recorded.

            Args:
                path: Served root directory.

            """
            _ = path

        @staticmethod
        def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
            """Return a synthetic spawn result.

            Args:
                path: Served root directory.
                log: Access-log destination.

            Returns:
                Synthetic pid, origin, and reuse flag.

            """
            _ = path
            _ = log
            return (42, "http://127.0.0.1:9000/", False)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as never ready.

            Args:
                url: Server origin to probe.
                pid: Spawned process id.

            Returns:
                Always false.

            """
            _ = url
            _ = pid
            return False

        @staticmethod
        def clear_server_state(*, path: Path) -> None:
            """Record the cleared server state.

            Args:
                path: Served root directory.

            """
            cleared.append(path)

    def record_terminate(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Process id.

        """
        killed.append(pid)

    monkeypatch.setattr(target=run, name="local", value=LocalStub)
    monkeypatch.setattr(
        target=run,
        name="terminate_tree",
        value=record_terminate,
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match="did not become ready",
    ):
        run.start_demo(log=tmp_path / "demo.log")
    expect_equal(actual=killed, expected=[42])
    expect_equal(actual=len(cleared), expected=1)


def test_main_serves_then_opens_and_closes_the_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` launches the demo, opens the session, and returns zero.

    Args:
        monkeypatch: Replaces the demo launcher and browser session.

    """
    buffer: StringIO = StringIO()
    events: list[str] = []

    def start_stub(*, log: Path) -> str:
        """Return a ready demo URL without spawning a server.

        Args:
            log: Access-log destination.

        Returns:
            Synthetic demo URL.

        """
        _ = log
        events.append("start")
        return (
            "http://127.0.0.1:9000/widgets/widget_selector/examples/web/index."
            "html"
        )

    def open_stub(*, url: str) -> None:
        """Record the opened URL.

        Args:
            url: Demo URL.

        """
        events.append(f"open:{url}")

    def wait_closed_stub() -> object:
        """Record the wait for browser exit.

        Returns:
            Synthetic wait result.

        """
        events.append("wait")
        return None

    def close_stub() -> None:
        """Record the session teardown."""
        events.append("close")

    def session_factory() -> object:
        """Return a session stand-in exposing attribute callables.

        Returns:
            Stubbed browser session.

        """
        return SimpleNamespace(
            open=open_stub,
            wait_closed=wait_closed_stub,
            close=close_stub,
        )

    monkeypatch.setattr(target=run, name="start_demo", value=start_stub)
    monkeypatch.setattr(target=run, name="stdout", value=buffer)
    monkeypatch.setattr(
        target=run,
        name="BrowserSession",
        value=session_factory,
    )
    expect_equal(actual=run.main(), expected=0)
    expect_in(member="index.html", container=buffer.getvalue())
    expect_equal(
        actual=events,
        expected=[
            "start",
            (
                "open:http://127.0.0.1:9000/widgets/widget_selector/examples/w"
                "eb/index.html"
            ),
            "wait",
            "close",
        ],
    )
