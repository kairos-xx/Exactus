# Copyright (c) 2026
"""Cover the ``exactus.packages.http_process`` CLI and process wait paths."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from socket import socket
from sys import executable, modules
from threading import Thread
from typing import Final, final, override

import pytest

from exactus.packages.http_process import cli as cli_module
from exactus.packages.http_process.cli import Cli, main
from exactus.packages.http_process.process import (
    HttpInspection,
    HttpProcess,
    HttpServer,
    ProcessInfo,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        loopback: Grouped module constant.

    """

    loopback: Final[str] = "127.0.0.1"


def _free_port() -> int:
    """Reserve and release an ephemeral loopback port.

    Returns:
        A port that is safe to bind immediately afterwards.

    """
    probe: socket = socket()
    probe.bind((Constants.loopback, 0))
    port: int = int(str(object=probe.getsockname()[1]))
    probe.close()
    return port


class _QuietHandler(BaseHTTPRequestHandler):
    """Serve a minimal HTTP 200 response without logging."""

    def do_get(self) -> None:
        """Answer every GET with an empty success body."""
        self.send_response(code=200)
        self.send_header(keyword="Content-Length", value="0")
        self.end_headers()

    @override
    def log_message(self, *args: object, **_kwargs: object) -> None:
        """Silence per-request logging.

        Args:
            args: Format string and arguments (unused).
            _kwargs: Keyword arguments (unused).

        """
        _ = (self, args, _kwargs)

    def __getattr__(self, name: str) -> object:
        """Resolve the ``do_GET`` dispatch name to ``do_get``.

        Args:
            name: Attribute being resolved.

        Returns:
            The GET handler for ``do_GET``.

        Raises:
            AttributeError: For every other missing attribute.

        """
        if name == "do_GET":
            return self.do_get
        raise AttributeError(name)


def _serve_once() -> tuple[ThreadingHTTPServer, Thread]:
    """Start a throwaway loopback HTTP server on a free port.

    Returns:
        The bound server and its serving thread.

    """
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        server_address=(Constants.loopback, 0),
        RequestHandlerClass=_QuietHandler,
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return (server, thread)


def test_cli_inspect_reports_closed_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inspect mode returns one when nothing serves HTTP.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["http_process", "--port", str(object=_free_port())],
    )
    monkeypatch.setattr(target=cli_module, name="stdout", value=StringIO())
    status: int = Cli.run()
    expect_equal(actual=status, expected=1)


def test_cli_inspect_reports_live_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inspect mode reports a live server and its owning process.

    Args:
        monkeypatch: Pytest patching helper.

    """
    server, thread = _serve_once()
    try:
        port: int = int(str(object=server.server_address[1]))
        out: StringIO = StringIO()
        monkeypatch.setattr(
            target=modules["sys"],
            name="argv",
            value=["http_process", "--port", str(object=port)],
        )
        monkeypatch.setattr(target=cli_module, name="stdout", value=out)
        status: int = Cli.run()
        expect_equal(actual=status, expected=0)
        expect_true(condition='"http": true' in out.getvalue())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_run_discovers_spawned_http_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command mode spawns, discovers, and stops an HTTP server.

    Args:
        monkeypatch: Pytest patching helper.

    """
    port: int = _free_port()
    out: StringIO = StringIO()
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "http_process",
            "--timeout",
            "20",
            "--",
            executable,
            "-m",
            "http.server",
            str(object=port),
            "--bind",
            Constants.loopback,
        ],
    )
    monkeypatch.setattr(target=cli_module, name="stdout", value=out)
    status: int = Cli.run()
    expect_equal(actual=status, expected=0)
    expect_true(condition='"url":' in out.getvalue())
    expect_true(condition=f":{port}" in out.getvalue())


def test_main_delegates_to_cli_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """``main`` forwards to ``Cli.run``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["http_process", "--port", str(object=_free_port())],
    )
    monkeypatch.setattr(target=cli_module, name="stdout", value=StringIO())
    expect_equal(actual=main(), expected=1)


def test_wait_for_http_requires_a_started_process() -> None:
    """Waiting without a managed process raises ``RuntimeError``."""
    inspector: HttpProcess = HttpProcess(timeout=0.1)
    with pytest.raises(expected_exception=RuntimeError, match=r"not.*started"):
        inspector.wait_for_http()


def test_wait_for_listener_requires_a_started_process() -> None:
    """The TCP variant reports the same missing-process failure."""
    inspector: HttpProcess = HttpProcess(timeout=0.1)
    with pytest.raises(expected_exception=RuntimeError, match=r"not.*started"):
        inspector.wait_for_listener()


def test_wait_for_http_reports_early_process_exit() -> None:
    """A process that exits before serving raises ``RuntimeError``."""
    inspector: HttpProcess = HttpProcess(
        command=[executable, "-c", "pass"],
        timeout=5.0,
        http_timeout=0.2,
    )
    inspector.start()
    with pytest.raises(expected_exception=RuntimeError, match="exited"):
        inspector.wait_for_http()


def test_wait_for_listener_times_out_without_a_socket() -> None:
    """A process that never listens raises ``TimeoutError``."""
    inspector: HttpProcess = HttpProcess(
        command=[executable, "-c", "import time; time.sleep(5)"],
        timeout=0.2,
    )
    inspector.start()
    try:
        with pytest.raises(expected_exception=TimeoutError):
            inspector.wait_for_listener()
    finally:
        inspector.stop()


def test_wait_for_times_out_on_a_closed_port() -> None:
    """Waiting for HTTP on a closed port raises ``TimeoutError``."""
    inspector: HttpProcess = HttpProcess(timeout=0.2, http_timeout=0.1)
    with pytest.raises(expected_exception=TimeoutError):
        inspector.wait_for(host=Constants.loopback, port=_free_port())


def test_stop_terminates_a_managed_process() -> None:
    """``stop`` terminates the spawned tree and clears the handle."""
    inspector: HttpProcess = HttpProcess(
        command=[executable, "-c", "import time; time.sleep(30)"],
        timeout=0.2,
    )
    inspector.start()
    expect_true(condition=inspector.running)
    inspector.stop()
    expect_false(condition=inspector.running)
    expect_true(condition=inspector.pid is None)


def test_stop_is_safe_without_a_process() -> None:
    """``stop`` is a no-op when nothing was started."""
    inspector: HttpProcess = HttpProcess(timeout=0.1)
    inspector.stop()


def test_inspect_reports_process_ownership() -> None:
    """Inspecting a live server resolves its owning local process."""
    server, thread = _serve_once()
    try:
        inspector: HttpProcess = HttpProcess(timeout=5.0, http_timeout=2.0)
        result: HttpInspection = inspector.inspect(
            host=Constants.loopback,
            port=int(str(object=server.server_address[1])),
        )
        expect_true(condition=result.tcp_open)
        expect_true(condition=result.http)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_wait_for_http_discovers_and_describes_a_spawned_server() -> None:
    """End-to-end discovery exercises listeners, servers, and lookups."""
    port: int = _free_port()
    inspector: HttpProcess = HttpProcess(
        command=[
            executable,
            "-m",
            "http.server",
            str(object=port),
            "--bind",
            Constants.loopback,
        ],
        timeout=20.0,
        http_timeout=2.0,
    )
    try:
        inspector.start()
        servers: tuple[HttpServer, ...] = inspector.wait_for_http()
        expect_true(condition=len(servers) >= 1)
        server: HttpServer = servers[0]
        expect_true(condition=server.pid is not None)
        _ = server.localhost_only
        _ = server.all_interfaces
        _ = server.specific_ip
        expect_true(condition=len(inspector.listeners) >= 1)
        expect_true(condition=port in inspector.ports)
        expect_true(condition=port in inspector.http_ports)
        expect_true(condition=Constants.loopback in inspector.bound_addresses)
        expect_true(
            condition=any(str(object=port) in url for url in inspector.urls),
        )
        expect_true(condition=len(inspector.localhost_servers) >= 1)
        _ = inspector.wildcard_servers
        _ = inspector.specific_ip_servers
        expect_true(
            condition=inspector.is_http(host=Constants.loopback, port=port),
        )
        owner: ProcessInfo | None = inspector.process_at(
            host=Constants.loopback,
            port=port,
        )
        expect_true(condition=owner is None or owner.pid > 0)
    finally:
        inspector.stop()


def test_constructor_rejects_empty_command() -> None:
    """An empty command list raises ``ValueError``."""
    with pytest.raises(expected_exception=ValueError, match="at least one"):
        HttpProcess(command=[])


def test_start_requires_a_command_and_single_use() -> None:
    """``start`` reports missing commands and double starts."""
    inspector: HttpProcess = HttpProcess(timeout=0.1)
    with pytest.raises(expected_exception=RuntimeError, match="no command"):
        inspector.start()
    started: HttpProcess = HttpProcess(
        command=[executable, "-c", "import time; time.sleep(5)"],
        timeout=0.2,
    )
    started.start()
    try:
        with pytest.raises(
            expected_exception=RuntimeError,
            match="already been started",
        ):
            started.start()
    finally:
        started.stop()


def test_inspect_rejects_an_invalid_port() -> None:
    """Out-of-range ports raise ``ValueError``."""
    inspector: HttpProcess = HttpProcess(timeout=0.1)
    with pytest.raises(expected_exception=ValueError, match="port"):
        inspector.inspect(host=Constants.loopback, port=0)
