"""Run the visual-cause exactus and write its report bundle."""

from __future__ import annotations

from sys import argv as sys_argv
from typing import TYPE_CHECKING, cast

from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.visual_cause.arguments import (
    create_parser as _create_parser,
)
from exactus.tools.visual_cause.core import VisualCauseRequest, run
from exactus.tools.visual_cause.queries import QuerySyntaxError
from exactus.tools.visual_cause.report import data, markdown
from exactus.tools.visual_cause.targets import Target, TargetOptions, resolve

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from pathlib import Path

    from exactus.tools.visual_cause.core import VisualCauseResult
_project_python_active: bool = _project_python_auto.Constants.activated


def create_parser() -> ArgumentParser:
    """Return the shared CLI grammar.

    Returns:
        Configured argument parser.

    """
    return _create_parser()


def parse_args(*, arguments: tuple[str, ...] | None = None) -> Namespace:
    """Resolve configuration, parse arguments, and validate targets.

    Args:
        arguments: CLI arguments, defaulting to ``sys.argv``.

    Returns:
        Parsed options carrying ``resolved_targets``.

    """
    parser: ArgumentParser = create_parser()
    given: tuple[str, ...] = (
        tuple(sys_argv[1:]) if arguments is None else arguments
    )
    options: Namespace = parser.parse_args(
        args=resolve_arguments(
            tool="visual_cause",
            parser=parser,
            arguments=given,
        ),
    )
    try:
        options.resolved_targets = resolve(
            options=cast(typ="TargetOptions", val=options),
        )
    except (FileNotFoundError, TypeError, ValueError) as error:
        parser.error(message=str(object=error))
    return options


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Run configured visual comparisons and return their gate status.

    Args:
        arguments: CLI arguments, defaulting to ``sys.argv``.

    Returns:
        ``0`` when no target failed, ``1`` otherwise.

    """
    options: Namespace = parse_args(arguments=arguments)
    root: Path = cast(typ="Path", val=options.root).resolve()
    output: Path = resolve_output(
        root=root,
        output=cast(typ="Path", val=options.output_dir),
    )
    with step_log(path=output / "ARTIFACTS" / "steps.txt"):
        trace(step=(f"visual_cause: arguments — root {root}, output {output}"))
        trace(step="visual_cause: run start")
        try:
            result: VisualCauseResult = run(
                request=VisualCauseRequest(
                    targets=cast(
                        typ="tuple[Target, ...]",
                        val=options.resolved_targets,
                    ),
                    output=output,
                ),
            )
        except QuerySyntaxError as error:
            create_parser().error(message=str(object=error))
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output / "result.md",
                json=output / "result.json",
                web=output / "result_web",
            ),
            analyzer="visual_cause",
            title="Visual Cause Exactus",
            markdown=markdown(result=result),
            data=data(result=result, project_root=str(object=root)),
        )
        trace(step=f"visual_cause: run finished — status {int(result.failed)}")
        return int(result.failed)


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(
            analyzer="visual_cause",
            title="Visual Cause Exactus",
            main=main,
        ),
    )
