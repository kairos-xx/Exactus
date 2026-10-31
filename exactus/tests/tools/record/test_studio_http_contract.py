# Copyright (c) 2026 Project contributors
"""Verify browser Studio's public HTTP security and mutation contracts."""

from __future__ import annotations

from contextlib import ExitStack
from http import HTTPStatus
from http.client import HTTPConnection
from json import dumps, loads
from pathlib import Path
from re import findall
from time import monotonic, sleep
from typing import TYPE_CHECKING, NamedTuple, cast
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.record import studio as studio_package
from exactus.tools.record.model import EventKind
from exactus.tools.record.studio.events import EventBus
from exactus.tools.record.studio.service import StudioService

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from http.client import HTTPResponse
    from urllib.parse import SplitResult

    from exactus.tools.record.model import (
        ExecutionRun,
        Flow,
        TimelineEvent,
        Workspace,
    )
    from exactus.tools.record.store import JsonValue


class Reply(NamedTuple):
    """HTTP response observed by a browser client.

    Attributes:
        status: HTTP status code.
        body: Raw response bytes.
        headers: Response headers.

    """

    status: int
    body: bytes
    headers: dict[str, str]


@pytest.mark.parametrize(
    "asset",
    [
        "index.js",
        "widget_clock.js",
        "examples/web/style.css",
        "examples/web/index.html",
    ],
)
def test_clock_package_assets(service: StudioService, asset: str) -> None:
    """Serve the clock and demo through the packaged asset allowlist.

    Args:
        service: Ready loopback Studio service.
        asset: Relative package asset path under test.

    """
    reply: Reply = request(
        service=service,
        path=f"/studio/packages/widgets/widget_clock/{asset}",
    )
    expect_equal(actual=reply.status, expected=HTTPStatus.OK)
    expect_true(condition=bool(reply.body))


def test_clock_package_asset_allowlist(service: StudioService) -> None:
    """Do not expose Python package files alongside browser assets.

    Args:
        service: Ready loopback Studio service.

    """
    reply: Reply = request(
        service=service,
        path="/studio/packages/widgets/widget_clock/__init__.py",
    )
    expect_equal(actual=reply.status, expected=HTTPStatus.NOT_FOUND)


def test_clock_module_root_alias(service: StudioService) -> None:
    """Resolve the module import from both static files and Studio URLs.

    Args:
        service: Ready loopback Studio service.

    """
    reply: Reply = request(
        service=service,
        path="/packages/widgets/widget_clock/index.js",
    )
    expect_equal(actual=reply.status, expected=HTTPStatus.OK)
    expect_in(member=b"export", container=reply.body)


@pytest.mark.parametrize(
    "asset",
    [
        "extended-selector.js",
        "extended-selector-editor.js",
        "extended-selector-editor.css",
    ],
)
def test_extended_selector_assets_are_served(
    service: StudioService,
    asset: str,
) -> None:
    """Serve the ExtendedSelector package engine and editor to the Studio page.

    Args:
        service: Ready loopback Studio service.
        asset: Vendored file name under test.

    """
    reply: Reply = request(
        service=service,
        path=f"/studio/packages/extended_selector/editor/{asset}",
    )
    expect_equal(actual=reply.status, expected=HTTPStatus.OK)
    expect_true(condition=bool(reply.body))


def test_package_projects_are_served_from_the_root_package_folder(
    service: StudioService,
) -> None:
    """Map ``/packages/...`` to the top-level package folder for browser files.

    Args:
        service: Ready loopback Studio service.

    """
    served: Reply = request(
        service=service,
        path="/packages/extended_selector/editor/extended-selector.js",
    )
    expect_equal(actual=served.status, expected=HTTPStatus.OK)
    expect_in(member=b"export", container=served.body)
    for hidden in (
        "/studio/packages/extended_selector/__init__.py",
        "/studio/packages/extended_selector/package.json",
        "/studio/packages/extended_selector/../README.md",
    ):
        reply: Reply = request(service=service, path=hidden)
        expect_equal(actual=reply.status, expected=HTTPStatus.NOT_FOUND)


@pytest.fixture
def service(tmp_path: Path) -> Iterator[StudioService]:
    """Serve one isolated workspace without opening a target browser.

    Args:
        tmp_path: Disposable project storage.

    Yields:
        Ready loopback service.

    """
    application: StudioService = StudioService(root=tmp_path, headless=True)
    application.start()
    try:
        yield application
    finally:
        application.stop()


def request(
    service: StudioService,
    *,
    path: str,
    headers: dict[str, str] | None = None,
    body: JsonValue = None,
) -> Reply:
    """Send a real HTTP request to the isolated service.

    Args:
        service: Ready local application.
        path: Requested route.
        headers: Additional client headers.
        body: Optional JSON POST body; otherwise use GET.

    Returns:
        Response status, bytes and headers.

    """
    address: SplitResult = urlsplit(url=service.origin)
    connection: HTTPConnection = HTTPConnection(
        host="127.0.0.1",
        port=address.port,
        timeout=5,
    )
    fields: dict[str, str] = {} if headers is None else dict(headers)
    payload: bytes | None = None if body is None else dumps(obj=body).encode()
    if payload is not None:
        fields.setdefault("Content-Type", "application/json")
    try:
        connection.request(
            method="GET" if payload is None else "POST",
            url=path,
            body=payload,
            headers=fields,
        )
        response: HTTPResponse = connection.getresponse()
        return Reply(
            status=response.status,
            body=response.read(),
            headers=dict(response.getheaders()),
        )
    finally:
        connection.close()


def authorized(service: StudioService) -> dict[str, str]:
    """Bootstrap the same-origin cookie through the public session route.

    Args:
        service: Ready local application.

    Returns:
        Protected command headers for the controlling tab.

    """
    reply: Reply = request(
        service=service,
        path="/api/session",
        headers={
            "Origin": service.origin,
            "Authorization": f"Bearer {service.token}",
        },
        body={},
    )
    expect_equal(actual=reply.status, expected=200)
    cookie: str = reply.headers["Set-Cookie"]
    expect_in(member="HttpOnly", container=cookie)
    expect_in(member="SameSite=Strict", container=cookie)
    return {
        "Cookie": cookie.split(sep=";", maxsplit=1)[0],
        "Origin": service.origin,
        "X-Studio-Client": "owner-tab",
    }


def document(reply: Reply) -> dict[str, JsonValue]:
    """Decode an observed JSON response.

    Args:
        reply: Response carrying JSON bytes.

    Returns:
        Public response object.

    """
    return cast(typ="dict[str, JsonValue]", val=loads(s=reply.body))


def test_raw_tab_gets_a_recovery_page_without_weakening_authorization(
    service: StudioService,
) -> None:
    """Explain how to recover when an unauthorized tab opens an API URL.

    Args:
        service: Isolated service.

    """
    page: Reply = request(
        service=service,
        path="/api/snapshot",
        headers={"Accept": "text/html"},
    )
    expect_equal(actual=page.status, expected=401)
    expect_in(member="text/html", container=page.headers["Content-Type"])
    expect_in(member=b"href=/studio/", container=page.body)
    expect_not_in(member=service.token.encode(), container=page.body)
    machine: Reply = request(service=service, path="/api/snapshot")
    expect_equal(actual=machine.status, expected=401)
    expect_equal(
        actual=document(reply=machine)["code"],
        expected="UNAUTHORIZED",
    )
    # Direct navigation still cannot read workspace data.
    for path in ["/api/snapshot", "/api/target-preview"]:
        reply: Reply = request(
            service=service,
            path=path,
            headers={"Accept": "text/html"},
        )
        expect_equal(actual=reply.status, expected=401)


def test_every_imported_stylesheet_and_module_is_served(
    service: StudioService,
) -> None:
    """Serve each stylesheet and module the plain Studio URL depends on.

    Args:
        service: Isolated service.

    """
    web: Path = Path(studio_package.__file__).parent / "web"
    imports: list[str] = []
    pending: list[Path] = [web / "editor.css"]
    while pending:
        sheet: Path = pending.pop()
        for target in findall(
            pattern=r'@import url\("([^"?]+)',
            string=sheet.read_text(encoding="utf-8"),
        ):
            resolved: Path = (sheet.parent / target).resolve()
            imports.append(resolved.relative_to(web.resolve()).as_posix())
            if resolved.relative_to(web.resolve()).parts[0] != "packages":
                pending.append(resolved)
    expect_true(condition=len(imports) > 0)
    # Order is the cascade, so it is not compared. Each stylesheet is imported
    # once and no stylesheet under styles/ is orphaned.
    expect_equal(actual=len(imports), expected=len(set(imports)))
    on_disk: list[str] = sorted(
        item.relative_to(web).as_posix()
        for item in (web / "styles").rglob(pattern="*.css")
    )
    local: list[str] = [item for item in imports if item.startswith("styles/")]
    expect_equal(actual=sorted(local), expected=on_disk)
    modules: list[str] = findall(
        pattern=r'from "\./([a-z-]+\.js)"',
        string=(web / "editor.js").read_text(encoding="utf-8"),
    )
    package_files: list[str] = [
        "exactus/packages/extended_selector/editor/extended-selector.js",
        "exactus/packages/extended_selector/editor/"
        "extended-selector-editor.js",
    ]
    for path in [*imports, *modules, *package_files]:
        reply: Reply = request(service=service, path=f"/studio/{path}")
        expect_equal(actual=reply.status, expected=200)
        expect_true(condition=len(reply.body) > 0)
    expect_in(
        member="[hidden][hidden]",
        container=(
            web / "styles" / "components" / "responsive-docks" / "style.css"
        ).read_text(encoding="utf-8"),
    )


def test_readiness_assets_and_authorization(service: StudioService) -> None:
    """Serve public assets while requiring a cookie for workspace data.

    Args:
        service: Isolated service.

    """
    readiness: Reply = request(service=service, path="/health")
    expect_equal(actual=document(reply=readiness)["ready"], expected=True)
    expect_equal(
        actual=readiness.headers["Cache-Control"],
        expected="no-store",
    )
    editor: Reply = request(service=service, path="/studio/")
    expect_equal(actual=editor.status, expected=200)
    expect_in(member=b"editor.js", container=editor.body)
    editor_cookie: str = editor.headers["Set-Cookie"]
    expect_in(member="HttpOnly", container=editor_cookie)
    expect_in(member="SameSite=Strict", container=editor_cookie)
    canonical: Reply = request(service=service, path="/studio?cache=current")
    expect_equal(
        actual=canonical.status,
        expected=HTTPStatus.PERMANENT_REDIRECT,
    )
    expect_equal(
        actual=canonical.headers["Location"],
        expected="/studio/?cache=current",
    )
    expect_equal(
        actual=canonical.headers["Cache-Control"],
        expected="no-store",
    )
    transport: Reply = request(service=service, path="/studio/transport.js")
    expect_equal(actual=transport.status, expected=200)
    expect_in(member=b"EventSource", container=transport.body)
    expect_not_in(member=b"qwebchannel", container=editor.body.lower())
    denied: Reply = request(service=service, path="/api/snapshot")
    expect_equal(actual=denied.status, expected=401)
    page_headers: dict[str, str] = {
        "Cookie": editor_cookie.split(sep=";", maxsplit=1)[0],
        "Origin": service.origin,
        "X-Studio-Client": "plain-studio-tab",
    }
    page_snapshot: Reply = request(
        service=service,
        path="/api/snapshot?client=plain-studio-tab",
        headers=page_headers,
    )
    expect_equal(actual=page_snapshot.status, expected=200)
    page_command: Reply = request(
        service=service,
        path="/api/command",
        headers=page_headers,
        body={
            "protocol": 1,
            "id": "plain-page-command",
            "command": "workspace.snapshot",
            "revision": document(reply=page_snapshot)["revision"],
        },
    )
    expect_equal(actual=page_command.status, expected=200)
    expect_equal(actual=document(reply=page_command)["ok"], expected=True)
    headers: dict[str, str] = authorized(service=service)
    snapshot: Reply = request(
        service=service,
        path="/api/snapshot",
        headers=headers,
    )
    expect_equal(actual=snapshot.status, expected=200)
    expect_not_in(member=service.token.encode(), container=snapshot.body)
    for path in ["/studio/%2e%2e/service.py", "/studio/missing.js"]:
        expect_equal(
            actual=request(service=service, path=path).status,
            expected=404,
        )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "https://foreign.example"},
        {"Origin": "null"},
        {"Host": "foreign.example"},
    ],
)
def test_bootstrap_rejects_foreign_origins(
    service: StudioService,
    headers: dict[str, str],
) -> None:
    """Reject cross-origin and rebinding attempts even with a valid token.

    Args:
        service: Isolated service.
        headers: Untrusted request headers.

    """
    reply: Reply = request(
        service=service,
        path="/api/session",
        headers={**headers, "Authorization": f"Bearer {service.token}"},
        body={},
    )
    expect_equal(actual=reply.status, expected=403)
    expect_equal(actual=document(reply=reply)["code"], expected="BAD_ORIGIN")


def test_duplicate_commands_and_concurrent_tabs(
    service: StudioService,
) -> None:
    """Deduplicate commands while allowing fresh edits from every tab.

    Args:
        service: Isolated service.

    """
    headers: dict[str, str] = authorized(service=service)
    initial: dict[str, JsonValue] = document(
        reply=request(service=service, path="/api/snapshot", headers=headers),
    )
    command: dict[str, JsonValue] = {
        "protocol": 1,
        "id": "create-once",
        "revision": initial["revision"],
        "command": "flow.create",
        "payload": {},
    }
    first: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body=command,
    )
    repeated: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body=command,
    )
    expect_equal(actual=first.status, expected=200)
    expect_equal(actual=repeated.body, expected=first.body)
    snapshot: dict[str, JsonValue] = document(
        reply=request(service=service, path="/api/snapshot", headers=headers),
    )
    expect_equal(
        actual=snapshot["revision"],
        expected=cast(typ="int", val=initial["revision"]) + 1,
    )
    stale_revision: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body={**command, "id": "stale-edit"},
    )
    expect_equal(actual=stale_revision.status, expected=200)
    reused: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body={**command, "command": "flow.delete"},
    )
    expect_equal(actual=document(reply=reused)["code"], expected="ID_REUSED")
    observer: dict[str, str] = {**headers, "X-Studio-Client": "observer-tab"}
    concurrent: Reply = request(
        service=service,
        path="/api/command",
        headers=observer,
        body={
            **command,
            "id": "observer-edit",
            "revision": initial["revision"],
        },
    )
    expect_equal(actual=concurrent.status, expected=200)
    read: Reply = request(
        service=service,
        path="/api/command",
        headers=observer,
        body={
            **command,
            "id": "observer-read",
            "command": "workspace.snapshot",
        },
    )
    expect_equal(actual=read.status, expected=200)
    expect_equal(
        actual=document(
            reply=request(
                service=service,
                path="/api/snapshot",
                headers=headers,
            ),
        )["revision"],
        expected=cast(typ="int", val=snapshot["revision"]) + 2,
    )


def test_bounded_history_requests_snapshot_after_eviction() -> None:
    """Retain recent ordered events and flag a client whose history expired."""
    events: EventBus = EventBus(capacity=2)
    for index in range(3):
        events.emit_event(name="progress", payload={"step": index})
    lost, rows = events.read(after=0, timeout=0)
    expect_true(condition=lost)
    expect_equal(actual=[sequence for sequence, _ in rows], expected=[2, 3])
    lost, rows = events.read(after=2, timeout=0)
    expect_equal(actual=lost, expected=False)
    expect_equal(actual=len(rows), expected=1)
    record: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=rows[0][1]),
    )
    expect_equal(actual=record["instance_id"], expected=events.instance_id)
    expect_true(condition=EventBus().instance_id != events.instance_id)
    events.close()
    expect_equal(actual=events.read(after=3, timeout=0), expected=(False, ()))


@pytest.mark.parametrize(
    "envelope",
    [
        [],
        {
            "protocol": 2,
            "id": "invalid",
            "command": "flow.create",
            "revision": 0,
        },
        {"protocol": 1, "id": "", "command": "flow.create", "revision": 0},
        {
            "protocol": 1,
            "id": "invalid",
            "command": "flow.create",
            "revision": True,
        },
        {"protocol": 1, "id": "invalid", "command": "unknown", "revision": 0},
    ],
)
def test_invalid_commands_preserve_workspace(
    service: StudioService,
    envelope: JsonValue,
) -> None:
    """Reject malformed or unsupported requests without changing the workspace.

    Args:
        service: Isolated service.
        envelope: Invalid command body.

    """
    headers: dict[str, str] = authorized(service=service)
    before: dict[str, JsonValue] = document(
        reply=request(service=service, path="/api/export", headers=headers),
    )
    if isinstance(envelope, dict) and envelope.get("command") == "unknown":
        envelope = {**envelope, "revision": service.snapshot()["revision"]}
    rejected: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body=envelope,
    )
    expect_equal(actual=rejected.status, expected=400)
    after: dict[str, JsonValue] = document(
        reply=request(service=service, path="/api/export", headers=headers),
    )
    expect_equal(actual=after, expected=before)


def test_import_save_conflict_and_path_boundaries(
    service: StudioService,
    tmp_path: Path,
) -> None:
    """Save Unicode filenames while protecting imports and external edits.

    Args:
        service: Isolated service.
        tmp_path: Project boundary.

    """
    headers: dict[str, str] = authorized(service=service)
    exported: Reply = request(
        service=service,
        path="/api/export",
        headers=headers,
    )
    expect_in(
        member="attachment",
        container=exported.headers["Content-Disposition"],
    )
    before: dict[str, JsonValue] = document(reply=exported)
    revision: JsonValue = service.snapshot()["revision"]

    def command(
        name: str,
        payload: Mapping[str, JsonValue],
        identity: str,
    ) -> Reply:
        """Dispatch one command at the latest authoritative revision.

        Args:
            name: Public command identifier.
            payload: Command parameters.
            identity: Unique request identifier.

        Returns:
            Observed HTTP reply.

        """
        return request(
            service=service,
            path="/api/command",
            headers=headers,
            body={
                "protocol": 1,
                "id": identity,
                "command": name,
                "revision": service.snapshot()["revision"],
                "payload": dict(payload),
            },
        )

    invalid: Reply = command(
        name="workspace.open",
        payload={"workspace": {"version": 99}},
        identity="bad-import",
    )
    expect_equal(actual=invalid.status, expected=400)
    expect_equal(actual=service.snapshot()["revision"], expected=revision)
    expect_equal(
        actual=document(
            reply=request(
                service=service,
                path="/api/export",
                headers=headers,
            ),
        ),
        expected=before,
    )
    filename: str = "résumé flow.pwflow.json"
    saved: Reply = command(
        name="workspace.save",
        payload={"filename": filename},
        identity="save",
    )
    expect_equal(actual=saved.status, expected=200)
    path: Path = tmp_path / filename
    expect_equal(actual=loads(s=path.read_text()), expected=before)
    path.write_text(data=path.read_text() + "\n", encoding="utf-8")
    external: bytes = path.read_bytes()
    conflict: Reply = command(
        name="workspace.save",
        payload={"filename": filename},
        identity="conflicting-save",
    )
    expect_equal(actual=conflict.status, expected=400)
    expect_equal(actual=path.read_bytes(), expected=external)
    for index, unsafe in enumerate(
        iterable=[
            "../escape.pwflow.json",
            str(object=tmp_path.parent / "escape.pwflow.json"),
        ],
    ):
        denied: Reply = command(
            name="workspace.save",
            payload={"filename": unsafe},
            identity=f"escape-{index}",
        )
        expect_equal(actual=denied.status, expected=400)
    absent: Reply = request(
        service=service,
        path="/artifacts/unknown",
        headers=headers,
    )
    expect_equal(actual=absent.status, expected=404)
    expect_equal(
        actual=document(reply=absent)["code"],
        expected="MISSING_ARTIFACT",
    )


@pytest.mark.parametrize(
    ("changes", "status", "code"),
    [
        ({"Content-Type": "text/plain"}, 415, "INVALID_INPUT"),
        ({"Content-Length": "8388609"}, 413, "PAYLOAD_TOO_LARGE"),
        ({"X-Studio-Client": ""}, 400, "INVALID_INPUT"),
        ({"Cookie": "studio=wrong-token"}, 401, "UNAUTHORIZED"),
    ],
)
def test_command_header_and_payload_boundaries(
    service: StudioService,
    changes: dict[str, str],
    status: int,
    code: str,
) -> None:
    """Reject oversized bodies, incorrect media types and missing identities.

    Args:
        service: Isolated service.
        changes: Invalid protected request headers.
        status: Expected HTTP rejection status.
        code: Stable public error code.

    """
    headers: dict[str, str] = {**authorized(service=service), **changes}
    rejected: Reply = request(
        service=service,
        path="/api/command",
        headers=headers,
        body={
            "protocol": 1,
            "id": "header-boundary",
            "command": "workspace.snapshot",
            "revision": service.snapshot()["revision"],
        },
    )
    expect_equal(actual=rejected.status, expected=status)
    expect_equal(actual=document(reply=rejected)["code"], expected=code)


def test_event_subscription_limit_releases_slots(
    service: StudioService,
) -> None:
    """Bound subscriptions and recover capacity when clients disconnect.

    Args:
        service: Isolated service.

    """
    headers: dict[str, str] = authorized(service=service)
    with ExitStack() as clients:
        for _ in range(16):
            _ = clients.enter_context(cm=service.subscriber())
        rejected: Reply = request(
            service=service,
            path="/events",
            headers=headers,
        )
        expect_equal(actual=rejected.status, expected=429)
        expect_equal(
            actual=document(reply=rejected)["code"],
            expected="TOO_MANY_CLIENTS",
        )
    with service.subscriber():
        expect_true(condition=service.running)


def edit(
    *,
    service: StudioService,
    headers: dict[str, str],
    command: str,
    payload: Mapping[str, JsonValue],
    status: int = 200,
) -> dict[str, JsonValue]:
    """Send an edit against the current public revision.

    Args:
        service: Running Studio service.
        headers: Controlling tab credentials.
        command: Supported editor command.
        payload: Command fields.
        status: Expected HTTP status.

    Returns:
        Latest public snapshot after the edit.

    Raises:
        AssertionError: If the edit fails or the snapshot is not updated.

    """
    attempt: int
    reply: Reply
    snapshot: dict[str, JsonValue]
    for attempt in range(20):
        snapshot = service.snapshot()
        reply = request(
            service=service,
            path="/api/command",
            headers=headers,
            body={
                "protocol": 1,
                "id": uuid4().hex,
                "revision": snapshot["revision"],
                "command": command,
                "payload": dict(payload),
            },
        )
        if not (
            status != HTTPStatus.CONFLICT
            and reply.status == HTTPStatus.CONFLICT
            and document(reply=reply).get("code") == "STALE_REVISION"
        ):
            break
        sleep(0.01 * (attempt + 1))
    else:
        msg: str = "Studio revision never settled"
        raise AssertionError(msg)
    expect_equal(actual=reply.status, expected=status)
    return service.snapshot()


def test_editor_flow_steps_assertions_and_connections(
    service: StudioService,
) -> None:
    """Save a populated flow, edit its steps and checks, and connect flows.

    Args:
        service: Running isolated editor.

    """
    headers: dict[str, str] = authorized(service=service)
    initial: str = str(object=service.snapshot()["active_flow_id"])
    _ = edit(
        service=service,
        headers=headers,
        command="flow.update",
        payload={
            "name": "Checkout",
            "task_description": "Complete checkout",
            "expected_behavior": "Receipt appears",
            "device_scope": "shared",
            "capture_record_images": True,
            "capture_play_images": True,
        },
    )
    event_options: tuple[dict[str, JsonValue], ...] = (
        {"kind": "javascript", "payload": "() => 42"},
        {
            "kind": "wait",
            "wait_for": "text",
            "payload": "Ready",
            "timeout_ms": "10",
        },
        {"kind": "screenshot"},
        {"kind": "click", "selector": "button"},
        {"kind": "input_text", "selector": "input", "payload": "Alice"},
        {"kind": "keystroke", "selector": "input", "payload": "Enter"},
        {"kind": "check", "selector": "input"},
        {"kind": "uncheck", "selector": "input"},
        {"kind": "url_change", "url": "https://example.test"},
    )
    for options in event_options:
        _ = edit(
            service=service,
            headers=headers,
            command="event.add",
            payload=options,
        )
    flow: Flow = service.controller.workspace.flows[0]
    expect_equal(actual=len(flow.events), expected=9)
    first: str = flow.events[0].event_id
    _ = edit(
        service=service,
        headers=headers,
        command="event.update",
        payload={"event_id": first, "label": "Answer", "payload": "() => 43"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="event.move",
        payload={"event_id": first, "offset": "1"},
    )
    expect_equal(
        actual=service.controller.workspace.flows[0].events[1].event_id,
        expected=first,
    )
    kind: str
    for kind in ("dom_visible", "dom_text", "url", "title"):
        _ = edit(
            service=service,
            headers=headers,
            command="event.assert",
            payload={
                "event_id": first,
                "kind": kind,
                "target": "body",
                "expected": "Receipt",
            },
        )
    flow = service.controller.workspace.flows[0]
    event: TimelineEvent = next(
        event for event in flow.events if event.event_id == first
    )
    expect_equal(actual=len(event.contract.postconditions), expected=4)
    assertion_id: str = event.contract.postconditions[0].assertion_id
    _ = edit(
        service=service,
        headers=headers,
        command="event.assert.remove",
        payload={"event_id": first, "assertion_id": assertion_id},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="event.delete",
        payload={"event_id": first},
    )
    expect_equal(
        actual=len(service.controller.workspace.flows[0].events),
        expected=8,
    )
    next_snapshot: dict[str, JsonValue] = edit(
        service=service,
        headers=headers,
        command="flow.create",
        payload={},
    )
    second: str = str(object=next_snapshot["active_flow_id"])
    connection: dict[str, JsonValue] = {
        "source": initial,
        "target": second,
        "mode": "condition",
        "condition_expression": "true",
        "priority": "1",
        "max_traversals": "2",
    }
    _ = edit(
        service=service,
        headers=headers,
        command="edge.add",
        payload=connection,
    )
    expect_equal(actual=len(service.controller.workspace.edges), expected=1)
    redefined: dict[str, JsonValue] = {
        **connection,
        "index": "0",
        "mode": "fallback",
        "condition_expression": "",
    }
    _ = edit(
        service=service,
        headers=headers,
        command="edge.update",
        payload=redefined,
    )
    expect_equal(
        actual=service.controller.workspace.edges[0].mode.value,
        expected="fallback",
    )
    _ = edit(
        service=service,
        headers=headers,
        command="edge.add",
        payload={**connection, "source": second, "target": initial},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="edge.move",
        payload={"index": "0", "to": "1"},
    )
    expect_equal(
        actual=service.controller.workspace.edges[1].mode.value,
        expected="fallback",
    )
    _ = edit(
        service=service,
        headers=headers,
        command="edge.remove",
        payload={**connection, "source": second, "target": initial},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="edge.remove",
        payload={**connection, "mode": "fallback", "condition_expression": ""},
    )
    expect_equal(actual=len(service.controller.workspace.edges), expected=0)
    _ = edit(
        service=service,
        headers=headers,
        command="flow.select",
        payload={"flow_id": initial},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="flow.delete",
        payload={"flow_id": second},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="workspace.save",
        payload={"filename": "checkout.pwflow.json"},
    )
    snapshot: dict[str, JsonValue] = edit(
        service=service,
        headers=headers,
        command="workspace.open",
        payload={"filename": "checkout.pwflow.json"},
    )
    expect_equal(actual=snapshot["dirty"], expected=False)
    expect_equal(
        actual=service.controller.workspace.flows[0].name,
        expected="Checkout",
    )


def test_invalid_editor_steps_leave_document_unchanged(
    service: StudioService,
) -> None:
    """Validation rejects invalid waits, moves, checks and graph targets.

    Args:
        service: Running isolated editor.

    """
    headers: dict[str, str] = authorized(service=service)
    _ = edit(
        service=service,
        headers=headers,
        command="event.add",
        payload={
            "kind": "wait",
            "wait_for": "text",
            "payload": "Ready",
            "timeout_ms": "1",
        },
    )
    event_id: str = service.controller.workspace.flows[0].events[0].event_id
    invalid_commands: tuple[tuple[str, dict[str, JsonValue]], ...] = (
        ("event.add", {"kind": "unsupported"}),
        (
            "event.add",
            {
                "kind": "wait",
                "wait_for": "text",
                "payload": "Ready",
                "timeout_ms": "0",
            },
        ),
        (
            "event.add",
            {
                "kind": "wait",
                "wait_for": "text",
                "payload": "Ready",
                "timeout_ms": "60001",
            },
        ),
        ("event.move", {"event_id": event_id, "offset": "2"}),
        ("event.assert", {"event_id": event_id, "kind": "dom_hidden"}),
        ("event.assert", {"event_id": event_id, "kind": "title"}),
        (
            "event.assert.remove",
            {"event_id": event_id, "assertion_id": "missing"},
        ),
        (
            "edge.add",
            {"source": "missing", "target": "missing", "mode": "always"},
        ),
        ("viewport.preset", {"mode": "shared"}),
        (
            "flow.delete",
            {"flow_id": service.controller.workspace.flows[0].flow_id},
        ),
        ("screenshot.open", {"artifact_id": "missing"}),
    )
    for command, payload in invalid_commands:
        _ = edit(
            service=service,
            headers=headers,
            command=command,
            payload=payload,
            status=400,
        )
    expect_equal(
        actual=len(service.controller.workspace.flows[0].events),
        expected=1,
    )


def test_editor_persists_websocket_request_configuration(
    service: StudioService,
) -> None:
    """Create an executable socket action with response-variable mappings.

    Args:
        service: Running isolated editor.

    """
    headers: dict[str, str] = authorized(service=service)
    config: dict[str, JsonValue] = {
        "version": 2,
        "transport": "websocket",
        "protocols": ["updates.v1"],
        "message": '{"type":"subscribe"}',
        "receive_count": 1,
        "timeout_ms": 5000,
        "captures": [
            {
                "source": "message_json",
                "path": "payload.id",
                "name": "Message ID",
                "value_type": "integer",
                "required": True,
            },
        ],
    }
    _ = edit(
        service=service,
        headers=headers,
        command="event.add",
        payload={
            "kind": "websocket_call",
            "url": "wss://stream.example.test/live",
            "request_config": dumps(obj=config),
            "output_variable": "Socket session",
        },
    )
    event: TimelineEvent = service.controller.workspace.flows[0].events[0]
    expect_equal(actual=event.kind, expected=EventKind.WEBSOCKET_CALL)
    expect_equal(actual=event.layer.value, expected="websocket")
    expect_equal(actual=loads(s=event.payload or "{}"), expected=config)
    expect_equal(actual=event.output_variable, expected="Socket session")


def test_editor_rejects_non_websocket_session_urls(
    service: StudioService,
) -> None:
    """Reject HTTP URLs before they become WebSocket actions.

    Args:
        service: Running isolated editor.

    """
    _ = edit(
        service=service,
        headers=authorized(service=service),
        command="event.add",
        payload={
            "kind": "websocket_call",
            "url": "https://stream.example.test/live",
            "request_config": "{}",
        },
        status=400,
    )
    expect_equal(
        actual=len(service.controller.workspace.flows[0].events),
        expected=0,
    )


def test_editor_reorders_and_retimes_steps(service: StudioService) -> None:
    """Steps drop at absolute replay positions and authored times.

    Args:
        service: Running isolated editor.

    """
    headers: dict[str, str] = authorized(service=service)
    for milliseconds in ("10", "20", "30"):
        _ = edit(
            service=service,
            headers=headers,
            command="event.add",
            payload={
                "kind": "wait",
                "wait_for": "text",
                "payload": "Ready",
                "timeout_ms": milliseconds,
            },
        )
    events: tuple[TimelineEvent, ...] = service.controller.workspace.flows[
        0
    ].events
    first: str = events[0].event_id
    _ = edit(
        service=service,
        headers=headers,
        command="event.reorder",
        payload={"event_id": first, "index": "2"},
    )
    events = service.controller.workspace.flows[0].events
    expect_equal(actual=events[2].event_id, expected=first)
    _ = edit(
        service=service,
        headers=headers,
        command="event.retime",
        payload={"event_id": first, "elapsed_ms": "60000"},
    )
    events = service.controller.workspace.flows[0].events
    moved: TimelineEvent = next(
        event for event in events if event.event_id == first
    )
    expect_equal(actual=moved.elapsed_ms, expected=60000)
    expect_equal(actual=events[-1].event_id, expected=first)
    invalid_commands: tuple[tuple[str, dict[str, JsonValue]], ...] = (
        ("event.reorder", {"event_id": "missing", "index": "0"}),
        ("event.reorder", {"event_id": first, "index": "9"}),
        ("event.retime", {"event_id": "missing", "elapsed_ms": "5"}),
        ("event.retime", {"event_id": first, "elapsed_ms": "3600001"}),
    )
    for command, payload in invalid_commands:
        _ = edit(
            service=service,
            headers=headers,
            command=command,
            payload=payload,
            status=400,
        )


def await_state(
    *,
    service: StudioService,
    key: str,
    expected: JsonValue,
) -> dict[str, JsonValue]:
    """Wait for an asynchronous browser result through public snapshots.

    Args:
        service: Running editor.
        key: Snapshot field to observe.
        expected: Required completed state.

    Returns:
        Matching public snapshot.

    """
    deadline: float = monotonic() + 15
    snapshot: dict[str, JsonValue] = service.snapshot()
    while snapshot.get(key) != expected and monotonic() < deadline:
        sleep(0.05)
        snapshot = service.snapshot()
    expect_equal(actual=snapshot.get(key), expected=expected)
    return snapshot


def test_recording_parent_captures_real_demo_clicks(
    service: StudioService,
    demo_url: str,
) -> None:
    """Capture actual demo clicks under one parent, including pause/resume.

    Args:
        service: Isolated Studio with a real managed browser.
        demo_url: Ordinary demo site, not a mocked recorder.

    """
    headers: dict[str, str] = authorized(service=service)
    edit(
        service=service,
        headers=headers,
        command="browser.open",
        payload={"url": demo_url},
    )
    await_state(service=service, key="target_state", expected="ready")
    edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
    )
    owner: str = service.controller.workspace.flows[0].flow_id
    parent: str = (
        service.controller.workspace.flows[0].recordings[0].recording_id
    )
    edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "click", "x": 400, "y": 340},
    )
    deadline: float = monotonic() + 15
    while not any(
        event.kind is EventKind.CLICK
        for event in service.controller.workspace.flows[0].events
    ):
        expect_true(condition=monotonic() < deadline)
        sleep(0.05)
    captured: TimelineEvent = next(
        event
        for event in service.controller.workspace.flows[0].events
        if event.kind is EventKind.CLICK
    )
    expect_equal(actual=captured.kind, expected=EventKind.CLICK)
    expect_equal(actual=captured.flow_id, expected=owner)
    expect_equal(actual=captured.recording_group_id, expected=parent)
    expect_true(condition=bool(captured.selector))
    edit(
        service=service,
        headers=headers,
        command="recorder.pause",
        payload={},
    )
    edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
    )
    edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "click", "x": 400, "y": 340},
    )
    resumed_click_count: int = 2
    while (
        sum(
            event.kind is EventKind.CLICK
            for event in service.controller.workspace.flows[0].events
        )
        < resumed_click_count
    ):
        expect_true(condition=monotonic() < deadline)
        sleep(0.05)
    expect_equal(
        actual=len(service.controller.workspace.flows[0].recordings),
        expected=1,
    )
    expect_equal(
        actual=service.controller.workspace.flows[0]
        .events[-1]
        .recording_group_id,
        expected=parent,
    )
    edit(service=service, headers=headers, command="recorder.stop", payload={})
    edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
    )
    expect_equal(
        actual=len(service.controller.workspace.flows[0].recordings),
        expected=2,
    )
    edit(service=service, headers=headers, command="recorder.stop", payload={})


def test_managed_browser_record_replay_and_close(
    service: StudioService,
    demo_url: str,
) -> None:
    """Open a real target, record navigation, replay its flow and close it.

    Args:
        service: Running isolated editor.
        demo_url: Real target application.

    """
    headers: dict[str, str] = authorized(service=service)
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
        status=400,
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.open",
        payload={"url": demo_url},
    )
    _ = await_state(service=service, key="target_state", expected="ready")
    _ = edit(
        service=service,
        headers=headers,
        command="browser.open",
        payload={"url": demo_url},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="viewport.preset",
        payload={
            "mode": "custom",
            "width": "390",
            "height": "844",
            "orientation": "landscape",
        },
    )
    _ = edit(
        service=service,
        headers=headers,
        command="viewport.preset",
        payload={"mode": "desktop", "orientation": "portrait"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="flow.update",
        payload={
            "name": "Recorded navigation",
            "capture_record_images": True,
            "capture_play_images": True,
        },
    )
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
    )
    deadline: float = monotonic() + 15
    while not service.controller.workspace.flows[0].events:
        expect_true(condition=monotonic() < deadline)
        sleep(0.05)
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.pause",
        payload={},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.navigate",
        payload={"url": demo_url + "#recorded"},
    )
    _ = await_state(
        service=service,
        key="target_url",
        expected=demo_url + "#recorded",
    )
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.stop",
        payload={},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="event.add",
        payload={"kind": "javascript", "payload": "() => ({answer: 42})"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="event.add",
        payload={"kind": "screenshot"},
    )
    _ = edit(service=service, headers=headers, command="run.play", payload={})
    _ = await_state(service=service, key="execution_run_id", expected=None)
    expect_true(condition=bool(service.controller.workspace.runs))
    expect_equal(
        actual=service.controller.workspace.runs[-1].status.value,
        expected="succeeded",
    )
    expect_true(condition=bool(service.controller.workspace.screenshots))
    artifact_id: str = service.controller.workspace.screenshots[-1].artifact_id
    _ = edit(
        service=service,
        headers=headers,
        command="screenshot.open",
        payload={"artifact_id": artifact_id},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.close",
        payload={},
    )
    _ = await_state(service=service, key="target_state", expected="closed")
    _ = edit(
        service=service,
        headers=headers,
        command="run.cancel",
        payload={},
    )


def test_a_run_pauses_steps_and_resumes_in_a_real_browser(
    service: StudioService,
    demo_url: str,
) -> None:
    """Step into a run from idle, step again, then let it finish.

    Args:
        service: Running isolated editor.
        demo_url: Real target application.

    """
    headers: dict[str, str] = authorized(service=service)
    _ = edit(
        service=service,
        headers=headers,
        command="browser.open",
        payload={"url": demo_url},
    )
    _ = await_state(service=service, key="target_state", expected="ready")
    for answer in ("1", "2"):
        _ = edit(
            service=service,
            headers=headers,
            command="event.add",
            payload={"kind": "javascript", "payload": f"() => {answer}"},
        )
    first, second = (
        event.event_id
        for event in service.controller.workspace.flows[0].events
    )
    _ = edit(service=service, headers=headers, command="run.step", payload={})
    _ = await_state(
        service=service,
        key="run_control",
        expected={"state": "paused", "before_event_id": first},
    )
    _ = edit(service=service, headers=headers, command="run.step", payload={})
    _ = await_state(
        service=service,
        key="run_control",
        expected={"state": "paused", "before_event_id": second},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="run.resume",
        payload={},
    )
    _ = await_state(service=service, key="execution_run_id", expected=None)
    expect_equal(
        actual=service.controller.workspace.runs[-1].status.value,
        expected="succeeded",
    )
    expect_equal(
        actual=service.snapshot()["run_control"],
        expected={"state": "running", "before_event_id": None},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="run.pause",
        payload={},
        status=400,
    )


def test_bundled_demo_runs_real_graph_and_retains_evidence(
    service: StudioService,
) -> None:
    """Open the bundled site, execute its graph and save real run evidence.

    Args:
        service: Running editor with an isolated project directory.

    """
    headers: dict[str, str] = authorized(service=service)
    _ = edit(service=service, headers=headers, command="demo.open", payload={})
    _ = await_state(service=service, key="target_state", expected="ready")
    workspace: Workspace = service.controller.workspace
    expect_equal(actual=len(workspace.flows), expected=3)
    expect_equal(actual=len(workspace.edges), expected=2)
    expect_true(condition=bool(workspace.flows[0].events[0].url))
    _ = edit(
        service=service,
        headers=headers,
        command="demo.open",
        payload={},
        status=400,
    )
    _ = edit(service=service, headers=headers, command="run.play", payload={})
    _ = await_state(service=service, key="execution_run_id", expected=None)
    result: ExecutionRun = service.controller.workspace.runs[-1]
    expect_equal(actual=result.status.value, expected="succeeded")
    expect_equal(actual=len(result.transitions), expected=2)
    expect_equal(actual=len(result.action_records), expected=8)
    expect_true(condition=bool(service.controller.workspace.screenshots))
    _ = edit(
        service=service,
        headers=headers,
        command="workspace.save",
        payload={"filename": "demo.pwflow.json"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="workspace.open",
        payload={"filename": "demo.pwflow.json"},
    )
    expect_equal(
        actual=service.controller.workspace.runs[-1].status.value,
        expected="succeeded",
    )
    expect_equal(actual=len(service.controller.workspace.edges), expected=2)
    preview: Reply = request(
        service=service,
        path="/api/target-preview",
        headers=headers,
    )
    preview_deadline: float = monotonic() + 30
    while (
        preview.status == HTTPStatus.NO_CONTENT
        and monotonic() < preview_deadline
    ):
        sleep(0.05)
        preview = request(
            service=service,
            path="/api/target-preview",
            headers=headers,
        )
    expect_equal(actual=preview.status, expected=200)
    expect_equal(actual=preview.headers["Content-Type"], expected="image/jpeg")
    expect_true(condition=preview.body.startswith(b"\xff\xd8"))
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.record",
        payload={},
    )
    before: int = len(service.controller.workspace.flows[0].events)
    _ = edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "key", "key": "Tab"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "key", "key": "Enter"},
    )
    deadline: float = monotonic() + 5
    while (
        not any(
            event.kind is EventKind.CLICK
            for event in service.controller.workspace.flows[0].events[before:]
        )
        and monotonic() < deadline
    ):
        sleep(0.05)
    expect_true(
        condition=any(
            event.kind is EventKind.CLICK
            for event in service.controller.workspace.flows[0].events[before:]
        ),
    )
    before = sum(
        event.kind is EventKind.CLICK
        for event in service.controller.workspace.flows[0].events
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "inspect", "x": 1, "y": 1, "picked": True},
    )
    deadline = monotonic() + 5
    while (
        service.snapshot().get("target_inspection") is None
        and monotonic() < deadline
    ):
        sleep(0.05)
    expect_true(
        condition=isinstance(
            service.snapshot().get("target_inspection"),
            dict,
        ),
    )
    expect_equal(
        actual=sum(
            event.kind is EventKind.CLICK
            for event in service.controller.workspace.flows[0].events
        ),
        expected=before,
    )
    _ = edit(
        service=service,
        headers=headers,
        command="recorder.stop",
        payload={},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="browser.input",
        payload={"action": "click", "x": -1, "y": 0},
        status=400,
    )


def await_operation(*, service: StudioService) -> dict[str, JsonValue]:
    """Wait for the owned discovery or Actions thread to finish.

    Args:
        service: Running isolated editor.

    Returns:
        Completed operation state.

    """
    deadline: float = monotonic() + 60
    state: JsonValue = service.snapshot()["crawl"]
    while isinstance(state, dict) and state.get("state") == "running":
        expect_true(
            condition=monotonic() < deadline,
            message=f"Studio operation did not finish: {state!r}",
        )
        sleep(0.05)
        state = service.snapshot()["crawl"]
    expect_true(condition=isinstance(state, dict))
    return cast(typ="dict[str, JsonValue]", val=state)


def test_studio_discovers_and_verifies_target(
    service: StudioService,
    tmp_path: Path,
) -> None:
    """Studio imports discovered flows and runs the saved project as Actions.

    Args:
        service: Running isolated editor.
        tmp_path: Project directory owned by the service.

    """
    headers: dict[str, str] = authorized(service=service)
    _ = edit(
        service=service,
        headers=headers,
        command="crawl.start",
        payload={"url": "about:blank"},
        status=400,
    )
    _ = edit(
        service=service,
        headers=headers,
        command="crawl.start",
        payload={
            "url": service.origin + "/health",
            "max_depth": "1",
            "max_states": "1",
            "follow_links": False,
            "click_controls": False,
        },
    )
    state: dict[str, JsonValue] = await_operation(service=service)
    expect_equal(actual=state["state"], expected="completed")
    expect_true(condition=bool(service.controller.workspace.flows[0].events))
    _ = edit(
        service=service,
        headers=headers,
        command="workspace.save",
        payload={"filename": "discovered.pwflow.json"},
    )
    _ = edit(
        service=service,
        headers=headers,
        command="actions.run",
        payload={
            "version": 1,
            "actions": [
                {
                    "id": "verify",
                    "tool": "frontend.run",
                    "arguments": {
                        "projects": [
                            {
                                "workspace": str(
                                    object=tmp_path / "discovered.pwflow.json",
                                ),
                                "width": 390,
                                "height": 844,
                                "theme": "light",
                            },
                        ],
                    },
                },
            ],
        },
    )
    state = await_operation(service=service)
    expect_equal(actual=state["state"], expected="succeeded")


def test_event_stream_delivers_initial_snapshot(
    service: StudioService,
) -> None:
    """The browser event stream starts with an authenticated live snapshot.

    Args:
        service: Running isolated editor.

    """
    headers: dict[str, str] = authorized(service=service)
    address: SplitResult = urlsplit(url=service.origin)
    connection: HTTPConnection = HTTPConnection(
        host="127.0.0.1",
        port=address.port,
        timeout=5,
    )
    try:
        connection.request(
            method="GET",
            url="/events?client=owner-tab",
            headers=headers,
        )
        response: HTTPResponse = connection.getresponse()
        expect_equal(actual=response.status, expected=200)
        expect_equal(
            actual=response.getheader(name="Content-Type"),
            expected="text/event-stream",
        )
        expect_true(condition=response.readline().startswith(b"id: "))
        data: bytes = response.readline()
        expect_in(member=b'"workspace.changed"', container=data)
        expect_in(member=b'"workspace"', container=data)
    finally:
        connection.close()
