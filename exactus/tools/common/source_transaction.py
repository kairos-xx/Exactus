# Copyright (c) 2026
"""Commit validated source proposals with durable, conflict-safe recovery."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from os import fsync, link, stat_result, utime
from pathlib import Path
from shutil import rmtree
from sqlite3 import Connection, OperationalError, connect
from stat import S_IMODE
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, ClassVar, Protocol, cast, final
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence
    from contextlib import AbstractContextManager

    from exactus.tools.common.json_types import JsonValue


class StageObserver(Protocol):
    """Observe source mutations without depending on a particular tool."""

    def stage(self, *, name: str) -> AbstractContextManager[None]:
        """Observe the named source stage.

        Args:
            name: Existing stage identity.

        Returns:
            Context manager spanning the stage's mutation window.

        """
        ...

    def remaining_seconds(self) -> float:
        """Return the remaining execution budget.

        Returns:
            Seconds left before the transaction deadline.

        """
        ...


class StageContext:
    """Own the context-local source observer.

    Attributes:
        current: Context-local transaction observer, when a guarded
            mutating workflow is active.

    """

    current: ClassVar[ContextVar[StageObserver | None]] = ContextVar(
        "exactus_source_observer",
        default=None,
    )


@contextmanager
def observe_source_stage(*, name: str) -> Generator[None]:
    """Record a source stage when a transaction observer is active.

    Args:
        name: Existing stage identity.

    Yields:
        Control to the stage implementation, inside the observer's
        stage context when one is registered.

    """
    observer: StageObserver | None = StageContext.current.get()
    if observer is None:
        yield
    else:
        with observer.stage(name=name):
            yield


class SourceConflictError(RuntimeError):
    """Refuse to replace source whose expected ownership changed."""


@final
@dataclass(frozen=True, slots=True)
class FileImage:
    """Capture exact bytes and restorable source metadata.

    Attributes:
        data: Original file bytes, including encoding markers/newlines.
        mode: Permission bits.
        atime_ns: Access timestamp before reading.
        mtime_ns: Modification timestamp before reading.

    """

    data: bytes
    mode: int
    atime_ns: int
    mtime_ns: int

    @property
    def digest(self) -> str:
        """Return the content identity.

        Returns:
            SHA-256 of the captured bytes.

        """
        return sha256(data=self.data).hexdigest()


@final
@dataclass(frozen=True, slots=True)
class FileEdit:
    """Describe one whole-file proposal against an exact prior state.

    Attributes:
        relative: Root-relative owned file.
        before: Expected original image, or absent file.
        after: Validated replacement image, or requested deletion.
        stages: Mutating stages responsible for this proposal.

    """

    relative: Path
    before: FileImage | None
    after: FileImage | None
    stages: tuple[str, ...] = ()


def read_image(*, path: Path) -> FileImage | None:
    """Read a stable regular file without following a source symlink.

    Args:
        path: File to inspect.

    Returns:
        Exact image, or ``None`` when absent.

    Raises:
        SourceConflictError: The file is unstable or is not an owned file.

    """
    if path.is_symlink():
        msg: str = f"Source symlink is not an owned replacement: {path}"
        raise SourceConflictError(msg)
    try:
        before: stat_result = path.stat()
    except FileNotFoundError:
        return None
    if not path.is_file():
        msg = f"Source path is not a regular file: {path}"
        raise SourceConflictError(msg)
    data: bytes = path.read_bytes()
    after: stat_result = path.stat()
    if (
        before.st_ino,
        before.st_dev,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_ino,
        after.st_dev,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        msg = f"Source changed while being read: {path}"
        raise SourceConflictError(msg)
    return FileImage(
        data=data,
        mode=S_IMODE(before.st_mode),
        atime_ns=before.st_atime_ns,
        mtime_ns=before.st_mtime_ns,
    )


def same_image(*, left: FileImage | None, right: FileImage | None) -> bool:
    """Compare source identity while ignoring read-induced access times.

    Args:
        left: Expected image.
        right: Observed image.

    Returns:
        Whether bytes, permissions and modification time match.

    """
    if left is None or right is None:
        return left is right
    return (
        left.data == right.data
        and left.mode == right.mode
        and left.mtime_ns == right.mtime_ns
    )


def _durable_file(*, path: Path, data: bytes, mode: int = 0o600) -> None:
    """Publish durable private journal data through adjacent staging.

    Args:
        path: Owned journal destination.
        data: Serialized bytes.
        mode: Requested permissions.

    """
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            _ = stream.write(data)
            stream.flush()
            fsync(fd=stream.fileno())
        temporary.chmod(mode=mode)
        _ = temporary.replace(target=path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SourceJournal:
    """Own one serialized source commit and its recoverable originals."""

    def __init__(self, *, root: Path, directory: Path) -> None:
        """Bind a private journal directory without changing source.

        Args:
            root: Owned project boundary.
            directory: Durable journal storage outside source discovery.

        """
        self.root: Path = root.resolve()
        self.directory: Path = directory
        self._connection: Connection | None = None
        self._run: Path | None = None
        self._manifest: dict[str, JsonValue] = {}
        self._edits: tuple[FileEdit, ...] = ()

    def acquire(self) -> None:
        """Acquire a crash-released cross-process writer lock and recover.

        Raises:
            SourceConflictError: Another source commit owns this journal.

        """
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(mode=0o700)
        connection: Connection = connect(
            database=str(object=self.directory / "lock.sqlite3"),
            timeout=0,
        )
        try:
            _ = connection.execute("BEGIN EXCLUSIVE")
        except OperationalError as error:
            connection.close()
            msg: str = "Another lint transaction owns this project's journal."
            raise SourceConflictError(msg) from error
        self._connection = connection
        try:
            self.recover()
        except BaseException:
            self.release()
            raise

    def release(self) -> None:
        """Release the process-owned lock after all cleanup."""
        if self._connection is not None:
            self._connection.rollback()
            self._connection.close()
            self._connection = None

    def commit(
        self,
        *,
        edits: Sequence[FileEdit],
        publish: Callable[[], None] | None = None,
    ) -> None:
        """Commit unique validated proposals, rolling back any failure.

        Args:
            edits: Non-overlapping whole-file proposals.
            publish: Final report publisher included in the transaction.

        Raises:
            SourceConflictError: A proposal has invalid ownership.

        """
        ordered: tuple[FileEdit, ...] = tuple(
            sorted(edits, key=lambda edit: edit.relative.as_posix()),
        )
        if len({edit.relative for edit in ordered}) != len(ordered):
            msg: str = "Overlapping whole-file source proposals."
            raise SourceConflictError(msg)
        for edit in ordered:
            path: Path = self._path(relative=edit.relative)
            if not same_image(left=edit.before, right=read_image(path=path)):
                msg = f"Stale source proposal: {edit.relative}"
                raise SourceConflictError(msg)
            if edit.after is not None and path.suffix == ".py":
                _ = compile(
                    source=edit.after.data,
                    filename=str(object=path),
                    mode="exec",
                    dont_inherit=True,
                )
        self._prepare(edits=ordered)
        try:
            for index, edit in enumerate(iterable=ordered):
                self._apply(index=index, edit=edit)
            if publish is not None:
                publish()
            self._manifest["state"] = "committed"
            self._save()
        except BaseException as error:
            failure: BaseException = error
            try:
                self._restore(run=self._run)
            except (OSError, RuntimeError, ValueError) as recovery_error:
                failure.add_note(
                    f"Source rollback requires recovery: {recovery_error}",
                )
            raise
        else:
            self._discard()

    def recover(self) -> None:
        """Recover interrupted commits without replacing external edits.

        Raises:
            SourceConflictError: External edits prevent automatic recovery.

        """
        for run in sorted(self.directory.glob(pattern="run-*")):
            self._restore(run=run)

    @staticmethod
    def _image_metadata(*, image: FileImage | None) -> JsonValue:
        """Serialize identity and metadata without source text.

        Args:
            image: Present or absent source image.

        Returns:
            JSON metadata, or null for absence.

        """
        return (
            None
            if image is None
            else {
                "digest": image.digest,
                "mode": image.mode,
                "atime_ns": image.atime_ns,
                "mtime_ns": image.mtime_ns,
            }
        )

    @staticmethod
    def _publish_new(*, path: Path, image: FileImage) -> None:
        """Publish a complete candidate with exclusive pathname creation.

        Args:
            path: Absent destination after its original was claimed.
            image: Validated replacement bytes and metadata.

        """
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                _ = stream.write(image.data)
                stream.flush()
                fsync(fd=stream.fileno())
            temporary.chmod(mode=image.mode)
            utime(path=temporary, ns=(image.atime_ns, image.mtime_ns))
            link(src=temporary, dst=path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _matches(*, image: FileImage | None, metadata: JsonValue) -> bool:
        """Check recoverable ownership against recorded content and mode.

        Args:
            image: Current file state.
            metadata: Recorded expected state.

        Returns:
            Whether this path is still transaction-owned.

        """
        if image is None or metadata is None:
            return image is metadata
        return (
            isinstance(metadata, dict)
            and image.digest == metadata.get("digest")
            and image.mode == metadata.get("mode")
        )

    def _path(self, *, relative: Path) -> Path:
        """Resolve one non-symlink owned path.

        Args:
            relative: Project-relative proposal path.

        Returns:
            Validated absolute destination.

        Raises:
            SourceConflictError: The path escapes ownership.

        """
        path: Path = self.root / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or path.is_symlink()
            or any(
                parent.is_symlink()
                for parent in path.parents
                if parent != self.root and parent.is_relative_to(self.root)
            )
            or not path.resolve().is_relative_to(self.root)
        ):
            msg: str = f"Invalid transaction destination: {relative}"
            raise SourceConflictError(msg)
        return path

    def _prepare(self, *, edits: tuple[FileEdit, ...]) -> None:
        """Durably record originals and intents before the first edit.

        Args:
            edits: Validated ordered proposals.

        """
        self._edits = edits
        self._run = self.directory / f"run-{uuid4().hex}"
        self._run.mkdir(mode=0o700)
        self._manifest = {
            "version": 1,
            "root": str(object=self.root),
            "state": "preparing",
            "entries": [],
        }
        self._save()
        entries: list[JsonValue] = []
        for index, edit in enumerate(iterable=edits):
            if edit.before is not None:
                _durable_file(
                    path=self._run / f"{index}.original",
                    data=edit.before.data,
                )
            entries.append(
                {
                    "path": edit.relative.as_posix(),
                    "before": self._image_metadata(image=edit.before),
                    "after": self._image_metadata(image=edit.after),
                    "claim": f".{edit.relative.name}."
                    f"exactus-{self._run.name}-{index}",
                    "started": False,
                },
            )
        self._manifest = {
            "version": 1,
            "root": str(object=self.root),
            "state": "prepared",
            "entries": entries,
        }
        self._save()

    def _save(self) -> None:
        """Flush the complete current intent before advancing."""
        if self._run is not None:
            _durable_file(
                path=self._run / "manifest.json",
                data=dumps(obj=self._manifest, sort_keys=True).encode(),
            )

    def _apply(self, *, index: int, edit: FileEdit) -> None:
        """Claim the observed original and publish without overwriting a rival.

        Args:
            index: Journal entry index.
            edit: Validated proposal.

        Raises:
            SourceConflictError: Source changed before or during publication.

        """
        entries: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=self._manifest["entries"],
        )
        entry: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=entries[index],
        )
        path: Path = self._path(relative=edit.relative)
        claim: Path = path.with_name(name=str(object=entry["claim"]))
        entry["started"] = True
        self._save()
        if edit.before is not None:
            _ = path.rename(target=claim)
            if not same_image(left=edit.before, right=read_image(path=claim)):
                msg: str = f"External edit intercepted during commit: {path}"
                raise SourceConflictError(msg)
        if edit.after is not None:
            self._publish_new(path=path, image=edit.after)
        elif path.exists() or path.is_symlink():
            msg = f"External file appeared during deletion: {path}"
            raise SourceConflictError(msg)

    def _restore(self, *, run: Path | None) -> None:
        """Restore interrupted entries, preserving mismatched external source.

        Args:
            run: Owned journal run directory.

        Raises:
            SourceConflictError: Invalid journal or externally changed source.

        """
        if run is None:
            return
        manifest: Path = run / "manifest.json"
        raw: JsonValue = loads(s=manifest.read_text(encoding="utf-8"))
        if (
            not isinstance(raw, dict)
            or raw.get("version") != 1
            or raw.get("root") != str(object=self.root)
        ):
            msg: str = f"Unsupported source journal: {run}"
            raise SourceConflictError(msg)
        entries: JsonValue = raw.get("entries")
        if not isinstance(entries, list):
            msg = f"Invalid source journal entries: {run}"
            raise SourceConflictError(msg)
        conflicts: list[str] = []
        for index in reversed(range(len(entries))):
            entry: dict[str, JsonValue] = cast(
                typ="dict[str, JsonValue]",
                val=entries[index],
            )
            path: Path = self._path(relative=Path(str(object=entry["path"])))
            claim: Path = path.with_name(name=str(object=entry["claim"]))
            expected_claim: str = f".{path.name}.exactus-{run.name}-{index}"
            if claim.name != expected_claim:
                msg = f"Invalid source recovery claim: {run}"
                raise SourceConflictError(msg)
            if raw.get("state") == "committed":
                claim.unlink(missing_ok=True)
                continue
            if not entry.get("started"):
                continue
            if not self._restore_entry(path=path, claim=claim, entry=entry):
                conflicts.append(str(object=path))
        if conflicts:
            msg = (
                f"External edits preserved; journal retained at {run}: "
                f"{", ".join(conflicts)}"
            )
            raise SourceConflictError(msg)
        rmtree(path=run)

    def _restore_entry(
        self,
        *,
        path: Path,
        claim: Path,
        entry: dict[str, JsonValue],
    ) -> bool:
        """Restore one claimed original without discarding external bytes.

        Args:
            path: Source file the entry restores.
            claim: Journaled original preserved beside the source file.
            entry: Recorded before/after image metadata for the file.

        Returns:
            Whether the entry restored cleanly.

        """
        current: FileImage | None = read_image(path=path)
        before: JsonValue = entry["before"]
        after: JsonValue = entry["after"]
        removed: Path = claim.with_name(name=f"{claim.name}.rollback")
        if self._matches(image=current, metadata=before):
            if claim.exists() and not self._matches(
                image=read_image(path=claim),
                metadata=before,
            ):
                return False
            claim.unlink(missing_ok=True)
            removed.unlink(missing_ok=True)
            return True
        if before is not None and not claim.exists():
            return self._matches(image=current, metadata=before)
        if current is not None and not self._withdraw(
            path=path,
            removed=removed,
            current=current,
            after=after,
        ):
            return False
        if claim.exists():
            try:
                link(src=claim, dst=path)
            except FileExistsError:
                return False
            claim.unlink()
        removed.unlink(missing_ok=True)
        return True

    def _withdraw(
        self,
        *,
        path: Path,
        removed: Path,
        current: FileImage,
        after: JsonValue,
    ) -> bool:
        """Claim rollback candidates before inspecting their ownership.

        Args:
            path: Source file withdrawn for inspection.
            removed: Private staging path receiving the withdrawal.
            current: Observed file state that must still match ``after``.
            after: Recorded post-edit image metadata.

        Returns:
            Whether the withdrawal matched and stayed owned.

        """
        if (
            not self._matches(image=current, metadata=after)
            or removed.exists()
        ):
            return False
        _ = path.rename(target=removed)
        if self._matches(image=read_image(path=removed), metadata=after):
            return True
        link(src=removed, dst=path)
        removed.unlink()
        return False

    def _discard(self) -> None:
        """Discard committed originals only after durable completion."""
        self._restore(run=self._run)
        self._run = None
