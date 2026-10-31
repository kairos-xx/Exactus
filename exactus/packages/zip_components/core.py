# Copyright (c) 2026 João Lopes.
"""Create source-bundle archives of exactus tools and packages packages.

The bundler mirrors how the repository is organized: each named
component contributes its source directory, its ``tests/`` mirror and
its ``docs/`` page, plus the small package skeleton (``__init__.py``
chains, the ``packages`` runner, ``exactus/tests/common`` helpers and
``pyproject.toml``) that lets the bundle keep working once unzipped
with ``unzip -o <name>.zip -d .`` at a repository root.

Component selection is transitive: every Python file inside a selected
component is scanned for ``exactus.packages.<name>`` and
``exactus.tools.<name>`` imports, and each discovered component is
bundled with the same rules.
Discovery recurses until no new component appears, so ``--tools
lints`` automatically picks up ``exactus.tools.common``,
``exactus.tools.reports`` and every packages package the lint pipeline
drives.  The archive name only lists the requested components, for
example ``exactus_lints_docs_packages_all_lints_browser.zip``.

Usage:
    python exactus/packages/zip_components --tools lints docs
    python -m exactus.packages.zip_components --packages all_lints browser
    python -m exactus.packages.zip_components --project -o exactus-release.zip

``--project`` switches to release mode: instead of bundling selected
components it archives the whole project tree, replacing the regular
``exactus/bundle`` directory with the contents of
``build/exactus/bundle`` inside the archive, like the retired
``zipit.py`` script.
"""

from __future__ import annotations

from dataclasses import dataclass
from json import dumps
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_regex
from sys import stdout
from typing import TYPE_CHECKING, Final, final
from zipfile import ZIP_DEFLATED, ZipFile

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.tree import human_size as _human_size
from exactus.packages.tree import render_tree as _render_tree
from exactus.tools.common.catalog import Constants as _CatalogConstants
from exactus.tools.common.config import (
    discovery_from_environment,
    reports_directory,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Iterator, Sequence
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


@final
class Constants:
    """Group module-level constants.

    Attributes:
        component_import: Grouped module constant.
        quoted_module: Grouped module constant.
        skipped_directories: Grouped module constant.
        skipped_suffixes: Grouped module constant.
        skipped_names: Grouped module constant.
        shared_paths: Grouped module constant.
        exactus_paths: Grouped module constant.
        package_paths: Grouped module constant.
        bundles_folder: Grouped module constant.
        project_excluded_directories: Grouped module constant.
        project_bundle: Grouped module constant.
        project_build_bundle: Grouped module constant.
        project_archive: Grouped module constant.
        folder_readme: Grouped module constant.

    """

    component_import: Final[Pattern[str]] = compile_regex(
        pattern="^\\s*(?:from|import)\\s+exactus\\.(packages|tools)\\.([a-z_][a-z0-9_]*)",
    )
    quoted_module: Final[Pattern[str]] = compile_regex(
        pattern="[\"\\']exactus\\.(packages|tools)\\.([a-z_][a-z0-9_]*)",
    )
    skipped_directories: Final[frozenset[str]] = frozenset({"__pycache__"})
    skipped_suffixes: Final[frozenset[str]] = frozenset({".pyc", ".pyo"})
    skipped_names: Final[frozenset[str]] = frozenset({".DS_Store"})
    shared_paths: Final[tuple[str, ...]] = (
        "pyproject.toml",
        "exactus/tests/__init__.py",
        "exactus/tests/conftest.py",
        "exactus/tests/common",
    )
    exactus_paths: Final[tuple[str, ...]] = (
        "exactus/__init__.py",
        "exactus/__main__.py",
        "exactus/tools/__init__.py",
        "exactus/tests/exactus/__init__.py",
        "exactus/tests/exactus/tools/__init__.py",
        "exactus/tests/exactus/tools/README.md",
        "exactus/docs/exactus/tools/DOCS.md",
        "exactus/docs/exactus/tools/README.md",
    )
    package_paths: Final[tuple[str, ...]] = (
        "exactus/packages/__init__.py",
        "exactus/packages/__main__.py",
        "exactus/packages/README.md",
        "exactus/tests/packages/__init__.py",
        "exactus/tests/packages/README.md",
        "exactus/tests/packages/test_packages.py",
        "exactus/docs/packages/DOCS.md",
        "exactus/docs/packages/README.md",
    )
    bundles_folder: Final[str] = "zip-components"
    project_excluded_directories: Final[frozenset[str]] = frozenset(
        {
            "__pycache__",
            "build",
            "dist",
            "bin",
            "EXACTUS_RESULTS_RELEASE",
            "packages",
            "node_modules",
            "exactus.egg-info",
        },
    )
    project_bundle: Final[Path] = Path("exactus", "bundle")
    project_build_bundle: Final[Path] = Path("build", "exactus", "bundle")
    project_archive: Final[str] = "exactus-release.zip"
    folder_readme: Final[str] = (
        "# `zip-components/`\n"
        "\n"
        "Archives produced by `exactus.packages.zip_components` "
        "(`python exactus/packages/zip_components …`).\n"
        "\n"
        "Each subdirectory is named after its `.zip` and contains the\n"
        "archive, a `README.md` describing the bundle, and a `TREE.txt`\n"
        "listing every member. Extract with `unzip -o <name>.zip -d .`\n"
        "at a repository root to restore the files in place.\n"
        "\n"
        "This directory is git-ignored: bundles are build artifacts.\n"
    )


@dataclass(frozen=True)
class Selection:
    """Component names bundled by kind.

    Attributes:
        exactus: ``exactus/tools/<name>`` components.
        packages: ``exactus/packages/<name>`` components.

    """

    exactus: tuple[str, ...]
    packages: tuple[str, ...]


@dataclass(frozen=True)
class BundleResult:
    """Outcome of one bundle write.

    Attributes:
        path: Archive path on disk.
        files: Archive member names in write order.
        selection: Components bundled after dependency discovery.

    """

    path: Path
    files: tuple[str, ...]
    selection: Selection


def project_root() -> Path:
    """Return the repository root that owns this package.

    Returns:
        The repository root path.

    """
    return Path(__file__).resolve().parents[3]


def _unique(names: Sequence[str]) -> tuple[str, ...]:
    """Return names without duplicates, preserving order.

    Args:
        names: Component names as requested.

    Returns:
        The deduplicated names.

    """
    return tuple(dict.fromkeys(names))


def _expand_names(
    *,
    root: Path,
    kind: str,
    names: Sequence[str],
) -> tuple[str, ...]:
    """Expand ``all``/``*`` tokens into every component of ``kind``.

    Args:
        root: Repository root.
        kind: ``"exactus"`` or ``"packages"``.
        names: Requested names; ``all`` or ``*`` selects every
            available component of that kind.

    Returns:
        The deduplicated names with wildcards resolved.

    """
    normalized: list[str] = ["all" if name == "*" else name for name in names]
    if "all" not in normalized:
        return _unique(names=normalized)
    available: Selection = available_components(root=root)
    pool: tuple[str, ...] = (
        available.exactus if kind == "exactus" else available.packages
    )
    return _unique(
        names=(*[name for name in normalized if name != "all"], *pool),
    )


def _component_source(root: Path, kind: str, name: str) -> Path:
    """Return the source directory of one component.

    Args:
        root: Repository root.
        kind: ``"exactus"`` or ``"packages"``.
        name: Component name.

    Returns:
        The component source directory.

    """
    if kind == "exactus":
        return root / "exactus" / "tools" / name
    return root / "exactus" / "packages" / name


def _component_directories(
    root: Path,
    kind: str,
    name: str,
) -> tuple[Path, ...]:
    """Return every existing directory owned by one component.

    Args:
        root: Repository root.
        kind: ``"exactus"`` or ``"packages"``.
        name: Component name.

    Returns:
        Source and test directories, existing ones only.

    """
    tests: Path = (
        root / "exactus" / "tests" / "exactus" / "tools" / name
        if kind == "exactus"
        else root / "exactus" / "tests" / "packages" / name
    )
    candidates: tuple[Path, ...] = (
        _component_source(root=root, kind=kind, name=name),
        tests,
    )
    return tuple(candidate for candidate in candidates if candidate.is_dir())


def _scan_imports(source: Path) -> set[tuple[str, str]]:
    """Collect component imports declared by one Python file.

    Static ``from``/``import`` statements and quoted dotted module
    names both count, because packages ``__main__`` shims resolve their
    bootstrap through ``import_module`` with names held in literals or
    candidate tuples.

    Args:
        source: Python file to scan.

    Returns:
        ``(kind, name)`` pairs for each packages or tools import.

    """
    found: set[tuple[str, str]] = set()
    try:
        lines: list[str] = source.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return found
    line: str
    for line in lines:
        static: Match[str] | None = Constants.component_import.match(
            string=line,
        )
        dynamic: Match[str] | None = Constants.quoted_module.search(
            string=line,
        )
        match: Match[str] | None = static or dynamic
        if match is None:
            continue
        kind: str = "exactus" if match.group(1) == "tools" else "packages"
        found.add((kind, match.group(2)))
    return found


def discover_components(
    *,
    root: Path,
    exactus: Sequence[str] = (),
    packages: Sequence[str] = (),
) -> Selection:
    """Expand a selection with every transitively imported component.

    Args:
        root: Repository root.
        exactus: Requested ``exactus/tools/<name>`` components.
        packages: Requested ``exactus/packages/<name>`` components.

    Returns:
        Requested plus discovered components, first-seen order kept.

    """
    selected: dict[str, list[str]] = {
        "exactus": list(_unique(names=exactus)),
        "packages": list(_unique(names=packages)),
    }
    pending: list[tuple[str, str]] = [
        *zip(
            ["exactus"] * len(selected["exactus"]),
            selected["exactus"],
            strict=True,
        ),
        *zip(
            ["packages"] * len(selected["packages"]),
            selected["packages"],
            strict=True,
        ),
    ]
    seen: set[tuple[str, str]] = set(pending)
    while pending:
        kind, name = pending.pop()
        directory: Path
        for directory in _component_directories(
            root=root,
            kind=kind,
            name=name,
        ):
            source: Path
            for source in sorted(directory.rglob(pattern="*.py")):
                dependency: tuple[str, str]
                for dependency in sorted(_scan_imports(source=source)):
                    if (
                        dependency in seen
                        or not _component_source(
                            root=root,
                            kind=dependency[0],
                            name=dependency[1],
                        ).is_dir()
                    ):
                        continue
                    seen.add(dependency)
                    pending.append(dependency)
                    selected[dependency[0]].append(dependency[1])
                    trace(
                        step=(
                            "zip components: discovered "
                            f"{dependency[0]}.{dependency[1]} "
                            f"from {kind}.{name}"
                        ),
                        depth=2,
                    )
    return Selection(
        exactus=tuple(selected["exactus"]),
        packages=tuple(selected["packages"]),
    )


def available_components(*, root: Path) -> Selection:
    """Return every bundleable component, sorted by name.

    Exactus entries are the canonical catalog tools — the same list
    ``python exactus --list-tools`` prints — while packages entries are
    every ``exactus/packages/`` package directory present under ``root``.

    Args:
        root: Repository root.

    Returns:
        Canonical exactus tool identifiers plus all packages packages.

    """

    def packages(directory: Path) -> tuple[str, ...]:
        """List package directories containing ``__init__.py``.

        Args:
            directory: Directory scanned for packages.

        Returns:
            Sorted package directory names.

        """
        if not directory.is_dir():
            return ()
        return tuple(
            sorted(
                entry.name
                for entry in directory.iterdir()
                if (entry / "__init__.py").is_file()
            ),
        )

    return Selection(
        exactus=tuple(
            sorted(
                tool.identifier
                for tool in _CatalogConstants.exactus_catalog.tools()
            ),
        ),
        packages=packages(directory=root / "exactus" / "packages"),
    )


def _walk(root: Path, relative: str) -> Iterator[Path]:
    """Yield bundle files under one root-relative path.

    Args:
        root: Repository root.
        relative: File or directory path relative to the root.

    Yields:
        Files only, skipping caches and platform noise.

    """
    path: Path = root / relative
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        return
    candidate: Path
    for candidate in sorted(path.rglob(pattern="*")):
        if (
            candidate.is_file()
            and (
                not Constants.skipped_directories.intersection(candidate.parts)
            )
            and (candidate.suffix not in Constants.skipped_suffixes)
            and (candidate.name not in Constants.skipped_names)
            and not any(
                part.startswith(".")
                for part in candidate.relative_to(path).parent.parts
            )
        ):
            yield candidate


def _results_directories(*, root: Path, names: Sequence[str]) -> list[str]:
    """Return each selected tool's existing reports subdirectory.

    Args:
        root: Repository root.
        names: Selected ``exactus/tools/<name>`` components.

    Returns:
        Root-relative report directories that exist, in selection order.

    """
    if not names:
        return []
    base: Path = reports_directory(
        files=discovery_from_environment(start=root),
    )
    return [
        (base / name.upper()).as_posix()
        for name in names
        if (root / base / name.upper()).is_dir()
    ]


def collect_files(*, root: Path, selection: Selection) -> tuple[str, ...]:
    """List every repository-relative file a selection bundles.

    Args:
        root: Repository root.
        selection: Components to bundle after dependency discovery.

    Returns:
        Sorted unique archive member names.

    """
    members: set[str] = set()
    roots: list[str] = list(Constants.shared_paths)
    if selection.exactus:
        roots.extend(Constants.exactus_paths)
    if selection.packages:
        roots.extend(Constants.package_paths)
    name: str
    roots.extend(_results_directories(root=root, names=selection.exactus))
    for name in selection.exactus:
        roots.extend(
            (
                f"exactus/tools/{name}",
                f"exactus/tests/exactus/tools/{name}",
                f"exactus/docs/exactus/tools/{name}",
            ),
        )
    for name in selection.packages:
        roots.extend(
            (
                f"exactus/packages/{name}",
                f"exactus/tests/packages/{name}",
                f"exactus/docs/packages/{name}",
            ),
        )
    relative: str
    for relative in roots:
        file: Path
        for file in _walk(root=root, relative=relative):
            members.add(file.relative_to(root).as_posix())
    return tuple(sorted(members))


def bundle_name(
    *,
    exactus: Sequence[str] = (),
    packages: Sequence[str] = (),
) -> str:
    """Return the archive name derived from the requested components.

    Args:
        exactus: Requested exactus tool names.
        packages: Requested packages package names.

    Returns:
        ``exactus_<…>.zip``, ``packages_<…>.zip`` or the joined form.

    """
    parts: list[str] = []
    exactus_names: tuple[str, ...] = _unique(
        names=["all" if name == "*" else name for name in exactus],
    )
    package_names: tuple[str, ...] = _unique(
        names=["all" if name == "*" else name for name in packages],
    )
    if exactus_names:
        parts.append("_".join(("exactus", *exactus_names)))
    if package_names:
        parts.append("_".join(("packages", *package_names)))
    return f"{'_'.join(parts)}.zip"


def _bundle_readme(
    *,
    name: str,
    files: Sequence[str],
    size: int,
    selection: Selection,
    requested: Selection,
) -> str:
    """Return the README describing one bundle directory.

    Args:
        name: Archive file name.
        files: Archive member names.
        size: Archive size in bytes.
        selection: Resolved selection including discovered dependencies.
        requested: Components named on the command line.

    Returns:
        Markdown content ending with a newline.

    """
    discovered: list[str] = [
        f"exactus.{entry}"
        for entry in selection.exactus
        if entry not in requested.exactus
    ] + [
        f"exactus.packages.{entry}"
        for entry in selection.packages
        if entry not in requested.packages
    ]
    requested_lines: str = "".join(
        f"- `exactus.{entry}`\n" for entry in requested.exactus
    ) + "".join(f"- `packages.{entry}`\n" for entry in requested.packages)
    return (
        f"# `{name.removesuffix('.zip')}/`\n"
        "\n"
        "Source bundle produced by `exactus.packages.zip_components`.\n"
        "\n"
        "## Contents\n"
        "\n"
        f"- `{name}` — the archive ({len(files)} files, "
        f"{_human_size(size=size)})\n"
        "- `TREE.txt` — the archive's members as a size/date tree\n"
        "- `README.md` — this file\n"
        "\n"
        "## Selection\n"
        "\n"
        f"{requested_lines}"
        "\n"
        f"Discovered transitively: "
        f"{', '.join(f'`{item}`' for item in discovered) or 'none'}\n"
        "\n"
        "## Usage\n"
        "\n"
        "```bash\n"
        f"unzip -o {name} -d .\n"
        "```\n"
        "\n"
        "Run at a repository root to restore every member in place.\n"
    )


def create_bundle(
    *,
    root: Path,
    exactus: Sequence[str] = (),
    packages: Sequence[str] = (),
    output: Path | None = None,
    output_folder: Path | None = None,
) -> BundleResult:
    """Write one source-bundle archive for the requested components.

    Args:
        root: Repository root.
        exactus: Requested ``exactus/tools/<name>`` components; ``all``
            or ``*`` selects every tool in the catalog.
        packages: Requested ``exactus/packages/<name>`` components; ``all`` or
            ``*`` selects every packages package.
        output: Explicit archive path; writes a bare zip, bypassing the
            scaffolded bundle layout.
        output_folder: Directory holding the bundle folder; defaults to
            ``<root>/zip-components``.

    Returns:
        The written archive path, its members and the full selection.

    """
    selection: Selection = Selection(
        exactus=_expand_names(root=root, kind="exactus", names=exactus),
        packages=_expand_names(root=root, kind="packages", names=packages),
    )
    discovered: Selection = discover_components(
        root=root,
        exactus=selection.exactus,
        packages=selection.packages,
    )
    files: tuple[str, ...] = collect_files(root=root, selection=discovered)
    name: str = bundle_name(exactus=exactus, packages=packages)
    bundle_dir: Path | None = None
    if output is not None:
        destination: Path = output
    else:
        folder: Path = (
            output_folder
            if output_folder is not None
            else root / Constants.bundles_folder
        )
        folder.mkdir(parents=True, exist_ok=True)
        folder_readme: Path = folder / "README.md"
        if not folder_readme.is_file():
            _ = folder_readme.write_text(
                data=Constants.folder_readme,
                encoding="utf-8",
            )
        bundle_dir = folder / name.removesuffix(".zip")
        bundle_dir.mkdir(parents=True, exist_ok=True)
        destination = bundle_dir / name
    with ZipFile(
        file=destination,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        member: str
        for member in files:
            archive.write(filename=root / member, arcname=member)
    if bundle_dir is not None:
        _ = (bundle_dir / "README.md").write_text(
            data=_bundle_readme(
                name=name,
                files=files,
                size=destination.stat().st_size,
                selection=discovered,
                requested=selection,
            ),
            encoding="utf-8",
        )
        _ = (bundle_dir / "TREE.txt").write_text(
            data=_render_tree(
                source=files,
                root=root,
                name=name.removesuffix(".zip"),
            ),
            encoding="utf-8",
        )
        trace(
            step=f"zip components: {bundle_dir.name}/README.md + TREE.txt",
            depth=1,
        )
    return BundleResult(path=destination, files=files, selection=discovered)


def _project_file_excluded(*, relative: Path) -> bool:
    """Return whether a project path is excluded from the release archive.

    Args:
        relative: Path relative to the project root.

    Returns:
        Whether the path must not be copied from the regular source tree.

    """
    return (
        relative.name in Constants.skipped_names
        or any(
            part.startswith(".")
            or part in Constants.project_excluded_directories
            for part in relative.parts
        )
        or relative == Constants.project_bundle
        or Constants.project_bundle in relative.parents
    )


def _project_bundle_excluded(*, relative: Path) -> bool:
    """Return whether a built-bundle file is excluded from the archive.

    Args:
        relative: Path relative to ``build/exactus/bundle``.

    Returns:
        Whether the path must be omitted.

    """
    return relative.name in Constants.skipped_names or any(
        part.startswith(".") or part in {"__pycache__", "node_modules"}
        for part in relative.parts
    )


def create_project_archive(
    *,
    root: Path,
    output: Path | None = None,
) -> BundleResult:
    """Write the project release ZIP with the current built bundle.

    The source tree is never modified. The regular ``exactus/bundle``
    directory is omitted from the project files and
    ``build/exactus/bundle`` is written into the archive at that
    location instead.

    Args:
        root: Project root to archive.
        output: Destination ZIP path; relative paths resolve under
            ``root``. Defaults to ``<root>/exactus-release.zip``.

    Returns:
        The written archive path, its member names and an empty
        component selection.

    Raises:
        FileNotFoundError: If the built Exactus bundle does not exist.

    """
    resolved: Path = root.resolve()
    bundle: Path = resolved / Constants.project_build_bundle
    if not bundle.is_dir():
        msg: str = f"Built bundle does not exist: {bundle}"
        raise FileNotFoundError(msg)
    destination: Path = (
        output if output is not None else Path(Constants.project_archive)
    )
    destination = (
        destination if destination.is_absolute() else resolved / destination
    ).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    members: list[tuple[Path, str]] = []
    for path in resolved.rglob(pattern="*"):
        relative: Path = path.relative_to(resolved)
        if (
            path.is_file()
            and path != destination
            and not _project_file_excluded(relative=relative)
        ):
            members.append((path, relative.as_posix()))
    for path in bundle.rglob(pattern="*"):
        relative = path.relative_to(bundle)
        if path.is_file() and not _project_bundle_excluded(relative=relative):
            members.append(
                (path, (Constants.project_bundle / relative).as_posix()),
            )
    with ZipFile(
        file=destination,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        source: Path
        arcname: str
        for source, arcname in members:
            archive.write(filename=source, arcname=arcname)
    return BundleResult(
        path=destination,
        files=tuple(arcname for _, arcname in members),
        selection=Selection(exactus=(), packages=()),
    )


def _project_release(
    *,
    parser: ArgumentParser,
    options: Namespace,
    root: Path,
    exactus: Sequence[str],
    packages: Sequence[str],
) -> int:
    """Write the whole-project release archive for ``--project``.

    Args:
        parser: Command-line parser used to report option conflicts.
        options: Parsed command-line arguments.
        root: Project root to archive.
        exactus: Requested exactus tool names (must be empty).
        packages: Requested packages names (must be empty).

    Returns:
        ``0`` when the archive was written.

    """
    if exactus or packages:
        parser.error(
            message="--project cannot be combined with component selections",
        )
    if options.listing:
        parser.error(message="--project cannot be combined with --list")
    if options.output_folder is not None:
        parser.error(
            message="--project cannot be combined with --output-folder",
        )
    result: BundleResult = create_project_archive(
        root=root,
        output=options.output,
    )
    shown: Path = (
        result.path.relative_to(root)
        if result.path.is_relative_to(root)
        else result.path
    )
    _written: int = stdout.write(
        f"zip components: {shown} — {len(result.files)} files, "
        f"{result.path.stat().st_size} bytes\n",
    )
    return 0


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Bundle the requested exactus tools and/or packages packages.

    Args:
        arguments: Command-line arguments excluding the program name.

    Returns:
        ``0`` when the archive was written, ``1`` without any selection.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="zip_components",
        description=(
            "Bundle exactus tools and/or packages packages with "
            "their sources, tests, docs and shared skeleton files. "
            "Positional names are shorthand for --packages; a bare "
            "``*``/``all`` positional selects every component of both "
            "kinds."
        ),
    )
    parser.add_argument(
        "names",
        nargs="*",
        metavar="PACKAGE",
        help=(
            "exactus/packages/<PACKAGE> components (shorthand for --packages)."
        ),
    )
    parser.add_argument(
        "--tools",
        dest="exactus",
        nargs="+",
        default=(),
        metavar="TOOL",
        help=(
            "exactus/tools/<TOOL> components to bundle "
            "(``all``/``*`` selects every tool)."
        ),
    )
    parser.add_argument(
        "--packages",
        dest="packages",
        nargs="+",
        default=(),
        metavar="PACKAGE",
        help=(
            "exactus/packages/<PACKAGE> components to bundle "
            "(``all``/``*`` selects every package)."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        type=Path,
        default=None,
        metavar="ZIP",
        help="Destination archive (writes a bare zip, no bundle layout).",
    )
    parser.add_argument(
        "--output-folder",
        dest="output_folder",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Directory holding the bundle folder "
            "(defaults to <root>/zip-components)."
        ),
    )
    parser.add_argument(
        "--list",
        "-l",
        dest="listing",
        action="store_true",
        help=(
            "Print the resolved selection as JSON instead of bundling; "
            "without components lists every available package."
        ),
    )
    parser.add_argument(
        "--project",
        dest="project",
        action="store_true",
        help=(
            "Archive the whole project as a release ZIP: the regular "
            "exactus/bundle directory is replaced by the contents of "
            "build/exactus/bundle inside the archive."
        ),
    )
    parser.add_argument(
        "--root",
        dest="root",
        type=Path,
        default=None,
        metavar="DIR",
        help="Project root to bundle from (defaults to auto-detection).",
    )
    options: Namespace = parser.parse_args(
        args=list(arguments) if arguments is not None else None,
    )
    positionals: tuple[str, ...] = tuple(options.names)
    exactus: tuple[str, ...] = tuple(options.exactus)
    packages: tuple[str, ...] = (*positionals, *options.packages)
    if any(token in {"*", "all"} for token in positionals) and not any(
        token in {"*", "all"} for token in exactus
    ):
        exactus = (*exactus, "all")
    if (
        not exactus
        and (not packages)
        and not options.listing
        and not options.project
    ):
        parser.print_usage(file=stdout)
        return 1
    root: Path = (
        options.root.expanduser().resolve()
        if options.root is not None
        else project_root()
    )
    if options.project:
        return _project_release(
            parser=parser,
            options=options,
            root=root,
            exactus=exactus,
            packages=packages,
        )
    if options.listing:
        selection: Selection = (
            discover_components(
                root=root,
                exactus=_expand_names(
                    root=root,
                    kind="exactus",
                    names=exactus,
                ),
                packages=_expand_names(
                    root=root,
                    kind="packages",
                    names=packages,
                ),
            )
            if exactus or packages
            else available_components(root=root)
        )
        _listed: int = stdout.write(
            dumps(
                obj={
                    "packages": sorted(selection.packages),
                    "exactus": sorted(selection.exactus),
                },
                indent=2,
            )
            + "\n",
        )
        return 0
    kind: str
    names: tuple[str, ...]
    for kind, names in (("exactus", exactus), ("packages", packages)):
        name: str
        for name in _expand_names(root=root, kind=kind, names=names):
            if not _component_source(root=root, kind=kind, name=name).is_dir():
                parser.error(message=f"unknown {kind} component: {name}")
    result: BundleResult = create_bundle(
        root=root,
        exactus=exactus,
        packages=packages,
        output=options.output,
        output_folder=options.output_folder,
    )
    requested: Selection = Selection(
        exactus=_expand_names(root=root, kind="exactus", names=exactus),
        packages=_expand_names(root=root, kind="packages", names=packages),
    )
    discovered: list[str] = [
        f"exactus.{name}"
        for name in result.selection.exactus
        if name not in requested.exactus
    ] + [
        f"exactus.packages.{name}"
        for name in result.selection.packages
        if name not in requested.packages
    ]
    shown: Path = (
        result.path.relative_to(root)
        if result.path.is_relative_to(root)
        else result.path
    )
    message: str = (
        f"zip components: {shown} — {len(result.files)} "
        f"files, {result.path.stat().st_size} bytes\n"
    )
    if discovered:
        message += f"zip components: discovered — {', '.join(discovered)}\n"
    _written: int = stdout.write(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
