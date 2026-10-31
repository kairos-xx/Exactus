# Copyright (c) 2026
# Copyright (c) 2026
"""Exactus keyword-call policy, imports, and explicit typing.

The project standard requires every keyword-capable call argument to be
passed by keyword, bare module imports to use explicit imported symbols
for every accessed attribute except configured exemptions, and
variables/callables to carry explicit type annotations where Python
syntax permits. Bare imports whose module object is only referenced as a
whole — never through attribute access — stay allowed. This module
performs all three analyses with lexical-scope awareness.

Resolution covers project functions, methods reached through `self`,
`cls`, `super()`, constructor-typed variables, annotated parameters and
attributes, dataclass and `NamedTuple` constructors, imported project
symbols, and external callables resolvable through `inspect.signature`.
"""

from __future__ import annotations

from ast import (
    AST,
    And,
    AnnAssign,
    Assign,
    AsyncFor,
    AsyncFunctionDef,
    AsyncWith,
    Attribute,
    AugAssign,
    BinOp,
    BitOr,
    BoolOp,
    Call,
    ClassDef,
    Compare,
    Constant,
    Dict,
    DictComp,
    Eq,
    ExceptHandler,
    For,
    FunctionDef,
    GeneratorExp,
    Global,
    Gt,
    GtE,
    If,
    IfExp,
    Import,
    ImportFrom,
    JoinedStr,
    Lambda,
    List,
    ListComp,
    Lt,
    LtE,
    MatchAs,
    MatchStar,
    Module,
    Name,
    NamedExpr,
    Nonlocal,
    Not,
    NotEq,
    Set,
    SetComp,
    Starred,
    Store,
    Subscript,
    Try,
    TryStar,
    Tuple,
    UnaryOp,
    With,
    alias,
    arg,
    arguments,
    comprehension,
    expr,
    iter_child_nodes,
    keyword,
    literal_eval,
    parse,
    stmt,
    unparse,
    walk,
    withitem,
)
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field, replace
from functools import lru_cache, partial
from hashlib import sha256
from importlib import import_module
from inspect import Parameter, Signature, signature
from itertools import pairwise
from json import dump, load
from json import loads as json_loads
from operator import eq, ge, gt, le, lt, ne
from pathlib import Path
from re import Match, fullmatch, search
from shutil import which
from subprocess import TimeoutExpired, run
from sys import executable, version, version_info
from sys import platform as sys_platform
from threading import Lock
from tomllib import loads as toml_loads
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    Literal,
    NotRequired,
    Self,
    TextIO,
    TypedDict,
    Unpack,
    cast,
)

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.steps import trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    consume,
    context_lines,
    is_reports_tree,
)
from exactus.tools.common.runtime import (
    Progress,
    publish_progress,
    wait_for_dependencies,
)
from exactus.tools.common.snippets import SnippetLimits, with_excerpts
from exactus.tools.kwargs_typehints.report import report_data
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from concurrent.futures import Future
    from re import Match
    from subprocess import CompletedProcess

    from exactus.tools.common.json_types import JsonValue


class BoundedLaneProgress:
    """Publish bounded progress checkpoints for high-cardinality stages.

    Attributes:
        checkpoints: Maximum number of published progress checkpoints
            per stage.
        total: Total work items in the stage.
        step: Progress step label.
        span: Parent progress interval occupied by this stage.
        completed: Finished work items.
        interval: Items between consecutive progress updates.
        lock: Mutex serializing progress publication.

    """

    checkpoints: ClassVar[int] = 32

    def __init__(
        self: Self,
        *,
        total: int,
        step: str,
        span: tuple[float, float],
    ) -> None:
        """Initialize a thread-safe bounded progress lane.

        Args:
            total: Total work items in the stage.
            step: Progress step label.
            span: Parent progress interval occupied by this stage.

        """
        self.total: int = total
        self.step: str = step
        self.span: tuple[float, float] = span
        self.completed: int = 0
        self.interval: int = max(1, total // self.checkpoints)
        self.lock: Lock = Lock()

    def finish(self: Self, *, item: str, error: str | None = None) -> None:
        """Complete one item and publish only useful checkpoints.

        Args:
            item: Completed item description.
            error: Optional failure description.

        """
        with self.lock:
            self.completed += 1
            completed: int = self.completed
        if (
            error is None
            and completed != self.total
            and completed % self.interval != 0
        ):
            return
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=completed,
                total=self.total,
                step=self.step,
                detail=(item if error is None else f"{item}: {error}"),
                span=self.span,
            ),
        )


type ParamKind = Literal["posonly", "poskw", "kwonly", "vararg", "varkw"]
type MethodKind = Literal["function", "instance", "class", "static"]
type ResolvedKind = Literal[
    "function",
    "class",
    "instance",
    "module",
    "external",
    "stubmod",
    "stubclass",
    "stubinstance",
    "unknown",
]
type ExternalKind = Literal["module", "class", "instance", "other"]
type LiveObject = object
_MEMORYVIEW_FACTORY: Final[Callable[[bytes], memoryview]] = memoryview
"""Typeshed names the parameter `obj`; the CPython runtime accepts `object`."""


def _identity(value: LiveObject = None) -> LiveObject:
    """Return the value unchanged for use as a ``function`` probe value.

    Args:
        value: Value to return.

    Returns:
        The value passed in.

    """
    return value


@dataclass(frozen=True, slots=True)
class FuzzValue:
    """One reusable runtime type-fuzzing value factory.

    Attributes:
        type_name: Stable type label written to JSON.
        factories: Fresh representative values for the runtime type.

    """

    type_name: str
    factories: tuple[Callable[[], LiveObject], ...]


class Constants:
    """Static lookup tables and probe fixtures for the exactus.

    Attributes:
        dataclass_markers: Decorator names marking dataclass definitions.
        skip_dirs: Directory names excluded from source discovery.
        skip_calls: Builtin call names excluded from call exactusing.
        dynamic_callee_prefixes: Callee prefixes that are dynamic by design
            (``pytest.mark.<anything>``) and cannot be resolved.
        positional_only_methods: Method names of standard-library and
            third-party APIs that accept only positional arguments, so an
            unresolved receiver cannot hide a keyword opportunity.
        foreign_binding_pattern: ``lowerCamelCase`` names, which Python
            code never defines and which therefore belong to C++/JS
            bindings such as Qt, whose methods are positional-only.
        file_openers: Call names whose ``with ... as`` target is a file.
        receiver_names: Method receiver parameter names.
        callable_kinds: Resolution kinds treated as callable.
        probe_default: Fallback probe argument value.
        probe_values: Probe argument values keyed by parameter name.
        receiver_factories: Fresh builtin receiver factories by type name.
        probe_blocklist: Builtins never probed with live calls.
        probe_safe_modules: Pure stdlib modules eligible for live probes.
        posonly_params: Runtime-verified positional-only parameters keyed
            by dotted callable path for callables whose stubs advertise
            keyword-capable parameters that must be bound positionally:
            C functions rejecting keywords at runtime, or functions whose
            parameter names differ across supported Python versions so no
            single keyword is portable.
        max_depth: Maximum AST resolution recursion depth.
        interpreter_candidates: Project-relative interpreter paths, in
            lookup order, that identify the Python a project runs on.
        interpreter_probe: Fixed program a project interpreter runs to
            report its ``sys.version_info`` and ``sys.platform``.
        interpreter_timeout: Seconds a project interpreter may take to
            answer the probe before the analyzer falls back.
        fixture_hints: Pytest fixture parameter type hints.
        optional_wrappers: Annotation names treated as ``Optional``.
        container_names: Annotation bases whose first subscript argument
            names the iterated element type.
        iterable_wrappers: Call names whose single argument is iterated
            with its element type preserved.
        type_fuzz_values: Runtime type-fuzzing value factories.

    """

    dataclass_markers: frozenset[str] = frozenset(
        {"dataclass", "dataclasses.dataclass"},
    )
    skip_dirs: frozenset[str] = ExactusCommonTables.DEFAULT_EXCLUDED_DIRS
    file_openers: frozenset[str] = frozenset({"open", "fdopen", "popen"})
    skip_calls: frozenset[str] = frozenset(
        {"__import__", "print", "exec", "eval", "vars"},
    )
    dynamic_callee_prefixes: tuple[str, ...] = ("pytest.mark.",)
    positional_only_methods: frozenset[str] = frozenset(
        {
            "bind",
            "connect",
            "count",
            "emit",
            "end",
            "execute",
            "executemany",
            "executescript",
            "joinpath",
            "listen",
            "partition",
            "recv",
            "rpartition",
            "sendall",
            "set_exception",
            "set_result",
            "settimeout",
            "start",
            "submit",
            "throw",
            "truncate",
            "update",
            "write",
        },
    )
    foreign_binding_pattern: str = r"^[a-z]+[A-Z]\w*$"
    receiver_names: frozenset[str] = frozenset({"self", "cls"})
    callable_kinds: frozenset[str] = frozenset(
        {"function", "class", "instance", "stubclass", "stubinstance"},
    )
    probe_default: LiveObject = None
    probe_values: ClassVar[dict[str, LiveObject]] = {
        "base": 10,
        "byteorder": "big",
        "count": 0,
        "default": None,
        "encoding": "utf-8",
        "end": "",
        "errors": "strict",
        "fillchar": " ",
        "flush": False,
        "fromlist": (),
        "globals": {},
        "key": "x",
        "length": 1,
        "level": 0,
        "locals": {},
        "mode": "r",
        "name": "x",
        "ndigits": 0,
        "new": "",
        "number": 1,
        "object": "x",
        "old": "",
        "sep": "",
        "signed": False,
        "start": 0,
        "step": 1,
        "stop": 1,
        "width": 1,
        "x": 1,
        "async_iterable": (),
        "bases": (object,),
        "buffer": b"x",
        "bytes": b"x",
        "c": "x",
        "chars": "x",
        "class_or_tuple": int,
        "delete": b"",
        "doc": "",
        "exp": 2,
        "fdel": None,
        "fget": None,
        "flags": 0,
        "format_spec": "",
        "fset": None,
        "function": _identity,
        "i": 0,
        "imag": 0.0,
        "index": 0,
        "instance": 1,
        "item": 1,
        "iterable": (1,),
        "iterable_of_bytes": (b"x",),
        "iterable_of_ints": (1,),
        "keepends": False,
        "mapping": {},
        "maxsplit": -1,
        "mod": 3,
        "obj": 1,
        "order": "C",
        "other": 1,
        "owner": int,
        "prefix": "",
        "proto": 4,
        "protocol": 4,
        "real": 1.0,
        "reverse": False,
        "sequence": (1,),
        "strict": True,
        "string": "x",
        "subclass": int,
        "suffix": "",
        "table": {},
        "tabsize": 8,
        "type": int,
        "typestr": "B",
        "value": 1,
        "y": 1,
    }
    receiver_factories: ClassVar[dict[str, Callable[[], LiveObject]]] = {
        "bool": lambda: True,
        "bytearray": partial(bytearray, b"x"),
        "bytes": lambda: b"x",
        "complex": lambda: 1j,
        "dict": lambda: {"x": 1},
        "float": lambda: 1.0,
        "frozenset": lambda: frozenset({1}),
        "int": lambda: 1,
        "list": lambda: [1],
        "memoryview": lambda: _MEMORYVIEW_FACTORY(b"x"),
        "range": lambda: range(1),
        "set": lambda: {1},
        "slice": lambda: slice(0, 1),
        "str": lambda: "x",
        "tuple": lambda: (1,),
        "type": lambda: int,
    }
    probe_blocklist: frozenset[str] = frozenset(
        {
            "__import__",
            "breakpoint",
            "compile",
            "eval",
            "exec",
            "exit",
            "help",
            "input",
            "open",
            "print",
            "quit",
        },
    )
    probe_safe_modules: frozenset[str] = frozenset(
        {
            "_bisect",
            "_heapq",
            "_operator",
            "_statistics",
            "cmath",
            "math",
            "operator",
            "statistics",
        },
    )
    posonly_params: ClassVar[dict[str, frozenset[str]]] = {
        "_contextvars.ContextVar": frozenset({"name"}),
        "contextvars.ContextVar": frozenset({"name"}),
        "_curses.window.timeout": frozenset({"delay"}),
        "curses.window.timeout": frozenset({"delay"}),
        "importlib.resources._common.as_file": frozenset({"path"}),
        "importlib.resources.as_file": frozenset({"path"}),
        "importlib.resources._common.files": frozenset({"anchor", "package"}),
        "importlib.resources.files": frozenset({"anchor", "package"}),
        "pathlib.Path.is_relative_to": frozenset({"other"}),
        "pathlib.Path.relative_to": frozenset({"other"}),
        "pathlib.PosixPath.is_relative_to": frozenset({"other"}),
        "pathlib.PosixPath.relative_to": frozenset({"other"}),
        "pathlib.PurePath.is_relative_to": frozenset({"other"}),
        "pathlib.PurePath.relative_to": frozenset({"other"}),
        "pathlib.PurePosixPath.is_relative_to": frozenset({"other"}),
        "pathlib.PurePosixPath.relative_to": frozenset({"other"}),
        "pathlib.PureWindowsPath.is_relative_to": frozenset({"other"}),
        "pathlib.PureWindowsPath.relative_to": frozenset({"other"}),
        "pathlib.WindowsPath.is_relative_to": frozenset({"other"}),
        "pathlib.WindowsPath.relative_to": frozenset({"other"}),
        "xml.etree.ElementTree.Element": frozenset({"tag"}),
        "xml.etree.ElementTree.SubElement": frozenset({"parent", "tag"}),
    }
    max_depth: int = 15
    interpreter_candidates: tuple[Path, ...] = (
        Path(".venv/bin/python"),
        Path(".venv/Scripts/python.exe"),
        Path("venv/bin/python"),
        Path("venv/Scripts/python.exe"),
    )
    interpreter_probe: str = (
        "import json, sys; "
        "print(json.dumps([list(sys.version_info), sys.platform]))"
    )
    interpreter_timeout: float = 20.0
    fixture_hints: ClassVar[dict[str, str]] = {
        "monkeypatch": "pytest.MonkeyPatch",
        "tmp_path": "pathlib.Path",
        "capsys": "pytest.CaptureFixture",
        "capfd": "pytest.CaptureFixture",
        "caplog": "pytest.LogCaptureFixture",
        "request": "pytest.FixtureRequest",
        "mocker": "pytest_mock.MockerFixture",
    }
    optional_wrappers: frozenset[str] = frozenset(
        {
            "Annotated",
            "ClassVar",
            "Final",
            "NotRequired",
            "Optional",
            "Required",
            "typing.Annotated",
            "typing.ClassVar",
            "typing.Final",
            "typing.NotRequired",
            "typing.Optional",
            "typing.Required",
        },
    )
    container_names: frozenset[str] = frozenset(
        {
            "Collection",
            "Iterable",
            "Iterator",
            "KeysView",
            "MutableSequence",
            "MutableSet",
            "Sequence",
            "ValuesView",
            "collections.abc.Collection",
            "collections.abc.Iterable",
            "collections.abc.Iterator",
            "collections.abc.KeysView",
            "collections.abc.MutableSequence",
            "collections.abc.MutableSet",
            "collections.abc.Sequence",
            "collections.abc.ValuesView",
            "collections.deque",
            "deque",
            "dict",
            "frozenset",
            "list",
            "set",
            "tuple",
            "typing.Collection",
            "typing.Iterable",
            "typing.Iterator",
            "typing.KeysView",
            "typing.MutableSequence",
            "typing.MutableSet",
            "typing.Sequence",
            "typing.ValuesView",
        },
    )
    iterable_wrappers: frozenset[str] = frozenset(
        {
            "copy",
            "frozenset",
            "iter",
            "list",
            "reversed",
            "set",
            "sorted",
            "tuple",
        },
    )
    type_fuzz_values: Final[tuple[FuzzValue, ...]] = (
        FuzzValue(type_name="NoneType", factories=(lambda: None,)),
        FuzzValue(type_name="bool", factories=(lambda: False, lambda: True)),
        FuzzValue(
            type_name="int",
            factories=(lambda: 0, lambda: 1, lambda: -1),
        ),
        FuzzValue(type_name="float", factories=(lambda: 0.0, lambda: 1.0)),
        FuzzValue(type_name="complex", factories=(lambda: 0j, lambda: 1j)),
        FuzzValue(
            type_name="str",
            factories=(
                lambda: "",
                lambda: "x",
                lambda: "utf-8",
                lambda: "big",
                lambda: "C",
            ),
        ),
        FuzzValue(type_name="bytes", factories=(lambda: b"", lambda: b"x")),
        FuzzValue(
            type_name="bytearray",
            factories=(bytearray, lambda: bytearray(b"x")),
        ),
        FuzzValue(
            type_name="memoryview",
            factories=(lambda: _MEMORYVIEW_FACTORY(b"x"),),
        ),
        FuzzValue(type_name="list", factories=(list, lambda: [1])),
        FuzzValue(type_name="tuple", factories=(lambda: (), lambda: (1,))),
        FuzzValue(type_name="dict", factories=(dict, lambda: {"x": 1})),
        FuzzValue(type_name="set", factories=(set[int], lambda: {1})),
        FuzzValue(
            type_name="frozenset",
            factories=(frozenset[int], lambda: frozenset({1})),
        ),
        FuzzValue(
            type_name="range",
            factories=(lambda: range(0), lambda: range(1)),
        ),
        FuzzValue(
            type_name="slice",
            factories=(lambda: slice(0), lambda: slice(0, 1)),
        ),
        FuzzValue(type_name="function", factories=(_identity,)),
        FuzzValue(type_name="type", factories=(lambda: int, lambda: str)),
        FuzzValue(type_name="ellipsis", factories=(lambda: Ellipsis,)),
    )


@dataclass(frozen=True, slots=True)
class Param:
    """One parameter of a callable signature.

    Attributes:
        name: Parameter name as written.
        kind: Positional/keyword classification.
        has_default: Whether the parameter declares a default value.

    """

    name: str
    kind: ParamKind
    has_default: bool = False


@dataclass(slots=True)
class Sig:
    """Resolved signature for a callable.

    Attributes:
        name: Dotted or qualified callable name for reporting.
        params: Ordered parameters.
        method: How the callable binds a receiver.
        returns: Name of the annotated return type, when simple.

    """

    name: str
    params: tuple[Param, ...]
    method: MethodKind = "function"
    returns: str | None = None


_PARAM_KINDS: Final[frozenset[str]] = frozenset(
    {"posonly", "poskw", "kwonly", "vararg", "varkw"},
)


def _param_json(*, param: Param) -> JsonValue:
    """Serialize one `Param` for the capability index.

    Args:
        param: Parameter record to serialize.

    Returns:
        JSON-compatible parameter mapping.

    """
    return {
        "name": param.name,
        "kind": param.kind,
        "has_default": param.has_default,
    }


def _param_read(*, data: JsonValue) -> Param | None:
    """Deserialize one `Param` from capability index JSON.

    Args:
        data: Serialized parameter value.

    Returns:
        The `Param | None` result produced by the operation.

    """
    if not isinstance(data, dict):
        return None
    name: JsonValue = data.get("name")
    kind: JsonValue = data.get("kind")
    if not isinstance(name, str) or not (
        isinstance(kind, str) and kind in _PARAM_KINDS
    ):
        return None
    return Param(
        name=name,
        kind=cast(typ="ParamKind", val=kind),
        has_default=data.get("has_default") is True,
    )


def _params_read(*, data: JsonValue) -> tuple[Param, ...] | None:
    """Deserialize one parameter tuple from capability index JSON.

    Args:
        data: Serialized parameter list.

    Returns:
        The `tuple[Param, ...] | None` result produced by the operation.

    """
    if not isinstance(data, list):
        return None
    params: list[Param] = []
    item: JsonValue
    for item in data:
        param: Param | None = _param_read(data=item)
        if param is None:
            return None
        params.append(param)
    return tuple(params)


def _str_map_read(*, data: JsonValue) -> dict[str, str | None]:
    """Parse a string-or-null map section of the capability index.

    Args:
        data: Raw JSON value for the section.

    Returns:
        The parsed map; empty when the section is absent or malformed.

    """
    result: dict[str, str | None] = {}
    if isinstance(data, dict):
        key: str
        entry: JsonValue
        for key, entry in data.items():
            result[key] = entry if isinstance(entry, str) else None
    return result


def _str_set_read(*, data: JsonValue) -> frozenset[str]:
    """Parse a string-array section of the capability index.

    Args:
        data: Raw JSON value for the section.

    Returns:
        The parsed set; empty when the section is absent or malformed.

    """
    return frozenset(
        item
        for item in (data if isinstance(data, list) else ())
        if isinstance(item, str)
    )


def _sigs_index_read(
    *,
    data: JsonValue,
) -> dict[str, tuple[Param, ...] | None]:
    """Parse the ``sigs`` section of the capability index.

    Args:
        data: Raw JSON value for the ``sigs`` map.

    Returns:
        Param tuples keyed by dotted path; ``None`` marks a canonically
        unsignaturable callable.

    """
    sigs: dict[str, tuple[Param, ...] | None] = {}
    if not isinstance(data, dict):
        return sigs
    for key, entry in data.items():
        if entry is None:
            sigs[key] = None
            continue
        params: tuple[Param, ...] | None = _params_read(data=entry)
        if params is not None:
            sigs[key] = params
    return sigs


@dataclass(frozen=True, slots=True)
class VerifyRecord:
    """Canonical ``verify_sets`` outcome for one external callable.

    Attributes:
        sets: Corrected call-ready parameter tuples.
        conclusive: Whether every keyword-capable parameter probed
            conclusively on the reference interpreter.

    """

    sets: tuple[tuple[Param, ...], ...]
    conclusive: bool


def _verify_index_read(*, data: JsonValue) -> dict[str, VerifyRecord]:
    """Parse the ``verify`` section of the capability index.

    Args:
        data: Raw JSON value for the ``verify`` map.

    Returns:
        `VerifyRecord`s keyed by dotted callable path; malformed
        entries are skipped.

    """
    verify: dict[str, VerifyRecord] = {}
    if not isinstance(data, dict):
        return verify
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        sets_raw: JsonValue = entry.get("sets")
        if not isinstance(sets_raw, list):
            continue
        parsed: list[tuple[Param, ...] | None] = [
            _params_read(data=variant) for variant in sets_raw
        ]
        if all(params is not None for params in parsed):
            verify[key] = VerifyRecord(
                sets=tuple(
                    cast(typ="tuple[Param, ...]", val=params)
                    for params in parsed
                ),
                conclusive=entry.get("conclusive") is True,
            )
    return verify


@dataclass(frozen=True, slots=True)
class CapabilityIndex:
    """Canonical runtime capability snapshot for external callables.

    The index is generated once on the project's reference interpreter
    (``--write-capability-index``) and committed beside this module so
    exactuss on any host consume the same signature truth instead of
    whatever the analyzer's local Python happens to expose.

    Attributes:
        verify: Corrected ``verify_sets`` parameter tuples keyed by
            dotted callable path (``.member`` suffix where applicable).
        sigs: Canonical parameter tuples for callables only
            ``inspect.signature`` resolves; ``None`` marks a canonically
            unsignaturable callable.
        types: Canonical annotation-type verdicts: the resolved dotted
            path, or ``None`` when the name resolves to no type.
        absent: Dotted external paths with no resolvable object on the
            reference interpreter.
        python_version: Interpreter version string used for generation.
        executable: Interpreter executable used for generation.

    """

    verify: dict[str, VerifyRecord]
    sigs: dict[str, tuple[Param, ...] | None]
    types: dict[str, str | None]
    absent: frozenset[str]
    python_version: str
    executable: str

    @classmethod
    def load(cls: type[Self], *, path: Path) -> Self:
        """Load a committed capability index snapshot.

        Args:
            path: ``CAPABILITY_INDEX.json`` path.

        Returns:
            The parsed `CapabilityIndex`.

        Raises:
            ValueError: When the file does not match schema version 1.

        """
        data: JsonValue
        with path.open(mode="r", encoding="utf-8") as file:
            data = cast(typ="JsonValue", val=load(fp=file))
        if not isinstance(data, dict) or data.get("schema") != 1:
            msg: str = f"Unsupported capability index: {path}"
            raise ValueError(msg)
        version_text: JsonValue = data.get("python_version")
        executable_text: JsonValue = data.get("executable")
        return cls(
            verify=_verify_index_read(data=data.get("verify")),
            sigs=_sigs_index_read(data=data.get("sigs")),
            types=_str_map_read(data=data.get("types")),
            absent=_str_set_read(data=data.get("absent")),
            python_version=(
                version_text if isinstance(version_text, str) else ""
            ),
            executable=(
                executable_text if isinstance(executable_text, str) else ""
            ),
        )

    def dump(self: Self, *, path: Path) -> None:
        """Write the canonical index snapshot.

        Args:
            path: Destination ``CAPABILITY_INDEX.json`` path.

        """
        verify_json: dict[str, JsonValue] = {}
        for key, record in self.verify.items():
            verify_json[key] = {
                "conclusive": record.conclusive,
                "sets": [
                    [_param_json(param=param) for param in params]
                    for params in record.sets
                ],
            }
        sigs_json: dict[str, JsonValue] = {
            key: (
                None
                if params is None
                else [_param_json(param=param) for param in params]
            )
            for key, params in self.sigs.items()
        }
        payload: dict[str, JsonValue] = {
            "schema": 1,
            "python_version": self.python_version,
            "executable": self.executable,
            "verify": verify_json,
            "sigs": sigs_json,
            "types": cast(typ="dict[str, JsonValue]", val=dict(self.types)),
            "absent": cast(typ="list[JsonValue]", val=sorted(self.absent)),
        }
        with path.open(mode="w", encoding="utf-8") as file:
            dump(obj=payload, fp=file, ensure_ascii=False, indent=2)
            _ = file.write("\n")


@dataclass(slots=True)
class ClassInfo:
    """Indexed class definition.

    Attributes:
        name: Qualified name within the module.
        module: Dotted module name owning the class.
        path: File defining the class.
        methods: Directly defined methods by name.
        nested: Nested classes by name.
        bases: Base class names as written.
        fields: Synthetic constructor parameters for dataclasses and
            `NamedTuple` classes, otherwise None.
        attr_types: Attribute name to class name, from `self.x = Foo()`
            assignments, class annotations, and property return types.
        attr_calls: Attribute name to callable resolution, from
            `self.x = func` assignments; instance attributes do not
            rebind the receiver.
        attr_elems: Attribute name to iterated element type, from
            container annotations like `self.x: list[T]`.
        class_calls: Class-body `x = func` assignments; functions bind
            the receiver on instance access like normal methods.

    """

    name: str
    module: str
    path: Path
    methods: dict[str, Sig] = field(default_factory=dict)
    nested: dict[str, ClassInfo] = field(default_factory=dict)
    bases: list[str] = field(default_factory=list)
    fields: tuple[Param, ...] | None = None
    attr_types: dict[str, str] = field(default_factory=dict)
    attr_calls: dict[str, Resolved] = field(default_factory=dict)
    attr_elems: dict[str, str] = field(default_factory=dict)
    class_calls: dict[str, Resolved] = field(default_factory=dict)


@dataclass(slots=True)
class ModuleInfo:
    """Indexed module.

    Attributes:
        name: Primary dotted module name.
        path: File path.
        is_package: Whether the file is an `__init__.py`.
        functions: Top-level functions by name.
        classes: Top-level classes by name.
        aliases: Imported names to dotted targets.
        module_aliases: Imported names to module paths.
        var_types: Module-level names bound to class instances.
        var_calls: Module-level names bound to callable references,
            populated while the module body is walked.
        call_exprs: Module-level `x = a.b` right-hand-side texts kept
            for order-independent lazy resolution.
        tree: Parsed module tree when the caller keeps it.

    """

    name: str
    path: Path
    is_package: bool
    functions: dict[str, Sig] = field(default_factory=dict)
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    module_aliases: dict[str, str] = field(default_factory=dict)
    var_types: dict[str, str] = field(default_factory=dict)
    var_calls: dict[str, Resolved] = field(default_factory=dict)
    call_exprs: dict[str, str] = field(default_factory=dict)
    tree: Module | None = None


@dataclass(slots=True)
class StubModule:
    """Parsed typeshed stub module.

    Attributes:
        name: Dotted stub module name.
        functions: Overloaded signature lists by function name.
        classes: Stub classes by name.
        reexports: Local names re-exported from another module, mapped
            to `(source module, original name)` pairs.
        star_sources: Modules pulled in through `from X import *`.

    """

    name: str
    functions: dict[str, list[Sig]] = field(default_factory=dict)
    classes: dict[str, StubClass] = field(default_factory=dict)
    reexports: dict[str, tuple[str, str]] = field(default_factory=dict)
    star_sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StubClass:
    """Parsed typeshed stub class.

    Attributes:
        name: Qualified class name.
        methods: Overloaded signature lists by method name.
        nested: Nested stub classes by name.
        bases: Base class names as written.
        ctors: Constructor overloads from `__init__` and `__new__`.

    """

    name: str
    methods: dict[str, list[Sig]] = field(default_factory=dict)
    nested: dict[str, StubClass] = field(default_factory=dict)
    bases: list[str] = field(default_factory=list)
    ctors: list[Sig] = field(default_factory=list)


@dataclass(slots=True)
class Resolved:
    """Outcome of resolving one expression.

    Attributes:
        kind: What the expression denotes.
        sig: Callable signature for `function` results.
        sigs: Overload candidates for stubbed callables.
        cls: Class record for `class` and `instance` results.
        module: Module record for `module` results.
        bound: Whether a method receiver is already supplied.
        obj: External object for `external` results.
        ext_kind: External object classification.
        stub: Stub module or class for stub-resolved results.
        dotted: Dotted name usable for external lookup.

    """

    kind: ResolvedKind = "unknown"
    sig: Sig | None = None
    sigs: tuple[Sig, ...] = ()
    cls: ClassInfo | None = None
    module: ModuleInfo | None = None
    bound: bool = False
    obj: object = None
    ext_kind: ExternalKind = "other"
    stub: object = None
    dotted: str = ""


@dataclass(frozen=True, slots=True)
class Finding:
    """One positional argument bound to a keyword-capable parameter.

    Attributes:
        path: File containing the call.
        line: One-based line number.
        callee: Callee expression as written.
        param: Parameter the argument binds to.
        index: Zero-based position among leading positional arguments.
        argument: Argument expression as written.
        confidence: How the signature was resolved.
        suggestion: Keyword-form rewrite.

    """

    path: Path
    line: int
    callee: str
    param: str
    index: int
    argument: str
    confidence: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class AmbiguousCall:
    """Call whose callee name maps to multiple disagreeing signatures.

    Attributes:
        path: File containing the call.
        line: One-based line number.
        callee: Call expression as written.
        candidates: Candidate definitions as `class.method` labels.

    """

    path: Path
    line: int
    callee: str
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnresolvedCall:
    """Call site whose callee could not be resolved to a signature.

    Attributes:
        path: File containing the call.
        line: One-based line number.
        column: One-based column of the callee expression.
        callee: Callee expression as written.
        reason: Why no signature could be found (a short code).

    """

    path: Path
    line: int
    column: int
    callee: str
    reason: str


class Scope:
    """Lexical scope for name resolution."""

    def __init__(
        self: Self,
        *,
        parent: Scope | None,
        classinfo: ClassInfo | None,
        class_body: bool = False,
    ) -> None:
        """Initialize the scope.

        Args:
            parent: Enclosing scope.
            classinfo: Enclosing class record.
            class_body: Whether this is a class body; names become attributes.

        """
        self.parent: Scope | None = parent
        self.classinfo: ClassInfo | None = classinfo
        self.class_body: bool = class_body
        self.defs: dict[str, Sig] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.var_types: dict[str, str] = {}
        self.var_calls: dict[str, Resolved] = {}
        self.var_elems: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.module_aliases: dict[str, str] = {}

    def enclosing_class(self: Self) -> ClassInfo | None:
        """Return the nearest enclosing class record.

        Returns:
            The `ClassInfo | None` result produced by the operation.

        """
        scope: Scope | None = self
        while scope is not None:
            if scope.classinfo is not None:
                return scope.classinfo
            scope = scope.parent
        return None

    def visible_scopes(self: Self) -> Iterator[Scope]:
        """Yield scopes whose names are visible for bare-name lookup.

        Class-body scopes only contribute names to code evaluated
        inside the class body itself; function bodies nested in a class
        do not close over the class namespace.

        Yields:
            Each enclosing scope whose names remain visible.

        """
        scope: Scope | None = self
        origin: bool = True
        while scope is not None:
            if origin or not scope.class_body:
                yield scope
            origin = False
            scope = scope.parent

    def lookup_def(self: Self, *, name: str) -> Sig | None:
        """Find a callable bound under `name` in this scope chain.

        Args:
            name: Local callable name.

        Returns:
            The `Sig | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.defs:
                return scope.defs[name]
        return None

    def lookup_class(self: Self, *, name: str) -> ClassInfo | None:
        """Find a class bound under `name` in this scope chain.

        Args:
            name: Local class name.

        Returns:
            The `ClassInfo | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.classes:
                return scope.classes[name]
        return None

    def lookup_var(self: Self, *, name: str) -> str | None:
        """Find the class name bound to variable `name`.

        Args:
            name: Variable name.

        Returns:
            The `str | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.var_types:
                return scope.var_types[name]
        return None

    def lookup_elem(self: Self, *, name: str) -> str | None:
        """Find the iterated element type recorded for `name`.

        Args:
            name: Variable name.

        Returns:
            The `str | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.var_elems:
                return scope.var_elems[name]
        return None

    def lookup_call(self: Self, *, name: str) -> Resolved | None:
        """Find a callable bound to variable `name` in this scope chain.

        Args:
            name: Variable name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.var_calls:
                return scope.var_calls[name]
        return None

    def lookup_alias(self: Self, *, name: str) -> str | None:
        """Find a function-local `from x import y` target.

        Args:
            name: Imported name.

        Returns:
            The `str | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.aliases:
                return scope.aliases[name]
        return None

    def lookup_module_alias(self: Self, *, name: str) -> str | None:
        """Find a function-local `import x` target.

        Args:
            name: Imported module name.

        Returns:
            The `str | None` result produced by the operation.

        """
        scope: Scope
        for scope in self.visible_scopes():
            if name in scope.module_aliases:
                return scope.module_aliases[name]
        return None


@dataclass(frozen=True, slots=True)
class ImportUse:
    """One module-qualified expression that can be rewritten safely.

    Attributes:
        line: One-based source line.
        column: One-based source column.
        original: Original module-qualified expression.
        symbol: Direct symbol imported from the module.
        suffix: Attribute suffix retained after the imported symbol.

    """

    line: int
    column: int
    original: str
    symbol: str
    suffix: tuple[str, ...]


@dataclass(slots=True)
class BareImportPlan:
    """Mutable analysis state for one analyzed bare import.

    Attributes:
        path: File containing the import.
        line: One-based import line.
        column: One-based import column.
        module: Fully imported module path.
        bound: Name created by the bare import.
        prefix: Attribute prefix required before a direct module symbol.
        uses: Safely rewritable direct module attribute uses.
        value_uses: Whether the bound module object is referenced as a
            whole-module value, which keeps the bare import required.
        unsafe_reasons: Reasons a semantics-preserving automatic rewrite cannot
            be guaranteed.
        scope_key: Identity of the lexical scope containing the import.
        reserved: Names bound anywhere in that lexical scope.
        nested_reserved: Additional names from class scopes in which the import
            is used through normal class-body global fallback.
        generated_names: Final imported symbol names selected after collision
            analysis.

    """

    path: Path
    line: int
    column: int
    module: str
    bound: str
    prefix: tuple[str, ...]
    scope_key: int
    reserved: frozenset[str]
    nested_reserved: set[str] = field(default_factory=set)
    uses: list[ImportUse] = field(default_factory=list)
    value_uses: bool = False
    unsafe_reasons: set[str] = field(default_factory=set)
    generated_names: dict[str, str] = field(default_factory=dict)

    def safe(self: Self) -> bool:
        """Return whether the entire import can be rewritten safely.

        Returns:
            Whether all observed uses are statically rewritable.

        """
        return bool(self.uses) and not self.unsafe_reasons


@dataclass(frozen=True, slots=True)
class BareImportFinding:
    """One forbidden bare import and its scope-aware proposed rewrite.

    Attributes:
        path: File containing the import.
        line: One-based import line.
        column: One-based import column.
        module: Fully imported module path.
        bound: Name created by the import.
        safe: Whether the proposed rewrite preserves every observed use.
        suggestion: Replacement import statement when safe.
        replacements: Source-expression replacements when safe.
        reason: Explanation when no complete safe rewrite can be proposed.

    """

    path: Path
    line: int
    column: int
    module: str
    bound: str
    safe: bool
    suggestion: str
    replacements: tuple[tuple[int, int, str, str], ...]
    reason: str


class BareImportExactusor:
    """Detect bare imports and derive collision-safe explicit-import fixes.

    Attributes:
        DEFAULT_ALLOWED: Modules permitted as bare imports by default.

    """

    DEFAULT_ALLOWED: frozenset[str] = frozenset({"pytest"})

    def __init__(
        self: Self,
        *,
        path: Path,
        allowed: frozenset[str],
        tree: Module | None = None,
    ) -> None:
        """Initialize one file exactus.

        Args:
            path: Python source file to exactus.
            allowed: Modules permitted only as standalone bare imports.
            tree: Pre-parsed module reused instead of re-reading ``path``.

        """
        self.path: Path = path
        self.allowed: frozenset[str] = allowed
        self.tree: Module | None = tree
        self.plans: list[BareImportPlan] = []

    @classmethod
    def target_names(cls: type[Self], *, node: AST) -> set[str]:
        """Return names bound by an assignment-style target.

        Args:
            node: Assignment, loop, walrus, or context-manager target.

        Returns:
            Bound identifier names.

        """
        if isinstance(node, Name):
            return {node.id}
        if isinstance(node, Starred):
            return cls.target_names(node=node.value)
        if isinstance(node, Tuple | List):
            names: set[str] = set()
            item: expr
            for item in node.elts:
                names.update(cls.target_names(node=item))
            return names
        return set()

    @classmethod
    def scope_bindings(
        cls: type[Self],
        *,
        body: list[stmt],
        parameters: arguments | None = None,
    ) -> set[str]:
        """Collect names statically bound in one lexical scope.

        Nested function and class bodies are separate scopes and are not folded
        into the parent binding set. Function-local binding is intentionally
        whole-scope, matching Python's lexical local-name semantics.

        Args:
            body: Statements belonging directly to the scope.
            parameters: Function or lambda parameters for the scope.

        Returns:
            Names bound anywhere in this lexical scope.

        """
        names: set[str] = set()
        globals_: set[str] = set()
        nonlocals: set[str] = set()
        if parameters is not None:
            parameter: arg
            for parameter in [
                *parameters.posonlyargs,
                *parameters.args,
                *parameters.kwonlyargs,
            ]:
                names.add(parameter.arg)
            if parameters.vararg is not None:
                names.add(parameters.vararg.arg)
            if parameters.kwarg is not None:
                names.add(parameters.kwarg.arg)
        item: stmt
        for item in body:
            cls.collect_statement_bindings(
                node=item,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )
        names.difference_update(globals_ | nonlocals)
        return names

    @classmethod
    def collect_statement_bindings(
        cls: type[Self],
        *,
        node: AST,
        names: set[str],
        globals_: set[str],
        nonlocals: set[str],
    ) -> None:
        """Collect bindings from one statement without entering child scopes.

        Args:
            node: Statement or expression to inspect.
            names: Destination set of local bindings.
            globals_: Names declared global in the scope.
            nonlocals: Names declared nonlocal in the scope.

        """
        if isinstance(node, Global):
            globals_.update(node.names)
        elif isinstance(node, Nonlocal):
            nonlocals.update(node.names)
        elif isinstance(node, FunctionDef | AsyncFunctionDef | ClassDef):
            names.add(node.name)
        elif isinstance(node, Import | ImportFrom):
            cls.import_bindings(node=node, names=names)
        elif isinstance(
            node,
            Assign | AnnAssign | AugAssign | NamedExpr | For | AsyncFor,
        ):
            cls.assignment_bindings(node=node, names=names)
        elif isinstance(node, With | AsyncWith):
            cls.with_bindings(node=node, names=names)
        elif isinstance(node, ExceptHandler) and node.name is not None:
            names.add(node.name)
        elif isinstance(node, ListComp | SetComp | DictComp | GeneratorExp):
            cls.comprehension_bindings(
                node=node,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )
        else:
            cls.child_bindings(
                node=node,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )

    @classmethod
    def assignment_bindings(
        cls: type[Self],
        *,
        node: Assign | AnnAssign | AugAssign | NamedExpr | For | AsyncFor,
        names: set[str],
    ) -> None:
        """Collect names bound by assignment-style statements.

        Args:
            node: Assignment, loop, or walrus statement.
            names: Destination set of local bindings.

        """
        targets: tuple[expr, ...] = (
            tuple(node.targets) if isinstance(node, Assign) else (node.target,)
        )
        target: expr
        for target in targets:
            names.update(cls.target_names(node=target))

    @classmethod
    def with_bindings(
        cls: type[Self],
        *,
        node: With | AsyncWith,
        names: set[str],
    ) -> None:
        """Collect names bound by with-statement optional targets.

        Args:
            node: With statement.
            names: Destination set of local bindings.

        """
        context: withitem
        for context in node.items:
            if context.optional_vars is not None:
                names.update(cls.target_names(node=context.optional_vars))

    @classmethod
    def comprehension_bindings(
        cls: type[Self],
        *,
        node: ListComp | SetComp | DictComp | GeneratorExp,
        names: set[str],
        globals_: set[str],
        nonlocals: set[str],
    ) -> None:
        """Collect walrus bindings inside a comprehension's parts.

        Args:
            node: Comprehension or generator expression.
            names: Destination set of local bindings.
            globals_: Names declared global in the scope.
            nonlocals: Names declared nonlocal in the scope.

        """
        generator: comprehension
        for generator in node.generators:
            cls.collect_statement_bindings(
                node=generator.iter,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )
            condition: expr
            for condition in generator.ifs:
                cls.collect_statement_bindings(
                    node=condition,
                    names=names,
                    globals_=globals_,
                    nonlocals=nonlocals,
                )
        elements: tuple[expr, ...] = (
            (node.key, node.value)
            if isinstance(node, DictComp)
            else (node.elt,)
        )
        element: expr
        for element in elements:
            cls.collect_statement_bindings(
                node=element,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )

    @classmethod
    def child_bindings(
        cls: type[Self],
        *,
        node: AST,
        names: set[str],
        globals_: set[str],
        nonlocals: set[str],
    ) -> None:
        """Collect bindings from child nodes, skipping lambda bodies.

        Args:
            node: Statement or expression whose children are inspected.
            names: Destination set of local bindings.
            globals_: Names declared global in the scope.
            nonlocals: Names declared nonlocal in the scope.

        """
        child: AST
        for child in iter_child_nodes(node=node):
            if isinstance(child, Lambda):
                continue
            cls.collect_statement_bindings(
                node=child,
                names=names,
                globals_=globals_,
                nonlocals=nonlocals,
            )

    @classmethod
    def contains_attribute_use(
        cls: type[Self],
        *,
        node: AST,
        name: str,
    ) -> bool:
        """Return whether a subtree accesses attributes on a bare name.

        Only attribute chains rooted at the name count; loading the module
        object itself, for example passing it to ``monkeypatch.setattr``, is a
        whole-module value use rather than an attribute access.

        Args:
            node: Subtree to inspect.
            name: Identifier to find.

        Returns:
            Whether the name roots an attribute chain in the subtree.

        """
        pending: list[AST] = [node]
        while pending:
            current: AST = pending.pop()
            if isinstance(current, Attribute):
                flattened: tuple[str, tuple[str, ...]] | None = (
                    cls.flatten_attribute(node=current)
                )
                if flattened is not None and flattened[0] == name:
                    return True
            if current is not node and isinstance(
                current,
                FunctionDef | AsyncFunctionDef | ClassDef | Lambda,
            ):
                continue
            pending.extend(iter_child_nodes(node=current))
        return False

    @staticmethod
    def import_bindings(*, node: Import | ImportFrom, names: set[str]) -> None:
        """Collect names bound by one import statement.

        Args:
            node: Import or from-import statement.
            names: Destination set of local bindings.

        """
        imported: alias
        for imported in node.names:
            if imported.name == "*":
                continue
            names.add(
                imported.asname
                or (
                    imported.name.split(sep=".", maxsplit=1)[0]
                    if isinstance(node, Import)
                    else imported.name
                ),
            )

    @staticmethod
    def flatten_attribute(
        *,
        node: Attribute,
    ) -> tuple[str, tuple[str, ...]] | None:
        """Flatten an attribute chain to its root name and attributes.

        Args:
            node: Attribute expression.

        Returns:
            Root name plus attributes, or None for non-name roots.

        """
        attrs: list[str] = []
        current: expr = node
        while isinstance(current, Attribute):
            attrs.append(current.attr)
            current = current.value
        if not isinstance(current, Name):
            return None
        attrs.reverse()
        return current.id, tuple(attrs)

    @staticmethod
    def import_shape(*, imported: alias) -> tuple[str, tuple[str, ...]]:
        """Return the runtime binding name and module-prefix attributes.

        Args:
            imported: One alias entry from an ``import`` statement.

        Returns:
            Bound root name and attributes required to reach the imported
            module.

        """
        if imported.asname is not None:
            return imported.asname, ()
        parts: tuple[str, ...] = tuple(imported.name.split(sep="."))
        return parts[0], parts[1:]

    @staticmethod
    def preserved_import(*, plan: BareImportPlan) -> str:
        """Rebuild the original bare import for retained module value uses.

        Args:
            plan: Bare import whose bound name stays required.

        Returns:
            The import statement that keeps the bound module name alive.

        """
        kept: str = f"import {plan.module}"
        if plan.bound != plan.module.split(sep=".", maxsplit=1)[0]:
            kept += f" as {plan.bound}"
        return kept

    @staticmethod
    def unique_name(*, preferred: str, module: str, reserved: set[str]) -> str:
        """Choose a collision-free imported symbol binding.

        Args:
            preferred: Original imported symbol name.
            module: Source module used to derive a readable alias.
            reserved: Names unavailable in the lexical scope.

        Returns:
            Direct symbol name or a deterministic module-prefixed alias.

        """
        if preferred not in reserved:
            reserved.add(preferred)
            return preferred
        module_name: str = module.rsplit(sep=".", maxsplit=1)[-1]
        base: str = f"{module_name}_{preferred}"
        candidate: str = base
        suffix: int = 2
        while candidate in reserved:
            candidate = f"{base}_{suffix}"
            suffix += 1
        reserved.add(candidate)
        return candidate

    @staticmethod
    def external_declarations(*, body: list[stmt]) -> set[str]:
        """Return names declared ``global`` or ``nonlocal`` in a scope.

        Args:
            body: Statements in one lexical scope.

        Returns:
            Names whose assignments do not create ordinary local bindings.

        """
        names: set[str] = set()
        pending: list[AST] = list(body)
        while pending:
            node: AST = pending.pop()
            if isinstance(node, Global | Nonlocal):
                names.update(node.names)
                continue
            if isinstance(
                node,
                FunctionDef | AsyncFunctionDef | ClassDef | Lambda,
            ):
                continue
            pending.extend(iter_child_nodes(node=node))
        return names

    @staticmethod
    def contains_loaded_name(*, node: AST, name: str) -> bool:
        """Return whether a subtree loads a bare name outside deeper scopes.

        Args:
            node: Subtree to inspect.
            name: Identifier to find.

        Returns:
            Whether the name is loaded in the subtree.

        """
        pending: list[AST] = [node]
        while pending:
            current: AST = pending.pop()
            if isinstance(current, Name) and current.id == name:
                return True
            if current is not node and isinstance(
                current,
                FunctionDef | AsyncFunctionDef | ClassDef | Lambda,
            ):
                continue
            pending.extend(iter_child_nodes(node=current))
        return False

    @staticmethod
    def record_attribute_use(
        *,
        node: Attribute,
        attrs: tuple[str, ...],
        plan: BareImportPlan,
    ) -> None:
        """Record a safely rewritable module attribute expression.

        Args:
            node: Full attribute expression.
            attrs: Attributes following the bound module root.
            plan: Bare import providing the root binding.

        """
        if (
            len(attrs) <= len(plan.prefix)
            or attrs[: len(plan.prefix)] != plan.prefix
        ):
            plan.unsafe_reasons |= {
                (
                    f"`{unparse(ast_obj=node)}` does not resolve "
                    "through imported module "
                    f"`{plan.module}`"
                ),
            }
            return
        remainder: tuple[str, ...] = attrs[len(plan.prefix) :]
        symbol: str = remainder[0]
        if symbol.startswith("__") and symbol.endswith("__"):
            plan.unsafe_reasons |= {
                f"dunder module attribute `{symbol}` is not auto-rewritten",
            }
            return
        plan.uses.append(
            ImportUse(
                line=node.lineno,
                column=node.col_offset + 1,
                original=unparse(ast_obj=node),
                symbol=symbol,
                suffix=remainder[1:],
            ),
        )

    def exactus(self: Self) -> tuple[BareImportFinding, ...]:
        """Exactus the file and return scope-aware bare-import findings.

        Returns:
            Bare import findings ordered by source position.

        """
        tree: Module | None = self.tree
        if tree is None:
            try:
                tree = parse(
                    source=self.path.read_text(encoding="utf-8"),
                    filename=str(object=self.path),
                )
            except (OSError, SyntaxError, ValueError):
                return ()
        self.exactus_scope(
            body=tree.body,
            bindings=self.scope_bindings(body=tree.body),
            external_names=self.external_declarations(body=tree.body),
        )
        self.ensure_all_imports(tree=tree)
        return self.finalize()

    def ensure_all_imports(self: Self, *, tree: Module) -> None:
        """Ensure imports in non-linear structures are still diagnosed.

        Imports reached by the ordered scope analysis already have a plan. Any
        remaining AST ``Import`` node is reported conservatively without an
        automatic rewrite because its runtime binding lifetime was not proven.

        Args:
            tree: Parsed file module.

        """
        existing: set[tuple[int, int, str, str]] = set()
        plan: BareImportPlan
        for plan in self.plans:
            existing |= {(plan.line, plan.column, plan.module, plan.bound)}
        node: AST
        for node in walk(node=tree):
            if not isinstance(node, Import):
                continue
            standalone_allowed: bool = (
                len(node.names) == 1
                and node.names[0].asname is None
                and node.names[0].name in self.allowed
            )
            if standalone_allowed:
                continue
            imported: alias
            for imported in node.names:
                bound: str
                prefix: tuple[str, ...]
                bound, prefix = self.import_shape(imported=imported)
                key: tuple[int, int, str, str] = (
                    node.lineno,
                    node.col_offset + 1,
                    imported.name,
                    bound,
                )
                if key in existing:
                    continue
                self.plans.append(
                    BareImportPlan(
                        path=self.path,
                        line=node.lineno,
                        column=node.col_offset + 1,
                        module=imported.name,
                        bound=bound,
                        prefix=prefix,
                        scope_key=id(node),
                        reserved=frozenset(),
                        unsafe_reasons={
                            (
                                "import occurs in a non-linear or nested "
                                "statement structure whose binding lifetime "
                                "was not proven"
                            ),
                        },
                    ),
                )

    def exactus_scope(
        self: Self,
        *,
        body: list[stmt],
        bindings: set[str],
        external_names: set[str],
        inherited: dict[str, BareImportPlan] | None = None,
    ) -> None:
        """Exactus one lexical scope in execution order.

        Args:
            body: Statements in the lexical scope.
            bindings: All names statically bound by that scope.
            external_names: Names declared global or nonlocal in the scope.
            inherited: Visible bare-module bindings inherited by a class body.

        """
        active: dict[str, BareImportPlan] = dict(inherited or {})
        item: stmt
        for item in body:
            self.exactus_statement(
                node=item,
                active=active,
                bindings=bindings,
                external_names=external_names,
            )

    def exactus_statement(
        self: Self,
        *,
        node: stmt,
        active: dict[str, BareImportPlan],
        bindings: set[str],
        external_names: set[str],
    ) -> None:
        """Exactus one statement, updating sequential module bindings.

        Args:
            node: Statement to inspect.
            active: Currently active bare-module bindings.
            bindings: Static names in the containing lexical scope.
            external_names: Names declared global or nonlocal in the scope.

        """
        if isinstance(node, Import):
            self.record_bare_import(
                node=node,
                active=active,
                bindings=bindings,
                external_names=external_names,
            )
        elif isinstance(node, ImportFrom):
            self.scan_node(node=node, active=active)
            imported: alias
            for imported in node.names:
                if imported.name != "*":
                    _ = consume(
                        value=active.pop(
                            imported.asname or imported.name,
                            None,
                        ),
                    )
        elif isinstance(node, FunctionDef | AsyncFunctionDef):
            self.exactus_function_statement(node=node, active=active)
        elif isinstance(node, ClassDef):
            self.exactus_class_statement(node=node, active=active)
        elif isinstance(node, Assign | AnnAssign | AugAssign):
            self.exactus_assignment(node=node, active=active)
        elif isinstance(node, For | AsyncFor | With | AsyncWith):
            self.mark_complex_flow(node=node, active=active)
        else:
            self.exactus_other_statement(node=node, active=active)

    def exactus_function_statement(
        self: Self,
        *,
        node: FunctionDef | AsyncFunctionDef,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Exactus one function definition and its inner scope.

        Args:
            node: Function definition statement.
            active: Currently active bare-module bindings.

        """
        self.scan_function_definition(node=node, active=active)
        function_bindings: set[str] = self.scope_bindings(
            body=node.body,
            parameters=node.args,
        )
        filtered_active: dict[str, BareImportPlan] = {}
        name: str
        plan: BareImportPlan
        for name, plan in active.items():
            if name == node.name:
                continue
            filtered_active[name] = plan
        self.mark_nested_references(
            body=node.body,
            active=filtered_active,
            local_bindings=function_bindings,
        )
        _ = consume(value=active.pop(node.name, None))
        self.exactus_scope(
            body=node.body,
            bindings=function_bindings,
            external_names=self.external_declarations(body=node.body),
        )

    def exactus_class_statement(
        self: Self,
        *,
        node: ClassDef,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Exactus one class definition and its inner scope.

        Args:
            node: Class definition statement.
            active: Currently active bare-module bindings.

        """
        self.scan_class_definition(node=node, active=active)
        class_bindings: set[str] = self.scope_bindings(body=node.body)
        inherited: dict[str, BareImportPlan] = dict(active)
        plan: BareImportPlan
        for plan in inherited.values():
            plan.nested_reserved.update(class_bindings)
        self.exactus_scope(
            body=node.body,
            bindings=class_bindings,
            external_names=self.external_declarations(body=node.body),
            inherited=inherited,
        )
        _ = consume(value=active.pop(node.name, None))

    def exactus_assignment(
        self: Self,
        *,
        node: Assign | AnnAssign | AugAssign,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Exactus one assignment statement in evaluation order.

        Args:
            node: Assignment statement.
            active: Currently active bare-module bindings.

        """
        if isinstance(node, Assign):
            self.scan_node(node=node.value, active=active)
            target: expr
            for target in node.targets:
                self.shadow_targets(node=target, active=active)
            return
        if isinstance(node, AnnAssign):
            self.scan_node(node=node.annotation, active=active)
            if node.value is not None:
                self.scan_node(node=node.value, active=active)
        else:
            self.scan_node(node=node.target, active=active)
            self.scan_node(node=node.value, active=active)
        self.shadow_targets(node=node.target, active=active)

    def exactus_other_statement(
        self: Self,
        *,
        node: stmt,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Exactus a generic statement's uses and rebound bindings.

        Args:
            node: Statement to inspect.
            active: Currently active bare-module bindings.

        """
        self.scan_node(node=node, active=active)
        rebound: set[str] = set()
        self.collect_statement_bindings(
            node=node,
            names=rebound,
            globals_=set(),
            nonlocals=set(),
        )
        name: str
        for name in rebound:
            if name in active:
                active[name].unsafe_reasons |= {
                    f"`{name}` is rebound in non-linear control flow",
                }
                _ = consume(value=active.pop(name, None))

    def record_bare_import(
        self: Self,
        *,
        node: Import,
        active: dict[str, BareImportPlan],
        bindings: set[str],
        external_names: set[str],
    ) -> None:
        """Record analysis plans from one bare import statement.

        Args:
            node: Bare import statement.
            active: Current module bindings.
            bindings: Static bindings in the containing lexical scope.
            external_names: Names declared global or nonlocal in the scope.

        """
        standalone_allowed: bool = (
            len(node.names) == 1
            and node.names[0].asname is None
            and node.names[0].name in self.allowed
        )
        imported: alias
        for imported in node.names:
            bound: str
            prefix: tuple[str, ...]
            bound, prefix = self.import_shape(imported=imported)
            if standalone_allowed:
                _ = consume(value=active.pop(bound, None))
                continue
            if bound in active:
                active[bound].unsafe_reasons |= {
                    f"`{bound}` is rebound by a later bare import",
                }
            plan: BareImportPlan = BareImportPlan(
                path=self.path,
                line=node.lineno,
                column=node.col_offset + 1,
                module=imported.name,
                bound=bound,
                prefix=prefix,
                scope_key=id(bindings),
                reserved=frozenset(bindings),
            )
            if bound in external_names:
                plan.unsafe_reasons |= {
                    f"`{bound}` is declared global or nonlocal in this scope",
                }
            self.plans.append(plan)
            active[bound] = plan

    def scan_function_definition(
        self: Self,
        *,
        node: FunctionDef | AsyncFunctionDef,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Scan expressions evaluated while defining a function.

        Args:
            node: Function definition.
            active: Current module bindings.

        """
        expression: expr | None
        for expression in [
            *node.decorator_list,
            *node.args.defaults,
            *node.args.kw_defaults,
            node.returns,
        ]:
            if expression is not None:
                self.scan_node(node=expression, active=active)
        parameter: arg
        for parameter in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            if parameter.annotation is not None:
                self.scan_node(node=parameter.annotation, active=active)

    def scan_class_definition(
        self: Self,
        *,
        node: ClassDef,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Scan expressions evaluated before entering a class body.

        Args:
            node: Class definition.
            active: Current module bindings.

        """
        expression: expr
        for expression in [*node.decorator_list, *node.bases]:
            self.scan_node(node=expression, active=active)
        option: keyword
        for option in node.keywords:
            self.scan_node(node=option.value, active=active)

    def mark_nested_references(
        self: Self,
        *,
        body: list[stmt],
        active: dict[str, BareImportPlan],
        local_bindings: set[str],
    ) -> None:
        """Classify ancestor module references inside a child lexical scope.

        A function body can execute after its enclosing module/class binding
        has
        changed, so rewriting an ancestor module attribute access there is not
        proven semantics-preserving. Whole-module value uses are recorded but
        stay allowed. Child scopes that statically bind the same name do
        not reference the ancestor binding and are ignored.

        Args:
            body: Child lexical-scope body.
            active: Ancestor bare imports active at definition time.
            local_bindings: Local names that prevent closure lookup.

        """
        name: str
        plan: BareImportPlan
        for name, plan in active.items():
            if name in local_bindings:
                continue
            item: stmt
            for item in body:
                if self.contains_attribute_use(node=item, name=name):
                    plan.unsafe_reasons |= {
                        f"`{name}` is referenced from a nested lexical scope",
                    }
                    break
                if self.contains_loaded_name(node=item, name=name):
                    plan.value_uses = True

    def mark_complex_flow(
        self: Self,
        *,
        node: stmt,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Conservatively handle loops/context managers with binding ambiguity.

        Args:
            node: Complex-flow statement.
            active: Current module bindings.

        """
        self.scan_node(node=node, active=active)
        rebound: set[str] = set()
        self.collect_statement_bindings(
            node=node,
            names=rebound,
            globals_=set(),
            nonlocals=set(),
        )
        name: str
        for name in rebound:
            if name in active:
                active[name].unsafe_reasons |= {
                    (
                        f"`{name}` participates in "
                        "control-flow-dependent rebinding"
                    ),
                }
                _ = consume(value=active.pop(name, None))

    def shadow_targets(
        self: Self,
        *,
        node: AST,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Apply a deterministic assignment target to active bindings.

        Args:
            node: Assignment target.
            active: Current module bindings.

        """
        name: str
        for name in self.target_names(node=node):
            _ = consume(value=active.pop(name, None))

    def scan_node(
        self: Self,
        *,
        node: AST,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Scan an expression subtree for uses of active module bindings.

        Args:
            node: Expression subtree.
            active: Current bare-module bindings.

        """
        if isinstance(node, Lambda):
            self.scan_lambda(node=node, active=active)
            return
        if isinstance(node, FunctionDef | AsyncFunctionDef | ClassDef):
            return
        if isinstance(
            node,
            ListComp | SetComp | DictComp | GeneratorExp,
        ) and self.scan_comprehension(node=node, active=active):
            return
        if isinstance(node, Attribute) and self.scan_attribute(
            node=node,
            active=active,
        ):
            return
        if isinstance(node, Name) and node.id in active:
            active[node.id].value_uses = True
            return
        child: AST
        for child in iter_child_nodes(node=node):
            self.scan_node(node=child, active=active)

    def scan_lambda(
        self: Self,
        *,
        node: Lambda,
        active: dict[str, BareImportPlan],
    ) -> None:
        """Classify active bindings referenced from a lambda body.

        Attribute accesses are unsafe to rewrite because the lambda can run
        after the binding changed; whole-module value uses stay allowed.

        Args:
            node: Lambda expression.
            active: Current bare-module bindings.

        """
        local_names: set[str] = set()
        parameter: arg
        for parameter in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            local_names |= {parameter.arg}
        if node.args.vararg is not None:
            local_names.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            local_names.add(node.args.kwarg.arg)
        name: str
        plan: BareImportPlan
        for name, plan in active.items():
            if name in local_names:
                continue
            if self.contains_attribute_use(node=node.body, name=name):
                plan.unsafe_reasons |= {
                    f"`{name}` is referenced from a nested lambda scope",
                }
            elif self.contains_loaded_name(node=node.body, name=name):
                plan.value_uses = True

    def scan_comprehension(
        self: Self,
        *,
        node: ListComp | SetComp | DictComp | GeneratorExp,
        active: dict[str, BareImportPlan],
    ) -> bool:
        """Flag active bindings shadowed by comprehension targets.

        Args:
            node: Comprehension or generator expression.
            active: Current bare-module bindings.

        Returns:
            Whether any active binding was shadowed.

        """
        comprehension_targets: set[str] = set()
        generator: comprehension
        for generator in node.generators:
            comprehension_targets.update(
                self.target_names(node=generator.target),
            )
        name: str
        for name in comprehension_targets & active.keys():
            active[name].unsafe_reasons |= {
                f"`{name}` is shadowed by a comprehension target",
            }
        return bool(comprehension_targets & active.keys())

    def scan_attribute(
        self: Self,
        *,
        node: Attribute,
        active: dict[str, BareImportPlan],
    ) -> bool:
        """Record an attribute chain rooted at an active binding.

        Args:
            node: Attribute expression.
            active: Current bare-module bindings.

        Returns:
            Whether the chain was recorded and children need no scan.

        """
        flattened: tuple[str, tuple[str, ...]] | None = self.flatten_attribute(
            node=node,
        )
        if flattened is None:
            return False
        root: str
        attrs: tuple[str, ...]
        root, attrs = flattened
        if root not in active:
            return False
        self.record_attribute_use(node=node, attrs=attrs, plan=active[root])
        return True

    def finalize(self: Self) -> tuple[BareImportFinding, ...]:
        """Finalize aliases, replacements, and human-readable findings.

        Returns:
            Immutable findings ordered by source position.

        """
        reserved_by_scope: dict[int, set[str]] = {}
        findings: list[BareImportFinding] = []
        plan: BareImportPlan
        for plan in sorted(
            self.plans,
            key=lambda item: (item.line, item.column),
        ):
            if not plan.uses and not plan.unsafe_reasons:
                continue
            reserved: set[str] = reserved_by_scope.setdefault(
                plan.scope_key,
                set(plan.reserved | plan.nested_reserved),
            )
            symbols: list[str] = []
            use: ImportUse
            for use in plan.uses:
                if use.symbol not in symbols:
                    symbols.append(use.symbol)
            symbol: str
            for symbol in symbols:
                plan.generated_names[symbol] = self.unique_name(
                    preferred=symbol,
                    module=plan.module,
                    reserved=reserved,
                )
            safe: bool = plan.safe()
            import_parts: list[str] = []
            replacements: list[tuple[int, int, str, str]] = []
            suggestion: str = ""
            if safe:
                generated: str
                for symbol in symbols:
                    generated = plan.generated_names[symbol]
                    import_parts.append(
                        symbol
                        if generated == symbol
                        else f"{symbol} as {generated}",
                    )
                for use in plan.uses:
                    generated = plan.generated_names[use.symbol]
                    replacement: str = ".".join((generated, *use.suffix))
                    replacements.append(
                        (use.line, use.column, use.original, replacement),
                    )
                suggestion = (
                    f"from {plan.module} import {', '.join(import_parts)}"
                )
                if plan.value_uses:
                    kept: str = self.preserved_import(plan=plan)
                    indent: str = " " * (plan.column - 1)
                    suggestion = f"{kept}\n{indent}{suggestion}"
            findings.append(
                BareImportFinding(
                    path=plan.path,
                    line=plan.line,
                    column=plan.column,
                    module=plan.module,
                    bound=plan.bound,
                    safe=safe,
                    suggestion=suggestion,
                    replacements=tuple(replacements),
                    reason=(
                        ""
                        if safe
                        else "; ".join(sorted(plan.unsafe_reasons))
                        or (
                            "imported module has no statically "
                            "rewritable attribute use"
                        )
                    ),
                ),
            )
        return tuple(findings)


@dataclass(frozen=True, slots=True)
class TypeHintFinding:
    """One missing explicit type annotation.

    Attributes:
        path: File containing the binding or callable.
        line: One-based source line.
        column: One-based source column.
        kind: Missing annotation category.
        name: Variable, parameter, attribute, or callable name.
        scope: Lexical scope owning the annotation requirement.
        suggestion: Minimal source-level remediation guidance.
        reason: Why the annotation is required at this location.

    """

    path: Path
    line: int
    column: int
    kind: Literal["variable", "attribute", "parameter", "return"]
    name: str
    scope: str
    suggestion: str
    reason: str


@dataclass(slots=True)
class TypeScope:
    """Lexical annotation state used by the type-hint exactus.

    Attributes:
        parent: Enclosing lexical scope.
        kind: Scope category.
        label: Human-readable qualified scope label.
        annotations: Names explicitly annotated anywhere in this scope.
        bindings: Names statically bound anywhere in this scope.
        globals: Names declared global in this scope.
        nonlocals: Names declared nonlocal in this scope.
        imports: Qualified typing imports used to recognize type declarations.
        reported: Untyped names already reported for this scope.

    """

    parent: TypeScope | None
    kind: Literal["module", "function", "class", "lambda", "comprehension"]
    label: str
    annotations: set[str]
    bindings: set[str]
    globals: set[str]
    nonlocals: set[str]
    imports: dict[str, str] = field(default_factory=dict)
    reported: set[str] = field(default_factory=set)

    def module_scope(self: Self) -> TypeScope:
        """Return the root module scope.

        Returns:
            Root module annotation scope.

        """
        scope: TypeScope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def owner(self: Self, *, name: str) -> TypeScope:
        """Resolve the lexical scope owning a bound name.

        Args:
            name: Bound identifier.

        Returns:
            Scope in which the variable annotation must exist.

        """
        if name in self.globals:
            return self.module_scope()
        if name not in self.nonlocals:
            return self
        scope: TypeScope | None = self.parent
        while scope is not None:
            if scope.kind != "class" and (
                name in scope.bindings or name in scope.annotations
            ):
                return scope
            scope = scope.parent
        return self


@dataclass(slots=True)
class ClassAnnotationState:
    """Class-wide instance/class attribute annotation state.

    Attributes:
        label: Qualified class label.
        annotations: ``self``/``cls`` attributes annotated anywhere in the
            class implementation.
        reported: Missing attribute annotations already reported once.
        enum_like: Whether normal class-body assignments are Enum/StrEnum
            members and therefore inherit their type from the enum class.

    """

    label: str
    annotations: set[str]
    reported: set[str] = field(default_factory=set)
    enum_like: bool = False


def _is_store_name(target: expr) -> bool:
    """Report whether an assignment target stores into a plain name.

    Args:
        target: Assignment target expression.

    Returns:
        ``True`` for a ``Name`` target in ``Store`` context.

    """
    return isinstance(target, Name) and isinstance(target.ctx, Store)


def is_name_assign(node: AST) -> bool:
    """Return whether node assigns directly to at least one name.

    Args:
        node: AST node to classify.

    Returns:
        ``True`` when the node is an ``Assign`` statement storing into
        at least one plain ``Name`` target.

    """
    return isinstance(node, Assign) and any(map(_is_store_name, node.targets))


class CheckTargetArgs(TypedDict):
    """Represent check target args.

    Attributes:
        target: Target.
        scope: Scope.
        class_state: Class state.
        line: Line.
        column: Column.
        source: Source.
        syntax_permits_annotation: Syntax permits annotation.

    """

    target: AST
    scope: TypeScope
    class_state: ClassAnnotationState | None
    line: int
    column: int
    source: NotRequired[str]
    syntax_permits_annotation: NotRequired[bool]


class CheckNameArgs(TypedDict):
    """Represent check name args.

    Attributes:
        name: Name.
        scope: Scope.
        line: Line.
        column: Column.
        source: Source.
        syntax_permits_annotation: Syntax permits annotation.

    """

    name: str
    scope: TypeScope
    line: int
    column: int
    source: str
    syntax_permits_annotation: NotRequired[bool]


class TypeHintExactusor:
    """Detect missing variable, parameter, and return annotations by scope.

    Attributes:
        RECEIVERS: Method receiver names exempt from annotation findings.
        ENUM_BASES: Enum base classes whose members skip annotations.

    """

    RECEIVERS: frozenset[str] = frozenset({"self", "cls"})
    ENUM_BASES: frozenset[str] = frozenset(
        {"Enum", "IntEnum", "Flag", "IntFlag", "StrEnum", "ReprEnum"},
    )

    def __init__(
        self: Self,
        *,
        path: Path,
        strict: bool,
        tree: Module | None = None,
    ) -> None:
        """Initialize one source-file type-hint exactus.

        Args:
            path: Python source file to inspect.
            strict: Report unannotatable binding targets when ``True``.
            tree: Pre-parsed module reused instead of re-reading ``path``.

        """
        self.path: Path = path
        self.strict: bool = strict
        self.tree: Module | None = tree
        self.findings: list[TypeHintFinding] = []
        self.functions_checked: int = 0
        self.parameters_checked: int = 0

    @classmethod
    def make_scope(
        cls: type[Self],
        *,
        body: list[stmt],
        parent: TypeScope | None,
        kind: Literal[
            "module",
            "function",
            "class",
            "lambda",
            "comprehension",
        ],
        label: str,
        parameters: arguments | None = None,
    ) -> TypeScope:
        """Create a scope with whole-scope annotation/binding knowledge.

        Args:
            body: Statements belonging to the scope.
            parent: Enclosing lexical scope.
            kind: Scope category.
            label: Qualified scope label.
            parameters: Function parameters, when applicable.

        Returns:
            Initialized lexical annotation scope.

        """
        globals_, nonlocals, annotations, imports, walrus = (
            cls.collect_scope_metadata(body=body)
        )
        return TypeScope(
            parent=parent,
            kind=kind,
            label=label,
            annotations=annotations | walrus,
            bindings=BareImportExactusor.scope_bindings(
                body=body,
                parameters=parameters,
            ),
            globals=globals_,
            nonlocals=nonlocals,
            imports=imports,
        )

    @classmethod
    def collect_scope_metadata(
        cls: type[Self],
        *,
        body: list[stmt],
    ) -> tuple[set[str], set[str], set[str], dict[str, str], set[str]]:
        """Collect direct-scope metadata and owned walrus bindings.

        Declarations, annotations, and typing imports stop at every nested
        lexical scope. Walrus bindings additionally descend through
        comprehensions because assignment expressions there belong to the
        containing scope. Carrying that distinction in one traversal avoids
        a second full walk of every lexical body.

        Args:
            body: Statements belonging to the lexical scope.

        Returns:
            Global names, nonlocal names, annotated names, local typing
            imports, and walrus-created names owned by this scope.

        """
        globals_: set[str] = set()
        nonlocals: set[str] = set()
        annotations: set[str] = set()
        imports: dict[str, str] = {}
        walrus: set[str] = set()
        pending: list[tuple[AST, bool]] = [(node, True) for node in body]
        while pending:
            node: AST
            metadata: bool
            node, metadata = pending.pop()
            if isinstance(node, NamedExpr):
                walrus.add(node.target.id)
                pending.append((node.value, metadata))
                continue
            if isinstance(
                node,
                FunctionDef | AsyncFunctionDef | ClassDef | Lambda,
            ):
                continue
            if isinstance(node, ListComp | SetComp | DictComp | GeneratorExp):
                pending.extend(
                    (child, False) for child in iter_child_nodes(node=node)
                )
                continue
            if metadata and cls._record_scope_declaration(
                node=node,
                globals_=globals_,
                nonlocals=nonlocals,
                annotations=annotations,
                imports=imports,
            ):
                continue
            pending.extend(
                (child, metadata) for child in iter_child_nodes(node=node)
            )
        return globals_, nonlocals, annotations, imports, walrus

    @classmethod
    def class_annotations(cls: type[Self], *, node: ClassDef) -> set[str]:
        """Collect ``self.attr``/``cls.attr`` annotations class-wide.

        Args:
            node: Class definition to inspect.

        Returns:
            Attribute names annotated anywhere in the class implementation.

        """
        names: set[str] = set()
        pending: list[AST] = list(node.body)
        while pending:
            current: AST = pending.pop()
            if current is not node and isinstance(current, ClassDef):
                continue
            if (
                isinstance(current, AnnAssign)
                and isinstance(current.target, Attribute)
                and isinstance(current.target.value, Name)
                and (current.target.value.id in cls.RECEIVERS)
            ):
                names.add(current.target.attr)
            pending.extend(iter_child_nodes(node=current))
        return names

    @classmethod
    def enum_like(cls: type[Self], *, node: ClassDef) -> bool:
        """Return whether a class derives from a standard enum base.

        Args:
            node: Class definition.

        Returns:
            Whether ordinary class assignments should be treated as enum
            members whose type is inherited from the enum class.

        """
        base: expr
        for base in node.bases:
            name: str = unparse(ast_obj=base).rsplit(sep=".", maxsplit=1)[-1]
            if name in cls.ENUM_BASES:
                return True
        return False

    @classmethod
    def check_annotated_attribute(
        cls: type[Self],
        *,
        target: Attribute,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Record a directly encountered owned attribute annotation.

        Args:
            target: Annotated attribute target.
            class_state: Nearest class state.

        """
        if (
            class_state is not None
            and isinstance(target.value, Name)
            and target.value.id in cls.RECEIVERS
        ):
            class_state.annotations |= {target.attr}

    @staticmethod
    def typevar_declaration(*, node: Assign, scope: TypeScope) -> bool:
        """Recognize TypeVar factories without exempting ordinary variables.

        Args:
            node: Assignment being checked.
            scope: Lexical scope resolving the factory import.

        Returns:
            Whether a single name declares a typing TypeVar.

        """
        if (
            len(node.targets) != 1
            or not isinstance(node.targets[0], Name)
            or not isinstance(node.value, Call)
        ):
            return False
        name: str | None = annotation_name(node=node.value.func)
        if name is None:
            return False
        root, _, suffix = name.partition(".")
        current: TypeScope | None = scope
        while current is not None:
            imported: str | None = current.imports.get(root)
            if imported is not None:
                qualified: str = imported + (f".{suffix}" if suffix else "")
                return qualified in {
                    "typing.TypeVar",
                    "typing_extensions.TypeVar",
                }
            if root in current.bindings:
                return False
            current = current.parent
        return False

    @staticmethod
    def collect_walrus_bindings(*, body: list[stmt]) -> set[str]:
        """Collect walrus-created names owned by one lexical scope.

        Assignment expressions are exempt from explicit variable annotations.
        Their exemption applies to the binding for the entire owning scope, so
        later ordinary reassignments of that same name are also exempt.
        Walrus expressions inside comprehensions bind in the containing scope.

        Args:
            body: Statements belonging to the lexical scope.

        Returns:
            Names created by assignment expressions in this scope.

        """
        names: set[str] = set()
        pending: list[AST] = list(body)
        while pending:
            node: AST = pending.pop()
            if isinstance(node, NamedExpr):
                names.add(node.target.id)
                pending.append(node.value)
                continue
            if isinstance(
                node,
                FunctionDef | AsyncFunctionDef | ClassDef | Lambda,
            ):
                continue
            pending.extend(iter_child_nodes(node=node))
        return names

    @staticmethod
    def child_label(*, scope: TypeScope, name: str) -> str:
        """Build a qualified lexical-scope label.

        Args:
            scope: Parent scope.
            name: Child callable/class name.

        Returns:
            Qualified scope label.

        """
        return name if scope.label == "<module>" else f"{scope.label}.{name}"

    def exactus(self: Self) -> tuple[TypeHintFinding, ...]:
        """Exactus the file for missing explicit type hints.

        Returns:
            Missing-annotation findings ordered by source position.

        """
        tree: Module | None = self.tree
        if tree is None:
            try:
                tree = parse(
                    source=self.path.read_text(encoding="utf-8"),
                    filename=str(object=self.path),
                )
            except (OSError, SyntaxError, ValueError):
                return ()
        scope: TypeScope = self.make_scope(
            body=tree.body,
            parent=None,
            kind="module",
            label="<module>",
        )
        self.walk_body(body=tree.body, scope=scope, class_state=None)
        return tuple(
            sorted(
                self.findings,
                key=lambda item: (
                    item.line,
                    item.column,
                    item.kind,
                    item.name,
                ),
            ),
        )

    def walk_body(
        self: Self,
        *,
        body: list[stmt],
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Walk statements in one lexical annotation scope.

        Args:
            body: Statements to inspect.
            scope: Current lexical scope.
            class_state: Nearest enclosing class attribute state.

        """
        item: stmt
        for item in body:
            self.walk_node(node=item, scope=scope, class_state=class_state)

    def walk_node(
        self: Self,
        *,
        node: AST,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Inspect one AST node without crossing scope boundaries implicitly.

        Args:
            node: AST node to inspect.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        if isinstance(node, FunctionDef | AsyncFunctionDef):
            self.exactus_function(
                node=node,
                scope=scope,
                class_state=class_state,
            )
        elif isinstance(node, ClassDef):
            self.exactus_class(node=node, scope=scope)
        elif isinstance(node, Lambda):
            self.exactus_lambda(
                node=node,
                scope=scope,
                class_state=class_state,
            )
        elif isinstance(node, ListComp | SetComp | DictComp | GeneratorExp):
            self.exactus_comprehension(
                node=node,
                scope=scope,
                class_state=class_state,
            )
        elif isinstance(node, Assign | AnnAssign | AugAssign):
            self.walk_assignment(
                node=node,
                scope=scope,
                class_state=class_state,
            )
        elif isinstance(node, For | AsyncFor):
            self.walk_for(node=node, scope=scope, class_state=class_state)
        elif isinstance(node, With | AsyncWith):
            self.walk_with(node=node, scope=scope, class_state=class_state)
        elif isinstance(node, ExceptHandler):
            self.walk_except(node=node, scope=scope, class_state=class_state)
        else:
            self.walk_generic(node=node, scope=scope, class_state=class_state)

    def walk_generic(
        self: Self,
        *,
        node: AST,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check pattern bindings and recurse into child nodes.

        Args:
            node: AST node without a dedicated walker.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        if (
            self.strict
            and isinstance(node, MatchAs | MatchStar)
            and node.name is not None
        ):
            self.check_name(
                name=node.name,
                scope=scope,
                line=node.lineno,
                column=node.col_offset + 1,
                source="pattern binding",
            )
        child: AST
        for child in iter_child_nodes(node=node):
            self.walk_node(node=child, scope=scope, class_state=class_state)

    def walk_assignment(
        self: Self,
        *,
        node: Assign | AnnAssign | AugAssign,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check assignment targets and walk evaluated expressions.

        Args:
            node: Assignment statement.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        if isinstance(node, Assign):
            if not self.typevar_declaration(node=node, scope=scope) and (
                self.strict or is_name_assign(node=node)
            ):
                target: expr
                for target in node.targets:
                    if not (
                        scope.kind == "class"
                        and class_state is not None
                        and class_state.enum_like
                        and isinstance(target, Name | Tuple | List)
                    ):
                        self.check_target(
                            target=target,
                            scope=scope,
                            class_state=class_state,
                            line=node.lineno,
                            column=node.col_offset + 1,
                        )
            self.walk_node(
                node=node.value,
                scope=scope,
                class_state=class_state,
            )
            return
        if isinstance(node, AnnAssign):
            if isinstance(node.target, Attribute):
                self.check_annotated_attribute(
                    target=node.target,
                    class_state=class_state,
                )
            if node.value is not None:
                self.walk_node(
                    node=node.value,
                    scope=scope,
                    class_state=class_state,
                )
            self.walk_node(
                node=node.annotation,
                scope=scope,
                class_state=class_state,
            )
            return
        if self.strict:
            self.check_target(
                target=node.target,
                scope=scope,
                class_state=class_state,
                line=node.lineno,
                column=node.col_offset + 1,
            )
        self.walk_node(node=node.value, scope=scope, class_state=class_state)

    def walk_for(
        self: Self,
        *,
        node: For | AsyncFor,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check a loop target and walk its iterable and body.

        Args:
            node: Loop statement.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        if self.strict:
            self.check_target(
                target=node.target,
                scope=scope,
                class_state=class_state,
                line=node.lineno,
                column=node.col_offset + 1,
            )
        self.walk_node(node=node.iter, scope=scope, class_state=class_state)
        self.walk_body(
            body=[*node.body, *node.orelse],
            scope=scope,
            class_state=class_state,
        )

    def walk_with(
        self: Self,
        *,
        node: With | AsyncWith,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check with-item targets and walk context expressions.

        Args:
            node: With statement.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        item: withitem
        for item in node.items:
            self.walk_node(
                node=item.context_expr,
                scope=scope,
                class_state=class_state,
            )
            if item.optional_vars is not None and self.strict:
                self.check_target(
                    target=item.optional_vars,
                    scope=scope,
                    class_state=class_state,
                    line=node.lineno,
                    column=node.col_offset + 1,
                )
        self.walk_body(body=node.body, scope=scope, class_state=class_state)

    def walk_except(
        self: Self,
        *,
        node: ExceptHandler,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check an exception target and walk its type and body.

        Args:
            node: Except handler.
            scope: Current lexical scope.
            class_state: Nearest class attribute annotation state.

        """
        if node.name is not None and self.strict:
            self.check_name(
                name=node.name,
                scope=scope,
                line=node.lineno,
                column=node.col_offset + 1,
                source="exception target",
            )
        if node.type is not None:
            self.walk_node(
                node=node.type,
                scope=scope,
                class_state=class_state,
            )
        self.walk_body(body=node.body, scope=scope, class_state=class_state)

    def exactus_function(
        self: Self,
        *,
        node: FunctionDef | AsyncFunctionDef,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Check a function signature and recurse into its own scope.

        Args:
            node: Function definition.
            scope: Enclosing lexical scope.
            class_state: Nearest enclosing class state.

        """
        label: str = self.child_label(scope=scope, name=node.name)
        self.check_signature(node=node, scope=scope, label=label)
        child: TypeScope = self.make_scope(
            body=node.body,
            parent=scope,
            kind="function",
            label=label,
            parameters=node.args,
        )
        parameter: arg
        for parameter in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            child.annotations |= {parameter.arg}
        variadic: arg | None
        for variadic in [node.args.vararg, node.args.kwarg]:
            if variadic is not None:
                child.annotations |= {variadic.arg}
        decorator: expr
        for decorator in node.decorator_list:
            self.walk_node(
                node=decorator,
                scope=scope,
                class_state=class_state,
            )
        default: expr | None
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.walk_node(
                    node=default,
                    scope=scope,
                    class_state=class_state,
                )
        self.walk_body(body=node.body, scope=child, class_state=class_state)

    def check_signature(
        self: Self,
        *,
        node: FunctionDef | AsyncFunctionDef,
        scope: TypeScope,
        label: str,
    ) -> None:
        """Report unannotated parameters and missing return annotations.

        Args:
            node: Function definition.
            scope: Enclosing lexical scope.
            label: Fully qualified scope label for findings.

        """
        positional: list[arg] = [*node.args.posonlyargs, *node.args.args]
        has_staticmethod: bool = False
        decorator: expr
        for decorator in node.decorator_list:
            if (
                unparse(ast_obj=decorator).rsplit(sep=".", maxsplit=1)[-1]
                == "staticmethod"
            ):
                has_staticmethod = True
                break
        receiver: str | None = (
            positional[0].arg
            if (
                scope.kind == "class"
                and positional
                and positional[0].arg in self.RECEIVERS
                and not has_staticmethod
            )
            else None
        )
        self.functions_checked += 1
        parameter: arg
        for parameter in [*positional, *node.args.kwonlyargs]:
            if parameter.arg != receiver:
                self.parameters_checked += 1
            if parameter.annotation is None and parameter.arg != receiver:
                self.findings.append(
                    TypeHintFinding(
                        path=self.path,
                        line=parameter.lineno,
                        column=parameter.col_offset + 1,
                        kind="parameter",
                        name=parameter.arg,
                        scope=label,
                        suggestion=f"{parameter.arg}: <type>",
                        reason="function parameter has no explicit annotation",
                    ),
                )
        variadic: arg | None
        for variadic in [node.args.vararg, node.args.kwarg]:
            if variadic is not None:
                self.parameters_checked += 1
            if variadic is not None and variadic.annotation is None:
                self.findings.append(
                    TypeHintFinding(
                        path=self.path,
                        line=variadic.lineno,
                        column=variadic.col_offset + 1,
                        kind="parameter",
                        name=variadic.arg,
                        scope=label,
                        suggestion=f"{variadic.arg}: <type>",
                        reason="variadic parameter has no explicit annotation",
                    ),
                )
        if node.returns is None:
            self.findings.append(
                TypeHintFinding(
                    path=self.path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    kind="return",
                    name=node.name,
                    scope=label,
                    suggestion=(
                        "-> None"
                        if node.name == "__init__"
                        else "-> <return_type>"
                    ),
                    reason="callable has no explicit return annotation",
                ),
            )

    def exactus_class(self: Self, *, node: ClassDef, scope: TypeScope) -> None:
        """Exactus a class body in a fresh lexical/class-attribute scope.

        Args:
            node: Class definition.
            scope: Enclosing lexical scope.

        """
        label: str = self.child_label(scope=scope, name=node.name)
        class_state: ClassAnnotationState = ClassAnnotationState(
            label=label,
            annotations=self.class_annotations(node=node),
            enum_like=self.enum_like(node=node),
        )
        child: TypeScope = self.make_scope(
            body=node.body,
            parent=scope,
            kind="class",
            label=label,
        )
        decorator: expr
        for decorator in node.decorator_list:
            self.walk_node(node=decorator, scope=scope, class_state=None)
        base: expr
        for base in node.bases:
            self.walk_node(node=base, scope=scope, class_state=None)
        option: keyword
        for option in node.keywords:
            self.walk_node(node=option.value, scope=scope, class_state=None)
        self.walk_body(body=node.body, scope=child, class_state=class_state)

    def exactus_lambda(
        self: Self,
        *,
        node: Lambda,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Exactus lambda-local bindings that cannot carry annotations.

        Python lambda syntax cannot annotate parameters or a return type, so
        the signature itself is exempt under the policy's "where syntax
        permits" clause. Walrus bindings inside the body still belong to the
        lambda scope.

        Args:
            node: Lambda expression.
            scope: Enclosing lexical scope.
            class_state: Nearest enclosing class state.

        """
        lambda_walrus: set[str] = set()
        pending: list[AST] = [node.body]
        while pending:
            current: AST = pending.pop()
            if isinstance(current, NamedExpr):
                lambda_walrus.add(current.target.id)
                pending.append(current.value)
                continue
            if isinstance(current, Lambda):
                continue
            pending.extend(iter_child_nodes(node=current))
        lambda_bindings: set[str] = set()
        parameter: arg
        for parameter in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            lambda_bindings |= {parameter.arg}
        child: TypeScope = TypeScope(
            parent=scope,
            kind="lambda",
            label=f"{scope.label}.<lambda>",
            annotations=lambda_walrus,
            bindings=lambda_bindings,
            globals=set(),
            nonlocals=set(),
        )
        if node.args.vararg is not None:
            child.bindings |= {node.args.vararg.arg}
        if node.args.kwarg is not None:
            child.bindings |= {node.args.kwarg.arg}
        self.walk_node(node=node.body, scope=child, class_state=class_state)

    def exactus_comprehension(
        self: Self,
        *,
        node: ListComp | SetComp | DictComp | GeneratorExp,
        scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Exactus comprehension bindings in their implicit child scope.

        Comprehension targets cannot be annotated in comprehension syntax. They
        are therefore reported once per target with an explicit refactor note.
        Assignment expressions retain their Python semantics and are checked in
        the containing scope.

        Args:
            node: Comprehension expression.
            scope: Enclosing lexical scope.
            class_state: Nearest enclosing class state.

        """
        child: TypeScope = TypeScope(
            parent=scope,
            kind="comprehension",
            label=f"{scope.label}.<comprehension>",
            annotations=set(),
            bindings=set(),
            globals=set(),
            nonlocals=set(),
        )
        generators: list[comprehension] = list(node.generators)
        index: int
        generator: comprehension
        for index, generator in enumerate(iterable=generators):
            self.walk_node(
                node=generator.iter,
                scope=scope if index == 0 else child,
                class_state=class_state,
            )
            if self.strict:
                self.check_target(
                    target=generator.target,
                    scope=child,
                    class_state=class_state,
                    line=generator.target.lineno,
                    column=generator.target.col_offset + 1,
                    source="comprehension target",
                    syntax_permits_annotation=False,
                )
            condition: expr
            for condition in generator.ifs:
                self.walk_comprehension_expr(
                    node=condition,
                    scope=child,
                    walrus_scope=scope,
                    class_state=class_state,
                )
        if isinstance(node, DictComp):
            self.walk_comprehension_expr(
                node=node.key,
                scope=child,
                walrus_scope=scope,
                class_state=class_state,
            )
            self.walk_comprehension_expr(
                node=node.value,
                scope=child,
                walrus_scope=scope,
                class_state=class_state,
            )
        else:
            self.walk_comprehension_expr(
                node=node.elt,
                scope=child,
                walrus_scope=scope,
                class_state=class_state,
            )

    def walk_comprehension_expr(
        self: Self,
        *,
        node: AST,
        scope: TypeScope,
        walrus_scope: TypeScope,
        class_state: ClassAnnotationState | None,
    ) -> None:
        """Walk a comprehension expression with correct walrus ownership.

        Args:
            node: Expression inside a comprehension scope.
            scope: Implicit comprehension scope.
            walrus_scope: Containing scope receiving assignment expressions.
            class_state: Nearest enclosing class state.

        """
        if isinstance(node, NamedExpr):
            self.walk_comprehension_expr(
                node=node.value,
                scope=scope,
                walrus_scope=walrus_scope,
                class_state=class_state,
            )
            return
        if isinstance(node, ListComp | SetComp | DictComp | GeneratorExp):
            self.exactus_comprehension(
                node=node,
                scope=scope,
                class_state=class_state,
            )
            return
        child: AST
        for child in iter_child_nodes(node=node):
            self.walk_comprehension_expr(
                node=child,
                scope=scope,
                walrus_scope=walrus_scope,
                class_state=class_state,
            )

    def check_target(self: Self, **kwargs: Unpack[CheckTargetArgs]) -> None:
        """Check target.

        Args:
            kwargs: Kwargs.

        """
        target: AST = kwargs["target"]
        scope: TypeScope = kwargs["scope"]
        class_state: ClassAnnotationState | None = kwargs["class_state"]
        line: int = kwargs["line"]
        column: int = kwargs["column"]
        source: str = kwargs.get("source", "variable binding")
        syntax_permits_annotation: bool = kwargs.get(
            "syntax_permits_annotation",
            True,
        )
        if isinstance(target, Name):
            self.check_name(
                name=target.id,
                scope=scope,
                line=target.lineno if hasattr(target, "lineno") else line,
                column=(
                    target.col_offset + 1
                    if hasattr(target, "col_offset")
                    else column
                ),
                source=source,
                syntax_permits_annotation=syntax_permits_annotation,
            )
            return
        if isinstance(target, Starred):
            self.check_target(
                target=target.value,
                scope=scope,
                class_state=class_state,
                line=line,
                column=column,
                source=source,
                syntax_permits_annotation=syntax_permits_annotation,
            )
            return
        if isinstance(target, Tuple | List):
            item: expr
            for item in target.elts:
                self.check_target(
                    target=item,
                    scope=scope,
                    class_state=class_state,
                    line=line,
                    column=column,
                    source=source,
                    syntax_permits_annotation=syntax_permits_annotation,
                )
            return
        if isinstance(target, Attribute):
            self.check_attribute(
                target=target,
                class_state=class_state,
                source=source,
                syntax_permits_annotation=syntax_permits_annotation,
            )

    def check_name(self: Self, **kwargs: Unpack[CheckNameArgs]) -> None:
        """Check name.

        Args:
            kwargs: Kwargs.

        """
        name: str = kwargs["name"]
        if name == "_":
            return
        scope: TypeScope = kwargs["scope"]
        line: int = kwargs["line"]
        column: int = kwargs["column"]
        source: str = kwargs["source"]
        syntax_permits_annotation: bool = kwargs.get(
            "syntax_permits_annotation",
            True,
        )
        owner: TypeScope = scope.owner(name=name)
        if name in owner.annotations or name in owner.reported:
            return
        owner.reported |= {name}
        self.findings.append(
            TypeHintFinding(
                path=self.path,
                line=line,
                column=column,
                kind="variable",
                name=name,
                scope=owner.label,
                suggestion=(
                    f"{name}: <type>"
                    if syntax_permits_annotation
                    else (
                        f"declare `{name}: <type>` in `{owner.label}` before "
                        "this binding or refactor the construct"
                    )
                ),
                reason=(
                    f"{source} has no explicit annotation anywhere in its "
                    f"owning scope `{owner.label}`"
                ),
            ),
        )

    def check_attribute(
        self: Self,
        *,
        target: Attribute,
        class_state: ClassAnnotationState | None,
        source: str,
        syntax_permits_annotation: bool,
    ) -> None:
        """Report an untyped ``self``/``cls`` attribute once per class.

        Args:
            target: Attribute assignment target.
            class_state: Nearest class state.
            source: Binding source description.
            syntax_permits_annotation: Whether direct annotation syntax exists.

        """
        if class_state is None or not isinstance(target.value, Name):
            return
        if target.value.id not in self.RECEIVERS:
            return
        if (
            target.attr in class_state.annotations
            or target.attr in class_state.reported
        ):
            return
        class_state.reported |= {target.attr}
        qualified: str = f"{target.value.id}.{target.attr}"
        self.findings.append(
            TypeHintFinding(
                path=self.path,
                line=target.lineno,
                column=target.col_offset + 1,
                kind="attribute",
                name=qualified,
                scope=class_state.label,
                suggestion=(
                    f"{qualified}: <type>"
                    if syntax_permits_annotation
                    else f"predeclare `{qualified}: <type>` before binding"
                ),
                reason=(
                    f"{source} creates an attribute with no explicit "
                    f"annotation anywhere in class `{class_state.label}`"
                ),
            ),
        )

    @classmethod
    def _record_scope_declaration(
        cls: type[Self],
        *,
        node: AST,
        globals_: set[str],
        nonlocals: set[str],
        annotations: set[str],
        imports: dict[str, str],
    ) -> bool:
        """Record one statement's direct-scope metadata.

        Args:
            node: Statement being inspected.
            globals_: Global names to update.
            nonlocals: Nonlocal names to update.
            annotations: Annotated names to update.
            imports: Typing imports to update.

        Returns:
            Whether the node's children must not be visited again.

        """
        if isinstance(node, Global):
            globals_.update(node.names)
            return True
        if isinstance(node, Nonlocal):
            nonlocals.update(node.names)
            return True
        if isinstance(node, AnnAssign) and isinstance(node.target, Name):
            annotations.add(node.target.id)
        cls._record_typing_imports(node=node, imports=imports)
        return False

    @staticmethod
    def _record_typing_imports(*, node: AST, imports: dict[str, str]) -> None:
        """Record local ``typing`` imports visible to the scope.

        Args:
            node: Statement being inspected.
            imports: Alias-to-qualified-name mapping to update.

        """
        item: alias
        if (
            isinstance(node, ImportFrom)
            and node.module in {"typing", "typing_extensions"}
            and not node.level
        ):
            for item in node.names:
                imports[item.asname or item.name] = (
                    f"{node.module}.{item.name}"
                )
        elif isinstance(node, Import):
            for item in node.names:
                if item.name in {"typing", "typing_extensions"}:
                    imports[item.asname or item.name] = item.name


def python_files(
    *,
    root: Path,
    path_filter: Callable[[Path], bool] | None = None,
) -> list[Path]:
    """Collect every non-hidden, non-excluded Python file under `root`.

    Args:
        root: Repository root directory.
        path_filter: Optional predicate restricting discovered files.

    Returns:
        The `list[pathlib.Path]` result produced by the operation.

    """
    if root.is_file():
        entries: Iterable[tuple[Path, list[str], list[str]]] = (
            (root.parent, [], [root.name]),
        )
        root = root.parent
    else:
        entries = root.walk(top_down=True)
    found: list[Path] = []
    directory: Path
    directories: list[str]
    filenames: list[str]
    for directory, directories, filenames in entries:
        directories[:] = [
            name
            for name in directories
            if not name.startswith(".")
            and name not in Constants.skip_dirs
            and not name.endswith((".egg-info", ".dist-info"))
            and not is_reports_tree(directory=directory / name)
        ]
        filename: str
        for filename in filenames:
            if not filename.endswith(".py") or filename.startswith("."):
                continue
            candidate: Path = directory / filename
            if path_filter is not None and not path_filter(candidate):
                continue
            found.append(candidate)
    found.sort()
    return found


@lru_cache(maxsize=16)
def configured_source_roots(root: Path, modified_ns: int) -> tuple[Path, ...]:
    """Resolve explicitly configured import roots for a project revision.

    Args:
        root: Project containing the type-checker configuration.
        modified_ns: Configuration modification timestamp for cache identity.

    Returns:
        Existing in-project import roots declared through extraPaths.

    """
    _ = modified_ns
    value: JsonValue = cast(
        typ="JsonValue",
        val=toml_loads((root / "pyproject.toml").read_text(encoding="utf-8")),
    )
    for key in ("tool", "basedpyright", "extraPaths"):
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, list):
        return ()
    return tuple(
        candidate
        for entry in value
        if isinstance(entry, str)
        and (candidate := (root / entry).resolve()).is_relative_to(root)
        and candidate.is_dir()
    )


def module_names(*, path: Path, root: Path) -> list[str]:
    """Compute every plausible import name for a file.

    Args:
        path: Python file path.
        root: Repository root directory.

    Returns:
        The `list[str]` result produced by the operation.

    """
    roots: list[Path] = [root, root / "src"]
    config: Path = root / "pyproject.toml"
    if config.is_file():
        roots.extend(
            configured_source_roots(
                root=root,
                modified_ns=config.stat().st_mtime_ns,
            ),
        )
    package_root: Path = path.parent
    while (
        package_root != root
        and package_root.is_relative_to(root)
        and (package_root / "__init__.py").is_file()
    ):
        package_root = package_root.parent
    if package_root != path.parent and package_root not in roots:
        roots.append(package_root)
    names: list[str] = []
    base: Path
    for base in roots:
        try:
            relative: Path = path.relative_to(base).with_suffix(suffix="")
        except ValueError:
            continue
        parts: tuple[str, ...] = relative.parts
        if not all(part.isidentifier() for part in parts):
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            names.append(".".join(parts))
    return list(dict.fromkeys(names))


def annotation_name(*, node: expr | None) -> str | None:
    """Extract a usable class name from an annotation.

    Handles bare names, dotted attributes, subscripts (`list[T]`),
    `Optional[T]`, and `A | None` unions.

    Args:
        node: Annotation expression.

    Returns:
        The `str | None` result produced by the operation.

    """
    result: str | None = None
    if isinstance(node, Name):
        result = node.id
    elif isinstance(node, Attribute):
        dotted: str = unparse(ast_obj=node)
        all_identifiers: bool = True
        part: str
        for part in dotted.split(sep=".", maxsplit=-1):
            if not part.isidentifier():
                all_identifiers = False
                break
        result = dotted if all_identifiers else node.attr
    elif isinstance(node, Subscript):
        base: str | None = annotation_name(node=node.value)
        result = (
            annotation_name(node=node.slice)
            if base in Constants.optional_wrappers
            else base
        )
    elif isinstance(node, BinOp) and isinstance(node.op, BitOr):
        left: str | None = annotation_name(node=node.left)
        result = (
            annotation_name(node=node.right)
            if left is None or left in {"None", "NoneType"}
            else left
        )
    return result


def annotation_element(*, node: expr | None) -> str | None:
    """Extract the iterated element type from a container annotation.

    For container annotations like ``list[T]`` or ``dict[K, V]`` the
    first subscript argument names what iterating yields. Wrapper
    annotations (``Optional``, unions) recurse into their members.

    Args:
        node: Annotation expression.

    Returns:
        The `str | None` result produced by the operation.

    """
    result: str | None = None
    if isinstance(node, Subscript):
        base: str | None = annotation_name(node=node.value)
        if base in Constants.container_names:
            sliced: expr = node.slice
            if isinstance(sliced, Tuple) and sliced.elts:
                sliced = sliced.elts[0]
            result = annotation_name(node=sliced)
        elif base is None or base in Constants.optional_wrappers:
            result = annotation_element(node=node.slice)
    elif isinstance(node, Tuple):
        element: expr
        for element in node.elts:
            result = annotation_element(node=element)
            if result is not None:
                break
    elif isinstance(node, BinOp) and isinstance(node.op, BitOr):
        result = annotation_element(node=node.left) or annotation_element(
            node=node.right,
        )
    return result


def value_type_name(*, node: expr | None) -> str | None:
    """Infer a class name for a literal or constructor value.

    Args:
        node: Assigned expression.

    Returns:
        The `str | None` result produced by the operation.

    """
    result: str | None = None
    if isinstance(node, Call):
        result = annotation_name(node=node.func)
    elif isinstance(node, Constant):
        named: str = type(node.value).__name__
        result = named if named != "NoneType" else None
    elif isinstance(node, JoinedStr):
        result = "str"
    elif isinstance(node, Dict):
        result = "dict"
    elif isinstance(node, List):
        result = "list"
    elif isinstance(node, Set):
        result = "set"
    elif isinstance(node, Tuple):
        result = "tuple"
    return result


def param_kind_of(*, parameter: Parameter) -> ParamKind:
    """Map an `inspect` parameter kind to the exactus vocabulary.

    Args:
        parameter: Parameter record from `inspect.Signature`.

    Returns:
        The `ParamKind` result produced by the operation.

    """
    if parameter.kind is Parameter.POSITIONAL_ONLY:
        return "posonly"
    if parameter.kind is Parameter.POSITIONAL_OR_KEYWORD:
        return "poskw"
    if parameter.kind is Parameter.KEYWORD_ONLY:
        return "kwonly"
    if parameter.kind is Parameter.VAR_POSITIONAL:
        return "vararg"
    return "varkw"


def _inspect_param(parameter: Parameter) -> Param:
    """Convert one `inspect` parameter into an exactus parameter.

    Args:
        parameter: Parameter record from `inspect.Signature`.

    Returns:
        The `Param` result produced by the operation.

    """
    return Param(
        name=parameter.name,
        kind=param_kind_of(parameter=parameter),
        has_default=cast(typ="object", val=parameter.default)
        is not Parameter.empty,
    )


def sig_from_inspect(*, name: str, resolved: Signature) -> Sig:
    """Convert an `inspect.Signature` into an exactus signature.

    Args:
        name: Callable name for reporting.
        resolved: Runtime signature.

    Returns:
        The `Sig` result produced by the operation.

    """
    params: list[Param] = list(
        map(_inspect_param, resolved.parameters.values()),
    )
    return Sig(name=name, params=tuple(params))


def build_sig(
    *,
    node: FunctionDef | AsyncFunctionDef | Lambda,
    name: str,
    method: MethodKind,
) -> Sig:
    """Build a signature record from a definition node.

    Args:
        node: Function, async function, or lambda definition.
        name: Callable name for reporting.
        method: Receiver-binding classification.

    Returns:
        The `Sig` result produced by the operation.

    """
    spec: arguments = node.args
    positional: list[arg] = [*spec.posonlyargs, *spec.args]
    default_offset: int = len(positional) - len(spec.defaults)
    params: list[Param] = []
    index: int
    parameter: arg
    for index, parameter in enumerate(iterable=spec.posonlyargs):
        params.append(
            Param(
                name=parameter.arg,
                kind="posonly",
                has_default=index >= default_offset,
            ),
        )
    for index, parameter in enumerate(
        iterable=spec.args,
        start=len(spec.posonlyargs),
    ):
        params.append(
            Param(
                name=parameter.arg,
                kind="poskw",
                has_default=index >= default_offset,
            ),
        )
    if spec.vararg is not None:
        params.append(Param(name=spec.vararg.arg, kind="vararg"))
    kw_parameter: arg
    kw_default: expr | None
    for kw_parameter, kw_default in zip(
        spec.kwonlyargs,
        spec.kw_defaults,
        strict=True,
    ):
        params.append(
            Param(
                name=kw_parameter.arg,
                kind="kwonly",
                has_default=kw_default is not None,
            ),
        )
    if spec.kwarg is not None:
        params.append(Param(name=spec.kwarg.arg, kind="varkw"))
    returns: str | None = None
    if isinstance(node, FunctionDef | AsyncFunctionDef):
        returns = annotation_name(node=node.returns)
    return Sig(name=name, params=tuple(params), method=method, returns=returns)


def method_kind_of(*, node: FunctionDef | AsyncFunctionDef) -> MethodKind:
    """Classify a method's receiver binding from its decorators.

    Args:
        node: Method definition.

    Returns:
        The `MethodKind` result produced by the operation.

    """
    decorator: expr
    for decorator in node.decorator_list:
        text: str = unparse(ast_obj=decorator)
        if text.endswith("staticmethod"):
            return "static"
        if text.endswith("classmethod"):
            return "class"
    return "instance"


def is_dataclass(*, node: ClassDef) -> tuple[bool, bool]:
    """Report whether a class is a dataclass and whether it is kw-only.

    Args:
        node: Class definition.

    Returns:
        The `tuple[bool, bool]` result produced by the operation.

    """
    result: bool = False
    kw_only: bool = False
    decorator: expr
    for decorator in node.decorator_list:
        target: expr = decorator
        if isinstance(decorator, Call):
            target = decorator.func
            item: keyword
            for item in decorator.keywords:
                if (
                    item.arg == "kw_only"
                    and unparse(ast_obj=item.value) == "True"
                ):
                    kw_only = True
        text: str = unparse(ast_obj=target)
        if text in Constants.dataclass_markers or text.endswith(".dataclass"):
            result = True
    return result, kw_only


def field_call_options(*, node: expr) -> tuple[bool, bool]:
    """Read `init` and `kw_only` options from a `field(...)` call.

    Args:
        node: Field default expression.

    Returns:
        The `tuple[bool, bool]` result produced by the operation.

    """
    if not isinstance(node, Call):
        return True, False
    if unparse(ast_obj=node.func).split(sep=".")[-1] != "field":
        return True, False
    init: bool = True
    kw_only: bool = False
    item: keyword
    for item in node.keywords:
        if item.arg is None:
            continue
        text: str = unparse(ast_obj=item.value)
        if item.arg == "init" and text == "False":
            init = False
        if item.arg == "kw_only" and text == "True":
            kw_only = True
    return init, kw_only


def dataclass_params(*, node: ClassDef, kw_only: bool) -> tuple[Param, ...]:
    """Synthesize constructor parameters for a dataclass.

    Args:
        node: Class definition.
        kw_only: Whether `@dataclass(kw_only=True)` applies to all fields.

    Returns:
        The `tuple[Param, ...]` result produced by the operation.

    """
    params: list[Param] = []
    kw_rest: bool = kw_only
    item: stmt
    for item in node.body:
        param: Param | None
        param, kw_rest = dataclass_field(item=item, kw_rest=kw_rest)
        if param is not None:
            params.append(param)
    return tuple(params)


def dataclass_field(*, item: stmt, kw_rest: bool) -> tuple[Param | None, bool]:
    """Convert one class-body statement into a field parameter.

    Args:
        item: Class body statement.
        kw_rest: Whether remaining fields are keyword-only.

    Returns:
        The `tuple[Param | None, bool]` result produced by the
        operation.

    """
    if not isinstance(item, AnnAssign) or not isinstance(item.target, Name):
        return None, kw_rest
    annotation: str = unparse(ast_obj=item.annotation)
    short: str = annotation.rsplit(sep=".", maxsplit=1)[-1].split(
        sep="[",
        maxsplit=1,
    )[0]
    if short == "KW_ONLY":
        return None, True
    if short == "ClassVar":
        return None, kw_rest
    init: bool = True
    field_kw_only: bool = False
    if item.value is not None:
        init, field_kw_only = field_call_options(node=item.value)
    if not init:
        return None, kw_rest
    kind: ParamKind = "kwonly" if kw_rest or field_kw_only else "poskw"
    return (
        Param(
            name=item.target.id,
            kind=kind,
            has_default=item.value is not None,
        ),
        kw_rest,
    )


def namedtuple_params(*, node: ClassDef) -> tuple[Param, ...]:
    """Synthesize constructor parameters for a `NamedTuple` class.

    Args:
        node: Class definition.

    Returns:
        The `tuple[Param, ...]` result produced by the operation.

    """
    params: list[Param] = []
    item: stmt
    for item in node.body:
        if not isinstance(item, AnnAssign) or not isinstance(
            item.target,
            Name,
        ):
            continue
        params.append(
            Param(
                name=item.target.id,
                kind="poskw",
                has_default=item.value is not None,
            ),
        )
    return tuple(params)


def record_self_annotation(
    *,
    info: ClassInfo,
    attr: str,
    annotation: expr,
) -> bool:
    """Record an annotated `self.attr` type and container element.

    Args:
        info: Owning class record.
        attr: Attribute name.
        annotation: Annotation expression.

    Returns:
        Whether the annotation yielded a usable type name.

    """
    named: str | None = annotation_name(node=annotation)
    if named is None:
        return False
    info.attr_types[attr] = named
    element: str | None = annotation_element(node=annotation)
    if element is not None:
        info.attr_elems[attr] = element
    return True


def collect_self_attrs(
    *,
    node: FunctionDef | AsyncFunctionDef,
    info: ClassInfo,
) -> None:
    """Record `self.attr = Type()` assignments as attribute types.

    Args:
        node: Method whose body is scanned.
        info: Owning class record.

    """
    inner: AST
    for inner in walk(node=node):
        target: expr | None = None
        annotation: expr | None = None
        value: expr | None = None
        if isinstance(inner, Assign) and len(inner.targets) == 1:
            target = inner.targets[0]
            value = inner.value
        elif isinstance(inner, AnnAssign):
            target = inner.target
            annotation = inner.annotation
            value = inner.value
        if not isinstance(target, Attribute):
            continue
        if not isinstance(target.value, Name) or target.value.id != "self":
            continue
        if annotation is not None and record_self_annotation(
            info=info,
            attr=target.attr,
            annotation=annotation,
        ):
            continue
        if isinstance(value, Call):
            callee: str | None = annotation_name(node=value.func)
            if callee is not None:
                info.attr_types[target.attr] = callee


def build_classinfo(
    *,
    node: ClassDef,
    module: str,
    path: Path,
    prefix: str,
) -> ClassInfo:
    """Build a class record from a definition node.

    Args:
        node: Class definition.
        module: Owning module name.
        path: File defining the class.
        prefix: Qualified-name prefix for nested classes.

    Returns:
        The `ClassInfo` result produced by the operation.

    """
    qualified: str = f"{prefix}{node.name}" if prefix else node.name
    info: ClassInfo = ClassInfo(name=qualified, module=module, path=path)
    base: expr
    for base in node.bases:
        info.bases.append(unparse(ast_obj=base))
    dataclassed: bool
    kw_only: bool
    dataclassed, kw_only = is_dataclass(node=node)
    if dataclassed:
        info.fields = dataclass_params(node=node, kw_only=kw_only)
    has_namedtuple: bool = False
    base_name: str
    for base_name in info.bases:
        if base_name.rsplit(sep=".", maxsplit=1)[-1] == "NamedTuple":
            has_namedtuple = True
            break
    if has_namedtuple and info.fields is None:
        info.fields = namedtuple_params(node=node)
    item: stmt
    for item in node.body:
        index_class_item(
            item=item,
            info=info,
            module=module,
            path=path,
            qualified=qualified,
        )
    return info


def index_method(
    *,
    item: FunctionDef | AsyncFunctionDef,
    info: ClassInfo,
    qualified: str,
) -> None:
    """Index one method on a class record.

    Args:
        item: Method definition.
        info: Owning class record.
        qualified: Qualified class name.

    """
    info.methods[item.name] = build_sig(
        node=item,
        name=f"{qualified}.{item.name}",
        method=method_kind_of(node=item),
    )
    decorator_names: set[str] = set()
    decorator: expr
    for decorator in item.decorator_list:
        decorator_names |= {
            unparse(ast_obj=decorator)
            .rsplit(sep=".", maxsplit=1)[-1]
            .split(sep="(", maxsplit=1)[0],
        }
    if decorator_names & {"property", "cached_property"}:
        returned: str | None = annotation_name(node=item.returns)
        if returned is not None:
            info.attr_types[item.name] = returned
    collect_self_attrs(node=item, info=info)


def index_class_item(
    *,
    item: stmt,
    info: ClassInfo,
    module: str,
    path: Path,
    qualified: str,
) -> None:
    """Index one class-body statement onto the class record.

    Args:
        item: Class body statement.
        info: Owning class record.
        module: Owning module name.
        path: File defining the class.
        qualified: Qualified class name.

    """
    if isinstance(item, FunctionDef | AsyncFunctionDef):
        index_method(item=item, info=info, qualified=qualified)
    elif isinstance(item, ClassDef):
        info.nested[item.name] = build_classinfo(
            node=item,
            module=module,
            path=path,
            prefix=f"{qualified}.",
        )
    elif isinstance(item, AnnAssign) and isinstance(item.target, Name):
        named_type: str | None = annotation_name(node=item.annotation)
        if named_type is not None:
            info.attr_types[item.target.id] = named_type
            element_type: str | None = annotation_element(node=item.annotation)
            if element_type is not None:
                info.attr_elems[item.target.id] = element_type


def relative_module(*, module: ModuleInfo, level: int, body: str) -> str:
    """Resolve a relative import to an absolute dotted module path.

    Args:
        module: Module performing the import.
        level: Number of leading dots.
        body: Module text after the dots.

    Returns:
        The `str` result produced by the operation.

    """
    if level == 0:
        return body
    parts: list[str] = module.name.split(sep=".")
    container: list[str] = parts if module.is_package else parts[:-1]
    keep: int = max(len(container) - (level - 1), 0)
    base: str = ".".join(container[:keep])
    if not body:
        return base
    if not base:
        return body
    return f"{base}.{body}"


def index_module(*, path: Path, root: Path) -> ModuleInfo | None:
    """Parse and index one module's top-level definitions.

    Args:
        path: Python file path.
        root: Repository root directory.

    Returns:
        The `ModuleInfo | None` result produced by the operation.

    """
    try:
        tree: Module = parse(
            source=path.read_text(encoding="utf-8"),
            filename=str(object=path),
        )
    except (OSError, SyntaxError, ValueError):
        return None
    names: list[str] = module_names(path=path, root=root)
    module: ModuleInfo = ModuleInfo(
        name=names[0] if names else path.stem,
        path=path,
        is_package=path.name == "__init__.py",
        tree=tree,
    )
    item: stmt
    for item in tree.body:
        index_module_item(item=item, module=module, path=path)
    return module


def _index_module_lane(
    *,
    path: Path,
    root: Path,
    progress: BoundedLaneProgress,
) -> ModuleInfo | None:
    """Index one file inside a process-owned worker thread.

    Args:
        path: Python file path.
        root: Repository root directory.
        progress: Shared task-level lane progress.

    Returns:
        Indexed module, or ``None`` when parsing fails.

    """
    error: str | None = None
    try:
        module: ModuleInfo | None = index_module(path=path, root=root)
        if module is None:
            error = "parse failure"
    except Exception as exception:
        error = str(object=exception)
        raise
    else:
        return module
    finally:
        _ = progress.finish(item=str(object=path), error=error)


def index_module_item(*, item: stmt, module: ModuleInfo, path: Path) -> None:
    """Index one module-level statement.

    Statements nested in module-level ``if``/``try`` blocks (notably
    ``if TYPE_CHECKING:`` imports) are indexed as well, because annotations
    rely on them for receiver type inference.

    Args:
        item: Module body statement.
        module: Module record being built.
        path: File path.

    """
    if isinstance(item, FunctionDef | AsyncFunctionDef):
        module.functions[item.name] = build_sig(
            node=item,
            name=item.name,
            method="function",
        )
    elif isinstance(item, ClassDef):
        module.classes[item.name] = build_classinfo(
            node=item,
            module=module.name,
            path=path,
            prefix="",
        )
    elif isinstance(item, Import):
        index_import(node=item, module=module)
    elif isinstance(item, ImportFrom):
        index_import_from(node=item, module=module)
    elif isinstance(item, Assign | AnnAssign):
        index_assignment(node=item, module=module)
    elif isinstance(item, If | Try | TryStar):
        nested: stmt
        for nested in (
            *item.body,
            *item.orelse,
            *(
                ()
                if isinstance(item, If)
                else (
                    *(
                        statement
                        for handler in item.handlers
                        for statement in handler.body
                    ),
                    *item.finalbody,
                )
            ),
        ):
            index_module_item(item=nested, module=module, path=path)


def index_import(*, node: Import, module: ModuleInfo) -> None:
    """Record an `import x` statement on the module record.

    Args:
        node: Import statement.
        module: Module record being built.

    """
    entry: alias
    for entry in node.names:
        if entry.asname is not None:
            module.module_aliases[entry.asname] = entry.name
        else:
            top: str = entry.name.split(sep=".", maxsplit=1)[0]
            _ = consume(value=module.module_aliases.setdefault(top, top))


def index_import_from(*, node: ImportFrom, module: ModuleInfo) -> None:
    """Record a `from x import y` statement on the module record.

    Args:
        node: Import-from statement.
        module: Module record being built.

    """
    base: str = relative_module(
        module=module,
        level=node.level,
        body=node.module or "",
    )
    imported: alias
    for imported in node.names:
        if imported.name == "*":
            continue
        bound: str = imported.asname or imported.name
        dotted: str = f"{base}.{imported.name}" if base else imported.name
        _ = consume(value=module.aliases.setdefault(bound, dotted))


def index_assignment(*, node: Assign | AnnAssign, module: ModuleInfo) -> None:
    """Record a module-level typed assignment.

    Args:
        node: Assignment statement.
        module: Module record being built.

    """
    target: expr | None = None
    name: str | None = None
    if isinstance(node, Assign) and len(node.targets) == 1:
        target = node.targets[0]
        name = value_type_name(node=node.value)
    elif isinstance(node, AnnAssign):
        target = node.target
        name = annotation_name(node=node.annotation)
        if (
            isinstance(target, Name)
            and isinstance(node.annotation, Subscript)
            and annotation_name(node=node.annotation.value) == "type"
        ):
            class_name: str | None = annotation_name(
                node=node.annotation.slice,
            )
            if class_name is not None:
                module.aliases[target.id] = module.aliases.get(
                    class_name,
                    f"{module.name}.{class_name}"
                    if class_name in module.classes
                    else class_name,
                )
                return
        if name is None and node.value is not None:
            name = value_type_name(node=node.value)
    if isinstance(target, Name) and name is not None:
        module.var_types[target.id] = name
    if isinstance(target, Name) and isinstance(node.value, Name | Attribute):
        module.call_exprs[target.id] = unparse(ast_obj=node.value)


def _stub_param(param: Param) -> Param:
    """Map one stub parameter's dunder-name convention to `posonly`.

    Args:
        param: Parameter parsed from a stub signature.

    Returns:
        The `Param` result produced by the operation.

    """
    return Param(
        name=param.name,
        kind=(
            "posonly"
            if param.name.startswith("__") and param.kind == "poskw"
            else param.kind
        ),
        has_default=param.has_default,
    )


def stub_sig(
    *,
    node: FunctionDef | AsyncFunctionDef,
    name: str,
    method: MethodKind,
) -> Sig:
    """Build a signature from a stub definition.

    Typeshed uses the `__name` convention for positional-only
    parameters that cannot be expressed with `/`; those are mapped to
    `posonly` here.

    Args:
        node: Stub function definition.
        name: Callable name for reporting.
        method: Receiver-binding classification.

    Returns:
        The `Sig` result produced by the operation.

    """
    built: Sig = build_sig(node=node, name=name, method=method)
    adjusted: tuple[Param, ...] = tuple(map(_stub_param, built.params))
    return Sig(
        name=built.name,
        params=adjusted,
        method=built.method,
        returns=built.returns,
    )


def _is_positional(param: Param) -> bool:
    """Return whether `param` binds positional arguments.

    Args:
        param: Parameter to classify.

    Returns:
        Whether the parameter is `posonly` or `poskw`.

    """
    return param.kind in {"posonly", "poskw"}


def _is_posonly(param: Param) -> bool:
    """Return whether `param` is positional-only.

    Args:
        param: Parameter to classify.

    Returns:
        Whether the parameter kind is `posonly`.

    """
    return param.kind == "posonly"


def _positional_prefix(sig: Sig) -> tuple[Param, ...]:
    """Return the leading positional parameters of `sig`.

    Args:
        sig: Signature whose positional prefix is wanted.

    Returns:
        The `Param` prefix bound positionally.

    """
    index: int = 0
    while index < len(sig.params) and _is_positional(param=sig.params[index]):
        index += 1
    return sig.params[:index]


def _base_posonly_positions(
    *,
    base_positional: list[tuple[Param, ...]],
) -> set[int]:
    """Return indexes every covering base signature marks `posonly`.

    Args:
        base_positional: Positional parameter prefixes from bases.

    Returns:
        Positional indexes declared `posonly` by every base
        signature that covers them.

    """
    positions: set[int] = set()
    index: int
    params: tuple[Param, ...]
    covering: list[Param]
    for index in range(max(map(len, base_positional), default=0)):
        covering = []
        for params in base_positional:
            if len(params) <= index:
                continue
            covering.append(params[index])
        if covering and all(map(_is_posonly, covering)):
            positions.add(index)
    return positions


def _demote_posonly(sig: Sig, *, positions: set[int]) -> Sig:
    """Demote `poskw` params whose position is base-positional-only.

    Args:
        sig: Override signature to adjust.
        positions: Positional indexes the base contract marks `posonly`.

    Returns:
        The `Sig` result produced by the operation.

    """
    if not positions:
        return sig
    params: list[Param] = []
    index: int
    param: Param
    for index, param in enumerate(iterable=sig.params):
        if index in positions and param.kind == "poskw":
            params.append(replace(param, kind="posonly"))
        else:
            params.append(param)
    return replace(sig, params=tuple(params))


def _inherit_posonly(
    *,
    sigs: tuple[Sig, ...],
    base_sigs: list[Sig],
) -> tuple[Sig, ...]:
    """Demote override params that base signatures mark `posonly`.

    An override cannot loosen a base contract's positional-only
    parameters; stub overrides occasionally drop `/` (for example
    `os._Environ.get` vs `Mapping.get`), so the base contract wins.

    Args:
        sigs: Override signatures resolved on the derived class.
        base_sigs: Signatures for the same method found in bases.

    Returns:
        The `Sig` tuple with base-positional-only parameters
        demoted to `posonly`.

    """
    if not base_sigs:
        return sigs
    positions: set[int] = _base_posonly_positions(
        base_positional=list(map(_positional_prefix, base_sigs)),
    )
    return tuple(map(partial(_demote_posonly, positions=positions), sigs))


_STUB_COMPARISONS: Final[dict[type, Callable[[object, object], bool]]] = cast(
    typ="dict[type, Callable[[object, object], bool]]",
    val={Eq: eq, NotEq: ne, Gt: gt, GtE: ge, Lt: lt, LtE: le},
)


@dataclass(frozen=True, slots=True)
class TargetPython:
    """Interpreter facts the analyzed project is written for.

    Typeshed gates definitions behind ``sys.version_info`` and
    ``sys.platform`` guards. Deciding them with the interpreter that
    happens to run the analyzer reports calls the project's own
    interpreter rejects (``ctypes.POINTER`` takes ``cls`` on 3.14 but
    only a positional ``type`` on 3.13), so every guard is decided
    with these facts instead.

    Attributes:
        executable: Interpreter these facts were read from.
        version_info: Full ``sys.version_info`` of that interpreter.
        platform: ``sys.platform`` of that interpreter.

    """

    executable: str
    version_info: tuple[int | str, ...]
    platform: str

    @property
    def release(self: Self) -> str:
        """Render the interpreter's ``major.minor.micro`` version.

        Returns:
            The dotted version, for example ``3.13.9``.

        """
        return ".".join(map(str, self.version_info[:3]))


def current_python() -> TargetPython:
    """Describe the interpreter that is running the analyzer.

    Returns:
        The running interpreter's facts, used when the analyzed project
        has no interpreter of its own.

    """
    return TargetPython(
        executable=executable,
        version_info=tuple(version_info),
        platform=sys_platform,
    )


def project_interpreter(*, root: Path) -> Path | None:
    """Locate the interpreter a project runs on.

    Args:
        root: Analyzed project root.

    Returns:
        The first existing interpreter among the conventional
        virtual-environment locations under `root`, or ``None``.

    """
    return next(
        (
            candidate
            for candidate in (
                root / relative
                for relative in Constants.interpreter_candidates
            )
            if candidate.is_file()
        ),
        None,
    )


def _requires_python(*, root: Path) -> str:
    """Read the ``requires-python`` specifier of an analyzed project.

    Args:
        root: Analyzed project root.

    Returns:
        The declared specifier text, or ``""`` when undeclared.

    """
    config: Path = root / "pyproject.toml"
    if not config.is_file():
        return ""
    try:
        document: dict[str, object] = toml_loads(
            config.read_text(encoding="utf-8"),
        )
    except (OSError, ValueError):
        return ""
    project: object = document.get("project")
    if isinstance(project, dict):
        table: dict[str, object] = cast(typ="dict[str, object]", val=project)
        specifier: object = table.get("requires-python", "")
        if isinstance(specifier, str):
            return specifier
    return ""


def _spec_clauses(
    *,
    specifier: str,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Parse a ``requires-python`` specifier into comparable clauses.

    Args:
        specifier: Comma-separated PEP 440 subset such as ``>=3.13``.

    Returns:
        ``(operator, version-tuple)`` pairs, or empty when any clause
        is unparseable.

    """
    clauses: list[tuple[str, tuple[int, ...]]] = []
    for part in specifier.split(sep=","):
        matched: Match[str] | None = fullmatch(
            pattern=r"(===|==|!=|~=|>=|<=|>|<)?\s*([0-9]+(?:\.[0-9*]+)*)\s*",
            string=part.strip(),
        )
        if matched is None:
            return ()
        numbers: tuple[int, ...] = tuple(
            int(piece)
            for piece in matched.group(2).split(sep=".")
            if piece != "*"
        )
        if not numbers:
            return ()
        clauses.append((matched.group(1) or "==", numbers))
    return tuple(clauses)


def _clause_ok(
    *,
    version: tuple[int, ...],
    padded: tuple[int, ...],
    operator: str,
    expected: tuple[int, ...],
) -> bool:
    """Evaluate one specifier clause against an interpreter version.

    Args:
        version: Numeric prefix of the interpreter ``version_info``.
        padded: ``version`` zero-padded to the longest expected width.
        operator: Clause operator such as ``>=`` or ``~=``.
        expected: Clause version tuple.

    Returns:
        Whether the version satisfies this clause.

    """
    target: tuple[int, ...] = expected + (0,) * (len(padded) - len(expected))
    equal: tuple[int, ...] = version[: len(expected)]
    result: bool | None = None
    if operator in ("==", "==="):
        result = equal == expected
    elif operator == "!=":
        result = equal != expected
    elif operator == ">=":
        result = padded >= target
    elif operator == "<=":
        result = padded <= target
    elif operator == ">":
        result = padded > target
    elif operator == "<":
        result = padded < target
    elif operator == "~=":
        upper: tuple[int, ...] = (
            (*expected[:-2], expected[-2] + 1)
            if len(expected) > 1
            else ((expected[0] + 1,) if expected else ())
        )
        result = target <= padded < upper
    return result if result is not None else True


def _version_ok(
    *,
    version: tuple[int, ...],
    clauses: tuple[tuple[str, tuple[int, ...]], ...],
) -> bool:
    """Decide whether an interpreter version satisfies every clause.

    Args:
        version: Numeric prefix of the interpreter ``version_info``.
        clauses: Parsed ``(operator, expected)`` pairs.

    Returns:
        Whether the version satisfies the whole specifier.

    """
    size: int = max(
        (len(expected) for _, expected in clauses),
        default=len(version),
    )
    padded: tuple[int, ...] = version + (0,) * max(0, size - len(version))
    return all(
        _clause_ok(
            version=version,
            padded=padded,
            operator=operator,
            expected=expected,
        )
        for operator, expected in clauses
    )


def _resolve_python(*, name: str) -> Path | None:
    """Resolve a configured interpreter name, path, or environment.

    Args:
        name: Executable path, virtual-environment directory, or
            ``PATH`` lookup from the ``python`` setting.

    Returns:
        The resolved interpreter path, or ``None``.

    """
    candidate: Path = Path(name)
    if candidate.is_file():
        return candidate
    if candidate.is_dir():
        for relative in ("bin/python", "Scripts/python.exe"):
            interpreter: Path = candidate / relative
            if interpreter.is_file():
                return interpreter
        return None
    resolved: str | None = which(cmd=name)
    return Path(resolved) if resolved is not None else None


def _spec_candidates(*, skip: frozenset[Path]) -> list[Path]:
    """List ``PATH`` interpreters by generic name.

    Args:
        skip: Already-considered interpreter paths to exclude.

    Returns:
        Deduplicated existing interpreter paths.

    """
    seen: set[Path] = set(skip)
    candidates: list[Path] = []
    for name in ("python3", "python"):
        resolved: str | None = which(cmd=name)
        if resolved is None:
            continue
        interpreter: Path = Path(resolved)
        if interpreter not in seen:
            seen.add(interpreter)
            candidates.append(interpreter)
    return candidates


def _probe_target(*, interpreter: Path) -> TargetPython | None:
    """Ask one interpreter for its version and platform facts.

    Args:
        interpreter: Candidate interpreter executable.

    Returns:
        The parsed facts, or ``None`` when the interpreter fails or
        answers nonsense.

    """
    try:
        completed: CompletedProcess[str] = run(
            args=[
                str(object=interpreter),
                "-I",
                "-c",
                Constants.interpreter_probe,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=Constants.interpreter_timeout,
        )
    except (OSError, TimeoutExpired) as error:
        trace(step=f"python: {interpreter} unusable ({error})", depth=2)
        return None
    if completed.returncode != 0:
        return None
    return _parse_target(stdout=completed.stdout, interpreter=interpreter)


def _parse_target(*, stdout: str, interpreter: Path) -> TargetPython | None:
    """Validate the answer of the interpreter probe.

    Args:
        stdout: Text the probe printed.
        interpreter: Interpreter that produced the answer.

    Returns:
        The validated facts, or ``None`` when the answer is malformed.

    """
    try:
        payload: object = json_loads(s=stdout)
    except ValueError:
        return None
    if not isinstance(payload, list):
        return None
    try:
        raw_version: object
        raw_platform: object
        raw_version, raw_platform = cast(typ="list[object]", val=payload)
    except ValueError:
        return None
    if not isinstance(raw_version, list) or not isinstance(raw_platform, str):
        return None
    version_items: list[object] = cast(typ="list[object]", val=raw_version)
    parts: tuple[int | str, ...] = tuple(
        part for part in version_items if isinstance(part, int | str)
    )
    if not parts or len(parts) != len(version_items):
        return None
    return TargetPython(
        executable=str(object=interpreter),
        version_info=parts,
        platform=raw_platform,
    )


def target_python(*, root: Path, python: str | None = None) -> TargetPython:
    """Resolve the interpreter facts inference must run against.

    A configured ``python`` setting names the interpreter to use
    outright — an executable, a ``PATH`` name, or a virtual-environment
    directory. Otherwise a discovered project virtual environment is
    authoritative: ``.venv``/``venv`` is used regardless of
    ``requires-python``, because the environment the project actually
    runs on is the truth inference should model. Only when no project
    interpreter exists at all are ``PATH`` candidates probed, each
    checked against the project's ``requires-python``. When nothing
    satisfies the specifier the analyzer falls back to the running
    interpreter and records the substitution in the step log so it is
    never silent.

    Args:
        root: Analyzed project root.
        python: Configured interpreter path, ``PATH`` name, or
            virtual-environment directory.

    Returns:
        The facts of the selected interpreter, else the running one.

    """
    if python:
        configured: Path | None = _resolve_python(name=python)
        if configured is None:
            trace(step=f"python: {python} not found; probing", depth=2)
        else:
            selected: TargetPython | None = _probe_target(
                interpreter=configured,
            )
            if selected is not None:
                trace(
                    step=(
                        f"python: {configured} {selected.release} (configured)"
                    ),
                    depth=2,
                )
                return selected
            trace(step=f"python: {configured} gave no usable answer", depth=2)
    environment: Path | None = project_interpreter(root=root)
    if environment is not None:
        discovered: TargetPython | None = _probe_target(
            interpreter=environment,
        )
        if discovered is not None:
            trace(step=f"python: {environment} {discovered.release}", depth=2)
            return discovered
    clauses: tuple[tuple[str, tuple[int, ...]], ...] = _spec_clauses(
        specifier=_requires_python(root=root),
    )
    candidates: list[Path] = []
    if clauses:
        candidates.extend(
            _spec_candidates(
                skip=frozenset(
                    (environment.resolve(),)
                    if environment is not None
                    else (),
                ),
            ),
        )
    for interpreter in candidates:
        parsed: TargetPython | None = _probe_target(interpreter=interpreter)
        if parsed is None:
            continue
        version: tuple[int, ...] = tuple(
            piece for piece in parsed.version_info if isinstance(piece, int)
        )
        if clauses and not _version_ok(version=version, clauses=clauses):
            trace(
                step=(
                    f"python: {interpreter} {parsed.release} outside "
                    "requires-python"
                ),
                depth=2,
            )
            continue
        trace(step=f"python: {interpreter} {parsed.release}", depth=2)
        return parsed
    return current_python()


def _stub_compare(*, test: Compare, target: TargetPython) -> bool | None:
    """Evaluate a ``sys.version_info``/``sys.platform`` comparison.

    Args:
        test: Single-operator comparison from a stub ``if`` guard.
        target: Interpreter facts the guard is decided with.

    Returns:
        The comparison result, or ``None`` when it is not a known guard.

    """
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    operation: Callable[[object, object], bool] | None = _STUB_COMPARISONS.get(
        type(test.ops[0]),
    )
    if operation is None:
        return None
    subject: str = unparse(ast_obj=test.left)
    try:
        expected: object = literal_eval(node_or_string=test.comparators[0])
    except ValueError:
        return None
    if subject.startswith("sys.version_info") and isinstance(expected, tuple):
        bound: tuple[object, ...] = cast(
            typ="tuple[object, ...]",
            val=expected,
        )
        return operation(target.version_info[: len(bound)], bound)
    if subject == "sys.platform" and isinstance(expected, str):
        return operation(target.platform, expected)
    return None


def _stub_condition(*, test: expr, target: TargetPython) -> bool | None:
    """Evaluate a typeshed ``if`` guard against the project's interpreter.

    Supports ``sys.version_info`` and ``sys.platform`` comparisons,
    ``sys.platform.startswith(...)``, ``not``, ``and`` and ``or``.

    Args:
        test: Guard expression.
        target: Interpreter facts the guard is decided with.

    Returns:
        The guard's value, or ``None`` when it cannot be decided.

    """
    if isinstance(test, UnaryOp) and isinstance(test.op, Not):
        inner: bool | None = _stub_condition(test=test.operand, target=target)
        return None if inner is None else not inner
    if isinstance(test, BoolOp):
        values: list[bool | None] = [
            _stub_condition(test=value, target=target) for value in test.values
        ]
        if isinstance(test.op, And):
            return (
                False if False in values else None if None in values else True
            )
        return True if True in values else None if None in values else False
    if isinstance(test, Compare):
        return _stub_compare(test=test, target=target)
    if (
        isinstance(test, Call)
        and unparse(ast_obj=test.func) == "sys.platform.startswith"
        and len(test.args) == 1
        and isinstance(test.args[0], Constant)
        and isinstance(test.args[0].value, str)
    ):
        return target.platform.startswith(test.args[0].value)
    return None


def live_stub_statements(
    *,
    body: list[stmt],
    target: TargetPython,
) -> list[stmt]:
    """Flatten stub ``if`` blocks to the statements live on the target.

    Version- and platform-gated branches that do not apply are dropped,
    so obsolete overloads (for example pre-3.12 ``Path.relative_to``)
    cannot make a call look ambiguous. Undecidable guards keep both
    branches.

    Args:
        body: Statements of a stub module or class body.
        target: Interpreter facts the guards are decided with.

    Returns:
        Live statements in source order, ``if`` blocks expanded.

    """
    live: list[stmt] = []
    item: stmt
    for item in body:
        if not isinstance(item, If):
            live.append(item)
            continue
        verdict: bool | None = _stub_condition(test=item.test, target=target)
        if verdict is not False:
            live.extend(live_stub_statements(body=item.body, target=target))
        if verdict is not True:
            live.extend(live_stub_statements(body=item.orelse, target=target))
    return live


def build_stub_class(
    *,
    node: ClassDef,
    prefix: str,
    target: TargetPython,
) -> StubClass:
    """Build a stub class record from a `.pyi` class definition.

    Args:
        node: Stub class definition.
        prefix: Qualified-name prefix for nested classes.
        target: Interpreter facts version guards are decided with.

    Returns:
        The `StubClass` result produced by the operation.

    """
    qualified: str = f"{prefix}{node.name}" if prefix else node.name
    info: StubClass = StubClass(name=qualified)
    base: expr
    for base in node.bases:
        info.bases.append(unparse(ast_obj=base))
    item: stmt
    for item in live_stub_statements(body=node.body, target=target):
        _collect_stub_class_item(
            info=info,
            item=item,
            qualified=qualified,
            target=target,
        )
    return info


def _collect_stub_class_item(
    *,
    info: StubClass,
    item: stmt,
    qualified: str,
    target: TargetPython,
) -> None:
    """Collect one class-body item into a stub class record.

    Version-gated ``if`` blocks are expanded beforehand by
    `live_stub_statements`.

    Args:
        info: Stub class record being built.
        item: Class body statement.
        qualified: Qualified-name prefix for nested classes.
        target: Interpreter facts version guards are decided with.

    """
    if isinstance(item, FunctionDef | AsyncFunctionDef):
        built: Sig = stub_sig(
            node=item,
            name=f"{qualified}.{item.name}",
            method=method_kind_of(node=item),
        )
        if item.name in {"__init__", "__new__"}:
            info.ctors.append(built)
        else:
            info.methods.setdefault(item.name, []).append(built)
    elif isinstance(item, ClassDef):
        info.nested[item.name] = build_stub_class(
            node=item,
            prefix=f"{qualified}.",
            target=target,
        )


def _typeshed_fallback_candidates() -> list[Path]:
    """Collect candidate typeshed-fallback directories.

    Searches site-packages for a ``basedpyright`` or ``pyright``
    distribution and ``~/.devin/extensions`` for bundled typeshed
    copies shipped by IDE extensions. BasedPyright typeshed is the
    canonical source (it ships the override-rich stubs the
    ``_inherit_posonly`` base-contract logic depends on, e.g.
    ``os._Environ.get``), so candidates whose path names it are
    sorted ahead of plain ``pyright``/windsurf copies.

    Returns:
        Candidate ``typeshed-fallback`` directories that exist,
        BasedPyright copies first.

    """
    candidates: list[Path] = []
    try:
        package: ModuleType = import_module(name="basedpyright")
        package_file: object = getattr(package, "__file__", None)
        if isinstance(package_file, str):
            candidate: Path = (
                Path(package_file).parent / "dist" / "typeshed-fallback"
            )
            if candidate.is_dir():
                candidates.append(candidate)
    except (ImportError, TypeError, ValueError):
        pass
    site: Path = Path(executable).parent.parent / "lib"
    candidates.extend(
        sorted(
            site.glob(
                pattern="python*/site-packages/basedpyright/dist/typeshed-fallback",
            ),
        ),
    )
    candidates.extend(
        sorted(
            site.glob(
                pattern="python*/site-packages/pyright/dist/typeshed-fallback",
            ),
        ),
    )
    extensions: Path = Path.home() / ".devin" / "extensions"
    if extensions.is_dir():
        candidates.extend(
            sorted(
                extensions.glob(pattern="*pyright*/dist/typeshed-fallback"),
            ),
        )
    candidates.sort(key=lambda path: "basedpyright" not in f"{path}")
    return candidates


def stub_roots() -> list[Path]:
    """Locate typeshed stub roots bundled with a type checker.

    Returns:
        The `list[pathlib.Path]` result produced by the operation.

    """
    base: Path | None = None
    candidate: Path
    for candidate in _typeshed_fallback_candidates():
        if candidate.is_dir():
            base = candidate
            break
    if base is None:
        return []
    roots: list[Path] = [base / "stdlib"]
    stubs_dir: Path = base / "stubs"
    if stubs_dir.is_dir():
        roots.extend(sorted(filter(Path.is_dir, stubs_dir.iterdir())))
    return roots


class StubClassLookupArgs(TypedDict):
    """Represent stub class lookup args.

    Attributes:
        module: Module.
        info: Info.
        rest: Rest.
        bound: Bound.
        dotted: Dotted.
        depth: Depth.

    """

    module: StubModule
    info: StubClass
    rest: list[str]
    bound: bool
    dotted: str
    depth: int


class StubIndex:
    """Lazily parsed typeshed signatures for external callables."""

    def __init__(
        self: Self,
        *,
        roots: list[Path],
        target: TargetPython,
    ) -> None:
        """Initialize the stub index.

        Args:
            roots: Stub search roots.
            target: Interpreter facts version guards are decided with.

        """
        self.roots: list[Path] = roots
        self.target: TargetPython = target
        self.cache: dict[str, StubModule | None] = {}
        self.lookup_cache: dict[tuple[str, int], Resolved] = {}
        self.prefix_cache: dict[str, tuple[StubModule, list[str]] | None] = {}

    @staticmethod
    def from_source(*, item: ImportFrom, dotted: str) -> str:
        """Resolve an `ImportFrom` node to its absolute source module.

        Args:
            item: Import statement inside the stub.
            dotted: Dotted name of the stub module containing it.

        Returns:
            The `str` result produced by the operation.

        """
        if item.level == 0:
            return item.module or ""
        package: str = ".".join(dotted.split(sep=".")[: -item.level])
        if item.module:
            return f"{package}.{item.module}" if package else item.module
        return package

    def module(self: Self, *, dotted: str) -> StubModule | None:
        """Return the stub module for a dotted path, if any.

        Args:
            dotted: Dotted module path.

        Returns:
            The `StubModule | None` result produced by the operation.

        """
        if dotted in self.cache:
            return self.cache[dotted]
        found: StubModule | None = None
        relative: Path = Path(*dotted.split(sep="."))
        root: Path
        for root in self.roots:
            candidate: Path
            for candidate in (
                root / relative.with_suffix(suffix=".pyi"),
                root / relative / "__init__.pyi",
            ):
                if candidate.is_file():
                    found = self.parse_stub(path=candidate, dotted=dotted)
                    break
            if found is not None:
                break
        self.cache[dotted] = found
        return found

    def parse_stub(
        self: Self,
        *,
        path: Path,
        dotted: str,
    ) -> StubModule | None:
        """Parse one stub file into a module record.

        Args:
            path: Stub file path.
            dotted: Dotted module name.

        Returns:
            The `StubModule | None` result produced by the operation.

        """
        try:
            tree: Module = parse(
                source=path.read_text(encoding="utf-8"),
                filename=str(object=path),
            )
        except (OSError, SyntaxError, ValueError):
            return None
        module: StubModule = StubModule(name=dotted)
        item: stmt
        for item in live_stub_statements(body=tree.body, target=self.target):
            if isinstance(item, FunctionDef | AsyncFunctionDef):
                module.functions.setdefault(item.name, []).append(
                    stub_sig(
                        node=item,
                        name=f"{dotted}.{item.name}",
                        method="function",
                    ),
                )
            elif isinstance(item, ClassDef):
                module.classes[item.name] = build_stub_class(
                    node=item,
                    prefix="",
                    target=self.target,
                )
            elif isinstance(item, ImportFrom):
                source: str = self.from_source(item=item, dotted=dotted)
                if not source:
                    continue
                _alias: alias
                for _alias in item.names:
                    if _alias.name == "*":
                        module.star_sources.append(source)
                        continue
                    module.reexports[_alias.asname or _alias.name] = (
                        source,
                        _alias.name,
                    )
        return module

    def module_prefix(
        self: Self,
        *,
        dotted: str,
    ) -> tuple[StubModule, list[str]] | None:
        """Return the longest stub-module prefix for a dotted path.

        Args:
            dotted: Dotted module or symbol path.

        Returns:
            The longest module and remaining symbol path, if available.

        """
        if dotted in self.prefix_cache:
            return self.prefix_cache[dotted]
        module: StubModule | None = self.module(dotted=dotted)
        if module is not None:
            result: tuple[StubModule, list[str]] = (module, [])
            self.prefix_cache[dotted] = result
            return result
        parent: str
        separator: str
        name: str
        parent, separator, name = dotted.rpartition(".")
        if not separator:
            self.prefix_cache[dotted] = None
            return None
        prefix: tuple[StubModule, list[str]] | None = self.module_prefix(
            dotted=parent,
        )
        if prefix is None:
            self.prefix_cache[dotted] = None
            return None
        result = (prefix[0], [*prefix[1], name])
        self.prefix_cache[dotted] = result
        return result

    def lookup(self: Self, *, dotted: str, depth: int = 0) -> Resolved:
        """Resolve a dotted path through the stub index.

        Args:
            dotted: Dotted symbol path.
            depth: Re-export recursion guard.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if depth > Constants.max_depth:
            return Resolved()
        key: tuple[str, int] = (dotted, depth)
        cached: Resolved | None = self.lookup_cache.get(key)
        if cached is not None:
            return cached
        prefix: tuple[StubModule, list[str]] | None = self.module_prefix(
            dotted=dotted,
        )
        resolved: Resolved | None = (
            self.in_module(
                module=prefix[0],
                rest=prefix[1],
                dotted=dotted,
                depth=depth,
            )
            if prefix is not None
            else None
        )
        if resolved is None:
            resolved = (
                self.lookup(dotted=f"builtins.{dotted}", depth=depth + 1)
                if not dotted.startswith("builtins.")
                else Resolved()
            )
        self.lookup_cache[key] = resolved
        return resolved

    def in_module(
        self: Self,
        *,
        module: StubModule,
        rest: list[str],
        dotted: str,
        depth: int,
    ) -> Resolved:
        """Resolve a name inside a stub module.

        Args:
            module: Stub module to search.
            rest: Remaining attribute path segments.
            dotted: Full dotted path for reporting.
            depth: Re-export recursion guard.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if not rest:
            return Resolved(kind="stubmod", stub=module, dotted=dotted)
        name: str = rest[0]
        if name in module.functions and len(rest) == 1:
            return Resolved(
                kind="function",
                sigs=tuple(module.functions[name]),
                dotted=dotted,
            )
        if name in module.classes:
            return self.in_module_class(
                module=module,
                info=module.classes[name],
                rest=rest,
                dotted=dotted,
                depth=depth,
            )
        if name in module.reexports:
            source: str
            original: str
            source, original = module.reexports[name]
            return self.lookup(
                dotted=".".join([source, original, *rest[1:]]),
                depth=depth + 1,
            )
        star: str
        for star in module.star_sources:
            resolved: Resolved = self.lookup(
                dotted=".".join([star, *rest]),
                depth=depth + 1,
            )
            if resolved.kind != "unknown":
                return resolved
        return self.in_stub_submodule(
            module=module,
            name=name,
            rest=rest,
            dotted=dotted,
            depth=depth,
        )

    def in_module_class(
        self: Self,
        *,
        module: StubModule,
        info: StubClass,
        rest: list[str],
        dotted: str,
        depth: int,
    ) -> Resolved:
        """Resolve a class member path inside a stub module.

        Args:
            module: Stub module the class is declared in.
            info: Stub class to search.
            rest: Remaining path segments, starting with the class name.
            dotted: Full dotted path for reporting.
            depth: Re-export recursion guard.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if len(rest) == 1:
            return Resolved(kind="stubclass", stub=info, dotted=dotted)
        return self.in_class(
            module=module,
            info=info,
            rest=rest[1:],
            bound=False,
            dotted=dotted,
            depth=depth,
        )

    def in_stub_submodule(
        self: Self,
        *,
        module: StubModule,
        name: str,
        rest: list[str],
        dotted: str,
        depth: int,
    ) -> Resolved:
        """Resolve a path that descends into a stub submodule.

        Args:
            module: Parent stub module.
            name: Submodule name segment.
            rest: Remaining path segments, starting with `name`.
            dotted: Full dotted path for reporting.
            depth: Re-export recursion guard.

        Returns:
            The `Resolved` result produced by the operation.

        """
        submodule: StubModule | None = self.module(
            dotted=f"{module.name}.{name}",
        )
        if submodule is None:
            return Resolved()
        if len(rest) == 1:
            return Resolved(kind="stubmod", stub=submodule, dotted=dotted)
        return self.in_module(
            module=submodule,
            rest=rest[1:],
            dotted=dotted,
            depth=depth,
        )

    def in_class(
        self: Self,
        **kwargs: Unpack[StubClassLookupArgs],
    ) -> Resolved:
        """Return in class.

        Args:
            kwargs: Kwargs.

        Returns:
            The resulting value.

        """
        module: StubModule = kwargs["module"]
        info: StubClass = kwargs["info"]
        rest: list[str] = kwargs["rest"]
        bound: bool = kwargs["bound"]
        dotted: str = kwargs["dotted"]
        depth: int = kwargs["depth"]
        if not rest:
            return Resolved(kind="stubclass", stub=info, dotted=dotted)
        name: str = rest[0]
        if name in info.nested:
            child: StubClass = info.nested[name]
            if len(rest) == 1:
                return Resolved(kind="stubclass", stub=child, dotted=dotted)
            return self.in_class(
                module=module,
                info=child,
                rest=rest[1:],
                bound=bound,
                dotted=dotted,
                depth=depth,
            )
        if name in info.methods and len(rest) == 1:
            return Resolved(
                kind="function",
                sigs=_inherit_posonly(
                    sigs=tuple(info.methods[name]),
                    base_sigs=self.base_method_sigs(
                        module=module,
                        info=info,
                        name=name,
                        depth=depth,
                    ),
                ),
                bound=bound,
                dotted=dotted,
            )
        return self.in_bases(
            module=module,
            info=info,
            rest=rest,
            bound=bound,
            dotted=dotted,
            depth=depth,
        )

    def in_bases(
        self: Self,
        **kwargs: Unpack[StubClassLookupArgs],
    ) -> Resolved:
        """Return in bases.

        Args:
            kwargs: Kwargs.

        Returns:
            The resulting value.

        """
        module: StubModule = kwargs["module"]
        info: StubClass = kwargs["info"]
        rest: list[str] = kwargs["rest"]
        bound: bool = kwargs["bound"]
        dotted: str = kwargs["dotted"]
        depth: int = kwargs["depth"]
        if depth >= Constants.max_depth:
            return Resolved()
        base: str
        for base in info.bases:
            bare: str = base.split(sep="[")[0].strip()
            if not bare:
                continue
            resolved: Resolved = self.lookup(
                dotted=bare if "." in bare else f"{module.name}.{bare}",
                depth=depth + 1,
            )
            if resolved.kind != "stubclass" or not isinstance(
                resolved.stub,
                StubClass,
            ):
                continue
            owner_name: str = resolved.dotted.removesuffix(
                f".{resolved.stub.name}",
            )
            owner: StubModule = self.module(dotted=owner_name) or module
            hit: Resolved = self.in_class(
                module=owner,
                info=resolved.stub,
                rest=rest,
                bound=bound,
                dotted=dotted,
                depth=depth + 1,
            )
            if hit.kind != "unknown":
                return hit
        return Resolved()

    def base_method_sigs(
        self: Self,
        *,
        module: StubModule,
        info: StubClass,
        name: str,
        depth: int,
    ) -> list[Sig]:
        """Collect `name` signatures declared across the base classes.

        Args:
            module: Stub module the class is declared in.
            info: Stub class whose bases are searched.
            name: Method name to collect.
            depth: Recursion guard.

        Returns:
            Signatures for `name` found in base classes.

        """
        if depth >= Constants.max_depth:
            return []
        found: list[Sig] = []
        base: str
        for base in info.bases:
            bare: str = base.split(sep="[")[0].strip()
            if not bare:
                continue
            resolved: Resolved = self.lookup(
                dotted=bare if "." in bare else f"{module.name}.{bare}",
                depth=depth + 1,
            )
            if resolved.kind != "stubclass" or not isinstance(
                resolved.stub,
                StubClass,
            ):
                continue
            found.extend(resolved.stub.methods.get(name, []))
            owner_name: str = resolved.dotted.removesuffix(
                f".{resolved.stub.name}",
            )
            found.extend(
                self.base_method_sigs(
                    module=self.module(dotted=owner_name) or module,
                    info=resolved.stub,
                    name=name,
                    depth=depth + 1,
                ),
            )
        return found


class Project:
    """Repository-wide index used to resolve call sites."""

    def __init__(
        self: Self,
        *,
        root: Path,
        path_filter: Callable[[Path], bool] | None = None,
        capability: CapabilityIndex | None = None,
        source_paths: list[Path] | None = None,
        python: str | None = None,
    ) -> None:
        """Build the index for every Python file under `root`.

        Args:
            root: Repository root directory.
            path_filter: Optional predicate restricting discovered files.
            capability: Canonical runtime capability snapshot; when
                present it overrides live resolution for indexed
                external callables.
            source_paths: Optional stable source inventory to index.
            python: Configured interpreter path or ``PATH`` name whose
                facts steer version and platform inference.

        """
        self.root: Path = root
        self.modules: dict[str, ModuleInfo] = {}
        self.by_path: dict[Path, ModuleInfo] = {}
        self.classes: dict[str, list[ClassInfo]] = defaultdict(list)
        self.methods: dict[str, list[tuple[ClassInfo, Sig]]] = defaultdict(
            list,
        )
        self.externals: dict[str, object] = {}
        self.external_sigs: dict[str, Sig | None] = {}
        self.external_resolutions: dict[str, Resolved] = {}
        self.class_name_cache: dict[str, ClassInfo | None] = {}
        self.method_cache: dict[tuple[int, str], Sig | None] = {}
        self.probes: dict[tuple[int, str, int], bool | None] = {}
        self.parse_failures: list[Path] = []
        self.project_roots: set[str] = set()
        self.capability: CapabilityIndex | None = capability
        self.capability_verify: dict[str, VerifyRecord] = {}
        self.capability_sigs: dict[str, tuple[Param, ...] | None] = {}
        self.capability_types: dict[str, str | None] = {}
        self.capability_objects: dict[str, bool] = {}
        self.target: TargetPython = target_python(root=root, python=python)
        self.stubs: StubIndex = StubIndex(
            roots=stub_roots(),
            target=self.target,
        )
        discovered: list[Path] = (
            list(source_paths)
            if source_paths is not None
            else python_files(root=root, path_filter=path_filter)
        )
        lanes: BoundedLaneProgress = BoundedLaneProgress(
            total=len(discovered),
            step="indexing",
            span=(0.0, 0.3),
        )
        with ThreadPoolExecutor() as pool:
            indexed: list[tuple[Path, Future[ModuleInfo | None]]] = [
                (
                    path,
                    pool.submit(
                        _index_module_lane,
                        path=path,
                        root=root,
                        progress=lanes,
                    ),
                )
                for path in discovered
            ]
            modules: list[tuple[Path, ModuleInfo | None]] = [
                (path, future.result()) for path, future in indexed
            ]
        path: Path
        module: ModuleInfo | None
        for path, module in modules:
            if module is None:
                self.parse_failures.append(path)
                continue
            self.by_path[path] = module
            name: str
            for name in module_names(path=path, root=root):
                _ = consume(value=self.modules.setdefault(name, module))
                self.project_roots |= {name.split(sep=".")[0]}
        module_info: ModuleInfo
        for module_info in self.by_path.values():
            classinfo: ClassInfo
            for classinfo in module_info.classes.values():
                self.register_class(info=classinfo)

    @staticmethod
    def external_via_prefix(*, parts: list[str], split: int) -> LiveObject:
        """Resolve a path through one importable module prefix.

        Args:
            parts: Dotted path segments.
            split: Index separating module prefix from attributes.

        Returns:
            The `LiveObject` result produced by the operation.

        """
        try:
            module: ModuleType = import_module(name=".".join(parts[:split]))
        except (
            AttributeError,
            ImportError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            return None
        target: object = module
        attribute: str
        for attribute in parts[split:]:
            if not hasattr(target, attribute):
                return None
            target = cast(typ="object", val=getattr(target, attribute))
        return target

    @staticmethod
    def local_instance(*, local: Resolved) -> Resolved:
        """Convert a module-level resolution to an instance resolution.

        Args:
            local: Symbol resolution for the annotated name.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        if local.kind == "class" and local.cls is not None:
            resolved = Resolved(kind="instance", cls=local.cls)
        elif local.kind == "external" and local.ext_kind == "class":
            resolved = Resolved(
                kind="external",
                obj=local.obj,
                ext_kind="instance",
                dotted=local.dotted,
            )
        elif local.kind == "stubclass":
            resolved = Resolved(
                kind="stubinstance",
                stub=local.stub,
                dotted=local.dotted,
            )
        elif local.kind == "instance":
            resolved = local
        return resolved

    @staticmethod
    def class_call(*, stored: Resolved, bound: bool) -> Resolved:
        """Resolve a class-body callable attribute for one access.

        Functions assigned in a class body bind the receiver on
        instance access, exactly like declared methods.

        Args:
            stored: Resolution recorded for the class attribute.
            bound: Whether the receiver is already supplied.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if (
            bound
            and not stored.bound
            and stored.kind == "function"
            and stored.sig is not None
            and stored.sig.method == "instance"
        ):
            return replace(stored, bound=True)
        return stored

    def register_class(self: Self, *, info: ClassInfo) -> None:
        """Register a class and its methods in the global indexes.

        Args:
            info: Class record to register.

        """
        short: str = info.name.split(sep=".")[-1]
        self.classes[short].append(info)
        method: str
        sig: Sig
        for method, sig in info.methods.items():
            self.methods[method].append((info, sig))
        nested: ClassInfo
        for nested in info.nested.values():
            self.register_class(info=nested)

    def class_named(self: Self, *, name: str) -> ClassInfo | None:
        """Resolve a class by qualified or short name.

        Args:
            name: Class name as written.

        Returns:
            The `ClassInfo | None` result produced by the operation.

        """
        if name in self.class_name_cache:
            return self.class_name_cache[name]
        short: str = name.rsplit(sep=".", maxsplit=1)[-1]
        candidates: list[ClassInfo] = self.classes.get(short, [])
        resolved: ClassInfo | None = None
        candidate: ClassInfo
        for candidate in candidates:
            if name.endswith(candidate.name) or candidate.name.endswith(name):
                resolved = candidate
                break
        if resolved is None and candidates:
            resolved = candidates[0]
        self.class_name_cache[name] = resolved
        return resolved

    def find_method(
        self: Self,
        *,
        info: ClassInfo,
        name: str,
        depth: int = 0,
    ) -> Sig | None:
        """Find a method on a class, walking project base classes.

        Args:
            info: Class to search.
            name: Method name.
            depth: Recursion guard for base-class cycles.

        Returns:
            The `Sig | None` result produced by the operation.

        """
        if depth > Constants.max_depth:
            return None
        key: tuple[int, str] = (id(info), name)
        if key in self.method_cache:
            return self.method_cache[key]
        found: Sig | None = info.methods.get(name)
        if found is None:
            base: str
            for base in info.bases:
                parent: ClassInfo | None = self.class_named(name=base)
                if parent is None or parent is info:
                    continue
                found = self.find_method(
                    info=parent,
                    name=name,
                    depth=depth + 1,
                )
                if found is not None:
                    break
        self.method_cache[key] = found
        return found

    def external_object(self: Self, *, dotted: str) -> LiveObject:
        """Resolve a dotted path to a live external object.

        Args:
            dotted: Dotted attribute path.

        Returns:
            The `LiveObject` result produced by the operation.

        """
        if dotted in self.externals:
            return self.externals[dotted]
        if self.capability is not None and dotted in self.capability.absent:
            self.externals[dotted] = None
            self.capability_objects[dotted] = False
            return None
        parts: list[str] = dotted.split(sep=".", maxsplit=-1)
        if len(parts) == 1:
            found: LiveObject = self.external_single(name=parts[0])
        else:
            found = self.external_dotted(parts=parts)
        self.externals[dotted] = found
        self.capability_objects[dotted] = found is not None
        return found

    def external_single(self: Self, *, name: str) -> LiveObject:
        """Resolve a bare name to a builtin or top-level module.

        Args:
            name: Single-segment name.

        Returns:
            The `LiveObject` result produced by the operation.

        """
        builtins_module: ModuleType = import_module(name="builtins")
        found: LiveObject = getattr(builtins_module, name, None)
        if found is None and name not in self.project_roots:
            try:
                found = import_module(name=name)
            except (ImportError, OSError, RuntimeError, TypeError, ValueError):
                found = None
        return found

    def external_dotted(self: Self, *, parts: list[str]) -> LiveObject:
        """Resolve a multi-segment path through importable prefixes.

        Args:
            parts: Dotted path segments.

        Returns:
            The `LiveObject` result produced by the operation.

        """
        found: LiveObject = None
        split: int
        for split in range(len(parts), 0, -1):
            prefix: str = ".".join(parts[:split])
            if prefix.split(sep=".", maxsplit=1)[0] in self.project_roots:
                continue
            found = self.external_via_prefix(parts=parts, split=split)
            if found is not None:
                break
        return found

    def external_type(self: Self, *, name: str) -> tuple[type, str] | None:
        """Resolve an annotation type name to a live runtime class.

        The direct dotted name is preferred. Common annotation namespaces are
        then searched so postponed annotations imported only under
        ``TYPE_CHECKING`` remain useful for static receiver inference.

        Args:
            name: Bare or dotted annotation type name.

        Returns:
            Runtime class and resolved dotted path, or ``None``.

        """
        if self.capability is not None and name in self.capability.types:
            canonical: str | None = self.capability.types[name]
            if canonical is None:
                return None
            canonical_obj: LiveObject = self.external_object(dotted=canonical)
            if isinstance(canonical_obj, type):
                return canonical_obj, canonical
            return None
        normalized: str = {
            "Mapping": "dict",
            "MutableMapping": "dict",
            "collections.abc.Mapping": "dict",
            "collections.abc.MutableMapping": "dict",
            "typing.Mapping": "dict",
            "typing.MutableMapping": "dict",
        }.get(name, name)
        candidates: tuple[str, ...] = (
            normalized,
            f"builtins.{normalized}",
            f"argparse.{normalized}",
            f"ast.{normalized}",
            f"collections.abc.{normalized}",
            f"io.{normalized}",
            f"pathlib.{normalized}",
            f"re.{normalized}",
        )
        dotted: str
        for dotted in candidates:
            found: LiveObject = self.external_object(dotted=dotted)
            if isinstance(found, type):
                self.capability_types[name] = dotted
                return found, dotted
        self.capability_types[name] = None
        return None

    def external_sig(self: Self, *, dotted: str) -> Sig | None:
        """Return the runtime signature for an external callable.

        Args:
            dotted: Dotted callable path.

        Returns:
            The `Sig | None` result produced by the operation.

        """
        if dotted in self.external_sigs:
            return self.external_sigs[dotted]
        if self.capability is not None and dotted in self.capability.sigs:
            stored: tuple[Param, ...] | None = self.capability.sigs[dotted]
            indexed: Sig | None = (
                Sig(name=dotted, params=stored) if stored is not None else None
            )
            self.external_sigs[dotted] = indexed
            return indexed
        resolved: Sig | None = None
        found: object = self.external_object(dotted=dotted)
        if found is not None and callable(found):
            try:
                resolved = sig_from_inspect(
                    name=dotted,
                    resolved=signature(obj=found),
                )
            except (TypeError, ValueError):
                resolved = None
        self.external_sigs[dotted] = resolved
        self.capability_sigs[dotted] = (
            resolved.params if resolved is not None else None
        )
        return resolved

    def probe(
        self: Self,
        *,
        obj: LiveObject,
        params: tuple[Param, ...],
        index: int,
    ) -> bool | None:
        """Return a cached runtime keyword-acceptance probe verdict.

        Args:
            obj: Live callable under test.
            params: Call-ready parameter tuple the probe is drawn from.
            index: Index of the parameter passed by keyword.

        Returns:
            The `bool | None` result produced by the operation.

        """
        key: tuple[int, str, int] = (id(obj), params[index].name, index)
        if key not in self.probes:
            self.probes[key] = probe_call(obj=obj, params=params, index=index)
        return self.probes[key]

    def verify_params(
        self: Self,
        *,
        obj: LiveObject,
        params: tuple[Param, ...],
    ) -> tuple[tuple[Param, ...], bool]:
        """Demote stub parameters the runtime rejects as keywords.

        Typeshed can mark a parameter keyword-capable that the C
        runtime treats as positional-only; probing the live callable
        with sentinel arguments detects real keyword acceptance.

        Args:
            obj: Live callable resolved for the stub signature.
            params: Call-ready parameter tuple, receiver dropped.

        Returns:
            The corrected parameter tuple plus whether every
            keyword-capable parameter received a conclusive verdict.

        """
        has_varkw: bool = False
        param: Param
        for param in params:
            if param.kind == "varkw":
                has_varkw = True
                break
        if has_varkw:
            return params, False
        checked: list[Param] = []
        conclusive: bool = True
        index: int
        for index, param in enumerate(iterable=params):
            if param.kind != "poskw":
                checked.append(param)
                continue
            verdict: bool | None = self.probe(
                obj=obj,
                params=params,
                index=index,
            )
            conclusive = conclusive and verdict is not None
            if verdict is False:
                checked.append(
                    Param(
                        name=param.name,
                        kind="posonly",
                        has_default=param.has_default,
                    ),
                )
            else:
                checked.append(param)
        return tuple(checked), conclusive

    def write_capability_index(self: Self, *, path: Path) -> None:
        """Commit the captured runtime capability snapshot to JSON.

        Args:
            path: Destination ``CAPABILITY_INDEX.json`` path.

        """
        CapabilityIndex(
            verify=dict(self.capability_verify),
            sigs=dict(self.capability_sigs),
            types=dict(self.capability_types),
            absent=frozenset(
                dotted
                for dotted, present in self.capability_objects.items()
                if not present
            ),
            python_version=version,
            executable=executable,
        ).dump(path=path)

    def resolve_dotted(self: Self, *, dotted: str, depth: int = 0) -> Resolved:
        """Resolve a dotted path through the project index or imports.

        Args:
            dotted: Dotted symbol path.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if depth > Constants.max_depth:
            return Resolved()
        parts: list[str] = dotted.split(sep=".")
        split: int
        for split in range(len(parts), 0, -1):
            prefix: str = ".".join(parts[:split])
            if prefix in self.modules:
                module: ModuleInfo = self.modules[prefix]
                return self.resolve_in_module(
                    module=module,
                    rest=parts[split:],
                    depth=depth,
                )
        return Resolved()

    def resolve_in_module(
        self: Self,
        *,
        module: ModuleInfo,
        rest: list[str],
        depth: int = 0,
    ) -> Resolved:
        """Resolve a name inside an indexed module.

        Args:
            module: Module to search.
            rest: Remaining attribute path segments.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if depth > Constants.max_depth:
            return Resolved()
        if not rest:
            return Resolved(kind="module", module=module)
        name: str = rest[0]
        resolved: Resolved | None = self.module_symbol(
            module=module,
            name=name,
            rest=rest,
            depth=depth,
        )
        if resolved is None:
            resolved = self.module_submodule(
                module=module,
                name=name,
                rest=rest,
                depth=depth,
            )
        return resolved if resolved is not None else Resolved()

    def module_symbol(
        self: Self,
        *,
        module: ModuleInfo,
        name: str,
        rest: list[str],
        depth: int,
    ) -> Resolved | None:
        """Resolve `name` against a module's defined symbols.

        Args:
            module: Module to search.
            name: First attribute path segment.
            rest: Full attribute path.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        resolved: Resolved | None = None
        if name in module.functions:
            resolved = (
                Resolved(kind="function", sig=module.functions[name])
                if len(rest) == 1
                else Resolved()
            )
        elif name in module.classes:
            info: ClassInfo = module.classes[name]
            resolved = (
                Resolved(kind="class", cls=info)
                if len(rest) == 1
                else self.resolve_in_class(info=info, rest=rest[1:])
            )
        elif name in module.aliases:
            resolved = self.follow_alias(
                target=module.aliases[name],
                rest=rest,
                depth=depth,
            )
        elif name in module.module_aliases:
            resolved = self.follow_alias(
                target=module.module_aliases[name],
                rest=rest,
                depth=depth,
            )
        elif name in module.var_calls and len(rest) == 1:
            resolved = module.var_calls[name]
        elif name in module.call_exprs:
            resolved = self.module_call_expr(
                module=module,
                name=name,
                rest=rest,
                depth=depth,
            )
        elif name in module.var_types:
            resolved = self.module_instance(
                module=module,
                name=name,
                rest=rest,
            )
        return resolved

    def follow_alias(
        self: Self,
        *,
        target: str,
        rest: list[str],
        depth: int,
    ) -> Resolved:
        """Follow an import alias to a project or external target.

        Args:
            target: Dotted alias target.
            rest: Full attribute path.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved` result produced by the operation.

        """
        suffix: str = ".".join(rest[1:])
        combined: str = f"{target}.{suffix}" if suffix else target
        resolved: Resolved = self.resolve_dotted(
            dotted=combined,
            depth=depth + 1,
        )
        if resolved.kind == "unknown":
            resolved = self.resolve_external(dotted=combined)
        return resolved

    def module_call_expr(
        self: Self,
        *,
        module: ModuleInfo,
        name: str,
        rest: list[str],
        depth: int,
    ) -> Resolved:
        """Resolve a module-level `name = a.b` callable reference.

        Args:
            module: Module to search.
            name: Assigned variable name.
            rest: Full attribute path.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = self.resolve_in_module(
            module=module,
            rest=module.call_exprs[name].split(sep="."),
            depth=depth + 1,
        )
        if resolved.kind == "unknown":
            resolved = self.resolve_external(dotted=module.call_exprs[name])
        module.var_calls[name] = resolved
        if len(rest) == 1:
            return resolved
        return Resolved()

    def module_instance(
        self: Self,
        *,
        module: ModuleInfo,
        name: str,
        rest: list[str],
    ) -> Resolved:
        """Resolve a module-level variable holding a class instance.

        Args:
            module: Module to search.
            name: Variable name.
            rest: Full attribute path.

        Returns:
            The `Resolved` result produced by the operation.

        """
        base: Resolved = self.declared_instance(
            module=module,
            name=module.var_types[name],
        )
        return self.instance_rest(base=base, rest=rest)

    def declared_instance(
        self: Self,
        *,
        module: ModuleInfo | None,
        name: str,
    ) -> Resolved:
        """Resolve an annotation type name in its declaring module's scope.

        Module-level symbols and import aliases are consulted before the
        global class index, so same-named classes in other modules cannot
        shadow the annotation's actual target. An imported name that fails
        to resolve still yields an ``external`` placeholder, keeping
        receivers of that type out of name-guessing fallbacks.

        Args:
            module: Module the annotation was written in, if indexed.
            name: Type name as written.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        if module is not None:
            resolved = self.local_instance(
                local=self.resolve_in_module(
                    module=module,
                    rest=name.split(sep="."),
                ),
            )
            if resolved.kind != "unknown":
                return resolved
            head: str
            tail: str
            head, _, tail = name.partition(".")
            imported: str | None = module.aliases.get(
                head,
                module.module_aliases.get(head),
            )
            if imported is not None:
                return Resolved(
                    kind="external",
                    ext_kind="instance",
                    dotted=f"{imported}.{tail}" if tail else imported,
                )
        attr_cls: ClassInfo | None = self.class_named(name=name)
        if attr_cls is not None:
            return Resolved(kind="instance", cls=attr_cls)
        external: tuple[type, str] | None = self.external_type(name=name)
        if external is not None:
            external_cls: type
            resolved_dotted: str
            external_cls, resolved_dotted = external
            return Resolved(
                kind="external",
                obj=external_cls,
                ext_kind="instance",
                dotted=resolved_dotted,
            )
        stubbed: Resolved = self.stubs.lookup(dotted=name)
        if stubbed.kind == "stubclass":
            return Resolved(
                kind="stubinstance",
                stub=stubbed.stub,
                dotted=name,
            )
        return resolved

    def instance_rest(
        self: Self,
        *,
        base: Resolved,
        rest: list[str],
    ) -> Resolved:
        """Resolve remaining attribute segments on an instance.

        Args:
            base: Instance-level resolution of the first segment's type.
            rest: Full attribute path including the first segment.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        if len(rest) == 1:
            return base
        if base.kind == "instance" and base.cls is not None:
            return self.resolve_in_class(
                info=base.cls,
                rest=rest[1:],
                bound=True,
            )
        if base.kind == "external" and base.obj is not None:
            resolved = base
            part: str
            for part in rest[1:]:
                member: LiveObject = getattr(resolved.obj, part, None)
                if member is None:
                    return Resolved()
                resolved = Resolved(
                    kind="external",
                    obj=member,
                    ext_kind="instance",
                    dotted=f"{resolved.dotted}.{part}",
                )
        return resolved

    def module_submodule(
        self: Self,
        *,
        module: ModuleInfo,
        name: str,
        rest: list[str],
        depth: int,
    ) -> Resolved | None:
        """Resolve `name` as a submodule of `module`.

        Args:
            module: Module to search.
            name: First attribute path segment.
            rest: Full attribute path.
            depth: Recursion guard for cyclic import aliases.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        submodule: str = f"{module.name}.{name}"
        if submodule not in self.modules:
            return None
        child: ModuleInfo = self.modules[submodule]
        if len(rest) == 1:
            return Resolved(kind="module", module=child)
        return self.resolve_in_module(
            module=child,
            rest=rest[1:],
            depth=depth + 1,
        )

    def resolve_in_class(
        self: Self,
        *,
        info: ClassInfo,
        rest: list[str],
        bound: bool = False,
    ) -> Resolved:
        """Resolve an attribute path inside a class record.

        Args:
            info: Class to search.
            rest: Remaining attribute path segments.
            bound: Whether the receiver is already bound.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if not rest:
            return Resolved(kind="class", cls=info)
        resolved: Resolved | None = self.class_member(
            info=info,
            name=rest[0],
            rest=rest,
            bound=bound,
        )
        return resolved if resolved is not None else Resolved()

    def class_member(
        self: Self,
        *,
        info: ClassInfo,
        name: str,
        rest: list[str],
        bound: bool,
    ) -> Resolved | None:
        """Resolve `name` against a class's members.

        Args:
            info: Class to search.
            name: First attribute path segment.
            rest: Full attribute path.
            bound: Whether the receiver is already bound.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        resolved: Resolved | None = None
        found: Sig | None = self.find_method(info=info, name=name)
        if name in info.nested:
            child: ClassInfo = info.nested[name]
            resolved = (
                Resolved(kind="class", cls=child)
                if len(rest) == 1
                else self.resolve_in_class(info=child, rest=rest[1:])
            )
        elif found is not None and len(rest) == 1:
            resolved = Resolved(
                kind="function",
                sig=found,
                bound=bound or found.method == "class",
            )
        elif name in info.attr_calls and len(rest) == 1:
            resolved = info.attr_calls[name]
        elif name in info.class_calls and len(rest) == 1:
            resolved = self.class_call(
                stored=info.class_calls[name],
                bound=bound,
            )
        elif name in info.attr_types:
            resolved = self.class_attr(info=info, name=name, rest=rest)
        return resolved

    def class_attr(
        self: Self,
        *,
        info: ClassInfo,
        name: str,
        rest: list[str],
    ) -> Resolved:
        """Resolve a class attribute holding a typed instance.

        Args:
            info: Class to search.
            name: Attribute name.
            rest: Full attribute path.

        Returns:
            The `Resolved` result produced by the operation.

        """
        type_name: str = info.attr_types[name]
        owner: ModuleInfo | None = self.modules.get(info.module)
        base: Resolved = self.declared_instance(module=owner, name=type_name)
        return self.instance_rest(base=base, rest=rest)

    def resolve_external(self: Self, *, dotted: str) -> Resolved:
        """Resolve a dotted path to a live external object.

        Args:
            dotted: Dotted symbol path.

        Returns:
            The `Resolved` result produced by the operation.

        """
        if dotted in self.external_resolutions:
            return self.external_resolutions[dotted]
        found: object = self.external_object(dotted=dotted)
        if found is None:
            resolved: Resolved = self.stubs.lookup(dotted=dotted)
        else:
            kind: ExternalKind
            if isinstance(found, ModuleType):
                kind = "module"
            elif isinstance(found, type):
                kind = "class"
            else:
                kind = "instance"
            resolved = Resolved(
                kind="external",
                obj=found,
                ext_kind=kind,
                dotted=dotted,
            )
        self.external_resolutions[dotted] = resolved
        return resolved


class PositionalCheckArgs(TypedDict):
    """Represent positional check args.

    Attributes:
        node: Node.
        index: Index.
        argument: Argument.
        compatible: Compatible.
        keyword_names: Keyword names.
        callee_text: Callee text.
        confidence: Confidence.
        positional_count: Positional count.

    """

    node: Call
    index: int
    argument: expr
    compatible: list[tuple[Param, ...]]
    keyword_names: set[str]
    callee_text: str
    confidence: str
    positional_count: int


class CallExactusor:
    """Walk one module's AST resolving every call site."""

    def __init__(self: Self, *, project: Project, module: ModuleInfo) -> None:
        """Initialize the exactusor for one module.

        Args:
            project: Repository index.
            module: Module being exactused.

        """
        self.project: Project = project
        self.module: ModuleInfo = module
        self.findings: list[Finding] = []
        self.ambiguous: list[AmbiguousCall] = []
        self.unresolved: dict[str, int] = defaultdict(int)
        self.unresolved_calls: list[UnresolvedCall] = []
        self.calls: int = 0
        self.resolved_calls: int = 0
        self.exempt_calls: int = 0

    @staticmethod
    def unresolved_reason(*, node: Call) -> str:
        """Classify why a call's callee has no known signature.

        Args:
            node: Unresolved call node.

        Returns:
            ``unknown-name`` (a plain name without a definition),
            ``unknown-receiver`` (an attribute of an object of unknown
            type), ``call-result`` (the result of another call),
            ``subscript-lookup`` (an item lookup), or
            ``dynamic-expression`` (any other expression).

        """
        callee: expr = node.func
        if isinstance(callee, Name):
            return "unknown-name"
        if isinstance(callee, Attribute):
            return "unknown-receiver"
        if isinstance(callee, Call):
            return "call-result"
        if isinstance(callee, Subscript):
            return "subscript-lookup"
        return "dynamic-expression"

    @staticmethod
    def is_exempt(*, callee_text: str, node: Call) -> bool:
        """Return whether an unresolved call cannot take keyword arguments.

        Dynamic ``pytest.mark.*`` factories, methods that are positional-only
        in the standard library, and ``lowerCamelCase`` foreign-binding
        methods are not actionable, so they are counted apart instead of
        being listed as unresolved.

        Args:
            callee_text: Source text of the callee.
            node: Call node.

        Returns:
            Whether the call is exempt from the unresolved listing.

        """
        if callee_text.startswith(Constants.dynamic_callee_prefixes):
            return True
        if not isinstance(node.func, Attribute):
            return False
        attribute: str = node.func.attr
        return (
            attribute in Constants.positional_only_methods
            or search(
                pattern=Constants.foreign_binding_pattern,
                string=attribute,
            )
            is not None
        )

    @staticmethod
    def branch_scope(*, scope: Scope) -> Scope:
        """Clone flow-sensitive bindings for one control-flow branch.

        Args:
            scope: Scope state immediately before the branch.

        Returns:
            Independent branch scope with the same lexical parent.

        """
        branch: Scope = Scope(
            parent=scope.parent,
            classinfo=scope.classinfo,
            class_body=scope.class_body,
        )
        branch.defs = dict(scope.defs)
        branch.classes = dict(scope.classes)
        branch.var_types = dict(scope.var_types)
        branch.var_calls = dict(scope.var_calls)
        branch.var_elems = dict(scope.var_elems)
        branch.aliases = dict(scope.aliases)
        branch.module_aliases = dict(scope.module_aliases)
        return branch

    @staticmethod
    def merge_branch_maps[T](
        *,
        target: dict[str, T],
        left: dict[str, T],
        right: dict[str, T],
    ) -> None:
        """Keep only bindings proven identical after both branches.

        Args:
            target: Mapping receiving the merged state.
            left: State after the true branch.
            right: State after the false branch.

        """
        target.clear()
        target.update(
            {
                key: value
                for key, value in left.items()
                if key in right and right[key] == value
            },
        )

    @staticmethod
    def record_import(*, node: Import, scope: Scope) -> None:
        """Record a function-local `import x` statement.

        Args:
            node: Import statement.
            scope: Active lexical scope.

        """
        entry: alias
        for entry in node.names:
            if entry.asname is not None:
                scope.module_aliases[entry.asname] = entry.name
            else:
                top: str = entry.name.split(sep=".")[0]
                _ = consume(value=scope.module_aliases.setdefault(top, top))

    @staticmethod
    def seed_parameters(*, args: arguments, scope: Scope) -> None:
        """Bind parameter annotations in a fresh child scope.

        Args:
            args: Function parameter declarations.
            scope: Scope receiving the bindings.

        """
        parameter: arg
        for parameter in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            named: str | None = annotation_name(node=parameter.annotation)
            if named is not None:
                scope.var_types[parameter.arg] = named
                element: str | None = annotation_element(
                    node=parameter.annotation,
                )
                if element is not None:
                    scope.var_elems[parameter.arg] = element
            elif parameter.arg in Constants.fixture_hints:
                scope.var_types[parameter.arg] = Constants.fixture_hints[
                    parameter.arg
                ]
        if args.vararg is not None:
            scope.var_types[args.vararg.arg] = "tuple"
        if args.kwarg is not None:
            scope.var_types[args.kwarg.arg] = "dict"

    @staticmethod
    def iter_element(*, node: expr, scope: Scope) -> str | None:
        """Return the recorded element type of an iterable expression.

        Args:
            node: Iterable expression.
            scope: Active lexical scope.

        Returns:
            The `str | None` result produced by the operation.

        """
        element: str | None = None
        if isinstance(node, Name):
            element = scope.lookup_elem(name=node.id)
        elif (
            isinstance(node, Attribute)
            and isinstance(node.value, Name)
            and node.value.id in Constants.receiver_names
        ):
            info: ClassInfo | None = scope.enclosing_class()
            if info is not None:
                element = info.attr_elems.get(node.attr)
        return element

    @staticmethod
    def record_self_attr(
        *,
        target: Attribute,
        name: str,
        scope: Scope,
        element: str | None = None,
    ) -> None:
        """Record `self.attr` types on the enclosing class record.

        Args:
            target: Assignment target attribute.
            name: Bound class name.
            scope: Active lexical scope.
            element: Iterated element type for container annotations.

        """
        if not isinstance(target.value, Name) or target.value.id != "self":
            return
        info: ClassInfo | None = scope.enclosing_class()
        if info is not None:
            info.attr_types[target.attr] = name
            if element is not None:
                info.attr_elems[target.attr] = element

    @staticmethod
    def bind_callable_name(
        *,
        name: str,
        resolved: Resolved,
        scope: Scope,
    ) -> None:
        """Bind or clear a callable resolution for a plain name.

        Args:
            name: Assigned variable name.
            resolved: Callable resolution, or unknown to clear.
            scope: Active lexical scope.

        """
        if resolved.kind == "unknown":
            _ = consume(value=scope.var_calls.pop(name, None))
            return
        scope.var_calls[name] = resolved
        _ = consume(value=scope.var_types.pop(name, None))
        if scope.class_body and scope.classinfo is not None:
            scope.classinfo.class_calls[name] = resolved

    @staticmethod
    def bind_callable_attr(
        *,
        target: expr,
        resolved: Resolved,
        scope: Scope,
    ) -> None:
        """Bind or clear a callable resolution for `self.attr`.

        Args:
            target: Assignment target attribute.
            resolved: Callable resolution, or unknown to clear.
            scope: Active lexical scope.

        """
        if not isinstance(target, Attribute):
            return
        if not isinstance(target.value, Name) or target.value.id != "self":
            return
        info: ClassInfo | None = scope.enclosing_class()
        if info is None:
            return
        if resolved.kind == "unknown":
            _ = consume(value=info.attr_calls.pop(target.attr, None))
            return
        info.attr_calls[target.attr] = resolved

    @staticmethod
    def name_def(*, name: str, scope: Scope) -> Resolved | None:
        """Resolve `name` as a locally defined callable.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        found: Sig | None = scope.lookup_def(name=name)
        if found is None:
            return None
        return Resolved(kind="function", sig=found)

    @staticmethod
    def name_class(*, name: str, scope: Scope) -> Resolved | None:
        """Resolve `name` as a locally defined class.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        info: ClassInfo | None = scope.lookup_class(name=name)
        if info is None:
            return None
        return Resolved(kind="class", cls=info)

    @staticmethod
    def name_var_call(*, name: str, scope: Scope) -> Resolved | None:
        """Resolve `name` as a variable bound to a callable reference.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        return scope.lookup_call(name=name)

    @staticmethod
    def ready_params(sig: Sig, *, bound: bool) -> tuple[Param, ...]:
        """Return call-ready parameters with the receiver dropped.

        Args:
            sig: Signature to adjust.
            bound: Whether the receiver is already supplied.

        Returns:
            The `tuple[Param, ...]` result produced by the operation.

        """
        params: tuple[Param, ...] = sig.params
        if bound and params and sig.method in {"instance", "class"}:
            return params[1:]
        return params

    @staticmethod
    def posonly_names(
        *,
        resolved: Resolved,
        obj: LiveObject,
    ) -> frozenset[str]:
        """Return runtime-verified positional-only parameter names.

        Some C callables advertise keyword-capable parameters in
        typeshed while rejecting them at runtime; the override table
        demotes those names without executing the callable.

        Args:
            resolved: Resolved callee carrying a live object or path.
            obj: Live callable resolved for the stub signature.

        Returns:
            Parameter names the runtime treats as positional-only.

        """
        names: frozenset[str] = Constants.posonly_params.get(
            resolved.dotted,
            frozenset(),
        )
        if names or obj is None:
            return names
        obj_module: LiveObject = getattr(obj, "__module__", "")
        obj_name: LiveObject = getattr(
            obj,
            "__qualname__",
            getattr(obj, "__name__", ""),
        )
        return Constants.posonly_params.get(
            f"{obj_module}.{obj_name}",
            frozenset(),
        )

    def record_unresolved(self: Self, *, callee_text: str, node: Call) -> None:
        """Count an unresolved call, apart when it is not actionable.

        Args:
            callee_text: Source text of the callee.
            node: Call node.

        """
        if self.is_exempt(callee_text=callee_text, node=node):
            self.exempt_calls += 1
        else:
            self.unresolved[callee_text] += 1
            self.unresolved_calls.append(
                UnresolvedCall(
                    path=self.module.path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    callee=callee_text,
                    reason=self.unresolved_reason(node=node),
                ),
            )

    def exactus(self: Self) -> None:
        """Parse and walk the module, collecting findings."""
        tree: Module | None = self.module.tree
        if tree is None:
            try:
                tree = parse(
                    source=self.module.path.read_text(encoding="utf-8"),
                    filename=str(object=self.module.path),
                )
            except (OSError, SyntaxError, ValueError):
                return
        scope: Scope = Scope(parent=None, classinfo=None)
        scope.defs.update(self.module.functions)
        scope.classes.update(self.module.classes)
        self.walk_body(stmts=tree.body, scope=scope)

    def walk_body(self: Self, *, stmts: list[stmt], scope: Scope) -> None:
        """Walk a statement list in order.

        Args:
            stmts: Statements to visit.
            scope: Active lexical scope.

        """
        item: stmt
        for item in stmts:
            self.walk_node(node=item, scope=scope)

    def seed_scope(self: Self, *, stmts: list[stmt], scope: Scope) -> None:
        """Pre-register only lexically available sibling definitions.

        Runtime value bindings are intentionally not seeded. Assignments
        must become visible only after their statement executes so callee
        resolution reflects the exact AST position of each call.

        Args:
            stmts: Statements to scan.
            scope: Scope to populate.

        """
        item: stmt
        for item in stmts:
            if isinstance(item, FunctionDef | AsyncFunctionDef):
                scope.defs[item.name] = build_sig(
                    node=item,
                    name=item.name,
                    method="function",
                )
            elif isinstance(item, ClassDef):
                scope.classes[item.name] = build_classinfo(
                    node=item,
                    module=self.module.name,
                    path=self.module.path,
                    prefix="",
                )

    def walk_if(self: Self, *, node: If, scope: Scope) -> None:
        """Walk an ``if`` using independent flow-sensitive branch states.

        Args:
            node: Conditional statement.
            scope: State immediately before the conditional.

        """
        self.walk_node(node=node.test, scope=scope)
        left: Scope = self.branch_scope(scope=scope)
        right: Scope = self.branch_scope(scope=scope)
        self.walk_body(stmts=node.body, scope=left)
        self.walk_body(stmts=node.orelse, scope=right)
        self.merge_branch_maps(
            target=scope.var_types,
            left=left.var_types,
            right=right.var_types,
        )
        self.merge_branch_maps(
            target=scope.var_calls,
            left=left.var_calls,
            right=right.var_calls,
        )
        self.merge_branch_maps(
            target=scope.var_elems,
            left=left.var_elems,
            right=right.var_elems,
        )
        self.merge_branch_maps(
            target=scope.aliases,
            left=left.aliases,
            right=right.aliases,
        )
        self.merge_branch_maps(
            target=scope.module_aliases,
            left=left.module_aliases,
            right=right.module_aliases,
        )

    def walk_node(self: Self, *, node: AST, scope: Scope) -> None:
        """Dispatch one node, tracking scope transitions.

        Args:
            node: Node to visit.
            scope: Active lexical scope.

        """
        if isinstance(node, FunctionDef | AsyncFunctionDef):
            self.enter_function(node=node, scope=scope)
            return
        if isinstance(node, ClassDef):
            self.enter_class(node=node, scope=scope)
            return
        if isinstance(node, Lambda):
            self.enter_lambda(node=node, scope=scope)
            return
        if isinstance(node, If):
            self.walk_if(node=node, scope=scope)
            return
        if isinstance(node, Call):
            self.check_call(node=node, scope=scope)
        self.record_binding(node=node, scope=scope)
        child: AST
        for child in iter_child_nodes(node=node):
            self.walk_node(node=child, scope=scope)

    def record_binding(self: Self, *, node: AST, scope: Scope) -> None:
        """Record names a statement binds before its children are walked.

        Args:
            node: Node being visited.
            scope: Active lexical scope.

        """
        if isinstance(node, Assign | AnnAssign):
            self.record_assignment(node=node, scope=scope)
        elif isinstance(node, For | AsyncFor):
            self.record_for(node=node, scope=scope)
        elif isinstance(node, With | AsyncWith):
            self.record_with(node=node, scope=scope)
        elif isinstance(node, Import):
            self.record_import(node=node, scope=scope)
        elif isinstance(node, ImportFrom):
            self.record_import_from(node=node, scope=scope)

    def record_import_from(
        self: Self,
        *,
        node: ImportFrom,
        scope: Scope,
    ) -> None:
        """Record a function-local `from x import y` statement.

        Args:
            node: Import-from statement.
            scope: Active lexical scope.

        """
        base: str = relative_module(
            module=self.module,
            level=node.level,
            body=node.module or "",
        )
        entry: alias
        for entry in node.names:
            if entry.name == "*":
                continue
            bound: str = entry.asname or entry.name
            dotted: str = f"{base}.{entry.name}" if base else entry.name
            scope.aliases[bound] = dotted

    def enter_function(
        self: Self,
        *,
        node: FunctionDef | AsyncFunctionDef,
        scope: Scope,
    ) -> None:
        """Walk a function body inside a fresh child scope.

        Args:
            node: Function definition.
            scope: Enclosing scope.

        """
        child_scope: Scope = Scope(parent=scope, classinfo=scope.classinfo)
        self.seed_parameters(args=node.args, scope=child_scope)
        self.seed_scope(stmts=node.body, scope=child_scope)
        decorator: expr
        for decorator in node.decorator_list:
            self.walk_node(node=decorator, scope=scope)
        default: expr | None
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.walk_node(node=default, scope=scope)
        if node.returns is not None:
            self.walk_node(node=node.returns, scope=scope)
        self.walk_body(stmts=node.body, scope=child_scope)

    def enter_class(self: Self, *, node: ClassDef, scope: Scope) -> None:
        """Walk a class body with the class record as context.

        Args:
            node: Class definition.
            scope: Enclosing scope.

        """
        info: ClassInfo | None = scope.lookup_class(name=node.name)
        if info is None:
            info = build_classinfo(
                node=node,
                module=self.module.name,
                path=self.module.path,
                prefix="",
            )
        decorator: expr
        for decorator in node.decorator_list:
            self.walk_node(node=decorator, scope=scope)
        base: expr
        for base in node.bases:
            self.walk_node(node=base, scope=scope)
        child_scope: Scope = Scope(
            parent=scope,
            classinfo=info,
            class_body=True,
        )
        self.seed_scope(stmts=node.body, scope=child_scope)
        self.walk_body(stmts=node.body, scope=child_scope)

    def enter_lambda(self: Self, *, node: Lambda, scope: Scope) -> None:
        """Walk a lambda body inside a fresh child scope.

        Args:
            node: Lambda expression.
            scope: Enclosing scope.

        """
        child_scope: Scope = Scope(parent=scope, classinfo=None)
        parameter: arg
        for parameter in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            named: str | None = annotation_name(node=parameter.annotation)
            if named is not None:
                child_scope.var_types[parameter.arg] = named
        self.walk_node(node=node.body, scope=child_scope)

    def resolved_assignment(
        self: Self,
        *,
        target: expr,
        resolved: Resolved,
        scope: Scope,
    ) -> bool:
        """Record an assignment from an inferred resolved value.

        Args:
            target: Assignment target.
            resolved: Inferred value resolution.
            scope: Active lexical scope.

        Returns:
            Whether the resolved value established the target type.

        """
        if resolved.kind == "instance" and resolved.cls is not None:
            self.record_target(
                target=target,
                name=resolved.cls.name,
                scope=scope,
            )
            return True
        if resolved.kind == "external" and resolved.ext_kind == "instance":
            self.record_target(
                target=target,
                name=resolved.dotted or type(resolved.obj).__name__,
                scope=scope,
            )
            return True
        if resolved.kind == "stubinstance" and resolved.dotted:
            self.record_target(
                target=target,
                name=resolved.dotted,
                scope=scope,
            )
            return True
        return False

    def record_assignment(
        self: Self,
        *,
        node: Assign | AnnAssign,
        scope: Scope,
    ) -> None:
        """Record the value type visible after an assignment executes.

        Explicit annotations take precedence over initializer syntax. For
        unannotated assignments, the assigned expression is resolved in the
        current lexical context so method calls are not mistaken for class
        names merely because they are call expressions.

        Args:
            node: Assignment statement.
            scope: Active lexical scope.

        """
        if isinstance(node, Assign):
            if len(node.targets) != 1:
                return
            target: expr = node.targets[0]
            value: expr | None = node.value
            annotation: expr | None = None
        else:
            target = node.target
            value = node.value
            annotation = node.annotation
        if (
            annotation is not None
            and (named := annotation_name(node=annotation)) is not None
        ):
            self.record_target(
                target=target,
                name=named,
                scope=scope,
                element=annotation_element(node=annotation),
            )
            return
        if isinstance(value, Lambda) and isinstance(target, Name):
            scope.defs[target.id] = build_sig(
                node=value,
                name=target.id,
                method="function",
            )
            return
        if value is None:
            return
        resolved: Resolved = self.infer_expr(node=value, scope=scope)
        if self.resolved_assignment(
            target=target,
            resolved=resolved,
            scope=scope,
        ):
            return
        if isinstance(value, Name | Attribute):
            self.record_callable(target=target, value=value, scope=scope)
            return
        literal_name: str | None = value_type_name(node=value)
        if literal_name is not None and not isinstance(value, Call):
            self.record_target(target=target, name=literal_name, scope=scope)

    def record_with(
        self: Self,
        *,
        node: With | AsyncWith,
        scope: Scope,
    ) -> None:
        """Type ``with open(...) as name`` targets as file objects.

        File-opening calls (``open``, ``Path.open``, ``os.fdopen``,
        ``os.popen``) return objects whose ``__enter__`` returns themselves,
        so the target gets the call's inferred type, or ``typing.IO`` when
        the overloads cannot be narrowed. Other context managers are left
        untyped because ``__enter__`` may return anything.

        Args:
            node: ``with`` statement.
            scope: Active lexical scope.

        """
        item: withitem
        for item in node.items:
            target: expr | None = item.optional_vars
            call: expr = item.context_expr
            if not isinstance(target, Name) or not isinstance(call, Call):
                continue
            if scope.lookup_var(name=target.id) is not None:
                continue
            opener: str = (
                call.func.id
                if isinstance(call.func, Name)
                else call.func.attr
                if isinstance(call.func, Attribute)
                else ""
            )
            if opener not in Constants.file_openers:
                continue
            if not self.resolved_assignment(
                target=target,
                resolved=self.infer_expr(node=call, scope=scope),
                scope=scope,
            ):
                self.record_target(
                    target=target,
                    name="typing.IO",
                    scope=scope,
                )

    def record_for(self: Self, *, node: For | AsyncFor, scope: Scope) -> None:
        """Type a `for` target from the iterated container's element.

        Args:
            node: Loop statement.
            scope: Active lexical scope.

        """
        iterable: expr = node.iter
        if (
            isinstance(iterable, Call)
            and len(iterable.args) == 1
            and not iterable.keywords
            and isinstance(iterable.func, Name | Attribute)
        ):
            caller: str = (
                iterable.func.id
                if isinstance(iterable.func, Name)
                else iterable.func.attr
            )
            if caller in Constants.iterable_wrappers:
                iterable = iterable.args[0]
        element: str | None = self.iter_element(node=iterable, scope=scope)
        if element is not None:
            self.record_target(target=node.target, name=element, scope=scope)

    def record_target(
        self: Self,
        *,
        target: expr,
        name: str,
        scope: Scope,
        element: str | None = None,
    ) -> None:
        """Bind a class name to a name or `self.attr` target.

        Args:
            target: Assignment target.
            name: Bound class name.
            scope: Active lexical scope.
            element: Iterated element type for container annotations.

        """
        if isinstance(target, Name):
            scope.var_types[target.id] = name
            _ = consume(value=scope.var_calls.pop(target.id, None))
            if element is not None:
                scope.var_elems[target.id] = element
            else:
                _ = consume(value=scope.var_elems.pop(target.id, None))
        elif isinstance(target, Attribute):
            self.record_self_attr(
                target=target,
                name=name,
                scope=scope,
                element=element,
            )

    def record_callable(
        self: Self,
        *,
        target: expr,
        value: Name | Attribute,
        scope: Scope,
    ) -> None:
        """Record a name or attribute bound to a callable reference.

        Bindings such as `c = A.a` or `fn = helper` let calls through
        the variable resolve to the aliased signature.

        Args:
            target: Assignment target.
            value: Callable reference expression.
            scope: Active lexical scope.

        """
        resolved: Resolved = self.infer_expr(node=value, scope=scope)
        if (
            resolved.kind == "external" and not callable(resolved.obj)
        ) or resolved.kind not in Constants.callable_kinds:
            resolved = Resolved()
        if isinstance(target, Name):
            self.bind_callable_name(
                name=target.id,
                resolved=resolved,
                scope=scope,
            )
        else:
            self.bind_callable_attr(
                target=target,
                resolved=resolved,
                scope=scope,
            )

    def resolve_name(self: Self, *, name: str, scope: Scope) -> Resolved:
        """Resolve a bare name through scope, module, imports, builtins.

        Args:
            name: Name expression text.
            scope: Active lexical scope.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved | None = None
        step: Callable[..., Resolved | None]
        for step in (
            self.name_def,
            self.name_class,
            self.name_var_call,
            self.name_var,
            self.name_scope_alias,
            self.name_scope_module,
        ):
            resolved = step(name=name, scope=scope)
            if resolved is not None:
                return resolved
        resolved = self.project.resolve_in_module(
            module=self.module,
            rest=[name],
        )
        if resolved.kind == "unknown":
            resolved = self.project.resolve_external(dotted=name)
        return resolved

    def name_var(self: Self, *, name: str, scope: Scope) -> Resolved | None:
        """Resolve `name` as a variable holding a class instance.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        var_type: str | None = scope.lookup_var(name=name)
        if var_type is None:
            return None
        return self.project.declared_instance(
            module=self.module,
            name=var_type,
        )

    def name_scope_alias(
        self: Self,
        *,
        name: str,
        scope: Scope,
    ) -> Resolved | None:
        """Resolve `name` as a function-local `from x import y`.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        local_alias: str | None = scope.lookup_alias(name=name)
        if local_alias is None:
            return None
        via_alias: Resolved = self.project.resolve_dotted(dotted=local_alias)
        if via_alias.kind != "unknown":
            return via_alias
        return self.project.resolve_external(dotted=local_alias)

    def name_scope_module(
        self: Self,
        *,
        name: str,
        scope: Scope,
    ) -> Resolved | None:
        """Resolve `name` as a function-local `import x`.

        Args:
            name: Name to resolve.
            scope: Active lexical scope.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        local_module: str | None = scope.lookup_module_alias(name=name)
        if local_module is None:
            return None
        via_local: Resolved = self.project.resolve_dotted(dotted=local_module)
        if via_local.kind != "unknown":
            return via_local
        return self.project.resolve_external(dotted=local_module)

    def infer_literal(self: Self, *, node: expr) -> Resolved:
        """Infer a literal container or scalar expression.

        Args:
            node: Literal-like expression.

        Returns:
            Resolved external instance or unknown.

        """
        type_name: str | None = value_type_name(node=node)
        if (
            type_name is None
            or (external := self.project.external_type(name=type_name)) is None
        ):
            return Resolved()
        external_cls: type
        literal_dotted: str
        external_cls, literal_dotted = external
        return Resolved(
            kind="external",
            obj=external_cls,
            ext_kind="instance",
            dotted=literal_dotted,
        )

    def infer_expr(self: Self, *, node: expr, scope: Scope) -> Resolved:
        """Infer what an expression denotes for attribute resolution.

        Args:
            node: Expression to classify.
            scope: Active lexical scope.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        if isinstance(node, Name):
            resolved = self.infer_name(node=node, scope=scope)
        elif isinstance(node, Attribute):
            owner: Resolved = self.infer_expr(node=node.value, scope=scope)
            resolved = self.attribute_of(owner=owner, name=node.attr)
            if resolved.kind == "unknown":
                resolved = self.fallback_external_member(name=node.attr)
        elif isinstance(node, Call):
            resolved = self.infer_call(node=node, scope=scope)
        elif isinstance(node, BinOp):
            resolved = self.infer_binop(node=node, scope=scope)
        elif isinstance(node, NamedExpr):
            resolved = self.infer_expr(node=node.value, scope=scope)
        elif isinstance(node, IfExp):
            left: Resolved = self.infer_expr(node=node.body, scope=scope)
            right: Resolved = self.infer_expr(node=node.orelse, scope=scope)
            resolved = left if left == right else Resolved()
        elif isinstance(
            node,
            Constant | JoinedStr | Dict | List | Set | Tuple,
        ):
            resolved = self.infer_literal(node=node)
        elif isinstance(node, Subscript):
            resolved = self.infer_subscript(node=node, scope=scope)
        return resolved

    def infer_binop(self: Self, *, node: BinOp, scope: Scope) -> Resolved:
        """Infer a binary expression from its concrete left-hand object.

        Args:
            node: Binary expression to classify.
            scope: Active lexical scope.

        Returns:
            Inferred result, or unknown when evaluation is unsafe.

        """
        owner: Resolved = self.infer_expr(node=node.left, scope=scope)
        if (
            owner.kind == "external"
            and owner.dotted in {"pathlib.Path", "pathlib.PurePath"}
            and type(node.op).__name__ == "Div"
        ):
            return owner
        if (
            owner.kind != "external"
            or owner.obj is None
            or not isinstance(node.right, Constant)
            or not isinstance(node.right.value, str | int | float | bytes)
        ):
            return Resolved()
        owner_obj: object = owner.obj
        if owner.ext_kind == "instance" and isinstance(owner_obj, type):
            try:
                owner_obj = cast(typ="type[object]", val=owner_obj)()
            except (OSError, TypeError, ValueError):
                return Resolved()
        method_name: str | None = {
            "Div": "__truediv__",
            "FloorDiv": "__floordiv__",
            "Mod": "__mod__",
            "Mult": "__mul__",
            "Add": "__add__",
            "Sub": "__sub__",
        }.get(type(node.op).__name__)
        method: object | None = (
            cast(typ="object", val=getattr(owner_obj, method_name))
            if method_name is not None and hasattr(owner_obj, method_name)
            else None
        )
        if not callable(method):
            return Resolved()
        try:
            result: object = method(node.right.value)
        except (ArithmeticError, OSError, TypeError, ValueError):
            return Resolved()
        return Resolved(
            kind="external",
            obj=result,
            ext_kind="instance",
            dotted=f"{type(result).__module__}.{type(result).__qualname__}",
        )

    def infer_subscript(
        self: Self,
        *,
        node: Subscript,
        scope: Scope,
    ) -> Resolved:
        """Infer common sequence-subscript result types.

        Args:
            node: Subscript expression.
            scope: Active lexical scope.

        Returns:
            Inferred result for type-preserving sequences and split results.

        """
        owner: Resolved = self.infer_expr(node=node.value, scope=scope)
        if owner.kind == "external" and owner.dotted in {
            "str",
            "builtins.str",
        }:
            return owner
        if (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Attribute)
            and node.value.func.attr in {"split", "rsplit", "splitlines"}
        ):
            external: tuple[type, str] | None = self.project.external_type(
                name="str",
            )
            if external is not None:
                external_cls: type
                dotted: str
                external_cls, dotted = external
                return Resolved(
                    kind="external",
                    obj=external_cls,
                    ext_kind="instance",
                    dotted=dotted,
                )
        return Resolved()

    def fallback_external_member(self: Self, *, name: str) -> Resolved:
        """Resolve a last-resort standard-library method by method name.

        Exact lexical receiver tracing always runs first. This fallback is
        limited to method names with a single intended runtime family in the
        exactus codebase, preventing a known standard method from being counted
        as an unresolved callee merely because generic element narrowing was
        unavailable.

        Args:
            name: Attribute method name.

        Returns:
            Resolved external member identity, or unknown.

        """
        owner_name: str | None = {
            "add_argument": "argparse.ArgumentParser",
            "append": "list",
            "endswith": "str",
            "get": "dict",
            "group": "re.Match",
            "lstrip": "str",
            "relative_to": "pathlib.Path",
            "removeprefix": "str",
            "removesuffix": "str",
            "replace": "str",
            "rstrip": "str",
            "seek": "io.BufferedRandom",
            "split": "str",
            "startswith": "str",
            "strip": "str",
        }.get(name)
        if owner_name is None:
            return Resolved()
        external: tuple[type, str] | None = self.project.external_type(
            name=owner_name,
        )
        if external is None:
            return Resolved()
        owner: type
        dotted: str
        owner, dotted = external
        member: LiveObject = getattr(owner, name, None)
        if member is None or not callable(member):
            return Resolved()
        return (
            self.external_member_callable(
                owner=Resolved(
                    kind="external",
                    obj=owner,
                    ext_kind="instance",
                    dotted=dotted,
                ),
                member=member,
                dotted=f"{dotted}.{name}",
            )
            or Resolved()
        )

    def infer_name(self: Self, *, node: Name, scope: Scope) -> Resolved:
        """Infer what a bare name denotes, including `self` and `cls`.

        Args:
            node: Name expression.
            scope: Active lexical scope.

        Returns:
            The `Resolved` result produced by the operation.

        """
        info: ClassInfo | None = scope.enclosing_class()
        resolved: Resolved = Resolved()
        if node.id == "self" and info is not None:
            resolved = Resolved(kind="instance", cls=info)
        elif node.id == "cls" and info is not None:
            resolved = Resolved(kind="class", cls=info)
        elif node.id not in Constants.receiver_names:
            resolved = self.resolve_name(name=node.id, scope=scope)
        return resolved

    def infer_special_attribute_call(
        self: Self,
        *,
        node: Call,
        scope: Scope,
    ) -> Resolved:
        """Infer known result-preserving attribute calls.

        Args:
            node: Attribute call expression.
            scope: Active lexical scope.

        Returns:
            Known result type, or unknown.

        """
        result: Resolved = Resolved()
        if isinstance(node.func, Attribute):
            owner: Resolved = self.infer_expr(
                node=node.func.value,
                scope=scope,
            )
            method: str = node.func.attr
            if owner.kind == "external":
                if (
                    owner.dotted in {"str", "builtins.str"}
                    and method
                    in {
                        "capitalize",
                        "casefold",
                        "center",
                        "expandtabs",
                        "format",
                        "format_map",
                        "join",
                        "ljust",
                        "lower",
                        "lstrip",
                        "removeprefix",
                        "removesuffix",
                        "replace",
                        "rjust",
                        "rstrip",
                        "strip",
                        "swapcase",
                        "title",
                        "upper",
                        "zfill",
                    }
                ) or (
                    owner.dotted in {"pathlib.Path", "pathlib.PurePath"}
                    and method
                    in {
                        "absolute",
                        "joinpath",
                        "relative_to",
                        "resolve",
                        "with_name",
                        "with_stem",
                        "with_suffix",
                    }
                ):
                    result = owner
                elif (
                    owner.dotted in {"re.Match", "_sre.SRE_Match"}
                    and method == "group"
                ):
                    string_type: tuple[type, str] | None = (
                        self.project.external_type(name="str")
                    )
                    if string_type is not None:
                        string_cls: type
                        string_dotted: str
                        string_cls, string_dotted = string_type
                        result = Resolved(
                            kind="external",
                            obj=string_cls,
                            ext_kind="instance",
                            dotted=string_dotted,
                        )
                elif method == "setdefault" and len(node.args) > 1:
                    result = self.infer_expr(node=node.args[1], scope=scope)
        return result

    def infer_cast_call(self: Self, *, node: Call, scope: Scope) -> Resolved:
        """Infer a ``typing.cast`` result.

        Args:
            node: Cast call.
            scope: Active lexical scope.

        Returns:
            Cast target type or inferred value type.

        """
        type_name: str | None = None
        value_node: expr | None = None
        item: keyword
        for item in node.keywords:
            if (
                item.arg == "typ"
                and isinstance(item.value, Constant)
                and isinstance(item.value.value, str)
            ):
                type_name = item.value.value.split(sep="[", maxsplit=1)[0]
            elif item.arg == "val":
                value_node = item.value
        if (
            type_name is not None
            and (external := self.project.external_type(name=type_name))
            is not None
        ):
            cast_cls: type
            cast_dotted: str
            cast_cls, cast_dotted = external
            return Resolved(
                kind="external",
                obj=cast_cls,
                ext_kind="instance",
                dotted=cast_dotted,
            )
        return (
            self.infer_expr(node=value_node, scope=scope)
            if value_node is not None
            else Resolved()
        )

    def infer_call(self: Self, *, node: Call, scope: Scope) -> Resolved:
        """Infer the result type of a call expression.

        Args:
            node: Call expression.
            scope: Active lexical scope.

        Returns:
            The inferred call-result object.

        """
        if isinstance(node.func, Name) and node.func.id == "super":
            return self.infer_super(scope=scope)
        if isinstance(node.func, Name) and node.func.id == "cast":
            return self.infer_cast_call(node=node, scope=scope)
        callee: Resolved = self.infer_expr(node=node.func, scope=scope)
        resolved: Resolved = self.call_result(callee=callee)
        if resolved.kind != "unknown":
            return resolved
        special: Resolved = self.infer_special_attribute_call(
            node=node,
            scope=scope,
        )
        if special.kind != "unknown":
            return special
        return self.known_external_result(callee=callee)

    def known_external_result(self: Self, *, callee: Resolved) -> Resolved:
        """Infer selected standard-library return types by dotted identity.

        Args:
            callee: Resolved callable object.

        Returns:
            Known standard-library result type, or unknown.

        """
        result_type: str | None = {
            "ast.unparse": "str",
            "json.dumps": "str",
            "re.compile": "re.Pattern",
            "re.fullmatch": "re.Match",
            "re.match": "re.Match",
            "re.search": "re.Match",
            "tempfile.TemporaryFile": "io.BufferedRandom",
        }.get(callee.dotted)
        method_name: str = callee.dotted.rsplit(sep=".", maxsplit=1)[-1]
        if result_type is None and callee.dotted.startswith(
            ("str.", "builtins.str."),
        ):
            if method_name in {
                "capitalize",
                "casefold",
                "center",
                "expandtabs",
                "format",
                "format_map",
                "join",
                "ljust",
                "lower",
                "lstrip",
                "removeprefix",
                "removesuffix",
                "replace",
                "rjust",
                "rstrip",
                "strip",
                "swapcase",
                "title",
                "upper",
                "zfill",
            }:
                result_type = "str"
            elif method_name in {"split", "rsplit", "splitlines"}:
                result_type = "list"
        if result_type is None and callee.dotted in {
            "re.Match.group",
            "_sre.SRE_Match.group",
        }:
            result_type = "str"
        if (
            result_type is None
            and callee.dotted.startswith("re.Pattern.")
            and callee.dotted.rsplit(sep=".", maxsplit=1)[-1]
            in {"fullmatch", "match", "search"}
        ):
            result_type = "re.Match"
        if result_type is None:
            return Resolved()
        external: tuple[type, str] | None = self.project.external_type(
            name=result_type,
        )
        if external is None:
            return Resolved()
        external_cls: type
        dotted: str
        external_cls, dotted = external
        return Resolved(
            kind="external",
            obj=external_cls,
            ext_kind="instance",
            dotted=dotted,
        )

    def infer_super(self: Self, *, scope: Scope) -> Resolved:
        """Infer a `super()` proxy as the next project or external base.

        Args:
            scope: Active lexical scope.

        Returns:
            The `Resolved` result produced by the operation.

        """
        info: ClassInfo | None = scope.enclosing_class()
        resolved: Resolved = Resolved()
        if info is not None:
            base: str = info.bases[0] if info.bases else "object"
            resolved = self.project.declared_instance(
                module=self.module,
                name=base,
            )
        return resolved

    def call_result(self: Self, *, callee: Resolved) -> Resolved:
        """Infer the result type produced by calling `callee`.

        Args:
            callee: Resolved callee expression.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        if callee.kind == "class" and callee.cls is not None:
            resolved = Resolved(kind="instance", cls=callee.cls)
        elif callee.kind == "external" and callee.ext_kind == "class":
            resolved = Resolved(
                kind="external",
                obj=callee.obj,
                ext_kind="instance",
                dotted=callee.dotted,
            )
        elif callee.kind == "stubclass":
            resolved = Resolved(
                kind="stubinstance",
                stub=callee.stub,
                dotted=callee.dotted,
            )
        elif callee.sig is not None and callee.sig.returns is not None:
            resolved = self.project.declared_instance(
                module=self.module,
                name=callee.sig.returns,
            )
        return resolved

    def attribute_of(self: Self, *, owner: Resolved, name: str) -> Resolved:
        """Resolve `owner.name` as an attribute access.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved | None = None
        step: Callable[..., Resolved | None]
        for step in (
            self.attr_module,
            self.attr_class,
            self.attr_instance,
            self.attr_external,
            self.attr_stub,
        ):
            resolved = step(owner=owner, name=name)
            if resolved is not None:
                return resolved
        return Resolved()

    def attr_module(
        self: Self,
        *,
        owner: Resolved,
        name: str,
    ) -> Resolved | None:
        """Resolve an attribute on a project module.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        if owner.kind != "module" or owner.module is None:
            return None
        resolved: Resolved = self.project.resolve_in_module(
            module=owner.module,
            rest=[name],
        )
        if resolved.kind != "unknown":
            return resolved
        return self.project.resolve_external(
            dotted=f"{owner.module.name}.{name}",
        )

    def attr_class(
        self: Self,
        *,
        owner: Resolved,
        name: str,
    ) -> Resolved | None:
        """Resolve an attribute on a project class object.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        if owner.kind != "class" or owner.cls is None:
            return None
        return self.project.resolve_in_class(info=owner.cls, rest=[name])

    def attr_instance(
        self: Self,
        *,
        owner: Resolved,
        name: str,
    ) -> Resolved | None:
        """Resolve an attribute on a project class instance.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        if owner.kind != "instance" or owner.cls is None:
            return None
        resolved: Resolved = self.project.resolve_in_class(
            info=owner.cls,
            rest=[name],
            bound=True,
        )
        if resolved.kind != "unknown":
            return resolved
        return self.external_base_attr(bases=owner.cls.bases, name=name)

    def attr_external(
        self: Self,
        *,
        owner: Resolved,
        name: str,
    ) -> Resolved | None:
        """Resolve an attribute on a live external object.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        if owner.kind != "external":
            return None
        return self.external_attr(owner=owner, name=name)

    def attr_stub(
        self: Self,
        *,
        owner: Resolved,
        name: str,
    ) -> Resolved | None:
        """Resolve an attribute on a stub module or class.

        Args:
            owner: Resolved owner expression.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        dotted: str = f"{owner.dotted}.{name}"
        resolved: Resolved | None = None
        if owner.kind == "stubmod" and isinstance(owner.stub, StubModule):
            resolved = self.project.stubs.in_module(
                module=owner.stub,
                rest=[name],
                dotted=dotted,
                depth=0,
            )
        elif owner.kind == "stubclass" and isinstance(owner.stub, StubClass):
            owner_module: StubModule | None = self.project.stubs.module(
                dotted=owner.dotted.removesuffix(f".{owner.stub.name}"),
            )
            if owner_module is None:
                return None
            resolved = self.project.stubs.in_class(
                module=owner_module,
                info=owner.stub,
                rest=[name],
                bound=False,
                dotted=dotted,
                depth=0,
            )
        elif owner.kind == "stubinstance" and isinstance(
            owner.stub,
            StubClass,
        ):
            owner_instance_module: StubModule | None = (
                self.project.stubs.module(
                    dotted=owner.dotted.removesuffix(f".{owner.stub.name}"),
                )
            )
            if owner_instance_module is None:
                return None
            resolved = self.project.stubs.in_class(
                module=owner_instance_module,
                info=owner.stub,
                rest=[name],
                bound=True,
                dotted=dotted,
                depth=0,
            )
        return resolved

    def external_base_attr(
        self: Self,
        *,
        bases: list[str],
        name: str,
    ) -> Resolved:
        """Resolve a method on an external base class.

        Args:
            bases: Base class names as written.
            name: Attribute name.

        Returns:
            The `Resolved` result produced by the operation.

        """
        resolved: Resolved = Resolved()
        base: str
        for base in bases:
            hit: Resolved | None = self.base_member(
                dotted=self.expand_base(name=base),
                name=name,
            )
            if hit is not None:
                resolved = hit
                break
        return resolved

    def base_member(self: Self, *, dotted: str, name: str) -> Resolved | None:
        """Resolve `name` on one external base class.

        Args:
            dotted: Dotted base-class path.
            name: Attribute name.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        parent: object = self.project.external_object(dotted=dotted)
        if (
            parent is None
            or not isinstance(parent, type)
            or not hasattr(parent, name)
        ):
            return None
        member: object = cast(typ="object", val=getattr(parent, name))
        if not callable(member):
            return None
        member_dotted: str = f"{dotted}.{name}"
        stubbed: Resolved | None = self.stub_member(
            dotted=member_dotted,
            bound=True,
        )
        if stubbed is not None:
            return stubbed
        capability: CapabilityIndex | None = self.project.capability
        member_sig: Sig | None
        if capability is not None and member_dotted in capability.sigs:
            stored: tuple[Param, ...] | None = capability.sigs[member_dotted]
            member_sig = (
                Sig(name=member_dotted, params=stored)
                if stored is not None
                else None
            )
        else:
            inspected_member: Signature | None = None
            with suppress(TypeError, ValueError):
                inspected_member = signature(obj=member)
            member_sig = (
                sig_from_inspect(name=member_dotted, resolved=inspected_member)
                if inspected_member is not None
                else None
            )
            self.project.capability_sigs[member_dotted] = (
                member_sig.params if member_sig is not None else None
            )
        if member_sig is None:
            fallback: Resolved | None = self.stub_member(
                dotted=member_dotted,
                bound=True,
            )
            return fallback or Resolved(
                kind="external",
                obj=member,
                ext_kind="instance",
                dotted=member_dotted,
            )
        if member_sig.params and member_sig.params[0].name in (
            Constants.receiver_names
        ):
            member_sig = Sig(
                name=member_sig.name,
                params=member_sig.params[1:],
                method=member_sig.method,
                returns=member_sig.returns,
            )
        return Resolved(kind="function", sig=member_sig)

    def stub_member(
        self: Self,
        *,
        dotted: str,
        bound: bool,
    ) -> Resolved | None:
        """Resolve a member through the typeshed stub index.

        Args:
            dotted: Dotted member path.
            bound: Whether the receiver is already bound.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        stubbed: Resolved = self.project.stubs.lookup(dotted=dotted)
        if stubbed.kind != "function" or not stubbed.sigs:
            return None
        return Resolved(
            kind="function",
            sigs=stubbed.sigs,
            bound=bound,
            dotted=dotted,
        )

    def stub_member_via_type(
        self: Self,
        *,
        member: LiveObject,
        bound: bool,
    ) -> Resolved | None:
        """Resolve a bound method through its owner type's stub.

        When `dotted` names a module-level variable (e.g.
        ``os.environ``), the stub index cannot resolve the path
        directly.  For a bound method the owner type's qualified
        stub path (``os._Environ.get``) succeeds instead.

        Args:
            member: Bound method or callable attribute.
            bound: Whether the receiver is already supplied.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        if member is None or not hasattr(member, "__self__"):
            return None
        owner: object = getattr(member, "__self__", None)
        if owner is None:
            return None
        owner_type: type = type(owner)
        method_name: str = getattr(member, "__name__", "")
        if not method_name:
            return None
        type_dotted: str = (
            f"{owner_type.__module__}.{owner_type.__qualname__}.{method_name}"
        )
        return self.stub_member(dotted=type_dotted, bound=bound)

    def expand_base(self: Self, *, name: str) -> str:
        """Expand a base-class name through the module's import table.

        Args:
            name: Base class name as written.

        Returns:
            The `str` result produced by the operation.

        """
        parts: list[str] = name.split(sep=".")
        first: str = parts[0]
        if first in self.module.aliases:
            target: str = self.module.aliases[first]
            suffix: str = ".".join(parts[1:])
            return f"{target}.{suffix}" if suffix else target
        if first in self.module.module_aliases:
            target_module: str = self.module.module_aliases[first]
            suffix_module: str = ".".join(parts[1:])
            return (
                f"{target_module}.{suffix_module}"
                if suffix_module
                else target_module
            )
        return name

    def external_attr(self: Self, *, owner: Resolved, name: str) -> Resolved:
        """Resolve an attribute on a live external object.

        Args:
            owner: Resolved external owner.
            name: Attribute name.

        Returns:
            The `Resolved` result produced by the operation.

        """
        owner_obj: object = owner.obj
        if owner_obj is None or not hasattr(owner_obj, name):
            return Resolved()
        member: object = cast(typ="object", val=getattr(owner_obj, name))
        resolved: Resolved | None = self.external_member(
            owner=owner,
            name=name,
            member=member,
        )
        return resolved if resolved is not None else Resolved()

    def external_member(
        self: Self,
        *,
        owner: Resolved,
        name: str,
        member: LiveObject,
    ) -> Resolved | None:
        """Resolve an attribute member on a live external object.

        Args:
            owner: Resolved external owner.
            name: Attribute name.
            member: The attribute value.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        dotted: str = f"{owner.dotted}.{name}"
        resolved: Resolved | None = None
        if isinstance(member, property):
            property_type: str | None = None
            if owner.dotted in {"pathlib.Path", "pathlib.PurePath"}:
                property_type = {
                    "anchor": "str",
                    "drive": "str",
                    "name": "str",
                    "parent": owner.dotted,
                    "root": "str",
                    "stem": "str",
                    "suffix": "str",
                }.get(name)
            if (
                property_type is not None
                and (
                    external := self.project.external_type(name=property_type)
                )
                is not None
            ):
                property_cls: type
                property_dotted: str
                property_cls, property_dotted = external
                resolved = Resolved(
                    kind="external",
                    obj=property_cls,
                    ext_kind="instance",
                    dotted=property_dotted,
                )
        elif isinstance(member, ModuleType):
            resolved = Resolved(
                kind="external",
                obj=member,
                ext_kind="module",
                dotted=dotted,
            )
        elif isinstance(member, type):
            resolved = Resolved(
                kind="external",
                obj=member,
                ext_kind="class",
                dotted=dotted,
            )
        elif not callable(member):
            if owner.dotted.startswith("ast.") and name in {
                "arg",
                "attr",
                "id",
                "name",
            }:
                external: tuple[type, str] | None = self.project.external_type(
                    name="str",
                )
                if external is not None:
                    string_cls: type
                    string_dotted: str
                    string_cls, string_dotted = external
                    resolved = Resolved(
                        kind="external",
                        obj=string_cls,
                        ext_kind="instance",
                        dotted=string_dotted,
                    )
            if resolved is None:
                resolved = self.project.stubs.lookup(dotted=dotted)
        else:
            resolved = self.external_member_callable(
                owner=owner,
                member=member,
                dotted=dotted,
            )
        return resolved

    def external_member_callable(
        self: Self,
        *,
        owner: Resolved,
        member: LiveObject,
        dotted: str,
    ) -> Resolved | None:
        """Resolve a callable member on a live external object.

        Args:
            owner: Resolved external owner.
            member: The callable attribute value.
            dotted: Full dotted member path.

        Returns:
            The `Resolved | None` result produced by the operation.

        """
        bound: bool = owner.ext_kind == "instance" or (
            getattr(member, "__self__", None) is not None
        )
        if not callable(member):
            return self.stub_member(dotted=dotted, bound=bound)
        stubbed: Resolved | None = self.stub_member(dotted=dotted, bound=bound)
        if stubbed is not None:
            return stubbed
        via_type: Resolved | None = self.stub_member_via_type(
            member=member,
            bound=bound,
        )
        if via_type is not None:
            return via_type
        capability: CapabilityIndex | None = self.project.capability
        sig: Sig | None
        if capability is not None and dotted in capability.sigs:
            stored: tuple[Param, ...] | None = capability.sigs[dotted]
            sig = (
                Sig(name=dotted, params=stored) if stored is not None else None
            )
        else:
            inspected: Signature | None = None
            with suppress(TypeError, ValueError):
                inspected = signature(obj=member)
            sig = (
                sig_from_inspect(name=dotted, resolved=inspected)
                if inspected is not None
                else None
            )
            self.project.capability_sigs[dotted] = (
                sig.params if sig is not None else None
            )
        if sig is None:
            fallback: Resolved | None = self.stub_member(
                dotted=dotted,
                bound=bound,
            )
            return fallback or Resolved(
                kind="external",
                obj=member,
                ext_kind="instance",
                dotted=dotted,
            )
        if owner.ext_kind == "instance" and sig.params:
            first: Param = sig.params[0]
            if first.name in Constants.receiver_names:
                sig = Sig(
                    name=sig.name,
                    params=sig.params[1:],
                    method=sig.method,
                    returns=sig.returns,
                )
        return Resolved(
            kind="function",
            sig=sig,
            obj=member,
            ext_kind="instance",
            dotted=dotted,
            bound=bound,
        )

    def check_call(self: Self, *, node: Call, scope: Scope) -> None:
        """Exactus one call site for positional keyword-capable args.

        Args:
            node: Call node.
            scope: Active lexical scope.

        """
        if not node.args:
            return
        all_starred: bool = True
        argument: expr
        for argument in node.args:
            if not isinstance(argument, Starred):
                all_starred = False
                break
        if all_starred:
            return
        self.calls += 1
        callee_text: str = unparse(ast_obj=node.func)
        if callee_text in Constants.skip_calls:
            return
        resolved: Resolved = self.infer_expr(node=node.func, scope=scope)
        param_sets: list[tuple[Param, ...]]
        confidence: str
        param_sets, confidence = self.param_sets_of(resolved=resolved)
        if (
            not param_sets
            and isinstance(node.func, Attribute)
            and node.func.attr not in Constants.positional_only_methods
            and not self.receiver_is_external(node=node.func, scope=scope)
        ):
            fallback: tuple[list[tuple[Param, ...]], str] | None = (
                self.fallback_method(name=node.func.attr, node=node)
            )
            if fallback is not None:
                param_sets, confidence = fallback
        if not param_sets:
            if resolved.kind == "unknown":
                self.record_unresolved(callee_text=callee_text, node=node)
            return
        self.resolved_calls += 1
        self.apply_params(
            node=node,
            param_sets=param_sets,
            callee_text=callee_text,
            confidence=confidence,
        )

    def receiver_is_external(
        self: Self,
        *,
        node: Attribute,
        scope: Scope,
    ) -> bool:
        """Return whether a method receiver has a known non-project type.

        A receiver traced to a standard-library or third-party type (for
        example ``db: sqlite3.Connection``), or annotated with any type the
        project index cannot see, must never be matched against same-named
        project methods: C methods without an introspectable signature are
        positional-only, so name-based guessing would report false positives.

        Args:
            node: Method attribute whose receiver is inspected.
            scope: Active lexical scope.

        Returns:
            Whether the receiver has a known type outside the project index.

        """
        if self.infer_expr(node=node.value, scope=scope).kind in {
            "external",
            "stubinstance",
            "stubclass",
        }:
            return True
        if self.inherited_external_attr(node=node.value, scope=scope):
            return True
        type_name: str | None = self.annotated_receiver_type(
            node=node.value,
            scope=scope,
        )
        return (
            type_name is not None
            and self.project.class_named(name=type_name) is None
        )

    def inherited_external_attr(
        self: Self,
        *,
        node: expr,
        scope: Scope,
    ) -> bool:
        """Return whether ``self.attr`` comes from a non-project base class.

        An attribute the project class never defines, on a class with a
        base outside the project (for example ``self.wfile`` on an
        ``http.server`` handler), belongs to that external base, so its
        methods must not be guessed from same-named project methods.

        Args:
            node: Receiver expression.
            scope: Active lexical scope.

        Returns:
            Whether the receiver is an attribute inherited externally.

        """
        if not (
            isinstance(node, Attribute)
            and isinstance(node.value, Name)
            and node.value.id in {"self", "cls"}
        ):
            return False
        info: ClassInfo | None = scope.enclosing_class()
        if info is None or node.attr in {
            *info.attr_types,
            *info.attr_calls,
            *info.methods,
        }:
            return False
        return any(
            self.project.class_named(name=base.rsplit(sep=".", maxsplit=1)[-1])
            is None
            for base in info.bases
        )

    def annotated_receiver_type(
        self: Self,
        *,
        node: expr,
        scope: Scope,
    ) -> str | None:
        """Return the declared type name of a receiver expression.

        Args:
            node: Receiver expression.
            scope: Active lexical scope.

        Returns:
            The annotated class name, or ``None`` when undeclared.

        """
        if isinstance(node, Name):
            return (
                None
                if node.id in {"self", "cls"}
                else scope.lookup_var(name=node.id)
            )
        if not isinstance(node, Attribute):
            return None
        if isinstance(node.value, Name) and node.value.id == "self":
            info: ClassInfo | None = scope.enclosing_class()
            return None if info is None else info.attr_types.get(node.attr)
        owner: str | None = self.annotated_receiver_type(
            node=node.value,
            scope=scope,
        )
        if owner is None:
            return None
        owner_info: ClassInfo | None = self.project.class_named(name=owner)
        return (
            owner
            if owner_info is None
            else owner_info.attr_types.get(node.attr)
        )

    def param_sets_of(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str]:
        """Convert a resolved callee into call-ready parameter sets.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str]` result produced by
            the operation.

        """
        result: tuple[list[tuple[Param, ...]], str] | None = None
        step: Callable[..., tuple[list[tuple[Param, ...]], str] | None]
        for step in (
            self.sets_function,
            self.sets_class,
            self.sets_instance,
            self.sets_stubclass,
            self.sets_stubinstance,
            self.sets_external,
        ):
            result = step(resolved=resolved)
            if result is not None:
                return result
        return [], "resolved"

    def verify_sets(
        self: Self,
        *,
        resolved: Resolved,
        sets: list[tuple[Param, ...]],
        member: str | None,
    ) -> tuple[list[tuple[Param, ...]], str]:
        """Verify stub parameter kinds against the live runtime object.

        Args:
            resolved: Resolved callee carrying a live object or path.
            sets: Call-ready parameter tuples from stub signatures.
            member: Attribute to probe instead of the object itself.

        Returns:
            The corrected parameter sets plus the confidence label,
            `stub-rt` when every keyword-capable parameter probed
            conclusively and `stub` otherwise.

        """
        key: str = resolved.dotted
        if member is not None:
            key = f"{key}.{member}" if key else member
        capability: CapabilityIndex | None = self.project.capability
        if key and capability is not None:
            record: VerifyRecord | None = capability.verify.get(key)
            if record is not None:
                return (
                    [tuple(params) for params in record.sets],
                    "stub-rt" if record.conclusive else "stub",
                )
        obj: LiveObject = resolved.obj
        if obj is None and resolved.dotted:
            obj = self.project.external_object(dotted=resolved.dotted)
        if member is not None:
            obj = _verify_member(obj=obj, member=member)
        names: frozenset[str] = self.posonly_names(resolved=resolved, obj=obj)
        if names:
            sets = [
                tuple(
                    replace(param, kind="posonly")
                    if param.name in names and param.kind == "poskw"
                    else param
                    for param in params
                )
                for params in sets
            ]
        if obj is None or not callable(obj) or not probeable(obj=obj):
            return self._verify_result(
                key=key,
                sets=tuple(sets),
                conclusive=False,
            )
        verified: list[tuple[Param, ...]] = []
        conclusive: bool = True
        params: tuple[Param, ...]
        for params in sets:
            checked: tuple[Param, ...]
            certain: bool
            checked, certain = self.project.verify_params(
                obj=obj,
                params=params,
            )
            verified.append(checked)
            conclusive = conclusive and certain
        return self._verify_result(
            key=key,
            sets=tuple(verified),
            conclusive=conclusive,
        )

    def sets_function(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for a resolved function or method.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "function":
            return None
        if resolved.sigs:
            sets: list[tuple[Param, ...]] = list(
                map(
                    partial(self.ready_params, bound=resolved.bound),
                    resolved.sigs,
                ),
            )
            return self.verify_sets(resolved=resolved, sets=sets, member=None)
        if resolved.sig is None:
            return [], "resolved"
        return (
            [self.ready_params(sig=resolved.sig, bound=resolved.bound)],
            "resolved",
        )

    def sets_class(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for a project class constructor.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "class" or resolved.cls is None:
            return None
        return (
            [
                self.ready_params(
                    sig=self.constructor_sig(info=resolved.cls),
                    bound=True,
                ),
            ],
            "constructor",
        )

    def sets_instance(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for calling a project class instance.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "instance" or resolved.cls is None:
            return None
        call_sig: Sig | None = self.project.find_method(
            info=resolved.cls,
            name="__call__",
        )
        if call_sig is None:
            return [], "resolved"
        return ([self.ready_params(sig=call_sig, bound=True)], "resolved")

    def sets_stubclass(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for a stub class constructor.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "stubclass" or not isinstance(
            resolved.stub,
            StubClass,
        ):
            return None
        ctors: list[Sig] = resolved.stub.ctors
        if not ctors:
            return (
                [
                    (
                        Param(name="args", kind="vararg"),
                        Param(name="kwargs", kind="varkw"),
                    ),
                ],
                "stub",
            )
        sets: list[tuple[Param, ...]] = list(
            map(partial(self.ready_params, bound=True), ctors),
        )
        return self.verify_sets(resolved=resolved, sets=sets, member=None)

    def sets_stubinstance(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for calling a stub class instance.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "stubinstance" or not isinstance(
            resolved.stub,
            StubClass,
        ):
            return None
        calls: list[Sig] = resolved.stub.methods.get("__call__", [])
        sets: list[tuple[Param, ...]] = list(
            map(partial(self.ready_params, bound=True), calls),
        )
        return self.verify_sets(
            resolved=resolved,
            sets=sets,
            member="__call__",
        )

    def sets_external(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Parameter sets for a live external callable.

        Args:
            resolved: Resolved callee expression.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        if resolved.kind != "external" or resolved.obj is None:
            return None
        stubbed: Resolved = self.project.stubs.lookup(dotted=resolved.dotted)
        if stubbed.kind != "unknown":
            return self.param_sets_of(resolved=stubbed)
        via_type: Resolved = self.external_via_type(resolved=resolved)
        if via_type.kind != "unknown":
            return self.param_sets_of(resolved=via_type)
        external: tuple[Param, ...] | None = self.external_callable_params(
            resolved=resolved,
        )
        if external is not None:
            return [external], "external"
        return [], "external"

    def external_via_type(self: Self, *, resolved: Resolved) -> Resolved:
        """Resolve a bound method through its owner type's stub.

        When `resolved.dotted` names a module-level variable (e.g.
        ``os.environ``), the stub index cannot resolve the path
        directly.  For a bound method the owner type's qualified
        stub path (``os._Environ.get``) succeeds instead.

        Args:
            resolved: Resolved external callee.

        Returns:
            The `Resolved` result produced by the operation.

        """
        obj: object = resolved.obj
        if obj is None or not hasattr(obj, "__self__"):
            return Resolved()
        owner: object = getattr(obj, "__self__", None)
        if owner is None:
            return Resolved()
        owner_type: type = type(owner)
        method_name: str = getattr(obj, "__name__", "")
        if not method_name:
            return Resolved()
        type_dotted: str = (
            f"{owner_type.__module__}.{owner_type.__qualname__}.{method_name}"
        )
        return self.project.stubs.lookup(dotted=type_dotted)

    def constructor_sig(self: Self, *, info: ClassInfo) -> Sig:
        """Return the effective constructor signature for a class.

        Args:
            info: Class record.

        Returns:
            The `Sig` result produced by the operation.

        """
        init: Sig | None = self.project.find_method(info=info, name="__init__")
        if init is not None:
            return init
        if info.fields is not None:
            return Sig(
                name=f"{info.name}.__init__",
                params=(Param(name="self", kind="posonly"), *info.fields),
                method="instance",
            )
        return Sig(
            name=f"{info.name}.__init__",
            params=(
                Param(name="self", kind="posonly"),
                Param(name="args", kind="vararg"),
                Param(name="kwargs", kind="varkw"),
            ),
            method="instance",
        )

    def external_callable_params(
        self: Self,
        *,
        resolved: Resolved,
    ) -> tuple[Param, ...] | None:
        """Return runtime signature parameters for an external callable.

        Args:
            resolved: Resolved external callee.

        Returns:
            The `tuple[Param, ...] | None` result produced by the
            operation.

        """
        capability: CapabilityIndex | None = self.project.capability
        if (
            capability is not None
            and resolved.dotted
            and resolved.dotted in capability.sigs
        ):
            return capability.sigs[resolved.dotted]
        obj: object = resolved.obj
        result: tuple[Param, ...] | None = None
        if obj is not None and callable(obj):
            try:
                inspected: Signature = signature(obj=obj)
            except (TypeError, ValueError):
                pass
            else:
                sig: Sig = sig_from_inspect(
                    name=resolved.dotted,
                    resolved=inspected,
                )
                if resolved.ext_kind == "instance" and sig.params:
                    first: Param = sig.params[0]
                    if first.name in Constants.receiver_names:
                        result = sig.params[1:]
                if result is None:
                    result = sig.params
        if resolved.dotted:
            self.project.capability_sigs[resolved.dotted] = result
        return result

    def fallback_method(
        self: Self,
        *,
        name: str,
        node: Call,
    ) -> tuple[list[tuple[Param, ...]], str] | None:
        """Resolve a method by unique global name as a last resort.

        Args:
            name: Method name.
            node: Call node for ambiguous-call reporting.

        Returns:
            The `tuple[list[tuple[Param, ...]], str] | None` result
            produced by the operation.

        """
        candidates: list[tuple[ClassInfo, Sig]] = self.project.methods.get(
            name,
            [],
        )
        if not candidates:
            return None
        if len(candidates) == 1:
            sig: Sig = candidates[0][1]
            return [self.ready_params(sig=sig, bound=True)], "unique-name"
        candidate_sig: Sig
        verdicts: list[bool] = []
        labels: list[str] = []
        _owner: ClassInfo
        for _owner, candidate_sig in candidates:
            labels.append(candidate_sig.name)
            verdicts.append(self.would_flag(sig=candidate_sig, node=node))
        if verdicts and all(verdicts):
            first_sig: Sig = candidates[0][1]
            return (
                [self.ready_params(sig=first_sig, bound=True)],
                "ambiguous-all-flag",
            )
        self.ambiguous.append(
            AmbiguousCall(
                path=self.module.path,
                line=node.lineno,
                callee=unparse(ast_obj=node.func),
                candidates=tuple(labels),
            ),
        )
        return None

    def would_flag(self: Self, *, sig: Sig, node: Call) -> bool:
        """Report whether a candidate signature flags this call.

        Args:
            sig: Candidate signature.
            node: Call node.

        Returns:
            The `bool` result produced by the operation.

        """
        params: tuple[Param, ...] = self.ready_params(sig=sig, bound=True)
        bindable: list[Param] = list(filter(_positional_capable, params))
        index: int
        argument: expr
        for index, argument in enumerate(iterable=node.args):
            if isinstance(argument, Starred) or index >= len(bindable):
                break
            if bindable[index].kind == "poskw":
                return True
        return False

    def apply_params(
        self: Self,
        *,
        node: Call,
        param_sets: list[tuple[Param, ...]],
        callee_text: str,
        confidence: str,
    ) -> None:
        """Bind call arguments to parameter sets and report findings.

        With overloads, an argument is flagged only when every
        arity-compatible overload binds it to a keyword-capable
        parameter; mixed verdicts go to the ambiguous list.

        Args:
            node: Call node.
            param_sets: Call-ready parameter tuples (receiver dropped).
            callee_text: Callee expression as written.
            confidence: Resolution confidence label.

        """
        if any(isinstance(argument, Starred) for argument in node.args):
            return
        positional: list[expr] = []
        argument: expr
        for argument in node.args:
            if isinstance(argument, Starred):
                break
            positional.append(argument)
        compatible: list[tuple[Param, ...]] = []
        params: tuple[Param, ...]
        for params in param_sets:
            if not arity_fits(params=params, arity=len(positional)):
                continue
            compatible.append(params)
        if not compatible:
            compatible = param_sets
        keyword_names: set[str] = set()
        item: keyword
        for item in node.keywords:
            if item.arg is not None:
                keyword_names |= {item.arg}
        index: int
        for index, argument in enumerate(iterable=positional):
            self.check_positional_arg(
                node=node,
                index=index,
                argument=argument,
                compatible=compatible,
                keyword_names=keyword_names,
                callee_text=callee_text,
                confidence=confidence,
                positional_count=len(positional),
            )

    def check_positional_arg(
        self: Self,
        **kwargs: Unpack[PositionalCheckArgs],
    ) -> None:
        """Check positional arg.

        Args:
            kwargs: Kwargs.

        """
        node: Call = kwargs["node"]
        index: int = kwargs["index"]
        argument: expr = kwargs["argument"]
        compatible: list[tuple[Param, ...]] = kwargs["compatible"]
        keyword_names: set[str] = kwargs["keyword_names"]
        callee_text: str = kwargs["callee_text"]
        confidence: str = kwargs["confidence"]
        positional_count: int = kwargs["positional_count"]
        verdicts: list[Param] = self._arg_verdicts(
            compatible=compatible,
            index=index,
        )
        flaggable: list[Param] = []
        blocked: list[Param] = []
        param: Param
        for param in verdicts:
            if param.kind == "poskw":
                flaggable.append(param)
            elif param.kind == "posonly":
                blocked.append(param)
        if flaggable and blocked:
            self._report_ambiguous(
                node=node,
                verdicts=verdicts,
                callee_text=callee_text,
            )
            return
        if not flaggable:
            return
        later_index: int
        for later_index in range(index + 1, positional_count):
            later: list[Param] = self._arg_verdicts(
                compatible=compatible,
                index=later_index,
            )
            if not later or any(
                candidate.kind != "poskw" for candidate in later
            ):
                return
        target: Param = flaggable[0]
        if (
            callee_text.startswith("stream.")
            and target.name in {"n", "offset", "s", "size"}
            and callee_text.rsplit(sep=".", maxsplit=1)[-1]
            in {"read", "seek", "truncate", "write"}
        ):
            return
        if target.name in keyword_names:
            return
        self.findings.append(
            Finding(
                path=self.module.path,
                line=node.lineno,
                callee=callee_text,
                param=target.name,
                index=index,
                argument=unparse(ast_obj=argument),
                confidence=confidence,
                suggestion=(f"{target.name}={unparse(ast_obj=argument)}"),
            ),
        )

    @staticmethod
    def _arg_verdicts(
        *,
        compatible: list[tuple[Param, ...]],
        index: int,
    ) -> list[Param]:
        """Collect the parameter bound at `index` across signatures.

        Args:
            compatible: Arity-compatible parameter tuples.
            index: Positional index of the argument.

        Returns:
            The `list[Param]` result produced by the operation.

        """
        verdicts: list[Param] = []
        params: tuple[Param, ...]
        param: Param
        for params in compatible:
            bindable: list[Param] = []
            for param in params:
                if not _positional_capable(param=param):
                    continue
                bindable.append(param)
            if index < len(bindable):
                verdicts.append(bindable[index])
        return verdicts

    def _verify_result(
        self: Self,
        *,
        key: str,
        sets: tuple[tuple[Param, ...], ...],
        conclusive: bool,
    ) -> tuple[list[tuple[Param, ...]], str]:
        """Record and return one external ``verify_sets`` outcome.

        Outcomes for non-project callees are captured so a
        ``--write-capability-index`` run can commit them as canonical
        runtime truth for hosts where the same callable resolves
        differently.

        Args:
            key: Capability index key (dotted callable path).
            sets: Corrected call-ready parameter tuples.
            conclusive: Whether every keyword probe was conclusive.

        Returns:
            The parameter sets plus the ``stub-rt``/``stub`` label.

        """
        if (
            key
            and "." in key
            and key.split(sep=".", maxsplit=1)[0]
            not in self.project.project_roots
        ):
            self.project.capability_verify[key] = VerifyRecord(
                sets=sets,
                conclusive=conclusive,
            )
        return list(sets), "stub-rt" if conclusive else "stub"

    def _report_ambiguous(
        self: Self,
        *,
        node: Call,
        verdicts: list[Param],
        callee_text: str,
    ) -> None:
        """Record a call whose overloads disagree on keyword safety.

        Args:
            node: Call node.
            verdicts: Parameters bound across compatible signatures.
            callee_text: Callee expression as written.

        """
        overload_names: list[str] = list(map(_overload_name, verdicts))
        self.ambiguous.append(
            AmbiguousCall(
                path=self.module.path,
                line=node.lineno,
                callee=callee_text,
                candidates=tuple(overload_names),
            ),
        )


def probe_module(*, obj: LiveObject) -> str:
    """Return the module that owns a live probe target.

    Args:
        obj: Live callable considered for probing.

    Returns:
        Owning module name, or an empty string when unavailable.

    """
    owner: LiveObject = getattr(obj, "__objclass__", None)
    module: LiveObject = getattr(
        owner if isinstance(owner, type) else obj,
        "__module__",
        "",
    )
    return module if isinstance(module, str) else ""


def probeable(*, obj: LiveObject) -> bool:
    """Decide whether a sentinel probe call on `obj` is side-effect safe.

    Runtime probing is deliberately allowlisted. Builtin types and
    callables remain supported, while known-pure stdlib computational
    modules are also eligible. Arbitrary project, I/O, process, network,
    filesystem, environment, random-state, and third-party callables are
    never executed merely to improve an exactus verdict.

    Args:
        obj: Live callable considered for probing.

    Returns:
        Whether the callable may be invoked with synthetic probe values.

    """
    if isinstance(obj, type):
        return getattr(obj, "__module__", "") == "builtins"
    name: LiveObject = getattr(obj, "__name__", "")
    return (
        isinstance(name, str)
        and name not in Constants.probe_blocklist
        and (
            (module := probe_module(obj=obj)) == "builtins"
            or module in Constants.probe_safe_modules
        )
    )


def _verify_member(*, obj: LiveObject, member: str) -> LiveObject:
    """Resolve the member attribute used as the probe target.

    `__call__` on a class object only counts when some class in the MRO
    defines it itself; the `type.__call__` descriptor inherited by every
    class does not describe the instance-call signature.

    Args:
        obj: Resolved live owner object.
        member: Attribute name to probe instead of `obj`.

    Returns:
        The live attribute object, or `None` when it must not be probed.

    """
    found: LiveObject = getattr(obj, member, None) if obj is not None else None
    if (
        member == "__call__"
        and isinstance(obj, type)
        and not any(member in vars(base) for base in obj.__mro__)
    ):
        return None
    return found


def kwarg_verdict(*, message: str, param: str) -> bool | None:
    """Classify a probe `TypeError` as keyword rejection or acceptance.

    Args:
        message: `TypeError` text raised by the probe call.
        param: Keyword name being probed.

    Returns:
        False when the keyword was rejected, True when it bound and the
        call failed afterwards, and None when the outcome is unclear.

    """
    if "keyword" in message or "positional-only" in message:
        return False
    missing: Match[str] | None = search(
        pattern=r"(?:missing|required)[^']*'([^']+)'",
        string=message,
    )
    if missing is not None:
        return missing.group(1) != param
    return not (
        "expected" in message or "takes" in message or "required" in message
    )


def probe_value(*, name: str) -> LiveObject:
    """Return a safe runtime value for a parameter name.

    Args:
        name: Parameter name needing a probe value.

    Returns:
        The name-specific safe value, or the `None` fallback.

    """
    return Constants.probe_values.get(name, Constants.probe_default)


def receiver_for(*, owner: type) -> LiveObject:
    """Build a fresh instance of `owner` for method probing.

    Args:
        owner: Builtin type needing a receiver instance.

    Returns:
        A new owner instance, or None when it needs constructor
        arguments that are not registered.

    """
    factory: Callable[[], LiveObject] = Constants.receiver_factories.get(
        owner.__name__,
        owner,
    )
    try:
        return factory()
    except (RuntimeError, TypeError, ValueError):
        return None


def bind_probe(*, obj: LiveObject) -> tuple[LiveObject, bool]:
    """Return a probe target and whether it carries a bound receiver.

    Unbound builtin method descriptors cannot validate keywords until a
    correctly typed receiver is present; binding a fresh instance makes
    their keyword checks observable.

    Args:
        obj: Callable or descriptor resolved for a stub signature.

    Returns:
        The `(target, bound)` pair produced by the operation.

    """
    if isinstance(obj, type):
        return obj, False
    self_obj: LiveObject = getattr(obj, "__self__", None)
    if self_obj is not None and not isinstance(self_obj, type):
        return obj, True
    owner: LiveObject = getattr(obj, "__objclass__", None)
    if not isinstance(owner, type):
        return obj, False
    receiver: LiveObject = receiver_for(owner=owner)
    if receiver is None:
        return obj, False
    member_name: LiveObject = getattr(obj, "__name__", "")
    if not isinstance(member_name, str):
        return obj, False
    bound: LiveObject = getattr(receiver, member_name, None)
    return (obj, False) if bound is None else (bound, True)


def probe_call(
    *,
    obj: LiveObject,
    params: tuple[Param, ...],
    index: int,
) -> bool | None:
    """Probe whether `params[index]` accepts a keyword on `obj`.

    Calls `obj` with safe values for the preceding positional
    parameters plus the candidate by keyword. Keyword-capable
    parameters bind and the call then either succeeds or fails on the
    value; positional-only parameters produce a keyword-related
    `TypeError` instead.

    Args:
        obj: Live callable under test.
        params: Call-ready parameter tuple the probe is drawn from.
        index: Index of the parameter passed by keyword.

    Returns:
        The `bool | None` result produced by the operation; None when
        the object is not callable.

    """
    target: LiveObject
    bound: bool
    target, bound = bind_probe(obj=obj)
    if not callable(target):
        return None
    flagged: Param = params[index]
    args: list[LiveObject] = []
    earlier: Param
    for earlier in params[:index]:
        if not _positional_capable(param=earlier) or (
            bound and earlier.name in Constants.receiver_names
        ):
            continue
        args.append(probe_value(name=earlier.name))
    exc: TypeError
    try:
        _ = consume(
            value=target(
                *args,
                **{flagged.name: probe_value(name=flagged.name)},
            ),
        )
    except TypeError as exc:
        return kwarg_verdict(message=str(object=exc), param=flagged.name)
    except (
        ArithmeticError,
        AssertionError,
        AttributeError,
        BufferError,
        EOFError,
        ImportError,
        IndexError,
        KeyError,
        LookupError,
        MemoryError,
        NameError,
        NotImplementedError,
        OSError,
        RecursionError,
        RuntimeError,
        StopAsyncIteration,
        StopIteration,
        SystemError,
        UnicodeError,
        ValueError,
    ):
        return True
    return True


@dataclass(frozen=True, slots=True)
class TypeTrial:
    """Observed runtime result for one candidate argument type.

    Attributes:
        type_name: Candidate runtime type label.
        observation: Runtime acceptance classification.
        exception_type: Raised exception class name, when present.
        exception_message: Exception text, when present.

    """

    type_name: str
    observation: str
    exception_type: str | None = None
    exception_message: str | None = None


@dataclass(frozen=True, slots=True)
class TypeParameter:
    """Empirical type information for one callable parameter.

    Attributes:
        name: Parameter name.
        kind: Corrected runtime parameter kind.
        advertised_kinds: Parameter kinds advertised by source signatures.
        has_default: Whether the signature supplies a default.
        keyword_valid: Empirical keyword validity when applicable.
        trials: Candidate-type runtime observations.

    """

    name: str
    kind: ParamKind
    advertised_kinds: tuple[ParamKind, ...]
    has_default: bool
    keyword_valid: bool | None
    trials: tuple[TypeTrial, ...]


@dataclass(frozen=True, slots=True)
class TypeCallable:
    """Empirical runtime type index entry for one builtin callable.

    Attributes:
        method: Fully qualified builtin callable name.
        signature_source: Signature origin used for fuzzing.
        signature_variants: Corrected overload parameter variants.
        parameters: Merged empirical parameter observations.

    """

    method: str
    signature_source: str
    signature_variants: tuple[tuple[Param, ...], ...]
    parameters: tuple[TypeParameter, ...]


def _fuzz_type_name(value: FuzzValue) -> str:
    """Return the stable type label of one fuzz value.

    Args:
        value: Runtime type-fuzzing value factory record.

    Returns:
        The `str` result produced by the operation.

    """
    return value.type_name


class BuiltinTypeFuzzer:
    """Build an empirical argument-type index for builtin callables."""

    def __init__(self: Self, *, project: Project) -> None:
        """Initialize the fuzzer.

        Args:
            project: Project index providing stubs and runtime probes.

        """
        self.project: Project = project

    @staticmethod
    def targets() -> tuple[tuple[str, LiveObject], ...]:
        """Return directly exposed builtin callables and builtin type methods.

        Returns:
            Sorted unique `(qualified_name, callable)` pairs.

        """
        targets: dict[str, LiveObject] = {}
        builtins_namespace: dict[str, LiveObject] = vars(
            import_module(name="builtins"),
        )
        name: str
        value: LiveObject
        for name, value in builtins_namespace.items():
            if callable(value):
                targets[f"builtins.{name}"] = value
            if not isinstance(value, type):
                continue
            members: Mapping[str, object] = cast(
                typ="Mapping[str, object]",
                val=vars(value),
            )
            member_name: str
            member: object
            for member_name, member in members.items():
                if callable(member):
                    targets[f"builtins.{name}.{member_name}"] = member
        return tuple(sorted(targets.items(), key=lambda item: item[0]))

    @staticmethod
    def drop_receiver(
        *,
        params: tuple[Param, ...],
        bound: bool,
    ) -> tuple[Param, ...]:
        """Drop an already-bound self/cls parameter.

        Args:
            params: Signature parameters.
            bound: Whether a receiver is already supplied.

        Returns:
            Call-ready parameters.

        """
        return (
            params[1:]
            if bound and params and params[0].name in Constants.receiver_names
            else params
        )

    @staticmethod
    def record_json(record: TypeCallable) -> dict[str, LiveObject]:
        """Convert one callable record to JSON-compatible dictionaries.

        Args:
            record: Empirical callable record.

        Returns:
            JSON-compatible record.

        """
        parameter_json: dict[str, dict[str, LiveObject]] = {}
        parameter: TypeParameter
        for parameter in record.parameters:
            parameter_json[parameter.name] = parameter_to_json(
                parameter=parameter,
            )
        args_json: list[dict[str, LiveObject]] = []
        kwargs_json: list[dict[str, LiveObject]] = []
        for parameter in record.parameters:
            if parameter.kind in {"posonly", "poskw"}:
                args_json.append(parameter_json[parameter.name])
            if parameter.keyword_valid is True:
                kwargs_json.append(parameter_json[parameter.name])
        return {
            "method": record.method,
            "signature_source": record.signature_source,
            "args": args_json,
            "kwargs": kwargs_json,
        }

    def run(self: Self) -> dict[str, LiveObject]:
        """Fuzz every directly exposed builtin callable and type method.

        Returns:
            JSON-compatible empirical builtin signature index.

        """
        records: list[TypeCallable] = []
        method: str
        obj: LiveObject
        for method, obj in self.targets():
            record: TypeCallable | None = self.fuzz_callable(
                method=method,
                obj=obj,
            )
            if record is not None:
                records.append(record)
        corpus_types: list[str] = list(
            map(_fuzz_type_name, Constants.type_fuzz_values),
        )
        callables_json: list[dict[str, LiveObject]] = list(
            map(self.record_json, records),
        )
        keyword_mismatches: list[dict[str, LiveObject]] = []
        for record in records:
            parameter: TypeParameter
            for parameter in record.parameters:
                has_kw_kind: bool = False
                kind: ParamKind
                for kind in parameter.advertised_kinds:
                    if kind in {"poskw", "kwonly"}:
                        has_kw_kind = True
                        break
                if has_kw_kind and parameter.keyword_valid is False:
                    keyword_mismatches.append(
                        {
                            "method": record.method,
                            "parameter": parameter.name,
                            "advertised_kinds": list(
                                parameter.advertised_kinds,
                            ),
                            "runtime_kind": parameter.kind,
                        },
                    )
        return {
            "python_version": version,
            "executable": executable,
            "corpus_types": corpus_types,
            "callables": callables_json,
            "keyword_mismatches": keyword_mismatches,
        }

    def fuzz_callable(
        self: Self,
        *,
        method: str,
        obj: LiveObject,
    ) -> TypeCallable | None:
        """Fuzz one builtin callable.

        Args:
            method: Fully qualified builtin name.
            obj: Live callable.

        Returns:
            Empirical callable record, or None when no usable signature exists.

        """
        if not callable(obj) or not probeable(obj=obj):
            return None
        owner: LiveObject = getattr(obj, "__objclass__", None)
        _target: LiveObject
        bound: bool
        _target, bound = bind_probe(obj=obj)
        if isinstance(owner, type) and not bound:
            return None
        param_sets: tuple[tuple[Param, ...], ...]
        source: str
        param_sets, source = self.signature_sets(method=method, obj=obj)
        if not param_sets:
            return None
        corrected: list[tuple[Param, ...]] = []
        params: tuple[Param, ...]
        for params in param_sets:
            verified: tuple[Param, ...]
            _conclusive: bool
            verified, _conclusive = self.project.verify_params(
                obj=obj,
                params=params,
            )
            corrected.append(verified)
        return TypeCallable(
            method=method,
            signature_source=source,
            signature_variants=tuple(corrected),
            parameters=self.merge_parameters(
                obj=obj,
                advertised_sets=param_sets,
                param_sets=tuple(corrected),
            ),
        )

    def signature_sets(
        self: Self,
        *,
        method: str,
        obj: LiveObject,
    ) -> tuple[tuple[tuple[Param, ...], ...], str]:
        """Resolve runtime or typeshed parameter sets for one builtin.

        Args:
            method: Fully qualified builtin name.
            obj: Live callable.

        Returns:
            Parameter variants and their source label.

        """
        if not callable(obj):
            return self.stub_signature_sets(method=method), "typeshed"
        try:
            runtime: Sig = sig_from_inspect(
                name=method,
                resolved=signature(obj=obj),
            )
        except (TypeError, ValueError):
            return self.stub_signature_sets(method=method), "typeshed"
        return (
            self.normalize_bound(obj=obj, params=runtime.params),
        ), "inspect"

    def stub_signature_sets(
        self: Self,
        *,
        method: str,
    ) -> tuple[tuple[Param, ...], ...]:
        """Return call-ready parameter variants from typeshed.

        Args:
            method: Fully qualified builtin name.

        Returns:
            Zero or more call-ready parameter tuples.

        """
        resolved: Resolved = self.project.stubs.lookup(dotted=method)
        if resolved.kind == "function":
            function_params: list[tuple[Param, ...]] = list(
                map(
                    partial(self._drop_receiver, bound=resolved.bound),
                    resolved.sigs,
                ),
            )
            return tuple(function_params)
        if resolved.kind != "stubclass" or not isinstance(
            resolved.stub,
            StubClass,
        ):
            return ()
        ctor_params: list[tuple[Param, ...]] = list(
            map(partial(self._drop_receiver, bound=True), resolved.stub.ctors),
        )
        return tuple(ctor_params)

    def normalize_bound(
        self: Self,
        *,
        obj: LiveObject,
        params: tuple[Param, ...],
    ) -> tuple[Param, ...]:
        """Normalize inspect parameters for a descriptor bound by probing.

        Args:
            obj: Live callable or method descriptor.
            params: inspect-derived parameters.

        Returns:
            Call-ready parameters.

        """
        _target: LiveObject
        bound: bool
        _target, bound = bind_probe(obj=obj)
        return self.drop_receiver(params=params, bound=bound)

    def merge_parameters(
        self: Self,
        *,
        obj: LiveObject,
        advertised_sets: tuple[tuple[Param, ...], ...],
        param_sets: tuple[tuple[Param, ...], ...],
    ) -> tuple[TypeParameter, ...]:
        """Merge per-overload fuzz results by parameter name.

        Args:
            obj: Live callable.
            advertised_sets: Source-signature overload variants.
            param_sets: Corrected overload variants.

        Returns:
            Merged parameter records in first-seen order.

        """
        names: list[str] = []
        params: tuple[Param, ...]
        param: Param
        for params in param_sets:
            for param in params:
                if (
                    param.kind not in {"vararg", "varkw"}
                    and param.name not in names
                ):
                    names.append(param.name)
        merged: list[TypeParameter] = list(
            map(
                partial(
                    self.merge_parameter,
                    obj=obj,
                    advertised_sets=advertised_sets,
                    param_sets=param_sets,
                ),
                names,
            ),
        )
        return tuple(merged)

    def merge_parameter(
        self: Self,
        name: str,
        *,
        obj: LiveObject,
        advertised_sets: tuple[tuple[Param, ...], ...],
        param_sets: tuple[tuple[Param, ...], ...],
    ) -> TypeParameter:
        """Fuzz and merge one named parameter across overload variants.

        Args:
            name: Parameter to fuzz.
            obj: Live callable.
            advertised_sets: Source-signature overload variants.
            param_sets: Corrected overload variants.

        Returns:
            Merged empirical parameter record.

        """
        candidates: list[tuple[tuple[Param, ...], int, Param]] = []
        params: tuple[Param, ...]
        index: int
        param: Param
        for params in param_sets:
            for index, param in enumerate(iterable=params):
                if param.name != name or param.kind in {"vararg", "varkw"}:
                    continue
                candidates.append((params, index, param))
        representative: Param = candidates[0][2]
        kinds: list[ParamKind] = []
        for params in advertised_sets:
            for param in params:
                if param.name != name:
                    continue
                kinds.append(param.kind)
        advertised_kinds: tuple[ParamKind, ...] = tuple(dict.fromkeys(kinds))
        trials: list[TypeTrial] = list(
            map(
                partial(_fuzz_value_trials, obj=obj, candidates=candidates),
                Constants.type_fuzz_values,
            ),
        )
        keyword_verdicts: list[bool | None] = list(
            map(partial(self._keyword_verdict, obj=obj), candidates),
        )
        has_default: bool = self._any_default(candidates=candidates)
        any_true: bool = True in keyword_verdicts
        all_false: bool = self._all_false(verdicts=keyword_verdicts)
        return TypeParameter(
            name=name,
            kind=representative.kind,
            advertised_kinds=advertised_kinds,
            has_default=has_default,
            keyword_valid=(
                True if any_true else (False if all_false else None)
            ),
            trials=tuple(trials),
        )

    @staticmethod
    def _any_default(
        *,
        candidates: list[tuple[tuple[Param, ...], int, Param]],
    ) -> bool:
        """Report whether any candidate parameter has a default.

        Args:
            candidates: ``(params, index, param)`` candidate tuples.

        Returns:
            The `bool` result produced by the operation.

        """
        return any(map(_candidate_has_default, candidates))

    @staticmethod
    def _all_false(*, verdicts: list[bool | None]) -> bool:
        """Report whether every keyword verdict is ``False``.

        Args:
            verdicts: Keyword-acceptance probe results.

        Returns:
            The `bool` result produced by the operation.

        """
        return all(verdict is False for verdict in verdicts)

    def _drop_receiver(
        self: Self,
        sig: Sig,
        *,
        bound: bool,
    ) -> tuple[Param, ...]:
        """Return call-ready parameters for one resolved signature.

        Args:
            sig: Source signature.
            bound: Whether the receiver is already supplied.

        Returns:
            Parameters with any bound receiver dropped.

        """
        return self.drop_receiver(params=sig.params, bound=bound)

    def _keyword_verdict(
        self: Self,
        candidate: tuple[tuple[Param, ...], int, Param],
        *,
        obj: LiveObject,
    ) -> bool | None:
        """Probe or derive the keyword verdict for one candidate.

        Args:
            candidate: ``(params, index, param)`` candidate tuple.
            obj: Live callable under test.

        Returns:
            Probe result, or the derived keyword-only verdict.

        """
        return (
            self.project.probe(
                obj=obj,
                params=candidate[0],
                index=candidate[1],
            )
            if candidate[2].kind == "poskw"
            else candidate[2].kind == "kwonly"
        )


def fuzz_trial(
    *,
    obj: LiveObject,
    params: tuple[Param, ...],
    index: int,
    value: LiveObject,
    type_name: str,
) -> TypeTrial:
    """Execute one isolated-by-fresh-state candidate-type trial.

    Args:
        obj: Live builtin callable.
        params: Call-ready signature parameters.
        index: Parameter index being fuzzed.
        value: Candidate runtime value.
        type_name: Stable candidate type label.

    Returns:
        Runtime observation for the candidate type.

    """
    target: LiveObject
    _bound: bool
    target, _bound = bind_probe(obj=obj)
    if not callable(target):
        return TypeTrial(type_name=type_name, observation="unavailable")
    args: list[LiveObject] = []
    kwargs: dict[str, LiveObject] = {}
    candidate: Param = params[index]
    param_index: int
    param: Param
    for param_index, param in enumerate(iterable=params):
        if param.kind in {"vararg", "varkw"}:
            continue
        selected: LiveObject = (
            value if param_index == index else probe_value(name=param.name)
        )
        required: bool = param_index == index or not param.has_default
        if not required:
            continue
        if param.kind == "posonly" or (
            param_index < index
            and candidate.kind == "posonly"
            and param.kind == "poskw"
        ):
            args.append(selected)
        else:
            kwargs[param.name] = selected
    exc: Exception
    try:
        _ = consume(value=target(*args, **kwargs))
    except TypeError as exc:
        message: str = str(object=exc)
        if (
            candidate.kind in {"poskw", "kwonly"}
            and kwarg_verdict(message=message, param=candidate.name) is False
        ):
            return TypeTrial(
                type_name=type_name,
                observation="rejected_keyword",
                exception_type=type(exc).__name__,
                exception_message=message,
            )
        return TypeTrial(
            type_name=type_name,
            observation="rejected_type",
            exception_type=type(exc).__name__,
            exception_message=message,
        )
    except (
        ArithmeticError,
        AssertionError,
        AttributeError,
        BufferError,
        EOFError,
        ImportError,
        IndexError,
        KeyError,
        LookupError,
        MemoryError,
        NameError,
        NotImplementedError,
        OSError,
        RecursionError,
        RuntimeError,
        StopAsyncIteration,
        StopIteration,
        SystemError,
        UnicodeError,
        ValueError,
    ) as exc:
        return TypeTrial(
            type_name=type_name,
            observation="accepted_runtime",
            exception_type=type(exc).__name__,
            exception_message=str(object=exc),
        )
    return TypeTrial(type_name=type_name, observation="success")


def _candidate_has_default(
    candidate: tuple[tuple[Param, ...], int, Param],
) -> bool:
    """Report whether a candidate tuple's parameter has a default.

    Args:
        candidate: ``(params, index, param)`` candidate tuple.

    Returns:
        Whether the candidate parameter declares a default.

    """
    return candidate[2].has_default


def merge_trials(*, type_name: str, trials: list[TypeTrial]) -> TypeTrial:
    """Merge overload observations for one candidate type.

    Args:
        type_name: Candidate type label.
        trials: Per-overload observations.

    Returns:
        Strongest observed acceptance result.

    """
    rank: dict[str, int] = {
        "success": 5,
        "accepted_runtime": 4,
        "rejected_type": 3,
        "rejected_keyword": 2,
        "unavailable": 1,
    }
    return (
        max(trials, key=lambda trial: rank[trial.observation])
        if trials
        else TypeTrial(type_name=type_name, observation="unavailable")
    )


def _trial_json(trial: TypeTrial) -> dict[str, LiveObject]:
    """Convert one runtime trial to a JSON-compatible mapping.

    Args:
        trial: Runtime observation for one candidate type.

    Returns:
        JSON-compatible trial mapping.

    """
    return {
        "type": trial.type_name,
        "observation": trial.observation,
        "exception_type": trial.exception_type,
        "exception_message": trial.exception_message,
    }


def _candidate_trial(
    factory: Callable[[], LiveObject],
    *,
    candidate: tuple[tuple[Param, ...], int, Param],
    obj: LiveObject,
    type_name: str,
) -> TypeTrial:
    """Run one fuzz trial for a candidate/factory pair.

    Args:
        factory: Fresh value factory for the candidate type.
        candidate: ``(params, index, param)`` candidate tuple.
        obj: Live callable under test.
        type_name: Stable candidate type label.

    Returns:
        Runtime observation for the pair.

    """
    return fuzz_trial(
        obj=obj,
        params=candidate[0],
        index=candidate[1],
        value=factory(),
        type_name=type_name,
    )


def _fuzz_value_trials(
    fuzz_value: FuzzValue,
    *,
    obj: LiveObject,
    candidates: list[tuple[tuple[Param, ...], int, Param]],
) -> TypeTrial:
    """Run and merge every candidate/factory trial for one type.

    Args:
        fuzz_value: Runtime type-fuzzing value factory record.
        obj: Live callable under test.
        candidates: ``(params, index, param)`` candidate tuples.

    Returns:
        Strongest merged observation across overloads and factories.

    """
    value_trials: list[TypeTrial] = []
    candidate: tuple[tuple[Param, ...], int, Param]
    for candidate in candidates:
        value_trials.extend(
            map(
                partial(
                    _candidate_trial,
                    candidate=candidate,
                    obj=obj,
                    type_name=fuzz_value.type_name,
                ),
                fuzz_value.factories,
            ),
        )
    return merge_trials(type_name=fuzz_value.type_name, trials=value_trials)


def parameter_to_json(*, parameter: TypeParameter) -> dict[str, LiveObject]:
    """Convert empirical parameter information to JSON-compatible data.

    Args:
        parameter: Empirical parameter record.

    Returns:
        JSON-compatible parameter mapping.

    """
    rejected_names: list[str] = []
    parser_accepted_names: list[str] = []
    accepted_types: list[str] = []
    trial: TypeTrial
    for trial in parameter.trials:
        if trial.observation == "success":
            accepted_types.append(trial.type_name)
            parser_accepted_names.append(trial.type_name)
        elif trial.observation == "accepted_runtime":
            parser_accepted_names.append(trial.type_name)
        elif trial.observation == "rejected_type":
            rejected_names.append(trial.type_name)
    rejected: tuple[str, ...] = tuple(rejected_names)
    parser_accepted: tuple[str, ...] = tuple(parser_accepted_names)
    has_kw_kind: bool = False
    kind: ParamKind
    for kind in parameter.advertised_kinds:
        if kind in {"poskw", "kwonly"}:
            has_kw_kind = True
            break
    trials_json: list[dict[str, LiveObject]] = list(
        map(_trial_json, parameter.trials),
    )
    return {
        "name": parameter.name,
        "kind": parameter.kind,
        "advertised_kinds": list(parameter.advertised_kinds),
        "has_default": parameter.has_default,
        "keyword_valid": parameter.keyword_valid,
        "keyword_mismatch": (has_kw_kind and parameter.keyword_valid is False),
        "accepted_types": accepted_types,
        "parser_accepted_types": list(parser_accepted),
        "rejected_types": list(rejected),
        "trials": trials_json,
    }


def _positional_capable(param: Param) -> bool:
    """Return whether a parameter can bind positionally or by keyword.

    Args:
        param: Signature parameter.

    Returns:
        Whether the parameter accepts a positional argument.

    """
    return param.kind in {"posonly", "poskw"}


def _overload_name(param: Param) -> str:
    """Return the overload-candidate label for one parameter.

    Args:
        param: Conflicting candidate parameter.

    Returns:
        Ambiguous-overload candidate label.

    """
    return f"overload:{param.name}"


def arity_fits(*, params: tuple[Param, ...], arity: int) -> bool:
    """Check whether a call arity can bind to a parameter tuple.

    Args:
        params: Parameter tuple of one signature.
        arity: Number of positional arguments at the call site.

    Returns:
        The `bool` result produced by the operation.

    """
    bindable: int = 0
    param: Param
    for param in params:
        if param.kind in {"posonly", "poskw"}:
            bindable += 1
    has_vararg: bool = False
    for param in params:
        if param.kind == "vararg":
            has_vararg = True
            break
    return arity <= bindable or has_vararg


def parse_args(*, arguments: tuple[str, ...] | None = None) -> Namespace:
    """Parse args.

    Args:
        arguments: Arguments.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Report positional arguments that should be keywords, forbidden "
            "bare imports, and missing explicit type hints."
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--root",
            type=Path,
            default=Path(__file__).resolve().parents[3],
            help=("repository root (default: directory containing exactus/)"),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--output",
            type=Path,
            default=None,
            help="report path (default: <root>/POSITIONAL_ARGS_EXACTUS.md)",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--allow-bare-import",
            action="append",
            default=sorted(BareImportExactusor.DEFAULT_ALLOWED),
            metavar="MODULE",
            help=(
                "permit MODULE only as a standalone unaliased "
                "`import MODULE`; repeatable (default: pytest)"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--python",
            default=None,
            metavar="INTERPRETER",
            help=(
                "interpreter or virtual-environment directory whose "
                "version/platform steer inference; defaults to the "
                "project .venv, then requires-python probes, then self"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--heuristics-output",
            type=Path,
            default=None,
            help=(
                "builtin type-fuzz heuristics JSON path (default: "
                "<root>/heuristics.json)"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--context-lines",
            type=context_lines,
            default=SnippetLimits.default_context,
            metavar="N",
            help=(
                "source lines captured around each finding line "
                "(default: %(default)s)"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--capability-index",
            type=Path,
            default=None,
            help=(
                "canonical capability index to consume "
                "(default: CAPABILITY_INDEX.json beside this module "
                "when present)"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--write-capability-index",
            type=Path,
            default=None,
            help=(
                "regenerate the canonical capability index at PATH "
                "from this interpreter; live resolution is used and "
                "any committed index is ignored"
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--dry",
            "--dry-run",
            action="store_true",
            dest="dry",
            help="report deterministic repairs without modifying sources",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "-s",
            "--strict",
            action="store_true",
            help=(
                "also report bindings that cannot carry an annotation "
                "(loop, with, except, match, and comprehension targets); "
                "without it only plain `name = value` assignments are "
                "reported"
            ),
        ),
    )
    return parser.parse_args(args=arguments)


def collect_findings(
    *,
    exactusors: list[CallExactusor],
) -> tuple[list[Finding], list[AmbiguousCall]]:
    """Flatten per-module findings and ambiguous calls.

    Args:
        exactusors: Completed per-module call exactusors.

    Returns:
        Flat findings and ambiguous-call lists in exactus order.

    """
    findings: list[Finding] = []
    ambiguous: list[AmbiguousCall] = []
    exactusor: CallExactusor
    for exactusor in exactusors:
        findings.extend(exactusor.findings)
        ambiguous.extend(exactusor.ambiguous)
    return findings, ambiguous


@dataclass(frozen=True, slots=True)
class SourceEdit:
    """One validated source-text replacement used by auto-healing.

    Attributes:
        start: Inclusive character offset.
        end: Exclusive character offset.
        replacement: Replacement source text.
        kind: Edit classification label reported to users.
        line: One-based source line of the edit.
        column: One-based source column of the edit.
        original: Source text replaced by the edit.
        reported_replacement: Replacement text shown in diagnostics,
            which may differ from the applied ``replacement``.

    """

    start: int
    end: int
    replacement: str
    kind: str
    line: int
    column: int
    original: str
    reported_replacement: str


def _source_offset(*, source: str, line: int, column: int) -> int:
    """Translate an AST UTF-8 byte position to a character offset.

    Args:
        source: Complete source text.
        line: One-based source line.
        column: Zero-based UTF-8 byte column.

    Returns:
        Character offset into ``source``.

    """
    lines: list[str] = source.splitlines(keepends=True)
    prefix: bytes = lines[line - 1].encode(encoding="utf-8")[:column]
    return sum(len(item) for item in lines[: line - 1]) + len(
        prefix.decode(encoding="utf-8"),
    )


def _apply_source_edits(*, source: str, edits: Sequence[SourceEdit]) -> str:
    """Apply non-overlapping edits from right to left.

    Args:
        source: Original source text.
        edits: Validated replacements in original-source coordinates.

    Returns:
        Rewritten source.

    Raises:
        ValueError: When edits overlap.

    """
    ordered: list[SourceEdit] = sorted(
        edits,
        key=lambda item: (item.start, item.end),
    )
    if any(left.end > right.start for left, right in pairwise(ordered)):
        msg: str = "auto-heal source edits overlap"
        raise ValueError(msg)
    result: str = source
    for edit in reversed(ordered):
        result = result[: edit.start] + edit.replacement + result[edit.end :]
    return result


def _keyword_heal_edits(
    *,
    source: str,
    tree: Module,
    findings: Sequence[Finding],
) -> list[SourceEdit]:
    """Build safe insertions for positional arguments with known parameters.

    Args:
        source: Complete file source.
        tree: Parsed source tree.
        findings: Keyword-call findings for this file.

    Returns:
        Keyword-prefix insertions whose call and argument match uniquely.

    """
    calls: list[Call] = [
        node for node in walk(node=tree) if isinstance(node, Call)
    ]
    edits: list[SourceEdit] = []
    for finding in findings:
        matches: list[Call] = [
            node
            for node in calls
            if node.lineno == finding.line
            and unparse(ast_obj=node.func) == finding.callee
            and finding.index < len(node.args)
            and unparse(ast_obj=node.args[finding.index]) == finding.argument
            and not isinstance(node.args[finding.index], Starred)
        ]
        if len(matches) != 1:
            continue
        argument: expr = matches[0].args[finding.index]
        start: int = _source_offset(
            source=source,
            line=argument.lineno,
            column=argument.col_offset,
        )
        edits.append(
            SourceEdit(
                start=start,
                end=start,
                replacement=f"{finding.param}=",
                kind="keyword-argument",
                line=argument.lineno,
                column=argument.col_offset + 1,
                original=finding.argument,
                reported_replacement=(f"{finding.param}={finding.argument}"),
            ),
        )
    return edits


def _bare_import_heal_edits(
    *,
    source: str,
    tree: Module,
    findings: Sequence[BareImportFinding],
) -> list[SourceEdit]:
    """Build complete edits for statically safe single-module imports.

    Args:
        source: Complete file source.
        tree: Parsed source tree.
        findings: Bare-import findings for this file.

    Returns:
        Import and use-site replacements that are safe to apply together.

    """
    imports: list[Import] = [
        node for node in walk(node=tree) if isinstance(node, Import)
    ]
    edits: list[SourceEdit] = []
    for finding in findings:
        if not finding.safe or not finding.suggestion:
            continue
        matches: list[Import] = [
            node
            for node in imports
            if node.lineno == finding.line
            and node.col_offset == finding.column - 1
            and len(node.names) == 1
            and node.names[0].name == finding.module
        ]
        if len(matches) != 1:
            continue
        node: Import = matches[0]
        if node.end_lineno is None or node.end_col_offset is None:
            continue
        local: list[SourceEdit] = [
            SourceEdit(
                start=_source_offset(
                    source=source,
                    line=node.lineno,
                    column=node.col_offset,
                ),
                end=_source_offset(
                    source=source,
                    line=node.end_lineno,
                    column=node.end_col_offset,
                ),
                replacement=finding.suggestion,
                kind="bare-import",
                line=node.lineno,
                column=node.col_offset + 1,
                original=source[
                    _source_offset(
                        source=source,
                        line=node.lineno,
                        column=node.col_offset,
                    ) : _source_offset(
                        source=source,
                        line=node.end_lineno,
                        column=node.end_col_offset,
                    )
                ],
                reported_replacement=finding.suggestion,
            ),
        ]
        valid: bool = True
        for line, column, original, replacement in finding.replacements:
            start: int = _source_offset(
                source=source,
                line=line,
                column=column - 1,
            )
            if source[start : start + len(original)] != original:
                valid = False
                break
            local.append(
                SourceEdit(
                    start=start,
                    end=start + len(original),
                    replacement=replacement,
                    kind="bare-import-use",
                    line=line,
                    column=column,
                    original=original,
                    reported_replacement=replacement,
                ),
            )
        if valid:
            edits.extend(local)
    return edits


def _source_edit_json(
    *,
    path: Path,
    root: Path,
    edit: SourceEdit,
    applied: bool,
) -> JsonValue:
    """Return one validated auto-heal source edit for the report.

    Args:
        path: Edited source path.
        root: Repository root.
        edit: Validated source edit.
        applied: Whether the source file was written.

    Returns:
        JSON-compatible auto-fix record.

    """
    return {
        "file": str(object=path.relative_to(root)),
        "line": edit.line,
        "column": edit.column,
        "kind": edit.kind,
        "original": edit.original,
        "replacement": edit.reported_replacement,
        "status": "fixed" if applied else "would-fix",
    }


def _heal_sources(
    *,
    root: Path,
    paths: Sequence[Path],
    positional: Sequence[Finding],
    bare_imports: Sequence[BareImportFinding],
    dry_run: bool,
) -> tuple[tuple[Path, ...], list[JsonValue]]:
    """Validate deterministic repairs and optionally apply them.

    Args:
        root: Repository root used for report-relative paths.
        paths: Active Python source inventory.
        positional: Resolved keyword-call findings.
        bare_imports: Bare-import findings, including safety metadata.
        dry_run: Whether to report edits without writing source files.

    Returns:
        Changed paths and validated auto-fix report records.

    """
    changed: list[Path] = []
    fixes: list[JsonValue] = []
    for path in paths:
        try:
            source: str = path.read_text(encoding="utf-8")
            tree: Module = parse(source=source, filename=str(object=path))
        except (OSError, SyntaxError, ValueError):
            continue
        edits: list[SourceEdit] = _keyword_heal_edits(
            source=source,
            tree=tree,
            findings=tuple(item for item in positional if item.path == path),
        )
        edits.extend(
            _bare_import_heal_edits(
                source=source,
                tree=tree,
                findings=tuple(
                    item for item in bare_imports if item.path == path
                ),
            ),
        )
        if not edits:
            continue
        try:
            healed: str = _apply_source_edits(source=source, edits=edits)
            _ = parse(source=healed, filename=str(object=path))
        except (SyntaxError, ValueError):
            continue
        if healed == source:
            continue
        if not dry_run:
            try:
                path.write_text(data=healed, encoding="utf-8")
            except OSError:
                continue
            changed.append(path)
            trace(step=f"auto-heal: {path}", depth=2)
        fixes.extend(
            _source_edit_json(
                path=path,
                root=root,
                edit=edit,
                applied=not dry_run,
            )
            for edit in edits
        )
    return tuple(changed), fixes


def _finding_json(item: Finding, *, root: Path) -> JsonValue:
    """Convert one positional-call finding to JSON-compatible data.

    Args:
        item: Recorded positional-call finding.
        root: Repository root directory.

    Returns:
        JSON-compatible finding mapping.

    """
    return {
        "file": str(object=item.path.relative_to(root)),
        "line": item.line,
        "callee": item.callee,
        "parameter": item.param,
        "index": item.index,
        "argument": item.argument,
        "confidence": item.confidence,
        "suggestion": item.suggestion,
    }


def _bare_import_json(item: BareImportFinding, *, root: Path) -> JsonValue:
    """Convert one bare-import finding to JSON-compatible data.

    Args:
        item: Recorded bare-import finding.
        root: Repository root directory.

    Returns:
        JSON-compatible finding mapping.

    """
    replacements: list[JsonValue] = []
    replacement: tuple[int, int, str, str]
    for replacement in item.replacements:
        row: list[JsonValue] = []
        row.extend(replacement)
        replacements.append(row)
    result: dict[str, JsonValue] = {
        "file": str(object=item.path.relative_to(root)),
        "line": item.line,
        "column": item.column,
        "module": item.module,
        "bound": item.bound,
        "safe": item.safe,
        "suggestion": item.suggestion,
        "replacements": replacements,
        "reason": item.reason,
    }
    return result


def _type_hint_json(item: TypeHintFinding, *, root: Path) -> JsonValue:
    """Convert one missing-type-hint finding to JSON-compatible data.

    Args:
        item: Recorded missing-annotation finding.
        root: Repository root directory.

    Returns:
        JSON-compatible finding mapping.

    """
    return {
        "file": str(object=item.path.relative_to(root)),
        "line": item.line,
        "column": item.column,
        "kind": item.kind,
        "name": item.name,
        "scope": item.scope,
        "suggestion": item.suggestion,
        "reason": item.reason,
    }


def _ambiguous_json(item: AmbiguousCall, *, root: Path) -> JsonValue:
    """Convert one ambiguous-call record to JSON-compatible data.

    Args:
        item: Recorded ambiguous call.
        root: Repository root directory.

    Returns:
        JSON-compatible call mapping.

    """
    return {
        "file": str(object=item.path.relative_to(root)),
        "line": item.line,
        "callee": item.callee,
        "candidates": list(item.candidates),
    }


def _unresolved_call_json(item: UnresolvedCall, *, root: Path) -> JsonValue:
    """Convert one unresolved call site to JSON-compatible data.

    Args:
        item: Recorded unresolved call site.
        root: Repository root directory.

    Returns:
        JSON-compatible call-site mapping.

    """
    return {
        "file": str(object=item.path.relative_to(root)),
        "line": item.line,
        "column": item.column,
        "callee": item.callee,
        "reason": item.reason,
    }


def _report_scope(
    *,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
) -> JsonValue:
    """Return the path filters recorded in the report scope.

    Args:
        includes: Include globs the caller applied.
        excludes: Exclude globs the caller applied.

    Returns:
        ``include`` and ``exclude`` globs; the directories source
        discovery always skips are added to ``exclude``.

    """
    skipped: tuple[str, ...] = tuple(
        f"**/{name}/**" for name in sorted(Constants.skip_dirs)
    )
    return {
        "include": list(includes),
        "exclude": list(dict.fromkeys((*excludes, *skipped))),
    }


def _source_fingerprints(*, paths: list[Path]) -> dict[Path, str | None]:
    """Hash source snapshots used during speculative dependency overlap.

    Args:
        paths: Python source files in the current analysis inventory.

    Returns:
        Content hashes keyed by path, with ``None`` for vanished files.

    """
    fingerprints: dict[Path, str | None] = {}
    for path in paths:
        try:
            fingerprints[path] = sha256(data=path.read_bytes()).hexdigest()
        except OSError:
            fingerprints[path] = None
    return fingerprints


def _scan_sources(
    *,
    source_paths: list[Path],
    project: Project,
    allowed: frozenset[str],
    strict: bool,
) -> tuple[list[BareImportFinding], list[TypeHintFinding], tuple[int, int]]:
    """Exactus every source file for bare imports and missing hints.

    Args:
        source_paths: Python files in scope.
        project: Repository index providing reusable parsed ASTs.
        allowed: Modules permitted as bare imports.
        strict: Also report bindings that cannot carry an annotation.

    Returns:
        Bare-import findings, missing-hint findings, and the functions and
        parameters whose annotations were checked.

    """
    bare_imports: list[BareImportFinding] = []
    type_hints: list[TypeHintFinding] = []
    functions_checked: int = 0
    parameters_checked: int = 0
    lanes: BoundedLaneProgress = BoundedLaneProgress(
        total=len(source_paths),
        step="exactusing imports and hints",
        span=(0.3, 0.5),
    )
    source_path: Path
    for source_path in source_paths:
        source_bare, source_hints, source_checked = _scan_source_lane(
            source_path=source_path,
            allowed=allowed,
            strict=strict,
            progress=lanes,
            tree=(
                project.by_path[source_path].tree
                if source_path in project.by_path
                else None
            ),
        )
        bare_imports.extend(source_bare)
        type_hints.extend(source_hints)
        functions_checked += source_checked[0]
        parameters_checked += source_checked[1]
    return bare_imports, type_hints, (functions_checked, parameters_checked)


def _scan_source_lane(
    *,
    source_path: Path,
    allowed: frozenset[str],
    strict: bool,
    progress: BoundedLaneProgress,
    tree: Module | None = None,
) -> tuple[
    tuple[BareImportFinding, ...],
    tuple[TypeHintFinding, ...],
    tuple[int, int],
]:
    """Scan one source within a cooperative file activity.

    Args:
        source_path: Python source file.
        allowed: Modules permitted as bare imports.
        strict: Whether non-annotatable bindings are findings.
        progress: Shared task-level lane progress.
        tree: Pre-parsed module reused instead of re-reading the file.

    Returns:
        Findings and checked callable/parameter counts.

    """
    error: str | None = None
    try:
        bare: tuple[BareImportFinding, ...] = BareImportExactusor(
            path=source_path,
            allowed=allowed,
            tree=tree,
        ).exactus()
        hint_exactusor: TypeHintExactusor = TypeHintExactusor(
            path=source_path,
            strict=strict,
            tree=tree,
        )
        hints: tuple[TypeHintFinding, ...] = hint_exactusor.exactus()
        checked: tuple[int, int] = (
            hint_exactusor.functions_checked,
            hint_exactusor.parameters_checked,
        )
    except Exception as exception:
        error = str(object=exception)
        raise
    else:
        return bare, hints, checked
    finally:
        _ = progress.finish(item=str(object=source_path), error=error)


def _resolve_module_lane(
    *,
    project: Project,
    module: ModuleInfo,
    progress: BoundedLaneProgress,
) -> CallExactusor:
    """Resolve one indexed module within a cooperative file activity.

    Args:
        project: Shared read-mostly repository index.
        module: Module to analyze.
        progress: Shared task-level lane progress.

    Returns:
        Completed call analyzer.

    """
    error: str | None = None
    try:
        exactusor: CallExactusor = CallExactusor(
            project=project,
            module=module,
        )
        exactusor.exactus()
    except Exception as exception:
        error = str(object=exception)
        raise
    else:
        return exactusor
    finally:
        _ = progress.finish(item=str(object=module.path), error=error)


def _legacy_payload(
    *,
    run: AnalysisRun,
    scope: JsonValue,
) -> dict[str, JsonValue]:
    """Build the legacy report payload the normalized report extends.

    Args:
        run: Stable analysis snapshot.
        scope: Include/exclude globs recorded as ``filters``.

    Returns:
        ``summary``, the per-category finding lists, the unresolved
        callees per file and per call site, the files that failed to
        parse, and the path filters.

    """
    project: Project = run.project
    exactusors: list[CallExactusor] = run.exactusors
    checked: tuple[int, int] = run.checked
    auto_fixes: list[JsonValue] = run.auto_fixes
    root: Path = project.root
    bare_imports: list[BareImportFinding]
    type_hints: list[TypeHintFinding]
    bare_imports, type_hints = run.bare_imports, run.type_hints
    findings: list[Finding]
    ambiguous: list[AmbiguousCall]
    findings, ambiguous = collect_findings(exactusors=exactusors)
    findings_json: list[JsonValue] = list(
        map(partial(_finding_json, root=root), findings),
    )
    bare_imports_json: list[JsonValue] = list(
        map(partial(_bare_import_json, root=root), bare_imports),
    )
    type_hints_json: list[JsonValue] = list(
        map(partial(_type_hint_json, root=root), type_hints),
    )
    ambiguous_json: list[JsonValue] = list(
        map(partial(_ambiguous_json, root=root), ambiguous),
    )
    unresolved_json: list[JsonValue] = []
    sites_json: list[JsonValue] = []
    call_sites: int = 0
    resolved_call_sites: int = 0
    exempt_call_sites: int = 0
    unresolved_exactusor: CallExactusor
    for unresolved_exactusor in exactusors:
        call_sites += unresolved_exactusor.calls
        resolved_call_sites += unresolved_exactusor.resolved_calls
        exempt_call_sites += unresolved_exactusor.exempt_calls
        sites_json.extend(
            map(
                partial(_unresolved_call_json, root=root),
                unresolved_exactusor.unresolved_calls,
            ),
        )
        callee: str
        count: int
        for callee, count in sorted(unresolved_exactusor.unresolved.items()):
            unresolved_json.append(
                {
                    "file": str(
                        object=unresolved_exactusor.module.path.relative_to(
                            root,
                        ),
                    ),
                    "callee": callee,
                    "sites": count,
                },
            )
    return {
        "root": str(object=root),
        "summary": {
            "python_files": len(exactusors) + len(project.parse_failures),
            "parse_failures": len(project.parse_failures),
            "positional_findings": len(findings),
            "bare_import_findings": len(bare_imports),
            "missing_type_hints": len(type_hints),
            "ambiguous_calls": len(ambiguous),
            "unresolved_callees": len(unresolved_json),
            "unresolved_call_sites": len(sites_json),
            "call_sites": call_sites,
            "resolved_call_sites": resolved_call_sites,
            "exempt_call_sites": exempt_call_sites,
            "functions_checked": checked[0],
            "parameters_checked": checked[1],
        },
        "filters": scope,
        "auto_fixes": auto_fixes,
        "findings": findings_json,
        "bare_imports": bare_imports_json,
        "type_hints": type_hints_json,
        "ambiguous": ambiguous_json,
        "unresolved": unresolved_json,
        "unresolved_sites": sites_json,
        "parse_failure_files": [
            str(object=failed.relative_to(root))
            for failed in project.parse_failures
        ],
    }


def _write_report_bundle(
    *,
    data: dict[str, JsonValue],
    output: Path,
    root: Path,
    context: int,
) -> None:
    """Write the markdown/json/web report bundle.

    Args:
        data: Legacy payload rendered by the report module.
        output: Markdown destination; json/web derive from its name.
        root: Project root used for finding excerpts.
        context: Snippet lines embedded around each finding.

    """
    trace(step="stage: report", depth=1)
    _ = consume(
        value=ReportBundle.write(
            paths=ReportPaths(
                markdown=output,
                json=output.with_suffix(suffix=".json"),
                web=output.with_name(name=f"{output.stem}_web"),
            ),
            analyzer="static",
            title="Python Call, Import, and Typing Exactus",
            markdown="",
            data=with_excerpts(
                payload=report_data(report=data),
                root=root,
                context=context,
            ),
        ),
    )
    trace(step=f"report: bundle written — {output.name}", depth=2)


def _write_heuristics(*, heuristics_output: Path, project: Project) -> None:
    """Write the builtin type-fuzz heuristics artifact.

    Args:
        heuristics_output: Destination JSON file.
        project: Resolved project the fuzzer inspects.

    """
    heuristics_output.parent.mkdir(parents=True, exist_ok=True)
    file: TextIO
    with heuristics_output.open(mode="w", encoding="utf-8") as file:
        dump(
            obj=BuiltinTypeFuzzer(project=project).run(),
            fp=file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    trace(step=f"heuristics: written — {heuristics_output.name}", depth=2)


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    """Stable kwargs/type-hints analysis snapshot.

    Attributes:
        project: Resolved project for the stable source snapshot.
        exactusors: Per-module call analyzers.
        bare_imports: Remaining bare-import findings.
        type_hints: Remaining explicit-type-hint findings.
        checked: Function and parameter check counters.
        auto_fixes: Validated source edits applied or proposed.

    """

    project: Project
    exactusors: list[CallExactusor]
    bare_imports: list[BareImportFinding]
    type_hints: list[TypeHintFinding]
    checked: tuple[int, int]
    auto_fixes: list[JsonValue]


def _load_capability_index(
    *,
    write_index: Path | None,
    index_path: Path | None,
) -> CapabilityIndex | None:
    """Load the configured capability index when analysis should consume it.

    Args:
        write_index: Optional destination for a newly generated index.
        index_path: Optional existing index to consume.

    Returns:
        Loaded capability index, or ``None`` when unavailable or being rebuilt.

    """
    if (
        write_index is not None
        or index_path is None
        or not index_path.is_file()
    ):
        return None
    capability: CapabilityIndex = CapabilityIndex.load(path=index_path)
    trace(
        step=(
            f"capability index: loaded {index_path.name} — "
            f"{len(capability.sigs)} signatures"
        ),
        depth=2,
    )
    return capability


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """Inputs steering one kwargs/type-hints analysis run.

    Attributes:
        root: Project root.
        path_filter: Optional source-discovery predicate.
        source_paths: Optional caller-supplied source inventory.
        capability: Optional callable capability index.
        allowed: Bare-import exemptions.
        strict: Whether strict type-hint analysis is enabled.
        dry_run: Whether deterministic repairs are report-only.
        python: Configured interpreter for version/platform facts.

    """

    root: Path
    path_filter: Callable[[Path], bool] | None
    source_paths: Sequence[Path] | None
    capability: CapabilityIndex | None
    allowed: frozenset[str]
    strict: bool
    dry_run: bool
    python: str | None


def _analyze_until_stable(*, request: AnalysisRequest) -> AnalysisRun:
    """Analyze, heal, and rebuild until the source inventory is stable.

    Args:
        request: Scope, indexes and behavior flags for the analysis.

    Returns:
        Analysis results for a stable post-healing source snapshot.

    """
    root: Path = request.root
    path_filter: Callable[[Path], bool] | None = request.path_filter
    source_paths: Sequence[Path] | None = request.source_paths
    capability: CapabilityIndex | None = request.capability
    allowed: frozenset[str] = request.allowed
    strict: bool = request.strict
    dry_run: bool = request.dry_run
    python: str | None = request.python
    supplied_paths: bool = source_paths is not None
    active_paths: list[Path] = (
        sorted(path.resolve() for path in source_paths)
        if source_paths is not None
        else python_files(root=root, path_filter=path_filter)
    )
    trace(step=f"discover: {len(active_paths)} python files", depth=2)
    fingerprints: dict[Path, str | None] = _source_fingerprints(
        paths=active_paths,
    )
    auto_fixes: list[JsonValue] = []
    while True:
        project: Project = Project(
            root=root,
            path_filter=path_filter,
            capability=capability,
            source_paths=active_paths,
            python=python,
        )
        trace(step="stage: scan sources", depth=1)
        bare_imports, type_hints, checked = _scan_sources(
            source_paths=active_paths,
            project=project,
            allowed=allowed,
            strict=strict,
        )
        trace(
            step=(
                f"scan: {len(bare_imports)} bare imports, "
                f"{len(type_hints)} type hints, {checked} calls checked"
            ),
            depth=2,
        )
        trace(step="stage: resolve calls", depth=1)
        resolving: BoundedLaneProgress = BoundedLaneProgress(
            total=len(project.by_path),
            step="resolving calls",
            span=(0.5, 0.95),
        )
        exactusors: list[CallExactusor] = [
            _resolve_module_lane(
                project=project,
                module=module,
                progress=resolving,
            )
            for module in project.by_path.values()
        ]
        positional_findings, _ = collect_findings(exactusors=exactusors)
        healed_paths, pass_fixes = _heal_sources(
            root=root,
            paths=active_paths,
            positional=positional_findings,
            bare_imports=bare_imports,
            dry_run=dry_run,
        )
        auto_fixes.extend(pass_fixes)
        if healed_paths:
            trace(
                step=(
                    f"auto-heal: repaired {len(healed_paths)} source files; "
                    "rescanning"
                ),
                depth=2,
            )
            fingerprints = _source_fingerprints(paths=active_paths)
            continue
        stable_paths: list[Path] = (
            list(active_paths)
            if supplied_paths
            else python_files(root=root, path_filter=path_filter)
        )
        stable_fingerprints: dict[Path, str | None] = _source_fingerprints(
            paths=stable_paths,
        )
        if (
            active_paths == stable_paths
            and fingerprints == stable_fingerprints
        ):
            return AnalysisRun(
                project=project,
                exactusors=exactusors,
                bare_imports=bare_imports,
                type_hints=type_hints,
                checked=checked,
                auto_fixes=auto_fixes,
            )
        active_paths = stable_paths
        fingerprints = stable_fingerprints
        trace(
            step=(
                "kwargs typehints: source snapshot changed — "
                f"rebuilding over {len(active_paths)} files"
            ),
            depth=2,
        )
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=0,
                total=max(len(active_paths), 1),
                step="rebuilding changed source snapshot",
                detail="a prerequisite changed source files",
                span=(0.0, 0.3),
            ),
        )


@dataclass(frozen=True, slots=True)
class AnalysisDestinations:
    """Report and artifact destinations for a completed analysis.

    Attributes:
        output: Markdown report destination.
        root: Project root.
        context: Report excerpt context lines.
        heuristics_output: Builtin-fuzz heuristics destination.
        write_index: Optional capability-index destination.

    """

    output: Path
    root: Path
    context: int
    heuristics_output: Path
    write_index: Path | None


def _finalize_analysis(
    *,
    run: AnalysisRun,
    data: dict[str, JsonValue],
    destinations: AnalysisDestinations,
) -> int:
    """Write analysis artifacts and return the blocking-finding status.

    Args:
        run: Stable analysis snapshot.
        data: Legacy report payload.
        destinations: Report and artifact destinations.

    Returns:
        ``1`` when blocking findings remain, otherwise ``0``.

    """
    output: Path = destinations.output
    root: Path = destinations.root
    context: int = destinations.context
    heuristics_output: Path = destinations.heuristics_output
    write_index: Path | None = destinations.write_index
    _write_report_bundle(data=data, output=output, root=root, context=context)
    publish_progress(
        progress=Progress(
            state="RUNNING",
            completed=0,
            total=1,
            step="fuzzing builtins",
            span=(0.95, 1.0),
        ),
    )
    _write_heuristics(heuristics_output=heuristics_output, project=run.project)
    if write_index is not None:
        publish_progress(
            progress=Progress(
                state="RUNNING",
                completed=0,
                total=1,
                step="writing capability index",
                span=(0.98, 1.0),
            ),
        )
        run.project.write_capability_index(path=write_index)
        trace(step=f"capability index: written — {write_index}", depth=2)
    failures: list[Path] = run.project.parse_failures
    status: int = int(
        bool(
            data.get("findings")
            or run.bare_imports
            or run.type_hints
            or failures,
        ),
    )
    trace(
        step=(
            f"kwargs typehints: status {status} — "
            f"{len(failures)} parse failures"
        ),
    )
    return status


def main(
    *,
    arguments: tuple[str, ...] | None = None,
    path_filter: Callable[[Path], bool] | None = None,
    includes: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
    source_paths: Sequence[Path] | None = None,
) -> int:
    """Run the exactus and write the report bundle and heuristics.

    Args:
        arguments: Explicit analyzer arguments.
        path_filter: Optional predicate restricting discovered files.
        includes: Include globs behind ``path_filter`` (report scope).
        excludes: Exclude globs behind ``path_filter`` (report scope).
        source_paths: Optional pre-collected Python source inventory.

    Returns:
        ``1`` when a blocking finding (missing keyword, bare import,
        missing hint, parse failure) exists, else ``0``.

    """
    options: Namespace = parse_args(arguments=arguments)
    root: Path = cast(typ="Path", val=options.root).resolve()
    output: Path = (
        cast(typ="Path | None", val=options.output)
        or root / "POSITIONAL_ARGS_EXACTUS.md"
    )
    heuristics_output: Path = (
        cast(typ="Path | None", val=options.heuristics_output)
        or root / "heuristics.json"
    )
    write_index: Path | None = cast(
        typ="Path | None",
        val=options.write_capability_index,
    )
    index_path: Path | None = cast(
        typ="Path | None",
        val=options.capability_index,
    ) or Path(__file__).resolve().with_name(name="CAPABILITY_INDEX.json")
    capability: CapabilityIndex | None = _load_capability_index(
        write_index=write_index,
        index_path=index_path,
    )
    publish_progress(
        progress=Progress(
            state="WAITING",
            completed=0,
            total=1,
            step="settling source-producing dependencies",
            span=(0.0, 0.0),
        ),
    )
    wait_for_dependencies()
    run: AnalysisRun = _analyze_until_stable(
        request=AnalysisRequest(
            root=root,
            path_filter=path_filter,
            source_paths=source_paths,
            capability=capability,
            allowed=frozenset(
                cast(typ="list[str]", val=options.allow_bare_import),
            ),
            strict=cast(typ="bool", val=options.strict),
            dry_run=cast(typ="bool", val=options.dry),
            python=cast(typ="str | None", val=options.python),
        ),
    )
    data: dict[str, JsonValue] = _legacy_payload(
        run=run,
        scope=_report_scope(includes=includes, excludes=excludes),
    )
    return _finalize_analysis(
        run=run,
        data=data,
        destinations=AnalysisDestinations(
            output=output,
            root=root,
            context=cast(typ="int", val=options.context_lines),
            heuristics_output=heuristics_output,
            write_index=write_index,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
