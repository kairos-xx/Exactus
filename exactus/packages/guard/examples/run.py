#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Comprehensive executable examples for the process guard API."""

from __future__ import annotations

from pathlib import Path
from subprocess import Popen
from sys import executable, stdout
from sys import path as import_path
from tempfile import TemporaryDirectory
from time import sleep

if __package__ in (None, ""):
    import_path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.packages.guard import (
    ProcessGuard,
    ProcessSupervisor,
    SupervisionResult,
)


class GuardExamples:
    """Demonstrate in-process and external process-tree supervision."""

    @classmethod
    def external_tree(cls) -> None:
        """Supervise a target that creates a child and grandchild."""
        with TemporaryDirectory() as directory:
            pid_file: Path = Path(directory) / "grandchild.pid"
            child_code: str = (
                f"import pathlib,subprocess,sys,time;p=subprocess.Popen([s"
                f"ys.executable,'-c','import time;time.sleep(60)']);pathli"
                f"b.Path("
                f"{str(object=pid_file)!r}"
                f").write_text(str(p.pid));time.sleep(60)"
            )
            root_code: str = (
                "import subprocess,sys,time;"
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
                "time.sleep(.25)"
            )
            result: SupervisionResult = ProcessSupervisor(
                command=(executable, "-c", root_code),
                poll_interval=0.005,
                grace_seconds=0.2,
            ).run()
            cls._print_result(title="external nested tree", result=result)

    @classmethod
    def exit_code(cls) -> None:
        """Demonstrate preservation of the target process exit status."""
        cls._print_result(
            title="exit-code preservation",
            result=ProcessSupervisor(
                command=(executable, "-c", "raise SystemExit(7)"),
            ).run(),
        )

    @classmethod
    def run(cls) -> None:
        """Run every safe, self-cleaning example."""
        _ = stdout.write("Process Guard examples\n")
        cls.in_process()
        cls.external_tree()
        cls.exit_code()

    @staticmethod
    def in_process() -> None:
        """Guard subprocesses created directly by the current process."""
        process: Popen[bytes]
        with ProcessGuard(poll_interval=0.01, grace_seconds=0.2) as guard:
            process = Popen(
                args=(executable, "-c", "import time; time.sleep(60)"),
            )
            sleep(0.05)
            _ = stdout.write(f"in-process child started: {process.pid}\n")
        if guard.result is not None:
            _ = stdout.write(
                "".join(
                    (
                        "in-process cleanup: ",
                        f"{len(guard.result.observed)} observed, ",
                        f"{len(guard.result.survivors)} survivors\n",
                    ),
                ),
            )

    @staticmethod
    def _print_result(*, title: str, result: SupervisionResult) -> None:
        """Print concise supervision metadata.

        Args:
            title: Human-readable example name.
            result: Completed supervision result.

        """
        _ = stdout.write(
            "".join(
                (
                    f"\n{title}\n",
                    f"  exit code: {result.exit_code}\n",
                    f"  observed: {len(result.cleanup.observed)}\n",
                    f"  terminated: {len(result.cleanup.terminated)}\n",
                    f"  force-killed: {len(result.cleanup.killed)}\n",
                    f"  survivors: {len(result.cleanup.survivors)}\n",
                ),
            ),
        )


def main() -> int:
    """Run the complete example suite.

    Returns:
        Zero after all examples complete successfully.

    """
    GuardExamples.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
