[Home](Home.md) > [Packages](Packages.md) > screenshot

# screenshot/

Screenshot capture script package: capture pages with arbitrarily nested
overflow fully exposed, and score image similarity perceptually.

## Behavior

- Overflow expansion: scroll containers of any depth are grown so hidden
  content is included rather than clipped.
- Deterministic output for the same page state — suitable for golden
  comparisons through `similarity.py`.
- Used by the server/screenshot shortcuts to produce durable visual
  evidence attached to reports.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/screenshot/`](../exactus/packages/screenshot/) | [`exactus/tests/packages/screenshot/`](../exactus/tests/packages/screenshot/) | [`DOCS.md`](../exactus/docs/packages/screenshot/DOCS.md) |

[< Packages-scene_description](Packages-scene_description.md) · [Packages index](Packages.md) · [Packages-server >](Packages-server.md)
