#!/usr/bin/env python3
# # Copyright (c) 2026 João Lopes.
"""Comprehensive executable example of the meaningful Python API."""

from pathlib import Path
from sys import path as import_path
from sys import stdout

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from exactus.packages.meaningful import (
    AnalysisRun,
    EvaluationPolicy,
    Meaningful,
    ProgressSnapshot,
)


class ApiExample:
    """Demonstrate analysis, parallelism, metadata, and progress callbacks."""

    @staticmethod
    def run() -> None:
        """Analyze the package and print concise run information."""
        root: Path = Path(__file__).resolve().parents[2]
        updates: list[ProgressSnapshot] = []
        analyzer: Meaningful = Meaningful(
            policy=EvaluationPolicy(evidence_context=2),
            max_workers=4,
            on_progress=updates.append,
        )
        run: AnalysisRun = analyzer.analyze(
            paths=[root, str(object=root / "examples" / "**" / "*.py")],
            exclude=(root / "examples" / "cli",),
        )
        stdout.write(
            "Meaningful Python API example\n"
            f"files: {run.metadata.total_files}\n"
            f"workers: {run.metadata.workers_used}\n"
            f"duration: {run.metadata.duration_seconds:.6f}s\n"
            f"progress callbacks: {len(updates)}\n"
            f"completion: {updates[-1].percent if updates else 100.0:.2f}%\n"
            f"TEST-3: {run.metadata.test_3}\n",
        )


if __name__ == "__main__":
    ApiExample.run()
