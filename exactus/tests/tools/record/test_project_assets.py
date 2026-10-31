# Copyright (c) 2026 Project contributors
"""Verify portable screenshot projects and transactional asset imports."""

from __future__ import annotations

from hashlib import sha256
from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from PIL import Image

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.model import (
    CapturePhase,
    EventKind,
    Flow,
    ScreenshotArtifact,
    TimelineEvent,
    TimelineLayer,
)
from exactus.tools.record.store import Workspace
from exactus.tools.record.studio.persistence import WorkspaceFiles

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def _workspace(*, root: Path) -> Workspace:
    """Create a real owned PNG and its current project metadata.

    Args:
        root: Directory that owns the PNG artifact.

    Returns:
        Workspace referencing the stored screenshot.

    """
    path: Path = root / "shot.png"
    root.mkdir(parents=True, exist_ok=True)
    Image.new(mode="RGB", size=(24, 16), color="#242527").save(fp=path)
    return Workspace(
        flows=(
            Flow(
                flow_id="flow",
                name="Test",
                task_description="",
                expected_behavior="",
                notes="",
                events=(
                    TimelineEvent(
                        event_id="event",
                        flow_id="flow",
                        sequence=0,
                        elapsed_ms=0,
                        layer=TimelineLayer.INTERACTION,
                        kind=EventKind.NOTE,
                        label="Screenshot",
                        payload="__screenshot__",
                    ),
                ),
            ),
        ),
        edges=(),
        screenshots=(
            ScreenshotArtifact(
                artifact_id="shot",
                flow_id="flow",
                event_id="event",
                phase=CapturePhase.RECORD,
                path=str(object=path),
                width=24,
                height=16,
                sha256=sha256(data=path.read_bytes()).hexdigest(),
            ),
        ),
    )


def test_project_transfers_between_roots(tmp_path: Path) -> None:
    """Keep screenshots usable after moving a single exported project file.

    Args:
        tmp_path: Isolated per-test directory.

    """
    source: WorkspaceFiles = WorkspaceFiles(root=tmp_path / "source")
    original: Workspace = _workspace(root=source.artifact_root)
    portable: dict[str, JsonValue] = source.project_document(
        workspace=original,
    )
    destination: WorkspaceFiles = WorkspaceFiles(root=tmp_path / "destination")
    opened: Workspace = destination.open(data={"workspace": portable})
    image: Path = destination.artifact(workspace=opened, artifact_id="shot")
    expect_equal(
        actual=image.read_bytes(),
        expected=Path(original.screenshots[0].path).read_bytes(),
    )
    destination.save(workspace=opened, data={"filename": "moved.pwflow.json"})
    again: WorkspaceFiles = WorkspaceFiles(root=tmp_path / "third")
    project: Path = destination.root / "moved.pwflow.json"
    transferred: Workspace = again.open(
        data={"workspace": loads(s=project.read_text())},
    )
    expect_true(
        condition=again.artifact(
            workspace=transferred,
            artifact_id="shot",
        ).is_file(),
    )


@pytest.mark.parametrize("change", ["hash", "dimensions", "path", "encoding"])
def test_invalid_asset_does_not_replace_project(
    change: str,
    tmp_path: Path,
) -> None:
    """Reject invalid assets before writing files or changing save metadata.

    Args:
        change: Metadata field corrupted in the rejected asset.
        tmp_path: Isolated per-test directory.

    """
    source: WorkspaceFiles = WorkspaceFiles(root=tmp_path / "source")
    original: Workspace = _workspace(root=source.artifact_root)
    portable: dict[str, JsonValue] = source.project_document(
        workspace=original,
    )
    screenshots: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=portable["screenshots"],
    )
    shot: dict[str, JsonValue] = screenshots[0]
    if change == "hash":
        shot["sha256"] = "0" * 64
    elif change == "dimensions":
        shot["width"] = 12
    elif change == "path":
        shot["path"] = "../../outside.png"
    else:
        assets: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=portable["assets"],
        )
        assets[str(object=shot["sha256"])] = "invalid@@"
    destination: WorkspaceFiles = WorkspaceFiles(root=tmp_path / "destination")
    with pytest.raises(
        expected_exception=ValueError,
        match=r"Screenshot|screenshot|Project",
    ):
        destination.open(data={"workspace": portable})
    expect_equal(actual=list(destination.artifact_root.iterdir()), expected=[])
    expect_equal(actual=destination.saved_name, expected=None)
