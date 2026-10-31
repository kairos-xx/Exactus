# Copyright (c) 2026
"""Preserve pytest skip identities and capture per-file execution timings."""

from __future__ import annotations

from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast, final

if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser
    from _pytest.terminal import TerminalReporter


@final
class Constants:
    """Group module-level constants.

    Attributes:
        skip_fields: Grouped module constant.

    """

    skip_fields: Final[int] = 3


class _OptionAccess(Protocol):
    """Define the minimal pytest option accessor consumed here."""

    def getoption(self, name: str) -> str | None:
        """Return the configured value for one option.

        Args:
            name: Option name.

        Returns:
            Configured string value, or ``None`` when unset.

        """
        ...


def pytest_addoption(parser: Parser) -> None:
    """Register Exactus-internal pytest options.

    Args:
        parser: Pytest command-line parser.

    """
    _ = parser.addoption(
        "--exactus-timings-output",
        action="store",
        default=None,
        help="Write per-test-file execution timings for Exactus.",
    )


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    """Emit structured skip records and optional timing telemetry.

    Args:
        terminalreporter: Pytest's terminal reporter with completed reports.

    """
    for report in terminalreporter.stats.get("skipped", []):
        detail: object = report.longrepr
        if not isinstance(detail, tuple):
            continue
        fields: tuple[object, ...] = cast(typ="tuple[object, ...]", val=detail)
        if len(fields) != Constants.skip_fields:
            continue
        path, line, reason = cast(typ="tuple[str, int, str]", val=detail)
        terminalreporter.write_line(
            line="EXACTUS_SKIPPED "
            + dumps(
                obj={
                    "test": report.nodeid,
                    "path": path,
                    "line": line,
                    "reason": reason,
                },
            ),
        )
    config: _OptionAccess = cast(
        typ="_OptionAccess",
        val=terminalreporter.config,
    )
    raw_output: str | None = config.getoption(name="--exactus-timings-output")
    if raw_output is None or not raw_output:
        return
    timings: dict[str, float] = {}
    reports: list[object] = [
        report
        for values in terminalreporter.stats.values()
        for report in values
    ]
    for raw_report in reports:
        nodeid: object = getattr(raw_report, "nodeid", None)
        duration: object = getattr(raw_report, "duration", None)
        if (
            not isinstance(nodeid, str)
            or not isinstance(duration, (int, float))
            or isinstance(duration, bool)
        ):
            continue
        relative: str = nodeid.split(sep="::", maxsplit=1)[0]
        if not relative.endswith(".py"):
            continue
        timings[relative] = timings.get(relative, 0.0) + float(duration)
    output: Path = Path(raw_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        data=dumps(obj={"version": 3, "files": timings}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
