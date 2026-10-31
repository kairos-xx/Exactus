# Copyright (c) 2026 Project contributors.
"""Dependency-free TOML serializer compatible with tomllib."""

from __future__ import annotations

from datetime import date, datetime, time
from math import isfinite
from re import fullmatch
from typing import Final

type TomlScalar = str | int | float | bool | datetime | date | time
type TomlValue = TomlScalar | list["TomlValue"] | dict[str, "TomlValue"]
type TomlDocument = dict[str, TomlValue]


class TomlSerializer:
    """Serialize Python values into TOML accepted by tomllib.

    Attributes:
        bare_key_pattern: Regular expression pattern for valid bare keys.

    """

    bare_key_pattern: Final[str] = r"[A-Za-z0-9_-]+"

    @classmethod
    def dumps(cls, *, value: TomlDocument) -> str:
        """Serialize a TOML document.

        Args:
            value: Document to serialize.

        Returns:
            Serialized TOML text.

        """
        lines: list[str] = []
        cls._write_table(lines=lines, path=(), table=value, emit_header=False)
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def _write_table(
        cls,
        *,
        lines: list[str],
        path: tuple[str, ...],
        table: dict[str, TomlValue],
        emit_header: bool,
    ) -> None:
        """Write one TOML table recursively.

        Args:
            lines: Destination lines.
            path: Table path.
            table: Table values.
            emit_header: Whether to emit the table header.

        """
        scalars: list[tuple[str, TomlValue]] = []
        tables: list[tuple[str, dict[str, TomlValue]]] = []
        arrays: list[tuple[str, list[dict[str, TomlValue]]]] = []
        for key, value in table.items():
            if isinstance(value, dict):
                tables.append((key, value))
                continue
            array_tables: list[dict[str, TomlValue]] | None = (
                cls._array_of_tables(value=value)
            )
            if array_tables is not None:
                arrays.append((key, array_tables))
                continue
            scalars.append((key, value))
        if emit_header and (scalars or arrays or not tables):
            if lines and lines[-1]:
                lines.append("")
            lines.append(f"[{cls._path(path=path)}]")
        for key, value in scalars:
            lines.append(f"{cls._key(value=key)} = {cls._value(value=value)}")
        for key, child in tables:
            cls._write_table(
                lines=lines,
                path=(*path, key),
                table=child,
                emit_header=True,
            )
        for key, items in arrays:
            cls._write_array_tables(
                lines=lines,
                path=(*path, key),
                items=items,
            )

    @classmethod
    def _write_array_tables(
        cls,
        *,
        lines: list[str],
        path: tuple[str, ...],
        items: list[dict[str, TomlValue]],
    ) -> None:
        """Write an array of TOML tables.

        Args:
            lines: Destination lines.
            path: Array-table path.
            items: Table items.

        """
        for item in items:
            if lines and lines[-1]:
                lines.append("")
            lines.append(f"[[{cls._path(path=path)}]]")
            scalars: list[tuple[str, TomlValue]] = []
            tables: list[tuple[str, dict[str, TomlValue]]] = []
            arrays: list[tuple[str, list[dict[str, TomlValue]]]] = []
            for key, value in item.items():
                if isinstance(value, dict):
                    tables.append((key, value))
                    continue
                array_tables: list[dict[str, TomlValue]] | None = (
                    cls._array_of_tables(value=value)
                )
                if array_tables is not None:
                    arrays.append((key, array_tables))
                    continue
                scalars.append((key, value))
            for key, value in scalars:
                lines.append(
                    f"{cls._key(value=key)} = {cls._value(value=value)}",
                )
            for key, child in tables:
                cls._write_table(
                    lines=lines,
                    path=(*path, key),
                    table=child,
                    emit_header=True,
                )
            for key, children in arrays:
                cls._write_array_tables(
                    lines=lines,
                    path=(*path, key),
                    items=children,
                )

    @classmethod
    def _value(cls, *, value: TomlValue) -> str:
        """Serialize one TOML value.

        Args:
            value: Value to serialize.

        Returns:
            TOML representation.

        Raises:
            TypeError: If the value cannot be serialized.
            ValueError: If a float is not finite.

        """
        if isinstance(value, str):
            return cls._string(value=value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(object=value)
        if isinstance(value, float):
            if not isfinite(value):
                msg: str = "TOML float must be finite."
                raise ValueError(msg)
            return repr(value)
        if isinstance(value, datetime | date | time):
            return value.isoformat()
        if isinstance(value, list):
            return cls._array(value=value)
        msg = f"Unsupported TOML value type: {type(value).__qualname__}"
        raise TypeError(msg)

    @classmethod
    def _array(cls, *, value: list[TomlValue]) -> str:
        """Serialize a regular TOML array.

        Args:
            value: Array values.

        Returns:
            TOML array representation.

        Raises:
            TypeError: If the array contains tables.

        """
        if any(isinstance(item, dict) for item in value):
            msg: str = "Tables must be emitted as TOML arrays of tables."
            raise TypeError(msg)
        return "[" + ", ".join(cls._value(value=item) for item in value) + "]"

    @classmethod
    def _path(cls, *, path: tuple[str, ...]) -> str:
        """Serialize a dotted TOML path.

        Args:
            path: Path components.

        Returns:
            Serialized path.

        """
        return ".".join(cls._key(value=component) for component in path)

    @classmethod
    def _key(cls, *, value: str) -> str:
        """Serialize a TOML key.

        Args:
            value: Key.

        Returns:
            Serialized key.

        """
        if fullmatch(pattern=cls.bare_key_pattern, string=value):
            return value
        return cls._string(value=value)

    @staticmethod
    def _array_of_tables(
        *,
        value: TomlValue,
    ) -> list[dict[str, TomlValue]] | None:
        """Return an array of tables when the value represents one.

        Args:
            value: Value to inspect.

        Returns:
            Array of tables, otherwise None.

        """
        if not isinstance(value, list) or not value:
            return None
        if not all(isinstance(item, dict) for item in value):
            return None
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _string(*, value: str) -> str:
        """Serialize a basic TOML string.

        Args:
            value: String.

        Returns:
            Escaped TOML string.

        """
        escaped: str = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\b", "\\b")
            .replace("\t", "\\t")
            .replace("\n", "\\n")
            .replace("\f", "\\f")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
