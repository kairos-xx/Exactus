"""Build and apply deterministic executable filesystem patches."""

from exactus.packages.patcher.cli import PatcherCli
from exactus.packages.patcher.core import (
    PatchResult,
    ProjectDelta,
    ProjectSnapshot,
    ProjectSource,
    PyzProjectPatch,
    resolve_invocation_root,
)
from exactus.packages.patcher.diff import DiffRenderer

__all__: tuple[str, ...] = (
    "DiffRenderer",
    "PatchResult",
    "PatcherCli",
    "ProjectDelta",
    "ProjectSnapshot",
    "ProjectSource",
    "PyzProjectPatch",
    "resolve_invocation_root",
)
