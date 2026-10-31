"""Own local HTTP services used by visual-cause targets."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self
from urllib.parse import quote

from exactus.packages.server.local import serve, wait_ready
from exactus.tools.common.process_control import terminate_tree

if TYPE_CHECKING:
    from types import TracebackType


@dataclass(frozen=True, slots=True, kw_only=True)
class ServedPage:
    """Resolved browser URL and its optional server log.

    Attributes:
        url: URL the browser navigates to.
        log: Server log path, ``None`` for remote URLs.

    """

    url: str
    log: Path | None


@dataclass(slots=True, kw_only=True)
class _Server:
    """Track one running local file server.

    Attributes:
        directory: Served document root.
        pid: Server process identifier.
        base_url: Origin the server answers on.
        reused: Whether the process was adopted rather than started.
        log: Path the server logs to.

    """

    directory: Path
    pid: int
    base_url: str
    reused: bool
    log: Path


class LocalServices(AbstractContextManager["LocalServices"]):
    """Share servers by directory and terminate only owned processes."""

    def __init__(self, *, artifacts: Path, timeout_ms: int) -> None:
        """Initialize an empty per-target service registry.

        Args:
            artifacts: Directory receiving server logs.
            timeout_ms: Readiness timeout in milliseconds.

        """
        self._artifacts: Path = artifacts
        self._timeout_seconds: float = timeout_ms / 1000.0
        self._servers: dict[Path, _Server] = {}

    def page(
        self,
        *,
        url: str | None,
        html: Path | None,
        landing: str,
        label: str,
    ) -> ServedPage:
        """Return an unchanged remote URL or serve one local source.

        Args:
            url: Remote URL used directly when given.
            html: Local HTML file or directory to serve.
            landing: Landing document name for directory sources.
            label: Side label used in errors and log names.

        Returns:
            Resolved page URL plus its server log path.

        Raises:
            ValueError: If neither ``url`` nor ``html`` was given.
            FileNotFoundError: If the source or landing page is missing.
            RuntimeError: If the server does not become ready.

        """
        if url is not None:
            return ServedPage(url=url, log=None)
        if html is None:
            msg: str = f"{label}: missing page source."
            raise ValueError(msg)
        source: Path = html.resolve()
        if not source.exists():
            msg = f"{label}: HTML source not found: {source}"
            raise FileNotFoundError(msg)
        directory: Path = source if source.is_dir() else source.parent
        relative: str = landing if source.is_dir() else source.name
        if source.is_dir() and not (source / relative).is_file():
            msg = f"{label}: landing page not found: {source / relative}"
            raise FileNotFoundError(msg)
        server: _Server | None = self._servers.get(directory)
        if server is None:
            log: Path = self._artifacts / f"{label}-server.log"
            pid, base_url, reused = serve(path=directory, log=log)
            if not wait_ready(
                url=base_url,
                pid=pid,
                timeout=self._timeout_seconds,
            ):
                if not reused:
                    terminate_tree(pid=pid)
                msg = f"{label}: local server did not become ready."
                raise RuntimeError(msg)
            server = _Server(
                directory=directory,
                pid=pid,
                base_url=base_url,
                reused=reused,
                log=log,
            )
            self._servers[directory] = server
        path: str = "/".join(
            quote(string=part) for part in Path(relative).parts
        )
        return ServedPage(url=f"{server.base_url}{path}", log=server.log)

    def __enter__(self) -> Self:
        """Create the artifact directory and return this registry.

        Returns:
            This registry ready to serve pages.

        """
        self._artifacts.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Terminate every server started by this registry.

        Args:
            _exception_type: Unused exception type supplied by ``with``.
            _exception: Unused exception supplied by ``with``.
            _traceback: Unused traceback supplied by ``with``.

        """
        for server in self._servers.values():
            if not server.reused:
                terminate_tree(pid=server.pid)
