# Copyright (c) 2026 Project contributors
"""Exercise the actual offline dashboard at desktop and mobile widths."""

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Error, sync_playwright

from exactus.packages.todo_sync import synchronize
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page


@pytest.mark.parametrize("width", [390, 1440, 1728])
def test_dashboard_controls(tmp_path: Path, width: int) -> None:
    """Verify offline search, filters, source links, reload and export.

    Args:
        tmp_path: Isolated document and screenshot directory.
        width: Browser viewport width used to test responsive controls.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(
        data=dedent(
            text=(
                "    # Plan\n    ## Work\n    - [ ] **R01 — Record browser"
                "** P0\n    - [x] **R02 — Graph connections** P1\n    - [ "
                "] **UI-O03 — Dock panels** P1\n    - [ ] </script><img sr"
                "c=x onerror=alert(1)>\n    "
            ),
        ),
        encoding="utf-8",
    )
    synchronize(path=path)
    errors: list[str] = []

    def on_error(error: Error) -> None:
        """Retain a browser runtime failure for the final assertion.

        Args:
            error: Uncaught exception reported by the page.

        """
        errors.append(str(object=error))

    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        page: Page = browser.new_page(viewport={"width": width, "height": 900})
        page.on(event="pageerror", f=on_error)
        page.goto(url=path.with_suffix(suffix=".html").as_uri())
        expect_equal(actual=page.title(), expected="TODO progress")
        expect_equal(
            actual=page.locator(selector="article.task").count(),
            expected=4,
        )
        expect_equal(
            actual=page.locator(selector="#completion").inner_text(),
            expected="25.0%",
        )
        expect_equal(
            actual=page.locator(selector="#tasks img").count(),
            expected=0,
        )
        page.get_by_role(role="textbox", name="Search tasks").fill(
            value="dock",
        )
        expect_equal(
            actual=page.locator(selector="article.task").count(),
            expected=1,
        )
        page.reload()
        expect_equal(
            actual=page.locator(selector="article.task").count(),
            expected=1,
        )
        page.get_by_role(role="textbox", name="Search tasks").fill(
            value="missing-word",
        )
        expect_equal(
            actual=page.locator(selector="article.task").count(),
            expected=0,
        )
        page.get_by_role(role="textbox", name="Search tasks").fill(value="")
        if page.get_by_role(
            role="button",
            name="Filters",
            exact=True,
        ).is_visible():
            page.get_by_role(role="button", name="Filters", exact=True).click()
        page.locator(
            selector='button[data-field="status"][data-label="Done"]',
        ).click()
        expect_equal(
            actual=page.locator(selector="article.task").count(),
            expected=1,
        )
        page.get_by_role(role="button", name="Reset all").click()
        page.get_by_role(role="combobox", name="Group results").select_option(
            value="priority",
        )
        expect_equal(
            actual=page.locator(selector=".group-card").count(),
            expected=3,
        )
        page.get_by_role(role="combobox", name="Sort tasks").select_option(
            value="id",
        )
        page.locator(selector="article.task .task-title").first.click()
        expect_equal(
            actual=page.locator(selector="#docWorkspace").is_visible(),
            expected=True,
        )
        document_text: str = page.locator(selector="#docView").inner_text()
        expect_equal(
            actual="Graph connections" in document_text,
            expected=True,
        )
        page.get_by_role(role="button", name="Tasks", exact=True).click()
        with page.expect_download() as download:
            page.get_by_role(role="button", name="Export visible").click()
        expect_equal(
            actual=download.value.suggested_filename,
            expected="todo-filtered.json",
        )
        expect_equal(
            actual=page.evaluate(
                expression=(
                    "document.documentElement.scrollWidth <= innerWidth"
                ),
            ),
            expected=True,
        )
        page.screenshot(path=str(object=tmp_path / f"dashboard-{width}.png"))
        expect_equal(actual=errors, expected=[])
        browser.close()
