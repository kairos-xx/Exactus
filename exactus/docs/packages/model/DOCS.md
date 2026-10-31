# Structural SQLite layer

This project uses a dependency-free structural SQLite layer instead of handwritten application SQL.

Core public concepts are `Table`, `Column`, `Param`, `Literal`, expression nodes, immutable statement nodes, `Database`, and explicit `Codec` values. `Table.from_dataclass()` or `Table(name=..., model=...)` derives SQLite affinity, nullability, column order, and primary-key membership from dataclass annotations and `Annotated[..., PrimaryKey()]` metadata.

`Database` provides `execute`, `execute_many`, `fetch_optional`, `fetch_exactly_one`, `fetch_many`, `scalar`, `decode_optional`, `decode_many`, and nested `transaction()` operations. `verify_schema()` compares a declared table with SQLite metadata and returns structured `SchemaDifference` values rather than mutating the database.

Application modules do not need SQL strings. The only raw-SQL escape hatch is `RawSql.from_external_schema()`, reserved for SQL read from external SQLite schema metadata.

## Architecture

Production application modules do not author SQL and do not execute SQLite statements directly. They construct immutable schema, expression, and statement objects and pass them through the SQLite execution boundary.

### Boundaries

`Table` derives physical columns from frozen dataclasses. Expressions and statements are immutable AST nodes. `SQLiteCompiler` is the sole serializer for identifiers, literals, expressions, DDL, DML, PRAGMAs, transactions, savepoints, and maintenance commands. `Database` is the sole execution boundary and owns parameter binding, cardinality helpers, row decoding, batch execution, tracing, error translation, and nested transaction/savepoint behavior.

`RawSql.from_external_schema()` is the reviewed escape hatch for SQL obtained from an arbitrary database's `sqlite_schema`. Production uses it at exactly one allowlisted site in `exactus/packages/rename_project/rename_project.py` to recreate externally sourced schema objects after structural renaming. It is not used for application-authored SQL.

`external_cli_sql()` is the explicit serialization boundary used only when `exactus/__main__.py` must generate a shell script consumed later by the external `sqlite3` executable.

### Enforced invariants

The architecture tests reject direct `Connection.execute`, `executemany`, or `executescript` calls in application modules; application compiler calls; SQL-statement literals; and unreviewed external-schema escape-hatch sites.

The compiler is deterministic and cached for immutable statements. SQL expressions reject accidental Python boolean evaluation. Empty `IN` is normalized to deterministic false semantics. Nested transactions use compiler-generated savepoints. Constraint errors preserve the original SQLite exception as their cause.

### Verification

The focused suite exercises schema round trips and drift detection, composite primary keys, optional/null columns, UPSERT, CRUD, dynamic identifiers, quoting, Unicode, cardinality APIs, scalar reads, dataclass decoding, batch inserts, nested savepoint rollback, trace privacy, constraint translation, codecs, empty `IN`, deterministic compilation, and seeded randomized identifier/value round trips against real SQLite.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Structural SQLite statement, schema, and execution model. |
| `examples/` | `run.py` demonstrates the structural SQLite model end to end without touching the filesystem: a dataclass derives the `notes` table, every statement compiles to inspectable SQL first, and the `Database` |
| `pipeline_queries.py` | Typed pipeline schema and statements without handwritten SQL. |
| `registry_queries.py` | Typed registry schema and statements without handwritten SQL. |
| `sqlite_model/` | Typed, dependency-free SQLite AST, compiler, and execution layer. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `pipeline_queries.py`

Typed pipeline schema and statements without handwritten SQL.

- `class OwnerRow` — One named pipeline owner record.
  - Fields: `pipeline: Annotated[str, PrimaryKey()]`, `run_id: Annotated[str, Unique()]`, `pid: int`, `fingerprint: str`, `state: str`, `generation: int`, `started_at: str`, `updated_at: str`
- `class RequestRow` — One pipeline observer request record.
  - Fields: `request_id: Annotated[str, PrimaryKey()]`, `pipeline: str`, `pipeline_run_id: str`, `fingerprint: str`, `pid: int`, `tty: str | None`, `state: str`, `generation: int | None`, `requested_at: str`, `updated_at: str`, `detail: str`, `error: str | None`
- `class Queries` — Precompiled table handles and statements for the coordinator.

### `registry_queries.py`

Typed registry schema and statements without handwritten SQL.

- `class RunRow` — One live or finished exactus run record.
  - Fields: `run_id: Annotated[str, PrimaryKey()]`, `kind: str`, `identifier: str`, `pipeline_run_id: str | None`, `pid: int`, `output: str`, `targets: str`, `status: str`, `progress: float`, `step: str`, `detail: str`, `created_at: str`, `updated_at: str`, `elapsed_seconds: float`
- `class WorkRow` — Per-tool progress item owned by one run.
  - Fields: `run_id: Annotated[str, PrimaryKey()]`, `tool: str`, `item: Annotated[str, PrimaryKey()]`, `state: str`, `error: str`, `updated_at: str`
- `class LeaseRow` — One cross-process reader/writer resource lease.
  - Fields: `lease_id: Annotated[str, PrimaryKey()]`, `run_id: str`, `tool: str`, `resource: str`, `mode: str`, `state: str`, `updated_at: str`
- `class Queries` — Precompiled table handles and statements for the registry.
- `live_processes_for_run(*, run_id: str) -> Select` — Build the process-id query used by the generated kill script.

### `sqlite_model/__init__.py`

Typed, dependency-free SQLite AST, compiler, and execution layer.

- `class SQLiteLayerError(RuntimeError)` — Base error raised by the SQLite abstraction.
- `class CompileError(SQLiteLayerError)` — Raised when an AST cannot be compiled.
- `class ParameterError(SQLiteLayerError)` — Raised for invalid statement parameters or cardinality.
- `class ConstraintError(SQLiteLayerError)` — Raised when SQLite rejects a constraint.
- `class SchemaError(SQLiteLayerError)` — Raised for schema verification failures.
- `class UnsupportedFeatureError(CompileError)` — Raised when an AST requests unsupported SQLite syntax.
- `class PrimaryKey` — Mark a dataclass field as part of a primary key.
- `class Unique` — Mark a dataclass field as a ``UNIQUE`` column.
- `class Identifier` — A validated SQLite identifier.
  - Fields: `value: str`
- `class Parameter` — A positional SQLite parameter placeholder.
- `class Literal` — A structural literal emitted by the compiler.
  - Fields: `value: S`
- `class Column` — A typed column reference.
  - Fields: `name: str`, `table: str | None`
  - `eq(*, value: ExpressionNode) -> BinaryExpression` — Build an equality predicate against ``value``.
  - `ne(*, value: ExpressionNode) -> BinaryExpression` — Build an inequality predicate against ``value``.
  - `lt(*, value: ExpressionNode) -> BinaryExpression` — Build a less-than predicate against ``value``.
  - `le(*, value: ExpressionNode) -> BinaryExpression` — Build a less-than-or-equal predicate against ``value``.
  - `gt(*, value: ExpressionNode) -> BinaryExpression` — Build a greater-than predicate against ``value``.
  - `ge(*, value: ExpressionNode) -> BinaryExpression` — Build a greater-than-or-equal predicate against ``value``.
  - `is_(*, value: ExpressionNode) -> BinaryExpression` — Build an ``IS`` predicate against ``value``.
  - `is_not(*, value: ExpressionNode) -> BinaryExpression` — Build an ``IS NOT`` predicate against ``value``.
  - `is_null() -> NullExpression` — Build an ``IS NULL`` predicate.
  - `is_not_null() -> NullExpression` — Build an ``IS NOT NULL`` predicate.
  - `like(*, value: ExpressionNode, negate: bool=False) -> BinaryExpression` — Build a ``LIKE`` (or ``NOT LIKE``) predicate.
  - `in_(*, values: tuple[ExpressionNode, ...]) -> InExpression` — Build an ``IN`` predicate over ``values``.
  - `not_in_values(*, values: tuple[ExpressionNode, ...]) -> InExpression` — Build a ``NOT IN`` predicate over ``values``.
  - `in_subquery(*, statement: Select) -> InSubqueryExpression` — Build an ``IN`` predicate over a subquery.
  - `not_in(*, statement: Select) -> InSubqueryExpression` — Build a ``NOT IN`` predicate over a subquery.
  - `desc() -> Ordering` — Build a descending ``ORDER BY`` term.
  - `alias(*, name: str) -> Alias` — Build an aliased expression named ``name``.
- `class BinaryOperator(Enum)` — Supported binary operators.
- `class BinaryExpression` — A binary SQL expression.
  - Fields: `left: ExpressionNode`, `operator: BinaryOperator`, `right: ExpressionNode`
  - `and_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class BooleanOperator(Enum)` — Supported boolean operators.
- `class BooleanExpression` — A normalized boolean expression.
  - Fields: `operator: BooleanOperator`, `operands: tuple[PredicateNode, ...]`
  - `and_(*, other: PredicateNode) -> BooleanExpression` — Combine this expression with ``other`` using ``AND``.
  - `or_(*, other: PredicateNode) -> BooleanExpression` — Combine this expression with ``other`` using ``OR``.
- `class NullExpression` — An IS NULL or IS NOT NULL expression.
  - Fields: `column: Column`, `negate: bool`
  - `and_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class InExpression` — An IN/NOT IN value expression.
  - Fields: `column: Column`, `values: tuple[ExpressionNode, ...]`, `negate: bool`
  - `and_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class InSubqueryExpression` — An IN/NOT IN subquery expression.
  - Fields: `column: Column`, `statement: Select`, `negate: bool`
  - `and_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(*, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class FunctionExpression` — A whitelisted SQL function call.
  - Fields: `name: str`, `arguments: tuple[ExpressionNode, ...]`
- `class Ordering` — An ORDER BY term.
  - Fields: `expression: ExpressionNode`, `descending: bool`
- `class Alias` — An aliased expression.
  - Fields: `expression: ExpressionNode`, `name: Identifier`
- `class ColumnDefinition` — Physical SQLite column definition.
  - Fields: `name: str`, `affinity: str`, `nullable: bool`, `primary_key: bool`, `unique: bool`
- `class Table` — Immutable SQLite table metadata and statement factory.
  - Fields: `name: str`, `model: type[DataclassInstance] | None`, `definitions: tuple[ColumnDefinition, ...]`
  - `from_dataclass(*, name: str, model: type[U]) -> Table` — Create table metadata from a dataclass model.
  - `columns() -> tuple[Column, ...]` — Return declared columns in deterministic order.
  - `with_model(*, model: type[DataclassInstance]) -> Table` — Return equivalent metadata associated with its row model.
  - `col(*, name: str) -> Column` — Return a validated column reference.
  - `create() -> CreateTable` — Build CREATE TABLE IF NOT EXISTS.
  - `create_index(*, name: str, columns: tuple[str, ...], unique: bool=False) -> CreateIndex` — Build CREATE INDEX IF NOT EXISTS over ``columns``.
  - `select(*, columns: tuple[SelectableNode, ...] | None=None) -> Select` — Build a SELECT statement.
  - `insert(*, replace: bool=False, columns: tuple[Column, ...] | None=None) -> Insert` — Build an INSERT statement.
  - `update(*, values: tuple[tuple[Column, ExpressionNode], ...]) -> Update` — Build an UPDATE statement.
  - `delete() -> Delete` — Build a DELETE statement.
- `class CreateTable` — CREATE TABLE statement.
  - Fields: `table: Table`
- `class CreateIndex` — CREATE INDEX statement.
  - Fields: `name: str`, `table: str`, `columns: tuple[str, ...]`, `unique: bool`
- `class Select` — SELECT statement.
  - Fields: `table: Table`, `columns: tuple[SelectableNode, ...]`, `predicate: PredicateNode | None`, `sorting: tuple[OrderNode, ...]`, `limit_value: ExpressionNode | None`
  - `where(*, predicate: PredicateNode) -> Select` — Return a copy filtered by ``predicate``.
  - `order_by(*, values: tuple[OrderNode, ...]) -> Select` — Return a copy ordered by ``values``.
  - `limit(*, value: ExpressionNode) -> Select` — Return a copy limited by ``value``.
- `class Insert` — INSERT statement.
  - Fields: `table: Table`, `columns: tuple[Column, ...]`, `replace: bool`, `conflict: tuple[Column, ...]`, `updates: tuple[Column, ...]`
  - `on_conflict_update(*, conflict: tuple[Column, ...], updates: tuple[Column, ...]) -> Insert` — Return a copy with ``ON CONFLICT ...
- `class Update` — UPDATE statement.
  - Fields: `table: Table`, `values: tuple[tuple[Column, ExpressionNode], ...]`, `predicate: PredicateNode | None`
  - `where(*, predicate: PredicateNode) -> Update` — Return a copy filtered by ``predicate``.
- `class Delete` — DELETE statement.
  - Fields: `table: Table`, `predicate: PredicateNode | None`
  - `where(*, predicate: PredicateNode) -> Delete` — Return a copy filtered by ``predicate``.
- `class CommandKind(Enum)` — Fixed SQLite command kinds.
- `class Command` — Fixed SQLite command.
  - Fields: `kind: CommandKind`
- `class Pragma` — Structured PRAGMA operation.
  - Fields: `name: str`, `value: ExpressionNode | None`, `call: Identifier | Literal[SqlScalar] | None`
- `class AlterRenameTable` — ALTER TABLE RENAME TO operation.
  - Fields: `table: Identifier`, `new: Identifier`
- `class AlterRenameColumn` — ALTER TABLE RENAME COLUMN operation.
  - Fields: `table: Identifier`, `old: Identifier`, `new: Identifier`
- `class Drop` — DROP schema object operation.
  - Fields: `kind: str`, `name: Identifier`
- `class SavepointKind(Enum)` — Nested transaction savepoint operation.
- `class Savepoint` — Structured savepoint operation.
  - Fields: `kind: SavepointKind`, `name: Identifier`
- `class RawSql` — External ``sqlite_schema`` SQL, never authored by the app.
  - Fields: `value: str`
  - `from_external_schema(*, value: str) -> RawSql` — Wrap nonempty SQL read from an external database schema.
- `class CompiledStatement` — Deterministic compiler result.
  - Fields: `sql: str`
- `class SQLiteCompiler` — Single serialization boundary for every SQLite token.
  - `compile(*, statement: StatementNode) -> CompiledStatement` — Compile an immutable AST statement, with bounded caching.
- `class Codec` — Explicit Python↔SQLite scalar conversion.
  - Fields: `encode: Callable[[T], S]`, `decode: Callable[[S], T]`
- `class TraceEvent` — Execution trace metadata without parameter values.
  - Fields: `statement_type: str`, `parameter_count: int`, `rowcount: int`
- `class SchemaDifference` — One physical-vs-declared schema difference.
  - Fields: `kind: str`, `column: str | None`, `expected: str | None`, `actual: str | None`
- `class SchemaReport` — Schema verification result.
  - Fields: `differences: tuple[SchemaDifference, ...]`
  - `matches() -> bool` — Whether the physical schema matches the declaration.
- `class Database` — The sole application-facing SQLite execution boundary.
  - `execute(*, statement: StatementNode, parameters: Parameters=()) -> Cursor` — Compile and execute one structural statement.
  - `begin(*, immediate: bool=False) -> None` — Begin an explicit outer transaction.
  - `commit() -> None` — Commit the current transaction.
  - `rollback() -> None` — Roll back the current transaction.
  - `execute_many(*, statement: Insert, parameter_sets: Sequence[Parameters]) -> Cursor` — Execute a typed INSERT repeatedly without executemany.
  - `fetch_one(*, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...] | None` — Compatibility alias returning the first row.
  - `fetch_all(*, statement: Select, parameters: Parameters=()) -> list[tuple[SqlScalar, ...]]` — Compatibility alias for fetching all rows.
  - `fetch_optional(*, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...] | None` — Return zero or one row, rejecting multiple rows.
  - `fetch_exactly_one(*, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...]` — Return exactly one row.
  - `fetch_many(*, statement: Select, parameters: Parameters=()) -> list[tuple[SqlScalar, ...]]` — Return all selected rows.
  - `scalar(*, statement: Select, parameters: Parameters=()) -> SqlScalar` — Return exactly one row containing exactly one column.
  - `decode_one(*, table: Table, statement: Select, parameters: Parameters=()) -> DataclassInstance | None` — Compatibility alias for decoding zero or one row.
  - `decode_optional(*, table: Table, statement: Select, parameters: Parameters=()) -> DataclassInstance | None` — Decode zero or one complete row into its dataclass model.
  - `decode_many(*, table: Table, statement: Select, parameters: Parameters=()) -> list[DataclassInstance]` — Decode complete rows into dataclass model instances.
  - `verify_schema(*, table: Table) -> SchemaReport` — Compare a declared table with SQLite table_xinfo metadata.
  - `transaction(*, immediate: bool=False) -> Generator[Database]` — Run an outer transaction or nested savepoint.
- `external_cli_sql(*, statement: StatementNode) -> str` — Serialize a statement for an external sqlite3 CLI consumer.
- `quote_identifier(*, value: str) -> str` — Quote a SQLite identifier through the compiler boundary.
- `execute(*, connection: Connection, statement: StatementNode, parameters: Parameters=()) -> Cursor` — Compatibility adapter through the centralized Database boundary.
- `function(*, name: str, arguments: tuple[ExpressionNode, ...]) -> FunctionExpression` — Build a whitelisted SQL function expression.
- `pragma(*, name: str, value: ExpressionNode | None=None, call: Identifier | Literal[SqlScalar] | None=None) -> Pragma` — Build a structured PRAGMA operation.
- `command(*, name: str) -> Command` — Build a fixed transaction/maintenance command.
- `alter_rename_table(*, table: str, new: str) -> AlterRenameTable` — Build an ``ALTER TABLE ...
- `alter_rename_column(*, table: str, old: str, new: str) -> AlterRenameColumn` — Build an ``ALTER TABLE ...
- `drop(*, kind: str, name: str) -> Drop` — Build a ``DROP`` operation for a schema object.
- `upsert(*, table: Table, columns: tuple[Column, ...], conflict: tuple[Column, ...], updates: tuple[Column, ...]) -> Insert` — Build a typed INSERT ...

## Examples

`run.py` demonstrates the structural SQLite model end to end without
touching the filesystem: a dataclass derives the `notes` table, every
statement compiles to inspectable SQL first, and the `Database`
execution boundary runs the same statements against an in-memory
SQLite connection and prints the fetched row.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- Third-party: `_typeshed`
- Used by: `__main__.py`, `packages/rename_project/rename_project.py`, `tests/common/package/test_package_independence.py`, `tests/packages/rename_project/test_next_safety_batch.py`, `tests/packages/rename_project/test_roundtrip.py`, `tests/packages/rename_project/test_sqlite_semantics.py`, `tests/tools/common/test_common_package.py`, `tests/tools/common/test_registry.py`, `tools/common/pipeline_supervisor.py`, `tools/common/registry.py`

## Tests

Tests live in `exactus/tests/packages/model/`.

- `test_examples.py` — Coverage for the ``exactus/packages/model/examples`` demonstration. (3 tests)
  - `test_example_main_runs_the_in_memory_demo`
  - `test_example_run_py_executes_as_script`
  - `test_examples_main_module_runs_the_demo`
- `test_sqlite_architecture.py` — Architectural regression checks for application SQLite access. (4 tests)
  - `test_application_does_not_bypass_database_layer`
  - `test_application_has_no_authored_sql_literals`
  - `test_raw_sql_escape_hatch_is_allowlisted`
  - `test_application_never_compiles_sql_itself`
- `test_sqlite_hardening.py` — Hardening and torture tests for the structural SQLite layer. (11 tests)
  - `test_schema_round_trip_and_drift_detection`
  - `test_cardinality_scalar_and_batch_operations`
  - `test_nested_transactions_use_savepoints`
  - `test_trace_never_contains_parameter_values`
  - `test_constraint_translation_preserves_cause`
  - `test_codec_is_explicit_and_bidirectional`
  - `test_expression_boolean_evaluation_is_rejected`
  - `test_empty_in_has_deterministic_sqlite_semantics`
  - `test_randomized_identifier_and_value_round_trip`
  - `test_structural_ddl_commands_and_error_paths`
  - `test_decode_many_exactly_one_and_schema_drift`
- `test_sqlite_model.py` — Behavioral tests for the typed SQLite compiler. (11 tests)
  - `test_registry_statements_execute_end_to_end`
  - `test_upsert_preserves_key_and_updates_mutable_values`
  - `test_dynamic_identifier_operations_are_safe`
  - `test_drop_rejects_non_schema_object_kinds`
  - `test_identifier_quoting_rejects_invalid_and_escapes_quotes`
  - `test_dataclass_schema_maps_optional_and_composite_primary_key`
  - `test_generated_kill_query_is_executable_sql`
  - `test_identifier_torture_and_compiler_determinism`
  - `test_database_decode_and_transaction`
  - `test_external_sql_escape_hatch_rejects_empty`
  - `test_null_predicates_and_transaction_rollback`

<!-- exactus:reference:end -->
