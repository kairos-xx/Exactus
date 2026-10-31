# Copyright (c) 2026 João Lopes.
"""Primary object-oriented Python API for meaningful analysis."""

from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from os import cpu_count, stat_result
from pathlib import Path
from platform import platform as platform_name
from sys import version as python_version
from threading import current_thread
from time import monotonic
from typing import NotRequired, TypedDict, Unpack

from exactus.packages.meaningful.analyzer import Metrics, UnitTestLevel
from exactus.packages.meaningful.engine import (
    EvidenceCollector,
    PolicyEvaluator,
    baseline_metrics,
    javascript_evidence,
    javascript_metrics,
)
from exactus.packages.meaningful.models import (
    AnalysisRun,
    AnalysisStage,
    DecisionNode,
    EvaluationPolicy,
    FileFailure,
    FileFinding,
    FileMetadata,
    FindingEvidence,
    ProgressCallback,
    ProgressSnapshot,
    ProgressState,
    PromotionScores,
    RunMetadata,
    RunTiming,
)

try:
    from exactus.packages.steps import trace
except ImportError:

    def trace(*, step: str, depth: int = 0) -> None:
        """Discard step events when the trace module is unavailable.

        Args:
            step: Step label, ignored.
            depth: Nesting depth, ignored.

        """
        del step, depth


try:
    from exactus.tools.common.cli import is_reports_tree
except ImportError:

    def is_reports_tree(*, directory: Path) -> bool:
        """Fingerprint an exactus report tree when vendored standalone.

        Mirrors ``exactus.tools.common.cli.is_reports_tree`` so this
        package can run without the ``exactus.tools`` namespace.

        Args:
            directory: Directory candidate to fingerprint.

        Returns:
            ``True`` when the directory is an exactus report tree.

        """
        if not directory.is_dir():
            return False
        return (
            (directory / ".runtime").is_dir()
            or (
                (directory / "result.json").is_file()
                and (directory / "result.md").is_file()
            )
            or (directory / "ARTIFACTS" / "@activity.json").is_file()
        )


type PathInput = str | Path
type PathInputs = PathInput | Sequence[PathInput]


class AnalyzeOptions(TypedDict):
    """Optional controls accepted by :meth:`Meaningful.analyze`.

    Attributes:
        include: Optional selector intersection.
        exclude: Optional selector subtraction.
        policy: Per-run evaluation policy.
        max_workers: Per-run worker limit.
        on_progress: Per-run progress observer.
        evidence_context: Per-run evidence context lines.

    """

    include: NotRequired[Sequence[PathInput]]
    exclude: NotRequired[Sequence[PathInput]]
    policy: NotRequired[EvaluationPolicy | None]
    max_workers: NotRequired[int | None]
    on_progress: NotRequired[ProgressCallback | None]
    evidence_context: NotRequired[int | None]


class Meaningful:
    """Resolve and analyze Python and JavaScript sources in bounded workers."""

    def __init__(
        self,
        *,
        policy: EvaluationPolicy | None = None,
        max_workers: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Configure a reusable analyzer.

        Args:
            policy: Value supplied for ``policy``.
            max_workers: Value supplied for ``max_workers``.
            on_progress: Value supplied for ``on_progress``.

        Raises:
            ValueError: If the operation cannot be completed.

        """
        if max_workers is not None and max_workers < 1:
            msg: str = "max_workers must be at least 1"
            raise ValueError(msg)
        self._policy: EvaluationPolicy = policy or EvaluationPolicy()
        self._max_workers: int | None = max_workers
        self._on_progress: ProgressCallback | None = on_progress

    @classmethod
    def resolve(
        cls,
        *,
        paths: PathInputs,
        include: Sequence[PathInput] = (),
        exclude: Sequence[PathInput] = (),
    ) -> tuple[Path, ...]:
        """Resolve selectors into a unique sorted tuple of Python files.

        Args:
            paths: Value supplied for ``paths``.
            include: Value supplied for ``include``.
            exclude: Value supplied for ``exclude``.

        Returns:
            The resulting value.

        """
        initial: frozenset[Path] = cls._expand_many(
            selectors=cls._normalize_inputs(paths=paths),
        )
        included: frozenset[Path] | None = (
            cls._expand_many(selectors=include) if include else None
        )
        excluded: frozenset[Path] = (
            cls._expand_many(selectors=exclude) if exclude else frozenset()
        )
        return tuple(
            sorted(
                (
                    path
                    for path in initial
                    if (included is None or path in included)
                    and path not in excluded
                ),
                key=str,
            ),
        )

    def analyze(
        self,
        *,
        paths: PathInputs,
        **options: Unpack[AnalyzeOptions],
    ) -> AnalysisRun:
        """Analyze selected files and return a complete immutable run model.

        Args:
            paths: File, directory, glob, or sequence of selectors.
            options: Typed per-run analysis options.

        Returns:
            Complete findings, failures, and run metadata.

        Raises:
            ValueError: If a worker limit is invalid.

        """
        include: Sequence[PathInput] = options.get("include", ())
        exclude: Sequence[PathInput] = options.get("exclude", ())
        policy: EvaluationPolicy | None = options.get("policy")
        max_workers: int | None = options.get("max_workers")
        on_progress: ProgressCallback | None = options.get("on_progress")
        evidence_context: int | None = options.get("evidence_context")
        started_at: datetime = datetime.now(tz=UTC)
        run_start: float = monotonic()
        resolution_start: float = monotonic()
        candidates: tuple[Path, ...] = self.resolve(
            paths=paths,
            include=include,
            exclude=exclude,
        )
        resolution_seconds: float = monotonic() - resolution_start
        trace(
            step=(
                f"meaningful: resolved {len(candidates)} candidates "
                f"in {resolution_seconds:.3f}s"
            ),
            depth=2,
        )
        selected_policy: EvaluationPolicy = policy or self._policy
        if evidence_context is not None:
            selected_policy = EvaluationPolicy(
                thresholds=selected_policy.thresholds,
                weights=selected_policy.weights,
                caps=selected_policy.caps,
                floors=selected_policy.floors,
                evidence_context=evidence_context,
            )
        requested_workers: int | None = (
            max_workers if max_workers is not None else self._max_workers
        )
        if requested_workers is not None and requested_workers < 1:
            msg: str = "max_workers must be at least 1"
            raise ValueError(msg)
        workers: int = min(
            len(candidates) or 1,
            requested_workers or min(32, (cpu_count() or 1) + 4),
        )
        trace(
            step=(
                f"meaningful: {workers} workers for {len(candidates)} files"
            ),
            depth=2,
        )
        callback: ProgressCallback | None = on_progress or self._on_progress
        analysis_start: float = monotonic()
        findings: list[FileFinding] = []
        failures: list[FileFailure] = []
        completed: int = 0
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="meaningful",
        ) as executor:
            futures: dict[Future[FileFinding | FileFailure], Path] = {
                executor.submit(
                    self._worker,
                    path=path,
                    policy=selected_policy,
                    callback=callback,
                    total=len(candidates),
                    analysis_started=analysis_start,
                ): path
                for path in candidates
            }
            for future in as_completed(fs=futures):
                path: Path = futures[future]
                level: UnitTestLevel | None = None
                outcome: FileFinding | FileFailure = future.result()
                if isinstance(outcome, FileFinding):
                    findings.append(outcome)
                    level = outcome.level
                else:
                    failures.append(outcome)
                completed += 1
                self._notify(
                    callback=callback,
                    snapshot=self._progress(
                        state=ProgressState(
                            total=len(candidates),
                            completed=completed,
                            succeeded=len(findings),
                            kept=sum(
                                finding.should_be_visited
                                for finding in findings
                            ),
                            filtered=sum(
                                not finding.should_be_visited
                                for finding in findings
                            ),
                            failed=len(failures),
                            current_path=path,
                            current_level=level,
                            stage=AnalysisStage.DECISION,
                            evidence_count=(
                                len(outcome.evidence)
                                if isinstance(outcome, FileFinding)
                                else 0
                            ),
                            started=analysis_start,
                        ),
                    ),
                )
        analysis_seconds: float = monotonic() - analysis_start
        trace(
            step=(
                f"meaningful: {len(findings)} findings, "
                f"{len(failures)} failures in "
                f"{analysis_seconds:.3f}s"
            ),
            depth=2,
        )
        finished_at: datetime = datetime.now(tz=UTC)
        ordered_findings: tuple[FileFinding, ...] = tuple(
            sorted(findings, key=lambda finding: str(object=finding.path)),
        )
        ordered_failures: tuple[FileFailure, ...] = tuple(
            sorted(failures, key=lambda failure: str(object=failure.path)),
        )
        return AnalysisRun(
            findings=ordered_findings,
            failures=ordered_failures,
            metadata=self._metadata(
                timing=RunTiming(
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=monotonic() - run_start,
                    resolution_seconds=resolution_seconds,
                    analysis_seconds=analysis_seconds,
                    requested_workers=requested_workers,
                    workers_used=workers,
                ),
                findings=ordered_findings,
                failures=ordered_failures,
            ),
        )

    def classify(
        self,
        *,
        paths: PathInputs,
        include: Sequence[PathInput] = (),
        exclude: Sequence[PathInput] = (),
        policy: EvaluationPolicy | None = None,
    ) -> tuple[FileFinding, ...]:
        """Compatibility convenience returning successful findings only.

        Args:
            paths: Value supplied for ``paths``.
            include: Value supplied for ``include``.
            exclude: Value supplied for ``exclude``.
            policy: Value supplied for ``policy``.

        Returns:
            The resulting value.

        Raises:
            RuntimeError: If the operation cannot be completed.

        """
        run: AnalysisRun = self.analyze(
            paths=paths,
            include=include,
            exclude=exclude,
            policy=policy,
        )
        if run.failures:
            failure: FileFailure = run.failures[0]
            msg: str = f"{failure.error_type}: {failure.message}"
            raise RuntimeError(msg)
        return run.findings

    @classmethod
    def _worker(
        cls,
        *,
        path: Path,
        policy: EvaluationPolicy,
        callback: ProgressCallback | None,
        total: int,
        analysis_started: float,
    ) -> FileFinding | FileFailure:
        """Execute one worker and retain accurate failure timing.

        Args:
            path: Value supplied for ``path``.
            policy: Value supplied for ``policy``.
            callback: Progress observer.
            total: Total files scheduled in the run.
            analysis_started: Monotonic run-analysis start.

        Returns:
            The resulting value.

        """
        started: float = monotonic()
        cls._notify(
            callback=callback,
            snapshot=cls._progress(
                state=ProgressState(
                    total=total,
                    completed=0,
                    succeeded=0,
                    kept=0,
                    filtered=0,
                    failed=0,
                    current_path=path,
                    current_level=None,
                    stage=AnalysisStage.FILE_STARTED,
                    evidence_count=0,
                    started=analysis_started,
                ),
            ),
        )
        try:
            return cls._analyze_file(
                path=path,
                policy=policy,
                callback=callback,
                total=total,
                analysis_started=analysis_started,
            )
        except (OSError, SyntaxError, ValueError) as error:
            trace(
                step=(
                    f"meaningful: {path.name} — failed "
                    f"{type(error).__name__}: {error}"
                ),
                depth=4,
            )
            return FileFailure(
                path=path,
                error_type=type(error).__name__,
                message=str(object=error),
                duration_seconds=monotonic() - started,
            )

    @classmethod
    def _analyze_file(
        cls,
        *,
        path: Path,
        policy: EvaluationPolicy,
        callback: ProgressCallback | None,
        total: int,
        analysis_started: float,
    ) -> FileFinding:
        """Analyze one file independently inside a worker.

        Args:
            path: Value supplied for ``path``.
            policy: Value supplied for ``policy``.
            callback: Progress observer.
            total: Total files scheduled in the run.
            analysis_started: Monotonic run-analysis start.

        Returns:
            The resulting value.

        """
        started_at: datetime = datetime.now(tz=UTC)
        started: float = monotonic()
        stat: stat_result = path.stat()
        text: str = path.read_text(encoding="utf-8")
        source_lines: int = len(text.splitlines())
        javascript: bool = path.suffix in {".js", ".mjs", ".cjs", ".jsx"}
        metrics: Metrics = (
            javascript_metrics(path=path)
            if javascript
            else baseline_metrics(path=path)
        )
        evaluator: PolicyEvaluator = PolicyEvaluator(policy=policy)
        scores: PromotionScores = evaluator.scores(
            metrics=metrics,
            source_lines=source_lines,
        )
        level: UnitTestLevel = evaluator.level(scores=scores)
        cls._notify(
            callback=callback,
            snapshot=cls._progress(
                state=ProgressState(
                    total=total,
                    completed=0,
                    succeeded=0,
                    kept=0,
                    filtered=0,
                    failed=0,
                    current_path=path,
                    current_level=level,
                    stage=AnalysisStage.FAST_SCAN,
                    evidence_count=0,
                    started=analysis_started,
                ),
            ),
        )
        trace(
            step=f"meaningful: {path.name} — fast scan {level.value}",
            depth=4,
        )
        evidence: tuple[FindingEvidence, ...] = (
            javascript_evidence(
                path=path,
                context=policy.evidence_context,
                level=level,
            )
            if javascript
            else EvidenceCollector(
                path=path,
                context=policy.evidence_context,
            ).collect(level=level)
        )
        cls._notify(
            callback=callback,
            snapshot=cls._progress(
                state=ProgressState(
                    total=total,
                    completed=0,
                    succeeded=0,
                    kept=0,
                    filtered=0,
                    failed=0,
                    current_path=path,
                    current_level=level,
                    stage=AnalysisStage.EVIDENCE,
                    evidence_count=len(evidence),
                    started=analysis_started,
                ),
            ),
        )
        trace(
            step=(f"meaningful: {path.name} — {len(evidence)} evidence items"),
            depth=4,
        )
        decision_tree: tuple[DecisionNode, ...] = evaluator.decisions(
            scores=scores,
            evidence=evidence,
        )
        finished_at: datetime = datetime.now(tz=UTC)
        return FileFinding(
            path=path,
            level=level,
            category=evaluator.category(level=level),
            scores=scores,
            should_be_visited=level
            in {UnitTestLevel.TEST_2, UnitTestLevel.TEST_3},
            decision_tree=decision_tree,
            reasons=cls._reasons(level=level, metrics=metrics),
            metrics=metrics,
            evidence=evidence,
            metadata=FileMetadata(
                size_bytes=stat.st_size,
                source_lines=source_lines,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=monotonic() - started,
                worker_name=current_thread().name,
            ),
        )

    @classmethod
    def _expand_many(
        cls,
        *,
        selectors: Sequence[PathInput],
    ) -> frozenset[Path]:
        """Expand selectors to normalized Python files.

        Args:
            selectors: Value supplied for ``selectors``.

        Returns:
            The resulting value.

        """
        return frozenset(
            path.resolve()
            for selector in selectors
            for path in cls._expand(selector=selector)
        )

    @classmethod
    def _expand(cls, *, selector: PathInput) -> tuple[Path, ...]:
        """Expand one literal path, directory, or glob.

        Args:
            selector: Value supplied for ``selector``.

        Returns:
            The resulting value.

        Raises:
            FileNotFoundError: If the operation cannot be completed.
            ValueError: If the operation cannot be completed.

        """
        text: str = str(object=selector)
        matches: tuple[Path, ...] = (
            cls._glob_paths(pattern=text)
            if cls._has_glob(text=text)
            else (Path(selector),)
        )
        if not matches:
            return ()
        expanded: list[Path] = []
        for match in matches:
            if not match.exists():
                msg: str = f"Path does not exist: {match}"
                raise FileNotFoundError(msg)
            if match.is_dir():
                expanded.extend(
                    path
                    for path in match.rglob(pattern="*")
                    if path.suffix in {".py", ".js", ".mjs", ".cjs", ".jsx"}
                    and not any(
                        is_reports_tree(directory=parent)
                        for parent in path.parents
                    )
                )
            elif match.suffix in {".py", ".js", ".mjs", ".cjs", ".jsx"}:
                expanded.append(match)
            else:
                msg = (
                    "Expected a Python or JavaScript file, directory, or "
                    f"glob: {match}"
                )
                raise ValueError(msg)
        return tuple(expanded)

    @staticmethod
    def _reasons(*, level: UnitTestLevel, metrics: Metrics) -> tuple[str, ...]:
        """Build concise semantic reasons for a finding.

        Args:
            level: Value supplied for ``level``.
            metrics: Value supplied for ``metrics``.

        Returns:
            The resulting value.

        """
        reasons: list[str] = [
            f"Promoted to {level.value} by normalized policy evidence.",
        ]
        if metrics.public_behavioral_members:
            reasons.append(
                f"{metrics.public_behavioral_members} public "
                "behavioral members.",
            )
        if metrics.side_effects:
            reasons.append(f"{metrics.side_effects} external side effects.")
        if metrics.mutations:
            reasons.append(f"{metrics.mutations} state mutations.")
        if metrics.branches or metrics.loops:
            reasons.append(
                f"{metrics.branches} branches and {metrics.loops} loops.",
            )
        if metrics.behavioral_statements:
            reasons.append(
                f"{metrics.behavioral_statements} behavioral statements.",
            )
        return tuple(reasons)

    @staticmethod
    def _progress(*, state: ProgressState) -> ProgressSnapshot:
        """Create one immutable live-progress snapshot.

        Args:
            state: Current aggregate and per-file progress state.

        Returns:
            Snapshot suitable for terminal rendering or API observation.

        """
        elapsed: float = monotonic() - state.started
        rate: float = state.completed / elapsed if elapsed > 0.0 else 0.0
        remaining: int = state.total - state.completed
        return ProgressSnapshot(
            total=state.total,
            completed=state.completed,
            succeeded=state.succeeded,
            kept=state.kept,
            filtered=state.filtered,
            failed=state.failed,
            remaining=remaining,
            percent=(
                100.0
                if state.total == 0
                else round(
                    number=state.completed / state.total * 100.0,
                    ndigits=2,
                )
            ),
            current_path=state.current_path,
            current_level=state.current_level,
            stage=state.stage,
            evidence_count=state.evidence_count,
            elapsed_seconds=elapsed,
            files_per_second=rate,
            estimated_remaining_seconds=(
                remaining / rate if rate > 0.0 else None
            ),
        )

    @staticmethod
    def _notify(
        *,
        callback: ProgressCallback | None,
        snapshot: ProgressSnapshot,
    ) -> None:
        """Invoke an observer without allowing it to corrupt analysis.

        Args:
            callback: Value supplied for ``callback``.
            snapshot: Value supplied for ``snapshot``.

        """
        if callback is None:
            return
        try:
            callback(snapshot)
        except (
            ArithmeticError,
            AssertionError,
            AttributeError,
            LookupError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            return

    @staticmethod
    def _metadata(
        *,
        timing: RunTiming,
        findings: tuple[FileFinding, ...],
        failures: tuple[FileFailure, ...],
    ) -> RunMetadata:
        """Aggregate immutable run metadata.

        Args:
            timing: Run timing and worker configuration.
            findings: Successful file decisions.
            failures: Failed file analyses.

        Returns:
            Complete aggregate metadata.

        """
        levels: tuple[UnitTestLevel, ...] = tuple(
            finding.level for finding in findings
        )
        return RunMetadata(
            started_at=timing.started_at,
            finished_at=timing.finished_at,
            duration_seconds=timing.duration_seconds,
            resolution_seconds=timing.resolution_seconds,
            analysis_seconds=timing.analysis_seconds,
            requested_workers=timing.requested_workers,
            workers_used=timing.workers_used,
            total_files=len(findings) + len(failures),
            succeeded=len(findings),
            failed=len(failures),
            kept=sum(finding.should_be_visited for finding in findings),
            filtered=sum(
                not finding.should_be_visited for finding in findings
            ),
            total_bytes=sum(
                finding.metadata.size_bytes for finding in findings
            ),
            total_source_lines=sum(
                finding.metadata.source_lines for finding in findings
            ),
            test_0=levels.count(UnitTestLevel.TEST_0),
            test_1=levels.count(UnitTestLevel.TEST_1),
            test_2=levels.count(UnitTestLevel.TEST_2),
            test_3=levels.count(UnitTestLevel.TEST_3),
            python_version=python_version.split()[0],
            platform=platform_name(),
            working_directory=Path.cwd(),
        )

    @staticmethod
    def _normalize_inputs(*, paths: PathInputs) -> tuple[PathInput, ...]:
        """Normalize one selector or a selector sequence.

        Args:
            paths: Value supplied for ``paths``.

        Returns:
            The resulting value.

        """
        return (paths,) if isinstance(paths, (str, Path)) else tuple(paths)

    @staticmethod
    def _glob_paths(*, pattern: str) -> tuple[Path, ...]:
        """Expand a pathlib glob pattern.

        Args:
            pattern: Relative or absolute glob pattern.

        Returns:
            Matching paths.

        """
        candidate: Path = Path(pattern)
        return tuple(
            (Path("/") if candidate.is_absolute() else Path.cwd()).glob(
                pattern=pattern.lstrip("/")
                if candidate.is_absolute()
                else pattern,
            ),
        )

    @staticmethod
    def _has_glob(*, text: str) -> bool:
        """Return whether text contains glob metacharacters.

        Args:
            text: Value supplied for ``text``.

        Returns:
            The resulting value.

        """
        return any(character in text for character in "*?[")


def analyze(
    *,
    paths: PathInputs,
    **options: Unpack[AnalyzeOptions],
) -> AnalysisRun:
    """Analyze sources through the functional convenience API.

    Args:
        paths: Value supplied for ``paths``.
        options: Typed per-run analysis options.

    Returns:
        The resulting value.

    """
    return Meaningful().analyze(paths=paths, **options)


def classify(
    *,
    paths: PathInputs,
    include: Sequence[PathInput] = (),
    exclude: Sequence[PathInput] = (),
    policy: EvaluationPolicy | None = None,
) -> tuple[FileFinding, ...]:
    """Return successful findings through the compatibility API.

    Args:
        paths: Value supplied for ``paths``.
        include: Value supplied for ``include``.
        exclude: Value supplied for ``exclude``.
        policy: Value supplied for ``policy``.

    Returns:
        The resulting value.

    """
    return Meaningful(policy=policy).classify(
        paths=paths,
        include=include,
        exclude=exclude,
    )
