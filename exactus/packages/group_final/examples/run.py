#!/usr/bin/env python3
"""Generate a demonstration project and run group_final against it."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import copytree, rmtree
from sys import path as sys_path
from tempfile import mkdtemp
from textwrap import dedent
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.group_final import FinalConstantsRefactor


@final
class Constants:
    """Group module-level constants.

    Attributes:
        sources: Grouped module constant.

    """

    sources: Final[dict[str, str]] = {
        "__init__.py": """\
\"""Demonstration package for group_final.\"""
""",
        "app.py": (
            dedent(
                text=(
                    """\
    \"""Demonstration module containing Final constants.\"""

    from typing import Final


    def make_name() -> str:
        \"""Build a demonstration value.\"""
        return "Exactus"


    NAME: Final[str] = make_name()
    COUNT: Final[int] = 3


    def describe() -> str:
        \"""Return text that references both constants.\"""
        return f"{NAME}: {COUNT}"
    """
                ),
            )
        ),
    }


def main() -> int:
    """Generate the demo project and run a dry-run demonstration.

    Returns:
        Process exit status.

    """
    source: Path = Path(__file__).parent / ".scratch" / "demo_project"
    source.mkdir(parents=True, exist_ok=True)
    for name, content in Constants.sources.items():
        _ = (source / name).write_text(data=content, encoding="utf-8")
    target: Path = Path(mkdtemp(prefix="group-final-example-")) / "project"
    copytree(src=source, dst=target)
    try:
        FinalConstantsRefactor(root=target, dry_run=True).run()
    finally:
        rmtree(path=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
