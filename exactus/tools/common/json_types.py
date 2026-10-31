# Copyright (c) 2026
"""JSON value types shared by the exactus tools."""

from __future__ import annotations

from json import dumps

type JsonScalar = str | int | float | bool | None
type JsonValue = (
    JsonDict[
        bool
        | dict[str, "JsonValue"]
        | float
        | int
        | list["JsonValue"]
        | str
        | None
    ]
    | JsonScalar
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)


class JsonDict[T](dict[str, T]):
    """Dictionary with a formatted JSON representation."""

    @property
    def tojson(self) -> str:
        """Formatted JSON serialization of this dictionary.

        Returns:
            The dictionary serialized as formatted JSON.

        """
        return dumps(
            obj={
                **{
                    key: self[key]
                    for key in ("title", "status", "tool", "summary")
                    if key in self
                },
                **{
                    key: self[key]
                    for key in sorted(self)
                    if key not in ("title", "status", "tool", "summary")
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )


type JsonObject = JsonDict[JsonValue]
