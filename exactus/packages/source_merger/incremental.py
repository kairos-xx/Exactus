"""Safely reparse an isolated Python function without rescanning its module."""

from __future__ import annotations

from dataclasses import replace
from typing import final

from exactus.packages.source_merger.model import Snapshot, Statement, Unit
from exactus.packages.source_merger.python_parser import PythonParser


@final
class IncrementalPythonParser:
    """Attempt structural reuse only when edit isolation can be demonstrated.

    Every ambiguous edit falls back to the full language parser. This avoids
    retaining stale offsets when declarations are moved, renamed or extracted.
    """

    @classmethod
    def reparse(cls, *, previous: Snapshot, source: str) -> Snapshot | None:
        """Incrementally update an isolated top-level Python function.

        Args:
            previous: Successfully parsed predecessor in the same editor fork.
            source: Current complete module text.

        Returns:
            Updated immutable snapshot, or None when safe isolation fails.

        """
        old: str = previous.source
        if not previous.valid or old == source:
            return None
        prefix: int = 0
        common: int = min(len(old), len(source))
        while prefix < common and old[prefix] == source[prefix]:
            prefix += 1
        suffix: int = 0
        while (
            suffix < common - prefix
            and old[len(old) - suffix - 1] == source[len(source) - suffix - 1]
        ):
            suffix += 1
        ending: int = len(old) - suffix
        changed: tuple[Unit, ...] = tuple(
            unit
            for unit in previous.units
            if unit.kind in {"function", "async_function"}
            and not unit.parent
            and unit.body_start <= prefix
            and ending <= unit.body_end
        )
        if len(changed) != 1:
            return None
        ancestor: Unit = changed[0]
        if any(
            unit is not ancestor
            and ancestor.start <= unit.start < ancestor.end
            for unit in previous.units
        ):
            return None
        delta: int = len(source) - len(old)
        ending_new: int = ancestor.end + delta
        if ending_new < ancestor.body_start or ending_new > len(source):
            return None
        fragment: str = source[ancestor.start : ending_new]
        parsed: Snapshot = PythonParser().parse(source=fragment)
        if (
            not parsed.valid
            or len(parsed.units) != 1
            or parsed.units[0].kind != ancestor.kind
            or parsed.units[0].name != ancestor.name
            or parsed.units[0].parent
            or parsed.units[0].end != len(fragment)
        ):
            return None
        new_unit: Unit = cls._shift_unit(
            item=parsed.units[0],
            offset=ancestor.start,
        )
        updated_units: tuple[Unit, ...] = tuple(
            new_unit
            if unit is ancestor
            else cls._shift_unit(item=unit, offset=delta)
            if unit.start >= ancestor.end
            else unit
            for unit in previous.units
        )
        statements: tuple[Statement, ...] = tuple(
            cls._shift_statement(item=item, offset=delta)
            if item.start >= ancestor.end
            else item
            for item in previous.statements
            if not (ancestor.start <= item.start < ancestor.end)
        )
        fragments: tuple[Statement, ...] = tuple(
            cls._shift_statement(
                item=item,
                offset=ancestor.start,
            )
            for item in parsed.statements
        )
        return Snapshot(
            source=source,
            units=updated_units,
            statements=tuple(
                sorted((*statements, *fragments), key=lambda item: item.start),
            ),
            valid=True,
        )

    @classmethod
    def _shift_unit(cls, *, item: Unit, offset: int) -> Unit:
        """Translate a declaration's span and owned statements.

        Args:
            item: Unit to translate.
            offset: Signed byte delta.

        Returns:
            Shifted unit copy.

        """
        return replace(
            item,
            start=item.start + offset,
            end=item.end + offset,
            body_start=item.body_start + offset,
            body_end=item.body_end + offset,
            statements=tuple(
                cls._shift_statement(
                    item=part,
                    offset=offset,
                )
                for part in item.statements
            ),
        )

    @staticmethod
    def _shift_statement(*, item: Statement, offset: int) -> Statement:
        """Translate a statement and its optional RHS offsets.

        Args:
            item: Statement to translate.
            offset: Signed byte delta.

        Returns:
            Shifted statement copy.

        """
        return replace(
            item,
            start=item.start + offset,
            end=item.end + offset,
            value_start=item.value_start + offset
            if item.value_start is not None
            else None,
            value_end=item.value_end + offset
            if item.value_end is not None
            else None,
        )
