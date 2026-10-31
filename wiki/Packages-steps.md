[Home](Home.md) > [Packages](Packages.md) > steps

# steps/

Timestamped step tracing shared by the Exactus packages: one
`timestamp +elapsed step` line per event in a plain text file.

## Behavior

- `step_log(path=...)` creates missing parents, opens the file for
  writing and becomes the process-wide active log for the context.
- Nested `step_log` contexts reuse the already active log instead of
  truncating the file, so a caller may activate the same run's log
  inside an outer activation.
- `trace(step=..., depth=...)` is a no-op until a log is active, so
  packaged tools can instrument themselves unconditionally.
- Writes are serialized through a lock and flushed per line; a file
  that cannot be opened or written degrades to a silent no-op.
- The nearest `pyproject.toml` — found by walking up from the
  destination, then from the working directory — can disable tracing:
  `[tool.steps] write = false` discards every call and never creates
  the file.
- Depth levels mark nesting: `0` tool boundary, `1` stage, `2` substep,
  `3` detail and `4` per-file record.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/steps/`](../exactus/packages/steps/) | [`exactus/tests/packages/steps/`](../exactus/tests/packages/steps/) | [`DOCS.md`](../exactus/docs/packages/steps/DOCS.md) |

[< Packages-shebang_update](Packages-shebang_update.md) · [Packages index](Packages.md) · [Packages-todo_sync >](Packages-todo_sync.md)
