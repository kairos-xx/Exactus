#!/usr/bin/env python3
# Copyright (c) 2026
"""Rename a throwaway copy of ``project`` with ``rename_project``.

The checked-in ``project/`` template is never modified: each run
copies it into the git-ignored ``.scratch/`` folder and renames the copy
to ``demo_app``, so a pristine example project is always ready to show.
"""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import copytree, rmtree
from sys import modules, stdout
from sys import path as sys_path
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()


@final
class Constants:
    """Group module-level constants.

    Attributes:
        here: Grouped module constant.
        template: Grouped module constant.
        work: Grouped module constant.
        new_name: Grouped module constant.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    template: Final[Path] = here / "project"
    work: Final[Path] = here / ".scratch"
    new_name: Final[str] = "demo_app"


def main() -> int:
    """Copy ``project`` and rename the copy to ``demo_app``.

    Returns:
        The ``rename_project`` exit status: ``0`` on success.

    """
    if Constants.work.exists():
        rmtree(path=Constants.work)
    Constants.work.mkdir(parents=True)
    copied: Path = Constants.work / Constants.template.name
    _ = copytree(src=Constants.template, dst=copied)
    _ = stdout.write(f"copied {Constants.template.name} -> {copied}\n\n")
    sys_path.insert(0, str(object=Constants.here.parent))
    sys_path.insert(
        0,
        str(object=Constants.here.parent.parent.parent.parent / "model"),
    )
    _ = modules.pop("rename_project", None)
    status: int = __import__(name="rename_project").main(
        arguments=(
            str(object=copied),
            "--name",
            Constants.new_name,
            "--yes",
            "--no-git",
            "--no-github",
            "--diff",
            "--boundary",
            "loose",
        ),
    )
    renamed: Path = Constants.work / Constants.new_name
    _ = stdout.write(
        f"\n{('renamed project:' if status == 0 else 'rename failed:')} "
        f"{renamed}\n",
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
