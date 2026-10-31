# Copyright (c) 2026
"""Normalize frontend execution evidence for Markdown and web reports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from exactus.tools.common.json_types import JsonValue


def objects(*, value: JsonValue) -> list[dict[str, JsonValue]]:
    """Read object rows without interpreting missing evidence as success.

    Args:
        value: A report list.

    Returns:
        Object rows in their recorded order.

    """
    return (
        [row for row in value if isinstance(row, dict)]
        if isinstance(value, list)
        else []
    )


def artifact_path(*, value: JsonValue, output: Path) -> str:
    """Resolve evidence after the runner moves auxiliary files to ARTIFACTS.

    Args:
        value: Recorded artifact path.
        output: Report directory.

    Returns:
        Report-relative path when the artifact belongs to this report.

    """
    path: Path = Path(str(object=value))
    if path.is_absolute():
        try:
            path = path.relative_to(output.resolve())
        except ValueError:
            return path.as_posix()
    if not (output / path).exists() and (output / "ARTIFACTS" / path).exists():
        path = Path("ARTIFACTS") / path
    return path.as_posix()


def normalized_data(
    *,
    payload: Mapping[str, JsonValue],
    output: Path,
) -> dict[str, JsonValue]:
    """Add summary, findings, scope and execution tables to raw evidence.

    Args:
        payload: Workspace or Actions execution report.
        output: Directory containing the report.

    Returns:
        Normalized blocks retaining every action, response and diagnostic.

    """
    flows: list[dict[str, JsonValue]] = objects(value=payload.get("flows"))
    actions: list[dict[str, JsonValue]] = objects(value=payload.get("actions"))
    findings: list[JsonValue] = []
    for index, row in enumerate(
        iterable=objects(value=payload.get("findings")),
        start=1,
    ):
        location: str = str(
            object=row.get("path") or row.get("file") or "execution",
        )
        category: str = str(object=row.get("category") or "")
        message: str = str(object=row.get("message") or "")
        prefix, separator, detail = message.partition(": ")
        if prefix in {"http", "console", "pageerror"}:
            category = category or prefix
            message = detail if separator else message
        if location == "server":
            category = "server"
        category = category or "workflow"
        group: str = str(
            object=row.get("flow")
            or (
                "Server"
                if category == "server"
                else location.partition(": ")[0]
            ),
        )
        stage: str = str(
            object=row.get("action")
            or row.get("phase")
            or (location.partition(": ")[2] or "Execution"),
        )
        titles: dict[str, str] = {
            "http": "HTTP request failed",
            "console": "Browser console error",
            "pageerror": "JavaScript exception",
            "server": "Server error",
            "workflow": "Workflow failed",
        }
        findings.append(
            {
                **row,
                "id": row.get("id") or f"FRONTEND-{index:03d}",
                "title": titles.get(category, "Browser error"),
                "category": category,
                "severity": row.get("severity", "error"),
                "group": group,
                "stage": stage,
                "message": message,
                "path": location,
                "line": row.get("line"),
                "blocking": row.get("severity", "error") == "error",
            },
        )
    steps: list[dict[str, JsonValue]] = [
        record
        for flow in flows
        for record in objects(value=flow.get("action_records"))
    ]
    outcomes: Counter[str] = Counter(
        str(object=flow.get("status", "unknown")) for flow in flows
    )
    step_outcomes: Counter[str] = Counter(
        str(object=record.get("status", "unknown")) for record in steps
    )
    diagnostics: list[JsonValue] = []
    workflow_rows: list[JsonValue] = []
    for flow in flows:
        environment: JsonValue = flow.get("environment")
        environment = (
            environment
            if isinstance(environment, dict)
            else payload.get("viewport", {})
        )
        environment = environment if isinstance(environment, dict) else {}
        records: list[dict[str, JsonValue]] = objects(
            value=flow.get("action_records"),
        )
        workflow_rows.append(
            {
                **flow,
                "name": environment.get("name") or flow.get("flow_id"),
                "width": environment.get("width"),
                "height": environment.get("height"),
                "theme": environment.get("theme")
                or payload.get("color_scheme"),
                "steps": len(records),
                "failed_steps": sum(
                    record.get("status") == "failed" for record in records
                ),
            },
        )
        for value in (
            flow.get("diagnostics"),
            environment.get("discovery_diagnostics"),
        ):
            diagnostics.extend(
                {**event, "flow": flow.get("flow_id")}
                for event in objects(value=value)
            )
    screenshots: list[JsonValue] = [
        {
            **event,
            "path": artifact_path(value=event.get("path"), output=output),
        }
        for event in objects(value=payload.get("evidence"))
        if event.get("type") == "screenshot" and event.get("path")
    ]
    severity: Counter[str] = Counter(
        str(object=row.get("severity", "error"))
        for row in objects(value=findings)
    )
    status: str = str(object=payload.get("status", "ERROR"))
    reason: str = (
        f"{len(findings)} browser, server or workflow findings; "
        f"{outcomes['failed']} failed workflows."
    )
    return {
        "title": "Frontend execution",
        "summary": {
            "targets_eligible": len(flows),
            "targets_analyzed": len(flows),
            "findings_total": len(findings),
            "severity": dict(severity),
            "workflows": len(flows),
            "workflow_outcomes": dict(outcomes),
            "steps": len(steps),
            "step_outcomes": dict(step_outcomes),
            "screenshots": len(screenshots),
            "recipe_actions": len(actions),
        },
        "scope": {
            "include": [
                payload.get("workspace")
                or payload.get("url")
                or "Configured Actions recipe",
            ],
            "exclude": [],
            "skipped": [],
        },
        "findings": findings,
        "gate": {"status": status, "reason": reason},
        "resume": f"{status}: {reason}",
        "extension": {
            "actions": [
                {
                    "id": row.get("id"),
                    "tool": row.get("tool"),
                    "status": row.get("status"),
                    "error": row.get("error"),
                }
                for row in actions
            ],
            "workflows": workflow_rows,
            "screenshots": screenshots,
            "browser_diagnostics": diagnostics,
            "server_diagnostics": payload.get("server_diagnostics", []),
        },
    }
