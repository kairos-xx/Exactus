# Copyright (c) 2026
"""Visual-cause runs against real pages through Chromium."""

from __future__ import annotations

from json import loads
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import expect_equal, expect_in, expect_true
from exactus.tools.visual_cause.arguments import create_parser
from exactus.tools.visual_cause.core import (
    VisualCauseRequest,
    VisualCauseResult,
    run,
)
from exactus.tools.visual_cause.main import main
from exactus.tools.visual_cause.queries import (
    QueryConfig,
    QueryResult,
    QuerySession,
    QuerySyntaxError,
)
from exactus.tools.visual_cause.targets import Target, TargetOptions, resolve

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        page: Grouped module constant.
        side_a: Grouped module constant.
        side_b: Grouped module constant.
        fast: Grouped module constant.

    """

    page: Final[str] = (
        '<!doctype html><html><head><meta charset="utf-8"><title>P<'
        "/title><style>body{margin:0}</style></head><body><main><div "
        'id="box">A</div><p class="note">Hi</p></main></body></html>'
    )
    side_a: Final[str] = "#box{width:80px;height:40px;background:#08f}"
    side_b: Final[str] = "#box{width:120px;height:40px;background:#08f}"
    fast: Final[tuple[str, ...]] = (
        "--viewport",
        "320x200",
        "--max-candidates",
        "5",
        "--parallel-workers",
        "1",
        "--timeout-ms",
        "20000",
    )


def _site(*, root: Path) -> Path:
    """Write a one-page site and two stylesheets under ``root``.

    Args:
        root: Directory to populate.

    Returns:
        The directory holding ``index.html`` and the stylesheets.

    """
    root.mkdir(parents=True, exist_ok=True)
    _ = (root / "index.html").write_text(data=Constants.page, encoding="utf-8")
    _ = (root / "a.css").write_text(data=Constants.side_a, encoding="utf-8")
    _ = (root / "b.css").write_text(data=Constants.side_b, encoding="utf-8")
    return root


def _targets(*, root: Path, flags: tuple[str, ...]) -> tuple[Target, ...]:
    """Resolve targets for a site with the fast render settings.

    Args:
        root: Project root and site directory.
        flags: Source and verdict flags.

    Returns:
        Validated targets.

    """
    options: TargetOptions = cast(
        typ="TargetOptions",
        val=create_parser().parse_args(
            args=[str(object=root), *Constants.fast, *flags],
        ),
    )
    return resolve(options=options)


def _session(*, page: Path, css: str, native: bool) -> QuerySession:
    """Build a query session for one local page.

    Args:
        page: Page file to open.
        css: Stylesheet injected after load.
        native: Whether the page keeps its own styles.

    Returns:
        A closed session ready to be entered.

    """
    return QuerySession(
        config=QueryConfig(
            url=page.as_uri(),
            width=320,
            height=200,
            timeout_ms=20000,
            css=css,
            native_styles=native,
        ),
    )


def test_session_queries_and_best_selectors(tmp_path: Path) -> None:
    """A session lints, matches and produces selectors for page elements.

    Args:
        tmp_path: Per-test directory.

    """
    page: Path = _site(root=tmp_path) / "index.html"
    session: QuerySession = _session(
        page=page,
        css=Constants.side_b,
        native=True,
    )
    with pytest.raises(expected_exception=RuntimeError, match="not open"):
        _ = session.page
    with session as opened:
        expect_equal(actual=opened.lint(query="#box"), expected=())
        expect_true(condition=bool(opened.lint(query="??(")))
        expect_equal(
            actual=opened.matching(css_path="#box", query="#box"),
            expected=(True, 1),
        )
        expect_equal(
            actual=opened.matching(css_path="#box", query="p"),
            expected=(False, 1),
        )
        expect_equal(
            actual=opened.matching(css_path="#missing", query="p"),
            expected=(False, 0),
        )
        best: QueryResult = opened.best(css_path="#box")
        expect_in(member="box", container=best.query)
        absent: QueryResult = opened.best(css_path="#missing")
        expect_equal(actual=absent.query, expected="#missing")
        expect_equal(actual=absent.candidates, expected=())
        width: object = opened.page.evaluate(
            expression="document.querySelector('#box').offsetWidth",
        )
        expect_equal(actual=width, expected=120)


def test_session_can_drop_native_styles(tmp_path: Path) -> None:
    """Without native styles the page's own stylesheets are removed.

    Args:
        tmp_path: Per-test directory.

    """
    page: Path = _site(root=tmp_path) / "index.html"
    with _session(page=page, css="", native=False) as opened:
        count: object = opened.page.evaluate(
            expression="document.querySelectorAll('style').length",
        )
    expect_equal(actual=count, expected=0)


def test_run_reports_changed_elements_by_level(tmp_path: Path) -> None:
    """A stylesheet comparison yields findings decided by the queries.

    Args:
        tmp_path: Per-test directory.

    """
    site: Path = _site(root=tmp_path / "site")
    targets: tuple[Target, ...] = _targets(
        root=tmp_path,
        flags=(
            "--html",
            str(object=site / "index.html"),
            "--css-a",
            str(object=site / "a.css"),
            "--css-b",
            str(object=site / "b.css"),
            "--fail",
            "#box",
            "--accept",
            "p",
            "--default-level",
            "warning",
        ),
    )
    result: VisualCauseResult = run(
        request=VisualCauseRequest(targets=targets, output=tmp_path / "out"),
    )
    expect_true(condition=result.failed)
    expect_equal(actual=len(result.targets), expected=1)
    levels: dict[str, str] = {
        item.css_path: item.level for item in result.findings
    }
    expect_in(member="fail", container=tuple(levels.values()))
    expect_true(condition=result.targets[0].changed_pixels > 0)
    expect_true(condition=bool(result.queries))
    expect_in(member="a", container=result.targets[0].artifacts)
    expect_true(
        condition=(
            tmp_path / "out" / result.targets[0].artifacts["diff"]
        ).is_file(),
    )


def test_run_overlay_directory_css_and_pixel_gate(tmp_path: Path) -> None:
    """A css-b directory overlays one page; the pixel gate can fail it.

    Args:
        tmp_path: Per-test directory.

    """
    site: Path = _site(root=tmp_path / "site")
    sheets: Path = tmp_path / "sheets"
    sheets.mkdir()
    _ = (sheets / "one.css").write_text(
        data="#box{width:200px;height:40px;background:#f80}",
        encoding="utf-8",
    )
    targets: tuple[Target, ...] = _targets(
        root=tmp_path,
        flags=(
            "--html",
            str(object=site / "index.html"),
            "--css-b",
            str(object=sheets),
            "--accept",
            "#box",
            "--fail-on",
            "pixels",
        ),
    )
    expect_equal(actual=targets[0].mode, expected="overlay")
    result: VisualCauseResult = run(
        request=VisualCauseRequest(targets=targets, output=tmp_path / "out"),
    )
    expect_true(condition=result.failed)
    expect_in(
        member="accept",
        container=tuple(item.level for item in result.findings),
    )


def test_run_reports_unreadable_sources_as_target_errors(
    tmp_path: Path,
) -> None:
    """A missing stylesheet becomes a failing target-level finding.

    Args:
        tmp_path: Per-test directory.

    """
    site: Path = _site(root=tmp_path / "site")
    targets: tuple[Target, ...] = _targets(
        root=tmp_path,
        flags=(
            "--html",
            str(object=site / "index.html"),
            "--css-b",
            str(object=tmp_path / "missing.css"),
        ),
    )
    result: VisualCauseResult = run(
        request=VisualCauseRequest(targets=targets, output=tmp_path / "out"),
    )
    expect_true(condition=result.failed)
    expect_equal(actual=result.findings[0].rule, expected="VCS900")
    expect_equal(actual=result.targets, expected=())


def test_invalid_level_query_raises(tmp_path: Path) -> None:
    """A level query the engine cannot parse aborts the run.

    Args:
        tmp_path: Per-test directory.

    """
    site: Path = _site(root=tmp_path / "site")
    targets: tuple[Target, ...] = _targets(
        root=tmp_path,
        flags=(
            "--html",
            str(object=site / "index.html"),
            "--css-b",
            str(object=site / "b.css"),
            "--fail",
            "??(",
        ),
    )
    with pytest.raises(expected_exception=QuerySyntaxError):
        _ = run(
            request=VisualCauseRequest(
                targets=targets,
                output=tmp_path / "out",
            ),
        )


def test_main_writes_the_report_bundle(tmp_path: Path) -> None:
    """The command compares, writes the bundle and returns the gate status.

    Args:
        tmp_path: Per-test directory.

    """
    site: Path = _site(root=tmp_path / "site")
    out: Path = tmp_path / "out"
    status: int = main(
        arguments=(
            str(object=tmp_path),
            "--html",
            str(object=site / "index.html"),
            "--css-a",
            str(object=site / "a.css"),
            "--css-b",
            str(object=site / "b.css"),
            "--fail",
            "#box",
            *Constants.fast,
            "-o",
            str(object=out),
        ),
    )
    expect_equal(actual=status, expected=1)
    payload: dict[str, object] = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_true(condition=(out / "result.md").is_file())


def test_main_rejects_bad_arguments_and_queries(tmp_path: Path) -> None:
    """Invalid targets and queries end the command with a usage error.

    Args:
        tmp_path: Per-test directory.

    """
    with pytest.raises(expected_exception=SystemExit):
        _ = main(arguments=(str(object=tmp_path), "--url", "http://a/"))
    site: Path = _site(root=tmp_path / "site")
    with pytest.raises(expected_exception=SystemExit):
        _ = main(
            arguments=(
                str(object=tmp_path),
                "--html",
                str(object=site / "index.html"),
                "--css-b",
                str(object=site / "b.css"),
                "--fail",
                "??(",
                *Constants.fast,
                "-o",
                str(object=tmp_path / "out"),
            ),
        )
