# `source_merger/`

Conflict-aware concurrent source reconciliation for Python, JS, HTML and CSS.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Conflict-aware concurrent source reconciliation for.
- [`advanced.py`](advanced.py) — Compatibility exports for the earlier tracked source-merger path.
- [`cache.py`](cache.py) — Bounded, session-owned parse and identity caches with.
- [`delta.py`](delta.py) — Conservative mutation-budget checks for independently.
- [`engine.py`](engine.py) — Conflict-first three-way reconciliation through tracked.
- [`expression.py`](expression.py) — Conservative expression reconciliation inside matched Python.
- [`foreign_parser.py`](foreign_parser.py) — Parse JavaScript, TypeScript, CSS and HTML with precise source locations.
- [`html_attributes.py`](html_attributes.py) — Conservative three-way HTML attribute reconciliation by source spans.
- [`incremental.py`](incremental.py) — Safely reparse an isolated Python function without rescanning its module.
- [`live.py`](live.py) — Reconcile a concurrent user edit with a tool proposal.
- [`merge.py`](merge.py) — Compatibility exports for the earlier source-merger module path.
- [`model.py`](model.py) — Immutable records used by the deterministic three-way source merger.
- [`parse_node.cjs`](parse_node.cjs) — Read JavaScript/TypeScript/CSS syntax without executing submitted source.
- [`patch.py`](patch.py) — Precise source-span operations with overlap and indentation safeguards.
- [`python_imports.py`](python_imports.py) — Isolate Python import header refactoring from unrelated concurrent edits.
- [`python_literals.py`](python_literals.py) — Preserve tool line wrapping during independent Python literal edits.
- [`python_parser.py`](python_parser.py) — Parse Python into source-precise, rename-insensitive structural records.
- [`tokens.py`](tokens.py) — Whitespace-insensitive token-level three-way merge fallback.
- [`tracking.py`](tracking.py) — Indexed hierarchical identity matching for independently.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
