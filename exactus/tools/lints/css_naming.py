# Copyright (c) 2026
"""Audit numbered CSS custom-property families without guessing their meaning.

The scanner uses Exactus's CSS lexer/parser, groups declarations by component,
and never changes source. Numeric identifiers are not automatically invalid:
repeated ordinal families provide evidence of non-semantic naming whereas
registered scales and documented numeric units can carry precise meaning.

Deliberately unsupported (reported as advisory evidence, never guessed):
``@import`` targets are not followed — only declarations present in the
scanned file contribute; CSS Modules ``:local``/``:global`` and Shadow DOM
``:host``/``::part`` selectors are recorded as scope context rather than
interpreted; non-literal JavaScript property access marks reference coverage
incomplete so no property is ever called definitively unused.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from re import Match, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, final

from exactus.tools.lints.css_tokens import CssDeclaration, parse_declarations

if TYPE_CHECKING:
    from collections.abc import Sequence


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class CssNamingConvention:
    """One scoped semantic registry for a numbered property stem.

    A convention declares that a stem's ordinals are meaningful design
    tokens — not anonymous numeric identifiers — and can constrain
    which members exist and how name quantity maps onto value. Matched
    stems leave the generic family/parallel audits entirely; violations
    of the registry's own constraints are reported as ``CSSN011``.

    Attributes:
        stem: Registered stem, e.g. ``--spacing-`` or ``--theme-v``.
        members: Allowed ordinals; empty allows every ordinal.
        unit: Required value unit for correspondence checks.
        step: Expected ``value / ordinal`` ratio for quantity
            correspondence; only checked together with ``unit``.
        versions: Whether the stem encodes a version scale
            (``--theme-v2``); informational, exempts nothing extra.
        scope: Component-relative path prefix the registry applies to;
            empty matches every component.
        rationale: Why the registry exists, carried for reports.
        review: Optional reviewer or review-date metadata.

    """

    stem: str
    members: frozenset[str] = frozenset()
    unit: str | None = None
    step: float | None = None
    versions: bool = False
    scope: str = ""
    rationale: str = ""
    review: str | None = None


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class CssNamingExemption:
    """One scoped naming exemption with provenance metadata.

    Attributes:
        name: Exempt property name; a trailing ``-`` or ``*`` marks a
            stem prefix exemption instead of an exact name.
        scope: Component-relative path prefix the exemption applies
            to; empty matches every component.
        rationale: Why the exemption exists, carried for reports.
        review: Optional reviewer or review-date metadata.

    """

    name: str
    scope: str = ""
    rationale: str = ""
    review: str | None = None


@final
@dataclass(frozen=True, slots=True)
class CssNamingReferences:
    """Statically knowable custom-property use outside stylesheets.

    Attributes:
        names: Referenced property names from HTML and JavaScript.
        locations: ``(name, "file:line")`` evidence pairs, sorted.
        dynamic: Whether non-literal property access was observed;
            dynamic use means reference coverage is incomplete and no
            property may be reported as definitively unused.
        scanned: Files inspected.

    """

    names: frozenset[str]
    locations: tuple[tuple[str, str], ...] = ()
    dynamic: bool = False
    scanned: int = 0

    @property
    def complete(self) -> bool:
        """Report whether the collected evidence is exhaustive.

        Returns:
            ``True`` only when files were scanned and no dynamic access
            leaves reference coverage unknown.

        """
        return self.scanned > 0 and not self.dynamic

    def locations_for(self, *, name: str) -> tuple[str, ...]:
        """List recorded evidence locations for one property.

        Args:
            name: Custom-property name including the leading dashes.

        Returns:
            Sorted ``file:line`` references, possibly empty.

        """
        return tuple(
            location for owner, location in self.locations if owner == name
        )


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
        conventions: Scoped semantic registries for numbered stems.
        exemptions: Scoped naming exemptions carrying provenance.
        component_roots: Explicit ``(path prefix, component name)``
            overrides applied before the directory heuristic.
        rule_severity: ``(rule, severity)`` overrides resolved through
            the normal policy model.

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
    conventions: frozenset[CssNamingConvention] = frozenset()
    exemptions: frozenset[CssNamingExemption] = frozenset()
    component_roots: frozenset[tuple[str, str]] = frozenset()
    rule_severity: frozenset[tuple[str, str]] = frozenset()


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
        column: One-based source column when known.
        scope: Selector/at-rule nesting of the flagged declaration.
        canonical: Normalized property spelling (stem + ordinal +
            suffix) used to compare family members.
        members: Sorted names of the family the finding belongs to.
        related: ``file:line`` evidence locations supporting the
            finding (other family members, external references).
        confidence: ``high`` for deterministic evidence, ``advisory``
            when reference or semantic completeness is unknown.
        reason: Machine-readable reason code behind the rule.

    """

    rule: str
    file: Path
    line: int
    message: str
    severity: str = "warning"
    column: int = 1
    scope: str = ""
    canonical: str = ""
    members: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    confidence: str = "high"
    reason: str = ""


@final
class Constants:
    """Regex patterns and policy for numeric token names.

    Attributes:
        numbered: Custom-property name with an ordinal and optional suffix.
        subgroup: Trailing single-letter or dash-delimited subgroup marker.
        measured: Names encoding a unit-bearing numeric value.
        structural: Numeric values with a unit or technical quantity.
        reference: Static references to custom properties.
        property_call: Literal CSS property accessor calls in JS/HTML.
        dynamic_call: Non-literal accessor use (coverage unknown).
        quoted_literal: Quoted bodies containing a ``--name`` literal.
        bare_name: Custom-property name inside a quoted body.
        suspicious_roots: Generic names that convey little semantic role.
        rules: Stable rule registry and severity.
        severities: Allowed per-rule severity levels.
        minimum_family: Minimum meaningful ordinal family size.
        arbitrary_digits: Digits regarded as an arbitrary identifier.
        confidence_advisory: Rules whose evidence is never complete.
        dynamic_template: Dynamic template segment where a ``--name`` may
            be composed rather than written literally.

    """

    numbered: Final[Pattern[str]] = compile_pattern(
        pattern=r"^(--[\w-]*?)(\d+)([A-Za-z_-]*)$",
    )
    subgroup: Final[Pattern[str]] = compile_pattern(
        pattern=r"^(--[\w-]*?)(?:[-_]?([A-Z])|[-_]([a-z]))$",
    )
    measured: Final[Pattern[str]] = compile_pattern(
        pattern="""\
(?x)
            ^--(?:duration|delay|breakpoint|width|height|size)-
            (\\d+(?:\\.\\d+)?)(ms|px|rem|em|s|%)$
        """,
    )
    structural: Final[Pattern[str]] = compile_pattern(
        pattern="""\
(?x)
            ^--(?:grid-columns|grid-rows|column-count|row-count)-\\d+$
            |^--(?:theme|schema)-v\\d+$
        """,
    )
    reference: Final[Pattern[str]] = compile_pattern(
        pattern=r"\bvar\(\s*(--[\w-]+)",
    )
    property_call: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?:setProperty|getPropertyValue|removeProperty"
            r"|getPropertyPriority)\s*\(\s*[\"'`](--[\w-]+)[\"'`]"
        ),
    )
    dynamic_call: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?:setProperty|getPropertyValue|removeProperty"
            r"|getPropertyPriority)\s*\(\s*(?![\"'`\s)])\S"
        ),
    )
    dynamic_template: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"(?:setProperty|getPropertyValue|removeProperty"
            r"|getPropertyPriority)\s*\(\s*`[^`]*\$\{"
        ),
    )
    quoted_literal: Final[Pattern[str]] = compile_pattern(
        pattern=r"[\"'`]([^\"'`\n]*--[\w-]+[^\"'`\n]*)[\"'`]",
    )
    bare_name: Final[Pattern[str]] = compile_pattern(
        pattern=r"(--[\w-]+)",
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
        "CSSN011": "registry-violation",
    }
    severities: Final[frozenset[str]] = frozenset(
        {"error", "warning", "info"},
    )
    confidence_advisory: Final[frozenset[str]] = frozenset(
        {"CSSN005", "CSSN006", "CSSN008", "CSSN009", "CSSN010"},
    )


def _spec_pairs(*, spec: str, kind: str) -> dict[str, str]:
    """Split a ``key=value;key=value`` registry spec into a mapping.

    Args:
        spec: Serialized convention or exemption specification.
        kind: Registry kind used in validation messages.

    Returns:
        Key/value pairs in declaration order.

    Raises:
        ValueError: If a pair lacks ``=`` or repeats a key.

    """
    pairs: dict[str, str] = {}
    for pair in spec.split(sep=";"):
        if not pair.strip():
            continue
        if "=" not in pair:
            msg: str = f"{kind} spec pair {pair!r} lacks '='"
            raise ValueError(msg)
        key: str
        value: str
        key, _, value = pair.partition("=")
        key = key.strip()
        if key in pairs:
            msg = f"{kind} spec repeats key {key!r}"
            raise ValueError(msg)
        pairs[key] = value.strip()
    if not pairs:
        msg = f"{kind} spec is empty"
        raise ValueError(msg)
    return pairs


def parse_convention(*, spec: str) -> CssNamingConvention:
    """Parse one ``key=value;`` convention spec.

    Recognized keys: ``stem`` (required), ``members`` (comma-separated
    ordinals), ``unit``, ``step``, ``versions``, ``scope``,
    ``rationale`` and ``review``.

    Args:
        spec: Serialized convention, e.g.
            ``stem=--spacing-;unit=px;step=4``.

    Returns:
        The typed registry entry.

    Raises:
        ValueError: If the spec is malformed or ``stem`` is missing.

    """
    pairs: dict[str, str] = _spec_pairs(spec=spec, kind="convention")
    allowed: frozenset[str] = frozenset(
        {
            "stem",
            "members",
            "unit",
            "step",
            "versions",
            "scope",
            "rationale",
            "review",
        },
    )
    unknown: set[str] = set(pairs) - set(allowed)
    if unknown:
        msg: str = f"convention spec has unknown keys {sorted(unknown)}"
        raise ValueError(msg)
    if not pairs.get("stem"):
        msg = "convention spec requires a stem"
        raise ValueError(msg)
    step: float | None = None
    if pairs.get("step"):
        try:
            step = float(pairs["step"])
        except ValueError as error:
            msg = f"convention step {pairs["step"]!r} is not numeric"
            raise ValueError(msg) from error
    return CssNamingConvention(
        stem=pairs["stem"],
        members=frozenset(
            member
            for member in pairs.get("members", "").split(sep=",")
            if member
        ),
        unit=pairs.get("unit") or None,
        step=step,
        versions=pairs.get("versions", "").lower() in {"1", "true", "yes"},
        scope=pairs.get("scope", ""),
        rationale=pairs.get("rationale", ""),
        review=pairs.get("review") or None,
    )


def convention_spec(*, convention: CssNamingConvention) -> str:
    """Serialize a registry entry back into spec form.

    Args:
        convention: Typed registry entry.

    Returns:
        ``key=value;`` specification preserving every field.

    """
    pairs: list[str] = [f"stem={convention.stem}"]
    if convention.members:
        pairs.append(f"members={",".join(sorted(convention.members))}")
    if convention.unit is not None:
        pairs.append(f"unit={convention.unit}")
    if convention.step is not None:
        pairs.append(f"step={convention.step}")
    if convention.versions:
        pairs.append("versions=1")
    if convention.scope:
        pairs.append(f"scope={convention.scope}")
    if convention.rationale:
        pairs.append(f"rationale={convention.rationale}")
    if convention.review is not None:
        pairs.append(f"review={convention.review}")
    return ";".join(pairs)


def parse_exemption(*, spec: str) -> CssNamingExemption:
    """Parse one ``key=value;`` exemption spec.

    Recognized keys: ``name`` (required), ``scope``, ``rationale`` and
    ``review``.

    Args:
        spec: Serialized exemption, e.g. ``name=--legacy-;scope=ui``.

    Returns:
        The typed exemption entry.

    Raises:
        ValueError: If the spec is malformed or ``name`` is missing.

    """
    pairs: dict[str, str] = _spec_pairs(spec=spec, kind="exemption")
    unknown: set[str] = set(pairs) - {"name", "scope", "rationale", "review"}
    if unknown:
        msg: str = f"exemption spec has unknown keys {sorted(unknown)}"
        raise ValueError(msg)
    if not pairs.get("name"):
        msg = "exemption spec requires a name"
        raise ValueError(msg)
    return CssNamingExemption(
        name=pairs["name"],
        scope=pairs.get("scope", ""),
        rationale=pairs.get("rationale", ""),
        review=pairs.get("review") or None,
    )


def exemption_spec(*, exemption: CssNamingExemption) -> str:
    """Serialize an exemption entry back into spec form.

    Args:
        exemption: Typed exemption entry.

    Returns:
        ``key=value;`` specification preserving every field.

    """
    pairs: list[str] = [f"name={exemption.name}"]
    if exemption.scope:
        pairs.append(f"scope={exemption.scope}")
    if exemption.rationale:
        pairs.append(f"rationale={exemption.rationale}")
    if exemption.review is not None:
        pairs.append(f"review={exemption.review}")
    return ";".join(pairs)


def _in_scope(*, component: Path, scope: str) -> bool:
    """Report whether a component satisfies a scope path prefix.

    Args:
        component: Component key produced by ``_component``.
        scope: Component-relative prefix; empty matches everything.

    Returns:
        Whether the component lies inside the scoped prefix.

    """
    normalized: str = scope.strip().strip("/")
    return not normalized or (
        component.as_posix() == normalized
        or component.as_posix().startswith(normalized + "/")
    )


def _severity(*, rule: str, default: str, policy: CssNamingSettings) -> str:
    """Resolve a rule's severity through the configured policy table.

    Args:
        rule: Stable CSSN identifier.
        default: Severity used when no override exists.
        policy: Active naming policy.

    Returns:
        Configured or default severity level.

    """
    return dict(policy.rule_severity).get(rule, default)


def _component(
    *,
    file: Path,
    root: Path,
    roots: frozenset[tuple[str, str]] = frozenset(),
) -> Path:
    """Return a deterministic component key, independent of absolute root.

    Args:
        file: Declaring stylesheet.
        root: Audited project root.
        roots: Explicit ``(path prefix, component name)`` overrides
            matched longest-prefix first before the directory heuristic.

    Returns:
        Component-relative directory, using a ``components`` owner when known.

    """
    relative: Path = (
        file.resolve().relative_to(root.resolve())
        if file.resolve().is_relative_to(root.resolve())
        else file
    )
    for prefix, name in sorted(
        roots,
        key=lambda entry: len(entry[0]),
        reverse=True,
    ):
        normalized: str = prefix.strip().strip("/")
        if normalized and (
            relative.as_posix() == normalized
            or relative.as_posix().startswith(normalized + "/")
            or PurePosixPath(relative.as_posix()).match(
                path_pattern=f"{normalized}/**",
            )
        ):
            return Path(name)
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


def _exempt(
    *,
    declaration: CssDeclaration,
    component: Path,
    policy: CssNamingSettings,
) -> bool:
    """Report whether a declaration is exempt from naming diagnostics.

    Args:
        declaration: Parsed custom property.
        component: Owning component key.
        policy: Active naming policy.

    Returns:
        Whether an exact name or scoped stem exemption applies.

    """
    if declaration.name in policy.ignored_names:
        return True
    for exemption in policy.exemptions:
        if not _in_scope(component=component, scope=exemption.scope):
            continue
        prefix: bool = exemption.name.endswith(("-", "*"))
        stem: str = exemption.name.rstrip("*")
        if declaration.name == exemption.name or (
            prefix and declaration.name.startswith(stem)
        ):
            return True
    return False


def _convention(
    *,
    stem: str,
    component: Path,
    policy: CssNamingSettings,
) -> CssNamingConvention | None:
    """Find the registry governing a numbered stem in a component.

    Args:
        stem: Normalized family stem (ordinals and suffix removed).
        component: Owning component key.
        policy: Active naming policy.

    Returns:
        The longest matching scoped registry, or ``None``.

    """
    normalized: str = stem.rstrip("-_")
    for convention in sorted(
        policy.conventions,
        key=lambda entry: (len(entry.scope), len(entry.stem)),
        reverse=True,
    ):
        if convention.stem.rstrip("-_") == normalized and _in_scope(
            component=component,
            scope=convention.scope,
        ):
            return convention
    return None


def _registry_findings(
    *,
    declaration: CssDeclaration,
    index: str,
    convention: CssNamingConvention,
    policy: CssNamingSettings,
) -> list[CssNamingFinding]:
    """Validate a declaration against its registered convention.

    Args:
        declaration: Registered-stem custom property.
        index: Ordinal carried by the name.
        convention: Matched scoped registry.
        policy: Active naming policy.

    Returns:
        ``CSSN011`` violations; empty when the declaration conforms.

    """
    findings: list[CssNamingFinding] = []
    if convention.members and index not in convention.members:
        findings.append(
            CssNamingFinding(
                rule="CSSN011",
                file=declaration.file,
                line=declaration.line,
                message=(
                    f"{declaration.name}"
                    f" is not a member of registered scale "
                    f"{convention.stem}"
                    f" (allowed: {", ".join(sorted(convention.members))})."
                ),
                severity=_severity(
                    rule="CSSN011",
                    default="error",
                    policy=policy,
                ),
                scope=declaration.scope,
                canonical=declaration.name,
                reason="registry-member",
            ),
        )
    value: str = declaration.value.strip()
    if (
        convention.unit is not None
        and "var(" not in value
        and "calc(" not in value
    ):
        magnitude: float | None = None
        if value.endswith(convention.unit):
            try:
                magnitude = float(value[: -len(convention.unit)])
            except ValueError:
                magnitude = None
        expected: float | None = (
            float(index) * convention.step
            if convention.step is not None and index.isdigit()
            else None
        )
        if magnitude is None or (
            expected is not None and magnitude != expected
        ):
            findings.append(
                CssNamingFinding(
                    rule="CSSN011",
                    file=declaration.file,
                    line=declaration.line,
                    message=(
                        f"{declaration.name}"
                        f": {declaration.value}"
                        f" violates registry {convention.stem}"
                        f" (unit {convention.unit}"
                        + (
                            f", step {convention.step}"
                            if convention.step is not None
                            else ""
                        )
                        + ")."
                    ),
                    severity=_severity(
                        rule="CSSN011",
                        default="error",
                        policy=policy,
                    ),
                    scope=declaration.scope,
                    canonical=declaration.name,
                    reason="registry-value",
                ),
            )
    return findings


def collect_css_references(*, files: Sequence[Path]) -> CssNamingReferences:
    """Collect statically knowable custom-property use in other sources.

    Reads ``var(--name)``, ``setProperty``/``getPropertyValue``/
    ``removeProperty``/``getPropertyPriority`` calls and quoted
    ``--name`` literals inside HTML and JavaScript sources. Non-literal
    accessor arguments or interpolated templates mark coverage
    incomplete; an unknown property is then never reported as
    definitively unused.

    Args:
        files: Non-stylesheet sources to scan (HTML, JS, TS, and any
            embedded-template formats the caller includes).

    Returns:
        Referenced names with evidence locations and coverage state.

    """
    names: set[str] = set()
    locations: list[tuple[str, str]] = []
    dynamic: bool = False
    scanned: int = 0
    for file in sorted(set(files)):
        text: str = file.read_text(encoding="utf-8")
        scanned += 1
        dynamic = dynamic or bool(
            Constants.dynamic_call.search(string=text)
            or Constants.dynamic_template.search(string=text),
        )
        for pattern in (
            Constants.reference,
            Constants.property_call,
        ):
            for match in pattern.finditer(string=text):
                name: str = match.group(1)
                names.add(name)
                locations.append(
                    (
                        name,
                        f"{file.as_posix()}:"
                        f"{text.count(chr(10), 0, match.start()) + 1}",
                    ),
                )
        for literal in Constants.quoted_literal.finditer(string=text):
            for match in Constants.bare_name.finditer(
                string=literal.group(1),
            ):
                name = match.group(1)
                names.add(name)
                locations.append(
                    (
                        name,
                        f"{file.as_posix()}:"
                        f"{text.count(chr(10), 0, literal.start()) + 1}",
                    ),
                )
    return CssNamingReferences(
        names=frozenset(names),
        locations=tuple(sorted(set(locations))),
        dynamic=dynamic,
        scanned=scanned,
    )


type FamilyKey = tuple[Path, str, str, str]
type FamilyMember = tuple[CssDeclaration, str]
type FamilyMap = dict[FamilyKey, list[FamilyMember]]
type ParallelMap = dict[tuple[Path, str], dict[str, set[str]]]


def _classify(
    *,
    declaration: CssDeclaration,
    component: Path,
    policy: CssNamingSettings,
) -> tuple[FamilyKey | None, str, list[CssNamingFinding]]:
    """Classify one declaration into a family key and immediate findings.

    Args:
        declaration: Parsed custom property.
        component: Owning component key.
        policy: Active naming policy.

    Returns:
        Family key and ordinal when the declaration joins a numbered
        family, plus any declaration-level findings.

    """
    findings: list[CssNamingFinding] = []
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
                    file=declaration.file,
                    line=declaration.line,
                    message=(
                        f"{declaration.name}"
                        f": "
                        f"{expected}"
                        f" != "
                        f"{declaration.value}"
                    ),
                    severity=_severity(
                        rule="CSSN004",
                        default="warning",
                        policy=policy,
                    ),
                    scope=declaration.scope,
                    canonical=declaration.name,
                    reason="value-mismatch",
                ),
            )
        return None, "", findings
    numbered: tuple[str, str, str, str] | None = _numbered(
        declaration=declaration,
    )
    if numbered is None:
        return None, "", findings
    stem: str
    subgroup: str
    index: str
    suffix: str
    stem, subgroup, index, suffix = numbered
    convention: CssNamingConvention | None = _convention(
        stem=stem,
        component=component,
        policy=policy,
    )
    if convention is not None:
        findings.extend(
            _registry_findings(
                declaration=declaration,
                index=index,
                convention=convention,
                policy=policy,
            ),
        )
        return None, "", findings
    if stem in {
        registered.rstrip("-_") for registered in policy.registered_scales
    }:
        return None, "", findings
    if (len(index) > 1 and index.startswith("0")) or (
        len(index) >= Constants.arbitrary_digits and suffix
    ):
        findings.append(
            CssNamingFinding(
                rule="CSSN002",
                file=declaration.file,
                line=declaration.line,
                message=(
                    f"{declaration.name}: numeric name lacks semantic role."
                ),
                severity=_severity(
                    rule="CSSN002",
                    default="warning",
                    policy=policy,
                ),
                scope=declaration.scope,
                canonical=declaration.name,
                reason="padded-identifier",
            ),
        )
    return (component, stem, subgroup, suffix), index, findings


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
        component: Path = _component(
            file=file,
            root=root,
            roots=policy.component_roots,
        )
        for declaration in _entries(
            text=file.read_text(encoding="utf-8"),
            file=file,
        ):
            if not declaration.is_custom or _exempt(
                declaration=declaration,
                component=component,
                policy=policy,
            ):
                continue
            declarations.append(declaration)
            key: FamilyKey | None
            index: str
            produced: list[CssNamingFinding]
            key, index, produced = _classify(
                declaration=declaration,
                component=component,
                policy=policy,
            )
            findings.extend(produced)
            if key is None:
                continue
            families[key].append((declaration, index))
            if key[2]:
                parallel[(component, key[1])][key[2]].add(index)
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
        member_names: tuple[str, ...] = tuple(
            sorted({member.name for member, _ in members}),
        )
        names: str = ", ".join(member_names)
        locations: tuple[str, ...] = tuple(
            sorted(
                f"{member.file.as_posix()}:{member.line}"
                for member, _ in members
            ),
        )
        padded: bool = bool(suffix) and all(
            number.startswith("0") for _, number in members
        )
        for declaration, index in members:
            findings.append(
                CssNamingFinding(
                    rule="CSSN001",
                    file=declaration.file,
                    line=declaration.line,
                    message=(
                        f"Family in {component}: {names}; use semantic names."
                    ),
                    severity=_severity(
                        rule="CSSN001",
                        default="error" if padded else "warning",
                        policy=policy,
                    ),
                    scope=declaration.scope,
                    canonical=(
                        f"{stem}{subgroup}"
                        f"{int(index) if index.isdigit() else index}"
                        f"{suffix}"
                    ),
                    members=member_names,
                    related=locations,
                    reason="distinct-ordinals",
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
                    severity=_severity(
                        rule="CSSN010",
                        default="info",
                        policy=policy,
                    ),
                    scope=members[0][0].scope,
                    members=member_names,
                    related=locations,
                    confidence="advisory",
                    reason="generic-root",
                ),
            )
        if len({member.value for member, _ in members}) == 1:
            findings.append(
                CssNamingFinding(
                    rule="CSSN006",
                    file=members[0][0].file,
                    line=members[0][0].line,
                    message=f"Numbered aliases {names} share the same value.",
                    severity=_severity(
                        rule="CSSN006",
                        default="info",
                        policy=policy,
                    ),
                    scope=members[0][0].scope,
                    members=member_names,
                    related=locations,
                    confidence="advisory",
                    reason="shared-value",
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
                    severity=_severity(
                        rule="CSSN007",
                        default="warning",
                        policy=policy,
                    ),
                    scope=members[0][0].scope,
                    members=member_names,
                    related=locations,
                    reason="mixed-separators",
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
        member_names: tuple[str, ...] = tuple(
            sorted({member.name for member in members}),
        )
        names: str = ", ".join(member_names)
        locations: tuple[str, ...] = tuple(
            sorted(
                f"{member.file.as_posix()}:{member.line}" for member in members
            ),
        )
        findings.append(
            CssNamingFinding(
                rule="CSSN003",
                file=members[0].file,
                line=members[0].line,
                message=f"Parallel {labels} in {component}: {names}.",
                severity=_severity(
                    rule="CSSN003",
                    default="error",
                    policy=policy,
                ),
                scope=members[0].scope,
                members=member_names,
                related=locations,
                reason="parallel-subgroups",
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
                    severity=_severity(
                        rule="CSSN005",
                        default="info",
                        policy=policy,
                    ),
                    scope=members[0].scope,
                    members=member_names,
                    related=locations,
                    confidence="advisory",
                    reason="single-letter-subgroups",
                ),
            )
    return findings


def _extended_findings(
    *,
    declarations: Sequence[CssDeclaration],
    policy: CssNamingSettings,
    references: CssNamingReferences | None = None,
) -> list[CssNamingFinding]:
    """Audit static references without claiming dynamic-use completeness.

    Args:
        declarations: Parsed custom properties across the scope.
        policy: Thresholds for weak-evidence alias diagnostics.
        references: External HTML/JavaScript reference evidence, or
            ``None`` when coverage is unknown.

    Returns:
        Low-confidence advisory findings, never automated rename proposals.

    """
    declared: dict[str, list[CssDeclaration]] = defaultdict(list)
    aliases: dict[str, frozenset[str]] = {}
    css_references: set[str] = set()
    for declaration in declarations:
        declared[declaration.name].append(declaration)
        targets: frozenset[str] = frozenset(
            Constants.reference.findall(string=declaration.value),
        )
        css_references.update(targets)
        aliases[declaration.name] = targets
    external: frozenset[str] = (
        references.names if references is not None else frozenset()
    )
    known: frozenset[str] = frozenset(css_references) | external
    complete: bool = references is not None and references.complete
    evidence: str = (
        "no references in known CSS/HTML/JS sources"
        if complete
        else "lacks known references; dynamic use not checked"
    )
    findings: list[CssNamingFinding] = [
        CssNamingFinding(
            rule="CSSN008",
            file=members[0].file,
            line=members[0].line,
            message=(f"{name} is possibly unused: {evidence}."),
            severity=_severity(
                rule="CSSN008",
                default="warning" if complete else "info",
                policy=policy,
            ),
            scope=members[0].scope,
            canonical=name,
            related=(
                references.locations_for(name=name)
                if references is not None
                else ()
            ),
            confidence="advisory",
            reason="unreferenced",
        )
        for name, members in sorted(declared.items())
        if name not in known
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
                            severity=_severity(
                                rule="CSSN009",
                                default="info",
                                policy=policy,
                            ),
                            scope=members[0].scope,
                            canonical=name,
                            confidence="advisory",
                            reason="alias-depth",
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
    reference_files: Sequence[Path] = (),
) -> tuple[CssNamingFinding, ...]:
    """Classify numeric CSS custom-property families without modifying code.

    Args:
        root: Project root used to select component identity.
        files: Stylesheets to inspect.
        settings: Optional explicit naming policy.
        reference_files: HTML/JavaScript sources scanned for statically
            knowable property references; only consumed when
            ``check_extended`` is enabled.

    Returns:
        Deterministically sorted warnings, errors and advisory diagnostics.

    Raises:
        OSError: If a stylesheet cannot be read.
        UnicodeError: If a stylesheet cannot be decoded as UTF-8.
        ValueError: If numeric family thresholds or configured
            severities are invalid.

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
    unknown_rules: set[str] = {
        rule for rule, _level in policy.rule_severity
    } - set(Constants.rules)
    unknown_levels: set[str] = {
        level for _rule, level in policy.rule_severity
    } - set(Constants.severities)
    if unknown_rules or unknown_levels:
        msg = (
            f"Invalid CSS naming severity overrides: "
            f"rules {sorted(unknown_rules)}, "
            f"levels {sorted(unknown_levels)}"
        )
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
            _extended_findings(
                declarations=declarations,
                policy=policy,
                references=collect_css_references(files=reference_files),
            ),
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
