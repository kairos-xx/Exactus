# Copyright (c) 2026
"""Verify Refurb diagnostics and optional offline tool behavior."""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from exactus.packages.all_lints import (
    AuditRunner,
    Cli,
    Diagnostic,
    ReportBuilder,
    ToolResult,
    ToolSpec,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from exactus.packages.all_lints.core import JsonObject, JsonValue


def test_refurb_cli_registered_optional() -> None:
    """Missing Refurb must remain a reported nonfatal optional tool."""
    specs: list[ToolSpec] = [
        spec for spec in Cli.specs() if spec.name == "refurb"
    ]
    expect_equal(actual=len(specs), expected=1)
    expect_true(condition=specs[0].optional)
    expect_equal(actual=specs[0].parser, expected="refurb")


def test_refurb_output_parses(tmp_path: Path) -> None:
    """Normalize native Refurb text output with Windows-aware path handling.

    Args:
        tmp_path: Per-test project directory.

    """
    runner: AuditRunner = AuditRunner(root=tmp_path, workers=1)
    results: list[Diagnostic] = cast(
        typ="list[Diagnostic]",
        val=private_call(
            owner=runner,
            name="_refurb",
            file=Path("src/app.py"),
            text="src/app.py:3:17 [FURB109]: Use a tuple instead of a list\n",
        ),
    )
    expect_equal(actual=len(results), expected=1)
    expect_equal(actual=results[0].code, expected="FURB109")
    expect_equal(actual=results[0].line, expected=3)
    expect_equal(actual=results[0].column, expected=17)


def test_optional_unavailable_is_reported_without_failure(
    tmp_path: Path,
) -> None:
    """Distinguish optional absence from mandatory tooling failure.

    Args:
        tmp_path: Per-test project directory.

    """
    unavailable: ToolResult = ToolResult(
        name="refurb",
        status="unavailable",
        duration_seconds=0.0,
        total_files=0,
        completed_files=0,
        diagnostics=[],
        files=[],
        optional=True,
    )
    report: JsonObject = ReportBuilder.build(
        root=tmp_path,
        started_at=datetime.now(tz=UTC),
        duration_seconds=0.0,
        results=[unavailable],
    )
    expect_equal(actual=report["ok"], expected=True)
    summary: JsonValue = report["summary"]
    expect_true(condition=isinstance(summary, dict))
    if isinstance(summary, dict):
        expect_equal(actual=summary["optional_unavailable"], expected=1)
    mandatory: ToolResult = ToolResult(
        name="ruff",
        status="unavailable",
        duration_seconds=0.0,
        total_files=0,
        completed_files=0,
        diagnostics=[],
        files=[],
    )
    failed: JsonObject = ReportBuilder.build(
        root=tmp_path,
        started_at=datetime.now(tz=UTC),
        duration_seconds=0.0,
        results=[unavailable, mandatory],
    )
    expect_equal(actual=failed["ok"], expected=False)
