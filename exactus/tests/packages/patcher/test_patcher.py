"""Test the deterministic executable project patcher.

The suite exercises project-source normalization, directory and ZIP inputs,
generated PYZ semantics, deterministic archive generation, reversible
patches, move detection, delta composition, source filtering, symbolic
links, path-safety validation, manifest validation, CLI parsing, binary
generation, generated-binary execution, runtime root resolution, and
read-only patch inspection.

Tests intentionally avoid bare ``assert`` statements so the complete Ruff
security rule set can remain enabled without per-file ignores or suppression
comments. Explicit validation uses the local ``_expect`` helper, while
expected exception paths use ``pytest.raises`` with constrained message
matching.
"""

from json import dumps
from pathlib import Path, PurePosixPath
from runpy import run_module
from shutil import copytree, make_archive
from subprocess import CompletedProcess, run
from sys import executable, modules
from typing import TYPE_CHECKING
from zipfile import ZipFile, ZipInfo

import pytest

from exactus.packages import project_python
from exactus.packages.patcher import (
    PatcherCli,
    PyzProjectPatch,
    resolve_invocation_root,
)
from exactus.packages.patcher.core import (
    EntryKind,
    ProjectSnapshot,
    ProjectSource,
    SnapshotEntry,
    safe_relative,
)
from exactus.packages.patcher.examples import run as example_run

if TYPE_CHECKING:
    from argparse import Namespace


def _expect(*, condition: bool, message: str) -> None:
    """Validate a condition and fail the current test when it is false.

    This helper replaces bare ``assert`` statements so the test suite can
    comply with Ruff's S101 rule without suppressions while retaining
    explicit and readable assertion failures.

    Args:
        condition: Boolean condition that must evaluate to ``True`` for the
            test to continue successfully.
        message: Human-readable failure message included in the raised
            exception when ``condition`` evaluates to ``False``.

    Raises:
        AssertionError: If ``condition`` evaluates to ``False``.

    """
    if not condition:
        raise AssertionError(message)


def _project(*, root: Path, version: str, obsolete: bool = False) -> None:
    """Create a deterministic filesystem project used by patcher tests.

    The generated project contains a ``src`` directory and an ``app.py``
    module whose version value is controlled by ``version``. An optional
    obsolete file can also be created to exercise removal operations.

    Args:
        root: Root directory in which the deterministic project structure
            is created.
        version: Version value written to ``src/app.py`` using its Python
            string representation.
        obsolete: Whether to create ``obsolete.txt`` for tests that exercise
            file removal or restoration.

    """
    (root / "src").mkdir(parents=True)
    (root / "src/app.py").write_text(
        data=f"VERSION = {version!r}\n",
        encoding="utf-8",
    )
    if obsolete:
        (root / "obsolete.txt").write_text(data="old\n", encoding="utf-8")


def test_resolve_relative_root_from_invocation_directory(
    tmp_path: Path,
) -> None:
    """Verify relative roots are resolved from the invocation directory.

    This ensures that ``--root .`` refers to the working directory from
    which a generated PYZ is invoked rather than the directory containing
    the PYZ itself.

    Args:
        tmp_path: Temporary pytest directory used as the simulated project
            and invocation filesystem.

    """
    invocation: Path = tmp_path / "project"
    invocation.mkdir()
    resolved: Path = resolve_invocation_root(root=".", cwd=invocation)
    _expect(
        condition=resolved == invocation.resolve(),
        message="Dot did not resolve against the invocation directory.",
    )


def test_folder_delta_and_relative_runtime_root(tmp_path: Path) -> None:
    """Verify a folder delta honors the runtime relative-root override.

    The test builds a delta between two directory snapshots, stores the
    generated PYZ outside the target project, invokes it from the target
    directory with ``--root .``, and verifies additions, modifications, and
    removals are applied to that invocation directory.

    Args:
        tmp_path: Temporary pytest directory containing the before, after,
            target, and generated-patch directories.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    downloads: Path = tmp_path / "downloads"
    paths: tuple[Path, ...] = (before, after, target, downloads)
    for path in paths:
        path.mkdir()
    _project(root=before, version="1", obsolete=True)
    _project(root=after, version="2")
    (after / "new.txt").write_text(data="new\n", encoding="utf-8")
    copytree(src=before, dst=target, dirs_exist_ok=True)
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=before,
    )
    output: Path = downloads / "update.pyz"
    patch.build(output=output)
    result: CompletedProcess[str] = run(
        args=(executable, str(object=output), "--root", "."),
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
    )
    app_content: str = (target / "src/app.py").read_text(encoding="utf-8")
    new_content: str = (target / "new.txt").read_text(encoding="utf-8")
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition=app_content == "VERSION = '2'\n",
        message="Application content was not updated.",
    )
    _expect(
        condition=new_content == "new\n",
        message="New file content was not applied.",
    )
    _expect(
        condition=not (target / "obsolete.txt").exists(),
        message="Obsolete file was not removed.",
    )


def test_zip_as_b_source(tmp_path: Path) -> None:
    """Verify an ordinary ZIP archive can provide the after-state source.

    The test creates a before directory and an after directory, archives the
    latter as a normal ZIP file, generates a delta against that ZIP, applies
    the resulting executable patch, and verifies the target content.

    Args:
        tmp_path: Temporary pytest directory used for source projects,
            archive generation, target state, and generated patch output.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    paths: tuple[Path, ...] = (before, after, target)
    for path in paths:
        path.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    copytree(src=before, dst=target, dirs_exist_ok=True)
    archive: Path = Path(
        make_archive(
            base_name=str(object=tmp_path / "after-archive"),
            format="zip",
            root_dir=after,
        ),
    )
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=archive,
        project_root=target,
    )
    output: Path = tmp_path / "update.pyz"
    patch.build(output=output)
    result: CompletedProcess[str] = run(
        args=(executable, str(object=output)),
        check=False,
        capture_output=True,
        text=True,
    )
    content: str = (target / "src/app.py").read_text(encoding="utf-8")
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition=content == "VERSION = '2'\n",
        message="ZIP-backed patch did not update the application.",
    )


def test_inverse_restores_before_state(tmp_path: Path) -> None:
    """Verify an inverse patch completely restores the original state.

    A reversible forward patch is generated and applied first. Its inverse
    is then generated and applied to the modified target. The final target
    is checked for both restored file content and restored removed files.

    Args:
        tmp_path: Temporary pytest directory containing the before, after,
            target, forward-patch, and reverse-patch artifacts.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    paths: tuple[Path, ...] = (before, after, target)
    for path in paths:
        path.mkdir()
    _project(root=before, version="1", obsolete=True)
    _project(root=after, version="2")
    copytree(src=before, dst=target, dirs_exist_ok=True)
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=target,
    )
    forward: Path = tmp_path / "forward.pyz"
    reverse: Path = tmp_path / "reverse.pyz"
    patch.build(output=forward)
    patch.inverse().build(output=reverse)
    forward_result: CompletedProcess[bytes] = run(
        args=(executable, str(object=forward)),
        check=False,
    )
    reverse_result: CompletedProcess[bytes] = run(
        args=(executable, str(object=reverse)),
        check=False,
    )
    restored: str = (target / "src/app.py").read_text(encoding="utf-8")
    _expect(
        condition=forward_result.returncode == 0,
        message="Forward patch failed.",
    )
    _expect(
        condition=reverse_result.returncode == 0,
        message="Reverse patch failed.",
    )
    _expect(
        condition=restored == "VERSION = '1'\n",
        message="Inverse patch did not restore application content.",
    )
    _expect(
        condition=(target / "obsolete.txt").is_file(),
        message="Inverse patch did not restore the obsolete file.",
    )


def test_deterministic_build(tmp_path: Path) -> None:
    """Verify identical patch inputs produce byte-identical PYZ artifacts.

    The same patch model is built twice into different output paths. The
    resulting bytes are compared directly to validate deterministic archive
    generation.

    Args:
        tmp_path: Temporary pytest directory containing the source projects
            and both generated PYZ artifacts.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=before,
    )
    first: Path = tmp_path / "first.pyz"
    second: Path = tmp_path / "second.pyz"
    patch.build(output=first)
    patch.build(output=second)
    _expect(
        condition=first.read_bytes() == second.read_bytes(),
        message="Identical inputs did not produce identical PYZ files.",
    )


@pytest.mark.parametrize("argument", [".", "./", "sub/.."])
def test_relative_root_variants(tmp_path: Path, argument: str) -> None:
    """Verify equivalent relative-root forms resolve to the same directory.

    Args:
        tmp_path: Temporary pytest directory used as the explicit invocation
            working directory.
        argument: Relative path representation expected to normalize to the
            supplied invocation directory.

    """
    resolved: Path = resolve_invocation_root(root=argument, cwd=tmp_path)
    _expect(
        condition=resolved == tmp_path.resolve(),
        message=f"Relative root {argument!r} resolved incorrectly.",
    )


def test_source_filter_symlink_empty_directory_and_unsupported(
    tmp_path: Path,
) -> None:
    """Verify source filtering and filesystem-entry classification.

    The test constructs files, an empty directory, and a symbolic link. It
    validates exclusion and inclusion patterns, verifies entry kinds, and
    confirms unsupported standalone source files are rejected.

    Args:
        tmp_path: Temporary pytest directory used to construct the source
            tree and unsupported source input.

    """
    root: Path = tmp_path / "source"
    root.mkdir()
    (root / "empty").mkdir()
    (root / "keep.txt").write_text(data="keep", encoding="utf-8")
    (root / "drop.log").write_text(data="drop", encoding="utf-8")
    (root / "link").symlink_to(target="keep.txt")
    snapshot: ProjectSnapshot = ProjectSource.from_path(
        path=root,
        excludes=("*.log",),
    )
    by_path: dict[PurePosixPath, SnapshotEntry] = snapshot.by_path
    _expect(
        condition=(
            by_path[PurePosixPath("empty")].kind is EntryKind.DIRECTORY
        ),
        message="Empty directory was not represented as a directory.",
    )
    _expect(
        condition=(by_path[PurePosixPath("link")].kind is EntryKind.SYMLINK),
        message="Symlink was not represented as a symlink.",
    )
    _expect(
        condition=PurePosixPath("drop.log") not in by_path,
        message="Excluded file remained in the snapshot.",
    )
    included: ProjectSnapshot = ProjectSource.from_path(
        path=root,
        includes=("*.txt",),
    )
    included_paths: tuple[str, ...] = tuple(
        entry.path.as_posix() for entry in included.entries
    )
    _expect(
        condition=included_paths == ("keep.txt",),
        message="Include filtering returned unexpected entries.",
    )
    bad: Path = tmp_path / "source.txt"
    bad.write_text(data="x", encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match="Unsupported source",
    ):
        ProjectSource.from_path(path=bad)


def test_ordinary_zip_directory_file_and_symlink(tmp_path: Path) -> None:
    """Verify ZIP snapshots preserve supported filesystem entry kinds.

    A synthetic ZIP containing a directory, regular file, and Unix symbolic
    link is created. The resulting project snapshot must classify every
    entry using the corresponding ``EntryKind`` value.

    Args:
        tmp_path: Temporary pytest directory in which the synthetic ZIP
            archive is created.

    """
    archive_path: Path = tmp_path / "source.zip"
    with ZipFile(file=archive_path, mode="w") as archive:
        directory: ZipInfo = ZipInfo(filename="empty/")
        directory.external_attr = 0o40755 << 16
        archive.writestr(zinfo_or_arcname=directory, data=b"")
        archive.writestr(zinfo_or_arcname="file.txt", data=b"hello")
        link: ZipInfo = ZipInfo(filename="link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        archive.writestr(zinfo_or_arcname=link, data=b"file.txt")
    snapshot: ProjectSnapshot = ProjectSource.from_path(path=archive_path)
    kinds: dict[str, EntryKind] = {
        entry.path.as_posix(): entry.kind for entry in snapshot.entries
    }
    expected: dict[str, EntryKind] = {
        "empty": EntryKind.DIRECTORY,
        "file.txt": EntryKind.FILE,
        "link": EntryKind.SYMLINK,
    }
    _expect(
        condition=kinds == expected,
        message="ZIP entry kinds were decoded incorrectly.",
    )


def test_pyz_is_semantic_after_snapshot_and_nonreversible_build(
    tmp_path: Path,
) -> None:
    """Verify a generated PYZ exposes its semantic after-state snapshot.

    A forward-only patch is built with compression disabled for all payload
    sizes. Loading that PYZ through ``ProjectSource`` must produce the same
    snapshot fingerprint as loading the original after-state directory.

    Args:
        tmp_path: Temporary pytest directory containing the source projects
            and generated semantic patch artifact.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=before,
    )
    output: Path = tmp_path / "semantic.pyz"
    patch.build(output=output, reversible=False, compression_threshold=0)
    snapshot: ProjectSnapshot = ProjectSource.from_path(path=output)
    expected: ProjectSnapshot = ProjectSource.from_path(path=after)
    _expect(
        condition=snapshot.fingerprint == expected.fingerprint,
        message="Generated PYZ did not expose the expected after-state.",
    )


def test_move_detection_disable_and_composition(tmp_path: Path) -> None:
    """Verify move detection controls and compatible delta composition.

    Identical content moved between paths must be represented as a move when
    detection is enabled and as independent operations when disabled.
    Compatible sequential deltas are then composed and their boundary
    fingerprints validated. Reverse-order incompatible composition must be
    rejected.

    Args:
        tmp_path: Temporary pytest directory containing the three sequential
            project states used for move and composition tests.

    """
    a: Path = tmp_path / "a"
    b: Path = tmp_path / "b"
    c: Path = tmp_path / "c"
    paths: tuple[Path, ...] = (a, b, c)
    for path in paths:
        path.mkdir()
    (a / "old.txt").write_text(data="same", encoding="utf-8")
    (b / "new.txt").write_text(data="same", encoding="utf-8")
    (c / "new.txt").write_text(data="changed", encoding="utf-8")
    ab: PyzProjectPatch = PyzProjectPatch.delta(a=a, b=b, project_root=a)
    move_detected: bool = any(
        operation.move_from is not None
        for operation in ab.delta_model.operations
    )
    _expect(condition=move_detected, message="Expected move was not detected.")
    plain: PyzProjectPatch = PyzProjectPatch.delta(
        a=a,
        b=b,
        project_root=a,
        detect_moves=False,
    )
    moves_disabled: bool = all(
        operation.move_from is None
        for operation in plain.delta_model.operations
    )
    _expect(
        condition=moves_disabled,
        message="Move remained after move detection was disabled.",
    )
    bc: PyzProjectPatch = PyzProjectPatch.delta(a=b, b=c, project_root=a)
    ac: PyzProjectPatch = ab.compose(next_patch=bc)
    _expect(
        condition=(
            ac.delta_model.before_fingerprint
            == ab.delta_model.before_fingerprint
        ),
        message="Composed delta has the wrong before fingerprint.",
    )
    _expect(
        condition=(
            ac.delta_model.after_fingerprint
            == bc.delta_model.after_fingerprint
        ),
        message="Composed delta has the wrong after fingerprint.",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="Deltas are not composable",
    ):
        bc.delta_model.compose(next_delta=ab.delta_model)


def test_direct_constructor_removal_relative_and_outside_rejection(
    tmp_path: Path,
) -> None:
    """Verify direct removals and project-root path containment.

    The direct ``PyzProjectPatch`` constructor is used to request a file
    removal, and its delta model is inspected for the corresponding
    operation. A path outside the project root is then supplied to the
    relative-path helper and must be rejected.

    Args:
        tmp_path: Temporary pytest directory containing the project root and
            an intentionally out-of-root path.

    """
    root: Path = tmp_path / "root"
    root.mkdir()
    (root / "keep.txt").write_text(data="keep", encoding="utf-8")
    (root / "remove.txt").write_text(data="remove", encoding="utf-8")
    patch: PyzProjectPatch = PyzProjectPatch(
        project_root=root,
        files=("keep.txt",),
        remove=("remove.txt",),
    )
    removal_found: bool = any(
        operation.after is None for operation in patch.delta_model.operations
    )
    _expect(
        condition=removal_found,
        message="Direct constructor did not create a removal operation.",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="outside project root",
    ):
        PyzProjectPatch.relative(root=root, path=tmp_path / "outside.txt")


def test_safe_relative_rejects_unsafe_values() -> None:
    """Verify unsafe project-relative path representations are rejected.

    Empty paths, parent-directory traversal, and absolute paths must never
    pass normalization because accepting them could allow patch operations
    to escape their intended project root.
    """
    unsafe_values: tuple[str, ...] = ("", "../x", "/absolute")
    for value in unsafe_values:
        with pytest.raises(
            expected_exception=ValueError,
            match="Unsafe project-relative path",
        ):
            safe_relative(value=value)


def test_manifest_validation_errors_and_corrupt_blob(tmp_path: Path) -> None:
    """Verify malformed manifests and corrupt embedded blobs are rejected.

    The test independently constructs a manifest with a non-list snapshot,
    a manifest containing an invalid snapshot entry, and a manifest whose
    declared blob digest does not match its embedded payload. Each malformed
    artifact must fail with its corresponding validation error.

    Args:
        tmp_path: Temporary pytest directory in which malformed patch
            archives are constructed.

    """
    path: Path = tmp_path / "bad.pyz"
    invalid_snapshot: dict[str, str] = {
        "format": "project-delta-pyz",
        "after_snapshot": "bad",
    }
    with ZipFile(file=path, mode="w") as archive:
        archive.writestr(
            zinfo_or_arcname="patch_data/manifest.json",
            data=dumps(obj=invalid_snapshot),
        )
    with pytest.raises(
        expected_exception=TypeError,
        match="Invalid embedded snapshot",
    ):
        ProjectSource.from_path(path=path)
    invalid_entry: dict[str, str | list[str]] = {
        "format": "project-delta-pyz",
        "after_snapshot": ["bad-entry"],
    }
    with ZipFile(file=path, mode="w") as archive:
        archive.writestr(
            zinfo_or_arcname="patch_data/manifest.json",
            data=dumps(obj=invalid_entry),
        )
    with pytest.raises(
        expected_exception=TypeError,
        match="Invalid embedded snapshot entry",
    ):
        ProjectSource.from_path(path=path)
    corrupt_entry: dict[str, str | int] = {
        "path": "x",
        "kind": "file",
        "mode": 420,
        "sha256": "0",
        "blob": "0",
    }
    corrupt_manifest: dict[str, str | list[dict[str, str | int]]] = {
        "format": "project-delta-pyz",
        "after_snapshot": [corrupt_entry],
    }
    with ZipFile(file=path, mode="w") as archive:
        archive.writestr(
            zinfo_or_arcname="patch_data/manifest.json",
            data=dumps(obj=corrupt_manifest),
        )
        archive.writestr(zinfo_or_arcname="patch_data/blobs/0", data=b"wrong")
    with pytest.raises(
        expected_exception=ValueError,
        match="Corrupt embedded blob",
    ):
        ProjectSource.from_path(path=path)


def test_generated_pyz_inspection_commands(tmp_path: Path) -> None:
    """Verify generated PYZ inspection and validation commands execute.

    A real patch is generated and invoked separately with ``--info``,
    ``--json``, ``--list``, ``--dry-run``, and ``--verify``. Every command
    must complete successfully and emit user-visible output without relying
    on a mutation-only invocation.

    Args:
        tmp_path: Temporary pytest directory containing source projects and
            the generated update PYZ.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    output: Path = tmp_path / "update.pyz"
    patch: PyzProjectPatch = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=before,
    )
    patch.build(output=output)
    flags: tuple[str, ...] = (
        "--info",
        "--json",
        "--list",
        "--dry-run",
        "--verify",
    )
    for flag in flags:
        result: CompletedProcess[str] = run(
            args=(executable, str(object=output), flag),
            check=False,
            capture_output=True,
            text=True,
        )
        _expect(
            condition=result.returncode == 0,
            message=f"{flag} failed: {result.stderr}",
        )
        _expect(
            condition=bool(result.stdout),
            message=f"{flag} produced no output.",
        )


def test_builder_help_is_exhaustive() -> None:
    """Verify module help documents the complete supported CLI surface.

    The help output must describe source types, root semantics, binary
    generation, generated-update commands, the Python API, binary-directory
    selection, and forward-only patch construction.
    """
    result: CompletedProcess[str] = run(
        args=(executable, "-m", "exactus.packages.patcher", "--help"),
        check=False,
        capture_output=True,
        text=True,
    )
    _expect(condition=result.returncode == 0, message=result.stderr)
    phrases: tuple[str, ...] = (
        "SOURCE TYPES",
        "ROOT SEMANTICS",
        "BUILD THE PATCHER CLI BINARY",
        "GENERATED UPDATE PYZ COMMANDS",
        "PYTHON API",
        "--bin-dir",
        "--forward-only",
    )
    for phrase in phrases:
        _expect(
            condition=phrase in result.stdout,
            message=f"Help is missing {phrase!r}.",
        )


def test_bin_default_and_generated_cli(tmp_path: Path) -> None:
    """Verify default binary generation and generated CLI help.

    Invoking the package with bare ``--bin`` must create
    ``bin/patcher.pyz`` beneath the selected project root. The generated
    binary must itself execute successfully and expose the documented delta
    builder interface.

    Args:
        tmp_path: Temporary pytest directory used as the selected project
            root and generated binary destination.

    """
    result: CompletedProcess[str] = run(
        args=(
            executable,
            "-m",
            "exactus.packages.patcher",
            "--project-root",
            str(object=tmp_path),
            "--bin",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    binary: Path = tmp_path / "bin/patcher.pyz"
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition=binary.is_file(),
        message="Default patcher binary was not created.",
    )
    help_result: CompletedProcess[str] = run(
        args=(executable, str(object=binary), "-h"),
        check=False,
        capture_output=True,
        text=True,
    )
    _expect(condition=help_result.returncode == 0, message=help_result.stderr)
    _expect(
        condition="BUILD A DELTA" in help_result.stdout,
        message="Generated binary did not expose delta help.",
    )


def test_generated_patch_backs_up_overlapping_removals(tmp_path: Path) -> None:
    """Apply removals containing both ancestor and descendant directories.

    Args:
        tmp_path: Temporary source, target, and patch filesystem.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    nested: Path = before / "legacy" / "__pycache__"
    nested.mkdir(parents=True)
    (before / "legacy" / "module.py").write_text(
        data="VALUE = 1\n",
        encoding="utf-8",
    )
    (nested / "module.pyc").write_bytes(data=b"cache")
    after.mkdir()
    copytree(src=before, dst=target, dirs_exist_ok=True)
    update: Path = PyzProjectPatch.delta(
        a=before,
        b=after,
        project_root=target,
    ).build(output=tmp_path / "remove.pyz")
    result: CompletedProcess[str] = run(
        args=(executable, str(object=update)),
        check=False,
        capture_output=True,
        text=True,
    )
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition=not (target / "legacy").exists(),
        message="Overlapping directory removals were not applied.",
    )


def test_generated_binary_builds_delta(tmp_path: Path) -> None:
    """Verify a generated patcher binary can build and apply a real delta.

    A self-contained patcher PYZ is generated first and then used in a
    subprocess to construct an update from two directory snapshots. The
    resulting update is applied to a copied target and its final content is
    validated.

    Args:
        tmp_path: Temporary pytest directory containing source projects,
            target state, generated builder binary, and generated update.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    paths: tuple[Path, ...] = (before, after, target)
    for path in paths:
        path.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    copytree(src=before, dst=target, dirs_exist_ok=True)
    binary: Path = PatcherCli.build_binary(project_root=tmp_path)
    update: Path = tmp_path / "update.pyz"
    result: CompletedProcess[str] = run(
        args=(
            executable,
            str(object=binary),
            "--a",
            str(object=before),
            "--b",
            str(object=after),
            "--project-root",
            str(object=target),
            "--output",
            str(object=update),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    apply_result: CompletedProcess[bytes] = run(
        args=(executable, str(object=update)),
        check=False,
    )
    content: str = (target / "src/app.py").read_text(encoding="utf-8")
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition=apply_result.returncode == 0,
        message="Generated update failed to apply.",
    )
    _expect(
        condition=content == "VERSION = '2'\n",
        message="Generated binary produced an incorrect delta.",
    )


def test_bin_dir_is_relative_to_project_root(tmp_path: Path) -> None:
    """Verify relative binary directories resolve below the project root.

    A nested relative ``bin_dir`` is supplied through the Python API. The
    returned binary path and filesystem artifact must both resolve beneath
    the explicitly selected project root.

    Args:
        tmp_path: Temporary pytest directory used as the project root for
            binary-directory resolution.

    """
    binary: Path = PatcherCli.build_binary(
        project_root=tmp_path,
        bin_dir="tools/commands",
    )
    expected: Path = tmp_path / "tools/commands/patcher.pyz"
    _expect(
        condition=binary == expected,
        message="Binary directory resolved incorrectly.",
    )
    _expect(condition=binary.is_file(), message="Binary file was not created.")


def test_cli_api_run_builds_binary(tmp_path: Path) -> None:
    """Verify the callable CLI API supports binary-generation arguments.

    ``PatcherCli.run`` is invoked with the same arguments available through
    the command-line interface, including an explicit binary directory. The
    operation must succeed and create the expected executable archive.

    Args:
        tmp_path: Temporary pytest directory used as the project root and
            generated binary destination.

    """
    status: int = PatcherCli.run(
        arguments=(
            "--project-root",
            str(object=tmp_path),
            "--bin",
            "--bin-dir",
            "commands",
        ),
    )
    binary: Path = tmp_path / "commands/patcher.pyz"
    _expect(condition=status == 0, message="Callable CLI binary build failed.")
    _expect(
        condition=binary.is_file(),
        message="Callable CLI did not create the binary.",
    )


def test_cli_api_run_builds_delta(tmp_path: Path) -> None:
    """Verify the callable CLI API exposes complete delta construction.

    The test exercises source selection, project-root selection, output
    selection, include and exclude filters, disabled move detection,
    forward-only generation, and an explicit compression threshold through
    ``PatcherCli.run``.

    Args:
        tmp_path: Temporary pytest directory containing the before, after,
            target, and generated delta paths.

    """
    before: Path = tmp_path / "before"
    after: Path = tmp_path / "after"
    target: Path = tmp_path / "target"
    paths: tuple[Path, ...] = (before, after, target)
    for path in paths:
        path.mkdir()
    _project(root=before, version="1")
    _project(root=after, version="2")
    copytree(src=before, dst=target, dirs_exist_ok=True)
    output: Path = tmp_path / "cli-update.pyz"
    status: int = PatcherCli.run(
        arguments=(
            "--a",
            str(object=before),
            "--b",
            str(object=after),
            "--project-root",
            str(object=target),
            "--output",
            str(object=output),
            "--include",
            "*",
            "--exclude",
            "*.never",
            "--no-detect-moves",
            "--forward-only",
            "--compression-threshold",
            "0",
        ),
    )
    _expect(condition=status == 0, message="Callable CLI delta build failed.")
    _expect(
        condition=output.is_file(),
        message="Callable CLI did not create the delta.",
    )


def test_parser_defaults_and_switches() -> None:
    """Verify parser defaults and inverse command-line switches.

    Parsing an empty argument sequence must expose the documented defaults.
    Parsing move-detection, reversibility, and binary switches must produce
    their corresponding changed namespace values.
    """
    defaults: Namespace = PatcherCli.parser().parse_args(args=[])
    _expect(
        condition=defaults.project_root == ".",
        message="Unexpected default project root.",
    )
    _expect(
        condition=defaults.output == "update.pyz",
        message="Unexpected default output path.",
    )
    _expect(
        condition=defaults.bin_dir is None,
        message="Unexpected default binary directory.",
    )
    _expect(
        condition=defaults.bin is None,
        message="Binary mode unexpectedly enabled.",
    )
    _expect(
        condition=defaults.detect_moves is True,
        message="Move detection should default to enabled.",
    )
    _expect(
        condition=defaults.reversible is True,
        message="Reversibility should default to enabled.",
    )
    changed: Namespace = PatcherCli.parser().parse_args(
        args=("--no-detect-moves", "--forward-only", "--bin"),
    )
    _expect(
        condition=changed.detect_moves is False,
        message="Move detection switch was not applied.",
    )
    _expect(
        condition=changed.reversible is False,
        message="Forward-only switch was not applied.",
    )
    _expect(
        condition=changed.bin == "bin",
        message="Bare --bin did not select the default directory.",
    )


def test_bin_accepts_inline_directory(tmp_path: Path) -> None:
    """Verify ``--bin`` accepts its destination directory inline.

    The callable CLI is invoked using ``--bin tools`` rather than the
    separate ``--bin-dir`` option. The resulting patcher binary must be
    created beneath the requested directory.

    Args:
        tmp_path: Temporary pytest directory used as the selected project
            root and binary output base.

    """
    status: int = PatcherCli.run(
        arguments=("--project-root", str(object=tmp_path), "--bin", "tools"),
    )
    binary: Path = tmp_path / "tools/patcher.pyz"
    _expect(
        condition=status == 0,
        message="Inline binary directory build failed.",
    )
    _expect(
        condition=binary.is_file(),
        message="Inline binary directory was not honored.",
    )


def test_module_without_arguments_prints_help() -> None:
    """Verify module invocation without arguments prints exhaustive help.

    Running ``python -m exactus.packages.patcher`` without additional arguments
    must
    terminate successfully and expose both source-type and binary-builder
    documentation instead of silently performing an operation.
    """
    result: CompletedProcess[str] = run(
        args=(executable, "-m", "exactus.packages.patcher"),
        check=False,
        capture_output=True,
        text=True,
    )
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition="SOURCE TYPES" in result.stdout,
        message="No-argument help omitted source documentation.",
    )
    _expect(
        condition="BUILD THE PATCHER CLI BINARY" in result.stdout,
        message="No-argument help omitted binary documentation.",
    )


def test_generated_binary_without_arguments_prints_help(
    tmp_path: Path,
) -> None:
    """Verify a generated binary without arguments prints exhaustive help.

    A self-contained patcher binary is generated and invoked without CLI
    arguments. It must terminate successfully and expose the same principal
    help sections as the source package entry point.

    Args:
        tmp_path: Temporary pytest directory used as the project root and
            generated binary destination.

    """
    binary: Path = PatcherCli.build_binary(project_root=tmp_path)
    result: CompletedProcess[str] = run(
        args=(executable, str(object=binary)),
        check=False,
        capture_output=True,
        text=True,
    )
    _expect(condition=result.returncode == 0, message=result.stderr)
    _expect(
        condition="SOURCE TYPES" in result.stdout,
        message="Generated binary help omitted source documentation.",
    )
    _expect(
        condition="BUILD THE PATCHER CLI BINARY" in result.stdout,
        message="Generated binary help omitted binary documentation.",
    )


def test_inline_bin_and_bin_dir_conflict(tmp_path: Path) -> None:
    """Verify conflicting binary-directory declarations are rejected.

    Supplying both an inline ``--bin`` directory and ``--bin-dir`` creates
    an ambiguous destination. The CLI must reject that combination through
    its argument-parser error path.

    Args:
        tmp_path: Temporary pytest directory supplied as the project root for
            the intentionally invalid CLI invocation.

    """
    with pytest.raises(expected_exception=SystemExit, match="2"):
        PatcherCli.run(
            arguments=(
                "--project-root",
                str(object=tmp_path),
                "--bin",
                "tools",
                "--bin-dir",
                "other",
            ),
        )


def test_main_module_switches_to_project_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the patcher module switches interpreter before its CLI runs.

    Args:
        monkeypatch: Pytest patching helper used to observe the switch
            request and replace the process argument vector.

    """
    calls: list[str] = []
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: calls.append("switch"),
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["exactus.packages.patcher"],
    )
    with pytest.raises(expected_exception=SystemExit, match="0"):
        run_module(mod_name="exactus.packages.patcher", run_name="__main__")
    _expect(
        condition=calls == ["switch"],
        message="Patcher module did not request the project-venv switch.",
    )


def test_examples_module_switches_to_project_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the patcher example uses the same automatic interpreter switch.

    Args:
        monkeypatch: Pytest patching helper used to observe the switch
            request and replace the example entry point.

    """
    calls: list[str] = []
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: calls.append("switch"),
    )
    monkeypatch.setattr(target=example_run, name="main", value=lambda: 0)
    with pytest.raises(expected_exception=SystemExit, match="0"):
        run_module(
            mod_name="exactus.packages.patcher.examples",
            run_name="__main__",
        )
    _expect(
        condition=calls == ["switch"],
        message="Patcher example did not request the project-venv switch.",
    )
