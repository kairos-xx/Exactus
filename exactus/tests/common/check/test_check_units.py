# Copyright (c) 2026
"""Focused unit coverage for the bundled CLI model and presentation helpers."""

from __future__ import annotations

from argparse import ArgumentParser
from io import StringIO
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile

from exactus import __main__ as check
from exactus.__main__ import HelpRenderer, Terminal, Tool
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import pytest

    from exactus.__main__ import ArgumentInfo


def _default_root() -> Path:
    """Resolve the private default-root helper.

    Returns:
        Resolved project root.

    """
    return cast(
        typ="Path",
        val=private_call(owner=check, name="_default_root"),
    )


def test_default_root_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefer the environment, then a packaged launcher, then the cwd.

    Args:
        tmp_path: Temporary project tree.
        monkeypatch: Pytest patching helper.

    """
    explicit: Path = tmp_path / "explicit"
    monkeypatch.setenv(name="EXACTUS_ROOT", value=str(object=explicit))
    expect_equal(actual=_default_root(), expected=explicit.resolve())
    monkeypatch.delenv(name="EXACTUS_ROOT")
    launcher: Path = tmp_path / "project" / "exec" / "exactus"
    launcher.parent.mkdir(parents=True)
    with ZipFile(file=launcher, mode="w") as archive:
        archive.writestr(zinfo_or_arcname="__main__.py", data="")
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=launcher)],
    )
    expect_equal(actual=_default_root(), expected=tmp_path / "project")
    installed: Path = tmp_path / "bin" / "exactus"
    installed.parent.mkdir(parents=True)
    with ZipFile(file=installed, mode="w") as archive:
        archive.writestr(zinfo_or_arcname="__main__.py", data="")
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=installed)],
    )
    monkeypatch.chdir(path=tmp_path)
    expect_equal(actual=_default_root(), expected=tmp_path.resolve())
    markered: Path = tmp_path / "tool" / "exactus"
    markered.parent.mkdir(parents=True)
    _ = (markered.parent / "pyproject.toml").write_text(
        data="",
        encoding="utf-8",
    )
    with ZipFile(file=markered, mode="w") as archive:
        archive.writestr(zinfo_or_arcname="__main__.py", data="")
    monkeypatch.setattr(
        target=check,
        name="argv",
        value=[str(object=markered)],
    )
    expect_equal(actual=_default_root(), expected=markered.parent)
    monkeypatch.setattr(target=check, name="argv", value=["python"])
    expect_equal(actual=_default_root(), expected=tmp_path.resolve())


def test_tool_and_terminal_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Create fresh parsers and apply styles only on capable terminals.

    Args:
        monkeypatch: Pytest patching helper.

    """
    created: list[ArgumentParser] = []

    def parser() -> ArgumentParser:
        """Create and record a parser.

        Returns:
            Newly created parser.

        """
        value: ArgumentParser = ArgumentParser(description="demo")
        created.append(value)
        return value

    tool: Tool = Tool(
        name="coverage_tests",
        create_parser=parser,
        aliases=("coverage",),
    )
    expect_equal(actual=tool.flag, expected="--coverage_tests")
    expect_equal(
        actual=tool.flags,
        expected=("--coverage_tests", "--coverage", "--coverage-tests"),
    )
    expect_true(condition=tool.parser is not tool.parser)
    expect_equal(actual=len(created), expected=2)
    stream: StringIO = StringIO()
    terminal: Terminal = Terminal(stream=stream)
    expect_equal(actual=terminal.style("text", Terminal.BOLD), expected="text")
    terminal.color = True
    expect_equal(
        actual=terminal.style("text", Terminal.BOLD, Terminal.CYAN),
        expected=f"{Terminal.BOLD}{Terminal.CYAN}text{Terminal.RESET}",
    )
    terminal.write(text="line")
    expect_equal(actual=stream.getvalue(), expected="line\n")
    monkeypatch.setenv(name="NO_COLOR", value="1")


def test_help_renderer_extracts_argument_metadata() -> None:
    """Render positional, optional, repeated, required and choice metadata."""
    parser: ArgumentParser = ArgumentParser(add_help=False)
    _ = parser.add_argument("source", metavar="FILE")
    _ = parser.add_argument("--verbose", action="store_true", help="Explain")
    _ = parser.add_argument(
        "--mode",
        choices=("fast", "safe"),
        default="safe",
        required=True,
    )
    _ = parser.add_argument("--pair", nargs=2, metavar=("KEY", "VALUE"))
    arguments: tuple[ArgumentInfo, ...] = HelpRenderer.arguments(parser=parser)
    expect_equal(actual=arguments[0].syntax, expected="FILE")
    expect_equal(actual=arguments[1].syntax, expected="--verbose")
    expect_in(member="required", container=arguments[2].description)
    expect_in(member="choices: fast, safe", container=arguments[2].description)
    expect_equal(
        actual=arguments[3].syntax,
        expected="--pair KEY VALUE KEY VALUE",
    )
    expect_equal(
        actual=HelpRenderer.wrap(text="one two three", width=7),
        expected=("one two", "three"),
    )


def test_completion_dispatches_without_running_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route protocol and installer commands before normal initialization.

    Args:
        monkeypatch: Pytest patching helper.

    """
    calls: list[tuple[str, ...]] = []

    def complete(*, arguments: tuple[str, ...], **_kwargs: object) -> int:
        """Capture completion protocol arguments.

        Args:
            arguments: Completion request tokens.
            **_kwargs: Catalog and provider inputs.

        Returns:
            Marker status.

        """
        calls.append(arguments)
        return 7

    def install(*, arguments: Sequence[str]) -> int:
        """Capture completion command arguments.

        Args:
            arguments: Completion command tokens.

        Returns:
            Marker status.

        """
        calls.append(tuple(arguments))
        return 8

    monkeypatch.setattr(target=check, name="run_completion", value=complete)
    monkeypatch.setattr(
        target=check,
        name="run_completion_command",
        value=install,
    )
    expect_equal(
        actual=check.main(arguments=("__complete", "--shell", "bash")),
        expected=7,
    )
    expect_equal(
        actual=check.main(arguments=("completion", "install")),
        expected=8,
    )
    expect_equal(actual=calls, expected=[("--shell", "bash"), ("install",)])
