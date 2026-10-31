# Copyright (c) 2026
"""Command-line entry point for visual_cause."""

from sys import modules

from exactus.packages.visual_cause import analyzer, dom_diff


def main() -> None:
    """Dispatch between causal-CSS and generic DOM comparison modes."""
    arguments: list[str] = modules["sys"].argv
    if arguments[1:2] == ["dom-diff"]:
        dom_diff.main(arguments=arguments[2:])
        return
    analyzer.main()
