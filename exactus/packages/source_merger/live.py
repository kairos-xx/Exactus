# Copyright (c) 2026
"""Reconcile a concurrent user edit with a tool proposal.

The tracked three-way merge treats the tool's proposal as the structural
destination and projects the user's changes onto it. When it reports a
conflict, a whitespace-insensitive token merge is tried and accepted
only for disjoint hunks that keep the result valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from exactus.packages.source_merger.cache import SnapshotCache
from exactus.packages.source_merger.engine import SourceMerger
from exactus.packages.source_merger.tokens import merge_tokens_bounded

if TYPE_CHECKING:
    from exactus.packages.source_merger.model import Language, MergeResult


@final
class Constants:
    """Group module-level constants.

    Attributes:
        languages: Grouped module constant.

    """

    languages: Final[dict[str, Language]] = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".css": "css",
        ".html": "html",
    }


@final
@dataclass(frozen=True, slots=True)
class LiveMerge:
    """Carry a reconciled live edit and how trustworthy the merge is.

    Attributes:
        data: Merged file bytes.
        exact: ``True`` for the tracked structural merge; ``False`` for
            the token-level fallback, which callers must keep reviewable.

    """

    data: bytes
    exact: bool


def _valid(*, source: str, language: Language) -> bool:
    """Report whether source parses in its language.

    Args:
        source: Candidate text.
        language: Grammar to apply.

    Returns:
        Whether the parser accepts the text.

    """
    return all(
        snapshot.valid
        for snapshot in SnapshotCache().parse_many(
            sources=(source,),
            language=language,
        )
    )


def _token_candidate(
    *,
    original: str,
    user: str,
    tool: str,
    language: Language,
) -> str | None:
    """Merge by tokens and reject candidates that regress validity.

    Args:
        original: Common ancestor text.
        user: User's fork.
        tool: Tool's fork.
        language: Grammar used for the validity check.

    Returns:
        Merged text, or ``None`` on conflict or newly invalid syntax.

    """
    candidate: str | None = merge_tokens_bounded(
        original=original,
        user_edited=user,
        tool_refactored=tool,
    )
    if candidate is None:
        return None
    if _valid(source=tool, language=language) and (
        not _valid(source=candidate, language=language)
    ):
        return None
    return candidate


def merge_live_edit(
    *,
    suffix: str,
    original: bytes,
    tool: bytes,
    user: bytes,
) -> LiveMerge | None:
    """Reconcile a concurrent user edit with the tool's proposal.

    Unsupported languages, undecodable text or true conflicts yield
    ``None`` so the caller keeps its fork-preserving behavior.

    Args:
        suffix: File suffix; selects the language.
        original: Common ancestor bytes (``A``).
        tool: The tool-produced bytes (``B``).
        user: The user's live bytes (``C``).

    Returns:
        The merged bytes with their trust level, else ``None``.

    """
    language: Language | None = Constants.languages.get(suffix)
    if language is None:
        return None
    try:
        before: str = original.decode(encoding="utf-8")
        current: str = user.decode(encoding="utf-8")
        after: str = tool.decode(encoding="utf-8")
        result: MergeResult = SourceMerger(
            original=before,
            user_edited=current,
            tool_refactored=after,
            language=language,
        ).merge()
        exact: bool = result.success and result.source is not None
        text: str | None = (
            result.source
            if exact
            else _token_candidate(
                original=before,
                user=current,
                tool=after,
                language=language,
            )
        )
    except (UnicodeDecodeError, ValueError, OSError, RuntimeError):
        return None
    if text is None:
        return None
    merged: bytes = text.encode(encoding="utf-8")
    if suffix == ".py":
        try:
            _ = compile(
                source=merged,
                filename="<live-merge>",
                mode="exec",
                dont_inherit=True,
            )
        except (SyntaxError, ValueError):
            return None
    return LiveMerge(data=merged, exact=exact)
