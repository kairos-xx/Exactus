# Copyright (c) 2026 João Lopes.
"""Command-line interface for performance trace analysis."""

from argparse import SUPPRESS, ArgumentParser, BooleanOptionalAction, Namespace
from pathlib import Path

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.performance.api import Performance
from exactus.packages.performance.config import PerformanceConfig


class Arguments(Namespace):
    """Store typed command-line arguments.

    Attributes:
        sources: Optional source expressions overriding ``tool.performance``.
        project: Optional project root used to locate ``pyproject.toml``.
        output: Optional dashboard output override.
        report: Optional JSON report destination override.
        serve: Optional server behavior override.
        open: Optional managed-browser behavior override.
        chrome: Optional Chrome or Chromium executable override.
        gap_threshold: Optional silent-gap threshold override.
        repetition_threshold: Optional repetition threshold override.
        server_timeout: Optional server readiness timeout override.
        summary: Whether to print analysis without exporting or serving.

    """

    sources: list[str] | None
    project: Path | None
    output: Path | None
    report: Path | None
    serve: bool | None
    open: bool | None
    chrome: Path | None
    gap_threshold: float | None
    repetition_threshold: int | None
    server_timeout: float | None
    summary: bool


class PerformanceCli:
    """Parse CLI arguments and dispatch performance analysis."""

    @classmethod
    def run(cls, *, arguments: tuple[str, ...] | None = None) -> int:
        """Execute the CLI using CLI, pyproject, then package defaults.

        Args:
            arguments: Optional explicit argument vector.

        Returns:
            Zero on success, or two when no traces are discovered.

        """
        parsed: Arguments = cls.parser().parse_args(
            args=arguments,
            namespace=Arguments(),
        )
        config: PerformanceConfig = PerformanceConfig.load(
            project=parsed.project,
            sources=tuple(parsed.sources) if parsed.sources else None,
            output=parsed.output,
            serve=parsed.serve,
            open_browser=parsed.open,
            chrome=parsed.chrome,
            gap_threshold=parsed.gap_threshold,
            repetition_threshold=parsed.repetition_threshold,
            server_timeout=parsed.server_timeout,
        )
        return Performance.execute(
            config=config,
            summary=parsed.summary,
            report=parsed.report,
        )

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the argument parser.

        Returns:
            Configured parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            prog="performance",
            description=(
                "Analyze Exactus steps.txt traces and profile bottlenecks."
            ),
        )
        _ = parser.add_argument(
            "sources",
            nargs="*",
            help="files, directories, or globs; defaults to tool.performance",
        )
        _ = parser.add_argument("--project", type=Path)
        _ = parser.add_argument("-o", "--output", type=Path)
        _ = parser.add_argument(
            "--report",
            type=Path,
            help=(
                "write the full JSON report here (default: "
                "<output>/report.json); no browser or server is needed"
            ),
        )
        _ = parser.add_argument(
            "--serve",
            action=BooleanOptionalAction,
            default=None,
        )
        _ = parser.add_argument(
            "--open",
            action=BooleanOptionalAction,
            default=None,
        )
        _ = parser.add_argument(
            "--no-browser",
            action="store_false",
            dest="open",
            help=SUPPRESS,
        )
        _ = parser.add_argument("--chrome", type=Path)
        _ = parser.add_argument("--gap-threshold", type=float)
        _ = parser.add_argument("--repetition-threshold", type=int)
        _ = parser.add_argument("--server-timeout", type=float)
        _ = parser.add_argument(
            "--summary",
            action="store_true",
            help="print analysis only; do not export or serve",
        )
        return parser
