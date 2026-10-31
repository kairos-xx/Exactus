#!/usr/bin/env python3
# Copyright (c) 2026
"""Record, normalize, compile, and replay interactive Playwright actions."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from importlib.resources import files as resource_files
from json import dumps, loads
from time import monotonic
from typing import TYPE_CHECKING, Final, Literal, Protocol, cast, final

from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Locator,
    Page,
    Playwright,
    Response,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

from exactus.tools.record.sprint import sprint

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type Action = dict[str, JsonValue]


class _Emitter(Protocol):
    """Typed source-code emitter for one semantic browser action."""

    def __call__(self, action: Action, locator: str) -> str | None:
        """Compile an action using its resolved locator expression.

        Args:
            action: Normalized browser action.
            locator: Locator expression in the target programming language.

        Returns:
            Replay statement, or None for unsupported actions.

        """
        ...


class _Performer(Protocol):
    """Typed runtime action handler for functional replay."""

    def __call__(
        self,
        page: Page,
        action: Action,
        locator: Locator | None,
    ) -> None:
        """Perform one recorded action on the current browser page.

        Args:
            page: Browser page receiving the action.
            action: Normalized browser action.
            locator: Resolved element, or None for page-level actions.

        """
        ...


def _script_source() -> str:
    """Return the injected browser recorder's source text.

    Resolved through ``importlib.resources`` so the recorder keeps working
    when the package executes from a pyz archive, where ``Path(__file__)``
    does not address real files.

    Returns:
        Contents of ``action_recorder.js``.

    """
    return (
        resource_files("exactus.tools.record")
        .joinpath("action_recorder.js")
        .read_text(encoding="utf-8")
    )


@dataclass(frozen=True, slots=True)
class RecorderOptions:
    """Configure one interactive recording session.

    Attributes:
        url: Absolute URL to open in the headed recorder.
        output: Directory receiving the generated replay artifacts.
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        timeout_ms: Initial navigation timeout in milliseconds.
        preserve_timing: Emit recorded inter-action delays in generated
            programs.

    """

    url: str
    output: Path
    width: int = 1440
    height: int = 1000
    timeout_ms: float = 5000.0
    preserve_timing: bool = False


@dataclass(frozen=True, slots=True)
class ReplayOptions:
    """Configure one replay session.

    Attributes:
        width: Viewport width in CSS pixels.
        height: Viewport height in CSS pixels.
        headless: Whether to replay without a visible browser window.
        timeout_ms: Per-action Playwright timeout in milliseconds.

    """

    width: int = 1440
    height: int = 1000
    headless: bool = False
    timeout_ms: float = 30000.0


class LocatorCompiler:
    """Compile structured locator candidates into Playwright syntax."""

    @classmethod
    def python(cls, *, target: Action) -> str:
        """Compile the strongest target locator to Python Playwright.

        Args:
            target: Recorded action target carrying locator candidates.

        Returns:
            A ``page`` expression locating the element.

        """
        candidate: Action | None = cls.candidate(target=target)
        if candidate is None:
            return 'page.locator("body")'
        kind: str = str(object=candidate.get("kind", "css"))
        value: JsonValue = candidate.get("value")
        if kind == "test_id":
            return f"page.get_by_test_id({dumps(obj=value)})"
        if kind == "role":
            return (
                f"page.get_by_role({dumps(obj=candidate.get('role'))}, name={
                    dumps(obj=candidate.get('name'))
                }, "
                f"exact=True)"
            )
        if kind == "label":
            return f"page.get_by_label({dumps(obj=value)}, exact=True)"
        if kind == "placeholder":
            return f"page.get_by_placeholder({dumps(obj=value)}, exact=True)"
        return f"page.locator({dumps(obj=value)})"

    @classmethod
    def javascript(cls, *, target: Action) -> str:
        """Compile the strongest target locator to JavaScript Playwright.

        Args:
            target: Recorded action target carrying locator candidates.

        Returns:
            A ``page`` expression locating the element.

        """
        candidate: Action | None = cls.candidate(target=target)
        if candidate is None:
            return 'page.locator("body")'
        kind: str = str(object=candidate.get("kind", "css"))
        value: JsonValue = candidate.get("value")
        if kind == "test_id":
            return f"page.getByTestId({dumps(obj=value)})"
        if kind == "role":
            return (
                f"page.getByRole({dumps(obj=candidate.get('role'))}, {{name: {
                    dumps(obj=candidate.get('name'))
                }, exact: "
                f"true}})"
            )
        if kind == "label":
            return f"page.getByLabel({dumps(obj=value)}, {{exact: true}})"
        if kind == "placeholder":
            return (
                f"page.getByPlaceholder({dumps(obj=value)}, {{exact: true}})"
            )
        return f"page.locator({dumps(obj=value)})"

    @staticmethod
    def candidate(*, target: Action) -> Action | None:
        """Return the strongest recorded locator candidate, if any.

        Args:
            target: Recorded action target carrying locator candidates.

        Returns:
            The first locator candidate, or ``None``.

        """
        locators: JsonValue = target.get("locators")
        if not isinstance(locators, list) or not locators:
            return None
        first: JsonValue = locators[0]
        return (
            cast(typ="Action", val=first) if isinstance(first, dict) else None
        )


class ActionNormalizer:
    """Collapse noisy raw browser events into semantic replay actions."""

    @classmethod
    def normalize(cls, *, actions: Sequence[Action]) -> list[Action]:
        """Normalize, deduplicate, and collapse replaceable actions.

        Args:
            actions: Raw recorded actions in chronological order.

        Returns:
            Deduplicated semantic replay program.

        """
        normalized: list[Action] = []
        for action in actions:
            kind: str = str(object=action.get("type", ""))
            if kind in {"focus", "wheel"}:
                continue
            signature: str = cls._signature(action=action)
            if normalized:
                previous: Action = normalized[-1]
                previous_kind: str = str(object=previous.get("type", ""))
                if (
                    kind == "double_click"
                    and previous_kind == "click"
                    and (previous.get("target") == action.get("target"))
                ):
                    normalized[-1] = action
                    continue
                previous_signature: str = cls._signature(action=previous)
                replaceable: bool = (
                    kind in {"fill", "contenteditable", "scroll"}
                    and kind == previous_kind
                    and (signature == previous_signature)
                )
                if replaceable:
                    normalized[-1] = action
                    continue
                if signature == previous_signature and action == previous:
                    continue
            normalized.append(action)
        return normalized

    @staticmethod
    def _signature(*, action: Action) -> str:
        """Render the identity signature used for deduplication.

        Args:
            action: Raw recorded action.

        Returns:
            Canonical JSON signature over the action's identity fields.

        """
        return dumps(
            obj={
                "type": action.get("type"),
                "target": action.get("target"),
                "source": action.get("source"),
                "key": action.get("key"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


class ActionCompiler:
    """Compile normalized semantic actions into runnable source code."""

    @classmethod
    def python(cls, *, action: Action) -> str | None:
        """Compile one semantic action to a Python Playwright statement.

        Args:
            action: Normalized action to compile.

        Returns:
            A Playwright statement, or ``None`` when the action is not
            replayable.

        """
        emitter: _Emitter | None = Constants.python_emitters.get(
            str(object=action.get("type", "")),
        )
        if emitter is None:
            return None
        target: Action | None = cls.target(action=action)
        locator: str = (
            LocatorCompiler.python(target=target) if target else "page"
        )
        return emitter(action=action, locator=locator)

    @classmethod
    def javascript(cls, *, action: Action) -> str | None:
        """Compile one semantic action to a JavaScript Playwright statement.

        Args:
            action: Normalized action to compile.

        Returns:
            A Playwright statement, or ``None`` when the action is not
            replayable.

        """
        emitter: _Emitter | None = Constants.javascript_emitters.get(
            str(object=action.get("type", "")),
        )
        if emitter is None:
            return None
        target: Action | None = cls.target(action=action)
        locator: str = (
            LocatorCompiler.javascript(target=target) if target else "page"
        )
        return emitter(action=action, locator=locator)

    @classmethod
    def write(
        cls,
        *,
        actions: Sequence[Action],
        output: Path,
        preserve_timing: bool = False,
    ) -> None:
        """Write normalized JSON and Python/JavaScript replay programs.

        Args:
            actions: Normalized replay program.
            output: Directory receiving the generated files.
            preserve_timing: Emit recorded inter-action delays.

        """
        output.mkdir(parents=True, exist_ok=True)
        _normalized_written: int = (
            output / "actions.normalized.json"
        ).write_text(
            data=dumps(obj=actions, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        python_lines: list[str] = ["# Generated Playwright actions."]
        js_lines: list[str] = ["// Generated Playwright actions."]
        previous_elapsed: float | None = None
        for action in actions:
            elapsed_value: JsonValue = action.get("elapsedMs")
            elapsed: float | None = (
                float(elapsed_value)
                if isinstance(elapsed_value, (int, float))
                else None
            )
            if (
                preserve_timing
                and previous_elapsed is not None
                and (elapsed is not None)
                and (elapsed > previous_elapsed)
            ):
                delay: int = round(number=elapsed - previous_elapsed)
                python_lines.append(f"page.wait_for_timeout(timeout={delay})")
                js_lines.append(f"await page.waitForTimeout({delay});")
            if (line := cls.python(action=action)) is not None:
                python_lines.append(line)
            if (line := cls.javascript(action=action)) is not None:
                js_lines.append(line)
            if elapsed is not None:
                previous_elapsed = elapsed
        _python_written: int = (output / "actions.py.txt").write_text(
            data="\n".join(python_lines) + "\n",
            encoding="utf-8",
        )
        _javascript_written: int = (output / "actions.mjs.txt").write_text(
            data="\n".join(js_lines) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def target(*, action: Action, key: str = "target") -> Action | None:
        """Return the dict-valued ``key`` entry of ``action``, if any.

        Args:
            action: Normalized action being inspected.
            key: Entry expected to hold a locator-bearing dict.

        Returns:
            The entry as an ``Action``, or ``None``.

        """
        value: JsonValue = action.get(key)
        return (
            cast(typ="Action", val=value) if isinstance(value, dict) else None
        )

    @staticmethod
    def key(*, action: Action) -> str:
        """Render the action's keypress as a ``Mod+Key`` chord.

        Args:
            action: Normalized ``key`` action.

        Returns:
            Playwright key chord such as ``Control+A``.

        """
        modifiers: JsonValue = action.get("modifiers")
        parts: list[str] = []
        if isinstance(modifiers, dict):
            mapping: tuple[tuple[str, str], ...] = (
                ("control", "Control"),
                ("alt", "Alt"),
                ("shift", "Shift"),
                ("meta", "Meta"),
            )
            for name, rendered in mapping:
                if modifiers.get(name) is True:
                    parts.append(rendered)
        key: str = str(object=action.get("key", ""))
        aliases: dict[str, str] = {" ": "Space"}
        parts.append(aliases.get(key, key))
        return "+".join(parts)


def _emit_python_click(action: Action, locator: str) -> str:
    """Compile a click-family action to Python Playwright.

    Args:
        action: Normalized ``click``, ``double_click``, or ``right_click``
            action.
        locator: Compiled Python locator expression.

    Returns:
        Python click statement.

    """
    kind: str = str(object=action.get("type", ""))
    if kind == "double_click":
        return f"{locator}.dblclick()"
    if kind == "right_click":
        return f'{locator}.click(button="right")'
    return f"{locator}.click()"


def _emit_python_fill(action: Action, locator: str) -> str:
    """Compile a fill-style action to Python Playwright.

    Args:
        action: Normalized ``fill`` or ``contenteditable`` action.
        locator: Compiled Python locator expression.

    Returns:
        Python fill statement.

    """
    return f"{locator}.fill({dumps(obj=action.get('value'))})"


def _emit_python_select(action: Action, locator: str) -> str:
    """Compile a select action to Python Playwright.

    Args:
        action: Normalized ``select`` action.
        locator: Compiled Python locator expression.

    Returns:
        Python select_option statement.

    """
    return f"{locator}.select_option({dumps(obj=action.get('values'))})"


def _emit_python_key(action: Action, locator: str) -> str:
    """Compile a keypress action to Python Playwright.

    Args:
        action: Normalized ``key`` action.
        locator: Compiled Python locator expression, or ``page``.

    Returns:
        Python press statement.

    """
    chord: str = ActionCompiler.key(action=action)
    if locator == "page":
        return f"page.keyboard.press({dumps(obj=chord)})"
    return f"{locator}.press({dumps(obj=chord)})"


def _emit_python_scroll(action: Action, locator: str) -> str:
    """Compile a scroll action to Python Playwright.

    Args:
        action: Normalized ``scroll`` action.
        locator: Compiled Python locator expression, or ``page``.

    Returns:
        Python scroll statement.

    """
    x: JsonValue = action.get("x", 0)
    y: JsonValue = action.get("y", 0)
    if locator == "page":
        return (
            f'page.evaluate("([x, y]) => window.scrollTo(x, y)", [{x}, {y}])'
        )
    return (
        f'{locator}.evaluate("(el, p) => '
        f'{{ el.scrollLeft = p.x; el.scrollTop = p.y; }}", '
        f'{{"x": {x}, "y": {y}}})'
    )


def _emit_python_drag(action: Action, locator: str) -> str | None:
    """Compile a drag action to Python Playwright.

    Args:
        action: Normalized ``drag`` action.
        locator: Unused; drag compiles both source and destination.

    Returns:
        Python drag_to statement, or ``None`` when either endpoint is
        missing.

    """
    _ = locator
    source: Action | None = ActionCompiler.target(action=action, key="source")
    destination: Action | None = ActionCompiler.target(action=action)
    if source is None or destination is None:
        return None
    source_locator: str = LocatorCompiler.python(target=source)
    destination_locator: str = LocatorCompiler.python(target=destination)
    return f"{source_locator}.drag_to({destination_locator})"


def _emit_python_goto(action: Action, locator: str) -> str:
    """Compile a navigation action to Python Playwright.

    Args:
        action: Normalized ``navigation`` action.
        locator: Unused; navigation always targets ``page``.

    Returns:
        Python goto statement.

    """
    _ = locator
    return f"page.goto({dumps(obj=action.get('url'))})"


def _emit_python_wait(action: Action, locator: str) -> str:
    """Compile an explicit wait to Python Playwright.

    Args:
        action: Normalized ``wait`` action carrying ``milliseconds``.
        locator: Unused; waits never target an element.

    Returns:
        Python ``wait_for_timeout`` statement.

    """
    _ = locator
    return f"page.wait_for_timeout(timeout={action.get('milliseconds', 0)})"


def _emit_python_position(action: Action, locator: str) -> str | None:
    """Compile an explicit coordinate pointer action to Python Playwright.

    Args:
        action: Normalized ``position_pointer`` action.
        locator: Unused; positional actions never target an element.

    Returns:
        Python ``page.mouse`` statement, or ``None`` for unsupported
        operations.

    """
    _ = locator
    x: JsonValue = action.get("x", 0)
    y: JsonValue = action.get("y", 0)
    operation: str = str(object=action.get("position_action", ""))
    if operation == "hover":
        return f"page.mouse.move({x}, {y})"
    if operation == "click":
        return f"page.mouse.click({x}, {y})"
    if operation == "double_click":
        return f"page.mouse.dblclick({x}, {y})"
    if operation == "right_click":
        return f'page.mouse.click({x}, {y}, button="right")'
    return None


def _emit_python_locator_action(action: Action, locator: str) -> str:
    """Compile a dispatched hover, check, or uncheck action.

    Args:
        action: Normalized action selected by the emitter registry.
        locator: Resolved Python locator expression.

    Returns:
        Python method invocation for the registered action.

    """
    return f"{locator}.{action['type']}()"


def _emit_javascript_click(action: Action, locator: str) -> str:
    """Compile a click-family action to JavaScript Playwright.

    Args:
        action: Normalized ``click``, ``double_click``, or ``right_click``
            action.
        locator: Compiled JavaScript locator expression.

    Returns:
        JavaScript click statement.

    """
    kind: str = str(object=action.get("type", ""))
    if kind == "double_click":
        return f"await {locator}.dblclick();"
    if kind == "right_click":
        return f'await {locator}.click({{button: "right"}});'
    return f"await {locator}.click();"


def _emit_javascript_fill(action: Action, locator: str) -> str:
    """Compile a fill-style action to JavaScript Playwright.

    Args:
        action: Normalized ``fill`` or ``contenteditable`` action.
        locator: Compiled JavaScript locator expression.

    Returns:
        JavaScript fill statement.

    """
    return f"await {locator}.fill({dumps(obj=action.get('value'))});"


def _emit_javascript_select(action: Action, locator: str) -> str:
    """Compile a select action to JavaScript Playwright.

    Args:
        action: Normalized ``select`` action.
        locator: Compiled JavaScript locator expression.

    Returns:
        JavaScript selectOption statement.

    """
    return f"await {locator}.selectOption({dumps(obj=action.get('values'))});"


def _emit_javascript_key(action: Action, locator: str) -> str:
    """Compile a keypress action to JavaScript Playwright.

    Args:
        action: Normalized ``key`` action.
        locator: Compiled JavaScript locator expression, or ``page``.

    Returns:
        JavaScript press statement.

    """
    chord: str = ActionCompiler.key(action=action)
    if locator == "page":
        return f"await page.keyboard.press({dumps(obj=chord)});"
    return f"await {locator}.press({dumps(obj=chord)});"


def _emit_javascript_scroll(action: Action, locator: str) -> str:
    """Compile a scroll action to JavaScript Playwright.

    Args:
        action: Normalized ``scroll`` action.
        locator: Compiled JavaScript locator expression, or ``page``.

    Returns:
        JavaScript scroll statement.

    """
    x: JsonValue = action.get("x", 0)
    y: JsonValue = action.get("y", 0)
    if locator == "page":
        return (
            f"await page.evaluate(([x, y]) => "
            f"window.scrollTo(x, y), [{x}, {y}]);"
        )
    return (
        f"await {locator}.evaluate((el, p) => "
        f"{{ el.scrollLeft = p.x; el.scrollTop = p.y; }}, {{x: {x}, y: {y}}});"
    )


def _emit_javascript_drag(action: Action, locator: str) -> str | None:
    """Compile a drag action to JavaScript Playwright.

    Args:
        action: Normalized ``drag`` action.
        locator: Unused; drag compiles both source and destination.

    Returns:
        JavaScript dragTo statement, or ``None`` when either endpoint is
        missing.

    """
    _ = locator
    source: Action | None = ActionCompiler.target(action=action, key="source")
    destination: Action | None = ActionCompiler.target(action=action)
    if source is None or destination is None:
        return None
    source_locator: str = LocatorCompiler.javascript(target=source)
    destination_locator: str = LocatorCompiler.javascript(target=destination)
    return f"await {source_locator}.dragTo({destination_locator});"


def _emit_javascript_goto(action: Action, locator: str) -> str:
    """Compile a navigation action to JavaScript Playwright.

    Args:
        action: Normalized ``navigation`` action.
        locator: Unused; navigation always targets ``page``.

    Returns:
        JavaScript goto statement.

    """
    _ = locator
    return f"await page.goto({dumps(obj=action.get('url'))});"


def _emit_javascript_wait(action: Action, locator: str) -> str:
    """Compile an explicit wait to JavaScript Playwright.

    Args:
        action: Normalized ``wait`` action carrying ``milliseconds``.
        locator: Unused; waits never target an element.

    Returns:
        JavaScript ``waitForTimeout`` statement.

    """
    _ = locator
    return f"await page.waitForTimeout({action.get('milliseconds', 0)});"


def _emit_javascript_position(action: Action, locator: str) -> str | None:
    """Compile an explicit coordinate pointer action to JavaScript.

    Args:
        action: Normalized ``position_pointer`` action.
        locator: Unused; positional actions never target an element.

    Returns:
        JavaScript ``page.mouse`` statement, or ``None`` for unsupported
        operations.

    """
    _ = locator
    x: JsonValue = action.get("x", 0)
    y: JsonValue = action.get("y", 0)
    operation: str = str(object=action.get("position_action", ""))
    if operation == "hover":
        return f"await page.mouse.move({x}, {y});"
    if operation == "click":
        return f"await page.mouse.click({x}, {y});"
    if operation == "double_click":
        return f"await page.mouse.dblclick({x}, {y});"
    if operation == "right_click":
        return f'await page.mouse.click({x}, {y}, {{button: "right"}});'
    return None


def _emit_javascript_locator_action(action: Action, locator: str) -> str:
    """Compile a dispatched hover, check, or uncheck action.

    Args:
        action: Normalized action selected by the emitter registry.
        locator: Resolved JavaScript locator expression.

    Returns:
        Awaited JavaScript method invocation for the registered action.

    """
    return f"await {locator}.{action['type']}();"


class ActionRecorder:
    """Own one headed Playwright recording session."""

    def __init__(
        self,
        *,
        options: RecorderOptions,
        on_action: Callable[[Action], None] | None = None,
    ) -> None:
        """Initialize the session around ``options``.

        Args:
            options: Recording session configuration.
            on_action: Optional listener receiving every recorded action
                after it is stored (used to stream into Exactus Record).

        """
        self._on_action: Callable[[Action], None] | None = on_action
        self._options: RecorderOptions = options
        self._raw: Path = options.output / "actions.raw.jsonl"
        self._actions: list[Action] = []
        self._pages: dict[int, str] = {}
        self._started: float = monotonic()
        self._last_action_id: int | None = None

    @property
    def actions(self) -> list[Action]:
        """Raw actions recorded so far.

        Returns:
            Recorded actions in chronological order.

        """
        return self._actions

    def instrument(self, *, page: Page) -> None:
        """Attach the recorder hooks and script to an existing page.

        The injected script also runs in the already-loaded document, so
        recording starts immediately instead of after the next navigation.

        Args:
            page: Page or attached browser tab to record.

        """
        self._options.output.mkdir(parents=True, exist_ok=True)
        self._configure_page(page=page)
        with suppress(PlaywrightError):
            _ = page.evaluate(expression=_script_source())

    def run(self) -> list[Action]:
        """Record until the browser closes, then normalize and compile.

        Returns:
            Normalized replay program persisted under ``options.output``.

        """
        self._options.output.mkdir(parents=True, exist_ok=True)
        _cleared: int = self._raw.write_text(data="", encoding="utf-8")
        with sync_playwright() as playwright:
            self._run(playwright=playwright)
        normalized: list[Action] = ActionNormalizer.normalize(
            actions=self._actions,
        )
        ActionCompiler.write(
            actions=normalized,
            output=self._options.output,
            preserve_timing=self._options.preserve_timing,
        )
        return normalized

    def _record(self, *, page: Page, payload: Action) -> None:
        """Append one recorded action and mirror it to the JSONL log.

        Args:
            page: Page the action originated from.
            payload: Raw action payload reported by the injected script.

        """
        action: Action = dict(payload)
        action["page"] = self._pages.get(id(page), "page-unknown")
        action["elapsedMs"] = round(
            number=(monotonic() - self._started) * 1000.0,
            ndigits=3,
        )
        if self._actions and self._actions[-1].get("type") == "scroll":
            action["precededByScrollId"] = self._actions[-1].get("id")
        action_id: JsonValue = action.get("id")
        if isinstance(action_id, int):
            self._last_action_id = action_id
        self._actions.append(action)
        if self._on_action is not None:
            self._on_action(action)
        with self._raw.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            _written: int = stream.write(
                dumps(obj=action, ensure_ascii=False, separators=(",", ":"))
                + "\n",
            )
        sprint(dumps(obj=action, ensure_ascii=False))

    def _configure_page(self, *, page: Page) -> None:
        """Attach recorder hooks and the injected script to ``page``.

        Args:
            page: Page or popup to instrument.

        """

        def receive(message: ConsoleMessage) -> None:
            """Forward injected-script console payloads to ``_record``.

            Args:
                message: Console message emitted by the page.

            """
            prefix: str = "__EXACTUS_ACTION__"
            if message.text.startswith(prefix):
                payload: JsonValue = cast(
                    typ="JsonValue",
                    val=loads(s=message.text.removeprefix(prefix)),
                )
                if isinstance(payload, dict):
                    self._record(
                        page=page,
                        payload=cast(typ="Action", val=payload),
                    )

        page_id: str = f"page-{len(self._pages) + 1}"
        self._pages[id(page)] = page_id
        page.on(event="console", f=receive)
        _ = page.add_init_script(script=_script_source())
        page.on(
            event="framenavigated",
            f=lambda frame: (
                self._record(
                    page=page,
                    payload={"type": "navigation", "url": frame.url},
                )
                if frame == page.main_frame
                else None
            ),
        )
        page.on(
            event="popup",
            f=lambda popup: self._configure_page(page=popup),
        )
        page.on(
            event="download",
            f=lambda download: self._record(
                page=page,
                payload={
                    "type": "download",
                    "url": download.url,
                    "suggestedFilename": download.suggested_filename,
                },
            ),
        )
        page.on(
            event="dialog",
            f=lambda dialog: self._record(
                page=page,
                payload={
                    "type": "dialog",
                    "dialogType": dialog.type,
                    "message": dialog.message,
                },
            ),
        )

    def _run(self, *, playwright: Playwright) -> None:
        """Drive the headed browser until the user closes it.

        Args:
            playwright: Active ``sync_playwright`` runtime.

        """
        browser: Browser = playwright.chromium.launch(headless=False)
        context: BrowserContext = browser.new_context(
            viewport={
                "width": self._options.width,
                "height": self._options.height,
            },
        )
        page: Page = context.new_page()
        self._configure_page(page=page)
        _response: Response | None = page.goto(
            url=self._options.url,
            timeout=self._options.timeout_ms,
        )
        sprint(
            f"Recording {
                self._options.url
            }. Close the browser or press Ctrl+C to "
            f"finish.",
        )
        try:
            while browser.is_connected():
                page.wait_for_timeout(timeout=250)
        except KeyboardInterrupt:
            browser.close()


def _replay_click(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a click action.

    Args:
        page: Unused; clicks act only on their locator.
        action: Unused; clicks need no extra fields.
        locator: Resolved click target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.click()


def _replay_double_click(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay a double-click action.

    Args:
        page: Unused; clicks act only on their locator.
        action: Unused; clicks need no extra fields.
        locator: Resolved click target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.dblclick()


def _replay_right_click(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay a right-click action.

    Args:
        page: Unused; clicks act only on their locator.
        action: Unused; clicks need no extra fields.
        locator: Resolved click target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.click(button="right")


def _replay_fill(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a fill-style action.

    Args:
        page: Unused; fills act only on their locator.
        action: Normalized ``fill`` or ``contenteditable`` action.
        locator: Resolved input target, or ``None``.

    """
    _ = page
    if locator is not None:
        locator.fill(value=str(object=action.get("value", "")))


def _replay_hover(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a hover action.

    Args:
        page: Unused; hovers act only on their locator.
        action: Unused; hovers need no extra fields.
        locator: Resolved hover target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.hover()


def _replay_check(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a check action.

    Args:
        page: Unused; checks act only on their locator.
        action: Unused; checks need no extra fields.
        locator: Resolved checkbox target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.check()


def _replay_uncheck(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay an uncheck action.

    Args:
        page: Unused; unchecks act only on their locator.
        action: Unused; unchecks need no extra fields.
        locator: Resolved checkbox target, or ``None``.

    """
    _ = (page, action)
    if locator is not None:
        locator.uncheck()


def _replay_select(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay a select action.

    Args:
        page: Unused; selects act only on their locator.
        action: Normalized ``select`` action.
        locator: Resolved ``select`` element, or ``None``.

    """
    _ = page
    if locator is None:
        return
    values: JsonValue = action.get("values")
    _selected: list[str] = locator.select_option(
        value=cast(typ="list[str]", val=values)
        if isinstance(values, list)
        else str(object=values),
    )


def _replay_key(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a keypress action.

    Args:
        page: Page used when no element focus is recorded.
        action: Normalized ``key`` action.
        locator: Resolved keypress target, or ``None``.

    """
    chord: str = ActionCompiler.key(action=action)
    if locator is not None:
        locator.press(key=chord)
    else:
        page.keyboard.press(key=chord)


def _replay_scroll(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay a scroll action.

    Args:
        page: Page used for window-level scrolls.
        action: Normalized ``scroll`` action.
        locator: Resolved scroll container, or ``None``.

    """
    x: JsonValue = action.get("x", 0)
    y: JsonValue = action.get("y", 0)
    if locator is not None:
        locator.evaluate(
            expression=(
                "(el, p) => { el.scrollLeft = p.x; el.scrollTop = p.y; }"
            ),
            arg={"x": x, "y": y},
        )
    else:
        page.evaluate(
            expression="([x, y]) => window.scrollTo(x, y)",
            arg=[x, y],
        )


def _replay_drag(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay a drag action.

    Args:
        page: Page hosting both drag endpoints.
        action: Normalized ``drag`` action.
        locator: Unused; drag resolves its own source and destination.

    """
    _ = locator
    source: Action | None = ActionCompiler.target(action=action, key="source")
    destination: Action | None = ActionCompiler.target(action=action)
    if source is not None and destination is not None:
        ActionReplayer.locate(page=page, target=source).drag_to(
            target=ActionReplayer.locate(page=page, target=destination),
        )


def _replay_wait(page: Page, action: Action, locator: Locator | None) -> None:
    """Replay an explicit wait action.

    Args:
        page: Page whose timeline the wait advances.
        action: Normalized ``wait`` action carrying ``milliseconds``.
        locator: Unused; waits never target an element.

    """
    _ = locator
    raw: JsonValue = action.get("milliseconds", 0)
    page.wait_for_timeout(
        timeout=float(raw) if isinstance(raw, int | float) else 0.0,
    )


def _replay_position(
    page: Page,
    action: Action,
    locator: Locator | None,
) -> None:
    """Replay an explicit coordinate pointer action.

    Args:
        page: Page receiving the mouse operation.
        action: Normalized ``position_pointer`` action.
        locator: Unused; positional actions never target an element.

    """
    _ = locator
    raw_x: JsonValue = action.get("x", 0)
    raw_y: JsonValue = action.get("y", 0)
    x: float = float(raw_x) if isinstance(raw_x, int | float) else 0.0
    y: float = float(raw_y) if isinstance(raw_y, int | float) else 0.0
    operation: str = str(object=action.get("position_action", ""))
    if operation == "hover":
        page.mouse.move(x=x, y=y)
    elif operation == "click":
        page.mouse.click(x=x, y=y)
    elif operation == "double_click":
        page.mouse.dblclick(x=x, y=y)
    elif operation == "right_click":
        page.mouse.click(x=x, y=y, button="right")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        python_emitters: Grouped module constant.
        javascript_emitters: Grouped module constant.
        performers: Grouped module constant.

    """

    python_emitters: Final[dict[str, _Emitter]] = {
        "wait": _emit_python_wait,
        "position_pointer": _emit_python_position,
        "click": _emit_python_click,
        "double_click": _emit_python_click,
        "right_click": _emit_python_click,
        "fill": _emit_python_fill,
        "contenteditable": _emit_python_fill,
        "hover": _emit_python_locator_action,
        "check": _emit_python_locator_action,
        "uncheck": _emit_python_locator_action,
        "select": _emit_python_select,
        "key": _emit_python_key,
        "scroll": _emit_python_scroll,
        "drag": _emit_python_drag,
        "navigation": _emit_python_goto,
    }
    javascript_emitters: Final[dict[str, _Emitter]] = {
        "wait": _emit_javascript_wait,
        "position_pointer": _emit_javascript_position,
        "click": _emit_javascript_click,
        "double_click": _emit_javascript_click,
        "right_click": _emit_javascript_click,
        "fill": _emit_javascript_fill,
        "contenteditable": _emit_javascript_fill,
        "hover": _emit_javascript_locator_action,
        "check": _emit_javascript_locator_action,
        "uncheck": _emit_javascript_locator_action,
        "select": _emit_javascript_select,
        "key": _emit_javascript_key,
        "scroll": _emit_javascript_scroll,
        "drag": _emit_javascript_drag,
        "navigation": _emit_javascript_goto,
    }
    performers: Final[dict[str, _Performer]] = {
        "wait": _replay_wait,
        "position_pointer": _replay_position,
        "click": _replay_click,
        "double_click": _replay_double_click,
        "right_click": _replay_right_click,
        "fill": _replay_fill,
        "contenteditable": _replay_fill,
        "hover": _replay_hover,
        "check": _replay_check,
        "uncheck": _replay_uncheck,
        "select": _replay_select,
        "key": _replay_key,
        "scroll": _replay_scroll,
        "drag": _replay_drag,
    }


class ActionReplayer:
    """Replay normalized actions without evaluating generated source code."""

    def __init__(
        self,
        *,
        url: str,
        actions: Sequence[Action],
        options: ReplayOptions | None = None,
    ) -> None:
        """Initialize the replayer with a start URL and action program.

        Args:
            url: Absolute URL to open before replaying.
            actions: Normalized action program.
            options: Viewport, visibility, and timeout settings; defaults
                apply when omitted.

        """
        self._url: str = url
        self._actions: Sequence[Action] = actions
        self._options: ReplayOptions = options or ReplayOptions()

    @staticmethod
    def locate(*, page: Page, target: Action) -> Locator:
        """Resolve a recorded target to a live ``Locator``.

        Args:
            page: Page being replayed against.
            target: Recorded action target carrying locator candidates.

        Returns:
            Locator for the strongest available candidate.

        """
        candidate: Action | None = LocatorCompiler.candidate(target=target)
        if candidate is None:
            return page.locator(selector="body")
        kind: str = str(object=candidate.get("kind", "css"))
        value: str = str(object=candidate.get("value", ""))
        if kind == "test_id":
            return page.get_by_test_id(test_id=value)
        if kind == "role":
            return page.get_by_role(
                role=cast(
                    typ="Literal['button']",
                    val=str(object=candidate.get("role", "")),
                ),
                name=str(object=candidate.get("name", "")),
                exact=True,
            )
        if kind == "label":
            return page.get_by_label(text=value, exact=True)
        if kind == "placeholder":
            return page.get_by_placeholder(text=value, exact=True)
        return page.locator(
            selector=str(object=candidate.get("value", "body")),
        )

    def perform(self, *, page: Page, action: Action) -> None:
        """Replay one normalized action against ``page``.

        Args:
            page: Page being replayed against.
            action: Normalized action to perform.

        """
        performer: _Performer | None = Constants.performers.get(
            str(object=action.get("type", "")),
        )
        if performer is None:
            return
        target: Action | None = ActionCompiler.target(action=action)
        locator: Locator | None = (
            self.locate(page=page, target=target) if target else None
        )
        performer(page=page, action=action, locator=locator)

    def run(self) -> list[str]:
        """Replay the normalized action sequence, collecting failures.

        Every action is attempted even when an earlier one failed, so one
        stale selector cannot hide the rest of the program.

        Returns:
            One ``"<index> <type>: <error>"`` line per failed action;
            empty when the whole program replayed.

        """
        failures: list[str] = []
        with sync_playwright() as playwright:
            browser: Browser = playwright.chromium.launch(
                headless=self._options.headless,
            )
            context: BrowserContext = browser.new_context(
                viewport={
                    "width": self._options.width,
                    "height": self._options.height,
                },
            )
            page: Page = context.new_page()
            page.set_default_timeout(timeout=self._options.timeout_ms)
            _response: Response | None = page.goto(url=self._url)
            for index, action in enumerate(iterable=self._actions):
                kind: str = str(object=action.get("type", ""))
                if kind == "navigation":
                    continue
                try:
                    self.perform(page=page, action=action)
                except PlaywrightError as error:
                    first: str = str(object=error).splitlines()[0]
                    failures.append(f"{index} {kind}: {first}")
            browser.close()
        return failures


def load_actions(*, path: Path) -> list[Action]:
    """Load normalized JSON actions.

    Args:
        path: ``actions.normalized.json`` written by the recorder.

    Returns:
        Action program entries.

    Raises:
        TypeError: When the file does not contain a JSON array.

    """
    value: JsonValue = cast(
        typ="JsonValue",
        val=loads(s=path.read_text(encoding="utf-8")),
    )
    if not isinstance(value, list):
        msg: str = "action program must be a JSON array"
        raise TypeError(msg)
    return [
        cast(typ="Action", val=item)
        for item in value
        if isinstance(item, dict)
    ]
