# Copyright (c) 2026
"""README renders result.md from its normalized result.json and template."""

from __future__ import annotations

from functools import partial
from json import loads
from pathlib import Path
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
from exactus.tools.readme.core import (
    ReadmeExactusInput,
    ReadmeExactusResult,
    readme,
    report_data,
)
from exactus.tools.readme.main import main as readme_main
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.render import Constants, ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
GOLDEN: Final[Path] = Path(__file__).resolve().parent / "golden"
TOOL_DIR: Final[Path] = ReportTemplates.tool_dir(analyzer="readme")
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
    "## Directory inventory",
    "## Rules",
    "\n---\n\nExactus · readme",
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
    "directories",
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
    monkeypatch.setattr(target=ent, name="argv", value=["readme", "."])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _project(*, root: Path) -> None:
    """Create a tiny project with one finding of each inventory rule.

    Args:
        root: Project directory.

    """
    (root / "docs" / "guides").mkdir(parents=True)
    _ = (root / "docs" / "README.md").write_text(data="`a.md`\n")
    _ = (root / "docs" / "a.md").write_text(data="a\n")
    _ = (root / "docs" / "b.md").write_text(data="b\n")


def _clean_project(*, root: Path) -> None:
    """Create a tiny project whose README documents everything.

    Args:
        root: Project directory.

    """
    (root / "docs").mkdir(parents=True)
    _ = (root / "docs" / "README.md").write_text(data="`a.md`\n")
    _ = (root / "docs" / "a.md").write_text(data="a\n")


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


def _run(
    *,
    root: Path,
    out: Path,
    flags: tuple[str, ...] = (),
) -> ToolRunResult:
    """Run README through ``execute_exactus`` into ``out``.

    Args:
        root: Project directory.
        out: Report directory.
        flags: Additional README analyzer flags.

    Returns:
        The run result.

    """
    return ent.execute_exactus(
        analyzer="readme",
        title="Readme Exactus",
        main=partial(
            readme_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                *flags,
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
        "## Directory inventory\n\nN/A — the tool reported no directory",
        "## Rules\n\nN/A — the tool reported no rule counts.",
    ):
        expect_in(member=member, container=text)


def test_report_data_is_normalized(tmp_path: Path) -> None:
    """``report_data`` returns summary, scope, findings and extension.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    (root / "docs" / "archive").mkdir()
    _ = (root / "docs" / "README.md").write_text(data="`a.md` `archive/`\n")
    result: ReadmeExactusResult = readme(
        inputs=ReadmeExactusInput(
            root=root,
            includes=(),
            excludes=("docs/archive",),
        ),
    )
    data: dict[str, JsonValue] = report_data(result=result)
    expect_equal(
        actual=sorted(data),
        expected=["directories", "extension", "findings", "scope", "summary"],
    )
    expect_equal(
        actual=data["summary"],
        expected={
            "targets_eligible": 3,
            "targets_analyzed": 2,
            "findings_total": 3,
            "severity": {"error": 3},
            "directories": 2,
            "findings": 3,
            "by_rule": {"RDM001": 1, "RDM002": 1, "RDM003": 1},
        },
    )
    expect_equal(
        actual=dig(document=data, path=("scope", "skipped")),
        expected=[
            {
                "target": "docs/archive",
                "reason": "excluded by include/exclude rules",
            },
        ],
    )
    expect_equal(
        actual=[
            dig(document=data, path=("findings", index, "id"))
            for index in range(3)
        ],
        expected=["README-001", "README-002", "README-003"],
    )
    expect_equal(
        actual=dig(document=data, path=("findings", 0)),
        expected={
            "id": "README-001",
            "title": "Missing README.md",
            "severity": "error",
            "rule": "RDM001",
            "path": "docs/guides",
            "file": "docs/guides",
            "line": 0,
            "message": "missing README.md",
            "blocking": True,
        },
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "directories", 0)),
        expected={
            "path": "docs",
            "has_readme": True,
            "readme_bytes": 18,
            "entries": 4,
            "documented": 2,
            "missing": 2,
        },
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "directories", 1)),
        expected={
            "path": "docs/guides",
            "has_readme": False,
            "readme_bytes": 0,
            "entries": 0,
            "documented": 0,
            "missing": 0,
        },
    )


def test_execute_exactus_renders_readme_from_template(tmp_path: Path) -> None:
    """A real README run writes the normalized report bundle.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "README"
    result: ToolRunResult = _run(root=root, out=out, flags=("--dry",))
    expect_equal(actual=result.status, expected="FAIL")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    positions: list[int] = [markdown.index(part) for part in SECTIONS]
    expect_equal(actual=positions, expected=sorted(positions))
    expect_true(condition=markdown.startswith("# README Exactus\n"))
    expect_in(
        member="> **Gate: FAIL** — 3 blocking findings",
        container=markdown,
    )
    expect_in(
        member=(
            "| [docs/guides](../../project/docs/guides) | missing | "
            "0 | 0 | 0 | 0 |"
        ),
        container=markdown,
    )
    payload: dict[str, JsonValue] = _object(path=out / "result.json")
    for key in (*BundleConstants.normalized_blocks, *LEGACY_KEYS):
        expect_in(member=key, container=payload)
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_equal(
        actual=dig(document=payload, path=("tool", "name")),
        expected="readme",
    )
    expect_equal(
        actual=dig(document=payload, path=("summary", "by_rule")),
        expected={"RDM001": 1, "RDM002": 1, "RDM003": 1},
    )
    expect_equal(
        actual=payload["directories"],
        expected=["docs", "docs/guides"],
    )
    expect_in(
        member={"level": 2, "title": "Directory inventory"},
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
    expect_equal(
        actual=ToolRunResult.from_report(
            payload=payload,
            output=out,
            fallback=result,
        ).tool,
        expected="readme",
    )


def test_clean_readme_run_states_no_findings(tmp_path: Path) -> None:
    """A fully documented project renders explicit empty-findings text.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _clean_project(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "README"
    expect_equal(actual=_run(root=root, out=out).status, expected="PASS")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    readme_bytes: int = (root / "docs" / "README.md").stat().st_size
    for member in (
        "| Status | PASS |",
        "> **Gate: PASS** — No blocking findings",
        "No blocking findings.",
        "## Findings\n\nNo findings.\n",
        f"| docs | present | {readme_bytes} | 1 | 1 | 0 |",
    ):
        expect_in(member=member, container=markdown)
