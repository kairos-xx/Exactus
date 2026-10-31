# Copyright (c) 2026 Project contributors
"""Deterministic network expectation matching for Flow observations."""

from __future__ import annotations

from fnmatch import fnmatchcase
from json import JSONDecodeError, dumps, loads
from re import Match, fullmatch, search
from re import error as regex_error
from typing import cast
from urllib.parse import parse_qs, urlsplit

from exactus.tools.record.model import (
    BodyMatchMode,
    ConditionOperator,
    HttpHeader,
    JsonCondition,
    NetworkExpectation,
    QueryCondition,
    TimelineEvent,
    UrlMatchMode,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class ExpectationEvaluationError(ValueError):
    """Represent ExpectationEvaluationError."""


class NetworkExpectationEvaluator:
    """Represent NetworkExpectationEvaluator."""

    @classmethod
    def evaluate(
        cls,
        *,
        expectation: NetworkExpectation,
        response: TimelineEvent,
    ) -> tuple[bool, str]:
        """Return evaluate.

        Args:
            expectation: Expectation.
            response: Response.

        Returns:
            The resulting value.

        """
        if response.url is None:
            return False, "Observed response has no URL."
        failure: str | None = None
        if (
            expectation.method is not None
            and (response.method or "").upper() != expectation.method.upper()
        ):
            failure = "HTTP method did not match."
        elif expectation.url_pattern is not None and not cls._url_matches(
            url=response.url,
            pattern=expectation.url_pattern,
            mode=expectation.url_match,
        ):
            failure = "URL did not match."
        elif not cls._query_matches(
            url=response.url,
            conditions=expectation.query_conditions,
        ):
            failure = "URL query conditions did not match."
        elif (
            expectation.expected_status is not None
            and response.status != expectation.expected_status
        ):
            failure = "HTTP status did not match."
        elif not cls._headers_match(
            actual=response.headers,
            expected=expectation.expected_headers,
        ):
            failure = "Expected response headers were not present."
        elif not cls._body_matches(
            actual=response.payload,
            expectation=expectation,
        ):
            failure = "Response body did not match."
        elif not cls._json_conditions_match(
            body=response.payload,
            conditions=expectation.json_conditions,
        ):
            failure = "JSON conditions did not match."
        return (
            (True, "Expectation matched.")
            if failure is None
            else (False, failure)
        )

    @classmethod
    def _query_matches(
        cls,
        *,
        url: str,
        conditions: tuple[QueryCondition, ...],
    ) -> bool:
        """Return query matches.

        Args:
            url: Url.
            conditions: Conditions.

        Returns:
            The resulting value.

        """
        query: dict[str, list[str]] = parse_qs(
            qs=urlsplit(url=url).query,
            keep_blank_values=True,
        )
        return all(
            cls._condition_matches(
                actual=query.get(condition.name),
                operator=condition.operator,
                expected=condition.value,
            )
            for condition in conditions
        )

    @classmethod
    def _body_matches(
        cls,
        *,
        actual: str | None,
        expectation: NetworkExpectation,
    ) -> bool:
        """Return body matches.

        Args:
            actual: Actual.
            expectation: Expectation.

        Returns:
            The resulting value.

        """
        if expectation.body_match is BodyMatchMode.NONE:
            return True
        if actual is None or expectation.expected_body is None:
            return False
        if expectation.body_match is BodyMatchMode.EXACT_TEXT:
            return actual == expectation.expected_body
        try:
            actual_json: JsonValue = cast(typ="JsonValue", val=loads(s=actual))
            expected_json: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=expectation.expected_body),
            )
        except JSONDecodeError:
            return False
        if expectation.body_match is BodyMatchMode.JSON_EXACT:
            return actual_json == expected_json
        return cls._json_contains(actual=actual_json, expected=expected_json)

    @classmethod
    def _json_conditions_match(
        cls,
        *,
        body: str | None,
        conditions: tuple[JsonCondition, ...],
    ) -> bool:
        """Return json conditions match.

        Args:
            body: Body.
            conditions: Conditions.

        Returns:
            The resulting value.

        """
        if not conditions:
            return True
        if body is None:
            return False
        try:
            root: JsonValue = cast(typ="JsonValue", val=loads(s=body))
        except JSONDecodeError:
            return False
        return all(
            cls._json_condition_matches(root=root, condition=condition)
            for condition in conditions
        )

    @classmethod
    def _json_condition_matches(
        cls,
        *,
        root: JsonValue,
        condition: JsonCondition,
    ) -> bool:
        """Return json condition matches.

        Args:
            root: Root.
            condition: Condition.

        Returns:
            The resulting value.

        """
        found: bool
        value: JsonValue | None
        found, value = cls._resolve_json_path(root=root, path=condition.path)
        if condition.operator is ConditionOperator.EXISTS:
            return found
        if not found:
            return False
        actual: list[str] = [cls._json_scalar_text(value=value)]
        return cls._condition_matches(
            actual=actual,
            operator=condition.operator,
            expected=condition.value,
        )

    @classmethod
    def _resolve_json_path(
        cls,
        *,
        root: JsonValue,
        path: str,
    ) -> tuple[bool, JsonValue | None]:
        """Return resolve json path.

        Args:
            root: Root.
            path: Path.

        Returns:
            The resulting value.

        """
        if path == "$":
            return True, root
        if not path.startswith("$."):
            return False, None
        current: JsonValue = root
        for component in path[2:].split(sep="."):
            name: str
            index: int | None
            name, index = cls._split_component(component=component)
            if not isinstance(current, dict) or name not in current:
                return False, None
            current = current[name]
            if index is not None:
                if not isinstance(current, list) or index >= len(current):
                    return False, None
                current = current[index]
        return True, current

    @classmethod
    def _json_contains(cls, *, actual: JsonValue, expected: JsonValue) -> bool:
        """Return json contains.

        Args:
            actual: Actual.
            expected: Expected.

        Returns:
            The resulting value.

        """
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(
                key in actual
                and cls._json_contains(
                    actual=actual[key],
                    expected=expected_value,
                )
                for key, expected_value in expected.items()
            )
        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            return all(
                any(
                    cls._json_contains(
                        actual=actual_value,
                        expected=expected_value,
                    )
                    for actual_value in actual
                )
                for expected_value in expected
            )
        return actual == expected

    @staticmethod
    def _url_matches(*, url: str, pattern: str, mode: UrlMatchMode) -> bool:
        """Return url matches.

        Args:
            url: Url.
            pattern: Pattern.
            mode: Mode.

        Returns:
            The resulting value.

        Raises:
            ExpectationEvaluationError: When the operation cannot complete.

        """
        if mode is UrlMatchMode.EXACT:
            return url == pattern
        if mode is UrlMatchMode.CONTAINS:
            return pattern in url
        if mode is UrlMatchMode.GLOB:
            return fnmatchcase(name=url, pat=pattern)
        try:
            return search(pattern=pattern, string=url) is not None
        except regex_error as error:
            raise ExpectationEvaluationError(str(object=error)) from error

    @staticmethod
    def _headers_match(
        *,
        actual: tuple[HttpHeader, ...],
        expected: tuple[HttpHeader, ...],
    ) -> bool:
        """Return headers match.

        Args:
            actual: Actual.
            expected: Expected.

        Returns:
            The resulting value.

        """
        normalized: tuple[tuple[str, str], ...] = tuple(
            (header.name.casefold(), header.value) for header in actual
        )
        return all(
            (header.name.casefold(), header.value) in normalized
            for header in expected
        )

    @staticmethod
    def _split_component(*, component: str) -> tuple[str, int | None]:
        """Return split component.

        Args:
            component: Component.

        Returns:
            The resulting value.

        """
        match: Match[str] | None = fullmatch(
            pattern=r"([^\[\]]+)(?:\[(\d+)\])?",
            string=component,
        )
        if match is None:
            return component, None
        index_text: str | None = match.group(2)
        return match.group(1), None if index_text is None else int(index_text)

    @staticmethod
    def _condition_matches(
        *,
        actual: list[str] | None,
        operator: ConditionOperator,
        expected: str | None,
    ) -> bool:
        """Return condition matches.

        Args:
            actual: Actual.
            operator: Operator.
            expected: Expected.

        Returns:
            The resulting value.

        Raises:
            ExpectationEvaluationError: When the operation cannot complete.

        """
        if operator is ConditionOperator.EXISTS:
            return actual is not None
        if actual is None or expected is None:
            return False
        if operator is ConditionOperator.EQUALS:
            return expected in actual
        if operator is ConditionOperator.NOT_EQUALS:
            return expected not in actual
        if operator is ConditionOperator.CONTAINS:
            return any(expected in value for value in actual)
        try:
            return any(
                search(pattern=expected, string=value) is not None
                for value in actual
            )
        except regex_error as error:
            raise ExpectationEvaluationError(str(object=error)) from error

    @staticmethod
    def _json_scalar_text(*, value: JsonValue | None) -> str:
        """Return json scalar text.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return dumps(
            obj=value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
