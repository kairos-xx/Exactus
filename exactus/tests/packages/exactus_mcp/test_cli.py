# Copyright (c) 2026
"""Validate Exactus MCP command-line configuration."""

from argparse import Namespace
from asyncio import Event as AsyncEvent
from asyncio import Task, create_task, sleep, wait_for
from asyncio import run as run_async
from collections.abc import Callable, Coroutine
from contextlib import suppress
from io import StringIO
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast

import pytest

from exactus.packages.exactus_mcp import cli
from exactus.packages.exactus_mcp.activity import ServiceActivity
from exactus.packages.exactus_mcp.cli import RuntimeConfig
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    private,
    private_call,
    require_type,
)


def private_coroutine(
    *,
    owner: object,
    name: str,
    **arguments: object,
) -> Coroutine[object, object, object]:
    """Call a private coroutine function with a typed result.

    Args:
        owner: Module or instance holding the coroutine function.
        name: Coroutine name, including its leading underscore.
        **arguments: Keyword arguments forwarded to the coroutine.

    Returns:
        The coroutine object produced by the call.

    """
    callable_: Callable[..., Coroutine[object, object, object]] = cast(
        typ="Callable[..., Coroutine[object, object, object]]",
        val=private(owner=owner, name=name),
    )
    return callable_(**arguments)


def swallow_kwargs(**kwargs: object) -> None:
    """Accept and discard any keyword arguments.

    Args:
        **kwargs: Ignored keyword arguments.

    """
    del kwargs


def kwargs_namespace(**kwargs: object) -> SimpleNamespace:
    """Convert keyword arguments into a namespace double.

    Args:
        **kwargs: Attributes for the namespace.

    Returns:
        Namespace carrying the supplied attributes.

    """
    return SimpleNamespace(**kwargs)


class LoopingServer:
    """Uvicorn double that serves until asked to exit."""

    def __init__(self, *, config: object = None) -> None:
        """Accept the ASGI configuration.

        Args:
            config: Uvicorn configuration.

        """
        del config
        self.started: bool = True
        self.should_exit: bool = False
        self._stopped: AsyncEvent = AsyncEvent()

    async def serve(self) -> None:
        """Pretend to serve until ``should_exit`` is set."""
        while not self.should_exit:
            with suppress(TimeoutError):
                _ = await wait_for(fut=self._stopped.wait(), timeout=0.01)


def _arguments(*, root: Path, port: int) -> Namespace:
    """Create a complete synthetic command-line namespace.

    Args:
        root: Candidate project root.
        port: Candidate local port.

    Returns:
        Namespace matching the command-line parser contract.

    """
    access_token: str = root.name
    return Namespace(
        root=root,
        host="127.0.0.1",
        port=port,
        access_token=access_token,
        ngrok=True,
        ngrok_command="ngrok",
        ngrok_url=None,
        ngrok_endpoint=None,
        mantledb_namespace=None,
        mantledb_path="url",
        mantledb_timeout=10.0,
        tunnel_timeout=30.0,
        check_timeout=900.0,
        log_level="info",
        menu_bar=False,
    )


def test_config_resolves_root_and_preserves_security_values(
    tmp_path: Path,
) -> None:
    """Valid arguments become a typed runtime configuration.

    Args:
        tmp_path: Existing synthetic project root.

    """
    configured: RuntimeConfig = require_type(
        value=private_call(
            owner=cli,
            name="_config",
            arguments=_arguments(root=tmp_path, port=0),
        ),
        kind=RuntimeConfig,
    )
    expect_equal(actual=configured.root, expected=tmp_path.resolve())
    expect_equal(actual=configured.access_token, expected=tmp_path.name)


def test_config_rejects_invalid_port(tmp_path: Path) -> None:
    """Ports outside the TCP range fail before service startup.

    Args:
        tmp_path: Existing synthetic project root.

    """
    with pytest.raises(
        expected_exception=ValueError,
        match="port must be between",
    ):
        _ = private_call(
            owner=cli,
            name="_config",
            arguments=_arguments(root=tmp_path, port=70_000),
        )


def test_config_rejects_two_ngrok_modes(tmp_path: Path) -> None:
    """Named endpoints and requested URLs cannot run together.

    Args:
        tmp_path: Existing synthetic project root.

    """
    arguments: Namespace = _arguments(root=tmp_path, port=6100)
    arguments.ngrok_url = "https://example.ngrok-free.app"
    arguments.ngrok_endpoint = "configured-endpoint"
    with pytest.raises(
        expected_exception=ValueError,
        match="mutually exclusive",
    ):
        _ = private_call(owner=cli, name="_config", arguments=arguments)


def test_main_lists_json_configuration_with_secrets_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare ``--config`` prints resolved values without credential text.

    Args:
        tmp_path: Temporary project and configuration directory.
        monkeypatch: Pytest process-state fixture.

    """
    path: Path = tmp_path / "service.json"
    _ = path.write_text(
        data=(
            "{"
            f'"root": "{tmp_path}", '
            '"access-token": "private-bearer", '
            '"mantledb-namespace": "private-namespace", '
            '"port": 6100'
            "}"
        ),
        encoding="utf-8",
    )
    path.chmod(mode=0o600)
    monkeypatch.setattr(
        target=cli,
        name="argv",
        value=["exactus-mcp", f"--config={path}", "--config"],
    )
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=cli, name="stdout", value=stream)
    result: int = cli.main()
    output: str = stream.getvalue()
    expect_equal(actual=result, expected=0)
    expect_in(member='"access-token": "<redacted>"', container=output)
    expect_in(member='"mantledb-namespace": "<redacted>"', container=output)
    expect_in(member='"port": 6100', container=output)
    expect_not_in(member="private-bearer", container=output)
    expect_not_in(member="private-namespace", container=output)


def test_configuration_root_reads_both_option_forms(tmp_path: Path) -> None:
    """``--root`` resolves from either CLI spelling before parsing.

    Args:
        tmp_path: Isolated project root.

    """
    expect_equal(
        actual=private_call(
            owner=cli,
            name="_configuration_root",
            values=(f"--root={tmp_path}", "--config"),
        ),
        expected=tmp_path.resolve(),
    )
    expect_equal(
        actual=private_call(
            owner=cli,
            name="_configuration_root",
            values=("--root", str(object=tmp_path), "--port", "1"),
        ),
        expected=tmp_path.resolve(),
    )
    expect_equal(
        actual=private_call(
            owner=cli,
            name="_configuration_root",
            values=("--root",),
        ),
        expected=Path.cwd().resolve(),
    )


@pytest.mark.parametrize(
    ("attribute", "value", "match"),
    [
        ("tunnel_timeout", 0.0, "timeouts must be greater than zero"),
        ("mantledb_namespace", "   ", "namespace cannot be empty"),
        ("mantledb_path", "", "path cannot be empty"),
    ],
)
def test_config_rejects_invalid_timeouts_and_mantledb(
    attribute: str,
    value: object,
    match: str,
    tmp_path: Path,
) -> None:
    """Zero timeouts and blank MantleDB values fail validation.

    Args:
        attribute: Namespace attribute under test.
        value: Invalid attribute value.
        match: Expected error text.
        tmp_path: Isolated project root.

    """
    arguments: Namespace = _arguments(root=tmp_path, port=0)
    setattr(arguments, attribute, value)
    with pytest.raises(expected_exception=ValueError, match=match):
        _ = private_call(owner=cli, name="_config", arguments=arguments)


def test_config_rejects_missing_root(tmp_path: Path) -> None:
    """A nonexistent project root fails validation.

    Args:
        tmp_path: Isolated project root.

    """
    arguments: Namespace = _arguments(root=tmp_path / "missing", port=0)
    with pytest.raises(expected_exception=ValueError, match="not a directory"):
        _ = private_call(owner=cli, name="_config", arguments=arguments)


def test_wait_started_reports_early_exit_and_timeout() -> None:
    """Uvicorn startup failures surface as runtime errors."""

    class DeadServer:
        """Server double that exits before accepting requests."""

        started: bool = False
        should_exit: bool = True

    with pytest.raises(expected_exception=RuntimeError, match="exited before"):
        run_async(
            main=private_coroutine(
                owner=cli,
                name="_wait_started",
                server=DeadServer(),
                startup_timeout=60.0,
            ),
        )

    class StalledServer:
        """Server double that never reports readiness."""

        started: bool = False
        should_exit: bool = False

    with pytest.raises(expected_exception=RuntimeError, match="did not start"):
        run_async(
            main=private_coroutine(
                owner=cli,
                name="_wait_started",
                server=StalledServer(),
                startup_timeout=0.0,
            ),
        )


def test_wait_for_stop_returns_once_event_set() -> None:
    """A pre-set stop event completes the stop waiter immediately."""
    stop_requested: Event = Event()
    stop_requested.set()
    result: object = run_async(
        main=private_coroutine(
            owner=cli,
            name="_wait_for_stop",
            stop_requested=stop_requested,
        ),
    )
    expect_equal(actual=result, expected=None)


def test_start_tunnel_disabled_returns_none(tmp_path: Path) -> None:
    """A disabled tunnel skips ngrok and MantleDB entirely.

    Args:
        tmp_path: Isolated project root.

    """
    arguments: Namespace = _arguments(root=tmp_path, port=0)
    arguments.ngrok = False
    config: RuntimeConfig = require_type(
        value=private_call(owner=cli, name="_config", arguments=arguments),
        kind=RuntimeConfig,
    )
    bearer: str = "token"
    result: object = run_async(
        main=private_coroutine(
            owner=cli,
            name="_start_tunnel",
            config=config,
            state=SimpleNamespace(local_url="http://127.0.0.1:1"),
            activity=ServiceActivity(),
            access_token=bearer,
        ),
    )
    expect_equal(actual=result, expected=None)


def test_start_tunnel_publishes_url_and_mantledb_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A started tunnel updates state and stores its public URL.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    saved: list[str] = []

    class FakeTunnel:
        """Tunnel double exposing a fixed public URL."""

        public_url: str = "https://demo.ngrok-free.app"

        @classmethod
        async def start(cls, **kwargs: object) -> "FakeTunnel":
            """Return a running tunnel double.

            Args:
                **kwargs: Ignored tunnel settings.

            Returns:
                Fake tunnel instance.

            """
            del kwargs
            return cls()

    class FakeStore:
        """MantleDB store double recording saved URLs."""

        def __init__(self, **kwargs: object) -> None:
            """Accept store settings.

            Args:
                **kwargs: Ignored store settings.

            """
            del kwargs

        @staticmethod
        def save(*, url: str) -> None:
            """Record the published tunnel URL.

            Args:
                url: Public tunnel URL.

            """
            saved.append(url)

    class FakeState:
        """State double recording public URL updates."""

        local_url: str = "http://127.0.0.1:1"

        @staticmethod
        def expose(*, public_url: str) -> None:
            """Record the exposed public URL.

            Args:
                public_url: Public tunnel URL.

            """
            saved.append(f"expose:{public_url}")

    monkeypatch.setattr(target=cli, name="NgrokTunnel", value=FakeTunnel)
    monkeypatch.setattr(target=cli, name="MantleUrlStore", value=FakeStore)
    arguments: Namespace = _arguments(root=tmp_path, port=0)
    arguments.mantledb_namespace = "namespace"
    config: RuntimeConfig = require_type(
        value=private_call(owner=cli, name="_config", arguments=arguments),
        kind=RuntimeConfig,
    )
    bearer: str = "token"
    tunnel: object = run_async(
        main=private_coroutine(
            owner=cli,
            name="_start_tunnel",
            config=config,
            state=FakeState(),
            activity=ServiceActivity(),
            access_token=bearer,
        ),
    )
    expect_equal(
        actual=saved,
        expected=[
            "expose:https://demo.ngrok-free.app",
            "https://demo.ngrok-free.app",
        ],
    )
    expect_true(condition=isinstance(tunnel, FakeTunnel))


def test_run_service_serves_until_stop_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The lifecycle loop serves, prints connection info, then stops.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(target=cli, name="Server", value=LoopingServer)
    monkeypatch.setattr(target=cli, name="Config", value=kwargs_namespace)
    monkeypatch.setattr(
        target=cli,
        name="create_application",
        value=kwargs_namespace,
    )
    monkeypatch.setattr(
        target=cli,
        name="ExactusMcpService",
        value=kwargs_namespace,
    )
    monkeypatch.setattr(
        target=cli,
        name="ExactusCommandRunner",
        value=kwargs_namespace,
    )
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=cli, name="stdout", value=stream)
    arguments: Namespace = _arguments(root=tmp_path, port=0)
    arguments.ngrok = False
    config: RuntimeConfig = require_type(
        value=private_call(owner=cli, name="_config", arguments=arguments),
        kind=RuntimeConfig,
    )
    stop_requested: Event = Event()

    async def delayed_stop() -> None:
        """Request shutdown after the service settles."""
        await sleep(delay=0.1)
        stop_requested.set()

    async def scenario() -> int:
        """Run the service with a delayed stop request.

        Returns:
            Service exit status.

        """
        task: Task[None] = create_task(coro=delayed_stop())
        result: object = await private_coroutine(
            owner=cli,
            name="run_service",
            config=config,
            stop_requested=stop_requested,
        )
        await task
        return cast(typ="int", val=result)

    result: int = run_async(main=scenario())
    expect_equal(actual=result, expected=0)
    expect_in(member="Exactus MCP is ready", container=stream.getvalue())
    expect_in(member="Bearer token:", container=stream.getvalue())


def test_run_service_marks_failed_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A startup failure records the error and re-raises it.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """

    class DeadServer:
        """Uvicorn double that exits immediately."""

        def __init__(self, *, config: object) -> None:
            """Accept the ASGI configuration.

            Args:
                config: Uvicorn configuration.

            """
            del config
            self.started: bool = False
            self.should_exit: bool = True

        async def serve(self) -> None:
            """Complete immediately like an exited process."""

    monkeypatch.setattr(target=cli, name="Server", value=DeadServer)
    monkeypatch.setattr(target=cli, name="Config", value=kwargs_namespace)
    monkeypatch.setattr(
        target=cli,
        name="create_application",
        value=kwargs_namespace,
    )
    monkeypatch.setattr(
        target=cli,
        name="ExactusMcpService",
        value=kwargs_namespace,
    )
    monkeypatch.setattr(
        target=cli,
        name="ExactusCommandRunner",
        value=kwargs_namespace,
    )
    monkeypatch.setattr(
        target=cli,
        name="_show_connection",
        value=swallow_kwargs,
    )
    arguments: Namespace = _arguments(root=tmp_path, port=0)
    arguments.ngrok = False
    config: RuntimeConfig = require_type(
        value=private_call(owner=cli, name="_config", arguments=arguments),
        kind=RuntimeConfig,
    )
    activity: ServiceActivity = ServiceActivity()
    with pytest.raises(expected_exception=RuntimeError, match="exited"):
        run_async(
            main=private_coroutine(
                owner=cli,
                name="run_service",
                config=config,
                activity=activity,
            ),
        )


def test_wait_for_runtime_surfaces_tunnel_exit() -> None:
    """An early tunnel exit aborts the runtime wait with its status."""

    class FakeTunnel:
        """Tunnel double that exits immediately with a status."""

        @staticmethod
        async def wait() -> int:
            """Return an unexpected exit status.

            Returns:
                Tunnel exit status.

            """
            return 7

    async def scenario() -> None:
        """Run the runtime wait with a completing tunnel task."""
        server: LoopingServer = LoopingServer()
        server_task: Task[None] = create_task(coro=server.serve())
        stop: Event = Event()
        stop_task: Task[object] = create_task(
            coro=private_coroutine(
                owner=cli,
                name="_wait_for_stop",
                stop_requested=stop,
            ),
        )
        with pytest.raises(expected_exception=RuntimeError, match="status 7"):
            await private_coroutine(
                owner=cli,
                name="_wait_for_runtime",
                server=server,
                server_task=server_task,
                tunnel=FakeTunnel(),
                stop_task=stop_task,
                activity=ServiceActivity(),
            )
        server.should_exit = True
        stop.set()
        await server_task
        await stop_task

    run_async(main=scenario())


def test_macos_menu_bar_guard_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-macOS platforms reject and dispatch reaches the menu module.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.setattr(target=cli, name="sys_platform", value="linux")
    with pytest.raises(expected_exception=ValueError, match="only on macOS"):
        private_call(owner=cli, name="_require_macos_menu_bar")
    ran: list[object] = []

    def fake_menu(*, config: object, service_runner: object) -> int:
        """Record the menu-bar invocation.

        Args:
            config: Runtime configuration.
            service_runner: Service coroutine factory.

        Returns:
            Menu exit status.

        """
        ran.extend((config, service_runner))
        return 3

    def fake_import(*, name: str) -> SimpleNamespace:
        """Return a menu module double.

        Args:
            name: Unused module name.

        Returns:
            Module double exposing ``run_menu_bar``.

        """
        del name
        return SimpleNamespace(run_menu_bar=fake_menu)

    monkeypatch.setattr(target=cli, name="import_module", value=fake_import)
    result: object = private_call(
        owner=cli,
        name="_run_macos_menu_bar",
        config=SimpleNamespace(tag="config"),
    )
    expect_equal(actual=result, expected=3)
    expect_equal(actual=len(ran), expected=2)


def test_main_runs_service_via_run_async(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A normal invocation hands the coroutine to ``run_async``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    seen: list[object] = []

    def fake_run_async(*, main: object) -> int:
        """Record and close the service coroutine.

        Args:
            main: Service coroutine.

        Returns:
            Process exit status.

        """
        seen.append(main)
        coroutine: Coroutine[object, object, object] = cast(
            typ="Coroutine[object, object, object]",
            val=main,
        )
        coroutine.close()
        return 0

    monkeypatch.setattr(target=cli, name="run_async", value=fake_run_async)
    monkeypatch.setattr(
        target=cli,
        name="argv",
        value=["exactus-mcp", "--root", str(object=tmp_path), "--no-menu-bar"],
    )
    result: int = cli.main()
    expect_equal(actual=result, expected=0)
    expect_equal(actual=len(seen), expected=1)


def test_main_reports_errors_and_interrupts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Configuration errors return one; interrupts return zero.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(
        target=cli,
        name="argv",
        value=["exactus-mcp", "--root", str(object=tmp_path / "missing")],
    )
    stream: StringIO = StringIO()
    monkeypatch.setattr(target=cli, name="stderr", value=stream)
    expect_equal(actual=cli.main(), expected=1)
    expect_in(member="exactus-mcp:", container=stream.getvalue())

    def interrupted(*, values: tuple[str, ...]) -> object:
        """Simulate Ctrl-C during option selection.

        Args:
            values: Unused raw arguments.

        Returns:
            Unreachable value; the call always raises.

        Raises:
            KeyboardInterrupt: Always.

        """
        del values
        raise KeyboardInterrupt

    monkeypatch.setattr(target=cli, name="select_config", value=interrupted)
    expect_equal(actual=cli.main(), expected=0)
