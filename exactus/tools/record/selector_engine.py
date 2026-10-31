# Copyright (c) 2026 Project contributors
"""Load the ExtendedSelector package engine as an injectable script."""

from __future__ import annotations

from importlib.resources import files
from json import dumps
from typing import TYPE_CHECKING, Final, cast, final
from weakref import WeakKeyDictionary

from playwright.sync_api import Error as PlaywrightError

if TYPE_CHECKING:
    from collections.abc import Callable
    from importlib.resources.abc import Traversable

    from playwright.sync_api import CDPSession, Page

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        package: Grouped module constant.
        relative: Grouped module constant.
        class_export: Grouped module constant.
        default_export: Grouped module constant.
        global_name: Grouped module constant.
        world_name: Grouped module constant.
        worlds: Grouped module constant.

    """

    package: Final[str] = "exactus.packages.extended_selector"
    relative: Final[str] = "editor/extended-selector.js"
    class_export: Final[str] = "export class ExtendedSelector "
    default_export: Final[str] = "export default ExtendedSelector;"
    global_name: Final[str] = "__EXACTUS_ES__"
    world_name: Final[str] = "exactus"
    worlds: Final[WeakKeyDictionary[Page, EngineWorld]] = WeakKeyDictionary()


def engine_source() -> str:
    """Return the ExtendedSelector package engine module source.

    Returns:
        JavaScript module text of ``extended-selector.js``.

    Raises:
        FileNotFoundError: When the package engine is missing.

    """
    resource: Traversable = files(anchor=Constants.package).joinpath(
        Constants.relative,
    )
    if not resource.is_file():
        msg: str = "The ExtendedSelector package engine is missing."
        raise FileNotFoundError(msg)
    return resource.read_text(encoding="utf-8")


def engine_script() -> str:
    """Return the engine as a plain script that defines one global.

    The module's ``export`` keywords are removed so the text can be evaluated
    in a page or an isolated world, and the class is published as
    ``globalThis.__EXACTUS_ES__``.

    Returns:
        JavaScript that defines ``globalThis.__EXACTUS_ES__``.

    Raises:
        ValueError: When the engine no longer has the expected export lines.

    """
    source: str = engine_source()
    if (
        source.count(Constants.class_export) != 1
        or source.count(Constants.default_export) != 1
    ):
        msg: str = (
            "The ExtendedSelector package engine has unexpected "
            "export statements."
        )
        raise ValueError(msg)
    script: str = source.replace(
        Constants.class_export,
        "class ExtendedSelector ",
    ).replace(Constants.default_export, "")
    name: str = Constants.global_name
    return f"{script}\nglobalThis.{name} = ExtendedSelector;\n"


class SelectorRuntimeError(ValueError):
    """Report a script failure inside the engine world.

    It is a ``ValueError`` so the flow runner treats it as a failed action
    instead of crashing the run.
    """


def _cdp(
    *,
    session: CDPSession,
    method: str,
    params: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Send one protocol command with a precise result type.

    Args:
        session: CDP session of the page.
        method: Protocol method, such as ``Runtime.evaluate``.
        params: Method parameters.

    Returns:
        The protocol reply.

    """
    send: Callable[..., dict[str, JsonValue]] = cast(
        typ="Callable[..., dict[str, JsonValue]]",
        val=session.send,
    )
    return send(method=method, params=params)


def _is_stale(*, error: PlaywrightError) -> bool:
    """Tell whether a protocol error means the world no longer exists.

    Args:
        error: Error raised by the CDP session.

    Returns:
        True when the page navigated or the session was detached.

    """
    text: str = str(object=error).lower()
    return any(
        part in text
        for part in (
            "cannot find context",
            "context was destroyed",
            "execution context",
            "session closed",
            "target closed",
            "detached",
        )
    )


@final
class EngineWorld:
    """Keep the engine in an isolated world of one page.

    The world shares the page's DOM but not its JavaScript globals, so the
    application cannot see or change the engine, and nothing the engine
    defines leaks into the page. A navigation destroys the world; the next
    call recreates it and injects the engine again.
    """

    def __init__(self, *, page: Page) -> None:
        """Remember the page; nothing is created until first use.

        Args:
            page: Page that owns the world.

        """
        self._page: Page = page
        self._session: CDPSession | None = None
        self._context_id: int | None = None

    def evaluate(self, *, expression: str) -> JsonValue:
        """Run a script in the world and return its JSON result.

        Args:
            expression: JavaScript expression; a promise is awaited.

        Returns:
            The value the script produced.

        Raises:
            Error: When the evaluation fails and is not stale.

        """
        try:
            return self._run(expression=expression)
        except PlaywrightError as error:
            if not _is_stale(error=error):
                raise
            self._reset()
            return self._run(expression=expression)

    def call(self, *, function: str, argument: JsonValue) -> JsonValue:
        """Call a JavaScript function with one JSON argument.

        Args:
            function: Source of a function, such as ``(args) => args.x``.
            argument: Value passed as the only argument.

        Returns:
            The function's JSON result.

        """
        literal: str = dumps(obj=argument, allow_nan=False)
        return self.evaluate(
            expression=f"({function.strip().removesuffix(';')})({literal})",
        )

    def _reset(self) -> None:
        """Forget the world and the session so both are created again."""
        self._context_id = None
        self._session = None

    def _run(self, *, expression: str) -> JsonValue:
        """Evaluate in the current world, creating it first when needed.

        Args:
            expression: JavaScript expression.

        Returns:
            The value the script produced.

        """
        return self._send(context_id=self._ensure(), expression=expression)

    def _ensure(self) -> int:
        """Return the world's context identifier, creating the world.

        Returns:
            Execution context identifier with the engine injected.

        """
        if self._context_id is not None:
            return self._context_id
        session: CDPSession = (
            self._session
            or self._page.context.new_cdp_session(page=self._page)
        )
        self._session = session
        tree: dict[str, dict[str, dict[str, str]]] = cast(
            typ="dict[str, dict[str, dict[str, str]]]",
            val=_cdp(session=session, method="Page.getFrameTree"),
        )
        world: dict[str, int] = cast(
            typ="dict[str, int]",
            val=_cdp(
                session=session,
                method="Page.createIsolatedWorld",
                params={
                    "frameId": tree["frameTree"]["frame"]["id"],
                    "worldName": Constants.world_name,
                    "grantUniveralAccess": True,
                },
            ),
        )
        context_id: int = world["executionContextId"]
        _ = self._send(
            context_id=context_id,
            expression=f"{engine_script()}\n'ready'",
        )
        self._context_id = context_id
        return context_id

    def _send(self, *, context_id: int, expression: str) -> JsonValue:
        """Evaluate in a known context.

        Args:
            context_id: Execution context identifier.
            expression: JavaScript expression.

        Returns:
            The value the script produced.

        Raises:
            SelectorRuntimeError: When the script throws.

        """
        session: CDPSession = cast(typ="CDPSession", val=self._session)
        reply: dict[str, dict[str, JsonValue]] = cast(
            typ="dict[str, dict[str, JsonValue]]",
            val=_cdp(
                session=session,
                method="Runtime.evaluate",
                params={
                    "expression": expression,
                    "contextId": context_id,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            ),
        )
        details: dict[str, JsonValue] | None = reply.get("exceptionDetails")
        if details is not None:
            exception: JsonValue = details.get("exception")
            text: JsonValue = (
                exception.get("description")
                if isinstance(exception, dict)
                else details.get("text")
            )
            raise SelectorRuntimeError(str(object=text).splitlines()[0])
        return reply["result"].get("value")


def world_for(*, page: Page) -> EngineWorld:
    """Return the page's engine world, creating the handle once.

    Args:
        page: Page whose world is wanted.

    Returns:
        The shared handle for the page.

    """
    world: EngineWorld | None = Constants.worlds.get(page)
    if world is None:
        world = EngineWorld(page=page)
        Constants.worlds[page] = world
    return world
