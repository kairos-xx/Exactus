#!/usr/bin/env python3
# Copyright (c) 2026
"""Uniform ``exactus-run/v1`` live-run progress document schema.

The remaining internal live-run surfaces publish the same envelope so
watchers can parse them identically:

- ``EXACTUS_RESULTS/PIPELINES/<PIPELINE>/ARTIFACTS/owner.json`` —
  pipeline ownership (``kind: "pipeline"``);
- ``exactus/tools-<platform>/parts/@activity.json`` — bundle build status
  (``kind: "build"``).

The shared keys are ``schema``, ``kind``, ``name``, ``run_id``,
``pipeline_run_id``, ``pid``, ``status``, ``progress`` (a ``[0, 1]``
fraction), ``completed``, ``total``, ``step``, ``detail``,
``started_at``, ``updated_at``, ``finished_at``, ``elapsed_seconds``,
``items``, and ``extra``. ``items`` members follow the ``RunItem``
shape; producer-specific payload lives under ``extra``.

The user-facing ``ARTIFACTS/@activity.json`` of tools and pipelines uses
the fixed ``exactus/activity/v1`` schema of
``exactus.tools.common.activity`` instead; pipeline ``items`` keep the
``RunItem`` shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, Self, final

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        progress_schema: Grouped module constant.

    """

    progress_schema: Final[str] = "exactus-run/v1"


def utc_now() -> str:
    """Return the current UTC wall-clock time as an ISO-8601 string.

    Returns:
        The resulting value.

    """
    return datetime.now(tz=UTC).astimezone().isoformat()


@dataclass(frozen=True, slots=True, kw_only=True)
class RunItem:
    """Describe one sub-entity record inside a uniform run document.

    Attributes:
        name: Sub-entity identifier (tool name, build step, ...).
        status: Lifecycle state (``WAITING``/``RUNNING``/``DONE``/...).
        progress: Completion fraction in ``[0, 1]``.
        step: Current step label.
        detail: Optional human-readable detail.
        run_id: Sub-entity run identifier, when one exists.
        started_at: ISO-8601 start timestamp.
        finished_at: ISO-8601 finish timestamp.
        elapsed_seconds: Wall-clock duration.
        extra: Producer-specific fields merged into the record.

    """

    name: str
    status: str
    progress: float = 0.0
    step: str = ""
    detail: str = ""
    run_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float = 0.0
    extra: dict[str, JsonValue] = field(default_factory=dict)

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the record as one ``exactus-run/v1`` items entry.

        Returns:
            JSON-compatible item document.

        """
        item: dict[str, JsonValue] = {
            "name": self.name,
            "run_id": self.run_id,
            "status": self.status,
            "progress": self.progress,
            "step": self.step,
            "detail": self.detail,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
        }
        item.update(dict(self.extra))
        return item


@dataclass(frozen=True, slots=True, kw_only=True)
class RunDocument:
    """Describe one uniform ``exactus-run/v1`` live-run document.

    Attributes:
        kind: Producer kind (``tool``, ``analyzer``, ``pipeline``,
            ``build``).
        name: Producer identifier (analyzer, pipeline, target).
        status: Lifecycle state (``WAITING``/``RUNNING``/``DONE``/
            ``FAIL``/``INTERRUPT``).
        progress: Completion fraction in ``[0, 1]``.
        completed: Completed logical work units.
        total: Total logical work units.
        step: Current step label.
        detail: Optional human-readable detail.
        run_id: Run identifier, when one exists.
        pipeline_run_id: Owning pipeline run identifier, when nested.
        pid: Owning process identifier.
        started_at: ISO-8601 start timestamp.
        updated_at: ISO-8601 last-write timestamp; defaults to now.
        finished_at: ISO-8601 finish timestamp.
        elapsed_seconds: Wall-clock duration.
        items: Sub-entity records.
        extra: Producer-specific fields kept under ``extra``.

    """

    kind: str
    name: str
    status: str
    progress: float = 0.0
    completed: int = 0
    total: int = 0
    step: str = ""
    detail: str = ""
    run_id: str | None = None
    pipeline_run_id: str | None = None
    pid: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float = 0.0
    items: tuple[RunItem | dict[str, JsonValue], ...] = ()
    extra: dict[str, JsonValue] = field(default_factory=dict)

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the document for a progress artifact file.

        Returns:
            JSON-compatible ``exactus-run/v1`` run document.

        """
        return {
            "schema": Constants.progress_schema,
            "kind": self.kind,
            "name": self.name,
            "run_id": self.run_id,
            "pipeline_run_id": self.pipeline_run_id,
            "pid": self.pid,
            "status": self.status,
            "progress": self.progress,
            "completed": self.completed,
            "total": self.total,
            "step": self.step,
            "detail": self.detail,
            "started_at": self.started_at,
            "updated_at": (
                self.updated_at if self.updated_at is not None else utc_now()
            ),
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
            "items": [
                item.payload() if isinstance(item, RunItem) else dict(item)
                for item in self.items
            ],
            "extra": dict(self.extra),
        }
