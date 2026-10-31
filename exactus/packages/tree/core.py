# Copyright (c) 2026 João Lopes.
"""Render directories, zip archives and path lists as ``TREE.txt`` text.

Every entry shows its name plus aligned columns for a human-readable
size and a ``dd Mon yyyy HH:MM`` modified date; directories aggregate
descendant file sizes and the latest descendant mtime, matching
``exactus/scripts/inventory`` output.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, tzinfo
from fnmatch import fnmatch
from pathlib import Path
from sys import stdout
from typing import TYPE_CHECKING, Final, final
from zipfile import ZipFile, is_zipfile

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Sequence
    from os import stat_result
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


type _Tree = dict[str, "tuple[int, float] | _Tree"]
type Members = Mapping[str, "tuple[int, float] | None"]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        skipped_names: Grouped module constant.
        skipped_directories: Grouped module constant.
        magic: Grouped module constant.

    """

    skipped_names: Final[frozenset[str]] = frozenset({".DS_Store"})
    skipped_directories: Final[frozenset[str]] = frozenset({"__pycache__"})
    magic: Final[frozenset[str]] = frozenset("*?[")


def human_size(*, size: int) -> str:
    """Format a byte count compactly, e.g. ``512B``/``23KB``/``4.6MB``.

    Args:
        size: Byte count.

    Returns:
        Human-readable size; decimal units drop a trailing ``.0``.

    """
    size_base: Final[int] = 1000
    value: float = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < size_base or unit == "GB":
            return (
                f"{size}B"
                if unit == "B"
                else f"{f'{value:.1f}'.removesuffix('.0')}{unit}"
            )
        value /= size_base
    return f"{size}B"


def _keep(
    *,
    member: str,
    include: Sequence[str],
    exclude: Sequence[str],
) -> bool:
    """Return whether a member survives the include/exclude globs.

    Args:
        member: Posix-style member label.
        include: Glob whitelist; empty keeps everything.
        exclude: Glob blacklist always applied.

    Returns:
        ``True`` when the member is rendered.

    """
    if include and (
        not any(fnmatch(name=member, pat=pattern) for pattern in include)
    ):
        return False
    return not any(fnmatch(name=member, pat=pattern) for pattern in exclude)


def _directory_members(*, source: Path) -> dict[str, tuple[int, float] | None]:
    """Collect every file under ``source`` as member entries.

    Args:
        source: Directory to walk.

    Returns:
        Posix-relative member labels mapped to ``(size, mtime)``.

    """
    members: dict[str, tuple[int, float] | None] = {}
    candidate: Path
    for candidate in sorted(source.rglob(pattern="*")):
        if (
            not candidate.is_file()
            or Constants.skipped_directories.intersection(candidate.parts)
            or candidate.name in Constants.skipped_names
        ):
            continue
        stat: stat_result = candidate.stat()
        members[candidate.relative_to(source).as_posix()] = (
            stat.st_size,
            stat.st_mtime,
        )
    return members


def _zip_members(*, source: Path) -> dict[str, tuple[int, float] | None]:
    """Collect a zip archive's members as entries.

    Args:
        source: Zip archive to inspect.

    Returns:
        Member labels mapped to ``(size, mtime)``; ``date_time`` stores
        local time without a zone, so it is used as-is.

    """
    members: dict[str, tuple[int, float] | None] = {}
    local_tz: tzinfo | None = datetime.now().astimezone().tzinfo
    with ZipFile(file=source) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            when: datetime = datetime(*info.date_time, tzinfo=local_tz)
            members[info.filename] = (info.file_size, when.timestamp())
    return members


def _listed_members(
    *,
    items: Sequence[str | Path],
    root: Path | None,
) -> dict[str, tuple[int, float] | None]:
    """Resolve an explicit member list to entries.

    Args:
        items: Member labels or paths. Strings stay verbatim; ``Path``
            items are relativized against ``root`` when possible.
        root: Base used to stat string members and relativize paths.

    Returns:
        Member labels mapped to ``(size, mtime)``; missing members
        record ``(0, 0.0)``.

    """
    members: dict[str, tuple[int, float] | None] = {}
    item: str | Path
    for item in items:
        if isinstance(item, Path):
            path: Path = item.expanduser().resolve()
            try:
                label: str = (
                    path.relative_to(root.resolve()).as_posix()
                    if root is not None
                    else path.name
                )
            except ValueError:
                label = path.name
        else:
            label = item
            path = root / item if root is not None else Path(item)
        members[label] = (
            ((stat := path.stat()).st_size, stat.st_mtime)
            if path.is_file()
            else (0, 0.0)
        )
    return members


def members_for(
    *,
    source: Path | Sequence[str | Path] | Members,
    root: Path | None = None,
) -> dict[str, tuple[int, float] | None]:
    """Resolve any supported source into member entries.

    Args:
        source: Directory, zip archive, single file, explicit list or
            ``label -> (size, mtime) | None`` mapping; ``None`` marks an
            explicit directory entry.
        root: Base directory for relative member labels and stats.

    Returns:
        Member labels mapped to ``(size, mtime)`` or ``None`` for
        explicit directory entries.

    """
    if isinstance(source, Mapping):
        return dict(source)
    if isinstance(source, Path):
        resolved: Path = source.expanduser().resolve()
        if resolved.is_dir():
            return _directory_members(source=resolved)
        if resolved.suffix == ".zip" and is_zipfile(filename=resolved):
            return _zip_members(source=resolved)
        stat: stat_result = resolved.stat()
        anchored: Path | None = root.resolve() if root is not None else None
        return {
            resolved.relative_to(anchored).as_posix()
            if anchored is not None and resolved.is_relative_to(anchored)
            else resolved.name: (stat.st_size, stat.st_mtime),
        }
    return _listed_members(items=source, root=root)


def _tree_stats(*, node: _Tree) -> tuple[int, float]:
    """Aggregate descendant file sizes and the latest descendant mtime.

    Args:
        node: Tree node; tuples are files, dicts directories.

    Returns:
        ``(total bytes, latest mtime)`` under ``node``.

    """
    total: int = 0
    latest: float = 0.0
    for value in node.values():
        if isinstance(value, dict):
            size, mtime = _tree_stats(node=value)
            total += size
            latest = max(latest, mtime)
        else:
            total += value[0]
            latest = max(latest, value[1])
    return (total, latest)


def _tree_rows(
    *,
    node: _Tree,
    prefix: str,
    rows: list[tuple[str, int, float]],
) -> None:
    """Append rendered tree rows for ``node``'s children.

    Args:
        node: Tree node whose children are rendered.
        prefix: Indentation prefix prepended to each row.
        rows: Accumulated ``(label, size, mtime)`` rows.

    """
    children: list[tuple[str, bool]] = sorted(
        ((name, isinstance(value, dict)) for name, value in node.items()),
        key=lambda child: child[0],
    )
    for index, (child_name, is_dir) in enumerate(iterable=children):
        last: bool = index == len(children) - 1
        branch: str = "└── " if last else "├── "
        value: tuple[int, float] | _Tree = node[child_name]
        size, mtime = (
            _tree_stats(node=value) if isinstance(value, dict) else value
        )
        rows.append(
            (
                f"{prefix}{branch}{child_name}{('/' if is_dir else '')}",
                size,
                mtime,
            ),
        )
        if isinstance(value, dict):
            _tree_rows(
                node=value,
                prefix=prefix + ("    " if last else "│   "),
                rows=rows,
            )


def render_tree(
    *,
    source: Path | Sequence[str | Path] | Members,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    name: str | None = None,
    root: Path | None = None,
) -> str:
    """Render ``source`` as a ``TREE.txt``-style listing.

    Args:
        source: Directory, ``.zip`` archive, single file, explicit list
            of member labels/``Path`` objects, or a
            ``label -> (size, mtime) | None`` mapping; a ``None`` value
            or trailing ``/`` marks an explicit directory entry.
        include: Glob whitelist applied to member labels; empty keeps
            everything.
        exclude: Glob blacklist applied to member labels.
        name: Label of the rendered root row; defaults to the source
            name or ``members`` for explicit lists.
        root: Base directory used to stat string members and relativize
            ``Path`` items.

    Returns:
        Tree text ending with a newline.

    """
    members: dict[str, tuple[int, float] | None] = members_for(
        source=source,
        root=root,
    )
    nested: _Tree = {}
    member: str
    for member in sorted(members):
        if not _keep(
            member=member.rstrip("/"),
            include=include,
            exclude=exclude,
        ):
            continue
        node: _Tree = nested
        parts: list[str] = member.rstrip("/").split(sep="/")
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            child: tuple[int, float] | _Tree = node[part]
            if isinstance(child, dict):
                node = child
        value: tuple[int, float] | None = members[member]
        if member.endswith("/") or value is None:
            if parts[-1] not in node:
                node[parts[-1]] = {}
        else:
            node[parts[-1]] = value
    title: str = (
        name
        if name is not None
        else source.name
        if isinstance(source, Path)
        else "members"
    )
    trace(step=f"tree: {title} ({len(members)} members)", depth=2)
    rows: list[tuple[str, int, float]] = [
        (f"{title}/", *_tree_stats(node=nested)),
    ]
    _tree_rows(node=nested, prefix="", rows=rows)
    width: int = max((len(label) for label, _size, _mtime in rows)) + 2
    lines: list[str] = []
    for label, size, mtime in rows:
        when: datetime = datetime.fromtimestamp(mtime, tz=UTC).astimezone()
        lines.append(
            f"{label:<{width}}"
            f"{human_size(size=size):>8}"
            f"  "
            f"{when:%d %b %Y %H:%M}",
        )
    return "\n".join(lines) + "\n"


def _expand(*, patterns: Sequence[str]) -> list[Path]:
    """Expand wildcard path arguments into concrete paths.

    Args:
        patterns: Literal paths or glob patterns.

    Returns:
        Resolved existing paths in sorted order.

    """
    found: list[Path] = []
    pattern: str
    for pattern in patterns:
        parts: tuple[str, ...] = Path(pattern).parts
        magic: int = next(
            (
                index
                for index, part in enumerate(iterable=parts)
                if Constants.magic.intersection(part)
            ),
            len(parts),
        )
        if magic == len(parts):
            candidate: Path = Path(pattern).expanduser()
            if candidate.exists():
                found.append(candidate)
            continue
        base: Path = Path(*parts[:magic]).expanduser() if magic else Path()
        found.extend(sorted(base.glob(pattern="/".join(parts[magic:]))))
    return found


def main(*, arguments: Sequence[str] | None = None) -> int:
    """Render trees for directories, zips and glob expansions.

    Args:
        arguments: Command-line arguments excluding the program name.

    Returns:
        ``0`` when at least one tree was rendered, ``1`` otherwise.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="tree",
        description=(
            "Render directories, zip archives and glob expansions "
            "as TREE.txt-style listings."
        ),
    )
    parser.add_argument(
        "sources",
        nargs="*",
        metavar="PATH",
        help="Directories, .zip archives or glob patterns.",
    )
    parser.add_argument(
        "--include",
        "-i",
        dest="include",
        action="append",
        metavar="GLOB",
        help="Keep only member paths matching this glob (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        dest="exclude",
        action="append",
        metavar="GLOB",
        help="Drop member paths matching this glob (repeatable).",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write the listing to FILE instead of stdout.",
    )
    options: Namespace = parser.parse_args(
        args=list(arguments) if arguments is not None else None,
    )
    sources: list[Path] = _expand(patterns=tuple(options.sources))
    if not sources:
        parser.print_usage(file=stdout)
        return 1
    rendered: list[str] = []
    source: Path
    for source in sources:
        trace(step=f"tree: {source}", depth=1)
        rendered.append(
            render_tree(
                source=source,
                include=tuple(options.include or ()),
                exclude=tuple(options.exclude or ()),
            ),
        )
    text: str = "\n".join(rendered)
    if options.output is not None:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        _ = options.output.write_text(data=text, encoding="utf-8")
        trace(step=f"tree: wrote {options.output}", depth=1)
        return 0
    _written: int = stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
