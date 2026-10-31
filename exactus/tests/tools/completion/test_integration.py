# Copyright (c) 2026
"""End-to-end coverage against the real ``check`` catalog."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess, run
from sys import executable
from typing import TYPE_CHECKING, Final, final

from exactus.__main__ import Check, bundled_tools
from exactus.__main__ import main as check_main
from exactus.packages.completion import launcher as launcher_module
from exactus.packages.completion.catalog import ProviderId
from exactus.packages.completion.install import (
    InstallResult,
    InstallStatus,
    ShellDiagnosis,
    _block_begin,
    _block_end,
    diagnose,
    install,
    uninstall,
)
from exactus.packages.completion.model import (
    CompletionContext,
    CompletionProvider,
    CompletionShell,
    RecognizedArguments,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_2,
)
from exactus.packages.completion.protocol import (
    Constants as _GroupFinalConstants_4,
)
from exactus.packages.completion.protocol import run_completion
from exactus.packages.completion.providers import default_providers
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_not_in,
    expect_true,
)
from exactus.tools.common.catalog import Constants as _GroupFinalConstants
from exactus.tools.completion.defaults import (
    Constants as _GroupFinalConstants_3,
)
from exactus.tools.completion.defaults import check_catalog
from exactus.tools.completion.main import run as completion_run


@final
class Constants:
    """Group module-level constants.

    Attributes:
        block_begin: Grouped module constant.
        block_end: Grouped module constant.
        check_begin: Grouped module constant.
        check_end: Grouped module constant.

    """

    block_begin: Final[str] = _block_begin(command_name="exactus")
    block_end: Final[str] = _block_end(command_name="exactus")
    check_begin: Final[str] = _block_begin(command_name="check")
    check_end: Final[str] = _block_end(command_name="check")


if TYPE_CHECKING:
    import pytest

    from exactus.packages.completion.catalog import CompletionCatalog


def _catalog() -> CompletionCatalog:
    """Build the real ``check`` completion catalog.

    Returns:
        Catalog wired from the dispatcher's own parsers.

    """
    return check_catalog(
        tools=bundled_tools(),
        orchestrator_parser=Check.create_parser(),
    )


def _records(*, words: tuple[str, ...], prefix: str) -> tuple[str, ...]:
    """Run ``__complete`` and return candidate values.

    Args:
        words: Logical words including the active word.
        prefix: Active-word prefix.

    Returns:
        First field of every emitted record.

    """
    stream: StringIO = StringIO()
    status: int = run_completion(
        catalog=_catalog(),
        providers=default_providers(
            tools=tuple(_GroupFinalConstants_3.tool_descriptions.items()),
            pipelines=tuple(
                (pipeline.identifier, "Named pipeline")
                for pipeline in (
                    _GroupFinalConstants.exactus_catalog.pipelines()
                )
            ),
        ),
        arguments=(
            f"--protocol-version={_GroupFinalConstants_4.protocol_version}",
            "--shell=bash",
            f"--active-word-index={len(words) - 1}",
            f"--prefix={prefix}",
            *(f"--word={word}" for word in words),
        ),
        out=stream,
    )
    expect_equal(actual=status, expected=_GroupFinalConstants_2.exit_ok)
    return tuple(
        line.split(sep="\x1f", maxsplit=1)[0]
        for line in stream.getvalue().splitlines()
    )


def test_root_offers_dispatch_and_orchestrator_flags() -> None:
    """``check --`` offers tool dispatch and orchestrator flags."""
    values: tuple[str, ...] = _records(words=("exactus", "--"), prefix="--")
    for expected in (
        "--lints",
        "--coverage_tests",
        "--docs",
        "--tools",
        "--pipeline",
        "--root",
        "--config",
    ):
        expect_in(member=expected, container=values)


def test_aliases_not_offered_but_matchable() -> None:
    """Alias dispatch flags are hidden from candidates."""
    values: tuple[str, ...] = _records(words=("exactus", "--"), prefix="--")
    expect_not_in(member="--coverage", container=values)
    expect_not_in(member="--tests", container=values)


def test_tool_values_after_tools_flag() -> None:
    """``--tools`` offers exactus catalog identifiers."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--tools", ""),
        prefix="",
    )
    for expected in ("lints", "docs", "frontend"):
        expect_in(member=expected, container=values)


def test_remaining_tool_values() -> None:
    """Used ``--tools`` values are not re-offered."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--tools", "lints", ""),
        prefix="",
    )
    expect_not_in(member="lints", container=values)
    expect_in(member="docs", container=values)


def test_pipeline_values() -> None:
    """``--pipeline`` offers catalog pipeline identifiers."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--pipeline", ""),
        prefix="",
    )
    expect_in(member="unified", container=values)


def test_tools_pipeline_mutex() -> None:
    """``--tools`` use suppresses ``--pipeline`` (parser mutex)."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--tools", "lints", "--pi"),
        prefix="--pi",
    )
    expect_not_in(member="--pipeline", container=values)


def test_dispatch_flag_switches_to_tool_grammar() -> None:
    """``--lints`` activates the lints tool's options."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--lints", "--"),
        prefix="--",
    )
    expect_in(member="--no-fix", container=values)
    expect_not_in(member="--pipeline", container=values)


def test_screenshot_shortcut_merges_grammars() -> None:
    """``--url`` activates the merged shortcut grammar."""
    values: tuple[str, ...] = _records(
        words=("exactus", "--frontend", "--"),
        prefix="--",
    )
    expect_in(member="--actions", container=values)


def test_completion_subcommand_offers_shells() -> None:
    """``check completion`` offers the four shells."""
    values: tuple[str, ...] = _records(
        words=("exactus", "completion", ""),
        prefix="",
    )
    for expected in ("bash", "zsh", "fish", "powershell"):
        expect_in(member=expected, container=values)


def test_completion_command_at_root() -> None:
    """``completion`` is offered as a root subcommand."""
    values: tuple[str, ...] = _records(words=("exactus", "com"), prefix="com")
    expect_in(member="completion", container=values)


def test_root_values_complete_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--root`` values complete directories.

    Args:
        tmp_path: Working directory holding one subdirectory.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "project").mkdir()
    monkeypatch.chdir(path=tmp_path)
    stream: StringIO = StringIO()
    status: int = run_completion(
        catalog=_catalog(),
        arguments=(
            "--shell=bash",
            "--active-word-index=2",
            "--prefix=pro",
            "--word=check",
            "--word=--root",
            "--word=pro",
        ),
        out=stream,
    )
    expect_equal(actual=status, expected=_GroupFinalConstants_2.exit_ok)
    expect_in(
        member="project/",
        container=tuple(
            line.split(sep="\x1f", maxsplit=1)[0]
            for line in stream.getvalue().splitlines()
        ),
    )


def test_check_main_routes_complete() -> None:
    """``check __complete`` reaches the hidden endpoint."""
    StringIO()
    status: int = check_main(
        arguments=(
            "__complete",
            "--shell=bash",
            "--active-word-index=1",
            "--prefix=--lin",
            "--word=check",
            "--word=--lin",
        ),
    )
    expect_equal(actual=status, expected=_GroupFinalConstants_2.exit_ok)


def test_check_main_routes_completion_command() -> None:
    """``check completion bash`` prints a script to stdout."""
    status: int = check_main(arguments=("completion", "bash"))
    expect_equal(actual=status, expected=_GroupFinalConstants_2.exit_ok)


def test_completion_command_prints_script() -> None:
    """The user command emits a shell adapter on stdout."""
    stream: StringIO = StringIO()
    status: int = completion_run(arguments=("zsh",), out=stream)
    expect_equal(actual=status, expected=0)
    expect_in(member="compdef", container=stream.getvalue())
    expect_in(
        member=(
            f"Completion protocol: {_GroupFinalConstants_4.protocol_version}"
        ),
        container=stream.getvalue(),
    )


def test_install_and_uninstall_bash(tmp_path: Path) -> None:
    """Bash install manages a block inside the user's ``.bashrc``.

    Args:
        tmp_path: Fake user home.

    """
    result: InstallResult = install(
        shell=CompletionShell.BASH,
        command_name="check",
        launcher=("check",),
        home=tmp_path,
    )
    expect_true(condition=result.changed)
    expect_equal(actual=result.path, expected=tmp_path / ".bashrc")
    expect_in(
        member="complete -F",
        container=result.path.read_text(encoding="utf-8"),
    )
    removed: InstallResult = uninstall(
        shell=CompletionShell.BASH,
        command_name="check",
        home=tmp_path,
    )
    expect_true(condition=removed.changed)
    expect_not_in(
        member=Constants.check_begin,
        container=result.path.read_text(encoding="utf-8"),
    )


def test_install_zsh_ensures_compinit(tmp_path: Path) -> None:
    """The zsh block enables compsys before registering.

    Args:
        tmp_path: Fake user home.

    """
    result: InstallResult = install(
        shell=CompletionShell.ZSH,
        command_name="check",
        launcher=("check",),
        home=tmp_path,
    )
    expect_equal(actual=result.path, expected=tmp_path / ".zshrc")
    text: str = result.path.read_text(encoding="utf-8")
    expect_in(member="autoload -Uz compinit && compinit", container=text)
    expect_in(member="compdef _check_completion check", container=text)


def test_install_refuses_foreign_file(tmp_path: Path) -> None:
    """A non-check provider file is never overwritten.

    Args:
        tmp_path: Fake user home.

    """
    target: Path = tmp_path / ".config" / "fish" / "completions" / "check.fish"
    target.parent.mkdir(parents=True)
    _ = target.write_text(data="# user content\n", encoding="utf-8")
    result: InstallResult = install(
        shell=CompletionShell.FISH,
        command_name="check",
        launcher=("check",),
        home=tmp_path,
    )
    expect_false(condition=result.changed)
    expect_equal(actual=result.status, expected=InstallStatus.BROKEN)
    expect_equal(
        actual=target.read_text(encoding="utf-8"),
        expected="# user content\n",
    )


def test_uninstall_refuses_foreign_file(tmp_path: Path) -> None:
    """A non-check provider file is never deleted.

    Args:
        tmp_path: Fake user home.

    """
    target: Path = tmp_path / ".config" / "fish" / "completions" / "check.fish"
    target.parent.mkdir(parents=True)
    _ = target.write_text(data="# user content\n", encoding="utf-8")
    result: InstallResult = uninstall(
        shell=CompletionShell.FISH,
        command_name="check",
        home=tmp_path,
    )
    expect_false(condition=result.changed)
    expect_true(condition=target.is_file())


def test_powershell_profile_block_lifecycle(tmp_path: Path) -> None:
    """Profile-block install and removal preserve user content.

    Args:
        tmp_path: Fake user home.

    """
    profile: Path = (
        tmp_path
        / ".config"
        / "powershell"
        / "Microsoft.PowerShell_profile.ps1"
    )
    profile.parent.mkdir(parents=True)
    _ = profile.write_text(
        data="# my profile\nSet-StrictMode\n",
        encoding="utf-8",
    )
    result: InstallResult = install(
        shell=CompletionShell.POWERSHELL,
        command_name="check",
        launcher=("check",),
        home=tmp_path,
    )
    expect_true(condition=result.changed)
    text: str = profile.read_text(encoding="utf-8")
    expect_in(member=Constants.check_begin, container=text)
    expect_in(member="Set-StrictMode", container=text)
    removed: InstallResult = uninstall(
        shell=CompletionShell.POWERSHELL,
        command_name="check",
        home=tmp_path,
    )
    expect_true(condition=removed.changed)
    text = profile.read_text(encoding="utf-8")
    expect_not_in(member=Constants.check_begin, container=text)
    expect_in(member="Set-StrictMode", container=text)


def test_install_idempotent_replaces_block(tmp_path: Path) -> None:
    """Reinstalling replaces the managed block, never duplicates.

    Args:
        tmp_path: Fake user home.

    """
    for _ in range(2):
        _ = install(
            shell=CompletionShell.POWERSHELL,
            command_name="check",
            launcher=("check",),
            home=tmp_path,
        )
    profile: Path = (
        tmp_path
        / ".config"
        / "powershell"
        / "Microsoft.PowerShell_profile.ps1"
    )
    expect_equal(
        actual=profile.read_text(encoding="utf-8").count(
            Constants.check_begin,
        ),
        expected=1,
    )
    expect_equal(
        actual=profile.read_text(encoding="utf-8").count(Constants.check_end),
        expected=1,
    )


def test_diagnose_missing_and_healthy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing shells diagnose cleanly; installed ones healthy.

    Args:
        tmp_path: Fake user home.
        monkeypatch: Isolate profile discovery from the user's environment.

    """
    monkeypatch.delenv(name="XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv(name="ZDOTDIR", raising=False)
    results: tuple[ShellDiagnosis, ...] = diagnose(
        command_name="check",
        launcher=("python3",),
        home=tmp_path,
    )
    for diagnosis in results:
        expect_equal(actual=diagnosis.status, expected=InstallStatus.MISSING)
    _ = install(
        shell=CompletionShell.FISH,
        command_name="check",
        launcher=("python3",),
        home=tmp_path,
    )
    results = diagnose(
        command_name="check",
        launcher=("python3",),
        home=tmp_path,
    )
    fish: ShellDiagnosis = next(
        item for item in results if item.shell is CompletionShell.FISH
    )
    expect_equal(actual=fish.status, expected=InstallStatus.HEALTHY)


def test_diagnose_missing_launcher(tmp_path: Path) -> None:
    """An installed provider with an unresolvable launcher fails.

    Args:
        tmp_path: Fake user home.

    """
    _ = install(
        shell=CompletionShell.FISH,
        command_name="check",
        launcher=("definitely-not-a-real-binary-xyz",),
        home=tmp_path,
    )
    results: tuple[ShellDiagnosis, ...] = diagnose(
        command_name="check",
        launcher=("definitely-not-a-real-binary-xyz",),
        home=tmp_path,
    )
    fish: ShellDiagnosis = next(
        item for item in results if item.shell is CompletionShell.FISH
    )
    expect_equal(actual=fish.status, expected=InstallStatus.LAUNCHER_MISSING)


def test_diagnose_stale_protocol(tmp_path: Path) -> None:
    """A foreign protocol version diagnoses as stale.

    Args:
        tmp_path: Fake user home.

    """
    target: Path = tmp_path / ".config" / "fish" / "completions" / "check.fish"
    target.parent.mkdir(parents=True)
    _ = target.write_text(data="# Completion protocol: 99\n", encoding="utf-8")
    results: tuple[ShellDiagnosis, ...] = diagnose(
        command_name="check",
        launcher=("check",),
        home=tmp_path,
    )
    fish: ShellDiagnosis = next(
        item for item in results if item.shell is CompletionShell.FISH
    )
    expect_equal(actual=fish.status, expected=InstallStatus.STALE)


def test_diagnose_command_output(tmp_path: Path) -> None:
    """``check completion all --diagnose`` prints per-shell status.

    Args:
        tmp_path: Fake user home.

    """
    stream: StringIO = StringIO()
    status: int = completion_run(
        arguments=("all", "--diagnose"),
        out=stream,
        home=tmp_path,
    )
    expect_equal(actual=status, expected=0)
    output: str = stream.getvalue()
    for shell in ("bash", "zsh", "fish", "powershell"):
        expect_in(member=shell, container=output)
    expect_in(member="missing", container=output)


def test_completion_command_install_action(tmp_path: Path) -> None:
    """``--install`` writes the provider file through the command.

    Args:
        tmp_path: Fake user home.

    """
    stream: StringIO = StringIO()
    status: int = completion_run(
        arguments=("fish", "--install"),
        out=stream,
        home=tmp_path,
    )
    expect_equal(actual=status, expected=0)
    expect_true(
        condition=(
            tmp_path / ".config" / "fish" / "completions" / "exactus.fish"
        ).is_file(),
    )


def test_launcher_resolution_covers_module_script_and_path_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapters retain a runnable interpreter for modules and zipapps.

    Args:
        tmp_path: Disposable launcher files.
        monkeypatch: Restore invocation and PATH resolution.

    """
    monkeypatch.setattr(
        target=launcher_module,
        name="argv",
        value=["__main__.py"],
    )
    expect_equal(
        actual=launcher_module.resolve_launcher(command_name="exactus"),
        expected=(launcher_module.executable, "-m", "exactus"),
    )
    launcher: Path = tmp_path / "exactus.py"
    launcher.write_text(data="print('example')")
    monkeypatch.setattr(
        target=launcher_module,
        name="argv",
        value=[str(object=launcher)],
    )
    expect_equal(
        actual=launcher_module.resolve_launcher(command_name="exactus"),
        expected=(launcher_module.executable, str(object=launcher)),
    )
    archive: Path = tmp_path / "exactus"
    archive.write_bytes(data=b"#!/usr/bin/env python3\nPK\x03\x04")
    monkeypatch.setattr(target=launcher_module, name="argv", value=["exactus"])
    monkeypatch.setenv(name="PATH", value=str(object=tmp_path))
    archive.chmod(mode=493)
    monkeypatch.chdir(path=tmp_path.parent)
    expect_equal(
        actual=launcher_module.resolve_launcher(command_name="exactus"),
        expected=(launcher_module.executable, str(object=archive)),
    )
    monkeypatch.setenv(name="PATH", value="")
    expect_equal(
        actual=launcher_module.resolve_launcher(command_name="exactus"),
        expected=("exactus",),
    )


def test_completion_launch_needs_only_standard_library(tmp_path: Path) -> None:
    """TAB runs with site packages disabled and leaves its cwd untouched.

    Args:
        tmp_path: Empty working directory for side-effect checks.

    """
    source: str = str(object=Path(__file__).resolve().parents[4])
    code: str = (
        f"\nimport sys\nsys.path.insert(0, "
        f"{source!r}"
        f")\nsys.argv = ['exactus', '__complete', '--shell=bash',\n       "
        f"     '--active-word-index=1', '--prefix=--lin',\n            '--"
        f"word=exactus', '--word=--lin']\nfrom exactus.__main__ import mai"
        f"n\nstatus = main()\nblocked = ('playwright', 'PIL', 'jinja2', 'e"
        f"xactus.tools.frontend.core',\n           'exactus.tools.lints.co"
        f"re', 'exactus.tools.coverage_tests.core')\nassert not any(name i"
        f"n sys.modules for name in blocked)\nraise SystemExit(status)\n"
    )
    result: CompletedProcess[str] = run(
        args=[executable, "-S", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    expect_equal(actual=result.returncode, expected=0)
    expect_equal(actual=result.stderr, expected="")
    expect_true(condition=result.stdout.startswith("--lints\x1f"))
    expect_equal(actual=tuple(tmp_path.iterdir()), expected=())


def test_canonical_registration_markers(tmp_path: Path) -> None:
    """Only the Exactus block is removed from a mixed user profile.

    Args:
        tmp_path: Isolated shell profile directory.

    """
    profile: Path = tmp_path / ".bashrc"
    foreign: str = "# custom provider\ncomplete -F custom other\n"
    _ = profile.write_text(data=foreign, encoding="utf-8")
    installed: InstallResult = install(
        shell=CompletionShell.BASH,
        command_name="exactus",
        launcher=("exactus",),
        home=tmp_path,
    )
    expect_true(condition=installed.changed)
    content: str = profile.read_text(encoding="utf-8")
    expect_in(member="# >>> exactus completion >>>", container=content)
    expect_in(member=foreign, container=content)
    removed: InstallResult = uninstall(
        shell=CompletionShell.BASH,
        command_name="exactus",
        home=tmp_path,
    )
    expect_true(condition=removed.changed)
    content = profile.read_text(encoding="utf-8")
    expect_in(member=foreign, container=content)
    expect_not_in(member=Constants.block_begin, container=content)


def test_default_tool_provider_uses_exactus_catalog() -> None:
    """Exactus catalog entries flow into TOOL provider candidates."""
    context: CompletionContext = CompletionContext(
        command_path=(),
        words=(),
        prefix="",
        recognized=RecognizedArguments(
            flags=frozenset(),
            values=(),
            multi_values=(),
            positionals=(),
            command_path=(),
        ),
        working_directory=Path("/"),
    )
    registry: dict[ProviderId, CompletionProvider] = default_providers(
        tools=tuple(_GroupFinalConstants_3.tool_descriptions.items()),
    )
    values: tuple[str, ...] = tuple(
        candidate.value
        for candidate in registry[ProviderId.TOOL].complete(context=context)
    )
    expect_in(member="lints", container=values)
    expect_in(member="coverage_tests", container=values)
