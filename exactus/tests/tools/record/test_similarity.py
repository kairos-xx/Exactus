# Copyright (c) 2026
"""Perceptual image similarity loading and cache contracts."""

from __future__ import annotations

from base64 import b64encode
from io import BytesIO
from re import compile as re_compile
from typing import TYPE_CHECKING, Final, final

import pytest
from PIL import Image

from exactus.tests.common.support import expect_equal, expect_true
from exactus.tools.record.similarity import ImageSimilarity, SimilarityResult

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.record.similarity import ImageSource


@final
class Constants:
    """Group module-level constants.

    Attributes:
        near_identical: Grouped module constant.

    """

    near_identical: Final[float] = 0.999


def _png_bytes(*, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Encode a solid 8x8 PNG.

    Args:
        color: Fill color.

    Returns:
        Encoded PNG bytes.

    """
    stream: BytesIO = BytesIO()
    Image.new(mode="RGB", size=(8, 8), color=color).save(
        fp=stream,
        format="PNG",
    )
    return stream.getvalue()


def test_load_source_variants(tmp_path: Path) -> None:
    """Every ``ImageSource`` shape decodes to an RGB image.

    Args:
        tmp_path: Temporary directory for the path-based source.

    """
    payload: bytes = _png_bytes()
    target: Path = tmp_path / "pixel.png"
    _ = target.write_bytes(data=payload)
    similarity: ImageSimilarity = ImageSimilarity()
    sources: tuple[ImageSource, ...] = (
        Image.new(mode="RGBA", size=(8, 8)),
        target,
        str(object=target),
        payload,
        b64encode(s=payload),
        f"data:image/png;base64,{b64encode(s=payload).decode()}",
        BytesIO(initial_bytes=payload),
    )
    for source in sources:
        expect_equal(actual=similarity.remember(source=source), expected=0)
        similarity.clear_cache()


def test_load_rejections(tmp_path: Path) -> None:
    """Undecodable sources raise ``ValueError``.

    Args:
        tmp_path: Temporary directory for a corrupt image file.

    """
    corrupt: Path = tmp_path / "broken.png"
    _ = corrupt.write_bytes(data=b"not an image")
    similarity: ImageSimilarity = ImageSimilarity()
    rejected: tuple[ImageSource, ...] = (
        corrupt,
        "not a path or base64 !!",
        "data:image/png;base64,!!!",
        b"\x00\x01\x02\x03",
        BytesIO(initial_bytes=b"junk"),
    )
    for source in rejected:
        with pytest.raises(
            expected_exception=ValueError,
            match=re_compile(pattern=r"\S+"),
        ):
            similarity.remember(source=source)


def test_history_and_cache() -> None:
    """``remember``/``compare_history`` grow the fingerprint cache."""
    similarity: ImageSimilarity = ImageSimilarity()
    expect_equal(actual=similarity.cache_size, expected=0)
    expect_equal(actual=similarity.remember(source=_png_bytes()), expected=0)
    expect_equal(
        actual=similarity.remember(source=_png_bytes(color=(0, 0, 255))),
        expected=1,
    )
    expect_equal(actual=similarity.cache_size, expected=2)
    history: tuple[object, ...] = similarity.compare_history(
        source=_png_bytes(),
        remember=False,
    )
    expect_equal(actual=len(history), expected=2)
    expect_equal(actual=similarity.cache_size, expected=2)
    similarity.clear_cache()
    expect_equal(actual=similarity.cache_size, expected=0)


def test_compare_scores() -> None:
    """Identical images score 1.0; distinct colors score lower."""
    red: bytes = _png_bytes()
    blue: bytes = _png_bytes(color=(0, 0, 255))
    expect_true(
        condition=ImageSimilarity.compare(first=red, second=red)
        > Constants.near_identical,
    )
    different: float = ImageSimilarity.compare(first=red, second=blue)
    expect_true(condition=0.0 < different < 1.0)


def test_compare_detailed_breakdown() -> None:
    """The detailed comparison exposes component scores."""
    result: SimilarityResult = ImageSimilarity.compare_detailed(
        first=_png_bytes(),
        second=_png_bytes(),
    )
    expect_true(condition=result.similarity > Constants.near_identical)
