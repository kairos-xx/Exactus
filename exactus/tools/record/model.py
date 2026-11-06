# Copyright (c) 2026 Project contributors
"""Immutable models for viewports, flows, actions, and runtime artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from re import fullmatch
from typing import Final, Self, final
from urllib.parse import SplitResult, urlsplit, urlunsplit

from exactus.tools.record.project_info import ProjectInfo
from exactus.tools.record.selectors import (
    Pace,
    RunMode,
    SelectorDef,
    TargetScope,
)


class RecorderCommandName(StrEnum):
    """Represent RecorderCommandName.

    Attributes:
        RECORD: Record.
        PAUSE: Pause.
        WAIT: Wait.
        VIEWPORT: Viewport.
        ACTIVE_FLOW: Active flow.

    """

    RECORD = "record"
    PAUSE = "pause"
    WAIT = "wait"
    VIEWPORT = "viewport"
    ACTIVE_FLOW = "active_flow"


class TimelineLayer(StrEnum):
    """Represent TimelineLayer.

    Attributes:
        INTERACTION: Interaction.
        NAVIGATION: Navigation.
        NETWORK: Network.
        WEBSOCKET: Websocket.
        CONSOLE: Console.
        TIMING: Timing.

    """

    INTERACTION = "interaction"
    NAVIGATION = "navigation"
    NETWORK = "network"
    WEBSOCKET = "websocket"
    CONSOLE = "console"
    TIMING = "timing"


class DeviceMode(StrEnum):
    """Represent DeviceMode.

    Attributes:
        SHARED: Shared.
        MOBILE: Mobile.
        TABLET: Tablet.
        DESKTOP: Desktop.
        CUSTOM: Custom.

    """

    SHARED = "shared"
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"
    CUSTOM = "custom"


class CapturePhase(StrEnum):
    """Represent CapturePhase.

    Attributes:
        RECORD: Record.
        PLAY: Play.

    """

    RECORD = "record"
    PLAY = "play"


class UrlMatchMode(StrEnum):
    """Represent UrlMatchMode.

    Attributes:
        EXACT: Exact.
        CONTAINS: Contains.
        GLOB: Glob.
        REGEX: Regex.

    """

    EXACT = "exact"
    CONTAINS = "contains"
    GLOB = "glob"
    REGEX = "regex"


class BodyMatchMode(StrEnum):
    """Represent BodyMatchMode.

    Attributes:
        NONE: None.
        EXACT_TEXT: Exact text.
        JSON_EXACT: Json exact.
        JSON_CONTAINS: Json contains.

    """

    NONE = "none"
    EXACT_TEXT = "exact_text"
    JSON_EXACT = "json_exact"
    JSON_CONTAINS = "json_contains"


class ConditionOperator(StrEnum):
    """Represent ConditionOperator.

    Attributes:
        EXISTS: Exists.
        EQUALS: Equals.
        NOT_EQUALS: Not equals.
        CONTAINS: Contains.
        REGEX: Regex.

    """

    EXISTS = "exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    REGEX = "regex"


class PositionPointerAction(StrEnum):
    """Represent PositionPointerAction.

    Attributes:
        CLICK: Click.
        DOUBLE_CLICK: Double click.
        RIGHT_CLICK: Right click.
        HOVER: Hover.
        DRAG: Drag.
        SCROLL: Scroll.
        GESTURE: Gesture.

    """

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG = "drag"
    SCROLL = "scroll"
    GESTURE = "gesture"


class ExpectationOutcome(StrEnum):
    """Represent ExpectationOutcome.

    Attributes:
        SUCCEEDED: Succeeded.
        FAILED: Failed.
        TIMED_OUT: Timed out.

    """

    SUCCEEDED = "pass"
    FAILED = "fail"
    TIMED_OUT = "timeout"


class ValueType(StrEnum):
    """Represent ValueType.

    Attributes:
        STRING: String.
        INTEGER: Integer.
        FLOAT: Float.
        BOOLEAN: Boolean.
        JSON: Json.
        URL: URL.
        SELECTOR: Selector.
        DURATION: Duration.
        ARTIFACT: Artifact.
        LIST: List.
        VOID: Void.

    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    URL = "url"
    SELECTOR = "selector"
    DURATION = "duration"
    ARTIFACT = "artifact"
    LIST = "list"
    VOID = "void"


class VariableScope(StrEnum):
    """Represent VariableScope.

    Attributes:
        FLOW: Flow.
        RUN: Run.
        WORKSPACE: Workspace.
        ENVIRONMENT: Environment.
        CREDENTIAL: Credential.

    """

    FLOW = "flow"
    RUN = "run"
    WORKSPACE = "workspace"
    ENVIRONMENT = "environment"
    CREDENTIAL = "secret"


class AssertionKind(StrEnum):
    """Represent AssertionKind.

    Attributes:
        DOM_VISIBLE: Dom visible.
        DOM_HIDDEN: Dom hidden.
        DOM_TEXT: Dom text.
        DOM_ATTRIBUTE: Dom attribute.
        DOM_COUNT: Dom count.
        URL: Url.
        TITLE: Title.
        COOKIE: Cookie.
        LOCAL_STORAGE: Local storage.
        SESSION_STORAGE: Session storage.
        CONSOLE: Console.
        JAVASCRIPT: Javascript.

    """

    DOM_VISIBLE = "dom_visible"
    DOM_HIDDEN = "dom_hidden"
    DOM_TEXT = "dom_text"
    DOM_ATTRIBUTE = "dom_attribute"
    DOM_COUNT = "dom_count"
    URL = "url"
    TITLE = "title"
    COOKIE = "cookie"
    LOCAL_STORAGE = "local_storage"
    SESSION_STORAGE = "session_storage"
    CONSOLE = "console"
    JAVASCRIPT = "javascript"


class AssertionOperator(StrEnum):
    """Represent AssertionOperator.

    Attributes:
        EXISTS: Exists.
        NOT_EXISTS: Not exists.
        EQUALS: Equals.
        NOT_EQUALS: Not equals.
        CONTAINS: Contains.
        REGEX: Regex.
        GREATER_THAN: Greater than.
        GREATER_THAN_OR_EQUAL: Greater than or equal.
        LESS_THAN: Less than.
        LESS_THAN_OR_EQUAL: Less than or equal.

    """

    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    REGEX = "regex"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"


class OutputSource(StrEnum):
    """Represent OutputSource.

    Attributes:
        RESPONSE_JSON_PATH: Response json path.
        DOM_TEXT: Dom text.
        DOM_ATTRIBUTE: Dom attribute.
        URL: Url.
        TITLE: Title.
        JAVASCRIPT: Javascript.
        VARIABLE: Variable.

    """

    RESPONSE_JSON_PATH = "response_json_path"
    DOM_TEXT = "dom_text"
    DOM_ATTRIBUTE = "dom_attribute"
    URL = "url"
    TITLE = "title"
    JAVASCRIPT = "javascript"
    VARIABLE = "variable"


class TransitionMode(StrEnum):
    """Represent TransitionMode.

    Attributes:
        ALWAYS: Always.
        CONDITION: Condition.
        FALLBACK: Fallback.
        RETRY: Retry.
        FINALLY: Finally.

    """

    ALWAYS = "always"
    CONDITION = "condition"
    FALLBACK = "fallback"
    RETRY = "retry"
    FINALLY = "finally"


class RunStatus(StrEnum):
    """Represent RunStatus.

    Attributes:
        RUNNING: Running.
        SUCCEEDED: Succeeded.
        FAILED: Failed.
        CANCELLED: Cancelled.

    """

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionRunStatus(StrEnum):
    """Represent ActionRunStatus.

    Attributes:
        SUCCEEDED: Succeeded.
        FAILED: Failed.
        SKIPPED: Skipped.
        WARNING: Failed, but the action allows the flow to continue.

    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


class AssertionOutcome(StrEnum):
    """Represent AssertionOutcome.

    Attributes:
        SUCCEEDED: Succeeded.
        FAILED: Failed.
        TIMED_OUT: Timed out.

    """

    SUCCEEDED = "pass"
    FAILED = "fail"
    TIMED_OUT = "timeout"


class EventKind(StrEnum):
    """Represent EventKind.

    Attributes:
        CLICK: Click.
        DOUBLE_CLICK: Double click.
        RIGHT_CLICK: Right click.
        HOVER: Hover.
        DRAG: Drag.
        SCROLL: Scroll.
        GESTURE: Gesture.
        POSITION_POINTER: Position pointer.
        INPUT_TEXT: Input text.
        CHECK: Select a checkbox.
        UNCHECK: Clear a checkbox.
        SELECT_OPTION: Select options in a list.
        KEYSTROKE: Keystroke.
        WAIT: Wait.
        URL_CHANGE: Url change.
        JAVASCRIPT: Execute a JavaScript function in the target page.
        HTTP_CALL: Http call.
        WEBSOCKET_CALL: Executable WebSocket session.
        EXTRACT_VALUE: Read a typed value from the target page.
        SET_VARIABLE: Create or replace a run variable.
        VIEWPORT: Change the viewport size or orientation.
        REQUEST: Request.
        RESPONSE: Response.
        WEBSOCKET_OPEN: Websocket open.
        WEBSOCKET_SENT: Websocket sent.
        WEBSOCKET_RECEIVED: Websocket received.
        WEBSOCKET_CLOSE: Websocket close.
        WEBSOCKET_ERROR: Websocket error.
        CONSOLE: Console.
        NOTE: Note.
        SNAPSHOT: Record the matched element as evidence.

    """

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    DRAG = "drag"
    SCROLL = "scroll"
    GESTURE = "gesture"
    POSITION_POINTER = "position_pointer"
    CHECK = "check"
    UNCHECK = "uncheck"
    SELECT_OPTION = "select_option"
    INPUT_TEXT = "input_text"
    KEYSTROKE = "keystroke"
    WAIT = "wait"
    URL_CHANGE = "url_change"
    JAVASCRIPT = "javascript"
    HTTP_CALL = "http_call"
    WEBSOCKET_CALL = "websocket_call"
    EXTRACT_VALUE = "extract_value"
    SET_VARIABLE = "set_variable"
    VIEWPORT = "viewport"
    REQUEST = "request"
    RESPONSE = "response"
    WEBSOCKET_OPEN = "websocket_open"
    WEBSOCKET_SENT = "websocket_sent"
    WEBSOCKET_RECEIVED = "websocket_received"
    WEBSOCKET_CLOSE = "websocket_close"
    WEBSOCKET_ERROR = "websocket_error"
    CONSOLE = "console"
    NOTE = "note"
    SNAPSHOT = "snapshot"


@final
class Constants:
    """Group module-level constants.

    Attributes:
        minimum_viewport_edge: Grouped module constant.
        maximum_viewport_edge: Grouped module constant.
        minimum_scale: Grouped module constant.
        maximum_scale: Grouped module constant.
        max_profile_name_length: Grouped module constant.
        profile_id_pattern: Grouped module constant.
        supported_media: Grouped module constant.
        derived_media: Grouped module constant.
        max_command_args: Grouped module constant.
        max_command_chars: Grouped module constant.
        max_url_chars: Grouped module constant.
        unsupported_media: Grouped module constant.
        port_max: Grouped module constant.
        printable: Grouped module constant.
        pointer_kinds: Grouped module constant.
        parallel_kinds: Grouped module constant.
        selector_required_kinds: Grouped module constant.
        expectation_owner_kinds: Grouped module constant.

    """

    minimum_viewport_edge: Final[int] = 160
    maximum_viewport_edge: Final[int] = 8192
    minimum_scale: Final[float] = 0.5
    maximum_scale: Final[float] = 4.0
    max_profile_name_length: Final[int] = 40
    profile_id_pattern: Final[str] = "[a-z0-9][a-z0-9_-]{0,31}"
    supported_media: Final[dict[str, tuple[str, ...]]] = {
        "prefers-color-scheme": ("light", "dark"),
        "prefers-contrast": ("no-preference", "more", "less", "custom"),
        "prefers-reduced-motion": ("no-preference", "reduce"),
        "prefers-reduced-transparency": ("no-preference", "reduce"),
        "forced-colors": ("none", "active"),
        "color-gamut": ("srgb", "p3", "rec2020"),
    }
    derived_media: Final[dict[str, str]] = {
        "width": "viewport size",
        "height": "viewport size",
        "aspect-ratio": "viewport size",
        "orientation": "viewport size",
        "device-width": "viewport size",
        "device-height": "viewport size",
        "device-aspect-ratio": "viewport size",
        "resolution": "pixel density",
        "pointer": "touch setting",
        "any-pointer": "touch setting",
        "hover": "touch setting",
        "any-hover": "touch setting",
        "overflow-block": "mobile setting",
    }
    max_command_args: Final[int] = 64
    max_command_chars: Final[int] = 2000
    max_url_chars: Final[int] = 2048
    unsupported_media: Final[frozenset[str]] = frozenset(
        {
            "color",
            "color-index",
            "monochrome",
            "grid",
            "inverted-colors",
            "update",
            "display-mode",
            "dynamic-range",
            "video-dynamic-range",
            "device-posture",
            "overflow-inline",
            "scripting",
        },
    )
    port_max: Final[int] = 65535
    printable: Final[int] = 32
    pointer_kinds: Final[frozenset[EventKind]] = frozenset(
        {
            EventKind.CLICK,
            EventKind.DOUBLE_CLICK,
            EventKind.RIGHT_CLICK,
            EventKind.HOVER,
            EventKind.DRAG,
            EventKind.SCROLL,
            EventKind.GESTURE,
            EventKind.POSITION_POINTER,
            EventKind.CHECK,
            EventKind.UNCHECK,
        },
    )
    parallel_kinds: Final[frozenset[EventKind]] = frozenset(
        {
            EventKind.JAVASCRIPT,
            EventKind.INPUT_TEXT,
            EventKind.SELECT_OPTION,
            EventKind.NOTE,
            EventKind.SNAPSHOT,
            EventKind.EXTRACT_VALUE,
            EventKind.SET_VARIABLE,
        },
    )
    selector_required_kinds: Final[frozenset[EventKind]] = frozenset(
        {
            EventKind.CLICK,
            EventKind.DOUBLE_CLICK,
            EventKind.RIGHT_CLICK,
            EventKind.HOVER,
            EventKind.DRAG,
            EventKind.SCROLL,
            EventKind.GESTURE,
            EventKind.CHECK,
            EventKind.UNCHECK,
            EventKind.SELECT_OPTION,
            EventKind.INPUT_TEXT,
            EventKind.SNAPSHOT,
            EventKind.EXTRACT_VALUE,
        },
    )
    expectation_owner_kinds: Final[frozenset[EventKind]] = frozenset(
        {
            EventKind.CLICK,
            EventKind.DOUBLE_CLICK,
            EventKind.RIGHT_CLICK,
            EventKind.HOVER,
            EventKind.DRAG,
            EventKind.SCROLL,
            EventKind.GESTURE,
            EventKind.POSITION_POINTER,
            EventKind.CHECK,
            EventKind.UNCHECK,
            EventKind.SELECT_OPTION,
            EventKind.INPUT_TEXT,
            EventKind.KEYSTROKE,
            EventKind.WAIT,
            EventKind.URL_CHANGE,
            EventKind.HTTP_CALL,
            EventKind.VIEWPORT,
        },
    )


class ActionLane(StrEnum):
    """Say which input device an action occupies while it runs.

    Attributes:
        POINTER: Mouse or touch; one action at a time, in entry order.
        KEYBOARD: Real key events; one action at a time, in entry order.
        FREE: No device; may overlap with anything.

    """

    POINTER = "pointer"
    KEYBOARD = "keyboard"
    FREE = "free"


def lane_of(*, kind: EventKind) -> ActionLane:
    """Return the lane an action kind runs in.

    Args:
        kind: Action kind.

    Returns:
        ``POINTER`` for mouse kinds, ``KEYBOARD`` for key events and ``FREE``
        for everything else.

    """
    if kind in Constants.pointer_kinds:
        return ActionLane.POINTER
    if kind is EventKind.KEYSTROKE:
        return ActionLane.KEYBOARD
    return ActionLane.FREE


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewportSize:
    """Represent ViewportSize.

    Attributes:
        width: Width.
        height: Height.

    """

    width: int
    height: int

    @property
    def is_horizontal(self) -> bool:
        """The is horizontal value.

        Returns:
            The resulting value.

        """
        return self.width >= self.height

    def horizontal(self) -> Self:
        """Return horizontal.

        Returns:
            The resulting value.

        """
        return (
            self
            if self.is_horizontal
            else type(self)(width=self.height, height=self.width)
        )

    def vertical(self) -> Self:
        """Return vertical.

        Returns:
            The resulting value.

        """
        return (
            type(self)(width=self.height, height=self.width)
            if self.is_horizontal
            else self
        )

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not all(
            Constants.minimum_viewport_edge
            <= edge
            <= Constants.maximum_viewport_edge
            for edge in (self.width, self.height)
        ):
            low: int = Constants.minimum_viewport_edge
            high: int = Constants.maximum_viewport_edge
            msg: str = (
                f"Viewport edges must be between {low} and {high} CSS px."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class Profile:
    """A named browser condition a flow is recorded and tested under.

    Attributes:
        profile_id: Stable identifier that flows and runs refer to.
        name: Name shown to the user.
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        scale: Device pixel ratio (the ``resolution`` media feature, in dppx).
        screen_width: Device screen width in CSS pixels, or None.
        screen_height: Device screen height in CSS pixels, or None.
        touch: Whether the device has touch input (coarse pointer, no hover).
        mobile: Whether the browser behaves as a mobile device.
        media: Emulated media features as sorted feature and value pairs.

    """

    profile_id: str
    name: str
    width: int
    height: int
    scale: float = 1.0
    screen_width: int | None = None
    screen_height: int | None = None
    touch: bool = False
    mobile: bool = False
    media: tuple[tuple[str, str], ...] = ()

    @property
    def device_settings(
        self,
    ) -> tuple[float, bool, bool, int | None, int | None]:
        """Settings Chromium only accepts when a browser context is created.

        Returns:
            Values that differ exactly when the browser must be reopened.

        """
        return (
            self.scale,
            self.mobile,
            self.touch,
            self.screen_width,
            self.screen_height,
        )

    @property
    def size(self) -> ViewportSize:
        """The viewport this profile applies.

        Returns:
            Viewport size in CSS pixels.

        """
        return ViewportSize(width=self.width, height=self.height)

    @staticmethod
    def check_media(*, name: str, value: str) -> None:
        """Accept only media features the test browser really emulates.

        Args:
            name: Media feature name, without parentheses.
            value: Requested value.

        Raises:
            ValueError: When the feature is derived, unsupported or unknown,
                or the value is not allowed.

        """
        if name in Constants.derived_media:
            source: str = Constants.derived_media[name]
            msg: str = (
                f"{name} follows from the profile's "
                f"{source}; set that instead."
            )
            raise ValueError(msg)
        if name in Constants.unsupported_media:
            msg = f"{name} cannot be emulated by the test browser."
            raise ValueError(msg)
        allowed: tuple[str, ...] | None = Constants.supported_media.get(name)
        if allowed is None:
            msg = f"{name} is not a media feature."
            raise ValueError(msg)
        if value not in allowed:
            msg = f"{name} accepts: {', '.join(allowed)}."
            raise ValueError(msg)

    def __post_init__(self) -> None:
        """Reject profiles the test browser could not honour.

        Raises:
            ValueError: When an identifier, size or media feature is invalid.

        """
        if fullmatch(
            pattern=Constants.profile_id_pattern,
            string=self.profile_id,
        ) is None or self.profile_id in {"shared", "custom"}:
            msg: str = (
                "A profile ID uses lowercase letters, digits, '-' "
                "or '_' (at most 32) and cannot be 'shared' or "
                "'custom'."
            )
            raise ValueError(msg)
        if not 0 < len(self.name.strip()) <= Constants.max_profile_name_length:
            longest: int = Constants.max_profile_name_length
            msg = f"A profile name needs 1 to {longest} characters."
            raise ValueError(msg)
        _ = ViewportSize(width=self.width, height=self.height)
        if (self.screen_width is None) != (self.screen_height is None):
            msg = "Set both device screen width and height, or neither."
            raise ValueError(msg)
        if self.screen_width is not None and self.screen_height is not None:
            _ = ViewportSize(
                width=self.screen_width,
                height=self.screen_height,
            )
        if (
            not Constants.minimum_scale
            <= self.scale
            <= Constants.maximum_scale
        ):
            msg = (
                f"Pixel density must be between "
                f"{Constants.minimum_scale} and {Constants.maximum_scale}."
            )
            raise ValueError(msg)
        names: list[str] = [name for name, _ in self.media]
        if len(set(names)) != len(names):
            msg = "A media feature can be set only once per profile."
            raise ValueError(msg)
        for name, value in self.media:
            self.check_media(name=name, value=value)


def default_profiles() -> tuple[Profile, ...]:
    """Return the profiles a new project starts with.

    Returns:
        Desktop, tablet and mobile profiles that users can change or remove.

    """
    return (
        Profile(profile_id="desktop", name="Desktop", width=1440, height=900),
        Profile(profile_id="tablet", name="Tablet", width=1024, height=1366),
        Profile(profile_id="mobile", name="Mobile", width=390, height=844),
    )


class TargetMode(StrEnum):
    """How the application under test is reached.

    Attributes:
        URL: An address that is already serving.
        SERVICE: A command Studio starts and whose port it detects.

    """

    URL = "url"
    SERVICE = "service"


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """The application a project records and tests.

    Attributes:
        mode: Whether the address is given or a service is started.
        url: URL mode address without a port; empty until configured.
        port: URL mode port; None uses 80 for http and 443 for https.
        command: Service mode program and arguments, run without a shell.
        cwd: Service mode working directory, relative to the project.
        service_port: Service mode port; None detects it automatically.
        path: Service mode page opened on the detected server.

    """

    mode: TargetMode = TargetMode.URL
    url: str = ""
    port: int | None = None
    command: tuple[str, ...] = ()
    cwd: str = ""
    service_port: int | None = None
    path: str = "/"

    @property
    def default_port(self) -> int:
        """The port used when none is given: 443 for https, else 80.

        Returns:
            Port number.

        """
        return 443 if self.url.startswith("https://") else 80

    def origin(self, *, service_url: str | None = None) -> str | None:
        """Return scheme, host and port of the target, when it has one.

        Args:
            service_url: Base URL of the running service, in service mode.

        Returns:
            Such as ``http://127.0.0.1:5173``, else None.

        """
        parts: SplitResult = urlsplit(
            url=self.address(service_url=service_url),
        )
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return None
        return f"{parts.scheme}://{parts.netloc}"

    def address(self, *, service_url: str | None = None) -> str:
        """Return the address the browser should open.

        Args:
            service_url: Base URL of the running service, in service mode.

        Returns:
            The page URL, or ``about:blank`` while nothing is configured.

        """
        if self.mode is TargetMode.SERVICE:
            return (
                f"{service_url.rstrip('/')}{self.path}"
                if service_url
                else "about:blank"
            )
        if not self.url:
            return "about:blank"
        scheme, host, rest = self._parts()
        port: int = self.port or self.default_port
        shown: str = "" if port == self.default_port else f":{port}"
        return f"{scheme}://{host}{shown}{rest}"

    def __post_init__(self) -> None:
        """Reject targets Studio could not safely reach or start.

        Raises:
            ValueError: When an address, port, command or path is invalid.

        """
        for port in (self.port, self.service_port):
            if port is not None and (not 1 <= port <= Constants.port_max):
                msg: str = (
                    f"A port is a number from 1 to {Constants.port_max}."
                )
                raise ValueError(msg)
        if self.url:
            self._parts()
        if not self.path.startswith("/") or any(
            char.isspace() or ord(char) < Constants.printable
            for char in self.path
        ):
            msg = "The page path starts with '/' and has no spaces."
            raise ValueError(msg)
        if (
            len(self.command) > Constants.max_command_args
            or sum(len(item) for item in self.command)
            > Constants.max_command_chars
            or any(not item or "\x00" in item for item in self.command)
        ):
            msg = "A service command needs short, non-empty arguments."
            raise ValueError(msg)
        if self.mode is TargetMode.SERVICE and (not self.command):
            msg = "Enter the command that starts the service."
            raise ValueError(msg)
        if self.cwd and (
            self.cwd.startswith(("/", "\\"))
            or ".." in self.cwd.replace("\\", "/").split(sep="/")
            or "\x00" in self.cwd
        ):
            msg = "The working directory is a folder inside the project."
            raise ValueError(msg)

    def _parts(self) -> tuple[str, str, str]:
        """Split and validate the URL.

        Returns:
            Scheme, bracket-safe host and the rest of the address.

        Raises:
            ValueError: When it is not a plain http or https address.

        """
        text: str = self.url if "://" in self.url else f"http://{self.url}"
        if len(text) > Constants.max_url_chars:
            msg: str = "The address is too long."
            raise ValueError(msg)
        parts: SplitResult = urlsplit(url=text)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            msg = "Use an http:// or https:// address with a host."
            raise ValueError(msg)
        if parts.username or parts.password:
            msg = "Do not put a login in the address."
            raise ValueError(msg)
        if parts.port is not None:
            msg = "Put the port in the port field, not in the address."
            raise ValueError(msg)
        name: str = parts.hostname
        host: str = f"[{name}]" if ":" in name else name
        rest: str = urlunsplit(
            components=("", "", parts.path, parts.query, parts.fragment),
        )
        return (parts.scheme, host, rest)


@dataclass(frozen=True, slots=True, kw_only=True)
class HttpHeader:
    """Represent HttpHeader.

    Attributes:
        name: Name.
        value: Value.

    """

    name: str
    value: str

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "":
            msg: str = "HTTP header name cannot be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryCondition:
    """Represent QueryCondition.

    Attributes:
        name: Name.
        operator: Operator.
        value: Value.

    """

    name: str
    operator: ConditionOperator
    value: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "":
            msg: str = "Query-condition name cannot be empty."
            raise ValueError(msg)
        if (
            self.operator is not ConditionOperator.EXISTS
            and self.value is None
        ):
            msg = "Non-existence query operators require a value."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class JsonCondition:
    """Represent JsonCondition.

    Attributes:
        path: Path.
        operator: Operator.
        value: Value.

    """

    path: str
    operator: ConditionOperator
    value: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not self.path.startswith("$"):
            msg: str = "JSON condition paths must start with '$'."
            raise ValueError(msg)
        if (
            self.operator is not ConditionOperator.EXISTS
            and self.value is None
        ):
            msg = "Non-existence JSON operators require a value."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class NetworkExpectation:
    """Represent NetworkExpectation.

    Attributes:
        expectation_id: Expectation id.
        label: Label.
        method: Method.
        url_pattern: Url pattern.
        url_match: Url match.
        query_conditions: Query conditions.
        expected_status: Expected status.
        expected_headers: Expected headers.
        body_match: Body match.
        expected_body: Expected body.
        json_conditions: Json conditions.
        timeout_ms: Timeout ms.

    """

    expectation_id: str
    label: str
    method: str | None = None
    url_pattern: str | None = None
    url_match: UrlMatchMode = UrlMatchMode.EXACT
    query_conditions: tuple[QueryCondition, ...] = ()
    expected_status: int | None = None
    expected_headers: tuple[HttpHeader, ...] = ()
    body_match: BodyMatchMode = BodyMatchMode.NONE
    expected_body: str | None = None
    json_conditions: tuple[JsonCondition, ...] = ()
    timeout_ms: int = 5000

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.expectation_id.strip() == "":
            msg: str = "Expectation ID cannot be empty."
            raise ValueError(msg)
        if self.timeout_ms <= 0:
            msg = "Expectation timeout must be positive."
            raise ValueError(msg)
        if (
            self.body_match is not BodyMatchMode.NONE
            and self.expected_body is None
        ):
            msg = "Selected body match mode requires an expected body."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowParameter:
    """Represent FlowParameter.

    Attributes:
        name: Name.
        value_type: Value type.
        required: Required.
        default_value: Default value.

    """

    name: str
    value_type: ValueType
    required: bool = True
    default_value: str | int | float | bool | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "":
            msg: str = "Flow parameter name cannot be empty."
            raise ValueError(msg)
        if self.required and self.default_value is not None:
            msg = "Required Flow parameters cannot define defaults."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowOutput:
    """Represent FlowOutput.

    Attributes:
        name: Name.
        value_type: Value type.
        expression: Expression.

    """

    name: str
    value_type: ValueType
    expression: str

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "" or self.expression.strip() == "":
            msg: str = "Flow outputs require a name and expression."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class VariableDefinition:
    """Represent VariableDefinition.

    Attributes:
        name: Name.
        value_type: Value type.
        scope: Scope.
        flow_id: Flow id.
        default_value: Default value.
        source_name: Source name.

    """

    name: str
    value_type: ValueType
    scope: VariableScope
    flow_id: str | None = None
    default_value: str | int | float | bool | None = None
    source_name: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "":
            msg: str = "Variable name cannot be empty."
            raise ValueError(msg)
        if self.scope is VariableScope.FLOW and self.flow_id is None:
            msg = "Flow-scoped variables require a Flow ID."
            raise ValueError(msg)
        if self.scope is not VariableScope.FLOW and self.flow_id is not None:
            msg = "Only Flow-scoped variables may carry a Flow ID."
            raise ValueError(msg)
        if self.scope in {VariableScope.ENVIRONMENT, VariableScope.CREDENTIAL}:
            if not self.source_name:
                msg = "Environment and secret variables require a source name."
                raise ValueError(msg)
            if self.default_value is not None:
                msg = (
                    "Environment and secret variables cannot persist defaults."
                )
                raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeVariable:
    """Represent RuntimeVariable.

    Attributes:
        name: Name.
        value_type: Value type.
        value: Value.
        secret: Secret.

    """

    name: str
    value_type: ValueType
    value: str | int | float | bool | None
    secret: bool = False

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "":
            msg: str = "Runtime variable name cannot be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssertionSpec:
    """Represent AssertionSpec.

    Attributes:
        assertion_id: Assertion id.
        label: Label.
        kind: Kind.
        operator: Operator.
        target: Target.
        selector_id: Saved selector reference for DOM assertions.
        expected: Expected.
        attribute: Attribute.
        timeout_ms: Timeout ms.

    """

    assertion_id: str
    label: str
    kind: AssertionKind
    operator: AssertionOperator
    target: str = ""
    selector_id: str | None = None
    expected: str | None = None
    attribute: str | None = None
    timeout_ms: int = 5000

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.assertion_id.strip() == "":
            msg: str = "Assertion ID cannot be empty."
            raise ValueError(msg)
        if self.timeout_ms <= 0:
            msg = "Assertion timeout must be positive."
            raise ValueError(msg)
        if (
            self.kind
            in {
                AssertionKind.DOM_VISIBLE,
                AssertionKind.DOM_HIDDEN,
                AssertionKind.DOM_TEXT,
                AssertionKind.DOM_ATTRIBUTE,
                AssertionKind.DOM_COUNT,
            }
            and self.target.strip() == ""
            and (not self.selector_id)
        ):
            msg = "DOM assertions require a selector target or reference."
            raise ValueError(msg)
        if self.kind is AssertionKind.DOM_ATTRIBUTE and (not self.attribute):
            msg = "DOM attribute assertions require an attribute name."
            raise ValueError(msg)
        if (
            self.operator
            not in {AssertionOperator.EXISTS, AssertionOperator.NOT_EXISTS}
            and self.expected is None
        ):
            msg = "Comparison assertions require an expected value."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputBinding:
    """Represent OutputBinding.

    Attributes:
        name: Name.
        value_type: Value type.
        source: Source.
        expression: Expression.
        selector: Selector.
        attribute: Attribute.

    """

    name: str
    value_type: ValueType
    source: OutputSource
    expression: str
    selector: str | None = None
    attribute: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.name.strip() == "" or self.expression.strip() == "":
            msg: str = "Output bindings require a name and expression."
            raise ValueError(msg)
        if self.source in {
            OutputSource.DOM_TEXT,
            OutputSource.DOM_ATTRIBUTE,
        } and (not self.selector):
            msg = "DOM output bindings require a CSS selector."
            raise ValueError(msg)
        if self.source is OutputSource.DOM_ATTRIBUTE and (not self.attribute):
            msg = "DOM attribute outputs require an attribute name."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionContract:
    """Represent ActionContract.

    Attributes:
        preconditions: Preconditions.
        postconditions: Postconditions.
        outputs: Outputs.
        retry_count: Retry count.
        retry_delay_ms: Retry delay ms.
        continue_on_failure: Continue on failure.
        pace: Pause or wait applied after the action has finished.

    """

    preconditions: tuple[AssertionSpec, ...] = ()
    postconditions: tuple[AssertionSpec, ...] = ()
    outputs: tuple[OutputBinding, ...] = ()
    retry_count: int = 0
    retry_delay_ms: int = 0
    continue_on_failure: bool = False
    pace: Pace | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.retry_count < 0 or self.retry_delay_ms < 0:
            msg: str = "Action retry values cannot be negative."
            raise ValueError(msg)
        identifiers: tuple[str, ...] = tuple(
            assertion.assertion_id
            for assertion in (*self.preconditions, *self.postconditions)
        )
        if len(set(identifiers)) != len(identifiers):
            msg = "Assertion IDs must be unique within an action contract."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class EventDraft:
    """Represent EventDraft.

    Attributes:
        layer: Layer.
        kind: Kind.
        label: Label.
        selector: Selector.
        url: Url.
        method: Method.
        status: Status.
        payload: Payload.
        headers: Headers.
        share_session_cookies: Share session cookies.
        caused_by_event_id: Caused by event id.
        position_action: Position action.
        x: X.
        y: Y.
        end_x: End x.
        end_y: End y.

    """

    layer: TimelineLayer
    kind: EventKind
    label: str
    selector: str | None = None
    url: str | None = None
    method: str | None = None
    status: int | None = None
    payload: str | None = None
    headers: tuple[HttpHeader, ...] = ()
    share_session_cookies: bool = False
    caused_by_event_id: str | None = None
    position_action: PositionPointerAction | None = None
    x: int | None = None
    y: int | None = None
    end_x: int | None = None
    end_y: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TimelineEvent:
    """Represent TimelineEvent.

    Attributes:
        event_id: Event id.
        flow_id: Flow id.
        sequence: Sequence.
        elapsed_ms: Elapsed ms.
        layer: Layer.
        kind: Kind.
        label: Label.
        selector: Selector.
        url: Url.
        method: Method.
        status: Status.
        payload: Payload.
        headers: Headers.
        share_session_cookies: Share session cookies.
        caused_by_event_id: Caused by event id.
        position_action: Position action.
        x: X.
        y: Y.
        end_x: End x.
        end_y: End y.
        expectations: Expectations.
        contract: Contract.
        request_id: Request id.
        initiator_url: Initiator url.
        initiator_stack: Initiator stack.
        recording_group_id: Recording parent that owns this action, if any.
        correlation_id: Identifier linking related requests and actions.
        attribution_confidence: Confidence that the cause was identified.
        attribution_reasons: Evidence behind the attribution.
        correlation_id: Correlation id.
        attribution_confidence: Attribution confidence.
        attribution_reasons: Attribution reasons.
        selector_id: Reusable project selector the action targets.
        targets: Whether the action applies to the first match or all.
        run_mode: How several targets are processed.
        pace_between: Pause or wait between sequential targets.
        sandbox: Run a JavaScript action in the isolated sandbox.
        output_variable: Run variable that receives the action result.
        when_expression: JavaScript condition that guards this action.
        incomplete: Whether required settings are still to be filled in.

    """

    event_id: str
    flow_id: str
    sequence: int
    elapsed_ms: int
    layer: TimelineLayer
    kind: EventKind
    label: str
    recording_group_id: str | None = None
    selector: str | None = None
    url: str | None = None
    method: str | None = None
    status: int | None = None
    payload: str | None = None
    headers: tuple[HttpHeader, ...] = ()
    share_session_cookies: bool = False
    caused_by_event_id: str | None = None
    position_action: PositionPointerAction | None = None
    x: int | None = None
    y: int | None = None
    end_x: int | None = None
    end_y: int | None = None
    expectations: tuple[NetworkExpectation, ...] = ()
    contract: ActionContract = field(default_factory=ActionContract)
    request_id: str | None = None
    initiator_url: str | None = None
    initiator_stack: tuple[str, ...] = ()
    correlation_id: str | None = None
    attribution_confidence: float | None = None
    attribution_reasons: tuple[str, ...] = ()
    selector_id: str | None = None
    targets: TargetScope = TargetScope.FIRST
    run_mode: RunMode = RunMode.SEQUENTIAL
    pace_between: Pace | None = None
    sandbox: bool = False
    output_variable: str | None = None
    when_expression: str | None = None
    incomplete: bool = False

    @property
    def supports_network_expectations(self) -> bool:
        """The supports network expectations value.

        Returns:
            The resulting value.

        """
        return self.kind in Constants.expectation_owner_kinds

    def with_sequence(self, *, sequence: int) -> Self:
        """Return with sequence.

        Args:
            sequence: Sequence.

        Returns:
            The resulting value.

        """
        return replace(self, sequence=sequence)

    def with_expectations(
        self,
        *,
        expectations: tuple[NetworkExpectation, ...],
    ) -> Self:
        """Return with expectations.

        Args:
            expectations: Expectations.

        Returns:
            The resulting value.

        """
        return replace(self, expectations=expectations)

    def with_contract(self, *, contract: ActionContract) -> Self:
        """Return with contract.

        Args:
            contract: Contract.

        Returns:
            The resulting value.

        """
        return replace(self, contract=contract)

    def with_attribution(
        self,
        *,
        caused_by_event_id: str,
        confidence: float,
        reasons: tuple[str, ...],
    ) -> Self:
        """Return with attribution.

        Args:
            caused_by_event_id: Caused by event id.
            confidence: Confidence.
            reasons: Reasons.

        Returns:
            The resulting value.

        """
        return replace(
            self,
            caused_by_event_id=caused_by_event_id,
            attribution_confidence=confidence,
            attribution_reasons=reasons,
        )

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.elapsed_ms < 0:
            msg: str = "Event elapsed time cannot be negative."
            raise ValueError(msg)
        self._validate_targeting()
        self._validate_selector_reference()
        self._validate_http_action()
        self._validate_expectations()
        self._validate_attribution()
        if self.output_variable is not None and (
            not self.output_variable.strip()
            or "{" in self.output_variable
            or "}" in self.output_variable
        ):
            msg = "A variable name cannot be empty or hold braces."
            raise ValueError(msg)
        if self.when_expression is not None and (
            not self.when_expression.strip()
        ):
            msg = "A conditional action needs a non-empty expression."
            raise ValueError(msg)
        if (
            self.kind in {EventKind.EXTRACT_VALUE, EventKind.SET_VARIABLE}
            and self.output_variable is None
            and (not self.incomplete)
        ):
            msg = f"{self.kind.value} actions must name their output variable."
            raise ValueError(msg)

    def _validate_targeting(self) -> None:
        """Handle validate targeting.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if (
            self.kind in Constants.selector_required_kinds
            and (not (self.selector or self.selector_id))
            and (not self.incomplete)
        ):
            msg: str = f"{self.kind.value} actions require a CSS selector."
            raise ValueError(msg)
        coordinates: tuple[int | None, ...] = (
            self.x,
            self.y,
            self.end_x,
            self.end_y,
        )
        if self.kind is EventKind.POSITION_POINTER:
            if self.selector is not None:
                msg = "Position pointer actions cannot carry selectors."
                raise ValueError(msg)
            if (
                self.position_action is None
                or self.x is None
                or self.y is None
            ):
                msg = "Position pointer actions require an action and x/y."
                raise ValueError(msg)
            return
        if any(value is not None for value in coordinates):
            msg = (
                "Coordinates are only legal on explicit position_pointer "
                "actions."
            )
            raise ValueError(msg)
        if self.position_action is not None:
            msg = "position_action is only valid for position_pointer."
            raise ValueError(msg)

    def _validate_selector_reference(self) -> None:
        """Check selector references, targeting modes and sandbox use.

        Raises:
            ValueError: When the combination of fields is not allowed.

        """
        if self.selector and self.selector_id:
            msg: str = "An action uses a selector or a selector_id, not both."
            raise ValueError(msg)
        if self.selector_id and self.kind is EventKind.POSITION_POINTER:
            msg = "Position pointer actions cannot carry selectors."
            raise ValueError(msg)
        referenced: bool = bool(self.selector or self.selector_id)
        if self.targets is TargetScope.ALL and (not referenced):
            msg = "Targeting all matches needs a selector."
            raise ValueError(msg)
        if (
            self.pace_between is not None
            and self.targets is not TargetScope.ALL
        ):
            msg = "A pause between targets needs targets set to all."
            raise ValueError(msg)
        if self.run_mode is RunMode.PARALLEL:
            if self.targets is not TargetScope.ALL:
                msg = "Parallel runs need targets set to all."
                raise ValueError(msg)
            if self.kind not in Constants.parallel_kinds:
                msg = (
                    f"{self.kind.value} actions use a shared input device and "
                    f"cannot run in parallel."
                )
                raise ValueError(msg)
        if self.sandbox and self.kind is not EventKind.JAVASCRIPT:
            msg = "Only JavaScript actions run in the sandbox."
            raise ValueError(msg)
        if (
            self.kind is EventKind.JAVASCRIPT
            and self.targets is TargetScope.ALL
            and (not self.sandbox)
        ):
            msg = "JavaScript actions that target elements run in the sandbox."
            raise ValueError(msg)

    def _validate_http_action(self) -> None:
        """Validate executable REST and WebSocket request actions.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.kind is EventKind.HTTP_CALL:
            if self.layer is not TimelineLayer.NETWORK:
                msg: str = "HTTP call actions must use the network layer."
                raise ValueError(msg)
            if (not self.url or not self.method) and (not self.incomplete):
                msg = "HTTP call actions require method and URL."
                raise ValueError(msg)
            return
        if self.kind is EventKind.WEBSOCKET_CALL:
            if self.layer is not TimelineLayer.WEBSOCKET:
                msg = "WebSocket call actions must use the websocket layer."
                raise ValueError(msg)
            if not self.url and (not self.incomplete):
                msg = "WebSocket call actions require a URL."
                raise ValueError(msg)
            return
        if self.share_session_cookies:
            msg = "Cookie sharing is only valid for HTTP call actions."
            raise ValueError(msg)

    def _validate_expectations(self) -> None:
        """Handle validate expectations.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.expectations and (not self.supports_network_expectations):
            msg: str = (
                "Network expectations can only be attached to "
                "executable Flow actions."
            )
            raise ValueError(msg)

    def _validate_attribution(self) -> None:
        """Handle validate attribution.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.attribution_confidence is not None and (
            not 0.0 <= self.attribution_confidence <= 1.0
        ):
            msg: str = "Attribution confidence must be between 0 and 1."
            raise ValueError(msg)
        if self.caused_by_event_id is None and (
            self.attribution_confidence is not None or self.attribution_reasons
        ):
            msg = "Attribution metadata requires a causal event ID."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowSettings:
    """Represent FlowSettings.

    Attributes:
        name: Name.
        task_description: Task description.
        expected_behavior: Expected behavior.
        notes: Notes.
        device_modes: Device modes.
        capture_record_images: Capture record images.
        capture_play_images: Capture play images.
        parameters: Flow inputs; None keeps the ones the flow already has.

    """

    name: str
    task_description: str
    expected_behavior: str
    notes: str
    device_modes: frozenset[str]
    capture_record_images: bool
    capture_play_images: bool
    parameters: tuple[FlowParameter, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowRecording:
    """A non-executable parent task containing captured timeline actions.

    Attributes:
        recording_id: Stable identifier of the parent task.
        label: Name shown for the parent task.
        start_ms: Timeline offset where the recording begins.

    """

    recording_id: str
    label: str
    start_ms: int

    def __post_init__(self) -> None:
        """Reject invalid parent identities and negative timeline offsets.

        Raises:
            ValueError: When a parent identity is invalid or the timeline
                offset is negative.

        """
        if not self.recording_id or not self.label or self.start_ms < 0:
            msg: str = "A recording needs an ID, label and nonnegative start."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class Flow:
    """Represent Flow.

    Attributes:
        flow_id: Flow id.
        name: Name.
        task_description: Task description.
        expected_behavior: Expected behavior.
        notes: Notes.
        device_modes: Device modes.
        capture_record_images: Capture record images.
        capture_play_images: Capture play images.
        parameters: Parameters.
        outputs: Outputs.
        events: Events.
        recordings: Non-executable parent tasks that group captured actions.

    """

    flow_id: str
    name: str
    task_description: str
    expected_behavior: str
    notes: str
    device_modes: frozenset[str] = field(
        default_factory=lambda: frozenset({DeviceMode.SHARED}),
    )
    capture_record_images: bool = False
    capture_play_images: bool = False
    parameters: tuple[FlowParameter, ...] = ()
    outputs: tuple[FlowOutput, ...] = ()
    events: tuple[TimelineEvent, ...] = ()
    recordings: tuple[FlowRecording, ...] = ()

    def with_events(self, *, events: tuple[TimelineEvent, ...]) -> Self:
        """Return with events.

        Args:
            events: Events.

        Returns:
            The resulting value.

        """
        return replace(self, events=events)

    def with_settings(self, *, settings: FlowSettings) -> Self:
        """Return with settings.

        Args:
            settings: Settings.

        Returns:
            The resulting value.

        """
        return replace(
            self,
            name=settings.name,
            task_description=settings.task_description,
            expected_behavior=settings.expected_behavior,
            notes=settings.notes,
            device_modes=settings.device_modes,
            capture_record_images=settings.capture_record_images,
            capture_play_images=settings.capture_play_images,
            parameters=self.parameters
            if settings.parameters is None
            else settings.parameters,
        )

    def applies_to(self, *, device_mode: str) -> bool:
        """Return applies to.

        Args:
            device_mode: Device mode.

        Returns:
            The resulting value.

        """
        return (
            DeviceMode.SHARED in self.device_modes
            or device_mode in self.device_modes
        )

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not self.device_modes:
            msg: str = "A Flow must target at least one device mode."
            raise ValueError(msg)
        self._validate_recordings()
        if (
            DeviceMode.SHARED in self.device_modes
            and len(self.device_modes) != 1
        ):
            msg = "Shared scope cannot be combined with device scopes."
            raise ValueError(msg)
        parameter_names: tuple[str, ...] = tuple(
            parameter.name for parameter in self.parameters
        )
        output_names: tuple[str, ...] = tuple(
            output.name for output in self.outputs
        )
        if len(set(parameter_names)) != len(parameter_names):
            msg = "Flow parameter names must be unique."
            raise ValueError(msg)
        if len(set(output_names)) != len(output_names):
            msg = "Flow output names must be unique."
            raise ValueError(msg)

    def _validate_recordings(self) -> None:
        """Require unique parent IDs and reject orphaned captured actions.

        Raises:
            ValueError: When recording IDs repeat or actions are orphaned.

        """
        identifiers: set[str] = {
            group.recording_id for group in self.recordings
        }
        if len(identifiers) != len(self.recordings):
            msg: str = "Recording IDs must be unique within a flow."
            raise ValueError(msg)
        if any(
            event.recording_group_id is not None
            and event.recording_group_id not in identifiers
            for event in self.events
        ):
            msg = "Recorded actions must reference a parent in their flow."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowEdge:
    """Represent FlowEdge.

    Attributes:
        source_flow_id: Source flow id.
        target_flow_id: Target flow id.
        mode: Mode.
        condition_expression: Condition expression.
        priority: Priority.
        max_traversals: Max traversals.

    """

    source_flow_id: str
    target_flow_id: str
    mode: TransitionMode = TransitionMode.ALWAYS
    condition_expression: str | None = None
    priority: int = 0
    max_traversals: int = 1

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.max_traversals <= 0:
            msg: str = "Flow-edge max traversals must be positive."
            raise ValueError(msg)
        if self.mode is TransitionMode.CONDITION and (
            not self.condition_expression
        ):
            msg = "Conditional Flow edges require an expression."
            raise ValueError(msg)
        if (
            self.mode is not TransitionMode.CONDITION
            and self.condition_expression
        ):
            msg = "Only conditional Flow edges may define an expression."
            raise ValueError(msg)
        if (
            self.source_flow_id == self.target_flow_id
            and self.mode is not TransitionMode.RETRY
        ):
            msg = "A Flow may transition to itself only through a retry edge."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScreenshotArtifact:
    """Represent ScreenshotArtifact.

    Attributes:
        artifact_id: Artifact id.
        flow_id: Flow id.
        event_id: Event id.
        phase: Phase.
        path: Path.
        width: Width.
        height: Height.
        sha256: Sha256.

    """

    artifact_id: str
    flow_id: str
    event_id: str
    phase: CapturePhase
    path: str
    width: int
    height: int
    sha256: str

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.width <= 0 or self.height <= 0:
            msg: str = "Screenshot dimensions must be positive."
            raise ValueError(msg)
        if self.path.strip() == "":
            msg = "Screenshot path cannot be empty."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpectationResult:
    """Represent ExpectationResult.

    Attributes:
        result_id: Result id.
        flow_id: Flow id.
        event_id: Event id.
        expectation_id: Expectation id.
        outcome: Outcome.
        details: Details.
        matched_url: Matched url.
        actual_status: Actual status.
        actual_body: Actual body.

    """

    result_id: str
    flow_id: str
    event_id: str
    expectation_id: str
    outcome: ExpectationOutcome
    details: str
    matched_url: str | None = None
    actual_status: int | None = None
    actual_body: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckpointDefinition:
    """Represent CheckpointDefinition.

    Attributes:
        checkpoint_id: Checkpoint id.
        name: Name.
        flow_id: Flow id.
        event_id: Event id.
        include_cookies: Include cookies.
        include_local_storage: Include local storage.
        include_session_storage: Include session storage.
        include_indexed_db: Include indexed db.
        include_variables: Include variables.

    """

    checkpoint_id: str
    name: str
    flow_id: str
    event_id: str | None = None
    include_cookies: bool = True
    include_local_storage: bool = True
    include_session_storage: bool = True
    include_indexed_db: bool = False
    include_variables: bool = True

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.checkpoint_id.strip() == "" or self.name.strip() == "":
            msg: str = "Checkpoint definitions require ID and name."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckpointArtifact:
    """Represent CheckpointArtifact.

    Attributes:
        artifact_id: Artifact id.
        checkpoint_id: Checkpoint id.
        run_id: Run id.
        flow_id: Flow id.
        event_id: Event id.
        url: Url.
        cookies_json: Cookies json.
        local_storage_json: Local storage json.
        session_storage_json: Session storage json.
        indexed_db_json: Indexed db json.
        variables: Variables.

    """

    artifact_id: str
    checkpoint_id: str
    run_id: str
    flow_id: str
    event_id: str | None
    url: str
    cookies_json: str | None = None
    local_storage_json: str | None = None
    session_storage_json: str | None = None
    indexed_db_json: str | None = None
    variables: tuple[RuntimeVariable, ...] = ()

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if any(
            value.strip() == ""
            for value in (
                self.artifact_id,
                self.checkpoint_id,
                self.run_id,
                self.flow_id,
            )
        ):
            msg: str = "Checkpoint artifacts require non-empty IDs."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AssertionResult:
    """Represent AssertionResult.

    Attributes:
        assertion_id: Assertion id.
        outcome: Outcome.
        details: Details.
        actual: Actual.

    """

    assertion_id: str
    outcome: AssertionOutcome
    details: str
    actual: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionRunRecord:
    """Represent ActionRunRecord.

    Attributes:
        event_id: Event id.
        flow_id: Flow id.
        status: Status.
        attempt: Attempt.
        started_ms: Started ms.
        finished_ms: Finished ms.
        assertions: Assertions.
        observed_event_ids: Observed event ids.
        screenshot_artifact_ids: Screenshot artifact ids.
        outputs: Outputs.
        error: Error.
        response_json: Serialized JavaScript return value, including null.
        cause_json: Serialized failure cause, when the action failed.
        streams_json: Serialized log, warning and error entries it produced.
        unit_index: Position of this target among the action's targets.
        unit_count: Number of targets the action expanded to.

    """

    event_id: str
    flow_id: str
    status: ActionRunStatus
    attempt: int
    started_ms: int
    finished_ms: int
    assertions: tuple[AssertionResult, ...] = ()
    observed_event_ids: tuple[str, ...] = ()
    screenshot_artifact_ids: tuple[str, ...] = ()
    outputs: tuple[RuntimeVariable, ...] = ()
    error: str | None = None
    response_json: str | None = None
    cause_json: str | None = None
    streams_json: str | None = None
    unit_index: int | None = None
    unit_count: int | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if (self.unit_index is None) != (self.unit_count is None):
            msg: str = "A unit needs both its index and the unit count."
            raise ValueError(msg)
        if self.attempt <= 0 or self.started_ms < 0:
            msg = "Action attempts and timestamps must be positive."
            raise ValueError(msg)
        if self.finished_ms < self.started_ms:
            msg = "Action finish time cannot precede its start time."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowExecutionResult:
    """Represent FlowExecutionResult.

    Attributes:
        run_id: Run id.
        flow_id: Flow id.
        status: Status.
        action_records: Action records.
        outputs: Outputs.
        error: Error.

    """

    run_id: str
    flow_id: str
    status: RunStatus
    action_records: tuple[ActionRunRecord, ...] = ()
    outputs: tuple[RuntimeVariable, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.status is RunStatus.RUNNING:
            msg: str = "Flow execution results must be terminal."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunTransition:
    """Represent RunTransition.

    Attributes:
        source_flow_id: Source flow id.
        target_flow_id: Target flow id.
        mode: Mode.
        reason: Reason.

    """

    source_flow_id: str
    target_flow_id: str
    mode: TransitionMode
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionRun:
    """Represent ExecutionRun.

    Attributes:
        run_id: Run id.
        initial_flow_id: Initial flow id.
        current_flow_id: Current flow id.
        device_mode: Device mode.
        status: Status.
        started_at_utc: Started at utc.
        finished_at_utc: Finished at utc.
        action_records: Action records.
        transitions: Transitions.
        variables: Variables.
        failure_reason: Failure reason.

    """

    run_id: str
    initial_flow_id: str
    current_flow_id: str | None
    device_mode: str
    status: RunStatus
    started_at_utc: str
    finished_at_utc: str | None = None
    action_records: tuple[ActionRunRecord, ...] = ()
    transitions: tuple[RunTransition, ...] = ()
    variables: tuple[RuntimeVariable, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        """Handle post init.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.run_id.strip() == "" or self.initial_flow_id.strip() == "":
            msg: str = "Execution runs require non-empty IDs."
            raise ValueError(msg)
        if (
            self.status is RunStatus.RUNNING
            and self.finished_at_utc is not None
        ):
            msg = "Running executions cannot have a finish timestamp."
            raise ValueError(msg)
        if (
            self.status is not RunStatus.RUNNING
            and self.finished_at_utc is None
        ):
            msg = "Terminal executions require a finish timestamp."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class Workspace:
    """Represent Workspace.

    Attributes:
        flows: Flows.
        edges: Edges.
        screenshots: Screenshots.
        variables: Variables.
        checkpoint_definitions: Checkpoint definitions.
        checkpoint_artifacts: Checkpoint artifacts.
        runs: Runs.
        profiles: Browser conditions flows are recorded and tested under.
        target: The application under test.
        selectors: Project-wide reusable selectors.
        project: Name, description, tags and authorship of the project.

    """

    flows: tuple[Flow, ...]
    edges: tuple[FlowEdge, ...]
    screenshots: tuple[ScreenshotArtifact, ...] = ()
    variables: tuple[VariableDefinition, ...] = ()
    checkpoint_definitions: tuple[CheckpointDefinition, ...] = ()
    checkpoint_artifacts: tuple[CheckpointArtifact, ...] = ()
    runs: tuple[ExecutionRun, ...] = ()
    profiles: tuple[Profile, ...] = field(default_factory=default_profiles)
    target: Target = field(default_factory=Target)
    selectors: tuple[SelectorDef, ...] = ()
    project: ProjectInfo = field(default_factory=ProjectInfo)


@dataclass(frozen=True, slots=True, kw_only=True)
class RecorderCommand:
    """Represent RecorderCommand.

    Attributes:
        name: Name.
        flow_id: Flow id.
        milliseconds: Milliseconds.
        width: Width.
        height: Height.
        scale: Scale.
        device_mode: Device mode.
        capture_images: Capture images.
        recording_group_id: Recording parent that receives captured actions.
        recording_start_ms: Timeline offset where the recording begins.

    """

    name: RecorderCommandName
    flow_id: str | None = None
    milliseconds: int | None = None
    width: int | None = None
    height: int | None = None
    scale: float | None = None
    device_mode: str | None = None
    capture_images: bool | None = None
    recording_group_id: str | None = None
    recording_start_ms: int = 0

    @classmethod
    def record(
        cls,
        *,
        flow_id: str,
        device_mode: str,
        capture_images: bool,
        recording_group_id: str | None = None,
        recording_start_ms: int = 0,
    ) -> Self:
        """Return record.

        Args:
            flow_id: Flow id.
            device_mode: Device mode.
            capture_images: Capture images.
            recording_group_id: Persisted parent of captured actions.
            recording_start_ms: Parent offset on the authored flow timeline.

        Returns:
            The resulting value.

        """
        return cls(
            name=RecorderCommandName.RECORD,
            flow_id=flow_id,
            device_mode=device_mode,
            capture_images=capture_images,
            recording_group_id=recording_group_id,
            recording_start_ms=recording_start_ms,
        )

    @classmethod
    def pause(cls, *, flow_id: str) -> Self:
        """Return pause.

        Args:
            flow_id: Flow id.

        Returns:
            The resulting value.

        """
        return cls(name=RecorderCommandName.PAUSE, flow_id=flow_id)

    @classmethod
    def wait(cls, *, flow_id: str, milliseconds: int) -> Self:
        """Return wait.

        Args:
            flow_id: Flow id.
            milliseconds: Milliseconds.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if milliseconds <= 0:
            msg: str = "Wait duration must be positive."
            raise ValueError(msg)
        return cls(
            name=RecorderCommandName.WAIT,
            flow_id=flow_id,
            milliseconds=milliseconds,
        )

    @classmethod
    def viewport(
        cls,
        *,
        flow_id: str,
        viewport: ViewportSize,
        device_mode: str,
    ) -> Self:
        """Return viewport.

        Args:
            flow_id: Flow id.
            viewport: Logical browser dimensions.
            device_mode: Device mode.

        Returns:
            The resulting value.

        """
        return cls(
            name=RecorderCommandName.VIEWPORT,
            flow_id=flow_id,
            width=viewport.width,
            height=viewport.height,
            scale=1.0,
            device_mode=device_mode,
        )

    @classmethod
    def active_flow(cls, *, flow_id: str) -> Self:
        """Return active flow.

        Args:
            flow_id: Flow id.

        Returns:
            The resulting value.

        """
        return cls(name=RecorderCommandName.ACTIVE_FLOW, flow_id=flow_id)
