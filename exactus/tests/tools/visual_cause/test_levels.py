# Copyright (c) 2026
"""The most severe matching query decides a finding's level."""

from __future__ import annotations

from exactus.tests.common.support import expect_equal, expect_none
from exactus.tools.visual_cause.levels import (
    Level,
    LevelDecision,
    QueryMatch,
    decide,
)


def _match(*, level: Level, query: str, count: int, order: int) -> QueryMatch:
    """Build one matched configured query.

    Args:
        level: Level the query assigns.
        query: Query text.
        count: Elements the query matches in the page.
        order: Configured position.

    Returns:
        The matched query.

    """
    return QueryMatch(level=level, query=query, match_count=count, order=order)


def test_default_level_applies_without_matches() -> None:
    """No match means the configured default decides, with no query."""
    decision: LevelDecision = decide(matches=(), default="warning")
    expect_equal(actual=decision.level, expected="warning")
    expect_none(value=decision.decided_by)
    expect_equal(actual=decision.matched, expected=())


def test_most_severe_level_wins() -> None:
    """Fail outranks warning, which outranks accept."""
    matches: tuple[QueryMatch, ...] = (
        _match(level="accept", query="a", count=1, order=0),
        _match(level="fail", query="f", count=9, order=1),
        _match(level="warning", query="w", count=1, order=2),
    )
    decision: LevelDecision = decide(matches=matches, default="accept")
    expect_equal(actual=decision.level, expected="fail")
    expect_equal(actual=decision.decided_by, expected="f")
    expect_equal(actual=decision.matched, expected=matches)


def test_narrowest_then_earliest_query_breaks_ties() -> None:
    """Among equal levels the query matching fewer elements decides."""
    matches: tuple[QueryMatch, ...] = (
        _match(level="warning", query="broad", count=5, order=0),
        _match(level="warning", query="late", count=2, order=3),
        _match(level="warning", query="early", count=2, order=1),
    )
    decision: LevelDecision = decide(matches=matches, default="fail")
    expect_equal(actual=decision.decided_by, expected="early")
