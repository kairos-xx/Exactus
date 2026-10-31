# Copyright (c) 2026
"""Evaluate mapping predicates against JSON values."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from .errors import MappingError
from .operators import Operators
from .paths import Lookup, PathResolver

if TYPE_CHECKING:
    from .json_types import JsonValue
    from .operators import Operator


class Constants:
    """Predicate constants.

    Attributes:
        presence_ops: Operators that test path presence only.

    """

    presence_ops: Final[frozenset[str]] = frozenset({"exists", "missing"})


class Predicates:
    """Evaluate predicate specifications."""

    @classmethod
    def evaluate(
        cls,
        *,
        spec: JsonValue,
        current: JsonValue,
        root: JsonValue,
    ) -> bool:
        """Evaluate one predicate specification.

        Args:
            spec: A bool, a combinator object, a ``$path`` comparison or
                an equality shorthand object.
            current: Value that relative paths start from.
            root: Whole document, for ``$.`` paths.

        Returns:
            The predicate result.

        Raises:
            MappingError: The specification is malformed.

        """
        if isinstance(spec, bool):
            return spec
        if not isinstance(spec, dict):
            msg: str = "Predicate must be an object or boolean"
            raise MappingError(msg)
        if "$and" in spec:
            return all(
                cls._each(spec=spec, key="$and", current=current, root=root),
            )
        if "$or" in spec:
            return any(
                cls._each(spec=spec, key="$or", current=current, root=root),
            )
        if "$not" in spec:
            return not cls.evaluate(
                spec=spec["$not"],
                current=current,
                root=root,
            )
        if "$path" not in spec:
            return all(
                cls._equals(
                    lookup=PathResolver.resolve(
                        current=current,
                        path=path,
                        root=root,
                    ),
                    expected=expected,
                )
                for path, expected in spec.items()
            )
        return cls._compare(spec=spec, current=current, root=root)

    @classmethod
    def _each(
        cls,
        *,
        spec: dict[str, JsonValue],
        key: str,
        current: JsonValue,
        root: JsonValue,
    ) -> list[bool]:
        """Evaluate every operand of a combinator.

        Args:
            spec: The combinator object.
            key: ``$and`` or ``$or``.
            current: Value that relative paths start from.
            root: Whole document.

        Returns:
            One result per operand.

        Raises:
            MappingError: The operand is not a list.

        """
        operands: JsonValue = spec[key]
        if not isinstance(operands, list):
            msg: str = f"{key} requires a list"
            raise MappingError(msg)
        return [
            cls.evaluate(spec=operand, current=current, root=root)
            for operand in operands
        ]

    @staticmethod
    def _equals(*, lookup: Lookup, expected: JsonValue) -> bool:
        """Test that a resolved path exists and equals ``expected``.

        Args:
            lookup: Resolved path outcome.
            expected: Expected value.

        Returns:
            ``False`` when the path is missing, else equality.

        """
        return lookup.found and lookup.value == expected

    @staticmethod
    def _compare(
        *,
        spec: dict[str, JsonValue],
        current: JsonValue,
        root: JsonValue,
    ) -> bool:
        """Evaluate a ``$path`` / ``$op`` / ``$value`` comparison.

        Args:
            spec: The comparison object.
            current: Value that relative paths start from.
            root: Whole document.

        Returns:
            The comparison result; ``False`` when the path is absent
            (except for ``exists`` and ``missing``).

        Raises:
            MappingError: The operator is unknown.

        """
        lookup: Lookup = PathResolver.resolve(
            current=current,
            path=str(object=spec["$path"]),
            root=root,
        )
        name: str = str(object=spec.get("$op", "truthy"))
        if name in Constants.presence_ops:
            return lookup.found == (name == "exists")
        operator: Operator | None = Operators.table().get(name)
        if operator is None:
            msg: str = f"Unknown operator: {name}"
            raise MappingError(msg)
        if not lookup.found:
            return False
        return operator(actual=lookup.value, expected=spec.get("$value"))
