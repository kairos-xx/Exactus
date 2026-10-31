# Copyright (c) 2026
"""Round-trip coverage for the dependency-free TOML serializer."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.common.toml import TomlDocument, TomlSerializer

if TYPE_CHECKING:
    from collections.abc import Mapping
from tomllib import loads as toml_loads


def _roundtrip(*, document: TomlDocument) -> Mapping[str, object]:
    """Serialize ``document`` and parse the emitted text back.

    Args:
        document: Document to serialize.

    Returns:
        The parsed TOML mapping.

    """
    return toml_loads(TomlSerializer.dumps(value=document))


def test_scalars_roundtrip() -> None:
    """Primitive values survive a serialize/parse round trip."""
    document: TomlDocument = {
        "name": "exactus",
        "count": 7,
        "ratio": 1.5,
        "enabled": True,
        "disabled": False,
    }
    parsed: Mapping[str, object] = _roundtrip(document=document)
    expect_equal(actual=parsed["name"], expected="exactus")
    expect_equal(actual=parsed["count"], expected=7)
    expect_equal(actual=parsed["ratio"], expected=1.5)
    expect_equal(actual=parsed["enabled"], expected=True)
    expect_equal(actual=parsed["disabled"], expected=False)


def test_temporal_scalars_roundtrip() -> None:
    """Date, time, and datetime values serialize to ISO format."""
    stamp: datetime = datetime(
        year=2026,
        month=1,
        day=2,
        hour=3,
        minute=4,
        second=5,
        tzinfo=UTC,
    )
    document: TomlDocument = {
        "stamp": stamp,
        "day": date(year=2026, month=1, day=2),
        "moment": time(hour=3, minute=4, second=5),
    }
    parsed: Mapping[str, object] = _roundtrip(document=document)
    expect_equal(actual=parsed["stamp"], expected=stamp)
    expect_equal(
        actual=parsed["day"],
        expected=date(year=2026, month=1, day=2),
    )
    expect_equal(
        actual=parsed["moment"],
        expected=time(hour=3, minute=4, second=5),
    )


def test_nested_tables_emit_dotted_headers() -> None:
    """Nested dictionaries serialize under dotted table headers."""
    document: TomlDocument = {
        "tool": {
            "ruff": {"line-length": 79},
            "basedpyright": {"typeCheckingMode": "strict"},
        },
    }
    text: str = TomlSerializer.dumps(value=document)
    expect_true(condition="[tool.ruff]" in text, message="ruff header")
    expect_true(
        condition="[tool.basedpyright]" in text,
        message="basedpyright header",
    )
    expect_true(condition="[tool]" not in text, message="no bare tool header")
    parsed: Mapping[str, object] = _roundtrip(document=document)
    tool: object = parsed["tool"]
    expect_true(condition=isinstance(tool, dict), message="tool mapping")


def test_empty_table_keeps_header() -> None:
    """A table without entries still emits its header."""
    text: str = TomlSerializer.dumps(value={"empty": {}})
    expect_true(condition="[empty]" in text, message="empty header")
    parsed: Mapping[str, object] = _roundtrip(document={"empty": {}})
    expect_true(condition=isinstance(parsed["empty"], dict))


def test_scalar_arrays_roundtrip() -> None:
    """Arrays of scalars serialize inline."""
    document: TomlDocument = {
        "include": ["a.py", "b.py"],
        "numbers": [1, 2, 3],
    }
    parsed: Mapping[str, object] = _roundtrip(document=document)
    expect_equal(actual=parsed["include"], expected=["a.py", "b.py"])
    expect_equal(actual=parsed["numbers"], expected=[1, 2, 3])


def test_array_of_tables_roundtrip() -> None:
    """Arrays of dictionaries serialize as ``[[table]]`` blocks."""
    document: TomlDocument = {
        "items": [
            {"name": "first", "weight": 1},
            {"name": "second", "weight": 2},
        ],
    }
    text: str = TomlSerializer.dumps(value=document)
    expect_true(condition="[[items]]" in text, message="array header")
    parsed: Mapping[str, object] = _roundtrip(document=document)
    items: object = parsed["items"]
    expect_true(condition=isinstance(items, list), message="items list")


def test_array_of_tables_with_nested_tables() -> None:
    """Array-of-table entries keep nested sub-tables."""
    document: TomlDocument = {
        "items": [{"meta": {"level": 1}, "name": "entry"}],
    }
    parsed: Mapping[str, object] = _roundtrip(document=document)
    items: object = parsed["items"]
    expect_true(condition=isinstance(items, list), message="items list")


def test_mixed_array_rejects_tables() -> None:
    """An array holding dictionaries inside scalars is rejected."""
    document: TomlDocument = {"bad": ["a", {"b": 1}]}
    with pytest.raises(expected_exception=TypeError):
        _ = TomlSerializer.dumps(value=document)


def test_unsupported_type_rejected() -> None:
    """Unsupported scalar types raise ``TypeError``."""
    document: TomlDocument = cast(typ="TomlDocument", val={"bad": object()})
    with pytest.raises(expected_exception=TypeError):
        _ = TomlSerializer.dumps(value=document)


def test_non_finite_float_rejected() -> None:
    """NaN and infinity cannot be serialized."""
    document: TomlDocument = {"bad": float("inf")}
    with pytest.raises(expected_exception=ValueError, match="finite"):
        _ = TomlSerializer.dumps(value=document)


def test_non_bare_key_is_quoted() -> None:
    """Keys outside the bare-key pattern serialize quoted."""
    text: str = TomlSerializer.dumps(value={"project-includes": ["a"]})
    expect_true(
        condition='"project-includes" = ' not in text,
        message="bare hyphenated key stays bare",
    )
    quoted: str = TomlSerializer.dumps(value={"weird key": "v"})
    expect_true(condition='"weird key" = "v"' in quoted, message="quoted key")


def test_string_escaping() -> None:
    """Escapes serialize inside basic TOML strings."""
    document: TomlDocument = {"text": 'a"b\\c\n'}
    parsed: Mapping[str, object] = _roundtrip(document=document)
    expect_equal(actual=parsed["text"], expected='a"b\\c\n')


def test_generated_pyproject_shape() -> None:
    """The lints template serializes into a valid lint config."""
    document: TomlDocument = toml_loads(
        "\n        [tool.ruff]\n        line-length = 79\n\n        [tool."
        'basedpyright]\n        typeCheckingMode = "strict"\n        inclu'
        'de = ["a.py"]\n\n        [tool.pyrefly]\n        project-includes'
        ' = ["a.py"]\n        ',
    )
    parsed: Mapping[str, object] = _roundtrip(document=document)
    expect_equal(actual=parsed, expected=document)


def test_array_of_tables_with_nested_array_of_tables() -> None:
    """Nested arrays of tables serialize recursively and round-trip."""
    document: TomlDocument = {
        "groups": [
            {
                "name": "parent",
                "children": [
                    {"name": "first", "weight": 1},
                    {"name": "second", "weight": 2},
                ],
            },
        ],
    }
    text: str = TomlSerializer.dumps(value=document)
    expect_true(condition="[[groups]]" in text, message="parent array header")
    expect_true(
        condition="[[groups.children]]" in text,
        message="nested array header",
    )
    expect_equal(actual=_roundtrip(document=document), expected=document)
