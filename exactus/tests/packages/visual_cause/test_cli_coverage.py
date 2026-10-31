# Copyright (c) 2026
"""Coverage for command entry points."""

from pathlib import Path
from runpy import run_module

import pytest

from exactus.packages.visual_cause import Settings, analyzer, dom_diff
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    private_result,
)


def test_settings_parses_valid_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parse all principal command-line scalar settings.

    Args:
        tmp_path: Test fixture or input value.
        monkeypatch: Test fixture or input value.

    """
    a: Path = tmp_path / "a.css"
    b: Path = tmp_path / "b.css"
    a.write_text(data="a{}", encoding="utf-8")
    b.write_text(data="b{}", encoding="utf-8")
    monkeypatch.setattr(
        target="sys.argv",
        name=[
            "visual_cause",
            "https://example.test/",
            str(object=a),
            str(object=b),
            "--width",
            "640",
            "--height",
            "480",
            "--threshold",
            "4",
            "--max-candidates",
            "3",
            "--timeout-ms",
            "900",
            "--screenshot-scale",
            "3",
        ],
    )
    settings: Settings = private_result(analyzer, "_settings", Settings)
    expect_equal(actual=settings.width, expected=640)
    expect_equal(actual=settings.height, expected=480)
    expect_equal(actual=settings.threshold, expected=4)
    expect_equal(actual=settings.screenshot_scale, expected=3.0)


def test_settings_rejects_invalid_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject invalid positive-dimension constraints.

    Args:
        tmp_path: Test fixture or input value.
        monkeypatch: Test fixture or input value.

    """
    a: Path = tmp_path / "a.css"
    b: Path = tmp_path / "b.css"
    a.write_text(data="a{}", encoding="utf-8")
    b.write_text(data="b{}", encoding="utf-8")
    monkeypatch.setattr(
        target="sys.argv",
        name=[
            "visual_cause",
            "https://example.test/",
            str(object=a),
            str(object=b),
            "--width",
            "0",
        ],
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="must be positive",
    ):
        private_result(analyzer, "_settings", Settings)


def test_module_entrypoint_calls_analyzer_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the visual-cause package entry-point semantics.

    Args:
        monkeypatch: Test fixture or input value.

    """
    called: list[bool] = []

    def record_main() -> None:
        """Record the analyzer entry-point invocation."""
        called.append(True)

    monkeypatch.setattr(target=analyzer, name="main", value=record_main)
    with pytest.raises(expected_exception=SystemExit) as captured:
        run_module(
            mod_name="exactus.packages.visual_cause.__main__",
            run_name="__main__",
        )
    expect_equal(actual=captured.value.code, expected=None)
    expect_equal(actual=called, expected=[True])


def test_module_entrypoint_dispatches_dom_diff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Execute the generic two-URL comparison command mode.

    Args:
        monkeypatch: Test fixture or input value.

    """
    captured: list[list[str] | None] = []

    def record_main(*, arguments: list[str] | None = None) -> int:
        """Record the generic-diff entry-point arguments.

        Args:
            arguments: Arguments after the ``dom-diff`` command.

        Returns:
            Successful process status.

        """
        captured.append(arguments)
        return 0

    monkeypatch.setattr(target=dom_diff, name="main", value=record_main)
    monkeypatch.setattr(
        target="sys.argv",
        name=[
            "visual_cause",
            "dom-diff",
            "https://a.example/",
            "https://b.example/",
        ],
    )
    with pytest.raises(expected_exception=SystemExit) as raised:
        run_module(
            mod_name="exactus.packages.visual_cause.__main__",
            run_name="__main__",
        )
    expect_equal(actual=raised.value.code, expected=None)
    expect_equal(
        actual=captured,
        expected=[["https://a.example/", "https://b.example/"]],
    )
