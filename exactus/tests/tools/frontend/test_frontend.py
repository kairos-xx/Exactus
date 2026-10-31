# Copyright (c) 2026
"""Verify FRONTEND uses normal Studio projects and their capture policies."""

from __future__ import annotations

from dataclasses import replace
from json import dumps, loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_in, expect_true
from exactus.tools.frontend.core import (
    FrontendExactusInput,
    FrontendExactusResult,
    FrontendFinding,
    frontend,
    markdown_report,
    report_data,
)
from exactus.tools.frontend.main import main as frontend_main
from exactus.tools.frontend.main import parse_args
from exactus.tools.record.model import (
    EventKind,
    Flow,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.store import Workspace, WorkspaceCodec

if TYPE_CHECKING:
    from argparse import Namespace

    from exactus.tools.common.json_types import JsonValue


def _project(*, path: Path, screenshot: bool) -> Path:
    """Save independent passing and failing workflow entry points.

    Args:
        path: Destination project file.
        screenshot: Attach a screenshot event to the passing flow.

    Returns:
        Saved project path.

    """
    event: TimelineEvent = TimelineEvent(
        event_id="script",
        flow_id="passing",
        sequence=0,
        elapsed_ms=0,
        layer=TimelineLayer.INTERACTION,
        kind=EventKind.JAVASCRIPT,
        label="Read structured response",
        payload="() => ({answer: 42, nested: [false, null]})",
    )
    events: list[TimelineEvent] = [event]
    if screenshot:
        events.append(
            replace(
                event,
                event_id="image",
                sequence=1,
                kind=EventKind.NOTE,
                payload="__screenshot__",
                label="Capture result",
            ),
        )
    failing: TimelineEvent = replace(
        event,
        flow_id="failing",
        event_id="failure",
        payload="() => { throw new Error('deliberate failure'); }",
    )
    WorkspaceCodec.save(
        path=path,
        workspace=Workspace(
            flows=(
                Flow(
                    task_description="",
                    expected_behavior="",
                    notes="",
                    flow_id="passing",
                    name="Passing",
                    events=tuple(events),
                ),
                Flow(
                    task_description="",
                    expected_behavior="",
                    notes="",
                    flow_id="failing",
                    name="Failing",
                    events=(failing,),
                ),
            ),
            edges=(),
        ),
    )
    return path


@pytest.mark.parametrize("screenshot", [False, True])
def test_flow_capture_policy_and_response(
    *,
    screenshot: bool,
    tmp_path: Path,
) -> None:
    """Preserve outcomes, JavaScript results and requested images.

    Args:
        screenshot: Whether the flow requests a screenshot artifact.
        tmp_path: Isolated per-test directory.

    """
    project: Path = _project(
        path=tmp_path / "project.pwflow.json",
        screenshot=screenshot,
    )
    result: FrontendExactusResult = frontend(
        inputs=FrontendExactusInput(
            output=tmp_path / "report",
            workspace=project,
        ),
    )
    data: dict[str, JsonValue] = report_data(result=result)
    flows: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=data["flows"],
    )
    expect_equal(
        actual=[flow["status"] for flow in flows],
        expected=["succeeded", "failed"],
    )
    records: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=flows[0]["action_records"],
    )
    expect_equal(
        actual=records[0]["response"],
        expected={"answer": 42, "nested": [False, None]},
    )
    images: list[Path] = list((tmp_path / "report").rglob(pattern="*.png"))
    expect_equal(actual=len(images), expected=int(screenshot))
    expect_equal(actual=len(result.findings), expected=1)
    expect_equal(
        actual=loads(
            s=(
                tmp_path / "report" / "ARTIFACTS" / "RUN" / "result.json"
            ).read_text(),
        )["flows"][0]["status"],
        expected="succeeded",
    )


def test_url_only_has_no_implicit_screenshots(tmp_path: Path) -> None:
    """Navigate without discovery or implicit screenshot artifacts.

    Args:
        tmp_path: Isolated per-test directory.

    """
    result: FrontendExactusResult = frontend(
        inputs=FrontendExactusInput(
            output=tmp_path,
            url="data:text/html,<h1>Ready</h1>",
        ),
    )
    expect_equal(actual=result.findings, expected=())
    expect_equal(actual=list(tmp_path.rglob(pattern="*.png")), expected=[])


def test_parser_accepts_workspace_without_url(tmp_path: Path) -> None:
    """Allow self-contained projects and reject obsolete crawler arguments.

    Args:
        tmp_path: Isolated per-test directory.

    """
    options: Namespace = parse_args(
        arguments=(str(object=tmp_path), "--workspace", "project.pwflow.json"),
    )
    expect_equal(
        actual=options.workspace,
        expected=Path("project.pwflow.json"),
    )
    with pytest.raises(expected_exception=SystemExit):
        parse_args(
            arguments=(
                str(object=tmp_path),
                "--url",
                "http://localhost",
                "--max-depth",
                "2",
            ),
        )
    with pytest.raises(expected_exception=SystemExit):
        parse_args(arguments=(str(object=tmp_path),))


def test_configured_recipe_and_explicit_project(tmp_path: Path) -> None:
    """Resolve recipes beside their config and honor explicit projects.

    Args:
        tmp_path: Isolated configured project root.

    """
    (tmp_path / "pyproject.toml").write_text(
        data=dedent(
            text=(
                "    [tool.exactus]\n    root = true\n    [tool.exactus.fr"
                'ontend]\n    actions = "recipes/check.json"\n    '
            ),
        ),
        encoding="utf-8",
    )
    base: tuple[str] = (str(object=tmp_path),)
    options: Namespace = parse_args(arguments=base)
    expect_equal(
        actual=options.actions,
        expected=tmp_path / "recipes/check.json",
    )
    options = parse_args(
        arguments=(*base, "--workspace", "edited.pwflow.json"),
    )
    expect_equal(actual=options.actions, expected=None)
    expect_equal(actual=options.workspace, expected=Path("edited.pwflow.json"))
    with pytest.raises(expected_exception=SystemExit):
        parse_args(
            arguments=(
                *base,
                "--actions",
                "recipe.json",
                "--workspace",
                "project.json",
            ),
        )


def test_frontend_cli_runs_recipe_and_writes_report(tmp_path: Path) -> None:
    """The Actions CLI executes an imported project and preserves responses.

    Args:
        tmp_path: Disposable recipe and report directory.

    """
    workspace: Workspace = Workspace(
        edges=(),
        flows=(
            Flow(
                flow_id="answer",
                name="Read answer",
                task_description="Read value",
                expected_behavior="Answer is 42",
                notes="",
                events=(
                    TimelineEvent(
                        event_id="answer",
                        flow_id="answer",
                        sequence=0,
                        elapsed_ms=0,
                        layer=TimelineLayer.INTERACTION,
                        kind=EventKind.JAVASCRIPT,
                        label="Read answer",
                        payload="() => ({answer: 42})",
                    ),
                ),
            ),
        ),
    )
    project: Path = tmp_path / "answer.pwflow.json"
    WorkspaceCodec.save(path=project, workspace=workspace)
    recipe: Path = tmp_path / "actions.json"
    recipe.write_text(
        data=dumps(
            obj={
                "version": 1,
                "actions": [
                    {
                        "id": "verify",
                        "tool": "frontend.run",
                        "arguments": {
                            "projects": [
                                {
                                    "workspace": str(object=project),
                                    "width": 390,
                                    "height": 844,
                                    "theme": "light",
                                },
                            ],
                        },
                    },
                ],
            },
        ),
    )
    output: Path = tmp_path / "report"
    expect_equal(
        actual=frontend_main(
            arguments=(
                str(object=tmp_path),
                "--actions",
                str(object=recipe),
                "-o",
                str(object=output),
            ),
        ),
        expected=0,
    )
    expect_true(condition=any(output.rglob(pattern="*.json")))


def test_frontend_legacy_markdown_retains_step_response(
    tmp_path: Path,
) -> None:
    """Standalone rendering preserves failed workflows and JavaScript data.

    Args:
        tmp_path: Isolated output directory.

    """
    result: FrontendExactusResult = FrontendExactusResult(
        findings=(
            FrontendFinding(
                rule="FLOW001",
                file="checkout",
                message="Missing receipt",
            ),
        ),
        options=FrontendExactusInput(url="about:blank", output=tmp_path),
        execution={
            "flows": [
                None,
                {
                    "flow_id": "checkout",
                    "run_id": "test",
                    "status": "failed",
                    "action_records": [
                        None,
                        {
                            "event_id": "receipt",
                            "label": "Read receipt",
                            "status": "failed",
                            "response": {"answer": 42},
                        },
                    ],
                },
            ],
        },
        server_diagnostics=(),
        elapsed_seconds=0.1,
    )
    markdown: str = markdown_report(result=result)
    expect_in(member="Read receipt", container=markdown)
    expect_in(member='"answer": 42', container=markdown)
    expect_in(member="Missing receipt", container=markdown)
