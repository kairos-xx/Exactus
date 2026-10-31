# Copyright (c) 2026 João Lopes.
"""Build deterministic and transactional executable filesystem deltas."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatch
from hashlib import sha256
from importlib.resources import files
from json import dumps, loads
from pathlib import Path, PurePosixPath
from stat import S_IFLNK, S_IMODE, S_ISLNK
from typing import TYPE_CHECKING, Final, TypedDict, Unpack, cast
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

if TYPE_CHECKING:
    from _hashlib import HASH
    from os import stat_result
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type ManifestEntry = dict[str, int | str]
type ManifestOperation = dict[str, str | None | ManifestEntry]


class DeltaOptions(TypedDict, total=False):
    """Describe optional controls accepted while calculating a delta.

    Attributes:
        includes: Glob patterns selecting project-relative paths to include.
        excludes: Glob patterns selecting project-relative paths to exclude.
        detect_moves: Whether matching removals and additions become moves.

    """

    includes: Iterable[str]
    excludes: Iterable[str]
    detect_moves: bool


class Defaults:
    """Provide immutable constants used by snapshot and archive processing.

    Attributes:
        format_version: Current project-delta manifest format version.
        zip_timestamp: Fixed ZIP timestamp used for deterministic archives.
        symlink_kind_bits: Filesystem type bits identifying symbolic links.
        archive_mode_mask: Bit mask isolating archived permission bits.
        archive_kind_mask: Bit mask isolating the archived filesystem type.
        default_file_mode: Default permission mode for regular files.
        default_directory_mode: Default permission mode for directories.
        executable_archive_mode: Archived permission mode for executables.
        executable_output_mode: Filesystem mode for generated executable PYZs.

    """

    format_version: Final[int] = 2
    zip_timestamp: Final[tuple[int, int, int, int, int, int]] = (
        1980,
        1,
        1,
        0,
        0,
        0,
    )
    symlink_kind_bits: Final[int] = S_IFLNK
    archive_mode_mask: Final[int] = 0o7777
    archive_kind_mask: Final[int] = 0o170000
    default_file_mode: Final[int] = 0o644
    default_directory_mode: Final[int] = 0o755
    executable_archive_mode: Final[int] = 0o755
    executable_output_mode: Final[int] = 0o700


def _json_object(*, content: bytes) -> JsonObject:
    """Decode JSON bytes and require an object at the document root.

    Args:
        content: UTF-8 JSON document bytes to decode.

    Returns:
        Recursively typed JSON object containing the decoded document.

    Raises:
        TypeError: If the decoded document root is not a JSON object.

    """
    value: JsonValue = cast(typ="JsonValue", val=loads(s=content))
    if not isinstance(value, dict):
        msg: str = "JSON document root must be an object."
        raise TypeError(msg)
    return value


def _json_list(*, mapping: JsonObject, key: str) -> list[JsonValue]:
    """Read a required JSON list from an object.

    Args:
        mapping: JSON object containing the requested member.
        key: Member name expected to contain a JSON list.

    Returns:
        JSON list stored under ``key``.

    Raises:
        TypeError: If the member does not contain a JSON list.

    """
    value: JsonValue = mapping[key]
    if not isinstance(value, list):
        msg: str = f"JSON member {key!r} must be a list."
        raise TypeError(msg)
    return value


def _json_mapping(*, value: JsonValue, context: str) -> JsonObject:
    """Require a JSON value to be an object.

    Args:
        value: JSON value to validate.
        context: Human-readable description used in validation errors.

    Returns:
        The validated JSON object.

    Raises:
        TypeError: If ``value`` is not a JSON object.

    """
    if not isinstance(value, dict):
        msg: str = f"{context} must be an object."
        raise TypeError(msg)
    return value


def _json_string(
    *,
    mapping: JsonObject,
    key: str,
    default: str | None = None,
) -> str:
    """Read a required or defaulted string member from a JSON object.

    Args:
        mapping: JSON object containing the requested member.
        key: Member name expected to contain a string.
        default: Optional value returned when the member is absent.

    Returns:
        String stored under ``key`` or ``default`` when supplied.

    Raises:
        KeyError: If the member is absent and no default was supplied.
        TypeError: If the selected value is not a string.

    """
    if key not in mapping:
        if default is not None:
            return default
        raise KeyError(key)
    value: JsonValue = mapping[key]
    if not isinstance(value, str):
        msg: str = f"JSON member {key!r} must be a string."
        raise TypeError(msg)
    return value


def _json_int(*, mapping: JsonObject, key: str) -> int:
    """Read a required integer member from a JSON object.

    Args:
        mapping: JSON object containing the requested member.
        key: Member name expected to contain an integer.

    Returns:
        Integer stored under ``key``.

    Raises:
        TypeError: If the selected value is not an integer or is a boolean.

    """
    value: JsonValue = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        msg: str = f"JSON member {key!r} must be an integer."
        raise TypeError(msg)
    return value


def resolve_invocation_root(
    *,
    root: str | Path,
    cwd: Path | None = None,
) -> Path:
    """Resolve an application root against the invocation directory.

    Relative roots are intentionally resolved against the process invocation
    directory rather than the location of a generated patch archive.

    Args:
        root: Absolute or invocation-directory-relative project root.
        cwd: Invocation directory override, primarily for deterministic tests.

    Returns:
        Absolute normalized project root.

    """
    invocation_cwd: Path = Path.cwd() if cwd is None else cwd
    candidate: Path = Path(root)
    return (
        candidate.resolve()
        if candidate.is_absolute()
        else (invocation_cwd / candidate).resolve()
    )


class EntryKind(StrEnum):
    """Identify filesystem entry kinds representable by a snapshot.

    Attributes:
        FILE: Regular filesystem file containing byte content.
        DIRECTORY: Filesystem directory that may contain other entries.
        SYMLINK: Symbolic link whose target is retained as metadata.

    """

    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


class ConflictPolicy(StrEnum):
    """Identify supported destination-precondition conflict policies.

    Attributes:
        ABORT: Stop patch application when a conflict is detected.
        OVERWRITE: Replace conflicting destination entries.
        SKIP: Leave conflicting destination entries unchanged.
        BACKUP: Preserve conflicting entries before replacing them.

    """

    ABORT = "abort"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """Describe one normalized filesystem entry.

    Attributes:
        path: Normalized project-relative POSIX path.
        kind: Filesystem entry kind.
        mode: Permission mode captured from the source filesystem.
        digest: Content or symlink-target SHA-256 digest when applicable.
        link_target: Symlink target text for symbolic links.
        content: File bytes retained for archive construction.

    """

    path: PurePosixPath
    kind: EntryKind
    mode: int
    digest: str = ""
    link_target: str = ""
    content: bytes = b""

    @property
    def identity(self) -> tuple[EntryKind, int, str, str]:
        """Return metadata used to determine semantic entry equality.

        Returns:
            Tuple containing kind, mode, digest, and symlink target.

        """
        return self.kind, self.mode, self.digest, self.link_target


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """Represent a complete normalized virtual project tree.

    Attributes:
        entries: Deterministically ordered filesystem entries in the project.

    """

    entries: tuple[SnapshotEntry, ...]

    @property
    def by_path(self) -> dict[PurePosixPath, SnapshotEntry]:
        """Return snapshot entries indexed by project-relative path.

        Returns:
            Mapping from normalized project-relative paths to entries.

        """
        return {entry.path: entry for entry in self.entries}

    @property
    def fingerprint(self) -> str:
        """Return a deterministic metadata and content fingerprint.

        Returns:
            SHA-256 hexadecimal digest covering every normalized entry.

        """
        digest: HASH = sha256()
        for entry in self.entries:
            digest.update(
                (
                    f"{entry.path.as_posix()}\0{entry.kind}\0"
                    f"{entry.mode:o}\0{entry.digest}\0"
                    f"{entry.link_target}\n"
                ).encode(),
            )
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class DeltaOperation:
    """Represent one path transition between two project snapshots.

    Attributes:
        path: Destination path affected by the transition.
        before: Entry expected before application, or ``None`` for additions.
        after: Entry expected after application, or ``None`` for removals.
        move_from: Original source path when the transition is a move.

    """

    path: PurePosixPath
    before: SnapshotEntry | None
    after: SnapshotEntry | None
    move_from: PurePosixPath | None = None


@dataclass(frozen=True, slots=True)
class PatchResult:
    """Describe the observable outcome of applying a project patch.

    Attributes:
        added: Project-relative paths created by the patch.
        changed: Existing project-relative paths replaced by the patch.
        removed: Project-relative paths removed by the patch.
        moved: Human-readable source-to-destination move descriptions.
        skipped: Paths skipped because of the selected conflict policy.
        conflicts: Paths whose preconditions differed from the patch model.
        bytes_written: Number of payload bytes written during application.
        verified: Whether post-application verification completed successfully.
        rolled_back: Whether transactional rollback was required.

    """

    added: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    moved: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    bytes_written: int = 0
    verified: bool = False
    rolled_back: bool = False


@dataclass(frozen=True, slots=True)
class ProjectDelta:
    """Represent a deterministic transition between two project snapshots.

    Attributes:
        before_fingerprint: Fingerprint required before applying the delta.
        after_fingerprint: Fingerprint expected after applying the delta.
        operations: Ordered path-level transitions comprising the delta.

    """

    before_fingerprint: str
    after_fingerprint: str
    operations: tuple[DeltaOperation, ...]

    @classmethod
    def between(
        cls,
        *,
        before: ProjectSnapshot,
        after: ProjectSnapshot,
        detect_moves: bool = True,
    ) -> "ProjectDelta":
        """Calculate the minimal transition between two snapshots.

        Entries existing at the same path are emitted only when their
        identities differ. When move detection is enabled, identical removed
        and added entries are paired deterministically and emitted as moves.

        Args:
            before: Complete source snapshot representing state A.
            after: Complete target snapshot representing state B.
            detect_moves: Whether matching removals and additions become moves.

        Returns:
            Deterministically ordered delta transforming ``before`` to
            ``after``.

        """
        before_map: dict[PurePosixPath, SnapshotEntry] = before.by_path
        after_map: dict[PurePosixPath, SnapshotEntry] = after.by_path
        removed: dict[PurePosixPath, SnapshotEntry] = {
            path: entry
            for path, entry in before_map.items()
            if path not in after_map
        }
        added: dict[PurePosixPath, SnapshotEntry] = {
            path: entry
            for path, entry in after_map.items()
            if path not in before_map
        }
        moves: dict[PurePosixPath, PurePosixPath] = {}
        if detect_moves:
            candidates: dict[
                tuple[EntryKind, int, str, str],
                list[PurePosixPath],
            ] = {}
            for path, entry in removed.items():
                candidates.setdefault(entry.identity, []).append(path)
            for sources in candidates.values():
                sources.sort(key=str)
            for path, entry in tuple(added.items()):
                sources: list[PurePosixPath] | None = candidates.get(
                    entry.identity,
                )
                if sources:
                    source: PurePosixPath = sources.pop(0)
                    moves[path] = source
                    removed.pop(source)
                    added.pop(path)
        operations: list[DeltaOperation] = [
            DeltaOperation(
                path=path,
                before=before_map[path],
                after=after_map[path],
            )
            for path in sorted(
                set(before_map).intersection(after_map),
                key=str,
            )
            if before_map[path].identity != after_map[path].identity
        ]
        operations.extend(
            DeltaOperation(path=path, before=entry, after=None)
            for path, entry in sorted(
                removed.items(),
                key=lambda item: str(object=item[0]),
            )
        )
        operations.extend(
            DeltaOperation(path=path, before=None, after=entry)
            for path, entry in sorted(
                added.items(),
                key=lambda item: str(object=item[0]),
            )
        )
        operations.extend(
            DeltaOperation(
                path=path,
                before=before_map[source],
                after=after_map[path],
                move_from=source,
            )
            for path, source in sorted(
                moves.items(),
                key=lambda item: str(object=item[0]),
            )
        )
        return cls(
            before_fingerprint=before.fingerprint,
            after_fingerprint=after.fingerprint,
            operations=tuple(
                sorted(operations, key=lambda item: str(object=item.path)),
            ),
        )

    def inverse(self) -> "ProjectDelta":
        """Return the exact inverse transition.

        Returns:
            Delta that transforms the original target state back into the
            original source state.

        """
        return ProjectDelta(
            before_fingerprint=self.after_fingerprint,
            after_fingerprint=self.before_fingerprint,
            operations=tuple(
                DeltaOperation(
                    path=operation.move_from or operation.path,
                    before=operation.after,
                    after=operation.before,
                    move_from=(
                        operation.path
                        if operation.move_from is not None
                        else None
                    ),
                )
                for operation in self.operations
            ),
        )

    def compose(self, *, next_delta: "ProjectDelta") -> "ProjectDelta":
        """Compose this A-to-B delta with a compatible B-to-C delta.

        Args:
            next_delta: Delta whose source fingerprint must equal this
                delta's target fingerprint.

        Returns:
            Delta representing the direct A-to-C transition.

        Raises:
            ValueError: If the intermediate fingerprints do not match.

        """
        if self.after_fingerprint != next_delta.before_fingerprint:
            msg: str = (
                "Deltas are not composable: intermediate fingerprints differ."
            )
            raise ValueError(msg)
        states: dict[
            PurePosixPath,
            tuple[SnapshotEntry | None, SnapshotEntry | None],
        ] = {}
        for operation in self.operations:
            source: PurePosixPath = operation.move_from or operation.path
            states[source] = (
                operation.before,
                None if operation.move_from else operation.after,
            )
            if operation.move_from is not None:
                states[operation.path] = (None, operation.after)
        for operation in next_delta.operations:
            source = operation.move_from or operation.path
            initial: SnapshotEntry | None = states.get(
                source,
                (operation.before, None),
            )[0]
            states[source] = (
                initial,
                None if operation.move_from else operation.after,
            )
            if operation.move_from is not None:
                destination_initial: SnapshotEntry | None = states.get(
                    operation.path,
                    (None, None),
                )[0]
                states[operation.path] = (destination_initial, operation.after)
        operations: tuple[DeltaOperation, ...] = tuple(
            DeltaOperation(path=path, before=before, after=after)
            for path, (before, after) in sorted(
                states.items(),
                key=lambda item: str(object=item[0]),
            )
            if (before is None) != (after is None)
            or (
                before is not None
                and after is not None
                and before.identity != after.identity
            )
        )
        return ProjectDelta(
            before_fingerprint=self.before_fingerprint,
            after_fingerprint=next_delta.after_fingerprint,
            operations=operations,
        )


class ProjectSource:
    """Load snapshots from directories, ZIP archives, or patch PYZ files."""

    @classmethod
    def from_path(
        cls,
        *,
        path: Path | str,
        includes: Iterable[str] = (),
        excludes: Iterable[str] = (),
    ) -> ProjectSnapshot:
        """Load a normalized snapshot from a supported source path.

        Args:
            path: Directory, ZIP archive, or generated patch PYZ to inspect.
            includes: Optional project-relative glob patterns to include.
            excludes: Optional project-relative glob patterns to exclude.

        Returns:
            Normalized snapshot loaded from the selected source.

        Raises:
            ValueError: If the source is neither a directory nor a supported
                archive type.

        """
        source: Path = Path(path).expanduser().resolve(strict=True)
        include_patterns: tuple[str, ...] = tuple(includes)
        exclude_patterns: tuple[str, ...] = tuple(excludes)
        if source.is_dir():
            return cls._directory(
                root=source,
                includes=include_patterns,
                excludes=exclude_patterns,
            )
        if source.suffix.lower() in {".zip", ".pyz"}:
            return cls._archive(
                path=source,
                includes=include_patterns,
                excludes=exclude_patterns,
            )
        msg: str = f"Unsupported source: {source}"
        raise ValueError(msg)

    @classmethod
    def _directory(
        cls,
        *,
        root: Path,
        includes: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> ProjectSnapshot:
        """Load a normalized snapshot from a filesystem directory.

        Args:
            root: Existing directory used as the project snapshot root.
            includes: Inclusion glob patterns.
            excludes: Exclusion glob patterns.

        Returns:
            Snapshot containing selected directories, files, and symlinks.

        """
        entries: list[SnapshotEntry] = []
        for path in sorted(
            root.rglob(pattern="*"),
            key=lambda item: item.as_posix(),
        ):
            relative: PurePosixPath = PurePosixPath(
                path.relative_to(root).as_posix(),
            )
            if not cls._selected(
                path=relative,
                includes=includes,
                excludes=excludes,
            ):
                continue
            status: stat_result = path.lstat()
            mode: int = S_IMODE(status.st_mode)
            if S_ISLNK(status.st_mode):
                target: str = path.readlink().as_posix()
                entries.append(
                    SnapshotEntry(
                        path=relative,
                        kind=EntryKind.SYMLINK,
                        mode=mode,
                        digest=sha256(
                            data=target.encode(encoding="utf-8"),
                        ).hexdigest(),
                        link_target=target,
                    ),
                )
            elif path.is_dir():
                entries.append(
                    SnapshotEntry(
                        path=relative,
                        kind=EntryKind.DIRECTORY,
                        mode=mode,
                    ),
                )
            elif path.is_file():
                content: bytes = path.read_bytes()
                entries.append(
                    SnapshotEntry(
                        path=relative,
                        kind=EntryKind.FILE,
                        mode=mode,
                        digest=cls._digest_bytes(content=content),
                        content=content,
                    ),
                )
        return ProjectSnapshot(entries=tuple(entries))

    @classmethod
    def _archive(
        cls,
        *,
        path: Path,
        includes: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> ProjectSnapshot:
        """Load a normalized snapshot from a ZIP or generated patch PYZ.

        Args:
            path: Existing archive path to inspect.
            includes: Inclusion glob patterns.
            excludes: Exclusion glob patterns.

        Returns:
            Snapshot reconstructed from the archive or embedded target state.

        Raises:
            TypeError: If an embedded patch manifest has invalid JSON types.

        """
        with ZipFile(file=path, mode="r") as archive:
            names: set[str] = set(archive.namelist())
            manifest_name: str = "patch_data/manifest.json"
            if path.suffix.lower() == ".pyz" and manifest_name in names:
                manifest: JsonObject = _json_object(
                    content=archive.read(name=manifest_name),
                )
                format_value: JsonValue | None = manifest.get("format")
                snapshot_value: JsonValue | None = manifest.get(
                    "after_snapshot",
                )
                if format_value == "project-delta-pyz":
                    if (
                        not isinstance(snapshot_value, list)
                        or not snapshot_value
                    ):
                        msg: str = (
                            "Invalid embedded snapshot: 'after_snapshot' "
                            "must be a non-empty list."
                        )
                        raise TypeError(msg)
                    return cls._snapshot_from_manifest(
                        archive=archive,
                        manifest=manifest,
                        key="after_snapshot",
                        includes=includes,
                        excludes=excludes,
                    )
            entries: list[SnapshotEntry] = []
            for info in sorted(
                archive.infolist(),
                key=lambda item: item.filename,
            ):
                stripped: str = info.filename.rstrip("/")
                if not stripped:
                    continue
                pure: PurePosixPath = safe_relative(value=stripped)
                if not cls._selected(
                    path=pure,
                    includes=includes,
                    excludes=excludes,
                ):
                    continue
                mode: int = (
                    (info.external_attr >> 16) & Defaults.archive_mode_mask
                ) or (
                    Defaults.default_directory_mode
                    if info.is_dir()
                    else Defaults.default_file_mode
                )
                kind_bits: int = (
                    info.external_attr >> 16
                ) & Defaults.archive_kind_mask
                if kind_bits == Defaults.symlink_kind_bits:
                    target: str = archive.read(name=info).decode(
                        encoding="utf-8",
                    )
                    entries.append(
                        SnapshotEntry(
                            path=pure,
                            kind=EntryKind.SYMLINK,
                            mode=mode,
                            digest=sha256(
                                data=target.encode(encoding="utf-8"),
                            ).hexdigest(),
                            link_target=target,
                        ),
                    )
                elif info.is_dir():
                    entries.append(
                        SnapshotEntry(
                            path=pure,
                            kind=EntryKind.DIRECTORY,
                            mode=mode,
                        ),
                    )
                else:
                    content: bytes = archive.read(name=info)
                    entries.append(
                        SnapshotEntry(
                            path=pure,
                            kind=EntryKind.FILE,
                            mode=mode,
                            digest=cls._digest_bytes(content=content),
                            content=content,
                        ),
                    )
            return ProjectSnapshot(entries=tuple(entries))

    @classmethod
    def _snapshot_from_manifest(
        cls,
        *,
        archive: ZipFile,
        manifest: JsonObject,
        key: str,
        includes: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> ProjectSnapshot:
        """Reconstruct a snapshot from a generated patch manifest.

        Args:
            archive: Open patch archive containing manifest payload blobs.
            manifest: Recursively typed patch manifest JSON object.
            key: Snapshot member to reconstruct from the manifest.
            includes: Inclusion glob patterns.
            excludes: Exclusion glob patterns.

        Returns:
            Snapshot reconstructed from validated manifest entries.

        Raises:
            ValueError: If a referenced file payload fails digest validation.

        """
        raw_entries: list[JsonValue] = _json_list(mapping=manifest, key=key)
        entries: list[SnapshotEntry] = []
        for raw_value in raw_entries:
            raw: JsonObject = _json_mapping(
                value=raw_value,
                context="Invalid embedded snapshot entry",
            )
            relative: PurePosixPath = safe_relative(
                value=_json_string(mapping=raw, key="path"),
            )
            if not cls._selected(
                path=relative,
                includes=includes,
                excludes=excludes,
            ):
                continue
            kind: EntryKind = EntryKind(_json_string(mapping=raw, key="kind"))
            digest: str = _json_string(mapping=raw, key="sha256", default="")
            content: bytes = b""
            if kind is EntryKind.FILE:
                blob: str = _json_string(mapping=raw, key="blob")
                content = archive.read(name=f"patch_data/blobs/{blob}")
                if sha256(data=content).hexdigest() != digest:
                    msg: str = f"Corrupt embedded blob for {relative}."
                    raise ValueError(msg)
            entries.append(
                SnapshotEntry(
                    path=relative,
                    kind=kind,
                    mode=_json_int(mapping=raw, key="mode"),
                    digest=digest,
                    link_target=_json_string(
                        mapping=raw,
                        key="link_target",
                        default="",
                    ),
                    content=content,
                ),
            )
        return ProjectSnapshot(entries=tuple(entries))

    @staticmethod
    def _selected(
        *,
        path: PurePosixPath,
        includes: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> bool:
        """Determine whether a relative path passes source filters.

        Args:
            path: Normalized project-relative path to evaluate.
            includes: Inclusion glob patterns, where empty means include all.
            excludes: Exclusion glob patterns applied after inclusion.

        Returns:
            ``True`` when the path should be represented in the snapshot.

        """
        text: str = path.as_posix()
        return (
            not includes
            or any(fnmatch(name=text, pat=pattern) for pattern in includes)
        ) and not any(fnmatch(name=text, pat=pattern) for pattern in excludes)

    @staticmethod
    def _digest_bytes(*, content: bytes) -> str:
        """Calculate a SHA-256 hexadecimal digest for in-memory bytes.

        Args:
            content: Bytes whose digest should be calculated.

        Returns:
            SHA-256 hexadecimal digest of ``content``.

        """
        return sha256(data=content).hexdigest()


def safe_relative(*, value: str) -> PurePosixPath:
    """Validate and normalize a project-relative POSIX path.

    Args:
        value: Path text expected to identify an entry below a project root.

    Returns:
        Validated relative ``PurePosixPath`` representation.

    Raises:
        ValueError: If the path is empty, absolute, or contains traversal or
            explicit current-directory components.

    """
    pure: PurePosixPath = PurePosixPath(value)
    if (
        not pure.parts
        or pure.is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
    ):
        msg: str = f"Unsafe project-relative path: {value!r}"
        raise ValueError(msg)
    return pure


class PyzProjectPatch:
    """Build deterministic executable project-delta archives."""

    def __init__(
        self,
        *,
        project_root: Path | str,
        files: Iterable[Path | str] = (),
        remove: Iterable[Path | str] = (),
    ) -> None:
        """Create a direct patch from selected project paths and removals.

        Args:
            project_root: Existing project directory represented by the patch.
            files: Existing project paths whose current entries are selected.
            remove: Project-relative paths removed from the target snapshot.

        """
        root: Path = Path(project_root).expanduser().resolve(strict=True)
        before: ProjectSnapshot = ProjectSource.from_path(path=root)
        after_map: dict[PurePosixPath, SnapshotEntry] = before.by_path
        for raw in remove:
            relative: PurePosixPath = self.relative(root=root, path=raw)
            after_map = {
                path: entry
                for path, entry in after_map.items()
                if path != relative and relative not in path.parents
            }
        selected: set[PurePosixPath] = set()
        for raw in files:
            source: Path = Path(raw)
            source = source if source.is_absolute() else root / source
            source = source.resolve(strict=True)
            paths: tuple[Path, ...] = (
                tuple(
                    sorted(
                        source.rglob(pattern="*"),
                        key=lambda item: item.as_posix(),
                    ),
                )
                if source.is_dir()
                else (source,)
            )
            selected.update(
                PurePosixPath(path.relative_to(root).as_posix())
                for path in paths
            )
        current: ProjectSnapshot = ProjectSource.from_path(path=root)
        for relative in selected:
            entry: SnapshotEntry | None = current.by_path.get(relative)
            if entry is not None:
                after_map[relative] = entry
        after: ProjectSnapshot = ProjectSnapshot(
            entries=tuple(
                entry
                for _, entry in sorted(
                    after_map.items(),
                    key=lambda item: str(object=item[0]),
                )
            ),
        )
        self.project_root: Path = root
        self.before_snapshot: ProjectSnapshot = before
        self.after_snapshot: ProjectSnapshot = after
        self.delta_model: ProjectDelta = ProjectDelta.between(
            before=before,
            after=after,
        )

    @classmethod
    def delta(
        cls,
        *,
        a: Path | str,
        b: Path | str,
        project_root: Path | str,
        **options: Unpack[DeltaOptions],
    ) -> "PyzProjectPatch":
        """Create a delta from independently supported A and B sources.

        Both sources may independently be directories, ZIP archives, or
        generated project-delta PYZ archives. Optional include and exclude
        patterns are applied identically to both snapshots.

        Args:
            a: Source representing project state A.
            b: Source representing project state B.
            project_root: Default destination root embedded in the patch.
            **options: Optional ``includes``, ``excludes``, and
                ``detect_moves`` controls for snapshot and delta generation.

        Returns:
            Patch builder representing the A-to-B transition.

        """
        includes: Iterable[str] = options.get("includes", ())
        excludes: Iterable[str] = options.get("excludes", ())
        detect_moves: bool = options.get("detect_moves", True)
        instance: PyzProjectPatch = cls.__new__(cls)
        instance.project_root = (
            Path(project_root).expanduser().resolve(strict=False)
        )
        instance.before_snapshot = ProjectSource.from_path(
            path=a,
            includes=includes,
            excludes=excludes,
        )
        instance.after_snapshot = ProjectSource.from_path(
            path=b,
            includes=includes,
            excludes=excludes,
        )
        instance.delta_model = ProjectDelta.between(
            before=instance.before_snapshot,
            after=instance.after_snapshot,
            detect_moves=detect_moves,
        )
        return instance

    @classmethod
    def from_delta(
        cls,
        *,
        delta: ProjectDelta,
        project_root: Path | str,
        before_snapshot: ProjectSnapshot,
        after_snapshot: ProjectSnapshot,
    ) -> "PyzProjectPatch":
        """Create a patch builder around an existing delta model.

        Args:
            delta: Existing transition model to package.
            project_root: Default destination root embedded in the patch.
            before_snapshot: Complete source snapshot associated with delta.
            after_snapshot: Complete target snapshot associated with delta.

        Returns:
            Patch builder wrapping the supplied transition and snapshots.

        """
        instance: PyzProjectPatch = cls.__new__(cls)
        instance.project_root = (
            Path(project_root).expanduser().resolve(strict=False)
        )
        instance.before_snapshot = before_snapshot
        instance.after_snapshot = after_snapshot
        instance.delta_model = delta
        return instance

    @staticmethod
    def relative(*, root: Path, path: Path | str) -> PurePosixPath:
        """Resolve a path and return its normalized project-relative form.

        Args:
            root: Absolute project root constraining the selected path.
            path: Absolute or project-root-relative path to normalize.

        Returns:
            POSIX path relative to ``root``.

        Raises:
            ValueError: If the resolved path is outside ``root``.

        """
        candidate: Path = Path(path)
        candidate = candidate if candidate.is_absolute() else root / candidate
        try:
            return PurePosixPath(
                candidate.resolve(strict=False).relative_to(root).as_posix(),
            )
        except ValueError as error:
            msg: str = f"Path is outside project root: {candidate}"
            raise ValueError(msg) from error

    def build(
        self,
        *,
        output: Path | str,
        reversible: bool = True,
        compression_threshold: int = 64,
    ) -> Path:
        """Write a deterministic executable PYZ containing this delta.

        File payloads are content-addressed by SHA-256 and deduplicated across
        the snapshots required by the selected reversibility mode. Archive
        timestamps and member metadata are normalized for reproducible output.

        Args:
            output: Destination path for the generated executable PYZ.
            reversible: Whether source-state payloads needed by an inverse
                operation should also be embedded.
            compression_threshold: Payload size below which ZIP storage is
                preferred over deflate compression.

        Returns:
            Absolute path of the generated executable patch archive.

        """
        destination: Path = Path(output).expanduser().resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        blobs: dict[str, bytes] = {}
        snapshots: tuple[ProjectSnapshot, ...] = (
            (self.before_snapshot, self.after_snapshot)
            if reversible
            else (self.after_snapshot,)
        )
        for snapshot in snapshots:
            for entry in snapshot.entries:
                if entry.kind is EntryKind.FILE:
                    blobs.setdefault(entry.digest, entry.content)
        operations: list[ManifestOperation] = [
            self._operation_dict(operation=operation, reversible=reversible)
            for operation in self.delta_model.operations
        ]
        manifest: JsonObject = {
            "format": "project-delta-pyz",
            "format_version": Defaults.format_version,
            "project_root": str(object=self.project_root),
            "reversible": reversible,
            "before_fingerprint": self.delta_model.before_fingerprint,
            "after_fingerprint": self.delta_model.after_fingerprint,
            "operations": cast(typ="list[JsonValue]", val=operations),
            "before_snapshot": cast(
                typ="list[JsonValue]",
                val=self._snapshot_dicts(snapshot=self.before_snapshot)
                if reversible
                else [],
            ),
            "after_snapshot": cast(
                typ="list[JsonValue]",
                val=self._snapshot_dicts(snapshot=self.after_snapshot),
            ),
        }
        canonical: bytes = dumps(
            obj=manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode(encoding="utf-8")
        manifest["patch_id"] = sha256(data=canonical).hexdigest()
        manifest_bytes: bytes = dumps(
            obj=manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode(encoding="utf-8")
        main_bytes: bytes = (
            files("exactus.packages.patcher")
            .joinpath("runtime.py")
            .read_bytes()
        )
        with ZipFile(
            file=destination,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            main_info: ZipInfo = self._zip_info(
                name="__main__.py",
                mode=Defaults.executable_archive_mode,
            )
            archive.writestr(zinfo_or_arcname=main_info, data=main_bytes)
            init_info: ZipInfo = self._zip_info(name="patch_data/__init__.py")
            archive.writestr(zinfo_or_arcname=init_info, data=b"")
            manifest_info: ZipInfo = self._zip_info(
                name="patch_data/manifest.json",
            )
            archive.writestr(
                zinfo_or_arcname=manifest_info,
                data=manifest_bytes,
            )
            for digest, content in sorted(blobs.items()):
                info: ZipInfo = self._zip_info(
                    name=f"patch_data/blobs/{digest}",
                )
                if len(content) < compression_threshold:
                    info.compress_type = ZIP_STORED
                archive.writestr(zinfo_or_arcname=info, data=content)
        destination.chmod(mode=Defaults.executable_output_mode)
        return destination

    def inverse(self) -> "PyzProjectPatch":
        """Return a builder representing the exact reverse patch.

        Returns:
            Patch builder that transforms the original target snapshot back
            into the original source snapshot.

        """
        return self.from_delta(
            delta=self.delta_model.inverse(),
            project_root=self.project_root,
            before_snapshot=self.after_snapshot,
            after_snapshot=self.before_snapshot,
        )

    def compose(self, *, next_patch: "PyzProjectPatch") -> "PyzProjectPatch":
        """Compose this patch with a compatible subsequent patch.

        Args:
            next_patch: Patch whose source state must match this patch's
                target state.

        Returns:
            Patch builder representing the combined direct transition.

        """
        return self.from_delta(
            delta=self.delta_model.compose(next_delta=next_patch.delta_model),
            project_root=self.project_root,
            before_snapshot=self.before_snapshot,
            after_snapshot=next_patch.after_snapshot,
        )

    @staticmethod
    def _zip_info(
        *,
        name: str,
        mode: int = Defaults.default_file_mode,
    ) -> ZipInfo:
        """Create deterministic ZIP metadata for one archive member.

        Args:
            name: POSIX archive member name.
            mode: Unix permission mode encoded into external attributes.

        Returns:
            Configured deterministic ``ZipInfo`` instance.

        """
        info: ZipInfo = ZipInfo(
            filename=name,
            date_time=Defaults.zip_timestamp,
        )
        info.compress_type = ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = (mode & 0xFFFF) << 16
        return info

    @staticmethod
    def _entry_dict(*, entry: SnapshotEntry, blob: str = "") -> ManifestEntry:
        """Serialize a snapshot entry into deterministic manifest data.

        Args:
            entry: Snapshot entry to serialize.
            blob: Optional content-addressed payload identifier.

        Returns:
            Manifest-compatible entry mapping.

        """
        result: ManifestEntry = {
            "path": entry.path.as_posix(),
            "kind": entry.kind.value,
            "mode": entry.mode,
        }
        if entry.digest:
            result["sha256"] = entry.digest
        if entry.link_target:
            result["link_target"] = entry.link_target
        if blob:
            result["blob"] = blob
        return result

    def _snapshot_dicts(
        self,
        *,
        snapshot: ProjectSnapshot,
    ) -> list[ManifestEntry]:
        """Serialize every entry in a snapshot for the patch manifest.

        Args:
            snapshot: Snapshot whose entries should be serialized.

        Returns:
            Ordered manifest entry mappings for the complete snapshot.

        """
        return [
            self._entry_dict(
                entry=entry,
                blob=(entry.digest if entry.kind is EntryKind.FILE else ""),
            )
            for entry in snapshot.entries
        ]

    def _operation_dict(
        self,
        *,
        operation: DeltaOperation,
        reversible: bool,
    ) -> ManifestOperation:
        """Serialize one delta operation for the embedded manifest.

        Args:
            operation: Delta operation to serialize.
            reversible: Whether source-state file blobs are embedded.

        Returns:
            Manifest mapping describing the path transition.

        """
        before: ManifestEntry | None = (
            self._entry_dict(
                entry=operation.before,
                blob=(
                    operation.before.digest
                    if reversible and operation.before.kind is EntryKind.FILE
                    else ""
                ),
            )
            if operation.before is not None
            else None
        )
        after: ManifestEntry | None = (
            self._entry_dict(
                entry=operation.after,
                blob=(
                    operation.after.digest
                    if operation.after.kind is EntryKind.FILE
                    else ""
                ),
            )
            if operation.after is not None
            else None
        )
        return {
            "path": operation.path.as_posix(),
            "move_from": (
                operation.move_from.as_posix()
                if operation.move_from is not None
                else None
            ),
            "before": before,
            "after": after,
        }
