# Copyright (c) 2026
"""Record exactus core: session summaries and report rendering.

The ``record`` exactus captures real browser interactions, exports them as a
replayable Playwright program and as a Exactus Record workspace, and can
replay either back against the application. This module turns the raw
outcome of such a session into the report data every exactus shares.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from exactus.tools.common.json_types import JsonValue


def _no_facts() -> dict[str, JsonValue]:
    """Return an empty Exactus Record fact mapping.

    Returns:
        A new empty mapping.

    """
    return {}


class RecordRules:
    """Stable identifiers of the findings the record exactus can raise.

    Attributes:
        replay_failure: A replayed action could not be performed.
        empty_recording: A session recorded no replayable action.
        unexportable: Recorded actions Exactus Record cannot address.

    """

    replay_failure: Final[str] = "REC001"
    empty_recording: Final[str] = "REC002"
    unexportable: Final[str] = "REC003"


@dataclass(frozen=True, slots=True)
class RecordFinding:
    """One problem found while recording or replaying.

    Attributes:
        rule: Stable rule identifier.
        severity: ``error`` fails the exactus, ``warning`` does not.
        message: Human-readable description.

    """

    rule: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class RecordResult:
    """Outcome of one record, replay, or Exactus Record session.

    Attributes:
        mode: ``record``, ``replay``, or ``studio``.
        url: Application URL the session targeted.
        actions: Replayable actions the session produced or consumed.
        exported_events: Exactus Record events generated from the actions.
        artifacts: Files written next to the report.
        workspace: Exactus Record workspace file, when one was written.
        failures: Replay failures, one line per action.
        studio: Exactus Record session facts (commands, events sent, Flows
            played) for ``studio`` mode.
        elapsed_seconds: Wall-clock duration of the session.

    """

    mode: str
    url: str
    actions: tuple[Mapping[str, JsonValue], ...] = ()
    exported_events: int = 0
    artifacts: tuple[str, ...] = ()
    workspace: str = ""
    failures: tuple[str, ...] = ()
    studio: Mapping[str, JsonValue] = field(default_factory=_no_facts)
    elapsed_seconds: float = 0.0


def action_counts(
    *,
    actions: Sequence[Mapping[str, JsonValue]],
) -> dict[str, int]:
    """Count recorded actions by type.

    Args:
        actions: Replayable actions.

    Returns:
        Mapping of action type to occurrences, sorted by type.

    """
    counts: dict[str, int] = {}
    for action in actions:
        kind: str = str(object=action.get("type", "unknown"))
        counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def findings(*, result: RecordResult) -> tuple[RecordFinding, ...]:
    """Derive the exactus findings of one session.

    Args:
        result: Session outcome.

    Returns:
        Replay failures as errors, plus warnings for empty recordings and
        for actions Exactus Record cannot address.

    """
    found: list[RecordFinding] = [
        RecordFinding(
            rule=RecordRules.replay_failure,
            severity="error",
            message=failure,
        )
        for failure in result.failures
    ]
    empty: bool = (
        result.exported_events == 0
        if result.mode == "crawl"
        else not result.actions
    )
    if empty and result.mode != "studio":
        found.append(
            RecordFinding(
                rule=RecordRules.empty_recording,
                severity="warning",
                message="the session produced no replayable action",
            ),
        )
    skipped: int = len(result.actions) - result.exported_events
    if result.mode == "record" and result.actions and (skipped > 0):
        found.append(
            RecordFinding(
                rule=RecordRules.unexportable,
                severity="warning",
                message=(
                    f"{skipped} action(s) have no selector-addressable Exactus"
                    " Record equivalent and were not exported"
                ),
            ),
        )
    return tuple(found)


def passed(*, result: RecordResult) -> bool:
    """Report whether a session raised no error finding.

    Args:
        result: Session outcome.

    Returns:
        ``True`` when every finding is a warning.

    """
    return all(item.severity != "error" for item in findings(result=result))


@final
class Constants:
    """Group module-level constants.

    Attributes:
        rule_titles: Grouped module constant.
        id_prefix: Grouped module constant.

    """

    rule_titles: Final[dict[str, str]] = {
        RecordRules.replay_failure: "Replay action failed",
        RecordRules.empty_recording: "Empty recording",
        RecordRules.unexportable: "Actions without Exactus Record equivalent",
    }
    id_prefix: Final[str] = "RECORD"


def _finding(
    *,
    index: int,
    finding: RecordFinding,
    result: RecordResult,
) -> dict[str, JsonValue]:
    """Return one finding in the normalized shape.

    Args:
        index: One-based position in the result.
        finding: Session violation.
        result: Session outcome supplying the location.

    Returns:
        Normalized finding carrying rule, severity and message.

    """
    return {
        "id": f"{Constants.id_prefix}-{index:03d}",
        "title": Constants.rule_titles.get(finding.rule, finding.rule),
        "severity": finding.severity,
        "rule": finding.rule,
        "path": result.workspace or result.url or "session",
        "line": None,
        "message": finding.message,
        "blocking": finding.severity == "error",
    }


def _severities(*, items: Sequence[RecordFinding]) -> dict[str, int]:
    """Count findings by severity.

    Args:
        items: Session findings.

    Returns:
        Severity name to finding count, sorted by name.

    """
    counts: dict[str, int] = {}
    for item in items:
        counts[item.severity] = counts.get(item.severity, 0) + 1
    return dict(sorted(counts.items()))


def report_data(*, result: RecordResult) -> dict[str, JsonValue]:
    """Return the normalized JSON payload of one record session.

    Args:
        result: Session outcome.

    Returns:
        ``summary``, ``scope``, ``findings`` and ``extension`` blocks;
        ``summary`` keeps the session ``mode``, ``url`` and counters.

    """
    items: tuple[RecordFinding, ...] = findings(result=result)
    rules: list[str] = [finding.rule for finding in items]
    skipped: int = len(result.actions) - result.exported_events
    targets: list[str] = [
        target for target in (result.url, result.workspace) if target
    ]
    return cast(
        typ="dict[str, JsonValue]",
        val={
            "summary": {
                "targets_eligible": len(result.actions),
                "targets_analyzed": len(result.actions),
                "findings_total": len(items),
                "severity": _severities(items=items),
                "mode": result.mode,
                "url": result.url,
                "actions": len(result.actions),
                "exported_events": result.exported_events,
                "failures": len(result.failures),
                "findings": len(items),
                "elapsed_seconds": round(
                    number=result.elapsed_seconds,
                    ndigits=3,
                ),
                "workspace": result.workspace,
            },
            "scope": {
                "include": targets,
                "exclude": [],
                "skipped": (
                    [
                        {
                            "target": f"{skipped} action(s)",
                            "reason": (
                                "no selector-addressable Exactus Record"
                                " equivalent"
                            ),
                        },
                    ]
                    if result.mode == "record" and skipped > 0
                    else []
                ),
            },
            "findings": [
                _finding(index=index, finding=finding, result=result)
                for index, finding in enumerate(iterable=items, start=1)
            ],
            "extension": {
                "rules": [
                    {"rule": rule, "title": title, "count": rules.count(rule)}
                    for rule, title in Constants.rule_titles.items()
                ],
                "metrics": {
                    "mode": result.mode,
                    "url": result.url,
                    "actions": len(result.actions),
                    "exported_events": result.exported_events,
                    "failures": len(result.failures),
                    "elapsed_seconds": round(
                        number=result.elapsed_seconds,
                        ndigits=3,
                    ),
                    "workspace": result.workspace,
                    "by_type": [
                        {"type": kind, "count": count}
                        for kind, count in action_counts(
                            actions=result.actions,
                        ).items()
                    ],
                    "produced_files": list(result.artifacts),
                    "studio": [
                        {"fact": name, "value": value}
                        for name, value in result.studio.items()
                    ],
                },
            },
        },
    )
