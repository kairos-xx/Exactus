# Copyright (c) 2026
"""Run-scoped environment boundary for nested Exactus executions.

An active run exports its coordination context — registry path, report
output, run identifiers, comparison baseline — so cooperating workers
share one run. Those exports must never cross into an independent
nested invocation: a child that inherits them resolves the parent's
registry, report directories, and root, then claims, resets, or clears
live output it does not own. Every boundary that launches an
independent Exactus context (nested pipelines, coverage-spawned test
processes, standalone invocations, pytest workers) strips this exact
set plus the prefixed families. Installation and toolchain selections
such as ``EXACTUS_PROJECT_PYTHON`` or ``EXACTUS_LINTER_TOOLCHAIN`` are
deliberately preserved so nested runs reuse the same interpreters.
"""

from __future__ import annotations

from os import environ
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import ItemsView, Mapping


@final
class Constants:
    """Group module-level constants.

    Attributes:
        variables: Grouped module constant.
        prefixes: Grouped module constant.

    """

    variables: Final[frozenset[str]] = frozenset(
        {
            "EXACTUS_COLLECT_FILES",
            "EXACTUS_COMPARISON_BASELINE",
            "EXACTUS_CONFIG",
            "EXACTUS_EXPLICIT_ARGUMENTS",
            "EXACTUS_HOST",
            "EXACTUS_ORCHESTRATED",
            "EXACTUS_PIPELINE_RUN_ID",
            "EXACTUS_PMANAGER_WORKER",
            "EXACTUS_PORT",
            "EXACTUS_PROJECT_ROOT",
            "EXACTUS_RECORD_ROOT",
            "EXACTUS_REGISTRY",
            "EXACTUS_REPORTS_ROOT",
            "EXACTUS_REPORT_OUTPUT",
            "EXACTUS_RESULTS",
            "EXACTUS_RESULTS_RELEASE",
            "EXACTUS_ROOT",
            "EXACTUS_RUN_ID",
            "EXACTUS_TOOL",
        },
    )
    prefixes: Final[tuple[str, ...]] = (
        "EXACTUS_ACTION__",
        "EXACTUS_ES__",
        "EXACTUS_RECORDER_FLUSH__",
        "EXACTUS_TOOLS_PAYLOAD__",
    )


def run_scoped(*, name: str) -> bool:
    """Report whether one environment variable belongs to a live run.

    Args:
        name: Environment variable name to classify.

    Returns:
        ``True`` when the variable carries run-scoped state.

    """
    return name in Constants.variables or name.startswith(Constants.prefixes)


def sanitized_environ(
    *,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a copy of ``source`` without any run-scoped variable.

    Args:
        source: Environment mapping to filter; ``os.environ`` when
            omitted.

    Returns:
        Filtered environment safe for an independent nested run.

    """
    items: ItemsView[str, str] = (
        environ.items() if source is None else source.items()
    )
    return {key: value for key, value in items if not run_scoped(name=key)}
