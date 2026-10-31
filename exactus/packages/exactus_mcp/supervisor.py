# Copyright (c) 2026
"""Run the Exactus MCP asyncio service behind synchronous controls."""

from __future__ import annotations

from asyncio import run as run_async
from threading import Event, RLock, Thread
from typing import TYPE_CHECKING, Protocol, final

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from pathlib import Path

    from .activity import ServiceActivity
    from .cli import RuntimeConfig


class ServiceRunner(Protocol):
    """Describe the asynchronous Exactus MCP service entry point."""

    def __call__(
        self,
        *,
        config: RuntimeConfig,
        activity: ServiceActivity,
        stop_requested: Event,
    ) -> Coroutine[None, None, int]:
        """Run one service generation until it stops.

        Args:
            config: Validated service configuration.
            activity: Shared lifecycle and caller activity sink.
            stop_requested: Thread-safe graceful shutdown request.

        Returns:
            Awaitable service exit status.

        """
        ...


@final
class ServiceSupervisor:
    """Provide non-blocking Start, Stop, and Restart service controls."""

    def __init__(
        self,
        *,
        config: RuntimeConfig,
        activity: ServiceActivity,
        service_runner: ServiceRunner,
    ) -> None:
        """Create a stopped supervisor.

        Args:
            config: Immutable service settings reused for every generation.
            activity: Shared observable lifecycle and call state.
            service_runner: Async service implementation to execute.

        """
        self._config: RuntimeConfig = config
        self._activity: ServiceActivity = activity
        self._service_runner: ServiceRunner = service_runner
        self._lock: RLock = RLock()
        self._stop_requested: Event = Event()
        self._service_thread: Thread | None = None
        self._restart_thread: Thread | None = None

    @property
    def root(self) -> Path:
        """Return the configured project root.

        Returns:
            Project root reused across service generations.

        """
        return self._config.root

    @property
    def public_tunnel_enabled(self) -> bool:
        """Return whether service generations should create a public tunnel.

        Returns:
            ``True`` when ngrok exposure is configured.

        """
        return self._config.ngrok

    def is_running(self) -> bool:
        """Return whether a service generation is still alive.

        Returns:
            ``True`` while the service thread is active.

        """
        with self._lock:
            return (
                self._service_thread is not None
                and self._service_thread.is_alive()
            )

    def start(self) -> bool:
        """Start the service unless one generation is already alive.

        Returns:
            ``True`` when a new generation was started.

        """
        with self._lock:
            if (
                self._service_thread is not None
                and self._service_thread.is_alive()
            ):
                return False
            self._stop_requested = Event()
            self._activity.mark_starting()
            thread: Thread = Thread(
                target=self._run,
                name="exactus-mcp-service",
                daemon=True,
            )
            self._service_thread = thread
            thread.start()
            return True

    def stop(self) -> bool:
        """Request graceful service shutdown without blocking the caller.

        Returns:
            ``True`` when a live generation received the request.

        """
        with self._lock:
            if (
                self._service_thread is None
                or not self._service_thread.is_alive()
            ):
                return False
            self._activity.mark_stopping()
            self._stop_requested.set()
            return True

    def restart(self) -> bool:
        """Request a serialized stop followed by a fresh start.

        Returns:
            ``True`` when a restart transition was scheduled.

        """
        with self._lock:
            if (
                self._restart_thread is not None
                and self._restart_thread.is_alive()
            ):
                return False
            current: Thread | None = self._service_thread
            if current is None or not current.is_alive():
                return self.start()
            self._activity.mark_restarting()
            self._stop_requested.set()
            transition: Thread = Thread(
                target=self._restart_after,
                args=(current,),
                name="exactus-mcp-restart",
                daemon=True,
            )
            self._restart_thread = transition
            transition.start()
            return True

    def shutdown(self, *, timeout: float) -> bool:
        """Stop the service and wait for bounded graceful cleanup.

        Args:
            timeout: Maximum seconds to wait for the current generation.

        Returns:
            ``True`` when no service thread remains alive.

        """
        _ = self.stop()
        with self._lock:
            thread: Thread | None = self._service_thread
        if thread is not None:
            thread.join(timeout=timeout)
        return thread is None or not thread.is_alive()

    def _restart_after(self, previous: Thread) -> None:
        """Wait for one generation, then start its replacement.

        Args:
            previous: Service thread currently shutting down.

        """
        previous.join()
        _ = self.start()

    def _run(self) -> None:
        """Run one async service generation inside its dedicated thread."""
        try:
            run_async(
                main=self._service_runner(
                    config=self._config,
                    activity=self._activity,
                    stop_requested=self._stop_requested,
                ),
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._activity.mark_failed(error=f"{type(exc).__name__}: {exc}")
