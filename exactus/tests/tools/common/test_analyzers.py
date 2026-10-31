# Copyright (c) 2026
"""In-process runs of every static analyzer over the toolkit and a sample."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from shutil import copytree, ignore_patterns
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import expect_in, expect_true
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.common.catalog import ToolSpec

if TYPE_CHECKING:
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        analyzers: Grouped module constant.

    """

    analyzers: Final[tuple[str, ...]] = ("kwargs_typehints", "docs", "readme")


def _module_name(*, name: str) -> str:
    """Return the catalog module of an analyzer.

    Args:
        name: Analyzer name with underscores.

    Returns:
        The dotted module name the catalog registers for the tool.

    Raises:
        ValueError: When the analyzer name is not in the catalog.

    """
    spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=name,
    )
    if spec is None:
        msg: str = f"unknown analyzer {name}"
        raise ValueError(msg)
    return spec.module


@pytest.mark.parametrize("name", Constants.analyzers)
def test_self_exactus_writes_reports(
    name: str,
    repo_args: tuple[str, ...],
    tmp_path: Path,
) -> None:
    """Each analyzer completes against the toolkit and emits a report.

    Args:
        name: Parametrized case name.
        repo_args: Parametrized repository arguments.
        tmp_path: Per-test temporary directory.

    """
    module: ModuleType = import_module(name=_module_name(name=name))
    status: int = module.main(
        arguments=(*repo_args, "-o", str(object=tmp_path / "out")),
    )
    expect_in(member=status, container={0, 1})
    expect_true(condition=any((tmp_path / "out").iterdir()))


@pytest.mark.parametrize("name", Constants.analyzers)
def test_sample_project_exactus(
    name: str,
    sample_project: Path,
    tmp_path: Path,
) -> None:
    """Each analyzer handles a small defective project.

    Args:
        name: Parametrized case name.
        sample_project: Generated sample project directory.
        tmp_path: Per-test temporary directory.

    """
    module: ModuleType = import_module(name=_module_name(name=name))
    status: int = module.main(
        arguments=(
            str(object=sample_project),
            "-o",
            str(object=tmp_path / "out"),
        ),
    )
    expect_in(member=status, container={0, 1})


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Copy two real third-party packages to exactus as a large corpus.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Root directory holding the copied packages.

    """
    target: Path = tmp_path / "corpus"
    for package in (
        import_module(name="_pytest"),
        import_module(name="coverage"),
    ):
        source: Path = Path(package.__file__ or "").parent
        _ = copytree(
            src=source,
            dst=target / source.name,
            ignore=ignore_patterns("__pycache__", "*.so", "*.pyi", "*.pyc"),
        )
    return target


@pytest.mark.parametrize("name", ["kwargs_typehints", "docs"])
def test_real_world_corpus(name: str, corpus: Path, tmp_path: Path) -> None:
    """Large third-party codebases are analyzed without crashing.

    Args:
        name: Parametrized case name.
        corpus: Parametrized corpus directory.
        tmp_path: Per-test temporary directory.

    """
    module: ModuleType = import_module(name=_module_name(name=name))
    status: int = module.main(
        arguments=(str(object=corpus), "-o", str(object=tmp_path / "out")),
    )
    expect_in(member=status, container={0, 1})
    expect_true(condition=any((tmp_path / "out").iterdir()))
