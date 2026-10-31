# Copyright (c) 2026 Project contributors
"""Serve the local editor, authenticated commands, events and artifacts."""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from hmac import compare_digest
from http import HTTPStatus
from http.cookies import Morsel, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from json import JSONDecodeError, dumps, loads
from mimetypes import guess_type
from pathlib import Path, PurePosixPath
from queue import Full
from secrets import token_urlsafe
from threading import BoundedSemaphore, RLock, Thread
from typing import TYPE_CHECKING, Final, cast, final, override
from urllib.parse import parse_qs, unquote, urlsplit

from exactus.tools.record.store import WorkspaceError
from exactus.tools.record.studio.controller import StudioController
from exactus.tools.record.studio.events import EventBus
from exactus.tools.record.studio.persistence import WorkspaceFiles
from exactus.tools.record.studio.projects import Constants as ProjectConstants
from exactus.tools.record.studio.projects import ProjectLibrary
from exactus.tools.record.studio.target_service import TargetService
from exactus.tools.record.studio.worker import ManagedBrowserWorker

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from importlib.resources.abc import Traversable
    from io import BufferedReader
    from socket import socket
    from socketserver import BaseServer
    from urllib.parse import SplitResult

    from exactus.tools.common.json_types import JsonValue


def _sentence(*, parts: tuple[str, ...]) -> str:
    """Join message fragments with one stable space.

    Args:
        parts: Message fragments to join.

    Returns:
        Space-joined message text.

    """
    return " ".join(parts)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_body: Grouped module constant.
        max_id_length: Grouped module constant.
        max_replies: Grouped module constant.
        read_commands: Grouped module constant.
        busy_blocked: Grouped module constant.
        package_suffixes: Grouped module constant.
        recovery_page: Grouped module constant.

    """

    max_body: Final[int] = 8 * 1024 * 1024
    max_id_length: Final[int] = 128
    max_replies: Final[int] = 256
    read_commands: Final[frozenset[str]] = frozenset(
        {"workspace.snapshot", "screenshot.open"},
    )
    busy_blocked: Final[frozenset[str]] = frozenset(
        {
            "workspace.open",
            "demo.open",
            "flow.delete",
            "browser.navigate",
            "viewport.preset",
            "browser.select",
            "project.create",
            "project.open",
        },
    )
    package_suffixes: Final[frozenset[str]] = frozenset(
        {".js", ".css", ".html"},
    )
    recovery_page: Final[bytes] = b"".join(
        (
            b"<!doctype html><html lang=en><meta charset=utf-8>",
            b"<meta name=viewport content='width=device-width,"
            b"initial-scale=1'>",
            b"<title>Open Studio</title><style>body{font:16px system-ui;",
            b"max-width:32rem;margin:4rem auto;padding:0 1rem;color:#222}",
            b"a{color:#0b57d0}</style><h1>This tab is not authorized</h1>",
            b"<p>Studio only answers tabs it opened itself, so a pasted ",
            b"data link cannot read or change your project.</p>",
            b"<p><a href=/studio/>Open Studio</a> to start an authorized ",
            b"session. If that does not help, restart Studio from the ",
            b"terminal and use the address it prints.</p></html>",
        ),
    )


@dataclass(frozen=True, slots=True)
class StudioError(Exception):
    """Carry a stable public error without exposing internal exceptions.

    Attributes:
        code: Machine-readable failure category.
        message: User-facing recovery instructions.
        status: HTTP error status.

    """

    code: str
    message: str
    status: int = 400


class StudioService:
    """Own one controller, target worker and authenticated service lifetime.

    Attributes:
        events: Bounded event history.
        library: Project library backing workspace persistence.
        targets: Per-target automation registry.
        worker: Exclusively owned target automation.
        controller: Authoritative workspace and run state.
        token: Per-launch bootstrap credential, never written to logs.
        running: Whether the HTTP service is accepting event subscribers.

    """

    def __init__(
        self,
        *,
        root: Path,
        port: int = 0,
        headless: bool = False,
    ) -> None:
        """Bind an available loopback port without opening browsers.

        Args:
            root: Explicit project storage root.
            port: Desired port, or zero to choose an available port.
            headless: Use a headless managed target in unattended environments.

        """
        self.events: EventBus = EventBus()
        self.library: ProjectLibrary = ProjectLibrary(root=root)
        start: str = next(
            iter(self.library.recents()),
            ProjectConstants.root_id,
        )
        persistence: WorkspaceFiles = WorkspaceFiles(
            root=self.library.folder(slug=start),
        )
        self.worker: ManagedBrowserWorker = ManagedBrowserWorker(
            output=persistence.artifact_root,
            headless=headless,
        )
        self.targets: TargetService = TargetService(
            root=persistence.root,
            emit=self._receive,
        )
        self.controller: StudioController = StudioController(
            worker=self.worker,
            events=self.events,
            persistence=persistence,
            targets=self.targets,
            library=self.library,
        )
        self.token: str = token_urlsafe(nbytes=32)
        self.running: bool = False
        self._lock = RLock()
        self._replies: OrderedDict[
            tuple[str, str],
            tuple[str, dict[str, JsonValue]],
        ] = OrderedDict()
        self._subscribers = BoundedSemaphore(value=16)
        self.worker.emit = self._receive
        self._server = ThreadingHTTPServer(
            server_address=("127.0.0.1", port),
            RequestHandlerClass=partial(StudioHandler, service=self),
        )
        self._server.daemon_threads = True
        self._thread = Thread(
            target=self._server.serve_forever,
            name="studio-http",
            daemon=True,
        )

    @property
    def persistence(self) -> WorkspaceFiles:
        """Files of the project that is open now.

        Returns:
            The active project's persistence, which follows project switches.

        """
        return self.controller.persistence

    @property
    def origin(self) -> str:
        """Exact permitted service origin.

        Returns:
            Loopback scheme, host and assigned port.

        """
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def url(self) -> str:
        """Browser bootstrap URL with a non-logged fragment.

        Returns:
            Ordinary editor URL carrying the per-launch token in its fragment.

        """
        return f"{self.origin}/studio/#token={self.token}"

    def start(self) -> None:
        """Start the HTTP listener and its single target worker."""
        self.running = True
        self._thread.start()
        self.worker.start()

    def stop(self) -> None:
        """Stop the service without affecting unrelated browser processes."""
        self.running = False
        self.events.close()
        self.worker.stop()
        self.controller.stop_demo()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def snapshot(self) -> dict[str, JsonValue]:
        """Return authoritative state for any connected Studio window.

        Returns:
            Workspace and separate service/target/runtime states. Every window
            may edit; revision checks serialize concurrent mutations.

        """
        with self._lock:
            result: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=self.controller.dispatch(
                    command="workspace.snapshot",
                    payload=None,
                    revision=0,
                ),
            )
            result.update(
                instance_id=self.events.instance_id,
                event_sequence=self.events.sequence,
                controlling=True,
                control_owner=None,
            )
            return result

    def command(
        self,
        *,
        value: JsonValue,
        client: str,
    ) -> dict[str, JsonValue]:
        """Validate, deduplicate, authorize ownership and dispatch commands.

        Args:
            value: Versioned command envelope.
            client: Tab identifier supplied in the protected request header.

        Returns:
            Versioned correlated command reply.

        Raises:
            StudioError: When input, ownership or revision is invalid.

        """
        request_id, command, _ = self._command_envelope(value=value)
        if not client or len(client) > Constants.max_id_length:
            raise StudioError(
                code="INVALID_INPUT",
                message="A per-tab client identity is required.",
            )
        envelope: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=value,
        )
        key: tuple[str, str] = (client, request_id)
        fingerprint: str = sha256(
            data=dumps(obj=envelope, sort_keys=True).encode(),
        ).hexdigest()
        with self._lock:
            previous: tuple[str, dict[str, JsonValue]] | None = (
                self._replies.get(key)
            )
            if previous is not None:
                if previous[0] != fingerprint:
                    raise StudioError(
                        code="ID_REUSED",
                        message="Request ID was reused for different input.",
                        status=409,
                    )
                return previous[1]
            state: dict[str, JsonValue] = self.snapshot()
            result: JsonValue = self._command_result(
                command=command,
                value=envelope,
                state=state,
            )
            reply: dict[str, JsonValue] = {
                "protocol": 1,
                "id": request_id,
                "ok": True,
                "result": result,
            }
            self._replies[key] = (fingerprint, reply)
            while len(self._replies) > Constants.max_replies:
                _ = self._replies.popitem(last=False)
            return reply

    def export_document(self, *, slug: str = "") -> JsonValue:
        """Serialize a project as the public export document.

        Args:
            slug: A project of the library; the open project when blank.

        Returns:
            The portable workspace document.

        """
        with self._lock:
            if slug and slug != self.controller.project_slug:
                return self.library.export_document(slug=slug)
            return self.persistence.project_document(
                workspace=self.controller.workspace,
            )

    def artifact_path(self, *, artifact_id: str) -> Path:
        """Resolve one owned artifact under the service lock.

        Args:
            artifact_id: Artifact identifier carried by the route.

        Returns:
            The artifact file path.

        """
        with self._lock:
            return self.persistence.artifact(
                workspace=self.controller.workspace,
                artifact_id=artifact_id,
            )

    @contextmanager
    def subscriber(self) -> Generator[None]:
        """Hold one bounded event-stream subscription slot.

        Yields:
            The held subscription slot until the context exits.

        Raises:
            StudioError: When the subscription limit is reached.

        """
        if not self._subscribers.acquire(blocking=False):
            raise StudioError(
                code="TOO_MANY_CLIENTS",
                message="Close unused Studio tabs.",
                status=429,
            )
        try:
            yield
        finally:
            self._subscribers.release()

    @staticmethod
    def _command_envelope(*, value: JsonValue) -> tuple[str, str, int]:
        """Validate the versioned envelope and extract its fields.

        Args:
            value: Versioned command envelope.

        Returns:
            The request identifier, command name and revision.

        Raises:
            StudioError: When the envelope or its fields are invalid.

        """
        if not isinstance(value, dict) or value.get("protocol") != 1:
            raise StudioError(
                code="INVALID_INPUT",
                message="Unsupported command protocol.",
            )
        request_id, command, revision = (
            value.get("id"),
            value.get("command"),
            value.get("revision"),
        )
        if (
            not isinstance(request_id, str)
            or not request_id
            or len(request_id) > Constants.max_id_length
            or (not isinstance(command, str))
            or (not isinstance(revision, int))
            or isinstance(revision, bool)
        ):
            raise StudioError(
                code="INVALID_INPUT",
                message="Command needs an ID, name and integer revision.",
            )
        return (request_id, command, revision)

    def _receive(self, message: dict[str, JsonValue]) -> None:
        """Serialize worker events against all HTTP mutations.

        Args:
            message: Worker domain event or lifecycle message.

        """
        with self._lock:
            self.controller.receive(message=message)

    def _command_result(
        self,
        *,
        command: str,
        value: dict[str, JsonValue],
        state: dict[str, JsonValue],
    ) -> JsonValue:
        """Apply one validated command and return the new snapshot.

        Args:
            command: Command name being dispatched.
            value: Full command envelope carrying the payload.
            state: Snapshot taken before dispatch.

        Returns:
            The post-command snapshot.

        Raises:
            StudioError: When the command is rejected or fails.

        """
        busy: bool = (
            state.get("execution_run_id") is not None
            or state.get("recording_state") == "recording"
        )
        if command in {"control.claim", "control.release"}:
            return self.snapshot()
        if busy and command in Constants.busy_blocked:
            raise StudioError(
                code="BUSY",
                message=_sentence(
                    parts=(
                        "Pause recording or cancel the run before this",
                        "operation.",
                    ),
                ),
                status=409,
            )
        try:
            _ = self.controller.dispatch(
                command=command,
                payload=value.get("payload"),
                revision=cast(typ="int", val=state["revision"]),
            )
        except (ValueError, KeyError, TypeError) as error:
            raise StudioError(
                code="INVALID_INPUT",
                message=str(object=error),
            ) from error
        except Full as error:
            raise StudioError(
                code="WORKER_BUSY",
                message="Target command queue is full. Try again shortly.",
                status=409,
            ) from error
        except FileNotFoundError as error:
            raise StudioError(
                code="MISSING_ARTIFACT",
                message="Screenshot is unavailable. Run the test again.",
                status=404,
            ) from error
        return self.snapshot()


class StudioHandler(BaseHTTPRequestHandler):
    """Serve explicit routes with origin, Host, cookie and payload checks."""

    def __init__(
        self,
        request: socket,
        client_address: tuple[str, int],
        server: BaseServer,
        *,
        service: StudioService,
    ) -> None:
        """Attach the service before processing an HTTP request.

        Args:
            request: Accepted connection socket.
            client_address: Remote loopback address.
            server: Owning HTTP server.
            service: Owning Studio application state.

        """
        self._service = service
        super().__init__(
            request=request,
            client_address=client_address,
            server=server,
        )

    @override
    def log_message(self, format: str, *args: JsonValue) -> None:
        """Avoid access logs that could expose bootstrap credentials.

        Args:
            format: HTTP server log format.
            *args: HTTP server log fields.

        """
        _ = (format, args)

    def do_post(self) -> None:
        """Handle bootstrap authentication and protected JSON commands."""
        value: JsonValue = None
        try:
            route: str = urlsplit(url=self.path).path
            self._guard(mutation=True, authorized=route != "/api/session")
            value = self._json_body()
            self._post_route(route=route, value=value)
        except StudioError as error:
            self._failure(
                error=error,
                request_id=value.get("id")
                if isinstance(value, dict)
                else None,
            )
        except (JSONDecodeError, ValueError):
            self._failure(
                error=StudioError(
                    code="INVALID_INPUT",
                    message="Invalid JSON request.",
                ),
            )
        except OSError:
            self._failure(
                error=StudioError(
                    code="PERSISTENCE_FAILED",
                    message=_sentence(
                        parts=(
                            "Could not save project data.",
                            "Check the project folder and retry.",
                        ),
                    ),
                    status=500,
                ),
            )

    def do_get(self) -> None:
        """Serve assets, readiness, snapshots, events and owned artifacts."""
        try:
            parsed: SplitResult = urlsplit(url=self.path)
            route: str = unquote(string=parsed.path)
            if route.startswith("/packages/"):
                route = f"/studio{route}"
            public: bool = route in {"/health", "/studio"} or route.startswith(
                "/studio/",
            )
            self._guard(authorized=not public)
            if route == "/api/target-preview":
                frame: bytes = self._service.worker.preview
                age: int | None = self._service.worker.preview_age_ms
                self._send_frame(frame=frame, age=age)
                return
            self._get_route(route=route, parsed=parsed)
        except StudioError as error:
            self._failure(error=error)
        except (FileNotFoundError, WorkspaceError):
            self._failure(
                error=StudioError(
                    code="MISSING_ARTIFACT",
                    message="Artifact unavailable. Run the test again.",
                    status=404,
                ),
            )
        except ValueError:
            self._failure(
                error=StudioError(
                    code="INVALID_INPUT",
                    message="Use a nonnegative event sequence.",
                    status=400,
                ),
            )
        except (BrokenPipeError, ConnectionResetError):
            return

    def __getattr__(self, name: str) -> Callable[[], None]:
        """Bridge ``BaseHTTPRequestHandler``'s ``do_VERB`` dispatch names.

        Args:
            name: Attribute being resolved.

        Returns:
            The bound lowercase handler for ``do_GET`` or ``do_POST``.

        Raises:
            AttributeError: When the attribute does not exist.

        """
        if name.startswith("do_") and name.lower() != name:
            try:
                return getattr(self, name.lower())
            except AttributeError:
                pass
        raise AttributeError(name)

    def _guard(
        self,
        *,
        mutation: bool = False,
        authorized: bool = True,
    ) -> None:
        """Reject rebinding, cross-origin controls and unauthorized access.

        Args:
            mutation: Require an explicit same-origin mutation header.
            authorized: Require the service-lifetime authorization cookie.

        Raises:
            StudioError: When access is not authorized.

        """
        expected: str = urlsplit(url=self._service.origin).netloc
        origin: str | None = self.headers.get("Origin")
        if (
            self.headers.get("Host") != expected
            or (origin is not None and origin != self._service.origin)
            or (mutation and origin != self._service.origin)
        ):
            raise StudioError(
                code="BAD_ORIGIN",
                message="Use this service's local Studio URL.",
                status=403,
            )
        if authorized:
            cookie: SimpleCookie = SimpleCookie()
            cookie.load(rawdata=self.headers.get("Cookie", ""))
            token: Morsel[str] | None = cookie.get("studio")
            if token is None or not compare_digest(
                str(object=token.value).encode(),
                self._service.token.encode(),
            ):
                raise StudioError(
                    code="UNAUTHORIZED",
                    message=_sentence(
                        parts=(
                            "Open Studio from its launch URL to authorize",
                            "this tab.",
                        ),
                    ),
                    status=401,
                )

    def _send_frame(self, *, frame: bytes, age: int | None) -> None:
        """Send the newest preview frame with its age in milliseconds.

        Args:
            frame: JPEG bytes, or empty bytes when no frame exists.
            age: Milliseconds since the frame arrived, if one exists.

        """
        self.send_response(code=200 if frame else 204)
        self.send_header(keyword="Content-Type", value="image/jpeg")
        self.send_header(
            keyword="Content-Length",
            value=str(object=len(frame)),
        )
        self.send_header(keyword="Cache-Control", value="no-store")
        self.send_header(keyword="X-Content-Type-Options", value="nosniff")
        if age is not None:
            self.send_header(keyword="X-Frame-Age-Ms", value=str(object=age))
        self.end_headers()
        self.wfile.write(frame)

    def _send(
        self,
        *,
        status: int = 200,
        data: bytes,
        content_type: str = "application/json",
        cookie: str | None = None,
        download: str | None = None,
    ) -> None:
        """Send bounded bytes with explicit content type and cache policy.

        Args:
            status: HTTP status code.
            data: Response body.
            content_type: Media type.
            cookie: Optional bootstrap cookie.
            download: Optional safe download filename.

        """
        self.send_response(code=status)
        self.send_header(keyword="Content-Type", value=content_type)
        self.send_header(keyword="Content-Length", value=str(object=len(data)))
        self.send_header(keyword="Cache-Control", value="no-store")
        self.send_header(keyword="X-Content-Type-Options", value="nosniff")
        self.send_header(keyword="Referrer-Policy", value="no-referrer")
        if cookie:
            self.send_header(keyword="Set-Cookie", value=cookie)
        if download:
            self.send_header(
                keyword="Content-Disposition",
                value=f'attachment; filename="{download}"',
            )
        self.end_headers()
        self.wfile.write(data)

    def _failure(
        self,
        *,
        error: StudioError,
        request_id: JsonValue = None,
    ) -> None:
        """Return a stable correlated error envelope.

        Args:
            error: Public failure details.
            request_id: Request correlation identifier when decoded.

        """
        if error.code == "UNAUTHORIZED" and "text/html" in self.headers.get(
            "Accept",
            "",
        ):
            self._send(
                status=error.status,
                data=Constants.recovery_page,
                content_type="text/html; charset=utf-8",
            )
            return
        self._send(
            status=error.status,
            data=dumps(
                obj={
                    "protocol": 1,
                    "id": request_id,
                    "ok": False,
                    "error": error.message,
                    "code": error.code,
                },
            ).encode(),
        )

    def _json_body(self) -> JsonValue:
        """Read one bounded JSON request body.

        Returns:
            The decoded request payload.

        Raises:
            StudioError: When the body is not acceptable JSON.

        """
        if (
            self.headers.get("Content-Type", "").split(sep=";", maxsplit=1)[0]
            != "application/json"
        ):
            raise StudioError(
                code="INVALID_INPUT",
                message="Use an application/json command body.",
                status=415,
            )
        length: int = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > Constants.max_body:
            raise StudioError(
                code="PAYLOAD_TOO_LARGE",
                message="Command body must be between 1 byte and 8 MiB.",
                status=413,
            )
        stream: BufferedReader = cast(typ="BufferedReader", val=self.rfile)
        return cast(typ="JsonValue", val=loads(s=stream.read(length)))

    def _post_route(self, *, route: str, value: JsonValue) -> None:
        """Dispatch one authenticated POST route.

        Args:
            route: Request path.
            value: Decoded JSON request payload.

        Raises:
            StudioError: When the route or credentials are invalid.

        """
        if route == "/api/session":
            if not compare_digest(
                self.headers.get("Authorization", "").encode(),
                f"Bearer {self._service.token}".encode(),
            ):
                raise StudioError(
                    code="UNAUTHORIZED",
                    message="The launch credential is invalid.",
                    status=401,
                )
            self._send(data=b'{"ok":true}', cookie=self._studio_cookie())
        elif route == "/api/command":
            result: dict[str, JsonValue] = self._service.command(
                value=value,
                client=self.headers.get("X-Studio-Client", ""),
            )
            self._send(data=dumps(obj=result).encode())
        else:
            raise StudioError(
                code="NOT_FOUND",
                message="Unknown Studio route.",
                status=404,
            )

    def _get_route(self, *, route: str, parsed: SplitResult) -> None:
        """Dispatch one authenticated GET route.

        Args:
            route: Unquoted request path.
            parsed: Parsed request URL carrying the query.

        Raises:
            FileNotFoundError: When the artifact is unavailable.
            StudioError: When the route or asset is unknown.

        """
        if route == "/studio":
            query: str = f"?{parsed.query}" if parsed.query else ""
            self.send_response(code=HTTPStatus.PERMANENT_REDIRECT)
            self.send_header(keyword="Location", value=f"/studio/{query}")
            self.send_header(keyword="Content-Length", value="0")
            self.send_header(keyword="Cache-Control", value="no-store")
            self.send_header(keyword="X-Content-Type-Options", value="nosniff")
            self.send_header(keyword="Referrer-Policy", value="no-referrer")
            self.end_headers()
        elif route == "/health":
            self._send(
                data=dumps(
                    obj={
                        "ready": self._service.running,
                        "instance_id": self._service.events.instance_id,
                    },
                ).encode(),
            )
        elif route.startswith("/studio/"):
            studio_asset: str = route.removeprefix("/studio/") or "index.html"
            self._serve_asset(
                relative=studio_asset,
                cookie=self._studio_cookie()
                if studio_asset == "index.html"
                else None,
            )
        elif route == "/api/snapshot":
            self._send(data=dumps(obj=self._service.snapshot()).encode())
        elif route == "/events":
            self._events(query=parsed.query)
        elif route == "/api/export":
            slug: str = parse_qs(qs=parsed.query).get("project", [""])[0]
            self._send(
                data=dumps(
                    obj=self._service.export_document(slug=slug),
                    ensure_ascii=False,
                    indent=2,
                ).encode(),
                download=f"{slug.lstrip('@') or 'flows'}.pwflow.json",
            )
        elif route.startswith("/reports/actions/"):
            relative: Path = Path(route.removeprefix("/reports/actions/"))
            base: Path = self._service.persistence.artifact_root / "actions"
            path: Path = (base / relative).resolve()
            if not path.is_relative_to(base.resolve()) or path.suffix not in {
                ".html",
                ".css",
                ".js",
                ".json",
                ".png",
            }:
                raise FileNotFoundError(path)
            self._send(
                data=path.read_bytes(),
                content_type=guess_type(url=path.name)[0]
                or "application/octet-stream",
            )
        elif route.startswith("/artifacts/"):
            self._serve_artifact(route=route, parsed=parsed)
        else:
            raise StudioError(
                code="NOT_FOUND",
                message="Unknown Studio route.",
                status=404,
            )

    def _studio_cookie(self) -> str:
        """Return the loopback Studio session cookie for this service.

        Returns:
            Loopback Studio session cookie for this service.

        """
        return (
            f"studio={self._service.token}; HttpOnly; SameSite=Strict; Path=/"
        )

    def _serve_asset(
        self,
        *,
        relative: str,
        cookie: str | None = None,
    ) -> None:
        """Serve one packaged editor asset under ``web/``.

        Args:
            relative: Path fragment relative to the asset root.
            cookie: Optional local Studio session established by the editor.

        Raises:
            StudioError: When the path escapes or is unknown.

        """
        if (
            any(part in {"", ".", ".."} for part in relative.split(sep="/"))
            or "\\" in relative
            or relative.startswith("/")
        ):
            raise StudioError(
                code="NOT_FOUND",
                message="Unknown editor asset.",
                status=404,
            )
        resource: Traversable
        packaged: str = relative.removeprefix("exactus/")
        if packaged.startswith("packages/"):
            if (
                PurePosixPath(packaged).suffix
                not in Constants.package_suffixes
            ):
                raise StudioError(
                    code="NOT_FOUND",
                    message="Unknown editor asset.",
                    status=404,
                )
            resource = files(anchor="exactus.packages").joinpath(
                packaged.removeprefix("packages/"),
            )
        else:
            resource = files(anchor="exactus.tools.record.studio").joinpath(
                "web",
                relative,
            )
        if not resource.is_file():
            raise StudioError(
                code="NOT_FOUND",
                message="Unknown editor asset.",
                status=404,
            )
        self._send(
            data=resource.read_bytes(),
            content_type=guess_type(url=relative)[0]
            or "application/octet-stream",
            cookie=cookie,
        )

    def _serve_artifact(self, *, route: str, parsed: SplitResult) -> None:
        """Serve one owned PNG artifact, optionally as a download.

        Args:
            route: Artifact request path carrying the identifier.
            parsed: Parsed request URL carrying the download flag.

        """
        path: Path = self._service.artifact_path(
            artifact_id=route.removeprefix("/artifacts/"),
        )
        self._send(
            data=path.read_bytes(),
            content_type="image/png",
            download=f"{path.stem}.png"
            if parsed.query == "download=1"
            else None,
        )

    def _events(self, *, query: str) -> None:
        """Stream bounded history with explicit snapshot resynchronization.

        Args:
            query: Event sequence and per-tab identity query.

        Raises:
            ValueError: When the arguments are invalid.

        """
        try:
            with self._service.subscriber():
                fields: dict[str, list[str]] = parse_qs(qs=query)
                after: int = int(
                    self.headers.get("Last-Event-ID")
                    or fields.get("after", ["0"])[0],
                )
                if after < 0:
                    msg: str = "Event sequence must be nonnegative."
                    raise ValueError(msg)
                self.send_response(code=HTTPStatus.OK)
                self.send_header(
                    keyword="Content-Type",
                    value="text/event-stream",
                )
                self.send_header(keyword="Cache-Control", value="no-store")
                self.end_headers()
                snapshot: dict[str, JsonValue] = self._service.snapshot()
                after = int(str(object=snapshot["event_sequence"]))
                event: dict[str, JsonValue] = {
                    "event": "workspace.changed",
                    "payload": snapshot,
                    "instance_id": self._service.events.instance_id,
                }
                self.wfile.write(
                    f"id: {after}\ndata: {dumps(obj=event)}\n\n".encode(),
                )
                self.wfile.flush()
                while self._service.running:
                    lost, rows = self._service.events.read(after=after)
                    if lost:
                        snapshot = self._service.snapshot()
                        after = int(str(object=snapshot["event_sequence"]))
                        event = {
                            "event": "workspace.changed",
                            "payload": snapshot,
                            "instance_id": self._service.events.instance_id,
                        }
                        data: str = dumps(obj=event)
                        self.wfile.write(
                            f"id: {after}\ndata: {data}\n\n".encode(),
                        )
                    else:
                        for after, value in rows:
                            self.wfile.write(
                                f"id: {after}\ndata: {value}\n\n".encode(),
                            )
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
