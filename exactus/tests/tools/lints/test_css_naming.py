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
    CssNamingConvention,
    CssNamingExemption,
    CssNamingFinding,
    CssNamingReferences,
    CssNamingSettings,
    collect_css_references,
    convention_spec,
    exemption_spec,
    parse_convention,
    parse_exemption,
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
        data="""\
/* --x1: 1; --x2: 2; */
content: "--x3: 3";
""",
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


def test_convention_registry_members_and_value(tmp_path: Path) -> None:
    """Registered stems obey member lists and quantity/value steps.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--spacing-4: 16px;--spacing-9: 9px;--spacing-2: 4px;}",
        encoding="utf-8",
    )
    convention: CssNamingConvention = CssNamingConvention(
        stem="--spacing-",
        members=frozenset({"2", "4", "8"}),
        unit="px",
        step=4.0,
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
        settings=CssNamingSettings(conventions=frozenset({convention})),
    )
    rules: list[str] = [finding.rule for finding in findings]
    expect_equal(
        actual=sorted(set(rules)),
        expected=["CSSN011"],
    )
    expect_true(
        condition=any(
            finding.reason == "registry-member" for finding in findings
        ),
    )
    expect_true(
        condition=any(
            finding.reason == "registry-value" for finding in findings
        ),
    )


def test_convention_scope_and_versions(tmp_path: Path) -> None:
    """Scoped registries apply per component; version stems pass.

    Args:
        tmp_path: Per-test project directory.

    """
    inside: Path = tmp_path / "components" / "button" / "vars.css"
    outside: Path = tmp_path / "components" / "menu" / "vars.css"
    inside.parent.mkdir(parents=True)
    outside.parent.mkdir(parents=True)
    _ = inside.write_text(
        data=":root {--pad-1: 1px;--pad-2: 2px;}",
        encoding="utf-8",
    )
    _ = outside.write_text(
        data=":root {--pad-1: 1px;--pad-2: 2px;--theme-v2: dark;}",
        encoding="utf-8",
    )
    settings: CssNamingSettings = CssNamingSettings(
        conventions=frozenset(
            {
                CssNamingConvention(
                    stem="--pad-",
                    scope="components/button",
                ),
                CssNamingConvention(stem="--theme-v", versions=True),
            },
        ),
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(inside, outside),
        settings=settings,
    )
    expect_true(
        condition=any(
            finding.file == outside and finding.rule == "CSSN001"
            for finding in findings
        ),
    )
    expect_false(
        condition=any(finding.file == inside for finding in findings),
    )
    expect_false(
        condition=any("theme-v" in finding.message for finding in findings),
    )


def test_scoped_exemptions_and_roots(tmp_path: Path) -> None:
    """Exemptions suppress findings only inside their scope; roots map.

    Args:
        tmp_path: Per-test project directory.

    """
    legacy: Path = tmp_path / "web" / "legacy" / "a.css"
    other: Path = tmp_path / "web" / "modern" / "b.css"
    legacy.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    body: str = ":root {--item1: 1px;--item2: 2px;}"
    _ = legacy.write_text(data=body, encoding="utf-8")
    _ = other.write_text(data=body, encoding="utf-8")
    settings: CssNamingSettings = CssNamingSettings(
        exemptions=frozenset(
            {
                CssNamingExemption(
                    name="--item*",
                    scope="legacy",
                    rationale="vendor shim",
                ),
            },
        ),
        component_roots=frozenset(
            {("web/legacy", "legacy"), ("web/modern", "modern")},
        ),
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(legacy, other),
        settings=settings,
    )
    expect_false(
        condition=any(finding.file == legacy for finding in findings),
    )
    expect_true(
        condition=any(
            finding.file == other and "modern" in finding.message
            for finding in findings
        ),
    )


def test_rule_severity_override_and_validation(tmp_path: Path) -> None:
    """Per-rule severities resolve through policy; bad values reject.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data=":root {--item1: 1px;--item2: 2px;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
        settings=CssNamingSettings(
            rule_severity=frozenset({("CSSN001", "info")}),
        ),
    )
    expect_true(
        condition=all(finding.severity == "info" for finding in findings),
    )
    with pytest.raises(expected_exception=ValueError, match="severity"):
        _ = scan_css_naming(
            root=tmp_path,
            files=(file,),
            settings=CssNamingSettings(
                rule_severity=frozenset({("CSSN001", "fatal")}),
            ),
        )


def test_javascript_and_html_reference_collection(tmp_path: Path) -> None:
    """Statically knowable references come from JS and HTML sources.

    Args:
        tmp_path: Per-test project directory.

    """
    js: Path = tmp_path / "app.js"
    _ = js.write_text(
        data=dedent(
            text="""\
    el.style.setProperty("--accent", v);
    const old = el.style.getPropertyValue("--legacy-1");
    theme("--brand");
    dynamic.setProperty(name, v);
    """,
        ),
        encoding="utf-8",
    )
    html: Path = tmp_path / "index.html"
    _ = html.write_text(
        data="""\
<div style="--inline-1: 2px; color: var(--accent)">x</div>
""",
        encoding="utf-8",
    )
    css: Path = tmp_path / "vars.css"
    _ = css.write_text(
        data=":root {--accent: red;--legacy-1: 1px;--brand: blue;"
        "--inline-1: 1px;--unused-1: 3px;--unused-2: 4px;}",
        encoding="utf-8",
    )
    references: CssNamingReferences = collect_css_references(
        files=(js, html),
    )
    expect_true(condition=references.dynamic)
    expect_false(condition=references.complete)
    expect_true(
        condition={
            "--accent",
            "--legacy-1",
            "--brand",
            "--inline-1",
        }
        <= references.names,
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(css,),
        settings=CssNamingSettings(check_extended=True),
        reference_files=(js, html),
    )
    expect_true(
        condition={
            finding.canonical
            for finding in findings
            if finding.rule == "CSSN008"
        }
        == {"--unused-1", "--unused-2"},
    )
    expect_true(
        condition=all(
            finding.severity == "info"
            for finding in findings
            if finding.rule == "CSSN008"
        ),
    )


def test_complete_reference_coverage_escalates(tmp_path: Path) -> None:
    """Complete coverage upgrades CSSN008; literals count as use.

    Args:
        tmp_path: Per-test project directory.

    """
    js: Path = tmp_path / "app.js"
    _ = js.write_text(
        data="""\
node.style.setProperty("--used", "1px");
""",
        encoding="utf-8",
    )
    css: Path = tmp_path / "vars.css"
    _ = css.write_text(
        data=":root {--used: 1px;--orphan: 2px;}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(css,),
        settings=CssNamingSettings(check_extended=True),
        reference_files=(js,),
    )
    advisory: list[CssNamingFinding] = [
        finding for finding in findings if finding.rule == "CSSN008"
    ]
    expect_equal(actual=len(advisory), expected=1)
    expect_equal(actual=advisory[0].canonical, expected="--orphan")
    expect_equal(actual=advisory[0].severity, expected="warning")


def test_finding_contract_carries_evidence(tmp_path: Path) -> None:
    """Findings expose scope, canonical names, members and locations.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "vars.css"
    _ = file.write_text(
        data="@media (min-width: 1px) {.card {--item1: 1px;}"
        ".list {--item2: 2px;}}",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
    )
    family: list[CssNamingFinding] = [
        finding for finding in findings if finding.rule == "CSSN001"
    ]
    expect_equal(actual=len(family), expected=2)
    expect_true(
        condition=all(
            finding.members == ("--item1", "--item2") for finding in family
        ),
    )
    expected_related: int = 2
    expect_true(
        condition=all(
            len(finding.related) == expected_related for finding in family
        ),
    )
    expect_true(
        condition=any("@media" in finding.scope for finding in family),
    )
    expect_true(
        condition=all(
            finding.reason == "distinct-ordinals" for finding in family
        ),
    )
    expect_true(
        condition=all(finding.confidence == "high" for finding in family),
    )
    expect_true(
        condition=any(finding.canonical == "--item1" for finding in family),
    )


def test_fixture_edge_cases(tmp_path: Path) -> None:
    """Escaped, unicode, repeated and malformed CSS do not corrupt output.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "edge.css"
    _ = file.write_text(
        data=":root {--café-1: 1px;--café-2: 2px;"
        "--item\\-escaped1: 4px;--item\\-escaped2: 5px;"
        "--dup1: 1px;--dup1: 2px;--dup2: 3px;}"
        "@media (a) { @supports (b) { .x {--item1: 1px;} }"
        "/* unclosed",
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] | None
    findings = (
        scan_css_naming(
            root=tmp_path,
            files=(file,),
        )
        or None
    )
    expect_true(
        condition=isinstance(findings, tuple),
    )
    if isinstance(findings, tuple):
        expect_true(
            condition=any("caf" in finding.message for finding in findings),
        )


def test_imports_shadow_dom_and_large_inputs(tmp_path: Path) -> None:
    """Imports, :host/::part scopes and large inputs stay bounded.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "component.css"
    _ = file.write_text(
        data=dedent(
            text="""\
    @import "tokens.css";
    :host {--item1: 1px;--item2: 2px;}
    ::part(label) {color: var(--item1);}
    """,
        )
        + "".join(
            f"""\
.x{i} {{--dup: {i}px;}}
"""
            for i in range(800)
        ),
        encoding="utf-8",
    )
    findings: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=(file,),
    )
    family: list[CssNamingFinding] = [
        finding for finding in findings if finding.rule == "CSSN001"
    ]
    expect_equal(actual=len(family), expected=2)
    expect_true(
        condition=all(":host" in finding.scope for finding in family),
    )


def test_deterministic_under_shuffled_discovery(tmp_path: Path) -> None:
    """File discovery order never changes the emitted findings.

    Args:
        tmp_path: Per-test project directory.

    """
    files: list[Path] = []
    for index, content in enumerate(
        iterable=(
            ":root {--item1: 1px;}",
            ":root {--item2: 2px;}",
            ":root {--item3: 3px;}",
        ),
    ):
        file: Path = tmp_path / f"f{index}.css"
        _ = file.write_text(data=content, encoding="utf-8")
        files.append(file)
    baseline: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=files,
    )
    shuffled: tuple[CssNamingFinding, ...] = scan_css_naming(
        root=tmp_path,
        files=list(reversed(files)),
    )
    expect_equal(actual=baseline, expected=shuffled)


def test_registry_specs_round_trip() -> None:
    """Convention and exemption specs serialize and parse losslessly."""
    convention: CssNamingConvention = parse_convention(
        spec=(
            "stem=--spacing-;members=1,2,4;unit=px;step=4;"
            "versions=0;scope=components/button;"
            "rationale=design scale;review=2026-01"
        ),
    )
    expect_equal(
        actual=parse_convention(
            spec=convention_spec(convention=convention),
        ),
        expected=convention,
    )
    expect_equal(
        actual=convention.members,
        expected=frozenset({"1", "2", "4"}),
    )
    exemption: CssNamingExemption = parse_exemption(
        spec="name=--legacy-;scope=web;rationale=shim",
    )
    expect_equal(
        actual=parse_exemption(
            spec=exemption_spec(exemption=exemption),
        ),
        expected=exemption,
    )
    with pytest.raises(expected_exception=ValueError, match="stem"):
        _ = parse_convention(spec="unit=px")
    with pytest.raises(expected_exception=ValueError, match="unknown"):
        _ = parse_exemption(spec="name=--x;bogus=1")
