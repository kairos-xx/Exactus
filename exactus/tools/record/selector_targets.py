# Copyright (c) 2026 Project contributors
"""Turn an action's selector reference into the targets it will act on."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final, cast, final

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from exactus.tools.record.model import EventKind
from exactus.tools.record.selector_resolver import Resolution, SelectorResolver
from exactus.tools.record.selectors import RunMode, SelectorDef, TargetScope

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import TimelineEvent
    from exactus.tools.record.selector_resolver import ResolvedMatch


@final
class Constants:
    """Group module-level constants.

    Attributes:
        inline_prefix: Grouped module constant.

    """

    inline_prefix: Final[str] = "ext="


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Unit:
    """One target of an action: the action with a concrete CSS selector.

    Attributes:
        event: The action to run, its selector already resolved.
        index: Position among the action's targets, when it has several.
        count: Number of targets, when the action expanded to several.
        cause: Why resolution failed; the unit then must not run.
        selector_id: Stored selector the target came from, if any.
        targets: CSS of every target of the action, in order.
        position: This unit's place within ``targets``.
        evidence: What the page reported about the element: tag, role, text,
            visibility, attributes and its viewport rectangle.

    """

    event: TimelineEvent
    index: int | None = None
    count: int | None = None
    cause: dict[str, JsonValue] | None = None
    selector_id: str | None = None
    targets: tuple[str, ...] = ()
    position: int = 0
    evidence: dict[str, JsonValue] | None = None


def needs_planning(*, event: TimelineEvent) -> bool:
    """Tell whether an action's selector must be resolved before running.

    Args:
        event: The action.

    Returns:
        True for stored selectors, ``ext=`` expressions and ``all`` targets.

    """
    return bool(
        event.selector_id
        or (event.selector or "").startswith(Constants.inline_prefix)
        or event.targets is TargetScope.ALL
        or (event.kind is EventKind.SNAPSHOT),
    )


def failure_cause(
    *,
    failure: Exception,
    unit: Unit,
    stage: str,
) -> dict[str, JsonValue]:
    """Describe why running a target failed.

    Args:
        failure: The exception that stopped the action.
        unit: The target that was running.
        stage: ``check`` for contract assertions, else ``execute``.

    Returns:
        A structured cause with the phase, message and resolved CSS.

    """
    phase: str = stage
    if isinstance(failure, PlaywrightTimeoutError):
        phase = "timeout"
    cause: dict[str, JsonValue] = {
        "phase": phase,
        "message": str(object=failure).splitlines()[0],
        "resolved_css": unit.event.selector,
        "target_index": unit.index,
        "selector_id": unit.selector_id,
    }
    if isinstance(failure, PlaywrightError):
        cause["playwright_error"] = str(object=failure)
    return cause


@final
class TargetPlanner:
    """Resolve each action's selector into the targets to run."""

    def __init__(
        self,
        *,
        page: Page,
        selectors: tuple[SelectorDef, ...],
        timeout_ms: int,
    ) -> None:
        """Bind the planner to a page and the project's selectors.

        Args:
            page: Page the actions run in.
            selectors: Stored selectors.
            timeout_ms: Longest wait for a selector to resolve.

        """
        self._page: Page = page
        self._selectors: tuple[SelectorDef, ...] = selectors
        self._resolver: SelectorResolver = SelectorResolver(
            page=page,
            selectors=selectors,
            timeout_ms=timeout_ms,
        )

    def plan(self, *, event: TimelineEvent) -> tuple[Unit, ...]:
        """Return the targets an action will run on.

        Args:
            event: The action.

        Returns:
            One unit per target. A unit carrying a cause means the selector
            could not be resolved and the action must fail with that cause.

        """
        if not needs_planning(event=event):
            return (Unit(event=event),)
        if event.selector_id:
            return self._stored(event=event)
        selector: str = event.selector or ""
        if (
            selector.startswith(Constants.inline_prefix)
            or event.kind is EventKind.SNAPSHOT
        ):
            return self._resolved(
                event=event,
                resolution=self._resolver.resolve(
                    expression=selector.removeprefix(Constants.inline_prefix),
                    expected_count=None,
                ),
                selector_id=None,
            )
        return self._plain(event=event)

    @staticmethod
    def _concrete(*, event: TimelineEvent, css: str) -> TimelineEvent:
        """Return the action pinned to one concrete selector.

        Args:
            event: The planned action.
            css: Selector that finds exactly one element.

        Returns:
            The action with targeting settings reset.

        """
        return replace(
            event,
            selector=css,
            selector_id=None,
            targets=TargetScope.FIRST,
            run_mode=RunMode.SEQUENTIAL,
            pace_between=None,
        )

    def _stored(self, *, event: TimelineEvent) -> tuple[Unit, ...]:
        """Plan an action that targets a stored selector.

        Args:
            event: The action.

        Returns:
            The planned targets.

        """
        stored: SelectorDef | None = next(
            (
                item
                for item in self._selectors
                if item.selector_id == event.selector_id
            ),
            None,
        )
        if stored is None:
            return (
                Unit(
                    event=event,
                    cause={
                        "phase": "resolve",
                        "message": f"Unknown selector: {event.selector_id}",
                        "selector_id": event.selector_id,
                    },
                    selector_id=event.selector_id,
                ),
            )
        return self._resolved(
            event=event,
            resolution=self._resolver.resolve_selector(selector=stored),
            selector_id=stored.selector_id,
        )

    def _resolved(
        self,
        *,
        event: TimelineEvent,
        resolution: Resolution,
        selector_id: str | None,
    ) -> tuple[Unit, ...]:
        """Turn a resolution into units.

        Args:
            event: The action.
            resolution: What the page reported.
            selector_id: Stored selector it came from, if any.

        Returns:
            One unit per target, or one failed unit.

        """
        if not resolution.ok:
            return (
                Unit(
                    event=event,
                    cause={**resolution.cause(), "selector_id": selector_id},
                    selector_id=selector_id,
                ),
            )
        matches: tuple[ResolvedMatch, ...] = (
            resolution.matches
            if event.targets is TargetScope.ALL
            else resolution.matches[:1]
        )
        several: bool = event.targets is TargetScope.ALL
        everything: tuple[str, ...] = tuple(
            match.css or "" for match in resolution.matches
        )
        return tuple(
            Unit(
                event=self._concrete(event=event, css=match.css or ""),
                index=match.index if several else None,
                count=len(matches) if several else None,
                selector_id=selector_id,
                targets=everything,
                position=match.index,
                evidence={
                    **match.evidence,
                    "rect": cast(typ="JsonValue", val=dict(match.rect)),
                },
            )
            for match in matches
        )

    def _plain(self, *, event: TimelineEvent) -> tuple[Unit, ...]:
        """Expand a Playwright selector with ``all`` targets.

        Args:
            event: The action.

        Returns:
            One unit per element, addressed with ``nth=``.

        """
        selector: str = cast(typ="str", val=event.selector)
        found: int = self._page.locator(selector=selector).count()
        if found == 0:
            return (
                Unit(
                    event=event,
                    cause={
                        "phase": "count",
                        "message": "Expected one or more, found 0.",
                        "expression": selector,
                        "found_count": 0,
                    },
                ),
            )
        everything: tuple[str, ...] = tuple(
            f"{selector} >> nth={index}" for index in range(found)
        )
        return tuple(
            Unit(
                event=self._concrete(event=event, css=everything[index]),
                index=index,
                count=found,
                targets=everything,
                position=index,
            )
            for index in range(found)
        )
