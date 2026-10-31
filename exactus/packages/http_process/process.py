"""Run processes and inspect HTTP servers and their owning processes."""

from dataclasses import dataclass
from enum import StrEnum
from http import client
from ipaddress import IPv4Address, IPv6Address, ip_address
from pathlib import Path
from socket import AddressFamily
from subprocess import DEVNULL, Popen
from time import monotonic, sleep
from typing import Final, final

from psutil import (
    CONN_LISTEN,
    Error,
    Process,
    net_connections,
    net_if_addrs,
    wait_procs,
)

type IpAddress = IPv4Address | IPv6Address


@final
class Constants:
    """Group module-level constants.

    Attributes:
        port_max: Grouped module constant.

    """

    port_max: Final = 65535


class BindScope(StrEnum):
    """Network scope represented by a socket bind address.

    Attributes:
        LOOPBACK: The listener only accepts local connections.
        WILDCARD: The listener accepts connections on every interface.
        SPECIFIC: The listener accepts connections on one local address.

    """

    LOOPBACK = "loopback"
    WILDCARD = "wildcard"
    SPECIFIC = "specific"


class IpFamily(StrEnum):
    """IP address family used by a listener.

    Attributes:
        IPV4: The listener uses an IPv4 address.
        IPV6: The listener uses an IPv6 address.

    """

    IPV4 = "ipv4"
    IPV6 = "ipv6"


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Describe a process owning a network listener.

    Attributes:
        pid: Process identifier.
        ppid: Parent process identifier.
        name: Process name.
        executable: Path of the program, when readable.
        command: Command line arguments.
        username: Account running the process, when readable.
        create_time: Start time as seconds since the epoch, when readable.

    """

    pid: int
    ppid: int
    name: str
    executable: Path | None
    command: tuple[str, ...]
    username: str | None
    create_time: float | None


@dataclass(frozen=True, slots=True)
class Listener:
    """Describe a TCP listener owned by a process.

    Attributes:
        pid: Owning process identifier.
        bind_host: Address the socket is bound to.
        port: Port the socket listens on.
        scope: Network scope implied by the bind address.
        family: IP family implied by the bind address.

    """

    pid: int
    bind_host: str
    port: int
    scope: BindScope
    family: IpFamily


@dataclass(frozen=True, slots=True)
class HttpServer:
    """Describe a verified HTTP server.

    Attributes:
        bind_host: Address the socket is bound to.
        probe_host: Address clients should connect to.
        port: Port the server listens on.
        scope: Network scope implied by the bind address.
        family: IP family implied by the bind address.
        url: Base URL of the server.
        status: HTTP status the server answered with.
        reason: HTTP reason phrase the server answered with.
        process: Owning process, when it can be resolved locally.

    """

    bind_host: str
    probe_host: str
    port: int
    scope: BindScope
    family: IpFamily
    url: str
    status: int
    reason: str
    process: ProcessInfo | None

    @property
    def pid(self) -> int | None:
        """Return the owning process identifier when available.

        Returns:
            Process identifier, or None when it cannot be resolved.
        """
        return None if self.process is None else self.process.pid

    @property
    def localhost_only(self) -> bool:
        """Return whether the server is restricted to loopback.

        Returns:
            True when the server only accepts local connections.
        """
        return self.scope is BindScope.LOOPBACK

    @property
    def all_interfaces(self) -> bool:
        """Return whether the server listens on wildcard interfaces.

        Returns:
            True when the server accepts connections on every interface.
        """
        return self.scope is BindScope.WILDCARD

    @property
    def specific_ip(self) -> bool:
        """Return whether the server is bound to one non-loopback IP.

        Returns:
            True when the server accepts connections on one local address.
        """
        return self.scope is BindScope.SPECIFIC


@dataclass(frozen=True, slots=True)
class HttpInspection:
    """Describe the result of inspecting an IP address and TCP port.

    Attributes:
        host: Address that was inspected.
        port: Port that was inspected.
        tcp_open: Whether a TCP connection was accepted.
        http: Whether an HTTP response was received.
        url: URL that was probed.
        status: HTTP status answered, when a response was received.
        reason: HTTP reason phrase answered, when a response was received.
        process: Owning process, when it can be resolved locally.

    """

    host: str
    port: int
    tcp_open: bool
    http: bool
    url: str
    status: int | None
    reason: str | None
    process: ProcessInfo | None

    @property
    def pid(self) -> int | None:
        """Return the owning process identifier when available.

        Returns:
            Process identifier, or None when it cannot be resolved.
        """
        return None if self.process is None else self.process.pid


class HttpProcess:
    """Run processes and inspect HTTP network listeners."""

    def __init__(
        self,
        command: list[str] | None = None,
        *,
        timeout: float = 30.0,
        poll_interval: float = 0.1,
        http_timeout: float = 0.5,
        cwd: Path | str | None = None,
    ) -> None:
        """Configure process execution and HTTP discovery.

        Args:
            command: Optional command and arguments used to start a process.
            timeout: Maximum number of seconds to wait for discovery.
            poll_interval: Delay between discovery attempts.
            http_timeout: Maximum duration of individual HTTP probes.
            cwd: Working directory for the started process; the caller's
                directory when omitted.

        Raises:
            ValueError: If a supplied command or timeout is invalid.
        """
        if command is not None and (not command):
            msg: str = "command must contain at least one element"
            raise ValueError(msg)
        if timeout <= 0.0:
            msg = "timeout must be greater than zero"
            raise ValueError(msg)
        if poll_interval <= 0.0:
            msg = "poll_interval must be greater than zero"
            raise ValueError(msg)
        if http_timeout <= 0.0:
            msg = "http_timeout must be greater than zero"
            raise ValueError(msg)
        self.command: tuple[str, ...] | None = (
            None if command is None else tuple(command)
        )
        self.timeout: float = timeout
        self.poll_interval: float = poll_interval
        self.http_timeout: float = http_timeout
        self.cwd: Path | None = None if cwd is None else Path(cwd)
        self.process: Popen[bytes] | None = None

    @property
    def pid(self) -> int | None:
        """Return the managed root process identifier.

        Returns:
            Process identifier, or None when no process was started.
        """
        return None if self.process is None else self.process.pid

    @property
    def running(self) -> bool:
        """Return whether the managed root process is running.

        Returns:
            True while the started process has not exited.
        """
        return self.process is not None and self.process.poll() is None

    @property
    def listeners(self) -> tuple[Listener, ...]:
        """Return TCP listeners owned by the managed process tree.

        Returns:
            TCP listeners belonging to the managed process tree.
        """
        if self.process is None:
            return ()
        discovered: dict[tuple[int, str, int], Listener] = {}
        for process in self._processes():
            try:
                for connection in process.net_connections(kind="tcp"):
                    if (
                        connection.status != CONN_LISTEN
                        or not connection.laddr
                    ):
                        continue
                    host: str = connection.laddr.ip
                    port: int = connection.laddr.port
                    address: IpAddress = ip_address(address=host)
                    discovered[process.pid, host, port] = Listener(
                        pid=process.pid,
                        bind_host=host,
                        port=port,
                        scope=self._bind_scope(address=address),
                        family=self._ip_family(address=address),
                    )
            except Error:
                continue
        return tuple(
            sorted(
                discovered.values(),
                key=lambda item: (item.pid, item.bind_host, item.port),
            ),
        )

    @property
    def http_servers(self) -> tuple[HttpServer, ...]:
        """Return verified HTTP servers owned by the process tree.

        Returns:
            HTTP servers belonging to the managed process tree.
        """
        return tuple(
            server
            for listener in self.listeners
            if (server := self._probe_listener(listener=listener)) is not None
        )

    @property
    def ports(self) -> tuple[int, ...]:
        """Return unique TCP listening ports owned by the process tree.

        Returns:
            Sorted listening ports owned by the managed process tree.
        """
        return tuple(sorted({listener.port for listener in self.listeners}))

    @property
    def http_ports(self) -> tuple[int, ...]:
        """Return unique verified HTTP ports.

        Returns:
            Sorted ports answering HTTP owned by the managed tree.
        """
        return tuple(sorted({server.port for server in self.http_servers}))

    @property
    def bound_addresses(self) -> tuple[str, ...]:
        """Return unique addresses used by owned TCP listeners.

        Returns:
            Sorted bind addresses used by owned TCP listeners.
        """
        return tuple(
            sorted({listener.bind_host for listener in self.listeners}),
        )

    @property
    def urls(self) -> tuple[str, ...]:
        """Return URLs belonging to verified HTTP servers.

        Returns:
            URLs answered by owned HTTP servers.
        """
        return tuple(server.url for server in self.http_servers)

    @property
    def localhost_servers(self) -> tuple[HttpServer, ...]:
        """Return HTTP servers restricted to loopback.

        Returns:
            Verified HTTP servers bound to loopback addresses.
        """
        return tuple(
            server
            for server in self.http_servers
            if server.scope is BindScope.LOOPBACK
        )

    @property
    def wildcard_servers(self) -> tuple[HttpServer, ...]:
        """Return HTTP servers bound to wildcard addresses.

        Returns:
            Verified HTTP servers bound to wildcard addresses.
        """
        return tuple(
            server
            for server in self.http_servers
            if server.scope is BindScope.WILDCARD
        )

    @property
    def specific_ip_servers(self) -> tuple[HttpServer, ...]:
        """Return servers bound to specific non-loopback addresses.

        Returns:
            Verified HTTP servers bound to one local address.
        """
        return tuple(
            server
            for server in self.http_servers
            if server.scope is BindScope.SPECIFIC
        )

    def start(self) -> Popen[bytes]:
        """Start the configured process.

        Returns:
            Started subprocess.

        Raises:
            RuntimeError: If no command exists or the process was started.
        """
        if self.command is None:
            msg: str = "no command was configured"
            raise RuntimeError(msg)
        if self.process is not None:
            msg = "process has already been started"
            raise RuntimeError(msg)
        self.process = Popen(
            args=self.command,
            stdout=DEVNULL,
            stderr=DEVNULL,
            cwd=self.cwd,
        )
        return self.process

    def inspect(self, *, host: str, port: int) -> HttpInspection:
        """Inspect an address for an HTTP server and local process owner.

        Args:
            host: IPv4 or IPv6 address to inspect.
            port: TCP port to inspect.

        Returns:
            HTTP inspection result.
        """
        address: IpAddress = ip_address(address=host)
        self._validate_port(port=port)
        normalized_host: str = str(object=address)
        url: str = self._url(host=normalized_host, port=port)
        connection: client.HTTPConnection = client.HTTPConnection(
            host=normalized_host,
            port=port,
            timeout=self.http_timeout,
        )
        try:
            connection.connect()
        except OSError:
            connection.close()
            return HttpInspection(
                host=normalized_host,
                port=port,
                tcp_open=False,
                http=False,
                url=url,
                status=None,
                reason=None,
                process=None,
            )
        try:
            connection.request(method="HEAD", url="/")
            response: client.HTTPResponse = connection.getresponse()
            response.read()
        except (OSError, client.HTTPException):
            return HttpInspection(
                host=normalized_host,
                port=port,
                tcp_open=True,
                http=False,
                url=url,
                status=None,
                reason=None,
                process=self._find_process(host=normalized_host, port=port),
            )
        finally:
            connection.close()
        return HttpInspection(
            host=normalized_host,
            port=port,
            tcp_open=True,
            http=True,
            url=url,
            status=response.status,
            reason=response.reason,
            process=self._find_process(host=normalized_host, port=port),
        )

    def is_http(self, *, host: str, port: int) -> bool:
        """Return whether an address is serving HTTP.

        Args:
            host: IPv4 or IPv6 address.
            port: TCP port.

        Returns:
            True when an HTTP response is received.
        """
        return self.inspect(host=host, port=port).http

    def process_at(self, *, host: str, port: int) -> ProcessInfo | None:
        """Return the local process owning an address and port.

        Args:
            host: IPv4 or IPv6 listener address.
            port: TCP listener port.

        Returns:
            Owning local process, or None when ownership cannot be resolved.
        """
        address: IpAddress = ip_address(address=host)
        self._validate_port(port=port)
        return self._find_process(host=str(object=address), port=port)

    def wait_for_http(self) -> tuple[HttpServer, ...]:
        """Wait until at least one owned HTTP server is detected.

        Returns:
            HTTP servers detected during discovery.

        Raises:
            RuntimeError: If no process exists or it exits before discovery.
            TimeoutError: If no HTTP server appears before the timeout.
        """
        if self.process is None:
            msg: str = "process has not been started"
            raise RuntimeError(msg)
        deadline: float = monotonic() + self.timeout
        while monotonic() < deadline:
            if servers := self.http_servers:
                return servers
            if self.process.poll() is not None:
                msg = (
                    f"process exited with code {self.process.returncode} "
                    "before opening an HTTP server"
                )
                raise RuntimeError(msg)
            sleep(self.poll_interval)
        msg = f"no HTTP server was detected within {self.timeout:.3f} seconds"
        raise TimeoutError(msg)

    def wait_for_listener(self) -> tuple[Listener, ...]:
        """Wait until at least one owned TCP listener is detected.

        Returns:
            TCP listeners detected during discovery.

        Raises:
            RuntimeError: If no process exists or it exits before discovery.
            TimeoutError: If no listener appears before the timeout.
        """
        if self.process is None:
            msg: str = "process has not been started"
            raise RuntimeError(msg)
        deadline: float = monotonic() + self.timeout
        while monotonic() < deadline:
            if listeners := self.listeners:
                return listeners
            if self.process.poll() is not None:
                msg = (
                    f"process exited with code {self.process.returncode} "
                    "before opening a TCP listener"
                )
                raise RuntimeError(msg)
            sleep(self.poll_interval)
        msg = f"no TCP listener was detected within {self.timeout:.3f} seconds"
        raise TimeoutError(msg)

    def wait_for(self, *, host: str, port: int) -> HttpInspection:
        """Wait until an address starts serving HTTP.

        Args:
            host: IPv4 or IPv6 address.
            port: TCP port.

        Returns:
            Successful HTTP inspection result.

        Raises:
            TimeoutError: If HTTP is not detected before the timeout.
        """
        deadline: float = monotonic() + self.timeout
        while monotonic() < deadline:
            if (result := self.inspect(host=host, port=port)).http:
                return result
            sleep(self.poll_interval)
        msg: str = (
            f"http://{host}:{port} did not start "
            "serving HTTP within {self.timeout:.3f} seconds"
        )
        raise TimeoutError(msg)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Terminate the managed process tree.

        Args:
            timeout: Seconds allowed for graceful termination.
        """
        if self.process is None:
            return
        processes: tuple[Process, ...] = self._processes()
        for process in reversed(processes):
            try:
                process.terminate()
            except Error:
                continue
        _, alive = wait_procs(procs=list(processes), timeout=timeout)
        for process in alive:
            try:
                process.kill()
            except Error:
                continue
        self.process.wait(timeout=timeout)
        self.process = None

    @staticmethod
    def _process_info(*, pid: int) -> ProcessInfo | None:
        """Collect process information.

        Args:
            pid: Process identifier.

        Returns:
            Process information when accessible.
        """
        try:
            process: Process = Process(pid=pid)
            with process.oneshot():
                executable_text: str = process.exe()
                return ProcessInfo(
                    pid=process.pid,
                    ppid=process.ppid(),
                    name=process.name(),
                    executable=(
                        Path(executable_text) if executable_text else None
                    ),
                    command=tuple(process.cmdline()),
                    username=process.username(),
                    create_time=process.create_time(),
                )
        except Error:
            return None

    @staticmethod
    def _is_local_address(*, address: IpAddress) -> bool:
        """Return whether an address belongs to the current machine.

        Args:
            address: Address to inspect.

        Returns:
            True for loopback or a configured local interface address.
        """
        if address.is_loopback:
            return True
        try:
            return any(
                ip_address(address=item.address.split(sep="%", maxsplit=1)[0])
                == address
                for addresses in net_if_addrs().values()
                for item in addresses
                if item.family
                in {AddressFamily.AF_INET, AddressFamily.AF_INET6}
            )
        except Error:
            return False

    @staticmethod
    def _validate_port(*, port: int) -> None:
        """Validate a TCP port.

        Args:
            port: Port to validate.

        Raises:
            ValueError: If the port is outside the valid TCP range.
        """
        if not 1 <= port <= Constants.port_max:
            msg: str = f"port must be between 1 and {Constants.port_max}"
            raise ValueError(msg)

    @staticmethod
    def _bind_scope(*, address: IpAddress) -> BindScope:
        """Classify the scope of an IP bind address.

        Args:
            address: Address to classify.

        Returns:
            Bind scope.
        """
        if address.is_loopback:
            return BindScope.LOOPBACK
        if address.is_unspecified:
            return BindScope.WILDCARD
        return BindScope.SPECIFIC

    @staticmethod
    def _ip_family(*, address: IpAddress) -> IpFamily:
        """Return the IP family of an address.

        Args:
            address: Address to classify.

        Returns:
            IPv4 or IPv6 family.
        """
        return (
            IpFamily.IPV4
            if isinstance(address, IPv4Address)
            else IpFamily.IPV6
        )

    @staticmethod
    def _probe_host(*, host: str) -> str:
        """Convert wildcard addresses to locally connectable addresses.

        Args:
            host: Listener bind address.

        Returns:
            Address suitable for a local connection.
        """
        address: IpAddress = ip_address(address=host)
        if not address.is_unspecified:
            return host
        return "127.0.0.1" if isinstance(address, IPv4Address) else "::1"

    @staticmethod
    def _url(*, host: str, port: int) -> str:
        """Construct an HTTP URL.

        Args:
            host: IPv4 or IPv6 address.
            port: TCP port.

        Returns:
            Properly formatted HTTP URL.
        """
        address: IpAddress = ip_address(address=host)
        formatted_host: str = (
            f"[{host}]" if isinstance(address, IPv6Address) else host
        )
        return f"http://{formatted_host}:{port}"

    def _processes(self) -> tuple[Process, ...]:
        """Return the root process and its descendants.

        Returns:
            Processes belonging to the managed process tree.
        """
        if self.process is None:
            return ()
        try:
            root: Process = Process(pid=self.process.pid)
            children: list[Process] = root.children(recursive=True)
        except Error:
            return ()
        return (root, *children)

    def _probe_listener(self, *, listener: Listener) -> HttpServer | None:
        """Determine whether a listener serves HTTP.

        Args:
            listener: Listener to inspect.

        Returns:
            HTTP server metadata, or None for a non-HTTP listener.
        """
        probe_host: str = self._probe_host(host=listener.bind_host)
        inspection: HttpInspection = self.inspect(
            host=probe_host,
            port=listener.port,
        )
        if not inspection.http or inspection.status is None:
            return None
        return HttpServer(
            bind_host=listener.bind_host,
            probe_host=probe_host,
            port=listener.port,
            scope=listener.scope,
            family=listener.family,
            url=inspection.url,
            status=inspection.status,
            reason=inspection.reason or "",
            process=self._process_info(pid=listener.pid),
        )

    def _find_process(self, *, host: str, port: int) -> ProcessInfo | None:
        """Find the local process owning a TCP listener.

        Args:
            host: Address being inspected.
            port: TCP port.

        Returns:
            Owning process information when locally resolvable.
        """
        target: IpAddress = ip_address(address=host)
        try:
            for connection in net_connections(kind="tcp"):
                if (
                    connection.status != CONN_LISTEN
                    or not connection.laddr
                    or connection.pid is None
                    or (connection.laddr.port != port)
                ):
                    continue
                bound: IpAddress = ip_address(address=connection.laddr.ip)
                if bound == target or (
                    bound.is_unspecified
                    and bound.version == target.version
                    and self._is_local_address(address=target)
                ):
                    return self._process_info(pid=connection.pid)
        except Error:
            pass
        return None
