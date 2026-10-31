# Copyright (c) 2026
"""Document artifact folders from their innermost children outward."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tools.common.directory_inventory import heal_directory

if TYPE_CHECKING:
    from pathlib import Path


def write_directory_docs(*, root: Path) -> None:
    """Refresh standard artifact inventories without changing authored prose.

    Args:
        root: Artifact subtree to document.

    """
    if not root.is_dir() or root.is_symlink():
        return
    entries: list[Path] = [
        entry
        for entry in sorted(root.iterdir())
        if not entry.name.startswith(".")
        and entry.name != "__pycache__"
        and not entry.is_symlink()
    ]
    for entry in entries:
        write_directory_docs(root=entry)
    heal_directory(directory=root, entries=entries)
