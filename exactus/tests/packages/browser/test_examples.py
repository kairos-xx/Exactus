# Copyright (c) 2026
"""Exercise the browser lifecycle example with recorded stubs."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
from io import StringIO
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.browser.examples import run
from exactus.packages.browser.lifecycle import (
    BrowserBackend,
    BrowserEvent,
    BrowserEventType,
    BrowserLifecycle,
)
from exactus.packages.server import local
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from argparse import Namespace


def test_parser_defaults_to_the_playwright_backend() -> None:
    """The bundled parser selects playwright and the demo page."""
    arguments: Namespace = run.Example.parser().parse_args(args=[])
    expect_equal(actual=arguments.backend, expected="playwright")
    expect_true(condition=arguments.url is None)
    expect_equal(actual=arguments.duration, expected=run.Constants.duration)


def test_run_with_explicit_url_skips_the_demo_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit URL opens playwright without serving the bundle.

    Args:
        monkeypatch: Replaces the browser lifecycle controller.

    """
    calls: list[tuple[object, ...]] = []

    def start_playwright(
        *,
        url: str,
        headless: bool,
        executable_path: Path | None,
    ) -> None:
        """Record the playwright launch request.

        Args:
            url: Page to open.
            headless: Headless flag.
            executable_path: Optional Chrome binary.

        """
        calls.append(("playwright", url, headless, executable_path))

    def wait(*, timeout: float | None) -> int:
        """Record the wait timeout.

        Args:
            timeout: Seconds before returning.

        Returns:
            Synthetic exit status.

        """
        calls.append(("wait", timeout))
        return 0

    def close() -> None:
        """Record the lifecycle teardown."""
        calls.append(("close", None))

    def lifecycle_factory(*, callback: object) -> object:
        """Return a lifecycle stand-in exposing attribute callables.

        Args:
            callback: Event callback supplied by the example.

        Returns:
            Stubbed lifecycle controller.

        """
        calls.append(("init", callback is not None))
        return SimpleNamespace(
            start_playwright=start_playwright,
            wait=wait,
            close=close,
        )

    monkeypatch.setattr(
        target=run,
        name="BrowserLifecycle",
        value=lifecycle_factory,
    )
    run.Example.run(
        arguments=run.Example.parser().parse_args(
            args=[
                "https://example.invalid/",
                "--headless",
                "--duration",
                "1.5",
            ],
        ),
    )
    expect_equal(
        actual=calls[1:],
        expected=[
            ("playwright", "https://example.invalid/", True, None),
            ("wait", 1.5),
            ("close", None),
        ],
    )


def test_run_serves_the_bundled_demo_when_no_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a URL the example serves ``web/`` and opens playwright.

    Args:
        monkeypatch: Replaces server helpers and the lifecycle.

    """
    calls: list[str] = []
    killed: list[int] = []

    class LocalStub:
        @staticmethod
        def reuse_server(*, path: Path) -> tuple[int, int] | None:
            """Report no recorded server.

            Args:
                path: Served root directory.

            Returns:
                Always ``None``; no server was recorded.

            """
            _ = path
            return None

        @staticmethod
        def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
            """Return a synthetic server spawn.

            Args:
                path: Served root directory.
                log: Access-log destination.

            Returns:
                Synthetic pid, origin, and reuse flag.

            """
            _ = path
            _ = log
            return (99, "http://127.0.0.1:8080/", False)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as ready.

            Args:
                url: Server origin.
                pid: Spawned process id.

            Returns:
                Always true.

            """
            _ = url
            _ = pid
            return True

        @staticmethod
        def clear_server_state(*, path: Path) -> None:
            """Record the cleared server state.

            Args:
                path: Served root directory.

            """
            _ = path
            calls.append("clear")

    def start_playwright(
        *,
        url: str,
        headless: bool,
        executable_path: Path | None,
    ) -> None:
        """Record the playwright URL.

        Args:
            url: Page to open.
            headless: Headless flag.
            executable_path: Optional Chrome binary.

        """
        _ = headless
        _ = executable_path
        calls.append(f"playwright:{url}")

    def wait(*, timeout: float | None) -> int:
        """Return a synthetic exit status.

        Args:
            timeout: Seconds before returning.

        Returns:
            Fixed success code.

        """
        _ = timeout
        return 0

    def close() -> None:
        """Record the lifecycle teardown."""
        calls.append("close")

    def lifecycle_factory(*, callback: object) -> object:
        """Return a lifecycle stand-in exposing attribute callables.

        Args:
            callback: Event callback supplied by the example.

        Returns:
            Stubbed lifecycle controller.

        """
        _ = callback
        return SimpleNamespace(
            start_playwright=start_playwright,
            wait=wait,
            close=close,
        )

    def record_terminate(*, pid: int) -> None:
        """Record terminated process ids.

        Args:
            pid: Process id.

        """
        killed.append(pid)

    monkeypatch.setattr(target=run, name="local", value=LocalStub)
    monkeypatch.setattr(
        target=run,
        name="BrowserLifecycle",
        value=lifecycle_factory,
    )
    monkeypatch.setattr(
        target=run,
        name="terminate_tree",
        value=record_terminate,
    )
    run.Example.run(arguments=run.Example.parser().parse_args(args=[]))
    expect_in(
        member="playwright:http://127.0.0.1:8080/index.html",
        container=calls,
    )
    expect_equal(actual=calls[-2:], expected=["close", "clear"])
    expect_equal(actual=killed, expected=[99])


def test_run_rejects_an_unsupported_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown backend raises ``ValueError`` after cleanup.

    Args:
        monkeypatch: Replaces the browser lifecycle controller.

    """
    closed: list[bool] = []

    def close() -> None:
        """Record the lifecycle teardown."""
        closed.append(True)

    def lifecycle_factory(*, callback: object) -> object:
        """Return a lifecycle stand-in exposing attribute callables.

        Args:
            callback: Event callback supplied by the example.

        Returns:
            Stubbed lifecycle controller.

        """
        _ = callback
        return SimpleNamespace(close=close)

    monkeypatch.setattr(
        target=run,
        name="BrowserLifecycle",
        value=lifecycle_factory,
    )
    arguments: Namespace = run.Example.parser().parse_args(
        args=["https://example.invalid/"],
    )
    arguments.backend = "netscape"
    with pytest.raises(
        expected_exception=ValueError,
        match="Unsupported browser backend",
    ):
        run.Example.run(arguments=arguments)
    expect_true(condition=bool(closed))


def test_run_chrome_backend_uses_the_native_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chrome branch launches natively then sleeps briefly.

    Args:
        monkeypatch: Replaces the lifecycle and the sleep delay.

    """
    calls: list[str] = []

    def launch_chrome(*, url: str, executable: Path | None) -> object:
        """Record the native Chrome launch.

        Args:
            url: Page to open.
            executable: Optional Chrome binary.

        Returns:
            Synthetic launch result.

        """
        _ = executable
        calls.append(f"chrome:{url}")
        return None

    def close() -> None:
        """Record the lifecycle teardown."""
        calls.append("close")

    def lifecycle_factory(*, callback: object) -> object:
        """Return a lifecycle stand-in exposing attribute callables.

        Args:
            callback: Event callback supplied by the example.

        Returns:
            Stubbed lifecycle controller.

        """
        _ = callback
        return SimpleNamespace(
            launch_chrome=launch_chrome,
            close=close,
            process=None,
        )

    def record_sleep(seconds: float) -> None:
        """Record requested sleep durations.

        Args:
            seconds: Requested delay.

        """
        calls.append(f"sleep:{seconds}")

    monkeypatch.setattr(
        target=run,
        name="BrowserLifecycle",
        value=lifecycle_factory,
    )
    monkeypatch.setattr(target=run, name="sleep", value=record_sleep)
    run.Example.run(
        arguments=run.Example.parser().parse_args(
            args=[
                "https://example.invalid/",
                "--backend",
                "chrome",
                "--duration",
                "0.01",
            ],
        ),
    )
    expect_equal(
        actual=calls,
        expected=["chrome:https://example.invalid/", "sleep:0.01", "close"],
    )


def test_event_renderer_prints_a_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The event hook formats one lifecycle event per line.

    Args:
        monkeypatch: Redirects the module-level ``stdout`` binding.

    """
    buffer: StringIO = StringIO()
    monkeypatch.setattr(target=run, name="stdout", value=buffer)
    private_call(
        owner=run.Example,
        name="_event",
        event=BrowserEvent(
            timestamp=datetime(year=2026, month=1, day=1, tzinfo=UTC),
            backend=BrowserBackend.PLAYWRIGHT,
            event=BrowserEventType.PAGE_OPEN,
            pid=42,
            url="https://example.invalid/",
            title="demo",
            exit_code=None,
            browser=None,
            context=None,
            page=None,
            page_identity=None,
        ),
    )
    expect_in(member="playwright", container=buffer.getvalue())
    expect_in(member="pid=42", container=buffer.getvalue())


def test_start_demo_reuses_the_recorded_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded server is adopted instead of spawning a new one.

    Args:
        monkeypatch: Replaces the server registry lookup.

    """

    def reuse_server(*, path: Path) -> tuple[int, int] | None:
        """Return the recorded demo server.

        Args:
            path: Served root directory.

        Returns:
            The recorded process id and port.

        """
        _ = path
        return (4321, 8080)

    monkeypatch.setattr(
        target=run.local,
        name="reuse_server",
        value=reuse_server,
    )
    pid: int
    origin: str
    reused: bool
    pid, origin, reused, _ = cast(
        typ="tuple[int, str, bool, Path]",
        val=private_call(owner=run.Example, name="_start_demo"),
    )
    expect_equal(actual=pid, expected=4321)
    expect_equal(actual=origin, expected="http://127.0.0.1:8080/")
    expect_true(condition=reused)


def test_wait_native_polls_until_process_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero duration polls the native process until it exits.

    Args:
        monkeypatch: Replaces the sleep delay.

    """
    polls: list[bool] = []
    sleeps: list[float] = []

    def poll() -> int | None:
        """Report running once, then exited.

        Returns:
            ``None`` on the first poll, then a zero exit status.

        """
        polls.append(True)
        return None if len(polls) == 1 else 0

    def record_sleep(seconds: float) -> None:
        """Record the requested sleep duration.

        Args:
            seconds: Delay in seconds.

        """
        sleeps.append(seconds)

    monkeypatch.setattr(target=run, name="sleep", value=record_sleep)
    lifecycle: SimpleNamespace = SimpleNamespace(
        process=SimpleNamespace(poll=poll),
    )
    private_call(
        owner=run.Example,
        name="_wait_native",
        lifecycle=lifecycle,
        duration=0.0,
    )
    expect_equal(actual=sleeps, expected=[0.1])


def test_main_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute the example file's ``__main__`` entry with stubs.

    Args:
        monkeypatch: Replaces the lifecycle controller and arguments.

    """
    calls: list[str] = []

    def start_playwright(
        _self: BrowserLifecycle,
        *,
        url: str,
        headless: bool,
        executable_path: Path | None,
    ) -> None:
        """Record the playwright launch request.

        Args:
            _self: Lifecycle instance (unused).
            url: Page to open.
            headless: Headless flag.
            executable_path: Optional Chrome binary.

        """
        _ = headless
        _ = executable_path
        calls.append(f"open:{url}")

    def wait(_self: BrowserLifecycle, *, timeout: float | None) -> int:
        """Record the wait timeout.

        Args:
            _self: Lifecycle instance (unused).
            timeout: Seconds before returning.

        Returns:
            Synthetic exit status.

        """
        calls.append(f"wait:{timeout}")
        return 0

    def close(_self: BrowserLifecycle) -> None:
        """Record the lifecycle teardown.

        Args:
            _self: Lifecycle instance (unused).

        """
        calls.append("close")

    monkeypatch.setattr(
        target=BrowserLifecycle,
        name="start_playwright",
        value=start_playwright,
    )
    monkeypatch.setattr(target=BrowserLifecycle, name="wait", value=wait)
    monkeypatch.setattr(target=BrowserLifecycle, name="close", value=close)
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["example", "https://example.invalid/", "--duration", "0.5"],
    )
    example: Path = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "browser"
        / "examples"
        / "run.py"
    )
    run_path(path_name=str(object=example), run_name="__main__")
    expect_equal(
        actual=calls,
        expected=["open:https://example.invalid/", "wait:0.5", "close"],
    )


def test_main_module_reports_an_unready_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unready fresh demo server raises ``RuntimeError`` after cleanup.

    Args:
        monkeypatch: Replaces the server helpers and lifecycle.

    """
    killed: list[int] = []
    cleared: list[Path] = []

    class LocalStub:
        """Stand-in for the shared loopback server helpers."""

        @staticmethod
        def reuse_server(*, path: Path) -> tuple[int, int] | None:
            """Report no recorded server.

            Args:
                path: Served root directory.

            Returns:
                Always ``None``.

            """
            _ = path
            return None

        @staticmethod
        def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
            """Return a synthetic server spawn.

            Args:
                path: Served root directory.
                log: Access-log destination.

            Returns:
                Synthetic pid, origin, and reuse flag.

            """
            _ = path
            _ = log
            return (99, "http://127.0.0.1:8080/", False)

        @staticmethod
        def wait_ready(*, url: str, pid: int) -> bool:
            """Report the synthetic server as never ready.

            Args:
                url: Server origin.
                pid: Spawned process id.

            Returns:
                Always ``False``.

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

    def terminate(*, pid: int) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.

        """
        killed.append(pid)

    def close(_self: BrowserLifecycle) -> None:
        """Accept lifecycle teardown without acting.

        Args:
            _self: Lifecycle instance (unused).

        """

    monkeypatch.setattr(
        target=local,
        name="reuse_server",
        value=LocalStub.reuse_server,
    )
    monkeypatch.setattr(target=local, name="serve", value=LocalStub.serve)
    monkeypatch.setattr(
        target=local,
        name="wait_ready",
        value=LocalStub.wait_ready,
    )
    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=LocalStub.clear_server_state,
    )
    monkeypatch.setattr(
        target=import_module(name="exactus.packages.server.process_control"),
        name="terminate_tree",
        value=terminate,
    )
    monkeypatch.setattr(target=BrowserLifecycle, name="close", value=close)
    monkeypatch.setattr(
        target=import_module(name="sys"),
        name="argv",
        value=["example"],
    )
    example: Path = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "browser"
        / "examples"
        / "run.py"
    )
    with pytest.raises(expected_exception=RuntimeError, match="ready"):
        run_path(path_name=str(object=example), run_name="__main__")
    expect_equal(actual=killed, expected=[99])
    expect_true(condition=len(cleared) == 1)


def test_run_ignores_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``KeyboardInterrupt`` during the wait still closes the browser.

    Args:
        monkeypatch: Replaces the browser lifecycle controller.

    """
    calls: list[str] = []

    def start_playwright(
        *,
        url: str,
        headless: bool,
        executable_path: Path | None,
    ) -> None:
        """Raise ``KeyboardInterrupt`` as if the user interrupted.

        Args:
            url: Page to open.
            headless: Headless flag.
            executable_path: Optional Chrome binary.

        Raises:
            KeyboardInterrupt: Always.

        """
        _ = url
        _ = headless
        _ = executable_path
        raise KeyboardInterrupt

    def close() -> None:
        """Record the lifecycle teardown."""
        calls.append("close")

    def lifecycle_factory(*, callback: object) -> object:
        """Return a lifecycle stand-in exposing attribute callables.

        Args:
            callback: Event callback supplied by the example.

        Returns:
            Stubbed lifecycle controller.

        """
        _ = callback
        return SimpleNamespace(start_playwright=start_playwright, close=close)

    monkeypatch.setattr(
        target=run,
        name="BrowserLifecycle",
        value=lifecycle_factory,
    )
    run.Example.run(
        arguments=run.Example.parser().parse_args(
            args=["https://example.invalid/"],
        ),
    )
    expect_equal(actual=calls, expected=["close"])
