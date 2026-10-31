# Copyright (c) 2026 Project contributors
"""Tests for action-attributed network expectation matching."""

from typing import cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    private_call,
    private_result,
)
from exactus.tools.record.expectations import (
    ExpectationEvaluationError,
    NetworkExpectationEvaluator,
)
from exactus.tools.record.model import (
    BodyMatchMode,
    ConditionOperator,
    EventKind,
    HttpHeader,
    JsonCondition,
    NetworkExpectation,
    QueryCondition,
    TimelineEvent,
    TimelineLayer,
    UrlMatchMode,
)


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


def _response(*, status: int = 200) -> TimelineEvent:
    """Return response.

    Args:
        status: Status.

    Returns:
        The resulting value.

    """
    return TimelineEvent(
        event_id="response-1",
        flow_id="flow-1",
        sequence=1,
        elapsed_ms=10,
        layer=TimelineLayer.NETWORK,
        kind=EventKind.RESPONSE,
        label="GET items",
        url="https://example.test/api/items?page=1&mode=full",
        method="GET",
        status=status,
        headers=(HttpHeader(name="Content-Type", value="application/json"),),
        payload='{"ok":true,"data":{"id":7,"name":"A"}}',
        caused_by_event_id="click-1",
    )


def test_expectation_matches_query_status_headers_and_json() -> None:
    """Handle test expectation matches query status headers and json."""
    expectation: NetworkExpectation = NetworkExpectation(
        expectation_id="x1",
        label="items response",
        method="GET",
        url_pattern="*/api/items*",
        url_match=UrlMatchMode.GLOB,
        query_conditions=(
            QueryCondition(
                name="page",
                operator=ConditionOperator.EQUALS,
                value="1",
            ),
        ),
        expected_status=200,
        expected_headers=(
            HttpHeader(name="content-type", value="application/json"),
        ),
        body_match=BodyMatchMode.JSON_CONTAINS,
        expected_body='{"ok":true,"data":{"id":7}}',
        json_conditions=(
            JsonCondition(
                path="$.data.name",
                operator=ConditionOperator.EQUALS,
                value='"A"',
            ),
        ),
    )
    matched: bool
    details: str
    matched, details = NetworkExpectationEvaluator.evaluate(
        expectation=expectation,
        response=_response(),
    )
    _require(condition=matched, msg=details)


def test_expectation_fails_on_unexpected_status() -> None:
    """Handle test expectation fails on unexpected status."""
    expectation: NetworkExpectation = NetworkExpectation(
        expectation_id="x1",
        label="items response",
        method="GET",
        url_pattern="https://example.test/api/items?page=1&mode=full",
        expected_status=201,
    )
    matched: bool
    details: str
    matched, details = NetworkExpectationEvaluator.evaluate(
        expectation=expectation,
        response=_response(),
    )
    _require(condition=not matched, msg="Status mismatch unexpectedly passed.")
    _require(condition="status" in details.lower(), msg=details)


def test_expectation_failure_dimensions_and_body_modes() -> None:
    """Cover URL, method, query, header, and body mismatch dimensions."""
    cases: tuple[NetworkExpectation, ...] = (
        NetworkExpectation(expectation_id="m", label="method", method="POST"),
        NetworkExpectation(
            expectation_id="u",
            label="url",
            url_pattern="/missing",
            url_match=UrlMatchMode.CONTAINS,
        ),
        NetworkExpectation(
            expectation_id="q",
            label="query",
            query_conditions=(
                QueryCondition(
                    name="missing",
                    operator=ConditionOperator.EXISTS,
                ),
            ),
        ),
        NetworkExpectation(
            expectation_id="h",
            label="header",
            expected_headers=(HttpHeader(name="X-Missing", value="x"),),
        ),
        NetworkExpectation(
            expectation_id="b",
            label="body",
            body_match=BodyMatchMode.EXACT_TEXT,
            expected_body="different",
        ),
        NetworkExpectation(
            expectation_id="j",
            label="json",
            body_match=BodyMatchMode.JSON_EXACT,
            expected_body='{"ok":false}',
        ),
        NetworkExpectation(
            expectation_id="c",
            label="condition",
            json_conditions=(
                JsonCondition(
                    path="$.data.missing",
                    operator=ConditionOperator.EXISTS,
                ),
            ),
        ),
    )
    for expectation in cases:
        matched: bool
        details: str
        matched, details = NetworkExpectationEvaluator.evaluate(
            expectation=expectation,
            response=_response(),
        )
        _require(
            condition=not matched,
            msg=f"Mismatch unexpectedly passed: {details}",
        )


def test_expectation_url_and_json_helpers_cover_variants() -> None:
    """Cover URL modes, indexed JSON paths, and condition operators."""
    response: TimelineEvent = _response()
    for mode, pattern in (
        (UrlMatchMode.EXACT, response.url or ""),
        (UrlMatchMode.CONTAINS, "/api/items"),
        (UrlMatchMode.REGEX, r"example\.test/.+items"),
    ):
        expectation: NetworkExpectation = NetworkExpectation(
            expectation_id=f"url-{mode.value}",
            label="url",
            url_pattern=pattern,
            url_match=mode,
        )
        matched: bool
        details: str
        matched, details = NetworkExpectationEvaluator.evaluate(
            expectation=expectation,
            response=response,
        )
        _require(condition=matched, msg=details)
    indexed: NetworkExpectation = NetworkExpectation(
        expectation_id="indexed",
        label="indexed",
        json_conditions=(
            JsonCondition(
                path="$.data.id",
                operator=ConditionOperator.NOT_EQUALS,
                value="8",
            ),
            JsonCondition(
                path="$.data.name",
                operator=ConditionOperator.CONTAINS,
                value="A",
            ),
            JsonCondition(
                path="$.data.name",
                operator=ConditionOperator.REGEX,
                value='^"A"$',
            ),
        ),
    )
    matched, details = NetworkExpectationEvaluator.evaluate(
        expectation=indexed,
        response=response,
    )
    _require(condition=matched, msg=details)


def test_expectation_helper_edge_paths() -> None:
    """Check expectation helpers cover their edge paths."""
    evaluator: type[NetworkExpectationEvaluator] = NetworkExpectationEvaluator
    with pytest.raises(expected_exception=ExpectationEvaluationError):
        private_call(
            owner=evaluator,
            name="_url_matches",
            url="x",
            pattern="[",
            mode=UrlMatchMode.REGEX,
        )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_body_matches",
            kind=bool,
            actual=None,
            expectation=NetworkExpectation(
                expectation_id="x",
                label="x",
                body_match=BodyMatchMode.EXACT_TEXT,
                expected_body="x",
            ),
        ),
        msg="Missing body should not match exact-text expectation.",
    )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_body_matches",
            kind=bool,
            actual="{",
            expectation=NetworkExpectation(
                expectation_id="x",
                label="x",
                body_match=BodyMatchMode.JSON_EXACT,
                expected_body="{}",
            ),
        ),
        msg="Malformed JSON should not match exact-json expectation.",
    )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_json_conditions_match",
            kind=bool,
            body=None,
            conditions=(
                JsonCondition(path="$.x", operator=ConditionOperator.EXISTS),
            ),
        ),
        msg="Missing body should not satisfy JSON conditions.",
    )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_json_conditions_match",
            kind=bool,
            body="{",
            conditions=(
                JsonCondition(path="$.x", operator=ConditionOperator.EXISTS),
            ),
        ),
        msg="Malformed JSON should not satisfy JSON conditions.",
    )
    expect_equal(
        actual=cast(
            typ="tuple[object, ...]",
            val=private_result(
                owner=evaluator,
                name="_resolve_json_path",
                kind=tuple,
                root={"x": 1},
                path="$",
            ),
        ),
        expected=(True, {"x": 1}),
    )
    expect_equal(
        actual=cast(
            typ="tuple[object, ...]",
            val=private_result(
                owner=evaluator,
                name="_resolve_json_path",
                kind=tuple,
                root={},
                path="x",
            ),
        ),
        expected=(False, None),
    )
    expect_equal(
        actual=cast(
            typ="tuple[object, ...]",
            val=private_result(
                owner=evaluator,
                name="_resolve_json_path",
                kind=tuple,
                root={"x": []},
                path="$.x[2]",
            ),
        ),
        expected=(False, None),
    )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_condition_matches",
            kind=bool,
            actual=None,
            operator=ConditionOperator.EQUALS,
            expected="x",
        ),
        msg="Missing value should not satisfy EQUALS.",
    )
    with pytest.raises(expected_exception=ExpectationEvaluationError):
        private_call(
            owner=evaluator,
            name="_condition_matches",
            actual=["x"],
            operator=ConditionOperator.REGEX,
            expected="[",
        )
    _require(
        condition=not private_result(
            owner=evaluator,
            name="_json_contains",
            kind=bool,
            actual={},
            expected=[],
        ),
        msg="Non-matching JSON containment should fail.",
    )
