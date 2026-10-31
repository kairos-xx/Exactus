# Copyright (c) 2026
"""Verify readable report timestamps and recorded-time precedence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tests.common.support import expect_equal
from exactus.tools.common.report_time import readable_time, report_times

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def test_readable_timezone_conversion() -> None:
    """Show explicit UTC and preserve instants from offset timestamps."""
    expect_equal(
        actual=readable_time(value="2026-10-04T22:42:17+01:00"),
        expected="04 October 2026, 21:42:17 UTC",
    )
    expect_equal(actual=readable_time(value="invalid"), expected=None)
    expect_equal(actual=readable_time(value=None), expected=None)
    expect_equal(
        actual=readable_time(value="2026-10-04T21:42:17"),
        expected="04 October 2026, 21:42:17 timezone not recorded",
    )


def test_run_time_precedence() -> None:
    """Prefer the run start over finish and report-generation timestamps."""
    start: str = "2026-10-04T20:00:00Z"
    finish: str = "2026-10-04T20:05:00Z"
    generated: str = "2026-10-04T20:06:00Z"
    result: dict[str, JsonValue] = report_times(
        payload={
            "run": {"started_at": start, "finished_at": finish},
            "generated_at": generated,
        },
    )
    expect_equal(actual=result["run_at"], expected=start)
    expect_equal(
        actual=result["run_at_human"],
        expected="04 October 2026, 20:00:00 UTC",
    )
    expect_equal(
        actual=report_times(
            payload={
                "run": {"started_at": None, "finished_at": finish},
                "generated_at": generated,
            },
        )["run_at"],
        expected=finish,
    )
    expect_equal(
        actual=report_times(payload={"generated_at": generated})["run_at"],
        expected=generated,
    )
