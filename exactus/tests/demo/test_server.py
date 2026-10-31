# Copyright (c) 2026
"""Executable Python tests for the demo fixture."""

from __future__ import annotations

from http import HTTPStatus
from http.client import HTTPConnection, HTTPResponse
from http.server import ThreadingHTTPServer
from io import StringIO
from os import environ
from pathlib import Path
from runpy import run_path
from threading import Thread
from typing import TYPE_CHECKING, Final, final
from unittest import TestCase
from unittest.mock import MagicMock, patch

from demo.demo_app.logic import next_status
from demo.server import DemoHandler, create_parser, error_status, main

if TYPE_CHECKING:
    from argparse import Namespace


@final
class Constants:
    """Group module-level constants.

    Attributes:
        server_script: Grouped module constant.

    """

    server_script: Final[Path] = next(
        parent / "demo" / "server.py"
        for parent in Path(__file__).resolve().parents
        if (parent / "demo" / "server.py").is_file()
    )


def _expect(*, case: TestCase, actual: object, expected: object) -> None:
    """Fail ``case`` unless ``actual`` equals ``expected``.

    Args:
        case: Running test case.
        actual: Observed value.
        expected: Required value.

    """
    if actual != expected:
        case.fail(msg=f"expected {expected!r}, got {actual!r}")


class DemoLogicTest(TestCase):
    """Validate pure Python behavior through the bundled pytest runner."""

    def test_ready_becomes_active(self) -> None:
        """A ready state becomes active."""
        if next_status(value="Ready") != "Active":
            self.fail(msg="Ready did not become Active")

    def test_active_becomes_ready(self) -> None:
        """A non-ready state becomes ready."""
        if next_status(value="Active") != "Ready":
            self.fail(msg="Active did not become Ready")


class DemoServerTest(TestCase):
    """Exercise the demo HTTP server over real loopback requests."""

    def setUp(self) -> None:
        """Start a throwaway server on a free loopback port."""
        DemoHandler.diagnostic_sent = False
        self.server: ThreadingHTTPServer = ThreadingHTTPServer(
            server_address=("127.0.0.1", 0),
            RequestHandlerClass=DemoHandler,
        )
        self.thread: Thread = Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

    def tearDown(self) -> None:
        """Stop the throwaway server."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_error_status_is_internal_server_error(self) -> None:
        """The intentional failure uses HTTP 500."""
        _expect(
            case=self,
            actual=error_status(),
            expected=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def test_api_error_returns_500(self) -> None:
        """The intentional endpoint fails with a plain-text body."""
        status, body = self._request(method="GET", path="/api/error")
        _expect(
            case=self,
            actual=status,
            expected=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        _expect(
            case=self,
            actual=body,
            expected=b"intentional demo server error\n",
        )

    def test_repeated_error_request_succeeds(self) -> None:
        """Emit the diagnostic once across requests to the same server."""
        first, _ = self._request(method="GET", path="/api/error")
        second, _ = self._request(method="GET", path="/api/error")
        _expect(
            case=self,
            actual=first,
            expected=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        _expect(case=self, actual=second, expected=HTTPStatus.OK)

    def test_static_request_is_served(self) -> None:
        """Other GET requests fall through to static file serving."""
        status, _ = self._request(method="GET", path="/")
        _expect(case=self, actual=status, expected=HTTPStatus.OK)

    def test_unsupported_method_is_rejected(self) -> None:
        """Only GET is mapped; other methods are not implemented."""
        status, _ = self._request(method="POST", path="/")
        _expect(case=self, actual=status, expected=HTTPStatus.NOT_IMPLEMENTED)

    def _request(self, *, method: str, path: str) -> tuple[int, bytes]:
        """Send one request to the throwaway server.

        Args:
            method: HTTP method.
            path: Request path.

        Returns:
            Response status and body.

        """
        connection: HTTPConnection = HTTPConnection(
            host="127.0.0.1",
            port=self.server.server_address[1],
        )
        try:
            connection.request(method=method, url=path)
            response: HTTPResponse = connection.getresponse()
            return (response.status, response.read())
        finally:
            connection.close()


class DemoCliTest(TestCase):
    """Validate the server entrypoint without binding a real port."""

    def test_parser_honors_exactus_environment(self) -> None:
        """``EXACTUS_HOST``/``EXACTUS_PORT`` provide the defaults."""
        with patch.dict(
            in_dict=environ,
            values={"EXACTUS_HOST": "127.0.0.2", "EXACTUS_PORT": "9123"},
        ):
            args: Namespace = create_parser().parse_args(args=[])
        _expect(case=self, actual=args.host, expected="127.0.0.2")
        _expect(case=self, actual=args.port, expected=9123)

    def test_main_serves_until_interrupted(self) -> None:
        """``main`` announces the URL and closes the server on Ctrl-C."""
        server: MagicMock = MagicMock()
        server.serve_forever.side_effect = KeyboardInterrupt
        output: StringIO = StringIO()
        with (
            patch(target="sys.argv", new=["server.py", "--port", "8123"]),
            patch(target="demo.server.chdir"),
            patch(target="demo.server.stdout", new=output),
            patch(
                target="demo.server.ThreadingHTTPServer",
                return_value=server,
            ),
        ):
            status: int = main()
        _expect(case=self, actual=status, expected=0)
        if ":8123/" not in output.getvalue():
            self.fail(msg="main did not announce the listening URL")
        server.server_close.assert_called_once_with()

    def test_script_exits_with_main_status(self) -> None:
        """Running the file as a script exits with ``main``'s status."""
        server: MagicMock = MagicMock()
        server.serve_forever.side_effect = KeyboardInterrupt
        code: object = None
        with (
            patch(target="sys.argv", new=["server.py"]),
            patch(target="os.chdir"),
            patch(target="sys.stdout", new=StringIO()),
            patch(
                target="http.server.ThreadingHTTPServer",
                return_value=server,
            ),
        ):
            try:
                _ = run_path(
                    path_name=str(object=Constants.server_script),
                    run_name="__main__",
                )
            except SystemExit as exit_request:
                code = exit_request.code
        _expect(case=self, actual=code, expected=0)
