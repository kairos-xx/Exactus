# Copyright (c) 2026
"""Markdown filters format values for templates."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from jinja2 import Environment, select_autoescape

from exactus.packages.markdown.filters import MarkdownFilters
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def test_text_escape_and_code() -> None:
    """Scalars stringify, structures dump as JSON, escapes apply."""
    expect_equal(actual=MarkdownFilters.text(value=None), expected="")
    expect_equal(
        actual=MarkdownFilters.text(value=[1, "a"]),
        expected='[1, "a"]',
    )
    expect_equal(
        actual=MarkdownFilters.escape(value="a*b|c"),
        expected="a\\*b\\|c",
    )
    expect_equal(actual=MarkdownFilters.code(value=None), expected="``")
    expect_equal(actual=MarkdownFilters.code(value="x"), expected="`x`")


def test_table_preserves_dunder_paths_and_titles() -> None:
    """Dunder filenames stay literal instead of becoming Markdown emphasis."""
    expect_in(
        member="| `pkg/__init__.py` | `pkg/__init__.py needs coverage` |",
        container=MarkdownFilters.render_table(
            value=[
                {
                    "path": "pkg/__init__.py",
                    "title": "pkg/__init__.py needs coverage",
                },
            ],
            columns=("Path:path", "Title:title"),
        ),
    )


def test_codeblock_bullets_numbered() -> None:
    """Fences and lists render one line per item."""
    expect_equal(
        actual=MarkdownFilters.codeblock(value="x", language="py"),
        expected="```py\nx\n```",
    )
    expect_equal(
        actual=MarkdownFilters.bullets(value=["a", "b"]),
        expected="- a\n- b",
    )
    expect_equal(actual=MarkdownFilters.bullets(value="a"), expected="- a")
    expect_equal(
        actual=MarkdownFilters.bullets(value=[{"n": 1}, {"n": 2}], path="n"),
        expected="- 1\n- 2",
    )
    expect_equal(
        actual=MarkdownFilters.numbered(value=["a", "b"]),
        expected="1. a\n2. b",
    )


def test_table_with_columns_escapes_cells() -> None:
    """Pipes and newlines in cells cannot break the table."""
    rows: list[JsonValue] = [{"name": "a|b", "score": 1, "note": "x\ny"}]
    expect_equal(
        actual=MarkdownFilters.render_table(
            value=rows,
            columns=("Name:name", "Score:score", "note"),
        ),
        expected=(
            dedent(
                text=(
                    "    | Name | Score | note |\n    | --- | --- | --- |"
                    "\n    | a\\|b | 1 | x<br>y |"
                ),
            )
        ),
    )


def test_table_defaults_and_empty() -> None:
    """Without columns the first row's keys head the table."""
    expect_equal(
        actual=MarkdownFilters.render_table(
            value=[{"a": 1, "b": 2}],
            columns=(),
        ),
        expected="| a | b |\n| --- | --- |\n| 1 | 2 |",
    )
    expect_equal(
        actual=MarkdownFilters.render_table(value=[], columns=()),
        expected="",
    )
    expect_equal(
        actual=MarkdownFilters.render_table(value="nope", columns=()),
        expected="",
    )


def test_json_filters_and_registration() -> None:
    """JSON filters keep unicode; ``register`` installs every filter."""
    expect_equal(
        actual=MarkdownFilters.to_json(value={"a": "é"}),
        expected='{\n  "a": "é"\n}',
    )
    expect_equal(
        actual=MarkdownFilters.compact_json(value={"a": [1, 2]}),
        expected='{"a":[1,2]}',
    )
    env: Environment = Environment(
        autoescape=select_autoescape(default=False, default_for_string=False),
    )
    MarkdownFilters.register(env=env)
    for name in (
        "md_escape",
        "md_code",
        "md_codeblock",
        "md_bullets",
        "md_numbered",
        "md_table",
        "json",
        "compact_json",
    ):
        expect_in(member=name, container=env.filters)


def test_table_filter_accepts_positional_columns_from_templates() -> None:
    """Jinja2 passes the rows and column specs to ``md_table`` positionally."""
    env: Environment = Environment(
        autoescape=select_autoescape(default=False, default_for_string=False),
    )
    MarkdownFilters.register(env=env)
    rendered: str = env.from_string(
        source='{{ rows | md_table("Name:name") }}',
    ).render(rows=[{"name": "a"}])
    expect_equal(actual=rendered, expected="| Name |\n| --- |\n| a |")


def test_cell_escapes_pipes_and_every_line_break() -> None:
    """``md_cell`` escapes ``|`` and turns CR, LF and CRLF into ``<br>``."""
    expect_equal(
        actual=MarkdownFilters.cell(value="a|b\r\nc\rd\ne"),
        expected="a\\|b<br>c<br>d<br>e",
    )
    env: Environment = Environment(autoescape=select_autoescape(default=False))
    MarkdownFilters.register(env=env)
    expect_equal(
        actual=env.from_string(source='{{ "x|y" | md_cell }}').render(),
        expected="x\\|y",
    )


def test_table_normalizes_crlf_cells_and_pipe_headers() -> None:
    """Table cells and headers are single-line and pipe-safe."""
    table: str = MarkdownFilters.render_table(
        value=[{"a": "one\r\ntwo"}],
        columns=("A|B:a",),
    )
    expect_equal(actual=table, expected="| A\\|B |\n| --- |\n| one<br>two |")
