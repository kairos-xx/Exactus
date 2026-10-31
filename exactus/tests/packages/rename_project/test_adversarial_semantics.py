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
                        source=f"x = {quote}{prefix}abc.cde{quote}\n",
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-js-string-{index}-{ord(quote)}",
                        suffix=".js",
                        source=f"const x = {quote}{prefix}abc.cde{quote};\n",
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-css-string-{index}-{ord(quote)}",
                        suffix=".css",
                        source=(
                            f"x {{ content: {quote}{prefix}"
                            f"abc.cde{quote}; }}\n"
                        ),
                        expected=(Expected.SAFE,),
                    ),
                    Case(
                        name=f"gen-html-attribute-{index}-{ord(quote)}",
                        suffix=".html",
                        source=(
                            f"<div title={quote}{prefix}abc.cde{quote}>"
                            f"</div>\n"
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
                    source=f"x ={gap}abc.cde\n",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-js-member-{index}",
                    suffix=".js",
                    source=f"const x ={gap}abc.cde;\n",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-css-selector-{index}",
                    suffix=".css",
                    source=f"abc.cde{gap}{{ color: red; }}\n",
                    expected=(Expected.GUARDED,),
                ),
                Case(
                    name=f"gen-html-script-member-{index}",
                    suffix=".html",
                    source=f"<script>const x ={gap}abc.cde;</script>\n",
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
            source=f"node.{method}({quote}abc.cde{quote});\n",
            expected=(Expected.GUARDED,),
        )
        for method in selector_methods
        for quote in quotes
    )
    jsdoc_forms: tuple[tuple[str, Expected], ...] = (
        ("/** abc.cde prose */\n", Expected.SAFE),
        ("/** {@link abc.cde} */\n", Expected.GUARDED),
        ("/** {@linkcode abc.cde} */\n", Expected.GUARDED),
        ("/** {@linkplain abc.cde} */\n", Expected.GUARDED),
        ("/** {@code abc.cde} */\n", Expected.GUARDED),
        ("/** @type {abc.cde} */\n", Expected.GUARDED),
        ("/** @returns {abc.cde} */\n", Expected.GUARDED),
        ("/** @throws {abc.cde} */\n", Expected.GUARDED),
        ("/** @extends abc.cde */\n", Expected.GUARDED),
        ("/** @implements abc.cde */\n", Expected.GUARDED),
        ("/** @memberof abc.cde */\n", Expected.GUARDED),
        ("/** @see abc.cde */\n", Expected.GUARDED),
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
                    source=f"{indent}# case {index}: abc.cde\n",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-js-comment-{index}",
                    suffix=".js",
                    source=f"{indent}// case {index}: abc.cde\n",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-html-text-{index}",
                    suffix=".html",
                    source=(
                        f'<p data-case="{index}">case {index}: abc.cde</p>\n'
                    ),
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-md-prose-{index}",
                    suffix=".md",
                    source=f"Case {index}: abc.cde documentation.\n",
                    expected=(Expected.SAFE,),
                ),
                Case(
                    name=f"gen-md-code-{index}",
                    suffix=".md",
                    source=f"Case {index}: `abc.cde`.\n",
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
            source="x = abc.cde\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-call",
            suffix=".py",
            source="x = abc.cde()\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-assignment-target",
            suffix=".py",
            source="abc.cde = 1\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-import",
            suffix=".py",
            source="import abc.cde\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-from-import",
            suffix=".py",
            source="from abc.cde import x\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-decorator",
            suffix=".py",
            source="@abc.cde\ndef f() -> None:\n    pass\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-annotation",
            suffix=".py",
            source="x: abc.cde[str]\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-string",
            suffix=".py",
            source='x = "abc.cde"\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-raw-string",
            suffix=".py",
            source='x = r"abc.cde"\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-comment",
            suffix=".py",
            source="# abc.cde\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-module-docstring",
            suffix=".py",
            source='"""abc.cde docs."""\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-function-docstring",
            suffix=".py",
            source='def f() -> None:\n    """abc.cde docs."""\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="py-fstring-expression",
            suffix=".py",
            source='x = f"{abc.cde}"\n',
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="py-fstring-text-and-expression",
            suffix=".py",
            source='x = f"abc.cde {abc.cde}"\n',
            expected=(Expected.GUARDED, Expected.GUARDED),
        ),
        Case(
            name="py-unicode-prefix",
            suffix=".py",
            source='x = "João — abc.cde"\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-member",
            suffix=".js",
            source="const x = abc.cde;\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-optional-member",
            suffix=".js",
            source="const x = obj?.abc.cde;\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-string",
            suffix=".js",
            source='const x = "abc.cde";\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-comment",
            suffix=".js",
            source="// abc.cde\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-block-comment",
            suffix=".js",
            source="/* abc.cde */\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-template-static",
            suffix=".js",
            source="const x = `abc.cde`;\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-template-expression",
            suffix=".js",
            source="const x = `${abc.cde}`;\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-selector-api",
            suffix=".js",
            source='document.querySelector("abc.cde");\n',
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-closest-api",
            suffix=".js",
            source='node.closest("abc.cde");\n',
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="js-object-key",
            suffix=".js",
            source='const x = {"abc.cde": 1};\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="js-unicode-prefix",
            suffix=".js",
            source='const x = "João — abc.cde";\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="ts-type-member",
            suffix=".ts",
            source="type T = typeof abc.cde;\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="tsx-string",
            suffix=".tsx",
            source='const x = "abc.cde";\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="jsdoc-prose",
            suffix=".js",
            source="/** abc.cde documentation. */\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="jsdoc-link",
            suffix=".js",
            source="/** {@link abc.cde} */\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-code",
            suffix=".js",
            source="/** {@code abc.cde} */\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-backtick",
            suffix=".js",
            source="/** `abc.cde` */\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-type",
            suffix=".js",
            source="/** @type {abc.cde} */\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="jsdoc-see",
            suffix=".js",
            source="/** @see abc.cde */\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="css-selector",
            suffix=".css",
            source="abc.cde { color: red; }\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="css-string",
            suffix=".css",
            source='x { content: "abc.cde"; }\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-comment",
            suffix=".css",
            source="/* abc.cde */\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-attribute-selector",
            suffix=".css",
            source='[data-x="abc.cde"] {}\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="css-url",
            suffix=".css",
            source='x { background: url("abc.cde"); }\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-text",
            suffix=".html",
            source="<p>abc.cde</p>\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-attribute",
            suffix=".html",
            source='<div title="abc.cde"></div>\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-script-member",
            suffix=".html",
            source="<script>const x = abc.cde;</script>\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-script-string",
            suffix=".html",
            source='<script>const x = "abc.cde";</script>\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-style-selector",
            suffix=".html",
            source="<style>abc.cde { color: red; }</style>\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-style-string",
            suffix=".html",
            source='<style>x { content: "abc.cde"; }</style>\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-event-handler",
            suffix=".html",
            source='<button onclick="abc.cde()">x</button>\n',
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="html-inline-style-string",
            suffix=".html",
            source="<div style=\"content: 'abc.cde'\"></div>\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-comment",
            suffix=".html",
            source="<!-- abc.cde -->\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="html-unicode-prefix",
            suffix=".html",
            source="<p>João — abc.cde</p>\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="md-prose",
            suffix=".md",
            source="Project abc.cde docs.\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="md-inline-code",
            suffix=".md",
            source="Use `abc.cde` here.\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-fenced-js",
            suffix=".md",
            source="```js\nconst x = abc.cde;\n```\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-fenced-text",
            suffix=".md",
            source="```text\nabc.cde\n```\n",
            expected=(Expected.GUARDED,),
        ),
        Case(
            name="md-link-label",
            suffix=".md",
            source="[abc.cde](https://example.test)\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="toml-string",
            suffix=".toml",
            source='name = "abc.cde"\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="xml-text",
            suffix=".xml",
            source="<x>abc.cde</x>\n",
            expected=(Expected.SAFE,),
        ),
        Case(
            name="csv-field",
            suffix=".csv",
            source='name,value\nproject,"abc.cde"\n',
            expected=(Expected.SAFE,),
        ),
        Case(
            name="txt-text",
            suffix=".txt",
            source="abc.cde\n",
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
        (".py", "x = 1\n", "x = (\n"),
        (".toml", 'x = "y"\n', 'x = "y\n'),
        (".xml", "<x>y</x>\n", "<x>\n"),
        (".csv", 'a,b\n1,"2"\n', 'a,b\n1,"2\n'),
        (".js", "const x = 1;\n", "const x = ;\n"),
        (".css", "x { color: red; }\n", "x { color: ;\n"),
        (".html", "<p>x</p>\n", "<p><\n"),
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
        "javascript": "const x = {a: 1};\n",
        "typescript": "const x: string = 'x';\n",
        "tsx": "const x = <div>ok</div>;\n",
        "css": "x { color: red; }\n",
        "html": "<!doctype html><p>x</p>\n",
        "markdown": "# Heading\n\nText.\n",
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
