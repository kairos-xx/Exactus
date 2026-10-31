# Copyright (c) 2026 João Lopes.
"""Analyze step traces for execution bottlenecks."""

from collections import Counter
from dataclasses import replace
from itertools import pairwise
from math import ceil
from pathlib import Path

from exactus.packages.performance.model import (
    ActorStat,
    Bottleneck,
    PerformanceRun,
    ResourceSample,
    ResourceSummary,
    SlowStep,
    Stage,
    StepEvent,
    TemplateStat,
    ThreadStat,
    TreeNode,
)
from exactus.packages.performance.parser import StepParser


class PerformanceAnalyzer:
    """Convert timestamped step traces into performance diagnostics."""

    @classmethod
    def analyze_events(
        cls,
        *,
        tool: str,
        source: Path,
        events: tuple[StepEvent, ...],
        gap_threshold: float = 0.25,
        repetition_threshold: int = 10,
    ) -> PerformanceRun:
        """Analyze already parsed events.

        Args:
            tool: Tool identifier associated with the trace.
            source: Source trace path.
            events: Parsed events in execution order.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            Complete immutable performance analysis.

        """
        duration: float = events[-1].elapsed if events else 0.0
        gaps: tuple[float, ...] = tuple(
            current.elapsed - previous.elapsed
            for previous, current in pairwise(events)
        )
        inferred: tuple[float, ...] = cls.inferred(events=events)
        return PerformanceRun(
            tool=tool,
            source=source,
            events=events,
            stages=cls._stages(events=events),
            bottlenecks=cls._bottlenecks(
                events=events,
                duration=duration,
                gap_threshold=gap_threshold,
                repetition_threshold=repetition_threshold,
            ),
            duration=duration,
            event_rate=len(events) / duration if duration > 0.0 else 0.0,
            largest_gap=max(gaps, default=0.0),
            actors=cls._actors(events=events, inferred=inferred),
            templates=cls._templates(events=events, inferred=inferred),
            slowest=cls._slowest(events=events, inferred=inferred),
            threads=cls._threads(events=events, inferred=inferred),
            silent=sum(gap for gap in gaps if gap >= gap_threshold),
            nodes=cls.tree(events=events, duration=duration),
        )

    @classmethod
    def analyze_file(
        cls,
        *,
        path: Path,
        gap_threshold: float = 0.25,
        repetition_threshold: int = 10,
    ) -> PerformanceRun:
        """Parse and analyze one trace file.

        Args:
            path: Path to the trace file.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            Complete performance analysis.

        """
        lines: tuple[str, ...] = tuple(
            path.read_text(encoding="utf-8").splitlines(),
        )
        samples: tuple[ResourceSample, ...] = StepParser.parse_samples(
            lines=lines,
        )
        return replace(
            cls.analyze_events(
                tool=StepParser.tool_name(path=path),
                source=path,
                events=StepParser.parse_lines(lines=lines),
                gap_threshold=gap_threshold,
                repetition_threshold=repetition_threshold,
            ),
            samples=samples,
            resources=cls.summarize(samples=samples),
        )

    @classmethod
    def analyze_paths(
        cls,
        *,
        paths: tuple[Path, ...],
        gap_threshold: float = 0.25,
        repetition_threshold: int = 10,
    ) -> tuple[PerformanceRun, ...]:
        """Discover and analyze every trace below the supplied paths.

        Args:
            paths: Files or directories containing traces.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            Analyzed runs ordered by source path.

        """
        return tuple(
            cls.analyze_file(
                path=path,
                gap_threshold=gap_threshold,
                repetition_threshold=repetition_threshold,
            )
            for path in StepParser.discover(paths=paths)
        )

    @staticmethod
    def tree(
        *,
        events: tuple[StepEvent, ...],
        duration: float,
    ) -> tuple[TreeNode, ...]:
        """Build every thread's execution tree from depth and spans.

        Args:
            events: Parsed events in execution order.
            duration: Total run duration; closes the main lane.

        Returns:
            Nodes in event order; span end lines do not open nodes.

        """
        starts: list[float] = []
        ends: list[float] = []
        measured_end: list[float | None] = []
        indexes: list[int] = []
        parents: list[int | None] = []
        levels: list[int] = []
        threads: list[str] = []
        stacks: dict[str, list[int]] = {}
        last: dict[str, float] = {}

        def close(*, stack: list[int], depth: int, at: float) -> None:
            """Pop every open node at or below ``depth`` on one stack.

            Args:
                stack: Open node indexes for one thread.
                depth: Event depth; nodes at this depth or deeper close.
                at: Fallback end time for nodes without a measured end.

            """
            while stack and events[indexes[stack[-1]]].depth >= depth:
                node: int = stack.pop()
                limit: float | None = measured_end[node]
                ends[node] = max(
                    starts[node],
                    limit if limit is not None else at,
                )

        for event in events:
            if event.phase == "end":
                continue
            stack: list[int] = stacks.setdefault(event.thread, [])
            close(stack=stack, depth=event.depth, at=event.elapsed)
            node: int = len(indexes)
            indexes.append(event.index)
            parents.append(stack[-1] if stack else None)
            levels.append(levels[stack[-1]] + 1 if stack else 0)
            threads.append(event.thread)
            starts.append(event.elapsed)
            ends.append(event.elapsed)
            measured_end.append(
                event.elapsed + event.measured
                if event.phase == "begin" and event.measured is not None
                else None,
            )
            stack.append(node)
            last[event.thread] = event.elapsed
        for thread, stack in stacks.items():
            close(
                stack=stack,
                depth=-1,
                at=max(duration, last[thread])
                if thread == "main"
                else last[thread],
            )
        children: list[list[int]] = [[] for _ in indexes]
        for node, parent in enumerate(iterable=parents):
            if parent is not None:
                children[parent].append(node)
        return tuple(
            TreeNode(
                id=node,
                event=indexes[node],
                parent=parents[node],
                children=tuple(children[node]),
                thread=threads[node],
                level=levels[node],
                start=starts[node],
                end=ends[node],
                total=max(0.0, ends[node] - starts[node]),
                self_time=max(
                    0.0,
                    ends[node]
                    - starts[node]
                    - sum(
                        max(0.0, ends[child] - starts[child])
                        for child in children[node]
                    ),
                ),
            )
            for node in range(len(indexes))
        )

    @staticmethod
    def integrate(
        *,
        samples: tuple[ResourceSample, ...],
        start: float,
        end: float,
    ) -> tuple[float, float, float, float] | None:
        """Integrate resource samples over an interval.

        Args:
            samples: Samples in time order.
            start: Interval start in elapsed seconds.
            end: Interval end in elapsed seconds.

        Returns:
            ``(mean_cpu, peak_rss, read_mib, write_mib)``, or ``None``
            when no sample overlaps the interval.

        """
        weight: float = 0.0
        cpu: float = 0.0
        read: float = 0.0
        write: float = 0.0
        rss: float = 0.0
        previous: float = 0.0
        for sample in samples:
            low: float = max(previous, start)
            high: float = min(sample.elapsed, end)
            previous = sample.elapsed
            if high <= low:
                continue
            width: float = high - low
            weight += width
            cpu += sample.cpu * width
            read += sample.read * width
            write += sample.write * width
            rss = max(rss, sample.rss)
        if weight <= 0.0:
            return None
        return (cpu / weight, rss, read, write)

    @staticmethod
    def summarize(
        *,
        samples: tuple[ResourceSample, ...],
    ) -> ResourceSummary | None:
        """Aggregate resource samples.

        Args:
            samples: Samples in time order.

        Returns:
            Summary, or ``None`` when the run was not sampled.

        """
        if not samples:
            return None
        previous: float = 0.0
        read: float = 0.0
        write: float = 0.0
        for sample in samples:
            width: float = max(0.0, sample.elapsed - previous)
            read += sample.read * width
            write += sample.write * width
            previous = sample.elapsed
        return ResourceSummary(
            samples=len(samples),
            mean_cpu=sum(item.cpu for item in samples) / len(samples),
            peak_cpu=max(item.cpu for item in samples),
            peak_rss=max(item.rss for item in samples),
            read=read,
            write=write,
            peak_procs=max(item.procs for item in samples),
        )

    @staticmethod
    def inferred(*, events: tuple[StepEvent, ...]) -> tuple[float, ...]:
        """Attribute each event the time until its thread's next event.

        A trace only records when steps start, so the wait before the
        next event on the same thread is the best available estimate of
        what the step cost. Lanes are separated so interleaved workers
        do not steal each other's time.

        Args:
            events: Parsed events in execution order.

        Returns:
            Seconds per event, ``0.0`` for each lane's final event.

        """
        values: list[float] = [0.0] * len(events)
        last: dict[str, StepEvent] = {}
        for event in events:
            previous: StepEvent | None = last.get(event.thread)
            if previous is not None:
                values[previous.index] = max(
                    0.0,
                    event.elapsed - previous.elapsed,
                )
            last[event.thread] = event
        return tuple(values)

    @classmethod
    def _actors(
        cls,
        *,
        events: tuple[StepEvent, ...],
        inferred: tuple[float, ...],
    ) -> tuple[ActorStat, ...]:
        """Aggregate attributed time per actor.

        Args:
            events: Parsed events in execution order.
            inferred: Inferred seconds per event.

        Returns:
            Actor statistics, largest attributed time first.

        """
        total: float = sum(inferred)
        grouped: dict[str, list[StepEvent]] = {}
        for event in events:
            grouped.setdefault(event.actor, []).append(event)
        stats: list[ActorStat] = []
        for name, members in grouped.items():
            samples: list[float] = [inferred[item.index] for item in members]
            stats.append(
                ActorStat(
                    name=name,
                    count=len(members),
                    inferred=sum(samples),
                    measured=sum(
                        item.measured or 0.0
                        for item in members
                        if item.phase != "end"
                    ),
                    share=sum(samples) / total if total > 0.0 else 0.0,
                    longest=max(samples),
                    p95=cls._percentile(values=samples, fraction=0.95),
                ),
            )
        return tuple(
            sorted(stats, key=lambda item: item.inferred, reverse=True),
        )

    @staticmethod
    def _percentile(*, values: list[float], fraction: float) -> float:
        """Return a nearest-rank percentile.

        Args:
            values: Sample values.
            fraction: Percentile as a fraction between zero and one.

        Returns:
            The percentile, ``0.0`` for an empty sample.

        """
        if not values:
            return 0.0
        ordered: list[float] = sorted(values)
        rank: int = max(0, ceil(fraction * len(ordered)) - 1)
        return ordered[rank]

    @staticmethod
    def _templates(
        *,
        events: tuple[StepEvent, ...],
        inferred: tuple[float, ...],
    ) -> tuple[TemplateStat, ...]:
        """Aggregate repeated operations by normalized message.

        Args:
            events: Parsed events in execution order.
            inferred: Inferred seconds per event.

        Returns:
            Template statistics, largest attributed time first.

        """
        grouped: dict[str, list[StepEvent]] = {}
        for event in events:
            grouped.setdefault(event.template, []).append(event)
        stats: list[TemplateStat] = [
            TemplateStat(
                template=template,
                count=len(members),
                inferred=sum(inferred[item.index] for item in members),
                measured=sum(
                    item.measured or 0.0
                    for item in members
                    if item.phase != "end"
                ),
                longest=max(inferred[item.index] for item in members),
                example=members[0].message,
            )
            for template, members in grouped.items()
        ]
        return tuple(
            sorted(stats, key=lambda item: item.inferred, reverse=True),
        )

    @staticmethod
    def _slowest(
        *,
        events: tuple[StepEvent, ...],
        inferred: tuple[float, ...],
        limit: int = 25,
    ) -> tuple[SlowStep, ...]:
        """Rank the individually slowest steps.

        Measured durations win over inferred ones.

        Args:
            events: Parsed events in execution order.
            inferred: Inferred seconds per event.
            limit: Maximum rows returned.

        Returns:
            Slowest steps, longest first.

        """
        steps: list[SlowStep] = [
            SlowStep(
                index=event.index,
                label=event.message,
                start=event.elapsed,
                duration=event.measured
                if event.measured is not None and event.phase != "end"
                else inferred[event.index],
                source="measured"
                if event.measured is not None and event.phase != "end"
                else "inferred",
                thread=event.thread,
            )
            for event in events
        ]
        return tuple(
            sorted(steps, key=lambda item: item.duration, reverse=True)[
                :limit
            ],
        )

    @staticmethod
    def _threads(
        *,
        events: tuple[StepEvent, ...],
        inferred: tuple[float, ...],
    ) -> tuple[ThreadStat, ...]:
        """Summarize each worker thread.

        Args:
            events: Parsed events in execution order.
            inferred: Inferred seconds per event.

        Returns:
            Thread statistics, busiest first.

        """
        grouped: dict[str, list[StepEvent]] = {}
        for event in events:
            grouped.setdefault(event.thread, []).append(event)
        stats: list[ThreadStat] = [
            ThreadStat(
                name=name,
                count=len(members),
                first=members[0].elapsed,
                last=members[-1].elapsed,
                busy=sum(inferred[item.index] for item in members),
            )
            for name, members in grouped.items()
        ]
        return tuple(sorted(stats, key=lambda item: item.busy, reverse=True))

    @staticmethod
    def _stages(*, events: tuple[StepEvent, ...]) -> tuple[Stage, ...]:
        """Infer stage intervals from depth-one events.

        Args:
            events: Parsed events in execution order.

        Returns:
            Stage intervals inferred from depth-one boundaries.

        """
        starts: list[int] = [
            event.index for event in events if event.depth == 1
        ]
        stages: list[Stage] = []
        for position, start_index in enumerate(iterable=starts):
            end_index: int = (
                starts[position + 1] - 1
                if position + 1 < len(starts)
                else len(events) - 1
            )
            start: StepEvent = events[start_index]
            end: StepEvent = events[end_index]
            stages.append(
                Stage(
                    name=start.message,
                    start=start.elapsed,
                    end=end.elapsed,
                    event_start=start_index,
                    event_end=end_index,
                    events=end_index - start_index + 1,
                    duration=max(0.0, end.elapsed - start.elapsed),
                ),
            )
        return tuple(stages)

    @staticmethod
    def _bottlenecks(
        *,
        events: tuple[StepEvent, ...],
        duration: float,
        gap_threshold: float,
        repetition_threshold: int,
    ) -> tuple[Bottleneck, ...]:
        """Rank silence gaps and repeated operations.

        Args:
            events: Parsed events in execution order.
            duration: Total run duration in seconds.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            Bottlenecks sorted by descending severity score.

        """
        items: list[Bottleneck] = []
        for previous, current in pairwise(events):
            gap: float = current.elapsed - previous.elapsed
            if gap < gap_threshold:
                continue
            items.append(
                Bottleneck(
                    kind="gap",
                    label=f"after {previous.message}",
                    start=previous.elapsed,
                    end=current.elapsed,
                    duration=gap,
                    count=1,
                    score=gap / max(duration, 0.001),
                ),
            )
        counts: Counter[str] = Counter(event.message for event in events)
        for label, count in counts.most_common(n=20):
            if count < repetition_threshold:
                continue
            matching: tuple[StepEvent, ...] = tuple(
                event for event in events if event.message == label
            )
            span: float = matching[-1].elapsed - matching[0].elapsed
            items.append(
                Bottleneck(
                    kind="repeat",
                    label=label,
                    start=matching[0].elapsed,
                    end=matching[-1].elapsed,
                    duration=span,
                    count=count,
                    score=count / max(len(events), 1),
                ),
            )
        return tuple(sorted(items, key=lambda item: item.score, reverse=True))
