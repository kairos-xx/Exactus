# Copyright (c) 2026 Project contributors
"""Verify declarative tool orchestration through real discovery and replay."""

from __future__ import annotations

from importlib import import_module
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_call,
)
from exactus.tools.actions import runner
from exactus.tools.actions.runner import (
    load_actions,
    run_actions,
    validate_actions,
)
from exactus.tools.record.model import (
    EventKind,
    Flow,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Workspace
actions_main: ModuleType = import_module(name="exactus.tools.actions.__main__")


def test_actions_entrypoint_defaults_and_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve default paths and map aggregate status to a process code.

    Args:
        tmp_path: Temporary recipe directory.
        monkeypatch: Pytest patching helper.

    """
    recipe: Path = tmp_path / "recipe.json"
    recipe.write_text(data="{}", encoding="utf-8")
    specification: dict[str, JsonValue] = {"version": 1, "actions": []}
    calls: list[tuple[dict[str, JsonValue], Path, Path]] = []

    def load(*, path: Path) -> dict[str, JsonValue]:
        """Return the fixture recipe from its expected path.

        Args:
            path: Recipe path requested by the entry point.

        Returns:
            Fixture action specification.

        """
        expect_equal(actual=path, expected=recipe)
        return specification

    monkeypatch.setattr(target=actions_main, name="load_actions", value=load)

    def run(
        *,
        specification: dict[str, JsonValue],
        root: Path,
        output: Path,
    ) -> dict[str, JsonValue]:
        """Capture resolved arguments and return a failed report.

        Args:
            specification: Loaded action recipe.
            root: Resolved action root.
            output: Resolved report output.

        Returns:
            Failed aggregate report.

        """
        calls.append((specification, root, output))
        return {"status": "failed"}

    monkeypatch.setattr(target=actions_main, name="run_actions", value=run)
    with patch(target="sys.argv", new=["actions", str(object=recipe)]):
        expect_equal(actual=actions_main.main(), expected=1)
    expect_equal(
        actual=calls,
        expected=[
            (
                specification,
                tmp_path.resolve(),
                Path("EXACTUS_RESULTS/ACTIONS"),
            ),
        ],
    )


@pytest.mark.parametrize("timestamps", [(), (0,), (0, 10000), (10000, 0)])
def test_evaluations_follow_captured_timestamps(
    timestamps: tuple[int, ...],
) -> None:
    """Keep script order after slow or out-of-order discovered captures.

    Args:
        timestamps: Recorded timestamps, including slow capture scenarios.

    """
    flow: Flow = Flow(
        flow_id="discovered",
        name="Captured flow",
        task_description="",
        expected_behavior="",
        notes="",
        events=tuple(
            TimelineEvent(
                event_id=f"capture-{index}",
                flow_id="discovered",
                sequence=index,
                elapsed_ms=timestamp,
                layer=TimelineLayer.INTERACTION,
                kind=EventKind.NOTE,
                label="Capture UI change",
            )
            for index, timestamp in enumerate(iterable=timestamps)
        ),
    )
    updated: Flow = cast(
        typ="Flow",
        val=private_call(
            owner=runner,
            name="_append_javascript",
            flow=flow,
            scripts=["() => 1", "() => 2"],
        ),
    )
    baseline: int = max(timestamps, default=0)
    expect_equal(actual=updated.events[:-2], expected=flow.events)
    expect_equal(
        actual=[event.elapsed_ms for event in updated.events[-2:]],
        expected=[baseline + 500, baseline + 1000],
    )
    expect_equal(
        actual=[event.sequence for event in updated.events[-2:]],
        expected=[len(timestamps), len(timestamps) + 1],
    )
    expect_equal(
        actual=[event.payload for event in updated.events[-2:]],
        expected=["() => 1", "() => 2"],
    )


def test_rejects_unknown_tools_and_forward_references() -> None:
    """Validate recipes before any process or tool starts."""
    candidates: list[JsonValue] = [
        {"version": True, "actions": []},
        {
            "version": 1,
            "actions": [{"id": "first", "tool": "shell", "arguments": {}}],
        },
        {
            "version": 1,
            "actions": [
                {
                    "id": "first",
                    "tool": "frontend.run",
                    "arguments": {"projects": "$later.projects"},
                },
            ],
        },
    ]
    for value in candidates:
        with pytest.raises(
            expected_exception=ValueError,
            match=r"Actions|Use|Unavailable",
        ):
            validate_actions(value=value)


def test_toml_named_output_reference(tmp_path: Path) -> None:
    """Read the same tool recipe from TOML without shell expansion.

    Args:
        tmp_path: Isolated per-test directory.

    """
    path: Path = tmp_path / "actions.toml"
    path.write_text(
        data=dedent(
            text=(
                '    version = 1\n    [[actions]]\n    id = "discover"\n  '
                '  tool = "record.crawl"\n    [actions.arguments]\n    url'
                ' = "http://localhost/"\n    [[actions]]\n    id = "verify'
                '"\n    tool = "frontend.run"\n    [actions.arguments]\n  '
                '  projects = "$discover.projects"\n    '
            ),
        ),
        encoding="utf-8",
    )
    expect_equal(actual=load_actions(path=path)["version"], expected=1)


def test_demo_discovery_replay_and_report(tmp_path: Path) -> None:
    """Launch once and replay discovered projects in two themes.

    Args:
        tmp_path: Isolated per-test directory.

    """
    root: Path = Path(__file__).resolve().parents[4]
    recipe: dict[str, JsonValue] = {
        "version": 1,
        "actions": [
            {
                "id": "discover",
                "tool": "record.crawl",
                "arguments": {
                    "entrypoint": "demo/server.py",
                    "url": "http://127.0.0.1/",
                    "port": 0,
                    "max_depth": 1,
                    "max_states": 1,
                    "screenshots": True,
                    "server_errors": True,
                    "javascript": [
                        (
                            "() => ({title: document.title, "
                            "theme: matchMedia('(prefers-color-scheme: dark)')"
                            ".matches})"
                        ),
                    ],
                    "environments": [
                        {"width": 390, "height": 844, "theme": "light"},
                        {"width": 800, "height": 600, "theme": "dark"},
                    ],
                },
            },
            {
                "id": "verify",
                "tool": "frontend.run",
                "arguments": {
                    "projects": "$discover.projects",
                    "server_log": "$discover.server_log",
                },
            },
        ],
    }
    output: Path = tmp_path / "actions"
    result: dict[str, JsonValue] = run_actions(
        specification=recipe,
        root=root,
        output=output,
    )
    actions: list[JsonValue] = cast(
        typ="list[JsonValue]",
        val=result["actions"],
    )
    expect_equal(actual=len(actions), expected=2)
    outputs: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=result["outputs"],
    )
    discover: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=outputs["discover"],
    )
    projects: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=discover["projects"],
    )
    expect_equal(actual=len(projects), expected=2)
    for project in projects:
        workspace: Workspace = WorkspaceCodec.load(
            path=Path(cast(typ="str", val=project["workspace"])),
        )
        expect_true(
            condition=any(
                event.kind == "javascript"
                for flow in workspace.flows
                for event in flow.events
            ),
        )
        for flow in workspace.flows:
            expect_equal(actual=flow.events[-1].kind, expected="javascript")
            expect_true(
                condition=all(
                    event.elapsed_ms < flow.events[-1].elapsed_ms
                    for event in flow.events[:-1]
                ),
            )
    verify: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=outputs["verify"],
    )
    reports: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=verify["reports"],
    )
    themes: list[JsonValue] = []
    for report in reports:
        execution: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=report["execution"],
        )
        flows: list[dict[str, JsonValue]] = cast(
            typ="list[dict[str, JsonValue]]",
            val=execution["flows"],
        )
        records: list[dict[str, JsonValue]] = cast(
            typ="list[dict[str, JsonValue]]",
            val=flows[0]["action_records"],
        )
        response: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=records[-1]["response"],
        )
        themes.append(response["theme"])
    expect_equal(actual=themes, expected=[False, True])
    expect_true(condition=(output / "discover" / "server.log").is_file())
    expect_true(condition=(output / "result_web" / "index.html").is_file())
    expect_equal(
        actual=loads(s=(output / "actions-result.json").read_text())["status"],
        expected=result["status"],
    )


def test_setup_failure_retains_report_and_stops_server(tmp_path: Path) -> None:
    """Preserve a failed tool result and clean up its owned process.

    Args:
        tmp_path: Isolated per-test directory.

    """
    specification: dict[str, JsonValue] = {
        "version": 1,
        "actions": [
            {
                "id": "discover",
                "tool": "record.crawl",
                "arguments": {"entrypoint": "missing.py"},
            },
        ],
    }
    with (
        patch(
            target="exactus.tools.actions.runner.start_entrypoint",
            return_value=(987654, 8123),
        ),
        patch(
            target="exactus.tools.actions.runner.wait_ready",
            return_value=False,
        ),
        patch(
            target="exactus.tools.actions.runner.terminate_tree",
        ) as terminate,
    ):
        report: dict[str, JsonValue] = run_actions(
            specification=specification,
            root=tmp_path,
            output=tmp_path / "out",
        )
    expect_equal(actual=report["status"], expected="failed")
    terminate.assert_called_once_with(pid=987654)
    expect_true(condition=(tmp_path / "out" / "actions-result.json").is_file())


@pytest.mark.parametrize(
    "arguments",
    [
        {"screenshots": "false"},
        {"max_depth": 0},
        {"max_states": 201},
        {"port": True},
        {"port": 65536},
        {"snapshot": True},
        {"javascript": [""]},
        {"environments": [{"width": 390.5}]},
        {"environments": [{"height": -1}]},
        {"environments": [{"theme": "system"}]},
        {"url": "file:///tmp/index.html"},
    ],
)
def test_invalid_later_call_never_starts_server(
    tmp_path: Path,
    arguments: dict[str, JsonValue],
) -> None:
    """Reject the whole recipe before executing an earlier valid call.

    Args:
        tmp_path: Isolated output directory.
        arguments: Invalid arguments in the second call.

    """
    specification: dict[str, JsonValue] = {
        "version": 1,
        "actions": [
            {
                "id": "first",
                "tool": "record.crawl",
                "arguments": {"entrypoint": "server.py"},
            },
            {"id": "second", "tool": "record.crawl", "arguments": arguments},
        ],
    }
    with patch(
        target="exactus.tools.actions.runner.start_entrypoint",
    ) as start:
        with pytest.raises(
            expected_exception=ValueError,
            match=r"must|Unknown|JavaScript|Environment|positive",
        ):
            run_actions(
                specification=specification,
                root=tmp_path,
                output=tmp_path / "out",
            )
        start.assert_not_called()
    expect_true(condition=not (tmp_path / "out").exists())


def test_frontend_findings_can_be_report_only(tmp_path: Path) -> None:
    """Keep intentional frontend findings while allowing Actions to succeed.

    Args:
        tmp_path: Isolated report directory.

    """
    events: list[dict[str, JsonValue]] = []
    recipe: dict[str, JsonValue] = {
        "version": 1,
        "actions": [
            {
                "id": "verify",
                "tool": "frontend.run",
                "arguments": {
                    "projects": [
                        {
                            "workspace": "project.pwflow.json",
                            "width": 390,
                            "height": 844,
                            "theme": "light",
                        },
                    ],
                    "fail_on_findings": False,
                },
            },
        ],
    }
    with (
        patch.object(
            target=runner,
            attribute="frontend",
            return_value=object(),
        ),
        patch.object(
            target=runner,
            attribute="report_data",
            return_value={
                "findings": [
                    {
                        "rule": "FRONTEND001",
                        "severity": "error",
                        "message": "intentional",
                    },
                ],
            },
        ),
        patch.object(target=runner.ReportBundle, attribute="write"),
        patch.object(target=runner, attribute="_report_actions"),
    ):
        result: dict[str, JsonValue] = run_actions(
            specification=recipe,
            root=tmp_path,
            output=tmp_path / "actions",
            emit=events.append,
        )
    expect_equal(actual=result["status"], expected="succeeded")
    output: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=cast(typ="dict[str, JsonValue]", val=result["outputs"])["verify"],
    )
    expect_equal(actual=output["findings"], expected=1)
    expect_equal(actual=output["status"], expected="succeeded")
    expect_equal(actual=events[-1]["state"], expected="succeeded")
    expect_equal(actual=events[-1]["action_id"], expected="verify")
    expect_equal(actual=events[-1]["tool"], expected="frontend.run")
