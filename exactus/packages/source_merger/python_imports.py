"""Isolate Python import header refactoring from unrelated concurrent edits."""

from __future__ import annotations

from ast import Constant, Expr, Import, ImportFrom, Module, parse, stmt
from ast import alias as ast_alias
from dataclasses import dataclass
from io import StringIO
from tokenize import COMMENT, generate_tokens
from typing import final

from exactus.packages.source_merger.model import MergeConflict, Replacement

type _Binding = tuple[str, str, str, str]


@final
@dataclass(frozen=True, slots=True)
class ImportRegion:
    """Contiguous, safely isolatable module import header.

    Attributes:
        start: Start of first module-level import line.
        end: End of last import line including its newline.
        text: Preserved source of the entire import region.
        bindings: Full alias identities from the region.
        aliases: Original import nodes with their alias names.

    """

    start: int
    end: int
    text: str
    bindings: frozenset[_Binding]
    aliases: tuple[tuple[_Binding, str], ...]


def _binding(
    *,
    node: Import | ImportFrom,
    alias: ast_alias,
) -> _Binding:
    """Return an import binding including its alias and relative module level.

    Args:
        node: Containing import statement.
        alias: Imported name within the statement.

    Returns:
        Stable lexical identity for one import binding.

    """
    if isinstance(node, Import):
        return ("import", "", alias.name, alias.asname or "")
    return (
        "from",
        "." * node.level + (node.module or ""),
        alias.name,
        alias.asname or "",
    )


def collect(*, source: str) -> ImportRegion | None:
    """Identify a top-level module import region safe to isolate.

    Args:
        source: Complete Python module text.

    Returns:
        Header import data, or None for interleaved executable code.

    """
    try:
        tree: Module = parse(source=source)
    except SyntaxError:
        return None
    nodes: list[stmt] = list(tree.body)
    imports: list[Import | ImportFrom] = []
    started: bool = False
    ended: bool = False
    for index, node in enumerate(iterable=nodes):
        if (
            index == 0
            and isinstance(node, Expr)
            and isinstance(node.value, Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        if isinstance(node, (Import, ImportFrom)):
            if ended:
                return None
            imports.append(node)
            started = True
        elif started:
            ended = True
    if not imports:
        return None
    lines: list[str] = source.splitlines(keepends=True)
    first: int = imports[0].lineno - 1
    last: int = imports[-1].end_lineno or imports[-1].lineno
    start: int = sum(map(len, lines[:first]))
    end: int = sum(map(len, lines[:last]))
    bindings: list[tuple[_Binding, str]] = []
    for node in imports:
        for alias in node.names:
            key: _Binding = _binding(node=node, alias=alias)
            raw: str = (
                f"import {alias.name}"
                if isinstance(node, Import)
                else (
                    f"from "
                    f"{'.' * node.level}"
                    f"{node.module or ''}"
                    f" import "
                    f"{alias.name}"
                )
            ) + (f" as {alias.asname}" if alias.asname else "")
            bindings.append((key, raw))
    return ImportRegion(
        start=start,
        end=end,
        text=source[start:end],
        bindings=frozenset(key for key, _raw in bindings),
        aliases=tuple(bindings),
    )


def reconcile(
    *,
    original: ImportRegion,
    user: ImportRegion,
    tool: ImportRegion,
) -> tuple[str | None, tuple[MergeConflict, ...]]:
    """Apply user import additions atop the tool's reorganized import header.

    Args:
        original: Original import header.
        user: User import header.
        tool: Tool import header.

    Returns:
        Complete merged header and unresolved import conflicts.

    """
    old_comments: tuple[str, ...] = tuple(
        token.string
        for token in generate_tokens(
            readline=StringIO(initial_value=original.text).readline,
        )
        if token.type == COMMENT
    )
    user_comments: tuple[str, ...] = tuple(
        token.string
        for token in generate_tokens(
            readline=StringIO(initial_value=user.text).readline,
        )
        if token.type == COMMENT
    )
    if user_comments != old_comments:
        return None, (
            MergeConflict(
                kind="unsupported_transformation",
                scope="imports",
                detail=(
                    "User changed import-region comments; regrouping cannot "
                    "safely attach them"
                ),
            ),
        )
    removed: frozenset[_Binding] = original.bindings - user.bindings
    additions: frozenset[_Binding] = user.bindings - original.bindings
    if removed & tool.bindings:
        return None, (
            MergeConflict(
                kind="concurrent_change",
                scope="imports",
                detail=(
                    "User removed imports that the tool retained; dependency "
                    "references require validation"
                ),
            ),
        )
    added: list[str] = []
    for name, source in user.aliases:
        if name in additions and name not in tool.bindings:
            added.append(source)
    if not added:
        return tool.text, ()
    future: list[str] = [
        line for line in added if line.startswith("from __future__ import ")
    ]
    ordinary: list[str] = [line for line in added if line not in future]
    lines: str = tool.text.rstrip("""\
\r
""")
    if future:
        # A new future import must follow any module docstring and precede all
        # ordinary imports. Avoid altering already valid future-header
        # ordering.
        lines = (
            """\

""".join(future)
            + """\

"""
            + lines
        )
    if ordinary:
        lines += """\

""" + """\

""".join(ordinary)
    return (
        lines
        + """\

""",
        (),
    )


def hide(*, source: str, region: ImportRegion) -> str:
    """Replace the entire import region with an ancestor-stable marker.

    Args:
        source: Source snapshot.
        region: Contiguous import header.

    Returns:
        Source with unmatched import grouping removed from textual diff3.

    """
    marker: Replacement = Replacement(
        start=region.start,
        end=region.end,
        text="""\
# MERGEKIT_IMPORT_BLOCK
""",
        scope="imports",
    )
    return source[: marker.start] + marker.text + source[marker.end :]
