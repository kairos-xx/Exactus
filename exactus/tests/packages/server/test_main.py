# Copyright (c) 2026
"""Cover the ``exactus.packages.server`` command-line entry point."""

from __future__ import annotations

from importlib import import_module
from io import StringIO
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from types import ModuleType
import pytest

from exactus.packages.server import local, process_control
from exactus.tests.common.support import expect_equal

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Constants:
    """Group module-level constants.

    Attributes:
        main_module: Grouped module constant.

    """

    main_module: Final[Path] = (
        Path(__file__).resolve().parents[4]
        / "exactus"
        / "packages"
        / "server"
        / "__main__.py"
    )


def _run_main_module(
    *,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    fail_bootstrap: bool = False,
) -> int:
    """Execute the server entry point with a synthetic command line.

    Args:
        monkeypatch: Pytest patching helper.
        argv: Replacement ``sys.argv`` for the module's ``main``.
        fail_bootstrap: Whether the project-venv import must fail.

    Returns:
        The ``SystemExit`` status raised by the entry point.

    """
    real_import: Callable[..., ModuleType] = import_module

    def maybe_fail(name: str, package: str | None = None) -> ModuleType:
        """Optionally reject the ``exactus.packages.project_python`` lookup.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result.

        Raises:
            ImportError: When ``fail_bootstrap`` rejects this candidate.

        """
        if fail_bootstrap and name == "exactus.packages.project_python":
            raise ImportError(name)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=maybe_fail,
    )
    monkeypatch.setattr(target=modules["sys"], name="argv", value=argv)
    monkeypatch.setattr(target=modules["sys"], name="stdout", value=StringIO())
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.main_module),
            run_name="__main__",
        )
    return int(str(object=raised.value.code))


def test_main_falls_back_to_the_unqualified_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Use ``project_python`` when the qualified import is unavailable.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    status: int = _run_main_module(
        monkeypatch=monkeypatch,
        argv=["server", str(object=tmp_path), "--stop"],
        fail_bootstrap=True,
    )
    expect_equal(actual=status, expected=1)


def test_main_stop_reports_missing_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--stop`` returns one when no server recorded its state.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """

    def _no_server(**_ignored: object) -> None:
        """Report that no recorded server exists.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(target=local, name="reuse_server", value=_no_server)
    status: int = _run_main_module(
        monkeypatch=monkeypatch,
        argv=["server", str(object=tmp_path), "--stop"],
    )
    expect_equal(actual=status, expected=1)


def test_main_stop_terminates_a_recorded_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--stop`` terminates the adopted server and clears its state.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    terminated: list[int] = []
    cleared: list[Path] = []

    def _record_clear(*, path: Path) -> None:
        """Record the cleared server directory.

        Args:
            path: Served root directory.

        """
        cleared.append(path)

    def _recorded_server(**_ignored: object) -> tuple[int, int]:
        """Return the recorded process and port pair.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            The synthetic process id and port.

        """
        return (4321, 9876)

    monkeypatch.setattr(
        target=local,
        name="reuse_server",
        value=_recorded_server,
    )

    def _record_termination(*, pid: int, **_ignored: object) -> None:
        """Record the terminated process id.

        Args:
            pid: Process id to terminate.
            _ignored: Extra keyword arguments (unused).

        """
        terminated.append(pid)

    monkeypatch.setattr(
        target=process_control,
        name="terminate_tree",
        value=_record_termination,
    )
    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=_record_clear,
    )
    status: int = _run_main_module(
        monkeypatch=monkeypatch,
        argv=["server", str(object=tmp_path), "--stop"],
    )
    expect_equal(actual=status, expected=0)
    expect_equal(actual=terminated, expected=[4321])
    expect_equal(actual=cleared, expected=[tmp_path])


def test_main_serve_reports_a_server_that_never_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Return one when the spawned server never accepts connections.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """

    def _fake_serve(**_ignored: object) -> tuple[int, str, bool]:
        """Return a synthetic spawned server triple.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            Process id, loopback URL, and adoption flag.

        """
        return (4321, "http://127.0.0.1:9876/", False)

    monkeypatch.setattr(target=local, name="serve", value=_fake_serve)

    def _never_ready(**_ignored: object) -> bool:
        """Report the server as never ready.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            Always ``False``.

        """
        return False

    monkeypatch.setattr(target=local, name="wait_ready", value=_never_ready)

    def _no_termination(**_ignored: object) -> None:
        """Accept termination requests without acting.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(
        target=process_control,
        name="terminate_tree",
        value=_no_termination,
    )

    def _clear_nothing(**_ignored: object) -> None:
        """Accept state-clearing requests without acting.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=_clear_nothing,
    )
    status: int = _run_main_module(
        monkeypatch=monkeypatch,
        argv=["server", str(object=tmp_path)],
    )
    expect_equal(actual=status, expected=1)


def test_main_serve_blocks_until_signaled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Serve until the installed signal handler releases the wait loop.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """

    def _fake_serve(**_ignored: object) -> tuple[int, str, bool]:
        """Return a synthetic spawned server triple.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            Process id, loopback URL, and adoption flag.

        """
        return (4321, "http://127.0.0.1:9876/", False)

    monkeypatch.setattr(target=local, name="serve", value=_fake_serve)

    def _ready(**_ignored: object) -> bool:
        """Report the server as immediately ready.

        Args:
            _ignored: Keyword arguments (unused).

        Returns:
            Always ``True``.

        """
        return True

    monkeypatch.setattr(target=local, name="wait_ready", value=_ready)

    def _no_termination(**_ignored: object) -> None:
        """Accept termination requests without acting.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(
        target=process_control,
        name="terminate_tree",
        value=_no_termination,
    )

    def _clear_nothing(**_ignored: object) -> None:
        """Accept state-clearing requests without acting.

        Args:
            _ignored: Keyword arguments (unused).

        """
        return

    monkeypatch.setattr(
        target=local,
        name="clear_server_state",
        value=_clear_nothing,
    )

    def install_and_fire(
        *,
        signalnum: int,
        handler: Callable[[int, object], None],
    ) -> object:
        """Invoke the installed handler immediately.

        Args:
            signalnum: Registered signal number.
            handler: Handler installed by ``main``.

        Returns:
            The previous handler placeholder.

        """
        handler(signalnum, None)
        return None

    monkeypatch.setattr(
        target=modules["signal"],
        name="signal",
        value=install_and_fire,
    )
    status: int = _run_main_module(
        monkeypatch=monkeypatch,
        argv=["server", str(object=tmp_path)],
    )
    expect_equal(actual=status, expected=0)
