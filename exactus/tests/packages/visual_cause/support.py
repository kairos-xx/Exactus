# Copyright (c) 2026
"""Typed assertion and reflection helpers shared by the test suite.

Project rules forbid bare ``assert`` statements and unannotated
``getattr`` reflection in owned sources, so every test checks outcomes
through these keyword-only helpers, which raise :class:`AssertionError`
with a message naming both the observed and the required value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Container


def fail(*, message: str) -> NoReturn:
    """Fail the running test.

    Args:
        message: Explanation of the failed expectation.

    Raises:
        AssertionError: Always.

    """
    raise AssertionError(message)


def expect_true(*, condition: object, message: str = "") -> None:
    """Require ``condition`` to be truthy.

    Args:
        condition: Observed truth value.
        message: Optional description reported on failure.

    """
    if not condition:
        fail(message=f"expected true: {message}")


def expect_false(*, condition: object, message: str = "") -> None:
    """Require ``condition`` to be falsy.

    Args:
        condition: Observed truth value.
        message: Optional description reported on failure.

    """
    if condition:
        fail(message=f"expected false: {message}")


def expect_equal(
    *,
    actual: object,
    expected: object,
    message: str = "",
) -> None:
    """Require two values to compare equal.

    Args:
        actual: Observed value.
        expected: Required value.
        message: Optional description reported on failure.

    """
    if actual != expected:
        fail(
            message=(
                f"expected {expected!r}, got {actual!r}"
                + (f" ({message})" if message else "")
            ),
        )


def expect_not_equal(*, actual: object, expected: object) -> None:
    """Require two values to compare unequal.

    Args:
        actual: Observed value.
        expected: Value that must differ.

    """
    if actual == expected:
        fail(message=f"expected a value other than {expected!r}")


def expect_in(*, member: object, container: Container[object]) -> None:
    """Require ``member`` to be contained in ``container``.

    Args:
        member: Value searched for.
        container: Collection or string expected to hold it.

    """
    if member not in container:
        fail(message=f"{member!r} not found in {container!r}")


def expect_not_in(*, member: object, container: Container[object]) -> None:
    """Require ``member`` to be absent from ``container``.

    Args:
        member: Value that must be missing.
        container: Collection or string inspected.

    """
    if member in container:
        fail(message=f"{member!r} unexpectedly found in {container!r}")


def expect_none(*, value: object) -> None:
    """Require ``value`` to be ``None``.

    Args:
        value: Observed value.

    """
    if value is not None:
        fail(message=f"expected None, got {value!r}")


def require[T](*, value: T | None) -> T:
    """Require ``value`` to be present and return it narrowed.

    Args:
        value: Observed optional value.

    Returns:
        The same value, known not to be ``None``.

    """
    if value is None:
        fail(message="expected a value, got None")
    return value


def require_type[T](*, value: object, kind: type[T]) -> T:
    """Require ``value`` to be an instance of ``kind`` and return it.

    Args:
        value: Observed value.
        kind: Required class.

    Returns:
        The value narrowed to ``kind``.

    """
    if not isinstance(value, kind):
        fail(message=f"expected {kind.__name__}, got {value!r}")
    return value


def private(owner: object, member: str, /) -> object:
    """Read a non-public attribute of ``owner`` by name.

    Tests exercise a few internal helpers whose behavior is not reachable
    through the public surface; this keeps that reflection explicit and
    in one place.

    Args:
        owner: Module, class, or instance holding the attribute.
        member: Attribute name, including its leading underscore.

    Returns:
        The attribute value.

    """
    return getattr(owner, member)


def private_call(owner: object, member: str, /, **arguments: object) -> object:
    """Call a non-public callable of ``owner`` with keyword arguments.

    Args:
        owner: Module, class, or instance holding the callable.
        member: Callable name, including its leading underscore.
        **arguments: Keyword arguments forwarded to the callable.

    Returns:
        Whatever the callable returns.

    """
    return cast(typ="Callable[..., object]", val=getattr(owner, member))(
        **arguments,
    )


def set_private(owner: object, member: str, value: object, /) -> None:
    """Assign a non-public attribute of ``owner`` by name.

    Args:
        owner: Module, class, or instance receiving the value.
        member: Attribute name, including its leading underscore.
        value: Value to store.

    """
    setattr(owner, member, value)


def private_clear(owner: object, member: str, /) -> None:
    """Empty a non-public mapping or collection held by ``owner``.

    Args:
        owner: Module, class, or instance holding the collection.
        member: Attribute name, including its leading underscore.

    """
    getattr(owner, member).clear()


def private_as[T](owner: object, member: str, kind: type[T], /) -> T:
    """Read a non-public attribute of ``owner`` as an instance of ``kind``.

    Args:
        owner: Module, class, or instance holding the attribute.
        member: Attribute name, including its leading underscore.
        kind: Class the attribute must be an instance of.

    Returns:
        The attribute narrowed to ``kind``.

    """
    return require_type(value=private(owner, member), kind=kind)


class Constant[T]:
    """Callable stand-in that ignores its arguments and returns one value."""

    def __init__(self, *, value: T) -> None:
        """Store the value every call returns.

        Args:
            value: Value returned by each call.

        """
        self._value: T = value

    def __call__(self, *positional: object, **arguments: object) -> T:
        """Return the stored value.

        Args:
            *positional: Ignored positional arguments.
            **arguments: Ignored keyword arguments.

        Returns:
            The stored value.

        """
        del positional, arguments
        return self._value


def private_result[T](
    owner: object,
    member: str,
    kind: type[T],
    /,
    **arguments: object,
) -> T:
    """Call a non-public callable of ``owner`` and type its result.

    Args:
        owner: Module, class, or instance holding the callable.
        member: Callable name, including its leading underscore.
        kind: Class the result must be an instance of.
        **arguments: Keyword arguments forwarded to the callable.

    Returns:
        The result narrowed to ``kind``.

    """
    return require_type(
        value=private_call(owner, member, **arguments),
        kind=kind,
    )


def dig(*, document: object, path: tuple[str | int, ...]) -> object:
    """Walk a decoded JSON document along ``path``.

    Args:
        document: Nested dict/list structure to traverse.
        path: Keys and indexes applied in order.

    Returns:
        The value found at the end of ``path``.

    """
    current: object = document
    for step in path:
        if isinstance(step, int):
            current = cast(typ="list[object]", val=current)[step]
        else:
            current = cast(typ="dict[str, object]", val=current)[step]
    return current


def dig_list(*, document: object, path: tuple[str | int, ...]) -> list[object]:
    """Walk a decoded JSON document and require a list at ``path``.

    Args:
        document: Nested dict/list structure to traverse.
        path: Keys and indexes applied in order.

    Returns:
        The list found at the end of ``path``.

    """
    return cast(typ="list[object]", val=dig(document=document, path=path))
