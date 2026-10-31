#!/usr/bin/env python3
# # Copyright (c) 2026 João Lopes.
"""Executable example of the thin meaningful CLI adapter."""

from pathlib import Path
from sys import path as import_path

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from exactus.packages.meaningful.cli import MeaningfulCli


class CliExample:
    """Demonstrate selectors, policy thresholds, and worker control."""

    @staticmethod
    def run() -> int:
        """Run a representative CLI request.

        Returns:
            The resulting value.

        """
        root: Path = Path(__file__).resolve().parents[2]
        return MeaningfulCli.run(
            arguments=(
                str(object=root),
                "--exclude",
                str(object=root / "examples" / "api"),
                "--threshold-test-0-to-1",
                "0.20",
                "--threshold-test-1-to-2",
                "0.45",
                "--threshold-test-2-to-3",
                "0.65",
                "--evidence-context",
                "2",
                "--workers",
                "4",
            ),
        )


if __name__ == "__main__":
    raise SystemExit(CliExample.run())
