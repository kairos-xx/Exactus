# Copyright (c) 2026
"""DOCS renders result.md from its normalized result.json and template."""

from __future__ import annotations

from functools import partial
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_in,
    expect_true,
    fail,
    stamped_markdown,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.models import ToolRunResult
from exactus.tools.docs.core import (
    Config,
    Report,
    Skip,
    Statistics,
    report_data,
)
from exactus.tools.docs.main import main as docs_main
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.render import Constants, ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
GOLDEN: Final[Path] = Path(__file__).resolve().parent / "golden"
TOOL_DIR: Final[Path] = ReportTemplates.tool_dir(analyzer="docs")
SECTIONS: Final[tuple[str, ...]] = (
    "## Identity",
    "## What was checked",
    "### Scope",
    "## Setup",
    "### Invocation",
    "### Environment",
    "## Gate",
    "## Findings",
    "## Artifacts",
    "## Documentation statistics",
    "## Analyzed code",
    "## Rules",
    "## Suggested documentation",
    "\n---\n\nExactus · docs",
)
LEGACY_KEYS: Final[tuple[str, ...]] = (
    "analyzer",
    "status",
    "passed",
    "resume",
    "duration_seconds",
    "sections",
    "web",
    "run_id",
    "title",
    "root",
    "statistics",
)
DOCUMENTED: Final[str] = dedent(
    text=(
        '    """Utilities."""\n    \n    \n    def double(value: int) -> int:'
        '\n        """Double a value.\n    \n        Args:\n            value:'
        " Number to double.\n    \n        Returns:\n            The doubled n"
        'umber.\n    \n        """\n        return value * 2\n    '
    ),
)


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["docs", "."])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _project(*, root: Path) -> None:
    """Create a tiny project with undocumented callables.

    Args:
        root: Project directory.

    """
    (root / "pkg").mkdir(parents=True)
    _ = (root / "pkg" / "util.py").write_text(
        data="def load(path: str) -> str:\n    return path\n",
    )
    _ = (root / "pkg" / "clean.py").write_text(data=DOCUMENTED)
    _ = (root / "pkg" / "excluded.py").write_text(data="x = 1\n")
    _ = (root / "README.md").write_text(data="# Demo\n\nA demo.\n")


def _object(*, path: Path) -> dict[str, JsonValue]:
    """Read one JSON object file.

    Args:
        path: JSON file.

    Returns:
        The decoded object.

    """
    loaded: JsonValue = loads(s=path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        fail(message=f"{path} is not a JSON object")
    return loaded


def _run(*, root: Path, out: Path, extra: tuple[str, ...]) -> ToolRunResult:
    """Run DOCS through ``execute_exactus`` into ``out``.

    Args:
        root: Project directory.
        out: Report directory.
        extra: Additional tool arguments.

    Returns:
        The run result.

    """
    return ent.execute_exactus(
        analyzer="docs",
        title="Docs Exactus",
        main=partial(
            docs_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                "--language",
                "python",
                *extra,
            ),
        ),
        output=out,
    )


def test_golden_result_renders_expected_markdown() -> None:
    """The checked-in result.json renders the checked-in result.md."""
    model: JsonValue = loads(
        s=(GOLDEN / "result.json").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown,
        expected=(GOLDEN / "expected.md").read_text(encoding="utf-8"),
    )


def test_crash_render_shows_error_and_na_blocks() -> None:
    """An envelope-only result renders ERROR with N/A tool blocks."""
    model: JsonValue = loads(
        s=(Constants.common / "examples" / "error_result.json").read_text(
            encoding="utf-8",
        ),
    )
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "| Status | ERROR |",
        "N/A — the tool reported no findings list.",
        "## Documentation statistics\n\nN/A — the tool reported no",
        "## Analyzed code\n\nN/A — the tool reported no per-language",
        "## Rules\n\nN/A — the tool reported no rule counts.",
        "## Suggested documentation\n\nN/A — the tool reported no findings",
    ):
        expect_in(member=member, container=text)


def test_report_data_is_normalized(tmp_path: Path) -> None:
    """``report_data`` returns summary, scope, findings and extension.

    Args:
        tmp_path: Per-test temporary directory.

    """
    config: Config = Config(
        root=tmp_path,
        markdown=tmp_path / "DOCS.md",
        json_output=tmp_path / "DOCS.json",
        languages=frozenset({"python"}),
        exclude_dirs=frozenset({"build"}),
        exclude_hidden_dirs=True,
        public_only=False,
        validate_javascript=False,
        fail_on="error",
        includes=("pkg/**",),
        excludes=("exactus/packages/**",),
    )
    report: Report = Report()
    report.statistics["python"] = Statistics(
        discovered=1,
        parsed=1,
        symbols=2,
        documented=1,
    )
    data: dict[str, JsonValue] = report_data(
        config=config,
        report=report,
        eligible=2,
        skipped=(Skip(target="pkg/old.py", reason="excluded"),),
    )
    expect_equal(
        actual=sorted(data),
        expected=[
            "extension",
            "findings",
            "root",
            "scope",
            "statistics",
            "summary",
        ],
    )
    expect_equal(
        actual=data["summary"],
        expected={
            "targets_eligible": 2,
            "targets_analyzed": 1,
            "findings_total": 0,
            "severity": {},
        },
    )
    expect_equal(actual=data["findings"], expected=[])
    expect_equal(
        actual=dig(document=data, path=("scope", "include")),
        expected=["pkg/**"],
    )
    expect_equal(
        actual=dig(document=data, path=("scope", "exclude")),
        expected=[
            "exactus/packages/**",
            "**/build/**",
            "**/.*/**",
            "**/*.min.js",
        ],
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "languages")),
        expected=[
            {
                "discovered": 1,
                "parsed": 1,
                "failed": 0,
                "symbols": 2,
                "documented": 1,
                "findings": 0,
                "language": "python",
                "coverage_percent": 50.0,
            },
        ],
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "fail_on")),
        expected="error",
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "metrics")),
        expected={
            "languages": [
                {
                    "language": "python",
                    "files_analyzed": 1,
                    "lines_analyzed": 0,
                },
            ],
        },
    )


def test_execute_exactus_renders_docs_from_template(tmp_path: Path) -> None:
    """A real DOCS run writes the normalized report bundle.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DOCS"
    result: ToolRunResult = _run(
        root=root,
        out=out,
        extra=("--exclude", "pkg/excluded.py"),
    )
    expect_equal(actual=result.status, expected="FAIL")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    positions: list[int] = [markdown.index(part) for part in SECTIONS]
    expect_equal(actual=positions, expected=sorted(positions))
    expect_true(condition=markdown.startswith("# Documentation Exactus\n"))
    expect_in(
        member="### DOCS-001 — Missing documentation: load",
        container=markdown,
    )
    payload: dict[str, JsonValue] = _object(path=out / "result.json")
    for key in (*BundleConstants.normalized_blocks, *LEGACY_KEYS):
        expect_in(member=key, container=payload)
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_equal(
        actual=dig(document=payload, path=("tool", "name")),
        expected="docs",
    )
    expect_equal(
        actual=dig(document=payload, path=("summary", "targets_eligible")),
        expected=3,
    )
    expect_equal(
        actual=dig(document=payload, path=("summary", "targets_analyzed")),
        expected=2,
    )
    expect_equal(
        actual=dig(document=payload, path=("statistics", "python", "parsed")),
        expected=2,
    )
    expect_equal(
        actual=dig(document=payload, path=("findings", 0, "code")),
        expected="DOC001",
    )
    expect_in(
        member={"level": 2, "title": "Documentation statistics"},
        container=dig_list(document=payload, path=("sections",)),
    )
    expect_equal(
        actual=stamped_markdown(model=payload, tool_dir=TOOL_DIR, base=out),
        expected=markdown,
    )
    web: dict[str, JsonValue] = _object(path=out / "result_web" / "data.json")
    expect_equal(actual=web["markdown"], expected=markdown)
    expect_equal(
        actual=dig(document=web, path=("view", "gate", "status")),
        expected="FAIL",
    )
    for member in ("## Analyzed code", "| python | 2 | 16 |"):
        expect_in(member=member, container=markdown)
    expect_equal(
        actual=dig(document=web, path=("view", "analyzed_code")),
        expected=[{"language": "python", "files": 2, "lines": 16}],
    )
    expect_equal(
        actual=dig(document=web, path=("view_columns", "analyzed_code")),
        expected=["language", "files", "lines"],
    )
    expect_equal(
        actual=ToolRunResult.from_report(
            payload=payload,
            output=out,
            fallback=result,
        ).tool,
        expected="docs",
    )


def test_clean_docs_run_states_no_findings(tmp_path: Path) -> None:
    """A documented project renders explicit empty-findings text.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    _ = (root / "util.py").write_text(data=DOCUMENTED)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DOCS"
    result: ToolRunResult = _run(root=root, out=out, extra=())
    expect_equal(actual=result.status, expected="PASS")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    for member in (
        "| Status | PASS |",
        "> **Gate: PASS** — No blocking findings",
        "No blocking findings.",
        "## Findings\n\nNo findings.\n",
        "## Suggested documentation\n\nNo suggestions.\n",
        "| python | 1 | 1 | 0 | 2 | 2 | 100.0 | 0 |",
    ):
        expect_in(member=member, container=markdown)


def test_overload_signatures_need_no_docstring(tmp_path: Path) -> None:
    """``@overload`` signatures are exempt from docstring requirements.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    _ = (root / "api.py").write_text(
        data=dedent(
            text=(
                '    """API."""\n'
                "    from typing import overload\n"
                "    \n"
                "    \n"
                "    @overload\n"
                "    def pick(value: int) -> int: ...\n"
                "    @overload\n"
                "    def pick(value: str) -> str: ...\n"
                "    def pick(value: int | str) -> int | str:\n"
                '        """Pick a value.\n'
                "    \n"
                "        Args:\n"
                "            value: Value to pick.\n"
                "    \n"
                "        Returns:\n"
                "            The picked value.\n"
                "    \n"
                '        """\n'
                "        return value\n"
            ),
        ),
    )
    out: Path = tmp_path / "EXACTUS_RESULTS" / "DOCS"
    result: ToolRunResult = _run(root=root, out=out, extra=())
    expect_equal(actual=result.status, expected="PASS")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    for member in (
        "| Status | PASS |",
        "## Findings\n\nNo findings.\n",
        "| python | 1 | 1 | 0 | 2 | 2 | 100.0 | 0 |",
    ):
        expect_in(member=member, container=markdown)
