"""Bridge visual-cause findings to the ExtendedSelector page engine."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files as resource_files
from shutil import which
from textwrap import dedent
from typing import TYPE_CHECKING, Self, cast

from playwright.sync_api import (
    Browser,
    ElementHandle,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from types import TracebackType

    from playwright.sync_api import BrowserContext

    from exactus.tools.common.json_types import JsonValue


class QuerySyntaxError(Exception):
    """Report one invalid configured ExtendedSelector query."""


def _engine_source() -> str:
    """Load the selector engine as a page-evaluable script.

    Resolved through ``importlib.resources`` so the engine keeps working
    when the package executes from a pyz archive, where ``Path(__file__)``
    does not address real files.

    Returns:
        ExtendedSelector source with ES-module exports replaced by a
        ``globalThis`` assignment.

    """
    source: str = (
        resource_files("exactus.packages.extended_selector")
        .joinpath("editor", "extended-selector.js")
        .read_text(encoding="utf-8")
    )
    return (
        source.replace(
            "export class ExtendedSelector",
            "class ExtendedSelector",
        ).replace("export default ExtendedSelector;", "")
        + "\nglobalThis.ExtendedSelector = ExtendedSelector;\n"
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryResult:
    """Optimal selector and ranked exact candidates for one element.

    Attributes:
        query: Best selector the engine produced.
        candidates: Ranked alternative selectors with their scores.

    """

    query: str
    candidates: tuple[dict[str, JsonValue], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryConfig:
    """Configure one B-side selector query session.

    Attributes:
        url: Served page URL the session navigates to.
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        timeout_ms: Navigation timeout in milliseconds.
        css: Stylesheet injected into the page.
        native_styles: Whether the page keeps its native styles.

    """

    url: str
    width: int
    height: int
    timeout_ms: int
    css: str
    native_styles: bool


class QuerySession:
    """Own one B-side browser render used for queries and best selectors."""

    def __init__(self, *, config: QueryConfig) -> None:
        """Initialize a closed query session.

        Args:
            config: Render and stylesheet configuration.

        """
        self._config: QueryConfig = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        """Return the initialized page.

        Returns:
            Live Playwright page.

        Raises:
            RuntimeError: If the session was never entered.

        """
        if self._page is None:
            msg: str = "Query session is not open."
            raise RuntimeError(msg)
        return self._page

    def lint(self, *, query: str) -> tuple[dict[str, JsonValue], ...]:
        """Return ExtendedSelector diagnostics for one expression.

        Args:
            query: ExtendedSelector expression to validate.

        Returns:
            Engine diagnostics, empty when the query is valid.

        """
        raw: object = self.page.evaluate(
            expression="query => new ExtendedSelector(document).lint(query)",
            arg=query,
        )
        return tuple(
            cast(typ="dict[str, JsonValue]", val=item)
            for item in cast(typ="list[object]", val=raw)
            if isinstance(item, dict)
        )

    def matching(self, *, css_path: str, query: str) -> tuple[bool, int]:
        """Return whether the finding element matches and total query count.

        Args:
            css_path: Selector locating the changed element.
            query: Configured ExtendedSelector expression.

        Returns:
            ``(matched, count)`` — whether the element matched and how
            many elements the query matches overall.

        """
        element: ElementHandle | None = self.page.query_selector(
            selector=css_path,
        )
        if element is None:
            return (False, 0)
        matched: bool = cast(
            typ="bool",
            val=self.page.evaluate(
                expression=(
                    dedent(
                        text=(
                            "    ([node, expression]) =>\n    new Extended"
                            "Selector(document).matches(node, expression)"
                        ),
                    )
                ),
                arg=[element, query],
            ),
        )
        count: int = cast(
            typ="int",
            val=self.page.evaluate(
                expression=(
                    dedent(
                        text=(
                            "    expression =>\n    new ExtendedSelector(d"
                            "ocument).count(expression)"
                        ),
                    )
                ),
                arg=query,
            ),
        )
        return (matched, count)

    def best(self, *, css_path: str) -> QueryResult:
        """Return an exact optimal selector for the finding element.

        Args:
            css_path: Selector locating the changed element.

        Returns:
            Best engine selector plus ranked candidates; the input
            selector alone when the element is absent.

        """
        element: ElementHandle | None = self.page.query_selector(
            selector=css_path,
        )
        if element is None:
            return QueryResult(query=css_path, candidates=())
        raw: object = self.page.evaluate(
            expression=(
                dedent(
                    text=(
                        "    node =>\n    new ExtendedSelector(document).b"
                        "estSelector(node, {deep: true})"
                    ),
                )
            ),
            arg=element,
        )
        if not isinstance(raw, dict):
            return QueryResult(query=css_path, candidates=())
        result: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=raw,
        )
        selector: JsonValue | None = result.get("selector")
        candidates: JsonValue | None = result.get("candidates", [])
        candidate_list: list[JsonValue] = (
            candidates if isinstance(candidates, list) else []
        )
        return QueryResult(
            query=selector if isinstance(selector, str) else css_path,
            candidates=tuple(
                item for item in candidate_list if isinstance(item, dict)
            ),
        )

    def __enter__(self) -> Self:
        """Open Chromium and prepare the B-side page.

        Returns:
            This session with a live page.

        Raises:
            Error: When neither bundled nor system Chromium launches.

        """
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except PlaywrightError:
            executable: str | None = which(cmd="chromium") or which(
                cmd="google-chrome",
            )
            if executable is None:
                self._playwright.stop()
                raise
            self._browser = self._playwright.chromium.launch(
                headless=True,
                executable_path=executable,
            )
        context: BrowserContext = self._browser.new_context(
            viewport={
                "width": self._config.width,
                "height": self._config.height,
            },
            reduced_motion="reduce",
        )
        self._page = context.new_page()
        self._page.goto(
            url=self._config.url,
            wait_until="domcontentloaded",
            timeout=self._config.timeout_ms,
        )
        if not self._config.native_styles:
            self._page.evaluate(
                expression=(
                    dedent(
                        text=(
                            "    () => {\n      const styles = document.qu"
                            'erySelectorAll(\'style, link[rel="stylesheet"'
                            "]');\n      for (const node of styles) {\n   "
                            "     node.remove();\n      }\n    }"
                        ),
                    )
                ),
            )
        if self._config.css:
            self._page.add_style_tag(content=self._config.css)
        self._page.add_script_tag(content=_engine_source())
        self._page.evaluate(expression="() => document.fonts.ready")
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Close browser-owned resources.

        Args:
            _exception_type: Unused exception type supplied by ``with``.
            _exception: Unused exception supplied by ``with``.
            _traceback: Unused traceback supplied by ``with``.

        """
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
