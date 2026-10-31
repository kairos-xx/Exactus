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
        "__init__.py": '"""Demonstration package for group_final."""\n',
        "app.py": (
            dedent(
                text=(
                    '    """Demonstration module containing Final constant'
                    's."""\n    \n    from typing import Final\n    \n    '
                    '\n    def make_name() -> str:\n        """Build a dem'
                    'onstration value."""\n        return "Exactus"\n    '
                    "\n    \n    NAME: Final[str] = make_name()\n    COUNT"
                    ": Final[int] = 3\n    \n    \n    def describe() -> s"
                    'tr:\n        """Return text that references both cons'
                    'tants."""\n        return f"{NAME}: {COUNT}"\n    '
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
