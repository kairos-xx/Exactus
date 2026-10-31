#!/usr/bin/env python3
# Copyright (c) 2026
"""Canonical exactus tool and pipeline catalog.

Tools are executable leaves. Pipelines contain only references to tool ids or
other pipelines and never execute work themselves. Resolution flattens nested
pipelines in declaration order and de-duplicates every tool by canonical id.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Describe one canonical executable exactus tool.

    Attributes:
        identifier: Stable CLI/catalog identifier.
        module: Importable Python module used by the internal API.
        script: Repository-relative standalone CLI script.
        output: Canonical child directory under ``EXACTUS_RESULTS``.
        aliases: Accepted compatibility names.
        dependencies: Canonical tools that must pass first.
        streaming_dependencies: Whether file activities may begin as each
            prerequisite releases the same file.
        whole_source_activity: Whether the task is one non-file source reader.
        file_census: Whether the run banner counts project files by
            suffix; tools that generate their own fixture scope opt out.

    """

    identifier: str
    module: str
    script: str
    output: str
    aliases: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    streaming_dependencies: bool = False
    whole_source_activity: bool = False
    file_census: bool = True


@dataclass(frozen=True, slots=True)
class PipelineSpec:
    """Describe one non-executable orchestration pipeline.

    Attributes:
        identifier: Stable pipeline identifier.
        stages: Dependency waves in reverse declaration order. The last wave
            runs first; each preceding wave starts only after the following
            wave completes. Members inside one wave may run in parallel.
        aliases: Accepted compatibility names.
        tool_arguments: Per-tool CLI arguments keyed by tool id, applied
            before any ``--tool-arg`` overrides.
        clear: Whether the pipeline's own report directory is removed before
            it claims ownership. Tool directories are refreshed individually
            when their workers start.

    """

    identifier: str
    stages: tuple[tuple[str, ...], ...]
    aliases: tuple[str, ...] = ()
    tool_arguments: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType(mapping={}),
    )
    clear: bool = False


class Catalog:
    """Resolve canonical tools and pipelines without duplicate execution."""

    def __init__(
        self,
        *,
        tools: tuple[ToolSpec, ...],
        pipelines: tuple[PipelineSpec, ...],
    ) -> None:
        """Create and validate a catalog.

        Args:
            tools: Canonical executable tools.
            pipelines: Canonical orchestration pipelines.

        Raises:
            ValueError: If ids/aliases collide or references are invalid.

        """
        tool_map: dict[str, ToolSpec] = {
            tool.identifier: tool for tool in tools
        }
        pipeline_map: dict[str, PipelineSpec] = {
            pipeline.identifier: pipeline for pipeline in pipelines
        }
        if len(tool_map) != len(tools) or len(pipeline_map) != len(pipelines):
            msg: str = "catalog identifiers must be unique"
            raise ValueError(msg)
        aliases: dict[str, str] = {}
        for identifier, values in (
            *((tool.identifier, tool.aliases) for tool in tools),
            *(
                (pipeline.identifier, pipeline.aliases)
                for pipeline in pipelines
            ),
        ):
            for alias in values:
                if (
                    alias in tool_map
                    or alias in pipeline_map
                    or alias in aliases
                ):
                    msg = f"catalog alias collision: {alias}"
                    raise ValueError(msg)
                aliases[alias] = identifier
        self._tools: Mapping[str, ToolSpec] = MappingProxyType(
            mapping=tool_map,
        )
        self._pipelines: Mapping[str, PipelineSpec] = MappingProxyType(
            mapping=pipeline_map,
        )
        self._aliases: Mapping[str, str] = MappingProxyType(mapping=aliases)
        for pipeline in pipelines:
            _ = self._resolve_pipeline(
                identifier=pipeline.identifier,
                stack=(),
            )
            self._check_tool_arguments(pipeline=pipeline)
        for tool in tools:
            for dependency in tool.dependencies:
                if self.tool(identifier=dependency) is None:
                    msg = (
                        f"unknown dependency {dependency!r} for"
                        f" {tool.identifier!r}"
                    )
                    raise ValueError(msg)

    @staticmethod
    def normalize(*, identifier: str) -> str:
        """Normalize a public catalog identifier.

        Args:
            identifier: User-provided identifier.

        Returns:
            Lowercase hyphenated identifier without exactus/script
            decoration.

        """
        return identifier.strip().lower().removesuffix(".py")

    def canonical(self, *, identifier: str) -> str:
        """Resolve an id or alias to its canonical identifier.

        Args:
            identifier: Tool or pipeline id/alias.

        Returns:
            Canonical identifier.

        Raises:
            ValueError: If the identifier is unknown.

        """
        canonical: str | None = self._key_for(identifier=identifier)
        if canonical is None:
            msg: str = f"unknown exactus catalog entry: {identifier}"
            raise ValueError(msg)
        return canonical

    def tool(self, *, identifier: str) -> ToolSpec | None:
        """Return a canonical tool, or ``None`` for a pipeline.

        Args:
            identifier: Tool id or alias.

        Returns:
            Tool specification or ``None``.

        """
        canonical: str | None = self._key_for(identifier=identifier)
        if canonical is None:
            return None
        return self._tools.get(canonical)

    def pipeline(self, *, identifier: str) -> PipelineSpec | None:
        """Return a canonical pipeline, or ``None`` for a tool.

        Args:
            identifier: Pipeline id or alias.

        Returns:
            Pipeline specification or ``None``.

        """
        canonical: str | None = self._key_for(identifier=identifier)
        if canonical is None:
            return None
        return self._pipelines.get(canonical)

    def tools(self) -> tuple[ToolSpec, ...]:
        """Return tools.

        Returns:
            The resulting value.

        """
        return tuple(self._tools.values())

    def pipelines(self) -> tuple[PipelineSpec, ...]:
        """Return pipelines.

        Returns:
            The resulting value.

        """
        return tuple(self._pipelines.values())

    def waves(self, *, identifier: str) -> tuple[tuple[ToolSpec, ...], ...]:
        """Return waves.

        Args:
            identifier: Identifier.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        pipeline: PipelineSpec | None = self.pipeline(identifier=identifier)
        if pipeline is None:
            msg: str = f"unknown pipeline: {identifier}"
            raise ValueError(msg)
        seen: set[str] = set()
        waves: list[tuple[ToolSpec, ...]] = []
        for stage in reversed(pipeline.stages):
            wave: list[ToolSpec] = []
            for member in stage:
                canonical: str = self.canonical(identifier=member)
                candidates: tuple[ToolSpec, ...] = (
                    (self._tools[canonical],)
                    if canonical in self._tools
                    else self.resolve(selections=(canonical,))
                )
                for tool in candidates:
                    if tool.identifier not in seen:
                        seen.add(tool.identifier)
                        wave.append(tool)
            if wave:
                waves.append(tuple(wave))
        return tuple(waves)

    def resolve(self, *, selections: tuple[str, ...]) -> tuple[ToolSpec, ...]:
        """Flatten tool/pipeline selections and de-duplicate canonical tools.

        Args:
            selections: Tool and/or pipeline ids.

        Returns:
            Tools in deterministic first-reference order.

        """
        identifiers: list[str] = []
        for selection in selections:
            canonical: str = self.canonical(identifier=selection)
            candidates: tuple[str, ...] = (
                (canonical,)
                if canonical in self._tools
                else self._resolve_pipeline(identifier=canonical, stack=())
            )
            for candidate in candidates:
                if candidate not in identifiers:
                    identifiers.append(candidate)
        return tuple(self._tools[identifier] for identifier in identifiers)

    def _key_for(self, *, identifier: str) -> str | None:
        """Resolve an id/alias tolerating ``-``/``_`` spelling variants.

        Args:
            identifier: Tool or pipeline id/alias in any dash/underscore
                spelling.

        Returns:
            Canonical identifier present in the catalog, or ``None``.

        """
        normalized: str = Catalog.normalize(identifier=identifier)
        spellings: tuple[str, ...] = (
            normalized,
            normalized.replace("-", "_"),
            normalized.replace("_", "-"),
        )
        for spelling in spellings:
            candidate: str = self._aliases.get(spelling, spelling)
            if candidate in self._tools or candidate in self._pipelines:
                return candidate
        return None

    def _check_tool_arguments(self, *, pipeline: PipelineSpec) -> None:
        """Validate that baked tool arguments name real catalog tools.

        Args:
            pipeline: Pipeline owning the argument map.

        Raises:
            ValueError: If an argument target resolves to no tool.

        """
        for target in pipeline.tool_arguments:
            if self.tool(identifier=target) is None:
                msg: str = (
                    f"unknown tool-argument target {target!r} in pipeline"
                    f" {pipeline.identifier!r}"
                )
                raise ValueError(msg)

    def _resolve_pipeline(
        self,
        *,
        identifier: str,
        stack: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return resolve pipeline.

        Args:
            identifier: Identifier.
            stack: Stack.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if identifier in stack:
            msg: str = f"pipeline cycle: {' -> '.join((*stack, identifier))}"
            raise ValueError(msg)
        pipeline: PipelineSpec | None = self._pipelines.get(identifier)
        if pipeline is None:
            msg = f"unknown pipeline: {identifier}"
            raise ValueError(msg)
        resolved: list[str] = []
        for stage in reversed(pipeline.stages):
            for member in stage:
                canonical: str = self._aliases.get(
                    Catalog.normalize(identifier=member),
                    Catalog.normalize(identifier=member),
                )
                if canonical in self._tools:
                    if canonical not in resolved:
                        resolved.append(canonical)
                elif canonical in self._pipelines:
                    for nested in self._resolve_pipeline(
                        identifier=canonical,
                        stack=(*stack, identifier),
                    ):
                        if nested not in resolved:
                            resolved.append(nested)
                else:
                    msg = (
                        f"unknown pipeline member {member!r} in {identifier!r}"
                    )
                    raise ValueError(msg)
        return tuple(resolved)


def _tool(
    identifier: str,
    *,
    dependencies: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    streaming_dependencies: bool = False,
    whole_source_activity: bool = False,
) -> ToolSpec:
    """Return tool.

    Args:
        identifier: Identifier.
        dependencies: Dependencies.
        aliases: Alternative identifiers accepted for the tool.
        streaming_dependencies: Permit file-granular dependency overlap.
        whole_source_activity: Protect the whole task as one source reader.

    Returns:
        The resulting value.

    """
    stem: str = identifier.replace("-", "_")
    return ToolSpec(
        identifier=identifier,
        module=f"exactus.tools.{stem}.main",
        script=f"exactus/tools/{stem}/main.py",
        output=identifier.upper(),
        dependencies=dependencies,
        aliases=aliases,
        streaming_dependencies=streaming_dependencies,
        whole_source_activity=whole_source_activity,
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        tools: Grouped module constant.
        url_gated: Grouped module constant.
        pipelines: Grouped module constant.
        exactus_catalog: Grouped module constant.

    """

    tools: Final[tuple[ToolSpec, ...]] = (
        _tool(identifier="lints"),
        _tool(identifier="coverage_tests", dependencies=("lints",)),
        _tool(identifier="docs", dependencies=("lints",)),
        _tool(
            identifier="kwargs_typehints",
            dependencies=("lints",),
            streaming_dependencies=True,
        ),
        _tool(identifier="readme", whole_source_activity=True),
        _tool(identifier="frontend"),
        _tool(identifier="record"),
        _tool(identifier="visual_cause", whole_source_activity=True),
        _tool(identifier="performance", whole_source_activity=True),
        replace(_tool(identifier="self_test"), file_census=False),
    )
    url_gated: Final[frozenset[str]] = frozenset(
        {"frontend", "record", "visual_cause"},
    )
    pipelines: Final[tuple[PipelineSpec, ...]] = (
        PipelineSpec(
            identifier="self",
            stages=(
                ("coverage_tests", "docs", "kwargs_typehints", "readme"),
                ("lints",),
            ),
        ),
        PipelineSpec(
            identifier="all-fast",
            stages=(
                ("performance",),
                tuple(
                    tool.identifier
                    for tool in tools
                    if tool.identifier
                    not in {"lints", "performance", "self_test"}
                ),
                ("lints",),
            ),
            aliases=("fast",),
            tool_arguments=MappingProxyType(
                mapping={
                    "lints": ("--no-clean", "--no-fix", "--no-infer"),
                    "performance": ("--no-serve",),
                },
            ),
            clear=True,
        ),
        PipelineSpec(
            identifier="unified",
            stages=(
                ("performance",),
                ("readme",),
                tuple(
                    tool.identifier
                    for tool in tools
                    if tool.identifier
                    not in {"lints", "readme", "performance"}
                ),
                ("lints",),
            ),
            tool_arguments=MappingProxyType(
                mapping={"performance": ("--no-serve",)},
            ),
        ),
    )
    exactus_catalog: Final[Catalog] = Catalog(tools=tools, pipelines=pipelines)


def validate_scripts(*, root: Path) -> tuple[str, ...]:
    """Validate scripts.

    Args:
        root: Root.

    Returns:
        The resulting value.

    """
    return tuple(
        tool.identifier
        for tool in Constants.exactus_catalog.tools()
        if not (root / tool.script).is_file()
    )
