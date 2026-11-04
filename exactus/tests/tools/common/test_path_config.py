# Copyright (c) 2026
"""Verify scoped configuration, native carriers and public provenance."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.common.config import (
    ConfigError,
    ConfigResolver,
    EffectiveRequest,
    OptionProvenance,
    ShowConfigReport,
    files_for_path,
    show_config,
    stacked_provenance,
)
from exactus.tools.common.path_filters import (
    PathFilters,
    ScopedMatcher,
    default_excludes,
    glob_match,
)
from exactus.tools.lints.core import LintExactusConfig, LintsConfigResolver


def test_scoped_chain_and_provenance(tmp_path: Path) -> None:
    """Merge nearest scalars and farthest-first lists with carrier paths.

    Args:
        tmp_path: Independent project.

    """
    (tmp_path / "pyproject.toml").write_text(
        data=dedent(
            text="""\
    [tool.exactus]
    reports-dir="reports"
    exclude=["build/**"]
    [tool.exactus.docs]
    context-lines=2
    """,
        ),
        encoding="utf-8",
    )
    folder: Path = tmp_path / "nested"
    folder.mkdir()
    local: Path = folder / "pyproject.toml"
    local.write_text(
        data=dedent(
            text="""\
    [tool.exactus]
    exclude=["skip/**"]
    [tool.exactus.docs]
    context-lines=7
    """,
        ),
        encoding="utf-8",
    )
    candidate: Path = folder / "source.py"
    candidate.touch()
    resolver: ConfigResolver = ConfigResolver(root=tmp_path)
    expect_equal(
        actual=resolver.stacked(path=candidate, table=("docs",)),
        expected={"context-lines": 7},
    )
    expect_equal(
        actual=resolver.filters(path=candidate).excludes,
        expected=("build/**", "nested/skip/**"),
    )
    expect_equal(
        actual=stacked_provenance(
            files=resolver.files(path=candidate),
            path=("docs",),
        ),
        expected={"context-lines": local},
    )
    report: ShowConfigReport = show_config(
        root=tmp_path,
        path=candidate,
        tools=(
            EffectiveRequest(tool="docs", module="exactus.tools.docs.main"),
        ),
    )
    expect_equal(actual=report.reports_dir, expected=tmp_path / "reports")
    expect_equal(actual=report.to_json()["schema_version"], expected=1)
    matching: list[OptionProvenance] = [
        o for o in report.tools[0].options if o.name == "context_lines"
    ]
    expect_equal(actual=matching[0].source, expected=local)
    expect_equal(actual=matching[0].value, expected="7")


@pytest.mark.parametrize("pattern", ["**/build/**", "build/**"])
def test_root_recursive_globs(pattern: str) -> None:
    """Canonical recursive globs include root directory matches.

    Args:
        pattern: Recursive or root-explicit glob.

    """
    expect_true(condition=glob_match(relative="build/a.py", pattern=pattern))


def test_scoped_matching(tmp_path: Path) -> None:
    """Nested filters affect their own subtree without excluding siblings.

    Args:
        tmp_path: Independent root.

    """
    matcher: ScopedMatcher = ScopedMatcher(
        root=tmp_path,
        scoped=(("nested", PathFilters(excludes=("skip/**",))),),
    )
    expect_false(condition=matcher.matches(path=tmp_path / "nested/skip/a.py"))
    expect_true(condition=matcher.matches(path=tmp_path / "other/skip/a.py"))
    expect_false(
        condition=matcher.matches(path=tmp_path.parent / "outside.py"),
    )


@pytest.mark.parametrize(
    ("name", "section"),
    [
        ("ruff.toml", "ruff"),
        (".ruff.toml", "ruff"),
        ("tsconfig.json", "typescript"),
        ("basedpyrightconfig.json", "basedpyright"),
        ("pyrefly.toml", "pyrefly"),
    ],
)
def test_native_carriers(tmp_path: Path, name: str, section: str) -> None:
    """Each native tool selects its nearest supported carrier.

    Args:
        tmp_path: Independent root.
        name: Native config filename.
        section: Tool identity.

    """
    directory: Path = tmp_path / "nested"
    directory.mkdir()
    carrier: Path = directory / name
    carrier.touch()
    source: Path = directory / "a.py"
    source.touch()
    expect_equal(
        actual=ConfigResolver(root=tmp_path).nearest_native(
            path=source,
            sections=(section,),
        ),
        expected=carrier,
    )


def test_boundary_and_root_marker(tmp_path: Path) -> None:
    """Nested root markers terminate inheritance and escapes are rejected.

    Args:
        tmp_path: Independent root.

    """
    (tmp_path / "pyproject.toml").write_text(
        data="""\
[tool.exactus.docs]
context-lines=2
""",
        encoding="utf-8",
    )
    directory: Path = tmp_path / "nested"
    directory.mkdir()
    carrier: Path = directory / "pyproject.toml"
    carrier.write_text(
        data="""\
[tool.exactus]
root=true
""",
        encoding="utf-8",
    )
    expect_equal(
        actual=tuple(
            f.path for f in files_for_path(path=directory, boundary=tmp_path)
        ),
        expected=(carrier,),
    )
    with pytest.raises(expected_exception=ConfigError):
        files_for_path(path=tmp_path.parent, boundary=tmp_path)
    with pytest.raises(expected_exception=ConfigError):
        files_for_path(path=tmp_path / "missing", boundary=tmp_path)


def test_dynamic_reports_exclusion(tmp_path: Path) -> None:
    """Explicit reports destinations participate in canonical exclusions.

    Args:
        tmp_path: Independent root.

    """
    patterns: tuple[str, ...] = default_excludes(
        root=tmp_path,
        reports_dir=Path("artifacts/reports"),
    )
    expect_false(
        condition=PathFilters(excludes=patterns).matches(
            relative="artifacts/reports/result.json",
        ),
    )
    expect_false(
        condition=PathFilters(excludes=patterns).matches(
            relative="nested/site-packages/module.py",
        ),
    )


def test_nested_lint_settings_preserve_ownership_and_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested switches and string settings apply without run controls.

    Args:
        tmp_path: Independent source tree.
        monkeypatch: Isolated explicit-argument environment.

    """
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    (nested / "pyproject.toml").write_text(
        data=(
            """\
[tool.exactus.lints]
no-organize=false
no-infer=true
line-length=101
workers=99
no-fix=false
css-naming-extended=true
"""
        ),
        encoding="utf-8",
    )
    source: Path = nested / "source.py"
    source.touch()
    base: LintExactusConfig = LintExactusConfig(
        organize=False,
        fix=False,
        workers=2,
    )
    resolver: LintsConfigResolver = LintsConfigResolver(
        root=tmp_path,
    )
    resolved: LintExactusConfig = resolver.resolve(path=source, base=base)
    expect_true(condition=resolved.organize)
    expect_false(condition=resolved.infer)
    expect_false(condition=resolved.fix)
    expect_equal(actual=resolved.workers, expected=2)
    expect_equal(actual=resolved.strings.line_length, expected=101)
    expect_true(condition=resolved.css_naming.check_extended)
    expect_true(condition=resolver.resolve(path=source, base=base) is resolved)
    monkeypatch.setenv(
        name="EXACTUS_EXPLICIT_ARGUMENTS",
        value='["--no-organize", "--line-length=79"]',
    )
    explicit: LintExactusConfig = LintsConfigResolver(root=tmp_path).resolve(
        path=source,
        base=base,
    )
    expect_false(condition=explicit.organize)
    expect_equal(
        actual=explicit.strings.line_length,
        expected=base.strings.line_length,
    )


def test_unknown_nested_tool_key_is_rejected(tmp_path: Path) -> None:
    """Encountered nested tool tables cannot silently drop unknown settings.

    Args:
        tmp_path: Independent source tree.

    """
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    (nested / "pyproject.toml").write_text(
        data="""\
[tool.exactus.lints]
unknown-setting=true
""",
        encoding="utf-8",
    )
    source: Path = nested / "source.py"
    source.touch()
    with pytest.raises(expected_exception=ConfigError, match="unknown option"):
        ConfigResolver(root=tmp_path).options(path=source, tool="lints")


def test_native_filters_are_scoped_to_their_declaring_folder(
    tmp_path: Path,
) -> None:
    """Native excludes and includes apply only below their configuration.

    Args:
        tmp_path: Independent source tree.

    """
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    (nested / "pyproject.toml").write_text(
        data="""\
[tool.ruff]
exclude=["skip.py"]
""",
        encoding="utf-8",
    )
    source: Path = nested / "skip.py"
    source.touch()
    resolver: LintsConfigResolver | ConfigResolver = ConfigResolver(
        root=tmp_path,
    )
    expect_false(
        condition=resolver.native_filters(path=source, tool="ruff").matches(
            relative="nested/skip.py",
        ),
    )
    sibling: Path = tmp_path / "skip.py"
    sibling.touch()
    expect_true(
        condition=resolver.native_filters(path=sibling, tool="ruff").matches(
            relative="skip.py",
        ),
    )


def test_explicit_config_report_anchor_matches_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit external carrier anchors reports beside its declaration.

    Args:
        tmp_path: Independent carrier directory.
        monkeypatch: Explicit configuration channel.

    """
    project: Path = tmp_path / "project"
    project.mkdir()
    carrier: Path = tmp_path / "pyproject.toml"
    carrier.write_text(
        data="""\
[tool.exactus]
reports-dir="reports"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(name="EXACTUS_CONFIG", value=str(object=carrier))
    report: ShowConfigReport = show_config(root=project)
    expect_equal(actual=report.reports_dir, expected=tmp_path / "reports")
