# Copyright (c) 2026
"""Coverage reports distinguish branch measurements and focus on failures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal, expect_in, expect_not_in
from exactus.tools.coverage_tests.report import (
    CoverageGates,
    CoverageTestsReport,
    Ranges,
    ReportInputs,
)
from exactus.tools.reports.render import ReportTemplates

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ([7], "7"),
        ([1, 2], "1, 2"),
        ([1, 2, 3], "1-3"),
        ([1, 5, 6, 7, 8, 9, 22, 23, 24], "1, 5-9, 22-24"),
        ([5, 6, 9, 10], "5, 6, 9, 10"),
        ([9, 1, 2, 1], "1, 2, 9"),
    ],
)
def test_ranges_text_compacts_only_runs_of_three(
    *,
    lines: list[int],
    expected: str,
) -> None:
    """Two-line runs stay comma-separated; longer runs become spans.

    Args:
        lines: Line numbers to collapse and render.
        expected: Rendered range text.

    """
    expect_equal(
        actual=Ranges.text(ranges=Ranges.collapse(lines=lines)),
        expected=expected,
    )


def test_coverage_report_keeps_failure_details_out_of_summary_tables(
    tmp_path: Path,
) -> None:
    """Render a passing overall gate with a failing per-file requirement.

    Args:
        tmp_path: Isolated source and report directory.

    """
    (tmp_path / "app.py").write_text(data="value = 1\n" * 10)
    inputs: ReportInputs = ReportInputs(
        root=tmp_path,
        context=1,
        coverage={
            "totals": {
                "percent_covered": 91.67,
                "num_statements": 100,
                "covered_lines": 95,
                "missing_lines": 5,
                "num_branches": 20,
                "covered_branches": 15,
            },
            "files": {
                "app.py": {
                    "summary": {"percent_covered": 70},
                    "missing_lines": [3, 4, 5],
                },
            },
        },
        graph={},
        javascript=None,
        execution={
            "status": 1,
            "tests": [{"outcome": "FAILED"}],
            "failed_tests": [{"test": "test_failure", "kind": "FAILED"}],
        },
        groups=(),
        gates=CoverageGates(fail_under=90, per_file_minimum=80),
    )
    data: dict[str, JsonValue] = CoverageTestsReport.report_data(inputs=inputs)
    model: dict[str, JsonValue] = {
        **data,
        "tool": {"name": "coverage_tests", "display_name": "Coverage"},
        "run": {"status": "FAIL"},
        "invocation": {"command": "exactus --coverage_tests", "arguments": []},
        "environment": {"variables": []},
        "artifacts": [
            {
                "name": "shard-000.log",
                "path": "ARTIFACTS/TESTS/pytest-shards/shard-000.log",
                "bytes": 10,
            },
        ],
    }
    rendered: str = ReportTemplates.render(
        model=model,
        tool_dir=ReportTemplates.tool_dir(analyzer="coverage_tests"),
    ).markdown
    expect_in(
        member="| Python | 91.67% | Lines + branches |",
        container=rendered,
    )
    expect_in(member="| app.py | 70.00% | 80.00% | 10.00", container=rendered)
    expect_in(
        member="**Uncovered lines**\n\n```text\n3-5\n```",
        container=rendered,
    )
    expect_equal(
        actual=rendered.count("### Files below the minimum"),
        expected=1,
    )
    expect_in(member="### Failed tests — 1", container=rendered)
    expect_in(member="test_failure", container=rendered)
    expect_not_in(member="| Uncovered lines |", container=rendered)
    expect_not_in(member="shard-000.log", container=rendered)
    expect_not_in(member="Pytest shards", container=rendered)
    expect_not_in(member="Test logs", container=rendered)
