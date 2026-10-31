# Copyright (c) 2026
"""KWARGS_TYPEHINTS renders result.md and its web view from normalized data."""

from __future__ import annotations

from functools import partial
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
    fail,
    stamped_markdown,
)
from exactus.tools.common import execution as ent
from exactus.tools.kwargs_typehints import core as kwargs_core
from exactus.tools.kwargs_typehints.main import (
    Constants as _GroupFinalConstants,
)
from exactus.tools.kwargs_typehints.main import PathScope
from exactus.tools.kwargs_typehints.main import main as kwargs_main
from exactus.tools.kwargs_typehints.report import (
    ReportTables,
    normalized_findings,
    report_data,
)
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.render import Constants, ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult
GOLDEN: Final[Path] = Path(__file__).resolve().parent / "golden"
TOOL_DIR: Final[Path] = ReportTemplates.tool_dir(analyzer="kwargs_typehints")
MODULE: Final[str] = dedent(
    text=(
        '    """Demo module."""\n    \n    import json\n    \n    \n    def sc'
        'ale(value: int, factor: int = 2) -> int:\n        """Scale a value.""'
        '"\n        return value * factor\n    \n    \n    def total(items):\n'
        '        """Sum items."""\n        return sum(items)\n    \n    \n    '
        'class Gamma:\n        """First walker."""\n    \n        def walk(sel'
        'f, pace: int) -> int:\n            """Walk."""\n            return pa'
        'ce\n    \n    \n    class Delta:\n        """Second walker."""\n    '
        '\n        def walk(self, pace: int, /) -> int:\n            """Walk."'
        '""\n            return pace\n    \n    \n    def dispatch(registry: d'
        'ict[str, object]) -> str:\n        """Dispatch dynamically."""\n     '
        '   registry["go"](7)\n        found = registry["w"]\n        found.wa'
        "lk(3)\n        return json.dumps(obj=scale(3))\n    "
    ),
)
CATEGORIES: Final[list[str]] = [
    "missing-kwargs",
    "bare-import",
    "missing-hint",
    "missing-hint",
    "missing-hint",
    "ambiguous-call",
    "unresolved-callee",
    "unresolved-callee",
]


def write_project(*, root: Path) -> None:
    """Write the tiny project every test exactuss.

    One positional argument that should be a keyword (``scale(3)``), a
    bare ``import json``, three missing hints, an ambiguous ``walk``
    call and two unresolved callees.

    Args:
        root: Project directory to create.

    """
    (root / "pkg").mkdir(parents=True)
    _ = (root / "pyproject.toml").write_text(
        data='[project]\nname = "demo"\n',
        encoding="utf-8",
    )
    _ = (root / "pkg" / "__init__.py").write_text(data="", encoding="utf-8")
    _ = (root / "pkg" / "mod.py").write_text(data=MODULE, encoding="utf-8")


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(
        target=ent,
        name="argv",
        value=["kwargs_typehints", "."],
    )
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


def _exactus(*, tmp_path: Path, context: int = 3) -> dict[str, JsonValue]:
    """Run the exactus core on the tiny project.

    Args:
        tmp_path: Per-test temporary directory.
        context: Context lines captured around each finding.

    Returns:
        The written ``result.json`` payload.

    """
    root: Path = tmp_path / "project"
    write_project(root=root)
    out: Path = tmp_path / "out"
    status: int = kwargs_core.main(
        arguments=(
            "--root",
            str(object=root),
            "--output",
            str(object=out / "KWARGS_TYPEHINTS.md"),
            "--heuristics-output",
            str(object=out / "ARTIFACTS" / _GroupFinalConstants.heuristics),
            "--context-lines",
            str(object=context),
            "--dry-run",
        ),
        path_filter=PathScope(root=root, includes=(), excludes=()),
        excludes=("exactus/packages/**",),
    )
    expect_equal(actual=status, expected=1)
    return _model(path=out / "result.json")


def test_findings_cover_every_category(tmp_path: Path) -> None:
    """Each category is normalized, ordered, numbered and located.

    Args:
        tmp_path: Per-test temporary directory.

    """
    payload: dict[str, JsonValue] = _exactus(tmp_path=tmp_path, context=1)
    findings: list[object] = dig_list(document=payload, path=("findings",))
    expect_equal(
        actual=[dig(document=item, path=("category",)) for item in findings],
        expected=CATEGORIES,
    )
    expect_equal(
        actual=[dig(document=item, path=("id",)) for item in findings],
        expected=[f"KWARGS-{index:03d}" for index in range(1, 9)],
    )
    expect_equal(
        actual=[dig(document=item, path=("blocking",)) for item in findings],
        expected=[True] * 5 + [False] * 3,
    )
    expect_equal(
        actual=[dig(document=item, path=("severity",)) for item in findings],
        expected=["error"] * 5 + ["warning", "info", "info"],
    )
    first: object = findings[0]
    for key, expected in (
        ("title", "Pass `value` by keyword to `scale`"),
        ("rule", "positional-argument"),
        ("source", "Missing keyword arguments"),
        ("path", "pkg/mod.py"),
        ("line", 37),
        ("file", "pkg/mod.py"),
        ("parameter", "value"),
        ("suggestion", "value=3"),
        ("confidence", "resolved"),
    ):
        expect_equal(
            actual=dig(document=first, path=(key,)),
            expected=expected,
        )
    expect_equal(
        actual=dig(document=first, path=("excerpt", "lines", 1)),
        expected={
            "n": 37,
            "target": True,
            "text": "    return json.dumps(obj=scale(3))",
        },
    )
    expect_equal(
        actual=[
            dig(document=item, path=("rule",))
            for item in findings[1:5] + findings[6:]
        ],
        expected=[
            "bare-import-manual",
            "missing-return-hint",
            "missing-parameter-hint",
            "missing-variable-hint",
            "subscript-lookup",
            "unknown-receiver",
        ],
    )
    expect_equal(
        actual=dig(document=findings[5], path=("candidates",)),
        expected=["Gamma.walk", "Delta.walk"],
    )


def test_summary_scope_and_metrics(tmp_path: Path) -> None:
    """Counters, scope and metrics describe what was checked.

    Args:
        tmp_path: Per-test temporary directory.

    """
    payload: dict[str, JsonValue] = _exactus(tmp_path=tmp_path)
    summary: object = dig(document=payload, path=("summary",))
    for key, expected in (
        ("python_files", 2),
        ("positional_findings", 1),
        ("targets_eligible", 2),
        ("targets_analyzed", 2),
        ("findings_total", 8),
        ("severity", {"error": 5, "warning": 1, "info": 2}),
        ("unresolved_call_sites", 2),
        ("functions_checked", 5),
        ("parameters_checked", 6),
    ):
        expect_equal(
            actual=dig(document=summary, path=(key,)),
            expected=expected,
        )
    expect_equal(
        actual=dig(document=payload, path=("scope",)),
        expected={
            "include": ["**/*.py"],
            "exclude": [
                "exactus/packages/**",
                *(
                    f"**/{name}/**"
                    for name in sorted(kwargs_core.Constants.skip_dirs)
                ),
            ],
            "skipped": [],
        },
    )
    overview: object = dig(
        document=payload,
        path=("extension", "metrics", "overview"),
    )
    for key, expected in (
        ("files_analyzed", 2),
        ("call_sites", 4),
        ("resolved_call_sites", 2),
        ("resolution_percent", 50.0),
        ("unresolved_call_sites", 2),
        ("skipped_call_sites", 0),
        ("missing_parameter_hints", 1),
        ("missing_return_hints", 1),
        ("missing_variable_hints", 1),
        ("hint_coverage_percent", 81.8),
        ("blocking_findings", 5),
    ):
        expect_equal(
            actual=dig(document=overview, path=(key,)),
            expected=expected,
        )
    categories: list[object] = dig_list(
        document=payload,
        path=("extension", "metrics", "categories"),
    )
    expect_equal(
        actual=[
            (
                dig(document=row, path=("category",)),
                dig(document=row, path=("count",)),
            )
            for row in categories
        ],
        expected=list(
            zip(ReportTables.categories, [1, 1, 3, 0, 1, 2], strict=True),
        ),
    )


def test_extension_rows_link_to_their_findings(tmp_path: Path) -> None:
    """Unresolved, ambiguous and bare-import rows name their finding.

    Args:
        tmp_path: Per-test temporary directory.

    """
    payload: dict[str, JsonValue] = _exactus(tmp_path=tmp_path)
    extension: object = dig(document=payload, path=("extension",))
    expect_equal(
        actual=dig(document=extension, path=("unresolved_callees",)),
        expected=[
            {
                "callee": "found.walk",
                "path": "pkg/mod.py",
                "line": 36,
                "reason": "receiver type unknown",
                "count": 1,
                "finding": "KWARGS-008",
            },
            {
                "callee": "registry['go']",
                "path": "pkg/mod.py",
                "line": 34,
                "reason": "subscript lookup",
                "count": 1,
                "finding": "KWARGS-007",
            },
        ],
    )
    expect_equal(
        actual=dig(document=extension, path=("ambiguous_call_sites",)),
        expected=[
            {
                "callee": "found.walk",
                "path": "pkg/mod.py",
                "line": 36,
                "candidates": "Gamma.walk, Delta.walk",
                "finding": "KWARGS-006",
            },
        ],
    )
    expect_equal(
        actual=dig(document=extension, path=("bare_imports",)),
        expected=[
            {
                "module": "json",
                "path": "pkg/mod.py",
                "line": 3,
                "fix": "manual",
                "suggestion": None,
                "finding": "KWARGS-002",
            },
        ],
    )
    expect_equal(
        actual=dig(document=extension, path=("methodology",)),
        expected=list(ReportTables.methodology),
    )


def test_normalization_of_rare_categories() -> None:
    """Parse failures, safe bare imports and unknown reasons normalize."""
    findings: list[JsonValue] = normalized_findings(
        report={
            "parse_failure_files": ["broken.py"],
            "bare_imports": [
                {
                    "file": "a.py",
                    "line": 1,
                    "column": 1,
                    "module": "os",
                    "safe": True,
                    "suggestion": "from os import sep",
                    "replacements": [[4, 7, "os.sep", "sep"]],
                },
            ],
            "unresolved_sites": [
                {"file": "a.py", "line": 9, "callee": "f", "reason": "odd"},
                {"file": "b.py", "line": 2, "callee": "f", "reason": ""},
            ],
        },
    )
    expect_equal(
        actual=[dig(document=item, path=("rule",)) for item in findings],
        expected=[
            "bare-import-fix",
            "syntax-error",
            "odd",
            "dynamic-expression",
        ],
    )
    expect_equal(
        actual=dig(document=findings[0], path=("message",)),
        expected=(
            "Replace it with `from os import sep` and rewrite 1 use of the"
            " module."
        ),
    )
    expect_equal(
        actual=dig(document=findings[1], path=("line",)),
        expected=None,
    )
    expect_equal(actual=dig(document=findings[2], path=("sites",)), expected=2)
    expect_in(
        member="No signature was found",
        container=str(object=dig(document=findings[2], path=("message",))),
    )
    data: dict[str, JsonValue] = report_data(
        report={"summary": {"python_files": 1, "parse_failures": 1}},
    )
    expect_equal(
        actual=dig(document=data, path=("summary", "targets_analyzed")),
        expected=0,
    )
    expect_equal(
        actual=dig(
            document=data,
            path=("extension", "metrics", "overview", "resolution_percent"),
        ),
        expected=None,
    )


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
        "### Metrics\n\nN/A — the tool reported no metrics.",
        "## Findings\n\nN/A — the tool reported no findings list.",
        "## Unresolved callees\n\nN/A — the tool reported no unresolved",
        "## Ambiguous call sites\n\nN/A — the tool reported no ambiguous",
        "## Bare imports\n\nN/A — the tool reported no bare imports.",
        "## Methodology and caveats\n\nN/A — the tool reported no",
    ):
        expect_in(member=member, container=text)


def test_clean_run_states_why_tables_are_empty() -> None:
    """A clean run says so in the findings and every extension table."""
    model: dict[str, JsonValue] = _model(path=GOLDEN / "result.json")
    clean: dict[str, JsonValue] = report_data(
        report={"summary": {"python_files": 2}},
    )
    for key in ("summary", "scope", "findings", "extension"):
        model[key] = clean[key]
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "## Findings\n\nNo findings.",
        "## Unresolved callees\n\nCallees with no known signature",
        "No unresolved callees: every checked call site resolved",
        "## Ambiguous call sites\n\nNo ambiguous call sites.",
        "## Bare imports\n\nNo bare imports.",
        "| Parse failures | error | Yes | 0 |",
        "| Resolved (%) |  |",
    ):
        expect_in(member=member, container=text)


def test_execute_exactus_writes_the_normalized_bundle(tmp_path: Path) -> None:
    """A real run writes result.json/md, the web view and heuristics.json.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    write_project(root=root)
    out: Path = tmp_path / "EXACTUS_RESULTS" / "KWARGS_TYPEHINTS"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="kwargs_typehints",
        title="Kwargs Typehints Exactus",
        main=partial(
            kwargs_main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                "--context-lines",
                "2",
                "--dry-run",
            ),
        ),
        output=out,
    )
    expect_equal(actual=result.status, expected="FAIL")
    expect_true(
        condition=(
            out / "ARTIFACTS" / _GroupFinalConstants.heuristics
        ).is_file(),
    )
    expect_true(
        condition=isinstance(
            loads(
                s=(
                    out / "ARTIFACTS" / _GroupFinalConstants.heuristics
                ).read_text(),
            ),
            dict,
        ),
    )
    for stale in ("BUILTIN_ARG_TYPES.json", "builtin_arg_types.json"):
        expect_false(condition=(out / "ARTIFACTS" / stale).exists())
        expect_false(condition=(out / stale).exists())
    payload: dict[str, JsonValue] = _model(path=out / "result.json")
    for key in (
        *BundleConstants.normalized_blocks,
        "unresolved",
        "type_hints",
    ):
        expect_in(member=key, container=payload)
    expect_in(
        member="ARTIFACTS/heuristics.json",
        container=[
            dig(document=item, path=("path",))
            for item in dig_list(document=payload, path=("artifacts",))
        ],
    )
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_equal(
        actual=stamped_markdown(model=payload, tool_dir=TOOL_DIR, base=out),
        expected=markdown,
    )
    expect_not_in(member="## Findings by area", container=markdown)
    for member in (
        "### Missing keyword arguments — 1 finding",
        "### Unresolved callees — 2 findings",
        (
            "| `found.walk` | [pkg/mod.py](../../project/pkg/mod.py) | 36 |"
            " receiver type unknown | 1 | KWARGS-008 |"
        ),
        "   37>|     return json.dumps(obj=scale(3))",
        "> **Gate: FAIL** — 5 blocking findings",
    ):
        expect_in(member=member, container=markdown)
    expect_equal(
        actual=dig(
            document=payload,
            path=("findings", 0, "excerpt", "context"),
        ),
        expected=2,
    )
    web: dict[str, JsonValue] = _model(path=out / "result_web" / "data.json")
    expect_equal(actual=web["markdown"], expected=markdown)
    view_findings: dict[object, object] = {
        dig(document=item, path=("id",)): item
        for item in dig_list(document=web, path=("view", "findings"))
    }
    rows: list[object] = dig_list(
        document=web,
        path=("view", "unresolved_callees"),
    )
    expect_equal(actual=len(rows), expected=2)
    for row in rows:
        linked: object = view_findings[dig(document=row, path=("finding",))]
        expect_equal(
            actual=dig(document=linked, path=("line",)),
            expected=dig(document=row, path=("line",)),
        )
        expect_true(
            condition=bool(
                dig_list(document=linked, path=("excerpt", "lines")),
            ),
        )
    expect_equal(
        actual=dig(document=web, path=("view_columns", "unresolved_callees")),
        expected=["callee", "path", "line", "reason", "call_sites", "finding"],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "source_label")),
        expected="Category",
    )
    expect_equal(
        actual=dig(document=web, path=("view", "metrics", 0)),
        expected={"metric": "Python files analyzed", "value": 2},
    )
