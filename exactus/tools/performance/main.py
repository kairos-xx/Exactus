#!/usr/bin/env python3
# Copyright (c) 2026
"""Instrument the generic performance package against this project."""

from __future__ import annotations

from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.performance.api import Performance
from exactus.packages.performance.config import PerformanceConfig
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.performance.arguments import create_parser as _create_parser
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace

    from exactus.packages.performance.model import PerformanceRun
    from exactus.tools.common.json_types import JsonValue
_project_python_active: bool = _project_python_auto.Constants.activated


class Constants:
    """Hold the Exactus-specific performance defaults.

    Attributes:
        default_sources: Result tree scanned for steps.txt traces.
        default_gap_threshold: Silent-gap threshold in seconds.
        default_repetition_threshold: Repeated-step count treated as a
            bottleneck.
        default_server_timeout: Seconds to wait for the dashboard server.

    """

    default_sources: tuple[str, ...] = ("EXACTUS_RESULTS",)
    default_gap_threshold: float = 0.25
    default_repetition_threshold: int = 10
    default_server_timeout: float = 10.0


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
            tool="performance",
            parser=parser,
            arguments=arguments,
        ),
    )


def _data(
    *,
    runs: tuple[PerformanceRun, ...],
    config: PerformanceConfig,
    root: Path,
) -> dict[str, JsonValue]:
    """Build the normalized report payload.

    Args:
        runs: Analyzed performance runs.
        config: Resolved analyzer configuration.
        root: Repository root recorded in the payload.

    Returns:
        ``summary``, ``scope``, ``findings`` and ``extension`` blocks
        plus the ``resume`` line lifted into the envelope.

    """
    slowest: PerformanceRun | None = (
        max(runs, key=lambda run: run.duration) if runs else None
    )
    resume: str = (
        "No steps.txt traces found."
        if slowest is None
        else (
            f"{len(runs)} run{'s' if len(runs) != 1 else ''} profiled — "
            f"slowest {slowest.tool} {slowest.duration:.1f}s"
        )
    )
    return {
        "status": "PASS" if runs else "FAIL",
        "project_root": str(object=root),
        "resume": resume,
        "summary": {
            "runs": len(runs),
            "findings": 0,
            "severity": {"error": 0, "warning": 0, "info": 0},
        },
        "findings": [],
        "scope": {"include": list(config.sources), "exclude": []},
        "extension": {
            "output": str(object=config.output),
            "serve": config.serve,
            "gap_threshold": config.gap_threshold,
            "repetition_threshold": config.repetition_threshold,
            "runs": [
                {
                    "tool": run.tool,
                    "duration": run.duration,
                    "events": len(run.events),
                    "events_per_second": run.event_rate,
                    "largest_gap": run.largest_gap,
                    "silent": run.silent,
                    "actors": len(run.actors),
                    "threads": len(run.threads),
                }
                for run in runs
            ],
        },
    }


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Return main.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    options: Namespace = parse_args(arguments=arguments)
    root: Path = cast(typ="Path", val=options.root).resolve()
    output_dir: Path = resolve_output(
        root=root,
        output=cast(typ="Path", val=options.output_dir),
    )
    with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
        trace(
            step=(
                f"performance: arguments — root {root}, output {output_dir}"
            ),
        )
        trace(step="performance: run start")
        config: PerformanceConfig = PerformanceConfig(
            project=root,
            sources=tuple(
                cast(typ="list[str] | None", val=options.sources)
                or Constants.default_sources,
            ),
            output=output_dir,
            serve=(
                options_serve
                if (
                    options_serve := cast(typ="bool | None", val=options.serve)
                )
                is not None
                else True
            ),
            open=(
                options_open
                if (options_open := cast(typ="bool | None", val=options.open))
                is not None
                else True
            ),
            chrome=cast(typ="Path | None", val=options.chrome),
            gap_threshold=(
                cast(typ="float | None", val=options.gap_threshold)
                or Constants.default_gap_threshold
            ),
            repetition_threshold=(
                cast(typ="int | None", val=options.repetition_threshold)
                or Constants.default_repetition_threshold
            ),
            server_timeout=(
                cast(typ="float | None", val=options.server_timeout)
                or Constants.default_server_timeout
            ),
        )
        runs: tuple[PerformanceRun, ...] = Performance.analyze(
            paths=config.paths(),
            gap_threshold=config.gap_threshold,
            repetition_threshold=config.repetition_threshold,
        )
        trace(step=f"performance: analyzed {len(runs)} runs", depth=1)
        status: int = Performance.execute(
            config=config,
            runs=runs,
            summary=cast(typ="bool", val=options.summary),
            report=cast(typ="Path | None", val=options.report),
        )
        trace(step="stage: report", depth=1)
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output_dir / "result.md",
                json=output_dir / "result.json",
                web=output_dir / "result_web",
            ),
            analyzer="performance",
            title="Performance Exactus",
            markdown="",
            data=_data(runs=runs, config=config, root=root),
        )
        trace(
            step=(f"report: bundle written — {output_dir / 'result.md'}"),
            depth=2,
        )
        trace(step=f"performance: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(
            analyzer="performance",
            title="Performance Exactus",
            main=main,
        ),
    )
