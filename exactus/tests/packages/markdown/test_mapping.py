# Copyright (c) 2026
"""Mapping specs reshape a source document into a template context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.markdown.errors import MappingError
from exactus.packages.markdown.mapping import Mapper
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        source: Grouped module constant.

    """

    source: Final[dict[str, JsonValue]] = {
        "project": {"name": "Exactus", "owner": None},
        "tasks": [
            {
                "id": 1,
                "title": "Run Ruff",
                "status": "open",
                "priority": 100,
                "owner": {"name": "Alice"},
            },
            {
                "id": 2,
                "title": "Run Pyright",
                "status": "open",
                "priority": 90,
                "owner": {"name": "Bob"},
            },
            {
                "id": 3,
                "title": "Old",
                "status": "done",
                "priority": 10,
                "owner": None,
            },
        ],
        "tags": ["python", "exactus", "python"],
        "nested": [[1, 2], [3]],
        "box": {"a": 1, "b": 2, "c": 3},
    }


class StubRenderer:
    """Renderer that echoes its inputs instead of using Jinja2."""

    def __call__(self, *, name: str, context: dict[str, JsonValue]) -> str:
        """Describe the render request.

        Args:
            name: Template name.
            context: Render context.

        Returns:
            ``name|item|index`` for assertions.

        """
        return f"{name}|{context['item']}|{context.get('index', '-')}"


def _map(*, spec: JsonValue) -> JsonValue:
    """Map ``spec`` against ``SOURCE``.

    Args:
        spec: Mapping specification.

    Returns:
        The mapped value.

    """
    mapper: Mapper = Mapper(renderer=StubRenderer())
    return mapper.map_value(
        spec=spec,
        current=Constants.source,
        root=Constants.source,
    )


def test_paths_literals_and_structures() -> None:
    """Strings are paths; plain dicts and lists map element-wise."""
    expect_equal(actual=_map(spec="project.name"), expected="Exactus")
    expect_equal(actual=_map(spec="nope"), expected=None)
    expect_equal(actual=_map(spec=5), expected=5)
    expect_equal(
        actual=_map(spec={"n": "project.name", "t": ["tags[0]"]}),
        expected={"n": "Exactus", "t": ["python"]},
    )
    expect_equal(actual=_map(spec={"$literal": "x"}), expected="x")


def test_default_required_and_default_on_null() -> None:
    """Defaults fill absent or null paths; required paths must exist."""
    expect_equal(
        actual=_map(spec={"$path": "nope", "$default": "d"}),
        expected="d",
    )
    expect_equal(
        actual=_map(
            spec={
                "$path": "project.owner",
                "$default": "nobody",
                "$default_on_null": True,
            },
        ),
        expected="nobody",
    )
    expect_equal(
        actual=_map(spec={"$path": "project.owner", "$default": "nobody"}),
        expected=None,
    )
    with pytest.raises(
        expected_exception=MappingError,
        match="Required path missing",
    ):
        _map(spec={"$path": "nope", "$required": True})


def test_when_coalesce_and_merge() -> None:
    """Conditionals, fallbacks and object merges compose."""
    expect_equal(
        actual=_map(
            spec={
                "$when": {
                    "$path": "project.name",
                    "$op": "eq",
                    "$value": "Exactus",
                },
                "$then": {"$literal": "yes"},
                "$else": {"$literal": "no"},
            },
        ),
        expected="yes",
    )
    expect_equal(
        actual=_map(
            spec={"$coalesce": ["nope", "project.owner", "project.name"]},
        ),
        expected="Exactus",
    )
    expect_equal(
        actual=_map(spec={"$coalesce": ["nope"], "$default": "d"}),
        expected="d",
    )
    expect_equal(
        actual=_map(spec={"$merge": ["box", {"z": 9}]}),
        expected={"a": 1, "b": 2, "c": 3, "z": 9},
    )
    with pytest.raises(
        expected_exception=MappingError,
        match="must be objects",
    ):
        _map(spec={"$merge": ["tags"]})


def test_where_sort_each_pipeline() -> None:
    """Filter, numeric sort and projection run in a fixed order."""
    result: JsonValue = _map(
        spec={
            "$path": "tasks",
            "$where": {"$path": "status", "$op": "ne", "$value": "done"},
            "$sort_by": "priority",
            "$reverse": True,
            "$each": {"id": "id", "owner": "owner.name"},
        },
    )
    expect_equal(
        actual=result,
        expected=[{"id": 1, "owner": "Alice"}, {"id": 2, "owner": "Bob"}],
    )


def test_sort_is_numeric_and_text_is_case_insensitive() -> None:
    """Numbers sort by value, strings sort casefolded after numbers."""
    ascending: JsonValue = _map(
        spec={"$path": "tasks", "$sort_by": "priority", "$each": "id"},
    )
    expect_equal(actual=ascending, expected=[3, 2, 1])
    titles: JsonValue = _map(
        spec={"$path": "tasks", "$sort_by": "title", "$each": "id"},
    )
    expect_equal(actual=titles, expected=[3, 2, 1])


def test_unique_slice_flatten_pick_omit_join() -> None:
    """List and object reshaping directives."""
    expect_equal(
        actual=_map(spec={"$path": "tags", "$unique": True}),
        expected=["python", "exactus"],
    )
    expect_equal(
        actual=_map(
            spec={"$path": "tasks", "$unique_by": "status", "$each": "id"},
        ),
        expected=[1, 3],
    )
    expect_equal(
        actual=_map(
            spec={"$path": "tasks", "$offset": 1, "$limit": 1, "$each": "id"},
        ),
        expected=[2],
    )
    expect_equal(
        actual=_map(spec={"$path": "nested", "$flatten": True}),
        expected=[1, 2, 3],
    )
    expect_equal(
        actual=_map(spec={"$path": "box", "$pick": ["a", "c", "zz"]}),
        expected={"a": 1, "c": 3},
    )
    expect_equal(
        actual=_map(spec={"$path": "box", "$omit": ["a"]}),
        expected={"b": 2, "c": 3},
    )
    expect_equal(
        actual=_map(spec={"$path": "tags", "$unique": True, "$join": ", "}),
        expected="python, exactus",
    )


def test_template_and_template_each() -> None:
    """Nested templates render once or once per item."""
    expect_equal(
        actual=_map(spec={"$path": "project.name", "$template": "t.md"}),
        expected="t.md|Exactus|-",
    )
    expect_equal(
        actual=_map(
            spec={
                "$path": "tags",
                "$unique": True,
                "$template": "t.md",
                "$template_each": True,
                "$separator": "; ",
            },
        ),
        expected="t.md|python|0; t.md|exactus|1",
    )


def test_wrong_value_kinds_name_the_directive() -> None:
    """Directives report which one received the wrong value type."""
    for key, path, text in (
        ("$where", "box", "$where requires a list"),
        ("$each", "box", "$each requires a list"),
        ("$pick", "tags", "$pick requires an object"),
        ("$offset", "tags", "$offset requires an integer"),
    ):
        spec: JsonValue = {
            "$path": path,
            key: ["a"] if key == "$pick" else True,
        }
        if key == "$offset":
            spec = {"$path": path, key: "one"}
        with pytest.raises(
            expected_exception=MappingError,
            match=text.replace("$", "\\$"),
        ):
            _map(spec=spec)


def test_context_exposes_source_and_data() -> None:
    """The template context always carries the original document."""
    mapper: Mapper = Mapper(renderer=StubRenderer())
    plain: dict[str, JsonValue] = mapper.context(
        source=Constants.source,
        mapping=None,
    )
    expect_in(member="project", container=plain)
    expect_equal(actual=plain["source"], expected=Constants.source)
    wrapped: dict[str, JsonValue] = mapper.context(source=[1, 2], mapping=None)
    expect_equal(actual=wrapped, expected={"data": [1, 2], "source": [1, 2]})
    mapped: dict[str, JsonValue] = mapper.context(
        source=Constants.source,
        mapping={"name": "project.name"},
    )
    expect_equal(actual=mapped["name"], expected="Exactus")
    expect_equal(actual=mapped["source"], expected=Constants.source)
