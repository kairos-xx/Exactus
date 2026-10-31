# Copyright (c) 2026 João Lopes.
"""Provide the transactional runtime embedded in project-delta PYZ files."""

from argparse import ArgumentParser, Namespace
from difflib import unified_diff
from hashlib import sha256
from importlib.resources import files
from importlib.resources.abc import Traversable
from json import dumps, load
from os import environ
from pathlib import Path, PurePosixPath
from re import Match, sub
from shutil import copy2, copytree, rmtree
from stat import S_IMODE
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import TYPE_CHECKING, TypedDict, cast

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from _hashlib import HASH
    from collections.abc import Iterable
sys: ModuleType = __import__("sys")
type EntryState = tuple[str, int, str, str] | None
type EntryData = dict[str, int | str]
type OperationValue = str | None | EntryData
type OperationData = dict[str, OperationValue]
type ManifestValue = (
    str | int | bool | None | list[EntryData] | list[OperationData]
)
type ManifestData = dict[str, ManifestValue]


class Arguments(Namespace):
    """Store fully typed command-line arguments for the patch runtime.

    Attributes:
        root: Optional destination-root override supplied at invocation time.
        dry_run: Whether operations are reported without filesystem mutation.
        force: Whether destination precondition conflicts are ignored.
        conflict: Policy used to handle destination precondition conflicts.
        list: Whether patch operations are listed without applying the patch.
        info: Whether formatted manifest information is written to stdout.
        json: Whether compact machine-readable manifest JSON is emitted.
        verify: Whether only destination preconditions are verified.
        diff: Whether a read-only unified content diff is rendered.
        no_color: Whether ANSI colors are disabled in rendered diff output.
        diff_context: Number of unchanged context lines around each diff hunk.

    """

    root: Path | None
    dry_run: bool
    force: bool
    conflict: str
    list: bool
    info: bool
    json: bool
    verify: bool
    diff: bool
    no_color: bool
    diff_context: int


class ResultData(TypedDict):
    """Describe the JSON result emitted after successful application.

    Attributes:
        added: Project-relative paths added by the patch.
        changed: Project-relative paths modified by the patch.
        removed: Project-relative paths removed by the patch.
        moved: Project-relative paths moved by the patch.
        skipped: Project-relative paths skipped during patch application.
        conflicts: Precondition conflicts encountered during application.
        bytes_written: Total payload bytes written while staging the patch.
        verified: Whether post-application verification completed successfully.
        rolled_back: Whether the patch application was rolled back.

    """

    added: list[str]
    changed: list[str]
    removed: list[str]
    moved: list[str]
    skipped: list[str]
    conflicts: list[str]
    bytes_written: int
    verified: bool
    rolled_back: bool


def _manifest() -> tuple[Traversable, ManifestData]:
    """Load and type the manifest bundled beside the runtime.

    Returns:
        Tuple containing the patch-data package and decoded manifest.

    """
    package: Traversable = files("patch_data")
    with package.joinpath("manifest.json").open(
        mode="r",
        encoding="utf-8",
    ) as stream:
        manifest: ManifestData = cast(typ="ManifestData", val=load(fp=stream))
    return package, manifest


def _operations(*, manifest: ManifestData) -> list[OperationData]:
    """Return typed operation data from a decoded manifest.

    Args:
        manifest: Decoded patch manifest.

    Returns:
        Ordered list of path-level patch operations.

    Raises:
        TypeError: If the manifest operation member has an invalid type.

    """
    value: ManifestValue = manifest["operations"]
    if not isinstance(value, list):
        msg: str = "Manifest operations must be a list."
        raise TypeError(msg)
    return cast(typ="list[OperationData]", val=value)


def _entry(*, operation: OperationData, key: str) -> EntryData | None:
    """Read an optional entry mapping from an operation.

    Args:
        operation: Manifest operation containing the requested member.
        key: Operation member name, normally ``before`` or ``after``.

    Returns:
        Entry mapping or ``None`` when that state is absent.

    Raises:
        TypeError: If the member is neither an entry mapping nor ``None``.

    """
    value: OperationValue = operation[key]
    if value is None:
        return None
    if not isinstance(value, dict):
        msg: str = f"Operation member {key!r} must be an entry object."
        raise TypeError(msg)
    return value


def _text(*, mapping: EntryData, key: str, default: str = "") -> str:
    """Read a string from an embedded manifest entry.

    Args:
        mapping: Entry mapping containing the requested member.
        key: Member name expected to contain text.
        default: Value used when the member is absent.

    Returns:
        String value stored under ``key`` or ``default`` when absent.

    Raises:
        TypeError: If the selected member is not a string.

    """
    value: int | str = mapping.get(key, default)
    if not isinstance(value, str):
        msg: str = f"Entry member {key!r} must be a string."
        raise TypeError(msg)
    return value


def _mode(*, mapping: EntryData) -> int:
    """Read and validate the permission mode from an entry mapping.

    Args:
        mapping: Entry mapping containing a ``mode`` member.

    Returns:
        Integer filesystem permission mode.

    Raises:
        TypeError: If the mode member is not an integer.

    """
    value: int | str = mapping["mode"]
    if not isinstance(value, int):
        msg: str = "Entry mode must be an integer."
        raise TypeError(msg)
    return value


def _operation_text(*, operation: OperationData, key: str) -> str | None:
    """Read an optional string member from an operation mapping.

    Args:
        operation: Operation mapping containing the requested member.
        key: Member name expected to contain text or ``None``.

    Returns:
        String value or ``None``.

    Raises:
        TypeError: If the member contains an unsupported value type.

    """
    value: OperationValue = operation[key]
    if value is None or isinstance(value, str):
        return value
    msg: str = f"Operation member {key!r} must be text or null."
    raise TypeError(msg)


def safe(*, root: Path, relative: str) -> Path:
    """Resolve a manifest path while preventing project-root traversal.

    Args:
        root: Existing destination project root.
        relative: Manifest path expected to remain below ``root``.

    Returns:
        Destination path corresponding to ``relative``.

    Raises:
        ValueError: If the path is empty, absolute, traverses upward, or
            resolves through a parent outside the destination root.

    """
    pure: PurePosixPath = PurePosixPath(relative)
    if not pure.parts or pure.is_absolute() or ".." in pure.parts:
        msg: str = f"Path is outside project root: {relative!r}"
        raise ValueError(msg)
    target: Path = root.joinpath(*pure.parts)
    resolved_root: Path = root.resolve(strict=True)
    resolved_parent: Path = target.parent.resolve(strict=False)
    if not resolved_parent.is_relative_to(resolved_root):
        msg = f"Path is outside project root: {relative!r}"
        raise ValueError(msg)
    return target


def digest(*, path: Path) -> str:
    """Calculate the SHA-256 digest of a filesystem file.

    Args:
        path: Existing regular file whose bytes should be hashed.

    Returns:
        SHA-256 hexadecimal digest of the file contents.

    """
    value: HASH = sha256()
    with path.open(mode="rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def state(*, path: Path) -> EntryState:
    """Capture the comparable state of a destination filesystem entry.

    Args:
        path: Filesystem path whose current state should be inspected.

    Returns:
        Comparable entry-state tuple, or ``None`` when the path is absent.

    """
    if path.is_symlink():
        target: str = path.readlink().as_posix()
        return (
            "symlink",
            S_IMODE(path.lstat().st_mode),
            sha256(data=target.encode(encoding="utf-8")).hexdigest(),
            target,
        )
    if path.is_dir():
        return ("directory", S_IMODE(path.stat().st_mode), "", "")
    if path.is_file():
        return ("file", S_IMODE(path.stat().st_mode), digest(path=path), "")
    return None


def expected(*, raw: EntryData | None) -> EntryState:
    """Convert manifest entry data into a comparable expected state.

    Args:
        raw: Manifest entry mapping or ``None`` for an absent path.

    Returns:
        Comparable expected entry state.

    """
    if raw is None:
        return None
    return (
        _text(mapping=raw, key="kind"),
        _mode(mapping=raw),
        _text(mapping=raw, key="sha256"),
        _text(mapping=raw, key="link_target"),
    )


def remove(*, path: Path) -> None:
    """Remove a file, symlink, or directory tree when present.

    Args:
        path: Filesystem path to remove.

    """
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        rmtree(path=path)


def restore(*, source: Path, target: Path) -> None:
    """Restore one transaction backup entry to its destination path.

    Args:
        source: Backup path containing the state to restore.
        target: Destination path that should receive the backup state.

    """
    remove(path=target)
    if source.is_symlink():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(target=source.readlink())
    elif source.is_dir():
        copytree(src=source, dst=target, symlinks=True)
    elif source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(src=source, dst=target, follow_symlinks=False)


def arguments() -> Arguments:
    """Parse command-line controls accepted by an executable patch.

    Returns:
        Fully typed runtime argument namespace.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Inspect, verify, or transactionally apply this project delta."
        ),
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--conflict",
        choices=("abort", "overwrite", "skip", "backup"),
        default="abort",
    )
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--info", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--diff-context", type=int, default=3)
    namespace: Arguments = Arguments()
    parser.parse_args(namespace=namespace)
    return namespace


def diff_blob(*, package: Traversable, raw: EntryData | None) -> bytes:
    """Read the embedded file bytes represented by a manifest entry.

    Args:
        package: Traversable patch-data package containing payload blobs.
        raw: Optional manifest entry whose file payload should be read.

    Returns:
        File bytes, or empty bytes for absent and non-file entries.

    """
    if raw is None or _text(mapping=raw, key="kind") != "file":
        return b""
    blob: str = _text(mapping=raw, key="blob")
    with package.joinpath("blobs", blob).open(mode="rb") as stream:
        return stream.read()


def paint(*, text: str, code: str, enabled: bool) -> str:
    """Wrap text in an ANSI color sequence when coloring is enabled.

    Args:
        text: Text to decorate.
        code: ANSI Select Graphic Rendition code.
        enabled: Whether ANSI decoration should be emitted.

    Returns:
        Decorated text when enabled, otherwise the original text.

    """
    return f"\033[{code}m{text}\033[0m" if enabled else text


def _syntax_match(*, match: Match[str], base: str) -> str:
    """Decorate one lightweight syntax token in a diff line.

    Args:
        match: Regular-expression match identifying a syntax token.
        base: ANSI code restoring the surrounding diff-line color.

    Returns:
        Highlighted token followed by the surrounding base color.

    """
    return f"\033[33m{match.group(0)}\033[0m{base}"


def syntax(*, text: str, path: str, enabled: bool, base: str) -> str:
    """Apply lightweight syntax highlighting to supported textual files.

    Args:
        text: Diff line to decorate.
        path: File path used to select supported textual syntaxes.
        enabled: Whether syntax highlighting should be applied.
        base: ANSI code restoring the surrounding diff-line color.

    Returns:
        Original or syntax-highlighted diff line.

    """
    suffixes: tuple[str, ...] = (
        ".js",
        ".mjs",
        ".cjs",
        ".css",
        ".html",
        ".htm",
        ".py",
        ".json",
        ".toml",
        ".xml",
    )
    if not enabled or not path.lower().endswith(suffixes):
        return text
    pattern: str = (
        r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
        r"\b(?:true|false|null|None|True|False|class|def|return|"
        r"import|from|const|let|var|function|if|else|for|while|"
        r"async|await|new|display|position|color|background|DOCTYPE)"
        r"\b|\b\d+(?:\.\d+)?\b|#[0-9A-Fa-f]{3,8}\b)"
    )
    return sub(
        pattern=pattern,
        repl=lambda match: _syntax_match(match=match, base=base),
        string=text,
    )


def _diff_code(*, line: str) -> str:
    """Select an ANSI color code for one unified-diff line.

    Args:
        line: Unified-diff line including its structural prefix.

    Returns:
        ANSI color code appropriate for the line category.

    """
    if line.startswith(("---", "+++")):
        return "36"
    if line.startswith("@@"):
        return "35"
    if line.startswith("+"):
        return "32"
    if line.startswith("-"):
        return "31"
    return "0"


def render_diff(
    *,
    package: Traversable,
    manifest: ManifestData,
    color: bool,
    context: int,
) -> str:
    """Render the embedded delta as a read-only unified diff.

    Args:
        package: Traversable patch-data package containing payload blobs.
        manifest: Decoded patch manifest.
        color: Whether ANSI coloring and syntax highlighting are enabled.
        context: Number of unchanged context lines around textual hunks.

    Returns:
        Complete human-readable unified diff text.

    """
    chunks: list[str] = []
    for operation in _operations(manifest=manifest):
        path: str = _operation_text(operation=operation, key="path") or ""
        move_from: str | None = _operation_text(
            operation=operation,
            key="move_from",
        )
        before: EntryData | None = _entry(operation=operation, key="before")
        after: EntryData | None = _entry(operation=operation, key="after")
        chunks.append(
            paint(
                text=f"diff --git a/{path} b/{path}\n",
                code="34",
                enabled=color,
            ),
        )
        if move_from is not None:
            chunks.append(
                paint(
                    text=(f"rename from {move_from}\nrename to {path}\n"),
                    code="33",
                    enabled=color,
                ),
            )
        before_kind: str | None = (
            None if before is None else _text(mapping=before, key="kind")
        )
        after_kind: str | None = (
            None if after is None else _text(mapping=after, key="kind")
        )
        if (before_kind is not None and before_kind != "file") or (
            after_kind is not None and after_kind != "file"
        ):
            old: str = "absent" if before is None else before_kind or ""
            new: str = "absent" if after is None else after_kind or ""
            chunks.append(
                paint(text=f"{old} -> {new}\n", code="33", enabled=color),
            )
            continue
        old_bytes: bytes = diff_blob(package=package, raw=before)
        new_bytes: bytes = diff_blob(package=package, raw=after)
        if b"\0" in old_bytes or b"\0" in new_bytes:
            chunks.append(
                paint(text="Binary files differ\n", code="33", enabled=color),
            )
            continue
        try:
            old_text: str = old_bytes.decode(encoding="utf-8")
            new_text: str = new_bytes.decode(encoding="utf-8")
        except UnicodeDecodeError:
            chunks.append(
                paint(text="Binary files differ\n", code="33", enabled=color),
            )
            continue
        old_name: str = (
            "/dev/null" if before is None else f"a/{move_from or path}"
        )
        new_name: str = "/dev/null" if after is None else f"b/{path}"
        lines: Iterable[str] = unified_diff(
            a=old_text.splitlines(keepends=True),
            b=new_text.splitlines(keepends=True),
            fromfile=old_name,
            tofile=new_name,
            n=context,
        )
        for line in lines:
            code: str = _diff_code(line=line)
            base: str = (
                f"\033[{code}m" if color and code in {"31", "32"} else ""
            )
            decorated: str = syntax(
                text=line,
                path=path,
                enabled=color and code in {"31", "32", "0"},
                base=base,
            )
            chunks.append(
                paint(
                    text=decorated,
                    code=code,
                    enabled=color and code != "0",
                ),
            )
    return "".join(chunks)


def _root(*, args: Arguments, manifest: ManifestData) -> Path:
    """Resolve the effective project root for this runtime invocation.

    Args:
        args: Parsed runtime arguments.
        manifest: Decoded patch manifest containing the embedded default root.

    Returns:
        Existing absolute project root selected for patch operations.

    Raises:
        NotADirectoryError: If the resolved root is not an existing directory.
        TypeError: If the embedded project root is not text.

    """
    if args.root is None:
        value: ManifestValue = manifest["project_root"]
        if not isinstance(value, str):
            msg: str = "Manifest project_root must be a string."
            raise TypeError(msg)
        root: Path = Path(value).expanduser().resolve(strict=True)
    else:
        candidate: Path = args.root.expanduser()
        root = (
            candidate if candidate.is_absolute() else Path.cwd() / candidate
        ).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    return root


def _conflicts(
    *,
    root: Path,
    operations: list[OperationData],
    args: Arguments,
) -> tuple[list[str], set[str]]:
    """Evaluate destination preconditions and selected conflict policy.

    Args:
        root: Effective destination project root.
        operations: Ordered manifest operations to validate.
        args: Parsed runtime controls including force and conflict policy.

    Returns:
        Tuple containing conflicting source paths and skipped destinations.

    Raises:
        RuntimeError: If an abort-policy precondition conflict is detected.

    """
    conflicts: list[str] = []
    skipped: set[str] = set()
    for operation in operations:
        path: str = _operation_text(operation=operation, key="path") or ""
        move_from: str | None = _operation_text(
            operation=operation,
            key="move_from",
        )
        source_relative: str = move_from or path
        target: Path = safe(root=root, relative=source_relative)
        before: EntryData | None = _entry(operation=operation, key="before")
        if state(path=target) != expected(raw=before):
            conflicts.append(source_relative)
            if not args.force and args.conflict == "abort":
                msg: str = f"Precondition conflict: {source_relative}"
                raise RuntimeError(msg)
            if not args.force and args.conflict == "skip":
                skipped.add(path)
    return conflicts, skipped


def _stage(
    *,
    package: Traversable,
    operations: list[OperationData],
    skipped: set[str],
    stage: Path,
) -> int:
    """Materialize all non-removal target entries in a staging directory.

    Args:
        package: Traversable patch-data package containing payload blobs.
        operations: Ordered manifest operations to stage.
        skipped: Destination paths excluded by conflict policy.
        stage: Empty transaction staging directory.

    Returns:
        Number of file payload bytes materialized into staging.

    Raises:
        RuntimeError: If an embedded file payload fails digest validation.

    """
    bytes_written: int = 0
    for operation in operations:
        path: str = _operation_text(operation=operation, key="path") or ""
        if path in skipped:
            continue
        after: EntryData | None = _entry(operation=operation, key="after")
        if after is None:
            continue
        staged: Path = safe(root=stage, relative=path)
        staged.parent.mkdir(parents=True, exist_ok=True)
        kind: str = _text(mapping=after, key="kind")
        if kind == "directory":
            staged.mkdir(parents=True, exist_ok=True)
            staged.chmod(mode=_mode(mapping=after))
        elif kind == "symlink":
            staged.symlink_to(target=_text(mapping=after, key="link_target"))
        else:
            blob: str = _text(mapping=after, key="blob")
            with package.joinpath("blobs", blob).open(
                mode="rb",
            ) as blob_stream:
                content: bytes = blob_stream.read()
            if sha256(data=content).hexdigest() != _text(
                mapping=after,
                key="sha256",
            ):
                msg: str = f"Corrupt payload: {path}"
                raise RuntimeError(msg)
            staged.write_bytes(data=content)
            staged.chmod(mode=_mode(mapping=after))
            bytes_written += len(content)
    return bytes_written


def _backup(
    *,
    root: Path,
    backup: Path,
    operations: list[OperationData],
    skipped: set[str],
) -> set[str]:
    """Copy every touched existing destination entry into backup storage.

    Args:
        root: Effective destination project root.
        backup: Empty transaction backup directory.
        operations: Ordered manifest operations that may touch destinations.
        skipped: Destination paths excluded by conflict policy.

    Returns:
        Set of every project-relative path covered by the transaction.

    """
    touched: set[str] = set()
    for operation in operations:
        path: str = _operation_text(operation=operation, key="path") or ""
        if path in skipped:
            continue
        move_from: str | None = _operation_text(
            operation=operation,
            key="move_from",
        )
        relatives: set[str] = {path}
        if move_from is not None:
            relatives.add(move_from)
        for relative in relatives:
            target: Path = safe(root=root, relative=relative)
            if target.exists() or target.is_symlink():
                saved: Path = safe(root=backup, relative=relative)
                if not (saved.exists() or saved.is_symlink()):
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink():
                        saved.symlink_to(target=target.readlink())
                    elif target.is_dir():
                        copytree(src=target, dst=saved, symlinks=True)
                    else:
                        copy2(src=target, dst=saved, follow_symlinks=False)
            touched.add(relative)
    return touched


def _apply(
    *,
    root: Path,
    stage: Path,
    operations: list[OperationData],
    skipped: set[str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Commit staged entries and removals to the destination project.

    Args:
        root: Effective destination project root.
        stage: Transaction staging directory containing target entries.
        operations: Ordered manifest operations to commit.
        skipped: Destination paths excluded by conflict policy.

    Returns:
        Lists of added, changed, removed, and moved paths.

    """
    added: list[str] = []
    changed: list[str] = []
    removed: list[str] = []
    moved: list[str] = []
    for operation in operations:
        path: str = _operation_text(operation=operation, key="path") or ""
        if path in skipped:
            continue
        move_from: str | None = _operation_text(
            operation=operation,
            key="move_from",
        )
        if move_from is not None:
            remove(path=safe(root=root, relative=move_from))
            moved.append(f"{move_from}->{path}")
        target: Path = safe(root=root, relative=path)
        before: EntryData | None = _entry(operation=operation, key="before")
        after: EntryData | None = _entry(operation=operation, key="after")
        remove(path=target)
        if after is None:
            removed.append(path)
            continue
        staged: Path = safe(root=stage, relative=path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if _text(mapping=after, key="kind") == "directory":
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(mode=_mode(mapping=after))
        else:
            staged.replace(target=target)
        (added if before is None else changed).append(path)
    return added, changed, removed, moved


def _verify_postconditions(
    *,
    root: Path,
    operations: list[OperationData],
    skipped: set[str],
) -> None:
    """Verify every applied destination against its manifest postcondition.

    Args:
        root: Effective destination project root.
        operations: Ordered manifest operations that were applied.
        skipped: Destination paths excluded by conflict policy.

    Raises:
        RuntimeError: If any destination differs from its expected target
            state after the commit phase.

    """
    for operation in operations:
        path: str = _operation_text(operation=operation, key="path") or ""
        if path in skipped:
            continue
        after: EntryData | None = _entry(operation=operation, key="after")
        if state(path=safe(root=root, relative=path)) != expected(raw=after):
            msg: str = f"Postcondition failed: {path}"
            raise RuntimeError(msg)


def _rollback(*, root: Path, backup: Path, touched: set[str]) -> None:
    """Restore every touched destination path from transaction backups.

    Args:
        root: Effective destination project root.
        backup: Transaction backup directory.
        touched: Project-relative paths affected by the failed transaction.

    """
    descending: list[str] = sorted(
        touched,
        key=lambda value: len(PurePosixPath(value).parts),
        reverse=True,
    )
    for relative in descending:
        remove(path=safe(root=root, relative=relative))
    ascending: list[str] = sorted(
        touched,
        key=lambda value: len(PurePosixPath(value).parts),
    )
    for relative in ascending:
        saved: Path = safe(root=backup, relative=relative)
        if saved.exists() or saved.is_symlink():
            restore(source=saved, target=safe(root=root, relative=relative))


def _operation_kind(*, operation: OperationData) -> str:
    """Return the human-readable operation category for list output.

    Args:
        operation: Manifest operation to classify.

    Returns:
        One of ``MOVE``, ``ADD``, ``REMOVE``, or ``CHANGE``.

    """
    if _operation_text(operation=operation, key="move_from") is not None:
        return "MOVE"
    if _entry(operation=operation, key="before") is None:
        return "ADD"
    if _entry(operation=operation, key="after") is None:
        return "REMOVE"
    return "CHANGE"


def _inspection_status(
    *,
    args: Arguments,
    package: Traversable,
    manifest: ManifestData,
    operations: list[OperationData],
) -> int | None:
    """Run a requested read-only inspection operation.

    Args:
        args: Parsed runtime arguments.
        package: Package containing the patch payload resources.
        manifest: Parsed patch manifest.
        operations: Validated manifest operations.

    Returns:
        Process status code when an inspection operation was requested,
        otherwise ``None``.

    Raises:
        ValueError: If diff context is negative.

    """
    if args.diff:
        if args.diff_context < 0:
            msg: str = "--diff-context must be zero or greater"
            raise ValueError(msg)
        _ = sys.stdout.write(
            render_diff(
                package=package,
                manifest=manifest,
                color=not args.no_color and "NO_COLOR" not in environ,
                context=args.diff_context,
            ),
        )
        return 0
    if args.info or args.json:
        _ = sys.stdout.write(
            dumps(
                obj=manifest,
                indent=2 if args.info else None,
                sort_keys=True,
            )
            + "\n",
        )
        return 0
    if args.list:
        for operation in operations:
            path: str = _operation_text(operation=operation, key="path") or ""
            move_from: str | None = _operation_text(
                operation=operation,
                key="move_from",
            )
            suffix: str = f" <- {move_from}" if move_from is not None else ""
            _ = sys.stdout.write(
                f"{_operation_kind(operation=operation):6} {path}{suffix}\n",
            )
        return 0
    return None


def main() -> int:
    """Run patch inspection, verification, or transactional application.

    Returns:
        Process status code. Successful operations return zero, while verify
        mode returns two when precondition conflicts are present.

    """
    args: Arguments = arguments()
    package: Traversable
    manifest: ManifestData
    package, manifest = _manifest()
    operations: list[OperationData] = _operations(manifest=manifest)
    inspection_status: int | None = _inspection_status(
        args=args,
        package=package,
        manifest=manifest,
        operations=operations,
    )
    if inspection_status is not None:
        return inspection_status
    root: Path = _root(args=args, manifest=manifest)
    conflicts: list[str]
    skipped: set[str]
    conflicts, skipped = _conflicts(
        root=root,
        operations=operations,
        args=args,
    )
    if args.verify:
        _ = sys.stdout.write(
            f"verified preconditions; conflicts={len(conflicts)}\n",
        )
        return 0 if not conflicts else 2
    if args.dry_run:
        for operation in operations:
            path: str = _operation_text(operation=operation, key="path") or ""
            action: str = "SKIP" if path in skipped else "APPLY"
            _ = sys.stdout.write(f"{action} {path}\n")
        return 0
    added: list[str] = []
    changed: list[str] = []
    removed: list[str] = []
    moved: list[str] = []
    bytes_written: int = 0
    with TemporaryDirectory(
        prefix="project-delta-",
        dir=root.parent,
    ) as temporary:
        work: Path = Path(temporary)
        backup: Path = work / "backup"
        stage: Path = work / "stage"
        backup.mkdir()
        stage.mkdir()
        touched: set[str] = set()
        try:
            bytes_written = _stage(
                package=package,
                operations=operations,
                skipped=skipped,
                stage=stage,
            )
            touched = _backup(
                root=root,
                backup=backup,
                operations=operations,
                skipped=skipped,
            )
            added, changed, removed, moved = _apply(
                root=root,
                stage=stage,
                operations=operations,
                skipped=skipped,
            )
            _verify_postconditions(
                root=root,
                operations=operations,
                skipped=skipped,
            )
        except BaseException:
            _rollback(root=root, backup=backup, touched=touched)
            raise
    result: ResultData = {
        "added": added,
        "changed": changed,
        "removed": removed,
        "moved": moved,
        "skipped": sorted(skipped),
        "conflicts": conflicts,
        "bytes_written": bytes_written,
        "verified": True,
        "rolled_back": False,
    }
    if args.conflict == "backup" and conflicts:
        _ = sys.stdout.write("conflicts were backed up transactionally\n")
    _ = sys.stdout.write(dumps(obj=result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
