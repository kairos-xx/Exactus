# Copyright (c) 2026
"""The lints CSS token audit resolves one token graph across stylesheets."""

from __future__ import annotations

from functools import partial
from itertools import product
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.common import execution
from exactus.tools.lints.core import LintExactus
from exactus.tools.lints.css_tokens import (
    Constants,
    CssDeclaration,
    CssSource,
    CssTokenFinding,
    CssTokenInput,
    Layer,
    layer_of,
    lex,
    parse_declarations,
    scan_css_tokens,
)
from exactus.tools.lints.main import main

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult


@final
class Sources:
    """Group stylesheet fixtures.

    Attributes:
        clean: A conforming token chain consumed by one rule.

    """

    clean: Final[str] = dedent(
        text=(
            """\
    :root {
      --primary-length-unit: 4px;
      --base-length-gap: calc(var(--primary-length-unit) * 2);
      --catalog-box-measure-gap: var(--base-length-gap);
      --gap: var(--catalog-box-measure-gap);
    }
    .box { margin: var(--gap); display: flex; }
    """
        ),
    )


def audit(
    *,
    root: Path,
    sources: dict[str, str],
    words: frozenset[str] = frozenset(),
) -> tuple[CssTokenFinding, ...]:
    """Write stylesheets under ``root`` and audit them as one set.

    Args:
        root: Isolated project root.
        sources: Stylesheet text keyed by root-relative path.
        words: Words forbidden in CATALOG names.

    Returns:
        Every finding of the audit.

    """
    for name, text in sources.items():
        path: Path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data=text, encoding="utf-8")
    return scan_css_tokens(
        inputs=CssTokenInput(
            root=root,
            files=sorted(root / name for name in sources),
            context_words=words,
        ),
    )


def rules(*, findings: tuple[CssTokenFinding, ...]) -> list[str]:
    """Return the sorted distinct rule identifiers of findings.

    Args:
        findings: Audit findings.

    Returns:
        Sorted unique rule identifiers.

    """
    return sorted({finding.rule for finding in findings})


def test_conforming_layers_pass(tmp_path: Path) -> None:
    """A PRIMARY, BASE, CATALOG, SEMANTIC chain consumed by SEMANTIC is clean.

    Args:
        tmp_path: Isolated project root.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": Sources.clean},
    )
    expect_equal(actual=findings, expected=())


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        (
            """\
:root { --a: 1px; }
:root { --a: 2px; }
""",
            "CSS101",
        ),
        (
            """\
.a { margin: var(--gap); }
""",
            "CSS102",
        ),
        (
            """\
:root { --base-derived-x: 1px; }
""",
            "CSS103",
        ),
        (
            """\
:root { --primary-keyword-solid: solid; }
""",
            "CSS104",
        ),
        (
            """\
:root { --primary-percent-half: 50%; }
""",
            "CSS105",
        ),
        (
            """\
:root { --primary-duration-slow: 400ms; }
""",
            "CSS106",
        ),
        (
            """\
:root { --primary-font-weight-bold: 700; }
""",
            "CSS107",
        ),
        (
            """\
:root { --primary-a: 1px; --primary-b: var(--primary-a); }
""",
            "CSS108",
        ),
        (
            """\
:root { --primary-a: calc(1px * 2); }
""",
            "CSS109",
        ),
        (
            dedent(
                text=(
                    """\
    :root { --catalog-box-measure-a: 1px; --base-a: \
var(--catalog-box-measure-a); }
    """
                ),
            ),
            "CSS110",
        ),
        (
            dedent(
                text=(
                    """\
                    :root { --primary-a: 1px; --catalog-box-measure-a: \
var(--primary-a); }
"""
                ),
            ),
            "CSS111",
        ),
        (
            dedent(
                text=(
                    """\
                    :root { --catalog-box-color-a: color-mix(in oklab, red, \
blue); }
"""
                ),
            ),
            "CSS112",
        ),
        (
            dedent(
                text=(
                    """\
                    :root { --base-number-one: 1; --catalog-box-measure-a: \
calc(2 * var(--base-number-one)); }
"""
                ),
            ),
            "CSS113",
        ),
        (
            """\
:root { --catalog-box-measure: 1px; }
""",
            "CSS114",
        ),
        (
            """\
:root { --catalog-measure-box-gap: 1px; }
""",
            "CSS115",
        ),
        (
            """\
:root { --catalog-box-weird-gap: 1px; }
""",
            "CSS116",
        ),
        (
            """\
:root { --catalog-box-measure-lg: 1px; }
""",
            "CSS117",
        ),
        (
            """\
:root { --catalog-timeline-measure-gap: 1px; }
""",
            "CSS118",
        ),
        (
            """\
:root { --gap: 4px; }
""",
            "CSS119",
        ),
        (
            dedent(
                text=(
                    """\
    :root { --catalog-box-measure-a: 1px; --gap: var(--catalog-box-measure-a, \
4px); }
    """
                ),
            ),
            "CSS120",
        ),
        (
            dedent(
                text=(
                    """\
                    :root { --base-a: 1px; --gap: var(--base-a); }
                    .a { margin: var(--base-a); }
"""
                ),
            ),
            "CSS121",
        ),
        (
            dedent(
                text=(
                    """\
                    :root { --gap: var(--catalog-a-measure-b); }
                    .a { width: calc(var(--gap) + 1px); }
"""
                ),
            ),
            "CSS122",
        ),
        (
            """\
.a { color: red; }
""",
            "CSS123",
        ),
        (
            """\
.a { unknown-prop: 5px; }
""",
            "CSS124",
        ),
        (
            """\
.a { flex-grow: 2; }
""",
            "CSS125",
        ),
    ],
)
def test_each_rule_reports(tmp_path: Path, text: str, rule: str) -> None:
    """Every ``CSS1xx`` rule is reported by a minimal stylesheet.

    Args:
        tmp_path: Isolated project root.
        text: Stylesheet violating one rule.
        rule: Expected rule identifier.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
        words=frozenset({"timeline"}),
    )
    expect_in(container=rules(findings=findings), member=rule)


def test_every_rule_has_a_name() -> None:
    """The rule table covers CSS100 through CSS125 without gaps."""
    expect_equal(
        actual=list(Constants.rules),
        expected=[f"CSS{number}" for number in range(100, 126)],
    )


def test_scoped_overrides_are_not_conflicts(tmp_path: Path) -> None:
    """A property set under different selectors is a cascade, not a clash.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = dedent(
        text=(
            """\
    :root { --dynamic-lane-h: 1.75rem; }
    .a { --dynamic-lane-h: 3rem; }
    @media (width < 40rem) { .a { --dynamic-lane-h: 1rem; } }
    """
        ),
    )
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_not_in(member="CSS101", container=rules(findings=findings))


def test_tokens_resolve_across_files(tmp_path: Path) -> None:
    """A token defined in one stylesheet satisfies a use in another.

    Args:
        tmp_path: Isolated project root.

    """
    sources: dict[str, str] = {
        "tokens.css": Sources.clean.partition(".box")[0],
        "app.css": """\
.box { margin: var(--gap); }
""",
    }
    expect_equal(actual=audit(root=tmp_path, sources=sources), expected=())
    missing: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={
            "app.css": """\
.box { margin: var(--gap); }
""",
        },
    )
    expect_equal(actual=rules(findings=missing), expected=["CSS102"])


def test_dynamic_references_need_no_definition(tmp_path: Path) -> None:
    """``--dynamic-*`` tokens are supplied at run time.

    Args:
        tmp_path: Isolated project root.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={
            "app.css": """\
:root { --base-w: var(--dynamic-width); }
""",
        },
    )
    expect_not_in(member="CSS102", container=rules(findings=findings))


def test_comments_and_strings_hide_nothing(tmp_path: Path) -> None:
    """Separators in comments and strings do not split declarations.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = (
        dedent(
            text=(
                """\
    /* .a { color: red; } */
    .a {
      content: var(--gap);
      quotes: "a;b{c}";
    }
    """
            ),
        )
    ) + Sources.clean
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(
        actual=sorted((finding.rule, finding.line) for finding in findings),
        expected=[("CSS123", 4)],
    )


def test_component_directories_are_matched_whole(tmp_path: Path) -> None:
    """A CATALOG name is flagged for the component's name, not its words.

    Args:
        tmp_path: Isolated project root.

    """
    sources: dict[str, str] = {
        "components/side-bar/side.css": (
            dedent(
                text=(
                    """\
    :root {
      --catalog-side-bar-measure-gap: 1px;
      --catalog-side-measure-gap: 1px;
      --catalog-bar-measure-gap: 1px;
    }
    """
                ),
            )
        ),
    }
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources=sources,
    )
    expect_equal(
        actual=[
            finding.line for finding in findings if finding.rule == "CSS118"
        ],
        expected=[2],
    )


def test_grammar_keywords_stay_literal(tmp_path: Path) -> None:
    """Structural keywords need no token; their design operands still do.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = dedent(
        text=(
            """\
    .a { place-items: center; flex-flow: row wrap; display: flex; }
    .b { place-items: 4px; flex: 0 0 auto; }
    """
        ),
    )
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(
        actual=lines_of(findings=findings),
        expected=[("CSS123", 2), ("CSS124", 2)],
    )


def test_finding_locates_declaration(tmp_path: Path) -> None:
    """A finding names the file, line and offending declaration.

    Args:
        tmp_path: Isolated project root.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={
            "app.css": Sources.clean
            + """\
.late { color: red; }
""",
        },
    )
    expect_equal(actual=len(findings), expected=1)
    expect_equal(actual=findings[0].file, expected=tmp_path / "app.css")
    expect_equal(actual=findings[0].line, expected=8)
    expect_in(container=findings[0].message, member="color: red")


def test_layer_prefixes() -> None:
    """Prefixes select the layer; any other custom property is SEMANTIC."""
    expect_equal(actual=layer_of(name="--primary-x"), expected=Layer.PRIMARY)
    expect_equal(actual=layer_of(name="--dynamic-x"), expected=Layer.DYNAMIC)
    expect_equal(actual=layer_of(name="--base-x"), expected=Layer.BASE)
    expect_equal(actual=layer_of(name="--catalog-x"), expected=Layer.CATALOG)
    expect_equal(actual=layer_of(name="--x"), expected=Layer.SEMANTIC)
    expect_false(condition=layer_of(name="--basement") is Layer.BASE)


def lines_of(
    *,
    findings: tuple[CssTokenFinding, ...],
) -> list[tuple[str, int]]:
    """Return the sorted ``(rule, line)`` pairs of findings.

    Args:
        findings: Audit findings.

    Returns:
        The pairs in sorted order.

    """
    return sorted((finding.rule, finding.line) for finding in findings)


def test_unreadable_files_are_findings_not_crashes(tmp_path: Path) -> None:
    """A missing or non-UTF-8 stylesheet is reported and the rest audited.

    Args:
        tmp_path: Isolated project root.

    """
    good: Path = tmp_path / "good.css"
    good.write_text(
        data="""\
.a { color: red; }
""",
        encoding="utf-8",
    )
    binary: Path = tmp_path / "binary.css"
    binary.write_bytes(data=b"\xff\xfe\x00.a { color: red }")
    findings: tuple[CssTokenFinding, ...] = scan_css_tokens(
        inputs=CssTokenInput(
            root=tmp_path,
            files=[good, binary, tmp_path / "missing.css", good],
        ),
    )
    expect_equal(
        actual=sorted((f.rule, f.file.name) for f in findings),
        expected=[
            ("CSS100", "binary.css"),
            ("CSS100", "missing.css"),
            ("CSS123", "good.css"),
        ],
    )


def test_byte_order_mark_and_crlf(tmp_path: Path) -> None:
    """A BOM is dropped and CRLF endings keep line numbers right.

    Args:
        tmp_path: Isolated project root.

    """
    path: Path = tmp_path / "app.css"
    path.write_bytes(
        data=b"\xef\xbb\xbf:root {\r\n  --primary-a: 1px;\r\n}\r\n"
        b".a {\r\n  color: red;\r\n}\r\n",
    )
    findings: tuple[CssTokenFinding, ...] = scan_css_tokens(
        inputs=CssTokenInput(root=tmp_path, files=[path]),
    )
    expect_equal(actual=lines_of(findings=findings), expected=[("CSS123", 5)])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """\
.a { color: red; /* never closed
 margin: 0; }
""",
            [("CSS123", 1)],
        ),
        (
            """\
.a { content: "oops; color: red;
}
.b { color: blue; }
""",
            [("CSS123", 1), ("CSS123", 3)],
        ),
        (
            """\
.a { content: "a\\"b;c"; color: red; }
""",
            [("CSS123", 1), ("CSS123", 1)],
        ),
        (
            dedent(
                text=(
                    """\
                    .a { background: url(data:image/svg+xml;utf8,<svg>{;}\
</svg>); color: red; }
"""
                ),
            ),
            [("CSS123", 1), ("CSS123", 1)],
        ),
        (
            dedent(
                text=(
                    """\
    .a { width: calc(1px; color: red; }
    .b { margin: var(--gap); }
    """
                ),
            ),
            [("CSS102", 2), ("CSS122", 1), ("CSS123", 1)],
        ),
        (
            """\
} ; ) .a { color: red; } } ;
""",
            [("CSS123", 1)],
        ),
        (".a { color: red", [("CSS123", 1)]),
        (
            """\
.a\\{b { color: red; }
""",
            [("CSS123", 1)],
        ),
    ],
)
def test_malformed_input_degrades_locally(
    tmp_path: Path,
    text: str,
    expected: list[tuple[str, int]],
) -> None:
    """Broken strings, comments, parentheses and braces hide nothing.

    Args:
        tmp_path: Isolated project root.
        text: Malformed stylesheet.
        expected: The ``(rule, line)`` pairs the audit must still find.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(actual=lines_of(findings=findings), expected=expected)


def test_important_does_not_hide_a_plain_reference(tmp_path: Path) -> None:
    """``var(--x) !important`` is still one plain SEMANTIC reference.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = (
        Sources.clean
        + """\
.a { color: var(--gap) !important; }
"""
    )
    expect_equal(
        actual=audit(root=tmp_path, sources={"app.css": text}),
        expected=(),
    )


def test_strings_are_not_references_or_literals(tmp_path: Path) -> None:
    """``var()`` and measures inside strings and ``url()`` are text.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = dedent(
        text=(
            """\
    .a { content: "var(--nope) 4px"; }
    .b { unknown-prop: url(sprite.png#4px) }
    """
        ),
    )
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(actual=lines_of(findings=findings), expected=[("CSS123", 1)])


def test_css_wide_keywords_need_no_token(tmp_path: Path) -> None:
    """``inherit`` cannot pass through a custom property; it stays literal.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = """\
.a { font: inherit; color: unset !important; margin: auto; }
"""
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(actual=lines_of(findings=findings), expected=[("CSS123", 1)])


def test_negative_numbers_are_literals(tmp_path: Path) -> None:
    """A signed measure is a design literal, not part of a name.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = """\
.a { unknown-prop: -4px; other-prop: col-4px; }
"""
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(actual=lines_of(findings=findings), expected=[("CSS124", 1)])


def test_context_words_match_case_insensitively(tmp_path: Path) -> None:
    """A CATALOG name segment matches a context word in any case.

    Args:
        tmp_path: Isolated project root.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": ":root { --catalog-Timeline-measure-gap: 1px; }"},
        words=frozenset({"TimeLine"}),
    )
    expect_in(container=rules(findings=findings), member="CSS118")


def test_long_values_are_clipped_in_messages(tmp_path: Path) -> None:
    """A huge value cannot bloat a finding message.

    Args:
        tmp_path: Isolated project root.

    """
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={
            "app.css": ".a { color: "
            + "red " * 5000
            + """\
; }
""",
        },
    )
    expect_equal(actual=len(findings), expected=1)
    limit: int = 3 * Constants.message_limit
    expect_true(condition=len(findings[0].message) < limit)


def test_one_line_files_scale(tmp_path: Path) -> None:
    """A minified single-line sheet is lexed and located in linear time.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = (
        ".a{"
        + "color:red;" * 20000
        + """\
}
"""
    )
    findings: tuple[CssTokenFinding, ...] = audit(
        root=tmp_path,
        sources={"app.css": text},
    )
    expect_equal(actual=len(findings), expected=20000)
    expect_true(condition={finding.line for finding in findings} == {1})


def test_lexer_keeps_text_length_and_lines(tmp_path: Path) -> None:
    """The structural view always matches the text in length and lines.

    Every sequence of up to four structural pieces is lexed and parsed, so
    each combination of comment, string, escape, parenthesis and brace
    openers and closers is met in every order.

    Args:
        tmp_path: Isolated project root.

    """
    pieces: tuple[str, ...] = (
        "/*",
        "*/",
        '"',
        "'",
        "\\",
        "(",
        ")",
        "{",
        "}",
        ";",
        ":",
        """\

""",
        "url(",
        "a",
    )
    for size in range(5):
        for combination in product(pieces, repeat=size):
            text: str = "".join(combination)
            source: CssSource = lex(text=text)
            expect_equal(actual=len(source.clean), expected=len(text))
            expect_equal(actual=len(source.masked), expected=len(text))
            expect_equal(
                actual=source.newlines,
                expected=tuple(
                    i
                    for i, c in enumerate(iterable=text)
                    if c
                    == """\

"""
                ),
            )
            declarations: list[CssDeclaration] = parse_declarations(
                text=text,
                file=tmp_path / "fuzz.css",
            )
            expect_true(
                condition=all(
                    1
                    <= item.line
                    <= text.count("""\

""")
                    + 1
                    for item in declarations
                ),
                message=repr(text),
            )


def test_every_prefix_of_a_sheet_audits(tmp_path: Path) -> None:
    """Truncating a sheet anywhere never raises and keeps lines in range.

    Args:
        tmp_path: Isolated project root.

    """
    text: str = dedent(
        text=(
            """\
    @import url(a.css);
    :root { --primary-a: 4px; --base-b: calc(var(--primary-a) * 2); }
    @media (min-width: 40rem) {
      .a { content: "x;y"; margin: var(--gap, 4px) !important;
           background: url(data:a;b) /* note */ red; }
    }
    """
        ),
    )
    path: Path = tmp_path / "app.css"
    for size in range(len(text) + 1):
        path.write_text(data=text[:size], encoding="utf-8")
        findings: tuple[CssTokenFinding, ...] = scan_css_tokens(
            inputs=CssTokenInput(root=tmp_path, files=[path]),
        )
        expect_true(
            condition=all(
                0
                <= f.line
                <= text.count("""\

""")
                + 1
                for f in findings
            ),
            message=f"prefix {size}",
        )


def no_commands(
    cwd: Path,
    toolchain: Path | None,
) -> dict[str, tuple[str, ...] | None]:
    """Resolve no external tools for the built-in report integration test.

    Args:
        cwd: Project root, unused.
        toolchain: Optional toolchain, unused.

    Returns:
        Empty external command mapping.

    """
    _ = (cwd, toolchain)
    return dict.fromkeys(
        (
            "ruff",
            "basedpyright",
            "pyrefly",
            "eslint",
            "tsc",
            "stylelint",
            "htmlhint",
            "prettier",
        ),
    )


def test_token_findings_are_part_of_lints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lints entry point reports token findings under ``custom_css``.

    Args:
        tmp_path: Isolated project root.
        monkeypatch: Patch external command resolution.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
""",
    )
    (root / "app.css").write_text(
        data=Sources.clean
        + dedent(
            text=(
                """\
    .late { color: red; }
    :root { --catalog-timeline-measure-gap: 1px; }
    """
            ),
        ),
    )
    monkeypatch.setattr(
        target=LintExactus,
        name="_resolve_commands",
        value=staticmethod(no_commands),
    )
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    output: Path = tmp_path / "LINTS"
    result: ToolRunResult = execution.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=partial(
            main,
            arguments=(
                str(object=root),
                "--dry",
                "--css-context-word",
                "timeline",
                "--output-dir",
                str(object=output),
            ),
        ),
        output=output,
    )
    expect_equal(actual=result.status, expected="FAIL")
    data: dict[str, JsonValue] = loads(s=(output / "result.json").read_text())
    findings: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=data["findings"],
    )
    selected: dict[str, dict[str, JsonValue]] = {
        str(object=finding["rule"]): finding
        for finding in findings
        if str(object=finding["rule"]).startswith("CSS1")
    }
    expect_equal(actual=sorted(selected), expected=["CSS118", "CSS123"])
    expect_true(
        condition=all(
            finding["source"] == "custom_css" for finding in selected.values()
        ),
    )


def test_studio_component_directories_have_one_uniform_contract() -> None:
    """Every Studio style component exposes the same three-file surface."""
    root: Path = (
        Path(__file__).parents[4]
        / "exactus"
        / "tools"
        / "record"
        / "studio"
        / "web"
        / "styles"
        / "components"
    )
    expected: tuple[str, ...] = ("README.md", "semantic.css", "style.css")
    for directory in sorted(
        (item for item in root.iterdir() if item.is_dir()),
        key=lambda item: item.name,
    ):
        expect_equal(
            actual=tuple(sorted(item.name for item in directory.iterdir())),
            expected=expected,
        )
