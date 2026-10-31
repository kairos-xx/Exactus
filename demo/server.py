#!/usr/bin/env python3
# Copyright (c) 2026
"""Serve the demo and expose an intentional HTTP 500 test endpoint."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from os import chdir, environ
from pathlib import Path
from sys import stdout
from threading import Lock
from typing import ClassVar, Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        static_root: Grouped module constant.

    """

    static_root: Final[Path] = Path(__file__).resolve().parent / "static"


def error_status() -> int:
    """Return the intentional server-error status used by the demo.

    Returns:
        HTTP 500 as an integer.

    """
    return int(HTTPStatus.INTERNAL_SERVER_ERROR)


class DemoHandler(SimpleHTTPRequestHandler):
    """Serve static demo assets plus one intentional failing request.

    Attributes:
        diagnostic_lock: Serialize the diagnostic across capture lanes.
        diagnostic_sent: Track the first failing response in this process.

    """

    diagnostic_lock: ClassVar[Lock] = Lock()
    diagnostic_sent: ClassVar[bool] = False

    def do_get(self) -> None:
        """Serve a static resource or the intentional error endpoint."""
        if self.path == "/api/error":
            body: bytes = b"intentional demo server error\n"
            with self.diagnostic_lock:
                status: int = (
                    HTTPStatus.OK
                    if DemoHandler.diagnostic_sent
                    else error_status()
                )
                DemoHandler.diagnostic_sent = True
            self.send_response(code=status)
            self.send_header(keyword="Content-Type", value="text/plain")
            self.send_header(
                keyword="Content-Length",
                value=str(object=len(body)),
            )
            self.end_headers()
            _ = self.wfile.write(body)
            return
        super().do_GET()


DemoHandler.do_GET = DemoHandler.do_get


def create_parser() -> ArgumentParser:
    """Create the demo server argument parser.

    Returns:
        Configured parser.

    """
    parser: ArgumentParser = ArgumentParser(description="Serve demo assets.")
    _ = parser.add_argument(
        "--host",
        default=environ.get("EXACTUS_HOST", "127.0.0.1"),
    )
    _ = parser.add_argument(
        "--port",
        type=int,
        default=int(environ.get("EXACTUS_PORT", "8765")),
    )
    return parser


def main() -> int:
    """Run the demo HTTP server until interrupted.

    Returns:
        Process exit status.

    """
    DemoHandler.diagnostic_sent = False
    args: Namespace = create_parser().parse_args()
    chdir(path=Constants.static_root)
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        server_address=(str(object=args.host), int(args.port)),
        RequestHandlerClass=DemoHandler,
    )
    _ = stdout.write(
        f"Demo server listening on http://{args.host}:{args.port}/\n",
    )
    stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
