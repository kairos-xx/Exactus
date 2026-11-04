# Copyright (c) 2026
"""Verify passing-baseline integrity and conservative incremental selection."""

from __future__ import annotations

from dataclasses import replace
from subprocess import CompletedProcess
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
    private_call,
)
from exactus.tools.common.process_control import read_json, write_json
from exactus.tools.coverage_tests import backend
from exactus.tools.coverage_tests.backend import TracerCapabilities
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CoverageConfig,
    LocalModuleIndex,
)
from exactus.tools.coverage_tests.incremental import ShardBaseline

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.coverage_tests.report import ReportInputs


def _config(*, root: Path) -> CoverageConfig:
    """Build an opt-in fixture config with no external service dependency.

    Args:
        root: Independent project root.

    Returns:
        Incremental test configuration.

    """
    return CoverageConfig(
        root=root,
        output=root / "artifacts" / "COVERAGE_TESTS",
        source_roots=(root,),
        branch=True,
        fail_under=90,
        excluded_dirs=frozenset(),
        pytest_args=(),
        incremental=True,
        measure_js=False,
    )


def test_only_passing_complete_snapshots_are_reused(tmp_path: Path) -> None:
    """Failed gates retain the old baseline; matching snapshots restore bytes.

    Args:
        tmp_path: Isolated cache tree.

    """
    cache: Path = tmp_path / "cache"
    source: Path = tmp_path / ".coverage.shard-0"
    source.write_bytes(data=b"coverage-data")
    shard: tuple[str, ...] = ("test_a.py::test_a",)
    baseline: ShardBaseline = ShardBaseline(
        directory=cache,
        identity="settings",
    )
    expect_equal(actual=baseline.layout(fallback=(shard,)), expected=(shard,))
    expect_equal(
        actual=baseline.restore(
            shard=shard,
            fingerprint="v1",
            target=tmp_path / "miss",
        ),
        expected=None,
    )
    baseline.stage(
        shard=shard,
        fingerprint="v1",
        source=source,
        result=CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"failed",
            stderr=b"",
        ),
    )
    baseline.commit(shards=(shard,), passed=True)
    expect_false(condition=(cache / "manifest.json").exists())
    baseline.stage(
        shard=shard,
        fingerprint="v1",
        source=source,
        result=CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"1 passed",
            stderr=b"",
        ),
    )
    baseline.commit(shards=(shard,), passed=False)
    expect_false(condition=(cache / "manifest.json").exists())
    baseline.commit(shards=(shard,), passed=True)
    loaded: ShardBaseline = ShardBaseline(directory=cache, identity="settings")
    target: Path = tmp_path / "restored" / ".coverage.shard-0"
    restored: CompletedProcess[bytes] | None = loaded.restore(
        shard=shard,
        fingerprint="v1",
        target=target,
    )
    expect_true(condition=restored is not None)
    expect_equal(
        actual=restored.stdout if restored is not None else b"",
        expected=b"1 passed",
    )
    expect_equal(
        actual=target.with_name(name=target.name + ".cached-0").read_bytes(),
        expected=b"coverage-data",
    )
    expect_equal(
        actual=loaded.restore(
            shard=shard,
            fingerprint="changed",
            target=target,
        ),
        expected=None,
    )
    expect_equal(
        actual=ShardBaseline(directory=cache, identity="changed").restore(
            shard=shard,
            fingerprint="v1",
            target=target,
        ),
        expected=None,
    )
    expect_equal(
        actual=loaded.layout(fallback=(("test_b.py",),)),
        expected=(("test_b.py",),),
    )


@pytest.mark.parametrize(
    "corruption",
    ["missing", "checksum", "path", "base64", "files"],
)
def test_corrupt_snapshot_falls_back_without_partial_restore(
    tmp_path: Path,
    corruption: str,
) -> None:
    """Corrupt metadata and payloads become complete cache misses.

    Args:
        tmp_path: Isolated cache tree.
        corruption: Malformed snapshot case.

    """
    cache: Path = tmp_path / "cache"
    source: Path = tmp_path / ".coverage.shard-0"
    source.write_bytes(data=b"data")
    shard: tuple[str, ...] = ("test_a.py",)
    baseline: ShardBaseline = ShardBaseline(
        directory=cache,
        identity="settings",
    )
    baseline.stage(
        shard=shard,
        fingerprint="v1",
        source=source,
        result=CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"passed",
            stderr=b"",
        ),
    )
    baseline.commit(shards=(shard,), passed=True)
    manifest: dict[str, JsonValue] = (
        read_json(path=cache / "manifest.json") or {}
    )
    entries: JsonValue = manifest.get("shards")
    expect_true(condition=isinstance(entries, dict))
    if not isinstance(entries, dict):
        return
    entry: JsonValue = entries.get(ShardBaseline.key(shard=shard))
    if not isinstance(entry, dict):
        pytest.fail(reason="fixture requires a stored shard")
    files: JsonValue = entry.get("files")
    if (
        not isinstance(files, list)
        or not files
        or not isinstance(files[0], str)
    ):
        pytest.fail(reason="fixture requires a stored data digest")
    if corruption == "missing":
        (cache / files[0]).unlink()
    elif corruption == "checksum":
        (cache / files[0]).write_bytes(data=b"different")
    elif corruption == "path":
        entry["files"] = cast(
            typ="list[JsonValue]",
            val=["../outside"],
        )
    elif corruption == "base64":
        entry["stdout"] = "!invalid"
    else:
        entry["files"] = []
    write_json(path=cache / "manifest.json", payload=manifest)
    target: Path = tmp_path / "scratch" / ".coverage.shard-0"
    expect_equal(
        actual=ShardBaseline(directory=cache, identity="settings").restore(
            shard=shard,
            fingerprint="v1",
            target=target,
        ),
        expected=None,
    )
    expect_false(condition=target.parent.exists())


@pytest.mark.parametrize(
    ("python", "branch", "green", "dynamic", "expected"),
    [
        ((3, 13), True, False, False, False),
        ((3, 14), True, False, False, True),
        ((3, 13), False, False, False, True),
        ((3, 14), True, True, False, False),
        ((3, 14), True, False, True, False),
    ],
)
def test_monitoring_preserves_tracing_requirements(
    python: tuple[int, int],
    *,
    branch: bool,
    green: bool,
    dynamic: bool,
    expected: bool,
) -> None:
    """Branch, greenlet, and dynamic-context workloads keep tracing.

    Args:
        python: Simulated interpreter capability.
        branch: Required branch coverage.
        green: Green-thread workload.
        dynamic: Dynamic contexts workload.
        expected: Expected monitoring eligibility.

    """
    expect_equal(
        actual=TracerCapabilities(
            python=python,
            coverage=(7, 16, 2),
            green_threads=green,
            dynamic_contexts=dynamic,
        ).sysmon(branch=branch),
        expected=expected,
    )


def test_transitive_inputs_invalidate_only_affected_shards(
    tmp_path: Path,
) -> None:
    """Static imports track dependency edits and dynamic imports widen impact.

    Args:
        tmp_path: Independent Python project.

    """
    test: Path = tmp_path / "test_a.py"
    module: Path = tmp_path / "sample.py"
    unrelated: Path = tmp_path / "unrelated.py"
    test.write_text(
        data="""\
from sample import value
""",
        encoding="utf-8",
    )
    module.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    unrelated.write_text(
        data="""\
other = 1
""",
        encoding="utf-8",
    )
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=_config(root=tmp_path),
    )
    index: LocalModuleIndex = LocalModuleIndex(
        root=tmp_path,
        source_roots=(tmp_path,),
        excluded_dirs=frozenset(),
        excludes=(),
    )
    # The same index is owned by run() before shard planning.
    monkeypatch: pytest.MonkeyPatch = pytest.MonkeyPatch()
    with monkeypatch.context() as patch:
        patch.setattr(target=runner, name="_incremental_index", value=index)
        sources: dict[Path, bytes] = {
            path: path.read_bytes() for path in (test, module, unrelated)
        }
        first: object = private_call(
            owner=runner,
            name="_shard_fingerprint",
            shard=(test.name,),
            sources=sources,
        )
        sources[unrelated] = b"other = 2\n"
        expect_equal(
            actual=private_call(
                owner=runner,
                name="_shard_fingerprint",
                shard=(test.name,),
                sources=sources,
            ),
            expected=first,
        )
        sources[module] = b"value = 2\n"
        expect_false(
            condition=private_call(
                owner=runner,
                name="_shard_fingerprint",
                shard=(test.name,),
                sources=sources,
            )
            == first,
        )
        sources[module] = b"value = __import__('external')\n"
        dynamic: object = private_call(
            owner=runner,
            name="_shard_fingerprint",
            shard=(test.name,),
            sources=sources,
        )
        sources[unrelated] = b"other = 3\n"
        expect_false(
            condition=private_call(
                owner=runner,
                name="_shard_fingerprint",
                shard=(test.name,),
                sources=sources,
            )
            == dynamic,
        )
    expect_false(
        condition=replace(
            _config(root=tmp_path),
            incremental=False,
        ).incremental,
    )


def test_incremental_run_reuses_coverage_and_reexecutes_changed_sources(
    tmp_path: Path,
) -> None:
    """Passing baseline reuse preserves measured totals and reacts to edits.

    Args:
        tmp_path: Isolated real pytest project.

    """
    module: Path = tmp_path / "sample.py"
    module.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    (tmp_path / "test_sample.py").write_text(
        data=(
            dedent(
                text="""\
    from sample import value

    def test_value():
        assert value in (1, 2)
    """,
            )
        ),
        encoding="utf-8",
    )
    config: CoverageConfig = _config(root=tmp_path)
    first: CombinedCoverageRunner = CombinedCoverageRunner(config=config)
    expect_equal(actual=first.run(), expected=0)
    baseline: Path = (
        config.output.parent
        / ".runtime"
        / "coverage-baseline"
        / "manifest.json"
    )
    expect_true(condition=baseline.is_file())
    first_report: ReportInputs | None = first.report_inputs
    second: CombinedCoverageRunner = CombinedCoverageRunner(config=config)
    expect_equal(actual=second.run(), expected=0)
    provenance: dict[str, JsonValue] = (
        read_json(
            path=config.output / "ARTIFACTS" / "COVERAGE" / "incremental.json",
        )
        or {}
    )
    expect_equal(actual=provenance.get("executed_shards"), expected=[])
    expect_equal(actual=provenance.get("reused_shards"), expected=[0])
    expect_true(
        condition=second.report_inputs is not None
        and first_report is not None,
    )
    if second.report_inputs is not None and first_report is not None:
        for key in ("files", "totals"):
            expect_equal(
                actual=second.report_inputs.coverage.get(key),
                expected=first_report.coverage.get(key),
            )
    module.write_text(
        data="""\
value = 2
""",
        encoding="utf-8",
    )
    third: CombinedCoverageRunner = CombinedCoverageRunner(config=config)
    expect_equal(actual=third.run(), expected=0)
    provenance = (
        read_json(
            path=config.output / "ARTIFACTS" / "COVERAGE" / "incremental.json",
        )
        or {}
    )
    expect_equal(actual=provenance.get("executed_shards"), expected=[0])
    expect_equal(actual=provenance.get("reused_shards"), expected=[])


@pytest.mark.parametrize("release", ["7.16.2", "7.6.0", "invalid"])
def test_monitoring_probe_respects_installed_backend(
    release: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Version parsing and explicit backend ownership remain conservative.

    Args:
        release: Simulated installed coverage release.
        monkeypatch: Scoped capability replacements.

    """

    def installed(*, distribution_name: str) -> str:
        """Return the controlled coverage version.

        Args:
            distribution_name: Requested metadata name.

        Returns:
            Controlled release string.

        """
        expect_equal(actual=distribution_name, expected="coverage")
        return release

    monkeypatch.delenv(name="COVERAGE_CORE", raising=False)
    monkeypatch.setattr(target=backend, name="version", value=installed)
    expect_false(
        condition=backend.monitoring_supported(
            branch=True,
            pytest_args=("--cov-context=test",),
        ),
    )
    monkeypatch.setenv(name="COVERAGE_CORE", value="ctrace")
    expect_false(
        condition=backend.monitoring_supported(branch=False, pytest_args=()),
    )
