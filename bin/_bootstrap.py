# Copyright (c) 2026 Project contributors
"""Put the repository root on ``sys.path`` and switch to the project venv.

Importing this module makes ``bin/`` entry points runnable under any
interpreter: it first exposes the repository packages, then re-executes
the caller with ``.venv/bin/python`` when the current interpreter is not
already the project environment.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Constants:
    """Group module-level constants.

    Attributes:
        project_root: Grouped module constant.

    """

    project_root: Final[Path] = Path(__file__).resolve().parent.parent


if str(object=Constants.project_root) not in sys_path:
    sys_path.insert(0, str(object=Constants.project_root))
_switch: Callable[[], None] = cast(
    typ="Callable[[], None]",
    val=vars(import_module(name="exactus.packages.project_python"))[
        "switch_to_project_venv"
    ],
)
_switch()
