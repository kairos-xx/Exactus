#!/usr/bin/env python3
# Copyright (c) 2026
"""Run overlapping Exactus processes against one disposable workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shlex import join
from subprocess import DEVNULL, Popen
from sys import executable, stdout
from tempfile import mkdtemp
from textwrap import dedent
from time import monotonic, sleep
from typing import TYPE_CHECKING, BinaryIO, Final, Self, cast, final

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.tools.common.registry import RunRecord, RunRegistry

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


@final
class Constants:
    """Store fixed demo settings.

    Attributes:
        default_files: Number of intentionally imperfect Python files.
        poll_seconds: Delay between registry snapshots.
        launch_grace_seconds: Delay after the final scheduled launch.
        unexpected_markers: Transcript fragments indicating infrastructure
            failure rather than ordinary analyzer findings.

    """

    default_files: Final[int] = 80
    poll_seconds: Final[float] = 0.2
    launch_grace_seconds: Final[float] = 0.25
    unexpected_markers: Final[tuple[str, ...]] = (
        "Traceback (most recent call last)",
        "exited before reporting",
        "external run produced no report",
        "No module named exactus",
    )


@dataclass(frozen=True, slots=True)
class Invocation:
    """Describe one independently launched Exactus process.

    Attributes:
        label: Short name used in monitoring output and log filenames.
        delay_seconds: Delay from demo start before launch.
        command: Complete child-process argument vector.

    """

    label: str
    delay_seconds: float
    command: tuple[str, ...]


@dataclass(slots=True)
class RunningInvocation:
    """Track one live child process and its transcript.

    Attributes:
        invocation: Immutable launch request.
        process: Running operating-system process.
        transcript: Binary output destination owned by the driver.

    """

    invocation: Invocation
    process: Popen[bytes]
    transcript: BinaryIO

    def close(self: Self) -> None:
        """Close the transcript after the process has stopped."""
        self.transcript.close()


def emit(*, message: str) -> None:
    """Write one immediately visible demo line.

    Args:
        message: Text to write, without its trailing newline.

    """
    _ = stdout.write(message + "\n")
    stdout.flush()


def parser() -> ArgumentParser:
    """Build the collision-demo command-line parser.

    Returns:
        Configured argument parser.

    """
    result: ArgumentParser = ExactusArgumentParser(description=__doc__)
    _ = result.add_argument(
        "--files",
        type=int,
        default=Constants.default_files,
        help="number of generated Python files",
    )
    _ = result.add_argument(
        "--prepare-only",
        action="store_true",
        help="create the project and print commands without launching them",
    )
    return result


def prepare_project(*, file_count: int) -> Path:
    """Create a disposable project containing deliberate analyzer findings.

    Args:
        file_count: Number of Python modules to generate.

    Raises:
        ValueError: If fewer than one source file was requested.

    Returns:
        Generated project root.

    """
    if file_count < 1:
        msg: str = "--files must be at least 1"
        raise ValueError(msg)
    root: Path = Path(mkdtemp(prefix="exactus-coordination-"))
    source: Path = root / "src"
    logs: Path = root / ".demo-logs"
    source.mkdir()
    logs.mkdir()
    _ = (root / "pyproject.toml").write_text(
        data=(
            dedent(
                text=(
                    '    [project]\n    name = "exactus-coordination-examp'
                    'le"\n    version = "0.0.0"\n    requires-python = ">='
                    '3.13"\n    '
                ),
            )
        ),
        encoding="utf-8",
    )
    _ = (root / "README.md").write_text(
        data=(
            dedent(
                text=(
                    "    # Exactus coordination fixture\n    \n    - `pypr"
                    "oject.toml` — Minimal project metadata.\n    - `src/`"
                    " — Generated Python modules.\n    "
                ),
            )
        ),
        encoding="utf-8",
    )
    inventory: list[str] = ["# Generated modules", ""]
    index: int
    for index in range(file_count):
        name: str = f"module_{index:03d}.py"
        _ = (source / name).write_text(
            data=dedent(
                text=(
                    f'\n                """Intentional analyzer fixture."""\n '
                    f"               def add_"
                    f"{index}"
                    f"(left, right):\n                    return left + right"
                    f"\n                "
                ),
            ).removeprefix("\n"),
            encoding="utf-8",
        )
        inventory.append(f"- `{name}` — Intentional type-hint finding.")
    _ = (source / "README.md").write_text(
        data="\n".join(inventory) + "\n",
        encoding="utf-8",
    )
    return root


def invocations(*, root: Path) -> tuple[Invocation, ...]:
    """Build overlapping commands sharing one project-root context.

    Args:
        root: Disposable project root.

    Returns:
        Launch requests ordered by their intentional collision time.

    """
    root_text: str = str(object=root)
    exactus_entry: str = str(object=Path(__file__).resolve().parents[3])
    include: str = "src/**/*.py"
    pipeline: tuple[str, ...] = (
        executable,
        exactus_entry,
        "--pipeline",
        "unified",
        "--root",
        root_text,
        "--exclude-tools",
        "coverage_tests",
        "docs",
        "frontend",
        "visual_cause",
        "--tool-arg",
        "lints::--dry",
        "--tool-arg",
        "lints::--no-install-tools",
        "--tool-arg",
        "lints::--include",
        "--tool-arg",
        f"lints::{include}",
        "--tool-arg",
        "kwargs_typehints::--include",
        "--tool-arg",
        f"kwargs_typehints::{include}",
    )
    return (
        Invocation(label="pipeline", delay_seconds=0.0, command=pipeline),
        Invocation(
            label="pipeline-reset",
            delay_seconds=0.8,
            command=pipeline,
        ),
        Invocation(
            label="pipeline-reset-again",
            delay_seconds=1.1,
            command=pipeline,
        ),
        Invocation(
            label="kwargs-rerun",
            delay_seconds=1.4,
            command=(
                executable,
                exactus_entry,
                "--kwargs_typehints",
                root_text,
                "--include",
                include,
            ),
        ),
    )


def print_commands(*, plans: tuple[Invocation, ...]) -> None:
    """Print copyable commands for the four-terminal demonstration.

    Args:
        plans: Ordered launch requests.

    """
    plan: Invocation
    for plan in plans:
        emit(message=f"{plan.label} (+{plan.delay_seconds:.1f}s):")
        emit(message=join(split_command=plan.command))


def registry_row(record: RunRecord, /) -> str:
    """Render one normalized registry record for the demo timeline.

    Args:
        record: Live pipeline or task record.

    Returns:
        Compact lifecycle row.

    """
    return (
        f"{record.kind:<8} {record.identifier:<18} "
        f"{record.status:<8} {record.progress * 100:6.2f}% "
        f"{record.step:<24} {record.detail}"
    ).rstrip()


def registry_snapshot(*, root: Path) -> tuple[str, ...]:
    """Return normalized live process rows from the workspace registry.

    Args:
        root: Disposable project root.

    Returns:
        Stable display rows for every currently live run.

    """
    database: Path = root / "EXACTUS_RESULTS" / ".runtime" / "runs.db"
    if not database.exists():
        return ()
    try:
        records: tuple[RunRecord, ...] = RunRegistry(path=database).live()
    except OSError:
        return ()
    return tuple(map(registry_row, records))


def launch(*, root: Path, invocation: Invocation) -> RunningInvocation:
    """Launch one Exactus invocation with an isolated transcript.

    Args:
        root: Disposable project root.
        invocation: Process launch request.

    Returns:
        Live process and owned transcript stream.

    """
    transcript: BinaryIO = (
        root / ".demo-logs" / f"{invocation.label}.log"
    ).open(mode="wb")
    process: Popen[bytes] = Popen(
        args=invocation.command,
        cwd=root,
        stdin=DEVNULL,
        stdout=transcript,
        stderr=transcript,
    )
    return RunningInvocation(
        invocation=invocation,
        process=process,
        transcript=transcript,
    )


def transcript_failed(*, root: Path, invocation: Invocation) -> bool:
    """Return whether one transcript contains a coordination failure.

    Args:
        root: Disposable project root.
        invocation: Completed invocation whose transcript is inspected.

    Returns:
        Whether a worker crash or missing report was observed.

    """
    transcript: str = (
        root / ".demo-logs" / f"{invocation.label}.log"
    ).read_text(encoding="utf-8", errors="replace")
    return any(map(transcript.__contains__, Constants.unexpected_markers))


def run_demo(*, root: Path, plans: tuple[Invocation, ...]) -> int:
    """Run every collision and monitor the shared registry until settled.

    Args:
        root: Disposable project root.
        plans: Ordered launch requests.

    Returns:
        Zero when every process exits normally or with analyzer findings.

    """
    started: float = monotonic()
    pending: list[Invocation] = list(plans)
    running: list[RunningInvocation] = []
    previous: tuple[str, ...] = ()
    coordination_failed: bool = False
    while pending or running:
        elapsed: float = monotonic() - started
        while pending and pending[0].delay_seconds <= elapsed:
            plan: Invocation = pending.pop(0)
            current: RunningInvocation = launch(root=root, invocation=plan)
            running.append(current)
            emit(
                message=(
                    f"[{elapsed:6.2f}s] launched {plan.label} "
                    f"pid={current.process.pid}"
                ),
            )
        snapshot: tuple[str, ...] = registry_snapshot(root=root)
        if snapshot != previous:
            emit(message=f"\n[{elapsed:6.2f}s] workspace state")
            row: str
            for row in snapshot:
                emit(message=f"  {row}")
            previous = snapshot
        active: list[RunningInvocation] = []
        for current in running:
            return_code: int | None = current.process.poll()
            if return_code is None:
                active.append(current)
                continue
            current.close()
            coordination_failed |= transcript_failed(
                root=root,
                invocation=current.invocation,
            )
            emit(
                message=(
                    f"[{elapsed:6.2f}s] {current.invocation.label} "
                    f"exited {return_code}"
                ),
            )
        running = active
        if pending or running:
            sleep(Constants.poll_seconds)
    sleep(Constants.launch_grace_seconds)
    return int(coordination_failed)


def main() -> int:
    """Prepare and optionally execute the coordination collision demo.

    Returns:
        Process exit status.

    """
    options: Namespace = parser().parse_args()
    root: Path = prepare_project(file_count=cast(typ="int", val=options.files))
    plans: tuple[Invocation, ...] = invocations(root=root)
    emit(message=f"demo project: {root}")
    if cast(typ="bool", val=options.prepare_only):
        print_commands(plans=plans)
        return 0
    status: int = run_demo(root=root, plans=plans)
    emit(message=f"\nreports: {root / 'EXACTUS_RESULTS'}")
    emit(message=f"transcripts: {root / '.demo-logs'}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
