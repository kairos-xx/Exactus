# Copyright (c) 2026
"""Registry-free process identification for Exactus.

Expose authenticated run metadata through a private loopback listener.

Discovery uses operating-system process and listening-socket enumeration.
No registry, PID file, persistent socket, or discovery database is required.

Both the controller and responders must receive the same private secret.
Never expose this secret in command-line arguments or process metadata.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest, new
from json import dumps, loads
from math import isfinite
from os import getpid, urandom
from secrets import token_hex
from socket import (
    AF_INET,
    SO_REUSEADDR,
    SOCK_STREAM,
    SOL_SOCKET,
    create_connection,
    socket,
)
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, ClassVar, Final, Self, final

from psutil import Error, Process, process_iter

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType


@final
class ProcessConstants:
    """Immutable process-control configuration.

    Attributes:
        application: Exactus application identifier.
        protocol: Supported wire-protocol version.
        host: Private loopback interface.
        timeout: Default network timeout.
        workers: Default discovery concurrency.
        max_workers: Maximum discovery concurrency.
        max_message: Maximum JSON message size.
        min_authkey: Minimum authentication-key length.
        backlog: Maximum queued connections.
        accept_timeout: Listener polling interval.
        shutdown_timeout: Maximum responder shutdown wait.
        nonce_bytes: Authentication challenge size.
        header_bytes: Message length-prefix size.
        buffer_bytes: Maximum single socket-read size.
        instance_bytes: Raw instance-identifier entropy.

    """

    application: Final[str] = "exactus"
    protocol: Final[int] = 1
    host: Final[str] = "127.0.0.1"
    timeout: Final[float] = 0.3
    workers: Final[int] = 32
    max_workers: Final[int] = 128
    max_message: Final[int] = 65536
    min_authkey: Final[int] = 32
    backlog: Final[int] = 16
    accept_timeout: Final[float] = 0.2
    shutdown_timeout: Final[float] = 2.0
    nonce_bytes: Final[int] = 32
    header_bytes: Final[int] = 4
    buffer_bytes: Final[int] = 4096
    instance_bytes: Final[int] = 16


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class RunIdentity:
    """Immutable identity of an Exactus root process.

    Attributes:
        root_pid: Operating-system process identifier.
        run_id: Exactus unified-run identifier.
        runs_db: Absolute runtime database path.
        created_at: Operating-system process creation timestamp.
        instance_id: Unique responder-instance identifier.
        application: Application identifier.
        protocol_version: Wire-protocol version.

    """

    root_pid: int
    run_id: str
    runs_db: str
    created_at: float
    instance_id: str
    application: str = "exactus"
    protocol_version: int = 1


type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)


@final
class IdentityResponder:
    """Expose Exactus process metadata without a centralized registry.

    Attributes:
        constants: Process-control configuration.
        identity: Immutable run identity advertised by this responder.

    """

    constants: ClassVar[ProcessConstants] = ProcessConstants()

    def __init__(
        self,
        *,
        run_id: str,
        runs_db: Path,
        authkey: bytes,
        timeout: float = 0.3,
    ) -> None:
        """Initialize an authenticated identity responder.

        Args:
            run_id: Active Exactus run identifier.
            runs_db: Active runtime SQLite database path.
            authkey: Private shared authentication secret.
            timeout: Per-connection timeout.

        Raises:
            ValueError: If configuration is invalid.

        """
        if not run_id:
            msg: str = "Run identifier must not be empty"
            raise ValueError(msg)
        if len(authkey) < self.constants.min_authkey:
            msg = (
                f"Authentication key must contain at least "
                f"{self.constants.min_authkey} bytes"
            )
            raise ValueError(msg)
        if not isfinite(timeout) or timeout <= 0:
            msg = "Timeout must be positive and finite"
            raise ValueError(msg)
        self.identity: RunIdentity = RunIdentity(
            root_pid=getpid(),
            run_id=run_id,
            runs_db=str(object=runs_db.resolve()),
            created_at=Process(pid=getpid()).create_time(),
            instance_id=token_hex(nbytes=self.constants.instance_bytes),
        )
        self._authkey: bytes = authkey
        self._timeout: float = timeout
        self._socket: socket | None = None
        self._thread: Thread | None = None
        self._stopping: Event = Event()
        self._lock: Lock = Lock()
        self._started: bool = False
        self._closed: bool = False

    @property
    def running(self) -> bool:
        """Return whether the responder is accepting requests.

        Returns:
            Whether the responder is accepting requests.

        """
        return (
            getpid() == self.identity.root_pid
            and self._thread is not None
            and self._thread.is_alive()
            and not self._stopping.is_set()
        )

    @property
    def port(self) -> int | None:
        """Return the active private loopback port.

        Returns:
            The active loopback port, or None when stopped.

        """
        if self._socket is None:
            return None
        return self._socket.getsockname()[1]

    def start(self) -> None:
        """Start the background responder.

        Raises:
            RuntimeError: If the responder was already started.
            OSError: If the listener cannot be initialized.

        """
        with self._lock:
            if getpid() != self.identity.root_pid:
                msg: str = "Cannot start an inherited responder in a child"
                raise RuntimeError(msg)
            if self._started or self._closed:
                msg = "Responder cannot be started more than once"
                raise RuntimeError(msg)
            listener: socket = socket(family=AF_INET, type=SOCK_STREAM)
            try:
                listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                listener.bind((self.constants.host, 0))
                listener.listen(self.constants.backlog)
                listener.settimeout(self.constants.accept_timeout)
                self._socket = listener
                self._thread = Thread(
                    target=self._serve,
                    name="exactus-identity",
                    daemon=False,
                )
                self._thread.start()
                self._started = True
            except (OSError, RuntimeError):
                listener.close()
                self._socket = None
                self._thread = None
                raise

    def close(self, *, timeout: float = 2.0) -> None:
        """Stop the responder and release its listener.

        Args:
            timeout: Maximum time to wait for the listener thread.

        Raises:
            ValueError: If the timeout is invalid.
            TimeoutError: If the responder cannot stop in time.

        """
        if not isfinite(timeout) or timeout <= 0:
            msg: str = "Timeout must be positive and finite"
            raise ValueError(msg)
        with self._lock:
            if self._closed or getpid() != self.identity.root_pid:
                return
            self._stopping.set()
            if self._socket is not None:
                self._socket.close()
            if self._thread is not None:
                self._thread.join(timeout=timeout)
                if self._thread.is_alive():
                    msg = "Identity responder did not stop"
                    raise TimeoutError(msg)
            self._socket = None
            self._thread = None
            self._closed = True

    def __enter__(self) -> Self:
        """Start the responder on context entry.

        Returns:
            The started responder.

        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Stop the responder on context exit.

        Args:
            exc_type: Exception type raised in the block, if any.
            exc: Exception raised in the block, if any.
            tb: Traceback for the exception, if any.

        """
        self.close()

    def _serve(self) -> None:
        """Accept requests while the responder is active."""
        listener: socket | None = self._socket
        if listener is None:
            return
        while not self._stopping.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stopping.is_set():
                    break
                continue
            with connection:
                connection.settimeout(self._timeout)
                try:
                    self._handle(connection=connection)
                except (TimeoutError, OSError, ValueError):
                    continue

    def _handle(self, *, connection: socket) -> None:
        """Authenticate and answer one identity request.

        Args:
            connection: Accepted loopback connection.

        Raises:
            OSError: If socket communication fails.
            ValueError: If the request is malformed.

        """
        nonce: bytes = urandom(self.constants.nonce_bytes)
        connection.sendall(nonce)
        expected: bytes = new(
            key=self._authkey,
            msg=nonce,
            digestmod=sha256,
        ).digest()
        received: bytes | None = _receive(
            connection=connection,
            size=len(expected),
            limit=self.constants.buffer_bytes,
        )
        if received is None:
            return
        if not compare_digest(received, expected):
            return
        payload: bytes = dumps(
            obj={
                "application": self.identity.application,
                "protocol_version": self.identity.protocol_version,
                "root_pid": self.identity.root_pid,
                "run_id": self.identity.run_id,
                "runs_db": self.identity.runs_db,
                "created_at": self.identity.created_at,
                "instance_id": self.identity.instance_id,
            },
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode(encoding="utf-8")
        if len(payload) > self.constants.max_message:
            msg: str = "Identity response exceeds maximum message size"
            raise ValueError(msg)
        connection.sendall(
            len(payload).to_bytes(
                length=self.constants.header_bytes,
                byteorder="big",
            )
            + payload,
        )


def _validate_access(
    *,
    authkey: bytes,
    timeout: float,
    constants: ProcessConstants,
) -> None:
    """Validate shared authentication credentials and timeout.

    Args:
        authkey: Shared authentication secret.
        timeout: Socket operation timeout.
        constants: Process-control configuration.

    Raises:
        ValueError: If authentication or timeout is invalid.

    """
    if len(authkey) < constants.min_authkey:
        msg: str = "Authentication key is too short"
        raise ValueError(msg)
    if not isfinite(timeout) or timeout <= 0:
        msg = "Timeout must be positive and finite"
        raise ValueError(msg)


def _receive(*, connection: socket, size: int, limit: int) -> bytes | None:
    """Read an exact number of bytes from a connection.

    Args:
        connection: Active socket connection.
        size: Exact number of bytes required.
        limit: Maximum single socket-read size.

    Returns:
        The requested bytes, or None when the peer disconnects early.

    """
    data: bytes = b""
    while len(data) < size:
        chunk: bytes = connection.recv(min(limit, size - len(data)))
        if not chunk:
            return None
        data += chunk
    return data


def _listening_ports(
    *,
    process: Process,
    port: int | None,
    constants: ProcessConstants,
) -> list[int]:
    """Return candidate private loopback ports for a process.

    Args:
        process: Candidate operating-system process.
        port: Known listening port, or None to enumerate all.
        constants: Process-control configuration.

    Returns:
        Candidate loopback listening ports.

    """
    if port is not None:
        return [port]
    return [
        connection.laddr.port
        for connection in process.net_connections(kind="tcp")
        if (
            connection.status == "LISTEN"
            and connection.laddr.ip == constants.host
        )
    ]


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class _Candidate:
    """Candidate process under interrogation.

    Attributes:
        process: Operating-system process handle.
        created_at: Expected process creation timestamp.

    """

    process: Process
    created_at: float


def _claims_match(
    *,
    claims: dict[str, JsonValue],
    candidate: _Candidate,
    constants: ProcessConstants,
) -> bool:
    """Return whether responder claims match the candidate process.

    Args:
        claims: Decoded responder metadata.
        candidate: Process under interrogation.
        constants: Process-control configuration.

    Returns:
        Whether every responder claim matches the process.

    """
    return all(
        (
            claims.get("application") == constants.application,
            claims.get("protocol_version") == constants.protocol,
            type(claims.get("root_pid")) is int,
            claims.get("root_pid") == candidate.process.pid,
            type(claims.get("created_at")) in (int, float),
            claims.get("created_at") == candidate.created_at,
            candidate.process.is_running(),
            candidate.process.create_time() == candidate.created_at,
        ),
    )


def _verified(
    *,
    decoded: JsonValue,
    candidate: _Candidate,
    constants: ProcessConstants,
) -> RunIdentity | None:
    """Build a verified identity from a decoded responder payload.

    Args:
        decoded: Decoded JSON response payload.
        candidate: Process under interrogation.
        constants: Process-control configuration.

    Returns:
        Verified Exactus identity or None.

    """
    if not isinstance(decoded, dict):
        return None
    claims: dict[str, JsonValue] = decoded
    run_id: JsonValue = claims.get("run_id")
    runs_db: JsonValue = claims.get("runs_db")
    instance_id: JsonValue = claims.get("instance_id")
    if (
        not isinstance(run_id, str)
        or not run_id
        or not isinstance(runs_db, str)
        or not runs_db
        or not isinstance(instance_id, str)
        or len(instance_id) != constants.instance_bytes * 2
        or not _claims_match(
            claims=claims,
            candidate=candidate,
            constants=constants,
        )
    ):
        return None
    return RunIdentity(
        root_pid=candidate.process.pid,
        run_id=run_id,
        runs_db=runs_db,
        created_at=candidate.created_at,
        instance_id=instance_id,
    )


def _interrogate(
    *,
    port: int,
    authkey: bytes,
    timeout: float,
    candidate: _Candidate,
    constants: ProcessConstants,
) -> RunIdentity | None:
    """Attempt one authenticated identity handshake on a port.

    Args:
        port: Candidate loopback listening port.
        authkey: Shared authentication secret.
        timeout: Socket operation timeout.
        candidate: Process under interrogation.
        constants: Process-control configuration.

    Returns:
        Verified Exactus identity or None.

    """
    try:
        with create_connection(
            address=(constants.host, port),
            timeout=timeout,
        ) as connection:
            connection.settimeout(timeout)
            nonce: bytes | None = _receive(
                connection=connection,
                size=constants.nonce_bytes,
                limit=constants.buffer_bytes,
            )
            if nonce is None:
                return None
            connection.sendall(
                new(key=authkey, msg=nonce, digestmod=sha256).digest(),
            )
            header: bytes | None = _receive(
                connection=connection,
                size=constants.header_bytes,
                limit=constants.buffer_bytes,
            )
            if header is None:
                return None
            size: int = int.from_bytes(bytes=header, byteorder="big")
            if not 0 < size <= constants.max_message:
                return None
            payload: bytes | None = _receive(
                connection=connection,
                size=size,
                limit=constants.buffer_bytes,
            )
            if payload is None:
                return None
            decoded: JsonValue = loads(s=payload.decode(encoding="utf-8"))
            return _verified(
                decoded=decoded,
                candidate=candidate,
                constants=constants,
            )
    except (TimeoutError, UnicodeError, OSError, ValueError, Error):
        return None


def identify(
    *,
    pid: int,
    authkey: bytes,
    timeout: float = 0.3,
    port: int | None = None,
) -> RunIdentity | None:
    """Interrogate a candidate Exactus process.

    Args:
        pid: Candidate operating-system process identifier.
        authkey: Shared authentication secret.
        timeout: Maximum socket operation timeout.
        port: Known listening port, or None to discover candidate ports.

    Returns:
        Verified Exactus identity or None.

    Raises:
        ValueError: If configuration is invalid.

    """
    constants: ProcessConstants = ProcessConstants()
    _validate_access(authkey=authkey, timeout=timeout, constants=constants)
    if pid <= 0:
        return None
    try:
        process: Process = Process(pid=pid)
        candidate: _Candidate = _Candidate(
            process=process,
            created_at=process.create_time(),
        )
        ports: list[int] = _listening_ports(
            process=process,
            port=port,
            constants=constants,
        )
    except (OSError, Error):
        return None
    for candidate_port in ports:
        identity: RunIdentity | None = _interrogate(
            port=candidate_port,
            authkey=authkey,
            timeout=timeout,
            candidate=candidate,
            constants=constants,
        )
        if identity is not None:
            return identity
    return None


def _listen_table(*, constants: ProcessConstants) -> dict[int, set[int]]:
    """Collect private loopback listeners grouped by process.

    Args:
        constants: Process-control configuration.

    Returns:
        Listening ports grouped by operating-system process identifier.

    """
    candidates: dict[int, set[int]] = {}
    for process in process_iter():
        try:
            for connection in process.net_connections(kind="tcp"):
                if (
                    connection.status != "LISTEN"
                    or not connection.laddr
                    or connection.laddr.ip != constants.host
                ):
                    continue
                candidates.setdefault(process.pid, set()).add(
                    connection.laddr.port,
                )
        except (OSError, Error):
            continue
    return candidates


def _exactus_candidates(
    *,
    candidates: dict[int, set[int]],
    constants: ProcessConstants,
) -> dict[int, set[int]]:
    """Keep processes resembling Exactus or Python interpreters.

    Args:
        candidates: Listening ports grouped by process identifier.
        constants: Process-control configuration.

    Returns:
        Filtered listening ports grouped by process identifier.

    """
    filtered: dict[int, set[int]] = {}
    for pid, ports in candidates.items():
        try:
            process: Process = Process(pid=pid)
            name: str = process.name().lower()
            command: str = " ".join(process.cmdline()).lower()
            if (
                "python" in name
                or constants.application in name
                or constants.application in command
            ):
                filtered[pid] = ports
        except (OSError, Error):
            continue
    return filtered


def _scan(
    *,
    candidates: dict[int, set[int]],
    authkey: bytes,
    timeout: float,
    workers: int,
) -> list[RunIdentity]:
    """Interrogate candidate ports concurrently.

    Args:
        candidates: Listening ports grouped by process identifier.
        authkey: Shared authentication secret.
        timeout: Per-socket operation timeout.
        workers: Maximum concurrent interrogation workers.

    Returns:
        Verified identities sorted by process identifier.

    """
    identities: dict[int, RunIdentity] = {}
    with ThreadPoolExecutor(
        max_workers=min(workers, len(candidates)),
        thread_name_prefix="exactus-discovery",
    ) as executor:
        futures: dict[Future[RunIdentity | None], int] = {
            executor.submit(
                identify,
                pid=pid,
                authkey=authkey,
                timeout=timeout,
                port=port,
            ): pid
            for pid, ports in candidates.items()
            for port in ports
        }
        for future in as_completed(fs=futures):
            try:
                identity: RunIdentity | None = future.result()
            except (OSError, Error, ValueError):
                continue
            if identity is not None:
                identities[identity.root_pid] = identity
    return sorted(identities.values(), key=lambda identity: identity.root_pid)


def discover(
    *,
    authkey: bytes,
    timeout: float = 0.3,
    workers: int = 32,
    full_scan: bool = True,
) -> list[RunIdentity]:
    """Discover running Exactus processes without a registry.

    Args:
        authkey: Shared private authentication secret.
        timeout: Per-socket operation timeout.
        workers: Maximum concurrent interrogation workers.
        full_scan: Whether to include all visible listening processes.

    Returns:
        Verified identities sorted by process identifier.

    Raises:
        ValueError: If configuration is invalid.

    """
    constants: ProcessConstants = ProcessConstants()
    _validate_access(authkey=authkey, timeout=timeout, constants=constants)
    if not 1 <= workers <= constants.max_workers:
        msg: str = f"Workers must be between 1 and {constants.max_workers}"
        raise ValueError(msg)
    candidates: dict[int, set[int]] = _listen_table(constants=constants)
    if not full_scan:
        candidates = _exactus_candidates(
            candidates=candidates,
            constants=constants,
        )
    if not candidates:
        return []
    return _scan(
        candidates=candidates,
        authkey=authkey,
        timeout=timeout,
        workers=workers,
    )
