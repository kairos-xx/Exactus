#!/usr/bin/env python3
# Copyright (c) 2026
"""Build a concrete visit plan covering every reachable app interface.

The crawler drives headless Chromium against a running VM Image Manager
instance, discovers every hash-routed panel from the rendered navigation,
and records the Playwright actions required to open every non-destructive
sub-interface: dialog triggers, select options, and checkbox/radio
toggles. The emitted JSON plan is consumed by ``visit.py``.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from pathlib import Path
from re import IGNORECASE, Pattern, sub
from re import compile as re_compile
from sys import path as sys_path
from typing import TYPE_CHECKING, ClassVar, Final, Literal, final
from urllib.parse import urlparse

from playwright.async_api import (
    BrowserContext,
    Error,
    Locator,
    Page,
    Route,
    async_playwright,
)

if __package__ in (None, ""):
    root: Path = Path(__file__).resolve().parents[3]
    sys_path.insert(0, str(object=root))
if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.async_api._generated import Browser
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type ActionKind = Literal["click", "select", "toggle"]
type ConsoleVersion = Literal["v1", "v2"]
type ThemeName = Literal["dark", "light"]


class CrawlerDefaults:
    """Store immutable crawler configuration values.

    Attributes:
        app_url: Default loopback application URL.
        content: CSS selector scoping interface elements.
        nav_buttons: CSS selector discovering panel routes from the
            navigation rail.
        nav_links: CSS selector discovering additional hash-routed links.
        button: CSS selector for clickable panel buttons.
        select: CSS selector for option-bearing panel selects.
        toggle: CSS selector for checkbox and radio sweeps.
        setup_selector: CSS selector for the first-run setup wizard.
        mutating_methods: HTTP methods blocked during exploration.
        theme_key: Storage key holding the remembered theme mode.
        panel_key: Storage key holding the remembered initial panel;
            cleared so replays start deterministically.
        machine_key: Storage key holding the selected workload.
        setup_seen_key: Storage key marking the wizard as seen.
        trigger_allow: Dialog-trigger labels worth opening.
        trigger_deny: Dialog-trigger labels never opened.
        theme_switch: Labels matching theme-mode controls; switching
            themes mid-visit would corrupt deterministic output.
        settle_ms: Settle wait after interaction.
        navigate_settle_ms: Settle wait after navigation.
        dialog_settle_ms: Settle wait after dialog triggers and input
            sweeps.
        action_timeout_ms: Per-action Playwright timeout.
        page_timeout_ms: Default page-level Playwright timeout.
        content_timeout_ms: Maximum wait for the content root.
        theme_switch_prefix: Theme switch prefix.

    """

    app_url: ClassVar[str] = "http://127.0.0.1:8000"
    content: ClassVar[str] = "#main-content"
    nav_buttons: ClassVar[str] = ".sv-navigation-rail button[data-value]"
    nav_links: ClassVar[str] = "a[href*='#/']"
    button: ClassVar[str] = "#main-content button:visible"
    select: ClassVar[str] = "#main-content select:visible"
    toggle: ClassVar[str] = (
        "#main-content input[type=checkbox]:visible,#main-content"
        " input[type=radio]:visible"
    )
    setup_selector: ClassVar[str] = ".vmim-setup"
    mutating_methods: ClassVar[frozenset[str]] = frozenset(
        {"POST", "PUT", "PATCH", "DELETE"},
    )
    theme_key: ClassVar[str] = "vmim.theme"
    panel_key: ClassVar[str] = "vmim.panel"
    machine_key: ClassVar[str] = "vmim.machine"
    setup_seen_key: ClassVar[str] = "vmim.setup.seen"
    trigger_allow: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            "add|new|create|connect|publish|edit|config|download|postman|impor"
            "t|pull|search|credential|token|ddns|tunnel|rule|settings|install|"
            "consume|probe|trace|client|wizard|peer|host|expose|bind|checkpoin"
            "t|snapshot|bundle|expand"
        ),
        flags=IGNORECASE,
    )
    trigger_deny: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            "delete|remove|stop|kill|rollback|prune|restart|reboot|cancel|clos"
            "e|save|confirm|apply|force|down\\b|destroy"
        ),
        flags=IGNORECASE,
    )
    theme_switch_prefix: ClassVar[str] = (
        "(?:switch to|follow the|toggle)\\s+(?:the\\s+)?"
    )
    theme_switch: ClassVar[Pattern[str]] = re_compile(
        pattern=(
            theme_switch_prefix + "(?:system\\s+|light\\s+|dark\\s+)?theme"
        ),
        flags=IGNORECASE,
    )
    settle_ms: ClassVar[float] = 700
    navigate_settle_ms: ClassVar[float] = 900
    dialog_settle_ms: ClassVar[float] = 400
    action_timeout_ms: ClassVar[float] = 5000
    page_timeout_ms: ClassVar[float] = 60000
    content_timeout_ms: ClassVar[float] = 15000


@dataclass(frozen=True, slots=True)
class VisitAction:
    """Describe one Playwright interaction within a visit.

    Attributes:
        kind: Interaction kind performed by the visitor.
        selector: CSS selector locating the target elements.
        index: Position inside the selector match list.
        text: Human-readable label or ``has_text`` filter value.
        value: Option value for ``select`` actions.

    """

    kind: ActionKind
    selector: str
    index: int = 0
    text: str = ""
    value: str = ""


@dataclass(frozen=True, slots=True)
class VisitStep:
    """Describe one interface visit: load ``url`` then apply ``actions``.

    Attributes:
        name: Stable interface identifier used in output artifacts.
        url: Absolute URL loaded before the actions run.
        actions: Ordered Playwright interactions opening the interface.
        id: Short identifier correlating the visit across device lanes,
            themes, and every report; derived from ``name`` when omitted.

    """

    name: str
    url: str
    actions: tuple[VisitAction, ...] = ()
    id: str = ""

    def __post_init__(self) -> None:
        """Derive the visit identifier from the name when omitted."""
        if not self.id:
            object.__setattr__(self, "id", visit_id(name=self.name))


@dataclass(frozen=True, slots=True)
class DeviceSpec:
    """Describe one emulated device lane for the visit matrix.

    Attributes:
        name: Lane identifier used in output folders.
        width: CSS viewport width.
        height: CSS viewport height.
        scale_factor: Device pixel ratio.
        mobile: Whether the context emulates a mobile viewport.
        touch: Whether the context exposes touch input.

    """

    name: str
    width: int
    height: int
    scale_factor: float
    mobile: bool
    touch: bool

    @classmethod
    def parse(cls, data: dict[str, JsonValue]) -> DeviceSpec | None:
        """Rebuild one device preset from a decoded plan entry.

        Args:
            data: Decoded device object.

        Returns:
            Validated device, or ``None`` when malformed.

        """
        name: JsonValue = data.get("name")
        width: JsonValue = data.get("width")
        height: JsonValue = data.get("height")
        if (
            not isinstance(name, str)
            or not name
            or (not isinstance(width, int))
            or (not isinstance(height, int))
        ):
            return None
        scale: JsonValue = data.get("scale_factor")
        mobile: JsonValue = data.get("mobile")
        touch: JsonValue = data.get("touch")
        return cls(
            name=name,
            width=width,
            height=height,
            scale_factor=(
                float(scale) if isinstance(scale, int | float) else 1.0
            ),
            mobile=mobile if isinstance(mobile, bool) else False,
            touch=touch if isinstance(touch, bool) else False,
        )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        devices: Grouped module constant.
        themes: Grouped module constant.

    """

    devices: Final[tuple[DeviceSpec, ...]] = (
        DeviceSpec(
            name="desktop",
            width=1440,
            height=900,
            scale_factor=2.0,
            mobile=False,
            touch=False,
        ),
        DeviceSpec(
            name="tablet",
            width=834,
            height=1194,
            scale_factor=2.0,
            mobile=True,
            touch=True,
        ),
        DeviceSpec(
            name="phone",
            width=390,
            height=844,
            scale_factor=3.0,
            mobile=True,
            touch=True,
        ),
    )
    themes: Final[tuple[ThemeName, ...]] = ("light", "dark")


def _parse_action(entry: JsonValue) -> VisitAction | None:
    """Rebuild one action from a decoded plan entry.

    Args:
        entry: Decoded action object.

    Returns:
        Validated action, or ``None`` when malformed.

    """
    if not isinstance(entry, dict):
        return None
    kind: JsonValue = entry.get("kind")
    selector: JsonValue = entry.get("selector")
    if kind not in ("click", "select", "toggle") or not isinstance(
        selector,
        str,
    ):
        return None
    raw_index: JsonValue = entry.get("index")
    raw_text: JsonValue = entry.get("text")
    raw_value: JsonValue = entry.get("value")
    return VisitAction(
        kind=kind,
        selector=selector,
        index=raw_index if isinstance(raw_index, int) else 0,
        text=raw_text if isinstance(raw_text, str) else "",
        value=raw_value if isinstance(raw_value, str) else "",
    )


@dataclass(frozen=True, slots=True)
class VisitPlan:
    """Describe every interface visit the application exposes.

    Attributes:
        base_url: Application origin the plan was discovered against.
        themes: Theme modes the visitor replays each visit under.
        devices: Emulated device lanes the visitor replays under.
        visits: Ordered interface visits.

    """

    base_url: str
    themes: tuple[ThemeName, ...] = Constants.themes
    devices: tuple[DeviceSpec, ...] = Constants.devices
    visits: tuple[VisitStep, ...] = ()

    @classmethod
    def parse(cls, data: dict[str, JsonValue]) -> VisitPlan:
        """Rebuild a plan from decoded JSON.

        Args:
            data: Decoded plan object.

        Returns:
            Validated visit plan.

        Raises:
            TypeError: When a field carries the wrong type.
            ValueError: When a required field is empty.

        """
        base_url: JsonValue = data.get("base_url")
        if not isinstance(base_url, str):
            msg: str = "plan.base_url must be a string"
            raise TypeError(msg)
        if not base_url:
            msg = "plan.base_url must be non-empty"
            raise ValueError(msg)
        raw_themes: JsonValue = data.get("themes")
        themes: tuple[ThemeName, ...] = (
            tuple(
                theme
                for entry in raw_themes
                for theme in Constants.themes
                if theme == entry
            )
            if isinstance(raw_themes, list)
            else Constants.themes
        )
        raw_devices: JsonValue = data.get("devices")
        devices: tuple[DeviceSpec, ...] = (
            tuple(
                device
                for entry in raw_devices
                if isinstance(entry, dict)
                if (device := DeviceSpec.parse(data=entry)) is not None
            )
            if isinstance(raw_devices, list)
            else Constants.devices
        )
        raw_visits: JsonValue = data.get("visits")
        if not isinstance(raw_visits, list):
            msg = "plan.visits must be a list"
            raise TypeError(msg)
        visits: list[VisitStep] = []
        for item in raw_visits:
            if not isinstance(item, dict):
                continue
            name: JsonValue = item.get("name")
            url: JsonValue = item.get("url")
            if not isinstance(name, str) or not isinstance(url, str):
                continue
            raw_actions: JsonValue = item.get("actions", [])
            actions: list[VisitAction] = [
                action
                for entry in (
                    raw_actions if isinstance(raw_actions, list) else []
                )
                if (action := _parse_action(entry=entry)) is not None
            ]
            raw_id: JsonValue = item.get("id")
            visits.append(
                VisitStep(
                    name=name,
                    url=url,
                    actions=tuple(actions),
                    id=raw_id if isinstance(raw_id, str) else "",
                ),
            )
        return cls(
            base_url=base_url,
            themes=themes,
            devices=devices,
            visits=tuple(visits),
        )


def slug(value: str) -> str:
    """Convert arbitrary text to a filesystem-safe short slug.

    Args:
        value: Source text.

    Returns:
        Filesystem-safe slug.

    """
    return (
        sub(pattern="[^a-zA-Z0-9._-]+", repl="-", string=value).strip("-._")[
            :120
        ]
        or "root"
    )


def visit_id(*, name: str) -> str:
    """Derive a short stable identifier from a visit name.

    Args:
        name: Visit name to fingerprint.

    Returns:
        Seven-character base64url token identical for identical names.

    """
    digest: bytes = sha256(string=name.encode(encoding="utf-8")).digest()
    return urlsafe_b64encode(s=digest)[:7].decode(encoding="ascii")


async def dismiss_wizard(page: Page) -> None:
    """Walk the first-run setup dialog until it closes.

    The wizard's primary ``Continue`` button advances each step; the
    ``Escape`` key is the fallback when no such button is rendered.

    Args:
        page: Playwright page.

    """
    for _ in range(8):
        dialog: Locator = page.locator(selector=CrawlerDefaults.setup_selector)
        if await dialog.count() == 0:
            return
        button: Locator = dialog.locator(
            selector_or_locator="button",
            has_text="Continue",
        ).first
        try:
            if await button.count():
                await button.click(timeout=CrawlerDefaults.action_timeout_ms)
            else:
                await page.keyboard.press(key="Escape")
        except Error:
            with suppress(Error):
                await page.keyboard.press(key="Escape")
        await page.wait_for_timeout(timeout=CrawlerDefaults.settle_ms)


async def route_mutations(context: BrowserContext, sink: list[str]) -> None:
    """Block mutating HTTP methods while recording their signatures.

    Args:
        context: Browser context to instrument.
        sink: Mutable list receiving ``METHOD /path`` signatures.

    """

    async def block(route: Route) -> None:
        """Fulfill mutating requests empty and pass the rest.

        Args:
            route: Playwright network route.

        """
        method: str = route.request.method.upper()
        if method in CrawlerDefaults.mutating_methods:
            sink.append(f"{method} {urlparse(url=route.request.url).path}")
            await route.fulfill(status=204, body="")
        else:
            await route.continue_()

    _ = await context.route(url="**/*", handler=block)


async def storage_seed(theme: ThemeName, machine: str) -> str:
    """Return the init script seeding deterministic storage state.

    Args:
        theme: Theme mode remembered for the context.
        machine: Workload identifier seeded as the current selection.

    Returns:
        JavaScript evaluated before every document loads.

    """
    theme_key: str = dumps(obj=CrawlerDefaults.theme_key)
    setup_key: str = dumps(obj=CrawlerDefaults.setup_seen_key)
    panel_key: str = dumps(obj=CrawlerDefaults.panel_key)
    return (
        f"localStorage.setItem({theme_key},"
        f" {dumps(obj=theme)});localStorage.setItem({setup_key},"
        f" '1');localStorage.removeItem({panel_key});"
        + (
            f"localStorage.setItem({dumps(obj=CrawlerDefaults.machine_key)},"
            f" {dumps(obj=machine)});"
            if machine
            else ""
        )
    )


async def settle_content(page: Page) -> None:
    """Wait for rendered content and the post-navigation settle.

    The ``#main-content`` mount point exists in the static shell before
    scripts render into it, so existence alone cannot gate enumeration:
    wait for a rendered marker — the v2 route heading or the settled v1
    panel container — before applying the fixed settle delay.

    Args:
        page: Playwright page.

    """
    with suppress(Error):
        _ = await page.wait_for_selector(
            selector=CrawlerDefaults.content,
            timeout=CrawlerDefaults.content_timeout_ms,
        )
    with suppress(Error):
        _ = await page.wait_for_selector(
            selector=(
                f"{CrawlerDefaults.content} h1,"
                ' .vmim-panel-container[aria-busy="false"]'
            ),
            state="attached",
            timeout=CrawlerDefaults.content_timeout_ms,
        )
    await page.wait_for_timeout(timeout=CrawlerDefaults.navigate_settle_ms)


async def panel_urls(
    page: Page,
    base_url: str,
    *,
    version: ConsoleVersion,
) -> list[str]:
    """Discover every hash-routed interface URL in visit order.

    Args:
        page: Playwright page showing the application shell.
        base_url: Application origin.
        version: Console generation; ``v1`` collapses hash routes to
            their first segment while ``v2`` routes are hierarchical
            and kept whole.

    Returns:
        Deduplicated absolute panel URLs.

    """
    urls: list[str] = []
    buttons: Locator = page.locator(selector=CrawlerDefaults.nav_buttons)
    for index in range(await buttons.count()):
        panel: str = (
            await buttons.nth(index=index).get_attribute(name="data-value")
            or ""
        )
        url: str = f"{base_url}/#/{panel}"
        if panel and url not in urls:
            urls.append(url)
    links: Locator = page.locator(selector=CrawlerDefaults.nav_links)
    for index in range(await links.count()):
        href: str = (
            await links.nth(index=index).get_attribute(name="href") or ""
        )
        fragment: str = href.split(sep="#", maxsplit=1)[-1]
        if not fragment.startswith("/"):
            continue
        route: str = fragment.strip("/")
        if version == "v1":
            route = route.split(sep="/", maxsplit=1)[0]
        url = f"{base_url}/#/{route}"
        if route and url not in urls:
            urls.append(url)
    return urls


async def dialog_visits(
    page: Page,
    *,
    url: str,
    panel: str,
) -> list[VisitStep]:
    """Record visits opening every non-destructive panel trigger.

    Args:
        page: Playwright page parked on the panel.
        url: Panel URL.
        panel: Canonical panel identifier.

    Returns:
        One visit per allowed trigger label.

    """
    buttons: Locator = page.locator(selector=CrawlerDefaults.button)
    labels: list[str] = []
    triggers: list[tuple[int, str]] = []
    for index in range(await buttons.count()):
        try:
            label: str = (
                await buttons.nth(index=index).inner_text() or ""
            ).strip()
        except Error:
            continue
        if (
            label
            and CrawlerDefaults.trigger_allow.search(string=label)
            and (not CrawlerDefaults.trigger_deny.search(string=label))
            and (not CrawlerDefaults.theme_switch.search(string=label))
            and (label not in labels)
        ):
            labels.append(label)
            triggers.append((index, label))
    return [
        VisitStep(
            name=f"{panel}:dialog-{slug(value=label.lower())}",
            url=url,
            actions=(
                VisitAction(
                    kind="click",
                    selector=CrawlerDefaults.button,
                    index=index,
                    text=label,
                ),
            ),
        )
        for index, label in triggers
    ]


async def option_visits(
    page: Page,
    *,
    url: str,
    panel: str,
) -> list[VisitStep]:
    """Record visits selecting every option of every panel select.

    Args:
        page: Playwright page parked on the panel.
        url: Panel URL.
        panel: Canonical panel identifier.

    Returns:
        One visit per select option value.

    """
    visits: list[VisitStep] = []
    selects: Locator = page.locator(selector=CrawlerDefaults.select)
    for index in range(await selects.count()):
        select: Locator = selects.nth(index=index)
        name: str = (
            await select.get_attribute(name="name")
            or await select.get_attribute(name="aria-label")
            or f"select-{index}"
        )
        options: Locator = select.locator(selector_or_locator="option")
        for option_index in range(await options.count()):
            value: str = (
                await options.nth(index=option_index).get_attribute(
                    name="value",
                )
                or ""
            )
            if not value:
                continue
            visits.append(
                VisitStep(
                    name=f"{panel}:option-{
                        slug(value=(f'{name}-{value}').lower())
                    }",
                    url=url,
                    actions=(
                        VisitAction(
                            kind="select",
                            selector=CrawlerDefaults.select,
                            index=index,
                            text=name,
                            value=value,
                        ),
                    ),
                ),
            )
    return visits


async def toggle_visits(
    page: Page,
    *,
    url: str,
    panel: str,
) -> list[VisitStep]:
    """Record visits flipping every panel checkbox and radio.

    Args:
        page: Playwright page parked on the panel.
        url: Panel URL.
        panel: Canonical panel identifier.

    Returns:
        One visit per named toggle.

    """
    visits: list[VisitStep] = []
    toggles: Locator = page.locator(selector=CrawlerDefaults.toggle)
    for index in range(await toggles.count()):
        toggle: Locator = toggles.nth(index=index)
        name: str = (
            await toggle.get_attribute(name="name")
            or await toggle.get_attribute(name="aria-label")
            or f"toggle-{index}"
        )
        if CrawlerDefaults.theme_switch.search(string=name):
            continue
        visits.append(
            VisitStep(
                name=f"{panel}:toggle-{slug(value=name.lower())}",
                url=url,
                actions=(
                    VisitAction(
                        kind="toggle",
                        selector=CrawlerDefaults.toggle,
                        index=index,
                        text=name,
                    ),
                ),
            ),
        )
    return visits


async def panel_visits(page: Page, *, url: str, panel: str) -> list[VisitStep]:
    """Inventory one panel plus its dialog, option, and toggle visits.

    Args:
        page: Playwright page.
        url: Panel URL.
        panel: Canonical panel identifier.

    Returns:
        The panel visit followed by every discovered sub-interface.

    """
    _ = await page.goto(url=url, wait_until="domcontentloaded")
    await settle_content(page=page)
    await dismiss_wizard(page=page)
    return [
        VisitStep(name=panel, url=url),
        *await dialog_visits(page=page, url=url, panel=panel),
        *await option_visits(page=page, url=url, panel=panel),
        *await toggle_visits(page=page, url=url, panel=panel),
    ]


def resolve_devices(names: str) -> tuple[DeviceSpec, ...]:
    """Resolve a comma-separated device list against the presets.

    Args:
        names: Comma-separated device names; empty selects all.

    Returns:
        Matching device presets in canonical order.

    Raises:
        ValueError: When an unknown device name is given.

    """
    wanted: set[str] = {
        name.strip() for name in names.split(sep=",") if name.strip()
    }
    if not wanted:
        return Constants.devices
    unknown: set[str] = wanted - {device.name for device in Constants.devices}
    if unknown:
        msg: str = f"unknown device(s): {', '.join(sorted(unknown))}"
        raise ValueError(msg)
    return tuple(
        device for device in Constants.devices if device.name in wanted
    )


def resolve_themes(names: str) -> tuple[ThemeName, ...]:
    """Resolve a comma-separated theme list against the presets.

    Args:
        names: Comma-separated theme names; empty selects all.

    Returns:
        Matching theme names in canonical order.

    Raises:
        ValueError: When an unknown theme name is given.

    """
    wanted: set[str] = {
        name.strip() for name in names.split(sep=",") if name.strip()
    }
    if not wanted:
        return Constants.themes
    unknown: set[str] = wanted - set(Constants.themes)
    if unknown:
        msg: str = f"unknown theme(s): {', '.join(sorted(unknown))}"
        raise ValueError(msg)
    return tuple(theme for theme in Constants.themes if theme in wanted)


@dataclass(frozen=True, slots=True)
class CrawlOptions:
    """Optional crawl switches.

    Attributes:
        version: Console generation being crawled.
        on_progress: Optional progress reporter called once per crawled
            panel with keyword fields (``state``, ``completed``,
            ``total``, ``step``, ``detail``); ``None`` reports nothing.

    """

    version: ConsoleVersion = "v1"
    on_progress: Callable[..., None] | None = None


async def build_plan(
    *,
    base_url: str,
    devices: tuple[DeviceSpec, ...],
    themes: tuple[ThemeName, ...],
    machine: str,
    options: CrawlOptions | None = None,
) -> VisitPlan:
    """Discover every interface visit the running application exposes.

    Args:
        base_url: Application origin.
        devices: Lane devices; the first supplies the crawl viewport.
        themes: Theme modes; the first supplies the crawl scheme.
        machine: Workload identifier seeded as the current selection.
        options: Optional crawl switches; defaults crawl ``v1`` silently.

    Returns:
        Complete visit plan.

    """
    crawl: CrawlOptions = options if options is not None else CrawlOptions()
    on_progress: Callable[..., None] | None = crawl.on_progress
    theme: ThemeName = themes[0]
    device: DeviceSpec = devices[0]
    async with async_playwright() as playwright:
        browser: Browser = await playwright.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            viewport={"width": device.width, "height": device.height},
            device_scale_factor=device.scale_factor,
            is_mobile=device.mobile,
            has_touch=device.touch,
            color_scheme=theme,
            accept_downloads=False,
        )
        _ = await context.add_init_script(
            script=await storage_seed(theme=theme, machine=machine),
        )
        page: Page = await context.new_page()
        page.set_default_timeout(timeout=CrawlerDefaults.page_timeout_ms)
        mutations: list[str] = []
        await route_mutations(context=context, sink=mutations)
        visits: list[VisitStep] = []
        try:
            _ = await page.goto(url=base_url, wait_until="domcontentloaded")
            await settle_content(page=page)
            await dismiss_wizard(page=page)
            urls: list[str] = await panel_urls(
                page=page,
                base_url=base_url,
                version=crawl.version,
            )
            index: int
            url: str
            for index, url in enumerate(iterable=urls, start=1):
                panel: str = url.rsplit(sep="/", maxsplit=1)[-1]
                if on_progress is not None:
                    on_progress(
                        state="RUNNING",
                        completed=index,
                        total=len(urls),
                        step="crawl panel",
                        detail=panel,
                    )
                visits.extend(
                    await panel_visits(page=page, url=url, panel=panel),
                )
        finally:
            await context.close()
            await browser.close()
    return VisitPlan(
        base_url=base_url,
        themes=themes,
        devices=devices,
        visits=tuple(visits),
    )
