# Copyright (c) 2026
"""Parse captured web-server output into screenshot diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from re import Match, Pattern
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        access: Grouped module constant.

    """

    access: Final[Pattern[str]] = re_compile(
        pattern=(
            '"(?P<method>[A-Z]+)\\s+(?P<url>\\S+)\\s+HTTP/[0-9.]+"\\s+(?P<stat'
            "us>[45][0-9]{2})\\b"
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ServerDiagnostic:
    """One HTTP error request parsed from captured server output.

    Attributes:
        stream: Captured stream the line came from (stdout/stderr).
        line: Raw access-log line.
        method: HTTP request method.
        url: Requested path.
        status: HTTP response status code.
        severity: ``warning`` for 4xx, ``error`` for 5xx.

    """

    stream: str
    line: str
    method: str
    url: str
    status: int
    severity: str


def parse_server_log(*, path: Path) -> tuple[ServerDiagnostic, ...]:
    """Parse Flask/Werkzeug, Uvicorn/FastAPI, and generic access logs.

    Args:
        path: Captured line-oriented server log.

    Returns:
        Deduplicated HTTP 4xx/5xx diagnostics in observation order.

    """
    try:
        lines: list[str] = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    found: list[ServerDiagnostic] = []
    seen: set[tuple[str, str, int]] = set()
    for raw in lines:
        stream, _, line = raw.partition(" ")
        match: Match[str] | None = Constants.access.search(string=line)
        if match is None:
            continue
        method: str = match.group("method")
        url: str = match.group("url")
        status: int = int(match.group("status"))
        key: tuple[str, str, int] = (method, url, status)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            ServerDiagnostic(
                stream=stream.removeprefix("[").removesuffix("]"),
                line=line,
                method=method,
                url=url,
                status=status,
                severity=(
                    "error"
                    if status >= HTTPStatus.INTERNAL_SERVER_ERROR
                    else "warning"
                ),
            ),
        )
    return tuple(found)
