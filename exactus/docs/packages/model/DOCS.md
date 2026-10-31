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
| `examples/` | Runnable demonstration for `exactus/packages/model/`. |
| `pipeline_queries.py` | Typed pipeline schema and statements without handwritten SQL. |
| `registry_queries.py` | Typed registry schema and statements without handwritten SQL. |
| `sqlite_model/` | Subdirectory. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Structural SQLite statement, schema, and execution model.


### `examples/__init__.py`

Runnable demonstration for the ``model`` package.


### `examples/__main__.py`

Run the model example with the project virtual environment.


### `examples/run.py`

Demonstrate the structural SQLite model against an in-memory database.

- `class NoteRow` — One example note record.
  - Fields: `note_id: Annotated[str, PrimaryKey()]`, `title: str`, `done: int`
- `class Constants` — Group module-level constants.
  - `notes` = `Table.from_dataclass(model=NoteRow, name='notes')`
  - `open_title` = `'ship model migration'`
- `main() -> int` — Compile and run a small typed schema, insert, and select.

### `pipeline_queries.py`

Typed pipeline schema and statements without handwritten SQL.

- `class OwnerRow` — One named pipeline owner record.
  - Fields: `pipeline: Annotated[str, PrimaryKey()]`, `run_id: Annotated[str, Unique()]`, `pid: int`, `fingerprint: str`, `state: str`, `generation: int`, `started_at: str`, `updated_at: str`
- `class RequestRow` — One pipeline observer request record.
  - Fields: `request_id: Annotated[str, PrimaryKey()]`, `pipeline: str`, `pipeline_run_id: str`, `fingerprint: str`, `pid: int`, `tty: str | None`, `state: str`, `generation: int | None`, `requested_at: str`, `updated_at: str`, `detail: str`, `error: str | None`
- `class Queries` — Precompiled table handles and statements for the coordinator.
  - `owners` = `Table.from_dataclass(model=OwnerRow, name='pipeline_owners')`
  - `requests` = `Table.from_dataclass(model=RequestRow, name='pipeline_requests')`
  - `owners_schema` = `owners.create()`
  - `requests_schema` = `requests.create()`
  - `requests_index` = `requests.create_index(name='pipeline_requests_owner_state', columns=('pip...`
  - `busy_timeout` = `pragma(name='busy_timeout', value=Literal(value=30000))`
  - `begin_immediate` = `command(name='begin_immediate')`
  - `commit` = `command(name='commit')`
  - `rollback` = `command(name='rollback')`
  - `select_owner` = `owners.select().where(predicate=owners.col(name='pipeline').eq(value=Para...`
  - `upsert_owner` = `upsert(table=owners, columns=owners.columns, conflict=(owners.col(name='p...`
  - `insert_request` = `requests.insert()`
  - `select_request` = `requests.select().where(predicate=requests.col(name='request_id').eq(valu...`
  - `select_requests` = `requests.select().where(predicate=requests.col(name='pipeline_run_id').eq...`
  - `settle_request` = `requests.update(values=((requests.col(name='state'), Param()), (requests....`
  - `settle_observer` = `requests.update(values=((requests.col(name='state'), Param()), (requests....`
  - `bump_owner_generation` = `owners.update(values=((owners.col(name='generation'), Param()), (owners.c...`
  - `select_pending` = `requests.select(columns=(requests.col(name='request_id'),)).where(predica...`
  - `seal_owner` = `owners.update(values=((owners.col(name='state'), Param()), (owners.col(na...`
  - `finish_owner` = `owners.update(values=((owners.col(name='state'), Param()), (owners.col(na...`
  - `select_terminal` = `requests.select(columns=(requests.col(name='request_id'), requests.col(na...`
  - `delete_terminal` = `requests.delete().where(predicate=requests.col(name='updated_at').lt(valu...`

### `registry_queries.py`

Typed registry schema and statements without handwritten SQL.

- `class RunRow` — One live or finished exactus run record.
  - Fields: `run_id: Annotated[str, PrimaryKey()]`, `kind: str`, `identifier: str`, `pipeline_run_id: str | None`, `pid: int`, `output: str`, `targets: str`, `status: str`, `progress: float`, `step: str`, `detail: str`, `created_at: str`, `updated_at: str`, `elapsed_seconds: float`
- `class WorkRow` — Per-tool progress item owned by one run.
  - Fields: `run_id: Annotated[str, PrimaryKey()]`, `tool: str`, `item: Annotated[str, PrimaryKey()]`, `state: str`, `error: str`, `updated_at: str`
- `class LeaseRow` — One cross-process reader/writer resource lease.
  - Fields: `lease_id: Annotated[str, PrimaryKey()]`, `run_id: str`, `tool: str`, `resource: str`, `mode: str`, `state: str`, `updated_at: str`
- `class Queries` — Precompiled table handles and statements for the registry.
  - `runs` = `Table.from_dataclass(model=RunRow, name='runs')`
  - `work` = `Table.from_dataclass(model=WorkRow, name='work_activities')`
  - `schema` = `runs.create()`
  - `work_schema` = `work.create()`
  - `upsert_work` = `upsert(table=work, columns=work.columns, conflict=(work.col(name='run_id'...`
  - `select_work` = `work.select(columns=(work.col(name='state'),)).where(predicate=work.col(n...`
  - `delete_work` = `work.delete().where(predicate=work.col(name='run_id').eq(value=Param()))`
  - `prune_work` = `work.delete().where(predicate=work.col(name='run_id').not_in(statement=ru...`
  - `leases` = `Table.from_dataclass(model=LeaseRow, name='resource_leases')`
  - `resource_schema` = `leases.create()`
  - `prune_resources` = `leases.delete().where(predicate=leases.col(name='run_id').not_in(statemen...`
  - `insert_resource` = `leases.insert(replace=True)`
  - `select_resource_conflicts` = `leases.select(columns=(leases.col(name='lease_id'),)).where(predicate=lea...`
  - `activate_resource` = `leases.update(values=((leases.col(name='state'), Literal(value='active'))...`
  - `delete_resource` = `leases.delete().where(predicate=leases.col(name='lease_id').eq(value=Para...`
  - `delete_run_resources` = `leases.delete().where(predicate=leases.col(name='run_id').eq(value=Param()))`
  - `select_live` = `runs.select().where(predicate=runs.col(name='status').eq(value=Param()))`
  - `count_runs` = `runs.select(columns=(function(name='COUNT', arguments=(runs.col(name='run...`
  - `count_finished` = `runs.select(columns=(function(name='COUNT', arguments=(runs.col(name='run...`
  - `insert_run` = `runs.insert(replace=True)`
  - `reap_run` = `runs.update(values=((runs.col(name='status'), Param()), (runs.col(name='u...`
  - `prune_runs` = `runs.delete().where(predicate=runs.col(name='status').ne(value=Param()).a...`
  - `trim_runs` = `runs.delete().where(predicate=runs.col(name='status').ne(value=Param()).a...`
  - `beat_run` = `runs.update(values=((runs.col(name='updated_at'), Param()), (runs.col(nam...`
  - `commit` = `command(name='commit')`
  - `rollback` = `command(name='rollback')`
  - `begin_immediate` = `command(name='begin_immediate')`
  - `vacuum` = `command(name='vacuum')`
  - `journal_mode` = `pragma(name='journal_mode', value=Literal(value='WAL'))`
  - `checkpoint` = `pragma(name='wal_checkpoint', call=Literal(value='TRUNCATE'))`
- `live_processes_for_run(*, run_id: str) -> Select` — Build the process-id query used by the generated kill script.

### `sqlite_model/__init__.py`

Typed, dependency-free SQLite AST, compiler, and execution layer.

- `class SQLiteLayerError` — Base error raised by the SQLite abstraction.
- `class CompileError` — Raised when an AST cannot be compiled.
- `class ParameterError` — Raised for invalid statement parameters or cardinality.
- `class ConstraintError` — Raised when SQLite rejects a constraint.
- `class SchemaError` — Raised for schema verification failures.
- `class UnsupportedFeatureError` — Raised when an AST requests unsupported SQLite syntax.
- `class PrimaryKey` — Mark a dataclass field as part of a primary key.
- `class Unique` — Mark a dataclass field as a ``UNIQUE`` column.
- `class Identifier` — A validated SQLite identifier.
  - Fields: `value: str`
- `class Parameter` — A positional SQLite parameter placeholder.
- `class Literal` — A structural literal emitted by the compiler.
  - Fields: `value: S`
- `class Column` — A typed column reference.
  - `table` = `None`
  - Fields: `name: str`
  - `eq(self, *, value: ExpressionNode) -> BinaryExpression` — Build an equality predicate against ``value``.
  - `ne(self, *, value: ExpressionNode) -> BinaryExpression` — Build an inequality predicate against ``value``.
  - `lt(self, *, value: ExpressionNode) -> BinaryExpression` — Build a less-than predicate against ``value``.
  - `le(self, *, value: ExpressionNode) -> BinaryExpression` — Build a less-than-or-equal predicate against ``value``.
  - `gt(self, *, value: ExpressionNode) -> BinaryExpression` — Build a greater-than predicate against ``value``.
  - `ge(self, *, value: ExpressionNode) -> BinaryExpression` — Build a greater-than-or-equal predicate against ``value``.
  - `is_(self, *, value: ExpressionNode) -> BinaryExpression` — Build an ``IS`` predicate against ``value``.
  - `is_not(self, *, value: ExpressionNode) -> BinaryExpression` — Build an ``IS NOT`` predicate against ``value``.
  - `is_null(self) -> NullExpression` — Build an ``IS NULL`` predicate.
  - `is_not_null(self) -> NullExpression` — Build an ``IS NOT NULL`` predicate.
  - `like(self, *, value: ExpressionNode, negate: bool=False) -> BinaryExpression` — Build a ``LIKE`` (or ``NOT LIKE``) predicate.
  - `in_(self, *, values: tuple[ExpressionNode, ...]) -> InExpression` — Build an ``IN`` predicate over ``values``.
  - `not_in_values(self, *, values: tuple[ExpressionNode, ...]) -> InExpression` — Build a ``NOT IN`` predicate over ``values``.
  - `in_subquery(self, *, statement: Select) -> InSubqueryExpression` — Build an ``IN`` predicate over a subquery.
  - `not_in(self, *, statement: Select) -> InSubqueryExpression` — Build a ``NOT IN`` predicate over a subquery.
  - `desc(self) -> Ordering` — Build a descending ``ORDER BY`` term.
  - `alias(self, *, name: str) -> Alias` — Build an aliased expression named ``name``.
- `class BinaryOperator` — Supported binary operators.
  - `EQ` = `'='`
  - `NE` = `'!='`
  - `LT` = `'<'`
  - `LE` = `'<='`
  - `GT` = `'>'`
  - `GE` = `'>='`
  - `LIKE` = `'LIKE'`
  - `NOT_LIKE` = `'NOT LIKE'`
  - `IS` = `'IS'`
  - `IS_NOT` = `'IS NOT'`
- `class BinaryExpression` — A binary SQL expression.
  - Fields: `left: ExpressionNode`, `operator: BinaryOperator`, `right: ExpressionNode`
  - `and_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class BooleanOperator` — Supported boolean operators.
  - `AND` = `'AND'`
  - `OR` = `'OR'`
- `class BooleanExpression` — A normalized boolean expression.
  - Fields: `operator: BooleanOperator`, `operands: tuple[PredicateNode, ...]`
  - `and_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this expression with ``other`` using ``AND``.
  - `or_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this expression with ``other`` using ``OR``.
- `class NullExpression` — An IS NULL or IS NOT NULL expression.
  - Fields: `column: Column`, `negate: bool`
  - `and_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class InExpression` — An IN/NOT IN value expression.
  - Fields: `column: Column`, `values: tuple[ExpressionNode, ...]`, `negate: bool`
  - `and_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class InSubqueryExpression` — An IN/NOT IN subquery expression.
  - Fields: `column: Column`, `statement: Select`, `negate: bool`
  - `and_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``AND``.
  - `or_(self, *, other: PredicateNode) -> BooleanExpression` — Combine this predicate with ``other`` using ``OR``.
- `class FunctionExpression` — A whitelisted SQL function call.
  - Fields: `name: str`, `arguments: tuple[ExpressionNode, ...]`
- `class Ordering` — An ORDER BY term.
  - `descending` = `False`
  - Fields: `expression: ExpressionNode`
- `class Alias` — An aliased expression.
  - Fields: `expression: ExpressionNode`, `name: Identifier`
- `class ColumnDefinition` — Physical SQLite column definition.
  - `unique` = `False`
  - Fields: `name: str`, `affinity: str`, `nullable: bool`, `primary_key: bool`
- `class Table` — Immutable SQLite table metadata and statement factory.
  - `model` = `None`
  - `definitions` = `()`
  - Fields: `name: str`
  - `from_dataclass(cls, *, name: str, model: type[U]) -> Table` — Create table metadata from a dataclass model.
  - `columns(self) -> tuple[Column, ...]` — Return declared columns in deterministic order.
  - `with_model(self, *, model: type[DataclassInstance]) -> Table` — Return equivalent metadata associated with its row model.
  - `col(self, *, name: str) -> Column` — Return a validated column reference.
  - `create(self) -> CreateTable` — Build CREATE TABLE IF NOT EXISTS.
  - `create_index(self, *, name: str, columns: tuple[str, ...], unique: bool=False) -> CreateIndex` — Build CREATE INDEX IF NOT EXISTS over ``columns``.
  - `select(self, *, columns: tuple[SelectableNode, ...] | None=None) -> Select` — Build a SELECT statement.
  - `insert(self, *, replace: bool=False, columns: tuple[Column, ...] | None=None) -> Insert` — Build an INSERT statement.
  - `update(self, *, values: tuple[tuple[Column, ExpressionNode], ...]) -> Update` — Build an UPDATE statement.
  - `delete(self) -> Delete` — Build a DELETE statement.
- `class CreateTable` — CREATE TABLE statement.
  - Fields: `table: Table`
- `class CreateIndex` — CREATE INDEX statement.
  - `unique` = `False`
  - Fields: `name: str`, `table: str`, `columns: tuple[str, ...]`
- `class Select` — SELECT statement.
  - `predicate` = `None`
  - `sorting` = `()`
  - `limit_value` = `None`
  - Fields: `table: Table`, `columns: tuple[SelectableNode, ...]`
  - `where(self, *, predicate: PredicateNode) -> Select` — Return a copy filtered by ``predicate``.
  - `order_by(self, *, values: tuple[OrderNode, ...]) -> Select` — Return a copy ordered by ``values``.
  - `limit(self, *, value: ExpressionNode) -> Select` — Return a copy limited by ``value``.
- `class Insert` — INSERT statement.
  - `replace` = `False`
  - `conflict` = `()`
  - `updates` = `()`
  - Fields: `table: Table`, `columns: tuple[Column, ...]`
  - `on_conflict_update(self, *, conflict: tuple[Column, ...], updates: tuple[Column, ...]) -> Insert` — Return a copy with ``ON CONFLICT ... DO UPDATE``.
- `class Update` — UPDATE statement.
  - `predicate` = `None`
  - Fields: `table: Table`, `values: tuple[tuple[Column, ExpressionNode], ...]`
  - `where(self, *, predicate: PredicateNode) -> Update` — Return a copy filtered by ``predicate``.
- `class Delete` — DELETE statement.
  - `predicate` = `None`
  - Fields: `table: Table`
  - `where(self, *, predicate: PredicateNode) -> Delete` — Return a copy filtered by ``predicate``.
- `class CommandKind` — Fixed SQLite command kinds.
  - `BEGIN` = `'begin'`
  - `BEGIN_IMMEDIATE` = `'begin_immediate'`
  - `COMMIT` = `'commit'`
  - `ROLLBACK` = `'rollback'`
  - `VACUUM` = `'vacuum'`
- `class Command` — Fixed SQLite command.
  - Fields: `kind: CommandKind`
- `class Pragma` — Structured PRAGMA operation.
  - `value` = `None`
  - `call` = `None`
  - Fields: `name: str`
- `class AlterRenameTable` — ALTER TABLE RENAME TO operation.
  - Fields: `table: Identifier`, `new: Identifier`
- `class AlterRenameColumn` — ALTER TABLE RENAME COLUMN operation.
  - Fields: `table: Identifier`, `old: Identifier`, `new: Identifier`
- `class Drop` — DROP schema object operation.
  - Fields: `kind: str`, `name: Identifier`
- `class SavepointKind` — Nested transaction savepoint operation.
  - `CREATE` = `'create'`
  - `ROLLBACK_TO` = `'rollback_to'`
  - `RELEASE` = `'release'`
- `class Savepoint` — Structured savepoint operation.
  - Fields: `kind: SavepointKind`, `name: Identifier`
- `class RawSql` — External ``sqlite_schema`` SQL, never authored by the app.
  - Fields: `value: str`
  - `from_external_schema(cls, *, value: str) -> RawSql` — Wrap nonempty SQL read from an external database schema.
- `class CompiledStatement` — Deterministic compiler result.
  - Fields: `sql: str`
- `class SQLiteCompiler` — Single serialization boundary for every SQLite token.
  - `compile(cls, *, statement: StatementNode) -> CompiledStatement` — Compile an immutable AST statement, with bounded caching.
- `class Codec` — Explicit Python↔SQLite scalar conversion.
  - Fields: `encode: Callable[[T], S]`, `decode: Callable[[S], T]`
- `class TraceEvent` — Execution trace metadata without parameter values.
  - Fields: `statement_type: str`, `parameter_count: int`, `rowcount: int`
- `class SchemaDifference` — One physical-vs-declared schema difference.
  - Fields: `kind: str`, `column: str | None`, `expected: str | None`, `actual: str | None`
- `class SchemaReport` — Schema verification result.
  - Fields: `differences: tuple[SchemaDifference, ...]`
  - `matches(self) -> bool` — Whether the physical schema matches the declaration.
- `class Database` — The sole application-facing SQLite execution boundary.
  - `__init__(self, *, connection: Connection, trace: Callable[[TraceEvent], None] | None=None) -> None` — Bind a raw SQLite connection to the execution boundary.
  - `execute(self, *, statement: StatementNode, parameters: Parameters=()) -> Cursor` — Compile and execute one structural statement.
  - `begin(self, *, immediate: bool=False) -> None` — Begin an explicit outer transaction.
  - `commit(self) -> None` — Commit the current transaction.
  - `rollback(self) -> None` — Roll back the current transaction.
  - `execute_many(self, *, statement: Insert, parameter_sets: Sequence[Parameters]) -> Cursor` — Execute a typed INSERT repeatedly without executemany.
  - `fetch_one(self, *, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...] | None` — Compatibility alias returning the first row.
  - `fetch_all(self, *, statement: Select, parameters: Parameters=()) -> list[tuple[SqlScalar, ...]]` — Compatibility alias for fetching all rows.
  - `fetch_optional(self, *, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...] | None` — Return zero or one row, rejecting multiple rows.
  - `fetch_exactly_one(self, *, statement: Select, parameters: Parameters=()) -> tuple[SqlScalar, ...]` — Return exactly one row.
  - `fetch_many(self, *, statement: Select, parameters: Parameters=()) -> list[tuple[SqlScalar, ...]]` — Return all selected rows.
  - `scalar(self, *, statement: Select, parameters: Parameters=()) -> SqlScalar` — Return exactly one row containing exactly one column.
  - `decode_one(self, *, table: Table, statement: Select, parameters: Parameters=()) -> DataclassInstance | None` — Compatibility alias for decoding zero or one row.
  - `decode_optional(self, *, table: Table, statement: Select, parameters: Parameters=()) -> DataclassInstance | None` — Decode zero or one complete row into its dataclass model.
  - `decode_many(self, *, table: Table, statement: Select, parameters: Parameters=()) -> list[DataclassInstance]` — Decode complete rows into dataclass model instances.
  - `verify_schema(self, *, table: Table) -> SchemaReport` — Compare a declared table with SQLite table_xinfo metadata.
  - `transaction(self, *, immediate: bool=False) -> Generator[Database]` — Run an outer transaction or nested savepoint.
- `external_cli_sql(*, statement: StatementNode) -> str` — Serialize a statement for an external sqlite3 CLI consumer.
- `quote_identifier(*, value: str) -> str` — Quote a SQLite identifier through the compiler boundary.
- `execute(*, connection: Connection, statement: StatementNode, parameters: Parameters=()) -> Cursor` — Compatibility adapter through the centralized Database boundary.
- `function(*, name: str, arguments: tuple[ExpressionNode, ...]) -> FunctionExpression` — Build a whitelisted SQL function expression.
- `pragma(*, name: str, value: ExpressionNode | None=None, call: Identifier | Literal[SqlScalar] | None=None) -> Pragma` — Build a structured PRAGMA operation.
- `command(*, name: str) -> Command` — Build a fixed transaction/maintenance command.
- `alter_rename_table(*, table: str, new: str) -> AlterRenameTable` — Build an ``ALTER TABLE ... RENAME TO`` operation.
- `alter_rename_column(*, table: str, old: str, new: str) -> AlterRenameColumn` — Build an ``ALTER TABLE ... RENAME COLUMN`` operation.
- `drop(*, kind: str, name: str) -> Drop` — Build a ``DROP`` operation for a schema object.
- `upsert(*, table: Table, columns: tuple[Column, ...], conflict: tuple[Column, ...], updates: tuple[Column, ...]) -> Insert` — Build a typed INSERT ... ON CONFLICT ... DO UPDATE.

## Examples

Runnable demonstration for `exactus/packages/model/`.

Demonstrate the structural SQLite model against an in-memory database.

```bash
python -m exactus.packages.model.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Used by: `__main__.py`, `packages/rename_project/rename_project.py`, `tests/packages/model/test_examples.py`, `tests/packages/model/test_sqlite_hardening.py`, `tests/packages/model/test_sqlite_model.py`, `tests/packages/rename_project/test_next_safety_batch.py`, `tests/packages/rename_project/test_roundtrip.py`, `tests/packages/rename_project/test_sqlite_semantics.py`, `tests/tools/common/test_registry.py`, `tools/common/pipeline_supervisor.py`, `tools/common/registry.py`

## Tests

Tests live in `exactus/tests/packages/model/`.

- `test_examples.py` — Coverage for the ``exactus/packages/model/examples`` demonstration. (3 tests)
  - `test_example_main_runs_the_in_memory_demo`
  - `test_example_run_py_executes_as_script`
  - `test_examples_main_module_runs_the_demo`
- `test_sqlite_architecture.py` — Architectural regression checks for application SQLite access. (4 tests)
  - `test_application_does_not_bypass_database_layer`
  - `test_application_has_no_authored_sql_literals`
  - `test_application_never_compiles_sql_itself`
  - `test_raw_sql_escape_hatch_is_allowlisted`
- `test_sqlite_hardening.py` — Hardening and torture tests for the structural SQLite layer. (11 tests)
  - `test_cardinality_scalar_and_batch_operations`
  - `test_codec_is_explicit_and_bidirectional`
  - `test_constraint_translation_preserves_cause`
  - `test_decode_many_exactly_one_and_schema_drift`
  - `test_empty_in_has_deterministic_sqlite_semantics`
  - `test_expression_boolean_evaluation_is_rejected`
  - `test_nested_transactions_use_savepoints`
  - `test_randomized_identifier_and_value_round_trip`
  - `test_schema_round_trip_and_drift_detection`
  - `test_structural_ddl_commands_and_error_paths`
  - `test_trace_never_contains_parameter_values`
- `test_sqlite_model.py` — Behavioral tests for the typed SQLite compiler. (11 tests)
  - `test_database_decode_and_transaction`
  - `test_dataclass_schema_maps_optional_and_composite_primary_key`
  - `test_drop_rejects_non_schema_object_kinds`
  - `test_dynamic_identifier_operations_are_safe`
  - `test_external_sql_escape_hatch_rejects_empty`
  - `test_generated_kill_query_is_executable_sql`
  - `test_identifier_quoting_rejects_invalid_and_escapes_quotes`
  - `test_identifier_torture_and_compiler_determinism`
  - `test_null_predicates_and_transaction_rollback`
  - `test_registry_statements_execute_end_to_end`
  - `test_upsert_preserves_key_and_updates_mutable_values`

<!-- exactus:reference:end -->
