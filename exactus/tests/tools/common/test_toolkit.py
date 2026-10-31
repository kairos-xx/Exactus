# Copyright (c) 2026 Project contributors
"""Validate catalog, collection, and current partitioned tool dispatch."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, cast, final

from exactus.packages.package.inventory import collect_files, excluded_dir
from exactus.packages.package.partition_fs import Catalog as FilesystemCatalog
from exactus.packages.package.partition_fs import (
    Json,
    PartitionStore,
    Recipe,
    RecipeScanner,
    load_catalog,
)
from exactus.packages.package.partition_launcher import Runtime
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.catalog import Catalog, validate_scripts


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]


def test_every_script_exists() -> None:
    """No catalog tool may point at a missing script."""
    expect_equal(actual=validate_scripts(root=Constants.root), expected=())


def test_normalize_strips_decoration() -> None:
    """Script-style names normalize to hyphenated identifiers."""
    script: str = "kwargs_typehints"
    normalized: str = Catalog.normalize(identifier=f" {script}.py ")
    expect_equal(actual=normalized, expected="kwargs_typehints")


def test_excluded_dir_rules() -> None:
    """Dot, uppercase, and generated directories are pruned."""
    for name in (".git", "EXACTUS_RESULTS", "build", "exec", "x.egg-info"):
        expect_true(condition=excluded_dir(name=name), message=name)
    expect_false(condition=excluded_dir(name="exactus"))
    expect_false(
        condition=excluded_dir(name="EXACTUS_RESULTS", allow_uppercase=True),
    )


def test_collect_files_skips_generated_output() -> None:
    """Only real project files are collected."""
    with TemporaryDirectory() as tmp:
        base: Path = Path(tmp)
        (base / "src").mkdir()
        (base / "src" / "a.py").write_text(data="x", encoding="utf-8")
        (base / "EXACTUS_RESULTS").mkdir()
        (base / "EXACTUS_RESULTS" / "r.md").write_text(
            data="x",
            encoding="utf-8",
        )
        (base / ".hidden").write_text(data="x", encoding="utf-8")
        found: list[str] = [
            p.relative_to(base).as_posix() for p in collect_files(root=base)
        ]
    expect_equal(actual=found, expected=["src/a.py"])


def test_all_listed_tools_have_a_command(tmp_path: Path) -> None:
    """Resolve every shipped declaration from verified miniature payloads.

    Args:
        tmp_path: Isolated build and runtime filesystem.

    """
    shipped: FilesystemCatalog = load_catalog(
        path=Constants.root
        / "exactus/bundle/linux/glibc/amd64/data/parts/fs/catalog.json",
    )
    store: PartitionStore = PartitionStore(cache=tmp_path / "objects")
    recipes: dict[str, Recipe] = {}
    for name, recipe in shipped["components"].items():
        root: Path = tmp_path / "staged" / name
        root.mkdir(parents=True)
        metadata: dict[str, Json] = recipe["metadata"]
        tools: dict[str, dict[str, str]] = cast(
            typ="dict[str, dict[str, str]]",
            val=metadata.get("tools", {}),
        )
        for spec in tools.values():
            if spec["kind"] in {"binary", "js-entry"}:
                target: Path = (
                    root
                    / (
                        "js/node_modules/"
                        if spec["kind"] == "js-entry"
                        else ""
                    )
                    / spec["target"]
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data=b"verified fixture executable")
        recipes[name] = RecipeScanner(objects=store.objects).scan(
            root=root,
            name=name,
            metadata=metadata,
        )
    store.build(recipes=recipes, output=tmp_path / "fs", platform="fixture")
    runtime: Runtime = Runtime(
        catalog_path=tmp_path / "fs/catalog.json",
        cache=tmp_path / "runtime",
    )
    expect_true(condition=bool(runtime.tools()), message="No bundled tools")
    for tool, (name, spec) in runtime.tools().items():
        command, environment = runtime.command(tool=tool, args=["--version"])
        expect_true(condition=bool(command[0]), message=tool)
        expect_equal(
            actual=environment["PYTHONDONTWRITEBYTECODE"],
            expected="1",
        )
        if spec["kind"] != "probe":
            expect_equal(actual=command[-1], expected="--version")
        expect_true(
            condition=(runtime.components / name).is_dir(),
            message=tool,
        )
