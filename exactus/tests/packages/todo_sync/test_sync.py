# Copyright (c) 2026 Project contributors
"""Validate parsing, atomic output, CLI and safe watcher lifecycle."""

from json import loads
from pathlib import Path
from re import DOTALL, Match, search
from textwrap import dedent
from time import monotonic, sleep
from typing import cast

import pytest

from exactus.packages.todo_sync import (
    completion,
    parse,
    render_html,
    sync,
    synchronize,
    update,
)
from exactus.packages.todo_sync.cli import main
from exactus.packages.todo_sync.watch import (
    lock_path,
    read_state,
    running,
    start,
    stop,
)
from exactus.tests.common.support import expect_equal


def test_excluded_examples_and_parent_rollup() -> None:
    """Fences/comments never count and parent totals include descendants."""
    source: str = dedent(
        text=(
            "    # Plan\n    ## Work\n    - [x] **R01 — Done** P0\n    ### Chi"
            "ld\n    - [ ] **UI-O03** □ **P1** ONGOING\n    ```md\n    - [x] f"
            "ake\n    ```\n    <!--\n    ```\n    - [x] hidden\n    -->\n    -"
            " [ ] real\n    "
        ),
    )
    sections, priorities = parse(text=source)
    expect_equal(actual=sum(item.total for item in sections), expected=3)
    expect_equal(actual=priorities, expected={"P0": (1, 0), "P1": (0, 1)})
    expect_equal(actual=completion(text=source), expected=100 / 3)
    result: str = update(text=source)
    expect_equal(actual="R01 Uncategorized" in result, expected=True)
    expect_equal(actual="UI-O03 Frontend" in result, expected=True)
    expect_equal(actual=update(text=result), expected=result)


@pytest.mark.parametrize("ident", ["R01", "H21", "PQ06", "UI-O03", "DIS-001"])
def test_identifiers(ident: str) -> None:
    """Support Exactus and supplied roadmap ID conventions.

    Args:
        ident: Supported task identifier to preserve during parsing.

    """
    sections, _priorities = parse(text=f"- [ ] **{ident} — Task**\n")
    expect_equal(actual=sections[0].tasks[0].ident, expected=ident)


@pytest.mark.parametrize(
    "source",
    [
        "<!-- ROADMAP_PROGRESS_DASHBOARD_START -->",
        "<!-- ROADMAP_PROGRESS_DASHBOARD_END -->",
        (
            dedent(
                text=(
                    "    <!-- ROADMAP_PROGRESS_DASHBOARD_END -->\n    <!--"
                    " ROADMAP_PROGRESS_DASHBOARD_START -->"
                ),
            )
        ),
        "<!-- ROADMAP_PROGRESS_DASHBOARD_START -->" * 2
        + "<!-- ROADMAP_PROGRESS_DASHBOARD_END -->",
    ],
)
def test_malformed_markers(source: str) -> None:
    """Reject duplicated, missing or reversed markers.

    Args:
        source: Invalid managed-dashboard marker sequence.

    """
    with pytest.raises(
        expected_exception=ValueError,
        match=r"marker|reversed",
    ):
        update(text=source)


def test_preserve_outside_managed_block() -> None:
    """Replacement preserves all whitespace outside the managed markers."""
    source: str = "# Plan\n\n- [ ] Keep  spaces  \n\n"
    generated: str = update(text=source)
    result: str = update(text=generated.replace("- [ ] Keep", "- [x] Keep"))
    expect_equal(
        actual=result.endswith("- [x] Keep  spaces  \n\n"),
        expected=True,
    )
    expect_equal(actual=update(text=result), expected=result)
    expect_equal(actual=update(text="# Empty\n"), expected="# Empty\n")


def test_top_summary_updates_without_moving_detailed_tables() -> None:
    """Keep HTML totals at the top and detailed tables after task content."""
    source: str = dedent(
        text=(
            "    # Plan\n    \n    <!-- ROADMAP_PROGRESS_SUMMARY_START -->\n  "
            "  <!-- ROADMAP_PROGRESS_SUMMARY_END -->\n    \n    ## Work\n    -"
            " [ ] Task\n    \n    <!-- ROADMAP_PROGRESS_DASHBOARD_START -->\n "
            "   <!-- ROADMAP_PROGRESS_DASHBOARD_END -->\n    "
        ),
    )
    result: str = update(text=source)
    expect_equal(
        actual=result.index('role="progressbar"') < result.index("## Work"),
        expected=True,
    )
    expect_equal(
        actual=result.index("### Priority progress") > result.index("## Work"),
        expected=True,
    )
    expect_equal(actual=result.count('role="progressbar"'), expected=1)
    result = update(text=result.replace("- [ ] Task", "- [x] Task"))
    expect_equal(actual="1/1 (100.0%)" in result, expected=True)
    expect_equal(actual=update(text=result), expected=result)


def test_duplicate_heading_anchor() -> None:
    """An empty earlier heading still consumes its slug suffix."""
    rendered: str = update(text="# Plan\n## Same\n## Same\n- [ ] task\n")
    expect_equal(actual="[Same](#same-1)" in rendered, expected=True)


def test_html_escaping() -> None:
    """Literal script tags cannot terminate the JSON data element."""
    html: str = render_html(
        text="# Plan\n- [ ] </script><script>evil()</script>\n",
    )
    match: Match[str] | None = search(
        pattern=r'<script id="task-data"[^>]*>\s*(.*?)\s*</script>',
        string=html,
        flags=DOTALL,
    )
    if match is None:
        pytest.fail(reason="Missing embedded JSON payload")
    data: dict[str, object] = cast(
        typ="dict[str, object]",
        val=loads(s=match[1]),
    )
    tasks: list[dict[str, object]] = cast(
        typ="list[dict[str, object]]",
        val=data["tasks"],
    )
    expect_equal(actual=tasks[0]["line"], expected=2)
    expect_equal(actual=tasks[0]["category"], expected="Uncategorized")
    expect_equal(actual="evil()" in str(object=data["md"]), expected=True)
    expect_equal(actual="__TASK_DATA__" not in html, expected=True)
    expect_equal(actual="innerHTML" not in html, expected=True)
    expect_equal(actual="DOMParser" not in html, expected=True)


def test_check_and_html_repair(tmp_path: Path) -> None:
    """Check never writes; no-op preserves mtimes; missing HTML repairs.

    Args:
        tmp_path: Isolated directory for the source and generated HTML.

    """
    path: Path = tmp_path / "Roadmap.md"
    path.write_text(data="# Plan\n- [ ] Task\n", encoding="utf-8")
    before: bytes = path.read_bytes()
    expect_equal(actual=synchronize(path=path, check=True), expected=True)
    expect_equal(actual=path.read_bytes(), expected=before)
    expect_equal(
        actual=not path.with_suffix(suffix=".html").exists(),
        expected=True,
    )
    expect_equal(actual=synchronize(path=path), expected=True)
    stat: int = path.stat().st_mtime_ns
    expect_equal(actual=not synchronize(path=path), expected=True)
    expect_equal(actual=path.stat().st_mtime_ns, expected=stat)
    path.with_suffix(suffix=".html").unlink()
    expect_equal(actual=synchronize(path=path, check=True), expected=True)
    expect_equal(actual=synchronize(path=path), expected=True)
    expect_equal(actual=not synchronize(path=path, check=True), expected=True)


def test_concurrent_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An edit during rendering is retained instead of overwritten.

    Args:
        tmp_path: Isolated document directory.
        monkeypatch: Fixture replacing the renderer with a concurrent edit.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="- [ ] before\n", encoding="utf-8")

    def render(*, text: str) -> str:
        """Simulate an editor changing the source during rendering.

        Args:
            text: Document passed to the replacement renderer.

        Returns:
            Original document, after the simulated edit is saved separately.

        """
        path.write_text(data="- [x] user edit\n", encoding="utf-8")
        return text

    monkeypatch.setattr(target=sync, name="render_html", value=render)
    with pytest.raises(expected_exception=ValueError, match="changed during"):
        synchronize(path=path)
    expect_equal(actual=path.read_text(), expected="- [x] user edit\n")


def test_symlink_preflight(tmp_path: Path) -> None:
    """Reject output symlinks before changing Markdown or linked target.

    Args:
        tmp_path: Isolated source, output link and linked-target directory.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="- [ ] task\n", encoding="utf-8")
    target: Path = tmp_path / "other.html"
    target.write_text(data="keep", encoding="utf-8")
    path.with_suffix(suffix=".html").symlink_to(target=target)
    with pytest.raises(
        expected_exception=ValueError,
        match="symbolic-link HTML",
    ):
        synchronize(path=path)
    expect_equal(actual=path.read_text(), expected="- [ ] task\n")
    expect_equal(actual=target.read_text(), expected="keep")


def test_cli(tmp_path: Path) -> None:
    """Check exit codes and mutually exclusive operations.

    Args:
        tmp_path: Isolated command-line input directory.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="- [ ] task\n", encoding="utf-8")
    args: list[str] = ["--path", str(object=path), "--no-html"]
    expect_equal(actual=main(argv=[*args, "--check"]), expected=1)
    expect_equal(actual=main(argv=args), expected=0)
    expect_equal(actual=main(argv=[*args, "--check"]), expected=0)
    with pytest.raises(expected_exception=SystemExit) as exc:
        main(argv=[*args, "--check", "--watch"])
    expect_equal(actual=exc.value.code, expected=2)


@pytest.mark.parametrize("interval", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_intervals(tmp_path: Path, interval: float) -> None:
    """Invalid intervals cannot create a background process.

    Args:
        tmp_path: Isolated input path that must never acquire a watcher.
        interval: Nonpositive or nonfinite polling interval to reject.

    """
    with pytest.raises(expected_exception=ValueError, match="finite"):
        start(path=tmp_path / "TODO.md", interval=interval)


def test_stale_state(tmp_path: Path) -> None:
    """Stale ownership requires inspection, never PID killing.

    Args:
        tmp_path: Isolated directory containing an intentionally stale lock.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="- [ ] task\n", encoding="utf-8")
    lock: Path = lock_path(path=path)
    lock.mkdir()
    (lock / "state.json").write_text(
        data='{"pid":1,"heartbeat":0}',
        encoding="utf-8",
    )
    expect_equal(actual=not running(path=path), expected=True)
    with pytest.raises(expected_exception=ValueError, match="stale"):
        stop(path=path)
    with pytest.raises(expected_exception=ValueError, match="manual recovery"):
        start(path=path)
    expect_equal(actual=lock.exists(), expected=True)


def test_real_watcher(tmp_path: Path) -> None:
    """A detached child syncs edits and exits cooperatively.

    Args:
        tmp_path: Isolated directory owned by this test and its watcher.

    """
    path: Path = tmp_path / "TODO.md"
    path.write_text(data="# Plan\n- [ ] task\n", encoding="utf-8")
    expect_equal(actual=start(path=path, interval=0.05), expected=0)
    try:
        expect_equal(actual=running(path=path), expected=True)
        expect_equal(actual=start(path=path), expected=0)
        source: str = path.read_text(encoding="utf-8")
        path.write_text(
            data=source.replace("- [ ] task", "- [x] task"),
            encoding="utf-8",
        )
        deadline: float = monotonic() + 5
        while (
            read_state(path=path).get("percent") != float(100)
            and monotonic() < deadline
        ):
            sleep(0.05)
        expect_equal(
            actual=read_state(path=path).get("percent"),
            expected=100.0,
        )
        expect_equal(
            actual=read_state(path=path).get("percent_delta"),
            expected=100.0,
        )
        # Completion metadata and the rendered companion are separate files.
        # Require both outputs to converge before asserting synchronization.
        deadline = monotonic() + 10
        while synchronize(path=path, check=True) and monotonic() < deadline:
            sleep(0.05)
        expect_equal(actual=synchronize(path=path, check=True), expected=False)
    finally:
        stop(path=path)
    expect_equal(actual=not lock_path(path=path).exists(), expected=True)
