# Copyright (c) 2026
# Copyright (c) 2026
"""Shared command-line and glob helpers for project exactuss."""

from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from fnmatch import fnmatch
from hashlib import sha256
from importlib import invalidate_caches
from importlib.resources import files as resource_files
from importlib.util import module_from_spec, spec_from_file_location
from json import loads
from os import X_OK, access, environ, pathsep
from pathlib import Path
from platform import libc_ver, machine, system
from shutil import copyfileobj, rmtree, which
from sys import modules
from sys import path as sys_path
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Final,
    Protocol,
    TypedDict,
    cast,
    final,
)
from uuid import uuid4

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.snippets import SnippetLimits

if TYPE_CHECKING:
    from _hashlib import HASH
    from collections.abc import Callable, Sequence
    from concurrent.futures import Future
    from importlib.machinery import ModuleSpec
    from importlib.resources.abc import Traversable
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        heartbeat_timestamp_format: Grouped module constant.

    """

    heartbeat_timestamp_format: Final[str] = "%d/%m/%Y %H:%M:%S"


def map_lanes[T, R](*, lanes: Sequence[T], work: Callable[[T], R]) -> list[R]:
    """Run ``work`` once per lane on pooled threads, preserving order.

    Console-version lanes share nothing mutable — each writes to its own
    ``OUTPUT/VERSION`` directory — so a small thread pool halves the
    wall-clock cost of sibling captures. A single lane runs inline to
    keep sequential semantics and a plain traceback.

    Args:
        lanes: Lane keys, typically console generations.
        work: Lane callable invoked once per lane key.

    Returns:
        Lane results in input order; the first lane exception propagates.

    """
    min_lanes: int = 2
    if len(lanes) < min_lanes:
        return [work(lane) for lane in lanes]
    with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
        futures: list[Future[R]] = [pool.submit(work, lane) for lane in lanes]
        return [future.result() for future in futures]


def consume[T](value: T) -> T:
    """Explicitly consume a return value used only for side effects.

    Args:
        value: Evaluated value intentionally discarded by callers.

    Returns:
        The value unchanged.

    """
    return value


def heartbeat_timestamp() -> str:
    """Return the local wall-clock time for heartbeat payloads.

    Returns:
        Current local time formatted ``DD/MM/YYYY HH:MM:SS``.

    """
    return (
        datetime.now(tz=UTC)
        .astimezone()
        .strftime(format=Constants.heartbeat_timestamp_format)
    )


@final
class ExactusCommonTables:
    """Shared lookup tables and compiled values.

    Attributes:
        DEFAULT_EXCLUDES: Default excludes.
        DEFAULT_EXCLUDED_DIRS: Directory names skipped during source
            discovery and measurement at any depth.
        LINTER_TOOLCHAIN: Linter toolchain.
        LINTER_TOOLCHAIN_ARCHES: Linter toolchain arches.
        LINTER_TOOLCHAIN_ENV: Linter toolchain env.
        BUNDLE_IMPORTS: Python modules the exactus bundle exposes
            in-process.

    """

    DEFAULT_EXCLUDES: ClassVar[tuple[str, ...]] = (
        ".*/**",
        "**/.*/**",
        "EXACTUS_RESULTS/**",
        "**/EXACTUS_RESULTS/**",
        "node_modules/**",
        "build/**",
        "dist/**",
        "*.egg-info/**",
        "**/__pycache__/**",
    )
    DEFAULT_EXCLUDED_DIRS: ClassVar[frozenset[str]] = frozenset(
        {
            ".agents",
            ".build-cache",
            ".cache",
            ".claude",
            ".cursor",
            ".devin",
            ".eggs",
            ".git",
            ".history",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".tox",
            ".venv",
            "EXACTUS_RESULTS",
            "__pycache__",
            "build",
            "coverage_report",
            "dist",
            "env",
            "htmlcov",
            "mutants",
            "node_modules",
            "site-packages",
            "venv",
        },
    )
    LINTER_TOOLCHAIN: ClassVar[str] = "linters-linux-amd64"
    LINTER_TOOLCHAIN_ENV: ClassVar[str] = "EXACTUS_LINTER_TOOLCHAIN"
    LINTER_TOOLCHAIN_ARCHES: ClassVar[frozenset[str]] = frozenset(
        {"x86_64", "amd64"},
    )
    BUNDLE_IMPORTS: ClassVar[tuple[str, ...]] = (
        "PIL",
        "coverage",
        "playwright",
    )


def context_lines(text: str) -> int:
    """Parse a ``--context-lines`` value.

    Args:
        text: Command-line or configuration text.

    Returns:
        The non-negative number of lines.

    Raises:
        ArgumentTypeError: If the text is not a non-negative integer.

    """
    try:
        value: int = int(text)
    except ValueError as exc:
        msg: str = f"expected a non-negative integer, got {text!r}"
        raise ArgumentTypeError(msg) from exc
    if value < 0:
        msg = f"expected a non-negative integer, got {text!r}"
        raise ArgumentTypeError(msg)
    return value


def add_common_arguments(
    *,
    parser: ArgumentParser,
    default_output: str,
) -> None:
    """Add the common exactus CLI surface.

    ``--context-lines`` sets the source lines captured around each
    finding line (report excerpts); ``[tool.exactus] context-lines`` sets
    it for every tool and ``[tool.exactus.<tool>] context-lines`` for one.

    Args:
        parser: Argument parser to extend.
        default_output: Default output directory name.

    """
    _ = consume(
        value=parser.add_argument(
            "root",
            nargs="?",
            type=Path,
            default=Path.cwd(),
            help="Project root (default: current directory).",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "-o",
            "--output-dir",
            type=Path,
            default=Path("EXACTUS_RESULTS") / default_output,
            help=(
                "Output directory (default:"
                f" EXACTUS_RESULTS/{default_output})."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--include",
            action="append",
            default=[],
            metavar="GLOB",
            help="Include relative paths matching GLOB; repeatable.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--exclude",
            action="append",
            default=[],
            metavar="GLOB",
            help="Exclude relative paths matching GLOB; repeatable.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--context-lines",
            type=context_lines,
            default=SnippetLimits.default_context,
            metavar="N",
            help=(
                "Source lines shown around each reported line in report"
                " excerpts and snippets (default: %(default)s)."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--dry",
            "--dry-run",
            action="store_true",
            dest="dry",
            help=(
                "Analyze and report without modifying project files; honored"
                " by tools that fix or write sources."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--collect-files",
            action="store_true",
            dest="collect_files",
            help=(
                "Bundle every file the report lists findings for into a"
                " FILES folder beside the report (README.md, TREE.txt and"
                " files.zip keeping the project folder structure)."
            ),
        ),
    )


def parse_common_arguments(
    *,
    default_output: str,
    arguments: tuple[str, ...] | None = None,
) -> Namespace:
    """Parse the common standalone exactus CLI surface.

    Args:
        default_output: Default output directory name.
        arguments: Explicit arguments supplied by the Python API. ``None``
            uses the standalone process command line.

    Returns:
        Parsed common exactus arguments.

    """
    parser: ArgumentParser = ExactusArgumentParser()
    add_common_arguments(parser=parser, default_output=default_output)
    return parser.parse_args(args=arguments)


def resolve_report_output(*, requested: Path | None, default: str) -> Path:
    """Resolve an analyzer report directory for optional-output CLIs.

    The ``run_exactus`` wrapper exports ``EXACTUS_REPORT_OUTPUT`` so a
    pipeline-provided ``--report-output`` always wins; an explicit
    ``--output`` comes next, then ``default`` under the working
    directory.

    Args:
        requested: Optional ``--output`` path supplied on the CLI.
        default: Fallback directory such as ``EXACTUS_RESULTS/BROWSER_E2E``.

    Returns:
        Absolute resolved output directory path.

    """
    if override := environ.pop("EXACTUS_REPORT_OUTPUT", default=None):
        return Path(override).resolve()
    return (requested or Path(default)).resolve()


def resolve_output(*, root: Path, output: Path) -> Path:
    """Resolve an output directory, honoring cwd-relative paths.

    Absolute paths pass through.  A relative path that already exists
    under the working directory, or that would land inside the scan
    root when resolved from the working directory (for example
    ``exactus/EXACTUS_RESULTS`` while scanning ``scripts/exactus``), is
    treated as working-directory relative.  Any other relative path is
    resolved under ``root``, so bare names like ``EXACTUS_RESULTS/UNIFIED``
    still
    land inside the scanned project.

    Args:
        root: Project root directory.
        output: Requested output directory.

    Returns:
        Absolute resolved output directory path.

    """
    if override := environ.pop("EXACTUS_REPORT_OUTPUT", default=None):
        return Path(override).resolve()
    if output.is_absolute():
        return output.resolve()
    resolved_root: Path = root.resolve()
    cwd_relative: Path = (Path.cwd() / output).resolve()
    if cwd_relative.is_dir() or cwd_relative.is_relative_to(resolved_root):
        return cwd_relative
    return (resolved_root / output).resolve()


def is_reports_tree(directory: Path) -> bool:
    """Return whether ``directory`` holds exactus report output.

    The results root name is configurable (``-o/--output-dir``,
    ``output_dir`` settings, ``EXACTUS_REPORT_OUTPUT``), so report trees
    are recognized by their contents rather than their name:

    - ``.runtime/`` — the shared run registry directory of a results
      root;
    - ``result.json`` + ``result.md`` — the canonical report bundle of
      a finished tool or pipeline output;
    - ``ARTIFACTS/@activity.json`` — the in-flight marker a run writes
      before its result bundle lands.

    Source discovery walks prune fingerprinted directories so renamed
    results roots and nested fixture outputs are never collected.

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


def match_path(
    *,
    path: Path,
    root: Path,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    defaults: bool = True,
) -> bool:
    """Return whether a path passes normalized glob filters.

    ``DEFAULT_EXCLUDES`` applies unless ``defaults`` is false (including
    dot-folder globs like ``.*/**``); caller-supplied ``excludes`` extend
    them rather than replacing them.

    Args:
        path: Candidate file path.
        root: Project root the candidate is relativized against.
        includes: Glob patterns the path must match, when supplied.
        excludes: Additional glob patterns rejecting the path.
        defaults: Whether ``DEFAULT_EXCLUDES`` participates in matching.

    Returns:
        ``True`` when the path survives the include/exclude filters.

    """
    relative: str = path.resolve().relative_to(root.resolve()).as_posix()
    patterns: tuple[str, ...] = (
        *(ExactusCommonTables.DEFAULT_EXCLUDES if defaults else ()),
        *excludes,
    )
    included: bool = not includes
    pattern: str
    if not included:
        for pattern in includes:
            if fnmatch(name=relative, pat=pattern):
                included = True
                break
    if not included:
        return False
    excluded: bool = False
    for pattern in patterns:
        if fnmatch(name=relative, pat=pattern):
            excluded = True
            break
    return not excluded


def linter_platform_supported() -> bool:
    """Return whether the bundled linter toolchain can execute locally.

    The ``linters-linux-amd64`` executable is a Linux AMD64 binary, so
    automatic discovery only applies on that platform.

    Returns:
        ``True`` when running on Linux on an AMD64-class machine.

    """
    return (
        system() == "Linux"
        and machine().lower() in ExactusCommonTables.LINTER_TOOLCHAIN_ARCHES
    )


def _executable_candidate(*, candidate: Path) -> Path | None:
    """Return a usable executable path, repairing its mode when needed.

    Args:
        candidate: Filesystem path to validate as an executable.

    Returns:
        Resolved executable path, or ``None`` when the candidate is not
        a runnable file.

    """
    resolved: Path = candidate.expanduser().resolve()
    if not resolved.is_file():
        return None
    if not access(path=resolved, mode=X_OK):
        with suppress(OSError):
            resolved.chmod(mode=493)
    return resolved if access(path=resolved, mode=X_OK) else None


def resolve_linter_toolchain(
    *,
    root: Path,
    option: Path | None = None,
) -> Path | None:
    """Resolve the canonical bundled Ruff + BasedPyright executable.

    An explicit ``option`` and the ``EXACTUS_LINTER_TOOLCHAIN`` environment
    variable are honored on any platform. Automatic discovery of the
    bundled executable and PATH lookup only apply on Linux AMD64, the
    toolchain's target platform.

    Args:
        root: Project root directory searched for the toolchain.
        option: Explicit toolchain path, when provided.

    Returns:
        Resolved toolchain executable path, or ``None`` when the bundled
        toolchain is unavailable.

    """
    name: str = ExactusCommonTables.LINTER_TOOLCHAIN
    candidate: Path | None
    for candidate in (
        option,
        (
            Path(env)
            if (env := environ.get(ExactusCommonTables.LINTER_TOOLCHAIN_ENV))
            else None
        ),
    ):
        if (
            candidate is not None
            and (resolved := _executable_candidate(candidate=candidate))
            is not None
        ):
            return resolved
    if not linter_platform_supported():
        return None
    for candidate in (
        root / name / name,
        root / name,
        root / ".chatgpt" / "tools" / name,
        Path(name),
    ):
        if (
            resolved := _executable_candidate(candidate=candidate)
        ) is not None:
            return resolved
    found: str | None = which(cmd=name)
    return (
        _executable_candidate(candidate=Path(found))
        if found is not None
        else None
    )


def linter_command(
    *,
    tool: str,
    root: Path,
    toolchain: Path | None = None,
    search: str | None = None,
) -> tuple[str, ...]:
    """Return the command prefix that invokes one linter.

    The bundled Linux AMD64 toolchain is preferred when present; an
    installed executable resolvable on ``search``/PATH comes next, the
    offline ``exactus/bundle`` platform bundle follows, and the bare tool
    name is returned last so the caller's own subprocess environment can
    still resolve it.

    Args:
        tool: Linter subcommand name (``ruff`` or ``basedpyright``).
        root: Project root used for toolchain discovery.
        toolchain: Pre-resolved toolchain path, when already known.
        search: Optional PATH-style search string for standalone tools.

    Returns:
        Command prefix, either ``(toolchain, tool)`` or ``(tool,)``.

    """
    resolved_toolchain: Path | None = (
        toolchain
        if toolchain is not None
        else resolve_linter_toolchain(root=root)
    )
    if resolved_toolchain is not None:
        return (str(object=resolved_toolchain), tool)
    if (found := which(cmd=tool, path=search)) is not None:
        return (found,)
    if (bundle := resolve_exactus_tool_bundle(root=root)) is not None:
        return (str(object=bundle), tool)
    return (tool,)


def _host_musl() -> bool:
    """Return whether the host C library is musl.

    Returns:
        ``True`` on musl-based Linux distributions.

    """
    if "musl" in libc_ver()[0].lower():
        return True
    return any(
        loader.is_file()
        for root in ("/lib", "/usr/lib")
        for loader in Path(root).glob(pattern="ld-musl-*.so*")
    )


def _host_bundle_dirs() -> tuple[Path, ...]:
    """Return host bundle directories under ``bundle/``, best first.

    Returns:
        Relative bundle directories such as ``linux/glibc/amd64`` or
        ``linux/musl/arm64`` suitable for the current host, empty when
        the platform is unsupported. musl hosts list their musl
        directory before the glibc fallback.

    """
    os_dir: str | None = {
        "Linux": "linux",
        "Darwin": "macos",
        "Windows": "windows",
    }.get(system())
    arch_dir: str | None = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine().lower())
    if os_dir is None or arch_dir is None:
        return ()
    if os_dir == "linux":
        glibc: Path = Path("linux") / "glibc" / arch_dir
        if _host_musl():
            return (Path("linux") / "musl" / arch_dir, glibc)
        return (glibc,)
    return (Path(os_dir) / arch_dir,)


def resolve_exactus_tool_bundle(*, root: Path) -> Path | None:
    """Resolve the offline exactus tool bundle for this host.

    Args:
        root: Project root searched for the ``bundle/<os>/<arch>``
            directory tree.

    Returns:
        Executable bundle path for the host platform, otherwise
        ``None``.

    """
    bundle_dirs: tuple[Path, ...] = _host_bundle_dirs()
    if not bundle_dirs:
        return None
    for bundle_dir in bundle_dirs:
        candidate: Path
        for candidate in (
            root / "bundle" / bundle_dir / "__main__.py",
            root / "exactus" / "bundle" / bundle_dir / "__main__.py",
            Path(__file__).parent.parent.parent
            / "bundle"
            / bundle_dir
            / "__main__.py",
        ):
            if (
                resolved := _executable_candidate(candidate=candidate)
            ) is not None:
                return resolved
    embedded: Path | None = _embedded_bundle_dir()
    if embedded is not None:
        return _executable_candidate(candidate=embedded / "__main__.py")
    return None


class _BundleMetadata(TypedDict):
    """Verified subset of component metadata needed for Python activation.

    Attributes:
        env: Env recorded by this structure.

    """

    env: dict[str, list[str]]


class _BundleComponent(TypedDict):
    """Verified component view for runtime selection.

    Attributes:
        metadata: Metadata recorded by this structure.

    """

    metadata: _BundleMetadata


class _BundleCatalog(TypedDict):
    """Verified catalog view for exactus helper integration.

    Attributes:
        components: Components recorded by this structure.

    """

    components: dict[str, _BundleComponent]


class _PartitionRuntime(Protocol):
    """Minimal runtime interface used by the exactus's Python activation.

    Attributes:
        components: Components recorded by this structure.

    """

    components: Path

    def ensure(self, name: str) -> Path:
        """Ensure one component's dependency closure is ready.

        Args:
            name: Component or resource name.


        Returns:
            Ensure one component's dependency closure is ready.

        """
        ...


class _RuntimeConstructor(Protocol):
    """Catalog-bound constructor exposed by the loaded runtime."""

    def __call__(self, catalog_path: Path) -> _PartitionRuntime:
        """Create the offline runtime for one catalog.

        Args:
            catalog_path: Verified distribution catalog location.

        Returns:
            Dependency-aware runtime instance.

        """
        ...


class _PartitionModule(Protocol):
    """Typed constructor exported by the standalone runtime module.

    Attributes:
        Runtime: Runtime recorded by this structure.

    """

    Runtime: _RuntimeConstructor


def _embedded_bundle_dir() -> Path | None:
    """Resolve a disk bundle or atomically copy a canonical zipapp bundle.

    Returns:
        Resolve a disk bundle or atomically copy a canonical zipapp bundle.

    """
    try:
        bundle: Traversable = resource_files("exactus").joinpath("bundle")
        for bundle_dir in _host_bundle_dirs():
            anchor: Traversable = bundle
            for part in bundle_dir.parts:
                anchor = anchor.joinpath(part)
            launcher: Traversable = anchor.joinpath("__main__.py")
            catalog: Traversable = anchor.joinpath(
                "data",
                "parts",
                "fs",
                "catalog.json",
            )
            if not launcher.is_file() or not catalog.is_file():
                continue
            if isinstance(launcher, Path):
                return launcher.parent
            return _materialize_bundle(anchor=anchor)
    except (ModuleNotFoundError, OSError, ValueError):
        return None
    return None


def _resource_copy(source: Traversable, target: Path) -> None:
    """Stream resources recursively; never load a compressed pack at once.

    Args:
        source: Verified source data.
        target: Target for this operation.


    Raises:
        ValueError: When the operation detects invalid input or state.

    """
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            if (
                child.name in {".", ".."}
                or "/" in child.name
                or "\\" in child.name
            ):
                msg: str = "Unsafe embedded resource name"
                raise ValueError(msg)
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            _resource_copy(source=child, target=target / child.name)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            source.open(mode="rb") as reader,
            target.open(mode="xb") as writer,
        ):
            copyfileobj(fsrc=reader, fdst=writer, length=1024 * 1024)


def _materialize_bundle(*, anchor: Traversable) -> Path | None:
    """Copy catalog, runtime, native bootstrap, and nested packs atomically.

    Args:
        anchor: Root of a canonical embedded partitioned bundle.

    Returns:
        Snapshot cache directory, or None when resources are invalid.

    """
    try:
        raw: bytes = anchor.joinpath(
            "data",
            "parts",
            "fs",
            "catalog.json",
        ).read_bytes()
        digest: HASH = sha256(data=raw)
        for name in (
            "__init__.py",
            "__main__.py",
            "partition_fs.py",
            "partition_launcher.py",
            "conflict_copies.py",
        ):
            digest.update(anchor.joinpath(name).read_bytes())
        base: Path = (
            Path(environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
            / "exactus-tools"
            / "embedded"
            / digest.hexdigest()
        )
        if (base / ".ready").is_file():
            return base
        temporary: Path = base.with_name(
            name=f".{base.name}.tmp.{uuid4().hex}",
        )
        temporary.mkdir(parents=True)
        try:
            for name in (
                "__init__.py",
                "__main__.py",
                "partition_fs.py",
                "partition_launcher.py",
                "conflict_copies.py",
                "zstd_portable",
                "data",
            ):
                _resource_copy(
                    source=anchor.joinpath(name),
                    target=temporary / name,
                )
            (temporary / ".ready").write_text(data=digest.hexdigest())
            if (base / ".ready").is_file():
                rmtree(path=temporary)
            else:
                temporary.replace(target=base)
        finally:
            if temporary.exists():
                rmtree(path=temporary)
    except (OSError, ValueError, KeyError):
        return None
    else:
        return base


def _partition_runtime(bundle: Path) -> _PartitionRuntime:
    """Load an isolated package namespace with relative runtime imports.

    Args:
        bundle: Bundle for this operation.


    Returns:
        Load an isolated package namespace with relative runtime imports.

    Raises:
        ImportError: When the operation detects invalid input or state.

    """
    path: Path = bundle.parent / "partition_launcher.py"
    package: str = (
        "_exactus_partition_"
        + sha256(
            data=path.read_bytes()
            + (bundle.parent / "partition_fs.py").read_bytes()
            + (
                bundle.parent / "data" / "parts" / "fs" / "catalog.json"
            ).read_bytes(),
        ).hexdigest()
    )
    module_spec: ModuleSpec | None = spec_from_file_location(
        name=package,
        location=path,
        submodule_search_locations=[str(object=bundle.parent)],
    )
    if module_spec is None or module_spec.loader is None:
        msg: str = "Partition runtime cannot be loaded"
        raise ImportError(msg)
    module: ModuleType = module_from_spec(spec=module_spec)
    modules[package] = module
    module_spec.loader.exec_module(module=module)
    runtime: _PartitionModule = cast(typ="_PartitionModule", val=module)
    return runtime.Runtime(
        catalog_path=bundle.parent / "data" / "parts" / "fs" / "catalog.json",
    )


def exactus_bundle_cache(*, root: Path) -> Path | None:
    """Materialize catalog components needed for Python/browser activation.

    Args:
        root: Project root searched for the native offline bundle.

    Returns:
        Component cache root, or None for absent or invalid bundles.

    """
    bundle: Path | None = resolve_exactus_tool_bundle(root=root)
    if bundle is None:
        return None
    try:
        runtime: _PartitionRuntime = _partition_runtime(bundle=bundle)
        catalog: _BundleCatalog = cast(
            typ="_BundleCatalog",
            val=loads(
                s=(
                    bundle.parent / "data" / "parts" / "fs" / "catalog.json"
                ).read_text(),
            ),
        )
        for name, component in sorted(catalog["components"].items()):
            if component["metadata"]["env"] or name == "chromium":
                runtime.ensure(name=name)
    except (ImportError, OSError, RuntimeError, ValueError, KeyError):
        return None
    return runtime.components


def exactus_bundle_python_paths(*, root: Path) -> tuple[Path, ...] | None:
    """Materialize every host bundle component and list its Python dirs.

    Args:
        root: Project root searched for the native offline bundle.

    Returns:
        Sorted ``<component>/python`` site directories for the host
        platform, or ``None`` when no bundle is resolvable.

    """
    bundle: Path | None = resolve_exactus_tool_bundle(root=root)
    if bundle is None:
        return None
    try:
        runtime: _PartitionRuntime = _partition_runtime(bundle=bundle)
        catalog: _BundleCatalog = cast(
            typ="_BundleCatalog",
            val=loads(
                s=(
                    bundle.parent / "data" / "parts" / "fs" / "catalog.json"
                ).read_text(),
            ),
        )
        site_dirs: list[Path] = []
        for name in sorted(catalog["components"]):
            site_dir: Path = runtime.ensure(name=name) / "python"
            if site_dir.is_dir():
                site_dirs.append(site_dir)
    except (ImportError, OSError, RuntimeError, ValueError, KeyError):
        return None
    return tuple(sorted(site_dirs))


def _export_bundle_paths(*, cache: Path) -> None:
    """Expose bundled Node modules and executable shims on the process env.

    Args:
        cache: Component cache root to scan for runtime directories.

    """
    path_entries: list[str] = []
    node_paths: list[str] = []
    for component in sorted(cache.iterdir()):
        for relative in ("node/bin", "js/node_modules/.bin"):
            candidate: Path = component / relative
            if candidate.is_dir():
                path_entries.append(str(object=candidate))
        modules_dir: Path = component / "js" / "node_modules"
        if modules_dir.is_dir():
            node_paths.append(str(object=modules_dir))
    if path_entries:
        environ["PATH"] = pathsep.join(
            dict.fromkeys(
                entry
                for entry in [
                    *path_entries,
                    *environ.get("PATH", "").split(sep=pathsep),
                ]
                if entry
            ),
        )
    if node_paths:
        environ["NODE_PATH"] = pathsep.join(
            dict.fromkeys(
                entry
                for entry in [
                    *node_paths,
                    *environ.get("NODE_PATH", "").split(sep=pathsep),
                ]
                if entry
            ),
        )


def activate_exactus_tool_bundle(*, root: Path) -> bool:
    """Expose selected offline Python modules and version-matched Chromium.

    Args:
        root: Project root searched for an external or embedded bundle.

    Returns:
        True when at least one bundled Python component was activated.

    """
    cache: Path | None = exactus_bundle_cache(root=root)
    if cache is None:
        return False
    entries: list[str] = [
        str(object=component / "python")
        for component in sorted(cache.iterdir())
        if (component / "python").is_dir()
    ]
    _export_bundle_paths(cache=cache)
    if not entries:
        return False
    for entry in reversed(entries):
        if entry in sys_path:
            sys_path.remove(entry)
        sys_path.insert(0, entry)
    existing: str = environ.get("PYTHONPATH", "")
    environ["PYTHONPATH"] = pathsep.join(
        dict.fromkeys([*entries, *existing.split(sep=pathsep)]),
    )
    pycache: Path = cache.parent / "pycache"
    attr: str = "pycache_prefix"
    if modules["sys"].pycache_prefix is None:
        setattr(modules["sys"], attr, str(object=pycache))
    _ = environ.setdefault("PYTHONPYCACHEPREFIX", str(object=pycache))
    invalidate_caches()
    browsers: Path = cache / "chromium" / "playwright-browsers"
    if browsers.is_dir():
        environ["PLAYWRIGHT_BROWSERS_PATH"] = str(object=browsers)
        _ = environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_DEPENDENCIES", "1")
    return True


def exactus_tool_prefix(*, tool: str, root: Path) -> tuple[str, ...] | None:
    """Resolve an installed tool or the bundle, or ``None``.

    Args:
        tool: External tool command name.
        root: Project root used for bundle discovery.

    Returns:
        Command prefix for the requested tool, or ``None`` when the tool
        is neither installed nor bundled on a supported platform.

    """
    if (installed := which(cmd=tool)) is not None:
        return (installed,)
    if (bundle := resolve_exactus_tool_bundle(root=root)) is not None:
        return (str(object=bundle), tool)
    return None


def exactus_tool_command(*, tool: str, root: Path) -> tuple[str, ...]:
    """Resolve an installed exactus tool or the offline Linux AMD64 bundle.

    Args:
        tool: External tool command name.
        root: Project root used for bundle discovery.

    Returns:
        Command prefix for the requested tool.

    """
    if (installed := which(cmd=tool)) is not None:
        return (installed,)
    if (bundle := resolve_exactus_tool_bundle(root=root)) is not None:
        return (str(object=bundle), tool)
    return (tool,)


def resolve_source_scope(
    *,
    path: Path,
) -> tuple[Path, tuple[Path, ...] | None]:
    """Resolve a user-supplied scan root into root plus explicit files.

    A file path is treated as a one-file scope rooted at its parent so
    every tool can run whatever analysis it supports on a single file;
    a directory resolves to itself with ``None`` files, meaning the
    caller's normal discovery walk applies.

    Args:
        path: File or directory supplied as the scan root.

    Returns:
        ``(root, files)`` where ``files`` is the explicit one-file scope
        or ``None`` for normal directory discovery.

    """
    resolved: Path = path.expanduser().resolve()
    if resolved.is_file():
        return resolved.parent, (resolved,)
    return resolved, None


def expand_paths(*, root: Path, patterns: tuple[str, ...]) -> tuple[Path, ...]:
    """Expand path/glob arguments relative to root deterministically.

    Args:
        root: Project root for relative glob expansion.
        patterns: Literal paths or glob patterns to expand.

    Returns:
        Existing resolved paths in first-match order, deduplicated.

    """
    expanded: list[Path] = []
    pattern: str
    for pattern in patterns:
        candidate: Path = Path(pattern)
        has_glob: bool = False
        token: str
        for token in "*?[":
            if token in pattern:
                has_glob = True
                break
        if not has_glob:
            matches: tuple[Path, ...] = (
                candidate if candidate.is_absolute() else root / candidate,
            )
        else:
            matches = tuple(root.glob(pattern=pattern))
        path: Path
        for path in matches:
            if not path.exists():
                continue
            expanded.append(path.resolve())
    return tuple(dict.fromkeys(expanded))
