[Home](Home.md) › Guides › Testing

# Testing

Suites mirror the source tree: `exactus/tests/packages/<pkg>/`,
`exactus/tests/tools/<tool>/`, `exactus/tests/bundle/`,
`exactus/tests/common/`, plus JavaScript `node:test` files alongside
their modules.

## Run with the project venv

```bash
.venv/bin/python -m pytest exactus/tests/packages/pmanager -x -q
```

**Always use `.venv/bin/python`** — `exactus.packages.project_python`
re-`exec`s into `.venv` when a foreign interpreter imports an exactus
entry point. Under a system/anaconda `python3` the pytest process is
silently replaced mid-run (exit 0, truncated output, no summary).

## Run per-directory, not the whole tree

Collect `tests/packages/` one directory at a time. Two pre-existing
quirks make one-process runs unreliable:

- `project_python/examples/run.py` inserts `exactus/packages/` at
  `sys.path[0]` during collection, shadowing same-named modules
  (e.g. `rename_project` resolves to the package instead of the inner
  `rename_project.py`).
- `rename_project` needs `pythonpath = .` from its own `pytest.ini`.

The coverage gate shards tests per-directory, which sidesteps both.

## Fast iteration

```bash
# one package's suite (seconds, not minutes)
.venv/bin/python -m pytest exactus/tests/packages/exactus_mcp -q
```

Verified baselines: `package` 161, `exactus_mcp` 192,
`visual_cause`+`rename_project` 412, `pmanager` 78, `zstd_portable` 60 —
all green.

## Gates

`exactus --coverage_tests` runs the full suite plus the `node:test`
lane, then validates evidence completeness and floors — 90% total, 80%
per-file (`--fail-under`/`--per-file-minimum` override). Reports land in
`EXACTUS_RESULTS/COVERAGE_TESTS/`.

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
