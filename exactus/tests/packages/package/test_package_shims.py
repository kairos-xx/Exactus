"""Tests for generated bundled-distribution import shims."""

from __future__ import annotations

from os import environ
from sys import modules
from typing import TYPE_CHECKING, cast

from coverage.collector import Collector

from exactus.packages.package import shims
from exactus.packages.package.shims import public_names
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    private,
    private_as,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


def test_public_names_drops_startup_hook_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``pth_file``-style startup hooks are never shimmed or probed.

    Startup-hook modules exist to run at interpreter startup; collecting
    shim names must neither execute nor re-export them.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    package: Path = tmp_path / "hookpkg"
    package.mkdir()
    package.joinpath("__init__.py").write_text(data="")
    package.joinpath("helper.py").write_text(data="VALUE = 1\n")
    package.joinpath("pth_file.py").write_text(
        data='raise RuntimeError("startup hook imported")\n',
    )
    syspath_prepend: Callable[..., None] = cast(
        typ="Callable[..., None]",
        val=private(owner=monkeypatch, name="syspath_prepend"),
    )
    syspath_prepend(path=str(object=tmp_path))
    names: list[str] | None = public_names(module="hookpkg")
    expect_in(member="helper", container=names or [])
    expect_not_in(member="pth_file", container=names or [])
    expect_not_in(member="hookpkg.pth_file", container=modules)


def test_quiet_probe_drops_coverage_process_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Probing ``coverage.pth_file`` cannot start a nested collector.

    ``coverage run`` parents export ``COVERAGE_PROCESS_START`` for
    subprocess patching; an in-process probe of that hook must not start
    a second collector whose leftover state destroys the outer run's
    data at exit.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    monkeypatch.delitem(dic=modules, name="coverage.pth_file", raising=False)
    rcfile: str = str(object=tmp_path / "coveragerc")
    monkeypatch.setenv(name="COVERAGE_PROCESS_START", value=rcfile)
    collectors: list[object] = cast(
        typ="list[object]",
        val=private_as(owner=Collector, name="_collectors", kind=list),
    )
    before: int = len(collectors)
    quiet_probe: Callable[..., bool] = cast(
        typ="Callable[..., bool]",
        val=private(owner=shims, name="_quiet"),
    )
    quiet: bool = quiet_probe(
        action="module",
        imported=None,
        name="coverage.pth_file",
    )
    expect_true(condition=quiet)
    expect_equal(actual=len(collectors), expected=before)
    expect_equal(actual=environ.get("COVERAGE_PROCESS_START"), expected=rcfile)
