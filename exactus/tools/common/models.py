# Copyright (c) 2026
# Copyright (c) 2026
"""Shared exactus orchestration models."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from json import JSONDecodeError, loads
from typing import TYPE_CHECKING, Self, cast

from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityEvent,
    ActivityHeartbeat,
    ActivityProgress,
)
from exactus.tools.common.progress import RunItem

if TYPE_CHECKING:
    from pathlib import Path
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def result_stats(*, report_json: Path) -> str:
    """Summarize a tool report's file coverage and finding severities.

    Args:
        report_json: Path of the tool's ``result.json`` payload.

    Returns:
        ``"<affected>/<analyzed> files, N errors, ..."`` when the payload
        carries the shared ``summary`` counters, else ``""``.

    """
    try:
        payload: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=report_json.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    raw_summary: JsonValue = payload.get("summary")
    summary: dict[str, JsonValue] = (
        raw_summary if isinstance(raw_summary, dict) else {}
    )
    raw_total: JsonValue = summary.get(
        "targets_analyzed",
        summary.get("targets_eligible"),
    )
    total: int = int(raw_total) if isinstance(raw_total, int | float) else 0
    raw_findings: JsonValue = payload.get("findings")
    findings: list[JsonValue] = (
        raw_findings if isinstance(raw_findings, list) else []
    )
    files: set[str] = {
        text
        for item in findings
        if isinstance(item, dict)
        for text in (
            str(
                object=item.get("file")
                or item.get("path")
                or item.get("target")
                or "",
            ),
        )
        if text
    }
    severity: Counter[str] = Counter(
        str(object=item.get("severity", "")).lower()
        for item in findings
        if isinstance(item, dict)
    )
    if not severity:
        raw_severity: JsonValue = summary.get("severity")
        if isinstance(raw_severity, dict):
            severity = Counter(
                {
                    str(object=level).lower(): int(count)
                    for level, count in raw_severity.items()
                    if isinstance(count, int | float)
                },
            )
    order: tuple[str, ...] = ("error", "warning", "information", "info")
    counts: list[str] = [
        f"{severity[level]} {level}{'s' if severity[level] != 1 else ''}"
        for level in order
        if severity.get(level)
    ]
    counts.extend(
        f"{severity[level]} {level}"
        for level in sorted(set(severity) - set(order))
        if severity[level]
    )
    raw_total_findings: JsonValue = summary.get("findings_total")
    findings_total: int = (
        int(raw_total_findings)
        if isinstance(raw_total_findings, int | float)
        else len(findings)
    )
    parts: list[str] = []
    if total:
        parts.append(f"{len(files)} files with issues / {total} files")
    if counts:
        parts.append(", ".join(counts))
    elif findings_total:
        parts.append(f"{findings_total} findings")
    return " · ".join(parts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolRequest:
    """Describe one tool execution requested by the orchestrator.

    Attributes:
        identifier: Canonical tool identifier.
        output: Analyzer report directory.
        arguments: Extra CLI arguments forwarded to the tool.
        run_id: Unique run identifier for this tool execution.
        pipeline_run_id: Owning pipeline run identifier, if any.
        project_root: Exactused project root, or ``None`` for the worker cwd.

    """

    identifier: str
    output: Path
    arguments: tuple[str, ...]
    run_id: str
    pipeline_run_id: str | None = None
    project_root: Path | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolRunResult:
    """Describe the completed outcome of one tool execution.

    Attributes:
        tool: Canonical tool identifier.
        run_id: Run identifier that produced the result.
        pipeline_run_id: Owning pipeline run identifier, if any.
        status: ``PASS``, ``FAIL``, ``INTERRUPT``, or ``CRASH``.
        passed: Whether the tool completed successfully.
        exit_code: Analyzer exit status.
        duration_seconds: Wall-clock execution duration.
        resume: One-line human-readable outcome summary.
        report: Markdown report path.
        report_json: JSON report path.
        report_web: Web report index path.
        replaced_after_execution: Whether the report on disk was
            superseded by a different run's output.

    """

    tool: str
    run_id: str
    pipeline_run_id: str | None
    status: str
    passed: bool
    exit_code: int
    duration_seconds: float
    resume: str
    report: Path
    report_json: Path
    report_web: Path
    replaced_after_execution: bool = False

    @classmethod
    def from_report(
        cls: type[Self],
        *,
        payload: JsonValue,
        output: Path,
        fallback: ToolRunResult,
    ) -> ToolRunResult:
        """Reconstruct a result from a superseding run's report payload.

        Args:
            payload: Parsed ``result.json`` document.
            output: Analyzer report directory holding the payload.
            fallback: Original result supplying defaults.

        Returns:
            Result describing the report actually on disk.

        """
        data: dict[str, JsonValue] = (
            cast(typ="dict[str, JsonValue]", val=payload)
            if isinstance(payload, dict)
            else {}
        )
        raw_tool: JsonValue | None = data.get("tool")
        tool: JsonValue | None = (
            raw_tool.get("name") if isinstance(raw_tool, dict) else raw_tool
        )
        run_id: JsonValue | None = data.get("run_id")
        pipeline_run_id: JsonValue | None = data.get("pipeline_run_id")
        status: JsonValue | None = data.get("status")
        passed: JsonValue | None = data.get("passed")
        duration: JsonValue | None = data.get("duration_seconds")
        resume: JsonValue | None = data.get("resume")
        succeeded: bool = (
            passed if isinstance(passed, bool) else fallback.passed
        )
        return cls(
            tool=tool if isinstance(tool, str) else fallback.tool,
            run_id=run_id if isinstance(run_id, str) else fallback.run_id,
            pipeline_run_id=(
                pipeline_run_id
                if isinstance(pipeline_run_id, str)
                else fallback.pipeline_run_id
            ),
            status=status if isinstance(status, str) else fallback.status,
            passed=succeeded,
            exit_code=0 if succeeded else max(fallback.exit_code, 1),
            duration_seconds=(
                float(duration)
                if isinstance(duration, int | float)
                else fallback.duration_seconds
            ),
            resume=resume if isinstance(resume, str) else fallback.resume,
            report=output / "result.md",
            report_json=output / "result.json",
            report_web=output / "result_web" / "index.html",
            replaced_after_execution=True,
        )

    def replaced(self: Self) -> ToolRunResult:
        """Mark this result as superseded by a different run's report.

        Returns:
            Copy flagged ``replaced_after_execution``.

        """
        return replace(self, replaced_after_execution=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolActivity:
    """Describe live progress of one tool inside a pipeline run.

    Attributes:
        name: Canonical tool identifier.
        run_id: Run identifier assigned to the tool execution.
        group: One-based dependency wave the tool belongs to.
        position: One-based position across all pipeline tools.
        status: Lifecycle state (``WAITING``/``RUNNING``/``PASS``/...).
        progress: Completion fraction in ``[0, 1]``.
        step: Current step label.
        started_at: ISO-8601 start timestamp, if started.
        finished_at: ISO-8601 finish timestamp, if finished.
        elapsed_seconds: Wall-clock execution duration.
        report_updated: Whether a newer report replaced this tool's result.
        issues: Live worker errors emitted before the process settles.
        hierarchy: Normalized task/subtask/activity progress subtree.

    """

    name: str
    run_id: str
    group: int
    position: int
    status: str
    progress: float
    step: str
    started_at: str | None
    finished_at: str | None
    elapsed_seconds: float
    report_updated: bool = False
    issues: int = 0
    hierarchy: dict[str, JsonValue] | None = None

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the record as one ``exactus-run/v1`` items entry.

        Returns:
            JSON-compatible item document.

        """
        return RunItem(
            name=self.name,
            run_id=self.run_id,
            status=self.status,
            progress=self.progress,
            step=self.step,
            started_at=self.started_at,
            finished_at=self.finished_at,
            elapsed_seconds=self.elapsed_seconds,
            extra={
                "group": self.group,
                "position": self.position,
                "report_updated": self.report_updated,
                "issues": self.issues,
                "hierarchy": self.hierarchy,
            },
        ).payload()


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineActivity:
    """Describe live progress of one pipeline run.

    Attributes:
        name: Canonical pipeline identifier.
        run_id: Pipeline run identifier.
        status: Lifecycle state.
        progress: Aggregate completion fraction in ``[0, 1]``.
        completed: Tools that reached a terminal state.
        total: Total pipeline tool count.
        step: Current pipeline stage label.
        detail: Optional human-readable detail.
        current_group: Dependency wave currently executing.
        group_count: Total dependency wave count.
        previous_duration_seconds: Duration of the previous pipeline
            run, when a report already existed.
        started_at: ISO-8601 start timestamp.
        finished_at: ISO-8601 finish timestamp.
        elapsed_seconds: Wall-clock pipeline duration.
        updated_at: ISO-8601 last-write timestamp.
        pid: Owning orchestrator process identifier.
        items: Per-tool activity records in pipeline order.
        events: Most recent pipeline events, oldest first.
        events_dropped: Older events no longer kept.

    """

    name: str
    run_id: str
    status: str
    progress: float
    completed: int
    total: int
    step: str
    detail: str
    current_group: int | None
    group_count: int
    started_at: str
    finished_at: str | None
    elapsed_seconds: float
    updated_at: str
    pid: int
    items: tuple[ToolActivity, ...]
    events: tuple[ActivityEvent, ...] = ()
    events_dropped: int = 0
    previous_duration_seconds: float | None = None

    def document(self: Self) -> ActivityDocument:
        """Build the fixed ``@activity.json`` document of the pipeline.

        Returns:
            The ``exactus/activity/v1`` document.

        """
        return ActivityDocument(
            kind="pipeline",
            name=self.name,
            status=self.status,
            run_id=self.run_id,
            started_at=self.started_at,
            updated_at=self.updated_at,
            finished_at=self.finished_at,
            elapsed_seconds=self.elapsed_seconds,
            heartbeat=ActivityHeartbeat(
                pid=self.pid,
                alive=self.status in {"WAITING", "RUNNING"},
                last_beat=self.updated_at,
                phase=(
                    "running"
                    if self.status in {"WAITING", "RUNNING"}
                    else "interrupted"
                    if self.status == "INTERRUPT"
                    else "finished"
                ),
            ),
            progress=ActivityProgress(
                completed=self.completed,
                total=self.total,
                fraction=self.progress,
                step=self.step,
                current=self.detail,
                hierarchy=self._hierarchy(),
            ),
            events=self.events,
            events_dropped=self.events_dropped,
            items=tuple(item.payload() for item in self.items),
            extra={
                "current_group": self.current_group,
                "group_count": self.group_count,
                **(
                    {
                        "previous_duration_seconds": round(
                            number=self.previous_duration_seconds,
                            ndigits=3,
                        ),
                    }
                    if self.previous_duration_seconds is not None
                    else {}
                ),
            },
        )

    def payload(self: Self) -> dict[str, JsonValue]:
        """Serialize the activity record for ``@activity.json``.

        Returns:
            JSON-compatible ``exactus/activity/v1`` activity document.

        """
        return self.document().payload()

    def _hierarchy(self: Self) -> dict[str, JsonValue]:
        """Compose task subtrees under the pipeline orchestrator node.

        Returns:
            Normalized pipeline progress hierarchy.

        """
        children: list[JsonValue] = []
        for item in self.items:
            if item.hierarchy is not None:
                children.append(dict(item.hierarchy))
                continue
            children.append(
                {
                    "level": "task",
                    "id": item.name,
                    "state": item.status,
                    "completed": int(
                        item.status not in {"WAITING", "RUNNING"},
                    ),
                    "total": 1,
                    "fraction": item.progress,
                    "step": item.step,
                    "current": item.step,
                    "error": (
                        {"message": f"{item.issues} worker error(s)"}
                        if item.issues
                        else None
                    ),
                    "children": [],
                },
            )
        return {
            "level": "pipeline",
            "id": self.name,
            "state": self.status,
            "completed": self.completed,
            "total": self.total,
            "fraction": self.progress,
            "step": self.step,
            "current": self.detail,
            "error": None,
            "children": children,
        }
