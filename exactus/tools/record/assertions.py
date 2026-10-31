# Copyright (c) 2026 Project contributors
"""Generic assertion comparison shared by UI, protocol, and test runtime."""

from __future__ import annotations

from re import error as regex_error
from re import search

from exactus.tools.record.model import (
    AssertionOperator,
    AssertionOutcome,
    AssertionResult,
    AssertionSpec,
)


class AssertionEvaluationError(ValueError):
    """Represent AssertionEvaluationError."""


class AssertionEvaluator:
    """Represent AssertionEvaluator."""

    @classmethod
    def evaluate(
        cls,
        *,
        assertion: AssertionSpec,
        actual: str | None,
        exists: bool,
    ) -> AssertionResult:
        """Return evaluate.

        Args:
            assertion: Assertion.
            actual: Actual.
            exists: Exists.

        Returns:
            The resulting value.

        Raises:
            AssertionEvaluationError: When the operation cannot complete.

        """
        try:
            matched: bool = cls._matches(
                assertion=assertion,
                actual=actual,
                exists=exists,
            )
        except (ValueError, regex_error) as error:
            raise AssertionEvaluationError(str(object=error)) from error
        return AssertionResult(
            assertion_id=assertion.assertion_id,
            outcome=(
                AssertionOutcome.SUCCEEDED
                if matched
                else AssertionOutcome.FAILED
            ),
            details=(
                "Assertion matched."
                if matched
                else cls._failure_details(
                    assertion=assertion,
                    actual=actual,
                    exists=exists,
                )
            ),
            actual=actual,
        )

    @classmethod
    def _matches(
        cls,
        *,
        assertion: AssertionSpec,
        actual: str | None,
        exists: bool,
    ) -> bool:
        """Return matches.

        Args:
            assertion: Assertion.
            actual: Actual.
            exists: Exists.

        Returns:
            The resulting value.

        """
        operator: AssertionOperator = assertion.operator
        if operator in {
            AssertionOperator.EXISTS,
            AssertionOperator.NOT_EXISTS,
        }:
            return (
                exists if operator is AssertionOperator.EXISTS else not exists
            )
        if not exists or actual is None or assertion.expected is None:
            return False
        if operator in {
            AssertionOperator.EQUALS,
            AssertionOperator.NOT_EQUALS,
            AssertionOperator.CONTAINS,
            AssertionOperator.REGEX,
        }:
            return cls._text_compare(
                operator=operator,
                actual=actual,
                expected=assertion.expected,
            )
        return cls._numeric_compare(
            operator=operator,
            actual=actual,
            expected=assertion.expected,
        )

    @staticmethod
    def _text_compare(
        *,
        operator: AssertionOperator,
        actual: str,
        expected: str,
    ) -> bool:
        """Return text compare.

        Args:
            operator: Operator.
            actual: Actual.
            expected: Expected.

        Returns:
            The resulting value.

        """
        if operator is AssertionOperator.EQUALS:
            return actual == expected
        if operator is AssertionOperator.NOT_EQUALS:
            return actual != expected
        if operator is AssertionOperator.CONTAINS:
            return expected in actual
        return search(pattern=expected, string=actual) is not None

    @staticmethod
    def _numeric_compare(
        *,
        operator: AssertionOperator,
        actual: str,
        expected: str,
    ) -> bool:
        """Return numeric compare.

        Args:
            operator: Operator.
            actual: Actual.
            expected: Expected.

        Returns:
            The resulting value.

        Raises:
            AssertionEvaluationError: When the operation cannot complete.

        """
        actual_number: float = float(actual)
        expected_number: float = float(expected)
        if operator is AssertionOperator.GREATER_THAN:
            return actual_number > expected_number
        if operator is AssertionOperator.GREATER_THAN_OR_EQUAL:
            return actual_number >= expected_number
        if operator is AssertionOperator.LESS_THAN:
            return actual_number < expected_number
        if operator is AssertionOperator.LESS_THAN_OR_EQUAL:
            return actual_number <= expected_number
        msg: str = f"Unsupported assertion operator: {operator.value}"
        raise AssertionEvaluationError(msg)

    @staticmethod
    def _failure_details(
        *,
        assertion: AssertionSpec,
        actual: str | None,
        exists: bool,
    ) -> str:
        """Return failure details.

        Args:
            assertion: Assertion.
            actual: Actual.
            exists: Exists.

        Returns:
            The resulting value.

        """
        return (
            f"{assertion.kind.value} {assertion.operator.value}: "
            f"expected={assertion.expected!r}, actual={actual!r}, "
            f"exists={exists}."
        )
