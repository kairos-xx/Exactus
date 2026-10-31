"""Group safely movable module-level Final constants into Constants classes."""

from __future__ import annotations

from argparse import Action, ArgumentParser, Namespace
from ast import (
    AST,
    AnnAssign,
    Assign,
    AsyncFunctionDef,
    Attribute,
    ClassDef,
    Constant,
    DictComp,
    Expr,
    FunctionDef,
    GeneratorExp,
    Global,
    Import,
    ImportFrom,
    Lambda,
    ListComp,
    Load,
    Module,
    Name,
    NodeTransformer,
    NodeVisitor,
    SetComp,
    Store,
    Subscript,
    alias,
    arg,
    copy_location,
    dump,
    expr,
    fix_missing_locations,
    parse,
    stmt,
    unparse,
)
from dataclasses import dataclass
from fnmatch import fnmatch
from os import environ, walk
from pathlib import Path
from sys import stdlib_module_names, stdout
from typing import ClassVar, TextIO, TypeVar, cast, final

from exactus.packages.argument_parser import ExactusArgumentParser

try:
    from exactus.packages.steps import trace
except ImportError:

    def trace(*, step: str, depth: int = 0) -> None:
        """Discard step events when the trace module is unavailable.

        Args:
            step: Step label, ignored.
            depth: Nesting depth, ignored.

        """
        del step, depth


try:
    from exactus.tools.common.cli import is_reports_tree
except ImportError:

    def is_reports_tree(*, directory: Path) -> bool:
        """Fingerprint an exactus report tree when vendored standalone.

        Mirrors ``exactus.tools.common.cli.is_reports_tree`` so this
        package can run without the ``exactus.tools`` namespace.

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


AstNode = TypeVar(name="AstNode", bound=AST)
"""AST node concrete type retained through generic visits."""


def _member_name(*, name: str) -> str:
    """Convert a module constant name to a public snake-case member.

    Args:
        name: Original module-level constant identifier.

    Returns:
        Public snake-case member name.

    """
    return "_".join(
        part.lower() for part in name.lstrip("_").split(sep="_") if part
    )


@dataclass(frozen=True, slots=True)
class ConstantBinding:
    """Describe a module-level Final constant candidate.

    Attributes:
        name: Identifier bound by the annotated assignment.
        statement_index: Position of the statement in its module body.
        statement: The annotated assignment node itself.

    """

    name: str
    statement_index: int
    statement: AnnAssign


@dataclass(frozen=True, slots=True)
class ModulePlan:
    """Describe a safe constants-class transformation for one module.

    Attributes:
        path: Module file receiving the generated class.
        module_name: Dotted module name for the file.
        names: Constant names safe to move into ``Constants``.
        insertion_index: Module body index where the class is inserted.
        merge: Whether the constants merge into an existing
            ``Constants`` class instead of creating one.

    """

    path: Path
    module_name: str
    names: frozenset[str]
    insertion_index: int
    merge: bool = False


@dataclass(frozen=True, slots=True)
class TransformRequest:
    """Collect the project context needed to transform one module.

    Attributes:
        plan: This module's own constants plan, when it gains a class.
        moved_by_module: Moved constant names indexed by provider module.
        members_by_module: Generated member renames indexed by module.
        current_module: Dotted name of the module being transformed.
        current_is_package: Whether the module file is ``__init__.py``.

    """

    plan: ModulePlan | None
    moved_by_module: dict[str, frozenset[str]]
    members_by_module: dict[str, dict[str, str]]
    current_module: str
    current_is_package: bool


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Summarize one refactoring run.

    Attributes:
        files: Python files discovered and analyzed.
        planned: Modules receiving a ``Constants`` class.
        constants: Constants moved into ``Constants`` classes.
        changed: Files whose generated source differs.
        dry_run: Whether the run analyzed without writing.

    """

    files: int
    planned: int
    constants: int
    changed: int
    dry_run: bool


def _print(*args: str, file: TextIO = stdout) -> None:
    """Print and immediately flush a script message.

    Args:
        *args: Values to print.
        file: Stream receiving the message.

    """
    _ = file.write(" ".join(str(object=arg) for arg in args) + "\n")
    _ = file.flush()


@final
class Palette:
    """Collect ANSI styling constants.

    Attributes:
        reset: Sequence restoring default text attributes.
        bold: Sequence enabling bold text.
        dim: Sequence enabling dimmed text.
        red: Sequence coloring text red.
        green: Sequence coloring text green.
        yellow: Sequence coloring text yellow.
        cyan: Sequence coloring text cyan.

    """

    reset: ClassVar[str] = "\x1b[0m"
    bold: ClassVar[str] = "\x1b[1m"
    dim: ClassVar[str] = "\x1b[2m"
    red: ClassVar[str] = "\x1b[31m"
    green: ClassVar[str] = "\x1b[32m"
    yellow: ClassVar[str] = "\x1b[33m"
    cyan: ClassVar[str] = "\x1b[36m"


def _paint(*, text: str, color: str, enabled: bool = True) -> str:
    """Wrap text in an ANSI color when coloring is enabled.

    Args:
        text: Text to colorize.
        color: ANSI SGR sequence applied before ``text``.
        enabled: When ``False`` return ``text`` unchanged.

    Returns:
        Colorized text, or ``text`` unchanged when ``enabled`` is
        ``False``.

    """
    return f"{color}{text}{Palette.reset}" if enabled else text


class ProgressDisplay:
    """Render a live single-row file-processing progress bar.

    Disabled automatically when standard output is not a terminal, so
    non-interactive runs emit no escape sequences; colors are dropped
    when ``NO_COLOR`` is set.
    """

    def __init__(self, *, label: str, total: int) -> None:
        """Initialize the display.

        Args:
            label: Row label shown before the bar.
            total: Total number of work items.

        """
        self._label: str = label
        self._total: int = total
        self._completed: int = 0
        self._enabled: bool = stdout.isatty()
        self._colored: bool = self._enabled and "NO_COLOR" not in environ

    def render(self) -> None:
        """Draw the initial progress line.

        Does nothing when standard output is not a terminal.

        """
        if self._enabled:
            self._write()

    def finish(self) -> None:
        """Record one processed file and refresh the line."""
        self._completed += 1
        if self._enabled:
            self._write()

    def close(self) -> None:
        """Terminate the progress line with a newline."""
        if self._enabled:
            _ = stdout.write("\n")
            _ = stdout.flush()

    def _line(self) -> str:
        """Render the progress line for the current state.

        Returns:
            Label, determinate bar, percentage and item counts; the fill
            renders cyan while running and green once complete.

        """
        ratio: float = (
            1.0
            if self._total == 0
            else min(self._completed / self._total, 1.0)
        )
        filled: int = round(number=ratio * 28)
        color: str = Palette.green if ratio >= 1.0 else Palette.cyan
        bar: str = (
            f"{Palette.dim}[{color}{'█' * filled}{Palette.dim}"
            f"{'░' * (28 - filled)}]{Palette.reset}"
            if self._colored
            else f"[{'█' * filled}{'░' * (28 - filled)}]"
        )
        return (
            f"{self._label:<8} {bar} {ratio * 100:6.2f}% "
            f"{self._completed}/{self._total}"
        )

    def _write(self) -> None:
        """Overwrite the current terminal line with the progress line."""
        _ = stdout.write(f"\r\x1b[2K{self._line()}")
        _ = stdout.flush()


class NameCollector(NodeVisitor):
    """Collect loaded names from an AST subtree."""

    def __init__(self) -> None:
        """Initialize an empty name set."""
        self.names: set[str] = set()

    def visit(self, node: AST) -> None:
        """Record a loaded name and recurse into the subtree.

        Args:
            node: Node being visited.

        """
        if isinstance(node, Name) and isinstance(node.ctx, Load):
            self.names.add(node.id)
        self.generic_visit(node=node)


class BindingCollector(NodeVisitor):
    """Collect every identifier bound below an AST subtree."""

    def __init__(self, *, nested: bool = True) -> None:
        """Initialize the collector.

        Args:
            nested: Whether bindings inside nested lexical scopes count.

        """
        self.names: set[str] = set()
        self.globals: set[str] = set()
        self._nested: bool = nested
        self._root: bool = True

    def visit(self, node: AST) -> None:
        """Collect bindings while optionally stopping at nested scopes.

        Args:
            node: Node being visited.

        """
        if isinstance(node, Name) and not isinstance(node.ctx, Load):
            self.names.add(node.id)
            return
        argument_name: object = getattr(node, "arg", None)
        if isinstance(argument_name, str):
            self.names.add(argument_name)
            self.generic_visit(node=node)
            return
        if isinstance(node, Import):
            self.names.update(
                item.asname or item.name.split(sep=".", maxsplit=1)[0]
                for item in node.names
            )
            return
        if isinstance(node, ImportFrom):
            self.names.update(
                item.asname or item.name
                for item in node.names
                if item.name != "*"
            )
            return
        if isinstance(node, Global):
            self.globals.update(node.names)
            return
        is_scope: bool = isinstance(
            node,
            (FunctionDef, AsyncFunctionDef, ClassDef, Lambda),
        )
        if is_scope and not self._root and not self._nested:
            if isinstance(node, (FunctionDef, AsyncFunctionDef, ClassDef)):
                self.names.add(node.name)
            return
        root: bool = self._root
        self._root = False
        self.generic_visit(node=node)
        self._root = root


class ScopedReferenceTransformer(NodeTransformer):
    """Base transformer that respects function-local shadowing."""

    def __init__(self, *, tracked: frozenset[str]) -> None:
        """Initialize tracked identifiers.

        Args:
            tracked: Names whose references may be rewritten.

        """
        self._tracked: frozenset[str] = tracked
        self._blocked: list[frozenset[str]] = [frozenset()]
        self._closure_blocked: list[frozenset[str]] = [frozenset()]

    def visit(self, node: AST) -> AST:
        """Visit a node through generic, scope-aware dispatch.

        Args:
            node: Node being visited.

        Returns:
            Original or rewritten node.

        """
        if self._skip(node=node):
            return node
        if isinstance(node, (FunctionDef, AsyncFunctionDef)):
            return self._visit_function(node=node)
        if isinstance(node, Lambda):
            return self._visit_lambda(node=node)
        if isinstance(node, ClassDef):
            return self._visit_class(node=node)
        if isinstance(node, (ListComp, SetComp, DictComp, GeneratorExp)):
            return self._visit_comprehension(node=node)
        return self._rewrite(node=super().visit(node=node))

    def _visit_typed(self, *, node: AstNode) -> AstNode:
        """Visit a node while retaining its concrete AST type.

        Args:
            node: Node being visited.

        Returns:
            Original or rewritten node with the same concrete type.

        """
        return cast(typ="AstNode", val=self.visit(node=node))

    def _visit_function(self, *, node: FunctionDef | AsyncFunctionDef) -> AST:
        """Visit outer expressions and a shadow-aware function body.

        Args:
            node: Function definition node being visited.

        Returns:
            The visited function definition node.

        """
        node.decorator_list = [
            self._visit_typed(node=item) for item in node.decorator_list
        ]
        node.returns = (
            self._visit_typed(node=node.returns) if node.returns else None
        )
        parameters: list[arg] = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        if node.args.vararg is not None:
            parameters.append(node.args.vararg)
        if node.args.kwarg is not None:
            parameters.append(node.args.kwarg)
        for parameter in parameters:
            annotation: expr | None = parameter.annotation
            if annotation is not None:
                parameter.annotation = self._visit_typed(node=annotation)
        defaults: list[expr] = [
            self._visit_typed(node=item) for item in node.args.defaults
        ]
        node.args.defaults = defaults
        node.args.kw_defaults = [
            self._visit_typed(node=item) if item is not None else None
            for item in node.args.kw_defaults
        ]
        collector: BindingCollector = BindingCollector(nested=False)
        collector.visit(node=node)
        local: frozenset[str] = frozenset(
            (collector.names - collector.globals) & self._tracked,
        )
        body_blocked: frozenset[str] = self._closure_blocked[-1] | local
        self._blocked.append(body_blocked)
        self._closure_blocked.append(body_blocked)
        node.body = [self._visit_typed(node=item) for item in node.body]
        self._closure_blocked.pop()
        self._blocked.pop()
        return node

    def _visit_lambda(self, *, node: Lambda) -> AST:
        """Visit a lambda while respecting argument shadowing.

        Args:
            node: Lambda expression node being visited.

        Returns:
            The visited lambda node.

        """
        node.args.defaults = [
            self._visit_typed(node=item) for item in node.args.defaults
        ]
        node.args.kw_defaults = [
            self._visit_typed(node=item) if item is not None else None
            for item in node.args.kw_defaults
        ]
        collector: BindingCollector = BindingCollector(nested=False)
        collector.visit(node=node)
        local: frozenset[str] = frozenset(collector.names & self._tracked)
        body_blocked: frozenset[str] = self._closure_blocked[-1] | local
        self._blocked.append(body_blocked)
        self._closure_blocked.append(body_blocked)
        node.body = self._visit_typed(node=node.body)
        self._closure_blocked.pop()
        self._blocked.pop()
        return node

    def _visit_class(self, *, node: ClassDef) -> AST:
        """Visit class expressions and its dynamically scoped body.

        Args:
            node: Class definition node being visited.

        Returns:
            The visited or rewritten class definition node.

        """
        node.decorator_list = [
            self._visit_typed(node=item) for item in node.decorator_list
        ]
        node.bases = [self._visit_typed(node=item) for item in node.bases]
        for item in node.keywords:
            item.value = self._visit_typed(node=item.value)
        collector: BindingCollector = BindingCollector(nested=False)
        collector.visit(node=node)
        local: frozenset[str] = frozenset(collector.names & self._tracked)
        self._blocked.append(self._blocked[-1] | local)
        node.body = [self._visit_typed(node=item) for item in node.body]
        self._blocked.pop()
        return self._rewrite(node=node)

    def _visit_comprehension(
        self,
        *,
        node: ListComp | SetComp | DictComp | GeneratorExp,
    ) -> AST:
        """Visit a comprehension with its isolated target bindings.

        Args:
            node: Comprehension node being visited.

        Returns:
            The visited or rewritten comprehension node.

        """
        if not node.generators:
            return self._rewrite(node=node)
        node.generators[0].iter = self._visit_typed(
            node=node.generators[0].iter,
        )
        collector: BindingCollector = BindingCollector()
        for generator in node.generators:
            collector.visit(node=generator.target)
        local: frozenset[str] = frozenset(collector.names & self._tracked)
        self._blocked.append(self._blocked[-1] | local)
        for index, generator in enumerate(iterable=node.generators):
            if index:
                generator.iter = self._visit_typed(node=generator.iter)
            generator.ifs = [
                self._visit_typed(node=item) for item in generator.ifs
            ]
        if isinstance(node, DictComp):
            node.key = self._visit_typed(node=node.key)
            node.value = self._visit_typed(node=node.value)
        else:
            node.elt = self._visit_typed(node=node.elt)
        self._blocked.pop()
        return self._rewrite(node=node)

    def _skip(self, *, node: AST) -> bool:
        """Return whether a complete subtree must remain untouched.

        Args:
            node: Node being visited.

        Returns:
            Whether the node and its subtree stay unmodified.

        """
        del node
        return False

    def _rewrite(self, *, node: AST) -> AST:
        """Rewrite one already-visited node in a concrete transformer.

        Args:
            node: Node after its children were visited.

        Returns:
            Original or rewritten node.

        """
        return node

    def _is_blocked(self, *, name: str) -> bool:
        """Return whether the current lexical scope shadows ``name``.

        Args:
            name: Identifier being checked for local shadowing.

        Returns:
            Whether ``name`` is bound in the current scope.

        """
        return name in self._blocked[-1]


class LocalReferenceTransformer(ScopedReferenceTransformer):
    """Rewrite references to moved constants inside their defining module."""

    def __init__(self, *, names: frozenset[str]) -> None:
        """Initialize the transformer.

        Args:
            names: Constant names moved into Constants.

        """
        super().__init__(tracked=names)
        self._names: frozenset[str] = names
        self._members: dict[str, str] = {
            name: _member_name(name=name) for name in names
        }

    def _skip(self, *, node: AST) -> bool:
        """Keep the generated Constants class internally self-contained.

        Args:
            node: Node being visited.

        Returns:
            Whether the node is the generated ``Constants`` class.

        """
        return isinstance(node, ClassDef) and node.name == "Constants"

    def _rewrite(self, *, node: AST) -> AST:
        """Rewrite a moved constant load to Constants.NAME.

        Args:
            node: Node being visited.

        Returns:
            Original or rewritten expression.

        """
        if (
            isinstance(node, Name)
            and node.id in self._names
            and not self._is_blocked(name=node.id)
            and isinstance(node.ctx, Load)
        ):
            return copy_location(
                new_node=Attribute(
                    value=Name(id="Constants", ctx=Load()),
                    attr=self._members[node.id],
                    ctx=Load(),
                ),
                old_node=node,
            )
        return node


class QualifiedReferenceTransformer(ScopedReferenceTransformer):
    """Rewrite module-qualified constant references."""

    def __init__(self, *, module_aliases: dict[str, frozenset[str]]) -> None:
        """Initialize the transformer.

        Args:
            module_aliases: Imported module aliases and moved names.

        """
        super().__init__(tracked=frozenset(module_aliases))
        self._module_aliases: dict[str, frozenset[str]] = module_aliases

    def _rewrite(self, *, node: AST) -> AST:
        """Rewrite module.NAME to module.Constants.NAME.

        Args:
            node: Node being visited.

        Returns:
            Original or rewritten expression.

        """
        if (
            isinstance(node, Attribute)
            and isinstance(node.value, Name)
            and (node.value.id in self._module_aliases)
            and not self._is_blocked(name=node.value.id)
            and (node.attr in self._module_aliases[node.value.id])
        ):
            return copy_location(
                new_node=Attribute(
                    value=Attribute(
                        value=node.value,
                        attr="Constants",
                        ctx=Load(),
                    ),
                    attr=_member_name(name=node.attr),
                    ctx=node.ctx,
                ),
                old_node=node,
            )
        return node


class MemberReferenceTransformer(NodeTransformer):
    """Rename references between members moved into ``Constants``."""

    def __init__(self, *, replacements: dict[str, str]) -> None:
        """Initialize member-name replacements.

        Args:
            replacements: Original module name to generated member name.

        """
        self._replacements: dict[str, str] = replacements

    def visit(self, node: AST) -> AST:
        """Rename one loaded member reference after visiting its children.

        Args:
            node: Node being visited.

        Returns:
            Original or renamed name expression.

        """
        node = self.generic_visit(node=node)
        if (
            isinstance(node, Name)
            and isinstance(node.ctx, Load)
            and node.id in self._replacements
        ):
            return copy_location(
                new_node=Name(id=self._replacements[node.id], ctx=Load()),
                old_node=node,
            )
        return node


class ConstantsMemberTransformer(ScopedReferenceTransformer):
    """Normalize references to members of generated Constants classes."""

    def __init__(
        self,
        *,
        current: dict[str, str],
        class_aliases: dict[str, dict[str, str]],
        module_aliases: dict[str, dict[str, str]],
    ) -> None:
        """Initialize generated member reference mappings.

        Args:
            current: Member renames for this module's own ``Constants``.
            class_aliases: Member renames indexed by imported class alias.
            module_aliases: Member renames indexed by imported module
                alias for ``module.Constants`` references.

        """
        tracked: frozenset[str] = frozenset(
            {"Constants", *class_aliases, *module_aliases},
        )
        super().__init__(tracked=tracked)
        self._current: dict[str, str] = current
        self._class_aliases: dict[str, dict[str, str]] = class_aliases
        self._module_aliases: dict[str, dict[str, str]] = module_aliases

    def _skip(self, *, node: AST) -> bool:
        """Leave the generated class body to its dedicated normalizer.

        Args:
            node: Node being visited.

        Returns:
            Whether the node is the generated ``Constants`` class.

        """
        return isinstance(node, ClassDef) and node.name == "Constants"

    def _rewrite(self, *, node: AST) -> AST:
        """Rewrite a generated Constants member to snake case.

        Args:
            node: Node after its children were visited.

        Returns:
            Original or rewritten attribute node.

        """
        if not isinstance(node, Attribute):
            return node
        replacements: dict[str, str] | None = None
        if isinstance(node.value, Name):
            qualifier: str = node.value.id
            if not self._is_blocked(name=qualifier):
                replacements = (
                    self._current
                    if qualifier == "Constants" and self._current
                    else self._class_aliases.get(qualifier)
                )
        elif (
            isinstance(node.value, Attribute)
            and node.value.attr == "Constants"
            and isinstance(node.value.value, Name)
            and not self._is_blocked(name=node.value.value.id)
        ):
            replacements = self._module_aliases.get(node.value.value.id)
        if replacements is None or node.attr not in replacements:
            return node
        node.attr = replacements[node.attr]
        return node


class FinalConstantsRefactor:
    """Refactor safely movable module-level Final constants project-wide.

    Attributes:
        excludes: Glob-like project-relative patterns for directories
            and files the refactoring must never scan or modify.

    """

    excludes: ClassVar[tuple[str, ...]] = (
        "**/node_modules",
        "**/__pycache__",
        "**/.*",
        "**/EXACTUS_RESULTS",
        "mutants",
        "**/mutants",
        "dist",
        "build",
        ".build-cache",
        "exactus/bundle",
    )

    def __init__(self, *, root: Path, dry_run: bool) -> None:
        """Initialize the refactoring operation.

        Args:
            root: Python source-tree root.
            dry_run: Whether the run analyzes without writing; when
                ``False`` transformed files are applied in place.

        """
        resolved: Path = root.resolve()
        if resolved.is_file():
            self._explicit_files: tuple[Path, ...] | None = (resolved,)
            self._root: Path = resolved.parent
        else:
            self._explicit_files = None
            self._root = resolved
        self._dry_run: bool = dry_run

    def run(self) -> ScanReport:
        """Analyze the source tree and rewrite it unless dry-running.

        Returns:
            Aggregated run statistics for the summary table.

        """
        paths: tuple[Path, ...] = tuple(self._python_files())
        trace(
            step=f"group final: {len(paths)} python files collected",
            depth=3,
        )
        modules: dict[Path, str] = {
            path: self._module_name(path=path) for path in paths
        }
        trees: dict[Path, Module] = self._parse_trees(paths=paths)
        trace(step=f"group final: parsed {len(trees)} modules", depth=3)
        plans: dict[Path, ModulePlan] = {
            path: plan
            for path, tree in trees.items()
            if (
                plan := self._plan(
                    path=path,
                    module_name=modules[path],
                    tree=tree,
                )
            )
            is not None
        }
        trace(
            step=(
                f"group final: {len(plans)} plans — "
                f"{sum(len(plan.names) for plan in plans.values())} "
                "constants"
            ),
            depth=3,
        )
        plans = self._drop_unsafe_cross_module_plans(
            plans=plans,
            modules=modules,
            trees=trees,
        )
        trace(
            step=(
                f"group final: {len(plans)} plans kept after "
                "unsafe-import check"
            ),
            depth=3,
        )
        existing_by_module: dict[str, dict[str, str]] = {
            modules[path]: members
            for path, tree in trees.items()
            if (members := self._existing_members(tree=tree))
        }
        moved_by_module: dict[str, frozenset[str]] = {
            plan.module_name: plan.names for plan in plans.values()
        }
        members_by_module: dict[str, dict[str, str]] = {
            **existing_by_module,
            **{
                plan.module_name: {
                    name: _member_name(name=name) for name in plan.names
                }
                for plan in plans.values()
            },
        }
        if not plans and not existing_by_module:
            trace(step="group final: no transformations required", depth=3)
            return ScanReport(
                files=len(trees),
                planned=0,
                constants=0,
                changed=0,
                dry_run=self._dry_run,
            )
        transform_paths: list[Path] = list(trees)
        if not plans:
            transform_paths = []
            for path, tree in trees.items():
                current_module: str = modules[path]
                class_aliases: dict[str, dict[str, str]]
                module_aliases: dict[str, dict[str, str]]
                class_aliases, module_aliases = self._constants_aliases(
                    tree=tree,
                    members_by_module=members_by_module,
                    current_module=current_module,
                    current_is_package=path.name == "__init__.py",
                )
                if (
                    current_module in existing_by_module
                    or class_aliases
                    or module_aliases
                ):
                    transform_paths.append(path)
            trace(
                step=(
                    "group final: legacy-reference scope — "
                    f"{len(transform_paths)} of {len(paths)} files"
                ),
                depth=3,
            )
        progress: ProgressDisplay = ProgressDisplay(
            label="files",
            total=len(transform_paths),
        )
        progress.render()
        changed: list[Path] = []
        for path in transform_paths:
            tree: Module = trees[path]
            original_tree: str = dump(node=tree, include_attributes=False)
            transformed: Module = self._transform_module(
                tree=tree,
                request=TransformRequest(
                    plan=plans.get(path),
                    moved_by_module=moved_by_module,
                    members_by_module=members_by_module,
                    current_module=modules[path],
                    current_is_package=path.name == "__init__.py",
                ),
            )
            if (
                dump(node=transformed, include_attributes=False)
                == original_tree
            ):
                progress.finish()
                continue
            try:
                original: str = path.read_text(encoding="utf-8")
            except OSError:
                trace(step=f"group final: {path} vanished, skipped", depth=3)
                progress.finish()
                continue
            relative: str = path.relative_to(self._root).as_posix()
            rendered: str = (
                unparse(ast_obj=fix_missing_locations(node=transformed)) + "\n"
            )
            source: str = self._leading_header(source=original) + rendered
            changed.append(path)
            if not self._dry_run:
                path.write_text(data=source, encoding="utf-8", newline="\n")
            trace(step=f"group final: {relative} — rewritten", depth=4)
            progress.finish()
        progress.close()
        for path in changed:
            _print(
                f"{('WOULD UPDATE' if self._dry_run else 'UPDATE')} "
                f"{path.relative_to(self._root)}",
            )
        return ScanReport(
            files=len(trees),
            planned=len(plans),
            constants=sum(len(plan.names) for plan in plans.values()),
            changed=len(changed),
            dry_run=self._dry_run,
        )

    @classmethod
    def _is_excluded(cls, *, path: Path) -> bool:
        """Return whether a project-relative path is excluded.

        Args:
            path: Project-relative path being checked.

        Returns:
            True when the path or one of its parents matches an
            exclusion pattern, so excluding a directory excludes its
            complete subtree.

        """
        candidates: tuple[str, ...] = (
            path.as_posix(),
            *(
                parent.as_posix()
                for parent in path.parents
                if parent != Path()
            ),
        )
        return any(
            fnmatch(name=candidate, pat=pattern)
            or fnmatch(name=candidate, pat=pattern.removeprefix("**/"))
            for pattern in cls.excludes
            for candidate in candidates
        )

    @classmethod
    def _candidate(
        cls,
        *,
        statement: AST,
        statement_index: int,
    ) -> ConstantBinding | None:
        """Return a supported module-level Final assignment.

        Args:
            statement: Top-level statement.
            statement_index: Position in the module body.

        Returns:
            Candidate binding when the statement is supported.

        """
        if (
            not isinstance(statement, AnnAssign)
            or not isinstance(statement.target, Name)
            or statement.value is None
            or (not cls._uppercase(name=statement.target.id))
            or (not cls._is_final(annotation=statement.annotation))
        ):
            return None
        return ConstantBinding(
            name=statement.target.id,
            statement_index=statement_index,
            statement=statement,
        )

    @classmethod
    def _existing_members(cls, *, tree: Module) -> dict[str, str]:
        """Collect uppercase members from a previously generated class.

        Args:
            tree: Module whose generated class is inspected.

        Returns:
            Mapping of previous member names to snake-case members.

        """
        constants: ClassDef | None = cls._generated_constants_class(tree=tree)
        if constants is None:
            return {}
        replacements: dict[str, str] = {}
        for statement in constants.body:
            if not isinstance(statement, AnnAssign) or not isinstance(
                statement.target,
                Name,
            ):
                continue
            original: str = statement.target.id
            normalized: str = _member_name(name=original)
            legacy: str = normalized.upper()
            if legacy != normalized:
                replacements[legacy] = normalized
            if original != normalized:
                replacements[original] = normalized
        return replacements

    @classmethod
    def _normalize_generated_class(
        cls,
        *,
        tree: Module,
        replacements: dict[str, str],
    ) -> None:
        """Rename existing generated class members and their dependencies.

        Args:
            tree: Module containing the previously generated class.
            replacements: Member renames applied inside the class.

        """
        if not replacements:
            return
        constants: ClassDef | None = cls._generated_constants_class(tree=tree)
        if constants is None:
            return
        transformer: MemberReferenceTransformer = MemberReferenceTransformer(
            replacements=replacements,
        )
        members: list[tuple[str, AnnAssign]] = []
        for statement in constants.body:
            if not isinstance(statement, AnnAssign) or not isinstance(
                statement.target,
                Name,
            ):
                continue
            statement.target.id = replacements.get(
                statement.target.id,
                statement.target.id,
            )
            if statement.value is not None:
                statement.value = cast(
                    typ="expr",
                    val=transformer.visit(node=statement.value),
                )
            members.append((statement.target.id, statement))
        if constants.body and isinstance(constants.body[0], Expr):
            constants.body[0].value = Constant(
                value=cls._class_docstring(members=members),
            )

    @classmethod
    def _rewrite_imports(
        cls,
        *,
        tree: Module,
        moved_by_module: dict[str, frozenset[str]],
        current_module: str = "",
        current_is_package: bool = False,
    ) -> None:
        """Rewrite direct imports of moved constants.

        Args:
            tree: Module whose imports are updated.
            moved_by_module: Moved names indexed by module.
            current_module: Dotted name of this module.
            current_is_package: Whether this module is a package initializer.

        """
        rewritten: list[stmt] = []
        emitted: dict[str, str] = {}
        replacements: dict[str, str | tuple[str, str]] = {}
        collector: BindingCollector = BindingCollector(nested=False)
        collector.visit(node=tree)
        occupied: set[str] = set(collector.names)
        for statement in tree.body:
            if not isinstance(statement, ImportFrom):
                rewritten.append(statement)
                continue
            resolved: str | None = cls._resolve_import_from(
                statement=statement,
                current_module=current_module,
                current_is_package=current_is_package,
            )
            if resolved not in moved_by_module:
                rewritten.append(statement)
                continue
            moved: frozenset[str] = moved_by_module[resolved]
            retained: list[alias] = [
                item for item in statement.names if item.name not in moved
            ]
            direct: list[alias] = [
                item for item in statement.names if item.name in moved
            ]
            if retained:
                statement.names = retained
                rewritten.append(statement)
            if direct:
                qualifier: str | None = emitted.get(resolved)
                if qualifier is None:
                    qualifier = "Constants"
                    if qualifier in occupied:
                        base: str = "_GroupFinalConstants"
                        qualifier = base
                        suffix: int = 2
                        while qualifier in occupied:
                            qualifier = f"{base}_{suffix}"
                            suffix += 1
                    occupied.add(qualifier)
                    emitted[resolved] = qualifier
                    rewritten.append(
                        ImportFrom(
                            module=statement.module,
                            names=[
                                alias(
                                    name="Constants",
                                    asname=(
                                        None
                                        if qualifier == "Constants"
                                        else qualifier
                                    ),
                                ),
                            ],
                            level=statement.level,
                        ),
                    )
                replacements.update(
                    {
                        item.asname or item.name: (
                            qualifier,
                            _member_name(name=item.name),
                        )
                        for item in direct
                    },
                )
        tree.body = rewritten
        if replacements:
            DirectImportReferenceTransformer(replacements=replacements).visit(
                node=tree,
            )

    @classmethod
    def _module_aliases(
        cls,
        *,
        tree: Module,
        moved_by_module: dict[str, frozenset[str]],
        current_module: str = "",
        current_is_package: bool = False,
    ) -> dict[str, frozenset[str]]:
        """Find module aliases that may reference moved constants.

        Args:
            tree: Parsed module.
            moved_by_module: Moved names indexed by module.
            current_module: Dotted name of this module.
            current_is_package: Whether this module is a package initializer.

        Returns:
            Alias-to-moved-names mapping.

        """
        aliases: dict[str, frozenset[str]] = {}
        for statement in tree.body:
            if isinstance(statement, Import):
                for imported in statement.names:
                    if imported.name in moved_by_module:
                        aliases[
                            imported.asname
                            or imported.name.split(sep=".", maxsplit=1)[0]
                        ] = moved_by_module[imported.name]
                continue
            if not isinstance(statement, ImportFrom):
                continue
            resolved: str | None = cls._resolve_import_from(
                statement=statement,
                current_module=current_module,
                current_is_package=current_is_package,
            )
            if resolved is None:
                continue
            for imported in statement.names:
                imported_module: str = f"{resolved}.{imported.name}"
                if imported_module in moved_by_module:
                    aliases[imported.asname or imported.name] = (
                        moved_by_module[imported_module]
                    )
        return aliases

    @classmethod
    def _constants_aliases(
        cls,
        *,
        tree: Module,
        members_by_module: dict[str, dict[str, str]],
        current_module: str = "",
        current_is_package: bool = False,
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        """Resolve imported Constants classes and their module qualifiers.

        Args:
            tree: Module whose import statements are analyzed.
            members_by_module: Generated member renames indexed by module.
            current_module: Dotted name of the module being transformed.
            current_is_package: Whether the module file is ``__init__.py``.

        Returns:
            Class-alias member maps and module-alias member maps.

        """
        class_aliases: dict[str, dict[str, str]] = {}
        module_aliases: dict[str, dict[str, str]] = {}
        for statement in tree.body:
            if isinstance(statement, Import):
                for imported in statement.names:
                    replacements: dict[str, str] | None = (
                        members_by_module.get(imported.name)
                    )
                    if replacements:
                        module_aliases[
                            imported.asname
                            or imported.name.split(sep=".", maxsplit=1)[0]
                        ] = replacements
                continue
            if not isinstance(statement, ImportFrom):
                continue
            resolved: str | None = cls._resolve_import_from(
                statement=statement,
                current_module=current_module,
                current_is_package=current_is_package,
            )
            if resolved is None:
                continue
            provider_members: dict[str, str] | None = members_by_module.get(
                resolved,
            )
            for imported in statement.names:
                if imported.name == "Constants" and provider_members:
                    class_aliases[imported.asname or imported.name] = (
                        provider_members
                    )
                    continue
                imported_module: str = f"{resolved}.{imported.name}"
                replacements = members_by_module.get(imported_module)
                if replacements:
                    module_aliases[imported.asname or imported.name] = (
                        replacements
                    )
        return class_aliases, module_aliases

    @staticmethod
    def _parse_trees(*, paths: tuple[Path, ...]) -> dict[Path, Module]:
        """Parse collected modules, skipping files that vanished.

        Collection runs ahead of analysis, so a source can disappear
        between the two — a concurrent cleanup deleting generated files
        must not abort the whole run.

        Args:
            paths: Python files collected for this run.

        Returns:
            Parsed module trees keyed by path, in collection order.

        """
        trees: dict[Path, Module] = {}
        for path in paths:
            try:
                text: str = path.read_text(encoding="utf-8")
            except OSError:
                trace(step=f"group final: {path} vanished, skipped", depth=3)
                continue
            trees[path] = parse(source=text, filename=str(object=path))
        return trees

    @staticmethod
    def _without_unsafe_names(
        *,
        plan: ModulePlan,
        tree: Module,
        unsafe: set[str],
    ) -> ModulePlan | None:
        """Keep the largest contiguous safe subset of one provider plan.

        Args:
            plan: Constants plan being filtered.
            tree: Provider module's parsed source.
            unsafe: Constant names ambiguous inside importing modules.

        Returns:
            Reduced plan covering the largest safe run, or None.

        """
        names: frozenset[str] = plan.names - unsafe
        positions: list[tuple[int, str]] = [
            (index, statement.target.id)
            for index, statement in enumerate(iterable=tree.body)
            if isinstance(statement, AnnAssign)
            and isinstance(statement.target, Name)
            and statement.target.id in names
        ]
        if not positions:
            return None
        groups: list[list[tuple[int, str]]] = []
        for position in positions:
            if groups and position[0] == groups[-1][-1][0] + 1:
                groups[-1].append(position)
            else:
                groups.append([position])
        selected: list[tuple[int, str]] = max(
            groups,
            key=lambda group: (len(group), -group[0][0]),
        )
        return ModulePlan(
            path=plan.path,
            module_name=plan.module_name,
            names=frozenset(name for _, name in selected),
            insertion_index=selected[0][0],
            merge=plan.merge,
        )

    @staticmethod
    def _module_rebinds(
        *,
        tree: Module,
        import_statement: Import | ImportFrom,
        name: str,
    ) -> bool:
        """Return whether another top-level statement binds an import name.

        Args:
            tree: Module containing the import statement.
            import_statement: The import statement itself, skipped.
            name: Local bound name produced by the import.

        Returns:
            Whether another module-level statement rebinds ``name``.

        """
        for statement in tree.body:
            if statement is import_statement:
                continue
            collector: BindingCollector = BindingCollector(nested=False)
            collector.visit(node=statement)
            if name in collector.names:
                return True
        return False

    @staticmethod
    def _resolve_import_from(
        *,
        statement: ImportFrom,
        current_module: str,
        current_is_package: bool,
    ) -> str | None:
        """Resolve a from-import to an absolute module name.

        Args:
            statement: Import statement to resolve.
            current_module: Dotted name of the containing module.
            current_is_package: Whether the containing file is ``__init__.py``.

        Returns:
            Absolute imported module name, or None above the package root.

        """
        if statement.level == 0:
            return statement.module
        package: list[str] = current_module.split(sep=".")
        if not current_is_package:
            package = package[:-1]
        ascend: int = statement.level - 1
        if ascend > len(package):
            return None
        base: list[str] = package[: len(package) - ascend]
        if statement.module:
            base.extend(statement.module.split(sep="."))
        return ".".join(base)

    @staticmethod
    def _has_binding_conflict(
        *,
        binding: ConstantBinding,
        tree: Module,
    ) -> bool:
        """Return whether another binding shadows or replaces a candidate.

        Moving a module binding is unsafe when the same spelling is bound in
        another statement or nested scope. Refusing that candidate lets the
        simple reference rewrite remain semantically exact.

        Args:
            binding: Candidate module constant.
            tree: Containing module.

        Returns:
            True when another binding of the name exists.

        """
        for index, statement in enumerate(iterable=tree.body):
            if index == binding.statement_index:
                continue
            collector: BindingCollector = BindingCollector()
            collector.visit(node=statement)
            if binding.name in collector.names:
                return True
        return False

    @staticmethod
    def _uppercase(*, name: str) -> bool:
        """Check the requested uppercase naming convention.

        Args:
            name: Binding name.

        Returns:
            True for uppercase names, optionally prefixed by underscores,
            whose public member form remains a valid identifier.

        """
        stripped: str = name.lstrip("_")
        return (
            stripped.isidentifier()
            and stripped == stripped.upper()
            and any(character.isalpha() for character in stripped)
        )

    @staticmethod
    def _is_final(*, annotation: AST) -> bool:
        """Determine whether an annotation is typing.Final-like.

        Args:
            annotation: Assignment annotation.

        Returns:
            True when Final is the annotation root.

        """
        root: AST = (
            annotation.value
            if isinstance(annotation, Subscript)
            else annotation
        )
        return (isinstance(root, Name) and root.id == "Final") or (
            isinstance(root, Attribute) and root.attr == "Final"
        )

    @staticmethod
    def _prologue_index(*, tree: Module) -> int:
        """Find the first body index after the docstring and imports.

        The ``Constants`` class must follow the module docstring, every
        ``from __future__ import`` and the ordinary import block: its
        annotations reference ``Final`` and its values may reference any
        imported name.

        Args:
            tree: Parsed module.

        Returns:
            Lowest legal insertion index.

        """
        index: int = int(
            bool(tree.body)
            and isinstance(tree.body[0], Expr)
            and isinstance(tree.body[0].value, Constant)
            and isinstance(tree.body[0].value.value, str),
        )
        for position, statement in enumerate(iterable=tree.body):
            if isinstance(statement, (Import, ImportFrom)):
                index = max(index, position + 1)
        return index

    @staticmethod
    def _leading_header(*, source: str) -> str:
        """Collect shebang and comment lines preceding the first code.

        ``ast.unparse`` drops comments, so rewritten files would lose
        their ``#!`` line and copyright header; the originals are
        captured here and re-prepended to the rendered module.

        Args:
            source: Original module text.

        Returns:
            The leading comment block, or ``""``.

        """
        lines: list[str] = []
        for line in source.splitlines(keepends=True):
            stripped: str = line.strip()
            if stripped == "" or stripped.startswith("#"):
                lines.append(line)
                continue
            break
        return "".join(lines)

    @staticmethod
    def _loaded_names(*, node: AST) -> set[str]:
        """Collect loaded names below an AST node.

        Args:
            node: AST subtree.

        Returns:
            Loaded identifier names.

        """
        collector: NameCollector = NameCollector()
        collector.visit(node=node)
        return collector.names

    @staticmethod
    def _top_level_definitions(*, tree: Module) -> dict[str, int]:
        """Map top-level definitions to their statement positions.

        Args:
            tree: Parsed module.

        Returns:
            Name-to-statement-index mapping.

        """
        definitions: dict[str, int] = {}
        for index, statement in enumerate(iterable=tree.body):
            if isinstance(
                statement,
                (ClassDef, FunctionDef, AsyncFunctionDef),
            ):
                definitions[statement.name] = index
            elif isinstance(statement, (Import, ImportFrom)):
                for imported in statement.names:
                    definitions[
                        imported.asname
                        or imported.name.split(sep=".", maxsplit=1)[0]
                    ] = index
            elif isinstance(statement, (AnnAssign, Assign)):
                collector: BindingCollector = BindingCollector(nested=False)
                collector.visit(node=statement)
                definitions.update(dict.fromkeys(collector.names, index))
        return definitions

    @staticmethod
    def _generated_constants_class(*, tree: Module) -> ClassDef | None:
        """Return the Constants class previously generated by this tool.

        Args:
            tree: Module whose body is searched.

        Returns:
            The generated ``Constants`` class node, or None.

        """
        for statement in tree.body:
            if not isinstance(statement, ClassDef):
                continue
            if statement.name != "Constants":
                continue
            if not statement.body:
                continue
            first: stmt = statement.body[0]
            if (
                isinstance(first, Expr)
                and isinstance(first.value, Constant)
                and isinstance(first.value.value, str)
                and first.value.value.startswith(
                    "Group module-level constants.",
                )
            ):
                return statement
        return None

    @staticmethod
    def _extend_docstring(
        *,
        docstring: str,
        members: list[tuple[str, AnnAssign]],
    ) -> str:
        """Append member entries to an existing ``Attributes`` block.

        Args:
            docstring: Existing ``Constants`` class docstring.
            members: Member name and original annotated assignment
                pairs being merged.

        Returns:
            Docstring with the merged members listed.

        """
        lines: list[str] = docstring.split(sep="\n")
        last_attribute: int = max(
            (
                index
                for index, line in enumerate(iterable=lines)
                if line.startswith("        ")
            ),
            default=len(lines) - 1,
        )
        lines[last_attribute + 1 : last_attribute + 1] = [
            f"        {member}: Grouped module constant."
            for member, _ in members
        ]
        return "\n".join(lines)

    @staticmethod
    def _class_docstring(*, members: list[tuple[str, AnnAssign]]) -> str:
        """Build the Google-style docstring for the generated class.

        Args:
            members: Member name and original annotated assignment
                pairs in emission order.

        Returns:
            Docstring listing every grouped constant in an
            ``Attributes`` block.

        """
        lines: list[str] = [
            "Group module-level constants.",
            "",
            "    Attributes:",
        ]
        for member, statement in members:
            del statement
            lines.append(f"        {member}: Grouped module constant.")
        lines.extend(("", "    "))
        return "\n".join(lines)

    @staticmethod
    def _typing_name(*, tree: Module, imported: str) -> str:
        """Choose a collision-free local name for a typing import.

        Args:
            tree: Original module.
            imported: Typing symbol to import.

        Returns:
            Bare name when safe, otherwise a deterministic private alias.

        """
        bindings: list[tuple[str, str | None]] = []
        for statement in tree.body:
            if isinstance(statement, ImportFrom):
                bindings.extend(
                    (item.asname or item.name, statement.module)
                    for item in statement.names
                )
                continue
            collector: BindingCollector = BindingCollector(nested=False)
            collector.visit(node=statement)
            bindings.extend((name, None) for name in collector.names)
        if all(
            name != imported or module == "typing" for name, module in bindings
        ):
            return imported
        occupied: set[str] = {name for name, _ in bindings}
        base: str = f"_group_final_{imported}"
        candidate: str = base
        suffix: int = 2
        while candidate in occupied:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _import_name_key(name: str) -> tuple[int, str]:
        """Compute the isort member-order key for one imported name.

        Args:
            name: Imported symbol name.

        Returns:
            Sort key ordering constants first, classes second and
            plain names last, case-insensitively inside each group.

        """
        group: int = 0 if name.isupper() else 1 if name[:1].isupper() else 2
        return group, name.lower()

    @staticmethod
    def _typing_import_index(*, tree: Module) -> int:
        """Find the sorted insertion index for a typing import.

        Args:
            tree: Module whose import block is scanned.

        Returns:
            Body index placing ``from typing import ...`` in sorted
            order among the module's standard-library imports, after
            the docstring and ``__future__`` imports.

        """
        index: int = int(
            bool(tree.body)
            and isinstance(tree.body[0], Expr)
            and isinstance(tree.body[0].value, Constant)
            and isinstance(tree.body[0].value.value, str),
        )
        target: tuple[str, int] = ("typing", 1)
        for position, statement in enumerate(iterable=tree.body):
            base: str
            kind: int
            if isinstance(statement, ImportFrom):
                if statement.module is None or statement.level != 0:
                    continue
                base = statement.module.split(sep=".", maxsplit=1)[0]
                kind = 1
            elif isinstance(statement, Import):
                base = min(
                    item.name.split(sep=".", maxsplit=1)[0]
                    for item in statement.names
                )
                kind = 0
            else:
                continue
            if base not in stdlib_module_names:
                continue
            if (base, kind) > target:
                return position
            index = position + 1
        return index

    def _drop_unsafe_cross_module_plans(
        self,
        *,
        plans: dict[Path, ModulePlan],
        modules: dict[Path, str],
        trees: dict[Path, Module],
    ) -> dict[Path, ModulePlan]:
        """Drop provider members whose consumers cannot be rewritten safely.

        A star import has no individual alias to rewrite safely. Leaving the
        provider untouched is preferable to producing a consumer that fails
        at import time.

        Args:
            plans: Initially eligible provider plans.
            modules: Import name for every source path.
            trees: Parsed source modules.

        Returns:
            Plans excluding star-imported providers.

        """
        unsafe: dict[str, set[str]] = {}
        plans_by_module: dict[str, ModulePlan] = {
            plan.module_name: plan for plan in plans.values()
        }
        for path, tree in trees.items():
            for statement in tree.body:
                self._collect_unsafe_imports(
                    statement=statement,
                    tree=tree,
                    current=(modules[path], path.name == "__init__.py"),
                    plans_by_module=plans_by_module,
                    unsafe=unsafe,
                )
        filtered: dict[Path, ModulePlan] = {}
        for path, plan in plans.items():
            retained: ModulePlan | None = self._without_unsafe_names(
                plan=plan,
                tree=trees[path],
                unsafe=unsafe.get(plan.module_name, set()),
            )
            if retained is not None:
                filtered[path] = retained
        return filtered

    def _collect_unsafe_imports(
        self,
        *,
        statement: stmt,
        tree: Module,
        current: tuple[str, bool],
        plans_by_module: dict[str, ModulePlan],
        unsafe: dict[str, set[str]],
    ) -> None:
        """Record provider members made ambiguous by one import statement.

        Args:
            statement: Import statement being analyzed.
            tree: Module containing the import statement.
            current: Module name and package flag of ``tree``.
            plans_by_module: Constants plans indexed by module name.
            unsafe: Ambiguous constant names accumulated per module.

        """
        if isinstance(statement, Import):
            for item in statement.names:
                plan: ModulePlan | None = plans_by_module.get(item.name)
                local: str = (
                    item.asname or item.name.split(sep=".", maxsplit=1)[0]
                )
                if plan is not None and self._module_rebinds(
                    tree=tree,
                    import_statement=statement,
                    name=local,
                ):
                    unsafe.setdefault(item.name, set()).update(plan.names)
            return
        if not isinstance(statement, ImportFrom):
            return
        resolved: str | None = self._resolve_import_from(
            statement=statement,
            current_module=current[0],
            current_is_package=current[1],
        )
        if resolved is None:
            return
        direct_plan: ModulePlan | None = plans_by_module.get(resolved)
        if direct_plan is not None:
            self._collect_unsafe_direct_imports(
                statement=statement,
                tree=tree,
                module=resolved,
                plan=direct_plan,
                unsafe=unsafe,
            )
        for item in statement.names:
            imported_module: str = f"{resolved}.{item.name}"
            submodule_plan: ModulePlan | None = plans_by_module.get(
                imported_module,
            )
            if submodule_plan is not None and self._module_rebinds(
                tree=tree,
                import_statement=statement,
                name=item.asname or item.name,
            ):
                unsafe.setdefault(imported_module, set()).update(
                    submodule_plan.names,
                )

    def _collect_unsafe_direct_imports(
        self,
        *,
        statement: ImportFrom,
        tree: Module,
        module: str,
        plan: ModulePlan,
        unsafe: dict[str, set[str]],
    ) -> None:
        """Record unsafe direct and star imports from one provider.

        Args:
            statement: From-import statement being analyzed.
            tree: Module containing the import statement.
            module: Absolute provider module the statement imports.
            plan: Constants plan of the provider module.
            unsafe: Ambiguous constant names accumulated per module.

        """
        if any(item.name == "*" for item in statement.names):
            unsafe.setdefault(module, set()).update(plan.names)
            return
        for item in statement.names:
            if item.name in plan.names and self._module_rebinds(
                tree=tree,
                import_statement=statement,
                name=item.asname or item.name,
            ):
                unsafe.setdefault(module, set()).add(item.name)

    def _python_files(self) -> list[Path]:
        """Return eligible Python files below the source root.

        Excluded directories are pruned during the walk, so generated,
        cached, dependency, hidden, mutation-testing and bundled trees
        are never descended into; an excluded file therefore never
        reaches parsing, analysis or rewriting.

        Returns:
            Deterministically ordered Python paths.

        """
        if self._explicit_files is not None:
            return [
                path for path in self._explicit_files if path.suffix == ".py"
            ]
        found: list[Path] = []
        for directory, dirnames, filenames in walk(top=self._root):
            relative_dir: Path = Path(directory).relative_to(self._root)
            dirnames[:] = [
                name
                for name in dirnames
                if not self._is_excluded(path=relative_dir / name)
                and not is_reports_tree(directory=Path(directory) / name)
            ]
            found.extend(
                self._root / relative_dir / name
                for name in filenames
                if Path(name).suffix == ".py"
                and (not self._is_excluded(path=relative_dir / name))
            )
        return sorted(found, key=lambda path: path.as_posix())

    def _module_name(self, *, path: Path) -> str:
        """Resolve a source path to its import-style module name.

        Args:
            path: Python source file.

        Returns:
            Dotted module name relative to the source root.

        """
        relative: Path = path.relative_to(self._root).with_suffix(suffix="")
        parts: tuple[str, ...] = relative.parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    def _plan(
        self,
        *,
        path: Path,
        module_name: str,
        tree: Module,
    ) -> ModulePlan | None:
        """Build the maximal safe single-class plan for a module.

        Args:
            path: Module source path.
            module_name: Import-style module name.
            tree: Parsed module.

        Returns:
            Safe transformation plan, or None when nothing can move.

        """
        candidates: tuple[ConstantBinding, ...] = tuple(
            (
                binding
                for index, statement in enumerate(iterable=tree.body)
                if (
                    binding := self._candidate(
                        statement=statement,
                        statement_index=index,
                    )
                )
                is not None
            ),
        )
        if not candidates:
            return None
        merge_class: ClassDef | None = self._generated_constants_class(
            tree=tree,
        )
        if not merge_class and "Constants" in self._top_level_definitions(
            tree=tree,
        ):
            return None
        if merge_class is not None:
            taken: set[str] = {
                statement.target.id
                for statement in merge_class.body
                if isinstance(statement, AnnAssign)
                and isinstance(statement.target, Name)
            }
            candidates = tuple(
                binding
                for binding in candidates
                if _member_name(name=binding.name) not in taken
            )
            if not candidates:
                return None
        duplicates: set[str] = set()
        seen: set[str] = set()
        for binding in candidates:
            member: str = _member_name(name=binding.name)
            (duplicates if member in seen else seen).add(member)
        candidates = tuple(
            binding
            for binding in candidates
            if _member_name(name=binding.name) not in duplicates
        )
        if not candidates:
            return None
        candidates = tuple(
            binding
            for binding in candidates
            if not self._has_binding_conflict(binding=binding, tree=tree)
        )
        if not candidates:
            return None
        groups: list[list[ConstantBinding]] = []
        for binding in candidates:
            if (
                groups
                and binding.statement_index
                == groups[-1][-1].statement_index + 1
            ):
                groups[-1].append(binding)
            else:
                groups.append([binding])
        selected: list[ConstantBinding] = max(
            groups,
            key=lambda group: (len(group), -group[0].statement_index),
        )
        return ModulePlan(
            path=path,
            module_name=module_name,
            names=frozenset(binding.name for binding in selected),
            insertion_index=selected[0].statement_index,
            merge=merge_class is not None,
        )

    def _required_insertion_index(
        self,
        *,
        binding: ConstantBinding,
        tree: Module,
        candidate_names: frozenset[str],
    ) -> int:
        """Find the first position after dependencies of a candidate.

        Args:
            binding: Candidate being analyzed.
            tree: Parsed module.
            candidate_names: Names of all Final candidates.

        Returns:
            Required module-body insertion index.

        """
        dependencies: set[str] = set()
        if binding.statement.value is not None:
            dependencies = (
                self._loaded_names(node=binding.statement.value)
                - candidate_names
            )
        definitions: dict[str, int] = self._top_level_definitions(tree=tree)
        return max(
            (
                definitions[name] + 1
                for name in dependencies
                if name in definitions
            ),
            default=0,
        )

    def _used_before(
        self,
        *,
        name: str,
        tree: Module,
        before_index: int,
        ignored_statement_indices: frozenset[int],
    ) -> bool:
        """Check whether a constant is needed before class insertion.

        Args:
            name: Candidate constant.
            tree: Parsed module.
            before_index: Proposed Constants insertion position.
            ignored_statement_indices: Candidate statements being moved.

        Returns:
            True when moving the binding would create an early reference.

        """
        return any(
            (
                name in self._loaded_names(node=statement)
                for index, statement in enumerate(
                    iterable=tree.body[:before_index],
                )
                if index not in ignored_statement_indices
            ),
        )

    def _transform_module(
        self,
        *,
        tree: Module,
        request: TransformRequest,
    ) -> Module:
        """Apply local and cross-module reference rewrites.

        Args:
            tree: Parsed module.
            request: Local plan and project-wide rewrite indexes.

        Returns:
            Transformed module AST.

        """
        plan: ModulePlan | None = request.plan
        if plan is not None:
            decorator_name: str = self._typing_name(
                tree=tree,
                imported="final",
            )
            tree = self._move_local_constants(
                tree=tree,
                plan=plan,
                decorator_name=decorator_name,
            )
            self._sync_typing_imports(tree=tree, decorator_name=decorator_name)
        current_members: dict[str, str] = request.members_by_module.get(
            request.current_module,
            {},
        )
        self._normalize_generated_class(
            tree=tree,
            replacements=current_members,
        )
        self._rewrite_imports(
            tree=tree,
            moved_by_module=request.moved_by_module,
            current_module=request.current_module,
            current_is_package=request.current_is_package,
        )
        aliases: dict[str, frozenset[str]] = self._module_aliases(
            tree=tree,
            moved_by_module=request.moved_by_module,
            current_module=request.current_module,
            current_is_package=request.current_is_package,
        )
        QualifiedReferenceTransformer(module_aliases=aliases).visit(node=tree)
        if plan is not None:
            LocalReferenceTransformer(names=plan.names).visit(node=tree)
        class_aliases, constants_module_aliases = self._constants_aliases(
            tree=tree,
            members_by_module=request.members_by_module,
            current_module=request.current_module,
            current_is_package=request.current_is_package,
        )
        ConstantsMemberTransformer(
            current=current_members,
            class_aliases=class_aliases,
            module_aliases=constants_module_aliases,
        ).visit(node=tree)
        return tree

    def _move_local_constants(
        self,
        *,
        tree: Module,
        plan: ModulePlan,
        decorator_name: str = "final",
    ) -> Module:
        """Replace selected module constants with a Constants class.

        Args:
            tree: Parsed module.
            plan: Movement plan.
            decorator_name: Collision-free local name for ``typing.final``.

        Returns:
            Module containing the new Constants class.

        """
        selected: list[AnnAssign] = [
            statement
            for statement in tree.body
            if isinstance(statement, AnnAssign)
            and isinstance(statement.target, Name)
            and (statement.target.id in plan.names)
        ]
        selected_ids: set[int] = {id(statement) for statement in selected}
        remaining: list[stmt] = [
            statement
            for statement in tree.body
            if id(statement) not in selected_ids
        ]
        removed_before: int = sum(
            (
                1
                for index, statement in enumerate(iterable=tree.body)
                if index < plan.insertion_index
                and id(statement) in selected_ids
            ),
        )
        insertion: int = plan.insertion_index - removed_before
        members: list[tuple[str, AnnAssign]] = []
        class_body: list[stmt] = []
        member_names: dict[str, str] = {
            name: _member_name(name=name) for name in plan.names
        }
        member_transformer: MemberReferenceTransformer = (
            MemberReferenceTransformer(replacements=member_names)
        )
        for statement in selected:
            target: AST = statement.target
            if not isinstance(target, Name):
                continue
            member: str = _member_name(name=target.id)
            members.append((member, statement))
            class_body.append(
                copy_location(
                    new_node=AnnAssign(
                        target=Name(id=member, ctx=Store()),
                        annotation=statement.annotation,
                        value=(
                            cast(
                                typ="expr",
                                val=member_transformer.visit(
                                    node=statement.value,
                                ),
                            )
                            if statement.value is not None
                            else None
                        ),
                        simple=1,
                    ),
                    old_node=statement,
                ),
            )
        if plan.merge:
            existing: ClassDef | None = self._generated_constants_class(
                tree=tree,
            )
            if existing is not None:
                generated_body: list[stmt] = existing.body
                generated_body.extend(class_body)
                first: stmt | None = (
                    existing.body[0] if existing.body else None
                )
                if (
                    isinstance(first, Expr)
                    and isinstance(first.value, Constant)
                    and isinstance(first.value.value, str)
                ):
                    first.value.value = self._extend_docstring(
                        docstring=first.value.value,
                        members=members,
                    )
            tree.body = remaining
            return tree
        class_body.insert(
            0,
            Expr(value=Constant(value=self._class_docstring(members=members))),
        )
        remaining.insert(
            insertion,
            ClassDef(
                name="Constants",
                bases=[],
                keywords=[],
                body=class_body,
                decorator_list=[Name(id=decorator_name, ctx=Load())],
                type_params=[],
            ),
        )
        tree.body = remaining
        return tree

    def _sync_typing_imports(
        self,
        *,
        tree: Module,
        decorator_name: str = "final",
    ) -> None:
        """Reconcile ``from typing`` imports with the generated class.

        Merges the ``ClassVar`` and ``final`` names required by the
        emitted ``Constants`` class into an existing ``from typing
        import ...`` statement in isort member order, drops a bare
        ``Final`` import left unused by the move, or inserts a new
        statement at the sorted position inside the module's
        standard-library import block when none exists.

        Args:
            tree: Module whose typing imports are synchronized.
            decorator_name: Local name used by the generated decorator.

        """
        required: dict[str, str | None] = {
            "final": None if decorator_name == "final" else decorator_name,
        }
        typing_import: ImportFrom | None = None
        for statement in tree.body:
            if (
                isinstance(statement, ImportFrom)
                and statement.level == 0
                and statement.module == "typing"
            ):
                if any(item.name == "*" for item in statement.names):
                    return
                typing_import = statement
                break
        if typing_import is not None:
            provided: set[str] = {
                item.asname or item.name for item in typing_import.names
            }
            typing_import.names += [
                alias(name=name, asname=asname)
                for name, asname in required.items()
                if (asname or name) not in provided
            ]
            typing_import.names.sort(
                key=lambda item: self._import_name_key(name=item.name),
            )
            if typing_import.names:
                return
            tree.body = [
                node for node in tree.body if node is not typing_import
            ]
        names: list[alias] = [
            alias(name=name, asname=required[name])
            for name in sorted(required, key=self._import_name_key)
        ]
        typing_index: int = self._typing_import_index(tree=tree)
        tree.body[typing_index:typing_index] = [
            ImportFrom(module="typing", names=names, level=0),
        ]


class DirectImportReferenceTransformer(ScopedReferenceTransformer):
    """Rewrite names imported directly from transformed modules."""

    def __init__(
        self,
        *,
        replacements: dict[str, str | tuple[str, str]],
    ) -> None:
        """Initialize direct-import replacements.

        Args:
            replacements: Local imported name to constant member name.

        """
        normalized: dict[str, tuple[str, str]] = {
            name: value if isinstance(value, tuple) else ("Constants", value)
            for name, value in replacements.items()
        }
        super().__init__(tracked=frozenset(normalized))
        self._replacements: dict[str, tuple[str, str]] = normalized

    def _rewrite(self, *, node: AST) -> AST:
        """Rewrite a direct imported constant reference.

        Args:
            node: Node being visited.

        Returns:
            Original or Constants-qualified expression.

        """
        if (
            isinstance(node, Name)
            and node.id in self._replacements
            and not self._is_blocked(name=node.id)
            and isinstance(node.ctx, Load)
        ):
            qualifier, member = self._replacements[node.id]
            return copy_location(
                new_node=Attribute(
                    value=Name(id=qualifier, ctx=Load()),
                    attr=member,
                    ctx=Load(),
                ),
                old_node=node,
            )
        return node


class Arguments(Namespace):
    """Typed command-line arguments.

    Attributes:
        root: Python source-tree root.
        dry_run: Whether the run analyzes without writing.

    """

    root: Path
    dry_run: bool


class Cli:
    """Command-line interface."""

    @classmethod
    def main(cls) -> int:
        """Run the command-line interface.

        Returns:
            Process exit status.

        """
        arguments: Arguments = cls.parser().parse_args(namespace=Arguments())
        report: ScanReport = FinalConstantsRefactor(
            root=arguments.root,
            dry_run=arguments.dry_run,
        ).run()
        _ = stdout.write(cls._summary(report=report))
        return 0

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the argument parser.

        Returns:
            Configured argument parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            description=(
                "Group safely movable module-level Final constants "
                "into Constants classes and update Python references."
            ),
        )
        _root: Action = parser.add_argument(
            "root",
            nargs="?",
            type=Path,
            default=Path.cwd(),
            help="Python source-tree root. Defaults to the current directory.",
        )
        _dry_run: Action = parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyze without writing. Omit to apply the changes.",
        )
        return parser

    @staticmethod
    def _summary(*, report: ScanReport) -> str:
        """Render the final compact run summary.

        Args:
            report: Aggregated run statistics.

        Returns:
            Newline-terminated table listing scanned, planned, moved and
            changed counts; ANSI colors decorate the header and counts
            when standard output is a terminal and ``NO_COLOR`` is unset.

        """
        enabled: bool = stdout.isatty() and "NO_COLOR" not in environ
        changed_label: str = (
            "files that would change" if report.dry_run else "files changed"
        )
        entries: tuple[tuple[str, int], ...] = (
            ("files scanned", report.files),
            ("modules planned", report.planned),
            ("constants moved", report.constants),
            (changed_label, report.changed),
        )
        width: int = max((len(label) for label, _ in entries))
        rows: list[str] = [
            "",
            _paint(
                text=f"{'metric'.ljust(width)}  count",
                color=Palette.bold,
                enabled=enabled,
            ),
        ]
        rows.extend(
            (
                f"{label:<{width}}  "
                + _paint(
                    text=f"{value:>5}",
                    color=Palette.cyan if value else Palette.dim,
                    enabled=enabled,
                )
                for label, value in entries
            ),
        )
        return "\n".join(rows) + "\n"


def main() -> int:
    """Run the constants refactoring CLI.

    Returns:
        Process exit status.

    """
    return Cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
