# Copyright (c) 2026
"""Dash/underscore folding in the shared ``ExactusArgumentParser``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.packages.argument_parser import (
    ExactusArgumentParser,
    normalized_option,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)

if TYPE_CHECKING:
    from argparse import Namespace


def _parser() -> ExactusArgumentParser:
    """Build a parser with dashed and underscored long options.

    Returns:
        Parser registering ``--foo-bar``, ``--baz-qux``, ``--dry``, and
        a positional.

    """
    parser: ExactusArgumentParser = ExactusArgumentParser()
    _ = parser.add_argument("--foo-bar", action="store_true")
    _ = parser.add_argument("--baz-qux")
    _ = parser.add_argument("--dry", action="store_true")
    _ = parser.add_argument("pos", nargs="?")
    return parser


def test_normalized_option_folds_long_names() -> None:
    """Only the name part of ``--`` tokens is folded."""
    expect_equal(
        actual=normalized_option(argument="--foo-bar"),
        expected="--foo_bar",
    )
    expect_equal(
        actual=normalized_option(argument="--foo-bar=baz"),
        expected="--foo_bar=baz",
    )
    expect_equal(actual=normalized_option(argument="-f"), expected="-f")
    expect_equal(actual=normalized_option(argument="--"), expected="--")
    expect_equal(actual=normalized_option(argument="pos-a"), expected="pos-a")


def test_dash_and_underscore_parse_identically() -> None:
    """Both spellings populate the same destination."""
    parser: ExactusArgumentParser = _parser()
    dashed: Namespace = parser.parse_args(args=["--foo-bar", "--baz-qux", "v"])
    underscored: Namespace = parser.parse_args(
        args=["--foo_bar", "--baz_qux", "v"],
    )
    expect_equal(actual=dashed, expected=underscored)
    expect_true(condition=dashed.foo_bar)
    expect_equal(actual=dashed.baz_qux, expected="v")


def test_equal_form_and_separator() -> None:
    """``--opt=value`` folds and ``--`` stops folding."""
    parser: ExactusArgumentParser = _parser()
    ns: Namespace = parser.parse_args(args=["--baz_qux=v"])
    expect_equal(actual=ns.baz_qux, expected="v")
    ns = parser.parse_args(args=["--", "--baz_qux=v"])
    expect_equal(actual=ns.pos, expected="--baz_qux=v")
    expect_equal(actual=ns.baz_qux, expected=None)


def test_abbrev_matching_still_works() -> None:
    """Unique-prefix abbreviations of registered spellings keep working."""
    parser: ExactusArgumentParser = _parser()
    ns: Namespace = parser.parse_args(args=["--foo-b"])
    expect_true(condition=ns.foo_bar)


def test_colliding_spellings_fall_back_to_exact() -> None:
    """Options differing only by ``-``/``_`` keep exact matching only."""
    parser: ExactusArgumentParser = ExactusArgumentParser()
    _ = parser.add_argument("--a-b", dest="dashed", action="store_true")
    _ = parser.add_argument("--a_b", dest="underscored", action="store_true")
    ns: Namespace = parser.parse_args(args=["--a-b"])
    expect_true(condition=ns.dashed)
    expect_false(condition=ns.underscored)
    ns = parser.parse_args(args=["--a_b"])
    expect_false(condition=ns.dashed)
    expect_true(condition=ns.underscored)


def test_subparsers_inherit_folding() -> None:
    """``add_subparsers`` children fold spellings automatically."""
    parser: ExactusArgumentParser = ExactusArgumentParser()
    child: ExactusArgumentParser = parser.add_subparsers(
        dest="cmd",
        required=True,
    ).add_parser(name="serve")
    _ = child.add_argument("--no-cache", action="store_true")
    ns: Namespace = parser.parse_args(args=["serve", "--no_cache"])
    expect_true(condition=ns.no_cache)


def test_unmatched_tokens_pass_through() -> None:
    """Unknown flags and positionals are untouched."""
    parser: ExactusArgumentParser = _parser()
    ns: Namespace
    rest: list[str]
    ns, rest = parser.parse_known_args(
        args=["--other-flag", "value", "--foo_bar"],
    )
    expect_true(condition=ns.foo_bar)
    expect_in(member="--other-flag", container=rest)
    expect_false(condition="--other_flag" in rest)
