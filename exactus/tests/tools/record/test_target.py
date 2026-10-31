# Copyright (c) 2026 Project contributors
"""Cover the application target: its rules, file format and running service."""

from __future__ import annotations

from socket import socket
from sys import executable
from time import monotonic, sleep
from typing import TYPE_CHECKING, Final, TypedDict, final

import pytest

from exactus.packages.http_process import BindScope, HttpServer, IpFamily
from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.model import Target, TargetMode, Workspace
from exactus.tools.record.store import WorkspaceCodec, WorkspaceError
from exactus.tools.record.studio.target_service import (
    TargetService,
    best_server,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.record.store import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        server: Grouped module constant.

    """

    server: Final[tuple[str, ...]] = (
        executable,
        "-m",
        "http.server",
        "0",
        "--bind",
        "127.0.0.1",
    )


class _TargetFields(TypedDict, total=False):
    """Target settings a rejection case submits.

    Attributes:
        mode: Whether the address is given or a service is started.
        url: Address field.
        port: Port field.
        command: Service program and arguments.
        cwd: Working directory inside the project.
        service_port: Fixed service port.
        path: Page path on the service.

    """

    mode: TargetMode
    url: str
    port: int
    command: tuple[str, ...]
    cwd: str
    service_port: int
    path: str


def _service(root: Path) -> tuple[TargetService, list[Event]]:
    """Create a service that records every state it reports.

    Args:
        root: Project folder.

    Returns:
        The service and the list its states are appended to.

    """
    events: list[Event] = []
    return (TargetService(root=root, emit=events.append), events)


def _await(service: TargetService, *states: str) -> dict[str, JsonValue]:
    """Wait until the service reports one of the given states.

    Args:
        service: Service being watched.
        *states: Acceptable states.

    Returns:
        The snapshot in that state.

    """
    deadline: float = monotonic() + 30
    snapshot: dict[str, JsonValue] = service.snapshot()
    while snapshot.get("state") not in states and monotonic() < deadline:
        sleep(0.05)
        snapshot = service.snapshot()
    expect_true(
        condition=snapshot.get("state") in states,
        message=f"Service stayed {snapshot!r}.",
    )
    return snapshot


def test_url_target_builds_its_address_from_url_and_port() -> None:
    """Use the port field, default per scheme, and keep the path."""
    expect_equal(actual=Target().address(), expected="about:blank")
    expect_equal(
        actual=Target(url="localhost", port=3000).address(),
        expected="http://localhost:3000",
    )
    expect_equal(
        actual=Target(url="http://example.com/app?x=1").address(),
        expected="http://example.com/app?x=1",
    )
    expect_equal(
        actual=Target(url="https://example.com").address(),
        expected="https://example.com",
    )
    expect_equal(
        actual=Target(url="http://[::1]", port=8080).address(),
        expected="http://[::1]:8080",
    )
    service: Target = Target(
        mode=TargetMode.SERVICE,
        command=("npm", "run", "dev"),
        path="/app",
    )
    expect_equal(
        actual=service.address(service_url="http://127.0.0.1:5173"),
        expected="http://127.0.0.1:5173/app",
    )
    expect_equal(actual=service.address(), expected="about:blank")


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"url": "ftp://example.com"}, "http://"),
        ({"url": "http://user:secret@example.com"}, "login"),
        ({"url": "http://example.com:80"}, "port field"),
        ({"port": 0}, "port"),
        ({"port": 70000}, "port"),
        ({"service_port": 99999}, "port"),
        ({"mode": TargetMode.SERVICE}, "command"),
        ({"command": ("",)}, "non-empty"),
        ({"cwd": "../outside"}, "inside the project"),
        ({"cwd": "/etc"}, "inside the project"),
        ({"path": "no-slash"}, "path"),
        ({"path": "/with space"}, "path"),
    ],
)
def test_target_rejects_unusable_settings(
    fields: _TargetFields,
    message: str,
) -> None:
    """Refuse addresses, ports, commands and folders Studio cannot honour.

    Args:
        fields: Settings that must be rejected.
        message: Part of the explanation the user must see.

    """
    with pytest.raises(expected_exception=ValueError, match=message):
        Target(**fields)


def test_target_round_trips_and_a_typed_port_moves_to_the_port_field() -> None:
    """Persist the target, default old projects, and accept host:port."""
    target: Target = Target(
        mode=TargetMode.SERVICE,
        command=("npm", "run", "dev"),
        cwd="web",
        service_port=5173,
        path="/login",
    )
    saved: JsonValue = WorkspaceCodec.to_json_value(
        workspace=Workspace(flows=(), edges=(), target=target),
    )
    expect_equal(
        actual=WorkspaceCodec.from_json_value(value=saved).target,
        expected=target,
    )
    legacy: dict[str, JsonValue] = (
        {key: value for key, value in saved.items() if key != "target"}
        if isinstance(saved, dict)
        else {}
    )
    expect_equal(
        actual=WorkspaceCodec.from_json_value(value=legacy).target,
        expected=Target(),
    )
    typed: Target = WorkspaceCodec.parse_target(
        value={"mode": "url", "url": "localhost:3000/app"},
    )
    expect_equal(actual=typed.port, expected=3000)
    expect_equal(actual=typed.address(), expected="http://localhost:3000/app")
    with pytest.raises(expected_exception=WorkspaceError):
        _ = WorkspaceCodec.parse_target(
            value={"mode": "url", "url": "ftp://example.com"},
        )
    with pytest.raises(expected_exception=WorkspaceError):
        _ = WorkspaceCodec.parse_target(value={"command": "not a list"})


def _server(port: int, status: int, scope: BindScope) -> HttpServer:
    """Build a detected server description.

    Args:
        port: Listening port.
        status: HTTP status it answered with.
        scope: Interface it is bound to.

    Returns:
        Server record without an owning process.

    """
    return HttpServer(
        bind_host="127.0.0.1",
        probe_host="127.0.0.1",
        port=port,
        scope=scope,
        family=IpFamily.IPV4,
        url=f"http://127.0.0.1:{port}",
        status=status,
        reason="",
        process=None,
    )


def test_port_detection_prefers_healthy_local_servers_then_lowest_port() -> (
    None
):
    """Pick the page a person most likely means among several listeners."""
    broken: HttpServer = _server(
        port=3000,
        status=500,
        scope=BindScope.LOOPBACK,
    )
    hot_reload: HttpServer = _server(
        port=24678,
        status=200,
        scope=BindScope.LOOPBACK,
    )
    app: HttpServer = _server(port=5173, status=200, scope=BindScope.LOOPBACK)
    exposed: HttpServer = _server(
        port=80,
        status=200,
        scope=BindScope.SPECIFIC,
    )
    expect_equal(actual=best_server(servers=(hot_reload, app)), expected=app)
    expect_equal(actual=best_server(servers=(broken, app)), expected=app)
    expect_equal(actual=best_server(servers=(exposed, app)), expected=app)


def test_service_starts_detects_its_port_and_stops(tmp_path: Path) -> None:
    """Start a real server from the project folder and find its port.

    Args:
        tmp_path: Pytest temporary directory.

    """
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "hello.txt").write_text(data="hello")
    service, events = _service(root=tmp_path)
    target: Target = Target(
        mode=TargetMode.SERVICE,
        command=Constants.server,
        cwd="site",
        path="/hello.txt",
    )
    service.start(target=target)
    try:
        expect_equal(actual=service.snapshot()["state"], expected="starting")
        running: dict[str, JsonValue] = _await(service, "running")
        url: JsonValue = running["url"]
        expect_true(condition=isinstance(url, str))
        expect_equal(
            actual=target.address(service_url=service.base_url),
            expected=f"{url}/hello.txt",
        )
        expect_true(condition=isinstance(running["pid"], int))
        expect_true(condition=bool(running["candidates"]))
        with pytest.raises(expected_exception=ValueError, match="already"):
            service.start(target=target)
        expect_true(
            condition=any(
                event.get("state") == "running"
                for event in events
                if event.get("type") == "target_service"
            ),
        )
        check: dict[str, JsonValue] = service.check(
            target=WorkspaceCodec.parse_target(value={"url": str(object=url)}),
        )
        expect_equal(actual=check["state"], expected="reachable")
    finally:
        service.stop(wait=True)
    expect_equal(actual=service.snapshot()["state"], expected="idle")
    expect_equal(actual=service.base_url, expected=None)


def test_service_honours_a_manually_set_port(tmp_path: Path) -> None:
    """Wait for the port the user named instead of detecting one.

    Args:
        tmp_path: Pytest temporary directory.

    """
    with socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = int(probe.getsockname()[1])
    service, _ = _service(root=tmp_path)
    service.start(
        target=Target(
            mode=TargetMode.SERVICE,
            command=(
                executable,
                "-m",
                "http.server",
                str(object=port),
                "--bind",
                "127.0.0.1",
            ),
            service_port=port,
        ),
    )
    try:
        running: dict[str, JsonValue] = _await(service, "running")
        expect_equal(actual=running["port"], expected=port)
    finally:
        service.stop(wait=True)


def test_service_reports_failures_a_person_can_act_on(tmp_path: Path) -> None:
    """Explain a missing program, an early exit and unsafe folders.

    Args:
        tmp_path: Pytest temporary directory.

    """
    service, _ = _service(root=tmp_path)
    service.start(
        target=Target(
            mode=TargetMode.SERVICE,
            command=("definitely-not-a-real-program-xyz",),
        ),
    )
    failed: dict[str, JsonValue] = _await(service, "failed")
    expect_true(condition="not found" in str(object=failed["error"]))
    service.start(
        target=Target(
            mode=TargetMode.SERVICE,
            command=(executable, "-c", "raise SystemExit(3)"),
        ),
    )
    exited: dict[str, JsonValue] = _await(service, "failed")
    expect_true(condition="exited" in str(object=exited["error"]))
    with pytest.raises(expected_exception=ValueError, match="working"):
        service.start(
            target=Target(
                mode=TargetMode.SERVICE,
                command=Constants.server,
                cwd="missing-folder",
            ),
        )
    outside: Path = tmp_path.parent / "outside-the-project"
    outside.mkdir(exist_ok=True)
    link: Path = tmp_path / "escape"
    link.symlink_to(target=outside, target_is_directory=True)
    with pytest.raises(expected_exception=ValueError, match="working"):
        service.start(
            target=Target(
                mode=TargetMode.SERVICE,
                command=Constants.server,
                cwd="escape",
            ),
        )
    with pytest.raises(expected_exception=ValueError, match="service"):
        service.start(target=Target(url="http://localhost"))


def test_check_tells_reachable_closed_and_unknown_addresses_apart(
    tmp_path: Path,
) -> None:
    """Probe an address without starting anything.

    Args:
        tmp_path: Pytest temporary directory.

    """
    service, _ = _service(root=tmp_path)
    expect_equal(
        actual=service.check(target=Target())["state"],
        expected="unset",
    )
    with socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed: int = int(probe.getsockname()[1])
    expect_equal(
        actual=service.check(
            target=Target(url="http://127.0.0.1", port=closed),
        )["state"],
        expected="unreachable",
    )
    expect_equal(
        actual=service.check(target=Target(url="http://no-such-host.invalid"))[
            "state"
        ],
        expected="unresolved",
    )
