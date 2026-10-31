# Copyright (c) 2026
"""DOCS reports docstring and JSDoc analysis volume."""

from __future__ import annotations

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_in,
    expect_not_in,
    fail,
    require_type,
)
from exactus.tools.common.cli import match_path
from exactus.tools.docs.core import (
    Config,
    DocumentationExactus,
    Report,
    report_data,
)
from exactus.tools.reports.render import ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        golden: Grouped module constant.
        tool_dir: Grouped module constant.
        doc: Grouped module constant.
        js: Grouped module constant.

    """

    golden: Final[Path] = Path(__file__).resolve().parent / "golden"
    tool_dir: Final[Path] = ReportTemplates.tool_dir(analyzer="docs")
    doc: Final[str] = '"""Module."""\n'
    js: Final[str] = (
        "/** Add. */\nexport function add(a, b) {\n  return a;\n}\n"
    )


def _write(*, root: Path, name: str, text: str) -> None:
    """Write one project file, creating its folder.

    Args:
        root: Project directory.
        name: Root-relative path.
        text: File content.

    """
    path: Path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(data=text)


def _config(
    *,
    root: Path,
    excludes: tuple[str, ...] = (),
    languages: frozenset[str] = frozenset({"python", "javascript"}),
) -> Config:
    """Build a configuration reporting under ``root``.

    Args:
        root: Project directory.
        excludes: Exclude globs.
        languages: Languages to analyze.

    Returns:
        The runtime configuration.

    """
    return Config(
        root=root,
        markdown=root.parent / "out" / "DOCS.md",
        json_output=root.parent / "out" / "DOCS.json",
        languages=frozenset(
            language
            for language in ("python", "javascript")
            if language in languages
        ),
        exclude_dirs=frozenset({"packages", "node_modules"}),
        exclude_hidden_dirs=True,
        public_only=False,
        validate_javascript=False,
        fail_on=None,
        excludes=excludes,
    )


def _metrics(*, root: Path, excludes: tuple[str, ...] = ()) -> object:
    """Run DOCS on a project and read ``extension.metrics``.

    Args:
        root: Project directory.
        excludes: Exclude globs applied to sources and Markdown.

    Returns:
        The decoded metrics block.

    """
    config: Config = _config(root=root, excludes=excludes)

    def keep(path: Path) -> bool:
        """Apply the exclude globs like the command line does.

        Args:
            path: Candidate source file.

        Returns:
            Whether the file is analyzed.

        """
        return match_path(path=path, root=root, includes=(), excludes=excludes)

    _ = DocumentationExactus(config=config, file_filter=keep).run()
    loaded: JsonValue = loads(
        s=(config.markdown.parent / "result.json").read_text(encoding="utf-8"),
    )
    return dig(document=loaded, path=("extension", "metrics"))


def _keys(*, value: object) -> list[str]:
    """List the sorted keys of a decoded JSON object.

    Args:
        value: Decoded JSON value expected to be an object.

    Returns:
        Its keys in sorted order.

    """
    fields: dict[str, object] = cast(
        typ="dict[str, object]",
        val=require_type(value=value, kind=dict),
    )
    return sorted(fields)


def _project(*, root: Path) -> None:
    """Create sources and Markdown files of several sizes.

    Args:
        root: Project directory.

    """
    _write(root=root, name="README.md", text="# Root\n\nIntro.\n")
    _write(root=root, name="app.py", text=Constants.doc + "x = 1\n")
    _write(root=root, name="pkg/mod.py", text=Constants.doc)
    _write(root=root, name="pkg/inner/deep.py", text=Constants.doc)
    _write(root=root, name="pkg/inner/readme.md", text="tiny")
    _write(root=root, name="web/app.js", text=Constants.js)
    _write(root=root, name="exactus/docs/README.md", text="# Docs\n" * 40)
    _write(root=root, name="exactus/docs/guide.md", text="guide\nmore\n")
    _write(root=root, name="exactus/docs/empty.md", text="")


def test_languages_report_files_and_lines(tmp_path: Path) -> None:
    """Each language lists the files and lines of the sources analyzed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    expect_equal(
        actual=dig(document=_metrics(root=root), path=("languages",)),
        expected=[
            {
                "language": "javascript",
                "files_analyzed": 1,
                "lines_analyzed": 4,
            },
            {"language": "python", "files_analyzed": 3, "lines_analyzed": 4},
        ],
    )


def test_failed_and_excluded_sources_are_not_counted(tmp_path: Path) -> None:
    """A syntax error or an excluded file adds neither files nor lines.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    _write(root=root, name="broken.py", text="def (:\n")
    _write(root=root, name="gen/out.py", text=Constants.doc * 10)
    expect_equal(
        actual=dig(
            document=_metrics(root=root, excludes=("gen/**",)),
            path=("languages", 1),
        ),
        expected={
            "language": "python",
            "files_analyzed": 3,
            "lines_analyzed": 4,
        },
    )


def test_legacy_language_table_is_unchanged(tmp_path: Path) -> None:
    """The existing ``languages`` and ``statistics`` keep their keys.

    Args:
        tmp_path: Per-test temporary directory.

    """
    config: Config = _config(root=tmp_path)
    report: Report = Report()
    data: dict[str, JsonValue] = report_data(
        config=config,
        report=report,
        eligible=0,
        skipped=(),
    )
    expected: list[str] = [
        "coverage_percent",
        "discovered",
        "documented",
        "failed",
        "findings",
        "language",
        "parsed",
        "symbols",
    ]
    expect_equal(
        actual=_keys(
            value=dig(document=data, path=("extension", "languages", 0)),
        ),
        expected=expected,
    )
    expect_equal(
        actual=_keys(value=dig(document=data, path=("statistics", "python"))),
        expected=[
            "discovered",
            "documented",
            "failed",
            "findings",
            "parsed",
            "symbols",
        ],
    )


def test_empty_sources_report_zero_code_volume(tmp_path: Path) -> None:
    """``report_data`` with no sources still emits the code metrics block.

    Args:
        tmp_path: Per-test temporary directory.

    """
    data: dict[str, JsonValue] = report_data(
        config=_config(root=tmp_path, languages=frozenset({"python"})),
        report=Report(),
        eligible=0,
        skipped=(),
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "metrics")),
        expected={
            "languages": [
                {
                    "language": "python",
                    "files_analyzed": 0,
                    "lines_analyzed": 0,
                },
            ],
        },
    )


def test_empty_metrics_say_why_nothing_is_listed() -> None:
    """Empty metrics render N/A with a reason in every block."""
    model: JsonValue = loads(
        s=(Constants.golden / "result.json").read_text(encoding="utf-8"),
    )
    if not isinstance(model, dict):
        fail(message="golden result is not an object")
    extension: JsonValue = model["extension"]
    if not isinstance(extension, dict):
        fail(message="golden result has no extension block")
    metrics: JsonValue = {
        "languages": [],
        "markdown": {
            "files": 0,
            "bytes": 0,
            "lines": 0,
            "readme_files": 0,
            "largest_readme": None,
            "smallest_readme": None,
        },
        "directories_without_readme": [],
    }
    extension["metrics"] = metrics
    text: str = ReportTemplates.render(
        model=model,
        tool_dir=Constants.tool_dir,
    ).markdown
    for member in (
        "## Analyzed code\n\nN/A — the tool reported no per-language metrics.",
    ):
        expect_in(member=member, container=text)
    expect_not_in(member="| Largest |", container=text)


def test_missing_metrics_render_na() -> None:
    """A result without ``extension.metrics`` renders N/A blocks."""
    model: JsonValue = loads(
        s=(Constants.golden / "result.json").read_text(encoding="utf-8"),
    )
    if not isinstance(model, dict):
        fail(message="golden result is not an object")
    extension: JsonValue = model["extension"]
    if not isinstance(extension, dict):
        fail(message="golden result has no extension block")
    del extension["metrics"]
    text: str = ReportTemplates.render(
        model=model,
        tool_dir=Constants.tool_dir,
    ).markdown
    for member in (
        "## Analyzed code\n\nN/A — the tool reported no per-language metrics.",
    ):
        expect_in(member=member, container=text)


def test_code_lines_count_line_feeds(tmp_path: Path) -> None:
    """Code lines end at line feeds only, exactly like Markdown lines.

    ``str.splitlines`` would also split at form feeds and Unicode line
    separators, so code and Markdown totals would disagree.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    text: str = '"""Module."""\nx = "a\x0cb\x1cc"\n# d\u2028e'
    _write(root=root, name="mod.py", text=text)
    _write(root=root, name="web/app.js", text="/** A\u2028B */\nlet a;\n")
    _write(root=root, name="notes.md", text=text)
    metrics: object = _metrics(root=root)
    expect_equal(
        actual=dig(document=metrics, path=("languages",)),
        expected=[
            {
                "language": "javascript",
                "files_analyzed": 1,
                "lines_analyzed": 2,
            },
            {"language": "python", "files_analyzed": 1, "lines_analyzed": 3},
        ],
    )
