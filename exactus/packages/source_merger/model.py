"""Immutable records used by the deterministic three-way source merger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, final

type Language = Literal["python", "javascript", "typescript", "html", "css"]
type ConflictKind = Literal[
    "ambiguous_identity",
    "concurrent_change",
    "missing_anchor",
    "parse_error",
    "structural_change",
    "unsupported_transformation",
    "textual_conflict",
    "validation_error",
    "source_changed",
    "delta_exceeded",
]


@final
@dataclass(frozen=True, slots=True)
class MergeConflict:
    """Describe a change that cannot be merged without informed review.

    Attributes:
        kind: Machine-readable conflict category.
        scope: Human-readable declaration or source location.
        detail: Precise reason for rejecting the merge.

    """

    kind: ConflictKind
    scope: str
    detail: str


@final
@dataclass(frozen=True, slots=True)
class SymbolMatch:
    """Represent tracked correspondence between two forked declarations.

    Attributes:
        original: Identifier in the common ancestor.
        changed: Corresponding identifier in the changed fork.
        branch: Fork where the correspondence was established.
        confidence: Score from zero to one; never a semantic proof.
        kind: Syntax kind of the matched source declaration.

    """

    original: str
    changed: str
    branch: Literal["user", "tool"]
    confidence: float
    kind: str


@final
@dataclass(frozen=True, slots=True)
class AppliedChange:
    """Record provenance of a successfully projected user modification.

    Attributes:
        scope: Matched declaration or statement.
        operation: Kind of source transformation.
        detail: Human-readable explanation.

    """

    scope: str
    operation: str
    detail: str


@final
@dataclass(frozen=True, slots=True)
class MergeResult:
    """Safe merge outcome with independent syntax and conflict status.

    Attributes:
        source: Reconciled source or None when review is required.
        conflicts: All recognized incompatible changes.
        matches: Detected declaration correspondences.
        applied_changes: Successfully projected user mutations.
        success: True only when no unresolved conflicts remain.
        syntax_valid: True when a language parser verified final source.

    """

    source: str | None
    conflicts: tuple[MergeConflict, ...]
    matches: tuple[SymbolMatch, ...]
    applied_changes: tuple[AppliedChange, ...]
    success: bool
    syntax_valid: bool | None


@final
@dataclass(frozen=True, slots=True)
class Statement:
    """Syntax-aware unit with offsets into the unchanged snapshot.

    Attributes:
        kind: Statement classification.
        start: Inclusive source offset.
        end: Exclusive source offset.
        shape: Name-insensitive syntactic fingerprint.
        exact: Name-aware semantic fingerprint.
        binding: Variable or selector introduced by this statement.
        value_start: Optional start offset for a RHS expression.
        value_end: Optional end offset for a RHS expression.
        annotation: Declaration annotation fingerprint, when present.

    """

    kind: str
    start: int
    end: int
    shape: str
    exact: str
    binding: str = ""
    value_start: int | None = None
    value_end: int | None = None
    annotation: str = ""


@final
@dataclass(frozen=True, slots=True)
class Unit:
    """Function, class, rule, or HTML element with independent identity.

    Attributes:
        kind: Structural category.
        name: Declared name or element identity.
        parent: Qualifying lexical container.
        start: Inclusive complete source offset.
        end: Exclusive complete source offset.
        body_start: Start of replaceable body span.
        body_end: End of replaceable body span.
        statements: Immediate body statements.
        fingerprint: Name-agnostic body fingerprint.
        signature: Name-agnostic declaration fingerprint.
        param_names: Positional parameter bindings.
        implicit_return: Whether the body is an arrow expression.
        header_semantic: Syntax-level signature and decorator identity.

    """

    kind: str
    name: str
    parent: str
    start: int
    end: int
    body_start: int
    body_end: int
    statements: tuple[Statement, ...]
    fingerprint: str
    signature: str
    param_names: tuple[str, ...] = ()
    implicit_return: bool = False
    header_semantic: str = ""

    @property
    def key(self) -> str:
        """Return the name qualified by its lexical owner.

        Returns:
            ``parent.name`` when nested, else the bare name.

        """
        return f"{self.parent}.{self.name}" if self.parent else self.name


@final
@dataclass(frozen=True, slots=True)
class Snapshot:
    """Parsed representation of a language-specific source snapshot.

    Attributes:
        source: Original bytes decoded as source text.
        units: Recognized declarations and movable blocks.
        statements: Every recognized statement for relocation matching.
        valid: Whether the parser accepted the source.
        error: Parser failure explanation when invalid.

    """

    source: str
    units: tuple[Unit, ...]
    statements: tuple[Statement, ...]
    valid: bool
    error: str = ""


@final
@dataclass(frozen=True, slots=True)
class Replacement:
    """Non-overlapping source offset replacement.

    Attributes:
        start: Inclusive source offset.
        end: Exclusive source offset.
        text: Replacement content.
        scope: Source scope for diagnostics.

    """

    start: int
    end: int
    text: str
    scope: str
