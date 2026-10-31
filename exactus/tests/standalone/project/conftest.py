"""Make the fixture project's ``python`` package importable in tests."""

from __future__ import annotations

from pathlib import Path
from sys import path as sys_path

_root: Path = Path(__file__).resolve().parent
if str(object=_root) not in sys_path:
    sys_path.insert(0, str(object=_root))
