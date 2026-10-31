# Copyright (c) 2026
"""Preserve skipped test evidence without turning skips into failures."""

from json import loads
from os import environ
from pathlib import Path
from subprocess import CompletedProcess, run
from sys import executable
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.coverage_tests import skip_plugin
from exactus.tools.coverage_tests.core import (
    CombinedCoverageRunner,
    CoverageConfig,
)
from exactus.tools.coverage_tests.core import TestFailure as Failure
from exactus.tools.coverage_tests.report import (
    CoverageGates,
    CoverageTestsReport,
    ReportInputs,
)

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

    from exactus.tools.common.json_types import JsonValue


class _Report:
    """Minimal pytest report stand-in carrying summary fields."""

    def __init__(
        self,
        *,
        nodeid: object,
        longrepr: object,
        duration: object,
    ) -> None:
        """Store the report fields read by the plugin.

        Args:
            nodeid: Pytest node identifier.
            longrepr: Skip detail payload.
            duration: Recorded execution seconds.

        """
        self.nodeid: object = nodeid
        self.longrepr: object = longrepr
        self.duration: object = duration


class _Options:
    """Minimal pytest config stand-in returning one option value."""

    def __init__(self, *, output: object) -> None:
        """Store the option value returned by ``getoption``.

        Args:
            output: Raw ``--exactus-timings-output`` option value.

        """
        self._output: object = output

    def getoption(self, name: str) -> object:
        """Return the stored option value regardless of ``name``.

        Args:
            name: Option name requested by the plugin.

        Returns:
            The stored option value.

        """
        del name
        return self._output


class _Reporter:
    """Minimal terminal-reporter stand-in for direct plugin calls."""

    def __init__(
        self,
        *,
        stats: dict[str, list[object]],
        output: object,
    ) -> None:
        """Store the stats mapping and option accessor.

        Args:
            stats: Pytest stats mapping grouped by outcome.
            output: Raw ``--exactus-timings-output`` option value.

        """
        self.stats: dict[str, list[object]] = stats
        self.config: _Options = _Options(output=output)
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        """Record one emitted summary line.

        Args:
            line: Text the plugin asked the reporter to print.

        """
        self.lines.append(line)


def test_skip_plugin_records_real_pytest_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the production plugin during an actual skipped test.

    Args:
        tmp_path: Isolated test project.
        capsys: Captured nested pytest output.

    """
    source: Path = tmp_path / "test_service.py"
    _ = source.write_text(
        data=(
            'import pytest\ndef test_service():\n    pytest.skip("offline")\n'
        ),
        encoding="utf-8",
    )
    status: int = pytest.main(
        args=["-q", "-p", "no:playwright", str(object=source)],
        plugins=[skip_plugin],
    )
    expect_equal(actual=status, expected=0)
    records: tuple[Failure, ...] = CombinedCoverageRunner.pytest_skips(
        text=capsys.readouterr().out,
        shard=0,
    )
    expect_equal(actual=len(records), expected=1)
    expect_equal(
        actual=records[0].test,
        expected="test_service.py::test_service",
    )
    expect_in(container=records[0].reason, member="offline")


def test_skip_plugin_preserves_parameter_ids_and_source(
    tmp_path: Path,
) -> None:
    """Keep skip details in TESTS reports and out of coverage findings.

    Args:
        tmp_path: Isolated test project.

    """
    source: Path = tmp_path / "test_skips.py"
    (tmp_path / "app.py").write_text(
        data="available = False\n",
        encoding="utf-8",
    )
    source.write_text(
        data=(
            dedent(
                text=(
                    "    import pytest, app\n    @pytest.mark.parametrize("
                    '"value", ["first", "second"])\n    def test_unavailab'
                    'le(value):\n        pytest.skip("requires unavailable'
                    ' service: " + value)\n    '
                ),
            )
        ),
        encoding="utf-8",
    )
    process: CompletedProcess[str] = run(
        args=(
            executable,
            "-m",
            "pytest",
            "-v",
            "-p",
            "exactus.tools.coverage_tests.skip_plugin",
            str(object=source),
        ),
        cwd=tmp_path,
        env={
            **environ,
            "PYTHONPATH": str(object=Path(__file__).resolve().parents[4]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=process.returncode, expected=0)
    skips: tuple[Failure, ...] = CombinedCoverageRunner.pytest_skips(
        text=process.stdout,
        shard=2,
    )
    expect_equal(actual=len(skips), expected=2)
    expect_in(container=skips[0].test, member="[first]")
    expect_in(container=skips[1].reason, member="second")
    expect_equal(actual=skips[0].line, expected=4)
    inputs: ReportInputs = ReportInputs(
        root=tmp_path,
        context=2,
        coverage={"totals": {"percent_covered": 100}, "files": {}},
        graph={},
        javascript=None,
        execution={
            "status": 0,
            "tests": [{"outcome": "SKIPPED"}, {"outcome": "SKIPPED"}],
            "skipped_tests": [
                {
                    "kind": skip.kind,
                    "test": skip.test,
                    "path": skip.path,
                    "line": skip.line,
                    "reason": skip.reason,
                    "shard": skip.shard,
                    "log": "ARTIFACTS/TESTS/pytest-shards/shard-002.log",
                }
                for skip in skips
            ],
        },
        groups=(),
        gates=CoverageGates(fail_under=90, per_file_minimum=80),
    )
    data: dict[str, JsonValue] = CoverageTestsReport.report_data(inputs=inputs)
    findings: list[dict[str, JsonValue]] = cast(
        typ="list[dict[str, JsonValue]]",
        val=data["findings"],
    )
    expect_equal(actual=findings, expected=[])
    gate: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=data["gate"],
    )
    expect_equal(actual=gate["status"], expected="PASS")
    summary: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=data["summary"],
    )
    expect_equal(
        actual=summary["severity"],
        expected={"error": 0, "warning": 0, "info": 0},
    )
    output: Path = tmp_path / "reports"
    runner: CombinedCoverageRunner = CombinedCoverageRunner(
        config=CoverageConfig(
            root=tmp_path,
            output=output,
            source_roots=(tmp_path,),
            branch=False,
            fail_under=None,
            excluded_dirs=frozenset(),
            pytest_args=(),
            measure_js=False,
            context_lines=2,
        ),
    )
    runner.run()
    reports: list[Path] = list((output / "TESTS").rglob(pattern="result.md"))
    expect_equal(actual=len(reports), expected=2)
    for report in reports:
        text: str = report.read_text(encoding="utf-8")
        expect_in(container=text, member="Skipped tests")
        expect_in(container=text, member="pytest.skip")
        expect_in(container=text, member="unavailable service: second")


def test_skip_plugin_skips_malformed_reports_and_writes_timings(
    tmp_path: Path,
) -> None:
    """Ignore malformed skip reports and aggregate per-file timings.

    Args:
        tmp_path: Isolated test project.

    """
    timings_path: Path = tmp_path / "timings.json"
    reporter: _Reporter = _Reporter(
        output=str(object=timings_path),
        stats={
            "skipped": [
                _Report(nodeid="bad.py::x", longrepr="broken", duration=0.5),
                _Report(
                    nodeid="bad.py::y",
                    longrepr=("a.py", 1),
                    duration=0.5,
                ),
                _Report(
                    nodeid="skip.py::z",
                    longrepr=("skip.py", 5, "offline"),
                    duration=0.25,
                ),
            ],
            "passed": [
                _Report(nodeid="a.py::ok", longrepr=None, duration=0.5),
                _Report(nodeid="a.py::slow", longrepr=None, duration=1.5),
                _Report(nodeid=123, longrepr=None, duration=0.4),
                _Report(nodeid="a.py::bool", longrepr=None, duration=True),
                _Report(nodeid="b.txt::x", longrepr=None, duration=0.6),
            ],
        },
    )
    skip_plugin.pytest_terminal_summary(
        terminalreporter=cast(typ="TerminalReporter", val=reporter),
    )
    expect_equal(actual=len(reporter.lines), expected=1)
    expect_in(member="EXACTUS_SKIPPED", container=reporter.lines[0])
    expect_in(member="skip.py::z", container=reporter.lines[0])
    timings: dict[str, object] = cast(
        typ="dict[str, object]",
        val=loads(s=timings_path.read_text(encoding="utf-8")),
    )
    expect_equal(
        actual=timings,
        expected={
            "version": 3,
            "files": {"a.py": 2.0, "bad.py": 1.0, "skip.py": 0.25},
        },
    )


def test_skip_plugin_ignores_missing_timings_option(tmp_path: Path) -> None:
    """Return without writing timings when the option is unset.

    Args:
        tmp_path: Isolated test project.

    """
    reporter: _Reporter = _Reporter(output=None, stats={})
    skip_plugin.pytest_terminal_summary(
        terminalreporter=cast(typ="TerminalReporter", val=reporter),
    )
    expect_equal(actual=list(tmp_path.iterdir()), expected=[])
