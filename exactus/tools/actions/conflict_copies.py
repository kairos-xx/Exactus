# Copyright (c) 2026 Project contributors
"""Reconcile numbered sync copies without discarding unique project data."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from os import walk
from pathlib import Path
from re import Match, fullmatch
from typing import TYPE_CHECKING, Final, final
from uuid import uuid4

if TYPE_CHECKING:
    from _hashlib import HASH


@final
class Constants:
    """Group module-level constants.

    Attributes:
        ignored: Grouped module constant.

    """

    ignored: Final[frozenset[str]] = frozenset(
        {
            ".history",
            "node_modules",
            "venv",
            "__pycache__",
            "exactus/packages",
        },
    )


@dataclass
class ClearResult:
    """Describe reconciled sync copies and recoverable conflicts.

    Attributes:
        removed_directories: Numbered directories removed after merging.
        merged_entries: Unique files or subtrees moved into canonical paths.
        preserved_conflicts: Divergent entries saved in the recovery directory.
        errors: Filesystem errors left for a later run to retry.

    """

    removed_directories: int = 0
    merged_entries: int = 0
    preserved_conflicts: int = 0
    errors: int = 0


def _digest(*, path: Path) -> bytes:
    """Hash a regular file with bounded memory.

    Args:
        path: File whose contents are compared.

    Returns:
        SHA-256 content digest.

    """
    digest: HASH = sha256()
    data: bytes
    with path.open(mode="rb") as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    return digest.digest()


def _same(*, source: Path, target: Path) -> bool:
    """Compare links or regular files without following directory links.

    Args:
        source: Numbered copy entry.
        target: Canonical entry.

    Returns:
        Whether both entries have the same type and contents.

    """
    if source.is_symlink() or target.is_symlink():
        return (
            source.is_symlink()
            and target.is_symlink()
            and (source.readlink() == target.readlink())
        )
    return (
        source.is_file()
        and target.is_file()
        and (source.stat().st_size == target.stat().st_size)
        and (_digest(path=source) == _digest(path=target))
    )


def _merge(
    *,
    source: Path,
    target: Path,
    root: Path,
    result: ClearResult,
) -> None:
    """Merge a duplicate tree, preserving every divergent entry.

    Args:
        source: Duplicate directory that is never traversed through links.
        target: Existing canonical directory.
        root: Project containing the recovery directory.
        result: Counters updated by reconciliation.

    """
    child: Path
    for child in source.iterdir():
        destination: Path = target / child.name
        if not destination.exists() and (not destination.is_symlink()):
            child.rename(target=destination)
            result.merged_entries += 1
        elif (
            child.is_dir()
            and (not child.is_symlink())
            and destination.is_dir()
            and (not destination.is_symlink())
        ):
            _merge(source=child, target=destination, root=root, result=result)
            child.rmdir()
        elif _same(source=child, target=destination):
            child.unlink()
        else:
            recovery: Path = (
                root
                / ".icloud-conflicts"
                / uuid4().hex
                / destination.relative_to(root)
            )
            recovery.parent.mkdir(parents=True, exist_ok=True)
            child.rename(target=recovery)
            result.preserved_conflicts += 1


def _numbered_copy(*, name: str, parent: Path) -> Path | None:
    """Return the canonical directory for a numbered copy name.

    Args:
        name: Directory entry, for example ``.runtime 2``.
        parent: Directory containing the entry.

    Returns:
        The canonical sibling directory when it exists, else ``None``.

    """
    match: Match[str] | None = fullmatch(
        pattern="(.+) ([2-9]|[1-9][0-9]+)",
        string=name,
    )
    if match is None:
        return None
    canonical: Path = parent / match.group(1)
    if canonical.is_symlink() or not canonical.is_dir():
        return None
    return canonical


def clear_conflict_copies(*, root: Path) -> ClearResult:
    """Reconcile numbered directories with existing canonical counterparts.

    Run at tool startup and completion. Ignore hidden/dependency trees and
    directory symlinks; numbered hidden copies such as ``.runtime 2`` still
    merge into their canonical sibling. Never remove unmatched numbered
    directories. Merge unique entries into the canonical tree and retain
    divergent contents in ``.icloud-conflicts``. A concurrently changing or
    unavailable entry stays in place for the next run instead of blocking
    the requested tool.

    Args:
        root: Project or bundle directory to reconcile.

    Returns:
        Reconciliation counters, including recoverable filesystem errors.

    """
    result: ClearResult = ClearResult()
    if ".history" in root.parts or root.is_symlink() or (not root.is_dir()):
        return result
    root = root.resolve()
    directory: str
    names: list[str]
    _files: list[str]
    for directory, names, _files in walk(top=root, followlinks=False):
        parent: Path = Path(directory)
        for name in tuple(names):
            path: Path = parent / name
            canonical: Path | None = _numbered_copy(name=name, parent=parent)
            if (
                name in Constants.ignored
                or path.relative_to(root).as_posix() in Constants.ignored
                or (canonical is not None and canonical.name == ".history")
                or path.is_symlink()
                or (name.startswith(".") and canonical is None)
            ):
                names.remove(name)
                continue
            if name.startswith("."):
                names.remove(name)
            if canonical is None:
                continue
            try:
                _merge(source=path, target=canonical, root=root, result=result)
                path.rmdir()
            except OSError:
                result.errors += 1
            else:
                if name in names:
                    names.remove(name)
                result.removed_directories += 1
    return result
