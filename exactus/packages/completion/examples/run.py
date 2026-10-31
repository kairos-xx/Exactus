#!/usr/bin/env python3
# Copyright (c) 2026
"""Complete a standalone command without importing any exactus tools."""

from pathlib import Path
from sys import path as import_path
from sys import stdout
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.completion.catalog import (
    CompletionCatalog,
    ProviderId,
    spec_from_parser,
)
from exactus.packages.completion.protocol import run_completion
from exactus.packages.completion.providers import default_providers

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from exactus.packages.completion.catalog import CommandSpec


def main() -> int:
    """Show flag and pipeline candidates from an application-owned grammar.

    Returns:
        Zero when both completion queries succeed.

    """
    parser: ArgumentParser = ExactusArgumentParser(prog="example")
    _ = parser.add_argument(
        "--lints",
        action="store_true",
        help="Check source style",
    )
    _ = parser.add_argument("--pipeline", help="Choose a pipeline")
    command: CommandSpec = spec_from_parser(
        name="example",
        description="Example command",
        parser=parser,
        providers={"pipeline": ProviderId.PIPELINE},
    )
    catalog: CompletionCatalog = CompletionCatalog(root=command, contexts=())
    for title, words, prefix in (
        ("Tool flags", ("example", "--li"), "--li"),
        ("Pipeline names", ("example", "--pipeline", "un"), "un"),
    ):
        _ = stdout.write(title + ":\n")
        status: int = run_completion(
            arguments=(
                "--shell=bash",
                f"--active-word-index={len(words) - 1}",
                f"--prefix={prefix}",
                *(f"--word={word}" for word in words),
            ),
            catalog=catalog,
            command_name="example",
            providers=default_providers(
                pipelines=(("unified", "Run every stage"),),
            ),
        )
        if status:
            return status
    return 0
