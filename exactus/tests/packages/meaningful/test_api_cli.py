# Copyright (c) 2026 João Lopes.
"""Tests for the object-oriented API, parallel runs, metadata, and CLI."""

from pathlib import Path
from textwrap import dedent
from typing import Final, final

import pytest

from exactus.packages.meaningful import (
    AnalysisRun,
    AnalysisStage,
    EvaluationPolicy,
    FileFinding,
    Meaningful,
    ProgressSnapshot,
    PromotionThresholds,
    UnitTestLevel,
    analyze,
)
from exactus.packages.meaningful.cli import MeaningfulCli
from exactus.packages.meaningful.examples.api.run import ApiExample
from exactus.packages.meaningful.examples.cli.run import CliExample


@final
class Constants:
    """Group module-level constants.

    Attributes:
        expected_file_count: Grouped module constant.
        expected_callback_count: Grouped module constant.
        expected_percent: Grouped module constant.
        expected_workers: Grouped module constant.
        expected_source_lines: Grouped module constant.
        invalid_exit_code: Grouped module constant.

    """

    expected_file_count: Final[int] = 8
    expected_callback_count: Final[int] = 6
    expected_percent: Final[float] = 100.0
    expected_workers: Final[int] = 3
    expected_source_lines: Final[int] = 16
    invalid_exit_code: Final[int] = 2


def expect(*, condition: bool) -> None:
    """Fail when a test condition is false.

    Args:
        condition: Condition that must hold.

    Raises:
        AssertionError: If ``condition`` is false.

    """
    if not condition:
        raise AssertionError


def _write(*, path: Path, source: str) -> Path:
    """Write a source fixture.

    Args:
        path: Value supplied for ``path``.
        source: Value supplied for ``source``.

    Returns:
        The resulting value.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data=source, encoding="utf-8")
    return path


def test_parallel_run_metadata_and_progress(*, tmp_path: Path) -> None:
    """Account for every finished worker and aggregate run metadata.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    for index in range(8):
        _write(
            path=tmp_path / f"m{index}.py",
            source=(
                f"def f{index}(value: int) -> int:\n    "
                "return value + {index}\n"
            ),
        )
    updates: list[ProgressSnapshot] = []
    run: AnalysisRun = Meaningful(
        max_workers=3,
        on_progress=updates.append,
    ).analyze(paths=tmp_path)
    expect(condition=len(run.findings) == Constants.expected_file_count)
    expect(condition=not run.failures)
    expect(condition=len(updates) == Constants.expected_file_count * 4)
    expect(
        condition={update.stage for update in updates}
        == {
            AnalysisStage.FILE_STARTED,
            AnalysisStage.FAST_SCAN,
            AnalysisStage.EVIDENCE,
            AnalysisStage.DECISION,
        },
    )
    expect(condition=updates[-1].completed == Constants.expected_file_count)
    expect(condition=updates[-1].remaining == 0)
    expect(condition=updates[-1].percent == Constants.expected_percent)
    expect(condition=run.metadata.total_files == Constants.expected_file_count)
    expect(
        condition=run.metadata.kept + run.metadata.filtered
        == Constants.expected_file_count,
    )
    expect(
        condition=len(run.should_be_visited) + len(run.filtered)
        == Constants.expected_file_count,
    )
    expect(condition=run.metadata.workers_used == Constants.expected_workers)
    expect(
        condition=run.metadata.duration_seconds
        >= run.metadata.analysis_seconds,
    )
    expect(condition=run.metadata.total_bytes > 0)
    expect(
        condition=run.metadata.total_source_lines
        == Constants.expected_source_lines,
    )


def test_javascript_behavior_is_classified_as_needing_tests(
    *,
    tmp_path: Path,
) -> None:
    """Keep dynamically loaded JavaScript behavior in the actionable set.

    Args:
        tmp_path: Temporary source directory.

    """
    source: Path = _write(
        path=tmp_path / "selector.js",
        source=(
            dedent(
                text=(
                    "    async context => {\n      try {\n        const it"
                    "ems = context.targets.map(value => value + 1);\n     "
                    "   if (items.length > 1) context.log(items);\n       "
                    " return await Promise.all(items);\n      } catch (err"
                    "or) {\n        throw new Error(String(error));\n     "
                    " }\n    };\n    "
                ),
            )
        ),
    )
    run: AnalysisRun = Meaningful(max_workers=1).analyze(paths=source)
    expect(condition=not run.failures)
    finding: FileFinding = run.findings[0]
    expect(condition=finding.should_be_visited)
    expect(
        condition=finding.level
        in {UnitTestLevel.TEST_2, UnitTestLevel.TEST_3},
    )
    expect(condition=bool(finding.evidence))
    expect(condition=bool(run.metadata.python_version))
    expect(condition=bool(run.metadata.platform))
    expect(condition=bool(run.metadata.working_directory))
    expect(
        condition=all(
            finding.metadata.worker_name for finding in run.findings
        ),
    )
    expect(
        condition=all(
            finding.metadata.duration_seconds >= 0.0
            for finding in run.findings
        ),
    )


def test_policy_thresholds_evidence_and_context(*, tmp_path: Path) -> None:
    """Expose scores and final-level source evidence through data models.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = _write(
        path=tmp_path / "complex.py",
        source=(
            dedent(
                text=(
                    "    def compute(value: int) -> int:\n        total: i"
                    "nt = 0\n        for item in range(value):\n          "
                    "  if item % 2:\n                total += item\n      "
                    "  return total\n    "
                ),
            )
        ),
    )
    policy: EvaluationPolicy = EvaluationPolicy(
        thresholds=PromotionThresholds(
            test_0_to_1=0.0,
            test_1_to_2=0.0,
            test_2_to_3=0.0,
        ),
        evidence_context=1,
    )
    finding: FileFinding = (
        Meaningful(policy=policy).analyze(paths=path).findings[0]
    )
    expect(condition=finding.level is UnitTestLevel.TEST_3)
    expect(condition=finding.scores.test_2_to_3 > 0.0)
    expect(condition=bool(finding.evidence))
    expect(condition=finding.should_be_visited)
    expect(condition=bool(finding.decision_tree))
    expect(condition=finding.decision_tree[-1].level_after is finding.level)
    expect(
        condition=set(finding.decision_tree[-1].evidence_ids)
        <= {item.id for item in finding.evidence},
    )
    expect(
        condition=all(
            item.context_start_line >= 1 for item in finding.evidence
        ),
    )
    expect(
        condition=any(
            line.highlighted
            for item in finding.evidence
            for line in item.source
        ),
    )


def test_resolution_inputs_and_filters(*, tmp_path: Path) -> None:
    """Support strings, Paths, folders, globs, include, and exclude.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    keep: Path = _write(
        path=tmp_path / "src" / "keep.py",
        source="VALUE = 1\n",
    )
    skip: Path = _write(
        path=tmp_path / "src" / "skip.py",
        source="VALUE = 2\n",
    )
    expect(
        condition=Meaningful.resolve(
            paths=[str(object=tmp_path / "src"), keep],
            include=(str(object=tmp_path / "src" / "*.py"),),
            exclude=(skip,),
        )
        == (keep.resolve(),),
    )
    expect(
        condition=Meaningful.resolve(
            paths=str(object=tmp_path / "**" / "missing*.py"),
        )
        == (),
    )


def test_failures_are_accounted_and_callback_isolated(
    *,
    tmp_path: Path,
) -> None:
    """Keep failed workers and callback errors from corrupting a run.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    _write(path=tmp_path / "good.py", source="VALUE = 1\n")
    _write(path=tmp_path / "bad.py", source="def broken(:\n")
    calls: list[ProgressSnapshot] = []

    def callback(snapshot: ProgressSnapshot) -> None:
        """Document callback.

        Args:
            snapshot: Value supplied for ``snapshot``.

        Raises:
            RuntimeError: If the operation cannot be completed.

        """
        calls.append(snapshot)
        msg: str = "observer failure"
        raise RuntimeError(msg)

    run: AnalysisRun = Meaningful(on_progress=callback).analyze(paths=tmp_path)
    expect(condition=len(run.findings) == 1)
    expect(condition=len(run.failures) == 1)
    expect(condition=run.metadata.failed == 1)
    expect(condition=run.failures[0].duration_seconds >= 0.0)
    expect(condition=len(calls) == Constants.expected_callback_count)
    expect(condition=calls[-1].percent == Constants.expected_percent)


def test_functional_api_and_overrides(*, tmp_path: Path) -> None:
    """Support functional convenience and per-run configuration overrides.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = _write(path=tmp_path / "a.py", source="VALUE = 1\n")
    run: AnalysisRun = analyze(paths=str(object=path), max_workers=1)
    expect(condition=run.metadata.workers_used == 1)
    overridden: AnalysisRun = Meaningful(max_workers=4).analyze(
        paths=path,
        max_workers=1,
        evidence_context=0,
    )
    expect(condition=overridden.metadata.workers_used == 1)


def test_validation_errors(*, tmp_path: Path) -> None:
    """Reject invalid workers, policies, and literal selectors.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    with pytest.raises(expected_exception=ValueError, match="max_workers"):
        Meaningful(max_workers=0)
    with pytest.raises(expected_exception=ValueError, match="max_workers"):
        Meaningful().analyze(paths=(), max_workers=0)
    with pytest.raises(
        expected_exception=ValueError,
        match="evidence_context",
    ):
        EvaluationPolicy(evidence_context=-1)
    with pytest.raises(expected_exception=ValueError, match="between 0 and 1"):
        PromotionThresholds(test_0_to_1=1.1)
    with pytest.raises(expected_exception=FileNotFoundError):
        Meaningful.resolve(paths=tmp_path / "missing.py")
    text: Path = _write(path=tmp_path / "a.txt", source="x")
    with pytest.raises(
        expected_exception=ValueError,
        match="Expected a Python or JavaScript file",
    ):
        Meaningful.resolve(paths=text)


def test_cli_json_output_file_and_errors(
    *,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Keep CLI a thin JSON adapter over the run model.

    Args:
        tmp_path: Value supplied for ``tmp_path``.
        capfd: Value supplied for ``capfd``.

    """
    source: Path = _write(path=tmp_path / "a.py", source="VALUE = 1\n")
    expect(
        condition=MeaningfulCli.run(
            arguments=(str(object=source), "--workers", "1"),
        )
        == 0,
    )
    capfd.readouterr()
    target: Path = tmp_path / "out" / "result.json"
    expect(
        condition=MeaningfulCli.run(
            arguments=(
                str(object=source),
                "--output-file",
                str(object=target),
                "--evidence-context",
                "0",
            ),
        )
        == 0,
    )
    expect(condition=target.exists())
    expect(
        condition=MeaningfulCli.run(
            arguments=(str(object=tmp_path / "missing.py"),),
        )
        == Constants.invalid_exit_code,
    )
    capfd.readouterr()


def test_examples_execute(capfd: pytest.CaptureFixture[str]) -> None:
    """Exercise the documented Python and CLI examples.

    Args:
        capfd: Value supplied for ``capfd``.

    """
    ApiExample.run()
    capfd.readouterr()
    expect(condition=CliExample.run() == 0)
    capfd.readouterr()
