# Copyright (c) 2026 Project contributors
"""Run every tool example and report each one's exit status.

Each ``exactus/tools/<name>/examples`` package — including nested
examples such as ``common/templates/markdown`` — is exercised through
every supported invocation form: ``python -m
exactus.tools.<name>.examples``, ``python
exactus/tools/<name>/examples``, and ``python
exactus/tools/<name>/examples/run.py`` when the script carries a
shebang, because each path reaches a different
``__package__``/bootstrap state.  Examples that self-terminate report
their real exit code; a process guard tracks every descendant created
during the run and terminates — then force-kills — whatever outlives
the dispatch, so detached demo servers and spawned helpers cannot leak
past the runner's exit.  Example output is written to per-example logs
so detached processes cannot hold a pipe open past the parent exit.

Usage:
    python -m exactus.tools
    python exactus/tools
    python -m exactus.tools actions record --timeout 60
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from operator import attrgetter
from pathlib import Path
from subprocess import STDOUT, Popen, TimeoutExpired
from sys import executable, stdout
from sys import path as import_paths
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING, Final, TextIO, final

if __package__ in {None, ""}:
    import_paths.append(str(object=Path(__file__).resolve().parents[2]))
from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.guard import ProcessGuard
from exactus.packages.server.process_control import terminate_tree

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


@final
class Constants:
    """Group module-level constants.

    Attributes:
        log_tail: Grouped module constant.
        timeout: Grouped module constant.
        watch_seconds: Grouped module constant.
        daemons: Grouped module constant.
        tools: Grouped module constant.
        root: Grouped module constant.

    """

    log_tail: Final[int] = 12
    timeout: Final[float] = 600.0
    watch_seconds: Final[float] = 10.0
    daemons: Final[frozenset[str]] = frozenset()
    tools: Path = Path(__file__).resolve().parent
    root: Path = tools.parents[1]


@final
@dataclass(frozen=True)
class Example:
    """Describe one tool example invocation.

    Attributes:
        name: Dotted tool path such as ``actions`` or
            ``common.templates.markdown``.
        directory: Runnable ``examples`` package directory.
        module: Dotted module used for the ``-m`` form.
        arguments: Extra CLI tokens appended to the launch.
        daemon: Whether a clean run stays alive past the timeout.
        script: Whether ``run.py`` carries a shebang, marking direct
            execution as a supported invocation form.

    """

    name: str
    directory: Path
    module: str
    arguments: tuple[str, ...] = ()
    daemon: bool = False
    script: bool = False


@final
@dataclass(frozen=True)
class Report:
    """Summarize one finished example run.

    Attributes:
        example: Invoked example.
        form: Invocation form: ``module``, ``folder``, or ``script``.
        status: ``ok``, ``alive``, ``fail``, or ``timeout``.
        exit_code: Real process exit code, or ``None`` when killed.
        seconds: Wall-clock duration.
        log: Captured stdout/stderr destination.

    """

    example: Example
    form: str
    status: str
    exit_code: int | None
    seconds: float
    log: Path


def discover() -> tuple[Example, ...]:
    """Find every runnable tool example.

    Returns:
        Sorted examples discovered under ``exactus/tools``, including
        nested ``templates`` example packages.

    """
    examples: list[Example] = []
    run_py: Path
    for run_py in sorted(Constants.tools.glob(pattern="**/examples/run.py")):
        name: str = ".".join(
            run_py.parents[1].relative_to(Constants.tools).parts,
        )
        module: str = ".".join(run_py.parent.relative_to(Constants.root).parts)
        script: bool = run_py.read_bytes().startswith(b"#!")
        examples.append(
            Example(
                name=name,
                directory=run_py.parent,
                module=module,
                daemon=name in Constants.daemons,
                script=script,
            ),
        )
    return tuple(examples)


def forms(*, example: Example) -> tuple[str, ...]:
    """Return the invocation forms an example supports.

    Args:
        example: Example to enumerate.

    Returns:
        ``module`` and ``folder`` always; ``script`` only when
        ``run.py`` carries a shebang marking direct execution.

    """
    return (
        ("module", "folder", "script")
        if example.script
        else ("module", "folder")
    )


def launch(
    *,
    example: Example,
    form: str,
    timeout: float,
    logs: Path,
) -> Report:
    """Launch one example through one invocation form.

    Args:
        example: Example to invoke.
        form: ``module`` (``python -m``), ``folder`` (directory
            execution of ``__main__.py``), or ``script`` (direct
            ``run.py`` execution).
        timeout: Seconds before the process is killed.
        logs: Directory receiving the per-example output log.

    Returns:
        Report describing how the run ended.

    """
    started: float = monotonic()
    log: Path = logs / f"{example.name}-{form}.log"
    timed_out: bool = False
    if form == "module":
        command: tuple[str, ...] = (executable, "-m", example.module)
    elif form == "folder":
        command = (executable, str(object=example.directory))
    else:
        command = (executable, str(object=example.directory / "run.py"))
    stream: TextIO
    with log.open(mode="w", encoding="utf-8") as stream:
        process: Popen[bytes] = Popen(
            args=(*command, *example.arguments),
            cwd=Constants.root,
            stdout=stream,
            stderr=STDOUT,
        )
        try:
            exit_code: int | None = process.wait(timeout=timeout)
        except TimeoutExpired:
            timed_out = True
            terminate_tree(pid=process.pid)
            _ = process.wait()
            exit_code = None
    seconds: float = monotonic() - started
    status: str
    if timed_out:
        status = "alive" if example.daemon else "timeout"
    elif exit_code == 0:
        status = "ok"
    else:
        status = "fail"
    return Report(
        example=example,
        form=form,
        status=status,
        exit_code=exit_code,
        seconds=seconds,
        log=log,
    )


def show(*, report: Report) -> None:
    """Print one example's outcome, with a log tail on failure.

    Args:
        report: Completed run to describe.

    """
    code: str = (
        f"exit={report.exit_code}"
        if report.exit_code is not None
        else "killed"
    )
    _ = stdout.write(
        f"{report.example.name:<28}"
        f" "
        f"{report.form:<7}"
        f" "
        f"{report.status:<8}"
        f" "
        f"{report.seconds:6.1f}"
        f"s  "
        f"{code}"
        f"\n",
    )
    if report.status in {"fail", "timeout"}:
        tail: list[str] = report.log.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()[-Constants.log_tail :]
        line: str
        for line in tail:
            _ = stdout.write(f"    {line}\n")


def _run(
    example: Example,
    *,
    timeout: float,
    logs: Path,
) -> tuple[Report, ...]:
    """Run every supported invocation form of one example sequentially.

    Args:
        example: Example to invoke.
        timeout: Seconds before a non-daemon form is killed.
        logs: Directory receiving the per-example output log.

    Returns:
        Reports in invocation-form order.

    """
    reports: list[Report] = []
    for form in forms(example=example):
        _ = stdout.write(f"running {example.name} ({form})...\n")
        stdout.flush()
        report: Report = launch(
            example=example,
            form=form,
            timeout=Constants.watch_seconds if example.daemon else timeout,
            logs=logs,
        )
        reports.append(report)
        show(report=report)
    return tuple(reports)


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Run every tool example and report the combined outcome.

    Args:
        arguments: Explicit CLI tokens or the process arguments.

    Returns:
        Zero when every example ran well, one otherwise.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="exactus.tools",
        description=__doc__,
    )
    _ = parser.add_argument(
        "names",
        nargs="*",
        help="Restrict the run to these tool example names.",
    )
    _ = parser.add_argument(
        "--timeout",
        type=float,
        default=Constants.timeout,
        help="Seconds before a non-daemon example is killed.",
    )
    args: Namespace = parser.parse_args(args=arguments)
    scratch_dir: str
    with TemporaryDirectory(prefix="tools-examples-") as scratch_dir:
        logs: Path = Path(scratch_dir) / "logs"
        logs.mkdir()
        examples: list[Example] = list(discover())
        if args.names:
            wanted: set[str] = set(args.names)
            known: set[str] = set(map(attrgetter("name"), examples))
            unknown: set[str] = wanted - known
            if unknown:
                _ = stdout.write(
                    f"unknown examples: "
                    f"{sorted(unknown)}\nknown examples:   "
                    f"{sorted(known)}\n",
                )
                return 2
            examples = list(filter(lambda item: item.name in wanted, examples))
        run: partial[tuple[Report, ...]] = partial(
            _run,
            timeout=args.timeout,
            logs=logs,
        )
        grouped: list[tuple[Report, ...]] = []
        with (
            ProcessGuard() as guard,
            ThreadPoolExecutor(max_workers=max(1, len(examples))) as pool,
        ):
            grouped = list(pool.map(run, examples))
        if guard.result is not None and (
            guard.result.terminated or guard.result.killed
        ):
            _ = stdout.write(
                f"guard cleaned "
                f"{len(guard.result.terminated) + len(guard.result.killed)}"
                " stray descendant(s)\n",
            )
        reports: list[Report] = [
            report for group in grouped for report in group
        ]
        passed: int = 0
        for report in reports:
            if report.status in {"ok", "alive"}:
                passed += 1
        _ = stdout.write(
            f"\n{passed}/{len(reports)} invocations ran well "
            f"({len(reports) - passed} failed)\n",
        )
        return 0 if passed == len(reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
