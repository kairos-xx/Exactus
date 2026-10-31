# Copyright (c) 2026
"""Tests for the runnable scene_description examples."""

from __future__ import annotations

from json import dumps, loads
from os import environ
from pathlib import Path
from subprocess import CompletedProcess, run
from sys import executable
from typing import TYPE_CHECKING

from exactus.packages.scene_description.examples import run as example_run
from exactus.packages.scene_description.examples.run import main
from exactus.tests.common.support import dig
from exactus.tests.packages.scene_description.conftest import (
    element,
    report,
    scene,
)
from exactus.tests.packages.scene_description.support import (
    expect_equal,
    expect_true,
    require_json_dict,
)

if TYPE_CHECKING:
    import pytest

    from exactus.packages.scene_description.models import JsonValue


def _seed_results(*, root: Path) -> None:
    """Populate a ``results`` directory the example consumes.

    Args:
        root: Working directory gaining a ``results`` tree.

    """
    results: Path = root / "results"
    results.mkdir()
    _ = (results / "report.json").write_text(
        data=dumps(
            obj=report(
                trees=[
                    {
                        "selector": "#cta",
                        "categories": ["layout"],
                        "root_cause": {"rule": "x"},
                    },
                ],
            ),
        ),
        encoding="utf-8",
    )
    _ = (results / "scene-a.json").write_text(
        data=dumps(obj=scene()),
        encoding="utf-8",
    )
    _ = (results / "scene-b.json").write_text(
        data=dumps(
            obj=scene(
                elements={
                    "e": element(selector="#cta", name="Go", tag="button"),
                },
            ),
        ),
        encoding="utf-8",
    )


def test_example_main_writes_enriched_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``examples.run.main`` emits JSON and Markdown next to its inputs.

    Args:
        monkeypatch: Pytest fixture used by this test.
        tmp_path: Pytest fixture used by this test.

    """
    _seed_results(root=tmp_path)
    monkeypatch.chdir(path=tmp_path)
    main()
    enriched: dict[str, JsonValue] = loads(
        s=(tmp_path / "results" / "report-described.json").read_text(
            encoding="utf-8",
        ),
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
    markdown: str = (tmp_path / "results" / "description.md").read_text(
        encoding="utf-8",
    )
    expect_true(
        condition="## Rendered change description" in markdown,
        message=markdown,
    )


def test_example_main_seeds_inputs_when_results_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main`` synthesizes inputs under ``.scratch`` when none exist.

    Args:
        tmp_path: Pytest fixture used by this test.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setattr(
        target=example_run,
        name="__file__",
        value=str(object=tmp_path / "pkg" / "examples" / "run.py"),
    )
    main()
    results: Path = tmp_path / "pkg" / "examples" / ".scratch" / "results"
    expect_true(condition=(results / "report-described.json").is_file())
    expect_true(condition=(results / "description.md").is_file())


def test_examples_module_entrypoint(tmp_path: Path) -> None:
    """``python -m exactus.packages.scene_description.examples`` runs the demo.

    Args:
        tmp_path: Pytest fixture used by this test.

    """
    _seed_results(root=tmp_path)
    completed: CompletedProcess[str] = run(
        args=[executable, "-m", "exactus.packages.scene_description.examples"],
        cwd=tmp_path,
        env={**environ, "PYTHONPATH": str(object=Path(__file__).parents[4])},
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(
        actual=completed.returncode,
        expected=0,
        message=completed.stderr,
    )
    expect_true(
        condition=(tmp_path / "results" / "report-described.json").is_file(),
        message=completed.stderr,
    )
