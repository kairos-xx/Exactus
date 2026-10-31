# Copyright (c) 2026
"""Declare the coverage_tests CLI grammar."""

from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError
from typing import Final, final

from exactus.packages.meaningful import (
    EvaluationPolicy,
    FeatureCaps,
    FeatureWeights,
    PromotionFloors,
    PromotionThresholds,
)
from exactus.tools.common.cli import add_common_arguments, consume


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_fail_under: Grouped module constant.
        default_per_file_minimum: Grouped module constant.

    """

    default_fail_under: Final[float] = 90.0
    default_per_file_minimum: Final[float] = 80.0


"Default overall coverage requirement."
"Default per-source-file coverage requirement."


def _positive(value: str) -> int:
    """Parse a positive integer command-line value.

    Args:
        value: Value.

    Returns:
        The resulting value.

    Raises:
        ArgumentTypeError: Raised when the operation cannot be completed.

    """
    parsed: int = int(value)
    if parsed < 1:
        msg: str = "must be at least 1"
        raise ArgumentTypeError(msg)
    return parsed


def _non_negative(value: str) -> int:
    """Parse a non-negative integer command-line value.

    Args:
        value: Value.

    Returns:
        The resulting value.

    Raises:
        ArgumentTypeError: Raised when the operation cannot be completed.

    """
    parsed: int = int(value)
    if parsed < 0:
        msg: str = "must be at least 0"
        raise ArgumentTypeError(msg)
    return parsed


def _normalized(value: str) -> float:
    """Parse a floating-point value between zero and one.

    Args:
        value: Value.

    Returns:
        The resulting value.

    Raises:
        ArgumentTypeError: Raised when the operation cannot be completed.

    """
    parsed: float = float(value)
    if not 0.0 <= parsed <= 1.0:
        msg: str = "must be between 0 and 1"
        raise ArgumentTypeError(msg)
    return parsed


def _non_negative_float(value: str) -> float:
    """Parse a non-negative floating-point command-line value.

    Args:
        value: Value.

    Returns:
        The resulting value.

    Raises:
        ArgumentTypeError: Raised when the operation cannot be completed.

    """
    parsed: float = float(value)
    if parsed < 0.0:
        msg: str = "must be non-negative"
        raise ArgumentTypeError(msg)
    return parsed


def create_parser() -> ArgumentParser:
    """Create parser.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ArgumentParser(
        description="Run combined coverage for recursively discovered tests.",
    )
    add_common_arguments(parser=parser, default_output="COVERAGE_TESTS")
    _ = consume(
        value=parser.add_argument(
            "--source-root",
            action="append",
            default=[],
        ),
    )
    _ = consume(value=parser.add_argument("--no-branch", action="store_true"))
    _ = consume(
        value=parser.add_argument("--no-js-coverage", action="store_true"),
    )
    _ = consume(value=parser.add_argument("--jobs", type=_positive))
    _ = consume(
        value=parser.add_argument(
            "--shard-by",
            choices=("file", "node"),
            default="file",
            help=(
                "Balance pytest workers by test file or by collected pytest "
                "node ID. Node sharding can split large test modules."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--fail-under",
            type=float,
            default=Constants.default_fail_under,
            help="Fail when total coverage is below this percent.",
        ),
    )
    _ = consume(
        value=parser.add_argument("--pytest-arg", action="append", default=[]),
    )
    _ = consume(
        value=parser.add_argument("--include-unreached", action="store_true"),
    )
    _ = consume(value=parser.add_argument("--average-minimum", type=float))
    _ = consume(
        value=parser.add_argument(
            "--per-file-minimum",
            type=float,
            default=Constants.default_per_file_minimum,
            help=(
                "Fail when any single source file is below this percent "
                "(0 disables the per-file gate). Files below the minimum "
                "are excused when Meaningful classifies them below the "
                "minimum test level and are then excluded from coverage."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--minimum",
            type=float,
            default=80.0,
            help="Required total coverage of the validated evidence.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--critical",
            action="append",
            default=[],
            help=(
                "Path fragment of a control-plane module with a stricter "
                "floor; repeatable."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--critical-minimum",
            type=float,
            default=80.0,
        ),
    )
    policy: EvaluationPolicy = EvaluationPolicy()
    thresholds: PromotionThresholds = policy.thresholds
    weights: FeatureWeights = policy.weights
    caps: FeatureCaps = policy.caps
    floors: PromotionFloors = policy.floors
    _ = consume(
        value=parser.add_argument(
            "--meaningful",
            choices=("off", "classify", "require"),
            default="require",
            help=(
                "Meaningful classification of unreached and sub-minimum "
                "sources; 'off' disables both checks."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--meaningful-minimum-level",
            choices=("TEST-0", "TEST-1", "TEST-2", "TEST-3"),
            default="TEST-2",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--meaningful-unclassified",
            choices=("filtered", "actionable", "error"),
            default="filtered",
        ),
    )
    _ = consume(
        value=parser.add_argument("--meaningful-workers", type=_positive),
    )
    _ = consume(
        value=parser.add_argument(
            "--meaningful-evidence-context",
            type=_non_negative,
            default=policy.evidence_context,
        ),
    )
    for name, default in (
        ("test-0-to-1", thresholds.test_0_to_1),
        ("test-1-to-2", thresholds.test_1_to_2),
        ("test-2-to-3", thresholds.test_2_to_3),
    ):
        _ = consume(
            value=parser.add_argument(
                f"--meaningful-threshold-{name}",
                type=_normalized,
                default=default,
            ),
        )
    for name, default in (
        ("behavior", weights.behavior),
        ("public-surface", weights.public_surface),
        ("side-effects", weights.side_effects),
        ("mutations", weights.mutations),
        ("decisions", weights.decisions),
        ("errors", weights.errors),
        ("computations", weights.computations),
        ("size", weights.size),
        ("nesting", weights.nesting),
    ):
        _ = consume(
            value=parser.add_argument(
                f"--meaningful-weight-{name}",
                type=_non_negative_float,
                default=default,
            ),
        )
    for name, default in (
        ("behavioral-statements", caps.behavioral_statements),
        ("public-members", caps.public_members),
        ("side-effects", caps.side_effects),
        ("mutations", caps.mutations),
        ("decisions", caps.decisions),
        ("errors", caps.errors),
        ("computations", caps.computations),
        ("source-lines", caps.source_lines),
        ("nesting", caps.nesting),
    ):
        _ = consume(
            value=parser.add_argument(
                f"--meaningful-cap-{name}",
                type=_positive,
                default=default,
            ),
        )
    for name, default in (
        ("side-effect-test-1-to-2", floors.side_effect_test_1_to_2),
        ("mutation-test-1-to-2", floors.mutation_test_1_to_2),
        ("error-test-1-to-2", floors.error_test_1_to_2),
        ("import-runtime-test-1-to-2", floors.import_runtime_test_1_to_2),
        ("high-complexity-test-2-to-3", floors.high_complexity_test_2_to_3),
    ):
        _ = consume(
            value=parser.add_argument(
                f"--meaningful-floor-{name}",
                type=_normalized,
                default=default,
            ),
        )
    return parser
