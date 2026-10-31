# Copyright (c) 2026 João Lopes.
"""Shared server and browser lifecycle for exported performance dashboards."""

from dataclasses import dataclass
from pathlib import Path

from exactus.packages.browser.lifecycle import BrowserLifecycle
from exactus.packages.server import local
from exactus.packages.server.process_control import terminate_tree


@dataclass(slots=True)
class DashboardSession:
    """Own or adopt the server and browser used by one dashboard.

    Attributes:
        directory: Exported dashboard directory served by
        ``exactus.packages.server``.
        pid: Process identifier of the shared loopback server.
        url: Absolute URL of the dashboard index page.
        reused: Whether ``exactus.packages.server`` adopted an existing server.
        browser: Browser lifecycle when this session opened Chrome.

    """

    directory: Path
    pid: int
    url: str
    reused: bool
    browser: BrowserLifecycle | None = None

    def close(self) -> None:
        """Close owned resources without killing an adopted server."""
        if self.browser is not None:
            self.browser.close()
            self.browser = None
        if not self.reused:
            terminate_tree(pid=self.pid)
            local.clear_server_state(path=self.directory)


class DashboardLauncher:
    """Launch exported dashboards through shared package infrastructure."""

    @staticmethod
    def serve(
        *,
        directory: Path,
        open_browser_window: bool = True,
        executable: Path | None = None,
        server_timeout: float = 10.0,
    ) -> DashboardSession:
        """Serve a dashboard and optionally open it with the browser package.

        Args:
            directory: Exported dashboard directory.
            open_browser_window: Whether to launch Chrome/Chromium.
            executable: Optional Chrome/Chromium executable override.
            server_timeout: Maximum seconds to wait for server readiness.

        Returns:
            Lifecycle session owning newly created resources.

        Raises:
            RuntimeError: When the shared server does not become ready.

        """
        resolved: Path = directory.resolve()
        pid: int
        origin: str
        reused: bool
        pid, origin, reused = local.serve(
            path=resolved,
            log=resolved / "server.log",
        )
        if not local.wait_ready(url=origin, pid=pid, timeout=server_timeout):
            if not reused:
                terminate_tree(pid=pid)
                local.clear_server_state(path=resolved)
            msg: str = f"Performance dashboard server is not ready: {origin}"
            raise RuntimeError(msg)
        url: str = f"{origin}index.html"
        browser: BrowserLifecycle | None = None
        if open_browser_window:
            browser = BrowserLifecycle()
            try:
                _ = browser.launch_chrome(url=url, executable=executable)
            except BaseException:
                if not reused:
                    terminate_tree(pid=pid)
                    local.clear_server_state(path=resolved)
                raise
        return DashboardSession(
            directory=resolved,
            pid=pid,
            url=url,
            reused=reused,
            browser=browser,
        )
