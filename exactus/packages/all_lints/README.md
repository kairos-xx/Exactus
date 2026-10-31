# `all_lints/`

Run project linters and merge their diagnostics into one JSON report.

Each tool's selected files are grouped into worker-sized batches, so
Ruff, ESLint, Stylelint and the HTML linter cost one process per chunk
rather than one per file; basedpyright splits its file set across four
parallel instances while pyrefly still runs once, and TypeScript checks
the discovered `jsconfig`/`tsconfig` project in a single pass. The Ruff
docstring row (`ruff_docs`) launches no process — its results reuse the
`--select ALL` run filtered to `D` rule codes. All checks share a worker
pool capped at sixteen by default (override with `--workers`). It
normalizes every diagnostic into a shared shape and writes a single
aggregate report. Ignore patterns come from a built-in default list
merged with each tool's `pyproject.toml` section (`[tool.ruff]`,
`[tool.basedpyright]`, `[tool.pyrefly]`) and are applied while
discovering the files each tool receives.

Progress counts completed file/tool checks rather than waiting for every
tool to finish a file. A one-second activity heartbeat identifies pending
tools without inventing progress. Embedded Exactus progress assigns 60%
of the overall bar to the main lint checks and never moves backwards.

```bash
python -m exactus.packages.all_lints [root] -o AUDIT_RESULTS.json
```

Run directly from the command line (`python -m exactus.packages.all_lints` or
`python exactus/packages/all_lints`), the tool creates an `ALL_LINTS_RESULTS/`
directory under the audited root: `result.json` holds the merged report
(the `-o` flag may still redirect it), `ARTIFACTS/steps.txt` records the
timestamped step trace, `ARTIFACTS/@activity.json` publishes an
`exactus/activity/v1` liveness document refreshed every second, and
`ARTIFACTS/stdout.log`/`stderr.log` capture the console streams with
ANSI escapes stripped. With `--collect-files`, `FILES/files.zip`
archives every file that produced diagnostics in report order — `unzip
-o ALL_LINTS_RESULTS/FILES/files.zip -d .` from the project root
restores them in place — and `FILES/TREE.txt` lists the archive members
via `exactus/packages/tree`. Every directory carries its own `README.md`. Embedded
callers that drive `AuditRunner` directly get none of this file layout.

The report directory name and the FILES bundle are configurable through
`[tool.all_lint]` (or `[tool.all_lints]`) in the audited project's
`pyproject.toml`: `output-dir` overrides `ALL_LINTS_RESULTS` and
`collect-files = true` writes the `FILES/` bundle; the `--collect-files`
flag does the same from the command line — the same opt-in semantics as
`[tool.exactus] collect-files` and every Exactus tool's `--collect-files`
flag. Both default to the standalone layout.

Pass `--unsafe-fixes` to allow Ruff's unsafe fixes during the format/fix
stabilization loop. The Python API exposes the same switch through
`AuditRunner.run_all(..., unsafe_fixes=True)`; it remains off by default.
`AuditRunner.use_repair(repair=...)` installs a `FileRepair` that runs for
every file after each Ruff format/fix cycle; a file the repair changed gets
another complete cycle. Exactus uses it for long-line repair.
`ToolSpec.command_prefix` lets callers use a multi-command launcher such as
an Exactus platform bundle while keeping all discovery, parsing and reporting
inside `all_lints`.

`__main__.py` makes the directory itself runnable as well:
`python exactus/packages/all_lints` puts the directory on `sys.path`, switches to
the project interpreter when one exists, and calls `main()` from
`core.py`. The module and example entry points both use the shared
`exactus.packages.project_python` bootstrap. `examples/` holds a runnable demo that rebuilds a throwaway
project under `.scratch/`, prints the merged excludes and generated
commands, and renders a synthetic report without invoking real linters.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Run project linters and merge their diagnostics into one JSON report.
- [`__main__.py`](__main__.py) — Run the merged linter audit.
- [`core.py`](core.py) — Run project linters in parallel and merge diagnostics into one report.

### Subdirectories

- [`examples/`](examples/README.md) — Runnable demonstration for `exactus/packages/all_lints/`.

<!-- exactus:inventory:end -->
