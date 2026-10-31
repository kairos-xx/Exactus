# Copyright (c) 2026
"""Tests for traceback and failure parsing helpers."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Final, final

from exactus.tests.common.support import expect_equal, expect_none, require
from exactus.tools.coverage_tests.tracebacks import (
    FailureSite,
    NamedFailure,
    NodeTestFailures,
    ProjectPaths,
    PytestTracebacks,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        project_file: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    project_file: Final[str] = (
        "exactus/tests/tools/coverage_tests/test_coverage_tool.py"
    )


def test_relative_returns_posix_path_for_project_file() -> None:
    """An existing project file is returned relative to the root."""
    result: str | None = ProjectPaths.relative(
        root=Constants.root,
        path=str(
            object=Constants.root
            / "exactus"
            / "tools"
            / "coverage_tests"
            / "tracebacks.py",
        ),
    )
    expect_equal(
        actual=result,
        expected="exactus/tools/coverage_tests/tracebacks.py",
    )


def test_relative_accepts_root_relative_path() -> None:
    """A root-relative path is resolved against the root."""
    result: str | None = ProjectPaths.relative(
        root=Constants.root,
        path="exactus/tests/tools/coverage_tests/test_tracebacks.py",
    )
    expect_equal(
        actual=result,
        expected="exactus/tests/tools/coverage_tests/test_tracebacks.py",
    )


def test_relative_rejects_outside_root(tmp_path: Path) -> None:
    """Paths outside the project root are ignored.

    Args:
        tmp_path: Per-test temporary directory.

    """
    result: str | None = ProjectPaths.relative(
        root=tmp_path / "project",
        path=str(object=tmp_path / "outside.txt"),
    )
    expect_none(value=result)


def test_relative_rejects_non_file() -> None:
    """Directories are not treated as files."""
    result: str | None = ProjectPaths.relative(
        root=Constants.root,
        path=str(object=Constants.root / "exactus"),
    )
    expect_none(value=result)


def test_relative_rejects_foreign_parts() -> None:
    """Paths inside installed package directories are ignored."""
    result: str | None = ProjectPaths.relative(
        root=Constants.root,
        path=str(object=Constants.root / "site-packages" / "pkg" / "mod.py"),
    )
    expect_none(value=result)


def test_relative_returns_none_for_unresolvable_path(tmp_path: Path) -> None:
    """A path whose resolution raises is treated as outside the project.

    Args:
        tmp_path: Per-test temporary directory.

    """
    result: str | None = ProjectPaths.relative(
        root=tmp_path,
        path="\x00invalid\x00",
    )
    expect_none(value=result)


def test_relative_rejects_foreign_parts_for_existing_file(
    tmp_path: Path,
) -> None:
    """A file under a foreign directory is still rejected.

    Args:
        tmp_path: Per-test temporary directory.

    """
    foreign: Path = tmp_path / "site-packages" / "pkg"
    foreign.mkdir(parents=True)
    file: Path = foreign / "mod.py"
    file.write_text(data="pass")
    result: str | None = ProjectPaths.relative(
        root=tmp_path,
        path=str(object=file),
    )
    expect_none(value=result)


def test_sections_split_failure_and_error_blocks() -> None:
    """Sections are grouped by their banner kind."""
    text: str = dedent(
        text=(
            "    \n    === FAILURES ===\n    ___ test_one ___\n    frame line"
            "\n    E assertion\n    === ERRORS ===\n    ___ ERROR at setup of "
            "test_two ___\n    setup line\n    E setup error\n    "
        ),
    )
    sections: list[tuple[str, str, list[str]]] = PytestTracebacks.sections(
        text=text,
    )
    expect_equal(actual=len(sections), expected=2)
    expect_equal(actual=sections[0][0], expected="FAILED")
    expect_equal(actual=sections[0][1], expected="test_one")
    expect_equal(actual=sections[1][0], expected="ERROR")
    expect_equal(actual=sections[1][1], expected="ERROR at setup of test_two")


def test_titles_for_failed_node() -> None:
    """Failed nodes map to the section title matching the test name."""
    result: tuple[str, ...] = PytestTracebacks.titles(
        kind="FAILED",
        node="exactus/tests/test_x.py::test_one",
    )
    expect_equal(actual=result, expected=("test_one",))


def test_titles_for_error_node() -> None:
    """Error nodes include setup and teardown variants."""
    result: tuple[str, ...] = PytestTracebacks.titles(
        kind="ERROR",
        node="exactus/tests/test_x.py::test_one",
    )
    expect_equal(
        actual=result,
        expected=(
            "ERROR at setup of test_one",
            "ERROR at teardown of test_one",
            "test_one",
        ),
    )


def test_titles_for_collection_error() -> None:
    """Collection errors use a dedicated title."""
    result: tuple[str, ...] = PytestTracebacks.titles(
        kind="ERROR",
        node="exactus/tests/test_x.py",
    )
    expect_equal(
        actual=result,
        expected=("ERROR collecting exactus/tests/test_x.py",),
    )


def test_reason_prefers_error_line() -> None:
    """The first E line becomes the reason when present."""
    result: str = PytestTracebacks.reason(
        errors=["ValueError: bad"],
        exception="ValueError",
    )
    expect_equal(actual=result, expected="ValueError: bad")


def test_reason_prepends_exception_when_not_in_error() -> None:
    """The exception class is prepended when the E line omits it."""
    result: str = PytestTracebacks.reason(
        errors=["bad value"],
        exception="ValueError",
    )
    expect_equal(actual=result, expected="ValueError: bad value")


def test_reason_falls_back_to_exception_only() -> None:
    """The exception alone is used when no E lines are available."""
    result: str = PytestTracebacks.reason(errors=[], exception="RuntimeError")
    expect_equal(actual=result, expected="RuntimeError")


def test_reason_returns_empty_when_nothing_is_known() -> None:
    """An empty reason is returned with neither errors nor exception."""
    result: str = PytestTracebacks.reason(errors=[], exception=None)
    expect_equal(actual=result, expected="")


def test_site_stops_at_capture_heading() -> None:
    """Lines after a capture heading are ignored for location and reason."""
    lines: list[str] = [
        "path/to/test.py:10: in function",
        "E first",
        "--- Captured stdout ---",
        "captured",
    ]
    site: FailureSite = PytestTracebacks.site(lines=lines, root=Constants.root)
    expect_equal(actual=site.reason, expected="first")


def test_site_skips_unmatched_lines() -> None:
    """Lines that match no pattern are ignored while scanning."""
    lines: list[str] = [
        "path/to/test.py:10: in function",
        "some unmatched text",
        "E failure",
    ]
    site: FailureSite = PytestTracebacks.site(lines=lines, root=Constants.root)
    expect_equal(actual=site.reason, expected="failure")


def test_site_picks_deepest_project_frame() -> None:
    """The deepest frame inside the project is selected."""
    test_file: str = str(
        object=Constants.root
        / "exactus"
        / "tests"
        / "tools"
        / "coverage_tests"
        / "test_tracebacks.py",
    )
    lines: list[str] = [
        "/site-packages/pkg.py:1: in outer",
        f"{test_file}:10: in inner",
        "E failure",
    ]
    site: FailureSite = PytestTracebacks.site(lines=lines, root=Constants.root)
    expect_equal(
        actual=site.path,
        expected="exactus/tests/tools/coverage_tests/test_tracebacks.py",
    )
    expect_equal(actual=site.line, expected=10)


def test_sites_returns_none_for_missing_section() -> None:
    """Entries without a matching section produce a None site."""
    text: str = "\n=== FAILURES ===\n___ present_test ___\nE failure\n"
    sites: tuple[FailureSite | None, ...] = PytestTracebacks.sites(
        text=text,
        root=Constants.root,
        entries=[("FAILED", "exactus/tests/test_x.py::missing_test")],
    )
    expect_equal(actual=len(sites), expected=1)
    expect_none(value=sites[0])


def test_sites_matches_and_pops_sections_in_order() -> None:
    """Each entry consumes its section and later entries may miss."""
    text: str = dedent(
        text=(
            "    \n    === FAILURES ===\n    ___ first_test ___\n    E failure"
            " one\n    ___ second_test ___\n    E failure two\n    "
        ),
    )
    sites: tuple[FailureSite | None, ...] = PytestTracebacks.sites(
        text=text,
        root=Constants.root,
        entries=[
            ("FAILED", "exactus/tests/test_x.py::first_test"),
            ("FAILED", "exactus/tests/test_x.py::second_test"),
            ("FAILED", "exactus/tests/test_x.py::third_test"),
        ],
    )
    expect_equal(actual=len(sites), expected=3)
    expect_equal(actual=sites[0] is not None, expected=True)
    expect_equal(actual=sites[1] is not None, expected=True)
    expect_none(value=sites[2])


def test_frame_path_handles_file_urls() -> None:
    """A file:// URL is decoded and made relative to the root."""
    file_path: Path = Constants.root / Constants.project_file
    url: str = f"file://{file_path}"
    result: str | None = NodeTestFailures.frame_path(
        root=Constants.root,
        raw=url,
    )
    expect_equal(
        actual=result,
        expected="exactus/tests/tools/coverage_tests/test_coverage_tool.py",
    )


def test_frame_path_handles_plain_paths() -> None:
    """A plain absolute path is made relative to the root."""
    file_path: Path = Constants.root / Constants.project_file
    result: str | None = NodeTestFailures.frame_path(
        root=Constants.root,
        raw=str(object=file_path),
    )
    expect_equal(
        actual=result,
        expected="exactus/tests/tools/coverage_tests/test_coverage_tool.py",
    )


def test_entry_returns_none_without_test_at() -> None:
    """A group that does not start with a test-at line is ignored."""
    result: NamedFailure | None = NodeTestFailures.entry(
        lines=["not a test at line"],
        root=Constants.root,
    )
    expect_none(value=result)


def test_entry_reads_name_reason_and_frame() -> None:
    """A normal Node spec failure entry is parsed."""
    test_path: str = str(object=Constants.root / Constants.project_file)
    lines: list[str] = [
        f"test at {test_path}:5:10",
        "✖ failing test (1.2ms)",
        "AssertionError: expected true",
        f"    at Object.<anonymous> ({test_path}:8:10)",
    ]
    result: NamedFailure | None = NodeTestFailures.entry(
        lines=lines,
        root=Constants.root,
    )
    failure: NamedFailure = require(value=result)
    expect_equal(actual=failure.name, expected="failing test")
    expect_equal(
        actual=failure.site.path,
        expected="exactus/tests/tools/coverage_tests/test_coverage_tool.py",
    )
    expect_equal(actual=failure.site.line, expected=8)
    expect_equal(
        actual=failure.site.reason,
        expected="AssertionError: expected true",
    )


def test_entry_uses_test_location_when_no_project_frame() -> None:
    """The test-at location is used when no stack frame maps to the project."""
    lines: list[str] = [
        "test at file:///site-packages/pkg/mod.test.js:5:10",
        "✖ external test",
        "Error: boom",
    ]
    result: NamedFailure | None = NodeTestFailures.entry(
        lines=lines,
        root=Constants.root,
    )
    failure: NamedFailure = require(value=result)
    expect_equal(actual=failure.name, expected="external test")
    expect_none(value=failure.site.path)


def test_parse_returns_empty_when_no_banner() -> None:
    """Output without a failing-tests banner yields no failures."""
    result: tuple[NamedFailure, ...] = NodeTestFailures.parse(
        text="some unrelated output",
        root=Constants.root,
    )
    expect_equal(actual=result, expected=())


def test_parse_collects_multiple_failures() -> None:
    """Every test-at group after the banner becomes one failure."""
    test_path: str = str(object=Constants.root / Constants.project_file)
    text: str = (
        f"✖ failing tests:\ntest at {test_path}:1:1\n✖ first\nError: first"
        f" failure\ntest at {test_path}:2:1\n✖ second\nError: second failure\n"
    )
    result: tuple[NamedFailure, ...] = NodeTestFailures.parse(
        text=text,
        root=Constants.root,
    )
    expect_equal(actual=len(result), expected=2)
    expect_equal(actual=result[0].name, expected="first")
    expect_equal(actual=result[1].name, expected="second")


def test_entry_prefers_first_project_frame() -> None:
    """Only the first project frame updates the location."""
    test_path: str = str(object=Constants.root / Constants.project_file)
    other_path: str = str(
        object=Constants.root / "exactus" / "tests" / "common" / "support.py",
    )
    lines: list[str] = [
        f"test at {test_path}:1:1",
        "✖ frame order",
        f"    at Object.<anonymous> ({other_path}:3:3)",
        f"    at Object.<anonymous> ({test_path}:9:9)",
    ]
    result: NamedFailure | None = NodeTestFailures.entry(
        lines=lines,
        root=Constants.root,
    )
    failure: NamedFailure = require(value=result)
    expect_equal(
        actual=failure.site.path,
        expected="exactus/tests/common/support.py",
    )
    expect_equal(actual=failure.site.line, expected=3)
