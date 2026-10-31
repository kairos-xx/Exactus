# Copyright (c) 2026 João Lopes.
"""Strong immutable data model for meaningful analysis runs."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from exactus.packages.meaningful.analyzer import (
    Category,
    Metrics,
    UnitTestLevel,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionThresholds:
    """Thresholds required to cross each adjacent test level.

    Attributes:
        test_0_to_1: Stored ``test_0_to_1`` value.
        test_1_to_2: Stored ``test_1_to_2`` value.
        test_2_to_3: Stored ``test_2_to_3`` value.

    """

    test_0_to_1: float = 0.25
    test_1_to_2: float = 0.50
    test_2_to_3: float = 0.70

    def __post_init__(self) -> None:
        """Validate normalized threshold values.

        Raises:
            ValueError: If the operation cannot be completed.

        """
        for name, value in (
            ("test_0_to_1", self.test_0_to_1),
            ("test_1_to_2", self.test_1_to_2),
            ("test_2_to_3", self.test_2_to_3),
        ):
            if not 0.0 <= value <= 1.0:
                msg: str = f"{name} must be between 0 and 1"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureWeights:
    """Relative importance of measured semantic features.

    Attributes:
        behavior: Stored ``behavior`` value.
        public_surface: Stored ``public_surface`` value.
        side_effects: Stored ``side_effects`` value.
        mutations: Stored ``mutations`` value.
        decisions: Stored ``decisions`` value.
        errors: Stored ``errors`` value.
        computations: Stored ``computations`` value.
        size: Stored ``size`` value.
        nesting: Stored ``nesting`` value.

    """

    behavior: float = 1.0
    public_surface: float = 1.1
    side_effects: float = 1.4
    mutations: float = 1.3
    decisions: float = 1.2
    errors: float = 1.3
    computations: float = 0.8
    size: float = 0.9
    nesting: float = 1.0


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureCaps:
    """Saturation caps used to normalize raw measurements.

    Attributes:
        behavioral_statements: Stored ``behavioral_statements`` value.
        public_members: Stored ``public_members`` value.
        side_effects: Stored ``side_effects`` value.
        mutations: Stored ``mutations`` value.
        decisions: Stored ``decisions`` value.
        errors: Stored ``errors`` value.
        computations: Stored ``computations`` value.
        source_lines: Stored ``source_lines`` value.
        nesting: Stored ``nesting`` value.

    """

    behavioral_statements: int = 30
    public_members: int = 10
    side_effects: int = 5
    mutations: int = 5
    decisions: int = 12
    errors: int = 5
    computations: int = 40
    source_lines: int = 300
    nesting: int = 5


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionFloors:
    """Minimum risk scores for semantically important behavior.

    Attributes:
        side_effect_test_1_to_2: Stored ``side_effect_test_1_to_2`` value.
        mutation_test_1_to_2: Stored ``mutation_test_1_to_2`` value.
        error_test_1_to_2: Stored ``error_test_1_to_2`` value.
        import_runtime_test_1_to_2: Minimum import-runtime promotion score.
        high_complexity_test_2_to_3: Minimum complex-behavior promotion score.

    """

    side_effect_test_1_to_2: float = 0.70
    mutation_test_1_to_2: float = 0.65
    error_test_1_to_2: float = 0.70
    import_runtime_test_1_to_2: float = 0.65
    high_complexity_test_2_to_3: float = 0.75


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationPolicy:
    """Complete policy controlling semantic promotion decisions.

    Attributes:
        thresholds: Stored ``thresholds`` value.
        weights: Stored ``weights`` value.
        caps: Stored ``caps`` value.
        floors: Stored ``floors`` value.
        evidence_context: Stored ``evidence_context`` value.

    """

    thresholds: PromotionThresholds = field(
        default_factory=PromotionThresholds,
    )
    weights: FeatureWeights = field(default_factory=FeatureWeights)
    caps: FeatureCaps = field(default_factory=FeatureCaps)
    floors: PromotionFloors = field(default_factory=PromotionFloors)
    evidence_context: int = 2

    def __post_init__(self) -> None:
        """Validate policy values.

        Raises:
            ValueError: If the operation cannot be completed.

        """
        if self.evidence_context < 0:
            msg: str = "evidence_context must be at least 0"
            raise ValueError(msg)
        numeric_values: tuple[float, ...] = (
            tuple(vars(self.weights).values())
            if hasattr(self.weights, "__dict__")
            else (
                self.weights.behavior,
                self.weights.public_surface,
                self.weights.side_effects,
                self.weights.mutations,
                self.weights.decisions,
                self.weights.errors,
                self.weights.computations,
                self.weights.size,
                self.weights.nesting,
            )
        )
        if any(value < 0.0 for value in numeric_values):
            msg = "feature weights must be non-negative"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class PromotionScores:
    """Normalized evidence available at each promotion boundary.

    Attributes:
        test_0_to_1: Stored ``test_0_to_1`` value.
        test_1_to_2: Stored ``test_1_to_2`` value.
        test_2_to_3: Stored ``test_2_to_3`` value.

    """

    test_0_to_1: float
    test_1_to_2: float
    test_2_to_3: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceLine:
    """One source line included in evidence.

    Attributes:
        line: Stored ``line`` value.
        text: Stored ``text`` value.
        highlighted: Stored ``highlighted`` value.

    """

    line: int
    text: str
    highlighted: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class FindingEvidence:
    """Source-backed evidence supporting the final classification level.

    Attributes:
        id: Stable evidence identifier used by decision nodes.
        category: Stored ``category`` value.
        reason: Stored ``reason`` value.
        line: Stored ``line`` value.
        end_line: Stored ``end_line`` value.
        context_start_line: Stored ``context_start_line`` value.
        context_end_line: Stored ``context_end_line`` value.
        source: Stored ``source`` value.

    """

    id: str
    category: str
    reason: str
    line: int
    end_line: int
    context_start_line: int
    context_end_line: int
    source: tuple[SourceLine, ...]


class AnalysisStage(StrEnum):
    """Observable stages of one progressive file decision.

    Attributes:
        FILE_STARTED: Worker accepted the file.
        FAST_SCAN: Semantic metrics and promotion scores are available.
        EVIDENCE: Source-backed evidence has been collected.
        DECISION: Final keep/filter decision is available.
        FILE_FAILED: File analysis failed.

    """

    FILE_STARTED = "file_started"
    FAST_SCAN = "fast_scan"
    EVIDENCE = "evidence"
    DECISION = "decision"
    FILE_FAILED = "file_failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionNode:
    """One auditable rule application in the actual decision path.

    Attributes:
        rule: Stable rule identifier.
        question: Human-readable decision question.
        outcome: Whether the rule promoted or accepted the condition.
        score: Score evaluated by the rule.
        threshold: Threshold applied by the rule.
        level_before: Level before this decision.
        level_after: Level after this decision.
        evidence_ids: Evidence records supporting this node.

    """

    rule: str
    question: str
    outcome: bool
    score: float
    threshold: float
    level_before: UnitTestLevel
    level_after: UnitTestLevel
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FileMetadata:
    """Execution and source metadata for one analyzed file.

    Attributes:
        size_bytes: Stored ``size_bytes`` value.
        source_lines: Stored ``source_lines`` value.
        started_at: Stored ``started_at`` value.
        finished_at: Stored ``finished_at`` value.
        duration_seconds: Stored ``duration_seconds`` value.
        worker_name: Stored ``worker_name`` value.

    """

    size_bytes: int
    source_lines: int
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    worker_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FileFinding:
    """Complete strongly typed finding for one Python source file.

    Attributes:
        path: Stored ``path`` value.
        level: Stored ``level`` value.
        category: Stored ``category`` value.
        scores: Stored ``scores`` value.
        should_be_visited: Whether an unreached source must remain actionable.
        decision_tree: Actual promotion decisions used to reach ``level``.
        reasons: Stored ``reasons`` value.
        metrics: Stored ``metrics`` value.
        evidence: Stored ``evidence`` value.
        metadata: Stored ``metadata`` value.

    """

    path: Path
    level: UnitTestLevel
    category: Category
    scores: PromotionScores
    should_be_visited: bool
    decision_tree: tuple[DecisionNode, ...]
    reasons: tuple[str, ...]
    metrics: Metrics
    evidence: tuple[FindingEvidence, ...]
    metadata: FileMetadata


@dataclass(frozen=True, slots=True, kw_only=True)
class FileFailure:
    """Failure produced by one completed analysis worker.

    Attributes:
        path: Stored ``path`` value.
        error_type: Stored ``error_type`` value.
        message: Stored ``message`` value.
        duration_seconds: Stored ``duration_seconds`` value.

    """

    path: Path
    error_type: str
    message: str
    duration_seconds: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressSnapshot:
    """Immutable progress state emitted after every finished worker.

    Attributes:
        total: Stored ``total`` value.
        completed: Stored ``completed`` value.
        succeeded: Stored ``succeeded`` value.
        kept: Sources that should be visited.
        filtered: Sources allowed to remain unreached.
        failed: Stored ``failed`` value.
        remaining: Stored ``remaining`` value.
        percent: Stored ``percent`` value.
        current_path: Stored ``current_path`` value.
        current_level: Stored ``current_level`` value.
        stage: Current analysis stage.
        evidence_count: Evidence records collected for the current file.
        elapsed_seconds: Stored ``elapsed_seconds`` value.
        files_per_second: Stored ``files_per_second`` value.
        estimated_remaining_seconds: Estimated seconds until completion.

    """

    total: int
    completed: int
    succeeded: int
    kept: int
    filtered: int
    failed: int
    remaining: int
    percent: float
    current_path: Path
    current_level: UnitTestLevel | None
    stage: AnalysisStage
    evidence_count: int
    elapsed_seconds: float
    files_per_second: float
    estimated_remaining_seconds: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RunMetadata:
    """Aggregate metadata describing a complete analysis run.

    Attributes:
        started_at: Stored ``started_at`` value.
        finished_at: Stored ``finished_at`` value.
        duration_seconds: Stored ``duration_seconds`` value.
        resolution_seconds: Stored ``resolution_seconds`` value.
        analysis_seconds: Stored ``analysis_seconds`` value.
        requested_workers: Stored ``requested_workers`` value.
        workers_used: Stored ``workers_used`` value.
        total_files: Stored ``total_files`` value.
        succeeded: Stored ``succeeded`` value.
        failed: Stored ``failed`` value.
        kept: Sources requiring test reachability.
        filtered: Sources safely removed from unreached findings.
        total_bytes: Stored ``total_bytes`` value.
        total_source_lines: Stored ``total_source_lines`` value.
        test_0: Stored ``test_0`` value.
        test_1: Stored ``test_1`` value.
        test_2: Stored ``test_2`` value.
        test_3: Stored ``test_3`` value.
        python_version: Stored ``python_version`` value.
        platform: Stored ``platform`` value.
        working_directory: Stored ``working_directory`` value.

    """

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    resolution_seconds: float
    analysis_seconds: float
    requested_workers: int | None
    workers_used: int
    total_files: int
    succeeded: int
    failed: int
    kept: int
    filtered: int
    total_bytes: int
    total_source_lines: int
    test_0: int
    test_1: int
    test_2: int
    test_3: int
    python_version: str
    platform: str
    working_directory: Path


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressState:
    """Inputs required to derive one progress snapshot.

    Attributes:
        total: Total scheduled files.
        completed: Completed worker count.
        succeeded: Successful worker count.
        kept: Actionable decisions completed so far.
        filtered: Non-actionable decisions completed so far.
        failed: Failed worker count.
        current_path: Most recently active path.
        current_level: Classification of the current path.
        stage: Current analysis lifecycle stage.
        evidence_count: Evidence records collected for the current path.
        started: Monotonic analysis start timestamp.

    """

    total: int
    completed: int
    succeeded: int
    kept: int
    filtered: int
    failed: int
    current_path: Path
    current_level: UnitTestLevel | None
    stage: AnalysisStage
    evidence_count: int
    started: float


@dataclass(frozen=True, slots=True, kw_only=True)
class RunTiming:
    """Timing and worker inputs used to aggregate run metadata.

    Attributes:
        started_at: UTC run start.
        finished_at: UTC run completion.
        duration_seconds: Complete wall-clock duration.
        resolution_seconds: Selector-resolution duration.
        analysis_seconds: Parallel-analysis duration.
        requested_workers: Explicit worker request when supplied.
        workers_used: Effective worker count.

    """

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    resolution_seconds: float
    analysis_seconds: float
    requested_workers: int | None
    workers_used: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalysisRun:
    """Complete result of one Python API analysis invocation.

    Attributes:
        findings: Stored ``findings`` value.
        failures: Stored ``failures`` value.
        metadata: Stored ``metadata`` value.

    """

    findings: tuple[FileFinding, ...]
    failures: tuple[FileFailure, ...]
    metadata: RunMetadata

    @property
    def should_be_visited(self) -> tuple[FileFinding, ...]:
        """Return unreached sources that must remain actionable.

        Returns:
            Findings that tests should visit.

        """
        return tuple(
            finding for finding in self.findings if finding.should_be_visited
        )

    @property
    def filtered(self) -> tuple[FileFinding, ...]:
        """Return unreached sources safely filtered from coverage findings.

        Returns:
            Findings that may remain unreached.

        """
        return tuple(
            finding
            for finding in self.findings
            if not finding.should_be_visited
        )


type ProgressCallback = Callable[[ProgressSnapshot], None]
