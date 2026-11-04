# Copyright (c) 2026
"""Isolate lint mutations and turn validated results into source proposals."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from os import utime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING, Final, Self, final

from exactus.tools.common.path_filters import default_excluded_dirs, glob_match
from exactus.tools.common.source_transaction import (
    FileEdit,
    FileImage,
    SourceConflictError,
    StageContext,
    StageObserver,
    read_image,
    same_image,
)

if TYPE_CHECKING:
    from _hashlib import HASH
    from collections.abc import Generator, Sequence
    from contextvars import Token
    from types import TracebackType


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionLimits:
    """Bound a source workspace and complete pipeline convergence.

    Attributes:
        max_files: Maximum copied source/configuration files.
        max_bytes: Maximum copied source bytes.
        max_passes: Complete mutating pipeline pass budget.
        timeout_seconds: Total mutation and verification budget.

    """

    max_files: int = 20000
    max_bytes: int = 268435456
    max_passes: int = 4
    timeout_seconds: float = 1800.0

    def __post_init__(self) -> None:
        """Reject invalid transaction budgets before creating scratch."""
        if (
            min(
                self.max_files,
                self.max_bytes,
                self.max_passes,
                self.timeout_seconds,
            )
            <= 0
        ):
            msg: str = "Source transaction budgets must be positive."
            raise ValueError(msg)


@final
class WorkspaceTables:
    """Own input classification and the active stage observer.

    Attributes:
        suffixes: Source/configuration formats eligible for owned changes.
        configs: Native carriers whose project-root paths need relocation.

    """

    suffixes: Final[frozenset[str]] = frozenset(
        {
            ".py",
            ".pyi",
            ".js",
            ".mjs",
            ".cjs",
            ".jsx",
            ".ts",
            ".tsx",
            ".css",
            ".scss",
            ".html",
            ".htm",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".md",
            ".txt",
            ".svg",
            ".xml",
        },
    )
    configs: Final[frozenset[str]] = frozenset(
        {
            "pyproject.toml",
            "ruff.toml",
            ".ruff.toml",
            "pyrefly.toml",
            "pyrightconfig.json",
            "basedpyrightconfig.json",
            "jsconfig.json",
            "tsconfig.json",
            "eslint.config.mjs",
            "eslint.config.js",
            "eslint.config.cjs",
            "stylelint.config.mjs",
            "stylelint.config.js",
        },
    )


class SourceWorkspace:
    """Own prospective source while preserving originals until commit."""

    def __init__(
        self,
        *,
        root: Path,
        ignores: Sequence[str],
        limits: TransactionLimits,
        output: Path | None = None,
    ) -> None:
        """Bind ownership and budgets before the first mutation.

        Args:
            root: Original project boundary.
            ignores: Existing run-global excluded paths.
            limits: Resource and convergence bounds.
            output: Report path excluded from the prospective source tree.

        """
        self.root: Path = root.resolve()
        self.limits: TransactionLimits = limits
        self._ignores: tuple[str, ...] = tuple(ignores)
        self._output: Path | None = output
        self._temporary: TemporaryDirectory[str] | None = None
        self.path: Path = self.root
        self.originals: dict[Path, FileImage] = {}
        self.stages: list[tuple[str, tuple[str, ...]]] = []
        self._token: Token[StageObserver | None] | None = None
        self._deadline: float = monotonic() + limits.timeout_seconds
        self._verified: dict[Path, FileImage] | None = None

    def check_budget(self) -> None:
        """Enforce the total run deadline at stage boundaries.

        Raises:
            TimeoutError: The transaction exceeded its configured budget.

        """
        if monotonic() > self._deadline:
            msg: str = "Lint source transaction exceeded its time budget."
            raise TimeoutError(msg)

    def remaining_seconds(self) -> float:
        """Return the positive remaining transaction execution budget.

        Returns:
            Seconds left before the transaction deadline, floored at a
            small positive value for subprocess timeouts.

        """
        self.check_budget()
        return max(0.001, self._deadline - monotonic())

    @contextmanager
    def stage(self, *, name: str) -> Generator[None]:
        """Record every stage's prospective changed paths.

        Args:
            name: Existing stage identity.

        Yields:
            Control to the existing stage implementation.

        Raises:
            SourceConflictError: A stage changed verified source.

        """
        self.check_budget()
        before: dict[Path, FileImage] = self.snapshot()
        try:
            yield
        finally:
            after: dict[Path, FileImage] = self.snapshot()
            changed: tuple[str, ...] = tuple(
                path.as_posix()
                for path in sorted(before.keys() | after.keys())
                if not same_image(left=before.get(path), right=after.get(path))
            )
            self.stages.append((name, changed))
        self.check_budget()
        if self._verified is not None and changed:
            msg: str = f"Source changed after final verification: {name}"
            raise SourceConflictError(msg)

    def snapshot(self) -> dict[Path, FileImage]:
        """Read bounded prospective source without following dependency links.

        Returns:
            Exact images indexed by original project-relative paths.

        """
        result: dict[Path, FileImage] = {}
        total: int = 0
        for directory, dirs, files in self.path.walk():
            dirs[:] = [
                name
                for name in dirs
                if not (directory / name).is_symlink()
                and not name.startswith(".")
            ]
            for name in files:
                path: Path = directory / name
                if (
                    path.is_symlink()
                    or path.suffix not in WorkspaceTables.suffixes
                ):
                    continue
                image: FileImage | None = read_image(path=path)
                if image is not None:
                    relative: Path = path.relative_to(self.path)
                    data: bytes = (
                        self._relocate(data=image.data, reverse=True)
                        if name in WorkspaceTables.configs
                        else image.data
                    )
                    result[relative] = FileImage(
                        data=data,
                        mode=image.mode,
                        atime_ns=image.atime_ns,
                        mtime_ns=image.mtime_ns,
                    )
                    total += len(data)
                    self._bound(files=len(result), size=total)
        return result

    def fingerprint(self) -> str:
        """Hash complete prospective content and permission state.

        Returns:
            Deterministic complete-pass state identity.

        """
        digest: HASH = sha256()
        for path, image in sorted(self.snapshot().items()):
            digest.update(path.as_posix().encode())
            digest.update(image.data)
            digest.update(str(object=image.mode).encode())
        return digest.hexdigest()

    def verify_originals(self) -> None:
        """Reject external changes before publishing any proposal.

        Raises:
            SourceConflictError: An original changed during analysis.

        """
        for relative, expected in self.originals.items():
            if not same_image(
                left=expected,
                right=read_image(path=self.root / relative),
            ):
                msg: str = f"External source edit preserved: {relative}"
                raise SourceConflictError(msg)

    def freeze(self) -> None:
        """Freeze validated prospective bytes and recheck originals."""
        self.check_budget()
        self.verify_originals()
        self._verified = self.snapshot()

    def proposals(self) -> tuple[FileEdit, ...]:
        """Return unique whole-file edits only for the frozen source state.

        Returns:
            Validated, non-overlapping commit proposals.

        Raises:
            SourceConflictError: The workspace is unverified or changed.

        """
        current: dict[Path, FileImage] = self.snapshot()
        if self._verified is None or any(
            not same_image(
                left=current.get(path),
                right=self._verified.get(path),
            )
            for path in current.keys() | self._verified.keys()
        ):
            msg: str = "Cannot commit an unverified or changed lint workspace."
            raise SourceConflictError(msg)
        self.verify_originals()
        return tuple(
            FileEdit(
                relative=path,
                before=self.originals.get(path),
                after=current.get(path),
                stages=tuple(
                    name
                    for name, paths in self.stages
                    if path.as_posix() in paths
                ),
            )
            for path in sorted(self.originals.keys() | current.keys())
            if not same_image(
                left=self.originals.get(path),
                right=current.get(path),
            )
        )

    def translate(self, *, value: str, reverse: bool = False) -> str:
        """Relocate owned absolute arguments or report paths.

        Args:
            value: Argument/report string.
            reverse: Translate the prospective path back to its public root.

        Returns:
            String with owned project prefixes relocated.

        """
        return self._relocate(data=value.encode(), reverse=reverse).decode()

    def __enter__(self) -> Self:
        """Create a private tree using the platform temporary directory.

        Returns:
            The explicitly owned workspace.

        """
        self._temporary = TemporaryDirectory(prefix="exactus-lints-")
        self.path = (Path(self._temporary.name) / self.root.name).resolve()
        self.path.mkdir(mode=0o700)
        try:
            self._mirror()
            self._token = StageContext.current.set(self)
        except BaseException:
            self._temporary.cleanup()
            raise
        return self

    def __exit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Release stage context and all private prospective files.

        Args:
            _kind: Propagating exception type.
            _error: Propagating exception instance.
            _traceback: Propagating traceback.

        """
        if self._token is not None:
            StageContext.current.reset(self._token)
        if self._temporary is not None:
            self._temporary.cleanup()

    def _relocate(self, *, data: bytes, reverse: bool = False) -> bytes:
        """Relocate native config path representations without altering source.

        Args:
            data: Configuration or report bytes.
            reverse: Restore the public project prefix.

        Returns:
            Relocated bytes, including JSON-escaped Windows paths.

        """
        before: Path = self.path if reverse else self.root
        after: Path = self.root if reverse else self.path
        result: bytes = data
        for old, new in (
            (str(object=before), str(object=after)),
            (before.as_posix(), after.as_posix()),
        ):
            result = result.replace(
                old.replace("\\", "\\\\").encode(),
                new.replace("\\", "\\\\").encode(),
            )
            result = result.replace(old.encode(), new.encode())
        return result

    def _excluded(self, *, relative: Path) -> bool:
        """Recognize existing excluded directory boundaries.

        Args:
            relative: Directory relative to the original project.

        Returns:
            Whether this directory is a read-only dependency boundary.

        """
        if any(
            part.startswith(".") for part in relative.parts
        ) or relative.name in default_excluded_dirs(root=self.root):
            return True
        if self._output is not None and (self.root / relative).is_relative_to(
            self._output.parent,
        ):
            return True
        return any(
            glob_match(relative=relative.as_posix(), pattern=pattern)
            or glob_match(
                relative=f"{relative.as_posix()}/__source__",
                pattern=pattern,
            )
            for pattern in self._ignores
        )

    def _mirror(self) -> None:
        """Copy owned text and preserve dependency resolution through links.

        Raises:
            SourceConflictError: A directory symlink requires an explicit
                exclusion before the workspace can mirror it safely.

        """
        total: int = 0
        for directory, dirs, files in self.root.walk():
            self.check_budget()
            relative: Path = directory.relative_to(self.root)
            destination: Path = self.path / relative
            destination.mkdir(parents=True, exist_ok=True)
            for name in tuple(dirs):
                source: Path = directory / name
                target: Path = destination / name
                if source.is_symlink() and not self._excluded(
                    relative=relative / name,
                ):
                    msg: str = (
                        "Source directory symlink requires an "
                        f"explicit exclusion: {source}"
                    )
                    raise SourceConflictError(msg)
                if self._excluded(
                    relative=relative / name,
                ):
                    dirs.remove(name)
                    target.symlink_to(target=source, target_is_directory=True)
            for name in files:
                source = directory / name
                target = destination / name
                if (
                    source.is_symlink()
                    and source.suffix in WorkspaceTables.suffixes
                ):
                    msg = (
                        "Source symlink cannot be rewritten "
                        f"transactionally: {source}"
                    )
                    raise SourceConflictError(msg)
                if (
                    source.is_symlink()
                    or source.suffix not in WorkspaceTables.suffixes
                ):
                    target.symlink_to(target=source)
                    continue
                image: FileImage | None = read_image(path=source)
                if image is None:
                    continue
                self.originals[relative / name] = image
                total += len(image.data)
                self._bound(files=len(self.originals), size=total)
                _ = target.write_bytes(
                    data=self._relocate(data=image.data)
                    if name in WorkspaceTables.configs
                    else image.data,
                )
                target.chmod(mode=image.mode)
                utime(path=target, ns=(image.atime_ns, image.mtime_ns))

    def _bound(self, *, files: int, size: int) -> None:
        """Reject oversized input before it exceeds the configured budget.

        Args:
            files: Number of owned source files.
            size: Total owned source bytes.

        Raises:
            SourceConflictError: Source storage exceeds the configured bounds.

        """
        if files > self.limits.max_files or size > self.limits.max_bytes:
            msg: str = "Lint transaction source exceeds its file/byte budget."
            raise SourceConflictError(msg)
