# Copyright (c) 2026
"""Publish real frontend work into the shared tool heartbeat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from exactus.tools.common.runtime import Progress, publish_progress

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@dataclass(slots=True)
class FrontendProgress:
    """Track Actions phases while reserving completion for report writing.

    Attributes:
        actions: Number of recipe actions, or one standalone execution.
        index: Current action index; standalone replay starts at zero.

    """

    actions: int = 1
    index: int = -1

    def __call__(self, event: dict[str, JsonValue]) -> None:
        """Publish actual environment and step completion.

        Args:
            event: Discovery, recipe or replay progress message.

        """
        if event.get("type") == "actions_state":
            if event.get("state") == "running":
                self.index += 1
            else:
                return
        elif event.get("type") != "frontend_progress":
            return
        completed: JsonValue = event.get("completed", 0)
        total: JsonValue = event.get("total", 1)
        share: JsonValue = event.get("fraction")
        workers: JsonValue = event.get("workers")
        if not isinstance(completed, int) or not isinstance(total, int):
            return
        index: int = max(self.index, 0)
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=completed,
                total=total,
                step=str(object=event.get("step") or event.get("action_id")),
                detail=str(object=event.get("detail") or ""),
                share=float(share)
                if isinstance(share, (int, float))
                else None,
                workers=workers if isinstance(workers, dict) else None,
                span=(
                    0.98 * index / max(self.actions, 1),
                    0.98 * (index + 1) / max(self.actions, 1),
                ),
            ),
        )
