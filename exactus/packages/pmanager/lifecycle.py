# Copyright (c) 2026 João Lopes.
"""Python process classes and lifecycle-hook decorators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from inspect import iscoroutinefunction
from threading import Thread
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.packages.pmanager.model import ModelValue


class Lifecycle(StrEnum):
    """Lifecycle.

    Attributes:
        PAUSE: Pause.
        RESUME: Resume.
        RESET: Reset.
        CANCEL: Cancel.
        KILL: Kill.
        STATUS: Status.

    """

    PAUSE = "pause"
    RESUME = "resume"
    RESET = "reset"
    CANCEL = "cancel"
    KILL = "kill"
    STATUS = "status"


lifecycle_hooks: dict[Callable[..., ModelValue], Lifecycle] = {}
broadcast_hooks: dict[Callable[..., ModelValue], str] = {}


def _decorate[**P, R](
    *,
    kind: Lifecycle,
    function: Callable[P, R],
) -> Callable[P, R]:
    """Register and return one lifecycle hook.

    Args:
        kind: Lifecycle.
        function: Function.

    Returns:
        The resulting value.

    """
    lifecycle_hooks[cast(typ="Callable[..., ModelValue]", val=function)] = kind
    return function


def pause[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the pause hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.PAUSE, function=function)


def resume[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the resume hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.RESUME, function=function)


def reset[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the reset hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.RESET, function=function)


def cancel[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the cancel hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.CANCEL, function=function)


def kill[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the bounded pre-kill hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.KILL, function=function)


def status[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Mark a method as the live status hook.

    Args:
        function: Function.

    Returns:
        The resulting value.

    """
    return _decorate(kind=Lifecycle.STATUS, function=function)


def receive[**P, R](topic: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Build a typed broadcast-receiver decorator.

    Args:
        topic: Broadcast topic or wildcard.

    Returns:
        Decorator preserving the receiver signature.

    """

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        """Register a broadcast receiver for the configured topic.

        Args:
            function: Function.

        Returns:
            The resulting value.

        """
        broadcast_hooks[
            cast(typ="Callable[..., ModelValue]", val=function)
        ] = topic
        return function

    return decorate


@dataclass(frozen=True, slots=True)
class CallArguments:
    """Callarguments.

    Attributes:
        args: Args.
        kwargs: Kwargs.

    """

    args: tuple[ModelValue, ...] = ()
    kwargs: dict[str, ModelValue] | None = None


class ProcessClass:
    """Processclass.

    Attributes:
        process_name: Process name.
        kill_timeout: Kill timeout.

    """

    process_name: str | None = None
    kill_timeout: float = 5.0

    def __init__(self) -> None:
        """Init."""
        self._broadcast_sender: (
            Callable[[str, ModelValue, str], int] | None
        ) = None

    @classmethod
    def name(cls) -> str:
        """Name.

        Returns:
            The resulting value.

        """
        return cls.process_name or cls.__name__

    def configure_broadcast(
        self,
        sender: Callable[[str, ModelValue, str], int],
    ) -> None:
        """Configure broadcast.

        Args:
            sender: Sender.

        """
        self._broadcast_sender = sender

    def broadcast(
        self,
        topic: str,
        payload: ModelValue = None,
        *,
        scope: str = "context",
    ) -> int:
        """Broadcast.

        Args:
            topic: Topic.
            payload: Payload.
            scope: Scope.

        Returns:
            The resulting value.

        """
        if self._broadcast_sender is None:
            return 0
        return self._broadcast_sender(topic, payload, scope)

    def receive_broadcast(self, topic: str, payload: ModelValue) -> None:
        """Receive broadcast.

        Args:
            topic: Topic.
            payload: Payload.

        """
        for attribute_name in dir(type(self)):
            candidate: Callable[..., ModelValue] = cast(
                typ="Callable[..., ModelValue]",
                val=getattr(type(self), attribute_name),
            )
            if not callable(candidate):
                continue
            if broadcast_hooks.get(candidate) not in {topic, "*"}:
                continue
            handler: Callable[[ModelValue], ModelValue] = cast(
                typ="Callable[[ModelValue], ModelValue]",
                val=getattr(self, attribute_name),
            )
            handler(payload)

    def lifecycle_hook(
        self,
        lifecycle: Lifecycle,
    ) -> Callable[[], ModelValue] | None:
        """Lifecycle hook.

        Args:
            lifecycle: Lifecycle.

        Returns:
            The resulting value.

        """
        for attribute_name in dir(type(self)):
            candidate: Callable[..., ModelValue] = cast(
                typ="Callable[..., ModelValue]",
                val=getattr(type(self), attribute_name),
            )
            if not callable(candidate):
                continue
            if lifecycle_hooks.get(candidate) == lifecycle:
                return cast(
                    typ="Callable[[], ModelValue]",
                    val=getattr(self, attribute_name),
                )
        return None

    def invoke_lifecycle(
        self,
        lifecycle: Lifecycle,
        timeout: float | None = None,
    ) -> bool:
        """Invoke lifecycle.

        Args:
            lifecycle: Lifecycle.
            timeout: Timeout.

        Raises:
            TypeError: When the operation cannot complete.

        Returns:
            The resulting value.

        """
        hook: Callable[[], ModelValue] | None = self.lifecycle_hook(
            lifecycle=lifecycle,
        )
        if hook is None:
            return True
        if iscoroutinefunction(obj=hook):
            msg: str = (
                "Async lifecycle hooks are not supported by this runner."
            )
            raise TypeError(msg)
        completed: list[bool] = []

        def invoke() -> None:
            """Invoke."""
            hook()
            completed.append(True)

        thread: Thread = Thread(target=invoke, daemon=True)
        thread.start()
        thread.join(timeout=self.kill_timeout if timeout is None else timeout)
        return bool(completed)


def process_name[ProcessT: ProcessClass](
    name: str,
) -> Callable[[type[ProcessT]], type[ProcessT]]:
    """Process name.

    Args:
        name: Name.

    Returns:
        The resulting value.

    """

    def decorate(cls: type[ProcessT]) -> type[ProcessT]:
        """Decorate.

        Args:
            cls: Process class to decorate.

        Returns:
            The resulting value.

        """
        cls.process_name = name
        return cls

    return decorate
