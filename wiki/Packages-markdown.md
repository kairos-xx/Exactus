[Home](Home.md) > [Packages](Packages.md) > markdown

# markdown/

The generic Markdown report engine: renders normalized `result.json`
documents through sandboxed Jinja2 templates driven by declarative
mapping files. Report-independent — nothing here imports `exactus.tools`.

Run standalone with `python -m exactus.markdown`.

## Mapping pipeline

A mapping file declares ordered steps applied in a fixed order:

`resolve → where → sort → unique → slice → each → flatten → pick/omit → join → template`

- Sorting is numeric first, then case-folded text — deterministic.
- Path expressions support nested keys, indices and `$` root anchors.
- Predicates compose the comparison operators with boolean logic.

## Security model

- Jinja2 runs sandboxed — no attribute access outside the data model.
- Templates resolve only inside declared allowed roots; `../` traversal
  and symlink escapes are rejected.
- Undefined access is configurable: strict mode raises typed errors,
  lenient mode renders empty.
- `md_fence` sizes every code fence beyond the longest backtick/tilde
  run inside the fenced content, preventing fence injection.

## Packaging

Templates, mapping data and examples ship via `importlib.resources`, so
the engine renders from inside the zipapp without unpacking.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/markdown/`](../exactus/packages/markdown/) | [`exactus/tests/packages/markdown/`](../exactus/tests/packages/markdown/) | [`DOCS.md`](../exactus/docs/packages/markdown/DOCS.md) |

[< Packages-http_process](Packages-http_process.md) · [Packages index](Packages.md) · [Packages-meaningful >](Packages-meaningful.md)
