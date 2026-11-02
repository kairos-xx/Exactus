# Copyright (c) 2026 João Lopes.
"""Open a URL in the managed browser and wait until the user closes it."""

from __future__ import annotations

from typing import final

from exactus.packages.browser.lifecycle import BrowserLifecycle


@final
class BrowserSession:
    """A managed browser owned by the calling script.

    The session replaces ``webbrowser.open``: scripts open their URL here,
    then call ``wait_closed`` so they exit once the user closes the browser.
    Headless sessions load the page without a visible window.
    """

    def __init__(self, *, headless: bool = False) -> None:
        """Create an idle session; no browser exists until ``open``.

        Args:
            headless: Load pages without showing a browser window.

        """
        self._headless: bool = headless
        self._lifecycle: BrowserLifecycle = BrowserLifecycle()

    def open(self, *, url: str) -> None:
        """Launch the managed browser on a URL.

        Args:
            url: Address to display.

        """
        self._lifecycle.start_playwright(
            url=url,
            headless=self._headless,
            no_viewport=True,
        )

    def wait_ready(self, *, timeout: float | None = None) -> bool:
        """Wait until the browser finished loading the initial page.

        Args:
            timeout: Maximum seconds to wait, or None to wait indefinitely.

        Returns:
            True when the page loaded, otherwise False.

        """
        return self._lifecycle.wait_ready(timeout=timeout)

    def wait_closed(self, *, timeout: float | None = None) -> bool:
        """Wait for the independently running browser worker to finish.

        Args:
            timeout: Maximum seconds to wait, or None to wait indefinitely.

        Returns:
            True when the browser worker finished, otherwise False.

        """
        return self._lifecycle.wait(timeout=timeout)

    def close(self) -> None:
        """Release the browser; safe after the user already closed it."""
        self._lifecycle.close()
