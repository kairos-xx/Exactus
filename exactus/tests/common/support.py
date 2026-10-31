# Copyright (c) 2026
"""Typed assertion, reflection and fixture helpers shared by the suite.

The toolkit's own rules forbid bare ``assert`` statements, suppression
comments and ``typing.Any`` in its sources, so every test checks outcomes
through these keyword-only helpers, which raise :class:`AssertionError`
with a message naming both the observed and the required value.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

from exactus.tools.reports.bundle import ReportBundle
from exactus.tools.reports.render import ReportTemplates

if TYPE_CHECKING:
    from collections.abc import Container

    from exactus.tools.common.json_types import JsonValue


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


def expect_equal(*, actual: object, expected: object) -> None:
    """Require two values to compare equal.

    Args:
        actual: Observed value.
        expected: Required value.

    """
    if actual != expected:
        fail(message=f"expected {expected!r}, got {actual!r}")


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


def private(*, owner: object, name: str) -> object:
    """Read a non-public attribute of ``owner`` by name.

    Tests exercise a few internal helpers whose behavior is not reachable
    through the public surface; this keeps that reflection explicit and
    in one place.

    Args:
        owner: Module, class, or instance holding the attribute.
        name: Attribute name, including its leading underscore.

    Returns:
        The attribute value.

    """
    return getattr(owner, name)


def private_call(*, owner: object, name: str, **arguments: object) -> object:
    """Call a non-public callable of ``owner`` with keyword arguments.

    Args:
        owner: Module, class, or instance holding the callable.
        name: Callable name, including its leading underscore.
        **arguments: Keyword arguments forwarded to the callable.

    Returns:
        Whatever the callable returns.

    """
    return getattr(owner, name)(**arguments)


def set_private(*, owner: object, name: str, value: object) -> None:
    """Assign a non-public attribute of ``owner`` by name.

    Args:
        owner: Module, class, or instance receiving the value.
        name: Attribute name, including its leading underscore.
        value: Value to store.

    """
    setattr(owner, name, value)


def private_clear(*, owner: object, name: str) -> None:
    """Empty a non-public mapping or collection held by ``owner``.

    Args:
        owner: Module, class, or instance holding the collection.
        name: Attribute name, including its leading underscore.

    """
    getattr(owner, name).clear()


def private_as[T](*, owner: object, name: str, kind: type[T]) -> T:
    """Read a non-public attribute of ``owner`` as an instance of ``kind``.

    Args:
        owner: Module, class, or instance holding the attribute.
        name: Attribute name, including its leading underscore.
        kind: Class the attribute must be an instance of.

    Returns:
        The attribute narrowed to ``kind``.

    """
    return require_type(value=private(owner=owner, name=name), kind=kind)


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
    *,
    owner: object,
    name: str,
    kind: type[T],
    **arguments: object,
) -> T:
    """Call a non-public callable of ``owner`` and type its result.

    Args:
        owner: Module, class, or instance holding the callable.
        name: Callable name, including its leading underscore.
        kind: Class the result must be an instance of.
        **arguments: Keyword arguments forwarded to the callable.

    Returns:
        The result narrowed to ``kind``.

    """
    return require_type(
        value=private_call(owner=owner, name=name, **arguments),
        kind=kind,
    )


def dig(*, document: object, path: tuple[str | int, ...]) -> object:
    """Walk a decoded JSON document along ``path``.

    Args:
        document: Decoded JSON value.
        path: Object keys and list positions to follow.

    Returns:
        The value found at the end of the path.

    """
    node: object = document
    for step in path:
        if isinstance(step, int):
            items: list[object] = cast(
                typ="list[object]",
                val=require_type(value=node, kind=list),
            )
            node = items[step]
        else:
            fields: dict[str, object] = cast(
                typ="dict[str, object]",
                val=require_type(value=node, kind=dict),
            )
            node = fields[step]
    return node


def dig_list(*, document: object, path: tuple[str | int, ...]) -> list[object]:
    """Walk a decoded JSON document to a list.

    Args:
        document: Decoded JSON value.
        path: Object keys and list positions to follow.

    Returns:
        The list found at the end of the path.

    """
    return cast(
        typ="list[object]",
        val=require_type(value=dig(document=document, path=path), kind=list),
    )


def stamped_markdown(
    *,
    model: dict[str, JsonValue],
    tool_dir: Path,
    base: Path,
) -> str:
    """Render ``model`` exactly as the entrypoint stamps ``result.md``.

    ``NormalizedStamp`` renders the tool template and then links every
    backticked project path that exists on disk, so a test comparing
    against a written ``result.md`` must apply the same pass.

    Args:
        model: Normalized ``result.json`` payload.
        tool_dir: Tool Markdown template directory.
        base: Directory ``result.md`` is written to.

    Returns:
        Rendered Markdown with project paths linked.

    """
    return ReportBundle.link_paths(
        markdown=ReportTemplates.render(
            model=model,
            tool_dir=tool_dir,
        ).markdown,
        base=base,
        root=Path(str(object=model.get("project_root") or Path.cwd())),
    )
