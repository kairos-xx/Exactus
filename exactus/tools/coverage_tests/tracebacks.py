# Copyright (c) 2026
"""Locate where and why each failing test failed.

pytest prints one traceback section per failed or errored test under its
``FAILURES`` and ``ERRORS`` banners, in the same order as the ``FAILED``
and ``ERROR`` lines of its short summary. Each section ends with the
location of the deepest frame (``path:line: ExceptionType`` in the
default ``long``/``auto`` styles, ``path:line: in function`` in the
``short`` style, ``File "path", line N`` in the ``native`` style) and
carries the exception text on its ``E`` lines. The deepest frame inside
the project root is the failing assertion or raise in the test or one of
its helpers; frames in the standard library or installed packages are
skipped.

The Node test runner's default ``spec`` reporter lists failures after a
``✖ failing tests:`` banner: ``test at path:line:column``, ``✖ name``,
the indented error and its stack, innermost frame first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from re import Match, Pattern
from re import compile as recompile
from typing import TYPE_CHECKING, ClassVar, Final, final
from urllib.parse import unquote, urlparse

from exactus.packages.steps import trace

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
class Constants:
    """Group module-level constants.

    Attributes:
        foreign_parts: Grouped module constant.

    """

    foreign_parts: Final[frozenset[str]] = frozenset(
        {"site-packages", "dist-packages", "node_modules", ".venv", "venv"},
    )


@dataclass(frozen=True, slots=True)
class FailureSite:
    """Where and why one test failed.

    Attributes:
        path: Root-relative POSIX path of the deepest project frame, or
            ``None`` when no frame lies inside the project.
        line: One-based line of that frame, or ``None``.
        reason: First line of the error: exception type and message.

    """

    path: str | None
    line: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class NamedFailure:
    """One failing JavaScript test with its location and reason.

    Attributes:
        name: Test name reported by the runner.
        site: Failing location and reason.

    """

    name: str
    site: FailureSite


@final
class ProjectPaths:
    """Map frame paths printed by test runners to project files."""

    @staticmethod
    def relative(*, root: Path, path: str) -> str | None:
        """Return a frame path relative to the project root.

        Args:
            root: Project root the runner was started in.
            path: Absolute or root-relative path printed by the runner.

        Returns:
            The POSIX path relative to ``root`` when it names an existing
            project file outside installed-package directories, else
            ``None``.

        """
        base: Path = root.resolve()
        candidate: Path = Path(path)
        try:
            resolved: Path = (
                candidate if candidate.is_absolute() else base / candidate
            ).resolve()
        except (OSError, RuntimeError, ValueError):
            return None
        if not resolved.is_relative_to(base) or not resolved.is_file():
            return None
        relative: Path = resolved.relative_to(base)
        if any(part in Constants.foreign_parts for part in relative.parts):
            return None
        return relative.as_posix()


@final
class PytestTracebacks:
    """Read failing locations and reasons from pytest's terminal output.

    Attributes:
        BANNER: ``=== NAME ===`` banner line.
        SECTION: ``___ title ___`` section heading of one report.
        CAPTURE: ``--- Captured ... ---`` heading ending a traceback.
        LOCATION: ``path:line:`` location line of a traceback entry.
        NATIVE: ``File "path", line N`` frame of the ``native`` style.
        ERROR: ``E`` line carrying exception text.
        EXCEPTION: Exception class name printed after a location.
        BLOCKS: Banner names holding failure sections, by summary kind.

    """

    BANNER: ClassVar[Pattern[str]] = recompile(
        pattern="^={3,} (?P<name>.+?) ={3,}$",
    )
    SECTION: ClassVar[Pattern[str]] = recompile(
        pattern="^_{2,} (?P<title>.+?) _{2,}$",
    )
    CAPTURE: ClassVar[Pattern[str]] = recompile(pattern="^-{3,} .+ -{3,}$")
    LOCATION: ClassVar[Pattern[str]] = recompile(
        pattern="^(?P<path>[^\\s:>][^:]*?):(?P<line>\\d+):(?: (?P<rest>.*))?$",
    )
    NATIVE: ClassVar[Pattern[str]] = recompile(
        pattern='^\\s*File "(?P<path>[^"]+)", line (?P<line>\\d+)',
    )
    ERROR: ClassVar[Pattern[str]] = recompile(
        pattern="^E(?:\\s+(?P<text>.*))?$",
    )
    EXCEPTION: ClassVar[Pattern[str]] = recompile(pattern="^[A-Za-z_][\\w.]*$")
    BLOCKS: ClassVar[dict[str, str]] = {
        "FAILURES": "FAILED",
        "ERRORS": "ERROR",
    }

    @classmethod
    def sections(cls, *, text: str) -> list[tuple[str, str, list[str]]]:
        """Split pytest output into failure sections.

        Args:
            text: Combined pytest output.

        Returns:
            ``(kind, title, lines)`` per section in print order; ``kind``
            is ``FAILED`` or ``ERROR``.

        """
        found: list[tuple[str, str, list[str]]] = []
        kind: str | None = None
        current: list[str] | None = None
        line: str
        for line in text.splitlines():
            banner: Match[str] | None = cls.BANNER.match(string=line)
            if banner is not None:
                kind = cls.BLOCKS.get(banner.group("name"))
                current = None
                continue
            if kind is None:
                continue
            heading: Match[str] | None = cls.SECTION.match(string=line)
            if heading is not None:
                current = []
                found.append((kind, heading.group("title"), current))
            elif current is not None:
                current.append(line)
        return found

    @classmethod
    def site(cls, *, lines: Sequence[str], root: Path) -> FailureSite:
        """Read the location and reason of one failure section.

        Args:
            lines: Section lines after its heading.
            root: Project root pytest ran in.

        Returns:
            The deepest project frame and the exception's first line.

        """
        errors: list[str] = []
        located: tuple[str, int] | None = None
        exception: str | None = None
        line: str
        for line in lines:
            if cls.CAPTURE.match(string=line) is not None:
                break
            error: Match[str] | None = cls.ERROR.match(string=line)
            if error is not None:
                errors.append((error.group("text") or "").strip())
                continue
            frame: Match[str] | None = cls.LOCATION.match(
                string=line,
            ) or cls.NATIVE.match(string=line)
            if frame is None:
                continue
            rest: str = (frame.groupdict().get("rest") or "").strip()
            exception = (
                rest if cls.EXCEPTION.match(string=rest) is not None else None
            )
            path: str | None = ProjectPaths.relative(
                root=root,
                path=frame.group("path"),
            )
            if path is not None:
                located = (path, int(frame.group("line")))
        return FailureSite(
            path=located[0] if located else None,
            line=located[1] if located else None,
            reason=cls.reason(errors=errors, exception=exception),
        )

    @classmethod
    def sites(
        cls,
        *,
        text: str,
        root: Path,
        entries: Sequence[tuple[str, str]],
    ) -> tuple[FailureSite | None, ...]:
        """Locate every short-summary entry in its traceback section.

        Args:
            text: Combined pytest output.
            root: Project root pytest ran in.
            entries: ``(kind, node)`` pairs from the short summary.

        Returns:
            One site per entry, in entry order; ``None`` when no section
            matches (for example with ``--tb=no`` or ``--tb=line``).

        """
        pending: list[tuple[str, str, list[str]]] = cls.sections(text=text)
        found: list[FailureSite | None] = []
        kind: str
        node: str
        for kind, node in entries:
            accepted: tuple[str, ...] = cls.titles(kind=kind, node=node)
            index: int = next(
                (
                    position
                    for position, (section_kind, title, _) in enumerate(
                        iterable=pending,
                    )
                    if section_kind == kind and title in accepted
                ),
                -1,
            )
            if index < 0:
                found.append(None)
                continue
            found.append(cls.site(lines=pending.pop(index)[2], root=root))
        if entries:
            resolved: int = sum(site is not None for site in found)
            trace(
                step=(
                    f"tracebacks: {resolved} sites located for "
                    f"{len(entries)} summary entries"
                ),
                depth=4,
            )
        return tuple(found)

    @staticmethod
    def titles(*, kind: str, node: str) -> tuple[str, ...]:
        """Return the section titles pytest prints for one summary entry.

        Args:
            kind: ``FAILED`` or ``ERROR``.
            node: Pytest node id from the short summary.

        Returns:
            Section titles that belong to the entry.

        """
        file: str
        separator: str
        rest: str
        file, separator, rest = node.partition("::")
        if not separator:
            return (f"ERROR collecting {file}",)
        name: str = rest.replace("::", ".")
        if kind == "ERROR":
            return (
                f"ERROR at setup of {name}",
                f"ERROR at teardown of {name}",
                name,
            )
        return (name,)

    @staticmethod
    def reason(*, errors: Sequence[str], exception: str | None) -> str:
        """Compose the first-line reason of one failure.

        Args:
            errors: Text of the section's ``E`` lines, in order.
            exception: Exception class printed after the last location.

        Returns:
            ``Type: message`` when both are known, else what is known.

        """
        first: str = next((item for item in errors if item), "")
        if not first:
            return exception or ""
        head: str = first.partition(":")[0]
        if exception and (not head.endswith(exception)):
            return f"{exception}: {first}"
        return first


@final
class NodeTestFailures:
    """Read failing tests from the Node test runner's ``spec`` output.

    Attributes:
        BANNER: Line opening the failing-tests list.
        TEST_AT: ``test at path:line:column`` line opening one failure.
        NAME: ``✖ name (duration)`` line naming the failing test.
        FRAME: Stack frame ending in ``path:line:column``.

    """

    BANNER: ClassVar[str] = "✖ failing tests:"
    TEST_AT: ClassVar[Pattern[str]] = recompile(
        pattern="^test at (?P<path>.+?):(?P<line>\\d+):\\d+$",
    )
    NAME: ClassVar[Pattern[str]] = recompile(
        pattern="^✖ (?P<name>.+?)(?: \\([\\d.]+m?s\\))?$",
    )
    FRAME: ClassVar[Pattern[str]] = recompile(
        pattern=(
            "^\\s+at (?:.*?\\()?(?P<path>[^()\\s]+?):(?P<line>\\d+):\\d+\\)?$"
        ),
    )

    @classmethod
    def entry(cls, *, lines: Sequence[str], root: Path) -> NamedFailure | None:
        """Read one failing-test entry.

        Args:
            lines: Lines from ``test at`` up to the next entry.
            root: Project root Node ran in.

        Returns:
            The failure, or ``None`` when the entry names no test.

        """
        start: Match[str] | None = cls.TEST_AT.match(string=lines[0])
        name: str = ""
        reason: str = ""
        located: tuple[str, int] | None = None
        if start is not None:
            test_path: str | None = cls.frame_path(
                root=root,
                raw=start.group("path"),
            )
            located = (
                (test_path, int(start.group("line"))) if test_path else None
            )
        frame_found: bool = False
        line: str
        for line in lines[1:]:
            named: Match[str] | None = cls.NAME.match(string=line)
            if named is not None and (not name):
                name = named.group("name")
                continue
            frame: Match[str] | None = cls.FRAME.match(string=line)
            if frame is not None:
                path: str | None = cls.frame_path(
                    root=root,
                    raw=frame.group("path"),
                )
                if path is not None and (not frame_found):
                    located = (path, int(frame.group("line")))
                    frame_found = True
                continue
            if name and (not reason) and line.strip():
                reason = line.strip()
        if not name:
            return None
        return NamedFailure(
            name=name,
            site=FailureSite(
                path=located[0] if located else None,
                line=located[1] if located else None,
                reason=reason,
            ),
        )

    @classmethod
    def parse(cls, *, text: str, root: Path) -> tuple[NamedFailure, ...]:
        """Read every failing test of one Node test-runner run.

        Args:
            text: Combined runner output.
            root: Project root Node ran in.

        Returns:
            Failing tests in report order.

        """
        lines: list[str] = text.splitlines()
        if cls.BANNER not in lines:
            return ()
        groups: list[list[str]] = []
        line: str
        for line in lines[lines.index(cls.BANNER) + 1 :]:
            if cls.TEST_AT.match(string=line) is not None:
                groups.append([line])
            elif groups:
                groups[-1].append(line)
        found: list[NamedFailure] = []
        group: list[str]
        for group in groups:
            failure: NamedFailure | None = cls.entry(lines=group, root=root)
            if failure is not None:
                found.append(failure)
        trace(
            step=(
                f"node failures: {len(found)} sites from "
                f"{len(groups)} failure groups"
            ),
            depth=4,
        )
        return tuple(found)

    @staticmethod
    def frame_path(*, root: Path, raw: str) -> str | None:
        """Map a printed frame or test path to a project file.

        Args:
            root: Project root Node ran in.
            raw: ``file://`` URL or plain path.

        Returns:
            Root-relative POSIX path, or ``None`` outside the project.

        """
        path: str = (
            unquote(string=urlparse(url=raw).path)
            if raw.startswith("file://")
            else raw
        )
        return ProjectPaths.relative(root=root, path=path)
