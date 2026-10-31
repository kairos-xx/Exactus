# Copyright (c) 2026
"""In-process runs of the lints analyzer over generated projects."""

from __future__ import annotations

from ast import literal_eval, parse
from io import StringIO
from itertools import pairwise
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.packages.organize import (
    JavaScriptClassMethodReorderer,
    JavaScriptReorderResult,
)
from exactus.packages.steps import step_log
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_equal,
    expect_true,
    private_call,
    private_result,
)
from exactus.tools.common import runtime as runtime_module
from exactus.tools.lints import core as lints_core
from exactus.tools.lints import shebang as shebang_module
from exactus.tools.lints.core import (
    LintExactus,
    LintExactusConfig,
    template_resource,
)
from exactus.tools.lints.js_function_blocks import JavaScriptBlockAnalyzer
from exactus.tools.lints.long_lines import LongLineRepair
from exactus.tools.lints.main import main, parse_args
from exactus.tools.lints.packages_pipeline import run_organize


@final
class Constants:
    """Group module-level constants.

    Attributes:
        line_length: Grouped module constant.

    """

    line_length: Final[int] = 60


if TYPE_CHECKING:
    from argparse import Namespace
    from pathlib import Path


def test_weighted_progress_keeps_activity_monotonic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Weight expensive checks and retain progress during heartbeat notes.

    Args:
        monkeypatch: Pytest patching helper.

    """
    snapshots: list[lints_core.Progress] = []

    def publish(*, progress: lints_core.Progress) -> None:
        """Capture shared progress events.

        Args:
            progress: Published progress snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=lints_core,
        name="publish_progress",
        value=publish,
    )
    progress: lints_core.LintProgress = lints_core.LintProgress()
    progress.stage(name="all lints")
    progress.note(step="all lints", share=0.5, completed=50, total=100)
    expect_equal(actual=snapshots[-1].completed, expected=50)
    expect_equal(actual=snapshots[-1].total, expected=100)
    progress.note(step="all lints", detail="still checking")
    expect_equal(actual=snapshots[-1].span, expected=(0.25, 0.85))
    expect_equal(actual=snapshots[-1].share, expected=0.5)
    progress.note(step="all lints", share=0.4)
    expect_equal(actual=snapshots[-1].share, expected=0.5)
    progress.stage(name="infer")
    expect_equal(actual=snapshots[-1].span, expected=(0.85, 0.95))
    expect_equal(actual=snapshots[-1].share, expected=0.0)


def test_conventions_progress_is_uniform_and_monotonic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each conventions sub-step fills only its own file-weighted slice.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    for name, source in (
        ("a.py", "x = 1\n"),
        ("b.py", "y = 2\n"),
        ("app.js", "const f = x => x;\n"),
        ("site.css", "a { display: flex; }\n"),
        ("index.html", "<html></html>\n"),
    ):
        _ = (tmp_path / name).write_text(data=source, encoding="utf-8")
    fractions: list[float] = []

    def record(*, progress: lints_core.Progress) -> None:
        """Fold each snapshot's span into an overall fraction.

        Args:
            progress: Published progress snapshot.

        """
        start, end = progress.span
        fractions.append(start + progress.fraction * max(end - start, 0.0))

    for module in (lints_core, runtime_module, shebang_module):
        monkeypatch.setattr(
            target=module,
            name="publish_progress",
            value=record,
        )
    progress: lints_core.LintProgress = lints_core.LintProgress()
    progress.stage(name="conventions")
    _ = private_call(
        owner=LintExactus,
        name="_custom_tools",
        inputs=lints_core.CustomToolsInput(
            cwd=tmp_path,
            python_files=frozenset({tmp_path / "a.py", tmp_path / "b.py"}),
            eslint_args=("app.js",),
            stylelint_args=("site.css",),
            htmlhint_args=("index.html",),
            bare_import_exceptions=(),
            targets=(".",),
            ignores=(),
            fix=False,
            progress=progress,
        ),
    )
    expect_true(
        condition=bool(fractions),
        message="The conventions stage published no progress.",
    )
    regressions: list[tuple[float, float]] = [
        (earlier, later)
        for earlier, later in pairwise(fractions)
        if later < earlier - 1e-9
    ]
    expect_equal(actual=regressions, expected=[])
    expect_true(
        condition=all(
            0.12 - 1e-9 <= fraction <= 0.25 + 1e-9 for fraction in fractions
        ),
        message="Conventions progress escaped its stage span.",
    )


def _run(project: Path, out: Path, *flags: str) -> int:
    """Run the lints analyzer with the given flags.

    Args:
        project: Project root.
        out: Report directory.
        *flags: Extra command-line flags.

    Returns:
        The analyzer exit status.

    """
    return main(
        arguments=(
            str(object=project),
            "-o",
            str(object=out),
            "--no-install-tools",
            *flags,
        ),
    )


def test_parse_args_defaults() -> None:
    """Defaults leave every cleaning stage enabled."""
    options: Namespace = parse_args(arguments=("somewhere",))
    expect_false(condition=bool(options.dry))
    expect_false(condition=bool(options.no_fix))
    expect_false(condition=bool(options.no_group_final))
    expect_false(condition=bool(options.no_organize))
    expect_false(condition=bool(options.unsafe_fixes))


def test_parse_args_integrated_stage_controls() -> None:
    """CLI controls expose group-final and unsafe Ruff behavior."""
    options: Namespace = parse_args(
        arguments=(
            "somewhere",
            "--no-group-final",
            "--no-organize",
            "--unsafe-fixes",
            "--workers",
            "7",
        ),
    )
    expect_true(condition=bool(options.no_group_final))
    expect_true(condition=bool(options.no_organize))
    expect_true(condition=bool(options.unsafe_fixes))
    expect_equal(actual=options.workers, expected=7)


def test_pyproject_configures_integrated_stages(tmp_path: Path) -> None:
    """The lints pyproject table accepts both integrated-stage controls.

    Args:
        tmp_path: Tmp path.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    _ = (project / "pyproject.toml").write_text(
        data=(
            dedent(
                text="""\
    [tool.exactus]
    root = true
    [tool.exactus.lints]
    no-group-final = true
    no-organize = true
    unsafe-fixes = true
    workers = 6
    """,
            )
        ),
        encoding="utf-8",
    )
    options: Namespace = parse_args(arguments=(str(object=project),))
    expect_true(condition=bool(options.no_group_final))
    expect_true(condition=bool(options.no_organize))
    expect_true(condition=bool(options.unsafe_fixes))
    expect_equal(actual=options.workers, expected=6)


def test_parse_args_simple_and_runtime_limits() -> None:
    """``--simple`` and the runtime-registry retention flags parse."""
    options: Namespace = parse_args(arguments=("somewhere",))
    expect_false(condition=bool(options.simple))
    expect_none(value=options.runtime_max_runs)
    expect_none(value=options.runtime_max_size)
    configured: Namespace = parse_args(
        arguments=(
            "somewhere",
            "--simple",
            "--runtime-max-runs",
            "12",
            "--runtime-max-size",
            "8MB",
        ),
    )
    expect_true(condition=bool(configured.simple))
    expect_equal(actual=configured.runtime_max_runs, expected=12)
    expect_equal(actual=configured.runtime_max_size, expected=8 * 1024 * 1024)


def test_parse_args_rejects_bad_runtime_limits() -> None:
    """Malformed runtime retention values fail argument parsing."""
    with pytest.raises(expected_exception=SystemExit):
        _ = parse_args(arguments=("somewhere", "--runtime-max-runs", "0"))
    with pytest.raises(expected_exception=SystemExit):
        _ = parse_args(arguments=("somewhere", "--runtime-max-size", "bogus"))


def test_pyproject_configures_simple_and_runtime_limits(
    tmp_path: Path,
) -> None:
    """The lints table accepts ``simple`` and the runtime limits.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    _ = (project / "pyproject.toml").write_text(
        data=(
            dedent(
                text="""\
    [tool.exactus]
    root = true
    [tool.exactus.lints]
    simple = true
    runtime_max_runs = 4
    runtime_max_size = "64kb"
    """,
            )
        ),
        encoding="utf-8",
    )
    options: Namespace = parse_args(arguments=(str(object=project),))
    expect_true(condition=bool(options.simple))
    expect_equal(actual=options.runtime_max_runs, expected=4)
    expect_equal(actual=options.runtime_max_size, expected=64 * 1024)
    _ = (project / "pyproject.toml").write_text(
        data=(
            dedent(
                text="""\
    [tool.exactus]
    root = true
    [tool.exactus.lints]
    runtime_max_size = 33554432
    """,
            )
        ),
        encoding="utf-8",
    )
    expect_equal(
        actual=parse_args(arguments=(str(object=project),)).runtime_max_size,
        expected=33554432,
    )


def test_simple_progress_budgets_only_all_lints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The all-lints-only run publishes its own spans and stage total.

    Args:
        monkeypatch: Pytest patching helper.

    """
    snapshots: list[lints_core.Progress] = []

    def publish(*, progress: lints_core.Progress) -> None:
        """Capture shared progress events.

        Args:
            progress: Published progress snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=lints_core,
        name="publish_progress",
        value=publish,
    )
    progress: lints_core.LintProgress = lints_core.LintProgress(simple=True)
    expect_equal(actual=progress.total, expected=4)
    progress.stage(name="toolchain")
    expect_equal(actual=snapshots[-1].span, expected=(0.02, 0.08))
    progress.stage(name="all lints")
    expect_equal(actual=snapshots[-1].span, expected=(0.08, 0.95))
    progress.stage(name="compliance and report")
    expect_equal(actual=snapshots[-1].span, expected=(0.95, 1.0))


def test_pyrefly_stage_span_replaces_infer_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-fix`` runs report a ``pyrefly`` stage, never ``infer``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    snapshots: list[lints_core.Progress] = []

    def publish(*, progress: lints_core.Progress) -> None:
        """Capture shared progress events.

        Args:
            progress: Published progress snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=lints_core,
        name="publish_progress",
        value=publish,
    )
    progress: lints_core.LintProgress = lints_core.LintProgress()
    progress.stage(name="pyrefly")
    expect_equal(actual=snapshots[-1].span, expected=(0.85, 0.95))
    expect_equal(actual=snapshots[-1].step, expected="pyrefly")


def test_run_organize_respects_dry_run_and_writes(tmp_path: Path) -> None:
    """Organize only selected Python files and honor dry-run mode.

    Args:
        tmp_path: Temporary test directory.

    """
    target: Path = tmp_path / "target.py"
    untouched: Path = tmp_path / "untouched.py"
    source: str = dedent(
        text="""\
    class Example:
        def public(self) -> None:
            pass

        @classmethod
        def build(cls) -> None:
            pass
    """,
    )
    _ = target.write_text(data=source, encoding="utf-8")
    _ = untouched.write_text(data=source, encoding="utf-8")
    dry_report: dict[str, lints_core.JsonValue] = run_organize(
        paths=(target,),
        dry_run=True,
    )
    expect_equal(actual=dry_report["files"], expected=1)
    expect_equal(actual=dry_report["changed"], expected=1)
    expect_equal(actual=target.read_text(encoding="utf-8"), expected=source)
    write_report: dict[str, lints_core.JsonValue] = run_organize(
        paths=(target,),
        dry_run=False,
    )
    expect_equal(actual=write_report["changed"], expected=1)
    reordered: str = target.read_text(encoding="utf-8")
    expect_true(
        condition=reordered.index("def build") < reordered.index("def public"),
    )
    expect_equal(actual=untouched.read_text(encoding="utf-8"), expected=source)


def test_run_organize_traces_each_file_state(tmp_path: Path) -> None:
    """Trace changed, unchanged, and unparseable organizer inputs.

    Args:
        tmp_path: Temporary test directory.

    """
    changed: Path = tmp_path / "changed.py"
    unchanged: Path = tmp_path / "unchanged.py"
    invalid: Path = tmp_path / "invalid.py"
    trace_path: Path = tmp_path / "steps.txt"
    _ = changed.write_text(
        data=(
            dedent(
                text="""\
    class Example:
        def public(self) -> None:
            pass

        @classmethod
        def build(cls) -> None:
            pass
    """,
            )
        ),
        encoding="utf-8",
    )
    _ = unchanged.write_text(data="class Empty:\n    pass\n", encoding="utf-8")
    _ = invalid.write_text(data="class Broken(:\n    pass\n", encoding="utf-8")
    with step_log(path=trace_path):
        report: dict[str, lints_core.JsonValue] = run_organize(
            paths=(changed, unchanged, invalid),
            dry_run=True,
        )
    trace_source: str = trace_path.read_text(encoding="utf-8")
    expect_equal(actual=report["changed"], expected=1)
    expect_equal(actual=report["skipped"], expected=1)
    expect_in(
        member=f"organize[python]: {changed} — would change",
        container=trace_source,
    )
    expect_in(
        member=f"organize[python]: {unchanged} — unchanged",
        container=trace_source,
    )
    expect_in(
        member=f"organize[python]: {invalid} — skipped: unparseable",
        container=trace_source,
    )


@pytest.mark.parametrize(
    "flags",
    [("--dry",), ("--no-clean", "--no-fix", "--no-infer")],
)
def test_sample_project_lints(
    flags: tuple[str, ...],
    sample_project: Path,
    tmp_path: Path,
) -> None:
    """Lints report findings for a defective sample project.

    Args:
        flags: Parametrized command-line flags.
        sample_project: Generated sample project directory.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(sample_project, tmp_path / "out", *flags)
    expect_in(member=status, container={0, 1})
    expect_true(condition=(tmp_path / "out" / "result.md").is_file())


def test_fixing_pass_runs_on_copy(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    """The default pipeline cleans and fixes a throwaway project.

    Args:
        sample_project: Generated sample project directory.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(project=sample_project, out=tmp_path / "out")
    expect_in(member=status, container={0, 1})


@pytest.mark.parametrize("flags", [(), ("--dry",), ("--no-fix",)])
def test_defect_project_lints(
    flags: tuple[str, ...],
    defect_project: Path,
    tmp_path: Path,
) -> None:
    """Lints flag defects in every supported language.

    Args:
        flags: Parametrized command-line flags.
        defect_project: Value for ``defect_project``.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(defect_project, tmp_path / "out", *flags)
    expect_equal(actual=status, expected=1)


def test_repo_lints_dry(repo_args: tuple[str, ...], tmp_path: Path) -> None:
    """The toolkit lints its own source tree without crashing.

    Args:
        repo_args: Parametrized repository arguments.
        tmp_path: Per-test temporary directory.

    """
    status: int = main(
        arguments=(
            *repo_args,
            "-o",
            str(object=tmp_path / "out"),
            "--dry",
            "--no-install-tools",
        ),
    )
    expect_in(member=status, container={0, 1})


@pytest.mark.parametrize(
    "name",
    ["eslint.config.mjs", "stylelint.config.mjs", "jsconfig.json"],
)
def test_template_resource_found(name: str) -> None:
    """The bundled linter templates resolve from the packaged lints core.

    Args:
        name: Template asset file name under
            ``exactus/tools/lints/templates``.

    """
    expect_true(condition=template_resource(name=name).is_file())


def test_parse_args_long_line_repair_control() -> None:
    """The long-line repair is on by default and has its own switch."""
    expect_false(
        condition=bool(parse_args(arguments=("somewhere",)).no_long_lines),
    )
    options: Namespace = parse_args(arguments=("somewhere", "--no-long-lines"))
    expect_true(condition=bool(options.no_long_lines))


def test_long_line_repair_needs_fixing_ruff_and_its_switch() -> None:
    """The repair exists only when fixing, enabled and Ruff is resolved."""
    commands: dict[str, tuple[str, ...] | None] = {"ruff": ("ruff",)}
    built: object = private_call(
        owner=LintExactus,
        name="_long_line_repair",
        config=LintExactusConfig(),
        commands=commands,
    )
    expect_true(condition=isinstance(built, LongLineRepair))
    for config, resolved in (
        (LintExactusConfig(fix=False), commands),
        (LintExactusConfig(long_lines=False), commands),
        (LintExactusConfig(), {"ruff": None}),
    ):
        expect_none(
            value=private_call(
                owner=LintExactus,
                name="_long_line_repair",
                config=config,
                commands=resolved,
            ),
        )


def test_long_line_summary_is_written_to_the_status_stream(
    tmp_path: Path,
) -> None:
    """Repaired and skipped files are reported; an absent repair is silent.

    Args:
        tmp_path: Per-test directory.

    """
    target: Path = tmp_path / "a.py"
    _ = target.write_text(
        data='value = "' + "word " * 30 + '"\n',
        encoding="utf-8",
    )
    broken: Path = tmp_path / "b.py"
    _ = broken.write_bytes(data=b"# coding: nosuchcodec\nx = 1\n")
    repair: LongLineRepair = LongLineRepair()
    repair(path=target)
    repair(path=broken)
    writer: StringIO = StringIO()
    private_call(
        owner=LintExactus,
        name="_report_long_lines",
        repair=repair,
        writer=writer,
    )
    expect_in(
        member="Repaired long lines in 1 file(s)",
        container=writer.getvalue(),
    )
    expect_in(member="1 unreadable file(s)", container=writer.getvalue())
    silent: StringIO = StringIO()
    private_call(
        owner=LintExactus,
        name="_report_long_lines",
        repair=None,
        writer=silent,
    )
    expect_equal(actual=silent.getvalue(), expected="")


def test_lints_repairs_lines_ruff_cannot_wrap(tmp_path: Path) -> None:
    """A fixing run wraps a long string that Ruff's formatter leaves alone.

    Args:
        tmp_path: Per-test directory.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    _ = (project / "pyproject.toml").write_text(
        data=(
            f"[tool.exactus]\nroot = true\n[tool.ruff]\nline-length "
            f"= {Constants.line_length}\n"
        ),
        encoding="utf-8",
    )
    source: Path = project / "app.py"
    original: str = (
        '"""Module."""\n\nVALUE = "' + "alpha beta gamma " * 6 + '"\n'
    )
    _ = source.write_text(data=original, encoding="utf-8")
    _ = _run(project=project, out=tmp_path / "out")
    repaired: str = source.read_text(encoding="utf-8")
    expect_not_equal(actual=repaired, expected=original)
    expect_true(
        condition=all(
            len(line) <= Constants.line_length
            for line in repaired.splitlines()
        ),
    )
    expect_equal(
        actual=literal_eval(node_or_string=repaired.split(sep="VALUE = ")[1]),
        expected="alpha beta gamma " * 6,
    )


def test_inline_style_scan_lints_generated_code_not_embedded_source(
    tmp_path: Path,
) -> None:
    """Lint generated code while ignoring its serialized source excerpts.

    Args:
        tmp_path: Per-test directory.

    """
    report_directory: Path = tmp_path / "result_web"
    report_directory.mkdir()
    report_data: Path = report_directory / "data.js"
    _ = report_data.write_text(
        data=(
            dedent(
                text=(
                    '    window.REPORT_DATA = {"text": "Object.assign(band.sty'
                    "le, { color: 'red' });\"};\n    Object.assign(band.style,"
                    ' { color: "red" });\n    '
                ),
            )
        ),
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(
            owner=LintExactus,
            name="_javascript_inline_styles",
            files=[report_data],
        ),
        expected=[
            {
                "tool": "custom_javascript",
                "file": str(object=report_data),
                "rule": "JS006",
                "severity": "warning",
                "message": (
                    "Static inline style `color` is assigned through "
                    "`Object.assign(...style, {...})`; move it to a CSS "
                    "class."
                ),
                "line": 2,
                "column": 29,
                "end_line": 2,
                "end_column": 29,
            },
        ],
    )


def test_javascript_organizer_orders_safe_method_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order JavaScript methods while leaving class fields as barriers.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    fake_espree: Path = tmp_path / "fake_espree.cjs"
    _ = fake_espree.write_text(
        data=r""""use strict";
exports.parse = source => {
  const classStart = source.indexOf("class Demo");
  const classEnd = source.lastIndexOf("}") + 1;
  const bodyStart = source.indexOf("{", classStart) + 1;
  const bodyEnd = classEnd - 1;
  const body = [];
  const pattern = new RegExp(
    "((?:static\\s+)?(?:get\\s+|set\\s+)?#?\\w+" +
      "\\s*\\([^)]*\\)\\s*\\{\\s*\\})",
    "g",
  );
  let match;
  while ((match = pattern.exec(source.slice(bodyStart, bodyEnd))) !== null) {
    const text = match[1];
    const start = bodyStart + match.index;
    const end = start + text.length;
    const words = text.match(/^(static\s+)?(?:(get|set)\s+)?(#?\w+)/);
    const name = words[3];
    body.push({
      type: "MethodDefinition",
      range: [start, end],
      computed: false,
      static: Boolean(words[1]),
      kind: name === "constructor" ? "constructor" : (words[2] ?? "method"),
      key: name.startsWith("#")
        ? { type: "PrivateIdentifier", name: name.slice(1) }
        : { type: "Identifier", name },
      value: { body: { type: "BlockStatement" } },
    });
  }
  const fieldText = "field = 1;";
  const fieldStart = source.indexOf(fieldText);
  body.push({
    type: "PropertyDefinition",
    range: [fieldStart, fieldStart + fieldText.length],
  });
  body.sort((left, right) => left.range[0] - right.range[0]);
  return {
    type: "Program",
    comments: [],
    body: [{
      type: "ClassDeclaration",
      range: [classStart, classEnd],
      body: { type: "ClassBody", body },
    }],
  };
};
""",
        encoding="utf-8",
    )
    source: str = """class Demo {
  #private() {}
  value() {}
  set size(value) {}
  get size() {}
  static make() {}
  constructor() {}
  field = 1;
  #later() {}
  later() {}
}
"""
    target: Path = tmp_path / "demo.js"
    _ = target.write_text(data=source, encoding="utf-8")

    def _fake_resolve_espree(analyzer: JavaScriptBlockAnalyzer) -> str:
        """Return the fake espree path regardless of the analyzer.

        Args:
            analyzer: Analyzer instance, unused.

        Returns:
            The fake espree module path.

        """
        del analyzer
        return str(object=fake_espree)

    monkeypatch.setattr(
        target=JavaScriptBlockAnalyzer,
        name="resolve_espree",
        value=_fake_resolve_espree,
    )
    result: JavaScriptReorderResult = JavaScriptClassMethodReorderer(
        path=target,
    ).measure()
    expect_true(condition=result.changed)
    before_field: str
    after_field: str
    before_field, after_field = result.source.split(
        sep="  field = 1;",
        maxsplit=1,
    )
    expect_true(
        condition=before_field.index("constructor()")
        < before_field.index("static make()")
        < before_field.index("get size()")
        < before_field.index("set size(value)")
        < before_field.index("value()")
        < before_field.index("#private()"),
    )
    expect_true(
        condition=after_field.index("later()") < after_field.index("#later()"),
    )
    expect_true(
        condition=JavaScriptClassMethodReorderer(path=target).measure().source
        == result.source,
    )


def test_uppercase_globals_exempt_generic_binders(tmp_path: Path) -> None:
    """``TypeVar``-family bindings skip ``PY002``; mutable globals do not.

    Args:
        tmp_path: Isolated directory for the sample module.

    """
    source: Path = tmp_path / "module.py"
    _ = source.write_text(
        data=(
            dedent(
                text="""\
    from typing import TypeVar, ParamSpec, NewType
    _N = TypeVar(name='_N')
    _P = ParamSpec(name='_P')
    UserId = NewType('UserId', int)
    MUTABLE: int = 0
    MUT2 = [1]
    """,
            )
        ),
        encoding="utf-8",
    )
    findings: list[lints_core.JsonValue] = cast(
        typ="list[lints_core.JsonValue]",
        val=private_result(
            owner=LintExactus,
            name="_uppercase_global_findings",
            kind=list,
            file=source,
            tree=parse(source=source.read_text(encoding="utf-8")),
        ),
    )
    messages: list[str] = [
        str(object=finding.get("message"))
        for finding in findings
        if isinstance(finding, dict)
    ]
    expect_equal(actual=len(findings), expected=2)
    expect_true(
        condition=all("`MUT" in message for message in messages),
        message="A generic binder or lowercase global was flagged.",
    )
