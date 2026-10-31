# Copyright (c) 2026
"""Cover the bundled ``guard`` example entry point."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import Final, Self, final

import pytest

from exactus.packages import guard as guard_package
from exactus.tests.common.support import expect_equal, expect_in


@final
class Constants:
    """Group module-level constants.

    Attributes:
        example: Grouped module constant.

    """

    example: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "guard"
        / "examples"
        / "run.py"
    )


@dataclass(frozen=True, slots=True)
class CleanupStub:
    """Stand-in for the real cleanup summary.

    Attributes:
        observed: Observed descendant process ids.
        terminated: Terminated descendant process ids.
        killed: Force-killed descendant process ids.
        survivors: Surviving descendant process ids.

    """

    observed: tuple[int, ...] = ()
    terminated: tuple[int, ...] = ()
    killed: tuple[int, ...] = ()
    survivors: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ResultStub:
    """Stand-in for the real ``SupervisionResult``.

    Attributes:
        exit_code: Target process exit status.
        cleanup: Synthetic cleanup summary.
        observed: Observed process ids.
        survivors: Surviving process ids.

    """

    exit_code: int = 0
    cleanup: CleanupStub = field(default_factory=CleanupStub)
    observed: tuple[int, ...] = ()
    survivors: tuple[int, ...] = ()


class ProcessStub:
    """Stand-in for a spawned child process.

    Attributes:
        pid: Synthetic child process id.

    """

    pid: int = 4242


class GuardStub:
    """Stand-in for the real ``ProcessGuard`` context manager."""

    def __init__(self, *, poll_interval: float, grace_seconds: float) -> None:
        """Record the guard timing options.

        Args:
            poll_interval: Seconds between descendant polls.
            grace_seconds: Termination grace period.

        """
        _ = poll_interval
        _ = grace_seconds
        self.result: ResultStub | None = ResultStub()

    def __enter__(self) -> Self:
        """Enter the synthetic supervision scope.

        Returns:
            The guard stub itself.

        """
        return self

    def __exit__(self, *exc: object) -> None:
        """Leave the synthetic supervision scope.

        Args:
            exc: Pending exception details (unused).

        """
        _ = exc


class SupervisorStub:
    """Stand-in for the real ``ProcessSupervisor``."""

    def __init__(self, **kwargs: object) -> None:
        """Accept every supervisor option without acting.

        Args:
            kwargs: Supervisor construction options (unused).

        """
        _ = kwargs

    @staticmethod
    def run() -> ResultStub:
        """Return a synthetic supervision result.

        Returns:
            The fixed stub result.

        """
        return ResultStub()


def test_example_module_runs_as_a_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the example file's ``__main__`` entry with stubbed processes.

    Args:
        monkeypatch: Pytest patching helper.

    """
    output: StringIO = StringIO()
    monkeypatch.setattr(
        target=guard_package,
        name="ProcessGuard",
        value=GuardStub,
    )
    monkeypatch.setattr(
        target=guard_package,
        name="ProcessSupervisor",
        value=SupervisorStub,
    )

    def fake_popen(*args: object, **kwargs: object) -> ProcessStub:
        """Return a synthetic child process.

        Args:
            args: Positional spawn arguments (unused).
            kwargs: Keyword spawn arguments (unused).

        Returns:
            The fixed process stub.

        """
        _ = args
        _ = kwargs
        return ProcessStub()

    monkeypatch.setattr(
        target=modules["subprocess"],
        name="Popen",
        value=fake_popen,
    )
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=output)
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(path_name=str(object=Constants.example), run_name="__main__")
    expect_equal(actual=raised.value.code, expected=0)
    rendered: str = output.getvalue()
    expect_in(member="in-process child started: 4242", container=rendered)
    expect_in(member="external nested tree", container=rendered)
    expect_in(member="exit-code preservation", container=rendered)
