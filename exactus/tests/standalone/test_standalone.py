"""Run the system ``exactus`` executable over the standalone project."""

from __future__ import annotations

from os import environ
from pathlib import Path
from shutil import which
from subprocess import CompletedProcess
from subprocess import run as subprocess_run
from typing import Final, final

import pytest

from exactus.bundle.freshness import bundle_stale
from exactus.packages.package.install import Constants as InstallConstants
from exactus.packages.package.install import (
    build_release,
    host_platform,
    release_name,
)
from exactus.tests.common.support import expect_true


@final
class Constants:
    """Group module-level constants.

    Attributes:
        run_timeout_seconds: Grouped module constant.
        stripped_prefixes: Grouped module constant.
        repository_root: Grouped module constant.
        project_root: Grouped module constant.

    """

    run_timeout_seconds: Final[int] = 1800
    stripped_prefixes: Final[tuple[str, ...]] = (
        "EXACTUS_",
        "COVERAGE_",
        "PYTEST_",
        "PYTHONPATH",
    )
    repository_root: Final[Path] = Path(__file__).resolve().parents[3]
    project_root: Final[Path] = Path(__file__).resolve().parent / "project"


def _current(*, bundle: Path) -> bool:
    """Report whether a bundle already stamps the live source tree.

    Args:
        bundle: The bundle path to check.

    Returns:
        True if the bundle is current, False otherwise.

    """
    return bundle.is_file() and (
        not bundle_stale(
            bundle=bundle,
            exactus_dir=Constants.repository_root / "exactus",
        )
    )


def _exactus_command() -> tuple[str, ...] | None:
    """Resolve a fresh ``exactus`` executable, rebuilding when stale.

    A system-wide install wins when it still matches the live sources;
    otherwise the platform release under ``bin/`` is used or rebuilt.

    Returns:
        The executable invocation, or ``None`` when the platform
        cannot provide one.

    """
    found: str | None = which(cmd="exactus")
    if found is not None and _current(bundle=Path(found)):
        return (found,)
    try:
        system, architecture = host_platform()
    except ValueError:
        return None
    artifact: Path = (
        InstallConstants.bin_dir
        / release_name(system=system, architecture=architecture)
        / InstallConstants.command_name
    )
    if not _current(bundle=artifact):
        artifact = build_release(system=system, architecture=architecture)
    return (str(object=artifact),)


def test_system_exactus_audits_standalone_project() -> None:
    """``exactus`` produces ``EXACTUS_RESULTS`` inside the project."""
    command: tuple[str, ...] | None = _exactus_command()
    if command is None:
        pytest.skip(reason="no installable exactus executable")
    project: Path = Constants.project_root
    child_env: dict[str, str] = {
        key: value
        for key, value in environ.items()
        if not key.startswith(Constants.stripped_prefixes)
    }
    result: CompletedProcess[str] = subprocess_run(
        check=False,
        args=[*command, "--root", str(object=project)],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=Constants.run_timeout_seconds,
        env=child_env,
    )
    reports: Path = project / "EXACTUS_RESULTS"
    expect_true(
        condition=result.returncode == 0,
        message=result.stdout[-2000:] + result.stderr[-2000:],
    )
    expect_true(
        condition=reports.is_dir(),
        message=result.stdout[-2000:] + result.stderr[-2000:],
    )
    results: list[Path] = sorted(reports.rglob(pattern="result.md"))
    expect_true(
        condition=bool(results),
        message="no result.md reports were produced",
    )
