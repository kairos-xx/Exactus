# Copyright (c) 2026 João Lopes.
"""Test the standalone transactional patch runtime directly.

The generated update-PYZ integration tests exercise the runtime as an
executable. This module complements them with direct tests of the reusable
runtime primitives for manifest validation, filesystem state inspection,
path safety, restoration, payload loading, highlighting, and diff rendering.
"""

from hashlib import sha256
from importlib import invalidate_caches
from json import dumps, loads
from pathlib import Path
from runpy import run_path
from stat import S_IMODE
from sys import modules, path
from typing import cast

import pytest

from exactus.packages.patcher.runtime import (
    EntryData,
    EntryState,
    ManifestData,
    OperationData,
    diff_blob,
    digest,
    expected,
    main,
    paint,
    remove,
    render_diff,
    restore,
    safe,
    state,
    syntax,
)


def _expect(*, condition: bool, message: str) -> None:
    """Validate a test postcondition without using a bare assertion.

    Args:
        condition: Condition that must evaluate to true.
        message: Failure message used when the condition is false.

    Raises:
        AssertionError: If ``condition`` evaluates to false.

    """
    if not condition:
        raise AssertionError(message)


def _file_entry(*, content: bytes, blob: str = "0") -> EntryData:
    """Create deterministic runtime manifest data for a regular file.

    Args:
        content: File bytes represented by the manifest entry.
        blob: Embedded payload blob identifier.

    Returns:
        Runtime entry mapping describing ``content``.

    """
    return {
        "kind": "file",
        "mode": 0o644,
        "sha256": sha256(data=content).hexdigest(),
        "link_target": "",
        "blob": blob,
    }


def _operation(
    *,
    path: str,
    before: EntryData | None,
    after: EntryData | None,
    move_from: str | None = None,
) -> OperationData:
    """Create one typed runtime operation mapping.

    Args:
        path: Destination project-relative path.
        before: Expected entry state before application.
        after: Required entry state after application.
        move_from: Optional source path for a move operation.

    Returns:
        Runtime operation mapping suitable for a manifest.

    """
    return {
        "path": path,
        "before": before,
        "after": after,
        "move_from": move_from,
    }


def test_safe_accepts_nested_path_and_rejects_unsafe_paths(
    tmp_path: Path,
) -> None:
    """Verify runtime path resolution remains inside the project root.

    Args:
        tmp_path: Temporary project root used for path-safety validation.

    """
    nested: Path = safe(root=tmp_path, relative="src/app.py")
    _expect(
        condition=nested == tmp_path / "src/app.py",
        message="Safe nested path resolved to an unexpected destination.",
    )
    unsafe: tuple[str, ...] = ("", "../escape", "/absolute")
    for relative in unsafe:
        with pytest.raises(
            expected_exception=ValueError,
            match="outside project root",
        ):
            safe(root=tmp_path, relative=relative)


def test_digest_state_and_expected_cover_file_directory_and_absence(
    tmp_path: Path,
) -> None:
    """Verify runtime state normalization for common filesystem entries.

    Args:
        tmp_path: Temporary directory containing inspected entries.

    """
    content: bytes = b"runtime-state\n"
    file_path: Path = tmp_path / "value.txt"
    file_path.write_bytes(data=content)
    directory: Path = tmp_path / "folder"
    directory.mkdir()
    missing: Path = tmp_path / "missing"
    raw: EntryData = _file_entry(content=content)
    _expect(
        condition=digest(path=file_path) == sha256(data=content).hexdigest(),
        message="Runtime digest did not match SHA-256.",
    )
    _expect(
        condition=state(path=file_path) == expected(raw=raw),
        message="File state did not match its manifest representation.",
    )
    directory_state: EntryState = state(path=directory)
    _expect(
        condition=directory_state is not None
        and directory_state[0] == "directory",
        message="Directory state was not classified as a directory.",
    )
    _expect(
        condition=state(path=missing) is None,
        message="Absent path unexpectedly produced runtime state.",
    )
    _expect(
        condition=expected(raw=None) is None,
        message="Absent manifest state did not normalize to None.",
    )


def test_state_and_restore_cover_symbolic_links(tmp_path: Path) -> None:
    """Verify symbolic-link state and transactional restoration.

    Args:
        tmp_path: Temporary directory containing link and backup entries.

    """
    target_file: Path = tmp_path / "target.txt"
    target_file.write_text(data="target\n", encoding="utf-8")
    link: Path = tmp_path / "link"
    link.symlink_to(target="target.txt")
    link_state: EntryState = state(path=link)
    _expect(
        condition=link_state is not None
        and link_state[0] == "symlink"
        and link_state[3] == "target.txt",
        message="Symbolic-link state was not captured correctly.",
    )
    backup: Path = tmp_path / "backup.txt"
    backup.write_text(data="before\n", encoding="utf-8")
    destination: Path = tmp_path / "destination.txt"
    destination.write_text(data="after\n", encoding="utf-8")
    restore(source=backup, target=destination)
    _expect(
        condition=destination.read_text(encoding="utf-8") == "before\n",
        message="Regular-file restoration did not replace the destination.",
    )
    remove(path=destination)
    _expect(
        condition=not destination.exists(),
        message="Runtime remove did not delete the restored file.",
    )


def test_restore_copies_directory_tree(tmp_path: Path) -> None:
    """Verify directory backups can be restored recursively.

    Args:
        tmp_path: Temporary directory containing backup and destination trees.

    """
    source: Path = tmp_path / "backup"
    source.mkdir()
    (source / "nested.txt").write_text(data="saved\n", encoding="utf-8")
    target: Path = tmp_path / "target"
    target.mkdir()
    (target / "stale.txt").write_text(data="stale\n", encoding="utf-8")
    restore(source=source, target=target)
    _expect(
        condition=(target / "nested.txt").read_text(encoding="utf-8")
        == "saved\n",
        message="Directory restoration omitted nested content.",
    )
    _expect(
        condition=not (target / "stale.txt").exists(),
        message="Directory restoration retained stale destination content.",
    )


def test_diff_blob_handles_absent_nonfile_and_file_payloads(
    tmp_path: Path,
) -> None:
    """Verify runtime diff payload loading follows manifest entry kinds.

    Args:
        tmp_path: Temporary traversable package containing payload blobs.

    """
    blobs: Path = tmp_path / "blobs"
    blobs.mkdir()
    content: bytes = b"payload\n"
    (blobs / "0").write_bytes(data=content)
    file_entry: EntryData = _file_entry(content=content)
    directory_entry: EntryData = {
        "kind": "directory",
        "mode": 0o755,
        "sha256": "",
        "link_target": "",
        "blob": "",
    }
    _expect(
        condition=diff_blob(package=tmp_path, raw=None) == b"",
        message="Absent diff entry unexpectedly produced payload bytes.",
    )
    _expect(
        condition=diff_blob(package=tmp_path, raw=directory_entry) == b"",
        message="Directory diff entry unexpectedly produced payload bytes.",
    )
    _expect(
        condition=diff_blob(package=tmp_path, raw=file_entry) == content,
        message="File diff entry did not load its embedded payload.",
    )


def test_paint_and_syntax_respect_color_controls() -> None:
    """Verify runtime ANSI decoration and lightweight syntax highlighting."""
    plain: str = paint(text="value", code="31", enabled=False)
    colored: str = paint(text="value", code="31", enabled=True)
    highlighted: str = syntax(
        text="value = 42",
        path="module.py",
        enabled=True,
        base="\033[32m",
    )
    unsupported: str = syntax(
        text="value = 42",
        path="module.txt",
        enabled=True,
        base="\033[32m",
    )
    _expect(
        condition=plain == "value",
        message="Disabled paint unexpectedly emitted ANSI decoration.",
    )
    _expect(
        condition=colored == "\033[31mvalue\033[0m",
        message="Enabled paint emitted unexpected ANSI decoration.",
    )
    _expect(
        condition="\033[33m42\033[0m" in highlighted,
        message="Python numeric token was not syntax highlighted.",
    )
    _expect(
        condition=unsupported == "value = 42",
        message="Unsupported suffix unexpectedly received highlighting.",
    )


def test_render_diff_covers_text_move_metadata_and_binary(
    tmp_path: Path,
) -> None:
    """Verify runtime rendering covers major embedded diff categories.

    Args:
        tmp_path: Temporary traversable package containing before/after blobs.

    """
    blobs: Path = tmp_path / "blobs"
    blobs.mkdir()
    old_text: bytes = b"value = 1\n"
    new_text: bytes = b"value = 2\n"
    binary: bytes = b"\x00\x01"
    payloads: tuple[tuple[str, bytes], ...] = (
        ("old", old_text),
        ("new", new_text),
        ("binary", binary),
    )
    for name, content in payloads:
        (blobs / name).write_bytes(data=content)
    old_entry: EntryData = _file_entry(content=old_text, blob="old")
    new_entry: EntryData = _file_entry(content=new_text, blob="new")
    binary_entry: EntryData = _file_entry(content=binary, blob="binary")
    directory_entry: EntryData = {
        "kind": "directory",
        "mode": 0o755,
        "sha256": "",
        "link_target": "",
        "blob": "",
    }
    operations: list[OperationData] = [
        _operation(path="src/app.py", before=old_entry, after=new_entry),
        _operation(
            path="renamed.py",
            before=old_entry,
            after=old_entry,
            move_from="old.py",
        ),
        _operation(path="folder", before=None, after=directory_entry),
        _operation(path="data.bin", before=None, after=binary_entry),
    ]
    manifest: ManifestData = {
        "project_root": str(object=tmp_path),
        "operations": operations,
    }
    rendered: str = render_diff(
        package=tmp_path,
        manifest=manifest,
        color=False,
        context=1,
    )
    expected_fragments: tuple[str, ...] = (
        "diff --git a/src/app.py b/src/app.py",
        "-value = 1",
        "+value = 2",
        "rename from old.py",
        "rename to renamed.py",
        "absent -> directory",
        "Binary files differ",
    )
    for fragment in expected_fragments:
        _expect(
            condition=fragment in rendered,
            message=f"Runtime diff omitted expected fragment: {fragment}",
        )


def test_runtime_manifest_accessors_reject_invalid_data(
    tmp_path: Path,
) -> None:
    """Verify malformed runtime manifest data fails through public behavior.

    Args:
        tmp_path: Temporary traversable package used for invalid diff data.

    """
    invalid: ManifestData = {
        "project_root": str(object=tmp_path),
        "operations": "invalid",
    }
    with pytest.raises(
        expected_exception=TypeError,
        match="Manifest operations must be a list",
    ):
        render_diff(package=tmp_path, manifest=invalid, color=False, context=3)


def _package(
    tmp_path: Path,
    *,
    manifest: ManifestData,
    blobs: tuple[tuple[str, bytes], ...] = (),
) -> Path:
    """Materialize a real ``patch_data`` package for resource loading.

    Args:
        tmp_path: Temporary directory that will hold the package.
        manifest: Manifest document serialized as ``manifest.json``.
        blobs: ``(name, bytes)`` payload files stored under ``blobs/``.

    Returns:
        Directory that must precede ``sys.path`` for ``files`` lookups.

    """
    package: Path = tmp_path / "patch_data"
    (package / "blobs").mkdir(parents=True)
    (package / "__init__.py").write_text(data="", encoding="utf-8")
    (package / "manifest.json").write_text(
        data=dumps(obj=manifest),
        encoding="utf-8",
    )
    for name, content in blobs:
        (package / "blobs" / name).write_bytes(data=content)
    return tmp_path


def _run_main(
    *,
    monkeypatch: pytest.MonkeyPatch,
    package_dir: Path,
    arguments: tuple[str, ...],
) -> int:
    """Execute the runtime ``main`` as a generated PYZ invocation.

    Args:
        monkeypatch: Pytest patching helper.
        package_dir: Directory containing the ``patch_data`` package.
        arguments: Runtime command-line flags.

    Returns:
        The runtime status code.

    """
    monkeypatch.delitem(dic=modules, name="patch_data", raising=False)
    monkeypatch.setattr(
        target="sys.path",
        name=[str(object=package_dir), *path],
    )
    invalidate_caches()
    monkeypatch.setattr(target="sys.argv", name=["patch.pyz", *arguments])
    return main()


def _directory_entry(*, directory: Path) -> EntryData:
    """Build a manifest entry matching a real directory state.

    Args:
        directory: Existing directory used to sample the entry mode.

    Returns:
        Manifest entry describing ``directory``.

    """
    return {
        "kind": "directory",
        "mode": S_IMODE(directory.stat().st_mode),
        "sha256": "",
        "link_target": "",
        "blob": "",
    }


def _symlink_entry(*, probe: Path, target: str) -> EntryData:
    """Build a manifest entry matching a real symbolic link state.

    Args:
        probe: Existing symbolic link used to sample the link mode.
        target: Link target text.

    Returns:
        Manifest entry describing a symbolic link to ``target``.

    """
    return {
        "kind": "symlink",
        "mode": S_IMODE(probe.lstat().st_mode),
        "sha256": sha256(data=target.encode(encoding="utf-8")).hexdigest(),
        "link_target": target,
        "blob": "",
    }


def _manifest_for(
    *,
    root: Path,
    operations: list[OperationData],
) -> ManifestData:
    """Assemble a minimal runtime manifest for a project root.

    Args:
        root: Destination project root recorded in the manifest.
        operations: Ordered patch operations.

    Returns:
        Manifest mapping consumable by the patch runtime.

    """
    return {
        "format": "project-delta-pyz",
        "project_root": str(object=root),
        "operations": operations,
    }


def test_main_lists_and_describes_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verify ``--info``, ``--json``, and ``--list`` inspection modes.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.
        capfd: File-descriptor capture for runtime output.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(
                    path="moved.txt",
                    before=None,
                    after=None,
                    move_from="origin.txt",
                ),
                _operation(path="added.txt", before=None, after=None),
                _operation(
                    path="gone.txt",
                    before=_file_entry(content=b"gone\n"),
                    after=None,
                ),
                _operation(
                    path="same.txt",
                    before=_file_entry(content=b"same\n"),
                    after=_file_entry(content=b"same\n"),
                ),
            ],
        ),
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--list",),
        )
        == 0,
        message="Runtime list inspection returned a nonzero status.",
    )
    listed: str = capfd.readouterr().out
    for fragment in (
        "MOVE   moved.txt <- origin.txt",
        "ADD    added.txt",
        "REMOVE gone.txt",
        "CHANGE same.txt",
    ):
        _expect(
            condition=fragment in listed,
            message=f"Runtime list omitted expected row: {fragment}",
        )
    for flag in ("--info", "--json"):
        _expect(
            condition=_run_main(
                monkeypatch=monkeypatch,
                package_dir=package_dir,
                arguments=(flag,),
            )
            == 0,
            message=f"Runtime {flag} inspection returned a nonzero status.",
        )
        _expect(
            condition="project-delta-pyz" in capfd.readouterr().out,
            message=f"Runtime {flag} omitted the manifest payload.",
        )


def test_main_diff_modes_render_and_validate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verify ``--diff`` renders content and rejects bad context values.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.
        capfd: File-descriptor capture for runtime output.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    old_text: bytes = b"keep\nold\nkeep\n"
    new_text: bytes = b"keep\nnew\nkeep\n"
    invalid_utf8: bytes = b"\xff\xfe\xff"
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(
                    path="src/app.py",
                    before=_file_entry(content=old_text, blob="old"),
                    after=_file_entry(content=new_text, blob="new"),
                ),
                _operation(
                    path="blob.dat",
                    before=None,
                    after=_file_entry(content=invalid_utf8, blob="binary"),
                ),
            ],
        ),
        blobs=(("old", old_text), ("new", new_text), ("binary", invalid_utf8)),
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--diff", "--no-color"),
        )
        == 0,
        message="Runtime diff inspection returned a nonzero status.",
    )
    rendered: str = capfd.readouterr().out
    for fragment in (
        "diff --git a/src/app.py b/src/app.py",
        "-old",
        "+new",
        " keep",
        "Binary files differ",
    ):
        _expect(
            condition=fragment in rendered,
            message=f"Runtime diff omitted expected fragment: {fragment}",
        )
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--diff",),
        )
        == 0,
        message="Runtime colored diff returned a nonzero status.",
    )
    _expect(
        condition="\x1b[" in capfd.readouterr().out,
        message="Runtime colored diff emitted no ANSI decoration.",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="--diff-context must be zero or greater",
    ):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--diff", "--diff-context", "-1"),
        )


def test_main_verify_and_conflict_policies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verify ``--verify``, ``--dry-run``, and conflict policy behavior.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.
        capfd: File-descriptor capture for runtime output.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    (root / "same.txt").write_text(data="same\n", encoding="utf-8")
    (root / "drift.txt").write_text(data="actual\n", encoding="utf-8")
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(
                    path="same.txt",
                    before=_file_entry(content=b"same\n"),
                    after=_file_entry(content=b"same\n", blob="same"),
                ),
                _operation(
                    path="drift.txt",
                    before=_file_entry(content=b"expected\n"),
                    after=_file_entry(content=b"target\n", blob="target"),
                ),
            ],
        ),
        blobs=(("same", b"same\n"), ("target", b"target\n")),
    )
    conflict_status: int = 2
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--verify", "--conflict", "skip"),
        )
        == conflict_status,
        message="Verify mode did not report the precondition conflict.",
    )
    _expect(
        condition="verified preconditions; conflicts=1"
        in capfd.readouterr().out,
        message="Verify mode omitted the conflict summary.",
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match=r"Precondition conflict: drift\.txt",
    ):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--verify",),
        )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--dry-run", "--conflict", "skip"),
        )
        == 0,
        message="Runtime dry-run returned a nonzero status.",
    )
    planned: str = capfd.readouterr().out
    _expect(
        condition="APPLY same.txt" in planned and "SKIP drift.txt" in planned,
        message="Dry-run did not mark apply and skip actions.",
    )
    _expect(
        condition=(root / "drift.txt").read_text(encoding="utf-8")
        == "actual\n",
        message="Dry-run unexpectedly mutated the destination file.",
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--conflict", "backup"),
        )
        == 0,
        message="Backup conflict application returned a nonzero status.",
    )
    _expect(
        condition="conflicts were backed up transactionally"
        in capfd.readouterr().out,
        message="Backup conflict policy emitted no notice.",
    )
    _expect(
        condition=(root / "drift.txt").read_text(encoding="utf-8")
        == "target\n",
        message="Backup conflict policy did not overwrite the file.",
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--conflict", "skip"),
        )
        == 0,
        message="Skip conflict application returned a nonzero status.",
    )
    result: dict[str, object] = loads(s=capfd.readouterr().out)
    _expect(
        condition=result.get("skipped") == ["drift.txt"]
        and (root / "drift.txt").read_text(encoding="utf-8") == "target\n",
        message="Skip conflict policy did not leave the file untouched.",
    )


def test_main_apply_commits_full_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Verify transactional application of every operation category.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.
        capfd: File-descriptor capture for the JSON result.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    (root / "keep.txt").write_text(data="old\n", encoding="utf-8")
    (root / "origin.txt").write_text(data="origin\n", encoding="utf-8")
    (root / "gone.txt").write_text(data="gone\n", encoding="utf-8")
    directory: Path = root / "replaced"
    directory.mkdir()
    probe: Path = tmp_path / "probe-link"
    probe.symlink_to(target="probe-target")
    new_file: bytes = b"new\n"
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(
                    path="keep.txt",
                    before=_file_entry(content=b"old\n"),
                    after=_file_entry(content=new_file, blob="new"),
                ),
                _operation(
                    path="moved.txt",
                    before=_file_entry(content=b"origin\n"),
                    after=_file_entry(content=b"moved\n", blob="moved"),
                    move_from="origin.txt",
                ),
                _operation(
                    path="gone.txt",
                    before=_file_entry(content=b"gone\n"),
                    after=None,
                ),
                _operation(
                    path="newdir",
                    before=None,
                    after=_directory_entry(directory=root),
                ),
                _operation(
                    path="newdir/added.py",
                    before=None,
                    after=_file_entry(content=b"added\n", blob="added"),
                ),
                _operation(
                    path="link",
                    before=None,
                    after=_symlink_entry(probe=probe, target="target.txt"),
                ),
                _operation(
                    path="replaced",
                    before=_directory_entry(directory=directory),
                    after=_file_entry(content=b"now-file\n", blob="replaced"),
                ),
            ],
        ),
        blobs=(
            ("new", new_file),
            ("moved", b"moved\n"),
            ("added", b"added\n"),
            ("replaced", b"now-file\n"),
        ),
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=(),
        )
        == 0,
        message="Runtime application returned a nonzero status.",
    )
    _expect(
        condition=(root / "keep.txt").read_text(encoding="utf-8") == "new\n",
        message="Changed file did not receive the staged payload.",
    )
    _expect(
        condition=not (root / "origin.txt").exists()
        and (root / "moved.txt").read_text(encoding="utf-8") == "moved\n",
        message="Move operation did not relocate the file.",
    )
    _expect(
        condition=not (root / "gone.txt").exists(),
        message="Remove operation left the destination file behind.",
    )
    _expect(
        condition=(root / "newdir" / "added.py").is_file()
        and (root / "link").is_symlink()
        and (root / "replaced").is_file(),
        message="Add operations did not materialize all entry kinds.",
    )
    result: dict[str, object] = loads(s=capfd.readouterr().out)
    _expect(
        condition=result.get("moved") == ["origin.txt->moved.txt"]
        and result.get("removed") == ["gone.txt"]
        and result.get("verified") is True,
        message="Result payload did not summarize the applied delta.",
    )


def test_main_rolls_back_failed_postcondition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify postcondition failure restores every touched destination.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    (root / "old.txt").write_text(data="orig\n", encoding="utf-8")
    (root / "victim.txt").write_text(data="victim\n", encoding="utf-8")
    link: Path = root / "lnk"
    link.symlink_to(target="victim.txt")
    probe: Path = tmp_path / "probe-link"
    probe.symlink_to(target="probe-target")
    broken_link: EntryData = {
        "kind": "symlink",
        "mode": S_IMODE(probe.lstat().st_mode),
        "sha256": "0" * 64,
        "link_target": "nowhere",
        "blob": "",
    }
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(
                    path="lnk",
                    before=_symlink_entry(probe=link, target="victim.txt"),
                    after=_file_entry(content=b"lnk-file\n", blob="lnk"),
                ),
                _operation(
                    path="old.txt",
                    before=_file_entry(content=b"orig\n"),
                    after=broken_link,
                ),
            ],
        ),
        blobs=(("lnk", b"lnk-file\n"),),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match=r"Postcondition failed: old\.txt",
    ):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--force",),
        )
    _expect(
        condition=(root / "old.txt").is_file()
        and (root / "old.txt").read_text(encoding="utf-8") == "orig\n",
        message="Rollback did not restore the modified file.",
    )
    _expect(
        condition=(root / "lnk").is_symlink()
        and (root / "lnk").readlink().as_posix() == "victim.txt",
        message="Rollback did not restore the symbolic link.",
    )


def test_main_rejects_corrupt_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify staged payload digests are enforced during application.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    bad_entry: EntryData = {
        "kind": "file",
        "mode": 0o644,
        "sha256": "0" * 64,
        "link_target": "",
        "blob": "payload",
    }
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(
            root=root,
            operations=[
                _operation(path="bad.txt", before=None, after=bad_entry),
            ],
        ),
        blobs=(("payload", b"payload\n"),),
    )
    with pytest.raises(
        expected_exception=RuntimeError,
        match=r"Corrupt payload: bad\.txt",
    ):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=(),
        )


def test_main_root_resolution_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify destination root resolution honors overrides and types.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(root=root, operations=[]),
    )
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--verify",),
        )
        == 0,
        message="Manifest-root verify returned a nonzero status.",
    )
    monkeypatch.chdir(path=tmp_path)
    _expect(
        condition=_run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--root", "project", "--verify"),
        )
        == 0,
        message="Relative root override returned a nonzero status.",
    )
    file_root: Path = tmp_path / "not-a-dir"
    file_root.write_text(data="x", encoding="utf-8")
    with pytest.raises(expected_exception=NotADirectoryError):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--root", str(object=file_root), "--verify"),
        )
    bad_manifest: Path = package_dir / "patch_data" / "manifest.json"
    bad_manifest.write_text(
        data=dumps(obj={"project_root": 3, "operations": []}),
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=TypeError,
        match="project_root must be a string",
    ):
        _ = _run_main(
            monkeypatch=monkeypatch,
            package_dir=package_dir,
            arguments=("--verify",),
        )


def test_main_rejects_malformed_manifest_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid manifest member types raise typed errors.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(root=root, operations=[]),
    )
    manifest_path: Path = package_dir / "patch_data" / "manifest.json"
    cases: tuple[tuple[OperationData, str], ...] = (
        (
            cast(
                typ="OperationData",
                val={
                    "path": 5,
                    "before": None,
                    "after": None,
                    "move_from": None,
                },
            ),
            "must be text or null",
        ),
        (
            {
                "path": "a.txt",
                "before": "bad",
                "after": None,
                "move_from": None,
            },
            "must be an entry object",
        ),
        (
            {
                "path": "a.txt",
                "before": {"kind": 5, "mode": 0o644},
                "after": None,
                "move_from": None,
            },
            "must be a string",
        ),
        (
            {
                "path": "a.txt",
                "before": {"kind": "file", "mode": "x"},
                "after": None,
                "move_from": None,
            },
            "mode must be an integer",
        ),
    )
    for operation, message in cases:
        manifest_path.write_text(
            data=dumps(obj=_manifest_for(root=root, operations=[operation])),
            encoding="utf-8",
        )
        with pytest.raises(expected_exception=TypeError, match=message):
            _ = _run_main(
                monkeypatch=monkeypatch,
                package_dir=package_dir,
                arguments=("--verify",),
            )


def test_module_guard_invokes_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the ``__main__`` guard runs the runtime entry point.

    Args:
        tmp_path: Temporary project and package directories.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    package_dir: Path = _package(
        tmp_path=tmp_path / "pkg",
        manifest=_manifest_for(root=root, operations=[]),
    )
    monkeypatch.delitem(dic=modules, name="patch_data", raising=False)
    monkeypatch.setattr(
        target="sys.path",
        name=[str(object=package_dir), *path],
    )
    invalidate_caches()
    monkeypatch.setattr(target="sys.argv", name=["patch.pyz", "--verify"])
    runtime_file: Path = Path(
        str(object=modules["exactus.packages.patcher.runtime"].__file__),
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        _ = run_path(path_name=str(object=runtime_file), run_name="__main__")
    _expect(
        condition=raised.value.code == 0,
        message="Module guard did not exit with the runtime status.",
    )


def test_safe_rejects_symlink_parent_escape(tmp_path: Path) -> None:
    """Verify resolution through an escaping symlink parent is refused.

    Args:
        tmp_path: Temporary project root containing the link.

    """
    outside: Path = tmp_path / "outside"
    outside.mkdir()
    root: Path = tmp_path / "root"
    root.mkdir()
    (root / "door").symlink_to(target=outside)
    with pytest.raises(
        expected_exception=ValueError,
        match="outside project root",
    ):
        safe(root=root, relative="door/x")
