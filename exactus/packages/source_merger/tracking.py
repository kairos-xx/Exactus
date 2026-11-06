"""Indexed hierarchical identity matching for independently.

Indexed hierarchical identity matching for independently refactored source
trees.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import final

from exactus.packages.source_merger.model import Snapshot, SymbolMatch, Unit


@final
@dataclass(frozen=True, slots=True)
class Tracking:
    """One-to-one correspondences, ambiguous ancestors, and audit matches.

    Attributes:
        pairs: Ancestor and fork declaration indices.
        ambiguous: Ancestors whose identity cannot be established safely.
        matches: Auditable correspondences and confidence estimates.

    """

    pairs: tuple[tuple[int, int], ...]
    ambiguous: tuple[int, ...]
    matches: tuple[SymbolMatch, ...]


@final
class Constants:
    """Bound candidate expansion and matching work for large files.

    Attributes:
        minimum_score: Lowest accepted identity confidence.
        minimum_margin: Required advantage over competing identities.
        max_candidates: Maximum candidates scored per unmatched declaration.
        max_scope_candidates: Scope-local fallback candidates considered.
        max_fuzzy_chars: Character budget for approximate body matching.

    """

    minimum_score: float = 0.72
    minimum_margin: float = 0.09
    max_candidates: int = 32
    max_scope_candidates: int = 24
    max_fuzzy_chars: int = 8192


def _compatible(*, base: Unit, candidate: Unit) -> bool:
    """Accept equivalent declaration categories, including arrow conversions.

    Args:
        base: Ancestor declaration.
        candidate: Fork declaration.

    Returns:
        Whether their declaration categories can correspond.

    """
    return base.kind == candidate.kind or {base.kind, candidate.kind} == {
        "function",
        "arrow",
    }


def _score(*, base: Unit, candidate: Unit) -> float:
    """Score a candidate only after indexed retrieval.

    Args:
        base: Ancestor declaration.
        candidate: Fork declaration.

    Returns:
        Identity confidence surrogate between zero and one.

    """
    if not _compatible(base=base, candidate=candidate):
        return 0.0
    if base.key == candidate.key:
        return 1.0
    if base.fingerprint and base.fingerprint == candidate.fingerprint:
        return (0.975 if base.signature == candidate.signature else 0.945) + (
            0.019 if base.name == candidate.name else 0.0
        )
    if (
        len(base.fingerprint) + len(candidate.fingerprint)
        > Constants.max_fuzzy_chars
    ):
        return 0.0
    base_shapes: tuple[str, ...] = tuple(
        item.shape for item in base.statements
    )
    candidate_shapes: tuple[str, ...] = tuple(
        item.shape for item in candidate.statements
    )
    similarity: float = max(
        SequenceMatcher(
            isjunk=None,
            a=base_shapes,
            b=candidate_shapes,
            autojunk=False,
        ).ratio(),
        SequenceMatcher(
            isjunk=None,
            a="|".join(base_shapes),
            b="|".join(candidate_shapes),
            autojunk=False,
        ).ratio(),
    )
    spelling: float = SequenceMatcher(
        isjunk=None,
        a=base.name,
        b=candidate.name,
        autojunk=False,
    ).ratio()
    return min(
        1.0,
        0.61 * similarity
        + 0.13 * spelling
        + (0.13 if base.parent == candidate.parent else 0.0)
        + (0.13 if base.signature == candidate.signature else 0.0)
        + (0.05 if base.name == candidate.name else 0.0),
    )


@final
@dataclass(slots=True)
class _Indexes:
    """Hierarchical lookup indexes over a changed snapshot.

    Attributes:
        by_key: Qualified identity index.
        by_fingerprint: Body-shape index.
        by_name: Kind and name index.
        by_parent: Kind and lexical parent index.
        by_signature: Signature index.

    """

    by_key: dict[str, list[int]]
    by_fingerprint: dict[tuple[str, str], list[int]]
    by_name: dict[tuple[str, str], list[int]]
    by_parent: dict[tuple[str, str], list[int]]
    by_signature: dict[tuple[str, str], list[int]]


def _build_indexes(*, changed: Snapshot) -> _Indexes:
    """Index changed units by every conservative identity facet.

    Args:
        changed: User or tool fork snapshot.

    Returns:
        Populated index bundle; arrows alias their function kind.

    """
    indexes: _Indexes = _Indexes(
        by_key=defaultdict(list),
        by_fingerprint=defaultdict(list),
        by_name=defaultdict(list),
        by_parent=defaultdict(list),
        by_signature=defaultdict(list),
    )
    for index, unit in enumerate(iterable=changed.units):
        indexes.by_key[unit.key].append(index)
        kinds: tuple[str, ...] = (
            (unit.kind, "function") if unit.kind == "arrow" else (unit.kind,)
        )
        for kind in kinds:
            indexes.by_fingerprint[(kind, unit.fingerprint)].append(index)
            indexes.by_name[(kind, unit.name)].append(index)
            indexes.by_parent[(kind, unit.parent)].append(index)
            indexes.by_signature[(kind, unit.signature)].append(index)
    return indexes


@final
@dataclass(slots=True)
class _State:
    """Mutable assignment state shared by the matching passes.

    Attributes:
        assigned_base: Matched ancestor unit indexes.
        assigned_fork: Matched changed unit indexes.
        ambiguous: Ancestor indexes that matched ambiguously.
        pairs: Committed correspondences.
        confidence: Per-pair identity confidence.

    """

    assigned_base: set[int] = field(default_factory=set)
    assigned_fork: set[int] = field(default_factory=set)
    ambiguous: set[int] = field(default_factory=set)
    pairs: list[tuple[int, int]] = field(default_factory=list)
    confidence: dict[tuple[int, int], float] = field(default_factory=dict)

    def assign(
        self,
        *,
        base_index: int,
        fork_index: int,
        score: float,
    ) -> None:
        """Commit a uniquely identified declaration correspondence.

        Args:
            base_index: Ancestor unit index.
            fork_index: Changed unit index.
            score: Identity confidence.

        """
        self.assigned_base.add(base_index)
        self.assigned_fork.add(fork_index)
        self.pairs.append((base_index, fork_index))
        self.confidence[(base_index, fork_index)] = score


def _exact_pass(
    *,
    original: Snapshot,
    changed: Snapshot,
    indexes: _Indexes,
    state: _State,
) -> None:
    """Assign unique qualified-key correspondences.

    Args:
        original: Common-ancestor snapshot.
        changed: User or tool fork snapshot.
        indexes: Changed-side indexes.
        state: Shared assignment state.

    """
    for index, base in enumerate(iterable=original.units):
        matches: list[int] = [
            target
            for target in indexes.by_key[base.key]
            if target not in state.assigned_fork
            and _compatible(base=base, candidate=changed.units[target])
        ]
        if len(matches) == 1:
            state.assign(base_index=index, fork_index=matches[0], score=1.0)
        elif len(matches) > 1:
            state.ambiguous.add(index)


def _fingerprint_pass(
    *,
    original: Snapshot,
    changed: Snapshot,
    indexes: _Indexes,
    state: _State,
    minimum_confidence: float,
) -> None:
    """Assign unique body-fingerprint correspondences.

    Args:
        original: Common-ancestor snapshot.
        changed: User or tool fork snapshot.
        indexes: Changed-side indexes.
        state: Shared assignment state.
        minimum_confidence: Lowest accepted identity confidence.

    """
    for index, base in enumerate(iterable=original.units):
        if (
            index in state.assigned_base
            or index in state.ambiguous
            or not base.fingerprint
        ):
            continue
        matches: list[int] = [
            target
            for target in indexes.by_fingerprint[(base.kind, base.fingerprint)]
            if target not in state.assigned_fork
            and _compatible(base=base, candidate=changed.units[target])
        ]
        if len(matches) == 1:
            target: int = matches[0]
            score: float = _score(base=base, candidate=changed.units[target])
            if score >= minimum_confidence:
                state.assign(base_index=index, fork_index=target, score=score)
        elif len(matches) > 1:
            state.ambiguous.add(index)


def _fuzzy_candidates(
    *,
    base: Unit,
    indexes: _Indexes,
    parent_aliases: dict[str, str],
) -> set[int] | None:
    """Gather bounded rename/move candidates for one ancestor unit.

    Args:
        base: Ancestor unit.
        indexes: Changed-side indexes.
        parent_aliases: Committed parent-key correspondences.

    Returns:
        Bounded candidate set, or None when it exceeds the guard limit.

    """
    candidates: set[int] = set(indexes.by_name[(base.kind, base.name)])
    signed: list[int] = indexes.by_signature[(base.kind, base.signature)]
    if len(signed) <= Constants.max_scope_candidates:
        candidates.update(signed)
    scoped_parent: str = parent_aliases.get(base.parent, base.parent)
    local: list[int] = indexes.by_parent[(base.kind, scoped_parent)]
    if len(local) <= Constants.max_scope_candidates:
        candidates.update(local)
    if len(candidates) > Constants.max_candidates:
        return None
    return candidates


def _fuzzy_pass(
    *,
    original: Snapshot,
    changed: Snapshot,
    indexes: _Indexes,
    state: _State,
    limits: tuple[float, float],
) -> None:
    """Score and commit remaining units through ranked fuzzy matching.

    Args:
        original: Common-ancestor snapshot.
        changed: User or tool fork snapshot.
        indexes: Changed-side indexes.
        state: Shared assignment state.
        limits: ``(minimum_confidence, minimum_margin)`` bounds.

    """
    minimum_confidence, minimum_margin = limits
    parent_aliases: dict[str, str] = {
        original.units[base_index].key: changed.units[fork_index].key
        for base_index, fork_index in state.pairs
    }
    # Restrict fuzzy scoring to indexed names, signatures, and lexical scopes.
    # A moved declaration remains discoverable through its name or signature.
    pending: dict[int, list[tuple[float, int]]] = {}
    reverse: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for index, base in enumerate(iterable=original.units):
        if index in state.assigned_base or index in state.ambiguous:
            continue
        candidates: set[int] | None = _fuzzy_candidates(
            base=base,
            indexes=indexes,
            parent_aliases=parent_aliases,
        )
        if candidates is None:
            # Never truncate a candidate set: doing so could hide a better
            # match.
            state.ambiguous.add(index)
            continue
        ranked: list[tuple[float, int]] = sorted(
            (
                (_score(base=base, candidate=changed.units[target]), target)
                for target in candidates
                if target not in state.assigned_fork
                and _compatible(base=base, candidate=changed.units[target])
            ),
            key=lambda entry: (-entry[0], entry[1]),
        )
        if not ranked or ranked[0][0] < minimum_confidence:
            continue
        pending[index] = ranked
        for score, target in ranked:
            reverse[target].append((score, index))
    for index, ranked in sorted(
        pending.items(),
        key=lambda item: (-item[1][0][0], item[0]),
    ):
        if index in state.ambiguous:
            continue
        score, target = ranked[0]
        second: float = ranked[1][0] if len(ranked) > 1 else 0.0
        rivals: float = max(
            (value for value, rival in reverse[target] if rival != index),
            default=0.0,
        )
        if max(second, rivals) >= score - minimum_margin:
            state.ambiguous.add(index)
        elif target not in state.assigned_fork:
            state.assign(base_index=index, fork_index=target, score=score)
        else:
            state.ambiguous.add(index)


def track(
    *,
    original: Snapshot,
    changed: Snapshot,
    branch: str,
    minimum_confidence: float = Constants.minimum_score,
    minimum_margin: float = Constants.minimum_margin,
) -> Tracking:
    """Match declarations using hierarchical indexes and bounded fuzzy search.

    Exact qualified identities are resolved first, then unique body
    fingerprints, then indexed rename/move candidates. Parent
    correspondences guide the final fuzzy pass. Ambiguous or oversized
    candidate groups are never guessed.

    Args:
        original: Common-ancestor snapshot.
        changed: User or tool fork.
        branch: Fork label for audit records.
        minimum_confidence: Lowest accepted nonexact identity confidence.
        minimum_margin: Required gap from competing candidates.

    Returns:
        Unique, conservative declaration correspondences.

    """
    indexes: _Indexes = _build_indexes(changed=changed)
    state: _State = _State()
    _exact_pass(
        original=original,
        changed=changed,
        indexes=indexes,
        state=state,
    )
    _fingerprint_pass(
        original=original,
        changed=changed,
        indexes=indexes,
        state=state,
        minimum_confidence=minimum_confidence,
    )
    _fuzzy_pass(
        original=original,
        changed=changed,
        indexes=indexes,
        state=state,
        limits=(minimum_confidence, minimum_margin),
    )
    return Tracking(
        pairs=tuple(sorted(state.pairs)),
        ambiguous=tuple(sorted(state.ambiguous)),
        matches=tuple(
            SymbolMatch(
                original=original.units[index].key,
                changed=changed.units[target].key,
                branch="user" if branch == "user" else "tool",
                confidence=state.confidence[(index, target)],
                kind=original.units[index].kind,
            )
            for index, target in sorted(state.pairs)
        ),
    )
