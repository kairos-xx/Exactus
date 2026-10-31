# Copyright (c) 2026 Project contributors
"""Publish bounded, ordered service events with snapshot recovery."""

from __future__ import annotations

from collections import deque
from json import dumps
from threading import Condition
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from exactus.tools.record.store import JsonValue


class EventBus:
    """Retain a bounded event history independently of connected clients.

    Attributes:
        instance_id: Fresh identifier for each service lifetime.
        sequence: Last published event sequence.

    """

    def __init__(self, *, capacity: int = 256) -> None:
        """Create the service-local history.

        Args:
            capacity: Maximum retained events.

        """
        self.instance_id: str = uuid4().hex
        self.sequence: int = 0
        self._history: deque[tuple[int, str]] = deque(maxlen=capacity)
        self._condition: Condition = Condition()
        self._closed: bool = False

    def emit_event(self, *, name: str, payload: JsonValue) -> None:
        """Publish an immutable JSON message and wake waiting clients.

        Args:
            name: Domain event name.
            payload: JSON event fields.

        """
        with self._condition:
            self.sequence += 1
            value: str = dumps(
                obj={
                    "protocol": 1,
                    "event": name,
                    "payload": payload,
                    "sequence": self.sequence,
                    "instance_id": self.instance_id,
                },
            )
            self._history.append((self.sequence, value))
            self._condition.notify_all()

    def read(
        self,
        *,
        after: int,
        timeout: float = 15,
    ) -> tuple[bool, tuple[tuple[int, str], ...]]:
        """Read newer events or indicate that history needs a snapshot.

        Args:
            after: Last sequence acknowledged by the client.
            timeout: Maximum blocking time for an idle subscriber.

        Returns:
            Snapshot requirement and immutable event records.

        """
        with self._condition:
            if after == self.sequence and not self._closed:
                _ = self._condition.wait(timeout=timeout)
            lost: bool = after > self.sequence or bool(
                self._history and after < self._history[0][0] - 1,
            )
            return lost, tuple(row for row in self._history if row[0] > after)

    def close(self) -> None:
        """Wake subscribers during shutdown."""
        with self._condition:
            self._closed = True
            self._condition.notify_all()
