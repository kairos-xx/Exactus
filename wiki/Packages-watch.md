[Home](Home.md) > [Packages](Packages.md) > watch

# watch/

Project-local recursive filesystem watcher that mirrors source changes
into a destination tree and records destination activity.

## Behavior

- Changes under the watched root are copied to the destination; removed
  entries are pruned when `mirror-deletes` is enabled.
- Excluded entries count as stale and are deleted during pruning —
  rsync `--delete-excluded` semantics.
- Entries on the `include` list override exclusion, so OS-generated
  files such as `.DS_Store` are left alone instead of being pruned
  repeatedly.
- Activity records are always kept, regardless of pruning rules.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/watch/`](../exactus/packages/watch/) | [`exactus/tests/packages/watch/`](../exactus/tests/packages/watch/) | [`DOCS.md`](../exactus/docs/packages/watch/DOCS.md) |

[< Packages-visual_cause](Packages-visual_cause.md) · [Packages index](Packages.md) · [Packages-widgets-widget_clock >](Packages-widgets-widget_clock.md)
