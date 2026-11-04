# Copyright (c) 2026
"""Verify native project grouping and nested Ruff style ownership."""

from __future__ import annotations

from json import loads
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from exactus.packages.all_lints import (
    AuditRunner,
    ResolvedRuffPolicy,
    RuffRunResult,
    RuffStabilizer,
    RuffStabilizerOptions,
    ToolSpec,
)
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
    private_call,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


@pytest.mark.parametrize(
    ("tool", "carrier", "flag"),
    [
        ("basedpyright", "basedpyrightconfig.json", "--project"),
        ("pyrefly", "pyrefly.toml", "-c"),
        ("tsc", "tsconfig.json", "--project"),
    ],
)
def test_native_groups_keep_their_project(
    tmp_path: Path,
    tool: str,
    carrier: str,
    flag: str,
) -> None:
    """Each subtree receives its own native project selector.

    Args:
        tmp_path: Independent project tree.
        tool: Analyzer identifier.
        carrier: Native config filename.
        flag: Explicit config selector.

    """
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    config: Path = nested / carrier
    config.write_text(
        data="{}" if carrier.endswith(".json") else "",
        encoding="utf-8",
    )
    file: Path = nested / "sample.py"
    file.touch()
    runner: AuditRunner = AuditRunner(root=tmp_path, workers=1)
    spec: ToolSpec = ToolSpec(
        name=tool,
        executable=tool,
        parser=tool,
        suffixes=frozenset({".py"}),
        arguments=(),
    )
    grouped: ToolSpec = cast(
        typ="ToolSpec",
        val=private_call(
            owner=runner,
            name="_scoped_spec",
            spec=spec,
            file=Path("nested/sample.py"),
        ),
    )
    expect_in(member=flag, container=grouped.arguments)
    expect_equal(actual=grouped.arguments[-1], expected=str(object=config))


def test_compact_overrides_do_not_escape_into_nested_style(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested Ruff carriers retain their own formatting configuration.

    Args:
        tmp_path: Independent project tree.
        monkeypatch: Pytest patching helper.

    """

    def accept(
        _self: RuffStabilizer,
        *,
        args: tuple[str, ...],
    ) -> RuffRunResult:
        """Accept every Ruff invocation without touching files.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        Returns:
            A successful typed run result with empty output.

        """
        return RuffRunResult(
            argv=args,
            returncode=0,
            stdout=b"",
            stderr=b"",
            duration_seconds=0.0,
        )

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=accept)
    root_file: Path = tmp_path / "root.py"
    root_file.touch()
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    (nested / "ruff.toml").write_text(
        data="""\
[format]
quote-style="single"
""",
        encoding="utf-8",
    )
    local_file: Path = nested / "local.py"
    local_file.touch()
    stabilizer: RuffStabilizer = RuffStabilizer(
        paths=[root_file, local_file],
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            capture_version=False,
            verify=False,
        ),
    )
    commands: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=stabilizer,
            name="_group_commands",
            args=(
                "ruff",
                "format",
                "--config",
                'format.quote-style="double"',
                str(object=root_file),
                str(object=local_file),
            ),
        ),
    )
    expect_equal(actual=len(commands), expected=2)
    root_command: tuple[str, ...] = next(
        command for command in commands if str(object=root_file) in command
    )
    nested_command: tuple[str, ...] = next(
        command for command in commands if str(object=local_file) in command
    )
    expect_true(condition="--config" in root_command)
    expect_false(condition="--config" in nested_command)


def test_ruff_rule_flags_follow_the_check_subcommand(tmp_path: Path) -> None:
    """Grouped Ruff commands put rule selection after the native subcommand.

    Args:
        tmp_path: Independent Ruff project.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
""",
        encoding="utf-8",
    )
    source: Path = tmp_path / "sample.py"
    source.write_text(
        data="""\
value = 1
""",
        encoding="utf-8",
    )
    runner: AuditRunner = AuditRunner(root=tmp_path, workers=1)
    spec: ToolSpec = ToolSpec(
        name="ruff",
        executable="ruff",
        parser="ruff",
        suffixes=frozenset({".py"}),
        arguments=("check", "--output-format", "json"),
    )
    scoped: ToolSpec = cast(
        typ="ToolSpec",
        val=private_call(
            owner=runner,
            name="_scoped_spec",
            spec=spec,
            file=Path("sample.py"),
        ),
    )
    expect_equal(actual=scoped.arguments[0], expected="check")
    expect_true(
        condition=scoped.arguments.index("--extend-ignore")
        > scoped.arguments.index("check"),
    )


def test_project_files_scope_limits_the_tsc_program(tmp_path: Path) -> None:
    """A scoped project config restricts ``tsc`` to discovered files.

    Args:
        tmp_path: Independent TypeScript project.

    """
    (tmp_path / "jsconfig.json").write_text(
        data="""\
{}
""",
        encoding="utf-8",
    )
    source: Path = tmp_path / "src" / "app.js"
    source.parent.mkdir()
    source.write_text(
        data="""\
const x = 1;
""",
        encoding="utf-8",
    )
    runner: AuditRunner = AuditRunner(root=tmp_path, workers=1)
    spec: ToolSpec = ToolSpec(
        name="typescript",
        executable="tsc",
        parser="typescript",
        suffixes=frozenset({".js"}),
        arguments=(
            "--noEmit",
            "--pretty",
            "false",
            "--project",
            str(object=tmp_path / "jsconfig.json"),
        ),
        project=True,
    )
    generated: Path
    with cast(
        typ="AbstractContextManager[ToolSpec]",
        val=private_call(
            owner=runner,
            name="_project_files_scope",
            spec=spec,
            files=[Path("src/app.js")],
        ),
    ) as scoped:
        index: int = scoped.arguments.index("--project")
        generated = Path(scoped.arguments[index + 1])
        expect_true(condition=generated.is_file())
        expect_equal(
            actual=loads(s=generated.read_text(encoding="utf-8")),
            expected={
                "extends": "./jsconfig.json",
                "files": [],
                "include": ["src/app.js"],
            },
        )
    expect_false(condition=generated.exists())


def test_project_files_scope_forwards_files_without_a_carrier(
    tmp_path: Path,
) -> None:
    """A carrier-less project spec checks the discovered files directly.

    Args:
        tmp_path: Independent TypeScript project.

    """
    runner: AuditRunner = AuditRunner(root=tmp_path, workers=1)
    spec: ToolSpec = ToolSpec(
        name="typescript",
        executable="tsc",
        parser="typescript",
        suffixes=frozenset({".js"}),
        arguments=("--noEmit", "--pretty", "false"),
        project=True,
    )
    with cast(
        typ="AbstractContextManager[ToolSpec]",
        val=private_call(
            owner=runner,
            name="_project_files_scope",
            spec=spec,
            files=[Path("a.js"), Path("b.js")],
        ),
    ) as scoped:
        expect_equal(
            actual=scoped.arguments,
            expected=("--noEmit", "--pretty", "false", "a.js", "b.js"),
        )
    direct: ToolSpec = ToolSpec(
        name="eslint",
        executable="eslint",
        parser="eslint",
        suffixes=frozenset({".js"}),
        arguments=("--format", "json"),
    )
    with cast(
        typ="AbstractContextManager[ToolSpec]",
        val=private_call(
            owner=runner,
            name="_project_files_scope",
            spec=direct,
            files=[Path("a.js")],
        ),
    ) as unchanged:
        expect_equal(actual=unchanged, expected=direct)


def test_policy_emits_py313_when_no_carrier_sets_target(
    tmp_path: Path,
) -> None:
    """Unconfigured roots get the documented ``py313`` fallback.

    Args:
        tmp_path: Independent project tree.

    """
    policy: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(project_root=tmp_path),
    )
    expect_equal(actual=policy.target_version, expected="py313")
    expect_in(
        member='target-version = "py313"',
        container=policy.fallback_config,
    )
    argv: tuple[str, ...] = policy.check_argv(
        paths=(tmp_path / "a.py",),
    )
    expect_in(member='target-version = "py313"', container=argv)


def test_policy_suppresses_py313_when_carrier_sets_target(
    tmp_path: Path,
) -> None:
    """A carrier ``target-version`` removes the fallback entirely.

    Args:
        tmp_path: Independent project tree.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
target-version = "py311"
""",
        encoding="utf-8",
    )
    policy: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(project_root=tmp_path),
    )
    expect_equal(actual=policy.target_version, expected="py311")
    expect_equal(actual=policy.fallback_config, expected=())
    argv: tuple[str, ...] = policy.check_argv(
        paths=(tmp_path / "a.py",),
    )
    expect_false(condition='target-version = "py313"' in argv)
    expect_false(condition="--config" in argv)


def test_policy_captures_nested_and_extend_settings(
    tmp_path: Path,
) -> None:
    """Carrier metadata lands on the resolved policy verbatim.

    Args:
        tmp_path: Independent project tree.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
line-length = 100
target-version = "py312"
preview = true
extend-exclude = ["generated", "vendor"]
[tool.ruff.format]
quote-style = "single"
""",
        encoding="utf-8",
    )
    policy: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(project_root=tmp_path),
    )
    expect_equal(actual=policy.line_length, expected=100)
    expect_equal(actual=policy.target_version, expected="py312")
    expect_true(condition=policy.preview is True)
    expect_in(member="generated", container=policy.exclusions)
    expect_in(member="vendor", container=policy.exclusions)
    expect_in(member="line-length", container=policy.settings)
    expect_in(member="extend-exclude", container=policy.settings)
    expect_in(member="format.quote-style", container=policy.settings)


def test_compact_overrides_respect_explicit_root_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root carrier keys suppress only their compact counterpart.

    Args:
        tmp_path: Independent project tree.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff.format]
quote-style = "single"
""",
        encoding="utf-8",
    )
    target: Path = tmp_path / "app.py"
    target.touch()

    def accept(
        _self: RuffStabilizer,
        *,
        args: tuple[str, ...],
    ) -> RuffRunResult:
        """Accept every Ruff invocation without touching files.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        Returns:
            A successful typed run result with empty output.

        """
        return RuffRunResult(
            argv=args,
            returncode=0,
            stdout=b"",
            stderr=b"",
            duration_seconds=0.0,
        )

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=accept)
    stabilizer: RuffStabilizer = RuffStabilizer(
        paths=[target],
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            verify=False,
        ),
    )
    commands: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=stabilizer,
            name="_group_commands",
            args=(
                "ruff",
                "format",
                "--config",
                "format.skip-magic-trailing-comma = false",
                str(object=target),
            ),
        ),
    )
    expect_equal(actual=len(commands), expected=1)
    command: tuple[str, ...] = commands[0]
    expect_false(
        condition=any(
            value.startswith("format.quote-style") for value in command
        ),
    )
    expect_true(
        condition=any("docstring-code-format" in value for value in command),
    )


def test_carrier_magic_trailing_comma_choice_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A carrier-set trailing-comma style suppresses the compact default.

    Args:
        tmp_path: Independent project tree.
        monkeypatch: Pytest patching helper.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff.format]
skip-magic-trailing-comma = true
""",
        encoding="utf-8",
    )
    target: Path = tmp_path / "app.py"
    target.touch()

    def accept(
        _self: RuffStabilizer,
        *,
        args: tuple[str, ...],
    ) -> RuffRunResult:
        """Accept every Ruff invocation without touching files.

        Args:
            _self: Stabilizer instance the patched method is bound to.
            args: Complete argument vector.

        Returns:
            A successful typed run result with empty output.

        """
        return RuffRunResult(
            argv=args,
            returncode=0,
            stdout=b"",
            stderr=b"",
            duration_seconds=0.0,
        )

    monkeypatch.setattr(target=RuffStabilizer, name="_run", value=accept)
    stabilizer: RuffStabilizer = RuffStabilizer(
        paths=[target],
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            verify=False,
        ),
    )
    commands: tuple[tuple[str, ...], ...] = cast(
        typ="tuple[tuple[str, ...], ...]",
        val=private_call(
            owner=stabilizer,
            name="_group_commands",
            args=(
                "ruff",
                "format",
                "--config",
                "format.skip-magic-trailing-comma = false",
                str(object=target),
            ),
        ),
    )
    expect_equal(actual=len(commands), expected=1)
    command: tuple[str, ...] = commands[0]
    expect_false(
        condition=any(
            value.startswith("format.skip-magic-trailing-comma")
            for value in command
        ),
    )
    expect_true(
        condition=any("docstring-code-format" in value for value in command),
    )


def test_isolated_policy_ignores_native_configuration(
    tmp_path: Path,
) -> None:
    """``--isolated`` drops the carrier and restores strict defaults.

    Args:
        tmp_path: Independent project tree.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
target-version = "py311"
""",
        encoding="utf-8",
    )
    policy: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            isolated=True,
        ),
    )
    expect_equal(actual=policy.carrier, expected=None)
    expect_equal(actual=policy.settings, expected=())
    expect_true(condition=policy.isolated)
    expect_in(member="--select", container=policy.rule_flags)
    expect_in(member="ALL", container=policy.rule_flags)
    argv: tuple[str, ...] = policy.format_argv(
        paths=(tmp_path / "a.py",),
    )
    expect_in(member="--isolated", container=argv)
    fixed: tuple[str, ...] = policy.fix_argv(
        paths=(tmp_path / "a.py",),
    )
    expect_in(member="--isolated", container=fixed)
    expect_in(member="check", container=fixed)


def test_policy_fingerprint_distinguishes_resolutions(
    tmp_path: Path,
) -> None:
    """Unsafe fixes and isolation produce distinct fingerprints.

    Args:
        tmp_path: Independent project tree.

    """
    base: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(project_root=tmp_path),
    )
    unsafe: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            unsafe_fixes=True,
        ),
    )
    isolated: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(
            project_root=tmp_path,
            isolated=True,
        ),
    )
    expect_true(condition=base.fingerprint != unsafe.fingerprint)
    expect_true(condition=base.fingerprint != isolated.fingerprint)
    expect_equal(actual=len(base.fingerprint), expected=16)


def test_verify_argv_exercises_every_override(tmp_path: Path) -> None:
    """The capability probe carries compact and fallback pairs.

    Args:
        tmp_path: Independent project tree.

    """
    target: Path = tmp_path / "app.py"
    policy: ResolvedRuffPolicy = ResolvedRuffPolicy.resolve(
        options=RuffStabilizerOptions(project_root=tmp_path),
    )
    probe: tuple[str, ...] = policy.verify_argv(path=target)
    expect_in(member="check", container=probe)
    expect_in(member="--exit-zero", container=probe)
    expect_in(member=str(object=target), container=probe)
    for pair in (*policy.compact_config, *policy.fallback_config):
        expect_in(member=pair, container=probe)
