# Copyright (c) 2026 Project contributors
"""Start, detect and stop the service a project's target refers to."""

from __future__ import annotations

from ipaddress import ip_address
from socket import (
    SOCK_STREAM,
    AddressFamily,
    SocketKind,
    gaierror,
    getaddrinfo,
)
from threading import Lock, Thread
from time import sleep
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import SplitResult, urlsplit

from exactus.packages.http_process import (
    BindScope,
    HttpInspection,
    HttpProcess,
    HttpServer,
    ProcessInfo,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from exactus.tools.record.model import Target
    from exactus.tools.record.store import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        start_timeout: Grouped module constant.
        settle_seconds: Grouped module constant.
        probe_timeout: Grouped module constant.
        error_status: Grouped module constant.

    """

    start_timeout: Final[float] = 30.0
    settle_seconds: Final[float] = 0.5
    probe_timeout: Final[float] = 1.0
    error_status: Final[int] = 500


def _process(info: ProcessInfo | None) -> JsonValue:
    """Describe the process that owns a listener.

    Args:
        info: Process metadata, when it is a local process.

    Returns:
        Identifier, name and command line, or None for a remote address.

    """
    if info is None:
        return None
    command: list[JsonValue] = [*info.command]
    return {"pid": info.pid, "name": info.name, "command": command}


def _candidate(server: HttpServer) -> dict[str, JsonValue]:
    """Describe one HTTP server a service opened.

    Args:
        server: Verified HTTP server.

    Returns:
        Address, port, status and owner.

    """
    return {
        "url": server.url,
        "port": server.port,
        "status": server.status,
        "pid": server.pid,
        "scope": server.scope.value,
    }


def best_server(servers: tuple[HttpServer, ...]) -> HttpServer:
    """Choose the server a person most likely means.

    Healthy servers come before broken ones, local ones before servers bound
    to one specific address, and then the lowest port wins.

    Args:
        servers: Servers found in the service's process tree.

    Returns:
        The preferred server.

    """
    return min(
        servers,
        key=lambda item: (
            item.status >= Constants.error_status,
            item.scope not in {BindScope.LOOPBACK, BindScope.WILDCARD},
            item.port,
        ),
    )


class TargetService:
    """Own at most one started service and report what is reachable."""

    def __init__(self, *, root: Path, emit: Callable[[Event], None]) -> None:
        """Prepare without starting anything.

        Args:
            root: Project folder; a service's working directory stays inside.
            emit: Receiver of state changes, called from the owning thread.

        """
        self._root: Path = root
        self._emit: Callable[[Event], None] = emit
        self._lock: Lock = Lock()
        self._runner: HttpProcess | None = None
        self._thread: Thread | None = None
        self._stopping: bool = False
        self._state: dict[str, JsonValue] = {"state": "idle"}

    @property
    def base_url(self) -> str | None:
        """Address of the running service, if one was detected.

        Returns:
            Base URL such as ``http://127.0.0.1:5173``, else None.

        """
        with self._lock:
            if self._state.get("state") != "running":
                return None
            url: JsonValue = self._state.get("url")
            return url if isinstance(url, str) else None

    @staticmethod
    def check(*, target: Target) -> dict[str, JsonValue]:
        """Probe the configured address without starting anything.

        Args:
            target: URL-mode target.

        Returns:
            Whether something answers there, with its HTTP status and, for a
            local listener, the process that owns it.

        """
        address: str = target.address()
        if address == "about:blank":
            return {"state": "unset"}
        parts: SplitResult = urlsplit(url=address)
        host: str = parts.hostname or ""
        port: int = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            found: list[
                tuple[
                    AddressFamily,
                    SocketKind,
                    int,
                    str,
                    tuple[str, int]
                    | tuple[str, int, int, int]
                    | tuple[int, bytes],
                ]
            ] = getaddrinfo(host=host, port=port, type=SOCK_STREAM)
        except gaierror:
            return {
                "state": "unresolved",
                "url": address,
                "error": f"Could not find a host named {host}.",
            }
        ip: str = str(
            object=ip_address(
                address=str(object=found[0][4][0]).split(sep="%")[0],
            ),
        )
        seen: HttpInspection = HttpProcess(
            http_timeout=Constants.probe_timeout,
        ).inspect(host=ip, port=port)
        state: str = (
            "unreachable"
            if not seen.tcp_open
            else "reachable"
            if seen.http
            else "open"
            if parts.scheme == "https"
            else "not-http"
        )
        return {
            "state": state,
            "url": address,
            "status": seen.status,
            "reason": seen.reason,
            "process": _process(info=seen.process),
        }

    def snapshot(self) -> dict[str, JsonValue]:
        """Return the current state, noticing a service that exited.

        Returns:
            State, command, detected address, candidates and any error.

        """
        with self._lock:
            runner: HttpProcess | None = self._runner
            if (
                self._state.get("state") == "running"
                and runner is not None
                and (not runner.running)
            ):
                code: int | None = (
                    None
                    if runner.process is None
                    else runner.process.returncode
                )
                self._state = {
                    **self._state,
                    "state": "exited",
                    "error": f"The service exited (code {code}).",
                }
            return dict(self._state)

    def start(self, *, target: Target) -> None:
        """Start the configured service and detect its port in the background.

        Args:
            target: Service-mode target with a command.

        Raises:
            ValueError: When the target is not a service, one is already
                running, or the working directory is not inside the project.

        """
        if target.mode.value != "service":
            msg: str = "Choose 'Start a service' in the target first."
            raise ValueError(msg)
        with self._lock:
            if self._state.get("state") in {"starting", "running"}:
                msg = "A service is already running. Stop it first."
                raise ValueError(msg)
            folder: Path = self._folder(target=target)
            command: list[JsonValue] = [*target.command]
            self._stopping = False
            self._state = {"state": "starting", "command": command}
            self._runner = HttpProcess(
                command=[*target.command],
                timeout=Constants.start_timeout,
                cwd=folder,
            )
            runner: HttpProcess = self._runner
        self._publish()
        self._thread = Thread(
            target=self._run,
            kwargs={"runner": runner, "target": target},
            name="studio-target-service",
            daemon=True,
        )
        self._thread.start()

    def set_root(self, *, root: Path) -> None:
        """Move to another project folder.

        Args:
            root: The new project folder; nothing may be running.

        """
        with self._lock:
            self._root = root

    def stop(self, *, wait: bool = False) -> None:
        """Stop the service and everything it started.

        Args:
            wait: Return only after the process tree is gone.

        """
        with self._lock:
            runner: HttpProcess | None = self._runner
            self._runner = None
            self._stopping = True
            self._state = {"state": "idle"}
        if runner is not None:
            if wait:
                runner.stop()
            else:
                Thread(target=runner.stop, daemon=True).start()
        self._publish()

    @staticmethod
    def _detect(
        *,
        runner: HttpProcess,
        port: int | None,
    ) -> tuple[HttpServer, ...]:
        """Find the HTTP servers the started process opened.

        Args:
            runner: Started process.
            port: Port set by hand, or None to detect it.

        Returns:
            One server for a manual port, otherwise every detected server.

        """
        if port is not None:
            _ = runner.wait_for(host="127.0.0.1", port=port)
            return tuple(
                item for item in runner.http_servers if item.port == port
            )
        first: tuple[HttpServer, ...] = runner.wait_for_http()
        sleep(Constants.settle_seconds)
        return runner.http_servers or first

    @staticmethod
    def _explain(*, error: Exception) -> str:
        """Turn a failure into a sentence a person can act on.

        Args:
            error: Failure raised while starting or detecting.

        Returns:
            Plain explanation.

        """
        if isinstance(error, FileNotFoundError):
            return f"The program was not found: {error.filename}."
        if isinstance(error, PermissionError):
            return f"The program could not be run: {error.filename}."
        if isinstance(error, TimeoutError):
            limit: float = Constants.start_timeout
            return (
                "The service did not start serving HTTP in"
                f" {limit:.0f} seconds."
            )
        return str(object=error)

    def _folder(self, *, target: Target) -> Path:
        """Resolve the working directory and keep it inside the project.

        Args:
            target: Service-mode target.

        Returns:
            Existing directory under the project folder.

        Raises:
            ValueError: When it escapes the project or does not exist.

        """
        base: Path = self._root.resolve()
        folder: Path = (base / target.cwd).resolve()
        if not folder.is_relative_to(base) or not folder.is_dir():
            msg: str = (
                "The working directory must be an existing project folder."
            )
            raise ValueError(msg)
        return folder

    def _run(self, *, runner: HttpProcess, target: Target) -> None:
        """Start the process, wait for HTTP and publish what was found.

        Args:
            runner: Process owner created by ``start``.
            target: Service-mode target being started.

        """
        try:
            _ = runner.start()
            servers: tuple[HttpServer, ...] = self._detect(
                runner=runner,
                port=target.service_port,
            )
        except (OSError, RuntimeError, TimeoutError) as error:
            if not self._stopping:
                runner.stop()
                self._fail(runner=runner, text=self._explain(error=error))
            return
        chosen: HttpServer = best_server(servers=servers)
        with self._lock:
            if self._runner is not runner:
                return
            candidates: list[JsonValue] = [
                _candidate(server=item) for item in servers
            ]
            self._state = {
                **self._state,
                "state": "running",
                "url": chosen.url,
                "port": chosen.port,
                "pid": runner.pid,
                "candidates": candidates,
            }
        self._publish()

    def _fail(self, *, runner: HttpProcess, text: str) -> None:
        """Record a failed start unless the user already stopped it.

        Args:
            runner: Process owner that failed.
            text: Explanation shown to the user.

        """
        with self._lock:
            if self._runner is not runner:
                return
            self._runner = None
            self._state = {
                "state": "failed",
                "command": self._state.get("command", []),
                "error": text,
            }
        self._publish()

    def _publish(self) -> None:
        """Report the latest state through the service's serialized channel."""
        self._emit(
            cast(
                typ="Event",
                val={"type": "target_service", **self.snapshot()},
            ),
        )
