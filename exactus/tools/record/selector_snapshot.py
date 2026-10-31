# Copyright (c) 2026 Project contributors
"""Compare a matched element with the baseline recorded for a snapshot."""

from __future__ import annotations

from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        rect_tolerance: Grouped module constant.
        compared: Grouped module constant.

    """

    rect_tolerance: Final[float] = 16.0
    compared: Final[tuple[str, ...]] = ("tag", "role", "text", "attributes")


def parse_baseline(*, payload: str | None) -> dict[str, JsonValue] | None:
    """Read a snapshot action's stored baseline.

    Args:
        payload: The action's payload, which holds the baseline as JSON.

    Returns:
        The baseline evidence, or ``None`` when none is stored or it is not
        valid JSON.

    """
    if not payload:
        return None
    try:
        value: JsonValue = cast(typ="JsonValue", val=loads(s=payload))
    except JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def compare_evidence(
    *,
    baseline: dict[str, JsonValue],
    current: dict[str, JsonValue],
) -> list[dict[str, JsonValue]]:
    """List how the current element differs from the baseline.

    Args:
        baseline: Evidence stored when the baseline was set.
        current: Evidence of the element found now.

    Returns:
        One ``{field, baseline, current}`` entry per difference; empty when
        the element still resembles the baseline.

    """
    changes: list[dict[str, JsonValue]] = [
        {
            "field": field,
            "baseline": baseline.get(field),
            "current": current.get(field),
        }
        for field in Constants.compared
        if baseline.get(field) != current.get(field)
    ]
    before: JsonValue = baseline.get("rect")
    after: JsonValue = current.get("rect")
    if isinstance(before, dict) and isinstance(after, dict):
        moved: bool = any(
            abs(
                _number(value=before.get(edge))
                - _number(value=after.get(edge)),
            )
            > Constants.rect_tolerance
            for edge in ("x", "y", "width", "height")
        )
        if moved:
            changes.append(
                {"field": "rect", "baseline": before, "current": after},
            )
    return changes


def _number(*, value: JsonValue) -> float:
    """Return a JSON number as a float.

    Args:
        value: JSON value that should be a number.

    Returns:
        The number, or ``0.0`` for anything else.

    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)
