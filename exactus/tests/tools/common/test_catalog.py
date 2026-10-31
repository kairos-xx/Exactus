# Copyright (c) 2026
"""Catalog validation, alias resolution, and pipeline wave planning."""

from __future__ import annotations

from pathlib import Path
from stat import S_IXUSR
from types import MappingProxyType
from typing import Final, final

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
    private_call,
)
from exactus.tools.common.catalog import Catalog, PipelineSpec, ToolSpec
from exactus.tools.common.catalog import Constants as _GroupFinalConstants


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_tools: Grouped module constant.
        min_pipelines: Grouped module constant.
        root: Grouped module constant.

    """

    min_tools: Final[int] = 7
    min_pipelines: Final[int] = 3
    root: Final[Path] = Path(__file__).resolve().parents[4]


def _tool(name: str, *deps: str, aliases: tuple[str, ...] = ()) -> ToolSpec:
    """Build a minimal tool spec.

    Args:
        name: Tool identifier.
        *deps: Dependency identifiers.
        aliases: Accepted aliases.

    Returns:
        The tool spec.

    """
    return ToolSpec(
        identifier=name,
        module=f"exactus.tools.{name}",
        script=f"{name}.py",
        output=name.upper(),
        aliases=aliases,
        dependencies=deps,
    )


def test_duplicate_identifiers_rejected() -> None:
    """Tool or pipeline ids must be unique."""
    with pytest.raises(expected_exception=ValueError, match="unique"):
        Catalog(tools=(_tool(name="a"), _tool(name="a")), pipelines=())
    pipe: PipelineSpec = PipelineSpec(identifier="p", stages=(("a",),))
    with pytest.raises(expected_exception=ValueError, match="unique"):
        Catalog(tools=(_tool(name="a"),), pipelines=(pipe, pipe))


def test_alias_collisions_rejected() -> None:
    """Aliases may not shadow ids or each other."""
    with pytest.raises(expected_exception=ValueError, match="collision"):
        Catalog(
            tools=(_tool(name="a"), _tool(name="b", aliases=("a",))),
            pipelines=(),
        )
    with pytest.raises(expected_exception=ValueError, match="collision"):
        Catalog(
            tools=(
                _tool(name="a", aliases=("x",)),
                _tool(name="b", aliases=("x",)),
            ),
            pipelines=(),
        )


def test_unknown_references_rejected() -> None:
    """Dependencies, members and baked arguments must exist."""
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown dependency",
    ):
        Catalog(tools=(_tool("a", "ghost"),), pipelines=())
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown pipeline member",
    ):
        Catalog(
            tools=(_tool(name="a"),),
            pipelines=(PipelineSpec(identifier="p", stages=(("ghost",),)),),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="tool-argument target",
    ):
        Catalog(
            tools=(_tool(name="a"),),
            pipelines=(
                PipelineSpec(
                    identifier="p",
                    stages=(("a",),),
                    tool_arguments=MappingProxyType(
                        mapping={"ghost": ("--x",)},
                    ),
                ),
            ),
        )


def test_pipeline_cycle_rejected() -> None:
    """Self-referential pipelines are detected."""
    with pytest.raises(expected_exception=ValueError, match="cycle"):
        Catalog(
            tools=(_tool(name="a"),),
            pipelines=(
                PipelineSpec(identifier="p", stages=(("q",),)),
                PipelineSpec(identifier="q", stages=(("p",),)),
            ),
        )


def test_nested_pipelines_and_waves() -> None:
    """Nested pipelines flatten and waves run last stage first."""
    catalog: Catalog = Catalog(
        tools=(_tool(name="a"), _tool(name="b"), _tool(name="c")),
        pipelines=(
            PipelineSpec(identifier="inner", stages=(("a", "b"), ("c",))),
            PipelineSpec(
                identifier="outer",
                stages=(("inner",), ("c",)),
                aliases=("o",),
            ),
        ),
    )
    expect_equal(
        actual=[t.identifier for t in catalog.resolve(selections=("o",))],
        expected=["c", "a", "b"],
    )
    waves: tuple[tuple[ToolSpec, ...], ...] = catalog.waves(identifier="outer")
    expect_equal(
        actual=[[t.identifier for t in wave] for wave in waves],
        expected=[["c"], ["a", "b"]],
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown pipeline",
    ):
        catalog.waves(identifier="a")
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown pipeline",
    ):
        catalog.waves(identifier="zzz")


def test_lookup_helpers() -> None:
    """Normalization, aliases and typed lookups."""
    expect_equal(
        actual=_GroupFinalConstants.exactus_catalog.canonical(
            identifier="Lints.py",
        ),
        expected="lints",
    )
    expect_equal(
        actual=_GroupFinalConstants.exactus_catalog.canonical(
            identifier="Docs.py",
        ),
        expected="docs",
    )
    expect_equal(
        actual=_GroupFinalConstants.exactus_catalog.canonical(
            identifier="fast",
        ),
        expected="all-fast",
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown exactus catalog entry",
    ):
        _GroupFinalConstants.exactus_catalog.canonical(identifier="nope")
    expect_true(
        condition=_GroupFinalConstants.exactus_catalog.tool(identifier="docs")
        is not None,
    )
    expect_none(
        value=_GroupFinalConstants.exactus_catalog.tool(identifier="unified"),
    )
    expect_true(
        condition=_GroupFinalConstants.exactus_catalog.pipeline(
            identifier="unified",
        )
        is not None,
    )
    expect_none(
        value=_GroupFinalConstants.exactus_catalog.pipeline(identifier="docs"),
    )
    expect_true(
        condition=len(_GroupFinalConstants.exactus_catalog.tools())
        >= Constants.min_tools,
    )
    expect_true(
        condition=len(_GroupFinalConstants.exactus_catalog.pipelines())
        >= Constants.min_pipelines,
    )


@pytest.mark.parametrize(
    "identifier",
    ["coverage_tests", "coverage", "tests", "exactus_coverage"],
)
def test_coverage_tests_aliases(identifier: str) -> None:
    """The former ``coverage`` and ``tests`` ids resolve to one tool.

    Args:
        identifier: Canonical id, spelling variant or alias.

    """
    if identifier != "coverage_tests":
        with pytest.raises(
            expected_exception=ValueError,
            match="unknown exactus catalog entry",
        ):
            _GroupFinalConstants.exactus_catalog.canonical(
                identifier=identifier,
            )
        expect_none(
            value=_GroupFinalConstants.exactus_catalog.tool(
                identifier=identifier,
            ),
        )
        return
    expect_equal(
        actual=_GroupFinalConstants.exactus_catalog.canonical(
            identifier=identifier,
        ),
        expected="coverage_tests",
    )
    spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=identifier,
    )
    expect_equal(
        actual=None if spec is None else (spec.output, spec.module),
        expected=("COVERAGE_TESTS", "exactus.tools.coverage_tests.main"),
    )
    expect_equal(
        actual=[
            tool.identifier
            for tool in _GroupFinalConstants.exactus_catalog.resolve(
                selections=(identifier, "self"),
            )
        ].count("coverage_tests"),
        expected=1,
    )


def test_resolve_deduplicates() -> None:
    """Selecting overlapping tools and pipelines runs each once."""
    resolved: tuple[ToolSpec, ...] = (
        _GroupFinalConstants.exactus_catalog.resolve(
            selections=("docs", "self", "docs"),
        )
    )
    ids: list[str] = [tool.identifier for tool in resolved]
    expect_equal(actual=len(ids), expected=len(set(ids)))
    expect_in(member="docs", container=ids)


def test_resolve_pipeline_unknown_member() -> None:
    """Resolving an unknown pipeline raises before wave planning."""
    with pytest.raises(
        expected_exception=ValueError,
        match="unknown pipeline",
    ):
        private_call(
            owner=_GroupFinalConstants.exactus_catalog,
            name="_resolve_pipeline",
            identifier="missing-pipeline",
            stack=(),
        )


@pytest.mark.parametrize(
    "identifier",
    [
        "readme",
        "docs",
        "kwargs_typehints",
        "lints",
        "coverage_tests",
        "frontend",
        "record",
    ],
)
def test_packaged_tool_layout(identifier: str) -> None:
    """Every tool lives in ``exactus/tools/<id>/`` with a main and a core.

    Args:
        identifier: Catalog identifier of a tool.

    """
    spec: ToolSpec | None = _GroupFinalConstants.exactus_catalog.tool(
        identifier=identifier,
    )
    expect_true(condition=spec is not None)
    if spec is None:
        return
    stem: str = identifier.replace("-", "_")
    expect_equal(actual=spec.module, expected=f"exactus.tools.{stem}.main")
    expect_equal(actual=spec.script, expected=f"exactus/tools/{stem}/main.py")
    main: Path = Constants.root / spec.script
    core: Path = main.with_name(name="core.py")
    expect_true(condition=main.is_file())
    expect_true(condition=core.is_file())
    expect_true(condition=main.stat().st_mode & S_IXUSR != 0)
    expect_true(condition=main.read_text(encoding="utf-8").startswith("#!"))
    expect_true(condition=core.stat().st_mode & S_IXUSR == 0)
    expect_true(
        condition=not core.read_text(encoding="utf-8").startswith("#!"),
    )


def test_unified_pipeline_audits_readmes_after_every_other_tool() -> None:
    """Readme inventories run after analyzers; performance profiles last."""
    waves: tuple[tuple[ToolSpec, ...], ...] = (
        _GroupFinalConstants.exactus_catalog.waves(identifier="unified")
    )
    names: list[list[str]] = [[t.identifier for t in wave] for wave in waves]
    expect_equal(actual=names[0], expected=["lints"])
    expect_equal(actual=names[-2], expected=["readme"])
    expect_equal(actual=names[-1], expected=["performance"])
    expect_true(condition="frontend" in names[1])


def test_identifier_lookup_accepts_dash_spellings() -> None:
    """``tool``/``pipeline``/``canonical`` fold ``-``/``_`` variants."""
    catalog: Catalog = Catalog(
        tools=(_tool(name="kwargs_typehints"), _tool(name="docs")),
        pipelines=(
            PipelineSpec(
                identifier="all-fast",
                stages=(("docs",),),
                aliases=("fast",),
                tool_arguments=MappingProxyType(mapping={}),
            ),
        ),
    )
    expect_equal(
        actual=catalog.canonical(identifier="kwargs-typehints"),
        expected="kwargs_typehints",
    )
    expect_equal(
        actual=catalog.canonical(identifier="kwargs_typehints"),
        expected="kwargs_typehints",
    )
    expect_true(
        condition=catalog.tool(identifier="kwargs-typehints") is not None,
    )
    expect_none(value=catalog.tool(identifier="all_fast"))
    expect_true(condition=catalog.pipeline(identifier="all_fast") is not None)
    expect_true(condition=catalog.pipeline(identifier="all-fast") is not None)
    expect_none(value=catalog.pipeline(identifier="kwargs_typehints"))
