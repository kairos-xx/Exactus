# Copyright (c) 2026
"""LINTS renders result.md and its web view from normalized data."""

from __future__ import annotations

from functools import partial
from json import loads
from pathlib import Path
from sys import executable
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    fail,
    private_call,
    require_type,
    stamped_markdown,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.snippets import with_excerpts
from exactus.tools.lints import core as lints_core
from exactus.tools.lints.core import CommandResult, LintExactus
from exactus.tools.lints.main import main as lints_main
from exactus.tools.lints.report import (
    finding_title,
    linter_status,
    relative_path,
    report_data,
)
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.render import Constants, ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult
GOLDEN: Final[Path] = Path(__file__).resolve().parent / "golden"
TOOL_DIR: Final[Path] = ReportTemplates.tool_dir(analyzer="lints")
APP: Final[str] = dedent(
    text=(
        '    """Demo application."""\n    \n    import os\n    LIMIT = 3\n    '
        '\n    \n    def load(path):\n        """Load one file."""\n        re'
        "turn open(path).read()\n    \n    \n    print(os.sep, LIMIT)\n    "
    ),
)
SCRIPT: Final[str] = (
    'const box = document.querySelector("#box");\nbox.style.color = "red";\n'
)
COMMANDS: Final[tuple[str, ...]] = (
    "ruff",
    "basedpyright",
    "pyrefly",
    "eslint",
    "tsc",
    "stylelint",
    "htmlhint",
    "prettier",
)


def write_sources(*, root: Path) -> None:
    """Write the two project files the fake findings point into.

    Args:
        root: Project directory.

    """
    (root / "pkg").mkdir(parents=True, exist_ok=True)
    (root / "web").mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(data="[tool.ruff]\n")
    _ = (root / "pkg" / "app.py").write_text(data=APP, encoding="utf-8")
    _ = (root / "web" / "app.js").write_text(data=SCRIPT, encoding="utf-8")


def _lint(
    *,
    origin: tuple[str, str, str],
    file: str,
    position: tuple[int, int],
    message: str,
) -> dict[str, JsonValue]:
    """Build one legacy lint finding.

    Args:
        origin: Producing linter, rule identifier and severity.
        file: File name as the linter reports it.
        position: One-based line and column.
        message: Linter message.

    Returns:
        The legacy finding.

    """
    tool: str
    rule: str
    severity: str
    line: int
    column: int
    tool, rule, severity = origin
    line, column = position
    return {
        "tool": tool,
        "file": file,
        "rule": rule,
        "severity": severity,
        "message": message,
        "line": line,
        "column": column,
        "end_line": line,
        "end_column": column,
    }


def _entry(
    *,
    tool: str,
    returncode: int,
    findings: list[JsonValue],
    version: str | None,
) -> dict[str, JsonValue]:
    """Build one legacy ``tools`` entry of a linter that ran.

    Args:
        tool: Linter name.
        returncode: Exit code.
        findings: Its findings.
        version: Probed version, if any.

    Returns:
        The legacy entry.

    """
    entry: dict[str, JsonValue] = {
        "tool": tool,
        "command": [] if version is None else [tool],
        "returncode": returncode,
        "stderr": "",
        "count": len(findings),
        "findings": findings,
        "duration_seconds": 0.25,
    }
    if version is not None:
        entry["version"] = version
    return entry


def fake_report(*, root: Path) -> dict[str, JsonValue]:
    """Return a legacy ``LintExactus.run`` payload without running linters.

    Ruff (exit 1, warnings only) and BasedPyright (exit 1, one error,
    one warning) fail; the built-in checkers, Pyrefly, ESLint (one
    ignored file) and TypeScript pass; Stylelint is not installed and
    HTMLHint had no files.

    Args:
        root: Project root; Ruff, BasedPyright, ESLint and the built-in
            checkers report absolute names under it.

    Returns:
        The legacy payload.

    """
    app: str = str(object=root / "pkg" / "app.py")
    script: str = str(object=root / "web" / "app.js")
    custom_python: list[JsonValue] = [
        _lint(
            origin=("custom_python", "PY002", "warning"),
            file=app,
            position=(4, 1),
            message=(
                "Module global `LIMIT` is uppercase but is not declared "
                "Final. Use an immutable constant or move mutable state to "
                "an explicit instance dependency."
            ),
        ),
    ]
    custom_javascript: list[JsonValue] = [
        _lint(
            origin=("custom_javascript", "JS005", "warning"),
            file=script,
            position=(2, 1),
            message="Static inline style `color` is assigned directly.",
        ),
    ]
    ruff: list[JsonValue] = [
        _lint(
            origin=("ruff", "ANN001", "warning"),
            file=app,
            position=(7, 10),
            message="Missing type annotation for function argument `path`",
        ),
        _lint(
            origin=("ruff", "PTH123", "warning"),
            file=app,
            position=(9, 12),
            message="`open()` should be replaced by `Path.open()`",
        ),
        _lint(
            origin=("ruff", "SIM115", "warning"),
            file=app,
            position=(9, 12),
            message="Use a context manager for opening files",
        ),
    ]
    basedpyright: list[JsonValue] = [
        _lint(
            origin=("basedpyright", "reportMissingParameterType", "error"),
            file=app,
            position=(7, 10),
            message=(
                dedent(
                    text=(
                        '    Type annotation is missing for parameter "pat'
                        'h"\n      Parameter "path" is unannotated'
                    ),
                )
            ),
        ),
        _lint(
            origin=("basedpyright", "reportUnusedCallResult", "warning"),
            file=app,
            position=(12, 1),
            message='Result of call expression is of type "None"',
        ),
    ]
    eslint: list[JsonValue] = [
        _lint(
            origin=("eslint", "prefer-const", "warning"),
            file=script,
            position=(1, 7),
            message="'box' is never reassigned. Use 'const' instead.",
        ),
    ]
    eslint_entry: dict[str, JsonValue] = _entry(
        tool="eslint",
        returncode=0,
        findings=eslint,
        version="9.12.0",
    )
    eslint_entry["skipped_files"] = [
        {
            "file": str(object=root / "web" / "exactus.packages.min.js"),
            "reason": "File ignored because of a matching ignore pattern.",
        },
    ]
    return {
        "version": 1,
        "tools": {
            "custom_python": _entry(
                tool="custom_python",
                returncode=0,
                findings=custom_python,
                version=None,
            ),
            "custom_javascript": _entry(
                tool="custom_javascript",
                returncode=0,
                findings=custom_javascript,
                version=None,
            ),
            "custom_css": _entry(
                tool="custom_css",
                returncode=0,
                findings=[],
                version=None,
            ),
            "custom_html": _entry(
                tool="custom_html",
                returncode=0,
                findings=[],
                version=None,
            ),
            "ruff": _entry(
                tool="ruff",
                returncode=1,
                findings=ruff,
                version="0.12.0",
            ),
            "ruff_docs": _entry(
                tool="ruff_docs",
                returncode=0,
                findings=[],
                version="0.12.0",
            ),
            "basedpyright": _entry(
                tool="basedpyright",
                returncode=1,
                findings=basedpyright,
                version="1.39.0",
            ),
            "pyrefly": _entry(
                tool="pyrefly",
                returncode=0,
                findings=[],
                version="0.40.0",
            ),
            "eslint": eslint_entry,
            "typescript": _entry(
                tool="typescript",
                returncode=0,
                findings=[],
                version="5.9.3",
            ),
            "stylelint": {
                "tool": "stylelint",
                "command": [],
                "returncode": 0,
                "stderr": "stylelint is not installed.",
                "count": 0,
                "findings": [],
                "skipped": True,
            },
        },
        "summary": {
            "analysis": {
                "targets": ["."],
                "ignore_patterns": [
                    "exactus/packages/**",
                    "**/__pycache__/**",
                ],
                "files": {
                    "python": 1,
                    "javascript_jsx": 2,
                    "css": 0,
                    "html": 0,
                    "unique_analyzed": 3,
                    "with_findings": 2,
                },
            },
            "clean": False,
        },
        "findings": [
            *custom_python,
            *custom_javascript,
            *ruff,
            *basedpyright,
            *eslint,
        ],
    }


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["lints", "."])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _model(*, path: Path) -> dict[str, JsonValue]:
    """Read one JSON object file.

    Args:
        path: JSON file.

    Returns:
        The decoded object.

    """
    loaded: JsonValue = cast(
        typ="JsonValue",
        val=loads(s=path.read_text(encoding="utf-8")),
    )
    if not isinstance(loaded, dict):
        fail(message=f"{path} is not a JSON object")
    return loaded


def test_report_data_normalizes_a_fake_result(tmp_path: Path) -> None:
    """Summary, scope, findings and metrics come from the legacy payload.

    Args:
        tmp_path: Per-test temporary directory.

    """
    legacy: dict[str, JsonValue] = fake_report(root=tmp_path)
    data: dict[str, JsonValue] = report_data(report=legacy, root=tmp_path)
    for key in ("version", "tools"):
        expect_equal(actual=data[key], expected=legacy[key])
    expect_equal(
        actual=dig(document=data, path=("summary", "analysis")),
        expected=dig(document=legacy, path=("summary", "analysis")),
    )
    for key, value in (
        ("targets_eligible", 3),
        ("targets_analyzed", 3),
        ("findings_total", 8),
        ("severity", {"error": 1, "warning": 7}),
        ("clean", False),
    ):
        expect_equal(
            actual=dig(document=data, path=("summary", key)),
            expected=value,
        )
    expect_equal(
        actual=data["scope"],
        expected={
            "include": ["."],
            "exclude": ["exactus/packages/**", "**/__pycache__/**"],
            "skipped": [
                {
                    "target": "web/exactus.packages.min.js",
                    "reason": (
                        "eslint: File ignored because of a matching ignore "
                        "pattern."
                    ),
                },
            ],
        },
    )
    findings: list[object] = dig_list(document=data, path=("findings",))
    expect_equal(
        actual=[
            (
                dig(document=item, path=("id",)),
                dig(document=item, path=("source",)),
                dig(document=item, path=("rule",)),
                dig(document=item, path=("blocking",)),
            )
            for item in findings
        ],
        expected=[
            ("LINTS-001", "custom_python", "PY002", True),
            ("LINTS-002", "custom_javascript", "JS005", True),
            ("LINTS-003", "ruff", "ANN001", True),
            ("LINTS-004", "ruff", "PTH123", True),
            ("LINTS-005", "ruff", "SIM115", True),
            ("LINTS-006", "basedpyright", "reportMissingParameterType", True),
            ("LINTS-007", "basedpyright", "reportUnusedCallResult", True),
            ("LINTS-008", "eslint", "prefer-const", True),
        ],
    )
    expect_equal(
        actual=findings[0],
        expected={
            "tool": "custom_python",
            "file": str(object=tmp_path / "pkg" / "app.py"),
            "rule": "PY002",
            "severity": "warning",
            "message": (
                "Module global `LIMIT` is uppercase but is not declared "
                "Final. Use an immutable constant or move mutable state to "
                "an explicit instance dependency."
            ),
            "line": 4,
            "column": 1,
            "end_line": 4,
            "end_column": 1,
            "id": "LINTS-001",
            "title": "Module global `LIMIT` is uppercase but is not "
            "declared Final.",
            "path": "pkg/app.py",
            "blocking": True,
            "source": "custom_python",
        },
    )
    expect_equal(
        actual=dig(document=findings[5], path=("title",)),
        expected='Type annotation is missing for parameter "path"',
    )


def test_report_data_metrics(tmp_path: Path) -> None:
    """Per-linter rows, top rules, top files and severities per linter.

    Args:
        tmp_path: Per-test temporary directory.

    """
    data: dict[str, JsonValue] = report_data(
        report=fake_report(root=tmp_path),
        root=tmp_path,
    )
    metrics: object = dig(document=data, path=("extension", "metrics"))
    expect_equal(
        actual=dig(document=metrics, path=("overview",)),
        expected={
            "linters_run": 10,
            "linters_unavailable": 1,
            "files_analyzed": 3,
            "files_with_findings": 2,
            "rules_triggered": 8,
            "findings": 8,
        },
    )
    rows: list[object] = dig_list(document=metrics, path=("linters",))
    expect_equal(
        actual=[dig(document=row, path=("linter",)) for row in rows],
        expected=[
            "custom_compliance",
            "custom_shebang",
            "custom_python",
            "custom_python_long_lines",
            "custom_javascript",
            "custom_javascript_delimiters",
            "custom_javascript_notation",
            "custom_css",
            "custom_html",
            "ruff",
            "ruff_docs",
            "basedpyright",
            "pyrefly",
            "eslint",
            "typescript",
            "stylelint",
            "htmlhint",
        ],
    )
    expect_equal(
        actual=rows[2],
        expected={
            "linter": "custom_python",
            "status": "ran",
            "version": "built-in",
            "files": 1,
            "findings": 1,
            "errors": 0,
            "warnings": 1,
            "information": 0,
            "exit_code": 0,
            "duration_seconds": 0.25,
        },
    )
    expect_equal(
        actual=rows[11],
        expected={
            "linter": "basedpyright",
            "status": "ran",
            "version": "1.39.0",
            "files": 1,
            "findings": 2,
            "errors": 1,
            "warnings": 1,
            "information": 0,
            "exit_code": 1,
            "duration_seconds": 0.25,
        },
    )
    expect_equal(actual=dig(document=rows[14], path=("files",)), expected=2)
    for index, status in ((15, "missing"), (16, "not run")):
        expect_equal(
            actual=rows[index],
            expected={
                "linter": dig(document=rows[index], path=("linter",)),
                "status": status,
                "version": None,
                "files": 0,
                "findings": 0,
                "errors": 0,
                "warnings": 0,
                "information": 0,
                "exit_code": None,
                "duration_seconds": None,
            },
        )
    expect_equal(
        actual=dig_list(document=metrics, path=("top_rules",))[:3],
        expected=[
            {"rule": "PY002", "linter": "custom_python", "count": 1},
            {"rule": "JS005", "linter": "custom_javascript", "count": 1},
            {"rule": "ANN001", "linter": "ruff", "count": 1},
        ],
    )
    expect_equal(
        actual=dig(document=metrics, path=("top_files",)),
        expected=[
            {"path": "pkg/app.py", "count": 6},
            {"path": "web/app.js", "count": 2},
        ],
    )
    expect_equal(
        actual=dig(document=metrics, path=("severity_by_linter",)),
        expected=[
            {"linter": "custom_python", "severity": "warning", "count": 1},
            {"linter": "custom_javascript", "severity": "warning", "count": 1},
            {"linter": "ruff", "severity": "warning", "count": 3},
            {"linter": "basedpyright", "severity": "error", "count": 1},
            {"linter": "basedpyright", "severity": "warning", "count": 1},
            {"linter": "eslint", "severity": "warning", "count": 1},
        ],
    )


def test_findings_carry_excerpts(tmp_path: Path) -> None:
    """Shared excerpts attach to findings at their root-relative path.

    Args:
        tmp_path: Per-test temporary directory.

    """
    write_sources(root=tmp_path)
    data: dict[str, JsonValue] = with_excerpts(
        payload=report_data(report=fake_report(root=tmp_path), root=tmp_path),
        root=tmp_path,
        context=1,
    )
    expect_equal(
        actual=dig(document=data, path=("findings", 0, "excerpt")),
        expected={
            "language": "python",
            "line": 4,
            "context": 1,
            "start": 3,
            "end": 5,
            "clipped": False,
            "lines": [
                {"n": 3, "text": "import os", "target": False},
                {"n": 4, "text": "LIMIT = 3", "target": True},
                {"n": 5, "text": "", "target": False},
            ],
        },
    )
    expect_equal(
        actual=dig(document=data, path=("findings", 7, "excerpt", "language")),
        expected="javascript",
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("", "R1"),
        ("One. Two.", "One."),
        ("Use `a. b` here. Then more.", "Use `a. b` here."),
        ("first\nsecond", "first"),
        ("x" * 130, "x" * 119 + "…"),
    ],
)
def test_finding_title(message: str, expected: str) -> None:
    """Titles are the first sentence of the first line, shortened.

    Args:
        message: Linter message.
        expected: Title.

    """
    expect_equal(
        actual=finding_title(message=message, rule="R1", source="ruff"),
        expected=expected,
    )


def test_paths_and_statuses(tmp_path: Path) -> None:
    """Paths become root-relative; statuses name how a linter took part.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_equal(
        actual=relative_path(
            value=str(object=tmp_path / "a" / "b.py"),
            root=tmp_path,
        ),
        expected="a/b.py",
    )
    expect_equal(
        actual=relative_path(value="/elsewhere/x.py", root=tmp_path),
        expected="/elsewhere/x.py",
    )
    expect_equal(
        actual=relative_path(value="./c.js", root=tmp_path),
        expected="c.js",
    )
    expect_equal(actual=relative_path(value="", root=tmp_path), expected="")
    expect_equal(actual=linter_status(entry=None), expected="not run")
    expect_equal(
        actual=linter_status(entry={"skipped": True, "stderr": "off"}),
        expected="skipped",
    )
    expect_equal(actual=linter_status(entry={"returncode": 2}), expected="ran")


def test_versions_and_durations_are_recorded(tmp_path: Path) -> None:
    """``--version`` probes and command timings reach the tool entries.

    Args:
        tmp_path: Per-test temporary directory.

    """
    probe: tuple[str, ...] = (
        executable,
        "-c",
        "print('ruff 0.12.0 (abc 2026-01-01)')",
    )
    tools: dict[str, JsonValue] = {
        "ruff": {"tool": "ruff"},
        "ruff_docs": {"tool": "ruff_docs"},
        "eslint": {"tool": "eslint", "skipped": True},
        "custom_python": {"tool": "custom_python"},
        "typescript": {"tool": "typescript"},
    }
    _ = private_call(
        owner=LintExactus,
        name="_record_versions",
        tools=tools,
        commands={
            "ruff": probe,
            "eslint": probe,
            "tsc": (str(object=tmp_path / "missing-tsc"),),
        },
    )
    expect_equal(
        actual=tools,
        expected={
            "ruff": {"tool": "ruff", "version": "0.12.0"},
            "ruff_docs": {"tool": "ruff_docs", "version": "0.12.0"},
            "eslint": {"tool": "eslint", "skipped": True},
            "custom_python": {"tool": "custom_python"},
            "typescript": {"tool": "typescript", "version": None},
        },
    )
    result: CommandResult = LintExactus.run_command(
        command=(executable, "-c", "print(1)"),
        cwd=tmp_path,
    )
    expect_true(condition=result.duration_seconds > 0)


def test_golden_result_renders_expected_markdown() -> None:
    """The checked-in result.json renders the checked-in result.md."""
    model: dict[str, JsonValue] = _model(path=GOLDEN / "result.json")
    expect_equal(
        actual=ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown,
        expected=(GOLDEN / "expected.md").read_text(encoding="utf-8"),
    )


def test_crash_render_shows_na_blocks() -> None:
    """An envelope-only result renders ERROR with N/A tool blocks."""
    model: dict[str, JsonValue] = _model(
        path=Constants.common / "examples" / "error_result.json",
    )
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "> **Gate: ERROR** — RuntimeError: boom",
        "## Findings\n\nN/A — the tool reported no findings list.",
        "## Lint metrics\n\nN/A — the tool reported no metrics.",
    ):
        expect_in(member=member, container=text)


def test_empty_findings_state_why_nothing_is_listed(tmp_path: Path) -> None:
    """A clean run says so in the findings and the metric tables.

    Args:
        tmp_path: Per-test temporary directory.

    """
    model: dict[str, JsonValue] = _model(path=GOLDEN / "result.json")
    legacy: dict[str, JsonValue] = fake_report(root=tmp_path)
    legacy["findings"] = []
    clean: dict[str, JsonValue] = report_data(report=legacy, root=tmp_path)
    for key in ("summary", "scope", "findings", "extension"):
        model[key] = clean[key]
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "## Findings\n\nNo findings.",
        "### Top rules\n\nN/A — no rule reported a finding.",
        "### Files with the most findings\n\nN/A — no file has a finding.",
        "| custom_python | ran | built-in | 1 | 0 |",
    ):
        expect_in(member=member, container=text)


def _no_commands(
    cwd: Path,
    toolchain: Path | None,
) -> dict[str, tuple[str, ...] | None]:
    """Resolve no external linter, so only the built-in checkers run.

    Args:
        cwd: Project working directory (unused).
        toolchain: Explicit toolchain (unused).

    Returns:
        ``None`` for every external command.

    """
    _ = (cwd, toolchain)
    return dict.fromkeys(COMMANDS)


def test_execute_exactus_renders_lints_from_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real LINTS run writes the normalized report bundle and web view.

    External linters are resolved to nothing (reported as missing), so
    the run needs no network, installs or linter binaries.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=LintExactus,
        name="_resolve_commands",
        value=staticmethod(_no_commands),
    )
    root: Path = tmp_path / "project"
    write_sources(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "LINTS"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=partial(
            lints_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                "--dry",
                "--no-install-tools",
                "--context-lines",
                "2",
            ),
        ),
        output=out,
    )
    expect_equal(actual=result.status, expected="FAIL")
    payload: dict[str, JsonValue] = _model(path=out / "result.json")
    for key in (*BundleConstants.normalized_blocks, "tools", "analyzer"):
        expect_in(member=key, container=payload)
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_equal(
        actual=stamped_markdown(model=payload, tool_dir=TOOL_DIR, base=out),
        expected=markdown,
    )
    expect_not_in(member="## Summary\n", container=markdown)
    for member in (
        "### custom_python — 2 findings",
        "### custom_javascript — 1 finding",
        "| ruff | missing | N/A | 0 | 0 |",
        "| [pkg/app.py](../../project/pkg/app.py) | 2 |",
        "    4>| LIMIT = 3",
    ):
        expect_in(member=member, container=markdown)
    first: object = dig(document=payload, path=("findings", 0))
    expect_equal(
        actual=dig(document=first, path=("excerpt", "context")),
        expected=2,
    )
    expect_equal(
        actual=dig(document=first, path=("path",)),
        expected="pkg/app.py",
    )
    web: dict[str, JsonValue] = _model(path=out / "result_web" / "data.json")
    expect_equal(actual=web["markdown"], expected=markdown)
    sources: list[object] = [
        dig(document=item, path=("source",))
        for item in dig_list(document=web, path=("view", "findings"))
    ]
    expect_equal(
        actual=sources,
        expected=["custom_python", "custom_python", "custom_javascript"],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "severity_levels")),
        expected=["error", "warning", "information"],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "source_label")),
        expected="Linter",
    )
    expect_equal(
        actual=dig(document=web, path=("view_columns", "linters")),
        expected=[
            "linter",
            "status",
            "version",
            "files",
            "findings",
            "errors",
            "warnings",
            "information",
            "exit_code",
            "duration_seconds",
        ],
    )
    expect_equal(
        actual=dig(document=web, path=("view_columns", "top_rules")),
        expected=["rule", "linter", "count"],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "top_files")),
        expected=[
            {"path": "pkg/app.py", "count": 2},
            {"path": "web/app.js", "count": 1},
        ],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "lint_overview", 0)),
        expected={"metric": "Linters run", "value": 9},
    )
    expect_true(condition=bool(dig(document=web, path=("view", "blocking"))))
    expect_none(
        value=dig(document=web, path=("view", "linters", 9, "version")),
    )


def _capture_steps(*, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch the shared progress sink and return its step labels.

    Args:
        monkeypatch: Pytest patching helper.

    Returns:
        The list that collects each published progress ``step``.

    """
    steps: list[str] = []

    def publish(*, progress: lints_core.Progress) -> None:
        """Record each shared progress step label.

        Args:
            progress: Published progress snapshot.

        """
        steps.append(progress.step)

    monkeypatch.setattr(
        target=lints_core,
        name="publish_progress",
        value=publish,
    )
    return steps


def test_execute_exactus_simple_reports_only_all_lints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--simple`` writes the standard bundle with all-lints tools only.

    External linters are resolved to nothing, so the run needs no
    network, installs or linter binaries.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=LintExactus,
        name="_resolve_commands",
        value=staticmethod(_no_commands),
    )
    steps: list[str] = _capture_steps(monkeypatch=monkeypatch)
    root: Path = tmp_path / "project"
    write_sources(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "LINTS"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=partial(
            lints_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                "--simple",
                "--dry",
                "--no-install-tools",
            ),
        ),
        output=out,
    )
    expect_equal(actual=result.status, expected="PASS")
    payload: dict[str, JsonValue] = _model(path=out / "result.json")
    for key in (*BundleConstants.normalized_blocks, "tools", "all_lints"):
        expect_in(member=key, container=payload)
    tools: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=require_type(
            value=dig(document=payload, path=("tools",)),
            kind=dict,
        ),
    )
    for name in (
        "custom_compliance",
        "custom_shebang",
        "custom_python",
        "custom_javascript",
        "custom_javascript_delimiters",
        "custom_javascript_notation",
        "custom_css",
        "custom_html",
    ):
        expect_not_in(member=name, container=tools)
    for name in ("ruff", "basedpyright", "pyrefly"):
        expect_in(member=name, container=tools)
    expect_equal(
        actual=dig(document=payload, path=("group_final", "enabled")),
        expected=False,
    )
    expect_equal(
        actual=dig(document=payload, path=("organize", "enabled")),
        expected=False,
    )
    for stage in ("conventions", "clean", "infer", "group final"):
        expect_not_in(member=stage, container=steps)
    expect_in(member="all lints", container=steps)


def test_execute_exactus_dry_reports_pyrefly_not_infer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-fix`` runs publish the ``pyrefly`` stage, never ``infer``.

    The pyrefly audit still runs in read-only mode; the guarded
    ``pyrefly infer`` mutation does not, so the stage label must not
    claim inference happened.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=LintExactus,
        name="_resolve_commands",
        value=staticmethod(_no_commands),
    )
    steps: list[str] = _capture_steps(monkeypatch=monkeypatch)
    root: Path = tmp_path / "project"
    write_sources(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "LINTS"
    _ = ent.execute_exactus(
        analyzer="lints",
        title="Lints Exactus",
        main=partial(
            lints_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                "--no-fix",
                "--no-install-tools",
            ),
        ),
        output=out,
    )
    expect_not_in(member="infer", container=steps)
    expect_in(member="pyrefly", container=steps)
