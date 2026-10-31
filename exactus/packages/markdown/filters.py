# Copyright (c) 2026
"""Markdown formatting filters for Jinja2 templates."""

from __future__ import annotations

from json import dumps
from re import MULTILINE, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final

from .paths import PathResolver

if TYPE_CHECKING:
    from jinja2 import Environment

    from .json_types import JsonValue


class Constants:
    """Filter constants.

    Attributes:
        escape: Characters that are special in Markdown.
        newline: Line break variants collapsed inside table cells.
        fence_marker: Opening fence runs that diagnostic text may contain.

    """

    escape: Final[Pattern[str]] = compile_pattern(
        pattern=r"([\\`*_{}\[\]<>#+.!|])",
    )
    newline: Final[Pattern[str]] = compile_pattern(pattern=r"\r\n|\r|\n")
    fence_marker: Final[Pattern[str]] = compile_pattern(
        pattern=r"^[ \t]*(?P<marker>~{3,}|`{3,})",
        flags=MULTILINE,
    )


class MarkdownFilters:
    """Filters exposed to templates.

    Jinja2 calls filters with positional arguments, so these methods are
    the one place the keyword-only convention does not apply.
    """

    @classmethod
    def escape(cls, value: JsonValue) -> str:
        """Backslash-escape Markdown control characters.

        Args:
            value: Value to escape.

        Returns:
            The escaped text.

        """
        return Constants.escape.sub(repl=r"\\\1", string=cls.text(value=value))

    @classmethod
    def cell(cls, value: JsonValue) -> str:
        """Escape a value for one single-line table cell.

        Args:
            value: Value to place in a cell.

        Returns:
            Text with ``|`` escaped and line breaks turned into ``<br>``.

        """
        return Constants.newline.sub(
            repl="<br>",
            string=cls.text(value=value).replace("|", "\\|"),
        )

    @classmethod
    def code(cls, value: JsonValue) -> str:
        """Wrap a value in an inline code span.

        Args:
            value: Value to wrap.

        Returns:
            The code span.

        """
        return f"`{cls.text(value=value)}`"

    @classmethod
    def codeblock(cls, value: JsonValue, language: str = "") -> str:
        """Wrap a value in a fenced code block.

        Args:
            value: Value to wrap.
            language: Info string after the opening fence.

        Returns:
            The fenced block.

        """
        return f"```{language}\n{cls.text(value=value)}\n```"

    @classmethod
    def fence(cls, value: JsonValue, language: str = "") -> str:
        """Wrap a value in a fence longer than any marker inside it.

        A fixed ``~~~~`` fence breaks when the text itself starts a line
        with ``~~~~`` or a backtick run; the fence here is one character
        longer than the longest marker found in the value, so content can
        never close it.

        Args:
            value: Value to fence.
            language: Info string after the opening fence.

        Returns:
            The fenced block.

        """
        text: str = cls.text(value=value)
        longest: int = max(
            (
                len(found["marker"])
                for found in Constants.fence_marker.finditer(string=text)
            ),
            default=3,
        )
        marker: str = "~" * (longest + 1)
        return f"{marker}{language}\n{text}\n{marker}"

    @classmethod
    def bullets(cls, value: JsonValue, path: str | None = None) -> str:
        """Render a bullet list.

        Args:
            value: List or scalar.
            path: Optional field of each item to print.

        Returns:
            One ``- item`` line per item.

        """
        return "\n".join(
            f"- {cls.text(value=cls._field(value=item, path=path))}"
            for item in cls._items(value=value)
        )

    @classmethod
    def numbered(cls, value: JsonValue, path: str | None = None) -> str:
        """Render a numbered list.

        Args:
            value: List or scalar.
            path: Optional field of each item to print.

        Returns:
            One ``n. item`` line per item.

        """
        return "\n".join(
            f"{index}. {cls.text(value=cls._field(value=item, path=path))}"
            for index, item in enumerate(
                iterable=cls._items(value=value),
                start=1,
            )
        )

    @classmethod
    def table(cls, value: JsonValue, *columns: str) -> str:
        """Render a Markdown table (Jinja2 positional entry point).

        Args:
            value: List of rows.
            *columns: ``"Header:path"`` or ``"path"`` column specs.

        Returns:
            The table, or an empty string for an empty or non-list value.

        """
        return cls.render_table(value=value, columns=columns)

    @classmethod
    def render_table(
        cls,
        *,
        value: JsonValue,
        columns: tuple[str, ...],
    ) -> str:
        """Render a Markdown table.

        Args:
            value: List of rows.
            columns: ``"Header:path"`` or ``"path"`` column specs.

        Returns:
            The table, or an empty string for an empty or non-list value.

        """
        if not isinstance(value, list) or not value:
            return ""
        specs: list[tuple[str, str]] = cls._columns(
            columns=columns,
            first=value[0],
        )
        lines: list[str] = [
            "| "
            + " | ".join(cls.cell(value=head) for head, _ in specs)
            + " |",
            "| " + " | ".join("---" for _ in specs) + " |",
        ]
        lines.extend(
            "| "
            + " | ".join(cls._cell(row=row, path=path) for _, path in specs)
            + " |"
            for row in value
        )
        return "\n".join(lines)

    @classmethod
    def register(cls, *, env: Environment) -> None:
        """Install every filter on a Jinja2 environment.

        Args:
            env: Environment to extend.

        """
        env.filters.update(
            {
                "md_escape": cls.escape,
                "md_cell": cls.cell,
                "md_code": cls.code,
                "md_codeblock": cls.codeblock,
                "md_fence": cls.fence,
                "md_bullets": cls.bullets,
                "md_numbered": cls.numbered,
                "md_table": cls.table,
                "json": cls.to_json,
                "compact_json": cls.compact_json,
            },
        )

    @staticmethod
    def text(value: JsonValue) -> str:
        """Stringify a value for inclusion in Markdown.

        Args:
            value: Any JSON value.

        Returns:
            Empty text for ``None``, compact JSON for containers, else
            ``str(value)``.

        """
        if value is None:
            return ""
        if isinstance(value, list | dict):
            return dumps(obj=value, ensure_ascii=False)
        return str(object=value)

    @staticmethod
    def to_json(value: JsonValue, indent: int = 2) -> str:
        """Serialize to indented JSON.

        Args:
            value: Value to serialize.
            indent: Indentation width.

        Returns:
            The JSON text.

        """
        return dumps(obj=value, ensure_ascii=False, indent=indent)

    @staticmethod
    def compact_json(value: JsonValue) -> str:
        """Serialize to compact JSON.

        Args:
            value: Value to serialize.

        Returns:
            The JSON text without extra whitespace.

        """
        return dumps(obj=value, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def _cell(cls, row: JsonValue, path: str) -> str:
        """Render one table cell.

        Args:
            row: Table row.
            path: Path of the cell inside the row.

        Returns:
            Escaped single-line cell text.

        """
        value: JsonValue = cls._field(value=row, path=path)
        text: str = cls.text(value=value)
        return cls.cell(value=cls.code(value=text) if "__" in text else text)

    @staticmethod
    def _items(value: JsonValue) -> list[JsonValue]:
        """Treat a scalar as a one-item list.

        Args:
            value: List or scalar.

        Returns:
            The list.

        """
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _field(value: JsonValue, path: str | None) -> JsonValue:
        """Select a field of an item.

        Args:
            value: Item.
            path: Path inside the item, or ``None`` for the item.

        Returns:
            The selected value.

        """
        if path is None:
            return value
        return PathResolver.resolve(current=value, path=path, root=value).value

    @staticmethod
    def _columns(
        *,
        columns: tuple[str, ...],
        first: JsonValue,
    ) -> list[tuple[str, str]]:
        """Resolve ``(header, path)`` pairs.

        Args:
            columns: ``"Header:path"`` or ``"path"`` strings.
            first: First table row, used when no columns are given.

        Returns:
            Header and path for each column.

        """
        if columns:
            pairs: list[tuple[str, str]] = []
            for column in columns:
                head, separator, path = column.partition(":")
                pairs.append((head, path if separator else column))
            return pairs
        if isinstance(first, dict):
            return [(key, key) for key in first]
        return [("value", ".")]
