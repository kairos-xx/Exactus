#!/usr/bin/env python3
# Copyright (c) 2026
"""Run the combined lint exactus and emit the LINTS report bundle."""

from __future__ import annotations

from os import environ
from pathlib import Path
from sys import path as sys_path
from sys import stderr, stdout
from typing import TYPE_CHECKING, cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.common.execution import run_exactus
from exactus.tools.lints.arguments import create_parser as _create_parser

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Mapping

    from exactus.tools.lints.shebang import (
        ExecWithoutShebang,
        ShebangWithoutExec,
    )
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import ExactusCommonTables, resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.registry import RegistryTables
from exactus.tools.common.snippets import with_excerpts
from exactus.tools.common.sprint import sprint
from exactus.tools.lints.core import (
    JsonValue,
    LintExactus,
    LintExactusConfig,
    LintExactusRequest,
)
from exactus.tools.lints.report import report_data
from exactus.tools.lints.shebang import ShebangSettings
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

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
            tool="lints",
            parser=parser,
            arguments=arguments,
        ),
    )


def _exit_status(report: Mapping[str, JsonValue], status: int) -> int:
    """Combine the workflow status with per-tool exit codes and findings.

    Args:
        report: Normalized lint report payload.
        status: Guarded-inference status.

    Returns:
        Nonzero when inference rolled back, an executed tool failed, or any
        finding was reported.

    """
    tools: JsonValue = report.get("tools", {})
    failed: bool = isinstance(tools, dict) and any(
        isinstance(entry, dict)
        and (not entry.get("skipped"))
        and isinstance(entry.get("returncode"), int)
        and (entry.get("returncode") != 0)
        for entry in tools.values()
    )
    findings: JsonValue = report.get("findings")
    has_findings: bool = isinstance(findings, list) and bool(findings)
    return status or int(failed) or int(has_findings)


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Return main.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    options: Namespace = parse_args(arguments=arguments)
    runtime_max_runs: int | None = cast(
        typ="int | None",
        val=options.runtime_max_runs,
    )
    if runtime_max_runs is not None:
        environ[RegistryTables.max_runs_env] = str(object=runtime_max_runs)
    runtime_max_size: int | None = cast(
        typ="int | None",
        val=options.runtime_max_size,
    )
    if runtime_max_size is not None:
        environ[RegistryTables.max_size_env] = str(object=runtime_max_size)
    root: Path = cast(typ="Path", val=options.root).resolve()
    output_dir: Path = resolve_output(
        root=root,
        output=cast(typ="Path", val=options.output_dir),
    )
    includes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.include),
    )
    excludes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.exclude),
    )
    dry: bool = cast(typ="bool", val=options.dry)
    config: LintExactusConfig = LintExactusConfig(
        clean=not (dry or cast(typ="bool", val=options.no_clean)),
        fix=not (dry or cast(typ="bool", val=options.no_fix)),
        long_lines=not cast(typ="bool", val=options.no_long_lines),
        delimiters=not cast(typ="bool", val=options.no_delimiters),
        notation=not cast(typ="bool", val=options.no_notation),
        infer=not (dry or cast(typ="bool", val=options.no_infer)),
        install_tools=not (
            dry or cast(typ="bool", val=options.no_install_tools)
        ),
        group_final=not cast(typ="bool", val=options.no_group_final),
        organize=not cast(typ="bool", val=options.no_organize),
        unsafe_fixes=not dry and cast(typ="bool", val=options.unsafe_fixes),
        workers=cast(typ="int | None", val=options.workers),
        shebang=ShebangSettings(
            heal=not (dry or cast(typ="bool", val=options.no_shebang_heal)),
            exec_no_shebang=cast(
                typ="ExecWithoutShebang",
                val=options.exec_no_shebang,
            ),
            shebang_no_exec=cast(
                typ="ShebangWithoutExec",
                val=options.shebang_no_exec,
            ),
        ),
        simple=cast(typ="bool", val=options.simple),
    )
    generated_ignores: tuple[str, ...] = ()
    output_parent: Path = output_dir.parent
    if (
        output_parent.name == "EXACTUS_RESULTS"
        and output_parent.is_relative_to(root)
    ):
        output_relative: str = output_parent.relative_to(root).as_posix()
        generated_ignores = (output_relative, f"{output_relative}/**")
    with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
        try:
            trace(
                step=f"lints: arguments — root {root}, output {output_dir}",
                depth=0,
            )
            report, status = LintExactus.run(
                request=LintExactusRequest(
                    cwd=root,
                    targets=includes or (".",),
                    report_path=output_dir / "LINTS.json",
                    ignores=(
                        *excludes,
                        *ExactusCommonTables.DEFAULT_EXCLUDES,
                        *generated_ignores,
                    ),
                    bare_import_exceptions=tuple(
                        cast(
                            typ="list[str]",
                            val=options.bare_import_exception,
                        ),
                    ),
                    config=config,
                    css_context_words=tuple(
                        cast(typ="list[str]", val=options.css_context_word),
                    ),
                    writer=stdout,
                    toolchain=cast(typ="Path | None", val=options.toolchain),
                    tool_args={
                        tool: tuple(
                            cast(
                                typ="list[str]",
                                val=getattr(options, f"{tool}_arg"),
                            ),
                        )
                        for tool in ("ruff", "basedpyright", "pyrefly")
                    },
                ),
            )
            trace(step="lints: write report bundle", depth=0)
            _ = ReportBundle.write(
                paths=ReportPaths(
                    markdown=output_dir / "LINTS.md",
                    json=output_dir / "LINTS.json",
                    web=output_dir / "LINTS_web",
                ),
                analyzer="lints",
                title="Lint Exactus",
                markdown="",
                data=with_excerpts(
                    payload=report_data(report=report, root=root),
                    root=root,
                    context=cast(typ="int", val=options.context_lines),
                ),
            )
            trace(step="lints: wrote LINTS.md, LINTS.json, LINTS_web", depth=1)
            exit_status: int = _exit_status(report=report, status=status)
            trace(step=f"lints: finished — exit status {exit_status}", depth=0)
        except RuntimeError as error:
            trace(step=f"lints: failed — {error}", depth=0)
            sprint(f"error: {error}", file=stderr)
            return 1
    return exit_status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(analyzer="lints", title="Lints Exactus", main=main),
    )
