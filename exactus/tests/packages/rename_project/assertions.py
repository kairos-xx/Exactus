"""Keyword-only assertion helpers for the rename_project tests.

Bare ``assert`` statements are replaced by these helpers so every check is
explicit, keyword-only, and reports both the observed and the required value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Container


def fail(*, message: str) -> NoReturn:
    """Fail the running test.

    Args:
        message: Explanation of the failed expectation.

    Raises:
        AssertionError: Always.

    """
    raise AssertionError(message)


def expect_true(*, condition: bool, message: str = "") -> None:
    """Require ``condition`` to hold.

    Args:
        condition: Observed truth value.
        message: Optional description reported on failure.

    """
    if not condition:
        fail(message=f"expected true: {message}")


def expect_false(*, condition: bool, message: str = "") -> None:
    """Require ``condition`` not to hold.

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
        fail(message=f"expected {expected!r}, got {actual!r}. {message}")


def expect_not_equal(
    *,
    actual: object,
    expected: object,
    message: str = "",
) -> None:
    """Require two values to compare unequal.

    Args:
        actual: Observed value.
        expected: Value that must differ.
        message: Optional description reported on failure.

    """
    if actual == expected:
        fail(message=f"expected a value other than {expected!r}. {message}")


def expect_in(
    *,
    member: object,
    container: Container[object],
    message: str = "",
) -> None:
    """Require ``member`` to be contained in ``container``.

    Args:
        member: Value searched for.
        container: Collection or string expected to hold it.
        message: Optional description reported on failure.

    """
    if member not in container:
        fail(message=f"{member!r} not found in {container!r}. {message}")


def expect_not_in(
    *,
    member: object,
    container: Container[object],
    message: str = "",
) -> None:
    """Require ``member`` to be absent from ``container``.

    Args:
        member: Value that must be missing.
        container: Collection or string inspected.
        message: Optional description reported on failure.

    """
    if member in container:
        fail(message=f"{member!r} unexpectedly in {container!r}. {message}")


def expect_none(*, value: object, message: str = "") -> None:
    """Require ``value`` to be ``None``.

    Args:
        value: Observed value.
        message: Optional description reported on failure.

    """
    if value is not None:
        fail(message=f"expected None, got {value!r}. {message}")


def expect_not_none(*, value: object, message: str = "") -> None:
    """Require ``value`` not to be ``None``.

    Args:
        value: Observed value.
        message: Optional description reported on failure.

    """
    if value is None:
        fail(message=f"expected a value, got None. {message}")
