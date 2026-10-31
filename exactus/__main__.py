#!/usr/bin/env python3
# Copyright (c) 2026
"""Run canonical exactus tools and staged pipelines through the Python API."""

from __future__ import annotations

from argparse import Action, ArgumentParser, Namespace
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from errno import ENOTEMPTY
from fnmatch import fnmatch
from hashlib import sha256
from importlib.resources import files as resource_files
from importlib.util import find_spec
from json import JSONDecodeError, dumps, loads
from os import _exit, chdir, environ, getpid, stat_result, walk
from os.path import relpath
from pathlib import Path
from re import Match, fullmatch
from shutil import get_terminal_size, rmtree, which
from signal import Signals, signal
from sqlite3 import DatabaseError
from subprocess import Popen
from sys import argv, prefix, stderr, stdout
from sys import path as sys_path
from threading import Event
from time import monotonic, sleep
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    NoReturn,
    Self,
    TextIO,
    cast,
    final,
)
from zipfile import is_zipfile

from psutil import Error, process_iter

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parent.parent))
from exactus.packages.argument_parser import (
    ExactusArgumentParser,
    normalized_option,
)
from exactus.packages.project_python import auto as _project_python_auto
from exactus.tools.common.cli import (
    ExactusCommonTables,
    activate_exactus_tool_bundle,
    is_reports_tree,
    match_path,
    resolve_exactus_tool_bundle,
)
from exactus.tools.common.collect_files import Constants as CollectFilesTables
from exactus.tools.common.collect_files import collect_report_files

if argv[1:2] != ["__complete"] and find_spec(name="jinja2") is None:
    _ = activate_exactus_tool_bundle(root=Path.cwd())
from exactus.bundle.freshness import warn_if_stale
from exactus.packages.completion.protocol import run_completion
from exactus.packages.completion.providers import default_providers
from exactus.packages.external.cli import run as run_external_command
from exactus.packages.model.registry_queries import live_processes_for_run
from exactus.packages.model.sqlite_model import external_cli_sql
from exactus.packages.package.install import run as run_install_command
from exactus.packages.pmanager import (
    Orchestrator,
    ProcessHandle,
    ProcessStatus,
)
from exactus.packages.pmanager.runtime import Client, Descriptor, Discovery
from exactus.tools.common.activity import (
    ActivityDocument,
    ActivityFile,
    ActivityLog,
    ActivityTables,
)
from exactus.tools.common.api import ExactusApi
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.catalog import PipelineSpec, ToolSpec
from exactus.tools.common.config import (
    ConfigError,
    ConfigFile,
    EffectiveRequest,
    argv_for,
    discovery_from_environment,
    effective,
    orchestrator_arguments,
    reports_anchor,
    reports_directory,
    stacked,
    tool_parser,
    validate,
)
from exactus.tools.common.conflict_copies import clear_conflict_copies
from exactus.tools.common.digest import (
    ToolDigest,
    digest_data,
    digest_report,
    render_failure,
)
from exactus.tools.common.models import (
    PipelineActivity,
    ToolActivity,
    ToolRequest,
    ToolRunResult,
    result_stats,
)
from exactus.tools.common.pipeline_supervisor import (
    Constants as PipelineRequestConstants,
)
from exactus.tools.common.pipeline_supervisor import (
    PipelineClaim,
    PipelineCoordinator,
    PipelineOwner,
    PipelineRequest,
)
from exactus.tools.common.process_control import (
    exit_if_replaced,
    new_run_id,
    pause_tree,
    process_exists,
    read_json,
    resume_tree,
    terminate_tree,
    write_json,
)
from exactus.tools.common.process_layer.access import (
    Constants as AccessConstants,
)
from exactus.tools.common.process_layer.access import (
    authkey,
    start_responder,
    stop_responder,
)
from exactus.tools.common.process_layer.process_control import (
    IdentityResponder,
    RunIdentity,
    discover,
    identify,
)
from exactus.tools.common.process_layer.process_termination import (
    ProcessTerminator,
    TerminationResult,
)
from exactus.tools.common.progress import RunDocument, utc_now
from exactus.tools.common.registry import RunBeat, RunClaim, RunRegistry
from exactus.tools.common.report_comparison import capture as capture_reports
from exactus.tools.common.report_comparison import (
    previous_duration as previous_report_duration,
)
from exactus.tools.common.sprint import sprint
from exactus.tools.common.stderr_capture import StderrMirror
from exactus.tools.common.terminal import ExactusTerminal, ResultRow
from exactus.tools.common.tool_worker import (
    build_spec,
    ensure_worker_path,
    external_descriptors,
    kill_context,
    live_status,
    pause_worker,
    reset_worker,
    result_from_status,
    resume_worker,
    tool_context,
    worker_arguments,
)
from exactus.tools.completion.defaults import (
    Constants as _GroupFinalConstants_2,
)
from exactus.tools.completion.defaults import check_catalog
from exactus.tools.completion.main import run as run_completion_command
from exactus.tools.completion.startup import ensure_completion
from exactus.tools.coverage_tests.arguments import (
    create_parser as coverage_tests_parser,
)
from exactus.tools.docs.arguments import create_parser as docs_parser
from exactus.tools.frontend.arguments import create_parser as frontend_parser
from exactus.tools.kwargs_typehints.arguments import (
    create_parser as kwargs_typehints_parser,
)
from exactus.tools.lints.arguments import create_parser as lints_parser
from exactus.tools.readme.arguments import create_parser as readme_parser
from exactus.tools.record.arguments import create_parser as record_parser
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.self_test.arguments import create_parser as self_test_parser
from exactus.tools.visual_cause.arguments import (
    create_parser as visual_cause_parser,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from types import FrameType

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.registry import RunRecord
_project_python_active: bool = _project_python_auto.Constants.activated


@dataclass(slots=True)
class _PipelineRun:
    """Mutable bookkeeping shared by one pipeline execution.

    Attributes:
        pipeline: Canonical pipeline identifier.
        run_id: Unique pipeline run identifier.
        started: Monotonic start timestamp.
        started_at: ISO-8601 wall-clock start timestamp.
        group_count: Total number of sequential wave groups.
        fractions: Per-tool completion fractions keyed by tool ID.
        fail_marks: Completion fraction each tool reached when it
            failed, keyed by tool ID.
        activities: Per-tool live activity records keyed by tool ID.
        order: Canonical tool ordering for reports.
        groups: Dependency group of each tool, one-based.
        external: Live member runs this pipeline does not own.
        adopted: External runs counted as the current wave's tools.
        paused: Suspended external run pids keyed by tool ID.
        report_stamps: ``(mtime_ns, size)`` of each healed report file.
        tool_started: Per-tool monotonic start timestamps.
        log: Recent pipeline events published in ``@activity.json``.
        orchestrator: Detached-worker orchestrator for this pipeline.
        context: Unique pmanager context for this pipeline.
        handles: Pipeline-owned live worker handles keyed by tool ID.
        pending: Tools waiting for their dependencies to settle.
        tools: Participating tool specifications keyed by identifier.
        coordinator: Transactional owner and observer state store.
        generation: Current shared work generation.
        previous_duration_seconds: Duration of the previous pipeline
            run, when a report already existed.

    """

    previous_duration_seconds: float | None
    pipeline: str
    run_id: str
    started: float
    started_at: str
    group_count: int
    fractions: dict[str, float]
    fail_marks: dict[str, float]
    activities: dict[str, ToolActivity]
    order: tuple[str, ...]
    groups: dict[str, int]
    external: dict[str, RunRecord]
    adopted: dict[str, RunRecord]
    paused: dict[str, int]
    report_stamps: dict[str, tuple[int, int]]
    tool_started: dict[str, float]
    log: ActivityLog
    orchestrator: Orchestrator | None
    context: str
    handles: dict[str, ProcessHandle]
    pending: dict[str, ToolSpec]
    tools: dict[str, ToolSpec]
    coordinator: PipelineCoordinator
    generation: int


@dataclass(frozen=True, slots=True)
class _PipelineClaim:
    """Describe whether this invocation owns or observes a pipeline.

    Attributes:
        run_id: Shared owner pipeline run identifier.
        owner: Whether this invocation owns orchestration.
        coordinator: Observer coordination store when joining.
        request: Observer request when joining.
        detail: Human-readable admission decision.

    """

    run_id: str
    owner: bool
    coordinator: PipelineCoordinator | None = None
    request: PipelineRequest | None = None
    detail: str = ""


@final
class Constants:
    """Group module-level constants.

    Attributes:
        empty_exclude: Grouped module constant.
        venv_names: Grouped module constant.
        min_python: Grouped module constant.
        pipeline_join_grace_seconds: Grouped module constant.
        counted_suffixes: Grouped module constant.

    """

    empty_exclude: Final[frozenset[str]] = frozenset()
    venv_names: Final[tuple[str, ...]] = (".venv", "venv", "env", ".env")
    min_python: Final[tuple[int, int]] = (3, 13)
    pipeline_join_grace_seconds: Final[float] = 0.6
    counted_suffixes: Final[tuple[str, ...]] = (
        ".py",
        ".json",
        ".html",
        ".css",
        ".md",
    )


def _default_root() -> Path:
    """Resolve the exactused project root before any flag is parsed.

    ``EXACTUS_ROOT`` wins; otherwise an ``exactus`` executable exactuss the
    project it sits in (``<project>/exec/exactus``),
    and anything else exactuss the current working directory. Server
    flags such as ``--entrypoint`` never move the root, so results
    always land in ``<project>/EXACTUS_RESULTS``. A system-wide install
    such as ``/usr/local/bin/exactus`` does not sit inside a project, so
    its directory only counts when it carries project markers —
    otherwise reports land beside the invocation, not inside the
    installation directory.

    Returns:
        Absolute project root.

    """
    if explicit := environ.get("EXACTUS_ROOT"):
        return Path(explicit).expanduser().resolve()
    launcher: Path = Path(argv[0]).resolve()
    if (
        launcher.name in {"exactus", "exactus.pyz"}
        and launcher.is_file()
        and is_zipfile(filename=launcher)
    ):
        if launcher.parent.name in {"exec", "build"}:
            return launcher.parent.parent
        markers: tuple[str, ...] = ("pyproject.toml", "package.json", ".git")
        if any((launcher.parent / marker).exists() for marker in markers):
            return launcher.parent
    return Path.cwd().resolve()


def _bundled_runtime() -> bool:
    """Return whether this process executes from a bundled zipapp.

    Source checkouts invoke ``python exactus`` with ``argv[0]`` naming
    the package directory, while installed executables resolve
    ``argv[0]`` to the pyz archive itself — the shell passes the real
    script path to the interpreter even for bare ``exactus`` calls.

    Returns:
        Whether ``argv[0]`` resolves to a zipapp archive.

    """
    launcher: Path = Path(argv[0])
    if launcher.is_dir():
        return False
    if not launcher.is_file():
        found: str | None = which(cmd=argv[0])
        if found is None:
            return False
        launcher = Path(found)
    return is_zipfile(filename=launcher)


def _bundled_self_test() -> bool:
    """Return whether this build opted in to ``self_test``.

    ``python -m exactus.packages.package --build --build-self-test``
    writes a ``SELF_TEST`` marker into the staged package; source
    checkouts never carry it.

    Returns:
        Whether the marker file is present in the package resources.

    """
    try:
        return resource_files("exactus").joinpath("SELF_TEST").is_file()
    except (ModuleNotFoundError, OSError):
        return False


def _bundled_unavailable() -> frozenset[str]:
    """Tool identifiers unavailable in the bundled executable.

    ``self_test`` self-diagnoses the toolkit against a generated
    fixture; it stays available from source and on executables built
    with the ``--build-self-test`` opt-in, and is hidden otherwise.

    Returns:
        ``{"self_test"}`` for zipapp runs lacking the opt-in marker;
        empty otherwise.

    """
    if _bundled_runtime() and (not _bundled_self_test()):
        return frozenset({"self_test"})
    return frozenset()


def _venv_version(*, venv: Path) -> tuple[int, int] | None:
    """Read the ``major.minor`` Python version recorded in ``pyvenv.cfg``.

    Args:
        venv: Virtual environment directory.

    Returns:
        Version tuple, or ``None`` when it cannot be determined.

    """
    with suppress(OSError):
        for line in (
            (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
        ):
            key, _, value = line.partition("=")
            if key.strip() not in {"version", "version_info"}:
                continue
            major, _, rest = value.strip().partition(".")
            minor: str = rest.partition(".")[0]
            if major.isdigit() and minor.isdigit():
                return (int(major), int(minor))
    return None


def project_interpreter(*, root: Path) -> tuple[Path, Path] | None:
    """Locate the project's virtualenv and its Python interpreter.

    Conventional names (``.venv``, ``venv``, ``env``, ``.env``) are
    tried first, then any direct child carrying ``pyvenv.cfg``.

    Args:
        root: Project root.

    Returns:
        ``(venv, interpreter)``, or ``None`` when no venv exists.

    """
    named: list[Path] = [root / name for name in Constants.venv_names]
    with suppress(OSError):
        named.extend(
            child
            for child in sorted(root.iterdir())
            if child.is_dir() and child not in named
        )
    for venv in named:
        if not (venv / "pyvenv.cfg").is_file():
            continue
        for interpreter in (
            venv / "bin" / "python",
            venv / "Scripts" / "python.exe",
        ):
            if interpreter.is_file():
                return (venv, interpreter)
    return None


type ParserFactory = Callable[[], ArgumentParser]


class Check:
    """Coordinate canonical exactus tools without CLI entrypoints.

    Attributes:
        root: Repository root containing the exactus tree.
        exactus_root: Aggregate ``EXACTUS_RESULTS`` output directory.
        poll_seconds: Delay between live progress refreshes.
        debug_marker: Filename of the sprint debug directive file.
        debug_dir: Default sprint capture directory name.
        debug_file: Sprint capture filename inside the directory.
        config_files: Loaded ``[tool.exactus]`` files, nearest first.
        collect_files: Whether finding files are bundled into each
            report's ``FILES`` folder.

    """

    root: ClassVar[Path] = _default_root()
    exactus_root: ClassVar[Path] = root / "EXACTUS_RESULTS"
    collect_files: ClassVar[bool] = False
    poll_seconds: Final[float] = 0.2
    debug_marker: Final[str] = "DEBUG.txt"
    debug_dir: Final[str] = "debug"
    debug_file: Final[str] = "out.txt"
    _progress_lines: int = 0
    _interrupt: Event = Event()
    _child: Popen[bytes] | None = None
    config_files: ClassVar[tuple[ConfigFile, ...]] = ()
    _config_key: ClassVar[tuple[Path, str] | None] = None

    @classmethod
    def load_config(cls, *, force: bool = False) -> None:
        """Discover and validate ``[tool.exactus]`` for the current root.

        Args:
            force: Reload even when this root was already loaded.

        """
        key: tuple[Path, str] = (cls.root, environ.get("EXACTUS_CONFIG", ""))
        if not force and cls._config_key == key:
            return
        files: tuple[ConfigFile, ...] = discovery_from_environment(
            start=cls.root,
        )
        validate(
            files=files,
            parsers={
                tool.identifier: tool_parser(module=tool.module)
                for tool in _GroupFinalConstants.exactus_catalog.tools()
            },
            pipelines=frozenset(
                pipeline.identifier
                for pipeline in (
                    _GroupFinalConstants.exactus_catalog.pipelines()
                )
            ),
        )
        cls.config_files = files
        cls.exactus_root = reports_anchor(
            files=files,
            start=cls.root,
        ) / reports_directory(files=files)
        environ["EXACTUS_REPORTS_ROOT"] = str(object=cls.exactus_root)
        cls._config_key = key

    @classmethod
    def use_root(cls, *, root: Path) -> None:
        """Retarget every exactus at ``root`` (inherited by re-execs).

        Args:
            root: Project root to exactus.

        """
        cls.root = root.expanduser().resolve()
        cls.exactus_root = cls.root / "EXACTUS_RESULTS"
        environ["EXACTUS_ROOT"] = str(object=cls.root)

    @classmethod
    def venv_reexec(cls) -> None:
        """Re-exec under the project's virtualenv interpreter when present.

        Exactus tools inventory the running interpreter's environment, so
        launching this script through an unrelated ``python3`` (such as a
        conda base env) produces meaningless reports. An already active
        ``VIRTUAL_ENV`` is respected. A project venv older than the
        toolkit's minimum Python cannot host the toolkit itself, so it is
        exported as ``EXACTUS_PROJECT_PYTHON`` for test subprocesses
        instead. Zipapp invocations (``argv[0]`` is a pyz, not this
        file) re-execute under the project interpreter so bundled
        CPython-tagged native extensions keep a matching ABI; other
        embedded invocations are left alone.

        Raises:
            SystemExit: When re-exec happens, carrying the child's status.

        """
        found: tuple[Path, Path] | None = project_interpreter(root=cls.root)
        if found is None or environ.get("VIRTUAL_ENV"):
            return
        venv, candidate = found
        if Path(prefix).resolve() == venv.resolve():
            return
        version: tuple[int, int] | None = _venv_version(venv=venv)
        if version is not None and version < Constants.min_python:
            environ["EXACTUS_PROJECT_PYTHON"] = str(object=candidate)
            return
        if Path(argv[0]).resolve() != Path(__file__).resolve():
            environ["EXACTUS_PROJECT_PYTHON"] = str(object=candidate)
            if not is_zipfile(filename=Path(argv[0])):
                return
            process: Popen[bytes] = Popen(
                args=(
                    str(object=candidate),
                    str(object=Path(argv[0]).resolve()),
                    *argv[1:],
                ),
            )
            cls._child = process
            raise SystemExit(process.wait())
        process = Popen(
            args=(
                str(object=candidate),
                str(object=Path(__file__).resolve()),
                *argv[1:],
            ),
        )
        cls._child = process
        raise SystemExit(process.wait())

    @classmethod
    def run_pipeline(
        cls,
        *,
        name: str,
        tool_arguments: dict[str, tuple[str, ...]],
        exclude: frozenset[str] = Constants.empty_exclude,
        common: tuple[str, ...] = (),
    ) -> bool:
        """Run a catalog pipeline wave-by-wave with parallel tools per wave.

        Args:
            name: Pipeline identifier or alias.
            tool_arguments: Per-tool CLI arguments keyed by tool ID.
            exclude: Canonical tool identifiers removed from the waves.
            common: Flat ``--include``/``--exclude`` flag pairs forwarded
                to every wave tool that accepts them.

        Returns:
            The resulting value.

        """
        pipeline, waves, merged = cls._pipeline_plan(
            name=name,
            tool_arguments=tool_arguments,
            exclude=exclude,
            common=common,
        )
        fingerprint: str = cls._pipeline_fingerprint(
            pipeline=pipeline,
            waves=waves,
            arguments=merged,
        )
        ownership: str | bool = cls._claim_pipeline_owner(
            pipeline=pipeline.identifier,
            fingerprint=fingerprint,
        )
        if isinstance(ownership, bool):
            return ownership
        run_id: str = ownership
        run_id, output = cls._prepare_pipeline(
            pipeline=pipeline,
            common=common,
            run_id=run_id,
        )
        tools: tuple[ToolSpec, ...] = tuple(
            tool for wave in waves for tool in wave
        )
        orchestrator: Orchestrator = cls._pipeline_orchestrator(tools=tools)
        context: str = tool_context(root=cls.root, owner=run_id)
        responder: IdentityResponder | None = start_responder(
            run_id=run_id,
            runtime=cls.exactus_root / ".runtime",
        )
        run: _PipelineRun | None = None
        try:
            with StderrMirror(directory=output / "ARTIFACTS"):
                cls._pause_ahead_tools(
                    run=(
                        run := cls._new_pipeline_run(
                            pipeline=pipeline.identifier,
                            run_id=run_id,
                            waves=waves,
                            orchestrator=orchestrator,
                            context=context,
                        )
                    ),
                )
                cls._publish_activity(
                    run=run,
                    current_group=1 if waves else None,
                    status="RUNNING",
                )
                memory_results: dict[str, ToolRunResult]
                while True:
                    memory_results = cls._run_graph(
                        run=run,
                        tool_arguments=merged,
                    )
                    cls._await_reruns(run=run)
                    if cls._apply_pipeline_requests(
                        run=run,
                        results=memory_results,
                    ):
                        continue
                    if run.coordinator.seal(
                        pipeline=pipeline.identifier,
                        run_id=run_id,
                    ):
                        break
                cls._set_pipeline_accepting(
                    pipeline=pipeline.identifier,
                    run_id=run_id,
                    accepting=False,
                )
                ExactusTerminal.clear_progress(lines=cls._progress_lines)
                cls._progress_lines = 0
                reconciled: tuple[ToolRunResult, ...] = tuple(
                    ExactusApi.reconcile(result=memory_results[identifier])
                    for identifier in run.order
                )
                if cls._interrupt.is_set():
                    reconciled = tuple(
                        result
                        if result.passed
                        else replace(
                            result,
                            status="INTERRUPT",
                            resume="interrupted by user",
                        )
                        for result in reconciled
                    )
                finished_at: str = (
                    datetime.now(tz=UTC).astimezone().isoformat()
                )
                final: str = (
                    "DONE"
                    if (
                        passed := (
                            bool(reconciled)
                            and all(result.passed for result in reconciled)
                        )
                    )
                    else "FAIL"
                    if not cls._interrupt.is_set()
                    else "INTERRUPT"
                )
                run.log.record(
                    level="info" if final == "DONE" else "warning",
                    message=(
                        f"finished: {final} in "
                        f"{monotonic() - run.started:.3f}s"
                    ),
                )
                cls._publish_activity(
                    run=run,
                    current_group=None,
                    status=final,
                    finished_at=finished_at,
                )
                cls._write_pipeline_report(
                    pipeline=pipeline.identifier,
                    run_id=run_id,
                    duration_seconds=monotonic() - run.started,
                    results=reconciled,
                )
                if cls._collect_files_enabled():
                    _ = collect_report_files(
                        output=cls._pipeline_output(
                            pipeline=pipeline.identifier,
                        ),
                    )
                _ = cls._write_kill_command(
                    pipeline=pipeline.identifier,
                    run_id=run_id,
                    active=False,
                )
                cls._finish_pipeline(
                    pipeline=pipeline.identifier,
                    run_id=run_id,
                    passed=passed,
                    elapsed_seconds=monotonic() - run.started,
                )
                cls._refresh_unified(finished=pipeline.identifier)
            ExactusTerminal.results(
                title=f"exactus · {pipeline.identifier}",
                rows=tuple(
                    ResultRow(
                        tool=result.tool,
                        status=f"{result.status}*"
                        if result.replaced_after_execution
                        else result.status,
                        duration_seconds=result.duration_seconds,
                        resume=result.resume,
                        report=str(object=result.report),
                        stats=result_stats(report_json=result.report_json),
                    )
                    for result in reconciled
                ),
            )
            if cls._interrupt.is_set():
                sprint(
                    "exactus: interrupted by signal — stopped running tools",
                    file=stdout,
                )
        finally:
            cls._release_paused(run=run)
            orchestrator.close(kill_owned=True)
            stop_responder(responder=responder)
            ExactusTerminal.detach_mirrors(
                note=(
                    f"exactus · {pipeline.identifier} — "
                    f"shared pipeline finished; every joined "
                    f"invocation observed this run.\n"
                ),
            )
        cls._clear_conflict_copies()
        return passed

    @classmethod
    def run_tool(
        cls,
        *,
        name: str,
        arguments: tuple[str, ...],
        common: tuple[str, ...] = (),
    ) -> bool:
        """Run one catalog tool through the exact same Python API contract.

        Args:
            name: Tool identifier or alias.
            arguments: Tool CLI arguments.
            common: Flat ``--include``/``--exclude`` flag pairs forwarded
                when the tool's parser accepts them.

        Returns:
            The resulting value.

        Raises:
            ValueError: If the tool identifier is unknown.

        """
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=name,
        )
        if tool is None:
            msg: str = f"unknown exactus tool: {name}"
            raise ValueError(msg)
        output: Path = cls.exactus_root / tool.output
        cls._enter_root()
        if tool.file_census:
            sprint(f"files · {cls._file_census(common=common)}", file=stdout)
        cls._reset_progress(tool=tool)
        run_id: str = new_run_id()
        request: ToolRequest = ToolRequest(
            identifier=tool.identifier,
            output=output,
            arguments=(
                *cls._common_args(tool=tool, common=common),
                *cls._collect_flags(tool=tool),
                *cls._config_arguments(tool=tool, pipeline=None),
                *arguments,
            ),
            run_id=run_id,
            project_root=cls.root,
        )
        ensure_worker_path()
        context: str = tool_context(root=cls.root, owner=run_id)
        orchestrator: Orchestrator = Orchestrator.from_object_spec(
            specification=build_spec(tools=(tool,), root=cls.root),
        )
        lines: int = 0
        process_status: ProcessStatus | None = None
        started: float = monotonic()
        responder: IdentityResponder | None = start_responder(
            run_id=run_id,
            runtime=cls.exactus_root / ".runtime",
        )
        try:
            _ = orchestrator.context(name=context).create(
                process=tool.identifier,
                arguments=worker_arguments(request=request, spec=tool),
            )
            while True:
                if cls._interrupt.is_set():
                    _ = kill_context(context=context)
                    _ = cls._terminate_run_tools(output=output)
                    process_status = None
                    break
                fraction: float
                step: str
                issues: int
                fraction, step, issues, _ = cls._read_progress(
                    tool=tool,
                    run_id=run_id,
                )
                lines = ExactusTerminal.progress(
                    title=f"exactus · {tool.identifier}",
                    global_fraction=fraction,
                    stage="standalone",
                    tools=(
                        (
                            tool.identifier,
                            "RUNNING!" if issues else "RUNNING",
                            fraction,
                            step,
                            None,
                        ),
                    ),
                    previous_lines=lines,
                )
                process_status = live_status(
                    descriptors=Discovery.all(),
                    name=tool.identifier,
                    context=context,
                )
                if process_status is None or process_status.terminal:
                    break
                sleep(cls.poll_seconds)
            result: ToolRunResult = result_from_status(
                request=request,
                spec=tool,
                process_status=process_status,
                started=started,
            )
        finally:
            orchestrator.close(kill_owned=True)
            stop_responder(responder=responder)
        return cls._report_tool(tool=tool, result=result, lines=lines)

    @classmethod
    def orchestrator_options(
        cls,
        *,
        clear: list[str] | None,
        exclude_tools: list[str],
        tool_arg: list[str],
        include: list[str],
        exclude: list[str],
    ) -> tuple[frozenset[str], tuple[str, ...], dict[str, tuple[str, ...]]]:
        """Resolve the orchestrator flags shared by ``main`` and shortcuts.

        Args:
            clear: ``--clear`` operands, or ``None`` when the flag was
                absent.
            exclude_tools: ``--exclude-tools`` operands.
            tool_arg: ``--tool-arg`` ``TOOL::ARG`` operands.
            include: ``--include`` glob operands.
            exclude: ``--exclude`` glob operands.

        Returns:
            Excluded tool identifiers, flat ``--include``/``--exclude``
            flag pairs, and the per-tool argument map.

        """
        if clear is not None:
            cls._clear(names=tuple(clear))
        excluded: frozenset[str] = cls._tool_exclusions(values=exclude_tools)
        per_tool: dict[str, tuple[str, ...]] = cls._pipeline_arguments(
            values=tool_arg,
        )
        common: tuple[str, ...] = tuple(
            (
                pair
                for flag, values in (
                    ("--include", include),
                    ("--exclude", exclude),
                )
                for value in values
                for pair in (flag, value)
            ),
        )
        return (excluded, common, per_tool)

    @classmethod
    def main(cls, *, arguments: Sequence[str] | None = None) -> None:
        """Dispatch the canonical tool/pipeline CLI; no arguments means all.

        Args:
            arguments: Arguments excluding the executable name, or ``None``
                to read ``sys.argv``.

        Raises:
            SystemExit: Always, with the aggregated exit status.

        """
        ExactusTerminal.clear_screen()
        cls._install_signal_guards()
        cls.venv_reexec()
        parser: ArgumentParser = cls.create_parser()
        args: Namespace = parser.parse_args(args=arguments)
        cls.collect_files = cast(typ="bool", val=args.collect_files)
        if (root := cast(typ="str | None", val=args.root)) is not None:
            cls.use_root(root=Path(root))
        cls._prepare_config(parser=parser, args=args)
        cls._clear_conflict_copies()
        cls._heal_activity_files()
        clear: list[str] | None = cast(typ="list[str] | None", val=args.clear)
        if clear is not None:
            try:
                cls._clear(names=tuple(clear))
            except ValueError as exc:
                parser.error(message=str(object=exc))
        cls._dispatch_kill(parser=parser, args=args)
        if cast(typ="bool", val=args.list_tools):
            sprint(
                "\n".join(
                    sorted(
                        tool.identifier
                        for tool in (
                            _GroupFinalConstants.exactus_catalog.tools()
                        )
                        if tool.identifier not in _bundled_unavailable()
                    ),
                ),
                file=stdout,
            )
            raise SystemExit(0)
        if cast(typ="bool", val=args.list_pipelines):
            sprint(
                "\n".join(
                    sorted(
                        pipeline.identifier
                        for pipeline in (
                            _GroupFinalConstants.exactus_catalog.pipelines()
                        )
                    ),
                ),
                file=stdout,
            )
            raise SystemExit(0)
        excluded: frozenset[str]
        try:
            excluded = cls._tool_exclusions(
                values=cast(typ="list[str]", val=args.exclude_tools),
            )
        except ValueError as exc:
            parser.error(message=str(object=exc))
        common: tuple[str, ...] = tuple(
            (
                pair
                for flag, values in (
                    ("--include", cast(typ="list[str]", val=args.include)),
                    ("--exclude", cast(typ="list[str]", val=args.exclude)),
                )
                for value in values
                for pair in (flag, value)
            ),
        )
        selected: list[str] = list(cast(typ="list[str]", val=args.tools) or [])
        if selected:
            names, positionals = cls._select_tools(
                parser=parser,
                args=args,
                selected=selected,
                excluded=excluded,
            )
            per_tool: dict[str, tuple[str, ...]] = cls._parsed_tool_arguments(
                parser=parser,
                args=args,
            )
            ok: bool = True
            for tool_name in names:
                ok = (
                    cls.run_tool(
                        name=tool_name,
                        arguments=(*positionals, *per_tool.get(tool_name, ())),
                        common=common,
                    )
                    and ok
                )
                if cls._interrupt.is_set():
                    break
            raise SystemExit(
                0 if ok else 130 if cls._interrupt.is_set() else 1,
            )
        pipeline: str = cast(typ="str | None", val=args.pipeline) or "unified"
        passed: bool = cls._run_named_pipeline(
            parser=parser,
            name=pipeline,
            args=args,
            exclude=excluded | _bundled_unavailable(),
            common=common,
        )
        raise SystemExit(
            0 if passed else 130 if cls._interrupt.is_set() else 1,
        )

    @staticmethod
    def create_parser() -> ArgumentParser:
        """Build the orchestrator command-line parser.

        Returns:
            Configured argument parser for tool and pipeline selection.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            description=(
                "Run canonical exactus tools and staged pipelines "
                "against the current project."
            ),
        )
        selection: Final = parser.add_mutually_exclusive_group()
        _action: object = selection.add_argument(
            "-t",
            "--tools",
            "--tool",
            metavar="NAME",
            dest="tools",
            nargs="+",
            help=(
                "Run one or more catalog tools; trailing arguments are "
                "forwarded."
            ),
        )
        _action = selection.add_argument(
            "--pipeline",
            metavar="NAME",
            help="Run one named pipeline (default: unified).",
        )
        _action = parser.add_argument(
            "--tool-arg",
            action="append",
            default=[],
            metavar="TOOL::ARG",
            help="Forward one argument to a pipeline tool; repeatable.",
        )
        _action = parser.add_argument(
            "--exclude-tools",
            "--exclude-tool",
            action="extend",
            default=[],
            metavar="NAME",
            dest="exclude_tools",
            nargs="+",
            help="Skip catalog tools during pipeline runs.",
        )
        _action = parser.add_argument(
            "--include",
            action="append",
            default=[],
            metavar="GLOB",
            help=(
                "Include relative paths matching GLOB; forwarded to every "
                "tool that accepts it; repeatable."
            ),
        )
        _action = parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            metavar="GLOB",
            help=(
                "Exclude relative paths matching GLOB; forwarded to every "
                "tool that accepts it; repeatable."
            ),
        )
        _action = parser.add_argument(
            "--collect-files",
            action="store_true",
            help=(
                "Bundle every file a report lists findings for into a "
                "FILES folder beside each report (README.md, TREE.txt and "
                "files.zip keeping the project folder structure); "
                "forwarded to every tool that accepts it."
            ),
        )
        _action = parser.add_argument(
            "--root",
            metavar="DIR",
            help=(
                "Project to check (default: an exactus copied into a "
                "project, EXACTUS_ROOT, or the current directory)."
            ),
        )
        _action = parser.add_argument(
            "--config",
            metavar="FILE",
            help=(
                "Read [tool.exactus] from FILE instead of discovering "
                "pyproject.toml files."
            ),
        )
        _action = parser.add_argument(
            "--no-config",
            action="store_true",
            help="Ignore every pyproject.toml [tool.exactus] table.",
        )
        _action = parser.add_argument(
            "--list-tools",
            action="store_true",
            help="List catalog tool identifiers and exit.",
        )
        _action = parser.add_argument(
            "--list-pipelines",
            action="store_true",
            help="List pipeline identifiers and exit.",
        )
        _action = parser.add_argument(
            "--clear",
            nargs="*",
            default=None,
            metavar="NAME",
            help="Clear EXACTUS_RESULTS (optionally selected tools) first.",
        )
        _action = parser.add_argument(
            "--kill",
            nargs="*",
            default=None,
            metavar="NAME",
            help=(
                "Terminate live Exactus runs (optionally for selected "
                "tool or pipeline outputs) and exit."
            ),
        )
        _action = parser.add_argument(
            "--kill-all",
            "--kill_all",
            action="store_true",
            help=(
                "Scan every visible process for Exactus and terminate "
                "verified run trees plus Exactus-named leftovers."
            ),
        )
        _action = parser.add_argument(
            "tool_args",
            nargs="*",
            metavar="TOOL_ARG",
            help="Arguments forwarded to --tool.",
        )
        del _action
        return parser

    @classmethod
    def _report_tool(
        cls,
        *,
        tool: ToolSpec,
        result: ToolRunResult,
        lines: int,
    ) -> bool:
        """Reconcile, display, and finalize a standalone tool result.

        Args:
            tool: Catalog tool that ran.
            result: Worker-produced run result.
            lines: Progress lines to clear before reporting.

        Returns:
            Whether the reconciled result passed.

        """
        ExactusTerminal.clear_progress(lines=lines)
        reconciled: ToolRunResult = ExactusApi.reconcile(result=result)
        if cls._interrupt.is_set() and (not reconciled.passed):
            reconciled = replace(
                reconciled,
                status="INTERRUPT",
                resume="interrupted by user",
            )
        ExactusTerminal.results(
            title=f"exactus · {tool.identifier}",
            rows=(
                ResultRow(
                    tool=reconciled.tool,
                    status=reconciled.status,
                    duration_seconds=reconciled.duration_seconds,
                    resume=reconciled.resume,
                    report=str(object=reconciled.report),
                    stats=result_stats(report_json=reconciled.report_json),
                ),
            ),
        )
        if cls._interrupt.is_set():
            sprint(
                "exactus: interrupted by signal — stopped running tools",
                file=stdout,
            )
        cls._heal_activity_files()
        cls._clear_conflict_copies()
        cls._refresh_unified(finished=tool.identifier)
        return reconciled.passed

    @classmethod
    def _config_arguments(
        cls,
        *,
        tool: ToolSpec,
        pipeline: str | None,
    ) -> tuple[str, ...]:
        """Render the configured arguments of one tool.

        Args:
            tool: Catalog tool being run.
            pipeline: Pipeline whose scoped table also applies.

        Returns:
            Tokens placed after any preset and before CLI arguments.

        """
        cls.load_config()
        if not cls.config_files:
            return ()
        return argv_for(
            files=cls.config_files,
            tool=tool.identifier,
            parser=tool_parser(module=tool.module),
            pipeline=pipeline,
        )

    @classmethod
    def _enter_root(cls) -> None:
        """Move into the project root before spawning tool workers.

        Spawned interpreters put their working directory on
        ``sys.path``, so stray modules in the caller's directory (for
        example a ``/tmp/msvcrt`` folder) could shadow the standard
        library inside every worker.
        """
        with suppress(OSError):
            chdir(path=cls.root)

    @classmethod
    def _file_census(cls, *, common: tuple[str, ...]) -> str:
        """Count reportable project files by suffix for the run banner.

        Walks ``cls.root`` honoring the configured and command-line
        include/exclude globs (plus the built-in excludes) and counts
        the ``.py``, ``.json``, ``.html``, ``.css`` and ``.md`` files
        the tools will see.

        Args:
            common: Flat ``(flag, value, ...)`` include/exclude pairs.

        Returns:
            One-line summary such as ``12 py · 3 json``.

        """
        pairs: tuple[tuple[str, str], ...] = tuple(
            zip(common[::2], common[1::2], strict=True),
        )
        includes: list[str] = [
            value for flag, value in pairs if flag == "--include"
        ]
        excludes: list[str] = [
            value for flag, value in pairs if flag == "--exclude"
        ]
        values: dict[str, JsonValue] = stacked(files=cls.config_files, path=())
        bucket: list[str]
        for key, bucket in (("include", includes), ("exclude", excludes)):
            configured: JsonValue | None = values.get(key)
            if isinstance(configured, list):
                bucket.extend(str(object=item) for item in configured)
            elif isinstance(configured, str):
                bucket.append(configured)
        counts: dict[str, int] = dict.fromkeys(Constants.counted_suffixes, 0)
        patterns: tuple[str, ...] = (
            *ExactusCommonTables.DEFAULT_EXCLUDES,
            *excludes,
        )
        dirpath: str
        dirnames: list[str]
        filenames: list[str]
        for dirpath, dirnames, filenames in walk(top=cls.root):
            base: Path = Path(dirpath)
            relative_dir: str = base.relative_to(cls.root).as_posix()
            prefix: str = "" if relative_dir == "." else f"{relative_dir}/"
            dirnames[:] = [
                name
                for name in dirnames
                if not is_reports_tree(directory=base / name)
                and (
                    not any(
                        fnmatch(name=f"{prefix}{name}", pat=pattern)
                        or fnmatch(name=f"{prefix}{name}/x", pat=pattern)
                        for pattern in patterns
                    )
                )
            ]
            filename: str
            for filename in filenames:
                path: Path = base / filename
                if path.suffix not in counts:
                    continue
                if match_path(
                    path=path,
                    root=cls.root,
                    includes=tuple(includes),
                    excludes=tuple(excludes),
                ):
                    counts[path.suffix] += 1
        return " · ".join(
            f"{counts[suffix]} {suffix.removeprefix('.')}"
            for suffix in Constants.counted_suffixes
        )

    @classmethod
    def _clear_conflict_copies(cls) -> None:
        """Reconcile sync folders and remove numbered report-file copies."""
        _ = clear_conflict_copies(root=cls.root)
        if not cls.exactus_root.is_dir():
            return
        pattern: str = (
            "(?P<stem>.+) (?P<index>[2-9][0-9]*)(?P<suffix>\\.[^.]+)?"
        )
        candidates: list[Path] = []
        parent: Path
        directories: list[str]
        files: list[str]
        for parent, directories, files in cls.exactus_root.walk():
            directories[:] = [
                name for name in directories if name != ".history"
            ]
            candidates.extend(parent / name for name in files)
        paths: list[Path] = sorted(
            candidates,
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for path in paths:
            if path.is_dir() or (
                not path.exists() and (not path.is_symlink())
            ):
                continue
            match: Match[str] | None = fullmatch(
                pattern=pattern,
                string=path.name,
            )
            if match is None:
                continue
            canonical: Path = path.with_name(
                name=match.group("stem") + (match.group("suffix") or ""),
            )
            if canonical.is_dir() != path.is_dir() or not canonical.exists():
                continue
            cls._remove(path=path)

    @classmethod
    def _install_signal_guards(cls) -> None:
        """Route termination signals into a cooperative interrupt flag.

        Interrupt, terminate, hang-up, quit, break, and suspend requests
        set ``_interrupt`` instead of raising ``KeyboardInterrupt``, so
        poll loops abort the run, live tool workers are terminated through
        the run registry, and no traceback reaches the terminal. A second
        signal after the flag is set exits the process immediately.

        """

        def _flag(signum: int, _frame: FrameType | None) -> None:
            """Set the interrupt flag and forward the signal to the child.

            Args:
                signum: Signal number that was received.
                _frame: Interrupted stack frame, unused.

            """
            exit_if_replaced()
            child: Popen[bytes] | None = cls._child
            if child is not None and child.poll() is None:
                with suppress(OSError, ValueError):
                    child.send_signal(sig=signum)
            if cls._interrupt.is_set():
                _exit(status=128 + signum)
            cls._interrupt.set()

        for name in (
            "SIGINT",
            "SIGTERM",
            "SIGHUP",
            "SIGQUIT",
            "SIGBREAK",
            "SIGTSTP",
        ):
            signum: Signals | None = getattr(Signals, name, None)
            if signum is None:
                continue
            with suppress(OSError, ValueError):
                _ = signal(signalnum=signum, handler=_flag)

    @classmethod
    def _terminate_run_tools(
        cls,
        *,
        pipeline_run_id: str | None = None,
        output: Path | None = None,
    ) -> int:
        """Terminate live run records matching the given ownership filters.

        Args:
            pipeline_run_id: Owning pipeline run identifier.
            output: Output directory whose owning run should terminate.

        Returns:
            Number of worker process trees signalled.

        """
        runtime: Path = cls.exactus_root / ".runtime"
        registry: RunRegistry = RunRegistry(path=runtime / "runs.db")
        secret: bytes | None = None
        with suppress(OSError, ValueError):
            secret = authkey(runtime=runtime)
        terminator: ProcessTerminator = ProcessTerminator()
        stopped: int = 0
        record: RunRecord
        for record in registry.live():
            matched: bool = (
                record.output == str(object=output.resolve())
                if output is not None
                else pipeline_run_id is None
                or (
                    record.kind == "tool"
                    and record.pipeline_run_id == pipeline_run_id
                )
            )
            if not matched:
                continue
            descriptor: Descriptor | None = Discovery.find(
                name=record.identifier,
                context=tool_context(
                    root=cls.root,
                    owner=record.pipeline_run_id or record.run_id,
                ),
            )
            if descriptor is not None:
                with suppress(OSError, RuntimeError):
                    _ = Client.request(descriptor=descriptor, command="kill")
            identity: RunIdentity | None = (
                identify(pid=record.pid, authkey=secret)
                if secret is not None
                else None
            )
            if identity is not None:
                with suppress(OSError, RuntimeError):
                    _ = terminator.terminate(identity=identity, force=True)
            else:
                terminate_tree(
                    pid=descriptor.pid
                    if descriptor is not None
                    else record.pid,
                )
            stopped += 1
        return stopped

    @classmethod
    def _dispatch_kill(
        cls,
        *,
        parser: ArgumentParser,
        args: Namespace,
    ) -> None:
        """Handle ``--kill`` and ``--kill-all`` requests.

        Args:
            parser: Active command-line parser for error reporting.
            args: Parsed command-line namespace.

        Raises:
            SystemExit: When a kill request was handled.

        """
        if cast(typ="bool", val=args.kill_all):
            verified: int
            leftovers: int
            verified, leftovers = cls._kill_all()
            sprint(
                (
                    f"kill-all: terminated "
                    f"{verified} processes in verified run trees and "
                    f"{leftovers} unverified leftovers"
                ),
                file=stdout,
            )
            raise SystemExit(0)
        kill: list[str] | None = cast(typ="list[str] | None", val=args.kill)
        if kill is not None:
            try:
                stopped: int = cls._kill(names=tuple(kill))
            except ValueError as exc:
                parser.error(message=str(object=exc))
            sprint(f"kill: signalled {stopped} run process trees", file=stdout)
            raise SystemExit(0)

    @classmethod
    def _candidate_authkeys(cls) -> list[bytes]:
        """Collect every runtime secret usable for process interrogation.

        Each runtime directory generates its own ``authkey`` secret, so a
        global scan must authenticate with every reachable key rather
        than only the current project's.

        Returns:
            Distinct secrets long enough for the wire protocol.

        """
        seen: set[bytes] = set()
        keys: list[bytes] = []

        def add(candidate: bytes) -> None:
            """Record ``candidate`` once when it is protocol-sized.

            Args:
                candidate: Secret to append when long enough and unseen.

            """
            if (
                len(candidate) >= AccessConstants.secret_bytes
                and candidate not in seen
            ):
                seen.add(candidate)
                keys.append(candidate)

        runtime: Path = cls.exactus_root / AccessConstants.directory
        with suppress(OSError, ValueError):
            add(candidate=authkey(runtime=runtime))
        registry: RunRegistry = RunRegistry(path=runtime / "runs.db")
        for record in registry.live():
            keyfile: Path = (
                Path(record.output).parent
                / AccessConstants.directory
                / AccessConstants.filename
            )
            with suppress(OSError):
                add(candidate=keyfile.read_bytes())
        return keys

    @classmethod
    def _kill_all(cls) -> tuple[int, int]:
        """Terminate every verified Exactus process tree on this host.

        Authenticated responders yield verified identities terminated
        through :class:`ProcessTerminator`; surviving interpreter or
        Exactus-named processes without a verifiable identity are
        removed through ``terminate_tree`` as a last resort.

        Returns:
            ``(verified, leftovers)`` process counts signalled.

        """
        identities: dict[int, RunIdentity] = {}
        for key in cls._candidate_authkeys():
            try:
                for identity in discover(authkey=key, full_scan=True):
                    identities[identity.root_pid] = identity
            except (OSError, ValueError):
                continue
        terminator: ProcessTerminator = ProcessTerminator()
        verified: int = 0
        for identity in identities.values():
            try:
                result: TerminationResult = terminator.terminate(
                    identity=identity,
                    force=True,
                )
            except (DatabaseError, OSError, RuntimeError):
                continue
            verified += result.count
        leftovers: int = 0
        for pid in cls._exactus_processes() - {getpid()}:
            with suppress(OSError, Error, RuntimeError):
                terminate_tree(pid=pid)
                leftovers += 1
        return (verified, leftovers)

    @classmethod
    def _kill(cls, *, names: tuple[str, ...]) -> int:
        """Terminate live run records without deleting report output.

        Args:
            names: ``--kill`` operands; empty selects every live run.

        Returns:
            Worker process trees signalled.

        Raises:
            ValueError: If an operand names no tool, pipeline or
                EXACTUS_RESULTS directory.

        """
        if not names:
            return cls._terminate_run_tools()
        stopped: int = 0
        for name in names:
            target: Path | None = cls._clear_target(name=name)
            if target is None:
                msg: str = (
                    f"--kill requires a tool, pipeline or "
                    f"EXACTUS_RESULTS folder, got: {name}"
                )
                raise ValueError(msg)
            stopped += cls._terminate_run_tools(output=target)
        return stopped

    @classmethod
    def _pipelines_root(cls) -> Path:
        """Return the directory holding every pipeline's output.

        Returns:
            ``EXACTUS_RESULTS/PIPELINES``.

        """
        return cls.exactus_root / "PIPELINES"

    @classmethod
    def _pipeline_output(cls, *, pipeline: str) -> Path:
        """Return the canonical aggregate output directory for a pipeline.

        Args:
            pipeline: Canonical pipeline identifier.

        Returns:
            ``EXACTUS_RESULTS/PIPELINES/<PIPELINE>``.

        """
        return cls._pipelines_root() / pipeline.upper().replace("-", "_")

    @classmethod
    def _pipeline_workspace(cls, *, pipeline: str, run_id: str) -> Path:
        """Create the pipeline output directory and its kill command.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: New pipeline run identifier.

        Returns:
            The recreated ``PIPELINES/<PIPELINE>`` directory.

        """
        output: Path = cls._pipeline_output(pipeline=pipeline)
        cls._remove_legacy_output(pipeline=pipeline)
        if output.exists():
            rmtree(path=output)
        (output / "ARTIFACTS").mkdir(parents=True, exist_ok=True)
        _ = cls._write_kill_command(pipeline=pipeline, run_id=run_id)
        return output

    @classmethod
    def _owner_path(cls, *, pipeline: str) -> Path:
        """Return one pipeline's inspectable ownership record.

        Args:
            pipeline: Canonical pipeline identifier.

        Returns:
            ``PIPELINES/<PIPELINE>/ARTIFACTS/owner.json``.

        """
        return (
            cls._pipeline_output(pipeline=pipeline)
            / "ARTIFACTS"
            / "owner.json"
        )

    @classmethod
    def _observe_pipeline(
        cls,
        *,
        pipeline: str,
        coordinator: PipelineCoordinator,
        request: PipelineRequest,
    ) -> bool:
        """Wait for one shared pipeline while its owner mirrors progress.

        Args:
            pipeline: Canonical pipeline identifier.
            coordinator: Shared transactional coordination store.
            request: This invocation's reset request.

        Returns:
            Whether the shared pipeline finished successfully.

        """
        sprint(
            (
                f"exactus · {pipeline} · joined {request.pipeline_run_id}; "
                f"waiting for owner reset"
            ),
            file=stdout,
        )
        announced: str = ""
        while not cls._interrupt.is_set():
            current: PipelineRequest | None = coordinator.get(
                request_id=request.request_id,
            )
            if current is not None and current.detail != announced:
                announced = current.detail
                if current.tty is None and announced:
                    sprint(f"timeline · {announced}", file=stdout)
            if (
                current is not None
                and current.state == PipelineRequestConstants.failed
            ):
                sprint(
                    (
                        f"exactus: shared reset failed: "
                        f"{current.error or current.detail}"
                    ),
                    file=stdout,
                )
                return False
            owner: PipelineOwner | None = coordinator.owner(pipeline=pipeline)
            if owner is None or owner.run_id != request.pipeline_run_id:
                sprint(
                    "exactus: shared pipeline owner disappeared",
                    file=stdout,
                )
                return False
            if owner.state not in {
                PipelineRequestConstants.running,
                PipelineRequestConstants.sealed,
            }:
                passed: bool = owner.state == "DONE"
                coordinator.settle_observer(
                    request_id=request.request_id,
                    state=PipelineRequestConstants.complete,
                    detail=f"shared pipeline finished: {owner.state}",
                )
                return passed
            sleep(cls.poll_seconds)
        coordinator.settle_observer(
            request_id=request.request_id,
            state=PipelineRequestConstants.detached,
            detail="observer interrupted while shared owner continued",
        )
        return False

    @classmethod
    def _claim_pipeline_owner(
        cls,
        *,
        pipeline: str,
        fingerprint: str,
    ) -> str | bool:
        """Elect an owner, observe a compatible owner, or wait to retry.

        Args:
            pipeline: Canonical pipeline identifier.
            fingerprint: Effective pipeline configuration hash.

        Returns:
            Owner run identifier, or shared pipeline result for an observer.

        """
        while not cls._interrupt.is_set():
            claim: _PipelineClaim = cls._claim_pipeline(
                pipeline=pipeline,
                fingerprint=fingerprint,
            )
            if claim.owner:
                return claim.run_id
            if claim.coordinator is not None and claim.request is not None:
                return cls._observe_pipeline(
                    pipeline=pipeline,
                    coordinator=claim.coordinator,
                    request=claim.request,
                )
            sprint(
                f"timeline · {claim.detail}; waiting for {claim.run_id}",
                file=stdout,
            )
            coordinator: PipelineCoordinator = PipelineCoordinator(
                runtime=cls.exactus_root / ".runtime",
            )
            while not cls._interrupt.is_set():
                owner: PipelineOwner | None = coordinator.owner(
                    pipeline=pipeline,
                )
                if (
                    owner is None
                    or owner.run_id != claim.run_id
                    or owner.state
                    not in {
                        PipelineRequestConstants.running,
                        PipelineRequestConstants.sealed,
                    }
                    or (not process_exists(pid=owner.pid))
                ):
                    break
                sleep(cls.poll_seconds)
        return False

    @classmethod
    def _activity_path(cls, *, pipeline: str) -> Path:
        """Return the canonical live pipeline activity artifact.

        Args:
            pipeline: Canonical pipeline identifier.

        Returns:
            ``PIPELINES/<PIPELINE>/ARTIFACTS/@activity.json``.

        """
        return (
            cls._pipeline_output(pipeline=pipeline)
            / "ARTIFACTS"
            / ActivityTables.file_name
        )

    @classmethod
    def _write_activity(cls, *, activity: PipelineActivity) -> None:
        """Atomically write a pretty-indented pipeline activity document.

        Args:
            activity: Live pipeline activity record.

        """
        ActivityFile.write(
            path=cls._activity_path(pipeline=activity.name),
            document=activity.document(),
        )

    @classmethod
    def _remove_legacy_output(cls, *, pipeline: str) -> None:
        """Delete a pipeline report left at the pre-``PIPELINES`` location.

        Only a directory whose ``result.json`` says ``kind: pipeline`` is
        removed, so a tool output of the same name is never touched.

        Args:
            pipeline: Canonical pipeline identifier.

        """
        legacy: Path = cls.exactus_root / pipeline.upper().replace("-", "_")
        report: dict[str, JsonValue] | None = read_json(
            path=legacy / "result.json",
        )
        if report is not None and report.get("kind") == "pipeline":
            with suppress(OSError):
                cls._remove(path=legacy)

    @classmethod
    def _claim_pipeline(
        cls,
        *,
        pipeline: str,
        fingerprint: str = "test-default",
    ) -> _PipelineClaim:
        """Atomically own, observe, or wait for one named pipeline.

        Args:
            pipeline: Canonical pipeline identifier.
            fingerprint: Effective pipeline configuration hash.

        Returns:
            Ownership, observer request, or wait decision.

        """
        legacy_owner: Path = cls.exactus_root / ".runtime" / "pipeline.json"
        run_id: str = new_run_id()
        coordinator: PipelineCoordinator = PipelineCoordinator(
            runtime=cls.exactus_root / ".runtime",
        )
        decision: PipelineClaim = coordinator.claim(
            pipeline=pipeline,
            run_id=run_id,
            pid=getpid(),
            fingerprint=fingerprint,
            tty=ExactusTerminal.tty_name(),
        )
        if decision.mode == "observer":
            return _PipelineClaim(
                run_id=decision.owner.run_id,
                owner=False,
                coordinator=coordinator,
                request=decision.request,
                detail=decision.detail,
            )
        if decision.mode == "wait":
            return _PipelineClaim(
                run_id=decision.owner.run_id,
                owner=False,
                coordinator=None,
                request=None,
                detail=decision.detail,
            )
        registry: RunRegistry = RunRegistry(
            path=cls.exactus_root / ".runtime" / "runs.db",
        )
        output_dir: Path = cls._pipeline_output(pipeline=pipeline)
        conflicts: tuple[RunRecord, ...] | None = registry.claim(
            request=RunClaim(
                kind="pipeline",
                identifier=pipeline,
                run_id=run_id,
                pipeline_run_id=None,
                pid=getpid(),
                output=output_dir,
                targets=(str(object=output_dir),),
            ),
        )
        if conflicts is not None:
            conflict: RunRecord
            for conflict in conflicts:
                if conflict.kind != "pipeline":
                    terminate_tree(pid=conflict.pid, replaced=True)
        with suppress(OSError):
            legacy_owner.unlink(missing_ok=True)
        return _PipelineClaim(
            run_id=run_id,
            owner=True,
            coordinator=coordinator,
            detail=decision.detail,
        )

    @classmethod
    def _write_kill_command(
        cls,
        *,
        pipeline: str,
        run_id: str,
        active: bool = True,
    ) -> Path:
        """Publish ``kill.sh`` terminating this run's whole process tree.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owned pipeline run identifier.
            active: Whether the script kills live processes; ``False``
                leaves a no-op stub so a recycled pid is never targeted.

        Returns:
            The generated script path.

        """
        path: Path = (
            cls._pipeline_output(pipeline=pipeline) / "ARTIFACTS" / "kill.sh"
        )
        if not active:
            _ = path.write_text(
                data=(
                    f"#!/usr/bin/env bash\n# exactus "
                    f"{pipeline} run {run_id} already finished.\nexit 0\n"
                ),
                encoding="utf-8",
            )
            path.chmod(mode=493)
            return path
        runs_db: Path = cls.exactus_root / ".runtime" / "runs.db"
        _ = path.write_text(
            data="\n".join(
                (
                    "#!/usr/bin/env bash",
                    (
                        f"# Terminate exactus "
                        f"{pipeline} run {run_id} and every tool process."
                    ),
                    "set -u",
                    f"ROOT_PID={getpid()}",
                    f"RUN_ID='{run_id}'",
                    f'RUNS_DB="{runs_db}"',
                    'RUNS_SQL="'
                    + external_cli_sql(
                        statement=live_processes_for_run(run_id="$RUN_ID"),
                    )
                    + ';"',
                    'roots="$ROOT_PID"',
                    (
                        'if command -v sqlite3 >/dev/null 2>&1 && [ -f "$RUNS'
                        '_DB" ]; then'
                    ),
                    '\tlive=$(sqlite3 "$RUNS_DB" "$RUNS_SQL" 2>/dev/null)',
                    '\troots="$roots $live"',
                    "fi",
                    "kill_tree() {",
                    '\tlocal pid="$1" sig="${2:-TERM}" child',
                    '\tfor child in $(pgrep -P "$pid" 2>/dev/null); do',
                    '\t\tkill_tree "$child" "$sig"',
                    "\tdone",
                    '\tkill "-$sig" "$pid" 2>/dev/null',
                    "}",
                    'for pid in $roots; do kill_tree "$pid" TERM; done',
                    "sleep 2",
                    'for pid in $roots; do kill_tree "$pid" KILL; done',
                    "exit 0",
                    "",
                ),
            ),
            encoding="utf-8",
        )
        path.chmod(mode=493)
        return path

    @classmethod
    def _touch_pipeline(cls, *, pipeline: str, run_id: str) -> None:
        """Refresh pipeline ownership while this invocation still owns it.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owned pipeline run identifier.

        """
        owner: Path = cls._owner_path(pipeline=pipeline)
        RunRegistry(path=cls.exactus_root / ".runtime" / "runs.db").beat(
            pulse=RunBeat(run_id=run_id),
        )
        current: dict[str, JsonValue] | None = read_json(path=owner)
        if isinstance(current, dict) and current.get("run_id") == run_id:
            merged: dict[str, JsonValue] = {
                **current,
                "name": pipeline,
                "status": "RUNNING",
                "updated_at": utc_now(),
            }
            activity: ActivityDocument | None = ActivityFile.read(
                path=cls._activity_path(pipeline=pipeline),
            )
            if activity is not None:
                merged |= {
                    "progress": activity.progress.fraction,
                    "completed": activity.progress.completed,
                    "total": activity.progress.total,
                    "step": activity.progress.step,
                    "detail": activity.progress.current,
                }
            write_json(path=owner, payload=merged)

    @classmethod
    def _set_pipeline_accepting(
        cls,
        *,
        pipeline: str,
        run_id: str,
        accepting: bool,
    ) -> None:
        """Publish whether the owner still accepts reset-and-join requests.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owned pipeline run identifier.
            accepting: Whether new invocations may join this execution.

        """
        owner: Path = cls._owner_path(pipeline=pipeline)
        current: dict[str, JsonValue] | None = read_json(path=owner)
        if not isinstance(current, dict) or current.get("run_id") != run_id:
            return
        extra: JsonValue | None = current.get("extra")
        current_extra: dict[str, JsonValue] = (
            dict(extra) if isinstance(extra, dict) else {}
        )
        current_extra["accepting"] = accepting
        write_json(
            path=owner,
            payload={
                **current,
                "extra": current_extra,
                "updated_at": utc_now(),
            },
        )

    @classmethod
    def _finish_pipeline(
        cls,
        *,
        pipeline: str,
        run_id: str,
        passed: bool,
        elapsed_seconds: float,
    ) -> None:
        """Publish the terminal pipeline ownership state when still owned.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owned pipeline run identifier.
            passed: Whether the pipeline completed successfully.
            elapsed_seconds: Pipeline wall-clock duration.

        """
        owner: Path = cls._owner_path(pipeline=pipeline)
        status: str = "DONE" if passed else "FAIL"
        PipelineCoordinator(runtime=cls.exactus_root / ".runtime").finish(
            pipeline=pipeline,
            run_id=run_id,
            state=status,
        )
        RunRegistry(path=cls.exactus_root / ".runtime" / "runs.db").finish(
            run_id=run_id,
            status=status,
            elapsed_seconds=elapsed_seconds,
        )
        current: dict[str, JsonValue] | None = read_json(path=owner)
        if isinstance(current, dict) and current.get("run_id") == run_id:
            finished_at: str = utc_now()
            extra: JsonValue | None = current.get("extra")
            write_json(
                path=owner,
                payload={
                    **current,
                    "status": status,
                    "finished_at": finished_at,
                    "updated_at": finished_at,
                    "elapsed_seconds": elapsed_seconds,
                    "completed": int(
                        cast(typ="int | str", val=current.get("total") or 0),
                    )
                    if passed
                    else int(
                        cast(
                            typ="int | str",
                            val=current.get("completed") or 0,
                        ),
                    ),
                    "progress": 1.0
                    if passed
                    else float(
                        cast(
                            typ="int | float",
                            val=current.get("progress") or 0.0,
                        ),
                    ),
                    "extra": {
                        **(dict(extra) if isinstance(extra, dict) else {}),
                        "accepting": False,
                    },
                },
            )

    @classmethod
    def _reset_progress(cls, *, tool: ToolSpec) -> None:
        """Drop a stale progress file left by an interrupted earlier run.

        Args:
            tool: Canonical tool specification about to launch.

        """
        with suppress(OSError):
            (
                cls.exactus_root / tool.output / "ARTIFACTS" / ".progress.json"
            ).unlink(missing_ok=True)

    @classmethod
    def _read_progress(
        cls,
        *,
        tool: ToolSpec,
        run_id: str,
    ) -> tuple[float, str, int, dict[str, JsonValue] | None]:
        """Read one tool's live progress artifact without requiring it.

        Args:
            tool: Canonical tool specification.
            run_id: Current invocation whose activity may be displayed.

        Returns:
            The resulting value.

        """
        path: Path = (
            cls.exactus_root / tool.output / "ARTIFACTS" / "@activity.json"
        )
        try:
            value: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (JSONDecodeError, OSError):
            return (0.0, "running", 0, None)
        if not isinstance(value, dict):
            return (0.0, "running", 0, None)
        if value.get("run_id") != run_id:
            return (0.0, "starting", 0, None)
        progress: JsonValue = value.get("progress")
        if not isinstance(progress, dict):
            return (0.0, "running", 0, None)
        raw_fraction: JsonValue = progress.get("fraction")
        raw_step: JsonValue = progress.get("step")
        issues: int = cls._progress_issues(value=progress.get("workers"))
        hierarchy: JsonValue = progress.get("hierarchy")
        return (
            min(max(float(raw_fraction), 0.0), 1.0)
            if isinstance(raw_fraction, (int, float))
            and (not isinstance(raw_fraction, bool))
            else 0.0,
            raw_step if isinstance(raw_step, str) else "running",
            issues,
            hierarchy if isinstance(hierarchy, dict) else None,
        )

    @classmethod
    def _progress_issues(cls, *, value: JsonValue) -> int:
        """Count error-bearing thread snapshots recursively.

        Args:
            value: Worker-progress payload.

        Returns:
            Number of current worker errors.

        """
        if isinstance(value, list | tuple):
            return sum(cls._progress_issues(value=item) for item in value)
        if not isinstance(value, dict):
            return 0
        errors: JsonValue = value.get("errors")
        direct: int = (
            errors
            if isinstance(errors, int) and (not isinstance(errors, bool))
            else int(bool(value.get("error")))
            + int(
                str(object=value.get("state", "")).lower()
                in {"error", "fail", "failed"},
            )
        )
        return direct + sum(
            (
                cls._progress_issues(value=item)
                for key, item in value.items()
                if key not in {"errors", "error", "state"}
            ),
        )

    @classmethod
    def _pipeline_markdown(
        cls,
        *,
        pipeline: str,
        header: tuple[str, str, float],
        results: tuple[ToolRunResult, ...],
        digests: tuple[ToolDigest, ...],
        output: Path,
    ) -> list[str]:
        """Render the aggregate pipeline report body.

        The report states what failed and why before it links anywhere:
        a status table, a section per failing tool with its dominant
        rules, hot files, first findings and failed tests, then the
        passing tools and finally links to every tool bundle.

        Args:
            pipeline: Canonical pipeline identifier.
            header: Pipeline status, run identifier, and duration.
            results: Reconciled per-tool results.
            digests: One digest per result, in order.
            output: Directory the report is written to.

        Returns:
            Markdown lines.

        """
        status, run_id, duration_seconds = header
        failing: tuple[ToolDigest, ...] = tuple(
            digest for digest in digests if digest.status != "PASS"
        )
        lines: list[str] = [
            f"# {pipeline.replace('-', ' ').title()} Pipeline",
            "",
            f"- Status: **{status}**",
            f"- Run UUID: `{run_id}`",
            f"- Duration: {duration_seconds:.3f}s",
            f"- Tools: {len(results)}",
            f"- Passed: {sum(result.passed for result in results)}",
            f"- Failed: {len(failing)}",
            "",
            "## Summary",
            "",
            "| Tool | Status | Time | Findings | Headline |",
            "| --- | --- | ---: | ---: | --- |",
        ]
        for result, digest in zip(results, digests, strict=True):
            headline: str = (
                "; ".join(digest.notes) if digest.notes else result.resume
            )
            lines.append(
                "".join(
                    (
                        f"| `{result.tool}` | **{result.status}** | ",
                        f"{result.duration_seconds:.1f}s | "
                        f"{digest.findings} | ",
                        f"{headline.replace('|', chr(92) + '|')} |",
                    ),
                ),
            )
        if failing:
            lines.extend(("", "## What failed and why", ""))
            for digest in failing:
                lines.extend(render_failure(digest=digest))
        passing: tuple[str, ...] = tuple(
            digest.tool for digest in digests if digest.status == "PASS"
        )
        if passing:
            lines.extend(
                (
                    "## Passing tools",
                    "",
                    *(f"- `{tool}`" for tool in passing),
                    "",
                ),
            )
        lines.extend(
            (
                "## Tool resumes",
                "",
                *(
                    cls._resume_line(result=result, output=output)
                    for result in results
                ),
                "",
            ),
        )
        return lines

    @classmethod
    def _write_pipeline_report(
        cls,
        *,
        pipeline: str,
        run_id: str,
        duration_seconds: float,
        results: tuple[ToolRunResult, ...],
    ) -> None:
        """Write one standardized aggregate report with linked tool resumes.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Pipeline run identifier.
            duration_seconds: Pipeline wall-clock duration.
            results: Reconciled per-tool results.

        """
        output: Path = cls._pipeline_output(pipeline=pipeline)
        passed: bool = bool(results) and all(
            result.passed for result in results
        )
        status: str = "PASS" if passed else "FAIL"
        metadata: dict[str, JsonValue] = {
            result.tool: cls._metadata(result=result, output=output)
            for result in results
        }
        snapshots: dict[str, JsonValue] = {
            result.tool: read_json(path=result.report_json) or {}
            for result in results
        }
        digests: tuple[ToolDigest, ...] = tuple(
            digest_report(
                tool=result.tool,
                fields=read_json(path=result.report_json) or {},
                status=result.status,
                resume=result.resume,
            )
            for result in results
        )
        failing: tuple[ToolDigest, ...] = tuple(
            digest for digest in digests if digest.status != "PASS"
        )
        markdown: str = "\n".join(
            cls._pipeline_markdown(
                pipeline=pipeline,
                header=(status, run_id, duration_seconds),
                results=results,
                digests=digests,
                output=output,
            ),
        )
        data: dict[str, JsonValue] = {
            "status": status,
            "kind": "pipeline",
            "pipeline": pipeline,
            "run_id": run_id,
            "duration_seconds": round(number=duration_seconds, ndigits=3),
            "tools": metadata,
            "report_snapshots": {
                tool: {
                    key: value
                    for key, value in snapshot.items()
                    if key
                    in {
                        "findings",
                        "summary",
                        "extension",
                        "totals",
                        "coverage",
                        "test_execution",
                        "status",
                    }
                }
                for tool, snapshot in snapshots.items()
                if isinstance(snapshot, dict)
            },
            "summary": {
                "status": status,
                "total": len(results),
                "passed": sum(result.passed for result in results),
                "failed": sum(not result.passed for result in results),
            },
            "digests": [digest_data(digest=item) for item in digests],
            "failures": [digest_data(digest=item) for item in failing],
        }
        _report: JsonValue = ReportBundle.write(
            paths=ReportPaths(
                markdown=output / "result.md",
                json=output / "result.json",
                web=output / "result_web",
            ),
            analyzer=pipeline,
            title=f"{pipeline.replace('-', ' ').title()} Pipeline",
            markdown=markdown,
            data=data,
        )

    @classmethod
    def _refresh_unified(cls, *, finished: str) -> None:
        """Re-render a stored UNIFIED aggregate from current tool reports.

        A tool or pipeline run completed after a ``unified`` run leaves
        that aggregate stale; rewrite its report bundle and
        ``@activity.json`` from the latest per-tool
        ``result.json`` documents.

        Args:
            finished: Identifier of the pipeline or tool run that just
                finished; the refresh is skipped for ``unified`` itself.

        """
        if finished == "unified":
            return
        output: Path = cls._pipeline_output(pipeline="unified")
        aggregate: Path = output / "result.json"
        if (
            not output.is_dir()
            or (previous := read_json(path=aggregate)) is None
        ):
            return
        try:
            unified_stamp: int = aggregate.stat().st_mtime_ns
        except OSError:
            unified_stamp = 0
        run_id_value: JsonValue = previous.get("run_id")
        duration_value: JsonValue = previous.get("duration_seconds")
        results: list[ToolRunResult] = []
        reports: dict[str, dict[str, JsonValue]] = {}
        for wave in _GroupFinalConstants.exactus_catalog.waves(
            identifier="unified",
        ):
            for tool in wave:
                tool_output: Path = cls.exactus_root / tool.output
                report_json: Path = tool_output / "result.json"
                fields: dict[str, JsonValue] | None = cls._report_fields(
                    path=report_json,
                )
                if fields is not None:
                    try:
                        stamp: int = report_json.stat().st_mtime_ns
                    except OSError:
                        stamp = 0
                    results.append(
                        replace(
                            ToolRunResult.from_report(
                                payload=fields,
                                output=tool_output,
                                fallback=ToolRunResult(
                                    tool=tool.identifier,
                                    run_id="",
                                    pipeline_run_id=None,
                                    status="FAIL",
                                    passed=False,
                                    exit_code=1,
                                    duration_seconds=0.0,
                                    resume="",
                                    report=tool_output / "result.md",
                                    report_json=report_json,
                                    report_web=tool_output
                                    / "result_web"
                                    / "index.html",
                                ),
                            ),
                            replaced_after_execution=stamp > unified_stamp,
                        ),
                    )
                    reports[tool.identifier] = fields
        if results:
            cls._write_pipeline_report(
                pipeline="unified",
                run_id=run_id_value
                if isinstance(run_id_value, str)
                else new_run_id(),
                duration_seconds=float(duration_value)
                if isinstance(duration_value, int | float)
                and (not isinstance(duration_value, bool))
                else 0.0,
                results=tuple(results),
            )
            cls._refresh_unified_activity(
                path=cls._activity_path(pipeline="unified"),
                results=tuple(results),
                reports=reports,
            )
            if cls._collect_files_enabled():
                _ = collect_report_files(output=output)

    @classmethod
    def _refresh_activity(
        cls,
        *,
        run: _PipelineRun,
        activity: ToolActivity,
    ) -> ToolActivity:
        """Adopt a newer published report for a completed tool.

        Tools recorded as ``PASS``, ``FAIL`` or ``INTERRUPT`` are
        inspected — one ``stat`` per publish per completed tool; the report
        itself is read only when its ``(mtime, size)`` stamp changed.

        Args:
            run: Mutable pipeline bookkeeping record.
            activity: Recorded activity for one tool.

        Returns:
            The recorded activity, or one refreshed from the tool's
            latest report when another run overwrote it.

        """
        if activity.status not in ("PASS", "FAIL", "INTERRUPT"):
            return activity
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=activity.name,
        )
        if tool is None:
            return activity
        path: Path = cls.exactus_root / tool.output / "result.json"
        try:
            info: stat_result = path.stat()
        except OSError:
            return activity
        stamp: tuple[int, int] = (info.st_mtime_ns, info.st_size)
        if run.report_stamps.get(activity.name) == stamp:
            return activity
        run.report_stamps[activity.name] = stamp
        fields: dict[str, JsonValue] | None = cls._report_fields(path=path)
        if fields is None or fields.get("run_id") == activity.run_id:
            return activity
        status: str = cast(typ="str", val=fields["status"])
        run_id: JsonValue = fields.get("run_id")
        generated_at: JsonValue = fields.get("generated_at")
        duration: JsonValue = fields.get("duration_seconds")
        return replace(
            activity,
            run_id=run_id if isinstance(run_id, str) else activity.run_id,
            status=status,
            report_updated=True,
            progress=1.0,
            step="complete",
            finished_at=generated_at
            if isinstance(generated_at, str)
            else activity.finished_at,
            elapsed_seconds=round(number=float(duration), ndigits=3)
            if isinstance(duration, (int, float))
            and (not isinstance(duration, bool))
            else activity.elapsed_seconds,
        )

    @classmethod
    def _heal_activity_entry(cls, *, entry: JsonValue) -> bool:
        """Adopt a tool's latest report into one recorded activity entry.

        Args:
            entry: One ``tools`` member of a published activity file.

        Returns:
            Whether the entry changed.

        """
        if not isinstance(entry, dict):
            return False
        name: JsonValue = entry.get("name")
        if entry.get("status") not in ("FAIL", "INTERRUPT") or not isinstance(
            name,
            str,
        ):
            return False
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=name,
        )
        if tool is None:
            return False
        fields: dict[str, JsonValue] | None = cls._report_fields(
            path=cls.exactus_root / tool.output / "result.json",
        )
        if fields is None:
            return False
        updates: dict[str, JsonValue] = {
            "status": fields["status"],
            "progress": 1.0,
            "step": "complete",
        }
        for key in ("run_id", "generated_at", "duration_seconds"):
            value: JsonValue = fields.get(key)
            if value is None:
                continue
            updates[
                "finished_at"
                if key == "generated_at"
                else "elapsed_seconds"
                if key == "duration_seconds"
                else key
            ] = value
        if all((entry.get(key) == value for key, value in updates.items())):
            return False
        entry.update(updates)
        return True

    @classmethod
    def _heal_activity_files(cls) -> None:
        """Reconcile recorded tool failures with their latest reports.

        Each ``FAIL``/``INTERRUPT`` entry in every published activity
        file contributes at most one ``result.json`` read — reports for
        passing tools are never opened.
        """
        path: Path
        for path in cls._pipelines_root().glob(
            pattern=f"*/ARTIFACTS/{ActivityTables.file_name}",
        ):
            payload: dict[str, JsonValue] | None = read_json(path=path)
            tools: JsonValue = (
                payload.get("items") if payload is not None else None
            )
            if payload is None or not isinstance(tools, list):
                continue
            changed: bool = False
            entry: JsonValue
            for entry in tools:
                changed |= cls._heal_activity_entry(entry=entry)
            statuses: tuple[JsonValue, ...] = tuple(
                item.get("status") for item in tools if isinstance(item, dict)
            )
            if (
                payload.get("status") in ("DONE", "FAIL")
                and statuses
                and (
                    payload["status"]
                    != (
                        "DONE"
                        if all(item == "PASS" for item in statuses)
                        else "FAIL"
                    )
                )
            ):
                payload["status"] = (
                    "DONE"
                    if all(item == "PASS" for item in statuses)
                    else "FAIL"
                )
                changed = True
            if changed:
                ActivityFile.write_json(path=path, payload=payload)

    @classmethod
    def _publish_activity(
        cls,
        *,
        run: _PipelineRun,
        current_group: int | None,
        status: str,
        finished_at: str | None = None,
    ) -> None:
        """Publish the complete programmatic state of one pipeline.

        Args:
            run: Mutable pipeline bookkeeping record.
            current_group: Currently executing wave group.
            status: Pipeline lifecycle status.
            finished_at: Terminal ISO-8601 timestamp.

        """
        identifier: str
        for identifier in run.order:
            run.activities[identifier] = cls._refresh_activity(
                run=run,
                activity=run.activities[identifier],
            )
        finished: int = sum(
            1
            for identifier in run.order
            if run.activities[identifier].status not in ("WAITING", "RUNNING")
        )
        cls._write_activity(
            activity=PipelineActivity(
                name=run.pipeline,
                run_id=run.run_id,
                status=status,
                progress=round(
                    number=cls._global_fraction(run=run),
                    ndigits=3,
                ),
                completed=finished,
                total=len(run.order),
                step=f"group {current_group}/{run.group_count}"
                if current_group is not None
                else "complete",
                detail="",
                current_group=current_group,
                group_count=run.group_count,
                previous_duration_seconds=run.previous_duration_seconds,
                started_at=run.started_at,
                finished_at=finished_at,
                elapsed_seconds=round(
                    number=monotonic() - run.started,
                    ndigits=3,
                ),
                updated_at=datetime.now(tz=UTC).astimezone().isoformat(),
                pid=getpid(),
                items=tuple(
                    run.activities[identifier] for identifier in run.order
                ),
                events=run.log.events(),
                events_dropped=run.log.dropped(),
            ),
        )

    @classmethod
    def _new_pipeline_run(
        cls: type[Check],
        *,
        pipeline: str,
        run_id: str,
        waves: tuple[tuple[ToolSpec, ...], ...],
        orchestrator: Orchestrator | None = None,
        context: str = "",
    ) -> _PipelineRun:
        """Build the initial bookkeeping record for one pipeline run.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Pipeline run identifier.
            waves: Ordered dependency waves of canonical tools.
            orchestrator: Detached-worker orchestrator.
            context: Unique pmanager context.

        Returns:
            The resulting value.

        """
        tools: tuple[ToolSpec, ...] = tuple(
            tool for wave in waves for tool in wave
        )
        order: tuple[str, ...] = tuple(tool.identifier for tool in tools)
        log: ActivityLog = ActivityLog()
        log.record(
            message=(
                f"started: {len(order)} tools in {len(waves)} dependency "
                f"groups"
            ),
        )
        groups: dict[str, int] = {
            tool.identifier: group
            for group, wave in enumerate(iterable=waves, start=1)
            for tool in wave
        }
        return _PipelineRun(
            previous_duration_seconds=previous_report_duration(
                path=cls._pipeline_output(pipeline=pipeline) / "result.json",
            ),
            pipeline=pipeline,
            run_id=run_id,
            started=monotonic(),
            started_at=datetime.now(tz=UTC).astimezone().isoformat(),
            group_count=len(waves),
            fractions=dict.fromkeys(order, 0.0),
            fail_marks={},
            activities={
                tool.identifier: ToolActivity(
                    name=tool.identifier,
                    run_id=f"{run_id}:{tool.identifier}",
                    group=groups[tool.identifier],
                    position=position,
                    status="WAITING",
                    progress=0.0,
                    step="waiting",
                    started_at=None,
                    finished_at=None,
                    elapsed_seconds=0.0,
                    issues=0,
                )
                for position, tool in enumerate(iterable=tools, start=1)
            },
            order=order,
            groups=groups,
            external={},
            adopted={},
            paused={},
            report_stamps={},
            tool_started={},
            log=log,
            orchestrator=orchestrator,
            context=context,
            handles={},
            pending={tool.identifier: tool for tool in tools},
            tools={tool.identifier: tool for tool in tools},
            coordinator=PipelineCoordinator(
                runtime=cls.exactus_root / ".runtime",
            ),
            generation=1,
        )

    @classmethod
    def _apply_pipeline_requests(
        cls,
        *,
        run: _PipelineRun,
        results: dict[str, ToolRunResult],
    ) -> bool:
        """Reset the shared work graph for every newly joined invocation.

        Simultaneous requests are coalesced into one new generation. Existing
        worker processes receive pmanager reset signals; completed tasks are
        returned to the DAG. No pipeline or worker owner process is killed.

        Args:
            run: Active owner pipeline state.
            results: Terminal task results accumulated by the owner.

        Returns:
            Whether at least one reset request was applied.

        """
        pending_requests: tuple[PipelineRequest, ...] = (
            run.coordinator.requests(
                pipeline_run_id=run.run_id,
                state=PipelineRequestConstants.pending,
            )
        )
        if not pending_requests:
            return False
        request: PipelineRequest
        for request in pending_requests:
            if request.tty is not None:
                _ = ExactusTerminal.mirror_tty(path=request.tty)
        active_descriptors, reset_count, failed_resets = (
            cls._reset_active_pipeline_workers(run=run)
        )
        if failed_resets:
            error: str = "reset signal was not accepted by: " + ", ".join(
                failed_resets,
            )
            run.coordinator.fail_requests(
                requests=pending_requests,
                error=error,
            )
            run.log.record(level="error", message=error)
            return False
        for identifier in run.order:
            active: bool = identifier in active_descriptors
            if not active:
                run.pending[identifier] = run.tools[identifier]
            else:
                run.tool_started[identifier] = monotonic()
            _ = results.pop(identifier, None)
            run.fractions[identifier] = 0.0
            cls._reset_progress(tool=run.tools[identifier])
            run.activities[identifier] = replace(
                run.activities[identifier],
                status="RUNNING" if active else "WAITING",
                progress=0.0,
                step="resetting shared generation"
                if active
                else "queued after shared reset",
                started_at=datetime.now(tz=UTC).astimezone().isoformat()
                if active
                else None,
                finished_at=None,
                elapsed_seconds=0.0,
                issues=0,
                hierarchy=None,
            )
        run.generation += 1
        run.report_stamps.clear()
        joined: str = ", ".join(
            request.request_id for request in pending_requests
        )
        run.log.record(
            message=(
                f"shared pipeline reset requested by "
                f"{joined}; restarted {reset_count} active workers and "
                f"requeued {len(run.pending)} tasks"
            ),
        )
        detail: str = (
            f"joined shared pipeline "
            f"{run.run_id}; owner started generation {run.generation}"
        )
        run.coordinator.acknowledge(
            requests=pending_requests,
            generation=run.generation,
            detail=detail,
        )
        return True

    @classmethod
    def _reset_active_pipeline_workers(
        cls,
        *,
        run: _PipelineRun,
    ) -> tuple[dict[str, Descriptor], int, list[str]]:
        """Deliver reset signals to every currently active pipeline task.

        Args:
            run: Active owner pipeline state.

        Returns:
            Active descriptors, successful reset count, and failed tool IDs.

        """
        descriptors: tuple[Descriptor, ...] = Discovery.all()
        active_descriptors: dict[str, Descriptor] = {}
        failed: list[str] = []
        identifier: str
        for identifier in run.order:
            if identifier not in run.handles and identifier not in run.adopted:
                continue
            owner: str = (
                run.adopted[identifier].pipeline_run_id
                or run.adopted[identifier].run_id
                if identifier in run.adopted
                else run.run_id
            )
            contexts: frozenset[str] = frozenset(
                {run.context, tool_context(root=cls.root, owner=owner)},
            )
            descriptor: Descriptor | None = next(
                (
                    candidate
                    for candidate in descriptors
                    if candidate.name == identifier
                    and candidate.context in contexts
                ),
                None,
            )
            if descriptor is None:
                failed.append(identifier)
            else:
                active_descriptors[identifier] = descriptor
        reset_count: int = 0
        if not failed:
            for identifier, descriptor in active_descriptors.items():
                if reset_worker(descriptor=descriptor):
                    reset_count += 1
                else:
                    failed.append(identifier)
        return (active_descriptors, reset_count, failed)

    @classmethod
    def _run_graph(
        cls,
        *,
        run: _PipelineRun,
        tool_arguments: dict[str, tuple[str, ...]],
    ) -> dict[str, ToolRunResult]:
        """Execute tools as soon as their participating dependencies settle.

        Args:
            run: Mutable pipeline bookkeeping record.
            tool_arguments: Per-tool CLI arguments keyed by tool ID.

        Returns:
            Terminal results keyed by tool identifier.

        """
        results: dict[str, ToolRunResult] = {}
        idle_started: float | None = None
        while True:
            if cls._interrupt.is_set():
                _ = kill_context(context=run.context)
                _ = cls._terminate_run_tools(pipeline_run_id=run.run_id)
                run.adopted.clear()
                break
            reset_applied: bool = cls._apply_pipeline_requests(
                run=run,
                results=results,
            )
            active: bool = bool(run.pending or run.handles or run.adopted)
            if not active:
                idle_started = (
                    monotonic() if idle_started is None else idle_started
                )
                if (
                    not reset_applied
                    and monotonic() - idle_started
                    >= Constants.pipeline_join_grace_seconds
                ):
                    break
                sleep(cls.poll_seconds)
                continue
            idle_started = None
            cls._touch_pipeline(pipeline=run.pipeline, run_id=run.run_id)
            descriptors: tuple[Descriptor, ...] = Discovery.all()
            external: dict[str, RunRecord] = cls._external_tools(run=run)
            run.external.clear()
            run.external.update(external)
            discovered_external: dict[str, Descriptor] = external_descriptors(
                records=external,
                descriptors=descriptors,
                root=cls.root,
            )
            cls._synchronize_external_reruns(
                run=run,
                results=results,
                external=external,
                descriptors=descriptors,
            )
            cls._schedule_ready_tools(
                run=run,
                results=results,
                tool_arguments=tool_arguments,
                descriptors=discovered_external,
            )
            cls._poll_owned_tools(
                run=run,
                results=results,
                tool_arguments=tool_arguments,
                descriptors=Discovery.all(),
            )
            cls._drain_adopted(
                run=run,
                external=external,
                results=results,
                descriptors=descriptors,
            )
            current_group: int | None = min(
                (
                    run.groups[identifier]
                    for identifier in run.order
                    if identifier not in results
                ),
                default=None,
            )
            cls._publish_activity(
                run=run,
                current_group=current_group,
                status="RUNNING",
            )
            cls._progress_lines = ExactusTerminal.progress(
                title=f"exactus · {run.pipeline}",
                global_fraction=cls._global_fraction(run=run),
                stage=f"settled {len(results)}/{len(run.order)}",
                tools=cls._progress_rows(run=run),
                previous_lines=cls._progress_lines,
            )
            if run.pending or run.handles or run.adopted:
                sleep(cls.poll_seconds)
        for identifier in run.order:
            if identifier not in results:
                cls._interrupt_result(
                    run=run,
                    identifier=identifier,
                    results=results,
                )
        return results

    @classmethod
    def _schedule_ready_tools(
        cls,
        *,
        run: _PipelineRun,
        results: dict[str, ToolRunResult],
        tool_arguments: dict[str, tuple[str, ...]],
        descriptors: dict[str, Descriptor],
    ) -> None:
        """Launch, adopt, pause, or dependency-block pending tools.

        Args:
            run: Pipeline bookkeeping record.
            results: Terminal results accumulated so far.
            tool_arguments: Per-tool command-line arguments.
            descriptors: External pmanager descriptors.

        """
        for identifier, tool in tuple(run.pending.items()):
            dependencies: frozenset[str] = frozenset(
                tool.dependencies,
            ) & frozenset(run.order)
            active: frozenset[str] = frozenset(
                (*run.handles, *run.adopted, *run.external),
            )
            ready: bool = dependencies.issubset(results)
            if tool.streaming_dependencies:
                ready = all(
                    dependency in results or dependency in active
                    for dependency in dependencies
                )
            if ready:
                group: int = run.groups[identifier]
                ready = all(
                    run.groups[other] >= group or other in results
                    for other in run.order
                )
            if not ready:
                cls._pause_waiting_external(
                    run=run,
                    identifier=identifier,
                    record=run.external.get(identifier),
                    descriptor=descriptors.get(identifier),
                )
                continue
            cls._start_ready_tool(
                run=run,
                tool=tool,
                arguments=tool_arguments.get(identifier, ()),
                external=run.external.get(identifier),
                descriptor=descriptors.get(identifier),
            )
            del run.pending[identifier]

    @classmethod
    def _synchronize_external_reruns(
        cls,
        *,
        run: _PipelineRun,
        results: dict[str, ToolRunResult],
        external: dict[str, RunRecord],
        descriptors: tuple[Descriptor, ...],
    ) -> None:
        """Return replaced tools and their completed dependents to the DAG.

        Args:
            run: Active pipeline state.
            results: Terminal results accumulated so far.
            external: Live runs owned by other invocations.
            descriptors: Shared pmanager discovery snapshot.

        """
        rerun: set[str] = set()
        for identifier, record in external.items():
            if identifier in run.pending or identifier in run.adopted:
                continue
            if identifier not in results and identifier not in run.handles:
                continue
            _ = results.pop(identifier, None)
            cls._release_superseded_worker(
                run=run,
                identifier=identifier,
                descriptors=descriptors,
            )
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=identifier,
            )
            if tool is not None:
                run.pending[identifier] = tool
            run.fractions[identifier] = record.progress
            _ = run.fail_marks.pop(identifier, None)
            rerun.add(identifier)
            run.log.record(message=f"{identifier} requeued by external run")
        for dependency in rerun:
            for identifier in run.order:
                if identifier not in results or not cls._tool_depends_on(
                    identifier=identifier,
                    dependency=dependency,
                ):
                    continue
                _ = results.pop(identifier, None)
                tool = _GroupFinalConstants.exactus_catalog.tool(
                    identifier=identifier,
                )
                if tool is not None:
                    run.pending[identifier] = tool
                run.fractions[identifier] = 0.0
                _ = run.fail_marks.pop(identifier, None)
                run.activities[identifier] = replace(
                    run.activities[identifier],
                    status="WAITING",
                    progress=0.0,
                    step=f"waiting for rerun of {dependency}",
                    started_at=None,
                    finished_at=None,
                    elapsed_seconds=0.0,
                )
                run.log.record(
                    message=(
                        f"{identifier} invalidated by rerun of {dependency}"
                    ),
                )

    @classmethod
    def _progress_lifecycle(
        cls,
        *,
        node: dict[str, JsonValue] | None,
        state: str,
        step: str,
        detail: str,
    ) -> dict[str, JsonValue] | None:
        """Apply one lifecycle state to a progress hierarchy.

        Args:
            node: Existing hierarchy root, when published.
            state: Lifecycle state to expose.
            step: Current lifecycle step.
            detail: Human-readable lifecycle reason.

        Returns:
            Updated hierarchy, or ``None`` when none was published.

        """
        if node is None:
            return None
        children: JsonValue = node.get("children")
        return {
            **node,
            "state": state,
            "step": step,
            "current": detail,
            "children": [
                cls._progress_lifecycle(
                    node=child,
                    state=state,
                    step=step,
                    detail=detail,
                )
                for child in children
                if isinstance(child, dict)
            ]
            if isinstance(children, list)
            else [],
        }

    @classmethod
    def _publish_external_lifecycle(
        cls,
        *,
        identifier: str,
        run_id: str,
        state: str,
        detail: str,
    ) -> None:
        """Publish a pipeline-controlled lifecycle on an external tool.

        Args:
            identifier: Canonical external tool identifier.
            run_id: External tool run identifier.
            state: Lifecycle state to publish.
            detail: Human-readable lifecycle reason.

        """
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=identifier,
        )
        if tool is None:
            return
        path: Path = (
            cls.exactus_root
            / tool.output
            / "ARTIFACTS"
            / ActivityTables.file_name
        )
        activity: ActivityDocument | None = ActivityFile.read(path=path)
        if activity is None or activity.run_id != run_id:
            return
        now: str = utc_now()
        step: str = "paused" if state == "PAUSED" else activity.progress.step
        ActivityFile.write(
            path=path,
            document=replace(
                activity,
                status=state,
                updated_at=now,
                heartbeat=replace(
                    activity.heartbeat,
                    alive=True,
                    last_beat=now,
                    phase=state.lower(),
                ),
                progress=replace(
                    activity.progress,
                    step=step,
                    current=detail,
                    hierarchy=cls._progress_lifecycle(
                        node=activity.progress.hierarchy,
                        state=state,
                        step=step,
                        detail=detail,
                    ),
                ),
            ),
        )

    @classmethod
    def _pause_waiting_external(
        cls,
        *,
        run: _PipelineRun,
        identifier: str,
        record: RunRecord | None,
        descriptor: Descriptor | None,
    ) -> None:
        """Pause an external run until its dependencies are terminal.

        Args:
            run: Pipeline bookkeeping record.
            identifier: Tool identifier.
            record: External registry record, when present.
            descriptor: External pmanager descriptor, when present.

        """
        if record is None or identifier in run.paused:
            return
        paused_worker: bool = descriptor is not None and pause_worker(
            descriptor=descriptor,
            owner=run.run_id,
        )
        pause_tree(
            pid=record.pid,
            exclude=(descriptor.pid,)
            if descriptor is not None and paused_worker
            else (),
        )
        run.paused[identifier] = record.pid
        cls._publish_external_lifecycle(
            identifier=identifier,
            run_id=record.run_id,
            state="PAUSED",
            detail="waiting for pipeline dependencies",
        )

    @classmethod
    def _poll_owned_tools(
        cls,
        *,
        run: _PipelineRun,
        results: dict[str, ToolRunResult],
        tool_arguments: dict[str, tuple[str, ...]],
        descriptors: tuple[Descriptor, ...],
    ) -> None:
        """Refresh and settle pipeline-owned workers.

        Args:
            run: Pipeline bookkeeping record.
            results: Terminal results accumulated so far.
            tool_arguments: Per-tool command-line arguments.
            descriptors: Shared discovery snapshot for this polling tick.

        """
        for identifier in tuple(run.handles):
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=identifier,
            )
            if tool is None:
                continue
            process_status: ProcessStatus | None = live_status(
                descriptors=descriptors,
                name=identifier,
                context=run.context,
            )
            fraction, step, issues, hierarchy = cls._read_progress(
                tool=tool,
                run_id=f"{run.run_id}:{identifier}",
            )
            fraction: float = max(fraction, run.fractions.get(identifier, 0.0))
            run.fractions[identifier] = fraction
            run.activities[identifier] = replace(
                run.activities[identifier],
                progress=round(number=fraction, ndigits=3),
                step=step,
                issues=issues,
                hierarchy=hierarchy,
                elapsed_seconds=round(
                    number=monotonic() - run.tool_started[identifier],
                    ndigits=3,
                ),
            )
            if process_status is not None and (not process_status.terminal):
                continue
            request: ToolRequest = cls._pipeline_request(
                run=run,
                tool=tool,
                arguments=tool_arguments.get(identifier, ()),
            )
            result: ToolRunResult = result_from_status(
                request=request,
                spec=tool,
                process_status=process_status,
                started=run.tool_started[identifier],
            )
            results[identifier] = result
            cls._settle_tool(run=run, result=result)
            del run.handles[identifier]

    @classmethod
    def _pipeline_request(
        cls,
        *,
        run: _PipelineRun,
        tool: ToolSpec,
        arguments: tuple[str, ...],
    ) -> ToolRequest:
        """Build one pipeline-owned tool request.

        Args:
            run: Pipeline bookkeeping record.
            tool: Catalog tool.
            arguments: Tool command-line arguments.

        Returns:
            Canonical worker request.

        """
        return ToolRequest(
            identifier=tool.identifier,
            output=cls.exactus_root / tool.output,
            arguments=arguments,
            run_id=f"{run.run_id}:{tool.identifier}",
            pipeline_run_id=run.run_id,
            project_root=cls.root,
        )

    @classmethod
    def _start_ready_tool(
        cls,
        *,
        run: _PipelineRun,
        tool: ToolSpec,
        arguments: tuple[str, ...],
        external: RunRecord | None,
        descriptor: Descriptor | None,
    ) -> None:
        """Adopt an external tool or launch one ready pipeline worker.

        Args:
            run: Pipeline bookkeeping record.
            tool: Ready catalog tool.
            arguments: Tool command-line arguments.
            external: Matching external run, when present.
            descriptor: Matching external pmanager descriptor.

        Raises:
            RuntimeError: If the pipeline has no process orchestrator.

        """
        identifier: str = tool.identifier
        run.tool_started[identifier] = monotonic()
        run.activities[identifier] = replace(
            run.activities[identifier],
            status="RUNNING",
            step="starting",
            issues=0,
            started_at=datetime.now(tz=UTC).astimezone().isoformat(),
        )
        if external is not None:
            released: bool = (
                resume_worker(descriptor=descriptor, owner=run.run_id)
                if descriptor is not None
                else True
            )
            if not released:
                _ = run.paused.setdefault(identifier, external.pid)
                run.activities[identifier] = replace(
                    run.activities[identifier],
                    status="PAUSED",
                    step="waiting for external release",
                )
                run.log.record(
                    message=(
                        f"{identifier} remains paused; the lease is "
                        f"still held by another owner"
                    ),
                )
                return
            if identifier in run.paused:
                paused_pid: int = run.paused.pop(identifier)
                resume_tree(pid=paused_pid)
                cls._publish_external_lifecycle(
                    identifier=identifier,
                    run_id=external.run_id,
                    state="RUNNING",
                    detail=external.step or "resumed by pipeline",
                )
            run.adopted[identifier] = external
            run.activities[identifier] = replace(
                run.activities[identifier],
                step=external.step or "external run",
            )
            run.log.record(
                message=f"{identifier} adopted from a running external run",
            )
            return
        run.log.record(message=f"{identifier} started")
        cls._reset_progress(tool=tool)
        if run.orchestrator is None:
            msg: str = "pipeline worker orchestration is not configured"
            raise RuntimeError(msg)
        request: ToolRequest = cls._pipeline_request(
            run=run,
            tool=tool,
            arguments=arguments,
        )
        run.handles[identifier] = run.orchestrator.context(
            name=run.context,
        ).create(
            process=identifier,
            arguments=worker_arguments(request=request, spec=tool),
        )

    @classmethod
    def _external_tools(cls, *, run: _PipelineRun) -> dict[str, RunRecord]:
        """Return live member-tool runs this pipeline does not own.

        Args:
            run: Mutable pipeline bookkeeping record.

        Returns:
            Live external runs keyed by member tool identifier.

        """
        registry: RunRegistry = RunRegistry(
            path=cls.exactus_root / ".runtime" / "runs.db",
        )
        found: dict[str, RunRecord] = {}
        record: RunRecord
        for record in registry.live():
            if (
                record.kind == "tool"
                and record.identifier in run.groups
                and (record.pipeline_run_id != run.run_id)
            ):
                found[record.identifier] = record
        return found

    @classmethod
    def _pause_ahead_tools(cls, *, run: _PipelineRun) -> None:
        """Suspend external member runs gated by unresolved dependencies.

        A standalone run started before the pipeline still owns its
        claim; pausing — not killing — it lets the pipeline adopt and
        release the same run when the wave arrives.

        Args:
            run: Mutable pipeline bookkeeping record.

        """
        external: dict[str, RunRecord] = cls._external_tools(run=run)
        run.external.update(external)
        descriptors: dict[str, Descriptor] = external_descriptors(
            records=external,
            descriptors=Discovery.all(),
            root=cls.root,
        )
        for identifier, record in external.items():
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=identifier,
            )
            dependencies: frozenset[str] = (
                frozenset(tool.dependencies) & frozenset(run.order)
                if tool is not None
                else frozenset()
            )
            if not dependencies or (
                tool is not None and tool.streaming_dependencies
            ):
                continue
            descriptor: Descriptor | None = descriptors.get(identifier)
            paused_worker: bool = descriptor is not None and pause_worker(
                descriptor=descriptor,
                owner=run.run_id,
            )
            pause_tree(
                pid=record.pid,
                exclude=(descriptor.pid,)
                if descriptor is not None and paused_worker
                else (),
            )
            run.paused[identifier] = record.pid
            cls._publish_external_lifecycle(
                identifier=identifier,
                run_id=record.run_id,
                state="PAUSED",
                detail="waiting for " + ", ".join(sorted(dependencies)),
            )
            run.log.record(
                message=f"{identifier} paused for dependencies "
                + ", ".join(sorted(dependencies)),
            )

    @classmethod
    def _release_group(cls, *, run: _PipelineRun, group: int) -> None:
        """Resume external runs paused until this wave's group.

        Args:
            run: Mutable pipeline bookkeeping record.
            group: One-based wave group about to execute.

        """
        for identifier, pid in tuple(run.paused.items()):
            if run.groups[identifier] > group:
                continue
            record: RunRecord | None = run.external.get(identifier)
            released: bool = True
            if record is not None:
                descriptor: Descriptor | None = Discovery.find(
                    name=identifier,
                    context=tool_context(
                        root=cls.root,
                        owner=record.pipeline_run_id or record.run_id,
                    ),
                )
                if descriptor is not None:
                    released = resume_worker(
                        descriptor=descriptor,
                        owner=run.run_id,
                    )
            if not released:
                continue
            resume_tree(pid=pid)
            if record is not None:
                cls._publish_external_lifecycle(
                    identifier=identifier,
                    run_id=record.run_id,
                    state="RUNNING",
                    detail=f"resumed for pipeline group {group}",
                )
            del run.paused[identifier]
            run.log.record(message=f"{identifier} resumed for group {group}")

    @classmethod
    def _release_paused(cls, *, run: _PipelineRun | None) -> None:
        """Resume every external run still suspended by the pipeline.

        Args:
            run: Mutable pipeline bookkeeping record, when created.

        """
        if run is None:
            return
        for identifier, pid in run.paused.items():
            record: RunRecord | None = run.external.get(identifier)
            released: bool = True
            if record is not None:
                descriptor: Descriptor | None = Discovery.find(
                    name=identifier,
                    context=tool_context(
                        root=cls.root,
                        owner=record.pipeline_run_id or record.run_id,
                    ),
                )
                if descriptor is not None:
                    released = resume_worker(
                        descriptor=descriptor,
                        owner=run.run_id,
                    )
            if released:
                resume_tree(pid=pid)
                if record is not None:
                    cls._publish_external_lifecycle(
                        identifier=identifier,
                        run_id=record.run_id,
                        state="RUNNING",
                        detail="released by pipeline",
                    )
        run.paused.clear()

    @classmethod
    def _drain_adopted(
        cls,
        *,
        run: _PipelineRun,
        external: dict[str, RunRecord],
        results: dict[str, ToolRunResult],
        descriptors: tuple[Descriptor, ...] = (),
    ) -> None:
        """Refresh or complete the wave's adopted external runs.

        Args:
            run: Mutable pipeline bookkeeping record.
            external: Freshly scanned live external runs.
            results: Accumulated pipeline results to extend.
            descriptors: Shared pmanager discovery snapshot.

        """
        for identifier in tuple(run.adopted):
            refresh: RunRecord | None = external.get(identifier)
            if refresh is not None:
                if refresh.run_id != run.adopted[identifier].run_id:
                    run.adopted[identifier] = refresh
                    _ = run.fractions.pop(identifier, None)
                    run.log.record(
                        message=(
                            f"{identifier} superseded by a newer external run"
                        ),
                    )
                fraction: float = refresh.progress
                tool: ToolSpec | None = (
                    _GroupFinalConstants.exactus_catalog.tool(
                        identifier=identifier,
                    )
                )
                issues: int = 0
                hierarchy: dict[str, JsonValue] | None
                if tool is not None:
                    fraction, _, issues, hierarchy = cls._read_progress(
                        tool=tool,
                        run_id=refresh.run_id,
                    )
                else:
                    hierarchy = None
                fraction = max(fraction, run.fractions.get(identifier, 0.0))
                run.fractions[identifier] = fraction
                run.activities[identifier] = replace(
                    run.activities[identifier],
                    progress=round(number=fraction, ndigits=3),
                    step=refresh.step or "running",
                    issues=issues,
                    hierarchy=hierarchy,
                    elapsed_seconds=round(
                        number=monotonic()
                        - run.tool_started.get(identifier, monotonic()),
                        ndigits=3,
                    ),
                )
                continue
            adopted: RunRecord = run.adopted[identifier]
            process_status: ProcessStatus | None = live_status(
                descriptors=descriptors,
                name=identifier,
                context=tool_context(
                    root=cls.root,
                    owner=adopted.pipeline_run_id or adopted.run_id,
                ),
            )
            if process_status is not None and (not process_status.terminal):
                lifecycle: str = process_status.state.value
                custom_status: JsonValue = process_status.custom_status
                if isinstance(custom_status, dict):
                    custom_step: JsonValue = custom_status.get("step")
                    if isinstance(custom_step, str) and custom_step:
                        lifecycle = custom_step
                run.activities[identifier] = replace(
                    run.activities[identifier],
                    step=lifecycle,
                )
                continue
            del run.adopted[identifier]
            result: ToolRunResult = cls._adopted_result(
                run=run,
                identifier=identifier,
            )
            results[identifier] = result
            run.log.record(
                level="info" if result.passed else "warning",
                message=(
                    f"{identifier} finished: {result.status} in "
                    f"{result.duration_seconds:.3f}s (external run)"
                ),
            )
            if not result.passed:
                run.fail_marks[identifier] = run.fractions.get(identifier, 0.0)
            run.fractions[identifier] = 1.0
            run.activities[identifier] = replace(
                run.activities[identifier],
                status=result.status,
                report_updated=True,
                progress=1.0,
                step="complete",
                finished_at=datetime.now(tz=UTC).astimezone().isoformat(),
                elapsed_seconds=round(
                    number=result.duration_seconds,
                    ndigits=3,
                ),
            )

    @classmethod
    def _adopted_result(
        cls,
        *,
        run: _PipelineRun,
        identifier: str,
    ) -> ToolRunResult:
        """Build the pipeline result for a finished external run.

        Args:
            run: Mutable pipeline bookkeeping record.
            identifier: Canonical tool identifier.

        Returns:
            The external run's report reconciled as this wave's result,
            or a failure when it produced none.

        """
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=identifier,
        )
        output: Path = (
            cls.exactus_root / tool.output
            if tool is not None
            else cls.exactus_root
        )
        return ExactusApi.reconcile(
            result=ToolRunResult(
                tool=identifier,
                run_id=f"{run.run_id}:{identifier}",
                pipeline_run_id=run.run_id,
                status="FAIL",
                passed=False,
                exit_code=1,
                duration_seconds=0.0,
                resume="the external run produced no report",
                report=output / "result.md",
                report_json=output / "result.json",
                report_web=output / "result_web" / "index.html",
            ),
        )

    @classmethod
    def _await_reruns(cls, *, run: _PipelineRun) -> None:
        """Wait for same-tool reruns launched while the pipeline ran.

        A standalone ``exactus --tool`` invoked during a pipeline claims
        the tool's report directory and replaces the pipeline-owned
        worker. Before results are reconciled, every such rerun must
        finish so the pipeline reports the newest run rather than the
        replaced one.  Finished reruns surface as ``*`` rows through
        ``_refresh_activity`` and drop out of the waiting list.

        Args:
            run: Mutable pipeline bookkeeping record.

        """
        announced: tuple[str, ...] = ()
        while not cls._interrupt.is_set():
            external: dict[str, RunRecord] = cls._external_tools(run=run)
            run.external.clear()
            run.external.update(external)
            pending: tuple[str, ...] = tuple(
                identifier
                for identifier in run.order
                if identifier in external
            )
            if not pending:
                for identifier in announced:
                    run.fractions[identifier] = 1.0
                return
            for identifier in pending:
                record: RunRecord = external[identifier]
                tool: ToolSpec | None = (
                    _GroupFinalConstants.exactus_catalog.tool(
                        identifier=identifier,
                    )
                )
                fraction: float = record.progress
                issues: int = 0
                hierarchy: dict[str, JsonValue] | None = None
                if tool is not None:
                    fraction, _, issues, hierarchy = cls._read_progress(
                        tool=tool,
                        run_id=record.run_id,
                    )
                run.fractions[identifier] = fraction
                run.activities[identifier] = replace(
                    run.activities[identifier],
                    run_id=record.run_id,
                    status="RUNNING",
                    progress=fraction,
                    step=record.step or "external rerun",
                    finished_at=None,
                    report_updated=True,
                    issues=issues,
                    hierarchy=hierarchy,
                )
            if pending != announced:
                announced = pending
                run.log.record(
                    message=f"waiting for {', '.join(pending)} to complete",
                )
            cls._touch_pipeline(pipeline=run.pipeline, run_id=run.run_id)
            cls._publish_activity(
                run=run,
                current_group=None,
                status="RUNNING",
            )
            cls._progress_lines = ExactusTerminal.progress(
                title=f"exactus · {run.pipeline}",
                global_fraction=cls._global_fraction(run=run),
                stage=f"waiting for {', '.join(pending)} to complete",
                tools=cls._progress_rows(run=run),
                previous_lines=cls._progress_lines,
            )
            sleep(cls.poll_seconds)

    @classmethod
    def _interrupt_result(
        cls,
        *,
        run: _PipelineRun,
        identifier: str,
        results: dict[str, ToolRunResult],
    ) -> None:
        """Record a synthesized ``INTERRUPT`` result for an unrun tool.

        Args:
            run: Mutable pipeline bookkeeping record.
            identifier: Canonical tool identifier never started.
            results: Accumulated pipeline results to extend.

        """
        tool_spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=identifier,
        )
        tool_output: Path = (
            cls.exactus_root / tool_spec.output
            if tool_spec is not None
            else cls.exactus_root
        )
        run.fail_marks[identifier] = run.fractions.get(identifier, 0.0)
        results[identifier] = ToolRunResult(
            tool=identifier,
            run_id=f"{run.run_id}:{identifier}",
            pipeline_run_id=run.run_id,
            status="INTERRUPT",
            passed=False,
            exit_code=130,
            duration_seconds=0.0,
            resume="interrupted by user before start",
            report=tool_output / "result.md",
            report_json=tool_output / "result.json",
            report_web=tool_output / "result_web" / "index.html",
        )
        run.log.record(
            level="warning",
            message=f"{identifier} not run: the pipeline was interrupted",
        )
        run.activities[identifier] = replace(
            run.activities[identifier],
            status="INTERRUPT",
            step="interrupted",
            finished_at=datetime.now(tz=UTC).astimezone().isoformat(),
        )

    @classmethod
    def _merged_arguments(
        cls,
        *,
        pipeline: PipelineSpec,
        waves: tuple[tuple[ToolSpec, ...], ...],
        tool_arguments: dict[str, tuple[str, ...]],
        common: tuple[str, ...],
    ) -> dict[str, tuple[str, ...]]:
        """Order each tool's arguments: preset, config, then the CLI.

        Args:
            pipeline: Pipeline being run.
            waves: Dependency waves that survived exclusions.
            tool_arguments: Per-tool ``--tool-arg`` values.
            common: Flat ``--include``/``--exclude`` flag pairs.

        Returns:
            The final argument tuple per tool identifier.

        """
        merged: dict[str, tuple[str, ...]] = {
            identifier: tuple(arguments)
            for identifier, arguments in pipeline.tool_arguments.items()
        }
        for wave in waves:
            for tool in wave:
                merged[tool.identifier] = (
                    *merged.get(tool.identifier, ()),
                    *cls._config_arguments(
                        tool=tool,
                        pipeline=pipeline.identifier,
                    ),
                )
        for identifier, arguments in tool_arguments.items():
            merged[identifier] = (*merged.get(identifier, ()), *arguments)
        for wave in waves:
            for tool in wave:
                merged[tool.identifier] = (
                    *cls._common_args(tool=tool, common=common),
                    *cls._collect_flags(tool=tool),
                    *merged.get(tool.identifier, ()),
                )
        return merged

    @classmethod
    def _prepare_pipeline(
        cls,
        *,
        pipeline: PipelineSpec,
        common: tuple[str, ...],
        run_id: str,
    ) -> tuple[str, Path]:
        """Optionally clear the pipeline report and claim its workspace.

        Args:
            pipeline: Resolved pipeline specification.
            common: Flat ``--include``/``--exclude`` flag pairs forwarded
                to every wave tool that accepts them.
            run_id: Already-claimed owner pipeline identity.

        Returns:
            The claimed run identifier and workspace path.

        """
        capture_reports(output=cls.exactus_root)
        if pipeline.clear:
            cls._clear(names=(pipeline.identifier,))
        cls._enter_root()
        sprint(f"files · {cls._file_census(common=common)}", file=stdout)
        output: Path = cls._pipeline_workspace(
            pipeline=pipeline.identifier,
            run_id=run_id,
        )
        cls._publish_pipeline_owner(
            pipeline=pipeline.identifier,
            run_id=run_id,
        )
        return (run_id, output)

    @classmethod
    def _publish_pipeline_owner(cls, *, pipeline: str, run_id: str) -> None:
        """Write the pipeline ownership record into a prepared workspace.

        Args:
            pipeline: Canonical pipeline identifier.
            run_id: Owned pipeline run identifier.

        """
        own_tty: str | None = ExactusTerminal.tty_name()
        write_json(
            path=cls._owner_path(pipeline=pipeline),
            payload=RunDocument(
                kind="pipeline",
                name=pipeline,
                status="RUNNING",
                run_id=run_id,
                pid=getpid(),
                started_at=datetime.now(tz=UTC).astimezone().isoformat(),
                extra={"tty": own_tty, "accepting": True},
            ).payload(),
        )

    @classmethod
    def _pipeline_plan(
        cls,
        *,
        name: str,
        tool_arguments: dict[str, tuple[str, ...]],
        exclude: frozenset[str],
        common: tuple[str, ...],
    ) -> tuple[
        PipelineSpec,
        tuple[tuple[ToolSpec, ...], ...],
        dict[str, tuple[str, ...]],
    ]:
        """Resolve one executable pipeline, its tools, and their arguments.

        Args:
            name: Pipeline identifier or alias.
            tool_arguments: Per-tool command-line arguments.
            exclude: Tool identifiers removed from the pipeline.
            common: Common include and exclude arguments.

        Returns:
            Pipeline, filtered dependency waves, and merged tool arguments.

        Raises:
            ValueError: If the pipeline is unknown or exclusions remove all
                tools.

        """
        pipeline: PipelineSpec | None = (
            _GroupFinalConstants.exactus_catalog.pipeline(identifier=name)
        )
        if pipeline is None:
            msg: str = f"unknown exactus pipeline: {name}"
            raise ValueError(msg)
        waves: tuple[tuple[ToolSpec, ...], ...] = tuple(
            kept
            for kept in (
                tuple(tool for tool in wave if tool.identifier not in exclude)
                for wave in _GroupFinalConstants.exactus_catalog.waves(
                    identifier=pipeline.identifier,
                )
            )
            if kept
        )
        if exclude and (not waves):
            msg = (
                f"--exclude-tools removed every tool from "
                f"pipeline: {pipeline.identifier}"
            )
            raise ValueError(msg)
        configured: dict[str, tuple[str, ...]] = cls._merged_arguments(
            pipeline=pipeline,
            waves=waves,
            tool_arguments=tool_arguments,
            common=common,
        )
        waves = tuple(
            kept
            for kept in (
                tuple(
                    tool
                    for tool in wave
                    if tool.identifier not in _GroupFinalConstants.url_gated
                    or any(
                        argument
                        in {
                            "--url",
                            "--workspace",
                            "--actions",
                            "--html",
                            "--target",
                        }
                        or argument.startswith(
                            (
                                "--url=",
                                "--workspace=",
                                "--actions=",
                                "--html=",
                                "--target=",
                            ),
                        )
                        for argument in configured.get(tool.identifier, ())
                    )
                )
                for wave in waves
            )
            if kept
        )
        return (
            pipeline,
            waves,
            cls._merged_arguments(
                pipeline=pipeline,
                waves=waves,
                tool_arguments=tool_arguments,
                common=common,
            ),
        )

    @classmethod
    def _force_remove(
        cls: type[Self],
        func: Callable[[str], None],
        path: str,
        exc_info: BaseException,
    ) -> None:
        """Retry a failed ``rmtree`` operation after restoring write bits.

        Read-only files or directories extracted from guest images make the
        default delete fail with ``PermissionError``; restoring the owner
        write/execute bits on the entry and its parent lets it proceed. A
        directory recreated or repopulated by a racing writer instead fails
        ``rmdir`` with ``ENOTEMPTY``; only a fresh tree walk removes those
        late entries.

        Args:
            func: The ``rmtree`` worker to retry (``unlink``/``rmdir``).
            path: Filesystem path that failed.
            exc_info: The exception raised by ``func``.

        """
        entry: Path = Path(path)
        if isinstance(exc_info, OSError) and exc_info.errno == ENOTEMPTY:
            rmtree(path=entry, onexc=cls._force_remove)
            return
        entry.chmod(mode=entry.stat().st_mode | 448)
        parent: Path = entry.parent
        parent.chmod(mode=parent.stat().st_mode | 448)
        func(path)

    @classmethod
    def _remove(cls, *, path: Path) -> None:
        """Delete one path whether it is a file, symlink or directory.

        Args:
            path: Filesystem path to remove when present.

        """
        if ".history" in path.parts:
            return
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            rmtree(path=path, onexc=cls._force_remove)

    @classmethod
    def _clear_target(cls, *, name: str) -> Path | None:
        """Resolve one ``--clear`` operand to an EXACTUS_RESULTS directory.

        Args:
            name: Catalog tool/pipeline id, alias, or EXACTUS_RESULTS
                folder name.

        Returns:
            The resulting value, or ``None`` when the name is invalid.

        """
        tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
            identifier=name,
        )
        if tool is not None:
            return cls.exactus_root / tool.output
        pipeline: PipelineSpec | None = (
            _GroupFinalConstants.exactus_catalog.pipeline(identifier=name)
        )
        if pipeline is not None:
            return cls._pipeline_output(pipeline=pipeline.identifier)
        normalized: str = name.strip().upper().replace("-", "_")
        candidate: Path = cls.exactus_root / normalized
        if (
            normalized
            and (not normalized.startswith("."))
            and (Path(normalized).name == normalized)
            and candidate.is_dir()
        ):
            return candidate
        return None

    @classmethod
    def _debug_output_dir(cls) -> Path:
        """Resolve the sprint capture folder declared by ``DEBUG.txt``.

        Mirrors the ``save`` resolution in ``sprint``
        but returns the containing directory rather than the record file.

        Returns:
            Directory receiving sprint capture records.

        """
        target: Path = cls.root / cls.debug_dir / cls.debug_file
        marker: Path = cls.root / cls.debug_marker
        if marker.is_file():
            raw: str
            for raw in marker.read_text(encoding="utf-8").splitlines():
                name: str
                separator: str
                value: str
                name, separator, value = raw.strip().partition("::")
                if name == "save" and separator:
                    target = Path(value.strip())
                    if not target.is_absolute():
                        target = cls.root / target
                    if not target.suffix:
                        target = target / cls.debug_file
        return target.parent

    @classmethod
    def _clear_debug_output(cls) -> None:
        """Empty the sprint capture folder declared by ``DEBUG.txt``.

        Refuses to empty the project root, the filesystem root, or the
        user home directory even when a ``save`` directive names them.

        """
        if not (cls.root / cls.debug_marker).is_file():
            return
        folder: Path = cls._debug_output_dir()
        resolved: Path = folder.resolve()
        if resolved in {cls.root, Path(resolved.anchor), Path.home()}:
            sprint(f"refusing to empty {resolved}", file=stdout)
            return
        if not folder.is_dir():
            sprint(f"{resolved} does not exist; nothing to clear", file=stdout)
            return
        removed: int = 0
        child: Path
        for child in folder.iterdir():
            cls._remove(path=child)
            removed += 1
        sprint(f"emptied {resolved} ({removed} entries)", file=stdout)

    @classmethod
    def _clear_all(cls) -> None:
        """Clear generated output while preserving coordination state."""
        if not cls.exactus_root.is_dir():
            return
        child: Path
        for child in cls.exactus_root.iterdir():
            if child.name not in {".history", ".runtime"}:
                cls._remove(path=child)
        sprint(f"cleared {cls.exactus_root}", file=stdout)

    @classmethod
    def _clear(cls, *, names: tuple[str, ...]) -> None:
        """Remove the EXACTUS_RESULTS tree or selected tool/pipeline outputs.

        Also empties the sprint capture folder declared by ``DEBUG.txt``.

        Args:
            names: ``--clear`` operands; an empty tuple removes everything.

        Raises:
            ValueError: If an operand names no tool, pipeline or
                EXACTUS_RESULTS directory.

        """
        capture_reports(output=cls.exactus_root)
        if not names:
            cls._clear_all()
            cls._clear_debug_output()
            return
        targets: list[Path] = []
        for name in names:
            target: Path | None = cls._clear_target(name=name)
            if target is None:
                msg: str = (
                    f"--clear requires a tool, pipeline or "
                    f"EXACTUS_RESULTS folder, got: {name}"
                )
                raise ValueError(msg)
            if target not in targets:
                targets.append(target)
        removed: list[Path] = []
        for target in targets:
            _ = cls._terminate_run_tools(output=target)
            if target.is_symlink() or target.exists():
                cls._remove(path=target)
                removed.append(target)
        if removed:
            sprint(
                "".join(f"cleared {path}\n" for path in removed),
                end="",
                file=stdout,
            )
        cls._clear_debug_output()

    @classmethod
    def _run_named_pipeline(
        cls,
        *,
        parser: ArgumentParser,
        name: str,
        args: Namespace,
        exclude: frozenset[str],
        common: tuple[str, ...],
    ) -> bool:
        """Run one pipeline, turning invalid input into a usage error.

        Args:
            parser: Argument parser used for ``parser.error`` exits.
            name: Pipeline identifier or alias.
            args: Parsed namespace holding ``tool_arg``.
            exclude: Canonical tools skipped by the run.
            common: Flat ``--include``/``--exclude`` flag pairs.

        Returns:
            Whether every pipeline tool passed.

        """
        try:
            return cls.run_pipeline(
                name=name,
                tool_arguments=cls._pipeline_arguments(
                    values=cast(typ="list[str]", val=args.tool_arg),
                ),
                exclude=exclude,
                common=common,
            )
        except ValueError as exc:
            parser.error(message=str(object=exc))

    @classmethod
    def _parsed_tool_arguments(
        cls,
        *,
        parser: ArgumentParser,
        args: Namespace,
    ) -> dict[str, tuple[str, ...]]:
        """Parse ``--tool-arg`` values, exiting with a usage error.

        Args:
            parser: Argument parser used for ``parser.error`` exits.
            args: Parsed namespace holding ``tool_arg``.

        Returns:
            Per-tool forwarded arguments keyed by canonical tool id.

        """
        try:
            return cls._pipeline_arguments(
                values=cast(typ="list[str]", val=args.tool_arg),
            )
        except ValueError as exc:
            parser.error(message=str(object=exc))

    @classmethod
    def _prepare_config(
        cls,
        *,
        parser: ArgumentParser,
        args: Namespace,
    ) -> None:
        """Apply ``--config``/``--no-config`` and load ``[tool.exactus]``.

        Args:
            parser: Parser used for ``parser.error`` exits.
            args: Parsed orchestrator namespace.

        """
        _apply_config_flags(
            config=cast(typ="str | None", val=args.config),
            disabled=cast(typ="bool", val=args.no_config),
        )
        try:
            cls.load_config(force=True)
        except ConfigError as exc:
            parser.error(message=str(object=exc))

    @classmethod
    def _collect_files_enabled(cls) -> bool:
        """Return whether finding files are bundled into each report.

        ``--collect-files`` on the orchestrator command line wins;
        otherwise the common ``collect-files`` key of the loaded
        ``[tool.exactus]`` tables decides.

        Returns:
            ``True`` when each report gains a ``FILES`` folder.

        """
        if cls.collect_files:
            return True
        cls.load_config()
        return (
            stacked(files=cls.config_files, path=()).get("collect-files")
            is True
        )

    @classmethod
    def _collect_flags(cls, *, tool: ToolSpec) -> tuple[str, ...]:
        """Return ``--collect-files`` when enabled and the tool accepts it.

        Args:
            tool: Catalog tool receiving the arguments.

        Returns:
            The flag when collection is enabled and the tool's parser
            owns it, else nothing.

        """
        if not cls._collect_files_enabled():
            return ()
        parser: ArgumentParser = tool_parser(module=tool.module)
        actions: Sequence[Action] = cast(
            typ="Sequence[Action]",
            val=getattr(parser, "_actions", ()),
        )
        options: frozenset[str] = frozenset(
            option for action in actions for option in action.option_strings
        )
        if CollectFilesTables.flag not in options:
            return ()
        return (CollectFilesTables.flag,)

    @classmethod
    def _common_args(
        cls,
        *,
        tool: ToolSpec,
        common: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Filter global ``--include``/``--exclude`` flags for a tool.

        Args:
            tool: Catalog tool receiving the arguments.
            common: Flat ``(flag, value, ...)`` global argument pairs.

        Returns:
            The pairs whose flag the tool's parser accepts.

        """
        cls.load_config()
        seen: set[tuple[str, str]] = set(
            zip(common[::2], common[1::2], strict=True),
        )
        merged: list[str] = list(common)
        values: dict[str, JsonValue] = stacked(files=cls.config_files, path=())
        for flag, key in (("--include", "include"), ("--exclude", "exclude")):
            configured: JsonValue | None = values.get(key)
            globs: tuple[str, ...] = (
                (configured,)
                if isinstance(configured, str)
                else tuple(
                    str(object=item)
                    for item in configured
                    if isinstance(item, str)
                )
                if isinstance(configured, list)
                else ()
            )
            for glob in globs:
                if (flag, glob) not in seen:
                    seen.add((flag, glob))
                    merged.extend((flag, glob))
        common = tuple(merged)
        reports_root: str | None = environ.get("EXACTUS_REPORTS_ROOT")
        project_root: str | None = environ.get("EXACTUS_ROOT")
        if (
            reports_root
            and project_root
            and Path(reports_root).is_relative_to(Path(project_root))
        ):
            base: Path = Path(reports_root).relative_to(Path(project_root))
            if base != Path("EXACTUS_RESULTS"):
                common = (
                    *common,
                    "--exclude",
                    base.as_posix(),
                    "--exclude",
                    f"{base.as_posix()}/**",
                )
        if not common:
            return ()
        parser: ArgumentParser = tool_parser(module=tool.module)
        actions: Sequence[Action] = cast(
            typ="Sequence[Action]",
            val=getattr(parser, "_actions", ()),
        )
        options: frozenset[str] = frozenset(
            option for action in actions for option in action.option_strings
        )
        return tuple(
            (
                argument
                for flag, value in zip(common[::2], common[1::2], strict=True)
                if flag in options
                for argument in (flag, value)
            ),
        )

    @classmethod
    def _pipeline_orchestrator(
        cls,
        *,
        tools: tuple[ToolSpec, ...],
    ) -> Orchestrator:
        """Build the detached-worker orchestrator for one pipeline.

        Args:
            tools: Participating catalog tools.

        Returns:
            Configured process orchestrator.

        """
        ensure_worker_path()
        return Orchestrator.from_object_spec(
            specification=build_spec(tools=tools, root=cls.root),
        )

    @staticmethod
    def _exactus_processes() -> set[int]:
        """Return pids of live processes that still look like Exactus.

        A candidate qualifies when its executable lives in the bundled
        ``exactus-tools`` payload or is Exactus-named, or when it runs
        under an interpreter and references an Exactus module, script or
        command token; paths that merely live inside an ``exactus``-named
        directory do not qualify, which keeps unrelated editors and test
        runs safe.

        Returns:
            Live process identifiers matching the Exactus heuristic.

        """
        matches: set[int] = set()
        for process in process_iter():
            try:
                name: str = process.name().lower()
                tokens: list[str] = [arg.lower() for arg in process.cmdline()]
            except (OSError, Error):
                continue
            executable: str = ""
            with suppress(OSError, Error):
                executable = process.exe().lower().replace("\\", "/")
            if "exactus-tools" in executable or executable.rsplit(
                sep="/",
                maxsplit=1,
            )[-1].startswith("exactus"):
                matches.add(process.pid)
                continue
            if "python" not in name and "exactus" not in name:
                continue
            for arg in tokens:
                stem: str = arg.replace("\\", "/").rsplit(sep="/", maxsplit=1)[
                    -1
                ]
                if (
                    arg == "exactus"
                    or arg.startswith("exactus.")
                    or stem.startswith("exactus")
                ) and (not Path(arg).is_dir()):
                    matches.add(process.pid)
                    break
        return matches

    @staticmethod
    def _metadata(
        *,
        result: ToolRunResult,
        output: Path,
    ) -> dict[str, JsonValue]:
        """Convert one shared result model to aggregate-report metadata.

        Args:
            result: Completed tool run result.
            output: Directory the aggregate report is written to.

        Returns:
            The resulting value; ``report_web_href`` links the tool's web
            report from the aggregate's ``result_web/index.html``.

        """
        return {
            "tool": result.tool,
            "run_id": result.run_id,
            "pipeline_run_id": result.pipeline_run_id,
            "report_replaced_after_execution": result.replaced_after_execution,
            "status": result.status,
            "passed": result.passed,
            "duration_seconds": round(
                number=result.duration_seconds,
                ndigits=3,
            ),
            "resume": result.resume,
            "report": str(object=result.report),
            "report_json": str(object=result.report_json),
            "report_web": str(object=result.report_web),
            "report_web_href": Path(
                relpath(
                    path=result.report_web.resolve(),
                    start=(output / "result_web").resolve(),
                ),
            ).as_posix(),
        }

    @staticmethod
    def _resume_line(*, result: ToolRunResult, output: Path) -> str:
        """Render one tool resume with report links relative to the report.

        Args:
            result: Completed tool run result.
            output: Directory the aggregate Markdown report is written to.

        Returns:
            One bullet line linking the tool's report bundle.

        """
        markdown: str = Path(
            relpath(path=result.report, start=output),
        ).as_posix()
        json_href: str = Path(
            relpath(path=result.report_json, start=output),
        ).as_posix()
        web: str = Path(
            relpath(path=result.report_web, start=output),
        ).as_posix()
        return (
            f"- `{result.tool}`: **{result.status}** "
            f"({result.duration_seconds:.3f}s) — {result.resume} "
            f"[markdown]({markdown}) · [json]({json_href}) · [web]({web})"
        )

    @staticmethod
    def _refresh_unified_activity(
        *,
        path: Path,
        results: tuple[ToolRunResult, ...],
        reports: dict[str, dict[str, JsonValue]],
    ) -> None:
        """Rewrite the stored UNIFIED activity file from current reports.

        Args:
            path: ``@activity.json`` of the unified run.
            results: Rebuilt per-tool results in pipeline order.
            reports: Latest decoded ``result.json`` per tool.

        """
        payload: dict[str, JsonValue] | None = read_json(path=path)
        if payload is None:
            return
        entries: JsonValue = payload.get("items")
        if not isinstance(entries, list):
            return
        latest: dict[str, ToolRunResult] = {
            result.tool: result for result in results
        }
        changed: bool = False
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                (name := entry.get("name")),
                str,
            ):
                continue
            result: ToolRunResult | None = latest.get(name)
            fields: dict[str, JsonValue] | None = reports.get(name)
            if result is None or fields is None:
                continue
            generated_at: JsonValue = fields.get("generated_at")
            updates: dict[str, JsonValue] = {
                "status": result.status,
                "progress": 1.0,
                "step": "complete",
                "run_id": result.run_id,
                "elapsed_seconds": round(
                    number=result.duration_seconds,
                    ndigits=3,
                ),
            }
            if isinstance(generated_at, str):
                updates["finished_at"] = generated_at
            if not all(
                (entry.get(key) == value for key, value in updates.items()),
            ):
                entry.update(updates)
                changed = True
        if not changed:
            return
        statuses: tuple[JsonValue, ...] = tuple(
            entry.get("status") for entry in entries if isinstance(entry, dict)
        )
        if payload.get("status") in ("DONE", "FAIL") and statuses:
            progress: JsonValue = payload.get("progress")
            payload |= {
                "status": "DONE"
                if all(status == "PASS" for status in statuses)
                else "FAIL",
                "progress": {
                    **(progress if isinstance(progress, dict) else {}),
                    "fraction": 1.0,
                    "percent": 100.0,
                },
            }
        payload["updated_at"] = datetime.now(tz=UTC).astimezone().isoformat()
        ActivityFile.write_json(path=path, payload=payload)

    @staticmethod
    def _report_fields(*, path: Path) -> dict[str, JsonValue] | None:
        """Read one tool report's fields when it carries a usable status.

        Args:
            path: The tool's latest ``result.json`` report.

        Returns:
            The decoded report fields, or ``None`` when the report is
            missing, malformed, or carries no string ``status``.

        """
        try:
            payload: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (OSError, JSONDecodeError):
            return None
        fields: dict[str, JsonValue] = (
            payload if isinstance(payload, dict) else {}
        )
        return fields if isinstance(fields.get("status"), str) else None

    @staticmethod
    def _tool_depends_on(*, identifier: str, dependency: str) -> bool:
        """Return whether one catalog tool transitively needs another.

        Args:
            identifier: Candidate dependent tool.
            dependency: Candidate prerequisite tool.

        Returns:
            Whether the dependency must settle first.

        """
        pending: list[str] = [identifier]
        visited: set[str] = set()
        while pending:
            current: str = pending.pop()
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=current,
            )
            if tool is None:
                continue
            for prerequisite in tool.dependencies:
                if prerequisite == dependency:
                    return True
                if prerequisite not in visited:
                    visited.add(prerequisite)
                    pending.append(prerequisite)
        return False

    @staticmethod
    def _release_superseded_worker(
        *,
        run: _PipelineRun,
        identifier: str,
        descriptors: tuple[Descriptor, ...],
    ) -> None:
        """Stop a detached pipeline worker superseded by an external run.

        Args:
            run: Active pipeline state.
            identifier: Tool whose output was claimed externally.
            descriptors: Shared pmanager discovery snapshot.

        """
        if run.handles.pop(identifier, None) is None:
            return
        owned: Descriptor | None = next(
            (
                descriptor
                for descriptor in descriptors
                if descriptor.name == identifier
                and descriptor.context == run.context
            ),
            None,
        )
        if owned is not None:
            with suppress(OSError, RuntimeError):
                _ = Client.request(descriptor=owned, command="kill")
            terminate_tree(pid=owned.pid, replaced=True)
        run.log.record(
            message=(
                f"{identifier} released its superseded pipeline worker "
                f"before external adoption"
            ),
        )

    @staticmethod
    def _settle_tool(*, run: _PipelineRun, result: ToolRunResult) -> None:
        """Record one owned or dependency-blocked terminal result.

        Args:
            run: Pipeline bookkeeping record.
            result: Terminal tool result.

        """
        identifier: str = result.tool
        run.log.record(
            level="info" if result.passed else "warning",
            message=(
                f"{identifier} finished: {result.status} in "
                f"{result.duration_seconds:.3f}s"
            ),
        )
        if not result.passed:
            run.fail_marks[identifier] = run.fractions.get(identifier, 0.0)
        run.fractions[identifier] = 1.0
        run.activities[identifier] = replace(
            run.activities[identifier],
            status=result.status,
            progress=1.0,
            step="complete",
            issues=0,
            finished_at=datetime.now(tz=UTC).astimezone().isoformat(),
            elapsed_seconds=round(number=result.duration_seconds, ndigits=3),
        )

    @staticmethod
    def _progress_rows(
        *,
        run: _PipelineRun,
    ) -> tuple[tuple[str, str, float, str, float | None], ...]:
        """Return ``(tool, status, fraction, detail, mark)`` rows.

        Args:
            run: Mutable pipeline bookkeeping record.

        Returns:
            Display rows for every tool in the run, in report order.
            ``mark`` is the fraction where the tool failed, or ``None``
            when it has not failed.

        """
        rows: list[tuple[str, str, float, str, float | None]] = []
        for identifier in run.order:
            activity: ToolActivity = run.activities[identifier]
            mark: float | None = run.fail_marks.get(identifier)
            external: RunRecord | None = run.external.get(identifier)
            if external is not None:
                rows.append(
                    (
                        identifier,
                        "PAUSED*"
                        if identifier in run.paused
                        else "RUNNING!*"
                        if activity.issues
                        else "RUNNING*",
                        external.progress,
                        "waiting for dependencies"
                        if identifier in run.paused
                        else external.step or "external run",
                        mark,
                    ),
                )
                continue
            detail: str = (
                activity.step
                if activity.status == "RUNNING"
                else "waiting"
                if activity.status == "WAITING"
                else f"{activity.status.lower()} "
                f"{activity.elapsed_seconds:.3f}s"
            )
            rows.append(
                (
                    identifier,
                    activity.status
                    + (
                        "!"
                        if activity.issues and activity.status == "RUNNING"
                        else ""
                    )
                    + (
                        "*"
                        if activity.report_updated
                        and activity.status in {"PASS", "FAIL"}
                        else ""
                    ),
                    run.fractions.get(identifier, 0.0),
                    detail,
                    mark,
                ),
            )
        return tuple(rows)

    @staticmethod
    def _global_fraction(*, run: _PipelineRun) -> float:
        """Aggregate normalized task progress with equal task weighting.

        Child work totals normalize progress inside their owning task. They
        must not become pipeline weights because tool-specific activity counts
        are incomparable: hundreds of documentation symbols must not make one
        docs run outweigh every other pipeline task.

        Args:
            run: Mutable pipeline bookkeeping record.

        Returns:
            Mean normalized completion fraction across pipeline tasks.

        """
        if not run.order:
            return 0.0
        completed: float = sum(
            run.fractions.get(identifier, 0.0) for identifier in run.order
        )
        return min(max(completed / len(run.order), 0.0), 1.0)

    @staticmethod
    def _pipeline_fingerprint(
        *,
        pipeline: PipelineSpec,
        waves: tuple[tuple[ToolSpec, ...], ...],
        arguments: dict[str, tuple[str, ...]],
    ) -> str:
        """Hash the effective pipeline structure and tool arguments.

        Args:
            pipeline: Resolved pipeline specification.
            waves: Participating dependency waves.
            arguments: Effective arguments keyed by tool identifier.

        Returns:
            Stable SHA-256 configuration fingerprint.

        """
        payload: str = dumps(
            obj={
                "pipeline": pipeline.identifier,
                "waves": [
                    [tool.identifier for tool in wave] for wave in waves
                ],
                "arguments": {
                    identifier: list(values)
                    for identifier, values in sorted(arguments.items())
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(data=payload.encode(encoding="utf-8")).hexdigest()

    @staticmethod
    def _select_tools(
        *,
        parser: ArgumentParser,
        args: Namespace,
        selected: list[str],
        excluded: frozenset[str],
    ) -> tuple[list[str], tuple[str, ...]]:
        """Resolve ``--tools`` operands into catalog names and positionals.

        Leading operands naming catalog tools become the selection; any
        trailing non-tool operands are forwarded as tool arguments, which
        is only meaningful when a single tool was selected.

        Args:
            parser: Argument parser used for ``parser.error`` exits.
            args: Parsed namespace holding the positional ``tool_args``.
            selected: Raw ``--tools`` operand list.
            excluded: Resolved ``--exclude-tools`` set.

        Returns:
            ``(names, positionals)`` — validated tool identifiers and
            forwarded positional arguments.

        """
        names: list[str] = []
        while (
            selected
            and _GroupFinalConstants.exactus_catalog.tool(
                identifier=selected[0],
            )
            is not None
        ):
            names.append(selected.pop(0))
        if not names:
            parser.error(message=f"unknown exactus tool: {selected[0]}")
        if selected and len(names) > 1:
            parser.error(
                message=(
                    "trailing tool arguments require exactly one tool "
                    "(use --tool-arg TOOL::ARG for multiples)"
                ),
            )
        if excluded:
            parser.error(
                message="--exclude-tools cannot be combined with --tool",
            )
        blocked: frozenset[str] = frozenset(names) & _bundled_unavailable()
        if blocked:
            parser.error(
                message=(
                    f"{sorted(blocked)[0]} is unavailable in the bundled "
                    f"executable"
                ),
            )
        return (names, (*selected, *cast(typ="list[str]", val=args.tool_args)))

    @staticmethod
    def _pipeline_arguments(
        *,
        values: list[str],
    ) -> dict[str, tuple[str, ...]]:
        """Parse repeated ``TOOL::ARG`` values using canonical tool IDs.

        Args:
            values: Raw ``TOOL::ARG`` values.

        Returns:
            The resulting value.

        Raises:
            ValueError: If a value lacks the delimiter or names no tool.

        """
        grouped: dict[str, list[str]] = {}
        for raw in values:
            if "::" not in raw:
                msg: str = "--tool-arg requires TOOL::ARG"
                raise ValueError(msg)
            tool_name, argument = raw.split(sep="::", maxsplit=1)
            canonical: str = _GroupFinalConstants.exactus_catalog.canonical(
                identifier=tool_name,
            )
            if (
                _GroupFinalConstants.exactus_catalog.tool(identifier=canonical)
                is None
            ):
                msg = f"pipeline arguments require a tool, got: {tool_name}"
                raise ValueError(msg)
            grouped.setdefault(canonical, []).append(argument)
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _tool_exclusions(*, values: list[str]) -> frozenset[str]:
        """Resolve ``--exclude-tools`` operands to canonical tool ids.

        Args:
            values: Raw tool names or aliases.

        Returns:
            Canonical identifiers to remove from pipeline waves.

        Raises:
            ValueError: If a name resolves to no catalog tool.

        """
        excluded: set[str] = set()
        for raw in values:
            tool: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
                identifier=raw,
            )
            if tool is None:
                msg: str = (
                    f"--exclude-tools requires a catalog tool, got: {raw}"
                )
                raise ValueError(msg)
            excluded.add(tool.identifier)
        return frozenset(excluded)


@dataclass(frozen=True, slots=True)
class Tool:
    """Describe a bundled command-line tool.

    Attributes:
        name: Canonical tool identifier.
        create_parser: Factory returning the tool's argument parser.
        aliases: Former identifiers also accepted as dispatch flags.

    """

    name: str
    create_parser: ParserFactory
    aliases: tuple[str, ...] = ()

    @property
    def flag(self) -> str:
        """Top-level dispatch flag, such as ``--lints``.

        Returns:
            Dispatch flag.

        """
        return f"--{self.name}"

    @property
    def flags(self) -> tuple[str, ...]:
        """Dispatch flag followed by one flag per alias.

        Returns:
            Flags such as ``("--coverage_tests", "--coverage-tests",
            "--coverage")`` — each underscore spelling is paired with
            its dashed variant.

        """
        base: tuple[str, ...] = (
            self.flag,
            *(f"--{alias}" for alias in self.aliases),
        )
        dashed: tuple[str, ...] = tuple(
            variant
            for variant in (flag.replace("_", "-") for flag in base)
            if variant not in base
        )
        return (*base, *dashed)

    @property
    def parser(self) -> ArgumentParser:
        """Create the tool's argument parser.

        Returns:
            Tool argument parser.

        """
        return self.create_parser()


@dataclass(frozen=True, slots=True)
class ArgumentInfo:
    """Represent an argument extracted from an ArgumentParser.

    Attributes:
        syntax: Human-readable argument syntax.
        description: Human-readable argument description.

    """

    syntax: str
    description: str


class Terminal:
    """Render dependency-free terminal output.

    Attributes:
        RESET: ANSI reset sequence.
        BOLD: ANSI bold sequence.
        DIM: ANSI dim sequence.
        CYAN: ANSI cyan sequence.
        RED: ANSI red sequence.

    """

    RESET: ClassVar[str] = "\x1b[0m"
    BOLD: ClassVar[str] = "\x1b[1m"
    DIM: ClassVar[str] = "\x1b[2m"
    CYAN: ClassVar[str] = "\x1b[36m"
    RED: ClassVar[str] = "\x1b[31m"

    def __init__(self, stream: TextIO) -> None:
        """Initialize terminal output.

        Args:
            stream: Destination stream.

        """
        self.stream: TextIO = stream
        self.color: bool = (
            stream.isatty()
            and "NO_COLOR" not in environ
            and (environ.get("TERM") != "dumb")
        )

    def style(self, text: str, *styles: str) -> str:
        """Apply ANSI styles when terminal styling is available.

        Args:
            text: Text to style.
            *styles: ANSI style sequences.

        Returns:
            Styled or unmodified text.

        """
        return f"{''.join(styles)}{text}{self.RESET}" if self.color else text

    def write(self, text: str = "") -> None:
        """Write a line to the terminal.

        Args:
            text: Line content.

        """
        print(text, file=self.stream)


class HelpRenderer:
    """Extract and render help from child ArgumentParser instances.

    Attributes:
        HELP_DEST: Argparse destination reserved for the help action.

    """

    HELP_DEST: ClassVar[str] = "help"

    def __init__(self, terminal: Terminal) -> None:
        """Initialize the help renderer.

        Args:
            terminal: Terminal output renderer.

        """
        self.terminal: Terminal = terminal

    @classmethod
    def argument_syntax(cls, action: Action) -> str:
        """Build human-readable syntax for an argparse action.

        Args:
            action: Argument parser action.

        Returns:
            Human-readable argument syntax.

        """
        metavar: str = cls.metavar(action=action)
        if not action.option_strings:
            return metavar
        options: str = ", ".join(action.option_strings)
        if action.nargs == 0:
            return options
        return f"{options} {metavar}"

    @classmethod
    def argument_description(cls, action: Action) -> str:
        """Build descriptive metadata for an argparse action.

        Args:
            action: Argument parser action.

        Returns:
            Argument description.

        """
        parts: list[str] = []
        if action.help and action.help != "==SUPPRESS==":
            parts.append(action.help)
        if action.required:
            parts.append("required")
        choices: Iterable[object] | None = cast(
            typ="Iterable[object] | None",
            val=action.choices,
        )
        if choices is not None:
            parts.append(
                "choices: "
                + ", ".join(str(object=choice) for choice in choices),
            )
        default: object = cast(typ="object", val=action.default)
        if (
            default is not None
            and default != "==SUPPRESS=="
            and (not action.required)
            and (action.dest != cls.HELP_DEST)
        ):
            parts.append(f"default: {default}")
        return " · ".join(parts) if parts else "—"

    @classmethod
    def arguments(cls, parser: ArgumentParser) -> tuple[ArgumentInfo, ...]:
        """Extract displayable arguments from a parser.

        Args:
            parser: Argument parser to inspect.

        Returns:
            Extracted argument metadata.

        """
        return tuple(
            ArgumentInfo(
                syntax=cls.argument_syntax(action=action),
                description=cls.argument_description(action=action),
            )
            for action in cast(
                typ="Sequence[Action]",
                val=getattr(parser, "_actions", ()),
            )
            if action.dest != cls.HELP_DEST
        )

    @staticmethod
    def metavar(action: Action) -> str:
        """Determine the display metavar for an argparse action.

        Args:
            action: Argument parser action.

        Returns:
            Display metavar.

        """
        if isinstance(action.metavar, tuple):
            base: str = " ".join(value for value in action.metavar)
        elif action.metavar is not None:
            base = action.metavar
        else:
            base = action.dest.upper()
        if action.nargs == "?":
            return f"[{base}]"
        if action.nargs == "*":
            return f"[{base} ...]"
        if action.nargs == "+":
            return f"{base} [{base} ...]"
        if isinstance(action.nargs, int):
            return " ".join(base for _ in range(action.nargs))
        return base

    @staticmethod
    def wrap(text: str, width: int) -> tuple[str, ...]:
        """Wrap text without external dependencies.

        Args:
            text: Text to wrap.
            width: Maximum line width.

        Returns:
            Wrapped lines.

        """
        if len(text) <= width:
            return (text,)
        words: list[str] = text.split()
        lines: list[str] = []
        line: str = ""
        for word in words:
            if not line:
                line = word
            elif len(line) + len(word) + 1 <= width:
                line = f"{line} {word}"
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return tuple(lines)

    def render(self, tools: Sequence[Tool]) -> None:
        """Render aggregated help for all bundled tools.

        Args:
            tools: Registered tools.

        """
        terminal_width: int = max(
            80,
            get_terminal_size(fallback=(120, 24)).columns,
        )
        description_width: int = max(30, terminal_width - 42)
        self.terminal.write()
        self.terminal.write(
            text=self.terminal.style("Available CLI Tools", Terminal.BOLD),
        )
        self.terminal.write()
        self.terminal.write(
            text="Usage: <archive> --<tool> [tool arguments ...]",
        )
        self.terminal.write()
        for tool in tools:
            self.render_tool(tool=tool, description_width=description_width)
        self.render_section(
            heading=self.terminal.style(
                "Orchestrator Flags",
                Terminal.BOLD,
                Terminal.CYAN,
            ),
            description=(
                "Flags below select catalog tools and named "
                "pipelines against the current project and own the "
                "EXACTUS_RESULTS tree. Global --include/--exclude "
                "globs are forwarded to every tool whose parser "
                "accepts them."
            ),
            parser=Check.create_parser(),
            description_width=description_width,
        )
        self.terminal.write(
            text=self.terminal.style("Global options", Terminal.BOLD),
        )
        self.terminal.write()
        self.terminal.write(text="  -h, --help    Show this help.")
        self.terminal.write(
            text="  completion    Print/install shell completion scripts.",
        )
        self.terminal.write(
            text=(
                "  --install     Build and install the exactus command "
                "system-wide."
            ),
        )
        self.terminal.write(
            text="  --uninstall   Remove the system-wide exactus command.",
        )
        self.terminal.write(
            text=(
                "  --external    List bundled tools, or run one with `-"
                "-external TOOL ARGS...`."
            ),
        )
        self.terminal.write()
        self.terminal.write(
            text="Use --<tool> --help for the tool's native help.",
        )
        self.terminal.write(
            text="Long options accept '-' and '_' interchangeably.",
        )
        self.terminal.write()

    def render_tool(self, tool: Tool, description_width: int) -> None:
        """Render one tool and its arguments.

        Args:
            tool: Tool to render.
            description_width: Description column width.

        """
        parser: ArgumentParser = tool.parser
        self.render_section(
            heading=self.terminal.style(
                tool.flag,
                Terminal.BOLD,
                Terminal.CYAN,
            ),
            description=parser.description or parser.prog or "No description.",
            parser=parser,
            description_width=description_width,
        )

    def render_section(
        self,
        *,
        heading: str,
        description: str,
        parser: ArgumentParser,
        description_width: int,
    ) -> None:
        """Render one heading, description, and argument table.

        Args:
            heading: Styled section heading line.
            description: Section description text.
            parser: Argument parser to inspect.
            description_width: Description column width.

        """
        self.terminal.write(text=heading)
        for line in self.wrap(text=description, width=description_width):
            self.terminal.write(text=f"  {line}")
        arguments: tuple[ArgumentInfo, ...] = self.arguments(parser=parser)
        if arguments:
            syntax_width: int = min(
                34,
                max(len(argument.syntax) for argument in arguments),
            )
            self.terminal.write()
            self.terminal.write(
                text=f"  {'ARGUMENT':<{syntax_width}}  DESCRIPTION",
            )
            self.terminal.write(
                text=(
                    f"  {'─' * syntax_width}  "
                    f"{'─' * min(description_width, 50)}"
                ),
            )
            for argument in arguments:
                self.render_argument(
                    argument=argument,
                    syntax_width=syntax_width,
                    description_width=description_width,
                )
        self.terminal.write()

    def render_argument(
        self,
        argument: ArgumentInfo,
        syntax_width: int,
        description_width: int,
    ) -> None:
        """Render one tool argument.

        Args:
            argument: Argument metadata.
            syntax_width: Width of the syntax column.
            description_width: Width of the description column.

        """
        lines: tuple[str, ...] = self.wrap(
            text=argument.description,
            width=description_width,
        )
        self.terminal.write(
            text=f"  {argument.syntax:<{syntax_width}}  {lines[0]}",
        )
        for line in lines[1:]:
            self.terminal.write(text=f"  {'':<{syntax_width}}  {line}")


class Application:
    """Dispatch bundled command-line tools.

    Attributes:
        HELP_FLAGS: Top-level flags that render aggregated help.

    """

    HELP_FLAGS: ClassVar[frozenset[str]] = frozenset(("-h", "--help"))

    def __init__(
        self,
        output: Terminal,
        error: Terminal,
        tools: Sequence[Tool],
    ) -> None:
        """Initialize the application.

        Args:
            output: Standard output renderer.
            error: Standard error renderer.
            tools: Registered tools.

        """
        self.output: Terminal = output
        self.error: Terminal = error
        self.tools: tuple[Tool, ...] = tuple(tools)
        self.tool_map: dict[str, Tool] = {
            flag: tool for tool in self.tools for flag in tool.flags
        }

    def run(self, arguments: Sequence[str]) -> int:
        """Dispatch the requested tool.

        Args:
            arguments: Arguments excluding the executable name.

        Returns:
            Process exit status.

        """
        sprint("\x1b[2J\x1b[3J\x1b[H")
        arguments, root = _extract_root(arguments=arguments)
        if root is not None:
            Check.use_root(root=root)
        arguments = _extract_config(arguments=arguments)
        if arguments and arguments[0] in self.HELP_FLAGS:
            HelpRenderer(terminal=self.output).render(tools=self.tools)
            return 0
        Check.venv_reexec()
        try:
            Check.load_config(force=True)
            arguments = self._configured(arguments=arguments)
        except ConfigError as exc:
            self.error.write(text=str(object=exc))
            return 2
        if any(
            normalized_option(argument=item) == "--show_config"
            for item in arguments
        ):
            return self._show_config(arguments=arguments)
        if not arguments:
            return self._orchestrate(arguments=())
        return self._dispatch(arguments=arguments)

    def show_error(self, argument: str) -> None:
        """Display an unknown-tool error.

        Args:
            argument: Unknown top-level argument.

        """
        self.error.write(
            text=self.error.style(
                f"Unknown tool: {argument}",
                Terminal.BOLD,
                Terminal.RED,
            ),
        )
        self.error.write()
        self.error.write(text="Available tools:")
        for tool in self.tools:
            self.error.write(text=f"  {tool.flag}")
        self.error.write()
        self.error.write(text="Run -h or --help to display complete help.")

    @staticmethod
    def _orchestrate(arguments: Sequence[str]) -> int:
        """Forward orchestrator arguments to :class:`Check`.

        Args:
            arguments: Arguments excluding the executable name.

        Returns:
            Orchestrator exit status.

        """
        try:
            Check.main(arguments=tuple(arguments))
        except SystemExit as exc:
            if isinstance(exc.code, int):
                return exc.code
            return 0 if exc.code is None else 1
        return 0

    def _show_config(self, *, arguments: Sequence[str]) -> int:
        """Print each tool's effective options and where they came from.

        Args:
            arguments: Arguments including ``--show-config``; ``-t NAME...``
                or ``--pipeline NAME`` narrow the report and tokens after
                ``--`` count as command-line options.

        Returns:
            Always ``0``.

        """
        items: list[str] = [
            item
            for item in arguments
            if normalized_option(argument=item) != "--show_config"
        ]
        cli: tuple[str, ...] = ()
        if "--" in items:
            split: int = items.index("--")
            cli, items = (tuple(items[split + 1 :]), items[:split])
        selected: list[str] = []
        pipeline: str | None = None
        collecting: bool = False
        for index, item in enumerate(iterable=items):
            if item in {"-t", "--tools", "--tool"}:
                collecting = True
            elif item.startswith("-"):
                collecting = False
                if item == "--pipeline" and index + 1 < len(items):
                    pipeline = items[index + 1]
            elif collecting:
                named: ToolSpec | None = (
                    _GroupFinalConstants.exactus_catalog.tool(identifier=item)
                )
                selected.append(item if named is None else named.identifier)
        spec: PipelineSpec | None = (
            _GroupFinalConstants.exactus_catalog.pipeline(identifier=pipeline)
            if pipeline is not None
            else None
        )
        tools: tuple[ToolSpec, ...] = tuple(
            tool
            for tool in _GroupFinalConstants.exactus_catalog.tools()
            if not selected or tool.identifier in selected
        )
        self.output.write(
            text="config files: "
            + (
                ", ".join(str(object=item.path) for item in Check.config_files)
                or "(none)"
            ),
        )
        for tool in tools:
            self.output.write(text=f"\n[{tool.identifier}]")
            for option, value, layer in effective(
                files=Check.config_files,
                request=EffectiveRequest(
                    tool=tool.identifier,
                    module=tool.module,
                    preset=spec.tool_arguments.get(tool.identifier, ())
                    if spec is not None
                    else (),
                    cli=cli,
                    pipeline=pipeline,
                ),
            ):
                self.output.write(text=f"  {option:<28} {layer:<9} {value}")
        return 0

    def _configured(self, *, arguments: Sequence[str]) -> tuple[str, ...]:
        """Prefix ``exactus``'s own settings from ``[tool.exactus]``.

        Args:
            arguments: Arguments the user typed.

        Returns:
            Configured tokens followed by ``arguments``.

        """
        pipeline: str = "unified"
        for index, item in enumerate(iterable=arguments):
            if item == "--pipeline" and index + 1 < len(arguments):
                pipeline = arguments[index + 1]
            elif item.startswith("--pipeline="):
                pipeline = item.partition("=")[2]
        injected: tuple[str, ...] = orchestrator_arguments(
            files=Check.config_files,
            parser=Check.create_parser(),
            arguments=arguments,
            pipeline=pipeline,
            tool_flags=frozenset(self.tool_map),
        )
        return (*injected, *arguments)

    def _dispatch(self, arguments: Sequence[str]) -> int:
        """Dispatch a tool flag, orchestrator flag, or unknown argument.

        Args:
            arguments: Arguments excluding the executable name; the
                first is not a help or shortcut flag.

        Returns:
            Process exit status.

        """
        if (tool := self.tool_map.get(arguments[0])) is not None:
            rest: list[str] = list(arguments[1:])
            if any(flag in self.HELP_FLAGS for flag in rest):
                _ = tool.parser.parse_args(args=rest)
                return 0
            return (
                0
                if Check.run_tool(name=tool.name, arguments=tuple(rest))
                else 1
            )
        if arguments[0].startswith("-"):
            return self._orchestrate(arguments=arguments)
        if resolve_exactus_tool_bundle(root=Path.cwd()) is not None:
            return run_external_command(arguments=list(arguments))
        self.show_error(argument=arguments[0])
        return 2


def _apply_config_flags(*, config: str | None, disabled: bool) -> None:
    """Export ``--config``/``--no-config`` for this and child processes.

    Args:
        config: Explicit configuration file, if any.
        disabled: Whether the configuration layer is turned off.

    """
    if disabled:
        environ["EXACTUS_CONFIG"] = "off"
    elif config is not None:
        environ["EXACTUS_CONFIG"] = str(
            object=Path(config).expanduser().resolve(),
        )


def _extract_config(*, arguments: Sequence[str]) -> tuple[str, ...]:
    """Remove ``--config FILE``/``--no-config`` and export their effect.

    Args:
        arguments: Raw arguments excluding the executable name.

    Returns:
        The remaining arguments.

    """
    remaining: list[str] = []
    config: str | None = None
    disabled: bool = False
    items: list[str] = list(arguments)
    index: int = 0
    while index < len(items):
        item: str = items[index]
        if item == "--":
            remaining.extend(items[index:])
            break
        if item == "--config" and index + 1 < len(items):
            config = items[index + 1]
            index += 2
            continue
        if item.startswith("--config="):
            config = item.partition("=")[2]
        elif normalized_option(argument=item) == "--no_config":
            disabled = True
        else:
            remaining.append(item)
        index += 1
    _apply_config_flags(config=config, disabled=disabled)
    return tuple(remaining)


def _extract_root(
    *,
    arguments: Sequence[str],
) -> tuple[tuple[str, ...], Path | None]:
    """Remove a global ``--root DIR``/``--root=DIR`` flag.

    Args:
        arguments: Raw arguments excluding the executable name.

    Returns:
        Remaining arguments and the requested root, if any.

    """
    remaining: list[str] = []
    root: Path | None = None
    items: list[str] = list(arguments)
    index: int = 0
    while index < len(items):
        item: str = items[index]
        if item == "--":
            remaining.extend(items[index:])
            break
        if item == "--root" and index + 1 < len(items):
            root = Path(items[index + 1])
            index += 2
            continue
        if item.startswith("--root="):
            root = Path(item.partition("=")[2])
        else:
            remaining.append(item)
        index += 1
    return (tuple(remaining), root)


def _handle_signal(signum: int, _frame: FrameType | None) -> NoReturn:
    """Convert a termination signal into a graceful exit.

    Descendants are terminated and streams flushed before the hard
    exit so blocked loops (Playwright's driver, server waits) cannot
    swallow a raised ``SystemExit`` inside an event-loop callback.

    Args:
        signum: Received signal number.
        _frame: Interrupted frame.

    """
    exit_if_replaced()
    _terminate_descendants()
    ExactusTerminal.restore_cursor()
    with suppress(Exception):
        _ = stdout.flush()
        _ = stderr.flush()
    _exit(status=128 + signum)


def _install_signal_handlers() -> None:
    """Route termination signals through graceful shutdown."""
    for name in ("SIGHUP", "SIGINT", "SIGTERM"):
        signum: Signals | None = getattr(Signals, name, None)
        if signum is not None:
            _ = signal(signalnum=signum, handler=_handle_signal)


def _terminate_descendants() -> None:
    """Terminate surviving children, including tool subprocesses."""
    terminate_tree(pid=getpid(), include_root=False)


def bundled_tools() -> tuple[Tool, ...]:
    """Return the tools dispatched by this CLI.

    Shared by :func:`main` and the completion catalog so both describe
    the same command surface.

    Returns:
        Every bundled tool with its parser factory and aliases.

    """
    tools: tuple[Tool, ...] = (
        Tool(name="lints", create_parser=lints_parser),
        Tool(name="coverage_tests", create_parser=coverage_tests_parser),
        Tool(name="docs", create_parser=docs_parser),
        Tool(name="kwargs_typehints", create_parser=kwargs_typehints_parser),
        Tool(name="readme", create_parser=readme_parser),
        Tool(name="record", create_parser=record_parser),
        Tool(name="frontend", create_parser=frontend_parser),
        Tool(name="visual_cause", create_parser=visual_cause_parser),
        Tool(name="self_test", create_parser=self_test_parser),
    )
    unavailable: frozenset[str] = _bundled_unavailable()
    return tuple(tool for tool in tools if tool.name not in unavailable)


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Run the bundled CLI dispatcher.

    Args:
        arguments: Arguments excluding the executable name.

    Returns:
        Process exit status.

    """
    resolved: Sequence[str] = argv[1:] if arguments is None else arguments
    if resolved and resolved[0] == "__complete":
        return run_completion(
            arguments=resolved[1:],
            catalog=check_catalog(
                tools=bundled_tools(),
                orchestrator_parser=Check.create_parser(),
            ),
            providers=default_providers(
                tools=tuple(_GroupFinalConstants_2.tool_descriptions.items()),
                pipelines=tuple(
                    (pipeline.identifier, "Named pipeline")
                    for pipeline in (
                        _GroupFinalConstants.exactus_catalog.pipelines()
                    )
                ),
            ),
        )
    if resolved and resolved[0] == "completion":
        return run_completion_command(arguments=resolved[1:])
    if resolved and resolved[0] in (
        "install",
        "--install",
        "uninstall",
        "--uninstall",
    ):
        return run_install_command(
            arguments=resolved[1:],
            uninstall=resolved[0] in ("uninstall", "--uninstall"),
        )
    if resolved and resolved[0] in ("external", "--external"):
        return run_external_command(arguments=resolved[1:])
    warn_if_stale()
    ensure_completion()
    tools: tuple[Tool, ...] = bundled_tools()
    _install_signal_handlers()
    try:
        return Application(
            output=Terminal(stream=stdout),
            error=Terminal(stream=stderr),
            tools=tools,
        ).run(arguments=resolved)
    except KeyboardInterrupt:
        return 130
    finally:
        _terminate_descendants()
        ExactusTerminal.restore_cursor()


if __name__ == "__main__":
    raise SystemExit(main())
