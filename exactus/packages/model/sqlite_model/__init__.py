"""Typed, dependency-free SQLite AST, compiler, and execution layer."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
from enum import Enum
from functools import lru_cache
from sqlite3 import (
    Connection,
    Cursor,
    DatabaseError,
    Error,
    IntegrityError,
    Row,
    complete_statement,
    connect,
)
from types import NoneType, UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

    from _typeshed import DataclassInstance
type SqlScalar = str | int | float | bytes | None
type Parameters = tuple[SqlScalar, ...]


def _quoted(*, value: str, quote: str) -> str:
    """Return ``value`` surrounded by ``quote``, escaping inner quotes.

    Args:
        value: Value.
        quote: Quote.

    Returns:
        The resulting value.

    """
    return quote + value.replace(quote, quote + quote) + quote


def _quoted_identifier(*, value: str) -> str:
    """Return ``value`` as a double-quoted SQLite identifier.

    Args:
        value: Value.

    Returns:
        The resulting value.

    """
    return _quoted(value=value, quote='"')


class SQLiteLayerError(RuntimeError):
    """Base error raised by the SQLite abstraction."""


class CompileError(SQLiteLayerError):
    """Raised when an AST cannot be compiled."""


class ParameterError(SQLiteLayerError):
    """Raised for invalid statement parameters or cardinality."""


class ConstraintError(SQLiteLayerError):
    """Raised when SQLite rejects a constraint."""


class SchemaError(SQLiteLayerError):
    """Raised for schema verification failures."""


class UnsupportedFeatureError(CompileError):
    """Raised when an AST requests unsupported SQLite syntax."""


@dataclass(frozen=True, slots=True)
class PrimaryKey:
    """Mark a dataclass field as part of a primary key."""


@dataclass(frozen=True, slots=True)
class Unique:
    """Mark a dataclass field as a ``UNIQUE`` column."""


@dataclass(frozen=True, slots=True)
class Identifier:
    """A validated SQLite identifier.

    Attributes:
        value: Value.

    """

    value: str

    def __post_init__(self) -> None:
        """Reject empty and NUL-containing identifiers.

        Raises:
            ValueError: When the identifier is empty or contains a NUL.

        """
        if not self.value or "\x00" in self.value:
            msg: str = "SQLite identifiers must be nonempty and NUL-free"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Parameter[S: SqlScalar]:
    """A positional SQLite parameter placeholder."""


@dataclass(frozen=True, slots=True)
class Literal[S: SqlScalar]:
    """A structural literal emitted by the compiler.

    Attributes:
        value: Value.

    """

    value: S


@dataclass(frozen=True, slots=True)
class Column:
    """A typed column reference.

    Attributes:
        name: Name.
        table: Table.

    """

    name: str
    table: str | None = None

    def eq(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build an equality predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.EQ, value=value)

    def ne(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build an inequality predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.NE, value=value)

    def lt(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build a less-than predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.LT, value=value)

    def le(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build a less-than-or-equal predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.LE, value=value)

    def gt(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build a greater-than predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.GT, value=value)

    def ge(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build a greater-than-or-equal predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.GE, value=value)

    def is_(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build an ``IS`` predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.IS, value=value)

    def is_not(self, *, value: ExpressionNode) -> BinaryExpression:
        """Build an ``IS NOT`` predicate against ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return self._binary(operator=BinaryOperator.IS_NOT, value=value)

    def is_null(self) -> NullExpression:
        """Build an ``IS NULL`` predicate.

        Returns:
            The resulting value.

        """
        return NullExpression(column=self, negate=False)

    def is_not_null(self) -> NullExpression:
        """Build an ``IS NOT NULL`` predicate.

        Returns:
            The resulting value.

        """
        return NullExpression(column=self, negate=True)

    def like(
        self,
        *,
        value: ExpressionNode,
        negate: bool = False,
    ) -> BinaryExpression:
        """Build a ``LIKE`` (or ``NOT LIKE``) predicate.

        Args:
            value: Value.
            negate: Negate.

        Returns:
            The resulting value.

        """
        return self._binary(
            operator=BinaryOperator.NOT_LIKE
            if negate
            else BinaryOperator.LIKE,
            value=value,
        )

    def in_(self, *, values: tuple[ExpressionNode, ...]) -> InExpression:
        """Build an ``IN`` predicate over ``values``.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        return InExpression(column=self, values=values, negate=False)

    def not_in_values(
        self,
        *,
        values: tuple[ExpressionNode, ...],
    ) -> InExpression:
        """Build a ``NOT IN`` predicate over ``values``.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        return InExpression(column=self, values=values, negate=True)

    def in_subquery(self, *, statement: Select) -> InSubqueryExpression:
        """Build an ``IN`` predicate over a subquery.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        return InSubqueryExpression(
            column=self,
            statement=statement,
            negate=False,
        )

    def not_in(self, *, statement: Select) -> InSubqueryExpression:
        """Build a ``NOT IN`` predicate over a subquery.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        return InSubqueryExpression(
            column=self,
            statement=statement,
            negate=True,
        )

    def desc(self) -> Ordering:
        """Build a descending ``ORDER BY`` term.

        Returns:
            The resulting value.

        """
        return Ordering(expression=self, descending=True)

    def alias(self, *, name: str) -> Alias:
        """Build an aliased expression named ``name``.

        Args:
            name: Name.

        Returns:
            The resulting value.

        """
        return Alias(expression=self, name=Identifier(value=name))

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL column.

        Raises:
            TypeError: Always; a SQL column cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL columns cannot be evaluated as Python booleans"
        raise TypeError(msg)

    def _binary(
        self,
        *,
        operator: BinaryOperator,
        value: ExpressionNode,
    ) -> BinaryExpression:
        """Return binary.

        Args:
            operator: Operator.
            value: Value.

        Returns:
            The resulting value.

        """
        return BinaryExpression(left=self, operator=operator, right=value)


class BinaryOperator(Enum):
    """Supported binary operators.

    Attributes:
        EQ: Eq.
        NE: Ne.
        LT: Lt.
        LE: Le.
        GT: Gt.
        GE: Ge.
        LIKE: Like.
        NOT_LIKE: Not like.
        IS: Is.
        IS_NOT: Is not.

    """

    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IS = "IS"
    IS_NOT = "IS NOT"


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    """A binary SQL expression.

    Attributes:
        left: Left.
        operator: Operator.
        right: Right.

    """

    left: ExpressionNode
    operator: BinaryOperator
    right: ExpressionNode

    def and_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``AND``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(self, other),
        )

    def or_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``OR``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.OR,
            operands=(self, other),
        )

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL expression.

        Raises:
            TypeError: Always; a SQL expression cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL expressions cannot be evaluated as Python booleans"
        raise TypeError(msg)


class BooleanOperator(Enum):
    """Supported boolean operators.

    Attributes:
        AND: And.
        OR: Or.

    """

    AND = "AND"
    OR = "OR"


@dataclass(frozen=True, slots=True)
class BooleanExpression:
    """A normalized boolean expression.

    Attributes:
        operator: Operator.
        operands: Operands.

    """

    operator: BooleanOperator
    operands: tuple[PredicateNode, ...]

    def and_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this expression with ``other`` using ``AND``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(self, other),
        )

    def or_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this expression with ``other`` using ``OR``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.OR,
            operands=(self, other),
        )

    def __post_init__(self) -> None:
        """Flatten nested operands sharing the same operator."""
        flattened: list[PredicateNode] = []
        for operand in self.operands:
            if (
                isinstance(operand, BooleanExpression)
                and operand.operator is self.operator
            ):
                flattened.extend(operand.operands)
            else:
                flattened.append(operand)
        object.__setattr__(self, "operands", tuple(flattened))

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL expression.

        Raises:
            TypeError: Always; a SQL expression cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL expressions cannot be evaluated as Python booleans"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class NullExpression:
    """An IS NULL or IS NOT NULL expression.

    Attributes:
        column: Column.
        negate: Negate.

    """

    column: Column
    negate: bool

    def and_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``AND``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(self, other),
        )

    def or_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``OR``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.OR,
            operands=(self, other),
        )

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL expression.

        Raises:
            TypeError: Always; a SQL expression cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL expressions cannot be evaluated as Python booleans"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class InExpression:
    """An IN/NOT IN value expression.

    Attributes:
        column: Column.
        values: Values.
        negate: Negate.

    """

    column: Column
    values: tuple[ExpressionNode, ...]
    negate: bool

    def and_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``AND``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(self, other),
        )

    def or_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``OR``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.OR,
            operands=(self, other),
        )

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL expression.

        Raises:
            TypeError: Always; a SQL expression cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL expressions cannot be evaluated as Python booleans"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class InSubqueryExpression:
    """An IN/NOT IN subquery expression.

    Attributes:
        column: Column.
        statement: Statement.
        negate: Negate.

    """

    column: Column
    statement: Select
    negate: bool

    def and_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``AND``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(self, other),
        )

    def or_(self, *, other: PredicateNode) -> BooleanExpression:
        """Combine this predicate with ``other`` using ``OR``.

        Args:
            other: Other.

        Returns:
            The resulting value.

        """
        return BooleanExpression(
            operator=BooleanOperator.OR,
            operands=(self, other),
        )

    def __bool__(self) -> bool:
        """Reject Python boolean evaluation of a SQL expression.

        Raises:
            TypeError: Always; a SQL expression cannot be evaluated as a
                Python boolean.

        """
        msg: str = "SQL expressions cannot be evaluated as Python booleans"
        raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class FunctionExpression:
    """A whitelisted SQL function call.

    Attributes:
        name: Name.
        arguments: Arguments.

    """

    name: str
    arguments: tuple[ExpressionNode, ...]


@dataclass(frozen=True, slots=True)
class Ordering:
    """An ORDER BY term.

    Attributes:
        expression: Expression.
        descending: Descending.

    """

    expression: ExpressionNode
    descending: bool = False


@dataclass(frozen=True, slots=True)
class Alias:
    """An aliased expression.

    Attributes:
        expression: Expression.
        name: Name.

    """

    expression: ExpressionNode
    name: Identifier


Param: type[Parameter[SqlScalar]] = Parameter
type ExpressionNode = (
    Column
    | Parameter[SqlScalar]
    | Literal[SqlScalar]
    | BinaryExpression
    | BooleanExpression
    | NullExpression
    | InExpression
    | InSubqueryExpression
    | FunctionExpression
    | Alias
)
type PredicateNode = (
    BinaryExpression
    | BooleanExpression
    | NullExpression
    | InExpression
    | InSubqueryExpression
)
type SelectableNode = ExpressionNode | Alias
type OrderNode = Ordering | ExpressionNode


@dataclass(frozen=True, slots=True)
class ColumnDefinition:
    """Physical SQLite column definition.

    Attributes:
        name: Name.
        affinity: Affinity.
        nullable: Nullable.
        primary_key: Primary key.
        unique: Unique.

    """

    name: str
    affinity: str
    nullable: bool
    primary_key: bool
    unique: bool = False


def _derive_table[U: DataclassInstance](
    *,
    name: str,
    model: type[U],
    table_cls: type[Table],
) -> Table:
    """Derive table metadata from a dataclass model.

    Args:
        name: Name.
        model: Model.
        table_cls: Table cls.

    Returns:
        The resulting value.

    Raises:
        TypeError: When the operation cannot complete.

    """
    hints: dict[str, object] = get_type_hints(obj=model, include_extras=True)
    definitions: list[ColumnDefinition] = []
    dataclass_model: type[DataclassInstance] = cast(
        typ="type[DataclassInstance]",
        val=model,
    )
    for field in fields(class_or_instance=dataclass_model):
        annotation: object = hints[field.name]
        primary_key: bool = False
        unique: bool = False
        if get_origin(tp=annotation) is Annotated:
            arguments: tuple[object, ...] = get_args(tp=annotation)
            annotation = arguments[0]
            primary_key = any(
                isinstance(item, PrimaryKey) for item in arguments[1:]
            )
            unique = any(isinstance(item, Unique) for item in arguments[1:])
        optional: bool = get_origin(
            tp=annotation,
        ) is UnionType and NoneType in get_args(tp=annotation)
        base: object = (
            next(
                item
                for item in get_args(tp=annotation)
                if item is not NoneType
            )
            if optional
            else annotation
        )
        affinities: dict[object, str] = {
            str: "TEXT",
            int: "INTEGER",
            float: "REAL",
            bytes: "BLOB",
            bool: "INTEGER",
        }
        affinity: str | None = affinities.get(base)
        if affinity is None:
            msg: str = f"Unsupported SQLite type: {annotation!r}"
            raise TypeError(msg)
        definitions.append(
            ColumnDefinition(
                name=field.name,
                affinity=affinity,
                nullable=optional,
                primary_key=primary_key,
                unique=unique,
            ),
        )
    return table_cls(name=name, model=model, definitions=tuple(definitions))


@dataclass(frozen=True, slots=True)
class Table:
    """Immutable SQLite table metadata and statement factory.

    Attributes:
        name: Name.
        model: Model.
        definitions: Definitions.

    """

    name: str
    model: type[DataclassInstance] | None = None
    definitions: tuple[ColumnDefinition, ...] = ()

    @classmethod
    def from_dataclass[U: DataclassInstance](
        cls,
        *,
        name: str,
        model: type[U],
    ) -> Table:
        """Create table metadata from a dataclass model.

        Args:
            name: Name.
            model: Model.

        Returns:
            The resulting value.

        """
        return _derive_table(name=name, model=model, table_cls=cls)

    @property
    def columns(self) -> tuple[Column, ...]:
        """Return declared columns in deterministic order.

        Returns:
            The resulting value.

        """
        return tuple(Column(name=item.name) for item in self.definitions)

    def with_model(self, *, model: type[DataclassInstance]) -> Table:
        """Return equivalent metadata associated with its row model.

        Args:
            model: Model.

        Returns:
            The resulting value.

        """
        return Table(name=self.name, model=model, definitions=self.definitions)

    def col(self, *, name: str) -> Column:
        """Return a validated column reference.

        Args:
            name: Name.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if self.definitions and name not in {
            item.name for item in self.definitions
        }:
            msg: str = f"Unknown column: {name}"
            raise ValueError(msg)
        return Column(name=name)

    def create(self) -> CreateTable:
        """Build CREATE TABLE IF NOT EXISTS.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if not self.definitions:
            msg: str = "CREATE requires a dataclass-backed table"
            raise TypeError(msg)
        return CreateTable(table=self)

    def create_index(
        self,
        *,
        name: str,
        columns: tuple[str, ...],
        unique: bool = False,
    ) -> CreateIndex:
        """Build CREATE INDEX IF NOT EXISTS over ``columns``.

        Args:
            name: Name.
            columns: Columns.
            unique: Unique.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not columns:
            msg: str = "CREATE INDEX requires at least one column"
            raise ValueError(msg)
        return CreateIndex(
            name=name,
            table=self.name,
            columns=columns,
            unique=unique,
        )

    def select(
        self,
        *,
        columns: tuple[SelectableNode, ...] | None = None,
    ) -> Select:
        """Build a SELECT statement.

        Args:
            columns: Columns.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        selected: tuple[SelectableNode, ...] = cast(
            typ="tuple[SelectableNode, ...]",
            val=self.columns if columns is None else columns,
        )
        if not selected:
            msg: str = "SELECT requires at least one column"
            raise ValueError(msg)
        return Select(table=self, columns=selected)

    def insert(
        self,
        *,
        replace: bool = False,
        columns: tuple[Column, ...] | None = None,
    ) -> Insert:
        """Build an INSERT statement.

        Args:
            replace: Replace.
            columns: Columns.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        selected: tuple[Column, ...] = (
            self.columns if columns is None else columns
        )
        if not selected:
            msg: str = "INSERT requires at least one column"
            raise ValueError(msg)
        return Insert(table=self, columns=selected, replace=replace)

    def update(
        self,
        *,
        values: tuple[tuple[Column, ExpressionNode], ...],
    ) -> Update:
        """Build an UPDATE statement.

        Args:
            values: Values.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not values:
            msg: str = "UPDATE requires at least one assignment"
            raise ValueError(msg)
        return Update(table=self, values=values)

    def delete(self) -> Delete:
        """Build a DELETE statement.

        Returns:
            The resulting value.

        """
        return Delete(table=self)

    def __post_init__(self) -> None:
        """Derive column definitions from the dataclass model."""
        if self.model is not None and not self.definitions:
            derived: Table = type(self).from_dataclass(
                name=self.name,
                model=self.model,
            )
            object.__setattr__(self, "definitions", derived.definitions)


@dataclass(frozen=True, slots=True)
class CreateTable:
    """CREATE TABLE statement.

    Attributes:
        table: Table.

    """

    table: Table


@dataclass(frozen=True, slots=True)
class CreateIndex:
    """CREATE INDEX statement.

    Attributes:
        name: Name.
        table: Table.
        columns: Columns.
        unique: Unique.

    """

    name: str
    table: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True, slots=True)
class Select:
    """SELECT statement.

    Attributes:
        table: Table.
        columns: Columns.
        predicate: Predicate.
        sorting: Sorting.
        limit_value: Limit value.

    """

    table: Table
    columns: tuple[SelectableNode, ...]
    predicate: PredicateNode | None = None
    sorting: tuple[OrderNode, ...] = ()
    limit_value: ExpressionNode | None = None

    def where(self, *, predicate: PredicateNode) -> Select:
        """Return a copy filtered by ``predicate``.

        Args:
            predicate: Predicate.

        Returns:
            The resulting value.

        """
        return Select(
            table=self.table,
            columns=self.columns,
            predicate=predicate,
            sorting=self.sorting,
            limit_value=self.limit_value,
        )

    def order_by(self, *, values: tuple[OrderNode, ...]) -> Select:
        """Return a copy ordered by ``values``.

        Args:
            values: Values.

        Returns:
            The resulting value.

        """
        return Select(
            table=self.table,
            columns=self.columns,
            predicate=self.predicate,
            sorting=values,
            limit_value=self.limit_value,
        )

    def limit(self, *, value: ExpressionNode) -> Select:
        """Return a copy limited by ``value``.

        Args:
            value: Value.

        Returns:
            The resulting value.

        """
        return Select(
            table=self.table,
            columns=self.columns,
            predicate=self.predicate,
            sorting=self.sorting,
            limit_value=value,
        )


@dataclass(frozen=True, slots=True)
class Insert:
    """INSERT statement.

    Attributes:
        table: Table.
        columns: Columns.
        replace: Replace.
        conflict: Conflict.
        updates: Updates.

    """

    table: Table
    columns: tuple[Column, ...]
    replace: bool = False
    conflict: tuple[Column, ...] = ()
    updates: tuple[Column, ...] = ()

    def on_conflict_update(
        self,
        *,
        conflict: tuple[Column, ...],
        updates: tuple[Column, ...],
    ) -> Insert:
        """Return a copy with ``ON CONFLICT ... DO UPDATE``.

        Args:
            conflict: Conflict.
            updates: Updates.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not conflict or not updates:
            msg: str = "UPSERT requires conflict columns and updates"
            raise ValueError(msg)
        return Insert(
            table=self.table,
            columns=self.columns,
            replace=self.replace,
            conflict=conflict,
            updates=updates,
        )


@dataclass(frozen=True, slots=True)
class Update:
    """UPDATE statement.

    Attributes:
        table: Table.
        values: Values.
        predicate: Predicate.

    """

    table: Table
    values: tuple[tuple[Column, ExpressionNode], ...]
    predicate: PredicateNode | None = None

    def where(self, *, predicate: PredicateNode) -> Update:
        """Return a copy filtered by ``predicate``.

        Args:
            predicate: Predicate.

        Returns:
            The resulting value.

        """
        return Update(
            table=self.table,
            values=self.values,
            predicate=predicate,
        )


@dataclass(frozen=True, slots=True)
class Delete:
    """DELETE statement.

    Attributes:
        table: Table.
        predicate: Predicate.

    """

    table: Table
    predicate: PredicateNode | None = None

    def where(self, *, predicate: PredicateNode) -> Delete:
        """Return a copy filtered by ``predicate``.

        Args:
            predicate: Predicate.

        Returns:
            The resulting value.

        """
        return Delete(table=self.table, predicate=predicate)


class CommandKind(Enum):
    """Fixed SQLite command kinds.

    Attributes:
        BEGIN: Begin.
        BEGIN_IMMEDIATE: Begin immediate.
        COMMIT: Commit.
        ROLLBACK: Rollback.
        VACUUM: Vacuum.

    """

    BEGIN = "begin"
    BEGIN_IMMEDIATE = "begin_immediate"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    VACUUM = "vacuum"


@dataclass(frozen=True, slots=True)
class Command:
    """Fixed SQLite command.

    Attributes:
        kind: Kind.

    """

    kind: CommandKind


@dataclass(frozen=True, slots=True)
class Pragma:
    """Structured PRAGMA operation.

    Attributes:
        name: Name.
        value: Value.
        call: Call.

    """

    name: str
    value: ExpressionNode | None = None
    call: Identifier | Literal[SqlScalar] | None = None

    def __post_init__(self) -> None:
        """Validate the PRAGMA name.

        Raises:
            ValueError: When the PRAGMA name is not alphanumeric.

        """
        if not self.name.replace("_", "").isalnum():
            msg: str = "Invalid PRAGMA name"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AlterRenameTable:
    """ALTER TABLE RENAME TO operation.

    Attributes:
        table: Table.
        new: New.

    """

    table: Identifier
    new: Identifier


@dataclass(frozen=True, slots=True)
class AlterRenameColumn:
    """ALTER TABLE RENAME COLUMN operation.

    Attributes:
        table: Table.
        old: Old.
        new: New.

    """

    table: Identifier
    old: Identifier
    new: Identifier


@dataclass(frozen=True, slots=True)
class Drop:
    """DROP schema object operation.

    Attributes:
        kind: Kind.
        name: Name.

    """

    kind: str
    name: Identifier

    def __post_init__(self) -> None:
        """Restrict DROP to supported schema object kinds.

        Raises:
            ValueError: When the DROP kind is unsupported.

        """
        if self.kind.upper() not in {"INDEX", "TRIGGER", "VIEW"}:
            msg: str = f"Unsupported DROP kind: {self.kind}"
            raise ValueError(msg)


class SavepointKind(Enum):
    """Nested transaction savepoint operation.

    Attributes:
        CREATE: Create.
        ROLLBACK_TO: Rollback to.
        RELEASE: Release.

    """

    CREATE = "create"
    ROLLBACK_TO = "rollback_to"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class Savepoint:
    """Structured savepoint operation.

    Attributes:
        kind: Kind.
        name: Name.

    """

    kind: SavepointKind
    name: Identifier


@dataclass(frozen=True, slots=True)
class RawSql:
    """External ``sqlite_schema`` SQL, never authored by the app.

    Attributes:
        value: Value.

    """

    value: str

    @classmethod
    def from_external_schema(cls, *, value: str) -> RawSql:
        """Wrap nonempty SQL read from an external database schema.

        Args:
            value: Value.

        Returns:
            The resulting value.

        Raises:
            ValueError: When the operation cannot complete.

        """
        if not value.strip():
            msg: str = "External SQL must be nonempty"
            raise ValueError(msg)
        return cls(value=value)


type Compilable = (
    CreateTable
    | CreateIndex
    | Select
    | Insert
    | Update
    | Delete
    | Command
    | Pragma
    | AlterRenameTable
    | AlterRenameColumn
    | Drop
    | Savepoint
    | RawSql
)
type StatementNode = (
    CreateTable
    | CreateIndex
    | Select
    | Insert
    | Update
    | Delete
    | Command
    | Pragma
    | AlterRenameTable
    | AlterRenameColumn
    | Drop
    | Savepoint
    | RawSql
)
type ControlNode = (
    Command
    | Pragma
    | Savepoint
    | RawSql
    | AlterRenameTable
    | AlterRenameColumn
    | Drop
)


@dataclass(frozen=True, slots=True)
class CompiledStatement:
    """Deterministic compiler result.

    Attributes:
        sql: Sql.

    """

    sql: str


class SQLiteCompiler:
    """Single serialization boundary for every SQLite token."""

    @classmethod
    @lru_cache(maxsize=1024)
    def compile(cls, *, statement: StatementNode) -> CompiledStatement:
        """Compile an immutable AST statement, with bounded caching.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        Raises:
            CompileError: When the operation cannot complete.

        """
        sql: str = cls._statement(statement=statement)
        if not sql.strip():
            msg: str = "Compiled SQL must be nonempty"
            raise CompileError(msg)
        return CompiledStatement(sql=sql)

    @classmethod
    def _column(cls, *, column: Column) -> str:
        """Return column.

        Args:
            column: Column.

        Returns:
            The resulting value.

        """
        name: str = cls._identifier(identifier=Identifier(value=column.name))
        if column.table is None:
            return name
        table: str = cls._identifier(identifier=Identifier(value=column.table))
        return f"{table}.{name}"

    @classmethod
    def _expression(cls, *, expression: ExpressionNode) -> str:
        """Return expression.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        if isinstance(expression, Column):
            return cls._column(column=expression)
        if isinstance(expression, Parameter):
            return "?"
        if isinstance(expression, Literal):
            return cls._literal(expression=expression)
        return cls._compound(expression=expression)

    @classmethod
    def _compound(cls, *, expression: ExpressionNode) -> str:
        """Return compound.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        if isinstance(expression, BinaryExpression):
            left: str = cls._expression(expression=expression.left)
            right: str = cls._expression(expression=expression.right)
            return f"{left} {expression.operator.value} {right}"
        if isinstance(expression, BooleanExpression):
            return cls._boolean(expression=expression)
        if isinstance(expression, NullExpression):
            return cls._null(expression=expression)
        return cls._membership(expression=expression)

    @classmethod
    def _boolean(cls, *, expression: BooleanExpression) -> str:
        """Return boolean.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        separator: str = f" {expression.operator.value} "
        joined: str = separator.join(
            cls._expression(expression=item) for item in expression.operands
        )
        return f"({joined})"

    @classmethod
    def _null(cls, *, expression: NullExpression) -> str:
        """Return null.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        column: str = cls._column(column=expression.column)
        negation: str = "NOT " if expression.negate else ""
        return f"{column} IS {negation}NULL"

    @classmethod
    def _membership(cls, *, expression: ExpressionNode) -> str:
        """Return membership.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        if isinstance(expression, InExpression):
            return cls._in(expression=expression)
        if isinstance(expression, InSubqueryExpression):
            return cls._in_subquery(expression=expression)
        if isinstance(expression, FunctionExpression):
            return cls._function(expression=expression)
        return cls._clause(expression=expression)

    @classmethod
    def _in(cls, *, expression: InExpression) -> str:
        """Return in.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        column: str = cls._column(column=expression.column)
        if not expression.values:
            return "1" if expression.negate else "0"
        values: str = ", ".join(
            cls._expression(expression=item) for item in expression.values
        )
        negation: str = "NOT " if expression.negate else ""
        return f"{column} {negation}IN ({values})"

    @classmethod
    def _in_subquery(cls, *, expression: InSubqueryExpression) -> str:
        """Return in subquery.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        column: str = cls._column(column=expression.column)
        subquery: str = cls._statement(statement=expression.statement)
        negation: str = "NOT " if expression.negate else ""
        return f"{column} {negation}IN ({subquery})"

    @classmethod
    def _function(cls, *, expression: FunctionExpression) -> str:
        """Return function.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        Raises:
            UnsupportedFeatureError: When the operation cannot complete.

        """
        if expression.name.upper() not in {"COALESCE", "COUNT"}:
            msg: str = f"Unsupported SQL function: {expression.name}"
            raise UnsupportedFeatureError(msg)
        arguments: str = ", ".join(
            cls._expression(expression=item) for item in expression.arguments
        )
        return f"{expression.name.upper()}({arguments})"

    @classmethod
    def _clause(cls, *, expression: OrderNode) -> str:
        """Return clause.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        Raises:
            CompileError: When the operation cannot complete.

        """
        if isinstance(expression, Ordering):
            suffix: str = " DESC" if expression.descending else " ASC"
            return cls._expression(expression=expression.expression) + suffix
        if isinstance(expression, Alias):
            inner: str = cls._expression(expression=expression.expression)
            name: str = cls._identifier(identifier=expression.name)
            return f"{inner} AS {name}"
        msg: str = f"Unsupported expression node: {type(expression).__name__}"
        raise CompileError(msg)

    @classmethod
    def _statement(cls, *, statement: StatementNode) -> str:
        """Return statement.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        if isinstance(statement, CreateTable):
            return cls._create_table(statement=statement)
        if isinstance(statement, CreateIndex):
            return cls._create_index(statement=statement)
        if isinstance(statement, Select):
            return cls._select(statement=statement)
        if isinstance(statement, Insert):
            return cls._insert(statement=statement)
        if isinstance(statement, Update):
            return cls._update(statement=statement)
        return (
            cls._delete(statement=statement)
            if isinstance(statement, Delete)
            else cls._control(statement=statement)
        )

    @classmethod
    def _create_table(cls, *, statement: CreateTable) -> str:
        """Create table.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        definitions: list[str] = []
        primary: list[str] = []
        for item in statement.table.definitions:
            column: str = cls._identifier(
                identifier=Identifier(value=item.name),
            )
            definitions.append(
                f"{column} {item.affinity}"
                + ("" if item.nullable else " NOT NULL")
                + (" UNIQUE" if item.unique else ""),
            )
            if item.primary_key:
                primary.append(column)
        if primary:
            definitions.append("PRIMARY KEY (" + ", ".join(primary) + ")")
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table.name),
        )
        return (
            "CREATE TABLE IF NOT EXISTS "
            + table
            + " ("
            + ", ".join(definitions)
            + ")"
        )

    @classmethod
    def _create_index(cls, *, statement: CreateIndex) -> str:
        """Create index.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        columns: str = ", ".join(
            cls._identifier(identifier=Identifier(value=name))
            for name in statement.columns
        )
        name: str = cls._identifier(
            identifier=Identifier(value=statement.name),
        )
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table),
        )
        return (
            "CREATE "
            + ("UNIQUE INDEX" if statement.unique else "INDEX")
            + " IF NOT EXISTS "
            + name
            + " ON "
            + table
            + " ("
            + columns
            + ")"
        )

    @classmethod
    def _select(cls, *, statement: Select) -> str:
        """Return select.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        columns: str = ", ".join(
            cls._expression(expression=item) for item in statement.columns
        )
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table.name),
        )
        parts: list[str] = ["SELECT", columns, "FROM", table]
        if statement.predicate is not None:
            parts += ["WHERE", cls._expression(expression=statement.predicate)]
        if statement.sorting:
            parts += [
                "ORDER BY",
                ", ".join(
                    (
                        cls._clause(expression=item)
                        if isinstance(item, Ordering)
                        else cls._expression(expression=item)
                    )
                    for item in statement.sorting
                ),
            ]
        if statement.limit_value is not None:
            parts += [
                "LIMIT",
                cls._expression(expression=statement.limit_value),
            ]
        return " ".join(parts)

    @classmethod
    def _insert(cls, *, statement: Insert) -> str:
        """Return insert.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        verb: str = (
            "INSERT OR REPLACE INTO" if statement.replace else "INSERT INTO"
        )
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table.name),
        )
        columns: str = ", ".join(
            cls._column(column=item) for item in statement.columns
        )
        placeholders: str = ", ".join("?" for _ in statement.columns)
        sql: str = " ".join(
            (verb, table, f"({columns})", "VALUES", f"({placeholders})"),
        )
        if statement.conflict:
            sql += cls._conflict(statement=statement)
        return sql

    @classmethod
    def _conflict(cls, *, statement: Insert) -> str:
        """Return conflict.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        conflict: str = ", ".join(
            cls._column(column=item) for item in statement.conflict
        )
        updates: str = ", ".join(
            cls._excluded(column=item) for item in statement.updates
        )
        return " " + " ".join(
            (f"ON CONFLICT({conflict})", "DO UPDATE SET", updates),
        )

    @classmethod
    def _excluded(cls, *, column: Column) -> str:
        """Return excluded.

        Args:
            column: Column.

        Returns:
            The resulting value.

        """
        quoted: str = cls._column(column=column)
        return f"{quoted}=excluded.{quoted}"

    @classmethod
    def _update(cls, *, statement: Update) -> str:
        """Return update.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table.name),
        )
        assignments: str = ", ".join(
            cls._assignment(column=column, value=value)
            for column, value in statement.values
        )
        parts: list[str] = ["UPDATE", table, "SET", assignments]
        if statement.predicate is not None:
            parts += ["WHERE", cls._expression(expression=statement.predicate)]
        return " ".join(parts)

    @classmethod
    def _assignment(cls, *, column: Column, value: ExpressionNode) -> str:
        """Return assignment.

        Args:
            column: Column.
            value: Value.

        Returns:
            The resulting value.

        """
        return " ".join(
            (
                cls._column(column=column),
                "=",
                cls._expression(expression=value),
            ),
        )

    @classmethod
    def _delete(cls, *, statement: Delete) -> str:
        """Return delete.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        table: str = cls._identifier(
            identifier=Identifier(value=statement.table.name),
        )
        parts: list[str] = ["DELETE", "FROM", table]
        if statement.predicate is not None:
            parts += ["WHERE", cls._expression(expression=statement.predicate)]
        return " ".join(parts)

    @classmethod
    def _control(cls, *, statement: ControlNode) -> str:
        """Return control.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        if isinstance(statement, Savepoint):
            return cls._savepoint(statement=statement)
        if isinstance(statement, RawSql):
            return statement.value
        if isinstance(statement, Command):
            return cls._command(statement=statement)
        if isinstance(statement, Pragma):
            return cls._pragma(statement=statement)
        if isinstance(statement, (AlterRenameTable, AlterRenameColumn)):
            return cls._alter(statement=statement)
        name: str = cls._identifier(identifier=statement.name)
        return f"DROP {statement.kind.upper()} {name}"

    @classmethod
    def _savepoint(cls, *, statement: Savepoint) -> str:
        """Return savepoint.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        name: str = cls._identifier(identifier=statement.name)
        return {
            SavepointKind.CREATE: f"SAVEPOINT {name}",
            SavepointKind.ROLLBACK_TO: f"ROLLBACK TO SAVEPOINT {name}",
            SavepointKind.RELEASE: f"RELEASE SAVEPOINT {name}",
        }[statement.kind]

    @classmethod
    def _pragma(cls, *, statement: Pragma) -> str:
        """Return pragma.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        result: str = "PRAGMA " + statement.name
        if statement.value is not None:
            result += "=" + cls._expression(expression=statement.value)
        if statement.call is not None:
            call: str = (
                cls._identifier(identifier=statement.call)
                if isinstance(statement.call, Identifier)
                else cls._expression(expression=statement.call)
            )
            result += f"({call})"
        return result

    @classmethod
    def _alter(cls, *, statement: AlterRenameTable | AlterRenameColumn) -> str:
        """Return alter.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        table: str = cls._identifier(identifier=statement.table)
        new: str = cls._identifier(identifier=statement.new)
        if isinstance(statement, AlterRenameColumn):
            old: str = cls._identifier(identifier=statement.old)
            return f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}"
        return f"ALTER TABLE {table} RENAME TO {new}"

    @staticmethod
    def _identifier(*, identifier: Identifier) -> str:
        """Return identifier.

        Args:
            identifier: Identifier.

        Returns:
            The resulting value.

        """
        return _quoted_identifier(value=identifier.value)

    @staticmethod
    def _literal(*, expression: Literal[SqlScalar]) -> str:
        """Return literal.

        Args:
            expression: Expression.

        Returns:
            The resulting value.

        """
        value: SqlScalar = expression.value
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, str):
            return _quoted(value=value, quote="'")
        if isinstance(value, bytes):
            return f"X'{value.hex()}'"
        return str(object=value)

    @staticmethod
    def _command(*, statement: Command) -> str:
        """Return command.

        Args:
            statement: Statement.

        Returns:
            The resulting value.

        """
        return {
            CommandKind.BEGIN: "BEGIN",
            CommandKind.BEGIN_IMMEDIATE: "BEGIN IMMEDIATE",
            CommandKind.COMMIT: "COMMIT",
            CommandKind.ROLLBACK: "ROLLBACK",
            CommandKind.VACUUM: "VACUUM",
        }[statement.kind]


@dataclass(frozen=True, slots=True)
class Codec[T, S: SqlScalar]:
    """Explicit Python↔SQLite scalar conversion.

    Attributes:
        encode: Encode.
        decode: Decode.

    """

    encode: Callable[[T], S]
    decode: Callable[[S], T]


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Execution trace metadata without parameter values.

    Attributes:
        statement_type: Statement type.
        parameter_count: Parameter count.
        rowcount: Rowcount.

    """

    statement_type: str
    parameter_count: int
    rowcount: int


@dataclass(frozen=True, slots=True)
class SchemaDifference:
    """One physical-vs-declared schema difference.

    Attributes:
        kind: Kind.
        column: Column.
        expected: Expected.
        actual: Actual.

    """

    kind: str
    column: str | None
    expected: str | None
    actual: str | None


@dataclass(frozen=True, slots=True)
class SchemaReport:
    """Schema verification result.

    Attributes:
        differences: Differences.

    """

    differences: tuple[SchemaDifference, ...]

    @property
    def matches(self) -> bool:
        """Whether the physical schema matches the declaration.

        Returns:
            The resulting value.

        """
        return not self.differences


class Database:
    """The sole application-facing SQLite execution boundary."""

    def __init__(
        self,
        *,
        connection: Connection,
        trace: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        """Bind a raw SQLite connection to the execution boundary.

        Args:
            connection: Connection.
            trace: Trace.

        """
        self._connection: Connection = connection
        self._trace: Callable[[TraceEvent], None] | None = trace
        self._savepoint_counter: int = 0

    def execute(
        self,
        *,
        statement: StatementNode,
        parameters: Parameters = (),
    ) -> Cursor:
        """Compile and execute one structural statement.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            ConstraintError: When the operation cannot complete.
            SQLiteLayerError: When the operation cannot complete.

        """
        compiled: CompiledStatement = SQLiteCompiler.compile(
            statement=statement,
        )
        try:
            cursor: Cursor = self._connection.execute(compiled.sql, parameters)
        except IntegrityError as exc:
            raise ConstraintError(str(object=exc)) from exc
        except Exception as exc:
            raise SQLiteLayerError(str(object=exc)) from exc
        if self._trace is not None:
            self._trace(
                TraceEvent(
                    statement_type=type(statement).__name__,
                    parameter_count=len(parameters),
                    rowcount=cursor.rowcount,
                ),
            )
        return cursor

    def begin(self, *, immediate: bool = False) -> None:
        """Begin an explicit outer transaction.

        Args:
            immediate: Immediate.

        """
        self.execute(
            statement=Command(
                kind=CommandKind.BEGIN_IMMEDIATE
                if immediate
                else CommandKind.BEGIN,
            ),
        )

    def commit(self) -> None:
        """Commit the current transaction."""
        self._connection.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._connection.rollback()

    def execute_many(
        self,
        *,
        statement: Insert,
        parameter_sets: Sequence[Parameters],
    ) -> Cursor:
        """Execute a typed INSERT repeatedly without executemany.

        Args:
            statement: Statement.
            parameter_sets: Parameter sets.

        Returns:
            The resulting value.

        Raises:
            ParameterError: When the operation cannot complete.
            ConstraintError: When the operation cannot complete.
            SQLiteLayerError: When the operation cannot complete.

        """
        expected: int = len(statement.columns)
        for parameters in parameter_sets:
            if len(parameters) != expected:
                msg: str = (
                    f"Expected {expected} parameters, "
                    f"received {len(parameters)}"
                )
                raise ParameterError(msg)
        compiled: CompiledStatement = SQLiteCompiler.compile(
            statement=statement,
        )
        try:
            cursor: Cursor = self._connection.executemany(
                compiled.sql,
                parameter_sets,
            )
        except IntegrityError as exc:
            raise ConstraintError(str(object=exc)) from exc
        except Exception as exc:
            raise SQLiteLayerError(str(object=exc)) from exc
        if self._trace is not None:
            self._trace(
                TraceEvent(
                    statement_type=type(statement).__name__,
                    parameter_count=sum(len(item) for item in parameter_sets),
                    rowcount=cursor.rowcount,
                ),
            )
        return cursor

    def fetch_one(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> tuple[SqlScalar, ...] | None:
        """Compatibility alias returning the first row.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        """
        row: tuple[SqlScalar, ...] | None = self.execute(
            statement=statement,
            parameters=parameters,
        ).fetchone()
        return None if row is None else tuple(row)

    def fetch_all(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> list[tuple[SqlScalar, ...]]:
        """Compatibility alias for fetching all rows.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        """
        return self.fetch_many(statement=statement, parameters=parameters)

    def fetch_optional(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> tuple[SqlScalar, ...] | None:
        """Return zero or one row, rejecting multiple rows.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            ParameterError: When the operation cannot complete.

        """
        rows: list[tuple[SqlScalar, ...]] = self.fetch_many(
            statement=statement.limit(value=Literal(value=2)),
            parameters=parameters,
        )
        if len(rows) > 1:
            msg: str = "Expected at most one row"
            raise ParameterError(msg)
        return rows[0] if rows else None

    def fetch_exactly_one(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> tuple[SqlScalar, ...]:
        """Return exactly one row.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            ParameterError: When the operation cannot complete.

        """
        row: tuple[SqlScalar, ...] | None = self.fetch_optional(
            statement=statement,
            parameters=parameters,
        )
        if row is None:
            msg: str = "Expected exactly one row, received none"
            raise ParameterError(msg)
        return row

    def fetch_many(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> list[tuple[SqlScalar, ...]]:
        """Return all selected rows.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        """
        return [
            tuple(row)
            for row in self.execute(
                statement=statement,
                parameters=parameters,
            ).fetchall()
        ]

    def scalar(
        self,
        *,
        statement: Select,
        parameters: Parameters = (),
    ) -> SqlScalar:
        """Return exactly one row containing exactly one column.

        Args:
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            ParameterError: When the operation cannot complete.

        """
        row: tuple[SqlScalar, ...] = self.fetch_exactly_one(
            statement=statement,
            parameters=parameters,
        )
        if len(row) != 1:
            msg: str = f"Expected one column, received {len(row)}"
            raise ParameterError(msg)
        return row[0]

    def decode_one(
        self,
        *,
        table: Table,
        statement: Select,
        parameters: Parameters = (),
    ) -> DataclassInstance | None:
        """Compatibility alias for decoding zero or one row.

        Args:
            table: Table.
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        """
        return self.decode_optional(
            table=table,
            statement=statement,
            parameters=parameters,
        )

    def decode_optional(
        self,
        *,
        table: Table,
        statement: Select,
        parameters: Parameters = (),
    ) -> DataclassInstance | None:
        """Decode zero or one complete row into its dataclass model.

        Args:
            table: Table.
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if table.model is None:
            msg: str = "Row decoding requires a dataclass-backed table"
            raise TypeError(msg)
        row: tuple[SqlScalar, ...] | None = self.fetch_optional(
            statement=statement,
            parameters=parameters,
        )
        return None if row is None else table.model(*row)

    def decode_many(
        self,
        *,
        table: Table,
        statement: Select,
        parameters: Parameters = (),
    ) -> list[DataclassInstance]:
        """Decode complete rows into dataclass model instances.

        Args:
            table: Table.
            statement: Statement.
            parameters: Parameters.

        Returns:
            The resulting value.

        Raises:
            TypeError: When the operation cannot complete.

        """
        if table.model is None:
            msg: str = "Row decoding requires a dataclass-backed table"
            raise TypeError(msg)
        return [
            table.model(*row)
            for row in self.fetch_many(
                statement=statement,
                parameters=parameters,
            )
        ]

    def verify_schema(self, *, table: Table) -> SchemaReport:
        """Compare a declared table with SQLite table_xinfo metadata.

        Args:
            table: Table.

        Returns:
            The resulting value.

        """
        rows: list[tuple[SqlScalar, ...]] = self.fetch_many(
            statement=Select(
                table=Table(name="pragma_table_xinfo"),
                columns=(
                    Column(name="name"),
                    Column(name="type"),
                    Column(name="notnull"),
                    Column(name="pk"),
                ),
                predicate=Column(name="arg").eq(
                    value=Literal(value=table.name),
                ),
            ),
        )
        # Some SQLite builds do not expose pragma_table_xinfo as a
        # table-valued function.
        if not rows:
            cursor: Cursor = self.execute(
                statement=Pragma(
                    name="table_xinfo",
                    call=Identifier(value=table.name),
                ),
            )
            rows = [
                (row[1], row[2], row[3], row[5]) for row in cursor.fetchall()
            ]
        actual: dict[str, tuple[str, bool, bool]] = {
            cast(typ="str", val=row[0]): (
                cast(typ="str", val=row[1]).upper(),
                not bool(row[2]),
                bool(row[3]),
            )
            for row in rows
        }
        differences: list[SchemaDifference] = []
        for definition in table.definitions:
            observed: tuple[str, bool, bool] | None = actual.pop(
                definition.name,
                None,
            )
            if observed is None:
                differences.append(
                    SchemaDifference(
                        kind="missing_column",
                        column=definition.name,
                        expected=definition.affinity,
                        actual=None,
                    ),
                )
                continue
            affinity, nullable, primary = observed
            if affinity != definition.affinity:
                differences.append(
                    SchemaDifference(
                        kind="wrong_type",
                        column=definition.name,
                        expected=definition.affinity,
                        actual=affinity,
                    ),
                )
            if nullable != definition.nullable and not primary:
                differences.append(
                    SchemaDifference(
                        kind="wrong_nullability",
                        column=definition.name,
                        expected=str(object=definition.nullable),
                        actual=str(object=nullable),
                    ),
                )
            if primary != definition.primary_key:
                differences.append(
                    SchemaDifference(
                        kind="wrong_primary_key",
                        column=definition.name,
                        expected=str(object=definition.primary_key),
                        actual=str(object=primary),
                    ),
                )
        differences.extend(
            SchemaDifference(
                kind="extra_column",
                column=name,
                expected=None,
                actual=affinity,
            )
            for name, (affinity, _, _) in actual.items()
        )
        return SchemaReport(differences=tuple(differences))

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Generator[Database]:
        """Run an outer transaction or nested savepoint.

        Args:
            immediate: Immediate.

        Yields:
            Values produced by the iterator.

        """
        if not self._connection.in_transaction:
            self.execute(
                statement=Command(
                    kind=CommandKind.BEGIN_IMMEDIATE
                    if immediate
                    else CommandKind.BEGIN,
                ),
            )
            try:
                yield self
            except BaseException:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
            return
        self._savepoint_counter += 1
        name: str = f"sqlite_model_{self._savepoint_counter}"
        identifier: Identifier = Identifier(value=name)
        self.execute(
            statement=Savepoint(kind=SavepointKind.CREATE, name=identifier),
        )
        try:
            yield self
        except BaseException:
            self.execute(
                statement=Savepoint(
                    kind=SavepointKind.ROLLBACK_TO,
                    name=identifier,
                ),
            )
            self.execute(
                statement=Savepoint(
                    kind=SavepointKind.RELEASE,
                    name=identifier,
                ),
            )
            raise
        else:
            self.execute(
                statement=Savepoint(
                    kind=SavepointKind.RELEASE,
                    name=identifier,
                ),
            )


def external_cli_sql(*, statement: StatementNode) -> str:
    """Serialize a statement for an external sqlite3 CLI consumer.

    Args:
        statement: Statement.

    Returns:
        The resulting value.

    """
    return SQLiteCompiler.compile(statement=statement).sql


def quote_identifier(*, value: str) -> str:
    """Quote a SQLite identifier through the compiler boundary.

    Args:
        value: Value.

    Returns:
        The resulting value.

    """
    return _quoted_identifier(value=Identifier(value=value).value)


def execute(
    *,
    connection: Connection,
    statement: StatementNode,
    parameters: Parameters = (),
) -> Cursor:
    """Compatibility adapter through the centralized Database boundary.

    Args:
        connection: Connection.
        statement: Statement.
        parameters: Parameters.

    Returns:
        The resulting value.

    """
    return Database(connection=connection).execute(
        statement=statement,
        parameters=parameters,
    )


def function(
    *,
    name: str,
    arguments: tuple[ExpressionNode, ...],
) -> FunctionExpression:
    """Build a whitelisted SQL function expression.

    Args:
        name: Name.
        arguments: Arguments.

    Returns:
        The resulting value.

    Raises:
        UnsupportedFeatureError: When the operation cannot complete.

    """
    normalized: str = name.upper()
    if normalized not in {"COALESCE", "COUNT"}:
        msg: str = f"Unsupported SQL function: {name}"
        raise UnsupportedFeatureError(msg)
    return FunctionExpression(name=normalized, arguments=arguments)


def pragma(
    *,
    name: str,
    value: ExpressionNode | None = None,
    call: Identifier | Literal[SqlScalar] | None = None,
) -> Pragma:
    """Build a structured PRAGMA operation.

    Args:
        name: Name.
        value: Value.
        call: Call.

    Returns:
        The resulting value.

    """
    return Pragma(name=name, value=value, call=call)


def command(*, name: str) -> Command:
    """Build a fixed transaction/maintenance command.

    Args:
        name: Name.

    Returns:
        The resulting value.

    Raises:
        ValueError: When the operation cannot complete.

    """
    try:
        kind: CommandKind = CommandKind(name)
    except ValueError as exc:
        msg: str = f"Unsupported SQLite command: {name}"
        raise ValueError(msg) from exc
    return Command(kind=kind)


def alter_rename_table(*, table: str, new: str) -> AlterRenameTable:
    """Build an ``ALTER TABLE ... RENAME TO`` operation.

    Args:
        table: Table.
        new: New.

    Returns:
        The resulting value.

    """
    return AlterRenameTable(
        table=Identifier(value=table),
        new=Identifier(value=new),
    )


def alter_rename_column(
    *,
    table: str,
    old: str,
    new: str,
) -> AlterRenameColumn:
    """Build an ``ALTER TABLE ... RENAME COLUMN`` operation.

    Args:
        table: Table.
        old: Old.
        new: New.

    Returns:
        The resulting value.

    """
    return AlterRenameColumn(
        table=Identifier(value=table),
        old=Identifier(value=old),
        new=Identifier(value=new),
    )


def drop(*, kind: str, name: str) -> Drop:
    """Build a ``DROP`` operation for a schema object.

    Args:
        kind: Kind.
        name: Name.

    Returns:
        The resulting value.

    """
    return Drop(kind=kind, name=Identifier(value=name))


def upsert(
    *,
    table: Table,
    columns: tuple[Column, ...],
    conflict: tuple[Column, ...],
    updates: tuple[Column, ...],
) -> Insert:
    """Build a typed INSERT ... ON CONFLICT ... DO UPDATE.

    Args:
        table: Table.
        columns: Columns.
        conflict: Conflict.
        updates: Updates.

    Returns:
        The resulting value.

    """
    return Insert(table=table, columns=columns).on_conflict_update(
        conflict=conflict,
        updates=updates,
    )


__all__: list[str] = [
    "Alias",
    "AlterRenameColumn",
    "AlterRenameTable",
    "BinaryExpression",
    "BinaryOperator",
    "BooleanExpression",
    "BooleanOperator",
    "Codec",
    "Column",
    "ColumnDefinition",
    "Command",
    "CommandKind",
    "Compilable",
    "CompileError",
    "CompiledStatement",
    "Connection",
    "ConstraintError",
    "ControlNode",
    "CreateIndex",
    "CreateTable",
    "Cursor",
    "Database",
    "DatabaseError",
    "Delete",
    "Drop",
    "Error",
    "ExpressionNode",
    "FunctionExpression",
    "Identifier",
    "InExpression",
    "InSubqueryExpression",
    "Insert",
    "Literal",
    "NullExpression",
    "OrderNode",
    "Ordering",
    "Param",
    "Parameter",
    "ParameterError",
    "Parameters",
    "Pragma",
    "PredicateNode",
    "PrimaryKey",
    "RawSql",
    "Row",
    "SQLiteCompiler",
    "SQLiteLayerError",
    "Savepoint",
    "SavepointKind",
    "SchemaDifference",
    "SchemaError",
    "SchemaReport",
    "Select",
    "SelectableNode",
    "SqlScalar",
    "StatementNode",
    "Table",
    "TraceEvent",
    "Unique",
    "UnsupportedFeatureError",
    "Update",
    "alter_rename_column",
    "alter_rename_table",
    "command",
    "complete_statement",
    "connect",
    "drop",
    "execute",
    "external_cli_sql",
    "function",
    "pragma",
    "quote_identifier",
    "upsert",
]
