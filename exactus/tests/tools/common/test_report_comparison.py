# Copyright (c) 2026
"""Exercise baseline retention and per-section report comparisons."""

from __future__ import annotations

from json import dumps, loads
from shutil import rmtree
from subprocess import CompletedProcess, run
from sys import executable
from textwrap import dedent
from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
)
from exactus.tools.common import report_comparison as comparison
from exactus.tools.common.json_types import JsonDict

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonObject, JsonValue


def test_coverage_remains_unresolved_when_measurements_change(
    tmp_path: Path,
) -> None:
    """Only removing a failing gate resolves it, not a new measured value.

    Args:
        tmp_path: Disposable report baseline.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    previous: dict[str, JsonValue] = {
        "rule": "coverage-per-file",
        "path": "pkg/__init__.py",
        "title": "Coverage below 80%",
        "message": "Coverage is 60%; missing lines: 1-10.",
        "line": 1,
    }
    _ = target.write_text(
        data=dumps(obj={"findings": [previous]}),
        encoding="utf-8",
    )
    current: JsonObject = JsonDict(
        {
            "findings": [
                {
                    **previous,
                    "message": "Coverage is 75%; missing lines: 8-10.",
                    "line": 8,
                },
            ],
        },
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    expect_true(condition=isinstance(changes, dict))
    if isinstance(changes, dict):
        expect_equal(actual=changes["added_count"], expected=0)
        expect_equal(actual=changes["resolved_count"], expected=0)
        expect_equal(actual=changes["unchanged_count"], expected=1)
    fixed: JsonObject = JsonDict({"findings": []})
    comparison.apply(payload=fixed, path=target)
    changes = fixed["comparison"]
    if isinstance(changes, dict):
        expect_equal(actual=changes["resolved_count"], expected=1)
    comparison.clear()


def test_subsections_metrics_and_repeated_findings(tmp_path: Path) -> None:
    """Count repeated findings and compare each linter and coverage metric.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    finding: dict[str, JsonValue] = {
        "source": "ruff",
        "rule": "D401",
        "path": "a.py",
        "title": "Docstring",
    }
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={
                "findings": [finding, finding],
                "extension": {"python": {"coverage": 75.5}},
            },
        ),
    )
    current_data: dict[str, JsonValue] = {
        "findings": [finding],
        "extension": {"python": {"coverage": 80.5}},
    }
    current: JsonObject = JsonDict(current_data)
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    expect_true(condition=isinstance(changes, dict))
    if isinstance(changes, dict):
        expect_equal(actual=changes["resolved_count"], expected=1)
        expect_equal(actual=changes["unchanged_count"], expected=1)
        sections: JsonValue = changes["subsections"]
        if isinstance(sections, list):
            rows: list[dict[str, JsonValue]] = [
                row
                for row in sections
                if isinstance(row, dict)
                and row.get("section") == "Source: ruff"
            ]
            expect_equal(actual=rows[0]["delta"], expected=-1)
        expect_equal(
            actual=changes["categories"],
            expected=[
                {
                    "category": "D401",
                    "title": "D401",
                    "current": 1,
                    "previous": 2,
                    "delta": -1,
                },
            ],
        )
    comparison.clear()


def test_aggregate_deltas_use_previous_tool_snapshots(tmp_path: Path) -> None:
    """Compare pipeline totals and nested tools against its own baseline.

    Args:
        tmp_path: Isolated aggregate directory.

    Raises:
        TypeError: When the comparison payload is not an object.

    """
    comparison.clear()
    finding: dict[str, str] = {
        "source": "ruff",
        "rule": "F401",
        "path": "a.py",
        "title": "Unused",
    }
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={
                "report_snapshots": {
                    "lints": {"findings": [finding]},
                    "docs": {"findings": []},
                },
            },
        ),
    )
    current_data: dict[str, JsonValue] = {
        "report_snapshots": {
            "lints": {"findings": []},
            "docs": {
                "findings": [
                    {"rule": "DOC", "path": "README.md", "title": "Missing"},
                ],
            },
        },
    }
    current: JsonObject = JsonDict(current_data)
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if not isinstance(changes, dict):
        raise TypeError
    expect_equal(actual=changes["delta"], expected=0)
    expect_equal(actual=changes["added_count"], expected=1)
    expect_equal(actual=changes["resolved_count"], expected=1)
    rows: JsonValue = changes["subsections"]
    if isinstance(rows, list):
        deltas: dict[str, JsonValue] = {
            str(object=row["section"]): row["delta"]
            for row in rows
            if isinstance(row, dict)
        }
        expect_equal(actual=deltas["Tool: lints"], expected=-1)
        expect_equal(actual=deltas["Tool: docs"], expected=1)
        expect_equal(actual=deltas["lints / Source: ruff"], expected=-1)
    expect_in(
        member="Category findings",
        container=comparison.markdown(comparison=changes),
    )
    comparison.clear()


def test_baseline_survives_cleanup_and_reaches_worker(tmp_path: Path) -> None:
    """Preserve canonical and named reports across cleanup and processes.

    Args:
        tmp_path: Isolated reports directory.

    """
    comparison.clear()
    output: Path = tmp_path / "reports"
    output.mkdir()
    for name in ("result.json", "README.json"):
        (output / name).write_text(
            data=dumps(
                obj={
                    "report_bundle": {},
                    "findings": [{"rule": "OLD", "path": "a.py"}],
                },
            ),
        )
    comparison.capture(output=output)
    rmtree(path=output)
    script: str = dedent(
        text=(
            "    import json,sys\n    from pathlib import Path\n    from exact"
            "us.tools.common.report_comparison import apply\n    payload={'fin"
            "dings': []}\n    apply(payload=payload,path=Path(sys.argv[1]))\n "
            "   sys.stdout.write(json.dumps(payload['comparison']))\n    "
        ),
    )
    for name in ("result.json", "README.json"):
        worker: CompletedProcess[str] = run(
            args=(executable, "-c", script, str(object=output / name)),
            capture_output=True,
            text=True,
            check=True,
        )
        changes: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=worker.stdout),
        )
        expect_true(condition=changes["available"] is True)
        expect_equal(actual=changes["delta"], expected=-1)
        expect_equal(actual=changes["resolved_count"], expected=1)
    comparison.clear()


def test_first_run_marks_delta_unavailable(tmp_path: Path) -> None:
    """Distinguish a first run from a real zero-change comparison.

    Args:
        tmp_path: Isolated first-run directory.

    """
    comparison.clear()
    current_data: dict[str, JsonValue] = {
        "findings": [{"rule": "A"}],
        "summary": {"findings_total": 1},
    }
    current: JsonObject = JsonDict(current_data)
    comparison.apply(payload=current, path=tmp_path / "result.json")
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        expect_false(condition=changes["available"] is True)
        expect_equal(actual=changes["delta"], expected=None)
    expect_in(
        member="establishes the baseline",
        container=comparison.markdown(comparison=changes),
    )
    comparison.clear()


def test_aggregate_with_counts_but_no_finding_history(tmp_path: Path) -> None:
    """Use recorded totals while leaving missing finding details unavailable.

    Args:
        tmp_path: Isolated aggregate directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(obj={"digests": [{"tool": "lints", "findings": 4}]}),
    )
    current: JsonObject = JsonDict(
        {"report_snapshots": {"lints": {"findings": []}}},
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        expect_equal(actual=changes["previous_total"], expected=4)
        expect_equal(actual=changes["delta"], expected=-4)
        expect_equal(actual=changes["resolved_count"], expected=None)
        rows: JsonValue = changes["subsections"]
        if isinstance(rows, list):
            expect_equal(
                actual=rows[0]["delta"] if isinstance(rows[0], dict) else None,
                expected=-4,
            )
    comparison.clear()


def test_coverage_metrics_exclude_file_details(tmp_path: Path) -> None:
    """Keep coverage totals and findings without expanding file evidence.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    previous: dict[str, JsonValue] = {
        "coverage": {
            "totals": {"percent_covered": 75.0},
            "shards": [{"failed": 3, "duration_seconds": 10}],
            "files": {"old.py": {"summary": {"covered_lines": 10}}},
        },
        "extension": {
            "coverage": {
                "files_below_minimum": [{"path": "old.py", "percent": 20}],
                "minimum_per_file": 80,
            },
        },
    }
    target.write_text(data=dumps(obj=previous), encoding="utf-8")
    current: JsonObject = JsonDict(
        {
            "coverage": {
                "totals": {"percent_covered": 85.0},
                "shards": [{"failed": 0, "duration_seconds": 2}],
                "files": {"new.py": {"summary": {"covered_lines": 30}}},
            },
            "extension": {
                "coverage": {
                    "files_below_minimum": [],
                    "minimum_per_file": 80,
                },
            },
            "findings": [{"rule": "coverage-per-file", "path": "new.py"}],
        },
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    expect_true(condition=isinstance(changes, dict))
    if isinstance(changes, dict):
        expect_equal(
            actual=changes["categories"],
            expected=[
                {
                    "category": "coverage-per-file",
                    "title": "coverage-per-file",
                    "current": 1,
                    "previous": 0,
                    "delta": 1,
                },
            ],
        )
        expect_equal(actual=changes["added_count"], expected=1)
    expect_equal(
        actual=current["coverage"],
        expected={
            "totals": {"percent_covered": 85.0},
            "shards": [{"failed": 0, "duration_seconds": 2}],
            "files": {"new.py": {"summary": {"covered_lines": 30}}},
        },
    )
    comparison.clear()


def test_sparse_count_maps_compare_missing_members_as_zero(
    tmp_path: Path,
) -> None:
    """Report resolved severity and rule counters as real negative deltas.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={
                "summary": {"severity": {"error": 2}, "by_rule": {"D401": 2}},
            },
        ),
    )
    current: JsonObject = JsonDict(
        {"summary": {"severity": {}, "by_rule": {}}},
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        metrics: JsonValue = changes["categories"]
        if isinstance(metrics, list):
            for row in metrics:
                if isinstance(row, dict):
                    expect_equal(actual=row["current"], expected=0)
                    expect_equal(actual=row["delta"], expected=-2)
    comparison.clear()


def test_rule_categories_include_zero_counts_and_real_deltas(
    tmp_path: Path,
) -> None:
    """Compare declared rules, including rules with no current findings.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={
                "extension": {
                    "rules": [
                        {
                            "rule": "RDM001",
                            "title": "Missing README.md",
                            "count": 2,
                        },
                        {
                            "rule": "RDM002",
                            "title": "Undocumented subdirectory",
                            "count": 0,
                        },
                    ],
                },
                "findings": [],
            },
        ),
    )
    current: JsonObject = JsonDict(
        {
            "extension": {
                "rules": [
                    {
                        "rule": "RDM001",
                        "title": "Missing README.md",
                        "count": 0,
                    },
                    {
                        "rule": "RDM002",
                        "title": "Undocumented subdirectory",
                        "count": 0,
                    },
                ],
            },
            "findings": [],
            "test_execution": {"tests": [{"shard": 77}]},
        },
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        expect_equal(
            actual=changes["categories"],
            expected=[
                {
                    "category": "RDM001",
                    "title": "Missing README.md",
                    "current": 0,
                    "previous": 2,
                    "delta": -2,
                },
                {
                    "category": "RDM002",
                    "title": "Undocumented subdirectory",
                    "current": 0,
                    "previous": 0,
                    "delta": 0,
                },
            ],
        )
        expect_false(condition="metrics" in changes)
    comparison.clear()


def test_local_server_findings_ignore_run_time_and_ephemeral_port(
    tmp_path: Path,
) -> None:
    """Repeated endpoint failures retain identity across local server runs.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    messages: tuple[str, ...] = (
        '127.0.0.1 - - [05/Oct/2026 04:15:56] "GET /api/error HTTP/1.1" 500 -',
        "http: HTTP 500 http://127.0.0.1:61544/api/error",
        "console: Failed to load resource http://localhost:61544/api/error",
    )
    findings: list[JsonValue] = [
        {"rule": "FRONTEND001", "path": "server", "message": message}
        for message in messages
    ]
    target.write_text(data=dumps(obj={"findings": findings}))
    current: JsonObject = JsonDict(
        {
            "findings": [
                {
                    "rule": "FRONTEND001",
                    "path": "server",
                    "message": message.replace("61544", "52558").replace(
                        "04:15:56",
                        "04:26:54",
                    ),
                }
                for message in messages
            ],
        },
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        expect_equal(actual=changes["delta"], expected=0)
        expect_equal(actual=changes["added_count"], expected=0)
        expect_equal(actual=changes["resolved_count"], expected=0)
        expect_equal(actual=changes["unchanged_count"], expected=3)
        expect_equal(actual=changes["added"], expected=[])
        expect_equal(actual=changes["resolved"], expected=[])
    else:
        expect_true(condition=False)
    comparison.clear()


def test_equal_totals_still_detect_different_endpoints(tmp_path: Path) -> None:
    """A different failed endpoint remains a real replacement finding.

    Args:
        tmp_path: Isolated report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={
                "findings": [
                    {
                        "rule": "FRONTEND001",
                        "message": "HTTP 500 http://127.0.0.1:10001/api/old",
                    },
                ],
            },
        ),
    )
    current: JsonObject = JsonDict(
        {
            "findings": [
                {
                    "rule": "FRONTEND001",
                    "message": "HTTP 500 http://127.0.0.1:10002/api/new",
                },
            ],
        },
    )
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    if isinstance(changes, dict):
        expect_equal(actual=changes["delta"], expected=0)
        expect_equal(actual=changes["added_count"], expected=1)
        expect_equal(actual=changes["resolved_count"], expected=1)
        expect_equal(actual=changes["unchanged_count"], expected=0)
    else:
        expect_true(condition=False)
    comparison.clear()


def test_capture_records_previous_duration(tmp_path: Path) -> None:
    """The duration of a captured report is available by canonical path.

    Args:
        tmp_path: Disposable report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={"duration_seconds": 123.456, "findings": [{"rule": "A"}]},
        ),
    )
    comparison.capture(output=tmp_path)
    expect_equal(
        actual=comparison.previous_duration(path=target),
        expected=123.456,
    )
    comparison.clear()
    expect_none(value=comparison.previous_duration(path=target))


def test_apply_includes_previous_duration(tmp_path: Path) -> None:
    """The comparison block carries the previous run duration when known.

    Args:
        tmp_path: Disposable report directory.

    """
    comparison.clear()
    target: Path = tmp_path / "result.json"
    target.write_text(
        data=dumps(
            obj={"duration_seconds": 42.5, "findings": [{"rule": "A"}]},
        ),
    )
    current: JsonObject = JsonDict({"findings": [{"rule": "A"}]})
    comparison.apply(payload=current, path=target)
    changes: JsonValue = current["comparison"]
    expect_true(condition=isinstance(changes, dict))
    if isinstance(changes, dict):
        expect_equal(
            actual=changes["previous_duration_seconds"],
            expected=42.5,
        )
    comparison.clear()


def test_first_run_comparison_duration_is_none(tmp_path: Path) -> None:
    """A first-run comparison explicitly records no previous duration.

    Args:
        tmp_path: Disposable report directory.

    """
    comparison.clear()
    current: JsonObject = JsonDict({"findings": [{"rule": "A"}]})
    comparison.apply(payload=current, path=tmp_path / "result.json")
    changes: JsonValue = current["comparison"]
    expect_true(condition=isinstance(changes, dict))
    if isinstance(changes, dict):
        expect_none(value=changes["previous_duration_seconds"])
    comparison.clear()


def test_markdown_renders_previous_duration() -> None:
    """The comparison section mentions the previous run duration."""
    text: str = comparison.markdown(
        comparison={
            "available": True,
            "current_total": 1,
            "previous_total": 1,
            "delta": 0,
            "added_count": 0,
            "resolved_count": 0,
            "unchanged_count": 1,
            "previous_duration_seconds": 7.891,
            "subsections": [],
            "categories": [],
        },
    )
    expect_in(member="Previous run completed in **7.891s**", container=text)


def test_markdown_omits_missing_previous_duration() -> None:
    """When no previous duration is recorded the line is skipped."""
    text: str = comparison.markdown(
        comparison={
            "available": True,
            "current_total": 1,
            "previous_total": 1,
            "delta": 0,
            "added_count": 0,
            "resolved_count": 0,
            "unchanged_count": 1,
            "previous_duration_seconds": None,
            "subsections": [],
            "categories": [],
        },
    )
    expect_false(condition="Previous run completed" in text)
