# Copyright (c) 2026 João Lopes.
"""Typed models for step-trace performance analysis."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, final


@dataclass(frozen=True, slots=True)
class StepEvent:
    """Represent one parsed step event.

    Attributes:
        index: Zero-based event position in the source trace.
        timestamp: Original ISO-8601 timestamp text.
        elapsed: Seconds elapsed since the run began.
        depth: Indentation-derived nesting depth.
        message: Step description with indentation removed.
        raw: Original source line without its trailing newline.
        thread: Emitting worker thread; ``main`` when untagged.
        span: Span identifier shared by a begin and end line, if any.
        measured: Seconds measured by a ``@dur`` trailer, an embedded
            ``in 1.2s`` phrase or a span, when known.
        phase: ``begin`` or ``end`` for span lines, else ``point``.
        actor: Text before the first ``:`` or `` — `` separator.
        template: Message with paths and numbers abstracted, so
            repeated operations group together.

    """

    index: int
    timestamp: str
    elapsed: float
    depth: int
    message: str
    raw: str
    thread: str = "main"
    span: int | None = None
    measured: float | None = None
    phase: str = "point"
    actor: str = ""
    template: str = ""


@dataclass(frozen=True, slots=True)
class Stage:
    """Represent a contiguous top-level execution stage.

    Attributes:
        name: Stage label inferred from a depth-one event.
        start: Stage start time in elapsed seconds.
        end: Stage end time in elapsed seconds.
        event_start: Index of the first event in the stage.
        event_end: Index of the last event in the stage.
        events: Number of events assigned to the stage.
        duration: Stage wall-clock duration in seconds.

    """

    name: str
    start: float
    end: float
    event_start: int
    event_end: int
    events: int
    duration: float


@dataclass(frozen=True, slots=True)
class Bottleneck:
    """Describe a suspicious interval or repeated operation.

    Attributes:
        kind: Bottleneck category such as ``gap`` or ``repeat``.
        label: Human-readable operation or interval label.
        start: Start time in elapsed seconds.
        end: End time in elapsed seconds.
        duration: Interval duration in seconds.
        count: Number of contributing events.
        score: Relative severity score; larger values are more suspicious.

    """

    kind: str
    label: str
    start: float
    end: float
    duration: float
    count: int
    score: float


@dataclass(frozen=True, slots=True)
class ActorStat:
    """Aggregate the time attributed to one step actor.

    Attributes:
        name: Actor label, the text before the first ``:``.
        count: Events emitted by the actor.
        inferred: Seconds until each event's successor, summed.
        measured: Explicitly measured seconds, summed.
        share: ``inferred`` as a fraction of all inferred time.
        longest: Largest single inferred interval in seconds.
        p95: 95th-percentile inferred interval in seconds.

    """

    name: str
    count: int
    inferred: float
    measured: float
    share: float
    longest: float
    p95: float


@dataclass(frozen=True, slots=True)
class TemplateStat:
    """Aggregate one repeated operation after path/number abstraction.

    Attributes:
        template: Normalized message shared by every occurrence.
        count: Number of occurrences.
        inferred: Inferred seconds, summed.
        measured: Measured seconds, summed.
        longest: Largest single inferred interval in seconds.
        example: One original message for orientation.

    """

    template: str
    count: int
    inferred: float
    measured: float
    longest: float
    example: str


@dataclass(frozen=True, slots=True)
class SlowStep:
    """Describe one individually slow step.

    Attributes:
        index: Event position in the trace.
        label: Step message.
        start: Start time in elapsed seconds.
        duration: Step duration in seconds.
        source: ``measured`` or ``inferred``.
        thread: Emitting thread.

    """

    index: int
    label: str
    start: float
    duration: float
    source: str
    thread: str


@dataclass(frozen=True, slots=True)
class ThreadStat:
    """Summarize one worker thread's activity.

    Attributes:
        name: Thread name, ``main`` for untagged lines.
        count: Events emitted.
        first: First event time in elapsed seconds.
        last: Last event time in elapsed seconds.
        busy: Inferred seconds attributed to the thread.

    """

    name: str
    count: int
    first: float
    last: float
    busy: float


@dataclass(frozen=True, slots=True)
class ResourceSample:
    """Describe one process-tree resource sample.

    Attributes:
        elapsed: Sample time in elapsed seconds.
        cpu: CPU use in percent of one core, summed over the tree.
        rss: Resident memory in MiB, summed over the tree.
        threads: Thread count across the tree.
        procs: Process count in the tree.
        read: Disk read rate in MiB/s.
        write: Disk write rate in MiB/s.
        scope: ``proc`` for per-process counters, ``system`` for the
            whole-machine fallback.
        raw: Original source line without its trailing newline.

    """

    elapsed: float
    cpu: float
    rss: float
    threads: int
    procs: int
    read: float
    write: float
    scope: str
    raw: str = ""


@dataclass(frozen=True, slots=True)
class ResourceSummary:
    """Summarize every sample of a run.

    Attributes:
        samples: Number of samples.
        mean_cpu: Mean CPU percent of one core.
        peak_cpu: Highest CPU percent of one core.
        peak_rss: Highest resident memory in MiB.
        read: Total MiB read, integrated over the samples.
        write: Total MiB written, integrated over the samples.
        peak_procs: Largest process count.

    """

    samples: int
    mean_cpu: float
    peak_cpu: float
    peak_rss: float
    read: float
    write: float
    peak_procs: int


@dataclass(frozen=True, slots=True)
class TreeNode:
    """Describe one node of a thread's execution tree.

    A node runs from its event to the next event on the same thread at
    the same or a shallower depth, or to its measured span end.

    Attributes:
        id: Node position in the run's node tuple.
        event: Index of the event that opened the node.
        parent: Parent node id, ``None`` for lane roots.
        children: Directly nested node ids.
        thread: Owning thread.
        level: Nesting level, zero for lane roots.
        start: Start in elapsed seconds.
        end: End in elapsed seconds.
        total: Wall-clock seconds from start to end.
        self_time: ``total`` minus the children's totals.

    """

    id: int
    event: int
    parent: int | None
    children: tuple[int, ...]
    thread: str
    level: int
    start: float
    end: float
    total: float
    self_time: float


@dataclass(frozen=True, slots=True)
class PerformanceRun:
    """Contain a fully analyzed tool execution.

    Attributes:
        tool: Normalized tool identifier.
        source: Source ``steps.txt`` path.
        events: Parsed events in source order.
        stages: Inferred stage intervals.
        bottlenecks: Ranked suspicious intervals and repeated operations.
        duration: Total elapsed duration in seconds.
        event_rate: Average events per second.
        largest_gap: Largest silence between adjacent events in seconds.
        actors: Time attributed to each actor, largest first.
        templates: Repeated operations by attributed time, largest first.
        slowest: Individually slowest steps, largest first.
        threads: Per-thread activity, busiest first.
        silent: Seconds spent in gaps at or above the gap threshold.
        samples: Resource samples in time order, empty when not sampled.
        resources: Aggregate of ``samples``.
        nodes: Per-thread execution trees, flattened in event order.

    """

    tool: str
    source: Path
    events: tuple[StepEvent, ...]
    stages: tuple[Stage, ...]
    bottlenecks: tuple[Bottleneck, ...]
    duration: float
    event_rate: float
    largest_gap: float
    actors: tuple[ActorStat, ...] = ()
    templates: tuple[TemplateStat, ...] = ()
    slowest: tuple[SlowStep, ...] = ()
    threads: tuple[ThreadStat, ...] = ()
    silent: float = 0.0
    samples: tuple[ResourceSample, ...] = ()
    resources: ResourceSummary | None = None
    nodes: tuple[TreeNode, ...] = ()


@final
class Constants:
    """Group module-level constants.

    Attributes:
        step_file: Grouped module constant.

    """

    step_file: Final[str] = "steps.txt"
