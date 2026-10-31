# Copyright (c) 2026
"""``pyproject.toml`` settings reaching standalone tools and ``check``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.__main__ import main
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tools.coverage_tests.main import parse_args

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        gate: Grouped module constant.
        zero_gate: Grouped module constant.

    """

    gate: Final[str] = "[tool.exactus.coverage_tests]\nfail-under = 77\n"
    zero_gate: Final[str] = (
        "[tool.exactus.coverage_tests]\nfail-under = 0\nminimum = 0\n"
    )


def _project_with(*, directory: Path, text: str) -> None:
    """Write a ``pyproject.toml`` holding ``text``.

    Args:
        directory: Project directory.
        text: TOML document.

    """
    _ = (directory / "pyproject.toml").write_text(data=text, encoding="utf-8")


def test_standalone_tool_reads_pyproject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A standalone tool picks up its table; the CLI still wins.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _project_with(directory=tmp_path, text=Constants.gate)
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED", raising=False)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    expect_equal(actual=parse_args(arguments=()).fail_under, expected=77.0)
    expect_equal(
        actual=parse_args(arguments=("--fail-under", "50")).fail_under,
        expected=50.0,
    )
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="off")
    expect_equal(actual=parse_args(arguments=()).fail_under, expected=90.0)


def test_context_lines_from_pyproject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read ``context-lines`` from the canonical coverage configuration.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _project_with(
        directory=tmp_path,
        text="[tool.exactus.coverage_tests]\ncontext-lines = 5\n",
    )
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED", raising=False)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    expect_equal(actual=parse_args(arguments=()).context_lines, expected=5)
    expect_equal(
        actual=parse_args(arguments=("--context-lines", "0")).context_lines,
        expected=0,
    )


def test_orchestrated_tool_skips_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under ``check`` the tool does not apply config a second time.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _project_with(directory=tmp_path, text=Constants.gate)
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    expect_equal(actual=parse_args(arguments=()).fail_under, expected=90.0)


def test_standalone_config_error_exits_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A bad key stops the tool with status 2 and names the key.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.
        capsys: Pytest output capture fixture.

    """
    _project_with(
        directory=tmp_path,
        text="[tool.exactus.coverage_tests]\nfail-undr = 1\n",
    )
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED", raising=False)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    with pytest.raises(expected_exception=SystemExit) as caught:
        _ = parse_args(arguments=())
    expect_equal(actual=caught.value.code, expected=2)
    expect_equal(actual="fail-undr" in capsys.readouterr().err, expected=True)


@pytest.mark.usefixtures("isolated_check")
def test_check_single_tool_uses_pyproject_gate(sample_project: Path) -> None:
    """``check --coverage`` (alias) honors the legacy ``fail-under``.

    The sample project covers well under the built-in 90% gate, so a pass
    can only come from the ``pyproject.toml`` value.

    Args:
        sample_project: Generated sample project directory.

    """
    settings: Path = sample_project / "pyproject.toml"
    original: str = (
        settings.read_text(encoding="utf-8") if settings.exists() else ""
    )
    _project_with(
        directory=sample_project,
        text=original + "\n" + Constants.zero_gate,
    )
    root: list[str] = [
        "--root",
        str(object=sample_project),
        "--coverage_tests",
    ]
    expect_equal(actual=main(arguments=root), expected=0)
    expect_equal(
        actual=main(arguments=[*root, "--fail-under", "100"]),
        expected=1,
    )


@pytest.mark.usefixtures("isolated_check")
def test_check_reports_config_errors(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid key stops ``check`` with status 2 before any tool runs.

    Args:
        sample_project: Generated sample project directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="")
    _project_with(
        directory=sample_project,
        text="[tool.exactus.coverage_tests]\nfail-undr = 1\n",
    )
    status: int = main(
        arguments=["--root", str(object=sample_project), "--coverage_tests"],
    )
    expect_equal(actual=status, expected=2)


@pytest.mark.usefixtures("isolated_check")
def test_no_config_and_explicit_config(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-config`` restores the built-in gate; ``--config`` selects a file.

    Args:
        sample_project: Generated sample project directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="")
    _project_with(directory=sample_project, text=Constants.zero_gate)
    root: list[str] = [
        "--root",
        str(object=sample_project),
        "--coverage_tests",
    ]
    expect_equal(actual=main(arguments=root), expected=0)
    expect_equal(actual=main(arguments=[*root, "--no-config"]), expected=1)
    other: Path = sample_project / "other.toml"
    _ = other.write_text(data=Constants.zero_gate, encoding="utf-8")
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="")
    _ = (sample_project / "pyproject.toml").unlink()
    expect_equal(actual=main(arguments=root), expected=1)
    expect_equal(
        actual=main(arguments=[*root, "--config", str(object=other)]),
        expected=0,
    )


@pytest.mark.usefixtures("isolated_check")
def test_orchestrator_settings_apply_to_pipeline_style_runs(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config ``clear`` runs for ``-t``; info flags and bad servers do not.

    Args:
        sample_project: Generated sample project directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="")
    _project_with(
        directory=sample_project,
        text="[tool.exactus]\nclear = true\n",
    )
    marker: Path = sample_project / "EXACTUS_RESULTS" / "marker.txt"
    marker.parent.mkdir(parents=True)
    _ = marker.write_text(data="x", encoding="utf-8")
    root: list[str] = ["--root", str(object=sample_project)]
    expect_equal(actual=main(arguments=[*root, "--list-tools"]), expected=0)
    expect_true(condition=marker.exists())
    status: int = main(arguments=[*root, "-t", "readme"])
    expect_in(member=status, container={0, 1})
    expect_false(condition=marker.exists())


@pytest.mark.usefixtures("isolated_check")
def test_show_config_exits_cleanly(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--show-config`` reports and exits ``0`` without running tools.

    Args:
        sample_project: Generated sample project directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setenv(name="EXACTUS_CONFIG", value="")
    _project_with(directory=sample_project, text=Constants.zero_gate)
    status: int = main(
        arguments=[
            "--root",
            str(object=sample_project),
            "--show-config",
            "-t",
            "coverage_tests",
        ],
    )
    expect_equal(actual=status, expected=0)
    expect_false(condition=(sample_project / "EXACTUS_RESULTS").exists())
