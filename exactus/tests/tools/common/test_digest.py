# Copyright (c) 2026
"""Tool reports are digested into failure summaries for aggregates."""

from __future__ import annotations

from json import dumps
from typing import TYPE_CHECKING, Final, final

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.common.digest import (
    ToolDigest,
    digest_data,
    digest_report,
    render_failure,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[str] = "/work/project"


def _fields() -> dict[str, JsonValue]:
    """Build a representative ``result.json`` payload.

    Returns:
        Findings, a tool-specific list, failed tests, and gate data.

    """
    return {
        "analyzer": "kwargs_typehints",
        "project_root": Constants.root,
        "findings": [
            {
                "file": f"{Constants.root}/a.py",
                "line": 3,
                "rule": "E1",
                "message": "m1",
            },
            {
                "file": f"{Constants.root}/a.py",
                "line": 9,
                "rule": "E1",
                "message": "m2",
            },
            {
                "file": f"{Constants.root}/b.py",
                "line": 1,
                "code": "W2",
                "message": "x|y",
            },
            {"file": "c.py", "line": 2, "message": "no rule"},
        ],
        "type_hints": [
            {"file": f"{Constants.root}/d.py", "line": 5, "reason": "bare"},
        ],
        "test_execution": {
            "failed_tests": [
                {"test": "t.py::test_a", "detail": "assert 1 == 2\nmore"},
            ],
        },
        "coverage": {"totals": {"percent_covered_display": "88"}},
        "gates": {
            "fail_under": 90,
            "per_file_minimum": 80,
            "files_below": ["x.py", "y.py"],
        },
    }


def test_digest_counts_rules_files_and_extras() -> None:
    """Rules, hot files, extras, tests, and gates are all summarized."""
    digest: ToolDigest = digest_report(
        tool="demo",
        fields=_fields(),
        status="FAIL",
        resume="FAIL: exit 1",
    )
    expect_equal(actual=digest.findings, expected=5)
    expect_equal(actual=dict(digest.rules)["E1"], expected=2)
    expect_equal(actual=dict(digest.rules)["kwargs_typehints"], expected=1)
    expect_equal(actual=dict(digest.rules)["missing-type-hint"], expected=1)
    expect_equal(actual=digest.files[0], expected=("a.py", 2))
    expect_equal(actual=digest.top[0].location, expected="a.py:3")
    expect_equal(
        actual=digest.failed_tests,
        expected=(("t.py::test_a", "assert 1 == 2"),),
    )
    expect_in(member="Total coverage 88%", container=digest.notes)
    expect_in(member="1 failed test(s)", container=digest.notes)
    expect_in(
        member="Per-file gate 80%: 2 file(s) below",
        container=digest.notes,
    )


def test_normalized_findings_skip_the_legacy_lists() -> None:
    """Normalized findings hold the tool lists; none is counted twice."""
    fields: dict[str, JsonValue] = {
        "analyzer": "kwargs_typehints",
        "project_root": Constants.root,
        "findings": [
            {"id": "KWARGS-001", "file": "a.py", "line": 3, "rule": "R1"},
            {"id": "KWARGS-002", "file": "d.py", "line": 5, "rule": "R2"},
        ],
        "type_hints": [{"file": "d.py", "line": 5, "reason": "bare"}],
        "bare_imports": [{"file": "a.py", "line": 1, "module": "os"}],
    }
    digest: ToolDigest = digest_report(
        tool="demo",
        fields=fields,
        status="FAIL",
        resume="FAIL: exit 1",
    )
    expect_equal(actual=digest.findings, expected=2)
    expect_equal(actual=dict(digest.rules), expected={"R1": 1, "R2": 1})


def test_render_failure_lists_tables_and_escapes_pipes() -> None:
    """The failure section shows rules, files, findings, and failed tests."""
    digest: ToolDigest = digest_report(
        tool="demo",
        fields=_fields(),
        status="FAIL",
        resume="FAIL: exit 1",
    )
    text: str = "\n".join(render_failure(digest=digest))
    for expected in (
        "### `demo` — FAIL",
        "| Rule | Count |",
        "| File | Findings |",
        "| Rule | Location | Message |",
        "| Failed test | Reason |",
        "x\\|y",
    ):
        expect_in(member=expected, container=text)


def test_empty_report_yields_an_empty_digest() -> None:
    """A report without findings still renders and serializes."""
    digest: ToolDigest = digest_report(
        tool="quiet",
        fields={},
        status="PASS",
        resume="",
    )
    expect_equal(actual=digest.findings, expected=0)
    expect_equal(actual=digest_data(digest=digest)["tool"], expected="quiet")
    expect_in(
        member="No resume reported.",
        container="\n".join(render_failure(digest=digest)),
    )
    expect_in(
        member='"tool": "quiet"',
        container=dumps(obj=digest_data(digest=digest)),
    )


def test_distinct_groups_ignore_origin_and_port() -> None:
    """Findings differing only by origin collapse into one counted group."""
    findings: list[JsonValue] = [
        {
            "file": f"variant-{index}",
            "rule": "SCR001",
            "message": f"HTTP 500 http://127.0.0.1:{6000 + index}/api",
        }
        for index in range(3)
    ]
    digest: ToolDigest = digest_report(
        tool="shots",
        fields={"findings": findings},
        status="FAIL",
        resume="",
    )
    expect_equal(
        actual=digest.distinct,
        expected=(("SCR001", "HTTP 500 <origin>/api", 3, "variant-0"),),
    )
