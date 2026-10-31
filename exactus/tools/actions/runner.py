# Copyright (c) 2026 Project contributors
"""Orchestrate discovery and functional exactuss from JSON or TOML actions."""

from __future__ import annotations

from asyncio import run as async_run
from dataclasses import replace
from functools import partial
from json import loads
from pathlib import Path
from tomllib import loads as load_toml
from typing import TYPE_CHECKING, Final, Literal, cast
from typing import final as _group_final_final
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from exactus.packages.server.local import start_entrypoint, wait_ready
from exactus.tools.actions.conflict_copies import clear_conflict_copies
from exactus.tools.actions.process_control import terminate_tree
from exactus.tools.common.api import ExactusApi
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.models import ToolRequest
from exactus.tools.frontend.core import (
    FrontendExactusInput,
    frontend,
    report_data,
)
from exactus.tools.frontend.report import normalized_data
from exactus.tools.record.click_explorer import CaptureVariant, ExplorerOptions
from exactus.tools.record.discovery import discover
from exactus.tools.record.model import (
    EventKind,
    Flow,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.workspace_actions import write_workspace
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from collections.abc import Callable
    from urllib.parse import SplitResult

    from exactus.tools.actions.json_types import JsonValue
    from exactus.tools.common.catalog import ToolSpec
    from exactus.tools.common.models import ToolRunResult
    from exactus.tools.frontend.core import FrontendExactusResult
    from exactus.tools.record.model import Workspace


def load_actions(*, path: Path) -> dict[str, JsonValue]:
    """Read a JSON or TOML tool recipe.

    Args:
        path: Recipe file.

    Returns:
        Validated action specification.

    """
    text: str = path.read_text(encoding="utf-8")
    value: JsonValue = (
        load_toml(text) if path.suffix == ".toml" else loads(s=text)
    )
    return validate_actions(value=value)


def validate_actions(*, value: JsonValue) -> dict[str, JsonValue]:
    """Validate all tool calls and references before launching anything.

    Args:
        value: Untrusted recipe document.

    Returns:
        Current-version recipe.

    Raises:
        TypeError: When the operation cannot complete with these arguments.
        ValueError: When tools, IDs or references are invalid.

    """
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value.get("version") != 1
    ):
        msg: str = "Actions require a version 1 object."
        raise ValueError(msg)
    steps: JsonValue | None = value.get("actions")
    if not isinstance(steps, list) or not steps:
        msg = "Actions require a nonempty sequence of tool calls."
        raise ValueError(msg)
    known: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            msg = "Each action must be an object."
            raise TypeError(msg)
        identity: JsonValue | None = step.get("id")
        if (
            not isinstance(identity, str)
            or not identity.isidentifier()
            or identity in known
        ):
            msg = "Action IDs must be unique identifiers."
            raise ValueError(msg)
        if step.get("tool") not in {
            "record.crawl",
            "frontend.run",
            *(
                tool.identifier
                for tool in _GroupFinalConstants.exactus_catalog.tools()
            ),
        }:
            msg = "Use record.crawl, frontend.run or a canonical exactus tool."
            raise ValueError(msg)
        arguments: JsonValue | None = step.get("arguments", {})
        if not isinstance(arguments, dict):
            msg = "Action arguments must be an object."
            raise TypeError(msg)
        _validate_references(value=arguments, known=known)
        _validate_arguments(tool=str(object=step["tool"]), arguments=arguments)
        known.add(identity)
    return value


def _bounded_integer(
    *,
    value: JsonValue,
    name: str,
    minimum: int,
    maximum: int,
) -> None:
    """Require an integer within the supported execution limits.

    Args:
        value: Argument value.
        name: Argument label.
        minimum: Inclusive lower bound.
        maximum: Inclusive upper bound.

    Raises:
        ValueError: When the value is outside the supported range.

    """
    if type(value) is not int or not minimum <= value <= maximum:
        msg: str = (
            f"{name} must be an integer between {minimum} and {maximum}."
        )
        raise ValueError(msg)


def _validate_arguments(*, tool: str, arguments: dict[str, JsonValue]) -> None:
    """Check concrete tool arguments before starting application processes.

    Args:
        tool: Canonical tool identifier.
        arguments: Declared call arguments.

    Raises:
        ValueError: When argument names, types or limits are invalid.

    """
    allowed: set[str] = {"argv"}
    if tool == "record.crawl":
        allowed = {
            "entrypoint",
            "url",
            "port",
            "screenshots",
            "server_errors",
            "javascript",
            "max_depth",
            "max_states",
            "environments",
            "follow_links",
            "click_controls",
            "include_selector",
        }
    elif tool == "frontend.run":
        allowed = {"projects", "server_log", "workers", "fail_on_findings"}
    unknown: set[str] = set(arguments) - allowed
    if unknown:
        msg: str = f"Unknown {tool} arguments: {', '.join(sorted(unknown))}."
        raise ValueError(msg)
    if tool == "record.crawl":
        _validate_crawl_arguments(
            arguments={
                key: item
                for key, item in arguments.items()
                if not (isinstance(item, str) and item.startswith("$"))
            },
        )
    elif tool == "frontend.run":
        if "fail_on_findings" in arguments and not isinstance(
            arguments["fail_on_findings"],
            bool,
        ):
            msg = "fail_on_findings must be a boolean."
            raise ValueError(msg)
        if "workers" in arguments:
            _bounded_integer(
                value=arguments["workers"],
                name="workers",
                minimum=1,
                maximum=64,
            )
        projects: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = arguments.get("projects")
        if not (
            (isinstance(projects, str) and projects.startswith("$"))
            or (
                isinstance(projects, list)
                and projects
                and all(isinstance(project, dict) for project in projects)
            )
        ):
            msg = "frontend.run requires projects or an output reference."
            raise ValueError(msg)
    else:
        argv: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = arguments.get("argv", [])
        if not isinstance(argv, list) or any(
            not isinstance(item, str) for item in argv
        ):
            msg = "Exactus argv must be a list of strings."
            raise ValueError(msg)


def _validate_crawl_arguments(*, arguments: dict[str, JsonValue]) -> None:
    """Validate discovery policies and responsive environments.

    Args:
        arguments: Discovery tool arguments.

    Raises:
        ValueError: When a policy or browser environment is invalid.

    """
    for name in (
        "screenshots",
        "server_errors",
        "follow_links",
        "click_controls",
    ):
        if name in arguments and type(arguments[name]) is not bool:
            msg: str = f"{name} must be a boolean."
            raise ValueError(msg)
    for name, minimum, maximum in (
        ("port", 0, 65535),
        ("max_depth", 1, 10),
        ("max_states", 1, 200),
    ):
        if name in arguments:
            _bounded_integer(
                value=arguments[name],
                name=name,
                minimum=minimum,
                maximum=maximum,
            )
    for name in ("entrypoint", "include_selector"):
        if name in arguments and (
            not isinstance(arguments[name], str) or not arguments[name]
        ):
            msg = f"{name} must be a nonempty string."
            raise ValueError(msg)
    _validate_url(value=arguments.get("url", "http://127.0.0.1/"))
    scripts: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get("javascript", [])
    if not isinstance(scripts, list) or any(
        not isinstance(script, str) or not script.strip() for script in scripts
    ):
        msg = "JavaScript actions must be a list of nonempty expressions."
        raise ValueError(msg)
    matrix: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get(
        "environments",
        [{"width": 1440, "height": 900, "theme": "light"}],
    )
    if not isinstance(matrix, list) or not matrix:
        msg = "Discovery environments must be a nonempty list."
        raise ValueError(msg)
    for environment in matrix:
        _ = _environment(environment=environment)


def _validate_url(*, value: JsonValue) -> None:
    """Require a browser URL with a valid host and port.

    Args:
        value: Application URL.


    Raises:
        TypeError: When the URL is not a string.
        ValueError: When the URL scheme, host or credentials are invalid.

    """
    url: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = value
    if not isinstance(url, str):
        msg: str = "url must be an HTTP or HTTPS URL."
        raise TypeError(msg)
    parts: SplitResult = urlsplit(url=url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        msg = "url must be an HTTP or HTTPS URL without credentials."
        raise ValueError(msg)
    _ = parts.port


def _validate_references(*, value: JsonValue, known: set[str]) -> None:
    """Reject output references to later or nonexistent tool calls.

    Args:
        value: Nested argument value.
        known: Earlier action identifiers.

    Raises:
        ValueError: When a reference is unavailable.

    """
    if isinstance(value, str) and value.startswith("$"):
        name, separator, field = value[1:].partition(".")
        if not separator or not field or name not in known:
            msg: str = f"Unavailable action output reference: {value}"
            raise ValueError(msg)
    elif isinstance(value, dict):
        for item in value.values():
            _validate_references(value=item, known=known)
    elif isinstance(value, list):
        for item in value:
            _validate_references(value=item, known=known)


def _resolve(
    *,
    value: JsonValue,
    outputs: dict[str, dict[str, JsonValue]],
) -> JsonValue:
    """Resolve named tool outputs without shell interpolation.

    Args:
        value: Argument tree.
        outputs: Completed tool outputs.

    Returns:
        Resolved argument tree.

    """
    if isinstance(value, str) and value.startswith("$"):
        name, _, field = value[1:].partition(".")
        return outputs[name][field]
    if isinstance(value, dict):
        return {
            key: _resolve(value=item, outputs=outputs)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve(value=item, outputs=outputs) for item in value]
    return value


def _environment(
    *,
    environment: JsonValue,
) -> tuple[int, int, Literal["light", "dark"]]:
    """Validate one responsive execution environment.

    Args:
        environment: Width, height and color scheme.

    Returns:
        Browser dimensions and preferred color scheme.

    Raises:
        TypeError: When the environment is not an object.
        ValueError: When dimensions or theme are invalid.

    """
    if not isinstance(environment, dict):
        msg: str = "Each discovery environment must be an object."
        raise TypeError(msg)
    if set(environment) - {"width", "height", "theme"}:
        msg = "Environment fields are width, height and theme."
        raise ValueError(msg)
    _bounded_integer(
        value=environment.get("width", 1440),
        name="width",
        minimum=1,
        maximum=16384,
    )
    _bounded_integer(
        value=environment.get("height", 900),
        name="height",
        minimum=1,
        maximum=16384,
    )
    width: int = cast(typ="int", val=environment.get("width", 1440))
    height: int = cast(typ="int", val=environment.get("height", 900))
    theme: JsonValue = environment.get("theme", "light")
    if min(width, height) <= 0 or theme not in {"light", "dark"}:
        msg = "Use positive viewport dimensions and light/dark themes."
        raise ValueError(msg)
    return (width, height, cast(typ='Literal["light", "dark"]', val=theme))


def _collect(
    event: dict[str, JsonValue],
    *,
    events: list[dict[str, JsonValue]],
    emit: Callable[[dict[str, JsonValue]], None],
) -> None:
    """Retain discovery evidence and forward live progress.

    Args:
        event: Discovery message.
        events: Accumulated messages.
        emit: Progress observer.

    """
    events.append(event)
    emit(event)


@_group_final_final
class Constants:
    """Group module-level constants.

    Attributes:
        mobile_max_width: Grouped module constant.

    """

    mobile_max_width: Final[int] = 600


def _append_javascript(*, flow: Flow, scripts: list[str]) -> Flow:
    """Append evaluations after all events, including slow captures.

    Args:
        flow: Discovered flow with real elapsed timestamps.
        scripts: Evaluations to execute in their configured order.

    Returns:
        Flow with evaluations strictly after the captured timeline.

    """
    sequence: list[TimelineEvent] = list(flow.events)
    elapsed_ms: int = max((event.elapsed_ms for event in sequence), default=0)
    for script_index, script in enumerate(iterable=scripts):
        elapsed_ms += 500
        sequence.append(
            TimelineEvent(
                event_id=f"{flow.flow_id}-js-{script_index}",
                flow_id=flow.flow_id,
                sequence=len(sequence),
                elapsed_ms=elapsed_ms,
                layer=TimelineLayer.INTERACTION,
                kind=EventKind.JAVASCRIPT,
                label=f"JavaScript evaluation {script_index + 1}",
                payload=script,
            ),
        )
    return replace(flow, events=tuple(sequence))


def _crawl(
    *,
    arguments: dict[str, JsonValue],
    output: Path,
    url: str,
    cancelled: Callable[[], bool],
    emit: Callable[[dict[str, JsonValue]], None],
) -> dict[str, JsonValue]:
    """Generate ordinary Studio projects for each requested environment.

    Args:
        arguments: Discovery policy and browser matrix.
        output: Owned discovery artifacts.
        url: Application URL.
        cancelled: Cooperative cancellation predicate.
        emit: Progress callback.

    Returns:
        Generated projects with their replay environments.

    Raises:
        ValueError: When a matrix or JavaScript configuration is invalid.

    """
    matrix: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get(
        "environments",
        [{"width": 1440, "height": 900, "theme": "light"}],
    )
    if not isinstance(matrix, list) or not matrix:
        msg: str = "Discovery environments must be a nonempty list."
        raise ValueError(msg)
    scripts: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get("javascript", [])
    if not isinstance(scripts, list) or any(
        not isinstance(script, str) for script in scripts
    ):
        msg = "JavaScript actions must be a list of expressions."
        raise ValueError(msg)
    projects: list[JsonValue] = []
    for index, environment in enumerate(iterable=matrix):
        if cancelled():
            break
        width, height, theme = _environment(environment=environment)
        name: str = f"{index + 1}-{width}x{height}-{theme}"
        lane: Path = output / name
        events: list[dict[str, JsonValue]] = []
        async_run(
            main=discover(
                options=ExplorerOptions(
                    url=url,
                    output=lane,
                    max_depth=int(str(object=arguments.get("max_depth", 2))),
                    max_states=int(
                        str(object=arguments.get("max_states", 20)),
                    ),
                    capture_ui_changes=arguments.get("screenshots", True)
                    is True,
                    follow_links=arguments.get("follow_links", True) is True,
                    click_controls=arguments.get("click_controls", True)
                    is True,
                    include_selector=str(
                        object=arguments.get("include_selector") or "",
                    )
                    or None,
                    variant=CaptureVariant(
                        name=name,
                        width=width,
                        height=height,
                        color_scheme=theme,
                        is_mobile=width <= Constants.mobile_max_width,
                        has_touch=width <= Constants.mobile_max_width,
                        scale=1,
                    ),
                ),
                cancelled=cancelled,
                emit=partial(_collect, events=events, emit=emit),
            ),
        )
        final: dict[str, JsonValue] | None = next(
            (
                event
                for event in reversed(events)
                if event.get("type") == "crawl_result"
            ),
            None,
        )
        emit(
            {
                "type": "frontend_progress",
                "completed": index + 1,
                "total": len(matrix),
                "step": "Discover browser environments",
                "detail": name,
            },
        )
        if final is None:
            continue
        document: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = final["workspace"]
        workspace: Workspace = WorkspaceCodec.from_json_value(value=document)
        workspace = replace(
            workspace,
            flows=tuple(
                _append_javascript(
                    flow=flow,
                    scripts=cast(typ="list[str]", val=scripts),
                )
                for flow in workspace.flows
            ),
        )
        path: Path = lane / "discovered.pwflow.json"
        updated: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = WorkspaceCodec.to_json_value(workspace=workspace)
        if isinstance(updated, dict) and isinstance(document, dict):
            updated["assets"] = document.get("assets", {})
            write_workspace(path=path, workspace=updated)
        projects.append(
            {
                "workspace": str(object=path),
                "width": width,
                "height": height,
                "theme": theme,
                "is_mobile": width <= Constants.mobile_max_width,
                "has_touch": width <= Constants.mobile_max_width,
                "name": name,
                "discovery_diagnostics": final.get("diagnostics", []),
            },
        )
    return {
        "projects": projects,
        "workspace": (
            projects[0]["workspace"]
            if projects and isinstance(projects[0], dict)
            else None
        ),
        "url": url,
    }


def _unique_findings(*, findings: list[JsonValue]) -> list[JsonValue]:
    """Group repeated browser/server errors while retaining failed flows.

    Args:
        findings: Findings across browser environments.

    Returns:
        One finding per diagnostic cause, plus every functional failure.

    """
    seen: set[tuple[str, str]] = set()
    result: list[JsonValue] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        key: tuple[str, str] = (
            str(object=finding.get("rule")),
            str(object=finding.get("message")),
        )
        if key[0] == "FLOW001" or key not in seen:
            result.append(finding)
            seen.add(key)
    return result


def _replay_progress(
    event: dict[str, JsonValue],
    *,
    emit: Callable[[dict[str, JsonValue]], None] | None,
    index: int,
    total: int,
) -> None:
    """Map replay steps into their project's slice of the Actions recipe.

    Args:
        event: Step progress message.
        emit: Optional observer.
        index: Current project's index.
        total: Number of browser projects.

    """
    if emit is None or event.get("type") != "frontend_progress":
        return
    completed: JsonValue = event.get("completed")
    count: JsonValue = event.get("total")
    fraction: JsonValue = event.get("fraction")
    if isinstance(completed, int) and isinstance(count, int):
        emit(
            {
                **event,
                "fraction": (
                    (
                        index + float(fraction)
                        if isinstance(fraction, (int, float))
                        else index + completed / max(count, 1)
                    )
                    / max(total, 1)
                ),
            },
        )


def _frontend(
    *,
    arguments: dict[str, JsonValue],
    output: Path,
    cancelled: Callable[[], bool],
    emit: Callable[[dict[str, JsonValue]], None] | None = None,
) -> dict[str, JsonValue]:
    """Execute generated projects using their saved browser environments.

    Args:
        arguments: Projects returned by discovery.
        output: Report destination.
        cancelled: Cooperative cancellation predicate.
        emit: Optional progress observer.

    Returns:
        Per-project frontend evidence and failure count.

    Raises:
        ValueError: When no generated projects are supplied.

    """
    projects: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get("projects")
    if not isinstance(projects, list) or not projects:
        msg: str = "frontend.run requires generated projects."
        raise ValueError(msg)
    reports: list[JsonValue] = []
    failures: int = 0
    for index, project in enumerate(iterable=projects):
        if cancelled():
            break
        if not isinstance(project, dict):
            continue
        lane: Path = output / str(object=index + 1)
        result: FrontendExactusResult = frontend(
            inputs=FrontendExactusInput(
                output=lane,
                workers=int(str(object=arguments.get("workers", 4))),
                cancelled=cancelled,
                emit=partial(
                    _replay_progress,
                    emit=emit,
                    index=index,
                    total=len(projects),
                ),
                workspace=Path(str(object=project["workspace"])),
                width=int(str(object=project["width"])),
                height=int(str(object=project["height"])),
                color_scheme=cast(
                    typ='Literal["dark", "light"]',
                    val=project["theme"],
                ),
                is_mobile=project.get("is_mobile") is True,
                has_touch=project.get("has_touch") is True,
                server_log=(
                    Path(str(object=arguments["server_log"]))
                    if arguments.get("server_log")
                    else None
                ),
            ),
        )
        if emit is not None:
            emit(
                {
                    "type": "frontend_progress",
                    "completed": index + 1,
                    "total": len(projects),
                    "step": "Replay workflows",
                },
            )
        data: dict[str, JsonValue] = report_data(result=result)
        data["discovery_diagnostics"] = project.get(
            "discovery_diagnostics",
            [],
        )
        findings: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=data.get("findings", []),
        )
        discovery_events: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = data.get("discovery_diagnostics", [])
        if isinstance(discovery_events, list):
            findings.extend(
                {
                    "rule": "FRONTEND001",
                    "severity": "error",
                    "file": f"{project.get('name')}: discovery",
                    "message": (
                        f"{event.get('category')}: {event.get('message')}"
                        f" {event.get('url')}"
                    ),
                }
                for event in discovery_events
                if isinstance(event, dict) and event.get("severity") == "error"
            )
        data["findings"] = _unique_findings(findings=findings)
        ReportBundle.write(
            paths=ReportPaths(
                markdown=lane / "result.md",
                json=lane / "result.json",
                web=lane / "result_web",
            ),
            analyzer="frontend",
            title=f"Frontend · {project.get('name')}",
            markdown="# Frontend execution\n",
            data=data,
        )
        reports.append(
            {
                "environment": project,
                "report": str(object=lane / "result_web" / "index.html"),
                "execution": data,
            },
        )
        failures += len(data["findings"])
    fail_on_findings: bool = arguments.get("fail_on_findings", True) is True
    return {
        "reports": reports,
        "findings": failures,
        "status": "failed" if failures and fail_on_findings else "succeeded",
    }


def _report_actions(*, output: Path, report: dict[str, JsonValue]) -> None:
    """Render one dynamic report across discovery and replay tools.

    Args:
        output: Orchestration artifact root.
        report: Completed tool calls and their outputs.

    """
    flows: list[JsonValue] = []
    evidence: list[JsonValue] = []
    findings: list[JsonValue] = []
    servers: list[JsonValue] = []
    outputs: dict[str, dict[str, JsonValue]] = cast(
        typ="dict[str, dict[str, JsonValue]]",
        val=report["outputs"],
    )
    for identity, result in outputs.items():
        reports: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = result.get("reports", [])
        if not isinstance(reports, list):
            continue
        for index, lane in enumerate(iterable=reports):
            if not isinstance(lane, dict):
                continue
            data: JsonValue | None = lane.get("execution")
            if not isinstance(data, dict):
                continue
            records: JsonValue = data.get("flows", [])
            if isinstance(records, list):
                flows.extend(
                    {
                        **flow,
                        "action_id": identity,
                        "artifact_root": (
                            f"../{identity}/{index + 1}/ARTIFACTS/RUN"
                        ),
                        "environment": lane.get("environment"),
                    }
                    for flow in records
                    if isinstance(flow, dict)
                )
            for key, target in [
                ("evidence", evidence),
                ("findings", findings),
                ("server_diagnostics", servers),
            ]:
                values: JsonValue = data.get(key, [])
                if isinstance(values, list):
                    target.extend(values)
    ReportBundle.write(
        paths=ReportPaths(
            markdown=output / "result.md",
            json=output / "result.json",
            web=output / "result_web",
        ),
        analyzer="frontend",
        title="Frontend execution",
        markdown="# Actions execution\n",
        data={
            **normalized_data(
                payload={
                    "status": (
                        "FAIL"
                        if report["status"] == "failed"
                        else (
                            "PASS"
                            if report["status"] == "succeeded"
                            else "CANCELLED"
                        )
                    ),
                    "actions": report["actions"],
                    "flows": flows,
                    "evidence": evidence,
                    "findings": _unique_findings(findings=findings),
                    "server_diagnostics": servers,
                },
                output=output,
            ),
            "status": (
                "FAIL"
                if report["status"] == "failed"
                else "PASS"
                if report["status"] == "succeeded"
                else "CANCELLED"
            ),
            "actions": report["actions"],
            "flows": flows,
            "evidence": evidence,
            "server_diagnostics": servers,
        },
    )


def _exactus_tool(
    *,
    name: str,
    arguments: dict[str, JsonValue],
    root: Path,
    output: Path,
) -> dict[str, JsonValue]:
    """Run one canonical tool through the existing isolated exactus API.

    Args:
        name: Canonical tool ID.
        arguments: CLI tokens in the argv field.
        root: Exactused project root.
        output: Owned tool output directory.

    Returns:
        Tool outcome and canonical report links.

    Raises:
        ValueError: When argv contains anything other than strings.

    """
    argv: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = arguments.get("argv", [])
    if not isinstance(argv, list) or any(
        not isinstance(token, str) for token in argv
    ):
        msg: str = "Canonical tool arguments require an argv list of strings."
        raise ValueError(msg)
    spec: ToolSpec = next(
        tool
        for tool in _GroupFinalConstants.exactus_catalog.tools()
        if tool.identifier == name
    )
    result: ToolRunResult = ExactusApi.run_tool(
        request=ToolRequest(
            identifier=name,
            project_root=root,
            output=output,
            arguments=(
                str(object=root),
                "-o",
                str(object=output),
                *cast(typ="list[str]", val=argv),
            ),
            run_id=uuid4().hex,
        ),
        spec=spec,
    )
    return {
        "status": "succeeded" if result.passed else "failed",
        "report": str(object=result.report_web),
        "result_json": str(object=result.report_json),
        "exit_code": result.exit_code,
    }


def _require_server(*, url: str, pid: int) -> None:
    """Require the owned application to accept browser connections.

    Args:
        url: Assigned application URL.
        pid: Server process created by this Actions run.

    Raises:
        RuntimeError: When the server fails to start.

    """
    if not wait_ready(url=url, pid=pid):
        msg: str = (
            "The Actions entrypoint did not start accepting connections."
        )
        raise RuntimeError(msg)


def run_actions(
    *,
    specification: dict[str, JsonValue],
    root: Path,
    output: Path,
    cancelled: Callable[[], bool] | None = None,
    emit: Callable[[dict[str, JsonValue]], None] | None = None,
) -> dict[str, JsonValue]:
    """Run ordered tools, retain their evidence and stop owned servers.

    Args:
        specification: Validated JSON/TOML action specification.
        root: Base directory for relative entrypoints.
        output: Destination for tool and orchestration artifacts.
        cancelled: Optional cooperative cancellation predicate.
        emit: Optional progress callback.


    Returns:
        Orchestration report preserving every completed tool result.

    """
    specification = validate_actions(value=specification)
    _ = clear_conflict_copies(root=root)
    stop: Callable[[], bool] = cancelled or (lambda: False)

    def publish(event: dict[str, JsonValue]) -> None:
        """Emit progress when an observer is attached.

        Args:
            event: Structured progress payload to forward.

        """
        if emit is not None:
            emit(event)

    outputs: dict[str, dict[str, JsonValue]] = {}
    steps: list[JsonValue] = []
    identity, tool = ("setup", "actions")
    processes: list[int] = []
    output.mkdir(parents=True, exist_ok=True)
    write_workspace(path=output / "actions.json", workspace=specification)
    try:
        for raw in cast(
            typ="list[dict[str, JsonValue]]",
            val=specification["actions"],
        ):
            if stop():
                break
            identity, tool = (str(object=raw["id"]), str(object=raw["tool"]))
            arguments: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=_resolve(value=raw.get("arguments", {}), outputs=outputs),
            )
            _validate_arguments(tool=tool, arguments=arguments)
            destination: Path = output / identity
            publish(
                event={
                    "type": "actions_state",
                    "state": "running",
                    "action_id": identity,
                    "tool": tool,
                },
            )
            if tool == "record.crawl":
                url: str = str(
                    object=arguments.get("url") or "http://127.0.0.1/",
                )
                log: Path = destination / "server.log"
                if arguments.get("entrypoint"):
                    path: Path = root / str(object=arguments["entrypoint"])
                    parts: SplitResult = urlsplit(url=url)
                    pid, port = start_entrypoint(
                        path=path,
                        log=log,
                        port=int(str(object=arguments.get("port", 0)))
                        or parts.port,
                    )
                    processes.append(pid)
                    url = urlunsplit(
                        components=(
                            parts.scheme,
                            f"{parts.hostname}:{port}",
                            parts.path,
                            parts.query,
                            parts.fragment,
                        ),
                    )
                    _require_server(url=url, pid=pid)
                result: dict[str, JsonValue] = _crawl(
                    arguments=arguments,
                    output=destination,
                    url=url,
                    cancelled=stop,
                    emit=publish,
                )
                result["server_log"] = (
                    str(object=log)
                    if log.is_file()
                    and arguments.get("server_errors", True) is True
                    else None
                )
            elif tool == "frontend.run":
                result = _frontend(
                    arguments=arguments,
                    output=destination,
                    cancelled=stop,
                    emit=publish,
                )
            else:
                result = _exactus_tool(
                    name=tool,
                    arguments=arguments,
                    root=root,
                    output=destination,
                )
            outputs[identity] = result
            steps.append(
                {
                    "id": identity,
                    "tool": tool,
                    "status": result.get("status", "succeeded"),
                    "result": result,
                },
            )
    except (RuntimeError, OSError, ValueError, TypeError, KeyError) as error:
        steps.append(
            {
                "id": identity,
                "tool": tool,
                "status": "failed",
                "error": str(object=error),
            },
        )
    finally:
        for pid in processes:
            terminate_tree(pid=pid)
    report: dict[str, JsonValue] = {
        "version": 1,
        "status": (
            "cancelled"
            if stop()
            else (
                "failed"
                if any(
                    isinstance(step, dict) and step.get("status") == "failed"
                    for step in steps
                )
                else "succeeded"
            )
        ),
        "actions": steps,
        "outputs": cast(typ="JsonValue", val=outputs),
    }
    write_workspace(path=output / "actions-result.json", workspace=report)
    _report_actions(output=output, report=report)
    publish(
        event={
            "type": "actions_state",
            "state": report["status"],
            "action_id": identity,
            "tool": tool,
            "report": str(object=output / "actions-result.json"),
        },
    )
    return report
