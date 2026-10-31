"""Resolve visual-cause finding levels from selector matches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

type Level = Literal["accept", "warning", "fail"]


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryMatch:
    """One configured query and its match cardinality.

    Attributes:
        level: Verdict level the query assigns.
        query: ExtendedSelector expression that matched.
        match_count: Elements the query matched in the page.
        order: Configured position used to break ties.

    """

    level: Level
    query: str
    match_count: int
    order: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LevelDecision:
    """The winning level and the evidence explaining it.

    Attributes:
        level: Most severe matched level, or the default.
        decided_by: Query that won, or ``None`` for the default.
        matched: Every configured query that matched.

    """

    level: Level
    decided_by: str | None
    matched: tuple[QueryMatch, ...]


class Constants:
    """Store severity ordering.

    Attributes:
        severity: Numeric rank per verdict level.

    """

    severity: Final[dict[Level, int]] = {"accept": 0, "warning": 1, "fail": 2}


def decide(
    *,
    matches: tuple[QueryMatch, ...],
    default: Level,
) -> LevelDecision:
    """Choose the most severe match and its narrowest winning query.

    Args:
        matches: Configured queries that matched the element.
        default: Level applied when nothing matched.

    Returns:
        Winning decision; ties resolve toward fewer matches and
        earlier configured order.

    """
    if not matches:
        return LevelDecision(level=default, decided_by=None, matched=())
    level: Level = max(
        (match.level for match in matches),
        key=lambda item: Constants.severity[item],
    )
    winning: QueryMatch = min(
        (match for match in matches if match.level == level),
        key=lambda item: (item.match_count, item.order),
    )
    return LevelDecision(
        level=level,
        decided_by=winning.query,
        matched=matches,
    )
