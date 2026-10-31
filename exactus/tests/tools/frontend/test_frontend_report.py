# Copyright (c) 2026
"""Frontend reports retain execution outcomes and readable evidence."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from exactus.tests.common.support import expect_equal, expect_in, expect_not_in
from exactus.tools.frontend.report import artifact_path, normalized_data
from exactus.tools.reports.render import ReportTemplates

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


def test_frontend_report_explains_diagnostics_and_steps(
    tmp_path: Path,
) -> None:
    """Preserve a failed step beside a successful workflow and its response.

    Args:
        tmp_path: Isolated output directory.

    """
    payload: dict[str, JsonValue] = {
        "status": "FAIL",
        "actions": [
            {"id": "verify", "tool": "frontend.run", "status": "failed"},
        ],
        "flows": [
            {
                "flow_id": "passing",
                "run_id": "r1",
                "status": "succeeded",
                "environment": {"width": 390, "height": 844, "theme": "dark"},
                "action_records": [
                    {
                        "event_id": "answer",
                        "kind": "javascript",
                        "label": "Read answer",
                        "status": "succeeded",
                        "script": "() => ({answer: 42})",
                        "response": {"answer": 42},
                        "assertions": [
                            {"status": "passed", "message": "Answer matches"},
                        ],
                        "screenshot_artifact_ids": ["shot"],
                    },
                ],
            },
            {
                "flow_id": "failing",
                "run_id": "r2",
                "status": "failed",
                "error": "Control was missing",
                "action_records": [
                    {
                        "event_id": "click",
                        "label": "Click missing control",
                        "kind": "click",
                        "status": "failed",
                        "error": "No matching button",
                        "response": None,
                    },
                ],
                "diagnostics": [
                    {
                        "severity": "error",
                        "category": "console",
                        "message": "Unable to save\nResponse was malformed",
                        "file": "https://example.test/app.js",
                        "line": 9,
                        "column": 17,
                        "function": "saveSettings",
                        "stack": (
                            "at saveSettings (https://example.test"
                            "/app.js:9:17)"
                        ),
                    },
                    {
                        "severity": "error",
                        "category": "http",
                        "message": "HTTP 500",
                        "url": "https://example.test/error",
                        "status": 500,
                    },
                ],
            },
        ],
        "findings": [
            {
                "rule": "FLOW001",
                "file": "failing",
                "severity": "error",
                "message": "No matching button",
            },
        ],
        "evidence": [
            {
                "type": "screenshot",
                "artifact_id": "shot",
                "path": "screenshots/shot.png",
                "width": 390,
                "height": 844,
                "flow_id": "passing",
                "event_id": "answer",
            },
        ],
        "server_diagnostics": [
            {"severity": "error", "line": "GET /error HTTP 500"},
            {
                "severity": "error",
                "stream": "stderr",
                "line": (
                    dedent(
                        text=(
                            "    Traceback (most recent call last):\n    R"
                            "untimeError: save failed"
                        ),
                    )
                ),
            },
        ],
    }
    model: dict[str, JsonValue] = {
        **payload,
        **normalized_data(payload=payload, output=tmp_path),
        "tool": {"name": "frontend", "display_name": "Frontend execution"},
        "run": {"status": "FAIL"},
        "invocation": {"command": "check --frontend", "arguments": []},
        "environment": {"variables": []},
    }
    rendered: str = ReportTemplates.render(
        model=model,
        tool_dir=ReportTemplates.tool_dir(analyzer="frontend"),
    ).markdown
    for text in (
        "2 workflows, 2 steps, 1 findings",
        "390",
        "dark",
        "HTTP 500",
        "No matching button",
        '"answer": 42',
        "Answer matches",
        "screenshots/shot.png",
        "GET /error HTTP 500",
        "Actions recipe",
        "Browser and discovery diagnostics",
        "Source: `https://example.test/app.js`:9:17",
        "Function: `saveSettings`",
        "```text\nUnable to save\nResponse was malformed\n```",
        "```text\nGET /error HTTP 500\n```",
        dedent(
            text=(
                "    ```text\n    Traceback (most recent call last):\n    "
                "RuntimeError: save failed\n    ```"
            ),
        ),
    ):
        expect_in(member=text, container=rendered)
    expect_not_in(
        member="N/A — the tool reported no summary",
        container=rendered,
    )


def test_artifact_paths_follow_organized_output(tmp_path: Path) -> None:
    """Link relocated screenshots while leaving external evidence paths alone.

    Args:
        tmp_path: Isolated output directory.

    """
    screenshot: Path = tmp_path / "ARTIFACTS" / "verify" / "shot.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(data=b"image")
    expect_equal(
        actual=artifact_path(
            value=str(object=tmp_path / "verify" / "shot.png"),
            output=tmp_path,
        ),
        expected="ARTIFACTS/verify/shot.png",
    )
    expect_equal(
        actual=artifact_path(value="/external/shot.png", output=tmp_path),
        expected="/external/shot.png",
    )


def test_empty_frontend_execution_does_not_claim_success(
    tmp_path: Path,
) -> None:
    """An execution with no evidence keeps an explicit unknown status.

    Args:
        tmp_path: Isolated output directory.

    """
    model: dict[str, JsonValue] = normalized_data(payload={}, output=tmp_path)
    expect_equal(
        actual=model["gate"],
        expected={
            "status": "ERROR",
            "reason": (
                "0 browser, server or workflow findings; 0 failed workflows."
            ),
        },
    )


def test_findings_group_browser_failures_by_flow(tmp_path: Path) -> None:
    """Keep related browser failures together and server logs readable.

    Args:
        tmp_path: Isolated report directory.

    """
    payload: dict[str, JsonValue] = {
        "status": "FAIL",
        "findings": [
            {
                "rule": "FRONTEND001",
                "file": "1-390x844-light: discovery",
                "message": "http: HTTP 500 Internal Server Error",
            },
            {
                "rule": "FRONTEND001",
                "file": "1-390x844-light: discovery",
                "message": "console: Failed to load resource",
            },
            {
                "rule": "FRONTEND001",
                "file": "server",
                "message": "GET /api/error HTTP/1.1 500",
            },
        ],
    }
    model: dict[str, JsonValue] = {
        **normalized_data(payload=payload, output=tmp_path),
        "tool": {"name": "frontend", "display_name": "Frontend"},
        "run": {"status": "FAIL"},
        "invocation": {"command": "exactus --frontend", "arguments": []},
        "environment": {"variables": []},
    }
    rendered: str = ReportTemplates.render(
        model=model,
        tool_dir=ReportTemplates.tool_dir(analyzer="frontend"),
    ).markdown
    section: str = rendered.split(sep="## Findings\n", maxsplit=1)[1].split(
        sep="## Artifacts",
        maxsplit=1,
    )[0]
    expect_equal(actual=section.count("### Flow: 1-390x844-light"), expected=1)
    for text in (
        "#### Discovery",
        "### Server",
        "**HTTP request failed**",
        "**Browser console error**",
        "```text\nFailed to load resource\n```",
        "```text\nGET /api/error HTTP/1.1 500\n```",
    ):
        expect_in(member=text, container=section)
    expect_not_in(member="FRONTEND001 at", container=rendered)
    expect_not_in(member="### Index", container=section)
