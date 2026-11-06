"""Exercise native menu lifecycle with an isolated status-library adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from sys import modules
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from exactus.packages.exactus_mcp.activity import ServiceActivity
from exactus.packages.exactus_mcp.supervisor import ServiceSupervisor
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    private,
    private_call,
    require_type,
)

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from exactus.packages.exactus_mcp.macos_menu import (
        MacMenuBarApplication,
        MenuCallback,
        NativeMenuItem,
    )


@dataclass(slots=True)
class MenuItem:
    """Represent the native item's mutable presentation and callback.

    Attributes:
        title: Visible menu label.
        callback: Enabled action, or None.
        hidden: Visibility state.
        children: Submenu entries.

    """

    title: str
    callback: MenuCallback | None = None
    hidden: bool = False
    children: list[NativeMenuItem] = field(default_factory=list)

    def set_callback(self, callback: MenuCallback | None) -> None:
        """Replace the enabled action.

        Args:
            callback: New enabled action.

        """
        self.callback = callback

    def add(self, menuitem: NativeMenuItem) -> None:
        """Append a submenu entry.

        Args:
            menuitem: New submenu entry.

        """
        self.children.append(menuitem)


@pytest.fixture
def menu_module() -> ModuleType:
    """Import the controller without loading platform-native bindings.

    Returns:
        Controller module using a replaceable native adapter.

    """
    with patch.dict(in_dict=modules, values={"rumps": MagicMock()}):
        return import_module(name="exactus.packages.exactus_mcp.macos_menu")


def _application(
    *,
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> tuple[MacMenuBarApplication, ServiceActivity, MagicMock, MagicMock]:
    """Build a controller with controlled native and supervisor boundaries.

    Args:
        module: Imported controller module.
        monkeypatch: Adapter replacement fixture.
        root: Displayed project root.

    Returns:
        Controller, real activity, supervisor double and native double.

    """
    native: MagicMock = MagicMock()
    native.MenuItem.side_effect = MenuItem
    supervisor: MagicMock = MagicMock(spec=ServiceSupervisor)
    supervisor.root = root
    supervisor.public_tunnel_enabled = True
    supervisor.is_running.return_value = False
    monkeypatch.setattr(target=module, name="RUMPS", value=native)
    activity: ServiceActivity = ServiceActivity()
    application: MacMenuBarApplication = cast(
        typ="MacMenuBarApplication",
        val=module.MacMenuBarApplication(
            activity=activity,
            supervisor=supervisor,
        ),
    )
    return application, activity, supervisor, native


def _item(*, application: MacMenuBarApplication, name: str) -> MenuItem:
    """Read one presentation item for contract assertions.

    Args:
        application: Controller under test.
        name: Internal menu item binding.

    Returns:
        Concrete fake menu item.

    """
    return require_type(
        value=private(owner=application, name=name),
        kind=MenuItem,
    )


@pytest.mark.parametrize(
    "phase",
    ["running", "updating", "failed", "starting", "disabled"],
)
def test_menu_renders_lifecycle_and_action_availability(
    menu_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
) -> None:
    """Display real service snapshots without stale enabled controls.

    Args:
        menu_module: Isolated controller module.
        monkeypatch: Boundary replacement fixture.
        tmp_path: Displayed project root.
        phase: Service state to render.

    """
    application, activity, supervisor, _native = _application(
        module=menu_module,
        monkeypatch=monkeypatch,
        root=tmp_path,
    )
    if phase == "running":
        supervisor.is_running.return_value = True
        activity.mark_running(
            local_url="http://127.0.0.1:6100",
            public_url="https://example.test",
        )
        _ = activity.begin_call(name="docs", request_metadata={})
    elif phase == "updating":
        activity.mark_updating(local_url="http://127.0.0.1:6100")
    elif phase == "failed":
        activity.mark_failed(error="startup failed")
    elif phase == "starting":
        activity.mark_starting()
    else:
        supervisor.public_tunnel_enabled = False
    _ = private_call(owner=application, name="_refresh")
    expect_equal(
        actual=_item(application=application, name="_project").title,
        expected=f"Project: {tmp_path.name}",
    )
    expect_equal(
        actual=_item(application=application, name="_stop").callback
        is not None,
        expected=phase == "running",
    )
    expect_equal(
        actual=_item(application=application, name="_start").callback
        is not None,
        expected=phase not in {"starting", "running"},
    )
    expect_equal(
        actual=_item(application=application, name="_error").hidden,
        expected=phase != "failed",
    )
    expected_public: dict[str, str] = {
        "running": "https://example.test",
        "updating": "Updating…",
        "disabled": "Disabled",
    }
    expect_equal(
        actual=_item(application=application, name="_public").title,
        expected=f"Public tunnel: {
            expected_public.get(phase, 'Not available')
        }",
    )
    if phase == "running":
        expect_in(
            member="1 active",
            container=_item(application=application, name="_status").title,
        )
        expect_in(
            member="Last call: docs",
            container=_item(application=application, name="_last_call").title,
        )


def test_menu_actions_use_supervisor_and_preferred_connection(
    menu_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Dispatch controls and connection actions through their owned boundaries.

    Args:
        menu_module: Isolated controller module.
        monkeypatch: Boundary replacement fixture.
        tmp_path: Displayed project root.

    """
    application, activity, supervisor, _native = _application(
        module=menu_module,
        monkeypatch=monkeypatch,
        root=tmp_path,
    )
    browser: MagicMock = MagicMock()
    clipboard: MagicMock = MagicMock()
    monkeypatch.setattr(target=menu_module, name="open_url", value=browser)
    monkeypatch.setattr(target=menu_module, name="run", value=clipboard)
    sender: MenuItem = MenuItem(title="sender")
    action: str
    for action in (
        "_start_service",
        "_stop_service",
        "_restart_service",
        "_open_status_page",
        "_copy_mcp_endpoint",
    ):
        _ = private_call(owner=application, name=action, _sender=sender)
    supervisor.start.assert_called_once_with()
    supervisor.stop.assert_called_once_with()
    supervisor.restart.assert_called_once_with()
    browser.assert_not_called()
    clipboard.assert_not_called()
    activity.mark_running(
        local_url="http://127.0.0.1:6100",
        public_url="https://example.test",
    )
    _ = private_call(
        owner=application,
        name="_open_status_page",
        _sender=sender,
    )
    _ = private_call(
        owner=application,
        name="_copy_mcp_endpoint",
        _sender=sender,
    )
    browser.assert_called_once_with(url="https://example.test/")
    clipboard.assert_called_once_with(
        args=("/usr/bin/pbcopy",),
        input="https://example.test/mcp",
        check=True,
        text=True,
    )


@pytest.mark.parametrize("running", [False, True])
def test_menu_quits_after_stop_or_deadline(
    *,
    menu_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: bool,
) -> None:
    """Quit waits for shutdown but cannot hang indefinitely.

    Args:
        menu_module: Isolated controller module.
        monkeypatch: Boundary replacement fixture.
        tmp_path: Displayed project root.
        running: Whether shutdown initially remains pending.

    """
    application, _activity, supervisor, native = _application(
        module=menu_module,
        monkeypatch=monkeypatch,
        root=tmp_path,
    )
    clock: MagicMock = MagicMock(return_value=10.0)
    monkeypatch.setattr(target=menu_module, name="monotonic", value=clock)
    supervisor.is_running.return_value = running
    _ = private_call(
        owner=application,
        name="_refresh_from_timer",
        _timer=native.Timer.return_value,
    )
    native.quit_application.assert_not_called()
    _ = private_call(
        owner=application,
        name="_quit_exactus",
        _sender=MenuItem(title="Quit"),
    )
    expect_equal(
        actual=native.quit_application.call_count,
        expected=0 if running else 1,
    )
    clock.return_value = 20.0
    _ = private_call(
        owner=application,
        name="_refresh_from_timer",
        _timer=native.Timer.return_value,
    )
    expect_equal(
        actual=native.quit_application.call_count,
        expected=1 if running else 2,
    )


@pytest.mark.parametrize("failure", [None, RuntimeError("native loop failed")])
def test_native_timer_is_stopped_when_run_loop_exits(
    menu_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: RuntimeError | None,
) -> None:
    """The native refresh timer is stopped even after a run-loop failure.

    Args:
        menu_module: Isolated controller module.
        monkeypatch: Boundary replacement fixture.
        tmp_path: Displayed project root.
        failure: Optional native run-loop failure.

    """
    application, _activity, _supervisor, native = _application(
        module=menu_module,
        monkeypatch=monkeypatch,
        root=tmp_path,
    )
    native.App.return_value.run.side_effect = failure
    if failure is None:
        application.run()
    else:
        with pytest.raises(
            expected_exception=RuntimeError,
            match="native loop failed",
        ):
            application.run()
    native.Timer.return_value.start.assert_called_once_with()
    native.Timer.return_value.stop.assert_called_once_with()
