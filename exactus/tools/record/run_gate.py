# Copyright (c) 2026 Project contributors
"""Pause, resume and single-step a flow run between its actions.

The runner executes on the browser thread, so the service cannot interrupt it
from outside. Instead the runner asks this gate before every action whether it
may proceed; the service thread changes the gate's state.
"""

from __future__ import annotations

from threading import Condition
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Constants:
    """Group module-level constants.

    Attributes:
        poll_seconds: Grouped module constant.

    """

    poll_seconds: Final[float] = 0.05


@final
class RunGate:
    """Hold a run before an action until it is resumed or stepped.

    The gate is owned by the service. ``pause`` takes effect at the next
    action boundary: an action that has already started always finishes, since
    stopping a click or a request half way would leave the page undefined.
    """

    def __init__(self) -> None:
        """Start open: a run proceeds until someone pauses it."""
        self._condition: Condition = Condition()
        self._paused: bool = False
        self._steps: int = 0
        self._waiting: bool = False

    @property
    def paused(self) -> bool:
        """Report whether a pause was requested and not yet resumed.

        Returns:
            True while the run is held or about to be.

        """
        with self._condition:
            return self._paused

    @property
    def waiting(self) -> bool:
        """Report whether a runner is blocked at an action boundary.

        Returns:
            True while a runner waits for a resume or a step.

        """
        with self._condition:
            return self._waiting

    def pause(self) -> None:
        """Hold the run before its next action."""
        with self._condition:
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        """Let the run continue without stopping again."""
        with self._condition:
            self._paused = False
            self._steps = 0
            self._condition.notify_all()

    def step(self) -> None:
        """Let exactly one more action run, then hold the run again."""
        with self._condition:
            self._paused = True
            self._steps += 1
            self._condition.notify_all()

    def reset(self) -> None:
        """Open the gate and forget pending steps, for a new or ended run."""
        self.resume()

    def wait_turn(
        self,
        *,
        cancelled: Callable[[], bool],
        on_hold: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        """Block until the next action may run.

        Called by the runner before each action. It returns at once while the
        run is not paused. When paused it calls ``on_hold``, waits for a
        resume, a step or cancellation, then calls ``on_release``.

        Args:
            cancelled: Cooperative cancellation signal, polled while waiting.
            on_hold: Called once when the run starts waiting.
            on_release: Called once when the run proceeds.

        """
        with self._condition:
            if not self._paused or self._steps > 0:
                self._take_step()
                return
            self._waiting = True
        on_hold()
        with self._condition:
            while self._paused and self._steps == 0 and (not cancelled()):
                _ = self._condition.wait(timeout=Constants.poll_seconds)
            self._take_step()
            self._waiting = False
        on_release()

    def _take_step(self) -> None:
        """Consume one pending step; the caller holds the lock."""
        if self._steps > 0:
            self._steps -= 1
