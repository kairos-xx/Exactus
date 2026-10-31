# Copyright (c) 2026 João Lopes.
"""Parse and discover Exactus step traces."""

from dataclasses import replace
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from typing import Final, final

from exactus.packages.performance.model import (
    Constants as _GroupFinalConstants,
)
from exactus.packages.performance.model import ResourceSample, StepEvent


@final
class Constants:
    """Group module-level constants.

    Attributes:
        line: Grouped module constant.
        trailer: Grouped module constant.
        embedded: Grouped module constant.
        separator: Grouped module constant.
        path: Grouped module constant.
        number: Grouped module constant.

    """

    line: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "^(?P<stamp>\\S+)\\s+\\+\\s*(?P<elapsed>\\d+(?:\\.\\d+)?)s\\s(?P<b"
            "ody>.*)$"
        ),
    )
    trailer: Final[Pattern[str]] = compile_pattern(
        pattern="\\s@(?P<key>[a-z_]+)=(?P<value>\\S+)\\s*$",
    )
    embedded: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "(?:\\bin |, |\\()(?P<value>\\d+(?:\\.\\d+)?)(?P<unit>ms|s)\\b"
        ),
    )
    separator: Final[Pattern[str]] = compile_pattern(pattern=":| — ")
    path: Final[Pattern[str]] = compile_pattern(
        pattern="(?:[A-Za-z]:)?(?:\\.{0,2}/)?[\\w.@+-]+(?:/[\\w.@+-]+)+/?",
    )
    number: Final[Pattern[str]] = compile_pattern(pattern="\\d+(?:\\.\\d+)?")


class StepParser:
    """Discover and parse ``exactus.packages.steps`` trace files."""

    @classmethod
    def parse_file(cls, *, path: Path) -> tuple[StepEvent, ...]:
        """Parse one trace file.

        Args:
            path: Trace file to read as UTF-8.

        Returns:
            Parsed events in source order.

        """
        text: str = path.read_text(encoding="utf-8")
        return cls.parse_lines(lines=tuple(text.splitlines()))

    @classmethod
    def parse_lines(cls, *, lines: tuple[str, ...]) -> tuple[StepEvent, ...]:
        """Parse raw trace lines.

        Trailing ``@key=value`` trailers are removed from the message
        and mapped onto event fields; span end lines contribute their
        measured duration to the matching begin line.

        Args:
            lines: Raw lines in source order.

        Returns:
            Successfully parsed events. Malformed lines are ignored.

        """
        events: list[StepEvent] = []
        for raw in lines:
            line: str = raw.rstrip("\r\n")
            match: Match[str] | None = Constants.line.match(string=line)
            if match is None:
                continue
            body: str = match.group("body")
            if body.startswith("~sample "):
                continue
            spaces: int = len(body) - len(body.lstrip(" "))
            text: str = body.lstrip(" ")
            trailers: dict[str, str] = {}
            while (found := Constants.trailer.search(string=text)) is not None:
                trailers.setdefault(found.group("key"), found.group("value"))
                text = text[: found.start()]
            span: int | None = cls._number(value=trailers.get("span"))
            measured: float | None = cls._seconds(value=trailers.get("dur"))
            if measured is None:
                measured = cls._embedded(message=text)
            phase: str = "point"
            if span is not None:
                phase = "end" if "dur" in trailers else "begin"
            events.append(
                StepEvent(
                    index=len(events),
                    timestamp=match.group("stamp"),
                    elapsed=float(match.group("elapsed")),
                    depth=spaces // 2,
                    message=text,
                    raw=line,
                    thread=trailers.get("thread", "main"),
                    span=span,
                    measured=measured,
                    phase=phase,
                    actor=Constants.separator.split(string=text, maxsplit=1)[
                        0
                    ].strip(),
                    template=cls.template(message=text),
                ),
            )
        durations: dict[int, float] = {
            event.span: event.measured
            for event in events
            if event.phase == "end"
            and event.span is not None
            and event.measured is not None
        }
        return tuple(
            replace(event, measured=durations[event.span])
            if event.phase == "begin"
            and event.span is not None
            and event.span in durations
            else event
            for event in events
        )

    @staticmethod
    def discover(*, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        """Discover step traces from files and directories.

        Args:
            paths: Explicit trace files or directories to search recursively.

        Returns:
            Unique resolved ``steps.txt`` files in deterministic path order.

        """
        found: set[Path] = set()
        for path in paths:
            candidate: Path = path.expanduser().resolve()
            if (
                candidate.is_file()
                and candidate.name == _GroupFinalConstants.step_file
            ):
                found.add(candidate)
            elif candidate.is_dir():
                found.update(
                    candidate.rglob(pattern=_GroupFinalConstants.step_file),
                )
        return tuple(sorted(found))

    @staticmethod
    def tool_name(*, path: Path) -> str:
        """Infer the tool identifier from a trace path.

        Args:
            path: Path to a ``steps.txt`` trace.

        Returns:
            Lowercase tool name derived from the directory above ARTIFACTS,
            or the immediate parent when no ARTIFACTS directory is present.

        """
        parent: Path = path.parent
        if parent.name.upper() == "ARTIFACTS":
            parent = parent.parent
        return parent.name.lower()

    @staticmethod
    def parse_samples(*, lines: tuple[str, ...]) -> tuple[ResourceSample, ...]:
        """Parse ``~sample`` resource lines.

        Args:
            lines: Raw lines in source order.

        Returns:
            Samples in source order; malformed samples are ignored.

        """
        samples: list[ResourceSample] = []
        for raw in lines:
            match: Match[str] | None = Constants.line.match(
                string=raw.rstrip("\r\n"),
            )
            if match is None or not match.group("body").startswith("~sample "):
                continue
            fields: dict[str, str] = dict(
                part.split(sep="=", maxsplit=1)
                for part in match.group("body").split()[1:]
                if "=" in part
            )
            try:
                samples.append(
                    ResourceSample(
                        elapsed=float(match.group("elapsed")),
                        cpu=float(fields["cpu"]),
                        rss=float(fields["rss"]),
                        threads=int(fields.get("threads", "0")),
                        procs=int(fields.get("procs", "0")),
                        read=float(fields.get("read", "0")),
                        write=float(fields.get("write", "0")),
                        scope=fields.get("ioscope", "proc"),
                        raw=raw.rstrip("\r\n"),
                    ),
                )
            except (KeyError, ValueError):
                continue
        return tuple(samples)

    @staticmethod
    def template(*, message: str) -> str:
        """Abstract paths and numbers so repeated operations group.

        Args:
            message: Message text without trailers.

        Returns:
            Message with paths as ``<path>`` and numbers as ``#``.

        """
        return Constants.number.sub(
            repl="#",
            string=Constants.path.sub(repl="<path>", string=message),
        )

    @staticmethod
    def _number(*, value: str | None) -> int | None:
        """Convert a trailer value to an integer.

        Args:
            value: Trailer text or ``None``.

        Returns:
            The integer, or ``None`` when absent or malformed.

        """
        return int(value) if value is not None and value.isdigit() else None

    @staticmethod
    def _seconds(*, value: str | None) -> float | None:
        """Convert a ``1.234s`` trailer value to seconds.

        Args:
            value: Trailer text or ``None``.

        Returns:
            Seconds, or ``None`` when absent or malformed.

        """
        if value is None or not value.endswith("s"):
            return None
        try:
            return float(value[:-1])
        except ValueError:
            return None

    @staticmethod
    def _embedded(*, message: str) -> float | None:
        """Find a duration phrase such as ``exit 0 in 4.006s``.

        Args:
            message: Message text without trailers.

        Returns:
            The last phrase's seconds, or ``None`` when absent.

        """
        values: list[float] = [
            float(found.group("value"))
            / (1000.0 if found.group("unit") == "ms" else 1.0)
            for found in Constants.embedded.finditer(string=message)
        ]
        return values[-1] if values else None
