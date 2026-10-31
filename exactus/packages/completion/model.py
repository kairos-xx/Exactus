# Copyright (c) 2026
"""Typed shell-completion domain values.

Every value here is immutable: the engine, providers and shell adapters
exchange frozen dataclasses so completion stays deterministic and free
of hidden mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final, Protocol, final

if TYPE_CHECKING:
    from pathlib import Path


class CompletionShell(StrEnum):
    """Interactive shells with a generated registration adapter.

    Attributes:
        BASH: Bash registration adapter.
        ZSH: Zsh registration adapter.
        FISH: Fish registration adapter.
        POWERSHELL: PowerShell registration adapter.

    """

    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"


class CompletionKind(StrEnum):
    """Semantic kind of a completion candidate.

    Attributes:
        COMMAND: Subcommand name.
        OPTION: Option flag.
        VALUE: Option or positional value.
        FILE: File path.
        DIRECTORY: Directory path.

    """

    COMMAND = "command"
    OPTION = "option"
    VALUE = "value"
    FILE = "file"
    DIRECTORY = "directory"


class CandidateFlag(IntFlag):
    """Wire-protocol bit flags describing one candidate.

    Attributes:
        NONE: No additional behavior.
        APPEND_SPACE: Append a space after insertion.
        PATH: Apply shell path escaping.
        DIRECTORY: Treat the path as a directory.
        DEPRECATED: Identify a deprecated candidate.

    """

    NONE = 0
    APPEND_SPACE = 1
    PATH = 2
    DIRECTORY = 4
    DEPRECATED = 8


@dataclass(frozen=True, slots=True)
class CompletionCandidate:
    """One value the shell may insert.

    Attributes:
        value: Logical insertion text (never shell-escaped).
        display: Label shown in list UIs; usually equals ``value``.
        description: One-line explanation for shells that show one.
        kind: Semantic candidate kind.
        append_space: Whether the shell should append a space after
            inserting this candidate.

    """

    value: str
    display: str
    description: str
    kind: CompletionKind
    append_space: bool

    @property
    def flags(self) -> int:
        """Encode this candidate's metadata as wire flags.

        Returns:
            Bit mask of :class:`CandidateFlag` values.

        """
        flags: CandidateFlag = CandidateFlag.NONE
        if self.append_space:
            flags |= CandidateFlag.APPEND_SPACE
        if self.kind in (CompletionKind.FILE, CompletionKind.DIRECTORY):
            flags |= CandidateFlag.PATH
        if self.kind is CompletionKind.DIRECTORY:
            flags |= CandidateFlag.DIRECTORY
        return int(flags)


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """Normalized command-line state supplied by a shell adapter.

    Attributes:
        shell: Requesting interactive shell.
        words: Logical command words, including the active word.
        active_word_index: Index into ``words`` of the edited token.
        prefix: Text up to the cursor inside the active word.
        protocol_version: Requested internal protocol version.

    """

    shell: CompletionShell
    words: tuple[str, ...]
    active_word_index: int
    prefix: str
    protocol_version: int = 1


@dataclass(frozen=True, slots=True)
class RecognizedArguments:
    """Arguments the scanner already committed before the cursor.

    Attributes:
        flags: Destinations of valueless options already supplied.
        values: ``(destination, value)`` pairs for single-value options.
        multi_values: ``(destination, values)`` pairs for repeatable or
            multi-value options.
        positionals: Positional values already consumed.
        command_path: Dispatch tokens that selected the active grammar.

    """

    flags: frozenset[str]
    values: tuple[tuple[str, str], ...]
    multi_values: tuple[tuple[str, tuple[str, ...]], ...]
    positionals: tuple[str, ...]
    command_path: tuple[str, ...]

    def get_one(self, *, dest: str) -> str | None:
        """Return the last recorded single value for ``dest``.

        Args:
            dest: Option destination.

        Returns:
            The most recent value, or ``None``.

        """
        for name, value in reversed(self.values):
            if name == dest:
                return value
        return None

    def get_many(self, *, dest: str) -> tuple[str, ...]:
        """Return every recorded value for ``dest``.

        Args:
            dest: Option destination.

        Returns:
            Concatenated values in supply order.

        """
        return tuple(
            (
                item
                for name, values in self.multi_values
                if name == dest
                for item in values
            ),
        )

    def has_flag(self, *, dest: str) -> bool:
        """Return whether a valueless option was supplied.

        Args:
            dest: Option destination.

        Returns:
            Whether the flag was already recognized.

        """
        return dest in self.flags


@dataclass(frozen=True, slots=True)
class CompletionContext:
    """Context exposed to dynamic candidate providers.

    Attributes:
        command_path: Dispatch tokens selecting the active grammar.
        words: Logical command words before the cursor.
        prefix: Current value prefix being completed.
        recognized: Arguments already committed by the scanner.
        working_directory: Directory filesystem providers resolve
            relative paths against.

    """

    command_path: tuple[str, ...]
    words: tuple[str, ...]
    prefix: str
    recognized: RecognizedArguments
    working_directory: Path


class CompletionProvider(Protocol):
    """Contract implemented by dynamic completion providers."""

    def complete(
        self,
        *,
        context: CompletionContext,
    ) -> tuple[CompletionCandidate, ...]:
        """Return completion candidates for the supplied context.

        Args:
            context: Normalized completion state.

        Returns:
            Candidates, prefix-filtered by the provider's own logic.

        """
        ...


@dataclass(frozen=True, slots=True)
class ValueCardinality:
    """Minimum and maximum values one argument consumes.

    Attributes:
        minimum: Values required for the argument to be satisfied.
        maximum: Values accepted; ``None`` means unbounded.
        consumes_remainder: Whether the argument swallows every
            remaining token (``argparse.REMAINDER`` semantics).

    """

    minimum: int
    maximum: int | None
    consumes_remainder: bool = False

    def satisfied(self, *, consumed: int) -> bool:
        """Return whether ``consumed`` values meet the minimum.

        Args:
            consumed: Values already assigned.

        Returns:
            Whether the minimum was reached.

        """
        return consumed >= self.minimum

    def accepts_more(self, *, consumed: int) -> bool:
        """Return whether the argument accepts another value.

        Args:
            consumed: Values already assigned.

        Returns:
            Whether one more value is legal.

        """
        if self.consumes_remainder:
            return True
        return self.maximum is None or consumed < self.maximum


@final
class Constants:
    """Group module-level constants.

    Attributes:
        field_separator: Grouped module constant.
        no_value: Grouped module constant.
        one_value: Grouped module constant.
        optional_value: Grouped module constant.
        any_values: Grouped module constant.
        at_least_one: Grouped module constant.

    """

    field_separator: Final[str] = "\x1f"
    "ASCII Unit Separator delimiting wire-protocol record fields."
    no_value: Final[ValueCardinality] = ValueCardinality(minimum=0, maximum=0)
    "Cardinality of ``store_true``/``store_false``/``count`` actions."
    one_value: Final[ValueCardinality] = ValueCardinality(minimum=1, maximum=1)
    optional_value: Final[ValueCardinality] = ValueCardinality(
        minimum=0,
        maximum=1,
    )
    any_values: Final[ValueCardinality] = ValueCardinality(
        minimum=0,
        maximum=None,
    )
    at_least_one: Final[ValueCardinality] = ValueCardinality(
        minimum=1,
        maximum=None,
    )


"Cardinality of a plain option or positional."
'Cardinality of ``nargs="?"``.'
'Cardinality of ``nargs="*"``.'
'Cardinality of ``nargs="+"``.'
