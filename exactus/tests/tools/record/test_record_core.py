# Copyright (c) 2026
"""Record exactus findings and normalized report data."""

from __future__ import annotations

from json import dumps, loads
from typing import TYPE_CHECKING, Final, final
from unittest.mock import patch

import pytest

from exactus.tests.common.support import (
    dig,
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.record import core as rc
from exactus.tools.record import main as record_entry
from exactus.tools.record.action_recorder import ActionRecorder
from exactus.tools.record.arguments import Constants as _GroupFinalConstants

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.record.core import RecordResult


@final
class Constants:
    """Group module-level constants.

    Attributes:
        click: Grouped module constant.

    """

    click: Final[dict[str, str]] = {"type": "click"}


def test_findings_by_mode() -> None:
    """Failures are errors; empty and partial exports warn."""
    clean: RecordResult = rc.RecordResult(
        mode="record",
        url="u",
        actions=(Constants.click,),
        exported_events=1,
    )
    expect_equal(actual=rc.findings(result=clean), expected=())
    expect_true(condition=rc.passed(result=clean))
    empty: RecordResult = rc.RecordResult(mode="record", url="u")
    expect_equal(
        actual=[f.rule for f in rc.findings(result=empty)],
        expected=["REC002"],
    )
    expect_true(condition=rc.passed(result=empty))
    partial: RecordResult = rc.RecordResult(
        mode="record",
        url="u",
        actions=(Constants.click, Constants.click),
        exported_events=1,
    )
    expect_equal(
        actual=[f.rule for f in rc.findings(result=partial)],
        expected=["REC003"],
    )
    failed: RecordResult = rc.RecordResult(
        mode="replay",
        url="u",
        actions=(Constants.click,),
        failures=("0 click: boom",),
    )
    expect_equal(
        actual=[f.severity for f in rc.findings(result=failed)],
        expected=["error"],
    )
    expect_false(condition=rc.passed(result=failed))
    quiet_studio: RecordResult = rc.RecordResult(mode="studio", url="")
    expect_equal(actual=rc.findings(result=quiet_studio), expected=())


def test_report_data_is_normalized() -> None:
    """``report_data`` returns summary, scope, findings and extension."""
    result: RecordResult = rc.RecordResult(
        mode="studio",
        url="http://x",
        actions=(Constants.click, Constants.click, {"type": "key"}),
        exported_events=3,
        artifacts=("actions.py.txt",),
        workspace="recording.pwflow.json",
        failures=("1 click: boom",),
        studio={"events_sent": 3, "commands": "record"},
        elapsed_seconds=1.234,
    )
    expect_equal(
        actual=rc.action_counts(actions=result.actions),
        expected={"click": 2, "key": 1},
    )
    data: dict[str, JsonValue] = rc.report_data(result=result)
    expect_equal(
        actual=sorted(data),
        expected=["extension", "findings", "scope", "summary"],
    )
    expect_equal(
        actual=dig(document=data, path=("summary", "actions")),
        expected=3,
    )
    expect_equal(
        actual=dig(document=data, path=("summary", "findings_total")),
        expected=1,
    )
    expect_equal(
        actual=dig(document=data, path=("summary", "severity")),
        expected={"error": 1},
    )
    expect_equal(
        actual=dig(document=data, path=("scope", "include")),
        expected=["http://x", "recording.pwflow.json"],
    )
    expect_equal(
        actual=dig(document=data, path=("findings", 0)),
        expected={
            "id": "RECORD-001",
            "title": "Replay action failed",
            "severity": "error",
            "rule": "REC001",
            "path": "recording.pwflow.json",
            "line": None,
            "message": "1 click: boom",
            "blocking": True,
        },
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "metrics", "by_type")),
        expected=[{"type": "click", "count": 2}, {"type": "key", "count": 1}],
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "metrics", "studio")),
        expected=[
            {"fact": "events_sent", "value": 3},
            {"fact": "commands", "value": "record"},
        ],
    )
    expect_equal(
        actual=dig(document=data, path=("extension", "rules", 0)),
        expected={
            "rule": "REC001",
            "title": "Replay action failed",
            "count": 1,
        },
    )


def test_report_data_skipped_actions() -> None:
    """Unexported actions become a skipped scope row and a warning."""
    result: RecordResult = rc.RecordResult(
        mode="record",
        url="u",
        actions=(Constants.click, Constants.click),
        exported_events=1,
    )
    data: dict[str, JsonValue] = rc.report_data(result=result)
    expect_equal(
        actual=dig(document=data, path=("scope", "skipped")),
        expected=[
            {
                "target": "1 action(s)",
                "reason": "no selector-addressable Exactus Record equivalent",
            },
        ],
    )
    expect_equal(
        actual=dig(document=data, path=("findings", 0, "severity")),
        expected="warning",
    )
    expect_equal(
        actual=dig(document=data, path=("summary", "severity")),
        expected={"warning": 1},
    )


def test_record_cli_crawls_and_replays_project(
    tmp_path: Path,
    demo_url: str,
) -> None:
    """Discovery exports an ordinary project that the CLI can replay.

    Args:
        tmp_path: Project and report directories.
        demo_url: Local test application.

    """
    root: str = str(object=tmp_path)
    expect_equal(
        actual=record_entry.main(
            arguments=(
                root,
                "--crawl",
                "--url",
                demo_url,
                "--max-depth",
                "1",
                "--max-states",
                "2",
                "--output-dir",
                "crawl",
                "--headless",
            ),
        ),
        expected=0,
    )
    project: Path = tmp_path / "crawl" / _GroupFinalConstants.workspace_name
    expect_true(condition=project.is_file())
    expect_equal(
        actual=record_entry.main(
            arguments=(
                root,
                "--replay",
                str(object=project),
                "--url",
                demo_url,
                "--output-dir",
                "replay",
                "--headless",
            ),
        ),
        expected=0,
    )
    expect_true(
        condition=(tmp_path / "replay" / "flow-tests" / "junit.xml").is_file(),
    )


def test_record_cli_exports_session_and_replays_program(
    tmp_path: Path,
    demo_url: str,
) -> None:
    """Captured session input exports portable assets and replay runs Chromium.

    Args:
        tmp_path: Isolated recording project.
        demo_url: Local navigation destination.

    """
    actions: list[dict[str, JsonValue]] = [
        {"type": "navigation", "url": demo_url},
    ]
    extra: Path = tmp_path / "transfer.pwflow.json"
    with patch.object(
        target=ActionRecorder,
        attribute="run",
        return_value=actions,
    ):
        expect_equal(
            actual=record_entry.main(
                arguments=(
                    str(object=tmp_path),
                    "--url",
                    demo_url,
                    "--output-dir",
                    "recording",
                    "--workspace",
                    str(object=extra),
                ),
            ),
            expected=0,
        )
    expect_true(condition=extra.is_file())
    program: Path = tmp_path / "actions.json"
    _ = program.write_text(data=dumps(obj=actions), encoding="utf-8")
    expect_equal(
        actual=record_entry.main(
            arguments=(
                str(object=tmp_path),
                "--url",
                demo_url,
                "--replay",
                str(object=program),
                "--output-dir",
                "program-replay",
                "--headless",
            ),
        ),
        expected=0,
    )


def test_record_cli_studio_and_invalid_setup(tmp_path: Path) -> None:
    """A bounded real Studio session saves; invalid setup exits before launch.

    Args:
        tmp_path: Isolated service project.

    """
    expect_equal(
        actual=record_entry.main(
            arguments=(
                str(object=tmp_path),
                "--no-open",
                "--headless",
                "--duration",
                "0.05",
                "--output-dir",
                "studio",
            ),
        ),
        expected=0,
    )
    document: dict[str, JsonValue] = loads(
        s=(tmp_path / "studio" / "result.json").read_text(encoding="utf-8"),
    )
    expect_true(condition="extension" in document)
    for arguments in (
        ("--crawl",),
        ("--replay", "missing.json"),
        ("--crawl", "--url", "http://localhost", "--max-depth", "0"),
    ):
        with pytest.raises(expected_exception=SystemExit) as caught:
            _ = record_entry.main(arguments=(str(object=tmp_path), *arguments))
        expect_equal(actual=caught.value.code, expected=2)
