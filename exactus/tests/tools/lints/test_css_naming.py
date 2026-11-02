# Copyright (c) 2026
"""Regression tests for numeric CSS custom-property naming."""

from pathlib import Path
from textwrap import dedent

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.lints.css_naming import (
    CssNamingFinding,
    CssNamingSettings,
    scan_css_naming,
)


def test_parallel_numeric_families(tmp_path: Path) -> None:
    """Detect parallel numbered families but not isolated identifiers.

    Args:
        tmp_path: Per-test project directory.

    """
    css: Path = tmp_path / "component" / "style.css"
    css.parent.mkdir()
    _ = css.write_text(
        data=dedent(
            text="""\
    --placeholderT1: 1px;
    --placeholderT2: 2px;
    --placeholderP1: 3px;
    --placeholderP2: 4px;
    --plan1B: 1px;
    --spacing-4: 4px;
    """,
        ),
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=[css],
    )
    expect_equal(
        actual=len(
            [finding for finding in findings if finding.rule == "CSSN001"],
        ),
        expected=4,
    )
    expect_true(
        condition=all("plan1B" not in finding.message for finding in findings),
    )


def test_mask_comments_and_strings(tmp_path: Path) -> None:
    """Ignore declarations embedded in CSS comments and strings.

    Args:
        tmp_path: Per-test project directory.

    """
    css: Path = tmp_path / "style.css"
    _ = css.write_text(
        data='/* --x1: 1; --x2: 2; */\ncontent: "--x3: 3";\n',
        encoding="utf-8",
    )
    expect_false(condition=bool(scan_css_naming(root=tmp_path, files=[css])))


def test_arbitrary_identifier(tmp_path: Path) -> None:
    """Flag padded arbitrary identifiers.

    Args:
        tmp_path: Per-test project directory.

    """
    css: Path = tmp_path / "style.css"
    _ = css.write_text(data="--plan023-big: 10px;", encoding="utf-8")
    expect_true(
        condition=any(
            finding.rule == "CSSN002"
            for finding in scan_css_naming(root=tmp_path, files=[css])
        ),
    )


def test_numeric_policies_and_unit_consistency(tmp_path: Path) -> None:
    """Allow numeric units and registered scales; detect contradictory values.

    Args:
        tmp_path: Per-test project directory.

    """
    css: Path = tmp_path / "theme.css"
    _ = css.write_text(
        data=dedent(
            text="""\
    :root {
    --duration-200ms: 200ms;
    --delay-100ms: 800ms;
    --spacing-4: 4px;
    --spacing-8: 8px;
    --grid-columns-12: 12;
    --theme-v2: dark;
    }
    """,
        ),
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(css,),
        settings=CssNamingSettings(
            registered_scales=frozenset({"--spacing-"}),
        ),
    )
    expect_equal(
        actual=[finding.rule for finding in findings],
        expected=["CSSN004"],
    )


def test_cross_file_component_and_isolation(tmp_path: Path) -> None:
    """Combine CSS from one component while isolating unrelated components.

    Args:
        tmp_path: Per-test project directory.

    """
    a: Path = tmp_path / "components" / "dialog" / "a.css"
    b: Path = tmp_path / "components" / "dialog" / "nested" / "b.css"
    c: Path = tmp_path / "components" / "menu" / "menu.css"
    for file, content in (
        (a, ":root {--placeholderT1: var(--base-x);}"),
        (b, ":root {--placeholderT2: var(--base-y);}"),
        (c, ":root {--placeholderT1: 1px;}"),
    ):
        file.parent.mkdir(parents=True, exist_ok=True)
        _ = file.write_text(data=content, encoding="utf-8")
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(a, b, c),
    )
    expect_equal(actual=len(findings), expected=2)
    expect_true(
        condition=all("dialog" in finding.message for finding in findings),
    )


def test_two_groups_one_index_is_not_parallel(tmp_path: Path) -> None:
    """One ordinal per subgroup does not establish a parallel sequence.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--placeholderT1: 1px;--placeholderP1: 2px;}",
        encoding="utf-8",
    )
    expect_false(condition=bool(scan_css_naming(root=tmp_path, files=(file,))))


def test_parallel_groups_have_error_severity(tmp_path: Path) -> None:
    """Parallel groups are a stronger structural defect than one sequence.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--placeholderT1: 1px;--placeholderT2: 2px;"
        "--placeholderP1: 1px;--placeholderP2: 2px;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
    )
    expect_equal(
        actual=len(
            [finding for finding in findings if finding.rule == "CSSN003"],
        ),
        expected=1,
    )
    expect_equal(
        actual=next(
            finding for finding in findings if finding.rule == "CSSN003"
        ).severity,
        expected="error",
    )


def test_configuration_can_disable_scan(tmp_path: Path) -> None:
    """An explicit policy switch prevents all naming analysis.

    Args:
        tmp_path: Per-test project directory.

    """
    expect_false(
        condition=bool(
            scan_css_naming(
                root=tmp_path,
                files=(tmp_path / "missing.css",),
                settings=CssNamingSettings(enabled=False),
            ),
        ),
    )


def test_extended_alias_warning(tmp_path: Path) -> None:
    """Only extended checks report weak evidence of duplicate aliases.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--item1: red;--item2: red;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
        settings=CssNamingSettings(check_extended=True),
    )
    expect_true(
        condition={finding.rule for finding in findings}
        >= {"CSSN001", "CSSN006", "CSSN010"},
    )


def test_inconsistent_separators_are_one_family(tmp_path: Path) -> None:
    """Treat equivalent dashed/undashed ordinals as one semantic family.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--item1: 1px;--item-2: 2px;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
        settings=CssNamingSettings(check_extended=True),
    )
    expect_true(
        condition={finding.rule for finding in findings}
        >= {"CSSN001", "CSSN007"},
    )


def test_css_alias_depth_and_cycle(tmp_path: Path) -> None:
    """Detect too-deep static aliases and cycles only in extended mode.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--a:var(--b);--b:var(--c);--c:var(--d);"
        "--d:var(--e);--e:1px;--cycle1:var(--cycle2);"
        "--cycle2:var(--cycle1);}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
        settings=CssNamingSettings(check_extended=True, max_alias_depth=2),
    )
    expect_true(
        condition={finding.rule for finding in findings} >= {"CSSN009"},
    )
    expect_false(
        condition=any(
            finding.rule == "CSSN009"
            for finding in scan_css_naming(root=tmp_path, files=(file,))
        ),
    )


def test_invalid_thresholds_are_rejected(tmp_path: Path) -> None:
    """Validate settings before accessing source files.

    Args:
        tmp_path: Per-test project directory.

    """
    with pytest.raises(expected_exception=ValueError, match="at least two"):
        _ = scan_css_naming(
            root=tmp_path,
            files=(),
            settings=CssNamingSettings(min_members=1),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="must be positive",
    ):
        _ = scan_css_naming(
            root=tmp_path,
            files=(),
            settings=CssNamingSettings(max_alias_depth=0),
        )


def test_namespaced_parallel_hyphenated_families(tmp_path: Path) -> None:
    """Identify the T/P pattern with conventional CSS dash separators.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--placeholder-t-1:1px;--placeholder-t-2:2px;"
        "--placeholder-p-1:3px;--placeholder-p-2:4px;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
    )
    expect_equal(
        actual=len(
            [finding for finding in findings if finding.rule == "CSSN003"],
        ),
        expected=1,
    )
