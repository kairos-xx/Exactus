# Copyright (c) 2026
"""Format recorded report times without changing their machine values."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from exactus.tools.common.json_types import JsonValue


def readable_time(*, value: JsonValue) -> str | None:
    """Format an ISO timestamp with an explicit timezone.

    Args:
        value: Recorded timestamp.

    Returns:
        Readable timestamp, or None when unavailable or invalid.

    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed: datetime = datetime.fromisoformat(value)
    except ValueError:
        return None
    zone: str = "timezone not recorded"
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(tz=UTC)
        zone = "UTC"
    return f"{parsed:%d %B %Y, %H:%M:%S} {zone}"


def report_times(*, payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Select the recorded run time and supply readable display fields.

    Args:
        payload: Report metadata and optional normalized run block.

    Returns:
        Machine run time and readable run/generation timestamps.

    """
    run: JsonValue = payload.get("run")
    recorded: dict[str, JsonValue] = run if isinstance(run, dict) else {}
    candidates: tuple[JsonValue, ...] = (
        recorded.get("started_at"),
        payload.get("started_at"),
        recorded.get("finished_at"),
        payload.get("finished_at"),
        payload.get("generated_at"),
    )
    selected: JsonValue = next(
        (value for value in candidates if readable_time(value=value)),
        None,
    )
    return {
        "run_at": selected,
        "run_at_human": readable_time(value=selected),
        "generated_at_human": readable_time(value=payload.get("generated_at")),
    }
