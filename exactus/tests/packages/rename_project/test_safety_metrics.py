"""Safety-oriented corpus metrics with asymmetric failure accounting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from exactus.tests.packages.rename_project.assertions import expect_equal


class Disposition(StrEnum):
    """Simplified classification used by metric accounting.

    Attributes:
        GUARDED: Guarded.
        SAFE: Safe.

    """

    SAFE = "safe"
    GUARDED = "guarded"


@dataclass(frozen=True, slots=True)
class Metrics:
    """Classification quality counters.

    Attributes:
        conservative_false_negatives: Conservative false negatives.
        correct: Correct.
        dangerous_false_positives: Dangerous false positives.
        total: Total.

    """

    total: int
    correct: int
    dangerous_false_positives: int
    conservative_false_negatives: int

    @property
    def accuracy(self) -> float:
        """Exact classification accuracy.

        Returns:
            The resulting value.

        """
        return 1.0 if self.total == 0 else self.correct / self.total


def measure(
    expected: tuple[Disposition, ...],
    actual: tuple[Disposition, ...],
) -> Metrics:
    """Measure safety errors, distinguishing dangerous from conservative.

    Args:
        expected: Value for ``expected``.
        actual: Value for ``actual``.

    Returns:
        The resulting value.

    Raises:
        ValueError: When the operation cannot complete.

    """
    if len(expected) != len(actual):
        msg: str = "Expected and actual classification counts differ"
        raise ValueError(msg)
    dangerous: int = sum(
        wanted is Disposition.GUARDED and got is Disposition.SAFE
        for wanted, got in zip(expected, actual, strict=True)
    )
    conservative: int = sum(
        wanted is Disposition.SAFE and got is Disposition.GUARDED
        for wanted, got in zip(expected, actual, strict=True)
    )
    return Metrics(
        total=len(expected),
        correct=sum(
            wanted is got for wanted, got in zip(expected, actual, strict=True)
        ),
        dangerous_false_positives=dangerous,
        conservative_false_negatives=conservative,
    )


def test_metric_distinguishes_error_severity() -> None:
    """A permissive mistake must not be conflated with a conservative miss."""
    metrics: Metrics = measure(
        expected=(Disposition.GUARDED, Disposition.SAFE, Disposition.SAFE),
        actual=(Disposition.SAFE, Disposition.GUARDED, Disposition.SAFE),
    )
    expect_equal(actual=metrics.total, expected=3)
    expect_equal(actual=metrics.correct, expected=1)
    expect_equal(actual=metrics.dangerous_false_positives, expected=1)
    expect_equal(actual=metrics.conservative_false_negatives, expected=1)
    expect_equal(actual=metrics.accuracy, expected=1 / 3)
