[Home](Home.md) > [Packages](Packages.md) > pmanager

# pmanager API

`pmanager` is a Python 3.13 process manager with a symmetric typed
configuration model, object-reference process graph API, detached
cross-platform workers, lifecycle hooks, structured Python arguments,
live status enrichment, and context/global broadcasts.

## Configuration

Use `Specification` for a serializable mutable data model or `Spec` for the
object-first graph builder. `Spec.process()` returns a `Process` object that
can be passed directly to `Dependency` and child collections. Direct object
references are retained in memory; names are produced only at the
serialization/runtime boundary.

## Runtime

`Orchestrator` owns runtime access. `Context` binds operations to one context.
`ProcessHandle` provides status, pause, resume, reset, restart, cancel, kill,
wait, watch, and subscription operations.

## Python workers

Subclass `ProcessClass`, use `PythonClassExecutor`, and optionally implement
decorated `@pause`, `@resume`, `@reset`, `@cancel`, `@kill`, `@status`, and
`@receive(topic)` methods. The kill hook is a bounded pre-kill hook and cannot
prevent mandatory termination.

## Broadcasts

Workers and orchestrators may publish context or global live events. Events
carry source identity, context, generation, topic, payload, sequence, and
timestamp. Delivery is live and bounded rather than durable.

## Examples

See `examples/api/run.py` and `examples/cli/run.py`.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/pmanager/`](../exactus/packages/pmanager/) | [`exactus/tests/packages/pmanager/`](../exactus/tests/packages/pmanager/) | [`DOCS.md`](../exactus/docs/packages/pmanager/DOCS.md) |

[< Packages-performance](Packages-performance.md) · [Packages index](Packages.md) · [Packages-project_python >](Packages-project_python.md)
