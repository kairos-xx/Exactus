# Copyright (c) 2026 Project contributors
"""Keep synchronous Playwright objects on one service-owned worker thread."""

from __future__ import annotations

from asyncio import run as run_async
from base64 import b64decode
from contextlib import suppress
from json import loads
from queue import Empty, Queue
from threading import Event as StopEvent
from threading import Thread
from time import monotonic, time
from typing import TYPE_CHECKING, Final, Protocol, cast, final
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

from exactus.tools.actions.runner import run_actions, validate_actions
from exactus.tools.record.action_recorder import (
    ActionRecorder,
    RecorderOptions,
)
from exactus.tools.record.click_explorer import CaptureVariant, ExplorerOptions
from exactus.tools.record.discovery import CrawlRequest, discover
from exactus.tools.record.flow_runner import (
    EvidenceRequest,
    FlowRunner,
    capture_evidence,
)
from exactus.tools.record.model import Profile, default_profiles
from exactus.tools.record.profile_emulation import (
    ProfileEmulator,
    context_options,
)
from exactus.tools.record.recorder_protocol import RecorderProtocol
from exactus.tools.record.run_gate import RunGate
from exactus.tools.record.store import WorkspaceCodec
from exactus.tools.record.studio.selector_commands import run_selector_test
from exactus.tools.record.studio.target_inspection import inspect_target
from exactus.tools.record.workspace_actions import action_event, bridge_event

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from urllib.parse import SplitResult

    from exactus.tools.record.action_recorder import Action
    from exactus.tools.record.execution import FlowDispatchRequest
    from exactus.tools.record.model import RecorderCommand
    from exactus.tools.record.store import JsonValue
    from exactus.tools.record.workspace_actions import Event


@final
class Constants:
    """Group module-level constants.

    Attributes:
        watch_seconds: Grouped module constant.
        refresh_seconds: Grouped module constant.
        refresh_timeout_ms: Grouped module constant.

    """

    watch_seconds: Final[float] = 5.0
    refresh_seconds: Final[float] = 1.5
    refresh_timeout_ms: Final[int] = 1500


class ScreencastSession(Protocol):
    """Describe the typed subset of Chromium's live-frame transport."""

    def send(self, *, method: str, params: dict[str, JsonValue]) -> JsonValue:
        """Send a screencast method.

        Args:
            method: Chromium method name.
            params: JSON method arguments.

        Returns:
            Chromium method result.

        """
        ...

    def on(
        self,
        *,
        event: str,
        f: Callable[[dict[str, JsonValue]], None],
    ) -> None:
        """Subscribe to screencast frames.

        Args:
            event: Chromium event name.
            f: Frame callback on the owning thread.

        """
        ...


def validate_target_url(*, url: str) -> str:
    """Allow web targets and the initial blank document.

    Args:
        url: User-supplied target URL.

    Returns:
        Validated URL.

    Raises:
        ValueError: When the scheme or destination is unsupported.

    """
    parsed: SplitResult = urlsplit(url=url)
    if url != "about:blank" and (
        parsed.scheme not in {"http", "https"} or not parsed.hostname
    ):
        msg: str = "Use an http:// or https:// target URL."
        raise ValueError(msg)
    if parsed.username or parsed.password:
        msg = "Use the target login form instead of URL credentials."
        raise ValueError(msg)
    return url


class BrowserWorker(Protocol):
    """Describe the controller's browser command boundary."""

    def actions(
        self,
        *,
        specification: dict[str, JsonValue],
        root: Path,
    ) -> None:
        """Run a declarative tool recipe.

        Args:
            specification: Validated tool calls.
            root: Project base for entrypoint resolution.

        """
        ...

    def crawl(self, *, request: CrawlRequest) -> None:
        """Start bounded discovery of the target URL.

        Args:
            request: Target, limits and action policy.

        """
        ...

    def broadcast(self, *, command: RecorderCommand) -> None:
        """Queue recording control.

        Args:
            command: Validated recorder command.

        """
        ...

    def broadcast_dispatch(self, *, request: FlowDispatchRequest) -> None:
        """Queue flow execution.

        Args:
            request: Immutable flow dispatch.

        """
        ...

    def navigate(self, *, value: str) -> None:
        """Queue navigation.

        Args:
            value: Target URL.

        """
        ...

    def set_profile(self, *, profile: Profile) -> None:
        """Apply the browser conditions the target is shown under.

        Args:
            profile: Viewport, device and media conditions.

        """
        ...

    def open_target(self, *, url: str) -> None:
        """Open an owned browser.

        Args:
            url: Initial target URL.

        """
        ...

    def input_target(self, *, message: Event) -> None:
        """Queue validated input for the visible managed page.

        Args:
            message: Pointer, wheel or keyboard input.

        """
        ...

    def close_target(self) -> None:
        """Close the owned target context."""
        ...

    def set_output(self, *, output: Path) -> None:
        """Move evidence to another project's directory.

        Args:
            output: Evidence directory of the project now open.

        """
        ...

    def select_target(self, *, page_id: str) -> None:
        """Choose an owned page.

        Args:
            page_id: Stable managed page identifier.

        """
        ...

    def cancel(self) -> None:
        """Signal cancellation outside the Playwright thread."""
        ...

    def pause_run(self) -> None:
        """Hold the running flow before its next action."""
        ...

    def resume_run(self) -> None:
        """Let a held flow continue without stopping again."""
        ...

    def step_run(self) -> None:
        """Let a held flow run exactly one more action."""
        ...


class ManagedBrowserWorker:
    """Own browser lifetime and process one bounded command queue.

    Attributes:
        emit: Serialized controller callback receiving worker messages.

    """

    def __init__(self, *, output: Path, headless: bool = False) -> None:
        """Configure a lazy target without launching a browser.

        Args:
            output: Service-owned evidence directory.
            headless: Use headless Chromium for unattended environments.

        """
        self.emit: Callable[[Event], None] = self._discard
        self._output: Path = output
        self._headless: bool = headless
        self._preview: bytes = b""
        self._preview_at: float | None = None
        self._watched_at: float = 0.0
        self._queue: Queue[Event] = Queue(maxsize=32)
        self._queued_run_id: str | None = None
        self._crawl_thread: Thread | None = None
        self._stop: StopEvent = StopEvent()
        self._cancel: StopEvent = StopEvent()
        self._gate: RunGate = RunGate()
        self._thread: Thread = Thread(
            target=self._run,
            name="studio-browser",
            daemon=True,
        )
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._pages: dict[str, Page] = {}
        self._sessions: dict[Page, ScreencastSession] = {}
        self._touches: dict[int, dict[str, JsonValue]] = {}
        self._recording: bool = False
        self._recording_group_id: str | None = None
        self._recording_flow_id: str = "flow-1"
        self._recording_origin: float = 0.0
        self._recording_epoch_ms: float = 0.0
        self._recording_accumulated_ms: int = 0
        self._recording_start_ms: int = 0
        self._flow_id: str = "flow-1"
        self._capture_images: bool = False
        self._captures: list[tuple[str, str]] = []
        self._profile: Profile = default_profiles()[0]
        self._reopening: bool = False
        self._emulator: ProfileEmulator = ProfileEmulator()
        self._viewport: dict[str, int] = {
            "width": self._profile.width,
            "height": self._profile.height,
        }
        self._recorder: ActionRecorder = ActionRecorder(
            options=RecorderOptions(url="about:blank", output=output),
            on_action=self._forward,
        )

    @property
    def preview(self) -> bytes:
        """Return the newest preview frame.

        Returns:
            JPEG bytes, or empty bytes when no frame exists.

        """
        self._watched_at = monotonic()
        return self._preview

    @preview.setter
    def preview(self, frame: bytes) -> None:
        """Retain a frame and remember when it arrived.

        Args:
            frame: JPEG bytes, or empty bytes to clear the preview.

        """
        self._preview = frame
        self._preview_at = monotonic() if frame else None

    @property
    def preview_age_ms(self) -> int | None:
        """Return how old the preview frame is, or None without a frame.

        Returns:
            Preview age in milliseconds, or None without a frame.

        """
        self._watched_at = monotonic()
        if self._preview_at is None:
            return None
        return int((monotonic() - self._preview_at) * 1000)

    def start(self) -> None:
        """Start the sole owning Playwright thread."""
        self._thread.start()

    def stop(self) -> None:
        """Cancel operations and close only service-owned browser resources."""
        self._stop.set()
        self._cancel.set()
        self._thread.join(timeout=10)
        if self._crawl_thread is not None:
            self._crawl_thread.join(timeout=10)

    def cancel(self) -> None:
        """Signal cooperative cancellation; no cross-thread browser calls."""
        self._cancel.set()
        self._gate.reset()

    def pause_run(self) -> None:
        """Hold the running flow before its next action."""
        self._gate.pause()

    def resume_run(self) -> None:
        """Let a held flow continue without stopping again."""
        self._gate.resume()

    def step_run(self) -> None:
        """Let a held flow run exactly one more action."""
        self._gate.step()

    def broadcast(self, *, command: RecorderCommand) -> None:
        """Queue an encoded domain recorder command.

        Args:
            command: Validated command.

        """
        self._queue.put_nowait(
            item=cast(
                typ="Event",
                val=loads(s=RecorderProtocol.encode_command(command=command)),
            ),
        )

    def broadcast_dispatch(self, *, request: FlowDispatchRequest) -> None:
        """Queue immutable execution inputs.

        Args:
            request: Current flow and runtime variables.

        """
        if request.run_id != self._queued_run_id:
            self._cancel.clear()
            self._queued_run_id = request.run_id
        self._queue.put_nowait(
            item=cast(
                typ="Event",
                val=loads(
                    s=RecorderProtocol.encode_dispatch_request(
                        request=request,
                    ),
                ),
            ),
        )

    def navigate(self, *, value: str) -> None:
        """Queue validated navigation without changing the editor page.

        Args:
            value: User-selected target URL.

        """
        self._queue.put_nowait(
            item={"type": "navigate", "url": validate_target_url(url=value)},
        )

    def set_profile(self, *, profile: Profile) -> None:
        """Queue a change of the conditions the target is shown under.

        Args:
            profile: Viewport, device and media conditions.

        """
        self._queue.put_nowait(
            item={
                "type": "profile",
                "profile": WorkspaceCodec.profile_to_json(profile=profile),
            },
        )

    def open_target(self, *, url: str) -> None:
        """Queue a new isolated browser context.

        Args:
            url: Initial target destination.

        """
        self._queue.put_nowait(
            item={"type": "open", "url": validate_target_url(url=url)},
        )

    def close_target(self) -> None:
        """Queue closure of the managed context."""
        self._cancel.set()
        self._queue.put_nowait(item={"type": "close"})

    def set_output(self, *, output: Path) -> None:
        """Move evidence to another project's directory.

        Args:
            output: Evidence directory of the project now open.

        """
        self._output = output
        self._recorder = ActionRecorder(
            options=RecorderOptions(url="about:blank", output=output),
            on_action=self._forward,
        )

    def input_target(self, *, message: Event) -> None:
        """Forward a validated live-panel input on the browser owning thread.

        Args:
            message: Validated pointer, wheel or keyboard input.

        """
        self._queue.put_nowait(item={**message, "type": "input"})

    def select_target(self, *, page_id: str) -> None:
        """Queue active-page selection within the managed context.

        Args:
            page_id: Page identifier from the target snapshot.

        """
        self._queue.put_nowait(item={"type": "select", "page_id": page_id})

    def actions(
        self,
        *,
        specification: dict[str, JsonValue],
        root: Path,
    ) -> None:
        """Execute an Actions recipe on the owned discovery thread.

        Args:
            specification: Tool calls and named output references.
            root: Project base for entrypoints.

        """
        specification = validate_actions(value=specification)
        self._cancel.clear()

        def execute() -> None:
            """Run the validated action specification to completion."""
            try:
                run_actions(
                    specification=specification,
                    root=root,
                    output=self._output / "actions",
                    cancelled=self._cancel.is_set,
                    emit=self.emit,
                )
            except (
                PlaywrightError,
                ValueError,
                OSError,
                RuntimeError,
                KeyError,
            ) as error:
                self.emit(
                    {
                        "type": "actions_state",
                        "state": "failed",
                        "error": str(object=error),
                    },
                )

        self._crawl_thread = Thread(
            target=execute,
            name="studio-actions",
            daemon=True,
        )
        self._crawl_thread.start()

    def crawl(self, *, request: CrawlRequest) -> None:
        """Launch the existing explorer with cancellable progress.

        Args:
            request: Target, limits and action policy.

        Raises:
            ValueError: When the arguments are invalid.

        """
        validated: str = validate_target_url(url=request.url)
        if validated == "about:blank":
            msg: str = "Enter a target URL before crawling."
            raise ValueError(msg)
        self._cancel.clear()

        def explore() -> None:
            """Crawl the validated target and capture discovered flows."""
            try:
                run_async(
                    main=discover(
                        options=ExplorerOptions(
                            url=validated,
                            output=self._output / "crawl",
                            width=self._viewport["width"],
                            height=self._viewport["height"],
                            max_depth=request.max_depth,
                            max_states=request.max_states,
                            workers=1,
                            capture_ui_changes=request.capture_ui_changes,
                            follow_links=request.follow_links,
                            click_controls=request.click_controls,
                            include_selector=request.include_selector,
                            variant=CaptureVariant(
                                name="studio",
                                width=self._viewport["width"],
                                height=self._viewport["height"],
                                color_scheme="dark"
                                if ("prefers-color-scheme", "dark")
                                in self._profile.media
                                else "light",
                                is_mobile=self._profile.mobile,
                                has_touch=self._profile.touch,
                                scale=self._profile.scale,
                            ),
                        ),
                        cancelled=self._cancel.is_set,
                        emit=self.emit,
                    ),
                )
            except (PlaywrightError, ValueError, OSError) as error:
                self.emit(
                    {
                        "type": "crawl_state",
                        "state": "failed",
                        "error": str(object=error),
                    },
                )

        self._crawl_thread = Thread(
            target=explore,
            name="studio-discovery",
            daemon=True,
        )
        self._crawl_thread.start()

    def select_page_for_test(self, *, page: Page) -> None:
        """Mark a page active without launching a browser.

        Args:
            page: Page that should own accepted preview frames.

        """
        self._page = page

    def accept_frame(
        self,
        *,
        page: Page,
        session: ScreencastSession,
        message: dict[str, JsonValue],
    ) -> None:
        """Keep a frame only when it matches the active page and viewport.

        Every frame is acknowledged, including rejected ones, because Chromium
        stops sending frames until the previous one is acknowledged.

        Args:
            page: Page that produced the frame.
            session: Chromium session that receives the acknowledgement.
            message: Chromium screencast frame and acknowledgement token.

        """
        metadata: JsonValue = message.get("metadata")
        matches_viewport: bool = (
            isinstance(metadata, dict)
            and metadata.get("deviceWidth") == self._viewport["width"]
            and (metadata.get("deviceHeight") == self._viewport["height"])
        )
        if self._page == page and matches_viewport:
            self.preview = b64decode(s=str(object=message["data"]))
        session.send(
            method="Page.screencastFrameAck",
            params={"sessionId": message["sessionId"]},
        )

    @staticmethod
    def _discard(message: Event) -> None:
        """Discard callbacks until the controller is attached.

        Args:
            message: Worker lifecycle or domain event.

        """
        _ = message

    @staticmethod
    def _keyboard_input(*, page: Page, action: str, message: Event) -> None:
        """Dispatch one keyboard action to the managed page.

        Args:
            page: Active managed target.
            action: ``key``, ``key_down`` or ``key_up``.
            message: Validated keyboard input.

        """
        if action == "key":
            key: str = str(object=message["key"])
            if len(key) == 1:
                page.keyboard.insert_text(text=key)
            else:
                page.keyboard.press(key=key)
            return
        held: str = str(object=message.get("code") or message["key"])
        if action == "key_down":
            page.keyboard.down(key=held)
        else:
            page.keyboard.up(key=held)

    def _forward(self, action: Action) -> None:
        """Forward selector-based recording while excluding replay actions.

        Args:
            action: Raw recorded target action.

        """
        if not self._recording:
            return
        if action.get("type") in {"focus", "wheel"}:
            return
        timestamp: JsonValue = action.get("timestamp")
        relative_ms: int = max(
            0,
            round(number=(monotonic() - self._recording_origin) * 1000),
        )
        if isinstance(timestamp, (int, float)):
            if timestamp < self._recording_epoch_ms:
                return
            relative_ms = round(number=timestamp - self._recording_epoch_ms)
        event: Event | None = action_event(action=action, event_id=uuid4().hex)
        if event is None:
            self.emit(
                {
                    "type": "worker_error",
                    "error": (
                        "This action cannot be represented as a "
                        "selector-based step."
                    ),
                },
            )
            return
        event["elapsed_ms"] = (
            self._recording_start_ms
            + self._recording_accumulated_ms
            + relative_ms
        )
        event["recording_group_id"] = self._recording_group_id
        self.emit(bridge_event(event=event, flow_id=self._recording_flow_id))
        if self._capture_images:
            self._captures.append(
                (self._recording_flow_id, str(object=event["id"])),
            )

    def _state(self, *, state: str) -> None:
        """Publish target identity and actual CSS viewport dimensions.

        Args:
            state: Target lifecycle state.

        """
        if self._reopening and state in {"closed", "opening"}:
            return
        self.emit(
            cast(
                typ="Event",
                val={
                    "type": "target_state",
                    "state": state,
                    "url": self._page.url
                    if self._page and (not self._page.is_closed())
                    else "about:blank",
                    "pages": [
                        {"id": name, "url": page.url}
                        for name, page in self._pages.items()
                        if not page.is_closed()
                    ],
                    "viewport": dict(self._viewport),
                },
            ),
        )

    def _attach(self, page: Page) -> None:
        """Install recorder hooks once and select a newly opened popup.

        Args:
            page: Page in the exclusively managed context.

        """
        if page in self._pages.values():
            return
        self._pages[uuid4().hex] = page
        self._page = page
        self._recorder.instrument(page=page)
        self._emulator.apply(page=page, profile=self._profile)
        session: ScreencastSession = cast(
            typ="ScreencastSession",
            val=page.context.new_cdp_session(page=page),
        )
        self._sessions[page] = session
        session.on(
            event="Page.screencastFrame",
            f=lambda message: self.accept_frame(
                page=page,
                session=session,
                message=message,
            ),
        )
        session.send(
            method="Page.startScreencast",
            params={
                "format": "jpeg",
                "quality": 75,
                "maxWidth": 1440,
                "maxHeight": 1440,
                "everyNthFrame": 1,
            },
        )
        page.on(event="dialog", f=lambda dialog: dialog.dismiss())
        page.on(event="close", f=lambda closed: self._closed_page(page=closed))
        page.on(
            event="framenavigated",
            f=lambda _frame: self._state(state="ready"),
        )
        self._state(state="ready")

    def _closed_page(self, *, page: Page) -> None:
        """Recover active target selection after a page closes.

        Args:
            page: Closed owned page.

        """
        self._sessions.pop(page, None)
        if self._page == page:
            self._page = next(
                (
                    item
                    for item in self._pages.values()
                    if not item.is_closed()
                ),
                None,
            )
        if self._page is None:
            self._recording = False
        self._state(state="ready" if self._page is not None else "closed")

    def _close(self) -> None:
        """Release only the browser and context launched by this worker."""
        self._recording = False
        if self._browser:
            with suppress(PlaywrightError):
                self._browser.close()
        self._browser = None
        self._context = None
        self._page = None
        self._pages.clear()
        self._sessions.clear()
        self._touches.clear()
        self._emulator.release()
        self.preview = b""
        self._state(state="closed")

    def _handle(self, *, message: Event) -> None:
        """Apply commands only on the owning thread.

        Args:
            message: Queue message.

        Raises:
            ValueError: When no suitable target is available.

        """
        kind: JsonValue = message.get("type")
        if kind == "close":
            self._close()
            return
        page: Page | None = self._page
        if page is None or page.is_closed():
            msg: str = "Open the managed test browser first."
            raise ValueError(msg)
        if kind == "navigate":
            _ = page.goto(url=str(object=message["url"]), timeout=5000)
            self.preview = page.screenshot(
                type="jpeg",
                quality=75,
                timeout=5000,
            )
            self._state(state="ready")
        elif kind == "input":
            self._input(page=page, message=message)
        elif kind == "select":
            selected: Page | None = self._pages.get(
                str(object=message["page_id"]),
            )
            if selected is None or selected.is_closed():
                msg = "Target page is no longer available."
                raise ValueError(msg)
            self._page = selected
            self._state(state="ready")
        elif kind == "command":
            self._command(page=page, message=message)
        elif kind == "execute_flow":
            self._execute_flow(page=page, message=message)

    def _input(self, *, page: Page, message: Event) -> None:
        """Execute live view input on the same page the recorder instruments.

        Args:
            page: Active managed target.
            message: Validated input and target CSS coordinates.

        """
        action: JsonValue = message.get("action")
        if action == "selector_test":
            self.emit(
                {
                    "type": "selector_test",
                    "result": run_selector_test(page=page, message=message),
                },
            )
        elif action == "inspect":
            self.emit(
                {
                    "type": "target_inspection",
                    "element": inspect_target(
                        page=page,
                        x=float(str(object=message["x"])),
                        y=float(str(object=message["y"])),
                    ),
                    "picked": message.get("picked") is True,
                },
            )
        elif action == "click":
            page.mouse.click(
                x=float(str(object=message["x"])),
                y=float(str(object=message["y"])),
            )
        elif action == "wheel":
            page.mouse.move(
                x=float(str(object=message["x"])),
                y=float(str(object=message["y"])),
            )
            page.mouse.wheel(
                delta_x=float(str(object=message["dx"])),
                delta_y=float(str(object=message["dy"])),
            )
        elif (
            action in {"pointer_down", "pointer_move", "pointer_up"}
            or action == "pointer_leave"
        ):
            self._pointer_input(page=page, message=message)
        elif action in {
            "touch_cancel",
            "touch_end",
            "touch_move",
            "touch_start",
        }:
            self._touch_input(page=page, message=message)
        elif action in {"key", "key_down", "key_up"}:
            self._keyboard_input(
                page=page,
                action=str(object=action),
                message=message,
            )

    def _pointer_input(self, *, page: Page, message: Event) -> None:
        """Dispatch exact pointer lifecycle input through Chromium.

        Args:
            page: Active managed page.
            message: Validated pointer input.

        """
        session: ScreencastSession | None = self._sessions.get(page)
        if session is None:
            return
        action: str = str(object=message["action"])
        event_type: str = {
            "pointer_down": "mousePressed",
            "pointer_leave": "mouseMoved",
            "pointer_move": "mouseMoved",
            "pointer_up": "mouseReleased",
        }[action]
        button_number: int = int(str(object=message.get("button", -1)))
        button: str = {
            0: "left",
            1: "middle",
            2: "right",
            3: "back",
            4: "forward",
        }.get(button_number, "none")
        session.send(
            method="Input.dispatchMouseEvent",
            params={
                "type": event_type,
                "x": float(str(object=message.get("x", -1))),
                "y": float(str(object=message.get("y", -1))),
                "button": button,
                "buttons": int(str(object=message.get("buttons", 0))),
                "pointerType": "mouse",
            },
        )

    def _touch_input(self, *, page: Page, message: Event) -> None:
        """Dispatch one contact while retaining the complete touch gesture.

        Args:
            page: Active managed page.
            message: Validated contact update.

        """
        session: ScreencastSession | None = self._sessions.get(page)
        if session is None:
            return
        action: str = str(object=message["action"])
        pointer_id: int = int(str(object=message["pointer_id"]))
        if action in {"touch_start", "touch_move"}:
            self._touches[pointer_id] = {
                "id": pointer_id,
                "x": float(str(object=message["x"])),
                "y": float(str(object=message["y"])),
                "radiusX": 1,
                "radiusY": 1,
                "force": 1,
            }
        else:
            self._touches.pop(pointer_id, None)
        touch_type: str = {
            "touch_cancel": "touchCancel",
            "touch_end": "touchEnd",
            "touch_move": "touchMove",
            "touch_start": "touchStart",
        }[action]
        touch_points: list[JsonValue] = list(self._touches.values())
        session.send(
            method="Input.dispatchTouchEvent",
            params={"type": touch_type, "touchPoints": touch_points},
        )

    def _command(self, *, page: Page, message: Event) -> None:
        """Apply a recorder command on the owning thread.

        Args:
            page: Active managed page.
            message: Queue message.

        """
        name: JsonValue = message.get("name")
        self._flow_id = str(object=message.get("flow_id") or self._flow_id)
        if name == "record":
            if self._recording:
                return
            group_id: str | None = (
                str(object=message["recording_group_id"])
                if message.get("recording_group_id")
                else None
            )
            fresh: bool = (
                group_id is None or group_id != self._recording_group_id
            )
            if fresh:
                self._recording_group_id = group_id
                self._recording_flow_id = self._flow_id
                self._recording_accumulated_ms = 0
                self._recording_start_ms = int(
                    str(object=message.get("recording_start_ms") or 0),
                )
            self._recording_origin = monotonic()
            self._recording_epoch_ms = time() * 1000
            self._capture_images = message.get("capture_images") is True
            self._recording = True
            if fresh:
                self._forward(action={"type": "navigation", "url": page.url})
        elif name == "pause":
            if self._recording:
                page.evaluate(
                    expression=(
                        "document.dispatchEvent("
                        "new Event('__EXACTUS_RECORDER_FLUSH__'))"
                    ),
                )
                self._recording_accumulated_ms += max(
                    0,
                    round(
                        number=(monotonic() - self._recording_origin) * 1000,
                    ),
                )
            self._recording = False

    def _execute_flow(self, *, page: Page, message: Event) -> None:
        """Replay a validated flow on the owning thread.

        Args:
            page: Active managed page.
            message: Queue message.

        """
        self._recording = False
        runner: FlowRunner = FlowRunner(
            output=self._output,
            emit=self.emit,
            cancelled=self._cancel.is_set,
            after_capture=self._restore_device,
        )
        runner.gate = self._gate
        self.emit(runner.run(page=page, message=message))

    def _keep_preview_fresh(self, page: Page) -> None:
        """Renew a watched preview that has not changed for a while.

        Chromium sends a frame only when the page changes, so a still page
        would otherwise look stale. A real screenshot with a short timeout
        proves the page still responds; a hung page fails it and ages.

        Args:
            page: Active managed page.

        """
        now: float = monotonic()
        if now - self._watched_at > Constants.watch_seconds:
            return
        if (
            self._preview_at is not None
            and now - self._preview_at < Constants.refresh_seconds
        ):
            return
        with suppress(PlaywrightError):
            self.preview = page.screenshot(
                type="jpeg",
                quality=75,
                timeout=Constants.refresh_timeout_ms,
            )

    def _restore_device(self, page: Page) -> None:
        """Re-assert touch emulation after the page was captured.

        Args:
            page: Page that was just captured.

        """
        self._emulator.restore(page=page, profile=self._profile)

    def _launch(
        self,
        *,
        playwright: Playwright,
        url: str,
        reopening: bool = False,
    ) -> None:
        """Open a fresh browser under the current profile and show a page.

        Args:
            playwright: Playwright driver owned by the worker thread.
            url: Destination to open.
            reopening: Replace a running browser without announcing that the
                target closed, so a queued run or recording is not cancelled.

        """
        self._reopening = reopening
        try:
            self._close()
            self._state(state="opening")
            self._browser = playwright.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(
                **context_options(profile=self._profile),
                accept_downloads=True,
            )
            self._context.on(event="page", f=self._attach)
            self._page = self._context.new_page()
            self._handle(message={"type": "navigate", "url": url})
        finally:
            self._reopening = False

    def _apply_profile(
        self,
        *,
        playwright: Playwright,
        profile: Profile,
    ) -> None:
        """Show the target under a different profile.

        Size and media changes apply to the open page. A different pixel
        density, screen, touch or mobile setting only exists at context
        creation, so the target is reopened at the same address.

        Args:
            playwright: Playwright driver owned by the worker thread.
            profile: Conditions to show the target under.

        """
        previous: Profile = self._profile
        self._profile = profile
        self._viewport = {"width": profile.width, "height": profile.height}
        page: Page | None = self._page
        if page is None or page.is_closed():
            return
        if previous.device_settings != profile.device_settings:
            self._launch(playwright=playwright, url=page.url, reopening=True)
            return
        page.set_viewport_size(
            viewport_size={"width": profile.width, "height": profile.height},
        )
        for owned in self._pages.values():
            if not owned.is_closed():
                self._emulator.apply(page=owned, profile=profile)
        self._state(state="ready")

    def _dispatch(self, *, playwright: Playwright, message: Event) -> None:
        """Route one queued command to the browser-owning handlers.

        Args:
            playwright: Playwright driver owned by the worker thread.
            message: Queue message.

        """
        kind: JsonValue = message.get("type")
        if kind == "open":
            if self._page and (not self._page.is_closed()):
                self._handle(
                    message={"type": "navigate", "url": message["url"]},
                )
            else:
                self._launch(
                    playwright=playwright,
                    url=str(object=message["url"]),
                )
        elif kind == "profile":
            self._apply_profile(
                playwright=playwright,
                profile=WorkspaceCodec.parse_profile(value=message["profile"]),
            )
        else:
            self._handle(message=message)

    def _run(self) -> None:
        """Run the owning event loop and clean up on every exit path."""
        try:
            with sync_playwright() as playwright:
                while not self._stop.is_set():
                    try:
                        message: Event | None = self._queue.get(timeout=0.025)
                    except Empty:
                        message = None
                    try:
                        if message is not None:
                            self._dispatch(
                                playwright=playwright,
                                message=message,
                            )
                        page: Page | None = self._page
                        if page and (not page.is_closed()):
                            queued, self._captures = (self._captures, [])
                            for flow_id, event_id in queued:
                                self.emit(
                                    capture_evidence(
                                        page=page,
                                        output=self._output,
                                        request=EvidenceRequest(
                                            flow_id=flow_id,
                                            event_id=event_id,
                                            phase="record",
                                            after_capture=self._restore_device,
                                        ),
                                    ),
                                )
                            self._keep_preview_fresh(page=page)
                            page.wait_for_timeout(timeout=20)
                    except (PlaywrightError, ValueError, OSError) as error:
                        self.emit(
                            {
                                "type": "worker_error",
                                "error": str(object=error),
                            },
                        )
                        if self._page is None or self._page.is_closed():
                            self._state(state="failed")
        finally:
            self._close()
