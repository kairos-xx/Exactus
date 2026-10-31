# Copyright (c) 2026
"""Run recursive tests with coverage derived from their local import graph.

One pytest execution feeds both halves of the ``coverage-tests`` tool: the
combined coverage report and the per-group test reports.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from ast import (
    AST,
    AsyncFunctionDef,
    Attribute,
    Call,
    FunctionDef,
    Import,
    ImportFrom,
    Name,
    NodeVisitor,
    alias,
    parse,
    walk,
)
from asyncio import Semaphore, create_subprocess_exec, gather, run
from asyncio.subprocess import PIPE
from bisect import bisect_right
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from fnmatch import fnmatch
from functools import partial
from hashlib import sha256
from importlib import import_module
from importlib.resources import files
from importlib.util import find_spec
from json import dumps, loads
from os import cpu_count, environ, pathsep
from pathlib import Path
from re import Match, Pattern
from re import compile as recompile
from shutil import rmtree
from subprocess import CompletedProcess, SubprocessError
from sys import executable, stdlib_module_names
from textwrap import dedent
from threading import Thread
from time import monotonic, sleep
from typing import TYPE_CHECKING, ClassVar, Final, Self, cast, final, override
from urllib.parse import unquote, urlparse

from exactus.packages.steps import trace
from exactus.tools.common.cli import (
    ExactusCommonTables,
    activate_exactus_tool_bundle,
    consume,
    exactus_tool_prefix,
    is_reports_tree,
    resolve_exactus_tool_bundle,
)
from exactus.tools.common.runtime import (
    Progress,
    emit_progress,
    publish_progress,
)
from exactus.tools.common.snippets import finding_excerpt
from exactus.tools.coverage_tests.arguments import (
    Constants as _GroupFinalConstants,
)
from exactus.tools.coverage_tests.meaningful import (
    MeaningfulConfig,
    MeaningfulResult,
    analyze_unreached,
    merge_results,
    write_artifact,
)
from exactus.tools.coverage_tests.report import (
    CoverageGates,
    CoverageTestsReport,
    ReportInputs,
)
from exactus.tools.coverage_tests.tracebacks import (
    FailureSite,
    NamedFailure,
    NodeTestFailures,
    PytestTracebacks,
)
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Callable, Iterable, Mapping, Sequence
    from types import ModuleType

    from coverage import CoverageData

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        bmp_max: Grouped module constant.
        expensive_call_names: Grouped module constant.
        child_env_drop: Grouped module constant.

    """

    bmp_max: Final[int] = 65535
    expensive_call_names: Final[frozenset[str]] = frozenset(
        {
            "Popen",
            "browserTest",
            "check_call",
            "check_output",
            "communicate",
            "run",
            "sleep",
            "spawn",
            "start",
            "wait",
        },
    )
    child_env_drop: Final[frozenset[str]] = frozenset(
        {
            "EXACTUS_ORCHESTRATED",
            "EXACTUS_PIPELINE_RUN_ID",
            "EXACTUS_REGISTRY",
            "EXACTUS_RUN_ID",
            "EXACTUS_TOOL",
        },
    )


@dataclass(frozen=True)
class CoverageCoreDefaults:
    """Immutable scalar configuration values.

    Attributes:
        raw_report_name: Raw report name.
        raw_js_report_name: Raw js report name.
        import_graph_name: Import graph name.
        meaningful_name: Meaningful name.
        completion_name: Completion name.
        validation_name: Validation name.
        js_tests_name: Js tests name.
        js_tests_schema: Js tests schema.
        test_costs_name: Test costs name.
        v8_coverage_dir: V8 coverage dir.

    """

    raw_report_name: Final[str] = "coverage_raw_py.json"
    raw_js_report_name: Final[str] = "coverage_raw_js.json"
    import_graph_name: Final[str] = "import_graph.json"
    meaningful_name: Final[str] = "meaningful.json"
    completion_name: Final[str] = "completion.json"
    validation_name: Final[str] = "validation.json"
    js_tests_name: Final[str] = "js-tests.json"
    js_tests_schema: Final[str] = "exactus.coverage-tests.js-tests/v1"
    test_costs_name: Final[str] = "test-costs.json"
    v8_coverage_dir: Final[str] = "v8-coverage"


@dataclass(frozen=True, slots=True)
class CoverageTestsLayout:
    """Locate every report and artifact directory of one tool run.

    Attributes:
        root: Root.

    """

    root: Path

    @property
    def coverage_report(self: Self) -> Path:
        """Directory of the coverage report.

        Returns:
            The resulting value.

        """
        return self.root / "COVERAGE"

    @property
    def tests_report(self: Self) -> Path:
        """Directory of the combined tests report and its group reports.

        Returns:
            The resulting value.

        """
        return self.root / "TESTS"

    @property
    def artifacts(self: Self) -> Path:
        """Directory shared by the run's artifacts.

        Returns:
            The resulting value.

        """
        return self.root / "ARTIFACTS"

    @property
    def coverage_artifacts(self: Self) -> Path:
        """Directory of the raw coverage evidence.

        Returns:
            The resulting value.

        """
        return self.artifacts / "COVERAGE"

    @property
    def tests_artifacts(self: Self) -> Path:
        """Directory of the raw test-run evidence.

        Returns:
            The resulting value.

        """
        return self.artifacts / "TESTS"


@final
class CoverageCoreTables:
    """Shared lookup tables and compiled values.

    Attributes:
        DEFAULT_EXCLUDED_DIRS: Default excluded dirs.
        DEFAULT_SOURCE_DIR_NAMES: Default source dir names.
        TEST_DIR_NAMES: Test dir names.
        JS_TEST_SUFFIXES: Js test suffixes.
        JS_TEST_NAME: Js test name.
        JS_LOADER: Js loader.
        JS_SOURCE_SUFFIXES: Js source suffixes.
        SHARD_LOG_DIRECTORY: Shard log directory.
        PYTEST_SUMMARY_ENTRY: Pytest summary entry.
        PYTEST_TEST_ENTRY: Pytest test entry.
        PYTEST_COLLECTED_ENTRY: Pytest collected entry.
        PYTEST_DURATION_ENTRY: Pytest duration entry.
        PYTEST_WARNING_LOCATION: Pytest warning location.
        JS_FAILURE_ENTRY: Js failure entry.
        SNIPPET_LANGUAGES: Snippet languages.
        SNIPPET_MAX_LINES: Snippet max lines.

    """

    DEFAULT_EXCLUDED_DIRS: ClassVar[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS | frozenset({"bundle"})
    )
    DEFAULT_SOURCE_DIR_NAMES: ClassVar[tuple[str, ...]] = ("src",)
    TEST_DIR_NAMES: ClassVar[frozenset[str]] = frozenset({"test", "tests"})
    JS_TEST_SUFFIXES: ClassVar[frozenset[str]] = frozenset(
        {".js", ".mjs", ".cjs"},
    )
    JS_TEST_NAME: ClassVar[Pattern[str]] = recompile(
        pattern="(?:\\.test|\\.spec|_test)\\.[cm]?js$",
    )
    JS_LOADER: ClassVar[str] = "exactus/tests/loader.mjs"
    JS_SOURCE_SUFFIXES: ClassVar[frozenset[str]] = frozenset({".js", ".mjs"})
    SHARD_LOG_DIRECTORY: ClassVar[str] = "pytest-shards"
    PYTEST_SUMMARY_ENTRY: ClassVar[Pattern[str]] = recompile(
        pattern=(
            "^(?P<kind>FAILED|ERROR)\\s+(?P<test>.+?)(?:\\s+-\\s+(?P<detail>.*"
            "))?$"
        ),
    )
    PYTEST_TEST_ENTRY: ClassVar[Pattern[str]] = recompile(
        pattern=(
            "^(?P<test>.+::.+)\\s+(?P<outcome>PASSED|FAILED|ERROR|SKIPPED|XFAI"
            "L|XPASS)\\b"
        ),
    )
    PYTEST_COLLECTED_ENTRY: ClassVar[Pattern[str]] = recompile(
        pattern="collected\\s+(?P<count>\\d+)\\s+items?\\b",
    )
    PYTEST_DURATION_ENTRY: ClassVar[Pattern[str]] = recompile(
        pattern=(
            "^\\s*(?P<seconds>\\d+(?:\\.\\d+)?)s\\s+(?:setup|call|teardown)\\s"
            "+(?P<nodeid>.+)$"
        ),
    )
    PYTEST_WARNING_LOCATION: ClassVar[Pattern[str]] = recompile(
        pattern=(
            "^\\s+(?P<location>\\S+?:\\d+):\\s+(?P<category>[A-Za-z_][\\w.]*):"
            "\\s*(?P<message>.*)$"
        ),
    )
    JS_FAILURE_ENTRY: ClassVar[Pattern[str]] = recompile(
        pattern="^\\s*not ok\\s+\\d+\\s+-\\s+(?P<name>.+?)\\s*$",
    )
    SNIPPET_LANGUAGES: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "javascript",
        ".tsx": "javascript",
        ".mts": "javascript",
        ".cts": "javascript",
    }
    SNIPPET_MAX_LINES: ClassVar[int] = 600


def _child_environ(
    *,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a sanitized environment for spawned child processes.

    Args:
        overrides: Overrides.

    Returns:
        The resulting value.

    """
    environment: dict[str, str] = {
        key: value
        for key, value in environ.items()
        if key not in Constants.child_env_drop
    }
    if overrides:
        environment.update(overrides)
    return environment


def _character_ranges(
    *,
    source: str,
    ranges: tuple[tuple[int, int, int], ...],
) -> tuple[tuple[int, int, int], ...]:
    """Translate UTF-16 code-unit offsets into Python character offsets.

    Args:
        source: Source.
        ranges: Ranges.

    Returns:
        The resulting value.

    """
    offsets: dict[int, int] = {0: 0}
    utf16_offset: int = 0
    for character_offset, character in enumerate(iterable=source, start=1):
        utf16_offset += 2 if ord(character) > Constants.bmp_max else 1
        offsets[utf16_offset] = character_offset
    return tuple(
        (
            (offsets.get(start, start), offsets.get(end, end), count)
            for start, end, count in ranges
        ),
    )


class CoverageRunError(RuntimeError):
    """Represent a combined-coverage discovery or execution failure."""


class CliNamespace(Namespace):
    """Describe the typed command-line parser namespace.

    Attributes:
        root: Root.
        output: Output.
        source_root: Source root.
        no_branch: No branch.
        fail_under: Fail under.
        exclude_dir: Exclude dir.
        pytest_args: Pytest args.
        no_js_coverage: No js coverage.
        jobs: Jobs.
        shard_by: Pytest shard unit.
        context_lines: Context lines.
        per_file_minimum: Per file minimum.

    """

    root: Path
    output: Path
    source_root: list[Path]
    no_branch: bool
    fail_under: float | None
    exclude_dir: list[str]
    pytest_args: list[str]
    no_js_coverage: bool
    jobs: int | None
    shard_by: str
    context_lines: int
    per_file_minimum: float | None

    def __init__(self: Self) -> None:
        """Initialize parser defaults before argparse overwrites them.

        Pre-seeded values must mirror the ``add_argument`` defaults:
        argparse skips an action's ``default`` whenever the destination
        attribute already exists on the target namespace.

        """
        super().__init__()
        self.root = Path()
        self.output = Path("coverage_report")
        self.source_root = []
        self.no_branch = False
        self.fail_under = 90.0
        self.exclude_dir = []
        self.pytest_args = []
        self.no_js_coverage = False
        self.jobs = None
        self.shard_by = "file"
        self.context_lines = 3
        self.per_file_minimum = 80.0


@dataclass(frozen=True, slots=True)
class CoverageConfig:
    """Store immutable combined-coverage execution settings.

    Attributes:
        root: Root.
        output: Output.
        source_roots: Source roots.
        branch: Branch.
        fail_under: Fail under.
        excluded_dirs: Excluded dirs.
        pytest_args: Pytest args.
        include_unreached: Include unreached.
        measure_js: Measure js.
        jobs: Jobs.
        shard_by: Pytest shard unit.
        context_lines: Context lines.
        per_file_minimum: Per file minimum.
        test_includes: Test includes.
        test_excludes: Test excludes.
        source_excludes: Root-relative globs rejecting measured source
            files from coverage and meaningful analysis.
        meaningful: Meaningful.

    """

    root: Path
    output: Path
    source_roots: tuple[Path, ...]
    branch: bool
    fail_under: float | None
    excluded_dirs: frozenset[str]
    pytest_args: tuple[str, ...]
    include_unreached: bool = False
    measure_js: bool = True
    jobs: int = 1
    shard_by: str = "file"
    context_lines: int = 3
    per_file_minimum: float | None = None
    test_includes: tuple[str, ...] = ()
    test_excludes: tuple[str, ...] = ()
    source_excludes: tuple[str, ...] = ()
    meaningful: MeaningfulConfig = field(default_factory=MeaningfulConfig)


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    """Describe one local importable Python module.

    Attributes:
        name: Name.
        path: Path.
        source_root: Source root.
        is_package: Is package.

    """

    name: str
    path: Path
    source_root: Path
    is_package: bool


@dataclass(frozen=True, slots=True)
class ImportRequest:
    """Describe one static import request found in a Python module.

    Attributes:
        module: Module.
        names: Names.
        level: Level.

    """

    module: str | None
    names: tuple[str, ...]
    level: int


@dataclass(frozen=True, slots=True)
class ImportGraph:
    """Store the recursively resolved local import graph.

    Attributes:
        tests: Tests.
        targets: Targets.
        ignored_imports: Ignored imports.

    """

    tests: tuple[Path, ...]
    targets: tuple[ModuleRecord, ...]
    ignored_imports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JsFileCoverage:
    """Store line-level coverage for one JavaScript source file.

    Attributes:
        covered: Covered.
        executable: Executable.

    """

    covered: frozenset[int]
    executable: frozenset[int]


@dataclass(frozen=True, slots=True)
class JsCoverageResult:
    """Store the outcome of the JavaScript coverage lane.

    Attributes:
        tests: Tests.
        files: Files.
        unreached: Unreached.
        status: Status.
        detail: Detail.
        failures: Failures.
        failure_sites: Failure sites.

    """

    tests: tuple[str, ...]
    files: dict[str, JsFileCoverage]
    unreached: tuple[str, ...]
    status: int
    detail: str = ""
    failures: tuple[str, ...] = ()
    failure_sites: tuple[NamedFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class CoverageSnapshot:
    """Store the measured coverage state at one point in the run.

    Attributes:
        report: Parsed Python coverage JSON payload.
        js_result: Completed JavaScript coverage lane, when present.
        js_manifest: JavaScript lane manifest, when present.

    """

    report: dict[str, JsonValue]
    js_result: JsCoverageResult | None
    js_manifest: dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class TestFailure:
    """One failed or errored test reported by a pytest shard.

    Attributes:
        shard: Shard.
        kind: Kind.
        test: Test.
        detail: Detail.
        path: Path.
        line: Line.
        reason: Reason.

    """

    shard: int
    kind: str
    test: str
    detail: str
    path: str | None = None
    line: int | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TestWarning:
    """One warning reported by a pytest shard.

    Attributes:
        shard: Shard.
        test: Test.
        location: Location.
        category: Category.
        message: Message.

    """

    shard: int
    test: str
    location: str
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class ExecutedTest:
    """One executed test reported by a pytest shard.

    Attributes:
        shard: Shard.
        test: Test.
        outcome: Outcome.

    """

    shard: int
    test: str
    outcome: str


@dataclass(frozen=True, slots=True)
class ShardOutcome:
    """Captured outcome of one parallel pytest shard.

    Attributes:
        index: Index.
        returncode: Returncode.
        log: Log.
        collected: Collected.
        tests: Tests.
        failures: Failures.
        warnings: Warnings.
        skipped: Skipped.

    """

    index: int
    returncode: int
    log: str
    collected: int | None
    tests: tuple[ExecutedTest, ...]
    failures: tuple[TestFailure, ...]
    warnings: tuple[TestWarning, ...]
    skipped: tuple[TestFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class TestExecution:
    """Aggregate pytest shard results with parsed test issues.

    Attributes:
        shards: Shards.
        status: Status.
        duration_seconds: Duration seconds.

    """

    shards: tuple[ShardOutcome, ...]
    status: int
    duration_seconds: float = 0.0


class ImportCollector(NodeVisitor):
    """Collect static ``import`` and ``from ... import ...`` statements."""

    def __init__(self: Self) -> None:
        """Initialize an empty collector."""
        self.requests: list[ImportRequest] = []

    @override
    def generic_visit(self: Self, node: AST) -> None:
        """Route import nodes to their collectors and keep recursing.

        Args:
            node: Node.

        """
        if isinstance(node, Import):
            self._collect_import(node=node)
        elif isinstance(node, ImportFrom):
            self._collect_import_from(node=node)
        super().generic_visit(node=node)

    @staticmethod
    def _imported_name(entry: alias) -> str:
        """Return the dotted name carried by one import alias.

        Args:
            entry: Entry.

        Returns:
            The resulting value.

        """
        return entry.name

    def _collect_import(self: Self, node: Import) -> None:
        """Collect absolute imports.

        Args:
            node: Node.

        """
        imported: alias
        for imported in node.names:
            self.requests.append(
                ImportRequest(module=imported.name, names=(), level=0),
            )

    def _collect_import_from(self: Self, node: ImportFrom) -> None:
        """Collect absolute or relative from-imports.

        Args:
            node: Node.

        """
        collected_names: list[str] = list(map(self._imported_name, node.names))
        self.requests.append(
            ImportRequest(
                module=node.module,
                names=tuple(collected_names),
                level=node.level,
            ),
        )


class LocalModuleIndex:
    """Index import names that resolve to local project Python files."""

    def __init__(
        self: Self,
        root: Path,
        source_roots: tuple[Path, ...],
        excluded_dirs: frozenset[str],
        excludes: tuple[str, ...] = (),
    ) -> None:
        """Build the local module index.

        Args:
            root: Root.
            source_roots: Source roots.
            excluded_dirs: Excluded dirs.
            excludes: Root-relative globs rejecting measured sources.

        """
        self._root: Path = root
        self._source_roots: tuple[Path, ...] = source_roots
        self._excluded_dirs: frozenset[str] = excluded_dirs
        self._excludes: tuple[str, ...] = excludes
        self._excluded: list[Path] = []
        self._by_name: dict[str, ModuleRecord] = self._build()
        self._by_path: dict[Path, ModuleRecord] = {}
        record: ModuleRecord
        for record in self._by_name.values():
            self._by_path[record.path] = record

    @property
    def records(self: Self) -> tuple[ModuleRecord, ...]:
        """All indexed local modules.

        Returns:
            The resulting value.

        """
        return tuple(
            sorted(self._by_path.values(), key=lambda record: record.name),
        )

    @property
    def excluded(self: Self) -> tuple[Path, ...]:
        """Source files rejected by the configured exclude globs.

        Returns:
            Sorted deduplicated paths omitted from coverage measurement.

        """
        return tuple(
            dict.fromkeys(
                sorted(self._excluded, key=lambda path: path.as_posix()),
            ),
        )

    def record_for_name(self: Self, name: str) -> ModuleRecord | None:
        """Return the local record for an import name.

        Args:
            name: Name.

        Returns:
            The resulting value.

        """
        return self._by_name.get(name)

    def record_for_path(self: Self, path: Path) -> ModuleRecord | None:
        """Return the indexed record for a source path.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        return self._by_path.get(path.resolve())

    def package_records(self: Self, name: str) -> tuple[ModuleRecord, ...]:
        """Return package initializers loaded before a module.

        Args:
            name: Name.

        Returns:
            The resulting value.

        """
        parts: tuple[str, ...] = tuple(name.split(sep="."))
        records: list[ModuleRecord] = []
        index: int
        for index in range(1, len(parts)):
            record: ModuleRecord | None = self.record_for_name(
                name=".".join(parts[:index]),
            )
            if record is not None and record.is_package:
                records.append(record)
        return tuple(records)

    @staticmethod
    def _module_name(path: Path, source_root: Path) -> tuple[str, bool]:
        """Convert a local Python path to its import name.

        Args:
            path: Path.
            source_root: Source root.

        Returns:
            The resulting value.

        """
        relative: Path = path.relative_to(source_root)
        is_package: bool = relative.name == "__init__.py"
        parts: tuple[str, ...] = (
            relative.parts[:-1]
            if is_package
            else (*relative.parts[:-1], relative.stem)
        )
        return (".".join(parts), is_package)

    def _is_allowed_path(self: Self, path: Path, source_root: Path) -> bool:
        """Return whether a Python path is eligible project source.

        Args:
            path: Path.
            source_root: Source root.

        Returns:
            The resulting value.

        """
        relative: Path = path.relative_to(source_root)
        parts: tuple[str, ...] = relative.parts[:-1]
        excluded: bool = False
        part: str
        for part in parts:
            if part.startswith(".") or part in self._excluded_dirs:
                excluded = True
                break
        testing_root: bool = (
            source_root.name in CoverageCoreTables.TEST_DIR_NAMES
        )
        return (
            path.is_file()
            and path.suffix == ".py"
            and (
                testing_root
                or (
                    not path.name.startswith("test_")
                    and CoverageCoreTables.TEST_DIR_NAMES.isdisjoint(parts)
                )
            )
            and (not excluded)
        )

    def _source_excluded(self: Self, path: Path) -> bool:
        """Return whether a path matches a configured exclude glob.

        Args:
            path: Candidate measured source.

        Returns:
            ``True`` when a root-relative exclude glob rejects the path.

        """
        if not self._excludes or not path.is_relative_to(self._root):
            return False
        relative: str = path.relative_to(self._root).as_posix()
        return any(
            fnmatch(name=relative, pat=pattern) for pattern in self._excludes
        )

    def _aliases(self: Self, record: ModuleRecord) -> tuple[str, ...]:
        """Return every import name that can load one local module.

        Args:
            record: Record.

        Returns:
            The resulting value.

        """
        relative: Path = (
            record.path.relative_to(self._root)
            if record.path.is_relative_to(self._root)
            else record.path.relative_to(record.source_root)
        )
        parts: tuple[str, ...] = (
            relative.parts[:-1]
            if record.is_package
            else (*relative.parts[:-1], relative.stem)
        )
        packages: list[str] = []
        directory: Path = self._root
        while (directory / "__init__.py").is_file() and directory.name:
            packages.insert(0, directory.name)
            directory = directory.parent
        return tuple(
            dict.fromkeys(
                (
                    *(
                        ".".join((*packages[index:], *parts))
                        for index in range(len(packages))
                    ),
                    record.name,
                    *(
                        ".".join(parts[index:])
                        for index in range(len(parts))
                        if parts[index] not in stdlib_module_names
                    ),
                ),
            ),
        )

    def _build(self: Self) -> dict[str, ModuleRecord]:
        """Build deterministic import-name to local-file mappings.

        Returns:
            The resulting value.

        """
        records: dict[str, ModuleRecord] = {}
        source_root: Path
        for source_root in sorted(
            self._source_roots,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            entries: Iterable[tuple[Path, list[str], list[str]]]
            scan_root: Path = source_root
            if scan_root.is_file():
                entries = ((scan_root.parent, [], [scan_root.name]),)
                scan_root = scan_root.parent
            else:
                entries = scan_root.walk()
            testing_root: bool = (
                scan_root.name in CoverageCoreTables.TEST_DIR_NAMES
            )
            path: Path
            directory: Path
            dirnames: list[str]
            filenames: list[str]
            for directory, dirnames, filenames in entries:
                dirnames[:] = sorted(
                    name
                    for name in dirnames
                    if not name.startswith(".")
                    and name not in self._excluded_dirs
                    and (
                        testing_root
                        or name not in CoverageCoreTables.TEST_DIR_NAMES
                    )
                    and (not is_reports_tree(directory=directory / name))
                )
                for filename in sorted(filenames):
                    if not filename.endswith(
                        ".py",
                    ) or not self._is_allowed_path(
                        path=(path := (directory / filename)),
                        source_root=scan_root,
                    ):
                        continue
                    if self._source_excluded(path=path):
                        self._excluded.append(path.resolve())
                        continue
                    name_and_kind: tuple[str, bool] = self._module_name(
                        path=path,
                        source_root=scan_root,
                    )
                    if not name_and_kind[0]:
                        continue
                    name: str = name_and_kind[0]
                    _ = consume(
                        value=records.setdefault(
                            name,
                            ModuleRecord(
                                name=name,
                                path=path.resolve(),
                                source_root=source_root,
                                is_package=name_and_kind[1],
                            ),
                        ),
                    )
        record: ModuleRecord
        for record in tuple(records.values()):
            alias_name: str
            for alias_name in self._aliases(record=record):
                _ = consume(value=records.setdefault(alias_name, record))
        return records


class ImportGraphResolver:
    """Resolve the local import closure rooted at discovered tests."""

    def __init__(self: Self, index: LocalModuleIndex) -> None:
        """Initialize the resolver.

        Args:
            index: Index.

        """
        self._index: LocalModuleIndex = index

    def resolve(self: Self, tests: tuple[Path, ...]) -> ImportGraph:
        """Resolve all recursively reachable local modules from exactus.tests.

        Args:
            tests: Tests.

        Returns:
            The resulting value.

        """
        pending: list[ModuleRecord] = []
        resolved: dict[Path, ModuleRecord] = {}
        ignored: set[str] = set()
        test: Path
        for test in tests:
            request: ImportRequest
            for request in self._requests(path=test):
                self._enqueue_request(
                    request=request,
                    current=None,
                    pending=pending,
                    resolved=resolved,
                    ignored=ignored,
                )
        while pending:
            current: ModuleRecord = pending.pop()
            if current.path in resolved:
                continue
            resolved[current.path] = current
            for request in self._requests(path=current.path):
                self._enqueue_request(
                    request=request,
                    current=current,
                    pending=pending,
                    resolved=resolved,
                    ignored=ignored,
                )
        return ImportGraph(
            tests=tests,
            targets=tuple(
                sorted(resolved.values(), key=lambda record: record.name),
            ),
            ignored_imports=tuple(sorted(ignored)),
        )

    @staticmethod
    def _requests(path: Path) -> tuple[ImportRequest, ...]:
        """Parse static imports from one Python file without importing it.

        Args:
            path: Path.

        Returns:
            The resulting value.

        Raises:
            CoverageRunError: Raised when the operation cannot be completed.

        """
        collector: ImportCollector = ImportCollector()
        try:
            collector.visit(
                node=parse(
                    source=path.read_text(encoding="utf-8"),
                    filename=str(object=path),
                ),
            )
        except (OSError, SyntaxError, UnicodeError) as error:
            error: OSError | SyntaxError | UnicodeError
            msg: str = f"Unable to inspect imports in {path}: {error}"
            raise CoverageRunError(msg) from error
        return tuple(collector.requests)

    @staticmethod
    def _relative_base(
        request: ImportRequest,
        current: ModuleRecord,
    ) -> str | None:
        """Resolve a relative import to an absolute module name.

        Args:
            request: Request.
            current: Current.

        Returns:
            The resulting value.

        """
        package: str = (
            current.name
            if current.is_package
            else current.name.rpartition(".")[0]
        )
        parts: list[str] = package.split(sep=".") if package else []
        if request.level > len(parts) + 1:
            return None
        retained: list[str] = (
            parts[: len(parts) - request.level + 1]
            if request.level > 1
            else parts
        )
        return ".".join(
            (*retained, *((request.module,) if request.module else ())),
        )

    def _enqueue(
        self: Self,
        name: str,
        *,
        pending: list[ModuleRecord],
        resolved: dict[Path, ModuleRecord],
    ) -> bool:
        """Add one local module and its package initializers to work.

        Args:
            name: Name.
            pending: Pending.
            resolved: Resolved.

        Returns:
            The resulting value.

        """
        if (record := self._index.record_for_name(name=name)) is None:
            return False
        candidate: ModuleRecord
        for candidate in (*self._index.package_records(name=name), record):
            if candidate.path not in resolved and candidate not in pending:
                pending.append(candidate)
        return True

    def _enqueue_request(
        self: Self,
        request: ImportRequest,
        current: ModuleRecord | None,
        *,
        pending: list[ModuleRecord],
        resolved: dict[Path, ModuleRecord],
        ignored: set[str],
    ) -> None:
        """Resolve one request and record only wholly non-local imports.

        Args:
            request: Request.
            current: Current.
            pending: Pending.
            resolved: Resolved.
            ignored: Ignored.

        """
        candidates: tuple[str, ...] = self._candidate_names(
            request=request,
            current=current,
        )
        matches: list[bool] = list(
            map(
                partial(self._enqueue, pending=pending, resolved=resolved),
                candidates,
            ),
        )
        if candidates and (not any(matches)):
            ignored.add(candidates[0])

    def _candidate_names(
        self: Self,
        request: ImportRequest,
        current: ModuleRecord | None,
    ) -> tuple[str, ...]:
        """Return absolute import names potentially loaded by one request.

        Args:
            request: Request.
            current: Current.

        Returns:
            The resulting value.

        """
        if request.level:
            if (
                current is None
                or (
                    base := self._relative_base(
                        request=request,
                        current=current,
                    )
                )
                is None
            ):
                return ()
        else:
            base = request.module or ""
        candidates: list[str] = []
        if base:
            candidates.append(base)
        name: str
        for name in request.names:
            if name == "*":
                continue
            candidates.append(f"{base}.{name}" if base else name)
        return tuple(dict.fromkeys(candidates))


class CombinedCoverageRunner:
    """Discover tests, resolve local targets, and render combined coverage."""

    _last_batch_durations: ClassVar[tuple[float, ...]] = ()

    def __init__(
        self: Self,
        config: CoverageConfig,
        *,
        test_filter: Callable[[Path], bool] | None = None,
    ) -> None:
        """Initialize the runner.

        Args:
            config: Config.
            test_filter: Test filter.

        """
        self._config: CoverageConfig = replace(
            config,
            root=config.root.resolve(),
            output=config.output.resolve(),
            source_roots=tuple(
                source_root.resolve() for source_root in config.source_roots
            ),
        )
        self._test_filter: Callable[[Path], bool] | None = test_filter
        self._layout: CoverageTestsLayout = CoverageTestsLayout(
            root=self._config.output,
        )
        self.report_inputs: ReportInputs | None = None
        self.report_legacy: dict[str, JsonValue] = {}
        self._current_static_costs: dict[str, int] = {}

    @classmethod
    def execute_program(
        cls: type[Self],
        *,
        program: str,
        arguments: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> CompletedProcess[bytes]:
        """Execute one arbitrary program without a shell.

        Args:
            program: Program.
            arguments: Arguments.
            cwd: Cwd.
            environment: Environment.

        Returns:
            The resulting value.

        """
        return run(
            main=cls._execute_program_async(
                program=program,
                arguments=arguments,
                cwd=cwd,
                environment=environment,
            ),
        )

    @classmethod
    def execute_many(
        cls: type[Self],
        *,
        argument_sets: tuple[tuple[str, ...], ...],
        cwd: Path,
        program: str | None = None,
        concurrency: int | None = None,
        progress: tuple[str, tuple[float, float]] = (
            "pytest shard",
            (0.2, 0.6),
        ),
    ) -> tuple[CompletedProcess[bytes], ...]:
        """Execute several Python module commands in parallel.

        Args:
            argument_sets: Argument sets.
            cwd: Cwd.
            program: Program.
            concurrency: Maximum simultaneously running commands.
            progress: Activity label and parent-task span for this batch.

        Returns:
            The resulting value.

        """
        return run(
            main=cls._execute_many_async(
                argument_sets=argument_sets,
                cwd=cwd,
                program=program,
                concurrency=concurrency,
                progress=progress,
            ),
        )

    @classmethod
    def execute(
        cls: type[Self],
        arguments: tuple[str, ...],
        cwd: Path,
        program: str | None = None,
    ) -> CompletedProcess[bytes]:
        """Execute one Python module command without a shell.

        Args:
            arguments: Arguments.
            cwd: Cwd.
            program: Program.

        Returns:
            The resulting value.

        """
        return run(
            main=cls._execute_async(
                arguments=arguments,
                cwd=cwd,
                program=program,
            ),
        )

    @staticmethod
    def pytest_failures(
        *,
        text: str,
        shard: int,
        root: Path | None = None,
    ) -> tuple[TestFailure, ...]:
        """Extract FAILED/ERROR summary entries from pytest output.

        Args:
            text: Text.
            shard: Shard.
            root: Root.

        Returns:
            The resulting value.

        """
        failures: list[TestFailure] = []
        line: str
        for line in text.splitlines():
            match: Match[str] | None = (
                CoverageCoreTables.PYTEST_SUMMARY_ENTRY.match(string=line)
            )
            if match is None:
                continue
            failures.append(
                TestFailure(
                    shard=shard,
                    kind=match.group("kind"),
                    test=match.group("test"),
                    detail=match.group("detail") or "",
                ),
            )
        if root is None or not failures:
            return tuple(failures)
        sites: tuple[FailureSite | None, ...] = PytestTracebacks.sites(
            text=text,
            root=root,
            entries=[(failure.kind, failure.test) for failure in failures],
        )
        return tuple(
            (
                failure
                if site is None
                else replace(
                    failure,
                    path=site.path,
                    line=site.line,
                    reason=site.reason,
                )
                for failure, site in zip(failures, sites, strict=True)
            ),
        )

    @staticmethod
    def pytest_skips(*, text: str, shard: int) -> tuple[TestFailure, ...]:
        """Read the complete skip records emitted by the pytest plugin.

        Args:
            text: Text.
            shard: Shard.

        Returns:
            The resulting value.

        """
        skipped: list[TestFailure] = []
        for line in text.splitlines():
            if not line.startswith("EXACTUS_SKIPPED "):
                continue
            entry: dict[str, JsonValue] = loads(
                s=line.removeprefix("EXACTUS_SKIPPED "),
            )
            source_line: JsonValue = entry.get("line")
            skipped.append(
                TestFailure(
                    shard=shard,
                    kind="SKIPPED",
                    test=str(object=entry.get("test", "")),
                    path=str(object=entry.get("path", "")),
                    line=source_line if isinstance(source_line, int) else None,
                    reason=str(object=entry.get("reason", "")),
                    detail=str(object=entry.get("reason", "")),
                ),
            )
        return tuple(skipped)

    @staticmethod
    def pytest_tests(*, text: str, shard: int) -> tuple[ExecutedTest, ...]:
        """Extract per-test outcomes from verbose pytest output.

        Args:
            text: Text.
            shard: Shard.

        Returns:
            The resulting value.

        """
        tests: list[ExecutedTest] = []
        seen: set[str] = set()
        line: str
        for line in text.splitlines():
            match: Match[str] | None = (
                CoverageCoreTables.PYTEST_TEST_ENTRY.match(string=line)
            )
            if match is None:
                continue
            node: str = match.group("test")
            if node in seen:
                continue
            seen.add(node)
            tests.append(
                ExecutedTest(
                    shard=shard,
                    test=node,
                    outcome=match.group("outcome"),
                ),
            )
        return tuple(tests)

    @staticmethod
    def pytest_collected(*, text: str) -> int | None:
        """Extract the collected test count from pytest output.

        Args:
            text: Text.

        Returns:
            The resulting value.

        """
        line: str
        for line in text.splitlines():
            match: Match[str] | None = (
                CoverageCoreTables.PYTEST_COLLECTED_ENTRY.search(string=line)
            )
            if match is not None:
                return int(match.group("count"))
        return None

    @staticmethod
    def pytest_warnings(*, text: str, shard: int) -> tuple[TestWarning, ...]:
        """Extract warnings-summary entries from pytest output.

        Args:
            text: Text.
            shard: Shard.

        Returns:
            The resulting value.

        """
        warnings: list[TestWarning] = []
        in_summary: bool = False
        test: str = ""
        line: str
        for line in text.splitlines():
            if line.startswith("="):
                if in_summary:
                    break
                in_summary = "warnings summary" in line
                continue
            if not in_summary or not line.strip() or line.startswith("--"):
                continue
            match: Match[str] | None = (
                CoverageCoreTables.PYTEST_WARNING_LOCATION.match(string=line)
            )
            if match is not None:
                warnings.append(
                    TestWarning(
                        shard=shard,
                        test=test,
                        location=match.group("location"),
                        category=match.group("category"),
                        message=match.group("message"),
                    ),
                )
            elif not line.startswith((" ", "\t")):
                test = line.strip()
        return tuple(warnings)

    def discover_tests(self: Self) -> tuple[Path, ...]:
        """Return deterministic recursive ``test_*.py`` paths.

        Returns:
            The resulting value.

        """
        root: Path = self._config.root
        entries: Iterable[tuple[Path, list[str], list[str]]]
        if root.is_file():
            entries = ((root.parent, [], [root.name]),)
            root = root.parent
        else:
            entries = root.walk()
        candidates: list[Path] = []
        path: Path
        directory: Path
        dirnames: list[str]
        filenames: list[str]
        for directory, dirnames, filenames in entries:
            parts: tuple[str, ...] = directory.relative_to(root).parts
            in_tests: bool = not CoverageCoreTables.TEST_DIR_NAMES.isdisjoint(
                parts,
            )
            dirnames[:] = sorted(
                name
                for name in dirnames
                if not name.startswith(".")
                and (in_tests or name not in self._config.excluded_dirs)
                and (not is_reports_tree(directory=directory / name))
            )
            for filename in filenames:
                if filename.startswith("test_") and filename.endswith(".py"):
                    path = directory / filename
                    if path.is_file():
                        candidates.append(path.resolve())
        discovered: tuple[Path, ...] = tuple(
            sorted(candidates, key=lambda path: path.as_posix()),
        )
        selected: tuple[Path, ...] = (
            discovered
            if self._test_filter is None
            else tuple(filter(self._test_filter, discovered))
        )
        trace(
            step=(
                f"discover tests: "
                f"{len(selected)} of {len(discovered)} test files"
            ),
            depth=2,
        )
        return selected

    def discover_js_tests(self: Self) -> tuple[Path, ...]:
        """Return deterministic ``node:test`` test files across the project.

        Returns:
            The resulting value.

        """
        root: Path = self._config.root
        entries: Iterable[tuple[Path, list[str], list[str]]]
        if root.is_file():
            entries = ((root.parent, [], [root.name]),)
            root = root.parent
        else:
            entries = root.walk()
        candidates: list[Path] = []
        path: Path
        directory: Path
        dirnames: list[str]
        filenames: list[str]
        for directory, dirnames, filenames in entries:
            in_tests: bool = not CoverageCoreTables.TEST_DIR_NAMES.isdisjoint(
                directory.relative_to(root).parts,
            )
            dirnames[:] = sorted(
                name
                for name in dirnames
                if not name.startswith(".")
                and (in_tests or name not in self._config.excluded_dirs)
                and (not is_reports_tree(directory=directory / name))
            )
            for name in filenames:
                path = directory / name
                if (
                    path.suffix not in CoverageCoreTables.JS_TEST_SUFFIXES
                    or not CoverageCoreTables.JS_TEST_NAME.search(string=name)
                ):
                    continue
                try:
                    text: str = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if "node:test" in text:
                    candidates.append(path.resolve())
        discovered: tuple[Path, ...] = tuple(
            sorted(candidates, key=lambda path: path.as_posix()),
        )
        selected: tuple[Path, ...] = (
            discovered
            if self._test_filter is None
            else tuple(filter(self._test_filter, discovered))
        )
        trace(
            step=(
                f"discover js tests: "
                f"{len(selected)} of {len(discovered)} node:test files"
            ),
            depth=2,
        )
        return selected

    def run(self: Self) -> int:
        """Run all tests once and report only their reachable local sources.

        Returns:
            The resulting value.

        """
        if not (tests := self.discover_tests()):
            return self._pass_without_tests()
        trace(step="stage: index sources", depth=1)
        emit_progress(
            state="RUNNING",
            completed=1,
            total=5,
            step="index sources",
            detail=f"{len(tests)} test files",
        )
        index: LocalModuleIndex = LocalModuleIndex(
            root=self._config.root,
            source_roots=self._config.source_roots,
            excluded_dirs=self._config.excluded_dirs,
            excludes=self._config.source_excludes,
        )
        graph: ImportGraph = ImportGraphResolver(index=index).resolve(
            tests=tests,
        )
        trace(
            step=(
                f"graph: {len(graph.targets)} local targets, "
                f"{len(graph.ignored_imports)} ignored imports"
            ),
            depth=2,
        )
        self._layout.coverage_artifacts.mkdir(parents=True, exist_ok=True)
        self._write_manifest(graph=graph)
        self._purge_data_files()
        collect_config: Path = self._write_coverage_config(
            name=".coveragerc.collect",
            omitted=index.excluded,
        )
        js_results: list[JsCoverageResult | None] = []
        js_errors: list[Exception] = []
        js_thread: Thread | None = self._start_javascript_lane(
            js_results=js_results,
            js_errors=js_errors,
        )
        trace(step="stage: pytest shards", depth=1)
        execution: TestExecution = self._run_test_shards(
            tests=tests,
            collect_config=collect_config,
        )
        groups: tuple[Mapping[str, JsonValue], ...] = (
            self._write_shared_test_reports(tests=tests, execution=execution)
        )
        trace(step="stage: combine coverage", depth=1)
        emit_progress(
            state="RUNNING",
            completed=3,
            total=5,
            step="combine coverage",
        )
        _ = consume(
            value=self._report(
                "combine",
                "--keep",
                "--quiet",
                config_path=collect_config,
            ),
        )
        meaningful: MeaningfulResult
        config_path: Path
        omitted: tuple[Path, ...]
        unreached: tuple[Path, ...]
        meaningful, config_path, omitted, unreached = (
            self._classify_and_rebuild(index=index, graph=graph)
        )
        coverage_report: dict[str, JsonValue] = self._coverage_report(
            config_path=config_path,
        )
        trace(step="stage: javascript lane — finalize", depth=1)
        emit_progress(
            state="RUNNING",
            completed=9,
            total=10,
            step="javascript lane",
        )
        if js_thread is not None:
            js_thread.join()
        if js_errors:
            raise js_errors[0]
        js_result: JsCoverageResult | None = (
            js_results[0] if js_results else self._run_js_coverage()
        )
        js_manifest: dict[str, JsonValue] | None = (
            self._js_manifest(result=js_result)
            if js_result is not None
            else None
        )
        js_status: int = js_result.status if js_result is not None else 0
        meaningful, omitted = self._merge_javascript_meaningful(
            current=meaningful,
            javascript=js_result,
            index=index,
            graph=graph,
            omitted=omitted,
        )
        snapshot: CoverageSnapshot
        snapshot, meaningful = self._excuse_shortfalls(
            graph=graph,
            unreached=unreached,
            omitted=omitted,
            snapshot=CoverageSnapshot(
                report=coverage_report,
                js_result=js_result,
                js_manifest=js_manifest,
            ),
            meaningful=meaningful,
        )
        coverage_report = snapshot.report
        js_manifest = snapshot.js_manifest
        self._write_exactus_bundle(
            javascript=js_manifest,
            execution=execution,
            groups=groups,
        )
        trace(step="stage: gates and finalization", depth=1)
        self._purge_data_files()
        totals: JsonValue = coverage_report.get("totals")
        total_map: dict[str, JsonValue] = (
            totals if isinstance(totals, dict) else {}
        )
        percent: JsonValue = total_map.get("percent_covered", 0.0)
        threshold_status: int = int(
            (
                self._config.fail_under is not None
                and isinstance(percent, int | float)
                and (percent < self._config.fail_under)
            )
            or bool(self._file_shortfalls(coverage_report=coverage_report))
            or self._js_gate_failed(javascript=js_manifest)
            or (
                self._config.meaningful.mode == "require"
                and bool(meaningful.actionable or meaningful.analysis_errors)
            ),
        )
        final_status: int = threshold_status or execution.status
        trace(
            step=(
                f"coverage tests: gates — total "
                f"{percent}%, threshold status {
                    threshold_status
                }, execution status {execution.status}, final {final_status}"
            ),
            depth=1,
        )
        self._write_completion(
            tests=tests,
            execution=execution,
            js_result=js_result,
            js_status=js_status,
            final_status=final_status,
        )
        return final_status

    @classmethod
    async def _execute_many_async(
        cls: type[Self],
        *,
        argument_sets: tuple[tuple[str, ...], ...],
        cwd: Path,
        program: str | None = None,
        concurrency: int | None = None,
        progress: tuple[str, tuple[float, float]] = (
            "pytest shard",
            (0.2, 0.6),
        ),
    ) -> tuple[CompletedProcess[bytes], ...]:
        """Execute several Python module commands concurrently.

        Args:
            argument_sets: Argument sets.
            cwd: Cwd.
            program: Program.
            concurrency: Maximum simultaneously running commands.
            progress: Activity label and parent-task span for this batch.

        Returns:
            The resulting value.

        """
        finished: list[int] = [0]
        total: int = len(argument_sets)
        durations: list[float] = [0.0 for _index in range(total)]
        semaphore: Semaphore | None = (
            Semaphore(value=concurrency)
            if concurrency is not None and concurrency < total
            else None
        )
        trace(
            step=f"exec batch: {total} commands"
            + (
                f", concurrency {concurrency}" if semaphore is not None else ""
            ),
            depth=2,
        )

        async def tracked(
            *,
            shard: int,
            arguments: tuple[str, ...],
        ) -> CompletedProcess[bytes]:
            """Run one shard and publish its completion progress.

            Args:
                shard: Shard.
                arguments: Arguments.

            Returns:
                The resulting value.

            """
            started: float = monotonic()
            if semaphore is None:
                result: CompletedProcess[bytes] = await cls._execute_async(
                    arguments=arguments,
                    cwd=cwd,
                    program=program,
                )
            else:
                async with semaphore:
                    result = await cls._execute_async(
                        arguments=arguments,
                        cwd=cwd,
                        program=program,
                    )
            durations[shard] = monotonic() - started
            finished[0] += 1
            publish_progress(
                progress=Progress(
                    state="RUNNING",
                    completed=finished[0],
                    total=total,
                    step=progress[0],
                    detail=f"shard {shard} exit {result.returncode}",
                    span=progress[1],
                ),
            )
            return result

        results: tuple[CompletedProcess[bytes], ...] = tuple(
            await gather(
                *(
                    tracked(shard=index, arguments=arguments)
                    for index, arguments in enumerate(iterable=argument_sets)
                ),
            ),
        )
        cls._last_batch_durations = tuple(durations)
        return results

    @classmethod
    def _execution_section_lines(
        cls: type[Self],
        *,
        execution: Mapping[str, JsonValue],
    ) -> list[str]:
        """Render the test-execution report section.

        Args:
            execution: Execution.

        Returns:
            The resulting value.

        """
        failed: JsonValue = execution.get("failed_tests", [])
        warned: JsonValue = execution.get("warnings", [])
        shards: JsonValue = execution.get("shards", [])
        executed: JsonValue = execution.get("tests", [])
        failed_items: list[JsonValue] = (
            failed if isinstance(failed, list) else []
        )
        warning_items: list[JsonValue] = (
            warned if isinstance(warned, list) else []
        )
        executed_items: list[JsonValue] = (
            executed if isinstance(executed, list) else []
        )
        shard_count: int = len(shards) if isinstance(shards, list) else 0
        shard_status: str = "PASS" if execution.get("status") == 0 else "FAIL"
        lines: list[str] = [
            "## Test execution",
            "",
            f"- Pytest shards: **{shard_count}**",
            f"- Shard status: **{shard_status}**",
            f"- Tests run: **{len(executed_items)}**",
            f"- Failed or errored tests: **{len(failed_items)}**",
            f"- Warnings: **{len(warning_items)}**",
            "",
        ]
        if failed_items:
            lines.extend(["### Failed and errored tests", ""])
            item: JsonValue
            for item in failed_items:
                entry: Mapping[str, JsonValue] = (
                    item if isinstance(item, dict) else {}
                )
                detail: JsonValue = entry.get("detail", "")
                suffix: str = f": {detail}" if detail else ""
                origin: str = cls._issue_origin(entry=entry)
                lines.append(
                    f"- `{entry.get('test', 'n/a')}` — {
                        entry.get('kind', 'FAILED')
                    }{suffix}{origin}",
                )
            lines.append("")
        if warning_items:
            lines.extend(["### Warnings", ""])
            for item in warning_items:
                entry = item if isinstance(item, dict) else {}
                origin = cls._issue_origin(entry=entry)
                lines.append(
                    f"- `{entry.get('test', 'n/a')}` — `{
                        entry.get('category', 'Warning')
                    }` at `{entry.get('location', 'n/a')}`: {
                        entry.get('message', '')
                    }{origin}",
                )
            lines.append("")
        return lines

    @classmethod
    def _all_source_files(
        cls: type[Self],
        index: LocalModuleIndex,
    ) -> tuple[Path, ...]:
        """Return indexed local Python source files.

        Args:
            index: Index.

        Returns:
            The resulting value.

        """
        return tuple(map(cls._record_path, index.records))

    @classmethod
    def _cost_counts(
        cls: type[Self],
        *,
        tree: AST,
    ) -> tuple[int, int, int, int, int]:
        """Count cost-bearing constructs inside one parsed test module.

        Args:
            tree: Parsed ``test_*.py`` module.

        Returns:
            Test, async test, parametrized, expensive-call, and fixture
            counts.

        """
        tests: int = 0
        async_tests: int = 0
        parametrized: int = 0
        expensive_calls: int = 0
        fixtures: int = 0
        node: AST
        for node in walk(node=tree):
            if isinstance(node, (FunctionDef, AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    tests += 1
                    async_tests += int(isinstance(node, AsyncFunctionDef))
                    parametrized += sum(
                        isinstance(decorator, Call)
                        and isinstance(decorator.func, Attribute)
                        and (decorator.func.attr == "parametrize")
                        for decorator in node.decorator_list
                    )
                elif node.name.startswith(("setup_", "teardown_", "fixture_")):
                    fixtures += 1
            elif (
                isinstance(node, Call)
                and cls._expensive_call_name(node=node)
                in Constants.expensive_call_names
            ):
                expensive_calls += 1
        return (tests, async_tests, parametrized, expensive_calls, fixtures)

    @classmethod
    def _js_section_lines(
        cls: type[Self],
        *,
        javascript: Mapping[str, JsonValue],
    ) -> list[str]:
        """Render the JavaScript lane report section.

        Args:
            javascript: Javascript.

        Returns:
            The resulting value.

        """
        js_missing: JsonValue = javascript.get("unreached_sources", [])
        js_files: JsonValue = javascript.get("files", [])
        lines: list[str] = [
            "## JavaScript coverage",
            "",
            "| File | Lines | Missing | Coverage |",
            "| --- | ---: | ---: | ---: |",
        ]
        if isinstance(js_files, list):
            lines.extend(map(cls._js_file_row, js_files))
        lines.append("")
        if isinstance(js_missing, list) and js_missing:
            lines.extend(
                [
                    "### JavaScript unreached source files",
                    "",
                    (
                        "These files were not reached during measurement and "
                        "are excluded from the percentages above."
                    ),
                    "",
                    *map(cls._bullet, js_missing),
                    "",
                ],
            )
        return lines

    @classmethod
    def _test_cost(cls: type[Self], *, test: Path) -> int:
        """Estimate pytest execution cost from static test structure.

        The estimate deliberately favors collected-test multiplicity and
        expensive integration-test signals over raw file size. It is only a
        scheduling heuristic and does not change collection or execution.

        Args:
            test: Discovered pytest file.

        Returns:
            Positive deterministic scheduling weight.

        """
        try:
            source: str = test.read_text(encoding="utf-8")
            tree: AST = parse(source=source, filename=str(object=test))
        except (OSError, SyntaxError, UnicodeError):
            try:
                return max(1, test.stat().st_size // 512)
            except OSError:
                return 1
        tests, async_tests, parametrized, expensive_calls, fixtures = (
            cls._cost_counts(tree=tree)
        )
        size_weight: int = max(1, len(source) // 4096)
        return max(
            1,
            tests * 32
            + async_tests * 16
            + parametrized * 48
            + expensive_calls * 12
            + fixtures * 8
            + size_weight,
        )

    @property
    def _work_dir(self: Self) -> Path:
        """The scratch directory holding this run's coverage plumbing.

        Returns:
            The resulting value.

        """
        return self._layout.coverage_artifacts / "tmp"

    @property
    def _data_file(self: Self) -> Path:
        """The absolute coverage data file for this run.

        Returns:
            The resulting value.

        """
        return self._work_dir / ".coverage"

    @property
    def _test_cost_cache_path(self: Self) -> Path:
        """Return the persistent learned test-cost cache path.

        Returns:
            JSON cache file location under ``.exactus-cache``.

        """
        return (
            self._config.root
            / ".exactus-cache"
            / "coverage-tests"
            / CoverageCoreDefaults.test_costs_name
        )

    @staticmethod
    async def _execute_async(
        arguments: tuple[str, ...],
        cwd: Path,
        program: str | None = None,
    ) -> CompletedProcess[bytes]:
        """Execute one Python module command asynchronously.

        Args:
            arguments: Arguments.
            cwd: Cwd.
            program: Program.

        Returns:
            The resulting value.

        """
        target: str = (
            program
            if program is not None
            else environ.get("EXACTUS_PROJECT_PYTHON") or executable
        )
        started: float = monotonic()
        first: str = f" {arguments[0]}" if arguments else ""
        trace(
            step=f"exec: {Path(target).name}{first} — {len(arguments)} argv",
            depth=3,
        )
        plugin_environment: dict[str, str] = {}
        if "exactus_skip_plugin" in arguments:
            for argument in arguments:
                if argument.startswith("--rcfile="):
                    plugin_environment["PYTHONPATH"] = pathsep.join(
                        filter(
                            None,
                            (
                                str(
                                    object=Path(
                                        argument.removeprefix("--rcfile="),
                                    ).parent,
                                ),
                                environ.get("PYTHONPATH", ""),
                            ),
                        ),
                    )
        process: Process = await create_subprocess_exec(
            target,
            *arguments,
            cwd=cwd,
            env=_child_environ(overrides=plugin_environment),
            stdout=PIPE,
            stderr=PIPE,
        )
        out, err = await process.communicate()
        trace(
            step=(
                f"exec: "
                f"{Path(target).name}"
                f" — exit "
                f"{process.returncode}"
                f" in "
                f"{monotonic() - started:.3f}"
                f"s"
            ),
            depth=3,
        )
        return CompletedProcess(
            args=(target, *arguments),
            returncode=cast(typ="int", val=process.returncode),
            stdout=out,
            stderr=err,
        )

    @staticmethod
    async def _execute_program_async(
        program: str,
        arguments: tuple[str, ...],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> CompletedProcess[bytes]:
        """Execute one arbitrary program asynchronously.

        Args:
            program: Program.
            arguments: Arguments.
            cwd: Cwd.
            environment: Environment.

        Returns:
            The resulting value.

        """
        started: float = monotonic()
        trace(
            step=f"exec program: {Path(program).name} — {len(arguments)} argv",
            depth=3,
        )
        process: Process = await create_subprocess_exec(
            program,
            *arguments,
            cwd=cwd,
            env=environment,
            stdout=PIPE,
            stderr=PIPE,
        )
        out, err = await process.communicate()
        trace(
            step=(
                f"exec program: "
                f"{Path(program).name} — exit {process.returncode} in {
                    monotonic() - started:.3f}s"
            ),
            depth=3,
        )
        return CompletedProcess(
            args=(program, *arguments),
            returncode=cast(typ="int", val=process.returncode),
            stdout=out,
            stderr=err,
        )

    @staticmethod
    def _decode_process_output(*, result: CompletedProcess[bytes]) -> str:
        """Decode one completed process's captured stdout and stderr.

        Args:
            result: Result.

        Returns:
            The resulting value.

        """
        stdout_text: str = (result.stdout or b"").decode(
            encoding="utf-8",
            errors="replace",
        )
        stderr_text: str = (result.stderr or b"").decode(
            encoding="utf-8",
            errors="replace",
        )
        return f"{stdout_text}\n=== stderr ===\n{stderr_text}"

    @staticmethod
    def _js_failures(*, text: str) -> tuple[str, ...]:
        """Extract failed test names from Node TAP reporter output.

        Args:
            text: Text.

        Returns:
            The resulting value.

        """
        names: list[str] = []
        line: str
        for line in text.splitlines():
            match: Match[str] | None = (
                CoverageCoreTables.JS_FAILURE_ENTRY.match(string=line)
            )
            if match is None:
                continue
            name: str = match.group("name")
            if name not in names:
                names.append(name)
        return tuple(names)

    @staticmethod
    def _execution_manifest(
        *,
        execution: TestExecution,
    ) -> dict[str, JsonValue]:
        """Render the test-execution outcome as a JSON-ready manifest.

        Args:
            execution: Execution.

        Returns:
            The resulting value.

        """
        return {
            "status": execution.status,
            "duration_seconds": execution.duration_seconds,
            "tests": [
                {**asdict(obj=test), "log": shard.log}
                for shard in execution.shards
                for test in shard.tests
            ],
            "shards": cast(
                typ="list[JsonValue]",
                val=[asdict(obj=shard) for shard in execution.shards],
            ),
            "failed_tests": [
                {**asdict(obj=failure), "log": shard.log}
                for shard in execution.shards
                for failure in shard.failures
            ],
            "skipped_tests": [
                {**asdict(obj=skip), "log": shard.log}
                for shard in execution.shards
                for skip in shard.skipped
            ],
            "warnings": [
                {**asdict(obj=warning), "log": shard.log}
                for shard in execution.shards
                for warning in shard.warnings
            ],
        }

    @staticmethod
    def _issue_origin(*, entry: Mapping[str, JsonValue]) -> str:
        """Render the shard-and-log provenance suffix for one issue.

        Args:
            entry: Entry.

        Returns:
            The resulting value.

        """
        return f" _(shard {entry.get('shard', '?')}, `{
            entry.get('log', 'n/a')
        }`)_"

    @staticmethod
    def _record_path(record: ModuleRecord) -> Path:
        """Return the filesystem path of one module record.

        Args:
            record: Record.

        Returns:
            The resulting value.

        """
        return record.path

    @staticmethod
    def _indent_item(value: Path) -> str:
        """Return one indented coverage-config line for a path.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return f"    {value}"

    @staticmethod
    def _script_line_coverage(
        *,
        path: Path,
        ranges: tuple[tuple[int, int, int], ...],
    ) -> JsFileCoverage:
        """Convert V8 block-coverage ranges into per-line coverage.

        Args:
            path: Path.
            ranges: Ranges.

        Returns:
            The resulting value.

        """
        try:
            source: str = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return JsFileCoverage(covered=frozenset(), executable=frozenset())
        if not ranges or not source:
            return JsFileCoverage(covered=frozenset(), executable=frozenset())
        ranges = _character_ranges(source=source, ranges=ranges)
        bounds: list[int] = sorted(
            {0, len(source)}
            | {start for start, _, _ in ranges}
            | {end for _, end, _ in ranges},
        )
        line_starts: list[int] = [0]
        index: int
        char: str
        for index, char in enumerate(iterable=source):
            if char == "\n":
                line_starts.append(index + 1)
        ascending: tuple[tuple[int, int, int], ...] = tuple(
            sorted(ranges, key=lambda entry: entry[1] - entry[0]),
        )
        covered: set[int] = set()
        executable_lines: set[int] = set()
        bound_index: int
        for bound_index in range(len(bounds) - 1):
            segment_start: int = bounds[bound_index]
            segment_end: int = bounds[bound_index + 1]
            start: int
            end: int
            count: int
            for start, end, count in ascending:
                if start <= segment_start < end:
                    first_line: int = bisect_right(
                        a=line_starts,
                        x=segment_start,
                    )
                    last_line: int = bisect_right(
                        a=line_starts,
                        x=segment_end - 1,
                    )
                    line: int
                    for line in range(first_line, last_line + 1):
                        executable_lines.add(line)
                        if count > 0:
                            covered.add(line)
                    break
        return JsFileCoverage(
            covered=frozenset(covered),
            executable=frozenset(executable_lines),
        )

    @staticmethod
    def _script_url_path(*, url: JsonValue) -> Path | None:
        """Resolve one V8 script URL to a filesystem path.

        Args:
            url: Url.

        Returns:
            The resulting value.

        """
        if not isinstance(url, str) or not url.startswith("file:"):
            return None
        return Path(unquote(string=urlparse(url=url).path)).resolve()

    @staticmethod
    def _script_ranges(
        *,
        script: Mapping[str, JsonValue],
    ) -> tuple[tuple[int, int, int], ...]:
        """Extract coverage ranges from one V8 script entry.

        Args:
            script: Script.

        Returns:
            The resulting value.

        """
        functions: JsonValue = script.get("functions", [])
        if not isinstance(functions, list):
            return ()
        ranges: list[tuple[int, int, int]] = []
        function: JsonValue
        for function in functions:
            if not isinstance(function, dict):
                continue
            raw_ranges: JsonValue = function.get("ranges", [])
            if not isinstance(raw_ranges, list):
                continue
            entry: JsonValue
            for entry in raw_ranges:
                if not isinstance(entry, dict):
                    continue
                start: JsonValue = entry.get("startOffset")
                end: JsonValue = entry.get("endOffset")
                count: JsonValue = entry.get("count")
                if (
                    isinstance(start, int)
                    and isinstance(end, int)
                    and isinstance(count, int)
                    and (start < end)
                ):
                    ranges.append((start, end, count))
        return tuple(ranges)

    @staticmethod
    def _await_v8_dumps(*, directory: Path, timeout: float = 5.0) -> None:
        """Wait briefly for straggler Node children to flush V8 dumps.

        Args:
            directory: Directory.
            timeout: Timeout.

        """
        deadline: float = monotonic() + timeout
        quiet_until: float = monotonic() + 0.2
        seen: int = len(tuple(directory.glob(pattern="*")))
        while monotonic() < quiet_until and monotonic() < deadline:
            count: int = len(tuple(directory.glob(pattern="*")))
            if count != seen:
                seen = count
                quiet_until = monotonic() + 0.2
            sleep(0.01)

    @staticmethod
    def _unreached_js_entry(*, path: Path) -> JsFileCoverage:
        """Approximate executable lines for a JavaScript file no test ran.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        try:
            source: str = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return JsFileCoverage(covered=frozenset(), executable=frozenset())
        executable_lines: set[int] = set()
        number: int
        text: str
        for number, text in enumerate(iterable=source.splitlines(), start=1):
            stripped: str = text.strip()
            if stripped and (not stripped.startswith("//")):
                executable_lines.add(number)
        return JsFileCoverage(
            covered=frozenset(),
            executable=frozenset(executable_lines),
        )

    @staticmethod
    def _js_percent(coverage: JsFileCoverage) -> float:
        """Return the covered percentage of one JavaScript file.

        Args:
            coverage: Coverage.

        Returns:
            The resulting value.

        """
        if not coverage.executable:
            return 100.0
        return round(
            number=100.0 * len(coverage.covered) / len(coverage.executable),
            ndigits=2,
        )

    @staticmethod
    def _expensive_call_name(*, node: Call) -> str:
        """Return the invoked attribute or bare name of one call.

        Args:
            node: Call node to inspect.

        Returns:
            Callable attribute or identifier name; empty otherwise.

        """
        function: AST = node.func
        if isinstance(function, Attribute):
            return function.attr
        if isinstance(function, Name):
            return function.id
        return ""

    @staticmethod
    def _js_summary_lines(*, javascript: Mapping[str, JsonValue]) -> list[str]:
        """Render the JavaScript lane summary bullet lines.

        Args:
            javascript: Javascript.

        Returns:
            The resulting value.

        """
        js_unreached: JsonValue = javascript.get("unreached_sources", [])
        js_unreached_count: int = (
            len(js_unreached) if isinstance(js_unreached, list) else 0
        )
        return [
            f"- JavaScript files measured: **{
                javascript.get(('files_measured'), 0)
            }**",
            f"- JavaScript line coverage: **{
                javascript.get(('percent_covered'), 'n/a')
            }%**",
            f"- JavaScript unreached sources: **{js_unreached_count}**",
        ]

    @staticmethod
    def _js_file_row(entry: JsonValue) -> str:
        """Render one JavaScript file coverage table row.

        Args:
            entry: Entry.

        Returns:
            The resulting value.

        """
        values: dict[str, JsonValue] = entry if isinstance(entry, dict) else {}
        percent: JsonValue = values.get(
            "percent_covered_display",
            values.get("percent_covered", "n/a"),
        )
        return "".join(
            (
                f"| `{values.get('path', 'n/a')}` | ",
                f"{values.get('num_statements', 'n/a')} | ",
                f"{values.get('missing_lines', 'n/a')} | ",
                f"{percent}% |",
            ),
        )

    @staticmethod
    def _bullet(item: JsonValue) -> str:
        """Return one Markdown bullet line for a JSON value.

        Args:
            item: Item.

        Returns:
            The resulting value.

        """
        if isinstance(item, dict) and isinstance(item.get("file"), str):
            module: JsonValue = item.get("module")
            suffix: str = f" (module `{module}`)" if module else ""
            return f"- `{item['file']}`{suffix}"
        return f"- `{item}`"

    @staticmethod
    def _test_group_name(*, test: str) -> str:
        """Return the TESTS report group for a root-relative test path.

        Args:
            test: Test.

        Returns:
            The resulting value.

        """
        directories: tuple[str, ...] = tuple(test.split(sep="/")[:-1])
        if not directories:
            return "ROOT"
        if directories[:2] == ("exactus", "tests"):
            directories = directories[1:]
        while directories[:1] == ("tests",) and directories[1:2] in (
            ("common",),
            ("exactus",),
            ("scripts",),
            ("src",),
        ):
            directories = directories[:1] + directories[2:]
        return "_".join(directories[:2])

    @staticmethod
    def _group_summary(
        *,
        name: str,
        files: list[str],
        executed: dict[str, list[tuple[str, str]]],
    ) -> dict[str, JsonValue]:
        """Count the outcomes of one test group.

        Args:
            name: Name.
            files: Files.
            executed: Executed.

        Returns:
            The resulting value.

        """
        outcomes: Counter[str] = Counter(
            (
                outcome
                for test in files
                for _, outcome in executed.get(test, [])
            ),
        )
        return {
            "group": name,
            "files": len(files),
            "tests": sum(outcomes.values()),
            "passed": outcomes["PASSED"],
            "failed": outcomes["FAILED"] + outcomes["ERROR"],
            "skipped": outcomes["SKIPPED"],
        }

    @staticmethod
    def _group_execution(
        *,
        selected: tuple[str, ...],
        execution: TestExecution,
    ) -> TestExecution:
        """Select group outcomes without inheriting unrelated failures.

        Args:
            selected: Selected.
            execution: Execution.

        Returns:
            The resulting value.

        """
        shards: list[ShardOutcome] = []
        for shard in execution.shards:
            tests: tuple[ExecutedTest, ...] = tuple(
                entry
                for entry in shard.tests
                if entry.test.partition("::")[0] in selected
            )
            failures: tuple[TestFailure, ...] = tuple(
                entry
                for entry in shard.failures
                if entry.test.partition("::")[0] in selected
            )
            warnings: tuple[TestWarning, ...] = tuple(
                entry
                for entry in shard.warnings
                if entry.test.partition("::")[0] in selected
            )
            skipped: tuple[TestFailure, ...] = tuple(
                entry
                for entry in shard.skipped
                if entry.test.partition("::")[0] in selected
            )
            if (
                not tests
                and (not failures)
                and (not warnings)
                and (not skipped)
            ):
                continue
            status: int = (
                shard.returncode
                if shard.returncode not in {0, 1}
                else int(
                    bool(failures)
                    or any(
                        entry.outcome in {"FAILED", "ERROR"} for entry in tests
                    ),
                )
            )
            shards.append(
                replace(
                    shard,
                    tests=tests,
                    failures=failures,
                    warnings=warnings,
                    skipped=skipped,
                    collected=len(tests),
                    returncode=status,
                ),
            )
        status = next(
            (shard.returncode for shard in shards if shard.returncode),
            execution.status if not shards else 0,
        )
        return TestExecution(
            shards=tuple(shards),
            status=status,
            duration_seconds=execution.duration_seconds,
        )

    @staticmethod
    def _exclusive_shard(*, shard: tuple[str, ...]) -> bool:
        """Return whether a package-wide meta-test needs an idle workspace.

        Args:
            shard: File paths or pytest node IDs assigned to one process.

        Returns:
            Whether the shard contains a test directly under
            ``tests/packages``.

        """
        item: str
        for item in shard:
            path: Path = Path(item.split(sep="::", maxsplit=1)[0])
            parts: tuple[str, ...] = path.parts
            index: int
            for index in range(len(parts) - 2):
                if parts[index : index + 2] == ("tests", "packages"):
                    return len(parts[index + 2 :]) == 1
        return False

    @staticmethod
    def _node_isolation_group(*, relative: str) -> str:
        """Return the import-isolation group for one test path.

        Standalone projects conventionally stored below ``tests/packages``
        can publish the same top-level module names as the host application.
        Each such project therefore gets its own pytest process; ordinary
        host tests share the main parallel pool.

        Args:
            relative: Project-relative test file or node ID path.

        Returns:
            Stable isolation-group name.

        """
        parts: tuple[str, ...] = Path(relative).parts
        index: int
        for index in range(len(parts) - 2):
            if parts[index : index + 2] == ("tests", "packages"):
                return f"packages/{parts[index + 2]}"
        return "shared"

    def _record_test_output(
        self: Self,
        *,
        results: tuple[CompletedProcess[bytes], ...],
        duration_seconds: float = 0.0,
    ) -> TestExecution:
        """Persist per-shard logs and parse failures and warnings.

        Args:
            results: Results.
            duration_seconds: Duration seconds.

        Returns:
            The resulting value.

        """
        log_dir: Path = (
            self._layout.tests_artifacts
            / CoverageCoreTables.SHARD_LOG_DIRECTORY
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        outcomes: list[ShardOutcome] = []
        index: int
        result: CompletedProcess[bytes]
        for index, result in enumerate(iterable=results):
            text: str = self._decode_process_output(result=result)
            log_name: str = f"shard-{index:03}.log"
            _ = consume(
                value=(log_dir / log_name).write_text(
                    data=text if text.endswith("\n") else f"{text}\n",
                    encoding="utf-8",
                ),
            )
            collected: int | None = self.pytest_collected(text=text)
            tests: tuple[ExecutedTest, ...] = self.pytest_tests(
                text=text,
                shard=index,
            )
            failures: tuple[TestFailure, ...] = self.pytest_failures(
                text=text,
                shard=index,
                root=self._config.root,
            )
            warnings: tuple[TestWarning, ...] = self.pytest_warnings(
                text=text,
                shard=index,
            )
            skipped: tuple[TestFailure, ...] = self.pytest_skips(
                text=text,
                shard=index,
            )
            outcomes.append(
                ShardOutcome(
                    index=index,
                    returncode=result.returncode,
                    log=(log_dir / log_name)
                    .relative_to(self._layout.root)
                    .as_posix(),
                    collected=collected,
                    tests=tests,
                    failures=failures,
                    warnings=warnings,
                    skipped=skipped,
                ),
            )
            trace(
                step=(
                    f"shard "
                    f"{index}"
                    f": exit "
                    f"{result.returncode}"
                    f" — "
                    f"{len(tests)}"
                    f" tests, "
                    f"{len(failures)}"
                    f" failures, "
                    f"{len(skipped)}"
                    f" skipped, "
                    f"{len(warnings)}"
                    f" warnings"
                ),
                depth=3,
            )
        status: int = next(
            (outcome.returncode for outcome in outcomes if outcome.returncode),
            0,
        )
        return TestExecution(
            shards=tuple(outcomes),
            status=status,
            duration_seconds=round(number=duration_seconds, ndigits=3),
        )

    def _write_coverage_config(
        self: Self,
        *,
        name: str,
        omitted: tuple[Path, ...] = (),
    ) -> Path:
        """Write one generated coverage configuration.

        Args:
            name: Name.
            omitted: Omitted.

        Returns:
            The resulting value.

        """
        self._work_dir.mkdir(parents=True, exist_ok=True)
        config_path: Path = self._work_dir / name
        source_lines: str = "\n".join(
            map(self._indent_item, self._config.source_roots),
        )
        source_root_names: frozenset[str] = frozenset(
            root.name for root in self._config.source_roots
        )
        patterns: tuple[str, ...] = (
            *map(self._indent_item, omitted),
            *(
                f"    */{directory}/**"
                for directory in sorted(self._config.excluded_dirs)
                if directory not in source_root_names
            ),
            *(
                ()
                if any(
                    root.name in CoverageCoreTables.TEST_DIR_NAMES
                    for root in self._config.source_roots
                )
                else (
                    "    */test_*.py",
                    *(
                        f"    */{directory}/**/conftest.py"
                        for directory in sorted(
                            CoverageCoreTables.TEST_DIR_NAMES,
                        )
                    ),
                )
            ),
        )
        omit_lines: tuple[str, ...] = ("omit =", "\n".join(patterns))
        parallel_line: tuple[str, ...] = (
            ("parallel = True",) if self._config.jobs > 1 else ()
        )
        _ = consume(
            value=config_path.write_text(
                data="\n".join(
                    (
                        "[run]",
                        f"branch = {self._config.branch}",
                        "concurrency = thread, greenlet"
                        if find_spec(name="greenlet") is not None
                        else "concurrency = thread",
                        "patch = subprocess",
                        *parallel_line,
                        f"data_file = {self._data_file}",
                        "source =",
                        source_lines,
                        *omit_lines,
                        "",
                        "[report]",
                        "show_missing = True",
                        "skip_empty = False",
                        *omit_lines,
                        "",
                    ),
                ),
                encoding="utf-8",
            ),
        )
        trace(
            step=(
                f"config: {name} written — {len(omitted)} omitted sources, "
                f"{len(self._config.source_roots)} source roots"
            ),
            depth=3,
        )
        return config_path

    def _executed_paths(self: Self) -> frozenset[Path]:
        """Return source files with at least one executed line.

        Returns:
            The resulting value.

        """
        if not self._data_file.is_file():
            return frozenset()
        _ = activate_exactus_tool_bundle(root=Path.cwd())
        coverage_module: ModuleType = import_module(name="coverage")
        data_type: type[CoverageData] = cast(
            typ="type[CoverageData]",
            val=coverage_module.CoverageData,
        )
        data: CoverageData = data_type(basename=str(object=self._data_file))
        data.read()
        return frozenset(
            Path(measured).resolve()
            for measured in data.measured_files()
            if data.lines(filename=measured)
        )

    def _omitted_paths(
        self: Self,
        *,
        index: LocalModuleIndex,
        graph: ImportGraph,
    ) -> tuple[Path, ...]:
        """Return indexed sources that no test reached.

        Args:
            index: Index.
            graph: Graph.

        Returns:
            The resulting value.

        """
        reached: frozenset[Path] = (
            frozenset(map(self._record_path, graph.targets))
            | self._executed_paths()
        )
        unreached: tuple[Path, ...] = tuple(
            path
            for path in self._all_source_files(index=index)
            if path not in reached
        )
        trace(
            step=(
                f"unreached: {len(unreached)} of {
                    len(self._all_source_files(index=index))
                } source files not "
                f"reached"
            ),
            depth=2,
        )
        return unreached

    def _source_excluded(self: Self, path: Path) -> bool:
        """Return whether a path matches a configured source exclusion.

        Args:
            path: Candidate measured source.

        Returns:
            ``True`` when a root-relative exclude glob rejects the path.

        """
        if not self._config.source_excludes or not path.is_relative_to(
            self._config.root,
        ):
            return False
        relative: str = path.relative_to(self._config.root).as_posix()
        return any(
            fnmatch(name=relative, pat=pattern)
            for pattern in self._config.source_excludes
        )

    def _js_source_allowed(self: Self, path: Path) -> bool:
        """Return whether a JavaScript path is eligible measured source.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        if (
            path.suffix not in CoverageCoreTables.JS_SOURCE_SUFFIXES
            or self._source_excluded(path=path)
        ):
            return False
        source_roots: tuple[Path, ...] = tuple(
            source_root
            for source_root in self._config.source_roots
            if path.is_relative_to(source_root)
        )
        if not source_roots:
            return False
        if any(
            part in CoverageCoreTables.TEST_DIR_NAMES or part.startswith(".")
            for part in path.relative_to(self._config.root).parts[:-1]
        ):
            return False
        source_root: Path = max(source_roots, key=lambda root: len(root.parts))
        part: str
        for part in path.relative_to(source_root).parts[:-1]:
            if (
                part.startswith(".")
                or part in self._config.excluded_dirs
                or part in CoverageCoreTables.TEST_DIR_NAMES
            ):
                return False
        return path.is_file() and ".test." not in path.name

    def _js_sources(self: Self) -> tuple[Path, ...]:
        """Return every measured JavaScript source under the source roots.

        Returns:
            The resulting value.

        """
        candidates: list[Path] = []
        source_root: Path
        for source_root in self._config.source_roots:
            path: Path
            directory: Path
            dirnames: list[str]
            filenames: list[str]
            entries: Iterable[tuple[Path, list[str], list[str]]] = (
                ((source_root.parent, [], [source_root.name]),)
                if source_root.is_file()
                else source_root.walk()
            )
            for directory, dirnames, filenames in entries:
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not is_reports_tree(directory=directory / name)
                ]
                for filename in filenames:
                    path = directory / filename
                    resolved: Path = path.resolve()
                    if self._js_source_allowed(path=resolved):
                        candidates.append(resolved)
        return tuple(
            dict.fromkeys(
                sorted(candidates, key=lambda path: path.as_posix()),
            ),
        )

    def _merge_v8_script(
        self: Self,
        *,
        script: JsonValue,
        merged: dict[Path, JsFileCoverage],
    ) -> None:
        """Merge one V8 script entry into per-file line coverage.

        Args:
            script: Script.
            merged: Merged.

        """
        if not isinstance(script, dict):
            return
        path: Path | None = self._script_url_path(url=script.get("url"))
        if path is None or not self._js_source_allowed(path=path):
            return
        coverage: JsFileCoverage = self._script_line_coverage(
            path=path,
            ranges=self._script_ranges(script=script),
        )
        previous: JsFileCoverage | None = merged.get(path)
        merged[path] = JsFileCoverage(
            covered=coverage.covered
            | (previous.covered if previous else frozenset[int]()),
            executable=coverage.executable
            | (previous.executable if previous else frozenset[int]()),
        )

    def _collect_v8_coverage(
        self: Self,
        *,
        directory: Path,
    ) -> dict[Path, JsFileCoverage]:
        """Merge V8 coverage dumps into per-file line coverage.

        Args:
            directory: Directory.

        Returns:
            The resulting value.

        """
        merged: dict[Path, JsFileCoverage] = {}
        dump_path: Path
        for dump_path in sorted(
            directory.glob(pattern="*.json"),
            key=lambda path: path.as_posix(),
        ):
            try:
                payload: dict[str, JsonValue] = cast(
                    typ="dict[str, JsonValue]",
                    val=loads(s=dump_path.read_text(encoding="utf-8")),
                )
            except (OSError, ValueError):
                continue
            scripts: JsonValue = payload.get("result", [])
            if not isinstance(scripts, list):
                continue
            script: JsonValue
            for script in scripts:
                self._merge_v8_script(script=script, merged=merged)
        return merged

    def _run_js_coverage(self: Self) -> JsCoverageResult | None:
        """Run JavaScript tests under V8 coverage and merge the dumps.

        Returns:
            The resulting value.

        """
        if not self._config.measure_js:
            trace(step="javascript lane: disabled by config", depth=2)
            return None
        tests: tuple[Path, ...] = self.discover_js_tests()
        if not tests:
            trace(step="javascript lane: no node:test files", depth=2)
            return None
        test_names: tuple[str, ...] = tuple(map(self._relative_string, tests))
        if (
            node := exactus_tool_prefix(tool="node", root=self._config.root)
        ) is None:
            trace(step="javascript lane: node unavailable", depth=2)
            return JsCoverageResult(
                tests=test_names,
                files={},
                unreached=(),
                status=2,
                detail="node executable is unavailable",
            )
        trace(
            step=f"javascript lane: node --test {len(test_names)} files",
            depth=2,
        )
        v8_dir: Path = self._work_dir / CoverageCoreDefaults.v8_coverage_dir
        v8_dir.mkdir(parents=True, exist_ok=True)
        stale: Path
        for stale in v8_dir.glob(pattern="*.json"):
            stale.unlink(missing_ok=True)
        loader: Path = self._config.root / CoverageCoreTables.JS_LOADER
        arguments: tuple[str, ...] = (
            *node[1:],
            *(
                ("--import", f"./{CoverageCoreTables.JS_LOADER}")
                if loader.is_file()
                else ()
            ),
            "--test",
            *test_names,
        )
        process: CompletedProcess[bytes] = self.execute_program(
            program=node[0],
            arguments=arguments,
            cwd=self._config.root,
            environment=_child_environ(
                overrides={"NODE_V8_COVERAGE": str(object=v8_dir)},
            ),
        )
        status: int = process.returncode
        js_output: str = self._decode_process_output(result=process)
        js_sites: tuple[NamedFailure, ...] = NodeTestFailures.parse(
            text=js_output,
            root=self._config.root,
        )
        js_failures: tuple[str, ...] = tuple(
            dict.fromkeys(
                (
                    *self._js_failures(text=js_output),
                    *(failure.name for failure in js_sites),
                ),
            ),
        )
        self._write_js_tests(
            command=(node[0], *arguments),
            process=process,
            tests=test_names,
            failures=js_failures,
        )
        self._await_v8_dumps(directory=v8_dir)
        merged: dict[Path, JsFileCoverage] = self._collect_v8_coverage(
            directory=v8_dir,
        )
        trace(
            step=(
                f"javascript: "
                f"{len(merged)} v8 files merged, "
                f"{len(js_failures)} failures — exit {status}"
            ),
            depth=2,
        )
        rmtree(path=v8_dir, ignore_errors=True)
        measured: dict[str, JsFileCoverage] = {
            self._relative_string(path=path): coverage
            for path, coverage in merged.items()
        }
        unreached: tuple[str, ...] = tuple(
            sorted(
                self._relative_string(path=path)
                for path in self._js_sources()
                if path not in merged
            ),
        )
        if self._config.include_unreached:
            source_path: Path
            for source_path in self._js_sources():
                name: str = self._relative_string(path=source_path)
                if name not in measured:
                    measured[name] = self._unreached_js_entry(path=source_path)
        self._layout.coverage_artifacts.mkdir(parents=True, exist_ok=True)
        _ = consume(
            value=(
                self._layout.coverage_artifacts
                / CoverageCoreDefaults.raw_js_report_name
            ).write_text(
                data=dumps(
                    obj={
                        "tests": list(test_names),
                        "status": status,
                        "files": {
                            name: {
                                "covered_lines": sorted(entry.covered),
                                "executable_lines": sorted(entry.executable),
                            }
                            for name, entry in sorted(measured.items())
                        },
                        "unreached_sources": list(unreached),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            ),
        )
        return JsCoverageResult(
            tests=test_names,
            files=measured,
            unreached=unreached,
            status=status,
            failures=js_failures,
            failure_sites=js_sites,
        )

    def _write_js_tests(
        self: Self,
        *,
        command: tuple[str, ...],
        process: CompletedProcess[bytes],
        tests: tuple[str, ...],
        failures: tuple[str, ...],
    ) -> None:
        """Write the JavaScript test run as ``ARTIFACTS/TESTS/js-tests.json``.

        Args:
            command: Command.
            process: Process.
            tests: Tests.
            failures: Failures.

        """
        document: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val={
                "schema": CoverageCoreDefaults.js_tests_schema,
                "command": list(command),
                "cwd": str(object=self._config.root),
                "exit_code": process.returncode,
                "tests": list(tests),
                "failed_tests": list(failures),
                "stdout_lines": list(
                    (process.stdout or b"")
                    .decode(encoding="utf-8", errors="replace")
                    .splitlines(),
                ),
                "stderr_lines": list(
                    (process.stderr or b"")
                    .decode(encoding="utf-8", errors="replace")
                    .splitlines(),
                ),
            },
        )
        self._layout.tests_artifacts.mkdir(parents=True, exist_ok=True)
        _ = consume(
            value=(
                self._layout.tests_artifacts
                / CoverageCoreDefaults.js_tests_name
            ).write_text(
                data=dumps(obj=document, indent=2) + "\n",
                encoding="utf-8",
            ),
        )

    def _js_manifest(
        self: Self,
        *,
        result: JsCoverageResult,
    ) -> dict[str, JsonValue]:
        """Build the JavaScript lane manifest for reports and bundles.

        Args:
            result: Result.

        Returns:
            The resulting value.

        """
        file_entries: list[JsonValue] = []
        name: str
        coverage: JsFileCoverage
        for name, coverage in sorted(result.files.items()):
            percent: float = self._js_percent(coverage=coverage)
            uncovered: tuple[int, ...] = tuple(
                sorted(coverage.executable - coverage.covered),
            )
            file_entries.append(
                {
                    "path": name,
                    "num_statements": len(coverage.executable),
                    "covered_lines": len(coverage.covered),
                    "missing_lines": len(uncovered),
                    "uncovered_lines": cast(
                        typ="list[JsonValue]",
                        val=list(uncovered),
                    ),
                    "snippets": self._file_snippets(
                        relative=name,
                        missing=uncovered,
                    ),
                    "percent_covered": percent,
                    "percent_covered_display": f"{percent:.2f}",
                },
            )
        executable_count: int = sum(
            len(entry.executable) for entry in result.files.values()
        )
        covered_count: int = sum(
            len(entry.covered) for entry in result.files.values()
        )
        located: frozenset[str] = frozenset(
            failure.name for failure in result.failure_sites
        )
        manifest: dict[str, JsonValue] = {
            "tests": cast(typ="list[JsonValue]", val=list(result.tests)),
            "status": result.status,
            "detail": result.detail,
            "files_measured": len(result.files),
            "files": file_entries,
            "executable_lines": executable_count,
            "covered_lines": covered_count,
            "percent_covered": round(
                number=100.0 * covered_count / executable_count,
                ndigits=2,
            )
            if executable_count
            else 100.0,
            "unreached_sources": cast(
                typ="list[JsonValue]",
                val=list(result.unreached),
            ),
            "failed_tests": cast(
                typ="list[JsonValue]",
                val=list(result.failures),
            ),
            "failures": [
                *(
                    {
                        "name": failure.name,
                        "path": failure.site.path,
                        "line": failure.site.line,
                        "reason": failure.site.reason,
                    }
                    for failure in result.failure_sites
                ),
                *(
                    {"name": name, "path": None, "line": None, "reason": ""}
                    for name in result.failures
                    if name not in located
                ),
            ],
            "raw_report": CoverageCoreDefaults.raw_js_report_name,
        }
        return manifest

    def _js_gate_failed(
        self: Self,
        *,
        javascript: Mapping[str, JsonValue] | None,
    ) -> bool:
        """Apply the configured total and per-file gates to JavaScript.

        Args:
            javascript: Javascript.

        Returns:
            The resulting value.

        """
        if javascript is None:
            return False
        percent: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = javascript.get("percent_covered")
        if (
            self._config.fail_under is not None
            and isinstance(percent, int | float)
            and (percent < self._config.fail_under)
        ):
            return True
        minimum: float | None = self._config.per_file_minimum
        files: (
            bool
            | dict[str, JsonValue]
            | float
            | int
            | list[JsonValue]
            | str
            | None
        ) = javascript.get("files")
        if minimum is None or not isinstance(files, list):
            return False
        for entry in files:
            if isinstance(entry, dict):
                measured: JsonValue | None = entry.get("percent_covered")
                if isinstance(measured, int | float) and measured < minimum:
                    return True
        return False

    def _file_shortfalls(
        self: Self,
        *,
        coverage_report: dict[str, JsonValue],
    ) -> list[tuple[str, float, int]]:
        """List source files below the per-file coverage gate.

        Args:
            coverage_report: Coverage report.

        Returns:
            The resulting value.

        """
        minimum: float | None = self._config.per_file_minimum
        files: JsonValue = coverage_report.get("files")
        if minimum is None or not isinstance(files, dict):
            return []
        found: list[tuple[str, float, int]] = []
        for path, entry in files.items():
            summary: JsonValue = (
                entry.get("summary") if isinstance(entry, dict) else None
            )
            if not isinstance(summary, dict):
                continue
            percent: JsonValue = summary.get("percent_covered", 100.0)
            missing: JsonValue = summary.get("missing_lines", 0)
            if (
                isinstance(percent, int | float)
                and isinstance(missing, int)
                and (percent < minimum)
            ):
                found.append((path, float(percent), missing))
        return sorted(found, key=lambda item: item[1])

    def _file_snippets(
        self: Self,
        *,
        relative: str,
        missing: Sequence[int],
    ) -> dict[str, JsonValue]:
        """Embed source hunks around uncovered lines for the web report.

        Args:
            relative: Relative.
            missing: Missing.

        Returns:
            The resulting value.

        """
        path: Path = self._config.root / relative
        language: str | None = CoverageCoreTables.SNIPPET_LANGUAGES.get(
            path.suffix.lower(),
        )
        if language is None or not missing:
            return {}
        try:
            lines: list[str] = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return {}
        context: int = max(0, self._config.context_lines)
        missing_set: frozenset[int] = frozenset(missing)
        windows: list[list[int]] = []
        for point in sorted(missing_set):
            start: int = max(1, point - context)
            end: int = min(len(lines), point + context)
            if start > len(lines):
                continue
            if windows and start <= windows[-1][1] + 1:
                windows[-1][1] = max(windows[-1][1], end)
            else:
                windows.append([start, end])
        hunks: list[JsonValue] = []
        embedded: int = 0
        truncated: bool = False
        window: list[int]
        for window in windows:
            room: int = CoverageCoreTables.SNIPPET_MAX_LINES - embedded
            if room <= 0:
                truncated = True
                break
            first: int
            last: int
            first, last = window
            last = min(last, first + room - 1)
            truncated = truncated or last < window[1]
            entries: list[JsonValue] = [
                {
                    "n": number,
                    "text": lines[number - 1],
                    "hit": number in missing_set,
                }
                for number in range(first, last + 1)
            ]
            embedded += len(entries)
            hunks.append({"start": first, "lines": entries})
            if truncated:
                break
        return {
            "language": language,
            "context": context,
            "truncated": truncated,
            "hunks": hunks,
        }

    def _relative_string(self: Self, path: Path) -> str:
        """Return the project-root-relative string form of one path.

        Args:
            path: Path.

        Returns:
            The resulting value.

        """
        return str(object=path.relative_to(self._config.root))

    def _target_entry(self: Self, record: ModuleRecord) -> dict[str, str]:
        """Return the JSON manifest entry for one coverage target.

        Args:
            record: Record.

        Returns:
            The resulting value.

        """
        return {
            "module": record.name,
            "file": str(object=record.path.relative_to(self._config.root)),
        }

    def _write_manifest(
        self: Self,
        graph: ImportGraph,
        *,
        unreached: tuple[Path, ...] = (),
        omitted: tuple[Path, ...] = (),
        meaningful: MeaningfulResult | None = None,
        excused: tuple[Path, ...] = (),
    ) -> None:
        """Write a manifest of tests and resolved coverage targets.

        Args:
            graph: Graph.
            unreached: Unreached.
            omitted: Omitted.
            meaningful: Meaningful.
            excused: Measured sources excused from the per-file gate.

        """
        tests_list: list[str] = list(map(self._relative_string, graph.tests))
        targets_list: list[dict[str, str]] = list(
            map(self._target_entry, graph.targets),
        )
        meaningful_config: MeaningfulConfig = self._config.meaningful
        self._layout.coverage_artifacts.mkdir(parents=True, exist_ok=True)
        _ = consume(
            value=self._layout.coverage_artifacts.joinpath(
                CoverageCoreDefaults.import_graph_name,
            ).write_text(
                data=dumps(
                    obj={
                        "tests": tests_list,
                        "targets": targets_list,
                        "ignored_non_local_imports": list(
                            graph.ignored_imports,
                        ),
                        "unreached_sources": list(
                            map(self._relative_string, unreached),
                        ),
                        "omitted_sources": list(
                            map(self._relative_string, omitted),
                        ),
                        "excused_sources": list(
                            map(self._relative_string, excused),
                        ),
                        "meaningful": {
                            "mode": meaningful_config.mode,
                            "minimum_level": (
                                meaningful_config.minimum_level.value
                            ),
                            "unclassified": meaningful_config.unclassified,
                            "artifact": "ARTIFACTS/COVERAGE/"
                            + CoverageCoreDefaults.meaningful_name,
                            "counts": meaningful.artifact.get("counts", {}),
                            "rows": list(meaningful.rows),
                            "failures": meaningful.artifact.get(
                                "failures",
                                [],
                            ),
                        }
                        if meaningful is not None
                        else None,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            ),
        )
        trace(
            step=(
                f"manifest: {len(tests_list)} tests, "
                f"{len(targets_list)} targets, {len(unreached)} unreached, "
                f"{len(omitted)} omitted"
            ),
            depth=2,
        )

    def _coverage_arguments(
        self: Self,
        items: tuple[str, ...],
        config_path: Path,
        *,
        timing_output: Path | None = None,
        use_bundle: bool = False,
    ) -> tuple[str, ...]:
        """Build arguments for the single combined coverage test run.

        Args:
            items: Items.
            config_path: Config path.
            timing_output: Optional per-file timing telemetry destination.
            use_bundle: Use bundle.

        Returns:
            The resulting value.

        """
        test_args: list[str] = list(items)
        _ = (config_path.parent / "__init__.py").write_text(
            data=(
                dedent(
                    text=(
                        "    # Copyright (c) 2026 Project contributors\n    "
                        '"""Generated coverage subprocess helpers."""\n    '
                    ),
                )
            ),
            encoding="utf-8",
        )
        _ = (config_path.parent / "exactus_skip_plugin.py").write_text(
            data=files(anchor="exactus.tools.coverage_tests")
            .joinpath("skip_plugin.py")
            .read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return (
            *(() if use_bundle else ("-m",)),
            "coverage",
            "run",
            f"--rcfile={config_path}",
            "-m",
            "pytest",
            "-v",
            "-p",
            "exactus_skip_plugin",
            *(
                ("--exactus-timings-output", str(object=timing_output))
                if timing_output is not None
                else ()
            ),
            *test_args,
            *self._config.pytest_args,
        )

    def _run_test_shards(
        self: Self,
        *,
        tests: tuple[Path, ...],
        collect_config: Path,
    ) -> TestExecution:
        """Run test shards under coverage and record their output.

        Args:
            tests: Tests.
            collect_config: Collect config.

        Returns:
            The resulting value.

        """
        items: tuple[str, ...] = (
            self._collect_pytest_nodes(tests=tests)
            if self._config.shard_by == "node"
            else tuple(self._relative_string(path=test) for test in tests)
        )
        shards: tuple[tuple[str, ...], ...] = (
            self._isolated_node_shards(tests=tests, nodes=items)
            if self._config.shard_by == "node"
            else self._balanced_test_shards(tests=tests, items=items)
        )
        regular_shards: tuple[tuple[str, ...], ...] = tuple(
            shard for shard in shards if not self._exclusive_shard(shard=shard)
        )
        exclusive_shards: tuple[tuple[str, ...], ...] = tuple(
            shard for shard in shards if self._exclusive_shard(shard=shard)
        )
        shards = (*regular_shards, *exclusive_shards)
        trace(
            step=(
                f"test shards: {len(shards)} {self._config.shard_by} "
                f"shards over {len(items)} test items — sizes "
            )
            + ", ".join(str(object=len(shard)) for shard in shards),
            depth=2,
        )
        bundle: Path | None = (
            resolve_exactus_tool_bundle(root=self._config.root)
            if find_spec(name="pytest") is None
            or find_spec(name="coverage") is None
            else None
        )
        if bundle is not None:
            trace(step=f"test shards: tool bundle {bundle}", depth=3)
        timing_paths: tuple[Path, ...] = tuple(
            collect_config.parent / f"pytest-timings-{index}.json"
            for index in range(len(shards))
        )
        started: float = monotonic()
        argument_sets: tuple[tuple[str, ...], ...] = tuple(
            (
                self._coverage_arguments(
                    items=shard,
                    config_path=collect_config,
                    timing_output=timing_paths[index],
                    use_bundle=bundle is not None,
                )
                for index, shard in enumerate(iterable=shards)
            ),
        )
        regular_count: int = len(regular_shards)
        regular_statuses: tuple[CompletedProcess[bytes], ...] = (
            self.execute_many(
                argument_sets=argument_sets[:regular_count],
                cwd=self._config.root,
                program=str(object=bundle) if bundle is not None else None,
                concurrency=self._config.jobs,
            )
        )
        if exclusive_shards:
            trace(
                step=(
                    f"test shards: run "
                    f"{len(exclusive_shards)} exclusive meta-test shards"
                ),
                depth=2,
            )
        exclusive_statuses: tuple[CompletedProcess[bytes], ...] = (
            self.execute_many(
                argument_sets=argument_sets[regular_count:],
                cwd=self._config.root,
                program=str(object=bundle) if bundle is not None else None,
                concurrency=1,
            )
            if exclusive_shards
            else ()
        )
        shard_statuses: tuple[CompletedProcess[bytes], ...] = (
            *regular_statuses,
            *exclusive_statuses,
        )
        self._update_test_cost_cache(timing_paths=timing_paths)
        self._publish_test_cost_cache()
        trace(
            step="test shards: all finished — exits "
            + ", ".join(
                str(object=result.returncode) for result in shard_statuses
            ),
            depth=2,
        )
        return self._record_test_output(
            results=shard_statuses,
            duration_seconds=monotonic() - started,
        )

    def _publish_test_cost_cache(self: Self) -> None:
        """Mirror the learned test-cost cache into the run artifacts.

        The artifact exposes the scheduling state used to balance the
        shards so reports can audit why each file landed where it did.
        """
        source: Path = self._test_cost_cache_path
        if not source.is_file():
            return
        self._layout.coverage_artifacts.mkdir(parents=True, exist_ok=True)
        _ = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.test_costs_name
        ).write_text(data=source.read_text(encoding="utf-8"), encoding="utf-8")

    def _load_test_cost_cache(self: Self) -> dict[str, float]:
        """Load genuine per-file pytest runtime measurements.

        Returns:
            Relative test file paths mapped to learned durations, or an
            empty mapping when no valid cache exists.

        """
        path: Path = self._test_cost_cache_path
        if not path.is_file():
            return {}
        try:
            raw: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (OSError, UnicodeError, ValueError):
            return {}
        target_version: int = 3
        if not isinstance(raw, dict) or raw.get("version") != target_version:
            return {}
        files_value: JsonValue | None = raw.get("files")
        if not isinstance(files_value, dict):
            return {}
        cache: dict[str, float] = {}
        key: str
        value: JsonValue
        for key, value in files_value.items():
            if isinstance(value, (int, float)) and (
                not isinstance(value, bool)
            ):
                cache[key] = max(1e-06, float(value))
        return cache

    def _update_test_cost_cache(
        self: Self,
        *,
        timing_paths: tuple[Path, ...],
    ) -> None:
        """Merge direct pytest per-file timing telemetry into the cache.

        Args:
            timing_paths: Per-shard telemetry JSON files.

        """
        previous: dict[str, float] = self._load_test_cost_cache()
        observed: dict[str, float] = {}
        timing_path: Path
        py_version: int = 3
        for timing_path in timing_paths:
            try:
                raw: JsonValue = cast(
                    typ="JsonValue",
                    val=loads(s=timing_path.read_text(encoding="utf-8")),
                )
            except (OSError, UnicodeError, ValueError):
                continue
            if not isinstance(raw, dict) or raw.get("version") != py_version:
                continue
            files_value: JsonValue | None = raw.get("files")
            if not isinstance(files_value, dict):
                continue
            relative: str
            value: JsonValue
            for relative, value in files_value.items():
                if isinstance(value, (int, float)) and (
                    not isinstance(value, bool)
                ):
                    observed[relative] = observed.get(relative, 0.0) + max(
                        1e-06,
                        float(value),
                    )
        if not observed:
            trace(step="test shards: no direct timing samples", depth=3)
            return
        learned: dict[str, float] = dict(previous)
        duration: float
        for relative, duration in observed.items():
            old: float | None = previous.get(relative)
            learned[relative] = (
                duration if old is None else old * 0.25 + duration * 0.75
            )
        cache_path: Path = self._test_cost_cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            data=dumps(
                obj={"version": 3, "files": learned},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        for timing_path in timing_paths:
            timing_path.unlink(missing_ok=True)
        trace(
            step=(
                f"test shards: {len(observed)} direct timing "
                f"samples, {len(learned)} persistent cached files"
            ),
            depth=3,
        )

    def _collect_pytest_nodes(
        self: Self,
        *,
        tests: tuple[Path, ...],
    ) -> tuple[str, ...]:
        """Collect exact pytest node IDs for test-level sharding.

        Args:
            tests: Discovered test files.

        Returns:
            Deterministic collected node IDs.

        Raises:
            CoverageRunError: When pytest collection fails or yields no nodes.

        """
        relative_tests: tuple[str, ...] = tuple(
            self._relative_string(path=test) for test in tests
        )
        groups: dict[str, list[str]] = {}
        relative: str
        for relative in relative_tests:
            group: str = self._node_isolation_group(relative=relative)
            groups.setdefault(group, []).append(relative)
        trace(
            step=(
                f"test shards: collect pytest node IDs in "
                f"{len(groups)} isolated import groups"
            ),
            depth=2,
        )
        bundle: Path | None = (
            resolve_exactus_tool_bundle(root=self._config.root)
            if find_spec(name="pytest") is None
            else None
        )
        results: tuple[CompletedProcess[bytes], ...] = self.execute_many(
            argument_sets=tuple(
                (
                    *(() if bundle is not None else ("-m",)),
                    "pytest",
                    "--collect-only",
                    "-q",
                    *members,
                    *self._config.pytest_args,
                )
                for members in groups.values()
            ),
            cwd=self._config.root,
            program=str(object=bundle) if bundle is not None else None,
            concurrency=self._config.jobs,
            progress=("pytest collect", (0.1, 0.2)),
        )
        prefixes: tuple[str, ...] = tuple(
            f"{relative}::" for relative in relative_tests
        )
        collected: list[str] = []
        group_name: str
        result: CompletedProcess[bytes]
        for group_name, result in zip(groups, results, strict=True):
            output: str = self._decode_process_output(result=result)
            if result.returncode != 0:
                detail: str = output.strip()
                msg: str = (
                    f"pytest node collection failed for {group_name}: {detail}"
                )
                raise CoverageRunError(msg)
            collected.extend(
                line.strip()
                for line in output.splitlines()
                if line.strip().startswith(prefixes)
            )
        nodes: tuple[str, ...] = tuple(dict.fromkeys(collected))
        if not nodes:
            msg = "pytest node collection completed without any test node IDs"
            raise CoverageRunError(msg)
        trace(step=f"test shards: collected {len(nodes)} node IDs", depth=2)
        return nodes

    def _isolated_node_shards(
        self: Self,
        *,
        tests: tuple[Path, ...],
        nodes: tuple[str, ...],
    ) -> tuple[tuple[str, ...], ...]:
        """Build node shards without mixing independent package projects.

        Keeping standalone package projects in separate pytest processes
        prevents identical top-level import names from contaminating one
        another. Host tests still split across all configured workers.

        Args:
            tests: Discovered test files.
            nodes: Collected pytest node IDs.

        Returns:
            Directory-isolated node shards.

        """
        grouped: dict[str, list[str]] = {}
        node: str
        for node in nodes:
            relative: str = node.split(sep="::", maxsplit=1)[0]
            group: str = self._node_isolation_group(relative=relative)
            grouped.setdefault(group, []).append(node)
        shards: list[tuple[str, ...]] = []
        group_name: str
        members: list[str]
        for group_name, members in grouped.items():
            if group_name != "shared":
                shards.append(tuple(members))
                continue
            shards.extend(
                self._balanced_test_shards(tests=tests, items=tuple(members)),
            )
        trace(
            step=(
                f"test shards: {len(shards)} directory-isolated "
                f"node shards across {len(grouped)} import groups"
            ),
            depth=2,
        )
        return tuple(shards)

    def _balanced_test_shards(
        self: Self,
        *,
        tests: tuple[Path, ...],
        items: tuple[str, ...] | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        """Partition tests using real timings with static cold-start fallback.

        Args:
            tests: Discovered test files.
            items: Explicit file paths or pytest node IDs to distribute.

        Returns:
            One learned-cost-balanced shard per configured worker.

        """
        selected: tuple[str, ...] = items or tuple(
            self._relative_string(path=test) for test in tests
        )
        shard_count: int = max(1, min(self._config.jobs, len(selected)))
        mutable_shards: list[list[str]] = [[] for _ in range(shard_count)]
        shard_weights: list[int] = [0 for _ in range(shard_count)]
        learned: dict[str, float] = self._load_test_cost_cache()
        static_costs: dict[str, int] = {
            self._relative_string(path=test): self._test_cost(test=test)
            for test in tests
        }
        ratios: list[float] = [
            learned[path] / max(1, static)
            for path, static in static_costs.items()
            if path in learned
        ]
        ratios.sort()
        seconds_per_static: float = (
            ratios[len(ratios) // 2] if ratios else 0.001
        )
        node_counts: Counter[str] = Counter(
            item.split(sep="::", maxsplit=1)[0] for item in selected
        )

        def estimated_milliseconds(item: str) -> int:
            """Return one item's learned or static scheduling weight.

            Args:
                item: Test node identifier.

            Returns:
                Estimated runtime in milliseconds.

            """
            relative: str = item.split(sep="::", maxsplit=1)[0]
            learned_seconds: float | None = learned.get(relative)
            if learned_seconds is not None:
                return max(
                    1,
                    int(learned_seconds / node_counts[relative] * 1000.0),
                )
            static_seconds: float = (
                static_costs.get(relative, 1)
                * seconds_per_static
                / node_counts[relative]
            )
            return max(1, int(static_seconds * 1000.0))

        weighted_tests: list[tuple[int, str]] = sorted(
            ((estimated_milliseconds(item=item), item) for item in selected),
            key=lambda item: (-item[0], item[1]),
        )
        weight: int
        item: str
        for weight, item in weighted_tests:
            index: int = min(
                range(shard_count),
                key=lambda candidate: (shard_weights[candidate], candidate),
            )
            mutable_shards[index].append(item)
            shard_weights[index] += weight
        trace(
            step=(
                f"test shards: {len(learned)} genuine cached "
                f"timings; estimated milliseconds "
            )
            + ", ".join(str(object=weight) for weight in shard_weights),
            depth=3,
        )
        return tuple(tuple(shard) for shard in mutable_shards)

    def _report(self: Self, *arguments: str, config_path: Path) -> int:
        """Generate one coverage report.

        Args:
            *arguments: Additional report command arguments.
            config_path: Config path.

        Returns:
            The resulting value.

        """
        bundle: Path | None = (
            resolve_exactus_tool_bundle(root=self._config.root)
            if find_spec(name="coverage") is None
            else None
        )
        process: CompletedProcess[bytes] = self.execute(
            arguments=(
                *(() if bundle is not None else ("-m",)),
                "coverage",
                *arguments,
                f"--rcfile={config_path}",
            ),
            cwd=self._config.root,
            program=str(object=bundle) if bundle is not None else None,
        )
        trace(
            step=f"coverage {' '.join(arguments)} — exit {process.returncode}",
            depth=2,
        )
        return process.returncode

    def _exactus_markdown(
        self: Self,
        *,
        coverage: Mapping[str, JsonValue],
        graph: Mapping[str, JsonValue],
        javascript: Mapping[str, JsonValue] | None = None,
    ) -> str:
        """Render normalized Markdown from coverage machine reports.

        Args:
            coverage: Coverage.
            graph: Graph.
            javascript: Javascript.

        Returns:
            The resulting value.

        """
        totals: JsonValue = coverage.get("totals")
        total: dict[str, JsonValue] = (
            totals if isinstance(totals, dict) else {}
        )
        files: JsonValue = coverage.get("files")
        file_map: dict[str, JsonValue] = (
            files if isinstance(files, dict) else {}
        )
        targets: JsonValue = graph.get("targets")
        ignored: JsonValue = graph.get("ignored_non_local_imports")
        unreached: JsonValue = graph.get("unreached_sources")
        percent: JsonValue = total.get(
            "percent_covered_display",
            total.get("percent_covered", "n/a"),
        )
        measured: JsonValue = total.get("percent_covered")
        target_count: int = len(targets) if isinstance(targets, list) else 0
        ignored_count: int = len(ignored) if isinstance(ignored, list) else 0
        unreached_count: int = (
            len(unreached) if isinstance(unreached, list) else 0
        )
        minimum: float | None = self._config.fail_under
        per_file: float | None = self._config.per_file_minimum
        shortfalls: list[tuple[str, float, int]] = self._file_shortfalls(
            coverage_report=dict(coverage),
        )
        passed: bool = (
            not shortfalls
            and (not self._js_gate_failed(javascript=javascript))
            and (
                minimum is None
                or (
                    isinstance(measured, int | float)
                    and float(measured) >= minimum
                )
            )
        )
        lines: list[str] = [
            "# Combined Coverage Exactus",
            "",
            "## Summary",
            "",
            f"- Status: **{('PASS' if passed else 'FAIL')}**",
            (
                f"- Coverage gate: "
                f"**{(minimum if minimum is not None else 'disabled')}**"
            ),
            (
                f"- Per-file gate: "
                f"**{per_file if per_file is not None else 'disabled'}** "
                f"({len(shortfalls)} file(s) below)"
            ),
            f"- Coverage: **{percent}%**",
            f"- Statements: **{total.get('num_statements', 'n/a')}**",
            f"- Missing lines: **{total.get('missing_lines', 'n/a')}**",
            f"- Covered lines: **{total.get('covered_lines', 'n/a')}**",
            f"- Reachable local targets: **{target_count}**",
            f"- Ignored non-local imports: **{ignored_count}**",
            f"- Unreached source files: **{unreached_count}**",
        ]
        if javascript is not None:
            lines.extend(self._js_summary_lines(javascript=javascript))
        if shortfalls:
            lines += [
                "",
                "## Files below the per-file gate",
                "",
                "| File | Coverage | Missing |",
                "| --- | ---: | ---: |",
                *(
                    f"| `{path}` | {value:.1f}% | {missing} |"
                    for path, value, missing in shortfalls
                ),
            ]
        lines += [
            "",
            "## File coverage",
            "",
            "| File | Statements | Missing | Coverage |",
            "| --- | ---: | ---: | ---: |",
        ]
        name: str
        raw: JsonValue
        for name, raw in sorted(file_map.items()):
            entry: dict[str, JsonValue] = raw if isinstance(raw, dict) else {}
            summary: JsonValue = entry.get("summary")
            values: dict[str, JsonValue] = (
                summary if isinstance(summary, dict) else {}
            )
            cell_percent: JsonValue = values.get(
                "percent_covered_display",
                values.get("percent_covered", "n/a"),
            )
            lines.append(
                "".join(
                    (
                        f"| `{name}` | ",
                        f"{values.get('num_statements', 'n/a')} | ",
                        f"{values.get('missing_lines', 'n/a')} | ",
                        f"{cell_percent}% |",
                    ),
                ),
            )
        lines.extend(["", "## Import graph", ""])
        if isinstance(targets, list):
            target_lines: list[str] = list(map(self._bullet, targets))
            lines.extend(
                ["### Reachable local targets", "", *target_lines, ""],
            )
        if isinstance(unreached, list) and unreached:
            lines.extend(
                [
                    "### Unreached source files",
                    "",
                    (
                        "These files were not reached during measurement and "
                        "are excluded from the percentages above."
                    ),
                    "",
                    *map(self._bullet, unreached),
                    "",
                ],
            )
        if isinstance(ignored, list):
            ignored_lines: list[str] = list(map(self._bullet, ignored))
            lines.extend(
                ["### Ignored non-local imports", "", *ignored_lines, ""],
            )
        if javascript is not None:
            lines.extend(self._js_section_lines(javascript=javascript))
        return "\n".join(lines).rstrip() + "\n"

    def _write_exactus_bundle(
        self: Self,
        *,
        javascript: Mapping[str, JsonValue] | None = None,
        execution: TestExecution | None = None,
        groups: Sequence[Mapping[str, JsonValue]] = (),
    ) -> None:
        """Write the coverage report and the unified root report.

        Args:
            javascript: Javascript.
            execution: Pytest execution, when available for the root gate.
            groups: Per-group test rows linking to ``TESTS/<group>``.

        """
        coverage_path: Path = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.raw_report_name
        )
        graph_path: Path = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.import_graph_name
        )
        bundle_started: float = monotonic()
        coverage: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=coverage_path.read_text(encoding="utf-8")),
        )
        graph_full: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=graph_path.read_text(encoding="utf-8")),
        )
        graph: dict[str, JsonValue] = {
            key: value for key, value in graph_full.items() if key != "tests"
        }
        coverage_javascript: dict[str, JsonValue] | None = (
            {
                key: value
                for key, value in javascript.items()
                if key
                not in {
                    "detail",
                    "failed_tests",
                    "failures",
                    "status",
                    "tests",
                }
            }
            if javascript is not None
            else None
        )
        coverage_files: JsonValue = coverage.get("files", {})
        if isinstance(coverage_files, dict):
            file_path: str
            file_entry: JsonValue
            for file_path, file_entry in coverage_files.items():
                if not isinstance(file_entry, dict):
                    continue
                missing: JsonValue = file_entry.get("missing_lines", [])
                numbers: list[int] = (
                    [value for value in missing if isinstance(value, int)]
                    if isinstance(missing, list)
                    else []
                )
                snippets: dict[str, JsonValue] = self._file_snippets(
                    relative=file_path,
                    missing=numbers,
                )
                if snippets:
                    file_entry["snippets"] = snippets
        trace(
            step=(
                f"report bundle: snippets prepared in "
                f"{monotonic() - bundle_started:.3f}s"
            ),
            depth=3,
        )
        markdown_started: float = monotonic()
        markdown: str = self._exactus_markdown(
            coverage=coverage,
            graph=graph,
            javascript=coverage_javascript,
        )
        trace(
            step=(
                f"report bundle: markdown prepared in "
                f"{monotonic() - markdown_started:.3f}s"
            ),
            depth=3,
        )
        data: Mapping[str, JsonValue] = cast(
            typ="Mapping[str, JsonValue]",
            val={
                "root": str(object=self._config.root),
                "coverage": coverage,
                "import_graph": graph,
                "javascript": coverage_javascript,
                "gates": {
                    "fail_under": self._config.fail_under,
                    "per_file_minimum": self._config.per_file_minimum,
                    "files_below": [
                        path
                        for path, _, _ in self._file_shortfalls(
                            coverage_report=coverage,
                        )
                    ],
                },
            },
        )
        directory: Path = self._layout.coverage_report
        _ = consume(
            value=ReportBundle.write(
                paths=ReportPaths(
                    markdown=directory / "result.md",
                    json=directory / "result.json",
                    web=directory / "result_web",
                ),
                analyzer="coverage",
                title="Combined Coverage Exactus",
                markdown=markdown,
                data=data,
            ),
        )
        trace(
            step=(
                f"report bundle: generic bundle written "
                f"at {monotonic() - bundle_started:.3f}s"
            ),
            depth=3,
        )
        self.report_inputs = ReportInputs(
            root=self._config.root,
            context=self._config.context_lines,
            coverage=coverage,
            graph=graph_full,
            javascript=javascript,
            execution=self._execution_manifest(execution=execution)
            if execution is not None
            else None,
            groups=tuple(groups),
            gates=CoverageGates(
                fail_under=self._config.fail_under,
                per_file_minimum=self._config.per_file_minimum,
            ),
            excluded_dirs=tuple(sorted(self._config.excluded_dirs)),
            includes=self._config.test_includes,
            excludes=self._config.test_excludes,
        )
        self.report_legacy = dict(data)
        CoverageTestsReport.write(
            inputs=self.report_inputs,
            output=self._layout.root,
            legacy=self.report_legacy,
        )
        trace(
            step=(
                f"report bundle: coverage report written "
                f"at {monotonic() - bundle_started:.3f}s"
            ),
            depth=3,
        )

    def _skip_details(
        self: Self,
        *,
        execution: TestExecution,
    ) -> tuple[list[JsonValue], list[str]]:
        """Build informational skip details for the nested test reports.

        Args:
            execution: Execution.

        Returns:
            The resulting value.

        """
        manifest: dict[str, JsonValue] = self._execution_manifest(
            execution=execution,
        )
        inputs: ReportInputs = ReportInputs(
            root=self._config.root,
            context=self._config.context_lines,
            coverage={},
            graph={},
            javascript=None,
            execution={"skipped_tests": manifest["skipped_tests"]},
            groups=(),
            gates=CoverageGates(fail_under=None, per_file_minimum=None),
        )
        findings: list[JsonValue] = [
            finding_excerpt(
                finding=cast(typ="JsonValue", val=item),
                root=inputs.root,
                context=inputs.context,
            )
            for item in CoverageTestsReport.test_findings(inputs=inputs)
        ]
        lines: list[str] = []
        if findings:
            lines.extend(("## Skipped tests", ""))
        for raw in findings:
            item: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=raw,
            )
            lines.extend(
                (
                    f"### `{item['test']}`",
                    "",
                    "**Outcome:** SKIPPED · **Severity:** info",
                    f"**Location:** `{item['path']}:{item['line']}`",
                    "",
                    str(object=item["message"]),
                    "",
                    (
                        f"Log: [Test "
                        f"output]({item['log']}) (shard {item['shard']})"
                    ),
                    "",
                ),
            )
            excerpt: JsonValue = item.get("excerpt")
            if isinstance(excerpt, dict):
                rows: list[dict[str, JsonValue]] = cast(
                    typ="list[dict[str, JsonValue]]",
                    val=excerpt["lines"],
                )
                lines.append("~~~python")
                lines.extend(
                    f"{row['n']}{'>' if row['target'] else ' '}| {row['text']}"
                    for row in rows
                )
                lines.extend(("~~~", ""))
        return (findings, lines)

    def _write_tests_summary(
        self: Self,
        *,
        output: Path,
        groups: dict[str, list[str]],
        executed: dict[str, list[tuple[str, str]]],
        execution: TestExecution,
    ) -> None:
        """Write the combined tests report: what ran, what failed, and why.

        Args:
            output: Output.
            groups: Groups.
            executed: Executed.
            execution: Execution.

        """
        outcomes: Counter[str] = Counter(
            (outcome for pairs in executed.values() for _, outcome in pairs),
        )
        manifest: dict[str, JsonValue] = self._execution_manifest(
            execution=execution,
        )
        skipped_findings, skipped_lines = self._skip_details(
            execution=execution,
        )
        failed: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=manifest["failed_tests"],
        )
        total: int = sum(outcomes.values())
        status: str = "PASS" if execution.status == 0 else "FAIL"
        group_rows: list[dict[str, JsonValue]] = [
            self._group_summary(name=name, files=files, executed=executed)
            for name, files in sorted(groups.items())
        ]
        lines: list[str] = [
            "# Combined Tests Report",
            "",
            f"- Status: **{status}**",
            f"- Tests run: **{total}** — "
            + ", ".join(
                (
                    f"{count} {name.lower()}"
                    for name, count in sorted(outcomes.items())
                ),
            ),
            f"- Test files: **{sum(len(v) for v in groups.values())}**",
            f"- Groups: **{len(groups)}**",
            f"- Shards: **{len(execution.shards)}**",
        ]
        collected: int = sum(
            shard.collected or 0 for shard in execution.shards
        )
        if collected > total:
            lines.append(
                f"- Collected but not reported: "
                f"**{collected - total}** (deselected, or pytest "
                f"printed no per-test outcome)",
            )
        lines.append("")
        if failed:
            lines.extend(
                (
                    "## Failed tests and why",
                    "",
                    "| Test | Kind | Reason | Log |",
                ),
            )
            lines.append("| --- | --- | --- | --- |")
            for item in failed:
                entry: Mapping[str, JsonValue] = cast(
                    typ="Mapping[str, JsonValue]",
                    val=item,
                )
                reason: str = str(object=entry.get("detail", "")).strip()
                first: str = (reason.splitlines() or [""])[0]
                lines.append(
                    f"| `{entry.get('test')}` | {entry.get('kind')} | "
                    f"{first.replace('|', chr(92) + '|')[:200]} | "
                    f"`{entry.get('log')}` |",
                )
            lines.append("")
        lines.extend(skipped_lines)
        lines.extend(
            (
                "## Results by group",
                "",
                "| Group | Files | Tests | Passed | Failed | Skipped |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ),
        )
        lines.extend(
            f"| `{row['group']}` | {row['files']} | {row['tests']} | "
            f"{row['passed']} | {row['failed']} | {row['skipped']} |"
            for row in group_rows
        )
        lines.extend(
            ("", "## Shards", "", "| Shard | Exit | Collected | Run | Log |"),
        )
        lines.append("| --- | ---: | ---: | ---: | --- |")
        lines.extend(
            f"| {shard.index} | {shard.returncode} | "
            f"{shard.collected if shard.collected is not None else 'n/a'} | "
            f"{len(shard.tests)} | `{shard.log}` |"
            for shard in execution.shards
        )
        warnings: Counter[str] = Counter(
            f"{warning.category}: {warning.message}"
            for shard in execution.shards
            for warning in shard.warnings
        )
        if warnings:
            lines.extend(("", "## Warnings", "", "| Warning | Count |"))
            lines.append("| --- | ---: |")
            lines.extend(
                (
                    f"| {text.replace('|', chr(92) + '|')[:200]} | {count} |"
                    for text, count in warnings.most_common()
                ),
            )
        _ = ReportBundle.write(
            paths=ReportPaths(
                markdown=output / "result.md",
                json=output / "result.json",
                web=output / "result_web",
            ),
            analyzer="tests",
            title="Combined Tests Report",
            markdown="\n".join(lines),
            data=cast(
                typ="dict[str, JsonValue]",
                val={
                    "status": status,
                    "passed": execution.status == 0,
                    "summary": {
                        "total": total,
                        "outcomes": dict(outcomes),
                        "files": sum(len(v) for v in groups.values()),
                        "shards": len(execution.shards),
                    },
                    "groups": group_rows,
                    "failed_tests": failed,
                    "skipped_tests": manifest["skipped_tests"],
                    "findings": skipped_findings,
                    "warnings": manifest["warnings"],
                    "shards": manifest["shards"],
                },
            ),
        )

    def _write_shared_test_reports(
        self: Self,
        *,
        tests: tuple[Path, ...],
        execution: TestExecution,
    ) -> tuple[Mapping[str, JsonValue], ...]:
        """Write the ``TESTS`` reports from the coverage pytest execution.

        Args:
            tests: Tests.
            execution: Execution.

        Returns:
            The resulting value.

        """
        tests_root: Path = self._layout.tests_report
        relative_tests: tuple[str, ...] = tuple(
            test.relative_to(self._config.root).as_posix() for test in tests
        )
        executed: dict[str, list[tuple[str, str]]] = {}
        shard: ShardOutcome
        entry: ExecutedTest
        for shard in execution.shards:
            for entry in shard.tests:
                node_file, _, node_test = entry.test.partition("::")
                executed.setdefault(node_file, []).append(
                    (node_test, entry.outcome),
                )
        groups: dict[str, list[str]] = {}
        test: str
        for test in relative_tests:
            groups.setdefault(self._test_group_name(test=test), []).append(
                test,
            )
        rmtree(path=tests_root, ignore_errors=True)
        self._write_tests_summary(
            output=tests_root,
            groups=groups,
            executed=executed,
            execution=execution,
        )
        name: str
        members: list[str]
        for name, members in sorted(groups.items()):
            selected: tuple[str, ...] = tuple(members)
            group_execution: TestExecution = self._group_execution(
                selected=selected,
                execution=execution,
            )
            skipped_findings, skipped_lines = self._skip_details(
                execution=group_execution,
            )
            status: str = "PASS" if group_execution.status == 0 else "FAIL"
            run_total: int = sum(
                len(executed.get(test, ())) for test in selected
            )
            output: Path = tests_root / name
            payload: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val={
                    "status": status,
                    "passed": group_execution.status == 0,
                    "shared_execution": "COVERAGE",
                    "shared_execution_status": execution.status,
                    "test_files": list(selected),
                    "tests_run": run_total,
                    "tests": {
                        test: [
                            {"name": test_name, "outcome": outcome}
                            for test_name, outcome in executed.get(test, [])
                        ]
                        for test in selected
                    },
                    "test_execution": self._execution_manifest(
                        execution=group_execution,
                    ),
                    "findings": skipped_findings,
                },
            )
            lines: list[str] = [
                f"# {name} Test Analyzer",
                "",
                f"- Status: **{status}**",
                "- Execution: shared with COVERAGE (no duplicate pytest run)",
                f"- Matching test files: **{len(selected)}**",
                f"- Tests run: **{run_total}**",
                "",
                "## Test files",
                "",
            ]
            for test in selected:
                entries: list[tuple[str, str]] = executed.get(test, [])
                lines.append(
                    f"### `{test}` — {len(entries)} "
                    f"test{('' if len(entries) == 1 else 's')}",
                )
                lines.append("")
                if entries:
                    lines.extend(("| Test | Outcome |", "| --- | --- |"))
                    test_name: str
                    outcome: str
                    for test_name, outcome in entries:
                        lines.append(
                            f"| `{test_name.replace('|', chr(92) + '|')}` "
                            f"| {outcome} |",
                        )
                else:
                    lines.append("No executed tests recorded.")
                lines.append("")
            lines.extend(skipped_lines)
            _ = ReportBundle.write(
                paths=ReportPaths(
                    markdown=output / "result.md",
                    json=output / "result.json",
                    web=output / "result_web",
                ),
                analyzer=f"tests-{name.lower()}",
                title=f"{name} Test Analyzer",
                markdown="\n".join(lines),
                data=payload,
            )
        return tuple(
            (
                {
                    **self._group_summary(
                        name=name,
                        files=members,
                        executed=executed,
                    ),
                    "report": f"TESTS/{name}",
                }
                for name, members in sorted(groups.items())
            ),
        )

    def _purge_data_files(self: Self) -> None:
        """Remove the scratch tree and stray coverage data files."""
        rmtree(path=self._work_dir, ignore_errors=True)
        stale: tuple[Path, ...] = tuple(
            self._config.output.glob(pattern=".coverage*"),
        )
        data_path: Path
        for data_path in stale:
            data_path.unlink(missing_ok=True)
        trace(
            step=f"purge: scratch tree, {len(stale)} stray data files",
            depth=3,
        )

    def _start_javascript_lane(
        self: Self,
        *,
        js_results: list[JsCoverageResult | None],
        js_errors: list[Exception],
    ) -> Thread | None:
        """Launch the independent JavaScript coverage lane in background.

        Args:
            js_results: One-element sink receiving the lane result.
            js_errors: Sink receiving any lane exception.

        Returns:
            The started thread, or ``None`` when the lane is disabled.

        """

        def run_javascript_lane() -> None:
            """Run the independent JavaScript coverage lane."""
            try:
                js_results.append(self._run_js_coverage())
            except (
                OSError,
                RuntimeError,
                SubprocessError,
                ValueError,
                TypeError,
                KeyError,
            ) as error:
                js_errors.append(error)

        if not self._config.measure_js:
            return None
        trace(step="stage: javascript lane — background start", depth=1)
        thread: Thread = Thread(
            target=run_javascript_lane,
            name="coverage-tests-javascript",
            daemon=False,
        )
        thread.start()
        return thread

    def _coverage_report(
        self: Self,
        *,
        config_path: Path,
    ) -> dict[str, JsonValue]:
        """Generate the combined JSON coverage report and load it.

        Args:
            config_path: Combined coverage configuration path.

        Returns:
            Parsed JSON coverage report payload.

        Raises:
            CoverageRunError: Raised when report generation fails.

        """
        trace(step="stage: coverage report", depth=1)
        emit_progress(
            state="RUNNING",
            completed=4,
            total=5,
            step="coverage report",
        )
        report_statuses: tuple[int, ...] = (
            self._report(
                "json",
                "-o",
                str(
                    object=self._layout.coverage_artifacts
                    / CoverageCoreDefaults.raw_report_name,
                ),
                config_path=config_path,
            ),
        )
        failed_report: int = 0
        status: int
        for status in report_statuses:
            if status != 0:
                failed_report = status
                break
        if failed_report:
            trace(
                step=f"coverage report: failed — exit {failed_report}",
                depth=2,
            )
            msg: str = (
                f"Coverage report generation failed with "
                f"exit code {failed_report}."
            )
            raise CoverageRunError(msg)
        return cast(
            typ="dict[str, JsonValue]",
            val=loads(
                s=(
                    self._layout.coverage_artifacts
                    / CoverageCoreDefaults.raw_report_name
                ).read_text(encoding="utf-8"),
            ),
        )

    def _write_completion(
        self: Self,
        *,
        tests: tuple[Path, ...],
        execution: TestExecution,
        js_result: JsCoverageResult | None,
        js_status: int,
        final_status: int,
    ) -> None:
        """Write the completion manifest summarizing the run.

        Args:
            tests: Discovered test files.
            execution: Test execution summary.
            js_result: JavaScript coverage result, when measured.
            js_status: JavaScript lane exit status.
            final_status: Combined final exit status.

        """
        coverage_path: Path = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.raw_report_name
        )
        _ = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.completion_name
        ).write_text(
            data=dumps(
                obj={
                    "completed": execution.status <= 1,
                    "returncode": 0
                    if execution.status <= 1
                    else execution.status,
                    "final_status": final_status,
                    "test_files_discovered": len(tests),
                    "tests_collected": None
                    if all(
                        shard.collected is None for shard in execution.shards
                    )
                    else sum(
                        shard.collected or 0 for shard in execution.shards
                    ),
                    "tests_executed": sum(
                        len(shard.tests) for shard in execution.shards
                    ),
                    "js_tests_discovered": len(js_result.tests)
                    if js_result is not None
                    else 0,
                    "js_returncode": js_status,
                    "pytest_jobs": self._config.jobs,
                    "pytest_shard_by": self._config.shard_by,
                    "pytest_shards": len(execution.shards),
                    "test_execution": self._execution_manifest(
                        execution=execution,
                    ),
                    "coverage_file": CoverageCoreDefaults.raw_report_name,
                    "coverage_sha256": sha256(
                        data=coverage_path.read_bytes(),
                    ).hexdigest(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _classify_and_rebuild(
        self: Self,
        *,
        index: LocalModuleIndex,
        graph: ImportGraph,
    ) -> tuple[MeaningfulResult, Path, tuple[Path, ...], tuple[Path, ...]]:
        """Classify unreached sources and rebuild the coverage config.

        Args:
            index: Local module index.
            graph: Import graph.

        Returns:
            The Meaningful result, combined coverage config path,
            omitted sources, and unreached sources.

        Raises:
            CoverageRunError: Raised when the operation cannot be completed.

        """
        unreached: tuple[Path, ...] = self._omitted_paths(
            index=index,
            graph=graph,
        )
        trace(step="stage: meaningful classification", depth=1)
        meaningful: MeaningfulResult = analyze_unreached(
            root=self._config.root,
            paths=unreached,
            config=self._config.meaningful,
        )
        write_artifact(
            path=self._layout.coverage_artifacts
            / CoverageCoreDefaults.meaningful_name,
            result=meaningful,
        )
        trace(
            step=(
                f"meaningful: "
                f"{len(meaningful.rows)} rows — "
                f"{len(meaningful.actionable)} actionable, "
                f"{len(meaningful.analysis_errors)} analysis errors"
            ),
            depth=2,
        )
        actionable: frozenset[str] = frozenset(meaningful.actionable)
        omitted: tuple[Path, ...] = (
            ()
            if self._config.include_unreached
            else tuple(
                path
                for path in unreached
                if self._config.meaningful.mode != "require"
                or self._relative_string(path=path) not in actionable
            )
        )
        if len(omitted) == len(self._all_source_files(index=index)):
            trace(
                step=(
                    "coverage tests: no local source reached by tests — "
                    "aborting"
                ),
                depth=1,
            )
            msg: str = (
                "Tests were found, but none of them imports or "
                "executes local project Python modules under the "
                "configured source roots."
            )
            raise CoverageRunError(msg)
        omitted = (*omitted, *index.excluded)
        trace(step=f"omitted: {len(omitted)} sources", depth=2)
        self._write_manifest(
            graph=graph,
            unreached=unreached,
            omitted=omitted,
            meaningful=meaningful,
        )
        config_path: Path = self._write_coverage_config(
            name=".coveragerc.combined",
            omitted=omitted,
        )
        return (meaningful, config_path, omitted, unreached)

    def _merge_javascript_meaningful(
        self: Self,
        *,
        current: MeaningfulResult,
        javascript: JsCoverageResult | None,
        index: LocalModuleIndex,
        graph: ImportGraph,
        omitted: tuple[Path, ...],
    ) -> tuple[MeaningfulResult, tuple[Path, ...]]:
        """Add unreached JavaScript sources to Meaningful classification.

        Args:
            current: Python classification produced before test reporting.
            javascript: Completed JavaScript coverage lane, when present.
            index: Local Python module index.
            graph: Python test import graph.
            omitted: Sources currently omitted from coverage.

        Returns:
            Combined classification and omitted sources, or ``current``
            and ``omitted`` unchanged when JavaScript is clean.

        """
        if javascript is None or not javascript.unreached:
            return (current, omitted)
        python_unreached: tuple[Path, ...] = self._omitted_paths(
            index=index,
            graph=graph,
        )
        javascript_unreached: tuple[Path, ...] = tuple(
            (self._config.root / relative).resolve()
            for relative in javascript.unreached
        )
        combined: MeaningfulResult = analyze_unreached(
            root=self._config.root,
            paths=(*python_unreached, *javascript_unreached),
            config=self._config.meaningful,
        )
        write_artifact(
            path=self._layout.coverage_artifacts
            / CoverageCoreDefaults.meaningful_name,
            result=combined,
        )
        actionable: frozenset[str] = frozenset(combined.actionable)
        omitted = (
            *(
                ()
                if self._config.include_unreached
                else tuple(
                    path
                    for path in python_unreached
                    if self._config.meaningful.mode != "require"
                    or self._relative_string(path=path) not in actionable
                )
            ),
            *index.excluded,
        )
        self._write_manifest(
            graph=graph,
            unreached=(*python_unreached, *javascript_unreached),
            omitted=omitted,
            meaningful=combined,
        )
        return (combined, omitted)

    def _excuse_shortfalls(
        self: Self,
        *,
        graph: ImportGraph,
        unreached: tuple[Path, ...],
        omitted: tuple[Path, ...],
        snapshot: CoverageSnapshot,
        meaningful: MeaningfulResult,
    ) -> tuple[CoverageSnapshot, MeaningfulResult]:
        """Excuse measured files below the per-file gate via Meaningful.

        Files below ``per_file_minimum`` are classified; those Meaningful
        rates below the minimum test level are excused — omitted from
        coverage entirely so they fail neither the per-file gate nor
        count against the total.

        Args:
            graph: Import graph.
            unreached: Sources no test reached.
            omitted: Sources currently omitted from coverage.
            snapshot: Measured coverage state before excusing.
            meaningful: Classification of unreached sources.

        Returns:
            Possibly regenerated coverage snapshot and Meaningful result.

        """
        minimum: float | None = self._config.per_file_minimum
        if self._config.meaningful.mode == "off" or minimum is None:
            return (snapshot, meaningful)
        coverage_report: dict[str, JsonValue] = snapshot.report
        js_result: JsCoverageResult | None = snapshot.js_result
        js_manifest: dict[str, JsonValue] | None = snapshot.js_manifest
        known: frozenset[Path] = frozenset(
            path.resolve() for path in unreached
        ) | frozenset(
            (self._config.root / relative).resolve()
            for relative in (() if js_result is None else js_result.unreached)
        )
        python_shortfalls: tuple[Path, ...] = tuple(
            (
                (self._config.root / relative).resolve()
                for relative, _percent, _missing in self._file_shortfalls(
                    coverage_report=coverage_report,
                )
                if (self._config.root / relative).resolve() not in known
            ),
        )
        js_shortfalls: tuple[Path, ...] = (
            ()
            if js_result is None
            else tuple(
                (
                    (self._config.root / name).resolve()
                    for name, coverage in js_result.files.items()
                    if self._js_percent(coverage=coverage) < minimum
                    and (self._config.root / name).resolve() not in known
                ),
            )
        )
        shortfalls: tuple[Path, ...] = (*python_shortfalls, *js_shortfalls)
        if not shortfalls:
            return (snapshot, meaningful)
        trace(step="stage: shortfall classification", depth=1)
        classified: MeaningfulResult = analyze_unreached(
            root=self._config.root,
            paths=shortfalls,
            config=self._config.meaningful,
            origin="shortfall",
        )
        excused: frozenset[Path] = frozenset(
            (self._config.root / name).resolve() for name in classified.excused
        )
        trace(
            step=(
                f"meaningful: "
                f"{len(shortfalls)} shortfalls — {len(excused)} excused"
            ),
            depth=2,
        )
        new_omitted: tuple[Path, ...] = omitted
        new_report: dict[str, JsonValue] = coverage_report
        python_excused: frozenset[Path] = excused & frozenset(
            python_shortfalls,
        )
        if python_excused:
            python_names: frozenset[str] = frozenset(
                self._relative_string(path=path) for path in python_excused
            )
            measured: JsonValue = coverage_report.get("files")
            remaining: frozenset[str] = (
                frozenset(measured) - python_names
                if isinstance(measured, dict)
                else frozenset()
            )
            new_omitted = (*omitted, *sorted(python_excused))
            if remaining:
                config_path: Path = self._write_coverage_config(
                    name=".coveragerc.combined",
                    omitted=new_omitted,
                )
                new_report = self._coverage_report(config_path=config_path)
            else:
                new_report = {
                    "files": {},
                    "totals": {
                        "covered_lines": 0,
                        "num_statements": 0,
                        "percent_covered": 100.0,
                        "percent_covered_display": "100",
                    },
                }
                _ = (
                    self._layout.coverage_artifacts
                    / CoverageCoreDefaults.raw_report_name
                ).write_text(
                    data=dumps(obj=new_report, indent=2) + "\n",
                    encoding="utf-8",
                )
        new_manifest: dict[str, JsonValue] | None = js_manifest
        if js_result is not None and js_manifest is not None:
            js_names: frozenset[str] = frozenset(
                self._relative_string(path=path)
                for path in js_shortfalls
                if path in excused
            )
            if js_names:
                filtered: JsCoverageResult = replace(
                    js_result,
                    files={
                        name: coverage
                        for name, coverage in js_result.files.items()
                        if name not in js_names
                    },
                )
                new_manifest = self._js_manifest(result=filtered)
        combined: MeaningfulResult = merge_results(
            first=meaningful,
            second=classified,
        )
        write_artifact(
            path=self._layout.coverage_artifacts
            / CoverageCoreDefaults.meaningful_name,
            result=combined,
        )
        js_unreached_paths: tuple[Path, ...] = (
            ()
            if js_result is None
            else tuple(
                (self._config.root / relative).resolve()
                for relative in js_result.unreached
            )
        )
        self._write_manifest(
            graph=graph,
            unreached=(*unreached, *js_unreached_paths),
            omitted=new_omitted,
            meaningful=combined,
            excused=tuple(sorted(excused)),
        )
        return (
            CoverageSnapshot(
                report=new_report,
                js_result=js_result,
                js_manifest=new_manifest,
            ),
            combined,
        )

    def _pass_without_tests(self: Self) -> int:
        """Record a vacuous pass when no ``test_*.py`` files exist.

        Returns:
            The resulting value.

        """
        trace(
            step="coverage tests: no test_*.py files — vacuous pass",
            depth=1,
        )
        self._layout.coverage_artifacts.mkdir(parents=True, exist_ok=True)
        meaningful: MeaningfulResult = analyze_unreached(
            root=self._config.root,
            paths=(),
            config=self._config.meaningful,
        )
        write_artifact(
            path=self._layout.coverage_artifacts
            / CoverageCoreDefaults.meaningful_name,
            result=meaningful,
        )
        emit_progress(
            state="RUNNING",
            completed=5,
            total=5,
            step="coverage report",
            detail="no test_*.py files discovered; vacuous pass",
        )
        coverage_path: Path = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.raw_report_name
        )
        vacuous: dict[str, JsonValue] = {
            "meta": {
                "empty": True,
                "note": (
                    "no test_*.py files discovered; coverage is "
                    "vacuously complete"
                ),
            },
            "files": {},
            "totals": {
                "covered_lines": 0,
                "num_statements": 0,
                "percent_covered": 100.0,
                "percent_covered_display": "100",
            },
        }
        _ = coverage_path.write_text(
            data=dumps(obj=vacuous, indent=2),
            encoding="utf-8",
        )
        js_result: JsCoverageResult | None = self._run_js_coverage()
        js_manifest: dict[str, JsonValue] | None = (
            self._js_manifest(result=js_result)
            if js_result is not None
            else None
        )
        js_status: int = js_result.status if js_result is not None else 0
        final_status: int = js_status or int(
            self._js_gate_failed(javascript=js_manifest),
        )
        _ = (
            self._layout.coverage_artifacts
            / CoverageCoreDefaults.completion_name
        ).write_text(
            data=dumps(
                obj={
                    "completed": final_status == 0,
                    "returncode": final_status,
                    "test_files_discovered": 0,
                    "js_tests_discovered": len(js_result.tests)
                    if js_result
                    else 0,
                    "js_returncode": js_status,
                    "pytest_jobs": self._config.jobs,
                    "pytest_shard_by": self._config.shard_by,
                    "pytest_shards": 0,
                    "test_execution": {
                        "status": 0,
                        "tests": [],
                        "shards": [],
                        "failed_tests": [],
                        "warnings": [],
                    },
                    "coverage_file": CoverageCoreDefaults.raw_report_name,
                    "coverage_sha256": sha256(
                        data=coverage_path.read_bytes(),
                    ).hexdigest(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        meaningful_config: MeaningfulConfig = self._config.meaningful
        self.report_inputs = ReportInputs(
            root=self._config.root,
            context=self._config.context_lines,
            coverage=vacuous,
            graph={
                "tests": [],
                "targets": [],
                "unreached_sources": [],
                "omitted_sources": [],
                "meaningful": {
                    "mode": meaningful_config.mode,
                    "minimum_level": meaningful_config.minimum_level.value,
                    "unclassified": meaningful_config.unclassified,
                    "artifact": "ARTIFACTS/COVERAGE/"
                    + CoverageCoreDefaults.meaningful_name,
                    "counts": meaningful.artifact.get("counts", {}),
                    "rows": [],
                    "failures": [],
                },
            },
            javascript=js_manifest,
            execution={
                "status": 0,
                "tests": [],
                "shards": [],
                "failed_tests": [],
                "warnings": [],
            },
            groups=(),
            gates=CoverageGates(
                fail_under=self._config.fail_under,
                per_file_minimum=self._config.per_file_minimum,
            ),
            excluded_dirs=tuple(sorted(self._config.excluded_dirs)),
            includes=self._config.test_includes,
            excludes=self._config.test_excludes,
        )
        self.report_legacy = {
            "root": str(object=self._config.root),
            "coverage": vacuous,
            "passed": final_status == 0,
            "javascript": js_manifest,
        }
        CoverageTestsReport.write(
            inputs=self.report_inputs,
            output=self._layout.root,
            legacy=self.report_legacy,
        )
        return final_status


class CommandLine:
    """Parse command-line arguments into a typed immutable configuration."""

    @classmethod
    def target_source_roots(
        cls: type[Self],
        *,
        requested: Path,
        root: Path,
    ) -> tuple[Path, ...]:
        """Choose the measured source roots for an exactus target.

        Args:
            requested: Requested.
            root: Root.

        Returns:
            The resulting value.

        """
        if requested.is_dir() and requested != root:
            return (requested.resolve(),)
        return cls.default_source_roots(root=root)

    @classmethod
    def parse(cls: type[Self]) -> CoverageConfig:
        """Parse CLI arguments.

        Returns:
            The resulting value.

        Raises:
            CoverageRunError: Raised when the operation cannot be completed.

        """
        parser: ArgumentParser = ArgumentParser(
            description=(
                "Recursively discover test_*.py files, statically "
                "resolve their complete local import graph, run "
                "all tests once, and generate combined coverage "
                "only for reachable project code."
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "root",
                nargs="?",
                type=Path,
                default=Path.cwd(),
                help=(
                    "Project root to scan recursively (default: current "
                    "directory)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "-o",
                "--output",
                type=Path,
                default=Path("coverage_report"),
                help="Report output directory (default: coverage_report).",
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--source-root",
                action="append",
                type=Path,
                default=[],
                metavar="PATH",
                help=(
                    "Local import root allowed in coverage; repeat as "
                    "needed. Defaults to ROOT/src when it exists, "
                    "otherwise ROOT."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--no-branch",
                action="store_true",
                help="Disable branch coverage.",
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--fail-under",
                type=float,
                default=_GroupFinalConstants.default_fail_under,
                metavar="PERCENT",
                help=(
                    "Fail when total coverage is below PERCENT after all "
                    "reports (default: %(default)s)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--exclude-dir",
                action="append",
                default=[],
                metavar="NAME",
                help=(
                    "Add a directory basename to recursive discovery "
                    "exclusions."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--no-js-coverage",
                action="store_true",
                help=(
                    "Skip running discovered `node:test` suites under "
                    "Node V8 coverage."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--jobs",
                "-j",
                type=int,
                default=None,
                metavar="N",
                help=(
                    "Split the discovered tests across N parallel pytest "
                    "processes (default: all CPU cores; use 1 to run "
                    "serially)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--shard-by",
                choices=("file", "node"),
                default="file",
                help=(
                    "Balance workers by test files or exact collected "
                    "pytest node IDs (default: %(default)s)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--context-lines",
                type=int,
                default=3,
                metavar="N",
                help=(
                    "Source lines embedded around each uncovered run in "
                    "the web report snippets (default: %(default)s)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "--per-file-minimum",
                type=float,
                default=80.0,
                metavar="PERCENT",
                help=(
                    "Fail when any single source file is below PERCENT "
                    "(default: %(default)s; 0 disables the gate)."
                ),
            ),
        )
        _ = consume(
            value=parser.add_argument(
                "pytest_args",
                nargs="*",
                help="Extra pytest arguments; place them after '--'.",
            ),
        )
        namespace: CliNamespace = parser.parse_args(namespace=CliNamespace())
        requested_root: Path = namespace.root.resolve()
        output: Path = (
            namespace.output
            if namespace.output.is_absolute()
            else requested_root / namespace.output
        ).resolve()
        root: Path = cls.project_root(root=requested_root)
        resolved_roots: list[Path] = list(
            map(partial(cls._resolve_root, root=root), namespace.source_root),
        )
        source_roots: tuple[Path, ...] = tuple(
            dict.fromkeys(resolved_roots),
        ) or cls.default_source_roots(root=root)
        invalid_paths: list[Path] = []
        path: Path
        for path in source_roots:
            if path.is_dir() and path.is_relative_to(root):
                continue
            invalid_paths.append(path)
        if invalid := tuple(invalid_paths):
            msg: str = (
                f"Every --source-root must be an existing "
                f"directory inside the project root: "
                f"{', '.join(map(str, invalid))}"
            )
            raise CoverageRunError(msg)
        return CoverageConfig(
            root=root,
            output=output,
            source_roots=source_roots,
            branch=not namespace.no_branch,
            fail_under=namespace.fail_under,
            excluded_dirs=frozenset(
                (
                    *CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
                    *namespace.exclude_dir,
                ),
            ),
            pytest_args=tuple(namespace.pytest_args),
            measure_js=not namespace.no_js_coverage,
            jobs=namespace.jobs or cpu_count() or 1,
            shard_by=namespace.shard_by,
            context_lines=max(0, namespace.context_lines),
            per_file_minimum=namespace.per_file_minimum,
        )

    @staticmethod
    def project_root(root: Path) -> Path:
        """Widen a subdirectory root to the enclosing project root.

        Args:
            root: Root.

        Returns:
            The resulting value.

        """
        candidate: Path
        for candidate in (root, *root.parents):
            if (candidate / "src").is_dir() and (
                any((candidate / name).is_dir() for name in ("tests", "test"))
                or any(candidate.glob(pattern="test_*.py"))
                or any((candidate / "src").rglob(pattern="test_*.py"))
            ):
                return candidate
            if any(
                (candidate / marker).exists()
                for marker in ("pyproject.toml", "package.json", ".git")
            ):
                break
        return root

    @staticmethod
    def default_source_roots(root: Path) -> tuple[Path, ...]:
        """Choose conventional local source roots.

        Args:
            root: Root.

        Returns:
            The resulting value.

        """
        conventional: list[Path] = []
        name: str
        for name in CoverageCoreTables.DEFAULT_SOURCE_DIR_NAMES:
            candidate: Path = root / name
            if candidate.is_dir():
                conventional.append(candidate.resolve())
        return tuple(conventional) or (root,)

    @staticmethod
    def _resolve_root(path: Path, *, root: Path) -> Path:
        """Resolve one source-root argument against the project root.

        Args:
            path: Path.
            root: Root.

        Returns:
            The resulting value.

        """
        return (path if path.is_absolute() else root / path).resolve()


def main() -> None:
    """Run the local-import combined coverage command-line application.

    Raises:
        SystemExit: Raised when the operation cannot be completed.

    """
    try:
        raise SystemExit(
            CombinedCoverageRunner(config=CommandLine.parse()).run(),
        )
    except CoverageRunError as error:
        error: CoverageRunError
        raise SystemExit(str(object=error)) from error


if __name__ == "__main__":
    main()
