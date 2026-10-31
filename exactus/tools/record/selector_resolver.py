# Copyright (c) 2026 Project contributors
"""Resolve stored selector expressions to CSS in the target page."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from time import monotonic
from typing import TYPE_CHECKING, cast, final

from exactus.tools.record.selector_engine import world_for

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.selectors import SelectorDef


@cache
def resolve_function() -> str:
    """Return the script that evaluates one expression in the page.

    Returns:
        JavaScript source of a function taking one JSON argument.

    """
    return (
        files(anchor="exactus.tools.record")
        .joinpath("selector_resolve.js")
        .read_text(encoding="utf-8")
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedMatch:
    """Describe one element a selector matched.

    Attributes:
        index: Position in the selector's own order.
        css: Exact CSS (or ``host >> inner`` chain) that finds only it.
        css_error: Why no CSS could be produced, when it could not.
        rect: Viewport rectangle: ``x``, ``y``, ``width``, ``height``.
        evidence: Tag, role, text, visibility and key attributes.
        failed_checks: Checks the element did not satisfy.

    """

    index: int
    css: str | None
    css_error: str | None
    rect: dict[str, float]
    evidence: dict[str, JsonValue]
    failed_checks: tuple[str, ...] = ()


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Resolution:
    """Describe the outcome of resolving one expression.

    Attributes:
        expression: The expression that was resolved.
        expected_count: Exact count required, or ``None`` for one or more.
        count: Number of elements found.
        matches: The matched elements, in the selector's order.
        error: Why the expression itself could not be evaluated.
        definition_errors: Stored selectors that could not be defined.
        elapsed_ms: Time spent, including polling.
        polls: Number of evaluations.

    """

    expression: str
    expected_count: int | None
    count: int
    matches: tuple[ResolvedMatch, ...]
    error: str | None = None
    definition_errors: tuple[str, ...] = ()
    elapsed_ms: int = 0
    polls: int = 1

    @property
    def count_ok(self) -> bool:
        """Return whether the match count is acceptable.

        Returns:
            True for the exact expected count, or one or more when none is
            expected.

        """
        if self.expected_count is None:
            return self.count >= 1
        return self.count == self.expected_count

    @property
    def checks_ok(self) -> bool:
        """Return whether every match satisfied every check.

        Returns:
            True when no match has a failed check.

        """
        return all(not match.failed_checks for match in self.matches)

    @property
    def css_ok(self) -> bool:
        """Return whether every match could be turned into CSS.

        Returns:
            True when each match has a CSS string.

        """
        return all(match.css for match in self.matches)

    @property
    def ok(self) -> bool:
        """Return whether the selector resolved cleanly.

        Returns:
            True when there is no error and count, checks and CSS are fine.

        """
        return (
            self.error is None
            and self.count_ok
            and self.checks_ok
            and self.css_ok
        )

    def cause(self) -> dict[str, JsonValue]:
        """Describe why the resolution failed.

        Returns:
            A structured cause: phase, expression, counts and the details of
            the first problem. Empty when the resolution succeeded.

        """
        if self.ok:
            return {}
        cause: dict[str, JsonValue] = {
            "expression": self.expression,
            "expected_count": self.expected_count,
            "found_count": self.count,
        }
        if self.error is not None:
            return {**cause, "phase": "resolve", "message": self.error}
        if not self.count_ok:
            expected: str = (
                "one or more"
                if self.expected_count is None
                else str(object=self.expected_count)
            )
            return {
                **cause,
                "phase": "count",
                "message": f"Expected {expected}, found {self.count}.",
            }
        if not self.checks_ok:
            failed: list[JsonValue] = [
                {"index": match.index, "checks": list(match.failed_checks)}
                for match in self.matches
                if match.failed_checks
            ]
            return {
                **cause,
                "phase": "check",
                "message": "A match failed its checks.",
                "failed": failed,
            }
        missing: ResolvedMatch = next(
            match for match in self.matches if not match.css
        )
        return {
            **cause,
            "phase": "compile",
            "message": missing.css_error or "No CSS for a match.",
            "target_index": missing.index,
        }


@final
class SelectorResolver:
    """Resolve expressions against one page, using the project's selectors."""

    def __init__(
        self,
        *,
        page: Page,
        selectors: tuple[SelectorDef, ...] = (),
        timeout_ms: int = 5000,
        poll_ms: int = 100,
    ) -> None:
        """Bind the resolver to a page and the stored selectors.

        Args:
            page: Page to search.
            selectors: Project selectors, so their names resolve in
                expressions.
            timeout_ms: Longest time to wait for the expected result.
            poll_ms: Interval between evaluations while waiting.

        """
        self._page: Page = page
        self._definitions: dict[str, JsonValue] = {
            item.name: item.expression for item in selectors
        }
        self._timeout_ms: int = timeout_ms
        self._poll_ms: int = poll_ms

    def sample(self, *, expression: str) -> Resolution:
        """Evaluate an expression once, without waiting or compiling CSS.

        Args:
            expression: ExtendedSelector expression.

        Returns:
            What the page reported right now.

        """
        return self._once(
            expression=expression,
            expected_count=None,
            checks=(),
            compile_css=False,
        )

    def resolve_selector(self, *, selector: SelectorDef) -> Resolution:
        """Resolve a stored selector with its own count and checks.

        Args:
            selector: Stored selector.

        Returns:
            The resolution.

        """
        return self.resolve(
            expression=selector.expression,
            expected_count=selector.expected_count,
            checks=selector.checks,
        )

    def resolve(
        self,
        *,
        expression: str,
        expected_count: int | None = 1,
        checks: tuple[str, ...] = (),
        compile_css: bool = True,
    ) -> Resolution:
        """Resolve an expression, waiting for the expected result.

        Evaluation repeats until the count and checks hold, the expression
        is found to be invalid, or the timeout passes.

        Args:
            expression: ExtendedSelector expression.
            expected_count: Exact count, or ``None`` for one or more.
            checks: Predicates every match must satisfy.
            compile_css: Also produce CSS for every match.

        Returns:
            The last resolution observed.

        """
        started: float = monotonic()
        polls: int = 0
        while True:
            polls += 1
            result: Resolution = self._once(
                expression=expression,
                expected_count=expected_count,
                checks=checks,
                compile_css=compile_css,
            )
            elapsed: float = monotonic() - started
            done: bool = (
                result.ok
                or result.error is not None
                or elapsed * 1000 >= self._timeout_ms
            )
            if done:
                return Resolution(
                    expression=result.expression,
                    expected_count=result.expected_count,
                    count=result.count,
                    matches=result.matches,
                    error=result.error,
                    definition_errors=result.definition_errors,
                    elapsed_ms=int(elapsed * 1000),
                    polls=polls,
                )
            self._page.wait_for_timeout(timeout=self._poll_ms)

    @staticmethod
    def _match(*, item: dict[str, JsonValue]) -> ResolvedMatch:
        """Convert one match reported by the page.

        Args:
            item: Match object from the resolve script.

        Returns:
            The typed match.

        """
        return ResolvedMatch(
            index=cast(typ="int", val=item["index"]),
            css=cast(typ="str | None", val=item["css"]),
            css_error=cast(typ="str | None", val=item["cssError"]),
            rect=cast(typ="dict[str, float]", val=item["rect"]),
            evidence=cast(typ="dict[str, JsonValue]", val=item["evidence"]),
            failed_checks=tuple(cast(typ="list[str]", val=item["failed"])),
        )

    def _once(
        self,
        *,
        expression: str,
        expected_count: int | None,
        checks: tuple[str, ...],
        compile_css: bool,
    ) -> Resolution:
        """Evaluate the expression one time.

        Args:
            expression: ExtendedSelector expression.
            expected_count: Exact count, or ``None`` for one or more.
            checks: Predicates every match must satisfy.
            compile_css: Also produce CSS for every match.

        Returns:
            What the page reported.

        """
        raw: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=world_for(page=self._page).call(
                function=resolve_function(),
                argument={
                    "expression": expression,
                    "definitions": self._definitions,
                    "checks": list(checks),
                    "compile": compile_css,
                },
            ),
        )
        items: list[dict[str, JsonValue]] = cast(
            typ="list[dict[str, JsonValue]]",
            val=raw["matches"],
        )
        return Resolution(
            expression=expression,
            expected_count=expected_count,
            count=cast(typ="int", val=raw["count"]),
            matches=tuple(self._match(item=item) for item in items),
            error=cast(typ="str | None", val=raw["error"]),
            definition_errors=tuple(
                cast(typ="list[str]", val=raw["definitionErrors"]),
            ),
        )
