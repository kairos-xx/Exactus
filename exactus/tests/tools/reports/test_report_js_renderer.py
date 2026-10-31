# Copyright (c) 2026
"""The web report's Markdown renderer escapes code and refuses bad links.

The renderer lives in ``report.js``; these tests load the script into a
Node ``vm`` context with a stub ``document`` and call its pure static
renderer functions, so they run only when ``node`` is on ``PATH``.
"""

from __future__ import annotations

from json import dumps, loads
from pathlib import Path
from shutil import which
from subprocess import CompletedProcess, run
from textwrap import dedent
from typing import Final, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    require,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        script: Grouped module constant.
        harness: Grouped module constant.
        node: Grouped module constant.
        spread: Grouped module constant.

    """

    script: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "tools"
        / "common"
        / "templates"
        / "html"
        / "report.js"
    )
    harness: Final[str] = dedent(
        text=(
            '    \n    const { readFileSync } = require("node:fs");\n    const'
            ' { runInNewContext } = require("node:vm");\n    const [script, me'
            "thod, payload] = process.argv.slice(1);\n    const context = { do"
            "cument: { addEventListener() {} } };\n    const source =\n      r"
            'eadFileSync(script, "utf8") +\n      "\\nglobalThis.ExactusReport'
            ' = ExactusReport;";\n    runInNewContext(source, context);\n    c'
            "onst inputs = JSON.parse(payload);\n    const outputs = inputs.ma"
            "p((input) => context.ExactusReport[method](input));\n    process."
            "stdout.write(JSON.stringify(outputs));\n    "
        ),
    )
    node: Final[str | None] = which(cmd="node")
    spread: Final[str] = harness.replace(
        "inputs.map((input) => context.ExactusReport[method](input))",
        "[context.ExactusReport[method](...inputs)]",
    )


pytestmark: pytest.MarkDecorator = pytest.mark.skipif(
    Constants.node is None,
    reason="node is not on PATH; report.js renderer tests need Node.js",
)


def render(*, method: str, inputs: list[str]) -> list[str]:
    """Call one static ``ExactusReport`` renderer on each input.

    Args:
        method: Static method name, such as ``markdown`` or ``inline``.
        inputs: Source texts passed one by one.

    Returns:
        The rendered HTML strings in input order.

    """
    completed: CompletedProcess[str] = run(
        args=[
            require(value=Constants.node),
            "-e",
            Constants.harness,
            str(object=Constants.script),
            method,
            dumps(obj=inputs),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    outputs: list[str] = loads(s=completed.stdout)
    return outputs


def test_tilde_fence_renders_escaped_code() -> None:
    """``~~~`` blocks are code: no emphasis, every character escaped."""
    source: str = "~~~python\ndef f(*args, **kwargs):\n    return '<b>'\n~~~\n"
    (html,) = render(method="markdown", inputs=[source])
    expect_in(member="def f(*args, **kwargs):", container=html)
    expect_in(member="&lt;b&gt;", container=html)
    expect_in(member="<pre><code>", container=html)
    expect_not_in(member="<em>", container=html)
    expect_not_in(member="<p>", container=html)


def test_backtick_fence_and_longer_closer() -> None:
    """A fence closes only on the same character, at least as long."""
    source: str = "````\n~~~\n```\n*x*\n````\nafter *y*"
    (html,) = render(method="markdown", inputs=[source])
    expect_in(member="<pre><code>~~~\n```\n*x*</code></pre>", container=html)
    expect_in(member="<p>after <em>y</em></p>", container=html)


def test_unclosed_fence_is_closed() -> None:
    """A fence left open at the end still yields balanced markup."""
    (html,) = render(method="markdown", inputs=["~~~\n[a](javascript:x)"])
    expect_equal(
        actual=html,
        expected="<pre><code>[a](javascript:x)</code></pre>",
    )


def test_javascript_links_stay_text() -> None:
    """Links with schemes other than http(s) never become anchors."""
    sources: list[str] = [
        "[docs](javascript:alert%28document.domain%29)",
        "[x](JavaScript:alert(1))",
        "[x](data:text/html,hi)",
        "[x](vbscript:msgbox)",
        "README in [sub](javascript:void(0)) dir",
    ]
    for html in render(method="inline", inputs=sources):
        expect_not_in(member="<a ", container=html)
        expect_not_in(member="href", container=html)


def test_markdown_paragraph_link_is_text() -> None:
    """The block renderer goes through the same link policy."""
    (html,) = render(
        method="markdown",
        inputs=["See [docs](javascript:alert%28document.domain%29)."],
    )
    expect_not_in(member="<a ", container=html)


def test_safe_links_render() -> None:
    """http(s), fragment, absolute and relative targets stay links."""
    outputs: list[str] = render(
        method="inline",
        inputs=[
            "[a](https://example.com/x?y=1&z=2)",
            "[b](#frag)",
            "[c](exactus/docs/page.md)",
            "[d](/abs)",
        ],
    )
    expect_equal(
        actual=outputs,
        expected=[
            '<a href="https://example.com/x?y=1&amp;z=2">a</a>',
            '<a href="#frag">b</a>',
            '<a href="../exactus/docs/page.md">c</a>',
            '<a href="/abs">d</a>',
        ],
    )


def test_code_span_has_no_inline_markup() -> None:
    """Code spans are escaped text; emphasis applies outside only."""
    (html,) = render(
        method="inline",
        inputs=["`f(*args, **kw)` and *em* and `[a](b)`"],
    )
    expect_equal(
        actual=html,
        expected=(
            "<code>f(*args, **kw)</code> and <em>em</em> and "
            "<code>[a](b)</code>"
        ),
    )


def test_code_label_links_remain_clickable() -> None:
    """Render a normalized source link relative to the nested web directory."""
    (html,) = render(
        method="inline",
        inputs=["[`source.py:4`](../source.py#L4)"],
    )
    expect_equal(
        actual=html,
        expected='<a href="../../source.py#L4"><code>source.py:4</code></a>',
    )


def test_file_links_encode_reserved_characters() -> None:
    """Encode spaces, hashes and Unicode in file destinations."""
    html: str = call(
        method="fileLink",
        arguments=["exactus/docs/a # (é).md", "../../.."],
    )
    expect_in(
        member='href="../../../exactus/docs/a%20%23%20(%C3%A9).md"',
        container=html,
    )


def test_severity_badge_escapes_label() -> None:
    """Unknown severities are escaped before reaching the badge."""
    (html,) = render(
        method="severityBadge",
        inputs=["<img src=x onerror=alert(1)>"],
    )
    expect_not_in(member="<img", container=html)
    expect_in(member="&lt;img", container=html)


def call(*, method: str, arguments: list[object]) -> str:
    """Call one static ``ExactusReport`` function with several arguments.

    Args:
        method: Static method name, such as ``viewFindings``.
        arguments: Positional arguments, JSON-serializable.

    Returns:
        The function's string result.

    """
    completed: CompletedProcess[str] = run(
        args=[
            require(value=Constants.node),
            "-e",
            Constants.spread,
            str(object=Constants.script),
            method,
            dumps(obj=arguments),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    outputs: list[str] = loads(s=completed.stdout)
    return outputs[0]


def _finding(*, number: int, source: str, rule: str) -> dict[str, object]:
    """Build one view-model finding.

    Args:
        number: Finding number.
        source: Producing linter.
        rule: Rule identifier.

    Returns:
        The finding.

    """
    return {
        "id": f"LINTS-{number:03d}",
        "title": "Line too long",
        "message": "Line too long\n  limit is 79",
        "severity": "warning",
        "rule": rule,
        "path": "pkg/a.py",
        "line": 3,
        "column": 7,
        "blocking": False,
        "source": source,
    }


def test_findings_filter_and_group_by_source() -> None:
    """Several sources add a labelled source filter and one group each."""
    model: dict[str, object] = {
        "findings": [
            _finding(number=1, source="ruff", rule="E501"),
            _finding(number=2, source="ruff", rule="F401"),
            _finding(number=3, source="eslint", rule="no-var"),
        ],
        "severity_levels": ["error", "warning", "information"],
        "source_label": "Linter",
    }
    html: str = call(method="viewFindings", arguments=[model, ""])
    for member in (
        '<label class="ds-label" for="findings-source">Linter</label>',
        '<option value="">All linters (3)</option>',
        '<option value="ruff">ruff (2)</option>',
        '<option value="eslint">eslint (1)</option>',
        'data-group="ruff"',
        'data-group="eslint"',
        'data-source="eslint"',
        "pkg/a.py:3:7",
        '<h4 class="finding-title">Line too long</h4>',
        '<p class="finding-message">limit is 79</p>',
    ):
        expect_in(member=member, container=html)
    expect_in(member="2 findings</span></h3>", container=html)


def test_single_source_keeps_a_flat_list() -> None:
    """Findings without several sources get no source filter or groups."""
    model: dict[str, object] = {
        "findings": [_finding(number=1, source="", rule="E501")],
        "severity_levels": ["error", "warning", "info"],
    }
    html: str = call(method="viewFindings", arguments=[model, ""])
    for member in ("findings-source", "finding-group", "<h4"):
        expect_not_in(member=member, container=html)
    expect_in(member='<h3 class="finding-title">', container=html)


def test_finding_rows_link_to_their_findings() -> None:
    """Rows naming a finding link to it and are clickable as a whole."""
    rows: list[dict[str, object]] = [
        {
            "callee": "found.walk",
            "path": "pkg/mod.py",
            "line": 36,
            "reason": "receiver type unknown",
            "call_sites": 1,
            "finding": "KWARGS-008",
        },
    ]
    html: str = call(
        method="recordTable",
        arguments=[
            "Unresolved callees",
            rows,
            None,
            ["callee", "path", "line", "reason", "call_sites", "finding"],
        ],
    )
    for member in (
        (
            '<tr class="row-link" id="row-unresolved-callees-1" tabindex="-1" '
            'data-finding-row="KWARGS-008" data-return-label="Unresolved '
            'callees">'
        ),
        (
            '<a href="#finding-kwargs-008" data-finding-link="KWARGS'
            '-008">found.walk</a>'
        ),
    ):
        expect_in(member=member, container=html)
    headings: list[str] = [
        part.split(sep="</button>", maxsplit=1)[0]
        for part in html.split(sep='data-numeric="')[1:]
    ]
    expect_equal(
        actual=[heading.split(sep=">", maxsplit=1)[1] for heading in headings],
        expected=["Callee", "Path", "Line", "Reason", "Call sites", "Finding"],
    )
    plain: str = call(
        method="recordTable",
        arguments=["Artifacts", [{"name": "a", "path": "b"}], None, []],
    )
    expect_not_in(member="row-link", container=plain)


def test_prose_lists_render_as_notes() -> None:
    """Sentences become a note list; glob-like strings stay code chips."""
    notes: str = call(
        method="extensionBlock",
        arguments=["Methodology", ["Uses the `ast` index.", "Two words."], []],
    )
    expect_in(
        member='<ul class="note-list"><li>Uses the <code>ast</code> index.',
        container=notes,
    )
    globs: str = call(
        method="extensionBlock",
        arguments=["Excluded", ["exactus/packages/**", "build"], []],
    )
    expect_in(member='<ul class="glob-list">', container=globs)


def test_tool_sections_follow_the_mapping_order() -> None:
    """Tool sections keep the mapping order recorded in ``view_order``."""
    sections: str = dumps(
        obj=call(
            method="viewSections",
            arguments=[
                {
                    "view": {"alpha": [], "zeta": [], "findings": []},
                    "view_order": ["findings", "zeta", "alpha"],
                },
            ],
        ),
    )
    expect_true(condition=sections.index('"Zeta"') < sections.index('"Alpha"'))


def test_category_filter_pluralizes_its_label() -> None:
    """A ``Category`` source label reads "All categories" in the filter."""
    model: dict[str, object] = {
        "findings": [
            _finding(number=1, source="Bare imports", rule="bare-import-fix"),
            _finding(number=2, source="Missing type hints", rule="hint"),
        ],
        "severity_levels": ["error", "warning", "info"],
        "source_label": "Category",
    }
    html: str = call(method="viewFindings", arguments=[model, ""])
    expect_in(
        member='<option value="">All categories (2)</option>',
        container=html,
    )


def test_ranges_compacts_only_runs_of_three() -> None:
    """Two-line runs stay comma-separated; longer runs become spans."""
    cases: list[tuple[list[int], str]] = [
        ([7], "7"),
        ([1, 2], "1, 2"),
        ([1, 2, 3], "1-3"),
        ([1, 5, 6, 7, 8, 9, 22, 23, 24], "1, 5-9, 22-24"),
    ]
    for lines, expected in cases:
        expect_equal(
            actual=call(method="ranges", arguments=[lines]),
            expected=expected,
        )


def test_anchor_lines_pass_through_unescaped() -> None:
    """``<a id>`` marker lines survive; other raw HTML stays escaped."""
    outputs: list[str] = render(
        method="markdown",
        inputs=[
            '<a id="finding-f-001"></a>\n### F-001 — Title',
            '<a href="x">y</a>',
        ],
    )
    expect_in(member='<a id="finding-f-001"></a>', container=outputs[0])
    expect_in(member="&lt;a href", container=outputs[1])
    expect_not_in(member='<a href="x"', container=outputs[1])


def test_diagnostic_callouts_have_distinct_colors() -> None:
    """Console and server labels remain distinct and escape their messages."""
    outputs: list[str] = render(
        method="markdown",
        inputs=[
            "> [!WARNING]\n> **Browser console error** <script>bad()</script>",
            "> [!CAUTION]\n> **Server error**",
        ],
    )
    expect_in(member="ds-badge-warn", container=outputs[0])
    expect_in(member="ds-badge-danger", container=outputs[1])
    expect_in(member="&lt;script&gt;", container=outputs[0])
    expect_not_in(member="<script>", container=outputs[0])
