# Copyright (c) 2026 Project contributors
"""Apply a profile's device and media conditions to a real Chromium page."""

from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, Protocol, TypedDict, cast

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from exactus.tools.record.json_types import JsonValue
    from exactus.tools.record.model import Profile


class MediaSession(Protocol):
    """Describe the typed subset of Chromium's protocol session in use."""

    def send(self, *, method: str, params: dict[str, JsonValue]) -> JsonValue:
        """Send a protocol method.

        Args:
            method: Chromium method name.
            params: JSON method arguments.

        Returns:
            Chromium method result.

        """
        ...


class ScreenSize(TypedDict):
    """Pixel dimensions of a viewport or device screen.

    Attributes:
        width: Horizontal pixel count.
        height: Vertical pixel count.

    """

    width: int
    height: int


class ContextOptions(TypedDict):
    """Browser-context options a profile controls, named as Playwright does.

    Attributes:
        viewport: Viewport size in CSS pixels.
        device_scale_factor: Device pixel ratio.
        is_mobile: Whether mobile emulation applies.
        has_touch: Whether the context supports touch events.
        screen: Physical screen size when it differs from the viewport.

    """

    viewport: ScreenSize
    device_scale_factor: float
    is_mobile: bool
    has_touch: bool
    screen: NotRequired[ScreenSize]


def context_options(*, profile: Profile) -> ContextOptions:
    """Return the browser-context options that realise a profile.

    Args:
        profile: Conditions to emulate.

    Returns:
        Keyword arguments for ``Browser.new_context``. Media features are not
        included; ``ProfileEmulator`` applies those so they cannot conflict.

    """
    options: ContextOptions = {
        "viewport": {"width": profile.width, "height": profile.height},
        "device_scale_factor": profile.scale,
        "is_mobile": profile.mobile,
        "has_touch": profile.touch,
    }
    if profile.screen_width is not None and profile.screen_height is not None:
        options["screen"] = {
            "width": profile.screen_width,
            "height": profile.screen_height,
        }
    return options


class ProfileEmulator:
    """Keep media emulation alive for every page it was applied to.

    Chromium drops a session's media overrides when that session closes, so
    this object owns one protocol session per page for as long as the browser
    runs. Applying again replaces the page's earlier features.
    """

    def __init__(self) -> None:
        """Start without any emulated pages."""
        self._sessions: dict[Page, MediaSession] = {}

    def apply(self, *, page: Page, profile: Profile) -> None:
        """Emulate a profile's media features on a page.

        Args:
            page: Page that should see the profile's media features.
            profile: Conditions to emulate. Features it no longer sets return
                to the browser default.

        """
        session: MediaSession | None = self._sessions.get(page)
        if session is None:
            if not profile.media:
                return
            session = cast(
                typ="MediaSession",
                val=page.context.new_cdp_session(page=page),
            )
            self._sessions[page] = session
        _ = session.send(
            method="Emulation.setEmulatedMedia",
            params={
                "features": [
                    {"name": name, "value": value}
                    for name, value in profile.media
                ],
            },
        )

    def restore(self, *, page: Page, profile: Profile) -> None:
        """Put touch emulation back after a full-page screenshot.

        Playwright resizes the page for a full-page capture and, in a touch
        device, does not restore touch input afterwards. Without this, every
        action after the first screenshot would run with a mouse.

        Args:
            page: Page that was just captured.
            profile: Conditions the page should still be under.

        """
        if not profile.touch:
            return
        session: MediaSession | None = self._sessions.get(page)
        if session is None:
            session = cast(
                typ="MediaSession",
                val=page.context.new_cdp_session(page=page),
            )
            self._sessions[page] = session
        _ = session.send(
            method="Emulation.setTouchEmulationEnabled",
            params={"enabled": True, "maxTouchPoints": 1},
        )

    def release(self) -> None:
        """Forget every session so a closed browser leaves nothing behind."""
        self._sessions.clear()
