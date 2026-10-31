# Copyright (c) 2026
"""Typed assertion helpers shared by the scene_description tests.

Project rules forbid bare ``assert`` statements in owned sources, so every
test checks outcomes through these keyword-only helpers, which raise
:class:`AssertionError` with a message naming both the observed and the
required value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Container

    from exactus.packages.scene_description.models import JsonValue


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
    """Require ``actual`` to equal ``expected``.

    Args:
        actual: Observed value.
        expected: Required value.
        message: Optional description reported on failure.

    """
    if actual != expected:
        fail(message=message or f"expected {expected!r}, observed {actual!r}")


def expect_in(*, member: object, container: Container[object]) -> None:
    """Require ``member`` to appear inside ``container``.

    Args:
        member: Item that must be present.
        container: Collection searched for the member.

    """
    if member not in container:
        fail(message=f"expected {member!r} in {container!r}")


def expect_none(*, value: object, message: str = "") -> None:
    """Require ``value`` to be ``None``.

    Args:
        value: Observed value.
        message: Optional description reported on failure.

    """
    if value is not None:
        fail(message=message or f"expected None, observed {value!r}")


def require_json_dict(*, value: object) -> dict[str, JsonValue]:
    """Require ``value`` to be a JSON object.

    Args:
        value: Observed value expected to be a dict.

    Returns:
        The value typed as a JSON object.

    """
    if not isinstance(value, dict):
        fail(message=f"expected a JSON object, observed {value!r}")
    return cast(typ="dict[str, JsonValue]", val=value)


def require_json_list(*, value: object) -> list[JsonValue]:
    """Require ``value`` to be a JSON array.

    Args:
        value: Observed value expected to be a list.

    Returns:
        The value typed as a JSON array.

    """
    if not isinstance(value, list):
        fail(message=f"expected a JSON array, observed {value!r}")
    return cast(typ="list[JsonValue]", val=value)


def expect_raises(
    *,
    kind: type[BaseException],
    call: Callable[[], object],
) -> BaseException:
    """Require ``call`` to raise ``kind`` and return the exception.

    Args:
        kind: Expected exception type.
        call: Zero-argument callable exercised by the test.

    Returns:
        The captured exception instance.

    Raises:
        AssertionError: If the operation cannot complete.

    """
    try:
        call()
    except kind as error:
        return error
    fail(message=f"expected {kind.__name__}")
    msg: str = "unreachable"
    raise AssertionError(msg)
