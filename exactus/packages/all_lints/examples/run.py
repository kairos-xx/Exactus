#!/usr/bin/env python3
# Copyright (c) 2026
"""Demonstrate ignore merging and report building on a scratch project.

Each run rebuilds a tiny project under the git-ignored ``.scratch/``
folder: a ``pyproject.toml`` carrying ``[tool.ruff]`` and
``[tool.basedpyright]`` ignore settings and one Python file. The example
prints the merged per-tool exclude patterns, shows the single-file
command lines the audit would launch, and writes a synthetic aggregate
report — no real linters are invoked, so the example runs offline every
time.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from importlib import import_module
from json import dumps
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from sys import stdout
from textwrap import dedent
from typing import TYPE_CHECKING, ClassVar, TextIO, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.all_lints import (
    Cli,
    Configuration,
    Diagnostic,
    FileResult,
    ReportBuilder,
    ToolResult,
)

if TYPE_CHECKING:
    from exactus.packages.all_lints.core import JsonObject


@final
class Constants:
    """Collect shared example paths and the scratch pyproject text.

    Attributes:
        here: Directory containing this example.
        work: Scratch project root recreated per run.
        pyproject: Scratch pyproject content with tool exclusions.

    """

    here: ClassVar[Path] = Path(__file__).resolve().parent
    work: ClassVar[Path] = here / ".scratch" / "demo_project"
    pyproject: ClassVar[str] = dedent(
        text=(
            '    [tool.ruff]\n    extend-exclude = ["fixtures", "generated"]\n'
            '    \n    [tool.basedpyright]\n    exclude = ["**/stubs"]\n    '
        ),
    )


def _print(*args: str, file: TextIO = stdout) -> None:
    """Print and immediately flush a script message.

    Args:
        *args: Values to print.
        file: Stream receiving the message.

    """
    _ = file.write(" ".join(str(object=arg) for arg in args) + "\n")
    _ = file.flush()


def _seed() -> None:
    """Recreate the scratch project and its pyproject configuration."""
    if Constants.work.parent.exists():
        rmtree(path=Constants.work.parent)
    Constants.work.mkdir(parents=True)
    (Constants.work / "pyproject.toml").write_text(
        data=Constants.pyproject,
        encoding="utf-8",
    )
    (Constants.work / "app.py").write_text(
        data=dedent(
            text=(
                '\n        """Demonstration module for the all_lints example."'
                '""\n\n        x = 1\n        '
            ),
        ),
        encoding="utf-8",
    )


def main() -> int:
    """Print merged excludes, tool commands, and a sample report.

    Returns:
        Zero after the demonstration completes.

    """
    _seed()
    _ = _print(f"scratch project: {Constants.work}\n\n")
    configuration: Configuration = Configuration(root=Constants.work)
    for tool in ("ruff", "basedpyright"):
        _ = _print(f"merged {tool} excludes:\n")
        for pattern in configuration.excludes(tool=tool):
            _ = _print(f"  {pattern}\n")
    _ = _print("\ncommands for app.py:\n")
    file: Path = Path("app.py")
    for spec in Cli.specs():
        _ = _print(f"  {spec.name}: {' '.join(spec.command(file=file))}\n")
    diagnostic: Diagnostic = Diagnostic(
        tool="ruff",
        file="app.py",
        line=1,
        column=1,
        end_line=1,
        end_column=4,
        severity="error",
        code="E225",
        message="missing whitespace around operator",
    )
    result: ToolResult = ToolResult(
        name="ruff",
        status="failed",
        duration_seconds=0.01,
        total_files=1,
        completed_files=1,
        diagnostics=[diagnostic],
        files=[
            FileResult(
                file="app.py",
                command=["ruff", "check", "app.py"],
                status="failed",
                exit_code=1,
                duration_seconds=0.01,
                diagnostics=[diagnostic],
                stdout="",
                stderr="",
            ),
        ],
    )
    report: JsonObject = ReportBuilder.build(
        root=Constants.work,
        started_at=datetime.now(tz=UTC).astimezone(),
        duration_seconds=0.01,
        results=[result],
    )
    _ = _print(f"\nreport:\n{dumps(obj=report, indent=2)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
