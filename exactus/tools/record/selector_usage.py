# Copyright (c) 2026 Project contributors
"""Find where selectors are used, and keep references valid on rename."""

from __future__ import annotations

from dataclasses import dataclass, replace
from re import Pattern, escape
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from exactus.tools.record.model import (
        ActionContract,
        Flow,
        FlowEdge,
        TimelineEvent,
        Workspace,
    )
    from exactus.tools.record.selectors import Pace, SelectorDef


@final
class Constants:
    """Group module-level constants.

    Attributes:
        probes: Grouped module constant.
        name_reference: Grouped module constant.
        probe_reference: Grouped module constant.

    """

    probes: Final[tuple[str, ...]] = (
        "count",
        "exists",
        "visible",
        "text",
        "enabled",
    )
    name_reference: Final[Pattern[str]] = re_compile(
        pattern="\\[extended-selector=([\"'])([A-Za-z][A-Za-z0-9_]*)\\1\\]",
    )
    probe_reference: Final[Pattern[str]] = re_compile(
        pattern=(
            "\\bsel_([A-Za-z][A-Za-z0-9_]*?)_(?:count|exists|visible|text|enab"
            "led)\\b"
        ),
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class SelectorUsage:
    """Describe everything that depends on one selector.

    Attributes:
        selector_id: The selector.
        actions: ``(flow_id, event_id)`` of every action that targets it.
        selectors: Identifiers of selectors whose expression names it.
        conditions: Pace and connection conditions that read its probes.

    """

    selector_id: str
    actions: tuple[tuple[str, str], ...] = ()
    selectors: tuple[str, ...] = ()
    conditions: int = 0

    @property
    def flow_count(self) -> int:
        """Return how many flows contain an action that targets it.

        Returns:
            Number of distinct flows.

        """
        return len({flow_id for flow_id, _ in self.actions})

    @property
    def in_use(self) -> bool:
        """Return whether anything depends on the selector.

        Returns:
            True when an action, selector or condition refers to it.

        """
        return bool(self.actions or self.selectors or self.conditions)


def referenced_names(*, expression: str) -> frozenset[str]:
    """Return the selector names an expression refers to.

    Args:
        expression: ExtendedSelector expression.

    Returns:
        Names used as ``[extended-selector="name"]``.

    """
    return frozenset(
        match.group(2)
        for match in Constants.name_reference.finditer(string=expression)
    )


def probe_names(*, condition: str) -> frozenset[str]:
    """Return the selector names a condition reads probes from.

    Args:
        condition: Condition expression.

    Returns:
        Names used as ``sel_<name>_<probe>``.

    """
    return frozenset(
        match.group(1)
        for match in Constants.probe_reference.finditer(string=condition)
    )


def _conditions(*, flow: Flow, workspace: Workspace) -> list[str]:
    """Collect every condition string that can read selector probes.

    Args:
        flow: Flow whose actions are scanned.
        workspace: Project, for the connections leaving the flow.

    Returns:
        Pace conditions of the flow's actions and its outgoing connections.

    """
    paces: list[Pace | None] = [
        pace
        for event in flow.events
        for pace in (event.pace_between, event.contract.pace)
    ]
    found: list[str] = [pace.until for pace in paces if pace and pace.until]
    found.extend(
        edge.condition_expression
        for edge in workspace.edges
        if edge.source_flow_id == flow.flow_id and edge.condition_expression
    )
    return found


def _action_references(
    *,
    workspace: Workspace,
    by_name: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    """Find the actions that target each selector.

    Args:
        workspace: The project.
        by_name: Selector identifier for each selector name.

    Returns:
        ``(flow_id, event_id)`` pairs keyed by selector identifier. An action
        counts through ``selector_id`` and through names inside an ``ext=``
        inline selector.

    """
    found: dict[str, list[tuple[str, str]]] = {
        selector_id: [] for selector_id in by_name.values()
    }
    for flow in workspace.flows:
        for event in flow.events:
            targets: set[str | None] = {event.selector_id}
            if event.selector and event.selector.startswith("ext="):
                targets.update(
                    by_name.get(name)
                    for name in referenced_names(expression=event.selector)
                )
            for target in targets:
                if target in found:
                    found[target].append((flow.flow_id, event.event_id))
    return found


def _nested_references(
    *,
    workspace: Workspace,
    by_name: dict[str, str],
) -> dict[str, list[str]]:
    """Find the selectors whose expression names another selector.

    Args:
        workspace: The project.
        by_name: Selector identifier for each selector name.

    Returns:
        Identifiers of the referring selectors, keyed by referenced selector.

    """
    found: dict[str, list[str]] = {
        selector_id: [] for selector_id in by_name.values()
    }
    for item in workspace.selectors:
        for name in referenced_names(expression=item.expression):
            target: str | None = by_name.get(name)
            if target is not None and target != item.selector_id:
                found[target].append(item.selector_id)
    return found


def _condition_counts(
    *,
    workspace: Workspace,
    by_name: dict[str, str],
) -> dict[str, int]:
    """Count the conditions that read each selector's probes.

    Args:
        workspace: The project.
        by_name: Selector identifier for each selector name.

    Returns:
        Number of pace and connection conditions per selector identifier.

    """
    counts: dict[str, int] = dict.fromkeys(by_name.values(), 0)
    for flow in workspace.flows:
        for condition in _conditions(flow=flow, workspace=workspace):
            for name in probe_names(condition=condition):
                target: str | None = by_name.get(name)
                if target is not None:
                    counts[target] += 1
    return counts


def usage_index(*, workspace: Workspace) -> dict[str, SelectorUsage]:
    """Return what depends on each selector in a project.

    Args:
        workspace: The project.

    Returns:
        One entry per selector, keyed by identifier.

    """
    by_name: dict[str, str] = {
        item.name: item.selector_id for item in workspace.selectors
    }
    actions: dict[str, list[tuple[str, str]]] = _action_references(
        workspace=workspace,
        by_name=by_name,
    )
    nested: dict[str, list[str]] = _nested_references(
        workspace=workspace,
        by_name=by_name,
    )
    conditions: dict[str, int] = _condition_counts(
        workspace=workspace,
        by_name=by_name,
    )
    return {
        selector_id: SelectorUsage(
            selector_id=selector_id,
            actions=tuple(actions[selector_id]),
            selectors=tuple(nested[selector_id]),
            conditions=conditions[selector_id],
        )
        for selector_id in by_name.values()
    }


def dangling_references(
    *,
    workspace: Workspace,
) -> tuple[tuple[str, str, str], ...]:
    """Return actions that point at a selector that does not exist.

    Args:
        workspace: The project.

    Returns:
        ``(flow_id, event_id, selector_id)`` for every broken reference.

    """
    known: set[str] = {item.selector_id for item in workspace.selectors}
    return tuple(
        (flow.flow_id, event.event_id, event.selector_id)
        for flow in workspace.flows
        for event in flow.events
        if event.selector_id is not None and event.selector_id not in known
    )


def _rename_expression(*, text: str, old: str, new: str) -> str:
    """Rewrite selector-name references inside an expression.

    Args:
        text: ExtendedSelector expression.
        old: Previous selector name.
        new: New selector name.

    Returns:
        The expression with ``[extended-selector="old"]`` renamed.

    """
    return re_compile(
        pattern="\\[extended-selector=([\"'])"
        + escape(pattern=old)
        + "\\1\\]",
    ).sub(
        repl=lambda match: (
            f"[extended-selector={match.group(1)}{new}{match.group(1)}]"
        ),
        string=text,
    )


def _rename_condition(*, text: str, old: str, new: str) -> str:
    """Rewrite probe names inside a condition.

    Args:
        text: Condition expression.
        old: Previous selector name.
        new: New selector name.

    Returns:
        The condition with ``sel_old_<probe>`` renamed.

    """
    pattern: Pattern[str] = re_compile(
        pattern="\\bsel_"
        + escape(pattern=old)
        + "_("
        + "|".join(Constants.probes)
        + ")\\b",
    )
    return pattern.sub(
        repl=lambda match: f"sel_{new}_{match.group(1)}",
        string=text,
    )


def _rename_pace(*, pace: Pace | None, old: str, new: str) -> Pace | None:
    """Rename probes inside a pace condition.

    Args:
        pace: Pace to rewrite, or ``None``.
        old: Previous selector name.
        new: New selector name.

    Returns:
        The rewritten pace.

    """
    if pace is None or pace.until is None:
        return pace
    return replace(
        pace,
        until=_rename_condition(text=pace.until, old=old, new=new),
    )


def _rename_event(
    *,
    event: TimelineEvent,
    old: str,
    new: str,
) -> TimelineEvent:
    """Rename references inside one action.

    Args:
        event: Action to rewrite.
        old: Previous selector name.
        new: New selector name.

    Returns:
        The rewritten action.

    """
    contract: ActionContract = replace(
        event.contract,
        pace=_rename_pace(pace=event.contract.pace, old=old, new=new),
    )
    selector: str | None = event.selector
    if selector is not None and selector.startswith("ext="):
        selector = _rename_expression(text=selector, old=old, new=new)
    return replace(
        event,
        selector=selector,
        pace_between=_rename_pace(pace=event.pace_between, old=old, new=new),
        contract=contract,
    )


def rename_references(
    *,
    workspace: Workspace,
    selector_id: str,
    name: str,
) -> tuple[Workspace, tuple[str, ...]]:
    """Rename a selector and every reference that can be rewritten safely.

    Selector expressions, ``ext=`` inline selectors, pace conditions and
    connection conditions are rewritten. JavaScript snippets are code, so
    their actions are reported instead of edited.

    Args:
        workspace: The project.
        selector_id: Selector being renamed.
        name: Its new name.

    Returns:
        The updated project and the identifiers of sandbox JavaScript actions
        whose snippet mentions the old name.

    """
    old: str = next(
        item.name
        for item in workspace.selectors
        if item.selector_id == selector_id
    )
    selectors: tuple[SelectorDef, ...] = tuple(
        replace(item, name=name)
        if item.selector_id == selector_id
        else replace(
            item,
            expression=_rename_expression(
                text=item.expression,
                old=old,
                new=name,
            ),
        )
        for item in workspace.selectors
    )
    flagged: list[str] = []
    flows: list[Flow] = []
    for flow in workspace.flows:
        events: list[TimelineEvent] = []
        for event in flow.events:
            if event.sandbox and event.payload and (old in event.payload):
                flagged.append(event.event_id)
            events.append(_rename_event(event=event, old=old, new=name))
        flows.append(replace(flow, events=tuple(events)))
    edges: tuple[FlowEdge, ...] = tuple(
        replace(
            edge,
            condition_expression=_rename_condition(
                text=edge.condition_expression,
                old=old,
                new=name,
            ),
        )
        if edge.condition_expression
        else edge
        for edge in workspace.edges
    )
    return (
        replace(
            workspace,
            selectors=selectors,
            flows=tuple(flows),
            edges=edges,
        ),
        tuple(flagged),
    )
