# Copyright (c) 2026
"""In-process coverage-tests runs over the demo and a tiny project."""

from __future__ import annotations

from asyncio import run
from functools import partial
from importlib import import_module
from json import loads
from pathlib import Path
from runpy import run_path
from shutil import copytree, ignore_patterns
from textwrap import dedent
from typing import TYPE_CHECKING, Final, cast, final

import pytest
from coverage import Coverage

from exactus.packages.meaningful import UnitTestLevel
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_equal,
    expect_not_in,
    expect_true,
    private_call,
)
from exactus.tools.common import execution as ent
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CoverageConfig,
    CoverageSnapshot,
    ImportGraph,
    JsCoverageResult,
    JsFileCoverage,
)
from exactus.tools.coverage_tests.main import main, parse_args
from exactus.tools.coverage_tests.meaningful import (
    MeaningfulConfig,
    MeaningfulResult,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable, Coroutine
    from subprocess import CompletedProcess
    from types import ModuleType

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.common.models import ToolRunResult


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        demo: Grouped module constant.
        tree: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    demo: Final[Path] = root / "demo"
    tree: Final[frozenset[str]] = frozenset(
        {
            "result.md",
            "result.json",
            "result_web/",
            "COVERAGE/result.md",
            "COVERAGE/result.json",
            "COVERAGE/result_web/",
            "TESTS/result.md",
            "TESTS/result.json",
            "TESTS/result_web/",
            "TESTS/tests/result.md",
            "TESTS/tests/result.json",
            "TESTS/tests/result_web/",
            "ARTIFACTS/@activity.json",
            "ARTIFACTS/stderr.log",
            "ARTIFACTS/stdout.log",
            "ARTIFACTS/COVERAGE/completion.json",
            "ARTIFACTS/COVERAGE/coverage_raw_js.json",
            "ARTIFACTS/COVERAGE/coverage_raw_py.json",
            "ARTIFACTS/COVERAGE/import_graph.json",
            "ARTIFACTS/COVERAGE/meaningful.json",
            "ARTIFACTS/COVERAGE/test-costs.json",
            "ARTIFACTS/COVERAGE/validation.json",
            "ARTIFACTS/TESTS/js-tests.json",
            "ARTIFACTS/TESTS/pytest-shards/shard-000.log",
            "ARTIFACTS/README.md",
            "ARTIFACTS/COVERAGE/README.md",
            "ARTIFACTS/TESTS/README.md",
            "ARTIFACTS/TESTS/pytest-shards/README.md",
            "COVERAGE/README.md",
            "TESTS/README.md",
            "TESTS/tests/README.md",
        },
    )


def test_package_does_not_shadow_third_party_coverage() -> None:
    """The ``coverage_tests`` package never hides the coverage library."""
    _ = import_module(name="exactus.tools.coverage_tests.core")
    library: ModuleType = import_module(name="coverage")
    location: Path = Path(str(object=library.__file__)).resolve()
    tools: Path = Constants.root / "exactus" / "tools"
    expect_false(condition=location.is_relative_to(tools))
    expect_true(condition=hasattr(library, "CoverageData"))


@pytest.fixture
def demo_copy(tmp_path: Path) -> Path:
    """Copy the demo fixture into a throwaway project.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root of the copied project.

    """
    target: Path = tmp_path / "demo"
    ignore: Callable[[str, list[str]], set[str]] = ignore_patterns(
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "EXACTUS_RESULTS",
        ".DS_Store",
    )
    _ = copytree(src=Constants.demo, dst=target, ignore=ignore)
    _ = copytree(
        src=Constants.root / "exactus" / "tests" / "demo",
        dst=target / "tests",
        ignore=ignore,
    )
    return target


def _run(project: Path, out: Path, *flags: str) -> int:
    """Run the coverage analyzer.

    Args:
        project: Project root.
        out: Report directory.
        *flags: Extra flags.

    Returns:
        The analyzer exit status.

    """
    return main(arguments=(str(object=project), "-o", str(object=out), *flags))


def test_parse_args_defaults() -> None:
    """Validation gates default to 80 percent and the run gate to 90."""
    options: Namespace = parse_args(arguments=("x",))
    expect_equal(actual=options.minimum, expected=80.0)
    expect_equal(actual=options.fail_under, expected=90.0)


def test_demo_combined_coverage(demo_copy: Path, tmp_path: Path) -> None:
    """Python and JavaScript coverage run together and gates pass.

    Args:
        demo_copy: Writable copy of the demo project.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(
        demo_copy,
        tmp_path / "out",
        "--minimum",
        "50",
        "--per-file-minimum",
        "10",
        "--average-minimum",
        "10",
    )
    expect_equal(actual=status, expected=0)
    expect_true(
        condition=(tmp_path / "out" / "raw_report.json").is_file()
        or any((tmp_path / "out").iterdir()),
    )


@pytest.mark.parametrize(
    "flags",
    [
        ("--no-js-coverage", "--no-branch", "--include-unreached"),
        ("--jobs", "2", "--critical", "server", "--critical-minimum", "1"),
        ("--fail-under", "1"),
        ("--source-root", "demo_app"),
        ("--pytest-arg=-x",),
    ],
)
def test_demo_flag_variants(
    flags: tuple[str, ...],
    demo_copy: Path,
    tmp_path: Path,
) -> None:
    """Optional flags are honored without crashing.

    Args:
        flags: Parametrized command-line flags.
        demo_copy: Writable copy of the demo project.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(demo_copy, tmp_path / "out", *flags)
    expect_in(member=status, container={0, 1, 2})


def test_unmet_gates_fail(demo_copy: Path, tmp_path: Path) -> None:
    """Impossible floors make the analyzer return a failing status.

    Args:
        demo_copy: Writable copy of the demo project.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(
        demo_copy,
        tmp_path / "out",
        "--minimum",
        "101",
        "--per-file-minimum",
        "101",
        "--average-minimum",
        "101",
    )
    expect_not_equal(actual=status, expected=0)


def test_project_without_tests(tmp_path: Path) -> None:
    """A project with no tests is handled without crashing.

    Args:
        tmp_path: Per-test temporary directory.

    """
    project: Path = tmp_path / "empty"
    project.mkdir()
    (project / "a.py").write_text(data="x = 1\n", encoding="utf-8")
    expect_in(
        member=_run(project=project, out=tmp_path / "out"),
        container={0, 1, 2},
    )


@pytest.mark.parametrize("flag", ["--average-minimum", "--per-file-minimum"])
def test_per_file_gates_fail(
    flag: str,
    demo_copy: Path,
    tmp_path: Path,
) -> None:
    """Average and per-file floors fail the run when unmet.

    Args:
        flag: Parametrized command-line flag.
        demo_copy: Writable copy of the demo project.
        tmp_path: Per-test temporary directory.

    """
    status: int = _run(
        demo_copy,
        tmp_path / "out",
        "--minimum",
        "0",
        flag,
        "101",
    )
    expect_equal(actual=status, expected=1)


def _runner(root: Path, context_lines: int = 3) -> CombinedCoverageRunner:
    """Build a coverage runner over a scratch project.

    Args:
        root: Scratch project root.
        context_lines: Context lines embedded around uncovered runs.

    Returns:
        Runner configured for the scratch project.

    """
    return CombinedCoverageRunner(
        config=CoverageConfig(
            root=root,
            output=root / "out",
            source_roots=(root,),
            branch=False,
            fail_under=None,
            excluded_dirs=frozenset(),
            pytest_args=(),
            measure_js=False,
            context_lines=context_lines,
        ),
    )


def test_generated_skip_plugin_is_a_regular_package(tmp_path: Path) -> None:
    """Create the copied pytest helper in an explicit Python package.

    Args:
        tmp_path: Isolated generated coverage configuration directory.

    """
    work_dir_attribute: str = "_work_dir"
    work_dir: Path = cast(
        typ="Path",
        val=getattr(_runner(root=tmp_path), work_dir_attribute),
    )
    expect_equal(actual=work_dir.name, expected="tmp")
    method: str = "_coverage_arguments"
    arguments: Callable[..., tuple[str, ...]] = cast(
        typ="Callable[..., tuple[str, ...]]",
        val=getattr(_runner(root=tmp_path), method),
    )
    _ = arguments(items=(), config_path=tmp_path / "coverage.ini")
    expect_equal(actual=(tmp_path / "__init__.py").is_file(), expected=True)
    expect_equal(
        actual=(tmp_path / "exactus_skip_plugin.py").is_file(),
        expected=True,
    )


def test_skip_plugin_preserves_project_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plugin discovery preserves imports in nested Python processes.

    Args:
        tmp_path: Temporary plugin configuration directory.
        monkeypatch: Isolated project import environment.

    """
    monkeypatch.setenv(name="PYTHONPATH", value=str(object=Constants.root))
    method: str = "_execute_async"
    execute: Callable[..., Coroutine[None, None, CompletedProcess[bytes]]] = (
        cast(
            typ=(
                "Callable[..., Coroutine[None, None, CompletedProcess[bytes]]]"
            ),
            val=getattr(_runner(root=tmp_path), method),
        )
    )
    process: CompletedProcess[bytes] = run(
        main=execute(
            arguments=(
                "-c",
                (
                    "from exactus.tools.coverage_tests.skip_plugin import "
                    "Constants; print(Constants.skip_fields)"
                ),
                "exactus_skip_plugin",
                f"--rcfile={tmp_path / 'coverage.ini'}",
            ),
            cwd=tmp_path,
        ),
    )
    expect_equal(actual=process.returncode, expected=0)
    expect_equal(actual=process.stdout.strip(), expected=b"3")


def test_production_conftest_is_measured(tmp_path: Path) -> None:
    """Measure production conftests while omitting test fixtures.

    Args:
        tmp_path: Per-test temporary directory.

    """
    production: Path = tmp_path / "src" / "screenshot" / "conftest.py"
    fixture: Path = tmp_path / "tests" / "nested" / "conftest.py"
    for source in (production, fixture):
        source.parent.mkdir(parents=True, exist_ok=True)
        _ = source.write_text(data="value = 42\n", encoding="utf-8")
    method: str = "_write_coverage_config"
    write_config: Callable[..., Path] = cast(
        typ="Callable[..., Path]",
        val=getattr(_runner(root=tmp_path), method),
    )
    config: Path = write_config(name="coverage.ini")
    coverage: Coverage = Coverage(config_file=str(object=config))
    coverage.start()
    for source in (production, fixture):
        _ = run_path(path_name=str(object=source))
    coverage.stop()
    measured: set[str] = set(coverage.get_data().measured_files())
    expect_in(member=str(object=production), container=measured)
    expect_false(condition=str(object=fixture) in measured)


def test_owned_source_root_is_not_omitted_by_directory_name(
    tmp_path: Path,
) -> None:
    """Measure an explicit source root even when its name is excluded.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source_root: Path = tmp_path / "packages"
    source_root.mkdir()
    source: Path = source_root / "module.py"
    _ = source.write_text(data="value = 42\n", encoding="utf-8")
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=tmp_path,
            output=tmp_path / "out",
            source_roots=(source_root,),
            branch=False,
            fail_under=None,
            excluded_dirs=frozenset({"packages"}),
            pytest_args=(),
            measure_js=False,
        ),
    )
    method: str = "_write_coverage_config"
    write_config: Callable[..., Path] = cast(
        typ="Callable[..., Path]",
        val=getattr(runner, method),
    )
    config: Path = write_config(name="coverage.ini")
    expect_false(
        condition="*/packages/**" in config.read_text(encoding="utf-8"),
    )
    coverage: Coverage = Coverage(config_file=str(object=config))
    coverage.start()
    _ = run_path(path_name=str(object=source))
    coverage.stop()
    expect_in(
        member=str(object=source),
        container=set(coverage.get_data().measured_files()),
    )


def test_file_snippets_embed_context(tmp_path: Path) -> None:
    """Uncovered lines embed as context-windowed, flagged hunks.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(
        data="\n".join(f"line_{number} = {number}" for number in range(1, 31))
        + "\n",
        encoding="utf-8",
    )
    snippets: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(
            owner=_runner(root=tmp_path, context_lines=2),
            name="_file_snippets",
            relative="src/app.py",
            missing=(10, 11, 25),
        ),
    )
    hunks: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=snippets["hunks"],
    )
    expect_equal(actual=len(hunks), expected=2)
    first: dict[str, JsonValue] = hunks[0]
    expect_equal(actual=first["start"], expected=8)
    lines: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=first["lines"],
    )
    expect_equal(actual=len(lines), expected=6)
    hits: list[JsonValue] = [line["n"] for line in lines if line["hit"]]
    expect_equal(actual=hits, expected=[10, 11])
    expect_equal(actual=snippets["language"], expected="python")
    expect_equal(actual=snippets["context"], expected=2)
    expect_false(condition=bool(snippets["truncated"]))


def test_file_snippets_zero_and_negative_context(tmp_path: Path) -> None:
    """Zero context embeds only the uncovered lines; negatives clamp to zero.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(
        data="\n".join(f"line_{number} = {number}" for number in range(1, 31))
        + "\n",
        encoding="utf-8",
    )
    for requested in (0, -4):
        snippets: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=private_call(
                owner=_runner(root=tmp_path, context_lines=requested),
                name="_file_snippets",
                relative="src/app.py",
                missing=(10, 11, 25),
            ),
        )
        hunks: list[dict[str, JsonValue]] = cast(
            typ="list[dict[str, JsonValue]]",
            val=snippets["hunks"],
        )
        shown: list[JsonValue] = [
            line["n"]
            for hunk in hunks
            for line in cast(
                typ="list[dict[str, JsonValue]]",
                val=hunk["lines"],
            )
        ]
        expect_equal(actual=shown, expected=[10, 11, 25])
        expect_equal(actual=snippets["context"], expected=0)


def test_context_lines_option(sample_project: Path, tmp_path: Path) -> None:
    """``--context-lines`` defaults to 3 and is embedded in the report.

    Args:
        sample_project: Generated project with an uncovered function.
        tmp_path: Per-test temporary directory.

    """
    expect_equal(actual=parse_args(arguments=("x",)).context_lines, expected=3)
    expect_equal(
        actual=parse_args(
            arguments=("x", "--context-lines", "5"),
        ).context_lines,
        expected=5,
    )
    out: Path = tmp_path / "out"
    status: int = _run(
        sample_project,
        out,
        "--no-js-coverage",
        "--fail-under",
        "0",
        "--minimum",
        "0",
        "--context-lines",
        "1",
    )
    expect_in(member=status, container={0, 1})
    report: str = (out / "result.json").read_text(encoding="utf-8")
    expect_in(member='"context": 1', container=report)


def test_file_snippets_skips_unhighlightable(tmp_path: Path) -> None:
    """Non-source files and missing files embed no snippets.

    Args:
        tmp_path: Per-test temporary directory.

    """
    runner: CombinedCoverageRunner = _runner(root=tmp_path)
    for relative, missing in (
        ("README.md", (1,)),
        ("gone.py", (1,)),
        ("x.py", ()),
    ):
        expect_equal(
            actual=private_call(
                owner=runner,
                name="_file_snippets",
                relative=relative,
                missing=missing,
            ),
            expected={},
        )


def test_combined_tests_report_lists_failures_with_reasons(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    """The TESTS report states what ran, what failed, and why.

    Args:
        sample_project: Generated project whose test is made to fail.
        tmp_path: Per-test temporary directory.

    """
    _ = (sample_project / "tests" / "test_mod.py").write_text(
        data=(
            dedent(
                text=(
                    "    from pkg.mod import add\n    \n    \n    def test"
                    "_add():\n        assert add(1, 2) == 3\n    \n    \n "
                    "   def test_broken():\n        assert add(1, 2) == 99"
                    ", 'wrong sum'\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    out: Path = tmp_path / "COVERAGE_TESTS"
    status: int = _run(sample_project, out, "--no-js-coverage")
    expect_equal(actual=status, expected=1)
    report: str = (out / "TESTS" / "result.md").read_text(encoding="utf-8")
    for expected in (
        "# Combined Tests Report",
        "## Failed tests and why",
        "test_broken",
        "wrong sum",
        "## Results by group",
        "## Shards",
    ):
        expect_in(member=expected, container=report)
    expect_true(condition=(out / "TESTS" / "result.json").is_file())
    expect_true(condition=(out / "TESTS" / "result_web").is_dir())


class FdStream:
    """Stream stand-in exposing a real process descriptor."""

    def __init__(self, *, descriptor: int) -> None:
        """Remember the descriptor.

        Args:
            descriptor: Process-level descriptor number.

        """
        self.descriptor: int = descriptor

    def fileno(self) -> int:
        """Return the descriptor.

        Returns:
            The wrapped descriptor.

        """
        return self.descriptor

    def flush(self) -> None:
        """Accept flushes."""


@pytest.fixture
def tiny_project(tmp_path: Path) -> Path:
    """Create a one-module package with one passing and one failing test.

    A ``node:test`` file exercises the JavaScript lane as well.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root of the generated project.

    """
    root: Path = tmp_path / "tiny"
    files: dict[str, str] = {
        "pkg/__init__.py": "",
        "pkg/calc.py": "def add(a, b):\n    return a + b\n",
        "tests/test_calc.py": (
            dedent(
                text=(
                    "    from pkg.calc import add\n    \n    \n    def tes"
                    "t_ok():\n        assert add(1, 2) == 3\n    \n    \n "
                    "   def test_bad():\n        assert add(1, 2) == 4, 'b"
                    "ad sum'\n    "
                ),
            )
        ),
        "lib/twice.mjs": "export const twice = (n) => n * 2;\n",
        "tests/twice.test.mjs": (
            dedent(
                text=(
                    '    import test from "node:test";\n    import assert '
                    'from "node:assert/strict";\n    import { twice } from'
                    ' "../lib/twice.mjs";\n    \n    test("twice", () => a'
                    "ssert.equal(twice(2), 4));\n    "
                ),
            )
        ),
    }
    name: str
    text: str
    for name, text in files.items():
        path: Path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(data=text, encoding="utf-8")
    return root


def _tree(*, output: Path) -> frozenset[str]:
    """List an output tree, collapsing each ``result_web`` to its name.

    Args:
        output: Tool output directory.

    Returns:
        POSIX paths relative to ``output``.

    """
    found: set[str] = set()
    path: Path
    for path in output.rglob(pattern="*"):
        relative: str = path.relative_to(output).as_posix()
        head: str
        head, marker, _ = relative.partition("result_web")
        if marker:
            found.add(f"{head}result_web/")
        elif path.is_file():
            found.add(relative)
    return frozenset(found)


def test_tiny_project_output_tree(
    tiny_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing coverage gate ignores test failures and writes the tree.

    Args:
        tiny_project: Package with one passing and one failing test.
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="off")
    monkeypatch.setattr(target=ent, name="argv", value=["exactus"])
    monkeypatch.setattr(
        target=ent,
        name="stdout",
        value=FdStream(descriptor=1),
    )
    monkeypatch.setattr(
        target=ent,
        name="stderr",
        value=FdStream(descriptor=2),
    )
    for name in (
        "EXACTUS_RUN_ID",
        "EXACTUS_PIPELINE_RUN_ID",
        "EXACTUS_COLLECT_FILES",
    ):
        monkeypatch.delenv(name=name, raising=False)
    output: Path = tmp_path / "EXACTUS_RESULTS" / "COVERAGE_TESTS"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="coverage_tests",
        title="Coverage Exactus",
        main=partial(
            main,
            arguments=(
                str(object=tiny_project),
                "-o",
                str(object=output),
                "--jobs",
                "1",
                "--fail-under",
                "0",
            ),
        ),
        output=output,
    )
    expect_equal(actual=result.exit_code, expected=1)
    expect_equal(
        actual=_tree(output=output) - {"ARTIFACTS/steps.txt"},
        expected=Constants.tree,
    )
    coverage_report: str = (output / "result.md").read_text(encoding="utf-8")
    for expected in ("test_bad", "bad sum", "Failed tests"):
        expect_in(member=expected, container=coverage_report)
    for excluded in ("Test execution", "Test logs"):
        expect_not_in(member=excluded, container=coverage_report)
    coverage_data: str = (output / "result.json").read_text(encoding="utf-8")
    expect_not_in(member='"test_execution"', container=coverage_data)
    expect_not_in(member='"failed_tests"', container=coverage_data)
    summary: str = (output / "TESTS" / "result.md").read_text(encoding="utf-8")
    expect_in(member="test_bad", container=summary)
    expect_in(member="bad sum", container=summary)
    js: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(output / "ARTIFACTS" / "TESTS" / "js-tests.json").read_text(
                encoding="utf-8",
            ),
        ),
    )
    expect_equal(
        actual=(js["schema"], js["exit_code"], js["tests"]),
        expected=(
            "exactus.coverage-tests.js-tests/v1",
            0,
            ["tests/twice.test.mjs"],
        ),
    )
    expect_true(condition=isinstance(js["stdout_lines"], list))
    completion: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(
            s=(
                output / "ARTIFACTS" / "COVERAGE" / "completion.json"
            ).read_text(encoding="utf-8"),
        ),
    )
    expect_equal(
        actual=completion["coverage_file"],
        expected="coverage_raw_py.json",
    )
    for report in ("result.json", "COVERAGE/result.json"):
        payload: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=loads(s=(output / report).read_text(encoding="utf-8")),
        )
        expect_in(member="coverage", container=payload)


def test_playwright_greenlet_body_is_measured(tmp_path: Path) -> None:
    """Measure executed browser code across Playwright greenlet switches.

    Args:
        tmp_path: Isolated source, test and report directory.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    (project / "browser_app.py").write_text(
        data=(
            dedent(
                text=(
                    "    from playwright.sync_api import sync_playwright\n"
                    "    \n    def version():\n        with sync_playwrigh"
                    "t() as playwright:\n            browser = playwright."
                    "chromium.launch()\n            try:\n                "
                    "return browser.version\n            finally:\n       "
                    "         browser.close()\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (project / "test_browser.py").write_text(
        data=(
            dedent(
                text=(
                    "    from browser_app import version\n    \n    def te"
                    "st_browser_version():\n        assert version().split"
                    "('.')[0].isdigit()\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    status: int = _run(
        project,
        tmp_path / "out",
        "--fail-under",
        "100",
        "--per-file-minimum",
        "100",
        "--no-js-coverage",
    )
    expect_equal(actual=status, expected=0)


def test_group_reports_do_not_inherit_other_group_failures(
    sample_project: Path,
    tmp_path: Path,
) -> None:
    """Keep passing and skipped groups green when another group fails.

    Args:
        sample_project: Project with an existing passing root test group.
        tmp_path: Report directory.

    """
    good: Path = sample_project / "tests/good"
    bad: Path = sample_project / "tests/bad"
    good.mkdir()
    bad.mkdir()
    (good / "test_healthy.py").write_text(
        data=(
            dedent(
                text=(
                    "    import pytest\n    from pkg.mod import add\n    "
                    "\n    def test_pass():\n        assert add(1, 2) == 3"
                    "\n    \n    def test_skip():\n        pytest.skip('Op"
                    "tional fixture unavailable')\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    (bad / "test_broken.py").write_text(
        data=(
            dedent(
                text=(
                    "    def test_fail():\n        assert False, 'Intentio"
                    "nal regression fixture'\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    out: Path = tmp_path / "out"
    status: int = _run(sample_project, out, "--jobs", "1", "--no-js-coverage")
    expect_equal(actual=status, expected=1)
    overall: dict[str, JsonValue] = loads(
        s=(out / "TESTS/result.json").read_text(encoding="utf-8"),
    )
    expect_equal(actual=overall["status"], expected="FAIL")
    for group, expected in (
        ("tests", "PASS"),
        ("tests_good", "PASS"),
        ("tests_bad", "FAIL"),
    ):
        report: dict[str, JsonValue] = loads(
            s=(out / f"TESTS/{group}/result.json").read_text(encoding="utf-8"),
        )
        expect_equal(actual=report["status"], expected=expected)
        expect_equal(actual=report["passed"], expected=expected == "PASS")
        manifest: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=report["test_execution"],
        )
        failures: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=manifest["failed_tests"],
        )
        expect_equal(actual=len(failures), expected=int(expected == "FAIL"))
        markdown: str = (out / f"TESTS/{group}/result.md").read_text(
            encoding="utf-8",
        )
        expect_in(member=f"Status: **{expected}**", container=markdown)
        expect_true(
            condition=(out / f"TESTS/{group}/result_web/data.json").is_file(),
        )


def test_v8_offsets_after_astral_unicode_keep_the_correct_line(
    tmp_path: Path,
) -> None:
    """Attribute UTF-16 browser ranges after emoji to their source line.

    Args:
        tmp_path: Temporary source directory.

    """
    source: str = 'const icon = "😀";\nthrow Error("missing");\n'
    path: Path
    path = tmp_path / "unicode.js"
    start: int
    end: int
    path.write_text(data=source, encoding="utf-8")
    result: JsFileCoverage
    start = (
        len(source.splitlines(keepends=True)[0].encode(encoding="utf-16-le"))
        // 2
    )
    end = len(source.encode(encoding="utf-16-le")) // 2
    result = cast(
        typ="JsFileCoverage",
        val=private_call(
            owner=CombinedCoverageRunner,
            name="_script_line_coverage",
            path=path,
            ranges=((0, end, 1), (start, end, 0)),
        ),
    )
    expect_equal(actual=result.covered, expected=frozenset({1}))
    expect_equal(actual=result.executable, expected=frozenset({1, 2}))


def test_excuse_shortfalls_filters_javascript_below_minimum(
    tmp_path: Path,
) -> None:
    """Drop an excused JavaScript file from the manifest and totals.

    Args:
        tmp_path: Tmp path.

    """
    source: Path = tmp_path / "mod.js"
    _ = source.write_text(
        data="export const used = () => 1;\n",
        encoding="utf-8",
    )
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=tmp_path,
            output=tmp_path / "out",
            source_roots=(tmp_path,),
            branch=False,
            fail_under=None,
            excluded_dirs=frozenset(),
            pytest_args=(),
            measure_js=False,
            per_file_minimum=80.0,
            meaningful=MeaningfulConfig(minimum_level=UnitTestLevel.TEST_3),
        ),
    )
    js_result: JsCoverageResult = JsCoverageResult(
        tests=(),
        files={
            "mod.js": JsFileCoverage(
                covered=frozenset({1}),
                executable=frozenset({1, 2, 3, 4}),
            ),
        },
        unreached=(),
        status=0,
    )
    js_manifest: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=private_call(owner=runner, name="_js_manifest", result=js_result),
    )
    snapshot: CoverageSnapshot
    meaningful: MeaningfulResult
    snapshot, meaningful = cast(
        typ="tuple[CoverageSnapshot, MeaningfulResult]",
        val=private_call(
            owner=runner,
            name="_excuse_shortfalls",
            graph=ImportGraph(tests=(), targets=(), ignored_imports=()),
            unreached=(),
            omitted=(),
            snapshot=CoverageSnapshot(
                report={"files": {}, "totals": {}},
                js_result=js_result,
                js_manifest=js_manifest,
            ),
            meaningful=MeaningfulResult(rows=(), artifact={}),
        ),
    )
    manifest: JsonValue = snapshot.js_manifest
    expect_true(condition=manifest is not None)
    manifest = cast(typ="dict[str, JsonValue]", val=manifest)
    expect_equal(actual=manifest["files"], expected=[])
    expect_equal(actual=manifest["files_measured"], expected=0)
    expect_equal(actual=manifest["percent_covered"], expected=100.0)
    expect_true(
        condition=any(
            row.get("origin") == "shortfall" for row in meaningful.rows
        ),
    )
    expect_in(member="mod.js", container=meaningful.excused)
