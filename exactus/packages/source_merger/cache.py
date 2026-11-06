"""Bounded, session-owned parse and identity caches with.

Bounded, session-owned parse and identity caches with indexed statement lookup.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from re import Match, search
from typing import TYPE_CHECKING, Final, final

from exactus.packages.source_merger.delta import DeltaMetrics, measure
from exactus.packages.source_merger.foreign_parser import (
    HtmlParser,
    NodeParser,
)
from exactus.packages.source_merger.incremental import IncrementalPythonParser
from exactus.packages.source_merger.python_parser import PythonParser
from exactus.packages.source_merger.tracking import Tracking, track

if TYPE_CHECKING:
    from exactus.packages.source_merger.model import (
        Language,
        Snapshot,
        Statement,
        Unit,
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        snapshot_count: Grouped module constant.
        max_exact_chars: Grouped module constant.
        max_candidate_pool: Grouped module constant.
        min_confidence: Grouped module constant.
        min_margin: Grouped module constant.

    """

    snapshot_count: Final[int] = 3
    max_exact_chars: Final[int] = 8192
    max_candidate_pool: Final[int] = 64
    min_confidence: Final[float] = 0.72
    min_margin: Final[float] = 0.09


@final
@dataclass(frozen=True, slots=True)
class CacheStats:
    """Snapshot and identity cache counters.

    Attributes:
        parsed: Number of newly parsed snapshots.
        reused: Number of exact snapshot cache hits.
        matched: Number of freshly computed identity correspondences.
        reused_matches: Number of cached correspondences returned.
        batches: Number of Node parser processes launched for snapshot batches.
        incremental: Number of safe Python partial source reparses.
        measured: Number of newly calculated fork delta reports.
        reused_deltas: Number of delta reports obtained from cache.

    """

    parsed: int
    reused: int
    matched: int
    reused_matches: int
    batches: int
    incremental: int
    measured: int
    reused_deltas: int


@final
class SnapshotCache:
    """Reuse immutable parse trees and tracking results across editor updates.

    Hash keys include the language and the complete source.  A bounded FIFO/LRU
    eviction policy makes the cache per-session rather than process-global.
    Cache entries are never reused after content changes without verification.

    Attributes:
        max_snapshots: Maximum source snapshots retained in this session.
        max_matches: Maximum source-pair tracking results retained.

    """

    def __init__(
        self,
        *,
        max_snapshots: int = 24,
        max_matches: int = 48,
    ) -> None:
        """Initialize bounded cache storage.

        Args:
            max_snapshots: Positive number of snapshots retained.
            max_matches: Positive number of matching results retained.

        Raises:
            ValueError: Requested cache capacities are not positive.

        """
        if max_snapshots < 1 or max_matches < 1:
            msg: str = "Cache capacities must be positive"
            raise ValueError(msg)
        self.max_snapshots: int = max_snapshots
        self.max_matches: int = max_matches
        self._snapshots: OrderedDict[tuple[Language, bytes], Snapshot] = (
            OrderedDict()
        )
        self._matches: OrderedDict[
            tuple[bytes, bytes, str, float, float],
            Tracking,
        ] = OrderedDict()
        self._parsed: int = 0
        self._reused: int = 0
        self._matched: int = 0
        self._reused_matches: int = 0
        self._batches: int = 0
        self._incremental: int = 0
        self._forks: dict[str, Snapshot] = {}
        self._deltas: OrderedDict[
            tuple[Language, bytes, bytes],
            DeltaMetrics,
        ] = OrderedDict()
        self._measured: int = 0
        self._reused_deltas: int = 0

    @property
    def stats(self) -> CacheStats:
        """Return immutable cache statistics for reproducible checks.

        Returns:
            Cache hit/miss counters for snapshot, match, and delta reuse.

        """
        return CacheStats(
            parsed=self._parsed,
            reused=self._reused,
            matched=self._matched,
            reused_matches=self._reused_matches,
            batches=self._batches,
            incremental=self._incremental,
            measured=self._measured,
            reused_deltas=self._reused_deltas,
        )

    def parse_many(
        self,
        *,
        sources: tuple[str, ...],
        language: Language,
    ) -> tuple[Snapshot, ...]:
        """Parse only cache misses; batch foreign misses in one process.

        Args:
            sources: Complete source snapshots.
            language: Source language shared by the snapshots.

        Returns:
            Parsed snapshots in request order; duplicates are parsed once.

        """
        entries: dict[tuple[Language, bytes], Snapshot] = {}
        missing: dict[tuple[Language, bytes], str] = {}
        keys: tuple[tuple[Language, bytes], ...] = tuple(
            self._key(source=source, language=language) for source in sources
        )
        for key, source in zip(keys, sources, strict=True):
            cached: Snapshot | None = self._snapshots.get(key)
            if cached is not None and cached.source == source:
                self._snapshots.move_to_end(key=key)
                self._reused += 1
                entries[key] = cached
            elif key not in missing:
                missing[key] = source
        if missing:
            new_keys: tuple[tuple[Language, bytes], ...] = tuple(missing)
            if language in {"javascript", "typescript", "css"}:
                parsed: tuple[Snapshot, ...] = NodeParser().parse_many(
                    sources=tuple(missing.values()),
                    language=language,
                )
                self._batches += 1
            else:
                parser: PythonParser | HtmlParser = (
                    PythonParser() if language == "python" else HtmlParser()
                )
                parsed = tuple(
                    parser.parse(source=source) for source in missing.values()
                )
            for key, snapshot in zip(new_keys, parsed, strict=True):
                self._remember(key=key, snapshot=snapshot)
                entries[key] = snapshot
        return tuple(entries[key] for key in keys)

    def parse(self, *, source: str, language: Language) -> Snapshot:
        """Return one cached snapshot, parsing it if its hash is not cached.

        Args:
            source: Complete source text.
            language: Source grammar.

        Returns:
            Cached or freshly parsed snapshot.

        """
        return self.parse_many(sources=(source,), language=language)[0]

    def parse_edit(
        self,
        *,
        source: str,
        language: Language,
        previous: Snapshot | None,
    ) -> Snapshot:
        """Reuse one unchanged source, or partially reparse a Python edit.

        Args:
            source: New complete source.
            language: Grammar for the source.
            previous: Previous snapshot from the same fork, if available.

        Returns:
            Safe partial snapshot when eligible; otherwise fully parsed.

        """
        key: tuple[Language, bytes] = self._key(
            source=source,
            language=language,
        )
        existing: Snapshot | None = self._snapshots.get(key)
        if existing is not None and existing.source == source:
            self._reused += 1
            self._snapshots.move_to_end(key=key)
            return existing
        candidate: Snapshot | None = (
            IncrementalPythonParser.reparse(previous=previous, source=source)
            if language == "python" and previous is not None
            else None
        )
        if candidate is None:
            return self.parse(source=source, language=language)
        self._remember(key=key, snapshot=candidate)
        self._incremental += 1
        return candidate

    def parse_forks(
        self,
        *,
        original: str,
        user: str,
        tool: str,
        language: Language,
    ) -> tuple[Snapshot, Snapshot, Snapshot]:
        """Reuse a stable ancestor and incrementally update its forks.

        Args:
            original: Common ancestor.
            user: Current editor snapshot.
            tool: Current refactoring snapshot.
            language: Shared grammar.

        Returns:
            Validated or explicitly invalid snapshots in ancestor/fork order.

        Raises:
            ValueError: If ``parse_many`` returns an unexpected count.

        """
        if language != "python":
            snapshots: tuple[Snapshot, ...] = self.parse_many(
                sources=(original, user, tool),
                language=language,
            )
            if len(snapshots) != Constants.snapshot_count:
                msg: str = "parse_many returned an unexpected snapshot count"
                raise ValueError(msg)
            return (snapshots[0], snapshots[1], snapshots[2])
        ancestor: Snapshot = self.parse(source=original, language=language)
        previous_user: Snapshot | None = self._forks.get("user")
        previous_tool: Snapshot | None = self._forks.get("tool")
        if self._forks.get("ancestor") is not ancestor:
            previous_user = None
            previous_tool = None
            self._forks.clear()
        user_snapshot: Snapshot = self.parse_edit(
            source=user,
            language=language,
            previous=previous_user,
        )
        tool_snapshot: Snapshot = self.parse_edit(
            source=tool,
            language=language,
            previous=previous_tool,
        )
        self._forks.update(
            {
                "ancestor": ancestor,
                "user": user_snapshot,
                "tool": tool_snapshot,
            },
        )
        return (ancestor, user_snapshot, tool_snapshot)

    def delta(
        self,
        *,
        original: str,
        changed: str,
        language: Language,
    ) -> DeltaMetrics:
        """Reuse exact ancestor-to-branch mutation metrics.

        Args:
            original: Common-ancestor source.
            changed: One fork's current source.
            language: Source grammar.

        Returns:
            Deterministic fork mutation budget data.

        """
        key: tuple[Language, bytes, bytes] = (
            language,
            self._key(source=original, language=language)[1],
            self._key(source=changed, language=language)[1],
        )
        cached: DeltaMetrics | None = self._deltas.get(key)
        if cached is not None:
            self._deltas.move_to_end(key=key)
            self._reused_deltas += 1
            return cached
        computed: DeltaMetrics = measure(
            original=original,
            changed=changed,
            language=language,
        )
        self._deltas[key] = computed
        if len(self._deltas) > self.max_matches:
            self._deltas.popitem(last=False)
        self._measured += 1
        return computed

    def match(
        self,
        *,
        original: Snapshot,
        changed: Snapshot,
        branch: str,
        minimum_confidence: float = 0.72,
        minimum_margin: float = 0.09,
    ) -> Tracking:
        """Reuse unchanged identity tracking across successive editor forks.

        Args:
            original: Common-ancestor snapshot.
            changed: User or tool fork snapshot.
            branch: Fork label for audit records.
            minimum_confidence: Lowest accepted identity confidence.
            minimum_margin: Required gap from competing candidates.

        Returns:
            Cached or freshly computed declaration correspondences.

        """
        old: bytes = sha256(
            data=original.source.encode(encoding="utf-8"),
        ).digest()
        new: bytes = sha256(
            data=changed.source.encode(encoding="utf-8"),
        ).digest()
        key: tuple[bytes, bytes, str, float, float] = (
            old,
            new,
            branch,
            minimum_confidence,
            minimum_margin,
        )
        cached: Tracking | None = self._matches.get(key)
        if cached is not None:
            self._matches.move_to_end(key=key)
            self._reused_matches += 1
            return cached
        result: Tracking = track(
            original=original,
            changed=changed,
            branch=branch,
            minimum_confidence=minimum_confidence,
            minimum_margin=minimum_margin,
        )
        self._matches[key] = result
        if len(self._matches) > self.max_matches:
            self._matches.popitem(last=False)
        self._matched += 1
        return result

    @staticmethod
    def _key(*, source: str, language: Language) -> tuple[Language, bytes]:
        """Hash a snapshot without depending on formatting or path.

        Args:
            source: Complete source text.
            language: Source grammar.

        Returns:
            ``(language, digest)`` cache key.

        """
        return (
            language,
            sha256(data=source.encode(encoding="utf-8")).digest(),
        )

    def _remember(
        self,
        *,
        key: tuple[Language, bytes],
        snapshot: Snapshot,
    ) -> None:
        """Retain an immutable snapshot and evict the least recent.

        Args:
            key: ``(language, digest)`` cache key.
            snapshot: Parsed snapshot to retain.

        """
        self._snapshots[key] = snapshot
        self._snapshots.move_to_end(key=key)
        if len(self._snapshots) > self.max_snapshots:
            self._snapshots.popitem(last=False)
        self._parsed += 1


@final
class StatementIndex:
    """Constant-time candidate retrieval by normalized statement identity.

    Parent-scope candidates are preferred over global candidates. If repeated
    statements remain indistinguishable, correspondence is rejected.

    Attributes:
        snapshot: Tool-fork snapshot backing all indexes.

    """

    def __init__(self, *, snapshot: Snapshot) -> None:
        """Build an immutable snapshot's indexes in one linear pass.

        Args:
            snapshot: Parsed source whose statements are indexed.

        """
        self.snapshot: Snapshot = snapshot
        shapes: dict[str, list[Statement]] = defaultdict(list)
        for statement in snapshot.statements:
            shapes[statement.shape].append(statement)
        self._shapes: dict[str, tuple[Statement, ...]] = {
            key: tuple(values) for key, values in shapes.items()
        }
        kinds: dict[str, list[Statement]] = defaultdict(list)
        calls: dict[tuple[str, str], list[Statement]] = defaultdict(list)
        for item in snapshot.statements:
            kinds[item.kind].append(item)
            identified: Match[str] | None = search(
                pattern="Call\\(id:([A-Za-z_]\\w*)",
                string=item.exact,
            )
            if identified is not None:
                calls[item.kind, identified.group(1)].append(item)
        self._kinds: dict[str, tuple[Statement, ...]] = {
            name: tuple(values) for name, values in kinds.items()
        }
        self._calls: dict[tuple[str, str], tuple[Statement, ...]] = {
            name: tuple(values) for name, values in calls.items()
        }
        self._scopes: dict[
            tuple[int, int],
            dict[str, tuple[Statement, ...]],
        ] = {}
        for unit in snapshot.units:
            groups: dict[str, list[Statement]] = defaultdict(list)
            for statement in unit.statements:
                groups[statement.shape].append(statement)
            self._scopes[unit.start, unit.end] = {
                key: tuple(values) for key, values in groups.items()
            }

    def locate(
        self,
        *,
        original: Statement,
        preferred: Unit | None,
    ) -> Statement | None:
        """Find an equivalent statement in a scope, then the whole tree.

        Args:
            original: Ancestor statement to relocate.
            preferred: Lexical parent to try first.

        Returns:
            The unique matching statement, or None.

        """
        if preferred is not None:
            scoped: tuple[Statement, ...] = self._scopes.get(
                (preferred.start, preferred.end),
                {},
            ).get(original.shape, ())
            selected: Statement | None = self._unique(
                candidates=scoped,
                original=original,
            )
            if selected is not None:
                return selected
        return self._unique(
            candidates=self._shapes.get(original.shape, ()),
            original=original,
        )

    def locate_mutated(
        self,
        *,
        original: Statement,
        preferred: Unit | None,
    ) -> Statement | None:
        """Find one uniquely similar statement, including moved calls.

        Call-bearing statements first use a named-callee index; all other
        statements use bounded same-kind candidates. The ranking refuses near
        ties, even when a lexical parent supplies an apparent candidate.

        Args:
            original: Ancestor statement to relocate.
            preferred: Lexical parent to try first.

        Returns:
            The unique matching statement, or None.

        """
        call: Match[str] | None = search(
            pattern="Call\\(id:([A-Za-z_]\\w*)",
            string=original.exact,
        )
        if len(original.exact) > Constants.max_exact_chars:
            return None
        pool: tuple[Statement, ...] = (
            self._calls.get((original.kind, call.group(1)), ())
            if call is not None
            else ()
        )
        if not pool:
            pool = self._kinds.get(original.kind, ())
        if len(pool) > Constants.max_candidate_pool:
            if preferred is None:
                return None
            pool = tuple(
                item
                for item in preferred.statements
                if item.kind == original.kind
                and item.binding == original.binding
            )
        candidates: tuple[Statement, ...] = tuple(
            item for item in pool if item.binding == original.binding
        )
        ranked: list[tuple[float, Statement]] = sorted(
            (
                (
                    SequenceMatcher(
                        isjunk=None,
                        a=original.exact,
                        b=item.exact,
                        autojunk=False,
                    ).ratio(),
                    item,
                )
                for item in candidates
            ),
            key=lambda entry: (-entry[0], entry[1].start),
        )
        if not ranked or ranked[0][0] < Constants.min_confidence:
            return None
        if (
            len(ranked) > 1
            and ranked[0][0] - ranked[1][0] < Constants.min_margin
        ):
            return None
        return ranked[0][1]

    @staticmethod
    def _unique(
        *,
        candidates: tuple[Statement, ...],
        original: Statement,
    ) -> Statement | None:
        """Reject uncertain duplicate candidates without positional ties.

        Args:
            candidates: Candidate statements with matching identity.
            original: Ancestor statement to relocate.

        Returns:
            The unique candidate, or None when ambiguity remains.

        """
        if len(candidates) == 1:
            return candidates[0]
        if original.binding:
            bound: tuple[Statement, ...] = tuple(
                item for item in candidates if item.binding == original.binding
            )
            if len(bound) == 1:
                return bound[0]
        exact: tuple[Statement, ...] = tuple(
            item for item in candidates if item.exact == original.exact
        )
        return exact[0] if len(exact) == 1 else None
