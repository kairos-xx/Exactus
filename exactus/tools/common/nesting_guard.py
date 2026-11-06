# Copyright (c) 2026
"""Contain runaway recursive Exactus launches.

Every Exactus process increments a nesting counter in its environment,
which children inherit. A launcher that keeps re-executing itself — for
example an interpreter or bundle dispatch that resolves back to the same
entrypoint — therefore stops after a bounded number of generations
instead of exhausting the machine's process table and memory.

Legitimate nesting (orchestrator, worker, nested pipeline, coverage,
test subprocess) stays far below the limit. The counter is deliberately
not run-scoped: it must survive the sanitized environment boundary,
because that boundary is exactly where an independent child is started.
"""

from __future__ import annotations

from os import environ, getpid, getppid
from sys import argv
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import MutableMapping


@final
class Constants:
    """Group module-level constants.

    Attributes:
        depth_variable: Grouped module constant.
        owner_variable: Grouped module constant.
        max_depth: Grouped module constant.

    """

    depth_variable: Final[str] = "EXACTUS_NEST_DEPTH"
    owner_variable: Final[str] = "EXACTUS_NEST_OWNER"
    max_depth: Final[int] = 32


class NestingError(RuntimeError):
    """Refuse to start an Exactus process nested beyond the limit."""


def enter(
    *,
    environment: MutableMapping[str, str] | None = None,
    process: int | None = None,
) -> int:
    """Record this process as one generation deeper than its parent.

    Entering twice from the same process is idempotent: depth counts
    process generations, not calls, so in-process callers such as test
    runners never approach the limit.

    Args:
        environment: Mapping to read and update; ``os.environ`` when
            omitted.
        process: Identifier of the entering process; the current pid
            when omitted.

    Returns:
        This process's nesting depth, starting at ``1``.

    Raises:
        NestingError: The inherited depth already reached the limit.

    """
    mapping: MutableMapping[str, str] = (
        environ if environment is None else environment
    )
    identity: str = str(object=getpid() if process is None else process)
    raw: str = mapping.get(Constants.depth_variable, "0")
    recorded: int = int(raw) if raw.isdecimal() else 0
    if mapping.get(Constants.owner_variable) == identity:
        return recorded
    inherited: int = recorded
    if inherited >= Constants.max_depth:
        msg: str = (
            f"recursive Exactus launch detected: nesting depth "
            f"{inherited}"
            f" reached the limit of "
            f"{Constants.max_depth}"
            f" (parent pid "
            f"{getppid()}"
            f", argv "
            f"{argv[:6]!r}"
            f"); refusing to start another generation"
        )
        raise NestingError(msg)
    mapping[Constants.depth_variable] = str(object=inherited + 1)
    mapping[Constants.owner_variable] = identity
    return inherited + 1
