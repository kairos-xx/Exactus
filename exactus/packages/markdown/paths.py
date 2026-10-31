# Copyright (c) 2026
"""Resolve JSON path expressions against nested documents."""

from __future__ import annotations

from dataclasses import dataclass
from re import Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, Self

if TYPE_CHECKING:
    from .json_types import JsonValue


class Constants:
    """Path grammar constants.

    Attributes:
        root_marker: Path meaning the whole document.
        root_anchor: Prefix anchoring a path at the document root.
        current_paths: Paths meaning the current value.
        token: One path step: a key name or a ``[n]`` list index.

    """

    root_marker: Final[str] = "$"
    root_anchor: Final[str] = "$."
    current_paths: Final[frozenset[str]] = frozenset({"", "."})
    token: Final[Pattern[str]] = compile_pattern(
        pattern=r"([^.\[\]]+)|\[(\d+)\]",
    )


@dataclass(frozen=True, slots=True)
class Lookup:
    """Outcome of resolving a path.

    Attributes:
        found: Whether every step of the path existed.
        value: The resolved value, or ``None`` when not found.

    """

    found: bool
    value: JsonValue = None

    @classmethod
    def hit(cls: type[Self], *, value: JsonValue) -> Self:
        """Build a successful lookup.

        Args:
            value: The resolved value.

        Returns:
            A lookup with ``found`` set.

        """
        return cls(found=True, value=value)

    @classmethod
    def miss(cls: type[Self]) -> Self:
        """Build a failed lookup.

        Returns:
            A lookup with ``found`` unset.

        """
        return cls(found=False, value=None)


class PathResolver:
    """Walk dict keys and list indexes described by a path string."""

    @classmethod
    def resolve(
        cls,
        *,
        current: JsonValue,
        path: str,
        root: JsonValue,
    ) -> Lookup:
        """Resolve ``path`` from ``current`` or from ``root``.

        Args:
            current: Value that relative paths start from.
            path: Path expression such as ``a.b[0]`` or ``$.a``.
            root: Whole document, used by ``$`` and ``$.`` paths.

        Returns:
            A hit with the value, or a miss when any step is absent.

        """
        if path in Constants.current_paths:
            return Lookup.hit(value=current)
        if path == Constants.root_marker:
            return Lookup.hit(value=root)
        target: JsonValue = (
            root if path.startswith(Constants.root_anchor) else current
        )
        text: str = path.removeprefix(Constants.root_anchor)
        for name, index in Constants.token.findall(string=text):
            step: Lookup = cls._step(target=target, name=name, index=index)
            if not step.found:
                return step
            target = step.value
        return Lookup.hit(value=target)

    @staticmethod
    def _step(*, target: JsonValue, name: str, index: str) -> Lookup:
        """Take one path step.

        Args:
            target: Value to descend into.
            name: Dict key, empty when this is an index step.
            index: List index digits, empty when this is a key step.

        Returns:
            The child lookup, or a miss.

        """
        if index:
            position: int = int(index)
            if isinstance(target, list) and position < len(target):
                return Lookup.hit(value=target[position])
            return Lookup.miss()
        if isinstance(target, dict) and name in target:
            return Lookup.hit(value=target[name])
        return Lookup.miss()
