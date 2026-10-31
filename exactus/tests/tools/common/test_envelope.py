# Copyright (c) 2026
"""The runner-owned envelope blocks of a normalized report."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from exactus.tests.common.support import (
    Constant,
    dig,
    expect_equal,
    expect_none,
    expect_not_in,
    expect_true,
)
from exactus.tools.common import envelope as envelope_module
from exactus.tools.common.envelope import (
    Envelope,
    EnvironmentProbe,
    Redaction,
    RunFacts,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


def _facts(
    *,
    output: Path,
    status: str = "FAIL",
    error: str | None = None,
) -> RunFacts:
    """Build run facts for one test.

    Args:
        output: Report directory.
        status: Run status.
        error: Crash text.

    Returns:
        The facts.

    """
    return RunFacts(
        analyzer="lints",
        title="Lints Exactus",
        status=status,
        exit_code=1,
        error=error,
        started_at="2026-10-03T09:00:00+00:00",
        finished_at="2026-10-03T09:00:02+00:00",
        duration_seconds=125.4,
        run_id="r1",
        pipeline_run_id=None,
        command="exactus --tool lints",
        cwd="/work",
        arguments=("--tool", "lints"),
        output=output,
    )


def test_variables_are_allowlisted_and_redacted() -> None:
    """Only exact allowlisted names appear, their values redacted."""
    rows: list[JsonValue] = EnvironmentProbe.variables(
        source={
            "HOME": "/home/me",
            "CI": "true",
            "EXACTUS_RUN_ID": "r1",
            "EXACTUS_REGISTRY": "https://user:pw@example.com/x",
            "EXACTUS_API_TOKEN": "s3cret",
            "EXACTUS_PROGRESS_PATH": "/work/p.json",
            "EXACTUS_MIRROR": "https://user:pw@example.com/x",
        },
    )
    expect_equal(
        actual=rows,
        expected=[
            {"name": "CI", "value": "true"},
            {
                "name": "EXACTUS_REGISTRY",
                "value": "https://[redacted]@example.com/x",
            },
            {"name": "EXACTUS_RUN_ID", "value": "r1"},
        ],
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("EXACTUS_GITHUB_PAT", "ghp_abcdef"),
        ("EXACTUS_PWD", "hunter2"),
        ("EXACTUS_BEARER", "abc.def"),
        ("EXACTUS_PRIVATE", "-----BEGIN KEY-----"),
        ("EXACTUS_DSN", "host=db password=hunter2"),
        ("DATABASE_URL", "postgres://u:hunter2@h/db"),
    ],
)
def test_unlisted_variables_never_leak(*, name: str, value: str) -> None:
    """Variables outside the allowlist are not reported at all.

    Args:
        name: Variable name a blocklist would miss.
        value: Secret value.

    """
    rows: list[JsonValue] = EnvironmentProbe.variables(source={name: value})
    expect_equal(actual=rows, expected=[])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("postgres://u:pa/ss@h/db", "postgres://[redacted]@h/db"),
        ("https://u:p@ss@h/x", "https://[redacted]@h/x"),
        (
            "https://ghp_abc@github.com/o/r",
            "https://[redacted]@github.com/o/r",
        ),
        (
            "x https://u:p@h y https://v:q@k",
            "x https://[redacted]@h y https://[redacted]@k",
        ),
        ("https://registry.example/@scope/pkg", None),
        ("https://h/path?u=a@b", None),
        ("host=db password=hunter2", "host=db password=[redacted]"),
        ("--token=abc --verbose", "--token=[redacted] --verbose"),
        ("--password hunter2 -v", "--password [redacted] -v"),
        ("Authorization: Bearer abc.def", "Authorization: Bearer [redacted]"),
        ("https://h/x?api_key=k1&y=2", "https://h/x?api_key=[redacted]&y=2"),
        ("exactus --tool lints", None),
    ],
)
def test_redaction_text(*, value: str, expected: str | None) -> None:
    """URL userinfo and keyed secrets hide; ordinary text stays.

    Args:
        value: Text to redact.
        expected: Redacted text, or ``None`` when it must stay unchanged.

    """
    expect_equal(
        actual=Redaction.text(value=value),
        expected=value if expected is None else expected,
    )


def test_redaction_arguments() -> None:
    """A bare secret flag hides the argument that follows it."""
    expect_equal(
        actual=Redaction.arguments(
            values=(
                "--token",
                "abc",
                "--password=pw",
                "--db",
                "postgres://u:p/w@h/d",
                "--auth",
                "--verbose",
            ),
        ),
        expected=[
            "--token",
            "[redacted]",
            "--password=[redacted]",
            "--db",
            "postgres://[redacted]@h/d",
            "--auth",
            "--verbose",
        ],
    )


def test_invocation_is_redacted(tmp_path: Path) -> None:
    """The invocation block never shows credentials.

    Args:
        tmp_path: Per-test temporary directory.

    """
    facts: RunFacts = replace(
        _facts(output=tmp_path),
        command="exactus --tool lints --token=s3cret https://u:pw@h/x",
        arguments=("--token", "s3cret", "--url", "https://u:p@w@h/x"),
    )
    blocks: dict[str, JsonValue] = Envelope.build(facts=facts, payload={})
    shown: str = str(object=blocks["invocation"])
    expect_not_in(member="s3cret", container=shown)
    expect_not_in(member="pw", container=shown)
    expect_not_in(member="p@w", container=shown)
    expect_equal(
        actual=dig(document=blocks, path=("invocation", "command")),
        expected=(
            "exactus --tool lints --token=[redacted] https://[redacted]@h/x"
        ),
    )


def test_environment_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment block names OS, Python, Node and CPUs.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=envelope_module,
        name="which",
        value=Constant(value=None),
    )
    facts: dict[str, JsonValue] = EnvironmentProbe.facts(source={})
    expect_none(value=facts["node"])
    expect_equal(actual=facts["variables"], expected=[])
    expect_true(condition=isinstance(facts["python"], str))
    expect_true(condition=isinstance(facts["os"], str))


def test_node_version_reads_the_installed_node(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A Node on PATH reports its version; a failing one reports none.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Per-test temporary directory.

    """
    node: Path = tmp_path / "node"
    _ = node.write_text(data="#!/bin/sh\necho v1.2.3\n")
    node.chmod(mode=0o755)
    monkeypatch.setattr(
        target=envelope_module,
        name="which",
        value=Constant(value=str(object=node)),
    )
    expect_equal(actual=EnvironmentProbe.node_version(), expected="v1.2.3")
    _ = node.write_text(data="#!/bin/sh\nexit 3\n")
    expect_none(value=EnvironmentProbe.node_version())


def test_duration_human() -> None:
    """Durations read in seconds, then minutes and seconds."""
    expect_equal(
        actual=Envelope.duration_human(seconds=1.24),
        expected="1.2 s",
    )
    expect_equal(
        actual=Envelope.duration_human(seconds=125.4),
        expected="2 min 5 s",
    )


@pytest.mark.parametrize(
    ("status", "error", "findings", "expected"),
    [
        ("PASS", None, [], ("PASS", "No blocking findings")),
        (
            "FAIL",
            None,
            [{"blocking": True}, {"blocking": False}],
            ("FAIL", "1 blocking finding"),
        ),
        ("FAIL", None, [], ("FAIL", "the tool exited with status 1")),
        ("ERROR", "Boom: bad\ntrace", None, ("ERROR", "Boom: bad")),
        ("ERROR", None, None, ("ERROR", "the tool ended early")),
    ],
)
def test_gate(
    *,
    tmp_path: Path,
    status: str,
    error: str | None,
    findings: list[JsonValue] | None,
    expected: tuple[str, str],
) -> None:
    """The gate follows status, blocking findings and crash text.

    Args:
        tmp_path: Per-test temporary directory.
        status: Run status.
        error: Crash text.
        findings: Tool findings, or ``None`` when absent.
        expected: Gate status and reason.

    """
    payload: dict[str, JsonValue] = (
        {} if findings is None else {"findings": findings}
    )
    gate: dict[str, JsonValue] = Envelope.gate(
        facts=_facts(output=tmp_path, status=status, error=error),
        payload=payload,
    )
    expect_equal(actual=(gate["status"], gate["reason"]), expected=expected)


def test_artifacts_list_visible_files(tmp_path: Path) -> None:
    """Artifacts list files under ARTIFACTS/ without hidden entries.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_equal(actual=Envelope.artifacts(output=tmp_path), expected=[])
    folder: Path = tmp_path / "ARTIFACTS"
    (folder / "deep").mkdir(parents=True)
    _ = (folder / "stderr.log").write_text(data="err")
    _ = (folder / "deep" / "x.json").write_text(data="{}")
    _ = (folder / ".progress.json").write_text(data="{}")
    (folder / "link").symlink_to(target=folder / "stderr.log")
    expect_equal(
        actual=Envelope.artifacts(output=tmp_path),
        expected=[
            {"name": "x.json", "path": "ARTIFACTS/deep/x.json", "bytes": 2},
            {"name": "stderr.log", "path": "ARTIFACTS/stderr.log", "bytes": 3},
        ],
    )


def test_build_returns_every_envelope_block(tmp_path: Path) -> None:
    """The envelope carries six blocks and prefers the payload title.

    Args:
        tmp_path: Per-test temporary directory.

    """
    blocks: dict[str, JsonValue] = Envelope.build(
        facts=_facts(output=tmp_path),
        payload={"title": "Lints Exactus", "findings": []},
    )
    expect_equal(
        actual=sorted(blocks),
        expected=sorted(envelope_module.Constants.blocks),
    )
    expect_equal(
        actual=dig(document=blocks, path=("tool", "display_name")),
        expected="Lints Exactus",
    )
    expect_equal(
        actual=dig(document=blocks, path=("run", "duration_human")),
        expected="2 min 5 s",
    )
    expect_equal(
        actual=dig(document=blocks, path=("invocation", "arguments")),
        expected=["--tool", "lints"],
    )
    fallback: dict[str, JsonValue] = Envelope.build(
        facts=_facts(output=tmp_path),
        payload={},
    )
    expect_equal(
        actual=dig(document=fallback, path=("tool", "display_name")),
        expected="Lints Exactus",
    )
    environment: JsonValue = fallback["environment"]
    expect_true(
        condition=isinstance(environment, dict) and "cpu_count" in environment,
    )


def test_tool_version_without_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing distribution leaves the version unknown.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=envelope_module.Constants,
        name="distribution",
        value="exactus-not-installed-anywhere",
    )
    expect_none(value=Envelope.tool_version())
