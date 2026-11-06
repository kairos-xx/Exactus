# Copyright (c) 2026
"""Exercise source transaction conflict detection and recovery boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from exactus.packages.source_merger.live import merge_live_edit
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.source_transaction import (
    FileEdit,
    FileImage,
    SourceConflictError,
    SourceJournal,
    read_image,
    same_image,
)


def test_read_image_returns_none_for_missing_file(tmp_path: Path) -> None:
    """Absent sources read as ``None`` instead of failing.

    Args:
        tmp_path: Independent source tree.

    """
    image: FileImage | None = read_image(path=tmp_path / "missing.txt")
    expect_true(condition=image is None)


def test_read_image_rejects_symlink_sources(tmp_path: Path) -> None:
    """Symlinks are never followed when reading transaction sources.

    Args:
        tmp_path: Independent source tree.

    """
    target: Path = tmp_path / "real.txt"
    _ = target.write_text(data="real", encoding="utf-8")
    link_path: Path = tmp_path / "link.txt"
    link_path.symlink_to(target=target)
    with pytest.raises(
        expected_exception=SourceConflictError,
        match="not an owned replacement",
    ):
        _ = read_image(path=link_path)


def test_read_image_rejects_non_regular_files(tmp_path: Path) -> None:
    """Directories are not readable transaction sources.

    Args:
        tmp_path: Independent source tree.

    """
    with pytest.raises(
        expected_exception=SourceConflictError,
        match="not a regular file",
    ):
        _ = read_image(path=tmp_path)


def test_read_image_captures_bytes_and_mode(tmp_path: Path) -> None:
    """Stable regular files produce a restorable image.

    Args:
        tmp_path: Independent source tree.

    """
    target: Path = tmp_path / "stable.py"
    _ = target.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    image: FileImage | None = read_image(path=target)
    expect_true(condition=image is not None)
    if image is not None:
        expect_equal(actual=image.data, expected=b"value = 1\n")


def test_same_image_matches_only_identical_states(tmp_path: Path) -> None:
    """Absent and present images compare only by recorded identity.

    Args:
        tmp_path: Independent source tree.

    """
    expect_true(condition=same_image(left=None, right=None))
    target: Path = tmp_path / "stable.py"
    _ = target.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    image: FileImage | None = read_image(path=target)
    expect_false(condition=same_image(left=image, right=None))
    expect_false(condition=same_image(left=None, right=image))
    expect_true(condition=same_image(left=image, right=image))


def test_commit_rejects_overlapping_proposals(tmp_path: Path) -> None:
    """Two edits against one source are never partially applied.

    Args:
        tmp_path: Independent source tree.

    """
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        edits: tuple[FileEdit, ...] = (
            FileEdit(relative=Path("same.py"), before=None, after=None),
            FileEdit(relative=Path("same.py"), before=None, after=None),
        )
        with pytest.raises(
            expected_exception=SourceConflictError,
            match="Overlapping whole-file",
        ):
            journal.commit(edits=edits)
    finally:
        journal.release()


def test_commit_keeps_current_when_only_the_user_changed(
    tmp_path: Path,
) -> None:
    """``C != A`` with ``B == A`` leaves the user's file untouched.

    Args:
        tmp_path: Independent source tree.

    """
    target: Path = tmp_path / "stale.py"
    _ = target.write_text(
        data="""\
external = True
""",
        encoding="utf-8",
    )
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        journal.commit(
            edits=(
                FileEdit(
                    relative=Path("stale.py"),
                    before=None,
                    after=None,
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=target.read_text(encoding="utf-8"),
        expected="""\
external = True
""",
    )


def test_commit_applies_b_and_preserves_all_three_forks(
    tmp_path: Path,
) -> None:
    """``C != A`` with ``B != A`` writes ``B`` and saves A/B/C.

    Args:
        tmp_path: Independent source tree.

    """
    target: Path = tmp_path / "forked.py"
    _ = target.write_text(
        data="""\
user = 'C'
""",
        encoding="utf-8",
    )
    before: FileImage = FileImage(
        data=b"orig = 'A'\n",
        mode=0o644,
        atime_ns=0,
        mtime_ns=0,
    )
    after: FileImage = FileImage(
        data=b"fixed = 'B'\n",
        mode=0o644,
        atime_ns=0,
        mtime_ns=0,
    )
    directory: Path = tmp_path / ".journal"
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=directory,
    )
    journal.acquire()
    try:
        journal.commit(
            edits=(
                FileEdit(
                    relative=Path("forked.py"),
                    before=before,
                    after=after,
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=target.read_text(encoding="utf-8"),
        expected="""\
fixed = 'B'
""",
    )
    conflict_root: Path = next(directory.glob(pattern="conflicts/*/"))
    expect_equal(
        actual=(conflict_root / "forked.py.original").read_bytes(),
        expected=b"orig = 'A'\n",
    )
    expect_equal(
        actual=(conflict_root / "forked.py.proposed").read_bytes(),
        expected=b"fixed = 'B'\n",
    )
    expect_equal(
        actual=(conflict_root / "forked.py.current").read_bytes(),
        expected=b"user = 'C'\n",
    )


def test_commit_merges_independent_user_edit_without_forks(
    tmp_path: Path,
) -> None:
    """Independent user and tool edits merge and leave no conflict forks.

    Args:
        tmp_path: Independent source tree.

    """
    original: bytes = b"def a():\n    return 1\n\n\ndef b():\n    return 2\n"
    refactored: bytes = (
        b"def a() -> int:\n    return 1\n\n\ndef b():\n    return 2\n"
    )
    edited: bytes = b"def a():\n    return 1\n\n\ndef b():\n    return 3\n"
    target: Path = tmp_path / "merged.py"
    _ = target.write_bytes(data=edited)
    directory: Path = tmp_path / ".journal"
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=directory,
        merger=merge_live_edit,
    )
    journal.acquire()
    try:
        dirty: tuple[Path, ...] = journal.commit(
            edits=(
                FileEdit(
                    relative=Path("merged.py"),
                    before=FileImage(
                        data=original,
                        mode=0o644,
                        atime_ns=0,
                        mtime_ns=0,
                    ),
                    after=FileImage(
                        data=refactored,
                        mode=0o644,
                        atime_ns=0,
                        mtime_ns=0,
                    ),
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=target.read_bytes(),
        expected=(
            b"def a() -> int:\n    return 1\n\n\ndef b():\n    return 3\n"
        ),
    )
    expect_equal(actual=dirty, expected=())
    expect_equal(
        actual=sorted(directory.glob(pattern="conflicts/*")),
        expected=[],
    )


def test_commit_token_merge_keeps_user_edit_and_flags_review(
    tmp_path: Path,
) -> None:
    """A heuristic token merge keeps the edit but preserves the forks.

    Duplicate selectors make the structural merge ambiguous, so the
    token-level fallback reconciles the edit and the file stays flagged.

    Args:
        tmp_path: Independent source tree.

    """
    original: bytes = (
        b".x {\n  color: red;\n}\n.x {\n  color: blue;\n}\n"
        b".y {\n  margin: 0px;\n}\n.z {\n  top: 1px;\n}\n"
    )
    refactored: bytes = original.replace(b"0px", b"0")
    edited: bytes = original.replace(b"top: 1px", b"top: 9px")
    target: Path = tmp_path / "heuristic.css"
    _ = target.write_bytes(data=edited)
    directory: Path = tmp_path / ".journal"
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=directory,
        merger=merge_live_edit,
    )
    journal.acquire()
    try:
        dirty: tuple[Path, ...] = journal.commit(
            edits=(
                FileEdit(
                    relative=Path("heuristic.css"),
                    before=FileImage(
                        data=original,
                        mode=0o644,
                        atime_ns=0,
                        mtime_ns=0,
                    ),
                    after=FileImage(
                        data=refactored,
                        mode=0o644,
                        atime_ns=0,
                        mtime_ns=0,
                    ),
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=target.read_bytes(),
        expected=refactored.replace(b"top: 1px", b"top: 9px"),
    )
    expect_equal(actual=dirty, expected=(Path("heuristic.css"),))
    conflict_root: Path = next(directory.glob(pattern="conflicts/*/"))
    expect_equal(
        actual=(conflict_root / "heuristic.css.current").read_bytes(),
        expected=edited,
    )


def test_commit_rejects_escaping_destinations(tmp_path: Path) -> None:
    """Proposals may never resolve outside the owned source root.

    Args:
        tmp_path: Independent source tree.

    """
    journal: SourceJournal = SourceJournal(
        root=tmp_path / "src",
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        edits: tuple[FileEdit, ...] = (
            FileEdit(relative=Path("../escape.py"), before=None, after=None),
        )
        with pytest.raises(
            expected_exception=SourceConflictError,
            match="Invalid transaction destination",
        ):
            journal.commit(edits=edits)
    finally:
        journal.release()


def test_acquire_rejects_concurrent_journal_owners(tmp_path: Path) -> None:
    """A second journal for the same project fails without waiting.

    Args:
        tmp_path: Independent source tree.

    """
    first: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    first.acquire()
    second: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    try:
        with pytest.raises(
            expected_exception=SourceConflictError,
            match="Another lint transaction",
        ):
            second.acquire()
    finally:
        first.release()


def test_commit_replaces_and_removes_owned_sources(tmp_path: Path) -> None:
    """Matching proposals publish, modify, and delete atomically.

    Args:
        tmp_path: Independent source tree.

    """
    existing: Path = tmp_path / "mod.py"
    _ = existing.write_text(
        data="""\
old = 1
""",
        encoding="utf-8",
    )
    removable: Path = tmp_path / "del.py"
    _ = removable.write_text(
        data="""\
gone = 1
""",
        encoding="utf-8",
    )
    before: FileImage | None = read_image(path=existing)
    before_removed: FileImage | None = read_image(path=removable)
    after: FileImage = FileImage(
        data=b"new = 2\n",
        mode=0o644,
        atime_ns=0,
        mtime_ns=0,
    )
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        journal.commit(
            edits=(
                FileEdit(
                    relative=Path("del.py"),
                    before=before_removed,
                    after=None,
                ),
                FileEdit(
                    relative=Path("mod.py"),
                    before=before,
                    after=after,
                ),
                FileEdit(
                    relative=Path("new.py"),
                    before=None,
                    after=after,
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=existing.read_text(encoding="utf-8"),
        expected="""\
new = 2
""",
    )
    expect_false(condition=removable.exists())
    expect_equal(
        actual=(tmp_path / "new.py").read_text(encoding="utf-8"),
        expected="""\
new = 2
""",
    )


def test_commit_ignores_timestamp_only_drift(tmp_path: Path) -> None:
    """A touched-but-identical file must accept ``B`` like ``C == A``.

    Args:
        tmp_path: Independent source tree.

    """
    target: Path = tmp_path / "touched.py"
    _ = target.write_text(
        data="""\
orig = 'A'
""",
        encoding="utf-8",
    )
    before: FileImage = FileImage(
        data=b"orig = 'A'\n",
        mode=0o644,
        atime_ns=1,
        mtime_ns=1,
    )
    after: FileImage = FileImage(
        data=b"fixed = 'B'\n",
        mode=0o644,
        atime_ns=0,
        mtime_ns=0,
    )
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        journal.commit(
            edits=(
                FileEdit(
                    relative=Path("touched.py"),
                    before=before,
                    after=after,
                ),
            ),
        )
    finally:
        journal.release()
    expect_equal(
        actual=target.read_text(encoding="utf-8"),
        expected="""\
fixed = 'B'
""",
    )
    expect_equal(
        actual=sorted((tmp_path / ".journal").glob(pattern="conflicts/*")),
        expected=[],
    )
