# Copyright (c) 2026 Project contributors
"""Error handling and operator coverage of the expression evaluator."""

from typing import Final, final

import pytest

from exactus.tools.record.expressions import (
    ExpressionError,
    ExpressionEvaluator,
    ValueCodec,
)
from exactus.tools.record.model import RuntimeVariable, ValueType


@final
class Constants:
    """Group module-level constants.

    Attributes:
        number: Grouped module constant.
        secret: Grouped module constant.

    """

    number: Final[RuntimeVariable] = RuntimeVariable(
        name="count",
        value_type=ValueType.INTEGER,
        value=3,
    )
    secret: Final[RuntimeVariable] = RuntimeVariable(
        name="token",
        value_type=ValueType.STRING,
        value="s3cret",
        secret=True,
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


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "   ",
        "1 +",
        "lambda: 1",
        "[1, 2]",
        "b'raw' == 'x'",
        "1 in 2",
        "'a' in 1",
        "1 is 1",
        "True < 1",
        "1 < 'a'",
        "unknown(1)",
        "exists()",
        "exists(1, 2)",
        "matches(1)",
        "matches(1, 2)",
        "matches('a', '(')",
        "missing == 1",
    ],
)
def test_invalid_expressions_raise(expression: str) -> None:
    """Malformed or unsupported expressions raise ``ExpressionError``.

    Args:
        expression: Expression.

    """
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.evaluate(
            expression=expression,
            variables=(Constants.number,),
        )


@pytest.mark.parametrize("expression", ["", "1 +"])
def test_validate_rejects_empty_and_syntax_errors(expression: str) -> None:
    """Validation reports empty and unparsable expressions.

    Args:
        expression: Expression.

    """
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.validate(expression=expression)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("count > 2", True),
        ("count >= 3", True),
        ("count < 4", True),
        ("count <= 2", False),
        ("'a' < 'b'", True),
        ("1 == 1 or 1 == 2", True),
        ("1 == 2 or 1 == 2", False),
        ("1 == 1 and 2 == 2", True),
        ("'a' not in 'bcd'", True),
        ("'bc' in 'abcd'", True),
        ("not (count == 3)", False),
    ],
)
def test_operators_evaluate(expression: str, *, expected: bool) -> None:
    """Comparison, boolean, and containment operators evaluate correctly.

    Args:
        expression: Expression.
        expected: Expected.

    """
    _require(
        condition=ExpressionEvaluator.evaluate(
            expression=expression,
            variables=(Constants.number,),
        )
        is expected,
        msg=f"Unexpected result for expression: {expression}",
    )


def test_interpolation_rejects_unknown_and_secret_variables() -> None:
    """Templates cannot reference unknown or secret variables."""
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.interpolate(
            template="${nothing}",
            variables=(Constants.number,),
        )
    with pytest.raises(expected_exception=ExpressionError):
        ExpressionEvaluator.interpolate(
            template="${token}",
            variables=(Constants.secret,),
        )


def test_boolean_coercion_accepts_booleans_and_rejects_text() -> None:
    """Booleans pass through; unrecognized text is rejected."""
    _require(
        condition=ValueCodec.coerce(value_type=ValueType.BOOLEAN, value=True)
        is True,
        msg="Boolean coercion did not pass through.",
    )
    with pytest.raises(expected_exception=ExpressionError):
        ValueCodec.coerce(value_type=ValueType.BOOLEAN, value="maybe")
