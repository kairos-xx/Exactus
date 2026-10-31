#!/usr/bin/env python3
# Copyright (c) 2026
"""Record, replay, and Exactus Record browser sessions as an exactus."""

from __future__ import annotations

from asyncio import run as run_async
from importlib import import_module
from json import loads
from pathlib import Path
from sys import path as sys_path
from time import monotonic
from typing import TYPE_CHECKING, Final, cast
from typing import final as _group_final_final

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
from exactus.packages.project_python import auto as _project_python_auto
from exactus.packages.steps import step_log, trace
from exactus.tools.common.cli import resolve_output
from exactus.tools.common.config import resolve_arguments
from exactus.tools.common.execution import run_exactus
from exactus.tools.common.sprint import sprint
from exactus.tools.record.arguments import Constants as _GroupFinalConstants
from exactus.tools.record.arguments import create_parser as _create_parser
from exactus.tools.record.core import RecordResult, passed, report_data
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Workspace
    from exactus.tools.record.studio.service import StudioService
_project_python_active: bool = _project_python_auto.Constants.activated


@_group_final_final
class Constants:
    """Group module-level constants.

    Attributes:
        max_crawl_depth: Grouped module constant.
        max_crawl_states: Grouped module constant.

    """

    max_crawl_depth: Final[int] = 10
    max_crawl_states: Final[int] = 200


def create_parser() -> ArgumentParser:
    """Return the shared CLI grammar used by execution and completion.

    Returns:
        Configured tool argument parser.

    """
    return _create_parser()


def parse_args(*, arguments: tuple[str, ...] | None = None) -> Namespace:
    """Parse the recorder command line.

    Args:
        arguments: Command-line tokens, or ``None`` for ``sys.argv``.

    Returns:
        The parsed options.

    """
    parser: ArgumentParser = create_parser()
    return parser.parse_args(
        args=resolve_arguments(
            tool="record",
            parser=parser,
            arguments=arguments,
        ),
    )


def _export_workspace(
    *,
    actions: tuple[dict[str, JsonValue], ...],
    options: Namespace,
    output: Path,
) -> tuple[int, str]:
    """Export a recorded program as a Exactus Record workspace.

    Args:
        actions: Replayable actions to export.
        options: Parsed command-line options.
        output: Report directory receiving the workspace.

    Returns:
        ``(exported event count, workspace file name)``.

    """
    studio: ModuleType = import_module(
        name="exactus.tools.record.workspace_actions",
    )
    flow_id: str = cast(typ="str", val=options.flow_id)
    events: list[dict[str, JsonValue]] = studio.actions_to_events(
        actions=actions,
        flow_id=flow_id,
    )
    workspace: dict[str, JsonValue] = studio.build_workspace(
        flows=[
            studio.build_flow(
                flow_id=flow_id,
                name=cast(typ="str", val=options.flow_name),
                events=events,
                notes=f"Recorded from {options.url or 'Exactus Record'}.",
            ),
        ],
    )
    studio.write_workspace(
        path=output / _GroupFinalConstants.workspace_name,
        workspace=workspace,
    )
    extra: Path | None = cast(typ="Path | None", val=options.workspace)
    if extra is not None:
        studio.write_workspace(path=extra, workspace=workspace)
    return (len(events), _GroupFinalConstants.workspace_name)


def _artifacts(*, output: Path) -> tuple[str, ...]:
    """List the program files a session left in the output directory.

    Args:
        output: Report directory.

    Returns:
        Sorted names of the recorder artifacts present.

    """
    names: tuple[str, ...] = (
        "actions.raw.jsonl",
        "actions.normalized.json",
        "actions.py.txt",
        "actions.mjs.txt",
        _GroupFinalConstants.workspace_name,
    )
    return tuple(name for name in names if (output / name).is_file())


def _load_program(
    *,
    path: Path,
    flow: str | None,
) -> list[dict[str, JsonValue]]:
    """Load a replay program from either supported file type.

    Args:
        path: Normalized action file or ``.pwflow.json`` workspace.
        flow: Workspace Flow to extract, or ``None`` for the first.

    Returns:
        The replayable actions.

    """
    studio: ModuleType = import_module(
        name="exactus.tools.record.workspace_actions",
    )
    return cast(
        typ="list[dict[str, JsonValue]]",
        val=studio.load_flow_actions(path=path, flow_id=flow),
    )


def _replay(
    *,
    options: Namespace,
    started: float,
    output: Path,
) -> RecordResult:
    """Replay a stored program and collect failures.

    Args:
        options: Parsed command-line options.
        started: Monotonic start time of the session.
        output: Directory receiving functional-test evidence.

    Returns:
        The replay outcome.

    """
    recorder: ModuleType = import_module(
        name="exactus.tools.record.action_recorder",
    )
    actions: list[dict[str, JsonValue]] = _load_program(
        path=cast(typ="Path", val=options.replay),
        flow=cast(typ="str | None", val=options.flow),
    )
    artifacts: tuple[str, ...] = ()
    replay_path: Path = cast(typ="Path", val=options.replay)
    document: JsonValue = cast(
        typ="JsonValue",
        val=loads(s=replay_path.read_text(encoding="utf-8")),
    )
    if isinstance(document, dict) and "flows" in document:
        runner: ModuleType = import_module(name="exactus.tools.record.run")
        report: dict[str, JsonValue] = runner.run_workspace(
            path=replay_path,
            output=output / "flow-tests",
            flow_id=cast(typ="str | None", val=options.flow),
            url=options.url,
            browser=runner.BrowserOptions(
                width=options.width,
                height=options.height,
                headless=options.headless,
            ),
        )
        artifacts = tuple(
            sorted(
                str(object=path.relative_to(output))
                for path in (output / "flow-tests").rglob(pattern="*")
                if path.is_file()
            ),
        )
        failures = [
            str(object=item.get("error") or "Flow failed")
            for item in cast(
                typ="list[dict[str, JsonValue]]",
                val=report["flows"],
            )
            if item["status"] == "failed"
        ]
    else:
        failures: list[str] = recorder.ActionReplayer(
            url=cast(typ="str", val=options.url),
            actions=actions,
            options=recorder.ReplayOptions(
                width=cast(typ="int", val=options.width),
                height=cast(typ="int", val=options.height),
                headless=cast(typ="bool", val=options.headless),
                timeout_ms=cast(typ="float", val=options.timeout_ms),
            ),
        ).run()
    return RecordResult(
        mode="replay",
        url=cast(typ="str", val=options.url),
        actions=tuple(actions),
        artifacts=artifacts,
        failures=tuple(failures),
        elapsed_seconds=monotonic() - started,
    )


def _record(
    *,
    options: Namespace,
    output: Path,
    started: float,
) -> RecordResult:
    """Record an interactive session and export its programs.

    Args:
        options: Parsed command-line options.
        output: Report directory receiving the recorder artifacts.
        started: Monotonic start time of the session.

    Returns:
        The recording outcome.

    """
    recorder: ModuleType = import_module(
        name="exactus.tools.record.action_recorder",
    )
    actions: list[dict[str, JsonValue]] = recorder.ActionRecorder(
        options=recorder.RecorderOptions(
            url=cast(typ="str", val=options.url),
            output=output,
            width=cast(typ="int", val=options.width),
            height=cast(typ="int", val=options.height),
            timeout_ms=cast(typ="float", val=options.timeout_ms),
            preserve_timing=cast(typ="bool", val=options.preserve_timing),
        ),
    ).run()
    exported, workspace = _export_workspace(
        actions=tuple(actions),
        options=options,
        output=output,
    )
    return RecordResult(
        mode="record",
        url=cast(typ="str", val=options.url),
        actions=tuple(actions),
        exported_events=exported,
        workspace=workspace,
        artifacts=_artifacts(output=output),
        elapsed_seconds=monotonic() - started,
    )


def _studio(
    *,
    options: Namespace,
    output: Path,
    started: float,
) -> RecordResult:
    """Drive Exactus Record as its recorder/player.

    Args:
        options: Parsed command-line options.
        output: Report directory receiving the session artifacts.
        started: Monotonic start time of the session.

    Returns:
        The Studio session outcome.

    """
    host: ModuleType = import_module(
        name="exactus.tools.record.studio.__main__",
    )
    service: StudioService = host.serve(
        options=host.StudioLaunch(
            root=cast(typ="Path", val=options.root).resolve(),
            port=cast(typ="int", val=options.port),
            headless=cast(typ="bool", val=options.headless),
            open_editor=not cast(typ="bool", val=options.no_open),
            window=cast(typ="bool", val=options.window),
            target_url=cast(typ="str | None", val=options.url),
            duration_seconds=cast(typ="float | None", val=options.duration),
        ),
    )
    interchange: ModuleType = import_module(
        name="exactus.tools.record.workspace_actions",
    )
    document: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=service.export_document(),
    )
    interchange.write_workspace(
        path=output / _GroupFinalConstants.workspace_name,
        workspace=document,
    )
    workspace: Workspace = service.controller.workspace
    return RecordResult(
        mode="studio",
        url=cast(typ="str | None", val=options.url) or "",
        actions=(),
        exported_events=sum(len(flow.events) for flow in workspace.flows),
        workspace=_GroupFinalConstants.workspace_name,
        artifacts=_artifacts(output=output),
        elapsed_seconds=monotonic() - started,
    )


def _crawl(
    *,
    options: Namespace,
    output: Path,
    started: float,
) -> RecordResult:
    """Export bounded discoveries as one ordinary Studio project.

    Args:
        options: Target URL and discovery limits.
        output: Project and report destination.
        started: Monotonic start time.

    Returns:
        Discovery outcome with the generated project artifact.

    """
    discovery: ModuleType = import_module(
        name="exactus.tools.record.discovery",
    )
    explorer: ModuleType = import_module(
        name="exactus.tools.record.click_explorer",
    )
    documents: list[dict[str, JsonValue]] = []
    run_async(
        main=discovery.discover(
            options=explorer.ExplorerOptions(
                url=cast(typ="str", val=options.url),
                output=output,
                max_depth=cast(typ="int", val=options.max_depth),
                max_states=cast(typ="int", val=options.max_states),
                width=cast(typ="int", val=options.width),
                height=cast(typ="int", val=options.height),
                capture_ui_changes=options.capture_ui_changes,
                follow_links=options.follow_links,
                click_controls=options.click_controls,
                include_selector=options.include_selector,
            ),
            cancelled=lambda: False,
            emit=documents.append,
        ),
    )
    final: dict[str, JsonValue] = documents[-1]
    document: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=final["workspace"],
    )
    interchange: ModuleType = import_module(
        name="exactus.tools.record.workspace_actions",
    )
    interchange.write_workspace(
        path=output / _GroupFinalConstants.workspace_name,
        workspace=document,
    )
    flows: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=document["flows"],
    )
    return RecordResult(
        mode="crawl",
        url=cast(typ="str", val=options.url),
        actions=(),
        exported_events=sum(
            len(cast(typ="list[JsonValue]", val=flow["events"]))
            for flow in flows
        ),
        workspace=_GroupFinalConstants.workspace_name,
        artifacts=(
            _GroupFinalConstants.workspace_name,
            "discovered.pwflow.json",
        ),
        elapsed_seconds=monotonic() - started,
    )


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Run the record exactus.

    Args:
        arguments: Command-line tokens, or ``None`` for ``sys.argv``.

    Returns:
        ``0`` when the session raised no error finding, ``1`` otherwise.

    """
    parser: ArgumentParser = create_parser()
    options: Namespace = parse_args(arguments=arguments)
    if (options.replay is not None or options.crawl) and options.url is None:
        parser.error(message="Pass --url URL for replay or discovery.")
    root: Path = cast(typ="Path", val=options.root).resolve()
    output: Path = resolve_output(
        root=root,
        output=cast(typ="Path", val=options.output_dir),
    )
    output.mkdir(parents=True, exist_ok=True)
    with step_log(path=output / "ARTIFACTS" / "steps.txt"):
        trace(step=(f"record: arguments — root {root}, output {output}"))
        trace(step="record: run start")
        started: float = monotonic()
        result: RecordResult
        if options.crawl:
            if (
                not 1 <= options.max_depth <= Constants.max_crawl_depth
                or not 1 <= options.max_states <= Constants.max_crawl_states
            ):
                parser.error(message="Use depth 1-10 and state limit 1-200.")
            result = _crawl(options=options, output=output, started=started)
        elif options.replay is not None:
            result = _replay(options=options, started=started, output=output)
        elif (
            options.url is not None
            and (not options.no_open)
            and (options.duration is None)
        ):
            result = _record(options=options, output=output, started=started)
        else:
            result = _studio(options=options, output=output, started=started)
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output / "result.md",
                json=output / "result.json",
                web=output / "result_web",
            ),
            analyzer="record",
            title="Record Exactus",
            markdown="",
            data={
                **report_data(result=result),
                "project_root": str(object=root),
            },
        )
        sprint(f"Reports written to {output}.")
        status: int = 0 if passed(result=result) else 1
        trace(step=f"record: run finished — status {status}")
        return status


if __name__ == "__main__":
    raise SystemExit(
        run_exactus(analyzer="record", title="Record Exactus", main=main),
    )
