# Copyright (c) 2026
"""Compare normalized exactus findings with the preceding report bundle."""

from __future__ import annotations

from atexit import register
from collections import Counter
from hashlib import sha256
from json import JSONDecodeError, dumps, loads
from os import environ
from pathlib import Path
from re import sub
from tempfile import TemporaryDirectory
from threading import RLock
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from exactus.tools.common.json_types import JsonObject, JsonValue
_previous: Final[dict[Path, dict[str, JsonValue]]] = {}
_previous_duration: Final[dict[Path, float]] = {}
_lock: Final[RLock] = RLock()
_owned: Final[list[TemporaryDirectory[str]]] = []
_BASELINE_ENV: Final[str] = "EXACTUS_COMPARISON_BASELINE"
_FACETS: Final[tuple[str, ...]] = (
    "source",
    "category",
    "section",
    "language",
    "rule",
)


def _duration_from(
    *,
    document: Mapping[str, JsonValue] | None,
) -> float | None:
    """Return the recorded wall-clock duration of a previous report.

    Args:
        document: Previous report document, when available.

    Returns:
        The previous run duration in seconds, or ``None`` when no duration
        was recorded.

    """
    if document is None:
        return None
    value: JsonValue = document.get(
        "duration_seconds",
        document.get("elapsed_seconds"),
    )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    run: JsonValue = document.get("run")
    if isinstance(run, dict):
        value = run.get("duration_seconds")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _store_duration(
    *,
    path: Path,
    document: Mapping[str, JsonValue] | None,
) -> None:
    """Remember the duration recorded for one captured report path.

    Args:
        path: Canonical report path.
        document: Previous report document, when available.

    """
    duration: float | None = _duration_from(document=document)
    if duration is not None:
        _previous_duration[path.resolve()] = duration


def _snapshot_path(*, path: Path) -> Path | None:
    """Locate an inherited run baseline for a canonical report path.

    Args:
        path: Canonical report path.

    Returns:
        Snapshot path when a baseline directory has been established.

    """
    directory: str | None = environ.get(_BASELINE_ENV)
    if not directory:
        return None
    key: str = sha256(data=str(object=path.resolve()).encode()).hexdigest()
    return Path(directory) / f"{key}.json"


def _read(*, path: Path) -> dict[str, JsonValue] | None:
    """Read one JSON object report.

    Args:
        path: Candidate ``result.json`` file.

    Returns:
        Decoded object, or ``None`` when unavailable or malformed.

    """
    try:
        value: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=path.read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _capture_documents(*, output: Path) -> dict[Path, dict[str, JsonValue]]:
    """Collect existing report documents before the tree is replaced.

    Args:
        output: Tool report directory or ``result.json`` about to be
            regenerated.

    Returns:
        Report documents keyed by their canonical paths.

    """
    captured: dict[Path, dict[str, JsonValue]] = {}
    if output.is_dir():
        for path in output.glob(pattern="**/*.json"):
            if any(
                part == "ARTIFACTS"
                or part.endswith("_web")
                or part.startswith(".")
                for part in path.relative_to(output).parts[:-1]
            ):
                continue
            if (document := _read(path=path)) is not None and (
                path.name == "result.json" or "report_bundle" in document
            ):
                captured[path.resolve()] = document
    elif (
        output.name == "result.json"
        and (document := _read(path=output)) is not None
    ):
        captured[output.resolve()] = document
    return captured


def _activity_duration(*, output: Path) -> float | None:
    """Return elapsed seconds from the preceding activity document.

    Args:
        output: Tool report directory.

    Returns:
        Recorded elapsed seconds, when available.

    """
    return _duration_from(
        document=_read(path=output / "ARTIFACTS" / "@activity.json"),
    )


def capture(*, output: Path) -> None:
    """Capture report documents before an output tree is replaced.

    Args:
        output: Tool report directory about to be regenerated.

    """
    captured: dict[Path, dict[str, JsonValue]] = _capture_documents(
        output=output,
    )
    activity_duration: float | None = _activity_duration(output=output)
    with _lock:
        _previous.update(captured)
        for path, document in captured.items():
            _store_duration(path=path, document=document)
        result_path: Path = (output / "result.json").resolve()
        if (
            activity_duration is not None
            and result_path not in _previous_duration
        ):
            _previous_duration[result_path] = activity_duration
        if captured and not environ.get(_BASELINE_ENV):
            directory: TemporaryDirectory[str] = TemporaryDirectory(
                prefix="exactus-report-baseline-",
            )
            _owned.append(directory)
            _ = register(directory.cleanup)
            environ[_BASELINE_ENV] = directory.name
        for path, document in captured.items():
            snapshot: Path | None = _snapshot_path(path=path)
            if snapshot is not None:
                _ = snapshot.write_text(
                    data=dumps(obj=document),
                    encoding="utf-8",
                )


def clear() -> None:
    """Discard reports captured for the current execution."""
    with _lock:
        _previous.clear()
        _previous_duration.clear()
        _ = environ.pop(_BASELINE_ENV, None)
        for directory in _owned:
            directory.cleanup()
        _owned.clear()


def previous_duration(*, path: Path) -> float | None:
    """Return the duration of the report that preceded ``path``.

    The value is captured at the start of a run, before the output tree
    is replaced, and remains available until :func:`clear` is called.
    When this process captured nothing — for example an orchestrated
    worker that inherited only the shared baseline — the snapshot
    directory pointed to by ``EXACTUS_COMPARISON_BASELINE`` is consulted
    as a fallback.

    Args:
        path: Canonical ``result.json`` path of the current run.

    Returns:
        The previous run duration in seconds, or ``None`` when no
        previous report exists or it recorded no duration.

    """
    resolved: Path = path.resolve()
    with _lock:
        duration: float | None = _previous_duration.get(resolved)
    if duration is not None:
        return duration
    snapshot: Path | None = _snapshot_path(path=path)
    duration = _duration_from(
        document=_read(path=snapshot) if snapshot is not None else None,
    )
    if duration is not None:
        with _lock:
            _previous_duration[resolved] = duration
    return duration


def _findings(
    *,
    document: Mapping[str, JsonValue],
) -> list[dict[str, JsonValue]]:
    """Return normalized finding objects from a report.

    Args:
        document: Decoded report document.

    Returns:
        Finding objects in report order.

    """
    raw: JsonValue = document.get("findings")
    snapshots: JsonValue | None = document.get("report_snapshots")
    if isinstance(snapshots, dict):
        return [
            {**finding, "tool": tool}
            for tool, snapshot in snapshots.items()
            if isinstance(snapshot, dict)
            for finding in _findings(document=snapshot)
        ]
    return (
        [dict(item) for item in raw if isinstance(item, dict)]
        if isinstance(raw, list)
        else []
    )


def _identity(*, finding: Mapping[str, JsonValue]) -> str:
    """Build a stable semantic identity for one finding.

    Args:
        finding: Normalized finding object.

    Returns:
        Short content hash excluding run-local numbering and source lines.

    """
    fields: tuple[str, ...] = (
        "rule",
        "code",
        "category",
        "path",
        "file",
        "title",
        "message",
        "reason",
        "test",
        "node",
        "callee",
        "argument",
        "tool",
        "source",
    )
    if finding.get("rule") in {
        "coverage-total",
        "coverage-per-file",
        "coverage-average",
        "coverage-javascript-total",
    }:
        fields = ("rule", "path", "file", "tool", "source")
    semantic: dict[str, JsonValue] = {
        key: finding[key]
        for key in fields
        if key in finding and finding[key] not in (None, "")
    }
    for key in ("message", "reason"):
        value: JsonValue = semantic.get(key)
        if isinstance(value, str):
            value = sub(
                pattern=r"(?<=://)(localhost|127\.0\.0\.1|\[::1\]):\d+",
                repl=r"\1:<port>",
                string=value,
            )
            semantic[key] = sub(
                pattern=(
                    r"(?<= - - )\[\d{2}/[A-Za-z]{3}/\d{4} "
                    r"\d{2}:\d{2}:\d{2}\]"
                ),
                repl="[<time>]",
                string=value,
            )
    encoded: str = dumps(obj=semantic, sort_keys=True, separators=(",", ":"))
    return sha256(data=encoded.encode()).hexdigest()[:16]


def _run_value(*, document: Mapping[str, JsonValue], key: str) -> JsonValue:
    """Read one run field from normalized or legacy report metadata.

    Args:
        document: Report document.
        key: Run field name.

    Returns:
        Stored value or ``None``.

    """
    run: JsonValue = document.get("run")
    if isinstance(run, dict) and key in run:
        return run[key]
    return document.get("run_id" if key == "id" else key)


def _changes(
    *,
    current: list[dict[str, JsonValue]],
    previous: list[dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    """Compare finding occurrences without collapsing repeated findings.

    Args:
        current: Current findings.
        previous: Previous findings.

    Returns:
        Counts and lists of added, resolved and unchanged occurrences.

    """
    remaining: Counter[str] = Counter(
        _identity(finding=item) for item in previous
    )
    added: list[JsonValue] = []
    for finding in current:
        key: str = _identity(finding=finding)
        if remaining[key]:
            remaining[key] -= 1
        else:
            added.append(dict(finding))
    resolved: list[JsonValue] = []
    for finding in previous:
        key = _identity(finding=finding)
        if remaining[key]:
            resolved.append(dict(finding))
            remaining[key] -= 1
    return {
        "current_total": len(current),
        "previous_total": len(previous),
        "delta": len(current) - len(previous),
        "added_count": len(added),
        "resolved_count": len(resolved),
        "unchanged_count": len(current) - len(added),
        "added": added,
        "resolved": resolved,
    }


def _groups(
    *,
    document: Mapping[str, JsonValue],
) -> dict[str, list[dict[str, JsonValue]]]:
    """Group findings by tool and subsection, including empty sections.

    Args:
        document: Report or aggregate snapshot.

    Returns:
        Section names mapped to finding occurrences.

    """
    groups: dict[str, list[dict[str, JsonValue]]] = {}
    snapshots: JsonValue | None = document.get("report_snapshots")
    if isinstance(snapshots, dict):
        for tool, snapshot in snapshots.items():
            if isinstance(snapshot, dict):
                groups[f"Tool: {tool}"] = _findings(document=snapshot)
                groups.update(
                    {
                        f"{tool} / {name}": rows
                        for name, rows in _groups(document=snapshot).items()
                    },
                )
        return groups
    for finding in _findings(document=document):
        for facet in _FACETS:
            value: JsonValue | None = finding.get(facet)
            if isinstance(value, str) and value:
                groups.setdefault(f"{facet.title()}: {value}", []).append(
                    finding,
                )
    return groups


def _category_rows(
    *,
    document: Mapping[str, JsonValue],
) -> dict[str, dict[str, JsonValue]]:
    """Read named tool categories, retaining categories with zero findings.

    Args:
        document: Normalized report.

    Returns:
        Named rule, category or linter counts.

    """
    extension: JsonValue = document.get("extension")
    if not isinstance(extension, dict):
        extension = {}
    metrics: JsonValue = extension.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    inventory: JsonValue = (
        extension.get("rules")
        or extension.get("categories")
        or metrics.get("linters")
        or metrics.get("categories")
    )
    result: dict[str, dict[str, JsonValue]] = {}
    if isinstance(inventory, list):
        for row in inventory:
            if isinstance(row, dict):
                name: str = str(
                    object=row.get("rule")
                    or row.get("category")
                    or row.get("linter"),
                )
                result[name] = {
                    "title": row.get("title") or row.get("label") or name,
                    "count": row.get("count", row.get("findings", 0)),
                }
    else:
        result = _finding_categories(document=document)
    snapshots: JsonValue = document.get("report_snapshots")
    if isinstance(snapshots, dict):
        result = {}
        for tool, snapshot in snapshots.items():
            if isinstance(snapshot, dict):
                result.update(
                    {
                        f"{tool} / {name}": row
                        for name, row in _category_rows(
                            document=snapshot,
                        ).items()
                    },
                )
    return result


def _finding_categories(
    *,
    document: Mapping[str, JsonValue],
) -> dict[str, dict[str, JsonValue]]:
    """Count finding rules when a tool has no published category inventory.

    Args:
        document: Normalized report.

    Returns:
        Recorded rule counters.

    """
    counts: Counter[str] = Counter(
        str(object=finding.get("rule") or finding.get("source") or "Findings")
        for finding in _findings(document=document)
    )
    summary: JsonValue = document.get("summary")
    by_rule: JsonValue = (
        summary.get("by_rule") if isinstance(summary, dict) else None
    )
    if isinstance(by_rule, dict):
        counts.update(
            {
                name: count
                for name, count in by_rule.items()
                if isinstance(count, int) and name not in counts
            },
        )
    return {
        name: {"title": name, "count": count} for name, count in counts.items()
    }


def _category_changes(
    *,
    current: Mapping[str, JsonValue],
    previous: Mapping[str, JsonValue] | None,
) -> list[JsonValue]:
    """Compare each tool category with its recorded predecessor.

    Args:
        current: Current report.
        previous: Previous report, or no baseline.

    Returns:
        One row per category with current, previous and net finding counts.

    """
    now: dict[str, dict[str, JsonValue]] = _category_rows(document=current)
    before: dict[str, dict[str, JsonValue]] = _category_rows(
        document=previous or {},
    )
    rows: list[JsonValue] = []
    for name in sorted(now.keys() | before.keys()):
        current_row: dict[str, JsonValue] = now.get(name, {})
        previous_row: dict[str, JsonValue] = before.get(name, {})
        count: JsonValue = current_row.get("count", 0)
        old: JsonValue = (
            previous_row.get("count", 0) if previous is not None else None
        )
        rows.append(
            {
                "category": name,
                "title": current_row.get("title")
                or previous_row.get("title")
                or name,
                "current": count,
                "previous": old,
                "delta": count - old
                if isinstance(count, int) and isinstance(old, int)
                else None,
            },
        )
    return rows


def _section_changes(
    *,
    current: Mapping[str, JsonValue],
    previous: Mapping[str, JsonValue] | None,
) -> dict[str, JsonValue]:
    """Build finding and metric deltas for every report subsection.

    Args:
        current: Current report.
        previous: Baseline report, when available.

    Returns:
        Section and metric comparison tables.


    """
    current_groups: dict[str, list[dict[str, JsonValue]]] = _groups(
        document=current,
    )
    previous_groups: dict[str, list[dict[str, JsonValue]]] = _groups(
        document=previous or {},
    )
    sections: list[JsonValue] = [
        {
            "section": name,
            **_changes(
                current=current_groups.get(name, []),
                previous=previous_groups.get(name, []),
            ),
        }
        for name in sorted(current_groups.keys() | previous_groups.keys())
    ]
    historical: dict[str, int] = _historical_counts(document=previous or {})
    if historical:
        for row in sections:
            if isinstance(row, dict):
                name: str = str(object=row.get("section", ""))
                before_count: JsonValue | None = (
                    historical.get(name.removeprefix("Tool: "))
                    if name.startswith("Tool: ")
                    else None
                )
                now_count: JsonValue | None = row.get("current_total")
                row.update(
                    previous_total=before_count,
                    delta=now_count - before_count
                    if isinstance(now_count, int | float)
                    and isinstance(before_count, int | float)
                    else None,
                    added_count=None,
                    resolved_count=None,
                    unchanged_count=None,
                )
    if previous is None:
        for row in sections:
            if isinstance(row, dict):
                row.update(
                    previous_total=None,
                    delta=None,
                    added_count=0,
                    resolved_count=0,
                    unchanged_count=0,
                )
    return {
        "subsections": sections,
        "categories": _category_changes(current=current, previous=previous),
    }


def _historical_counts(*, document: Mapping[str, JsonValue]) -> dict[str, int]:
    """Read aggregate counts when detailed baseline snapshots are absent.

    Args:
        document: Previous aggregate report.

    Returns:
        Recorded finding counts by tool, without inferring missing details.

    """
    if isinstance(document.get("report_snapshots"), dict):
        return {}
    digests: JsonValue | None = document.get("digests")
    if not isinstance(digests, list):
        return {}
    counts: dict[str, int] = {}
    for item in digests:
        if not isinstance(item, dict):
            continue
        tool: JsonValue | None = item.get("tool")
        count: JsonValue | None = item.get("findings")
        if (
            isinstance(tool, str)
            and isinstance(count, int)
            and not isinstance(count, bool)
        ):
            counts[tool] = count
    return counts


def _finding_changes(
    *,
    current: Mapping[str, JsonValue],
    previous: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    """Compare recorded totals without inventing absent finding history.

    Args:
        current: Current report.
        previous: Previous report.


    Returns:
        Finding delta and availability of individual finding comparisons.


    """
    changes: dict[str, JsonValue] = _changes(
        current=_findings(document=current),
        previous=_findings(document=previous),
    )
    historical: dict[str, int] = _historical_counts(document=previous)
    changes["finding_details_available"] = not bool(historical)
    if historical:
        before: int = sum(historical.values())
        changes.update(
            previous_total=before,
            delta=len(_findings(document=current)) - before,
            added_count=None,
            resolved_count=None,
            unchanged_count=None,
            added=[],
            resolved=[],
        )
    return changes


def markdown(*, comparison: JsonValue) -> str:
    """Render global and subsection deltas for any Markdown report.

    Args:
        comparison: Comparison block attached to the report.

    Returns:
        Common comparison section, including the first-run explanation.

    """
    if not isinstance(comparison, dict):
        return ""
    lines: list[str] = ["## Change since previous report", ""]
    if comparison.get("available") is not True:
        return "\n".join(
            [
                *lines,
                "No previous report exists; "
                "this run establishes the baseline.",
                "",
            ],
        )
    previous_duration: JsonValue = comparison.get("previous_duration_seconds")
    if isinstance(previous_duration, (int, float)) and not isinstance(
        previous_duration,
        bool,
    ):
        lines.append(
            f"Previous run completed in **{previous_duration:.3f}s**.",
        )
        lines.append("")
    lines.extend(
        [
            "| Findings | Current | Previous | Delta | "
            "Added | Resolved | Unchanged |",
            "|---|---:|---:|---:|---:|---:|---:|",
            "| Overall | "
            + " | ".join(
                str(object=comparison.get(key))
                if comparison.get(key) is not None
                else "N/A"
                for key in (
                    "current_total",
                    "previous_total",
                    "delta",
                    "added_count",
                    "resolved_count",
                    "unchanged_count",
                )
            )
            + " |",
            "",
        ],
    )
    for key, label, columns in (
        (
            "categories",
            "Category findings",
            ("category", "title", "current", "previous", "delta"),
        ),
    ):
        rows: JsonValue | None = comparison.get(key)
        if not isinstance(rows, list) or not rows:
            continue
        lines.extend(
            [
                f"### {label}",
                "",
                "| "
                + " | ".join(
                    column.replace("_", " ").title() for column in columns
                )
                + " |",
                "| " + " | ".join("---" for _ in columns) + " |",
            ],
        )
        for row in rows:
            if isinstance(row, dict):
                cells: list[str] = [
                    str(object=row.get(column))
                    if row.get(column) is not None
                    else "N/A"
                    for column in columns
                ]
                lines.append(
                    "| "
                    + " | ".join(
                        cell.replace("|", r"\|").replace("\n", " ")
                        for cell in cells
                    )
                    + " |",
                )
        lines.append("")
    return "\n".join(lines)


def apply(*, payload: JsonObject, path: Path) -> None:
    """Attach finding-level comparison data to a current report payload.

    Args:
        payload: Current report payload, mutated in place.
        path: Current canonical ``result.json`` path.

    """
    with _lock:
        previous: dict[str, JsonValue] | None = _previous.get(path.resolve())
    if previous is None and path.is_file():
        previous = _read(path=path)
    if (
        previous is None
        and (snapshot := _snapshot_path(path=path)) is not None
    ):
        previous = _read(path=snapshot)
    previous_duration_seconds: float | None = _duration_from(document=previous)
    if previous_duration_seconds is not None:
        _previous_duration[path.resolve()] = previous_duration_seconds
    current_findings: list[dict[str, JsonValue]] = _findings(document=payload)
    if previous is None:
        payload["comparison"] = {
            "available": False,
            "current_total": len(current_findings),
            "previous_total": None,
            "previous_duration_seconds": None,
            "delta": None,
            "added_count": 0,
            "resolved_count": 0,
            "unchanged_count": 0,
            "added": [],
            "resolved": [],
            **_section_changes(current=payload, previous=None),
        }
        return
    previous_findings: list[dict[str, JsonValue]] = _findings(
        document=previous,
    )
    changes: dict[str, JsonValue] = _finding_changes(
        current=payload,
        previous=previous,
    )
    unchanged: Counter[str] = Counter(
        _identity(finding=item) for item in previous_findings
    )
    annotated: list[JsonValue] = []
    for finding in current_findings:
        item: dict[str, JsonValue] = dict(finding)
        key: str = _identity(finding=item)
        item["change"] = "unchanged" if unchanged[key] else "added"
        if unchanged[key]:
            unchanged[key] -= 1
        item["comparison_key"] = key
        if not changes["finding_details_available"]:
            _ = item.pop("change", None)
        annotated.append(item)
    payload["findings"] = annotated
    payload["comparison"] = {
        "available": True,
        "previous_generated_at": previous.get("generated_at"),
        "previous_run_id": _run_value(document=previous, key="id"),
        "previous_status": _run_value(document=previous, key="status"),
        "previous_duration_seconds": previous_duration_seconds,
        **changes,
        **_section_changes(current=payload, previous=previous),
    }
