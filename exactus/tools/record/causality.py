# Copyright (c) 2026 Project contributors
"""Deterministic causal attribution for recorded browser observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

from exactus.tools.record.model import EventKind, TimelineEvent


@final
class Constants:
    """Group module-level constants.

    Attributes:
        maximum_causal_window_ms: Grouped module constant.
        minimum_confidence: Grouped module constant.
        minimum_winner_margin: Grouped module constant.
        temporal_weight: Grouped module constant.
        correlation_weight: Grouped module constant.
        initiator_weight: Grouped module constant.
        stack_weight: Grouped module constant.
        observation_kinds: Grouped module constant.

    """

    maximum_causal_window_ms: Final[int] = 5000
    minimum_confidence: Final[float] = 0.35
    minimum_winner_margin: Final[float] = 0.08
    temporal_weight: Final[float] = 0.45
    correlation_weight: Final[float] = 0.4
    initiator_weight: Final[float] = 0.1
    stack_weight: Final[float] = 0.05
    observation_kinds: Final[frozenset[EventKind]] = frozenset(
        {
            EventKind.REQUEST,
            EventKind.RESPONSE,
            EventKind.WEBSOCKET_OPEN,
            EventKind.WEBSOCKET_SENT,
            EventKind.WEBSOCKET_RECEIVED,
            EventKind.WEBSOCKET_CLOSE,
            EventKind.WEBSOCKET_ERROR,
            EventKind.CONSOLE,
            EventKind.URL_CHANGE,
        },
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributionCandidate:
    """Represent AttributionCandidate.

    Attributes:
        event_id: Event id.
        confidence: Confidence.
        reasons: Reasons.

    """

    event_id: str
    confidence: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributionDecision:
    """Represent AttributionDecision.

    Attributes:
        event: Event.
        candidates: Candidates.
        inferred: Inferred.

    """

    event: TimelineEvent
    candidates: tuple[AttributionCandidate, ...]
    inferred: bool


class CausalAttributor:
    """Represent CausalAttributor."""

    @classmethod
    def attribute(
        cls,
        *,
        observation: TimelineEvent,
        prior_events: tuple[TimelineEvent, ...],
    ) -> AttributionDecision:
        """Return attribute.

        Args:
            observation: Observation.
            prior_events: Prior events.

        Returns:
            The resulting value.

        """
        if (
            observation.caused_by_event_id is not None
            or observation.kind not in Constants.observation_kinds
        ):
            return AttributionDecision(
                event=observation,
                candidates=(),
                inferred=False,
            )
        candidates: list[AttributionCandidate] = sorted(
            (
                candidate
                for event in prior_events
                if (
                    candidate := cls._score(
                        observation=observation,
                        candidate=event,
                    )
                )
                is not None
            ),
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )
        if (
            not candidates
            or candidates[0].confidence < Constants.minimum_confidence
        ):
            return AttributionDecision(
                event=observation,
                candidates=tuple(candidates),
                inferred=False,
            )
        if (
            len(candidates) > 1
            and candidates[0].confidence - candidates[1].confidence
            < Constants.minimum_winner_margin
        ):
            return AttributionDecision(
                event=observation,
                candidates=tuple(candidates),
                inferred=False,
            )
        winner: AttributionCandidate = candidates[0]
        return AttributionDecision(
            event=observation.with_attribution(
                caused_by_event_id=winner.event_id,
                confidence=winner.confidence,
                reasons=winner.reasons,
            ),
            candidates=tuple(candidates),
            inferred=True,
        )

    @staticmethod
    def _score(
        *,
        observation: TimelineEvent,
        candidate: TimelineEvent,
    ) -> AttributionCandidate | None:
        """Return score.

        Args:
            observation: Observation.
            candidate: Candidate.

        Returns:
            The resulting value.

        """
        if (
            candidate.flow_id != observation.flow_id
            or not candidate.supports_network_expectations
            or candidate.elapsed_ms > observation.elapsed_ms
        ):
            return None
        delta_ms: int = observation.elapsed_ms - candidate.elapsed_ms
        if delta_ms > Constants.maximum_causal_window_ms:
            return None
        confidence: float = Constants.temporal_weight * (
            1.0 - delta_ms / Constants.maximum_causal_window_ms
        )
        reasons: list[str] = [f"temporal proximity {delta_ms} ms"]
        if (
            candidate.correlation_id is not None
            and candidate.correlation_id == observation.correlation_id
        ):
            confidence += Constants.correlation_weight
            reasons.append("matching correlation ID")
        if (
            candidate.url is not None
            and observation.initiator_url is not None
            and (candidate.url == observation.initiator_url)
        ):
            confidence += Constants.initiator_weight
            reasons.append("matching initiator URL")
        if candidate.url is not None and any(
            candidate.url in frame for frame in observation.initiator_stack
        ):
            confidence += Constants.stack_weight
            reasons.append("initiator stack references action URL")
        return AttributionCandidate(
            event_id=candidate.event_id,
            confidence=min(1.0, confidence),
            reasons=tuple(reasons),
        )
