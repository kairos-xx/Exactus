"""Conflict-aware concurrent source reconciliation for.

Conflict-aware concurrent source reconciliation for Python, JS, HTML and CSS.
"""

from exactus.packages.source_merger.cache import CacheStats, SnapshotCache
from exactus.packages.source_merger.delta import (
    DeltaMetrics,
    DeltaPolicy,
    measure,
)
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
    "CacheStats",
    "DeltaMetrics",
    "DeltaPolicy",
    "MergeConflict",
    "MergeResult",
    "SnapshotCache",
    "SourceMerger",
    "SymbolMatch",
    "TrackedSourceMerger",
    "measure",
]
