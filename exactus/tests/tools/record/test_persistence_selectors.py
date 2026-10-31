# Copyright (c) 2026 Project contributors
"""Verify selectors persist beside the flows, selectors first."""

from __future__ import annotations

from dataclasses import replace
from json import loads
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tests.tools.record.selector_support import project
from exactus.tools.record.studio import persistence as persistence_module
from exactus.tools.record.studio.persistence import WorkspaceFiles

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.model import Workspace


def _saved(*, root: Path) -> WorkspaceFiles:
    """Open a fresh persistence layer on a project folder.

    Args:
        root: Project folder.

    Returns:
        The persistence layer.

    """
    return WorkspaceFiles(root=root)


def _names(*, document: object) -> list[object]:
    """Return the selector names listed in a document.

    Args:
        document: Decoded selectors document or project document.

    Returns:
        The ``name`` of every selector, in order.

    """
    return [
        dig(document=item, path=("name",))
        for item in dig_list(document=document, path=("selectors",))
    ]


def test_save_writes_selectors_beside_the_flows(tmp_path: Path) -> None:
    """Keep selectors out of the flows file and in their own document.

    Args:
        tmp_path: Disposable project folder.

    """
    files: WorkspaceFiles = _saved(root=tmp_path)
    files.save(workspace=project(), data={"filename": "flows.pwflow.json"})
    flows: dict[str, object] = loads(
        s=(tmp_path / "flows.pwflow.json").read_text(encoding="utf-8"),
    )
    selectors: object = loads(
        s=(tmp_path / "selectors.pwflow.json").read_text(encoding="utf-8"),
    )
    expect_false(condition="selectors" in flows)
    expect_equal(actual=_names(document=selectors), expected=["card", "title"])


def test_project_round_trips_through_the_files(tmp_path: Path) -> None:
    """Reopen a saved project with the same selectors.

    Args:
        tmp_path: Disposable project folder.

    """
    original: Workspace = project()
    _saved(root=tmp_path).save(
        workspace=original,
        data={"filename": "flows.pwflow.json"},
    )
    reopened: Workspace = _saved(root=tmp_path).open(
        data={"filename": "flows.pwflow.json"},
    )
    expect_equal(actual=reopened.selectors, expected=original.selectors)
    expect_equal(
        actual=reopened.flows[1].events[0].selector_id,
        expected="sel-card",
    )


def test_selectors_are_written_before_the_flows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave an unused selector, not a dangling reference, after a crash.

    Args:
        tmp_path: Disposable project folder.
        monkeypatch: Replaces the flows writer with one that fails.

    """

    def explode(**_: object) -> None:
        """Simulate a storage failure.

        Args:
            **_: Ignored save arguments.

        Raises:
            OSError: Always, carrying ``disk full``.

        """
        msg: str = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(
        target=persistence_module,
        name="write_workspace",
        value=explode,
    )
    with pytest.raises(expected_exception=OSError, match="disk full"):
        _saved(root=tmp_path).save(
            workspace=project(),
            data={"filename": "flows.pwflow.json"},
        )
    expect_true(condition=(tmp_path / "selectors.pwflow.json").exists())
    expect_false(condition=(tmp_path / "flows.pwflow.json").exists())


def test_no_selectors_means_no_file_until_one_existed(tmp_path: Path) -> None:
    """Skip an empty file, but record deletion of the last selector.

    Args:
        tmp_path: Disposable project folder.

    """
    files: WorkspaceFiles = _saved(root=tmp_path)
    bare: Workspace = replace(project(), selectors=())
    files.save(workspace=bare, data={"filename": "flows.pwflow.json"})
    expect_false(condition=(tmp_path / "selectors.pwflow.json").exists())
    files.save(workspace=project(), data={"filename": "flows.pwflow.json"})
    expect_true(condition=(tmp_path / "selectors.pwflow.json").exists())
    files.save(workspace=bare, data={"filename": "flows.pwflow.json"})
    document: dict[str, object] = loads(
        s=(tmp_path / "selectors.pwflow.json").read_text(encoding="utf-8"),
    )
    expect_equal(actual=document["selectors"], expected=[])


def test_external_edits_to_selectors_are_not_overwritten(
    tmp_path: Path,
) -> None:
    """Refuse to save over a selectors file changed behind Studio's back.

    Args:
        tmp_path: Disposable project folder.

    """
    files: WorkspaceFiles = _saved(root=tmp_path)
    files.save(workspace=project(), data={"filename": "flows.pwflow.json"})
    path: Path = tmp_path / "selectors.pwflow.json"
    _ = path.write_text(
        data=path.read_text(encoding="utf-8").replace("card", "cards"),
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=ValueError, match="Selectors"):
        files.save(workspace=project(), data={})


def test_uploaded_projects_and_exports_carry_selectors(tmp_path: Path) -> None:
    """Move selectors inside the document when there is no sibling file.

    Args:
        tmp_path: Disposable project folder.

    """
    files: WorkspaceFiles = _saved(root=tmp_path)
    exported: dict[str, JsonValue] = files.project_document(
        workspace=project(),
    )
    expect_equal(actual=_names(document=exported), expected=["card", "title"])
    (tmp_path / "other").mkdir()
    imported: Workspace = _saved(root=tmp_path / "other").open(
        data={"workspace": exported},
    )
    expect_equal(
        actual=[item.name for item in imported.selectors],
        expected=["card", "title"],
    )


def test_recovery_keeps_unsaved_selectors(tmp_path: Path) -> None:
    """Recover selectors together with the unsaved flows.

    Args:
        tmp_path: Disposable project folder.

    """
    _saved(root=tmp_path).persist_recovery(workspace=project())
    recovered: Workspace | None = _saved(root=tmp_path).recover()
    expect_equal(
        actual=None if recovered is None else len(recovered.selectors),
        expected=2,
    )
