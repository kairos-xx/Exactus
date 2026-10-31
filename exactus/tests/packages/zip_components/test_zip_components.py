# Copyright (c) 2026 João Lopes.
"""Tests for source-bundle archives of exactus tools and packages packages."""

from __future__ import annotations

from io import StringIO
from json import loads
from pathlib import Path
from textwrap import dedent
from zipfile import ZipFile

import pytest

from exactus.packages.zip_components.core import (
    BundleResult,
    Selection,
    available_components,
    bundle_name,
    collect_files,
    create_bundle,
    create_project_archive,
    discover_components,
    main,
)
from exactus.tests.common.support import expect_in, expect_not_in, expect_true


def _root() -> Path:
    """Return the repository root that owns this test file.

    Returns:
        The repository root path.

    """
    return Path(__file__).resolve().parents[4]


def _fake_tree(root: Path) -> None:
    """Create a minimal component tree for discovery tests.

    Args:
        root: Scratch root populated with fake components.

    """
    files: dict[str, str] = {
        "pyproject.toml": "[tool.steps]\nwrite = true\n",
        "exactus/packages/__init__.py": "",
        "exactus/packages/alpha/__init__.py": (
            dedent(
                text=(
                    "    from exactus.packages.beta import B\n    PROBE: s"
                    "tr = 'exactus.packages.delta'\n    "
                ),
            )
        ),
        "exactus/packages/beta/__init__.py": "B: int = 1\n",
        "exactus/packages/beta/core.py": "import exactus.packages.gamma\n",
        "exactus/packages/gamma/__init__.py": "",
        "exactus/packages/delta/__init__.py": "",
        "exactus/packages/unused/__init__.py": "",
        "exactus/tests/packages/alpha/test_alpha.py": "",
        "exactus/docs/packages/alpha/DOCS.md": "",
    }
    relative: str
    text: str
    for relative, text in files.items():
        path: Path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _bytes: int = path.write_text(data=text, encoding="utf-8")


def _project_tree(root: Path) -> None:
    """Create a minimal project tree with a built bundle.

    Args:
        root: Scratch project root populated with fake files.

    """
    files: dict[str, str] = {
        "exactus/__init__.py": "",
        "exactus/bundle/stale.txt": "stale\n",
        "exactus/tools/lints/__init__.py": "",
        "exactus/packages/pkg/__init__.py": "",
        "build/exactus/bundle/BUILT.txt": "built\n",
        "build/exactus/bundle/__pycache__/noise.pyc": "",
        "node_modules/pkg/index.js": "",
        ".hidden/secret.txt": "",
        "visible.py": "x = 1\n",
    }
    relative: str
    text: str
    for relative, text in files.items():
        path: Path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _bytes: int = path.write_text(data=text, encoding="utf-8")


def test_bundle_name_joins_kinds_in_request_order() -> None:
    """Name archives after the requested components only."""
    expect_true(
        condition=bundle_name(exactus=("lints", "docs"))
        == "exactus_lints_docs.zip",
    )
    expect_true(
        condition=bundle_name(packages=("all_lints", "browser"))
        == "packages_all_lints_browser.zip",
    )
    expect_true(
        condition=bundle_name(
            exactus=("lints", "docs"),
            packages=("all_lints", "browser"),
        )
        == "exactus_lints_docs_packages_all_lints_browser.zip",
    )
    expect_true(
        condition=bundle_name(packages=("steps", "steps"))
        == "packages_steps.zip",
    )


def test_discover_components_is_transitive(tmp_path: Path) -> None:
    """Follow component imports until no new component appears.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    selection: Selection = discover_components(
        root=tmp_path,
        packages=("alpha",),
    )
    expect_true(condition=selection.exactus == ())
    expect_true(
        condition=selection.packages == ("alpha", "beta", "delta", "gamma"),
    )


def test_discover_components_skips_missing_directories(tmp_path: Path) -> None:
    """Ignore imports that do not resolve to component directories.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    source: Path = tmp_path / "exactus" / "packages" / "alpha" / "extra.py"
    _bytes: int = source.write_text(
        data=(
            dedent(
                text=(
                    "    import exactus.packages.missing\n    from exactus"
                    ".packages.absent import x\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    selection: Selection = discover_components(
        root=tmp_path,
        packages=("alpha",),
    )
    expect_not_in(member="missing", container=selection.packages)
    expect_not_in(member="absent", container=selection.packages)


def test_collect_files_adds_skeleton_skips_caches(tmp_path: Path) -> None:
    """Bundle skeleton paths and component trees without cache noise.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    cache: Path = tmp_path / "exactus" / "packages" / "alpha" / "__pycache__"
    cache.mkdir()
    noise: Path = cache / "alpha.cpython-313.pyc"
    _bytes: int = noise.write_text(data="", encoding="utf-8")
    selection: Selection = discover_components(
        root=tmp_path,
        packages=("alpha",),
    )
    files: tuple[str, ...] = collect_files(root=tmp_path, selection=selection)
    expect_in(member="pyproject.toml", container=files)
    expect_in(member="exactus/packages/__init__.py", container=files)
    expect_in(member="exactus/packages/alpha/__init__.py", container=files)
    expect_in(member="exactus/packages/beta/core.py", container=files)
    expect_in(
        member="exactus/tests/packages/alpha/test_alpha.py",
        container=files,
    )
    expect_in(member="exactus/docs/packages/alpha/DOCS.md", container=files)
    expect_not_in(
        member="exactus/packages/unused/__init__.py",
        container=files,
    )
    expect_true(condition=all("__pycache__" not in member for member in files))


def test_collect_files_includes_results_directories(tmp_path: Path) -> None:
    """Bundle existing report directories of selected exactus tools.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    tool: Path = tmp_path / "exactus" / "tools" / "helper"
    tool.mkdir(parents=True)
    _bytes: int = (tool / "__init__.py").write_text(data="", encoding="utf-8")
    results: Path = tmp_path / "EXACTUS_RESULTS" / "HELPER"
    results.mkdir(parents=True)
    _bytes = (results / "result.md").write_text(data="", encoding="utf-8")
    other: Path = tmp_path / "EXACTUS_RESULTS" / "OTHER"
    other.mkdir()
    _bytes = (other / "result.md").write_text(data="", encoding="utf-8")
    files: tuple[str, ...] = collect_files(
        root=tmp_path,
        selection=Selection(exactus=("helper",), packages=()),
    )
    expect_in(member="EXACTUS_RESULTS/HELPER/result.md", container=files)
    expect_not_in(member="EXACTUS_RESULTS/OTHER/result.md", container=files)


def test_collect_files_ignores_missing_results(tmp_path: Path) -> None:
    """Skip report directories that do not exist.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    files: tuple[str, ...] = collect_files(
        root=tmp_path,
        selection=Selection(exactus=("helper",), packages=("alpha",)),
    )
    expect_true(
        condition=not any(
            member.startswith("EXACTUS_RESULTS/") for member in files
        ),
    )


def test_create_bundle_writes_a_real_archive(tmp_path: Path) -> None:
    """Write archive members at repository-relative paths.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    output: Path = tmp_path / "packages_alpha.zip"
    result: BundleResult = create_bundle(
        root=tmp_path,
        packages=("alpha",),
        output=output,
    )
    expect_true(condition=output.is_file())
    expect_true(condition=result.path == output)
    with ZipFile(file=output) as archive:
        names: tuple[str, ...] = tuple(archive.namelist())
    expect_in(member="exactus/packages/alpha/__init__.py", container=names)
    expect_in(member="exactus/packages/gamma/__init__.py", container=names)
    expect_in(member="pyproject.toml", container=names)


def test_create_bundle_scaffolds_readme_and_tree(tmp_path: Path) -> None:
    """Default bundles nest under ``zip-components/<stem>/``.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    result: BundleResult = create_bundle(root=tmp_path, packages=("alpha",))
    bundle: Path = result.path.parent
    expect_true(
        condition=bundle == tmp_path / "zip-components" / "packages_alpha",
    )
    expect_true(condition=(bundle / "README.md").is_file())
    expect_true(condition=(bundle / "TREE.txt").is_file())
    expect_true(condition=(bundle.parent / "README.md").is_file())
    tree: str = (bundle / "TREE.txt").read_text(encoding="utf-8")
    expect_true(condition=tree.splitlines()[0].startswith("packages_alpha/"))
    expect_in(member="└── pyproject.toml", container=tree)


def test_lints_selection_discovers_pipeline_components() -> None:
    """Expand the real lints tool into its shared dependencies."""
    selection: Selection = discover_components(
        root=_root(),
        exactus=("lints",),
    )
    expect_in(member="common", container=selection.exactus)
    expect_in(member="reports", container=selection.exactus)
    expect_in(member="all_lints", container=selection.packages)
    expect_in(member="organize", container=selection.packages)


def test_main_writes_the_scaffolded_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Place the archive inside ``zip-components/<stem>/`` with docs.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("--packages", "alpha"))
    expect_true(condition=status == 0)
    folder: Path = tmp_path / "zip-components"
    bundle: Path = folder / "packages_alpha"
    archive: Path = bundle / "packages_alpha.zip"
    expect_true(condition=archive.is_file())
    expect_true(condition=(folder / "README.md").is_file())
    expect_true(condition=(bundle / "README.md").is_file())
    expect_true(condition=(bundle / "TREE.txt").is_file())
    readme: str = (bundle / "README.md").read_text(encoding="utf-8")
    expect_in(member="unzip -o packages_alpha.zip", container=readme)
    expect_in(member="packages_alpha.zip", container=capture.getvalue())


def test_main_output_folder_overrides_the_default_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Place the bundle under ``--output-folder`` instead.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=StringIO(),
    )
    custom: Path = tmp_path / "archives"
    status: int = main(
        arguments=(
            "--packages",
            "alpha",
            "--output-folder",
            str(object=custom),
        ),
    )
    expect_true(condition=status == 0)
    expect_true(
        condition=(custom / "packages_alpha" / "packages_alpha.zip").is_file(),
    )
    expect_true(condition=(custom / "README.md").is_file())
    expect_true(condition=not (tmp_path / "zip-components").exists())


def test_main_root_flag_bundles_from_the_given_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bundle from ``--root`` instead of the auto-detected root.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=StringIO(),
    )
    status: int = main(
        arguments=("--packages", "alpha", "--root", str(object=tmp_path)),
    )
    expect_true(condition=status == 0)
    expect_true(
        condition=(
            tmp_path
            / "zip-components"
            / "packages_alpha"
            / "packages_alpha.zip"
        ).is_file(),
    )


def test_available_components_lists_every_package(tmp_path: Path) -> None:
    """List canonical exactus tools plus every packages package.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    loose: Path = tmp_path / "exactus" / "packages" / "loose"
    loose.mkdir()
    _bytes: int = (loose / "README.md").write_text(data="", encoding="utf-8")
    selection: Selection = available_components(root=tmp_path)
    expect_true(
        condition=selection.packages
        == ("alpha", "beta", "delta", "gamma", "unused"),
    )
    expect_true(
        condition=selection.exactus
        == (
            "coverage_tests",
            "docs",
            "frontend",
            "kwargs_typehints",
            "lints",
            "performance",
            "readme",
            "record",
            "self_test",
            "visual_cause",
        ),
    )


def test_main_list_outputs_every_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print every available package as JSON without writing an archive.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("--list",))
    expect_true(condition=status == 0)
    payload: dict[str, list[str]] = loads(s=capture.getvalue())
    expect_true(
        condition=payload["packages"]
        == ["alpha", "beta", "delta", "gamma", "unused"],
    )
    expect_in(member="lints", container=payload["exactus"])
    expect_not_in(member="helper", container=payload["exactus"])
    expect_not_in(member=".zip", container=capture.getvalue())


def test_main_list_resolves_a_named_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Print the discovered closure for the requested components.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("--packages", "alpha", "-l"))
    expect_true(condition=status == 0)
    payload: dict[str, list[str]] = loads(s=capture.getvalue())
    expect_true(
        condition=payload["packages"] == ["alpha", "beta", "delta", "gamma"],
    )
    expect_not_in(member="unused", container=payload["packages"])
    expect_true(condition=not (tmp_path / "packages_alpha.zip").exists())


def test_main_prints_usage_without_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit ``1`` when neither kind of component is requested.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=())
    expect_true(condition=status == 1)
    expect_in(member="usage", container=capture.getvalue())


def test_main_rejects_an_unknown_component() -> None:
    """Exit through the parser for a component that does not exist."""
    with pytest.raises(expected_exception=SystemExit, match="2"):
        _status: int = main(arguments=("--packages", "definitely_missing"))


def test_main_positional_names_are_packages_shorthand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bundle ``zip_components alpha`` exactly like ``--packages alpha``.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=StringIO(),
    )
    status: int = main(arguments=("alpha",))
    expect_true(condition=status == 0)
    expect_true(
        condition=(
            tmp_path
            / "zip-components"
            / "packages_alpha"
            / "packages_alpha.zip"
        ).is_file(),
    )


def test_main_wildcard_expands_to_every_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expand ``*``/``all`` into every package of that kind.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("--packages", "*", "-l"))
    expect_true(condition=status == 0)
    payload: dict[str, list[str]] = loads(s=capture.getvalue())
    expect_true(
        condition=payload["packages"]
        == ["alpha", "beta", "delta", "gamma", "unused"],
    )
    expect_true(condition=payload["exactus"] == [])


def test_main_bare_star_selects_everything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat a positional ``*`` as ``--packages * --tools *``.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("*", "-l"))
    expect_true(condition=status == 0)
    payload: dict[str, list[str]] = loads(s=capture.getvalue())
    expect_in(member="alpha", container=payload["packages"])
    expect_in(member="unused", container=payload["packages"])
    expect_in(member="lints", container=payload["exactus"])


def test_bundle_name_renders_wildcards_as_all() -> None:
    """Name wildcard bundles ``packages_all.zip`` rather than ``*.zip``."""
    expect_true(condition=bundle_name(packages=("*",)) == "packages_all.zip")
    expect_true(
        condition=bundle_name(exactus=("*",), packages=("*",))
        == "exactus_all_packages_all.zip",
    )


def test_main_accepts_both_component_kinds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bundle exactus tools and packages packages into one archive.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _fake_tree(root=tmp_path)
    tool: Path = tmp_path / "exactus" / "tools" / "helper"
    tool.mkdir(parents=True)
    _bytes: int = (tool / "__init__.py").write_text(data="", encoding="utf-8")
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=StringIO(),
    )
    output: Path = tmp_path / "combined.zip"
    status: int = main(
        arguments=(
            "--tools",
            "helper",
            "--packages",
            "alpha",
            "--output",
            str(object=output),
        ),
    )
    expect_true(condition=status == 0)
    with ZipFile(file=output) as archive:
        names: tuple[str, ...] = tuple(archive.namelist())
    expect_in(member="exactus/tools/helper/__init__.py", container=names)
    expect_in(member="exactus/packages/alpha/__init__.py", container=names)


def test_create_project_archive_replaces_the_bundle(tmp_path: Path) -> None:
    """Archive the tree with ``build`` bundle remapped to ``exactus/bundle``.

    Args:
        tmp_path: Temporary test directory.

    """
    _project_tree(root=tmp_path)
    output: Path = tmp_path / "release.zip"
    result: BundleResult = create_project_archive(root=tmp_path, output=output)
    expect_true(condition=result.path == output)
    with ZipFile(file=output) as archive:
        names: tuple[str, ...] = tuple(archive.namelist())
    expect_in(member="visible.py", container=names)
    expect_in(member="exactus/bundle/BUILT.txt", container=names)
    expect_not_in(member="exactus/bundle/stale.txt", container=names)
    expect_true(condition=not any("packages" in member for member in names))
    expect_true(condition=not any("__pycache__" in member for member in names))
    expect_true(
        condition=not any("node_modules" in member for member in names),
    )
    expect_true(condition=not any(".hidden" in member for member in names))
    expect_true(
        condition=not any(member.startswith("build/") for member in names),
    )


def test_create_project_archive_requires_the_built_bundle(
    tmp_path: Path,
) -> None:
    """Fail with ``FileNotFoundError`` when the built bundle is missing.

    Args:
        tmp_path: Temporary test directory.

    """
    _bytes: int = (tmp_path / "marker.txt").write_text(
        data="x = 1\n",
        encoding="utf-8",
    )
    with pytest.raises(
        expected_exception=FileNotFoundError,
        match="Built bundle does not exist",
    ):
        _result: BundleResult = create_project_archive(
            root=tmp_path,
            output=tmp_path / "release.zip",
        )


def test_main_project_writes_the_release_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Write ``exactus-release.zip`` at the project root by default.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    _project_tree(root=tmp_path)
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.project_root",
        name=lambda: tmp_path,
    )
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.zip_components.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("--project",))
    expect_true(condition=status == 0)
    archive: Path = tmp_path / "exactus-release.zip"
    expect_true(condition=archive.is_file())
    with ZipFile(file=archive) as zipped:
        names: tuple[str, ...] = tuple(zipped.namelist())
    expect_in(member="exactus/bundle/BUILT.txt", container=names)
    expect_in(member="exactus-release.zip", container=capture.getvalue())


def test_main_project_rejects_component_selections() -> None:
    """Exit through the parser when ``--project`` mixes with selections."""
    with pytest.raises(expected_exception=SystemExit, match="2"):
        _status: int = main(arguments=("--project", "--packages", "alpha"))
