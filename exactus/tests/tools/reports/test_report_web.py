# Copyright (c) 2026
"""The web bundle carries the view model that renders ``result.md``."""

from __future__ import annotations

from functools import partial
from json import loads
from shutil import copytree
from typing import TYPE_CHECKING, Final, NoReturn, final

import pytest

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    fail,
    private_call,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.envelope import RunFacts
from exactus.tools.readme.main import main as readme_main
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.reports.render import (
    NormalizedStamp,
    RenderedReport,
    ReportTemplates,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        base_view_keys: Grouped module constant.
        data_js_prefix: Grouped module constant.

    """

    base_view_keys: Final[frozenset[str]] = frozenset(
        {
            "artifacts",
            "blocking",
            "environment",
            "extension",
            "findings",
            "gate",
            "invocation",
            "run",
            "scope",
            "severity_levels",
            "summary",
            "tool",
        },
    )
    data_js_prefix: Final[str] = "window.__REPORT_DATA__ = "


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["readme", "."])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _object(*, text: str) -> dict[str, JsonValue]:
    """Decode one JSON object document.

    Args:
        text: JSON text.

    Returns:
        The decoded object.

    """
    loaded: JsonValue = loads(s=text)
    if not isinstance(loaded, dict):
        fail(message="document is not a JSON object")
    return loaded


def _data_js(*, web: Path) -> dict[str, JsonValue]:
    """Decode the payload inlined in ``data.js``.

    Args:
        web: Web bundle directory.

    Returns:
        The ``window.__REPORT_DATA__`` object.

    """
    text: str = (web / BundleConstants.data_js_name).read_text(
        encoding="utf-8",
    )
    expect_true(condition=text.startswith(Constants.data_js_prefix))
    expect_true(condition=text.endswith(";\n"))
    argument: str = (
        text.removeprefix(Constants.data_js_prefix)
        .removesuffix(";\n")
        .removeprefix("JSON.parse(`")
        .removesuffix("`)")
    )
    document: str = (
        argument.replace("\\${", "${")
        .replace("\\`", "`")
        .replace("\\\\", "\\")
    )
    return _object(text=document)


def _readme_bundle(*, root: Path, out: Path) -> None:
    """Run README over a tiny project with inventory findings.

    Args:
        root: Project directory.
        out: Report directory.

    """
    (root / "docs" / "guides").mkdir(parents=True)
    _ = (root / "docs" / "README.md").write_text(data="`a.md`\n")
    _ = (root / "docs" / "a.md").write_text(data="a\n")
    _ = (root / "docs" / "b.md").write_text(data="b\n")
    _ = ent.execute_exactus(
        analyzer="readme",
        title="Readme Exactus",
        main=partial(
            readme_main,
            arguments=(str(object=root), "--output-dir", str(object=out)),
        ),
        output=out,
    )


def test_migrated_web_data_carries_the_markdown_view(tmp_path: Path) -> None:
    """``data.js`` inlines the view model ``result.md`` was rendered from.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "README"
    _readme_bundle(root=tmp_path / "project", out=out)
    web: Path = out / "result_web"
    inlined: dict[str, JsonValue] = _data_js(web=web)
    expect_equal(
        actual=inlined,
        expected=_object(
            text=(web / BundleConstants.data_name).read_text(encoding="utf-8"),
        ),
    )
    payload: dict[str, JsonValue] = _object(
        text=(out / "result.json").read_text(encoding="utf-8"),
    )
    rendered: RenderedReport = ReportTemplates.render(
        model=payload,
        tool_dir=ReportTemplates.tool_dir(analyzer="readme"),
    )
    expect_equal(actual=inlined["view"], expected=rendered.view)
    expect_equal(
        actual=inlined["markdown"],
        expected=(out / "result.md").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=ReportBundle.link_paths(
            markdown=rendered.markdown,
            base=out,
            root=tmp_path / "project",
        ),
        expected=inlined["markdown"],
    )
    expect_in(
        member="[ARTIFACTS/stdout.log](ARTIFACTS/stdout.log)",
        container=str(object=inlined["markdown"]),
    )
    view: JsonValue = inlined["view"]
    if not isinstance(view, dict):
        fail(message="view is not an object")
    expect_true(condition=frozenset(view) >= Constants.base_view_keys)
    expect_in(member="inventory", container=view)
    expect_not_in(member="source", container=view)
    columns: JsonValue = inlined["view_columns"]
    if not isinstance(columns, dict):
        fail(message="view_columns is not an object")
    expect_equal(
        actual=columns["inventory"],
        expected=[
            "directory",
            "readme",
            "bytes",
            "entries",
            "documented",
            "missing",
        ],
    )
    expect_equal(
        actual=columns["artifacts"],
        expected=["name", "path", "bytes"],
    )
    expect_equal(actual=inlined["view_order"], expected=list(rendered.view))
    stripped: dict[str, JsonValue] = {
        key: value
        for key, value in inlined.items()
        if key
        not in {
            "markdown",
            "view",
            "view_columns",
            "view_order",
            "local_links",
        }
    }
    expect_equal(actual=stripped, expected=payload)
    expect_equal(
        actual=dig(
            document=inlined,
            path=("local_links", "ARTIFACTS/stdout.log"),
        ),
        expected="ARTIFACTS/stdout.log",
    )


def test_columns_follow_first_seen_row_keys() -> None:
    """Only list-of-object blocks get a column order, in first-seen order."""
    expect_equal(
        actual=ReportTemplates.columns(
            view={
                "rules": [
                    {"rule": "R1", "title": "One"},
                    {"rule": "R2", "count": 2, "title": "Two"},
                ],
                "levels": ["error", "warning"],
                "empty": [],
                "gate": {"status": "PASS"},
                "mixed": [1, {"name": "x"}],
            },
        ),
        expected={"rules": ["rule", "title", "count"], "mixed": ["name"]},
    )


def _facts(*, output: Path, cwd: Path) -> RunFacts:
    """Build run facts for the unmigrated ``frontend`` tool.

    Args:
        output: Report directory.
        cwd: Working directory recorded in the facts.

    Returns:
        Facts of a passing run.

    """
    return RunFacts(
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
        cwd=str(object=cwd),
        arguments=(),
        output=output,
    )


def test_unmigrated_web_data_has_no_view(tmp_path: Path) -> None:
    """An unmigrated tool's web data keeps the legacy shape.

    Args:
        tmp_path: Per-test temporary directory.

    """
    legacy: Path = tmp_path / "legacy"
    _ = ReportBundle.write(
        paths=ReportPaths(
            markdown=legacy / "result.md",
            json=legacy / "result.json",
            web=legacy / "result_web",
        ),
        analyzer="frontend",
        title="Screenshot Report",
        markdown="# Screenshot Report\n\n## Findings\n\nNone.\n",
        data={"findings": [], "summary": {"files": 1}},
    )
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
        facts=_facts(output=stamped, cwd=tmp_path),
    )
    plain: dict[str, JsonValue] = _data_js(web=legacy / "result_web")
    with_facts: dict[str, JsonValue] = _data_js(web=stamped / "result_web")
    for key in ("view", "view_columns", "view_order"):
        expect_not_in(member=key, container=with_facts)
    expect_equal(actual=with_facts, expected=plain)


class _RaiseAfterReport:
    """Tool main that writes its report and then raises."""

    def __init__(self, *, root: Path, out: Path) -> None:
        """Remember the project and report directories.

        Args:
            root: Project directory.
            out: Report directory.

        """
        self.root: Path = root
        self.out: Path = out

    def __call__(self) -> NoReturn:
        """Run README, then fail.

        Raises:
            RuntimeError: Always, after the report was written.

        """
        _ = readme_main(
            arguments=(
                str(object=self.root),
                "--output-dir",
                str(object=self.out),
            ),
        )
        msg: str = "boom after the report"
        raise RuntimeError(msg)


class _FailingWrite:
    """Stand-in for a web data writer whose disk write fails."""

    def __call__(self, *positional: object, **arguments: object) -> None:
        """Fail like a full disk.

        Args:
            *positional: Ignored positional arguments.
            **arguments: Ignored keyword arguments.

        Raises:
            OSError: Always.

        """
        del positional, arguments
        msg: str = "disk full"
        raise OSError(msg)


def test_error_after_report_is_kept(tmp_path: Path) -> None:
    """A tool raising after writing its report keeps the traceback.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    out: Path = tmp_path / "EXACTUS_RESULTS" / "README"
    (root / "docs").mkdir(parents=True)
    _ = (root / "docs" / "README.md").write_text(data="docs\n")
    _ = ent.execute_exactus(
        analyzer="readme",
        title="Readme Exactus",
        main=_RaiseAfterReport(root=root, out=out),
        output=out,
    )
    payload: dict[str, JsonValue] = _object(
        text=(out / "result.json").read_text(encoding="utf-8"),
    )
    error: object = dig(document=payload, path=("run", "error"))
    if not isinstance(error, str):
        fail(message="run.error is not text")
    expect_in(member="RuntimeError: boom after the report", container=error)
    expect_in(member="Traceback", container=error)
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_in(member="The tool raised an error:", container=markdown)
    expect_in(member="RuntimeError: boom after the report", container=markdown)


def test_web_write_failure_keeps_the_normalized_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed web data write never lets legacy stamps rewrite result.md.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=NormalizedStamp,
        name="_web",
        value=_FailingWrite(),
    )
    out: Path = tmp_path / "EXACTUS_RESULTS" / "README"
    _readme_bundle(root=tmp_path / "project", out=out)
    payload: dict[str, JsonValue] = _object(
        text=(out / "result.json").read_text(encoding="utf-8"),
    )
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_equal(
        actual=markdown,
        expected=ReportBundle.link_paths(
            markdown=ReportTemplates.render(
                model=payload,
                tool_dir=ReportTemplates.tool_dir(analyzer="readme"),
            ).markdown,
            base=out,
            root=tmp_path / "project",
        ),
    )
    expect_not_in(member="- Status: **", container=markdown)
