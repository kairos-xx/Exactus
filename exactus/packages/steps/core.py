# Copyright (c) 2026
"""Record a timestamped step trace of a tool run in a text file.

Any tool can share this small logger: :class:`StepLog` appends one
``timestamp elapsed step`` line per event, and the module-level
:func:`trace` forwards events to whichever log is active so
instrumented helpers need no plumbing of their own.  Depth levels mark
nesting: ``0`` tool boundary, ``1`` stage, ``2`` substep, ``3`` detail
and ``4`` per-file record.

A line may end with space-separated ``@key=value`` trailers that carry
machine-readable facts without disturbing the human-readable text:

``@thread=NAME``
    Worker thread that emitted the line; omitted on the main thread so
    single-threaded traces stay unchanged.
``@span=N``
    Identifier shared by the begin and end lines of one :func:`span`.
``@dur=SECONDSs``
    Measured duration, written on span end lines and by
    ``trace(duration=...)``.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from sys import stdout
from threading import Lock, Thread, current_thread, main_thread
from time import monotonic
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING, ClassVar, TextIO, cast, final

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

    from .sampler import ResourceSampler
type StepsValue = (
    bool | float | int | str | list["StepsValue"] | dict[str, "StepsValue"]
)
type StepsTable = dict[str, StepsValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        active: Grouped module constant.

    """

    active: ClassVar[StepLog | None] = None


def _setting(*, path: Path, key: str, default: StepsValue) -> StepsValue:
    """Resolve one ``[tool.steps]`` key from the nearest pyproject.

    The destination's ancestors are searched first so a project can
    configure tracing even when a tool is invoked from elsewhere; the
    working directory is the fallback anchor.

    Args:
        path: Destination whose ancestors hold the project pyproject.
        key: Key inside ``[tool.steps]``.
        default: Value used when the file, section or key is absent.

    Returns:
        The configured value, or ``default``.

    """
    seen: set[Path] = set()
    anchor: Path
    for anchor in (path.parent, Path.cwd()):
        if anchor in seen:
            continue
        seen.add(anchor)
        directory: Path
        for directory in (anchor, *anchor.parents):
            pyproject: Path = directory / "pyproject.toml"
            if not pyproject.is_file():
                continue
            try:
                with pyproject.open(mode="rb") as file:
                    data: StepsTable = cast(
                        typ="StepsTable",
                        val=load_toml(file),
                    )
            except (OSError, TOMLDecodeError):
                break
            tool: StepsValue | None = data.get("tool")
            steps: StepsValue | None = (
                tool.get("steps") if isinstance(tool, dict) else None
            )
            return (
                steps.get(key, default) if isinstance(steps, dict) else default
            )
    return default


def _write_enabled(*, path: Path) -> bool:
    """Resolve ``[tool.steps] write`` from the nearest ``pyproject.toml``.

    Args:
        path: Destination whose ancestors hold the project pyproject.

    Returns:
        ``False`` only when the nearest pyproject sets
        ``[tool.steps] write = false``.

    """
    value: StepsValue = _setting(path=path, key="write", default=True)
    return value if isinstance(value, bool) else True


def _sample_interval(*, path: Path) -> float:
    """Resolve ``[tool.steps] sample`` in seconds.

    Args:
        path: Destination whose ancestors hold the project pyproject.

    Returns:
        Seconds between resource samples; ``0.0`` disables sampling.

    """
    value: StepsValue = _setting(path=path, key="sample", default=0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, float(value))


def _thread_tag() -> str | None:
    """Name the emitting thread, or ``None`` on the main thread.

    Returns:
        Whitespace-free thread name for the ``@thread`` trailer.

    """
    current: Thread = current_thread()
    if current is main_thread():
        return None
    return "_".join(current.name.split()) or "worker"


@final
class StepLog:
    """Append timestamped, depth-indented step lines to one file.

    Attributes:
        path: Destination text file rewritten on every run.

    """

    def __init__(self, *, path: Path) -> None:
        """Open ``path`` for writing, degrading to a no-op on failure.

        When the nearest ``pyproject.toml`` sets ``[tool.steps]
        write = false`` the file is never created and every recorded
        step is discarded.

        Args:
            path: Destination file; missing parents are created.

        """
        self.path: Path = path
        self._lock: Lock = Lock()
        self._spans: int = 0
        self._started: float = monotonic()
        self._stream: TextIO | None = None
        self._sampler: ResourceSampler | None = None
        if not _write_enabled(path=path):
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = path.open(mode="w", encoding="utf-8")
        except OSError:
            self._stream = None
            return
        interval: float = _sample_interval(path=path)
        if interval > 0.0:
            module: ModuleType = import_module(
                name=".sampler",
                package=__package__,
            )
            sampler: type[ResourceSampler] = cast(
                typ="type[ResourceSampler]",
                val=module.ResourceSampler,
            )
            self._sampler = sampler(emit=self.write_sample, interval=interval)
            self._sampler.start()

    def next_span(self) -> int:
        """Allocate a span identifier unique within this log.

        Returns:
            The next positive span number.

        """
        with self._lock:
            self._spans += 1
            return self._spans

    def write(
        self,
        *,
        step: str,
        depth: int = 0,
        duration: float | None = None,
        span: int | None = None,
    ) -> None:
        """Append one timestamped step line.

        Args:
            step: Step or substep description.
            depth: Indentation depth marking substep nesting.
            duration: Measured seconds for the step, when known.
            span: Span identifier tying begin and end lines together.

        """
        stream: TextIO | None = self._stream
        if stream is None:
            return
        stamp: str = (
            datetime.now(tz=UTC)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )
        elapsed: str = f"{monotonic() - self._started:9.3f}s"
        thread: str | None = _thread_tag()
        trailers: str = "".join(
            f" @{key}={value}"
            for key, value in (
                ("span", span),
                ("dur", None if duration is None else f"{duration:.3f}s"),
                ("thread", thread),
            )
            if value is not None
        )
        with self._lock:
            try:
                _ = stream.write(
                    f"{stamp} +{elapsed} {'  ' * depth}{step}{trailers}\n",
                )
                _ = stream.flush()
            except OSError:
                self._stream = None

    def write_sample(self, fields: str) -> None:
        """Append one ``~sample`` resource line without thread trailers.

        Args:
            fields: Space-separated ``key=value`` resource fields.

        """
        stream: TextIO | None = self._stream
        if stream is None:
            return
        stamp: str = (
            datetime.now(tz=UTC)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )
        elapsed: str = f"{monotonic() - self._started:9.3f}s"
        with self._lock:
            try:
                _ = stream.write(f"{stamp} +{elapsed} ~sample {fields}\n")
                _ = stream.flush()
            except OSError:
                self._stream = None

    def close(self) -> None:
        """Stop sampling, then flush and close the underlying stream."""
        sampler: ResourceSampler | None = self._sampler
        if sampler is not None:
            sampler.stop()
            self._sampler = None
        with self._lock:
            if self._stream is not None:
                with suppress(OSError):
                    self._stream.close()
                self._stream = None


@contextmanager
def step_log(*, path: Path) -> Generator[StepLog]:
    """Activate a step log for the duration of the context.

    Nested contexts reuse the already active log instead of truncating
    the file, so a caller may activate the same run's log again inside
    an outer activation.

    Args:
        path: Destination file for the run's step lines.

    Yields:
        The active :class:`StepLog`, disabled silently when the file
        cannot be opened.

    """
    if Constants.active is not None:
        yield Constants.active
        return
    log: StepLog = StepLog(path=path)
    Constants.active = log
    try:
        yield log
    finally:
        Constants.active = None
        log.close()


def trace(*, step: str, depth: int = 0, duration: float | None = None) -> None:
    """Forward one step line to the active log, when one exists.

    Args:
        step: Step or substep description.
        depth: Indentation depth marking substep nesting.
        duration: Measured seconds for the step, when already known.

    """
    log: StepLog | None = Constants.active
    if log is not None:
        log.write(step=step, depth=depth, duration=duration)


@contextmanager
def span(*, step: str, depth: int = 0) -> Generator[None]:
    """Record a step's begin line and a measured end line.

    The begin line is the plain ``step`` text; the end line repeats it
    with `` — done`` and carries ``@dur`` so profilers get an exact
    duration instead of inferring one from the next event.  Without an
    active log the context only runs its body.

    Args:
        step: Step description, written on both lines.
        depth: Indentation depth marking substep nesting.

    Yields:
        Control to the measured body.

    """
    log: StepLog | None = Constants.active
    if log is None:
        yield
        return
    identifier: int = log.next_span()
    started: float = monotonic()
    log.write(step=step, depth=depth, span=identifier)
    try:
        yield
    finally:
        log.write(
            step=f"{step} — done",
            depth=depth,
            span=identifier,
            duration=monotonic() - started,
        )


def main(*, path: Path | None = None) -> int:
    """Write a small demonstration trace beside the package.

    Args:
        path: Destination override; defaults to ``.scratch/steps.txt``
            next to this module.

    Returns:
        Zero after the demonstration completes.

    """
    destination: Path = (
        path
        if path is not None
        else Path(__file__).resolve().parent / ".scratch" / "steps.txt"
    )
    with step_log(path=destination):
        trace(step="steps: demonstration run")
        for stage in ("collect", "check", "report"):
            trace(step=f"stage: {stage}", depth=1)
            trace(step=f"{stage}: items processed", depth=2)
        trace(step="steps: demonstration finished")
    _ = stdout.write(f"step trace: {destination}\n\n")
    if destination.is_file():
        _ = stdout.write(destination.read_text(encoding="utf-8"))
    else:
        _ = stdout.write("tracing disabled ([tool.steps] write = false)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
