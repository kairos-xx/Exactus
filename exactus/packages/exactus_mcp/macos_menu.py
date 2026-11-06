# Copyright (c) 2026
"""Present Exactus MCP lifecycle and controls in the macOS menu bar."""

from __future__ import annotations

from importlib import import_module
from importlib.resources import files
from subprocess import run
from time import monotonic
from typing import TYPE_CHECKING, Final, Protocol, cast, final
from webbrowser import open as open_url

from .activity import ActivitySnapshot, ServiceActivity, ServicePhase
from .supervisor import ServiceRunner, ServiceSupervisor

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import datetime

    from .cli import RuntimeConfig


class NativeMenuItem(Protocol):
    """Describe the typed status-menu item surface Exactus uses."""

    @property
    def callback(self) -> MenuCallback | None:
        """Return the active command callback, when enabled.

        Returns:
            Current callback, or ``None`` when disabled.

        """
        ...

    @property
    def hidden(self) -> bool:
        """Return whether the item is hidden.

        Returns:
            Current visibility state.

        """
        ...

    @hidden.setter
    def hidden(self, value: bool) -> None:
        """Set whether the item is hidden.

        Args:
            value: New visibility state.

        """
        ...

    @property
    def title(self) -> str:
        """Return the visible menu title.

        Returns:
            Current visible title.

        """
        ...

    @title.setter
    def title(self, value: str) -> None:
        """Set the visible menu title.

        Args:
            value: New visible title.

        """
        ...

    def set_callback(self, callback: MenuCallback | None) -> None:
        """Enable the item with a callback or disable it with ``None``.

        Args:
            callback: Command callback, or ``None`` to disable the item.

        """
        ...

    def add(self, menuitem: NativeMenuItem) -> None:
        """Append one child command to this item's submenu.

        Args:
            menuitem: Child command to append.

        """
        ...


type MenuCallback = Callable[[NativeMenuItem], None]


class NativeTimer(Protocol):
    """Describe the native menu refresh timer."""

    def start(self) -> None:
        """Start the timer."""
        ...

    def stop(self) -> None:
        """Stop the timer."""
        ...


class NativeApp(Protocol):
    """Describe the native status application run loop."""

    def run(self) -> None:
        """Run the native application loop."""
        ...


class NativeSeparator(Protocol):
    """Mark the native menu separator sentinel."""


class MenuItemFactory(Protocol):
    """Describe construction of one native menu item."""

    def __call__(
        self,
        title: str,
        callback: MenuCallback | None = None,
    ) -> NativeMenuItem:
        """Create one native menu item.

        Args:
            title: Visible item title.
            callback: Optional command callback.

        Returns:
            Constructed native menu item.

        """
        ...


class TimerFactory(Protocol):
    """Describe construction of one native refresh timer."""

    def __call__(
        self,
        *,
        callback: Callable[[NativeTimer], None],
        interval: float,
    ) -> NativeTimer:
        """Create one native timer.

        Args:
            callback: Function invoked by the repeating timer.
            interval: Seconds between invocations.

        Returns:
            Constructed native timer.

        """
        ...


class AppFactory(Protocol):
    """Describe construction of one native status application."""

    def __call__(self, name: str, **options: AppOption) -> NativeApp:
        """Create one native status application.

        Args:
            name: Native application name.
            **options: Rumps application construction options.

        Returns:
            Constructed native status application.

        """
        ...


type AppOption = str | bool | None | Iterable[NativeMenuItem | NativeSeparator]


class RumpsModule(Protocol):
    """Describe the dynamically loaded macOS status library.

    Attributes:
        App: Native status-application factory.
        MenuItem: Native menu-item factory.
        Timer: Native timer factory.
        separator: Native menu separator sentinel.

    """

    App: AppFactory
    MenuItem: MenuItemFactory
    Timer: TimerFactory
    separator: NativeSeparator

    def quit_application(self) -> None:
        """Terminate the shared native application."""
        ...


RUMPS: Final[RumpsModule] = cast(
    typ="RumpsModule",
    val=import_module(name="rumps"),
)


@final
class Constants:
    """Group menu presentation and shutdown constants.

    Attributes:
        refresh_interval: Seconds between visible status refreshes.
        shutdown_timeout: Grace period before the menu application exits.

    """

    refresh_interval: Final[float] = 0.5
    shutdown_timeout: Final[float] = 8.0


@final
class MacMenuBarApplication:
    """Own the native status item, menu copy, and service actions."""

    def __init__(
        self,
        *,
        activity: ServiceActivity,
        supervisor: ServiceSupervisor,
    ) -> None:
        """Create the Exactus status item and stable menu structure.

        Args:
            activity: Shared observable service activity.
            supervisor: Background service lifecycle controller.

        """
        self._activity: ServiceActivity = activity
        self._supervisor: ServiceSupervisor = supervisor
        self._quitting: bool = False
        self._quit_deadline: float | None = None
        self._status: NativeMenuItem = RUMPS.MenuItem(
            title="Exactus MCP — Starting",
        )
        self._project: NativeMenuItem = RUMPS.MenuItem(title="Project")
        self._local: NativeMenuItem = RUMPS.MenuItem(
            title="Local: Not available",
        )
        self._public: NativeMenuItem = RUMPS.MenuItem(
            title="Public tunnel: Not available",
        )
        self._calls: NativeMenuItem = RUMPS.MenuItem(
            title="Calls: 0 · Active: 0",
        )
        self._last_call: NativeMenuItem = RUMPS.MenuItem(
            title="No MCP calls yet",
        )
        self._error: NativeMenuItem = RUMPS.MenuItem(title="")
        self._error.hidden = True
        self._start: NativeMenuItem = RUMPS.MenuItem(
            title="Start Server",
            callback=self._start_service,
        )
        self._stop: NativeMenuItem = RUMPS.MenuItem(
            title="Stop Server",
            callback=self._stop_service,
        )
        self._restart: NativeMenuItem = RUMPS.MenuItem(
            title="Restart Server",
            callback=self._restart_service,
        )
        self._open: NativeMenuItem = RUMPS.MenuItem(
            title="Open Status Page",
            callback=self._open_status_page,
        )
        self._copy: NativeMenuItem = RUMPS.MenuItem(
            title="Copy Connection URL",
            callback=self._copy_mcp_endpoint,
        )
        self._quit: NativeMenuItem = RUMPS.MenuItem(
            title="Quit Exactus MCP",
            callback=self._quit_exactus,
        )
        self._server_controls: NativeMenuItem = RUMPS.MenuItem(
            title="Server Controls",
        )
        self._server_controls.add(menuitem=self._start)
        self._server_controls.add(menuitem=self._stop)
        self._server_controls.add(menuitem=self._restart)
        self._connection: NativeMenuItem = RUMPS.MenuItem(title="Connection")
        self._connection.add(menuitem=self._open)
        self._connection.add(menuitem=self._copy)
        icon_path: str = str(
            object=files(anchor="exactus.packages.exactus_mcp").joinpath(
                "macos",
                "icons",
                "server.svg",
            ),
        )
        self._application: NativeApp = RUMPS.App(
            name="Exactus MCP",
            title=None,
            icon=icon_path,
            template=True,
            menu=(
                self._status,
                self._project,
                self._local,
                self._public,
                self._calls,
                self._last_call,
                self._error,
                RUMPS.separator,
                self._server_controls,
                self._connection,
                self._quit,
            ),
            quit_button=None,
        )
        self._timer: NativeTimer = RUMPS.Timer(
            callback=self._refresh_from_timer,
            interval=Constants.refresh_interval,
        )
        self._refresh()

    def run(self) -> None:
        """Run the menu application until the user chooses Quit."""
        self._timer.start()
        try:
            self._application.run()
        finally:
            self._timer.stop()

    @staticmethod
    def _set_enabled(
        *,
        item: NativeMenuItem,
        callback: MenuCallback,
        enabled: bool,
    ) -> None:
        """Enable or disable one menu action without changing its label.

        Args:
            item: Menu command to update.
            callback: Command callback restored when enabled.
            enabled: Whether the command can currently run.

        """
        selected: MenuCallback | None = callback if enabled else None
        if (item.callback is not None) != enabled:
            item.set_callback(callback=selected)

    @staticmethod
    def _last_call_text(*, snapshot: ActivitySnapshot) -> str:
        """Format the most recent MCP call as one scan-friendly line.

        Args:
            snapshot: Current service activity.

        Returns:
            Last-call label and local timestamp, or an empty-state message.

        """
        if snapshot.last_call is None or snapshot.last_call_at is None:
            return "No MCP calls yet"
        local_value: datetime = snapshot.last_call_at.astimezone()
        local_time: str = local_value.strftime(format="%H:%M:%S")
        return f"Last call: {snapshot.last_call} · {local_time}"

    def _start_service(self, _sender: NativeMenuItem) -> None:
        """Start the managed MCP service.

        Args:
            _sender: Native Start menu item.

        """
        _ = self._supervisor.start()
        self._refresh()

    def _stop_service(self, _sender: NativeMenuItem) -> None:
        """Stop the managed MCP service gracefully.

        Args:
            _sender: Native Stop menu item.

        """
        _ = self._supervisor.stop()
        self._refresh()

    def _restart_service(self, _sender: NativeMenuItem) -> None:
        """Restart the managed MCP service without blocking the menu.

        Args:
            _sender: Native Restart menu item.

        """
        _ = self._supervisor.restart()
        self._refresh()

    def _open_status_page(self, _sender: NativeMenuItem) -> None:
        """Open the preferred status page in the default browser.

        Args:
            _sender: Native Open menu item.

        """
        snapshot: ActivitySnapshot = self._activity.snapshot()
        value: str | None = snapshot.public_url or snapshot.local_url
        if value is not None:
            _ = open_url(url=f"{value}/")

    def _copy_mcp_endpoint(self, _sender: NativeMenuItem) -> None:
        """Copy the preferred MCP endpoint to the system pasteboard.

        Args:
            _sender: Native Copy menu item.

        """
        endpoint: str | None = self._activity.snapshot().mcp_url
        if endpoint is not None:
            _ = run(
                args=("/usr/bin/pbcopy",),
                input=endpoint,
                check=True,
                text=True,
            )

    def _quit_exactus(self, _sender: NativeMenuItem) -> None:
        """Begin graceful shutdown, then terminate the menu application.

        Args:
            _sender: Native Quit menu item.

        """
        self._quitting = True
        self._quit_deadline = monotonic() + Constants.shutdown_timeout
        _ = self._supervisor.stop()
        self._refresh()
        if not self._supervisor.is_running():
            RUMPS.quit_application()

    def _refresh_from_timer(self, _timer: NativeTimer) -> None:
        """Refresh menu state on the native run-loop timer.

        Args:
            _timer: Repeating native refresh timer.

        """
        self._refresh()
        service_stopped: bool = not self._supervisor.is_running()
        shutdown_expired: bool = (
            self._quit_deadline is not None
            and monotonic() >= self._quit_deadline
        )
        if self._quitting and (service_stopped or shutdown_expired):
            RUMPS.quit_application()

    def _refresh(self) -> None:
        """Render the newest activity snapshot into the native menu."""
        snapshot: ActivitySnapshot = self._activity.snapshot()
        phase_text: str = snapshot.phase.value
        if snapshot.active_calls:
            phase_text = f"{phase_text} · {snapshot.active_calls} active"
        self._status.title = f"Exactus MCP — {phase_text}"
        self._project.title = f"Project: {self._supervisor.root.name}"
        self._local.title = f"Local: {snapshot.local_url or 'Not available'}"
        public_text: str
        if snapshot.public_url is not None:
            public_text = snapshot.public_url
        elif not self._supervisor.public_tunnel_enabled:
            public_text = "Disabled"
        elif snapshot.phase is ServicePhase.UPDATING:
            public_text = "Updating…"
        else:
            public_text = "Not available"
        self._public.title = f"Public tunnel: {public_text}"
        self._calls.title = (
            f"Calls: {snapshot.call_count} · Active: {snapshot.active_calls}"
        )
        self._last_call.title = self._last_call_text(snapshot=snapshot)
        self._error.hidden = snapshot.last_error is None
        if snapshot.last_error is not None:
            self._error.title = f"Last error: {snapshot.last_error}"
        running: bool = self._supervisor.is_running()
        transitioning: bool = snapshot.phase in {
            ServicePhase.STARTING,
            ServicePhase.STOPPING,
            ServicePhase.RESTARTING,
        }
        self._set_enabled(
            item=self._start,
            callback=self._start_service,
            enabled=not running and not transitioning,
        )
        self._set_enabled(
            item=self._stop,
            callback=self._stop_service,
            enabled=running and not transitioning,
        )
        self._set_enabled(
            item=self._restart,
            callback=self._restart_service,
            enabled=running and not transitioning,
        )
        endpoint_available: bool = snapshot.mcp_url is not None
        self._set_enabled(
            item=self._open,
            callback=self._open_status_page,
            enabled=endpoint_available,
        )
        self._set_enabled(
            item=self._copy,
            callback=self._copy_mcp_endpoint,
            enabled=endpoint_available,
        )


def run_menu_bar(
    *,
    config: RuntimeConfig,
    service_runner: ServiceRunner,
) -> int:
    """Run the native menu-bar application and managed MCP service.

    Args:
        config: Service settings reused by Start and Restart.
        service_runner: Async Exactus MCP service entry point.

    Returns:
        Zero after the user quits the menu application.

    """
    activity: ServiceActivity = ServiceActivity()
    supervisor: ServiceSupervisor = ServiceSupervisor(
        config=config,
        activity=activity,
        service_runner=service_runner,
    )
    application: MacMenuBarApplication = MacMenuBarApplication(
        activity=activity,
        supervisor=supervisor,
    )
    _ = supervisor.start()
    application.run()
    _ = supervisor.shutdown(timeout=Constants.shutdown_timeout)
    return 0
