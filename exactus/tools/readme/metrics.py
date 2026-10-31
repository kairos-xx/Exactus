# Copyright (c) 2026
"""Measure Markdown files and README sizes for the README report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tools.common.cli import is_reports_tree, match_path

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


def collect_metrics(
    *,
    root: Path,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    excluded_dirs: frozenset[str],
) -> dict[str, JsonValue]:
    """Measure scoped Markdown files and source directories without READMEs.

    Args:
        root: Project directory.
        includes: Included path globs.
        excludes: Excluded path globs.
        excluded_dirs: Built-in directory exclusions.

    Returns:
        Markdown totals, README extremes and undocumented source folders.

    """
    documents: list[dict[str, JsonValue]] = []
    readmes: list[dict[str, JsonValue]] = []
    source_dirs: set[str] = set()
    documented: set[str] = set()
    entries: Iterable[tuple[Path, list[str], list[str]]] = (
        ((root.parent, [], [root.name]),)
        if root.is_file()
        else root.walk(top_down=True)
    )
    if root.is_file():
        root = root.parent
    for directory, directories, filenames in entries:
        directories[:] = [
            name
            for name in directories
            if name not in excluded_dirs
            and not name.startswith(".")
            and not is_reports_tree(directory=directory / name)
            and not name.endswith((".egg-info", ".dist-info"))
            and not (directory / name).is_symlink()
        ]
        for name in sorted(filenames):
            path: Path = directory / name
            if path.is_symlink() or not match_path(
                path=path,
                root=root,
                includes=includes,
                excludes=excludes,
            ):
                continue
            relative: str = directory.relative_to(root).as_posix()
            if path.suffix in {".py", ".js", ".mjs", ".cjs"}:
                source_dirs.add(relative)
            if path.suffix.lower() != ".md":
                continue
            try:
                content: bytes = path.read_bytes()
            except OSError:
                continue
            entry: dict[str, JsonValue] = {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(content),
                "lines": content.count(b"\n")
                + int(bool(content) and not content.endswith(b"\n")),
            }
            documents.append(entry)
            if name.lower() == "readme.md":
                documented.add(relative)
                readmes.append(entry)
    readmes.sort(key=lambda item: str(object=item["path"]))
    sizes: list[tuple[int, dict[str, JsonValue]]] = [
        (int(str(object=item["bytes"])), item) for item in readmes
    ]
    largest: dict[str, JsonValue] | None = (
        max(sizes, key=lambda pair: pair[0])[1] if sizes else None
    )
    smallest: dict[str, JsonValue] | None = (
        min(sizes, key=lambda pair: pair[0])[1] if sizes else None
    )
    missing: Sequence[JsonValue] = sorted(source_dirs - documented)
    return {
        "markdown": {
            "files": len(documents),
            "bytes": sum(int(str(object=item["bytes"])) for item in documents),
            "lines": sum(int(str(object=item["lines"])) for item in documents),
            "readme_files": len(readmes),
            "largest_readme": None
            if largest is None
            else {"path": largest["path"], "bytes": largest["bytes"]},
            "smallest_readme": None
            if smallest is None
            else {"path": smallest["path"], "bytes": smallest["bytes"]},
        },
        "directories_without_readme": list(missing),
    }
