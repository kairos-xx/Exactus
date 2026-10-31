#!/usr/bin/env python3
"""Watch a directory tree, copy changes, and record destination activity."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from hashlib import sha256
from json import dumps
from os import DirEntry, cpu_count, getpid, scandir, stat_result
from pathlib import Path
from plistlib import dump as dump_plist
from shutil import copy2, rmtree
from stat import S_ISREG
from subprocess import CompletedProcess, run
from sys import executable, platform, stderr, stdout
from textwrap import dedent
from threading import Lock
from time import monotonic, sleep
from tomllib import TOMLDecodeError
from tomllib import load as load_toml
from typing import TYPE_CHECKING, Final, Literal, cast, final

from exactus.packages.argument_parser import ExactusArgumentParser

if TYPE_CHECKING:
    from collections.abc import Callable
__version__: str = "3.1.0"


@final
class Constants:
    """Group module-level constants.

    Attributes:
        activity_name: Grouped module constant.
        autostart_label: Grouped module constant.
        pyproject_name: Grouped module constant.
        config_table: Grouped module constant.
        autostart_plist_name: Grouped module constant.
        metrics_ttl: Grouped module constant.
        parallel_threshold: Grouped module constant.
        prune_interval: Grouped module constant.

    """

    activity_name: Final[str] = "@activity.json"
    autostart_label: Final[str] = "com.folder-watch-copy"
    pyproject_name: Final[str] = "pyproject.toml"
    config_table: Final[tuple[str, str]] = ("tool", "watch")
    autostart_plist_name: Final[str] = f"{autostart_label}.plist"
    metrics_ttl: Final[float] = 1.0
    parallel_threshold: Final[int] = 8
    prune_interval: Final[float] = 5.0


type ActivityValue = bool | float | int | str | dict[str, int]
type PruneVerdict = Literal["keep", "stale", "descend"]
type TomlValue = (
    str | int | float | bool | list[TomlValue] | dict[str, TomlValue]
)


@dataclass(frozen=True, slots=True)
class EntryState:
    """Represent the observable state of one source filesystem entry.

    Attributes:
        is_directory: Whether the entry is a directory.
        is_symlink: Whether the entry is a symbolic link.
        size: Entry size in bytes.
        modified_ns: Modification timestamp in nanoseconds.
        link_target: Symbolic link target, or None for other entries.

    """

    is_directory: bool
    is_symlink: bool
    size: int
    modified_ns: int
    link_target: str | None


@dataclass(frozen=True, slots=True)
class TreeMetrics:
    """Describe an inventory of a filesystem snapshot.

    Attributes:
        files: Count of regular files.
        directories: Count of directories.
        symlinks: Count of symbolic links.
        total_entries: Total number of filesystem entries.
        total_size_bytes: Combined size of all files in bytes.

    """

    files: int
    directories: int
    symlinks: int
    total_entries: int
    total_size_bytes: int


@dataclass(frozen=True, slots=True)
class ActivityDelta:
    """Describe one successfully applied destination operation.

    Attributes:
        operation: Applied operation such as ``copy``, ``mkdir``,
            ``symlink``, or ``delete``.
        relative_path: Destination-relative path of the changed entry.
        entry_type: Filesystem entry kind such as ``file``, ``directory``,
            ``symlink``, or the generic ``entry``.
        size_delta_bytes: Destination size change in bytes, negative when
            the operation removed content.
        transferred_bytes: Bytes copied into the destination.

    """

    operation: str
    relative_path: str
    entry_type: str
    size_delta_bytes: int
    transferred_bytes: int


class ActivityRecorder:
    """Maintain an atomic machine-readable activity record in a destination."""

    def __init__(self, *, source: Path, destination: Path) -> None:
        """Initialize an activity recorder.

        Args:
            source: Watched source directory.
            destination: Mirrored destination directory.

        """
        self._source: Path = source
        self._destination: Path = destination
        self._path: Path = destination / Constants.activity_name
        self._started_at: datetime = datetime.now().astimezone()
        self._updates: int = 0
        self._copied_files: int = 0
        self._created_directories: int = 0
        self._copied_symlinks: int = 0
        self._deleted_entries: int = 0
        self._transferred_bytes: int = 0
        self._net_size_delta_bytes: int = 0
        self._lock: Lock = Lock()

    def record(
        self,
        *,
        delta: ActivityDelta,
        source_metrics: TreeMetrics,
        destination_metrics: TreeMetrics,
        autostart_installed: bool,
    ) -> None:
        """Record one successful filesystem operation.

        Args:
            delta: Metadata for the operation just applied.
            source_metrics: Current source-tree inventory.
            destination_metrics: Current destination-tree inventory.
            autostart_installed: Whether the macOS LaunchAgent is installed.

        """
        with self._lock:
            self._updates += 1
            self._transferred_bytes += delta.transferred_bytes
            self._net_size_delta_bytes += delta.size_delta_bytes
            if delta.operation == "copy":
                self._copied_files += 1
            elif delta.operation == "mkdir":
                self._created_directories += 1
            elif delta.operation == "symlink":
                self._copied_symlinks += 1
            elif delta.operation == "delete":
                self._deleted_entries += 1
            now: datetime = datetime.now().astimezone()
            payload: dict[str, ActivityValue] = {
                "schema_version": 1,
                "watcher_version": __version__,
                "watcher_pid": getpid(),
                "origin": str(object=self._source),
                "destination": str(object=self._destination),
                "started_at": self._started_at.isoformat(
                    timespec="milliseconds",
                ),
                "last_update": now.isoformat(timespec="milliseconds"),
                "last_update_date": now.date().isoformat(),
                "last_update_time": now.timetz().isoformat(
                    timespec="milliseconds",
                ),
                "last_operation": delta.operation,
                "last_relative_path": delta.relative_path,
                "last_entry_type": delta.entry_type,
                "last_delta_size_bytes": delta.size_delta_bytes,
                "last_transferred_bytes": delta.transferred_bytes,
                "updates_this_run": self._updates,
                "copied_files_this_run": self._copied_files,
                "created_directories_this_run": self._created_directories,
                "copied_symlinks_this_run": self._copied_symlinks,
                "deleted_entries_this_run": self._deleted_entries,
                "transferred_bytes_this_run": self._transferred_bytes,
                "net_size_delta_bytes_this_run": (self._net_size_delta_bytes),
                "source": asdict(obj=source_metrics),
                "target": asdict(obj=destination_metrics),
                "autostart_installed": autostart_installed,
            }
            self._write(payload=payload)

    def write_started(
        self,
        *,
        source_metrics: TreeMetrics,
        destination_metrics: TreeMetrics,
        autostart_installed: bool,
    ) -> None:
        """Create the activity file when a watcher starts.

        Args:
            source_metrics: Current source-tree inventory.
            destination_metrics: Current destination-tree inventory.
            autostart_installed: Whether the macOS LaunchAgent is installed.

        """
        now: datetime = datetime.now().astimezone()
        payload: dict[str, ActivityValue] = {
            "schema_version": 1,
            "watcher_version": __version__,
            "watcher_pid": getpid(),
            "origin": str(object=self._source),
            "destination": str(object=self._destination),
            "started_at": self._started_at.isoformat(timespec="milliseconds"),
            "last_update": now.isoformat(timespec="milliseconds"),
            "last_update_date": now.date().isoformat(),
            "last_update_time": now.timetz().isoformat(
                timespec="milliseconds",
            ),
            "last_operation": "watch_started",
            "last_relative_path": "",
            "last_entry_type": "watcher",
            "last_delta_size_bytes": 0,
            "last_transferred_bytes": 0,
            "updates_this_run": 0,
            "copied_files_this_run": 0,
            "created_directories_this_run": 0,
            "copied_symlinks_this_run": 0,
            "deleted_entries_this_run": 0,
            "transferred_bytes_this_run": 0,
            "net_size_delta_bytes_this_run": 0,
            "source": asdict(obj=source_metrics),
            "target": asdict(obj=destination_metrics),
            "autostart_installed": autostart_installed,
        }
        self._write(payload=payload)

    def _write(self, *, payload: dict[str, ActivityValue]) -> None:
        """Atomically replace the JSON activity document.

        Args:
            payload: Complete activity document.

        """
        self._destination.mkdir(parents=True, exist_ok=True)
        temporary: Path = self._path.with_name(
            name=f".{Constants.activity_name}.tmp",
        )
        temporary.write_text(
            data=f"{dumps(obj=payload, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
        temporary.replace(target=self._path)


class MacAutostart:
    """Install and manage the folder watcher as a macOS LaunchAgent."""

    @classmethod
    def installed(cls) -> bool:
        """Return whether the LaunchAgent property list exists.

        Returns:
            True when autostart is installed.

        """
        return cls.plist_path().is_file()

    @classmethod
    def install(cls, *, script: Path, arguments: CliArguments) -> None:
        """Install and immediately bootstrap the per-user LaunchAgent.

        Args:
            script: Absolute path to this watcher script.
            arguments: Watcher configuration to persist.

        Raises:
            RuntimeError: If launchctl cannot bootstrap the agent.
            ValueError: If source or destination are missing.

        """
        cls.require_macos()
        source: Path | None = arguments.source
        destination: Path | None = arguments.destination
        if source is None or destination is None:
            msg: str = "Source and destination are required for autostart."
            raise ValueError(msg)
        plist_path: Path = cls.plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        program_arguments: list[str] = [
            executable,
            str(object=script),
            str(object=source.expanduser().resolve()),
            str(object=destination.expanduser().resolve()),
            "--interval",
            str(object=arguments.interval),
            "--settle-time",
            str(object=arguments.settle_time),
        ]
        if arguments.workers is not None:
            program_arguments.extend(
                ["--workers", str(object=arguments.workers)],
            )
        pattern: str
        for pattern in arguments.exclude or ():
            program_arguments.extend(["--exclude", pattern])
        for pattern in arguments.include or ():
            program_arguments.extend(["--include", pattern])
        if arguments.initial_sync:
            program_arguments.append("--initial-sync")
        if arguments.mirror_deletes:
            program_arguments.append("--mirror-deletes")
        if arguments.quiet:
            program_arguments.append("--quiet")
        logs: Path = Path.home() / "Library" / "Logs"
        logs.mkdir(parents=True, exist_ok=True)
        payload: dict[str, bool | str | list[str]] = {
            "Label": Constants.autostart_label,
            "ProgramArguments": program_arguments,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Background",
            "StandardOutPath": str(object=logs / "folder-watch-copy.log"),
            "StandardErrorPath": str(
                object=logs / "folder-watch-copy.error.log",
            ),
        }
        temporary: Path = plist_path.with_suffix(suffix=".plist.tmp")
        with temporary.open(mode="wb") as stream:
            dump_plist(value=payload, fp=stream, sort_keys=True)
        temporary.replace(target=plist_path)
        cls._bootout(ignore_failure=True)
        result: CompletedProcess[str] = cls._launchctl(
            arguments=[
                "bootstrap",
                f"gui/{cls._uid()}",
                str(object=plist_path),
            ],
        )
        if result.returncode != 0:
            msg = result.stderr.strip() or "launchctl bootstrap failed."
            raise RuntimeError(msg)

    @classmethod
    def install_package(cls, *, settings: WatchSettings) -> None:
        """Install this package configuration as a per-user LaunchAgent.

        Args:
            settings: Fully resolved watcher configuration.

        Raises:
            RuntimeError: If launchctl cannot bootstrap the agent.

        """
        cls.require_macos()
        plist_path: Path = cls.plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        program_arguments: list[str] = [
            executable,
            str(object=Path(__file__).resolve().parent / "__main__.py"),
        ]
        if settings.pyproject is not None:
            program_arguments.extend(
                ["--pyproject", str(object=settings.pyproject)],
            )
        else:
            program_arguments.extend(
                [
                    str(object=settings.source),
                    str(object=settings.destination),
                ],
            )
            program_arguments.extend(
                ["--interval", str(object=settings.interval)],
            )
            program_arguments.extend(
                ["--settle-time", str(object=settings.settle_time)],
            )
            program_arguments.extend(
                ["--workers", str(object=settings.workers)],
            )
            pattern: str
            for pattern in settings.exclude:
                program_arguments.extend(["--exclude", pattern])
            for pattern in settings.include:
                program_arguments.extend(["--include", pattern])
            if settings.initial_sync:
                program_arguments.append("--initial-sync")
            if settings.mirror_deletes:
                program_arguments.append("--mirror-deletes")
            if settings.quiet:
                program_arguments.append("--quiet")
        logs: Path = Path.home() / "Library" / "Logs"
        logs.mkdir(parents=True, exist_ok=True)
        payload: dict[str, bool | str | list[str]] = {
            "Label": Constants.autostart_label,
            "ProgramArguments": program_arguments,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Background",
            "StandardOutPath": str(object=logs / "folder-watch-copy.log"),
            "StandardErrorPath": str(
                object=logs / "folder-watch-copy.error.log",
            ),
        }
        if settings.project_root is not None:
            payload["WorkingDirectory"] = str(object=settings.project_root)
        temporary: Path = plist_path.with_suffix(suffix=".plist.tmp")
        with temporary.open(mode="wb") as stream:
            dump_plist(value=payload, fp=stream, sort_keys=True)
        temporary.replace(target=plist_path)
        cls._bootout(ignore_failure=True)
        result: CompletedProcess[str] = cls._launchctl(
            arguments=[
                "bootstrap",
                f"gui/{cls._uid()}",
                str(object=plist_path),
            ],
        )
        if result.returncode != 0:
            msg: str = result.stderr.strip() or "launchctl bootstrap failed."
            raise RuntimeError(msg)

    @classmethod
    def uninstall(cls) -> bool:
        """Unload and remove the installed LaunchAgent.

        Returns:
            True when an installed property list was removed.

        """
        cls.require_macos()
        plist_path: Path = cls.plist_path()
        existed: bool = plist_path.exists()
        cls._bootout(ignore_failure=True)
        plist_path.unlink(missing_ok=True)
        return existed

    @classmethod
    def status(cls) -> dict[str, bool | int | str | list[str]]:
        """Return installed and launchctl state plus persisted arguments.

        Returns:
            Autostart status information.

        """
        cls.require_macos()
        plist_path: Path = cls.plist_path()
        result: CompletedProcess[str] = cls._launchctl(
            arguments=[
                "print",
                f"gui/{cls._uid()}/{Constants.autostart_label}",
            ],
        )
        return {
            "installed": plist_path.is_file(),
            "loaded": result.returncode == 0,
            "label": Constants.autostart_label,
            "plist": str(object=plist_path),
            "launchctl_exit_code": result.returncode,
        }

    @staticmethod
    def plist_path() -> Path:
        """Return the per-user LaunchAgent property-list path.

        Returns:
            LaunchAgent property-list path.

        """
        return (
            Path.home()
            / "Library"
            / "LaunchAgents"
            / Constants.autostart_plist_name
        )

    @staticmethod
    def require_macos() -> None:
        """Reject LaunchAgent operations outside macOS.

        Raises:
            RuntimeError: If the current operating system is not macOS.

        """
        if platform != "darwin":
            msg: str = "Autostart management is supported only on macOS."
            raise RuntimeError(msg)

    @classmethod
    def _bootout(cls, *, ignore_failure: bool) -> None:
        """Unload the current agent when loaded.

        Args:
            ignore_failure: Whether a launchctl failure may be ignored.

        Raises:
            RuntimeError: If unloading fails and failure is not ignored.

        """
        result: CompletedProcess[str] = cls._launchctl(
            arguments=[
                "bootout",
                f"gui/{cls._uid()}/{Constants.autostart_label}",
            ],
        )
        if result.returncode != 0 and (not ignore_failure):
            msg: str = result.stderr.strip() or "launchctl bootout failed."
            raise RuntimeError(msg)

    @staticmethod
    def _uid() -> int:
        """Return the current numeric user identifier.

        Returns:
            Current user identifier.

        Raises:
            RuntimeError: If the ``id`` command fails.

        """
        result: CompletedProcess[str] = run(
            args=["id", "-u"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            msg: str = result.stderr.strip() or "Unable to determine user id."
            raise RuntimeError(msg)
        return int(result.stdout.strip())

    @staticmethod
    def _launchctl(*, arguments: list[str]) -> CompletedProcess[str]:
        """Execute launchctl without invoking a shell.

        Args:
            arguments: Arguments following the launchctl executable.

        Returns:
            Completed launchctl process.

        """
        return run(
            args=["launchctl", *arguments],
            check=False,
            capture_output=True,
            text=True,
        )


@dataclass(slots=True)
class FolderWatchCopy:
    """Poll one directory tree and copy changes into another tree.

    Attributes:
        source: Directory tree to observe.
        destination: Directory tree receiving changed entries.
        interval: Seconds between filesystem scans.
        settle_time: Minimum stable time before a changed file is copied.
        exclusions: Glob patterns matched against relative POSIX paths.
        inclusions: Glob patterns that override exclusions for matching
            relative POSIX paths.
        mirror_deletes: Whether source deletions remove destination
            entries and destination entries absent from the source are
            removed.
        verbose: Whether successful operations are written to stdout.
        workers: Parallel worker count for bulk operations, or 0 to
            auto-select from the CPU count.

    Raises:
        ValueError: If configuration is invalid.

    """

    source: Path
    destination: Path
    interval: float
    settle_time: float
    exclusions: tuple[str, ...]
    inclusions: tuple[str, ...]
    mirror_deletes: bool
    verbose: bool
    workers: int = 0
    _activity: ActivityRecorder = field(init=False)
    _metrics_lock: Lock = field(init=False)
    _source_metrics_cache: (
        tuple[dict[Path, EntryState], TreeMetrics] | None
    ) = field(init=False, default=None)
    _destination_metrics_cache: tuple[float, TreeMetrics] | None = field(
        init=False,
        default=None,
    )
    _last_prune: float = field(init=False, default=0.0)

    def run(
        self,
        *,
        initial_sync: bool,
        should_stop: Callable[[], bool] | None = None,
    ) -> bool:
        """Watch until interrupted or the supervisor requests a restart.

        Args:
            initial_sync: Whether to copy the complete source tree before
                watching for subsequent changes.
            should_stop: Optional callback checked before each filesystem
                scan. Returning true stops this watcher so its supervisor
                can apply a changed configuration.

        Returns:
            True when a configuration change requested the stop. False
            when the user interrupted the watcher.

        """
        previous: dict[Path, EntryState] = self._snapshot()
        pending: dict[Path, tuple[EntryState, float]] = {}
        self.destination.mkdir(parents=True, exist_ok=True)
        self._activity.write_started(
            source_metrics=self._metrics_cached(snapshot=previous),
            destination_metrics=self._destination_metrics_cached(refresh=True),
            autostart_installed=MacAutostart.installed(),
        )
        if initial_sync:
            self._sync_snapshot(snapshot=previous)
            self._record(
                delta=ActivityDelta(
                    operation="sync",
                    relative_path="",
                    entry_type="watcher",
                    size_delta_bytes=0,
                    transferred_bytes=0,
                ),
                source_snapshot=previous,
                refresh_metrics=True,
            )
        self._write(
            message=f"Watching {self.source}\n"
            f"Copying changes to {self.destination}\n"
            f"Activity: {self.destination / Constants.activity_name}\n"
            "Press Ctrl+C to stop.\n",
        )
        try:
            while True:
                sleep(self.interval)
                if should_stop is not None and should_stop():
                    return True
                current: dict[Path, EntryState] = self._snapshot()
                now: float = monotonic()
                self._process_changes(
                    previous=previous,
                    current=current,
                    pending=pending,
                    now=now,
                )
                if (
                    self.mirror_deletes
                    and now - self._last_prune >= Constants.prune_interval
                ):
                    self._prune_destination(source_snapshot=current)
                    self._last_prune = now
                previous = current
        except KeyboardInterrupt:
            self._write(message="Stopped.\n")
            return False

    def __post_init__(self) -> None:
        """Resolve paths, build the recorder and validate the setup."""
        self.source = self.source.expanduser().resolve()
        self.destination = self.destination.expanduser().resolve()
        self._activity = ActivityRecorder(
            source=self.source,
            destination=self.destination,
        )
        self._metrics_lock = Lock()
        if self.workers == 0:
            self.workers = min(8, cpu_count() or 4)
        self._validate_configuration()

    @staticmethod
    def _state(*, path: Path) -> EntryState:
        """Read the state used for change detection.

        Args:
            path: Filesystem entry to inspect.

        Returns:
            Immutable state for the entry.

        """
        path_stat: stat_result = path.lstat()
        is_symlink: bool = path.is_symlink()
        return EntryState(
            is_directory=path.is_dir() and (not is_symlink),
            is_symlink=is_symlink,
            size=path_stat.st_size,
            modified_ns=path_stat.st_mtime_ns,
            link_target=str(object=path.readlink()) if is_symlink else None,
        )

    @staticmethod
    def _sort_key(relative: Path) -> tuple[int, str]:
        """Return a deterministic parent-before-child path sort key.

        Args:
            relative: Relative filesystem path.

        Returns:
            Path depth followed by lexical POSIX path.

        """
        return (len(relative.parts), relative.as_posix())

    @staticmethod
    def _unchanged(*, destination: Path, state: EntryState) -> bool:
        """Return whether a destination file already matches the source.

        ``copy2`` preserves the source modification time, so equal size
        and nanosecond timestamps mean the bytes already match.

        Args:
            destination: Destination path to inspect.
            state: Observed source state.

        Returns:
            True when the destination regular file is identical.

        """
        try:
            existing: stat_result = destination.lstat()
        except OSError:
            return False
        return (
            S_ISREG(existing.st_mode)
            and existing.st_size == state.size
            and existing.st_mtime_ns == state.modified_ns
        )

    @staticmethod
    def _replace_with_symlink(
        *,
        destination: Path,
        target: str | None,
    ) -> None:
        """Replace a destination entry with a symbolic link.

        Args:
            destination: Destination path to replace.
            target: Symbolic-link target.

        Raises:
            ValueError: If the observed symlink has no target.

        """
        if target is None:
            msg: str = f"Missing symbolic-link target for {destination}"
            raise ValueError(msg)
        if destination.is_symlink() or destination.is_file():
            destination.unlink(missing_ok=True)
        elif destination.is_dir():
            rmtree(path=destination)
        destination.symlink_to(target=target)

    @staticmethod
    def _metrics(*, snapshot: dict[Path, EntryState]) -> TreeMetrics:
        """Calculate inventory metrics for a source snapshot.

        Args:
            snapshot: Filesystem snapshot.

        Returns:
            Aggregate tree metrics.

        """
        files: int = sum(
            1
            for state in snapshot.values()
            if not state.is_directory and (not state.is_symlink)
        )
        directories: int = sum(
            1 for state in snapshot.values() if state.is_directory
        )
        symlinks: int = sum(
            1 for state in snapshot.values() if state.is_symlink
        )
        total_size: int = sum(
            state.size
            for state in snapshot.values()
            if not state.is_directory and (not state.is_symlink)
        )
        return TreeMetrics(
            files=files,
            directories=directories,
            symlinks=symlinks,
            total_entries=len(snapshot),
            total_size_bytes=total_size,
        )

    @staticmethod
    def _entry_size(*, path: Path) -> int:
        """Return the byte size of an existing non-directory entry.

        Args:
            path: Destination path to inspect.

        Returns:
            Entry size, or zero for absent entries and directories.

        """
        try:
            if path.is_symlink():
                return path.lstat().st_size
            if path.is_file():
                return path.stat().st_size
        except (FileNotFoundError, PermissionError, OSError):
            return 0
        return 0

    @staticmethod
    def _write_error(*, relative: Path, error: OSError) -> None:
        """Write a non-fatal filesystem error.

        Args:
            relative: Relative path whose operation failed.
            error: Filesystem exception raised by the operation.

        """
        stderr.write(f"ERROR {relative}: {error}\n")
        stderr.flush()

    def _validate_configuration(self) -> None:
        """Validate paths and timing configuration.

        Raises:
            ValueError: If configuration is invalid.

        """
        if not self.source.is_dir():
            msg: str = f"Source is not a directory: {self.source}"
            raise ValueError(msg)
        if self.interval <= 0.0:
            msg = "Interval must be greater than zero."
            raise ValueError(msg)
        if self.settle_time < 0.0:
            msg = "Settle time cannot be negative."
            raise ValueError(msg)
        if self.workers < 1:
            msg = "Worker count must be at least one."
            raise ValueError(msg)
        if self.source == self.destination:
            msg = "Source and destination must be different directories."
            raise ValueError(msg)
        if self.source in self.destination.parents:
            msg = "Destination cannot be inside the watched source tree."
            raise ValueError(msg)
        if self.destination in self.source.parents:
            msg = "Source cannot be inside the destination tree."
            raise ValueError(msg)

    def _snapshot(self) -> dict[Path, EntryState]:
        """Build a relative-path snapshot of the source tree.

        Returns:
            Current observable filesystem state keyed by relative path.

        """
        snapshot: dict[Path, EntryState] = {}
        paths: list[Path] = [self.source]
        while paths:
            current: Path = paths.pop()
            try:
                children: tuple[Path, ...] = tuple(current.iterdir())
            except OSError:
                continue
            child: Path
            for child in children:
                relative: Path = child.relative_to(self.source)
                if self._excluded(relative=relative):
                    continue
                try:
                    state: EntryState = self._state(path=child)
                except (FileNotFoundError, PermissionError, OSError):
                    continue
                snapshot[relative] = state
                if state.is_directory and (not state.is_symlink):
                    paths.append(child)
        return snapshot

    def _excluded(self, *, relative: Path) -> bool:
        """Return whether a relative source path is excluded.

        Args:
            relative: Path relative to the watched source.

        Returns:
            True when any configured exclusion matches the path or a
            path segment and no inclusion claims it.

        """
        posix: str = relative.as_posix()
        pattern: str
        part: str
        for pattern in self.inclusions:
            if fnmatch(name=posix, pat=pattern):
                return False
            for part in relative.parts:
                if fnmatch(name=part, pat=pattern):
                    return False
        for pattern in self.exclusions:
            if fnmatch(name=posix, pat=pattern):
                return True
            for part in relative.parts:
                if fnmatch(name=part, pat=pattern):
                    return True
        return False

    def _process_changes(
        self,
        *,
        previous: dict[Path, EntryState],
        current: dict[Path, EntryState],
        pending: dict[Path, tuple[EntryState, float]],
        now: float,
    ) -> None:
        """Process created, modified, deleted, and settling entries.

        Args:
            previous: Snapshot from the preceding scan.
            current: Snapshot from the current scan.
            pending: Files waiting to remain stable for settle_time seconds.
            now: Current monotonic timestamp.

        """
        deleted: set[Path] = previous.keys() - current.keys()
        changed: set[Path] = {
            relative
            for relative, state in current.items()
            if previous.get(relative) != state
        }
        relative: Path
        for relative in deleted:
            pending.pop(relative, None)
            if self.mirror_deletes:
                self._delete_destination(
                    relative=relative,
                    source_snapshot=current,
                )
        for relative in sorted(changed, key=self._sort_key):
            state: EntryState = current[relative]
            if state.is_directory or state.is_symlink:
                self._copy_entry(
                    relative=relative,
                    state=state,
                    source_snapshot=current,
                )
                pending.pop(relative, None)
            else:
                pending[relative] = (state, now)
        pending_value: tuple[EntryState, float]
        for relative, pending_value in tuple(pending.items()):
            expected: EntryState = pending_value[0]
            first_stable: float = pending_value[1]
            actual: EntryState | None = current.get(relative)
            if actual is None:
                pending.pop(relative, None)
            elif actual != expected:
                pending[relative] = (actual, now)
            elif now - first_stable >= self.settle_time:
                self._copy_entry(
                    relative=relative,
                    state=actual,
                    source_snapshot=current,
                )
                pending.pop(relative, None)

    def _sync_snapshot(self, *, snapshot: dict[Path, EntryState]) -> None:
        """Copy all entries represented by a source snapshot.

        Entries are copied in parallel when the snapshot is large enough
        to benefit from a worker pool.

        Args:
            snapshot: Source snapshot to synchronize.

        """
        relatives: list[Path] = sorted(snapshot, key=self._sort_key)

        def copy_one(relative: Path) -> None:
            """Copy one snapshot entry to the destination.

            Args:
                relative: Source-relative path being synchronized.

            """
            self._copy_entry(
                relative=relative,
                state=snapshot[relative],
                source_snapshot=snapshot,
            )

        if self.workers <= 1 or len(relatives) < Constants.parallel_threshold:
            relative_item: Path
            for relative_item in relatives:
                copy_one(relative=relative_item)
            return
        pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=self.workers)
        try:
            list(pool.map(copy_one, relatives))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _copy_entry(
        self,
        *,
        relative: Path,
        state: EntryState,
        source_snapshot: dict[Path, EntryState],
    ) -> None:
        """Copy one source entry to its corresponding destination path.

        Args:
            relative: Path relative to the source root.
            state: Observed source state.
            source_snapshot: Current source snapshot for activity metadata.

        """
        source: Path = self.source / relative
        destination: Path = self.destination / relative
        old_size: int = self._entry_size(path=destination)
        try:
            if state.is_directory:
                if destination.is_symlink() or destination.is_file():
                    destination.unlink(missing_ok=True)
                if destination.is_dir():
                    return
                destination.mkdir(parents=True, exist_ok=True)
                self._record(
                    delta=ActivityDelta(
                        operation="mkdir",
                        relative_path=relative.as_posix(),
                        entry_type="directory",
                        size_delta_bytes=-old_size,
                        transferred_bytes=0,
                    ),
                    source_snapshot=source_snapshot,
                )
                self._write(message=f"DIR   {relative}\n")
                return
            destination.parent.mkdir(parents=True, exist_ok=True)
            if state.is_symlink:
                if (
                    destination.is_symlink()
                    and str(object=destination.readlink()) == state.link_target
                ):
                    return
                self._replace_with_symlink(
                    destination=destination,
                    target=state.link_target,
                )
                self._record(
                    delta=ActivityDelta(
                        operation="symlink",
                        relative_path=relative.as_posix(),
                        entry_type="symlink",
                        size_delta_bytes=state.size - old_size,
                        transferred_bytes=0,
                    ),
                    source_snapshot=source_snapshot,
                )
                self._write(message=f"LINK  {relative}\n")
                return
            if destination.is_dir() and (not destination.is_symlink()):
                rmtree(path=destination)
            if self._unchanged(destination=destination, state=state):
                return
            temporary: Path = destination.with_name(
                name=f".{destination.name}.folder-watch-copy.tmp",
            )
            temporary.unlink(missing_ok=True)
            copy2(src=source, dst=temporary, follow_symlinks=False)
            temporary.replace(target=destination)
            self._record(
                delta=ActivityDelta(
                    operation="copy",
                    relative_path=relative.as_posix(),
                    entry_type="file",
                    size_delta_bytes=state.size - old_size,
                    transferred_bytes=state.size,
                ),
                source_snapshot=source_snapshot,
            )
            self._write(message=f"COPY  {relative}\n")
        except (FileNotFoundError, PermissionError, OSError) as error:
            self._write_error(relative=relative, error=error)

    def _prune_destination(
        self,
        *,
        source_snapshot: dict[Path, EntryState],
    ) -> None:
        """Remove destination entries missing from the source tree.

        Excluded paths are removed too — mirroring means the
        destination holds only the watched view — while the activity
        record is left untouched. A stale directory is deleted as a
        whole, so its children are not evaluated separately. When the
        destination kind disagrees with the source, the stale entry is
        removed and the source entry is copied in its place.

        Args:
            source_snapshot: Current source snapshot keyed by relative
                path.

        """
        if not self.destination.is_dir():
            return
        stale: list[Path] = []
        paths: list[Path] = [self.destination]
        while paths:
            current: Path = paths.pop()
            try:
                with scandir(path=current) as iterator:
                    children: tuple[DirEntry[str], ...] = tuple(iterator)
            except OSError:
                continue
            entry: DirEntry[str]
            for entry in children:
                try:
                    is_symlink: bool = entry.is_symlink()
                    is_directory: bool = (
                        entry.is_dir(follow_symlinks=False) and not is_symlink
                    )
                except OSError:
                    continue
                child: Path = Path(entry.path)
                verdict: PruneVerdict = self._prune_verdict(
                    child=child,
                    is_symlink=is_symlink,
                    is_directory=is_directory,
                    source_snapshot=source_snapshot,
                )
                if verdict == "stale":
                    stale.append(child)
                elif verdict == "descend":
                    paths.append(child)
        self._apply_prune(stale=stale, source_snapshot=source_snapshot)

    def _apply_prune(
        self,
        *,
        stale: list[Path],
        source_snapshot: dict[Path, EntryState],
    ) -> None:
        """Delete stale destination entries, replacing mismatches.

        Removals run in parallel when the stale set is large enough to
        benefit from a worker pool.

        Args:
            stale: Destination paths absent from the source or present
                with a different kind.
            source_snapshot: Current source snapshot keyed by relative
                path.

        """

        def prune_one(path: Path) -> None:
            """Delete and optionally recopy one stale destination entry.

            Args:
                path: Absolute destination path being pruned.

            """
            relative_path: Path = path.relative_to(self.destination)
            self._delete_destination(
                relative=relative_path,
                source_snapshot=source_snapshot,
            )
            state: EntryState | None = source_snapshot.get(relative_path)
            if state is not None:
                self._copy_entry(
                    relative=relative_path,
                    state=state,
                    source_snapshot=source_snapshot,
                )

        if self.workers <= 1 or len(stale) < Constants.parallel_threshold:
            path: Path
            for path in stale:
                prune_one(path=path)
            return
        pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=self.workers)
        try:
            list(pool.map(prune_one, stale))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _prune_verdict(
        self,
        *,
        child: Path,
        is_symlink: bool,
        is_directory: bool,
        source_snapshot: dict[Path, EntryState],
    ) -> PruneVerdict:
        """Classify one destination entry against the source snapshot.

        Args:
            child: Destination entry to classify.
            is_symlink: Whether the entry is a symbolic link.
            is_directory: Whether the entry is a real directory.
            source_snapshot: Current source snapshot keyed by relative
                path.

        Returns:
            ``"descend"`` for directories also present as directories
            in the source, ``"stale"`` for entries absent from the
            source — including excluded paths, which mirror deletes
            drop from the destination — or present with a different
            kind, and ``"keep"`` for everything else, including the
            activity record.

        """
        relative: Path = child.relative_to(self.destination)
        if child.parent == self.destination and child.name in (
            Constants.activity_name,
            f".{Constants.activity_name}.tmp",
        ):
            return "keep"
        if self._excluded(relative=relative):
            return "stale"
        state: EntryState | None = source_snapshot.get(relative)
        if (
            state is None
            or is_directory != state.is_directory
            or is_symlink != state.is_symlink
        ):
            return "stale"
        return "descend" if is_directory else "keep"

    def _delete_destination(
        self,
        *,
        relative: Path,
        source_snapshot: dict[Path, EntryState],
    ) -> None:
        """Delete the destination counterpart of a removed source entry.

        Args:
            relative: Path relative to the source root.
            source_snapshot: Current source snapshot for activity metadata.

        """
        destination: Path = self.destination / relative
        old_size: int = self._entry_size(path=destination)
        try:
            if destination.is_symlink() or destination.is_file():
                destination.unlink(missing_ok=True)
            elif destination.is_dir():
                rmtree(path=destination)
            self._record(
                delta=ActivityDelta(
                    operation="delete",
                    relative_path=relative.as_posix(),
                    entry_type="entry",
                    size_delta_bytes=-old_size,
                    transferred_bytes=0,
                ),
                source_snapshot=source_snapshot,
            )
            self._write(message=f"DELETE {relative}\n")
        except (PermissionError, OSError) as error:
            self._write_error(relative=relative, error=error)

    def _record(
        self,
        *,
        delta: ActivityDelta,
        source_snapshot: dict[Path, EntryState],
        refresh_metrics: bool = False,
    ) -> None:
        """Record a completed destination operation.

        Args:
            delta: Completed operation metadata.
            source_snapshot: Current source snapshot.
            refresh_metrics: Force a fresh destination walk instead of
                the rate-limited cached metrics.

        """
        self._activity.record(
            delta=delta,
            source_metrics=self._metrics_cached(snapshot=source_snapshot),
            destination_metrics=self._destination_metrics_cached(
                refresh=refresh_metrics,
            ),
            autostart_installed=MacAutostart.installed(),
        )

    def _metrics_cached(
        self,
        *,
        snapshot: dict[Path, EntryState],
    ) -> TreeMetrics:
        """Return source metrics, reused for an unchanged snapshot.

        The snapshot argument is compared by identity and retained in
        the cache, which keeps its ``id`` stable while cached.

        Args:
            snapshot: Filesystem snapshot.

        Returns:
            Aggregate tree metrics.

        """
        with self._metrics_lock:
            cached: tuple[dict[Path, EntryState], TreeMetrics] | None = (
                self._source_metrics_cache
            )
            if cached is not None and cached[0] is snapshot:
                return cached[1]
            metrics: TreeMetrics = self._metrics(snapshot=snapshot)
            self._source_metrics_cache = (snapshot, metrics)
            return metrics

    def _destination_metrics_cached(
        self,
        *,
        refresh: bool = False,
    ) -> TreeMetrics:
        """Return destination metrics refreshed at a limited rate.

        Bulk operations record activity far faster than a full tree
        walk; caching bounds the walk to once per metrics_ttl seconds.

        Args:
            refresh: Force a fresh walk instead of the cached value.

        Returns:
            Aggregate destination-tree metrics.

        """
        with self._metrics_lock:
            now: float = monotonic()
            cached: tuple[float, TreeMetrics] | None = (
                self._destination_metrics_cache
            )
            if (
                not refresh
                and cached is not None
                and now - cached[0] < Constants.metrics_ttl
            ):
                return cached[1]
            metrics: TreeMetrics = self._destination_metrics()
            self._destination_metrics_cache = (now, metrics)
            return metrics

    def _destination_metrics(self) -> TreeMetrics:
        """Calculate current destination metrics excluding activity metadata.

        Returns:
            Aggregate destination-tree metrics.

        """
        files: int = 0
        directories: int = 0
        symlinks: int = 0
        total_size: int = 0
        entries: int = 0
        paths: list[Path] = [self.destination]
        while paths:
            current: Path = paths.pop()
            try:
                with scandir(path=current) as iterator:
                    children: tuple[DirEntry[str], ...] = tuple(iterator)
            except OSError:
                continue
            entry: DirEntry[str]
            for entry in children:
                if (
                    current == self.destination
                    and entry.name == Constants.activity_name
                ):
                    continue
                if entry.name == f".{Constants.activity_name}.tmp":
                    continue
                entries += 1
                try:
                    if entry.is_symlink():
                        symlinks += 1
                    elif entry.is_dir(follow_symlinks=False):
                        directories += 1
                        paths.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        files += 1
                        total_size += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
        return TreeMetrics(
            files=files,
            directories=directories,
            symlinks=symlinks,
            total_entries=entries,
            total_size_bytes=total_size,
        )

    def _write(self, *, message: str) -> None:
        """Write an informational message when verbose output is enabled.

        Args:
            message: Text to write.

        """
        if self.verbose:
            stdout.write(message)
            stdout.flush()


@dataclass(frozen=True, slots=True)
class WatchSettings:
    """Represent the fully resolved watcher configuration.

    Attributes:
        source: Directory tree to observe.
        destination: Directory tree receiving changed entries.
        interval: Seconds between filesystem scans.
        settle_time: Minimum stable time before a changed file is copied.
        exclude: Glob patterns matched against relative POSIX paths.
        include: Glob patterns that override exclusions for matching
            relative POSIX paths.
        initial_sync: Whether to copy the complete source tree before
            watching for subsequent changes.
        mirror_deletes: Whether source deletions remove destination
            entries and destination entries absent from the source are
            removed.
        quiet: Whether status output is suppressed.
        run: Whether the watcher loop is enabled by configuration.
        project_root: Directory containing the project pyproject.toml, or
            None for CLI-only operation.
        pyproject: Project TOML file providing ``[tool.watch]`` values, or
            None for CLI-only operation.
        workers: Parallel worker count for bulk operations, or 0 to
            auto-select from the CPU count.

    """

    source: Path
    destination: Path
    interval: float
    settle_time: float
    exclude: tuple[str, ...]
    include: tuple[str, ...]
    initial_sync: bool
    mirror_deletes: bool
    quiet: bool
    run: bool
    project_root: Path | None
    pyproject: Path | None
    workers: int = 0


class PyprojectConfig:
    """Discover and load ``[tool.watch]`` project configuration."""

    @classmethod
    def load(
        cls,
        *,
        path: Path,
    ) -> dict[str, bool | float | int | str | list[str]]:
        """Load and validate the ``[tool.watch]`` table.

        Args:
            path: Project TOML file.

        Returns:
            Validated watch configuration values.

        Raises:
            ValueError: If the TOML is invalid or unknown settings exist.

        """
        allowed: frozenset[str] = frozenset(
            {
                "source",
                "destination",
                "interval",
                "settle-time",
                "exclude",
                "include",
                "initial-sync",
                "mirror-deletes",
                "quiet",
                "run",
                "workers",
            },
        )
        document: dict[str, TomlValue] = cls._document(path=path)
        table: dict[str, TomlValue] | None = cls._watch_table(
            document=document,
            path=path,
        )
        if table is None:
            return {}
        unknown: set[str] = set(table) - allowed
        if unknown:
            msg: str = "Unknown [tool.watch] setting(s): " + ", ".join(
                sorted(unknown),
            )
            raise ValueError(msg)
        return {
            key: cls._value(key=key, value=value)
            for key, value in table.items()
        }

    @classmethod
    def fingerprint(cls, *, path: Path | None) -> str:
        """Return a stable identity for the current ``[tool.watch]`` table.

        Invalid or temporarily missing TOML still receives an identity so a
        running watcher stops promptly and the supervisor can wait for the
        next editor write instead of continuing with stale settings.

        Args:
            path: Project TOML file, or None for CLI-only operation.

        Returns:
            Stable text that changes whenever ``[tool.watch]`` changes.

        """
        if path is None:
            return "cli-only"
        try:
            document: dict[str, TomlValue] = cls._document(path=path)
            table: dict[str, TomlValue] | None = cls._watch_table(
                document=document,
                path=path,
            )
            return "table:" + dumps(
                obj=table or {},
                sort_keys=True,
                separators=(",", ":"),
            )
        except (OSError, TypeError, ValueError):
            try:
                return "raw:" + sha256(data=path.read_bytes()).hexdigest()
            except OSError:
                return "missing"

    @staticmethod
    def discover(*, start: Path) -> Path | None:
        """Find the nearest pyproject.toml at or above a starting path.

        Args:
            start: File or directory from which to search upward.

        Returns:
            Nearest pyproject.toml, or None when no project file exists.

        """
        current: Path = start.expanduser().resolve()
        if current.is_file():
            current = current.parent
        candidate: Path
        for candidate in (current, *current.parents):
            pyproject: Path = candidate / Constants.pyproject_name
            if pyproject.is_file():
                return pyproject
        return None

    @staticmethod
    def _document(*, path: Path) -> dict[str, TomlValue]:
        """Read and parse a TOML document.

        Args:
            path: Project TOML file.

        Returns:
            Parsed top-level TOML table.

        Raises:
            ValueError: If the TOML document is invalid.

        """
        try:
            with path.open(mode="rb") as stream:
                return load_toml(stream)
        except TOMLDecodeError as error:
            msg: str = f"Invalid TOML in {path}: {error}"
            raise ValueError(msg) from error

    @staticmethod
    def _watch_table(
        *,
        document: dict[str, TomlValue],
        path: Path,
    ) -> dict[str, TomlValue] | None:
        """Return the ``[tool.watch]`` table when present.

        Args:
            document: Parsed top-level TOML table.
            path: Project TOML file, used for error messages.

        Returns:
            The watch table, or None when the file does not configure it.

        Raises:
            TypeError: If ``tool.watch`` is not a TOML table.

        """
        tool_value: TomlValue | None = document.get("tool")
        if not isinstance(tool_value, dict):
            return None
        watch_value: TomlValue | None = cast(
            typ="dict[str, TomlValue]",
            val=tool_value,
        ).get("watch")
        if watch_value is None:
            return None
        if not isinstance(watch_value, dict):
            msg: str = f"[tool.watch] in {path} must be a TOML table."
            raise TypeError(msg)
        return cast(typ="dict[str, TomlValue]", val=watch_value)

    @staticmethod
    def _value(
        *,
        key: str,
        value: TomlValue,
    ) -> bool | float | int | str | list[str]:
        """Validate and coerce one ``[tool.watch]`` value.

        Args:
            key: Setting name inside ``[tool.watch]``.
            value: Parsed TOML value.

        Returns:
            The value coerced to the type expected for the key.

        Raises:
            TypeError: If the value has the wrong type for the key.

        """
        if key in {"source", "destination"}:
            if not isinstance(value, str) or not value:
                msg: str = f"[tool.watch].{key} must be a non-empty string."
                raise TypeError(msg)
            return value
        if key == "workers":
            if isinstance(value, bool) or not isinstance(value, int):
                msg = f"[tool.watch].{key} must be an integer."
                raise TypeError(msg)
            return value
        if key in {"interval", "settle-time"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                msg = f"[tool.watch].{key} must be a number."
                raise TypeError(msg)
            return float(value)
        if key in {"exclude", "include"}:
            if not isinstance(value, list) or not all(
                isinstance(item, str)
                for item in cast(typ="list[TomlValue]", val=value)
            ):
                msg = f"[tool.watch].{key} must be an array of strings."
                raise TypeError(msg)
            return cast(typ="list[str]", val=value)
        if not isinstance(value, bool):
            msg = f"[tool.watch].{key} must be a boolean."
            raise TypeError(msg)
        return value


class CliArguments(Namespace):
    """Provide precise types for command-line argument values.

    Attributes:
        source: Watched source directory, or None when unset.
        destination: Mirrored destination directory, or None when unset.
        pyproject: Explicit pyproject.toml path, or None for discovery.
        interval: Seconds between filesystem scans, or None when unset.
        settle_time: Minimum stable time before a changed file is copied,
            or None when unset.
        exclude: Exclusion glob patterns, or None when unset.
        include: Glob patterns overriding exclusions, or None when unset.
        initial_sync: Whether to copy the complete source tree first, or
            None when unset.
        mirror_deletes: Whether source deletions remove destination
            entries and destination entries absent from the source are
            removed, or None when unset.
        quiet: Whether status output is suppressed, or None when unset.
        workers: Parallel worker count for bulk operations, or None
            when unset.
        install_autostart: Whether to install the autostart agent.
        uninstall_autostart: Whether to remove the autostart agent.
        autostart_status: Whether to print the autostart agent status.

    """

    source: Path | None
    destination: Path | None
    pyproject: Path | None
    interval: float | None
    settle_time: float | None
    exclude: list[str] | None
    include: list[str] | None
    initial_sync: bool | None
    mirror_deletes: bool | None
    quiet: bool | None
    workers: int | None
    install_autostart: bool
    uninstall_autostart: bool
    autostart_status: bool


class FolderWatchCopyCli:
    """Resolve project/CLI configuration and launch FolderWatchCopy."""

    @classmethod
    def run(cls) -> int:
        """Parse arguments, manage autostart, or run the watcher.

        Returns:
            Process exit status.

        """
        arguments: CliArguments = CliArguments()
        cls.parser().parse_args(namespace=arguments)
        operation_count: int = sum(
            (
                arguments.install_autostart,
                arguments.uninstall_autostart,
                arguments.autostart_status,
            ),
        )
        if operation_count > 1:
            stderr.write(
                dedent(
                    text=(
                        "    Configuration error: Choose only one autostar"
                        "t management operation.\n    "
                    ),
                ),
            )
            return 2
        try:
            if arguments.autostart_status:
                stdout.write(f"{dumps(obj=MacAutostart.status(), indent=2)}\n")
                return 0
            if arguments.uninstall_autostart:
                removed: bool = MacAutostart.uninstall()
                stdout.write(
                    "Autostart removed.\n"
                    if removed
                    else "Autostart was not installed.\n",
                )
                return 0
            settings: WatchSettings = cls._settings(arguments=arguments)
            if arguments.install_autostart:
                MacAutostart.install_package(settings=settings)
                stdout.write(
                    f"Autostart installed: {MacAutostart.plist_path()}\n",
                )
                return 0
            return cls._supervise(
                arguments=arguments,
                initial_settings=settings,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            stderr.write(f"Configuration error: {error}\n")
            return 2

    @staticmethod
    def parser() -> ArgumentParser:
        """Build the command-line parser.

        Returns:
            Configured argument parser.

        """
        parser: ArgumentParser = ExactusArgumentParser(
            description="Recursively watch a project tree and copy changed "
            "entries. Values in [tool.watch] are used when "
            "CLI values are absent.",
        )
        parser.add_argument(
            "source",
            type=Path,
            nargs="?",
            help="Directory to watch.",
        )
        parser.add_argument(
            "destination",
            type=Path,
            nargs="?",
            help="Directory receiving changed files and folders.",
        )
        parser.add_argument(
            "--pyproject",
            type=Path,
            default=None,
            metavar="PATH",
            help="Use an explicit pyproject.toml instead of upward discovery.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=None,
            metavar="SECONDS",
        )
        parser.add_argument(
            "--settle-time",
            type=float,
            default=None,
            metavar="SECONDS",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=None,
            metavar="COUNT",
            help="Parallel worker count for bulk operations (0 = auto).",
        )
        parser.add_argument(
            "--exclude",
            action="append",
            default=None,
            metavar="GLOB",
        )
        parser.add_argument(
            "--include",
            action="append",
            default=None,
            metavar="GLOB",
            help="Keep entries matching GLOB even when excluded.",
        )
        parser.add_argument(
            "--initial-sync",
            action="store_true",
            default=None,
        )
        parser.add_argument(
            "--no-initial-sync",
            action="store_false",
            dest="initial_sync",
        )
        parser.add_argument(
            "--mirror-deletes",
            action="store_true",
            default=None,
        )
        parser.add_argument(
            "--no-mirror-deletes",
            action="store_false",
            dest="mirror_deletes",
        )
        parser.add_argument("--quiet", action="store_true", default=None)
        parser.add_argument("--no-quiet", action="store_false", dest="quiet")
        parser.add_argument("--install-autostart", action="store_true")
        parser.add_argument("--uninstall-autostart", action="store_true")
        parser.add_argument("--autostart-status", action="store_true")
        return parser

    @classmethod
    def _supervise(
        cls,
        *,
        arguments: CliArguments,
        initial_settings: WatchSettings,
    ) -> int:
        """Run watchers and replace them when ``[tool.watch]`` changes.

        A false ``run`` setting pauses file copying without terminating this
        supervisor. It continues polling the project file and starts a fresh
        watcher as soon as a later valid configuration enables ``run``.

        Args:
            arguments: Original CLI values, retained as overrides across
                configuration reloads.
            initial_settings: Settings resolved before entering the loop.

        Returns:
            Process exit status.

        """
        settings: WatchSettings = initial_settings
        pyproject: Path | None = settings.pyproject
        fingerprint: str = PyprojectConfig.fingerprint(path=pyproject)
        while True:
            try:
                if not settings.run:
                    if not settings.quiet:
                        stdout.write(
                            dedent(
                                text=(
                                    "    Watcher paused by [tool.watch].ru"
                                    "n = false.\n    Watching pyproject.to"
                                    "ml for configuration changes. Press C"
                                    "trl+C to stop.\n    "
                                ),
                            ),
                        )
                        stdout.flush()
                    cls._wait_for_configuration(
                        pyproject=pyproject,
                        fingerprint=fingerprint,
                    )
                else:
                    try:
                        watcher: FolderWatchCopy = FolderWatchCopy(
                            source=settings.source,
                            destination=settings.destination,
                            interval=settings.interval,
                            settle_time=settings.settle_time,
                            exclusions=settings.exclude,
                            inclusions=settings.include,
                            mirror_deletes=settings.mirror_deletes,
                            verbose=not settings.quiet,
                            workers=settings.workers,
                        )
                    except ValueError as error:
                        stderr.write(f"Configuration error: {error}\n")
                        stderr.flush()
                        cls._wait_for_configuration(
                            pyproject=pyproject,
                            fingerprint=fingerprint,
                        )
                        settings, fingerprint = cls._reload_configuration(
                            arguments=arguments,
                            pyproject=pyproject,
                        )
                        continue

                    def configuration_changed(
                        expected: str = fingerprint,
                    ) -> bool:
                        """Return whether the watched config fingerprint moved.

                        Args:
                            expected: Fingerprint captured when the watcher
                                last (re)loaded its configuration.

                        Returns:
                            Whether ``pyproject.toml`` changed on disk.

                        """
                        return expected != PyprojectConfig.fingerprint(
                            path=pyproject,
                        )

                    restart: bool = watcher.run(
                        initial_sync=settings.initial_sync,
                        should_stop=configuration_changed,
                    )
                    if not restart:
                        return 0
                settings, fingerprint = cls._reload_configuration(
                    arguments=arguments,
                    pyproject=pyproject,
                )
                if not settings.quiet:
                    stdout.write("Watch configuration changed; reloading.\n")
                    stdout.flush()
            except KeyboardInterrupt:
                if not settings.quiet:
                    stdout.write("Stopped.\n")
                    stdout.flush()
                return 0

    @classmethod
    def _reload_configuration(
        cls,
        *,
        arguments: CliArguments,
        pyproject: Path | None,
    ) -> tuple[WatchSettings, str]:
        """Wait until a changed configuration becomes valid and load it.

        Editors can replace ``pyproject.toml`` through several short-lived
        writes. A malformed or missing intermediate file keeps the worker
        stopped, but it never kills the supervisor.

        Args:
            arguments: Original CLI values retained as overrides.
            pyproject: Project file being observed.

        Returns:
            Valid resolved settings and the fingerprint they came from.

        """
        while True:
            fingerprint: str = PyprojectConfig.fingerprint(path=pyproject)
            try:
                return (cls._settings(arguments=arguments), fingerprint)
            except (TypeError, ValueError) as error:
                stderr.write(f"Configuration error: {error}\n")
                stderr.flush()
                cls._wait_for_configuration(
                    pyproject=pyproject,
                    fingerprint=fingerprint,
                )

    @classmethod
    def _settings(cls, *, arguments: CliArguments) -> WatchSettings:
        """Resolve CLI values over project-local TOML configuration.

        Args:
            arguments: Parsed command-line namespace.

        Returns:
            Complete watcher settings.

        Raises:
            ValueError: If source or destination cannot be resolved.

        """
        pyproject: Path | None
        if arguments.pyproject is not None:
            pyproject = arguments.pyproject.expanduser().resolve()
            if not pyproject.is_file():
                msg: str = f"pyproject.toml does not exist: {pyproject}"
                raise ValueError(msg)
        else:
            pyproject = PyprojectConfig.discover(start=Path.cwd())
        config: dict[str, bool | float | int | str | list[str]] = (
            PyprojectConfig.load(path=pyproject)
            if pyproject is not None
            else {}
        )
        project_root: Path | None = (
            pyproject.parent if pyproject is not None else None
        )
        source: Path = cls._resolve_path(
            cli=arguments.source,
            configured=config.get("source"),
            project_root=project_root,
            name="SOURCE / [tool.watch].source",
        )
        destination: Path = cls._resolve_path(
            cli=arguments.destination,
            configured=config.get("destination"),
            project_root=project_root,
            name="DESTINATION / [tool.watch].destination",
        )
        return WatchSettings(
            source=source,
            destination=destination,
            interval=cls._float_value(
                cli=arguments.interval,
                configured=config.get("interval"),
                default=0.5,
            ),
            settle_time=cls._float_value(
                cli=arguments.settle_time,
                configured=config.get("settle-time"),
                default=0.5,
            ),
            exclude=tuple(
                arguments.exclude
                if arguments.exclude is not None
                else cls._string_list(value=config.get("exclude"), default=[]),
            ),
            include=tuple(
                arguments.include
                if arguments.include is not None
                else cls._string_list(value=config.get("include"), default=[]),
            ),
            initial_sync=cls._bool_value(
                cli=arguments.initial_sync,
                configured=config.get("initial-sync"),
                default=False,
            ),
            mirror_deletes=cls._bool_value(
                cli=arguments.mirror_deletes,
                configured=config.get("mirror-deletes"),
                default=False,
            ),
            quiet=cls._bool_value(
                cli=arguments.quiet,
                configured=config.get("quiet"),
                default=False,
            ),
            run=cls._bool_value(
                cli=None,
                configured=config.get("run"),
                default=True,
            ),
            project_root=project_root,
            pyproject=pyproject,
            workers=cls._int_value(
                cli=arguments.workers,
                configured=config.get("workers"),
                default=0,
            ),
        )

    @staticmethod
    def _wait_for_configuration(
        *,
        pyproject: Path | None,
        fingerprint: str,
    ) -> None:
        """Block until the watched configuration table changes.

        Args:
            pyproject: Project TOML file being observed.
            fingerprint: Table identity already consumed by the supervisor.

        Raises:
            ValueError: If no project file exists to observe.

        """
        if pyproject is None:
            msg: str = "Live configuration reload requires pyproject.toml."
            raise ValueError(msg)
        while PyprojectConfig.fingerprint(path=pyproject) == fingerprint:
            sleep(0.1)

    @staticmethod
    def _resolve_path(
        *,
        cli: Path | None,
        configured: bool | float | str | list[str] | None,
        project_root: Path | None,
        name: str,
    ) -> Path:
        """Resolve a CLI or TOML path.

        Args:
            cli: Explicit command-line path.
            configured: TOML value.
            project_root: Directory containing pyproject.toml.
            name: Setting name for errors.

        Returns:
            Absolute resolved path.

        Raises:
            ValueError: If no path is available.

        """
        if cli is not None:
            return cli.expanduser().resolve()
        if isinstance(configured, str):
            configured_path: Path = Path(configured).expanduser()
            if configured_path.is_absolute():
                return configured_path.resolve()
            if project_root is None:
                msg: str = (
                    f"Cannot resolve relative {name} without pyproject.toml."
                )
                raise ValueError(msg)
            return (project_root / configured_path).resolve()
        msg = (
            f"{name} is required. Pass it on the CLI or configure "
            "[tool.watch]."
        )
        raise ValueError(msg)

    @staticmethod
    def _int_value(
        *,
        cli: int | None,
        configured: bool | float | str | list[str] | None,
        default: int,
    ) -> int:
        """Resolve an integer setting with CLI precedence.

        Args:
            cli: Explicit command-line value, or None when unset.
            configured: Validated ``[tool.watch]`` value, an integer
                when the setting applies.
            default: Fallback used when neither source provides a value.

        Returns:
            CLI value when present, otherwise the configured integer or
            the default.

        """
        if cli is not None:
            return cli
        if isinstance(configured, int) and not isinstance(configured, bool):
            return configured
        return default

    @staticmethod
    def _float_value(
        *,
        cli: float | None,
        configured: bool | float | str | list[str] | None,
        default: float,
    ) -> float:
        """Resolve a floating-point setting with CLI precedence.

        Args:
            cli: Explicit command-line value, or None when unset.
            configured: Validated ``[tool.watch]`` value, a float when the
                setting applies.
            default: Fallback used when neither source provides a value.

        Returns:
            CLI value when present, otherwise the configured float or the
            default.

        """
        return (
            cli
            if cli is not None
            else configured
            if isinstance(configured, float)
            else default
        )

    @staticmethod
    def _bool_value(
        *,
        cli: bool | None,
        configured: bool | float | str | list[str] | None,
        default: bool,
    ) -> bool:
        """Resolve a boolean setting with CLI precedence.

        Args:
            cli: Explicit command-line value, or None when unset.
            configured: Validated ``[tool.watch]`` value, a boolean when the
                setting applies.
            default: Fallback used when neither source provides a value.

        Returns:
            CLI value when present, otherwise the configured boolean or the
            default.

        """
        return (
            cli
            if cli is not None
            else configured
            if isinstance(configured, bool)
            else default
        )

    @staticmethod
    def _string_list(
        *,
        value: bool | float | str | list[str] | None,
        default: list[str],
    ) -> list[str]:
        """Resolve an already validated TOML string array.

        Args:
            value: Validated TOML value, a string list when configured.
            default: Fallback list used when the value is not a list.

        Returns:
            The configured string list or the default.

        """
        return value if isinstance(value, list) else default


def main() -> int:
    """Run the folder watcher command.

    Returns:
        Process exit status.

    """
    return FolderWatchCopyCli.run()
