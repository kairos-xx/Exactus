# Copyright (c) 2026
"""Comparison operators for mapping predicates."""

from __future__ import annotations

from re import error as regexerror
from re import search
from typing import TYPE_CHECKING, Final, Protocol

from .errors import MappingError

if TYPE_CHECKING:
    from .json_types import JsonValue


class Operator(Protocol):
    """Keyword-only comparison between a resolved value and an operand."""

    def __call__(self, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Compare ``actual`` against ``expected``.

        Args:
            actual: Resolved value.
            expected: Operand from the specification.

        Returns:
            The comparison result.

        """
        ...


class Constants:
    """Predicate constants.

    Attributes:
        empty_values: Values treated as empty.
        type_names: ``type_is`` names mapped to Python types.

    """

    empty_values: Final[tuple[object, ...]] = (None, "", [], {})
    type_names: Final[dict[str, tuple[type, ...]]] = {
        "str": (str,),
        "int": (int,),
        "float": (float,),
        "bool": (bool,),
        "list": (list,),
        "dict": (dict,),
        "null": (type(None),),
    }


class Operators:
    """Comparison operators keyed by their mapping-spec name."""

    @classmethod
    def not_empty(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Negate :meth:`empty`.

        Args:
            actual: Resolved value.
            expected: Unused operand.

        Returns:
            Whether the value is not empty.

        """
        return not cls.empty(actual=actual, expected=expected)

    @classmethod
    def not_in(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Negate :meth:`in_` for container operands.

        Args:
            actual: Resolved value.
            expected: Container operand.

        Returns:
            Whether the value is not a member.

        """
        if isinstance(expected, str | list | dict):
            return not cls.in_(actual=actual, expected=expected)
        return True

    @classmethod
    def gt(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``actual > expected`` for numbers or strings.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            The comparison, ``False`` for incomparable types.

        """
        return cls._ordered(name="gt", actual=actual, expected=expected)

    @classmethod
    def gte(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``actual >= expected`` for numbers or strings.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            The comparison, ``False`` for incomparable types.

        """
        return cls._ordered(name="gte", actual=actual, expected=expected)

    @classmethod
    def lt(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``actual < expected`` for numbers or strings.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            The comparison, ``False`` for incomparable types.

        """
        return cls._ordered(name="lt", actual=actual, expected=expected)

    @classmethod
    def lte(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``actual <= expected`` for numbers or strings.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            The comparison, ``False`` for incomparable types.

        """
        return cls._ordered(name="lte", actual=actual, expected=expected)

    @classmethod
    def table(cls) -> dict[str, Operator]:
        """Map specification names to operator callables.

        Returns:
            Every operator that takes a resolved value and an operand.

        """
        return {
            "truthy": cls.truthy,
            "falsy": cls.falsy,
            "empty": cls.empty,
            "not_empty": cls.not_empty,
            "eq": cls.eq,
            "ne": cls.ne,
            "gt": cls.gt,
            "gte": cls.gte,
            "lt": cls.lt,
            "lte": cls.lte,
            "contains": cls.contains,
            "in": cls.in_,
            "not_in": cls.not_in,
            "starts_with": cls.starts_with,
            "ends_with": cls.ends_with,
            "regex": cls.regex,
            "type_is": cls.type_is,
        }

    @staticmethod
    def truthy(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``bool(actual)``.

        Args:
            actual: Resolved value.
            expected: Unused operand.

        Returns:
            Whether the value is truthy.

        """
        del expected
        return bool(actual)

    @staticmethod
    def falsy(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test ``not actual``.

        Args:
            actual: Resolved value.
            expected: Unused operand.

        Returns:
            Whether the value is falsy.

        """
        del expected
        return not actual

    @staticmethod
    def empty(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test for null, empty string, empty list or empty dict.

        Args:
            actual: Resolved value.
            expected: Unused operand.

        Returns:
            Whether the value is empty.

        """
        del expected
        return actual in Constants.empty_values

    @staticmethod
    def eq(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test equality.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            Whether the two values are equal.

        """
        return actual == expected

    @staticmethod
    def ne(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test inequality.

        Args:
            actual: Resolved value.
            expected: Operand.

        Returns:
            Whether the two values differ.

        """
        return actual != expected

    @staticmethod
    def contains(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test that a container holds ``expected``.

        Args:
            actual: Resolved string, list or dict.
            expected: Member to look for.

        Returns:
            Whether the member is present.

        """
        if isinstance(actual, str):
            return isinstance(expected, str) and expected in actual
        if isinstance(actual, list | dict):
            return expected in actual
        return False

    @staticmethod
    def in_(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test that ``actual`` is a member of ``expected``.

        Args:
            actual: Resolved value.
            expected: Container operand.

        Returns:
            Whether the value is a member.

        """
        if isinstance(expected, str):
            return isinstance(actual, str) and actual in expected
        if isinstance(expected, list | dict):
            return actual in expected
        return False

    @staticmethod
    def starts_with(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test a string prefix.

        Args:
            actual: Resolved value.
            expected: Prefix.

        Returns:
            Whether both are strings and the prefix matches.

        """
        return (
            isinstance(actual, str)
            and isinstance(expected, str)
            and actual.startswith(expected)
        )

    @staticmethod
    def ends_with(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test a string suffix.

        Args:
            actual: Resolved value.
            expected: Suffix.

        Returns:
            Whether both are strings and the suffix matches.

        """
        return (
            isinstance(actual, str)
            and isinstance(expected, str)
            and actual.endswith(expected)
        )

    @staticmethod
    def regex(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test a regular-expression search.

        Args:
            actual: Resolved value.
            expected: Pattern.

        Returns:
            Whether both are strings and the pattern is found.

        Raises:
            MappingError: The pattern is not a valid regular expression.

        """
        if not (isinstance(actual, str) and isinstance(expected, str)):
            return False
        try:
            return search(pattern=expected, string=actual) is not None
        except regexerror as error:
            msg: str = f"Invalid regex: {error}"
            raise MappingError(msg) from error

    @staticmethod
    def type_is(*, actual: JsonValue, expected: JsonValue) -> bool:
        """Test the JSON type name of the value.

        Args:
            actual: Resolved value.
            expected: One of ``str int float bool list dict null``.

        Returns:
            Whether the type matches. ``bool`` is not an ``int``.

        """
        kinds: tuple[type, ...] = Constants.type_names.get(
            str(object=expected),
            (),
        )
        if isinstance(actual, bool):
            return bool in kinds
        return isinstance(actual, kinds) if kinds else False

    @classmethod
    def _ordered(
        cls,
        *,
        name: str,
        actual: JsonValue,
        expected: JsonValue,
    ) -> bool:
        """Dispatch an ordering comparison by operand type.

        Args:
            name: One of ``gt``, ``gte``, ``lt``, ``lte``.
            actual: Resolved value.
            expected: Operand.

        Returns:
            The result; booleans and mixed types never compare.

        """
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if isinstance(actual, int | float) and isinstance(
            expected,
            int | float,
        ):
            return cls._compare(
                name=name,
                left=float(actual),
                right=float(expected),
            )
        if isinstance(actual, str) and isinstance(expected, str):
            return cls._compare(name=name, left=actual, right=expected)
        return False

    @staticmethod
    def _compare[T: (float, str)](*, name: str, left: T, right: T) -> bool:
        """Apply the named ordering operator.

        Args:
            name: One of ``gt``, ``gte``, ``lt``, ``lte``.
            left: Left operand.
            right: Right operand of the same type.

        Returns:
            The comparison result.

        """
        match name:
            case "gt":
                return left > right
            case "gte":
                return left >= right
            case "lt":
                return left < right
            case _:
                return left <= right
