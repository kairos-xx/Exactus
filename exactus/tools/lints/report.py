# Copyright (c) 2026
"""Normalize the LINTS report: summary, scope, findings and metrics.

``LintExactus.run`` returns the legacy payload (``tools``, ``summary``,
``findings``). ``report_data`` keeps every legacy key and field and adds
the normalized blocks the report templates read: ``summary`` counters,
``scope``, findings with ``id``/``title``/``path``/``blocking``/``source``
ordered by linter then location, and ``extension.metrics`` (per-linter
status, version, files, findings, severities, exit code and duration;
top rules; files with the most findings; severities per linter).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Final

from exactus.tools.lints.compliance import Constants as ComplianceRules
from exactus.tools.lints.core import Constants as LintConstants

if TYPE_CHECKING:
    from collections.abc import Mapping

    from exactus.tools.common.json_types import JsonValue


class ReportTables:
    """Constants of the normalized LINTS report.

    Attributes:
        id_prefix: Prefix of every finding identifier.
        top_limit: Rows kept in the top-rules and top-files tables.
        title_chars: Longest finding title before it is shortened.
        ellipsis: Suffix of a shortened title.
        severities: Lint severities in report order.
        builtin: Version shown for the built-in convention checkers.
        custom_prefix: Name prefix of the built-in convention checkers.
        missing: Skip reason suffix of a linter that is not installed.
        file_groups: ``summary.analysis.files`` counter of the files each
            linter is handed; ``typescript`` checks a compiler project
            covering the JavaScript file set.
        ranks: Report position of every linter.

    """

    id_prefix: Final[str] = "LINTS"
    top_limit: Final[int] = 20
    title_chars: Final[int] = 120
    ellipsis: Final[str] = "…"
    severities: Final[tuple[str, ...]] = ("error", "warning", "information")
    builtin: Final[str] = "built-in"
    custom_prefix: Final[str] = "custom_"
    missing: Final[str] = "is not installed."
    file_groups: Final[dict[str, str]] = {
        "custom_compliance": "python",
        "custom_shebang": "python",
        "custom_python": "python",
        "custom_python_long_lines": "python",
        "custom_javascript": "javascript_jsx",
        "custom_javascript_delimiters": "javascript_jsx",
        "custom_javascript_notation": "javascript_jsx",
        "custom_css": "css",
        "custom_html": "html",
        "ruff": "python",
        "ruff_docs": "python",
        "basedpyright": "python",
        "pyrefly": "python",
        "eslint": "javascript_jsx",
        "typescript": "javascript_jsx",
        "stylelint": "css",
        "htmlhint": "html",
    }
    ranks: Final[dict[str, int]] = {
        name: index
        for index, name in enumerate(iterable=LintConstants.tool_names)
    }


def _object(value: JsonValue) -> dict[str, JsonValue]:
    """Return a JSON object, or an empty one for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is an object, else ``{}``.

    """
    return value if isinstance(value, dict) else {}


def _list(value: JsonValue) -> list[JsonValue]:
    """Return a JSON list, or an empty one for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is a list, else ``[]``.

    """
    return value if isinstance(value, list) else []


def _int(value: JsonValue) -> int:
    """Return a JSON integer, or zero for any other value.

    Args:
        value: Any JSON value.

    Returns:
        ``value`` when it is an integer (not a boolean), else ``0``.

    """
    return (
        value if isinstance(value, int) and not isinstance(value, bool) else 0
    )


def _rank(name: str) -> int:
    """Return the report position of a linter.

    Args:
        name: Linter name.

    Returns:
        Its index in the linter order; unknown names sort last.

    """
    return ReportTables.ranks.get(name, len(ReportTables.ranks))


def relative_path(*, value: str, root: Path) -> str:
    """Express a linter's file name relative to the project root.

    Args:
        value: File name as the linter reported it (absolute or relative).
        root: Project root the linters ran in.

    Returns:
        The root-relative POSIX path; a path outside the root is kept
        as reported; an empty name stays empty.

    """
    if not value:
        return ""
    path: Path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def linter_status(*, entry: JsonValue) -> str:
    """Classify how one linter took part in the run.

    Args:
        entry: The linter's legacy ``tools`` entry, if any.

    Returns:
        ``ran``; ``missing`` (not installed); ``skipped`` (any other
        skip); or ``not run`` (no matching files, no entry).

    """
    if not isinstance(entry, dict):
        return "not run"
    if not entry.get("skipped"):
        return "ran"
    reason: str = str(object=entry.get("stderr", "")).strip()
    return "missing" if reason.endswith(ReportTables.missing) else "skipped"


def _first_sentence(text: str) -> str:
    """Return the first sentence of a line, ignoring code-span periods.

    Args:
        text: One message line.

    Returns:
        Text up to the first ``". "`` outside a backtick code span, or
        the whole line.

    """
    ticks: int = 0
    index: int
    char: str
    for index, char in enumerate(iterable=text):
        if char == "`":
            ticks += 1
        elif (
            char == "."
            and not ticks % 2
            and text[index + 1 : index + 2] == " "
        ):
            return text[: index + 1]
    return text


def finding_title(*, message: str, rule: str, source: str) -> str:
    """Return the one-line title of a lint finding.

    Args:
        message: Linter message, possibly several lines long.
        rule: Rule identifier.
        source: Linter name.

    Returns:
        The first sentence of the first message line, shortened past
        ``title_chars``; the rule (or ``<source> finding``) when the
        message is empty.

    """
    stripped: str = message.strip()
    if not stripped:
        return rule or f"{source} finding"
    first: str = _first_sentence(text=stripped.splitlines()[0].strip())
    if len(first) <= ReportTables.title_chars:
        return first
    return (
        first[: ReportTables.title_chars - 1].rstrip() + ReportTables.ellipsis
    )


def _location_key(
    row: tuple[dict[str, JsonValue], str],
) -> tuple[int, str, int, int, str]:
    """Order findings by linter, then path, line, column and rule.

    Args:
        row: Legacy finding and its root-relative path.

    Returns:
        The sort key.

    """
    finding: dict[str, JsonValue]
    path: str
    finding, path = row
    return (
        _rank(name=str(object=finding.get("tool", ""))),
        path,
        _int(value=finding.get("line")),
        _int(value=finding.get("column")),
        str(object=finding.get("rule", "")),
    )


def normalized_findings(
    *,
    report: Mapping[str, JsonValue],
    root: Path,
) -> list[JsonValue]:
    """Return the findings in the normalized shape, keeping legacy fields.

    Errors and warnings both block the gate; only information-level
    findings are allowed without failing the exactus.

    Args:
        report: Legacy LINTS payload (deduplicated ``findings``).
        root: Project root the linters ran in.

    Returns:
        Findings ordered by linter (report order) then path, line, column
        and rule, numbered ``LINTS-001`` onwards.

    """
    rows: list[tuple[dict[str, JsonValue], str]] = [
        (
            item,
            relative_path(value=str(object=item.get("file", "")), root=root),
        )
        for item in _list(value=report.get("findings"))
        if isinstance(item, dict)
    ]
    rows.sort(key=_location_key)
    findings: list[JsonValue] = []
    index: int
    item: dict[str, JsonValue]
    path: str
    for index, (item, path) in enumerate(iterable=rows, start=1):
        source: str = str(object=item.get("tool", ""))
        message: str = str(object=item.get("message", ""))
        rule: str = str(object=item.get("rule", ""))
        severity: str = str(object=item.get("severity", "")) or "warning"
        findings.append(
            {
                **item,
                "id": f"{ReportTables.id_prefix}-{index:03d}",
                "title": finding_title(
                    message=message,
                    rule=rule,
                    source=source,
                ),
                "severity": severity,
                "rule": rule,
                "path": path,
                "line": _int(value=item.get("line")),
                "column": _int(value=item.get("column")),
                "message": message,
                "blocking": severity in ("error", "warning"),
                "source": source,
            },
        )
    return findings


def _severity_counts(*, findings: list[JsonValue]) -> dict[str, JsonValue]:
    """Count findings per severity, known severities first.

    Args:
        findings: Normalized findings.

    Returns:
        Non-zero counts keyed by severity.

    """
    counts: Counter[str] = Counter(
        str(object=item.get("severity", ""))
        for item in findings
        if isinstance(item, dict)
    )
    ordered: list[str] = [
        *(level for level in ReportTables.severities if counts[level]),
        *sorted(set(counts) - set(ReportTables.severities)),
    ]
    return {level: counts[level] for level in ordered}


def _skipped(
    *,
    report: Mapping[str, JsonValue],
    root: Path,
) -> list[JsonValue]:
    """List the files a linter's own configuration told it to ignore.

    Args:
        report: Legacy LINTS payload.
        root: Project root the linters ran in.

    Returns:
        ``target``/``reason`` rows; only ESLint reports ignored files.

    """
    tools: dict[str, JsonValue] = _object(value=report.get("tools"))
    rows: list[JsonValue] = []
    name: str
    item: JsonValue
    for name in LintConstants.tool_names:
        entry: dict[str, JsonValue] = _object(value=tools.get(name))
        for item in _list(value=entry.get("skipped_files")):
            skip: dict[str, JsonValue] = _object(value=item)
            rows.append(
                {
                    "target": relative_path(
                        value=str(object=skip.get("file", "")),
                        root=root,
                    ),
                    "reason": f"{name}: {skip.get('reason', '')}",
                },
            )
    return rows


def _scope(
    *,
    report: Mapping[str, JsonValue],
    root: Path,
) -> dict[str, JsonValue]:
    """Return the normalized ``scope`` block.

    Args:
        report: Legacy LINTS payload.
        root: Project root the linters ran in.

    Returns:
        Requested targets as ``include``, ignore globs as ``exclude`` and
        linter-ignored files as ``skipped``.

    """
    analysis: dict[str, JsonValue] = _object(
        value=_object(value=report.get("summary")).get("analysis"),
    )
    return {
        "include": [
            str(object=target)
            for target in _list(value=analysis.get("targets"))
        ],
        "exclude": [
            str(object=pattern)
            for pattern in _list(value=analysis.get("ignore_patterns"))
        ],
        "skipped": _skipped(report=report, root=root),
    }


def _summary(
    *,
    report: Mapping[str, JsonValue],
    findings: list[JsonValue],
) -> dict[str, JsonValue]:
    """Return the legacy summary with the normalized counters added.

    Args:
        report: Legacy LINTS payload.
        findings: Normalized findings.

    Returns:
        Legacy ``timing``/``host``/``analysis``/``tools``/``clean`` plus
        ``targets_eligible``, ``targets_analyzed``, ``findings_total``
        and ``severity``.

    """
    legacy: dict[str, JsonValue] = _object(value=report.get("summary"))
    files: dict[str, JsonValue] = _object(
        value=_object(value=legacy.get("analysis")).get("files"),
    )
    unique: int = _int(value=files.get("unique_analyzed"))
    return {
        **legacy,
        "targets_eligible": unique,
        "targets_analyzed": unique,
        "findings_total": len(findings),
        "severity": _severity_counts(findings=findings),
    }


def _linter_row(
    *,
    name: str,
    entry: JsonValue,
    files: Mapping[str, JsonValue],
    counts: Counter[tuple[str, str]],
) -> dict[str, JsonValue]:
    """Return the metrics row of one linter.

    Args:
        name: Linter name.
        entry: The linter's legacy ``tools`` entry, if any.
        files: ``summary.analysis.files`` counters.
        counts: Findings per ``(linter, severity)``.

    Returns:
        Status, version, files checked, findings by severity, exit code
        and duration (``null`` when unknown).

    """
    status: str = linter_status(entry=entry)
    record: dict[str, JsonValue] = _object(value=entry)
    ran: bool = status == "ran"
    group: str | None = ReportTables.file_groups.get(name)
    version: JsonValue = record.get("version")
    duration: JsonValue = record.get("duration_seconds")
    code: JsonValue = record.get("returncode")
    errors: int = counts[name, "error"]
    warnings: int = counts[name, "warning"]
    information: int = counts[name, "information"]
    return {
        "linter": name,
        "status": status,
        "version": (
            ReportTables.builtin
            if ran and name.startswith(ReportTables.custom_prefix)
            else version
            if isinstance(version, str)
            else None
        ),
        "files": (
            (_int(value=files.get(group)) if group is not None else None)
            if ran
            else 0
        ),
        "findings": sum(
            count for (linter, _), count in counts.items() if linter == name
        ),
        "errors": errors,
        "warnings": warnings,
        "information": information,
        "exit_code": code if ran and isinstance(code, int) else None,
        "duration_seconds": (
            duration
            if ran
            and isinstance(duration, int | float)
            and not isinstance(duration, bool)
            else None
        ),
    }


def _rule_key(item: tuple[tuple[str, str], int]) -> tuple[int, int, str]:
    """Order rules by count (descending), linter, then rule.

    Args:
        item: ``((rule, linter), count)`` pair.

    Returns:
        The sort key.

    """
    rule: str
    linter: str
    count: int
    (rule, linter), count = item
    return (-count, _rank(name=linter), rule)


def _file_key(item: tuple[str, int]) -> tuple[int, str]:
    """Order files by count (descending), then path.

    Args:
        item: ``(path, count)`` pair.

    Returns:
        The sort key.

    """
    path: str
    count: int
    path, count = item
    return (-count, path)


def _metrics(
    *,
    report: Mapping[str, JsonValue],
    findings: list[JsonValue],
) -> dict[str, JsonValue]:
    """Return the ``extension.metrics`` block.

    Args:
        report: Legacy LINTS payload.
        findings: Normalized findings.

    Returns:
        ``overview`` counters, ``linters`` rows, ``top_rules``,
        ``top_files`` and ``severity_by_linter``.

    """
    tools: dict[str, JsonValue] = _object(value=report.get("tools"))
    files: dict[str, JsonValue] = _object(
        value=_object(
            value=_object(value=report.get("summary")).get("analysis"),
        ).get("files"),
    )
    items: list[dict[str, JsonValue]] = [
        item for item in findings if isinstance(item, dict)
    ]
    counts: Counter[tuple[str, str]] = Counter(
        (str(object=item.get("source", "")), str(object=item.get("severity")))
        for item in items
    )
    rules: Counter[tuple[str, str]] = Counter(
        (str(object=item.get("rule", "")), str(object=item.get("source", "")))
        for item in items
    )
    paths: Counter[str] = Counter(
        str(object=item.get("path", "")) for item in items if item.get("path")
    )
    linters: list[JsonValue] = [
        _linter_row(
            name=name,
            entry=tools.get(name),
            files=files,
            counts=counts,
        )
        for name in LintConstants.tool_names
    ]
    statuses: list[str] = [
        str(object=_object(value=row).get("status")) for row in linters
    ]
    return {
        "overview": {
            "linters_run": statuses.count("ran"),
            "linters_unavailable": statuses.count("missing")
            + statuses.count("skipped"),
            "files_analyzed": _int(value=files.get("unique_analyzed")),
            "files_with_findings": len(paths),
            "rules_triggered": len(rules),
            "findings": len(items),
        },
        "linters": linters,
        "top_rules": [
            {"rule": rule, "linter": linter, "count": count}
            for (rule, linter), count in sorted(rules.items(), key=_rule_key)[
                : ReportTables.top_limit
            ]
        ],
        "top_files": [
            {"path": path, "count": count}
            for path, count in sorted(paths.items(), key=_file_key)[
                : ReportTables.top_limit
            ]
        ],
        "severity_by_linter": [
            {"linter": name, "severity": level, "count": counts[name, level]}
            for name in LintConstants.tool_names
            for level in ReportTables.severities
            if counts[name, level]
        ],
    }


def _rules(*, findings: list[JsonValue]) -> list[JsonValue]:
    """List engineering rules and every rule reported by the other linters.

    Args:
        findings: Normalized lint findings.

    Returns:
        Rule titles, categories and counts, including clean engineering rules.

    """
    catalog: dict[str, tuple[str, str]] = dict(ComplianceRules.rules)
    counts: Counter[str] = Counter()
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        rule: str = str(object=raw.get("rule") or "unknown")
        counts[rule] += 1
        catalog.setdefault(
            rule,
            (
                str(object=raw.get("title") or rule),
                str(object=raw.get("source") or "Other"),
            ),
        )
    return [
        {
            "rule": rule,
            "title": title,
            "category": category,
            "count": counts[rule],
        }
        for rule, (title, category) in catalog.items()
    ]


def report_data(
    *,
    report: Mapping[str, JsonValue],
    root: Path,
) -> dict[str, JsonValue]:
    """Return the LINTS payload with the normalized blocks added.

    Args:
        report: Legacy payload returned by ``LintExactus.run``.
        root: Project root the linters ran in.

    Returns:
        Every legacy key, with ``summary`` extended, ``findings`` in the
        normalized shape (legacy fields kept), and new ``scope`` and
        ``extension`` (``metrics``) blocks.

    """
    findings: list[JsonValue] = normalized_findings(report=report, root=root)
    return {
        **report,
        "summary": _summary(report=report, findings=findings),
        "scope": _scope(report=report, root=root),
        "findings": findings,
        "extension": {
            "metrics": _metrics(report=report, findings=findings),
            "rules": _rules(findings=findings),
        },
    }
