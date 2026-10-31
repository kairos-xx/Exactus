# Copyright (c) 2026
"""Shared helpers: output resolution, filtering, and bundle discovery."""

from __future__ import annotations

from pathlib import Path
from platform import machine, system
from shutil import copyfile
from sys import path as sys_path
from typing import TYPE_CHECKING, Final, NoReturn, final
from zipfile import Path as ZipPath
from zipfile import ZipFile

import pytest

from exactus.packages.package.partition_fs import (
    PartitionStore,
    Recipe,
    RecipeScanner,
)
from exactus.packages.zstd_portable import export_package
from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    private_call,
    require,
    require_type,
)
from exactus.tools.common import cli as cm

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Callable


@final
class Constants:
    """Group module-level constants.

    Attributes:
        launcher_body: Grouped module constant.

    """

    launcher_body: Final[str] = "# Partitioned filesystem tool launcher\n"


def test_map_lanes_and_misc() -> None:
    """Lanes keep order and helpers pass values through."""
    expect_equal(
        actual=cm.map_lanes(lanes=[1], work=lambda x: x + 1),
        expected=[2],
    )
    expect_equal(
        actual=cm.map_lanes(lanes=[1, 2, 3], work=lambda x: x * 2),
        expected=[2, 4, 6],
    )
    expect_equal(actual=cm.consume(value=5), expected=5)
    expect_equal(actual=len(cm.heartbeat_timestamp()), expected=19)


def test_parse_common_arguments() -> None:
    """The shared parser exposes root, output, include and exclude."""
    options: Namespace = cm.parse_common_arguments(
        default_output="X",
        arguments=("proj", "--include", "a", "--exclude", "b"),
    )
    expect_equal(actual=options.include, expected=["a"])
    expect_equal(actual=options.exclude, expected=["b"])
    expect_equal(actual=options.output_dir, expected=Path("EXACTUS_RESULTS/X"))


def test_resolve_report_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pipeline override wins over CLI and default paths.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    expect_equal(
        actual=cm.resolve_report_output(requested=None, default="D"),
        expected=(tmp_path / "D").resolve(),
    )
    expect_equal(
        actual=cm.resolve_report_output(requested=Path("r"), default="D"),
        expected=(tmp_path / "r").resolve(),
    )
    monkeypatch.setenv(
        name="EXACTUS_REPORT_OUTPUT",
        value=str(object=tmp_path / "env"),
    )
    expect_equal(
        actual=cm.resolve_report_output(requested=None, default="D"),
        expected=(tmp_path / "env").resolve(),
    )


def test_resolve_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative outputs resolve against cwd or the project root.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = tmp_path / "root"
    root.mkdir()
    elsewhere: Path = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(path=elsewhere)
    absolute: Path = tmp_path / "abs"
    expect_equal(
        actual=cm.resolve_output(root=root, output=absolute),
        expected=absolute,
    )
    expect_equal(
        actual=cm.resolve_output(root=root, output=Path("OUT")),
        expected=(root / "OUT").resolve(),
    )
    (elsewhere / "exists").mkdir()
    expect_equal(
        actual=cm.resolve_output(root=root, output=Path("exists")),
        expected=(elsewhere / "exists").resolve(),
    )
    monkeypatch.chdir(path=root)
    expect_equal(
        actual=cm.resolve_output(root=root, output=Path("x")),
        expected=(root / "x").resolve(),
    )
    monkeypatch.setenv(
        name="EXACTUS_REPORT_OUTPUT",
        value=str(object=tmp_path / "env"),
    )
    expect_equal(
        actual=cm.resolve_output(root=root, output=Path("x")),
        expected=(tmp_path / "env").resolve(),
    )


def test_match_path(tmp_path: Path) -> None:
    """Include, exclude and default exclusions combine.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "a").mkdir()
    keep: Path = tmp_path / "a" / "x.py"
    keep.write_text(data="", encoding="utf-8")
    hidden: Path = tmp_path / ".git" / "y.py"
    hidden.parent.mkdir()
    hidden.write_text(data="", encoding="utf-8")
    expect_true(
        condition=cm.match_path(
            path=keep,
            root=tmp_path,
            includes=(),
            excludes=(),
        ),
    )
    expect_false(
        condition=cm.match_path(
            path=keep,
            root=tmp_path,
            includes=("b/*",),
            excludes=(),
        ),
    )
    expect_true(
        condition=cm.match_path(
            path=keep,
            root=tmp_path,
            includes=("a/*",),
            excludes=(),
        ),
    )
    expect_false(
        condition=cm.match_path(
            path=keep,
            root=tmp_path,
            includes=(),
            excludes=("a/*",),
        ),
    )
    expect_false(
        condition=cm.match_path(
            path=hidden,
            root=tmp_path,
            includes=(),
            excludes=(),
        ),
    )


def test_is_reports_tree(tmp_path: Path) -> None:
    """Report trees fingerprint by content, whatever their name.

    Args:
        tmp_path: Per-test temporary directory.

    """
    plain: Path = tmp_path / "src"
    plain.mkdir()
    expect_false(condition=cm.is_reports_tree(directory=plain))
    expect_false(condition=cm.is_reports_tree(directory=plain / "x.py"))
    runtime_root: Path = tmp_path / "REPORTS"
    (runtime_root / ".runtime").mkdir(parents=True)
    expect_true(condition=cm.is_reports_tree(directory=runtime_root))
    bundle: Path = tmp_path / "renamed" / "LINTS"
    bundle.mkdir(parents=True)
    expect_false(condition=cm.is_reports_tree(directory=bundle))
    _ = (bundle / "result.json").write_text(data="{}", encoding="utf-8")
    expect_false(condition=cm.is_reports_tree(directory=bundle))
    _ = (bundle / "result.md").write_text(data="# Lints\n", encoding="utf-8")
    expect_true(condition=cm.is_reports_tree(directory=bundle))
    running: Path = tmp_path / "out" / "DOCS"
    (running / "ARTIFACTS").mkdir(parents=True)
    expect_false(condition=cm.is_reports_tree(directory=running))
    _ = (running / "ARTIFACTS" / "@activity.json").write_text(
        data="{}",
        encoding="utf-8",
    )
    expect_true(condition=cm.is_reports_tree(directory=running))


def test_expand_paths(tmp_path: Path) -> None:
    """Literal and glob patterns expand to existing resolved paths.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "a.py").write_text(data="", encoding="utf-8")
    (tmp_path / "b.py").write_text(data="", encoding="utf-8")
    found: tuple[Path, ...] = cm.expand_paths(
        root=tmp_path,
        patterns=("a.py", "*.py", "missing.py", str(object=tmp_path / "b.py")),
    )
    expect_equal(
        actual=found,
        expected=(
            (tmp_path / "a.py").resolve(),
            (tmp_path / "b.py").resolve(),
        ),
    )


def test_executable_candidate(tmp_path: Path) -> None:
    """Non-executable files are repaired; directories are rejected.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "tool"
    script.write_text(data="#!/bin/sh\n", encoding="utf-8")
    script.chmod(mode=420)
    expect_equal(
        actual=private_call(
            owner=cm,
            name="_executable_candidate",
            candidate=script,
        ),
        expected=script.resolve(),
    )
    expect_none(
        value=private_call(
            owner=cm,
            name="_executable_candidate",
            candidate=tmp_path / "none",
        ),
    )
    expect_none(
        value=private_call(
            owner=cm,
            name="_executable_candidate",
            candidate=tmp_path,
        ),
    )


def test_platform_support(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only Linux on amd64-class machines is supported.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="system",
        value=Constant(value="Linux"),
    )
    monkeypatch.setattr(
        target=cm,
        name="machine",
        value=Constant(value="x86_64"),
    )
    expect_true(condition=cm.linter_platform_supported())
    monkeypatch.setattr(
        target=cm,
        name="machine",
        value=Constant(value="arm64"),
    )
    expect_false(condition=cm.linter_platform_supported())
    monkeypatch.setattr(
        target=cm,
        name="system",
        value=Constant(value="Darwin"),
    )
    expect_false(condition=cm.linter_platform_supported())


def test_toolchain_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit option, environment and discovered toolchains resolve.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    name: str = cm.ExactusCommonTables.LINTER_TOOLCHAIN
    tool: Path = tmp_path / "custom"
    tool.write_text(data="#!/bin/sh\n", encoding="utf-8")
    tool.chmod(mode=493)
    monkeypatch.setattr(
        target=cm,
        name="linter_platform_supported",
        value=Constant(value=False),
    )
    monkeypatch.delenv(
        name=cm.ExactusCommonTables.LINTER_TOOLCHAIN_ENV,
        raising=False,
    )
    expect_equal(
        actual=cm.resolve_linter_toolchain(root=tmp_path, option=tool),
        expected=tool,
    )
    expect_none(value=cm.resolve_linter_toolchain(root=tmp_path))
    monkeypatch.setenv(
        name=cm.ExactusCommonTables.LINTER_TOOLCHAIN_ENV,
        value=str(object=tool),
    )
    expect_equal(
        actual=cm.resolve_linter_toolchain(root=tmp_path),
        expected=tool,
    )
    monkeypatch.delenv(name=cm.ExactusCommonTables.LINTER_TOOLCHAIN_ENV)
    monkeypatch.setattr(
        target=cm,
        name="linter_platform_supported",
        value=Constant(value=True),
    )
    expect_none(value=cm.resolve_linter_toolchain(root=tmp_path))
    monkeypatch.setattr(
        target=cm,
        name="which",
        value=Constant(value=str(object=tool)),
    )
    expect_equal(
        actual=cm.resolve_linter_toolchain(root=tmp_path),
        expected=tool,
    )
    local: Path = tmp_path / name
    local.write_text(data="#!/bin/sh\n", encoding="utf-8")
    local.chmod(mode=493)
    expect_equal(
        actual=cm.resolve_linter_toolchain(root=tmp_path),
        expected=local.resolve(),
    )


def test_linter_command_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Toolchain, installed tool, bundle, then bare name.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="resolve_linter_toolchain",
        value=Constant(value=None),
    )
    monkeypatch.setattr(target=cm, name="which", value=Constant(value=None))
    monkeypatch.setattr(
        target=cm,
        name="resolve_exactus_tool_bundle",
        value=Constant(value=None),
    )
    expect_equal(
        actual=cm.linter_command(tool="ruff", root=tmp_path),
        expected=("ruff",),
    )
    monkeypatch.setattr(
        target=cm,
        name="resolve_exactus_tool_bundle",
        value=Constant(value=Path("/b")),
    )
    expect_equal(
        actual=cm.linter_command(tool="ruff", root=tmp_path),
        expected=("/b", "ruff"),
    )
    monkeypatch.setattr(
        target=cm,
        name="which",
        value=Constant(value="/bin/ruff"),
    )
    expect_equal(
        actual=cm.linter_command(tool="ruff", root=tmp_path),
        expected=("/bin/ruff",),
    )
    expect_equal(
        actual=cm.linter_command(
            tool="ruff",
            root=tmp_path,
            toolchain=Path("/t"),
        ),
        expected=("/t", "ruff"),
    )
    expect_equal(
        actual=cm.exactus_tool_prefix(tool="x", root=tmp_path),
        expected=("/bin/ruff",),
    )
    expect_equal(
        actual=cm.exactus_tool_command(tool="x", root=tmp_path),
        expected=("/bin/ruff",),
    )
    monkeypatch.setattr(target=cm, name="which", value=Constant(value=None))
    expect_equal(
        actual=cm.exactus_tool_prefix(tool="x", root=tmp_path),
        expected=("/b", "x"),
    )
    expect_equal(
        actual=cm.exactus_tool_command(tool="x", root=tmp_path),
        expected=("/b", "x"),
    )
    monkeypatch.setattr(
        target=cm,
        name="resolve_exactus_tool_bundle",
        value=Constant(value=None),
    )
    expect_none(value=cm.exactus_tool_prefix(tool="x", root=tmp_path))
    expect_equal(
        actual=cm.exactus_tool_command(tool="x", root=tmp_path),
        expected=("x",),
    )


def _bundle(root: Path, body: str = Constants.launcher_body) -> Path:
    """Write a fake offline-bundle launcher.

    Args:
        root: Directory to hold ``bundle/linux/glibc/amd64``.
        body: Launcher source.

    Returns:
        The launcher path.

    """
    launcher: Path = (
        root / "bundle" / "linux" / "glibc" / "amd64" / "__main__.py"
    )
    launcher.parent.mkdir(parents=True)
    launcher.write_text(data=body, encoding="utf-8")
    launcher.chmod(mode=493)
    (launcher.parent / "__init__.py").write_text(data="")
    for name in ("partition_fs.py", "partition_launcher.py"):
        copyfile(
            src=Path(__file__).resolve().parents[4]
            / "exactus"
            / "packages"
            / "package"
            / name,
            dst=launcher.parent / name,
        )
    copyfile(
        src=Path(__file__).resolve().parents[4]
        / "exactus/tools/common/conflict_copies.py",
        dst=launcher.parent / "conflict_copies.py",
    )
    export_package(
        os_name=system().lower(),
        machine=machine(),
        target=launcher.parent,
    )
    stage: Path = root / "staged"
    (stage / "python").mkdir(parents=True)
    (stage / "python" / "module.py").write_text(data="VALUE = 1\n")
    store: PartitionStore = PartitionStore(cache=root / "build-cache")
    recipe: Recipe = RecipeScanner(objects=store.objects).scan(
        root=stage,
        name="python-tools",
        metadata={
            "requires": [],
            "tools": {},
            "env": {"PYTHONPATH": ["python"]},
        },
    )
    store.build(
        recipes={"python-tools": recipe},
        output=launcher.parent / "data" / "parts" / "fs",
        platform="fixture",
    )
    return launcher


def test_bundle_resolution_and_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A launcher is found, executed, and exposed on the path.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="_host_bundle_dirs",
        value=Constant(value=()),
    )
    expect_none(value=cm.resolve_exactus_tool_bundle(root=tmp_path))
    expect_none(value=cm.exactus_bundle_cache(root=tmp_path))
    expect_false(condition=cm.activate_exactus_tool_bundle(root=tmp_path))
    monkeypatch.setattr(
        target=cm,
        name="_host_bundle_dirs",
        value=Constant(value=(Path("linux") / "glibc" / "amd64",)),
    )
    for name in ("LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH", "PYTHONPATH"):
        monkeypatch.setenv(name=name, value=cm.environ.get(name, ""))
    monkeypatch.setenv(
        name="EXACTUS_TOOLS_CACHE",
        value=str(object=tmp_path / "runtime-cache"),
    )
    launcher: Path = _bundle(root=tmp_path)
    expect_equal(
        actual=cm.resolve_exactus_tool_bundle(root=tmp_path),
        expected=launcher.resolve(),
    )
    cache: Path | None = cm.exactus_bundle_cache(root=tmp_path)
    cache = require(value=cache)
    saved_path: list[str] = list(sys_path)
    try:
        expect_true(condition=cm.activate_exactus_tool_bundle(root=tmp_path))
        expect_in(
            member=str(object=cache / "python-tools" / "python"),
            container=sys_path,
        )
        expect_true(condition=cm.activate_exactus_tool_bundle(root=tmp_path))
    finally:
        sys_path[:] = saved_path


@pytest.mark.parametrize(
    "failure",
    ["missing-runtime", "missing-catalog", "invalid-catalog", "corrupt-pack"],
)
def test_bundle_cache_failures(
    failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid partitioned bundles never activate Python paths.

    Args:
        failure: Failure for this operation.
        tmp_path: Isolated test filesystem.
        monkeypatch: Pytest environment and dependency overrides.

    """
    monkeypatch.setattr(
        target=cm,
        name="_host_bundle_dirs",
        value=Constant(value=(Path("linux") / "glibc" / "amd64",)),
    )
    monkeypatch.setenv(
        name="EXACTUS_TOOLS_CACHE",
        value=str(object=tmp_path / "cache"),
    )
    launcher: Path = _bundle(root=tmp_path)
    catalog: Path = launcher.parent / "data" / "parts" / "fs" / "catalog.json"
    if failure == "missing-runtime":
        (launcher.parent / "partition_launcher.py").unlink()
    elif failure == "missing-catalog":
        catalog.unlink()
    elif failure == "invalid-catalog":
        catalog.write_text(data="{}")
    else:
        next(
            (launcher.parent / "data" / "parts" / "fs" / "packs").glob(
                pattern="*/*.zst",
            ),
        ).write_bytes(data=b"bad")
    expect_none(value=cm.exactus_bundle_cache(root=tmp_path))


def test_activate_requires_python_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cache lacking ``python/`` is not activated.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="exactus_bundle_cache",
        value=Constant(value=tmp_path),
    )
    expect_false(condition=cm.activate_exactus_tool_bundle(root=tmp_path))


def test_activate_exposes_chromium_browsers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser activation exposes bundled Chromium paths to child processes.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    python: Path = tmp_path / "python-tools" / "python"
    browsers: Path = tmp_path / "chromium" / "playwright-browsers"
    for directory in (python, browsers):
        directory.mkdir(parents=True)
    for name in ("LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH", "PYTHONPATH"):
        monkeypatch.setenv(name=name, value=cm.environ.get(name, ""))
    monkeypatch.setattr(
        target=cm,
        name="exactus_bundle_cache",
        value=Constant(value=tmp_path),
    )
    saved_path: list[str] = list(sys_path)
    try:
        expect_true(condition=cm.activate_exactus_tool_bundle(root=tmp_path))
        expect_equal(
            actual=cm.environ["PLAYWRIGHT_BROWSERS_PATH"],
            expected=str(object=browsers),
        )
    finally:
        sys_path[:] = saved_path


def test_embedded_bundle_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partitioned bundle directory is found as real files.

    Args:
        tmp_path: Isolated test filesystem.
        monkeypatch: Pytest environment and dependency overrides.

    """
    _bundle(root=tmp_path)
    monkeypatch.setattr(
        target=cm,
        name="_host_bundle_dirs",
        value=Constant(value=(Path("linux") / "glibc" / "amd64",)),
    )

    def resources(_package: str) -> Path:
        """Resolve the fixture resource directory.

        Args:
            _package:  package for this operation.

        Returns:
            The verified result of this operation.

        """
        return tmp_path

    monkeypatch.setattr(target=cm, name="resource_files", value=resources)
    found: Path = require_type(
        value=private_call(owner=cm, name="_embedded_bundle_dir"),
        kind=Path,
    )
    expect_true(condition=(found / "__main__.py").is_file())


def test_materialize_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested pack and bootstrap ZIP resources copy into an atomic cache.

    Args:
        tmp_path: Isolated test filesystem.
        monkeypatch: Pytest environment and dependency overrides.

    """
    monkeypatch.setenv(
        name="XDG_CACHE_HOME",
        value=str(object=tmp_path / "runtime-cache"),
    )
    launcher: Path = _bundle(root=tmp_path / "bundle-source")
    zip_path: Path = tmp_path / "bundle.zip"
    with ZipFile(file=zip_path, mode="w") as archive:
        for path in launcher.parent.rglob(pattern="*"):
            if path.is_file():
                archive.write(
                    path,
                    path.relative_to(launcher.parent).as_posix(),
                )
    with ZipFile(file=zip_path) as archive:
        anchor: ZipPath = ZipPath(root=archive)
        base: Path = require_type(
            value=private_call(
                owner=cm,
                name="_materialize_bundle",
                anchor=anchor,
            ),
            kind=Path,
        )
        expect_true(condition=(base / "partition_fs.py").is_file())
        expect_true(
            condition=(
                base / "data" / "parts" / "fs" / "catalog.json"
            ).is_file(),
        )
        expect_true(
            condition=bool(
                list(
                    (base / "data" / "parts" / "fs" / "packs").glob(
                        pattern="*/*.zst",
                    ),
                ),
            ),
        )
        expect_equal(
            actual=private_call(
                owner=cm,
                name="_materialize_bundle",
                anchor=anchor,
            ),
            expected=base,
        )
        expect_equal(
            actual=(
                base / "data" / "parts" / "fs" / "catalog.json"
            ).read_bytes(),
            expected=(
                launcher.parent / "data" / "parts" / "fs" / "catalog.json"
            ).read_bytes(),
        )
        blocker: Path = tmp_path / "blocked"
        blocker.write_text(data="file")
        monkeypatch.setenv(name="XDG_CACHE_HOME", value=str(object=blocker))
        expect_none(
            value=private_call(
                owner=cm,
                name="_materialize_bundle",
                anchor=anchor,
            ),
        )


def test_resolve_bundle_via_embedded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The embedded bundle is the last discovery fallback.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="_host_bundle_dirs",
        value=Constant(value=(Path("linux") / "glibc" / "amd64",)),
    )
    fake_dir: Path = tmp_path / "emb"
    fake_dir.mkdir()
    target: Path = fake_dir / "__main__.py"
    target.write_text(data="", encoding="utf-8")
    target.chmod(mode=493)
    original: Callable[..., object] = cm.Path.__truediv__
    del original
    monkeypatch.setattr(
        target=cm,
        name="_embedded_bundle_dir",
        value=Constant(value=fake_dir),
    )
    monkeypatch.setattr(
        target=cm,
        name="_executable_candidate",
        value=_only(allowed=target),
    )
    expect_equal(
        actual=cm.resolve_exactus_tool_bundle(root=tmp_path),
        expected=target,
    )
    monkeypatch.setattr(
        target=cm,
        name="_embedded_bundle_dir",
        value=Constant(value=None),
    )
    expect_none(value=cm.resolve_exactus_tool_bundle(root=tmp_path))


def _only(allowed: Path) -> Callable[..., Path | None]:
    """Build a candidate filter accepting a single path.

    Args:
        allowed: The sole accepted path.

    Returns:
        A replacement for ``_executable_candidate``.

    """

    def candidate(*, candidate: Path) -> Path | None:
        """Accept only ``allowed``.

        Args:
            candidate: Path under test.

        Returns:
            The path when allowed, else ``None``.

        """
        return candidate if candidate == allowed else None

    return candidate


def test_embedded_bundle_dir_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing or unreachable embedded bundles resolve to ``None``.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=cm,
        name="resource_files",
        value=Constant(value=tmp_path),
    )
    expect_none(value=private_call(owner=cm, name="_embedded_bundle_dir"))

    def missing(package: str) -> NoReturn:
        """Simulate an unimportable package anchor.

        Args:
            package: Package name being resolved.

        Raises:
            ModuleNotFoundError: Always, for the given package.

        """
        raise ModuleNotFoundError(package)

    monkeypatch.setattr(target=cm, name="resource_files", value=missing)
    expect_none(value=private_call(owner=cm, name="_embedded_bundle_dir"))


@pytest.mark.parametrize(
    ("host", "arch", "musl", "expected"),
    [
        ("Linux", "x86_64", False, (Path("linux") / "glibc" / "amd64",)),
        ("Linux", "aarch64", False, (Path("linux") / "glibc" / "arm64",)),
        (
            "Linux",
            "aarch64",
            True,
            (
                Path("linux") / "musl" / "arm64",
                Path("linux") / "glibc" / "arm64",
            ),
        ),
        ("Darwin", "arm64", False, (Path("macos") / "arm64",)),
        ("Darwin", "x86_64", False, (Path("macos") / "amd64",)),
        ("Windows", "AMD64", False, (Path("windows") / "amd64",)),
        ("FreeBSD", "amd64", False, ()),
        ("Linux", "riscv64", False, ()),
    ],
)
def test_host_bundle_dirs(
    *,
    host: str,
    arch: str,
    musl: bool,
    expected: tuple[Path, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host OS/architecture/libc map to ordered bundle directories.

    Args:
        host: Simulated ``platform.system`` value.
        arch: Simulated ``platform.machine`` value.
        musl: Simulated musl detection result.
        expected: Ordered bundle subdirectory candidates.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=cm, name="system", value=Constant(value=host))
    monkeypatch.setattr(target=cm, name="machine", value=Constant(value=arch))
    monkeypatch.setattr(
        target=cm,
        name="_host_musl",
        value=Constant(value=musl),
    )
    expect_equal(
        actual=private_call(owner=cm, name="_host_bundle_dirs"),
        expected=expected,
    )
