# Copyright (c) 2026
"""Exercise literal-only reconciliation of Python statements."""

from __future__ import annotations

from ast import Assign, Constant, Module, parse, stmt
from typing import TYPE_CHECKING, cast

from exactus.packages.source_merger import python_literals
from exactus.packages.source_merger.model import Replacement, Statement
from exactus.packages.source_merger.python_literals import (
    LiteralFork,
    literal_replacements,
)
from exactus.packages.source_merger.python_parser import PythonParser
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_none,
    expect_true,
    private_call,
    private_result,
    require,
)

if TYPE_CHECKING:
    from ast import AST
    from collections.abc import Iterable


def _record(*, source: str, index: int = 0) -> Statement:
    """Build a statement identity record for a top-level statement.

    Args:
        source: Complete Python program text.
        index: Position in ``Module.body`` to record.

    Returns:
        Statement record whose offsets match the AST node.

    """
    tree: Module = parse(source=source)
    node: stmt = tree.body[index]
    return Statement(
        kind=type(node).__name__,
        start=PythonParser.offset(
            source=source,
            line=node.lineno,
            col=node.col_offset,
        ),
        end=PythonParser.offset(
            source=source,
            line=node.end_lineno or node.lineno,
            col=node.end_col_offset or 0,
        ),
        shape="",
        exact="",
    )


def _fork(*, source: str, index: int = 0) -> LiteralFork:
    """Pair a source text with the record of one of its statements.

    Args:
        source: Complete Python program text.
        index: Position in ``Module.body`` to record.

    Returns:
        Fork wrapper for ``literal_replacements``.

    """
    return LiteralFork(
        source=source,
        record=_record(source=source, index=index),
    )


def test_literal_edit_projects_onto_tool_wrapping() -> None:
    """A changed literal is patched at its tool-side wrapped position."""
    tool_source: str = """\
x = (
    "old"
)
"""
    replacements: tuple[Replacement, ...] = require(
        value=literal_replacements(
            original=_fork(
                source="""\
x = "old"
""",
            ),
            user=_fork(
                source="""\
x = "new"
""",
            ),
            tool=_fork(source=tool_source),
        ),
    )
    expect_equal(actual=len(replacements), expected=1)
    patch: Replacement = replacements[0]
    expect_equal(actual=patch.text, expected='"new"')
    expect_equal(
        actual=tool_source[patch.start : patch.end],
        expected='"old"',
    )
    expect_equal(actual=patch.scope, expected="literal")


def test_literal_changes_inside_calls_collect_each_leaf() -> None:
    """Every changed constant leaf produces its own replacement."""
    replacements: tuple[Replacement, ...] = require(
        value=literal_replacements(
            original=_fork(
                source="""\
x = f(1, 2)
""",
            ),
            user=_fork(
                source="""\
x = f(3, 4)
""",
            ),
            tool=_fork(
                source="""\
x = f(1, 2)
""",
            ),
        ),
    )
    expect_equal(actual=len(replacements), expected=2)


def test_unparsable_original_returns_none() -> None:
    """A fork that cannot be parsed declines reconciliation."""
    original: LiteralFork = LiteralFork(
        source="""\
x = (
""",
        record=_record(
            source="""\
x = 1
""",
        ),
    )
    expect_none(
        value=literal_replacements(
            original=original,
            user=_fork(
                source="""\
x = 2
""",
            ),
            tool=_fork(
                source="""\
x = 1
""",
            ),
        ),
    )


def test_unmatched_record_returns_none() -> None:
    """Offsets that identify no unique statement decline reconciliation."""
    tool: LiteralFork = LiteralFork(
        source="""\
x = 1
""",
        record=Statement(
            kind="Assign",
            start=999,
            end=1000,
            shape="",
            exact="",
        ),
    )
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = 1
""",
            ),
            user=_fork(
                source="""\
x = 2
""",
            ),
            tool=tool,
        ),
    )


def test_statement_node_returns_the_unique_match() -> None:
    """A resolvable record locates its AST statement."""
    source: str = """\
x = 1
"""
    node: stmt | None = cast(
        typ="stmt | None",
        val=private_call(
            owner=python_literals,
            name="_statement_node",
            source=source,
            record=_record(source=source),
        ),
    )
    expect_true(condition=isinstance(node, Assign))


def test_structural_change_returns_none() -> None:
    """A node-kind change is not a literal-only edit."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = 1
""",
            ),
            user=_fork(
                source="""\
x = [1]
""",
            ),
            tool=_fork(
                source="""\
x = 1
""",
            ),
        ),
    )


def test_concurrent_literal_change_returns_none() -> None:
    """Both forks changing a constant is a conflict, not a projection."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = 1
""",
            ),
            user=_fork(
                source="""\
x = 2
""",
            ),
            tool=_fork(
                source="""\
x = 3
""",
            ),
        ),
    )


def test_tool_only_change_returns_none() -> None:
    """An unchanged user literal contributes no replacements."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = 1
""",
            ),
            user=_fork(
                source="""\
x = 1
""",
            ),
            tool=_fork(
                source="""\
x = 2
""",
            ),
        ),
    )


def test_list_length_change_returns_none() -> None:
    """Growing a container is a structural edit, not a literal edit."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = [1]
""",
            ),
            user=_fork(
                source="""\
x = [1, 2]
""",
            ),
            tool=_fork(
                source="""\
x = [1]
""",
            ),
        ),
    )


def test_name_change_returns_none() -> None:
    """Renaming a reference is not a literal-only edit."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = a
""",
            ),
            user=_fork(
                source="""\
x = b
""",
            ),
            tool=_fork(
                source="""\
x = a
""",
            ),
        ),
    )


def test_list_item_name_change_returns_none() -> None:
    """A renamed reference inside a container fails reconciliation."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
x = [a]
""",
            ),
            user=_fork(
                source="""\
x = [b]
""",
            ),
            tool=_fork(
                source="""\
x = [a]
""",
            ),
        ),
    )


def test_non_ast_list_items_return_none() -> None:
    """Scalar name lists cannot reconcile as literal edits."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
global a
""",
            ),
            user=_fork(
                source="""\
global b
""",
            ),
            tool=_fork(
                source="""\
global a
""",
            ),
        ),
    )


def test_dropped_optional_field_returns_none() -> None:
    """Removing an optional child is a structural edit."""
    expect_none(
        value=literal_replacements(
            original=_fork(
                source="""\
assert x, "m"
""",
            ),
            user=_fork(
                source="""\
assert x
""",
            ),
            tool=_fork(
                source="""\
assert x, "m"
""",
            ),
        ),
    )


def _ctx() -> object:
    """Build shared walk state for private-comparison probes.

    Returns:
        Empty comparison context accepted by the literal helpers.

    """
    return private_call(
        owner=python_literals,
        name="_Ctx",
        tool_source="",
        user_source="",
        changes=[],
    )


def test_compare_constants_accepts_non_constant_nodes() -> None:
    """Non-literal triples are delegated back to structural comparison."""
    ctx: object = _ctx()
    node: AST = parse(source="x = 1").body[0]
    expect_true(
        condition=private_result(
            owner=python_literals,
            name="_compare_constants",
            kind=bool,
            old=node,
            own=node,
            latest=node,
            ctx=ctx,
        ),
    )


def test_compare_lists_rejects_non_list_fields() -> None:
    """Mismatched field kinds cannot reconcile recursively."""
    ctx: object = _ctx()
    expect_false(
        condition=private_result(
            owner=python_literals,
            name="_compare_lists",
            kind=bool,
            old_value=1,
            own_value=1,
            latest_value=1,
            ctx=ctx,
        ),
    )


def test_compare_lists_rejects_non_ast_items() -> None:
    """Lists of scalars cannot reconcile recursively."""
    ctx: object = _ctx()
    expect_false(
        condition=private_result(
            owner=python_literals,
            name="_compare_lists",
            kind=bool,
            old_value=["a"],
            own_value=["a"],
            latest_value=["a"],
            ctx=ctx,
        ),
    )


def test_compare_field_rejects_misaligned_names() -> None:
    """Fields from different positions cannot be compared."""
    ctx: object = _ctx()
    expect_false(
        condition=private_result(
            owner=python_literals,
            name="_compare_field",
            kind=bool,
            triple=(
                ("value", 1),
                ("kind", 1),
                ("kind", 1),
            ),
            ctx=ctx,
        ),
    )


def test_fields_skip_context_and_opaque_values() -> None:
    """Context fields and non-scalar values are not semantic leaves."""
    node: AST = Constant(value=b"raw")
    fields: Iterable[tuple[str, object]] = cast(
        typ="Iterable[tuple[str, object]]",
        val=private_call(
            owner=python_literals,
            name="_fields",
            node=node,
        ),
    )
    names: list[str] = [name for name, _ in fields]
    expect_true(condition="value" not in names)
    expect_true(condition="kind" in names)
