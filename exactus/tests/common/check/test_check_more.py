# Copyright (c) 2026
"""Venv discovery, shortcut servers, and unified pipeline runs."""

from __future__ import annotations

from os import environ
from pathlib import Path
from typing import Final, final

import pytest

from exactus import __main__ as check
from exactus.__main__ import Check, main, project_interpreter
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    private_call,
    require,
)

pytestmark: pytest.MarkDecorator = pytest.mark.usefixtures("isolated_check")


@final
class Constants:
    """Group module-level constants.

    Attributes:
        root: Grouped module constant.
        demo: Grouped module constant.
        reshebang: Grouped module constant.

    """

    root: Final[Path] = Path(__file__).resolve().parents[4]
    demo: Final[Path] = root / "demo"
    reshebang: Final = staticmethod(Check.venv_reexec)


def _make_venv(root: Path, version: str, name: str = ".venv") -> Path:
    """Create a fake virtualenv under ``root``.

    Args:
        root: Project directory.
        version: Version recorded in ``pyvenv.cfg``.
        name: Directory name of the venv.

    Returns:
        The venv directory.

    """
    venv: Path = root / name
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text(
        data=f"version = {version}\n",
        encoding="utf-8",
    )
    (venv / "bin" / "python").write_text(data="", encoding="utf-8")
    return venv


def test_project_interpreter_discovery(tmp_path: Path) -> None:
    """Conventional and arbitrary venv names are discovered.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_none(value=project_interpreter(root=tmp_path))
    venv: Path = _make_venv(root=tmp_path, version="3.13.1", name="custom")
    found: tuple[Path, Path] | None = project_interpreter(root=tmp_path)
    found = require(value=found)
    expect_equal(actual=found[0], expected=venv)
    (venv / "bin" / "python").unlink()
    expect_none(value=project_interpreter(root=tmp_path))


def test_venv_version_parsing(tmp_path: Path) -> None:
    """Versions come from pyvenv.cfg when parseable.

    Args:
        tmp_path: Per-test temporary directory.

    """
    venv: Path = _make_venv(root=tmp_path, version="3.9.2")
    expect_equal(
        actual=private_call(owner=check, name="_venv_version", venv=venv),
        expected=(3, 9),
    )
    (venv / "pyvenv.cfg").write_text(data="version = x\n", encoding="utf-8")
    expect_none(
        value=private_call(owner=check, name="_venv_version", venv=venv),
    )
    expect_none(
        value=private_call(
            owner=check,
            name="_venv_version",
            venv=tmp_path / "none",
        ),
    )


def test_venv_reexec_old_python_exports_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An outdated project venv is exported for test subprocesses.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _make_venv(root=tmp_path, version="3.8.0")
    monkeypatch.delenv(name="VIRTUAL_ENV", raising=False)
    monkeypatch.setattr(target=Check, name="root", value=tmp_path)
    Constants.reshebang()
    expect_true(condition=environ["EXACTUS_PROJECT_PYTHON"].endswith("python"))


def test_venv_reexec_embedded_and_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedded use and an active venv never re-exec.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _make_venv(root=tmp_path, version="3.13.0")
    monkeypatch.setattr(target=Check, name="root", value=tmp_path)
    monkeypatch.setenv(name="VIRTUAL_ENV", value="/somewhere")
    Constants.reshebang()
    monkeypatch.delenv(name="VIRTUAL_ENV")
    Constants.reshebang()
    expect_true(condition=environ["EXACTUS_PROJECT_PYTHON"].endswith("python"))


def test_venv_reexec_spawns_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When run as the script itself, the venv interpreter is executed.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _make_venv(root=tmp_path, version="3.13.0")
    monkeypatch.delenv(name="VIRTUAL_ENV", raising=False)
    monkeypatch.setattr(target=Check, name="root", value=tmp_path)
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[check.__file__, "--list-tools"],
    )
    monkeypatch.setattr(target=check, name="prefix", value="/nowhere")

    class FakeProcess:
        """Stand-in for ``Popen`` that exits immediately."""

        def __init__(self, *, args: tuple[str, ...]) -> None:
            """Remember the command.

            Args:
                args: Spawned command line.

            """
            self.args = args

        @staticmethod
        def wait() -> int:
            """Return a fixed exit status.

            Returns:
                Zero.

            """
            return 7

    monkeypatch.setattr(target=check, name="Popen", value=FakeProcess)
    with pytest.raises(expected_exception=SystemExit) as caught:
        Constants.reshebang()
    expect_equal(actual=caught.value.code, expected=7)


def test_clear_conflict_copies(tmp_path: Path) -> None:
    """Numbered duplicates of artifacts are removed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    monkey_root: Path = tmp_path / "EXACTUS_RESULTS"
    (monkey_root / "LINTS").mkdir(parents=True)
    (monkey_root / "LINTS" / "result.md").write_text(
        data="a",
        encoding="utf-8",
    )
    (monkey_root / "LINTS" / "result 2.md").write_text(
        data="b",
        encoding="utf-8",
    )
    (monkey_root / "LINTS 2").mkdir()
    Check.use_root(root=tmp_path)
    _ = private_call(owner=Check, name="_clear_conflict_copies")
    expect_false(condition=(monkey_root / "LINTS" / "result 2.md").exists())
    expect_false(condition=(monkey_root / "LINTS 2").exists())
    expect_true(condition=(monkey_root / "LINTS" / "result.md").exists())


def test_unified_pipeline_subset(sample_project: Path) -> None:
    """The unified pipeline publishes its aggregate activity report.

    Args:
        sample_project: Generated sample project directory.

    """
    status: int = main(
        arguments=[
            "--root",
            str(object=sample_project),
            "--exclude-tools",
            "lints",
            "coverage_tests",
            "frontend",
        ],
    )
    expect_in(member=status, container={0, 1})
    unified: Path = (
        sample_project / "EXACTUS_RESULTS" / "PIPELINES" / "UNIFIED"
    )
    expect_true(condition=unified.is_dir())
    for name in ("@activity.json", "stderr.log"):
        expect_true(
            condition=(unified / "ARTIFACTS" / name).is_file(),
            message=name,
        )
    expect_false(condition=(unified / "ARTIFACTS" / "stderr.json").exists())
    expect_true(condition=(unified / "ARTIFACTS" / "owner.json").is_file())
    expect_false(
        condition=(sample_project / "EXACTUS_RESULTS" / "UNIFIED").exists(),
    )


def test_frontend_navigation_through_local_server(
    sample_project: Path,
    demo_url: str,
) -> None:
    """The frontend selector navigates to an explicitly managed local server.

    Args:
        sample_project: Generated project directory.
        demo_url: Fixture-owned local application URL.

    """
    status: int = main(
        arguments=[
            "--root",
            str(object=sample_project),
            "--frontend",
            "--url",
            demo_url,
        ],
    )
    expect_in(member=status, container={0, 1})


def test_application_startup_requires_actions() -> None:
    """Reject removed application startup shortcuts."""
    expect_equal(
        actual=main(arguments=["--entrypoint", "demo/server.py"]),
        expected=2,
    )


def test_history_backups_survive_cleanup_and_clear(tmp_path: Path) -> None:
    """Generated output cleanup preserves every archived backup byte.

    Args:
        tmp_path: Disposable project with backups and generated reports.

    """
    Check.use_root(root=tmp_path)
    backup: Path = Check.exactus_root / ".history" / "LINTS"
    backup.mkdir(parents=True)
    (backup / "result.md").write_text(data="original backup")
    duplicate: Path = backup / "result 2.md"
    duplicate.write_text(data="distinct backup")
    output: Path = Check.exactus_root / "LINTS"
    output.mkdir()
    (output / "result.md").write_text(data="generated")
    _ = private_call(owner=Check, name="_clear_conflict_copies")
    expect_equal(actual=duplicate.read_text(), expected="distinct backup")
    _ = private_call(owner=Check, name="_clear_all")
    expect_false(condition=output.exists())
    expect_equal(actual=duplicate.read_text(), expected="distinct backup")
    expect_equal(
        actual=(backup / "result.md").read_text(),
        expected="original backup",
    )
