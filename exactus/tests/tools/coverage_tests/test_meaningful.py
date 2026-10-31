# Copyright (c) 2026
"""Meaningful classification, configuration, and coverage integration."""

from __future__ import annotations

from json import loads
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.meaningful import UnitTestLevel
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tools.coverage_tests.main import main, parse_args
from exactus.tools.coverage_tests.meaningful import (
    MeaningfulConfig,
    MeaningfulResult,
    analyze_unreached,
    merge_results,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path
    from typing import Literal

    from exactus.tools.common.json_types import JsonValue


def test_meaningful_parser_defaults_and_complete_policy() -> None:
    """Expose enforcement defaults and every Meaningful policy family."""
    options: Namespace = parse_args(arguments=("x",))
    expect_equal(actual=options.meaningful, expected="require")
    expect_equal(actual=options.meaningful_minimum_level, expected="TEST-2")
    expect_equal(actual=options.meaningful_unclassified, expected="filtered")
    expect_equal(actual=options.meaningful_evidence_context, expected=2)
    expect_equal(actual=options.meaningful_threshold_test_1_to_2, expected=0.5)
    expect_equal(actual=options.meaningful_weight_side_effects, expected=1.4)
    expect_equal(actual=options.meaningful_cap_source_lines, expected=300)
    expect_equal(
        actual=options.meaningful_floor_high_complexity_test_2_to_3,
        expected=0.75,
    )


def test_meaningful_pyproject_and_cli_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load Meaningful settings from pyproject and prefer explicit CLI.

    Args:
        tmp_path: Tmp path.
        monkeypatch: Monkeypatch.

    """
    config: Path = tmp_path / "pyproject.toml"
    config.write_text(
        data=(
            dedent(
                text=(
                    '    [tool.exactus.coverage_tests]\n    meaningful = "'
                    'classify"\n    meaningful-minimum-level = "TEST-3"\n '
                    "   meaningful-workers = 2\n    meaningful-weight-beha"
                    "vior = 1.7\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(name="EXACTUS_CONFIG", value=str(object=config))
    configured: Namespace = parse_args(arguments=("x",))
    expect_equal(actual=configured.meaningful, expected="classify")
    expect_equal(actual=configured.meaningful_minimum_level, expected="TEST-3")
    expect_equal(actual=configured.meaningful_workers, expected=2)
    expect_equal(actual=configured.meaningful_weight_behavior, expected=1.7)
    overridden: Namespace = parse_args(arguments=("x", "--meaningful", "off"))
    expect_equal(actual=overridden.meaningful, expected="off")


def test_meaningful_parser_accepts_all_control_families() -> None:
    """Map representative flags from every Meaningful option family."""
    options: Namespace = parse_args(
        arguments=(
            "x",
            "--meaningful",
            "classify",
            "--meaningful-minimum-level",
            "TEST-3",
            "--meaningful-unclassified",
            "actionable",
            "--meaningful-workers",
            "2",
            "--meaningful-evidence-context",
            "4",
            "--meaningful-threshold-test-0-to-1",
            "0.1",
            "--meaningful-weight-behavior",
            "2.0",
            "--meaningful-cap-behavioral-statements",
            "40",
            "--meaningful-floor-side-effect-test-1-to-2",
            "0.8",
        ),
    )
    expect_equal(actual=options.meaningful, expected="classify")
    expect_equal(actual=options.meaningful_minimum_level, expected="TEST-3")
    expect_equal(actual=options.meaningful_unclassified, expected="actionable")
    expect_equal(actual=options.meaningful_workers, expected=2)
    expect_equal(actual=options.meaningful_evidence_context, expected=4)
    expect_equal(actual=options.meaningful_threshold_test_0_to_1, expected=0.1)
    expect_equal(actual=options.meaningful_weight_behavior, expected=2.0)
    expect_equal(
        actual=options.meaningful_cap_behavioral_statements,
        expected=40,
    )
    expect_equal(
        actual=options.meaningful_floor_side_effect_test_1_to_2,
        expected=0.8,
    )


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--meaningful-workers", "0"),
        ("--meaningful-evidence-context", "-1"),
        ("--meaningful-threshold-test-0-to-1", "1.1"),
        ("--meaningful-weight-behavior", "-0.1"),
        ("--meaningful-cap-source-lines", "0"),
        ("--meaningful-floor-side-effect-test-1-to-2", "-0.1"),
    ],
)
def test_meaningful_parser_rejects_invalid_policy_values(
    flag: str,
    value: str,
) -> None:
    """Fail cleanly for invalid Meaningful numeric settings.

    Args:
        flag: Flag.
        value: Value.

    """
    with pytest.raises(expected_exception=SystemExit):
        parse_args(arguments=("x", flag, value))


def test_adapter_preserves_successes_and_failures(tmp_path: Path) -> None:
    """Keep one canonical row for every path even when analysis fails.

    Args:
        tmp_path: Tmp path.

    """
    structural: Path = tmp_path / "structural.py"
    broken: Path = tmp_path / "broken.py"
    structural.write_text(data='"""Only structure."""\n', encoding="utf-8")
    broken.write_text(data="def broken(:\n", encoding="utf-8")
    result: MeaningfulResult = analyze_unreached(
        root=tmp_path,
        paths=(structural, broken),
        config=MeaningfulConfig(minimum_level=UnitTestLevel.TEST_0),
    )
    expect_equal(actual=len(result.rows), expected=2)
    by_path: dict[str, dict[str, JsonValue]] = {
        cast(typ="str", val=row["target"]): row for row in result.rows
    }
    expect_equal(
        actual=by_path["structural.py"]["status"],
        expected="actionable",
    )
    expect_equal(
        actual=by_path["broken.py"]["status"],
        expected="unclassified",
    )
    expect_in(member="failure", container=by_path["broken.py"])
    expect_equal(
        actual=result.artifact["selected_paths"],
        expected=["structural.py", "broken.py"],
    )


def test_adapter_respects_configured_level_boundary(tmp_path: Path) -> None:
    """Filter a structural file when only TEST-3 is actionable.

    Args:
        tmp_path: Tmp path.

    """
    structural: Path = tmp_path / "structural.py"
    structural.write_text(data='"""Only structure."""\n', encoding="utf-8")
    result: MeaningfulResult = analyze_unreached(
        root=tmp_path,
        paths=(structural,),
        config=MeaningfulConfig(minimum_level=UnitTestLevel.TEST_3),
    )
    expect_equal(actual=result.rows[0]["level"], expected="TEST-0")
    expect_equal(actual=result.rows[0]["status"], expected="filtered")
    expect_false(condition=result.rows[0]["actionable"] is True)


def test_meaningful_detects_javascript_not_covered_by_tests(
    tmp_path: Path,
) -> None:
    """Require tests for behavioral JavaScript reported as uncovered.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = tmp_path / "selector_sandbox.js"
    source.write_text(
        data=(
            dedent(
                text=(
                    "    async context => {\n      try {\n        if (cont"
                    "ext.targets.length) context.log('running');\n        "
                    "return await Promise.all(context.targets);\n      } c"
                    "atch (error) { throw error; }\n    };\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    result: MeaningfulResult = analyze_unreached(
        root=tmp_path,
        paths=(source,),
        config=MeaningfulConfig(),
    )
    row: dict[str, JsonValue] = result.rows[0]
    expect_equal(actual=row["source"], expected="meaningful")
    expect_equal(actual=row["status"], expected="actionable")
    expect_true(condition=row["actionable"] is True)


@pytest.mark.parametrize(
    ("policy", "actionable", "analysis_error"),
    [
        ("filtered", False, False),
        ("actionable", True, False),
        ("error", False, True),
    ],
)
def test_adapter_applies_unclassified_policy(
    *,
    policy: str,
    actionable: bool,
    analysis_error: bool,
    tmp_path: Path,
) -> None:
    """Apply every configured policy to a retained failed analysis row.

    Args:
        policy: Policy.
        actionable: Actionable.
        analysis_error: Analysis error.
        tmp_path: Tmp path.

    """
    broken: Path = tmp_path / "broken.py"
    broken.write_text(data="def broken(:\n", encoding="utf-8")
    result: MeaningfulResult = analyze_unreached(
        root=tmp_path,
        paths=(broken,),
        config=MeaningfulConfig(
            unclassified=cast(
                typ="Literal['filtered', 'actionable', 'error']",
                val=policy,
            ),
        ),
    )
    row: dict[str, JsonValue] = result.rows[0]
    expect_equal(actual=row["status"], expected="unclassified")
    expect_equal(actual=row["actionable"], expected=actionable)
    expect_equal(actual=row["analysis_error"], expected=analysis_error)


def _project(*, root: Path) -> None:
    """Create one reached source and one unreached source.

    Args:
        root: Root.

    """
    package: Path = root / "app"
    tests: Path = root / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (package / "__init__.py").write_text(data="", encoding="utf-8")
    (package / "reached.py").write_text(
        data="def value():\n    return 1\n",
        encoding="utf-8",
    )
    (package / "unreached.py").write_text(
        data="def choose(value):\n    return 1 if value else 2\n",
        encoding="utf-8",
    )
    (tests / "test_reached.py").write_text(
        data=(
            dedent(
                text=(
                    "    from app.reached import value\n    \n    def test"
                    "_value():\n        assert value() == 1\n    "
                ),
            )
        ),
        encoding="utf-8",
    )


def _payload(*, output: Path, name: str) -> dict[str, JsonValue]:
    """Load one JSON artifact from a coverage-tests run.

    Args:
        output: Output.
        name: Name.

    Returns:
        The resulting value.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(output / "ARTIFACTS" / "COVERAGE" / name).read_text(
                encoding="utf-8",
            ),
        ),
    )


def test_require_counts_unreached_source_at_zero(tmp_path: Path) -> None:
    """Count required unreached files at zero and fail the coverage gate.

    Args:
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / "project"
    output: Path = tmp_path / "require"
    _project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--meaningful-minimum-level",
            "TEST-0",
        ),
    )
    expect_equal(actual=status, expected=1)
    coverage: dict[str, JsonValue] = _payload(
        output=output,
        name="coverage_raw_py.json",
    )
    files: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=coverage["files"],
    )
    expect_in(member="app/unreached.py", container=files)
    summary: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=cast(typ="dict[str, JsonValue]", val=files["app/unreached.py"])[
            "summary"
        ],
    )
    expect_equal(actual=summary["percent_covered"], expected=0.0)
    graph: dict[str, JsonValue] = _payload(
        output=output,
        name="import_graph.json",
    )
    expect_false(
        condition="app/unreached.py"
        in cast(typ="list[JsonValue]", val=graph["omitted_sources"]),
    )
    meaningful: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=graph["meaningful"],
    )
    rows: list[JsonValue] = cast(typ="list[JsonValue]", val=meaningful["rows"])
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("target") == "app/unreached.py"
            and item.get("status") == "actionable"
            for item in rows
        ),
    )
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    findings: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["findings"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-meaningful"
            for item in findings
        ),
    )
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=result["gate"])["status"],
        expected="FAIL",
    )
    scope: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=result["scope"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("target") == "app/unreached.py"
            and item.get("actionable") is True
            for item in cast(typ="list[JsonValue]", val=scope["skipped"])
        ),
    )
    extension: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=result["extension"],
    )
    coverage_extension: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=extension["coverage"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("gate") == "Untested meaningful sources"
            and item.get("status") == "FAIL"
            for item in cast(
                typ="list[JsonValue]",
                val=coverage_extension["gates"],
            )
        ),
    )


def test_include_unreached_counts_filtered_sources_without_findings(
    tmp_path: Path,
) -> None:
    """Count every source at zero while Meaningful findings stay selective.

    Args:
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / "include"
    output: Path = tmp_path / "out-include"
    _project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--minimum",
            "0",
            "--per-file-minimum",
            "0",
            "--include-unreached",
            "--meaningful-minimum-level",
            "TEST-3",
        ),
    )
    expect_equal(actual=status, expected=0)
    coverage: dict[str, JsonValue] = _payload(
        output=output,
        name="coverage_raw_py.json",
    )
    files: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=coverage["files"],
    )
    expect_in(member="app/unreached.py", container=files)
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    expect_false(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-meaningful"
            for item in cast(typ="list[JsonValue]", val=result["findings"])
        ),
    )


@pytest.mark.parametrize("mode", ["classify", "off"])
def test_non_enforcing_modes_preserve_previous_omission(
    mode: str,
    tmp_path: Path,
) -> None:
    """Preserve omission when classification does not enforce results.

    Args:
        mode: Mode.
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / mode
    output: Path = tmp_path / f"out-{mode}"
    _project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--meaningful",
            mode,
        ),
    )
    expect_equal(actual=status, expected=0)
    coverage: dict[str, JsonValue] = _payload(
        output=output,
        name="coverage_raw_py.json",
    )
    files: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=coverage["files"],
    )
    expect_false(condition="app/unreached.py" in files)
    artifact: dict[str, JsonValue] = _payload(
        output=output,
        name="meaningful.json",
    )
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=artifact["settings"])[
            "mode"
        ],
        expected=mode,
    )
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    findings: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["findings"],
    )
    expect_false(
        condition=any(
            isinstance(item, dict)
            and isinstance(rule := item.get("rule"), str)
            and rule.startswith("coverage-meaningful")
            for item in findings
        ),
    )


def test_shortfall_rows_carry_origin_and_reason(tmp_path: Path) -> None:
    """Tag rows produced for sub-gate sources with the shortfall origin.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = tmp_path / "partial.py"
    source.write_text(data="def value():\n    return 1\n", encoding="utf-8")
    result: MeaningfulResult = analyze_unreached(
        root=tmp_path,
        paths=(source,),
        config=MeaningfulConfig(),
        origin="shortfall",
    )
    row: dict[str, JsonValue] = result.rows[0]
    expect_equal(actual=row["origin"], expected="shortfall")
    expect_equal(
        actual=row["reason"],
        expected="measured coverage is below the per-file minimum",
    )


def test_merge_results_combines_rows_and_counts() -> None:
    """Merge two classification passes with rebuilt artifact counts."""
    first: MeaningfulResult = MeaningfulResult(
        rows=(
            {
                "target": "unreached.py",
                "origin": "unreached",
                "status": "actionable",
                "actionable": True,
                "analysis_error": False,
                "level": "TEST-2",
            },
        ),
        artifact={
            "selected_paths": ["unreached.py"],
            "rows": [],
            "findings": [{"path": "unreached.py"}],
            "failures": [],
            "progress": [{"stage": "decision"}],
            "counts": {},
        },
    )
    second: MeaningfulResult = MeaningfulResult(
        rows=(
            {
                "target": "partial.py",
                "origin": "shortfall",
                "status": "filtered",
                "actionable": False,
                "analysis_error": False,
                "level": "TEST-1",
            },
        ),
        artifact={
            "selected_paths": ["partial.py"],
            "rows": [],
            "findings": [{"path": "partial.py"}],
            "failures": [],
            "progress": [{"stage": "decision"}],
            "counts": {},
        },
    )
    merged: MeaningfulResult = merge_results(first=first, second=second)
    expect_equal(actual=len(merged.rows), expected=2)
    expect_equal(actual=merged.actionable, expected=("unreached.py",))
    expect_equal(actual=merged.excused, expected=("partial.py",))
    counts: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=merged.artifact["counts"],
    )
    expect_equal(actual=counts["actionable"], expected=1)
    expect_equal(actual=counts["filtered"], expected=1)
    expect_equal(
        actual=merged.artifact["selected_paths"],
        expected=["unreached.py", "partial.py"],
    )
    expect_equal(
        actual=len(
            cast(typ="list[JsonValue]", val=merged.artifact["findings"]),
        ),
        expected=2,
    )


def _partial_project(*, root: Path) -> None:
    """Create one covered source and one sub-gate measured source.

    Args:
        root: Root.

    """
    package: Path = root / "app"
    tests: Path = root / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (package / "__init__.py").write_text(data="", encoding="utf-8")
    (package / "covered.py").write_text(
        data="def value():\n    return 1\n",
        encoding="utf-8",
    )
    (package / "partial.py").write_text(
        data="def used():\n    return 1\n\n"
        + "".join(
            f"def unused_{index}():\n    return {index}\n\n"
            for index in range(2, 8)
        ),
        encoding="utf-8",
    )
    (tests / "test_app.py").write_text(
        data=(
            dedent(
                text=(
                    "    from app.covered import value\n    from app.parti"
                    "al import used\n    \n    def test_value():\n        "
                    "assert value() == 1\n    \n    def test_used():\n    "
                    "    assert used() == 1\n    "
                ),
            )
        ),
        encoding="utf-8",
    )


def test_shortfall_excused_below_minimum_level(tmp_path: Path) -> None:
    """Exclude a sub-gate file Meaningful rates below the minimum level.

    Args:
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / "project"
    output: Path = tmp_path / "excused"
    _partial_project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--per-file-minimum",
            "80",
            "--meaningful-minimum-level",
            "TEST-3",
        ),
    )
    expect_equal(actual=status, expected=0)
    coverage: dict[str, JsonValue] = _payload(
        output=output,
        name="coverage_raw_py.json",
    )
    files: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=coverage["files"],
    )
    expect_in(member="app/covered.py", container=files)
    expect_false(condition="app/partial.py" in files)
    graph: dict[str, JsonValue] = _payload(
        output=output,
        name="import_graph.json",
    )
    expect_in(
        member="app/partial.py",
        container=cast(typ="list[JsonValue]", val=graph["excused_sources"]),
    )
    expect_in(
        member="app/partial.py",
        container=cast(typ="list[JsonValue]", val=graph["omitted_sources"]),
    )
    meaningful: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=graph["meaningful"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("target") == "app/partial.py"
            and item.get("origin") == "shortfall"
            and item.get("status") == "filtered"
            for item in cast(typ="list[JsonValue]", val=meaningful["rows"])
        ),
    )
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    findings: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["findings"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-shortfall-excused"
            and item.get("severity") == "info"
            and item.get("path") == "app/partial.py"
            for item in findings
        ),
    )
    expect_false(
        condition=any(
            isinstance(item, dict) and item.get("rule") == "coverage-per-file"
            for item in findings
        ),
    )


def test_shortfall_actionable_keeps_per_file_finding(tmp_path: Path) -> None:
    """Keep enforcing the per-file gate on meaningful sub-gate files.

    Args:
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / "project"
    output: Path = tmp_path / "enforced"
    _partial_project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--per-file-minimum",
            "80",
            "--meaningful-minimum-level",
            "TEST-0",
        ),
    )
    expect_equal(actual=status, expected=1)
    coverage: dict[str, JsonValue] = _payload(
        output=output,
        name="coverage_raw_py.json",
    )
    expect_in(
        member="app/partial.py",
        container=cast(typ="dict[str, JsonValue]", val=coverage["files"]),
    )
    result: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
    )
    findings: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["findings"],
    )
    expect_true(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-per-file"
            and item.get("path") == "app/partial.py"
            for item in findings
        ),
    )
    expect_false(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-shortfall-excused"
            for item in findings
        ),
    )
    expect_false(
        condition=any(
            isinstance(item, dict)
            and item.get("rule") == "coverage-meaningful"
            for item in findings
        ),
    )


@pytest.mark.parametrize("mode", ["classify", "off"])
def test_shortfall_gate_only_excused_when_meaningful_runs(
    mode: str,
    tmp_path: Path,
) -> None:
    """Excuse sub-gate files in classify mode but not when Meaningful is off.

    Args:
        mode: Mode.
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / mode
    output: Path = tmp_path / f"out-{mode}"
    _partial_project(root=project)
    status: int = main(
        arguments=(
            str(object=project),
            "-o",
            str(object=output),
            "--source-root",
            "app",
            "--no-js-coverage",
            "--fail-under",
            "0",
            "--per-file-minimum",
            "80",
            "--meaningful",
            mode,
            "--meaningful-minimum-level",
            "TEST-3",
        ),
    )
    expect_equal(actual=status, expected=0 if mode == "classify" else 1)
