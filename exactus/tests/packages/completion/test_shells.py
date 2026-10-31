# Copyright (c) 2026
"""Coverage for the shell registration-script renderers."""

from __future__ import annotations

from json import loads
from shutil import which
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING, Final, final

from exactus.packages.completion.model import CompletionShell
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants,
)
from exactus.packages.completion.shells import (
    _function_name,
    render,
    render_bash,
    render_fish,
    render_powershell,
    render_zsh,
)
from exactus.tests.common.support import expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path


@final
class Constants:
    """Group module-level constants.

    Attributes:
        launcher: Grouped module constant.

    """

    launcher: Final[tuple[str, ...]] = ("check",)


def test_function_name_sanitizes() -> None:
    """Non-identifier characters become underscores."""
    expect_equal(
        actual=_function_name(command_name="my-tool"),
        expected="_my_tool_completion",
    )
    expect_equal(
        actual=_function_name(command_name="check"),
        expected="_check_completion",
    )


def test_bash_script_shape() -> None:
    """Bash output registers a function and parses US records."""
    script: str = render_bash(
        command_name="check",
        launcher=Constants.launcher,
    )
    expect_in(
        member=(
            f"# Completion protocol: {_GroupFinalConstants.protocol_version}"
        ),
        container=script,
    )
    expect_in(member="_check_completion()", container=script)
    expect_in(member="complete -F _check_completion check", container=script)
    expect_in(member="COMP_WORDS", container=script)
    expect_in(member="compopt -o nospace", container=script)
    expect_in(member="$'\\x1f'", container=script)
    expect_in(member="__complete", container=script)


def test_zsh_script_shape() -> None:
    """Zsh output declares compdef and splits on the separator."""
    script: str = render_zsh(command_name="check", launcher=Constants.launcher)
    expect_in(member="#compdef check", container=script)
    expect_in(member="compdef _check_completion check", container=script)
    expect_in(member="compadd", container=script)
    expect_in(member="CURRENT - 1", container=script)
    expect_in(member="__complete", container=script)


def test_fish_script_shape() -> None:
    """Fish output registers a ``complete`` handler."""
    script: str = render_fish(
        command_name="check",
        launcher=Constants.launcher,
    )
    expect_in(member="function _check_completion", container=script)
    expect_in(member="complete --command check --no-files", container=script)
    expect_in(member="commandline -opc", container=script)
    expect_in(member="__complete", container=script)


def test_powershell_script_shape() -> None:
    """PowerShell output registers a native argument completer."""
    script: str = render_powershell(
        command_name="check",
        launcher=Constants.launcher,
    )
    expect_in(member="Register-ArgumentCompleter -Native", container=script)
    expect_in(member="-CommandName 'check'", container=script)
    expect_in(member="CompletionResult]::new", container=script)
    expect_in(member="__complete", container=script)


def test_render_dispatches_every_shell() -> None:
    """``render`` covers all four supported shells."""
    for shell in CompletionShell:
        script: str = render(
            shell=shell,
            command_name="check",
            launcher=Constants.launcher,
        )
        expect_in(member="__complete", container=script)
        expect_in(
            member=(
                f"Completion protocol: {_GroupFinalConstants.protocol_version}"
            ),
            container=script,
        )


def test_scripts_are_deterministic() -> None:
    """Identical inputs produce byte-identical scripts."""
    for shell in CompletionShell:
        first: str = render(
            shell=shell,
            command_name="check",
            launcher=Constants.launcher,
        )
        second: str = render(
            shell=shell,
            command_name="check",
            launcher=Constants.launcher,
        )
        expect_equal(actual=first, expected=second)


def test_launcher_embedded_in_scripts() -> None:
    """A multi-word launcher is quoted into each adapter."""
    launcher: tuple[str, ...] = ("python3", "-m", "exactus")
    for shell in CompletionShell:
        script: str = render(
            shell=shell,
            command_name="check",
            launcher=launcher,
        )
        expect_in(member="python3", container=script)


def test_generated_bash_is_syntactically_valid() -> None:
    """The bash adapter parses under ``bash -n``."""
    script: str = render_bash(
        command_name="check",
        launcher=Constants.launcher,
    )
    result: CompletedProcess[str] = run(
        args=["bash", "-n"],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=result.returncode, expected=0)


def test_generated_zsh_is_syntactically_valid() -> None:
    """The zsh adapter parses under ``zsh -n`` when available."""
    if which(cmd="zsh") is None:
        return
    script: str = render_zsh(command_name="check", launcher=Constants.launcher)
    result: CompletedProcess[str] = run(
        args=["zsh", "-n"],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=result.returncode, expected=0)


def test_generated_fish_is_syntactically_valid() -> None:
    """The fish adapter parses under ``fish --no-execute``."""
    if which(cmd="fish") is None:
        return
    script: str = render_fish(
        command_name="check",
        launcher=Constants.launcher,
    )
    result: CompletedProcess[str] = run(
        args=["fish", "--no-execute", "/dev/stdin"],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=result.returncode, expected=0)


def test_powershell_uses_cursor_and_logical_words(tmp_path: Path) -> None:
    """Native completion ignores suffix tokens and decodes quoting.

    Args:
        tmp_path: Isolated adapter script directory.

    """
    executable: str | None = which(cmd="pwsh")
    if executable is None:
        return
    cases: tuple[tuple[str, int, tuple[str, ...]], ...] = (
        (
            "exactus --docs 'folder name' --width 800",
            len("exactus --docs 'folder n"),
            ("exactus", "--docs", "folder n"),
        ),
        (
            "exactus --docs  --width 800",
            len("exactus --docs "),
            ("exactus", "--docs", ""),
        ),
        (
            'exactus --docs "folder name" ',
            len('exactus --docs "folder name" '),
            ("exactus", "--docs", "folder name", ""),
        ),
        (
            "exactus --docs foo` bar ",
            len("exactus --docs foo` bar "),
            ("exactus", "--docs", "foo bar", ""),
        ),
    )
    for index, (line, cursor, words) in enumerate(iterable=cases):
        escaped: str = line.replace("'", "''")
        script: str = render_powershell(
            command_name="exactus",
            launcher=("Capture-Request",),
        ) + (
            f"\nfunction Capture-Request {{ $script:captured = @($args) }}"
            f"\n$line = '"
            f"{escaped}"
            f"'\n$tokens=$null; $errors=$null\n$ast=[System.Management.Aut"
            f"omation.Language.Parser]::ParseInput(\n    $line, [ref]$toke"
            f"ns, [ref]$errors\n)\n$command=$ast.Find({{\n    param($node)"
            f"\n    $node -is [System.Management.Automation.Language.Comma"
            f"ndAst]\n}}, $true)\n& $__exactusCompleter '' $command "
            f"{cursor}"
            f" | Out-Null\n$script:captured | ConvertTo-Json -Compress\n"
        )
        path: Path = tmp_path / f"cursor-{index}.ps1"
        _ = path.write_text(data=script, encoding="utf-8")
        result: CompletedProcess[str] = run(
            args=[executable, "-NoProfile", "-File", str(object=path)],
            capture_output=True,
            text=True,
            check=False,
        )
        expect_equal(actual=result.returncode, expected=0)
        expect_equal(actual=result.stderr, expected="")
        expect_equal(
            actual=loads(s=result.stdout),
            expected=[
                "__complete",
                f"--protocol-version={_GroupFinalConstants.protocol_version}",
                "--shell=powershell",
                f"--active-word-index={len(words) - 1}",
                f"--prefix={words[-1]}",
                *(f"--word={word}" for word in words),
            ],
        )
