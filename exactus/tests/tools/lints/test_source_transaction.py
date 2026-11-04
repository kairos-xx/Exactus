# Copyright (c) 2026
"""Exercise source transaction isolation, rollback, and stale proposals."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import expect_equal
from exactus.tools.common.source_transaction import (
    FileEdit,
    SourceConflictError,
    SourceJournal,
    read_image,
    same_image,
)
from exactus.tools.lints.core import (
    LintExactus,
    LintExactusConfig,
    LintExactusRequest,
)
from exactus.tools.lints.workspace import SourceWorkspace, TransactionLimits

if TYPE_CHECKING:
    from exactus.tools.common.source_transaction import FileImage
    from exactus.tools.lints.core import JsonValue


def test_workspace_preserves_original_and_metadata(tmp_path: Path) -> None:
    """Prospective mutation must not touch original bytes or permissions.

    Args:
        tmp_path: Independent project tree.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"\xef\xbb\xbfvalue = 1\r\n")
    source.chmod(mode=0o750)
    original: FileImage | None = read_image(path=source)
    with SourceWorkspace(
        root=tmp_path,
        ignores=(),
        limits=TransactionLimits(),
    ) as workspace:
        candidate: Path = workspace.path / source.name
        candidate.write_bytes(data=b"\xef\xbb\xbfvalue = 2\r\n")
        expect_equal(
            actual=source.read_bytes(),
            expected=b"\xef\xbb\xbfvalue = 1\r\n",
        )
        workspace.freeze()
        edits: tuple[FileEdit, ...] = workspace.proposals()
        expect_equal(actual=len(edits), expected=1)
        expect_equal(
            actual=same_image(left=edits[0].before, right=original),
            expected=True,
        )
        expect_equal(
            actual=edits[0].after.mode if edits[0].after else None,
            expected=0o750,
        )


def test_journal_rolls_back_report_failure(tmp_path: Path) -> None:
    """A report publishing failure must restore original exact bytes.

    Args:
        tmp_path: Independent project tree.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    before: FileImage | None = read_image(path=source)
    candidate: Path = tmp_path / "candidate.py"
    candidate.write_bytes(data=b"value = 2\n")
    after: FileImage | None = read_image(path=candidate)
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )

    def fail() -> None:
        """Inject a late report failure.

        Raises:
            RuntimeError: Always, to reject the report publication.

        """
        msg: str = "report failed"
        raise RuntimeError(msg)

    journal.acquire()
    try:
        with pytest.raises(
            expected_exception=RuntimeError,
            match="report failed",
        ):
            journal.commit(
                edits=(
                    FileEdit(
                        relative=Path("example.py"),
                        before=before,
                        after=after,
                    ),
                ),
                publish=fail,
            )
        expect_equal(actual=source.read_bytes(), expected=b"value = 1\n")
    finally:
        journal.release()


def test_stale_proposal_preserves_manual_edit(tmp_path: Path) -> None:
    """Changed originals must be preserved and rejected before commit.

    Args:
        tmp_path: Independent project tree.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    before: FileImage | None = read_image(path=source)
    source.write_bytes(data=b"manual = 3\n")
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        with pytest.raises(
            expected_exception=SourceConflictError,
            match="Stale",
        ):
            journal.commit(
                edits=(
                    FileEdit(
                        relative=Path("example.py"),
                        before=before,
                        after=before,
                    ),
                ),
            )
        expect_equal(actual=source.read_bytes(), expected=b"manual = 3\n")
    finally:
        journal.release()


def test_restart_recovers_interrupted_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopening the durable journal restores interrupted source claims.

    Args:
        tmp_path: Independent project tree.
        monkeypatch: Pytest patching helper.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    before: FileImage | None = read_image(path=source)
    replacement: Path = tmp_path / "replacement.py"
    replacement.write_bytes(data=b"value = 2\n")
    after: FileImage | None = read_image(path=replacement)
    directory: Path = tmp_path / ".journal"
    journal: SourceJournal = SourceJournal(root=tmp_path, directory=directory)

    def fail() -> None:
        """Interrupt after publication.

        Raises:
            KeyboardInterrupt: Always, to abandon the commit.

        """
        raise KeyboardInterrupt

    def interrupted_restore(*, run: Path | None) -> None:
        """Simulate interruption before rollback starts.

        Args:
            run: Journaled commit directory, unused.

        Raises:
            RuntimeError: Always, to simulate losing the process.

        """
        del run
        msg: str = "simulated process loss"
        raise RuntimeError(msg)

    journal.acquire()
    try:
        with monkeypatch.context() as patch:
            scoped: pytest.MonkeyPatch = patch
            scoped.setattr(
                target=journal,
                name="_restore",
                value=interrupted_restore,
            )
            with pytest.raises(expected_exception=KeyboardInterrupt):
                journal.commit(
                    edits=(
                        FileEdit(
                            relative=Path("example.py"),
                            before=before,
                            after=after,
                        ),
                    ),
                    publish=fail,
                )
        expect_equal(actual=source.read_bytes(), expected=b"value = 2\n")
    finally:
        journal.release()
    restarted: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=directory,
    )
    restarted.acquire()
    try:
        expect_equal(actual=source.read_bytes(), expected=b"value = 1\n")
        expect_equal(actual=list(directory.glob(pattern="run-*")), expected=[])
    finally:
        restarted.release()


def test_late_manual_edit_survives_rollback(tmp_path: Path) -> None:
    """Rollback retains the journal instead of overwriting a manual edit.

    Args:
        tmp_path: Independent project tree.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    before: FileImage | None = read_image(path=source)
    replacement: Path = tmp_path / "replacement.py"
    replacement.write_bytes(data=b"value = 2\n")
    after: FileImage | None = read_image(path=replacement)
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )

    def fail() -> None:
        """Simulate a manual save concurrent with a failed publication.

        Raises:
            RuntimeError: Always, after the conflicting edit lands.

        """
        source.write_bytes(data=b"manual = 3\n")
        msg: str = "report failed"
        raise RuntimeError(msg)

    journal.acquire()
    try:
        with pytest.raises(
            expected_exception=RuntimeError,
            match="report failed",
        ):
            journal.commit(
                edits=(
                    FileEdit(
                        relative=Path("example.py"),
                        before=before,
                        after=after,
                    ),
                ),
                publish=fail,
            )
        expect_equal(actual=source.read_bytes(), expected=b"manual = 3\n")
    finally:
        journal.release()


@pytest.mark.parametrize("kind", ["overlap", "syntax"])
def test_invalid_proposals_fail_before_mutation(
    tmp_path: Path,
    *,
    kind: str,
) -> None:
    """Reject overlap and invalid Python before replacing source.

    Args:
        tmp_path: Independent project tree.
        kind: Proposal defect under test.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    before: FileImage | None = read_image(path=source)
    candidate: Path = tmp_path / "candidate.txt"
    candidate.write_bytes(data=b"def invalid(\n")
    after: FileImage | None = read_image(path=candidate)
    edit: FileEdit = FileEdit(
        relative=Path("example.py"),
        before=before,
        after=after,
    )
    journal: SourceJournal = SourceJournal(
        root=tmp_path,
        directory=tmp_path / ".journal",
    )
    journal.acquire()
    try:
        with pytest.raises(
            expected_exception=(SourceConflictError, SyntaxError),
        ):
            journal.commit(
                edits=(edit, edit) if kind == "overlap" else (edit,),
            )
        expect_equal(actual=source.read_bytes(), expected=b"value = 1\n")
    finally:
        journal.release()


def test_post_verification_mutation_is_rejected(tmp_path: Path) -> None:
    """A frozen candidate cannot change before commit.

    Args:
        tmp_path: Independent project tree.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")
    with SourceWorkspace(
        root=tmp_path,
        ignores=(),
        limits=TransactionLimits(),
    ) as workspace:
        workspace.freeze()
        candidate: Path = workspace.path / source.name
        candidate.write_bytes(data=b"value = 2\n")
        with pytest.raises(
            expected_exception=SourceConflictError,
            match="unverified or changed",
        ):
            workspace.proposals()
    expect_equal(actual=source.read_bytes(), expected=b"value = 1\n")


@pytest.mark.parametrize("budget", [0, -1])
def test_invalid_budget_is_rejected(*, budget: int) -> None:
    """A nonpositive budget cannot disable bounded execution.

    Args:
        budget: Pass ceiling under test.

    """
    with pytest.raises(expected_exception=ValueError, match="positive"):
        TransactionLimits(max_passes=budget)


@pytest.mark.parametrize("failure", [False, True])
def test_complete_pipeline_commits_only_verified_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure: bool,
) -> None:
    """All mutating passes run privately; verified edits always publish.

    Args:
        tmp_path: Independent project tree.
        monkeypatch: Pytest patching helper.
        failure: Whether the final audit reports residual findings.

    """
    source: Path = tmp_path / "example.py"
    source.write_bytes(data=b"value = 1\n")

    def run(
        *,
        request: LintExactusRequest,
    ) -> tuple[dict[str, JsonValue], int]:
        """Emulate a convergent transform and independent analyzer.

        Args:
            request: Run scope and config for the emulated pass.

        Returns:
            Report payload and exit status matching ``failure``.

        """
        expect_equal(actual=source.read_bytes(), expected=b"value = 1\n")
        if request.config.fix:
            target: Path = request.cwd / "example.py"
            if target.read_bytes() != b"value = 2\n":
                target.write_bytes(data=b"value = 2\n")
        return {
            "tools": {},
            "findings": ["failure"] if failure else [],
        }, int(failure)

    monkeypatch.setattr(
        target=LintExactus,
        name="_run_cached",
        value=staticmethod(run),
    )
    _, status = LintExactus.run(
        request=LintExactusRequest(
            cwd=tmp_path,
            targets=(".",),
            report_path=tmp_path / "reports" / "LINTS.json",
            ignores=(),
            bare_import_exceptions=(),
            config=LintExactusConfig(),
            writer=StringIO(),
            toolchain=None,
            tool_args={},
        ),
    )
    expect_equal(actual=status, expected=int(failure))
    expect_equal(actual=source.read_bytes(), expected=b"value = 2\n")
