"""Regression tests for identity-preserving source mutation reconciliation."""

from __future__ import annotations

from ast import parse
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from exactus.packages.source_merger import (
    DeltaPolicy,
    MergeResult,
    SourceMerger,
    measure,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    fail,
)

if TYPE_CHECKING:
    from exactus.packages.source_merger.model import Language


def reconcile(
    *,
    language: Language,
    original: str,
    user: str,
    tool: str,
) -> MergeResult:
    """Merge three source versions using the public Python API.

    Args:
        language: Parser language.
        original: Common ancestor.
        user: User-edited fork.
        tool: Tool-refactored fork.

    Returns:
        Merge result with explicit conflict reporting.

    """
    return SourceMerger(
        original=original,
        user_edited=user,
        tool_refactored=tool,
        language=language,
    ).merge()


@pytest.mark.parametrize(
    ("original", "user", "tool", "required"),
    [
        (
            """\
def f(x):
    return x + 1
""",
            (
                """\
def f(x):
    if x < 0:
        raise ValueError('negative')
    return x + 1
"""
            ),
            """\
def f(x: int) -> int:
    return x + 1
""",
            ("x: int", "if x < 0", "raise ValueError"),
        ),
        (
            """\
def process(value):
    return value + 1
""",
            (
                """\
def process(value):
    if value < 0:
        raise ValueError('negative')
    return value + 1
"""
            ),
            """\
def calculate(number: int) -> int:
    return number + 1
""",
            ("def calculate", "if number < 0", "return number + 1"),
        ),
        (
            """\
def f(x):
    result = x + 1
    return result
""",
            """\
def f(x):
    result = x + 2
    return result
""",
            (
                """\
def f(x: int) -> int:
    total: int = x + 1
    return total
"""
            ),
            ("total: int = x + 2", "return total"),
        ),
        (
            """\
LIMIT = 5
""",
            """\
LIMIT = 7
""",
            """\
from typing import Final, final
@final
class Constants:
    LIMIT: Final[int] = 5
""",
            ("@final", "class Constants", "LIMIT: Final[int] = 7"),
        ),
        (
            (
                """\
class C:
    def first(self):
        return 1

    def second(self):
        return 2
"""
            ),
            (
                """\
class C:
    def first(self):
        return 9

    def second(self):
        return 2
"""
            ),
            (
                """\
class C:
    def second(self):
        return 2

    def first(self):
        return 1
"""
            ),
            ("def second", "return 9", "def first"),
        ),
        (
            """\
def f(x):
    validate(x)
    transform(x)
    save(x)
""",
            """\
def f(x):
    validate(x)
    transform(x, strict=True)
    save(x)
""",
            """\
def f(x):
    prepare(x)
    save(x)

def prepare(x):
    validate(x)
    transform(x)
""",
            ("def prepare", "transform(x, strict=True)", "save(x)"),
        ),
        (
            """\
def f(x):
    return x
""",
            """\
def f(x):
    return x + 2
""",
            (
                """\
def f(x: int) -> int:
    return x

def extra():
    return 0
"""
            ),
            ("return x + 2", "def extra"),
        ),
    ],
)
def test_python_refactoring(
    *,
    original: str,
    user: str,
    tool: str,
    required: tuple[str, ...],
) -> None:
    """Typing, moves and new declarations preserve user edits.

    Args:
        original: Common-ancestor source.
        user: Concurrently edited source.
        tool: Refactored source.
        required: Fragments expected in the merged result.

    """
    result: MergeResult = reconcile(
        language="python",
        original=original,
        user=user,
        tool=tool,
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    if result.source is None:
        fail(message="result.source is None")
    parse(source=result.source)
    expect_true(condition=all(part in result.source for part in required))
    if "def second" in result.source:
        expect_true(
            condition=result.source.index("def second")
            < result.source.index(
                "def first",
            ),
        )
    if "def prepare" in result.source:
        expect_true(
            condition=result.source.index("save(x)")
            < result.source.index(
                "def prepare",
            ),
        )


@pytest.mark.parametrize(
    ("language", "original", "user", "tool", "required"),
    [
        (
            "javascript",
            """\
function f(x) {
  return x + 1;
}
""",
            (
                """\
function f(x) {
  if (x < 0) throw Error('negative');
  return x + 1;
}
"""
            ),
            """\
const f = (value) => value + 1;
""",
            ("const f", "=> {", "if (value < 0)", "return value + 1"),
        ),
        (
            "javascript",
            """\
function compute(x) {
  return x + 1;
}
""",
            """\
function compute(x) {
  return x + 2;
}
""",
            """\
const calculate = (value) => value + 1;
""",
            ("const calculate", "value + 2"),
        ),
        (
            "javascript",
            """\
function say(x) {
  return x + 1;
}
""",
            """\
function say(x) {
  console.log('x');
  return x + 1;
}
""",
            """\
const say = (value) => value + 1;
""",
            ("console.log('x')", "value + 1"),
        ),
        (
            "typescript",
            """\
function f(x) {
  return x + 1;
}
""",
            """\
function f(x) {
  if (x < 0) throw Error('bad');
  return x + 1;
}
""",
            """\
const f = (x: number): number => x + 1;
""",
            ("x: number", "if (x < 0)"),
        ),
        (
            "css",
            """\
.old { color: red; }
""",
            """\
.old { color: blue; }
""",
            """\
.new { color: red; }
""",
            (".new", "color: blue"),
        ),
        (
            "css",
            """\
.x { --old: red; }
""",
            """\
.x { --old: blue; }
""",
            """\
.x { --new: red; }
""",
            ("--new: blue",),
        ),
        (
            "css",
            """\
.a { color: red; }
.b { opacity: 1; }
""",
            """\
.a { color: blue; }
.b { opacity: 1; }
""",
            """\
.b { opacity: 1; }
.a { color: red; }
""",
            ("color: blue", "opacity: 1"),
        ),
        (
            "html",
            """\
<div id="a"><span>One</span></div>
""",
            """\
<div id="a"><span>Two</span></div>
""",
            """\
<main><div id="a"><span>One</span></div></main>
""",
            ("<main>", "<span>Two</span>"),
        ),
        (
            "html",
            """\
<div id="hero" class="old"><span>Hello</span></div>
""",
            """\
<div id="hero" class="new"><span>Welcome</span></div>
""",
            (
                """\
<main><div data-x="1" id="hero" class="old"><span>Hello</span></div></main>
"""
            ),
            ('class="new"', 'data-x="1"', "Welcome"),
        ),
        (
            "html",
            """\
<div id="outer"><b id="inner">A</b></div>
""",
            """\
<div id="outer"><b id="inner">B</b></div>
""",
            """\
<section><div id="outer"><b id="inner">A</b></div></section>
""",
            ("<section>", '<b id="inner">B</b>'),
        ),
    ],
)
def test_other_languages(
    *,
    language: Language,
    original: str,
    user: str,
    tool: str,
    required: tuple[str, ...],
) -> None:
    """Merge JavaScript arrow conversion, CSS, and HTML movement.

    Args:
        language: Source grammar.
        original: Common-ancestor source.
        user: Concurrently edited source.
        tool: Refactored source.
        required: Fragments expected in the merged result.

    """
    result: MergeResult = reconcile(
        language=language,
        original=original,
        user=user,
        tool=tool,
    )
    expect_true(condition=result.success, message=str(object=result.conflicts))
    if result.source is None:
        fail(message="result.source is None")
    expect_true(condition=all(part in result.source for part in required))


@pytest.mark.parametrize(
    ("language", "original", "user", "tool", "kind"),
    [
        (
            "python",
            """\
def f(x):
    return x
""",
            """\
def f(x):
    return x

print(f(3))
""",
            """\
def g(x):
    return x
""",
            "unsupported_transformation",
        ),
        (
            "python",
            """\
def f(x):
    return x
""",
            """\
def f(x: str):
    return x
""",
            """\
def f(x: int):
    return x
""",
            "unsupported_transformation",
        ),
        (
            "python",
            """\
def f(x):
    return x
""",
            """\
def f(y):
    return y
""",
            """\
def f(x: int):
    return x
""",
            "unsupported_transformation",
        ),
        (
            "python",
            """\
X = 1
""",
            """\
X = 2
""",
            """\
X = 3
""",
            "concurrent_change",
        ),
        (
            "python",
            """\
def f(x):
    return x
""",
            """\
def f(x):
    # User note
    return x
""",
            """\
def f(x: int):
    return x
""",
            "unsupported_transformation",
        ),
        (
            "javascript",
            """\
function f(x) { return x; }
""",
            """\
function f(y) { return y; }
""",
            """\
const f = (x) => x;
""",
            "unsupported_transformation",
        ),
        (
            "html",
            """\
<div id="a" class="old">A</div>
""",
            """\
<div id="a" class="user">A</div>
""",
            """\
<div id="a" class="tool">A</div>
""",
            "concurrent_change",
        ),
        (
            "html",
            """\
<div id="a">A</div>
""",
            """\
<div id="a">B</div>
""",
            """\
<div id="a"><b>A</b></div>
""",
            "textual_conflict",
        ),
        (
            "css",
            """\
.a { color: red; }
""",
            """\
.a { color: blue; }
""",
            """\
.a { color: green; }
""",
            "missing_anchor",
        ),
    ],
)
def test_conflicts(
    *,
    language: Language,
    original: str,
    user: str,
    tool: str,
    kind: str,
) -> None:
    """Reject unsupported or incompatible changes without an output.

    Args:
        language: Source grammar.
        original: Common-ancestor source.
        user: Concurrently edited source.
        tool: Refactored source.
        kind: Expected conflict category.

    """
    result: MergeResult = reconcile(
        language=language,
        original=original,
        user=user,
        tool=tool,
    )
    expect_false(condition=result.success)
    expect_none(value=result.source)
    expect_true(
        condition=any(item.kind == kind for item in result.conflicts),
        message=str(object=result.conflicts),
    )


def test_no_op_returns_tool() -> None:
    """Return the untouched tool fork when no user edits occurred."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
x = 1
""",
        user="""\
x = 1
""",
        tool="""\
x: int = 1
""",
    )
    expect_true(
        condition=result.success
        and result.source
        == """\
x: int = 1
""",
    )


def test_no_tool_edits_returns_user() -> None:
    """Return current user source when the tool made no changes."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
x = 1
""",
        user="""\
x = 2
""",
        tool="""\
x = 1
""",
    )
    expect_true(
        condition=result.success
        and result.source
        == """\
x = 2
""",
    )


def test_invalid_python_fails_closed() -> None:
    """Reject a syntactically incomplete original ancestor."""
    result: MergeResult = reconcile(
        language="python",
        original="def x(: pass",
        user="def x(: return 1",
        tool="def y(: pass",
    )
    expect_true(condition=not result.success and result.source is None)
    expect_true(
        condition=any(item.kind == "parse_error" for item in result.conflicts),
    )


def test_python_wrapping_survives_literal_change() -> None:
    """Wrapped literals keep refactor-generated formatting."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f(x):
    return sum([1, 2]) + x
""",
        user="""\
def f(x):
    return sum([1, 3]) + x
""",
        tool=(
            dedent(
                text="""\
    def f(x: int) -> int:
        return (
            sum(
                [
                    1,
                    2,
                ]
            ) + x
        )
    """,
            )
        ),
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_in(member="                3,", container=result.source)
    expect_in(
        member="""\
    return (
""",
        container=result.source,
    )


def test_python_new_import_survives_tool_import_regrouping() -> None:
    """Preserve user import additions alongside tool import consolidation."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
from typing import Optional

def f(x):
    return x + 1
""",
        user=(
            dedent(
                text="""\
    from pathlib import Path
    from typing import Optional

    def f(x):
        return x + 2
    """,
            )
        ),
        tool=(
            dedent(
                text="""\
    from typing import Final, Optional

    def f(x: int) -> int:
        return x + 1
    """,
            )
        ),
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_in(member="from pathlib import Path", container=result.source)
    expect_in(
        member="from typing import Final, Optional",
        container=result.source,
    )
    expect_in(member="return x + 2", container=result.source)


def test_css_property_reference_tracks_renaming() -> None:
    """Inserted custom-property references follow tool-side renames."""
    result: MergeResult = reconcile(
        language="css",
        original="""\
.x {
  --old: red;
}
""",
        user="""\
.x {
  --old: red;
  color: var(--old);
}
""",
        tool="""\
.x {
  --new: red;
}
""",
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_in(
        member="""\
  color: var(--new);
}""",
        container=result.source,
    )


def test_html_independent_attribute_addition() -> None:
    """Retain two independently added attributes during HTML relocation."""
    result: MergeResult = reconcile(
        language="html",
        original="""\
<div id="hero">Hi</div>
""",
        user="""\
<div id="hero" title="Hello">Hi</div>
""",
        tool="""\
<main><div id="hero" data-x="1">Hi</div></main>
""",
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_true(
        condition='data-x="1"' in result.source
        and 'title="Hello"' in result.source,
    )


def test_js_regex_is_not_rewritten_during_parameter_rename() -> None:
    """Renames inside calls leave regex literals untouched."""
    result: MergeResult = reconcile(
        language="javascript",
        original="""\
function f(x) {
  return x;
}
""",
        user="""\
function f(x) {
  if (/x/.test(x)) throw Error('bad');
  return x;
}
""",
        tool="""\
const f = (value) => value;
""",
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_in(member="/x/.test(value)", container=result.source)


def test_user_import_removal_that_tool_retains_is_conflict() -> None:
    """Reject removing tool-required imports without reference analysis."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
import os
import sys

x = 1
""",
        user="""\
import os

x = 2
""",
        tool="""\
import sys
import os

x: int = 1
""",
    )
    expect_true(condition=not result.success and result.source is None)
    expect_true(
        condition=any(item.scope == "imports" for item in result.conflicts),
    )


def test_css_single_line_without_trailing_newline() -> None:
    """Never let PostCSS offset conventions overrun a closing brace."""
    result: MergeResult = reconcile(
        language="css",
        original=".a { color: red; }",
        user=".a { color: blue; }",
        tool=".b { color: red; }",
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_true(
        condition=".b" in result.source and "color: blue" in result.source,
    )


def test_python_function_moved_into_final_class() -> None:
    """Track a function converted into a static method in a generated class."""
    result: MergeResult = reconcile(
        language="python",
        original="""\
def f(x):
    return x + 1
""",
        user="""\
def f(x):
    return x + 2
""",
        tool=(
            dedent(
                text="""\
    from typing import final
    @final
    class Operations:
        @staticmethod
        def f(x: int) -> int:
            return x + 1
    """,
            )
        ),
    )
    expect_true(condition=result.success and result.source is not None)
    if result.source is None:
        fail(message="result.source is None")
    expect_in(
        member="""\
@final
class Operations""",
        container=result.source,
    )
    expect_in(member="return x + 2", container=result.source)


def test_delta_policy_blocks_large_paste_in_short_fork() -> None:
    """Large pastes exceed the burst mutation budget."""
    result: MergeResult = SourceMerger(
        original="""\
def f():
    return 1
""",
        user_edited="""\
def f():
    return 1
"""
        + """\

""".join((f"value_{i} = {i}") for i in range(100)),
        tool_refactored="""\
def f() -> int:
    return 1
""",
        language="python",
        delta_policy=DeltaPolicy(max_user_inserted_tokens=40),
        fork_elapsed_seconds=5.0,
    ).merge()
    expect_false(condition=result.success)
    expect_true(
        condition=any(
            conflict.kind == "delta_exceeded" for conflict in result.conflicts
        ),
    )


def test_delta_policy_ignores_line_wrapping() -> None:
    """Whitespace-only Python changes do not consume a lexical edit budget."""
    original: str = """\
value = calculate(1, 2)
"""
    wrapped: str = """\
value = calculate(
    1,
    2,
)
"""
    expect_equal(
        actual=measure(
            original=original,
            changed=wrapped,
            language="python",
        ).edit_events,
        expected=0,
    )
    expect_equal(actual=DeltaPolicy().short_fork_seconds, expected=5.0)


def test_delta_policy_custom_burst_threshold() -> None:
    """Custom burst threshold enforces the configured budget."""
    result: MergeResult = SourceMerger(
        original="""\
def f():
    return 1
""",
        user_edited="""\
def f():
    return 2
""",
        tool_refactored="""\
def f() -> int:
    return 1
""",
        language="python",
        delta_policy=DeltaPolicy(max_user_tokens_per_second=0.1),
        fork_elapsed_seconds=1.0,
    ).merge()
    expect_true(
        condition=any(
            conflict.kind == "delta_exceeded" for conflict in result.conflicts
        ),
    )
