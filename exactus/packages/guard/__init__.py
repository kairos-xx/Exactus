# Copyright (c) 2026 João Lopes.
"""Public API for process_guard."""

from pathlib import Path
from sys import path as import_paths

import_paths.append(str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.guard.guard import ProcessGuard
from exactus.packages.guard.model import (
    CleanupResult,
    ProcessIdentity,
    ProcessRecord,
)
from exactus.packages.guard.supervisor import (
    ProcessSupervisor,
    SupervisionResult,
)

__all__: tuple[str, ...] = (
    "CleanupResult",
    "ProcessGuard",
    "ProcessIdentity",
    "ProcessRecord",
    "ProcessSupervisor",
    "SupervisionResult",
)
