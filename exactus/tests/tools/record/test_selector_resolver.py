# Copyright (c) 2026 Project contributors
"""Resolve stored selectors in a real browser page."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Locator, sync_playwright

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tests.tools.record.selector_support import Constants
from exactus.tools.record.selector_resolver import (
    Resolution,
    ResolvedMatch,
    SelectorResolver,
)
from exactus.tools.record.selectors import SelectorDef

if TYPE_CHECKING:
    from collections.abc import Iterator

    from playwright.sync_api import Page, Route

    from exactus.tools.common.json_types import JsonValue


@pytest.fixture
def page() -> Iterator[Page]:
    """Create a disposable Chromium page showing the selector fixture.

    Yields:
        A page with deterministic geometry and two open shadow roots.

    """
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        opened: Page = browser.new_context(
            viewport={"width": 1000, "height": 800},
        ).new_page()
        opened.goto(url=Constants.page_url)
        yield opened
        browser.close()


def _ids(*, page: Page, resolution: Resolution) -> list[str | None]:
    """Find each match again through its generated CSS.

    Args:
        page: Page the selector was resolved in.
        resolution: Result whose CSS is checked.

    Returns:
        The ``id`` of the single element each CSS string finds.

    """
    found: list[str | None] = []
    for match in resolution.matches:
        locator: Locator = page.locator(selector=match.css or "")
        expect_equal(actual=locator.count(), expected=1)
        found.append(locator.get_attribute(name="id"))
    return found


def test_every_match_gets_css_that_finds_only_it(page: Page) -> None:
    """Compile each element to a selector Playwright resolves uniquely.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(page=page).resolve(
        expression=".item",
        expected_count=5,
    )
    expect_true(condition=resolution.ok)
    expect_equal(
        actual=_ids(page=page, resolution=resolution),
        expected=[
            "above-far",
            "above-near",
            "below-near",
            "left-near",
            "right-near",
        ],
    )
    first: ResolvedMatch = resolution.matches[0]
    expect_equal(actual=first.evidence["tag"], expected="div")
    expect_equal(actual=first.rect["width"], expected=100)
    expect_equal(actual=first.evidence["visible"], expected=True)


def test_sort_order_survives_the_round_trip(page: Page) -> None:
    """Keep the order the expression imposed, element by element.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(page=page).resolve(
        expression="sort(.item, -[data-priority])",
        expected_count=5,
    )
    expect_equal(
        actual=_ids(page=page, resolution=resolution),
        expected=[
            "left-near",
            "right-near",
            "above-far",
            "below-near",
            "above-near",
        ],
    )


def test_stored_selectors_resolve_by_name(page: Page) -> None:
    """Let one stored selector build on another.

    Args:
        page: Fixture page.

    """
    reference: SelectorDef = SelectorDef(
        selector_id="sel-ref",
        name="reference",
        expression="#ref",
    )
    nearby: SelectorDef = SelectorDef(
        selector_id="sel-near",
        name="nearby",
        expression='nearest_above(.item, [extended-selector="reference"])',
        expected_count=2,
    )
    resolution: Resolution = SelectorResolver(
        page=page,
        selectors=(reference, nearby),
    ).resolve_selector(selector=nearby)
    expect_equal(
        actual=_ids(page=page, resolution=resolution),
        expected=["above-near", "above-far"],
    )


def test_waits_for_elements_that_appear_late(page: Page) -> None:
    """Poll until the expected element exists.

    Args:
        page: Fixture page.

    """
    _ = page.evaluate(
        expression=dedent(
            text=(
                "    () => setTimeout(() => {\n                const late "
                '= document.createElement("p");\n                late.clas'
                'sName = "late";\n                document.body.append(lat'
                "e);\n            }, 300)"
            ),
        ),
    )
    resolution: Resolution = SelectorResolver(
        page=page,
        timeout_ms=3000,
    ).resolve(expression=".late")
    expect_true(condition=resolution.ok)
    expect_true(condition=resolution.polls > 1)


def test_a_wrong_count_is_reported_after_the_timeout(page: Page) -> None:
    """Explain a count mismatch with the numbers involved.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(
        page=page,
        timeout_ms=200,
    ).resolve(expression=".item", expected_count=3)
    expect_false(condition=resolution.ok)
    cause: dict[str, JsonValue] = resolution.cause()
    expect_equal(actual=cause["phase"], expected="count")
    expect_equal(actual=cause["found_count"], expected=5)
    expect_in(member="Expected 3, found 5", container=str(object=cause))


def test_failed_checks_name_the_element_and_the_check(page: Page) -> None:
    """Report which match failed which predicate.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(
        page=page,
        timeout_ms=100,
    ).resolve(
        expression=".item",
        expected_count=5,
        checks=("[data-priority>=5]",),
    )
    expect_false(condition=resolution.checks_ok)
    cause: dict[str, JsonValue] = resolution.cause()
    expect_equal(actual=cause["phase"], expected="check")
    expect_in(member="[data-priority>=5]", container=str(object=cause))


def test_an_invalid_expression_fails_fast(page: Page) -> None:
    """Do not poll for an expression that can never evaluate.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(
        page=page,
        timeout_ms=5000,
    ).resolve(expression="sort(.item, #oops)")
    expect_equal(actual=resolution.polls, expected=1)
    expect_equal(actual=resolution.cause()["phase"], expected="resolve")
    expect_in(
        member="Invalid sort key",
        container=str(object=resolution.error),
    )


def test_broken_stored_selectors_do_not_break_others(page: Page) -> None:
    """Report an undefinable selector and carry on.

    Args:
        page: Fixture page.

    """
    broken: SelectorDef = SelectorDef(
        selector_id="sel-broken",
        name="broken",
        expression="sort(.item, #oops)",
    )
    resolution: Resolution = SelectorResolver(
        page=page,
        selectors=(broken,),
    ).resolve(expression="#ref")
    expect_true(condition=resolution.ok)
    expect_in(member="broken", container=resolution.definition_errors[0])


def test_shadow_elements_resolve_to_chains(page: Page) -> None:
    """Anchor elements inside open shadow roots to their hosts.

    Args:
        page: Fixture page.

    """
    resolution: Resolution = SelectorResolver(page=page).resolve(
        expression="button.inner",
        expected_count=2,
    )
    expect_true(condition=resolution.ok)
    for match in resolution.matches:
        expect_in(member=" >> ", container=match.css or "")
        expect_equal(
            actual=page.locator(selector=match.css or "").count(),
            expected=1,
        )


def test_the_world_is_rebuilt_after_a_navigation(page: Page) -> None:
    """Keep working when the page is replaced.

    Args:
        page: Fixture page.

    """
    resolver: SelectorResolver = SelectorResolver(page=page)
    expect_true(condition=resolver.resolve(expression="#ref").ok)
    _ = page.goto(url="data:text/html,<p class=fresh>hi</p>")
    expect_true(condition=resolver.resolve(expression=".fresh").ok)


def test_the_page_is_left_untouched(page: Page) -> None:
    """Add nothing to the page's globals or DOM.

    Args:
        page: Fixture page.

    """
    _ = SelectorResolver(page=page).resolve(
        expression=".item",
        expected_count=5,
    )
    expect_equal(
        actual=page.evaluate(expression="typeof globalThis.__EXACTUS_ES__"),
        expected="undefined",
    )
    expect_equal(
        actual=page.evaluate(
            expression="document.querySelectorAll('[extended-selector]').length",
        ),
        expected=0,
    )


def test_pages_with_a_strict_csp_still_resolve(page: Page) -> None:
    """Run without evaluating strings in the page's own security context.

    Args:
        page: Fixture page.

    """

    def serve(route: Route) -> None:
        """Fulfill navigation with a strict-CSP page.

        Args:
            route: Intercepted navigation route.

        """
        route.fulfill(
            body="<p class=guarded>ok</p>",
            content_type="text/html",
            headers={"Content-Security-Policy": "script-src 'none'"},
        )

    page.route(url="http://guarded.test/", handler=serve)
    _ = page.goto(url="http://guarded.test/")
    expect_true(
        condition=SelectorResolver(page=page)
        .resolve(expression=".guarded")
        .ok,
    )
