"""Adversarial semantic-safety tests for rename_project."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from re import Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, final

import pytest

pytest.importorskip(modname="tree_sitter")
pytest.importorskip(modname="tree_sitter_language_pack")
from inspect import getfile

from exactus.tests.packages.rename_project.assertions import (
    expect_equal,
    expect_false,
    expect_not_none,
    expect_true,
)
from rename_project import (
    byte_boundaries,
    byte_to_character,
    parse_tree,
    safe_dotted_spans,
    span_contained,
    structurally_valid_rewrite,
)

if TYPE_CHECKING:
    from tree_sitter import Node


class Expected(StrEnum):
    """Expected disposition of an ``abc.cde`` occurrence.

    Attributes:
        GUARDED: Guarded.
        SAFE: Safe.

    """

    SAFE = "safe"
    GUARDED = "guarded"


@dataclass(frozen=True, slots=True)
class Case:
    """One adversarial source specimen.

    Attributes:
        expected: Expected.
        name: Name.
        source: Source.
        suffix: Suffix.

    """

    name: str
    suffix: str
    source: str
    expected: tuple[Expected, ...]


def _generated_cases() -> tuple[Case, ...]:
    """Generate syntax/layout variants around high-risk constructs.

    Returns:
        The resulting value.

    """
    cases: list[Case] = []
    unicode_prefixes: tuple[str, ...] = ("", "João ", "日本語 ", "🙂 ")
    quotes: tuple[str, ...] = ('"', "'")
    for index, prefix in enumerate(iterable=unicode_prefixes):
        for quote in quotes:
            cases.extend(
                (
                    Case(
                        name=f"gen-py-string-{index}-{ord(quote)}",
                        suffix=".py",
                        source=f"""\
x = {quote}{prefix}abc.cde{quote}
""",
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-js-string-{index}-{ord(quote)}",
                        suffix=".js",
                        source=f"""\
const x = {quote}{prefix}abc.cde{quote};
""",
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-css-string-{index}-{ord(quote)}",
                        suffix=".css",
                        source=(
                            f"""\
x {{ content: {quote}{prefix}abc.cde{quote}; }}
"""
                        ),
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-html-attribute-{index}-{ord(quote)}",
                        suffix=".html",
                        source=(
                            f"""\
<div title={quote}{prefix}abc.cde{quote}></div>
"""
                        ),
                        expected=(Expected.SAFE,),
                    ),
                ),
            )
    whitespace: tuple[str, ...] = ("", " ", "  ", "\t")
    for index, gap in enumerate(iterable=whitespace):
        cases.extend(
            (
                Case(
                    name=f"gen-py-member-{index}",
                    suffix=".py",
                    source=f"""\
x ={gap}abc.cde
""",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-js-member-{index}",
                    suffix=".js",
                    source=f"""\
const x ={gap}abc.cde;
""",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-css-selector-{index}",
                    suffix=".css",
                    source=f"""\
abc.cde{gap}{{ color: red; }}
""",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-html-script-member-{index}",
                    suffix=".html",
                    source=f"""\
<script>const x ={gap}abc.cde;</script>
""",
                    expected=(Expected.GUARDED,),
                ),
            ),
        )
    selector_methods: tuple[str, ...] = (
        "querySelector",
        "querySelectorAll",
        "matches",
        "closest",
    )
    cases.extend(
        Case(
            name=f"gen-js-selector-{method}-{ord(quote)}",
            suffix=".js",
            source=f"""\
node.{method}({quote}abc.cde{quote});
""",
            expected=(Expected.GUARDED,),
        )
        for method in selector_methods
        for quote in quotes
    )
    jsdoc_forms: tuple[tuple[str, Expected], ...] = (
        (
            """\
/** abc.cde prose */
""",
            Expected.SAFE,
        ),
        (
            """\
/** {@link abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** {@linkcode abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** {@linkplain abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** {@code abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @type {abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @returns {abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @throws {abc.cde} */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @extends abc.cde */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @implements abc.cde */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @memberof abc.cde */
""",
            Expected.GUARDED,
        ),
        (
            """\
/** @see abc.cde */
""",
            Expected.GUARDED,
        ),
    )
    for index, (source, expected) in enumerate(iterable=jsdoc_forms):
        cases.append(
            Case(
                name=f"gen-jsdoc-{index}",
                suffix=".js",
                source=source,
                expected=(expected,),
            ),
        )
    for index in range(25):
        indent: str = " " * (index % 5)
        cases.extend(
            (
                Case(
                    name=f"gen-py-comment-{index}",
                    suffix=".py",
                    source=f"""\
{indent}# case {index}: abc.cde
""",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-js-comment-{index}",
                    suffix=".js",
                    source=f"""\
{indent}// case {index}: abc.cde
""",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-html-text-{index}",
                    suffix=".html",
                    source=(
                        f"""\
<p data-case="{index}">case {index}: abc.cde</p>
"""
                    ),
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-md-prose-{index}",
                    suffix=".md",
                    source=f"""\
Case {index}: abc.cde documentation.
""",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-md-code-{index}",
                    suffix=".md",
                    source=f"""\
Case {index}: `abc.cde`.
""",
                    expected=(Expected.GUARDED,),
                ),
            ),
        )
    return tuple(cases)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        dotted: Grouped module constant.
        minimum_cases: Grouped module constant.
        minimum_guarded: Grouped module constant.
        base_cases: Grouped module constant.
        cases: Grouped module constant.

    """

    dotted: Final[Pattern[str]] = compile_pattern(pattern="abc\\.cde")
    minimum_cases: Final[int] = 250
    minimum_guarded: Final[int] = 50
    base_cases: Final[tuple[Case, ...]] = (
        Case(
            name="py-attribute",
            suffix=".py",
            source="""\
x = abc.cde
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-call",
            suffix=".py",
            source="""\
x = abc.cde()
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-assignment-target",
            suffix=".py",
            source="""\
abc.cde = 1
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-import",
            suffix=".py",
            source="""\
import abc.cde
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-from-import",
            suffix=".py",
            source="""\
from abc.cde import x
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-decorator",
            suffix=".py",
            source="""\
@abc.cde
def f() -> None:
    pass
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-annotation",
            suffix=".py",
            source="""\
x: abc.cde[str]
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-string",
            suffix=".py",
            source="""\
x = "abc.cde"
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-raw-string",
            suffix=".py",
            source="""\
x = r"abc.cde"
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-comment",
            suffix=".py",
            source="""\
# abc.cde
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-module-docstring",
            suffix=".py",
            source="""\
\"""abc.cde docs.\"""
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-function-docstring",
            suffix=".py",
            source="""\
def f() -> None:
    \"""abc.cde docs.\"""
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-fstring-expression",
            suffix=".py",
            source="""\
x = f"{abc.cde}"
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-fstring-text-and-expression",
            suffix=".py",
            source="""\
x = f"abc.cde {abc.cde}"
""",
            expected=(Expected.GUARDED, Expected.GUARDED),
        ),
        Case(
            name="py-unicode-prefix",
            suffix=".py",
            source="""\
x = "João — abc.cde"
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-member",
            suffix=".js",
            source="""\
const x = abc.cde;
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-optional-member",
            suffix=".js",
            source="""\
const x = obj?.abc.cde;
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-string",
            suffix=".js",
            source="""\
const x = "abc.cde";
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-comment",
            suffix=".js",
            source="""\
// abc.cde
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-block-comment",
            suffix=".js",
            source="""\
/* abc.cde */
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-template-static",
            suffix=".js",
            source="""\
const x = `abc.cde`;
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-template-expression",
            suffix=".js",
            source="""\
const x = `${abc.cde}`;
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-selector-api",
            suffix=".js",
            source="""\
document.querySelector("abc.cde");
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-closest-api",
            suffix=".js",
            source="""\
node.closest("abc.cde");
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-object-key",
            suffix=".js",
            source="""\
const x = {"abc.cde": 1};
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-unicode-prefix",
            suffix=".js",
            source="""\
const x = "João — abc.cde";
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="ts-type-member",
            suffix=".ts",
            source="""\
type T = typeof abc.cde;
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="tsx-string",
            suffix=".tsx",
            source="""\
const x = "abc.cde";
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="jsdoc-prose",
            suffix=".js",
            source="""\
/** abc.cde documentation. */
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="jsdoc-link",
            suffix=".js",
            source="""\
/** {@link abc.cde} */
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-code",
            suffix=".js",
            source="""\
/** {@code abc.cde} */
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-backtick",
            suffix=".js",
            source="""\
/** `abc.cde` */
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-type",
            suffix=".js",
            source="""\
/** @type {abc.cde} */
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-see",
            suffix=".js",
            source="""\
/** @see abc.cde */
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="css-selector",
            suffix=".css",
            source="""\
abc.cde { color: red; }
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="css-string",
            suffix=".css",
            source="""\
x { content: "abc.cde"; }
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-comment",
            suffix=".css",
            source="""\
/* abc.cde */
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-attribute-selector",
            suffix=".css",
            source="""\
[data-x="abc.cde"] {}
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-url",
            suffix=".css",
            source="""\
x { background: url("abc.cde"); }
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-text",
            suffix=".html",
            source="""\
<p>abc.cde</p>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-attribute",
            suffix=".html",
            source="""\
<div title="abc.cde"></div>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-script-member",
            suffix=".html",
            source="""\
<script>const x = abc.cde;</script>
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-script-string",
            suffix=".html",
            source="""\
<script>const x = "abc.cde";</script>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-style-selector",
            suffix=".html",
            source="""\
<style>abc.cde { color: red; }</style>
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-style-string",
            suffix=".html",
            source="""\
<style>x { content: "abc.cde"; }</style>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-event-handler",
            suffix=".html",
            source="""\
<button onclick="abc.cde()">x</button>
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-inline-style-string",
            suffix=".html",
            source="""\
<div style="content: 'abc.cde'"></div>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-comment",
            suffix=".html",
            source="""\
<!-- abc.cde -->
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-unicode-prefix",
            suffix=".html",
            source="""\
<p>João — abc.cde</p>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="md-prose",
            suffix=".md",
            source="""\
Project abc.cde docs.
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="md-inline-code",
            suffix=".md",
            source="""\
Use `abc.cde` here.
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-fenced-js",
            suffix=".md",
            source="""\
```js
const x = abc.cde;
```
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-fenced-text",
            suffix=".md",
            source="""\
```text
abc.cde
```
""",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-link-label",
            suffix=".md",
            source="""\
[abc.cde](https://example.test)
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="toml-string",
            suffix=".toml",
            source="""\
name = "abc.cde"
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="xml-text",
            suffix=".xml",
            source="""\
<x>abc.cde</x>
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="csv-field",
            suffix=".csv",
            source="""\
name,value
project,"abc.cde"
""",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="txt-text",
            suffix=".txt",
            source="""\
abc.cde
""",
            expected=(Expected.SAFE,),
        ),
    )
    cases: Final[tuple[Case, ...]] = base_cases + _generated_cases()


def _actual(case: Case) -> tuple[Expected, ...]:
    """Classify every exact dotted occurrence using production safe spans.

    Args:
        case: Parametrized case.

    Returns:
        The resulting value.

    """
    safe_by_line: dict[int, tuple[tuple[int, int], ...]] = safe_dotted_spans(
        text=case.source,
        suffix=case.suffix,
    )
    actual: list[Expected] = []
    for line_number, line in enumerate(
        iterable=case.source.splitlines(keepends=True),
        start=1,
    ):
        safe: tuple[tuple[int, int], ...] = safe_by_line.get(line_number, ())
        for match in Constants.dotted.finditer(string=line):
            contained: bool = span_contained(
                span=match.span(),
                containers=safe,
            )
            actual.append(Expected.SAFE if contained else Expected.GUARDED)
    return tuple(actual)


@pytest.mark.parametrize("case", Constants.cases, ids=lambda case: case.name)
def test_adversarial_classification(case: Case) -> None:
    """Every adversarial occurrence must receive its declared disposition.

    Args:
        case: Parametrized case.

    """
    expect_equal(actual=_actual(case=case), expected=case.expected)


def test_corpus_has_safety_weight() -> None:
    """Prevent accidental shrinking of the high-risk regression corpus."""
    total: int = sum(len(case.expected) for case in Constants.cases)
    guarded: int = sum(
        item is Expected.GUARDED
        for case in Constants.cases
        for item in case.expected
    )
    languages: set[str] = {case.suffix for case in Constants.cases}
    expect_true(condition=total >= Constants.minimum_cases)
    expect_true(condition=guarded >= Constants.minimum_guarded)
    required: set[str] = {
        ".py",
        ".js",
        ".css",
        ".html",
        ".md",
        ".toml",
        ".xml",
        ".csv",
        ".txt",
    }
    expect_true(condition=required <= languages)


def test_utf8_byte_character_round_trip() -> None:
    """Every Unicode character boundary must map back exactly."""
    text: str = "ASCII João 日本語 🙂 abc.cde"
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    expect_equal(actual=len(boundaries), expected=len(text) + 1)
    expect_equal(
        actual=tuple(
            byte_to_character(boundaries=boundaries, offset=offset)
            for offset in boundaries
        ),
        expected=tuple(range(len(text) + 1)),
    )


@pytest.mark.parametrize(
    ("suffix", "valid", "invalid"),
    [
        (
            ".py",
            """\
x = 1
""",
            """\
x = (
""",
        ),
        (
            ".toml",
            """\
x = "y"
""",
            """\
x = "y
""",
        ),
        (
            ".xml",
            """\
<x>y</x>
""",
            """\
<x>
""",
        ),
        (
            ".csv",
            """\
a,b
1,"2"
""",
            """\
a,b
1,"2
""",
        ),
        (
            ".js",
            """\
const x = 1;
""",
            """\
const x = ;
""",
        ),
        (
            ".css",
            """\
x { color: red; }
""",
            """\
x { color: ;
""",
        ),
        (
            ".html",
            """\
<p>x</p>
""",
            """\
<p><
""",
        ),
    ],
)
def test_structural_validation_rejects_invalid_source(
    suffix: str,
    valid: str,
    invalid: str,
) -> None:
    """Post-rewrite parser validation must reject malformed source.

    Args:
        suffix: Value for ``suffix``.
        valid: Value for ``valid``.
        invalid: Value for ``invalid``.

    """
    expect_true(
        condition=structurally_valid_rewrite(text=valid, suffix=suffix),
    )
    expect_false(
        condition=structurally_valid_rewrite(text=invalid, suffix=suffix),
    )


def test_parser_contracts() -> None:
    """Every configured Tree-sitter grammar must load and parse a specimen."""
    specimens: dict[str, str] = {
        "javascript": """\
const x = {a: 1};
""",
        "typescript": """\
const x: string = 'x';
""",
        "tsx": """\
const x = <div>ok</div>;
""",
        "css": """\
x { color: red; }
""",
        "html": """\
<!doctype html><p>x</p>
""",
        "markdown": """\
# Heading

Text.
""",
    }
    for language, source in specimens.items():
        parsed: tuple[bytes, Node] | None = parse_tree(
            text=source,
            language=language,
        )
        expect_not_none(value=parsed, message=language)


def test_source_file_exists() -> None:
    """Keep this suite colocatable with the standalone script."""
    expect_equal(
        actual=Path(getfile(object=safe_dotted_spans)).name,
        expected="rename_project.py",
    )
