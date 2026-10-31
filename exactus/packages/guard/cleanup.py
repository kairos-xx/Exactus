# Copyright (c) 2026 João Lopes.
"""Terminate processes previously observed by a process tracker."""

from __future__ import annotations

from contextlib import suppress
from time import monotonic
from typing import TYPE_CHECKING

from psutil import (
    STATUS_ZOMBIE,
    AccessDenied,
    NoSuchProcess,
    Process,
    TimeoutExpired,
)

from exactus.packages.guard.model import (
    CleanupResult,
    ProcessIdentity,
    ProcessRecord,
)

if TYPE_CHECKING:
    from exactus.packages.guard.tracker import ProcessTracker


class ProcessCleaner:
    """Perform identity-safe, deepest-first descendant cleanup."""

    _IDENTITY_TOLERANCE_SECONDS: float = 0.001

    def __init__(
        self,
        *,
        tracker: ProcessTracker,
        grace_seconds: float = 1.5,
        settle_seconds: float = 0.15,
    ) -> None:
        """Initialize cleanup policy.

        Args:
            tracker: Historical descendant tracker to clean.
            grace_seconds: Maximum graceful termination wait.
            settle_seconds: Maximum final force-kill wait.

        """
        self._tracker: ProcessTracker = tracker
        self._grace_seconds: float = grace_seconds
        self._settle_seconds: float = settle_seconds

    def cleanup(self) -> CleanupResult:
        """Terminate all observed descendants and force-kill survivors.

        Returns:
            Complete cleanup outcome for the tracker's historical descendants.

        """
        observed: tuple[ProcessRecord, ...] = self._tracker.stop()
        terminated: tuple[ProcessIdentity, ...] = self._signal(
            records=observed,
            force=False,
        )
        survivors: tuple[ProcessIdentity, ...] = self._wait_until_dead(
            identities=terminated,
            timeout=self._grace_seconds,
        )
        survivor_set: set[ProcessIdentity] = set(survivors)
        killed: tuple[ProcessIdentity, ...] = self._signal(
            records=tuple(
                record
                for record in observed
                if record.identity in survivor_set
            ),
            force=True,
        )
        final_survivors: tuple[ProcessIdentity, ...] = self._wait_until_dead(
            identities=killed,
            timeout=self._settle_seconds,
        )
        return CleanupResult(
            observed=observed,
            terminated=terminated,
            killed=killed,
            survivors=final_survivors,
        )

    @classmethod
    def _live_process(cls, *, identity: ProcessIdentity) -> Process | None:
        """Resolve an identity only when PID and creation time still match.

        Args:
            identity: Process identity to resolve.

        Returns:
            Matching live process, or ``None`` when unavailable or reused.

        """
        try:
            process: Process = Process(pid=identity.pid)
            return (
                process
                if abs(process.create_time() - identity.create_time)
                < cls._IDENTITY_TOLERANCE_SECONDS
                else None
            )
        except (AccessDenied, NoSuchProcess):
            return None

    @classmethod
    def _alive(cls, *, identity: ProcessIdentity) -> bool:
        """Return whether the exact process incarnation is still running.

        Args:
            identity: Process identity to inspect.

        Returns:
            ``True`` when the exact process is alive and not a zombie.

        """
        return (
            (process := cls._live_process(identity=identity)) is not None
            and process.is_running()
            and process.status() != STATUS_ZOMBIE
        )

    @classmethod
    def _signal(
        cls,
        *,
        records: tuple[ProcessRecord, ...],
        force: bool,
    ) -> tuple[ProcessIdentity, ...]:
        """Signal live records deepest-first and return signaled identities.

        Args:
            records: Historical process records to signal.
            force: Whether to kill rather than terminate each process.

        Returns:
            Identities for processes that accepted the requested signal.

        """
        signaled: list[ProcessIdentity] = []
        for record in sorted(
            records,
            key=lambda item: item.depth,
            reverse=True,
        ):
            if (
                process := cls._live_process(identity=record.identity)
            ) is None:
                continue
            try:
                process.kill() if force else process.terminate()
                signaled.append(record.identity)
            except (AccessDenied, NoSuchProcess):
                continue
        return tuple(signaled)

    @classmethod
    def _wait_until_dead(
        cls,
        *,
        identities: tuple[ProcessIdentity, ...],
        timeout: float,
    ) -> tuple[ProcessIdentity, ...]:
        """Wait up to a deadline and return identities still alive.

        Args:
            identities: Process identities whose termination is awaited.
            timeout: Maximum wait duration in seconds.

        Returns:
            Identities still alive when waiting finishes.

        """
        deadline: float = monotonic() + timeout
        survivors: tuple[ProcessIdentity, ...] = identities
        while survivors and monotonic() < deadline:
            for identity in survivors:
                if (process := cls._live_process(identity=identity)) is None:
                    continue
                with suppress(TimeoutExpired):
                    _ = process.wait(
                        timeout=min(0.02, max(0.0, deadline - monotonic())),
                    )
            survivors = tuple(
                identity
                for identity in survivors
                if cls._alive(identity=identity)
            )
        return survivors
