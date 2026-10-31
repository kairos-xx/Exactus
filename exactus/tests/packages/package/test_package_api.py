"""Tests for the unified package Python API."""

from pathlib import Path
from textwrap import dedent

import pytest

from exactus.packages.package import api
from exactus.packages.package.config import (
    BuildConfig,
    BundleConfig,
    PackageConfig,
    PipelineConfig,
    load_config,
)


def expect_equal[T](*, actual: T, expected: T) -> None:
    """Require equal values.

    Args:
        actual: Observed value.
        expected: Required value.

    """
    if actual != expected:
        pytest.fail(reason=f"{actual!r} != {expected!r}")


def expect_true(*, condition: bool) -> None:
    """Require a true condition.

    Args:
        condition: Condition that must hold.

    """
    if not condition:
        pytest.fail(reason="expected a true condition")


def test_run_orders_selected_stages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Selected stages execute in canonical order.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    seen: list[str] = []

    def fake_load_config(
        *,
        root: Path,
        path: Path | None = None,
    ) -> PipelineConfig:
        """Return default stage settings without reading pyproject.

        Args:
            root: Project root.
            path: Unused explicit configuration path.

        Returns:
            Default pipeline configuration.

        """
        del path
        return PipelineConfig(root=root)

    def fake_build(*, config: BuildConfig, root: Path) -> api.StageResult:
        """Record the build stage instead of building.

        Args:
            config: Unused build-stage settings.
            root: Unused project root.

        Returns:
            Synthetic build stage result.

        """
        del config, root
        seen.append("build")
        return api.StageResult(name="build", outputs=())

    def fake_bundle(*, config: BundleConfig, root: Path) -> api.StageResult:
        """Record the bundle stage instead of bundling.

        Args:
            config: Unused bundle-stage settings.
            root: Unused project root.

        Returns:
            Synthetic bundle stage result.

        """
        del config, root
        seen.append("bundle")
        return api.StageResult(name="bundle", outputs=())

    def fake_package(*, config: PackageConfig, root: Path) -> api.StageResult:
        """Record the package stage instead of archiving.

        Args:
            config: Unused package-stage settings.
            root: Unused project root.

        Returns:
            Synthetic package stage result.

        """
        del config, root
        seen.append("package")
        return api.StageResult(name="package", outputs=())

    monkeypatch.setattr(target=api, name="load_config", value=fake_load_config)
    monkeypatch.setattr(target=api, name="build", value=fake_build)
    monkeypatch.setattr(target=api, name="bundle", value=fake_bundle)
    monkeypatch.setattr(target=api, name="package", value=fake_package)
    result: api.RunResult = api.run(
        root=tmp_path,
        package_stage=True,
        build_stage=True,
        bundle_stage=True,
    )
    expect_equal(actual=seen, expected=["build", "bundle", "package"])
    expect_equal(
        actual=tuple(stage.name for stage in result.stages),
        expected=("build", "bundle", "package"),
    )


def test_run_defaults_to_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No configured stages preserves package-only compatibility.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """

    def fake_load_config(
        *,
        root: Path,
        path: Path | None = None,
    ) -> PipelineConfig:
        """Return default stage settings without reading pyproject.

        Args:
            root: Project root.
            path: Unused explicit configuration path.

        Returns:
            Default pipeline configuration.

        """
        del path
        return PipelineConfig(root=root)

    def fake_package(*, config: PackageConfig, root: Path) -> api.StageResult:
        """Record the package stage instead of archiving.

        Args:
            config: Unused package-stage settings.
            root: Unused project root.

        Returns:
            Synthetic package stage result.

        """
        del config, root
        return api.StageResult(name="package", outputs=())

    monkeypatch.setattr(target=api, name="load_config", value=fake_load_config)
    monkeypatch.setattr(target=api, name="package", value=fake_package)
    result: api.RunResult = api.run(root=tmp_path)
    expect_equal(
        actual=tuple(stage.name for stage in result.stages),
        expected=("package",),
    )


def _noop(*args: object, **kwargs: object) -> None:
    """Swallow any call signature during monkey-patched tests.

    Args:
        *args: Positional arguments to ignore.
        **kwargs: Keyword arguments to ignore.

    """
    del args, kwargs


def test_build_expands_target_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Target names, groups and ``all`` expand to concrete targets.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    seen: list[str] = []

    def fake_build_check(
        *,
        target: Path,
        kept: frozenset[Path] | None,
        self_test: bool,
    ) -> None:
        """Capture the produced check executable path.

        Args:
            target: Check executable path.
            kept: Unused preserved bundle leaves.
            self_test: Unused self-diagnostic opt-in flag.

        """
        del kept, self_test
        seen.append(str(object=target))

    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    monkeypatch.setattr(target=api, name="build_check", value=fake_build_check)
    monkeypatch.setattr(target=api, name="build_dist", value=_noop)
    monkeypatch.setattr(target=api, name="build_tree", value=_noop)
    monkeypatch.setattr(target=api, name="kept_bundle_leaves", value=_noop)
    config: BuildConfig = BuildConfig(
        enabled=True,
        check=True,
        dist=False,
        tree=False,
        targets=("all",),
    )
    result: api.StageResult = api.build(config=config, root=tmp_path)
    expect_equal(actual=result.name, expected="build")
    expect_equal(actual=len(result.outputs), expected=1)


def test_build_falls_back_to_auto_host_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty target list with ``auto`` resolves to the host target.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    monkeypatch.setattr(
        target=api,
        name="host_target",
        value=lambda: "linux-amd64",
    )
    monkeypatch.setattr(target=api, name="build_check", value=_noop)
    monkeypatch.setattr(target=api, name="build_dist", value=_noop)
    monkeypatch.setattr(target=api, name="build_tree", value=_noop)
    monkeypatch.setattr(target=api, name="kept_bundle_leaves", value=_noop)
    config: BuildConfig = BuildConfig(
        enabled=True,
        check=True,
        dist=False,
        tree=False,
        targets=(),
        exec_targets=(),
    )
    result: api.StageResult = api.build(config=config, root=tmp_path)
    expect_equal(actual=result.name, expected="build")
    expect_equal(actual=len(result.outputs), expected=1)


def test_build_raises_on_unknown_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unknown target name raises a clear ValueError.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    config: BuildConfig = BuildConfig(
        enabled=True,
        targets=("no-such-target",),
    )
    with pytest.raises(expected_exception=ValueError, match="unknown target"):
        _ = api.build(config=config, root=tmp_path)


def test_build_raises_when_auto_target_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Auto target detection failure raises a clear ValueError.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    monkeypatch.setattr(target=api, name="host_target", value=lambda: None)
    config: BuildConfig = BuildConfig(enabled=True, targets=("auto",))
    with pytest.raises(
        expected_exception=ValueError,
        match="cannot detect host bundle target",
    ):
        _ = api.build(config=config, root=tmp_path)


def test_load_config_reads_all_stages(tmp_path: Path) -> None:
    """The unified TOML parser reads stage-specific settings.

    Args:
        tmp_path: Isolated filesystem root.

    """
    path: Path = tmp_path / "pyproject.toml"
    path.write_text(
        data=dedent(
            text=(
                "    [tool.package.build]\n    enabled=true\n    targets=["
                '"all"]\n    [tool.package.bundle]\n    enabled=true\n    '
                'node-version="24"\n    part-bytes=123\n    [tool.package.'
                'package]\n    enabled=true\n    output="x.zip"\n    '
            ),
        ),
        encoding="utf-8",
    )
    config: PipelineConfig = load_config(root=tmp_path)
    expect_equal(actual=config.build.enabled, expected=True)
    expect_equal(actual=config.build.targets, expected=("all",))
    expect_equal(actual=config.bundle.node_version, expected="24")
    expect_equal(actual=config.bundle.part_bytes, expected=123)
    expect_equal(actual=config.package.output, expected=tmp_path / "x.zip")


def test_build_collects_every_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Check, dist and tree outputs all appear in the stage result.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    monkeypatch.setattr(target=api, name="build_check", value=_noop)
    monkeypatch.setattr(target=api, name="build_dist", value=_noop)
    monkeypatch.setattr(target=api, name="build_tree", value=_noop)
    config: BuildConfig = BuildConfig(
        enabled=True,
        check=True,
        dist=True,
        tree=True,
        targets=(),
    )
    result: api.StageResult = api.build(config=config, root=tmp_path)
    expect_equal(actual=len(result.outputs), expected=3)


def test_bundle_rejects_multi_target_output(tmp_path: Path) -> None:
    """An explicit output cannot pair with several bundle targets.

    Args:
        tmp_path: Isolated project root.

    """
    config: BundleConfig = BundleConfig(
        enabled=True,
        targets=("all",),
        output=tmp_path / "bundle.py",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="require one target",
    ):
        _ = api.bundle(config=config, root=tmp_path)


def test_bundle_builds_requested_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every requested target receives a builder with filtered options.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated project root.

    """
    builds: list[tuple[str, tuple[str, ...]]] = []

    class FakeBuilder:
        """Record constructor and build arguments instead of bundling."""

        def __init__(
            self,
            *,
            config: api.NativeBundleConfig,
            output: Path,
            rebuild_args: tuple[str, ...],
            parts_dir: Path | None,
            target: api.BuildTarget,
        ) -> None:
            """Capture the target-specific configuration.

            Args:
                config: Native bundle configuration.
                output: Bundle output path.
                rebuild_args: Unused rebuild arguments.
                parts_dir: Unused parts directory.
                target: Bundle target under construction.

            """
            del rebuild_args, parts_dir
            self._config: api.NativeBundleConfig = config
            self._output: Path = output
            self._target: api.BuildTarget = target

        def build(
            self,
            *,
            part_bytes: int,
            only: tuple[str, ...],
            rebuild: bool,
        ) -> Path:
            """Record the build request and return the output path.

            Args:
                part_bytes: Unused part size.
                only: Unused only-selection.
                rebuild: Unused rebuild flag.

            Returns:
                Recorded output path.

            """
            del part_bytes, only, rebuild
            builds.append((self._target.name, self._config.optional))
            return self._output

    monkeypatch.setattr(target=api, name="clear_conflict_copies", value=_noop)
    monkeypatch.setattr(target=api, name="write_content", value=_noop)
    monkeypatch.setattr(target=api, name="BundleBuilder", value=FakeBuilder)
    config: BundleConfig = BundleConfig(
        enabled=True,
        targets=("linux-musl-amd64", "macos-arm64"),
        optional=("playwright",),
        only=("pillow",),
    )
    result: api.StageResult = api.bundle(config=config, root=tmp_path)
    expect_equal(actual=len(result.outputs), expected=2)
    expect_equal(actual=dict(builds)["linux-musl-amd64"], expected=("pillow",))
    expect_equal(
        actual=dict(builds)["macos-arm64"],
        expected=("playwright", "pillow"),
    )


def test_package_archives_project_and_documents(tmp_path: Path) -> None:
    """Default packaging zips the tree and regenerates README files.

    Args:
        tmp_path: Isolated project root.

    """
    _ = (tmp_path / "module.py").write_text(data="x = 1\n", encoding="utf-8")
    result: api.StageResult = api.package(
        config=PackageConfig(enabled=True),
        root=tmp_path,
    )
    (archive,) = result.outputs
    expect_equal(actual=archive.suffix, expected=".zip")
    expect_true(condition=archive.is_file())
    expect_true(condition=(archive.parent / "README.md").is_file())
    expect_true(condition=(tmp_path / "packages" / "README.md").is_file())


def test_package_honours_explicit_output(tmp_path: Path) -> None:
    """An explicit archive path skips the generated documentation.

    Args:
        tmp_path: Isolated project root.

    """
    _ = (tmp_path / "module.py").write_text(data="x = 1\n", encoding="utf-8")
    output: Path = tmp_path / "custom.zip"
    result: api.StageResult = api.package(
        config=PackageConfig(enabled=True, output=output),
        root=tmp_path,
    )
    expect_equal(actual=result.outputs, expected=(output,))
    expect_true(condition=output.is_file())
    expect_true(condition=not (tmp_path / "packages").exists())
