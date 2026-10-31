#!/usr/bin/env python3
# Copyright (c) 2026
# Copyright (c) 2026
"""Exactus per-directory README documentation inventories."""

from __future__ import annotations

from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.common.snippets import with_excerpts
from exactus.tools.readme.arguments import create_parser as _create_parser
from exactus.tools.readme.core import (
    ReadmeExactusInput,
    ReadmeExactusResult,
    readme,
    report_data,
)
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
_project_python_active: bool = _project_python_auto.Constants.activated


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
            tool="readme",
            parser=parser,
            arguments=arguments,
        ),
    )


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
                f"readme: arguments — root {root}, "
                f"output {output_dir}, fix "
                f"{not cast(typ='bool', val=options.dry)}"
            ),
        )
        trace(step="readme: run start")
        result: ReadmeExactusResult = readme(
            inputs=ReadmeExactusInput(
                root=root,
                includes=tuple(cast(typ="list[str]", val=options.include)),
                excludes=tuple(cast(typ="list[str]", val=options.exclude)),
                fix=not cast(typ="bool", val=options.dry),
            ),
        )
        trace(step="stage: report", depth=1)
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output_dir / "README.md",
                json=output_dir / "README.json",
                web=output_dir / "README_web",
            ),
            analyzer="readme",
            title="README Exactus",
            markdown="",
            data=with_excerpts(
                payload=report_data(result=result),
                root=root,
                context=cast(typ="int", val=options.context_lines),
            ),
        )
        trace(
            step=f"report: bundle written — {output_dir / 'README.md'}",
            depth=2,
        )
        status: int = int(bool(result.findings))
        trace(step=f"readme: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(analyzer="readme", title="Readme Exactus", main=main),
    )
