# Copyright (c) 2026
"""Multi-factor perceptual image similarity scoring."""

from __future__ import annotations

from base64 import b64decode
from binascii import Error
from dataclasses import dataclass
from io import BytesIO
from math import log2, sqrt
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING, BinaryIO, Self, cast

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

type ImageSource = str | bytes | Path | BinaryIO | Image.Image
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


@dataclass(frozen=True, slots=True)
class SimilarityResult:
    """Contain the components of an image similarity comparison.

    Attributes:
        similarity: Final weighted similarity from zero to one.
        appearance: Normalized pixel-appearance similarity.
        structure: Multi-scale structural similarity.
        perceptual: Perceptual difference-hash similarity.
        color: Color-distribution similarity.
        geometry: Original size and aspect-ratio similarity.

    """

    similarity: float
    appearance: float
    structure: float
    perceptual: float
    color: float
    geometry: float


@dataclass(frozen=True, slots=True)
class CachedComparison:
    """Contain a comparison against one previously cached image.

    Attributes:
        index: Zero-based index of the cached reference image.
        result: Detailed similarity result against that image.

    """

    index: int
    result: SimilarityResult


@dataclass(frozen=True, slots=True)
class _ImageFingerprint:
    """Contain precomputed image features used by comparisons.

    Attributes:
        size: Original image dimensions.
        normalized: Normalized RGB analysis image.
        structure: Luminance and edge images for each structural scale.
        perceptual: Difference-hash bits.
        histogram: Normalized RGB histogram.

    """

    size: tuple[int, int]
    normalized: Image.Image
    structure: tuple[tuple[Image.Image, Image.Image], ...]
    perceptual: tuple[bool, ...]
    histogram: tuple[float, ...]


class ImageSimilarity:
    """Compare images and cache fingerprints for repeated comparisons."""

    _ANALYSIS_SIZE: int = 256
    _HASH_WIDTH: int = 16
    _HASH_HEIGHT: int = 16
    _STRUCTURE_SCALES: tuple[int, ...] = (256, 128, 64, 32)
    _STRUCTURE_WEIGHTS: tuple[float, ...] = (0.40, 0.30, 0.20, 0.10)
    _APPEARANCE_WEIGHT: float = 0.30
    _STRUCTURE_WEIGHT: float = 0.35
    _PERCEPTUAL_WEIGHT: float = 0.15
    _COLOR_WEIGHT: float = 0.10
    _GEOMETRY_WEIGHT: float = 0.10

    def __init__(self) -> None:
        """Initialize an empty comparison fingerprint cache."""
        self._fingerprints: list[_ImageFingerprint] = []

    @classmethod
    def compare(cls, first: ImageSource, second: ImageSource) -> float:
        """Return perceptual similarity between two images.

        Args:
            first: First supported image source.
            second: Second supported image source.

        Returns:
            Similarity in the inclusive range zero to one.


        Notes:
            The operation fails if either source cannot be decoded as an image.

        """
        return cls.compare_detailed(first=first, second=second).similarity

    @classmethod
    def compare_detailed(
        cls,
        first: ImageSource,
        second: ImageSource,
    ) -> SimilarityResult:
        """Return the final score and individual similarity components.

        Args:
            first: First supported image source.
            second: Second supported image source.

        Returns:
            Detailed immutable similarity result.


        Notes:
            The operation fails if either source cannot be decoded as an image.

        """
        return cls._compare_fingerprints(
            first=cls._fingerprint(image=cls._load(source=first)),
            second=cls._fingerprint(image=cls._load(source=second)),
        )

    @property
    def cache_size(self) -> int:
        """The number of cached image fingerprints.

        Returns:
            Number of cached images.

        """
        return len(self._fingerprints)

    def clear_cache(self) -> None:
        """Remove all cached image fingerprints."""
        self._fingerprints.clear()

    def remember(self, source: ImageSource) -> int:
        """Fingerprint and cache an image without comparing it.

        Args:
            source: Supported image source to cache.

        Returns:
            Zero-based cache index assigned to the image.


        Notes:
            The operation fails if the source cannot be decoded as an image.

        """
        self._fingerprints.append(
            self._fingerprint(image=self._load(source=source)),
        )
        return len(self._fingerprints) - 1

    def compare_history(
        self,
        source: ImageSource,
        *,
        remember: bool = True,
    ) -> tuple[CachedComparison, ...]:
        """Compare a new image against every cached image fingerprint.

        The new image is fingerprinted only once. By default its fingerprint is
        appended after comparison, so each consecutive call compares against
        every image supplied to earlier calls.

        Args:
            source: New image to compare against the cache.
            remember: Whether to cache the new fingerprint after comparison.

        Returns:
            Comparisons in cache insertion order. The first call returns an
            empty tuple because no prior images exist.


        Notes:
            The operation fails if the source cannot be decoded as an image.

        """
        fingerprint: _ImageFingerprint = self._fingerprint(
            image=self._load(source=source),
        )
        comparisons: tuple[CachedComparison, ...] = tuple(
            CachedComparison(
                index=index,
                result=self._compare_fingerprints(
                    first=previous,
                    second=fingerprint,
                ),
            )
            for index, previous in enumerate(iterable=self._fingerprints)
        )
        if remember:
            self._fingerprints.append(fingerprint)
        return comparisons

    @classmethod
    def _compare_fingerprints(
        cls,
        first: _ImageFingerprint,
        second: _ImageFingerprint,
    ) -> SimilarityResult:
        """Compare two precomputed image fingerprints.

        Args:
            first: First image fingerprint.
            second: Second image fingerprint.

        Returns:
            Detailed immutable similarity result.

        """
        appearance: float = cls._image_difference_similarity(
            first=first.normalized,
            second=second.normalized,
        )
        structure: float = cls._fingerprint_structure(
            first=first.structure,
            second=second.structure,
        )
        perceptual: float = cls._hash_similarity(
            first=first.perceptual,
            second=second.perceptual,
        )
        color: float = cls._histogram_similarity(
            first=first.histogram,
            second=second.histogram,
        )
        geometry: float = cls._geometry_sizes(
            first=first.size,
            second=second.size,
        )
        return SimilarityResult(
            similarity=cls._clamp(
                value=(
                    appearance * cls._APPEARANCE_WEIGHT
                    + structure * cls._STRUCTURE_WEIGHT
                    + perceptual * cls._PERCEPTUAL_WEIGHT
                    + color * cls._COLOR_WEIGHT
                    + geometry * cls._GEOMETRY_WEIGHT
                ),
            ),
            appearance=appearance,
            structure=structure,
            perceptual=perceptual,
            color=color,
            geometry=geometry,
        )

    @classmethod
    def _fingerprint(cls, image: Image.Image) -> _ImageFingerprint:
        """Precompute every reusable feature required for comparison.

        Args:
            image: Loaded RGB image.

        Returns:
            Immutable image fingerprint.

        """
        normalized: Image.Image = cls._normalized(image=image)
        histogram: list[int] = normalized.histogram()
        histogram_total: int = sum(histogram)
        return _ImageFingerprint(
            size=image.size,
            normalized=normalized,
            structure=tuple(
                (
                    (
                        gray := cls._normalized(
                            image=image,
                            size=size,
                        ).convert(mode="L")
                    ),
                    gray.filter(filter=ImageFilter.FIND_EDGES),
                )
                for size in cls._STRUCTURE_SCALES
            ),
            perceptual=cls._difference_hash(image=image),
            histogram=tuple(value / histogram_total for value in histogram),
        )

    @classmethod
    def _load(cls, source: ImageSource) -> Image.Image:
        """Load an image from any supported representation.

        Args:
            source: Image source.

        Returns:
            Loaded RGB image.

        Raises:
            ValueError: If the source cannot be decoded.

        """
        if isinstance(source, Image.Image):
            return source.convert(mode="RGB")
        if isinstance(source, Path):
            return cls._load_path(path=source)
        if isinstance(source, str):
            return cls._load_string(source=source)
        if isinstance(source, bytes):
            return cls._load_binary(value=source)
        try:
            position: int | None = source.tell() if source.seekable() else None
            data: bytes = source.read()
            if position is not None:
                _ = source.seek(position)
            return cls._load_bytes(value=data)
        except (OSError, ValueError, TypeError) as error:
            msg: str = "Cannot read image from file object."
            raise ValueError(msg) from error

    @classmethod
    def _load_string(cls, source: str) -> Image.Image:
        """Load an image from a path string or Base64 payload.

        Args:
            source: Filesystem path, data URL, or Base64 image text.

        Returns:
            Loaded RGB image.

        Raises:
            ValueError: If the string is neither a path nor Base64.

        """
        if (path := Path(source)).is_file():
            return cls._load_path(path=path)
        encoded: str = (
            source.split(sep=",", maxsplit=1)[1]
            if source.startswith("data:image/") and "," in source
            else source
        )
        try:
            return cls._load_bytes(value=b64decode(s=encoded, validate=True))
        except (Error, ValueError) as error:
            msg: str = "String is neither an image path nor valid Base64."
            raise ValueError(msg) from error

    @classmethod
    def _load_binary(cls, value: bytes) -> Image.Image:
        """Load an image from raw or Base64-encoded bytes.

        Args:
            value: Encoded image data or Base64 text bytes.

        Returns:
            Loaded RGB image.

        Raises:
            ValueError: If the bytes are neither an image nor Base64.

        """
        try:
            return cls._load_bytes(value=value)
        except ValueError:
            try:
                return cls._load_bytes(value=b64decode(s=value, validate=True))
            except (Error, ValueError) as error:
                msg: str = "Bytes are neither an image nor valid Base64."
                raise ValueError(msg) from error

    @classmethod
    def _normalized(
        cls,
        image: Image.Image,
        size: int | None = None,
    ) -> Image.Image:
        """Normalize an image to a common square canvas.

        Args:
            image: Source image.
            size: Optional output dimension.

        Returns:
            Normalized RGB image.

        """
        dimension: int = size or cls._ANALYSIS_SIZE
        return ImageOps.pad(
            image=image.convert(mode="RGB"),
            size=(dimension, dimension),
            method=Image.Resampling.LANCZOS,
            color="black",
            centering=(0.5, 0.5),
        )

    @classmethod
    def _fingerprint_structure(
        cls,
        first: tuple[tuple[Image.Image, Image.Image], ...],
        second: tuple[tuple[Image.Image, Image.Image], ...],
    ) -> float:
        """Compare precomputed multi-scale structural features.

        Args:
            first: First luminance/edge scale features.
            second: Second luminance/edge scale features.

        Returns:
            Weighted multi-scale structural similarity.

        """
        return cls._clamp(
            value=sum(
                (
                    cls._image_difference_similarity(
                        first=first_scale[0],
                        second=second_scale[0],
                    )
                    * 0.35
                    + cls._image_difference_similarity(
                        first=first_scale[1],
                        second=second_scale[1],
                    )
                    * 0.65
                )
                * weight
                for first_scale, second_scale, weight in zip(
                    first,
                    second,
                    cls._STRUCTURE_WEIGHTS,
                    strict=True,
                )
            ),
        )

    @classmethod
    def _image_difference_similarity(
        cls: type[Self],
        first: Image.Image,
        second: Image.Image,
    ) -> float:
        """Calculate normalized mean absolute image similarity.

        Args:
            first: First equally sized image.
            second: Second equally sized image.

        Returns:
            Similarity from zero to one.

        """
        difference: Image.Image = ImageChops.difference(
            image1=first,
            image2=second,
        )
        return cls._clamp(
            value=1.0
            - fmean(data=ImageStat.Stat(image_or_list=difference).mean)
            / 255.0,
        )

    @classmethod
    def _difference_hash(cls, image: Image.Image) -> tuple[bool, ...]:
        """Calculate a perceptual difference hash.

        Args:
            image: Source image.

        Returns:
            Boolean hash representation.

        """
        resized: Image.Image = image.convert(mode="L").resize(
            size=(cls._HASH_WIDTH + 1, cls._HASH_HEIGHT),
            resample=Image.Resampling.LANCZOS,
        )
        pixels: list[int] = list(
            cast(
                typ="Callable[[], Iterable[int]]",
                val=getattr(resized, "get_flattened_data", None)
                or resized.getdata,
            )(),
        )
        return tuple(
            pixels[row * (cls._HASH_WIDTH + 1) + column]
            > pixels[row * (cls._HASH_WIDTH + 1) + column + 1]
            for row in range(cls._HASH_HEIGHT)
            for column in range(cls._HASH_WIDTH)
        )

    @classmethod
    def _histogram_similarity(
        cls,
        first: tuple[float, ...],
        second: tuple[float, ...],
    ) -> float:
        """Compare normalized color histograms.

        Args:
            first: First normalized histogram.
            second: Second normalized histogram.

        Returns:
            Histogram intersection similarity.

        """
        return cls._clamp(
            value=sum(
                min(first_value, second_value)
                for first_value, second_value in zip(
                    first,
                    second,
                    strict=True,
                )
            ),
        )

    @classmethod
    def _geometry_sizes(
        cls,
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> float:
        """Measure similarity between two original image sizes.

        Args:
            first: First image width and height.
            second: Second image width and height.

        Returns:
            Geometry similarity.

        """
        first_width: int
        first_height: int
        first_width, first_height = first
        second_width: int
        second_height: int
        second_width, second_height = second
        dimension_similarity: float = sqrt(
            cls._ratio(first=float(first_width), second=float(second_width))
            * cls._ratio(
                first=float(first_height),
                second=float(second_height),
            ),
        )
        aspect_similarity: float = cls._ratio(
            first=first_width / first_height,
            second=second_width / second_height,
        )
        return cls._clamp(
            value=(dimension_similarity * 0.35 + aspect_similarity * 0.65),
        )

    @staticmethod
    def _load_path(path: Path) -> Image.Image:
        """Load an image from a filesystem path.

        Args:
            path: Image path.

        Returns:
            Loaded RGB image.

        Raises:
            ValueError: If Pillow cannot decode the file.

        """
        try:
            with Image.open(fp=path) as image:
                return image.convert(mode="RGB")
        except (OSError, ValueError) as error:
            msg: str = f"Cannot decode image file: {path}"
            raise ValueError(msg) from error

    @staticmethod
    def _load_bytes(value: bytes) -> Image.Image:
        """Decode encoded image bytes.

        Args:
            value: Encoded image data.

        Returns:
            Decoded RGB image.

        Raises:
            ValueError: If Pillow cannot decode the bytes.

        """
        try:
            with Image.open(fp=BytesIO(initial_bytes=value)) as image:
                return image.convert(mode="RGB")
        except (OSError, ValueError) as error:
            msg: str = "Cannot decode image bytes."
            raise ValueError(msg) from error

    @staticmethod
    def _hash_similarity(
        first: tuple[bool, ...],
        second: tuple[bool, ...],
    ) -> float:
        """Compare two precomputed perceptual hashes.

        Args:
            first: First hash bits.
            second: Second hash bits.

        Returns:
            Perceptual similarity.

        """
        differences: int = sum(
            left != right for left, right in zip(first, second, strict=True)
        )
        return 1.0 - differences / len(first)

    @staticmethod
    def _ratio(first: float, second: float) -> float:
        """Calculate symmetric logarithmic ratio similarity.

        Args:
            first: First positive value.
            second: Second positive value.

        Returns:
            Ratio similarity from zero to one.

        """
        return cast(typ="float", val=2.0 ** -abs(log2(first / second)))

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp a similarity value to its valid range.

        Args:
            value: Input value.

        Returns:
            Value between zero and one.

        """
        return max(0.0, min(1.0, value))
