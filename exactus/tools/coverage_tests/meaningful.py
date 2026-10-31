# Copyright (c) 2026
"""Classify unreached and sub-minimum sources with Meaningful."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeGuard, cast

from exactus.packages.meaningful import (
    AnalysisRun,
    AnalysisStage,
    EvaluationPolicy,
    FeatureCaps,
    FeatureWeights,
    FileFailure,
    FileFinding,
    Meaningful,
    ProgressSnapshot,
    PromotionFloors,
    PromotionThresholds,
    UnitTestLevel,
)
from exactus.packages.steps import trace
from exactus.tools.common.runtime import emit_progress

if TYPE_CHECKING:
    from collections.abc import Sequence

    from _typeshed import DataclassInstance

    from exactus.tools.common.json_types import JsonScalar, JsonValue
type JsonInput = (
    JsonScalar
    | Path
    | datetime
    | Enum
    | dict[str, "JsonInput"]
    | Sequence["JsonInput"]
    | DataclassInstance
)
type MeaningfulMode = Literal["off", "classify", "require"]
type UnclassifiedPolicy = Literal["filtered", "actionable", "error"]
type ClassificationOrigin = Literal["unreached", "shortfall"]


@dataclass(frozen=True, slots=True, kw_only=True)
class MeaningfulConfig:
    """Store Exactus controls and the complete Meaningful evaluation policy.

    Attributes:
        mode: Mode.
        minimum_level: Minimum level.
        unclassified: Unclassified.
        workers: Workers.
        policy: Policy.

    """

    mode: MeaningfulMode = "require"
    minimum_level: UnitTestLevel = UnitTestLevel.TEST_2
    unclassified: UnclassifiedPolicy = "filtered"
    workers: int | None = None
    policy: EvaluationPolicy = field(default_factory=EvaluationPolicy)

    def __post_init__(self) -> None:
        """Reject an invalid explicit worker count.

        Raises:
            ValueError: Raised when the operation cannot be completed.

        """
        if self.workers is not None and self.workers < 1:
            msg: str = "meaningful workers must be at least 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class MeaningfulResult:
    """Retain canonical skipped rows and the complete artifact payload.

    Attributes:
        rows: Rows.
        artifact: Artifact.

    """

    rows: tuple[dict[str, JsonValue], ...]
    artifact: dict[str, JsonValue]

    @property
    def actionable(self) -> tuple[str, ...]:
        """Return paths Exactus treats as requiring test reachability.

        Returns:
            The resulting value.

        """
        return tuple(
            cast(typ="str", val=row["target"])
            for row in self.rows
            if row.get("actionable") is True
        )

    @property
    def analysis_errors(self) -> tuple[str, ...]:
        """Return failed paths whose configured policy is ``error``.

        Returns:
            The resulting value.

        """
        return tuple(
            cast(typ="str", val=row["target"])
            for row in self.rows
            if row.get("analysis_error") is True
        )

    @property
    def excused(self) -> tuple[str, ...]:
        """Return paths neither requiring tests nor failing analysis.

        Returns:
            The resulting value.

        """
        return tuple(
            cast(typ="str", val=row["target"])
            for row in self.rows
            if row.get("actionable") is not True
            and row.get("analysis_error") is not True
        )


def policy_from_values(
    *,
    evidence_context: int,
    thresholds: tuple[float, float, float],
    weights: tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
    ],
    caps: tuple[int, int, int, int, int, int, int, int, int],
    floors: tuple[float, float, float, float, float],
) -> EvaluationPolicy:
    """Build and validate a complete Meaningful evaluation policy.

    Args:
        evidence_context: Evidence context.
        thresholds: Thresholds.
        weights: Weights.
        caps: Caps.
        floors: Floors.

    Returns:
        The resulting value.

    Raises:
        ValueError: Raised when the operation cannot be completed.

    """
    if any(value <= 0 for value in caps):
        msg: str = "meaningful feature caps must be positive"
        raise ValueError(msg)
    if any(not 0.0 <= value <= 1.0 for value in floors):
        msg = "meaningful promotion floors must be between 0 and 1"
        raise ValueError(msg)
    return EvaluationPolicy(
        thresholds=PromotionThresholds(
            test_0_to_1=thresholds[0],
            test_1_to_2=thresholds[1],
            test_2_to_3=thresholds[2],
        ),
        weights=FeatureWeights(
            behavior=weights[0],
            public_surface=weights[1],
            side_effects=weights[2],
            mutations=weights[3],
            decisions=weights[4],
            errors=weights[5],
            computations=weights[6],
            size=weights[7],
            nesting=weights[8],
        ),
        caps=FeatureCaps(
            behavioral_statements=caps[0],
            public_members=caps[1],
            side_effects=caps[2],
            mutations=caps[3],
            decisions=caps[4],
            errors=caps[5],
            computations=caps[6],
            source_lines=caps[7],
            nesting=caps[8],
        ),
        floors=PromotionFloors(
            side_effect_test_1_to_2=floors[0],
            mutation_test_1_to_2=floors[1],
            error_test_1_to_2=floors[2],
            import_runtime_test_1_to_2=floors[3],
            high_complexity_test_2_to_3=floors[4],
        ),
        evidence_context=evidence_context,
    )


def _is_dataclass_instance(value: JsonInput) -> TypeGuard[DataclassInstance]:
    """Return whether a value is a dataclass instance.

    Args:
        value: Value to inspect.

    Returns:
        Whether the value is a dataclass instance.

    """
    return is_dataclass(obj=value) and not isinstance(value, type)


def _dataclass_values(value: JsonInput) -> dict[str, JsonInput]:
    """Return serialized fields for a confirmed dataclass instance.

    Args:
        value: Dataclass instance to serialize.

    Returns:
        Serialized dataclass fields.

    """
    return cast(
        typ="dict[str, JsonInput]",
        val=asdict(obj=cast(typ="DataclassInstance", val=value)),
    )


def _json(value: JsonInput, *, root: Path) -> JsonValue:
    """Convert dataclass output into stable JSON-compatible values.

    Args:
        value: Value.
        root: Root.

    Returns:
        The resulting value.

    Raises:
        TypeError: Raised when the operation cannot be completed.

    """
    result: JsonValue
    if value is None or isinstance(value, bool | int | float | str):
        result = value
    elif isinstance(value, Path):
        resolved: Path = value.resolve()
        result = str(
            object=resolved.relative_to(root)
            if resolved.is_relative_to(root)
            else value,
        )
    elif isinstance(value, datetime):
        result = value.isoformat()
    elif isinstance(value, Enum):
        result = cast(typ="str", val=value.value)
    elif isinstance(value, dict):
        result = {
            str(object=key): _json(value=item, root=root)
            for key, item in value.items()
        }
    elif isinstance(value, list | tuple):
        result = [_json(value=item, root=root) for item in value]
    elif _is_dataclass_instance(value=value):
        result = _json(value=_dataclass_values(value=value), root=root)
    else:
        msg: str = (
            f"Unsupported Meaningful artifact value: {type(value).__name__}"
        )
        raise TypeError(msg)
    return result


def _relative(*, path: Path, root: Path) -> str:
    """Render a path relative to the Exactus project root when possible.

    Args:
        path: Path.
        root: Root.

    Returns:
        The resulting value.

    """
    resolved: Path = path.resolve()
    return str(
        object=resolved.relative_to(root)
        if resolved.is_relative_to(root)
        else path,
    )


def _rank(level: UnitTestLevel) -> int:
    """Return the ordered rank of one Meaningful level.

    Args:
        level: Level.

    Returns:
        The resulting value.

    """
    return tuple(UnitTestLevel).index(level)


def _progress(
    *,
    snapshots: list[ProgressSnapshot],
    snapshot: ProgressSnapshot,
) -> None:
    """Retain every stage and publish only completed-file progress.

    Args:
        snapshots: Snapshots.
        snapshot: Snapshot.

    """
    snapshots.append(snapshot)
    if snapshot.stage is AnalysisStage.DECISION:
        emit_progress(
            state="RUNNING",
            completed=snapshot.completed,
            total=snapshot.total,
            step="meaningful classification",
            detail=str(object=snapshot.current_path),
        )


def analyze_unreached(
    *,
    root: Path,
    paths: tuple[Path, ...],
    config: MeaningfulConfig,
    origin: ClassificationOrigin = "unreached",
) -> MeaningfulResult:
    """Classify every canonical candidate path without dropping failures.

    Args:
        root: Root.
        paths: Paths.
        config: Config.
        origin: Whether paths are fully unreached sources or measured
            sources below the per-file coverage minimum.

    Returns:
        The resulting value.

    """
    reason: str = (
        "no test imports or executes this file"
        if origin == "unreached"
        else "measured coverage is below the per-file minimum"
    )
    supported: frozenset[str] = frozenset(
        {".py", ".js", ".mjs", ".cjs", ".jsx"},
    )
    selected: tuple[Path, ...] = tuple(
        path for path in paths if path.suffix in supported
    )
    trace(
        step=(
            f"meaningful: {len(selected)} source files selected "
            f"of {len(paths)} {origin} — mode {config.mode}"
        ),
        depth=2,
    )
    snapshots: list[ProgressSnapshot] = []
    findings: dict[Path, FileFinding] = {}
    failures: dict[Path, FileFailure] = {}
    run: AnalysisRun | None = None
    if config.mode != "off" and selected:
        run = Meaningful(
            policy=config.policy,
            max_workers=config.workers,
            on_progress=lambda snapshot: _progress(
                snapshots=snapshots,
                snapshot=snapshot,
            ),
        ).analyze(paths=selected)
        findings = {item.path.resolve(): item for item in run.findings}
        failures = {item.path.resolve(): item for item in run.failures}
        trace(
            step=(
                f"meaningful: run complete — {len(findings)} findings, "
                f"{len(failures)} failures"
            ),
            depth=2,
        )
    elif config.mode == "off":
        trace(step="meaningful: mode off — classification skipped", depth=2)
    rows: list[dict[str, JsonValue]] = []
    for path in paths:
        target: str = _relative(path=path, root=root)
        finding: FileFinding | None = findings.get(path.resolve())
        failure: FileFailure | None = failures.get(path.resolve())
        if config.mode == "off" or path.suffix not in supported:
            rows.append(
                {
                    "target": target,
                    "reason": reason,
                    "origin": origin,
                    "source": "reachability",
                    "level": None,
                    "category": None,
                    "status": "unclassified",
                    "actionable": False,
                    "analysis_error": False,
                },
            )
            continue
        if finding is not None:
            data: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=_json(value=finding, root=root),
            )
            level: UnitTestLevel = finding.level
            actionable: bool = _rank(level=level) >= _rank(
                level=config.minimum_level,
            )
            rows.append(
                {
                    "target": target,
                    "reason": reason,
                    "origin": origin,
                    "source": "meaningful",
                    **data,
                    "status": "actionable" if actionable else "filtered",
                    "actionable": actionable,
                    "analysis_error": False,
                },
            )
            continue
        failure_data: JsonValue = (
            _json(value=failure, root=root)
            if failure is not None
            else {
                "path": target,
                "error_type": "MissingOutcome",
                "message": "Meaningful returned no outcome for this path",
                "duration_seconds": 0.0,
            }
        )
        actionable = config.unclassified == "actionable"
        rows.append(
            {
                "target": target,
                "reason": "Meaningful could not classify this file",
                "origin": origin,
                "source": "meaningful",
                "level": None,
                "category": None,
                "status": "unclassified",
                "actionable": actionable,
                "analysis_error": config.unclassified == "error",
                "failure": failure_data,
            },
        )
    level_counts: Counter[str] = Counter(
        row["level"] for row in rows if isinstance(row["level"], str)
    )
    status_counts: Counter[str] = Counter(
        cast(typ="str", val=row["status"]) for row in rows
    )
    artifact: dict[str, JsonValue] = {
        "schema": "exactus.coverage_tests.meaningful/v1",
        "settings": _json(value=config, root=root),
        "selected_paths": [
            _relative(path=path, root=root) for path in selected
        ],
        "rows": cast(typ="list[JsonValue]", val=rows),
        "findings": _json(value=run.findings, root=root)
        if run is not None
        else [],
        "failures": _json(value=run.failures, root=root)
        if run is not None
        else [],
        "metadata": _json(value=run.metadata, root=root)
        if run is not None
        else None,
        "progress": _json(value=snapshots, root=root),
        "counts": {
            **{
                level.value: level_counts[level.value]
                for level in UnitTestLevel
            },
            "actionable": status_counts["actionable"],
            "filtered": status_counts["filtered"],
            "unclassified": status_counts["unclassified"],
        },
    }
    trace(
        step=(
            f"meaningful: {len(rows)} rows — "
            f"{status_counts['actionable']} actionable, "
            f"{status_counts['filtered']} filtered, "
            f"{status_counts['unclassified']} unclassified"
        ),
        depth=2,
    )
    return MeaningfulResult(rows=tuple(rows), artifact=artifact)


def _items(*, value: JsonValue) -> list[JsonValue]:
    """Return a JSON value as a list, defaulting to empty.

    Args:
        value: Value.

    Returns:
        The resulting value.

    """
    return list(value) if isinstance(value, list) else []


def merge_results(
    *,
    first: MeaningfulResult,
    second: MeaningfulResult,
) -> MeaningfulResult:
    """Merge two classification passes into one combined result.

    Args:
        first: Earlier classification result.
        second: Later classification result.

    Returns:
        Combined rows with a rebuilt artifact payload.

    """
    rows: tuple[dict[str, JsonValue], ...] = (*first.rows, *second.rows)
    level_counts: Counter[str] = Counter(
        row["level"] for row in rows if isinstance(row["level"], str)
    )
    status_counts: Counter[str] = Counter(
        cast(typ="str", val=row["status"]) for row in rows
    )
    merged: dict[str, JsonValue] = {
        **first.artifact,
        "selected_paths": [
            *_items(value=first.artifact.get("selected_paths")),
            *_items(value=second.artifact.get("selected_paths")),
        ],
        "rows": cast(typ="list[JsonValue]", val=list(rows)),
        "findings": [
            *_items(value=first.artifact.get("findings")),
            *_items(value=second.artifact.get("findings")),
        ],
        "failures": [
            *_items(value=first.artifact.get("failures")),
            *_items(value=second.artifact.get("failures")),
        ],
        "metadata": second.artifact.get("metadata")
        or first.artifact.get("metadata"),
        "progress": [
            *_items(value=first.artifact.get("progress")),
            *_items(value=second.artifact.get("progress")),
        ],
        "counts": {
            **{
                level.value: level_counts[level.value]
                for level in UnitTestLevel
            },
            "actionable": status_counts["actionable"],
            "filtered": status_counts["filtered"],
            "unclassified": status_counts["unclassified"],
        },
    }
    trace(
        step=(
            f"meaningful: merged {len(second.rows)} rows into "
            f"{len(rows)} total"
        ),
        depth=2,
    )
    return MeaningfulResult(rows=rows, artifact=merged)


def write_artifact(*, path: Path, result: MeaningfulResult) -> None:
    """Write the complete Meaningful integration artifact.

    Args:
        path: Path.
        result: Result.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        data=dumps(obj=result.artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trace(
        step=(
            f"meaningful: artifact written — {path.name}, "
            f"{len(result.rows)} rows"
        ),
        depth=3,
    )
