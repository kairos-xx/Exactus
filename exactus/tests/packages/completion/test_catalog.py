# Copyright (c) 2026
"""Coverage for parser introspection in ``exactus/completion/catalog``."""

from __future__ import annotations

from argparse import SUPPRESS, ArgumentParser, _MutuallyExclusiveGroup
from pathlib import Path

from exactus.packages.completion.catalog import (
    CommandSpec,
    CompletionCatalog,
    OptionSpec,
    ProviderId,
    completion_command_spec,
    merge_specs,
    spec_from_parser,
)
from exactus.packages.completion.model import Constants
from exactus.packages.completion.model import Constants as _GroupFinalConstants
from exactus.packages.completion.model import (
    Constants as _GroupFinalConstants_2,
)
from exactus.packages.completion.model import (
    Constants as _GroupFinalConstants_3,
)
from exactus.packages.completion.model import (
    Constants as _GroupFinalConstants_4,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_none,
    expect_true,
)


def _option(*, spec: CommandSpec, name: str) -> OptionSpec:
    """Look up one option in a spec by accepted name.

    Args:
        spec: Grammar to search.
        name: Any accepted option string.

    Returns:
        The matching option spec.

    Raises:
        LookupError: When no option accepts the name.

    """
    option: OptionSpec | None = spec.option_named(word=name)
    if option is None:
        raise LookupError(name)
    return option


def test_spec_from_parser_maps_cardinalities() -> None:
    """``nargs`` variants map to the matching cardinalities."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--one")
    _ = parser.add_argument("--maybe", nargs="?")
    _ = parser.add_argument("--any", nargs="*")
    _ = parser.add_argument("--some", nargs="+")
    _ = parser.add_argument("--flag", action="store_true")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_equal(
        actual=_option(spec=spec, name="--one").cardinality,
        expected=_GroupFinalConstants.one_value,
    )
    expect_equal(
        actual=_option(spec=spec, name="--maybe").cardinality,
        expected=_GroupFinalConstants_2.optional_value,
    )
    expect_equal(
        actual=_option(spec=spec, name="--any").cardinality,
        expected=_GroupFinalConstants_3.any_values,
    )
    expect_equal(
        actual=_option(spec=spec, name="--some").cardinality,
        expected=_GroupFinalConstants_4.at_least_one,
    )
    expect_equal(
        actual=_option(spec=spec, name="--flag").cardinality,
        expected=Constants.no_value,
    )


def test_spec_from_parser_collects_choices() -> None:
    """``choices`` become static candidate values."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--mode", choices=("fast", "slow"))
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_equal(
        actual=_option(spec=spec, name="--mode").static_values,
        expected=("fast", "slow"),
    )


def test_spec_from_parser_marks_mutex_groups() -> None:
    """Mutually exclusive members share a group identifier."""
    parser: ArgumentParser = ArgumentParser()
    group: _MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
    _ = group.add_argument("--left", action="store_true")
    _ = group.add_argument("--right", action="store_true")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    left: OptionSpec = _option(spec=spec, name="--left")
    right: OptionSpec = _option(spec=spec, name="--right")
    expect_true(condition=left.mutex_group is not None)
    expect_equal(actual=left.mutex_group, expected=right.mutex_group)


def test_spec_from_parser_repeatable_append() -> None:
    """``append`` actions are marked repeatable."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--tag", action="append")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_true(condition=_option(spec=spec, name="--tag").repeatable)


def test_spec_from_parser_hides_suppressed_options() -> None:
    """``help=SUPPRESS`` actions carry ``hidden``."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--secret", help=SUPPRESS)
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_true(condition=_option(spec=spec, name="--secret").hidden)


def test_spec_from_parser_positionals() -> None:
    """Positional actions become positional specs."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("target", metavar="TARGET")
    _ = parser.add_argument("rest", nargs="*")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_equal(actual=len(spec.positionals), expected=2)
    expect_equal(actual=spec.positionals[0].dest, expected="target")
    expect_equal(
        actual=spec.positionals[1].cardinality,
        expected=_GroupFinalConstants_3.any_values,
    )


def test_provider_inference_by_metavar_and_type() -> None:
    """Metavar and ``type=Path`` drive provider inference."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--file", metavar="FILE")
    _ = parser.add_argument("--dir", metavar="DIR")
    _ = parser.add_argument("--path", type=Path)
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_equal(
        actual=_option(spec=spec, name="--file").provider,
        expected=ProviderId.PATH,
    )
    expect_equal(
        actual=_option(spec=spec, name="--dir").provider,
        expected=ProviderId.DIRECTORY,
    )
    expect_equal(
        actual=_option(spec=spec, name="--path").provider,
        expected=ProviderId.PATH,
    )


def test_provider_overrides_win() -> None:
    """Destination overrides beat metavar heuristics."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--thing", metavar="FILE")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
        providers={"thing": ProviderId.DIRECTORY},
    )
    expect_equal(
        actual=_option(spec=spec, name="--thing").provider,
        expected=ProviderId.DIRECTORY,
    )


def test_long_names_lead_canonical_order() -> None:
    """``--`` names precede short names in spec ordering."""
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("-v", "--verbose", action="store_true")
    spec: CommandSpec = spec_from_parser(
        name="x",
        description="",
        parser=parser,
    )
    expect_equal(
        actual=_option(spec=spec, name="--verbose").names,
        expected=("--verbose", "-v"),
    )


def test_merge_specs_combines_options() -> None:
    """Merged specs keep options from every source."""
    first: CommandSpec = CommandSpec(
        name="a",
        description="",
        options=(
            OptionSpec(
                names=("--one",),
                dest="one",
                cardinality=Constants.no_value,
            ),
        ),
    )
    second: CommandSpec = CommandSpec(
        name="a",
        description="",
        options=(
            OptionSpec(
                names=("--two",),
                dest="two",
                cardinality=Constants.no_value,
            ),
        ),
    )
    merged: CommandSpec = merge_specs(
        name="a",
        description="merged",
        specs=(first, second),
    )
    expect_in(
        member="--one",
        container=tuple(o.names[0] for o in merged.options),
    )
    expect_in(
        member="--two",
        container=tuple(o.names[0] for o in merged.options),
    )


def test_completion_command_spec_exposes_shells() -> None:
    """The public command offers the four shells plus management."""
    spec: CommandSpec = completion_command_spec()
    names: tuple[str, ...] = tuple(
        subcommand.name for subcommand in spec.subcommands
    )
    for shell in ("bash", "zsh", "fish", "powershell"):
        expect_in(member=shell, container=names)


def test_catalog_context_lookup() -> None:
    """``context_named`` resolves dispatch targets."""
    child: CommandSpec = CommandSpec(name="kid", description="")
    catalog: CompletionCatalog = CompletionCatalog(
        root=CommandSpec(name="root", description=""),
        contexts=(child,),
    )
    expect_equal(actual=catalog.context_named(name="kid"), expected=child)
    expect_none(value=catalog.context_named(name="nope"))
