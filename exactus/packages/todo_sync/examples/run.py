#!/usr/bin/env python3
# Copyright (c) 2026 Project contributors
"""Synchronize a throwaway copy of the bundled ``TODO.md`` example.

The demo duplicates the checked-in checklist into the git-ignored
``.scratch/`` folder and runs the real synchronizer against the copy,
which rewrites the managed dashboard block and emits the standalone
``TODO.html`` dashboard beside it. The bundled source stays pristine.
"""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import copy2
from sys import path as sys_path
from sys import stdout
from typing import Final, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.todo_sync import completion, synchronize


@final
class Constants:
    """Group module-level constants.

    Attributes:
        here: Grouped module constant.
        source: Grouped module constant.
        scratch: Grouped module constant.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    source: Final[Path] = here / "TODO.md"
    scratch: Final[Path] = here / ".scratch"


def main(*, scratch: Path | None = None) -> int:
    """Copy the example checklist and synchronize the copy.

    Args:
        scratch: Artifact directory overriding the default
            ``.scratch/`` — tests pass a temporary directory to stay
            hermetic.

    Returns:
        ``0`` after the copy's Markdown and HTML dashboards are written.

    """
    workspace: Path = scratch or Constants.scratch
    workspace.mkdir(parents=True, exist_ok=True)
    target: Path = workspace / "TODO.md"
    _ = copy2(src=Constants.source, dst=target)
    changed: bool = synchronize(path=target)
    html: Path = target.with_suffix(suffix=".html")
    percent: float = completion(text=target.read_text(encoding="utf-8"))
    _ = stdout.write(
        f"sync      {target.name}: {'updated' if changed else 'in sync'}\n"
        f"dashboard {html.name}: {html.stat().st_size} bytes\n"
        f"complete  {percent:.1f}%\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
