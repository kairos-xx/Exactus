# Copyright (c) 2026
"""Re-execute project scripts with the repository virtual environment."""

from __future__ import annotations

from importlib import import_module
from multiprocessing import parent_process
from pathlib import Path
from shutil import which
from sys import argv, prefix
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable


def _project_root() -> Path:
    """Locate the project root by searching upward for ``.venv``.

    Returns:
        Nearest ancestor containing ``.venv``, or this package's
        grandparent when no virtual environment exists.

    """
    resolved: Path = Path(__file__).resolve()
    for candidate in resolved.parents:
        if (candidate / ".venv").is_dir():
            return candidate
    return resolved.parents[1]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        project_root: Grouped module constant.

    """

    project_root: Final[Path] = _project_root()


def switch_to_project_venv() -> None:
    """Replace the current interpreter with ``.venv`` when available.

    The method is intentionally safe to call at the beginning of every
    project script. It returns immediately when no local virtual environment
    exists or when the process already runs inside that environment. A
    successful process replacement preserves the original path and arguments.

    """
    # Multiprocessing children never own an entrypoint: ``sys.argv`` is the
    # parent's vector (with ``argv[0]`` rewritten to the parent's ``__main__``
    # under spawn), so ``execv`` would replace the worker with an unrelated
    # program. The spawning process already picked the interpreter.
    if parent_process() is not None:
        return
    environment: Path = Constants.project_root / ".venv"
    relative: Path = (
        Path("Scripts/python.exe")
        if import_module(name="os").name == "nt"
        else Path("bin/python")
    )
    interpreter: Path = environment / relative
    if (
        not interpreter.is_file()
        or Path(prefix).resolve() == environment.resolve()
    ):
        return
    # Interpreter invocations without a script path cannot be replaced:
    # ``execv`` would hand ``argv[0]`` to the child as a file to open.
    if not argv or argv[0] in {"", "-", "-c"}:
        return
    program: Path = Path(argv[0])
    if not program.exists():
        resolved_program: str | None = which(cmd=argv[0])
        if resolved_program is None:
            return
        program = Path(resolved_program)
    exec_process: Callable[[str, list[str]], None] = cast(
        typ="Callable[[str, list[str]], None]",
        val=vars(import_module(name="os"))["execv"],
    )
    exec_process(
        str(object=interpreter),
        [str(object=interpreter), str(object=program), *argv[1:]],
    )
