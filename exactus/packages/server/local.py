# Copyright (c) 2026
"""Loopback web-server lifecycle for the screenshot exactus shortcuts.

``--server`` directories are served by an embedded ``http.server``
snippet that answers a predictable identity ping, letting repeat
invocations adopt a surviving instance instead of stacking a second
server on the same content. ``--entrypoint`` helpers export
``EXACTUS_HOST``/``EXACTUS_PORT`` (plus ``HOST``/``PORT``) so the script
binds a known loopback port — the ``--url`` port when one is given,
otherwise an assigned free port.
"""

from __future__ import annotations

from contextlib import suppress
from hashlib import sha256
from http.client import HTTPConnection
from json import loads
from os import environ
from pathlib import Path
from socket import create_connection, socket
from subprocess import PIPE, Popen
from sys import executable
from textwrap import dedent
from threading import Lock, Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import ParseResult, urlparse

if TYPE_CHECKING:
    from typing import TextIO
from .process_control import process_exists, terminate_tree


@final
class Constants:
    """Group module-level constants.

    Attributes:
        probe_hosts: Grouped module constant.
        probe_port: Grouped module constant.
        ping_path: Grouped module constant.
        server_token: Grouped module constant.
        server_snippet: Grouped module constant.
        log_lock: Grouped module constant.
        serve_retries: Grouped module constant.

    """

    probe_hosts: Final[tuple[str, ...]] = ("localhost", "127.0.0.1")
    probe_port: Final[int] = 80
    ping_path: Final[str] = "/_exactus_ping"
    server_token: Final[bytes] = b"exactus-check-server"
    server_snippet: Final[str] = dedent(
        text=(
            f'\n        """Loopback file server answering the exactus identity'
            f' ping."""\n\n        from functools import partial\n        from'
            f" http.server import (\n            SimpleHTTPRequestHandler,\n  "
            f"          ThreadingHTTPServer,\n        )\n        from sys impo"
            f"rt argv\n\n\n        class Handler(SimpleHTTPRequestHandler):\n "
            f'           """Serve files and answer the predictable identity pi'
            f'ng."""\n\n            def do_GET(self) -> None:\n               '
            f' """Answer the identity ping or serve the requested file.\n\n   '
            f"             Returns:\n                    Nothing; the response"
            f' is written to ``self.wfile``.\n\n                """\n         '
            f'       if self.path == "'
            f"{ping_path}"
            f'":\n                    body: bytes = '
            f"{server_token!r}"
            f"\n                    self.send_response(code=200)\n            "
            f'        self.send_header(\n                        keyword="Cont'
            f'ent-Type",\n                        value="text/plain",\n       '
            f"             )\n                    self.send_header(\n         "
            f'               keyword="Content-Length",\n                      '
            f"  value=str(object=len(body)),\n                    )\n         "
            f"           self.end_headers()\n                    self.wfile.wr"
            f"ite(body)\n                    return\n                super().d"
            f"o_GET()\n\n            def log_message(self, format: str, *args:"
            f' object) -> None:\n                """Write standard access logs'
            f" for exactus correlation.\n\n                Args:\n            "
            f"        format: Printf-style access-log format string.\n        "
            f"            args: Values interpolated into the format string.\n"
            f'\n                """\n                super().log_message(forma'
            f't, *args)\n\n\n        def _serve() -> None:\n            """Bin'
            f"d the loopback port and serve the directory forever.\n\n        "
            f"    The port and served directory arrive as ``argv[1]`` and\n   "
            f"         ``argv[2]`` because this program runs through ``python "
            f'-c``.\n            """\n            server: ThreadingHTTPServer '
            f'= ThreadingHTTPServer(\n                server_address=("127.0.0'
            f'.1", int(argv[1])),\n                RequestHandlerClass=partial'
            f"(Handler, directory=argv[2]),\n            )\n            server"
            f'.serve_forever()\n\n\n        if __name__ == "__main__":\n      '
            f"      _serve()"
        ),
    )
    log_lock: Final[Lock] = Lock()
    serve_retries: Final[int] = 4


def _capture_stream(*, stream: TextIO, name: str, log: Path) -> None:
    """Continuously copy one child-process stream into a durable log.

    Server output is kept out of the terminal so it cannot interleave
    with the live progress display; the screenshot exactus parses the log
    file for HTTP diagnostics.

    Args:
        stream: Child-process text stream to drain.
        name: Stream label written before each line (stdout/stderr).
        log: Log file receiving the labelled lines.

    """
    for line in stream:
        record: str = f"[{name}] {line.rstrip()}\n"
        with Constants.log_lock:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open(mode="a", encoding="utf-8") as handle:
                _ = handle.write(record)
                handle.flush()


def _spawn_captured(
    *,
    args: tuple[str, ...],
    cwd: Path,
    log: Path,
    environment: dict[str, str] | None = None,
) -> Popen[str]:
    """Start a server while continuously capturing stdout and stderr.

    Args:
        args: Command line of the server process.
        cwd: Working directory of the server process.
        log: Log file receiving both captured streams.
        environment: Environment for the process, or ``None`` to inherit.

    Returns:
        The running server process.

    """
    log.parent.mkdir(parents=True, exist_ok=True)
    _ = log.write_text(data="", encoding="utf-8")
    process: Popen[str] = Popen(
        args=args,
        cwd=cwd,
        env=environment,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        bufsize=1,
    )
    if process.stdout is not None:
        Thread(
            target=_capture_stream,
            kwargs={"stream": process.stdout, "name": "stdout", "log": log},
            daemon=True,
        ).start()
    if process.stderr is not None:
        Thread(
            target=_capture_stream,
            kwargs={"stream": process.stderr, "name": "stderr", "log": log},
            daemon=True,
        ).start()
    return process


def accepts(*, host: str, port: int, timeout: float = 1.0) -> bool:
    """Return whether ``host:port`` accepts a TCP connection.

    Args:
        host: Hostname or address to probe.
        port: TCP port to probe.
        timeout: Per-attempt connection timeout in seconds.

    Returns:
        Whether the connection was accepted.

    """
    with (
        suppress(OSError),
        create_connection(address=(host, port), timeout=timeout),
    ):
        return True
    return False


def free_port() -> int:
    """Return an available loopback TCP port.

    Returns:
        Ephemeral port number currently free on ``127.0.0.1``.

    """
    with socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return cast(typ="int", val=probe.getsockname()[1])


def probe_default_url(*, pid: int, timeout: float = 15.0) -> str | None:
    """Poll default loopback hosts on port 80 for a running server.

    Args:
        pid: Entrypoint process id; early exit short-circuits the probe.
        timeout: Maximum seconds to wait for a responding server.

    Returns:
        URL of the first accepting host, or ``None``.

    """
    deadline: float = monotonic() + timeout
    while monotonic() < deadline:
        if not process_exists(pid=pid):
            return None
        for host in Constants.probe_hosts:
            if accepts(host=host, port=Constants.probe_port):
                return f"http://{host}:{Constants.probe_port}/"
        sleep(0.05)
    return None


def wait_ready(*, url: str, pid: int, timeout: float = 15.0) -> bool:
    """Poll until the URL's host and port accept TCP connections.

    Args:
        url: URL whose host and port are probed.
        pid: Server process id; early exit short-circuits the wait.
        timeout: Maximum seconds to wait for readiness.

    Returns:
        Whether the server accepted a connection before the deadline.

    """
    parsed: ParseResult = urlparse(url=url)
    host: str = parsed.hostname or "127.0.0.1"
    port: int = parsed.port or (443 if parsed.scheme == "https" else 80)
    deadline: float = monotonic() + timeout
    while monotonic() < deadline:
        if not process_exists(pid=pid):
            return False
        if accepts(host=host, port=port):
            return True
        sleep(0.05)
    return False


def server_state_path(*, path: Path) -> Path:
    """Return the state file recording a ``--server`` instance.

    Args:
        path: Served directory.

    Returns:
        Cache path keyed by the resolved directory digest.

    """
    base: Path = Path(
        environ.get("XDG_CACHE_HOME") or str(object=Path.home() / ".cache"),
    )
    digest: str = sha256(
        data=str(object=path.resolve()).encode(encoding="utf-8"),
    ).hexdigest()[:16]
    return base / "exactus-tools" / "servers" / f"{digest}.json"


def ping_server(*, port: int, timeout: float = 1.5) -> bool:
    """Return whether ``port`` answers the ``--server`` identity probe.

    Args:
        port: Loopback TCP port to probe.
        timeout: HTTP request timeout in seconds.

    Returns:
        Whether the ping endpoint returned the predictable token.

    """
    connection: HTTPConnection = HTTPConnection(
        host="127.0.0.1",
        port=port,
        timeout=timeout,
    )
    with suppress(OSError):
        try:
            connection.request(method="GET", url=Constants.ping_path)
            return connection.getresponse().read() == Constants.server_token
        finally:
            connection.close()
    return False


def reuse_server(*, path: Path) -> tuple[int, int] | None:
    """Return the pid and port of a surviving ``--server`` instance.

    Args:
        path: Served directory.

    Returns:
        ``(pid, port)`` when the recorded server still answers the
        identity ping, otherwise ``None``.

    """
    state: Path = server_state_path(path=path)
    try:
        payload: object = loads(s=state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    record: dict[str, object] = cast(typ="dict[str, object]", val=payload)
    pid: object = record.get("pid")
    port: object = record.get("port")
    if not isinstance(pid, int) or not isinstance(port, int):
        return None
    if process_exists(pid=pid) and ping_server(port=port):
        return (pid, port)
    return None


def serve(*, path: Path, log: Path) -> tuple[int, str, bool]:
    """Reuse a surviving ``--server`` instance or spawn a new one.

    Args:
        path: Directory to serve.
        log: File receiving the server's captured stdout/stderr.

    Returns:
        ``(pid, url, reused)`` for the running server.

    Raises:
        RuntimeError: When a fresh server cannot be spawned after
            several attempts.

    """
    existing: tuple[int, int] | None = reuse_server(path=path)
    if existing is not None:
        pid, port = existing
        return (pid, f"http://127.0.0.1:{port}/", True)
    state: Path = server_state_path(path=path)
    attempt: int
    for attempt in range(Constants.serve_retries):
        port: int = free_port()
        url: str = f"http://127.0.0.1:{port}/"
        process: Popen[str] = _spawn_captured(
            args=(
                executable,
                "-c",
                Constants.server_snippet,
                str(object=port),
                str(object=path.resolve()),
            ),
            cwd=path.resolve(),
            log=log,
        )
        with suppress(OSError):
            state.parent.mkdir(parents=True, exist_ok=True)
            _ = state.write_text(
                data=f'{{"pid": {process.pid}, "port": {port}}}\n',
                encoding="utf-8",
            )
        if process.poll() is None:
            return (process.pid, url, False)
        terminate_tree(pid=process.pid)
        _ = process.wait()
        clear_server_state(path=path)
        if attempt < Constants.serve_retries - 1:
            sleep(0.05 * (attempt + 1))
    msg: str = f"could not start server for {path}"
    raise RuntimeError(msg)


def start_entrypoint(
    *,
    path: Path,
    log: Path,
    port: int | None = None,
) -> tuple[int, int]:
    """Launch a custom server script before the screenshot exactus.

    Args:
        path: Python file run with the interpreter; its parent directory
            becomes the working directory.
        log: File receiving the server's captured stdout/stderr.
        port: Loopback port exported through ``EXACTUS_PORT``/``PORT``;
            a free port is assigned when ``None``.

    Returns:
        ``(pid, port)`` of the launched process.

    """
    assigned: int = free_port() if port is None else port
    environment: dict[str, str] = dict(environ)
    environment |= {
        "EXACTUS_HOST": "127.0.0.1",
        "EXACTUS_PORT": str(object=assigned),
        "HOST": "127.0.0.1",
        "PORT": str(object=assigned),
        "PYTHONUNBUFFERED": "1",
    }
    process: Popen[str] = _spawn_captured(
        args=(executable, str(object=path.resolve())),
        cwd=path.resolve().parent,
        log=log,
        environment=environment,
    )
    return (process.pid, assigned)


def clear_server_state(*, path: Path) -> None:
    """Remove the recorded ``--server`` state file for ``path``.

    Args:
        path: Served directory.

    """
    with suppress(OSError):
        server_state_path(path=path).unlink()
