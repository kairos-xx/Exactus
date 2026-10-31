# Copyright (c) 2026
"""Share project-tree filtering between package and build_make scripts.

A single predicate set decides what belongs to the distributable
project tree so the zip archive (``exactus.packages.package``) and the
rendered ``TREE.txt`` (``exactus.packages.package --build``) describe
the same content by default:

- directories whose name starts with ``.`` (``.git``, ``.ruff_cache``,
  ``.vscode``, ``.history``, …) — pruned entirely, as are dotfiles
  like ``.DS_Store``;
- directories whose name is all-uppercase (``EXACTUS_RESULTS``,
  ``LINTS``, ``FRONTEND``, …) — generated exactus output;
- ``build/`` dist trees, ``*.egg-info`` packaging metadata,
  ``__pycache__`` bytecode caches, the ``exec/`` executable output
  directory, and the ``packages/`` archive output directory;
- files that are readable zip archives — ``*.zip``, ``*.whl`` wheels,
  and the extensionless ``exec/exactus``/``build/exactus`` zipapps.

``EXACTUS_RESULTS`` can optionally be retained as an exception to the
all-uppercase directory rule. Within that subtree, other uppercase
directories are also retained, while all remaining directory and file
filtering rules continue to apply.
"""

from __future__ import annotations

from functools import lru_cache
from json import loads
from os import stat_result, walk
from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict, cast, final
from zipfile import is_zipfile

from exactus.packages.tree import render_tree as _render_tree

if TYPE_CHECKING:
    from collections.abc import Iterator


@final
class Constants:
    """Group module-level constants.

    Attributes:
        exactus_results: Grouped module constant.

    """

    exactus_results: Final[str] = "EXACTUS_RESULTS"


class _PackPath(TypedDict):
    """Distribution path of a current catalog pack.

    Attributes:
        path: Relative immutable pack path.

    """

    path: str


class _PayloadCatalog(TypedDict):
    """Catalog fields required to select distributable payload files.

    Attributes:
        format: Filesystem format identifier.
        packs: Current reachable pack records.

    """

    format: str
    packs: dict[str, _PackPath]


@lru_cache(maxsize=16)
def _partition_members(root: Path, modified_ns: int) -> frozenset[str] | None:
    """Read current distribution membership once per catalog revision.

    Args:
        root: Partitioned filesystem root.
        modified_ns: Catalog modification timestamp used as cache identity.

    Returns:
        Reachable files, or None for an unrelated catalog format.

    """
    _ = modified_ns
    catalog: _PayloadCatalog = cast(
        typ="_PayloadCatalog",
        val=loads(s=(root / "catalog.json").read_text(encoding="utf-8")),
    )
    if catalog.get("format") != "partitioned-filesystem-v1":
        return None
    return frozenset(
        {"catalog.json"}
        | {pack["path"] for pack in catalog["packs"].values()},
    )


def partition_excluded(*, directory: Path, name: str) -> bool:
    """Exclude retained catalogs and unreachable packs from distributions.

    Args:
        directory: Directory containing the candidate entry.
        name: Candidate file or directory name.

    Returns:
        Whether the entry lies outside current catalog membership.

    """
    for root in (directory, *directory.parents):
        catalog: Path = root / "catalog.json"
        if root.name != "fs" or not catalog.is_file():
            continue
        members: frozenset[str] | None = _partition_members(
            root=root,
            modified_ns=catalog.stat().st_mtime_ns,
        )
        if members is None:
            return False
        relative: str = (directory / name).relative_to(root).as_posix()
        if name == "README.md" or (directory / name / "README.md").is_file():
            return False
        return relative not in members and (
            not any(member.startswith(relative + "/") for member in members)
        )
    return False


def excluded_dir(*, name: str, allow_uppercase: bool = False) -> bool:
    """Return whether a directory is pruned from the project tree.

    Args:
        name: Immediate directory name.
        allow_uppercase: Whether all-uppercase directory names are
            allowed.

    Returns:
        ``True`` for dot-folders, the ``build`` dist tree,
        ``*.egg-info`` packaging metadata, ``__pycache__`` bytecode
        caches, and the ``exec``/``packages`` output dirs.
        All-uppercase names are also excluded unless
        ``allow_uppercase`` is enabled.

    """
    return (
        name.startswith(".")
        or (name.isupper() and (not allow_uppercase))
        or name in ("build", "__pycache__", "exec", "packages")
        or name.endswith(".egg-info")
    )


def is_zip(path: Path) -> bool:
    """Return whether a file is a zip archive by content.

    ``is_zipfile`` locates the end-of-central-directory record, so it
    also recognizes ``exec/exactus``/``build/exactus`` zipapps whose ``PK``
    data sits behind a ``#!`` shebang line, plus ``*.whl``/``*.zip``
    files.

    Args:
        path: Candidate file.

    Returns:
        ``True`` when the file is a readable zip archive.

    """
    return is_zipfile(filename=path)


def walk_project(
    *,
    root: Path,
    include_exactus_results: bool = False,
) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Yield the filtered project tree, directory by directory.

    When ``include_exactus_results`` is enabled, the root-level
    ``EXACTUS_RESULTS`` directory is retained despite its uppercase name.
    Within that subtree, other uppercase directories are also retained.
    All other normal directory and file exclusions continue to apply.

    Args:
        root: Project root to walk.
        include_exactus_results: Whether to retain ``EXACTUS_RESULTS`` and
            allow uppercase directories within its subtree.

    Yields:
        ``(directory, kept dirnames, kept filenames)`` triples in
        deterministic order; ``dirnames`` is already pruned in place
        semantics so descendants of excluded dirs are never visited.
        Symlinked directories surface among the filenames as leaf
        entries rather than being descended into.

    """
    for base, directories, names in walk(top=root, followlinks=False):
        directory: Path = Path(base)
        relative: Path = directory.relative_to(root)
        in_exactus_results: bool = (
            include_exactus_results
            and bool(relative.parts)
            and (relative.parts[0] == Constants.exactus_results)
        )
        directories[:] = sorted(
            name
            for name in directories
            if (
                (
                    include_exactus_results
                    and directory == root
                    and (name == Constants.exactus_results)
                )
                or not excluded_dir(
                    name=name,
                    allow_uppercase=in_exactus_results,
                )
            )
            and (not partition_excluded(directory=directory, name=name))
        )
        linked: frozenset[str] = frozenset(
            name for name in directories if (directory / name).is_symlink()
        )
        directories[:] = [name for name in directories if name not in linked]
        yield (
            directory,
            list(directories),
            sorted(
                name
                for name in [*names, *linked]
                if not name.startswith(".")
                and (not partition_excluded(directory=directory, name=name))
                and (
                    not is_zip(path=directory / name)
                    or (
                        directory.name == "bin"
                        and directory.parent.name == "zstd_portable"
                    )
                )
            ),
        )


def collect_files(
    *,
    root: Path,
    exclude: Path | None = None,
    include_exactus_results: bool = False,
) -> list[Path]:
    """Collect the project files eligible for archiving.

    Args:
        root: Project root to walk.
        exclude: Optional file path always skipped (the archive itself).
        include_exactus_results: Whether to retain ``EXACTUS_RESULTS`` and
            allow uppercase directories within its subtree.

    Returns:
        Sorted list of files to archive.

    """
    resolved: Path | None = exclude.resolve() if exclude else None
    files: list[Path] = []
    for base, _directories, names in walk_project(
        root=root,
        include_exactus_results=include_exactus_results,
    ):
        for name in names:
            path: Path = base / name
            if resolved is None or path.resolve() != resolved:
                files.append(path)
    return files


def render_tree(*, root: Path, include_exactus_results: bool = False) -> str:
    """Render the filtered project tree as ``tree``-style text.

    Every entry shows its name plus aligned columns for a
    human-readable size and a ``dd Mon yyyy HH:MM`` modified date;
    directories aggregate descendant file sizes and the latest
    descendant mtime. The listing itself is produced by
    ``exactus.packages.tree``; this wrapper supplies the project-filtered
    member set so zipapps and caches stay hidden.

    When ``include_exactus_results`` is enabled, the root-level
    ``EXACTUS_RESULTS`` directory and uppercase directories within its
    subtree are included. All other normal filtering rules continue
    to apply.

    Args:
        root: Project root; its name becomes the first line.
        include_exactus_results: Whether to retain ``EXACTUS_RESULTS`` and
            allow uppercase directories within its subtree.

    Returns:
        Tree text ending with a newline, e.g. ``root/`` followed by
        ``├──``/``└──`` entries with directories suffixed by ``/``.

    """
    members: dict[str, tuple[int, float] | None] = {}
    base: Path
    directories: list[str]
    names: list[str]
    for base, directories, names in walk_project(
        root=root,
        include_exactus_results=include_exactus_results,
    ):
        relative: Path = base.relative_to(root)
        name: str
        for name in directories:
            members[(relative / name).as_posix() + "/"] = None
        for name in names:
            child: Path = base / name
            stat: stat_result = (
                child.lstat() if child.is_symlink() else child.stat()
            )
            members[(relative / name).as_posix()] = (
                stat.st_size,
                stat.st_mtime,
            )
    return _render_tree(source=members, name=root.name)
