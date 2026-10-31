# Copyright (c) 2026
"""Exercise the language-aware safe-span scanners in the renamer."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest

pytest.importorskip(modname="tree_sitter")
pytest.importorskip(modname="tree_sitter_language_pack")
from importlib import import_module

from exactus.tests.common.support import private_call, private_result
from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from rename_project import RenameRules, safe_dotted_spans

if TYPE_CHECKING:
    from pathlib import Path
    from re import Pattern
    from types import ModuleType
renamer: ModuleType = import_module(name="rename_project")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        first_line: Grouped module constant.
        python_docstring_line: Grouped module constant.
        python_value_line: Grouped module constant.
        python_fstring_line: Grouped module constant.
        sql_names_line: Grouped module constant.
        javascript_doc_line: Grouped module constant.
        javascript_string_line: Grouped module constant.
        javascript_comment_line: Grouped module constant.
        javascript_block_line: Grouped module constant.
        css_comment_line: Grouped module constant.
        markdown_heading_line: Grouped module constant.
        markdown_prose_line: Grouped module constant.
        markdown_fence_body: Grouped module constant.
        markdown_quote_line: Grouped module constant.
        text_tail_line: Grouped module constant.
        unicode_comment_line: Grouped module constant.
        python_source: Grouped module constant.
        sql_source: Grouped module constant.
        javascript_source: Grouped module constant.
        css_source: Grouped module constant.
        html_source: Grouped module constant.
        markdown_source: Grouped module constant.
        text_source: Grouped module constant.
        unicode_source: Grouped module constant.

    """

    first_line: Final[int] = 1
    python_docstring_line: Final[int] = 1
    python_value_line: Final[int] = 4
    python_fstring_line: Final[int] = 5
    sql_names_line: Final[int] = 1
    javascript_doc_line: Final[int] = 1
    javascript_string_line: Final[int] = 2
    javascript_comment_line: Final[int] = 6
    javascript_block_line: Final[int] = 7
    css_comment_line: Final[int] = 1
    markdown_heading_line: Final[int] = 1
    markdown_prose_line: Final[int] = 2
    markdown_fence_body: Final[int] = 5
    markdown_quote_line: Final[int] = 7
    text_tail_line: Final[int] = 2
    unicode_comment_line: Final[int] = 1
    python_source: Final[str] = dedent(
        text=(
            '    """Module docstring mentioning abc.cde."""\n    import abc.cd'
            'e\n    \n    VALUE = "abc.cde"  # trailing abc.cde comment\n    N'
            "AME = f\"{abc.cde} interpolated\"\n    '''module literal with ab"
            'c.cde\'\'\'\n    \n    def f():\n        """Docstring abc.cde."""'
            '\n        return abc.cde\n    \n    class K:\n        """Class do'
            'cstring abc.cde."""\n        x = \'abc.cde\'\n    # full-line abc'
            ".cde comment\n    "
        ),
    )
    sql_source: Final[str] = dedent(
        text=(
            '    SELECT "abc.cde", `abc.cde`, [abc.cde] FROM abc_cde\n    WHER'
            "E note = 'abc.cde' -- abc.cde tail comment\n    /* abc.cde block"
            "\n       comment */ SELECT 'unterminated abc.cde\n    "
        ),
    )
    javascript_source: Final[str] = dedent(
        text=(
            "    /** JSDoc abc.cde */\n    const s = 'abc.cde';\n    const t ="
            ' "abc.cde";\n    const u = `abc.cde`;\n    const v = `${abc.cde} '
            "sub`;\n    // line abc.cde\n    /* block abc.cde */\n    document"
            ".querySelector('div.abc-cde');\n    obj.getElementById('abc-cde')"
            ";\n    return abc.cde;\n    "
        ),
    )
    css_source: Final[str] = dedent(
        text=(
            "    /* abc.cde comment */\n    .abc-cde { content: 'abc.cde'; }\n"
            '    a::before { content: "abc.cde"; }\n    .x { color: red; }\n  '
            "  "
        ),
    )
    html_source: Final[str] = dedent(
        text=(
            "    <html><head><style>/* abc.cde */ .a { color: red }</style><sc"
            "ript>// abc.cde\n    var x = 'abc.cde';</script></head><body><!--"
            ' abc.cde --><p class="abc-cde">prose abc.cde text</p><p style=\'c'
            "olor: red'>abc.cde</p></body></html>\n    "
        ),
    )
    markdown_source: Final[str] = dedent(
        text=(
            "    # Heading abc.cde\n    Prose paragraph with abc.cde mention."
            "\n    `inline abc.cde code` and [a link](https://abc.cde/x).\n   "
            " ```python\n    abc.cde inside a fenced block\n    ```\n    > quo"
            "ted abc.cde prose\n    - list abc.cde item\n    "
        ),
    )
    text_source: Final[str] = "code abc.cde # comment abc.cde\nplain text\n"
    unicode_source: Final[str] = "// café ☕ abc.cde\nconst s = 'abc.cde';\n"


def _spans(text: str, suffix: str) -> dict[int, tuple[tuple[int, int], ...]]:
    """Call the dispatcher with positional-free arguments.

    Args:
        text: Source text to scan.
        suffix: File suffix selecting the scanner.

    Returns:
        Line-numbered safe spans.

    """
    return safe_dotted_spans(text=text, suffix=suffix)


def test_python_safe_spans_cover_strings_and_comments() -> None:
    """Python literals, docstrings, and comments are marked safe."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.python_source,
        suffix=".py",
    )
    expect_true(condition=bool(spans))
    docstring: tuple[tuple[int, int], ...] = spans[
        Constants.python_docstring_line
    ]
    expect_true(condition=docstring[0][0] == 0)
    expect_in(member=Constants.python_value_line, container=spans)


def test_python_safe_spans_fail_closed_on_syntax_error() -> None:
    """Malformed Python produces no safe regions."""
    expect_equal(actual=_spans(text="def (:\n", suffix=".py"), expected={})


def test_python_safe_spans_exclude_fstring_bodies() -> None:
    """Interpolated f-string lines keep no dotted-safe regions."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.python_source,
        suffix=".pyi",
    )
    expect_false(condition=Constants.python_fstring_line in spans)


def test_sql_safe_spans_skip_strings_and_comments() -> None:
    """SQL strings and comments are excluded; identifiers stay safe."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.sql_source,
        suffix=".sql",
    )
    expect_true(condition=Constants.sql_names_line in spans)
    first: tuple[tuple[int, int], ...] = spans[Constants.sql_names_line]
    expect_true(condition=first[0][0] == 0)


def test_javascript_safe_offsets_marks_literals() -> None:
    """JavaScript strings/templates/comments are marked; DOM calls stay out."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.javascript_source,
        suffix=".js",
    )
    expect_true(condition=Constants.javascript_doc_line in spans)
    expect_true(condition=Constants.javascript_string_line in spans)
    expect_true(condition=Constants.javascript_comment_line in spans)
    expect_true(condition=Constants.javascript_block_line in spans)


def test_typescript_safe_offsets_parse_ts_and_tsx() -> None:
    """TypeScript and TSX sources run through the JavaScript scanner."""
    expect_true(
        condition=bool(_spans(text=Constants.javascript_source, suffix=".ts")),
    )
    tsx: str = dedent(
        text=(
            "    const e = <div className='x'>hi</div>; // abc.cde\n    const "
            "s = 'abc.cde';\n    "
        ),
    )
    expect_true(condition=bool(_spans(text=tsx, suffix=".tsx")))


def test_css_safe_offsets_mark_strings_and_comments() -> None:
    """CSS comments and string values are marked; selectors stay out."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.css_source,
        suffix=".css",
    )
    expect_true(condition=Constants.css_comment_line in spans)


def test_html_safe_offsets_mark_prose_and_attributes() -> None:
    """HTML prose, quoted attributes, and embedded regions are marked."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.html_source,
        suffix=".html",
    )
    expect_true(condition=bool(spans))


def test_markdown_safe_offsets_mark_prose() -> None:
    """Markdown prose and quotes are marked; fenced code stays out."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.markdown_source,
        suffix=".md",
    )
    expect_true(condition=Constants.markdown_prose_line in spans)
    expect_true(condition=Constants.markdown_quote_line in spans)
    expect_false(condition=Constants.markdown_fence_body in spans)


def test_unknown_suffix_falls_back_to_comment_spans() -> None:
    """Unrecognized suffixes use the generic comment-span fallback."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.text_source,
        suffix=".txt",
    )
    expect_true(condition=bool(spans))
    expect_true(condition=Constants.text_tail_line in spans)


def test_non_ascii_text_maps_byte_offsets_to_characters() -> None:
    """Multi-byte text keeps character (not byte) span offsets."""
    spans: dict[int, tuple[tuple[int, int], ...]] = _spans(
        text=Constants.unicode_source,
        suffix=".js",
    )
    expect_true(condition=Constants.unicode_comment_line in spans)


def test_web_symbol_scanner_indexes_cross_references(tmp_path: Path) -> None:
    """The HTML/CSS/JS symbol scanner links classes, ids, and references.

    Args:
        tmp_path: Pytest temporary directory.

    """
    web: Path = tmp_path / "web"
    web.mkdir()
    _ = (web / "index.html").write_text(
        data=(
            dedent(
                text=(
                    '    <html><body><div id="abc-cde" class="x abc-cde"><'
                    "script src='abc-cde.js'></script></body></html>\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    _ = (web / "site.css").write_text(
        data=".abc-cde { color: red } #abc-cde { top: 0 }\n",
        encoding="utf-8",
    )
    _ = (web / "app.js").write_text(
        data="document.getElementById('abc-cde');\nfetch('abc-cde.json');\n",
        encoding="utf-8",
    )
    pattern, styles = cast(
        typ="tuple[Pattern[str], dict[str, tuple[str, ...]]]",
        val=private_result(
            owner=renamer,
            name="_name_matcher",
            kind=tuple,
            names=("abc_cde",),
        ),
    )
    rules: RenameRules = RenameRules(
        names=pattern,
        styles=styles,
        words=("foo", "bar"),
    )
    scanner: object = private_result(
        owner=renamer,
        name="_WebSymbols",
        kind=object,
        rules=rules,
    )
    for file in ("index.html", "site.css", "app.js"):
        private_call(owner=scanner, name="scan", path=web / file)
    graph: list[tuple[str, int, int]] = cast(
        typ="list[tuple[str, int, int]]",
        val=private_result(owner=scanner, name="graph", kind=list),
    )
    symbols: list[str] = [entry[0] for entry in graph]
    expect_true(condition=bool(symbols))
    expect_in(member="abc-cde", container=symbols)
