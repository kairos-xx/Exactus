# Copyright (c) 2026
"""CSS expression trees, causal set minimization, and layout evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ValueNode:
    """One source-preserving CSS expression node.

    Attributes:
    kind: Stored kind value.
    text: Stored text value.
    start: Stored start value.
    end: Stored end value.
    children: Stored children value.

    """

    kind: str
    text: str
    start: int
    end: int
    children: tuple[ValueNode, ...] = ()

    def to_json(self) -> dict[str, str | int | list[dict[str, str | int]]]:
        """Return a shallow JSON-safe node representation.

        Returns:
        Result produced by to json.

        """
        return {
            "kind": self.kind,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "children": [
                {
                    "kind": child.kind,
                    "text": child.text,
                    "start": child.start,
                    "end": child.end,
                }
                for child in self.children
            ],
        }


class CssValueParser:
    """Parse nested CSS functions, arguments, operators, and literal spans."""

    _OPERATORS: Final[frozenset[str]] = frozenset({"+", "-", "*", "/"})

    @classmethod
    def parse(cls, value: str) -> ValueNode:
        """Return the expression tree preserving exact source offsets.

        Args:
        value: Value for value.

        Returns:
        Result produced by parse.

        """
        return ValueNode(
            kind="value",
            text=value,
            start=0,
            end=len(value),
            children=cls._children(value=value, start=0, end=len(value)),
        )

    @classmethod
    def walk(cls, node: ValueNode) -> tuple[ValueNode, ...]:
        """Return all descendants in depth-first order.

        Args:
        node: Value for node.

        Returns:
        Result produced by walk.

        """
        return (
            node,
            *(
                descendant
                for child in node.children
                for descendant in cls.walk(node=child)
            ),
        )

    @staticmethod
    def replace(value: str, node: ValueNode, replacement: str) -> str:
        """Replace exactly one source span.

        Args:
        value: Value for value.
        node: Value for node.
        replacement: Value for replacement.

        Returns:
        Result produced by replace.

        """
        return f"{value[: node.start]}{replacement}{value[node.end :]}"

    @classmethod
    def _children(
        cls,
        value: str,
        start: int,
        end: int,
    ) -> tuple[ValueNode, ...]:
        """Parse direct value children through the parser state machine.

        Args:
        value: Value for value.
        start: Value for start.
        end: Value for end.

        Returns:
        Result produced by  children.

        """
        return cls._children_impl(value=value, start=start, end=end)

    @classmethod
    def _children_impl(
        cls,
        value: str,
        start: int,
        end: int,
    ) -> tuple[ValueNode, ...]:
        """Split a CSS expression into source-aligned child nodes.

        Args:
        value: Value for value.
        start: Value for start.
        end: Value for end.

        Returns:
        Result produced by  children impl.

        """
        children: list[ValueNode] = []
        index: int = start
        while index < end:
            if value[index].isspace():
                index += 1
                continue
            if value.startswith("/*", index):
                index = cls._comment_end(value=value, index=index, end=end)
                continue
            if value[index] in {'"', "'"}:
                finish: int = cls._quoted_end(
                    value=value,
                    start=index,
                    end=end,
                )
                children.append(
                    ValueNode(
                        kind="string",
                        text=value[index:finish],
                        start=index,
                        end=finish,
                    ),
                )
                index = finish
                continue
            function: tuple[ValueNode, int] | None = cls._function_child(
                value=value,
                index=index,
                end=end,
            )
            if function is not None:
                node, index = function
                children.append(node)
                continue
            if value[index] in cls._OPERATORS and (
                value[index] != "-"
                or index == start
                or value[index - 1].isspace()
            ):
                children.append(
                    ValueNode(
                        kind="operator",
                        text=value[index],
                        start=index,
                        end=index + 1,
                    ),
                )
                index += 1
                continue
            literal: tuple[ValueNode, int] = cls._literal_child(
                value=value,
                index=index,
                end=end,
            )
            children.append(literal[0])
            index = literal[1]
        return tuple(children)

    @classmethod
    def _function_child(
        cls,
        value: str,
        index: int,
        end: int,
    ) -> tuple[ValueNode, int] | None:
        """Parse a function node starting at index when present.

        Args:
        value: Value for value.
        index: Value for index.
        end: Value for end.

        Returns:
            Function node plus next index, or None for non-functions.

        """
        if not (value[index].isalpha() or value[index] in "_-"):
            return None
        name_end: int = index + 1
        while name_end < end and (
            value[name_end].isalnum() or value[name_end] in "_-"
        ):
            name_end += 1
        if name_end >= end or value[name_end] != "(":
            return None
        close_index: int = cls._closing_paren(
            value=value,
            opening=name_end,
            end=end,
        )
        if close_index < 0:
            return None
        arguments: tuple[ValueNode, ...] = cls._arguments(
            value=value,
            start=name_end + 1,
            end=close_index,
        )
        return (
            ValueNode(
                kind=f"function:{value[index:name_end].lower()}",
                text=value[index : close_index + 1],
                start=index,
                end=close_index + 1,
                children=arguments,
            ),
            close_index + 1,
        )

    @classmethod
    def _literal_child(
        cls,
        value: str,
        index: int,
        end: int,
    ) -> tuple[ValueNode, int]:
        """Parse a literal span starting at index.

        Args:
        value: Value for value.
        index: Value for index.
        end: Value for end.

        Returns:
            Literal node plus next index.

        """
        finish: int = index + 1
        while (
            finish < end
            and (not value[finish].isspace())
            and (value[finish] not in ",()")
        ):
            if value[finish] in cls._OPERATORS and (
                value[finish] != "-" or value[finish - 1].isspace()
            ):
                break
            finish += 1
        return (
            ValueNode(
                kind="literal",
                text=value[index:finish],
                start=index,
                end=finish,
            ),
            finish,
        )

    @classmethod
    def _arguments(
        cls,
        value: str,
        start: int,
        end: int,
    ) -> tuple[ValueNode, ...]:
        """Split top-level function arguments while respecting nesting.

        Args:
        value: Value for value.
        start: Value for start.
        end: Value for end.

        Returns:
        Result produced by  arguments.

        """
        bounds: list[tuple[int, int]] = []
        depth: int = 0
        part_start: int = start
        index: int = start
        while index < end:
            char: str = value[index]
            if char in {'"', "'"}:
                index = cls._quoted_end(value=value, start=index, end=end)
                continue
            if value.startswith("/*", index):
                index = cls._comment_end(value=value, index=index, end=end)
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                bounds.append((part_start, index))
                part_start = index + 1
            index += 1
        bounds.append((part_start, end))
        return tuple(
            (
                ValueNode(
                    kind="argument",
                    text=value[left:right],
                    start=left,
                    end=right,
                    children=cls._children(value=value, start=left, end=right),
                )
                for left, right in bounds
            ),
        )

    @classmethod
    def _closing_paren(cls, value: str, opening: int, end: int) -> int:
        """Find a matching closing parenthesis outside strings/comments.

        Args:
        value: Value for value.
        opening: Value for opening.
        end: Value for end.

        Returns:
        Result produced by  closing paren.

        """
        depth: int = 0
        index: int = opening
        while index < end:
            if value[index] in {'"', "'"}:
                index = cls._quoted_end(value=value, start=index, end=end)
                continue
            if value.startswith("/*", index):
                index = cls._comment_end(value=value, index=index, end=end)
                continue
            if value[index] == "(":
                depth += 1
            elif value[index] == ")":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return -1

    @staticmethod
    def _comment_end(value: str, index: int, end: int) -> int:
        """Return the index after a CSS comment.

        Args:
        value: Value for value.
        index: Value for index.
        end: Value for end.

        Returns:
            Index following the comment terminator, or the end bound.

        """
        close: int = value.find("*/", index + 2, end)
        return end if close < 0 else close + 2

    @staticmethod
    def _quoted_end(value: str, start: int, end: int) -> int:
        """Find the end of an escaped CSS string.

        Args:
        value: Value for value.
        start: Value for start.
        end: Value for end.

        Returns:
        Result produced by  quoted end.

        """
        index: int = start + 1
        while index < end:
            if value[index] == "\\":
                index += 2
            elif value[index] == value[start]:
                return index + 1
            else:
                index += 1
        return end


@dataclass(frozen=True, slots=True)
class CauseSet:
    """One experimentally supported minimal sufficient intervention set.

    Attributes:
    members: Stored members value.
    improvement: Stored improvement value.
    confidence: Stored confidence value.
    evaluations: Stored evaluations value.
    minimal_within_budget: Stored minimal within budget value.

    """

    members: tuple[tuple[int, str], ...]
    improvement: float
    confidence: float
    evaluations: int
    minimal_within_budget: bool


class CausalMinimizer:
    """Find bounded minimal sufficient cause sets using group testing."""

    def __init__(
        self,
        evaluate: Callable[[tuple[tuple[int, str], ...]], float],
        budget: int = 64,
        threshold: float = 0.8,
    ) -> None:
        """Initialize a memoized counterfactual evaluator.

        Args:
        evaluate: Value for evaluate.
        budget: Value for budget.
        threshold: Value for threshold.

        """
        self.evaluate: Callable[[tuple[tuple[int, str], ...]], float] = (
            evaluate
        )
        self.budget: int = budget
        self.threshold: float = threshold
        self.cache: dict[tuple[tuple[int, str], ...], float] = {}

    def score(self, members: tuple[tuple[int, str], ...]) -> float | None:
        """Evaluate a canonical cause set, or None if budget exhausted.

        Args:
        members: Value for members.

        Returns:
        Result produced by score.

        """
        key: tuple[tuple[int, str], ...] = tuple(sorted(set(members)))
        if key in self.cache:
            return self.cache[key]
        if len(self.cache) >= self.budget:
            return None
        value: float = self.evaluate(key)
        self.cache[key] = value
        return value

    def minimize(
        self,
        candidates: tuple[tuple[int, str], ...],
    ) -> CauseSet | None:
        """Reduce a sufficient set via partitions then one-by-one removal.

        Args:
        candidates: Value for candidates.

        Returns:
        Result produced by minimize.

        """
        current: tuple[tuple[int, str], ...] = tuple(sorted(set(candidates)))
        if not current:
            return None
        full: float | None = self.score(members=current)
        if full is None or full < self.threshold:
            return None
        current = self._reduce_partitions(current=current)
        for member in tuple(current):
            remainder: tuple[tuple[int, str], ...] = tuple(
                item for item in current if item != member
            )
            if not remainder:
                continue
            score: float | None = self.score(members=remainder)
            if score is not None and score >= self.threshold:
                current = remainder
        final: float = self.cache[current]
        return CauseSet(
            members=current,
            improvement=final,
            confidence=min(1.0, final),
            evaluations=len(self.cache),
            minimal_within_budget=len(self.cache) < self.budget,
        )

    def _reduce_partitions(
        self,
        current: tuple[tuple[int, str], ...],
    ) -> tuple[tuple[int, str], ...]:
        """Shrink a sufficient set by testing chunk complements.

        Args:
            current: Current sufficient cause set.

        Returns:
            Reduced set that still meets the threshold.

        """
        granularity: int = 2
        while len(current) > 1:
            chunk_size: int = max(
                1,
                (len(current) + granularity - 1) // granularity,
            )
            reduced: bool = False
            for index in range(0, len(current), chunk_size):
                remainder: tuple[tuple[int, str], ...] = (
                    current[:index] + current[index + chunk_size :]
                )
                if not remainder:
                    continue
                score: float | None = self.score(members=remainder)
                if score is not None and score >= self.threshold:
                    current = remainder
                    granularity = max(2, granularity - 1)
                    reduced = True
                    break
            if reduced:
                continue
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)
        return current


class LayoutEvidence:
    """Infer grid/flex/container layout explanations from snapshots."""

    @staticmethod
    def compare(
        a: dict[str, str],
        b: dict[str, str],
    ) -> dict[str, dict[str, str]]:
        """Return changed layout properties and resolved track details.

        Args:
        a: Value for a.
        b: Value for b.

        Returns:
        Result produced by compare.

        """
        properties: tuple[str, ...] = (
            "display",
            "grid-template-columns",
            "grid-template-rows",
            "grid-auto-columns",
            "grid-auto-rows",
            "grid-auto-flow",
            "grid-column",
            "grid-row",
            "column-gap",
            "row-gap",
            "flex-direction",
            "flex-wrap",
            "flex-basis",
            "flex-grow",
            "flex-shrink",
            "justify-content",
            "align-items",
            "align-content",
            "min-width",
            "min-height",
            "max-width",
            "max-height",
            "width",
            "height",
            "container-type",
            "container-name",
            "contain",
            "content-visibility",
        )
        return {
            name: {"a": a.get(name, ""), "b": b.get(name, "")}
            for name in properties
            if a.get(name, "") != b.get(name, "")
        }


@dataclass(frozen=True, slots=True)
class CssTokenNode:
    """Lossless token/expression node inside a CSS value.

    Attributes:
    kind: Stored kind value.
    text: Stored text value.
    start: Stored start value.
    end: Stored end value.
    children: Stored children value.

    """

    kind: str
    text: str
    start: int
    end: int
    children: tuple[CssTokenNode, ...] = ()


class CssValueTokenizer:
    """Lossless tokenizer for counterfactual CSS value interventions."""

    @classmethod
    def parse(cls, value: str) -> tuple[CssTokenNode, ...]:
        """Tokenize literals, operators, functions, strings, and separators.

        Args:
        value: Value for value.

        Returns:
        Result produced by parse.

        """
        nodes: list[CssTokenNode] = []
        index: int = 0
        while index < len(value):
            node, index = cls._token_at(value=value, index=index)
            nodes.append(node)
        return tuple(nodes)

    @classmethod
    def flatten(
        cls,
        nodes: tuple[CssTokenNode, ...],
    ) -> tuple[CssTokenNode, ...]:
        """Flatten a value tree while retaining exact source spans.

        Args:
        nodes: Value for nodes.

        Returns:
        Result produced by flatten.

        """
        output: list[CssTokenNode] = []
        for node in nodes:
            output.append(node)
            output.extend(cls.flatten(nodes=node.children))
        return tuple(output)

    @classmethod
    def _token_at(cls, value: str, index: int) -> tuple[CssTokenNode, int]:
        """Dispatch one token scan based on the current character.

        Args:
        value: Value for value.
        index: Value for index.

        Returns:
            Scanned token plus next index.

        """
        char: str = value[index]
        if char.isspace():
            return cls._whitespace_token(value=value, index=index)
        if char in "+-*/ ,":
            return (
                CssTokenNode(
                    kind="operator",
                    text=char,
                    start=index,
                    end=index + 1,
                ),
                index + 1,
            )
        if char in "'\"":
            return cls._string_token(value=value, index=index)
        if char.isalpha() or char in "_-":
            return cls._ident_token(value=value, index=index)
        return cls._literal_token(value=value, index=index)

    @classmethod
    def _ident_token(cls, value: str, index: int) -> tuple[CssTokenNode, int]:
        """Scan an identifier or parenthesized function expression.

        Args:
        value: Value for value.
        index: Value for index.

        Returns:
            Ident/function token plus next index.

        """
        start: int = index
        index += 1
        while index < len(value) and (
            value[index].isalnum() or value[index] in "_-"
        ):
            index += 1
        if index < len(value) and value[index] == "(":
            depth: int = 1
            index += 1
            inner_start: int = index
            while index < len(value) and depth:
                if value[index] == "(":
                    depth += 1
                elif value[index] == ")":
                    depth -= 1
                index += 1
            inner_end: int = max(inner_start, index - 1)
            children: tuple[CssTokenNode, ...] = tuple(
                cls._shift(node=node, offset=inner_start)
                for node in CssValueTokenizer.parse(
                    value=value[inner_start:inner_end],
                )
            )
            return (
                CssTokenNode(
                    kind="function",
                    text=value[start:index],
                    start=start,
                    end=index,
                    children=children,
                ),
                index,
            )
        return (
            CssTokenNode(
                kind="ident",
                text=value[start:index],
                start=start,
                end=index,
            ),
            index,
        )

    @classmethod
    def _shift(cls, node: CssTokenNode, offset: int) -> CssTokenNode:
        """Shift a recursively parsed node into original source coordinates.

        Args:
        node: Value for node.
        offset: Value for offset.

        Returns:
        Result produced by  shift.

        """
        return CssTokenNode(
            kind=node.kind,
            text=node.text,
            start=node.start + offset,
            end=node.end + offset,
            children=tuple(
                cls._shift(node=child, offset=offset)
                for child in node.children
            ),
        )

    @staticmethod
    def _whitespace_token(value: str, index: int) -> tuple[CssTokenNode, int]:
        """Scan one whitespace run.

        Args:
        value: Value for value.
        index: Value for index.

        Returns:
            Whitespace token plus next index.

        """
        start: int = index
        index += 1
        while index < len(value) and value[index].isspace():
            index += 1
        return (
            CssTokenNode(
                kind="whitespace",
                text=value[start:index],
                start=start,
                end=index,
            ),
            index,
        )

    @staticmethod
    def _string_token(value: str, index: int) -> tuple[CssTokenNode, int]:
        """Scan one quoted string including escapes.

        Args:
        value: Value for value.
        index: Value for index.

        Returns:
            String token plus next index.

        """
        start: int = index
        quote: str = value[index]
        index += 1
        escaped: bool = False
        while index < len(value):
            current: str = value[index]
            index += 1
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == quote:
                break
        return (
            CssTokenNode(
                kind="string",
                text=value[start:index],
                start=start,
                end=index,
            ),
            index,
        )

    @staticmethod
    def _literal_token(value: str, index: int) -> tuple[CssTokenNode, int]:
        """Scan one non-delimiter literal run.

        Args:
        value: Value for value.
        index: Value for index.

        Returns:
            Literal token plus next index.

        """
        start: int = index
        index += 1
        while (
            index < len(value)
            and (not value[index].isspace())
            and (value[index] not in "+-*/,()")
        ):
            index += 1
        return (
            CssTokenNode(
                kind="literal",
                text=value[start:index],
                start=start,
                end=index,
            ),
            index,
        )
