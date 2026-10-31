# Copyright (c) 2026
"""The package facade is the controlled public API surface."""

from __future__ import annotations

from importlib import import_module
from inspect import signature
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.catalog import ToolSpec

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    import pytest


@final
class Constants:
    """Group module-level constants.

    Attributes:
        exactus: Grouped module constant.

    """

    exactus: Final[ModuleType] = import_module(name="exactus")


def test_exports_match_catalog() -> None:
    """``exactus.__all__`` is exactly the catalog's tool identifiers."""
    expect_equal(
        actual=sorted(Constants.exactus.__all__),
        expected=sorted(
            tool.identifier
            for tool in _GroupFinalConstants.exactus_catalog.tools()
        ),
    )


def test_exports_are_real_callables() -> None:
    """Every facade export is a real function defined in the package."""
    for name in Constants.exactus.__all__:
        exported: object = getattr(Constants.exactus, name)
        expect_true(condition=callable(exported))
        expect_equal(actual=exported.__module__, expected="exactus")
        delegate: Callable[..., object] = cast(
            typ="Callable[..., object]",
            val=exported,
        )
        expect_true(
            condition="arguments" in signature(obj=delegate).parameters,
        )


def test_exports_delegate_to_tool_mains() -> None:
    """Each export pipes to its ``exactus.tools.<name>.main`` module."""
    tool: ToolSpec
    for tool in _GroupFinalConstants.exactus_catalog.tools():
        module: ModuleType = import_module(name=tool.module)
        expect_true(condition=callable(module.main))
        expect_true(condition=hasattr(Constants.exactus, tool.identifier))


def _recording_main(
    *,
    calls: list[tuple[str, ...] | None],
) -> Callable[..., int]:
    """Build a ``main`` replacement that records its arguments.

    Args:
        calls: Sink receiving the delegated argument tuples.

    Returns:
        Replacement ``main`` function.

    """

    def main(*, arguments: tuple[str, ...] | None = None) -> int:
        """Record the delegated call.

        Args:
            arguments: Facade-supplied argument tuple.

        Returns:
            Marker exit status.

        """
        calls.append(arguments)
        return 7

    return main


def test_exports_call_tool_mains(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each facade function calls its tool's ``main`` with the arguments.

    Args:
        monkeypatch: Patch fixture.

    """
    tool: ToolSpec
    for tool in _GroupFinalConstants.exactus_catalog.tools():
        module: ModuleType = import_module(name=tool.module)
        calls: list[tuple[str, ...] | None] = []
        monkeypatch.setattr(
            target=module,
            name="main",
            value=_recording_main(calls=calls),
        )
        delegate: Callable[..., object] = cast(
            typ="Callable[..., object]",
            val=getattr(Constants.exactus, tool.identifier),
        )
        expect_equal(actual=delegate(arguments=("--flag",)), expected=7)
        expect_equal(actual=delegate(), expected=7)
        expect_equal(actual=calls, expected=[("--flag",), None])


def test_internals_stay_private() -> None:
    """Tool internals are not re-exported through the package dict."""
    private: Final[tuple[str, ...]] = ("tools", "scripts", "bundle")
    for name in private:
        expect_true(condition=name not in Constants.exactus.__all__)
