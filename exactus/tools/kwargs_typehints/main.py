#!/usr/bin/env python3
# Copyright (c) 2026
"""Exactus keyword usage, imports, and explicit type hints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, Final, Self, cast, final

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    match_path,
    resolve_output,
)
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.kwargs_typehints.arguments import (
    create_parser as _create_parser,
)
from exactus.tools.kwargs_typehints.core import main as core_main

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
_project_python_active: bool = _project_python_auto.Constants.activated


@final
class Constants:
    """Group module-level constants.

    Attributes:
        heuristics: Grouped module constant.

    """

    heuristics: Final[str] = "heuristics.json"


"File name of the builtin type-fuzz heuristics inside ``ARTIFACTS``."


@dataclass(frozen=True, slots=True)
class PathScope:
    """Include/exclude glob filter applied to discovered source files.

    Attributes:
        root: Project root the globs are relative to.
        includes: Globs a path must match, when any are given.
        excludes: Globs rejecting a path (the defaults always apply).

    """

    root: Path
    includes: tuple[str, ...]
    excludes: tuple[str, ...]

    def __call__(self: Self, path: Path) -> bool:
        """Return whether a discovered file is in scope.

        Args:
            path: Candidate source file.

        Returns:
            ``True`` when the path passes the include/exclude globs.

        """
        return match_path(
            path=path,
            root=self.root,
            includes=self.includes,
            excludes=self.excludes,
        )


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
            tool="kwargs_typehints",
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
    bare_import_args: tuple[str, ...] = tuple(
        argument
        for module in cast(typ="list[str]", val=options.allow_bare_import)
        for argument in ("--allow-bare-import", module)
    )
    with step_log(path=output_dir / "ARTIFACTS" / "steps.txt"):
        trace(
            step=(
                f"kwargs typehints: arguments — root {root}, "
                f"output {output_dir}"
            ),
        )
        trace(step="kwargs typehints: run start")
        status: int = core_main(
            arguments=(
                "--root",
                str(object=root),
                "--output",
                str(object=output_dir / "KWARGS_TYPEHINTS.md"),
                "--heuristics-output",
                str(object=output_dir / "ARTIFACTS" / Constants.heuristics),
                "--context-lines",
                str(object=cast(typ="int", val=options.context_lines)),
                *(
                    ("--strict",)
                    if cast(typ="bool", val=options.strict)
                    else ()
                ),
                *(("--dry-run",) if cast(typ="bool", val=options.dry) else ()),
                *(
                    ("--python", cast(typ="str", val=options.python))
                    if options.python
                    else ()
                ),
                *bare_import_args,
            ),
            path_filter=PathScope(
                root=root,
                includes=includes,
                excludes=excludes,
            ),
            includes=includes,
            excludes=(*excludes, *ExactusCommonTables.DEFAULT_EXCLUDES),
        )
        trace(step=f"kwargs typehints: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(
            analyzer="kwargs_typehints",
            title="Kwargs Typehints Exactus",
            main=main,
        ),
    )
