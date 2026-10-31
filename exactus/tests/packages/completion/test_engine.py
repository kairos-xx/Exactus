# Copyright (c) 2026
"""Decision-tree coverage for :class:`CompletionEngine`."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Final

from exactus.packages.completion.catalog import (
    CommandSpec,
    CompletionCatalog,
    OptionSpec,
    PositionalSpec,
    ProviderId,
)
from exactus.packages.completion.engine import CompletionEngine, ScanState
from exactus.packages.completion.model import (
    CompletionCandidate,
    CompletionContext,
    CompletionKind,
    CompletionRequest,
    CompletionShell,
    Constants,
)
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
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)

if TYPE_CHECKING:
    from pathlib import Path


class _WordsProvider:
    """Deterministic provider yielding two canned values."""

    @staticmethod
    def complete(
        *,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Return fixed candidates filtered by the context prefix.

        Args:
            context: Normalized completion state.

        Returns:
            The canned candidates matching the prefix.

        """
        return tuple(
            CompletionCandidate(
                value=value,
                display=value,
                description="canned",
                kind=CompletionKind.VALUE,
                append_space=True,
            )
            for value in ("alpha", "beta")
            if value.startswith(context.prefix)
        )


def _catalog() -> CompletionCatalog:
    """Build the synthetic grammar exercised by these tests.

    Returns:
        Catalog with value/flag/mutex/repeat options, a dispatch
        context, and one subcommand.

    """
    child: CommandSpec = CommandSpec(
        name="child",
        description="Child grammar",
        options=(
            OptionSpec(
                names=("--color", "-c"),
                dest="color",
                cardinality=_GroupFinalConstants.one_value,
                static_values=("red", "green"),
                description="Pick a color",
            ),
        ),
        positionals=(
            PositionalSpec(
                dest="target",
                metavar="TARGET",
                cardinality=_GroupFinalConstants.one_value,
                provider=ProviderId.TOOL,
                description="Target word",
            ),
        ),
    )
    root: CommandSpec = CommandSpec(
        name="root",
        description="Root grammar",
        options=(
            OptionSpec(
                names=("--format", "-f"),
                dest="format",
                cardinality=_GroupFinalConstants.one_value,
                static_values=("json", "text"),
                description="Output format",
            ),
            OptionSpec(
                names=("--verbose", "-v"),
                dest="verbose",
                cardinality=Constants.no_value,
                repeatable=True,
                description="Increase verbosity",
            ),
            OptionSpec(
                names=("--once",),
                dest="once",
                cardinality=Constants.no_value,
                description="Run once",
            ),
            OptionSpec(
                names=("--twice",),
                dest="twice",
                cardinality=Constants.no_value,
                mutex_group="times",
                description="Two runs",
            ),
            OptionSpec(
                names=("--thrice",),
                dest="thrice",
                cardinality=Constants.no_value,
                mutex_group="times",
                description="Three runs",
            ),
            OptionSpec(
                names=("--tag",),
                dest="tag",
                cardinality=_GroupFinalConstants.one_value,
                repeatable=True,
                static_values=("a", "b", "c"),
                description="Repeatable tag",
            ),
            OptionSpec(
                names=("--many",),
                dest="many",
                cardinality=_GroupFinalConstants_4.at_least_one,
                description="Greedy value list",
            ),
            OptionSpec(
                names=("--maybe",),
                dest="maybe",
                cardinality=_GroupFinalConstants_2.optional_value,
                description="Optional value",
            ),
            OptionSpec(
                names=("--hidden",),
                dest="hidden",
                cardinality=Constants.no_value,
                hidden=True,
                description="Suppressed",
            ),
            OptionSpec(
                names=("--switch",),
                dest="switch",
                cardinality=Constants.no_value,
                context="child",
                description="Switch context",
            ),
            OptionSpec(
                names=("--alias", "-a"),
                dest="alias",
                cardinality=Constants.no_value,
                canonical_only=True,
                description="Canonical offered only",
            ),
            OptionSpec(
                names=("--depth",),
                dest="depth",
                cardinality=_GroupFinalConstants.one_value,
                description="Numeric depth",
            ),
            OptionSpec(
                names=("--files",),
                dest="files",
                cardinality=_GroupFinalConstants_3.any_values,
                provider=ProviderId.TOOL,
                description="Words",
            ),
        ),
        subcommands=(child,),
    )
    return CompletionCatalog(root=root, contexts=(child,))


def _engine(*, working_directory: Path) -> CompletionEngine:
    """Create an engine over the synthetic catalog.

    Args:
        working_directory: Directory providers resolve against.

    Returns:
        Engine wired to the canned provider.

    """
    return CompletionEngine(
        catalog=_catalog(),
        command_name="root",
        providers={ProviderId.TOOL: _WordsProvider()},
        working_directory=working_directory,
    )


def _complete(
    *,
    working_directory: Path,
    words: tuple[str, ...],
    prefix: str,
) -> tuple[CompletionCandidate, ...]:
    """Complete the last word of ``words``.

    Args:
        working_directory: Directory providers resolve against.
        words: Logical command words including the active word.
        prefix: Active-word prefix.

    Returns:
        Engine candidates.

    """
    return _engine(working_directory=working_directory).complete(
        request=CompletionRequest(
            shell=CompletionShell.BASH,
            words=words,
            active_word_index=len(words) - 1,
            prefix=prefix,
        ),
    )


def _values(
    *,
    working_directory: Path,
    words: tuple[str, ...],
    prefix: str,
) -> tuple[str, ...]:
    """Collect candidate values for one request.

    Args:
        working_directory: Directory providers resolve against.
        words: Logical command words including the active word.
        prefix: Active-word prefix.

    Returns:
        Candidate values in emission order.

    """
    return tuple(
        candidate.value
        for candidate in _complete(
            working_directory=working_directory,
            words=words,
            prefix=prefix,
        )
    )


def test_root_offers_subcommands_and_positionals(tmp_path: Path) -> None:
    """Bare tokens offer subcommand names plus positional values.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", ""),
        prefix="",
    )
    expect_in(member="child", container=values)


def test_long_options_filtered_by_prefix(tmp_path: Path) -> None:
    """``--`` prefixes offer only matching long option names.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--fo"),
        prefix="--fo",
    )
    expect_in(member="--format", container=values)
    expect_not_in(member="--verbose", container=values)


def test_used_non_repeatable_option_suppressed(tmp_path: Path) -> None:
    """A supplied non-repeatable option is not offered again.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--format", "json", "--"),
        prefix="--",
    )
    expect_not_in(member="--format", container=values)


def test_repeatable_option_reoffered(tmp_path: Path) -> None:
    """Repeatable flags stay legal after one use.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--verbose", "--"),
        prefix="--",
    )
    expect_in(member="--verbose", container=values)


def test_mutex_group_suppresses_sibling(tmp_path: Path) -> None:
    """Using one mutex member suppresses the other.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--twice", "--"),
        prefix="--",
    )
    expect_not_in(member="--thrice", container=values)
    expect_in(member="--format", container=values)


def test_option_value_choices(tmp_path: Path) -> None:
    """A pending option offers its static choices.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--format", ""),
        prefix="",
    )
    expect_equal(actual=values, expected=("json", "text"))


def test_inline_value_completion(tmp_path: Path) -> None:
    """``--name=v`` prefixes complete to ``--name=value`` insertions.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--format=j"),
        prefix="--format=j",
    )
    expect_equal(actual=values, expected=("--format=json",))


def test_repeat_values_exclude_consumed(tmp_path: Path) -> None:
    """Repeatable options offer remaining values only.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--tag", "a", "--tag", ""),
        prefix="",
    )
    expect_not_in(member="a", container=values)
    expect_in(member="b", container=values)


def test_double_dash_disables_options(tmp_path: Path) -> None:
    """After ``--`` a dash prefix hits positionals, not options.

    Args:
        tmp_path: Provider working directory.

    """
    candidates: tuple[CompletionCandidate, ...] = _complete(
        working_directory=tmp_path,
        words=("root", "child", "--", "--"),
        prefix="--",
    )
    expect_false(
        condition=any(
            candidate.kind is CompletionKind.OPTION for candidate in candidates
        ),
        message="options must not appear after --",
    )


def test_dispatch_option_switches_context(tmp_path: Path) -> None:
    """A context option activates the target grammar's options.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--switch", "--"),
        prefix="--",
    )
    expect_in(member="--color", container=values)
    expect_not_in(member="--format", container=values)


def test_subcommand_switches_context(tmp_path: Path) -> None:
    """A subcommand token activates the child grammar.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "child", "--"),
        prefix="--",
    )
    expect_in(member="--color", container=values)
    expect_not_in(member="--format", container=values)


def test_positional_provider_used_inside_subcommand(tmp_path: Path) -> None:
    """A positional with a provider completes provider values.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "child", ""),
        prefix="",
    )
    expect_equal(actual=values, expected=("alpha", "beta"))


def test_hidden_option_never_offered(tmp_path: Path) -> None:
    """Hidden options stay legal but are never candidates.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--h"),
        prefix="--h",
    )
    expect_not_in(member="--hidden", container=values)
    accepted: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--hidden", ""),
        prefix="",
    )
    expect_in(member="child", container=accepted)


def test_canonical_only_offers_long_name(tmp_path: Path) -> None:
    """``canonical_only`` options offer the long name only.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "-"),
        prefix="-",
    )
    expect_in(member="--alias", container=values)
    expect_not_in(member="-a", container=values)


def test_short_cluster_consumes_flags(tmp_path: Path) -> None:
    """``-vv`` counts as two uses of a repeatable short flag.

    Args:
        tmp_path: Provider working directory.

    """
    engine: CompletionEngine = _engine(working_directory=tmp_path)
    state: ScanState = engine.scan(tokens=("-vv",))
    expect_in(member="verbose", container=state.flags)


def test_short_option_attached_value(tmp_path: Path) -> None:
    """``-fjson`` commits the value to ``--format``.

    Args:
        tmp_path: Provider working directory.

    """
    engine: CompletionEngine = _engine(working_directory=tmp_path)
    state: ScanState = engine.scan(tokens=("-fjson",))
    expect_in(member=("format", "json"), container=state.values)


def test_negative_number_is_a_value(tmp_path: Path) -> None:
    """A negative number feeds the pending option, not options.

    Args:
        tmp_path: Provider working directory.

    """
    engine: CompletionEngine = _engine(working_directory=tmp_path)
    state: ScanState = engine.scan(tokens=("--depth", "-3"))
    expect_in(member=("depth", "-3"), container=state.values)


def test_option_prefix_interrupts_satisfied_pending(tmp_path: Path) -> None:
    """After a satisfied option value, ``-`` offers options.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--format", "json", "--"),
        prefix="--",
    )
    expect_in(member="--verbose", container=values)


def test_greedy_option_keeps_collecting(tmp_path: Path) -> None:
    """``nargs='*'`` keeps consuming values until a known option.

    Args:
        tmp_path: Provider working directory.

    """
    engine: CompletionEngine = _engine(working_directory=tmp_path)
    state: ScanState = engine.scan(tokens=("--many", "one", "two"))
    expect_equal(actual=state.pending is not None, expected=True)
    values: tuple[str, ...] = _values(
        working_directory=tmp_path,
        words=("root", "--many", "one", "--"),
        prefix="--",
    )
    expect_in(member="--verbose", container=values)


def test_candidates_sorted_by_kind_then_value(tmp_path: Path) -> None:
    """Candidate order is deterministic: kind, then value.

    Args:
        tmp_path: Provider working directory.

    """
    candidates: tuple[CompletionCandidate, ...] = _complete(
        working_directory=tmp_path,
        words=("root", ""),
        prefix="",
    )
    kinds: Final = tuple(candidate.kind for candidate in candidates)
    expect_equal(actual=kinds, expected=tuple(sorted(kinds)))


def test_warm_static_completion_latency(tmp_path: Path) -> None:
    """Warm static completion stays within the 100 ms regression budget.

    Args:
        tmp_path: Provider working directory.

    """
    engine: CompletionEngine = _engine(working_directory=tmp_path)
    request: CompletionRequest = CompletionRequest(
        shell=CompletionShell.BASH,
        words=("exactus", "--f"),
        active_word_index=1,
        prefix="--f",
    )
    _ = engine.complete(request=request)
    started: float = perf_counter()
    for _ in range(10):
        _ = engine.complete(request=request)
    mean_seconds: float = (perf_counter() - started) / 10
    budget_seconds: float = 0.1
    expect_true(condition=mean_seconds < budget_seconds)


def _folded_engine(*, working_directory: Path) -> CompletionEngine:
    """Create an engine over a grammar with dashed long options.

    Args:
        working_directory: Directory providers resolve against.

    Returns:
        Engine whose options mirror the parser's dash/underscore folding.

    """
    root: CommandSpec = CommandSpec(
        name="root",
        description="Folding grammar",
        options=(
            OptionSpec(
                names=("--dry-run", "--dry"),
                dest="dry",
                cardinality=Constants.no_value,
                description="Dry run",
            ),
            OptionSpec(
                names=("--collect-files",),
                dest="collect_files",
                cardinality=Constants.no_value,
                description="Collect files",
            ),
        ),
    )
    return CompletionEngine(
        catalog=CompletionCatalog(root=root, contexts=()),
        command_name="root",
        providers={},
        working_directory=working_directory,
    )


def _folded_values(
    *,
    working_directory: Path,
    words: tuple[str, ...],
) -> tuple[str, ...]:
    """Complete the last word of ``words`` over the folding grammar.

    Args:
        working_directory: Directory providers resolve against.
        words: Logical command words including the active word.

    Returns:
        Candidate values.

    """
    return tuple(
        candidate.value
        for candidate in _folded_engine(
            working_directory=working_directory,
        ).complete(
            request=CompletionRequest(
                shell=CompletionShell.BASH,
                words=words,
                active_word_index=len(words) - 1,
                prefix=words[-1],
            ),
        )
    )


def test_underscore_prefix_offers_the_dashed_option(tmp_path: Path) -> None:
    """``--collect_`` completes to the registered ``--collect-files``.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _folded_values(
        working_directory=tmp_path,
        words=("root", "--collect_"),
    )
    expect_in(member="--collect-files", container=values)
    expect_not_in(member="--dry-run", container=values)


def test_underscore_spelling_counts_as_a_used_option(tmp_path: Path) -> None:
    """``--dry_run`` suppresses a second ``--dry-run`` suggestion.

    Args:
        tmp_path: Provider working directory.

    """
    values: tuple[str, ...] = _folded_values(
        working_directory=tmp_path,
        words=("root", "--dry_run", "--"),
    )
    expect_not_in(member="--dry-run", container=values)
    expect_in(member="--collect-files", container=values)
