# Copyright (c) 2026 João Lopes.
"""Thin command-line adapter over the canonical Python API."""

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from dataclasses import asdict
from json import dumps
from pathlib import Path
from sys import argv, stderr, stdout

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.meaningful.api import Meaningful
from exactus.packages.meaningful.models import (
    AnalysisRun,
    EvaluationPolicy,
    PromotionThresholds,
)


class MeaningfulCli:
    """Parse CLI selectors and serialize the Python API run model."""

    @classmethod
    def run(cls, *, arguments: Sequence[str] | None = None) -> int:
        """Run analysis and emit the complete run model as JSON.

        Args:
            arguments: Value supplied for ``arguments``.

        Returns:
            The resulting value.

        """
        options: Namespace = cls.parser().parse_args(
            args=list(argv[1:] if arguments is None else arguments),
        )
        try:
            policy: EvaluationPolicy = EvaluationPolicy(
                thresholds=PromotionThresholds(
                    test_0_to_1=options.threshold_test_0_to_1,
                    test_1_to_2=options.threshold_test_1_to_2,
                    test_2_to_3=options.threshold_test_2_to_3,
                ),
                evidence_context=options.evidence_context,
            )
            run: AnalysisRun = Meaningful(
                policy=policy,
                max_workers=options.workers,
            ).analyze(
                paths=tuple(options.paths),
                include=tuple(options.include),
                exclude=tuple(options.exclude),
            )
            payload: str = f"{
                dumps(
                    obj=asdict(obj=run), indent=2, sort_keys=True, default=str
                )
            }\n"
            if options.output_file is None:
                stdout.write(payload)
            else:
                options.output_file.parent.mkdir(parents=True, exist_ok=True)
                options.output_file.write_text(data=payload, encoding="utf-8")
        except (OSError, SyntaxError, ValueError) as error:
            stderr.write(f"error: {error}\n")
            return 2
        return 0

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the command-line parser.

        Returns:
            The resulting value.

        """
        parser: ArgumentParser = ExactusArgumentParser(prog="meaningful")
        parser.add_argument("paths", nargs="+")
        parser.add_argument("--include", action="append", default=[])
        parser.add_argument("--exclude", action="append", default=[])
        parser.add_argument(
            "--threshold-test-0-to-1",
            type=float,
            default=0.25,
        )
        parser.add_argument(
            "--threshold-test-1-to-2",
            type=float,
            default=0.50,
        )
        parser.add_argument(
            "--threshold-test-2-to-3",
            type=float,
            default=0.70,
        )
        parser.add_argument("--evidence-context", type=int, default=2)
        parser.add_argument("--workers", type=int)
        parser.add_argument("--output-file", type=Path)
        return parser


def main(*, arguments: Sequence[str] | None = None) -> None:
    """Run the CLI and terminate with its exit status.

    Args:
        arguments: Value supplied for ``arguments``.

    Raises:
        SystemExit: If the operation cannot be completed.

    """
    raise SystemExit(MeaningfulCli.run(arguments=arguments))
