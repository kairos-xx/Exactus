# Copyright (c) 2026
"""Regression tests for conservative Python simplifications."""

from ast import parse
from itertools import product
from pathlib import Path
from textwrap import dedent

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.lints.python_simplify import (
    PythonSimplifyResult,
    simplify_python_files,
    simplify_python_source,
)


def test_annotated_immediate_return_is_preserved() -> None:
    """Never erase a type annotation by inlining its initializer."""
    source: str = """\
def compute():
    value: int = 42
    return value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_false(condition=bool(result.proposals))
    expect_equal(actual=result.skipped[0].rule, expected="PYS000")
    expect_true(condition="annotation" in result.skipped[0].reason)


def test_global_binding_is_never_inlined() -> None:
    """A ``global`` write must survive; it is not a removable local."""
    source: str = dedent(
        text="""\
    def compute():
        global value
        value = init()
        return value
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS001")
    expect_true(condition="global" in result.skipped[0].reason)


def test_nonlocal_binding_is_never_inlined() -> None:
    """A ``nonlocal`` write must survive; it is not a removable local."""
    source: str = dedent(
        text="""\
    def outer():
        value = 0

        def compute():
            nonlocal value
            value = init()
            return value
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)


def test_global_assignment_is_never_folded_into_walrus() -> None:
    """A walrus binds a local; it cannot replace a ``global`` write."""
    source: str = dedent(
        text="""\
    def compute():
        global value
        value = init()
        if value:
            use(value)
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS002")


def test_single_use_expression_statement_is_inlined() -> None:
    """PYS003 inlines a one-use local into an expression statement."""
    source: str = """\
def compute():
    value = init()
    consume(value)
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    consume((init()))
""",
    )
    expect_equal(actual=result.proposals[0].rule, expected="PYS003")


def test_single_use_assignment_rhs_is_inlined() -> None:
    """PYS003 inlines a one-use local used once on a later right side."""
    source: str = """\
def compute():
    value = init()
    other = value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    other = (init())
""",
    )


def test_annotated_target_keeps_annotation_when_inlined() -> None:
    """PYS003 preserves the annotation on the consuming statement."""
    source: str = """\
def compute():
    value = init()
    other: int = value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    other: int = (init())
""",
    )


def test_multiple_loads_in_statement_are_skipped() -> None:
    """PYS003 refuses to duplicate an expression across two reads."""
    source: str = """\
def compute():
    value = init()
    y = value + value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS003")


def test_lambda_capture_is_never_inlined() -> None:
    """A load deferred inside a lambda body is not a candidate."""
    source: str = """\
def compute():
    value = init()
    return lambda: value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)


def test_comprehension_load_is_never_inlined() -> None:
    """A load inside a comprehension element is not provably once."""
    source: str = """\
def compute():
    value = init()
    items = [i for i in value]
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS003")


def test_dead_store_with_constant_is_removed() -> None:
    """PYS004 drops a constant store unconditionally overwritten."""
    source: str = """\
def compute():
    value = 1
    value = init()
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    value = init()
""",
    )
    expect_equal(actual=result.proposals[0].rule, expected="PYS004")


def test_dead_store_with_effectful_initializer_is_kept() -> None:
    """PYS004 never removes a call that may have side effects."""
    source: str = """\
def compute():
    value = init()
    value = reset()
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS004")


def test_global_dead_store_is_kept() -> None:
    """PYS004 does not remove stores visible at module scope."""
    source: str = """\
def compute():
    global value
    value = 1
    value = init()
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)


def test_boolean_composition_in_return() -> None:
    """PYS005 inlines a local evaluated first in a boolean return."""
    source: str = """\
def compute():
    value = init()
    return value or default
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    return (init()) or default
""",
    )
    expect_equal(actual=result.proposals[0].rule, expected="PYS005")


def test_non_first_operand_is_never_reordered() -> None:
    """PYS005 refuses when inlining would reorder evaluation."""
    source: str = """\
def compute():
    value = init()
    return default or value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.skipped[0].rule, expected="PYS005")
    expect_true(condition="first evaluated" in result.skipped[0].reason)


def test_conditional_test_composition_in_return() -> None:
    """PYS006 inlines a local evaluated first in a conditional test."""
    source: str = """\
def compute():
    value = init()
    return yes if value else no
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
def compute():
    return yes if (init()) else no
""",
    )
    expect_equal(actual=result.proposals[0].rule, expected="PYS006")


def test_conditional_body_load_is_never_inlined() -> None:
    """PYS006 refuses loads inside a conditional branch."""
    source: str = dedent(
        text="""\
    def compute():
        value = init()
        return value if flag else no
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)


def test_overlapping_proposals_resolve_deterministically() -> None:
    """Conflicting edits skip the earlier proposal, then converge."""
    source: str = """\
def compute():
    x = 1
    y = x
    return y
"""
    once: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_equal(
        actual=once.source,
        expected="""\
def compute():
    x = 1
    return x
""",
    )
    twice: PythonSimplifyResult = simplify_python_source(
        source=once.source,
        fix=True,
    )
    expect_equal(
        actual=twice.source,
        expected="""\
def compute():
    return 1
""",
    )
    expect_false(
        condition=simplify_python_source(
            source=twice.source,
            fix=True,
        ).changed,
    )


def test_multiline_assignment_records_skip() -> None:
    """A multi-line initializer reports a stable guard skip."""
    source: str = dedent(
        text="""\
    def compute():
        x = (
            calculate()
        )
        return x
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.skipped[0].rule, expected="PYS000")
    expect_true(condition="multi-line" in result.skipped[0].reason)


def test_commented_assignment_records_skip() -> None:
    """An assignment carrying a comment reports a stable guard skip."""
    source: str = """\
def compute():
    x = 1  # keep
    return x
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.skipped[0].rule, expected="PYS000")
    expect_true(condition="comment" in result.skipped[0].reason)


def test_try_body_pairs_are_never_touched() -> None:
    """Statements nested inside ``try`` keep their exception timing."""
    source: str = dedent(
        text="""\
    def compute():
        try:
            x = init()
            return x
        finally:
            cleanup()
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.source, expected=source)


def test_awaited_return_leads_with_load() -> None:
    """PYS005 inlines the operand of an awaited return value."""
    source: str = """\
async def compute():
    value = init()
    return await value
"""
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="""\
async def compute():
    return await (init())
""",
    )


def test_walrus_in_if_and_preserve_body() -> None:
    """Introduce a named expression without re-evaluating its initializer."""
    source: str = dedent(
        text="""\
    def compute():
        value = calculate()
        if value:
            consume(value)
        return value
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition="if (value := calculate()):" in result.source)
    expect_true(condition="consume(value)" in result.source)
    expect_equal(actual=result.proposals[0].rule, expected="PYS002")
    expect_false(
        condition=simplify_python_source(
            source=result.source,
            fix=True,
        ).changed,
    )


def test_audit_does_not_modify_source() -> None:
    """Audit mode returns proposed edits without applying them."""
    source: str = """\
def compute():
    x = 1
    return x
"""
    result: PythonSimplifyResult = simplify_python_source(source=source)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=len(result.proposals), expected=1)
    expect_false(condition=result.changed)


def test_nonadjacent_statements_are_preserved() -> None:
    """Never move computation past statements with observable behavior."""
    source: str = """\
def compute():
    x = calculate()
    notify()
    return x
"""
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_nested_read_prevents_inline() -> None:
    """Maintain variables referenced in more than one expression."""
    source: str = """\
def compute():
    x = 1
    print(x)
    return x
"""
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_comment_prevents_rewrite() -> None:
    """Do not relocate source lines containing comments."""
    source: str = """\
def compute():
    x = 1  # keep
    return x
"""
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_walrus_can_be_disabled() -> None:
    """Explicit policy disables named-expression changes."""
    source: str = """\
def compute():
    x = calculate()
    if x:
        use(x)
"""
    expect_false(
        condition=simplify_python_source(
            source=source,
            fix=True,
            walrus=False,
        ).changed,
    )


def test_multiline_assignment_is_not_moved() -> None:
    """Skip expressions that cannot be replaced as one source line."""
    source: str = dedent(
        text="""\
    def compute():
        x = (
            calculate()
        )
        if x:
            use(x)
    """,
    )
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_file_runner_audit_only(tmp_path: Path) -> None:
    """No-fix mode leaves files byte-for-byte unchanged.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "source.py"
    _ = file.write_text(
        data="""\
def f():
    x = 5
    return x
""",
        encoding="utf-8",
    )
    before: bytes = file.read_bytes()
    report: dict[str, int] = simplify_python_files(files=(file,), fix=False)
    expect_equal(
        actual=report,
        expected={"files": 1, "proposals": 1, "skipped": 0, "changed": 0},
    )
    expect_equal(actual=file.read_bytes(), expected=before)


def test_file_runner_fixes_once(tmp_path: Path) -> None:
    """Repeated execution converges to one stable representation.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "source.py"
    _ = file.write_text(
        data="""\
def f():
    x = 5
    return x
""",
        encoding="utf-8",
    )
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=1,
    )
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=0,
    )


def test_file_runner_preserves_utf8_bom_and_crlf(tmp_path: Path) -> None:
    """Preserve BOM and newline bytes after an atomic transform.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "crlf.py"
    original: bytes = b"\xef\xbb\xbfdef f():\r\n    x = 4\r\n    return x\r\n"
    _ = file.write_bytes(data=original)
    result: dict[str, int] = simplify_python_files(files=(file,), fix=True)
    expect_equal(actual=result["changed"], expected=1)
    expect_equal(
        actual=file.read_bytes(),
        expected=b"\xef\xbb\xbfdef f():\r\n    return 4\r\n",
    )


def test_file_runner_supports_source_encoding_cookie(tmp_path: Path) -> None:
    """Honor PEP 263 encodings instead of unconditionally using UTF-8.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "latin1.py"
    text: str = """\
# coding: latin-1
def f():
    x = 'café'
    return x
"""
    _ = file.write_bytes(data=text.encode(encoding="latin-1"))
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=1,
    )
    expect_equal(
        actual=file.read_bytes(),
        expected="""\
# coding: latin-1
def f():
    return 'café'
""".encode(encoding="latin-1"),
    )


def test_file_runner_skips_unreadable_python(tmp_path: Path) -> None:
    """Invalid source should be skipped without an attempted rewrite.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "invalid.py"
    _ = file.write_bytes(data=b"\xff\xfe\xff")
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True),
        expected={"files": 0, "proposals": 0, "skipped": 0, "changed": 0},
    )


def test_file_runner_preserves_symlink_target(tmp_path: Path) -> None:
    """Avoid replacing links with unrelated temporary regular files.

    Args:
        tmp_path: Per-test project directory.

    """
    target: Path = tmp_path / "actual.py"
    _ = target.write_text(
        data="""\
def f():
    x = 9
    return x
""",
    )
    alias: Path = tmp_path / "alias.py"
    alias.symlink_to(target=target)
    expect_equal(
        actual=simplify_python_files(files=(alias,), fix=True)["changed"],
        expected=0,
    )
    expect_true(condition=alias.is_symlink())
    expect_equal(
        actual=target.read_text(),
        expected="""\
def f():
    x = 9
    return x
""",
    )


def test_simplifier_invariants_hold_across_generated_space() -> None:
    """Exhaustive generated-space check of the core invariants.

    Every generated ``def f()`` module (identifier x initializer x
    second-statement shape, 288 combinations) must produce output that
    reparses, is byte-for-byte deterministic, and is a fixed point of a
    second pass; every proposal and skip must carry complete metadata.

    """
    names: tuple[str, ...] = ("a", "value", "tmp_result", "x1", "inner_v", "z")
    initializers: tuple[str, ...] = (
        "0",
        "1",
        "-1",
        "f()",
        "g(1)",
        "'s'",
        "[]",
        "(1, 2)",
    )
    uses: tuple[str, ...] = (
        "return {n}",
        """\
if {n}:
        return 1
    return 0""",
        """\
{n}.append(1)
    return {n}""",
        "return {n} or 0",
        "return 0 if {n} else 1",
        """\
{n} = g()
    return {n}""",
    )
    for name, initializer, use in product(names, initializers, uses):
        source: str = f"""\
def f():
    {name} = {initializer}
    {use.format(n=name)}
"""
        first: PythonSimplifyResult = simplify_python_source(
            source=source,
            fix=True,
        )
        parse(source=first.source)
        expect_equal(
            actual=simplify_python_source(source=source, fix=True).source,
            expected=first.source,
        )
        expect_equal(
            actual=simplify_python_source(
                source=first.source,
                fix=True,
            ).source,
            expected=first.source,
        )
        for proposal in first.proposals:
            expect_true(condition=bool(proposal.rule))
            expect_true(condition=proposal.line > 0)
            expect_true(condition=bool(proposal.before))
            expect_true(condition=proposal.before != proposal.after)
            expect_true(condition=bool(proposal.reason))
        for skip in first.skipped:
            expect_true(condition=bool(skip.rule))
            expect_true(condition=skip.line >= 0)
            expect_true(condition=bool(skip.reason))
