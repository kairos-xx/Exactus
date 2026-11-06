"""Parse JavaScript, TypeScript, CSS and HTML with precise source locations."""

from __future__ import annotations

from html.parser import HTMLParser
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import TypedDict, cast, final

from exactus.packages.source_merger.model import (
    Language,
    Snapshot,
    Statement,
    Unit,
)


class _StatementData(TypedDict):
    """Wire representation of a parsed source statement.

    Attributes:
        kind: AST node type name.
        start: Start byte offset.
        end: End byte offset.
        shape: Normalized structural fingerprint.
        exact: Exact source text.
        binding: Bound identifier, when applicable.
        annotation: Type annotation text, when present.

    """

    kind: str
    start: int
    end: int
    shape: str
    exact: str
    binding: str
    annotation: str


class _UnitData(TypedDict):
    """Wire representation of a parsed language declaration.

    Attributes:
        kind: Declaration type name.
        name: Declared identifier.
        parent: Lexical parent path.
        start: Start byte offset.
        end: End byte offset.
        body_start: Body start offset.
        body_end: Body end offset.
        statements: Contained statements.
        fingerprint: Body shape hash.
        signature: Parameter signature.
        param_names: Declared parameter names.
        implicit_return: Whether the declaration returns implicitly.
        header_semantic: Normalized header form.

    """

    kind: str
    name: str
    parent: str
    start: int
    end: int
    body_start: int
    body_end: int
    statements: list[_StatementData]
    fingerprint: str
    signature: str
    param_names: list[str]
    implicit_return: bool
    header_semantic: str


class _ParserResponse(TypedDict):
    """Result of a read-only external language parser.

    Attributes:
        valid: Whether parsing succeeded.
        error: Parse error detail.
        units: Top-level declarations.
        statements: Top-level statements.

    """

    valid: bool
    error: str
    units: list[_UnitData]
    statements: list[_StatementData]


def _opt_int(*, value: str | float | bool | None) -> int | None:
    """Return value when it is an integer.

    Args:
        value: Candidate integer from decoded JSON.

    Returns:
        The integer, or None.

    """
    return value if isinstance(value, int) else None


@final
class NodeParser:
    """Invoke TypeScript and PostCSS AST parsers without.

    Invoke TypeScript and PostCSS AST parsers without executing user code.
    """

    @staticmethod
    def rewrite_identifiers(
        *,
        source: str,
        language: Language,
        mapping: dict[str, str],
    ) -> str:
        """Rename only JavaScript identifier references via the AST.

        Args:
            source: New or changed JS statement, not executed by the parser.
            language: JavaScript or TypeScript grammar.
            mapping: Confirmed renames from source bindings to tool bindings.

        Returns:
            Statement retaining strings, comments, properties and regexes.

        Raises:
            ValueError: Syntax, parser or scope ambiguity prevents safe
                projection.

        """
        try:
            process: CompletedProcess[bytes] = run(
                args=[
                    "node",
                    str(
                        object=Path(__file__).with_name(
                            name="parse_node.cjs",
                        ),
                    ),
                ],
                input=dumps(
                    obj={
                        "source": source,
                        "language": language,
                        "action": "rewrite_identifiers",
                        "mapping": mapping,
                    },
                ).encode(encoding="utf-8"),
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, TimeoutExpired) as error:
            msg: str = f"JavaScript scope parser unavailable: {error}"
            raise ValueError(msg) from error
        if process.returncode != 0:
            msg = process.stderr.decode(encoding="utf-8", errors="replace")
            raise ValueError(msg or "TypeScript AST parser failed")
        try:
            response: dict[str, str | bool] = loads(s=process.stdout)
        except (ValueError, TypeError) as error:
            msg = f"Invalid JavaScript rewrite response: {error}"
            raise ValueError(msg) from error
        if response.get("valid") is not True or not isinstance(
            response.get("text"),
            str,
        ):
            msg = str(
                object=response.get(
                    "error",
                    "JavaScript identifier binding is ambiguous",
                ),
            )
            raise ValueError(msg)
        return str(object=response["text"])

    def parse_many(
        self,
        *,
        sources: tuple[str, ...],
        language: Language,
    ) -> tuple[Snapshot, ...]:
        """Parse several JavaScript, TypeScript, or CSS sources.

        Args:
            sources: Sources from the same language.
            language: Grammar accepted by the Node parser.

        Returns:
            One syntax snapshot per input, preserving original ordering.

        Raises:
            ValueError: Parser count/protocol failures.

        """
        if not sources:
            return ()
        try:
            process: CompletedProcess[bytes] = run(
                args=[
                    "node",
                    str(
                        object=Path(__file__).with_name(
                            name="parse_node.cjs",
                        ),
                    ),
                ],
                input=dumps(
                    obj={
                        "batch": [
                            {"source": source, "language": language}
                            for source in sources
                        ],
                    },
                ).encode(encoding="utf-8"),
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, TimeoutExpired) as error:
            return tuple(
                Snapshot(
                    source=source,
                    units=(),
                    statements=(),
                    valid=False,
                    error=f"Node parser unavailable: {error}",
                )
                for source in sources
            )
        if process.returncode != 0:
            reason: str = process.stderr.decode(
                encoding="utf-8",
                errors="replace",
            )
            return tuple(
                Snapshot(
                    source=source,
                    units=(),
                    statements=(),
                    valid=False,
                    error=reason,
                )
                for source in sources
            )
        try:
            results: list[_ParserResponse] = loads(s=process.stdout)
        except JSONDecodeError as error:
            return tuple(
                Snapshot(
                    source=source,
                    units=(),
                    statements=(),
                    valid=False,
                    error=f"Invalid parser protocol: {error}",
                )
                for source in sources
            )
        if len(results) != len(sources):
            msg: str = (
                "Node parser returned an invalid number of batch responses"
            )
            raise ValueError(msg)
        try:
            return tuple(
                self._decode(source=source, data=item)
                for source, item in zip(sources, results, strict=True)
            )
        except (ValueError, TypeError) as error:
            return tuple(
                Snapshot(
                    source=source,
                    units=(),
                    statements=(),
                    valid=False,
                    error=f"Invalid parser protocol: {error}",
                )
                for source in sources
            )

    def parse(self, *, source: str, language: Language) -> Snapshot:
        """Parse one foreign-language source through the shared batch.

        Args:
            source: Complete source text.
            language: Source grammar.

        Returns:
            Parsed snapshot.

        """
        return self.parse_many(sources=(source,), language=language)[0]

    @staticmethod
    def _decode(*, source: str, data: _ParserResponse) -> Snapshot:
        """Convert one Node parser response into offset-backed syntax records.

        Args:
            source: Parsed source string.
            data: Node bridge's AST-derived metadata.

        Returns:
            Structured syntax snapshot, or a validation failure.

        """
        try:
            if not data["valid"]:
                return Snapshot(
                    source=source,
                    units=(),
                    statements=(),
                    valid=False,
                    error=data.get("error", "Parser rejected input"),
                )

            def stmt(*, item: _StatementData) -> Statement:
                """Convert one foreign-language syntax statement.

                Args:
                    item: Wire statement record.

                Returns:
                    Statement model.

                """
                return Statement(
                    kind=item["kind"],
                    start=item["start"],
                    end=item["end"],
                    shape=item["shape"],
                    exact=item["exact"],
                    binding=item.get("binding", ""),
                    value_start=_opt_int(
                        value=cast(
                            typ="str | float | bool | None",
                            val=item.get("value_start"),
                        ),
                    ),
                    value_end=_opt_int(
                        value=cast(
                            typ="str | float | bool | None",
                            val=item.get("value_end"),
                        ),
                    ),
                    annotation=item.get("annotation", ""),
                )

            return Snapshot(
                source=source,
                units=tuple(
                    Unit(
                        kind=item["kind"],
                        name=item["name"],
                        parent=item["parent"],
                        start=item["start"],
                        end=item["end"],
                        body_start=item["body_start"],
                        body_end=item["body_end"],
                        statements=tuple(
                            stmt(item=part) for part in item["statements"]
                        ),
                        fingerprint=item["fingerprint"],
                        signature=item["signature"],
                        param_names=tuple(item["param_names"]),
                        implicit_return=item.get("implicit_return") is True,
                        header_semantic=item.get("header_semantic", ""),
                    )
                    for item in data["units"]
                ),
                statements=tuple(
                    stmt(item=item) for item in data["statements"]
                ),
                valid=True,
            )
        except (KeyError, ValueError, TypeError) as error:
            return Snapshot(
                source=source,
                units=(),
                statements=(),
                valid=False,
                error=f"Invalid parser protocol: {error}",
            )


@final
class HtmlCollector(HTMLParser):
    """Collect HTML tag ranges without normalizing the original markup."""

    def __init__(self, *, source: str) -> None:
        """Initialize a syntax-preserving HTML tree collector.

        Args:
            source: Original HTML document text.

        """
        super().__init__(convert_charrefs=False)
        self.source: str = source
        self.offsets: list[int] = [0]
        for line in source.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.open_nodes: list[tuple[str, str, int, int, int]] = []
        self.units: list[Unit] = []
        self.failures: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Record a new element and its current nesting context.

        Args:
            tag: Parsed HTML tag name.
            attrs: Original HTML attributes.

        """
        opening: int = self._pos()
        start_end: int = opening + len(self.get_starttag_text() or "")
        attr_map: dict[str, str | None] = dict(attrs)
        name: str = attr_map.get("id") or attr_map.get("data-testid") or tag
        parent: str = self.open_nodes[-1][1] if self.open_nodes else ""
        if tag in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            if attr_map.get("id") or attr_map.get("data-testid"):
                self.units.append(
                    Unit(
                        kind="element",
                        name=name,
                        parent=parent,
                        start=opening,
                        end=start_end,
                        body_start=start_end,
                        body_end=start_end,
                        statements=(),
                        fingerprint="",
                        signature=tag,
                    ),
                )
            return
        self.open_nodes.append(
            (tag, name, opening, start_end, len(self.open_nodes)),
        )

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Record a void-style element without creating a spurious stack entry.

        Args:
            tag: Parsed tag name.
            attrs: Parsed attributes.

        """
        self.handle_starttag(tag=tag, attrs=attrs)
        _, name, start, end, _ = self.open_nodes.pop()
        if name != tag:
            self.units.append(
                Unit(
                    kind="element",
                    name=name,
                    parent="",
                    start=start,
                    end=end,
                    body_start=end,
                    body_end=end,
                    statements=(),
                    fingerprint="",
                    signature=tag,
                ),
            )

    def handle_endtag(self, tag: str) -> None:
        """Close the most recently opened matching element.

        Args:
            tag: Closing tag name.

        """
        if not self.open_nodes:
            self.failures.append(f"Unexpected closing tag {tag}")
            return
        start_tag, name, start, inner_start, _ = self.open_nodes.pop()
        if start_tag != tag:
            self.failures.append(f"Unbalanced tag {start_tag} closed as {tag}")
            return
        opening: int = self._pos()
        closing: int = self.source.find(">", opening) + 1
        if closing == 0:
            self.failures.append(f"Incomplete closing tag {tag}")
            return
        content: str = self.source[inner_start:opening]
        if name != tag:
            self.units.append(
                Unit(
                    kind="element",
                    name=name,
                    parent="",
                    start=start,
                    end=closing,
                    body_start=inner_start,
                    body_end=opening,
                    statements=(),
                    fingerprint=content.strip(),
                    signature=tag,
                ),
            )

    def _pos(self) -> int:
        """Return absolute position of the current HTML parser token.

        Returns:
            Byte offset into the original source.

        """
        line: int
        column: int
        line, column = self.getpos()
        return self.offsets[line - 1] + column


@final
class HtmlParser:
    """Parse matched, explicitly closed HTML elements without.

    Parse matched, explicitly closed HTML elements without rewriting markup.
    """

    @staticmethod
    def parse(*, source: str) -> Snapshot:
        """Extract HTML element ranges, rejecting malformed structural edits.

        Args:
            source: HTML document.

        Returns:
            HTML snapshot and explicit parser status.

        """
        collector: HtmlCollector = HtmlCollector(source=source)
        try:
            collector.feed(data=source)
            collector.close()
        except (ValueError, IndexError) as error:
            return Snapshot(
                source=source,
                units=(),
                statements=(),
                valid=False,
                error=f"HTML parsing failed: {error}",
            )
        if collector.open_nodes:
            collector.failures.append("Unclosed HTML elements")
        selected: list[Unit] = []
        for unit in sorted(
            collector.units,
            key=lambda item: (item.start, -item.end),
        ):
            if not any(
                existing.start <= unit.start and unit.end <= existing.end
                for existing in selected
            ):
                selected.append(unit)
        return Snapshot(
            source=source,
            units=tuple(selected),
            statements=(),
            valid=not collector.failures,
            error="; ".join(collector.failures),
        )
