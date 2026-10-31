# Copyright (c) 2026 João Lopes.
"""In-process descendant cleanup context manager."""

from __future__ import annotations

from os import getpid
from typing import TYPE_CHECKING, Self

from exactus.packages.guard.cleanup import ProcessCleaner
from exactus.packages.guard.tracker import ProcessTracker

if TYPE_CHECKING:
    from types import TracebackType

    from exactus.packages.guard.model import CleanupResult


class ProcessGuard:
    """Track and clean descendants created inside a context manager."""

    def __init__(
        self,
        *,
        poll_interval: float = 0.02,
        grace_seconds: float = 1.5,
    ) -> None:
        """Initialize an in-process guard.

        Args:
            poll_interval: Descendant discovery interval in seconds.
            grace_seconds: Grace period before force-killing descendants.

        """
        self._tracker: ProcessTracker = ProcessTracker(
            root_pid=getpid(),
            poll_interval=poll_interval,
        )
        self._grace_seconds: float = grace_seconds
        self._result: CleanupResult | None = None

    @property
    def result(self) -> CleanupResult | None:
        """Return cleanup metadata after the guard exits.

        Returns:
            Cleanup metadata, or ``None`` before context exit.

        """
        return self._result

    def __enter__(self) -> Self:
        """Start tracking descendants.

        Returns:
            This active process guard.

        """
        self._tracker.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Clean descendants without suppressing the triggering exception.

        Args:
            exc_type: Exception type raised by the guarded block, if any.
            exc_value: Exception instance raised by the guarded block, if any.
            traceback: Traceback associated with the exception, if any.

        Returns:
            Always ``False`` so exceptions propagate to the caller.

        """
        self._result = ProcessCleaner(
            tracker=self._tracker,
            grace_seconds=self._grace_seconds,
        ).cleanup()
        return False
