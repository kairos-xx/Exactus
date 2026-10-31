# Copyright (c) 2026
"""Run the browser test suite and enforce JavaScript coverage."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING, Final, Protocol, cast, final

from playwright.sync_api import Browser, Page, Route, sync_playwright

from exactus.tests.common.support import require_type
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_true,
    require_json_dict,
    require_json_list,
)

if TYPE_CHECKING:
    from exactus.packages.scene_description.models import JsonValue


@final
class Constants:
    """Module-level paths shared by the JavaScript tests.

    Attributes:
        js_root: Browser runtime asset directory.
        tests_js_root: JavaScript test asset directory.
        runtime_js: Unified evidence runtime under test.
        browser_test_js: In-browser test suite.
        coverage_floor: Required V8 byte coverage of the runtime.

    """

    js_root: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "scene_description"
        / "js"
    )
    tests_js_root: Final[Path] = Path(__file__).parent / "js"
    runtime_js: Final[Path] = js_root / "unified_evidence.js"
    browser_test_js: Final[Path] = tests_js_root / "browser.test.mjs"
    coverage_floor: Final[float] = 90.0


class _CdpSender(Protocol):
    """Structural subset of a Playwright CDP session used here."""

    def send(
        self,
        method: str,
        params: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Send a raw Chrome DevTools Protocol command.

        Args:
            method: CDP command name.
            params: Optional command parameters.

        Returns:
            Decoded command result object.

        """
        ...


def _node_check(*, path: Path) -> None:
    """Require ``path`` to parse as a JavaScript program.

    Args:
        path: JavaScript source file under test.

    """
    completed: CompletedProcess[str] = run(
        args=["node", "--check", str(object=path)],
        text=True,
        capture_output=True,
        check=False,
    )
    expect_equal(
        actual=completed.returncode,
        expected=0,
        message=completed.stderr,
    )


def test_runtime_js_parses() -> None:
    """The evidence runtime parses under Node."""
    _node_check(path=Constants.runtime_js)


def test_browser_test_js_parses() -> None:
    """The in-browser test suite parses under Node."""
    _node_check(path=Constants.browser_test_js)


def _covered_fraction(*, entry: dict[str, JsonValue]) -> float:
    """Compute the executed byte fraction of one V8 coverage entry.

    Executed regions are the union of all ranges with ``count > 0`` minus
    the union of all ``count == 0`` holes nested inside them; the domain is
    the union of every reported range.

    Args:
        entry: CDP ``Profiler.takePreciseCoverage`` entry with
            ``functions`` ranges.

    Returns:
        Fraction of source bytes executed at least once.

    """
    domain: set[int] = set()
    executed: set[int] = set()
    holes: set[int] = set()
    function_value: JsonValue
    for function_value in require_json_list(value=entry["functions"]):
        function: dict[str, JsonValue] = require_json_dict(
            value=function_value,
        )
        span_value: JsonValue
        for span_value in require_json_list(value=function["ranges"]):
            span: dict[str, JsonValue] = require_json_dict(value=span_value)
            region: range = range(
                require_type(value=span["startOffset"], kind=int),
                require_type(value=span["endOffset"], kind=int),
            )
            domain.update(region)
            if require_type(value=span["count"], kind=int) > 0:
                executed.update(region)
            else:
                holes.update(region)
    if not domain:
        return 1.0
    return len(executed - holes) / len(domain)


def _failure_lines(*, failed: list[JsonValue]) -> list[str]:
    """Format in-browser suite failures for the assertion message.

    Args:
        failed: Failure entries reported by the in-browser suite.

    Returns:
        One ``name: error`` line per failed check.

    """
    lines: list[str] = []
    item: JsonValue
    for item in failed:
        entry: dict[str, JsonValue] = require_json_dict(value=item)
        lines.append(f"{entry.get('name')}: {entry.get('error')}")
    return lines


def test_browser_suite_and_coverage() -> None:
    """Run the in-browser suite and require the coverage floor.

    The evidence runtime and the test program are served over a synthetic
    host so V8 coverage attributes each entry to a stable URL.
    """
    runtime_source: str = Constants.runtime_js.read_text(encoding="utf-8")
    test_source: str = Constants.browser_test_js.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch()
        page: Page = browser.new_page(viewport={"width": 1280, "height": 3200})

        def serve(route: Route) -> None:
            """Handle serve.

            Args:
                route: Route.

            """
            url: str = route.request.url
            if url.endswith("unified_evidence.js"):
                route.fulfill(
                    body=runtime_source,
                    content_type="text/javascript",
                )
            elif url.endswith("browser.test.mjs"):
                route.fulfill(body=test_source, content_type="text/javascript")
            else:
                route.fulfill(
                    body="<html><body></body></html>",
                    content_type="text/html",
                )

        page.route(url="**/*", handler=serve)
        session: _CdpSender = cast(
            typ="_CdpSender",
            val=page.context.new_cdp_session(page=page),
        )
        _ = session.send(method="Profiler.enable")
        _ = session.send(
            method="Profiler.startPreciseCoverage",
            params={"callCount": True, "detailed": True},
        )
        page.goto(url="http://scene-tests.local/index.html")
        page.add_script_tag(url="http://scene-tests.local/unified_evidence.js")
        page.add_script_tag(
            url="http://scene-tests.local/browser.test.mjs",
            type="module",
        )
        page.wait_for_function(
            expression="() => globalThis.__sceneTestResults !== undefined",
            timeout=180000,
        )
        results: dict[str, JsonValue] = require_json_dict(
            value=page.evaluate(
                expression="() => globalThis.__sceneTestResults",
            ),
        )
        coverage: list[JsonValue] = require_json_list(
            value=session.send(method="Profiler.takePreciseCoverage")[
                "result"
            ],
        )
        _ = session.send(method="Profiler.stopPreciseCoverage")
        browser.close()
    failed: list[JsonValue] = require_json_list(value=results["failed"])
    expect_true(
        condition=not failed,
        message="\n".join(_failure_lines(failed=failed)),
    )
    urls: list[str] = []
    fraction: float = 0.0
    raw_entry: JsonValue
    for raw_entry in coverage:
        entry: dict[str, JsonValue] = require_json_dict(value=raw_entry)
        url: JsonValue = entry.get("url")
        if not isinstance(url, str):
            continue
        urls.append(url)
        if url.endswith("unified_evidence.js"):
            fraction = _covered_fraction(entry=entry)
    expect_true(
        condition="http://scene-tests.local/unified_evidence.js" in urls,
        message=f"no coverage entry for the runtime; saw {urls!r}",
    )
    percent: float = fraction * 100
    expect_true(
        condition=percent >= Constants.coverage_floor,
        message=(
            f"unified_evidence.js coverage {percent:.1f}% "
            f"< {Constants.coverage_floor}%"
        ),
    )
