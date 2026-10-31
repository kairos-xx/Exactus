# Copyright (c) 2026
"""The visual-cause report renders findings, counts and evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.visual_cause.core import (
    Finding,
    TargetResult,
    VisualCauseResult,
)
from exactus.tools.visual_cause.report import data, markdown

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.visual_cause.levels import Level


def _finding(*, level: Level, name: str) -> Finding:
    """Build one finding with the given level.

    Args:
        level: Verdict level of the finding.
        name: Element name placed in the identifier.

    Returns:
        The finding.

    """
    return Finding(
        id=f"home/400x300/{name}",
        rule="VCS001",
        target="home",
        viewport="400x300",
        tag="div",
        css_path=f"#{name}",
        query=f"#{name}",
        candidates=(),
        categories=("geometry",),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=1234,
        causes=(),
        level=level,
        decided_by=None if level == "accept" else f"#{name}",
        matched=(),
        message=f"div changed in home at 400x300 ({name}).",
    )


def _target(*, artifacts: dict[str, str]) -> TargetResult:
    """Build one target result.

    Args:
        artifacts: Artifact names to report-relative paths.

    Returns:
        The target result.

    """
    return TargetResult(
        name="home",
        mode="stylesheets",
        viewport="400x300",
        url_a="http://a/",
        url_b="http://b/",
        changed_pixels=4321,
        changed_element_count=3,
        counts={"fail": 1, "warning": 1, "accept": 1},
        artifacts=artifacts,
        server_diagnostics=(),
    )


def test_data_counts_findings_by_level() -> None:
    """The payload carries status, per-level counts and the findings."""
    result: VisualCauseResult = VisualCauseResult(
        targets=(_target(artifacts={}),),
        findings=(
            _finding(level="fail", name="one"),
            _finding(level="warning", name="two"),
            _finding(level="accept", name="three"),
        ),
        queries=({"query": "#one", "level": "fail"},),
        failed=True,
    )
    payload: dict[str, JsonValue] = data(
        result=result,
        project_root="/project",
    )
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_equal(
        actual=payload["summary"],
        expected={
            "targets": 1,
            "findings": 3,
            "fail": 1,
            "warning": 1,
            "accept": 1,
            "severity": {"error": 1, "warning": 1, "info": 1},
        },
    )
    expect_equal(actual=payload["project_root"], expected="/project")
    expect_equal(
        actual=payload["scope"],
        expected={"include": ["home"], "exclude": [], "skipped": []},
    )
    findings: object = payload["findings"]
    expect_true(condition=isinstance(findings, list))
    rows: list[JsonValue] = cast(typ="list[JsonValue]", val=findings)
    expect_equal(actual=len(rows), expected=3)
    first: dict[str, JsonValue] = cast(typ="dict[str, JsonValue]", val=rows[0])
    expect_equal(actual=first["title"], expected="div changed")
    expect_equal(actual=first["severity"], expected="error")
    expect_equal(actual=first["path"], expected="#one")
    expect_true(condition=first["blocking"] is True)


def test_markdown_lists_findings_and_evidence() -> None:
    """The rendered report names findings and embeds the three images."""
    result: VisualCauseResult = VisualCauseResult(
        targets=(
            _target(
                artifacts={
                    "a": "ARTIFACTS/a.png",
                    "b": "ARTIFACTS/b.png",
                    "diff": "ARTIFACTS/diff.png",
                },
            ),
        ),
        findings=(_finding(level="fail", name="one"),),
        queries=(),
        failed=True,
    )
    text: str = markdown(result=result)
    expect_in(member="Verdict: **FAIL**", container=text)
    expect_in(member="### `home/400x300/one`", container=text)
    expect_in(member="4,321", container=text)
    expect_in(member="![](ARTIFACTS/diff.png)", container=text)
    expect_in(member="## Warning findings\n\nNone.", container=text)


def test_markdown_handles_empty_runs() -> None:
    """A run without targets says so and has no evidence images."""
    text: str = markdown(
        result=VisualCauseResult(
            targets=(),
            findings=(),
            queries=(),
            failed=False,
        ),
    )
    expect_in(member="Verdict: **PASS**", container=text)
    expect_in(member="No completed targets", container=text)
    expect_not_in(member="![](", container=text)
