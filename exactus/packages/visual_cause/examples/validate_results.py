# Copyright (c) 2026
"""Validate that the demo produced navigable human evidence."""

from pathlib import Path
from re import findall
from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        evidence_triplet_size: Grouped module constant.

    """

    evidence_triplet_size: Final[int] = 3


def main() -> None:
    """Require a non-empty Markdown causal report and resolvable evidence.

    Raises:
        RuntimeError: If the report or referenced evidence is incomplete.

    """
    root: Path = Path(__file__).resolve().parent / "results"
    report: Path = root / "report.md"
    if not report.is_file():
        msg: str = "examples/results/report.md was not generated"
        raise RuntimeError(msg)
    markdown: str = report.read_text(encoding="utf-8")
    required: tuple[str, ...] = (
        "## `",
        "### Rule ",
        "#### `",
        "##### Affected element `",
        "**Other contributing properties:**",
        "```css",
    )
    missing: list[str] = [token for token in required if token not in markdown]
    if missing:
        msg = f"report.md is missing required sections: {missing}"
        raise RuntimeError(msg)
    if (
        "Changed rules represented | 0" in markdown
        or "Identified changed properties | 0" in markdown
    ):
        msg = "report.md contains no CSS rule/property evidence"
        raise RuntimeError(msg)
    references: list[str] = findall(
        pattern="!\\[\\]\\((evidence/[^)]+\\.png)\\)",
        string=markdown,
    )
    if (
        len(references) < Constants.evidence_triplet_size
        or len(references) % Constants.evidence_triplet_size != 0
    ):
        msg = "report.md does not contain complete A/B/diff evidence triplets"
        raise RuntimeError(msg)
    absent: list[str] = [
        reference
        for reference in references
        if not (root / reference).is_file()
    ]
    if absent:
        msg = f"report.md references missing evidence: {absent}"
        raise RuntimeError(msg)
    empty: list[str] = [
        reference
        for reference in references
        if (root / reference).stat().st_size == 0
    ]
    if empty:
        msg = f"report.md references empty evidence: {empty}"
        raise RuntimeError(msg)


if __name__ == "__main__":
    main()
