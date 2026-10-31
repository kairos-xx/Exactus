# Copyright (c) 2026 Project contributors
"""Inventory the version-3 action surface that structured flows must keep."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from re import MULTILINE, findall
from sys import stdout
from typing import Final, final

from exactus.tools.record.model import EventKind


@final
class Constants:
    """Group module-level constants.

    Attributes:
        catalog_pattern: Grouped module constant.
        command_pattern: Grouped module constant.
        runner_pattern: Grouped module constant.
        catalog_aliases: Grouped module constant.
        catalog_multi: Grouped module constant.
        guard_ids: Grouped module constant.

    """

    catalog_pattern: Final[str] = '\\bid: "([a-z_]+)"'
    command_pattern: Final[str] = (
        '^\\s+"([a-z_]+\\.[a-z_.]+)": self\\._command'
    )
    runner_pattern: Final[str] = "event\\.kind is EventKind\\.([A-Z_]+)"
    catalog_aliases: Final[tuple[tuple[str, str], ...]] = (
        ("touch_tap", "gesture"),
        ("touch_long_press", "gesture"),
        ("touch_swipe", "gesture"),
        ("touch_pinch", "gesture"),
        ("viewport_rotate", "viewport"),
        ("viewport_resize", "viewport"),
        ("extract_text", "extract_value"),
        ("extract_checked", "extract_value"),
        ("extract_number", "extract_value"),
        ("count_matches", "extract_value"),
        ("extract_attribute", "extract_value"),
        ("wait_element", "wait"),
        ("wait_text", "wait"),
        ("wait_url", "wait"),
        ("wait_expression", "wait"),
        ("screenshot", "note"),
    )
    catalog_multi: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
        (
            "pointer",
            (
                "click",
                "double_click",
                "right_click",
                "hover",
                "drag",
                "scroll",
                "position_pointer",
                "gesture",
            ),
        ),
    )
    guard_ids: Final[tuple[str, ...]] = ("if",)


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionInventory:
    """Hold the four views of the action surface that must agree.

    Attributes:
        event_kinds: Persisted event-kind values supported by the model.
        catalog_ids: Action identifiers exposed by the Studio catalog.
        controller_commands: Commands accepted by the Studio controller.
        runner_special_kinds: Event kinds with dedicated runner branches.

    """

    event_kinds: tuple[str, ...]
    catalog_ids: tuple[str, ...]
    controller_commands: tuple[str, ...]
    runner_special_kinds: tuple[str, ...]


def catalog_ids(*, source: str) -> tuple[str, ...]:
    """List the action ids declared in the JavaScript catalog.

    Args:
        source: Text of ``action-library.js``.

    Returns:
        Ids in declaration order, without duplicates.

    """
    found: list[str] = findall(
        pattern=Constants.catalog_pattern,
        string=source,
    )
    return tuple(dict.fromkeys(found))


def controller_commands(*, source: str) -> tuple[str, ...]:
    """List the commands the Studio controller dispatches.

    Args:
        source: Text of ``studio/controller.py``.

    Returns:
        Command names in declaration order, without duplicates.

    """
    found: list[str] = findall(
        pattern=Constants.command_pattern,
        string=source,
        flags=MULTILINE,
    )
    return tuple(dict.fromkeys(found))


def runner_special_kinds(*, source: str) -> tuple[str, ...]:
    """List the event kinds the runner executes through a special path.

    Args:
        source: Text of ``flow_runner.py``.

    Returns:
        Lower-case kind values in declaration order, without duplicates.

    """
    found: list[str] = findall(pattern=Constants.runner_pattern, string=source)
    return tuple(dict.fromkeys(item.lower() for item in found))


def kinds_for_catalog_id(*, catalog_id: str) -> tuple[str, ...]:
    """Resolve every event kind a catalog id can execute as.

    Args:
        catalog_id: Action id from the JavaScript catalog.

    Returns:
        The event kinds: empty for a guard such as ``if``, every kind a
        composite action can emit, or the single resolved kind.

    """
    if catalog_id in Constants.guard_ids:
        return ()
    multi: dict[str, tuple[str, ...]] = dict(Constants.catalog_multi)
    if catalog_id in multi:
        return multi[catalog_id]
    aliases: dict[str, str] = dict(Constants.catalog_aliases)
    return (aliases.get(catalog_id, catalog_id),)


def kind_for_catalog_id(*, catalog_id: str) -> str | None:
    """Resolve the single event kind a catalog id executes as.

    Args:
        catalog_id: Action id from the JavaScript catalog.

    Returns:
        The event kind value, or None for a guard such as ``if`` and for
        composite actions such as ``pointer`` that emit several kinds.

    """
    kinds: tuple[str, ...] = kinds_for_catalog_id(catalog_id=catalog_id)
    return kinds[0] if len(kinds) == 1 else None


def build_inventory(*, record: Path) -> ActionInventory:
    """Measure the action surface from the working tree.

    Args:
        record: The ``exactus/tools/record`` folder.

    Returns:
        The inventory of kinds, catalog ids, commands and runner paths.

    """
    web: Path = record / "studio" / "web" / "action-library.js"
    controller: Path = record / "studio" / "controller.py"
    runner: Path = record / "flow_runner.py"
    return ActionInventory(
        event_kinds=tuple(kind.value for kind in EventKind),
        catalog_ids=catalog_ids(source=web.read_text(encoding="utf-8")),
        controller_commands=controller_commands(
            source=controller.read_text(encoding="utf-8"),
        ),
        runner_special_kinds=runner_special_kinds(
            source=runner.read_text(encoding="utf-8"),
        ),
    )


def render_matrix(*, inventory: ActionInventory) -> str:
    """Render the parity matrix as Markdown.

    Args:
        inventory: Measured action surface.

    Returns:
        Markdown with one row per event kind and one list of commands.

    """
    lines: list[str] = [
        "# Flow Studio v3 action inventory",
        "",
        "Generated by `python -m exactus.tools.record.flow_inventory`.",
        "",
        "| Event kind | Catalog ids | Runner path |",
        "| --- | --- | --- |",
    ]
    for kind in inventory.event_kinds:
        ids: str = ", ".join(
            item
            for item in inventory.catalog_ids
            if kind in kinds_for_catalog_id(catalog_id=item)
        )
        path: str = (
            "special" if kind in inventory.runner_special_kinds else "generic"
        )
        lines.append(f"| `{kind}` | {ids or '—'} | {path} |")
    lines.extend(["", "## Controller commands", ""])
    lines.extend(f"- `{command}`" for command in inventory.controller_commands)
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write the parity matrix for the working tree to standard output."""
    record: Path = Path(__file__).resolve().parent
    stdout.write(render_matrix(inventory=build_inventory(record=record)))


if __name__ == "__main__":
    main()
