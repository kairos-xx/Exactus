# Copyright (c) 2026
"""Generate ``exactus.vendor.<name>`` shims for bundled distributions."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import (
    contextmanager,
    redirect_stderr,
    redirect_stdout,
    suppress,
)
from importlib import import_module
from importlib.util import find_spec
from io import StringIO
from json import loads
from os import environ
from pathlib import Path
from pkgutil import iter_modules
from shutil import copy2, copytree, ignore_patterns
from sys import stdout
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final
from warnings import catch_warnings, simplefilter

if TYPE_CHECKING:
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        package: Grouped module constant.
        bundle: Grouped module constant.
        skip_names: Grouped module constant.
        skip_vendor: Grouped module constant.
        ignore: Grouped module constant.
        module_overrides: Grouped module constant.
        extra_modules: Grouped module constant.
        swap_only: Grouped module constant.
        drop_common: Grouped module constant.
        unstubbed: Grouped module constant.
        drop_names: Grouped module constant.
        any_names: Grouped module constant.
        builtins: Grouped module constant.
        probe_env_drop: Grouped module constant.
        startup_hooks: Grouped module constant.
        header: Grouped module constant.
        base_imports: Grouped module constant.
        loader_head: Grouped module constant.
        name_stem: Grouped module constant.
        name_literal: Grouped module constant.
        file_literal: Grouped module constant.

    """

    package: Final[Path] = Path(__file__).resolve().parents[2]
    bundle: Final[Path] = package / "bundle"
    skip_names: Final[frozenset[str]] = frozenset({"__pycache__"})
    skip_vendor: Final[frozenset[str]] = frozenset(
        {"basedpyright", "nodejs_wheel", "playwright", "pyrefly", "ruff"},
    )
    ignore: Final[tuple[str, ...]] = (
        ".DS_Store",
        "__pycache__",
        "*.dist-info",
        "*.egg-info",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.pyd",
        "*.dylib",
        "*.dll",
        "*.exe",
        "*.js",
        "*.mjs",
        "*.cjs",
        "*.node",
        "tests",
        "test",
        "bin",
        "dist",
        "driver",
    )
    module_overrides: Final[dict[str, str]] = {
        "jaraco.classes": "jaraco.classes",
        "jaraco_context": "jaraco.context",
        "jaraco_functools": "jaraco.functools",
        "linkify_it_py": "linkify_it",
        "markdown_it_py": "markdown_it",
        "nodejs_wheel_binaries": "nodejs_wheel",
        "opentelemetry_api": "opentelemetry",
        "pillow": "PIL",
        "pyjwt": "jwt",
        "python_multipart": "python_multipart",
        "pyyaml": "yaml",
        "rpds_py": "rpds",
    }
    extra_modules: Final[dict[str, tuple[str, ...]]] = {
        "attrs": ("attr",),
        "python_multipart": ("multipart",),
    }
    swap_only: Final[frozenset[str]] = frozenset(
        {"pytest", "typing_extensions"},
    )
    drop_common: Final[frozenset[str]] = frozenset(
        {"benchmarks", "conftest", "test", "tests"},
    )
    unstubbed: Final[frozenset[str]] = frozenset(
        {
            "basedpyright",
            "jsonschema_specifications",
            "multipart",
            "pycparser",
            "requests_toolbelt",
            "rfc3986",
            "ruff",
        },
    )
    drop_names: Final[dict[str, frozenset[str]]] = {
        "anyio": frozenset({"wait_socket_readable", "wait_socket_writable"}),
        "docutils": frozenset({"TYPE_CHECKING"}),
        "id": frozenset({"Callable", "base64", "binascii", "json"}),
        "jaraco.context": frozenset(
            {
                "Callable",
                "Generator",
                "Iterator",
                "Literal",
                "TYPE_CHECKING",
                "TracebackType",
                "TypeVar",
                "builtins",
                "cast",
                "contextlib",
                "errno",
                "functools",
                "operator",
                "os",
                "platform",
                "shutil",
                "stat",
                "subprocess",
                "sys",
                "tarfile",
                "tempfile",
                "urllib",
            },
        ),
        "markupsafe": frozenset({"cabc", "string", "t"}),
        "pydantic": frozenset(
            {
                "BaseConfig",
                "Extra",
                "PaymentCardNumber",
                "parse_obj_as",
                "root_validator",
                "schema_json_of",
                "schema_of",
                "validator",
            },
        ),
        "pyrefly": frozenset({"importlib"}),
        "requests": frozenset(
            {
                "DependencyWarning",
                "FileModeWarning",
                "NullHandler",
                "RequestsDependencyWarning",
                "charset_normalizer_version",
                "logging",
                "ssl",
                "urllib3",
                "warnings",
            },
        ),
    }
    any_names: Final[dict[str, frozenset[str]]] = {
        "cffi": frozenset({"gen_src"}),
        "charset_normalizer": frozenset({"from_path", "is_binary"}),
        "docutils": frozenset({"namedtuple"}),
        "greenlet": frozenset({"platform"}),
        "jaraco.context": frozenset(
            {
                "CM",
                "Optional",
                "PathLike",
                "T",
                "Tuple",
                "Type",
                "Union",
                "types",
            },
        ),
        "jaraco.functools": frozenset(
            {
                "Callable",
                "TypeVar",
                "chainable",
                "collections",
                "functools",
                "inspect",
                "itertools",
                "more_itertools",
                "none_as",
                "noop",
                "operator",
                "passthrough",
                "time",
                "types",
                "warnings",
            },
        ),
        "jsonschema": frozenset({"benchmarks", "tests"}),
        "more_itertools": frozenset({"UnequalIterablesError", "zip_equal"}),
        "nh3": frozenset({"nh3"}),
        "opentelemetry": frozenset({"propagators", "util"}),
        "psutil": frozenset({"sensors_battery"}),
        "pygments": frozenset({"highlight"}),
        "requests": frozenset({"chardet_version"}),
        "rpds": frozenset({"Stack", "rpds"}),
        "yaml": frozenset(
            {
                "compose",
                "compose_all",
                "emit",
                "io",
                "parse",
                "scan",
                "serialize",
                "serialize_all",
                "warnings",
            },
        ),
    }
    builtins: Final[frozenset[str]] = frozenset(
        dir(import_module(name="builtins")),
    )
    probe_env_drop: Final[frozenset[str]] = frozenset(
        {"COVERAGE_PROCESS_CONFIG", "COVERAGE_PROCESS_START"},
    )
    startup_hooks: Final[frozenset[str]] = frozenset(
        {"pth_file", "sitecustomize", "usercustomize"},
    )
    header: Final[str] = "# Copyright (c) 2026\n"
    base_imports: Final[str] = dedent(
        text=(
            "    from importlib import import_module\n    from importlib.machi"
            "nery import PathFinder\n    from importlib.util import module_fro"
            "m_spec\n    from pathlib import Path\n    from sys import modules"
            " as _modules\n    from sys import path as _path\n    from types i"
            "mport ModuleType\n    "
        ),
    )
    loader_head: Final[str] = dedent(
        text=(
            "    if (\n        _existing := _modules.get(\n            {name}"
            "\n        )\n    ) is not None and Path(\n        getattr(_existi"
            'ng, "__file__", "") or "",\n    ).resolve() != _file:\n        _p'
            "ackage: ModuleType = _existing\n    elif (\n        _spec := Path"
            "Finder.find_spec(\n            fullname=_name,\n            path="
            "[\n                entry\n                for entry in _path\n   "
            '             if Path(entry or ".").resolve() != _file.parent\n   '
            "         ],\n        )\n    ) is not None and (_loader := _spec.l"
            "oader) is not None:\n        _modules[_name] = _package = module_"
            "from_spec(spec=_spec)\n        try:\n            _loader.exec_mod"
            "ule(module=_package)\n        except BaseException:\n            "
            "if _modules.get(_name) is _package:\n                _ = _modules"
            ".pop(_name, None)\n            raise\n    else:\n        _modules"
            '[_name] = _package = import_module(\n            name=f"{__packag'
            'e__}._vendor.{_name}",\n        )\n    _modules[(_alias := __name'
            "__)] = _package\n    "
        ),
    )
    name_stem: Final[str] = (
        "_name := (_file := Path(__file__).resolve()).stem,"
    )
    name_literal: Final[str] = '_name := "{module}",'
    file_literal: Final[str] = "_file: Path = Path(__file__).resolve()\n"


def bundled_distributions(*, bundle: Path) -> list[str]:
    """Collect the union of Python distributions in bundle manifests.

    Args:
        bundle: Bundle root holding platform ``data/bundle.json``
            manifests.

    Returns:
        Sorted distribution names recorded across all platform
            ``data/bundle.json`` manifests.

    """
    names: set[str] = set()
    for manifest in sorted(bundle.glob(pattern="*/**/data/bundle.json")):
        raw: object = loads(s=manifest.read_text())
        if not isinstance(raw, dict):
            continue
        document: dict[str, object] = cast(typ="dict[str, object]", val=raw)
        versions: object = document.get("versions")
        if not isinstance(versions, dict):
            continue
        python: object = cast(typ="dict[str, object]", val=versions).get(
            "python",
        )
        if isinstance(python, (dict, list)):
            names.update(cast(typ="Iterable[str]", val=python))
    return sorted(names)


@contextmanager
def _probing_env() -> Generator[None]:
    """Drop coverage subprocess-startup variables while probing.

    Import-probing a module must never run interpreter-startup side
    effects: when a ``coverage run`` parent exports
    ``COVERAGE_PROCESS_START`` (``patch = subprocess``), importing a
    startup hook such as ``coverage.pth_file`` would start a second,
    never-stopped collector and destroy the outer run's data.

    Yields:
        Nothing; the environment is restored on exit.

    """
    removed: dict[str, str] = {
        var: environ.pop(var)
        for var in Constants.probe_env_drop
        if var in environ
    }
    try:
        yield
    finally:
        environ.update(removed)


def _quiet(*, action: str, imported: ModuleType | None, name: str) -> bool:
    """Return whether an import or attribute access stays quiet.

    Args:
        action: ``"getattr"`` for attribute resolution or
            ``"module"`` for submodule import.
        imported: Module holding the attribute, when applicable.
        name: Attribute or dotted module name.

    Returns:
        ``True`` when the operation succeeds without errors,
        warnings, or emitted output.

    """
    stdout_buffer: StringIO = StringIO()
    stderr_buffer: StringIO = StringIO()
    try:
        with (
            _probing_env(),
            catch_warnings(record=True) as caught,
            redirect_stdout(stdout_buffer),
            redirect_stderr(stderr_buffer),
        ):
            simplefilter(action="always")
            if action == "getattr" and imported is not None:
                getattr(imported, name)
            else:
                import_module(name=name)
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        SystemExit,
        ValueError,
    ):
        return False
    return (
        not caught
        and (not stdout_buffer.getvalue())
        and (not stderr_buffer.getvalue())
    )


def public_names(*, module: str) -> list[str] | None:
    """Return the module's re-exportable public names, or ``None``.

    Args:
        module: Importable module name for this operation.

    Returns:
        Sorted public names verified to resolve, otherwise ``None``
        when the module cannot be imported in the current
        environment.

    """
    try:
        with _probing_env():
            imported: ModuleType = import_module(name=module)
    except (ImportError, OSError, RuntimeError, SystemExit, ValueError):
        return None
    declared: object = getattr(imported, "__all__", None)
    candidates: set[str] = set()
    if isinstance(declared, (list, tuple)):
        names: Iterable[str] = (
            str(object=item)
            for item in cast(typ="Iterable[object]", val=declared)
        )
        candidates.update(names)
    else:
        names = (
            name
            for name in dir(imported)
            if not name.startswith("_") and name != "annotations"
        )
        candidates.update(names)
    submodules: set[str] = set()
    path: object = getattr(imported, "__path__", None)
    if path is not None:
        with suppress(ImportError, OSError):
            submodules.update(
                entry.name
                for entry in iter_modules(
                    path=cast(typ="Iterable[str]", val=path),
                )
                if not entry.name.startswith("_")
            )
    allowed: set[str] = {
        name
        for name in candidates | submodules
        if name.isidentifier()
        and name not in Constants.builtins
        and name not in Constants.startup_hooks
        and (not (name.startswith("__") and name.endswith("__")))
    }
    found: set[str] = {
        name
        for name in allowed & candidates
        if _quiet(action="getattr", imported=imported, name=name)
    }
    found.update(
        name
        for name in allowed & submodules
        if name not in found
        and _quiet(action="module", imported=None, name=f"{module}.{name}")
    )
    return sorted(found)


def _render(
    *,
    dist: str,
    module: str,
    names: list[str] | None,
    shim: str,
) -> str:
    """Render one shim module's source.

    Args:
        dist: Bundled distribution name for the docstring.
        module: Real importable module name.
        names: Public names to re-export, or ``None`` for a
            swap-only shim.
        shim: Filename stem of the emitted shim.

    Returns:
        Complete Python source for the shim file.

    """
    doc: str = f'"""Use installed ``{dist}`` or the bundled copy."""\n'
    dropped: frozenset[str] = (
        Constants.drop_names.get(module, frozenset()) | Constants.drop_common
    )
    kept: list[str] = [name for name in names or [] if name not in dropped]
    untyped: frozenset[str] = (
        frozenset(kept)
        if module in Constants.unstubbed
        else Constants.any_names.get(module, frozenset()) & frozenset(kept)
    )
    typed: list[str] = [name for name in kept if name not in untyped]
    source: str = Constants.header + doc + "\n" + Constants.base_imports
    if shim == module.rsplit(sep=".", maxsplit=1)[-1]:
        name: str = Constants.name_stem
        preamble: str = ""
    else:
        name = Constants.name_literal.format(module=module)
        preamble = Constants.file_literal
    source += "\n" + preamble + Constants.loader_head.replace("{name}", name)
    if typed:
        imported: str = "".join(f"        {name},\n" for name in typed)
        source += (
            f"\nif __name__ != "
            f'"{module}":\n    from {module} import (\n{imported}    )\n'
        )
        exported: str = "".join(f'        "{name}",\n' for name in typed)
        source += "\n    __all__: list[str] = [\n" + exported + "    ]\n"
    return source


def _shim_names(*, dist: str, module: str) -> list[str]:
    """Return shim names emitted for one distribution.

    Args:
        dist: Bundled distribution name.
        module: Real importable module name.

    Returns:
        Distinct flat shim names under ``exactus.vendor``
        (distribution and module spellings).

    """
    names: set[str] = {dist.replace(".", "_")}
    if module == module.lower():
        names.add(module.replace(".", "_"))
    return sorted(names)


def _stage_python_dirs(*, bundle: Path) -> list[Path]:
    """Return per-component staging site-packages directories.

    Args:
        bundle: Bundle root containing staged Python components.

    Returns:
        Sorted ``python`` payload directories from bundle staging.

    """
    return sorted(
        bundle.glob(pattern="*/data/.build-cache/*/components/*/*/python"),
    )


def _package_init(*, directory: Path) -> Path | None:
    """Create a package ``__init__.py`` when one is missing.

    Args:
        directory: Vendored package directory.

    Returns:
        The written file path, or ``None`` when one exists.

    """
    init: Path = directory / "__init__.py"
    if init.is_file():
        return None
    init.write_text(data=Constants.header + '"""Vendored package copy."""\n')
    return init


def _vendor_copy(
    *,
    vendor_dir: Path,
    source: Path,
    parts: tuple[str, ...],
) -> list[Path]:
    """Copy one module file or package tree under ``_vendor``.

    Args:
        vendor_dir: ``_vendor`` destination directory.
        source: Installed module file or package directory.
        parts: Dotted module name components.

    Returns:
        Paths written under ``_vendor``.

    """
    target: Path = vendor_dir.joinpath(*parts)
    written: list[Path] = []
    for index in range(1, len(parts)):
        directory: Path = vendor_dir.joinpath(*parts[:index])
        directory.mkdir(parents=True, exist_ok=True)
        init: Path | None = _package_init(directory=directory)
        if init is not None:
            written.append(init)
    if source.is_dir():
        _ = copytree(
            src=source,
            dst=target,
            ignore=ignore_patterns(*Constants.ignore),
            dirs_exist_ok=True,
        )
        init = _package_init(directory=target)
        if init is not None:
            written.append(init)
        written.append(target)
        return written
    target = target.with_suffix(suffix=".py")
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = copy2(src=source, dst=target)
    written.append(target)
    return written


def _vendor_one(*, vendor_dir: Path, bundle: Path, module: str) -> list[Path]:
    """Vendor a real source copy of ``module`` under ``_vendor``.

    Args:
        vendor_dir: ``_vendor`` destination directory.
        bundle: Bundle root used for staging fallbacks.
        module: Real importable module name.

    Returns:
        Paths written under ``_vendor``; empty when the module's
        source cannot be located in the environment or in bundle
        staging. Binary-wrapper distributions are skipped: their
        payloads are platform-bound and reach users through CLI
        dispatch rather than imports.

    """
    parts: tuple[str, ...] = tuple(module.split(sep="."))
    top: str = parts[0]
    if top in Constants.skip_vendor:
        return []
    root: Path | None = None
    with suppress(ImportError, OSError, ValueError):
        spec: object = find_spec(name=top)
        locations: object = getattr(spec, "submodule_search_locations", None)
        origin: object = getattr(spec, "origin", None)
        if isinstance(locations, Iterable):
            root = Path(
                next(iter(cast(typ="Iterable[str]", val=locations))),
            ).parent
        elif isinstance(origin, str):
            root = Path(origin).parent
    if root is None:
        for stage in _stage_python_dirs(bundle=bundle):
            if (stage / top).exists() or (stage / f"{top}.py").is_file():
                root = stage
                break
    if root is None:
        return []
    source: Path = root.joinpath(*parts)
    if not source.is_dir():
        source = source.with_suffix(suffix=".py")
    if not source.exists():
        return []
    return _vendor_copy(vendor_dir=vendor_dir, source=source, parts=parts)


def generate(*, package: Path) -> list[Path]:
    """Write all shim files under ``<package>/vendor``.

    Args:
        package: ``exactus`` package root (source tree or build
            staging) whose ``bundle`` manifests define the shim set.

    Returns:
        Paths written, sorted.

    """
    shim_dir: Path = package / "vendor"
    vendor_dir: Path = shim_dir / "_vendor"
    bundle: Path = package / "bundle"
    shims: dict[str, tuple[str, str]] = {}
    for dist in bundled_distributions(bundle=bundle):
        module: str = Constants.module_overrides.get(dist, dist)
        for shim in _shim_names(dist=dist, module=module):
            shims[shim] = (dist, module)
        for extra in Constants.extra_modules.get(dist, ()):
            shims[extra] = (extra, extra)
    resolved: dict[str, list[str] | None] = {
        module: None
        if module in Constants.swap_only
        else public_names(module=module)
        for _, module in sorted(set(shims.values()))
    }
    shim_dir.mkdir(parents=True, exist_ok=True)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    init: Path = shim_dir / "__init__.py"
    init.write_text(
        data=Constants.header
        + '"""Generated import shims for bundled distributions."""\n',
    )
    vendor_init: Path = vendor_dir / "__init__.py"
    vendor_init.write_text(
        data=Constants.header
        + '"""Vendored fallback copies of bundled distributions."""\n',
    )
    written: list[Path] = [init, vendor_init]
    for shim, (dist, module) in sorted(shims.items()):
        path: Path = shim_dir / f"{shim}.py"
        path.write_text(
            data=_render(
                dist=dist,
                module=module,
                names=resolved[module],
                shim=shim,
            ),
        )
        written.append(path)
    for module in sorted({module for _, module in shims.values()}):
        written.extend(
            _vendor_one(vendor_dir=vendor_dir, bundle=bundle, module=module),
        )
    return sorted(written)


def main() -> int:
    """Regenerate every shim and print the written file count.

    Returns:
        Process exit status.

    """
    written: list[Path] = generate(package=Constants.package)
    _ = stdout.write(f"wrote {len(written)} shim files\n")
    for path in written:
        _ = stdout.write(f"{path}\n")
    stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
