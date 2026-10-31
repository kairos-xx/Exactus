# Copyright (c) 2026
"""Exactus tooling, recording, and report generation.

This module's dict is the package's controlled public API: each
catalog tool is exposed as a real function that pipes into the
module the catalog declares for it. Internals under
``exactus.tools`` stay private by non-export — only the names in
``__all__`` are part of the surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, final

from exactus.tools.common.catalog import Constants as _GroupFinalConstants

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from exactus.tools.common.catalog import ToolSpec
__all__: list[str] = [
    "coverage_tests",
    "docs",
    "frontend",
    "kwargs_typehints",
    "lints",
    "performance",
    "readme",
    "record",
    "self_test",
    "visual_cause",
]


class ToolMain(Protocol):
    """Describe the public entry point implemented by an Exactus tool."""

    def __call__(self, *, arguments: Sequence[str] | None = None) -> int:
        """Run a tool and return its process exit status.

        Args:
            arguments: Explicit tool arguments or ``None``.

        Returns:
            The tool's process exit status.

        """
        ...


@final
class ToolModule:
    """Load and execute Exactus tool modules lazily."""

    @classmethod
    def run(cls, *, name: str, arguments: Sequence[str] | None) -> int:
        """Load and run an Exactus tool.

        Args:
            name: Canonical tool identifier resolved through the
                catalog.
            arguments: Explicit tool arguments or ``None``.

        Returns:
            The tool's process exit status.

        Raises:
            TypeError: If the imported module has no callable ``main``.

        """
        spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=name,
        )
        module: ModuleType = import_module(
            name=(
                spec.module
                if spec is not None
                else f"exactus.tools.{name}.main"
            ),
        )
        main_attribute: ToolMain | None = cls._main(module=module)
        if main_attribute is None:
            msg: str = (
                f"Tool module {module.__name__!r} does not expose "
                "a callable main."
            )
            raise TypeError(msg)
        return main_attribute(
            arguments=(None if arguments is None else tuple(arguments)),
        )

    @staticmethod
    def _main(*, module: ModuleType) -> ToolMain | None:
        """Return a module's typed tool entry point when available.

        Args:
            module: Dynamically imported tool module.

        Returns:
            Typed tool entry point or ``None``.

        """
        value: ToolMain | None = getattr(module, "main", None)
        return value if callable(value) else None


def lints(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``lints`` tool: clean, lint, and type-check sources.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="lints", arguments=arguments)


def coverage_tests(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``coverage_tests`` tool: tests plus coverage reports.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="coverage_tests", arguments=arguments)


def docs(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``docs`` tool: documentation coverage and structure.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="docs", arguments=arguments)


def kwargs_typehints(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``kwargs_typehints`` tool: keyword-argument annotations.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="kwargs_typehints", arguments=arguments)


def readme(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``readme`` tool: README documentation coverage.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="readme", arguments=arguments)


def frontend(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``frontend`` tool: browser interactions and diagnostics.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="frontend", arguments=arguments)


def record(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``record`` tool: record and replay browser workflows.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="record", arguments=arguments)


def visual_cause(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``visual_cause`` tool: explain rendered CSS differences.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="visual_cause", arguments=arguments)


def performance(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``performance`` tool: profile tool step traces.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="performance", arguments=arguments)


def self_test(*, arguments: Sequence[str] | None = None) -> int:
    """Run the ``self_test`` tool: probe every reachable tool.

    Args:
        arguments: Optional argument tuple; ``sys.argv[1:]`` when
            ``None``.

    Returns:
        The tool's process exit status.

    """
    return ToolModule.run(name="self_test", arguments=arguments)
