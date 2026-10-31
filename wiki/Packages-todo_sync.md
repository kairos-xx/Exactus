[Home](Home.md) > [Packages](Packages.md) > todo_sync

# todo_sync/

Reusable, standard-library-only TODO-list synchronizer with no
dependency on the Exactus runtime, npm, or the network. It never infers
completion or changes checkboxes.

## Behavior

- Normalized task headers use
  `**ID** **Priority** **Category** — Description`.
- `--normalize` migrates legacy headers; `--normalize --check` validates
  without writing.
- Watchers refuse to kill processes they did not start.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/todo_sync/`](../exactus/packages/todo_sync/) | [`exactus/tests/packages/todo_sync/`](../exactus/tests/packages/todo_sync/) | [`DOCS.md`](../exactus/docs/packages/todo_sync/DOCS.md) |

[< Packages-steps](Packages-steps.md) · [Packages index](Packages.md) · [Packages-tree >](Packages-tree.md)
