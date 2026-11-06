# Copyright (c) 2026
"""Three-way source merge decisions for conflicting proposals.

A transaction owns three images for every touched file: ``A`` — the
original captured when analysis began, ``B`` — the exactus-produced
replacement, and ``C`` — the user's current on-disk state read again
at commit time. ``decide`` resolves which image wins so concurrent
user edits never abort an otherwise-valid run:

- ``C == A`` → accept ``B`` (the user did not touch the file).
- ``C != A`` and ``B == A`` → keep ``C`` (only the user changed it).
- ``C != A`` and ``B != A`` → accept ``B`` while persisting all three
  forked images for a later conciliation merge.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol, final

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.source_transaction import FileImage


def _same_content(*, left: FileImage | None, right: FileImage | None) -> bool:
    """Return whether two images carry identical bytes and mode.

    Args:
        left: First image, or ``None`` for absent.
        right: Second image, or ``None`` for absent.

    Returns:
        ``True`` when both are absent or share data and mode.

    """
    if left is None or right is None:
        return left is right
    return left.data == right.data and left.mode == right.mode


@final
class MergeVerdict(Enum):
    """Outcome of one three-way merge decision.

    Attributes:
        apply_proposed: Accept ``B``; the user file still equals ``A``.
        keep_current: Keep ``C``; the user edited the file while the
            exactus proposal carried no change anyway.
        apply_and_preserve: Accept ``B`` while persisting ``A``, ``B``,
            and ``C`` for a later conciliation merge.

    """

    apply_proposed = auto()
    keep_current = auto()
    apply_and_preserve = auto()


def decide(
    *,
    before: FileImage | None,
    after: FileImage | None,
    current: FileImage | None,
) -> MergeVerdict:
    """Choose the winning image for one transaction target.

    Args:
        before: ``A`` — the original image captured at snapshot time.
        after: ``B`` — the exactus-produced replacement, or ``None``
            when the proposal deletes the file.
        current: ``C`` — the live on-disk image read at commit time.

    Returns:
        Which image the commit must leave behind.

    """
    if _same_content(left=before, right=current):
        return MergeVerdict.apply_proposed
    if _same_content(left=before, right=after):
        return MergeVerdict.keep_current
    return MergeVerdict.apply_and_preserve


class MergedEdit(Protocol):
    """Describe a reconciled live edit produced by an injected merger."""

    @property
    def data(self) -> bytes:
        """Return the merged file bytes.

        Returns:
            Reconciled source encoded as bytes.

        """
        ...

    @property
    def exact(self) -> bool:
        """Return whether the merge was structurally exact.

        Returns:
            True when no placeholder conflict markers remain.

        """
        ...


class LiveMerger(Protocol):
    """Reconcile a concurrent user edit with a tool proposal."""

    def __call__(
        self,
        *,
        suffix: str,
        original: bytes,
        tool: bytes,
        user: bytes,
    ) -> MergedEdit | None:
        """Merge the three byte images, or decline with ``None``.

        Args:
            suffix: File suffix; selects the language.
            original: Common ancestor bytes (``A``).
            tool: The tool-produced bytes (``B``).
            user: The user's live bytes (``C``).

        Returns:
            The merged edit, or ``None`` when it cannot be reconciled.

        """
        ...


def save_conflict(
    *,
    directory: Path,
    relative: Path,
    before: FileImage | None,
    after: FileImage | None,
    current: FileImage | None,
) -> Path:
    """Persist the three forked images for later conciliation.

    Args:
        directory: Conflict root; receives ``<relative>.original``,
            ``<relative>.proposed`` and ``<relative>.current`` siblings.
        relative: Root-relative file whose images are preserved.
        before: ``A`` — the original snapshot image.
        after: ``B`` — the exactus-produced image.
        current: ``C`` — the live on-disk image.

    Returns:
        The conflict root that received the images.

    """
    base: Path = directory / relative
    base.parent.mkdir(parents=True, exist_ok=True)
    suffix: str
    image: FileImage | None
    for suffix, image in (
        (".original", before),
        (".proposed", after),
        (".current", current),
    ):
        target: Path = base.with_name(name=base.name + suffix)
        if image is None:
            target.unlink(missing_ok=True)
        else:
            _ = target.write_bytes(data=image.data)
    return directory
