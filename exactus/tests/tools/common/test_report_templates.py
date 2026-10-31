# Copyright (c) 2026
"""The shipped report templates render goldens and reach the bundle."""

from __future__ import annotations

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages.markdown import render_report
from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.reports.bundle import ReportBundle, ReportPaths

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        common: Grouped module constant.
        template: Grouped module constant.
        examples: Grouped module constant.
        mapping: Grouped module constant.
        html: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    common: Final[Path] = root / "exactus" / "tools" / "common" / "templates"
    template: Final[Path] = common / "markdown" / "result_template.md"
    examples: Final[Path] = common / "markdown" / "examples"
    mapping: Final[Path] = common / "markdown" / "mapping.json"
    html: Final[Path] = common / "html"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("result.json", "expected.md"),
        ("empty_result.json", "expected_empty.md"),
        ("error_result.json", "expected_error.md"),
    ],
)
def test_example_matches_golden(*, data: str, expected: str) -> None:
    """The core template reproduces the golden Markdown exactly.

    Args:
        data: Source JSON file name.
        expected: Golden Markdown file name.

    """
    rendered: str = render_report(
        result=Constants.examples / data,
        template=Constants.template,
        mapping=Constants.mapping,
    )
    golden: str = (Constants.examples / expected).read_text(encoding="utf-8")
    expect_equal(actual=rendered, expected=golden)


def test_empty_example_keeps_every_section() -> None:
    """A clean run still states scope, findings and artifacts."""
    rendered: str = render_report(
        result=Constants.examples / "empty_result.json",
        template=Constants.template,
        mapping=Constants.mapping,
    )
    for heading in (
        "## Identity",
        "## What was checked",
        "### Scope",
        "## Setup",
        "## Gate",
        "## Findings",
        "## Artifacts",
    ):
        expect_in(member=heading, container=rendered)
    expect_in(member="No findings.", container=rendered)
    expect_in(member="No skipped targets.", container=rendered)
    expect_in(member="N/A — no include rules.", container=rendered)
    expect_in(member="No auxiliary artifacts.", container=rendered)
    expect_in(member="| Exit code | N/A |", container=rendered)


def test_pipes_in_cells_and_globs_survive() -> None:
    """Pipes are escaped in table cells; globs stay literal code spans."""
    text: str = (Constants.examples / "result.json").read_text(
        encoding="utf-8",
    )
    document: JsonValue = loads(s=text.replace('"run-001"', '"a|b"'))
    rendered: str = render_report(
        result=document,
        template=Constants.template,
        mapping=Constants.mapping,
    )
    expect_in(member="| Run ID | a\\|b |", container=rendered)
    expect_in(member="- `**/__pycache__/**`", container=rendered)
    expect_in(
        member="| exactus/packages/x.js | excluded by config |",
        container=rendered,
    )
    expect_in(member="- F-003 — Mutable default argument", container=rendered)
    expect_in(
        member="| stderr.log | ARTIFACTS/stderr.log | 120 |",
        container=rendered,
    )


def test_error_example_renders_missing_blocks_as_na() -> None:
    """A crash result without tool blocks renders ``N/A`` sections."""
    rendered: str = render_report(
        result=Constants.examples / "error_result.json",
        template=Constants.template,
        mapping=Constants.mapping,
    )
    expect_in(member="| Status | ERROR |", container=rendered)
    expect_in(
        member="> **Gate: ERROR** — RuntimeError: boom",
        container=rendered,
    )
    for sentence in (
        "N/A — the tool reported no summary.",
        "N/A — the tool reported no scope.",
        "N/A — the tool reported no findings list.",
    ):
        expect_in(member=sentence, container=rendered)


def test_bundle_ships_the_common_web_assets(tmp_path: Path) -> None:
    """``ReportBundle.write`` copies the shipped web assets verbatim.

    Args:
        tmp_path: Per-test temporary directory.

    """
    ReportBundle.write(
        paths=ReportPaths(
            markdown=tmp_path / "result.md",
            json=tmp_path / "result.json",
            web=tmp_path / "result_web",
        ),
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n\nBody\n",
        data={"findings": []},
    )
    web: Path = tmp_path / "result_web"
    expect_equal(
        actual=(web / "report.js").read_text(encoding="utf-8"),
        expected=(Constants.html / "report.js").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=(web / "cerulean.css").read_text(encoding="utf-8"),
        expected=(Constants.html / "vendor" / "cerulean.css").read_text(
            encoding="utf-8",
        ),
    )
