"""Coverage for assertion evaluation and causal attribution."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tools.record.assertions import (
    AssertionEvaluationError,
    AssertionEvaluator,
)
from exactus.tools.record.causality import CausalAttributor
from exactus.tools.record.model import (
    AssertionKind,
    AssertionOperator,
    AssertionOutcome,
    AssertionSpec,
    EventKind,
    TimelineEvent,
    TimelineLayer,
)

if TYPE_CHECKING:
    from exactus.tools.record.causality import AttributionDecision
    from exactus.tools.record.model import AssertionResult


def _require(*, condition: bool, msg: str) -> None:
    """Handle require.

    Args:
        condition: Condition.
        msg: Msg.

    Raises:
        AssertionError: When the operation cannot complete.

    """
    if not condition:
        raise AssertionError(msg)


def spec(
    operator: AssertionOperator,
    expected: str | None = "x",
) -> AssertionSpec:
    """Build an assertion spec for one operator.

    Args:
        operator: Operator under test.
        expected: Expected value text.

    Returns:
        The configured spec.

    """
    return AssertionSpec(
        assertion_id=f"a-{operator.value}",
        label="test",
        kind=AssertionKind.URL,
        operator=operator,
        expected=expected,
    )


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "exists", "outcome"),
    [
        (
            AssertionOperator.EXISTS,
            None,
            None,
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.NOT_EXISTS,
            None,
            None,
            False,
            AssertionOutcome.SUCCEEDED,
        ),
        (AssertionOperator.EQUALS, "x", "x", True, AssertionOutcome.SUCCEEDED),
        (
            AssertionOperator.NOT_EQUALS,
            "x",
            "y",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.CONTAINS,
            "abc",
            "b",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.REGEX,
            "abc",
            "a.c",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.GREATER_THAN,
            "3",
            "2",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.GREATER_THAN_OR_EQUAL,
            "2",
            "2",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.LESS_THAN,
            "1",
            "2",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (
            AssertionOperator.LESS_THAN_OR_EQUAL,
            "2",
            "2",
            True,
            AssertionOutcome.SUCCEEDED,
        ),
        (AssertionOperator.EQUALS, "x", "y", True, AssertionOutcome.FAILED),
        (AssertionOperator.EQUALS, None, "x", False, AssertionOutcome.FAILED),
    ],
)
def test_assertion_operators(
    operator: AssertionOperator,
    actual: str | None,
    expected: str | None,
    *,
    exists: bool,
    outcome: AssertionOutcome,
) -> None:
    """Check one operator row of the evaluation truth table.

    Args:
        operator: Operator under test.
        actual: Actual page value.
        expected: Expected value text.
        exists: Whether the target element exists.
        outcome: Expected assertion outcome.

    """
    result: AssertionResult = AssertionEvaluator.evaluate(
        assertion=spec(operator=operator, expected=expected),
        actual=actual,
        exists=exists,
    )
    _require(
        condition=result.outcome is outcome,
        msg="Assertion outcome mismatch.",
    )
    _require(condition=result.details != "", msg="Missing result details.")


def test_assertion_errors() -> None:
    """Check malformed specs raise evaluation errors."""
    with pytest.raises(expected_exception=AssertionEvaluationError):
        AssertionEvaluator.evaluate(
            assertion=spec(operator=AssertionOperator.REGEX, expected="["),
            actual="x",
            exists=True,
        )
    with pytest.raises(expected_exception=AssertionEvaluationError):
        AssertionEvaluator.evaluate(
            assertion=spec(
                operator=AssertionOperator.GREATER_THAN,
                expected="x",
            ),
            actual="y",
            exists=True,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EventDetails:
    """Optional timeline-event fields used by the attribution tests.

    Attributes:
        flow_id: Flow identifier shared by related events.
        url: Event URL, when the event has one.
        correlation_id: Correlation identifier linking related events.
        initiator_url: URL of the event initiator, when known.
        initiator_stack: Initiator stack frames.
        caused_by_event_id: Identifier of the causing event.

    """

    flow_id: str = "f"
    url: str | None = None
    correlation_id: str | None = None
    initiator_url: str | None = None
    initiator_stack: tuple[str, ...] = ()
    caused_by_event_id: str | None = None


@final
class Constants:
    """Group module-level constants.

    Attributes:
        min_confidence: Grouped module constant.
        expected_candidates: Grouped module constant.
        default_details: Grouped module constant.

    """

    min_confidence: Final[float] = 0.9
    expected_candidates: Final[int] = 2
    default_details: Final[EventDetails] = EventDetails()


def event(
    event_id: str,
    kind: EventKind,
    elapsed_ms: int,
    *,
    details: EventDetails = Constants.default_details,
) -> TimelineEvent:
    """Build a timeline event with test defaults.

    Args:
        event_id: Event identifier.
        kind: Event kind.
        elapsed_ms: Milliseconds since the run started.
        details: Optional event fields.

    Returns:
        The configured event.

    """
    selector: str | None = "#x" if kind is EventKind.CLICK else None
    return TimelineEvent(
        event_id=event_id,
        flow_id=details.flow_id,
        sequence=0,
        elapsed_ms=elapsed_ms,
        layer=TimelineLayer.INTERACTION
        if kind is EventKind.CLICK
        else TimelineLayer.NETWORK,
        kind=kind,
        label=event_id,
        selector=selector,
        url=details.url,
        correlation_id=details.correlation_id,
        initiator_url=details.initiator_url,
        initiator_stack=details.initiator_stack,
        caused_by_event_id=details.caused_by_event_id,
    )


def test_causal_attribution_paths() -> None:
    """Check causal attribution follows each evidence path."""
    action: TimelineEvent = event(
        event_id="a",
        kind=EventKind.CLICK,
        elapsed_ms=100,
        details=EventDetails(url="https://x", correlation_id="c"),
    )
    obs: TimelineEvent = event(
        event_id="o",
        kind=EventKind.RESPONSE,
        elapsed_ms=200,
        details=EventDetails(
            correlation_id="c",
            initiator_url="https://x",
            initiator_stack=("https://x/script.js",),
        ),
    )
    decision: AttributionDecision = CausalAttributor.attribute(
        observation=obs,
        prior_events=(action,),
    )
    _require(condition=decision.inferred, msg="Attribution not inferred.")
    _require(
        condition=decision.event.caused_by_event_id == "a",
        msg="Attribution pointed at the wrong event.",
    )
    _require(
        condition=decision.candidates[0].confidence > Constants.min_confidence,
        msg="Attribution confidence too low.",
    )
    already: TimelineEvent = event(
        event_id="o2",
        kind=EventKind.RESPONSE,
        elapsed_ms=200,
        details=EventDetails(caused_by_event_id="a"),
    )
    _require(
        condition=not CausalAttributor.attribute(
            observation=already,
            prior_events=(action,),
        ).inferred,
        msg="Pre-attributed event should not be re-attributed.",
    )
    note: TimelineEvent = event(
        event_id="n",
        kind=EventKind.NOTE,
        elapsed_ms=200,
    )
    _require(
        condition=not CausalAttributor.attribute(
            observation=note,
            prior_events=(action,),
        ).inferred,
        msg="Note event should not be attributed.",
    )
    _require(
        condition=not CausalAttributor.attribute(
            observation=event(
                event_id="late",
                kind=EventKind.RESPONSE,
                elapsed_ms=7000,
            ),
            prior_events=(action,),
        ).inferred,
        msg="Late observation should not be attributed.",
    )
    wrong_flow: TimelineEvent = event(
        event_id="b",
        kind=EventKind.CLICK,
        elapsed_ms=100,
        details=EventDetails(flow_id="other"),
    )
    _require(
        condition=not CausalAttributor.attribute(
            observation=obs,
            prior_events=(wrong_flow,),
        ).inferred,
        msg="Cross-flow attribution should not be inferred.",
    )


def test_causal_ambiguity_does_not_guess() -> None:
    """Check ambiguous candidates are left unattributed."""
    first: TimelineEvent = event(
        event_id="a1",
        kind=EventKind.CLICK,
        elapsed_ms=100,
        details=EventDetails(url="https://a"),
    )
    second: TimelineEvent = event(
        event_id="a2",
        kind=EventKind.CLICK,
        elapsed_ms=101,
        details=EventDetails(url="https://b"),
    )
    obs: TimelineEvent = event(
        event_id="o",
        kind=EventKind.RESPONSE,
        elapsed_ms=150,
    )
    decision: AttributionDecision = CausalAttributor.attribute(
        observation=obs,
        prior_events=(first, second),
    )
    _require(
        condition=not decision.inferred,
        msg="Ambiguous candidates should stay unattributed.",
    )
    _require(
        condition=len(decision.candidates) == Constants.expected_candidates,
        msg="Both candidates should be reported.",
    )
