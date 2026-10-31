# Copyright (c) 2026
"""Cover the ``exactus.packages.screenshot`` command-line entry point."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from runpy import run_path
from sys import modules
from types import ModuleType
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import expect_equal, set_private

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
        / "screenshot"
        / "__main__.py"
    )


@dataclass(frozen=True, slots=True)
class _Spec:
    """Stand-in for the real ``CaptureSpec`` dataclass.

    Attributes:
        path: Requested output file.
        width: Requested viewport width.
        height: Requested viewport height.

    """

    path: Path
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class _Capture:
    """Stand-in for the real ``Capture`` result.

    Attributes:
        path: Written capture file.

    """

    path: Path


class _Screenshot:
    """Stand-in for the browser-backed ``Screenshot`` class."""

    @staticmethod
    async def capture(*, url: str, target: str, spec: _Spec) -> _Capture:
        """Return a synthetic capture without launching a browser.

        Args:
            url: Requested URL (unused).
            target: Requested selector (unused).
            spec: Recorded capture specification.

        Returns:
            A capture carrying the requested output path.

        """
        _ = (url, target)
        return _Capture(path=spec.path)


def _screenshot_module() -> ModuleType:
    """Build the stub ``exactus.packages.screenshot`` module namespace.

    Returns:
        Module exposing stub ``CaptureSpec`` and ``Screenshot`` attributes.

    """
    stub: ModuleType = ModuleType(name="exactus.packages.screenshot")
    set_private(owner=stub, name="CaptureSpec", value=_Spec)
    set_private(owner=stub, name="Screenshot", value=_Screenshot)
    return stub


def test_main_captures_through_the_stubbed_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive ``main`` end to end with the screenshot package stubbed.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest patching helper.

    """
    real_import: Callable[..., ModuleType] = import_module
    stub: ModuleType = _screenshot_module()

    def route(name: str, package: str | None = None) -> ModuleType:
        """Return the stub for ``exactus.packages.screenshot`` lookups.

        Args:
            name: Requested module name.
            package: Anchor package for relative imports.

        Returns:
            The stub module or the real import result.

        Raises:
            ImportError: When the primary venv candidate is requested.

        """
        if name == "exactus.packages.screenshot":
            return stub
        if name == "exactus.packages.project_python":
            raise ImportError(name)
        return real_import(name, package=package)

    output: Path = tmp_path / "shot.png"
    monkeypatch.setattr(
        target=modules["importlib"],
        name="import_module",
        value=route,
    )
    monkeypatch.setattr(
        target=modules["sys"],
        name="argv",
        value=[
            "screenshot",
            "https://example.test/",
            "--output",
            str(object=output),
        ],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_path(
            path_name=str(object=Constants.main_module),
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=0)
