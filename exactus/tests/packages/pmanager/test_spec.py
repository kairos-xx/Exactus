# Copyright (c) 2026 João Lopes
"""Specification smoke tests."""

from pathlib import Path
from typing import Final, final

from exactus.packages.pmanager.runtime import JsonValue, Spec
from exactus.tests.common.support import fail


@final
class Constants:
    """Group module-level constants.

    Attributes:
        expected_children: Grouped module constant.
        root: Grouped module constant.

    """

    expected_children: Final = 2
    root: Final = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "pmanager"
    )


def _processes() -> dict[str, dict[str, JsonValue]]:
    """Load normalized process definitions.

    Returns:
        Normalized process definitions.

    """
    return Spec(path=Constants.root / "processes.json").processes


def test_spec_has_all_examples() -> None:
    """Verify all demonstration processes are defined."""
    if set(_processes()) != {"A", "B", "C", "D", "E"}:
        fail(message="Expected A through E process definitions.")


def test_e_is_parallel_join() -> None:
    """Verify E is configured as a parallel fan-out/join process."""
    config: dict[str, JsonValue] = _processes()["E"]
    if config.get("launch") != "parallel":
        fail(message="E must launch children in parallel.")
    children: JsonValue = config.get("children")
    if (
        not isinstance(children, list)
        or len(children) != Constants.expected_children
    ):
        fail(message="E must define two children.")


def test_c_is_global_singleton_runner() -> None:
    """Verify C uses global single-runner concurrency."""
    config: dict[str, JsonValue] = _processes()["C"]
    concurrency: JsonValue = config.get("concurrency")
    if not isinstance(concurrency, dict):
        fail(message="C must define concurrency.")
    if concurrency.get("scope") != "global":
        fail(message="C concurrency must be global.")
    if concurrency.get("max_running") != 1:
        fail(message="C must allow one running instance.")
