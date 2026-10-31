#!/usr/bin/env python3
# Copyright (c) 2026
"""Explore clickable states and capture visually distinctive screens."""

from __future__ import annotations

from asyncio import Event, Future, Queue, TaskGroup, get_running_loop, shield
from dataclasses import dataclass, field
from hashlib import sha256
from re import IGNORECASE, Pattern
from re import compile as re_compile
from re import sub as re_sub
from textwrap import dedent
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, Self, cast
from urllib.parse import ParseResult, urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error,
    Locator,
    Page,
    Route,
    async_playwright,
)

from exactus.tools.record.capture_screen import (
    SnapshotCapture,
    SnapshotOptions,
)
from exactus.tools.record.diagnostics import (
    DiagnosticCollector,
    DiagnosticEvent,
)
from exactus.tools.record.similarity import ImageSimilarity

if TYPE_CHECKING:
    from asyncio import Task
    from collections.abc import Awaitable, Callable
    from pathlib import Path


class ExplorerDefaults:
    """Store immutable exploratory-crawler defaults.

    Attributes:
        CLICKABLE: CSS selector matching replayable click candidates.
        DANGEROUS: Label pattern excluded during safe exploration.
        MUTATING_METHODS: HTTP methods blocked during safe exploration.
        TARGET: Default snapshot target selector.
        MAP_SHARE: Fraction of a lane's progress spent mapping candidates.
        PROBES_PER_STATE: Initial probe budget assumed for unscanned states.
        DESCRIBE: Page script returning a target's tag, href, CSS
            selector and absolute document centre.
        SETTLE_MS: Post-interaction settle delay in milliseconds.
        TIMEOUT_MS: Per-action Playwright timeout in milliseconds.
        PAGE_TIMEOUT_MS: Page navigation timeout in milliseconds.
        SIMILARITY: Minimum image similarity treated as a duplicate.
        MAX_DEPTH: Maximum click depth from the initial state.
        MAX_STATES: Maximum states captured per lane.
        VIEWPORT_WIDTH: Default desktop viewport width in pixels.
        VIEWPORT_HEIGHT: Default desktop viewport height in pixels.
        TABLET_WIDTH: Tablet viewport width in pixels.
        TABLET_HEIGHT: Tablet viewport height in pixels.
        PHONE_WIDTH: Phone viewport width in pixels.
        PHONE_HEIGHT: Phone viewport height in pixels.
        DEVICE_SCALE_FACTOR: Default device pixel ratio.

    """

    CLICKABLE: ClassVar[str] = (
        "a[href],button,input[type=button],input[type=submit],input[type=r"
        "eset],input[type=checkbox],input[type=radio],select,summary,[role"
        "=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],["
        "role=radio],[role=switch],[role=option],[onclick],[tabindex]:not("
        "[tabindex='-1'])"
    )
    DANGEROUS: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            r"\b(delete|remove|destroy|erase|wipe|format|purchase|buy|pay|"
            r"submit|send|publish|deploy|shutdown|reboot|restart|kill|stop|"
            r"logout|sign\s*out|unsubscribe|revoke|terminate|drop)\b"
        ),
        flags=IGNORECASE,
    )
    MUTATING_METHODS: ClassVar[frozenset[str]] = frozenset(
        {"DELETE", "PATCH", "POST", "PUT"},
    )
    TARGET: ClassVar[str] = "body"
    MAP_SHARE: ClassVar[float] = 0.3
    PROBES_PER_STATE: ClassVar[int] = 2
    DESCRIBE: ClassVar[str] = dedent(
        text=(
            "    element => {\n      const step = (node) => {\n        if (nod"
            "e.id) {\n          return `#${CSS.escape(node.id)}`;\n        }\n"
            "        const tag = node.tagName.toLowerCase();\n        const si"
            "blings = node.parentElement\n          ? [...node.parentElement.c"
            "hildren].filter(\n              (child) => child.tagName === node"
            ".tagName,\n            )\n          : [];\n        return sibling"
            "s.length > 1\n          ? `${tag}:nth-of-type(${siblings.indexOf("
            "node) + 1})`\n          : tag;\n      };\n      const parts = [];"
            "\n      for (let node = element; node; node = node.parentElement)"
            " {\n        const part = step(node);\n        parts.unshift(part)"
            ';\n        if (part.startsWith("#") || part === "body") {\n      '
            "    break;\n        }\n      }\n      const box = element.getBoun"
            "dingClientRect();\n      return {\n        tag: element.tagName.t"
            'oLowerCase(),\n        href: element.getAttribute("href") || "",'
            '\n        selector: parts.join(" > "),\n        x: Math.round(box'
            ".left + window.scrollX + box.width / 2),\n        y: Math.round(b"
            "ox.top + window.scrollY + box.height / 2),\n      };\n    }"
        ),
    )
    SETTLE_MS: ClassVar[float] = 500.0
    TIMEOUT_MS: ClassVar[float] = 5_000.0
    PAGE_TIMEOUT_MS: ClassVar[float] = 30_000.0
    SIMILARITY: ClassVar[float] = 0.965
    MAX_DEPTH: ClassVar[int] = 4
    MAX_STATES: ClassVar[int] = 100
    VIEWPORT_WIDTH: ClassVar[int] = 1440
    VIEWPORT_HEIGHT: ClassVar[int] = 1000
    TABLET_WIDTH: ClassVar[int] = 1024
    TABLET_HEIGHT: ClassVar[int] = 1366
    PHONE_WIDTH: ClassVar[int] = 390
    PHONE_HEIGHT: ClassVar[int] = 844
    DEVICE_SCALE_FACTOR: ClassVar[float] = 2.0


@dataclass(frozen=True, slots=True, kw_only=True)
class ClickTarget:
    """Describe a replayable clickable target.

    Attributes:
        index: DOM-order index within the clickable selector results.
        label: Compact semantic label for the element.
        tag: Lowercased element tag name.
        href: Anchor destination when present.
        selector: CSS selector (``querySelector`` string) for the element.
        url: Page URL on which the element was clicked.
        x: Absolute document x of the element centre, in CSS pixels.
        y: Absolute document y of the element centre, in CSS pixels.

    """

    index: int
    label: str
    tag: str
    href: str
    selector: str = ""
    url: str = ""
    x: int = 0
    y: int = 0

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        """Identity used to tell whether a click unveiled this target.

        Returns:
            ``(url, tag, label, href, selector)``.

        """
        return (self.url, self.tag, self.label, self.href, self.selector)


@dataclass(frozen=True, slots=True, kw_only=True)
class StateNode:
    """Describe one visually distinct interaction state.

    Attributes:
        id: Deterministic short state identifier.
        parent_id: Identifier of the discovering parent state.
        path: Click sequence replaying this state.
        url: URL displayed by this state.
        screenshot: Captured screenshot filename.
        similarity_to_parent: Visual similarity to the parent state.

    """

    id: str
    parent_id: str | None
    path: tuple[ClickTarget, ...]
    url: str
    screenshot: str
    similarity_to_parent: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticFinding:
    """Associate diagnostics with one tested interaction.

    Attributes:
        variant: Capture variant that observed the diagnostics.
        parent_id: State in which the action ran.
        action: Clicked target that triggered the events.
        events: Diagnostic events attributed to the action.

    """

    variant: str
    parent_id: str
    action: ClickTarget
    events: tuple[DiagnosticEvent, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureVariant:
    """Describe one responsive and color-scheme capture environment.

    Attributes:
        name: Unique variant identifier.
        width: Viewport width in pixels.
        height: Viewport height in pixels.
        color_scheme: Emulated preferred color scheme.
        is_mobile: Whether mobile emulation is enabled.
        has_touch: Whether touch emulation is enabled.
        scale: Device scale factor.

    """

    name: str
    width: int
    height: int
    color_scheme: Literal["dark", "light"]
    is_mobile: bool
    has_touch: bool
    scale: float


@dataclass(frozen=True, slots=True, kw_only=True)
class LaneUpdate:
    """Describe one lane lifecycle transition.

    Attributes:
        name: Capture variant name.
        state: Lane lifecycle state.
        completed: Completed lane work units.
        total: Total lane work units.
        step: Current lane step.
        detail: Optional detail.
        share: Lane completion in ``[0, 1]`` across both phases.

    """

    name: str
    state: str
    completed: int
    total: int
    step: str
    detail: str = ""
    share: float | None = None


class LaneReporter(Protocol):
    """Publish live per-lane exploration progress."""

    def lane(self: Self, *, update: LaneUpdate) -> None:
        """Report one lane lifecycle transition.

        Args:
            update: Lane lifecycle transition.

        """

    def diagnostics(
        self: Self,
        *,
        events: tuple[DiagnosticEvent, ...],
    ) -> None:
        """Report newly attributed diagnostic events.

        Args:
            events: Diagnostic events attributed since the last report.

        """


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixResult:
    """Carry everything one capture-matrix run observed.

    Attributes:
        variants: Executed capture environments.
        results: Distinctive states keyed by variant name.
        diagnostics: Diagnostic events keyed by variant name.
        findings: Interaction-attributed findings keyed by variant name.
        blocked: Mutating requests intercepted per variant name.
        candidates: Clicks mapped as screenshot candidates per variant.

    """

    variants: tuple[CaptureVariant, ...]
    results: dict[str, tuple[StateNode, ...]]
    diagnostics: dict[str, tuple[DiagnosticEvent, ...]]
    findings: dict[str, tuple[DiagnosticFinding, ...]]
    blocked: dict[str, tuple[str, ...]]
    candidates: dict[str, int]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExplorerOptions:
    """Configure browser-state exploration.

    Attributes:
        url: Initial URL explored by every lane.
        output: Directory receiving captured screenshots.
        target: Snapshot target selector.
        similarity: Minimum image similarity treated as a duplicate.
        max_depth: Maximum click depth from the initial state.
        max_states: Maximum states captured per lane.
        settle_ms: Post-interaction settle delay in milliseconds.
        timeout_ms: Per-action Playwright timeout in milliseconds.
        width: Default desktop viewport width in pixels.
        height: Default desktop viewport height in pixels.
        scale: Default device scale factor.
        headless: Whether the browser runs headless.
        unsafe: Whether dangerous targets and mutations are allowed.
        exhaustive: Whether every state re-clicks every visible target
            instead of only the targets its own click unveiled.
        workers: Browser pages per lane trying click targets in parallel.
        only_get: Whether every request other than ``GET`` is blocked.
        variant: Capture environment assigned to this lane.
        capture_ui_changes: Persist screenshots of distinctive UI states.
        follow_links: Follow navigable links discovered on visited pages.
        click_controls: Activate interactive controls besides links.
        include_selector: Optional CSS selector limiting clickable targets.

    """

    url: str
    output: Path
    target: str = ExplorerDefaults.TARGET
    similarity: float = ExplorerDefaults.SIMILARITY
    max_depth: int = ExplorerDefaults.MAX_DEPTH
    max_states: int = ExplorerDefaults.MAX_STATES
    settle_ms: float = ExplorerDefaults.SETTLE_MS
    timeout_ms: float = ExplorerDefaults.TIMEOUT_MS
    width: int = ExplorerDefaults.VIEWPORT_WIDTH
    height: int = ExplorerDefaults.VIEWPORT_HEIGHT
    scale: float = ExplorerDefaults.DEVICE_SCALE_FACTOR
    headless: bool = True
    unsafe: bool = False
    exhaustive: bool = False
    workers: int = 4
    only_get: bool = False
    capture_ui_changes: bool = True
    follow_links: bool = True
    click_controls: bool = True
    include_selector: str | None = None
    variant: CaptureVariant = field(
        default_factory=lambda: CaptureVariant(
            name="desktop-light",
            width=ExplorerDefaults.VIEWPORT_WIDTH,
            height=ExplorerDefaults.VIEWPORT_HEIGHT,
            color_scheme="light",
            is_mobile=False,
            has_touch=False,
            scale=ExplorerDefaults.DEVICE_SCALE_FACTOR,
        ),
    )


@dataclass(frozen=True, slots=True)
class _Worker:
    """One isolated browser page plus its diagnostics collector.

    Attributes:
        page: Page used to replay paths and try click targets.
        collector: Diagnostics observed on ``page``.

    """

    page: Page
    collector: DiagnosticCollector


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One mapped click that may unveil a new screenshot.

    Attributes:
        parent: Click path reaching the state the click starts from.
        target: Element to click.

    """

    parent: tuple[ClickTarget, ...]
    target: ClickTarget


@dataclass(frozen=True, slots=True)
class _Node:
    """One DOM state queued for mapping.

    Attributes:
        path: Click path reaching the state.
        signature: DOM signature of the state.
        inherited: Target keys already visible in the parent state.

    """

    path: tuple[ClickTarget, ...]
    signature: str
    inherited: frozenset[tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _Probe:
    """DOM-level outcome of one mapping click.

    Attributes:
        url: URL displayed after the click.
        signature: Hash of the URL and serialized DOM after the click.

    """

    url: str
    signature: str


@dataclass(frozen=True, slots=True)
class _Attempt:
    """Observed outcome of one click, before the dedup decisions.

    Attributes:
        url: URL displayed after the click.
        events: Diagnostics raised by the click.
        preview: Viewport screenshot after the click.

    """

    url: str
    events: tuple[DiagnosticEvent, ...]
    preview: bytes


class ClickExplorer:
    """Breadth-first explore and capture visually novel clickable states."""

    def __init__(
        self: Self,
        options: ExplorerOptions,
        reporter: LaneReporter | None = None,
        lane_name: str = "",
        plan: tuple[Future[tuple[_Candidate, ...]], bool] | None = None,
    ) -> None:
        """Initialize the explorer.

        Args:
            options: Immutable run configuration.
            reporter: Optional run-wide progress reporter.
            lane_name: Variant name used in progress events.
            plan: Candidate plan shared by lanes of one device, and whether
                this lane maps it (other lanes wait for it instead).

        """
        self._options: ExplorerOptions = options
        self._similarity: ImageSimilarity = ImageSimilarity()
        self._states: list[StateNode] = []
        self._blocked_requests: list[str] = []
        self._reporter: LaneReporter | None = reporter
        self._lane_name: str = lane_name
        self._plan: tuple[Future[tuple[_Candidate, ...]], bool] | None = plan
        self._collectors: list[DiagnosticCollector] = []
        self._findings: list[DiagnosticFinding] = []
        self._visited_urls: set[str] = set()
        self._planned: int = 0
        self._clicked: int = 0
        self._mapped: int = 0
        self._known: int = 1
        self._capturing: bool = False
        self._probe_budget: int = ExplorerDefaults.PROBES_PER_STATE

    @property
    def diagnostics(self: Self) -> tuple[DiagnosticEvent, ...]:
        """All diagnostics observed by this lane.

        Returns:
            Diagnostic events in observation order.

        """
        seen: set[tuple[str, ...]] = set()
        merged: list[DiagnosticEvent] = []
        for collector in self._collectors:
            for event in collector.events:
                key: tuple[str, ...] = (
                    event.category,
                    event.severity,
                    event.phase,
                    event.action,
                    event.message,
                    event.url,
                    event.method,
                    str(object=event.status),
                )
                if key not in seen:
                    seen.add(key)
                    merged.append(event)
        return tuple(merged)

    @property
    def planned(self: Self) -> int:
        """Click targets mapped so far (potential screenshots).

        Returns:
            Planned click count.

        """
        return self._planned

    @property
    def findings(self: Self) -> tuple[DiagnosticFinding, ...]:
        """Interaction-attributed diagnostic findings.

        Returns:
            Findings keyed to the action that triggered them.

        """
        return tuple(self._findings)

    @property
    def blocked(self: Self) -> tuple[str, ...]:
        """Mutating requests intercepted during safe exploration.

        Returns:
            ``METHOD URL`` entries for every intercepted mutation.

        """
        return tuple(self._blocked_requests)

    async def run(self: Self) -> tuple[StateNode, ...]:
        """Run the browser exploration and return distinctive states.

        Returns:
            Distinctive states in breadth-first discovery order.

        """
        self._options.output.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(
                headless=self._options.headless,
            )
            contexts: list[BrowserContext] = []
            try:
                workers: list[_Worker] = []
                for _ in range(max(self._options.workers, 1)):
                    context: BrowserContext = await browser.new_context(
                        viewport={
                            "width": self._options.variant.width,
                            "height": self._options.variant.height,
                        },
                        color_scheme=self._options.variant.color_scheme,
                        is_mobile=self._options.variant.is_mobile,
                        has_touch=self._options.variant.has_touch,
                        device_scale_factor=self._options.variant.scale,
                    )
                    contexts.append(context)
                    if self._options.only_get or not self._options.unsafe:
                        _ = await context.route(
                            url="**/*",
                            handler=self._route,
                        )
                    page: Page = await context.new_page()
                    page.set_default_timeout(timeout=self._options.timeout_ms)
                    collector: DiagnosticCollector = DiagnosticCollector(
                        variant=self._lane_name,
                    )
                    await collector.attach_async(page=page)
                    self._collectors.append(collector)
                    workers.append(_Worker(page=page, collector=collector))
                await self._explore(workers=tuple(workers))
            finally:
                for context in contexts:
                    await context.close()
                await browser.close()
        return tuple(self._states)

    @staticmethod
    async def _signature(page: Page) -> str:
        """Hash the URL and serialized DOM of the current state.

        Args:
            page: Page displaying the state.

        Returns:
            Hex digest identifying the DOM state.

        """
        html: str = cast(
            typ="str",
            val=await page.evaluate(
                expression=(
                    "() => document.documentElement"
                    " ? document.documentElement.outerHTML : ''"
                ),
            ),
        )
        return sha256(data=f"{page.url}\n{html}".encode()).hexdigest()

    @staticmethod
    async def _parallel[I, T](
        *,
        workers: tuple[_Worker, ...],
        items: tuple[I, ...],
        work: Callable[[_Worker, I], Awaitable[T]],
    ) -> list[T]:
        """Run ``work`` for every item on leased workers.

        Args:
            workers: Isolated pages leased first-come first-served.
            items: Work items.
            work: Coroutine factory receiving a worker and an item.

        Returns:
            Results in item order.

        """
        idle: Queue[_Worker] = Queue()
        for worker in workers:
            idle.put_nowait(item=worker)
        results: list[T | None] = [None] * len(items)

        async def run(index: int, item: I) -> None:
            """Lease a worker, run ``work`` on ``item``, store the result.

            Args:
                index: Position of ``item`` in ``items``.
                item: Work item.

            """
            worker: _Worker = await idle.get()
            try:
                results[index] = await work(worker, item)
            finally:
                idle.put_nowait(item=worker)

        async with TaskGroup() as group:
            for index, item in enumerate(iterable=items):
                _ = group.create_task(coro=run(index=index, item=item))
        return cast(typ="list[T]", val=results)

    @staticmethod
    async def _label(locator: Locator) -> str:
        """Build a compact semantic label for a clickable locator.

        Args:
            locator: Candidate clickable element.

        Returns:
            Best available accessible or textual label.

        """
        aria: str = await locator.get_attribute(name="aria-label") or ""
        title: str = await locator.get_attribute(name="title") or ""
        value: str = await locator.get_attribute(name="value") or ""
        text: str = (await locator.inner_text()).strip()
        return " ".join(
            part.strip() for part in (aria, title, text, value) if part.strip()
        )[:240]

    @staticmethod
    def _state_id(path: tuple[ClickTarget, ...], url: str) -> str:
        """Derive a deterministic short identifier for a state.

        Args:
            path: Interaction path reaching the state.
            url: URL displayed by the state.

        Returns:
            Short hexadecimal state identifier.

        """
        material: str = "|".join(
            (
                url,
                *(
                    f"{target.index}:{target.tag}:{target.label}"
                    for target in path
                ),
            ),
        )
        return sha256(data=material.encode(encoding="utf-8")).hexdigest()[:16]

    async def _explore(self: Self, workers: tuple[_Worker, ...]) -> None:
        """Map every screenshot candidate, then capture against that plan.

        Phase one crawls without screenshots and records each click that
        changes the DOM into a state not seen before; its size is the
        progress total. Phase two replays those candidates, applies the
        visual similarity heuristics, and captures the survivors.

        Args:
            workers: Isolated pages; the first one maps targets.

        """
        main: _Worker = workers[0]
        main.collector.phase(phase="initial")
        await self._reset(page=main.page, path=())
        baseline: bytes = await self._viewport(page=main.page)
        self._visited_urls.add(main.page.url)
        root: StateNode = await self._remember_state(
            page=main.page,
            parent_id=None,
            path=(),
            preview=baseline,
            parent_preview=None,
        )
        candidates: tuple[_Candidate, ...] = await self._candidates(
            workers=workers,
            signature=await self._signature(page=main.page),
        )
        self._planned = len(candidates)
        self._capturing = True
        await self._capture(
            workers=workers,
            root=(root, baseline),
            candidates=candidates,
        )

    async def _candidates(
        self: Self,
        *,
        workers: tuple[_Worker, ...],
        signature: str,
    ) -> tuple[_Candidate, ...]:
        """Map candidates, or reuse the plan another lane maps.

        Light and dark lanes of one device share the same DOM, so only
        one of them crawls; the other waits for its plan.

        Args:
            workers: Isolated pages crawling concurrently.
            signature: DOM signature of the initial state.

        Returns:
            Candidates in breadth-first order.

        """
        if self._plan is None:
            return await self._map(workers=workers, signature=signature)
        plan, mapper = self._plan
        if not mapper:
            self._report(step="map", detail="waiting for the shared plan")
            return await shield(arg=plan)
        try:
            candidates: tuple[_Candidate, ...] = await self._map(
                workers=workers,
                signature=signature,
            )
        except BaseException as error:
            if not plan.done():
                plan.set_exception(error)
            raise
        if not plan.done():
            plan.set_result(candidates)
        return candidates

    async def _map(
        self: Self,
        *,
        workers: tuple[_Worker, ...],
        signature: str,
    ) -> tuple[_Candidate, ...]:
        """Crawl click targets breadth-first and list screenshot candidates.

        A click is a candidate when it reaches an unvisited URL or a DOM
        state not seen before. New states are crawled further, clicking
        only the targets they unveiled unless ``exhaustive``.

        Args:
            workers: Isolated pages crawling concurrently.
            signature: DOM signature of the initial state.

        Returns:
            Candidates in breadth-first order.

        """
        seen: set[str] = {signature}
        visited: set[str] = set(self._visited_urls)
        candidates: list[_Candidate] = []
        level: list[_Node] = [
            _Node(path=(), signature=signature, inherited=frozenset()),
        ]
        self._known = 1
        while level and len(candidates) < self._options.max_states:
            scans: list[tuple[ClickTarget, ...]] = await self._parallel(
                workers=workers,
                items=tuple(level),
                work=lambda worker, node: self._scan(
                    worker=worker,
                    path=node.path,
                ),
            )
            work: list[
                tuple[_Node, frozenset[tuple[str, ...]], ClickTarget]
            ] = [
                (node, frozenset(target.key for target in visible), target)
                for node, visible in zip(level, scans, strict=True)
                for target in visible
                if self._options.exhaustive or target.key not in node.inherited
            ]
            self._known += len(work) - self._probe_budget * sum(
                bool(node.path) for node in level
            )
            child_scans: int = sum(bool(node.path) for node in level)
            if child_scans:
                self._probe_budget = max(
                    1,
                    round(
                        number=sum(bool(node.path) for node, _, _ in work)
                        / child_scans,
                    ),
                )
            probes: list[_Probe | None] = await self._parallel(
                workers=workers,
                items=tuple((*node.path, target) for node, _, target in work),
                work=lambda worker, item: self._probe(
                    worker=worker,
                    path=item,
                ),
            )
            following: list[_Node] = []
            for (node, known, target), probe in zip(work, probes, strict=True):
                if (
                    probe is None
                    or probe.signature == node.signature
                    or probe.signature in seen
                    or (probe.url != target.url and probe.url in visited)
                    or len(candidates) >= self._options.max_states
                ):
                    continue
                visited.add(probe.url)
                seen.add(probe.signature)
                candidates.append(_Candidate(parent=node.path, target=target))
                if len(node.path) + 1 < self._options.max_depth:
                    following.append(
                        _Node(
                            path=(*node.path, target),
                            signature=probe.signature,
                            inherited=known,
                        ),
                    )
            self._known += len(following) * (1 + self._probe_budget)
            level = following
        self._mapped = self._known
        return tuple(candidates)

    async def _scan(
        self: Self,
        *,
        worker: _Worker,
        path: tuple[ClickTarget, ...],
    ) -> tuple[ClickTarget, ...]:
        """Replay ``path`` and list the click targets visible there.

        Args:
            worker: Leased page.
            path: Click path reaching the state to scan.

        Returns:
            Visible, enabled, safe click targets.

        """
        worker.collector.phase(phase="replay")
        await self._reset(page=worker.page, path=path)
        targets: tuple[ClickTarget, ...] = await self._targets(
            page=worker.page,
        )
        self._step_mapped(detail=f"{len(targets)} target(s) visible")
        return targets

    def _step_mapped(self: Self, *, detail: str) -> None:
        """Count one finished mapping step and publish progress.

        Args:
            detail: Human-readable detail.

        """
        self._mapped += 1
        self._report(step="map", detail=detail)

    async def _probe(
        self: Self,
        *,
        worker: _Worker,
        path: tuple[ClickTarget, ...],
    ) -> _Probe | None:
        """Replay ``path`` and describe the resulting DOM state.

        Args:
            worker: Leased page.
            path: Click path whose last click is being probed.

        Returns:
            DOM outcome, or ``None`` when the last click failed.

        """
        worker.collector.phase(phase="replay")
        await self._reset(page=worker.page, path=path[:-1])
        if not await self._click(page=worker.page, target=path[-1]):
            self._step_mapped(detail="click failed")
            return None
        probe: _Probe = _Probe(
            url=worker.page.url,
            signature=await self._signature(page=worker.page),
        )
        self._step_mapped(detail=f"probed {path[-1].label or path[-1].tag}")
        return probe

    async def _capture(
        self: Self,
        *,
        workers: tuple[_Worker, ...],
        root: tuple[StateNode, bytes],
        candidates: tuple[_Candidate, ...],
    ) -> None:
        """Replay every candidate concurrently, deciding in plan order.

        Workers are leased first-come first-served, and each attempt
        waits for its turn before the similarity decisions and the
        capture, so results match a sequential run exactly.

        Args:
            workers: Isolated pages available to this lane.
            root: Initial state and its preview.
            candidates: Mapped candidates in breadth-first order.

        """
        idle: Queue[_Worker] = Queue()
        for worker in workers:
            idle.put_nowait(item=worker)
        turns: list[Event] = [Event() for _ in range(len(candidates) + 1)]
        turns[0].set()
        previews: dict[tuple[ClickTarget, ...], bytes] = {(): root[1]}
        owners: dict[tuple[ClickTarget, ...], str] = {(): root[0].id}

        async def attempt(index: int, candidate: _Candidate) -> None:
            """Replay one candidate, then decide on it in plan order.

            Args:
                index: Position of the candidate in the plan.
                candidate: Mapped click to replay.

            """
            worker: _Worker = await idle.get()
            try:
                outcome: _Attempt | None = await self._attempt(
                    worker=worker,
                    candidate=candidate,
                )
                await turns[index].wait()
                try:
                    if (
                        outcome is not None
                        and len(self._states) < self._options.max_states
                    ):
                        await self._accept(
                            worker=worker,
                            candidate=candidate,
                            outcome=outcome,
                            lineage=(previews, owners),
                        )
                finally:
                    turns[index + 1].set()
            finally:
                idle.put_nowait(item=worker)

        async with TaskGroup() as group:
            for index, candidate in enumerate(iterable=candidates):
                _ = group.create_task(
                    coro=attempt(index=index, candidate=candidate),
                )

    async def _attempt(
        self: Self,
        *,
        worker: _Worker,
        candidate: _Candidate,
    ) -> _Attempt | None:
        """Replay a candidate's parent path on ``worker`` and click it.

        Args:
            worker: Leased page and its collector.
            candidate: Mapped click to replay.

        Returns:
            Click outcome, or ``None`` when the click could not happen.

        """
        target: ClickTarget = candidate.target
        worker.collector.phase(phase="replay")
        await self._reset(page=worker.page, path=candidate.parent)
        mark: int = worker.collector.mark()
        worker.collector.phase(
            phase="action",
            action=target.label or target.tag,
        )
        clicked: bool = await self._click(page=worker.page, target=target)
        self._clicked += 1
        self._report(
            step="capture",
            detail=f"{target.label or target.tag} @ {target.selector}",
        )
        if not clicked:
            return None
        return _Attempt(
            url=worker.page.url,
            events=worker.collector.since(mark=mark),
            preview=await self._viewport(page=worker.page),
        )

    async def _accept(
        self: Self,
        *,
        worker: _Worker,
        candidate: _Candidate,
        outcome: _Attempt,
        lineage: tuple[
            dict[tuple[ClickTarget, ...], bytes],
            dict[tuple[ClickTarget, ...], str],
        ],
    ) -> None:
        """Record diagnostics, apply visual similarity, then capture.

        Every attempted path keeps its preview and nearest captured
        ancestor, so children compare against what their parent really
        looked like even when the parent itself was deduplicated.

        Args:
            worker: Page still displaying the clicked state.
            candidate: Mapped click that was replayed.
            outcome: Observed click outcome.
            lineage: Previews and owning state ids keyed by click path.

        """
        previews, owners = lineage
        path: tuple[ClickTarget, ...] = (*candidate.parent, candidate.target)
        parent_preview: bytes = previews.get(candidate.parent, previews[()])
        owner: str = owners.get(candidate.parent, owners[()])
        previews[path] = outcome.preview
        owners[path] = owner
        if outcome.url != candidate.target.url:
            self._visited_urls.add(outcome.url)
        if outcome.events:
            self._findings.append(
                DiagnosticFinding(
                    variant=self._lane_name,
                    parent_id=owner,
                    action=candidate.target,
                    events=outcome.events,
                ),
            )
            if self._reporter is not None:
                self._reporter.diagnostics(events=outcome.events)
        if (
            ImageSimilarity.compare(
                first=parent_preview,
                second=outcome.preview,
            )
            >= self._options.similarity
        ):
            return
        if any(
            comparison.result.similarity >= self._options.similarity
            for comparison in self._similarity.compare_history(
                source=outcome.preview,
                remember=False,
            )
        ):
            return
        child: StateNode = await self._remember_state(
            page=worker.page,
            parent_id=owner,
            path=path,
            preview=outcome.preview,
            parent_preview=parent_preview,
        )
        owners[path] = child.id

    def _report(self: Self, *, step: str, detail: str) -> None:
        """Publish lane progress across the map and capture phases.

        Mapping fills the first 30% (states crawled out of states
        known); capturing fills the rest against the mapped candidate
        count, which is also published as ``completed/total``.

        Args:
            step: Lane step label.
            detail: Human-readable detail.

        """
        mapping: float = self._mapped / max(self._known, 1)
        capturing: float = self._clicked / max(self._planned, 1)
        share: float = (
            ExplorerDefaults.MAP_SHARE
            + (1 - ExplorerDefaults.MAP_SHARE) * capturing
            if self._capturing
            else ExplorerDefaults.MAP_SHARE * mapping
        )
        if self._reporter is not None:
            self._reporter.lane(
                update=LaneUpdate(
                    name=self._lane_name,
                    state="RUNNING",
                    completed=self._clicked,
                    total=max(self._planned, self._clicked),
                    step=step,
                    detail=detail,
                    share=share,
                ),
            )

    async def _reset(
        self: Self,
        page: Page,
        path: tuple[ClickTarget, ...],
    ) -> None:
        """Reload the initial URL and replay an interaction path.

        Args:
            page: Browser page to reset.
            path: Click sequence recreating the desired state.

        Raises:
            Error: When navigation fails for a reason other than a
                racing client-side redirect.

        """
        try:
            _ = await page.goto(
                url=self._options.url,
                wait_until="domcontentloaded",
                timeout=ExplorerDefaults.PAGE_TIMEOUT_MS,
            )
        except Error as exc:
            if "interrupted by another navigation" not in str(object=exc):
                raise
            # A client-side redirect won the race; the page still lands
            # where the application sent it.
            await page.wait_for_load_state(
                state="domcontentloaded",
                timeout=ExplorerDefaults.PAGE_TIMEOUT_MS,
            )
        await self._settle(page=page)
        for target in path:
            if not await self._click(page=page, target=target):
                break

    async def _targets(self: Self, page: Page) -> tuple[ClickTarget, ...]:
        """Return visible, enabled click candidates for the current state.

        Args:
            page: Browser page being inspected.

        Returns:
            Stable target descriptors for the current DOM state.

        """
        locator: Locator = page.locator(
            selector=self._options.include_selector
            or ExplorerDefaults.CLICKABLE,
        )
        count: int = await locator.count()
        targets: list[ClickTarget] = []
        for index in range(count):
            candidate: Locator = locator.nth(index=index)
            try:
                if (
                    not await candidate.is_visible()
                    or not await candidate.is_enabled()
                ):
                    continue
                label: str = await self._label(locator=candidate)
                facts: dict[str, str | int] = cast(
                    typ="dict[str, str | int]",
                    val=await candidate.evaluate(
                        expression=ExplorerDefaults.DESCRIBE,
                    ),
                )
            except Error:
                continue
            if not self._options.unsafe and ExplorerDefaults.DANGEROUS.search(
                string=label,
            ):
                continue
            is_link: bool = (
                bool(facts["href"]) and str(object=facts["tag"]) == "a"
            )
            if (is_link and not self._options.follow_links) or (
                not is_link and not self._options.click_controls
            ):
                continue
            targets.append(
                ClickTarget(
                    index=index,
                    label=label,
                    tag=str(object=facts["tag"]),
                    href=str(object=facts["href"]),
                    selector=str(object=facts["selector"]),
                    url=page.url,
                    x=int(facts["x"]),
                    y=int(facts["y"]),
                ),
            )
        return tuple(targets)

    async def _click(self: Self, page: Page, target: ClickTarget) -> bool:
        """Click one replay target and settle the resulting UI.

        Args:
            page: Browser page containing the target.
            target: Target descriptor discovered in this state.

        Returns:
            Whether the interaction completed successfully.

        """
        locator: Locator = page.locator(
            selector=ExplorerDefaults.CLICKABLE,
        ).nth(index=target.index)
        try:
            if (
                not await locator.is_visible()
                or not await locator.is_enabled()
            ):
                return False
            await locator.scroll_into_view_if_needed()
            await locator.click(timeout=self._options.timeout_ms)
            await self._settle(page=page)
        except Error:
            return False
        return True

    async def _remember_state(
        self: Self,
        page: Page,
        parent_id: str | None,
        path: tuple[ClickTarget, ...],
        preview: bytes,
        parent_preview: bytes | None,
    ) -> StateNode:
        """Persist a distinctive state using the existing capture tool.

        Args:
            page: Page currently displaying the state.
            parent_id: Parent state identifier.
            path: Replay path reaching the state.
            preview: Viewport screenshot used for state comparison.
            parent_preview: Parent viewport screenshot when available.

        Returns:
            Newly recorded state metadata.

        """
        state_id: str = self._state_id(path=path, url=page.url)
        destination: Path = (
            self._options.output
            / f"{self._url_slug(url=page.url)}__{state_id}.png"
        )
        capture: SnapshotCapture = SnapshotCapture(
            page=page,
            target=self._options.target,
            options=SnapshotOptions(),
        )
        if self._options.capture_ui_changes:
            _ = await capture.capture(path=destination)
        _ = self._similarity.remember(source=preview)
        state: StateNode = StateNode(
            id=state_id,
            parent_id=parent_id,
            path=path,
            url=page.url,
            screenshot=destination.name
            if self._options.capture_ui_changes
            else "",
            similarity_to_parent=(
                None
                if parent_preview is None
                else ImageSimilarity.compare(
                    first=parent_preview,
                    second=preview,
                )
            ),
        )
        self._states.append(state)
        self._report(step="capture", detail=f"captured {destination.name}")
        return state

    async def _route(self: Self, route: Route) -> None:
        """Block mutating HTTP requests, or every non-GET with ``only_get``.

        Args:
            route: Intercepted Playwright route.

        """
        method: str = route.request.method.upper()
        if (
            method != "GET"
            if self._options.only_get
            else (
                not self._options.unsafe
                and method in ExplorerDefaults.MUTATING_METHODS
            )
        ):
            self._blocked_requests.append(f"{method} {route.request.url}")
            await route.abort(error_code="blockedbyclient")
            return
        await route.continue_()

    async def _settle(self: Self, page: Page) -> None:
        """Wait for animations and asynchronous UI reactions.

        Args:
            page: Browser page to settle.

        """
        await page.wait_for_timeout(timeout=self._options.settle_ms)

    async def _viewport(self: Self, page: Page) -> bytes:
        """Capture the content area for visual comparison.

        The capture target (``body`` by default) is shot at CSS scale, so
        the image spans exactly the rendered content: it is independent
        of the scroll position, includes content unveiled below the fold,
        and is not diluted by empty viewport space on tall devices.

        Args:
            page: Browser page to capture.

        Returns:
            PNG screenshot bytes.

        """
        try:
            return await page.locator(
                selector=self._options.target,
            ).first.screenshot(
                type="png",
                animations="disabled",
                caret="hide",
                scale="css",
            )
        except Error:
            return await page.screenshot(
                type="png",
                animations="disabled",
                caret="hide",
                full_page=True,
                scale="css",
            )

    def _url_slug(self: Self, *, url: str) -> str:
        """Return a filename-safe form of ``url`` relative to the start URL.

        Args:
            url: URL displayed by a state.

        Returns:
            For example ``root``, ``page`` or ``docs_guide-q-tab-2``.

        """
        start: ParseResult = urlparse(url=self._options.url)
        current: ParseResult = urlparse(url=url)
        path: str = current.path
        if current.netloc == start.netloc:
            base: str = start.path.rsplit(sep="/", maxsplit=1)[0]
            path = path.removeprefix(base)
        relative: str = path.strip("/") + (
            f"-q-{current.query}" if current.query else ""
        )
        return (
            re_sub(
                pattern=r"[^A-Za-z0-9._-]+",
                repl="_",
                string=relative,
            ).strip("_")
            or "root"
        )


class CaptureMatrix:
    """Run responsive light/dark explorations concurrently."""

    def __init__(
        self: Self,
        options: ExplorerOptions,
        reporter: LaneReporter | None = None,
    ) -> None:
        """Initialize the matrix runner.

        Args:
            options: Base exploration configuration.
            reporter: Optional live progress sink.

        """
        self._options: ExplorerOptions = options
        self._reporter: LaneReporter | None = reporter

    async def run(self: Self) -> MatrixResult:
        """Run all device and theme variants concurrently.

        Returns:
            Structured run outcome covering states, diagnostics, findings,
            and intercepted mutations for every variant.

        """
        variants: tuple[CaptureVariant, ...] = self._variants()
        plans: dict[str, Future[tuple[_Candidate, ...]]] = {}
        mappers: set[str] = set()
        for variant in variants:
            device: str = variant.name.rsplit(sep="-", maxsplit=1)[0]
            if device not in plans:
                plans[device] = get_running_loop().create_future()
                mappers.add(variant.name)
        explorers: dict[str, ClickExplorer] = {
            variant.name: ClickExplorer(
                options=ExplorerOptions(
                    url=self._options.url,
                    output=self._options.output / variant.name,
                    target=self._options.target,
                    similarity=self._options.similarity,
                    max_depth=self._options.max_depth,
                    max_states=self._options.max_states,
                    settle_ms=self._options.settle_ms,
                    timeout_ms=self._options.timeout_ms,
                    width=variant.width,
                    height=variant.height,
                    scale=variant.scale,
                    headless=self._options.headless,
                    unsafe=self._options.unsafe,
                    exhaustive=self._options.exhaustive,
                    workers=self._options.workers,
                    only_get=self._options.only_get,
                    variant=variant,
                ),
                reporter=self._reporter,
                lane_name=variant.name,
                plan=(
                    plans[variant.name.rsplit(sep="-", maxsplit=1)[0]],
                    variant.name in mappers,
                ),
            )
            for variant in variants
        }
        tasks: dict[str, Task[tuple[StateNode, ...]]] = {}
        async with TaskGroup() as group:
            tasks = {
                name: group.create_task(
                    coro=self._run_lane(name=name, explorer=explorer),
                    name=name,
                )
                for name, explorer in explorers.items()
            }
        return MatrixResult(
            variants=variants,
            results={name: task.result() for name, task in tasks.items()},
            diagnostics={
                name: explorer.diagnostics
                for name, explorer in explorers.items()
            },
            findings={
                name: explorer.findings for name, explorer in explorers.items()
            },
            blocked={
                name: explorer.blocked for name, explorer in explorers.items()
            },
            candidates={
                name: explorer.planned for name, explorer in explorers.items()
            },
        )

    async def _run_lane(
        self: Self,
        *,
        name: str,
        explorer: ClickExplorer,
    ) -> tuple[StateNode, ...]:
        """Run one lane while publishing lifecycle progress.

        Args:
            name: Variant name used in progress events.
            explorer: Lane explorer to run.

        Returns:
            Distinctive states discovered by the lane.

        """
        if self._reporter is not None:
            self._reporter.lane(
                update=LaneUpdate(
                    name=name,
                    state="RUNNING",
                    completed=0,
                    total=1,
                    step="explore",
                ),
            )
        states: tuple[StateNode, ...] = await explorer.run()
        if self._reporter is not None:
            self._reporter.lane(
                update=LaneUpdate(
                    name=name,
                    state="DONE",
                    completed=explorer.planned,
                    total=max(explorer.planned, 1),
                    step="complete",
                    detail=f"{len(states)} distinctive states",
                ),
            )
        return states

    def _variants(self: Self) -> tuple[CaptureVariant, ...]:
        """Build the default six-way responsive/theme matrix.

        Returns:
            Desktop, tablet, and phone in light and dark modes.

        """
        devices: tuple[tuple[str, int, int, bool, bool], ...] = (
            (
                "desktop",
                self._options.width,
                self._options.height,
                False,
                False,
            ),
            (
                "tablet",
                ExplorerDefaults.TABLET_WIDTH,
                ExplorerDefaults.TABLET_HEIGHT,
                True,
                True,
            ),
            (
                "phone",
                ExplorerDefaults.PHONE_WIDTH,
                ExplorerDefaults.PHONE_HEIGHT,
                True,
                True,
            ),
        )
        schemes: tuple[Literal["dark", "light"], ...] = ("light", "dark")
        return tuple(
            CaptureVariant(
                name=f"{device}-{scheme}",
                width=width,
                height=height,
                color_scheme=scheme,
                is_mobile=is_mobile,
                has_touch=has_touch,
                scale=self._options.scale,
            )
            for device, width, height, is_mobile, has_touch in devices
            for scheme in schemes
        )
