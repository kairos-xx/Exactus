# Copyright (c) 2026
"""Rename a project: its root directory, its files, and its name in text.

The script plans every change first, shows it, and only then applies it as
one transaction that is rolled back if anything fails. The root directory is
renamed last, so a failed run never leaves the project half-moved.

The repository root is resolved in order: the optional ``root`` argument,
the nearest ancestor of the working directory holding a ``.git`` or
``pyproject.toml`` marker, then the same upward search from the script's own
directory. The root directory is renamed to ``--name`` (default ``exactus``).

Old names
    The root directory name and ``[project] name`` from ``pyproject.toml``
    are detected automatically; ``--from NAME`` (alias ``--alias``) adds
    more. Each occurrence keeps the casing convention it was written in;
    renaming ``abc_cde`` to ``foo_bar`` produces:

    =================== =========================== ==================
    Old spelling        Convention                  New spelling
    =================== =========================== ==================
    ``abc_cde``         snake_case identifiers      ``foo_bar``
    ``ABC_CDE``         screaming constants         ``FOO_BAR``
    ``abc-cde``         kebab-case packaging names  ``foo-bar``
    ``AbcCde``          PascalCase class names      ``FooBar``
    ``abcCde``          camelCase variables         ``fooBar``
    ``Abc Cde``         Title Case headings         ``Foo Bar``
    ``ABC CDE``         uppercase prose             ``FOO BAR``
    ``abc cde``         lowercase prose             ``foo bar``
    ``abccde``          flat compound names         ``foobar``
    ``abc.cde``         safe dotted names           ``foo.bar``
    =================== =========================== ==================

Restyling
    When a spelling is ambiguous (a single-word old name reads the same in
    snake, kebab, and Title case) the file kind decides: code prefers
    ``snake_case``/``PascalCase``, prose prefers lowercase and Title Case,
    and data files prefer ``kebab-case``. Context rules refine this:

    - heading lines in ``.md``/``.markdown`` files render Title Case;
    - ``name =`` lines in ``.toml`` render ``kebab-case``;
    - inline code keeps the written style;
    - matches touching ``/`` or ``.`` keep it, so paths and module
      references stay filename-accurate.

Safety
    - Files come from ``git ls-files`` (tracked plus untracked, honoring
      ``.gitignore``) inside a repository, else from a walk that prunes VCS
      data, virtual environments, caches, and build output.
    - Line endings, BOMs, file modes, and symlinks are preserved; binary,
      non-UTF-8, oversized, and shebang content is never rewritten and is
      reported when it mentions the old name.
    - Absolute paths inside the project become relative; other existing
      absolute paths are left untouched and shielded from restyling.
    - Files and directories whose names carry the old name are renamed in
      the matching style, deepest first, and collisions are detected before
      anything changes.
    - ``--dry-run`` reports without touching anything; without ``--yes`` a
      terminal confirmation is required.
"""

from __future__ import annotations

from ast import Constant, JoinedStr, Module, parse
from ast import walk as ast_walk
from contextlib import closing
from csv import Error as CsvError
from csv import reader as csv_reader
from dataclasses import dataclass, field
from difflib import unified_diff
from fnmatch import fnmatch
from io import StringIO
from keyword import iskeyword
from os import walk
from pathlib import Path
from re import IGNORECASE, Match, Pattern, escape, findall, split
from re import compile as compile_pattern
from shutil import copymode
from subprocess import CalledProcessError, CompletedProcess, run
from sys import stderr, stdin, stdout
from tempfile import NamedTemporaryFile
from textwrap import dedent
from tokenize import COMMENT, TokenError, generate_tokens
from tomllib import TOMLDecodeError, loads
from typing import TYPE_CHECKING, Final, cast
from typing import final as _group_final_final

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring as xml_fromstring
from tree_sitter_language_pack import get_parser

from cli_help import paint, pretty_parser
from exactus.packages.model.sqlite_model import (
    Connection,
    Cursor,
    DatabaseError,
    Identifier,
    InExpression,
    Literal,
    Param,
    PredicateNode,
    RawSql,
    Row,
    SelectableNode,
    SQLiteLayerError,
    Table,
    alter_rename_column,
    alter_rename_table,
    command,
    complete_statement,
    connect,
    drop,
    pragma,
)
from exactus.packages.model.sqlite_model import execute as execute_sql

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Iterable, Sequence

    from tree_sitter import Node, Parser
type Cell = str | int | float | bytes | None


@_group_final_final
class Constants:
    """Group module-level constants.

    Attributes:
        prose: Grouped module constant.
        data: Grouped module constant.
        doc_suffixes: Grouped module constant.
        min_attribute_parts: Grouped module constant.
        quoted_length: Grouped module constant.
        line_comment: Grouped module constant.
        code_suffixes: Grouped module constant.
        dotted_guard_suffixes: Grouped module constant.
        styles: Grouped module constant.
        preference: Grouped module constant.
        boundaries: Grouped module constant.
        path_token: Grouped module constant.
        name_line: Grouped module constant.
        max_leftovers: Grouped module constant.
        ask_attempts: Grouped module constant.
        github_url: Grouped module constant.
        short_limit: Grouped module constant.
        valid_name: Grouped module constant.
        web_attribute: Grouped module constant.
        css_symbol: Grouped module constant.
        js_id: Grouped module constant.
        js_selector: Grouped module constant.
        js_class: Grouped module constant.
        web_suffixes: Grouped module constant.
        default_name: Grouped module constant.
        default_max_size: Grouped module constant.
        pruned_dirs: Grouped module constant.
        module_suffixes: Grouped module constant.
        sqlite_suffixes: Grouped module constant.
        sqlite_header: Grouped module constant.

    """

    prose: Final[frozenset[str]] = frozenset(
        (".md", ".markdown", ".rst", ".txt", ".adoc"),
    )
    data: Final[frozenset[str]] = frozenset(
        (".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".csv", ".xml"),
    )
    doc_suffixes: Final[frozenset[str]] = frozenset((".md", ".markdown"))
    min_attribute_parts: Final[int] = 2
    quoted_length: Final[int] = 2
    line_comment: Final[Pattern[str]] = compile_pattern(
        pattern="(?:^|(?<=\\s))(?:#|//)",
    )
    code_suffixes: Final[frozenset[str]] = frozenset(
        (
            ".c",
            ".cc",
            ".cpp",
            ".cs",
            ".css",
            ".go",
            ".h",
            ".hpp",
            ".html",
            ".java",
            ".js",
            ".jsx",
            ".mjs",
            ".php",
            ".py",
            ".pyi",
            ".rb",
            ".rs",
            ".sh",
            ".sql",
            ".swift",
            ".ts",
            ".tsx",
            ".vue",
            ".xml",
        ),
    )
    dotted_guard_suffixes: Final[frozenset[str]] = code_suffixes | frozenset(
        (".md", ".markdown"),
    )
    styles: Final[tuple[str, ...]] = (
        "snake",
        "screaming",
        "kebab",
        "dot",
        "flat",
        "lower",
        "upper",
        "title",
        "camel",
        "pascal",
    )
    preference: Final[dict[str, tuple[str, ...]]] = {
        "code": (
            "snake",
            "pascal",
            "screaming",
            "camel",
            "kebab",
            "flat",
            "dot",
            "lower",
            "upper",
            "title",
        ),
        "prose": (
            "lower",
            "title",
            "upper",
            "snake",
            "pascal",
            "screaming",
            "kebab",
            "flat",
            "dot",
            "camel",
        ),
        "data": (
            "kebab",
            "snake",
            "screaming",
            "flat",
            "dot",
            "lower",
            "upper",
            "title",
            "camel",
            "pascal",
        ),
    }
    boundaries: Final[dict[str, tuple[str, str]]] = {
        "word": ("(?<!\\w)", "(?!\\w)"),
        "loose": ("(?<![A-Za-z0-9])", "(?![A-Za-z0-9])"),
    }
    path_token: Final[Pattern[str]] = compile_pattern(
        pattern="(?<![\\w/])/(?!/)(?:[\\w.@%+=~,:-]+/)*[\\w.@%+=~,:-]+",
    )
    name_line: Final[Pattern[str]] = compile_pattern(pattern="\\s*name\\s*=")
    max_leftovers: Final[int] = 3
    ask_attempts: Final[int] = 3
    github_url: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "(?P<head>(?:https?://|ssh://git@|git@)github\\.com[:/])(?P<owner>"
            "[^/]+)/(?P<repo>[^/]+?)(?P<tail>\\.git)?/?"
        ),
    )
    short_limit: Final[int] = 3
    valid_name: Final[Pattern[str]] = compile_pattern(
        pattern="[A-Za-z][\\w.\\- ]*",
    )
    web_attribute: Final[Pattern[str]] = compile_pattern(
        pattern="\\b(?P<name>id|class)\\s*=\\s*(?P<q>['\\\"])(?P<value>.*?)(?P=q)",
        flags=IGNORECASE,
    )
    css_symbol: Final[Pattern[str]] = compile_pattern(
        pattern="(?<![\\w-])(?P<prefix>[.#])(?P<name>[A-Za-z_][\\w-]*)",
    )
    js_id: Final[Pattern[str]] = compile_pattern(
        pattern="\\bgetElementById\\s*\\(\\s*(['\\\"])(?P<name>[^'\\\"]+)\\1",
    )
    js_selector: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "\\b(?:querySelector(?:All)?|matches|closest)\\s*\\(\\s*(['\\\"])("
            "?P<selector>[^'\\\"]+)\\1"
        ),
    )
    js_class: Final[Pattern[str]] = compile_pattern(
        pattern=(
            "\\.classList\\.(?:add|remove|toggle|contains|replace)\\s*\\(\\s*("
            "['\\\"])(?P<name>[^'\\\"]+)\\1"
        ),
    )
    web_suffixes: Final[frozenset[str]] = frozenset(
        (".html", ".css", ".js", ".mjs"),
    )
    default_name: Final[str] = "exactus"
    default_max_size: Final[int] = 5 * 1024 * 1024
    pruned_dirs: Final[frozenset[str]] = frozenset(
        (
            ".git",
            ".hg",
            ".svn",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".tox",
            ".nox",
            ".mypy_cache",
            ".ruff_cache",
            ".pytest_cache",
            ".history",
            "dist",
            "build",
        ),
    )
    module_suffixes: Final[tuple[str, ...]] = (
        ".py",
        ".pyi",
        ".js",
        ".mjs",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".go",
        ".rs",
    )
    sqlite_suffixes: Final[frozenset[str]] = frozenset(
        (".db", ".db3", ".sqlite", ".sqlite3"),
    )
    sqlite_header: Final[bytes] = b"SQLite format 3\x00"


def _paint(*, code: str, text: str) -> str:
    """Style text with an SGR code such as ``1;36`` when on a terminal.

    Args:
        code: SGR parameters without the escape sequence.
        text: Text to style.

    Returns:
        The styled text, or ``text`` unchanged without a terminal.

    """
    return paint(code=f"\x1b[{code}m", text=text)


class RenameError(Exception):
    """Report a problem that stops the rename before or during apply."""


@dataclass(frozen=True, slots=True)
class Options:
    """User-controlled behavior of one rename.

    Attributes:
        new_name: Target name in any casing; also the root directory name.
        old_names: Extra old spellings beyond the detected ones.
        boundary: ``word`` (default) or ``loose`` name boundaries.
        keep_absolute: Leave absolute project paths untouched.
        rename_root: Rename the root directory itself.
        use_git: Prefer ``git ls-files`` inside a repository.
        includes: Relative-path globs; when set only matches are touched.
        excludes: Relative-path globs that are never touched.
        max_size: Largest file, in bytes, that is rewritten.
        abbreviations: ``(old, new)`` exact, case-sensitive short forms.
        allow_short_lowercase: Permit lowercase abbreviations of up to
            three letters, which collide with ordinary words and suffixes.
        dotted: Also rename dotted spellings in non-code and proven-safe
            code regions. Executable dotted references remain guarded.
        dotted_code: Permit dotted replacement in executable code. This is a
            deliberately separate high-risk override.
        github: ``True`` renames the GitHub repository behind the remote,
            ``False`` never does, ``None`` asks when one is discovered.
        remote: Git remote that points at that repository.
        sqlite: Sqlite.
        sqlite_schema: Sqlite schema.

    """

    new_name: str
    old_names: tuple[str, ...] = ()
    boundary: str = "word"
    keep_absolute: bool = False
    rename_root: bool = True
    use_git: bool = True
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    max_size: int = Constants.default_max_size
    abbreviations: tuple[tuple[str, str], ...] = ()
    allow_short_lowercase: bool = False
    dotted: bool = False
    dotted_code: bool = False
    sqlite: bool = True
    sqlite_schema: bool = False
    github: bool | None = None
    remote: str = "origin"


@dataclass(frozen=True, slots=True)
class RemoteRename:
    """A planned GitHub repository rename.

    Attributes:
        remote: Git remote whose URL is updated.
        owner: Repository owner or organization.
        old: Current repository name.
        new: Repository name after the rename.
        old_url: Remote URL before the rename.
        new_url: Remote URL after the rename.

    """

    remote: str
    owner: str
    old: str
    new: str
    old_url: str
    new_url: str


@dataclass(frozen=True, slots=True)
class RenameRules:
    """Everything needed to restyle the old name into the new one.

    Attributes:
        names: Pattern matching every old-name styling.
        styles: ``group name -> candidate styles`` from ``_name_matcher``;
            an abbreviation group holds ``("=" + replacement,)``.
        words: New-name words to render.

    """

    names: Pattern[str]
    styles: dict[str, tuple[str, ...]]
    words: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileEdit:
    """One planned content rewrite.

    Attributes:
        path: File to rewrite.
        before: Original bytes.
        after: Rewritten bytes.
        matches: Number of name and path substitutions.

    """

    path: Path
    before: bytes
    after: bytes
    matches: int


@dataclass(frozen=True, slots=True)
class SqliteSchemaEdit:
    """One SQLite table or column rename performed through ALTER TABLE.

    Attributes:
        database: Database.
        kind: Kind.
        new: New.
        old: Old.
        table: Table.

    """

    database: Path
    kind: str
    table: str
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class SqlApplicationReference:
    """One static application SQL reference to a renamed schema symbol.

    Attributes:
        kind: Kind.
        line: Line.
        path: Path.
        symbol: Symbol.

    """

    path: Path
    line: int
    symbol: str
    kind: str


@dataclass(frozen=True, slots=True)
class SqliteCellEdit:
    """One SQLite TEXT-cell update identified by a stable row locator.

    Attributes:
        after: After.
        before: Before.
        column: Column.
        database: Database.
        locator_columns: Locator columns.
        locator_values: Locator values.
        table: Table.

    """

    database: Path
    table: str
    column: str
    locator_columns: tuple[str, ...]
    locator_values: tuple[int | float | str | bytes | None, ...]
    before: str
    after: str


@dataclass(slots=True)
class Plan:
    """Every change a rename would make.

    Attributes:
        root: Project root before the rename.
        edits: Content rewrites.
        renames: ``(source, destination)`` pairs, deepest first.
        root_target: New root directory, when it changes.
        skipped: ``(path, reason)`` files that mention the name but were
            left alone.
        leftovers: ``(path, line number, text)`` mixed-case spellings the
            rewrite did not recognize, such as ``Abc_Cde``.
        remote: GitHub repository rename to perform after the local one.
        candidate: GitHub repository discovered but not yet confirmed.
        guarded: Guarded.
        sql_references: Sql references.
        sqlite_edits: Sqlite edits.
        sqlite_schema_edits: Sqlite schema edits.
        web_links: Web links.

    """

    root: Path
    edits: list[FileEdit] = field(default_factory=list)
    sqlite_edits: list[SqliteCellEdit] = field(default_factory=list)
    sqlite_schema_edits: list[SqliteSchemaEdit] = field(default_factory=list)
    sql_references: list[SqlApplicationReference] = field(default_factory=list)
    renames: list[tuple[Path, Path]] = field(default_factory=list)
    root_target: Path | None = None
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    leftovers: list[tuple[Path, int, str]] = field(default_factory=list)
    guarded: list[tuple[Path, int, str, str]] = field(default_factory=list)
    web_links: list[tuple[str, int, int]] = field(default_factory=list)
    remote: RemoteRename | None = None
    candidate: RemoteRename | None = None


@dataclass(frozen=True, slots=True)
class _Context:
    """Settings shared by every file of one plan.

    Attributes:
        rules: Old-name matcher, styles, and new-name words.
        prefixes: Absolute project-root spellings (old and new location).
        needles: Old-name byte spellings for unreadable-file reporting.
        options: User options.
        leftover: Case-insensitive pattern for unrecognized spellings.
        roots: Source roots that dotted names are resolved against.

    """

    rules: RenameRules
    prefixes: tuple[str, ...]
    needles: frozenset[bytes]
    options: Options
    leftover: Pattern[str]
    roots: tuple[Path, ...] = ()


def _words(*, name: str) -> tuple[str, ...]:
    """Split a project name into lowercase words.

    Args:
        name: Name in any casing or separator style.

    Returns:
        The component words, lowercased.

    """
    words: list[str] = []
    for chunk in split(pattern="[_\\-.\\s]+", string=name):
        words.extend(
            findall(
                pattern="[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+",
                string=chunk,
            ),
        )
    return tuple(word.lower() for word in words if word)


def _styled(*, words: tuple[str, ...], style: str) -> str:
    """Render words in one casing convention.

    Args:
        words: Component words.
        style: One of the ``_STYLES`` keys.

    Returns:
        The styled name.

    """
    joined: dict[str, str] = {
        "snake": "_".join(words),
        "screaming": "_".join(words).upper(),
        "kebab": "-".join(words),
        "dot": ".".join(words),
        "flat": "".join(words),
        "lower": " ".join(words),
        "upper": " ".join(words).upper(),
        "title": " ".join(word.capitalize() for word in words),
        "camel": words[0] + "".join(w.capitalize() for w in words[1:]),
        "pascal": "".join(word.capitalize() for word in words),
    }
    return joined[style]


def _kind(*, suffix: str) -> str:
    """Classify a file by suffix for ambiguous-style resolution.

    Args:
        suffix: Lowercase file suffix, with its dot.

    Returns:
        ``prose``, ``data`` or ``code``.

    """
    if suffix in Constants.prose:
        return "prose"
    if suffix in Constants.data:
        return "data"
    return "code"


def _name_matcher(
    *,
    names: Iterable[str],
    boundary: str = "word",
    abbreviations: tuple[tuple[str, str], ...] = (),
    dotted: bool = True,
) -> tuple[Pattern[str], dict[str, tuple[str, ...]]]:
    """Build one regex matching each old name in every casing style.

    Args:
        names: Old project names and aliases.
        boundary: Key of ``_BOUNDARIES``.
        abbreviations: Exact ``(old, new)`` short forms to replace verbatim.
        dotted: Include the dotted spelling (``abc.cde``) in the pattern.

    Returns:
        The compiled pattern and a ``group name -> candidate styles`` map.

    """
    literal_styles: dict[str, list[str]] = {}
    for name in names:
        words: tuple[str, ...] = _words(name=name)
        if not words:
            continue
        for style in Constants.styles:
            if style == "dot" and (not dotted):
                continue
            candidates: list[str] = literal_styles.setdefault(
                _styled(words=words, style=style),
                [],
            )
            if style not in candidates:
                candidates.append(style)
    for short, replacement in abbreviations:
        literal_styles[short] = [f"={replacement}"]
    entries: list[tuple[str, list[str]]] = sorted(
        literal_styles.items(),
        key=lambda pair: -len(pair[0]),
    )
    group_styles: dict[str, tuple[str, ...]] = {
        f"G{index}": tuple(styles)
        for index, (_, styles) in enumerate(iterable=entries)
    }
    before, after = Constants.boundaries[boundary]
    pattern: Pattern[str] = compile_pattern(
        pattern=before
        + "(?:"
        + "|".join(
            (
                f"(?P<G{index}>{escape(pattern=literal)})"
                for index, (literal, _) in enumerate(iterable=entries)
            ),
        )
        + ")"
        + after,
    )
    return (pattern, group_styles)


def _leftover_pattern(*, names: Iterable[str]) -> Pattern[str]:
    """Build a case-insensitive pattern for spellings the matcher misses.

    Args:
        names: Old project names.

    Returns:
        A pattern matching each name's words in any casing, optionally
        separated by ``_``, ``-``, ``.`` or a space.

    """
    alternatives: list[str] = [
        "[_\\-. ]?".join(escape(pattern=word) for word in words)
        for words in (_words(name=name) for name in names)
        if words
    ]
    return compile_pattern(
        pattern="(?<!\\w)(?:" + "|".join(alternatives) + ")(?!\\w)",
        flags=IGNORECASE,
    )


def _literal(*, candidates: tuple[str, ...]) -> str | None:
    """Return the verbatim replacement of an abbreviation group.

    Args:
        candidates: Candidate styles of a matched group.

    Returns:
        The replacement text, or ``None`` for an ordinary name group.

    """
    first: str = candidates[0]
    return first[1:] if first.startswith("=") else None


def _pick(*, candidates: tuple[str, ...], kind: str) -> str:
    """Choose one style among those a spelling could have been written in.

    Args:
        candidates: Styles that render the matched text identically.
        kind: File kind from ``_kind``.

    Returns:
        The preferred style for that kind of file.

    """
    for style in Constants.preference[kind]:
        if style in candidates:
            return style
    return candidates[0]


def _context_style(
    *,
    style: str,
    suffix: str,
    line: str,
    span: tuple[int, int],
) -> str:
    """Adjust a detected style for its syntactic context.

    Args:
        style: Style detected from the match itself.
        suffix: Lowercase file suffix.
        line: Line containing the match.
        span: Match ``(start, end)`` offsets inside ``line``.

    Returns:
        The style to render.

    """
    start, end = span
    before: str = line[start - 1] if start else ""
    after: str = line[end] if end < len(line) else ""
    if (before and before in "/.") or (after and after in "/."):
        return style
    if line.count("`", 0, start) % 2 == 1:
        return style
    if suffix in Constants.doc_suffixes and line.lstrip().startswith("#"):
        return "title"
    if suffix == ".toml" and Constants.name_line.match(string=line):
        return "kebab"
    return style


def _inside(*, token: str, prefixes: tuple[str, ...]) -> str | None:
    """Express an absolute token relative to the project, if it is inside.

    Args:
        token: Absolute path token.
        prefixes: Absolute project-root spellings (old and new location).

    Returns:
        ``.`` or the relative remainder, or ``None`` when outside.

    """
    for prefix in prefixes:
        if token == prefix:
            return "."
        if token.startswith(prefix + "/"):
            return token[len(prefix) + 1 :]
    return None


def _protected_paths(
    *,
    line: str,
    prefixes: tuple[str, ...],
    keep_absolute: bool,
) -> tuple[str, list[tuple[int, int]], int]:
    """Relativize in-project absolute paths and shield external ones.

    Args:
        line: Raw line.
        prefixes: Absolute project-root spellings (old and new location).
        keep_absolute: Leave in-project absolute paths untouched.

    Returns:
        The line with in-project paths made relative, the spans of paths
        that must not be restyled, and the number of paths relativized.

    """
    pieces: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor: int = 0
    length: int = 0
    relativized: int = 0
    for match in Constants.path_token.finditer(string=line):
        token: str = match.group(0)
        pieces.append(line[cursor : match.start()])
        length += match.start() - cursor
        cursor = match.end()
        inside: str | None = _inside(token=token, prefixes=prefixes)
        if inside is not None and (not keep_absolute):
            pieces.append(inside)
            length += len(inside)
            relativized += 1
            continue
        pieces.append(token)
        if inside is not None or Path(token).exists():
            spans.append((length, length + len(token)))
        length += len(token)
    pieces.append(line[cursor:])
    return ("".join(pieces), spans, relativized)


def dotted_path_exists(*, dotted: str, roots: tuple[Path, ...]) -> bool:
    """Report whether a dotted name addresses an existing module or package.

    ``exactus.tools`` resolves when ``exactus/tools/`` or
    ``exactus/tools.py`` (or
    another source file) exists under a source root, so the text is an import
    path that must keep working.

    Args:
        dotted: Matched text such as ``abc.cde``.
        roots: Source roots to look under.

    Returns:
        ``True`` when the dotted name is a project path.

    """
    parts: list[str] = dotted.split(sep=".")
    for base in roots:
        if base.joinpath(*parts).is_dir():
            return True
        parent: Path = base.joinpath(*parts[:-1])
        if any(
            (parent / f"{parts[-1]}{suffix}").is_file()
            for suffix in Constants.module_suffixes
        ):
            return True
    return False


def _dotted_is_guarded(
    *,
    text: str,
    span: tuple[int, int],
    suffix: str,
    safe: tuple[tuple[int, int], ...],
    context: _Context,
) -> bool:
    """Decide whether a dotted occurrence must be left unchanged.

    An occurrence is guarded when it names an existing module or package
    path, or when it sits in executable code or Markdown code rather than in
    a string, comment, or prose region proven safe by a parser.

    Args:
        text: The matched dotted text.
        span: Match offsets inside the line.
        suffix: Lowercase file suffix.
        safe: Safe regions of the line.
        context: Shared rewrite settings.

    Returns:
        Whether the occurrence stays as written.

    """
    if dotted_path_exists(dotted=text, roots=context.roots):
        return True
    return suffix in Constants.dotted_guard_suffixes and (
        not span_contained(span=span, containers=safe)
    )


def _is_dotted(*, candidates: tuple[str, ...]) -> bool:
    """Return whether a matcher group represents a dotted spelling.

    Args:
        candidates: Candidate styles attached to a matcher group.

    Returns:
        Whether the spelling can only be interpreted as dotted style.

    """
    return candidates == ("dot",)


def _line_spans_from_offsets(
    *,
    text: str,
    offsets: tuple[tuple[int, int], ...],
) -> dict[int, tuple[tuple[int, int], ...]]:
    """Convert absolute half-open offsets into one-based line/column spans.

    Args:
        text: Complete source text.
        offsets: Absolute half-open ranges.

    Returns:
        Mapping from one-based line number to half-open column ranges.

    """
    starts: list[int] = [0]
    starts.extend(
        (
            index + 1
            for index, character in enumerate(iterable=text)
            if character == "\n"
        ),
    )
    result: dict[int, list[tuple[int, int]]] = {}
    for low, high in offsets:
        for index, line_start in enumerate(iterable=starts):
            line_end: int = (
                starts[index + 1] if index + 1 < len(starts) else len(text)
            )
            if high <= line_start:
                break
            if low >= line_end:
                continue
            result.setdefault(index + 1, []).append(
                (
                    max(low, line_start) - line_start,
                    min(high, line_end) - line_start,
                ),
            )
    return {line: tuple(spans) for line, spans in result.items()}


def _utf8_byte_column_to_character(*, line: str, column: int) -> int:
    """Convert one AST UTF-8 byte column to a character column.

    Args:
        line: Value for ``line``.
        column: Value for ``column``.

    Returns:
        The resulting value.

    """
    boundaries: tuple[int, ...] = byte_boundaries(text=line)
    try:
        return byte_to_character(boundaries=boundaries, offset=column)
    except ValueError:
        return len(line)


@dataclass(slots=True)
class _SqlLine:
    """Scan one SQL line for regions outside strings and comments.

    Attributes:
        line: The line being scanned.
        in_block_comment: Whether a ``/* */`` comment is open; carried from
            line to line by the caller.
        spans: Safe half-open column ranges found so far.
        start: Column where the current safe range began.
        index: Column being examined.
        quote: Opening delimiter of the quoted region being skipped.
        terminated: Whether a ``--`` comment ended the line.

    """

    line: str
    in_block_comment: bool
    spans: list[tuple[int, int]] = field(default_factory=list)
    start: int = 0
    index: int = 0
    quote: str | None = None
    terminated: bool = False

    def scan(self) -> list[tuple[int, int]]:
        """Scan the whole line.

        Returns:
            Safe half-open column ranges.

        """
        while self.index < len(self.line):
            if self.in_block_comment:
                if not self._skip_block_comment():
                    break
            elif self.quote is not None:
                self._skip_quoted()
            elif not self._advance_code():
                break
        if (
            not self.terminated
            and self.quote is None
            and (not self.in_block_comment)
            and (self.start < len(self.line))
        ):
            self.spans.append((self.start, len(self.line)))
        return self.spans

    def _close_span(self) -> None:
        """Record the safe range that ends at the current column."""
        if self.start < self.index:
            self.spans.append((self.start, self.index))

    def _skip_block_comment(self) -> bool:
        """Advance through an open block comment.

        Returns:
            ``False`` when the comment continues past the end of the line.

        """
        end: int = self.line.find("*/", self.index)
        if end < 0:
            self.index = self.start = len(self.line)
            return False
        self.index = self.start = end + 2
        self.in_block_comment = False
        return True

    def _skip_quoted(self) -> None:
        """Advance one character inside a quoted region."""
        quote: str = cast(typ="str", val=self.quote)
        closing: str = "]" if quote == "[" else quote
        if self.line[self.index] != closing:
            self.index += 1
            return
        following: str = self.line[self.index + 1 : self.index + 2]
        if closing in {"'", '"', "`"} and following == closing:
            self.index += 2
            return
        self.quote = None
        self.index += 1
        self.start = (
            self.index if closing == "'" else min(self.start, self.index)
        )

    def _advance_code(self) -> bool:
        """Advance one step through code outside quotes and comments.

        Returns:
            ``False`` when a ``--`` comment ends the line.

        """
        if self.line.startswith("--", self.index):
            self._close_span()
            self.terminated = True
            return False
        if self.line.startswith("/*", self.index):
            self._close_span()
            self.in_block_comment = True
            self.index += 2
            self.start = self.index
            return True
        character: str = self.line[self.index]
        if character == "'":
            self._close_span()
            self.quote = character
            self.index += 1
            self.start = self.index
        else:
            if character in {'"', "`", "["}:
                self.quote = character
            self.index += 1
        return True


def sql_safe_dotted_spans(
    *,
    text: str,
) -> dict[int, tuple[tuple[int, int], ...]]:
    """Return SQL regions where dotted identifiers may be rewritten.

    SQLite identifiers are structural, so unquoted and identifier-quoted
    regions are safe. Single-quoted string literals and comments are excluded.
    Malformed quoted text fails closed for the affected remainder.

    Args:
        text: Complete SQL source text.

    Returns:
        One-based line numbers mapped to safe half-open column spans.

    """
    result: dict[int, tuple[tuple[int, int], ...]] = {}
    in_block_comment: bool = False
    for number, line in enumerate(
        iterable=text.splitlines(keepends=True),
        start=1,
    ):
        scanner: _SqlLine = _SqlLine(
            line=line,
            in_block_comment=in_block_comment,
        )
        spans: list[tuple[int, int]] = scanner.scan()
        in_block_comment = scanner.in_block_comment
        if spans:
            result[number] = tuple(spans)
    return result


def python_safe_dotted_spans(
    *,
    text: str,
) -> dict[int, tuple[tuple[int, int], ...]]:
    """Find Python documentation, literal-string, and comment regions.

    The implementation intentionally does *not* mark any part of an f-string
    as safe: its expressions are executable Python and its literal text is
    interleaved with them. Ordinary
    string constants, including real module/class/function docstrings, are
    obtained from the AST so their exact source ranges are known. Comments are
    obtained from ``tokenize``. Everything else is executable syntax and is
    therefore guarded for dotted replacement.

    Args:
        text: Complete Python source text.

    Returns:
        One-based line numbers mapped to safe half-open column spans.

    """
    spans: dict[int, list[tuple[int, int]]] = {}
    try:
        tree: Module = parse(source=text)
    except SyntaxError:
        return {}
    source_lines: list[str] = text.splitlines(keepends=True)
    fstring_parts: frozenset[int] = frozenset(
        id(part)
        for node in ast_walk(node=tree)
        if isinstance(node, JoinedStr)
        for part in ast_walk(node=node)
    )
    for node in ast_walk(node=tree):
        if (
            not isinstance(node, Constant)
            or not isinstance(node.value, str)
            or id(node) in fstring_parts
            or (node.end_lineno is None)
        ):
            continue
        for line_number in range(node.lineno, node.end_lineno + 1):
            source_line: str = source_lines[line_number - 1]
            low: int = (
                _utf8_byte_column_to_character(
                    line=source_line,
                    column=node.col_offset,
                )
                if line_number == node.lineno
                else 0
            )
            high: int = (
                _utf8_byte_column_to_character(
                    line=source_line,
                    column=node.end_col_offset
                    if node.end_col_offset is not None
                    else len(source_line) - 1,
                )
                if line_number == node.end_lineno
                else len(source_line)
            )
            spans.setdefault(line_number, []).append((low, high))
    try:
        for token in generate_tokens(
            readline=StringIO(initial_value=text).readline,
        ):
            if token.type != COMMENT:
                continue
            spans.setdefault(token.start[0], []).append(
                (token.start[1], token.end[1]),
            )
    except (IndentationError, TokenError):
        return {}
    return {line: tuple(ranges) for line, ranges in spans.items()}


def byte_boundaries(*, text: str) -> tuple[int, ...]:
    """Return UTF-8 byte offsets for every Python character boundary.

    Args:
        text: Unicode source text.

    Returns:
        Byte offset corresponding to every character boundary, including EOF.

    """
    boundaries: list[int] = [0]
    total: int = 0
    for character in text:
        total += len(character.encode(encoding="utf-8"))
        boundaries.append(total)
    return tuple(boundaries)


def byte_to_character(*, boundaries: tuple[int, ...], offset: int) -> int:
    """Translate an exact Tree-sitter UTF-8 byte boundary to a character index.

    Args:
        boundaries: UTF-8 byte offsets for each Python character boundary.
        offset: Tree-sitter byte offset.

    Returns:
        Corresponding Python string index.

    Raises:
        ValueError: If ``offset`` is not a valid UTF-8 character boundary.

    """
    low: int = 0
    high: int = len(boundaries)
    while low < high:
        middle: int = (low + high) // 2
        if boundaries[middle] < offset:
            low = middle + 1
        else:
            high = middle
    if low == len(boundaries) or boundaries[low] != offset:
        msg: str = f"Tree-sitter returned non-character byte boundary {offset}"
        raise ValueError(msg)
    return low


def _node_character_span(
    *,
    node: Node,
    boundaries: tuple[int, ...],
) -> tuple[int, int]:
    """Return a Tree-sitter node's half-open Python character range.

    Args:
        node: Parsed syntax node.
        boundaries: UTF-8 byte offsets for every character boundary.

    Returns:
        Half-open Python character range.

    """
    return (
        byte_to_character(boundaries=boundaries, offset=node.start_byte),
        byte_to_character(boundaries=boundaries, offset=node.end_byte),
    )


def _node_text(*, node: Node, source: bytes) -> str:
    """Decode a syntax node's exact UTF-8 source.

    Args:
        node: Syntax node.
        source: Complete UTF-8 source bytes.

    Returns:
        Node source text.

    """
    return source[node.start_byte : node.end_byte].decode(encoding="utf-8")


def _descendants(*, node: Node) -> tuple[Node, ...]:
    """Return all descendants of a Tree-sitter node in source order.

    Args:
        node: Root node.

    Returns:
        Descendant nodes, excluding ``node`` itself.

    """
    result: list[Node] = []
    pending: list[Node] = list(reversed(node.children))
    while pending:
        child: Node = pending.pop()
        result.append(child)
        pending.extend(reversed(child.children))
    return tuple(result)


def parse_tree(*, text: str, language: str) -> tuple[bytes, Node] | None:
    """Parse text with a Python-hosted Tree-sitter grammar, failing closed.

    Args:
        text: Source text.
        language: ``tree-sitter-language-pack`` grammar name.

    Returns:
        UTF-8 source and root node, or ``None`` when the grammar rejects input.

    """
    parser: Parser = get_parser(name=language)
    source: bytes = text.encode(encoding="utf-8")
    root: Node = parser.parse(source).root_node
    return None if root.has_error else (source, root)


def _jsdoc_safe_offsets(
    *,
    text: str,
    base: int,
) -> tuple[tuple[int, int], ...]:
    """Return JSDoc prose while excluding symbol, code, and type regions.

    Args:
        text: Complete JSDoc comment including delimiters.
        base: Character offset of ``text`` in the containing source.

    Returns:
        Absolute half-open character ranges containing documentation prose.

    """
    blocked: list[tuple[int, int]] = []
    patterns: tuple[Pattern[str], ...] = (
        compile_pattern(
            pattern="\\{@(?:link|linkcode|linkplain|code)\\b.*?\\}",
        ),
        compile_pattern(pattern="`+[^`\\n]*`+"),
        compile_pattern(
            pattern=(
                "@(?:type|param|returns?|return|throws?|template)\\s*\\{[^}\\n"
                "]*\\}"
            ),
        ),
        compile_pattern(
            pattern="@(?:extends|implements|memberof|mixes|see)\\s+\\S+",
        ),
    )
    for pattern in patterns:
        blocked.extend(match.span() for match in pattern.finditer(string=text))
    return tuple(
        (
            (base + low, base + high)
            for low, high in _subtract_offsets(
                spans=((0, len(text)),),
                blocked=tuple(blocked),
            )
        ),
    )


def _ancestor_call_name(*, node: Node, source: bytes) -> str | None:
    """Return the nearest JavaScript call expression's callee spelling.

    Args:
        node: String/template syntax node.
        source: Complete JavaScript UTF-8 source.

    Returns:
        Callee source or ``None`` when the node is not inside a call.

    """
    current: Node | None = node.parent
    while current is not None:
        if current.type == "call_expression":
            function: Node | None = current.child_by_field_name("function")
            return (
                None
                if function is None
                else _node_text(node=function, source=source)
            )
        if current.type in {"statement_block", "program"}:
            return None
        current = current.parent
    return None


def _javascript_safe_offsets(
    *,
    text: str,
    language: str = "javascript",
) -> tuple[tuple[int, int], ...]:
    """Return parser-proven JavaScript documentation/comment/string regions.

    Selector-bearing DOM API arguments are deliberately excluded because their
    contents are syntax-bearing cross-language references. Template strings
    containing substitutions are also excluded as mixed executable regions.

    Args:
        text: JavaScript/JSX/TypeScript source.
        language: Tree-sitter grammar name.

    Returns:
        Safe half-open Python character ranges. Empty means fail-closed.

    """
    parsed: tuple[bytes, Node] | None = parse_tree(
        text=text,
        language=language,
    )
    if parsed is None:
        return ()
    source, root = parsed
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    safe: list[tuple[int, int]] = []
    selector_calls: frozenset[str] = frozenset(
        ("querySelector", "querySelectorAll", "matches", "closest"),
    )
    for node in _descendants(node=root):
        if node.type == "comment":
            low, high = _node_character_span(node=node, boundaries=boundaries)
            value: str = text[low:high]
            safe.extend(
                _jsdoc_safe_offsets(text=value, base=low)
                if value.startswith("/**")
                else ((low, high),),
            )
            continue
        if node.type not in {"string", "string_fragment", "template_string"}:
            continue
        if (
            node.type == "string_fragment"
            and node.parent is not None
            and (node.parent.type == "template_string")
        ):
            continue
        if node.type == "template_string" and any(
            child.type in {"template_substitution", "substitution"}
            for child in node.children
        ):
            continue
        call_name: str | None = _ancestor_call_name(node=node, source=source)
        if (
            call_name is not None
            and call_name.rsplit(sep=".", maxsplit=1)[-1] in selector_calls
        ):
            continue
        safe.append(_node_character_span(node=node, boundaries=boundaries))
    return tuple(safe)


def _css_safe_offsets(*, text: str) -> tuple[tuple[int, int], ...]:
    """Return parser-proven CSS comments and string-value regions.

    Args:
        text: CSS source.

    Returns:
        Safe half-open character ranges. Selectors remain excluded.

    """
    parsed: tuple[bytes, Node] | None = parse_tree(text=text, language="css")
    if parsed is None:
        return ()
    _, root = parsed
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    return tuple(
        _node_character_span(node=node, boundaries=boundaries)
        for node in _descendants(node=root)
        if node.type in {"comment", "string_value", "string"}
    )


def _subtract_offsets(
    *,
    spans: tuple[tuple[int, int], ...],
    blocked: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """Subtract blocked ranges from allowed ranges.

    Args:
        spans: Allowed half-open ranges.
        blocked: Ranges to remove.

    Returns:
        Remaining half-open ranges.

    """
    result: list[tuple[int, int]] = []
    for low, high in spans:
        fragments: list[tuple[int, int]] = [(low, high)]
        for block_low, block_high in blocked:
            next_fragments: list[tuple[int, int]] = []
            for frag_low, frag_high in fragments:
                if block_high <= frag_low or frag_high <= block_low:
                    next_fragments.append((frag_low, frag_high))
                    continue
                if frag_low < block_low:
                    next_fragments.append((frag_low, block_low))
                if block_high < frag_high:
                    next_fragments.append((block_high, frag_high))
            fragments = next_fragments
        result.extend(fragments)
    return tuple(result)


def _html_attribute_parts(
    *,
    node: Node,
    source: bytes,
) -> tuple[str, Node] | None:
    """Return an HTML attribute's normalized name and value node.

    Args:
        node: Tree-sitter HTML ``attribute`` node.
        source: Complete HTML UTF-8 source.

    Returns:
        ``(name, value_node)`` or ``None`` for valueless/unrecognized attrs.

    """
    name_node: Node | None = node.child_by_field_name("name")
    value_node: Node | None = node.child_by_field_name("value")
    if name_node is None or value_node is None:
        named: tuple[Node, ...] = tuple(
            child for child in node.children if child.is_named
        )
        if len(named) < Constants.min_attribute_parts:
            return None
        name_node, value_node = (named[0], named[-1])
    return (_node_text(node=name_node, source=source).lower(), value_node)


def _unquote_span(
    *,
    node: Node,
    source: bytes,
    boundaries: tuple[int, ...],
) -> tuple[int, int]:
    """Return an HTML attribute value's content range without quotes.

    Args:
        node: Attribute value syntax node.
        source: Complete UTF-8 source.
        boundaries: UTF-8 byte offsets for every character boundary.

    Returns:
        Half-open character range of the value content.

    """
    low, high = _node_character_span(node=node, boundaries=boundaries)
    value: str = _node_text(node=node, source=source)
    return (
        (low + 1, high - 1)
        if len(value) >= Constants.quoted_length and value[0] in {"'", '"'}
        else (low, high)
    )


def _embedded_offsets(
    *,
    text: str,
    low: int,
    high: int,
    language: str,
) -> tuple[tuple[int, int], ...]:
    """Parse an embedded language region and translate its ranges to the host.

    Args:
        text: Complete host source.
        low: Embedded region start character offset.
        high: Embedded region end character offset.
        language: Embedded grammar name.

    Returns:
        Host-relative safe character ranges.

    """
    nested: str = text[low:high]
    offsets: tuple[tuple[int, int], ...] = (
        _css_safe_offsets(text=nested)
        if language == "css"
        else _javascript_safe_offsets(text=nested, language=language)
    )
    return tuple(((low + start, low + end) for start, end in offsets))


def _parent_type(*, node: Node) -> str:
    """Return a syntax node's parent type, or an empty string at the root.

    Args:
        node: Parsed syntax node.

    Returns:
        The parent's grammar type name.

    """
    return "" if node.parent is None else node.parent.type


def _style_attribute_offsets(
    *,
    text: str,
    low: int,
    high: int,
) -> tuple[tuple[int, int], ...]:
    """Find safe CSS inside an inline ``style`` attribute value.

    A declaration list is not a stylesheet, so it is wrapped in a rule for
    the CSS grammar and the resulting ranges are shifted back.

    Args:
        text: Complete host source.
        low: Attribute value start character offset.
        high: Attribute value end character offset.

    Returns:
        Host-relative safe character ranges.

    """
    nested: str = text[low:high]
    wrapper: int = len("x{")
    ranges: list[tuple[int, int]] = []
    for start, end in _css_safe_offsets(text=f"x{{{nested}}}"):
        first: int = max(start - wrapper, 0)
        last: int = min(end - wrapper, len(nested))
        if first < last:
            ranges.append((low + first, low + last))
    return tuple(ranges)


def _html_attribute_offsets(
    *,
    node: Node,
    text: str,
    source: bytes,
    boundaries: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    """Return the safe ranges of one HTML attribute value.

    Args:
        node: Tree-sitter HTML ``attribute`` node.
        text: Complete HTML source.
        source: Complete HTML UTF-8 source.
        boundaries: UTF-8 byte offsets for every character boundary.

    Returns:
        Safe half-open ranges: embedded CSS for ``style``, embedded
        JavaScript for ``on*`` handlers, the plain value otherwise.

    """
    parts: tuple[str, Node] | None = _html_attribute_parts(
        node=node,
        source=source,
    )
    if parts is None:
        return ()
    name, value_node = parts
    low, high = _unquote_span(
        node=value_node,
        source=source,
        boundaries=boundaries,
    )
    if name == "style":
        return _style_attribute_offsets(text=text, low=low, high=high)
    if name.startswith("on"):
        return _embedded_offsets(
            text=text,
            low=low,
            high=high,
            language="javascript",
        )
    return ((low, high),)


def _html_content_offsets(
    *,
    node: Node,
    text: str,
    boundaries: tuple[int, ...],
) -> tuple[tuple[int, int], ...]:
    """Return the safe ranges of ``<script>`` or ``<style>`` content.

    Args:
        node: Raw-text, script-content, or style-content node.
        text: Complete HTML source.
        boundaries: UTF-8 byte offsets for every character boundary.

    Returns:
        Safe ranges from parsing the embedded language, or nothing when the
        parent is neither element.

    """
    language: str | None = {
        "script_element": "javascript",
        "style_element": "css",
    }.get(_parent_type(node=node))
    if language is None:
        return ()
    low, high = _node_character_span(node=node, boundaries=boundaries)
    return _embedded_offsets(text=text, low=low, high=high, language=language)


def _html_safe_offsets(*, text: str) -> tuple[tuple[int, int], ...]:
    """Return parser-proven HTML prose/attributes plus parsed embedded regions.

    Args:
        text: HTML source.

    Returns:
        Safe half-open character ranges. Empty means fail-closed.

    """
    parsed: tuple[bytes, Node] | None = parse_tree(text=text, language="html")
    if parsed is None:
        return ()
    source, root = parsed
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    safe: list[tuple[int, int]] = []
    for node in _descendants(node=root):
        if node.type in {"text", "comment"}:
            if _parent_type(node=node) not in {
                "script_element",
                "style_element",
            }:
                safe.append(
                    _node_character_span(node=node, boundaries=boundaries),
                )
        elif node.type == "attribute":
            safe.extend(
                _html_attribute_offsets(
                    node=node,
                    text=text,
                    source=source,
                    boundaries=boundaries,
                ),
            )
        elif node.type in {"raw_text", "script_content", "style_content"}:
            safe.extend(
                _html_content_offsets(
                    node=node,
                    text=text,
                    boundaries=boundaries,
                ),
            )
    return tuple(safe)


def _inline_code_offsets(
    *,
    text: str,
    base: int,
) -> tuple[tuple[int, int], ...]:
    """Find inline code spans inside one Markdown paragraph.

    The block grammar leaves paragraph text opaque, so the paragraph is
    parsed again with the inline grammar. If that parse fails the whole
    paragraph is reported as code, which guards it (fail closed).

    Args:
        text: Text of one block-level ``inline`` node.
        base: Character offset of ``text`` in the complete document.

    Returns:
        Absolute half-open character ranges of inline code.

    """
    parsed: tuple[bytes, Node] | None = parse_tree(
        text=text,
        language="markdown_inline",
    )
    if parsed is None:
        return ((base, base + len(text)),)
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    spans: list[tuple[int, int]] = []
    for node in _descendants(node=parsed[1]):
        if node.type == "code_span":
            low, high = _node_character_span(node=node, boundaries=boundaries)
            spans.append((base + low, base + high))
    return tuple(spans)


def _markdown_safe_offsets(*, text: str) -> tuple[tuple[int, int], ...]:
    """Return parser-proven Markdown prose while excluding code syntax.

    Args:
        text: Markdown source.

    Returns:
        Safe prose ranges. Empty means fail-closed.

    """
    parsed: tuple[bytes, Node] | None = parse_tree(
        text=text,
        language="markdown",
    )
    if parsed is None:
        return ()
    _, root = parsed
    boundaries: tuple[int, ...] = byte_boundaries(text=text)
    blocked_types: frozenset[str] = frozenset(
        (
            "code_span",
            "fenced_code_block",
            "indented_code_block",
            "inline_code",
            "code_fence_content",
        ),
    )
    blocked: list[tuple[int, int]] = []
    for node in _descendants(node=root):
        if node.type in blocked_types or (
            "code" in node.type and "block" in node.type
        ):
            blocked.append(
                _node_character_span(node=node, boundaries=boundaries),
            )
        elif node.type == "inline":
            low, high = _node_character_span(node=node, boundaries=boundaries)
            blocked.extend(_inline_code_offsets(text=text[low:high], base=low))
    return _subtract_offsets(spans=((0, len(text)),), blocked=tuple(blocked))


def _tree_sitter_language(*, suffix: str) -> str | None:
    """Map a source suffix to its Tree-sitter grammar.

    Args:
        suffix: Lowercase file suffix.

    Returns:
        Grammar name or ``None`` for formats handled by native Python parsers.

    """
    return {
        ".css": "css",
        ".html": "html",
        ".htm": "html",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".md": "markdown",
        ".markdown": "markdown",
    }.get(suffix)


def safe_dotted_spans(
    *,
    text: str,
    suffix: str,
) -> dict[int, tuple[tuple[int, int], ...]]:
    """Return syntax-proven regions where dotted text may be rewritten.

    Python uses its native AST/tokenizer. JavaScript, TypeScript, HTML, CSS,
    and Markdown use Python-hosted Tree-sitter parsers. Parser failure yields
    no safe ranges, deliberately guarding every dotted candidate.

    Args:
        text: Complete decoded file content.
        suffix: Lowercase file suffix.

    Returns:
        One-based line numbers mapped to safe half-open character ranges.

    """
    if suffix in {".py", ".pyi"}:
        return python_safe_dotted_spans(text=text)
    if suffix == ".sql":
        return sql_safe_dotted_spans(text=text)
    offsets: tuple[tuple[int, int], ...] | None = _tree_sitter_offsets(
        text=text,
        suffix=suffix,
    )
    if offsets is not None:
        return _line_spans_from_offsets(text=text, offsets=offsets)
    return {
        line_number: spans
        for line_number, line in enumerate(
            iterable=text.splitlines(keepends=True),
            start=1,
        )
        if (spans := _comment_spans(line=line, suffix=suffix))
    }


def _tree_sitter_offsets(
    *,
    text: str,
    suffix: str,
) -> tuple[tuple[int, int], ...] | None:
    """Find safe ranges in formats parsed with Tree-sitter.

    Args:
        text: Complete decoded file content.
        suffix: Lowercase file suffix.

    Returns:
        Safe half-open character ranges, empty when the parser fails, or
        ``None`` when the suffix is not a Tree-sitter format.

    """
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        return _javascript_safe_offsets(
            text=text,
            language=_tree_sitter_language(suffix=suffix) or "javascript",
        )
    if suffix == ".css":
        return _css_safe_offsets(text=text)
    if suffix in {".html", ".htm"}:
        return _html_safe_offsets(text=text)
    if suffix in {".md", ".markdown"}:
        return _markdown_safe_offsets(text=text)
    return None


def _comment_spans(*, line: str, suffix: str) -> tuple[tuple[int, int], ...]:
    """Return where one line of an unparsed format may be rewritten.

    Prose and data formats (text, TOML, YAML, JSON, XML, CSV, ...) hold
    names as text, so the whole line is safe. For anything else only a
    trailing ``#`` or ``//`` comment is: the rest may be executable syntax
    this script has no parser for, so it stays guarded.

    Args:
        line: One source line, with or without its terminator.
        suffix: Lowercase file suffix.

    Returns:
        Half-open column ranges that may be rewritten.

    """
    end: int = len(line.rstrip("\r\n"))
    if not end:
        return ()
    if suffix in Constants.prose or suffix in Constants.data:
        return ((0, end),)
    marker: Match[str] | None = Constants.line_comment.search(string=line)
    return ((marker.start(), end),) if marker is not None else ()


def span_contained(
    *,
    span: tuple[int, int],
    containers: tuple[tuple[int, int], ...],
) -> bool:
    """Return whether ``span`` is fully inside one allowed container.

    Args:
        span: Candidate half-open range.
        containers: Allowed half-open ranges.

    Returns:
        Whether one container fully covers the candidate.

    """
    start, end = span
    return any((low <= start and end <= high for low, high in containers))


def _rewrite_line(
    *,
    line: str,
    context: _Context,
    suffix: str,
    safe_dotted: tuple[tuple[int, int], ...] = (),
) -> tuple[str, int, tuple[tuple[int, int], ...]]:
    """Rewrite path tokens and project-name spellings on one line.

    Args:
        line: Raw line including its newline.
        context: Shared rewrite settings.
        suffix: Lowercase file suffix for context rules.
        safe_dotted: Regions where dotted spelling is known to be non-code.

    Returns:
        Rewritten line, substitution count, and guarded dotted spans.

    """
    relative, shielded, count = _protected_paths(
        line=line,
        prefixes=context.prefixes,
        keep_absolute=context.options.keep_absolute,
    )
    kind: str = _kind(suffix=suffix)
    rules: RenameRules = context.rules
    pieces: list[str] = []
    guarded: list[tuple[int, int]] = []
    cursor: int = 0
    for match in rules.names.finditer(string=relative):
        start, end = match.span()
        if any((start < high and end > low for low, high in shielded)):
            continue
        candidates: tuple[str, ...] = rules.styles[
            cast(typ="str", val=match.lastgroup)
        ]
        if (
            context.options.dotted
            and (not context.options.dotted_code)
            and _is_dotted(candidates=candidates)
            and _dotted_is_guarded(
                text=match.group(0),
                span=(start, end),
                suffix=suffix,
                safe=safe_dotted if relative == line else (),
                context=context,
            )
        ):
            guarded.append((start, end))
            continue
        verbatim: str | None = _literal(candidates=candidates)
        pieces.append(relative[cursor:start])
        if verbatim is not None:
            pieces.append(verbatim)
            cursor = end
            count += 1
            continue
        style: str = _context_style(
            style=_pick(candidates=candidates, kind=kind),
            suffix=suffix,
            line=relative,
            span=(start, end),
        )
        pieces.append(_styled(words=rules.words, style=style))
        cursor = end
        count += 1
    pieces.append(relative[cursor:])
    return ("".join(pieces), count, tuple(guarded))


def _restyle_name(*, name: str, rules: RenameRules) -> str:
    """Restyle the project name inside one file or directory name.

    Args:
        name: Path component.
        rules: Old-name matcher, styles, and new-name words.

    Returns:
        The component with every old-name spelling replaced.

    """
    kind: str = _kind(suffix=Path(name).suffix.lower())

    def _sub(match: Match[str]) -> str:
        """Render the new name in the style of one match.

        Args:
            match: Old-name match inside the path component.

        Returns:
            The restyled new name, or the abbreviation's replacement.

        """
        candidates: tuple[str, ...] = rules.styles[
            cast(typ="str", val=match.lastgroup)
        ]
        verbatim: str | None = _literal(candidates=candidates)
        if verbatim is not None:
            return verbatim
        return _styled(
            words=rules.words,
            style=_pick(candidates=candidates, kind=kind),
        )

    return rules.names.sub(repl=_sub, string=name)


def _locate(*, start: Path) -> Path | None:
    """Find a repository root by walking upward from ``start``.

    Args:
        start: Directory the search begins in.

    Returns:
        The nearest ancestor holding a repository marker, or ``None``.

    """
    for directory in (start, *start.parents):
        if any(
            (directory / marker).exists()
            for marker in (".git", "pyproject.toml")
        ):
            return directory
    return None


def _resolve_root(*, given: str | None, script: Path) -> Path:
    """Pick the repository root: argument, caller's tree, then the script's.

    Args:
        given: Explicit root argument, if any.
        script: Absolute path of this script.

    Returns:
        The resolved project root.

    Raises:
        RenameError: When no root can be located.

    """
    if given is not None:
        return Path(given).expanduser().resolve()
    found: Path | None = _locate(start=Path.cwd())
    if found is None:
        found = _locate(start=script.parent)
    if found is None:
        msg: str = "could not locate a repository root; pass it as an argument"
        raise RenameError(msg)
    return found


def _project_name(*, root: Path) -> str | None:
    """Read ``[project] name`` from the root's ``pyproject.toml``.

    Args:
        root: Project root.

    Returns:
        The declared distribution name, or ``None``.

    """
    try:
        document: dict[str, object] = loads(
            (root / "pyproject.toml").read_text(encoding="utf-8"),
        )
    except (OSError, TOMLDecodeError):
        return None
    project: object = document.get("project")
    name: object = (
        cast(typ="dict[str, object]", val=project).get("name")
        if isinstance(project, dict)
        else None
    )
    return name if isinstance(name, str) else None


def _git_files(*, root: Path) -> list[Path] | None:
    """List files git knows about, honoring ``.gitignore``.

    Args:
        root: Project root.

    Returns:
        Absolute paths, or ``None`` when git is unusable here.

    """
    if not (root / ".git").exists():
        return None
    try:
        result: CompletedProcess[bytes] = run(
            args=[
                "git",
                "-C",
                str(object=root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            check=True,
        )
    except (OSError, CalledProcessError):
        return None
    return [
        root / item
        for item in result.stdout.decode(encoding="utf-8").split(sep="\x00")
        if item
    ]


def _walk_files(*, root: Path) -> list[Path]:
    """Walk the tree pruning VCS data, environments, and build output.

    Args:
        root: Project root.

    Returns:
        Absolute file and symlink paths.

    """
    found: list[Path] = []
    for directory, names, files in walk(top=root, followlinks=False):
        names[:] = sorted(
            name
            for name in names
            if name not in Constants.pruned_dirs
            and (not name.endswith(".egg-info"))
        )
        found.extend(Path(directory) / name for name in sorted(files))
    return found


def _wanted(*, path: Path, root: Path, options: Options) -> bool:
    """Apply ``--include``/``--exclude`` globs to one path.

    Args:
        path: Absolute path.
        root: Project root.
        options: Rename options.

    Returns:
        Whether the path may be touched.

    """
    relative: str = path.relative_to(root).as_posix()
    if ".git" in relative.split(sep="/"):
        return False
    if options.includes and (
        not any(
            fnmatch(name=relative, pat=pattern) for pattern in options.includes
        )
    ):
        return False
    return not any(
        fnmatch(name=relative, pat=pattern) for pattern in options.excludes
    )


def _select(*, root: Path, options: Options) -> list[Path]:
    """Choose the files a rename may touch.

    Args:
        root: Project root.
        options: Rename options.

    Returns:
        Existing paths in stable order.

    """
    listed: list[Path] | None = (
        _git_files(root=root) if options.use_git else None
    )
    candidates: list[Path] = (
        listed if listed is not None else _walk_files(root=root)
    )
    return sorted(
        path
        for path in set(candidates)
        if (path.is_symlink() or path.is_file())
        and _wanted(path=path, root=root, options=options)
    )


def _leftovers(
    *,
    path: Path,
    text: str,
    context: _Context,
) -> list[tuple[Path, int, str]]:
    """Find old-name spellings that the rewrite does not recognize.

    Args:
        path: File the text belongs to.
        text: Final content of the file.
        context: Shared rewrite settings.

    Returns:
        Up to three ``(path, line number, line)`` hits.

    """
    hits: list[tuple[Path, int, str]] = []
    for number, line in enumerate(iterable=text.splitlines(), start=1):
        if context.leftover.search(
            string=context.rules.names.sub(repl="", string=line),
        ):
            hits.append((path, number, line.strip()[:100]))
            if len(hits) == Constants.max_leftovers:
                break
    return hits


def structurally_valid_rewrite(*, text: str, suffix: str) -> bool:
    """Validate rewritten structured text before accepting an edit.

    This is a postcondition safety net: even a locally plausible replacement
    is rejected if it makes a format with an available deterministic parser
    invalid. Python is reparsed as an AST; TOML and XML use their standard
    parsers; CSV uses strict CSV parsing. Other formats retain their dedicated
    lexical/semantic guards.

    Args:
        text: Rewritten complete file content.
        suffix: Lowercase file suffix.

    Returns:
        Whether the rewritten file remains structurally valid.

    """
    try:
        if suffix in {".py", ".pyi"}:
            _ = parse(source=text)
        elif suffix == ".toml":
            _ = loads(text)
        elif suffix == ".xml":
            _ = xml_fromstring(text=text)
        elif suffix == ".csv":
            _ = tuple(csv_reader(StringIO(initial_value=text), strict=True))
        elif suffix == ".sql":
            stripped: str = text.strip()
            if stripped and (not complete_statement(statement=stripped)):
                return False
        elif (language := _tree_sitter_language(suffix=suffix)) is not None:
            parsed: tuple[bytes, Node] | None = parse_tree(
                text=text,
                language=language,
            )
            if parsed is None:
                return False
    except (CsvError, DefusedXmlException, SyntaxError, TOMLDecodeError):
        return False
    return True


def _sql_identifier(*, value: str) -> str:
    """Quote one SQLite identifier without interpolating it as SQL data.

    Args:
        value: Value for ``value``.

    Returns:
        The resulting value.

    """
    return '"' + value.replace('"', '""') + '"'


def _is_sqlite(*, path: Path) -> bool:
    """Return whether a selected file is an SQLite database.

    Args:
        path: Value for ``path``.

    Returns:
        The resulting value.

    """
    if path.suffix.lower() not in Constants.sqlite_suffixes:
        return False
    try:
        with path.open(mode="rb") as stream:
            return (
                stream.read(len(Constants.sqlite_header))
                == Constants.sqlite_header
            )
    except OSError:
        return False


def _sqlite_tables(*, connection: Connection) -> tuple[str, ...]:
    """Return user table names in deterministic order.

    Args:
        connection: Value for ``connection``.

    Returns:
        The resulting value.

    """
    schema: Table = Table(name="sqlite_schema")
    predicate: PredicateNode = (
        schema.col(name="type")
        .eq(value=Literal(value="table"))
        .and_(
            other=schema.col(name="name").like(
                value=Literal(value="sqlite_%"),
                negate=True,
            ),
        )
    )
    rows: list[Row] = execute_sql(
        connection=connection,
        statement=schema.select(columns=(schema.col(name="name"),))
        .where(predicate=predicate)
        .order_by(values=(schema.col(name="name"),)),
    ).fetchall()
    return tuple(str(object=row[0]) for row in rows)


def _sqlite_identifier_rewrite(*, value: str, context: _Context) -> str | None:
    """Return a rewritten identifier only for one unambiguous full value.

    Args:
        value: Value for ``value``.
        context: Value for ``context``.

    Returns:
        The resulting value.

    """
    rewritten, count, dotted_guarded = _rewrite_line(
        line=value,
        context=context,
        suffix=".txt",
        safe_dotted=(),
    )
    if dotted_guarded or count == 0 or rewritten == value:
        return None
    return rewritten


def _sqlite_table_edit(
    *,
    path: Path,
    table: str,
    table_names: set[str],
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> SqliteSchemaEdit | None:
    """Plan the rename of one SQLite table, guarding name collisions.

    Args:
        path: Value for ``path``.
        table: Value for ``table``.
        table_names: Value for ``table_names``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    new_table: str | None = _sqlite_identifier_rewrite(
        value=table,
        context=context,
    )
    if new_table is None:
        return None
    if new_table in table_names and new_table != table:
        guarded.append((path, 0, table, "SQLite table rename collision"))
        return None
    return SqliteSchemaEdit(
        database=path,
        kind="table",
        table=table,
        old=table,
        new=new_table,
    )


def _sqlite_column_edits(
    *,
    connection: Connection,
    path: Path,
    table: str,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> list[SqliteSchemaEdit]:
    """Plan collision-free column renames for one SQLite table.

    Args:
        connection: Value for ``connection``.
        path: Value for ``path``.
        table: Value for ``table``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    columns: list[Row] = execute_sql(
        connection=connection,
        statement=pragma(name="table_xinfo", call=Identifier(value=table)),
    ).fetchall()
    column_names: set[str] = {str(object=row[1]) for row in columns}
    planned_columns: set[str] = set()
    edits: list[SqliteSchemaEdit] = []
    for row in columns:
        column: str = str(object=row[1])
        new_column: str | None = _sqlite_identifier_rewrite(
            value=column,
            context=context,
        )
        if new_column is None:
            continue
        if (
            new_column in column_names and new_column != column
        ) or new_column in planned_columns:
            guarded.append(
                (
                    path,
                    0,
                    f"{table}.{column}",
                    "SQLite column rename collision",
                ),
            )
            continue
        planned_columns.add(new_column)
        edits.append(
            SqliteSchemaEdit(
                database=path,
                kind="column",
                table=table,
                old=column,
                new=new_column,
            ),
        )
    return edits


def _sqlite_object_edits(
    *,
    connection: Connection,
    path: Path,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> list[SqliteSchemaEdit]:
    """Plan collision-free index, trigger, and view renames.

    Args:
        connection: Value for ``connection``.
        path: Value for ``path``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    schema: Table = Table(name="sqlite_schema")
    object_types: InExpression = schema.col(name="type").in_(
        values=(
            Literal(value="index"),
            Literal(value="trigger"),
            Literal(value="view"),
        ),
    )
    predicate: PredicateNode = object_types.and_(
        other=schema.col(name="sql").is_not(value=Literal(value=None)),
    )
    schema_rows: list[Row] = execute_sql(
        connection=connection,
        statement=schema.select(
            columns=(
                schema.col(name="type"),
                schema.col(name="name"),
                schema.col(name="tbl_name"),
            ),
        )
        .where(predicate=predicate)
        .order_by(values=(schema.col(name="type"), schema.col(name="name"))),
    ).fetchall()
    schema_names: set[str] = {
        str(object=row[0])
        for row in execute_sql(
            connection=connection,
            statement=schema.select(columns=(schema.col(name="name"),)),
        ).fetchall()
    }
    edits: list[SqliteSchemaEdit] = []
    for schema_row in schema_rows:
        name: str = str(object=schema_row[1])
        new_name: str | None = _sqlite_identifier_rewrite(
            value=name,
            context=context,
        )
        if new_name is None:
            continue
        if new_name in schema_names and new_name != name:
            guarded.append(
                (path, 0, name, "SQLite schema object rename collision"),
            )
            continue
        edits.append(
            SqliteSchemaEdit(
                database=path,
                kind=str(object=schema_row[0]),
                table=str(object=schema_row[2]),
                old=name,
                new=new_name,
            ),
        )
    return edits


def _sqlite_schema_plan(
    *,
    path: Path,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> list[SqliteSchemaEdit]:
    """Plan collision-free table and column renames for SQLite.

    Args:
        path: Value for ``path``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    edits: list[SqliteSchemaEdit] = []
    uri: str = f"file:{path.as_posix()}?mode=ro"
    try:
        with closing(thing=connect(database=uri, uri=True)) as connection:
            tables: tuple[str, ...] = _sqlite_tables(connection=connection)
            table_names: set[str] = set(tables)
            for table in tables:
                table_edit: SqliteSchemaEdit | None = _sqlite_table_edit(
                    path=path,
                    table=table,
                    table_names=table_names,
                    context=context,
                    guarded=guarded,
                )
                if table_edit is not None:
                    edits.append(table_edit)
                edits.extend(
                    _sqlite_column_edits(
                        connection=connection,
                        path=path,
                        table=table,
                        context=context,
                        guarded=guarded,
                    ),
                )
            edits.extend(
                _sqlite_object_edits(
                    connection=connection,
                    path=path,
                    context=context,
                    guarded=guarded,
                ),
            )
    except (DatabaseError, SQLiteLayerError) as exc:
        guarded.append(
            (path, 0, path.name, f"SQLite schema read failed: {exc}"),
        )
    return edits


def _sqlite_schema_references(
    *,
    connection: Connection,
    path: Path,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> None:
    """Guard schema objects whose SQL text mentions the old name.

    Args:
        connection: Value for ``connection``.
        path: Value for ``path``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    """
    schema: Table = Table(name="sqlite_schema")
    schema_rows: list[Row] = execute_sql(
        connection=connection,
        statement=schema.select(
            columns=(
                schema.col(name="type"),
                schema.col(name="name"),
                schema.col(name="sql"),
            ),
        )
        .where(
            predicate=schema.col(name="sql").is_not(value=Literal(value=None)),
        )
        .order_by(values=(schema.col(name="type"), schema.col(name="name"))),
    ).fetchall()
    guarded.extend(
        (
            path,
            0,
            f"{schema_row['type']} {schema_row['name']}",
            "SQLite schema reference",
        )
        for schema_row in schema_rows
        if context.rules.names.search(string=str(object=schema_row["sql"]))
        is not None
    )


def _sqlite_row_locator(
    *,
    connection: Connection,
    table: str,
    columns: list[Row],
) -> tuple[tuple[str, ...], str | None]:
    """Choose the columns that identify one row of a table.

    Args:
        connection: Open database connection.
        table: Table name.
        columns: ``PRAGMA table_xinfo`` rows of the table.

    Returns:
        The locator columns (empty when no stable locator exists) and the
        rowid alias used, if any.

    """
    names: tuple[str, ...] = tuple(str(object=row[1]) for row in columns)
    primary: tuple[str, ...] = tuple(
        str(object=row[1])
        for row in sorted(columns, key=lambda item: int(item[5]))
        if int(row[5]) > 0
    )
    schema: Table = Table(name="sqlite_schema")
    table_sql_row: tuple[Cell, ...] | None = execute_sql(
        connection=connection,
        statement=schema.select(columns=(schema.col(name="sql"),)).where(
            predicate=schema.col(name="type")
            .eq(value=Literal(value="table"))
            .and_(other=schema.col(name="name").eq(value=Param())),
        ),
        parameters=(table,),
    ).fetchone()
    table_sql: str = (
        "" if table_sql_row is None else str(object=table_sql_row[0])
    )
    rowid_alias: str | None = next(
        (alias for alias in ("rowid", "_rowid_", "oid") if alias not in names),
        None,
    )
    if "WITHOUT ROWID" in table_sql.upper() or rowid_alias is None:
        return (primary, rowid_alias)
    return ((rowid_alias,), rowid_alias)


def _sqlite_table_cell_edits(
    *,
    connection: Connection,
    path: Path,
    table: str,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> list[SqliteCellEdit]:
    """Plan safe TEXT-cell replacements in one table.

    Args:
        connection: Value for ``connection``.
        path: Value for ``path``.
        table: Value for ``table``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    _sql_identifier(value=table)
    columns: list[Row] = execute_sql(
        connection=connection,
        statement=pragma(name="table_xinfo", call=Identifier(value=table)),
    ).fetchall()
    names: tuple[str, ...] = tuple(str(object=row[1]) for row in columns)
    writable: tuple[str, ...] = tuple(
        str(object=row[1]) for row in columns if int(row[6]) == 0
    )
    locator_columns, rowid_alias = _sqlite_row_locator(
        connection=connection,
        table=table,
        columns=columns,
    )
    if not locator_columns:
        guarded.append(
            (path, 0, table, "SQLite table has no stable row locator"),
        )
        return []
    select_columns: tuple[str, ...] = locator_columns + tuple(
        name for name in names if name not in locator_columns
    )
    dynamic_table: Table = Table(name=table)
    selected: tuple[SelectableNode, ...] = tuple(
        dynamic_table.col(name=name).alias(name=name)
        if name == rowid_alias and name not in names
        else dynamic_table.col(name=name)
        for name in select_columns
    )
    rows: list[Row] = execute_sql(
        connection=connection,
        statement=dynamic_table.select(columns=selected),
    ).fetchall()
    edits: list[SqliteCellEdit] = []
    for data_row in rows:
        locator_values: tuple[Cell, ...] = tuple(
            data_row[name] for name in locator_columns
        )
        for column in writable:
            value: Cell = data_row[column]
            if not isinstance(value, str):
                continue
            rewritten, count, dotted_guarded = _rewrite_line(
                line=value,
                context=context,
                suffix=".txt",
                safe_dotted=(),
            )
            if dotted_guarded:
                guarded.append(
                    (path, 0, f"{table}.{column}", "SQLite dotted value"),
                )
            if count == 0 or rewritten == value:
                continue
            edits.append(
                SqliteCellEdit(
                    database=path,
                    table=table,
                    column=column,
                    locator_columns=locator_columns,
                    locator_values=locator_values,
                    before=value,
                    after=rewritten,
                ),
            )
    return edits


def _sqlite_plan(
    *,
    path: Path,
    context: _Context,
    guarded: list[tuple[Path, int, str, str]],
) -> list[SqliteCellEdit]:
    """Plan safe TEXT-cell replacements in one SQLite database.

    Args:
        path: Value for ``path``.
        context: Value for ``context``.
        guarded: Value for ``guarded``.

    Returns:
        The resulting value.

    """
    edits: list[SqliteCellEdit] = []
    uri: str = f"file:{path.as_posix()}?mode=ro"
    try:
        with closing(thing=connect(database=uri, uri=True)) as connection:
            connection.row_factory = Row
            _sqlite_schema_references(
                connection=connection,
                path=path,
                context=context,
                guarded=guarded,
            )
            for table in _sqlite_tables(connection=connection):
                edits.extend(
                    _sqlite_table_cell_edits(
                        connection=connection,
                        path=path,
                        table=table,
                        context=context,
                        guarded=guarded,
                    ),
                )
    except (DatabaseError, SQLiteLayerError) as exc:
        guarded.append((path, 0, path.name, f"SQLite read failed: {exc}"))
    return edits


def _sqlite_recreate_named_object(
    *,
    connection: Connection,
    edit: SqliteSchemaEdit,
) -> None:
    """Rename an index, trigger, or view without rewriting its SQL body.

    Args:
        connection: Value for ``connection``.
        edit: Value for ``edit``.

    Raises:
        RenameError: When the operation cannot complete.

    """
    schema: Table = Table(name="sqlite_schema")
    row: tuple[Cell, ...] | None = execute_sql(
        connection=connection,
        statement=schema.select(columns=(schema.col(name="sql"),)).where(
            predicate=schema.col(name="type")
            .eq(value=Param())
            .and_(other=schema.col(name="name").eq(value=Param())),
        ),
        parameters=(edit.kind, edit.old),
    ).fetchone()
    if row is None or row[0] is None:
        msg: str = f"SQLite {edit.kind} disappeared: {edit.old}"
        raise RenameError(msg)
    sql: str = str(object=row[0])
    keyword: str = edit.kind.upper()
    pattern: Pattern[str] = compile_pattern(
        pattern=(
            f"^(CREATE\\s+(?:UNIQUE\\s+)?"
            f"{keyword}"
            f'\\s+)(?:\\"'
            f"{escape(pattern=edit.old)}"
            f'\\"|`'
            f"{escape(pattern=edit.old)}"
            f"`|\\["
            f"{escape(pattern=edit.old)}"
            f"\\]|"
            f"{escape(pattern=edit.old)}"
            f")(?=\\s)"
        ),
        flags=IGNORECASE,
    )
    rewritten, count = pattern.subn(
        repl=f"\\1{_sql_identifier(value=edit.new)}",
        string=sql,
        count=1,
    )
    if count != 1:
        msg = f"Unable to isolate SQLite {edit.kind} name: {edit.old}"
        raise RenameError(msg)
    execute_sql(
        connection=connection,
        statement=drop(kind=keyword, name=edit.old),
    )
    execute_sql(
        connection=connection,
        statement=RawSql.from_external_schema(value=rewritten),
    )


def _sqlite_apply_cell_edits(
    *,
    connection: Connection,
    edits: list[SqliteCellEdit],
) -> None:
    """Update planned cells, requiring each to hit exactly one row.

    Args:
        connection: Value for ``connection``.
        edits: Value for ``edits``.

    """
    for edit in edits:
        dynamic_table: Table = Table(name=edit.table)
        predicates: tuple[PredicateNode, ...] = tuple(
            dynamic_table.col(name=name).is_(value=Param())
            for name in edit.locator_columns
        )
        predicate: PredicateNode = predicates[0]
        for additional in predicates[1:]:
            predicate = predicate.and_(other=additional)
        cursor: Cursor = execute_sql(
            connection=connection,
            statement=dynamic_table.update(
                values=((dynamic_table.col(name=edit.column), Param()),),
            ).where(predicate=predicate),
            parameters=(edit.after, *edit.locator_values),
        )
        _require_single_row(edit=edit, changed=cursor.rowcount)


def _require_single_row(*, edit: SqliteCellEdit, changed: int) -> None:
    """Require that an update touched exactly one row.

    Args:
        edit: The planned cell edit.
        changed: Rows the statement reported as changed.

    Raises:
        RenameError: When the row identity no longer matches.

    """
    if changed != 1:
        msg: str = (
            f"SQLite row identity changed for "
            f"{edit.table}.{edit.column}: expected 1 row, got {changed}"
        )
        raise RenameError(msg)


def _sqlite_apply_schema_edits(
    *,
    connection: Connection,
    schema_edits: list[SqliteSchemaEdit],
) -> None:
    """Apply table, column, index, trigger, and view renames in order.

    Args:
        connection: Value for ``connection``.
        schema_edits: Value for ``schema_edits``.

    """
    execute_sql(
        connection=connection,
        statement=pragma(
            name="legacy_alter_table",
            value=Literal(value=False),
        ),
    )
    table_names: dict[str, str] = {}
    structural: tuple[SqliteSchemaEdit, ...] = tuple(
        edit for edit in schema_edits if edit.kind in {"table", "column"}
    )
    named_objects: tuple[SqliteSchemaEdit, ...] = tuple(
        edit
        for edit in schema_edits
        if edit.kind in {"index", "trigger", "view"}
    )
    for schema_edit in structural:
        current_table: str = table_names.get(
            schema_edit.table,
            schema_edit.table,
        )
        if schema_edit.kind == "column":
            execute_sql(
                connection=connection,
                statement=alter_rename_column(
                    table=current_table,
                    old=schema_edit.old,
                    new=schema_edit.new,
                ),
            )
            continue
        execute_sql(
            connection=connection,
            statement=alter_rename_table(
                table=current_table,
                new=schema_edit.new,
            ),
        )
        table_names[schema_edit.table] = schema_edit.new
    for schema_edit in named_objects:
        _sqlite_recreate_named_object(connection=connection, edit=schema_edit)


def _sqlite_verify(*, connection: Connection) -> None:
    """Verify foreign keys and integrity after the edits.

    Args:
        connection: Open connection inside the edit transaction.

    Raises:
        RenameError: When either check fails.

    """
    if execute_sql(
        connection=connection,
        statement=pragma(name="foreign_key_check"),
    ).fetchall():
        msg: str = "SQLite foreign_key_check failed"
        raise RenameError(msg)
    integrity: tuple[Cell, ...] | None = execute_sql(
        connection=connection,
        statement=pragma(name="integrity_check"),
    ).fetchone()
    if integrity is None or str(object=integrity[0]).lower() != "ok":
        msg = "SQLite integrity_check failed"
        raise RenameError(msg)


def _sqlite_apply_group(
    *,
    database: Path,
    edits: list[SqliteCellEdit],
    schema_edits: list[SqliteSchemaEdit],
) -> None:
    """Apply planned SQLite cell changes atomically and validate the DB.

    Args:
        database: Value for ``database``.
        edits: Value for ``edits``.
        schema_edits: Value for ``schema_edits``.

    """
    connection: Connection = connect(database=database)
    try:
        execute_sql(
            connection=connection,
            statement=pragma(name="foreign_keys", value=Literal(value=True)),
        )
        execute_sql(
            connection=connection,
            statement=command(name="begin_immediate"),
        )
        _sqlite_apply_cell_edits(connection=connection, edits=edits)
        _sqlite_apply_schema_edits(
            connection=connection,
            schema_edits=schema_edits,
        )
        _sqlite_verify(connection=connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _plan_file(
    *,
    path: Path,
    context: _Context,
    leftovers: list[tuple[Path, int, str]],
    guarded: list[tuple[Path, int, str, str]],
) -> tuple[FileEdit | None, str | None]:
    """Plan the content rewrite of one file.

    Args:
        path: File to examine.
        context: Shared rewrite settings.
        leftovers: Collects unrecognized spellings found in this file.
        guarded: Collects dotted code occurrences deliberately not rewritten.

    Returns:
        The edit (or ``None``) and a reason when the file mentions the
        old name but cannot be rewritten.

    """
    data: bytes = path.read_bytes()
    mentions: bool = any(needle in data for needle in context.needles)
    skipped: str | None = None
    if len(data) > context.options.max_size:
        skipped = "too large"
    elif b"\x00" in data[:4096]:
        skipped = "binary"
    if skipped is not None:
        return (None, skipped if mentions else None)
    try:
        original: str = data.decode(encoding="utf-8")
    except UnicodeDecodeError:
        return (None, "not UTF-8" if mentions else None)
    out: list[str] = []
    total: int = 0
    suffix: str = path.suffix.lower()
    safe_dotted_by_line: dict[int, tuple[tuple[int, int], ...]] = (
        safe_dotted_spans(text=original, suffix=suffix)
        if context.options.dotted and suffix in Constants.dotted_guard_suffixes
        else {}
    )
    for index, line in enumerate(iterable=original.splitlines(keepends=True)):
        if index == 0 and line.startswith("#!"):
            out.append(line)
            continue
        rewritten, count, guarded_spans = _rewrite_line(
            line=line,
            context=context,
            suffix=suffix,
            safe_dotted=safe_dotted_by_line.get(index + 1, ()),
        )
        out.append(rewritten)
        total += count
        guarded.extend(
            (path, index + 1, line.strip()[:100], "dotted code reference")
            for _span in guarded_spans
        )
    result: str = "".join(out)
    leftovers.extend(_leftovers(path=path, text=result, context=context))
    if result == original:
        return (None, None)
    if not structurally_valid_rewrite(text=result, suffix=suffix):
        return (None, "rewrite failed structural validation")
    edit: FileEdit = FileEdit(
        path=path,
        before=data,
        after=result.encode(encoding="utf-8"),
        matches=total,
    )
    return (edit, None)


def _path_renames(
    *,
    files: list[Path],
    root: Path,
    rules: RenameRules,
) -> list[tuple[Path, Path]]:
    """Plan file and directory renames, deepest first.

    Args:
        files: Selected files.
        root: Project root.
        rules: Old-name matcher, styles, and new-name words.

    Returns:
        ``(source, destination)`` pairs ready to apply in order.

    """
    paths: set[Path] = set()
    for file in files:
        paths.add(file)
        paths.update(
            parent
            for parent in file.parents
            if parent != root and root in parent.parents
        )
    renames: list[tuple[Path, Path]] = []
    for path in sorted(
        paths,
        key=lambda item: (-len(item.parts), str(object=item)),
    ):
        restyled: str = _restyle_name(name=path.name, rules=rules)
        if restyled != path.name:
            renames.append((path, path.with_name(name=restyled)))
    return renames


def _check_collisions(
    *,
    renames: list[tuple[Path, Path]],
    root_target: Path | None,
    root: Path,
) -> None:
    """Refuse renames whose destinations clash.

    Args:
        renames: Planned file and directory renames.
        root_target: New root directory, if any.
        root: Project root.

    Raises:
        RenameError: Naming every clashing destination.

    """
    sources: set[Path] = {source for source, _ in renames}
    seen: dict[Path, Path] = {}
    problems: list[str] = []
    for source, destination in renames:
        previous: Path | None = seen.get(destination)
        if previous is not None:
            problems.append(
                f"{previous} and {source} both become {destination}",
            )
        seen[destination] = source
        case_only: bool = (
            destination.name.lower() == source.name.lower()
            and destination.parent == source.parent
        )
        if (
            destination.exists()
            and destination not in sources
            and (not case_only)
        ):
            problems.append(f"{destination} already exists")
    if (
        root_target is not None
        and root_target.exists()
        and (root_target.name.lower() != root.name.lower())
    ):
        problems.append(f"{root_target} already exists")
    if problems:
        msg: str = "rename would collide:\n  " + "\n  ".join(problems)
        raise RenameError(msg)


def _gh(*, arguments: list[str]) -> CompletedProcess[bytes]:
    """Run the GitHub CLI.

    Args:
        arguments: Arguments after ``gh``.

    Returns:
        The completed process.

    """
    return run(args=["gh", *arguments], capture_output=True, check=True)


def _remote_url(*, root: Path, remote: str) -> str:
    """Read a git remote's URL.

    Args:
        root: Repository working tree.
        remote: Remote name.

    Returns:
        The configured URL.

    Raises:
        RenameError: When git or the remote is unavailable.

    """
    try:
        result: CompletedProcess[bytes] = run(
            args=["git", "-C", str(object=root), "remote", "get-url", remote],
            capture_output=True,
            check=True,
        )
    except (OSError, CalledProcessError, DatabaseError, RenameError) as exc:
        msg: str = f"no git remote named {remote!r} in {root}"
        raise RenameError(msg) from exc
    return result.stdout.decode(encoding="utf-8").strip()


def _require_github_cli() -> None:
    """Check that the GitHub CLI is installed and signed in.

    Raises:
        RenameError: When ``gh`` cannot act on the user's behalf.

    """
    try:
        _ = _gh(arguments=["auth", "status"])
    except (OSError, CalledProcessError, DatabaseError, RenameError) as exc:
        msg: str = (
            "renaming the repository needs the GitHub CLI: gh auth login"
        )
        raise RenameError(msg) from exc


def _plan_remote(
    *,
    root: Path,
    options: Options,
    rules: RenameRules,
) -> tuple[RemoteRename | None, RemoteRename | None]:
    """Find the GitHub repository behind the remote and plan its rename.

    The repository name is restyled exactly like every other reference,
    so URLs rewritten inside files keep pointing at the renamed repository.

    With ``--github`` problems are errors. Without it the repository is
    only discovered, quietly, so the user can be asked about it.

    Args:
        root: Project root before the rename.
        options: Rename options.
        rules: Old-name matcher, styles, and new-name words.

    Returns:
        ``(confirmed, candidate)``: the rename to perform, and a discovered
        one awaiting the user's answer. At most one is set.

    Raises:
        RenameError: With ``--github``, when the remote is not a GitHub
            repository whose name carries the old name, or ``gh`` is
            missing or not signed in.

    """
    if options.github is False:
        return (None, None)
    strict: bool = options.github is True
    try:
        url: str = _remote_url(root=root, remote=options.remote)
    except RenameError:
        if strict:
            raise
        return (None, None)
    parts: Match[str] | None = Constants.github_url.fullmatch(string=url)
    if parts is None:
        if strict:
            msg: str = (
                f"remote {options.remote!r} is not a github.com URL: {url}"
            )
            raise RenameError(msg)
        return (None, None)
    old: str = parts["repo"]
    new: str = _restyle_name(name=old, rules=rules)
    if new == old:
        if strict:
            msg = f"repository name {old!r} does not contain the old name"
            raise RenameError(msg)
        return (None, None)
    change: RemoteRename = RemoteRename(
        remote=options.remote,
        owner=parts["owner"],
        old=old,
        new=new,
        old_url=url,
        new_url=f"{parts['head']}{parts['owner']}/{new}{parts['tail'] or ''}",
    )
    if not strict:
        return (None, change)
    _require_github_cli()
    return (change, None)


def _rename_repository(*, change: RemoteRename, undo: bool) -> None:
    """Rename the GitHub repository with the GitHub CLI.

    Args:
        change: The planned rename.
        undo: Reverse the rename instead of performing it.

    """
    source, target = (
        (change.new, change.old) if undo else (change.old, change.new)
    )
    _ = _gh(
        arguments=[
            "repo",
            "rename",
            target,
            "--repo",
            f"{change.owner}/{source}",
            "--yes",
        ],
    )


def _repoint_remote(
    *,
    change: RemoteRename,
    directory: Path,
    undo: bool,
) -> None:
    """Point the git remote at the new (or, when undoing, old) URL.

    Args:
        change: The planned rename.
        directory: Working tree whose remote URL is updated.
        undo: Restore the original URL.

    """
    _ = run(
        args=[
            "git",
            "-C",
            str(object=directory),
            "remote",
            "set-url",
            change.remote,
            change.old_url if undo else change.new_url,
        ],
        capture_output=True,
        check=True,
    )


def _abbreviations(
    *,
    options: Options,
    words: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    """Validate abbreviations and fill in default replacements.

    A bare abbreviation maps to the new name's initials in the same case
    (``AT`` becomes ``FB``, ``at`` becomes ``fb``, ``At`` becomes ``Fb``).

    Args:
        options: Rename options.
        words: Words of the new name.

    Returns:
        ``(old, new)`` pairs ready for the matcher.

    Raises:
        RenameError: On an empty, non-alphanumeric, or risky abbreviation.

    """
    initials: str = "".join(word[0] for word in words)
    pairs: list[tuple[str, str]] = []
    for short, replacement in options.abbreviations:
        if not short.isalnum():
            msg: str = f"abbreviation {short!r} must be letters and digits"
            raise RenameError(msg)
        if (
            short.islower()
            and len(short) <= Constants.short_limit
            and (not options.allow_short_lowercase)
        ):
            msg = (
                f"abbreviation "
                f"{short!r}"
                f" is a lowercase word or suffix (think 'look at', 'starte"
                f"d_at'); pass --allow-short-lowercase to rename it anyway"
            )
            raise RenameError(msg)
        if replacement:
            pairs.append((short, replacement))
        elif short.isupper():
            pairs.append((short, initials.upper()))
        elif short.islower():
            pairs.append((short, initials.lower()))
        else:
            pairs.append((short, initials.capitalize()))
    return tuple(pairs)


@dataclass(slots=True)
class _WebSymbols:
    """Collect HTML definitions and CSS/JavaScript references of web symbols.

    Attributes:
        rules: Active project-name matching rules.
        definitions: ``id``/``class`` symbols and the files defining them.
        references: Symbols used by CSS or JavaScript and their files.

    """

    rules: RenameRules
    definitions: dict[str, set[Path]] = field(default_factory=dict)
    references: dict[str, set[Path]] = field(default_factory=dict)

    def scan(self, *, path: Path) -> None:
        """Scan one file when it is a readable web source.

        Args:
            path: Candidate project file.

        """
        suffix: str = path.suffix.lower()
        if path.is_symlink() or suffix not in Constants.web_suffixes:
            return
        try:
            text: str = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        if suffix == ".html":
            self._scan_html(path=path, text=text)
        elif suffix == ".css":
            self._scan_css(path=path, text=text)
        else:
            self._scan_javascript(path=path, text=text)

    def graph(self) -> list[tuple[str, int, int]]:
        """Return symbols having both a definition and a reference.

        Returns:
            ``(symbol, definition count, reference count)``, sorted by symbol.

        """
        return sorted(
            (
                (symbol, len(paths), len(self.references[symbol]))
                for symbol, paths in self.definitions.items()
                if symbol in self.references
            ),
            key=lambda item: item[0],
        )

    def _record(
        self,
        *,
        target: dict[str, set[Path]],
        symbol: str,
        path: Path,
    ) -> None:
        """Record one relevant web symbol.

        Args:
            target: Definition or reference table.
            symbol: DOM/CSS symbol without ``.``/``#`` prefix.
            path: File containing it.

        """
        if symbol and self.rules.names.search(string=symbol) is not None:
            target.setdefault(symbol, set()).add(path)

    def _scan_html(self, *, path: Path, text: str) -> None:
        """Record ``id`` and ``class`` definitions of an HTML file.

        Args:
            path: Value for ``path``.
            text: Value for ``text``.

        """
        for match in Constants.web_attribute.finditer(string=text):
            values: tuple[str, ...] = (
                tuple(match.group("value").split())
                if match.group("name").lower() == "class"
                else (match.group("value"),)
            )
            for symbol in values:
                self._record(target=self.definitions, symbol=symbol, path=path)

    def _scan_css(self, *, path: Path, text: str) -> None:
        """Record selector references of a stylesheet.

        Args:
            path: Value for ``path``.
            text: Value for ``text``.

        """
        for match in Constants.css_symbol.finditer(string=text):
            self._record(
                target=self.references,
                symbol=match.group("name"),
                path=path,
            )

    def _scan_javascript(self, *, path: Path, text: str) -> None:
        """Record DOM id, class, and selector references of a script.

        Args:
            path: Value for ``path``.
            text: Value for ``text``.

        """
        for pattern in (Constants.js_id, Constants.js_class):
            for match in pattern.finditer(string=text):
                self._record(
                    target=self.references,
                    symbol=match.group("name"),
                    path=path,
                )
        for match in Constants.js_selector.finditer(string=text):
            for symbol_match in Constants.css_symbol.finditer(
                string=match.group("selector"),
            ):
                self._record(
                    target=self.references,
                    symbol=symbol_match.group("name"),
                    path=path,
                )


def _web_symbol_graph(
    *,
    files: list[Path],
    rules: RenameRules,
) -> list[tuple[str, int, int]]:
    """Build a lightweight HTML/CSS/JS cross-reference graph.

    The graph correlates HTML ``id``/``class`` definitions with CSS selectors
    and JavaScript DOM references. Only symbols containing a spelling matched
    by the rename rules are retained. This is intentionally a verification
    layer, not permission to rewrite arbitrary strings: syntax-specific
    classifiers still decide whether each occurrence is safe.

    Args:
        files: Selected project files.
        rules: Active project-name matching rules.

    Returns:
        ``(symbol, definition count, reference count)`` entries that have both
        a definition and at least one cross-file/syntax reference.

    """
    symbols: _WebSymbols = _WebSymbols(rules=rules)
    for path in files:
        symbols.scan(path=path)
    return symbols.graph()


def _application_sql_references(
    *,
    files: list[Path],
    schema_edits: list[SqliteSchemaEdit],
) -> list[SqlApplicationReference]:
    """Find static SQL-looking references to planned SQLite schema names.

    Args:
        files: Value for ``files``.
        schema_edits: Value for ``schema_edits``.

    Returns:
        The resulting value.

    """
    references: list[SqlApplicationReference] = []
    suffixes: frozenset[str] = frozenset(
        (".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".sql"),
    )
    keywords: Pattern[str] = compile_pattern(
        pattern=(
            "\\b(?:SELECT|FROM|JOIN|UPDATE|INSERT|INTO|DELETE|CREATE|ALTER|DRO"
            "P)\\b"
        ),
        flags=IGNORECASE,
    )
    symbols: tuple[tuple[str, str], ...] = tuple(
        dict.fromkeys((edit.old, edit.kind) for edit in schema_edits),
    )
    if not symbols:
        return references
    for path in files:
        if path.suffix.lower() not in suffixes or not path.is_file():
            continue
        try:
            text: str = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(iterable=text.splitlines(), start=1):
            if keywords.search(string=line) is None:
                continue
            for symbol, kind in symbols:
                boundary: Pattern[str] = compile_pattern(
                    pattern=(
                        f"(?<![A-Za-z0-9_])"
                        f"{escape(pattern=symbol)}"
                        f"(?![A-Za-z0-9_])"
                    ),
                )
                if boundary.search(string=line) is not None:
                    references.append(
                        SqlApplicationReference(
                            path=path,
                            line=number,
                            symbol=symbol,
                            kind=kind,
                        ),
                    )
    return references


def build_plan(*, root: Path, options: Options) -> Plan:
    """Compute every change without touching the disk.

    Args:
        root: Project root.
        options: Rename options.

    Returns:
        The complete plan.

    Raises:
        RenameError: On an invalid name or a destination collision.

    """
    new_words: tuple[str, ...] = _words(name=options.new_name)
    if (
        not new_words
        or Constants.valid_name.fullmatch(string=options.new_name) is None
    ):
        msg: str = (
            f"invalid project name "
            f"{options.new_name!r}"
            f": use letters, digits, '_', '-', '.' or spaces, starting wit"
            f"h a letter"
        )
        raise RenameError(msg)
    detected: list[str] = [root.name]
    declared: str | None = _project_name(root=root)
    if declared is not None:
        detected.append(declared)
    old_names: tuple[str, ...] = tuple(
        dict.fromkeys((*detected, *options.old_names)),
    )
    if all(_words(name=name) == new_words for name in old_names):
        msg = "the new name equals the current name; nothing to do"
        raise RenameError(msg)
    abbreviations: tuple[tuple[str, str], ...] = _abbreviations(
        options=options,
        words=new_words,
    )
    pattern, styles = _name_matcher(
        names=old_names,
        boundary=options.boundary,
        abbreviations=abbreviations,
        dotted=options.dotted,
    )
    rules: RenameRules = RenameRules(
        names=pattern,
        styles=styles,
        words=new_words,
    )
    target: Path | None = (
        root.with_name(name=options.new_name)
        if options.rename_root and root.name != options.new_name
        else None
    )
    context: _Context = _Context(
        rules=rules,
        prefixes=tuple(
            dict.fromkeys(
                str(object=root.with_name(name=name))
                for name in (root.name, options.new_name)
            ),
        ),
        needles=frozenset(name.encode() for name in old_names),
        options=options,
        leftover=_leftover_pattern(names=old_names),
        roots=(root, root / "src"),
    )
    files: list[Path] = _select(root=root, options=options)
    plan: Plan = Plan(root=root, root_target=target)
    plan.web_links = _web_symbol_graph(files=files, rules=rules)
    for path in files:
        if path.is_symlink():
            continue
        if options.sqlite and _is_sqlite(path=path):
            plan.sqlite_edits.extend(
                _sqlite_plan(path=path, context=context, guarded=plan.guarded),
            )
            if options.sqlite_schema:
                plan.sqlite_schema_edits.extend(
                    _sqlite_schema_plan(
                        path=path,
                        context=context,
                        guarded=plan.guarded,
                    ),
                )
            continue
        edit, reason = _plan_file(
            path=path,
            context=context,
            leftovers=plan.leftovers,
            guarded=plan.guarded,
        )
        if edit is not None:
            plan.edits.append(edit)
        if reason is not None:
            plan.skipped.append((path, reason))
    plan.sql_references = _application_sql_references(
        files=files,
        schema_edits=plan.sqlite_schema_edits,
    )
    plan.remote, plan.candidate = _plan_remote(
        root=root,
        options=options,
        rules=rules,
    )
    plan.renames = _path_renames(files=files, root=root, rules=rules)
    _check_collisions(renames=plan.renames, root_target=target, root=root)
    return plan


def _write_atomic(*, path: Path, data: bytes) -> None:
    """Replace a file's content atomically, keeping its mode.

    Args:
        path: File to replace.
        data: New content.

    """
    temporary: Path = path.with_name(name=f".{path.name}.rename-tmp")
    _ = temporary.write_bytes(data=data)
    copymode(src=path, dst=temporary)
    _ = temporary.replace(target=path)


def move(*, source: Path, destination: Path) -> None:
    """Rename a path, handling case-only changes on case-folding disks.

    Args:
        source: Existing path.
        destination: New path.

    """
    if (
        source.name.lower() == destination.name.lower()
        and source.parent == destination.parent
    ):
        staging: Path = source.with_name(name=f".{source.name}.rename-tmp")
        _ = source.rename(target=staging)
        _ = staging.rename(target=destination)
        return
    _ = source.rename(target=destination)


def _sqlite_backup(*, database: Path) -> Path:
    """Copy a SQLite database to a temporary file before it is edited.

    Args:
        database: Database to back up.

    Returns:
        The backup file.

    """
    with NamedTemporaryFile(
        prefix="rename-project-sqlite-",
        suffix=".sqlite",
        delete=False,
    ) as temporary:
        backup_path: Path = Path(temporary.name)
    with (
        closing(thing=connect(database=database)) as source,
        closing(thing=connect(database=backup_path)) as target,
    ):
        source.backup(target=target)
    return backup_path


def _sqlite_restore(*, database: Path, backup: Path) -> None:
    """Copy a backup over a SQLite database.

    Args:
        database: Database to restore.
        backup: Backup made by ``_sqlite_backup``.

    """
    with (
        closing(thing=connect(database=backup)) as source,
        closing(thing=connect(database=database)) as target,
    ):
        source.backup(target=target)


def _sqlite_groups(
    *,
    plan: Plan,
) -> dict[Path, tuple[list[SqliteCellEdit], list[SqliteSchemaEdit]]]:
    """Group SQLite cell and schema edits by database.

    Args:
        plan: Plan from ``build_plan``.

    Returns:
        Each database mapped to its cell edits and schema edits.

    """
    groups: dict[
        Path,
        tuple[list[SqliteCellEdit], list[SqliteSchemaEdit]],
    ] = {}
    for cell_edit in plan.sqlite_edits:
        groups.setdefault(cell_edit.database, ([], []))[0].append(cell_edit)
    for schema_edit in plan.sqlite_schema_edits:
        groups.setdefault(schema_edit.database, ([], []))[1].append(
            schema_edit,
        )
    return groups


@dataclass(slots=True)
class _Transaction:
    """Track every applied step of a plan so a failure can undo it.

    Attributes:
        plan: The plan being applied.
        written: File edits already written.
        moved: Renames already performed.
        sqlite_backups: ``(database, backup)`` pairs made before editing.
        renamed_repository: Whether the GitHub repository was renamed.
        repointed: Whether the git remote was repointed.

    """

    plan: Plan
    written: list[FileEdit] = field(default_factory=list)
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    sqlite_backups: list[tuple[Path, Path]] = field(default_factory=list)
    renamed_repository: bool = False
    repointed: bool = False

    @property
    def final(self) -> Path:
        """The project root after the rename.

        Returns:
            The resulting value.

        """
        return self.plan.root_target or self.plan.root

    def write_files(self) -> None:
        """Write every planned text-file rewrite."""
        for edit in self.plan.edits:
            _write_atomic(path=edit.path, data=edit.after)
            self.written.append(edit)

    def apply_sqlite(self) -> None:
        """Back up and edit every planned SQLite database."""
        for database, (cells, schema) in sorted(
            _sqlite_groups(plan=self.plan).items(),
        ):
            self.sqlite_backups.append(
                (database, _sqlite_backup(database=database)),
            )
            _sqlite_apply_group(
                database=database,
                edits=cells,
                schema_edits=schema,
            )
        for schema_edit in self.plan.sqlite_schema_edits:
            shown: Path = schema_edit.database.relative_to(self.plan.root)
            _ = stdout.write(
                f"{_paint(code='36', text='sqlite-schema:')} {shown} {
                    schema_edit.kind
                } {schema_edit.old!r} -> {schema_edit.new!r}\n",
            )

    def rename_paths(self) -> None:
        """Rename files, directories, and finally the project root."""
        steps: list[tuple[Path, Path]] = list(self.plan.renames)
        if self.plan.root_target is not None:
            steps.append((self.plan.root, self.plan.root_target))
        for source, destination in steps:
            move(source=source, destination=destination)
            self.moved.append((source, destination))

    def rename_remote(self) -> None:
        """Rename the GitHub repository and repoint the remote."""
        if self.plan.remote is None:
            return
        _rename_repository(change=self.plan.remote, undo=False)
        self.renamed_repository = True
        _repoint_remote(
            change=self.plan.remote,
            directory=self.final,
            undo=False,
        )
        self.repointed = True

    def rollback(self) -> None:
        """Undo every step that was applied, newest first."""
        remote: RemoteRename | None = self.plan.remote
        if remote is not None and self.repointed:
            _repoint_remote(change=remote, directory=self.final, undo=True)
        if remote is not None and self.renamed_repository:
            _rename_repository(change=remote, undo=True)
        for source, destination in reversed(self.moved):
            move(source=destination, destination=source)
        for database, backup in self.sqlite_backups:
            _sqlite_restore(database=database, backup=backup)
        for edit in self.written:
            _write_atomic(path=edit.path, data=edit.before)

    def discard_backups(self) -> None:
        """Delete the temporary SQLite backups."""
        for _database, backup in self.sqlite_backups:
            backup.unlink(missing_ok=True)


def apply_plan(*, plan: Plan) -> None:
    """Apply a plan as one transaction, rolling back on failure.

    Args:
        plan: Plan from ``build_plan``.

    Raises:
        RenameError: When an operation failed; everything done so far has
            been undone.

    """
    transaction: _Transaction = _Transaction(plan=plan)
    try:
        transaction.write_files()
        transaction.apply_sqlite()
        transaction.rename_paths()
        transaction.rename_remote()
    except (
        OSError,
        CalledProcessError,
        DatabaseError,
        SQLiteLayerError,
        RenameError,
    ) as exc:
        transaction.rollback()
        transaction.discard_backups()
        msg: str = f"rename failed and was rolled back: {exc}"
        raise RenameError(msg) from exc
    transaction.discard_backups()


def _identifier(*, text: str) -> bool:
    """Report whether ``text`` can name a Python module.

    Args:
        text: Candidate module name.

    Returns:
        ``True`` for a non-keyword identifier.

    """
    return text.isidentifier() and (not iskeyword(text))


def _report_github(*, plan: Plan) -> None:
    """Print the GitHub part of the plan.

    Args:
        plan: Plan to describe.

    """
    if plan.remote is not None:
        change: RemoteRename = plan.remote
        _ = stdout.write(
            f"{_paint(code='35', text='github: ')} {change.owner}/{
                change.old
            } -> {change.owner}/{change.new} (remote {change.remote!r} -> {
                change.new_url
            })\n",
        )
    elif plan.candidate is not None:
        found: RemoteRename = plan.candidate
        _ = stdout.write(
            f"{_paint(code='35', text='github: ')} found {found.owner}/{
                found.old
            }; you will be asked whether to rename "
            f"it to {found.owner}/{found.new}\n",
        )


def _report_rewrites(*, plan: Plan, diff: bool) -> None:
    """Print file and SQLite rewrites, with diffs when asked.

    Args:
        plan: Plan to describe.
        diff: Print unified diffs of every rewrite.

    """
    for edit in plan.edits:
        shown: Path = edit.path.relative_to(plan.root)
        _ = stdout.write(
            f"{_paint(code='32', text='rewrite:')} {shown} {
                _paint(code='2', text=f'({edit.matches})')
            }\n",
        )
        if diff:
            stdout.writelines(
                unified_diff(
                    a=edit.before.decode().splitlines(keepends=True),
                    b=edit.after.decode().splitlines(keepends=True),
                    fromfile=f"a/{shown}",
                    tofile=f"b/{shown}",
                ),
            )
    for sqlite_edit in plan.sqlite_edits:
        shown_db: Path = sqlite_edit.database.relative_to(plan.root)
        _ = stdout.write(
            f"{_paint(code='32', text='sqlite: ')} {shown_db} {
                sqlite_edit.table
            }.{sqlite_edit.column}: {sqlite_edit.before!r} -> {
                sqlite_edit.after!r
            }\n",
        )


def _report_renames(*, plan: Plan) -> None:
    """Print file, directory, and root renames.

    Args:
        plan: Plan to describe.

    """
    for source, destination in plan.renames:
        _ = stdout.write(
            f"{_paint(code='36', text='rename: ')} {
                source.relative_to(plan.root)
            } -> {destination.name}\n",
        )
    if plan.root_target is not None:
        _ = stdout.write(
            f"{_paint(code='36', text='rename: ')} {plan.root} -> {
                plan.root_target
            }\n",
        )


def _report_findings(*, plan: Plan) -> None:
    """Print skipped files and cross-reference findings.

    Args:
        plan: Plan to describe.

    """
    for path, reason in plan.skipped:
        _ = stdout.write(
            f"{_paint(code='33', text=f'skipped ({reason}):')} {
                path.relative_to(plan.root)
            }\n",
        )
    for symbol, definitions, references in plan.web_links:
        _ = stdout.write(
            f"{_paint(code='36', text='web-link:')} {symbol!r} ({
                definitions
            } HTML definition file(s), "
            f"{references} CSS/JS reference file(s))\n",
        )
    for reference in plan.sql_references:
        shown_sql: Path = reference.path.relative_to(plan.root)
        _ = stdout.write(
            f"{_paint(code='36', text='sql-ref:')} {shown_sql}:{
                reference.line
            } {reference.kind} {reference.symbol!r}\n",
        )


def _report_warnings(*, plan: Plan) -> None:
    """Print guarded occurrences and unrecognized spellings to stderr.

    Args:
        plan: Plan to describe.

    """
    for path, number, text, reason in plan.guarded:
        _ = stderr.write(
            f"{_paint(code='33', text='guarded:')} {reason} at {
                path.relative_to(plan.root)
            }:{number}: {text}\n",
        )
    for path, number, text in plan.leftovers:
        _ = stderr.write(
            f"{_paint(code='33', text='warning:')} unrecognized spelling at "
            f"{path.relative_to(plan.root)}:{number}: {text}\n",
        )


def _report(*, plan: Plan, options: Options, diff: bool, quiet: bool) -> None:
    """Print the plan.

    Args:
        plan: Plan to describe.
        options: Rename options.
        diff: Print unified diffs of every rewrite.
        quiet: Print only the summary line.

    """
    if not quiet:
        _report_rewrites(plan=plan, diff=diff)
        _report_renames(plan=plan)
        _report_findings(plan=plan)
        _report_github(plan=plan)
    _report_warnings(plan=plan)
    _ = stdout.write(
        f"{len(plan.edits)} file(s) rewritten, "
        f"{len(plan.sqlite_edits)} SQLite cell(s) rewritten, {
            len(plan.sqlite_schema_edits)
        } SQLite schema rename(s), {len(plan.renames)} renamed, {
            len(plan.skipped)
        } skipped, {len(plan.guarded)} guarded, {
            len(plan.leftovers)
        } unrecognized -> {options.new_name}\n",
    )
    module: str = _styled(words=_words(name=options.new_name), style="snake")
    if not _identifier(text=module):
        _ = stderr.write(
            f"warning: {module!r} is not a valid Python module name\n",
        )


def _parser() -> ArgumentParser:
    """Build the command-line parser.

    Returns:
        The configured parser.

    """
    parser: ArgumentParser = pretty_parser(
        prog="rename_project.py",
        description=(
            dedent(
                text=(
                    "    Rename a project: its root directory, the files a"
                    "nd folders\n    named after it, and its name inside t"
                    "ext files, restyled to\n    match how each occurrence"
                    " was written (snake_case, kebab-case,\n    PascalCase"
                    ", camelCase, SCREAMING_CASE, Title Case...).\n    Opt"
                    "ionally renames the GitHub repository too.\n    \n   "
                    " Every change is planned first, shown, confirmed, and"
                    " applied\n    as one transaction that is rolled back "
                    "on failure. Start with\n    --dry-run --diff."
                ),
            )
        ),
        epilog=(
            dedent(
                text=(
                    "    examples:\n      rename_project.py --name foo_bar"
                    " --dry-run --diff\n          preview every change wit"
                    "hout touching anything\n      rename_project.py --nam"
                    "e foo_bar --yes\n          apply without the confirma"
                    "tion question\n      rename_project.py --name foo_bar"
                    " --from exactus-tools --abbrev AT\n          also ren"
                    "ame an earlier name and its abbreviation\n      renam"
                    "e_project.py --name foo_bar --github\n          also "
                    "rename the GitHub repository (no question asked)\n   "
                    "   rename_project.py --name foo_bar --exclude '*.lock"
                    "' --boundary loose\n          skip lockfiles; rename "
                    "inside identifiers too\n    \n    exit status: 0 succ"
                    "ess or dry run; 1 refused, declined, or rolled back."
                    "\n    full guide: README_RENAME_PROJECT.md"
                ),
            )
        ),
    )
    _ = parser.add_argument(
        "root",
        nargs="?",
        help=(
            "repository root; located from the working directory, then "
            "the script's parent, when omitted"
        ),
    )
    naming: ArgumentParser = cast(
        typ="ArgumentParser",
        val=parser.add_argument_group(title="naming"),
    )
    _ = naming.add_argument(
        "--name",
        default=Constants.default_name,
        metavar="NAME",
        help=(
            "target project name in any casing; also the new root "
            "directory name (default: %(default)s)"
        ),
    )
    _ = naming.add_argument(
        "--from",
        "--alias",
        dest="old_names",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "extra old name to replace (repeatable); the root directory "
            "and pyproject [project] name are detected already"
        ),
    )
    _ = naming.add_argument(
        "--abbrev",
        action="append",
        default=[],
        metavar="OLD[=NEW]",
        help=(
            "also rename an exact, case-sensitive abbreviation, e.g. "
            "AT=FB; a bare AT becomes the new name's initials in the same "
            "case (repeatable, one per spelling)"
        ),
    )
    _ = naming.add_argument(
        "--allow-short-lowercase",
        action="store_true",
        help=(
            "allow lowercase abbreviations of up to three letters, which "
            "also match words like 'at' and suffixes like '_at'"
        ),
    )
    _ = naming.add_argument(
        "--dotted",
        action="store_true",
        help=(
            "also rename the dotted spelling (abc.cde); off by default "
            "because in code it is usually attribute access or an import "
            "path, such as obj.attr or package.module"
        ),
    )
    _ = naming.add_argument(
        "--dotted-code",
        action="store_true",
        help=(
            "also rewrite dotted spellings in executable code; high-risk "
            "override for intentional package/member renames; implies -"
            "-dotted"
        ),
    )
    _ = naming.add_argument(
        "--boundary",
        choices=sorted(Constants.boundaries),
        default="word",
        help=(
            "'word' matches a name only when it does not touch letters, digits"
            " or '_'; 'loose' also renames inside identifiers such as old_name"
            "_core (default: %(default)s)"
        ),
    )
    scope: ArgumentParser = cast(
        typ="ArgumentParser",
        val=parser.add_argument_group(title="scope"),
    )
    _ = scope.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="only touch paths matching GLOB (relative, POSIX); repeatable",
    )
    _ = scope.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="never touch paths matching GLOB; repeatable",
    )
    _ = scope.add_argument(
        "--no-git",
        action="store_true",
        help=(
            "walk the tree instead of using git ls-files (which honors .gitign"
            "ore)"
        ),
    )
    _ = scope.add_argument(
        "--no-rename-root",
        action="store_true",
        help="rewrite files but keep the root directory name",
    )
    _ = scope.add_argument(
        "--keep-absolute",
        action="store_true",
        help=(
            "leave absolute paths inside the project untouched instead of maki"
            "ng them relative"
        ),
    )
    _ = scope.add_argument(
        "--no-sqlite",
        action="store_true",
        help="do not inspect or update SQLite .db/.sqlite/.sqlite3 files",
    )
    _ = scope.add_argument(
        "--sqlite-schema",
        action="store_true",
        help="also rename SQLite table/column identifiers using ALTER TABLE",
    )
    _ = scope.add_argument(
        "--max-size",
        type=int,
        default=Constants.default_max_size,
        metavar="BYTES",
        help="skip files larger than this (default: %(default)s)",
    )
    github: ArgumentParser = cast(
        typ="ArgumentParser",
        val=parser.add_argument_group(title="github"),
    )
    _ = github.add_argument(
        "--github",
        dest="github",
        action="store_const",
        const=True,
        default=None,
        help=(
            "rename the GitHub repository behind the git remote with gh and re"
            "point the remote, without asking; rolled back if the local rename"
            " fails. Without a flag, a discovered repository is offered intera"
            "ctively"
        ),
    )
    _ = github.add_argument(
        "--no-github",
        dest="github",
        action="store_const",
        const=False,
        help="never rename or offer to rename the GitHub repository",
    )
    _ = github.add_argument(
        "--remote",
        default="origin",
        metavar="NAME",
        help="git remote used for GitHub (default: %(default)s)",
    )
    output: ArgumentParser = cast(
        typ="ArgumentParser",
        val=parser.add_argument_group(title="output and confirmation"),
    )
    _ = output.add_argument(
        "--dry-run",
        action="store_true",
        help="report changes without renaming or writing",
    )
    _ = output.add_argument(
        "--diff",
        action="store_true",
        help="show a unified diff of every rewrite",
    )
    _ = output.add_argument(
        "--quiet",
        action="store_true",
        help="print only the summary line",
    )
    _ = output.add_argument(
        "--yes",
        action="store_true",
        help=(
            "apply without the confirmation question; never renames a GitHub r"
            "epository by itself (use --github)"
        ),
    )
    return parser


def _options(*, args: Namespace) -> Options:
    """Translate parsed arguments into options.

    Args:
        args: Parsed command line.

    Returns:
        The rename options.

    """
    return Options(
        new_name=cast(typ="str", val=args.name),
        old_names=tuple(cast(typ="list[str]", val=args.old_names)),
        boundary=cast(typ="str", val=args.boundary),
        keep_absolute=cast(typ="bool", val=args.keep_absolute),
        rename_root=not cast(typ="bool", val=args.no_rename_root),
        use_git=not cast(typ="bool", val=args.no_git),
        includes=tuple(cast(typ="list[str]", val=args.include)),
        excludes=tuple(cast(typ="list[str]", val=args.exclude)),
        max_size=cast(typ="int", val=args.max_size),
        abbreviations=tuple(
            (
                (short, replacement)
                for short, _, replacement in (
                    item.partition("=")
                    for item in cast(typ="list[str]", val=args.abbrev)
                )
            ),
        ),
        allow_short_lowercase=cast(typ="bool", val=args.allow_short_lowercase),
        dotted=cast(typ="bool", val=args.dotted)
        or cast(typ="bool", val=args.dotted_code),
        dotted_code=cast(typ="bool", val=args.dotted_code),
        sqlite=not cast(typ="bool", val=args.no_sqlite),
        sqlite_schema=cast(typ="bool", val=args.sqlite_schema),
        github=cast(typ="bool | None", val=args.github),
        remote=cast(typ="str", val=args.remote),
    )


def ask(
    *,
    question: str,
    details: tuple[str, ...] = (),
    default: bool = False,
) -> bool:
    """Ask a yes/no question with an ANSI-styled prompt.

    Colors are used only on a terminal and are suppressed by ``NO_COLOR``.
    An empty answer takes ``default``; an unrecognized one asks again.

    Args:
        question: The question, shown in bold.
        details: Dimmed context lines under the question.
        default: Answer taken when the user just presses Enter.

    Returns:
        The user's answer; ``False`` when input ends.

    """
    mark: str = _paint(code="1;36", text="?")
    _ = stdout.write(f"\n{mark} {_paint(code='1', text=question)}\n")
    for detail in details:
        _ = stdout.write(f"  {_paint(code='2', text=detail)}\n")
    choices: str = "Y/n" if default else "y/N"
    hint: str = _paint(code="2", text=f"[{choices}]")
    for _attempt in range(Constants.ask_attempts):
        _ = stdout.write(f"  {_paint(code='1;36', text='>')} {hint} ")
        stdout.flush()
        answer: str = stdin.readline()
        if not answer:
            return False
        reply: str = answer.strip().lower()
        if not reply:
            return default
        if reply in {"y", "yes"}:
            return True
        if reply in {"n", "no"}:
            return False
        _ = stdout.write(
            f"  {_paint(code='33', text='Please answer y or n.')}\n",
        )
    return False


def _confirmed(*, assume_yes: bool, plan: Plan) -> bool:
    """Ask before changing anything, unless told not to.

    Args:
        assume_yes: ``--yes`` was given.
        plan: The plan about to be applied.

    Returns:
        Whether to apply the plan.

    Raises:
        RenameError: When confirmation is needed but input is not a
            terminal.

    """
    if assume_yes:
        return True
    if not stdin.isatty():
        msg: str = "refusing to change files without --yes (or use --dry-run)"
        raise RenameError(msg)
    return ask(
        question=(
            f"Apply {len(plan.edits)} file edit(s) and "
            f"{len(plan.renames) + (plan.root_target is not None)} rename(s)?"
        ),
        details=(f"project: {plan.root}",),
    )


def _offer_github(*, plan: Plan) -> None:
    """Ask whether to rename the GitHub repository found behind the remote.

    Never acts on its own: a discovered repository is renamed only after
    an explicit "yes" at the terminal, even with ``--yes``. Without a
    terminal the repository is left alone, with a hint to use ``--github``.

    Args:
        plan: Plan whose ``candidate`` may become its ``remote``.


    """
    change: RemoteRename | None = plan.candidate
    if change is None:
        return
    if not stdin.isatty():
        _ = stdout.write(
            f"{_paint(code='33', text='note:')}"
            f" GitHub repository "
            f"{change.owner}"
            f"/"
            f"{change.old}"
            f" left unchanged (pass --github to rename it non-interact"
            f"ively)\n",
        )
        return
    agreed: bool = ask(
        question=(
            f"Rename GitHub repository "
            f"{change.owner}/{change.old} to {change.owner}/{change.new}?"
        ),
        details=(
            f"remote {change.remote!r} will point at {change.new_url}",
            (
                "GitHub redirects the old URL; CI, webhooks and other clones m"
                "ust be updated."
            ),
        ),
    )
    if agreed:
        _require_github_cli()
        plan.remote = change


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Plan, show, and apply a project rename.

    Args:
        arguments: Command-line tokens, or ``None`` for ``sys.argv``.

    Returns:
        Process exit status: ``0`` on success or dry run, ``1`` when the
        rename was refused, declined, or rolled back.

    """
    args: Namespace = _parser().parse_args(
        args=None if arguments is None else list(arguments),
    )
    options: Options = _options(args=args)
    try:
        root: Path = _resolve_root(
            given=cast(typ="str | None", val=args.root),
            script=Path(__file__).resolve(),
        )
        plan: Plan = build_plan(root=root, options=options)
        _report(
            plan=plan,
            options=options,
            diff=cast(typ="bool", val=args.diff),
            quiet=cast(typ="bool", val=args.quiet),
        )
        if cast(typ="bool", val=args.dry_run):
            _ = stdout.write("dry run: nothing was changed\n")
            return 0
        if not _confirmed(
            assume_yes=cast(typ="bool", val=args.yes),
            plan=plan,
        ):
            _ = stdout.write("aborted: nothing was changed\n")
            return 1
        _offer_github(plan=plan)
        apply_plan(plan=plan)
    except RenameError as exc:
        _ = stderr.write(f"{_paint(code='1;31', text='error:')} {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
