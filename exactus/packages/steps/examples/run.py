#!/usr/bin/env python3
# Copyright (c) 2026
"""Write a timestamped step trace for a small simulated tool run.

Each run recreates the git-ignored ``.scratch/`` folder beside this
file, activates :func:`~exactus.packages.steps.step_log` on ``steps.txt`` and
emits a simulated pipeline: a tool boundary, stages, substeps and
per-file records. A nested ``step_log`` context shows that inner tools
reuse the already active log instead of truncating it, and worker
threads show that writes are serialized safely. The finished trace is
printed so the timestamp, elapsed and depth columns are visible.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from importlib import import_module
from pathlib import Path
from shutil import rmtree
from sys import path as sys_path
from sys import stdout
from typing import Final, TextIO, final

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.steps import step_log, trace


@final
class Constants:
    """Collect shared example paths and the simulated stage map.

    Attributes:
        here: Directory containing this example.
        work: Scratch output directory recreated per run.
        destination: Trace file written by the demonstration.
        stages: Stage name paired with the files it pretends to scan.

    """

    here: Final[Path] = Path(__file__).resolve().parent
    work: Final[Path] = here / ".scratch"
    destination: Final[Path] = work / "ARTIFACTS" / "steps.txt"
    stages: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
        ("collect", ("src/app.py", "src/lib.py")),
        ("check", ("src/app.py", "src/lib.py", "src/extra.py")),
        ("report", ("ARTIFACTS/report.md",)),
    )


def _print(*args: str, file: TextIO | None = None) -> None:
    """Print and immediately flush a script message.

    Args:
        *args: Values to print.
        file: Stream receiving the message; defaults to ``stdout``.

    """
    stream: TextIO = file if file is not None else stdout
    _ = stream.write(" ".join(str(object=arg) for arg in args) + "\n")
    _ = stream.flush()


def _scan_file(*, stage: str, file: str) -> None:
    """Emit a substep and per-file record for one simulated file.

    Args:
        stage: Stage currently pretending to scan.
        file: Simulated file name.

    """
    trace(step=f"{stage}: scanning {file}", depth=3)
    trace(step=f"{stage}: {file} — passed, 0 diagnostics", depth=4)


def _stage(*, name: str, files: tuple[str, ...]) -> None:
    """Emit one stage header plus parallel per-file records.

    Args:
        name: Stage name recorded at depth one.
        files: Simulated files scanned by worker threads.

    """
    trace(step=f"stage: {name}", depth=1)
    trace(step=f"{name}: {len(files)} files queued", depth=2)

    def _scan(file: str) -> None:
        """Emit the records for one file in this stage.

        Args:
            file: Simulated file name.

        """
        _scan_file(stage=name, file=file)

    with ThreadPoolExecutor(max_workers=2) as pool:
        _ = list(pool.map(_scan, files))


def main() -> int:
    """Emit a simulated tool run and print the resulting trace.

    Returns:
        Zero after the demonstration completes.

    """
    if Constants.work.exists():
        rmtree(path=Constants.work)
    nested: Path = Constants.work / "nested.txt"
    with step_log(path=Constants.destination):
        trace(step="demo: run start")
        stage: tuple[str, tuple[str, ...]]
        for stage in Constants.stages:
            _stage(name=stage[0], files=stage[1])
        with step_log(path=nested):
            trace(step="demo: nested step_log reused the active log", depth=2)
        trace(step="demo: run finished")
    _ = _print(f"step trace: {Constants.destination}\n")
    _ = _print(Constants.destination.read_text(encoding="utf-8"))
    _ = _print(
        "nested step_log reuse: "
        f"{nested.name} was never created — "
        f"nested exists: {nested.exists()}\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
