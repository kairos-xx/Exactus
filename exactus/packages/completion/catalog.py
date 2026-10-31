# Copyright (c) 2026
"""Completion catalog: the CLI grammar described for the engine.

The catalog is built by introspecting the *same* ``ArgumentParser``
instances the CLI parses with, so completion metadata can never drift
from a second, hand-maintained grammar. The only private attributes
touched — ``parser._actions`` and ``parser._mutually_exclusive_groups``
— are already used by the project's ``HelpRenderer`` for the identical
introspection problem; action internals themselves (``option_strings``,
``nargs``, ``choices``, ``metavar``, ``type``, ``help``, ``required``)
are stable ``argparse.Action`` surface.
"""

from __future__ import annotations

from argparse import SUPPRESS, Action, ArgumentParser
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

from exactus.packages.argument_parser import normalized_option

from .model import Constants as _GroupFinalConstants
from .model import Constants as _GroupFinalConstants_2
from .model import Constants as _GroupFinalConstants_3
from .model import Constants as _GroupFinalConstants_4
from .model import Constants as _GroupFinalConstants_5
from .model import ValueCardinality

if TYPE_CHECKING:
    from collections.abc import Iterable


class ProviderId(StrEnum):
    """Typed identifier for a dynamic completion provider.

    Attributes:
        PATH: Files and directories.
        DIRECTORY: Directories only.
        TOOL: Exactus catalog tool identifiers.
        PIPELINE: Exactus catalog pipeline identifiers.
        TOOL_ARGUMENT: Scoped tool argument prefixes.

    """

    PATH = "path"
    "Files and directories."
    DIRECTORY = "directory"
    "Directories only."
    TOOL = "tool"
    "Exactus catalog tool identifiers."
    PIPELINE = "pipeline"
    "Exactus catalog pipeline identifiers."
    TOOL_ARGUMENT = "tool-argument"
    "``TOOL::ARG`` scoped-argument prefixes."


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One option accepted by a command grammar.

    Attributes:
        names: Accepted option strings; the canonical long form first.
        dest: Argparse destination used as recognized-argument key.
        cardinality: How many values the option consumes.
        repeatable: Whether the option may be supplied more than once.
        provider: Dynamic provider for its values, if any.
        static_values: Static choice values, if any.
        description: One-line help reused as the candidate description.
        hidden: Whether the option is suppressed from every UI.
        mutex_group: Mutually-exclusive group identifier, if any.
        context: Grammar context activated when this option is seen
            (tool and screenshot-shortcut dispatch flags).
        required: Whether the parser requires the option.
        canonical_only: When ``True`` only the canonical name is
            offered as a candidate while every name stays matchable
            (Policy A — canonical-only).

    """

    names: tuple[str, ...]
    dest: str
    cardinality: ValueCardinality
    repeatable: bool = False
    provider: ProviderId | None = None
    static_values: tuple[str, ...] = ()
    description: str = ""
    hidden: bool = False
    mutex_group: str | None = None
    context: str | None = None
    required: bool = False
    canonical_only: bool = False

    @property
    def canonical_name(self) -> str:
        """Preferred option string for identity checks.

        Returns:
            The first ``--`` long name, otherwise the first name.

        """
        return next(
            (name for name in self.names if name.startswith("--")),
            self.names[0],
        )

    @property
    def takes_values(self) -> bool:
        """Whether the option consumes at least one value.

        Returns:
            Whether any value may follow the option.

        """
        return self.cardinality.consumes_remainder or (
            self.cardinality.maximum is None or self.cardinality.maximum > 0
        )


@dataclass(frozen=True, slots=True)
class PositionalSpec:
    """One positional accepted by a command grammar.

    Attributes:
        dest: Argparse destination used as recognized-argument key.
        metavar: Display metavar.
        cardinality: How many values the positional consumes.
        provider: Dynamic provider for its values, if any.
        static_values: Static choice values, if any.
        description: One-line help reused as the candidate description.

    """

    dest: str
    metavar: str
    cardinality: ValueCardinality
    provider: ProviderId | None = None
    static_values: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One command grammar node.

    Attributes:
        name: Command or context identifier.
        description: One-line help reused as the candidate description.
        options: Options accepted in this grammar.
        positionals: Positional specs in consumption order.
        subcommands: Nested command grammars.
        hidden: Whether the command is suppressed from every UI.

    """

    name: str
    description: str
    options: tuple[OptionSpec, ...] = ()
    positionals: tuple[PositionalSpec, ...] = ()
    subcommands: tuple[CommandSpec, ...] = ()
    hidden: bool = False

    def option_named(self, *, word: str) -> OptionSpec | None:
        """Return the option named ``word``, folding ``-`` and ``_``.

        Long options match like the shared argument parser: ``--dry_run``
        names the same option as ``--dry-run``. Exact spellings win.

        Args:
            word: Command-line word.

        Returns:
            The matching option, or ``None``.

        """
        exact: OptionSpec | None = next(
            (option for option in self.options if word in option.names),
            None,
        )
        if exact is not None or not word.startswith("--"):
            return exact
        folded: str = normalized_option(argument=word)
        return next(
            (
                option
                for option in self.options
                if any(
                    name.startswith("--")
                    and normalized_option(argument=name) == folded
                    for name in option.names
                )
            ),
            None,
        )

    def subcommand_named(self, *, word: str) -> CommandSpec | None:
        """Return the visible subcommand named ``word``.

        Args:
            word: Command-line word.

        Returns:
            The matching subcommand, or ``None``.

        """
        return next(
            (
                subcommand
                for subcommand in self.subcommands
                if not subcommand.hidden and subcommand.name == word
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class CompletionCatalog:
    """The whole CLI grammar reachable during completion.

    Attributes:
        root: Grammar active before any dispatch word.
        contexts: Alternate grammars activated by dispatch options
            (``--lints``, ``--url`` ...), keyed by their ``name``.

    """

    root: CommandSpec
    contexts: tuple[CommandSpec, ...]

    def context_named(self, *, name: str) -> CommandSpec | None:
        """Return the grammar context registered as ``name``.

        Args:
            name: Context identifier matching ``OptionSpec.context``.

        Returns:
            The matching grammar, or ``None``.

        """
        return next(
            (context for context in self.contexts if context.name == name),
            None,
        )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repeatable_actions: Grouped module constant.
        nargs_cardinality: Grouped module constant.
        directory_dests: Grouped module constant.
        path_metavars: Grouped module constant.
        name_providers: Grouped module constant.

    """

    repeatable_actions: Final[frozenset[str]] = frozenset(
        (
            "_AppendAction",
            "_AppendConstAction",
            "_CountAction",
            "_ExtendAction",
        ),
    )
    nargs_cardinality: Final[dict[object, ValueCardinality]] = {
        0: _GroupFinalConstants.no_value,
        None: _GroupFinalConstants_2.one_value,
        "?": _GroupFinalConstants_3.optional_value,
        "*": _GroupFinalConstants_4.any_values,
        "+": _GroupFinalConstants_5.at_least_one,
    }
    directory_dests: Final[frozenset[str]] = frozenset(
        ("root", "output_dir", "server"),
    )
    path_metavars: Final[frozenset[str]] = frozenset(("FILE", "PATH"))
    name_providers: Final[dict[str, ProviderId]] = {
        "tools": ProviderId.TOOL,
        "exclude_tools": ProviderId.TOOL,
        "clear": ProviderId.TOOL,
        "pipeline": ProviderId.PIPELINE,
    }


"``argparse`` action classes whose options may repeat."
"Static ``nargs`` values and their typed cardinality."


def _cardinality_of(*, action: Action) -> ValueCardinality:
    """Translate an argparse ``nargs`` into typed cardinality.

    Args:
        action: Argparse action to inspect.

    Returns:
        The matching value cardinality.

    """
    nargs: object = action.nargs
    known: ValueCardinality | None = Constants.nargs_cardinality.get(nargs)
    if known is not None:
        return known
    if isinstance(nargs, int):
        return ValueCardinality(minimum=nargs, maximum=nargs)
    return ValueCardinality(minimum=0, maximum=None, consumes_remainder=True)


def _metavar_of(*, action: Action) -> str:
    """Return an action's metavar text when it is a plain string.

    Args:
        action: Argparse action to inspect.

    Returns:
        The metavar string, or an empty string for tuple/absent
        metavars.

    """
    metavar: object = action.metavar
    return metavar if isinstance(metavar, str) else ""


def _mutex_groups(*, parser: ArgumentParser) -> dict[int, str]:
    """Map mutex-member action ids to a stable group identifier.

    Args:
        parser: Argument parser to inspect.

    Returns:
        Action ``id()`` to group-name mapping.

    """
    groups: tuple[object, ...] = tuple(
        getattr(parser, "_mutually_exclusive_groups", ()),
    )
    mapping: dict[int, str] = {}
    for index, group in enumerate(iterable=groups):
        members: tuple[object, ...] = tuple(
            getattr(group, "_group_actions", ()),
        )
        for member in members:
            mapping[id(member)] = f"mutex-{index}"
    return mapping


def _canonical_names(*, action: Action) -> tuple[str, ...]:
    """Order an action's option strings long-form first.

    Args:
        action: Argparse action to inspect.

    Returns:
        Option strings with ``--`` names leading, declaration order
        preserved within each length class.

    """
    strings: tuple[str, ...] = tuple(action.option_strings)
    return (
        *(name for name in strings if name.startswith("--")),
        *(name for name in strings if not name.startswith("--")),
    )


def spec_from_parser(
    *,
    name: str,
    description: str,
    parser: ArgumentParser,
    providers: dict[str, ProviderId] | None = None,
) -> CommandSpec:
    """Convert an ``ArgumentParser`` into a :class:`CommandSpec`.

    Args:
        name: Grammar identifier.
        description: One-line description (``parser.description``
            when absent is not reused; callers pass the curated text).
        parser: Argument parser to introspect.
        providers: Destination-to-provider overrides applied after the
            metavar/type heuristics.

    Returns:
        The converted command grammar.

    """
    overrides: dict[str, ProviderId] = providers or {}
    mutex: dict[int, str] = _mutex_groups(parser=parser)
    options: list[OptionSpec] = []
    positionals: list[PositionalSpec] = []
    actions: tuple[Action, ...] = tuple(getattr(parser, "_actions", ()))
    for action in actions:
        if action.dest == "help":
            continue
        description_text: str = (
            ""
            if action.help is None or action.help == SUPPRESS
            else action.help
        )
        hidden_action: bool = action.help == SUPPRESS
        cardinality: ValueCardinality = _cardinality_of(action=action)
        metavar: str = _metavar_of(action=action)
        choices: tuple[str, ...] = tuple(
            str(object=choice)
            for choice in cast(
                typ="Iterable[object]",
                val=action.choices or (),
            )
        )
        if not action.option_strings:
            positionals.append(
                PositionalSpec(
                    dest=action.dest,
                    metavar=metavar or action.dest.upper(),
                    cardinality=cardinality,
                    provider=_provider_for(
                        dest=action.dest,
                        metavar=metavar,
                        path_type=action.type is Path,
                        overrides=overrides,
                    ),
                    static_values=choices,
                    description=description_text,
                ),
            )
            continue
        options.append(
            OptionSpec(
                names=_canonical_names(action=action),
                dest=action.dest,
                cardinality=cardinality,
                repeatable=type(action).__name__
                in Constants.repeatable_actions,
                provider=_provider_for(
                    dest=action.dest,
                    metavar=metavar,
                    path_type=action.type is Path,
                    overrides=overrides,
                ),
                static_values=choices,
                description=description_text,
                hidden=hidden_action,
                mutex_group=mutex.get(id(action)),
                required=action.required,
            ),
        )
    return CommandSpec(
        name=name,
        description=description,
        options=tuple(options),
        positionals=tuple(positionals),
    )


def _provider_for(
    *,
    dest: str,
    metavar: str,
    path_type: bool,
    overrides: dict[str, ProviderId],
) -> ProviderId | None:
    """Choose a dynamic provider for one argparse destination.

    Args:
        dest: Argument destination.
        metavar: Declared metavar, if any.
        path_type: Whether argparse declares a Path value.
        overrides: Destination-to-provider overrides.

    Returns:
        The provider identifier, or ``None``.

    """
    if dest in overrides:
        return overrides[dest]
    if metavar == "DIR" or (path_type and dest in Constants.directory_dests):
        return ProviderId.DIRECTORY
    if metavar in Constants.path_metavars or path_type:
        return ProviderId.PATH
    if metavar == "NAME":
        return Constants.name_providers.get(dest)
    if metavar == "TOOL::ARG":
        return ProviderId.TOOL_ARGUMENT
    return None


"Destinations whose ``Path`` values must be directories."
"Metavars that denote filesystem paths."
"``NAME``-metavar destinations mapped to their provider."


def completion_command_spec() -> CommandSpec:
    """Return the public ``completion`` command grammar.

    Returns:
        Grammar for ``exactus completion <subcommand>``.

    """
    shells: tuple[str, ...] = ("bash", "zsh", "fish", "powershell")
    return CommandSpec(
        name="completion",
        description="Manage shell completion",
        subcommands=(
            *tuple(
                CommandSpec(
                    name=name,
                    description=f"Generate {name} completion code",
                )
                for name in shells
            ),
            CommandSpec(
                name="install",
                description="Install a completion script",
                options=(
                    OptionSpec(
                        names=("--shell",),
                        dest="shell",
                        cardinality=_GroupFinalConstants_2.one_value,
                        static_values=shells,
                        description="Shell to install completion for",
                        required=True,
                    ),
                ),
            ),
            CommandSpec(
                name="uninstall",
                description="Remove an installed completion script",
                options=(
                    OptionSpec(
                        names=("--shell",),
                        dest="shell",
                        cardinality=_GroupFinalConstants_2.one_value,
                        static_values=shells,
                        description="Shell to remove completion for",
                        required=True,
                    ),
                ),
            ),
            CommandSpec(
                name="diagnose",
                description="Report completion environment details",
                options=(
                    OptionSpec(
                        names=("--shell",),
                        dest="shell",
                        cardinality=_GroupFinalConstants_2.one_value,
                        static_values=shells,
                        description="Inspect one shell's install state",
                    ),
                    OptionSpec(
                        names=("--verbose",),
                        dest="verbose",
                        cardinality=_GroupFinalConstants.no_value,
                        description="Show provider and catalog details",
                    ),
                ),
            ),
        ),
    )


def merge_specs(
    *,
    name: str,
    description: str,
    specs: tuple[CommandSpec, ...],
    extra_options: tuple[OptionSpec, ...] = (),
) -> CommandSpec:
    """Combine several grammars into one, first declaration winning.

    Used where ``exactus`` forwards remaining tokens into a second
    grammar (the screenshot shortcut accepts its own flags plus the
    screenshot tool's; ``--record`` additionally peels the orchestrator
    server flags).

    Args:
        name: Merged grammar identifier.
        description: One-line description.
        specs: Grammars to merge in precedence order.
        extra_options: Options appended after every merged option.

    Returns:
        The merged grammar.

    """
    options: list[OptionSpec] = []
    seen: set[str] = set()
    for spec in specs:
        for option in spec.options:
            if option.canonical_name in seen:
                continue
            seen.add(option.canonical_name)
            options.append(option)
    positionals: list[PositionalSpec] = []
    for spec in specs:
        positionals.extend(spec.positionals)
    return CommandSpec(
        name=name,
        description=description,
        options=(*options, *extra_options),
        positionals=tuple(positionals),
    )
