# Copyright (c) 2026
"""Cover the ``exactus.tools`` example-runner ``__main__`` module."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from runpy import run_path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from typing import TYPE_CHECKING, Final, Self, final

if TYPE_CHECKING:
    import pytest
from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools import __main__ as tools_main


@final
class Constants:
    """Group module-level constants.

    Attributes:
        entry: Grouped module constant.
        names: Grouped module constant.

    """

    entry: Final[Path] = Path(tools_main.__file__ or "").resolve()
    names: Final[tuple[str, ...]] = (
        "actions",
        "common",
        "common.templates.markdown",
        "record",
    )


def _example(
    *,
    name: str = "demo",
    directory: Path | None = None,
    module: str = "exactus.tools.demo.examples",
    daemon: bool = False,
    script: bool = True,
) -> tools_main.Example:
    """Build an ``Example`` row with overridable fields.

    Args:
        name: Dotted example name.
        directory: Runnable ``examples`` package directory.
        module: Dotted module used for the ``-m`` form.
        daemon: Whether the example stays alive past the timeout.
        script: Whether ``run.py`` supports direct execution.

    Returns:
        A constructed ``Example``.

    """
    return tools_main.Example(
        name=name,
        directory=directory or Constants.entry.parent,
        module=module,
        daemon=daemon,
        script=script,
    )


def _process(exit_code: int = 0) -> type:
    """Build a ``Popen`` stand-in that finishes instantly.

    Args:
        exit_code: Status ``wait`` reports.

    Returns:
        A factory class mimicking ``Popen``.

    """

    class Process:
        """Fake process returning a fixed exit status."""

        pid: int = 4321

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the launch arguments without spawning."""

        @staticmethod
        def wait(timeout: float | None = None) -> int:
            """Return the recorded exit status.

            Args:
                timeout: Ignored timeout.

            Returns:
                The configured exit code.

            """
            _ = timeout
            return exit_code

    return Process


def _hanging_process() -> type:
    """Build a ``Popen`` stand-in that never finishes.

    Returns:
        A factory class mimicking a hung ``Popen``.

    """

    class Process:
        """Fake process timing out once, then reaping cleanly."""

        pid: int = 4321

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the launch arguments without spawning."""
            self.waits: int = 0

        def wait(self, timeout: float | None = None) -> int:
            """Time out on the first call, then report reaped.

            Args:
                timeout: Ignored timeout.

            Returns:
                ``130`` once the process is reaped.

            Raises:
                TimeoutExpired: On the first call only.

            """
            _ = timeout
            self.waits += 1
            if self.waits == 1:
                raise TimeoutExpired(cmd=("demo",), timeout=0)
            return 130

    return Process


def _guard(result: object | None = None) -> type:
    """Build a ``ProcessGuard`` stand-in.

    Args:
        result: Cleanup result the guard reports, ``None`` for none.

    Returns:
        A context-manager class mimicking ``ProcessGuard``.

    """
    captured: object | None = result

    class Guard:
        """Fake guard reporting a configured cleanup result."""

        result: object | None = captured

        def __enter__(self) -> Self:
            """Enter the guard scope.

            Returns:
                The guard itself.

            """
            return self

        @staticmethod
        def __exit__(*_args: object) -> None:
            """Leave the guard scope without cleanup."""

    return Guard


def test_run_path_bootstrap_augments_import_paths() -> None:
    """Executing the file outside a package puts the root on the path."""
    namespace: dict[str, object] = run_path(
        path_name=str(object=Constants.entry),
        run_name="bootstrap_probe",
    )
    expect_true(condition=callable(namespace["main"]))
    expect_true(condition="discover" in namespace)


def test_discover_finds_every_tool_example() -> None:
    """``discover`` enumerates the four bundled example packages."""
    examples: tuple[tools_main.Example, ...] = tools_main.discover()
    expect_equal(
        actual=tuple(sorted(example.name for example in examples)),
        expected=Constants.names,
    )
    example: tools_main.Example
    for example in examples:
        expect_true(condition=example.script)
        expect_true(condition=not example.daemon)
        expect_true(condition=example.module.endswith(".examples"))


def test_forms_include_script_only_when_shebang_present() -> None:
    """The ``script`` form requires a ``run.py`` shebang."""
    expect_equal(
        actual=tools_main.forms(example=_example(script=True)),
        expected=("module", "folder", "script"),
    )
    expect_equal(
        actual=tools_main.forms(example=_example(script=False)),
        expected=("module", "folder"),
    )


def test_launch_reports_success_for_each_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero exit status maps to ``ok`` for every invocation form.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_process(exit_code=0),
    )
    example: tools_main.Example = _example()
    report: tools_main.Report
    for report in (
        tools_main.launch(
            example=example,
            form=form,
            timeout=1.0,
            logs=tmp_path,
        )
        for form in ("module", "folder", "script")
    ):
        expect_equal(actual=report.status, expected="ok")
        expect_equal(actual=report.exit_code, expected=0)


def test_launch_reports_failure_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero exit status maps to ``fail``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_process(exit_code=3),
    )
    report: tools_main.Report = tools_main.launch(
        example=_example(),
        form="module",
        timeout=1.0,
        logs=tmp_path,
    )
    expect_equal(actual=report.status, expected="fail")
    expect_equal(actual=report.exit_code, expected=3)


def test_launch_reports_timeout_and_daemon_alive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hung launches are ``timeout`` unless the example is a daemon.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    terminated: list[int] = []

    def terminate(*, pid: int) -> None:
        """Record the terminated process identifier.

        Args:
            pid: Process to terminate.

        """
        terminated.append(pid)

    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_hanging_process(),
    )
    monkeypatch.setattr(
        target=tools_main,
        name="terminate_tree",
        value=terminate,
    )
    timed_out: tools_main.Report = tools_main.launch(
        example=_example(),
        form="module",
        timeout=0.01,
        logs=tmp_path,
    )
    expect_equal(actual=timed_out.status, expected="timeout")
    expect_equal(actual=timed_out.exit_code, expected=None)
    expect_equal(actual=terminated, expected=[4321])
    alive: tools_main.Report = tools_main.launch(
        example=_example(daemon=True),
        form="module",
        timeout=0.01,
        logs=tmp_path,
    )
    expect_equal(actual=alive.status, expected="alive")


def test_show_prints_status_and_failure_log_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``show`` prints one line for healthy runs and tails failed logs.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    log: Path = tmp_path / "demo-module.log"
    _ = log.write_text(data="\n".join(f"line{i}" for i in range(20)))
    out: StringIO = StringIO()
    monkeypatch.setattr(target=tools_main, name="stdout", value=out)
    report: tools_main.Report = tools_main.Report(
        example=_example(),
        form="module",
        status="fail",
        exit_code=7,
        seconds=1.5,
        log=log,
    )
    tools_main.show(report=report)
    text: str = out.getvalue()
    expect_true(condition="demo" in text and "fail" in text)
    expect_true(condition="line19" in text)
    expect_true(condition="line0" not in text)
    tools_main.show(
        report=tools_main.Report(
            example=_example(),
            form="module",
            status="ok",
            exit_code=0,
            seconds=0.5,
            log=log,
        ),
    )
    expect_true(condition="exit=0" in out.getvalue())


def test_main_rejects_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unrecognized example names exit with usage status ``2``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    out: StringIO = StringIO()
    monkeypatch.setattr(target=tools_main, name="stdout", value=out)
    status: int = tools_main.main(arguments=("nope",))
    expect_equal(actual=status, expected=2)
    expect_true(condition="unknown examples" in out.getvalue())
    expect_true(condition="actions" in out.getvalue())


def test_main_runs_every_form_and_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A healthy sweep launches each form and exits zero.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_process(exit_code=0),
    )
    monkeypatch.setattr(target=tools_main, name="ProcessGuard", value=_guard())
    out: StringIO = StringIO()
    monkeypatch.setattr(target=tools_main, name="stdout", value=out)
    expect_equal(actual=tools_main.main(arguments=()), expected=0)
    expect_true(
        condition=f"{3 * len(Constants.names)}/{3 * len(Constants.names)}"
        " invocations ran well" in out.getvalue(),
    )


def test_main_restricts_to_named_examples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Name arguments limit the sweep to the selected examples.

    Args:
        monkeypatch: Pytest patching helper.

    """
    launched: list[str] = []

    class Process:
        """Fake process recording which examples launch."""

        pid: int = 4321

        def __init__(self, *args: object, **_kwargs: object) -> None:
            """Record the example name from the log destination.

            Args:
                args: Launch command tokens.
                _kwargs: Launch keyword arguments.

            """
            _ = (args, _kwargs)

        @staticmethod
        def wait(timeout: float | None = None) -> int:
            """Report the process as finished.

            Args:
                timeout: Ignored timeout.

            Returns:
                Always ``0``.

            """
            _ = timeout
            return 0

    def popen(*args: object, **kwargs: object) -> Process:
        """Launch the fake while recording the command.

        Args:
            args: Launch command tokens.
            kwargs: Launch keyword arguments.

        Returns:
            The fake process.

        """
        _ = kwargs
        launched.append(str(object=args))
        return Process(*args)

    monkeypatch.setattr(target=tools_main, name="Popen", value=popen)
    monkeypatch.setattr(target=tools_main, name="ProcessGuard", value=_guard())
    out: StringIO = StringIO()
    monkeypatch.setattr(target=tools_main, name="stdout", value=out)
    expect_equal(actual=tools_main.main(arguments=("record",)), expected=0)
    expect_equal(actual=len(launched), expected=3)


def test_main_returns_one_when_a_form_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing example turns the combined status into ``1``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_process(exit_code=1),
    )
    monkeypatch.setattr(target=tools_main, name="ProcessGuard", value=_guard())
    monkeypatch.setattr(target=tools_main, name="stdout", value=StringIO())
    expect_equal(actual=tools_main.main(arguments=()), expected=1)


def test_main_reports_guard_cleaned_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stray descendants cleaned by the guard appear in the summary.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=tools_main,
        name="Popen",
        value=_process(exit_code=0),
    )
    monkeypatch.setattr(
        target=tools_main,
        name="ProcessGuard",
        value=_guard(result=SimpleNamespace(terminated=[11, 12], killed=[])),
    )
    out: StringIO = StringIO()
    monkeypatch.setattr(target=tools_main, name="stdout", value=out)
    expect_equal(actual=tools_main.main(arguments=()), expected=0)
    expect_true(
        condition="guard cleaned 2 stray descendant(s)" in out.getvalue(),
    )
