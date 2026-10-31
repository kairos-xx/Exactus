# Copyright (c) 2026 Project contributors
"""Run JavaScript actions in the isolated sandbox with run-wide streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tools.record.selector_engine import world_for

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.selectors import SelectorDef


@final
class Constants:
    """Group module-level constants.

    Attributes:
        history_keys: Grouped module constant.

    """

    history_keys: Final[dict[str, str]] = {
        "log": "logs",
        "warn": "warnings",
        "error": "errors",
    }


@cache
def sandbox_function() -> str:
    """Return the script that runs a snippet in the sandbox.

    Returns:
        JavaScript source of an async function taking one JSON argument.

    """
    return (
        files(anchor="exactus.tools.record")
        .joinpath("selector_sandbox.js")
        .read_text(encoding="utf-8")
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class StreamEntry:
    """One line written to the run streams.

    Attributes:
        level: ``log``, ``warn`` or ``error``.
        source: ``tool`` or ``snippet``.
        message: Text of the entry.
        flow_id: Flow that produced it.
        action_id: Action that produced it.
        unit: Target position, when the action has several targets.
        cause: Structured failure cause, for tool errors.
        at: Epoch milliseconds, when known.

    """

    level: str
    source: str
    message: str
    flow_id: str
    action_id: str
    unit: int | None = None
    cause: dict[str, JsonValue] | None = None
    at: int = 0


@final
@dataclass(slots=True)
class RunStreams:
    """Logs, warnings, errors and variables shared by one run's actions.

    The Python run is authoritative. The sandbox receives a copy before each
    snippet and hands back what it added, because a navigation destroys the
    page's JavaScript world.

    Attributes:
        entries: Every entry in the order it happened.
        vars: Values snippets keep between actions.

    """

    entries: list[dict[str, JsonValue]] = field(default_factory=list)
    vars: dict[str, JsonValue] = field(default_factory=dict)

    def add(self, *, entry: StreamEntry) -> dict[str, JsonValue]:
        """Append one entry.

        Args:
            entry: What to record.

        Returns:
            The stored entry, with its sequence number.

        """
        stored: dict[str, JsonValue] = {
            "seq": len(self.entries),
            "at": entry.at,
            "level": entry.level,
            "source": entry.source,
            "message": entry.message,
            "flow_id": entry.flow_id,
            "action_id": entry.action_id,
            "unit": entry.unit,
            "cause": entry.cause,
        }
        self.entries.append(stored)
        return stored

    def history(self) -> dict[str, JsonValue]:
        """Return the streams in the shape the sandbox reads them.

        Returns:
            ``logs``, ``warnings`` and ``errors`` lists of entries.

        """
        shaped: dict[str, JsonValue] = {
            key: [] for key in Constants.history_keys.values()
        }
        for entry in self.entries:
            key: str = Constants.history_keys.get(
                str(object=entry["level"]),
                "logs",
            )
            cast(typ="list[JsonValue]", val=shaped[key]).append(entry)
        return shaped


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SandboxCall:
    """Describe one snippet run.

    Attributes:
        script: Snippet source: an expression or a function body.
        flow_id: Flow the action belongs to.
        action_id: The action.
        run_id: The run.
        targets: CSS of every target of the action, in order.
        indices: Which targets to run on, all at the same time.
        count: Number of targets, when the action has several.
        flow_name: Flow name.
        action_kind: Action kind.
        action_label: Action label.
        project_id: Project id.
        project_name: Project name.
        project_revision: Project revision.
        context_id: Context id.
        context_name: Context name.
        context_base_url: Context base URL.
        context_origin: Context origin.

    """

    script: str
    flow_id: str
    action_id: str
    run_id: str
    targets: tuple[str, ...] = ()
    indices: tuple[int, ...] = (0,)
    count: int | None = None
    flow_name: str = ""
    action_kind: str = ""
    action_label: str = ""
    project_id: str = ""
    project_name: str = ""
    project_revision: str = ""
    context_id: str = ""
    context_name: str = ""
    context_base_url: str = ""
    context_origin: str = ""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SandboxResult:
    """The outcome of a snippet on one target.

    Attributes:
        index: Target position the snippet ran on.
        value: The snippet's JSON result.
        error: First line of the error it threw, if it threw.
        entries: Log, warning and error calls it made.

    """

    index: int
    value: JsonValue
    error: str | None
    entries: tuple[dict[str, JsonValue], ...]


def run_sandbox(
    *,
    page: Page,
    call: SandboxCall,
    streams: RunStreams,
    selectors: tuple[SelectorDef, ...] = (),
) -> tuple[SandboxResult, ...]:
    """Run a snippet in the page's isolated world.

    The streams' variables are updated at once. Log entries are returned, not
    stored, so each action can attach exactly the entries it produced; call
    ``merge`` when the action runs.

    Args:
        page: Page whose isolated world runs the snippet.
        call: What to run and on which targets.
        streams: Run-wide streams, read for history and variables.
        selectors: Stored selectors, so their names resolve.

    Returns:
        One result per requested target index.

    """
    history: dict[str, JsonValue] = streams.history()
    raw: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=world_for(page=page).call(
            function=sandbox_function(),
            argument={
                "script": call.script,
                "definitions": {
                    item.name: item.expression for item in selectors
                },
                "vars": streams.vars,
                "logs": history["logs"],
                "warnings": history["warnings"],
                "errors": history["errors"],
                "flowId": call.flow_id,
                "actionId": call.action_id,
                "runId": call.run_id,
                "targets": list(call.targets),
                "indices": list(call.indices),
                "count": call.count,
                "flowName": call.flow_name,
                "actionKind": call.action_kind,
                "actionLabel": call.action_label,
                "project": {
                    "id": call.project_id,
                    "name": call.project_name,
                    "revision": call.project_revision,
                },
                "context": {
                    "id": call.context_id,
                    "name": call.context_name,
                    "baseUrl": call.context_base_url,
                    "origin": call.context_origin,
                },
            },
        ),
    )
    streams.vars = cast(typ="dict[str, JsonValue]", val=raw["vars"])
    items: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=raw["results"],
    )
    return tuple(
        SandboxResult(
            index=cast(typ="int", val=item["index"]),
            value=item["value"],
            error=cast(typ="str | None", val=item["error"]),
            entries=tuple(
                cast(typ="list[dict[str, JsonValue]]", val=item["out"]),
            ),
        )
        for item in items
    )


def merge(
    *,
    streams: RunStreams,
    result: SandboxResult,
    flow_id: str,
    action_id: str,
    unit: int | None,
) -> None:
    """Store the entries a snippet produced in the run's streams.

    Args:
        streams: Run-wide streams.
        result: Outcome of the snippet on one target.
        flow_id: Flow the action belongs to.
        action_id: The action.
        unit: Target position, when the action has several targets.

    """
    for entry in result.entries:
        _ = streams.add(
            entry=StreamEntry(
                level=str(object=entry["level"]),
                source="snippet",
                message=str(object=entry["message"]),
                flow_id=flow_id,
                action_id=action_id,
                unit=unit,
                at=cast(typ="int", val=entry["at"]),
            ),
        )
