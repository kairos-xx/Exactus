#!/usr/bin/env python3
# Copyright (c) 2026
"""Enrich an existing Visual Cause report with captured A/B scene manifests.

The example consumes a ``results`` directory in the working directory —
``report.json`` plus the ``scene-a.json``/``scene-b.json`` manifests —
and writes ``report-described.json`` and ``description.md`` beside them.
When the inputs are missing, a small synthetic set is written first so
the demo runs from any directory.
"""

from contextlib import suppress
from importlib import import_module
from json import dumps, loads
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.scene_description.visual_cause import (
    VisualCauseDescriber,
)

if TYPE_CHECKING:
    from exactus.packages.scene_description.models import JsonValue


def _inputs(*, root: Path) -> None:
    """Write a minimal synthetic report and scene pair for the demo.

    Args:
        root: ``results`` directory receiving the input fixtures.

    """
    report: dict[str, JsonValue] = {
        "change_trees": [
            {
                "selector": "#cta",
                "categories": ["layout"],
                "mechanisms": ["script"],
                "root_cause": {"rule": "demo"},
            },
        ],
    }
    scene_a: dict[str, JsonValue] = {
        "metadata": {"url": "https://example.test/", "variant": "A"},
        "reference": {},
        "elements": {
            "header": {
                "selector": "header",
                "tag": "header",
                "name": "Site header",
            },
        },
    }
    scene_b: dict[str, JsonValue] = {
        "metadata": {"url": "https://example.test/", "variant": "B"},
        "reference": {},
        "elements": {
            "header": {
                "selector": "header",
                "tag": "header",
                "name": "Site header",
            },
            "cta": {"selector": "#cta", "tag": "button", "name": "Go"},
        },
    }
    for name, document in (
        ("report.json", report),
        ("scene-a.json", scene_a),
        ("scene-b.json", scene_b),
    ):
        _ = (root / name).write_text(
            data=dumps(obj=document, indent=2),
            encoding="utf-8",
        )


def main() -> None:
    """Read Visual Cause and scene JSON files and write an enriched report."""
    root: Path = Path("results")
    if not all(
        (root / name).is_file()
        for name in ("report.json", "scene-a.json", "scene-b.json")
    ):
        root = Path(__file__).resolve().parent / ".scratch" / "results"
        root.mkdir(parents=True, exist_ok=True)
        _inputs(root=root)
    report: dict[str, JsonValue] = loads(s=(root / "report.json").read_text())
    scene_a: dict[str, JsonValue] = loads(
        s=(root / "scene-a.json").read_text(),
    )
    scene_b: dict[str, JsonValue] = loads(
        s=(root / "scene-b.json").read_text(),
    )
    describer: VisualCauseDescriber = VisualCauseDescriber()
    enriched: dict[str, JsonValue] = describer.enrich(
        report=report,
        scene_a=scene_a,
        scene_b=scene_b,
    )
    (root / "report-described.json").write_text(
        data=dumps(obj=enriched, indent=2),
        encoding="utf-8",
    )
    (root / "description.md").write_text(
        data=describer.markdown(report=enriched),
        encoding="utf-8",
    )
    _ = stdout.write(
        f"enriched report: {root / 'report-described.json'}\n"
        f"description:     {root / 'description.md'}\n",
    )


if __name__ == "__main__":
    main()
