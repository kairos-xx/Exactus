"""Tests for the unified package CLI."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Unpack
from unittest.mock import MagicMock

import pytest

from exactus.packages.package import api, cli, inventory_cli
from exactus.packages.package.api import RunResult
from exactus.packages.package.config import BundleConfig

if TYPE_CHECKING:
    from argparse import ArgumentParser


def expect_equal[T](*, actual: T, expected: T) -> None:
    """Require equal values.

    Args:
        actual: Observed value.
        expected: Required value.

    """
    if actual != expected:
        pytest.fail(reason=f"{actual!r} != {expected!r}")


@dataclass(slots=True, kw_only=True)
class Capture:
    """Capture typed arguments passed from the CLI to the API.

    Attributes:
        build_stage: Recorded build-stage selection.
        bundle_stage: Recorded bundle-stage selection.
        package_stage: Recorded package-stage selection.
        bundle_config: Recorded bundle-stage configuration.

    """

    build_stage: bool | None = None
    bundle_stage: bool | None = None
    package_stage: bool | None = None
    bundle_config: BundleConfig | None = None


def test_cli_stage_flags_are_exact_and_order_independent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """CLI stage flags select the exact requested set.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    captured: Capture = Capture()

    def fake_run(
        *,
        root: Path,
        pyproject: Path | None = None,
        **arguments: Unpack[api.RunArguments],
    ) -> RunResult:
        """Record the requested stage selections instead of running.

        Args:
            root: Unused project root.
            pyproject: Unused configuration path.
            arguments: Stage selections and configuration overrides.

        Returns:
            Empty pipeline result.

        """
        del root, pyproject
        captured.build_stage = arguments.get("build_stage")
        captured.bundle_stage = arguments.get("bundle_stage")
        captured.package_stage = arguments.get("package_stage")
        return RunResult(stages=())

    monkeypatch.setattr(target=cli, name="run", value=fake_run)
    expect_equal(
        actual=cli.main(
            arguments=(
                "--root",
                str(object=tmp_path),
                "--package",
                "--build",
                "--bundle",
            ),
        ),
        expected=0,
    )
    expect_equal(actual=captured.build_stage, expected=True)
    expect_equal(actual=captured.bundle_stage, expected=True)
    expect_equal(actual=captured.package_stage, expected=True)


def test_cli_field_override_preserves_other_pyproject_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A CLI field overrides only its matching configured field.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Isolated filesystem root.

    """
    (tmp_path / "pyproject.toml").write_text(
        data='[tool.package.bundle]\nnode-version="23"\noptional=["jinja2"]\n',
        encoding="utf-8",
    )
    captured: Capture = Capture()

    def fake_run(
        *,
        root: Path,
        pyproject: Path | None = None,
        **arguments: Unpack[api.RunArguments],
    ) -> RunResult:
        """Record the bundle configuration instead of running.

        Args:
            root: Unused project root.
            pyproject: Unused configuration path.
            arguments: Stage selections and configuration overrides.

        Returns:
            Empty pipeline result.

        """
        del root, pyproject
        captured.bundle_config = arguments.get("bundle_config")
        return RunResult(stages=())

    monkeypatch.setattr(target=cli, name="run", value=fake_run)
    expect_equal(
        actual=cli.main(
            arguments=(
                "--root",
                str(object=tmp_path),
                "--bundle",
                "--bundle-node-version",
                "24",
            ),
        ),
        expected=0,
    )
    config: BundleConfig | None = captured.bundle_config
    if config is None:
        pytest.fail(reason="CLI did not pass a bundle configuration")
    expect_equal(actual=config.node_version, expected="24")
    expect_equal(actual=config.optional, expected=("jinja2",))


@pytest.mark.parametrize("mode", ["terminal", "pipe", "no-color"])
def test_inventory_help_respects_terminal_and_no_color(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """Render flags, positionals and metavariables without coloring pipes.

    Args:
        monkeypatch: Terminal and environment boundary replacement.
        mode: Terminal capability and user preference.

    """
    terminal: MagicMock = MagicMock()
    terminal.isatty.return_value = mode != "pipe"
    monkeypatch.setattr(target=inventory_cli, name="stdout", value=terminal)
    monkeypatch.delenv(name="NO_COLOR", raising=False)
    if mode == "no-color":
        monkeypatch.setenv(name="NO_COLOR", value="")
    parser: ArgumentParser = inventory_cli.pretty_parser(
        prog="inventory",
        description="Inspect assets",
        epilog="Examples stay intact.",
    )
    _ = parser.add_argument("source", help="Asset source")
    _ = parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Destination",
    )
    _ = parser.add_argument(
        "--verbose",
        action="store_true",
        help="More details",
    )
    text: str = parser.format_help()
    expect_equal(actual="\x1b[" in text, expected=mode == "terminal")
    expect_equal(actual="source" in text, expected=True)
    expect_equal(actual="--output" in text, expected=True)
    expect_equal(actual="PATH" in text, expected=True)
    expect_equal(actual="Examples stay intact." in text, expected=True)
    expect_equal(
        actual=inventory_cli.paint(code="\x1b[1m", text=""),
        expected="",
    )
    empty: ArgumentParser = inventory_cli.pretty_parser(
        prog="empty",
        description="No epilog",
    )
    expect_equal(actual=empty.epilog, expected=None)
