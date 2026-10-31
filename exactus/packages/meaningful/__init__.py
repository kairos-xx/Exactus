# Copyright (c) 2026 João Lopes.
"""Public API for meaningful Python test-necessity analysis."""

from pathlib import Path
from sys import path as import_paths

import_paths.append(str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.meaningful.analyzer import (
    Category,
    Metrics,
    UnitTestLevel,
)
from exactus.packages.meaningful.api import Meaningful, analyze, classify
from exactus.packages.meaningful.models import (
    AnalysisRun,
    AnalysisStage,
    DecisionNode,
    EvaluationPolicy,
    FeatureCaps,
    FeatureWeights,
    FileFailure,
    FileFinding,
    FileMetadata,
    FindingEvidence,
    ProgressCallback,
    ProgressSnapshot,
    PromotionFloors,
    PromotionScores,
    PromotionThresholds,
    RunMetadata,
    SourceLine,
)

__all__: tuple[str, ...] = (
    "AnalysisRun",
    "AnalysisStage",
    "Category",
    "DecisionNode",
    "EvaluationPolicy",
    "FeatureCaps",
    "FeatureWeights",
    "FileFailure",
    "FileFinding",
    "FileMetadata",
    "FindingEvidence",
    "Meaningful",
    "Metrics",
    "ProgressCallback",
    "ProgressSnapshot",
    "PromotionFloors",
    "PromotionScores",
    "PromotionThresholds",
    "RunMetadata",
    "SourceLine",
    "UnitTestLevel",
    "analyze",
    "classify",
)
