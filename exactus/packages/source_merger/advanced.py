"""Compatibility exports for the earlier tracked source-merger path."""

from exactus.packages.source_merger.engine import (
    SourceMerger,
    TrackedSourceMerger,
)
from exactus.packages.source_merger.model import (
    AppliedChange,
    MergeConflict,
    MergeResult,
    SymbolMatch,
)

__all__: list[str] = [
    "AppliedChange",
    "MergeConflict",
    "MergeResult",
    "SourceMerger",
    "SymbolMatch",
    "TrackedSourceMerger",
]
