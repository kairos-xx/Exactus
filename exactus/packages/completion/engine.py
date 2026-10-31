# Copyright (c) 2026
"""Grammar-aware word scanner and candidate producer.

The scanner replays every completed word before the cursor against the
catalog to recover committed CLI state — active grammar context, used
options, pending option values, positional index. The decision tree
then maps that state plus the active prefix to candidate records.

Dynamic providers are only consulted at the last step and only for the
argument actually being completed; scanning itself is pure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from re import fullmatch
from typing import TYPE_CHECKING, Final, final

from exactus.packages.argument_parser import normalized_option

from .model import (
    CompletionCandidate,
    CompletionContext,
    CompletionKind,
    CompletionRequest,
    RecognizedArguments,
)

if TYPE_CHECKING:
    from pathlib import Path

    from .catalog import (
        CommandSpec,
        CompletionCatalog,
        OptionSpec,
        PositionalSpec,
        ProviderId,
    )
    from .model import CompletionProvider


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_candidates: Grouped module constant.
        max_description: Grouped module constant.
        provider_errors: Grouped module constant.
        negative_number: Grouped module constant.
        kind_order: Grouped module constant.

    """

    max_candidates: Final[int] = 500
    max_description: Final[int] = 200
    provider_errors: Final[tuple[type[BaseException], ...]] = (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RuntimeError,
    )
    negative_number: Final[str] = "-\\d+(\\.\\d+)?"
    kind_order: Final[dict[CompletionKind, int]] = {
        CompletionKind.COMMAND: 0,
        CompletionKind.OPTION: 1,
        CompletionKind.VALUE: 2,
        CompletionKind.FILE: 3,
        CompletionKind.DIRECTORY: 4,
    }


"Maximum candidates emitted for one completion request."
"Maximum description length in Unicode code points."
"Expected provider failure modes converted to empty candidates."
"Pattern recognizing value tokens that merely start with a dash."
"Deterministic candidate category ordering."


@dataclass(frozen=True, slots=True)
class ScanState:
    """Committed CLI state after scanning completed tokens.

    Attributes:
        command: Currently active grammar context.
        options_enabled: Whether ``-`` tokens still parse as options
            (``False`` after a ``--`` marker).
        pending: Option currently collecting values, if any.
        pending_consumed: Values already assigned to ``pending``.
        positional_index: Index of the active positional spec.
        positional_consumed: Values assigned to the active positional.
        used: Canonical names of options already supplied.
        used_groups: Mutex groups with a member already supplied.
        flags: Destinations of valueless options already supplied.
        values: ``(dest, value)`` pairs for single-value options.
        multi_values: ``(dest, values)`` pairs for repeatable and
            multi-value options.
        positionals: Positional values consumed so far.
        command_path: Dispatch tokens that selected the active grammar.

    """

    command: CommandSpec
    options_enabled: bool = True
    pending: OptionSpec | None = None
    pending_consumed: int = 0
    positional_index: int = 0
    positional_consumed: int = 0
    used: frozenset[str] = frozenset()
    used_groups: frozenset[str] = frozenset()
    flags: frozenset[str] = frozenset()
    values: tuple[tuple[str, str], ...] = ()
    multi_values: tuple[tuple[str, tuple[str, ...]], ...] = ()
    positionals: tuple[str, ...] = ()
    command_path: tuple[str, ...] = ()

    def recognized(self) -> RecognizedArguments:
        """Render the scanner's accumulators as recognized arguments.

        Returns:
            Immutable recognized-arguments view for providers.

        """
        return RecognizedArguments(
            flags=self.flags,
            values=self.values,
            multi_values=self.multi_values,
            positionals=self.positionals,
            command_path=self.command_path,
        )


class CompletionEngine:
    """Turn a shell's completion request into candidates.

    Attributes:
        catalog: CLI grammar the engine interprets.
        providers: Dynamic providers keyed by identifier.
        working_directory: Directory filesystem values resolve
            against.
        command_name: Executable name stripped from ``words[0]``.

    """

    def __init__(
        self,
        *,
        catalog: CompletionCatalog,
        providers: dict[ProviderId, CompletionProvider],
        working_directory: Path,
        command_name: str,
    ) -> None:
        """Initialize the engine.

        Args:
            catalog: CLI grammar the engine interprets.
            providers: Dynamic providers keyed by identifier.
            working_directory: Directory filesystem values resolve
                against.
            command_name: Executable name stripped from ``words[0]``.

        """
        self.catalog: CompletionCatalog = catalog
        self.providers: dict[ProviderId, CompletionProvider] = providers
        self.working_directory: Path = working_directory
        self.command_name: str = command_name

    def complete(
        self,
        *,
        request: CompletionRequest,
    ) -> tuple[CompletionCandidate, ...]:
        """Produce candidates for one completion request.

        Args:
            request: Normalized shell completion state.

        Returns:
            Prefix-filtered, deduplicated, deterministic candidates.

        """
        completed: tuple[str, ...] = tuple(
            request.words[1 : request.active_word_index],
        )
        state: ScanState = self.scan(tokens=completed)
        context: CompletionContext = CompletionContext(
            command_path=state.command_path,
            words=completed,
            prefix=request.prefix,
            recognized=state.recognized(),
            working_directory=self.working_directory,
        )
        candidates: tuple[CompletionCandidate, ...] = self._produce(
            state=state,
            context=context,
        )
        return _finalize(candidates=candidates)

    def scan(self, *, tokens: tuple[str, ...]) -> ScanState:
        """Replay completed tokens into committed grammar state.

        Args:
            tokens: Logical words strictly before the active word.

        Returns:
            The resulting scan state.

        """
        state: ScanState = ScanState(command=self.catalog.root)
        for word in tokens:
            state = self._step(state=state, word=word)
        return state

    @staticmethod
    def _is_pending_value(*, state: ScanState, word: str) -> bool:
        """Return whether ``word`` feeds the pending option.

        A word starts a new option — and therefore ends the pending
        option's value run — only when the pending option's minimum is
        already satisfied and the word exactly names a known option or
        is ``--``. Negative numbers always count as values.

        Args:
            state: Committed state including the pending option.
            word: Token to classify.

        Returns:
            Whether the word is consumed as a value.

        """
        option: OptionSpec | None = state.pending
        if option is None or not option.cardinality.accepts_more(
            consumed=state.pending_consumed,
        ):
            return False
        if (
            fullmatch(pattern=Constants.negative_number, string=word)
            is not None
        ):
            return True
        satisfied: bool = option.cardinality.satisfied(
            consumed=state.pending_consumed,
        )
        if not state.options_enabled or not satisfied:
            return True
        if word == "--":
            return False
        command: CommandSpec = state.command
        if (
            command.option_named(word=word) is not None
            or command.subcommand_named(word=word) is not None
        ):
            return False
        name, has_value, _suffix = word.partition("=")
        return not (
            has_value
            and word.startswith("--")
            and (command.option_named(word=name) is not None)
        )

    @staticmethod
    def _consume_value(*, state: ScanState, word: str) -> ScanState:
        """Assign ``word`` to the pending option's value run.

        Args:
            state: Committed state with a pending option.
            word: Value word.

        Returns:
            State with the value recorded and pending released when the
            option's cardinality is exhausted.

        """
        option: OptionSpec | None = state.pending
        if option is None:
            return state
        consumed: int = state.pending_consumed + 1
        values: tuple[tuple[str, str], ...] = state.values
        multi: tuple[tuple[str, tuple[str, ...]], ...] = state.multi_values
        if option.repeatable or option.cardinality.maximum != 1:
            multi = (*multi, (option.dest, (word,)))
        else:
            values = (*values, (option.dest, word))
        done: bool = not option.cardinality.accepts_more(consumed=consumed)
        return replace(
            state,
            pending=None if done else option,
            pending_consumed=consumed,
            values=values,
            multi_values=multi,
        )

    @staticmethod
    def _consume_positional(*, state: ScanState, word: str) -> ScanState:
        """Assign ``word`` to the active positional.

        Args:
            state: Committed state.
            word: Value word.

        Returns:
            State with the positional recorded and the index advanced
            when the spec's cardinality is exhausted.

        """
        positionals: tuple[str, ...] = (*state.positionals, word)
        index: int = state.positional_index
        consumed: int = state.positional_consumed + 1
        spec: PositionalSpec | None = (
            state.command.positionals[index]
            if index < len(state.command.positionals)
            else None
        )
        if spec is not None and (
            not spec.cardinality.accepts_more(consumed=consumed)
        ):
            return replace(
                state,
                positional_index=index + 1,
                positional_consumed=0,
                positionals=positionals,
            )
        return replace(
            state,
            positional_consumed=consumed,
            positionals=positionals,
        )

    @staticmethod
    def _options(
        *,
        state: ScanState,
        prefix: str,
    ) -> tuple[CompletionCandidate, ...]:
        """Produce option candidates legal in the current state.

        Args:
            state: Committed grammar state.
            prefix: Current word prefix (``-``-leading).

        Returns:
            Option-name candidates, suppressed options removed.

        """
        candidates: list[CompletionCandidate] = []
        for option in state.command.options:
            if option.hidden:
                continue
            if not option.repeatable and option.canonical_name in state.used:
                continue
            if (
                option.mutex_group is not None
                and option.mutex_group in state.used_groups
                and (option.canonical_name not in state.used)
            ):
                continue
            names: tuple[str, ...] = (
                (option.canonical_name,)
                if option.canonical_only
                else option.names
            )
            candidates.extend(
                CompletionCandidate(
                    value=name,
                    display=name,
                    description=option.description,
                    kind=CompletionKind.OPTION,
                    append_space=True,
                )
                for name in names
                if name.startswith(prefix)
                or (
                    prefix.startswith("--")
                    and normalized_option(argument=name).startswith(
                        normalized_option(argument=prefix),
                    )
                )
            )
        return tuple(candidates)

    def _step(self, *, state: ScanState, word: str) -> ScanState:
        """Advance the scanner over one completed word.

        Args:
            state: Committed state so far.
            word: Token to interpret.

        Returns:
            The updated scan state.

        """
        if state.pending is not None:
            if self._is_pending_value(state=state, word=word):
                return self._consume_value(state=state, word=word)
            state = replace(state, pending=None, pending_consumed=0)
        if state.options_enabled and word == "--":
            return replace(state, options_enabled=False)
        option_step: ScanState | None = (
            self._step_option(state=state, word=word)
            if state.options_enabled
            else None
        )
        if option_step is not None:
            return option_step
        return self._step_word(state=state, word=word)

    def _step_option(self, *, state: ScanState, word: str) -> ScanState | None:
        """Interpret ``word`` as an option-shaped token.

        Args:
            state: Committed state so far.
            word: Token to interpret.

        Returns:
            Updated state when the token names an option, is
            ``--name=value``, or forms a short cluster, else ``None``.

        """
        command: CommandSpec = state.command
        option: OptionSpec | None = command.option_named(word=word)
        if option is not None:
            return self._use_option(state=state, option=option)
        if word.startswith("--") and "=" in word:
            name, _, value = word.partition("=")
            option = command.option_named(word=name)
            if option is not None:
                used: ScanState = self._use_option(state=state, option=option)
                return (
                    self._consume_value(state=used, word=value)
                    if option.takes_values
                    else used
                )
        return self._match_short(state=state, word=word)

    def _step_word(self, *, state: ScanState, word: str) -> ScanState:
        """Interpret ``word`` as a subcommand or positional value.

        Args:
            state: Committed state so far.
            word: Token to interpret.

        Returns:
            The updated scan state.

        """
        subcommand: CommandSpec | None = state.command.subcommand_named(
            word=word,
        )
        if subcommand is not None:
            return replace(
                ScanState(command=subcommand),
                used=state.used,
                used_groups=state.used_groups,
                flags=state.flags,
                values=state.values,
                multi_values=state.multi_values,
                command_path=(*state.command_path, word),
            )
        return self._consume_positional(state=state, word=word)

    def _use_option(
        self,
        *,
        state: ScanState,
        option: OptionSpec,
    ) -> ScanState:
        """Record one option occurrence and start its value run.

        Args:
            state: Committed state.
            option: Matched option spec.

        Returns:
            State with the option marked used, pending state armed when
            the option consumes values, and the grammar context switched
            when the option is a dispatch flag.

        """
        used: frozenset[str] = state.used | {option.canonical_name}
        groups: frozenset[str] = (
            state.used_groups | {option.mutex_group}
            if option.mutex_group is not None
            else state.used_groups
        )
        command: CommandSpec = state.command
        command_path: tuple[str, ...] = state.command_path
        if option.context is not None:
            target: CommandSpec | None = self.catalog.context_named(
                name=option.context,
            )
            if target is not None:
                command = target
                command_path = (*command_path, option.canonical_name)
        pending: OptionSpec | None = option if option.takes_values else None
        return replace(
            state,
            command=command,
            pending=pending,
            pending_consumed=0,
            used=used,
            used_groups=groups,
            flags=state.flags
            if pending is not None
            else state.flags | {option.dest},
            command_path=command_path,
        )

    def _match_short(self, *, state: ScanState, word: str) -> ScanState | None:
        """Interpret ``-oVALUE`` attachments and ``-abc`` flag clusters.

        Args:
            state: Committed state.
            word: Short-option-shaped word (single leading dash).

        Returns:
            Updated state when the word is fully explained by the
            grammar, else ``None``.

        """
        if not word.startswith("-") or word.startswith("--"):
            return None
        command: CommandSpec = state.command
        names: dict[str, OptionSpec] = {
            name: option
            for option in command.options
            for name in option.names
            if name.startswith("-") and (not name.startswith("--"))
        }
        for name in sorted(names, key=len, reverse=True):
            if len(word) > len(name) and word.startswith(name):
                option: OptionSpec = names[name]
                if not option.takes_values:
                    continue
                used: ScanState = self._use_option(state=state, option=option)
                return self._consume_value(state=used, word=word[len(name) :])
        chars: str = word[1:]
        current: ScanState = state
        for index, char in enumerate(iterable=chars):
            member: OptionSpec | None = names.get(f"-{char}")
            if member is None:
                return None
            current = self._use_option(state=current, option=member)
            if member.takes_values:
                remainder: str = chars[index + 1 :]
                if not remainder:
                    return current
                return self._consume_value(state=current, word=remainder)
        return current

    def _produce(
        self,
        *,
        state: ScanState,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Map scan state plus prefix to raw candidates.

        Args:
            state: Committed grammar state.
            context: Provider-visible completion context carrying the
                active prefix.

        Returns:
            Unsorted candidates.

        """
        prefix: str = context.prefix
        pending: OptionSpec | None = state.pending
        if pending is not None and (
            not pending.cardinality.satisfied(consumed=state.pending_consumed)
        ):
            return self._values(option=pending, prefix=prefix, context=context)
        if pending is not None and pending.cardinality.accepts_more(
            consumed=state.pending_consumed,
        ):
            if not (state.options_enabled and prefix.startswith("-")):
                return self._values(
                    option=pending,
                    prefix=prefix,
                    context=context,
                )
            state = replace(state, pending=None, pending_consumed=0)
        command: CommandSpec = state.command
        if (
            state.options_enabled
            and prefix.startswith("--")
            and ("=" in prefix)
        ):
            name, _, value_prefix = prefix.partition("=")
            inline: OptionSpec | None = command.option_named(word=name)
            if inline is not None:
                if not inline.takes_values:
                    return ()
                return self._inline(
                    option=inline,
                    name=name,
                    value_prefix=value_prefix,
                    context=context,
                )
        if state.options_enabled and prefix.startswith("-"):
            return self._options(state=state, prefix=prefix)
        candidates: list[CompletionCandidate] = [
            CompletionCandidate(
                value=subcommand.name,
                display=subcommand.name,
                description=subcommand.description,
                kind=CompletionKind.COMMAND,
                append_space=True,
            )
            for subcommand in command.subcommands
            if not subcommand.hidden
        ]
        positional: PositionalSpec | None = (
            command.positionals[state.positional_index]
            if state.positional_index < len(command.positionals)
            else None
        )
        if positional is not None:
            candidates.extend(
                self._positional_values(
                    positional=positional,
                    prefix=prefix,
                    context=context,
                ),
            )
        return tuple(candidates)

    def _values(
        self,
        *,
        option: OptionSpec,
        prefix: str,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Produce value candidates for one option.

        Args:
            option: Option collecting values.
            prefix: Current value prefix.
            context: Provider-visible context.

        Returns:
            Static and dynamic value candidates.

        """
        seen: tuple[str, ...] = (
            context.recognized.get_many(dest=option.dest)
            if option.repeatable or option.cardinality.maximum != 1
            else ()
        )
        candidates: list[CompletionCandidate] = [
            candidate
            for candidate in self._argument_values(
                provider=option.provider,
                static_values=option.static_values,
                description=option.description,
                prefix=prefix,
                context=context,
            )
            if candidate.value not in seen
        ]
        return tuple(candidates)

    def _positional_values(
        self,
        *,
        positional: PositionalSpec,
        prefix: str,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Produce value candidates for one positional.

        Args:
            positional: Active positional spec.
            prefix: Current value prefix.
            context: Provider-visible context.

        Returns:
            Static and dynamic value candidates.

        """
        return self._argument_values(
            provider=positional.provider,
            static_values=positional.static_values,
            description=positional.description,
            prefix=prefix,
            context=context,
        )

    def _argument_values(
        self,
        *,
        provider: ProviderId | None,
        static_values: tuple[str, ...],
        description: str,
        prefix: str,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Merge static choices and dynamic provider candidates.

        Args:
            provider: Dynamic provider identifier, if any.
            static_values: Static choice values.
            description: Parser help reused for static candidates.
            prefix: Current value prefix.
            context: Provider-visible context.

        Returns:
            Prefix-filtered candidates, dynamic first.

        """
        dynamic: tuple[CompletionCandidate, ...] = ()
        if provider is not None:
            instance: CompletionProvider | None = self.providers.get(provider)
            if instance is not None:
                scoped: CompletionContext = replace(context, prefix=prefix)
                try:
                    dynamic = instance.complete(context=scoped)
                except Constants.provider_errors:
                    dynamic = ()
        static: tuple[CompletionCandidate, ...] = tuple(
            CompletionCandidate(
                value=value,
                display=value,
                description=description,
                kind=CompletionKind.VALUE,
                append_space=True,
            )
            for value in static_values
        )
        return tuple(
            candidate
            for candidate in (*dynamic, *static)
            if candidate.value.startswith(prefix)
        )

    def _inline(
        self,
        *,
        option: OptionSpec,
        name: str,
        value_prefix: str,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Produce ``--name=value`` insertion candidates.

        Args:
            option: Matched option.
            name: Option name on the left of ``=``.
            value_prefix: Value prefix on the right.
            context: Provider-visible context.

        Returns:
            Candidates preserving the ``--name=`` left side.

        """
        return tuple(
            CompletionCandidate(
                value=f"{name}={candidate.value}",
                display=candidate.value,
                description=candidate.description,
                kind=candidate.kind,
                append_space=True,
            )
            for candidate in self._values(
                option=option,
                prefix=value_prefix,
                context=context,
            )
        )


def _finalize(
    *,
    candidates: tuple[CompletionCandidate, ...],
) -> tuple[CompletionCandidate, ...]:
    """Deduplicate, sort, describe and cap the candidate list.

    Args:
        candidates: Raw candidates from every source.

    Returns:
        Deterministic candidate tuple capped at ``MAX_CANDIDATES``.

    """
    deduplicated: dict[str, CompletionCandidate] = {}
    for candidate in candidates:
        if candidate.value not in deduplicated:
            deduplicated[candidate.value] = replace(
                candidate,
                description=candidate.description[: Constants.max_description],
            )
    ordered: list[CompletionCandidate] = sorted(
        deduplicated.values(),
        key=lambda candidate: (
            Constants.kind_order[candidate.kind],
            candidate.value,
        ),
    )
    return tuple(ordered[: Constants.max_candidates])
