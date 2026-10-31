# Copyright (c) 2026 Project contributors
"""Coverage for the pointer-action demo launcher."""

from __future__ import annotations

from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from runpy import run_module
from typing import Final, final

import pytest

from exactus.packages.actions.action_pointer.examples import run
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    require,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[Path] = Path(run.__file__).resolve().parents[1]


def _stop(*, record: tuple[int, int] | None) -> None:
    """Terminate a demo server left running by a test.

    Args:
        record: ``(pid, port)`` from the local server registry.

    """
    if record is not None:
        terminate_tree(pid=record[0])
    local.clear_server_state(path=Constants.root)


def test_start_demo_serves_assets_and_reuses(tmp_path: Path) -> None:
    """Serve the page and package from one reusable loopback server.

    Args:
        tmp_path: Per-test scratch directory.

    """
    url: str = run.start_demo(log=tmp_path / "demo.log")
    record: tuple[int, int] | None = local.reuse_server(path=Constants.root)
    try:
        expect_true(condition=url.endswith("/examples/web/index.html"))
        port: int = require(value=record)[1]
        connection: HTTPConnection = HTTPConnection(
            host="127.0.0.1",
            port=port,
        )
        try:
            for asset in (
                "/examples/web/index.html",
                "/examples/web/code.js",
                "/examples/web/demo.css",
                "/index.js",
                "/pointer_studio.js",
            ):
                connection.request(method="GET", url=asset)
                expect_equal(
                    actual=connection.getresponse().status,
                    expected=200,
                )
        finally:
            connection.close()
        expect_equal(
            actual=run.start_demo(log=tmp_path / "demo.log"),
            expected=url,
        )
    finally:
        _stop(record=record)


def test_main_prints_url_and_opens_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print the demo URL and open it in the managed browser.

    Args:
        monkeypatch: Pytest patching helper.

    """
    opened: list[str] = []
    sink: StringIO = StringIO()

    def _fixed_demo(**_options: object) -> str:
        """Return a fixed demo URL.

        Args:
            **_options: Ignored launch options.

        Returns:
            Stable demo URL.

        """
        return "http://127.0.0.1:9/examples/web/index.html"

    class _Session:
        """Record a browser launch and close immediately."""

        @staticmethod
        def open(*, url: str) -> None:
            """Record the opened URL.

            Args:
                url: URL handed to the browser.

            """
            opened.append(url)

        @staticmethod
        def wait_closed(*, timeout: float | None = None) -> bool:
            """Report an already closed browser.

            Args:
                timeout: Optional wait limit.

            Returns:
                True when no timeout was requested.

            """
            return timeout is None

        def close(self) -> None:
            """Release nothing because the fake owns no browser."""

    monkeypatch.setattr(target=run, name="start_demo", value=_fixed_demo)
    monkeypatch.setattr(target=run, name="BrowserSession", value=_Session)
    monkeypatch.setattr(target=run, name="stdout", value=sink)
    expect_equal(actual=run.main(), expected=0)
    expect_equal(
        actual=opened,
        expected=["http://127.0.0.1:9/examples/web/index.html"],
    )
    expect_in(member=opened[0], container=sink.getvalue())


def test_module_entrypoint_invokes_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the examples module forwards to the launcher.

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
            mod_name="exactus.packages.actions.action_pointer.examples",
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)
    expect_equal(actual=calls, expected=["main"])


def test_start_demo_reports_unready_server_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed readiness check kills fresh servers and raises.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Per-test scratch directory.

    """
    terminated: list[int] = []
    cleared: list[Path] = []

    def _record_terminate(*, pid: int) -> None:
        """Record process-tree termination.

        Args:
            pid: Recorded process identifier.

        """
        terminated.append(pid)

    def _record_clear(*, path: Path) -> None:
        """Record server-state cleanup.

        Args:
            path: Recorded server root.

        """
        cleared.append(path)

    def _no_server(*, path: Path) -> tuple[int, int] | None:
        """Report no reusable server.

        Args:
            path: Unused server root.

        Returns:
            Absence of a reusable server.

        """
        del path
        return None

    def _fresh_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a scripted fresh server launch.

        Args:
            path: Unused server root.
            log: Unused access-log destination.

        Returns:
            Scripted pid, origin, and fresh-start marker.

        """
        del path, log
        return (4242, "http://127.0.0.1:9/", False)

    def _reused_serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
        """Return a scripted reused server launch.

        Args:
            path: Unused server root.
            log: Unused access-log destination.

        Returns:
            Scripted pid, origin, and reuse marker.

        """
        del path, log
        return (4242, "http://127.0.0.1:9/", True)

    def _never_ready(*, url: str, pid: int) -> bool:
        """Report the server as never ready.

        Args:
            url: Unused readiness URL.
            pid: Unused process identifier.

        Returns:
            Permanent unready status.

        """
        del url, pid
        return False

    monkeypatch.setattr(target=local, name="reuse_server", value=_no_server)
    monkeypatch.setattr(target=local, name="serve", value=_fresh_serve)
    monkeypatch.setattr(target=local, name="wait_ready", value=_never_ready)
    monkeypatch.setattr(
        target=run,
        name="terminate_tree",
        value=_record_terminate,
    )
    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=_record_clear,
    )
    with pytest.raises(expected_exception=RuntimeError, match="not become"):
        _ = run.start_demo(log=tmp_path / "demo.log")
    expect_equal(actual=terminated, expected=[4242])
    expect_equal(actual=cleared, expected=[Constants.root])
    terminated.clear()
    cleared.clear()
    monkeypatch.setattr(target=local, name="serve", value=_reused_serve)
    with pytest.raises(expected_exception=RuntimeError, match="not become"):
        _ = run.start_demo(log=tmp_path / "demo.log")
    expect_equal(actual=terminated, expected=[])
    expect_equal(actual=cleared, expected=[])
