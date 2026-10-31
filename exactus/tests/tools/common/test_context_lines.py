# Copyright (c) 2026
"""The shared ``--context-lines`` option and its configuration layers."""

from __future__ import annotations

from argparse import ArgumentTypeError
from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import expect_equal, expect_in
from exactus.tools.common import config as _config
from exactus.tools.common.cli import context_lines
from exactus.tools.coverage_tests.main import parse_args as coverage_args
from exactus.tools.docs.main import parse_args as docs_args
from exactus.tools.lints.main import create_parser as lints_parser
from exactus.tools.lints.main import parse_args as lints_args
from exactus.tools.readme.main import create_parser as readme_parser
from exactus.tools.readme.main import parse_args as readme_args

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from collections.abc import Callable
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        parsers: Grouped module constant.

    """

    parsers: Final[tuple[Callable[..., Namespace], ...]] = (
        lints_args,
        readme_args,
        docs_args,
        coverage_args,
    )


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run a standalone tool from an empty project directory.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    Returns:
        The project directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED", raising=False)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    return tmp_path


def _configure(*, root: Path, text: str) -> None:
    """Write ``pyproject.toml`` with ``text``.

    Args:
        root: Project directory.
        text: TOML document.

    """
    _ = (root / "pyproject.toml").write_text(
        data=f"[tool.exactus]\nroot = true\n{text}",
        encoding="utf-8",
    )


def _lines(
    *,
    parse: Callable[..., Namespace],
    arguments: tuple[str, ...],
) -> int:
    """Parse arguments with one tool and return its context lines.

    Args:
        parse: The tool's ``parse_args``.
        arguments: Command-line arguments.

    Returns:
        The resolved ``context_lines`` value.

    """
    namespace: Namespace = parse(arguments=arguments)
    value: object = namespace.context_lines
    return value if isinstance(value, int) else -1


@pytest.mark.usefixtures("project")
def test_default_is_three_for_every_tool() -> None:
    """Without configuration every tool captures three context lines."""
    for parse in Constants.parsers:
        expect_equal(actual=_lines(parse=parse, arguments=()), expected=3)


def test_common_table_sets_every_tool(project: Path) -> None:
    """``[tool.exactus] context-lines`` reaches every tool.

    Args:
        project: Project directory.

    """
    _configure(root=project, text="context-lines = 5\n")
    for parse in Constants.parsers:
        expect_equal(actual=_lines(parse=parse, arguments=()), expected=5)


def test_tool_table_overrides_common_and_cli_wins(project: Path) -> None:
    """``[tool.exactus.<tool>]`` beats ``[tool.exactus]``; the CLI beats both.

    Args:
        project: Project directory.

    """
    _configure(
        root=project,
        text="context-lines = 5\n\n[tool.exactus.lints]\ncontext-lines = 1\n",
    )
    expect_equal(actual=_lines(parse=lints_args, arguments=()), expected=1)
    expect_equal(actual=_lines(parse=readme_args, arguments=()), expected=5)
    expect_equal(
        actual=_lines(parse=lints_args, arguments=("--context-lines", "7")),
        expected=7,
    )
    expect_equal(
        actual=_lines(parse=readme_args, arguments=("--context-lines", "0")),
        expected=0,
    )


def test_pipeline_table_sits_between_tool_table_and_cli(project: Path) -> None:
    """The pipeline-scoped tool table overrides the tool table.

    Args:
        project: Project directory.

    """
    _configure(
        root=project,
        text=(
            dedent(
                text=(
                    "    context-lines = 5\n    \n    [tool.exactus.lints]"
                    "\n    context-lines = 1\n    \n    [tool.exactus.pipe"
                    "line.self.lints]\n    context-lines = 9\n    "
                ),
            )
        ),
    )
    files: tuple[_config.ConfigFile, ...] = _config.discover(
        start=project,
        explicit=None,
    )
    parser: ArgumentParser = lints_parser()
    tokens: tuple[str, ...] = _config.argv_for(
        files=files,
        tool="lints",
        parser=parser,
        pipeline="self",
    )
    expect_equal(
        actual=parser.parse_args(args=list(tokens)).context_lines,
        expected=9,
    )
    expect_equal(
        actual=parser.parse_args(
            args=[*tokens, "--context-lines", "2"],
        ).context_lines,
        expected=2,
    )
    _config.validate(
        files=files,
        parsers={"lints": parser, "readme": readme_parser()},
        pipelines=("self",),
    )


def test_negative_values_are_rejected(
    project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A negative count stops the tool with status 2 from CLI or config.

    Args:
        project: Project directory.
        capsys: Pytest output capture fixture.

    """
    with pytest.raises(expected_exception=SystemExit) as cli:
        _ = lints_args(arguments=("--context-lines", "-1"))
    expect_equal(actual=cli.value.code, expected=2)
    _configure(root=project, text="context-lines = -2\n")
    with pytest.raises(expected_exception=SystemExit) as config:
        _ = lints_args(arguments=())
    expect_equal(actual=config.value.code, expected=2)
    expect_in(member="context-lines", container=capsys.readouterr().err)


def test_context_lines_type() -> None:
    """The option type accepts non-negative integers only."""
    expect_equal(actual=context_lines(text="0"), expected=0)
    expect_equal(actual=context_lines(text="12"), expected=12)
    for text in ("-1", "two", "1.5"):
        with pytest.raises(expected_exception=ArgumentTypeError):
            _ = context_lines(text=text)
