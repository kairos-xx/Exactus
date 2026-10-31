# Copyright (c) 2026 Project contributors
"""File synchronization with stable reads and atomic replacement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import atomic_write, render_html, update
from .normalize import normalize

if TYPE_CHECKING:
    from os import stat_result
    from pathlib import Path


def synchronize(
    *,
    path: Path,
    check: bool = False,
    html: bool = True,
    normalize_tasks: bool = False,
) -> bool:
    """Update managed Markdown and sibling HTML; return whether either differs.

    Check mode never writes. A changed source during rendering aborts
    the write.
    Atomic replacement prevents torn files, but is not a cross-process editing
    transaction: arbitrary writers must still coordinate with the watcher.

    Args:
        path: Source Markdown file whose dashboard is synchronized.
        check: Report differences without writing either output.
        html: Generate or compare the sibling standalone HTML dashboard.
        normalize_tasks: Write uniform task headers before synchronization.

    Returns:
        Whether the Markdown or requested HTML differs from current output.

    Raises:
        ValueError: If an output is a symlink, aliases the input, or the
            Markdown changes during rendering.

    """
    if path.is_symlink():
        msg: str = "Refusing to replace a symbolic-link TODO file."
        raise ValueError(msg)
    before: stat_result = path.stat()
    source: str = path.read_text(encoding="utf-8")
    normalized: str = normalize(text=source) if normalize_tasks else source
    updated: str = update(text=normalized)
    output: Path = path.with_suffix(suffix=".html")
    if html and output == path:
        msg = "Markdown input and HTML output must be different."
        raise ValueError(msg)
    if html and output.is_symlink():
        msg = "Refusing to replace a symbolic-link HTML file."
        raise ValueError(msg)
    rendered: str = render_html(text=updated) if html else ""
    html_changed: bool = html and (
        not output.exists() or output.read_text(encoding="utf-8") != rendered
    )
    changed: bool = source != updated or html_changed
    if check or not changed:
        return changed
    after: stat_result = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or path.read_text(encoding="utf-8") != source:
        msg = "TODO changed during rendering; retry after the edit."
        raise ValueError(msg)
    if source != updated:
        atomic_write(path=path, text=updated)
    if html_changed:
        if output.is_symlink():
            msg = "Refusing to replace a symbolic-link HTML file."
            raise ValueError(msg)
        atomic_write(path=output, text=rendered)
    return changed
