# Copyright (c) 2026
"""Gate JavaScript coverage while preserving passing test results."""

from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CoverageConfig,
    CoverageCoreTables,
)
from exactus.tools.coverage_tests.report import (
    CoverageGates,
    CoverageTestsReport,
    ReportInputs,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def test_javascript_gates_are_reported_as_coverage_findings(
    tmp_path: Path,
) -> None:
    """Keep a low-coverage JavaScript lane in the coverage part.

    Args:
        tmp_path: Temporary project root.

    """
    inputs: ReportInputs = ReportInputs(
        root=tmp_path,
        context=3,
        coverage={"totals": {"percent_covered": 100}, "files": {}},
        graph={},
        execution={"status": 0},
        groups=(),
        javascript={
            "status": 0,
            "percent_covered": 50,
            "files": [
                {
                    "path": "app.js",
                    "percent_covered": 50,
                    "uncovered_lines": [2, 3],
                },
            ],
        },
        gates=CoverageGates(fail_under=90, per_file_minimum=80),
    )
    findings: list[dict[str, JsonValue]] = (
        CoverageTestsReport.coverage_findings(inputs=inputs)
    )
    expect_equal(
        actual=[item["rule"] for item in findings],
        expected=["coverage-javascript-total", "coverage-per-file"],
    )
    expect_in(
        member="JavaScript",
        container=str(object=findings[0]["message"]),
    )
    expect_equal(actual=findings[1]["path"], expected="app.js")
    expect_equal(actual=findings[1]["uncovered"], expected="2, 3")


def test_package_named_javascript_sources_are_measured(tmp_path: Path) -> None:
    """Sources under a ``packages`` directory are measured like others.

    Args:
        tmp_path: Isolated project and source directory.

    """
    source: Path = tmp_path / "exactus" / "packages" / "maintained"
    source.mkdir(parents=True)
    script: Path = source / "dashboard.js"
    script.write_text(data="export const ready = true;\n", encoding="utf-8")
    generated: Path = source / "node_modules" / "dependency.js"
    generated.parent.mkdir()
    generated.write_text(data="export const ready = true;\n", encoding="utf-8")
    (tmp_path / "exactus" / "packages" / "other.js").write_text(
        data="export const ignored = true;\n",
        encoding="utf-8",
    )
    test_path: Path = tmp_path / "tests" / "dashboard.test.mjs"
    test_path.parent.mkdir()
    test_path.write_text(
        data=dedent(
            text=(
                "    import test from 'node:test';\n    import assert from"
                " 'node:assert/strict';\n    import {ready} from '../exact"
                "us/packages/maintained/dashboard.js';\n    test('ready', "
                "() => assert.equal(ready, true));\n    "
            ),
        ),
        encoding="utf-8",
    )
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=tmp_path,
            output=tmp_path / "reports",
            source_roots=(tmp_path,),
            branch=True,
            fail_under=None,
            excluded_dirs=CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
            pytest_args=(),
        ),
    )
    expect_equal(actual=runner.run(), expected=0)
    inputs: ReportInputs | None = runner.report_inputs
    expect_equal(actual=inputs is None, expected=False)
    if inputs is None:
        return
    javascript: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=inputs.javascript,
    )
    files: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=javascript["files"],
    )
    expect_equal(
        actual=[entry["path"] for entry in files],
        expected=["exactus/packages/maintained/dashboard.js"],
    )


def test_javascript_only_project_runs_tests_and_fails_low_coverage(
    tmp_path: Path,
) -> None:
    """Run Node tests even without Python tests and enforce both gates.

    Args:
        tmp_path: Temporary project root.


    """
    root: Path = tmp_path / "project"
    (root / "tests").mkdir(parents=True)
    (root / "app.mjs").write_text(
        data=dedent(
            text=(
                "    export function loaded() { return true; }\n    export"
                " function unused() {\n    "
            ),
        )
        + "\n".join(f"  const n{i} = {i};" for i in range(20))
        + "\n  return n19;\n}\n",
    )
    (root / "tests/app.test.mjs").write_text(
        data=dedent(
            text=(
                "    import test from 'node:test';\n    import assert from"
                " 'node:assert/strict';\n    import {loaded} from '../app."
                "mjs';\n    test('loaded', () => assert.equal(loaded(), tr"
                "ue));\n    "
            ),
        ),
    )
    output: Path = tmp_path / "reports"
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=root,
            output=output,
            source_roots=(root,),
            branch=True,
            fail_under=90,
            per_file_minimum=80,
            excluded_dirs=CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
            pytest_args=(),
            include_unreached=True,
        ),
    )
    expect_equal(actual=runner.run(), expected=1)
    inputs: ReportInputs | None = runner.report_inputs
    expect_equal(actual=inputs is None, expected=False)
    if inputs is None:
        return
    javascript: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=inputs.javascript,
    )
    expect_equal(actual=javascript["status"], expected=0)
    expect_equal(actual=javascript["failed_tests"], expected=[])
    completion: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(output / "ARTIFACTS/COVERAGE/completion.json").read_text(),
        ),
    )
    expect_equal(actual=completion["js_returncode"], expected=0)
    expect_equal(actual=completion["returncode"], expected=1)


def test_unavailable_javascript_runtime_keeps_distinct_reason(
    tmp_path: Path,
) -> None:
    """A missing Node runtime reports its detail, not a generic failure.

    Args:
        tmp_path: Temporary project root.

    """
    inputs: ReportInputs = ReportInputs(
        root=tmp_path,
        context=3,
        coverage={"totals": {"percent_covered": 100}, "files": {}},
        graph={},
        execution={"status": 0},
        groups=(),
        javascript={
            "status": 2,
            "detail": "node executable is unavailable",
            "tests": ["app.test.js"],
        },
        gates=CoverageGates(fail_under=90, per_file_minimum=80),
    )
    part: dict[str, JsonValue] = CoverageTestsReport.tests_part(inputs=inputs)
    expect_equal(actual=part["status"], expected="FAIL")
    expect_in(
        member="node executable is unavailable",
        container=str(object=part["reason"]),
    )
