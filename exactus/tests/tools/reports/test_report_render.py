# Copyright (c) 2026
"""Tool templates extend the common template; mappings merge over base."""

from __future__ import annotations

from json import dumps, loads
from shutil import copytree
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast
from zipfile import Path as ZipPath
from zipfile import ZipFile

import pytest

from exactus.packages.markdown import MappingError
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    private_call,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.envelope import RunFacts
from exactus.tools.reports import render as report_render
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.reports.render import (
    Constants,
    RenderedReport,
    ReportTemplates,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
EXAMPLES: Final[Path] = Constants.common / "examples"


def test_packaged_templates_remain_renderable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render the complete report from templates stored inside a ZIP.

    Args:
        tmp_path: Temporary archive directory.
        monkeypatch: Test patch manager.

    """
    archive: Path = tmp_path / "check.zip"
    with ZipFile(file=archive, mode="w") as bundle:
        for tool in ("common", "lints"):
            source: Path = Constants.tools / tool / "templates" / "markdown"
            for template in source.rglob(pattern="*"):
                if template.is_file():
                    bundle.write(
                        template,
                        template.relative_to(Constants.tools),
                    )
    with ZipFile(file=archive) as bundle:

        def resources(package: str) -> ZipPath:
            """Return the archived resource root.

            Args:
                package: Package whose resources are requested.

            Returns:
                The ZIP template tree.

            """
            expect_equal(actual=package, expected="exactus.tools")
            return ZipPath(root=bundle)

        monkeypatch.setattr(
            target=report_render,
            name="__file__",
            value=str(object=archive / "reports/render.py"),
        )
        monkeypatch.setattr(
            target=report_render,
            name="resource_files",
            value=resources,
        )
        root: Path = cast(
            typ="Path",
            val=private_call(owner=report_render, name="_template_tools_root"),
        )
        model: JsonValue = _example()
        findings: JsonValue = (
            model.get("findings") if isinstance(model, dict) else None
        )
        if isinstance(findings, list):
            for finding in findings:
                if isinstance(finding, dict):
                    finding["source"] = "ruff"
        rendered: RenderedReport = ReportTemplates.render(
            model=model,
            tool_dir=root / "lints/templates/markdown",
            common_dir=root / "common/templates/markdown",
        )
    for heading in (
        "## Identity",
        "## What was checked",
        "## Setup",
        "## Findings",
        "## Artifacts",
    ):
        expect_in(member=heading, container=rendered.markdown)
    expect_in(member="Mutable default argument", container=rendered.markdown)


def _tool_dir(*, root: Path, mapping: JsonValue | None) -> Path:
    """Create a throwaway tool template directory.

    Args:
        root: Parent directory.
        mapping: Tool mapping to write, or ``None`` for none.

    Returns:
        The tool Markdown template directory.

    """
    folder: Path = root / "tool" / "templates" / "markdown"
    folder.mkdir(parents=True)
    _ = (folder / "template.md").write_text(
        data=(
            dedent(
                text=(
                    '    {% extends "result_template.md" %}\n    {% block '
                    "tool_extension %}\n    \n    ## Extra\n    \n    {{ e"
                    "xtra }} / {{ severity_levels | join(',') }}\n    {% e"
                    "ndblock %}\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    if mapping is not None:
        _ = (folder / "mapping.json").write_text(
            data=dumps(obj=mapping),
            encoding="utf-8",
        )
    return folder


def _example() -> JsonValue:
    """Load the common example result.

    Returns:
        The parsed example.

    """
    loaded: JsonValue = loads(
        s=(EXAMPLES / "result.json").read_text(encoding="utf-8"),
    )
    return loaded


def test_tool_template_extends_common_template(tmp_path: Path) -> None:
    """The tool block lands after Artifacts and before the footer.

    Args:
        tmp_path: Per-test temporary directory.

    """
    rendered: RenderedReport = ReportTemplates.render(
        model=_example(),
        tool_dir=_tool_dir(
            root=tmp_path,
            mapping={"extra": {"$literal": "tool-value"}},
        ),
    )
    text: str = rendered.markdown
    expect_in(
        member="## Extra\n\ntool-value / error,warning,info\n",
        container=text,
    )
    expect_true(
        condition=text.index("## Artifacts")
        < text.index("## Extra")
        < text.index("\n---\n"),
    )
    expect_equal(actual=rendered.view["extra"], expected="tool-value")
    expect_not_in(member="source", container=rendered.view)


def test_tool_mapping_wins_over_base(tmp_path: Path) -> None:
    """Tool keys replace base keys; other base keys stay.

    Args:
        tmp_path: Per-test temporary directory.

    """
    folder: Path = _tool_dir(
        root=tmp_path,
        mapping={
            "extra": {"$literal": "x"},
            "severity_levels": {"$literal": ["error"]},
        },
    )
    merged: dict[str, JsonValue] = ReportTemplates.mapping(tool_dir=folder)
    expect_equal(
        actual=merged["severity_levels"],
        expected={"$literal": ["error"]},
    )
    expect_equal(actual=merged["run"], expected="run")
    text: str = ReportTemplates.render(
        model=_example(),
        tool_dir=folder,
    ).markdown
    expect_in(member="x / error\n", container=text)
    expect_not_in(member="| WARNING |", container=text)


def test_missing_tool_mapping_uses_base(tmp_path: Path) -> None:
    """Without a tool mapping the base mapping applies alone.

    Args:
        tmp_path: Per-test temporary directory.

    """
    folder: Path = _tool_dir(root=tmp_path, mapping=None)
    expect_equal(
        actual=ReportTemplates.mapping(tool_dir=folder),
        expected=ReportTemplates.load_mapping(
            path=Constants.common / "mapping.json",
        ),
    )


@pytest.mark.parametrize("content", ["[1]", "{nope"])
def test_bad_mapping_is_rejected(*, tmp_path: Path, content: str) -> None:
    """A mapping that is not a JSON object raises ``MappingError``.

    Args:
        tmp_path: Per-test temporary directory.
        content: Mapping file text.

    """
    path: Path = tmp_path / "mapping.json"
    _ = path.write_text(data=content, encoding="utf-8")
    with pytest.raises(expected_exception=MappingError):
        _ = ReportTemplates.load_mapping(path=path)


def test_migrated_tools() -> None:
    """Every tool ships a Markdown template."""
    for analyzer in (
        "readme",
        "docs",
        "lints",
        "kwargs_typehints",
        "coverage_tests",
        "record",
    ):
        expect_true(condition=ReportTemplates.migrated(analyzer=analyzer))
    expect_true(condition=ReportTemplates.migrated(analyzer="frontend"))
    expect_equal(
        actual=ReportTemplates.tool_dir(analyzer="kwargs_typehints").parts[-3],
        expected="kwargs_typehints",
    )


def test_validate_blocks() -> None:
    """Missing, mistyped and incomplete blocks are rejected."""
    complete: dict[str, JsonValue] = {
        name: [] if name in BundleConstants.list_blocks else {}
        for name in BundleConstants.normalized_blocks
    }
    ReportBundle.validate_blocks(
        payload=complete,
        required=BundleConstants.normalized_blocks,
    )
    ReportBundle.validate_blocks(payload={}, required=frozenset())
    cases: list[tuple[dict[str, JsonValue], str]] = [
        ({**complete, "gate": None}, "'gate' must be a JSON object"),
        ({**complete, "findings": {}}, "'findings' must be a JSON list"),
        ({**complete, "findings": [{"id": "x"}]}, "finding missing keys"),
        ({**complete, "findings": ["x"]}, "finding missing keys"),
    ]
    payload: dict[str, JsonValue]
    message: str
    for payload, message in cases:
        with pytest.raises(expected_exception=ValueError, match=message):
            ReportBundle.validate_blocks(
                payload=payload,
                required=BundleConstants.normalized_blocks,
            )
    with pytest.raises(expected_exception=ValueError, match="missing blocks"):
        ReportBundle.validate_blocks(
            payload={},
            required=BundleConstants.envelope_blocks,
        )


def _legacy_bundle(*, output: Path) -> None:
    """Write a legacy report bundle for an unmigrated tool.

    Args:
        output: Report directory.

    """
    _ = ReportBundle.write(
        paths=ReportPaths(
            markdown=output / "result.md",
            json=output / "result.json",
            web=output / "result_web",
        ),
        analyzer="frontend",
        title="Screenshot Report",
        markdown="# Screenshot Report\n\n## Findings\n\nNone.\n",
        data={"findings": [], "summary": {"files": 1}},
    )


def test_unmigrated_tool_keeps_legacy_markdown(tmp_path: Path) -> None:
    """Run facts do not change an unmigrated tool's stamped report.

    Args:
        tmp_path: Per-test temporary directory.

    """
    legacy: Path = tmp_path / "legacy"
    _legacy_bundle(output=legacy)
    stamped: Path = tmp_path / "stamped"
    _ = copytree(src=legacy, dst=stamped)
    _ = private_call(
        owner=ent,
        name="_stamp_result",
        output=legacy,
        analyzer="frontend",
        status=0,
        elapsed_seconds=1.0,
    )
    _ = private_call(
        owner=ent,
        name="_stamp_result",
        output=stamped,
        analyzer="frontend",
        status=0,
        elapsed_seconds=1.0,
        facts=RunFacts(
            analyzer="frontend",
            title="Screenshot Report",
            status="PASS",
            exit_code=0,
            error=None,
            started_at=None,
            finished_at="2026-10-03T09:00:00+00:00",
            duration_seconds=1.0,
            run_id=None,
            pipeline_run_id=None,
            command="exactus --tool frontend",
            cwd=str(object=tmp_path),
            arguments=(),
            output=stamped,
        ),
    )
    markdown: str = (stamped / "result.md").read_text(encoding="utf-8")
    expect_equal(
        actual=markdown,
        expected=(legacy / "result.md").read_text(encoding="utf-8"),
    )


def test_identity_renders_previous_duration(tmp_path: Path) -> None:
    """The Identity table shows the previous run duration when available.

    Args:
        tmp_path: Per-test temporary directory.

    """
    model: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=_example(),
    )
    model["previous_duration_seconds"] = 7.891
    rendered: RenderedReport = ReportTemplates.render(
        model=model,
        tool_dir=_tool_dir(
            root=tmp_path,
            mapping={"extra": {"$literal": "x"}},
        ),
    )
    expect_in(
        member="| Previous duration | 7.891s |",
        container=rendered.markdown,
    )


def test_fence_markers_in_content_cannot_close_the_fence() -> None:
    """Error text or commands holding ``~~~~`` stay inside the fence."""
    model: JsonValue = loads(
        s=(EXAMPLES / "error_result.json").read_text(encoding="utf-8"),
    )
    if not isinstance(model, dict):
        return
    run: JsonValue = model["run"]
    invocation: JsonValue = model["invocation"]
    if not isinstance(run, dict) or not isinstance(invocation, dict):
        return
    run["error"] = (
        "first\n~~~~text\ninjected heading\n~~~~\nlast\n```python\ncode\n```"
    )
    invocation["command"] = "run --flag ~~~~"
    markdown: str = ReportTemplates.render(
        model=model,
        tool_dir=ReportTemplates.tool_dir(analyzer="lints"),
    ).markdown
    expect_in(member="\n~~~~~text\nfirst\n", container=markdown)
    expect_in(
        member="\n~~~~shell\nrun --flag ~~~~\n~~~~\n",
        container=markdown,
    )
    expect_in(member="injected heading\n~~~~\nlast", container=markdown)


def test_render_adds_a_linked_per_file_resume(tmp_path: Path) -> None:
    """Findings gain anchors and a per-file resume linking to them.

    Args:
        tmp_path: Per-test temporary directory.

    """
    rendered: RenderedReport = ReportTemplates.render(
        model=_example(),
        tool_dir=_tool_dir(
            root=tmp_path,
            mapping={"extra": {"$literal": "x"}},
        ),
    )
    text: str = rendered.markdown
    expect_true(condition=text.index("### By file") < text.index("### F-001"))
    for member in (
        "#### `pkg/a.py`",
        "1 finding — 1 error",
        "- [F-001](#finding-f-001) — error · E722 · line 3",
        "- [F-002](#finding-f-002) — warning · F401 · line 1",
        '<a id="finding-f-001"></a>',
        '<a id="finding-f-003"></a>',
    ):
        expect_in(member=member, container=text)
    expect_not_in(member="file_summary", container=rendered.view)


def test_render_groups_pathless_findings_as_general(tmp_path: Path) -> None:
    """A finding without a path lands in a ``(general)`` resume group.

    Args:
        tmp_path: Per-test temporary directory.

    """
    model: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=_example(),
    )
    findings: JsonValue = model["findings"]
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict) and finding.get("id") == "F-002":
                finding["path"] = None
    text: str = ReportTemplates.render(
        model=model,
        tool_dir=_tool_dir(
            root=tmp_path,
            mapping={"extra": {"$literal": "x"}},
        ),
    ).markdown
    expect_in(member="#### `(general)`", container=text)
    expect_in(
        member="- [F-002](#finding-f-002) — warning · F401",
        container=text,
    )
