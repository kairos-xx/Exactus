# Copyright (c) 2026
"""Own content-identified source and AST reuse within one lint run."""

from __future__ import annotations

from ast import Module, parse
from contextvars import ContextVar, Token
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from typing import TYPE_CHECKING, Final, Self, final

if TYPE_CHECKING:
    from os import stat_result
    from pathlib import Path
    from types import TracebackType


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """Bind source bytes and a read-only AST to a content identity.

    Attributes:
        digest: SHA-256 of the actual source bytes.
        source: Decoded source text.
        tree: Parsed AST, never handed to a mutating consumer directly.

    """

    digest: str
    source: str
    tree: Module


class SourceCache:
    """Own a bounded source snapshot for one explicitly scoped run."""

    def __init__(self, *, max_entries: int = 1024) -> None:
        """Create a bounded cache without reading the filesystem.

        Args:
            max_entries: Maximum retained parsed files for this run.

        """
        self._max_entries: int = max(1, max_entries)
        self._records: dict[Path, SourceRecord] = {}
        self._texts: dict[
            Path,
            tuple[tuple[int, int, int, int], str, str],
        ] = {}
        self._lock: RLock = RLock()
        self._token: Token[SourceCache | None] | None = None

    def read(self, *, path: Path, mutable: bool = False) -> SourceRecord:
        """Read actual bytes and reuse parsing only for identical content.

        Args:
            path: Source file to inspect.
            mutable: Copy the AST before a transformation may modify it.

        Returns:
            A content-identified source record.

        """
        identity: Path = path.resolve()
        with self._lock:
            digest, source = self._text(path=identity)
            record: SourceRecord | None = self._records.get(identity)
            if record is None or record.digest != digest:
                record = SourceRecord(
                    digest=digest,
                    source=source,
                    tree=parse(source=source, filename=str(object=path)),
                )
                if len(self._records) >= self._max_entries:
                    self._records.pop(next(iter(self._records)))
                self._records[identity] = record
            return SourceRecord(
                digest=record.digest,
                source=record.source,
                tree=(
                    parse(source=record.source, filename=str(object=path))
                    if mutable
                    else record.tree
                ),
            )

    def text(self, *, path: Path) -> str:
        """Read text without parsing non-Python sources.

        Args:
            path: Source candidate.

        Returns:
            Current decoded source.

        """
        with self._lock:
            return self._text(path=path.resolve())[1]

    def invalidate(self, *, path: Path) -> None:
        """Release a record after a source-producing operation.

        Args:
            path: Written or removed source.

        """
        with self._lock:
            self._records.pop(path.resolve(), None)
            self._texts.pop(path.resolve(), None)

    def __enter__(self) -> Self:
        """Install this run's cache in its execution context.

        Returns:
            The owned cache.

        """
        self._token = SourceCacheTables.current.set(self)
        return self

    def __exit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Restore the enclosing context and release all retained source.

        Args:
            _kind: Exception type, if the run failed.
            _error: Primary exception, if any.
            _traceback: Primary exception traceback.

        """
        if self._token is not None:
            SourceCacheTables.current.reset(self._token)
            self._token = None
        self._records.clear()
        self._texts.clear()

    def _text(self, *, path: Path) -> tuple[str, str]:
        """Refresh a text snapshot when filesystem identity changes.

        Args:
            path: Absolute source path.

        Returns:
            Content digest and decoded source.

        Raises:
            OSError: When repeated concurrent edits prevent a stable read.

        """
        for _attempt in range(2):
            before: stat_result = path.stat()
            signature: tuple[int, int, int, int] = (
                before.st_mtime_ns,
                before.st_ctime_ns,
                before.st_size,
                before.st_ino,
            )
            previous: tuple[tuple[int, int, int, int], str, str] | None = (
                self._texts.get(path)
            )
            if previous is not None and previous[0] == signature:
                return previous[1], previous[2]
            data: bytes = path.read_bytes()
            after: stat_result = path.stat()
            if signature == (
                after.st_mtime_ns,
                after.st_ctime_ns,
                after.st_size,
                after.st_ino,
            ):
                digest: str = sha256(data=data).hexdigest()
                source: str = data.decode(encoding="utf-8-sig")
                if len(self._texts) >= self._max_entries:
                    self._texts.pop(next(iter(self._texts)))
                self._texts[path] = (signature, digest, source)
                return digest, source
        msg: str = f"Source changed repeatedly while reading {path}"
        raise OSError(msg)


@final
class SourceCacheTables:
    """Own the context-local active cache dependency.

    Attributes:
        current: Optional cache installed by an owning run.

    """

    current: Final[ContextVar[SourceCache | None]] = ContextVar(
        "exactus_source_cache",
        default=None,
    )


def source_record(*, path: Path, mutable: bool = False) -> SourceRecord:
    """Read source through the active run cache or an unretained reader.

    Args:
        path: Source candidate.
        mutable: Whether the returned AST may be modified.

    Returns:
        Source text and its matching AST.

    """
    cache: SourceCache | None = SourceCacheTables.current.get()
    return (cache or SourceCache()).read(path=path, mutable=mutable)


def source_text(*, path: Path) -> str:
    """Read source text through the owned per-run cache when present.

    Args:
        path: Source candidate.

    Returns:
        Current source text.

    """
    cache: SourceCache | None = SourceCacheTables.current.get()
    return (cache or SourceCache()).text(path=path)
