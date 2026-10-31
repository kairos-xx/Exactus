# Copyright (c) 2026
"""Build the normalized root report of the ``coverage-tests`` tool.

The root ``COVERAGE_TESTS/result.json`` unifies both halves of one run.
Its ``gate`` is composed of two part gates, ``gate.parts.tests`` and
``gate.parts.coverage`` (each ``{status, reason}``), and its global
status is ``PASS`` only when both parts pass:

- tests fail when any pytest or ``node:test`` test failed or errored, or
  when a test run itself failed (a non-zero exit with no failed test);
- coverage fails when the total minimum (``--fail-under``), the per-file
  minimum, the average per-file minimum or the evidence check is unmet.

``findings`` holds one blocking error per failed or errored test (path
and line of the failing assertion or raise, reason, excerpt) and one per
unmet coverage gate (per-file shortfalls carry the uncovered ranges and an
excerpt of the first one). ``extension`` holds the tests and coverage
summaries and links to the ``TESTS`` and ``COVERAGE`` sub-reports. The
legacy keys (``coverage``, ``import_graph``, ``javascript``,
``test_execution``, ``gates``, ``passed``, ``root``) are kept.
"""

from __future__ import annotations

from ast import literal_eval
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Final, Self, cast, final

from exactus.packages.steps import trace
from exactus.tools.common.snippets import finding_excerpt
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class ReportTables:
    """Constants of the normalized root report.

    Attributes:
        title: Title.
        assertion_values: Assertion values.
        analyzer: Analyzer.
        test_rules: Test rules.
        tests_source: Tests source.
        coverage_source: Coverage source.
        python_tests: Python tests.
        javascript_tests: Javascript tests.
        outcomes: Outcomes.
        levels: Levels.

    """

    title: Final[str] = "Coverage"
    assertion_values: Final[int] = 2
    analyzer: Final[str] = "coverage_tests"
    test_rules: Final[dict[str, str]] = {
        "FAILED": "test-failure",
        "ERROR": "test-error",
        "SKIPPED": "test-skipped",
    }
    tests_source: Final[str] = "Tests"
    coverage_source: Final[str] = "Coverage"
    python_tests: Final[str] = "**/test_*.py"
    javascript_tests: Final[tuple[str, ...]] = (
        "**/*.test.{js,mjs,cjs}",
        "**/*.spec.{js,mjs,cjs}",
        "**/*_test.{js,mjs,cjs}",
    )
    outcomes: Final[dict[str, str]] = {
        "PASSED": "passed",
        "FAILED": "failed",
        "ERROR": "errors",
        "SKIPPED": "skipped",
        "XFAIL": "xfailed",
        "XPASS": "xpassed",
    }
    levels: Final[tuple[str, ...]] = ("error", "warning", "info")


@dataclass(frozen=True, slots=True)
class CoverageGates:
    """Coverage gates of one run.

    Attributes:
        fail_under: Fail under.
        per_file_minimum: Per file minimum.
        average_minimum: Average minimum.
        validation: Validation.

    """

    fail_under: float | None
    per_file_minimum: float | None
    average_minimum: float | None = None
    validation: Mapping[str, JsonValue] | None = None


@dataclass(frozen=True, slots=True)
class ReportInputs:
    """Everything the root report is built from.

    Attributes:
        root: Root.
        context: Context.
        coverage: Coverage.
        graph: Graph.
        javascript: Javascript.
        execution: Execution.
        groups: Groups.
        gates: Gates.
        excluded_dirs: Excluded dirs.
        includes: Includes.
        excludes: Excludes.

    """

    root: Path
    context: int
    coverage: Mapping[str, JsonValue]
    graph: Mapping[str, JsonValue]
    javascript: Mapping[str, JsonValue] | None
    execution: Mapping[str, JsonValue] | None
    groups: tuple[Mapping[str, JsonValue], ...]
    gates: CoverageGates
    excluded_dirs: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()


@final
class Values:
    """Typed reads of loosely shaped JSON values."""

    @staticmethod
    def items(*, value: JsonValue | None) -> list[JsonValue]:
        """Return a JSON list, or an empty one.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return value if isinstance(value, list) else []

    @staticmethod
    def mapping(*, value: JsonValue | None) -> dict[str, JsonValue]:
        """Return a JSON object, or an empty one.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return value if isinstance(value, dict) else {}

    @staticmethod
    def number(*, value: JsonValue | None) -> float | None:
        """Return a JSON number as a float.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)

    @staticmethod
    def count(*, value: JsonValue | None) -> int:
        """Return a JSON integer count.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        if isinstance(value, bool) or not isinstance(value, int):
            return 0
        return value

    @staticmethod
    def text(*, value: JsonValue | None) -> str:
        """Return a JSON string.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return value if isinstance(value, str) else ""


@final
class Ranges:
    """Collapse line numbers into ranges.

    Attributes:
        span_size: Minimum contiguous run that earns a ``first-last`` span.

    """

    span_size: Final[int] = 3

    @classmethod
    def text(cls, *, ranges: Sequence[tuple[int, int]]) -> str:
        """Render ranges as ``3-5, 9, 12, 13``.

        A span only earns a dash when it covers at least three lines —
        ``5-6`` reads no better than ``5, 6``, so two-line runs stay
        comma-separated.

        Args:
            ranges: Ranges.

        Returns:
            The resulting value.

        """
        return ", ".join(
            str(object=first)
            if first == last
            else (
                f"{first}-{last}"
                if last - first + 1 >= cls.span_size
                else f"{first}, {last}"
            )
            for first, last in ranges
        )

    @staticmethod
    def collapse(*, lines: Sequence[int]) -> list[tuple[int, int]]:
        """Group sorted line numbers into contiguous ranges.

        Args:
            lines: Lines.

        Returns:
            The resulting value.

        """
        ranges: list[tuple[int, int]] = []
        number: int
        for number in sorted(set(lines)):
            if ranges and number == ranges[-1][1] + 1:
                ranges[-1] = (ranges[-1][0], number)
            else:
                ranges.append((number, number))
        return ranges


@final
class CoverageTestsReport:
    """Compose the normalized blocks of the root report."""

    @classmethod
    def test_findings(
        cls: type[Self],
        *,
        inputs: ReportInputs,
    ) -> list[dict[str, JsonValue]]:
        """Return details for failed, errored and skipped tests.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        execution: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.execution),
        )
        found: list[dict[str, JsonValue]] = []
        raw: JsonValue
        for raw in (
            *Values.items(value=execution.get("failed_tests")),
            *Values.items(value=execution.get("skipped_tests")),
        ):
            entry: dict[str, JsonValue] = Values.mapping(value=raw)
            kind: str = Values.text(value=entry.get("kind")) or "FAILED"
            node: str = Values.text(value=entry.get("test"))
            detail: str = Values.text(value=entry.get("detail")).strip()
            reason: str = (
                Values.text(value=entry.get("reason")).strip()
                or (detail.splitlines() or [""])[0]
                or ("Test failed" if kind == "FAILED" else "Test errored")
            )
            path: str = Values.text(value=entry.get("path"))
            line: JsonValue = entry.get("line")
            found.append(
                {
                    "id": cls.stable_id(prefix="TEST", parts=(kind, node)),
                    "title": node,
                    "severity": "info" if kind == "SKIPPED" else "error",
                    "rule": ReportTables.test_rules.get(kind, "test-failure"),
                    "path": path or node.partition("::")[0] or None,
                    "line": line if path and isinstance(line, int) else None,
                    "message": reason,
                    "assertion_diff": cls.assertion_diff(message=reason),
                    "blocking": kind != "SKIPPED",
                    "source": "Skipped tests"
                    if kind == "SKIPPED"
                    else ReportTables.tests_source,
                    "test": node,
                    "kind": kind,
                    "shard": entry.get("shard"),
                    "log": entry.get("log"),
                    "language": "python",
                },
            )
        javascript: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.javascript),
        )
        for raw in Values.items(value=javascript.get("failures")):
            failure: dict[str, JsonValue] = Values.mapping(value=raw)
            name: str = Values.text(value=failure.get("name"))
            js_path: str = Values.text(value=failure.get("path"))
            js_line: JsonValue = failure.get("line")
            found.append(
                {
                    "id": cls.stable_id(prefix="JSTEST", parts=(name,)),
                    "title": name,
                    "severity": "error",
                    "rule": "test-failure",
                    "path": js_path or None,
                    "line": js_line
                    if js_path and isinstance(js_line, int)
                    else None,
                    "message": Values.text(value=failure.get("reason"))
                    or "Test failed",
                    "blocking": True,
                    "source": ReportTables.tests_source,
                    "test": name,
                    "kind": "FAILED",
                    "log": "ARTIFACTS/TESTS/js-tests.json",
                    "language": "javascript",
                },
            )
        return found

    @classmethod
    def coverage_findings(
        cls: type[Self],
        *,
        inputs: ReportInputs,
    ) -> list[dict[str, JsonValue]]:
        """Return one finding per unmet coverage gate.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        gates: CoverageGates = inputs.gates
        totals: dict[str, JsonValue] = Values.mapping(
            value=inputs.coverage.get("totals"),
        )
        total: float | None = Values.number(
            value=totals.get("percent_covered"),
        )
        files: list[tuple[str, float, list[int]]] = cls.file_percents(
            coverage=inputs.coverage,
        )
        javascript: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.javascript),
        )
        js_total: float | None
        found: list[dict[str, JsonValue]] = []
        js_total = Values.number(value=javascript.get("percent_covered"))
        if (
            gates.fail_under is not None
            and js_total is not None
            and js_total < gates.fail_under
        ):
            found.append(
                cls.violation(
                    rule="coverage-javascript-total",
                    title="JavaScript coverage is below the minimum",
                    message=(
                        f"Total JavaScript coverage is "
                        f"{cls.percent(value=js_total)}; the minimum is "
                        f"{cls.percent(value=gates.fail_under)}."
                    ),
                    measured=js_total,
                    required=gates.fail_under,
                ),
            )
        if (
            gates.fail_under is not None
            and total is not None
            and total < gates.fail_under
        ):
            found.append(
                cls.violation(
                    rule="coverage-total",
                    title="Total coverage is below the minimum",
                    message=(
                        f"Total Python coverage is "
                        f"{cls.percent(value=total)}; the minimum is "
                        f"{cls.percent(value=gates.fail_under)}."
                    ),
                    measured=total,
                    required=gates.fail_under,
                ),
            )
        if gates.average_minimum is not None:
            average: float | None = (
                sum(percent for _, percent, _ in files) / len(files)
                if files
                else None
            )
            if average is None or average < gates.average_minimum:
                found.append(
                    cls.violation(
                        rule="coverage-average",
                        title="Average per-file coverage is below the minimum",
                        message=(
                            "No Python source file was measured."
                            if average is None
                            else f"Average per-file coverage is "
                            f"{cls.percent(value=average)}; the minimum is "
                            f"{cls.percent(value=gates.average_minimum)}."
                        ),
                        measured=average,
                        required=gates.average_minimum,
                    ),
                )
        verdict: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=gates.validation),
        )
        if verdict and verdict.get("status") != "PASS":
            found.append(
                cls.violation(
                    rule="coverage-evidence",
                    title="Coverage evidence check failed",
                    message=(
                        Values.text(value=verdict.get("reason"))
                        or "the coverage evidence is invalid"
                    ).capitalize()
                    + ".",
                    measured=None,
                    required=None,
                ),
            )
        found.extend(cls.meaningful_findings(inputs=inputs))
        found.extend(
            cls.per_file_findings(
                inputs=inputs,
                files=[
                    *files,
                    *cls.javascript_percents(javascript=javascript),
                ],
            ),
        )
        return found

    @classmethod
    def meaningful_findings(
        cls: type[Self],
        *,
        inputs: ReportInputs,
    ) -> list[dict[str, JsonValue]]:
        """Return blocking findings required by Meaningful enforcement.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        manifest: dict[str, JsonValue] = Values.mapping(
            value=inputs.graph.get("meaningful"),
        )
        enforce: bool = manifest.get("mode") == "require"
        required: str = Values.text(value=manifest.get("minimum_level"))
        found: list[dict[str, JsonValue]] = []
        for raw in Values.items(value=manifest.get("rows")):
            row: dict[str, JsonValue] = Values.mapping(value=raw)
            actionable: bool = row.get("actionable") is True
            analysis_error: bool = row.get("analysis_error") is True
            origin: str = Values.text(value=row.get("origin")) or "unreached"
            path: str = Values.text(value=row.get("target"))
            level: str = Values.text(value=row.get("level"))
            category: str = Values.text(value=row.get("category"))
            evidence: list[JsonValue] = Values.items(value=row.get("evidence"))
            first_evidence: dict[str, JsonValue] = Values.mapping(
                value=evidence[0] if evidence else None,
            )
            if origin == "shortfall" and not actionable and not analysis_error:
                detail: str = (
                    f"{level} ({category})"
                    if level and category
                    else level or "unclassified"
                )
                found.append(
                    {
                        "id": cls.stable_id(
                            prefix="COV",
                            parts=("coverage-shortfall-excused", path),
                        ),
                        "title": (
                            f"{path} is excused from the per-file minimum"
                        ),
                        "severity": "info",
                        "rule": "coverage-shortfall-excused",
                        "path": path,
                        "line": first_evidence.get("line") or 1,
                        "message": (
                            f"{detail} does not meet the required "
                            f"{required} level; the file is excused "
                            "from coverage gates and excluded from "
                            "coverage measurement."
                        ),
                        "blocking": False,
                        "source": ReportTables.coverage_source,
                        "level": level or None,
                        "category": category or None,
                        "scores": row.get("scores"),
                        "reasons": row.get("reasons"),
                        "required_level": required,
                    },
                )
                continue
            if not actionable and not analysis_error:
                continue
            if not enforce:
                continue
            if origin == "shortfall" and actionable:
                continue
            reasons: list[str] = [
                Values.text(value=item)
                for item in Values.items(value=row.get("reasons"))
                if Values.text(value=item)
            ]
            failure: dict[str, JsonValue] = Values.mapping(
                value=row.get("failure"),
            )
            rule: str = (
                "coverage-meaningful-analysis"
                if analysis_error
                else "coverage-meaningful"
            )
            if analysis_error:
                error_type: str = Values.text(value=failure.get("error_type"))
                error_message: str = Values.text(value=failure.get("message"))
                title: str = f"{path} could not be classified"
                message: str = f"{error_type}: {error_message}".strip(": ")
            else:
                title = f"{path} is untested and meaningful"
                detail = f"{level} ({category})" if category else level
                message = (
                    f"{detail} meets the required {required} level; "
                    "add a test file. This important file is counted at 0% "
                    "coverage."
                )
                if reasons:
                    message += f" {reasons[0]}"
            found.append(
                {
                    "id": cls.stable_id(prefix="COV", parts=(rule, path)),
                    "title": title,
                    "severity": "error",
                    "rule": rule,
                    "path": path,
                    "line": first_evidence.get("line") or 1,
                    "message": message,
                    "blocking": True,
                    "source": ReportTables.coverage_source,
                    "level": level or None,
                    "category": category or None,
                    "scores": row.get("scores"),
                    "reasons": row.get("reasons"),
                    "required_level": required,
                    "failure": row.get("failure"),
                },
            )
        return found

    @classmethod
    def violation(
        cls: type[Self],
        *,
        rule: str,
        title: str,
        message: str,
        measured: float | None,
        required: float | None,
    ) -> dict[str, JsonValue]:
        """Return one project-wide coverage finding.

        Args:
            rule: Rule.
            title: Title.
            message: Message.
            measured: Measured.
            required: Required.

        Returns:
            The resulting value.

        """
        return {
            "id": cls.stable_id(prefix="COV", parts=(rule,)),
            "title": title,
            "severity": "error",
            "rule": rule,
            "path": None,
            "line": None,
            "message": message,
            "blocking": True,
            "source": ReportTables.coverage_source,
            "percent": None
            if measured is None
            else round(number=measured, ndigits=2),
            "required": required,
        }

    @classmethod
    def per_file_findings(
        cls: type[Self],
        *,
        inputs: ReportInputs,
        files: Sequence[tuple[str, float, list[int]]],
    ) -> list[dict[str, JsonValue]]:
        """Return one finding per file below the per-file minimum.

        Args:
            inputs: Inputs.
            files: Files.

        Returns:
            The resulting value.

        """
        minimum: float | None = inputs.gates.per_file_minimum
        if minimum is None:
            return []
        found: list[dict[str, JsonValue]] = []
        path: str
        percent: float
        missing: list[int]
        for path, percent, missing in sorted(files, key=cls.percent_key):
            if percent >= minimum:
                continue
            ranges: list[tuple[int, int]] = Ranges.collapse(lines=missing)
            listed: str = Ranges.text(ranges=ranges)
            found.append(
                {
                    "id": cls.stable_id(
                        prefix="COV",
                        parts=("coverage-per-file", path),
                    ),
                    "title": f"{path} is below the per-file minimum",
                    "severity": "error",
                    "rule": "coverage-per-file",
                    "path": path,
                    "line": ranges[0][0] if ranges else None,
                    "message": (
                        f"{path} has {cls.percent(value=percent)} coverage; "
                        f"every file needs {cls.percent(value=minimum)}."
                        + (f" Uncovered lines: {listed}." if listed else "")
                    ),
                    "blocking": True,
                    "source": ReportTables.coverage_source,
                    "percent": round(number=percent, ndigits=2),
                    "required": minimum,
                    "uncovered": listed,
                    "uncovered_ranges": [
                        [first, last] for first, last in ranges
                    ],
                },
            )
        return found

    @classmethod
    def tests_part(
        cls: type[Self],
        *,
        inputs: ReportInputs,
    ) -> dict[str, JsonValue]:
        """Return the tests part gate.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        counts: dict[str, int] = cls.outcomes(inputs=inputs)
        execution: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.execution),
        )
        javascript: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.javascript),
        )
        js_failed: int = len(Values.items(value=javascript.get("failures")))
        python: list[str] = [
            f"{count} {label}"
            for count, label in (
                (counts["failed"], "failed"),
                (counts["errors"], "errored"),
            )
            if count
        ]
        problems: list[str] = []
        if python:
            noun: str = "test" if counts["total"] == 1 else "tests"
            problems.append(f"{', '.join(python)} of {counts['total']} {noun}")
        if js_failed:
            problems.append(
                f"{js_failed} JavaScript "
                f"{'test' if js_failed == 1 else 'tests'} failed",
            )
        status: int = Values.count(value=execution.get("status"))
        js_status: int = Values.count(value=javascript.get("status"))
        if problems:
            return {
                "status": "FAIL",
                "reason": "; ".join(problems),
                "position": 1,
            }
        if status:
            return {
                "status": "FAIL",
                "reason": f"Pytest exited with status {status}",
                "position": 1,
            }
        if js_status:
            detail: str = Values.text(value=javascript.get("detail"))
            return {
                "status": "FAIL",
                "reason": detail
                or f"The JavaScript test run exited with status {js_status}",
                "position": 1,
            }
        if not counts["total"] and not javascript:
            return {
                "status": "PASS",
                "reason": "No tests were found",
                "position": 1,
            }
        passed: str = (
            f"{counts['passed']} of {counts['total']} "
            f"{'test' if counts['total'] == 1 else 'tests'} passed"
            if counts["total"]
            else "No Python tests ran"
        )
        extras: list[str] = [
            f"{counts[key]} {key}"
            for key in ("skipped", "xfailed", "xpassed")
            if counts[key]
        ]
        js_files: int = len(Values.items(value=javascript.get("tests")))
        if js_files:
            extras.append(
                f"{js_files} JavaScript test "
                f"{'file' if js_files == 1 else 'files'} passed",
            )
        return {
            "status": "PASS",
            "reason": "; ".join((passed, *extras)),
            "position": 1,
        }

    @classmethod
    def coverage_part(
        cls: type[Self],
        *,
        inputs: ReportInputs,
        findings: Sequence[Mapping[str, JsonValue]],
    ) -> dict[str, JsonValue]:
        """Return the coverage part gate.

        Args:
            inputs: Inputs.
            findings: Findings.

        Returns:
            The resulting value.

        """
        gates: CoverageGates = inputs.gates
        total: float | None = Values.number(
            value=Values.mapping(value=inputs.coverage.get("totals")).get(
                "percent_covered",
            ),
        )
        rules: Counter[str] = Counter(
            Values.text(value=item.get("rule")) for item in findings
        )
        problems: list[str] = []
        if rules["coverage-javascript-total"]:
            problems.append("JavaScript coverage is below the total minimum")
        if rules["coverage-total"]:
            problems.append(
                f"total {cls.percent(value=total)} is below "
                f"{cls.percent(value=gates.fail_under)}",
            )
        if rules["coverage-per-file"]:
            count: int = rules["coverage-per-file"]
            problems.append(
                f"{count} {'file' if count == 1 else 'files'} below the "
                f"{cls.percent(value=gates.per_file_minimum)} per-file "
                "minimum",
            )
        meaningful_count: int = rules["coverage-meaningful"]
        analysis_count: int = rules["coverage-meaningful-analysis"]
        if meaningful_count or analysis_count:
            problems.append(
                "Meaningful requires "
                f"{meaningful_count} untested sources and reports "
                f"{analysis_count} analysis errors",
            )
        item: Mapping[str, JsonValue]
        for item in findings:
            if item.get("rule") == "coverage-average":
                measured: float | None = Values.number(
                    value=item.get("percent"),
                )
                problems.append(
                    "average per-file coverage "
                    + (
                        "has no measured file"
                        if measured is None
                        else f"{cls.percent(value=measured)} is below "
                        f"{cls.percent(value=gates.average_minimum)}"
                    ),
                )
            elif item.get("rule") == "coverage-evidence":
                problems.append(
                    "evidence check failed: "
                    + Values.text(value=item.get("message")).rstrip("."),
                )
        if problems:
            reason: str = ", ".join(problems)
            return {
                "status": "FAIL",
                "reason": reason[:1].upper() + reason[1:],
                "position": 2,
            }
        parts: list[str] = [
            f"Total {cls.percent(value=total)}"
            + (
                f" meets the {cls.percent(value=gates.fail_under)} minimum"
                if gates.fail_under is not None
                else " (no minimum set)"
            ),
        ]
        if gates.per_file_minimum is not None:
            parts.append(
                "every file meets "
                f"{cls.percent(value=gates.per_file_minimum)}",
            )
        return {"status": "PASS", "reason": "; ".join(parts), "position": 2}

    @classmethod
    def coverage_block(
        cls: type[Self],
        *,
        inputs: ReportInputs,
        part: Mapping[str, JsonValue],
        findings: Sequence[Mapping[str, JsonValue]],
    ) -> dict[str, JsonValue]:
        """Return the coverage summary of ``extension``.

        Args:
            inputs: Inputs.
            part: Part.
            findings: Findings.

        Returns:
            The resulting value.

        """
        gates: CoverageGates = inputs.gates
        totals: dict[str, JsonValue] = Values.mapping(
            value=inputs.coverage.get("totals"),
        )
        total: float | None = Values.number(
            value=totals.get("percent_covered"),
        )
        files: list[tuple[str, float, list[int]]] = cls.file_percents(
            coverage=inputs.coverage,
        )
        languages: list[JsonValue] = [
            {
                "language": "Python",
                "basis": "Lines + branches"
                if Values.count(value=totals.get("num_branches"))
                else "Lines",
                "percent": None
                if total is None
                else round(number=total, ndigits=2),
                "lines": Values.count(value=totals.get("num_statements")),
                "covered": Values.count(value=totals.get("covered_lines")),
                "missing": Values.count(value=totals.get("missing_lines")),
                "files": len(files),
            },
        ]
        javascript: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.javascript),
        )
        if javascript:
            executable: int = Values.count(
                value=javascript.get("executable_lines"),
            )
            covered: int = Values.count(value=javascript.get("covered_lines"))
            languages.append(
                {
                    "language": "JavaScript",
                    "basis": "Lines",
                    "percent": Values.number(
                        value=javascript.get("percent_covered"),
                    ),
                    "lines": executable,
                    "covered": covered,
                    "missing": executable - covered,
                    "files": Values.count(
                        value=javascript.get("files_measured"),
                    ),
                },
            )
        rules: Counter[str] = Counter(
            Values.text(value=item.get("rule")) for item in findings
        )
        rows: list[JsonValue] = []
        if gates.fail_under is not None:
            rows.append(
                {
                    "gate": "Total coverage",
                    "option": "--fail-under",
                    "required": cls.percent(value=gates.fail_under),
                    "measured": cls.percent(value=total),
                    "status": "FAIL" if rules["coverage-total"] else "PASS",
                },
            )
        if javascript and gates.fail_under is not None:
            rows.append(
                {
                    "gate": "JavaScript total coverage",
                    "option": "--fail-under",
                    "required": cls.percent(value=gates.fail_under),
                    "measured": cls.percent(
                        value=Values.number(
                            value=javascript.get("percent_covered"),
                        ),
                    ),
                    "status": "FAIL"
                    if rules["coverage-javascript-total"]
                    else "PASS",
                },
            )
        if gates.per_file_minimum is not None:
            below: int = rules["coverage-per-file"]
            file_count: int = len(files) + len(
                cls.javascript_percents(javascript=javascript),
            )
            rows.append(
                {
                    "gate": "Per-file minimum",
                    "option": "--per-file-minimum",
                    "required": cls.percent(value=gates.per_file_minimum),
                    "measured": f"{below} of {file_count} files below",
                    "status": "FAIL" if below else "PASS",
                },
            )
        if gates.average_minimum is not None:
            average: float | None = (
                sum(percent for _, percent, _ in files) / len(files)
                if files
                else None
            )
            rows.append(
                {
                    "gate": "Average per-file coverage",
                    "option": "--average-minimum",
                    "required": cls.percent(value=gates.average_minimum),
                    "measured": cls.percent(value=average),
                    "status": "FAIL" if rules["coverage-average"] else "PASS",
                },
            )
        meaningful: dict[str, JsonValue] = Values.mapping(
            value=inputs.graph.get("meaningful"),
        )
        if meaningful.get("mode") == "require":
            actionable: int = rules["coverage-meaningful"]
            analysis_errors: int = rules["coverage-meaningful-analysis"]
            rows.append(
                {
                    "gate": "Untested meaningful sources",
                    "option": "--meaningful-minimum-level",
                    "required": ">= "
                    + Values.text(value=meaningful.get("minimum_level")),
                    "measured": (
                        f"{actionable} actionable, "
                        f"{analysis_errors} analysis errors"
                    ),
                    "status": "FAIL"
                    if actionable or analysis_errors
                    else "PASS",
                },
            )
        verdict: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=gates.validation),
        )
        if verdict:
            rows.append(
                {
                    "gate": "Evidence check",
                    "option": "--minimum",
                    "required": "complete, unchanged evidence",
                    "measured": "valid"
                    if verdict.get("status") == "PASS"
                    else Values.text(value=verdict.get("reason")) or "invalid",
                    "status": "FAIL" if rules["coverage-evidence"] else "PASS",
                },
            )
        unreached: int = len(
            Values.items(value=inputs.graph.get("unreached_sources")),
        )
        return {
            "status": part.get("status"),
            "reason": part.get("reason"),
            "languages": languages,
            "gates": rows,
            "files_below_minimum": [
                {
                    "path": item.get("path"),
                    "percent": item.get("percent"),
                    "required": item.get("required"),
                    "uncovered": item.get("uncovered"),
                    "finding": item.get("id"),
                }
                for item in findings
                if item.get("rule") == "coverage-per-file"
            ],
            "unreached_sources": unreached,
            "report": "COVERAGE",
        }

    @classmethod
    def tests_block(
        cls: type[Self],
        *,
        inputs: ReportInputs,
        part: Mapping[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Return the tests summary of ``extension``.

        Args:
            inputs: Inputs.
            part: Part.

        Returns:
            The resulting value.

        """
        counts: dict[str, int] = cls.outcomes(inputs=inputs)
        execution: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.execution),
        )
        javascript: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.javascript),
        )
        return {
            "status": part.get("status"),
            "reason": part.get("reason"),
            **counts,
            "duration_seconds": Values.number(
                value=execution.get("duration_seconds"),
            ),
            "test_files": len(Values.items(value=inputs.graph.get("tests"))),
            "shards": len(Values.items(value=execution.get("shards"))),
            "javascript_test_files": len(
                Values.items(value=javascript.get("tests")),
            ),
            "javascript_failed": len(
                Values.items(value=javascript.get("failures")),
            ),
            "groups": [dict(row) for row in inputs.groups],
            "report": "TESTS",
        }

    @classmethod
    def report_data(
        cls: type[Self],
        *,
        inputs: ReportInputs,
    ) -> dict[str, JsonValue]:
        """Return the normalized blocks of the root report.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        coverage_findings: list[dict[str, JsonValue]] = cls.coverage_findings(
            inputs=inputs,
        )
        tests_findings: list[dict[str, JsonValue]] = [
            item
            for item in cls.test_findings(inputs=inputs)
            if item.get("blocking")
        ]
        coverage_part: dict[str, JsonValue] = cls.coverage_part(
            inputs=inputs,
            findings=coverage_findings,
        )
        tests_part: dict[str, JsonValue] = cls.tests_part(inputs=inputs)
        gate: dict[str, JsonValue] = cls.gate(
            coverage=coverage_part,
            tests=tests_part,
        )
        findings: list[JsonValue] = [
            finding_excerpt(
                finding=cast(typ="JsonValue", val=item),
                root=inputs.root,
                context=inputs.context,
            )
            for item in (*tests_findings, *coverage_findings)
        ]
        counts: dict[str, int] = cls.outcomes(inputs=inputs)
        targets: int = len(cls.file_percents(coverage=inputs.coverage)) + len(
            cls.javascript_percents(
                javascript=Values.mapping(
                    value=cast(typ="JsonValue", val=inputs.javascript),
                ),
            ),
        )
        total: float | None = Values.number(
            value=Values.mapping(value=inputs.coverage.get("totals")).get(
                "percent_covered",
            ),
        )
        rule_titles: dict[str, str] = {
            "test-failure": "Failed tests",
            "test-error": "Errored tests",
            "coverage-total": "Overall Python coverage",
            "coverage-javascript-total": "Overall JavaScript coverage",
            "coverage-per-file": "Per-file coverage minimum",
            "coverage-average": "Average file coverage",
            "coverage-evidence": "Coverage evidence validation",
            "coverage-meaningful": "Untested meaningful sources",
            "coverage-meaningful-analysis": "Meaningful analysis failures",
            "coverage-shortfall-excused": "Excused sub-gate sources",
        }
        return {
            "summary": {
                "targets_eligible": targets,
                "targets_analyzed": targets,
                "findings_total": len(findings),
                "severity": {
                    level: sum(
                        isinstance(item, dict)
                        and item.get("severity") == level
                        for item in findings
                    )
                    for level in ReportTables.levels
                },
                "coverage_percent": None
                if total is None
                else round(number=total, ndigits=2),
                "coverage_required": inputs.gates.fail_under,
                "tests": {
                    **counts,
                    "files": len(
                        Values.items(value=inputs.graph.get("tests")),
                    ),
                },
            },
            "scope": cls.scope(inputs=inputs),
            "findings": findings,
            "extension": {
                "tests": cls.tests_block(inputs=inputs, part=tests_part),
                "categories": [
                    {
                        "category": rule,
                        "title": title,
                        "count": sum(
                            isinstance(item, dict) and item.get("rule") == rule
                            for item in findings
                        ),
                    }
                    for rule, title in rule_titles.items()
                ],
                "coverage": cls.coverage_block(
                    inputs=inputs,
                    part=coverage_part,
                    findings=coverage_findings,
                ),
                "reports": [
                    {
                        "name": "Tests",
                        "report": "TESTS",
                        "description": "Every test result, failed tests "
                        "with reasons, shards and warnings",
                    },
                    {
                        "name": "Coverage",
                        "report": "COVERAGE",
                        "description": "Coverage per file with uncovered "
                        "lines, the import graph and the JavaScript lane",
                    },
                ],
            },
            "gate": gate,
            "resume": f"{gate['status']}: {gate['reason']}",
        }

    @classmethod
    def write(
        cls: type[Self],
        *,
        inputs: ReportInputs,
        output: Path,
        legacy: Mapping[str, JsonValue],
    ) -> None:
        """Write the root report bundle.

        Args:
            inputs: Inputs.
            output: Output.
            legacy: Legacy.

        """
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output / "result.md",
                json=output / "result.json",
                web=output / "result_web",
            ),
            analyzer=ReportTables.analyzer,
            title=ReportTables.title,
            markdown="",
            data={**legacy, **cls.report_data(inputs=inputs)},
        )
        trace(
            step=(f"report: result bundle written — {output / 'result.md'}"),
            depth=2,
        )

    @staticmethod
    def assertion_diff(*, message: str) -> dict[str, JsonValue] | None:
        """Decode quoted assertion values for readable report code blocks.

        Args:
            message: Message.

        Returns:
            The resulting value.

        """
        prefix: str = "AssertionError: "
        if not message.startswith(prefix):
            return None
        detail: str = message.removeprefix(prefix)
        if detail.startswith("expected "):
            expression: str = detail.removeprefix("expected ").replace(
                ", got ",
                ", ",
                count=1,
            )
        elif " not found in " in detail:
            expression = detail.replace(" not found in ", ", ", count=1)
        else:
            return None
        try:
            parsed: object = literal_eval(node_or_string=f"({expression})")
        except (SyntaxError, ValueError):
            return None
        if isinstance(parsed, tuple):
            values: tuple[object, ...] = cast(
                typ="tuple[object, ...]",
                val=parsed,
            )
            if len(values) == ReportTables.assertion_values:
                expected, actual = values
                if isinstance(expected, str) and isinstance(actual, str):
                    return {"expected": expected, "actual": actual}
        return None

    @staticmethod
    def stable_id(*, prefix: str, parts: Sequence[str]) -> str:
        """Return an identifier that is stable across runs.

        Args:
            prefix: Prefix.
            parts: Parts.

        Returns:
            The resulting value.

        """
        digest: str = sha256(
            data="\0".join(parts).encode(encoding="utf-8"),
        ).hexdigest()
        return f"{prefix}-{digest[:8]}"

    @staticmethod
    def percent(*, value: float | None) -> str:
        """Format a percentage for reasons and messages.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return "N/A" if value is None else f"{value:.1f}%"

    @staticmethod
    def file_percents(
        *,
        coverage: Mapping[str, JsonValue],
    ) -> list[tuple[str, float, list[int]]]:
        """List every measured Python file with its coverage.

        Args:
            coverage: Coverage.

        Returns:
            The resulting value.

        """
        rows: list[tuple[str, float, list[int]]] = []
        path: str
        raw: JsonValue
        for path, raw in sorted(
            Values.mapping(value=coverage.get("files")).items(),
        ):
            entry: dict[str, JsonValue] = Values.mapping(value=raw)
            percent: float | None = Values.number(
                value=Values.mapping(value=entry.get("summary")).get(
                    "percent_covered",
                ),
            )
            missing: list[int] = [
                number
                for number in Values.items(value=entry.get("missing_lines"))
                if isinstance(number, int) and not isinstance(number, bool)
            ]
            rows.append((path, 100.0 if percent is None else percent, missing))
        return rows

    @staticmethod
    def javascript_percents(
        *,
        javascript: Mapping[str, JsonValue],
    ) -> list[tuple[str, float, list[int]]]:
        """List measured JavaScript files with their uncovered source lines.

        Args:
            javascript: Javascript.

        Returns:
            The resulting value.

        """
        entry: dict[str, JsonValue]
        files: list[tuple[str, float, list[int]]] = []
        percent: float | None
        for raw in Values.items(value=javascript.get("files")):
            entry = Values.mapping(value=raw)
            percent = Values.number(value=entry.get("percent_covered"))
            if percent is not None:
                files.append(
                    (
                        Values.text(value=entry.get("path")),
                        percent,
                        [
                            line
                            for line in Values.items(
                                value=entry.get("uncovered_lines"),
                            )
                            if isinstance(line, int)
                        ],
                    ),
                )
        return files

    @staticmethod
    def percent_key(item: tuple[str, float, list[int]]) -> tuple[float, str]:
        """Sort key: lowest coverage first, then path.

        Args:
            item: Item.

        Returns:
            The resulting value.

        """
        return (item[1], item[0])

    @staticmethod
    def outcomes(*, inputs: ReportInputs) -> dict[str, int]:
        """Count pytest outcomes.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        execution: dict[str, JsonValue] = Values.mapping(
            value=cast(typ="JsonValue", val=inputs.execution),
        )
        seen: Counter[str] = Counter(
            Values.text(value=Values.mapping(value=item).get("outcome"))
            for item in Values.items(value=execution.get("tests"))
        )
        counts: dict[str, int] = {
            key: seen[outcome]
            for outcome, key in ReportTables.outcomes.items()
        }
        failed: int = 0
        errors: int = 0
        item: JsonValue
        for item in Values.items(value=execution.get("failed_tests")):
            kind: str = Values.text(
                value=Values.mapping(value=item).get("kind"),
            )
            failed += kind == "FAILED"
            errors += kind == "ERROR"
        counts["failed"] = max(counts["failed"], failed)
        counts["errors"] = max(counts["errors"], errors)
        counts["total"] = sum(seen.values())
        return counts

    @staticmethod
    def gate(
        *,
        coverage: Mapping[str, JsonValue],
        tests: Mapping[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Combine the tests and coverage gates into the report gate.

        The global gate fails when either part fails so that a test
        failure cannot be hidden behind a passing coverage gate and
        vice versa.

        Args:
            coverage: Coverage gate result.
            tests: Tests gate result.

        Returns:
            The resulting value.

        """
        parts: dict[str, JsonValue] = {
            "tests": {**tests, "label": "Tests"},
            "coverage": {**coverage, "label": "Coverage"},
        }
        resolved: list[dict[str, JsonValue]] = [
            part for part in parts.values() if isinstance(part, dict)
        ]
        failed: list[dict[str, JsonValue]] = [
            part for part in resolved if part.get("status") == "FAIL"
        ]
        if failed:
            reasons: list[str] = [
                f"{part.get('label', 'part')}: {part.get('reason', '')}"
                for part in failed
            ]
            return {
                "status": "FAIL",
                "reason": "; ".join(reasons),
                "parts": parts,
            }
        return {
            "status": "PASS",
            "reason": "; ".join(
                str(object=part.get("reason", "")) for part in resolved
            ),
            "parts": parts,
        }

    @staticmethod
    def scope(*, inputs: ReportInputs) -> dict[str, JsonValue]:
        """Return the ``scope`` block.

        Args:
            inputs: Inputs.

        Returns:
            The resulting value.

        """
        meaningful: dict[str, JsonValue] = Values.mapping(
            value=inputs.graph.get("meaningful"),
        )
        return {
            "include": [],
            "exclude": [],
            "skipped": Values.items(value=meaningful.get("rows")),
        }
