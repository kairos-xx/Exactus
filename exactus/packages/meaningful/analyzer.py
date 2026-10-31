# Copyright (c) 2026 João Lopes.
"""Analyze Python source semantics to estimate test necessity."""

from ast import (
    AST,
    AnnAssign,
    Assert,
    Assign,
    AsyncFor,
    AsyncFunctionDef,
    AsyncWith,
    Attribute,
    AugAssign,
    Await,
    BinOp,
    BoolOp,
    Call,
    ClassDef,
    Compare,
    Constant,
    Delete,
    Dict,
    Eq,
    Expr,
    For,
    FunctionDef,
    If,
    IfExp,
    Import,
    ImportFrom,
    List,
    Match,
    Module,
    Name,
    NamedExpr,
    Pass,
    Raise,
    Return,
    Set,
    Starred,
    Subscript,
    Try,
    TryStar,
    Tuple,
    TypeAlias,
    UnaryOp,
    While,
    With,
    Yield,
    YieldFrom,
    comprehension,
    iter_child_nodes,
    parse,
    stmt,
    walk,
)
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final, TypedDict, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        side_effect_names: Grouped module constant.
        side_effect_attributes: Grouped module constant.
        side_effect_prefixes: Grouped module constant.
        external_state_names: Grouped module constant.
        mutation_names: Grouped module constant.
        mutation_attributes: Grouped module constant.
        static_declaration_calls: Grouped module constant.
        computation_calls: Grouped module constant.
        usage: Grouped module constant.
        default_threshold: Grouped module constant.
        complex_cyclomatic_threshold: Grouped module constant.
        complex_nesting_threshold: Grouped module constant.
        complex_public_members_threshold: Grouped module constant.
        max_nesting_score: Grouped module constant.
        multi_call_behavior_threshold: Grouped module constant.
        multi_statement_behavior_threshold: Grouped module constant.

    """

    side_effect_names: Final[frozenset[str]] = frozenset(
        {
            "input",
            "open",
            "print",
            "datetime.date.today",
            "datetime.datetime.now",
            "datetime.datetime.utcnow",
            "os.chdir",
            "os.chmod",
            "os.chown",
            "os.environ.get",
            "os.getenv",
            "os.kill",
            "os.makedirs",
            "os.mkdir",
            "os.putenv",
            "os.remove",
            "os.removedirs",
            "os.rename",
            "os.replace",
            "os.rmdir",
            "os.system",
            "os.unlink",
            "os.unsetenv",
            "shutil.copy",
            "shutil.copy2",
            "shutil.copyfile",
            "shutil.copytree",
            "shutil.move",
            "random.choice",
            "random.choices",
            "random.randint",
            "random.random",
            "random.randrange",
            "random.shuffle",
            "random.uniform",
            "shutil.rmtree",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "subprocess.Popen",
            "subprocess.run",
            "sys.stderr.write",
            "sys.stdout.write",
            "time.monotonic",
            "time.time",
            "uuid.uuid4",
        },
    )
    side_effect_attributes: Final[frozenset[str]] = frozenset(
        {
            "chmod",
            "commit",
            "connect",
            "execute",
            "executemany",
            "hardlink_to",
            "mkdir",
            "open",
            "read_bytes",
            "read_text",
            "recv",
            "recvfrom",
            "rename",
            "replace",
            "request",
            "rmdir",
            "rollback",
            "send",
            "sendall",
            "sendto",
            "symlink_to",
            "touch",
            "unlink",
            "write",
            "write_bytes",
            "write_text",
        },
    )
    side_effect_prefixes: Final[frozenset[str]] = frozenset(
        {"httpx.", "requests.", "socket.", "urllib.request."},
    )
    external_state_names: Final[frozenset[str]] = frozenset(
        {"os.environ", "sys.argv"},
    )
    mutation_names: Final[frozenset[str]] = frozenset({"delattr", "setattr"})
    mutation_attributes: Final[frozenset[str]] = frozenset(
        {
            "add",
            "append",
            "clear",
            "discard",
            "extend",
            "insert",
            "pop",
            "remove",
            "reverse",
            "setdefault",
            "sort",
            "update",
        },
    )
    static_declaration_calls: Final[frozenset[str]] = frozenset(
        {
            "dataclasses.field",
            "enum.auto",
            "frozenset",
            "pathlib.Path",
            "pathlib.PurePath",
            "pathlib.PurePosixPath",
            "pathlib.PureWindowsPath",
            "typing.NewType",
            "typing.ParamSpec",
            "typing.TypeVar",
            "typing.TypeVarTuple",
        },
    )
    computation_calls: Final[frozenset[str]] = frozenset(
        {
            "abs",
            "all",
            "any",
            "bool",
            "bytes",
            "dict",
            "float",
            "int",
            "len",
            "list",
            "max",
            "min",
            "round",
            "set",
            "sorted",
            "str",
            "sum",
            "tuple",
        },
    )
    usage: Final[str] = "Usage: python_test_need.py FILE.py [--json]\n"
    default_threshold: Final[int] = 12
    complex_cyclomatic_threshold: Final[int] = 6
    complex_nesting_threshold: Final[int] = 3
    complex_public_members_threshold: Final[int] = 4
    max_nesting_score: Final[int] = 3
    multi_call_behavior_threshold: Final[int] = 2
    multi_statement_behavior_threshold: Final[int] = 2


type FunctionNode = FunctionDef | AsyncFunctionDef


class UnitTestLevel(StrEnum):
    """Available test-necessity classifications.

    Attributes:
        TEST_0: Stored ``TEST_0`` value.
        TEST_1: Stored ``TEST_1`` value.
        TEST_2: Stored ``TEST_2`` value.
        TEST_3: Stored ``TEST_3`` value.

    """

    TEST_0 = "TEST-0"
    TEST_1 = "TEST-1"
    TEST_2 = "TEST-2"
    TEST_3 = "TEST-3"


class Category(StrEnum):
    """Semantic categories corresponding to the test levels.

    Attributes:
        STRUCTURAL: Stored ``STRUCTURAL`` value.
        TRIVIAL: Stored ``TRIVIAL`` value.
        BEHAVIORAL: Stored ``BEHAVIORAL`` value.
        COMPLEX: Stored ``COMPLEX`` value.

    """

    STRUCTURAL = "structural"
    TRIVIAL = "trivial"
    BEHAVIORAL = "behavioral"
    COMPLEX = "complex"


class MetricsJson(TypedDict):
    """JSON representation of classification metrics.

    Attributes:
        cyclomatic_complexity: Stored ``cyclomatic_complexity`` value.
        branches: Stored ``branches`` value.
        loops: Stored ``loops`` value.
        exception_handlers: Stored ``exception_handlers`` value.
        raises: Stored ``raises`` value.
        boolean_decisions: Stored ``boolean_decisions`` value.
        comprehension_decisions: Stored ``comprehension_decisions`` value.
        computations: Stored ``computations`` value.
        side_effects: Stored ``side_effects`` value.
        mutations: Stored ``mutations`` value.
        behavioral_statements: Stored ``behavioral_statements`` value.
        runtime_calls: Stored ``runtime_calls`` value.
        substantive_callables: Stored ``substantive_callables`` value.
        trivial_callables: Stored ``trivial_callables`` value.
        public_behavioral_members: Stored ``public_behavioral_members`` value.
        module_runtime_statements: Stored ``module_runtime_statements`` value.
        max_control_nesting: Stored ``max_control_nesting`` value.

    """

    cyclomatic_complexity: int
    branches: int
    loops: int
    exception_handlers: int
    raises: int
    boolean_decisions: int
    comprehension_decisions: int
    computations: int
    side_effects: int
    mutations: int
    behavioral_statements: int
    runtime_calls: int
    substantive_callables: int
    trivial_callables: int
    public_behavioral_members: int
    module_runtime_statements: int
    max_control_nesting: int


class ClassificationJson(TypedDict):
    """JSON representation of a complete classification.

    Attributes:
        path: Stored ``path`` value.
        level: Stored ``level`` value.
        category: Stored ``category`` value.
        score: Stored ``score`` value.
        requires_unit_tests: Stored ``requires_unit_tests`` value.
        requires_execution: Stored ``requires_execution`` value.
        requires_branch_coverage: Stored ``requires_branch_coverage`` value.
        reasons: Stored ``reasons`` value.
        metrics: Stored ``metrics`` value.

    """

    path: str
    level: str
    category: str
    score: int
    requires_unit_tests: bool
    requires_execution: bool
    requires_branch_coverage: bool
    reasons: list[str]
    metrics: MetricsJson


@dataclass(frozen=True, slots=True, kw_only=True)
class Metrics:
    """Measured behavioral properties of one Python module.

    Attributes:
        cyclomatic_complexity: Stored ``cyclomatic_complexity`` value.
        branches: Stored ``branches`` value.
        loops: Stored ``loops`` value.
        exception_handlers: Stored ``exception_handlers`` value.
        raises: Stored ``raises`` value.
        boolean_decisions: Stored ``boolean_decisions`` value.
        comprehension_decisions: Stored ``comprehension_decisions`` value.
        computations: Stored ``computations`` value.
        side_effects: Stored ``side_effects`` value.
        mutations: Stored ``mutations`` value.
        behavioral_statements: Stored ``behavioral_statements`` value.
        runtime_calls: Stored ``runtime_calls`` value.
        substantive_callables: Stored ``substantive_callables`` value.
        trivial_callables: Stored ``trivial_callables`` value.
        public_behavioral_members: Stored ``public_behavioral_members`` value.
        module_runtime_statements: Stored ``module_runtime_statements`` value.
        max_control_nesting: Stored ``max_control_nesting`` value.

    """

    cyclomatic_complexity: int
    branches: int
    loops: int
    exception_handlers: int
    raises: int
    boolean_decisions: int
    comprehension_decisions: int
    computations: int
    side_effects: int
    mutations: int
    behavioral_statements: int
    runtime_calls: int
    substantive_callables: int
    trivial_callables: int
    public_behavioral_members: int
    module_runtime_statements: int
    max_control_nesting: int

    def to_json(self) -> MetricsJson:
        """Return a JSON-compatible metric mapping.

        Returns:
            The resulting value.

        """
        return MetricsJson(
            cyclomatic_complexity=self.cyclomatic_complexity,
            branches=self.branches,
            loops=self.loops,
            exception_handlers=self.exception_handlers,
            raises=self.raises,
            boolean_decisions=self.boolean_decisions,
            comprehension_decisions=self.comprehension_decisions,
            computations=self.computations,
            side_effects=self.side_effects,
            mutations=self.mutations,
            behavioral_statements=self.behavioral_statements,
            runtime_calls=self.runtime_calls,
            substantive_callables=self.substantive_callables,
            trivial_callables=self.trivial_callables,
            public_behavioral_members=self.public_behavioral_members,
            module_runtime_statements=self.module_runtime_statements,
            max_control_nesting=self.max_control_nesting,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Classification:
    """Test recommendation and evidence for one Python module.

    Attributes:
        path: Stored ``path`` value.
        level: Stored ``level`` value.
        category: Stored ``category`` value.
        score: Stored ``score`` value.
        requires_unit_tests: Stored ``requires_unit_tests`` value.
        requires_execution: Stored ``requires_execution`` value.
        requires_branch_coverage: Stored ``requires_branch_coverage`` value.
        reasons: Stored ``reasons`` value.
        metrics: Stored ``metrics`` value.

    """

    path: Path
    level: UnitTestLevel
    category: Category
    score: int
    requires_unit_tests: bool
    requires_execution: bool
    requires_branch_coverage: bool
    reasons: tuple[str, ...]
    metrics: Metrics

    def to_json(self) -> ClassificationJson:
        """Return the classification in a stable JSON-compatible shape.

        Returns:
            The resulting value.

        """
        return ClassificationJson(
            path=str(object=self.path),
            level=self.level.value,
            category=self.category.value,
            score=self.score,
            requires_unit_tests=self.requires_unit_tests,
            requires_execution=self.requires_execution,
            requires_branch_coverage=self.requires_branch_coverage,
            reasons=list(self.reasons),
            metrics=self.metrics.to_json(),
        )

    def render(self) -> str:
        """Render a compact human-readable report.

        Returns:
            The resulting value.

        """
        return "\n".join(
            (
                f"file: {self.path}",
                f"classification: {self.level.value} ({self.category.value})",
                f"score: {self.score}",
                "unit tests required: "
                f"{('yes' if self.requires_unit_tests else 'no')}",
                "execution required: "
                f"{('yes' if self.requires_execution else 'no')}",
                (
                    f"branch coverage required: "
                    f"{('yes' if self.requires_branch_coverage else 'no')}"
                ),
                "metrics:",
                (
                    f"  cyclomatic complexity: "
                    f"{self.metrics.cyclomatic_complexity}"
                ),
                (
                    f"  behavioral statements: "
                    f"{self.metrics.behavioral_statements}"
                ),
                f"  branches: {self.metrics.branches}",
                f"  loops: {self.metrics.loops}",
                f"  exception handlers: {self.metrics.exception_handlers}",
                f"  side effects: {self.metrics.side_effects}",
                f"  mutations: {self.metrics.mutations}",
                f"  computations: {self.metrics.computations}",
                f"  runtime calls: {self.metrics.runtime_calls}",
                "  public behavioral members: "
                f"{self.metrics.public_behavioral_members}",
                "  module runtime statements: "
                f"{self.metrics.module_runtime_statements}",
                f"  max control nesting: {self.metrics.max_control_nesting}",
                "reasons:",
                *(f"  - {reason}" for reason in self.reasons),
                "",
            ),
        )


class PythonTestNeedClassifier:
    """Classify one Python file from its syntax and observable behavior."""

    _path: Path
    _tree: Module
    _imports: Mapping[str, str]
    _threshold: int

    def __init__(
        self,
        *,
        path: Path,
        threshold: int = Constants.default_threshold,
    ) -> None:
        """Load and parse a Python source file.

        Args:
                    path: Python source file to classify.

        Raises:
                    OSError: If the source file cannot be read.
                    SyntaxError: If the source is not valid Python.
                    ValueError: If the path does not identify a Python file.

        Args:
            path: Value supplied for ``path``.
            threshold: Value supplied for ``threshold``.

        Raises:
            ValueError: If the operation cannot be completed.

        """
        if threshold < 1:
            msg: str = "threshold must be at least 1"
            raise ValueError(msg)
        if path.suffix != ".py":
            msg = f"Expected a .py file, got: {path}"
            raise ValueError(msg)
        self._path = path
        self._threshold = threshold
        self._tree = parse(
            source=path.read_text(encoding="utf-8"),
            filename=str(object=path),
            mode="exec",
        )
        self._imports = MappingProxyType(mapping=self._import_bindings())

    def classify(self) -> Classification:
        """Measure the file and derive its test-necessity classification.

        Returns:
            The resulting value.

        """
        functions: tuple[FunctionNode, ...] = tuple(
            node
            for node in walk(node=self._tree)
            if isinstance(node, (FunctionDef, AsyncFunctionDef))
        )
        trivial_functions: tuple[FunctionNode, ...] = tuple(
            function
            for function in functions
            if not self._is_stub(function=function)
            and self._is_pure_delegate(function=function)
        )
        substantive_functions: tuple[FunctionNode, ...] = tuple(
            function
            for function in functions
            if not self._is_stub(function=function)
            and (not self._is_pure_delegate(function=function))
        )
        module_roots: tuple[stmt, ...] = self._module_runtime_roots()
        runtime_roots: tuple[AST, ...] = (
            *module_roots,
            *(
                statement
                for function in substantive_functions
                for statement in self._meaningful_body(body=function.body)
            ),
        )
        nodes: tuple[AST, ...] = tuple(
            {
                id(node): node
                for root in runtime_roots
                for node in walk(node=root)
            }.values(),
        )
        metrics: Metrics = self._metrics(
            nodes=nodes,
            substantive_functions=substantive_functions,
            trivial_functions=trivial_functions,
            module_runtime_statements=len(module_roots),
            runtime_roots=runtime_roots,
        )
        score: int = self._score(metrics=metrics)
        is_pure_entrypoint: bool = (
            self._path.name == "__main__.py"
            and metrics.substantive_callables == 0
            and (metrics.module_runtime_statements == 0)
        )
        has_hard_behavior: bool = any(
            (
                metrics.branches > 0,
                metrics.loops > 0,
                metrics.exception_handlers > 0,
                metrics.raises > 0,
                metrics.boolean_decisions > 0,
                metrics.comprehension_decisions > 0,
                metrics.computations > 0,
                metrics.side_effects > 0,
                metrics.mutations > 0,
                metrics.module_runtime_statements > 0,
                metrics.runtime_calls
                >= Constants.multi_call_behavior_threshold,
                metrics.behavioral_statements
                >= Constants.multi_statement_behavior_threshold,
            ),
        )
        is_complex: bool = has_hard_behavior and any(
            (
                score >= self._threshold,
                metrics.cyclomatic_complexity
                >= Constants.complex_cyclomatic_threshold,
                metrics.max_control_nesting
                >= Constants.complex_nesting_threshold,
                metrics.public_behavioral_members
                >= Constants.complex_public_members_threshold,
            ),
        )
        level: UnitTestLevel = self._test_level(
            has_hard_behavior=has_hard_behavior,
            has_runtime_behavior=metrics.substantive_callables > 0
            or metrics.trivial_callables > 0,
            is_complex=is_complex,
            is_pure_entrypoint=is_pure_entrypoint,
        )
        requires_unit_tests: bool = level in {
            UnitTestLevel.TEST_2,
            UnitTestLevel.TEST_3,
        }
        return Classification(
            path=self._path,
            level=level,
            category=self._category(level=level),
            score=score,
            requires_unit_tests=requires_unit_tests,
            requires_execution=level is not UnitTestLevel.TEST_0,
            requires_branch_coverage=requires_unit_tests
            and self._has_decisions(metrics=metrics),
            reasons=self._reasons(
                metrics=metrics,
                level=level,
                is_pure_entrypoint=is_pure_entrypoint,
            ),
            metrics=metrics,
        )

    @classmethod
    def _classes_in_body(cls, *, body: list[stmt]) -> tuple[ClassDef, ...]:
        """Return classes reachable without entering callable bodies.

        Args:
            body: Value supplied for ``body``.

        Returns:
            The resulting value.

        """
        direct_classes: tuple[ClassDef, ...] = tuple(
            statement for statement in body if isinstance(statement, ClassDef)
        )
        return (
            *direct_classes,
            *(
                nested_class
                for class_node in direct_classes
                for nested_class in cls._classes_in_body(body=class_node.body)
            ),
        )

    @classmethod
    def _meaningful_body(cls, *, body: list[stmt]) -> tuple[stmt, ...]:
        """Return a body without its optional leading docstring.

        Args:
            body: Value supplied for ``body``.

        Returns:
            The resulting value.

        """
        return tuple(
            (
                statement
                for index, statement in enumerate(iterable=body)
                if index > 0 or not cls._is_docstring(statement=statement)
            ),
        )

    @classmethod
    def _delegated_call(cls, *, statement: stmt) -> Call | None:
        """Extract the sole call from a delegation statement.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if isinstance(statement, (Expr, Return)) and isinstance(
            statement.value,
            Call,
        ):
            return cls._unwrap_system_exit(call=statement.value)
        if isinstance(statement, Raise) and isinstance(statement.exc, Call):
            return cls._unwrap_system_exit(call=statement.exc)
        return None

    @classmethod
    def _syntactic_name(cls, *, node: AST) -> str | None:
        """Return the dotted spelling of a statically addressable node.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        if isinstance(node, Name):
            return node.id
        if not isinstance(node, Attribute):
            return None
        prefix: str | None = cls._syntactic_name(node=node.value)
        return f"{prefix}.{node.attr}" if prefix is not None else node.attr

    @classmethod
    def _is_pure_main_guard(cls, *, statement: If) -> bool:
        """Return whether the main guard only invokes main().

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        return (
            cls._is_main_guard(node=statement)
            and len(statement.body) == 1
            and isinstance(statement.body[0], Expr)
            and isinstance(statement.body[0].value, Call)
            and isinstance(statement.body[0].value.func, Name)
            and (statement.body[0].value.func.id == "main")
            and (not statement.body[0].value.args)
            and (not statement.body[0].value.keywords)
            and (not statement.orelse)
        )

    @classmethod
    def _control_depth(cls, *, node: AST, depth: int) -> int:
        """Return the deepest nested control-flow depth below a node.

        Args:
            node: Value supplied for ``node``.
            depth: Value supplied for ``depth``.

        Returns:
            The resulting value.

        """
        next_depth: int = depth + int(
            isinstance(node, (If, For, AsyncFor, While, Try, TryStar, Match))
            and (not cls._is_main_guard(node=node)),
        )
        return max(
            (
                cls._control_depth(node=child, depth=next_depth)
                for child in iter_child_nodes(node=node)
            ),
            default=next_depth,
        )

    @staticmethod
    def _test_level(
        *,
        has_hard_behavior: bool,
        has_runtime_behavior: bool,
        is_complex: bool,
        is_pure_entrypoint: bool,
    ) -> UnitTestLevel:
        """Select a test level from the measured behavioral state.

        Args:
            has_hard_behavior: Value supplied for ``has_hard_behavior``.
            has_runtime_behavior: Value supplied for ``has_runtime_behavior``.
            is_complex: Value supplied for ``is_complex``.
            is_pure_entrypoint: Value supplied for ``is_pure_entrypoint``.

        Returns:
            The resulting value.

        """
        if is_pure_entrypoint or not (
            has_hard_behavior or has_runtime_behavior
        ):
            return UnitTestLevel.TEST_0
        if is_complex:
            return UnitTestLevel.TEST_3
        if has_hard_behavior:
            return UnitTestLevel.TEST_2
        return UnitTestLevel.TEST_1

    @staticmethod
    def _category(*, level: UnitTestLevel) -> Category:
        """Map a test level to its semantic category.

        Args:
            level: Value supplied for ``level``.

        Returns:
            The resulting value.

        """
        if level is UnitTestLevel.TEST_0:
            return Category.STRUCTURAL
        if level is UnitTestLevel.TEST_1:
            return Category.TRIVIAL
        if level is UnitTestLevel.TEST_2:
            return Category.BEHAVIORAL
        return Category.COMPLEX

    @staticmethod
    def _is_mutation(*, node: AST) -> bool:
        """Return whether a node mutates existing state.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        if isinstance(node, (AugAssign, Delete)):
            return True
        if isinstance(node, Assign):
            return any(
                isinstance(target, (Attribute, Subscript))
                for target in node.targets
            )
        return isinstance(node, AnnAssign) and isinstance(
            node.target,
            (Attribute, Subscript),
        )

    @staticmethod
    def _score(*, metrics: Metrics) -> int:
        """Calculate the weighted test-necessity score.

        Args:
            metrics: Value supplied for ``metrics``.

        Returns:
            The resulting value.

        """
        return (
            metrics.branches * 2
            + metrics.loops * 2
            + metrics.exception_handlers * 2
            + metrics.raises * 2
            + metrics.boolean_decisions
            + metrics.comprehension_decisions
            + metrics.computations
            + metrics.side_effects * 3
            + metrics.mutations * 2
            + metrics.public_behavioral_members
            + min(metrics.max_control_nesting, Constants.max_nesting_score)
        )

    @staticmethod
    def _reasons(
        *,
        metrics: Metrics,
        level: UnitTestLevel,
        is_pure_entrypoint: bool,
    ) -> tuple[str, ...]:
        """Explain the classification using stable machine-readable facts.

        Args:
            metrics: Value supplied for ``metrics``.
            level: Value supplied for ``level``.
            is_pure_entrypoint: Value supplied for ``is_pure_entrypoint``.

        Returns:
            The resulting value.

        """
        return tuple(
            reason
            for reason in (
                "pure entry-point delegation" if is_pure_entrypoint else None,
                "declarations/imports only"
                if level is UnitTestLevel.TEST_0 and (not is_pure_entrypoint)
                else None,
                f"{metrics.trivial_callables} pure delegation callable(s)"
                if metrics.trivial_callables > 0
                else None,
                f"{metrics.substantive_callables} substantive callable(s)"
                if metrics.substantive_callables > 0
                else None,
                f"{metrics.branches} branch decision(s)"
                if metrics.branches > 0
                else None,
                f"{metrics.loops} loop(s)" if metrics.loops > 0 else None,
                f"{metrics.exception_handlers} exception handler(s)"
                if metrics.exception_handlers > 0
                else None,
                f"{metrics.side_effects} external/I/O side effect(s)"
                if metrics.side_effects > 0
                else None,
                f"{metrics.mutations} state mutation(s)"
                if metrics.mutations > 0
                else None,
                f"{metrics.computations} computation(s)"
                if metrics.computations > 0
                else None,
                f"{metrics.module_runtime_statements} import-time statement(s)"
                if metrics.module_runtime_statements > 0
                else None,
                f"{metrics.runtime_calls} runtime call(s)"
                if metrics.runtime_calls
                >= Constants.multi_call_behavior_threshold
                else None,
                "high structural complexity"
                if level is UnitTestLevel.TEST_3
                else None,
            )
            if reason is not None
        )

    @staticmethod
    def _has_decisions(*, metrics: Metrics) -> bool:
        """Return whether meaningful alternative execution paths exist.

        Args:
            metrics: Value supplied for ``metrics``.

        Returns:
            The resulting value.

        """
        return any(
            (
                metrics.branches > 0,
                metrics.loops > 0,
                metrics.exception_handlers > 0,
                metrics.boolean_decisions > 0,
                metrics.comprehension_decisions > 0,
            ),
        )

    @staticmethod
    def _unwrap_system_exit(*, call: Call) -> Call:
        """Unwrap conventional ``raise SystemExit(delegate())`` calls.

        Args:
            call: Value supplied for ``call``.

        Returns:
            The resulting value.

        """
        if (
            isinstance(call.func, Name)
            and call.func.id == "SystemExit"
            and (len(call.args) == 1)
            and isinstance(call.args[0], Call)
            and (not call.keywords)
        ):
            return call.args[0]
        return call

    @staticmethod
    def _is_forwarding_expression(*, node: AST) -> bool:
        """Return whether an argument is forwarded without transformation.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        return isinstance(node, (Name, Constant, Attribute, Starred))

    @staticmethod
    def _statement_bindings(
        *,
        statement: Import | ImportFrom,
    ) -> tuple[tuple[str, str], ...]:
        """Return local/imported name pairs for one import statement.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if isinstance(statement, Import):
            return tuple(
                (
                    imported.asname
                    or imported.name.split(sep=".", maxsplit=1)[0],
                    imported.name
                    if imported.asname is not None
                    else imported.name.split(sep=".", maxsplit=1)[0],
                )
                for imported in statement.names
            )
        module_name: str = "." * statement.level + (statement.module or "")
        return tuple(
            (
                imported.asname or imported.name,
                f"{module_name}.{imported.name}"
                if module_name
                else imported.name,
            )
            for imported in statement.names
            if imported.name != "*"
        )

    @staticmethod
    def _is_docstring(*, statement: stmt) -> bool:
        """Return whether a statement is a literal string docstring.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        return (
            isinstance(statement, Expr)
            and isinstance(statement.value, Constant)
            and isinstance(statement.value.value, str)
        )

    @staticmethod
    def _is_type_checking_guard(*, statement: If) -> bool:
        """Return whether an if statement is a TYPE_CHECKING guard.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        return (
            isinstance(statement.test, Name)
            and statement.test.id == "TYPE_CHECKING"
        )

    @staticmethod
    def _is_main_guard(*, node: AST) -> bool:
        """Return whether a node is the canonical __main__ guard.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        return (
            isinstance(node, If)
            and isinstance(node.test, Compare)
            and isinstance(node.test.left, Name)
            and (node.test.left.id == "__name__")
            and (len(node.test.ops) == 1)
            and isinstance(node.test.ops[0], Eq)
            and (len(node.test.comparators) == 1)
            and isinstance(node.test.comparators[0], Constant)
            and (node.test.comparators[0].value == "__main__")
        )

    def _metrics(
        self,
        *,
        nodes: tuple[AST, ...],
        substantive_functions: tuple[FunctionNode, ...],
        trivial_functions: tuple[FunctionNode, ...],
        module_runtime_statements: int,
        runtime_roots: tuple[AST, ...],
    ) -> Metrics:
        """Calculate semantic metrics from selected runtime AST nodes.

        Args:
            nodes: Value supplied for ``nodes``.
            substantive_functions: Substantive callable nodes.
            trivial_functions: Value supplied for ``trivial_functions``.
            module_runtime_statements: Module-level runtime statement count.
            runtime_roots: Value supplied for ``runtime_roots``.

        Returns:
            The resulting value.

        """
        branches: int = sum(
            1
            for node in nodes
            if isinstance(node, (If, IfExp))
            and (not self._is_main_guard(node=node))
        ) + sum(len(node.cases) for node in nodes if isinstance(node, Match))
        loops: int = sum(
            1 for node in nodes if isinstance(node, (For, AsyncFor, While))
        )
        exception_handlers: int = sum(
            len(node.handlers)
            for node in nodes
            if isinstance(node, (Try, TryStar))
        )
        boolean_decisions: int = sum(
            max(0, len(node.values) - 1)
            for node in nodes
            if isinstance(node, BoolOp)
        )
        comprehension_decisions: int = sum(
            len(node.ifs) for node in nodes if isinstance(node, comprehension)
        )
        computations: int = sum(
            1
            for node in nodes
            if isinstance(
                node,
                (
                    BinOp,
                    UnaryOp,
                    Compare,
                    IfExp,
                    NamedExpr,
                    Dict,
                    List,
                    Set,
                    Tuple,
                ),
            )
            or (
                isinstance(node, Call) and self._is_computation_call(node=node)
            )
        )
        runtime_calls: int = sum(1 for node in nodes if isinstance(node, Call))
        side_effects: int = sum(
            1
            for node in nodes
            if (
                isinstance(node, Call) and self._is_side_effect_call(node=node)
            )
            or (
                isinstance(node, Subscript)
                and self._is_external_state_access(node=node)
            )
        )
        mutations: int = sum(
            1
            for node in nodes
            if self._is_mutation(node=node)
            or (isinstance(node, Call) and self._is_mutating_call(node=node))
        )
        behavioral_statements: int = sum(
            1
            for node in nodes
            if isinstance(node, stmt)
            and self._is_behavioral_statement(statement=node)
        )
        public_function_ids: frozenset[int] = frozenset(
            id(function) for function in self._public_callables()
        )
        public_behavioral_members: int = sum(
            1
            for function in substantive_functions
            if id(function) in public_function_ids
        )
        cyclomatic_complexity: int = (
            1
            + branches
            + loops
            + exception_handlers
            + boolean_decisions
            + comprehension_decisions
        )
        return Metrics(
            cyclomatic_complexity=cyclomatic_complexity,
            branches=branches,
            loops=loops,
            exception_handlers=exception_handlers,
            raises=sum(1 for node in nodes if isinstance(node, Raise)),
            boolean_decisions=boolean_decisions,
            comprehension_decisions=comprehension_decisions,
            computations=computations,
            side_effects=side_effects,
            mutations=mutations,
            behavioral_statements=behavioral_statements,
            runtime_calls=runtime_calls,
            substantive_callables=len(substantive_functions),
            trivial_callables=len(trivial_functions),
            public_behavioral_members=public_behavioral_members,
            module_runtime_statements=module_runtime_statements,
            max_control_nesting=max(
                (
                    self._control_depth(node=root, depth=0)
                    for root in runtime_roots
                ),
                default=0,
            ),
        )

    def _module_runtime_roots(self) -> tuple[stmt, ...]:
        """Return module/class statements executed outside callable bodies.

        Returns:
            The resulting value.

        """
        return (
            *(
                statement
                for statement in self._tree.body
                if not isinstance(
                    statement,
                    (FunctionDef, AsyncFunctionDef, ClassDef),
                )
                and (
                    not self._is_structural_module_statement(
                        statement=statement,
                    )
                )
            ),
            *(
                statement
                for class_node in self._module_classes()
                for statement in class_node.body
                if not isinstance(
                    statement,
                    (FunctionDef, AsyncFunctionDef, ClassDef),
                )
                and (
                    not self._is_structural_class_statement(
                        statement=statement,
                    )
                )
            ),
        )

    def _public_callables(self) -> tuple[FunctionNode, ...]:
        """Return public functions and methods reachable from module scope.

        Returns:
            The resulting value.

        """
        return (
            *(
                statement
                for statement in self._tree.body
                if isinstance(statement, (FunctionDef, AsyncFunctionDef))
                and (not statement.name.startswith("_"))
            ),
            *(
                statement
                for class_node in self._module_classes()
                for statement in class_node.body
                if isinstance(statement, (FunctionDef, AsyncFunctionDef))
                and (not statement.name.startswith("_"))
            ),
        )

    def _module_classes(self) -> tuple[ClassDef, ...]:
        """Return classes declared in module or module-level class scopes.

        Returns:
            The resulting value.

        """
        return self._classes_in_body(body=self._tree.body)

    def _is_structural_module_statement(self, *, statement: stmt) -> bool:
        """Return whether a top-level statement is declaration-only.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if isinstance(statement, (Import, ImportFrom, TypeAlias, Pass)):
            return True
        if self._is_docstring(statement=statement):
            return True
        if (
            self._path.name == "__main__.py"
            and isinstance(statement, Expr)
            and isinstance(statement.value, Call)
            and isinstance(statement.value.func, Name)
            and (statement.value.func.id in self._imports)
            and (not statement.value.args)
            and (not statement.value.keywords)
        ):
            return True
        if isinstance(statement, If):
            return self._is_pure_main_guard(statement=statement) or (
                self._is_type_checking_guard(statement=statement)
                and all(
                    self._is_structural_module_statement(statement=child)
                    for child in statement.body
                )
            )
        return self._is_structural_assignment(statement=statement)

    def _is_structural_class_statement(self, *, statement: stmt) -> bool:
        """Return whether a class-body statement is declaration-only.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if self._is_docstring(statement=statement) or isinstance(
            statement,
            Pass,
        ):
            return True
        return self._is_structural_assignment(statement=statement)

    def _is_structural_assignment(self, *, statement: stmt) -> bool:
        """Return whether an assignment only declares static data.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if isinstance(statement, AnnAssign):
            return isinstance(statement.target, Name) and (
                statement.value is None
                or self._is_static_expression(node=statement.value)
            )
        return (
            isinstance(statement, Assign)
            and all(isinstance(target, Name) for target in statement.targets)
            and self._is_static_expression(node=statement.value)
        )

    def _is_static_expression(self, *, node: AST) -> bool:
        """Return whether an expression is safe declaration-time data.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        if isinstance(node, Call):
            name: str | None = self._qualified_name(node=node.func)
            return (
                name in Constants.static_declaration_calls
                and all(
                    self._is_static_expression(node=argument)
                    for argument in node.args
                )
                and all(
                    self._is_static_expression(node=keyword.value)
                    for keyword in node.keywords
                )
            )
        if isinstance(
            node,
            (Await, NamedExpr, Yield, YieldFrom, comprehension),
        ):
            return False
        return all(
            self._is_static_expression(node=child)
            for child in iter_child_nodes(node=node)
        )

    def _is_pure_delegate(self, *, function: FunctionNode) -> bool:
        """Return whether a callable only forwards to one other callable.

        Args:
            function: Value supplied for ``function``.

        Returns:
            The resulting value.

        """
        body: tuple[stmt, ...] = self._meaningful_body(body=function.body)
        if len(body) != 1:
            return False
        call: Call | None = self._delegated_call(statement=body[0])
        return (
            call is not None
            and (
                not (
                    self._is_side_effect_call(node=call)
                    or self._is_computation_call(node=call)
                    or self._is_mutating_call(node=call)
                )
            )
            and all(
                self._is_forwarding_expression(node=argument)
                for argument in call.args
            )
            and all(
                keyword.arg is not None
                and self._is_forwarding_expression(node=keyword.value)
                for keyword in call.keywords
            )
        )

    def _is_stub(self, *, function: FunctionNode) -> bool:
        """Return whether a callable contains no executable implementation.

        Args:
            function: Value supplied for ``function``.

        Returns:
            The resulting value.

        """
        body: tuple[stmt, ...] = self._meaningful_body(body=function.body)
        return not body or all(
            isinstance(statement, Pass)
            or (
                isinstance(statement, Expr)
                and isinstance(statement.value, Constant)
                and (statement.value.value is Ellipsis)
            )
            for statement in body
        )

    def _is_behavioral_statement(self, *, statement: stmt) -> bool:
        """Return whether a statement contributes observable behavior.

        Args:
            statement: Value supplied for ``statement``.

        Returns:
            The resulting value.

        """
        if isinstance(
            statement,
            (
                Assert,
                AsyncFor,
                AsyncWith,
                AugAssign,
                Delete,
                For,
                Match,
                Raise,
                Try,
                TryStar,
                While,
                With,
            ),
        ):
            return True
        if isinstance(statement, If):
            return not self._is_main_guard(node=statement)
        if isinstance(statement, Return):
            return statement.value is not None and (
                not isinstance(statement.value, (Name, Constant, Attribute))
            )
        if isinstance(statement, Expr):
            return not self._is_docstring(statement=statement)
        if isinstance(statement, Assign):
            return self._is_mutation(node=statement) or not isinstance(
                statement.value,
                (Name, Constant, Attribute),
            )
        return isinstance(statement, AnnAssign) and (
            self._is_mutation(node=statement)
            or (
                statement.value is not None
                and (
                    not isinstance(
                        statement.value,
                        (Name, Constant, Attribute),
                    )
                )
            )
        )

    def _is_side_effect_call(self, *, node: Call) -> bool:
        """Return whether a call reads or mutates an external boundary.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        name: str | None = self._qualified_name(node=node.func)
        return (
            name is not None
            and (
                name in Constants.side_effect_names
                or any(
                    name.startswith(prefix)
                    for prefix in Constants.side_effect_prefixes
                )
            )
        ) or (
            isinstance(node.func, Attribute)
            and node.func.attr in Constants.side_effect_attributes
        )

    def _is_external_state_access(self, *, node: Subscript) -> bool:
        """Return whether a subscript reads ambient process state.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        name: str | None = self._qualified_name(node=node.value)
        return name is not None and name in Constants.external_state_names

    def _is_mutating_call(self, *, node: Call) -> bool:
        """Return whether a call mutates caller-visible in-memory state.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        name: str | None = self._qualified_name(node=node.func)
        return (name is not None and name in Constants.mutation_names) or (
            isinstance(node.func, Attribute)
            and node.func.attr in Constants.mutation_attributes
        )

    def _is_computation_call(self, *, node: Call) -> bool:
        """Return whether a built-in call directly computes a value.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        name: str | None = self._qualified_name(node=node.func)
        return name is not None and name in Constants.computation_calls

    def _qualified_name(self, *, node: AST) -> str | None:
        """Return a dotted name resolved through module import bindings.

        Args:
            node: Value supplied for ``node``.

        Returns:
            The resulting value.

        """
        syntactic_name: str | None = self._syntactic_name(node=node)
        if syntactic_name is None:
            return None
        root: str
        separator: str
        remainder: str
        root, separator, remainder = syntactic_name.partition(".")
        imported_root: str | None = self._imports.get(root)
        if imported_root is None:
            return syntactic_name
        return f"{imported_root}.{remainder}" if separator else imported_root

    def _import_bindings(self) -> dict[str, str]:
        """Return top-level names mapped to their defining import paths.

        Returns:
            The resulting value.

        """
        return {
            local_name: imported_name
            for statement in self._tree.body
            if isinstance(statement, (Import, ImportFrom))
            for local_name, imported_name in self._statement_bindings(
                statement=statement,
            )
        }
