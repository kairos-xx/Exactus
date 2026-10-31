[Home](Home.md) › Guides › CLI

# Command line

One executable, one flag per tool: `exactus --<tool> [tool args ...]`.
Running `exactus` with no arguments runs the full gate — every enabled
tool plus the pipelines — which is the canonical repository check.

## Tools

| Flag | Page | Summary |
|---|---|---|
| `--lints` | [Tools-lints](Tools-lints.md) | Clean/fix convergence + Ruff, BasedPyright, pyrefly, `tsc`, ESLint, Stylelint, HTMLHint and custom Python/JS/CSS checks |
| `--coverage_tests` | [Tools-coverage_tests](Tools-coverage_tests.md) | One pytest run + `node:test` lane feeding combined coverage and per-group test reports; 90% total / per-file gates |
| `--docs` | [Tools-docs](Tools-docs.md) | Python Google docstrings and JavaScript JSDoc validation |
| `--kwargs_typehints` | [Tools-kwargs_typehints](Tools-kwargs_typehints.md) | Positional-call, bare-import and explicit-annotation checks |
| `--readme` | [Tools-readme](Tools-readme.md) | Per-directory README documentation inventories |
| `--record` | [Tools-record](Tools-record.md) | Browser recording, crawling, diagnostics and flow replay; hosts Flow Studio |
| `--frontend` | [Tools-frontend](Tools-frontend.md) | Clickable-state capture across device/theme lanes plus console/page-error diagnostics |
| `--visual_cause` | [Tools-visual_cause](Tools-visual_cause.md) | Visual-causality comparison and reporting |
| `--self_test` | [Tools-self_test](Tools-self_test.md) | Self-diagnostic catalog probing every reachable tool (hidden on normal builds) |

## Shared semantics

- **Project root** resolves in order: `--root DIR` (or `EXACTUS_ROOT`),
  the project containing a `check`/`bin/exactus` executable, then the
  current directory.
- **Reports** land in `<project>/EXACTUS_RESULTS/<TOOL>/`; override with
  `-o/--output-dir` or `[tool.exactus] reports-dir` in `pyproject.toml`.
- **Progress**: every tool draws a live progress bar; raw output is
  captured to `EXACTUS_RESULTS/<TOOL>/ARTIFACTS/{stdout,stderr}.log`
  with `@activity.json` beside them.
- **Dry run**: `--dry`/`--dry-run` analyzes without modifying sources;
  `--no-fix` audits without the repair passes.
- **Workers**: `--workers N` bounds parallel external processes
  (default `min(16, cpu_count)`).

## Help

```bash
exactus            # aggregated help listing every tool flag
exactus -h
exactus --lints -h # one tool's options
```

`exactus --self_test` exists only on executables built with
`--build-self-test`.

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
