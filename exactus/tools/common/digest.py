# Copyright (c) 2026
"""Summarize tool reports into failure digests for aggregate reports.

Every exactus tool writes the same ``result.json`` envelope: a ``findings``
list whose entries carry a rule or code, a file, a line, and a message,
plus tool-specific extras such as ``test_execution`` or ``gates``. This
module reads that envelope generically and renders what a reader needs to
act on a failing pipeline: how many findings, which rules and files
dominate, the first few findings with their locations, failed tests with
their reasons, and any gate that was missed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from re import sub
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        top_rules: Grouped module constant.
        top_files: Grouped module constant.
        top_findings: Grouped module constant.
        top_tests: Grouped module constant.
        top_distinct: Grouped module constant.
        origin_pattern: Grouped module constant.
        rule_keys: Grouped module constant.
        message_keys: Grouped module constant.
        extra_lists: Grouped module constant.
        message_limit: Grouped module constant.

    """

    top_rules: Final[int] = 8
    top_files: Final[int] = 8
    top_findings: Final[int] = 12
    top_tests: Final[int] = 15
    top_distinct: Final[int] = 8
    origin_pattern: Final[str] = "https?://[\\w.\\-]+(?::\\d+)?"
    rule_keys: Final[tuple[str, ...]] = ("rule", "code", "kind", "category")
    message_keys: Final[tuple[str, ...]] = (
        "message",
        "reason",
        "detail",
        "suggestion",
    )
    extra_lists: Final[tuple[tuple[str, str], ...]] = (
        ("bare_imports", "bare-import"),
        ("type_hints", "missing-type-hint"),
        ("ambiguous", "ambiguous-call"),
    )
    message_limit: Final[int] = 160


@dataclass(frozen=True, slots=True)
class FindingLine:
    """One finding reduced to what a reader needs.

    Attributes:
        rule: Rule or code that raised it.
        location: ``file:line`` relative to the project, or ``-``.
        message: First line of the message, clipped.

    """

    rule: str
    location: str
    message: str


@dataclass(frozen=True, slots=True)
class ToolDigest:
    """A tool report summarized for an aggregate report.

    Attributes:
        tool: Tool or pipeline identifier.
        status: ``PASS``, ``FAIL`` or another reported status.
        resume: The tool's own one-line resume.
        findings: Number of findings.
        rules: Most frequent ``(rule, count)`` pairs.
        files: Most affected ``(file, count)`` pairs.
        top: First findings in report order.
        distinct: Most frequent distinct problems: ``(rule, message, count,
            example location)`` with origins and ports normalized away.
        notes: Headline facts, such as coverage or a missed gate.
        failed_tests: ``(test, reason)`` pairs for failed tests.

    """

    tool: str
    status: str
    resume: str
    findings: int
    rules: tuple[tuple[str, int], ...]
    files: tuple[tuple[str, int], ...]
    top: tuple[FindingLine, ...]
    distinct: tuple[tuple[str, str, int, str], ...]
    notes: tuple[str, ...]
    failed_tests: tuple[tuple[str, str], ...]


def _text(*, value: JsonValue | None) -> str:
    """Render a JSON scalar as text.

    Args:
        value: Decoded JSON value.

    Returns:
        The text, or an empty string for non-scalars and ``None``.

    """
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and (not isinstance(value, bool)):
        return str(object=value)
    return ""


def _first(*, entry: Mapping[str, JsonValue], keys: Sequence[str]) -> str:
    """Return the first non-empty text among ``keys``.

    Args:
        entry: One finding.
        keys: Candidate keys in priority order.

    Returns:
        The text found, or an empty string.

    """
    for key in keys:
        text: str = _text(value=entry.get(key))
        if text:
            return text
    return ""


def _relative(*, path: str, root: str) -> str:
    """Express a file relative to the project root.

    Args:
        path: Path as reported, possibly absolute.
        root: Project root as reported.

    Returns:
        The shortened path.

    """
    prefix: str = root.rstrip("/") + "/"
    return path[len(prefix) :] if root and path.startswith(prefix) else path


def _collect(
    *,
    fields: Mapping[str, JsonValue],
) -> list[Mapping[str, JsonValue]]:
    """Gather every finding-like entry of a report.

    Args:
        fields: Decoded ``result.json``.

    Returns:
        Entries from ``findings`` plus tool-specific lists, each tagged
        with a ``rule`` when it had none. Normalized findings (items with
        an ``id``) already include those lists, so they are read alone.

    """
    entries: list[Mapping[str, JsonValue]] = []
    analyzer: str = _text(value=fields.get("analyzer"))
    listed: JsonValue | None = fields.get("findings")
    normalized: bool = isinstance(listed, list) and any(
        isinstance(item, dict) and "id" in item for item in listed
    )
    sources: tuple[tuple[str, str], ...] = (
        ("findings", analyzer),
        *(() if normalized else Constants.extra_lists),
    )
    for key, label in sources:
        raw: JsonValue | None = fields.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            entry: dict[str, JsonValue] = dict(item)
            if label and (not _first(entry=entry, keys=Constants.rule_keys)):
                entry["rule"] = label
            entries.append(entry)
    return entries


def _failed_tests(
    *,
    fields: Mapping[str, JsonValue],
) -> tuple[tuple[str, str], ...]:
    """Extract failed tests and their reasons from a report.

    Args:
        fields: Decoded ``result.json``.

    Returns:
        ``(test, reason)`` pairs from ``failed_tests`` at the top level or
        inside ``test_execution``.

    """
    execution: JsonValue | None = fields.get("test_execution")
    raw: JsonValue | None = fields.get("failed_tests")
    if raw is None and isinstance(execution, dict):
        raw = execution.get("failed_tests")
    if not isinstance(raw, list):
        return ()
    pairs: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            test: str = _text(value=item.get("test"))
            reason: str = _text(value=item.get("detail")).strip()
            pairs.append((test, reason.splitlines()[0] if reason else ""))
    return tuple(pairs)


def _notes(*, fields: Mapping[str, JsonValue]) -> tuple[str, ...]:
    """Build headline facts from tool-specific report sections.

    Args:
        fields: Decoded ``result.json``.

    Returns:
        Short statements such as the measured coverage and any missed gate.

    """
    notes: list[str] = []
    coverage: JsonValue | None = fields.get("coverage")
    if isinstance(coverage, dict):
        totals: JsonValue | None = coverage.get("totals")
        if isinstance(totals, dict):
            percent: str = _text(value=totals.get("percent_covered_display"))
            if percent:
                notes.append(f"Total coverage {percent}%")
    failed: int = len(_failed_tests(fields=fields))
    if failed:
        notes.append(f"{failed} failed test(s)")
    gates: JsonValue | None = fields.get("gates")
    if isinstance(gates, dict):
        total_gate: str = _text(value=gates.get("fail_under"))
        per_file: str = _text(value=gates.get("per_file_minimum"))
        below: JsonValue | None = gates.get("files_below")
        if total_gate:
            notes.append(f"Total gate {total_gate}%")
        if per_file:
            count: int = len(below) if isinstance(below, list) else 0
            notes.append(f"Per-file gate {per_file}%: {count} file(s) below")
    return tuple(notes)


def _distinct(
    *,
    lines: Sequence[Mapping[str, JsonValue]],
    root: str,
) -> tuple[tuple[str, str, int, str], ...]:
    """Group findings that differ only by origin, port, or location.

    Args:
        lines: Finding-like entries.
        root: Project root as reported.

    Returns:
        The most frequent ``(rule, message, count, example)`` groups, most
        frequent first; empty when every finding is already unique.

    """
    counts: Counter[tuple[str, str]] = Counter()
    example: dict[tuple[str, str], str] = {}
    for entry in lines:
        rule: str = (
            _first(entry=entry, keys=Constants.rule_keys) or "unclassified"
        )
        message: str = sub(
            pattern=Constants.origin_pattern,
            repl="<origin>",
            string=(
                _first(entry=entry, keys=Constants.message_keys).splitlines()
                or [""]
            )[0][: Constants.message_limit],
        )
        key: tuple[str, str] = (rule, message)
        counts[key] += 1
        file: str = _relative(path=_text(value=entry.get("file")), root=root)
        example.setdefault(key, file or "-")
    groups: list[tuple[str, str, int, str]] = [
        (rule, message, count, example[rule, message])
        for (rule, message), count in counts.most_common(
            n=Constants.top_distinct,
        )
        if count > 1
    ]
    return tuple(groups)


def digest_report(
    *,
    tool: str,
    fields: Mapping[str, JsonValue],
    status: str,
    resume: str,
) -> ToolDigest:
    """Summarize one tool report.

    Args:
        tool: Tool or pipeline identifier.
        fields: Decoded ``result.json`` of the tool.
        status: Reconciled status of the run.
        resume: The tool's resume line.

    Returns:
        The digest.

    """
    root: str = _text(value=fields.get("project_root"))
    entries: list[Mapping[str, JsonValue]] = _collect(fields=fields)
    rules: Counter[str] = Counter(
        _first(entry=entry, keys=Constants.rule_keys) or "unclassified"
        for entry in entries
    )
    files: Counter[str] = Counter(
        _relative(path=_text(value=entry.get("file")), root=root)
        for entry in entries
        if _text(value=entry.get("file"))
    )
    top: list[FindingLine] = []
    for entry in entries[: Constants.top_findings]:
        file: str = _relative(path=_text(value=entry.get("file")), root=root)
        line: str = _text(value=entry.get("line"))
        message: str = _first(entry=entry, keys=Constants.message_keys)
        top.append(
            FindingLine(
                rule=_first(entry=entry, keys=Constants.rule_keys)
                or "unclassified",
                location=f"{file}:{line}" if file and line else file or "-",
                message=(message.splitlines() or [""])[0][
                    : Constants.message_limit
                ],
            ),
        )
    return ToolDigest(
        tool=tool,
        status=status,
        resume=resume,
        findings=len(entries),
        rules=tuple(rules.most_common(n=Constants.top_rules)),
        files=tuple(files.most_common(n=Constants.top_files)),
        top=tuple(top),
        distinct=_distinct(lines=entries, root=root),
        notes=_notes(fields=fields),
        failed_tests=_failed_tests(fields=fields),
    )


def _escape(*, text: str) -> str:
    """Make text safe inside a Markdown table cell.

    Args:
        text: Raw text.

    Returns:
        The text with pipes escaped.

    """
    return text.replace("|", "\\|")


def render_failure(*, digest: ToolDigest) -> list[str]:
    """Render one failing tool as Markdown.

    Args:
        digest: Digest of a tool that did not pass.

    Returns:
        Markdown lines: facts, dominant rules and files, first findings,
        and failed tests with reasons.

    """
    lines: list[str] = [
        f"### `{digest.tool}` — {digest.status}",
        "",
        f"{digest.resume}".strip() or "No resume reported.",
        "",
    ]
    facts: list[str] = [*digest.notes]
    if digest.findings:
        facts.append(f"{digest.findings} finding(s)")
    if facts:
        lines.extend((*(f"- {fact}" for fact in facts), ""))
    if digest.rules:
        lines.extend(("| Rule | Count |", "| --- | ---: |"))
        lines.extend(
            (
                f"| `{_escape(text=rule)}` | {count} |"
                for rule, count in digest.rules
            ),
        )
        lines.append("")
    if digest.files:
        lines.extend(("| File | Findings |", "| --- | ---: |"))
        lines.extend(
            (
                f"| `{_escape(text=file)}` | {count} |"
                for file, count in digest.files
            ),
        )
        lines.append("")
    if digest.distinct:
        lines.extend(
            (
                "| Distinct problem | Rule | Occurrences | Example |",
                "| --- | --- | ---: | --- |",
            ),
        )
        lines.extend(
            (
                f"| {_escape(text=message)} | `{_escape(text=rule)}` | {count}"
                f" | `{_escape(text=example)}` |"
                for rule, message, count, example in digest.distinct
            ),
        )
        lines.append("")
    if digest.top:
        lines.extend(("| Rule | Location | Message |", "| --- | --- | --- |"))
        lines.extend(
            f"| `{_escape(text=item.rule)}` | `{_escape(text=item.location)}`"
            f" | {_escape(text=item.message)} |"
            for item in digest.top
        )
        lines.append("")
    if digest.failed_tests:
        lines.extend(("| Failed test | Reason |", "| --- | --- |"))
        lines.extend(
            (
                f"| `{_escape(text=test)}` | {_escape(text=reason)} |"
                for test, reason in digest.failed_tests[: Constants.top_tests]
            ),
        )
        hidden: int = len(digest.failed_tests) - Constants.top_tests
        if hidden > 0:
            lines.append(f"| … | {hidden} more failed test(s) |")
        lines.append("")
    return lines


def digest_data(*, digest: ToolDigest) -> dict[str, JsonValue]:
    """Convert a digest to JSON-ready data.

    Args:
        digest: Digest to convert.

    Returns:
        A mapping suitable for a report's ``data`` payload.

    """
    return cast(
        typ="dict[str, JsonValue]",
        val={
            "tool": digest.tool,
            "status": digest.status,
            "resume": digest.resume,
            "findings": digest.findings,
            "rules": [
                {"rule": rule, "count": count} for rule, count in digest.rules
            ],
            "files": [
                {"file": file, "count": count} for file, count in digest.files
            ],
            "top": [
                {
                    "rule": item.rule,
                    "location": item.location,
                    "message": item.message,
                }
                for item in digest.top
            ],
            "distinct": [
                {
                    "rule": rule,
                    "message": message,
                    "count": count,
                    "example": example,
                }
                for rule, message, count, example in digest.distinct
            ],
            "notes": list(digest.notes),
            "failed_tests": [
                {"test": test, "reason": reason}
                for test, reason in digest.failed_tests
            ],
        },
    )
