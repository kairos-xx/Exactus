# Copyright (c) 2026
"""Cross-platform termination of verified Exactus process trees.

Terminate an Exactus root process and its descendants using an authenticated
run identity and the associated SQLite runtime database.

Database-listed PIDs are accepted only when they belong to the verified
root process tree. This prevents stale database records from terminating
unrelated processes after PID reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from sqlite3 import DatabaseError, connect
from time import monotonic
from typing import TYPE_CHECKING, final

from psutil import AccessDenied, Error, NoSuchProcess, Process, wait_procs

if TYPE_CHECKING:
    from .process_control import RunIdentity


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class TerminationResult:
    """Represent the outcome of terminating an Exactus run.

    Attributes:
        root_pid: Exactus root process identifier.
        run_id: Exactus unified-run identifier.
        runs_db: Runtime SQLite database path.
        discovered: PIDs identified as belonging to the process tree.
        terminated: PIDs terminated during the graceful phase.
        killed: PIDs terminated during the forced phase.
        already_exited: PIDs that exited before termination was attempted.
        failed: PIDs that could not be terminated.
        skipped: Database-listed PIDs outside the verified process tree.
        duration: Total termination duration in seconds.

    """

    root_pid: int
    run_id: str
    runs_db: str
    discovered: tuple[int, ...]
    terminated: tuple[int, ...]
    killed: tuple[int, ...]
    already_exited: tuple[int, ...]
    failed: tuple[int, ...]
    skipped: tuple[int, ...]
    duration: float

    @property
    def success(self) -> bool:
        """Return whether all verified processes were terminated.

        Returns:
            Whether all verified processes were terminated.

        """
        return not self.failed

    @property
    def count(self) -> int:
        """Return the number of successfully terminated processes.

        Returns:
            The number of successfully terminated processes.

        """
        return len(self.terminated) + len(self.killed)


@final
@dataclass(slots=True, kw_only=True)
class _Progress:
    """Mutable termination progress shared across phases.

    Attributes:
        terminated: PIDs terminated during the graceful phase.
        killed: PIDs terminated during the forced phase.
        already_exited: PIDs that exited before signals completed.
        failed: PIDs that could not be terminated.

    """

    terminated: set[int] = field(default_factory=set)
    killed: set[int] = field(default_factory=set)
    already_exited: set[int] = field(default_factory=set)
    failed: set[int] = field(default_factory=set)


@final
class ProcessTerminator:
    """Terminate Exactus process trees using verified runtime identities."""

    def __init__(
        self,
        *,
        grace_period: float = 2.0,
        kill_timeout: float = 2.0,
    ) -> None:
        """Initialize process termination settings.

        Args:
            grace_period: Time allowed for graceful termination.
            kill_timeout: Time allowed after forced termination.

        Raises:
            ValueError: If a timeout is negative or nonfinite.

        """
        if (
            not isfinite(grace_period)
            or grace_period < 0
            or not isfinite(kill_timeout)
            or kill_timeout < 0
        ):
            msg: str = "Termination timeouts must be finite and nonnegative"
            raise ValueError(msg)
        self.grace_period: float = grace_period
        self.kill_timeout: float = kill_timeout

    def terminate(
        self,
        *,
        identity: RunIdentity,
        force: bool = True,
    ) -> TerminationResult:
        """Terminate one verified Exactus run and its process tree.

        Args:
            identity: Authenticated Exactus run identity.
            force: Whether to force-kill processes surviving the grace period.

        Returns:
            Structured termination results.

        Raises:
            DatabaseError: If the runtime database cannot be queried.
            RuntimeError: If termination would target the calling process.

        """
        started: float = monotonic()
        if identity.root_pid == Process().pid:
            msg: str = "Refusing to terminate the current process"
            raise RuntimeError(msg)
        root: Process | None = self._root(identity=identity)
        if root is None:
            return self._absent(identity=identity, started=started)
        processes: list[Process] = self._processes(root=root)
        skipped: set[int] = self._skipped(
            identity=identity,
            processes=processes,
        )
        snapshots: list[tuple[Process, float]] = self._snapshots(
            processes=processes,
        )
        progress: _Progress = _Progress()
        self._shutdown(snapshots=snapshots, force=force, progress=progress)
        return TerminationResult(
            root_pid=identity.root_pid,
            run_id=identity.run_id,
            runs_db=identity.runs_db,
            discovered=tuple(process.pid for process, _ in snapshots),
            terminated=tuple(sorted(progress.terminated)),
            killed=tuple(sorted(progress.killed)),
            already_exited=tuple(sorted(progress.already_exited)),
            failed=tuple(sorted(progress.failed)),
            skipped=tuple(sorted(skipped)),
            duration=monotonic() - started,
        )

    @staticmethod
    def _absent(*, identity: RunIdentity, started: float) -> TerminationResult:
        """Build the result when the verified root already exited.

        Args:
            identity: Authenticated Exactus run identity.
            started: Termination start timestamp.

        Returns:
            Result marking the root as already exited.

        """
        return TerminationResult(
            root_pid=identity.root_pid,
            run_id=identity.run_id,
            runs_db=identity.runs_db,
            discovered=(),
            terminated=(),
            killed=(),
            already_exited=(identity.root_pid,),
            failed=(),
            skipped=(),
            duration=monotonic() - started,
        )

    @staticmethod
    def _snapshots(*, processes: list[Process]) -> list[tuple[Process, float]]:
        """Capture process creation timestamps before signalling.

        Args:
            processes: Verified process-tree members.

        Returns:
            Live process handles paired with creation timestamps.

        """
        snapshots: list[tuple[Process, float]] = []
        for process in processes:
            try:
                snapshots.append((process, process.create_time()))
            except (Error, OSError):
                continue
        return snapshots

    @staticmethod
    def _database_pids(*, identity: RunIdentity) -> set[int]:
        """Retrieve running tool PIDs associated with an Exactus run.

        Args:
            identity: Verified Exactus run identity.

        Returns:
            Positive process identifiers recorded as running.

        Raises:
            DatabaseError: If the database cannot be queried.

        """
        database: Path = Path(identity.runs_db)
        if not database.is_file():
            return set()
        with connect(
            database=database.as_uri() + "?mode=ro",
            uri=True,
            timeout=0.2,
        ) as connection:
            rows: list[tuple[int]] = connection.execute(
                (
                    "\n                    SELECT DISTINCT pid\n              "
                    "      FROM runs\n                    WHERE status = 'RUNN"
                    "ING'\n                      AND (\n                      "
                    "    run_id = ?\n                          OR pipeline_run"
                    "_id = ?\n                      )\n                      A"
                    "ND pid IS NOT NULL\n                      AND pid > 0\n  "
                    "              "
                ),
                (identity.run_id, identity.run_id),
            ).fetchall()
        return {pid for row in rows if (pid := row[0]) > 0}

    @staticmethod
    def _root(*, identity: RunIdentity) -> Process | None:
        """Resolve the original Exactus process without accepting PID reuse.

        Args:
            identity: Previously verified Exactus identity.

        Returns:
            Matching live process, or None.

        """
        try:
            process: Process = Process(pid=identity.root_pid)
            if (
                process.create_time() != identity.created_at
                or not process.is_running()
                or process.status() == "zombie"
            ):
                return None
        except (Error, OSError):
            return None
        return process

    @staticmethod
    def _tree(*, root: Process) -> list[Process]:
        """Capture descendants before terminating their parents.

        Args:
            root: Verified Exactus root process.

        Returns:
            Descendants in child-first order, followed by the root.

        """
        descendants: list[Process] = root.children(recursive=True)
        return [*reversed(descendants), root]

    @staticmethod
    def _alive(*, process: Process, created_at: float) -> bool:
        """Verify that a process is still the original process instance.

        Args:
            process: Previously captured process handle.
            created_at: Original process creation timestamp.

        Returns:
            Whether the original process remains alive.

        """
        try:
            return (
                process.create_time() == created_at
                and process.is_running()
                and process.status() != "zombie"
            )
        except (Error, OSError):
            return False

    def _processes(self, *, root: Process) -> list[Process]:
        """Resolve the process tree, falling back to the root alone.

        Args:
            root: Verified Exactus root process.

        Returns:
            Process tree, or only the root when traversal fails.

        """
        try:
            return self._tree(root=root)
        except (Error, OSError):
            return [root]

    def _skipped(
        self,
        *,
        identity: RunIdentity,
        processes: list[Process],
    ) -> set[int]:
        """Return database PIDs that fall outside the verified tree.

        Args:
            identity: Authenticated Exactus run identity.
            processes: Verified process-tree members.

        Returns:
            Database-listed PIDs absent from the process tree.

        """
        try:
            database_pids: set[int] = self._database_pids(identity=identity)
        except (DatabaseError, OSError):
            return set()
        return database_pids - {process.pid for process in processes}

    def _shutdown(
        self,
        *,
        snapshots: list[tuple[Process, float]],
        force: bool,
        progress: _Progress,
    ) -> None:
        """Run graceful then forced termination phases.

        Args:
            snapshots: Process handles with creation timestamps.
            force: Whether to kill processes surviving the grace period.
            progress: Mutable termination progress.

        """
        alive: list[Process] = self._signal(
            snapshots=snapshots,
            progress=progress,
        )
        if force:
            alive = self._kill(
                alive=alive,
                snapshots=snapshots,
                progress=progress,
            )
        progress.failed.update(process.pid for process in alive)
        progress.failed.difference_update(progress.terminated)
        progress.failed.difference_update(progress.killed)
        progress.failed.difference_update(progress.already_exited)

    def _signal(
        self,
        *,
        snapshots: list[tuple[Process, float]],
        progress: _Progress,
    ) -> list[Process]:
        """Signal live processes and wait for graceful exits.

        Args:
            snapshots: Process handles with creation timestamps.
            progress: Mutable termination progress.

        Returns:
            Processes still alive after the grace period.

        """
        for process, created_at in snapshots:
            if not self._alive(process=process, created_at=created_at):
                progress.already_exited.add(process.pid)
                continue
            try:
                process.terminate()
            except NoSuchProcess:
                progress.already_exited.add(process.pid)
            except (AccessDenied, OSError):
                progress.failed.add(process.pid)
        pending: list[Process] = []
        for process, created_at in snapshots:
            if (
                process.pid in progress.already_exited
                or process.pid in progress.failed
            ):
                continue
            if self._alive(process=process, created_at=created_at):
                pending.append(process)
            else:
                progress.terminated.add(process.pid)
        gone: list[Process]
        alive: list[Process]
        gone, alive = wait_procs(procs=pending, timeout=self.grace_period)
        progress.terminated.update(
            process.pid
            for process in gone
            if process.pid not in progress.already_exited
        )
        return alive

    def _kill(
        self,
        *,
        alive: list[Process],
        snapshots: list[tuple[Process, float]],
        progress: _Progress,
    ) -> list[Process]:
        """Kill surviving processes and wait for forced exits.

        Args:
            alive: Processes surviving the graceful phase.
            snapshots: Process handles with creation timestamps.
            progress: Mutable termination progress.

        Returns:
            Processes still alive after the kill timeout.

        """
        created_at_map: dict[int, float] = {
            process.pid: created_at for process, created_at in snapshots
        }
        for process in alive:
            created_at: float | None = created_at_map.get(process.pid)
            if created_at is None or not self._alive(
                process=process,
                created_at=created_at,
            ):
                continue
            try:
                process.kill()
            except NoSuchProcess:
                progress.already_exited.add(process.pid)
            except (AccessDenied, OSError):
                progress.failed.add(process.pid)
        survivors: list[Process] = [
            process
            for process in alive
            if process.pid not in progress.already_exited
        ]
        gone: list[Process]
        remaining: list[Process]
        gone, remaining = wait_procs(
            procs=survivors,
            timeout=self.kill_timeout,
        )
        progress.killed.update(
            process.pid
            for process in gone
            if process.pid not in progress.already_exited
        )
        return remaining
