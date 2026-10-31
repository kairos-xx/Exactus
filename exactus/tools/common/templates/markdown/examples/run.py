#!/usr/bin/env python3
# Copyright (c) 2026
"""Validate bundled Markdown report input and expected-output fixtures."""

from json import loads
from pathlib import Path
from sys import path as import_path
from sys import stdout
from typing import TYPE_CHECKING, cast

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[6]))
if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


def main() -> int:
    """Parse every JSON fixture and verify each expected report exists.

    Returns:
        Zero when the complete fixture set is readable.

    """
    root: Path = Path(__file__).resolve().parent
    stems: tuple[str, ...] = ("result", "empty_result", "error_result")
    for stem in stems:
        value: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=(root / f"{stem}.json").read_text(encoding="utf-8")),
        )
        if not isinstance(value, dict):
            return 1
        expected: str = (
            "expected.md"
            if stem == "result"
            else f"expected_{stem.removesuffix('_result')}.md"
        )
        if not (root / expected).is_file():
            return 1
    _ = stdout.write(f"validated {len(stems)} Markdown report fixtures\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
