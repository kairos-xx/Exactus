#!/usr/bin/env python3
# Copyright (c) 2026
"""Run the project's tests once for combined coverage and test reports."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from json import JSONDecodeError, dumps, loads
from os import cpu_count
from pathlib import Path
from sys import path as sys_path
from sys import stderr
from typing import TYPE_CHECKING, NoReturn, Self, cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.common.sprint import sprint
from exactus.tools.coverage_tests.arguments import (
    create_parser as _create_parser,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from exactus.tools.common.json_types import JsonValue
from exactus.packages.meaningful import UnitTestLevel
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import expand_paths, match_path, resolve_output
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CommandLine,
    CoverageConfig,
    CoverageCoreDefaults,
    CoverageCoreTables,
    CoverageRunError,
    CoverageTestsLayout,
)
from exactus.tools.coverage_tests.meaningful import (
    MeaningfulConfig,
    policy_from_values,
)
from exactus.tools.coverage_tests.report import CoverageTestsReport

_project_python_active: bool = _project_python_auto.Constants.activated


class CoverageValidator:
    """Reject partial/stale coverage evidence before release publication."""

    @classmethod
    def validate(
        cls: type[Self],
        *,
        directory: Path,
        minimum_percent: float,
        critical_patterns: tuple[str, ...] = (),
        critical_minimum: float = 0.0,
    ) -> dict[str, JsonValue]:
        """Validate completion marker, coverage JSON and minimum percentage.

        Args:
            directory: Directory.
            minimum_percent: Minimum percent.
            critical_patterns: Path fragments naming control-plane modules.
            critical_minimum: Per-file minimum for those modules.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        evidence: Path = cls.evidence(directory=directory)
        marker: Path = evidence / CoverageCoreDefaults.completion_name
        if not marker.is_file():
            msg: str = "coverage evidence is incomplete"
            raise ValueError(msg)
        completion: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=marker.read_text(encoding="utf-8")),
        )
        coverage: Path = evidence / str(
            object=completion.get("coverage_file", "coverage.json"),
        )
        if not coverage.is_file():
            msg = "coverage evidence is incomplete"
            raise ValueError(msg)
        if cast(
            typ="int",
            val=completion.get("returncode", -1),
        ) != 0 or not bool(completion.get("completed", False)):
            msg = "coverage test run did not complete successfully"
            raise ValueError(msg)
        if (
            cast(typ="int", val=completion.get("js_tests_discovered", 0)) > 0
            and cast(typ="int", val=completion.get("js_returncode", 0)) != 0
        ):
            msg = "javascript coverage test run did not complete successfully"
            raise ValueError(msg)
        digest: str = sha256(data=coverage.read_bytes()).hexdigest()
        if completion.get("coverage_sha256") != digest:
            msg = "coverage data hash does not match completion marker"
            raise ValueError(msg)
        data: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=coverage.read_text(encoding="utf-8")),
        )
        totals: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=data.get("totals", {}),
        )
        percent: float = float(
            cast(
                typ="float | str | int",
                val=totals.get(
                    "percent_covered",
                    totals.get("percent_covered_display", 0.0),
                ),
            ),
        )
        if percent < minimum_percent:
            msg = (
                f"coverage {percent:.2f}% is below"
                f" required {minimum_percent:.2f}%"
            )
            raise ValueError(msg)
        shortfalls: tuple[tuple[str, float], ...] = cls.critical_shortfalls(
            data=data,
            patterns=critical_patterns,
            minimum_percent=critical_minimum,
        )
        if shortfalls:
            listed: str = ", ".join(
                (f"{path} {value:.2f}%" for path, value in shortfalls[:5]),
            )
            msg = (
                f"{len(shortfalls)} control-plane module(s) below"
                f" required {critical_minimum:.2f}%: {listed}"
            )
            raise ValueError(msg)
        trace(
            step=(
                f"validate: coverage {percent:.2f}% — marker, hash, "
                f"and {len(critical_patterns)} critical patterns pass"
            ),
            depth=2,
        )
        return cast(
            typ="dict[str, JsonValue]",
            val={
                "status": "PASS",
                "percent": percent,
                "critical_minimum": critical_minimum,
                "critical_patterns": list(critical_patterns),
                "coverage_sha256": digest,
                "tests_collected": completion.get("tests_collected"),
                "tests_executed": completion.get("tests_executed"),
            },
        )

    @staticmethod
    def critical_shortfalls(
        *,
        data: dict[str, JsonValue],
        patterns: tuple[str, ...],
        minimum_percent: float,
    ) -> tuple[tuple[str, float], ...]:
        """Return control-plane files below their own coverage floor.

        State-changing control-plane code carries a per-file floor that
        presentation and helper modules do not, so a well-covered whole
        tree cannot hide one poorly exercised critical module.

        Args:
            data: Parsed ``coverage.json`` payload.
            patterns: Path fragments identifying critical modules.
            minimum_percent: Per-file minimum for those modules.

        Returns:
            ``(path, percent)`` pairs sorted by percentage, lowest first.

        """
        if not patterns:
            return ()
        files: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=data.get("files", {}),
        )
        shortfalls: list[tuple[str, float]] = []
        path: str
        entry: object
        for path, entry in files.items():
            if not any(pattern in path for pattern in patterns):
                continue
            summary: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=cast(typ="dict[str, JsonValue]", val=entry).get(
                    "summary",
                    {},
                ),
            )
            percent: float = float(
                cast(
                    typ="float | str | int",
                    val=summary.get("percent_covered", 0.0),
                ),
            )
            if percent < minimum_percent:
                shortfalls.append((path, percent))
        return tuple(sorted(shortfalls, key=lambda item: item[1]))

    @staticmethod
    def evidence(*, directory: Path) -> Path:
        """Locate the directory holding the completion marker.

        The tool keeps its coverage evidence in ``ARTIFACTS/COVERAGE``;
        a bare ``ARTIFACTS`` directory or ``directory`` itself is accepted
        for evidence produced elsewhere.

        Args:
            directory: Tool output or evidence directory.

        Returns:
            The first candidate holding ``completion.json``, else
            ``directory``.

        """
        layout: CoverageTestsLayout = CoverageTestsLayout(root=directory)
        candidate: Path
        for candidate in (layout.coverage_artifacts, layout.artifacts):
            if (candidate / CoverageCoreDefaults.completion_name).is_file():
                return candidate
        return directory


def create_parser() -> ArgumentParser:
    """Return the shared CLI grammar used by execution and completion.

    Returns:
        Configured tool argument parser.

    """
    return _create_parser()


def parse_args(*, arguments: tuple[str, ...] | None = None) -> Namespace:
    """Parse args.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = create_parser()
    return parser.parse_args(
        args=resolve_arguments(
            tool="coverage_tests",
            parser=parser,
            arguments=arguments,
        ),
    )


def _fail(*, message: str) -> NoReturn:
    """Raise a coverage failure with a prepared message.

    Args:
        message: `str` value used by the operation.

    Raises:
        CoverageRunError: Always, carrying ``message``.

    """
    raise CoverageRunError(message)


def _validate(*, options: Namespace, output_dir: Path) -> int:
    """Reject partial, stale or below-minimum coverage evidence.

    The completion marker must report a successful run (including the
    JavaScript lane), its hash must match the coverage data, and the
    totals must meet ``--minimum`` and the ``--critical`` floors. The
    verdict is written to ``ARTIFACTS/COVERAGE/validation.json``.

    Args:
        options: Parsed coverage arguments.
        output_dir: Tool output directory holding the evidence.

    Returns:
        ``0`` when the evidence is valid, ``2`` otherwise.

    """
    code: int = 0
    try:
        result: dict[str, JsonValue] = CoverageValidator.validate(
            directory=output_dir,
            minimum_percent=cast(typ="float", val=options.minimum),
            critical_patterns=tuple(
                cast(typ="list[str]", val=options.critical),
            ),
            critical_minimum=cast(typ="float", val=options.critical_minimum),
        )
    except ValueError as error:
        result = {"status": "INVALID_RESULT", "reason": str(object=error)}
        trace(step=f"validate: failed — {error}", depth=2)
        sprint(f"coverage validation failed: {error}", file=stderr)
        code = 2
    evidence: Path = CoverageTestsLayout(root=output_dir).coverage_artifacts
    evidence.mkdir(parents=True, exist_ok=True)
    _ = (evidence / CoverageCoreDefaults.validation_name).write_text(
        data=dumps(obj=result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return code


def _verdict(*, output_dir: Path) -> dict[str, JsonValue] | None:
    """Read the evidence verdict ``_validate`` wrote.

    Args:
        output_dir: Tool output directory.

    Returns:
        The ``validation.json`` object, or ``None`` when absent.

    """
    path: Path = (
        CoverageTestsLayout(root=output_dir).coverage_artifacts
        / CoverageCoreDefaults.validation_name
    )
    try:
        loaded: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _rewrite_root(
    *,
    runner: CombinedCoverageRunner,
    output_dir: Path,
    average_minimum: float | None,
    validation: dict[str, JsonValue] | None,
) -> None:
    """Rewrite the root report with the gates checked after the run.

    The runner writes the root report with the gates it knows
    (``--fail-under``, ``--per-file-minimum``); the average per-file
    minimum and the evidence check are applied here, so the coverage part
    gate covers every coverage gate.

    Args:
        runner: Runner that completed (its ``report_inputs`` are set).
        output_dir: Tool output directory.
        average_minimum: ``--average-minimum``, or ``None``.
        validation: Evidence verdict, or ``None`` when it did not run.

    """
    if runner.report_inputs is None:
        return
    CoverageTestsReport.write(
        inputs=replace(
            runner.report_inputs,
            gates=replace(
                runner.report_inputs.gates,
                average_minimum=average_minimum,
                validation=validation,
            ),
        ),
        output=output_dir,
        legacy=runner.report_legacy,
    )


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Return main.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    options: Namespace = parse_args(arguments=arguments)
    requested_root: Path = cast(typ="Path", val=options.root).resolve()
    root: Path = CommandLine.project_root(root=requested_root)
    output_dir: Path = resolve_output(
        root=requested_root,
        output=cast(typ="Path", val=options.output_dir),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    includes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.include),
    )
    excludes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.exclude),
    )
    source_roots: tuple[Path, ...] = expand_paths(
        root=root,
        patterns=tuple(cast(typ="list[str]", val=options.source_root)),
    ) or CommandLine.target_source_roots(requested=requested_root, root=root)
    config: CoverageConfig = CoverageConfig(
        root=root,
        output=output_dir,
        source_roots=source_roots,
        branch=not cast(typ="bool", val=options.no_branch),
        fail_under=cast(typ="float | None", val=options.fail_under),
        excluded_dirs=CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
        pytest_args=tuple(cast(typ="list[str]", val=options.pytest_arg)),
        include_unreached=cast(typ="bool", val=options.include_unreached),
        measure_js=not cast(typ="bool", val=options.no_js_coverage),
        jobs=cast(typ="int | None", val=options.jobs) or cpu_count() or 1,
        shard_by=cast(typ="str", val=options.shard_by),
        context_lines=max(0, cast(typ="int", val=options.context_lines)),
        per_file_minimum=cast(
            typ="float | None",
            val=options.per_file_minimum,
        ),
        test_includes=includes,
        test_excludes=excludes,
        source_excludes=excludes,
        meaningful=MeaningfulConfig(
            mode=options.meaningful,
            minimum_level=UnitTestLevel(options.meaningful_minimum_level),
            unclassified=options.meaningful_unclassified,
            workers=options.meaningful_workers,
            policy=policy_from_values(
                evidence_context=options.meaningful_evidence_context,
                thresholds=(
                    options.meaningful_threshold_test_0_to_1,
                    options.meaningful_threshold_test_1_to_2,
                    options.meaningful_threshold_test_2_to_3,
                ),
                weights=(
                    options.meaningful_weight_behavior,
                    options.meaningful_weight_public_surface,
                    options.meaningful_weight_side_effects,
                    options.meaningful_weight_mutations,
                    options.meaningful_weight_decisions,
                    options.meaningful_weight_errors,
                    options.meaningful_weight_computations,
                    options.meaningful_weight_size,
                    options.meaningful_weight_nesting,
                ),
                caps=(
                    options.meaningful_cap_behavioral_statements,
                    options.meaningful_cap_public_members,
                    options.meaningful_cap_side_effects,
                    options.meaningful_cap_mutations,
                    options.meaningful_cap_decisions,
                    options.meaningful_cap_errors,
                    options.meaningful_cap_computations,
                    options.meaningful_cap_source_lines,
                    options.meaningful_cap_nesting,
                ),
                floors=(
                    options.meaningful_floor_side_effect_test_1_to_2,
                    options.meaningful_floor_mutation_test_1_to_2,
                    options.meaningful_floor_error_test_1_to_2,
                    options.meaningful_floor_import_runtime_test_1_to_2,
                    options.meaningful_floor_high_complexity_test_2_to_3,
                ),
            ),
        ),
    )
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=config,
        test_filter=lambda path: match_path(
            path=path,
            root=root,
            includes=includes,
            excludes=excludes,
            defaults=False,
        ),
    )
    average_minimum: float | None = cast(
        typ="float | None",
        val=options.average_minimum,
    )
    artifacts: Path = CoverageTestsLayout(root=output_dir).artifacts
    with step_log(path=artifacts / "steps.txt"):
        trace(
            step=(
                f"coverage tests: arguments — root {root}, "
                f"output {output_dir}, jobs {config.jobs}"
            ),
        )
        trace(step="coverage tests: run start")
        try:
            status: int = runner.run()
            trace(
                step=f"coverage tests: run finished — status {status}",
                depth=1,
            )
            validation: int = _validate(options=options, output_dir=output_dir)
            trace(
                step=(
                    f"coverage tests: evidence validation — exit {validation}"
                ),
                depth=1,
            )
            _rewrite_root(
                runner=runner,
                output_dir=output_dir,
                average_minimum=average_minimum,
                validation=_verdict(output_dir=output_dir),
            )
            if status:
                return status
            if validation:
                return validation
            if average_minimum is None:
                trace(step="coverage tests: done — status 0")
                return 0
            data: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=loads(
                    s=(
                        CoverageTestsLayout(root=output_dir).coverage_artifacts
                        / CoverageCoreDefaults.raw_report_name
                    ).read_text(encoding="utf-8"),
                ),
            )
            files: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=data.get("files", {}),
            )
            percentages: tuple[tuple[str, float], ...] = tuple(
                (
                    (
                        path,
                        cast(
                            typ="float",
                            val=cast(
                                typ="dict[str, JsonValue]",
                                val=cast(
                                    typ="dict[str, JsonValue]",
                                    val=entry,
                                ).get("summary", {}),
                            ).get("percent_covered", 0.0),
                        ),
                    )
                    for path, entry in files.items()
                ),
            )
            if not percentages:
                _fail(message="coverage report contains no source files")
            average: float = sum((value for _, value in percentages)) / len(
                percentages,
            )
            trace(
                step=(
                    f"coverage tests: average per-file coverage — "
                    f"{average:.2f}% (minimum {average_minimum:.2f}%)"
                ),
                depth=1,
            )
            if average < average_minimum:
                _fail(
                    message=(
                        f"average per-file coverage {average:.2f}%"
                        f" is below required {average_minimum:.2f}%"
                    ),
                )
            trace(step="coverage tests: done — status 0")
        except CoverageRunError as error:
            error: CoverageRunError
            trace(step=f"coverage tests: failed — {error}")
            sprint(f"{error}", file=stderr)
            return 1
        return 0


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(
            analyzer="coverage_tests",
            title="Coverage and Tests Exactus",
            main=main,
        ),
    )
