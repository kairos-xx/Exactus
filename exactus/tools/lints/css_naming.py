# Copyright (c) 2026
"""Audit numbered CSS custom-property families without guessing their meaning.

The scanner uses Exactus's CSS lexer/parser, groups declarations by component,
and never changes source. Numeric identifiers are not automatically invalid:
repeated ordinal families provide evidence of non-semantic naming whereas
registered scales and documented numeric units can carry precise meaning.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from re import Match, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, final

from exactus.tools.lints.css_tokens import CssDeclaration, parse_declarations

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class CssNamingSettings:
    """Configure contextual CSS custom-property naming audits.

    Attributes:
        enabled: Execute CSS naming checks.
        min_members: Minimum unique ordinals for a numbered family.
        parallel_groups: Minimum parallel subfamilies for CSSN003.
        parallel_members: Minimum unique ordinals per parallel group.
        registered_scales: Exact registered scale stems (e.g. ``--spacing``).
        ignored_names: Explicit names exempt from naming diagnostics.
        check_values: Compare explicit unit-bearing names with their values.
        check_extended: Run heuristic diagnostics with weaker evidence.
        max_alias_depth: Maximum allowed consecutive static alias hops.

    """

    enabled: bool = True
    min_members: int = 2
    parallel_groups: int = 2
    parallel_members: int = 2
    registered_scales: frozenset[str] = frozenset()
    ignored_names: frozenset[str] = frozenset()
    check_values: bool = True
    check_extended: bool = False
    max_alias_depth: int = 3


@final
@dataclass(frozen=True, slots=True)
class CssNamingFinding:
    """A suspicious custom-property declaration or family.

    Attributes:
        rule: Stable CSSN identifier.
        file: Source stylesheet.
        line: One-based source line.
        message: Diagnostic with relevant family evidence.
        severity: Error, warning or information.

    """

    rule: str
    file: Path
    line: int
    message: str
    severity: str = "warning"


@final
class Constants:
    """Regex patterns and policy for numeric token names.

    Attributes:
        numbered: Custom-property name with an ordinal and optional suffix.
        subgroup: Trailing single-letter or dash-delimited subgroup marker.
        measured: Names encoding a unit-bearing numeric value.
        structural: Numeric values with a unit or technical quantity.
        reference: Static references to custom properties.
        suspicious_roots: Generic names that convey little semantic role.
        rules: Stable rule registry and severity.
        minimum_family: Minimum meaningful ordinal family size.
        arbitrary_digits: Digits regarded as an arbitrary identifier.

    """

    numbered: Final[Pattern[str]] = compile_pattern(
        pattern=r"^(--[\w-]*?)(\d+)([A-Za-z_-]*)$",
    )
    subgroup: Final[Pattern[str]] = compile_pattern(
        pattern=r"^(--[\w-]*?)(?:[-_]?([A-Z])|[-_]([a-z]))$",
    )
    measured: Final[Pattern[str]] = compile_pattern(
        pattern=r"""(?x)
            ^--(?:duration|delay|breakpoint|width|height|size)-
            (\d+(?:\.\d+)?)(ms|px|rem|em|s|%)$
        """,
    )
    structural: Final[Pattern[str]] = compile_pattern(
        pattern=r"""(?x)
            ^--(?:grid-columns|grid-rows|column-count|row-count)-\d+$
            |^--(?:theme|schema)-v\d+$
        """,
    )
    reference: Final[Pattern[str]] = compile_pattern(
        pattern=r"\bvar\(\s*(--[\w-]+)",
    )
    suspicious_roots: Final[frozenset[str]] = frozenset(
        {
            "--plan",
            "--placeholder",
            "--item",
            "--variant",
            "--color",
            "--token",
        },
    )
    minimum_family: Final[int] = 2
    arbitrary_digits: Final[int] = 3
    rules: Final[dict[str, str]] = {
        "CSSN001": "numbered-family",
        "CSSN002": "suspicious-numeric-identifier",
        "CSSN003": "parallel-numbered-families",
        "CSSN004": "numeric-name-value-mismatch",
        "CSSN005": "ambiguous-numeric-abbreviation",
        "CSSN006": "possible-numeric-alias",
        "CSSN007": "inconsistent-family-delimiters",
        "CSSN008": "possibly-unused-custom-property",
        "CSSN009": "excessive-alias-depth",
        "CSSN010": "generic-numbered-token",
    }


def _component(*, file: Path, root: Path) -> Path:
    """Return a deterministic component key, independent of absolute root.

    Args:
        file: Declaring stylesheet.
        root: Audited project root.

    Returns:
        Component-relative directory, using a ``components`` owner when known.

    """
    relative: Path = (
        file.resolve().relative_to(root.resolve())
        if file.resolve().is_relative_to(root.resolve())
        else file
    )
    parts: tuple[str, ...] = relative.parts
    if "components" in parts and parts.index("components") + 1 < len(parts):
        index: int = parts.index("components")
        return Path(*parts[: index + 2])
    return relative.parent


def _entries(*, text: str, file: Path) -> list[CssDeclaration]:
    """Reuse Exactus's declaration lexer, including a fixture fallback.

    Args:
        text: CSS stylesheet or declaration-only fixture.
        file: Location of the stylesheet.

    Returns:
        Parsed declarations with source line locations.

    """
    declarations: list[CssDeclaration] = parse_declarations(
        text=text,
        file=file,
    )
    return (
        declarations
        if declarations or "{" in text
        else parse_declarations(text=f":root {{{text}}}", file=file)
    )


def _subfamily(*, stem: str) -> tuple[str, str]:
    """Separate an ordinal family into a common root and subgroup.

    Args:
        stem: Numeric-prefix portion of a property name.

    Returns:
        Root and single-letter subgroup, or stem and empty subgroup.

    """
    normalized: str = stem.rstrip("-_")
    match: Match[str] | None = Constants.subgroup.fullmatch(string=normalized)
    return (
        (match.group(1), match.group(2) or match.group(3) or "")
        if match
        else (normalized, "")
    )


def _numbered(
    *,
    declaration: CssDeclaration,
) -> tuple[str, str, str, str] | None:
    """Extract ordinal info unless a numeric convention applies.

    Args:
        declaration: Parsed CSS custom property.

    Returns:
        Stem, subgroup, ordinal and trailing suffix, or ``None``.

    """
    match: Match[str] | None = Constants.numbered.fullmatch(
        string=declaration.name,
    )
    if match is None or Constants.structural.fullmatch(
        string=declaration.name,
    ):
        return None
    root: str
    subgroup: str
    root, subgroup = _subfamily(stem=match.group(1))
    return root, subgroup, match.group(2), match.group(3)


type FamilyKey = tuple[Path, str, str, str]
type FamilyMember = tuple[CssDeclaration, str]
type FamilyMap = dict[FamilyKey, list[FamilyMember]]
type ParallelMap = dict[tuple[Path, str], dict[str, set[str]]]


def _collect(
    *,
    root: Path,
    files: Sequence[Path],
    policy: CssNamingSettings,
) -> tuple[
    FamilyMap,
    ParallelMap,
    list[CssDeclaration],
    list[CssNamingFinding],
]:
    """Parse stylesheet declarations and classify indexed family membership.

    Args:
        root: Audited project root.
        files: CSS files selected by the existing scope resolver.
        policy: Active naming policy.

    Returns:
        Families, parallel groups, declarations and immediate findings.

    """
    families: FamilyMap = defaultdict(list)
    parallel: ParallelMap = defaultdict(lambda: defaultdict(set))
    declarations: list[CssDeclaration] = []
    findings: list[CssNamingFinding] = []
    for file in sorted(set(files)):
        component: Path = _component(file=file, root=root)
        for declaration in _entries(
            text=file.read_text(encoding="utf-8"),
            file=file,
        ):
            if (
                not declaration.is_custom
                or declaration.name in policy.ignored_names
            ):
                continue
            declarations.append(declaration)
            measured: Match[str] | None = Constants.measured.fullmatch(
                string=declaration.name,
            )
            if measured is not None:
                expected: str = f"{measured.group(1)}{measured.group(2)}"
                if (
                    policy.check_values
                    and declaration.value.strip() != expected
                    and "var(" not in declaration.value
                    and "calc(" not in declaration.value
                ):
                    findings.append(
                        CssNamingFinding(
                            rule="CSSN004",
                            file=file,
                            line=declaration.line,
                            message=(
                                f"{declaration.name}"
                                f": "
                                f"{expected}"
                                f" != "
                                f"{declaration.value}"
                            ),
                        ),
                    )
                continue
            numbered: tuple[str, str, str, str] | None = _numbered(
                declaration=declaration,
            )
            if numbered is None:
                continue
            stem: str
            subgroup: str
            index: str
            suffix: str
            stem, subgroup, index, suffix = numbered
            if stem in {
                registered.rstrip("-_")
                for registered in policy.registered_scales
            }:
                continue
            families[(component, stem, subgroup, suffix)].append(
                (declaration, index),
            )
            if subgroup:
                parallel[(component, stem)][subgroup].add(index)
            if (len(index) > 1 and index.startswith("0")) or (
                len(index) >= Constants.arbitrary_digits and suffix
            ):
                findings.append(
                    CssNamingFinding(
                        rule="CSSN002",
                        file=file,
                        line=declaration.line,
                        message=(
                            f"{declaration.name}"
                            f": numeric name lacks semantic role."
                        ),
                    ),
                )
    return families, parallel, declarations, findings


def _family_findings(
    *,
    families: FamilyMap,
    policy: CssNamingSettings,
) -> list[CssNamingFinding]:
    """Report distinct-number families and optional weak-evidence patterns.

    Args:
        families: Parsed per-component numeric families.
        policy: Numeric naming thresholds and advisory settings.

    Returns:
        Family-level and declaration-level diagnostics.

    """
    findings: list[CssNamingFinding] = []
    for (component, stem, subgroup, suffix), members in sorted(
        families.items(),
        key=lambda entry: str(object=entry[0]),
    ):
        distinct: set[str] = {number for _, number in members}
        if len(distinct) < policy.min_members:
            continue
        names: str = ", ".join(sorted({member.name for member, _ in members}))
        padded: bool = bool(suffix) and all(
            number.startswith("0") for _, number in members
        )
        for declaration, _ in members:
            findings.append(
                CssNamingFinding(
                    rule="CSSN001",
                    file=declaration.file,
                    line=declaration.line,
                    message=(
                        f"Family in {component}: {names}; use semantic names."
                    ),
                    severity="error" if padded else "warning",
                ),
            )
        if not policy.check_extended:
            continue
        if stem in Constants.suspicious_roots:
            findings.append(
                CssNamingFinding(
                    rule="CSSN010",
                    file=members[0][0].file,
                    line=members[0][0].line,
                    message=(
                        f"Generic family "
                        f"{stem}"
                        f"{subgroup}"
                        f"{suffix}"
                        f" lacks named roles."
                    ),
                    severity="info",
                ),
            )
        if len({member.value for member, _ in members}) == 1:
            findings.append(
                CssNamingFinding(
                    rule="CSSN006",
                    file=members[0][0].file,
                    line=members[0][0].line,
                    message=f"Numbered aliases {names} share the same value.",
                    severity="info",
                ),
            )
        spelling: set[str] = {
            member.name[: -(len(number) + len(suffix))]
            for member, number in members
        }
        if len(spelling) > 1:
            findings.append(
                CssNamingFinding(
                    rule="CSSN007",
                    file=members[0][0].file,
                    line=members[0][0].line,
                    message=(
                        f"Family {names} mixes numeric-prefix separator"
                        f" styles."
                    ),
                ),
            )
    return findings


def _parallel_findings(
    *,
    families: FamilyMap,
    parallel: ParallelMap,
    policy: CssNamingSettings,
) -> list[CssNamingFinding]:
    """Report parallel ordinal subfamilies under one semantic root.

    Args:
        families: Parsed indexed declarations.
        parallel: Per-component subgroup ordinals.
        policy: Parallel-family thresholds.

    Returns:
        Strong parallel-family errors and optional abbreviation notices.

    """
    findings: list[CssNamingFinding] = []
    for (component, root_name), groups in sorted(
        parallel.items(),
        key=lambda entry: str(object=entry[0]),
    ):
        qualifying: dict[str, set[str]] = {
            group: indices
            for group, indices in groups.items()
            if len(indices) >= policy.parallel_members
        }
        if len(qualifying) < policy.parallel_groups:
            continue
        members: list[CssDeclaration] = sorted(
            (
                declaration
                for (owner, stem, group, _suffix), entries in families.items()
                if owner == component
                and stem == root_name
                and group in qualifying
                for declaration, _ordinal in entries
            ),
            key=lambda declaration: (
                declaration.file.as_posix(),
                declaration.line,
                declaration.name,
            ),
        )
        labels: str = ", ".join(sorted(qualifying))
        names: str = ", ".join(sorted({member.name for member in members}))
        findings.append(
            CssNamingFinding(
                rule="CSSN003",
                file=members[0].file,
                line=members[0].line,
                message=f"Parallel {labels} in {component}: {names}.",
                severity="error",
            ),
        )
        if policy.check_extended:
            findings.append(
                CssNamingFinding(
                    rule="CSSN005",
                    file=members[0].file,
                    line=members[0].line,
                    message=(
                        f"Subgroups "
                        f"{labels}"
                        f" use ambiguous single-letter abbreviations."
                    ),
                    severity="info",
                ),
            )
    return findings


def _extended_findings(
    *,
    declarations: Sequence[CssDeclaration],
    policy: CssNamingSettings,
) -> list[CssNamingFinding]:
    """Audit static references without claiming dynamic-use completeness.

    Args:
        declarations: Parsed custom properties across the scope.
        policy: Thresholds for weak-evidence alias diagnostics.

    Returns:
        Low-confidence advisory findings, never automated rename proposals.

    """
    declared: dict[str, list[CssDeclaration]] = defaultdict(list)
    aliases: dict[str, frozenset[str]] = {}
    references: set[str] = set()
    for declaration in declarations:
        declared[declaration.name].append(declaration)
        targets: frozenset[str] = frozenset(
            Constants.reference.findall(string=declaration.value),
        )
        references.update(targets)
        aliases[declaration.name] = targets
    findings: list[CssNamingFinding] = [
        CssNamingFinding(
            rule="CSSN008",
            file=members[0].file,
            line=members[0].line,
            message=(
                f"{name} lacks known CSS references; dynamic use not checked."
            ),
            severity="info",
        )
        for name, members in sorted(declared.items())
        if name.startswith("--placeholder") and name not in references
    ]
    for name, members in sorted(declared.items()):
        stack: list[tuple[str, int, frozenset[str]]] = [
            (name, 0, frozenset({name})),
        ]
        reported: bool = False
        while stack and not reported:
            current: str
            depth: int
            seen: frozenset[str]
            current, depth, seen = stack.pop()
            for target in sorted(aliases.get(current, frozenset())):
                if target not in declared:
                    continue
                if target in seen or depth >= policy.max_alias_depth:
                    findings.append(
                        CssNamingFinding(
                            rule="CSSN009",
                            file=members[0].file,
                            line=members[0].line,
                            message=(
                                f"{name}"
                                f" has a cyclic or too-deep CSS alias chain."
                            ),
                            severity="info",
                        ),
                    )
                    reported = True
                    break
                stack.append((target, depth + 1, seen | {target}))
    return findings


def scan_css_naming(
    *,
    root: Path,
    files: Sequence[Path],
    settings: CssNamingSettings | None = None,
) -> tuple[CssNamingFinding, ...]:
    """Classify numeric CSS custom-property families without modifying code.

    Args:
        root: Project root used to select component identity.
        files: Stylesheets to inspect.
        settings: Optional explicit naming policy.

    Returns:
        Deterministically sorted warnings, errors and advisory diagnostics.

    Raises:
        OSError: If a stylesheet cannot be read.
        UnicodeError: If a stylesheet cannot be decoded as UTF-8.
        ValueError: If numeric family thresholds are invalid.

    """
    policy: CssNamingSettings = settings or CssNamingSettings()
    if not policy.enabled:
        return ()
    if (
        min(
            policy.min_members,
            policy.parallel_groups,
            policy.parallel_members,
        )
        < Constants.minimum_family
    ):
        msg: str = "CSS numeric-family thresholds must be at least two"
        raise ValueError(msg)
    if policy.max_alias_depth < 1:
        msg = "CSS alias depth must be positive"
        raise ValueError(msg)
    families: FamilyMap
    parallel: ParallelMap
    declarations: list[CssDeclaration]
    findings: list[CssNamingFinding]
    families, parallel, declarations, findings = _collect(
        root=root,
        files=files,
        policy=policy,
    )
    findings.extend(_family_findings(families=families, policy=policy))
    findings.extend(
        _parallel_findings(
            families=families,
            parallel=parallel,
            policy=policy,
        ),
    )
    if policy.check_extended:
        findings.extend(
            _extended_findings(declarations=declarations, policy=policy),
        )
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.file.as_posix(),
                finding.line,
                finding.rule,
                finding.message,
            ),
        ),
    )
