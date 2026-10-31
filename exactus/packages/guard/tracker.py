# Copyright (c) 2026 João Lopes.
"""Continuously discover and retain descendant process identities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, Lock, Thread

from psutil import AccessDenied, NoSuchProcess, Process, ZombieProcess

from exactus.packages.guard.model import ProcessIdentity, ProcessRecord

type Clock = Callable[[], datetime]


class ProcessTracker:
    """Track the historical descendant tree of one root process.

    The tracker retains processes after they disappear from the live tree.
    Process identity combines PID and creation time so PID reuse cannot cause
    an unrelated process to be treated as a previously observed descendant.
    """

    def __init__(
        self,
        *,
        root_pid: int,
        poll_interval: float = 0.02,
        clock: Clock | None = None,
    ) -> None:
        """Initialize descendant tracking.

        Args:
            root_pid: Process whose descendants are owned by this tracker.
            poll_interval: Delay between background discovery passes.
            clock: Injectable timestamp provider for recorded observations.

        """
        self._root_pid: int = root_pid
        self._poll_interval: float = poll_interval
        self._clock: Clock = clock or self._utc_now
        self._records: dict[ProcessIdentity, ProcessRecord] = {}
        self._stop_event: Event = Event()
        self._lock: Lock = Lock()
        self._thread: Thread | None = None

    def snapshot(self) -> tuple[ProcessRecord, ...]:
        """Discover current descendants and return the historical registry.

        Returns:
            All process records observed during this tracking session.

        """
        try:
            descendants: list[Process] = Process(pid=self._root_pid).children(
                recursive=True,
            )
        except (AccessDenied, NoSuchProcess, ZombieProcess):
            descendants = []
        discovered: list[ProcessRecord] = []
        for process in descendants:
            if (identity := self._identity(process=process)) is None:
                continue
            try:
                record: ProcessRecord = ProcessRecord(
                    identity=identity,
                    parent_pid=process.ppid(),
                    name=process.name(),
                    command=tuple(process.cmdline()),
                    first_seen=self._clock(),
                    depth=self._depth(process=process),
                )
            except (AccessDenied, NoSuchProcess, ZombieProcess):
                continue
            discovered.append(record)
        with self._lock:
            for record in discovered:
                _ = self._records.setdefault(record.identity, record)
            return tuple(self._records.values())

    def start(self) -> None:
        """Start background descendant discovery once."""
        if self._thread is not None:
            return
        _ = self.snapshot()
        self._thread = Thread(
            target=self._watch,
            name="process-guard-tracker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> tuple[ProcessRecord, ...]:
        """Stop discovery after one final snapshot and return all records.

        Returns:
            Final historical process registry.

        """
        _ = self.snapshot()
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._poll_interval * 4.0))
        return self.snapshot()

    @staticmethod
    def _utc_now() -> datetime:
        """Return the current UTC timestamp.

        Returns:
            Timezone-aware current UTC timestamp.

        """
        return datetime.now(tz=UTC)

    @staticmethod
    def _identity(*, process: Process) -> ProcessIdentity | None:
        """Return a stable identity when process metadata remains available.

        Args:
            process: Process whose identity should be captured.

        Returns:
            Stable process identity, or ``None`` when metadata is unavailable.

        """
        try:
            return ProcessIdentity(
                pid=process.pid,
                create_time=process.create_time(),
            )
        except (AccessDenied, NoSuchProcess, ZombieProcess):
            return None

    def _depth(self, *, process: Process) -> int:
        """Calculate current ancestry depth relative to the tracked root.

        Args:
            process: Descendant whose ancestry should be measured.

        Returns:
            Current descendant depth relative to the tracked root.

        """
        depth: int = 1
        current: Process = process
        while current.ppid() != self._root_pid:
            try:
                parent: Process | None = current.parent()
            except (AccessDenied, NoSuchProcess, ZombieProcess):
                break
            if parent is None:
                break
            current = parent
            depth += 1
        return depth

    def _watch(self) -> None:
        """Discover descendants until tracking is stopped."""
        while not self._stop_event.wait(timeout=self._poll_interval):
            _ = self.snapshot()
