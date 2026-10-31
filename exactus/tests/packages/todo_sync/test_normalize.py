# Copyright (c) 2026 Project contributors
"""Uniform headers preserve obligations and expose source metadata."""

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

from exactus.packages.todo_sync import normalize, parse, render_html, update
from exactus.packages.todo_sync.cli import main
from exactus.packages.todo_sync.core import visible_lines
from exactus.packages.todo_sync.normalize import Patterns
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from re import Match


def test_canonical_queue_schema() -> None:
    """Keep the real handoff queue explicit and IDs unique as it evolves."""
    source: str = (
        Path(__file__).resolve().parents[4] / "docs" / "todo" / "TODO.md"
    ).read_text(encoding="utf-8")
    identifiers: list[str] = []
    for line in visible_lines(text=source):
        box: Match[str] | None = Patterns.BOX.match(string=line)
        if box is None:
            continue
        header: Match[str] | None = Patterns.NORMAL.match(string=box[3])
        expect_equal(actual=header is not None, expected=True)
        if header is not None:
            identifiers.append(header[1])
    expect_equal(actual=bool(identifiers), expected=True)
    expect_equal(actual=len(identifiers), expected=len(set(identifiers)))
    expect_equal(
        actual="## Bespoke execution map — Studio first" in source,
        expected=True,
    )


def test_headers_and_idempotence() -> None:
    """Keep IDs/states/details and allocate collision-free child IDs."""
    source: str = dedent(
        text=(
            "    # Plan\n    ## P1 — Work\n    - [x] **UI-O03** □ **P0** — Bui"
            "ld controls\n      Acceptance: retain the evidence.\n      - [ ] "
            "Nested action\n    - [ ] No urgency\n    ## P1/P2 — Ambiguous\n  "
            "  - [ ] Unscheduled\n    ```md\n    - [ ] Example\n    ```\n    <"
            "!--\n    - [x] Hidden\n    -->\n    "
        ),
    )
    output: str = normalize(text=source)
    expect_equal(actual=normalize(text=output), expected=output)
    for expected in (
        "- [x] **UI-O03** **P0** **Frontend** — Build controls",
        "  Acceptance: retain the evidence.",
        "  - [ ] **UI-O03-01** **P0** **Frontend** — Nested action",
        "- [ ] **TODO-001** **P1** **Uncategorized** — No urgency",
        "- [ ] **TODO-002** **Untriaged** **Uncategorized** — Unscheduled",
        "```md\n- [ ] Example\n```",
        "<!--\n- [x] Hidden\n-->",
    ):
        expect_equal(actual=expected in output, expected=True)


def test_explicit_metadata_wins() -> None:
    """Description mentions cannot override normalized priority/category."""
    source: str = dedent(
        text=(
            "    - [ ] **W001** **Untriaged** **Uncategorized** — Consider P0 "
            "or P1; □ is an example glyph.\n    "
        ),
    )
    sections, priorities = parse(text=source)
    expect_equal(actual=sections[0].tasks[0].priority, expected="Untriaged")
    expect_equal(
        actual=sections[0].tasks[0].category,
        expected="uncategorized",
    )
    expect_equal(actual=priorities, expected={"Untriaged": (0, 1)})
    html: str = render_html(text=source)
    expect_equal(actual='"priority": "Untriaged"' in html, expected=True)
    expect_equal(actual='"text": "Consider P0 or P1;' in html, expected=True)
    expect_equal(actual=normalize(text=source), expected=source)
    expect_equal(
        actual="| Untriaged | Done |" in update(text=source),
        expected=True,
    )


def test_crlf_and_unknown_priority() -> None:
    """Preserve line endings and do not invent urgency."""
    source: str = "# Plan\r\n- [ ] **R01 — Package wheel**\r\n  Detail\r\n"
    output: str = normalize(text=source)
    expect_equal(
        actual=output,
        expected=(
            dedent(
                text=(
                    "    # Plan\r\n    - [ ] **R01** **Untriaged** **DevOp"
                    "s / Release** — **Package wheel**\r\n      Detail\r\n"
                    "    "
                ),
            )
        ),
    )


def test_normalization_check_is_read_only(tmp_path: Path) -> None:
    """Check audits legacy headers without replacing the source.

    Args:
        tmp_path: Isolated source directory for one-shot normalization.

    """
    source: Path = tmp_path / "TODO.md"
    original: str = "# Plan\n- [ ] Unscheduled\n"
    source.write_text(data=original, encoding="utf-8")
    expect_equal(
        actual=main(
            argv=["--path", str(object=source), "--normalize", "--check"],
        ),
        expected=1,
    )
    expect_equal(actual=source.read_text(encoding="utf-8"), expected=original)
    expect_equal(
        actual=source.with_suffix(suffix=".html").exists(),
        expected=False,
    )
    expect_equal(
        actual=main(argv=["--path", str(object=source), "--normalize"]),
        expected=0,
    )
    expect_equal(
        actual=main(
            argv=["--path", str(object=source), "--normalize", "--check"],
        ),
        expected=0,
    )


@pytest.mark.parametrize(
    "mode",
    ["--watch", "--watch-child", "--watch-stop", "--watch-status"],
)
def test_normalization_cannot_be_silently_ignored(mode: str) -> None:
    """Watcher control must reject a one-shot normalization flag.

    Args:
        mode: Watcher lifecycle flag incompatible with normalization.

    """
    with pytest.raises(expected_exception=SystemExit) as failure:
        main(argv=["--normalize", mode])
    expect_equal(actual=failure.value.code, expected=2)
