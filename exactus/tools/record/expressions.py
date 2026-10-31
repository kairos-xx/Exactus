# Copyright (c) 2026 Project contributors
"""Safe deterministic expression and template evaluation for Flow execution."""

from __future__ import annotations

from ast import (
    AST,
    And,
    BoolOp,
    Call,
    Compare,
    Constant,
    Eq,
    Expression,
    Gt,
    GtE,
    In,
    Load,
    Lt,
    LtE,
    Name,
    Not,
    NotEq,
    NotIn,
    Or,
    UnaryOp,
    cmpop,
    expr,
    parse,
    walk,
)
from json import JSONDecodeError, dumps, loads
from re import Match, Pattern, search
from re import compile as re_compile
from re import error as regex_error
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from types import EllipsisType
from exactus.tools.record.model import RuntimeVariable, ValueType

type ScalarValue = str | int | float | bool | None
type JsonValue = ScalarValue | list[JsonValue] | dict[str, JsonValue]


@final
class Constants:
    """Group module-level constants.

    Attributes:
        template_pattern: Grouped module constant.
        allowed_functions: Grouped module constant.
        binary_argument_count: Grouped module constant.

    """

    template_pattern: Final[Pattern[str]] = re_compile(
        pattern="\\$\\{([A-Za-z_][\\w.-]*)\\}",
    )
    allowed_functions: Final[frozenset[str]] = frozenset(
        {"contains", "exists", "matches"},
    )
    binary_argument_count: Final[int] = 2


class ExpressionError(ValueError):
    """Represent ExpressionError."""


class ValueCodec:
    """Represent ValueCodec."""

    @classmethod
    def coerce(
        cls,
        *,
        value_type: ValueType,
        value: ScalarValue,
    ) -> ScalarValue:
        """Return coerce.

        Args:
            value_type: Value type.
            value: Value.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if value is None:
            return None
        try:
            if value_type is ValueType.STRING:
                return str(object=value)
            if value_type is ValueType.INTEGER:
                return cls._integer(value=value)
            if value_type is ValueType.FLOAT:
                return cls._float(value=value)
            if value_type is ValueType.BOOLEAN:
                return cls._boolean(value=value)
            if value_type is ValueType.JSON:
                return cls._json(value=value)
        except (TypeError, ValueError, JSONDecodeError) as error:
            msg: str = (
                f"Value {value!r} is invalid for type {value_type.value}."
            )
            raise ExpressionError(msg) from error
        msg = f"Unsupported value type: {value_type.value}"
        raise ExpressionError(msg)

    @staticmethod
    def render(*, variable: RuntimeVariable) -> str:
        """Return render.

        Args:
            variable: Variable.

        Returns:
            The resulting value.

        """
        if variable.value is None:
            return ""
        if variable.value_type is ValueType.BOOLEAN:
            return "true" if variable.value is True else "false"
        return str(object=variable.value)

    @staticmethod
    def _integer(*, value: ScalarValue) -> int:
        """Return integer.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if value is None or isinstance(value, bool):
            msg: str = "Only non-boolean scalar values become integers."
            raise TypeError(msg)
        return int(value)

    @staticmethod
    def _float(*, value: ScalarValue) -> float:
        """Return float.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if value is None or isinstance(value, bool):
            msg: str = "Only non-boolean scalar values become floats."
            raise TypeError(msg)
        return float(value)

    @staticmethod
    def _boolean(*, value: ScalarValue) -> bool:
        """Return boolean.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized: str = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        msg: str = f"Cannot coerce {value!r} to boolean."
        raise ValueError(msg)

    @staticmethod
    def _json(*, value: ScalarValue) -> str:
        """Return json.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if not isinstance(value, str):
            msg: str = "JSON values must be supplied as JSON strings."
            raise TypeError(msg)
        parsed: JsonValue = cast(typ="JsonValue", val=loads(s=value))
        return dumps(
            obj=parsed,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


class ExpressionEvaluator:
    """Represent ExpressionEvaluator."""

    @classmethod
    def evaluate(
        cls,
        *,
        expression: str,
        variables: tuple[RuntimeVariable, ...],
    ) -> bool:
        """Return evaluate.

        Args:
            expression: Expression.
            variables: Variables.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if expression.strip() == "":
            msg: str = "Expression cannot be empty."
            raise ExpressionError(msg)
        try:
            tree: Expression = parse(source=expression, mode="eval")
        except SyntaxError as error:
            raise ExpressionError(str(object=error)) from error
        environment: dict[str, ScalarValue] = {
            variable.name: variable.value for variable in variables
        }
        result: ScalarValue = cls._node_value(
            node=tree.body,
            environment=environment,
        )
        if not isinstance(result, bool):
            msg = "Transition expression must evaluate to a boolean."
            raise ExpressionError(msg)
        return result

    @staticmethod
    def validate(*, expression: str) -> None:
        """Handle validate.

        Args:
            expression: Expression.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if expression.strip() == "":
            msg: str = "Expression cannot be empty."
            raise ExpressionError(msg)
        try:
            tree: Expression = parse(source=expression, mode="eval")
        except SyntaxError as error:
            msg = str(object=error)
            raise ExpressionError(msg) from error
        allowed: tuple[type[AST], ...] = (
            Expression,
            BoolOp,
            And,
            Or,
            UnaryOp,
            Not,
            Compare,
            Eq,
            NotEq,
            Gt,
            GtE,
            Lt,
            LtE,
            In,
            NotIn,
            Name,
            Load,
            Constant,
            Call,
        )
        for node in walk(node=tree):
            if not isinstance(node, allowed):
                msg = f"Unsupported expression syntax: {type(node).__name__}"
                raise ExpressionError(msg)
            if isinstance(node, Call) and (
                not isinstance(node.func, Name)
                or node.func.id not in Constants.allowed_functions
                or node.keywords
            ):
                msg = "Expression contains an unsupported function call."
                raise ExpressionError(msg)

    @staticmethod
    def interpolate(
        *,
        template: str,
        variables: tuple[RuntimeVariable, ...],
    ) -> str:
        """Return interpolate.

        Args:
            template: Template.
            variables: Variables.

        Returns:
            The resulting value.

        """
        environment: dict[str, RuntimeVariable] = {
            variable.name: variable for variable in variables
        }

        def replace_match(match: Match[str]) -> str:
            """Return replace match.

            Args:
                match: Match.

            Returns:
                The resulting value.

            Raises:
                ExpressionError: When the operation cannot complete.

            """
            name: str = match.group(1)
            if (variable := environment.get(name)) is None:
                msg: str = f"Unknown template variable: {name}"
                raise ExpressionError(msg)
            if variable.secret:
                msg = f"Secret variable {name} cannot be interpolated here."
                raise ExpressionError(msg)
            return ValueCodec.render(variable=variable)

        return Constants.template_pattern.sub(
            repl=replace_match,
            string=template,
        )

    @classmethod
    def _node_value(
        cls,
        *,
        node: expr,
        environment: dict[str, ScalarValue],
    ) -> ScalarValue:
        """Return node value.

        Args:
            node: Node.
            environment: Environment.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if isinstance(node, Constant):
            return cls._constant(node=node)
        if isinstance(node, Name):
            if node.id not in environment:
                msg: str = f"Unknown variable: {node.id}"
                raise ExpressionError(msg)
            return environment[node.id]
        if isinstance(node, UnaryOp) and isinstance(node.op, Not):
            return not cls._truthy(
                value=cls._node_value(
                    node=node.operand,
                    environment=environment,
                ),
            )
        if isinstance(node, BoolOp):
            return cls._boolean_operation(node=node, environment=environment)
        if isinstance(node, Compare):
            return cls._comparison(node=node, environment=environment)
        if isinstance(node, Call):
            return cls._call(node=node, environment=environment)
        msg = f"Unsupported expression node: {type(node).__name__}"
        raise ExpressionError(msg)

    @classmethod
    def _boolean_operation(
        cls,
        *,
        node: BoolOp,
        environment: dict[str, ScalarValue],
    ) -> bool:
        """Return boolean operation.

        Args:
            node: Node.
            environment: Environment.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if isinstance(node.op, And):
            return all(
                cls._truthy(
                    value=cls._node_value(node=value, environment=environment),
                )
                for value in node.values
            )
        if isinstance(node.op, Or):
            return any(
                cls._truthy(
                    value=cls._node_value(node=value, environment=environment),
                )
                for value in node.values
            )
        msg: str = "Unsupported boolean operator."
        raise ExpressionError(msg)

    @classmethod
    def _comparison(
        cls,
        *,
        node: Compare,
        environment: dict[str, ScalarValue],
    ) -> bool:
        """Return comparison.

        Args:
            node: Node.
            environment: Environment.

        Returns:
            The resulting value.

        """
        left: ScalarValue = cls._node_value(
            node=node.left,
            environment=environment,
        )
        comparisons: list[bool] = []
        for operator, comparator in zip(
            node.ops,
            node.comparators,
            strict=True,
        ):
            right: ScalarValue = cls._node_value(
                node=comparator,
                environment=environment,
            )
            comparisons.append(
                cls._compare(left=left, operator=operator, right=right),
            )
            left = right
        return all(comparisons)

    @classmethod
    def _compare(
        cls,
        *,
        left: ScalarValue,
        operator: cmpop,
        right: ScalarValue,
    ) -> bool:
        """Return compare.

        Args:
            left: Left.
            operator: Operator.
            right: Right.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if isinstance(operator, Eq):
            return left == right
        if isinstance(operator, NotEq):
            return left != right
        if isinstance(operator, In):
            return cls._contains(container=right, item=left)
        if isinstance(operator, NotIn):
            return not cls._contains(container=right, item=left)
        if isinstance(operator, (Gt, GtE, Lt, LtE)):
            return cls._ordered_compare(
                left=left,
                operator=operator,
                right=right,
            )
        msg: str = "Unsupported comparison operator."
        raise ExpressionError(msg)

    @classmethod
    def _ordered_compare(
        cls,
        *,
        left: ScalarValue,
        operator: cmpop,
        right: ScalarValue,
    ) -> bool:
        """Return ordered compare.

        Args:
            left: Left.
            operator: Operator.
            right: Right.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if isinstance(left, bool) or isinstance(right, bool):
            msg: str = "Booleans cannot participate in ordered comparisons."
            raise ExpressionError(msg)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            left_value: float = float(left)
            right_value: float = float(right)
        elif isinstance(left, str) and isinstance(right, str):
            return cls._string_compare(
                left=left,
                operator=operator,
                right=right,
            )
        else:
            msg = "Ordered comparison operands must have compatible types."
            raise ExpressionError(msg)
        if isinstance(operator, Gt):
            return left_value > right_value
        if isinstance(operator, GtE):
            return left_value >= right_value
        if isinstance(operator, Lt):
            return left_value < right_value
        return left_value <= right_value

    @classmethod
    def _call(cls, *, node: Call, environment: dict[str, ScalarValue]) -> bool:
        """Return call.

        Args:
            node: Node.
            environment: Environment.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if (
            not isinstance(node.func, Name)
            or node.func.id not in Constants.allowed_functions
            or node.keywords
        ):
            msg: str = "Only approved expression helpers are callable."
            raise ExpressionError(msg)
        values: tuple[ScalarValue, ...] = tuple(
            cls._node_value(node=argument, environment=environment)
            for argument in node.args
        )
        if node.func.id == "exists":
            if len(values) != 1:
                msg = "exists() requires one argument."
                raise ExpressionError(msg)
            return values[0] is not None
        if node.func.id == "contains":
            if len(values) != Constants.binary_argument_count:
                msg = "contains() requires two arguments."
                raise ExpressionError(msg)
            return cls._contains(container=values[0], item=values[1])
        if len(values) != Constants.binary_argument_count:
            msg = "matches() requires two string arguments."
            raise ExpressionError(msg)
        subject: ScalarValue = values[0]
        pattern: ScalarValue = values[1]
        if not isinstance(subject, str) or not isinstance(pattern, str):
            msg = "matches() requires two string arguments."
            raise ExpressionError(msg)
        try:
            return search(pattern=pattern, string=subject) is not None
        except regex_error as error:
            raise ExpressionError(str(object=error)) from error

    @staticmethod
    def _constant(*, node: Constant) -> ScalarValue:
        """Return constant.

        Args:
            node: Node.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        value: (
            str | bytes | int | float | complex | bool | EllipsisType | None
        ) = node.value
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        msg: str = f"Unsupported literal type: {type(value).__name__}"
        raise ExpressionError(msg)

    @staticmethod
    def _truthy(*, value: ScalarValue) -> bool:
        """Return truthy.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return bool(value)

    @staticmethod
    def _string_compare(*, left: str, operator: cmpop, right: str) -> bool:
        """Return string compare.

        Args:
            left: Left.
            operator: Operator.
            right: Right.

        Returns:
            The resulting value.

        """
        if isinstance(operator, Gt):
            return left > right
        if isinstance(operator, GtE):
            return left >= right
        if isinstance(operator, Lt):
            return left < right
        return left <= right

    @staticmethod
    def _contains(*, container: ScalarValue, item: ScalarValue) -> bool:
        """Return contains.

        Args:
            container: Container.
            item: Item.

        Returns:
            The resulting value.

        Raises:
            ExpressionError: When the operation cannot complete.

        """
        if not isinstance(container, str) or not isinstance(item, str):
            msg: str = "Containment requires string operands."
            raise ExpressionError(msg)
        return item in container
