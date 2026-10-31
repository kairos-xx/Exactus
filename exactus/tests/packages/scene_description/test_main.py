# Copyright (c) 2026
"""Tests for the scene_description command-line entry point."""

from __future__ import annotations

from json import dumps, loads
from typing import TYPE_CHECKING

from exactus.packages.scene_description import cli
from exactus.tests.common.support import dig, private_call
from exactus.tests.packages.scene_description.conftest import (
    element,
    report,
    scene,
)
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_raises,
    expect_true,
    require_json_dict,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from exactus.packages.scene_description.models import JsonValue


def _write(*, path: Path, value: object) -> Path:
    """Serialize a JSON document to ``path``.

    Args:
        path: Destination file.
        value: JSON-serializable payload.

    Returns:
        The written path.

    """
    _ = path.write_text(data=dumps(obj=value), encoding="utf-8")
    return path


def _load_document(*, path: Path) -> dict[str, JsonValue]:
    """Invoke the private JSON loader through reflection.

    Args:
        path: JSON document to load.

    Returns:
        Parsed JSON object.

    """
    return require_json_dict(
        value=private_call(owner=cli, name="_load", path=path),
    )


def test_load_returns_dict(tmp_path: Path) -> None:
    """``_load`` returns parsed JSON objects.

    Args:
        tmp_path: Pytest fixture used by this test.

    """
    path: Path = _write(path=tmp_path / "a.json", value={"k": 1})
    expect_equal(actual=_load_document(path=path), expected={"k": 1})


def test_load_rejects_non_object(tmp_path: Path) -> None:
    """``_load`` rejects JSON documents that are not objects.

    Args:
        tmp_path: Pytest fixture used by this test.

    """
    path: Path = _write(path=tmp_path / "a.json", value=[1, 2])
    expect_raises(kind=TypeError, call=lambda: _load_document(path=path))


def test_main_enriches_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI writes an enriched report plus a Markdown summary.

    Args:
        monkeypatch: Pytest fixture used by this test.
        tmp_path: Pytest fixture used by this test.

    """
    report_path: Path = _write(
        path=tmp_path / "report.json",
        value=report(trees=[{"selector": "#cta", "categories": ["layout"]}]),
    )
    scene_a_path: Path = _write(path=tmp_path / "a.json", value=scene())
    scene_b_path: Path = _write(
        path=tmp_path / "b.json",
        value=scene(
            elements={"e": element(selector="#cta", name="Go", tag="button")},
        ),
    )
    output: Path = tmp_path / "out"
    monkeypatch.setattr(
        target="sys.argv",
        name=[
            "scene_description",
            str(object=report_path),
            str(object=scene_a_path),
            str(object=scene_b_path),
            "-o",
            str(object=output),
        ],
    )
    cli.main()
    enriched: dict[str, JsonValue] = loads(
        s=(output / "report.json").read_text(encoding="utf-8"),
    )
    expect_true(condition="change_description" in enriched)
    description: dict[str, JsonValue] = require_json_dict(
        value=dig(
            document=enriched,
            path=("change_trees", 0, "visual_description"),
        ),
    )
    expect_equal(
        actual=description["summary"],
        expected="button “Go” appeared.",
    )
    markdown: str = (output / "description.md").read_text(encoding="utf-8")
    expect_true(
        condition="## Rendered change description" in markdown,
        message=markdown,
    )
