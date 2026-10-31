# Process Guard

`exactus.packages.guard` is a Python 3.13 process-tree supervisor for code that must not
leave subprocesses running after the owning operation finishes.

## Interfaces

### External supervisor

The strongest portable interface is `ProcessSupervisor`. It starts an arbitrary
command, continuously records recursive descendants, preserves the target exit
code, and cleans descendants after the target exits.

```python
from sys import executable
from exactus.packages.guard import ProcessSupervisor

result = ProcessSupervisor(
    command=(executable, "worker.py", "--mode", "build"),
).run()
```

From a shell:

```bash
python -m exactus.packages.guard python worker.py --mode build
```

Options belonging to the guard precede the target command. Everything after
the command begins is forwarded to the target.

### In-process guard

```python
from exactus.packages.guard import ProcessGuard

with ProcessGuard():
    main()
```

The context manager tracks descendants of the current Python process and
performs cleanup when the block leaves, including exceptional exits. It does
not suppress the application's exception.

## Process identity and PID reuse

A PID alone is not treated as a durable identity. Each observed process is
identified by its PID and OS-reported creation time. Cleanup resolves that
identity again before signaling, preventing a recycled PID from causing an
unrelated process to be killed.

## Historical tracking

The background tracker repeatedly snapshots recursive descendants and retains
records after a process disappears. This matters when an intermediate process
creates a grandchild and exits before final cleanup.

Each `ProcessRecord` contains its stable identity, observed parent PID, name,
command line, first-seen UTC timestamp, and observed ancestry depth.

## Cleanup policy

Cleanup stops the tracker, resolves still-live identities, terminates known
processes deepest-first, waits for the configured grace period, force-kills
survivors, and waits again. On POSIX the external supervisor additionally
creates a dedicated target session/process group and signals that group as a
containment backstop.

`CleanupResult` exposes `observed`, `terminated`, `killed`, and `survivors`.
`SupervisionResult` adds the target `exit_code`.

## Platform boundary

No userspace Python implementation can execute cleanup after the supervisor
itself is unconditionally destroyed (for example POSIX `SIGKILL`), after an OS
or kernel failure, or after power loss. The external supervisor protects
against the *target* terminating unexpectedly while the supervisor remains
alive. Platform containment facilities can strengthen this further but cannot
remove the machine-failure boundary.

## Examples

The complete examples can be run in all of these forms from the project root:

```bash
exactus/packages/guard/examples/run.py
python exactus/packages/guard/examples
python -m exactus.packages.guard.examples
```

If direct execution is unavailable because executable permission was not
preserved by an archive, use `python exactus/packages/guard/examples/run.py`.

The example demonstrates in-process guarding, nested external descendants,
cleanup metadata, force-cleanup accounting, and target exit-code preservation.

## Configuration

`ProcessGuard` and `ProcessSupervisor` accept `poll_interval` and
`grace_seconds`. Smaller polling intervals reduce the observation window for
very short-lived ancestry at the cost of additional process-table activity.
The grace period controls how long terminated descendants may exit normally
before cleanup escalates to force-killing them.

## Dependencies

The implementation requires Python 3.13+ and `psutil`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for process_guard. |
| `__main__.py` | Execute process_guard as a Python module. |
| `cleanup.py` | Terminate processes previously observed by a process tracker. |
| `cli.py` | Command-line entry point for external process supervision. |
| `examples/` | Executable examples for exactus.packages.guard. |
| `guard.py` | In-process descendant cleanup context manager. |
| `model.py` | Typed value models for process supervision. |
| `supervisor.py` | External process supervisor that owns and cleans a target process tree. |
| `tracker.py` | Continuously discover and retain descendant process identities. |

Run it as a module: `python -m exactus.packages.guard`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--poll-interval` | descendant discovery interval in seconds | default=0.02, type=float |
| `--grace-seconds` | grace period before force-killing descendants | default=1.5, type=float |
| `command` | command and arguments to supervise | nargs=REMAINDER |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `cleanup.py`

Terminate processes previously observed by a process tracker.

- `class ProcessCleaner` — Perform identity-safe, deepest-first descendant cleanup.
  - `cleanup() -> CleanupResult` — Terminate all observed descendants and force-kill survivors.

### `cli.py`

Command-line entry point for external process supervision.

- `class CliArguments(Namespace)` — Strongly typed command-line namespace.
- `class Cli` — Parse command-line arguments and execute the process supervisor.
  - `run(*, arguments: Sequence[str]) -> int` — Execute one supervised command and return its exit status.
  - `parser() -> ArgumentParser` — Build the command-line parser.
- `main() -> int` — Run the command-line application.

### `guard.py`

In-process descendant cleanup context manager.

- `class ProcessGuard` — Track and clean descendants created inside a context manager.
  - `result() -> CleanupResult | None` — Return cleanup metadata after the guard exits.

### `model.py`

Typed value models for process supervision.

- `class StopReason(Enum)` — Reason a supervised process stopped.
- `class ProcessIdentity` — Uniquely identify one operating-system process incarnation.
  - Fields: `pid: int`, `create_time: float`
- `class ProcessRecord` — Describe a process observed during one supervision session.
  - Fields: `identity: ProcessIdentity`, `parent_pid: int | None`, `name: str`, `command: tuple[str, ...]`, `first_seen: datetime`, `depth: int`
- `class CleanupResult` — Describe the result of descendant cleanup.
  - Fields: `observed: tuple[ProcessRecord, ...]`, `terminated: tuple[ProcessIdentity, ...]`, `killed: tuple[ProcessIdentity, ...]`, `survivors: tuple[ProcessIdentity, ...]`

### `supervisor.py`

External process supervisor that owns and cleans a target process tree.

- `class SupervisionResult` — Result returned after the target and descendants have been cleaned.
  - Fields: `exit_code: int`, `cleanup: CleanupResult`
- `class TargetProcess` — Typed adapter around psutil's subprocess-compatible process.
  - `pid() -> int` — Return the process identifier.
  - `is_running() -> bool` — Return whether the process is still running.
  - `terminate() -> None` — Request termination.
  - `wait() -> int` — Wait for completion and return the exit status.
- `class ProcessSupervisor` — Run an arbitrary command and clean its surviving process tree.
  - `run() -> SupervisionResult` — Run the target, then clean every surviving descendant.

### `tracker.py`

Continuously discover and retain descendant process identities.

- `class ProcessTracker` — Track the historical descendant tree of one root process.
  - `snapshot() -> tuple[ProcessRecord, ...]` — Discover current descendants and return the historical registry.
  - `start() -> None` — Start background descendant discovery once.
  - `stop() -> tuple[ProcessRecord, ...]` — Stop discovery after one final snapshot and return all records.

## Examples

Executable examples for exactus.packages.guard.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- Third-party: `psutil`
- Used by: `packages/__main__.py`, `tests/packages/meaningful/test_meaningful_sources.py`, `tools/__main__.py`

## Tests

Tests live in `exactus/tests/packages/guard/`.

- `test_example_run.py` — Cover the bundled ``guard`` example entry point. (1 tests)
  - `test_example_module_runs_as_a_script`

<!-- exactus:reference:end -->
