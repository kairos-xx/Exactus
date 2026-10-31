# Copyright (c) 2026
"""RECORD renders result.md from its normalized result.json and template."""

from __future__ import annotations

from functools import partial
from json import loads
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final, NoReturn

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_in,
    expect_true,
    fail,
    stamped_markdown,
)
from exactus.tools.common import execution as ent
from exactus.tools.common.models import ToolRequest, ToolRunResult
from exactus.tools.record.core import RecordResult, passed, report_data
from exactus.tools.reports.bundle import Constants as BundleConstants
from exactus.tools.reports.bundle import ReportBundle, ReportPaths
from exactus.tools.reports.render import Constants, ReportTemplates

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue
GOLDEN: Final[Path] = Path(__file__).resolve().parent / "golden_tool"
TOOL_DIR: Final[Path] = ReportTemplates.tool_dir(analyzer="record")
SECTIONS: Final[tuple[str, ...]] = (
    "## Identity",
    "## What was checked",
    "### Scope",
    "## Setup",
    "### Invocation",
    "### Environment",
    "## Gate",
    "## Findings",
    "## Artifacts",
    "## Session",
    "## Rules",
    "\n---\n\nExactus · record",
)
LEGACY_KEYS: Final[tuple[str, ...]] = (
    "analyzer",
    "status",
    "passed",
    "resume",
    "duration_seconds",
    "sections",
    "web",
    "run_id",
    "title",
)


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(
        target=ent,
        name="argv",
        value=["record", "--url", "http://x"],
    )
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _result() -> RecordResult:
    """One replay outcome with an error and a warning.

    Returns:
        Session outcome with two normalized findings.

    """
    return RecordResult(
        mode="replay",
        url="http://127.0.0.1:8000",
        actions=({"type": "click"}, {"type": "click"}, {"type": "key"}),
        exported_events=3,
        artifacts=("replay.py",),
        workspace="recording.pwflow.json",
        failures=("1 click: boom",),
        elapsed_seconds=1.234,
    )


def test_golden_result_renders_expected_markdown() -> None:
    """The checked-in result.json renders the checked-in result.md."""
    model: JsonValue = loads(
        s=(GOLDEN / "result.json").read_text(encoding="utf-8"),
    )
    expect_equal(
        actual=ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown,
        expected=(GOLDEN / "expected.md").read_text(encoding="utf-8"),
    )


def test_empty_session_state_why_nothing_is_listed() -> None:
    """A session without actions or files says N/A and why."""
    model: JsonValue = loads(
        s=(GOLDEN / "result.json").read_text(encoding="utf-8"),
    )
    if not isinstance(model, dict):
        fail(message="golden result is not an object")
    extension: JsonValue = model["extension"]
    if not isinstance(extension, dict):
        fail(message="golden result has no extension block")
    metrics: JsonValue = {
        "mode": "record",
        "url": "",
        "actions": 0,
        "exported_events": 0,
        "failures": 0,
        "elapsed_seconds": 0.0,
        "workspace": "",
        "by_type": [],
        "produced_files": [],
        "studio": [],
    }
    extension["metrics"] = metrics
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "| Mode | record |",
        "### Actions by type\n\nN/A — no replayable actions were recorded.",
        dedent(
            text=(
                "    ### Exactus Record session\n    \n    N/A — no Exactu"
                "s Record session facts were reported."
            ),
        ),
        "### Produced files\n\nN/A — the session produced no files.",
    ):
        expect_in(member=member, container=text)


def test_crash_render_shows_error_and_na_blocks() -> None:
    """An envelope-only result renders ERROR with N/A tool blocks."""
    model: JsonValue = loads(
        s=(Constants.common / "examples" / "error_result.json").read_text(
            encoding="utf-8",
        ),
    )
    text: str = ReportTemplates.render(model=model, tool_dir=TOOL_DIR).markdown
    for member in (
        "| Status | ERROR |",
        "> **Gate: ERROR** — RuntimeError: boom",
        "N/A — the tool reported no summary.",
        "N/A — the tool reported no scope.",
        "N/A — the tool reported no findings list.",
        "## Session\n\nN/A — the tool reported no session facts.",
        "## Rules\n\nN/A — the tool reported no rule counts.",
    ):
        expect_in(member=member, container=text)


def _write_report(*, out: Path) -> int:
    """Write the normalized payload the record tool produces.

    Args:
        out: Report directory.

    Returns:
        Tool exit status.

    """
    result: RecordResult = _result()
    _ = ReportBundle.write(
        paths=ReportPaths(
            markdown=out / "result.md",
            json=out / "result.json",
            web=out / "result_web",
        ),
        analyzer="record",
        title="Record Exactus",
        markdown="",
        data={
            **report_data(result=result),
            "project_root": str(object=out.parent.parent),
        },
    )
    return int(not passed(result=result))


def _payload(*, out: Path) -> dict[str, JsonValue]:
    """Read a report directory's ``result.json``.

    Args:
        out: Report directory.

    Returns:
        The decoded payload.

    """
    loaded: JsonValue = loads(
        s=(out / "result.json").read_text(encoding="utf-8"),
    )
    if not isinstance(loaded, dict):
        fail(message=f"{out / 'result.json'} is not a JSON object")
    return loaded


def test_execute_exactus_renders_record_from_template(tmp_path: Path) -> None:
    """A real RECORD run writes the normalized report bundle.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "RECORD"
    result: ToolRunResult = ent.execute_exactus(
        analyzer="record",
        title="Record Exactus",
        main=partial(_write_report, out=out),
        output=out,
    )
    expect_equal(actual=result.status, expected="FAIL")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    positions: list[int] = [markdown.index(part) for part in SECTIONS]
    expect_equal(actual=positions, expected=sorted(positions))
    expect_true(condition=markdown.startswith("# Record Exactus\n"))
    expect_in(
        member="> **Gate: FAIL** — 1 blocking finding",
        container=markdown,
    )
    payload: dict[str, JsonValue] = _payload(out=out)
    for key in (*BundleConstants.normalized_blocks, *LEGACY_KEYS):
        expect_in(member=key, container=payload)
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_equal(
        actual=dig(document=payload, path=("run", "status")),
        expected="FAIL",
    )
    expect_equal(
        actual=dig(document=payload, path=("tool", "name")),
        expected="record",
    )
    expect_equal(
        actual=dig(document=payload, path=("summary", "mode")),
        expected="replay",
    )
    expect_in(
        member={"level": 2, "title": "What was checked"},
        container=dig_list(document=payload, path=("sections",)),
    )
    expect_equal(
        actual=stamped_markdown(model=payload, tool_dir=TOOL_DIR, base=out),
        expected=markdown,
    )
    web: JsonValue = loads(
        s=(out / "result_web" / "data.json").read_text(encoding="utf-8"),
    )
    if not isinstance(web, dict):
        fail(message="result_web/data.json is not a JSON object")
    expect_equal(actual=web["markdown"], expected=markdown)
    expect_equal(
        actual=dig(document=web, path=("view", "gate", "status")),
        expected="FAIL",
    )
    for member in (
        "## Session",
        "| Mode | replay |",
        "| Exactus Record events exported | 3 |",
        "| click | 2 |",
        "- `replay.py`",
        "| REC001 | Replay action failed | 1 |",
    ):
        expect_in(member=member, container=markdown)
    expect_equal(
        actual=dig(document=web, path=("view", "action_types")),
        expected=[{"type": "click", "count": 2}, {"type": "key", "count": 1}],
    )
    expect_equal(
        actual=dig(document=web, path=("view", "produced_files")),
        expected=["replay.py"],
    )
    expect_equal(
        actual=dig(document=web, path=("view_columns", "session")),
        expected=["fact", "value"],
    )
    expect_equal(
        actual=ToolRunResult.from_report(
            payload=payload,
            output=out,
            fallback=result,
        ).tool,
        expected="record",
    )


def _raise() -> NoReturn:
    """Fail like a broken analyzer.

    Raises:
        RuntimeError: Always.

    """
    msg: str = "boom"
    raise RuntimeError(msg)


def test_failing_exec_renders_error_report(tmp_path: Path) -> None:
    """A run that crashes before reporting renders status ERROR.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "RECORD"
    _ = ent.execute_exactus(
        analyzer="record",
        title="Record Exactus",
        main=_raise,
        output=out,
    )
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_in(member="| Status | ERROR |", container=markdown)
    expect_in(
        member="> **Gate: ERROR** — RuntimeError: boom",
        container=markdown,
    )
    expect_in(
        member="N/A — the tool reported no findings list.",
        container=markdown,
    )
    payload: dict[str, JsonValue] = _payload(out=out)
    expect_equal(actual=payload["status"], expected="FAIL")
    expect_equal(actual=payload["report_generation"], expected="fallback")
    expect_equal(
        actual=dig(document=payload, path=("run", "status")),
        expected="ERROR",
    )


def test_crashed_exec_worker_renders_error_report(tmp_path: Path) -> None:
    """A dead RECORD worker gets the template report with status ERROR.

    Args:
        tmp_path: Per-test temporary directory.

    """
    out: Path = tmp_path / "EXACTUS_RESULTS" / "RECORD"
    result: ToolRunResult = ent.crashed_exactus(
        request=ToolRequest(
            identifier="record",
            output=out,
            arguments=("--url", "http://x"),
            run_id="e" * 32,
            project_root=tmp_path,
        ),
        title="Record Exactus",
        crash=ent.CrashDetails(pid=99999, exit_code=-9, elapsed_seconds=0.5),
    )
    expect_equal(actual=result.status, expected="INTERRUPT")
    markdown: str = (out / "result.md").read_text(encoding="utf-8")
    expect_in(member="| Status | ERROR |", container=markdown)
    expect_in(member="exactus --tool record", container=markdown)
    expect_in(member="`--url` `http://x`", container=markdown)
    expect_in(member="N/A — the tool reported no summary.", container=markdown)
    payload: dict[str, JsonValue] = _payload(out=out)
    expect_equal(actual=payload["status"], expected="INTERRUPT")
    expect_equal(
        actual=dig(document=payload, path=("gate", "status")),
        expected="ERROR",
    )
