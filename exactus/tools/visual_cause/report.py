"""Normalize visual-cause results for the shared report bundle."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.visual_cause.core import Finding, VisualCauseResult


def data(
    *,
    result: VisualCauseResult,
    project_root: str,
) -> dict[str, JsonValue]:
    """Return the normalized JSON payload.

    Args:
        result: Completed visual-cause run result.
        project_root: Repository root recorded in the payload.

    Returns:
        JSON-ready document for the report bundle.

    """
    severities: dict[str, str] = {
        "fail": "error",
        "warning": "warning",
        "accept": "info",
    }
    counts: dict[str, int] = {
        level: sum(item.level == level for item in result.findings)
        for level in ("fail", "warning", "accept")
    }
    return {
        "status": "FAIL" if result.failed else "PASS",
        "project_root": project_root,
        "summary": {
            "targets": len(result.targets),
            "findings": len(result.findings),
            "fail": counts["fail"],
            "warning": counts["warning"],
            "accept": counts["accept"],
            "severity": {
                "error": counts["fail"],
                "warning": counts["warning"],
                "info": counts["accept"],
            },
        },
        "findings": [
            {
                **cast(typ="dict[str, JsonValue]", val=asdict(obj=finding)),
                "title": (
                    f"{finding.tag} changed" if finding.tag else "Target error"
                ),
                "severity": severities[finding.level],
                "path": finding.css_path or finding.target,
                "line": None,
                "blocking": finding.level == "fail",
            }
            for finding in result.findings
        ],
        "scope": {
            "include": cast(
                typ="list[JsonValue]",
                val=sorted(
                    {target.name for target in result.targets}
                    | {finding.target for finding in result.findings},
                ),
            ),
            "exclude": [],
            "skipped": [],
        },
        "extension": {
            "targets": [
                {
                    **cast(typ="dict[str, JsonValue]", val=asdict(obj=target)),
                    "a": target.artifacts.get("a", ""),
                    "b": target.artifacts.get("b", ""),
                    "diff": target.artifacts.get("diff", ""),
                    "engine_report": target.artifacts.get("engine_report", ""),
                    "engine_markdown": target.artifacts.get(
                        "engine_markdown",
                        "",
                    ),
                }
                for target in result.targets
            ],
            "queries": list(result.queries),
        },
    }


def markdown(*, result: VisualCauseResult) -> str:
    """Render one concise report with target and finding detail.

    Args:
        result: Completed visual-cause run result.

    Returns:
        Markdown text ending in a newline.

    """
    lines: list[str] = [
        "# Visual Cause Exactus",
        "",
        f"Verdict: **{'FAIL' if result.failed else 'PASS'}**",
        "",
        "## Targets",
        "",
        "| Target | Viewport | Mode | Pixels | Findings | Fail | Warning |"
        " Accept |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        "| "
        + " | ".join(
            (
                target.name,
                target.viewport,
                target.mode,
                f"{target.changed_pixels:,}",
                str(object=target.changed_element_count),
                str(object=target.counts.get("fail", 0)),
                str(object=target.counts.get("warning", 0)),
                str(object=target.counts.get("accept", 0)),
            ),
        )
        + " |"
        for target in result.targets
    )
    if not result.targets:
        lines.append("| No completed targets | — | — | — | — | — | — | — |")
    for level in ("fail", "warning", "accept"):
        lines.extend(["", f"## {level.title()} findings", ""])
        selected: tuple[Finding, ...] = tuple(
            item for item in result.findings if item.level == level
        )
        if not selected:
            lines.append("None.")
            continue
        for finding in selected:
            lines.extend(
                [
                    f"### `{finding.id}`",
                    "",
                    f"- Rule: `{finding.rule}`",
                    "- Query: `"
                    f"{finding.query or finding.css_path or 'target'}`",
                    f"- Decision: `{finding.decided_by or 'default'}`",
                    f"- Changed pixels: {finding.changed_pixels:,}",
                    f"- Message: {finding.message}",
                    "",
                ],
            )
    lines.extend(["## Evidence", ""])
    for target in result.targets:
        artifacts: dict[str, str] = target.artifacts
        if all(name in artifacts for name in ("a", "b", "diff")):
            lines.extend(
                [
                    f"### {target.name} · {target.viewport}",
                    "",
                    "| A | B | Difference |",
                    "|---|---|---|",
                    f"| ![]({artifacts['a']}) | ![]({artifacts['b']}) |"
                    f" ![]({artifacts['diff']}) |",
                    "",
                ],
            )
    return "\n".join(lines).rstrip() + "\n"
