#!/usr/bin/env python3
# Copyright (c) 2026
"""Collect browser-visible diagnostics during click exploration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, Literal, Protocol, Self, cast, final

from playwright.sync_api import Error as BrowserError

if TYPE_CHECKING:
    from re import Match, Pattern

    from playwright import async_api, sync_api

    type ConsoleMessage = async_api.ConsoleMessage | sync_api.ConsoleMessage
    type Error = async_api.Error | sync_api.Error
    type Page = async_api.Page | sync_api.Page
    type Request = async_api.Request | sync_api.Request
    type Response = async_api.Response | sync_api.Response
    type WebSocket = async_api.WebSocket | sync_api.WebSocket
    from exactus.tools.record.json_types import JsonValue
type DiagnosticCategory = Literal[
    "console",
    "pageerror",
    "requestfailed",
    "http",
    "websocket",
]
type DiagnosticPhase = Literal["initial", "replay", "action"]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        self_inflicted: Grouped module constant.
        http_error_min: Grouped module constant.
        http_server_error_min: Grouped module constant.
        stack_frame: Grouped module constant.

    """

    self_inflicted: Final[tuple[str, ...]] = (
        "ERR_BLOCKED_BY_CLIENT",
        "ERR_ABORTED",
    )
    http_error_min: Final[int] = 400
    http_server_error_min: Final[int] = 500
    stack_frame: Final[Pattern[str]] = re_compile(
        pattern=(
            "^\\s*at\\s+(?:(?P<function>.*?)\\s+\\()?(?P<file>.+?):(?P<line>\\"
            "d+):(?P<column>\\d+)\\)?\\s*$"
        ),
    )


class _CDPSender(Protocol):
    """Typed subset of the Chromium command interface."""

    def send(self: Self, *, method: str) -> dict[str, JsonValue]:
        """Send a parameterless protocol command.

        Args:
            method: Chromium command name.

        Returns:
            Chromium command result.

        """
        ...


class _AsyncCDPSender(Protocol):
    """Typed subset of the async Chromium command interface."""

    async def send(self: Self, *, method: str) -> dict[str, JsonValue]:
        """Send a parameterless async protocol command.

        Args:
            method: Chromium command name.

        Returns:
            Chromium command result.

        """
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class DiagnosticEvent:
    """Describe one browser-observable diagnostic event.

    Attributes:
        category: Diagnostic channel that produced the event.
        severity: Severity label assigned to the event.
        phase: Exploration phase in which the event was observed.
        variant: Capture variant that observed the event.
        action: Interaction label attributed to the event.
        message: Human-readable event payload.
        url: Resource URL associated with the event.
        method: HTTP method for network events.
        status: HTTP status code for network events.
        timestamp: ISO-8601 observation timestamp.
        file: Script URL or source file.
        line: One-based source line.
        column: One-based source column.
        function: Function that emitted the diagnostic.
        stack: Complete available JavaScript stack.

    """

    category: DiagnosticCategory
    severity: str
    phase: DiagnosticPhase
    variant: str
    action: str
    message: str
    url: str
    method: str = ""
    status: int | None = None
    timestamp: str = ""
    file: str = ""
    line: int | None = None
    column: int | None = None
    function: str = ""
    stack: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class EventDraft:
    """Carry the caller-supplied fields of one diagnostic event.

    Attributes:
        category: Diagnostic channel that produced the event.
        severity: Severity label assigned to the event.
        message: Human-readable event payload.
        url: Resource URL associated with the event.
        method: HTTP method for network events.
        status: HTTP status code for network events.
        file: Script URL or source file.
        line: One-based source line.
        column: One-based source column.
        function: Function that emitted the diagnostic.
        stack: Complete available JavaScript stack.

    """

    category: DiagnosticCategory
    severity: str
    message: str
    url: str
    method: str = ""
    status: int | None = None
    file: str = ""
    line: int | None = None
    column: int | None = None
    function: str = ""
    stack: str = ""


class DiagnosticCollector:
    """Collect and deduplicate Playwright page diagnostics."""

    def __init__(self: Self, *, variant: str) -> None:
        """Initialize the collector for one device/theme lane.

        Args:
            variant: Capture variant name stamped on collected events.

        """
        self._variant: str = variant
        self._phase: DiagnosticPhase = "initial"
        self._action: str = ""
        self._events: list[DiagnosticEvent] = []
        self._keys: set[tuple[str, ...]] = set()
        self._console_stacks: bool = False
        self._sessions: list[sync_api.CDPSession | async_api.CDPSession] = []

    @property
    def events(self: Self) -> tuple[DiagnosticEvent, ...]:
        """Collected events in observation order.

        Returns:
            Collected diagnostic events.

        """
        return tuple(self._events)

    @staticmethod
    def stack_origin(*, stack: str) -> dict[str, str]:
        """Read the first source location from a JavaScript stack.

        Args:
            stack: Browser-provided JavaScript stack.

        Returns:
            Available file, line, column and function fields.

        """
        for line in stack.splitlines():
            match: Match[str] | None = Constants.stack_frame.match(string=line)
            if match is not None:
                return {
                    key: value
                    for key, value in match.groupdict().items()
                    if value is not None
                }
        return {}

    @staticmethod
    def serialize(event: DiagnosticEvent) -> dict[str, JsonValue]:
        """Serialize one diagnostic event for report artifacts.

        Args:
            event: Diagnostic event to serialize.

        Returns:
            JSON-compatible mapping of the event fields.

        """
        return cast(typ="dict[str, JsonValue]", val=asdict(obj=event))

    def mark(self: Self) -> int:
        """Return a cursor suitable for retrieving newly observed events.

        Returns:
            Index cursor into the collected event list.

        """
        return len(self._events)

    def since(self: Self, *, mark: int) -> tuple[DiagnosticEvent, ...]:
        """Return events observed after a previous cursor.

        Args:
            mark: Cursor previously returned by ``mark``.

        Returns:
            Events observed after the cursor.

        """
        return tuple(self._events[mark:])

    def phase(self: Self, *, phase: DiagnosticPhase, action: str = "") -> None:
        """Set attribution for subsequently observed diagnostics.

        Args:
            phase: Exploration phase to attribute.
            action: Interaction label to attribute.

        """
        self._phase = phase
        self._action = action

    def attach(self: Self, *, page: Page) -> None:
        """Attach diagnostic listeners to a Playwright page.

        Args:
            page: Page whose events should be collected.

        """
        page.on(event="console", f=self._console)
        page.on(event="pageerror", f=self._page_error)
        page.on(event="requestfailed", f=self._request_failed)
        page.on(event="response", f=self._response)
        page.on(event="websocket", f=self._websocket)

    def attach_sync(self: Self, *, page: sync_api.Page) -> None:
        """Attach listeners and Chromium console stack capture.

        Args:
            page: Synchronous Playwright page.

        """
        self.attach(page=page)
        try:
            session: sync_api.CDPSession = page.context.new_cdp_session(
                page=page,
            )
            session.on(
                event="Runtime.consoleAPICalled",
                f=self._runtime_console,
            )
            session.on(
                event="Runtime.exceptionThrown",
                f=self._runtime_exception,
            )
            cast(typ="_CDPSender", val=session).send(method="Runtime.enable")
            self._sessions.append(session)
            self._console_stacks = True
        except BrowserError:
            self._console_stacks = False

    async def attach_async(self: Self, *, page: async_api.Page) -> None:
        """Attach async page listeners and Chromium console stacks.

        Args:
            page: Asynchronous Playwright page.

        """
        self.attach(page=page)
        try:
            session: async_api.CDPSession = await page.context.new_cdp_session(
                page=page,
            )
            session.on(
                event="Runtime.consoleAPICalled",
                f=self._runtime_console,
            )
            session.on(
                event="Runtime.exceptionThrown",
                f=self._runtime_exception,
            )
            await cast(typ="_AsyncCDPSender", val=session).send(
                method="Runtime.enable",
            )
            self._sessions.append(session)
            self._console_stacks = True
        except BrowserError:
            self._console_stacks = False

    @staticmethod
    def _stack_frame(*, frame: dict[str, JsonValue]) -> str:
        """Render one Chromium call frame.

        Args:
            frame: Frame.

        Returns:
            The resulting value.

        """
        function: JsonValue = frame.get("functionName") or "<anonymous>"
        url: JsonValue = frame.get("url", "")
        line: int = int(str(object=frame.get("lineNumber", 0))) + 1
        column: int = int(str(object=frame.get("columnNumber", 0))) + 1
        return f"    at {function} ({url}:{line}:{column})"

    def _add(self: Self, *, draft: EventDraft) -> None:
        """Append one unique diagnostic event.

        Args:
            draft: Caller-supplied event fields.

        """
        key: tuple[str, ...] = (
            draft.category,
            draft.severity,
            self._phase,
            self._action,
            draft.message,
            draft.url,
            draft.method,
            "" if draft.status is None else str(object=draft.status),
            draft.file,
            str(object=draft.line),
            str(object=draft.column),
            draft.function,
        )
        if key in self._keys:
            return
        self._keys.add(key)
        if draft.category == "console" and draft.stack:
            self._events = [
                event
                for event in self._events
                if not (
                    event.category == "console"
                    and (not event.stack)
                    and (event.message == draft.message)
                    and (event.url == draft.url)
                    and (event.phase == self._phase)
                    and (event.action == self._action)
                )
            ]
        self._events.append(
            DiagnosticEvent(
                category=draft.category,
                severity=draft.severity,
                phase=self._phase,
                variant=self._variant,
                action=self._action,
                message=draft.message,
                url=draft.url,
                method=draft.method,
                status=draft.status,
                timestamp=datetime.now(tz=UTC).astimezone().isoformat(),
                file=draft.file,
                line=draft.line,
                column=draft.column,
                function=draft.function,
                stack=draft.stack,
            ),
        )

    def _runtime_console(self: Self, event: dict[str, JsonValue]) -> None:
        """Record a console event with its browser-provided call frames.

        Args:
            event: Chromium Runtime.consoleAPICalled payload.

        """
        arguments: JsonValue = event.get("args")
        arguments = arguments if isinstance(arguments, list) else []
        message: str = " ".join(
            str(object=value.get("value", value.get("description", "")))
            for value in arguments
            if isinstance(value, dict)
        )
        if message.startswith("--playwright--set--content--"):
            return
        trace: JsonValue = event.get("stackTrace")
        frames: JsonValue = (
            trace.get("callFrames") if isinstance(trace, dict) else []
        )
        frames = frames if isinstance(frames, list) else []
        locations: list[dict[str, JsonValue]] = [
            value for value in frames if isinstance(value, dict)
        ]
        first: dict[str, JsonValue] = locations[0] if locations else {}
        source_line: JsonValue = first.get("lineNumber")
        source_column: JsonValue = first.get("columnNumber")
        stack: str = "\n".join(
            self._stack_frame(frame=frame) for frame in locations
        )
        self._add(
            draft=EventDraft(
                category="console",
                severity=(
                    "info"
                    if any(
                        marker in message
                        for marker in Constants.self_inflicted
                    )
                    else str(object=event.get("type", "log"))
                ),
                message=message,
                url=str(object=first.get("url", "")),
                file=str(object=first.get("url", "")),
                line=source_line + 1 if isinstance(source_line, int) else None,
                column=(
                    source_column + 1
                    if isinstance(source_column, int)
                    else None
                ),
                function=str(object=first.get("functionName", "")),
                stack=stack,
            ),
        )

    def _console(self: Self, message: ConsoleMessage) -> None:
        """Record one browser console message.

        Messages about requests the exactus blocked or cancelled are
        recorded as ``info``.

        Args:
            message: Playwright console message.

        """
        if any(
            event.category == "console"
            and event.stack
            and (event.message == message.text)
            and (event.url == message.location.get("url", ""))
            and (event.phase == self._phase)
            and (event.action == self._action)
            for event in self._events
        ):
            return
        location: dict[str, str | int] = cast(
            typ="dict[str, str | int]",
            val=dict(message.location),
        )
        self._add(
            draft=EventDraft(
                category="console",
                severity=(
                    "info"
                    if any(
                        marker in message.text
                        for marker in Constants.self_inflicted
                    )
                    else message.type
                ),
                message=message.text,
                url=message.location.get("url", ""),
                file=str(object=location.get("url", "")),
                line=int(location.get("lineNumber", 0)) + 1,
                column=int(location.get("columnNumber", 0)) + 1,
            ),
        )

    def _page_error(self: Self, error: Error) -> None:
        """Record one uncaught JavaScript exception.

        Args:
            error: Playwright page error.

        """
        if self._console_stacks:
            return
        stack: str = error.stack or str(object=error)
        origin: dict[str, str] = self.stack_origin(stack=stack)
        self._add(
            draft=EventDraft(
                category="pageerror",
                severity="error",
                message=str(object=error),
                url="",
                file=origin.get("file", ""),
                line=int(origin["line"]) if origin.get("line") else None,
                column=int(origin["column"]) if origin.get("column") else None,
                function=origin.get("function", ""),
                stack=stack,
            ),
        )

    def _runtime_exception(self: Self, event: dict[str, JsonValue]) -> None:
        """Record Chromium exceptions with normalized source coordinates.

        Args:
            event: Chromium Runtime.exceptionThrown payload.

        """
        details: JsonValue = event.get("exceptionDetails")
        if not isinstance(details, dict):
            return
        exception: JsonValue = details.get("exception")
        description: str = (
            str(
                object=exception.get(
                    "description",
                    exception.get("value", ""),
                ),
            )
            if isinstance(exception, dict)
            else str(object=details.get("text", ""))
        )
        trace: JsonValue = details.get("stackTrace")
        frames: JsonValue = (
            trace.get("callFrames") if isinstance(trace, dict) else []
        )
        frames = frames if isinstance(frames, list) else []
        locations: list[dict[str, JsonValue]] = [
            value for value in frames if isinstance(value, dict)
        ]
        first: dict[str, JsonValue] = locations[0] if locations else details
        source_line: JsonValue = first.get("lineNumber")
        source_column: JsonValue = first.get("columnNumber")
        message: str = (
            description.splitlines()[0]
            if description
            else "JavaScript exception"
        )
        stack: str = (
            message
            + "\n"
            + "\n".join(self._stack_frame(frame=frame) for frame in locations)
        )
        self._add(
            draft=EventDraft(
                category="pageerror",
                severity="error",
                message=message,
                url=str(object=first.get("url", "")),
                file=str(object=first.get("url", "")),
                line=source_line + 1 if isinstance(source_line, int) else None,
                column=(
                    source_column + 1
                    if isinstance(source_column, int)
                    else None
                ),
                function=str(object=first.get("functionName", "")),
                stack=stack,
            ),
        )

    def _request_failed(self: Self, request: Request) -> None:
        """Record one failed network request.

        Blocked or navigation-cancelled requests are recorded as ``info``.

        Args:
            request: Playwright failed request.

        """
        failure: str | None = request.failure
        self._add(
            draft=EventDraft(
                category="requestfailed",
                severity=(
                    "info"
                    if any(
                        marker in (failure or "")
                        for marker in Constants.self_inflicted
                    )
                    else "error"
                ),
                message=failure or "request failed",
                url=request.url,
                method=request.method,
            ),
        )

    def _response(self: Self, response: Response) -> None:
        """Record HTTP 4xx and 5xx responses.

        Args:
            response: Playwright response to inspect.

        """
        if response.status < Constants.http_error_min:
            return
        request: Request = response.request
        self._add(
            draft=EventDraft(
                category="http",
                severity=(
                    "error"
                    if response.status >= Constants.http_server_error_min
                    else "warning"
                ),
                message=f"HTTP {response.status} {response.status_text}",
                url=response.url,
                method=request.method,
                status=response.status,
            ),
        )

    def _websocket(self: Self, socket: WebSocket) -> None:
        """Attach error listeners to one WebSocket.

        Args:
            socket: Playwright WebSocket to observe.

        """
        socket.on(
            event="socketerror",
            f=lambda error: self._add(
                draft=EventDraft(
                    category="websocket",
                    severity="error",
                    message=str(object=error),
                    url=socket.url,
                ),
            ),
        )
        socket.on(
            event="framereceived",
            f=lambda payload: self._websocket_frame(
                socket=socket,
                payload=str(object=payload),
            ),
        )

    def _websocket_frame(
        self: Self,
        *,
        socket: WebSocket,
        payload: str,
    ) -> None:
        """Record received WebSocket frames that visibly describe errors.

        Args:
            socket: WebSocket that received the frame.
            payload: Received frame payload.

        """
        lowered: str = payload.lower()
        if "error" not in lowered and "exception" not in lowered:
            return
        self._add(
            draft=EventDraft(
                category="websocket",
                severity="error",
                message=payload,
                url=socket.url,
            ),
        )
