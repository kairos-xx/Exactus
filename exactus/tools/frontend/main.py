#!/usr/bin/env python3
# Copyright (c) 2026
# Copyright (c) 2026
"""Execute Studio workflows and report functional frontend evidence."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from sys import argv as sys_argv
from sys import path as sys_path
from typing import cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from typing import TYPE_CHECKING

from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import (
    activate_exactus_tool_bundle,
    resolve_output,
)
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.frontend.arguments import create_parser as _create_parser
from exactus.tools.frontend.core import (
    FrontendExactusInput,
    FrontendExactusResult,
    frontend,
    markdown_report,
    report_data,
)
from exactus.tools.frontend.progress import FrontendProgress
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue
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
    given: tuple[str, ...] = (
        tuple(sys_argv[1:]) if arguments is None else arguments
    )
    resolved: tuple[str, ...] = resolve_arguments(
        tool="frontend",
        parser=parser,
        arguments=given,
    )
    explicit_target: bool = any(
        token in {"--url", "--workspace"}
        or token.startswith(("--url=", "--workspace="))
        for token in given
    )
    if explicit_target:
        configured: list[str] = list(resolved[: len(resolved) - len(given)])
        if "--actions" in configured:
            index: int = configured.index("--actions")
            del configured[index : index + 2]
        resolved = (*configured, *given)
    options: Namespace = parser.parse_args(args=resolved)
    options.workers_explicit = any(
        argument == "--workers" or argument.startswith("--workers=")
        for argument in given
    )
    if options.actions and (options.workspace or options.url):
        parser.error(
            message="Use --actions separately from --workspace/--url.",
        )
    if not options.url and (not options.workspace) and (not options.actions):
        parser.error(message="Provide --actions, --workspace or --url.")
    if options.workers <= 0:
        parser.error(message="Workflow workers must be positive.")
    if (
        min(options.width, options.height, options.scale, options.timeout_ms)
        <= 0
    ):
        parser.error(message="Viewport, scale and timeout must be positive.")
    return options


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
        trace(step=(f"frontend: arguments — root {root}, output {output_dir}"))
        trace(step="frontend: run start")
        if options.actions is not None:
            _ = activate_exactus_tool_bundle(root=root)
            actions: ModuleType = import_module(
                name="exactus.tools.actions.runner",
            )
            specification: Path = cast(
                typ="Path",
                val=options.actions,
            ).resolve()
            recipe: dict[str, JsonValue] = actions.load_actions(
                path=specification,
            )
            recipe_actions: JsonValue = recipe.get("actions")
            if isinstance(recipe_actions, list):
                for action in recipe_actions:
                    if (
                        isinstance(action, dict)
                        and action.get("tool") == "frontend.run"
                    ):
                        arguments_value: JsonValue = action.get("arguments")
                        if isinstance(arguments_value, dict):
                            action_arguments: dict[str, JsonValue] = (
                                arguments_value
                            )
                            worker_count: int = cast(
                                typ="int",
                                val=options.workers,
                            )
                            if options.workers_explicit:
                                action_arguments["workers"] = worker_count
                            else:
                                _ = action_arguments.setdefault(
                                    "workers",
                                    worker_count,
                                )
            observer: FrontendProgress = FrontendProgress(
                actions=len(recipe_actions)
                if isinstance(recipe_actions, list)
                else 1,
            )
            outcome: dict[str, JsonValue] = actions.run_actions(
                specification=recipe,
                root=specification.parent,
                output=output_dir,
                emit=observer,
            )
            status: int = int(outcome["status"] != "succeeded")
            trace(step=f"frontend: run finished — status {status}")
            return status
        result: FrontendExactusResult = frontend(
            inputs=FrontendExactusInput(
                url=cast(typ="str", val=options.url),
                output=output_dir,
                workspace=options.workspace,
                flow_id=options.flow,
                timeout_ms=options.timeout_ms,
                width=cast(typ="int", val=options.width),
                height=cast(typ="int", val=options.height),
                scale=cast(typ="float", val=options.scale),
                headless=not cast(typ="bool", val=options.headed),
                server_log=cast(typ="Path | None", val=options.server_log),
                emit=FrontendProgress(),
                workers=options.workers,
            ),
        )
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output_dir / "result.md",
                json=output_dir / "result.json",
                web=output_dir / "result_web",
            ),
            analyzer="frontend",
            title="Frontend Exactus",
            markdown=markdown_report(result=result),
            data={
                **report_data(result=result),
                "project_root": str(object=root),
            },
        )
        status = int(bool(result.findings))
        trace(step=f"frontend: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(analyzer="frontend", title="Frontend Exactus", main=main),
    )
