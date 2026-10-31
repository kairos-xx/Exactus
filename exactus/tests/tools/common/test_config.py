# Copyright (c) 2026
"""Discovery, parsing, merging and rendering of ``[tool.exactus]`` settings."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus import __main__ as check
from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.common import config as cfg

if TYPE_CHECKING:
    from exactus.tools.common.config import ConfigFile
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        tool_toml: Grouped module constant.

    """

    tool_toml: Final[str] = dedent(
        text=(
            '    \n    [tool.exactus]\n    include = ["a/**"]\n    [tool.exact'
            "us.demo]\n    fail-under = 90\n    no-branch = true\n    quiet = "
            'false\n    pytest-arg = ["-x", "-q"]\n    jobs = 0\n    [tool.exa'
            "ctus.pipeline.self.demo]\n    fail-under = 95\n    "
        ),
    )


def _write(*, directory: Path, text: str) -> Path:
    """Write a ``pyproject.toml`` into ``directory``.

    Args:
        directory: Target directory, created when missing.
        text: TOML document.

    Returns:
        The written file.

    """
    directory.mkdir(parents=True, exist_ok=True)
    path: Path = directory / "pyproject.toml"
    _ = path.write_text(data=text, encoding="utf-8")
    return path


def _files(
    *,
    tmp_path: Path,
    text: str = Constants.tool_toml,
) -> tuple[cfg.ConfigFile, ...]:
    """Load a one-file stack.

    Args:
        tmp_path: Per-test temporary directory.
        text: TOML document.

    Returns:
        The loaded stack.

    """
    _ = _write(directory=tmp_path, text=text)
    return cfg.discover(start=tmp_path)


def _parser() -> ArgumentParser:
    """Build a parser with one flag of each rendering kind.

    Returns:
        The parser.

    """
    parser: ArgumentParser = ArgumentParser()
    _ = parser.add_argument("--fail-under", type=float)
    _ = parser.add_argument("--no-branch", action="store_true")
    _ = parser.add_argument("--quiet", action="store_true")
    _ = parser.add_argument("--pytest-arg", action="append", default=[])
    _ = parser.add_argument("--jobs", type=int)
    _ = parser.add_argument("--include", action="append", default=[])
    return parser


def test_discover_walks_upward_nearest_first(tmp_path: Path) -> None:
    """Every ancestor with ``[tool.exactus]`` is loaded, nearest first.

    Args:
        tmp_path: Per-test temporary directory.

    """
    outer: Path = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    inner: Path = _write(
        directory=tmp_path / "pkg",
        text="[tool.exactus]\nb = 2\n",
    )
    found: tuple[cfg.ConfigFile, ...] = cfg.discover(start=tmp_path / "pkg")
    expect_equal(actual=[item.path for item in found], expected=[inner, outer])


def test_discover_stops_at_root_marker(tmp_path: Path) -> None:
    """``root = true`` ends the upward walk after that file.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    inner: Path = _write(
        directory=tmp_path / "pkg",
        text="[tool.exactus]\nroot = true\n",
    )
    found: tuple[cfg.ConfigFile, ...] = cfg.discover(start=tmp_path / "pkg")
    expect_equal(actual=[item.path for item in found], expected=[inner])


def test_discover_skips_files_without_exactus_table(tmp_path: Path) -> None:
    """A ``pyproject.toml`` lacking ``[tool.exactus]`` is ignored.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(directory=tmp_path, text="[tool.ruff]\nline-length = 80\n")
    expect_equal(actual=cfg.discover(start=tmp_path), expected=())


def test_explicit_and_disabled(tmp_path: Path) -> None:
    """``--config`` loads one file; ``--no-config`` loads none.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    other: Path = tmp_path / "other.toml"
    _ = other.write_text(data="[tool.exactus]\nb = 2\n", encoding="utf-8")
    found: tuple[cfg.ConfigFile, ...] = cfg.discover(
        start=tmp_path,
        explicit=other,
    )
    expect_equal(actual=[item.path for item in found], expected=[other])
    expect_equal(
        actual=cfg.discover(start=tmp_path, disabled=True),
        expected=(),
    )
    with pytest.raises(expected_exception=cfg.ConfigError):
        _ = cfg.discover(start=tmp_path, explicit=tmp_path / "missing.toml")


def test_invalid_toml_names_the_file(tmp_path: Path) -> None:
    """A parse failure raises ``ConfigError`` naming the file.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = _write(directory=tmp_path, text="[tool.exactus\n")
    with pytest.raises(expected_exception=cfg.ConfigError) as caught:
        _ = cfg.discover(start=tmp_path)
    expect_in(member=str(object=path), container=str(object=caught.value))


def test_environment_variable_controls_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``EXACTUS_CONFIG`` is either ``off`` or an explicit path.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    monkeypatch.setenv(name=cfg.Constants.environment_variable, value="off")
    expect_equal(
        actual=cfg.discovery_from_environment(start=tmp_path),
        expected=(),
    )
    monkeypatch.setenv(
        name=cfg.Constants.environment_variable,
        value=str(object=tmp_path / "pyproject.toml"),
    )
    expect_equal(
        actual=len(cfg.discovery_from_environment(start=tmp_path / "x")),
        expected=1,
    )


def test_discover_boundary_contains_the_walk(tmp_path: Path) -> None:
    """A boundary stops the walk reaching enclosing configuration.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    inner: Path = _write(
        directory=tmp_path / "pkg",
        text="[tool.exactus]\nb = 2\n",
    )
    found: tuple[cfg.ConfigFile, ...] = cfg.discover(
        start=tmp_path / "pkg" / "deep",
        boundary=tmp_path / "pkg",
    )
    expect_equal(actual=[item.path for item in found], expected=[inner])


def test_discover_boundary_relocates_outside_start(tmp_path: Path) -> None:
    """A start outside the boundary is moved inside it.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    inner: Path = _write(
        directory=tmp_path / "pkg",
        text="[tool.exactus]\nb = 2\n",
    )
    found: tuple[cfg.ConfigFile, ...] = cfg.discover(
        start=tmp_path,
        boundary=tmp_path / "pkg",
    )
    expect_equal(actual=[item.path for item in found], expected=[inner])


def test_exactus_root_bounds_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``EXACTUS_ROOT`` keeps nested runs off the enclosing project.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _write(directory=tmp_path, text="[tool.exactus]\na = 1\n")
    project: Path = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv(name="EXACTUS_ROOT", value=str(object=project))
    found: tuple[cfg.ConfigFile, ...] = cfg.discovery_from_environment(
        start=tmp_path,
    )
    expect_equal(actual=found, expected=())


def test_render_kinds(tmp_path: Path) -> None:
    """Scalars, flags, repeats and zero are rendered exactly.

    Args:
        tmp_path: Per-test temporary directory.

    """
    argv: tuple[str, ...] = cfg.argv_for(
        files=_files(tmp_path=tmp_path),
        tool="demo",
        parser=_parser(),
    )
    expect_equal(
        actual=argv,
        expected=(
            "--fail-under",
            "90",
            "--no-branch",
            "--pytest-arg=-x",
            "--pytest-arg=-q",
            "--jobs",
            "0",
        ),
    )


def test_pipeline_table_overrides_tool_table(tmp_path: Path) -> None:
    """The pipeline-scoped table comes last so it wins.

    Args:
        tmp_path: Per-test temporary directory.

    """
    argv: tuple[str, ...] = cfg.argv_for(
        files=_files(tmp_path=tmp_path),
        tool="demo",
        parser=_parser(),
        pipeline="self",
    )
    expect_equal(actual=argv[-2:], expected=("--fail-under", "95"))
    parsed: Namespace = _parser().parse_args(args=list(argv))
    expect_equal(actual=parsed.fail_under, expected=95.0)


def test_negative_values_survive(tmp_path: Path) -> None:
    """Values starting with a dash are not read as flags.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text="[tool.exactus.demo]\nfail-under = -1\n",
    )
    argv: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="demo",
        parser=_parser(),
    )
    expect_equal(
        actual=_parser().parse_args(args=list(argv)).fail_under,
        expected=-1.0,
    )


def test_common_keys_standalone_only(tmp_path: Path) -> None:
    """Common orchestrator keys apply to standalone runs only.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(tmp_path=tmp_path)
    standalone: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="demo",
        parser=_parser(),
        standalone=True,
    )
    expect_equal(actual=standalone[:2], expected=("--include", "a/**"))
    orchestrated: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="demo",
        parser=_parser(),
    )
    expect_not_in(member="--include", container=orchestrated)


def test_unknown_key_and_wrong_type(tmp_path: Path) -> None:
    """Typos and bad values raise ``ConfigError`` naming file and key.

    Args:
        tmp_path: Per-test temporary directory.

    """
    bad_key: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text="[tool.exactus.demo]\nfail-undr = 1\n",
    )
    with pytest.raises(expected_exception=cfg.ConfigError, match="fail-undr"):
        _ = cfg.argv_for(files=bad_key, tool="demo", parser=_parser())
    bad_type: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text='[tool.exactus.demo]\nfail-under = "high"\n',
    )
    with pytest.raises(expected_exception=cfg.ConfigError, match="fail-under"):
        _ = cfg.argv_for(files=bad_type, tool="demo", parser=_parser())
    bad_flag: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text='[tool.exactus.demo]\nno-branch = "yes"\n',
    )
    with pytest.raises(expected_exception=cfg.ConfigError, match="no-branch"):
        _ = cfg.argv_for(files=bad_flag, tool="demo", parser=_parser())


def test_common_key_unknown_to_a_tool_is_skipped(tmp_path: Path) -> None:
    """A common key the tool lacks is skipped rather than rejected.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text="[tool.exactus]\nfail-under = 5\n",
    )
    bare: ArgumentParser = ArgumentParser()
    expect_equal(
        actual=cfg.argv_for(files=files, tool="demo", parser=bare),
        expected=(),
    )


def test_nested_files_merge(tmp_path: Path) -> None:
    """Nearest scalars win; lists combine farthest first.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(
        directory=tmp_path,
        text='[tool.exactus.demo]\nfail-under = 10\npytest-arg = ["-x"]\n',
    )
    _ = _write(
        directory=tmp_path / "pkg",
        text='[tool.exactus.demo]\nfail-under = 20\npytest-arg = ["-q"]\n',
    )
    merged: dict[str, JsonValue] = cfg.stacked(
        files=cfg.discover(start=tmp_path / "pkg"),
        path=("demo",),
    )
    expect_equal(actual=merged["fail-under"], expected=20)
    expect_equal(actual=merged["pytest-arg"], expected=["-x", "-q"])


def test_validate_rejects_unknown_table_and_common_key(tmp_path: Path) -> None:
    """Unknown tables and unclaimed common keys fail validation.

    Args:
        tmp_path: Per-test temporary directory.

    """
    parsers: dict[str, ArgumentParser] = {"demo": _parser()}
    for text, needle in (
        ("[tool.exactus.nope]\na = 1\n", "nope"),
        ("[tool.exactus]\nbogus = 1\n", "bogus"),
        ("[tool.exactus.pipeline.ghost]\na = 1\n", "ghost"),
        ("[tool.exactus.pipeline.self.nope]\na = 1\n", "nope"),
        ("[tool.exactus.demo]\nbogus = 1\n", "bogus"),
    ):
        files: tuple[cfg.ConfigFile, ...] = _files(
            tmp_path=tmp_path,
            text=text,
        )
        with pytest.raises(expected_exception=cfg.ConfigError, match=needle):
            cfg.validate(
                files=files,
                parsers=parsers,
                pipelines=frozenset(("self",)),
            )
    ok: tuple[cfg.ConfigFile, ...] = _files(tmp_path=tmp_path)
    cfg.validate(files=ok, parsers=parsers, pipelines=frozenset(("self",)))


def test_validate_accepts_package_owned_mcp_configuration(
    tmp_path: Path,
) -> None:
    """The MCP package owns its service and nested watcher schemas.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text=(
            dedent(
                text=(
                    "    [tool.exactus.mcp]\n    port = 6100\n    [tool.ex"
                    "actus.mcp.wakeup]\n    keep-service-running = true\n "
                    "   "
                ),
            )
        ),
    )
    cfg.validate(
        files=files,
        parsers={"demo": _parser()},
        pipelines=frozenset(("self",)),
    )


def test_orchestrator_injection_rules(tmp_path: Path) -> None:
    """Config entrypoint/clear are injected only for pipeline-style runs.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text="[tool.exactus]\nclear = true\n",
    )
    parser: ArgumentParser = check.Check.create_parser()

    def inject(arguments: tuple[str, ...]) -> tuple[str, ...]:
        """Inject orchestrator settings for one invocation.

        Args:
            arguments: Simulated CLI arguments.

        Returns:
            The injected tokens.

        """
        return cfg.orchestrator_arguments(
            files=files,
            parser=parser,
            arguments=arguments,
            pipeline=None,
        )

    expect_equal(actual=inject(arguments=()), expected=("--clear",))
    expect_equal(
        actual=inject(arguments=("-t", "docs")),
        expected=("--clear",),
    )
    expect_equal(
        actual=inject(arguments=("--url", "http://x")),
        expected=("--clear",),
    )
    expect_equal(actual=inject(arguments=("somepath",)), expected=())
    expect_true(condition=bool(inject(arguments=("--pipeline", "self"))))


def test_effective_reports_the_winning_layer(tmp_path: Path) -> None:
    """Each option names the layer that set its final value.

    The legacy ``[tool.exactus.coverage]`` table reports as the tool layer.

    Args:
        tmp_path: Per-test temporary directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text="[tool.exactus.coverage_tests]\nfail-under = 95\njobs = 2\n",
    )

    def layers(cli: tuple[str, ...]) -> dict[str, str]:
        """Map each option to its winning layer.

        Args:
            cli: Command-line tokens for the tool.

        Returns:
            Layer name per option.

        """
        rows: list[tuple[str, str, str]] = cfg.effective(
            files=files,
            request=cfg.EffectiveRequest(
                tool="coverage_tests",
                module="exactus.tools.coverage_tests.main",
                preset=("--no-branch",),
                cli=cli,
            ),
        )
        return {option: layer for option, _, layer in rows}

    plain: dict[str, str] = layers(cli=())
    expect_equal(actual=plain["fail_under"], expected="tool")
    expect_equal(actual=plain["no_branch"], expected="preset")
    expect_equal(actual=plain["output_dir"], expected="default")
    overridden: dict[str, str] = layers(cli=("--fail-under", "50"))
    expect_equal(actual=overridden["fail_under"], expected="cli")
    expect_equal(actual=overridden["jobs"], expected="tool")


def test_canonical_section_precedence(tmp_path: Path) -> None:
    """Tool, pipeline and CLI gates override common defaults in order.

    Args:
        tmp_path: Isolated project directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text=(
            dedent(
                text=(
                    "    [tool.exactus]\n    fail-under = 10\n    jobs = 3"
                    "\n    [tool.exactus.coverage_tests]\n    fail-under ="
                    " 20\n    [tool.exactus.pipeline.self.coverage_tests]"
                    "\n    jobs = 4\n    "
                ),
            )
        ),
    )
    parser: ArgumentParser = _parser()
    argv: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="coverage_tests",
        parser=parser,
    )
    configured: Namespace = parser.parse_args(args=list(argv))
    expect_equal(actual=configured.fail_under, expected=20.0)
    expect_equal(actual=configured.jobs, expected=3)
    expect_equal(
        actual=parser.parse_args(
            args=[*argv, "--fail-under", "30"],
        ).fail_under,
        expected=30.0,
    )
    scoped: Namespace = parser.parse_args(
        args=list(
            cfg.argv_for(
                files=files,
                tool="coverage_tests",
                parser=parser,
                pipeline="self",
            ),
        ),
    )
    expect_equal(actual=scoped.jobs, expected=4)


def test_canonical_tool_list_extends_common_list(tmp_path: Path) -> None:
    """Repeated tool options extend the common options in order.

    Args:
        tmp_path: Isolated project directory.

    """
    files: tuple[cfg.ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text=(
            dedent(
                text=(
                    '    [tool.exactus]\n    pytest-arg = ["-x"]\n    [too'
                    'l.exactus.coverage_tests]\n    pytest-arg = ["-q"]\n '
                    "   "
                ),
            )
        ),
    )
    argv: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="coverage_tests",
        parser=_parser(),
    )
    expect_equal(actual=argv, expected=("--pytest-arg=-x", "--pytest-arg=-q"))


def test_validate_rejects_legacy_sections(tmp_path: Path) -> None:
    """Removed legacy table names produce an explicit configuration error.

    Args:
        tmp_path: Isolated project directory.

    """
    parsers: dict[str, ArgumentParser] = {"coverage_tests": _parser()}
    for section in ("coverage", "coverage-tests"):
        files: tuple[cfg.ConfigFile, ...] = _files(
            tmp_path=tmp_path,
            text=f"[tool.exactus.{section}]\nfail-under = 10\n",
        )
        with pytest.raises(
            expected_exception=cfg.ConfigError,
            match="unknown tool",
        ):
            cfg.validate(
                files=files,
                parsers=parsers,
                pipelines=frozenset(("self",)),
            )


@pytest.mark.parametrize("directory", ["reports/exactus", "EXACTUS_RESULTS"])
def test_reports_directory_setting(tmp_path: Path, directory: str) -> None:
    """Read the project-relative reports base without forwarding a flag.

    Args:
        tmp_path: Temporary configuration directory.
        directory: Configured base directory.

    """
    files: tuple[ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text=f'[tool.exactus]\nreports-dir = "{directory}"\n',
    )
    expect_equal(
        actual=cfg.reports_directory(files=files),
        expected=Path(directory),
    )
    expect_equal(
        actual=cfg.argv_for(
            files=files,
            tool="demo",
            parser=_parser(),
            standalone=True,
        ),
        expected=(),
    )


@pytest.mark.parametrize(
    "directory",
    ["", ".", "..", "../reports", "/reports"],
)
def test_reports_directory_rejects_project_escape(
    tmp_path: Path,
    directory: str,
) -> None:
    """Prevent report cleanup from targeting the project or its parent.

    Args:
        tmp_path: Temporary configuration directory.
        directory: Invalid configured directory.

    """
    files: tuple[ConfigFile, ...] = _files(
        tmp_path=tmp_path,
        text=f'[tool.exactus]\nreports-dir = "{directory}"\n',
    )
    with pytest.raises(
        expected_exception=cfg.ConfigError,
        match="reports-dir",
    ):
        _ = cfg.reports_directory(files=files)


def test_standalone_reports_directory_and_cli_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply the reports base while preserving explicit output choices.

    Args:
        tmp_path: Temporary project.
        monkeypatch: Test patch manager.

    """
    _ = _files(
        tmp_path=tmp_path,
        text='[tool.exactus]\nroot = true\nreports-dir = "reports/exactus"\n',
    )
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.delenv(name="EXACTUS_ORCHESTRATED", raising=False)
    monkeypatch.delenv(name="EXACTUS_CONFIG", raising=False)
    monkeypatch.setenv(name="EXACTUS_REPORTS_ROOT", value="")
    parser: ArgumentParser = _parser()
    _ = parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("EXACTUS_RESULTS/DEMO"),
    )
    tokens: tuple[str, ...] = cfg.resolve_arguments(
        tool="demo",
        parser=parser,
        arguments=(),
    )
    expect_equal(
        actual=parser.parse_args(args=tokens).output_dir,
        expected=(tmp_path / "reports/exactus/DEMO").resolve(),
    )
    tokens = cfg.resolve_arguments(
        tool="demo",
        parser=parser,
        arguments=("--output-dir", "explicit"),
    )
    expect_equal(
        actual=parser.parse_args(args=tokens).output_dir,
        expected=Path("explicit"),
    )


def test_path_keys_resolve_against_declaring_file(tmp_path: Path) -> None:
    """``actions``/``workspace`` resolve beside the file that set them.

    Args:
        tmp_path: Per-test temporary directory.

    """
    parent: Path = _write(
        directory=tmp_path,
        text='[tool.exactus.demo]\nworkspace = "parent/ws"\n',
    )
    child: Path = _write(
        directory=tmp_path / "pkg",
        text='[tool.exactus.demo]\nactions = "child/recipe.json"\n',
    )
    files: tuple[ConfigFile, ...] = cfg.discover(start=tmp_path / "pkg")
    parser: ArgumentParser = _parser()
    _ = parser.add_argument("--actions")
    _ = parser.add_argument("--workspace")
    tokens: tuple[str, ...] = cfg.argv_for(
        files=files,
        tool="demo",
        parser=parser,
        standalone=True,
    )
    options: Namespace = parser.parse_args(args=tokens)
    expect_equal(
        actual=options.actions,
        expected=str(object=child.parent / "child/recipe.json"),
    )
    expect_equal(
        actual=options.workspace,
        expected=str(object=parent.parent / "parent/ws"),
    )
    _ = _write(
        directory=tmp_path / "pkg",
        text=(
            dedent(
                text=(
                    '    [tool.exactus.demo]\n    workspace = "child/ws"\n'
                    '    actions = "child/recipe.json"\n    '
                ),
            )
        ),
    )
    nearer: tuple[ConfigFile, ...] = cfg.discover(start=tmp_path / "pkg")
    tokens = cfg.argv_for(
        files=nearer,
        tool="demo",
        parser=parser,
        standalone=True,
    )
    options = parser.parse_args(args=tokens)
    expect_equal(
        actual=options.workspace,
        expected=str(object=child.parent / "child/ws"),
    )
