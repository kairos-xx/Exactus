# Copyright (c) 2026 João Lopes.
"""Typed value models for process supervision."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class StopReason(Enum):
    """Reason a supervised process stopped.

    Attributes:
        NATURAL: Target exited without supervisor intervention.
        TERMINATED: Process stopped after graceful termination.
        KILLED: Process stopped after forced termination.
        VANISHED: Process disappeared before its state could be observed.

    """

    NATURAL = "natural"
    TERMINATED = "terminated"
    KILLED = "killed"
    VANISHED = "vanished"


@dataclass(frozen=True, slots=True, order=True)
class ProcessIdentity:
    """Uniquely identify one operating-system process incarnation.

    Attributes:
        pid: Operating-system process identifier.
        create_time: Process creation timestamp used to detect PID reuse.

    """

    pid: int
    create_time: float


@dataclass(frozen=True, slots=True)
class ProcessRecord:
    """Describe a process observed during one supervision session.

    Attributes:
        identity: PID and creation-time identity.
        parent_pid: Parent PID observed during discovery, when available.
        name: Operating-system process name.
        command: Command line reported for the process.
        first_seen: Timestamp of the first successful observation.
        depth: Descendant depth relative to the supervised root.

    """

    identity: ProcessIdentity
    parent_pid: int | None
    name: str
    command: tuple[str, ...]
    first_seen: datetime
    depth: int


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Describe the result of descendant cleanup.

    Attributes:
        observed: Historical descendant records known to the tracker.
        terminated: Identities sent graceful termination.
        killed: Identities sent forced termination.
        survivors: Identities still alive after final cleanup.

    """

    observed: tuple[ProcessRecord, ...]
    terminated: tuple[ProcessIdentity, ...]
    killed: tuple[ProcessIdentity, ...]
    survivors: tuple[ProcessIdentity, ...]
