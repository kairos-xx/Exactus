# Copyright (c) 2026
"""Shared argument parser accepting ``-`` and ``_`` interchangeably.

Long options differ across tools only by habit: some options are spelled
with dashes, others with underscores. ``ExactusArgumentParser`` folds the
two spellings at parse time so every registered long option accepts both
forms without help-text noise or duplicated flags.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from sys import modules
from typing import TYPE_CHECKING, TypeVar, cast, final, overload

if TYPE_CHECKING:
    from collections.abc import Iterable
_N = TypeVar(name="_N")


def normalized_option(*, argument: str) -> str:
    """Fold dashes to underscores in the name part of a long option.

    Args:
        argument: Command-line token, possibly ``--name`` or
            ``--name=value``.

    Returns:
        ``--``-prefixed tokens with the option name folded; short
        options, ``--``, and positionals pass through untouched.

    """
    if not argument.startswith("--") or argument == "--":
        return argument
    name: str
    separator: str
    value: str
    name, separator, value = argument.partition("=")
    return "--" + name[2:].replace("-", "_") + separator + value


@final
class ExactusArgumentParser(ArgumentParser):
    """``ArgumentParser`` accepting ``-``/``_`` long-option spellings."""

    @overload
    def parse_known_args(
        self,
        args: Iterable[str] | None = None,
        namespace: None = None,
    ) -> tuple[Namespace, list[str]]: ...
    @overload
    def parse_known_args(
        self,
        args: Iterable[str] | None,
        namespace: _N,
    ) -> tuple[_N, list[str]]: ...
    @overload
    def parse_known_args(self, *, namespace: _N) -> tuple[_N, list[str]]: ...
    def parse_known_args(
        self,
        args: Iterable[str] | None = None,
        namespace: _N | None = None,
    ) -> tuple[_N, list[str]]:
        """Rewrite alternative long-option spellings, then parse.

        Each ``--token`` whose dash/underscore-folded name matches a
        registered long option is rewritten to the registered spelling;
        folded names claimed by two different options fall back to exact
        matching. Parsing stops folding after a bare ``--`` separator.

        Args:
            args: Arguments to parse; ``None`` reads ``sys.argv[1:]``.
            namespace: Optional namespace to populate.

        Returns:
            Populated namespace and unrecognized arguments.

        """
        folded: dict[str, str] = {}
        collisions: set[str] = set()
        for option in self._option_string_actions:
            if not option.startswith("--"):
                continue
            key: str = normalized_option(argument=option)
            if key in folded and folded[key] != option:
                collisions.add(key)
            else:
                folded[key] = option
        for key in collisions:
            del folded[key]
        tokens: list[str] = []
        separated: bool = False
        source: Iterable[str] = (
            modules["sys"].argv[1:] if args is None else args
        )
        for argument in list(source):
            if separated or argument == "--":
                separated = True
                tokens.append(argument)
                continue
            rewritten: str = argument
            if argument.startswith("--"):
                name: str
                separator: str
                value: str
                name, separator, value = argument.partition("=")
                canonical: str | None = folded.get(
                    normalized_option(argument=name),
                )
                if canonical is not None:
                    rewritten = canonical + separator + value
            tokens.append(rewritten)
        if namespace is None:
            return cast(
                typ="tuple[_N, list[str]]",
                val=super().parse_known_args(args=tokens),
            )
        return super().parse_known_args(args=tokens, namespace=namespace)
