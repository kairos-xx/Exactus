# Copyright (c) 2026
"""JSON value types shared by the exactus tools."""

from __future__ import annotations

from json import dumps

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class JsonDict[T](dict[str, T]):
    """Dictionary with a formatted JSON representation."""

    @property
    def tojson(self) -> str:
        """Formatted JSON serialization of this dictionary.

        Returns:
            The dictionary serialized as formatted JSON.

        """
        return dumps(obj=self, ensure_ascii=False, indent=2, sort_keys=True)


type JsonObject = JsonDict[JsonValue]
