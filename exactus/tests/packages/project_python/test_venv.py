# Copyright (c) 2026
"""Exercise the shared project virtual-environment bootstrap."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from runpy import run_path
from sys import modules
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages import project_python
from exactus.tests.common.support import (
    expect_equal,
    expect_true,
    private_result,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        repo: Grouped module constant.

    """

    repo: Final[Path] = Path(__file__).resolve().parents[4]


def test_switch_to_project_venv_reexecutes_with_original_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the local interpreter and preserve the requested command.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    interpreter: Path = project / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(data="")
    calls: list[tuple[str, list[str]]] = []

    def capture(path: str, arguments: list[str]) -> None:
        """Capture the process replacement request.

        Args:
            path: Interpreter path passed to ``os.execv``.
            arguments: Argument vector passed to ``os.execv``.

        """
        calls.append((path, arguments))

    monkeypatch.setattr(
        target=project_python.Constants,
        name="project_root",
        value=project,
    )
    monkeypatch.setattr(
        target=project_python,
        name="prefix",
        value=str(object=tmp_path / "system"),
    )
    monkeypatch.setattr(
        target=project_python,
        name="argv",
        value=["exactus/packages/package/build.py", "--tree"],
    )
    monkeypatch.setitem(
        dic=vars(project_python.import_module(name="os")),
        name="execv",
        value=capture,
    )
    project_python.switch_to_project_venv()
    expect_equal(
        actual=calls,
        expected=[
            (
                str(object=interpreter),
                [
                    str(object=interpreter),
                    "exactus/packages/package/build.py",
                    "--tree",
                ],
            ),
        ],
    )


def test_switch_to_project_venv_is_safe_without_a_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return when the environment is missing or already active.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []

    def capture_unexpected(_path: str, _arguments: list[str]) -> None:
        """Record an unexpected process replacement.

        Args:
            _path: Interpreter path passed to ``os.execv`` (unused).
            _arguments: Argument vector passed to ``os.execv`` (unused).

        """
        calls.append("called")

    monkeypatch.setattr(
        target=project_python.Constants,
        name="project_root",
        value=tmp_path,
    )
    monkeypatch.setitem(
        dic=vars(project_python.import_module(name="os")),
        name="execv",
        value=capture_unexpected,
    )
    project_python.switch_to_project_venv()
    environment: Path = tmp_path / ".venv"
    interpreter: Path = environment / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(data="")
    monkeypatch.setattr(
        target=project_python,
        name="prefix",
        value=str(object=environment),
    )
    project_python.switch_to_project_venv()
    expect_equal(actual=calls, expected=[])


def test_switch_to_project_venv_skips_multiprocessing_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker processes inherit a foreign ``sys.argv`` and must not re-execute.

    Spawned children see the parent's argument vector with ``argv[0]``
    rewritten to the parent's ``__main__`` module; replacing the worker with
    that program silently kills it before it can return a result.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    interpreter: Path = project / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(data="")
    calls: list[str] = []

    def capture_unexpected(_path: str, _arguments: list[str]) -> None:
        """Record an unexpected process replacement.

        Args:
            _path: Interpreter path passed to ``os.execv`` (unused).
            _arguments: Argument vector passed to ``os.execv`` (unused).

        """
        calls.append("called")

    monkeypatch.setattr(
        target=project_python.Constants,
        name="project_root",
        value=project,
    )
    monkeypatch.setattr(
        target=project_python,
        name="prefix",
        value=str(object=tmp_path / "system"),
    )
    monkeypatch.setattr(
        target=project_python,
        name="argv",
        value=[
            "/opt/anaconda3/lib/python3.13/site-packages/pytest/__main__.py",
            "exactus/tests/example/test_case.py::test_probe",
            "-q",
        ],
    )
    monkeypatch.setattr(
        target=project_python,
        name="parent_process",
        value=object,
    )
    monkeypatch.setitem(
        dic=vars(project_python.import_module(name="os")),
        name="execv",
        value=capture_unexpected,
    )
    project_python.switch_to_project_venv()
    expect_equal(actual=calls, expected=[])


def test_executable_tools_and_scripts_use_project_python() -> None:
    """Every executable Exactus/exactus/packages boundary uses the switch."""
    entries: list[Path] = [
        Constants.repo / "exactus" / "__main__.py",
        *sorted(
            (Constants.repo / "exactus" / "tools").glob(
                pattern="*/__main__.py",
            ),
        ),
        *sorted(
            (Constants.repo / "exactus" / "tools").glob(
                pattern="*/examples/__main__.py",
            ),
        ),
        Constants.repo
        / "exactus"
        / "tools"
        / "record"
        / "studio"
        / "__main__.py",
        *[
            path
            for path in sorted(
                (Constants.repo / "exactus" / "tools").glob(
                    pattern="*/main.py",
                ),
            )
            if 'if __name__ == "__main__"' in path.read_text(encoding="utf-8")
        ],
        Constants.repo / "exactus" / "packages" / "all_lints" / "__main__.py",
        Constants.repo
        / "exactus"
        / "packages"
        / "all_lints"
        / "examples"
        / "__main__.py",
        Constants.repo
        / "exactus"
        / "packages"
        / "group_final"
        / "__main__.py",
        Constants.repo
        / "exactus"
        / "packages"
        / "group_final"
        / "examples"
        / "__main__.py",
        Constants.repo / "exactus" / "packages" / "patcher" / "__main__.py",
        Constants.repo
        / "exactus"
        / "packages"
        / "patcher"
        / "examples"
        / "__main__.py",
    ]
    missing: list[str] = [
        path.relative_to(Constants.repo).as_posix()
        for path in entries
        if not any(
            marker in path.read_text(encoding="utf-8")
            for marker in (
                "switch_to_project_venv",
                "exactus.packages.project_python.auto",
                "exactus.packages.project_python import auto",
            )
        )
    ]
    expect_equal(actual=missing, expected=[])


def test_project_root_falls_back_to_package_grandparent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the package grandparent when no ancestor owns ``.venv``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    module_file: Path = tmp_path / "deep" / "pkg" / "module.py"

    def _fixed_path(*_ignored: object) -> Path:
        """Return the prepared module file for every lookup.

        Args:
            _ignored: Constructor arguments (unused).

        Returns:
            The prepared module file.

        """
        return module_file

    monkeypatch.setattr(target=project_python, name="Path", value=_fixed_path)
    result: Path = private_result(
        owner=project_python,
        name="_project_root",
        kind=Path,
    )
    expect_equal(actual=result, expected=tmp_path / "deep")


def test_switch_returns_when_argv_has_no_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skip replacement for interpreter-only invocations like ``-c``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    interpreter: Path = project / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(data="")
    calls: list[str] = []

    def capture_unexpected(_path: str, _arguments: list[str]) -> None:
        """Record an unexpected process replacement.

        Args:
            _path: Interpreter path passed to ``os.execv`` (unused).
            _arguments: Argument vector passed to ``os.execv`` (unused).

        """
        calls.append("called")

    monkeypatch.setattr(
        target=project_python.Constants,
        name="project_root",
        value=project,
    )
    monkeypatch.setattr(
        target=project_python,
        name="prefix",
        value=str(object=tmp_path / "system"),
    )
    monkeypatch.setattr(
        target=project_python,
        name="argv",
        value=["-c", "print(1)"],
    )
    monkeypatch.setitem(
        dic=vars(project_python.import_module(name="os")),
        name="execv",
        value=capture_unexpected,
    )
    project_python.switch_to_project_venv()
    expect_equal(actual=calls, expected=[])


def test_switch_resolves_program_through_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a bare command name through ``PATH`` before replacing.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    project: Path = tmp_path / "project"
    interpreter: Path = project / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text(data="")
    program: Path = tmp_path / "bin" / "tool"
    program.parent.mkdir()
    _ = program.write_text(data="")
    calls: list[tuple[str, list[str]]] = []

    def capture(path: str, arguments: list[str]) -> None:
        """Capture the process replacement request.

        Args:
            path: Interpreter path passed to ``os.execv``.
            arguments: Argument vector passed to ``os.execv``.

        """
        calls.append((path, arguments))

    monkeypatch.setattr(
        target=project_python.Constants,
        name="project_root",
        value=project,
    )
    monkeypatch.setattr(
        target=project_python,
        name="prefix",
        value=str(object=tmp_path / "system"),
    )
    monkeypatch.setattr(
        target=project_python,
        name="argv",
        value=["tool", "--flag"],
    )

    def _found_program(*_ignored: object, **_named: object) -> str:
        """Resolve the prepared program path for every name.

        Args:
            _ignored: Positional arguments (unused).
            _named: Keyword arguments (unused).

        Returns:
            The prepared program path.

        """
        return str(object=program)

    monkeypatch.setattr(
        target=project_python,
        name="which",
        value=_found_program,
    )
    monkeypatch.setitem(
        dic=vars(project_python.import_module(name="os")),
        name="execv",
        value=capture,
    )
    project_python.switch_to_project_venv()
    expect_equal(
        actual=calls,
        expected=[
            (
                str(object=interpreter),
                [str(object=interpreter), str(object=program), "--flag"],
            ),
        ],
    )


def test_main_module_runs_the_requested_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fall back to the unqualified import and ``run_path`` the script.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    marker: Path = tmp_path / "marker.txt"
    script: Path = tmp_path / "task.py"
    _ = script.write_text(
        data=(
            "from pathlib import Path\n"
            f'Path({str(object=marker)!r}).write_text("ran")\n'
        ),
        encoding="utf-8",
    )
    real_import: Callable[..., ModuleType] = import_module

    def fail_primary(name: str, package: str | None = None) -> ModuleType:
        """Fail only the qualified ``exactus.packages.project_python`` lookup.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The real import result for every other candidate.

        Raises:
            ImportError: For the qualified
                ``exactus.packages.project_python`` name.

        """
        if name == "exactus.packages.project_python":
            raise ImportError(name)
        return real_import(name, package=package)

    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=fail_primary,
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=["project_python", str(object=script)],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(
                object=(
                    Constants.repo
                    / "exactus"
                    / "packages"
                    / "project_python"
                    / "__main__.py"
                ),
            ),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)
    expect_true(condition=marker.is_file())
