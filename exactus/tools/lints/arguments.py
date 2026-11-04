# Copyright (c) 2026
"""Declare the lints grammar without importing its execution engine."""

from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path
from re import Match, fullmatch
from typing import TYPE_CHECKING, Final, final

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.cli import add_common_arguments, consume

if TYPE_CHECKING:
    from collections.abc import Mapping


def _positive(value: str) -> int:
    """Parse a positive integer.

    Args:
        value: Command-line value.

    Returns:
        Positive integer.

    Raises:
        ArgumentTypeError: When the value is not positive.

    """
    parsed: int = int(value)
    if parsed < 1:
        msg: str = "value must be at least 1"
        raise ArgumentTypeError(msg)
    return parsed


def _byte_size(value: str) -> int:
    """Parse a byte-size ceiling such as ``33554432`` or ``32MB``.

    Args:
        value: Command-line or configuration value.

    Returns:
        The size in bytes.

    Raises:
        ArgumentTypeError: When the value is not a byte size.

    """
    match: Match[str] | None = fullmatch(
        pattern="(?P<amount>\\d+)\\s*(?P<unit>[a-z]*)",
        string=value.strip().lower(),
    )
    multiplier: int | None = (
        Constants.size_units.get(match["unit"] or "b") if match else None
    )
    if match is None or multiplier is None:
        msg: str = (
            f"expected a byte size such as 33554432, 32MB or 8g, got {value!r}"
        )
        raise ArgumentTypeError(msg)
    return int(match["amount"]) * multiplier


@final
class Constants:
    """Group module-level constants.

    Attributes:
        default_bare_import_exceptions: Grouped module constant.
        size_units: Grouped module constant.

    """

    default_bare_import_exceptions: Final[tuple[str, ...]] = ("pytest", "sys")
    size_units: Final[Mapping[str, int]] = {
        "": 1,
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "k": 1 << 10,
        "kb": 1 << 10,
        "kib": 1 << 10,
        "m": 1 << 20,
        "mb": 1 << 20,
        "mib": 1 << 20,
        "g": 1 << 30,
        "gb": 1 << 30,
        "gib": 1 << 30,
    }


"Modules permitted as bare imports by the default lint policy."


def create_parser() -> ArgumentParser:
    """Create parser.

    Returns:
        The resulting value.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        description=(
            "Clean, lint, and type-check sources; emit the LINTS "
            "Markdown/JSON/web report bundle."
        ),
    )
    add_common_arguments(parser=parser, default_output="LINTS")
    _ = consume(
        value=parser.add_argument(
            "--transaction-passes",
            type=_positive,
            default=4,
            metavar="N",
            help="Maximum complete source transaction passes (default: 4).",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--transaction-timeout",
            type=_positive,
            default=1800,
            metavar="SECONDS",
            help="Total mutation and verification budget "
            "(default: 1800 seconds).",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--workers",
            type=_positive,
            default=None,
            metavar="N",
            help=(
                "Maximum independent external lint processes; defaults to "
                "min(16, CPU count). Use 1 for serial execution."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-clean",
            action="store_true",
            help="Skip source cleaning and formatter passes.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-fix",
            action="store_true",
            help=(
                "Audit only: report without healing. Skips the Ruff "
                "format/check --fix convergence loop along with source "
                "cleaning, convention rewrites, refactors, shebang repair "
                "and guarded inference."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--simple",
            action="store_true",
            help=(
                "Run only the all_lints package audit and report its "
                "findings alone: skips source cleaning, convention scans, "
                "refactors, compliance and guarded inference."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-long-lines",
            action="store_true",
            help=(
                "Skip the long-line repair that runs inside the Ruff -"
                "-fix convergence loop."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-delimiters",
            action="store_true",
            help=(
                "Skip the JavaScript delimiter scan and the delimiter "
                "simplification it applies under --fix."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-notation",
            action="store_true",
            help=(
                "Skip the JavaScript function-block scan and the arrow or "
                "static normalization it applies under --fix."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-infer",
            action="store_true",
            help="Skip guarded pyrefly infer.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-group-final",
            action="store_true",
            help="Skip the group_final refactor that normally runs first.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-organize",
            action="store_true",
            help=(
                "Skip the organize class-method reorder that normally "
                "runs after scope collection."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--unsafe-fixes",
            action="store_true",
            help="Allow Ruff unsafe fixes during all_lints stabilization.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-shebang-heal",
            action="store_true",
            help=(
                "Report shebang/executable mismatches without repairing them."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--exec-no-shebang",
            choices=("add-shebang", "drop-exec"),
            default="add-shebang",
            help=(
                "Heal executable files lacking a shebang by inserting the "
                "interpreter line for their suffix (default) or by "
                "clearing their executable bits."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--shebang-no-exec",
            choices=("add-exec", "drop-shebang"),
            default="add-exec",
            help=(
                "Heal shebang files lacking the executable bit by marking "
                "them executable (default) or by removing the shebang "
                "line."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-install-tools",
            action="store_true",
            help="Do not install missing external tools.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--runtime-max-runs",
            type=_positive,
            default=None,
            metavar="N",
            help=(
                "Finished runs kept in the shared EXACTUS_RESULTS"
                "/.runtime registry; the oldest are pruned after each run "
                "(default: 500)."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--runtime-max-size",
            type=_byte_size,
            default=None,
            metavar="SIZE",
            help=(
                "Byte cap on the shared EXACTUS_RESULTS/.runtime registry "
                "database as raw bytes or a size (for example 33554432 "
                "or 64MB); the oldest finished runs are deleted when it "
                "is exceeded. 0 disables the cap (default: 64MB)."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--bare-import-exception",
            action="append",
            default=list(Constants.default_bare_import_exceptions),
            metavar="MODULE",
            help=(
                "Allow a Python bare import. Repeat for multiple modules; "
                "defaults to pytest."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-python-simplify",
            action="store_true",
            help="Disable safe adjacent-statement Python AST rewrites.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-embedded-strings",
            action="store_true",
            help=(
                "Skip the verified multiline literal presentation pass "
                "that rewrites supported strings and complete f-strings "
                "into physical multiline form without changing values."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--format-embedded",
            action="store_true",
            help=(
                "Format inferred HTML, JavaScript, CSS, or Python inside "
                "multiline literals with Prettier or Ruff. May change "
                "string contents; requires --allow-value-changes."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--allow-value-changes",
            action="store_true",
            help=(
                "Permit transforms that intentionally change string "
                "contents; required by --format-embedded."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--line-length",
            type=_positive,
            metavar="N",
            help=(
                "Explicit string-transform target width; defaults to the "
                "line length resolved from Ruff configuration."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--multiline-strategy",
            choices=("preserve", "split", "smart"),
            default="smart",
            metavar="MODE",
            help=(
                "Multiline literal strategy: preserve existing triple "
                "quotes, split literals into adjacent physical lines, or "
                "choose per literal (smart, default)."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-split-fstrings",
            action="store_true",
            help="Exclude f-strings from width-limited literal splitting.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-split-raw-strings",
            action="store_true",
            help="Exclude raw literals from width-limited splitting.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-split-bytes",
            action="store_true",
            help="Exclude byte literals from width-limited splitting.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-format-interpolations",
            action="store_true",
            help=(
                "Skip Ruff-backed expansion of eligible oversized calls "
                "inside f-string interpolations."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--call-format-minimum",
            type=_positive,
            default=3,
            metavar="N",
            help=(
                "Minimum argument count before an f-string call "
                "interpolation is expanded (default 3)."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--no-css-naming",
            action="store_true",
            help="Disable the component-aware CSS numeric naming audit.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-scale",
            action="append",
            default=[],
            metavar="STEM",
            help="Registered numeric CSS design scale (repeatable).",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-extended",
            action="store_true",
            help="Include weak-evidence advisory CSS naming findings.",
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-convention",
            action="append",
            default=[],
            metavar="SPEC",
            help=(
                "Scoped CSS naming registry as key=value pairs joined "
                "by ';' (stem=--spacing-;unit=px;step=4;members=1,2,4;"
                "scope=ui;rationale=...;review=...). Repeatable."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-exempt",
            action="append",
            default=[],
            metavar="SPEC",
            help=(
                "Scoped CSS naming exemption as key=value pairs joined "
                "by ';' (name=--legacy-;scope=ui;rationale=...). "
                "Repeatable."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-severity",
            action="append",
            default=[],
            metavar="RULE=LEVEL",
            help=(
                "Per-rule CSSN severity override (error, warning, "
                "info); e.g. --css-naming-severity CSSN008=warning. "
                "Repeatable."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-naming-component",
            action="append",
            default=[],
            metavar="PATH=NAME",
            help=(
                "Explicit component-root mapping applied before the "
                "directory heuristic; e.g. web/ui=ui. Repeatable."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--css-context-word",
            action="append",
            default=[],
            metavar="WORD",
            help=(
                "Application or component word that CSS CATALOG token "
                "names must not contain (CSS118). Repeat for multiple "
                "words; components/<name>/ directories are added "
                "automatically."
            ),
        ),
    )
    _ = consume(
        value=parser.add_argument(
            "--toolchain",
            type=Path,
            default=None,
            help="Explicit exactus toolchain executable path.",
        ),
    )
    for tool in ("ruff", "basedpyright", "pyrefly"):
        _ = consume(
            value=parser.add_argument(
                f"--{tool}-arg",
                action="append",
                default=[],
                metavar="ARG",
                help=f"Extra argument forwarded to {tool}; repeatable.",
            ),
        )
    return parser
