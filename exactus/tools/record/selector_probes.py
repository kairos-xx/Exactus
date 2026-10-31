# Copyright (c) 2026 Project contributors
"""Publish selector probes as variables for conditions."""

from __future__ import annotations

from dataclasses import dataclass
from re import Pattern
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

from exactus.tools.record.expressions import (
    ExpressionError,
    ExpressionEvaluator,
)
from exactus.tools.record.model import RuntimeVariable, ValueType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from exactus.tools.record.model import Workspace
    from exactus.tools.record.selector_resolver import (
        Resolution,
        ResolvedMatch,
        SelectorResolver,
    )
    from exactus.tools.record.selectors import SelectorDef


@final
class Constants:
    """Group module-level constants.

    Attributes:
        system_flow_succeeded: Grouped module constant.
        system_flow_failed: Grouped module constant.
        probe_details: Grouped module constant.
        probe_types: Grouped module constant.
        pattern: Grouped module constant.

    """

    system_flow_succeeded: Final[str] = "flow_succeeded"
    system_flow_failed: Final[str] = "flow_failed"
    probe_details: Final[dict[str, str]] = {
        "count": "How many elements match",
        "exists": "Whether anything matches",
        "visible": "Whether every match is visible",
        "text": "The text of the first match",
        "enabled": "Whether every match is enabled",
    }
    probe_types: Final[dict[str, str]] = {
        "count": "integer",
        "exists": "boolean",
        "visible": "boolean",
        "text": "string",
        "enabled": "boolean",
    }
    pattern: Final[Pattern[str]] = re_compile(
        pattern=(
            "\\bsel_([A-Za-z][A-Za-z0-9_]*?)_(count|exists|visible|text|enable"
            "d)\\b"
        ),
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeRef:
    """One probe variable a condition reads.

    Attributes:
        variable: Variable name, such as ``sel_card_count``.
        selector_name: Selector it reads from.
        probe: ``count``, ``exists``, ``visible``, ``text`` or ``enabled``.

    """

    variable: str
    selector_name: str
    probe: str


def probe_refs(*, conditions: Iterable[str]) -> tuple[ProbeRef, ...]:
    """Find the probe variables that conditions read.

    Args:
        conditions: Condition expressions.

    Returns:
        Each distinct probe once, in order of first use.

    """
    found: dict[str, ProbeRef] = {}
    for condition in conditions:
        for match in Constants.pattern.finditer(string=condition):
            variable: str = match.group(0)
            found.setdefault(
                variable,
                ProbeRef(
                    variable=variable,
                    selector_name=match.group(1),
                    probe=match.group(2),
                ),
            )
    return tuple(found.values())


def edge_probe_names(*, workspace: Workspace, flow_id: str) -> tuple[str, ...]:
    """Name the probes the connections leaving a flow read.

    Args:
        workspace: The project.
        flow_id: Flow whose outgoing connections are inspected.

    Returns:
        Probe variable names to measure when the flow ends.

    """
    return tuple(
        ref.variable
        for ref in probe_refs(
            conditions=(
                edge.condition_expression
                for edge in workspace.edges
                if edge.source_flow_id == flow_id and edge.condition_expression
            ),
        )
    )


def condition_vocabulary(*, workspace: Workspace) -> list[dict[str, str]]:
    """List the names a condition can use, for the editor's suggestions.

    Args:
        workspace: The project.

    Returns:
        One entry per name with its ``kind`` (``system``, ``probe`` or
        ``output``), its ``value_type`` (``string``, ``integer``, ``float``,
        ``boolean`` or ``json``) and a short ``detail`` the editor shows
        beside it. The editor type-checks conditions with the value types.

    """
    terms: list[dict[str, str]] = [
        {
            "name": Constants.system_flow_succeeded,
            "kind": "system",
            "value_type": "boolean",
            "detail": "The flow finished without a failure.",
        },
        {
            "name": Constants.system_flow_failed,
            "kind": "system",
            "value_type": "boolean",
            "detail": "The flow finished with a failure.",
        },
    ]
    for selector in workspace.selectors:
        terms.extend(
            (
                {
                    "name": f"sel_{selector.name}_{probe}",
                    "kind": "probe",
                    "value_type": Constants.probe_types[probe],
                    "detail": f"{detail} for the selector {selector.name}.",
                }
                for probe, detail in Constants.probe_details.items()
            ),
        )
    seen: set[str] = set()
    for flow in workspace.flows:
        for output in flow.outputs:
            if output.name in seen:
                continue
            seen.add(output.name)
            terms.append(
                {
                    "name": output.name,
                    "kind": "output",
                    "value_type": output.value_type.value,
                    "detail": f"Output of the flow {flow.name}.",
                },
            )
    return terms


def _value(*, probe: str, resolution: Resolution) -> RuntimeVariable:
    """Turn a resolution into one probe variable.

    Args:
        probe: Probe name.
        resolution: What the selector found.

    Returns:
        The variable, without its name filled in by the caller.

    """
    found: tuple[ResolvedMatch, ...] = resolution.matches
    flags: dict[str, bool] = {
        "visible": bool(found)
        and all(match.evidence.get("visible") is True for match in found),
        "enabled": bool(found)
        and all(match.evidence.get("enabled") is True for match in found),
        "exists": bool(found),
    }
    if probe == "count":
        return RuntimeVariable(
            name=probe,
            value_type=ValueType.INTEGER,
            value=len(found),
        )
    if probe == "text":
        text: object = found[0].evidence.get("text") if found else ""
        return RuntimeVariable(
            name=probe,
            value_type=ValueType.STRING,
            value=str(object=text),
        )
    return RuntimeVariable(
        name=probe,
        value_type=ValueType.BOOLEAN,
        value=flags[probe],
    )


def probe_variables(
    *,
    resolver: SelectorResolver,
    selectors: tuple[SelectorDef, ...],
    refs: Iterable[ProbeRef],
) -> tuple[RuntimeVariable, ...]:
    """Measure probes in the page.

    Each selector is sampled once, however many probes read it.

    Args:
        resolver: Resolver bound to the page.
        selectors: Stored selectors.
        refs: Probes to measure.

    Returns:
        One variable per probe.

    Raises:
        ValueError: When a probe names a selector that does not exist.

    """
    by_name: dict[str, SelectorDef] = {item.name: item for item in selectors}
    samples: dict[str, Resolution] = {}
    variables: list[RuntimeVariable] = []
    for ref in refs:
        selector: SelectorDef | None = by_name.get(ref.selector_name)
        if selector is None:
            msg: str = (
                f"{ref.variable} needs a selector named "
                f"{ref.selector_name!r}, and there is none."
            )
            raise ValueError(msg)
        if ref.selector_name not in samples:
            samples[ref.selector_name] = resolver.sample(
                expression=selector.expression,
            )
        measured: RuntimeVariable = _value(
            probe=ref.probe,
            resolution=samples[ref.selector_name],
        )
        variables.append(
            RuntimeVariable(
                name=ref.variable,
                value_type=measured.value_type,
                value=measured.value,
            ),
        )
    return tuple(variables)


def validate_condition(
    *,
    expression: str,
    selectors: tuple[SelectorDef, ...],
) -> None:
    """Check a condition before it is saved.

    Args:
        expression: Condition in the connection-condition language.
        selectors: Stored selectors, which the probes must refer to.

    Raises:
        ValueError: When the syntax is invalid or a probe names a selector
            that does not exist.

    """
    try:
        ExpressionEvaluator.validate(expression=expression)
    except ExpressionError as error:
        msg: str = f"Invalid condition: {error}"
        raise ValueError(msg) from error
    known: set[str] = {item.name for item in selectors}
    for ref in probe_refs(conditions=(expression,)):
        if ref.selector_name not in known:
            msg = (
                f"{ref.variable} needs a selector named "
                f"{ref.selector_name!r}, and there is none."
            )
            raise ValueError(msg)
