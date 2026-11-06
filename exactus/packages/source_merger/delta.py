"""Conservative mutation-budget checks for independently.

Conservative mutation-budget checks for independently edited source forks.
"""

from __future__ import annotations

from ast import dump, parse
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from io import StringIO
from re import findall
from tokenize import (
    DEDENT,
    ENCODING,
    ENDMARKER,
    INDENT,
    NEWLINE,
    NL,
    TokenError,
    generate_tokens,
)
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Iterator

    from exactus.packages.source_merger.model import Language


@final
class Constants:
    """Group module-level constants.

    Attributes:
        max_inline_span: Grouped module constant.
        max_token_budget: Grouped module constant.

    """

    max_inline_span: Final[int] = 256
    max_token_budget: Final[int] = 4096


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class DeltaPolicy:
    """Limits for automatic reconciliation; exceeding a limit requires review.

    Attributes:
        max_user_changed_fraction: Largest permitted fraction of ancestor
            tokens changed.
        max_tool_changed_fraction: Largest permitted fraction of ancestor
            tokens changed.
        max_combined_changed_fraction: Largest combined changed fraction.
        max_user_inserted_tokens: Maximum number of user-added tokens per
            fork.
        max_user_replaced_tokens: Maximum number of user-replaced tokens
            per fork.
        max_user_deleted_tokens: Maximum number of user-deleted tokens per
            fork.
        max_user_edit_events: Maximum number of independent user edit
            regions.
        max_user_tokens_per_second: Burst-size limit when elapsed time is
            known.
        short_fork_seconds: Interval at which burst diagnostics are
            enabled.
        min_identity_confidence: Minimum identity score for an automatic
            merge.
        min_identity_margin: Minimum separation between best and runner-up
            match.

    """

    max_user_changed_fraction: float = 1.0
    max_tool_changed_fraction: float = 1.0
    max_combined_changed_fraction: float = 2.0
    max_user_inserted_tokens: int = 20000
    max_user_replaced_tokens: int = 20000
    max_user_deleted_tokens: int = 20000
    max_user_edit_events: int = 500
    max_user_tokens_per_second: float = 10000.0
    short_fork_seconds: float = 5.0
    min_identity_confidence: float = 0.72
    min_identity_margin: float = 0.09


@final
@dataclass(frozen=True, slots=True)
class DeltaMetrics:
    """Lexical delta measurements, independent of formatting and line numbers.

    Attributes:
        ancestor_tokens: Number of ancestor tokens.
        changed_fraction: Fraction of ancestor tokens affected, capped at one.
        inserted_tokens: Tokens inserted into the fork.
        replaced_tokens: Original tokens replaced by the fork.
        deleted_tokens: Tokens deleted from the ancestor.
        edit_events: Number of non-equal token diff regions.

    """

    ancestor_tokens: int
    changed_fraction: float
    inserted_tokens: int
    replaced_tokens: int
    deleted_tokens: int
    edit_events: int


def _tokens(*, source: str, language: Language) -> tuple[str, ...]:
    """Extract meaningful tokens without treating line wrapping as mutation.

    Args:
        source: Complete source text.
        language: Source grammar.

    Returns:
        Ordered tokens with structural meaning.

    """
    if language == "python":
        try:
            return tuple(
                (f"{token.type}:{token.string}")
                for token in generate_tokens(
                    readline=StringIO(initial_value=source).readline,
                )
                if token.type
                not in {NL, NEWLINE, INDENT, DEDENT, ENDMARKER, ENCODING}
            )
        except (IndentationError, SyntaxError, TokenError):
            return tuple(source.split())
    return tuple(
        findall(
            pattern=(
                "(?:[A-Za-z_$][\\w$-]*|\\d+(?:\\.\\d+)?|===|!==|=>|==|!=|<=|>="
                "|\\S)"
            ),
            string=source,
        ),
    )


def _unique_anchors(
    *,
    before: list[str],
    after: list[str],
) -> list[tuple[int, int]]:
    """Compute longest-increasing-subsequence line anchors.

    Args:
        before: Original lines.
        after: Edited lines.

    Returns:
        Aligned unique-line anchor pairs in original order.

    """
    former: Counter[str] = Counter(before)
    latter: Counter[str] = Counter(after)
    positions: dict[str, int] = {
        line: index
        for index, line in enumerate(iterable=after)
        if latter[line] == 1 and former[line] == 1
    }
    candidates: list[tuple[int, int]] = [
        (index, positions[line])
        for index, line in enumerate(iterable=before)
        if line in positions
    ]
    ends: list[int] = []
    tail_indices: list[int] = []
    parents: list[int] = [-1] * len(candidates)
    for index, (_, location) in enumerate(iterable=candidates):
        position: int = bisect_left(a=ends, x=location)
        if position:
            parents[index] = tail_indices[position - 1]
        if position == len(ends):
            ends.append(location)
            tail_indices.append(index)
        else:
            ends[position] = location
            tail_indices[position] = index
    anchors: list[tuple[int, int]] = []
    if tail_indices:
        cursor: int = tail_indices[-1]
        while cursor >= 0:
            anchors.append(candidates[cursor])
            cursor = parents[cursor]
        anchors.reverse()
    return anchors


def _changed_lines(
    *,
    before: list[str],
    after: list[str],
) -> Iterator[tuple[str, int, int, int, int]]:
    """Yield bounded edit chunks using O(n log n) unique-line anchors.

    Args:
        before: Common-ancestor lines.
        after: Changed lines.

    Yields:
        Bounded changed-line chunks.

    Unique common lines provide deterministic anchors under reordering. Long
    unmatched spans are emitted intact to avoid quadratic fuzzy matching.
    Repeated content is reduced through exact common-prefix/suffix trimming.

    """
    anchors: list[tuple[int, int]] = _unique_anchors(
        before=before,
        after=after,
    )
    left: int = 0
    right: int = 0
    for anchor_old, anchor_new in (*anchors, (len(before), len(after))):
        old_end: int = anchor_old
        new_end: int = anchor_new
        old_begin: int = left
        new_begin: int = right
        while (
            old_begin < old_end
            and new_begin < new_end
            and (before[old_begin] == after[new_begin])
        ):
            old_begin += 1
            new_begin += 1
        while (
            old_begin < old_end
            and new_begin < new_end
            and (before[old_end - 1] == after[new_end - 1])
        ):
            old_end -= 1
            new_end -= 1
        if old_begin < old_end or new_begin < new_end:
            if (
                old_end - old_begin + new_end - new_begin
                <= Constants.max_inline_span
            ):
                for action, i1, i2, j1, j2 in SequenceMatcher(
                    isjunk=None,
                    a=before[old_begin:old_end],
                    b=after[new_begin:new_end],
                    autojunk=True,
                ).get_opcodes():
                    if action != "equal":
                        yield (
                            action,
                            old_begin + i1,
                            old_begin + i2,
                            new_begin + j1,
                            new_begin + j2,
                        )
            else:
                yield (
                    "replace"
                    if old_begin < old_end and new_begin < new_end
                    else "delete"
                    if old_begin < old_end
                    else "insert",
                    old_begin,
                    old_end,
                    new_begin,
                    new_end,
                )
        left = anchor_old + 1
        right = anchor_new + 1


def _comma_squashed(*, tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Drop trailing tuple commas that formatter styles may remove.

    Args:
        tokens: Lexical token sequence.

    Returns:
        Tokens with inconsequential trailing commas removed.

    """
    return tuple(
        (
            value
            for index, value in enumerate(iterable=tokens)
            if not (
                value == "55:,"
                and index + 1 < len(tokens)
                and (tokens[index + 1] in {"55:)", "55:]", "55:}"})
            )
        ),
    )


def _python_metrics(
    *,
    original: str,
    changed: str,
    ancestor: tuple[str, ...],
    fork: tuple[str, ...],
) -> DeltaMetrics | None:
    """Measure Python semantics when lexical diffs may understate changes.

    Args:
        original: Ancestor source text.
        changed: Edited source text.
        ancestor: Ancestor tokens.
        fork: Edited tokens.

    Returns:
        Metrics for equivalent or conservatively charged sources, or None
        when the token streams genuinely differ.

    """
    equivalent_tokens: bool = ancestor == fork or (
        len(fork) <= len(ancestor) + 64
        and len(ancestor) <= len(fork) + 64
        and (_comma_squashed(tokens=ancestor) == _comma_squashed(tokens=fork))
    )
    if not equivalent_tokens:
        return None
    try:
        if dump(node=parse(source=original), include_attributes=False) == dump(
            node=parse(source=changed),
            include_attributes=False,
        ) and tuple(findall(pattern="(?m)#.*$", string=original)) == tuple(
            findall(pattern="(?m)#.*$", string=changed),
        ):
            return DeltaMetrics(
                ancestor_tokens=len(ancestor),
                changed_fraction=0.0,
                inserted_tokens=0,
                replaced_tokens=0,
                deleted_tokens=0,
                edit_events=0,
            )
    except SyntaxError:
        pass
    return DeltaMetrics(
        ancestor_tokens=len(ancestor),
        changed_fraction=1.0,
        inserted_tokens=len(fork),
        replaced_tokens=len(ancestor),
        deleted_tokens=0,
        edit_events=1,
    )


def _chunk_delta(
    *,
    kind: str,
    old_text: str,
    new_text: str,
    language: Language,
    span: int,
) -> tuple[int, int, int, int]:
    """Count replaced, deleted, inserted tokens and events for one chunk.

    Args:
        kind: Diff action for the chunk.
        old_text: Ancestor chunk text.
        new_text: Edited chunk text.
        language: Grammar used for tokenization.
        span: Fallback event count for budget-exceeding chunks.

    Returns:
        ``(replaced, deleted, inserted, events)`` tuple.

    """
    old_tokens: tuple[str, ...] = _tokens(source=old_text, language=language)
    if kind in {"delete", "insert"}:
        new_tokens: tuple[str, ...] = _tokens(
            source=new_text,
            language=language,
        )
        return (0, len(old_tokens), len(new_tokens), 1)
    new_tokens = _tokens(source=new_text, language=language)
    if len(old_tokens) + len(new_tokens) > Constants.max_token_budget:
        return (len(old_tokens), 0, len(new_tokens), span)
    replaced: int = 0
    deleted: int = 0
    inserted: int = 0
    events: int = 0
    for action, i1, i2, j1, j2 in SequenceMatcher(
        isjunk=None,
        a=old_tokens,
        b=new_tokens,
        autojunk=True,
    ).get_opcodes():
        if action == "equal":
            continue
        events += 1
        if action == "replace":
            replaced += i2 - i1
            inserted += j2 - j1
        elif action == "delete":
            deleted += i2 - i1
        elif action == "insert":
            inserted += j2 - j1
    return (replaced, deleted, inserted, events)


def measure(
    *,
    original: str,
    changed: str,
    language: Language,
) -> DeltaMetrics:
    """Measure fork deltas using line-local token matches.

    Args:
        original: Common-ancestor source.
        changed: One fork's current source.
        language: Source grammar.

    Returns:
        Mutation budget data.

    Unchanged lines never participate in token-level diff. Large unmatched
    chunks are conservatively counted as full replacements rather than
    exposing an O(n²) repetitive-token comparison to an interactive editor.

    """
    if original == changed:
        return DeltaMetrics(
            ancestor_tokens=0,
            changed_fraction=0.0,
            inserted_tokens=0,
            replaced_tokens=0,
            deleted_tokens=0,
            edit_events=0,
        )
    ancestor: tuple[str, ...] = _tokens(source=original, language=language)
    fork: tuple[str, ...] = _tokens(source=changed, language=language)
    if language == "python":
        python_metrics: DeltaMetrics | None = _python_metrics(
            original=original,
            changed=changed,
            ancestor=ancestor,
            fork=fork,
        )
        if python_metrics is not None:
            return python_metrics
    if language != "python" and ancestor == fork:
        return DeltaMetrics(
            ancestor_tokens=len(ancestor),
            changed_fraction=0.0,
            inserted_tokens=0,
            replaced_tokens=0,
            deleted_tokens=0,
            edit_events=0,
        )
    replaced: int = 0
    deleted: int = 0
    inserted: int = 0
    events: int = 0
    before: list[str] = original.splitlines(keepends=True)
    after: list[str] = changed.splitlines(keepends=True)
    for kind, start, end, new_start, new_end in _changed_lines(
        before=before,
        after=after,
    ):
        if kind == "equal":
            continue
        delta_chunk: tuple[int, int, int, int] = _chunk_delta(
            kind=kind,
            old_text="".join(before[start:end]),
            new_text="".join(after[new_start:new_end]),
            language=language,
            span=max(1, end - start, new_end - new_start),
        )
        replaced += delta_chunk[0]
        deleted += delta_chunk[1]
        inserted += delta_chunk[2]
        events += delta_chunk[3]
    return DeltaMetrics(
        ancestor_tokens=len(ancestor),
        changed_fraction=min(
            1.0,
            (replaced + deleted + inserted) / max(1, len(ancestor)),
        ),
        inserted_tokens=inserted,
        replaced_tokens=replaced,
        deleted_tokens=deleted,
        edit_events=events,
    )


def violations(
    *,
    user: DeltaMetrics,
    tool: DeltaMetrics,
    policy: DeltaPolicy,
    elapsed_seconds: float | None,
) -> tuple[str, ...]:
    """Explain why a lexical delta is too large for automatic merge.

    Args:
        user: User-fork mutation metrics.
        tool: Tool-fork mutation metrics.
        policy: Delta policy bounds.
        elapsed_seconds: Fork editing time budget.

    Returns:
        Human-readable violation details.

    Explain why a lexical delta is too large for automatic reconciliation.

    """
    findings: list[str] = []
    limits: tuple[tuple[str, float, float], ...] = (
        (
            "user changed fraction",
            user.changed_fraction,
            policy.max_user_changed_fraction,
        ),
        (
            "tool changed fraction",
            tool.changed_fraction,
            policy.max_tool_changed_fraction,
        ),
        (
            "combined changed fraction",
            user.changed_fraction + tool.changed_fraction,
            policy.max_combined_changed_fraction,
        ),
        (
            "user inserted tokens",
            user.inserted_tokens,
            policy.max_user_inserted_tokens,
        ),
        (
            "user replaced tokens",
            user.replaced_tokens,
            policy.max_user_replaced_tokens,
        ),
        (
            "user deleted tokens",
            user.deleted_tokens,
            policy.max_user_deleted_tokens,
        ),
        ("user edit regions", user.edit_events, policy.max_user_edit_events),
    )
    findings.extend(
        (
            (f"{name}: {actual:.4g} exceeds {maximum:.4g}")
            for name, actual, maximum in limits
            if actual > maximum
        ),
    )
    if elapsed_seconds is not None:
        if elapsed_seconds < 0:
            findings.append("Fork elapsed time cannot be negative")
        elif (
            elapsed_seconds <= policy.short_fork_seconds
            and (
                user.inserted_tokens
                + user.replaced_tokens
                + user.deleted_tokens
            )
            / max(elapsed_seconds, 0.001)
            > policy.max_user_tokens_per_second
        ):
            findings.append(
                "Short-fork edit burst exceeds configured token-rate limit; "
                "pasted changes require review",
            )
    return tuple(findings)
