[Home](Home.md) > [Packages](Packages.md) > model

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/model/`](../exactus/packages/model/) | [`exactus/tests/packages/model/`](../exactus/tests/packages/model/) | [`DOCS.md`](../exactus/docs/packages/model/DOCS.md) |

[< Packages-meaningful](Packages-meaningful.md) · [Packages index](Packages.md) · [Packages-organize >](Packages-organize.md)
