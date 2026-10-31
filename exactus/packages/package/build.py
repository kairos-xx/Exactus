#!/usr/bin/env python3
# Copyright (c) 2026
"""Build the distributable artifacts of the exactus.

With no arguments all artifacts are produced: the executable,
extensionless ``exactus`` zipapp at ``bin/release/exactus_all/exactus``, a
``build/``
directory holding that zipapp unzipped — the ``exactus`` package plus
the ``__main__.py`` entry stub, runnable directly — and a ``TREE.txt``
rendering of the project tree — the same filtered file set
``package.py`` archives (see ``collect.py``).

``EXACTUS_RESULTS/`` and its complete subtree are included in ``TREE.txt``
by default. Use ``--no-exactus`` to exclude ``EXACTUS_RESULTS/`` from the
rendered tree.

``--check`` builds only the root pyz, ``--build`` builds only the
``build/`` dist directory, and ``--tree`` writes only ``TREE.txt``;
passing all three is the same as passing none.

``[tool.build]`` in ``pyproject.toml`` presets any flag; ``--target`` on
the command line wins over its ``targets``/``target`` entries. The
``[tool.build.exec]`` subtable scopes ``targets``/``target`` to the pyz
alone — ``--exec-target`` overrides it, and without either the pyz
inherits the general ``[tool.build]`` filter.

Native ``zstd_portable`` archives are sourced from
``<project-root>/bin/zstd_portable`` and copied into every staged bundle
target containing the ``zstd_portable`` package. Selection is based on
the bundle target's operating system and architecture. Linux libc does
not affect zstd archive selection.

"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import partial
from hashlib import sha256
from json import loads as json_loads
from pathlib import Path
from shutil import copy2, copytree, rmtree
from stat import S_IRWXU
from sys import path as sys_path
from tempfile import TemporaryDirectory
from textwrap import dedent
from tomllib import load as load_toml
from typing import TYPE_CHECKING, Final, cast, final
from zipapp import create_archive

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[3]))
    sys_path.insert(0, str(object=Path(__file__).resolve().parent.parent))
from exactus.bundle.content import write_content
from exactus.bundle.freshness import SIGNATURE_NAME, render_signature
from exactus.packages.package.bundle import Constants as _GroupFinalConstants
from exactus.packages.package.inventory import partition_excluded, render_tree
from exactus.packages.package.inventory_cli import pretty_parser
from exactus.packages.package.shims import generate
from exactus.packages.zstd_portable import Constants as ZstdConstants
from exactus.tools.common.conflict_copies import clear_conflict_copies
from exactus.tools.common.directory_inventory import heal_directory

if TYPE_CHECKING:
    from _hashlib import HASH
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable
type TomlValue = (
    str
    | int
    | float
    | bool
    | datetime
    | date
    | time
    | list[TomlValue]
    | dict[str, TomlValue]
)
type TomlTable = dict[str, TomlValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        package: Grouped module constant.
        bundle: Grouped module constant.
        bin_zstd_portable: Grouped module constant.
        zstd_archives: Grouped module constant.
        check: Grouped module constant.
        dist: Grouped module constant.
        tree: Grouped module constant.
        excluded_dirs: Grouped module constant.
        main_stub: Grouped module constant.
        check_readme_template: Grouped module constant.
        dist_readme: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[3]
    package: Final[Path] = root / "exactus"
    bundle: Final[Path] = package / "bundle"
    bin_zstd_portable: Final[Path] = root / "bin" / "zstd_portable"
    zstd_archives: Final[dict[tuple[str, str], str]] = {
        ("linux", "amd64"): "linux-x86_64.zip",
        ("linux", "x86_64"): "linux-x86_64.zip",
        ("linux", "arm64"): "linux-arm64.zip",
        ("linux", "aarch64"): "linux-arm64.zip",
        ("macos", "amd64"): "macos-universal2.zip",
        ("macos", "x86_64"): "macos-universal2.zip",
        ("macos", "arm64"): "macos-universal2.zip",
        ("macos", "aarch64"): "macos-universal2.zip",
        ("windows", "amd64"): "windows-x86_64.zip",
        ("windows", "x86_64"): "windows-x86_64.zip",
        ("windows", "x86"): "windows-x86.zip",
        ("windows", "i386"): "windows-x86.zip",
        ("windows", "i686"): "windows-x86.zip",
        ("windows", "arm64"): "windows-arm64.zip",
        ("windows", "aarch64"): "windows-arm64.zip",
    }
    check: Final[Path] = root / "bin" / "release" / "exactus_all" / "exactus"
    dist: Final[Path] = root / "build"
    tree: Final[Path] = root / "TREE.txt"
    excluded_dirs: Final[frozenset[str]] = frozenset(
        {"__pycache__", "EXACTUS_RESULTS"},
    )
    main_stub: Final[str] = dedent(
        text=(
            '\n        """Pyz entry point dispatching to the exactus."""\n\n '
            "       from os import environ, execv, pathsep\n        from "
            "pathlib import Path\n        from shutil import which\n        "
            "from sys import argv, executable\n\n        archive: str = "
            "str(object=Path(argv[0]).resolve())\n        python_path: "
            "list[str] = [archive]\n        if existing_python_path := "
            'environ.get("PYTHONPATH", ""):\n            python'
            "_path.extend(existing_python_path.split(sep=pathsep))\n       "
            ' environ["PYTHONPATH"] = pathsep.join(dict.fromkeys(python'
            "_path))\n\n        from exactus.__main__ import main\n        "
            "from exactus.tools.common.cli import resolve_exactus_tool"
            "_bundle\n\n\n        def preferred_python() -> str:\n            "
            '"""Return an interpreter matching the bundled wheels\' ABI.\n\n '
            "           Bundled components ship CPython-tagged "
            "extensions, so tool\n            dispatch must run under the "
            "project interpreter when known,\n            else a PATH "
            "python matching the build tag, else whatever\n            "
            'launched this archive.\n\n            """\n            if '
            'candidate := environ.get("EXACTUS_PROJECT_PYTHON"):\n         '
            "       return candidate\n            return "
            'which(cmd="python3.13") or executable\n\n        BUNDLED'
            "_TOOLS: frozenset[str] = frozenset({\n            "
            '"basedpyright",\n            "build",\n            '
            '"coverage",\n            "eslint",\n            "exactus'
            '-mcp",\n            "exactus-mcp-wakeup",\n            '
            '"htmlhint",\n            "jinja2",\n            "jslint",\n     '
            '       "mutmut",\n            "node",\n            "pillow",\n  '
            '          "playwright",\n            "prettier",\n            '
            '"pyrefly",\n            "pytest",\n            "ruff",\n        '
            '    "stylelint",\n            "tsc",\n            "twine",\n    '
            '        "uvicorn",\n        })\n\n        if len(argv) > 1 and '
            "argv[1] in BUNDLED_TOOLS:\n            bundle: Path | None = "
            "resolve_exactus_tool_bundle(root=Path.cwd())\n            if "
            'bundle is None:\n                message: str = "No '
            'compatible bundled toolchain is available"\n                '
            "raise SystemExit(message)\n            interpreter: str = "
            "preferred_python()\n            execv(interpreter, "
            "[interpreter, str(bundle), *argv[1:]])\n\n        raise "
            "SystemExit(main())\n        "
        ),
    ).removeprefix("\n")
    check_readme_template: Final[Path] = (
        Path(__file__).resolve().parent / "templates" / "readme_template.md"
    )
    dist_readme: Final[str] = dedent(
        text=(
            "    # `build/`\n    \n    Generated dist directory produced by `p"
            "ython exactus.packages.package --build --build`.\n    \n    The `"
            "bin/release/exactus_all/exactus` zipapp unzipped — the `exactus/`"
            " package plus\n    the `__main__.py` entry stub, runnable without"
            " bundling:\n    \n    - `python build/` — same CLI as the `bin/re"
            "lease` pyz.\n    - `python -m exactus` — works from inside this d"
            "irectory.\n    "
        ),
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class BuildFileConfig:
    """``[tool.build]`` defaults layered under command-line options.

    Attributes:
        build: Build only the ``build/`` dist directory.
        check: Build only the ``bin/release/exactus_all/exactus`` zipapp.
        exec_target: Single pyz-scoped target or group name.
        exec_targets: Bundle targets and aliases staged into the pyz.
        no_exactus: Exclude ``EXACTUS_RESULTS`` from ``TREE.txt``.
        target: Single general bundle target or group name.
        targets: General bundle targets and group aliases.
        tree: Write only ``TREE.txt``.

    """

    build: bool = False
    check: bool = False
    exec_target: str | None = None
    exec_targets: tuple[str, ...] = ()
    no_exactus: bool = False
    target: str | None = None
    targets: tuple[str, ...] = ()
    tree: bool = False


def build_file_config(*, path: Path) -> BuildFileConfig:
    """Read ``[tool.build]`` defaults from a ``pyproject.toml`` file.

    Args:
        path: Candidate ``pyproject.toml`` location.

    Returns:
        Parsed build defaults.

    Raises:
        TypeError: A configured key holds a value of the wrong type.

    """
    if not path.is_file():
        return BuildFileConfig()
    with path.open(mode="rb") as stream:
        document: TomlTable = cast(typ="TomlTable", val=load_toml(stream))
    tools: TomlValue = document.get("tool", {})
    if not isinstance(tools, dict):
        return BuildFileConfig()
    section: TomlValue = cast(typ="TomlTable", val=tools).get("build", {})
    if not isinstance(section, dict):
        return BuildFileConfig()
    table: TomlTable = cast(typ="TomlTable", val=section)
    target, targets = _target_keys(table=table, source="[tool.build]")
    exec_section: TomlValue = table.get("exec", {})
    if not isinstance(exec_section, dict):
        msg: str = "[tool.build.exec] must be a table"
        raise TypeError(msg)
    exec_target, exec_targets = _target_keys(
        table=cast(typ="TomlTable", val=exec_section),
        source="[tool.build.exec]",
    )
    flags: dict[str, bool] = {}
    for key in ("exactus", "check", "build", "tree", "no-exactus"):
        raw: TomlValue = table.get(key, False)
        if not isinstance(raw, bool):
            msg = f"[tool.build] {key} must be a boolean"
            raise TypeError(msg)
        flags[key] = raw
    return BuildFileConfig(
        build=flags["build"],
        check=flags["exactus"] or flags["check"],
        exec_target=exec_target,
        exec_targets=exec_targets,
        no_exactus=flags["no-exactus"],
        target=target,
        targets=targets,
        tree=flags["tree"],
    )


def _target_keys(
    *,
    table: TomlTable,
    source: str,
) -> tuple[str | None, tuple[str, ...]]:
    """Read the ``target``/``targets`` pair from one config table.

    Args:
        table: Decoded TOML table.
        source: Table name used in error messages.

    Returns:
        The single target name and targets list.

    Raises:
        TypeError: A configured key has an invalid type.

    """
    names: TomlValue = table.get("targets", [])
    if not isinstance(names, list) or not all(
        isinstance(name, str) for name in names
    ):
        msg: str = f"{source} targets must be a list of strings"
        raise TypeError(msg)
    target: TomlValue | None = table.get("target")
    if target is not None and (not isinstance(target, str)):
        msg = f"{source} target must be a string"
        raise TypeError(msg)
    return (target, tuple(name for name in names if isinstance(name, str)))


def kept_bundle_leaves(*, targets: list[str] | None) -> frozenset[Path] | None:
    """Resolve target requests into kept bundle directories.

    Args:
        targets: Requested target names, aliases or ``all``.

    Returns:
        Package-relative bundle leaves to keep, or ``None`` when every
        target remains in the build.

    """
    if not targets or "all" in targets:
        return None
    names: set[str] = {
        member
        for name in targets
        for member in _GroupFinalConstants.target_groups.get(name, (name,))
    }
    return frozenset(
        Path("bundle").joinpath(*name.split(sep="-")) for name in names
    )


def _kept_leaf(*, candidate: Path, leaf: Path) -> bool:
    """Return whether ``leaf`` retains ``candidate``.

    Args:
        candidate: Package-relative staged path.
        leaf: Bundle leaf retained by target filtering.

    Returns:
        Whether the candidate belongs to the retained target.

    """
    return (
        candidate == leaf
        or leaf.is_relative_to(candidate)
        or candidate.is_relative_to(leaf)
        or (
            candidate.parent == leaf.parent
            and candidate.name == f"{leaf.name}.update"
        )
    )


def _ignore(
    directory: str,
    names: list[str],
    *,
    kept: frozenset[Path] | None = None,
) -> set[str]:
    """Filter excluded files and unselected bundle targets.

    Args:
        directory: Directory traversed by ``copytree``.
        names: Immediate child names.
        kept: Bundle leaves retained by target filtering.

    Returns:
        Names excluded from staging.

    """
    current: Path = Path(directory)
    excluded: set[str] = {
        name
        for name in names
        if name in Constants.excluded_dirs
        or name == ".DS_Store"
        or name.endswith((".pyc", ".pyo"))
        or ((current / name).is_dir() and name.startswith("."))
        or partition_excluded(directory=current, name=name)
    }
    if kept is None:
        return excluded
    relative: Path = (
        Path(directory).resolve().relative_to(Constants.package.resolve())
    )
    if not relative.parts or relative.parts[0] != "bundle":
        return excluded
    systems: frozenset[str] = frozenset(
        name.split(sep="-", maxsplit=1)[0]
        for name in _GroupFinalConstants.targets
    )
    for name in names:
        candidate: Path = relative / name
        if (
            not (Path(directory) / name).is_dir()
            or candidate.parts[1] not in systems
        ):
            continue
        if not any(
            _kept_leaf(candidate=candidate, leaf=leaf) for leaf in kept
        ):
            excluded.add(name)
    return excluded


def _zstd_archive_name(*, system: str, architecture: str) -> str:
    """Resolve the native zstd archive for a bundle target.

    Args:
        system: Bundle operating-system identifier.
        architecture: Bundle CPU architecture identifier.

    Returns:
        Native archive filename.

    Raises:
        ValueError: No native archive mapping exists for the target.

    """
    try:
        return Constants.zstd_archives[system, architecture]
    except KeyError as exc:
        msg: str = (
            f"No zstd portable archive is configured "
            f"for {system}/{architecture}"
        )
        raise ValueError(msg) from exc


def _stage_zstd_portable(*, staging: Path) -> None:
    """Stage native zstd archives into every applicable bundle target.

    The bundle layout is expected to use:

    ``bundle/<system>/<variant>/<architecture>/zstd_portable``

    For Linux, ``variant`` may distinguish ``glibc`` from ``musl``.
    That distinction deliberately does not participate in native zstd
    archive selection because both variants use the same portable
    executable for a given CPU architecture.

    macOS uses the same ``macos-universal2.zip`` payload for both Intel
    and Apple Silicon bundle targets.

    Args:
        staging: Distribution staging root containing ``exactus/``.

    Raises:
        FileNotFoundError: A mapped native archive does not exist.
        ValueError: A staged target has no native archive mapping.

    """
    bundle: Path = staging / "exactus" / "bundle"
    if not bundle.is_dir():
        return
    zstd_packages: list[Path] = sorted(
        path
        for path in bundle.glob(pattern="*/*/*/zstd_portable")
        if path.is_dir()
    )
    expected_relative_parts: int = 4
    for zstd_package in zstd_packages:
        relative: Path = zstd_package.relative_to(bundle)
        if len(relative.parts) != expected_relative_parts:
            msg: str = f"Unexpected zstd bundle layout: {zstd_package}"
            raise ValueError(msg)
        system: str = relative.parts[0]
        architecture: str = relative.parts[2]
        archive_name: str = _zstd_archive_name(
            system=system,
            architecture=architecture,
        )
        source: Path = Constants.bin_zstd_portable / archive_name
        if not source.is_file():
            msg = (
                f"Missing zstd portable archive for "
                f"{system}/{architecture}: {source}"
            )
            raise FileNotFoundError(msg)
        destination_directory: Path = zstd_package / "bin"
        destination_directory.mkdir(parents=True, exist_ok=True)
        destination: Path = destination_directory / archive_name
        _ = copy2(src=source, dst=destination)


def _hash_file(*, path: Path) -> str:
    """Return the SHA-256 digest of a file using bounded memory.

    Args:
        path: File to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest.

    """
    digest: HASH = sha256()
    with path.open(mode="rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _catalog_packs(*, path: Path) -> TomlTable:
    """Read and validate a bundle catalog pack table.

    Args:
        path: Catalog JSON file.

    Returns:
        Typed pack table.

    Raises:
        TypeError: The catalog or its pack table is malformed.

    """
    document: TomlValue = cast(
        typ="TomlValue",
        val=json_loads(s=path.read_text(encoding="utf-8")),
    )
    if not isinstance(document, dict):
        msg: str = f"Invalid bundle catalog: {path}"
        raise TypeError(msg)
    packs: TomlValue = document.get("packs", {})
    if not isinstance(packs, dict):
        msg = f"Bundle catalog has no packs table: {path}"
        raise TypeError(msg)
    return packs


def _pack_record(
    *,
    catalog: Path,
    pack_id: str,
    value: TomlValue,
) -> tuple[str, str, int]:
    """Validate and extract one bundle pack record.

    Args:
        catalog: Catalog containing the record.
        pack_id: Content-addressed pack identifier.
        value: Decoded pack record.

    Returns:
        Relative path, SHA-256 digest and expected byte count.

    Raises:
        TypeError: The pack record is malformed.

    """
    if not isinstance(value, dict):
        msg: str = f"Invalid pack record {pack_id} in {catalog}"
        raise TypeError(msg)
    relative: TomlValue = value.get("path", "")
    expected_sha256: TomlValue = value.get("sha256", "")
    expected_bytes: TomlValue = value.get("bytes", -1)
    if (
        not isinstance(relative, str)
        or not isinstance(expected_sha256, str)
        or (not isinstance(expected_bytes, int))
        or isinstance(expected_bytes, bool)
    ):
        msg = f"Incomplete pack record {pack_id} in {catalog}"
        raise TypeError(msg)
    return (relative, expected_sha256, expected_bytes)


def _validate_pack(
    *,
    catalog: Path,
    root: Path,
    pack_id: str,
    record: TomlValue,
) -> None:
    """Validate one immutable bundle pack.

    Args:
        catalog: Catalog referencing the pack.
        root: Partition filesystem root.
        pack_id: Content-addressed pack identifier.
        record: Decoded pack metadata.

    Raises:
        ValueError: The pack is absent or does not match its metadata.

    """
    relative, expected_sha256, expected_bytes = _pack_record(
        catalog=catalog,
        pack_id=pack_id,
        value=record,
    )
    pack: Path = root / relative
    if not pack.is_file():
        msg: str = f"Missing bundle pack {pack_id}: {pack}"
        raise ValueError(msg)
    if pack.stat().st_size != expected_bytes:
        msg = f"Bundle pack size mismatch {pack_id}: {pack}"
        raise ValueError(msg)
    if _hash_file(path=pack) != expected_sha256:
        msg = f"Bundle pack hash mismatch {pack_id}: {pack}"
        raise ValueError(msg)


def _validate_catalog_packs(*, catalog: Path) -> None:
    """Validate every immutable pack referenced by one catalog.

    Args:
        catalog: Catalog JSON file.

    """
    root: Path = (
        catalog.parent.parent
        if catalog.parent.name == "catalogs"
        else catalog.parent
    )
    packs: TomlTable = _catalog_packs(path=catalog)
    for pack_id, record in packs.items():
        _validate_pack(
            catalog=catalog,
            root=root,
            pack_id=pack_id,
            record=record,
        )


def _validate_staged_bundle_packs(*, staging: Path) -> None:
    """Validate all catalogs in the exact staged bundle.

    Both active catalogs and retained rollback catalogs are checked
    after target filtering and native-payload staging.

    Args:
        staging: Distribution staging root containing ``exactus/``.

    """
    bundle: Path = staging / "exactus" / "bundle"
    if not bundle.is_dir():
        return
    catalogs: list[Path] = sorted(
        bundle.glob(pattern="**/data/parts/fs/catalog.json"),
    )
    catalogs.extend(
        sorted(bundle.glob(pattern="**/data/parts/fs/catalogs/*.json")),
    )
    for catalog in catalogs:
        _validate_catalog_packs(catalog=catalog)


def _stage_package(
    *,
    staging: Path,
    kept: frozenset[Path] | None = None,
    self_test: bool = False,
) -> None:
    """Copy the filtered package and entry stub into staging.

    Native zstd payloads are copied after the Python package tree so
    that the executable cannot accidentally depend on native payloads
    already present in a source bundle leaf.

    Args:
        staging: Directory receiving the distribution tree.
        kept: Bundle leaves retained by target filtering.
        self_test: Write the ``SELF_TEST`` marker enabling the
            ``self_test`` diagnostic on the built executable.

    """
    _ = copytree(
        src=Constants.package,
        dst=staging / "exactus",
        ignore=partial(_ignore, kept=kept),
    )
    _ = generate(package=staging / "exactus")
    _stage_zstd_portable(staging=staging)
    _validate_staged_bundle_packs(staging=staging)
    _ = write_content(root=staging / "exactus" / "bundle")
    _ = (staging / "exactus" / SIGNATURE_NAME).write_bytes(
        data=render_signature(exactus_dir=staging / "exactus"),
    )
    if self_test:
        _ = (staging / "exactus" / "SELF_TEST").write_text(
            data="enabled\n",
            encoding="utf-8",
        )
    _ = (staging / "__main__.py").write_text(
        data=Constants.main_stub,
        encoding="utf-8",
    )


def _version_maps(
    *,
    versions: TomlTable,
) -> tuple[dict[str, str], dict[str, str]]:
    """Normalize a component version map to lowercase lookups.

    Args:
        versions: Component ``{"python": ..., "node": ...}`` map.

    Returns:
        Lowercase package-name to version maps for Python and Node.

    """
    python: TomlValue = versions.get("python", {})
    node: TomlValue = versions.get("node", {})
    return (
        {
            str(object=k).lower(): str(object=v)
            for k, v in cast(
                typ="dict[object, object]",
                val=python if isinstance(python, dict) else {},
            ).items()
        },
        {
            str(object=k).lower(): str(object=v)
            for k, v in cast(
                typ="dict[object, object]",
                val=node if isinstance(node, dict) else {},
            ).items()
        },
    )


def _spec_version(
    *,
    name: str,
    module: str,
    kind: str,
    py: dict[str, str],
    nd: dict[str, str],
) -> str:
    """Resolve a version from a tool declaration's dispatch fields.

    Args:
        name: Declared ``target`` field.
        module: Declared ``module`` field.
        kind: Declared tool kind.
        py: Lowercase Python package versions.
        nd: Lowercase Node package versions.

    Returns:
        The resolved version, or ``""`` when not attributable.

    """
    if module and module.lower() in py:
        return py[module.lower()]
    if kind == "python-module" and name.lower() in py:
        return py[name.lower()]
    if kind == "js-entry":
        package: str = name.split(sep="/", maxsplit=1)[0].lower()
        if package in nd:
            return nd[package]
    for token in name.replace(";", " ").split():
        module_name: str = token.removeprefix("from").removeprefix("import")
        module_name = module_name.split(sep=".", maxsplit=1)[0].strip().lower()
        for candidate in (token.lower(), module_name):
            if candidate in py:
                return py[candidate]
    if name:
        matches: list[str] = [
            version
            for package, version in py.items()
            if package.startswith(name.lower())
        ]
        if matches:
            return matches[0]
    return ""


def _required_versions(
    *,
    components: TomlTable,
    metadata: TomlTable,
) -> tuple[str, TomlValue | None]:
    """Resolve the versions of a component's last requirement.

    Args:
        components: Catalog ``components`` table.
        metadata: Component metadata holding ``requires``.

    Returns:
        Required component name and its version map, when resolvable.

    """
    name: str = ""
    versions: TomlValue | None = None
    requires: TomlValue = metadata.get("requires", [])
    if isinstance(requires, list):
        for requirement in requires:
            if isinstance(requirement, str):
                dependency: TomlValue = components.get(requirement, "")
                if isinstance(dependency, dict):
                    inner: TomlValue = dependency.get("metadata", "")
                    if isinstance(inner, dict):
                        versions = inner.get("versions")
                        name = requirement
    return (name, versions)


def _tool_version(
    *,
    tool: str,
    spec: TomlTable,
    versions: TomlTable,
    requires: tuple[str, TomlValue | None] = ("", None),
    project: str = "",
) -> str:
    """Resolve one tool's bundled package version.

    Args:
        tool: Tool name declared in catalog metadata.
        spec: Tool declaration from catalog metadata.
        versions: Component ``{"python": ..., "node": ...}`` map.
        requires: ``(name, versions)`` of a component the tool's
            component requires, used for binary payloads such as
            browsers whose version tracks the required package.
        project: Project version for tools that dispatch to the
            ``exactus`` package itself.

    Returns:
        The resolved version, or ``""`` when not attributable.

    """
    py: dict[str, str]
    nd: dict[str, str]
    py, nd = _version_maps(versions=versions)
    target: TomlValue = spec.get("target", "")
    module: TomlValue = spec.get("module", "")
    name: str = target if isinstance(target, str) else ""
    own: str = module if isinstance(module, str) and module else name
    if own.startswith("exactus.") and project:
        return project
    resolved: str = _spec_version(
        name=name,
        module=module if isinstance(module, str) else "",
        kind=str(object=spec.get("kind", "")),
        py=py,
        nd=nd,
    )
    if resolved:
        return resolved
    normalized: str = tool.replace("-", "_").lower()
    normalized_name: str = name.replace("-", "_").lower()
    matches: list[str] = [
        version
        for package, version in py.items()
        if package.startswith(normalized) or package == normalized_name
    ]
    if matches:
        return matches[0]
    requires_component: str
    requires_versions: TomlValue | None
    requires_component, requires_versions = requires
    resolved = ""
    if isinstance(requires_versions, dict):
        required: TomlValue = requires_versions.get("python", {})
        if isinstance(required, dict):
            primary: str = requires_component.replace("-", "_").lower()
            if primary in required:
                resolved = str(object=required[primary])
        if not resolved:
            resolved = _tool_version(
                tool=tool,
                spec=spec,
                versions=requires_versions,
                project=project,
            )
    return resolved


def _catalog_tools(*, catalog: Path, project: str = "") -> dict[str, str]:
    """Collect declared tools and versions from one bundle catalog.

    Args:
        catalog: ``data/parts/fs/catalog.json`` of one bundle target.
        project: Project version applied to ``exactus.*`` modules.

    Returns:
        Tool name to bundled version mapping.

    """
    tools: dict[str, str] = {}
    if not catalog.is_file():
        return tools
    document: TomlValue = json_loads(s=catalog.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return tools
    components: TomlValue = document.get("components", {})
    if not isinstance(components, dict):
        return tools
    for component in components.values():
        if not isinstance(component, dict):
            continue
        metadata: TomlValue = component.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        declared: TomlValue = metadata.get("tools", {})
        versions: TomlValue = metadata.get("versions", {})
        if not isinstance(declared, dict) or not isinstance(versions, dict):
            continue
        requires: tuple[str, TomlValue | None] = _required_versions(
            components=components,
            metadata=metadata,
        )
        for tool, spec in declared.items():
            if tool in tools or not isinstance(spec, dict):
                continue
            tools[tool] = _tool_version(
                tool=tool,
                spec=spec,
                versions=versions,
                requires=requires,
                project=project,
            )
    return tools


def _bundled_tools(
    *,
    leaves: list[str],
    node_version: str,
    project: str = "",
) -> dict[str, str]:
    """Collect every embedded tool and its version from catalogs.

    Args:
        leaves: Embedded bundle target names (``macos-arm64`` style).
        node_version: Bundled Node.js runtime version.
        project: Project version applied to ``exactus.*`` modules.

    Returns:
        Tool name to bundled version mapping.

    """
    tools: dict[str, str] = {}
    for leaf in leaves:
        catalog: Path = (
            Constants.package
            / "bundle"
            / Path(*leaf.split(sep="-"))
            / "data"
            / "parts"
            / "fs"
            / "catalog.json"
        )
        for tool, version in _catalog_tools(
            catalog=catalog,
            project=project,
        ).items():
            tools.setdefault(tool, version)
    if "node" in tools:
        tools["node"] = node_version
    for tool in ("zstd", "zstd-cli"):
        if tool in tools:
            tools[tool] = ZstdConstants.version
    return tools


def _write_manifest(
    *,
    target: Path,
    kept: frozenset[Path] | None,
    self_test: bool,
) -> None:
    """Write ``MANIFEST.md`` describing the built executable.

    Args:
        target: Destination executable just produced.
        kept: Bundle leaves retained by target filtering.
        self_test: Whether the ``SELF_TEST`` marker was staged.

    """
    if kept is None:
        leaves: list[str] = sorted(_GroupFinalConstants.targets)
    else:
        leaves = sorted("-".join(leaf.parts[1:]) for leaf in kept)
    version: TomlValue = "unknown"
    node_version: str = "22.21.1"
    pyproject: Path = Constants.root / "pyproject.toml"
    if pyproject.is_file():
        with pyproject.open(mode="rb") as stream:
            document: TomlTable = cast(typ="TomlTable", val=load_toml(stream))
        project: TomlValue = document.get("project", {})
        if isinstance(project, dict):
            version = project.get("version", "unknown")
        tool: TomlValue = document.get("tool", {})
        if isinstance(tool, dict):
            bundle_section: TomlValue = tool.get("bundle", {})
            if isinstance(bundle_section, dict):
                configured: TomlValue = bundle_section.get(
                    "node-version",
                    "22.21.1",
                )
                if isinstance(configured, str):
                    node_version = configured
    rows: str = "".join(f"- `{leaf}`\n" for leaf in leaves)
    tools: dict[str, str] = _bundled_tools(
        leaves=leaves,
        node_version=node_version,
        project=version if isinstance(version, str) else "",
    )
    tool_rows: str = "".join(
        (
            f"| `{tool}` | `{version or '—'}` |\n"
            for tool, version in sorted(tools.items())
        ),
    )
    _ = (target.parent / "MANIFEST.md").write_text(
        data=(
            f"# `{target.name}` — {
                target.parent.name
            }\n\n| Field | Value |\n| --- | --- |\n| Version | `{
                version
            }` |\n| File | `{target.name}` |\n| Size | {
                target.stat().st_size
            } bytes |\n| SHA-256 | `{
                _hash_file(path=target)
            }` |\n| Self-test | {
                ('enabled' if self_test else 'disabled')
            } |\n\n## Embedded bundle targets\n\n"
        )
        + (rows or "- none\n")
        + "\n## Bundled tools\n\n"
        + (
            "| Tool | Version |\n| --- | --- |\n" + tool_rows
            if tool_rows
            else "- none\n"
        ),
        encoding="utf-8",
    )


def build_check(
    *,
    target: Path,
    kept: frozenset[Path] | None = None,
    self_test: bool = False,
) -> None:
    """Build the executable zipapp.

    Args:
        target: Destination executable.
        kept: Bundle leaves retained by target filtering.
        self_test: Enable ``self_test`` on the built executable.

    """
    with TemporaryDirectory(
        prefix="exactus-package-",
        ignore_cleanup_errors=True,
    ) as temporary:
        staging: Path = Path(temporary)
        _stage_package(staging=staging, kept=kept, self_test=self_test)
        target.parent.mkdir(parents=True, exist_ok=True)
        readme: Path = target.parent.parent / "README.md"
        if not readme.is_file():
            _ = readme.write_text(
                data=Constants.check_readme_template.read_text(
                    encoding="utf-8",
                ).replace("{name}", target.parent.parent.name),
                encoding="utf-8",
            )
        with TemporaryDirectory(
            prefix=".exactus-out-",
            dir=target.parent.parent,
            ignore_cleanup_errors=True,
        ) as output_staging:
            temporary_target: Path = Path(output_staging) / "exactus"
            create_archive(
                source=staging,
                target=temporary_target,
                interpreter="/usr/bin/env python3",
                compressed=True,
            )
            _ = temporary_target.replace(target=target)
    target.chmod(mode=493)
    _write_manifest(target=target, kept=kept, self_test=self_test)
    heal_directory(
        directory=target.parent.parent,
        entries=[
            entry
            for entry in sorted(target.parent.parent.iterdir())
            if not entry.name.startswith(".")
        ],
    )


def _rmtree_retry(
    func: Callable[[str], None],
    path: str,
    _exc: BaseException,
) -> None:
    """Retry a failed ``rmtree`` operation.

    Finder may create ``.DS_Store`` files between directory scanning and
    removal. Read-only staged artifacts may also need owner permissions
    restored before retrying.

    Args:
        func: Removal operation to retry.
        path: Entry whose removal failed.
        _exc: Original exception supplied by ``rmtree``.

    """
    entry: Path = Path(path)
    candidate: Path
    for candidate in (entry, entry.parent):
        with suppress(OSError):
            candidate.chmod(mode=S_IRWXU)
    if entry.is_dir():
        child: Path
        for child in entry.iterdir():
            if child.is_dir() and (not child.is_symlink()):
                rmtree(path=child, onexc=_rmtree_retry)
            else:
                child.unlink(missing_ok=True)
    func(path)


def build_dist(
    *,
    kept: frozenset[Path] | None = None,
    self_test: bool = False,
) -> None:
    """Build the unzipped ``build/`` distribution.

    Args:
        kept: Bundle leaves retained by target filtering.
        self_test: Enable ``self_test`` on the built executable.

    """
    with TemporaryDirectory(
        prefix="exactus-dist-",
        ignore_cleanup_errors=True,
    ) as temporary:
        staging: Path = Path(temporary)
        _stage_package(staging=staging, kept=kept, self_test=self_test)
        if Constants.dist.exists():
            rmtree(path=Constants.dist, onexc=_rmtree_retry)
        _ = copytree(src=staging, dst=Constants.dist)
    _ = (Constants.dist / "README.md").write_text(
        data=Constants.dist_readme,
        encoding="utf-8",
    )
    heal_directory(
        directory=Constants.dist,
        entries=sorted(Constants.dist.iterdir()),
    )


def build_tree(*, target: Path, include_exactus_results: bool = True) -> None:
    """Write the filtered project tree.

    Args:
        target: Destination tree file.
        include_exactus_results: Include ``EXACTUS_RESULTS``.

    """
    _ = target.write_text(
        data=render_tree(
            root=Constants.root,
            include_exactus_results=include_exactus_results,
        ),
        encoding="utf-8",
    )


def create_parser() -> ArgumentParser:
    """Create the build CLI parser.

    Returns:
        Configured parser.

    """
    parser: ArgumentParser = pretty_parser(
        prog="python -m exactus.packages.package --build",
        description=(
            "Build the toolkit's distributable artifacts; no "
            "artifact flags builds all three. EXACTUS_RESULTS is "
            "included in the project tree by default."
        ),
        epilog=(
            dedent(
                text=(
                    "    examples:\n      python -m exactus.packages.packa"
                    "ge --build\n      python -m exactus.packages.package "
                    "--build --no-exactus\n      python -m exactus.package"
                    "s.package --build --check\n      python -m exactus.pa"
                    "ckages.package --build --build\n      python -m exact"
                    "us.packages.package --build --tree\n      python -m e"
                    "xactus.packages.package --build --build --target amd6"
                    "4\n      python -m exactus.packages.package --build -"
                    "-tree --no-exactus"
                ),
            )
        ),
    )
    _ = parser.add_argument(
        "--exactus",
        "--check",
        dest="check",
        action="store_true",
        help="Build the ./bin/release/exactus_all/exactus zipapp only.",
    )
    _ = parser.add_argument(
        "--build",
        action="store_true",
        help="Build the ./build dist directory (unzipped zipapp tree) only.",
    )
    _ = parser.add_argument(
        "--tree",
        action="store_true",
        help="Write ./TREE.txt with the packaged project tree only.",
    )
    _ = parser.add_argument(
        "--no-exactus",
        action="store_true",
        help="Exclude EXACTUS_RESULTS and its complete subtree from TREE.txt.",
    )
    _ = parser.add_argument(
        "--target",
        action="extend",
        nargs="+",
        choices=(
            *_GroupFinalConstants.targets,
            *_GroupFinalConstants.target_groups,
            "all",
        ),
        default=None,
        help=(
            "Limit bundled OS/architecture/libc targets staged into the "
            "zipapp and dist tree; accepts several values and may be "
            "repeated. `all` keeps every target. Group aliases expand: "
        )
        + ", ".join(sorted(_GroupFinalConstants.target_groups))
        + ". Default: keep every target.",
    )
    _ = parser.add_argument(
        "--exec-target",
        action="extend",
        nargs="+",
        choices=(
            *_GroupFinalConstants.targets,
            *_GroupFinalConstants.target_groups,
            "all",
        ),
        default=None,
        help=(
            "Limit bundled targets staged into the fat release pyz only; "
            "overrides [tool.build.exec] targets and --target for the "
            "pyz. Same values as --target."
        ),
    )
    return parser


def _target_names(
    *,
    parser: ArgumentParser,
    cli: list[str] | None,
    targets: tuple[str, ...],
    target: str | None,
    label: str,
) -> list[str]:
    """Resolve requested bundle target names.

    Args:
        parser: Parser used to report configuration errors.
        cli: CLI target names.
        targets: Configured target list.
        target: Configured single target.
        label: Configuration subtable suffix.

    Returns:
        Validated requested target names.

    """
    if cli:
        return list(cli)
    names: list[str] = [*targets]
    if target is not None:
        names.append(target)
    allowed: frozenset[str] = frozenset(
        (
            *_GroupFinalConstants.targets,
            *_GroupFinalConstants.target_groups,
            "all",
        ),
    )
    unknown: set[str] = set(names) - allowed
    if unknown:
        parser.error(
            message=f"[tool.build{label}] unknown target(s): "
            + ", ".join(sorted(unknown)),
        )
    return names


def main() -> int:
    """Build the selected artifacts.

    Returns:
        Process exit status.

    """
    parser: ArgumentParser = create_parser()
    args: Namespace = parser.parse_args()
    _ = clear_conflict_copies(root=Constants.root)
    try:
        file_config: BuildFileConfig = build_file_config(
            path=Constants.root / "pyproject.toml",
        )
    except (TypeError, ValueError) as exc:
        parser.error(message=str(object=exc))
    targets: list[str] = _target_names(
        parser=parser,
        cli=args.target,
        targets=file_config.targets,
        target=file_config.target,
        label="",
    )
    exec_targets: list[str] = (
        _target_names(
            parser=parser,
            cli=args.exec_target,
            targets=file_config.exec_targets,
            target=file_config.exec_target,
            label=".exec",
        )
        or targets
    )
    kept: frozenset[Path] | None = kept_bundle_leaves(targets=targets)
    kept_exec: frozenset[Path] | None = kept_bundle_leaves(
        targets=exec_targets,
    )
    want_check: bool = bool(args.check) or file_config.check
    want_build: bool = bool(args.build) or file_config.build
    want_tree: bool = bool(args.tree) or file_config.tree
    want_all: bool = not (want_check or want_build or want_tree)
    if want_check or want_all:
        build_check(target=Constants.check, kept=kept_exec)
    if want_build or want_all:
        build_dist(kept=kept)
    if want_tree or want_all:
        build_tree(
            target=Constants.tree,
            include_exactus_results=not (
                args.no_exactus or file_config.no_exactus
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
