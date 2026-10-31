[Home](Home.md) > [Packages](Packages.md) > guard

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/guard/`](../exactus/packages/guard/) | [`exactus/tests/packages/guard/`](../exactus/tests/packages/guard/) | [`DOCS.md`](../exactus/docs/packages/guard/DOCS.md) |

[< Packages-group_final](Packages-group_final.md) · [Packages index](Packages.md) · [Packages-http_process >](Packages-http_process.md)
