# Copyright (c) 2026 João Lopes.
"""Public high-level API for performance analysis."""

from pathlib import Path
from sys import stdout
from time import sleep
from typing import TextIO

from exactus.packages.performance.analyzer import PerformanceAnalyzer
from exactus.packages.performance.config import PerformanceConfig
from exactus.packages.performance.dashboard import DashboardExporter
from exactus.packages.performance.model import PerformanceRun
from exactus.packages.performance.report import Constants as ReportConstants
from exactus.packages.performance.report import JsonObject, PerformanceReport
from exactus.packages.performance.session import (
    DashboardLauncher,
    DashboardSession,
)


class Performance:
    """Expose the performance analyzer as a compact application API."""

    @classmethod
    def execute(
        cls,
        *,
        config: PerformanceConfig,
        runs: tuple[PerformanceRun, ...] | None = None,
        summary: bool = False,
        report: Path | None = None,
        writer: TextIO = stdout,
    ) -> int:
        """Run the complete analyze, report, export and serve flow.

        Args:
            config: Resolved analyzer configuration.
            runs: Pre-analyzed runs; analyzed from ``config`` when absent.
            summary: Print the analysis summary without exporting.
            report: Optional JSON report destination overriding
                ``<output>/report.json``.
            writer: Stream receiving progress lines.

        Returns:
            ``0`` on success, ``2`` when no traces are discovered.

        """
        paths: tuple[Path, ...] = config.paths()
        resolved: tuple[PerformanceRun, ...] = (
            runs
            if runs is not None
            else cls.analyze(
                paths=paths,
                gap_threshold=config.gap_threshold,
                repetition_threshold=config.repetition_threshold,
            )
        )
        if not resolved:
            _ = writer.write("No steps.txt traces found.\n")
            return 2
        _ = writer.write(cls.summarize(runs=resolved) + "\n")
        written: Path = PerformanceReport.write(
            runs=resolved,
            path=report
            if report is not None
            else config.output / ReportConstants.file_name,
        )
        _ = writer.write(f"Report: {written}\n")
        if summary:
            return 0
        index: Path = DashboardExporter.export(
            runs=resolved,
            destination=config.output,
        )
        _ = writer.write(f"Dashboard: {index}\n")
        if not config.serve:
            return 0
        session: DashboardSession = DashboardLauncher.serve(
            directory=config.output,
            open_browser_window=config.open,
            executable=config.chrome,
            server_timeout=config.server_timeout,
        )
        _ = writer.write(f"Serving: {session.url}\nPress Ctrl+C to stop.\n")
        try:
            while True:
                sleep(3600.0)
        except KeyboardInterrupt:
            session.close()
        return 0

    @classmethod
    def summarize(cls, *, runs: tuple[PerformanceRun, ...]) -> str:
        """Render a compact textual run summary.

        Args:
            runs: Analyzed runs to summarize.

        Returns:
            Human-readable summary text.

        """
        return "\n".join(
            line for run in runs for line in cls._run_lines(run=run)
        )

    @classmethod
    def export(cls, *, paths: tuple[Path, ...], destination: Path) -> Path:
        """Analyze traces and export the interactive dashboard.

        Args:
            paths: Trace files or directories containing trace files.
            destination: Dashboard output directory.

        Returns:
            Generated dashboard index path.

        """
        return DashboardExporter.export(
            runs=cls.analyze(paths=paths),
            destination=destination,
        )

    @classmethod
    def serve(
        cls,
        *,
        paths: tuple[Path, ...],
        destination: Path,
        open_browser_window: bool = True,
        executable: Path | None = None,
        server_timeout: float = 10.0,
    ) -> DashboardSession:
        """Analyze, export, serve, and optionally open the dashboard.

        ``exactus.packages.server`` owns loopback serving and reuse while
        ``exactus.packages.browser`` owns the browser lifecycle.

        Args:
            paths: Trace files or directories containing trace files.
            destination: Dashboard output directory.
            open_browser_window: Whether to launch Chrome/Chromium.
            executable: Optional Chrome/Chromium executable override.
            server_timeout: Maximum seconds to wait for server readiness.

        Returns:
            Dashboard lifecycle session. Call ``close`` when finished.

        """
        _ = cls.export(paths=paths, destination=destination)
        return DashboardLauncher.serve(
            directory=destination,
            open_browser_window=open_browser_window,
            executable=executable,
            server_timeout=server_timeout,
        )

    @classmethod
    def report(
        cls,
        *,
        paths: tuple[Path, ...],
        destination: Path | None = None,
        gap_threshold: float = 0.25,
        repetition_threshold: int = 10,
    ) -> JsonObject:
        """Build the machine-readable report, optionally writing it.

        No dashboard, server or browser is involved.

        Args:
            paths: Trace files or directories containing trace files.
            destination: File to write the JSON report to, if any.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            The report document.

        """
        runs: tuple[PerformanceRun, ...] = cls.analyze(
            paths=paths,
            gap_threshold=gap_threshold,
            repetition_threshold=repetition_threshold,
        )
        if destination is not None:
            _ = PerformanceReport.write(runs=runs, path=destination)
        return PerformanceReport.build(runs=runs)

    @staticmethod
    def analyze(
        *,
        paths: tuple[Path, ...],
        gap_threshold: float = 0.25,
        repetition_threshold: int = 10,
    ) -> tuple[PerformanceRun, ...]:
        """Analyze traces below the supplied paths.

        Args:
            paths: Trace files or directories containing trace files.
            gap_threshold: Minimum silent interval to report.
            repetition_threshold: Minimum repeated events to report.

        Returns:
            Analyzed runs in deterministic source order.

        """
        return PerformanceAnalyzer.analyze_paths(
            paths=paths,
            gap_threshold=gap_threshold,
            repetition_threshold=repetition_threshold,
        )

    @staticmethod
    def _run_lines(*, run: PerformanceRun) -> tuple[str, ...]:
        """Render one run's headline plus its main bottleneck hints.

        Args:
            run: Analyzed run.

        Returns:
            The headline, then indented actor, step and worker hints.

        """
        lines: list[str] = [
            f"{run.tool}: {run.duration:.3f}s, {len(run.events)} events, "
            f"{run.event_rate:.2f} events/s, gap {run.largest_gap:.3f}s",
        ]
        if run.duration > 0.0:
            lines.append(
                f"  silent {run.silent:.3f}s "
                f"({run.silent / run.duration:.0%} of runtime)",
            )
        lines.extend(
            f"  actor {actor.name or '-'}: {actor.inferred:.3f}s "
            f"({actor.share:.0%}), {actor.count} events"
            for actor in run.actors[:3]
        )
        lines.extend(
            f"  slow {step.duration:.3f}s {step.source}: {step.label[:80]}"
            for step in run.slowest[:3]
        )
        if run.resources is not None:
            lines.append(
                f"  cpu mean {run.resources.mean_cpu:.0f}% "
                f"peak {run.resources.peak_cpu:.0f}% · "
                f"rss peak {run.resources.peak_rss:.0f} MiB · "
                f"io {run.resources.read:.1f} MiB read / "
                f"{run.resources.write:.1f} MiB written",
            )
        if len(run.threads) > 1:
            lines.append(
                f"  workers: {len(run.threads)} threads, busiest "
                f"{run.threads[0].name} {run.threads[0].busy:.3f}s",
            )
        return tuple(lines)
