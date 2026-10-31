[Home](Home.md) > [Packages](Packages.md) > group_final

# group_final/

AST-based refactoring that groups safely movable module-level `Final`
constants into a `Constants` class and updates references across the
source tree.

## Behavior

- Only provably safe constants move: values and references are resolved
  through AST analysis rather than text rewriting.
- Generated `Constants` classes follow the repository's grouped-constant
  convention; surviving references are rewritten to `Constants.<name>`.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/group_final/`](../exactus/packages/group_final/) | [`exactus/tests/packages/group_final/`](../exactus/tests/packages/group_final/) | [`DOCS.md`](../exactus/docs/packages/group_final/DOCS.md) |

[< Packages-external](Packages-external.md) · [Packages index](Packages.md) · [Packages-guard >](Packages-guard.md)
