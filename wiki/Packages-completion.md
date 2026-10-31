[Home](Home.md) > [Packages](Packages.md) > completion

# completion/

Grammar-aware shell autocomplete for `exactus`: the engine, the catalog
describing the CLI grammar, the hidden `__complete` wire protocol, shell
adapters and user-level installation.

## How it works

1. A generated shell function intercepts completion and invokes
   `exactus __complete …` with the current words and cursor position.
2. `protocol.py` decodes the request; `engine.py` walks the grammar from
   `catalog.py`/`defaults.py` to find the expected token kind.
3. `providers.py` resolves dynamic candidates (tool names, pipeline
   names, filesystem paths, option values) deterministically.
4. Candidates return over the wire protocol; the shell renders them.

## Invariants

- Completion never mutates project state; `__complete` is read-only.
- Providers must be deterministic and must not import tool execution
  engines — the grammar, not the tools, drives completion.
- Install targets are strictly user-level profile files; nothing writes
  system shell configuration.
- Long options fold `-` and `_` exactly like the shared
  `exactus.packages.argument_parser.ExactusArgumentParser`: `--collect_`
  completes to the registered `--collect-files`, and an already typed
  `--dry_run` counts as using `--dry-run`, so it is not offered twice.
  Candidates always use the registered spelling.
- The catalog introspects each tool's public grammar
  (`tools/<tool>/arguments.py`), so every option declared there — for
  example `kwargs_typehints --python INTERPRETER` — is completable, with
  its help text, without a second hand-written list.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/completion/`](../exactus/packages/completion/) | [`exactus/tests/packages/completion/`](../exactus/tests/packages/completion/) | [`DOCS.md`](../exactus/docs/packages/completion/DOCS.md) |

[< Packages-browser](Packages-browser.md) · [Packages index](Packages.md) · [Packages-exactus_mcp >](Packages-exactus_mcp.md)
