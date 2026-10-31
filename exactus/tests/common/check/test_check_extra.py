# Copyright (c) 2026
"""Orchestrator internals: signals, clearing, registry and unified refresh."""

from __future__ import annotations

from errno import ENOTEMPTY
from os import environ, getpid, kill
from signal import SIGTERM
from subprocess import Popen
from sys import executable
from threading import Event
from typing import TYPE_CHECKING

import pytest

from exactus import __main__ as check
from exactus.__main__ import Application, Check, Terminal, main
from exactus.packages.pmanager.runtime import Descriptor
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    private_as,
    private_call,
    require_type,
    set_private,
)
from exactus.tools.common.catalog import Constants as CatalogConstants
from exactus.tools.common.catalog import PipelineSpec
from exactus.tools.common.registry import RunClaim, RunRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue
pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures("isolated_check")


def test_unified_aggregate_refreshes_after_single_tool(
    sample_project: Path,
) -> None:
    """A tool run after ``unified`` rewrites the stored aggregate.

    Args:
        sample_project: Generated sample project directory.

    """
    root: str = str(object=sample_project)
    expect_in(
        member=main(
            arguments=[
                "--root",
                root,
                "--exclude-tools",
                "lints",
                "coverage_tests",
                "frontend",
                "docs",
                "kwargs_typehints",
            ],
        ),
        container={0, 1},
    )
    unified: Path = (
        sample_project / "EXACTUS_RESULTS" / "PIPELINES" / "UNIFIED"
    )
    expect_true(condition=(unified / "result.json").is_file())
    expect_in(
        member=main(arguments=["--root", root, "--tool", "readme"]),
        container={0, 1},
    )
    expect_in(
        member=main(arguments=["--root", root, "--tool", "docs"]),
        container={0, 1},
    )


def test_signal_guard_sets_interrupt_flag() -> None:
    """A termination signal flips the cooperative interrupt flag."""
    private_as(owner=Check, name="_interrupt", kind=Event).clear()

    class Child:
        """Popen stand-in recording forwarded signals."""

        def __init__(self) -> None:
            """Start with no signals."""
            self.sent: list[int] = []

        def poll(self) -> None:
            """Report a running child."""

        def send_signal(self, *, sig: int) -> None:
            """Record a signal.

            Args:
                sig: Signal number.

            """
            self.sent.append(sig)

    child: Child = Child()
    set_private(owner=Check, name="_child", value=child)
    _ = private_call(owner=Check, name="_install_signal_guards")
    kill(getpid(), SIGTERM)
    expect_true(
        condition=private_as(
            owner=Check,
            name="_interrupt",
            kind=Event,
        ).is_set(),
    )
    expect_equal(actual=child.sent, expected=[SIGTERM])


def test_terminate_run_tools_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live registered runs are signalled by output or pipeline.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    Check.use_root(root=tmp_path)
    killed: list[int] = []
    commands: list[str] = []

    def record_kill(*, pid: int) -> None:
        """Record a terminate request instead of killing anything.

        Args:
            pid: Process id that would have been terminated.

        """
        killed.append(pid)

    monkeypatch.setattr(target=check, name="terminate_tree", value=record_kill)
    descriptor: Descriptor = Descriptor(
        pid=31337,
        port=9000,
        name="x",
        context="exactus:p1",
        args=(),
    )

    def find_worker(*, name: str, context: str) -> Descriptor | None:
        """Resolve only the first registered run through pmanager.

        Args:
            name: Tool process name.
            context: Tool process context.

        Returns:
            Descriptor for the first run; ``None`` for the fallback run.

        """
        return descriptor if name == "x" and context.endswith("/p1") else None

    def request_worker(
        *,
        descriptor: Descriptor,
        command: str,
        payload: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Record one pmanager control command.

        Args:
            descriptor: Target worker descriptor.
            command: IPC command.
            payload: Optional command payload.

        Returns:
            Empty successful response.

        """
        del descriptor, payload
        commands.append(command)
        return {}

    monkeypatch.setattr(
        target=check.Discovery,
        name="find",
        value=staticmethod(find_worker),
    )
    monkeypatch.setattr(
        target=check.Client,
        name="request",
        value=staticmethod(request_worker),
    )
    registry: RunRegistry = RunRegistry(
        path=Check.exactus_root / ".runtime" / "runs.db",
    )
    out: Path = tmp_path / "EXACTUS_RESULTS" / "X"
    other: Path = tmp_path / "EXACTUS_RESULTS" / "Y"
    first_sleeper: Popen[bytes] = Popen(
        args=[executable, "-c", "import time; time.sleep(60)"],
    )
    second_sleeper: Popen[bytes] = Popen(
        args=[executable, "-c", "import time; time.sleep(60)"],
    )
    try:
        for run_id, directory, pipeline, pid in (
            ("a", out, "p1", first_sleeper.pid),
            ("b", other, "p2", second_sleeper.pid),
        ):
            expect_true(
                condition=registry.claim(
                    request=RunClaim(
                        kind="tool",
                        identifier="x",
                        run_id=run_id,
                        pipeline_run_id=pipeline,
                        pid=pid,
                        output=directory,
                        targets=(),
                    ),
                )
                is not None,
            )
        expect_equal(
            actual=private_call(
                owner=Check,
                name="_terminate_run_tools",
                output=out,
            ),
            expected=1,
        )
        expect_equal(
            actual=private_call(
                owner=Check,
                name="_terminate_run_tools",
                pipeline_run_id="p2",
            ),
            expected=1,
        )
        expect_equal(
            actual=private_call(owner=Check, name="_terminate_run_tools"),
            expected=2,
        )
    finally:
        first_sleeper.kill()
        second_sleeper.kill()
    expect_true(condition=bool(killed))
    expect_in(member=31337, container=killed)
    expect_in(member=second_sleeper.pid, container=killed)
    expect_true(condition=bool(commands))
    expect_true(condition=all(command == "kill" for command in commands))


def test_clear_variants(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Clearing handles tools, pipelines, folders and debug capture.

    Args:
        tmp_path: Per-test temporary directory.
        capsys: Pytest output capture fixture.

    """
    Check.use_root(root=tmp_path)
    for name in ("LINTS", "PIPELINES/SELF", "CUSTOM"):
        (Check.exactus_root / name).mkdir(parents=True)
        (Check.exactus_root / name / "f.txt").write_text(data="x")
    locked: Path = Check.exactus_root / "LOCKED"
    (locked / "inner").mkdir(parents=True)
    (locked / "inner" / "f").write_text(data="x")
    (locked / "inner").chmod(mode=0o555)
    (tmp_path / "DEBUG.txt").write_text(data="save::dbg\n")
    (tmp_path / "dbg").mkdir()
    (tmp_path / "dbg" / "out.txt").write_text(data="x")
    _ = private_call(
        owner=Check,
        name="_clear",
        names=("lints", "self", "custom", "locked"),
    )
    expect_false(condition=(Check.exactus_root / "LINTS").exists())
    expect_false(
        condition=(Check.exactus_root / "PIPELINES" / "SELF").exists(),
    )
    expect_false(condition=(Check.exactus_root / "LOCKED").exists())
    expect_false(condition=bool(list((tmp_path / "dbg").iterdir())))
    with pytest.raises(expected_exception=ValueError, match="requires"):
        _ = private_call(owner=Check, name="_clear", names=("../etc",))
    (Check.exactus_root / "KEEP").mkdir(parents=True)
    runtime: Path = Check.exactus_root / ".runtime"
    runtime.mkdir(exist_ok=True)
    state: Path = runtime / "pipelines.db"
    state.write_text(data="coordination", encoding="utf-8")
    _ = private_call(owner=Check, name="_clear", names=())
    expect_true(condition=Check.exactus_root.is_dir())
    expect_equal(
        actual=state.read_text(encoding="utf-8"),
        expected="coordination",
    )
    expect_false(condition=(Check.exactus_root / "KEEP").exists())
    _ = private_call(owner=Check, name="_clear_all")
    expect_true(condition=bool(capsys))


def test_pipeline_clear_preserves_tool_outputs_until_workers_start(
    tmp_path: Path,
) -> None:
    """Pipeline preparation clears its report without clearing tool reports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    Check.use_root(root=tmp_path)
    for relative in ("LINTS", "DOCS", "PIPELINES/ALL_FAST"):
        directory: Path = Check.exactus_root / relative
        directory.mkdir(parents=True)
        (directory / "marker.txt").write_text(data=relative, encoding="utf-8")
    pipeline: PipelineSpec = require_type(
        value=CatalogConstants.exactus_catalog.pipeline(identifier="all-fast"),
        kind=PipelineSpec,
    )
    _ = private_call(
        owner=Check,
        name="_prepare_pipeline",
        pipeline=pipeline,
        common=(),
        run_id="pipeline-run",
    )
    expect_true(condition=(Check.exactus_root / "LINTS/marker.txt").is_file())
    expect_true(condition=(Check.exactus_root / "DOCS/marker.txt").is_file())
    expect_false(
        condition=(
            Check.exactus_root / "PIPELINES/ALL_FAST/marker.txt"
        ).exists(),
    )


def test_debug_clear_refuses_dangerous_targets(tmp_path: Path) -> None:
    """Project root, filesystem root and home are never emptied.

    Args:
        tmp_path: Per-test temporary directory.

    """
    Check.use_root(root=tmp_path)
    (tmp_path / "DEBUG.txt").write_text(data=f"save::{tmp_path}/x.log\n")
    (tmp_path / "keep.txt").write_text(data="keep")
    _ = private_call(owner=Check, name="_clear_debug_output")
    expect_true(condition=(tmp_path / "keep.txt").exists())
    (tmp_path / "DEBUG.txt").write_text(data="save::/\nsave::missing/dir\n")
    _ = private_call(owner=Check, name="_clear_debug_output")


def _ignore_path(path: str) -> None:
    """Accept a path without touching the filesystem.

    Args:
        path: Entry the retried removal would have handled.

    """
    del path


def test_force_remove_handles_enotempty(tmp_path: Path) -> None:
    """Racing writers leave directories that a second walk removes.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "t"
    target.mkdir()
    (target / "late").write_text(data="x")
    _ = private_call(
        owner=Check,
        name="_force_remove",
        func=_ignore_path,
        path=str(object=target),
        exc_info=OSError(ENOTEMPTY, "not empty"),
    )
    expect_false(condition=target.exists())


def test_bad_tool_arg_is_usage_error(sample_project: Path) -> None:
    """Malformed ``--tool-arg`` values exit with status 2.

    Args:
        sample_project: Generated sample project directory.

    """
    root: str = str(object=sample_project)
    expect_equal(
        actual=main(
            arguments=[
                "--root",
                root,
                "--tool",
                "readme",
                "--tool-arg",
                "bad",
            ],
        ),
        expected=2,
    )
    expect_in(
        member=main(
            arguments=[
                "--root",
                root,
                "--tool",
                "readme",
                "--tool-arg",
                "x::y",
            ],
        ),
        container={1, 2},
    )
    expect_equal(
        actual=main(
            arguments=["--root", root, "--tool", "readme", "docs", "extra"],
        ),
        expected=2,
    )


def test_no_server_error_and_unknown_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without any URL or server the user gets guidance.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    written: list[str] = []

    class Sink(Terminal):
        """Terminal collecting rendered lines."""

        def __init__(self) -> None:
            """Skip stream wiring."""
            self.lines = written
            self.color = False

        def write(self, text: str = "") -> None:
            """Collect a line.

            Args:
                text: Line text.

            """
            self.lines.append(text)

    app: Application = Application(output=Sink(), error=Sink(), tools=())
    monkeypatch.chdir(path=tmp_path)
    app.show_error(argument="mystery")
    expect_true(condition=any("Unknown tool" in line for line in written))


def test_pipeline_interrupted_before_start(sample_project: Path) -> None:
    """A pending interrupt synthesizes INTERRUPT results for every tool.

    Args:
        sample_project: Generated sample project directory.

    """
    private_as(owner=Check, name="_interrupt", kind=Event).set()
    status: int = main(
        arguments=[
            "--root",
            str(object=sample_project),
            "--pipeline",
            "self",
            "--exclude-tools",
            "lints",
            "coverage_tests",
        ],
    )
    expect_in(member=status, container={1, 130})


def test_clear_preserves_report_history(tmp_path: Path) -> None:
    """Clear generated output while retaining recoverable report history.

    Args:
        tmp_path: Isolated project output directory.

    """
    Check.use_root(root=tmp_path)
    history: Path = Check.exactus_root / ".history"
    history.mkdir(parents=True)
    saved: Path = history / "previous.json"
    saved.write_text(data='{"status":"PASS"}', encoding="utf-8")
    generated: Path = Check.exactus_root / "DOCS"
    generated.mkdir()
    (generated / "result.md").write_text(data="generated", encoding="utf-8")
    _ = private_call(owner=Check, name="_clear_all")
    expect_equal(
        actual=saved.read_text(encoding="utf-8"),
        expected='{"status":"PASS"}',
    )
    expect_false(condition=generated.exists())


@pytest.mark.parametrize(
    ("directive", "folder"),
    [("capture", "capture"), ("capture/run.log", "capture")],
)
def test_debug_output_resolves_relative_save_directives(
    tmp_path: Path,
    directive: str,
    folder: str,
) -> None:
    """Resolve folder and file directives relative to the selected project.

    Args:
        tmp_path: Isolated project root.
        directive: Relative save directive written to the marker.
        folder: Expected capture folder below the project root.

    """
    Check.use_root(root=tmp_path)
    (tmp_path / "DEBUG.txt").write_text(
        data=f"unrelated::ignored\nsave::{directive}\n",
        encoding="utf-8",
    )
    expect_equal(
        actual=private_call(owner=Check, name="_debug_output_dir"),
        expected=tmp_path / folder,
    )


@pytest.mark.parametrize(
    ("arguments", "remaining", "disabled"),
    [
        (("--no-config", "--docs"), ("--docs",), True),
        (("--config=config.toml", "--lints"), ("--lints",), False),
        (("--config", "config.toml", "--docs"), ("--docs",), False),
        (
            ("--", "--config", "tool.toml"),
            ("--", "--config", "tool.toml"),
            None,
        ),
        (("--config",), ("--config",), None),
    ],
)
def test_config_arguments_preserve_tool_operands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: tuple[str, ...],
    remaining: tuple[str, ...],
    *,
    disabled: bool | None,
) -> None:
    """Consume global config flags without swallowing tool arguments.

    Args:
        tmp_path: Selected project containing relative config files.
        monkeypatch: Isolate the config environment.
        arguments: Global flags followed by tool operands.
        remaining: Expected operands forwarded to the tool.
        disabled: Whether config is disabled, selected, or unchanged.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="unchanged")
    expect_equal(
        actual=private_call(
            owner=check,
            name="_extract_config",
            arguments=arguments,
        ),
        expected=remaining,
    )
    expect_equal(
        actual=environ["EXACTUS_CONFIG"],
        expected="off"
        if disabled
        else str(object=tmp_path / "config.toml")
        if disabled is False
        else "unchanged",
    )
