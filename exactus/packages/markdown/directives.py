# Copyright (c) 2026
"""Base types for mapping directives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Protocol

from .errors import MappingError

if TYPE_CHECKING:
    from .json_types import JsonValue


class MappingHost(Protocol):
    """Services a directive step needs from the mapper."""

    def map_value(
        self,
        *,
        spec: JsonValue,
        current: JsonValue,
        root: JsonValue,
    ) -> JsonValue:
        """Map a nested specification.

        Args:
            spec: Nested mapping specification.
            current: Value relative paths start from.
            root: Whole document.

        Returns:
            The mapped value.

        """
        ...

    def render_name(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Render a named template.

        Args:
            name: Template name relative to a configured root.
            context: Render context.

        Returns:
            The rendered text.

        """
        ...


class Step(ABC):
    """One mapping directive applied to a resolved value.

    Attributes:
        keys: Specification keys that activate this step.

    """

    keys: ClassVar[tuple[str, ...]] = ()

    @staticmethod
    def items(*, value: JsonValue, directive: str) -> list[JsonValue]:
        """Require a list.

        Args:
            value: Value to check.
            directive: Directive name for the error message.

        Returns:
            The list.

        Raises:
            MappingError: The value is not a list.

        """
        if not isinstance(value, list):
            msg: str = f"{directive} requires a list"
            raise MappingError(msg)
        return value

    @staticmethod
    def members(*, value: JsonValue, directive: str) -> dict[str, JsonValue]:
        """Require an object.

        Args:
            value: Value to check.
            directive: Directive name for the error message.

        Returns:
            The object.

        Raises:
            MappingError: The value is not an object.

        """
        if not isinstance(value, dict):
            msg: str = f"{directive} requires an object"
            raise MappingError(msg)
        return value

    @staticmethod
    def integer(*, value: JsonValue, directive: str, default: int) -> int:
        """Require an integer, or return ``default`` for ``None``.

        Args:
            value: Value to check.
            directive: Directive name for the error message.
            default: Result when ``value`` is ``None``.

        Returns:
            The integer.

        Raises:
            MappingError: The value is neither ``None`` nor an integer.

        """
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, int):
            msg: str = f"{directive} requires an integer"
            raise MappingError(msg)
        return value

    def applies(self, *, spec: dict[str, JsonValue]) -> bool:
        """Report whether the specification activates this step.

        Args:
            spec: Mapping specification object.

        Returns:
            Whether any of this step's keys is present.

        """
        return any(key in spec for key in self.keys)

    @abstractmethod
    def apply(
        self,
        *,
        value: JsonValue,
        spec: dict[str, JsonValue],
        root: JsonValue,
        host: MappingHost,
    ) -> JsonValue:
        """Transform ``value`` according to ``spec``.

        Args:
            value: Value produced by earlier steps.
            spec: Mapping specification object.
            root: Whole document.
            host: Mapper services for nested mapping and rendering.

        Returns:
            The transformed value.

        """
