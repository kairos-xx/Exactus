#!/usr/bin/env python3
# Copyright (c) 2026
"""Replay a crawler visit plan across parallel device and theme lanes.

The visitor loads a ``crawler.py`` JSON plan — interface URLs, the
Playwright actions needed to open each, plus the device and theme
matrix — then drives headless Chromium through every combination in
parallel lanes: one Playwright window per ``device/theme`` pair.

Artifacts land under the output directory::

    VISIT/
      FRONTEND/<device>/<theme>/<number>-<name>.<ext>
                                   — number is stable across every lane;
                                     similarity filtering may leave gaps
      REPORTS/crawler.json       — the consumed plan, verbatim
      REPORTS/console.json       — browser console output, args
                                   expanded and serialized as JSON
      REPORTS/server.json        — every HTTP exchange with the
                                   running server (optional)
      REPORTS/screenshots.json   — capture manifest: Playwright
                                   settings, paths, durations
"""

from __future__ import annotations

from asyncio import Queue, Semaphore, create_task, gather, get_running_loop
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from time import perf_counter
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast, final
from urllib.parse import parse_qsl, urlparse

from playwright.async_api import (
    BrowserContext,
    ConsoleMessage,
    Error,
    Page,
    Request,
    async_playwright,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

if __package__ in (None, ""):
    root: Path = Path(__file__).resolve().parents[3]
    sys_path.insert(0, str(object=root))
from exactus.tools.record.capture_screen import (
    SnapshotCapture,
    SnapshotOptions,
)
from exactus.tools.record.crawler import (
    CrawlerDefaults,
    DeviceSpec,
    JsonValue,
    ThemeName,
    VisitAction,
    VisitPlan,
    VisitStep,
    dismiss_wizard,
    route_mutations,
    settle_content,
    slug,
    storage_seed,
)
from exactus.tools.record.similarity import ImageSimilarity
from exactus.tools.record.sprint import sprint

if TYPE_CHECKING:
    from asyncio import Task
    from collections.abc import Awaitable, Callable

    from playwright.async_api._generated import (
        Browser,
        JSHandle,
        Locator,
        Response,
    )

    from exactus.tools.record.capture_screen import Capture
    from exactus.tools.record.similarity import CachedComparison


class VisitDefaults:
    """Store immutable visit configuration values.

    Attributes:
        root: Repository root resolved from this file.
        output: Default artifact directory.
        visit_attempts: Total replay attempts per visit. A failed
            navigation retries directly so a reload cannot race it.

    """

    root: ClassVar[Path] = Path(__file__).resolve().parents[2]
    output: ClassVar[Path] = root / "VISIT"
    visit_attempts: ClassVar[int] = 2


type LaneItem = tuple[
    VisitStep | None,
    ConsoleMessage | Request | BaseException,
]


class VisitSkipError(Exception):
    """Signal that a recorded action has no control in this lane.

    The plan is recorded on the first device; responsive lanes can
    legitimately lack the recorded control — a collapsed mobile menu
    or a disabled wizard step has no clickable target. Those visits
    report a skip rather than a timeout failure.
    """


@dataclass(frozen=True, slots=True)
class CaptureSettings:
    """Bundle the capture and replay settings recorded in the manifest.

    Attributes:
        selector: CSS selector expanded vertically before capture.
        target_only: Clip the image to the target element's box.
        image_type: Image encoding format.
        quality: JPEG quality, 0-100; ignored for PNG output.
        scale: ``css`` for CSS pixels or ``device`` for device pixels.
        max_height: Maximum captured image height.
        workers: Parallel Playwright windows; ``0`` means one per lane.
        similarity_threshold: Maximum similarity a stored capture may
            have against every earlier capture; images at or above the
            threshold are reported as duplicates instead of stored.

    """

    selector: str
    target_only: bool
    image_type: Literal["png", "jpeg"]
    quality: int | None
    scale: Literal["css", "device"]
    max_height: int
    workers: int
    similarity_threshold: float


@dataclass(frozen=True, slots=True)
class ShotRecord:
    """Record the outcome of one replayed interface visit.

    Attributes:
        id: Short visit identifier shared by every lane and report.
        index: Visit position inside the plan.
        name: Interface identifier from the plan.
        url: URL visited.
        device: Device lane name.
        theme: Emulated color scheme.
        ok: Whether the visit captured without errors.
        path: Saved screenshot path, when captured and stored.
        duration_ms: Wall-clock duration of the visit.
        truncated_height: Whether capture hit the height cap.
        duplicate: Whether an earlier capture matched above the
            similarity threshold, so this image was not stored.
        similarity: Highest similarity found against earlier captures.
        error: Failure description, when failed.
        skipped: Reason the recorded action had no applicable control
            in this lane; empty when the visit was replayed.

    """

    id: str
    index: int
    name: str
    url: str
    device: str
    theme: str
    ok: bool
    path: str
    duration_ms: float
    truncated_height: bool
    duplicate: bool
    similarity: float
    error: str
    skipped: str = ""


@dataclass(frozen=True, slots=True)
class VisitReport:
    """Aggregate everything the parallel replay observed.

    Attributes:
        results: Per-capture outcomes.
        console: Serialized browser console entries.
        server: Serialized HTTP exchanges with the running server.
        mutations: Mutating request signatures blocked en route.

    """

    results: list[ShotRecord]
    console: list[dict[str, JsonValue]]
    server: list[dict[str, JsonValue]]
    mutations: list[str]


@dataclass(frozen=True, slots=True)
class LaneWork:
    """Describe one lane's replay assignment.

    Attributes:
        device: Device lane emulated by the context.
        theme: Color scheme emulated by the context.
        visits: ``(index, step)`` pairs replayed in plan order.
        directory: Screenshot directory for this lane.

    """

    device: DeviceSpec
    theme: ThemeName
    visits: list[tuple[int, VisitStep]]
    directory: Path


@dataclass(frozen=True, slots=True)
class LaneSinks:
    """Collect the shared report sinks lanes append into.

    Attributes:
        results: Sink receiving per-capture outcomes.
        console: Sink receiving console entries.
        server: Sink receiving server exchange entries.
        mutations: Sink receiving blocked mutating signatures.

    """

    results: list[ShotRecord]
    console: list[dict[str, JsonValue]]
    server: list[dict[str, JsonValue]]
    mutations: list[str]


@dataclass(slots=True)
class Progress:
    """Track shared replay progress for the single-line bar.

    Attributes:
        done: Visits completed across all lanes.
        total: Visits planned across all lanes.

    """

    done: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class VisitTask:
    """One plan step replayed inside a lane.

    Attributes:
        step: Visit step replayed.
        index: Visit position inside the plan.
        number: Stable logical screenshot number shared by every lane.

    """

    step: VisitStep
    index: int
    number: int


@dataclass(frozen=True, slots=True)
class VisitOptions:
    """Run-time replay switches shared by every lane.

    Attributes:
        machine: Workload identifier seeded as the current selection.
        server_log: Whether HTTP exchanges feed ``server.json``.
        dedup: Whether each lane deduplicates through ``similarity.py``.
        on_progress: Optional progress reporter called after each visit
            with keyword fields; ``None`` reports nothing.

    """

    machine: str
    server_log: bool
    dedup: bool
    on_progress: Callable[..., None] | None = None


@dataclass(frozen=True, slots=True)
class LaneMatrix:
    """Device/theme combinations fanned out into lanes.

    Attributes:
        devices: Device lanes selected for this run.
        themes: Themes selected for this run.

    """

    devices: tuple[DeviceSpec, ...]
    themes: tuple[ThemeName, ...]


@dataclass(frozen=True, slots=True)
class LaneOutputs:
    """Shared report sinks and progress a lane appends into.

    Attributes:
        sinks: Shared report sinks.
        progress: Shared replay progress.

    """

    sinks: LaneSinks
    progress: Progress


@final
class Constants:
    """Group module-level constants.

    Attributes:
        sensitive_headers: Grouped module constant.
        post_limit: Grouped module constant.

    """

    sensitive_headers: Final[frozenset[str]] = frozenset(
        {
            "authorization",
            "cookie",
            "proxy-authorization",
            "set-cookie",
            "x-api-key",
        },
    )
    post_limit: Final[int] = 2048


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Mask credential-bearing headers in a serialized header set.

    Args:
        headers: Header name/value mapping.

    Returns:
        Copy with sensitive values replaced by ``<redacted>``.

    """
    return {
        name: (
            "<redacted>"
            if name.lower() in Constants.sensitive_headers
            else value
        )
        for name, value in headers.items()
    }


def post_payload(request: Request) -> JsonValue:
    """Serialize a request body; truncate text and mark binary data.

    Args:
        request: Playwright request object.

    Returns:
        Decoded text (truncated past ``POST_LIMIT``), a binary
        placeholder, or ``None`` when the request has no body.

    """
    raw: bytes | None = request.post_data_buffer
    if raw is None:
        return None
    try:
        text: str = raw.decode(encoding="utf-8")
    except UnicodeDecodeError:
        return f"<binary {len(raw)} bytes>"
    return (
        text
        if len(text) <= Constants.post_limit
        else (
            f"{text[: Constants.post_limit]}<truncated"
            f" {len(text) - Constants.post_limit} chars>"
        )
    )


def store_sync(path: Path, data: bytes) -> None:
    """Write capture bytes to disk; called inside an executor.

    Args:
        path: Destination file.
        data: Encoded image bytes.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(data=data)


def progress_line(done: int, total: int, label: str) -> str:
    """Render the single-line progress bar.

    Args:
        done: Completed visits.
        total: Planned visits.
        label: Current visit description.

    Returns:
        Carriage-return-prefixed status line.

    """
    width: int = 28
    ratio: float = done / total if total else 1.0
    filled: int = int(width * ratio)
    bar: str = "#" * filled + "-" * (width - filled)
    return f"\r[{bar}] {done}/{total} {label[:64]}".ljust(110)


async def serialize_arg(handle: JSHandle) -> JsonValue:
    """Expand one console argument into a JSON-serializable value.

    Args:
        handle: Playwright handle to the console argument.

    Returns:
        JSON value, a string fallback, or ``None``.

    """
    try:
        return cast(typ="JsonValue", val=await handle.json_value())
    except Error:
        try:
            return cast(
                typ="JsonValue",
                val=await handle.evaluate(expression="v => String(v)"),
            )
        except Error:
            return None


async def console_entry(
    message: ConsoleMessage,
    *,
    visit: str,
    visit_id: str,
    device: str,
    theme: str,
) -> dict[str, JsonValue]:
    """Serialize one console message with expanded arguments.

    Args:
        message: Browser console message.
        visit: Interface visit active when the message arrived.
        visit_id: Short identifier of the active visit.
        device: Device lane name.
        theme: Emulated color scheme.

    Returns:
        JSON-serializable console entry.

    """
    args: list[JsonValue] = [
        await serialize_arg(handle=handle) for handle in message.args
    ]
    return {
        "id": visit_id,
        "visit": visit,
        "device": device,
        "theme": theme,
        "type": message.type,
        "text": message.text,
        "location": cast(typ="JsonValue", val=dict(message.location)),
        "args": args,
    }


async def server_entry(
    request: Request,
    *,
    visit: str,
    visit_id: str,
    device: str,
    theme: str,
) -> dict[str, JsonValue]:
    """Serialize one finished or failed HTTP exchange.

    Args:
        request: Playwright request object.
        visit: Interface visit active when the exchange ended.
        visit_id: Short identifier of the active visit.
        device: Device lane name.
        theme: Emulated color scheme.

    Returns:
        JSON-serializable server exchange entry.

    """
    response: Response | None = await request.response()
    timing: dict[str, object] = dict(request.timing)
    duration: float = cast(typ="float", val=timing.get("responseEnd", -1.0))
    failure: str | None = request.failure
    query: dict[str, str] = dict(
        parse_qsl(qs=urlparse(url=request.url).query, keep_blank_values=True),
    )
    response_headers: dict[str, str] = (
        redact_headers(headers=response.headers) if response else {}
    )
    return {
        "id": visit_id,
        "visit": visit,
        "device": device,
        "theme": theme,
        "method": request.method,
        "url": request.url,
        "query": cast(typ="JsonValue", val=query),
        "resource_type": request.resource_type,
        "headers": cast(
            typ="JsonValue",
            val=redact_headers(headers=request.headers),
        ),
        "post_data": post_payload(request=request),
        "status": response.status if response is not None else None,
        "response_headers": cast(typ="JsonValue", val=response_headers),
        "failure": failure or "",
        "duration_ms": duration if duration >= 0.0 else None,
        "timing": cast(typ="JsonValue", val=timing),
    }


async def drain(
    queue: Queue[LaneItem | None],
    *,
    device: str,
    theme: str,
    console: list[dict[str, JsonValue]],
    server: list[dict[str, JsonValue]],
) -> None:
    """Consume one lane's queued events until the ``None`` sentinel.

    Args:
        queue: Lane event queue; ``None`` ends the drain.
        device: Device lane name.
        theme: Emulated color scheme.
        console: Sink receiving console entries.
        server: Sink receiving server exchange entries.

    """
    while (item := (await queue.get())) is not None:
        step, event = item
        visit: str = step.name if step is not None else ""
        visit_id: str = step.id if step is not None else ""
        if isinstance(event, ConsoleMessage):
            console.append(
                await console_entry(
                    message=event,
                    visit=visit,
                    visit_id=visit_id,
                    device=device,
                    theme=theme,
                ),
            )
        elif isinstance(event, Request):
            server.append(
                await server_entry(
                    request=event,
                    visit=visit,
                    visit_id=visit_id,
                    device=device,
                    theme=theme,
                ),
            )
        else:
            console.append(
                {
                    "id": visit_id,
                    "visit": visit,
                    "device": device,
                    "theme": theme,
                    "type": "pageerror",
                    "text": str(object=event),
                    "location": None,
                    "args": [],
                },
            )


async def _require_control(*, target: Locator, action: VisitAction) -> None:
    """Require the recorded control to exist and accept input.

    Args:
        target: Resolved locator for the action's control.
        action: Recorded interaction being replayed.

    Raises:
        VisitSkipError: When the control is absent or disabled.

    """
    reason: str = ""
    try:
        await target.first.wait_for(
            state="attached",
            timeout=CrawlerDefaults.action_timeout_ms,
        )
    except PlaywrightTimeoutError:
        reason = "absent"
    else:
        if await target.first.is_disabled():
            reason = "disabled"
    if reason:
        msg: str = (
            f"{action.kind} target {reason}: {action.selector}[{action.index}]"
        )
        raise VisitSkipError(msg)


async def perform(page: Page, action: VisitAction) -> None:
    """Apply one plan action to the current page.

    Args:
        page: Playwright page.
        action: Recorded interaction to replay.

    """
    if action.kind == "click":
        needle: str = " ".join(action.text.split())
        target: Locator = page.locator(
            selector=action.selector,
            has_text=needle,
        )
        if await target.count() == 0:
            target = page.locator(selector=action.selector).nth(
                index=action.index,
            )
        await _require_control(target=target, action=action)
        try:
            await target.first.click(timeout=CrawlerDefaults.action_timeout_ms)
        except Error:
            dispatch: Callable[..., Awaitable[None]] = cast(
                typ="Callable[..., Awaitable[None]]",
                val=target.first.dispatch_event,
            )
            await dispatch(type="click")
    elif action.kind == "select":
        target = page.locator(selector=action.selector).nth(index=action.index)
        await _require_control(target=target, action=action)
        _ = await target.select_option(
            value=action.value,
            timeout=CrawlerDefaults.action_timeout_ms,
        )
    else:
        target = page.locator(selector=action.selector).nth(index=action.index)
        await _require_control(target=target, action=action)
        try:
            await target.click(timeout=CrawlerDefaults.action_timeout_ms)
        except Error:
            dispatch = cast(
                typ="Callable[..., Awaitable[None]]",
                val=target.dispatch_event,
            )
            await dispatch(type="click")
    await page.wait_for_timeout(timeout=CrawlerDefaults.dialog_settle_ms)


async def visit_step(
    page: Page,
    work: LaneWork,
    *,
    task: VisitTask,
    settings: CaptureSettings,
    similarity: ImageSimilarity | None,
) -> ShotRecord:
    """Replay one interface visit and capture the opened state.

    The captured image is fingerprinted and compared in a worker
    thread against every earlier capture of the same device/theme lane
    through ``similarity.py``. Only captures scoring under
    ``settings.similarity_threshold`` are stored and reported as
    valid; anything at or above the threshold is reported as a
    duplicate and dropped. Filename numbers come from the logical plan
    position, not from the number of images retained in a lane. Therefore
    the same interface has the same number in dark/light and
    desktop/tablet/mobile lanes; a lane may intentionally contain gaps when
    similarity filtering drops a capture.

    Args:
        page: Playwright page.
        work: Lane assignment supplying device, theme, and directory.
        task: Plan visit to replay with its filename counter.
        settings: Capture settings forwarded to the expander.
        similarity: Lane dedup engine; ``None`` stores every capture.

    Returns:
        Outcome of the visit.

    """
    step: VisitStep = task.step
    index: int = task.index
    number: int = task.number
    device: DeviceSpec = work.device
    theme: ThemeName = work.theme
    started: float = perf_counter()
    path: Path | None = None
    capture: Capture | None = None
    best: float = 0.0
    duplicate: bool = False
    error: str = ""
    skipped: str = ""
    for attempt in range(VisitDefaults.visit_attempts):
        path = None
        capture = None
        best = 0.0
        duplicate = False
        try:
            navigated: Response | None = await page.goto(
                url=step.url,
                wait_until="domcontentloaded",
            )
            if navigated is None:
                _ = await page.reload(wait_until="domcontentloaded")
            await settle_content(page=page)
            await dismiss_wizard(page=page)
            for action in step.actions:
                await perform(page=page, action=action)
            capture = await SnapshotCapture(
                page=page,
                target=settings.selector,
                options=SnapshotOptions(
                    max_height=settings.max_height,
                    target_only=settings.target_only,
                    image_type=settings.image_type,
                    quality=settings.quality,
                    scale=settings.scale,
                ),
            ).capture(path=None)
            if similarity is not None:
                matches: tuple[
                    CachedComparison,
                    ...,
                ] = await get_running_loop().run_in_executor(
                    executor=None,
                    func=partial(
                        similarity.compare_history,
                        source=capture.data if capture else "",
                    ),
                )
                best = max(
                    (match.result.similarity for match in matches),
                    default=0.0,
                )
                duplicate = best >= settings.similarity_threshold
            if not duplicate:
                prefix: str = f"{number:03d}-{slug(value=step.name)}"
                filename: str = f"{prefix}-{step.id}.{settings.image_type}"
                candidate: Path = work.directory / filename
                await get_running_loop().run_in_executor(
                    executor=None,
                    func=partial(
                        store_sync,
                        path=candidate,
                        data=capture.data if capture else b"",
                    ),
                )
                path = candidate
            error = ""
            break
        except VisitSkipError as caught:
            skipped = str(object=caught)
            break
        except (Error, OSError, RuntimeError, ValueError) as caught:
            error = repr(caught)
            if attempt + 1 >= VisitDefaults.visit_attempts:
                break
    return ShotRecord(
        id=step.id,
        index=index,
        name=step.name,
        url=step.url,
        device=device.name,
        theme=theme,
        ok=not error,
        path=str(object=path) if path is not None else "",
        duration_ms=(perf_counter() - started) * 1000.0,
        truncated_height=(
            capture.truncated_height if capture is not None else False
        ),
        duplicate=duplicate,
        similarity=best,
        error=error,
        skipped=skipped,
    )


async def run_lane(
    browser: Browser,
    *,
    work: LaneWork,
    settings: CaptureSettings,
    options: VisitOptions,
    outputs: LaneOutputs,
) -> None:
    """Replay every visit inside one device/theme Playwright window.

    The dedup engine is lane-local: a capture is only compared
    against earlier captures of the same device and theme, which
    keeps fingerprint history bounded and race-free.

    Args:
        browser: Shared headless browser.
        work: Lane assignment: device, theme, visits, directory.
        settings: Capture settings forwarded to each visit.
        options: Run-time replay switches for this lane.
        outputs: Report sinks and progress for this lane.

    """
    sinks: LaneSinks = outputs.sinks
    progress: Progress = outputs.progress
    device: DeviceSpec = work.device
    theme: ThemeName = work.theme
    similarity: ImageSimilarity | None = (
        ImageSimilarity() if options.dedup else None
    )
    context: BrowserContext = await browser.new_context(
        viewport={"width": device.width, "height": device.height},
        device_scale_factor=device.scale_factor,
        is_mobile=device.mobile,
        has_touch=device.touch,
        color_scheme=theme,
        accept_downloads=False,
    )
    _ = await context.add_init_script(
        script=await storage_seed(theme=theme, machine=options.machine),
    )
    await route_mutations(context=context, sink=sinks.mutations)
    page: Page = await context.new_page()
    page.set_default_timeout(timeout=CrawlerDefaults.page_timeout_ms)
    queue: Queue[LaneItem | None] = Queue()
    state: dict[str, VisitStep | None] = {"step": None}
    page.on(
        event="console",
        f=lambda event: queue.put_nowait(item=(state["step"], event)),
    )
    page.on(
        event="pageerror",
        f=lambda event: queue.put_nowait(item=(state["step"], event)),
    )
    if options.server_log:
        page.on(
            event="requestfinished",
            f=lambda event: queue.put_nowait(item=(state["step"], event)),
        )
        page.on(
            event="requestfailed",
            f=lambda event: queue.put_nowait(item=(state["step"], event)),
        )
    consumer: Task[None] = create_task(
        coro=drain(
            queue=queue,
            device=device.name,
            theme=theme,
            console=sinks.console,
            server=sinks.server,
        ),
    )
    try:
        for index, step in work.visits:
            state["step"] = step
            record: ShotRecord = await visit_step(
                page=page,
                work=work,
                task=VisitTask(step=step, index=index, number=index + 1),
                settings=settings,
                similarity=similarity,
            )
            sinks.results.append(record)
            progress.done += 1
            if options.on_progress is not None:
                options.on_progress(
                    state="RUNNING",
                    completed=progress.done,
                    total=progress.total,
                    step="capture",
                    detail=f"{device.name}/{theme} {step.name}",
                )
            sprint(
                progress_line(
                    done=progress.done,
                    total=progress.total,
                    label=f"{device.name}/{theme} {step.name}",
                ),
                end="",
                file=stdout,
            )
    finally:
        queue.put_nowait(item=None)
        await consumer
        await context.close()


async def run_visits(
    plan: VisitPlan,
    *,
    shots: Path,
    settings: CaptureSettings,
    matrix: LaneMatrix,
    options: VisitOptions,
) -> VisitReport:
    """Replay every visit across parallel device/theme windows.

    Args:
        plan: Crawler visit plan.
        shots: Root screenshot directory.
        settings: Capture settings forwarded to each visit.
        matrix: Device/theme combinations fanned out into lanes.
        options: Run-time replay switches shared by every lane.

    Returns:
        Aggregated replay report.

    """
    lanes: list[LaneWork] = [
        LaneWork(
            device=device,
            theme=theme,
            visits=list(enumerate(iterable=plan.visits)),
            directory=shots / device.name / theme,
        )
        for device in matrix.devices
        for theme in matrix.themes
    ]
    gate: Semaphore = Semaphore(
        value=settings.workers if settings.workers > 0 else len(lanes),
    )
    sinks: LaneSinks = LaneSinks(
        results=[],
        console=[],
        server=[],
        mutations=[],
    )
    progress: Progress = Progress(done=0, total=len(lanes) * len(plan.visits))

    async def lane(browser: Browser, work: LaneWork) -> None:
        """Run one lane behind the worker semaphore.

        Args:
            browser: Shared headless browser.
            work: Lane assignment executed by this window.

        """
        async with gate:
            await run_lane(
                browser=browser,
                work=work,
                settings=settings,
                options=options,
                outputs=LaneOutputs(sinks=sinks, progress=progress),
            )

    async with async_playwright() as playwright:
        browser: Browser = await playwright.chromium.launch(headless=True)
        try:
            _ = await gather(
                *(lane(browser=browser, work=work) for work in lanes),
            )
        finally:
            await browser.close()
    sinks.results.sort(key=lambda r: (r.index, r.device, r.theme))
    return VisitReport(
        results=sinks.results,
        console=sinks.console,
        server=sinks.server,
        mutations=sinks.mutations,
    )
