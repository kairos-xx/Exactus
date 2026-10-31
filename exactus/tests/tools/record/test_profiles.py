# Copyright (c) 2026 Project contributors
"""Validate profile settings and prove Chromium honours every accepted one."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import replace
from typing import TYPE_CHECKING, TypedDict, Unpack

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.model import (
    Constants,
    Profile,
    Workspace,
    default_profiles,
)
from exactus.tools.record.profile_emulation import (
    ProfileEmulator,
    context_options,
)
from exactus.tools.record.run import scoped_profile
from exactus.tools.record.store import WorkspaceCodec, WorkspaceError
from exactus.tools.record.studio.demo import demo_workspace

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

    from exactus.tools.record.model import Flow
    from exactus.tools.record.store import JsonValue


class _ProfileFields(TypedDict, total=False):
    """Profile fields a test may override.

    Attributes:
        profile_id: Identifier.
        name: Display name.
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        scale: Device pixel ratio.
        screen_width: Device screen width, if set.
        screen_height: Device screen height, if set.
        touch: Whether input is touch.
        mobile: Whether the browser is mobile.
        media: Emulated media features.

    """

    profile_id: str
    name: str
    width: int
    height: int
    scale: float
    screen_width: int | None
    screen_height: int | None
    touch: bool
    mobile: bool
    media: tuple[tuple[str, str], ...]


def _profile(**fields: Unpack[_ProfileFields]) -> Profile:
    """Build a valid profile and apply requested field changes.

    Args:
        fields: Fields differing from the phone defaults.

    Returns:
        The profile.

    """
    return replace(
        Profile(profile_id="phone", name="Phone", width=390, height=844),
        **fields,
    )


@pytest.mark.parametrize(
    ("feature", "message"),
    [
        ("pointer", "touch setting"),
        ("width", "viewport size"),
        ("resolution", "pixel density"),
        ("monochrome", "cannot be emulated"),
        ("scripting", "cannot be emulated"),
        ("device-posture", "cannot be emulated"),
        ("made-up", "not a media feature"),
    ],
)
def test_profile_rejects_features_the_browser_cannot_set(
    feature: str,
    message: str,
) -> None:
    """Refuse derived, unsupported and unknown media features by name.

    Args:
        feature: Media feature a user tried to set.
        message: Part of the explanation the user must see.

    """
    with pytest.raises(expected_exception=ValueError, match=message):
        _profile(media=((feature, "x"),))


def test_profile_validates_values_ranges_and_identity() -> None:
    """Reject values outside each setting's semantic range."""
    with pytest.raises(expected_exception=ValueError, match="accepts"):
        _profile(media=(("prefers-color-scheme", "blue"),))
    with pytest.raises(expected_exception=ValueError, match="only once"):
        _profile(
            media=(("forced-colors", "none"), ("forced-colors", "active")),
        )
    with pytest.raises(expected_exception=ValueError, match="Pixel density"):
        _profile(scale=9)
    with pytest.raises(expected_exception=ValueError, match="CSS px"):
        _profile(width=10)
    with pytest.raises(expected_exception=ValueError, match="both"):
        _profile(screen_width=800)
    for bad_id in ("Phone", "", "shared", "custom", "a b", "x" * 33):
        with pytest.raises(expected_exception=ValueError, match="profile ID"):
            _profile(profile_id=bad_id)
    with pytest.raises(expected_exception=ValueError, match="name"):
        _profile(name="  ")


def test_profiles_round_trip_and_legacy_files_get_defaults() -> None:
    """Persist profiles and fill defaults for projects saved without them."""
    phone: Profile = _profile(
        scale=3,
        touch=True,
        mobile=True,
        screen_width=390,
        screen_height=844,
        media=(("prefers-color-scheme", "dark"),),
    )
    workspace: Workspace = Workspace(flows=(), edges=(), profiles=(phone,))
    saved: JsonValue = WorkspaceCodec.to_json_value(workspace=workspace)
    expect_equal(
        actual=WorkspaceCodec.from_json_value(value=saved).profiles,
        expected=(phone,),
    )
    expect_true(condition=isinstance(saved, dict))
    if not isinstance(saved, dict):
        return
    legacy: dict[str, JsonValue] = {
        key: value for key, value in saved.items() if key != "profiles"
    }
    expect_equal(
        actual=WorkspaceCodec.from_json_value(value=legacy).profiles,
        expected=default_profiles(),
    )
    listed: JsonValue = saved["profiles"]
    first: JsonValue = listed[0] if isinstance(listed, list) else None
    bad_media: JsonValue = {
        "id": "p",
        "name": "P",
        "width": 400,
        "height": 400,
        "media": {"monochrome": "2"},
    }
    variants: list[JsonValue] = [[], [first, first], [bad_media]]
    for profiles in variants:
        broken: dict[str, JsonValue] = {**saved, "profiles": profiles}
        with pytest.raises(expected_exception=WorkspaceError):
            _ = WorkspaceCodec.from_json_value(value=broken)


def test_field_catalog_covers_every_editable_setting() -> None:
    """Publish a typed control description for each setting and each choice."""
    catalog: JsonValue = WorkspaceCodec.profile_schema()
    expect_true(condition=isinstance(catalog, dict))
    if not isinstance(catalog, dict):
        return
    fields: JsonValue = catalog["fields"]
    expect_true(condition=isinstance(fields, list))
    if not isinstance(fields, list):
        return
    by_id: dict[str, dict[str, JsonValue]] = {
        str(object=field["id"]): field
        for field in fields
        if isinstance(field, dict)
    }
    expect_equal(actual=by_id["width"]["unit"], expected="px")
    expect_equal(actual=by_id["aspect-ratio"]["kind"], expected="ratio")
    expect_equal(actual=by_id["scale"]["unit"], expected="dppx")
    for name, options in Constants.supported_media.items():
        expect_equal(actual=by_id[name]["options"], expected=list(options))
    unsupported: JsonValue = catalog["unsupported"]
    names: list[JsonValue] = (
        unsupported if isinstance(unsupported, list) else []
    )
    expect_true(condition="monochrome" in names)


def _matches(page: Page, query: str) -> bool:
    """Evaluate a media query in the page.

    Args:
        page: Page to ask.
        query: Complete media query.

    Returns:
        Whether the page currently matches the query.

    """
    return bool(
        page.evaluate(expression="q => matchMedia(q).matches", arg=query),
    )


def test_chromium_honours_every_accepted_media_value() -> None:
    """Every value the model accepts must change what the page can see."""
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        try:
            for name, options in Constants.supported_media.items():
                for value in options:
                    profile: Profile = _profile(media=((name, value),))
                    context: BrowserContext = browser.new_context(
                        **context_options(profile=profile),
                    )
                    emulator: ProfileEmulator = ProfileEmulator()
                    page: Page = context.new_page()
                    emulator.apply(page=page, profile=profile)
                    page.set_content(html="<p>x</p>")
                    expect_true(
                        condition=_matches(
                            page=page,
                            query=f"({name}: {value})",
                        ),
                        message=f"({name}: {value}) is not honoured",
                    )
                    context.close()
        finally:
            browser.close()


def test_chromium_follows_viewport_density_and_touch_settings() -> None:
    """Typed size, density, screen and input settings reach media queries."""
    phone: Profile = _profile(
        scale=3,
        touch=True,
        mobile=True,
        screen_width=430,
        screen_height=932,
        media=(("prefers-color-scheme", "dark"),),
    )
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        try:
            context: BrowserContext = browser.new_context(
                **context_options(profile=phone),
            )
            emulator: ProfileEmulator = ProfileEmulator()
            page: Page = context.new_page()
            emulator.apply(page=page, profile=phone)
            page.set_content(
                html='<meta name="viewport" content="width=device-width">',
            )
            for query in (
                "(width: 390px)",
                "(height: 844px)",
                "(orientation: portrait)",
                "(resolution: 3dppx)",
                "(device-width: 430px)",
                "(device-height: 932px)",
                "(pointer: coarse)",
                "(hover: none)",
                "(prefers-color-scheme: dark)",
            ):
                expect_true(
                    condition=_matches(page=page, query=query),
                    message=query,
                )
            # Media emulation survives navigation and applies to new pages.
            page.set_content(html="<p>again</p>")
            expect_true(
                condition=_matches(
                    page=page,
                    query="(prefers-color-scheme: dark)",
                ),
            )
            popup: Page = context.new_page()
            emulator.apply(page=popup, profile=phone)
            expect_true(
                condition=_matches(
                    page=popup,
                    query="(prefers-color-scheme: dark)",
                ),
            )
            context.close()
            desktop: BrowserContext = browser.new_context(
                **context_options(profile=default_profiles()[0]),
            )
            plain: Page = desktop.new_page()
            expect_true(
                condition=_matches(page=plain, query="(pointer: fine)"),
            )
            expect_true(condition=_matches(page=plain, query="(hover: hover)"))
            expect_true(
                condition=_matches(page=plain, query="(width: 1440px)"),
            )
            desktop.close()
        finally:
            browser.close()


def test_runner_scopes_a_flow_to_exactly_one_saved_profile() -> None:
    """Run under a profile only for a flow scoped to one existing profile."""
    phone: Profile = _profile(profile_id="phone")
    base: Workspace = demo_workspace(url="http://localhost/")
    workspace: Workspace = replace(base, profiles=(*base.profiles, phone))
    flow: Flow = workspace.flows[0]
    shared: Flow = replace(flow, device_modes=frozenset({"shared"}))
    only: Flow = replace(flow, device_modes=frozenset({"phone"}))
    both: Flow = replace(flow, device_modes=frozenset({"phone", "desktop"}))
    gone: Flow = replace(flow, device_modes=frozenset({"watch"}))
    expect_equal(
        actual=scoped_profile(workspace=workspace, flow=shared),
        expected=None,
    )
    expect_equal(
        actual=scoped_profile(workspace=workspace, flow=only),
        expected=phone,
    )
    expect_equal(
        actual=scoped_profile(workspace=workspace, flow=both),
        expected=None,
    )
    expect_equal(
        actual=scoped_profile(workspace=workspace, flow=gone),
        expected=None,
    )


def test_touch_survives_full_page_screenshots_only_when_restored() -> None:
    """A full-page capture drops touch input; the emulator puts it back."""
    phone: Profile = _profile(scale=3, touch=True, mobile=True)
    query: str = "() => matchMedia('(pointer: coarse)').matches"
    page_html: str = (
        "<meta name=viewport content='width=device-width'>"
        "<div style='height:3000px'>tall</div>"
    )
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=True)
        try:
            context: BrowserContext = browser.new_context(
                **context_options(profile=phone),
            )
            page: Page = context.new_page()
            page.set_content(html=page_html)
            expect_true(condition=bool(page.evaluate(expression=query)))
            # Documents the browser behaviour the restore exists to repair.
            # Interval polling avoids requestAnimationFrame stalls in a
            # busy headless page; engines that keep touch are tolerated
            # because the contract under test is the restored state.
            _ = page.screenshot(full_page=True)
            with suppress(PlaywrightTimeoutError):
                page.wait_for_function(
                    expression=(
                        "() => !matchMedia('(pointer: coarse)').matches"
                    ),
                    polling=100,
                    timeout=5000,
                )
            ProfileEmulator().restore(page=page, profile=phone)
            expect_true(condition=bool(page.evaluate(expression=query)))
            context.close()
        finally:
            browser.close()
