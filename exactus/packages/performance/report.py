# Copyright (c) 2026 João Lopes.
"""Build the machine-readable performance report."""

from dataclasses import asdict
from datetime import UTC, datetime
from json import dumps
from pathlib import Path
from typing import Final, cast, final

from exactus.packages.performance.analyzer import PerformanceAnalyzer
from exactus.packages.performance.model import (
    PerformanceRun,
    ResourceSample,
    StepEvent,
    TreeNode,
)

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        schema: Grouped module constant.
        digits: Grouped module constant.
        file_name: Grouped module constant.

    """

    schema: Final[str] = "exactus.performance-report/v1"
    digits: Final[int] = 6
    file_name: Final[str] = "report.json"


@final
class PerformanceReport:
    """Serialize analyzed runs into one complete JSON document.

    The document is self-contained: per tool it carries every event with
    its attribution, the stage and bottleneck lists, actor / operation /
    thread aggregates, the slowest steps, every resource sample, and the
    full execution tree with per-node resource use, so consumers need not
    re-parse ``steps.txt`` or run the dashboard.
    """

    @classmethod
    def build(cls, *, runs: tuple[PerformanceRun, ...]) -> JsonObject:
        """Build the report document.

        Args:
            runs: Analyzed runs.

        Returns:
            JSON-serializable report with a ``schema`` field.

        """
        tools: list[JsonValue] = [cls._tool(run=run) for run in runs]
        durations: list[float] = [run.duration for run in runs]
        return {
            "schema": Constants.schema,
            "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "summary": {
                "tools": len(runs),
                "events": sum(len(run.events) for run in runs),
                "nodes": sum(len(run.nodes) for run in runs),
                "samples": sum(len(run.samples) for run in runs),
                "duration_total": cls._seconds(value=sum(durations)),
                "duration_longest": cls._seconds(
                    value=max(durations, default=0.0),
                ),
                "silent_total": cls._seconds(
                    value=sum(run.silent for run in runs),
                ),
            },
            "tools": tools,
        }

    @classmethod
    def write(cls, *, runs: tuple[PerformanceRun, ...], path: Path) -> Path:
        """Write the report as UTF-8 JSON.

        Args:
            runs: Analyzed runs.
            path: Destination file; parents are created.

        Returns:
            The written path.

        """
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(
            data=dumps(obj=cls.build(runs=runs), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def _round(cls, *, value: JsonValue) -> JsonValue:
        """Round every float inside a JSON-shaped value.

        Args:
            value: Value built from dataclass fields.

        Returns:
            Same shape with floats rounded.

        """
        if isinstance(value, float):
            return cls._seconds(value=value)
        if isinstance(value, list):
            return [cls._round(value=item) for item in value]
        if isinstance(value, dict):
            return {key: cls._round(value=item) for key, item in value.items()}
        return value

    @classmethod
    def _tool(cls, *, run: PerformanceRun) -> JsonValue:
        """Serialize one run.

        Args:
            run: Analyzed run.

        Returns:
            JSON object for the run.

        """
        inferred: tuple[float, ...] = PerformanceAnalyzer.inferred(
            events=run.events,
        )
        resource_summary: JsonValue = (
            cls._round(value=asdict(obj=run.resources))
            if run.resources is not None
            else None
        )
        document: JsonObject = {
            "tool": run.tool,
            "source": str(object=run.source),
            "duration": run.duration,
            "event_count": len(run.events),
            "event_rate": run.event_rate,
            "largest_gap": run.largest_gap,
            "silent": run.silent,
            "stages": [asdict(obj=item) for item in run.stages],
            "bottlenecks": [asdict(obj=item) for item in run.bottlenecks],
            "actors": [asdict(obj=item) for item in run.actors],
            "operations": [asdict(obj=item) for item in run.templates],
            "slowest": [asdict(obj=item) for item in run.slowest],
            "threads": [asdict(obj=item) for item in run.threads],
            "resources": {
                "summary": resource_summary,
                "samples": [cls._sample(sample=item) for item in run.samples],
            },
            "tree": [cls._node(run=run, node=item) for item in run.nodes],
            "events": [
                cls._event(event=item, inferred=inferred[item.index])
                for item in run.events
            ],
        }
        return cls._round(value=document)

    @staticmethod
    def _seconds(*, value: float) -> float:
        """Round a duration or rate for stable output.

        Args:
            value: Seconds or a rate.

        Returns:
            The rounded number.

        """
        return round(number=value, ndigits=Constants.digits)

    @staticmethod
    def _event(*, event: StepEvent, inferred: float) -> JsonObject:
        """Serialize one event with its attributed time.

        Args:
            event: Parsed event.
            inferred: Seconds until the thread's next event.

        Returns:
            JSON object for the event.

        """
        return {
            "index": event.index,
            "timestamp": event.timestamp,
            "elapsed": event.elapsed,
            "depth": event.depth,
            "thread": event.thread,
            "phase": event.phase,
            "span": event.span,
            "actor": event.actor,
            "message": event.message,
            "template": event.template,
            "measured": event.measured,
            "inferred": inferred,
        }

    @staticmethod
    def _sample(*, sample: ResourceSample) -> JsonObject:
        """Serialize one resource sample without its raw line.

        Args:
            sample: Resource sample.

        Returns:
            JSON object for the sample.

        """
        document: JsonObject = {
            key: value
            for key, value in asdict(obj=sample).items()
            if key != "raw"
        }
        return document

    @staticmethod
    def _node(*, run: PerformanceRun, node: TreeNode) -> JsonObject:
        """Serialize one tree node with its resource use.

        Args:
            run: Run owning the node.
            node: Tree node.

        Returns:
            JSON object for the node.

        """
        usage: tuple[float, float, float, float] | None = (
            PerformanceAnalyzer.integrate(
                samples=run.samples,
                start=node.start,
                end=node.end,
            )
        )
        document: JsonObject = {
            "id": node.id,
            "event": node.event,
            "parent": node.parent,
            "children": cast(typ="list[JsonValue]", val=list(node.children)),
            "thread": node.thread,
            "level": node.level,
            "label": run.events[node.event].message,
            "start": node.start,
            "end": node.end,
            "total": node.total,
            "self": node.self_time,
            "measured": run.events[node.event].measured,
            "cpu_mean": usage[0] if usage is not None else None,
            "rss_peak": usage[1] if usage is not None else None,
            "read_mib": usage[2] if usage is not None else None,
            "write_mib": usage[3] if usage is not None else None,
        }
        return document
