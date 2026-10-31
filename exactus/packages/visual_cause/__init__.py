# Copyright (c) 2026
"""Causal CSS visual-difference analysis."""

from pathlib import Path
from sys import path as import_paths

import_paths.append(str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.visual_cause.analyzer import (
    AnalysisResults,
    CssTarget,
    CssVisualCause,
    ProgressObserver,
    Settings,
    analyze,
)
from exactus.packages.visual_cause.dom_diff import (
    ComparisonReport as DomDiffComparisonReport,
)
from exactus.packages.visual_cause.dom_diff import (
    DiffRegion,
    DomElement,
    ElementMatch,
    VisualDomDiff,
)
from exactus.packages.visual_cause.dom_diff import Settings as DomDiffSettings

__all__: tuple[str, ...] = (
    "AnalysisResults",
    "CssTarget",
    "CssVisualCause",
    "DiffRegion",
    "DomDiffComparisonReport",
    "DomDiffSettings",
    "DomElement",
    "ElementMatch",
    "ProgressObserver",
    "Settings",
    "VisualDomDiff",
    "analyze",
)
