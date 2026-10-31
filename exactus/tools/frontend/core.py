# Copyright (c) 2026
"""Exactus saved Studio workflows with the shared functional test executor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from json import dumps
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Literal, cast

from exactus.packages.server.diagnostics import parse_server_log
from exactus.tools.common.cli import activate_exactus_tool_bundle
from exactus.tools.frontend.report import normalized_data

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue


@dataclass(frozen=True, slots=True)
class FrontendFinding:
    """Describe an execution or browser diagnostic failure.

    Attributes:
        rule: Stable finding rule.
        file: Flow or action producing the failure.
        message: Failure description.
        severity: Finding severity.
        line: One-based source line when captured.
        column: One-based source column when captured.
        function: Originating JavaScript function.
        stack: Available browser stack trace.
        flow: Workflow producing the failure.
        action: Action producing the failure.
        phase: Discovery or replay phase.
        category: Browser, server or workflow issue type.

    """

    rule: str
    file: str
    message: str
    severity: str = "error"
    line: int | None = None
    column: int | None = None
    function: str = ""
    stack: str = ""
    flow: str = ""
    action: str = ""
    phase: str = ""
    category: str = ""


@dataclass(frozen=True, slots=True)
class FrontendExactusInput:
    """Configure execution of a Studio project.

    Attributes:
        output: Destination for reports and requested screenshots.
        url: Optional initial application URL.
        workspace: Current Studio project; omit for a navigation-only flow.
        flow_id: Optional workflow entry point.
        width: Logical browser width.
        height: Logical browser height.
        scale: Screenshot device scale.
        timeout_ms: Browser action timeout.
        color_scheme: Browser light or dark preference.
        is_mobile: Enable mobile emulation.
        has_touch: Enable touch input.
        cancelled: Optional cooperative cancellation predicate.
        emit: Optional observer receiving replay progress.
        headless: Whether the browser runs without a visible window.
        server_log: Optional server diagnostic log.
        workers: Maximum concurrent independent workflow visits.

    """

    output: Path
    url: str | None = None
    workspace: Path | None = None
    flow_id: str | None = None
    width: int = 1440
    height: int = 1000
    scale: float = 1.0
    timeout_ms: float = 5000
    color_scheme: Literal["light", "dark"] = "light"
    is_mobile: bool = False
    has_touch: bool = False
    cancelled: Callable[[], bool] | None = None
    emit: Callable[[dict[str, JsonValue]], None] | None = None
    headless: bool = True
    server_log: Path | None = None
    workers: int = 4


@dataclass(frozen=True, slots=True)
class FrontendExactusResult:
    """Collect workflow execution and exactus findings.

    Attributes:
        findings: Browser, server and functional failures.
        options: Effective execution options.
        execution: Shared executor report with runs and step evidence.
        server_diagnostics: Serialized server diagnostic events.
        elapsed_seconds: Total execution duration.

    """

    findings: tuple[FrontendFinding, ...]
    options: FrontendExactusInput
    execution: dict[str, JsonValue]
    server_diagnostics: tuple[JsonValue, ...]
    elapsed_seconds: float


def _execution_findings(
    *,
    execution: dict[str, JsonValue],
) -> list[FrontendFinding]:
    """Collect failures while preserving independent workflow outcomes.

    Args:
        execution: Shared functional execution report.

    Returns:
        Functional failures and action-attributed browser errors.

    """
    findings: list[FrontendFinding] = []
    flows: JsonValue | None = execution.get("flows", [])
    if isinstance(flows, list):
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            identity: str = str(object=flow.get("flow_id", "flow"))
            if flow.get("status") == "failed":
                findings.append(
                    FrontendFinding(
                        rule="FLOW001",
                        file=identity,
                        flow=identity,
                        category="workflow",
                        message=str(
                            object=flow.get("error") or "Workflow failed",
                        ),
                    ),
                )
            diagnostics: JsonValue | None = flow.get("diagnostics", [])
            if isinstance(diagnostics, list):
                for event in diagnostics:
                    if (
                        isinstance(event, dict)
                        and event.get("severity") == "error"
                    ):
                        target: JsonValue | None = event.get(
                            "action",
                        ) or event.get("phase")
                        detail: str = (
                            f"{event.get('message')} {event.get('url')}"
                        )
                        source_line: JsonValue = event.get("line")
                        source_column: JsonValue = event.get("column")
                        findings.append(
                            FrontendFinding(
                                rule="FRONTEND001",
                                file=str(
                                    object=event.get("file")
                                    or f"{identity}: {target}",
                                ),
                                message=f"{event.get('category')}: {detail}",
                                flow=identity,
                                action=str(object=event.get("action") or ""),
                                phase=str(object=event.get("phase") or ""),
                                category=str(
                                    object=event.get("category") or "",
                                ),
                                line=source_line
                                if isinstance(source_line, int)
                                else None,
                                column=source_column
                                if isinstance(source_column, int)
                                else None,
                                function=str(object=event.get("function", "")),
                                stack=str(object=event.get("stack", "")),
                            ),
                        )
    return findings


def frontend(*, inputs: FrontendExactusInput) -> FrontendExactusResult:
    """Execute saved flows and capture only their requested screenshots.

    Args:
        inputs: Project and browser execution options.

    Returns:
        Functional results and attributed diagnostics.

    Raises:
        ValueError: When neither a project nor a URL is provided.

    """
    if inputs.workspace is None and not inputs.url:
        msg: str = "Provide a Studio workspace or application URL."
        raise ValueError(msg)
    started: float = monotonic()
    _ = activate_exactus_tool_bundle(root=Path(__file__).resolve().parents[3])
    runner: ModuleType = import_module(name="exactus.tools.record.run")
    actions: ModuleType = import_module(
        name="exactus.tools.record.workspace_actions",
    )
    path: Path | None = inputs.workspace
    if path is None:
        path = inputs.output / "ARTIFACTS" / "navigation.pwflow.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        document: dict[str, JsonValue] = actions.build_workspace(
            flows=[
                actions.build_flow(
                    events=actions.actions_to_events(
                        actions=[{"type": "navigation", "url": inputs.url}],
                        flow_id="navigation",
                    ),
                    flow_id="navigation",
                    name="Application navigation",
                ),
            ],
        )
        path.write_text(
            data=dumps(obj=document, indent=2) + "\n",
            encoding="utf-8",
        )
    execution: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=runner.run_workspace(
            path=path,
            output=inputs.output / "ARTIFACTS" / "RUN",
            flow_id=inputs.flow_id,
            url=inputs.url if inputs.workspace is not None else None,
            browser=runner.BrowserOptions(
                width=inputs.width,
                height=inputs.height,
                scale=inputs.scale,
                timeout_ms=inputs.timeout_ms,
                color_scheme=inputs.color_scheme,
                is_mobile=inputs.is_mobile,
                has_touch=inputs.has_touch,
                cancelled=inputs.cancelled,
                emit=inputs.emit,
                headless=inputs.headless,
                workers=inputs.workers,
            ),
        ),
    )
    findings: list[FrontendFinding] = _execution_findings(execution=execution)
    saved_server: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = execution.get("server_diagnostics", [])
    server = tuple(saved_server) if isinstance(saved_server, list) else ()
    server: tuple[JsonValue, ...]
    server += (
        tuple(
            cast(typ="JsonValue", val=asdict(obj=event))
            for event in parse_server_log(path=inputs.server_log)
        )
        if inputs.server_log is not None
        else ()
    )
    findings.extend(
        FrontendFinding(
            rule="FRONTEND001",
            file="server",
            category="server",
            message=str(object=event.get("line")),
        )
        for event in server
        if isinstance(event, dict) and event.get("severity") == "error"
    )
    return FrontendExactusResult(
        findings=tuple(findings),
        options=inputs,
        execution=execution,
        server_diagnostics=server,
        elapsed_seconds=round(number=monotonic() - started, ndigits=3),
    )


def report_data(*, result: FrontendExactusResult) -> dict[str, JsonValue]:
    """Build dynamic report data from the shared execution evidence.

    Args:
        result: Completed frontend exactus.

    Returns:
        Structured flows, actions, diagnostics and requested artifacts.

    """
    payload: dict[str, JsonValue] = {
        **result.execution,
        "execution_status": result.execution["status"],
        "status": "CANCELLED"
        if result.execution["status"] == "cancelled"
        else "FAIL"
        if result.findings
        else "PASS",
        "url": result.options.url,
        "workspace": str(object=result.options.workspace)
        if result.options.workspace is not None
        else None,
        "viewport": {
            "width": result.options.width,
            "height": result.options.height,
            "scale": result.options.scale,
        },
        "elapsed_seconds": result.elapsed_seconds,
        "server_diagnostics": list(result.server_diagnostics),
        "findings": [
            cast(typ="JsonValue", val=asdict(obj=finding))
            for finding in result.findings
        ],
        "artifact_root": "../ARTIFACTS/RUN",
    }
    payload.update(
        normalized_data(payload=payload, output=result.options.output),
    )
    return payload


def markdown_report(*, result: FrontendExactusResult) -> str:
    """Render execution results with JavaScript responses and assertions.

    Args:
        result: Completed frontend exactus.

    Returns:
        Human-readable workflow report.


    """
    lines: list[str] = [
        "# Frontend Exactus",
        "",
        f"Findings: **{len(result.findings)}**",
        "",
        "Screenshots follow the capture policy saved in each flow.",
        "",
    ]
    flows: (
        bool
        | dict[str, JsonValue]
        | float
        | int
        | list[JsonValue]
        | str
        | None
    ) = result.execution.get("flows", [])
    if isinstance(flows, list):
        for flow in flows:
            if not isinstance(flow, dict):
                continue
            lines.extend(
                [
                    f"## {flow.get('flow_id')} — {flow.get('status')}",
                    "",
                    f"Run: `{flow.get('run_id', '')}`",
                    "",
                ],
            )
            records: JsonValue = flow.get("action_records", [])
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        label: JsonValue | None = record.get(
                            "label",
                        ) or record.get("event_id")
                        lines.extend(
                            [
                                f"### {label} — {record.get('status')}",
                                "",
                                "```json",
                                dumps(obj=record, indent=2),
                                "```",
                                "",
                            ],
                        )
    lines.extend(
        f"- **{finding.file}** {finding.message}"
        for finding in result.findings
    )
    return "\n".join(lines) + "\n"
