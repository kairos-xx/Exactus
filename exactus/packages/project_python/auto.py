"""Activate the repository virtual environment when this module is imported."""

from __future__ import annotations

from sys import modules
from typing import Final, final

from . import switch_to_project_venv

if "pytest" not in modules:
    switch_to_project_venv()


@final
class Constants:
    """Group module-level constants.

    Attributes:
        activated: Grouped module constant.

    """

    activated: Final[bool] = True
