# Copyright (c) 2026
"""Exercise the packaged virtual-environment shebang updater."""

from __future__ import annotations

from importlib import import_module
from io import StringIO
from runpy import run_path
from sys import modules, path
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.packages import project_python
from exactus.packages.shebang_update import Settings, ShebangUpdater, core
from exactus.tests.common.support import expect_equal, expect_in, expect_none

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
importlib: ModuleType = __import__("importlib")
sys: ModuleType = __import__("sys")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        stale: Grouped module constant.
        body: Grouped module constant.

    """

    stale: Final[bytes] = (
        b"#!/previous/checkout/demo_project/.venv/bin/python3\n"
    )
    body: Final[bytes] = b"print('demo')\n"


def _project(*, tmp_path: Path) -> Path:
    """Create a project root containing an empty ``.venv/bin``.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        The created project root.

    """
    root: Path = tmp_path / "project"
    (root / ".venv" / "bin").mkdir(parents=True)
    return root


def test_settings_builds_the_project_interpreter_shebang(
    tmp_path: Path,
) -> None:
    """Render the absolute shebang for the configured environment.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    expect_equal(
        actual=Settings(root=root).shebang,
        expected=f"#!{(root / '.venv/bin/python').resolve()}".encode(),
    )
    custom: Settings = Settings(
        root=root,
        virtual_environment="env",
        python_executable="bin/python3",
    )
    expect_equal(
        actual=custom.shebang,
        expected=f"#!{(root / 'env/bin/python3').resolve()}".encode(),
    )


def test_run_rewrites_a_stale_shebang(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rewrite the first line and preserve the remainder of the file.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(tmp_path=tmp_path)
    script: Path = root / "tools" / "build.py"
    script.parent.mkdir(parents=True)
    _ = script.write_bytes(data=Constants.stale + Constants.body)
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=core, name="stdout", value=sink)
    updated: int = ShebangUpdater(settings=Settings(root=root)).run()
    expect_equal(actual=updated, expected=1)
    expected: str = Settings(root=root).shebang.decode()
    expect_equal(
        actual=script.read_bytes(),
        expected=(expected + "\n").encode() + Constants.body,
    )
    output: str = sink.getvalue()
    expect_in(member="tools/build.py", container=output)
    expect_in(member="#!/previous/checkout", container=output)
    expect_in(member=f"-> {expected}", container=output)


def test_run_skips_files_inside_the_environment(tmp_path: Path) -> None:
    """Leave files below ``.venv`` untouched even when stale.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    inside: Path = root / ".venv" / "bin" / "activate.py"
    _ = inside.write_bytes(data=Constants.stale + Constants.body)
    expect_equal(
        actual=ShebangUpdater(settings=Settings(root=root)).run(),
        expected=0,
    )
    expect_equal(
        actual=inside.read_bytes(),
        expected=Constants.stale + Constants.body,
    )


def test_run_ignores_non_matching_first_lines(tmp_path: Path) -> None:
    """Skip files without an absolute venv Python shebang.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    cases: dict[str, bytes] = {
        "env.py": b"#!/usr/bin/env python3\n",
        "relative.py": b"#!.venv/bin/python\n",
        "other.py": b"#!/opt/other/bin/python\n",
        "nested.py": b"#!/x/.venv/bin/python/other\n",
        "plain.txt": b"no shebang\n",
    }
    for name, content in cases.items():
        _ = (root / name).write_bytes(data=content)
    expect_equal(
        actual=ShebangUpdater(settings=Settings(root=root)).run(),
        expected=0,
    )
    for name, content in cases.items():
        expect_equal(actual=(root / name).read_bytes(), expected=content)


def test_run_leaves_current_shebangs_unchanged(tmp_path: Path) -> None:
    """Skip files already carrying the expected shebang, including CRLF.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    expected: bytes = Settings(root=root).shebang
    lf: bytes = expected + b"\n" + Constants.body
    crlf: bytes = expected + b"\r\n" + Constants.body
    _ = (root / "lf.py").write_bytes(data=lf)
    _ = (root / "crlf.py").write_bytes(data=crlf)
    expect_equal(
        actual=ShebangUpdater(settings=Settings(root=root)).run(),
        expected=0,
    )
    expect_equal(actual=(root / "lf.py").read_bytes(), expected=lf)
    expect_equal(actual=(root / "crlf.py").read_bytes(), expected=crlf)


def test_run_survives_unwritable_files(tmp_path: Path) -> None:
    """Return ``False`` from the update when the rewrite is refused.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = _project(tmp_path=tmp_path)
    script: Path = root / "locked.py"
    _ = script.write_bytes(data=Constants.stale + Constants.body)
    script.chmod(mode=292)
    try:
        updated: int = ShebangUpdater(settings=Settings(root=root)).run()
    finally:
        script.chmod(mode=420)
    expect_equal(actual=updated, expected=0)
    expect_equal(
        actual=script.read_bytes(),
        expected=Constants.stale + Constants.body,
    )


def test_run_reports_zero_for_an_empty_project(tmp_path: Path) -> None:
    """Walk a tree without candidates without changing anything.

    Args:
        tmp_path: Pytest temporary directory.

    """
    root: Path = tmp_path / "empty"
    root.mkdir()
    expect_equal(
        actual=ShebangUpdater(settings=Settings(root=root)).run(),
        expected=0,
    )


def test_core_module_runs_main_as_a_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute ``core.py`` with ``__name__`` equal to ``__main__``.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    _ = run_path(path_name=str(object=core.__file__), run_name="__main__")


def test_main_updates_the_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scan the current directory and report singular and plural counts.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    root: Path = _project(tmp_path=tmp_path)
    _ = (root / "cli.py").write_bytes(data=Constants.stale + Constants.body)
    sink: StringIO = StringIO()
    monkeypatch.setattr(target=core, name="stdout", value=sink)
    monkeypatch.chdir(path=root)
    expect_none(value=core.main())
    expect_in(member="Updated 1 file.", container=sink.getvalue())
    expect_none(value=core.main())
    expect_in(member="Updated 0 files.", container=sink.getvalue())


def test_main_module_switches_interpreter_and_invokes_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switch to the project interpreter, then delegate to ``main``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []
    monkeypatch.setattr(
        target=project_python,
        name="switch_to_project_venv",
        value=lambda: calls.append("switch"),
    )
    monkeypatch.setitem(
        dic=modules,
        name="shebang_update",
        value=SimpleNamespace(main=lambda: calls.append("main")),
    )
    monkeypatch.setattr(target=sys, name="path", value=[*path])
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = import_module(name="exactus.packages.shebang_update.__main__")
    expect_none(value=captured.value.code)
    expect_equal(actual=calls, expected=["switch", "main"])


def test_main_module_runs_without_a_bootstrap_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skip the interpreter switch when ``project_python`` is absent.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[str] = []
    real_import: Callable[..., ModuleType] = import_module

    def refuse_bootstrap(name: str, package: str | None = None) -> ModuleType:
        """Reject only the interpreter-switch candidate imports.

        Args:
            name: Module the caller asked to import.
            package: Anchor for relative imports (unused).

        Returns:
            The imported module for every other name.

        Raises:
            ImportError: When ``name`` is an interpreter-switch candidate.

        """
        del package
        if name in ("exactus.packages.project_python", "project_python"):
            raise ImportError(name)
        return real_import(name)

    monkeypatch.setattr(
        target=importlib,
        name="import_module",
        value=refuse_bootstrap,
    )
    monkeypatch.setitem(
        dic=modules,
        name="shebang_update",
        value=SimpleNamespace(main=lambda: calls.append("main")),
    )
    monkeypatch.setattr(target=sys, name="path", value=[*path])
    with pytest.raises(expected_exception=SystemExit) as captured:
        _ = real_import(name="exactus.packages.shebang_update.__main__")
    expect_none(value=captured.value.code)
    expect_equal(actual=calls, expected=["main"])
