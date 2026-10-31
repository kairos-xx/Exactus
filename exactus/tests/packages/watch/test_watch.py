# Copyright (c) 2026
"""Exercise the project-local filesystem watcher and its CLI."""

from __future__ import annotations

from json import loads
from pathlib import Path
from subprocess import CompletedProcess
from textwrap import dedent
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from exactus.packages.watch import core
from exactus.tests.common.support import (
    Constant,
    dig,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    private,
    private_as,
    private_call,
    private_result,
    require,
    require_type,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from exactus.packages.watch.core import EntryState


def make_watcher(
    tmp_path: Path,
    *,
    mirror: bool = True,
    settle: float = 0.0,
) -> core.FolderWatchCopy:
    """Build a watcher under ``tmp_path`` with fast polling.

    Args:
        tmp_path: Pytest temporary directory.
        mirror: Whether source deletions propagate to the destination.
        settle: Settle time passed to the watcher.

    Returns:
        Configured watcher instance.

    """
    source: Path = tmp_path / "source"
    source.mkdir()
    return core.FolderWatchCopy(
        source=source,
        destination=tmp_path / "dest",
        interval=0.01,
        settle_time=settle,
        exclusions=("*.tmp", ".git"),
        inclusions=(),
        mirror_deletes=mirror,
        verbose=False,
    )


def snapshot_of(watcher: core.FolderWatchCopy) -> dict[Path, core.EntryState]:
    """Return the watcher's private source snapshot.

    Args:
        watcher: Watcher whose source tree is scanned.

    Returns:
        Relative-path snapshot of the source tree.

    """
    return cast(
        typ="dict[Path, core.EntryState]",
        val=private_call(owner=watcher, name="_snapshot"),
    )


def resolve_path(
    *,
    cli: Path | None,
    configured: object,
    project_root: Path | None,
) -> Path:
    """Invoke the CLI's private ``_resolve_path`` helper.

    ``private_call`` cannot forward a positional ``name`` argument, so the
    static method is fetched once and called directly.

    Args:
        cli: Explicit command-line path.
        configured: Configured TOML value.
        project_root: Directory containing ``pyproject.toml``.

    Returns:
        Absolute resolved path.

    """
    resolver: Callable[..., Path] = cast(
        typ="Callable[..., Path]",
        val=private(owner=core.FolderWatchCopyCli, name="_resolve_path"),
    )
    return resolver(
        cli=cli,
        configured=configured,
        project_root=project_root,
        name="source",
    )


def test_config_validation_and_helpers(tmp_path: Path) -> None:
    """Reject invalid configurations and compute snapshot helpers.

    Args:
        tmp_path: Pytest temporary directory.

    """
    with pytest.raises(expected_exception=ValueError, match="not a directory"):
        core.FolderWatchCopy(
            source=tmp_path / "missing",
            destination=tmp_path / "d",
            interval=1.0,
            settle_time=0.0,
            exclusions=(),
            inclusions=(),
            mirror_deletes=False,
            verbose=False,
        )
    source: Path = tmp_path / "s"
    source.mkdir()
    invalid: tuple[tuple[Path, float, float, str], ...] = (
        (source, 1.0, 0.0, "different directories"),
        (source / "d", 1.0, 0.0, "inside the watched source"),
        (tmp_path, 1.0, 0.0, "inside the destination tree"),
        (tmp_path / "d", 0.0, 0.0, "greater than zero"),
        (tmp_path / "d", 1.0, -1.0, "cannot be negative"),
    )
    for destination, interval, settle, message in invalid:
        with pytest.raises(expected_exception=ValueError, match=message):
            core.FolderWatchCopy(
                source=source,
                destination=destination,
                interval=interval,
                settle_time=settle,
                exclusions=(),
                inclusions=(),
                mirror_deletes=False,
                verbose=False,
            )
    key: tuple[int, str] = cast(
        typ="tuple[int, str]",
        val=private_call(
            owner=core.FolderWatchCopy,
            name="_sort_key",
            relative=Path("a/b"),
        ),
    )
    expect_equal(actual=key, expected=(2, "a/b"))
    metrics: core.TreeMetrics = private_result(
        owner=core.FolderWatchCopy,
        name="_metrics",
        kind=core.TreeMetrics,
        snapshot={
            Path("d"): core.EntryState(
                is_directory=True,
                is_symlink=False,
                size=0,
                modified_ns=1,
                link_target=None,
            ),
            Path("f"): core.EntryState(
                is_directory=False,
                is_symlink=False,
                size=3,
                modified_ns=1,
                link_target=None,
            ),
            Path("l"): core.EntryState(
                is_directory=False,
                is_symlink=True,
                size=2,
                modified_ns=1,
                link_target="x",
            ),
        },
    )
    expect_equal(
        actual=metrics,
        expected=core.TreeMetrics(
            files=1,
            directories=1,
            symlinks=1,
            total_entries=3,
            total_size_bytes=3,
        ),
    )


def test_snapshot_sync_activity_changes_and_delete(tmp_path: Path) -> None:
    """Mirror creations, edits and deletions into the destination tree.

    Args:
        tmp_path: Pytest temporary directory.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path, settle=0.5)
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    (source / "dir").mkdir()
    _ = (source / "dir" / "a.txt").write_text(data="abc")
    _ = (source / "skip.tmp").write_text(data="skip")
    (source / ".git").mkdir()
    _ = (source / ".git" / "x").write_text(data="x")
    (source / "link").symlink_to(target="dir/a.txt")
    snap: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    expect_not_in(member=Path("skip.tmp"), container=snap)
    expect_not_in(member=Path(".git"), container=snap)
    expect_true(condition=snap[Path("link")].is_symlink)
    activity: core.ActivityRecorder = private_as(
        owner=watcher,
        name="_activity",
        kind=core.ActivityRecorder,
    )
    activity.write_started(
        source_metrics=private_result(
            owner=watcher,
            name="_metrics",
            kind=core.TreeMetrics,
            snapshot=snap,
        ),
        destination_metrics=private_result(
            owner=watcher,
            name="_destination_metrics",
            kind=core.TreeMetrics,
        ),
        autostart_installed=False,
    )
    private_call(owner=watcher, name="_sync_snapshot", snapshot=snap)
    expect_equal(actual=(dest / "dir" / "a.txt").read_text(), expected="abc")
    expect_true(condition=(dest / "link").is_symlink())
    data: dict[str, object] = cast(
        typ="dict[str, object]",
        val=require_type(
            value=loads(s=(dest / core.Constants.activity_name).read_text()),
            kind=dict,
        ),
    )
    expect_equal(
        actual=dig(document=data, path=("updates_this_run",)),
        expected=3,
    )
    expect_equal(
        actual=dig(document=data, path=("source", "files")),
        expected=1,
    )
    previous: dict[Path, core.EntryState] = snap
    _ = (source / "dir" / "a.txt").write_text(data="abcdef")
    current: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    pending: dict[Path, tuple[core.EntryState, float]] = {}
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=previous,
        current=current,
        pending=pending,
        now=1.0,
    )
    expect_in(member=Path("dir/a.txt"), container=pending)
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=current,
        current=current,
        pending=pending,
        now=2.0,
    )
    expect_equal(
        actual=(dest / "dir" / "a.txt").read_text(),
        expected="abcdef",
    )
    (source / "dir" / "a.txt").unlink()
    latest: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=current,
        current=latest,
        pending=pending,
        now=3.0,
    )
    expect_false(condition=(dest / "dir" / "a.txt").exists())
    remaining: core.TreeMetrics = private_result(
        owner=watcher,
        name="_destination_metrics",
        kind=core.TreeMetrics,
    )
    expect_equal(actual=remaining.files, expected=0)


def test_mirror_prune_removes_excluded_destination_entries(
    tmp_path: Path,
) -> None:
    """Excluded destination entries are pruned under mirror deletes.

    Adding an exclusion after files were already synced must not leave
    stale copies behind; the activity record stays untouched because it
    belongs to the watcher rather than the mirrored view.

    Args:
        tmp_path: Pytest temporary directory.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path)
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    _ = (source / "keep.txt").write_text(data="k")
    dest.mkdir()
    (dest / ".git").mkdir()
    _ = (dest / ".git" / "x").write_text(data="x")
    _ = (dest / "junk.tmp").write_text(data="j")
    _ = (dest / "keep.txt").write_text(data="k")
    _ = (dest / core.Constants.activity_name).write_text(data="{}")
    private_call(
        owner=watcher,
        name="_prune_destination",
        source_snapshot=snapshot_of(watcher=watcher),
    )
    expect_false(condition=(dest / ".git").exists())
    expect_false(condition=(dest / "junk.tmp").exists())
    expect_true(condition=(dest / core.Constants.activity_name).is_file())
    expect_true(condition=(dest / "keep.txt").is_file())


def test_inclusions_override_exclusions(tmp_path: Path) -> None:
    """Included paths stay watched and protected even when excluded.

    Args:
        tmp_path: Pytest temporary directory.

    """
    source: Path = tmp_path / "source"
    source.mkdir()
    watcher: core.FolderWatchCopy = core.FolderWatchCopy(
        source=source,
        destination=tmp_path / "dest",
        interval=0.01,
        settle_time=0.0,
        exclusions=(".*", "*.tmp"),
        inclusions=(".DS_Store",),
        mirror_deletes=True,
        verbose=False,
    )
    _ = (source / ".DS_Store").write_text(data="ds")
    _ = (source / ".hidden").write_text(data="h")
    snap: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    expect_in(member=Path(".DS_Store"), container=snap)
    expect_not_in(member=Path(".hidden"), container=snap)
    dest: Path = tmp_path / "dest"
    dest.mkdir()
    _ = (dest / ".DS_Store").write_text(data="ds")
    (dest / ".hidden").mkdir()
    private_call(
        owner=watcher,
        name="_prune_destination",
        source_snapshot=snap,
    )
    expect_true(condition=(dest / ".DS_Store").is_file())
    expect_false(condition=(dest / ".hidden").exists())


def test_pending_change_reset_and_no_delete_mirroring(tmp_path: Path) -> None:
    """Reset settled entries and keep deletions when mirroring is off.

    Args:
        tmp_path: Pytest temporary directory.

    """
    watcher: core.FolderWatchCopy = make_watcher(
        tmp_path=tmp_path,
        mirror=False,
        settle=5.0,
    )
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    entry: Path = source / "a"
    _ = entry.write_text(data="1")
    previous: dict[Path, core.EntryState] = {}
    current: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    pending: dict[Path, tuple[core.EntryState, float]] = {}
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=previous,
        current=current,
        pending=pending,
        now=1.0,
    )
    _ = entry.write_text(data="22")
    changed: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=current,
        current=changed,
        pending=pending,
        now=2.0,
    )
    expect_equal(actual=pending[Path("a")][0].size, expected=2)
    entry.unlink()
    empty: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)
    private_call(
        owner=watcher,
        name="_process_changes",
        previous=changed,
        current=empty,
        pending=pending,
        now=3.0,
    )
    expect_equal(actual=pending, expected={})
    expect_false(condition=dest.exists())


def test_destination_type_replacement_and_entry_size(tmp_path: Path) -> None:
    """Replace destination entries when their type changes.

    Args:
        tmp_path: Pytest temporary directory.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path)
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    dest.mkdir()
    _ = (source / "x").write_text(data="file")
    (dest / "x").mkdir()
    snap = snapshot_of(watcher=watcher)
    private_call(
        owner=watcher,
        name="_copy_entry",
        relative=Path("x"),
        state=snap[Path("x")],
        source_snapshot=snap,
    )
    expect_equal(actual=(dest / "x").read_text(), expected="file")
    size: int = private_result(
        owner=watcher,
        name="_entry_size",
        kind=int,
        path=dest / "x",
    )
    expect_equal(actual=size, expected=4)
    (source / "x").unlink()
    (source / "x").mkdir()
    snap: dict[Path, EntryState] = snapshot_of(watcher=watcher)
    private_call(
        owner=watcher,
        name="_copy_entry",
        relative=Path("x"),
        state=snap[Path("x")],
        source_snapshot=snap,
    )
    expect_true(condition=(dest / "x").is_dir())
    size = private_result(
        owner=watcher,
        name="_entry_size",
        kind=int,
        path=dest / "x",
    )
    expect_equal(actual=size, expected=0)
    with pytest.raises(
        expected_exception=ValueError,
        match="Missing symbolic-link target",
    ):
        private_call(
            owner=watcher,
            name="_replace_with_symlink",
            destination=dest / "bad",
            target=None,
        )


def test_pyproject_discovery_loading_and_errors(tmp_path: Path) -> None:
    """Discover pyproject.toml upward and validate [tool.watch] values.

    Args:
        tmp_path: Pytest temporary directory.

    """
    project: Path = tmp_path / "p"
    nested: Path = project / "a" / "b"
    nested.mkdir(parents=True)
    pyproject: Path = project / "pyproject.toml"
    _ = pyproject.write_text(
        data=(
            dedent(
                text=(
                    '    [tool.watch]\n    source="."\n    destination="..'
                    '/backup"\n    interval=1\n    settle-time=0.2\n    ex'
                    'clude=["*.tmp"]\n    initial-sync=true\n    mirror-de'
                    "letes=false\n    quiet=true\n    run=false\n    "
                ),
            )
        ),
    )
    expect_equal(
        actual=core.PyprojectConfig.discover(start=nested),
        expected=pyproject,
    )
    config: dict[str, bool | float | str | list[str]] = (
        core.PyprojectConfig.load(path=pyproject)
    )
    expect_equal(actual=config["interval"], expected=1.0)
    expect_equal(actual=config["initial-sync"], expected=True)
    expect_equal(actual=config["run"], expected=False)
    expect_none(value=core.PyprojectConfig.discover(start=tmp_path / "none"))
    cases: tuple[tuple[str, type[Exception], str], ...] = (
        ("x = [", ValueError, "Invalid TOML"),
        ("[tool]\nwatch=1", TypeError, "must be a TOML table"),
        ("[tool.watch]\nwat=1", ValueError, "Unknown"),
        ("[tool.watch]\nsource=1", TypeError, "non-empty string"),
        ("[tool.watch]\ninterval=true", TypeError, "must be a number"),
        ("[tool.watch]\nexclude=[1]", TypeError, "array of strings"),
        ('[tool.watch]\nquiet="x"', TypeError, "must be a boolean"),
    )
    for text, error, message in cases:
        _ = pyproject.write_text(data=text)
        with pytest.raises(expected_exception=error, match=message):
            core.PyprojectConfig.load(path=pyproject)
    _ = pyproject.write_text(data="x=1")
    expect_equal(actual=core.PyprojectConfig.load(path=pyproject), expected={})
    _ = pyproject.write_text(data="[tool]\nx=1")
    expect_equal(actual=core.PyprojectConfig.load(path=pyproject), expected={})


def test_settings_precedence_and_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefer CLI values over [tool.watch] and reject bad resolution.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "p"
    project.mkdir()
    pyproject: Path = project / "pyproject.toml"
    _ = pyproject.write_text(
        data=(
            dedent(
                text=(
                    '    [tool.watch]\n    source="."\n    destination="..'
                    '/d"\n    interval=2.0\n    initial-sync=true\n    exc'
                    'lude=["x"]\n    '
                ),
            )
        ),
    )
    monkeypatch.chdir(path=project)
    arguments: core.CliArguments = core.CliArguments(
        source=None,
        destination=None,
        pyproject=None,
        interval=3.0,
        settle_time=None,
        exclude=None,
        include=None,
        initial_sync=False,
        mirror_deletes=None,
        quiet=None,
        workers=None,
        install_autostart=False,
        uninstall_autostart=False,
        autostart_status=False,
    )
    settings: core.WatchSettings = private_result(
        owner=core.FolderWatchCopyCli,
        name="_settings",
        kind=core.WatchSettings,
        arguments=arguments,
    )
    expect_equal(actual=settings.source, expected=project.resolve())
    expect_equal(actual=settings.interval, expected=3.0)
    expect_false(condition=settings.initial_sync)
    expect_equal(actual=settings.exclude, expected=("x",))
    interval: float = private_result(
        owner=core.FolderWatchCopyCli,
        name="_float_value",
        kind=float,
        cli=None,
        configured="x",
        default=4.0,
    )
    expect_equal(actual=interval, expected=4.0)
    flag: bool = private_result(
        owner=core.FolderWatchCopyCli,
        name="_bool_value",
        kind=bool,
        cli=None,
        configured=1.0,
        default=True,
    )
    expect_true(condition=flag)
    names: list[str] = cast(
        typ="list[str]",
        val=private_call(
            owner=core.FolderWatchCopyCli,
            name="_string_list",
            value=None,
            default=["d"],
        ),
    )
    expect_equal(actual=names, expected=["d"])
    with pytest.raises(
        expected_exception=ValueError,
        match="Cannot resolve relative",
    ):
        resolve_path(cli=None, configured="x", project_root=None)
    with pytest.raises(expected_exception=ValueError, match="is required"):
        resolve_path(cli=None, configured=None, project_root=project)
    arguments.pyproject = tmp_path / "missing.toml"
    with pytest.raises(
        expected_exception=ValueError,
        match="pyproject\\.toml does not exist",
    ):
        private_call(
            owner=core.FolderWatchCopyCli,
            name="_settings",
            arguments=arguments,
        )


def test_autostart_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover LaunchAgent install, status, uninstall and failure paths.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=core, name="platform", value="linux")
    with pytest.raises(expected_exception=RuntimeError, match="only on macOS"):
        core.MacAutostart.require_macos()
    monkeypatch.setattr(target=core, name="platform", value="darwin")
    monkeypatch.setattr(
        target=Path,
        name="home",
        value=staticmethod(Constant(value=tmp_path)),
    )
    expect_false(condition=core.MacAutostart.installed())

    def ok_launchctl(*, arguments: list[str]) -> CompletedProcess[str]:
        """Pretend every launchctl invocation succeeds.

        Args:
            arguments: Arguments passed to launchctl.

        Returns:
            Successful completed process.

        """
        return CompletedProcess(
            args=arguments,
            returncode=0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_launchctl",
        value=staticmethod(ok_launchctl),
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_uid",
        value=staticmethod(Constant(value=501)),
    )
    source: Path = tmp_path / "s"
    source.mkdir()
    settings: core.WatchSettings = core.WatchSettings(
        source=source,
        destination=tmp_path / "d",
        interval=0.5,
        settle_time=0.2,
        exclude=("x",),
        include=(),
        initial_sync=True,
        mirror_deletes=True,
        quiet=False,
        run=True,
        project_root=tmp_path,
        pyproject=tmp_path / "pyproject.toml",
    )
    core.MacAutostart.install_package(settings=settings)
    expect_true(condition=core.MacAutostart.installed())
    expect_equal(actual=core.MacAutostart.status()["loaded"], expected=True)
    expect_true(condition=core.MacAutostart.uninstall())
    expect_false(condition=core.MacAutostart.uninstall())

    def bad_launchctl(*, arguments: list[str]) -> CompletedProcess[str]:
        """Pretend every launchctl invocation fails.

        Args:
            arguments: Arguments passed to launchctl.

        Returns:
            Failed completed process.

        """
        return CompletedProcess(
            args=arguments,
            returncode=1,
            stdout="",
            stderr="bad",
        )

    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_launchctl",
        value=staticmethod(bad_launchctl),
    )
    with pytest.raises(expected_exception=RuntimeError, match="bad"):
        private_call(
            owner=core.MacAutostart,
            name="_bootout",
            ignore_failure=False,
        )


def test_uid_bootstrap_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Propagate uid lookup and launchctl bootstrap failures.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=core,
        name="run",
        value=Constant(
            value=CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="uid bad",
            ),
        ),
    )
    with pytest.raises(expected_exception=RuntimeError, match="uid bad"):
        private_call(owner=core.MacAutostart, name="_uid")
    monkeypatch.setattr(target=core, name="platform", value="darwin")
    monkeypatch.setattr(
        target=Path,
        name="home",
        value=staticmethod(Constant(value=tmp_path)),
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_uid",
        value=staticmethod(Constant(value=1)),
    )

    def bad_launchctl(*, arguments: list[str]) -> CompletedProcess[str]:
        """Pretend launchctl bootstrap fails.

        Args:
            arguments: Arguments passed to launchctl.

        Returns:
            Failed completed process.

        """
        return CompletedProcess(
            args=arguments,
            returncode=1,
            stdout="",
            stderr="boot bad",
        )

    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_launchctl",
        value=staticmethod(bad_launchctl),
    )
    source: Path = tmp_path / "s"
    source.mkdir()
    settings: core.WatchSettings = core.WatchSettings(
        source=source,
        destination=tmp_path / "d",
        interval=1,
        settle_time=0,
        exclude=(),
        include=(),
        initial_sync=False,
        mirror_deletes=False,
        quiet=False,
        run=True,
        project_root=None,
        pyproject=None,
    )
    with pytest.raises(expected_exception=RuntimeError, match="boot bad"):
        core.MacAutostart.install_package(settings=settings)


class _Parser:
    """Stand-in argument parser returning fixed ``CliArguments``."""

    def __init__(self, *, values: core.CliArguments) -> None:
        """Store the values ``parse_args`` reports.

        Args:
            values: Argument values copied into the namespace.

        """
        self._values: core.CliArguments = values

    def parse_args(self, *, namespace: core.CliArguments) -> core.CliArguments:
        """Copy the stored values into ``namespace``.

        Args:
            namespace: Namespace receiving the stored values.

        Returns:
            The populated namespace.

        """
        namespace.__dict__.update(self._values.__dict__)
        return namespace


def cli_values(**overrides: object) -> core.CliArguments:
    """Build ``CliArguments`` with every watch setting unset.

    Args:
        **overrides: Field values replacing the defaults.

    Returns:
        Populated CLI arguments namespace.

    """
    base: dict[str, object] = {
        "source": None,
        "destination": None,
        "pyproject": None,
        "interval": None,
        "settle_time": None,
        "exclude": None,
        "include": None,
        "initial_sync": None,
        "mirror_deletes": None,
        "quiet": None,
        "workers": None,
        "install_autostart": False,
        "uninstall_autostart": False,
        "autostart_status": False,
    }
    base.update(overrides)
    values: core.CliArguments = core.CliArguments()
    values.__dict__.update(base)
    return values


def test_cli_management_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dispatch the ``--autostart-status`` management operation.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="status",
        value=staticmethod(Constant(value={"installed": True})),
    )
    _ = require(value=core.FolderWatchCopyCli.parser())
    monkeypatch.setattr(
        target=core.FolderWatchCopyCli,
        name="parser",
        value=staticmethod(
            Constant(value=_Parser(values=cli_values(autostart_status=True))),
        ),
    )
    expect_equal(actual=core.FolderWatchCopyCli.run(), expected=0)


def test_run_loop_and_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run one sync iteration and exercise verbose output paths.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path)
    _ = (tmp_path / "source" / "a").write_text(data="x")
    calls: int = 0

    def stop(_seconds: float) -> None:
        """Interrupt the watch loop after the second sleep.

        Args:
            _seconds: Requested sleep duration, ignored.

        Raises:
            KeyboardInterrupt: Always after the first call.

        """
        nonlocal calls
        calls += 1
        if calls > 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(target=core, name="sleep", value=stop)
    watcher.run(initial_sync=True)
    expect_equal(actual=(tmp_path / "dest" / "a").read_text(), expected="x")
    verbose: core.FolderWatchCopy = core.FolderWatchCopy(
        source=tmp_path / "source",
        destination=tmp_path / "d2",
        interval=1,
        settle_time=0,
        exclusions=(),
        inclusions=(),
        mirror_deletes=False,
        verbose=True,
    )
    private_call(owner=verbose, name="_write", message="ok")
    private_call(
        owner=verbose,
        name="_write_error",
        relative=Path("x"),
        error=OSError("bad"),
    )


def test_autostart_legacy_install_and_success_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install the LaunchAgent through the legacy CLI entry point.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=core, name="platform", value="darwin")
    monkeypatch.setattr(
        target=Path,
        name="home",
        value=staticmethod(Constant(value=tmp_path)),
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_uid",
        value=staticmethod(Constant(value=2)),
    )

    def ok_launchctl(*, arguments: list[str]) -> CompletedProcess[str]:
        """Pretend launchctl bootstrap succeeds.

        Args:
            arguments: Arguments passed to launchctl.

        Returns:
            Successful completed process.

        """
        return CompletedProcess(
            args=arguments,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        target=core.MacAutostart,
        name="_launchctl",
        value=staticmethod(ok_launchctl),
    )
    source: Path = tmp_path / "s"
    source.mkdir()
    arguments: core.CliArguments = core.CliArguments(
        source=source,
        destination=tmp_path / "d",
        pyproject=None,
        interval=0.2,
        settle_time=0.3,
        exclude=["x"],
        include=None,
        initial_sync=True,
        mirror_deletes=True,
        quiet=True,
        workers=None,
        install_autostart=False,
        uninstall_autostart=False,
        autostart_status=False,
    )
    core.MacAutostart.install(
        script=tmp_path / "watch.py",
        arguments=arguments,
    )
    expect_true(condition=core.MacAutostart.plist_path().exists())


def test_copy_delete_error_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep copying and deleting when individual entries fail.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path)
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    dest.mkdir()
    _ = (source / "a").write_text(data="x")
    snap: dict[Path, core.EntryState] = snapshot_of(watcher=watcher)

    def denied(**kwargs: object) -> NoReturn:
        """Reject every copy attempt.

        Args:
            **kwargs: Arguments passed to ``copy2``, ignored.

        Raises:
            PermissionError: Always.

        """
        del kwargs
        msg: str = "denied"
        raise PermissionError(msg)

    monkeypatch.setattr(target=core, name="copy2", value=denied)
    private_call(
        owner=watcher,
        name="_copy_entry",
        relative=Path("a"),
        state=snap[Path("a")],
        source_snapshot=snap,
    )
    _ = (dest / "z").write_text(data="z")
    original_unlink: Callable[..., None] = Path.unlink

    def bad_unlink(self: Path, *, missing_ok: bool = False) -> None:
        """Fail unlinking only for the destination file ``z``.

        Args:
            self: Path being unlinked.
            missing_ok: Whether a missing file is tolerated.

        Raises:
            PermissionError: If the path is named ``z``.

        """
        if self.name == "z":
            msg: str = "denied"
            raise PermissionError(msg)
        original_unlink(self=self, missing_ok=missing_ok)

    monkeypatch.setattr(target=Path, name="unlink", value=bad_unlink)
    private_call(
        owner=watcher,
        name="_delete_destination",
        relative=Path("z"),
        source_snapshot=snap,
    )


def test_cli_all_dispatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch install, uninstall and watch operations from the CLI.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """

    def run_args(values: core.CliArguments) -> int:
        """Run the CLI with ``values`` as parsed arguments.

        Args:
            values: Arguments the patched parser returns.

        Returns:
            Process exit status.

        """
        monkeypatch.setattr(
            target=core.FolderWatchCopyCli,
            name="parser",
            value=staticmethod(Constant(value=_Parser(values=values))),
        )
        return core.FolderWatchCopyCli.run()

    expect_equal(
        actual=run_args(
            values=cli_values(
                install_autostart=True,
                uninstall_autostart=True,
            ),
        ),
        expected=2,
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="uninstall",
        value=staticmethod(Constant(value=True)),
    )
    expect_equal(
        actual=run_args(values=cli_values(uninstall_autostart=True)),
        expected=0,
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="uninstall",
        value=staticmethod(Constant(value=False)),
    )
    expect_equal(
        actual=run_args(values=cli_values(uninstall_autostart=True)),
        expected=0,
    )
    source: Path = tmp_path / "s"
    source.mkdir()
    settings: core.WatchSettings = core.WatchSettings(
        source=source,
        destination=tmp_path / "d",
        interval=0.1,
        settle_time=0,
        exclude=(),
        include=(),
        initial_sync=False,
        mirror_deletes=False,
        quiet=True,
        run=True,
        project_root=None,
        pyproject=None,
    )
    monkeypatch.setattr(
        target=core.FolderWatchCopyCli,
        name="_settings",
        value=staticmethod(Constant(value=settings)),
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="install_package",
        value=staticmethod(Constant(value=None)),
    )
    monkeypatch.setattr(
        target=core.MacAutostart,
        name="plist_path",
        value=staticmethod(Constant(value=tmp_path / "p")),
    )
    expect_equal(
        actual=run_args(values=cli_values(install_autostart=True)),
        expected=0,
    )
    monkeypatch.setattr(
        target=core.FolderWatchCopy,
        name="run",
        value=Constant(value=None),
    )
    expect_equal(actual=run_args(values=cli_values()), expected=0)


def test_supervisor_restarts_for_changed_watch_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stop the current watcher and create another after TOML changes.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    first_destination: Path = tmp_path / "first"
    second_destination: Path = tmp_path / "second"
    pyproject: Path = project / "pyproject.toml"

    def configuration(*, destination: Path, enabled: bool = True) -> str:
        """Render one watch table for the supervisor test.

        Args:
            destination: Configured copy target.
            enabled: Whether the worker should run.

        Returns:
            TOML document text.

        """
        return (
            f"[tool.watch]\nrun = {str(object=enabled).lower()}\nsource ="
            f' "."\ndestination = "{destination}"\ninterval = 0.01\n'
        )

    _ = pyproject.write_text(data=configuration(destination=first_destination))
    arguments: core.CliArguments = cli_values(pyproject=pyproject)
    settings: core.WatchSettings = private_result(
        owner=core.FolderWatchCopyCli,
        name="_settings",
        kind=core.WatchSettings,
        arguments=arguments,
    )
    destinations: list[Path] = []

    def repair_configuration(_seconds: float) -> None:
        """Finish the editor's temporary invalid TOML write.

        Args:
            _seconds: Requested sleep duration, ignored.

        """
        _ = pyproject.write_text(
            data=configuration(destination=second_destination),
        )

    class FakeWatcher:
        """Capture watcher replacements without polling the filesystem."""

        def __init__(self, **values: object) -> None:
            """Record the destination passed to the replacement worker."""
            destinations.append(
                require_type(value=values["destination"], kind=Path),
            )

        @staticmethod
        def run(
            *,
            initial_sync: bool,
            should_stop: Callable[[], bool] | None = None,
        ) -> bool:
            """Change configuration once, then simulate user shutdown.

            Returns:
                Whether the watcher should keep running.

            """
            del initial_sync
            if len(destinations) == 1:
                _ = pyproject.write_text(data="[tool.watch\n")
                expect_true(condition=require(value=should_stop)())
                return True
            return False

    monkeypatch.setattr(target=core, name="sleep", value=repair_configuration)
    monkeypatch.setattr(target=core, name="FolderWatchCopy", value=FakeWatcher)
    status: int = private_result(
        owner=core.FolderWatchCopyCli,
        name="_supervise",
        kind=int,
        arguments=arguments,
        initial_settings=settings,
    )
    expect_equal(actual=status, expected=0)
    expect_equal(
        actual=destinations,
        expected=[first_destination.resolve(), second_destination.resolve()],
    )


def test_run_false_pauses_until_pyproject_enables_watcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the supervisor alive while ``run`` is false, then start.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    pyproject: Path = project / "pyproject.toml"
    destination: Path = tmp_path / "destination"

    def write_config(*, enabled: bool) -> None:
        """Write the paused or enabled watch configuration.

        Args:
            enabled: Whether the written configuration enables the watcher.

        """
        _ = pyproject.write_text(
            data=(
                f"[tool.watch]\nrun = {str(object=enabled).lower()}\nsource ="
                f' "."\ndestination = "{destination}"\n'
            ),
        )

    write_config(enabled=False)
    arguments: core.CliArguments = cli_values(pyproject=pyproject)
    settings: core.WatchSettings = private_result(
        owner=core.FolderWatchCopyCli,
        name="_settings",
        kind=core.WatchSettings,
        arguments=arguments,
    )
    expect_false(condition=settings.run)
    sleep_calls: int = 0

    def enable_after_pause(_seconds: float) -> None:
        """Enable the watcher when its supervisor performs the first poll.

        Args:
            _seconds: Requested sleep duration, ignored.

        """
        nonlocal sleep_calls
        sleep_calls += 1
        write_config(enabled=True)

    workers: list[Path] = []

    class FakeWatcher:
        """Capture the worker created after the paused state ends."""

        def __init__(self, **values: object) -> None:
            """Record the destination of the enabled worker."""
            workers.append(
                require_type(value=values["destination"], kind=Path),
            )

        @staticmethod
        def run(
            *,
            initial_sync: bool,
            should_stop: Callable[[], bool] | None = None,
        ) -> bool:
            """Simulate a user stopping the newly enabled worker.

            Returns:
                Whether the watcher should keep running.

            """
            del initial_sync, should_stop
            return False

    monkeypatch.setattr(target=core, name="sleep", value=enable_after_pause)
    monkeypatch.setattr(target=core, name="FolderWatchCopy", value=FakeWatcher)
    status: int = private_result(
        owner=core.FolderWatchCopyCli,
        name="_supervise",
        kind=int,
        arguments=arguments,
        initial_settings=settings,
    )
    expect_equal(actual=status, expected=0)
    expect_equal(actual=sleep_calls, expected=1)
    expect_equal(actual=workers, expected=[destination.resolve()])


def test_more_path_and_metrics_branches(tmp_path: Path) -> None:
    """Cover remaining path resolution and metrics branches.

    Args:
        tmp_path: Pytest temporary directory.

    """
    watcher: core.FolderWatchCopy = make_watcher(tmp_path=tmp_path)
    source: Path = tmp_path / "source"
    dest: Path = tmp_path / "dest"
    dest.mkdir()
    nested: Path = source / "d"
    nested.mkdir()
    expect_none(value=core.PyprojectConfig.discover(start=nested))
    absolute: Path = resolve_path(
        cli=None,
        configured=str(object=tmp_path),
        project_root=None,
    )
    expect_equal(actual=absolute, expected=tmp_path)
    cli_path: Path = resolve_path(
        cli=Path(),
        configured=None,
        project_root=None,
    )
    expect_true(condition=cli_path.is_absolute())
    (dest / "l").symlink_to(target="missing")
    (dest / "d").mkdir()
    _ = (dest / "d" / "f").write_text(data="12")
    metrics: core.TreeMetrics = private_result(
        owner=watcher,
        name="_destination_metrics",
        kind=core.TreeMetrics,
    )
    expect_equal(actual=metrics.symlinks, expected=1)
    expect_equal(actual=metrics.directories, expected=1)
    expect_equal(actual=metrics.files, expected=1)
    link_size: int = private_result(
        owner=watcher,
        name="_entry_size",
        kind=int,
        path=dest / "l",
    )
    expect_true(condition=link_size > 0)
    (dest / "thing").mkdir()
    private_call(
        owner=watcher,
        name="_replace_with_symlink",
        destination=dest / "thing",
        target="target",
    )
    expect_true(condition=(dest / "thing").is_symlink())
    expect_equal(actual=core.main.__name__, expected="main")
