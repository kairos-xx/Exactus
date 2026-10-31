#!/usr/bin/env python3
# Copyright (c) 2026
"""Exactus Python docstrings and JavaScript JSDoc."""

from __future__ import annotations

from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, cast

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import match_path, resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.docs.arguments import create_parser as _create_parser
from exactus.tools.docs.core import (
    Config,
    Constants,
    DocumentationExactus,
    Language,
    Severity,
)

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
            tool="docs",
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
    output_dir.mkdir(parents=True, exist_ok=True)
    includes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.include),
    )
    excludes: tuple[str, ...] = tuple(
        cast(typ="list[str]", val=options.exclude),
    )
    language: str = cast(typ="str", val=options.language)
    fail_on: str = cast(typ="str", val=options.fail_on)
    config: Config = Config(
        root=root,
        markdown=output_dir / "DOCS.md",
        json_output=output_dir / "DOCS.json",
        languages=frozenset({"python", "javascript"})
        if language == "both"
        else frozenset({cast(typ="Language", val=language)}),
        exclude_dirs=Constants.exclude_dirs,
        exclude_hidden_dirs=True,
        public_only=cast(typ="bool", val=options.public_only),
        validate_javascript=not cast(typ="bool", val=options.no_js_check),
        fail_on=None
        if fail_on == "never"
        else cast(typ="Severity", val=fail_on),
        includes=includes,
        excludes=excludes,
        context_lines=cast(typ="int", val=options.context_lines),
    )
    exactus: DocumentationExactus = DocumentationExactus(
        config=config,
        file_filter=lambda path: match_path(
            path=path,
            root=root,
            includes=includes,
            excludes=excludes,
        ),
    )
    with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
        trace(
            step=(
                f"docs: arguments — root {root}, output {output_dir}, "
                f"language {language}, fail_on {fail_on}"
            ),
        )
        trace(step="docs: run start")
        status: int = exactus.run()
        trace(step=f"docs: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(analyzer="docs", title="Docs Exactus", main=main),
    )
