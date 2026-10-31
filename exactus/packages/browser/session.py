# Copyright (c) 2026 João Lopes.
"""Open a URL in the managed browser and wait until the user closes it."""

from __future__ import annotations

from typing import final

from exactus.packages.browser.lifecycle import BrowserLifecycle


@final
class BrowserSession:
    """A visible browser window owned by the calling script.

    The session replaces ``webbrowser.open``: scripts open their URL here,
    then call ``wait_closed`` so they exit once the user closes the browser.
    """

    def __init__(self) -> None:
        """Create an idle session; no browser exists until ``open``."""
        self._lifecycle: BrowserLifecycle = BrowserLifecycle()

    def open(self, *, url: str) -> None:
        """Launch the managed browser on a URL.

        Args:
            url: Address to display.

        """
        self._lifecycle.start_playwright(
            url=url,
            headless=False,
            no_viewport=True,
        )

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
