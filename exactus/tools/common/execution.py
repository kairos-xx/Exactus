# Copyright (c) 2026
"""Shared standalone exactus entry-point reporting."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from json import JSONDecodeError, dumps, loads
from logging import Logger, getLogger
from os import (
    close,
    dup,
    dup2,
    environ,
    getpid,
    kill,
    pathsep,
    pipe,
    read,
    stat_result,
)
from pathlib import Path
from shlex import join as shlex_join
from shutil import move, rmtree
from signal import Handlers, Signals, signal
from stat import S_IRWXU, S_ISREG
from sys import argv, stderr, stdout
from threading import Event, Lock, Thread, current_thread, main_thread
from time import monotonic
from traceback import format_exc
from types import FrameType, TracebackType
from typing import TYPE_CHECKING, Final, Self, cast
from typing import final as _group_final_final

from exactus.packages.markdown import TemplateEngineError
from exactus.packages.pmanager.runtime import Client, Descriptor, Discovery
from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityFile,
    ActivityHeartbeat,
    ActivityLog,
    ActivityProgress,
    ActivityTables,
)
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.cli import consume
from exactus.tools.common.collect_files import collect_report_files, requested
from exactus.tools.common.config import (
    discovery_from_environment,
    reports_anchor,
    reports_directory,
)
from exactus.tools.common.conflict_copies import clear_conflict_copies
from exactus.tools.common.envelope import RunFacts
from exactus.tools.common.json_types import JsonDict, JsonValue
from exactus.tools.common.models import (
    ToolRequest,
    ToolRunResult,
    result_stats,
)
from exactus.tools.common.process_control import (
    exit_if_replaced,
    new_run_id,
    pause_tree,
    resume_tree,
    terminate_tree,
)
from exactus.tools.common.progress import utc_now
from exactus.tools.common.registry import (
    RegistryTables,
    RunBeat,
    RunClaim,
    RunRegistry,
    run_context,
)
from exactus.tools.common.report_comparison import (
    capture as capture_previous_reports,
)
from exactus.tools.common.report_comparison import (
    clear as clear_previous_reports,
)
from exactus.tools.common.report_comparison import (
    previous_duration as previous_report_duration,
)
from exactus.tools.common.runtime import (
    Progress,
    clear_progress,
    current_progress,
    emit_progress,
    publish_progress,
    source_activity,
)
from exactus.tools.common.stderr_capture import StderrRecorder, StderrTables
from exactus.tools.common.terminal import ExactusTerminal, ResultRow
from exactus.tools.reports.bundle import Constants as ReportConstants
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.reports.render import NormalizedStamp, ReportTemplates

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from exactus.tools.common.catalog import PipelineSpec, ToolSpec
    from exactus.tools.common.config import ConfigFile
    from exactus.tools.common.registry import RunRecord
type SignalHandler = (
    Callable[[int, FrameType | None], None] | Handlers | int | None
)
type AnalyzerException = Exception | SystemExit | KeyboardInterrupt


@_group_final_final
class Constants:
    """Group module-level constants.

    Attributes:
        logger: Grouped module constant.

    """

    logger: Final[Logger] = getLogger(name=__name__)


class ExactusEntrypointTables:
    """Store common standalone exactus CLI constants.

    Attributes:
        heartbeat_seconds: Heartbeat seconds.
        checkpoint_timeout_seconds: Maximum dependent checkpoint handshake.
        terminate_signals: Signals terminating a run as interrupted.
        report_output: Report output.
        capture_limit: Captured output tail bytes kept in memory.
        artifact_embed_limit: Maximum artifact bytes embedded in a report.
        runner_files: Files the runner itself writes for every run.

    """

    report_output: Final[str] = "--report-output"
    heartbeat_seconds: Final[float] = 1.0
    checkpoint_timeout_seconds: Final[float] = 5.0
    terminate_signals: Final[tuple[Signals, ...]] = tuple(
        Signals.__members__[name]
        for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT", "SIGBREAK")
        if name in Signals.__members__
    )
    capture_limit: Final[int] = 262144
    artifact_embed_limit: Final[int] = 65536
    runner_files: Final[frozenset[str]] = frozenset(
        {ActivityTables.file_name, StderrTables.log_name, "stdout.log"},
    )


@dataclass(frozen=True, slots=True)
class _RunContext:
    """Represent run context.

    Attributes:
        output: Output.
        analyzer: Analyzer.
        started_at: Started at.
        started: Started.
        interrupted: Interrupted.
        stop: Stop.
        write_lock: Write lock.
        registry: Shared cross-process run registry.
        run_id: Run id.
        pipeline_run_id: Pipeline run id.
        previous_duration_seconds: Duration of the previous successful or
            failed run, when a report already existed.
        log: Recent activity events published in ``@activity.json``.
        stderr: Line recorder of the captured standard error.

    """

    output: Path
    analyzer: str
    started_at: str
    started: float
    interrupted: Event
    stop: Event
    write_lock: Lock
    registry: RunRegistry
    run_id: str
    pipeline_run_id: str | None
    previous_duration_seconds: float | None
    log: ActivityLog
    stderr: StderrRecorder


@dataclass(slots=True, frozen=True)
class ExactusRunIds:
    """Run identifiers injected by an orchestrating pipeline.

    Attributes:
        run_id: Unique tool run identifier; generated when omitted.
        pipeline_run_id: Owning pipeline run identifier.

    """

    run_id: str | None = None
    pipeline_run_id: str | None = None


def _activity_path(*, output: Path) -> Path:
    """Return a run's ``ARTIFACTS/@activity.json`` path.

    Args:
        output: Analyzer report directory.

    Returns:
        The activity document path.

    """
    return output / "ARTIFACTS" / ActivityTables.file_name


def _write_activity(*, output: Path, document: ActivityDocument) -> None:
    """Atomically publish one ``@activity.json`` document.

    Args:
        output: Analyzer report directory.
        document: Heartbeat, progress and activity of the run.

    """
    ActivityFile.write(path=_activity_path(output=output), document=document)


def _activity_progress(*, fields: dict[str, JsonValue]) -> ActivityProgress:
    """Convert normalized progress fields to the activity block.

    Args:
        fields: Output of ``_progress_fields``.

    Returns:
        The ``progress`` block of ``@activity.json``.

    """
    fraction: JsonValue = fields.get("progress")
    completed: JsonValue = fields.get("completed")
    total: JsonValue = fields.get("total")
    step: JsonValue = fields.get("step")
    detail: JsonValue = fields.get("detail")
    workers: JsonValue = fields.get("workers")
    hierarchy: JsonValue = fields.get("hierarchy")
    return ActivityProgress(
        completed=completed if isinstance(completed, int) else 0,
        total=total if isinstance(total, int) else 0,
        fraction=float(fraction) if isinstance(fraction, float) else 0.0,
        step=step if isinstance(step, str) else "",
        current=detail if isinstance(detail, str) else "",
        workers=(
            cast(typ="dict[str, JsonValue]", val=workers)
            if isinstance(workers, dict)
            else None
        ),
        hierarchy=(
            cast(typ="dict[str, JsonValue]", val=hierarchy)
            if isinstance(hierarchy, dict)
            else None
        ),
    )


def _activity(
    *,
    context: _RunContext,
    status: str,
    phase: str,
    fields: dict[str, JsonValue],
    finished_at: str | None = None,
) -> ActivityDocument:
    """Build the ``@activity.json`` document of a running or ended run.

    Args:
        context: Shared run state for heartbeat and signal helpers.
        status: Run lifecycle status.
        phase: Heartbeat phase (``running``, ``finished``, ...).
        fields: Output of ``_progress_fields``.
        finished_at: Finish timestamp of an ended run.

    Returns:
        The complete activity document.

    """
    now: str = utc_now()
    extra: dict[str, JsonValue] = {}
    if context.previous_duration_seconds is not None:
        extra["previous_duration_seconds"] = round(
            number=context.previous_duration_seconds,
            ndigits=3,
        )
    return ActivityDocument(
        kind="tool",
        name=context.analyzer,
        status=status,
        run_id=context.run_id,
        pipeline_run_id=context.pipeline_run_id,
        started_at=context.started_at,
        updated_at=now,
        finished_at=finished_at,
        elapsed_seconds=monotonic() - context.started,
        heartbeat=ActivityHeartbeat(
            pid=getpid(),
            alive=phase == "running",
            last_beat=now,
            phase=phase,
            interval_seconds=ExactusEntrypointTables.heartbeat_seconds,
        ),
        progress=_activity_progress(fields=fields),
        events=context.log.events(),
        events_dropped=context.log.dropped(),
        extra=extra,
    )


def _report_output(*, analyzer: str) -> Path:
    """Remove and resolve the common report-output argument.

    Args:
        analyzer: Stable exactus analyzer name.

    Returns:
        Directory receiving the common ReportBundle run report.

    Raises:
        ValueError: If ``--report-output`` has no following path.

    """
    if ExactusEntrypointTables.report_output not in argv:
        root: str | None = environ.get("EXACTUS_ROOT")
        start: Path = Path(root).resolve() if root else Path.cwd()
        files: tuple[ConfigFile, ...] = discovery_from_environment(start=start)
        directory: Path = reports_directory(files=files)
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=analyzer,
        )
        name: str = (
            tool.output
            if tool is not None
            else analyzer.removeprefix("exactus_").upper().replace("-", "_")
        )
        return reports_anchor(files=files, start=start) / directory / name
    index: int = argv.index(ExactusEntrypointTables.report_output)
    if index + 1 >= len(argv):
        msg: str = "--report-output requires a path"
        raise ValueError(msg)
    output: Path = Path(argv[index + 1])
    del argv[index : index + 2]
    return output


def _terminate_live_run(*, output: Path) -> None:
    """Terminate a live run recorded in ``ARTIFACTS/@activity.json``.

    Args:
        output: Analyzer report directory.

    """
    document: ActivityDocument | None = ActivityFile.read(
        path=_activity_path(output=output),
    )
    if document is None:
        return
    pid: int | None = document.heartbeat.pid
    if document.status == "RUNNING" and pid is not None:
        terminate_tree(pid=pid, replaced=True)


def _claim_run(
    *,
    analyzer: str,
    output: Path,
    run_id: str,
    pipeline_run_id: str | None,
) -> RunRegistry:
    """Register this run and terminate every live conflicting run.

    Args:
        analyzer: Stable exactus analyzer name.
        output: Resolved analyzer report directory.
        run_id: Unique run identifier.
        pipeline_run_id: Owning pipeline run identifier, when any.

    Returns:
        The shared registry this run was recorded in.

    """
    registry: RunRegistry = RunRegistry.for_output(output=output)
    conflicts: tuple[RunRecord, ...] | None = registry.claim(
        request=RunClaim(
            kind="tool",
            identifier=analyzer,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            pid=getpid(),
            output=output,
            targets=(str(object=output.resolve()),),
        ),
    )
    if conflicts is None:
        _terminate_live_run(output=output)
        return registry
    conflict: RunRecord
    for conflict in conflicts:
        terminate_tree(pid=conflict.pid, replaced=True)
    return registry


def _preserved_output(*, output: Path, run_id: str) -> Path:
    """Return a unique sibling path for protected report evidence.

    Args:
        output: Analyzer report directory that could not be emptied.
        run_id: Unique run identifier disambiguating preservation copies.

    Returns:
        Nonexistent sibling path receiving the prior output directory.

    """
    candidate: Path = output.with_name(
        name=f"{output.name}.preserved-{run_id}",
    )
    serial: int = 1
    while candidate.exists():
        serial += 1
        candidate = output.with_name(
            name=f"{output.name}.preserved-{run_id}-{serial}",
        )
    return candidate


def _rmtree_writable(
    func: Callable[[str], None],
    path: str,
    _exc: BaseException,
) -> None:
    """Retry a failed `rmtree` step after making the entry writable.

    Artifacts extracted from install media keep read-only permissions:
    children sit inside ``dr-xr-xr-x`` directories, so ``unlink`` fails on
    the parent's missing write bit — both the entry and its parent must
    regain owner writability before the retry can succeed.

    Args:
        func: Removal operation to retry (``rmdir``, ``unlink``, ``scandir``).
        path: Entry that failed removal.
        _exc: Exception instance supplied by `rmtree` via ``onexc``.

    """
    candidate: Path
    for candidate in (Path(path), Path(path).parent):
        with suppress(OSError):
            candidate.chmod(mode=S_IRWXU)
    func(path)


def _remove_tree(*, path: Path) -> None:
    """Delete one output tree, forcing read-only artifacts writable first.

    Args:
        path: Directory to delete recursively.

    """
    rmtree(path=path, onexc=_rmtree_writable)


def _clear_directory(*, path: Path) -> None:
    """Remove every child of ``path`` while keeping the directory itself.

    Keeping the directory inode stable avoids Finder/IDE duplicate-folder
    artifacts (e.g. ``KWARGS_TYPEHINTS 2``) when the output tree is recreated
    while a file browser has the folder open.

    Args:
        path: Directory whose children should be removed.

    """
    with suppress(OSError):
        path.chmod(mode=S_IRWXU)
    child: Path
    for child in path.iterdir():
        try:
            if child.is_dir() and (not child.is_symlink()):
                _remove_tree(path=child)
            else:
                child.unlink()
        except OSError:
            with suppress(OSError):
                child.chmod(mode=S_IRWXU)
            if child.is_dir() and (not child.is_symlink()):
                _remove_tree(path=child)
            else:
                child.unlink()


def _prepare_output(*, output: Path, run_id: str) -> None:
    """Empty the report directory while preserving protected evidence.

    Guest artifacts can retain restrictive ownership from a VM or container.
    Deleting them must not block the next exactus, so an output tree that
    cannot
    be emptied is moved aside intact and the current run receives a fresh
    path. Stale preserved copies from earlier runs are reclaimed first.

    The existing directory is kept and only its contents are removed, so
    external file browsers that have the folder open do not create duplicate
    folder names when the analyzer regenerates the report.

    Args:
        output: Analyzer report directory.
        run_id: Unique run identifier used in the preservation name.

    """
    stale: Path
    for stale in output.parent.glob(pattern=f"{output.name}.preserved-*"):
        with suppress(OSError):
            if stale.is_dir() and (not stale.is_symlink()):
                _remove_tree(path=stale)
            else:
                stale.unlink()
    if not output.exists() and (not output.is_symlink()):
        return
    try:
        if output.is_dir() and (not output.is_symlink()):
            _clear_directory(path=output)
        else:
            output.unlink()
    except OSError:
        _ = output.rename(
            target=_preserved_output(output=output, run_id=run_id),
        )


def _progress_fields(*, payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Normalize progress payload fields for merged publication.

    Args:
        payload: Latest in-process progress payload.

    Returns:
        Progress fields safe to embed in the heartbeat and registry.

    """
    raw_progress: JsonValue = payload.get("progress")
    raw_completed: JsonValue = payload.get("completed")
    raw_total: JsonValue = payload.get("total")
    raw_step: JsonValue = payload.get("step")
    raw_detail: JsonValue = payload.get("detail")
    fraction: float = (
        min(max(float(raw_progress), 0.0), 1.0)
        if isinstance(raw_progress, (int, float))
        and (not isinstance(raw_progress, bool))
        else 0.0
    )
    result: dict[str, JsonValue] = {
        "progress": fraction,
        "completed": (
            raw_completed
            if isinstance(raw_completed, int)
            and (not isinstance(raw_completed, bool))
            else 0
        ),
        "total": (
            raw_total
            if isinstance(raw_total, int) and (not isinstance(raw_total, bool))
            else 0
        ),
        "step": raw_step if isinstance(raw_step, str) else "running",
        "detail": raw_detail if isinstance(raw_detail, str) else "",
    }
    workers: JsonValue = payload.get("workers")
    if isinstance(workers, dict):
        result["workers"] = dict(workers)
    hierarchy: JsonValue = payload.get("hierarchy")
    if isinstance(hierarchy, dict):
        result["hierarchy"] = dict(hierarchy)
    return result


def _heartbeat(*, context: _RunContext) -> None:
    """Refresh the merged heartbeat file and shared registry row.

    The per-directory ``ARTIFACTS/@activity.json`` is the user-facing
    heartbeat, progress and activity document; the registry row is the
    cross-process source of truth used for ownership and kill decisions.

    Args:
        context: Shared run state for heartbeat and signal helpers.

    """
    context.output.mkdir(parents=True, exist_ok=True)
    last_step: JsonValue = None
    while not context.stop.is_set():
        fields: dict[str, JsonValue] = _progress_fields(
            payload=current_progress(),
        )
        if fields["step"] != last_step:
            last_step = fields["step"]
            detail: JsonValue = fields["detail"]
            context.log.record(
                message=f"step: {last_step}"
                + (
                    f" ({detail})"
                    if isinstance(detail, str) and detail
                    else ""
                ),
            )
        elapsed_seconds: float = round(
            number=monotonic() - context.started,
            ndigits=3,
        )
        with suppress(OSError):
            context.output.mkdir(parents=True, exist_ok=True)
            with context.write_lock:
                if not context.stop.is_set():
                    _write_activity(
                        output=context.output,
                        document=_activity(
                            context=context,
                            status="RUNNING",
                            phase="running",
                            fields=fields,
                        ),
                    )
        context.registry.beat(
            pulse=RunBeat(
                run_id=context.run_id,
                progress=cast(typ="float", val=fields["progress"]),
                step=cast(typ="str", val=fields["step"]),
                detail=cast(typ="str", val=fields["detail"]),
                elapsed_seconds=elapsed_seconds,
            ),
        )
        if "EXACTUS_ORCHESTRATED" not in environ:
            ExactusTerminal.standalone_progress(
                tool=context.analyzer,
                fraction=cast(typ="float", val=fields["progress"]),
                step=cast(typ="str", val=fields["step"]),
            )
        _ = context.stop.wait(
            timeout=ExactusEntrypointTables.heartbeat_seconds,
        )


def _report_snapshot(*, output: Path) -> dict[Path, tuple[int, int]]:
    """Capture analyzer report artifacts before or after execution.

    Args:
        output: Analyzer report directory.

    Returns:
        Mapping of report paths to modification time and size.

    """
    snapshot: dict[Path, tuple[int, int]] = {}
    for suffix in ("*.md", "*.json"):
        for path in output.glob(pattern=suffix):
            if path.name in ExactusEntrypointTables.runner_files:
                continue
            try:
                info: stat_result = path.stat()
            except OSError:
                continue
            snapshot[path] = (info.st_mtime_ns, info.st_size)
    return snapshot


def _report_emitted(
    *,
    output: Path,
    before: dict[Path, tuple[int, int]],
) -> bool:
    """Return whether this execution emitted Markdown and JSON reports.

    Args:
        output: Analyzer report directory.
        before: Artifact snapshot captured before analyzer execution.

    Returns:
        ``True`` when both report formats were created or rewritten.

    """
    after: dict[Path, tuple[int, int]] = _report_snapshot(output=output)
    changed: frozenset[Path] = frozenset(
        (
            path
            for path, signature in after.items()
            if before.get(path) != signature
        ),
    )
    return any(path.suffix == ".md" for path in changed) and any(
        path.suffix == ".json" for path in changed
    )


class _StreamTee:
    """Duplicate one descriptor's writes into a bounded tail buffer.

    The descriptor is redirected through a pipe; a reader thread forwards
    every chunk to the original descriptor, appends it to a transcript
    file in the report directory, and retains a bounded tail for the
    fallback report. Child processes inheriting the descriptor are
    captured as well.
    """

    def __init__(
        self,
        *,
        fd: int,
        transcript: Path,
        recorder: StderrRecorder | None = None,
    ) -> None:
        """Redirect ``fd`` through a teeing pipe.

        Args:
            fd: File descriptor to capture (``1`` or ``2``).
            transcript: File receiving the complete captured stream.
            recorder: Line recorder fed with every chunk, when the
                stream is standard error.

        """
        self._fd: int = fd
        self._transcript: Path = transcript
        self._recorder: StderrRecorder | None = recorder
        self._saved: int = dup(fd)
        self._read_fd: int
        write_fd: int
        self._read_fd, write_fd = pipe()
        _ = dup2(fd=write_fd, fd2=fd)
        close(fd=write_fd)
        self._chunks: deque[bytes] = deque()
        self._size: int = 0
        self._lock: Lock = Lock()
        self._thread: Thread = Thread(target=self._pump, daemon=True)
        self._thread.start()

    @property
    def original_fd(self) -> int:
        """The terminal stream descriptor saved before output capture.

        Returns:
            Descriptor captured before redirection began.

        """
        return self._saved

    def stop(self) -> str:
        """Restore the descriptor and return the captured tail.

        Returns:
            Captured tail text bounded by the configured limit.

        """
        _ = dup2(fd=self._saved, fd2=self._fd)
        close(fd=self._saved)
        self._thread.join(timeout=10)
        return b"".join(self._chunks).decode(
            encoding="utf-8",
            errors="replace",
        )

    def _pump(self) -> None:
        """Forward captured chunks until the redirected fd closes."""
        with self._transcript.open(mode="wb") as log:
            while chunk := read(self._read_fd, 65536):
                _ = consume(value=log.write(chunk))
                if self._recorder is not None:
                    self._recorder.feed(chunk=chunk)
                with self._lock:
                    self._chunks.append(chunk)
                    self._size += len(chunk)
                    while self._size > ExactusEntrypointTables.capture_limit:
                        self._size -= len(self._chunks.popleft())
        close(fd=self._read_fd)


def _capture_streams(
    *,
    output: Path,
    recorder: StderrRecorder | None = None,
) -> tuple[_StreamTee, ...]:
    """Redirect stdout and stderr through transcript tees.

    Args:
        output: Analyzer report directory receiving transcript logs.
        recorder: Line recorder describing standard error.

    Returns:
        Started tees for descriptors 1 and 2, or empty when the
        descriptors cannot be redirected.

    """
    artifacts: Path = output / "ARTIFACTS"
    artifacts.mkdir(parents=True, exist_ok=True)
    tees: list[_StreamTee] = []
    try:
        tees.append(
            _StreamTee(
                fd=stdout.fileno(),
                transcript=artifacts / "stdout.log",
            ),
        )
        tees.append(
            _StreamTee(
                fd=stderr.fileno(),
                transcript=artifacts / StderrTables.log_name,
                recorder=recorder,
            ),
        )
    except OSError:
        for tee in tees:
            with suppress(OSError):
                _ = consume(value=tee.stop())
        return ()
    return tuple(tees)


def _stop_streams(*, tees: tuple[_StreamTee, ...]) -> tuple[str, str]:
    """Flush streams, restore descriptors, and return captured tails.

    Args:
        tees: Active stream tees created by ``_capture_streams``.

    Returns:
        Captured stdout and stderr tail text.

    """
    if not tees:
        return ("", "")
    _ = stdout.flush()
    _ = stderr.flush()
    return (tees[0].stop(), tees[1].stop())


def _report_artifacts(*, output: Path, stem: str) -> list[JsonValue]:
    """List analyzer-emitted artifacts with embedded small payloads.

    Args:
        output: Analyzer report directory.
        stem: Report bundle filename stem excluded from the listing.

    Returns:
        Artifact descriptors containing name, path, size, and parsed
        content for small JSON documents.

    """
    excluded: frozenset[str] = frozenset(
        {
            *ExactusEntrypointTables.runner_files,
            *(
                f"ARTIFACTS/{name}"
                for name in ExactusEntrypointTables.runner_files
            ),
            f"{stem}.md",
            f"{stem}.json",
        },
    )
    artifacts: list[JsonValue] = []
    path: Path
    try:
        candidates: tuple[Path, ...] = tuple(sorted(output.rglob(pattern="*")))
    except OSError:
        candidates = ()
    for path in candidates:
        if path.is_symlink():
            continue
        try:
            info: stat_result = path.stat()
        except OSError:
            continue
        if not S_ISREG(info.st_mode):
            continue
        relative: str = path.relative_to(output).as_posix()
        if (
            relative in excluded
            or relative.startswith(f"{stem}_web/")
            or any(part.startswith(".") for part in Path(relative).parts)
        ):
            continue
        entry: dict[str, JsonValue] = {
            "name": path.name,
            "path": relative,
            "bytes": info.st_size,
        }
        if (
            path.suffix == ".json"
            and info.st_size <= ExactusEntrypointTables.artifact_embed_limit
        ):
            try:
                entry["content"] = loads(s=path.read_text(encoding="utf-8"))
            except (OSError, JSONDecodeError):
                entry["content"] = None
        artifacts.append(entry)
    return artifacts


@dataclass(frozen=True, slots=True)
class FallbackResult:
    """Everything a fallback report needs to render the full run.

    Attributes:
        output: Analyzer report directory.
        analyzer: Stable analyzer identifier.
        title: Human-readable exactus title.
        status: Analyzer exit status.
        command: Executed command line.
        elapsed_seconds: Analyzer wall-clock runtime.
        stdout_tail: Captured standard-output tail.
        stderr_tail: Captured standard-error tail.
        error: Unhandled analyzer error, when present.

    """

    output: Path
    analyzer: str
    title: str
    status: int
    command: str
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str
    error: str | None


def _fallback_markdown(
    *,
    result: FallbackResult,
    artifacts: list[JsonValue],
) -> str:
    """Render a full fallback report body from captured execution data.

    Args:
        result: Captured analyzer execution result.
        artifacts: Artifact descriptors from ``_report_artifacts``.

    Returns:
        Markdown report containing the complete analyzer result.

    """
    lines: list[str] = [
        f"# {result.title}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Analyzer | `{result.analyzer}` |",
        f"| Result | **{('PASS' if result.status == 0 else 'FAIL')}** |",
        f"| Exit status | `{result.status}` |",
        f"| Elapsed | `{result.elapsed_seconds:.3f}s` |",
        f"| Command | `{result.command}` |",
        "",
        "## Analyzer output",
        "",
        "```text",
        result.stdout_tail.rstrip() or "(no output)",
        "```",
        "",
        "## Diagnostics",
        "",
        "```text",
        result.stderr_tail.rstrip() or "(no output)",
        "```",
        "",
    ]
    if result.error:
        lines.extend(
            ("## Execution error", "", "```text", result.error, "```", ""),
        )
    lines.extend(("## Emitted artifacts", ""))
    if not artifacts:
        lines.extend(("The analyzer emitted no report artifacts.", ""))
    else:
        lines.extend(("| Artifact | Bytes |", "| --- | ---: |"))
        lines.extend(
            f"| `{artifact.get('path')}` | {artifact.get('bytes')} |"
            for artifact in artifacts
            if isinstance(artifact, dict)
        )
        lines.append("")
        artifact: JsonValue
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            content: JsonValue = artifact.get("content")
            if not isinstance(content, dict | list):
                continue
            lines.extend(
                (
                    f"### `{artifact.get('path')}`",
                    "",
                    "```json",
                    dumps(obj=content, indent=2, sort_keys=True),
                    "```",
                    "",
                ),
            )
    return "\n".join(lines)


def _fallback_resume(*, result: FallbackResult) -> str:
    """Lift a ``prog: error: message`` line out of the stderr tail.

    Analyzers that reject their command line through
    ``ArgumentParser.error`` exit before emitting a report; their usage
    message is the most useful resume text available.

    Args:
        result: Captured analyzer execution result.

    Returns:
        The parser's error message, or an empty string when the stderr
        tail does not end with an ``error:`` line.

    """
    tail: str = result.stderr_tail.rstrip()
    if not tail:
        return ""
    _prefix, marker, message = tail.splitlines()[-1].rpartition("error: ")
    if not marker or not message.strip():
        return ""
    return message.strip()


def _write_fallback_report(*, result: FallbackResult) -> None:
    """Write a report only when the analyzer could not emit one itself.

    Args:
        result: Captured analyzer execution result.

    """
    stem: str = result.output.name.upper()
    artifacts: list[JsonValue] = _report_artifacts(
        output=result.output,
        stem=stem,
    )
    _ = ReportBundle.write(
        paths=ReportPaths(
            markdown=result.output / f"{stem}.md",
            json=result.output / f"{stem}.json",
            web=result.output / f"{stem}_web",
        ),
        analyzer=result.analyzer,
        title=result.title,
        markdown=_fallback_markdown(result=result, artifacts=artifacts),
        data={
            "status": result.status,
            "passed": result.status == 0,
            "standalone": True,
            "command": result.command,
            "elapsed_seconds": result.elapsed_seconds,
            "output": {
                "stdout": result.stdout_tail,
                "stderr": result.stderr_tail,
            },
            "artifacts": artifacts,
            "error": result.error,
            "resume": _fallback_resume(result=result),
            "report_generation": "fallback",
        },
    )


def _install_terminate_handlers(
    *,
    context: _RunContext,
    output_fd: int = 2,
) -> dict[Signals, SignalHandler]:
    """Install handlers that mark the heartbeat interrupted on signals.

    Each handler writes a terminal ``INTERRUPT`` heartbeat and then
    re-delivers the signal under the default disposition so the process
    still dies by that signal and its parent observes a real signal
    termination.

    When another exactus replaces this run, print the replacement notice
    through the original stream and exit with status 130 instead.

    Args:
        context: Shared run state for heartbeat and signal helpers.
        output_fd: Original terminal stream for replacement notices.

    Returns:
        Previously installed handlers keyed by signal; empty when not
        running on the main thread.

    """
    previous: dict[Signals, SignalHandler] = {}

    def _terminate(signum: int, _frame: FrameType | None) -> None:
        """Record the interrupt and re-raise the terminating signal.

        Args:
            signum: Received signal number.
            _frame: Interrupted stack frame.

        """
        exit_if_replaced(output_fd=output_fd)
        context.interrupted.set()
        context.stop.set()
        context.log.record(
            level="warning",
            message=f"interrupted by signal {Signals(value=signum).name}",
        )
        with context.write_lock, suppress(OSError):
            _write_activity(
                output=context.output,
                document=_activity(
                    context=context,
                    status="INTERRUPT",
                    phase="interrupted",
                    fields=_progress_fields(payload=current_progress()),
                    finished_at=utc_now(),
                ),
            )
        context.registry.finish(
            run_id=context.run_id,
            status="INTERRUPT",
            elapsed_seconds=monotonic() - context.started,
        )
        _ = signal(signalnum=signum, handler=Handlers.SIG_DFL)
        kill(getpid(), signum)

    if (
        current_thread() is main_thread()
        and environ.get("EXACTUS_PMANAGER_WORKER") != "1"
    ):
        for signum in ExactusEntrypointTables.terminate_signals:
            previous[signum] = signal(signalnum=signum, handler=_terminate)
    return previous


def _restore_terminate_handlers(
    *,
    previous: dict[Signals, SignalHandler],
) -> None:
    """Restore signal handlers saved before a run.

    Args:
        previous: Handlers to reinstall keyed by signal.

    """
    for signum, handler in previous.items():
        with suppress(OSError, ValueError):
            _ = signal(signalnum=signum, handler=handler)


@contextmanager
def _analyzer_environment(*, output: Path) -> Generator[None]:
    """Expose the report directory and source root to the analyzer.

    Args:
        output: Analyzer report directory.

    Yields:
        Nothing; environment variables are restored on exit.

    """
    previous_output: str | None = environ.get("EXACTUS_REPORT_OUTPUT")
    previous_pythonpath: str | None = environ.get("PYTHONPATH")
    root: Path = Path.cwd().resolve()
    environ["EXACTUS_REPORT_OUTPUT"] = str(object=output.resolve())
    environ["PYTHONPATH"] = pathsep.join(
        (
            str(object=root / "src"),
            str(object=root),
            *((previous_pythonpath,) if previous_pythonpath else ()),
        ),
    )
    try:
        yield
    finally:
        if previous_output is None:
            _ = environ.pop("EXACTUS_REPORT_OUTPUT", default=None)
        else:
            environ["EXACTUS_REPORT_OUTPUT"] = previous_output
        if previous_pythonpath is None:
            _ = environ.pop("PYTHONPATH", default=None)
        else:
            environ["PYTHONPATH"] = previous_pythonpath


class _InvocationCapture:
    """Capture analyzer failures at the execution boundary."""

    def __init__(self) -> None:
        """Initialize an empty invocation outcome."""
        self.exception: AnalyzerException | None = None
        self.traceback: str = ""

    def __enter__(self) -> Self:
        """Enter the analyzer invocation boundary.

        Returns:
            The resulting value.
            Enter the analyzer invocation boundary.

        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Capture supported analyzer failures for report generation.

        Args:
            exception: Exception.
            exception_type: Exception type.
            traceback: Traceback.

        Returns:
            The resulting value.

        """
        del exception_type, traceback
        supported: bool = isinstance(
            exception,
            (Exception, SystemExit, KeyboardInterrupt),
        )
        if not supported:
            return False
        self.exception = exception
        self.traceback = format_exc()
        return True


def _invoke(
    *,
    main: Callable[[], int],
    context: _RunContext,
) -> tuple[int, str | None]:
    """Execute the analyzer and normalize its exit status.

    Args:
        main: Analyzer main function.
        context: Shared run state for heartbeat and signal helpers.

    Returns:
        Analyzer exit status paired with an error description when the
        analyzer raised instead of returning a status.

    """
    capture: _InvocationCapture = _InvocationCapture()
    status: int = 1
    with _analyzer_environment(output=context.output), capture:
        status = main()
    exception: AnalyzerException | None = capture.exception
    if exception is None:
        return (status, None)
    if isinstance(exception, SystemExit):
        code: int | str | None = exception.code
        status = code if isinstance(code, int) else 0 if code is None else 1
        return (status, f"SystemExit: {exception.code}" if status else None)
    if isinstance(exception, KeyboardInterrupt):
        context.interrupted.set()
        return (130, "KeyboardInterrupt")
    Constants.logger.error(
        "Analyzer run failed: %s\n%s",
        exception,
        capture.traceback,
    )
    return (
        1,
        f"{type(exception).__name__}: {exception}\n\n{capture.traceback}",
    )


def _final_pulse(*, context: _RunContext, status: int) -> None:
    """Write the terminal ``@activity.json`` of a finished analyzer run.

    Args:
        context: Shared run state for heartbeat and signal helpers.
        status: Analyzer exit status.

    """
    interrupted: bool = context.interrupted.is_set()
    final: str = (
        "INTERRUPT" if interrupted else "DONE" if status == 0 else "FAIL"
    )
    elapsed_seconds: float = round(
        number=monotonic() - context.started,
        ndigits=3,
    )
    context.log.record(
        level="info" if final == "DONE" else "warning",
        message=(
            f"finished: {final} (exit status {status}) in"
            f" {elapsed_seconds:.3f}s"
        ),
    )
    extra: dict[str, JsonValue] = {"exit_code": status}
    if context.previous_duration_seconds is not None:
        extra["previous_duration_seconds"] = round(
            number=context.previous_duration_seconds,
            ndigits=3,
        )
    _write_activity(
        output=context.output,
        document=replace(
            _activity(
                context=context,
                status=final,
                phase="interrupted" if interrupted else "finished",
                fields=_progress_fields(payload=current_progress()),
                finished_at=utc_now(),
            ),
            extra=extra,
        ),
    )
    context.registry.finish(
        run_id=context.run_id,
        status=final,
        elapsed_seconds=elapsed_seconds,
    )


def _finish_stderr(*, context: _RunContext) -> None:
    """Guarantee ``ARTIFACTS/stderr.log`` once the stream tees stopped.

    A run whose streams could not be redirected still gets an empty
    ``stderr.log``.

    Args:
        context: Shared run state for heartbeat and signal helpers.

    """
    context.stderr.finish()
    with suppress(OSError):
        artifacts: Path = context.output / "ARTIFACTS"
        artifacts.mkdir(parents=True, exist_ok=True)
        log: Path = artifacts / StderrTables.log_name
        if not log.exists():
            _ = log.write_bytes(data=b"")
    errors: int = context.stderr.levels["error"]
    warnings: int = context.stderr.levels["warning"]
    if errors or warnings:
        context.log.record(
            level="warning",
            message=(
                f"stderr: {context.stderr.lines} lines, {errors} error and"
                f" {warnings} warning lines"
            ),
        )


def _organize_artifacts(*, analyzer: str, output: Path) -> None:
    """Move non-report analyzer evidence into ``ARTIFACTS``.

    A subdirectory holding its own ``result.md`` is a nested report (such
    as ``COVERAGE_TESTS/COVERAGE``) and stays in place.

    Args:
        analyzer: Stable analyzer identifier retained for diagnostics.
        output: Analyzer report directory.

    """
    del analyzer
    reserved: frozenset[str] = frozenset(
        {
            "ARTIFACTS",
            "FILES",
            "result.json",
            "result.md",
            "result_web",
            "V1",
            "V2",
        },
    )
    candidates: tuple[Path, ...] = tuple(
        path
        for path in output.iterdir()
        if path.name not in reserved
        and (not (path.is_dir() and (path / "result.md").is_file()))
    )
    if not candidates:
        return
    artifacts: Path = output / "ARTIFACTS"
    artifacts.mkdir(parents=True, exist_ok=True)
    for source in candidates:
        destination: Path = artifacts / source.name
        if destination.exists():
            if destination.is_dir():
                rmtree(path=destination)
            else:
                destination.unlink()
        _ = move(src=source, dst=destination)


def _stamp_json(
    *,
    path: Path,
    analyzer: str,
    status: int,
    elapsed_seconds: float,
    fallback: str,
) -> str:
    """Stamp ``result.json`` with canonical status fields.

    Args:
        path: Analyzer JSON report path.
        analyzer: Stable analyzer identifier.
        status: Analyzer process exit status.
        elapsed_seconds: Tool wall-clock duration.
        fallback: Resume text used when the report supplies none.

    Returns:
        Tool-provided or generated resume text.

    """
    if not path.is_file():
        return fallback
    try:
        payload: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    result: str = "PASS" if status == 0 else "FAIL"
    payload["tool"] = analyzer
    payload["run_id"] = environ.get("EXACTUS_RUN_ID")
    payload["pipeline_run_id"] = environ.get("EXACTUS_PIPELINE_RUN_ID")
    payload["status"] = result
    payload["passed"] = status == 0
    payload["duration_seconds"] = round(number=elapsed_seconds, ndigits=3)
    previous_duration: float | None = previous_report_duration(path=path)
    if previous_duration is not None:
        payload["previous_duration_seconds"] = round(
            number=previous_duration,
            ndigits=3,
        )
    resume: str = fallback
    existing_resume: JsonValue = payload.get("resume")
    if isinstance(existing_resume, str) and existing_resume.strip():
        resume = existing_resume
    else:
        candidate: JsonValue = payload.get("summary", payload.get("message"))
        if isinstance(candidate, str) and candidate.strip():
            resume = candidate
        payload["resume"] = resume
    _ = consume(
        value=path.write_text(
            data=JsonDict(payload).tojson + "\n",
            encoding="utf-8",
        ),
    )
    return resume


def _stamp_markdown(*, path: Path, result: str, resume: str) -> None:
    """Insert canonical status and resume sections into ``result.md``.

    Args:
        path: Analyzer Markdown report path.
        result: PASS or FAIL stamp.
        resume: Final resume text.

    """
    if not path.is_file():
        return
    markdown: str = path.read_text(encoding="utf-8")
    lines: list[str] = markdown.splitlines()
    if "- Status: **" not in markdown:
        lines.insert(1, "")
        lines.insert(2, f"- Status: **{result}**")
    previous_duration: float | None = previous_report_duration(
        path=path.parent / "result.json",
    )
    if previous_duration is not None and "- Previous run:" not in markdown:
        status_index: int = next(
            (
                index
                for index, line in enumerate(iterable=lines)
                if line.startswith("- Status: **")
            ),
            1,
        )
        lines.insert(status_index + 1, "")
        lines.insert(
            status_index + 2,
            f"- Previous run: **{previous_duration:.3f}s**",
        )
    if "## Resume" not in markdown:
        lines.extend(("", "## Resume", "", resume))
    _ = consume(
        value=path.write_text(data="\n".join(lines) + "\n", encoding="utf-8"),
    )


def _stamp_web(
    *,
    web: Path,
    analyzer: str,
    status: int,
    elapsed_seconds: float,
    resume: str,
) -> None:
    """Stamp the ``data.json``/``data.js`` payload inside ``result_web``.

    Args:
        web: Analyzer web report directory.
        analyzer: Stable analyzer identifier.
        status: Analyzer process exit status.
        elapsed_seconds: Tool wall-clock duration.
        resume: Final resume text.

    """
    path: Path = web / "data.json"
    if not path.is_file():
        return
    try:
        web_payload: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return
    if not isinstance(web_payload, dict):
        return
    web_payload["tool"] = analyzer
    web_payload["status"] = "PASS" if status == 0 else "FAIL"
    web_payload["passed"] = status == 0
    web_payload["duration_seconds"] = round(number=elapsed_seconds, ndigits=3)
    previous_duration: float | None = previous_report_duration(
        path=web.parent / "result.json",
    )
    if previous_duration is not None:
        web_payload["previous_duration_seconds"] = round(
            number=previous_duration,
            ndigits=3,
        )
    web_payload["resume"] = resume
    ReportBundle.write_web_data(web=web, payload=JsonDict(web_payload))


def _stamp_normalized(*, facts: RunFacts) -> bool:
    """Render a migrated tool's report through its template.

    A tool is migrated when it ships ``templates/markdown/template.md``.
    A run with status ``ERROR`` only needs the envelope blocks; the
    tool's own blocks then render as ``N/A``.

    Args:
        facts: Run facts filling the envelope.

    Returns:
        ``True`` when the normalized report replaced the legacy stamps;
        ``False`` for unmigrated tools or when rendering failed, in which
        case the legacy stamps still apply.

    """
    if not ReportTemplates.migrated(analyzer=facts.analyzer):
        return False
    required: frozenset[str] = (
        ReportConstants.envelope_blocks
        if facts.status == "ERROR"
        else ReportConstants.normalized_blocks
    )
    try:
        return NormalizedStamp.apply(facts=facts, required=required)
    except (OSError, ValueError, TemplateEngineError):
        Constants.logger.exception(msg="Normalized report rendering failed")
        return False


def _stamp_result(
    *,
    output: Path,
    analyzer: str,
    status: int,
    elapsed_seconds: float,
    facts: RunFacts | None = None,
) -> str:
    """Stamp the canonical JSON and Markdown reports with PASS/FAIL.

    Args:
        output: Analyzer report directory.
        analyzer: Stable analyzer identifier.
        status: Analyzer process exit status.
        elapsed_seconds: Tool wall-clock duration.
        facts: Run facts; a migrated tool's report is then rendered
            from its template instead of the legacy text stamps.

    Returns:
        Tool-provided or generated resume text.

    """
    result: str = "PASS" if status == 0 else "FAIL"
    resume: str = _stamp_json(
        path=output / "result.json",
        analyzer=analyzer,
        status=status,
        elapsed_seconds=elapsed_seconds,
        fallback=f"{result}: analyzer completed with exit status {status}.",
    )
    if facts is not None and _stamp_normalized(facts=facts):
        return resume
    _stamp_markdown(path=output / "result.md", result=result, resume=resume)
    _stamp_web(
        web=output / "result_web",
        analyzer=analyzer,
        status=status,
        elapsed_seconds=elapsed_seconds,
        resume=resume,
    )
    return resume


def _sync_cleanup_root(*, output: Path) -> Path:
    """Bound sync cleanup to the active project or exact report directory.

    Args:
        output: Analyzer report directory used when no project is known.

    Returns:
        Explicit exactus root, marked current project, or report directory.

    """
    root: Path = Path(environ.get("EXACTUS_ROOT", str(object=Path.cwd())))
    return (
        root
        if "EXACTUS_ROOT" in environ or (root / "pyproject.toml").is_file()
        else output
    )


def _pipeline_locks(*, analyzer: str) -> dict[str, int]:
    """Map each catalog pipeline containing ``analyzer`` to its wave.

    Args:
        analyzer: Stable analyzer identifier.

    Returns:
        Pipeline identifiers mapped to the analyzer's one-based
        dependency group inside that pipeline.

    """
    tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=analyzer,
    )
    if tool is None or not tool.dependencies or tool.streaming_dependencies:
        return {}
    locks: dict[str, int] = {}
    spec: PipelineSpec
    for spec in _GroupFinalConstants.exactus_catalog.pipelines():
        group: int
        wave: tuple[ToolSpec, ...]
        for group, wave in enumerate(
            iterable=_GroupFinalConstants.exactus_catalog.waves(
                identifier=spec.identifier,
            ),
            start=1,
        ):
            if any(tool.identifier == analyzer for tool in wave):
                locks[spec.identifier] = group
                break
    return locks


def _dependency_closure(*, analyzer: str) -> frozenset[str]:
    """Return every transitive catalog dependency of one analyzer.

    Args:
        analyzer: Canonical tool identifier.

    Returns:
        Transitive prerequisite identifiers.

    """
    pending: list[str] = [analyzer]
    found: set[str] = set()
    while pending:
        identifier: str = pending.pop()
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=identifier,
        )
        if tool is None:
            continue
        for dependency in tool.dependencies:
            if dependency not in found:
                found.add(dependency)
                pending.append(dependency)
    return frozenset(found)


def _depends_on(*, analyzer: str, dependency: str) -> bool:
    """Return whether ``analyzer`` transitively requires ``dependency``.

    Args:
        analyzer: Candidate dependent tool.
        dependency: Candidate prerequisite tool.

    Returns:
        Whether catalog ordering requires the dependency first.

    """
    return dependency in _dependency_closure(analyzer=analyzer)


def _worker_descriptor(*, record: RunRecord) -> Descriptor | None:
    """Resolve the pmanager worker described by a run-registry row.

    Args:
        record: Live tool-run record.

    Returns:
        Matching worker descriptor, when the run uses pmanager.

    """
    return Discovery.find(
        name=record.identifier,
        context=run_context(
            root=Path(
                environ.get(
                    RegistryTables.project_root_env,
                    str(object=Path.cwd()),
                ),
            ),
            owner=record.pipeline_run_id or record.run_id,
        ),
    )


def _dependent_runs(
    *,
    registry: RunRegistry,
    analyzer: str,
    run_id: str,
) -> tuple[RunRecord, ...]:
    """Return live runs whose catalog ordering depends on this run.

    Args:
        registry: Workspace run registry.
        analyzer: Prerequisite tool identifier.
        run_id: Prerequisite run identifier to exclude.

    Returns:
        Live dependent tool runs.

    """
    return tuple(
        record
        for record in registry.live()
        if record.kind == "tool"
        and record.run_id != run_id
        and _depends_on(analyzer=record.identifier, dependency=analyzer)
    )


def _pause_live_dependents(*, context: _RunContext) -> None:
    """Checkpoint downstream tools at their next complete file boundary.

    Args:
        context: Prerequisite run state.

    """
    for record in _dependent_runs(
        registry=context.registry,
        analyzer=context.analyzer,
        run_id=context.run_id,
    ):
        descriptor: Descriptor | None = _worker_descriptor(record=record)
        if descriptor is None:
            pause_tree(pid=record.pid)
            continue
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=record.identifier,
        )
        if tool is None or not tool.streaming_dependencies:
            with suppress(OSError, RuntimeError):
                _ = Client.request(
                    descriptor=descriptor,
                    command="pause",
                    payload={"owner": f"dependency:{context.run_id}"},
                )
            continue
        with suppress(OSError, RuntimeError):
            _ = Client.request(
                descriptor=descriptor,
                command="event",
                payload={
                    "topic": "exactus.tool.control",
                    "payload": {
                        "action": "checkpoint_pause",
                        "dependency": context.analyzer,
                        "run_id": context.run_id,
                    },
                    "source": context.analyzer,
                    "context": descriptor.context,
                },
            )
            checkpoint_deadline: float = (
                monotonic()
                + ExactusEntrypointTables.checkpoint_timeout_seconds
            )
            while not context.interrupted.is_set():
                snapshot: dict[str, JsonValue] = Client.request(
                    descriptor=descriptor,
                    command="info",
                )
                custom: JsonValue = snapshot.get("custom_status")
                checkpoint: JsonValue = (
                    custom.get("checkpoint")
                    if isinstance(custom, dict)
                    else None
                )
                child_exited: bool = snapshot.get("exit_code") is not None
                timed_out: bool = monotonic() >= checkpoint_deadline
                ready: bool = (
                    isinstance(checkpoint, dict)
                    and checkpoint.get("ready") is True
                )
                if ready or child_exited or timed_out:
                    _ = Client.request(descriptor=descriptor, command="reset")
                    context.log.record(
                        message=(
                            f"restarted {record.identifier} after "
                            + (
                                "a complete file boundary"
                                if ready
                                else "its worker exited"
                                if child_exited
                                else "checkpoint timeout"
                            )
                        ),
                    )
                    break
                _ = context.stop.wait(timeout=0.05)
        context.log.record(
            message=(
                f"requested file-boundary checkpoint from"
                f" {record.identifier} for {context.analyzer}"
            ),
        )


def release_dependency_workers(
    *,
    analyzer: str,
    run_id: str,
    output: Path,
) -> None:
    """Release checkpointed downstream workers after prerequisite analysis.

    Args:
        analyzer: Completed prerequisite identifier.
        run_id: Completed prerequisite run identifier.
        output: Prerequisite output used to locate the workspace registry.

    """
    registry: RunRegistry = RunRegistry.for_output(output=output)
    for record in _dependent_runs(
        registry=registry,
        analyzer=analyzer,
        run_id=run_id,
    ):
        descriptor: Descriptor | None = _worker_descriptor(record=record)
        if descriptor is None:
            resume_tree(pid=record.pid)
            continue
        try:
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=record.identifier,
            )
            if tool is None or not tool.streaming_dependencies:
                _ = Client.request(
                    descriptor=descriptor,
                    command="start",
                    payload={"owner": f"dependency:{run_id}"},
                )
                continue
            _ = Client.request(
                descriptor=descriptor,
                command="event",
                payload={
                    "topic": "exactus.tool.control",
                    "payload": {
                        "action": "checkpoint_resume",
                        "dependency": analyzer,
                        "run_id": run_id,
                    },
                    "source": analyzer,
                    "context": descriptor.context,
                },
            )
        except (OSError, RuntimeError):
            terminate_tree(pid=record.pid, replaced=True)


def _dependency_gate(
    *,
    registry: RunRegistry,
    analyzer: str,
    run_id: str,
) -> str | None:
    """Return a wait label while an earlier catalog dependency is live.

    Args:
        registry: Workspace run registry.
        analyzer: Tool waiting to execute.
        run_id: Waiting run identifier.

    Returns:
        Wait label, or ``None`` when all prerequisites are terminal.

    """
    tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=analyzer,
    )
    if tool is not None and tool.streaming_dependencies:
        return None
    dependencies: frozenset[str] = _dependency_closure(analyzer=analyzer)
    blocker: RunRecord | None = next(
        (
            record
            for record in registry.live()
            if record.kind == "tool"
            and record.run_id != run_id
            and record.identifier in dependencies
        ),
        None,
    )
    return (
        f"waiting for dependency {blocker.identifier}"
        if blocker is not None
        else None
    )


def _pipeline_gate(
    *,
    registry: RunRegistry,
    locks: dict[str, int],
) -> str | None:
    """Return a wait label while a live pipeline gates this analyzer.

    A pipeline publishes the wave it currently executes as
    ``current_group`` in its ``@activity.json``. An analyzer whose own
    group is ahead of that marker must wait — the groups feeding it
    have not run yet.

    Args:
        registry: Run registry to scan for live pipelines.
        locks: Pipeline identifiers mapped to the analyzer's group.

    Returns:
        The blocking wait label, or ``None`` when no live pipeline is
        behind the analyzer's group.

    """
    record: RunRecord
    for record in registry.live():
        if record.kind != "pipeline":
            continue
        group: int | None = locks.get(record.identifier)
        if group is None:
            continue
        document: ActivityDocument | None = ActivityFile.read(
            path=Path(record.output) / "ARTIFACTS" / ActivityTables.file_name,
        )
        if document is None:
            return f"waiting for {record.identifier} to start"
        if document.status not in {"WAITING", "RUNNING"}:
            continue
        current: JsonValue = document.extra.get("current_group")
        if current is None:
            continue
        if (
            isinstance(current, int)
            and not isinstance(current, bool)
            and group > current
        ):
            return f"waiting for {record.identifier} group {current}"
    return None


def _await_pipeline_gate(*, context: _RunContext) -> None:
    """Hold a run until dependencies and live pipelines permit execution.

    The run stays claimed — and therefore adoptable by the pipeline —
    but sleeps instead of analyzing the tree before the groups feeding
    it have run. Pipeline-owned workers skip the gate entirely; their
    wave already schedules them.

    Args:
        context: Shared run state for heartbeat and signal helpers.

    """
    locks: dict[str, int] = (
        _pipeline_locks(analyzer=context.analyzer)
        if context.pipeline_run_id is None
        else {}
    )
    announced: str | None = None
    while not context.interrupted.is_set():
        try:
            blocked: str | None = _dependency_gate(
                registry=context.registry,
                analyzer=context.analyzer,
                run_id=context.run_id,
            )
            if blocked is None and locks:
                blocked = _pipeline_gate(
                    registry=context.registry,
                    locks=locks,
                )
        except OSError:
            return
        if blocked is None:
            return
        if blocked != announced:
            announced = blocked
            context.log.record(message=blocked)
            emit_progress(state="RUNNING", completed=0, total=1, step=blocked)
        _ = context.stop.wait(
            timeout=ExactusEntrypointTables.heartbeat_seconds,
        )


def _invoke_gated(
    *,
    main: Callable[[], int],
    context: _RunContext,
) -> tuple[int, str | None]:
    """Wait out the pipeline group gate, then invoke the analyzer.

    Args:
        main: Analyzer main function.
        context: Shared run state for heartbeat and signal helpers.

    Returns:
        The analyzer exit status and error, or an interrupt result when
        the run was signalled while waiting at the gate.

    """
    _await_pipeline_gate(context=context)
    if context.interrupted.is_set():
        return (130, "interrupted while waiting")
    return _invoke(main=main, context=context)


def _invoke_coordinated(
    *,
    main: Callable[[], int],
    context: _RunContext,
) -> tuple[int, str | None]:
    """Pause stale downstream work, then invoke at queue readiness.

    Args:
        main: Analyzer entry point.
        context: Shared run state.

    Returns:
        Analyzer status and optional error.

    """
    _pause_live_dependents(context=context)
    tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=context.analyzer,
    )
    with source_activity(
        mode="read",
        identity=f"task:{context.analyzer}",
        enabled=tool.whole_source_activity if tool is not None else False,
    ):
        return _invoke_gated(main=main, context=context)


def _finish_coordinated(*, context: _RunContext, status: int) -> None:
    """Release downstream work and publish this run's final pulse.

    Args:
        context: Shared run state.
        status: Analyzer exit status.

    """
    release_dependency_workers(
        analyzer=context.analyzer,
        run_id=context.run_id,
        output=context.output,
    )
    _final_pulse(context=context, status=status)


def _begin_tool_progress(*, analyzer: str, title: str) -> None:
    """Reset and publish the initial task progress snapshot.

    Args:
        analyzer: Canonical tool identifier.
        title: Human-readable tool title.

    """
    environ.setdefault(
        RegistryTables.project_root_env,
        str(object=Path.cwd().resolve()),
    )
    environ["EXACTUS_TOOL"] = analyzer
    clear_progress()
    emit_progress(
        state="RUNNING",
        completed=0,
        total=1,
        step="starting",
        detail=title,
    )


def execute_exactus(
    *,
    analyzer: str,
    title: str,
    main: Callable[[], int],
    output: Path | None = None,
    run_ids: ExactusRunIds | None = None,
) -> ToolRunResult:
    """Return execute exactus.

    Args:
        analyzer: Analyzer.
        title: Title.
        main: Main.
        output: Output.
        run_ids: Run identifiers injected by an orchestrating pipeline.

    Returns:
        The resulting value.

    """
    ids: ExactusRunIds = run_ids or ExactusRunIds()
    command: str = shlex_join(split_command=argv)
    arguments: tuple[str, ...] = tuple(argv[1:])
    resolved_output: Path = (
        output if output is not None else _report_output(analyzer=analyzer)
    )
    run_id: str = ids.run_id or environ.get(
        "EXACTUS_RUN_ID",
        default=new_run_id(),
    )
    pipeline_run_id: str | None = (
        ids.pipeline_run_id
        if ids.pipeline_run_id is not None
        else environ.get("EXACTUS_PIPELINE_RUN_ID")
    )
    registry: RunRegistry = _claim_run(
        analyzer=analyzer,
        output=resolved_output,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
    )
    environ["EXACTUS_RUN_ID"] = run_id
    environ[RegistryTables.env_path] = str(object=registry.path)
    _ = clear_conflict_copies(root=_sync_cleanup_root(output=resolved_output))
    capture_previous_reports(output=resolved_output)
    _prepare_output(output=resolved_output, run_id=run_id)
    resolved_output.mkdir(parents=True, exist_ok=True)
    before: dict[Path, tuple[int, int]] = _report_snapshot(
        output=resolved_output,
    )
    started: float = monotonic()
    context: _RunContext = _RunContext(
        output=resolved_output,
        analyzer=analyzer,
        started_at=utc_now(),
        started=started,
        interrupted=Event(),
        stop=Event(),
        write_lock=Lock(),
        registry=registry,
        run_id=run_id,
        pipeline_run_id=pipeline_run_id,
        previous_duration_seconds=previous_report_duration(
            path=resolved_output / "result.json",
        ),
        log=ActivityLog(),
        stderr=StderrRecorder(),
    )
    context.log.record(message=f"started: {title}")
    _begin_tool_progress(analyzer=analyzer, title=title)
    heartbeat: Thread = Thread(
        target=_heartbeat,
        kwargs={"context": context},
        daemon=True,
    )
    heartbeat.start()
    previous_handlers: dict[Signals, SignalHandler] = (
        _install_terminate_handlers(
            context=context,
            output_fd=tees[-1].original_fd
            if (
                tees := _capture_streams(
                    output=resolved_output,
                    recorder=context.stderr,
                )
            )
            else 2,
        )
    )
    status, error = _invoke_coordinated(main=main, context=context)
    elapsed_seconds: float = monotonic() - started
    stdout_tail, stderr_tail = _stop_streams(tees=tees)
    if error:
        context.log.record(
            level="error",
            message=f"tool error: {error.splitlines()[0]}",
        )
    _finish_stderr(context=context)
    context.stop.set()
    heartbeat.join(timeout=ExactusEntrypointTables.heartbeat_seconds * 2)
    _restore_terminate_handlers(previous=previous_handlers)
    if not (
        reported := _report_emitted(output=resolved_output, before=before)
    ):
        context.log.record(
            level="warning",
            message="the tool wrote no report; a fallback report was written",
        )
        _write_fallback_report(
            result=FallbackResult(
                output=resolved_output,
                analyzer=analyzer,
                title=title,
                status=status,
                error=error,
                command=command,
                elapsed_seconds=elapsed_seconds,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
            ),
        )
    last: dict[str, JsonValue] = _progress_fields(payload=current_progress())
    last_total: int = (
        int(last["total"]) if isinstance(last["total"], int) else 1
    )
    publish_progress(
        progress=Progress(
            state="DONE" if status == 0 else "FAIL",
            completed=(
                last_total
                if status == 0
                else (
                    int(last["completed"])
                    if isinstance(last["completed"], int)
                    else 0
                )
            ),
            total=last_total,
            step="complete",
            detail=title,
            error=error or "",
        ),
    )
    _organize_artifacts(analyzer=analyzer, output=resolved_output)
    resume: str = _stamp_result(
        output=resolved_output,
        analyzer=analyzer,
        status=status,
        elapsed_seconds=elapsed_seconds,
        facts=RunFacts(
            analyzer=analyzer,
            title=title,
            status=(
                "ERROR" if not reported else "PASS" if status == 0 else "FAIL"
            ),
            exit_code=status,
            error=error
            or (
                None
                if reported
                else "the tool exited without writing a report"
            ),
            started_at=context.started_at,
            finished_at=utc_now(),
            duration_seconds=elapsed_seconds,
            run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            command=command,
            cwd=str(object=Path.cwd()),
            arguments=arguments,
            output=resolved_output,
        ),
    )
    if requested(tokens=arguments):
        _ = collect_report_files(output=resolved_output)
    _finish_coordinated(context=context, status=status)
    result: ToolRunResult = ToolRunResult(
        tool=analyzer,
        run_id=context.run_id,
        pipeline_run_id=context.pipeline_run_id,
        status="PASS" if status == 0 else "FAIL",
        passed=status == 0,
        exit_code=status,
        duration_seconds=elapsed_seconds,
        resume=resume,
        report=resolved_output / "result.md",
        report_json=resolved_output / "result.json",
        report_web=resolved_output / "result_web" / "index.html",
    )
    if "EXACTUS_ORCHESTRATED" not in environ:
        ExactusTerminal.finish_standalone_progress(failed=not result.passed)
        ExactusTerminal.results(
            title=f"exactus · {analyzer.removeprefix('exactus_')}",
            rows=(
                ResultRow(
                    tool=analyzer,
                    status=result.status,
                    duration_seconds=elapsed_seconds,
                    resume=resume,
                    report=str(object=result.report),
                    stats=result_stats(report_json=result.report_json),
                ),
            ),
        )
    _ = clear_conflict_copies(root=_sync_cleanup_root(output=resolved_output))
    clear_progress()
    clear_previous_reports()
    _ = environ.pop("EXACTUS_TOOL", default=None)
    return result


@dataclass(frozen=True, slots=True)
class CrashDetails:
    """Facts describing a worker process that died before reporting.

    Attributes:
        pid: Dead worker process identifier.
        exit_code: Worker exit code; negative values are signals.
        elapsed_seconds: Wall-clock time before the worker vanished.

    """

    pid: int | None
    exit_code: int
    elapsed_seconds: float


def _output_reclaimed(*, output: Path, run_id: str) -> bool:
    """Return whether a newer run already owns the report directory.

    Args:
        output: Analyzer report directory shared by consecutive runs.
        run_id: Dead run whose deferred crash handling is in progress.

    Returns:
        ``True`` when another run claims the directory, so the dead run must
        not write reports or reorganize files used by the replacement run.

    """
    resolved: str = str(object=output.resolve())
    registry: RunRegistry = RunRegistry.for_output(output=output)
    if any(
        record.run_id != run_id and record.output == resolved
        for record in registry.live()
    ):
        return True
    document: ActivityDocument | None = ActivityFile.read(
        path=_activity_path(output=output),
    )
    owner: str | None = document.run_id if document is not None else None
    return owner is not None and owner != run_id


def _crash_result(
    *,
    request: ToolRequest,
    crash: CrashDetails,
    status: str,
    resume: str,
) -> ToolRunResult:
    """Return the immutable result model for a dead exactus worker.

    Args:
        request: Canonical tool request identifying the dead run.
        crash: Worker-death facts captured by the orchestrator.
        status: Terminal status to report.
        resume: Human-readable failure summary.

    Returns:
        A failed result pointing at the analyzer's canonical report paths.

    """
    output: Path = request.output
    return ToolRunResult(
        tool=request.identifier,
        run_id=request.run_id,
        pipeline_run_id=request.pipeline_run_id,
        status=status,
        passed=False,
        exit_code=crash.exit_code or 1,
        duration_seconds=round(number=crash.elapsed_seconds, ndigits=3),
        resume=resume,
        report=output / "result.md",
        report_json=output / "result.json",
        report_web=output / "result_web" / "index.html",
    )


def _crash_activity(
    *,
    request: ToolRequest,
    crash: CrashDetails,
    status: str,
) -> ActivityDocument:
    """Build the terminal ``@activity.json`` of a dead worker.

    Events the worker had already published are kept when the document
    still belongs to the same run.

    Args:
        request: Canonical tool request identifying the dead run.
        crash: Worker-death facts captured by the orchestrator.
        status: Terminal status to report.

    Returns:
        The final activity document.

    """
    previous: ActivityDocument | None = ActivityFile.read(
        path=_activity_path(output=request.output),
    )
    if previous is not None and previous.run_id != request.run_id:
        previous = None
    log: ActivityLog = ActivityLog()
    if previous is not None:
        log.extend(events=previous.events, dropped=previous.events_dropped)
    log.record(
        level="error",
        message=(
            "the worker process ended before reporting (exit code"
            f" {crash.exit_code})"
        ),
    )
    now: str = utc_now()
    return ActivityDocument(
        kind="tool",
        name=request.identifier,
        status=status,
        run_id=request.run_id,
        pipeline_run_id=request.pipeline_run_id,
        started_at=previous.started_at if previous is not None else None,
        updated_at=now,
        finished_at=now,
        elapsed_seconds=crash.elapsed_seconds,
        heartbeat=ActivityHeartbeat(
            pid=crash.pid,
            alive=False,
            last_beat=(
                previous.heartbeat.last_beat if previous is not None else None
            ),
            phase="crashed",
            interval_seconds=ExactusEntrypointTables.heartbeat_seconds,
        ),
        progress=_activity_progress(
            fields=(
                {
                    "progress": previous.progress.fraction,
                    "completed": previous.progress.completed,
                    "total": previous.progress.total,
                    "step": previous.progress.step,
                    "detail": previous.progress.current,
                }
                if previous is not None
                else _progress_fields(payload={})
            ),
        ),
        events=log.events(),
        events_dropped=log.dropped(),
        extra={"exit_code": crash.exit_code},
    )


def crashed_exactus(
    *,
    request: ToolRequest,
    title: str,
    crash: CrashDetails,
) -> ToolRunResult:
    """Record a run whose worker process ended before reporting.

    The terminal heartbeat, fallback report bundle, and result model
    still land so a hard crash looks like every other failed exactus
    instead of surfacing a bare traceback.

    Args:
        request: Canonical tool request identifying the dead run.
        title: Human-readable exactus title.
        crash: Worker-death facts captured by the orchestrator.

    Returns:
        A failed `ToolRunResult` pointing at the fallback bundle.

    """
    analyzer: str = request.identifier
    output: Path = request.output
    run_id: str = request.run_id
    pipeline_run_id: str | None = request.pipeline_run_id
    exit_code: int = crash.exit_code
    elapsed_seconds: float = crash.elapsed_seconds
    interrupted: bool = exit_code < 0
    status: str = "INTERRUPT" if interrupted else "FAIL"
    resume: str = (
        f"the exactus worker exited before reporting (exit {exit_code}); run"
        f" `exactus --tool {analyzer}` again"
    )
    error: str = (
        "the worker process ended without returning a result; its exit code"
        f" is {exit_code}"
    )
    registry: RunRegistry = RunRegistry.for_output(output=output)
    registry.finish(
        run_id=run_id,
        status=status,
        elapsed_seconds=elapsed_seconds,
    )
    if _output_reclaimed(output=output, run_id=run_id):
        return _crash_result(
            request=request,
            crash=crash,
            status=status,
            resume=resume,
        )
    with suppress(OSError):
        output.mkdir(parents=True, exist_ok=True)
        _write_activity(
            output=output,
            document=_crash_activity(
                request=request,
                crash=crash,
                status=status,
            ),
        )
    with suppress(OSError):
        if not _report_emitted(output=output, before={}):
            _write_fallback_report(
                result=FallbackResult(
                    output=output,
                    analyzer=analyzer,
                    title=title,
                    status=exit_code or 1,
                    command=f"exactus --tool {analyzer}",
                    elapsed_seconds=elapsed_seconds,
                    stdout_tail="",
                    stderr_tail="",
                    error=error,
                ),
            )
        _organize_artifacts(analyzer=analyzer, output=output)
        artifacts: Path = output / "ARTIFACTS"
        if not (artifacts / StderrTables.log_name).is_file():
            artifacts.mkdir(parents=True, exist_ok=True)
            _ = (artifacts / StderrTables.log_name).write_bytes(data=b"")
        report_json: Path = output / "result.json"
        if report_json.is_file():
            report_payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=report_json.read_text(encoding="utf-8")),
            )
            if isinstance(report_payload, dict):
                report_payload.update(
                    {
                        "tool": analyzer,
                        "run_id": run_id,
                        "pipeline_run_id": pipeline_run_id,
                        "status": status,
                        "passed": False,
                        "duration_seconds": round(
                            number=elapsed_seconds,
                            ndigits=3,
                        ),
                        "resume": resume,
                    },
                )
                _ = report_json.write_text(
                    data=JsonDict(report_payload).tojson + "\n",
                    encoding="utf-8",
                )
        if not _stamp_normalized(
            facts=RunFacts(
                analyzer=analyzer,
                title=title,
                status="ERROR",
                exit_code=exit_code,
                error=error,
                started_at=None,
                finished_at=utc_now(),
                duration_seconds=elapsed_seconds,
                run_id=run_id,
                pipeline_run_id=pipeline_run_id,
                command=f"exactus --tool {analyzer}",
                cwd=str(object=request.project_root or Path.cwd()),
                arguments=request.arguments,
                output=output,
            ),
        ):
            _stamp_markdown(
                path=output / "result.md",
                result=status,
                resume=resume,
            )
        if requested(tokens=request.arguments):
            _ = collect_report_files(output=output)
    return _crash_result(
        request=request,
        crash=crash,
        status=status,
        resume=resume,
    )


def run_exactus(*, analyzer: str, title: str, main: Callable[[], int]) -> int:
    """Return run exactus.

    Args:
        analyzer: Analyzer.
        title: Title.
        main: Main.

    Returns:
        The resulting value.

    """
    if any(argument in {"-h", "--help"} for argument in argv[1:]):
        _ = _report_output(analyzer=analyzer)
        return main()
    return execute_exactus(analyzer=analyzer, title=title, main=main).exit_code
