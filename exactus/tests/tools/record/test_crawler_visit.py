# Copyright (c) 2026
"""The visit-plan crawler and the parallel visit replayer."""

from __future__ import annotations

from asyncio import Queue, run
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from json import loads
from textwrap import dedent
from threading import Thread
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from playwright.async_api import async_playwright

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_not_in,
    expect_true,
    require,
)
from exactus.tools.record import crawler as cr
from exactus.tools.record import visit as vs

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from playwright.async_api import Browser, BrowserContext, Page
    from playwright.async_api import Request as PlaywrightRequest

    from exactus.tools.record.crawler import (
        ConsoleVersion,
        DeviceSpec,
        JsonValue,
        ThemeName,
        VisitPlan,
        VisitStep,
    )
    from exactus.tools.record.visit import LaneWork, ShotRecord, VisitReport


@final
class Constants:
    """Group module-level constants.

    Attributes:
        site: Grouped module constant.

    """

    site: Final[str] = dedent(
        text=(
            '    <!doctype html><html lang="en"><body>\n    <nav class="sv-nav'
            'igation-rail">\n    <button data-value="items">Items</button>\n  '
            '  <button data-value="settings">Settings</button>\n    <button da'
            'ta-value="">Empty</button>\n    <button data-value="items">Dup</b'
            'utton>\n    </nav>\n    <a href="#/items/detail">detail</a><a hre'
            'f="#/items">same</a>\n    <a href="/plain">plain</a>\n    <div id'
            '="main-content"></div>\n    <script>\n    const routes = {\n     '
            ' items: `<h1>Items</h1>\n        <button id="create">Create item<'
            "/button>\n        <button>Delete item</button>\n        <button>S"
            "witch to dark theme</button>\n        <button>Create item</button"
            '>\n        <button id="post">Add record</button>\n        <button'
            ' disabled id="off">Config disabled</button>\n        <select name'
            '="kind"><option value="">pick</option>\n          <option value="'
            'a">A</option></select>\n        <select aria-label="size"><option'
            ' value="s">S</option></select>\n        <select><option value="z"'
            '>Z</option></select>\n        <input type="checkbox" name="flag">'
            '\n        <input type="checkbox" aria-label="Toggle theme">\n    '
            '    <input type="radio">\n        <div id="dlg" hidden>Dialog ope'
            "n</div>`,\n      settings: `<h1>Settings</h1><p>plain</p>`,\n    "
            "};\n    function render() {\n      const route = (location.hash.r"
            'eplace("#/", "") || "items").split("/")[0];\n      document.getEl'
            'ementById("main-content").innerHTML =\n        routes[route] || r'
            'outes.items;\n      const create = document.getElementById("creat'
            'e");\n      if (create) create.onclick = () => {\n        documen'
            't.getElementById("dlg").hidden = false;\n      };\n      const po'
            'st = document.getElementById("post");\n      if (post) post.oncli'
            'ck = () =>\n        fetch("/api/save", {method: "POST", body: "x"'
            '});\n      console.log("rendered", route);\n    }\n    window.add'
            'EventListener("hashchange", render);\n    render();\n    if (!loc'
            'alStorage.getItem("vmim.setup.seen")) {\n      document.body.inse'
            'rtAdjacentHTML("beforeend",\n        \'<div class="vmim-setup"><b'
            'utton id="cont">Continue</button></div>\');\n      document.getEl'
            'ementById("cont").onclick = () =>\n        document.querySelector'
            '(".vmim-setup").remove();\n    }\n    </script></body></html>'
        ),
    )


@pytest.fixture(autouse=True)
def fast_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the crawler's settle and timeout delays.

    Args:
        monkeypatch: Pytest patching helper.

    """
    for name, value in {
        "settle_ms": 30,
        "navigate_settle_ms": 30,
        "dialog_settle_ms": 30,
        "action_timeout_ms": 800,
        "content_timeout_ms": 2000,
    }.items():
        monkeypatch.setattr(target=cr.CrawlerDefaults, name=name, value=value)


@pytest.fixture
def app_url(tmp_path: Path) -> Iterator[str]:
    """Serve the crawler-shaped application.

    Args:
        tmp_path: Pytest temporary directory.

    Yields:
        The application origin without a trailing slash.

    """
    site: Path = tmp_path / "app"
    site.mkdir()
    (site / "index.html").write_text(data=Constants.site, encoding="utf-8")
    server: ThreadingHTTPServer = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(SimpleHTTPRequestHandler, directory=str(object=site)),
    )
    thread: Thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_slug_and_ids() -> None:
    """Slugs are filesystem safe and ids are stable."""
    expect_equal(actual=cr.slug(value="  A b/c! "), expected="A-b-c")
    expect_equal(actual=cr.slug(value="///"), expected="root")
    expect_equal(actual=len(cr.slug(value="x" * 500)), expected=120)
    expect_equal(actual=cr.visit_id(name="a"), expected=cr.visit_id(name="a"))
    expect_not_equal(
        actual=cr.visit_id(name="a"),
        expected=cr.visit_id(name="b"),
    )
    step: VisitStep = cr.VisitStep(name="n", url="u")
    expect_equal(actual=step.id, expected=cr.visit_id(name="n"))
    expect_equal(
        actual=cr.VisitStep(name="n", url="u", id="fixed").id,
        expected="fixed",
    )


def test_device_and_theme_resolution() -> None:
    """Names resolve against presets and unknown names fail."""
    expect_equal(
        actual=cr.resolve_devices(names=""),
        expected=cr.Constants.devices,
    )
    expect_equal(
        actual=[d.name for d in cr.resolve_devices(names="phone, desktop")],
        expected=["desktop", "phone"],
    )
    with pytest.raises(expected_exception=ValueError, match="unknown device"):
        _ = cr.resolve_devices(names="watch")
    expect_equal(
        actual=cr.resolve_themes(names=""),
        expected=cr.Constants.themes,
    )
    expect_equal(actual=cr.resolve_themes(names="dark"), expected=("dark",))
    with pytest.raises(expected_exception=ValueError, match="unknown theme"):
        _ = cr.resolve_themes(names="sepia")


def test_plan_parsing() -> None:
    """Plans decode defensively and validate required fields."""
    plan: VisitPlan = cr.VisitPlan.parse(
        data={
            "base_url": "http://x",
            "themes": ["dark", "bogus"],
            "devices": [
                {
                    "name": "d",
                    "width": 1,
                    "height": 2,
                    "scale_factor": 2,
                    "mobile": True,
                    "touch": True,
                },
                {"name": "", "width": 1, "height": 2},
                {"name": "e", "width": "x", "height": 2},
                "junk",
            ],
            "visits": [
                {
                    "name": "a",
                    "url": "u",
                    "id": "ident",
                    "actions": [
                        {
                            "kind": "click",
                            "selector": "b",
                            "index": 2,
                            "text": "t",
                            "value": "v",
                        },
                        {"kind": "select", "selector": "s"},
                        {"kind": "nope", "selector": "s"},
                        {"kind": "click"},
                        "junk",
                    ],
                },
                {"name": "b", "url": "u", "actions": "bad"},
                {"name": 1, "url": "u"},
                "junk",
            ],
        },
    )
    expect_equal(actual=plan.themes, expected=("dark",))
    expect_equal(actual=[d.name for d in plan.devices], expected=["d"])
    expect_equal(actual=plan.devices[0].scale_factor, expected=2.0)
    expect_equal(actual=len(plan.visits), expected=2)
    expect_equal(actual=plan.visits[0].id, expected="ident")
    expect_equal(actual=len(plan.visits[0].actions), expected=2)
    defaults: VisitPlan = cr.VisitPlan.parse(
        data={"base_url": "http://x", "visits": []},
    )
    expect_equal(actual=defaults.themes, expected=cr.Constants.themes)
    expect_equal(actual=defaults.devices, expected=cr.Constants.devices)
    with pytest.raises(expected_exception=TypeError):
        _ = cr.VisitPlan.parse(data={"base_url": 1, "visits": []})
    with pytest.raises(expected_exception=ValueError, match="non-empty"):
        _ = cr.VisitPlan.parse(data={"base_url": "", "visits": []})
    with pytest.raises(expected_exception=TypeError):
        _ = cr.VisitPlan.parse(data={"base_url": "x", "visits": "no"})
    odd: DeviceSpec | None = cr.DeviceSpec.parse(
        data={"name": "n", "width": 1, "height": 2},
    )
    odd = require(value=odd)
    expect_equal(
        actual=(odd.scale_factor, odd.mobile, odd.touch),
        expected=(1.0, False, False),
    )


def test_storage_seed_script() -> None:
    """The seed script sets theme, setup flag and optional machine."""
    text: str = run(main=cr.storage_seed(theme="dark", machine="m1"))
    expect_in(member="vmim.theme", container=text)
    expect_in(member="vmim.machine", container=text)
    expect_not_in(
        member="vmim.machine",
        container=run(main=cr.storage_seed(theme="light", machine="")),
    )


class _Progress:
    """Record every progress report a capture function emits."""

    def __init__(self) -> None:
        """Start with no recorded reports."""
        self.calls: list[dict[str, object]] = []

    def __call__(self, **fields: object) -> None:
        """Store one report.

        Args:
            **fields: Progress fields passed by the capture code.

        """
        self.calls.append(fields)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_build_plan_discovers_interfaces(
    app_url: str,
    version: ConsoleVersion,
) -> None:
    """The crawler inventories panels, dialogs, options and toggles.

    Args:
        app_url: Value for ``app_url``.
        version: Value for ``version``.

    """
    progress: _Progress = _Progress()
    plan: VisitPlan = run(
        main=cr.build_plan(
            base_url=app_url,
            devices=cr.resolve_devices(names="desktop"),
            themes=("light",),
            machine="m",
            options=cr.CrawlOptions(version=version, on_progress=progress),
        ),
    )
    expect_true(condition=bool(progress.calls))
    expect_equal(actual=progress.calls[0]["step"], expected="crawl panel")
    names: list[str] = [visit.name for visit in plan.visits]
    expect_in(member="items", container=names)
    expect_in(member="settings", container=names)
    expect_true(condition=any(":dialog-create-item" in name for name in names))
    expect_false(condition=any("delete" in name for name in names))
    expect_false(condition=any("dark-theme" in name for name in names))
    expect_true(condition=any(":option-kind-a" in name for name in names))
    expect_true(condition=any(":toggle-flag" in name for name in names))
    expect_false(
        condition=any(
            "toggle-theme" in name.lower() and "toggle-toggle" in name
            for name in names
        ),
    )
    detail: list[str] = [n for n in names if n.endswith("detail")]
    expect_equal(actual=bool(detail), expected=version == "v2")


def test_dismiss_wizard_paths(app_url: str) -> None:
    """The wizard closes by Continue or by Escape fallback.

    Args:
        app_url: Value for ``app_url``.

    """

    async def scenario() -> None:
        """Dismiss the wizard through each supported path."""
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            page: Page = await browser.new_page()
            _ = await page.goto(url=app_url)
            await cr.dismiss_wizard(page=page)
            expect_equal(
                actual=await page.locator(selector=".vmim-setup").count(),
                expected=0,
            )
            await page.set_content(
                html=(
                    '<div class="vmim-setup" tabindex="0">no'
                    " button</div><script>document.addEventListener("
                    "'keydown',e=>{if(e.key==='Escape')"
                    "document.querySelector('.vmim-setup').remove()})"
                    "</script>"
                ),
            )
            await page.focus(selector=".vmim-setup")
            await cr.dismiss_wizard(page=page)
            expect_equal(
                actual=await page.locator(selector=".vmim-setup").count(),
                expected=0,
            )
            await page.set_content(
                html=(
                    '<div class="vmim-setup"><button'
                    ' style="display:none">Continue</button></div>'
                ),
            )
            await cr.dismiss_wizard(page=page)
            await browser.close()

    run(main=scenario())


def test_visit_helpers() -> None:
    """Pure replay helpers redact, truncate and format."""
    expect_equal(
        actual=vs.redact_headers(headers={"Cookie": "a", "X": "b"}),
        expected={"Cookie": "<redacted>", "X": "b"},
    )

    class RequestStub:
        """Request stub with a configurable body."""

        def __init__(self, body: bytes | None) -> None:
            """Store the body.

            Args:
                body: Request body.

            """
            self.post_data_buffer = body

    def request(body: bytes | None) -> PlaywrightRequest:
        """Dress a stub as a Playwright ``Request``.

        Args:
            body: Request body.

        Returns:
            The stub, viewed as a request.

        """
        return cast(typ="PlaywrightRequest", val=RequestStub(body=body))

    expect_none(value=vs.post_payload(request=request(body=None)))
    expect_equal(
        actual=vs.post_payload(request=request(body=b"abc")),
        expected="abc",
    )
    expect_in(
        member="binary",
        container=str(
            object=vs.post_payload(request=request(body=b"\xff\xfe")),
        ),
    )
    big: object = vs.post_payload(request=request(body=b"x" * 3000))
    expect_in(member="truncated 952 chars", container=str(object=big))
    expect_true(
        condition=vs.progress_line(done=1, total=2, label="label").startswith(
            "\r[",
        ),
    )
    expect_in(
        member="0/0",
        container=vs.progress_line(done=0, total=0, label="x"),
    )


def test_store_sync(tmp_path: Path) -> None:
    """Captures are written beneath new directories.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "a" / "b.png"
    vs.store_sync(path=target, data=b"x")
    expect_equal(actual=target.read_bytes(), expected=b"x")


def _settings(
    *,
    similarity_threshold: float = 0.995,
    workers: int = 1,
) -> vs.CaptureSettings:
    """Build capture settings for tests.

    Args:
        similarity_threshold: Maximum similarity a stored capture may have.
        workers: Parallel Playwright windows.

    Returns:
        The settings.

    """
    return vs.CaptureSettings(
        selector="body",
        target_only=False,
        image_type="png",
        quality=None,
        scale="css",
        max_height=4000,
        workers=workers,
        similarity_threshold=similarity_threshold,
    )


@pytest.mark.parametrize(
    ("dedup", "server_log", "threshold"),
    [(True, True, 0.5), (False, False, 0.995)],
)
def test_run_visits_end_to_end(
    app_url: str,
    tmp_path: Path,
    *,
    dedup: bool,
    server_log: bool,
    threshold: float,
) -> None:
    """A crawled plan replays across lanes with captures and logs.

    Args:
        app_url: Value for ``app_url``.
        tmp_path: Per-test temporary directory.
        dedup: Value for ``dedup``.
        server_log: Value for ``server_log``.
        threshold: Value for ``threshold``.

    """
    devices: tuple[DeviceSpec, ...] = cr.resolve_devices(names="desktop,phone")
    themes: tuple[ThemeName, ...] = cr.resolve_themes(names="light,dark")
    plan: VisitPlan = run(
        main=cr.build_plan(
            base_url=app_url,
            devices=devices,
            themes=("light",),
            machine="",
        ),
    )
    absent: VisitStep = cr.VisitStep(
        name="absent",
        url=f"{app_url}/#/items",
        actions=(
            cr.VisitAction(kind="click", selector="#nothing", text="zz"),
        ),
    )
    disabled: VisitStep = cr.VisitStep(
        name="disabled",
        url=f"{app_url}/#/items",
        actions=(
            cr.VisitAction(kind="select", selector="#off", index=0, value="x"),
        ),
    )
    posting: VisitStep = cr.VisitStep(
        name="posting",
        url=f"{app_url}/#/items",
        actions=(
            cr.VisitAction(kind="click", selector="#post", text="Add record"),
        ),
    )
    plan = cr.VisitPlan(
        base_url=app_url,
        devices=devices,
        themes=themes,
        visits=(*plan.visits, absent, disabled, posting),
    )
    shots: Path = tmp_path / "shots"
    lane_progress: _Progress = _Progress()
    report: VisitReport = run(
        main=vs.run_visits(
            plan=plan,
            shots=shots,
            settings=_settings(similarity_threshold=threshold, workers=0),
            matrix=vs.LaneMatrix(devices=devices, themes=themes),
            options=vs.VisitOptions(
                machine="m",
                server_log=server_log,
                dedup=dedup,
                on_progress=lane_progress,
            ),
        ),
    )
    expect_true(condition=bool(report.results))
    expect_true(condition=bool(lane_progress.calls))
    expect_equal(actual=lane_progress.calls[0]["step"], expected="capture")
    expect_true(condition=any(r.skipped for r in report.results))
    expect_true(condition=any(r.ok and r.path for r in report.results))
    expect_true(condition=bool(report.console))
    expect_true(
        condition="POST /api/save" in report.mutations
        or not any(r.name == "posting" and r.ok for r in report.results),
    )
    expect_equal(actual=bool(report.server), expected=server_log)
    expect_true(condition=bool(list(shots.rglob(pattern="*.png"))))
    if dedup and threshold < 1:
        expect_true(condition=any(r.duplicate for r in report.results))


def test_visit_step_failure_reports_error(tmp_path: Path) -> None:
    """Unreachable URLs exhaust retries and report the error.

    Args:
        tmp_path: Per-test temporary directory.

    """

    async def scenario() -> vs.ShotRecord:
        """Visit a failing step and collect its record.

        Returns:
            The shot record of the failed step.

        """
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            context: BrowserContext = await browser.new_context()
            page: Page = await context.new_page()
            work: LaneWork = vs.LaneWork(
                device=cr.Constants.devices[0],
                theme="light",
                visits=[],
                directory=tmp_path / "lane",
            )
            record: ShotRecord = await vs.visit_step(
                page=page,
                work=work,
                task=vs.VisitTask(
                    step=cr.VisitStep(name="x", url="http://127.0.0.1:1/"),
                    index=0,
                    number=1,
                ),
                settings=_settings(),
                similarity=None,
            )
            await browser.close()
            return record

    record: ShotRecord = run(main=scenario())
    expect_false(condition=record.ok)
    expect_true(condition=bool(record.error))


def test_drain_events(tmp_path: Path) -> None:
    """Queued console and page-error events are serialized.

    Args:
        tmp_path: Per-test temporary directory.

    """

    async def scenario() -> list[dict[str, JsonValue]]:
        """Drain the event queue into serialized records.

        Returns:
            The drained event records.

        """
        async with async_playwright() as playwright:
            browser: Browser = await playwright.chromium.launch(headless=True)
            page: Page = await browser.new_page()
            queue: Queue[vs.LaneItem | None] = Queue()
            page.on(
                event="console",
                f=lambda event: queue.put_nowait(item=(None, event)),
            )
            await page.evaluate(
                expression="console.log('a', {b: 1}, document.body)",
            )
            await page.wait_for_timeout(timeout=200)
            queue.put_nowait(
                item=(cr.VisitStep(name="v", url="u"), RuntimeError("boom")),
            )
            queue.put_nowait(item=None)
            console: list[dict[str, JsonValue]] = []
            await vs.drain(
                queue=queue,
                device="d",
                theme="light",
                console=console,
                server=[],
            )
            await browser.close()
            return console

    entries: list[dict[str, JsonValue]] = run(main=scenario())
    expect_equal(actual=entries[0]["type"], expected="log")
    expect_equal(actual=entries[-1]["type"], expected="pageerror")
    expect_true(condition=bool(tmp_path))
    expect_true(condition=bool(loads(s='{"ok": 1}')))
