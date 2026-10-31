#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Build representative traces, analyze them, and export the dashboard."""

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from tempfile import TemporaryDirectory
from textwrap import dedent

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.performance import Performance, PerformanceRun


def _trace(*, tool: str) -> str:
    """Create a representative trace with stages, bursts, and a stall.

    Args:
        tool: Tool label embedded in event messages.

    Returns:
        Complete ``steps.txt`` content.

    """
    return (
        "\n".join(
            (
                f"2026-10-14T12:00:00.000+00:00 +    0.000s {tool}: start",
                "2026-10-14T12:00:00.010+00:00 +    0.010s   discover",
                "2026-10-14T12:00:00.020+00:00 +    0.020s     scan files",
                "2026-10-14T12:00:00.030+00:00 +    0.030s     scan files",
                "2026-10-14T12:00:00.040+00:00 +    0.040s     scan files",
                "2026-10-14T12:00:01.500+00:00 +    1.500s   analyze",
                "2026-10-14T12:00:01.520+00:00 +    1.520s     parse",
                "2026-10-14T12:00:01.540+00:00 +    1.540s     parse",
                "2026-10-14T12:00:01.560+00:00 +    1.560s     parse",
                "2026-10-14T12:00:02.000+00:00 +    2.000s   report",
                f"2026-10-14T12:00:02.050+00:00 +    2.050s {tool}: done",
            ),
        )
        + "\n"
    )


def main() -> int:
    """Exercise discovery, analysis, export, and reporting.

    Returns:
        Zero after the example completes successfully.

    """
    with TemporaryDirectory(prefix="performance-example-") as temporary:
        root: Path = Path(temporary)
        for tool in ("LINTS", "COVERAGE_TESTS", "KWARGS_TYPEHINTS"):
            trace: Path = (
                root / "EXACTUS_RESULTS" / tool / "ARTIFACTS" / "steps.txt"
            )
            trace.parent.mkdir(parents=True, exist_ok=True)
            _ = trace.write_text(
                data=_trace(tool=tool.lower()),
                encoding="utf-8",
            )
        runs: tuple[PerformanceRun, ...] = Performance.analyze(
            paths=(root / "EXACTUS_RESULTS",),
        )
        output: Path = root / "dashboard"
        index: Path = Performance.export(
            paths=(root / "EXACTUS_RESULTS",),
            destination=output,
        )
        for run in runs:
            _ = stdout.write(
                f"{run.tool}: duration={run.duration:.3f}s "
                f"events={len(run.events)} stages={len(run.stages)} "
                f"largest_gap={run.largest_gap:.3f}s\n",
            )
            for bottleneck in run.bottlenecks[:3]:
                _ = stdout.write(
                    f"  {bottleneck.kind}: {bottleneck.label} "
                    f"score={bottleneck.score:.3f}\n",
                )
        _ = stdout.write(f"Dashboard exported to {index}\n")
        _ = stdout.write(
            dedent(
                text=(
                    "    Use Performance.serve(...) in a persistent applic"
                    "ation to open it.\n    "
                ),
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
