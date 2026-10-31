# Copyright (c) 2026 João Lopes.
"""External process supervisor that owns and cleans a target process tree."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from os import killpg
from os import name as os_name
from signal import SIGINT, SIGKILL, SIGTERM, signal
from typing import TYPE_CHECKING, cast

from psutil import Popen

from exactus.packages.guard.cleanup import ProcessCleaner
from exactus.packages.guard.tracker import ProcessTracker

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import FrameType

    from exactus.packages.guard.model import CleanupResult


@dataclass(frozen=True, slots=True)
class SupervisionResult:
    """Result returned after the target and descendants have been cleaned.

    Attributes:
        exit_code: Exit status produced by the supervised target.
        cleanup: Descendant cleanup outcome.

    """

    exit_code: int
    cleanup: CleanupResult


class TargetProcess:
    """Typed adapter around psutil's subprocess-compatible process."""

    def __init__(self, *, command: tuple[str, ...]) -> None:
        """Launch a supervised command.

        Args:
            command: Executable and arguments to launch.

        """
        self._process: Popen = Popen(
            args=command,
            start_new_session=os_name != "nt",
        )

    @property
    def pid(self) -> int:
        """Return the process identifier.

        Returns:
            Operating-system process identifier.

        """
        return self._process.pid

    def is_running(self) -> bool:
        """Return whether the process is still running.

        Returns:
            ``True`` while the target process is running.

        """
        return self._process.is_running()

    def terminate(self) -> None:
        """Request termination."""
        self._process.terminate()

    def wait(self) -> int:
        """Wait for completion and return the exit status.

        Returns:
            Target process exit status.

        """
        return self._process.wait()


class ProcessSupervisor:
    """Run an arbitrary command and clean its surviving process tree.

    On POSIX, the target owns a new session and process group. Historical
    descendant tracking complements that containment boundary so descendants
    that change process groups after discovery remain individually known.
    """

    def __init__(
        self,
        *,
        command: Sequence[str],
        poll_interval: float = 0.02,
        grace_seconds: float = 1.5,
    ) -> None:
        """Initialize an external command supervisor.

        Args:
            command: Executable followed by its arguments.
            poll_interval: Descendant discovery interval in seconds.
            grace_seconds: Grace period before force-killing descendants.

        Raises:
            ValueError: If command is empty.

        """
        if not command:
            msg: str = "command must contain an executable"
            raise ValueError(msg)
        self._command: tuple[str, ...] = tuple(command)
        self._poll_interval: float = poll_interval
        self._grace_seconds: float = grace_seconds
        self._target: TargetProcess | None = None

    def run(self) -> SupervisionResult:
        """Run the target, then clean every surviving descendant.

        Returns:
            Target exit status and descendant cleanup metadata.

        """
        previous: dict[
            int,
            int | Callable[[int, FrameType | None], object] | None,
        ] = {}
        for handled_signal in (SIGINT, SIGTERM):
            previous[handled_signal] = signal(
                signalnum=handled_signal,
                handler=self._request_stop,
            )
        self._target = TargetProcess(command=self._command)
        tracker: ProcessTracker = ProcessTracker(
            root_pid=self._target.pid,
            poll_interval=self._poll_interval,
        )
        tracker.start()
        try:
            exit_code: int = self._target.wait()
        finally:
            _ = tracker.snapshot()
            self._signal_group(force=False)
            cleanup: CleanupResult = ProcessCleaner(
                tracker=tracker,
                grace_seconds=self._grace_seconds,
            ).cleanup()
            self._signal_group(force=True)
            for handled_signal, handler in previous.items():
                _ = signal(
                    signalnum=handled_signal,
                    handler=cast(
                        typ="int | Callable[[int, FrameType | None], object]",
                        val=handler,
                    ),
                )
        return SupervisionResult(exit_code=exit_code, cleanup=cleanup)

    def _request_stop(
        self,
        _signal_number: int,
        _frame: FrameType | None,
    ) -> None:
        """Request target termination after an interrupt signal.

        Args:
            _signal_number: Received signal number.
            _frame: Current interpreter frame supplied by the signal handler.

        """
        if self._target is not None and self._target.is_running():
            self._target.terminate()

    def _signal_group(self, *, force: bool) -> None:
        """Signal the POSIX target process group when it still exists.

        Args:
            force: Whether to send ``SIGKILL`` instead of ``SIGTERM``.

        """
        if os_name == "nt" or self._target is None:
            return
        with suppress(ProcessLookupError):
            killpg(self._target.pid, SIGKILL if force else SIGTERM)
