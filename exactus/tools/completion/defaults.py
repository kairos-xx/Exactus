# Copyright (c) 2026
"""Wire the real ``exactus`` grammars into a completion catalog.

This module accepts application parsers through a structural protocol.
It maps every parser destination to a provider without importing the
calling application or its exactus tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, final

from exactus.packages.completion.catalog import (
    CommandSpec,
    CompletionCatalog,
    OptionSpec,
    ProviderId,
    completion_command_spec,
    spec_from_parser,
)
from exactus.packages.completion.model import Constants as _GroupFinalConstants

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Tool(Protocol):
    """Describe a dispatch tool supplied by the calling application."""

    @property
    def name(self) -> str:
        """Canonical tool identifier.

        Returns:
            The tool's dispatch name.

        """
        ...

    @property
    def flags(self) -> tuple[str, ...]:
        """Accepted dispatch flags.

        Returns:
            Flags this tool accepts after its name.

        """
        ...

    @property
    def parser(self) -> ArgumentParser:
        """The application's argument parser.

        Returns:
            Parser that produces the tool's dispatch options.

        """
        ...


@final
class Constants:
    """Group module-level constants.

    Attributes:
        common_providers: Grouped module constant.
        tool_descriptions: Grouped module constant.

    """

    common_providers: Final[dict[str, ProviderId]] = {
        "root": ProviderId.DIRECTORY,
        "output_dir": ProviderId.DIRECTORY,
        "source_root": ProviderId.DIRECTORY,
        "include": ProviderId.PATH,
        "exclude": ProviderId.PATH,
        "config": ProviderId.PATH,
        "toolchain": ProviderId.PATH,
        "server_log": ProviderId.PATH,
        "replay": ProviderId.PATH,
        "tools": ProviderId.TOOL,
        "exclude_tools": ProviderId.TOOL,
        "clear": ProviderId.TOOL,
        "pipeline": ProviderId.PIPELINE,
        "tool_arg": ProviderId.TOOL_ARGUMENT,
    }
    tool_descriptions: Final[dict[str, str]] = {
        "lints": "Clean, lint, and type-check sources",
        "coverage_tests": "Run tests and emit coverage reports",
        "docs": "Exactus documentation coverage and structure",
        "kwargs_typehints": "Exactus keyword-argument type annotations",
        "readme": "Exactus README documentation coverage",
        "record": "Record and replay browser workflows",
        "frontend": (
            "Exactus frontend interactions, images, and browser diagnostics"
        ),
        "visual_cause": (
            "Explain causal visual differences between rendered pages"
        ),
        "performance": (
            "Profile tool step traces and export the performance dashboard"
        ),
        "self_test": (
            "Self-diagnose the runtime against a generated fixture project"
        ),
    }


"Destination-to-provider overrides shared by every grammar."
"One-line descriptions for each tool dispatch flag."


def _parser_description(*, parser: ArgumentParser) -> str:
    """Return a parser's one-line description.

    Args:
        parser: Argument parser to inspect.

    Returns:
        The description's first line, or an empty string.

    """
    description: str = parser.description or ""
    return description.strip().splitlines()[0] if description.strip() else ""


def _tool_spec(*, tool: Tool) -> CommandSpec:
    """Convert one bundled tool into a grammar context.

    Args:
        tool: Registered dispatch tool.

    Returns:
        Grammar for everything following the tool's dispatch flag.

    """
    parser: ArgumentParser = tool.parser
    spec: CommandSpec = spec_from_parser(
        name=tool.name,
        description=Constants.tool_descriptions.get(
            tool.name,
            _parser_description(parser=parser),
        ),
        parser=parser,
        providers=Constants.common_providers,
    )
    return spec


def _dispatch_option(*, name: str, tool: Tool) -> OptionSpec:
    """Build a tool dispatch flag that switches grammar context.

    Only the canonical flag is offered as a candidate (Policy A:
    canonical-only); alias flags remain matchable.

    Args:
        name: Canonical tool identifier.
        tool: Registered dispatch tool.

    Returns:
        Dispatch option spec.

    """
    flags: tuple[str, ...] = tool.flags
    return OptionSpec(
        names=flags,
        dest=f"dispatch_{name.replace('-', '_')}",
        cardinality=_GroupFinalConstants.no_value,
        description=Constants.tool_descriptions.get(name, ""),
        context=name,
        canonical_only=True,
    )


def check_catalog(
    *,
    tools: tuple[Tool, ...],
    orchestrator_parser: ArgumentParser,
) -> CompletionCatalog:
    """Assemble the ``exactus`` completion catalog.

    Args:
        tools: Bundled dispatch tools with parser factories.
        orchestrator_parser: The top-level ``exactus`` parser.

    Returns:
        Catalog mirroring the dispatcher's real grammar: tool flags,
        the orchestrator flags, ``-h``/``--help``, ``--show-config``,
        and the ``completion`` command.

    """
    contexts: list[CommandSpec] = [_tool_spec(tool=tool) for tool in tools]
    orchestrator: CommandSpec = spec_from_parser(
        name="exactus",
        description="Run canonical exactus tools and staged pipelines",
        parser=orchestrator_parser,
        providers=Constants.common_providers,
    )
    dispatch: tuple[OptionSpec, ...] = tuple(
        _dispatch_option(name=tool.name, tool=tool) for tool in tools
    )
    extra: tuple[OptionSpec, ...] = (
        OptionSpec(
            names=("-h", "--help"),
            dest="help",
            cardinality=_GroupFinalConstants.no_value,
            description="Show aggregated tool help",
        ),
        OptionSpec(
            names=("--show-config",),
            dest="show_config",
            cardinality=_GroupFinalConstants.no_value,
            description="Show each tool's effective configuration",
        ),
    )
    return CompletionCatalog(
        root=CommandSpec(
            name="exactus",
            description=orchestrator.description,
            options=(*dispatch, *extra, *orchestrator.options),
            positionals=orchestrator.positionals,
            subcommands=(completion_command_spec(),),
        ),
        contexts=tuple(contexts),
    )
