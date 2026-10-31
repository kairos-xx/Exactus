# Copyright (c) 2026
"""Smoke tests for the http_process package."""

from http.client import HTTPConnection
from ipaddress import IPv4Address
from pathlib import Path
from sys import executable

from exactus.packages.http_process import HttpProcess, HttpServer
from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)


def test_address_helpers() -> None:
    """Validate address classification and URL construction."""
    inspector: HttpProcess = HttpProcess()
    expect_equal(
        actual=private_call(
            owner=inspector,
            name="_probe_host",
            host=str(object=IPv4Address(address=0)),
        ),
        expected="127.0.0.1",
    )
    expect_equal(
        actual=private_call(owner=inspector, name="_probe_host", host="::"),
        expected="::1",
    )
    expect_equal(
        actual=private_call(
            owner=inspector,
            name="_url",
            host="::1",
            port=8000,
        ),
        expected="http://[::1]:8000",
    )


def test_started_process_uses_the_requested_working_directory(
    tmp_path: Path,
) -> None:
    """Start a command in a chosen folder and detect the port it opens.

    Args:
        tmp_path: Folder the server must treat as its current directory.

    """
    (tmp_path / "marker.txt").write_text(data="served from cwd")
    runner: HttpProcess = HttpProcess(
        command=[executable, "-m", "http.server", "0", "--bind", "127.0.0.1"],
        cwd=tmp_path,
    )
    runner.start()
    try:
        servers: tuple[HttpServer, ...] = runner.wait_for_http()
        expect_true(condition=bool(servers))
        connection: HTTPConnection = HTTPConnection(
            host=servers[0].probe_host,
            port=servers[0].port,
        )
        try:
            connection.request(method="GET", url="/marker.txt")
            expect_equal(
                actual=connection.getresponse().read(),
                expected=b"served from cwd",
            )
        finally:
            connection.close()
    finally:
        runner.stop()
