# Copyright (c) 2026 João Lopes.
"""Reorder Python class methods while preserving original source text."""

from argparse import ArgumentParser, Namespace
from ast import (
    AsyncFunctionDef,
    Attribute,
    ClassDef,
    FunctionDef,
    Module,
    Name,
    expr,
    parse,
    stmt,
)
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from glob import has_magic
from pathlib import Path
from sys import stdout
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import Final, cast, final

from exactus.packages.argument_parser import ExactusArgumentParser

from .javascript import (
    JavaScriptClassMethodReorderer,
    JavaScriptReorderMetrics,
    JavaScriptReorderResult,
)

type MethodNode = FunctionDef | AsyncFunctionDef


def _is_reports_tree(*, directory: Path) -> bool:
    """Fingerprint an exactus report tree regardless of its name.

    Mirrors ``exactus.tools.common.cli.is_reports_tree``; this package
    is importable standalone, so the check stays local: a ``.runtime``
    registry directory, a ``result.json`` + ``result.md`` bundle, or an
    ``ARTIFACTS/@activity.json`` in-flight marker identify report
    output that must never be reorganized.

    Args:
        directory: Directory candidate to fingerprint.

    Returns:
        ``True`` when the directory is an exactus report tree.

    """
    if not directory.is_dir():
        return False
    return (
        (directory / ".runtime").is_dir()
        or (
            (directory / "result.json").is_file()
            and (directory / "result.md").is_file()
        )
        or (directory / "ARTIFACTS" / "@activity.json").is_file()
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_reorder_methods: Grouped module constant.
        min_dunder_name_length: Grouped module constant.
        supported_suffixes: Grouped module constant.
        default_order: Grouped module constant.

    """

    min_reorder_methods: Final[int] = 2
    min_dunder_name_length: Final[int] = 5
    supported_suffixes: Final[frozenset[str]] = frozenset(
        {".py", ".js", ".jsx", ".mjs", ".cjs"},
    )
    default_order: Final[tuple[str, ...]] = (
        "new",
        "init",
        "classmethod",
        "property",
        "staticmethod",
        "method",
        "magic",
        "private_classmethod",
        "private_property",
        "private_staticmethod",
        "private_method",
    )


"Canonical class-method category order."


@dataclass(frozen=True, slots=True)
class ReorderMetrics:
    """Metrics describing one reorder operation.

    Attributes:
        classes_reordered: Classes whose method order changed.
        classes_seen: Structural classes inspected.
        lines_moved: Source lines relocated.
        methods_moved: Methods whose position changed.
        methods_seen: Direct methods inspected.

    """

    classes_reordered: int = 0
    classes_seen: int = 0
    lines_moved: int = 0
    methods_moved: int = 0
    methods_seen: int = 0


type OrganizeMetrics = ReorderMetrics | JavaScriptReorderMetrics


@dataclass(frozen=True, slots=True)
class ReorderResult:
    """Outcome of reordering one Python source.

    Attributes:
        metrics: Aggregated reorder metrics.
        source: Reordered source text.

    """

    metrics: ReorderMetrics
    source: str

    @property
    def changed(self) -> bool:
        """Whether the reorder moved at least one method.

        Returns:
            Whether any method changed position.

        """
        return self.metrics.methods_moved > 0


@dataclass(frozen=True, slots=True)
class _ClassMetrics:
    """Reorder metrics collected while processing one class.

    Attributes:
        methods: Direct methods inspected.
        moved: Methods whose position changed.
        lines_moved: Source lines relocated.

    """

    methods: int
    moved: int
    lines_moved: int


def validate_order(*, order: Sequence[str]) -> tuple[str, ...]:
    """Validate and normalize a method-category order.

    Args:
        order: Category names in the desired order.

    Returns:
        Normalized order tuple.

    Raises:
        ValueError: If ``order`` is not a complete permutation of the
            canonical categories in ``DEFAULT_ORDER``.

    """
    normalized: tuple[str, ...] = tuple(order)
    if len(normalized) == len(Constants.default_order) and frozenset(
        normalized,
    ) == frozenset(Constants.default_order):
        return normalized
    details: list[str] = []
    default: set[str] = set(Constants.default_order)
    unknown: list[str] = sorted(set(normalized) - default)
    missing: list[str] = sorted(default - set(normalized))
    if unknown:
        details.append(f"unknown categories: {', '.join(unknown)}")
    if missing:
        details.append(f"missing categories: {', '.join(missing)}")
    if not details:
        details.append("duplicate categories")
    msg: str = f"invalid organize order ({'; '.join(details)})"
    raise ValueError(msg)


def configured_order(*, start: Path | None = None) -> tuple[str, ...]:
    """Resolve ``[tool.organize] order`` from the nearest ``pyproject.toml``.

    The ``start`` anchor's ancestors are searched from the bottom up and
    the first ``pyproject.toml`` wins, even when it declares no
    ``[tool.organize]`` section.

    Args:
        start: File or directory whose ancestors hold the project
            pyproject; the working directory is used when ``None``.

    Returns:
        The configured order, or ``DEFAULT_ORDER`` when the section or
        file is absent.

    Raises:
        TypeError: If the configured ``order`` value is not a list of
            category names.

    """
    anchor: Path = (Path.cwd() if start is None else start).resolve()
    if not anchor.is_dir():
        anchor = anchor.parent
    directory: Path
    for directory in (anchor, *anchor.parents):
        pyproject: Path = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            with pyproject.open(mode="rb") as file:
                data: dict[str, object] = load_toml(file)
        except (OSError, TOMLDecodeError):
            break
        tool: object = data.get("tool")
        section: object = (
            cast(typ="dict[object, object]", val=tool).get("organize")
            if isinstance(tool, dict)
            else None
        )
        raw: object = (
            cast(typ="dict[object, object]", val=section).get("order")
            if isinstance(section, dict)
            else None
        )
        if raw is None:
            return Constants.default_order
        if not isinstance(raw, (list, tuple)):
            msg: str = (
                "invalid organize order ([tool.organize] order must be a "
                "list of category names)"
            )
            raise TypeError(msg)
        return validate_order(order=cast(typ="Sequence[str]", val=raw))
    return Constants.default_order


@dataclass(frozen=True, slots=True)
class _Method:
    """Describe one direct class method and its movable source span.

    Attributes:
        node: Method's AST node.
        start: Zero-based first movable source line.
        end: Exclusive movable source end line.
        category: Ordering category name.
        property_name: Property family name, or ``None`` for
            non-property methods.
        property_rank: Accessor rank inside the property family.

    """

    node: MethodNode
    start: int
    end: int
    category: str
    property_name: str | None
    property_rank: int


class _ClassCollector:
    """Collect structural classes without descending into function bodies."""

    def __init__(self) -> None:
        """Initialize an empty class collection."""
        self.classes: list[ClassDef] = []

    def collect(self, *, tree: Module) -> None:
        """Collect module-level classes and their direct nested classes.

        Args:
            tree: Parsed Python module.

        """
        statement: stmt
        for statement in tree.body:
            if isinstance(statement, ClassDef):
                self._collect_class(node=statement)

    def _collect_class(self, *, node: ClassDef) -> None:
        """Collect a class and direct nested class declarations recursively.

        Args:
            node: Class definition to collect.

        """
        self.classes.append(node)
        statement: stmt
        for statement in node.body:
            if isinstance(statement, ClassDef):
                self._collect_class(node=statement)


class PythonClassMethodReorderer:
    """Reorder direct class methods using a stable, source-preserving policy.

    The transformer never regenerates Python through ``ast.unparse``.
    Instead, it parses only for structural information and moves the exact
    original source slices belonging to methods.

    Ordering:
        1. ``__new__``
        2. ``__init__``
        3. public class methods
        4. public property families
        5. public static methods
        6. public instance methods
        7. other magic methods
        8. private class methods
        9. private property families
        10. private static methods
        11. private instance methods

    Property getter/setter/deleter methods remain together. Their original
    family order is preserved except that getter, setter, and deleter are
    normalized to that order when all can be identified.

    A contiguous comment block directly touching a method's first decorator
    or ``def`` line moves with that method. Comments separated from a method
    by a blank line remain anchored. Method and class docstrings remain
    untouched because method bodies are moved verbatim and non-method class
    statements are never reordered.
    """

    def __init__(
        self,
        *,
        path: Path,
        order: Sequence[str] = Constants.default_order,
    ) -> None:
        """Initialize a file-backed reorderer.

        Args:
            order: Category order overriding the canonical default.
            path: Python source file to transform.

        """
        self.order: tuple[str, ...] = validate_order(order=order)
        self.path: Path = path

    @classmethod
    def reorder_source(
        cls,
        *,
        source: str,
        order: Sequence[str] = Constants.default_order,
    ) -> str:
        """Reorder all classes in Python source.

        Nested classes are handled independently. The operation is
        idempotent and preserves all source text except method placement.

        Args:
            order: Category order overriding the canonical default.
            source: Complete Python source text.

        Returns:
            Reordered source text.

        """
        return cls.reorder_source_detailed(order=order, source=source).source

    @classmethod
    def reorder_source_detailed(
        cls,
        *,
        source: str,
        order: Sequence[str] = Constants.default_order,
    ) -> ReorderResult:
        """Reorder all classes in Python source and collect metrics.

        Args:
            order: Category order overriding the canonical default.
            source: Complete Python source text.

        Returns:
            Reordered source text with aggregated metrics.

        """
        rank: dict[str, int] = {
            category: position
            for position, category in enumerate(
                iterable=validate_order(order=order),
            )
        }
        tree: Module = parse(source=source)
        collector: _ClassCollector = _ClassCollector()
        collector.collect(tree=tree)
        lines: list[str] = source.splitlines(keepends=True)
        classes: list[ClassDef] = sorted(
            collector.classes,
            key=lambda node: cls._class_depth_key(node=node),
            reverse=True,
        )
        classes_reordered: int = 0
        lines_moved: int = 0
        methods_moved: int = 0
        methods_seen: int = 0
        for class_node in classes:
            outcome: _ClassMetrics = cls._reorder_class(
                lines=lines,
                class_node=class_node,
                rank=rank,
            )
            methods_seen += outcome.methods
            if outcome.moved == 0:
                continue
            classes_reordered += 1
            methods_moved += outcome.moved
            lines_moved += outcome.lines_moved
        return ReorderResult(
            metrics=ReorderMetrics(
                classes_reordered=classes_reordered,
                classes_seen=len(classes),
                lines_moved=lines_moved,
                methods_moved=methods_moved,
                methods_seen=methods_seen,
            ),
            source="".join(lines),
        )

    def reorder(self) -> str:
        """Return reordered file content without writing it.

        Returns:
            Reordered Python source.

        """
        return self.reorder_source(
            order=self.order,
            source=self.path.read_text(encoding="utf-8"),
        )

    def measure(self) -> ReorderResult:
        """Return the reorder outcome with metrics, without writing.

        Returns:
            Reordered source with aggregated metrics.

        """
        return self.reorder_source_detailed(
            order=self.order,
            source=self.path.read_text(encoding="utf-8"),
        )

    def write(self) -> bool:
        """Reorder the file in place when a change is required.

        Returns:
            Whether the file content changed.

        """
        source: str = self.path.read_text(encoding="utf-8")
        result: ReorderResult = self.reorder_source_detailed(
            order=self.order,
            source=source,
        )
        if source == result.source:
            return False
        _bytes_written: int = self.path.write_text(
            data=result.source,
            encoding="utf-8",
        )
        return True

    @classmethod
    def _reorder_class(
        cls,
        *,
        lines: list[str],
        class_node: ClassDef,
        rank: dict[str, int],
    ) -> _ClassMetrics:
        """Reorder direct methods of one class.

        Args:
            class_node: Class whose direct methods are reordered.
            lines: Mutable complete-source line list.
            rank: Category ranks resolved from the configured order.

        Returns:
            Reorder metrics collected for the class.

        """
        methods: list[_Method] = []
        for statement in class_node.body:
            if not isinstance(statement, (FunctionDef, AsyncFunctionDef)):
                continue
            methods.append(cls._describe_method(lines=lines, node=statement))
        if len(methods) < Constants.min_reorder_methods:
            return _ClassMetrics(methods=len(methods), moved=0, lines_moved=0)
        ordered: list[_Method] = cls._ordered_methods(
            methods=methods,
            rank=rank,
        )
        moved: int = sum(
            (
                1
                for original, replacement in zip(methods, ordered, strict=True)
                if original.node is not replacement.node
            ),
        )
        if moved == 0:
            return _ClassMetrics(methods=len(methods), moved=0, lines_moved=0)
        lines_moved: int = sum(
            (
                replacement.end - replacement.start
                for original, replacement in zip(methods, ordered, strict=True)
                if original.node is not replacement.node
            ),
        )
        replacements: list[tuple[int, int, list[str]]] = []
        for slot, replacement in zip(methods, ordered, strict=True):
            replacements.append(
                (
                    slot.start,
                    slot.end,
                    lines[replacement.start : replacement.end],
                ),
            )
        for start, end, replacement_lines in reversed(replacements):
            lines[start:end] = replacement_lines
        return _ClassMetrics(
            methods=len(methods),
            moved=moved,
            lines_moved=lines_moved,
        )

    @classmethod
    def _describe_method(
        cls,
        *,
        lines: list[str],
        node: MethodNode,
    ) -> _Method:
        """Describe a method and its exact movable source span.

        Args:
            lines: Complete-source line list.
            node: Direct class method.

        Returns:
            Classified method descriptor.

        """
        first_line: int = (
            min(decorator.lineno for decorator in node.decorator_list)
            if node.decorator_list
            else node.lineno
        )
        start: int = cls._leading_comment_start(
            lines=lines,
            first_line=first_line - 1,
            indentation=node.col_offset,
        )
        property_name, property_rank = cls._property_identity(node=node)
        return _Method(
            node=node,
            start=start,
            end=node.end_lineno or node.lineno,
            category=cls._category(
                node=node,
                is_property=property_name is not None,
            ),
            property_name=property_name,
            property_rank=property_rank,
        )

    @classmethod
    def _ordered_methods(
        cls,
        *,
        methods: list[_Method],
        rank: dict[str, int],
    ) -> list[_Method]:
        """Return methods in the configured stable order.

        Args:
            methods: Methods in original source order.
            rank: Category ranks resolved from the configured order.

        Returns:
            Canonically ordered methods.

        """
        property_family_order: dict[str, int] = {}
        next_family: int = 0
        for method in methods:
            if method.property_name is None:
                continue
            if method.property_name not in property_family_order:
                property_family_order[method.property_name] = next_family
                next_family += 1
        indexed: list[tuple[int, _Method]] = list(enumerate(iterable=methods))
        return [
            method
            for _, method in sorted(
                indexed,
                key=lambda item: cls._sort_key(
                    original_index=item[0],
                    method=item[1],
                    property_family_order=property_family_order,
                    rank=rank,
                ),
            )
        ]

    @classmethod
    def _category(cls, *, node: MethodNode, is_property: bool) -> str:
        """Classify a method into the canonical ordering category.

        Args:
            node: Method to classify.
            is_property: Whether it belongs to a property family.

        Returns:
            Category name listed in ``DEFAULT_ORDER``.

        """
        name: str = node.name
        is_private: bool = name.startswith("_")
        is_magic: bool = (
            len(name) >= Constants.min_dunder_name_length
            and name.startswith("__")
            and name.endswith("__")
        )
        category: str
        if name == "__new__":
            category = "new"
        elif name == "__init__":
            category = "init"
        elif is_magic:
            category = "magic"
        elif cls._has_decorator(node=node, name="classmethod"):
            category = "private_classmethod" if is_private else "classmethod"
        elif is_property:
            category = "private_property" if is_private else "property"
        elif cls._has_decorator(node=node, name="staticmethod"):
            category = "private_staticmethod" if is_private else "staticmethod"
        else:
            category = "private_method" if is_private else "method"
        return category

    @classmethod
    def _property_identity(cls, *, node: MethodNode) -> tuple[str | None, int]:
        """Identify a property family and accessor kind.

        Args:
            node: Method to inspect.

        Returns:
            Property name and accessor rank, or ``(None, 0)``.

        """
        for decorator in node.decorator_list:
            decorator_name: str | None = cls._decorator_name(
                decorator=decorator,
            )
            if decorator_name == "property":
                return (node.name, 0)
            if (
                isinstance(decorator, Attribute)
                and decorator.attr in {"setter", "deleter", "getter"}
                and isinstance(decorator.value, Name)
            ):
                return (
                    decorator.value.id,
                    {"getter": 0, "setter": 1, "deleter": 2}[decorator.attr],
                )
        return (None, 0)

    @classmethod
    def _has_decorator(cls, *, node: MethodNode, name: str) -> bool:
        """Return whether a method has a recognized decorator.

        Args:
            node: Method to inspect.
            name: Decorator's terminal name.

        Returns:
            Whether the decorator is present.

        """
        return any(
            cls._decorator_name(decorator=decorator) == name
            for decorator in node.decorator_list
        )

    @staticmethod
    def _class_depth_key(*, node: ClassDef) -> tuple[int, int]:
        """Return a stable bottom-up class processing key.

        Args:
            node: Class definition.

        Returns:
            Sort key favoring later and more deeply indented classes.

        """
        return (node.col_offset, node.lineno)

    @staticmethod
    def _leading_comment_start(
        *,
        lines: list[str],
        first_line: int,
        indentation: int,
    ) -> int:
        """Find comments directly attached to a method.

        Args:
            lines: Complete-source line list.
            first_line: Zero-based first decorator or definition line.
            indentation: Method indentation width.

        Returns:
            Zero-based start line of the movable method slice.

        """
        start: int = first_line
        index: int = first_line - 1
        prefix: str = " " * indentation
        while index >= 0:
            stripped: str = lines[index].strip()
            if not stripped or not lines[index].startswith(prefix):
                break
            if not stripped.startswith("#"):
                break
            start = index
            index -= 1
        return start

    @staticmethod
    def _sort_key(
        *,
        original_index: int,
        method: _Method,
        property_family_order: dict[str, int],
        rank: dict[str, int],
    ) -> tuple[int, int, int, int]:
        """Build a deterministic stable method sort key.

        Args:
            original_index: Method's original class-body position.
            method: Classified method.
            property_family_order: Original property-family ordering.
            rank: Category ranks resolved from the configured order.

        Returns:
            Canonical sort key.

        """
        category_rank: int = rank[method.category]
        if method.property_name is None:
            return (category_rank, original_index, 0, original_index)
        return (
            category_rank,
            property_family_order[method.property_name],
            method.property_rank,
            original_index,
        )

    @staticmethod
    def _decorator_name(*, decorator: expr) -> str | None:
        """Return a simple or qualified decorator's terminal name.

        Args:
            decorator: AST decorator expression.

        Returns:
            Terminal decorator name when statically recognizable.

        """
        if isinstance(decorator, Name):
            return decorator.id
        if isinstance(decorator, Attribute):
            return decorator.attr
        return None


def _matches(*, path: Path, patterns: Sequence[str]) -> bool:
    """Return whether a path matches any glob pattern.

    Args:
        path: Path tested against the patterns.
        patterns: Glob patterns matched against the posix path text.

    Returns:
        Whether at least one pattern matches.

    """
    text: str = path.as_posix()
    return any(fnmatch(name=text, pat=pattern) for pattern in patterns)


def _expand(*, argument: str) -> list[Path]:
    """Expand one path argument through ``Path`` glob semantics.

    Args:
        argument: File, directory, or glob pattern.

    Returns:
        Matching paths, or the literal path when it is not a pattern.

    """
    path: Path = Path(argument)
    if not has_magic(s=argument):
        return [path]
    anchor_parts: list[str] = []
    for part in path.parts:
        if has_magic(s=part):
            break
        anchor_parts.append(part)
    anchor: Path = Path(*anchor_parts)
    pattern: str = str(object=Path(*path.parts[len(anchor_parts) :]))
    return sorted(anchor.glob(pattern=pattern))


def _resolve_paths(
    *,
    arguments: Sequence[str],
    includes: Sequence[str],
    excludes: Sequence[str],
) -> list[Path]:
    """Expand path arguments and apply include/exclude globs.

    Args:
        arguments: Files, directories, or glob patterns to organize.
        includes: Glob patterns a source must match when non-empty.
        excludes: Glob patterns a source must not match.

    Returns:
        Sorted unique supported Python and JavaScript sources to process.

    """
    found: dict[str, Path] = {}
    argument: str
    for argument in arguments:
        candidate: Path
        for candidate in _expand(argument=argument):
            candidates: list[Path] = (
                sorted(
                    path
                    for path in candidate.rglob(pattern="*")
                    if path.is_file()
                    and path.suffix.lower() in Constants.supported_suffixes
                    and not any(
                        _is_reports_tree(directory=parent)
                        for parent in path.parents
                    )
                )
                if candidate.is_dir()
                else [candidate]
            )
            path: Path
            for path in candidates:
                if path.suffix.lower() not in Constants.supported_suffixes:
                    continue
                if _matches(path=path, patterns=excludes):
                    continue
                if includes and (not _matches(path=path, patterns=includes)):
                    continue
                found[str(object=path.resolve())] = path
    return [found[key] for key in sorted(found)]


def _organize_path(
    *,
    path: Path,
    order: Sequence[str],
    dry: bool,
) -> OrganizeMetrics | None:
    """Organize one file and print its outcome.

    Args:
        dry: Report changes without writing the file.
        order: Category order applied to the file.
        path: Supported source file to process.

    Returns:
        Reorder metrics, or ``None`` when the file failed.

    """
    try:
        if path.suffix.lower() == ".py":
            result: ReorderResult | JavaScriptReorderResult = (
                PythonClassMethodReorderer(order=order, path=path).measure()
            )
        else:
            result = JavaScriptClassMethodReorderer(path=path).measure()
    except (OSError, RuntimeError, SyntaxError, TypeError) as error:
        _written: int = stdout.write(f"error: {path} — {error}\n")
        return None
    metrics: OrganizeMetrics = result.metrics
    if not result.changed:
        _written = stdout.write(
            f"unchanged: {path} — {metrics.methods_seen} methods\n",
        )
        return metrics
    detail: str = (
        f"{metrics.methods_moved}/{metrics.methods_seen} methods moved, "
        f"{metrics.classes_reordered}/{
            metrics.classes_seen
        } classes reordered, {metrics.lines_moved} lines moved"
    )
    if dry:
        _written = stdout.write(f"would update: {path} — {detail}\n")
        return metrics
    _bytes_written: int = path.write_text(data=result.source, encoding="utf-8")
    _written = stdout.write(f"updated: {path} — {detail}\n")
    return metrics


def _create_parser() -> ArgumentParser:
    """Create the organize command-line parser.

    Returns:
        Configured argument parser.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="python -m exactus.packages.organize",
        description=(
            "Reorder Python and JavaScript class methods into "
            "canonical semantic layouts while preserving source "
            "text."
        ),
    )
    _ = parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="*",
        help=(
            "Python/JavaScript files, directories, or glob patterns to "
            "organize."
        ),
    )
    _ = parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="Only organize sources matching GLOB; repeatable.",
    )
    _ = parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Skip sources matching GLOB; repeatable.",
    )
    _ = parser.add_argument(
        "--dry",
        "--dry-run",
        action="store_true",
        dest="dry",
        help="Report the changes organize would make without writing.",
    )
    _ = parser.add_argument(
        "--order",
        metavar="CATEGORIES",
        help=(
            "Comma-separated category order overriding [tool.organize] "
            "order in pyproject.toml."
        ),
    )
    return parser


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Organize class methods in Python and JavaScript files.

    Args:
        arguments: Command-line tokens; process arguments when ``None``.

    Returns:
        ``0`` on success, ``1`` when no paths were given or a file
        failed.

    """
    parser: ArgumentParser = _create_parser()
    options: Namespace = parser.parse_args(
        args=None if arguments is None else list(arguments),
    )
    paths: list[Path] = _resolve_paths(
        arguments=cast(typ="list[str]", val=options.paths),
        includes=cast(typ="list[str]", val=options.include),
        excludes=cast(typ="list[str]", val=options.exclude),
    )
    if not paths:
        parser.print_usage(file=stdout)
        return 1
    order_option: str | None = cast(typ="str | None", val=options.order)
    try:
        order: tuple[str, ...] = (
            validate_order(order=order_option.split(sep=","))
            if order_option is not None
            else configured_order()
        )
    except ValueError as error:
        parser.error(message=str(object=error))
    dry: bool = cast(typ="bool", val=options.dry)
    moved: int = 0
    reordered_files: int = 0
    failures: int = 0
    for path in paths:
        metrics: OrganizeMetrics | None = _organize_path(
            path=path,
            order=order,
            dry=dry,
        )
        if metrics is None:
            failures += 1
            continue
        moved += metrics.methods_moved
        reordered_files += int(metrics.methods_moved > 0)
    _written: int = stdout.write(
        f"organized {len(paths)} files — {reordered_files} {
            ('would change' if dry else 'changed')
        }, {len(paths) - reordered_files - failures} unchanged, "
        f"{failures} failed; {moved} methods moved\n",
    )
    return int(failures > 0)
