# Copyright (c) 2026 Project contributors
"""Exercise the standalone coverage CLI and malformed browser evidence."""

from __future__ import annotations

from sys import modules
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_in, private_call
from exactus.tools.coverage_tests import core

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


def _config(*, root: Path, jobs: int = 2) -> core.CoverageConfig:
    """Build an isolated coverage configuration.

    Args:
        root: Temporary project root.
        jobs: Concurrent pytest shard limit.

    Returns:
        Coverage configuration rooted in the temporary project.

    """
    return core.CoverageConfig(
        root=root,
        output=root / "out",
        source_roots=(root,),
        branch=True,
        fail_under=None,
        excluded_dirs=core.CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
        pytest_args=(),
        jobs=jobs,
    )


def test_discovery_prunes_outputs_but_keeps_nested_test_groups(
    tmp_path: Path,
) -> None:
    """Discovery ignores generated roots without hiding groups under tests.

    Args:
        tmp_path: Isolated project tree.

    """
    tests: Path = tmp_path / "tests"
    nested: Path = tests / "packages"
    excluded: Path = tmp_path / "dist"
    hidden: Path = tmp_path / ".hidden"
    for directory in (nested, excluded, hidden):
        directory.mkdir(parents=True)
    expected: tuple[Path, ...] = (
        tmp_path / "test_root.py",
        tests / "test_group.py",
        nested / "test_nested.py",
    )
    path: Path
    for path in (
        *expected,
        excluded / "test_excluded.py",
        hidden / "test_hidden.py",
    ):
        path.write_text(
            data="def test_value():\n    assert True\n",
            encoding="utf-8",
        )
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    expect_equal(
        actual=runner.discover_tests(),
        expected=tuple(sorted(path.resolve() for path in expected)),
    )


def test_collection_progress_cannot_overtake_test_execution(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep collection below the execution span so progress never reverses.

    Args:
        tmp_path: Isolated command working directory.
        monkeypatch: Progress publisher replacement.

    """
    updates: list[core.Progress] = []

    def retain(*, progress: core.Progress) -> None:
        """Retain one published update.

        Args:
            progress: Update emitted by the command batch.

        """
        updates.append(progress)

    monkeypatch.setattr(target=core, name="publish_progress", value=retain)
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    _ = runner.execute_many(
        argument_sets=(("-c", "pass"),),
        cwd=tmp_path,
        progress=("pytest collect", (0.1, 0.2)),
    )
    _ = runner.execute_many(argument_sets=(("-c", "pass"),), cwd=tmp_path)
    expect_equal(
        actual=[update.step for update in updates],
        expected=["pytest collect", "pytest shard"],
    )
    expect_equal(
        actual=[update.span for update in updates],
        expected=[(0.1, 0.2), (0.2, 0.6)],
    )


def test_file_shards_are_balanced_without_duplicate_collection(
    tmp_path: Path,
) -> None:
    """File-level sharding assigns every module once by estimated cost.

    Args:
        tmp_path: Isolated project tree.

    """
    counts: tuple[tuple[str, int], ...] = (
        ("test_large.py", 3),
        ("test_medium.py", 1),
        ("test_small.py", 0),
    )
    tests: tuple[Path, ...] = tuple(tmp_path / name for name, _count in counts)
    path: Path
    count: int
    for path, (_name, count) in zip(tests, counts, strict=True):
        path.write_text(
            data="".join(
                f"def test_case_{index}() -> None:\n    pass\n\n\n"
                for index in range(count)
            ),
            encoding="utf-8",
        )
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    shards: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=runner,
            name="_balanced_test_shards",
            tests=tests,
        ),
    )
    expect_equal(
        actual=shards,
        expected=(("test_large.py",), ("test_medium.py", "test_small.py")),
    )


def test_node_shards_split_large_test_modules(tmp_path: Path) -> None:
    """Node-level sharding can distribute one slow module across workers.

    Args:
        tmp_path: Isolated project tree.

    """
    test_file: Path = tmp_path / "test_large.py"
    test_file.write_text(
        data="def test_one(): pass\ndef test_two(): pass\n",
        encoding="utf-8",
    )
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    nodes: tuple[str, ...] = (
        "test_large.py::test_one",
        "test_large.py::test_two",
    )
    shards: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=runner,
            name="_balanced_test_shards",
            tests=(test_file,),
            items=nodes,
        ),
    )
    expect_equal(actual=shards, expected=((nodes[0],), (nodes[1],)))


def test_node_collection_uses_exact_pytest_ids(tmp_path: Path) -> None:
    """Collection preserves parametrized node IDs for worker assignment.

    Args:
        tmp_path: Isolated project tree.

    """
    test_file: Path = tmp_path / "test_nodes.py"
    test_file.write_text(
        data=(
            dedent(
                text=(
                    "    import pytest\n    \n    \n    @pytest.mark.param"
                    "etrize('value', [1, 2])\n    def test_value(value: in"
                    "t) -> None:\n        assert value > 0\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    nodes: tuple[str, ...] = cast(
        typ="tuple[str, ...]",
        val=private_call(
            owner=runner,
            name="_collect_pytest_nodes",
            tests=(test_file,),
        ),
    )
    expect_equal(
        actual=nodes,
        expected=(
            "test_nodes.py::test_value[1]",
            "test_nodes.py::test_value[2]",
        ),
    )


def test_node_shards_isolate_standalone_packages(tmp_path: Path) -> None:
    """Independent package projects never share a pytest interpreter.

    Args:
        tmp_path: Isolated project tree.

    """
    first: Path = tmp_path / "tests" / "packages" / "first" / "test_a.py"
    second: Path = tmp_path / "tests" / "packages" / "second" / "test_b.py"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(data="def test_a(): pass\n", encoding="utf-8")
    second.write_text(data="def test_b(): pass\n", encoding="utf-8")
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    nodes: tuple[str, ...] = (
        "tests/packages/first/test_a.py::test_a",
        "tests/packages/second/test_b.py::test_b",
    )
    shards: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=runner,
            name="_isolated_node_shards",
            tests=(first, second),
            nodes=nodes,
        ),
    )
    expect_equal(actual=shards, expected=((nodes[0],), (nodes[1],)))


def test_package_meta_tests_require_an_exclusive_shard() -> None:
    """Package-wide launchers run after package-specific test processes."""
    exclusive: bool = cast(
        typ="bool",
        val=private_call(
            owner=core.CombinedCoverageRunner,
            name="_exclusive_shard",
            shard=("exactus/tests/packages/test_packages.py::test_all",),
        ),
    )
    ordinary: bool = cast(
        typ="bool",
        val=private_call(
            owner=core.CombinedCoverageRunner,
            name="_exclusive_shard",
            shard=(
                "exactus/tests/packages/markdown/test_engine.py::test_one",
            ),
        ),
    )
    expect_equal(actual=(exclusive, ordinary), expected=(True, False))


def test_child_environment_drops_live_coordination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coverage subprocesses cannot mutate their parent's live registry.

    Args:
        monkeypatch: Isolate the process environment used by the helper.

    """
    values: dict[str, str] = {
        "EXACTUS_ORCHESTRATED": "1",
        "EXACTUS_PIPELINE_RUN_ID": "pipeline",
        "EXACTUS_REGISTRY": "/live/runs.db",
        "EXACTUS_RUN_ID": "coverage",
        "EXACTUS_TOOL": "coverage_tests",
    }
    name: str
    value: str
    for name, value in values.items():
        monkeypatch.setenv(name=name, value=value)
    child: dict[str, str] = cast(
        typ="dict[str, str]",
        val=private_call(owner=core, name="_child_environ"),
    )
    expect_equal(
        actual=tuple(name for name in values if name in child),
        expected=(),
    )


def test_standalone_cli_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve repeated source roots and preserve every standalone CLI option.

    Args:
        tmp_path: Isolated project with an explicitly maintained source tree.
        monkeypatch: Restore process arguments after parsing.

    """
    source: Path = tmp_path / "src"
    source.mkdir()
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "coverage-tests",
            str(object=tmp_path),
            "--source-root",
            "src",
            "--source-root",
            str(object=source),
            "--output",
            "reports",
            "--no-branch",
            "--no-js-coverage",
            "--fail-under",
            "81",
            "--per-file-minimum",
            "79",
            "--exclude-dir",
            "generated",
            "--jobs",
            "2",
            "--shard-by",
            "node",
            "--context-lines",
            "-3",
            "--",
            "-q",
        ],
    )
    config: core.CoverageConfig = core.CommandLine.parse()
    expect_equal(actual=config.root, expected=tmp_path)
    expect_equal(actual=config.source_roots, expected=(source,))
    expect_equal(actual=config.output, expected=tmp_path / "reports")
    expect_equal(actual=config.branch, expected=False)
    expect_equal(actual=config.measure_js, expected=False)
    expect_equal(actual=config.fail_under, expected=81)
    expect_equal(actual=config.per_file_minimum, expected=79)
    expect_equal(actual=config.context_lines, expected=0)
    expect_equal(actual=config.jobs, expected=2)
    expect_equal(actual=config.shard_by, expected="node")
    expect_equal(actual=config.pytest_args, expected=("-q",))
    expect_in(member="generated", container=config.excluded_dirs)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["coverage-tests", str(object=tmp_path)],
    )
    defaulted: core.CoverageConfig = core.CommandLine.parse()
    expect_equal(actual=defaulted.source_roots, expected=(source,))
    expect_equal(actual=defaulted.per_file_minimum, expected=80)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "coverage-tests",
            str(object=tmp_path),
            "--source-root",
            "absent",
        ],
    )
    with pytest.raises(
        expected_exception=core.CoverageRunError,
        match="existing directory",
    ):
        core.CommandLine.parse()


def test_project_root_boundaries(tmp_path: Path) -> None:
    """Widen source subtrees only inside their nearest project marker.

    Args:
        tmp_path: Isolated project layout.

    """
    source: Path = tmp_path / "src"
    source.mkdir()
    tests: Path = tmp_path / "tests"
    tests.mkdir()
    expect_equal(
        actual=core.CommandLine.project_root(root=source),
        expected=tmp_path,
    )
    expect_equal(
        actual=core.CommandLine.target_source_roots(
            requested=source,
            root=tmp_path,
        ),
        expected=(source,),
    )
    expect_equal(
        actual=core.CommandLine.target_source_roots(
            requested=tmp_path,
            root=tmp_path,
        ),
        expected=(source,),
    )
    (source / "pyproject.toml").write_text(data="", encoding="utf-8")
    expect_equal(
        actual=core.CommandLine.project_root(root=source),
        expected=source,
    )
    expect_equal(
        actual=core.CommandLine.default_source_roots(root=tests),
        expected=(tests,),
    )


@pytest.mark.parametrize("status", [0, 1])
def test_standalone_main_preserves_exit_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    """Exit with the runner result without performing a nested full test run.

    Args:
        tmp_path: Isolated project root.
        monkeypatch: Restore argument and runner seams after the assertion.
        status: Successful or failing runner result to propagate.

    """
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["coverage-tests", str(object=tmp_path)],
    )

    def run_stub(_self: core.CombinedCoverageRunner) -> int:
        """Return the controlled runner status.

        Args:
            _self: Runner instance whose subprocess work is replaced.

        Returns:
            Status expected from the standalone entry point.

        """
        return status

    monkeypatch.setattr(
        target=core.CombinedCoverageRunner,
        name="run",
        value=run_stub,
    )
    with pytest.raises(expected_exception=SystemExit) as error:
        core.main()
    expect_equal(actual=error.value.code, expected=status)
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "coverage-tests",
            str(object=tmp_path),
            "--source-root",
            "missing",
        ],
    )
    with pytest.raises(
        expected_exception=SystemExit,
        match="existing directory",
    ):
        core.main()


def test_invalid_v8_ranges_are_ignored() -> None:
    """Retain valid V8 intervals while rejecting malformed nested entries."""
    malformed: dict[str, JsonValue] = {
        "functions": [
            None,
            {"ranges": None},
            {
                "ranges": [
                    None,
                    {"startOffset": "bad", "endOffset": 4, "count": 1},
                    {"startOffset": 4, "endOffset": 4, "count": 1},
                    {"startOffset": 0, "endOffset": 4, "count": 1},
                ],
            },
        ],
    }
    expect_equal(
        actual=private_call(
            owner=core.CombinedCoverageRunner,
            name="_script_ranges",
            script=malformed,
        ),
        expected=((0, 4, 1),),
    )
    expect_equal(
        actual=private_call(
            owner=core.CombinedCoverageRunner,
            name="_script_ranges",
            script={"functions": None},
        ),
        expected=(),
    )
    expect_equal(
        actual=private_call(
            owner=core.CombinedCoverageRunner,
            name="_script_url_path",
            url=None,
        ),
        expected=None,
    )
    expect_equal(
        actual=private_call(
            owner=core.CombinedCoverageRunner,
            name="_script_url_path",
            url="https://example.com/app.js",
        ),
        expected=None,
    )


def test_empty_and_missing_javascript_sources(tmp_path: Path) -> None:
    """Missing and empty files have no executable coverage ranges.

    Args:
        tmp_path: Directory holding the intentionally empty source.

    """
    empty: Path = tmp_path / "empty.js"
    empty.write_text(data="", encoding="utf-8")
    for path in (empty, tmp_path / "missing.js"):
        coverage: core.JsFileCoverage = cast(
            typ="core.JsFileCoverage",
            val=private_call(
                owner=core.CombinedCoverageRunner,
                name="_script_line_coverage",
                path=path,
                ranges=((0, 4, 1),),
            ),
        )
        expect_equal(actual=coverage.executable, expected=frozenset[int]())
        expect_equal(
            actual=private_call(
                owner=core.CombinedCoverageRunner,
                name="_js_percent",
                coverage=coverage,
            ),
            expected=100,
        )


def test_source_excludes_drop_measured_python_files(tmp_path: Path) -> None:
    """Exclude globs drop matching files from the measured module index.

    Args:
        tmp_path: Isolated project tree.

    """
    src: Path = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    kept: Path = src / "pkg" / "kept.py"
    dropped: Path = src / "pkg" / "generated.py"
    legacy: Path = src / "legacy_helper.py"
    for path in (kept, dropped, legacy):
        path.write_text(data="VALUE = 1\n", encoding="utf-8")
    index: core.LocalModuleIndex = core.LocalModuleIndex(
        root=tmp_path,
        source_roots=(src,),
        excluded_dirs=core.CoverageCoreTables.DEFAULT_EXCLUDED_DIRS,
        excludes=("src/pkg/generated.py", "**/legacy_*.py"),
    )
    expect_equal(
        actual=tuple(record.path for record in index.records),
        expected=(kept.resolve(),),
    )
    expect_equal(
        actual=index.excluded,
        expected=(legacy.resolve(), dropped.resolve()),
    )


def test_source_excludes_drop_measured_javascript(tmp_path: Path) -> None:
    """Exclude globs drop matching files from the JavaScript lane.

    Args:
        tmp_path: Isolated project tree.

    """
    src: Path = tmp_path / "src"
    src.mkdir()
    kept: Path = src / "kept.mjs"
    dropped: Path = src / "generated.mjs"
    for path in (kept, dropped):
        path.write_text(data="export const value = 1;\n", encoding="utf-8")
    config: core.CoverageConfig = core.replace(
        _config(root=tmp_path),
        source_roots=(src,),
        source_excludes=("src/generated.mjs",),
    )
    runner: core.CombinedCoverageRunner = core.CombinedCoverageRunner(
        config=config,
    )
    sources: tuple[Path, ...] = cast(
        typ="tuple[Path, ...]",
        val=private_call(owner=runner, name="_js_sources"),
    )
    expect_equal(actual=sources, expected=(kept.resolve(),))
