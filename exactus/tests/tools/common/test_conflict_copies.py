"""Verify automatic sync cleanup preserves unique and conflicting data."""

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from exactus.bundle import conflict_copies as toolkit_copies
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.conflict_copies import (
    ClearResult,
    clear_conflict_copies,
)
from exactus.tools.record import conflict_copies as record_copies

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


def test_sync_merges_unique_entries_and_preserves_conflicts(
    tmp_path: Path,
) -> None:
    """Keep canonical bytes, merge unique data and retain conflicting copies.

    Args:
        tmp_path: Isolated sync project.

    """
    canonical: Path = tmp_path / "reports"
    duplicate: Path = tmp_path / "reports 2"
    (canonical / "nested").mkdir(parents=True)
    (duplicate / "nested").mkdir(parents=True)
    (canonical / "same.txt").write_text(data="same")
    (duplicate / "same.txt").write_text(data="same")
    (canonical / "conflict.txt").write_text(data="current")
    (duplicate / "conflict.txt").write_text(data="unique older bytes")
    (duplicate / "nested/new.txt").write_text(data="keep me")
    (duplicate / "extra").mkdir()
    (duplicate / "extra/file.txt").write_text(data="extra")
    (canonical / "kind").write_text(data="canonical file")
    (duplicate / "kind").mkdir()
    (duplicate / "kind/other.txt").write_text(data="different kind")
    result: ClearResult = clear_conflict_copies(root=tmp_path)
    expect_equal(actual=result.removed_directories, expected=1)
    expect_equal(actual=result.merged_entries, expected=2)
    expect_equal(actual=result.preserved_conflicts, expected=2)
    expect_equal(actual=result.errors, expected=0)
    expect_false(condition=duplicate.exists())
    expect_equal(
        actual=(canonical / "conflict.txt").read_text(),
        expected="current",
    )
    expect_equal(
        actual=(canonical / "nested/new.txt").read_text(),
        expected="keep me",
    )
    recovered: set[str] = {
        p.read_text()
        for p in (tmp_path / ".icloud-conflicts").rglob(pattern="*.txt")
    }
    expect_equal(
        actual=recovered,
        expected={"unique older bytes", "different kind"},
    )
    expect_equal(
        actual=clear_conflict_copies(root=tmp_path).removed_directories,
        expected=0,
    )


def test_sync_ignores_unmatched_hidden_and_symlink_directories(
    tmp_path: Path,
) -> None:
    """Avoid traversing external links and retain unmatched numbered folders.

    Args:
        tmp_path: Isolated sync project.

    """
    (tmp_path / "chapter 2").mkdir()
    (tmp_path / ".hidden/data").mkdir(parents=True)
    (tmp_path / ".hidden/data 2").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data 2").symlink_to(
        target=tmp_path / "data",
        target_is_directory=True,
    )
    (tmp_path / "linked").symlink_to(
        target=tmp_path / "data",
        target_is_directory=True,
    )
    (tmp_path / "linked 2").mkdir()
    expect_equal(
        actual=clear_conflict_copies(root=tmp_path).removed_directories,
        expected=0,
    )
    expect_true(condition=(tmp_path / "chapter 2").is_dir())
    expect_true(condition=(tmp_path / ".hidden/data 2").is_dir())
    expect_true(condition=(tmp_path / "data 2").is_symlink())
    expect_equal(
        actual=clear_conflict_copies(
            root=tmp_path / "missing",
        ).removed_directories,
        expected=0,
    )
    expect_equal(
        actual=clear_conflict_copies(
            root=tmp_path / "linked",
        ).removed_directories,
        expected=0,
    )


def test_sync_merges_numbered_hidden_directories(tmp_path: Path) -> None:
    """Reconcile ``.name N`` copies without traversing other hidden trees.

    Args:
        tmp_path: Isolated sync project.

    """
    canonical: Path = tmp_path / ".runtime"
    duplicate: Path = tmp_path / ".runtime 2"
    canonical.mkdir()
    duplicate.mkdir()
    _ = (duplicate / "state.json").write_text(data="{}", encoding="utf-8")
    _ = (duplicate / "nested 2").mkdir()
    result: ClearResult = clear_conflict_copies(root=tmp_path)
    expect_equal(
        actual=(
            result.removed_directories,
            (tmp_path / ".runtime/state.json").is_file(),
            (tmp_path / ".runtime/nested 2").is_dir(),
            duplicate.exists(),
        ),
        expected=(1, True, True, False),
    )


def test_sync_compares_links_and_retries_busy_folders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove identical links and retry unavailable directories later.

    Args:
        tmp_path: Isolated sync project.
        monkeypatch: Injected filesystem availability failure.

    """
    (tmp_path / "base").mkdir()
    duplicate: Path = tmp_path / "base 10"
    duplicate.mkdir()
    (tmp_path / "base/link").symlink_to(target="absent")
    (duplicate / "link").symlink_to(target="absent")
    expect_equal(
        actual=clear_conflict_copies(root=tmp_path).removed_directories,
        expected=1,
    )
    duplicate.mkdir()
    original: Callable[[Path], None] = Path.rmdir

    def busy(self: Path) -> None:
        """Emulate a sync provider holding the numbered folder.

        Args:
            self: Directory being removed.

        Raises:
            OSError: When the duplicate folder is temporarily unavailable.

        """
        if self == duplicate:
            msg: str = "Sync folder is busy"
            raise OSError(msg)
        original(self)

    monkeypatch.setattr(target=Path, name="rmdir", value=busy)
    expect_equal(
        actual=clear_conflict_copies(root=tmp_path).errors,
        expected=1,
    )
    expect_true(condition=duplicate.is_dir())


@pytest.fixture(
    autouse=True,
    params=(
        "exactus.tools.common.conflict_copies",
        "exactus.tools.actions.conflict_copies",
        "exactus.tools.record.conflict_copies",
        toolkit_copies.__name__,
    ),
)
def subsystem_contract(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the shared behavior in every shipped subsystem copy.

    Args:
        request: Parametrized implementation module name.
        monkeypatch: Isolated module binding substitutions.

    """
    implementations: dict[str, ModuleType] = {
        "exactus.tools.record.conflict_copies": record_copies,
        toolkit_copies.__name__: toolkit_copies,
    }
    implementation: ModuleType = implementations.get(
        request.param,
    ) or import_module(name=request.param)
    monkeypatch.setattr(
        target=import_module(name=__name__),
        name="ClearResult",
        value=implementation.ClearResult,
    )
    monkeypatch.setattr(
        target=import_module(name=__name__),
        name="clear_conflict_copies",
        value=implementation.clear_conflict_copies,
    )


def test_history_backups_are_never_reconciled(tmp_path: Path) -> None:
    """Backup folders and numbered backup copies are left untouched.

    Args:
        tmp_path: Disposable project.

    """
    backup: Path = tmp_path / ".history"
    duplicate: Path = tmp_path / ".history 2"
    backup.mkdir()
    duplicate.mkdir()
    (backup / "old").mkdir()
    (backup / "old 2").mkdir()
    (duplicate / "unique.txt").write_text(data="backup")
    result: ClearResult = clear_conflict_copies(root=tmp_path)
    expect_equal(actual=result.removed_directories, expected=0)
    expect_true(condition=(backup / "old 2").exists())
    expect_equal(
        actual=(duplicate / "unique.txt").read_text(),
        expected="backup",
    )
    result = clear_conflict_copies(root=backup)
    expect_equal(actual=result.removed_directories, expected=0)
