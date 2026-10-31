# Copyright (c) 2026
"""Shared flushed-writer printing helpers for scripts and examples.

When a ``DEBUG.txt`` marker exists at the project root, each call can
append a capture record to a log file (``debug/out.txt`` by default).
The marker holds one directive per line:

- ``save`` or ``save::<path>`` — enable capture; a directory target
  receives ``out.txt``, a file target is used as-is, and relative paths
  resolve under the project root.
- ``clear`` or ``clear::<age>`` — drop records older than the age
  (``1d5h``, ``30m``, or bare seconds; default one day).
- ``filter::<streams>`` — limit capture to ``stdout``, ``stderr``, or
  ``all`` (the default); several names may be space-separated.
- ``include::<selectors>`` / ``exclude::<selectors>`` — space-separated
  ``file_glob[function_glob, ...]`` entries matched against the caller
  site; an empty file part defaults to ``**/*.py``.

Each record stores the stream label, timestamp, ``file:line:column``
and qualified function name of the external call site (frames inside
this module are skipped), followed by the emitted text. A call can opt
out per invocation with ``SprintStyle(save=False)``. The marker and the
``debug/`` output directory are gitignored local artifacts.

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from inspect import currentframe
from pathlib import Path, PurePosixPath
from re import Match, Pattern, findall
from re import compile as recompile
from sys import stderr, stdout
from time import mktime, strptime, time
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    Protocol,
    cast,
    final,
    override,
    runtime_checkable,
)

if TYPE_CHECKING:
    from types import FrameType
type PrintLevel = Literal["info", "success", "warning", "error"]


@dataclass(frozen=True)
class SprintStyle:
    """Per-call output and capture policy for `sprint`.

    Attributes:
        level: Severity prefix applied to non-empty output.
        color: Whether to wrap the line in the level's ANSI color;
            `None` follows automatic TTY detection.
        save: Whether the call may write a ``DEBUG.txt`` capture
            record; ``False`` suppresses it.

    """

    level: PrintLevel = "info"
    color: bool | None = None
    save: bool = True


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_style: Grouped module constant.
        debug_marker: Grouped module constant.
        debug_directory: Grouped module constant.
        debug_filename: Grouped module constant.
        debug_default_age: Grouped module constant.
        debug_stamp: Grouped module constant.
        debug_units: Grouped module constant.
        debug_selector: Grouped module constant.
        debug_stamp_pattern: Grouped module constant.
        module_file: Grouped module constant.
        project_root: Grouped module constant.
        error_style: Grouped module constant.

    """

    default_style: Final[SprintStyle] = SprintStyle()
    debug_marker: Final[str] = "DEBUG.txt"
    debug_directory: Final[str] = "debug"
    debug_filename: Final[str] = "out.txt"
    debug_default_age: Final[float] = 86400.0
    debug_stamp: Final[str] = "%d/%m/%Y %H:%M:%S"
    debug_units: Final[dict[str, int]] = {
        "d": 86400,
        "h": 3600,
        "m": 60,
        "s": 1,
    }
    debug_selector: Final[Pattern[str]] = recompile(
        pattern="^(?P<file>[^\\[\\]]*)(?:\\[(?P<functions>[^\\[\\]]*)\\])?$",
    )
    debug_stamp_pattern: Final[Pattern[str]] = recompile(
        pattern=(
            "^(?:STDOUT|STDERR) - (\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2}:\\d{2})"
        ),
    )
    module_file: Final[Path] = Path(__file__).resolve()
    project_root: Final[Path] = Path.cwd()
    error_style: Final[SprintStyle] = SprintStyle(level="error")


@dataclass(frozen=True)
class _DebugSelector:
    """One ``include::``/``exclude::`` selector.

    Attributes:
        file: Glob matched against the call site's project-relative
            path; ``**/*.py`` when the entry carries only a function
            filter.
        functions: Function-name globs matched against the caller's
            qualified name, or ``None`` to accept any function.

    """

    file: str
    functions: tuple[str, ...] | None


@dataclass(frozen=True)
class _DebugSpec:
    """Resolved ``DEBUG.txt`` directives.

    Attributes:
        target: Capture file receiving records.
        save: Whether records are appended.
        max_age: Record lifetime in seconds, or ``None`` to keep all.
        streams: Stream labels allowed to record; ``("stderr",
            "stdout")`` captures both.
        include: Selectors that allow capture; empty allows all sites.
        exclude: Selectors that deny capture.

    """

    target: Path
    save: bool
    max_age: float | None
    streams: tuple[str, ...]
    include: tuple[_DebugSelector, ...]
    exclude: tuple[_DebugSelector, ...]


@dataclass(frozen=True)
class _DebugSite:
    """Call site captured for a debug record.

    Attributes:
        path: Source filename as reported by the frame.
        relative: POSIX path relative to the project root when the
            site lives under it, otherwise the resolved path.
        line: Executing line number.
        column: Executing column, one-based; ``0`` when unavailable.
        qualname: Qualified name of the executing function.

    """

    path: str
    relative: str
    line: int
    column: int
    qualname: str


class _Printable(Protocol):
    """A value `sprint` renders via ``str()``.

    Any object qualifies; the protocol states the only capability the
    printer relies on, which keeps ``*args`` honest without the
    ``object`` escape hatch.
    """

    @override
    def __str__(self) -> str:
        """Return the printable representation.

        Returns:
            The `str` result produced by the operation.

        """
        ...


class Writer(Protocol):
    """Writable text stream accepted by `sprint`."""

    def write(self, s: str, /) -> int:
        """Write `s` and return the characters written.

        Args:
            s: `str` value used by the operation.

        Returns:
            The `int` result produced by the operation.

        """
        ...

    def flush(self) -> None:
        """Flush buffered output to the stream."""
        ...


@runtime_checkable
class _Terminal(Protocol):
    """Stream that can report whether it is attached to a terminal."""

    def isatty(self) -> bool:
        """Return whether the stream is attached to a terminal.

        Returns:
            The `bool` result produced by the operation.

        """
        ...


def _style(*, level: PrintLevel) -> tuple[str, str]:
    """Return the line prefix and ANSI color code for `level`.

    Args:
        level: Severity level selecting the style.

    Returns:
        A ``(prefix, ansi_code)`` pair; both empty for `info`.

    """
    match level:
        case "success":
            return ("✓ ", "\x1b[32m")
        case "warning":
            return ("! ", "\x1b[33m")
        case "error":
            return ("✗ ", "\x1b[31m")
        case _:
            return ("", "")


def _debug_save_target(*, root: Path, value: str | None) -> Path:
    """Resolve a ``save`` value to a capture file path.

    Args:
        root: Project root containing the marker file.
        value: Optional ``save::PATH`` operand; ``None`` for bare
            ``save``.

    Returns:
        ``<root>/debug/out.txt`` for bare ``save``; the named path
        directly when it has a file suffix, otherwise
        ``PATH/out.txt``. Relative targets resolve under `root`.

    """
    if value is None:
        return root / Constants.debug_directory / Constants.debug_filename
    target: Path = Path(value.strip())
    if not target.is_absolute():
        target = root / target
    return target if target.suffix else target / Constants.debug_filename


def _debug_max_age(*, value: str | None) -> float:
    """Parse a ``clear`` operand into a record lifetime in seconds.

    Args:
        value: Operand such as ``1d5h`` or ``86400``; ``None``, empty,
            and unparseable values select the one-day default.

    Returns:
        Maximum record age in seconds.

    """
    text: str = "" if value is None else value.strip()
    if text.isdigit():
        return float(text)
    total: float = float(
        sum(
            (
                int(amount) * Constants.debug_units[unit]
                for amount, unit in cast(
                    typ="list[tuple[str, str]]",
                    val=findall(pattern="(\\d+)\\s*([dhms])", string=text),
                )
            ),
        ),
    )
    return total or Constants.debug_default_age


def _debug_selector(*, entry: str) -> _DebugSelector:
    """Parse one ``include::``/``exclude::`` entry.

    Args:
        entry: ``file_glob`` optionally followed by
            ``[function_glob, ...]``.

    Returns:
        The parsed selector.

    """
    match: Match[str] | None = Constants.debug_selector.fullmatch(string=entry)
    if match is None:
        return _DebugSelector(file=entry, functions=None)
    raw_functions: str | None = match["functions"]
    functions: tuple[str, ...] = (
        ()
        if raw_functions is None
        else tuple(
            name.strip()
            for name in raw_functions.split(sep=",")
            if name.strip()
        )
    )
    return _DebugSelector(
        file=match["file"].strip() or "**/*.py",
        functions=functions or None,
    )


def _debug_spec(*, marker: Path) -> _DebugSpec | None:
    """Resolve every directive inside a ``DEBUG.txt`` marker.

    Args:
        marker: Marker file path at the project root.

    Returns:
        The resolved spec, or ``None`` when the marker is absent or
        requests neither saving nor clearing.

    """
    if not marker.is_file():
        return None
    root: Path = marker.parent
    save: bool = False
    target: Path = _debug_save_target(root=root, value=None)
    max_age: float | None = None
    streams: set[str] = set()
    include: list[_DebugSelector] = []
    exclude: list[_DebugSelector] = []
    raw: str
    for raw in marker.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line: str = raw.strip()
        if not line:
            continue
        name: str
        separator: str
        value: str
        name, separator, value = line.partition("::")
        match name:
            case "save":
                save = True
                if separator:
                    target = _debug_save_target(root=root, value=value)
            case "clear":
                max_age = _debug_max_age(value=value if separator else None)
            case "filter":
                streams.update(
                    label
                    for word in value.split()
                    for label in (
                        ("stdout", "stderr") if word == "all" else (word,)
                    )
                    if label in ("stdout", "stderr")
                )
            case "include" | "exclude":
                selectors: list[_DebugSelector] = (
                    include if name == "include" else exclude
                )
                selectors.extend(
                    _debug_selector(entry=entry) for entry in value.split()
                )
            case _:
                continue
    if not save and max_age is None:
        return None
    return _DebugSpec(
        target=target,
        save=save,
        max_age=max_age,
        streams=tuple(sorted(streams)) or ("stderr", "stdout"),
        include=tuple(include),
        exclude=tuple(exclude),
    )


def _debug_site(*, root: Path) -> _DebugSite | None:
    """Return the first call site outside this module.

    Stack frames produced inside ``sprint.py`` are skipped, so records
    written through ``sprint_err`` still point at its caller.

    Args:
        root: Project root used to relativize the source path.

    Returns:
        The external call site, or ``None`` when none exists.

    """
    frame: FrameType | None = currentframe()
    try:
        while (
            frame is not None
            and Path(frame.f_code.co_filename).resolve()
            == Constants.module_file
        ):
            frame = frame.f_back
        if frame is None:
            return None
        positions: tuple[tuple[int | None, ...], ...] = tuple(
            frame.f_code.co_positions(),
        )
        index: int = frame.f_lasti // 2
        column: int = 0
        if index < len(positions) and positions[index][2] is not None:
            column = cast(typ="int", val=positions[index][2]) + 1
        path: str = frame.f_code.co_filename
        resolved: Path = Path(path).resolve()
        return _DebugSite(
            path=path,
            relative=resolved.relative_to(root).as_posix()
            if resolved.is_relative_to(root)
            else resolved.as_posix(),
            line=frame.f_lineno,
            column=column,
            qualname=frame.f_code.co_qualname,
        )
    finally:
        del frame


def _selector_matches(*, selector: _DebugSelector, site: _DebugSite) -> bool:
    """Return whether `site` satisfies `selector`.

    Args:
        selector: File glob plus optional function-name globs.
        site: Candidate call site.

    Returns:
        ``True`` when the file glob matches the site's relative path
        and, when present, a function glob matches its qualified name.

    """
    path: PurePosixPath = PurePosixPath(site.relative)
    if not (
        path.match(path_pattern=selector.file)
        or path.match(path_pattern=f"{selector.file}/**")
    ):
        return False
    if selector.functions is None:
        return True
    names: tuple[str, ...] = (
        site.qualname,
        site.qualname.replace(".", "/"),
        site.qualname.rpartition(".")[2],
    )
    return any(
        fnmatchcase(name=candidate, pat=pattern)
        for pattern in selector.functions
        for candidate in names
    )


def _debug_clear(*, target: Path, max_age: float, now: float) -> None:
    """Drop capture records older than `max_age` seconds.

    Args:
        target: Capture file to prune.
        max_age: Maximum record age in seconds.
        now: Current time as epoch seconds.

    """
    if not target.is_file():
        return
    record: str
    kept: list[str] = []
    for record in target.read_text(encoding="utf-8", errors="replace").split(
        sep="-----\n",
    ):
        if not record.strip():
            continue
        stamp: Match[str] | None = Constants.debug_stamp_pattern.match(
            string=record.split(sep="\n", maxsplit=1)[0],
        )
        try:
            written: float = (
                mktime(strptime(stamp[1], Constants.debug_stamp))
                if stamp is not None
                else now
            )
        except ValueError:
            written = now
        if now - written > max_age:
            continue
        kept.append(record + "-----\n")
    _ = target.write_text(data="".join(kept), encoding="utf-8")


def _debug_record(
    *,
    text: str,
    writer: Writer,
    root: Path | None = None,
) -> None:
    """Append a capture record when ``DEBUG.txt`` requests one.

    Capture is best effort: unreadable markers and unwritable targets —
    such as the read-only filesystem inside a guest container — are
    ignored rather than failing the caller.

    Args:
        text: Message emitted by the call.
        writer: Stream that received the message.
        root: Project root containing the marker file; ``None``
            resolves the package's own project root at call time.

    """
    base: Path = root or Constants.project_root
    try:
        spec: _DebugSpec | None = _debug_spec(
            marker=base / Constants.debug_marker,
        )
        if spec is None:
            return
        if spec.max_age is not None:
            _debug_clear(target=spec.target, max_age=spec.max_age, now=time())
        if not spec.save:
            return
        label: str = "stderr" if writer is stderr else "stdout"
        if label not in spec.streams:
            return
        site: _DebugSite | None = _debug_site(root=base)
        if site is None:
            return
        selected: bool = not spec.include or any(
            _selector_matches(selector=selector, site=site)
            for selector in spec.include
        )
        excluded: bool = any(
            _selector_matches(selector=selector, site=site)
            for selector in spec.exclude
        )
        if not selected or excluded:
            return
        record_label: str = label.upper()
        stamp: str = (
            datetime.now(tz=UTC)
            .astimezone()
            .strftime(format=Constants.debug_stamp)
        )
        spec.target.parent.mkdir(parents=True, exist_ok=True)
        with spec.target.open(mode="a", encoding="utf-8") as handle:
            _ = handle.write(
                f"{record_label}"
                f" - "
                f"{stamp}"
                f"\n"
                f"{site.path}"
                f":"
                f"{site.line}"
                f":"
                f"{site.column}"
                f" > "
                f"{site.qualname}"
                f"\n\n"
                f"{text}"
                f"\n-----\n",
            )
    except OSError:
        return


def sprint(
    *args: _Printable,
    sep: str = " ",
    end: str = "\n",
    file: Writer | None = None,
    flush: bool = True,
    style: SprintStyle = Constants.default_style,
) -> None:
    """Print a message and optionally flush the writer.

    Args:
        *args: Values to print.
        sep: Separator inserted between values.
        end: String appended after the joined values.
        file: Writer to use; defaults to stdout, or stderr for the
            `warning` and `error` levels.
        flush: Whether to flush the writer after writing.
        style: Severity prefix, ANSI color policy, and ``DEBUG.txt``
            capture permission applied to the output.

    """
    writer: Writer = (
        file
        if file is not None
        else stderr
        if style.level in ("warning", "error")
        else stdout
    )
    text: str = sep.join(str(object=arg) for arg in args)
    if text:
        prefix: str
        code: str
        prefix, code = _style(level=style.level)
        colored: bool = (
            style.color
            if style.color is not None
            else isinstance(writer, _Terminal) and writer.isatty()
        )
        text = (
            f"{code}{prefix}{text}\x1b[0m"
            if colored and code
            else f"{prefix}{text}"
        )
    _ = writer.write(text + end)
    if flush:
        writer.flush()
    if style.save:
        _debug_record(text=text, writer=writer)


def sprint_err(
    *args: _Printable,
    sep: str = " ",
    end: str = "\n",
    flush: bool = True,
    style: SprintStyle = Constants.error_style,
) -> None:
    """Print a message to stderr and optionally flush.

    Args:
        *args: Values to print.
        sep: Separator inserted between values.
        end: String appended after the joined values.
        flush: Whether to flush the writer after writing.
        style: Severity prefix, ANSI color policy, and ``DEBUG.txt``
            capture permission applied to the output; defaults to the
            error level. Pass ``SprintStyle(level="error", save=False)``
            to suppress capture.

    """
    sprint(*args, sep=sep, end=end, file=stderr, flush=flush, style=style)
