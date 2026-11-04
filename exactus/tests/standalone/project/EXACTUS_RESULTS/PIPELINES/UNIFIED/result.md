# Unified Pipeline

**Run time:** 04 November 2026, 12:37:03 UTC

## Change since previous report

Previous run completed in **66.158s**.

| Findings | Current | Previous | Delta | Added | Resolved | Unchanged |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 0 | 0 | 0 | 0 | 0 | 0 |

### Category findings

| Category | Title | Current | Previous | Delta |
| --- | --- | --- | --- | --- |
| coverage_tests / coverage-average | Average file coverage | 0 | 0 | 0 |
| coverage_tests / coverage-evidence | Coverage evidence validation | 0 | 0 | 0 |
| coverage_tests / coverage-javascript-total | Overall JavaScript coverage | 0 | 0 | 0 |
| coverage_tests / coverage-meaningful | Untested meaningful sources | 0 | 0 | 0 |
| coverage_tests / coverage-meaningful-analysis | Meaningful analysis failures | 0 | 0 | 0 |
| coverage_tests / coverage-per-file | Per-file coverage minimum | 0 | 0 | 0 |
| coverage_tests / coverage-shortfall-excused | Excused sub-gate sources | 0 | 0 | 0 |
| coverage_tests / coverage-total | Overall Python coverage | 0 | 0 | 0 |
| coverage_tests / test-error | Errored tests | 0 | 0 | 0 |
| coverage_tests / test-failure | Failed tests | 0 | 0 | 0 |
| docs / DOC001 | Missing documentation | 0 | 0 | 0 |
| docs / DOC002 | Missing parameter documentation | 0 | 0 | 0 |
| docs / DOC003 | Stale parameter documentation | 0 | 0 | 0 |
| docs / DOC004 | Missing return documentation | 0 | 0 | 0 |
| docs / DOC005 | Return and yield mismatch | 0 | 0 | 0 |
| docs / DOC006 | Missing exception documentation | 0 | 0 | 0 |
| docs / DOC007 | Missing attribute documentation | 0 | 0 | 0 |
| docs / DOC008 | Malformed documentation | 0 | 0 | 0 |
| docs / DOC009 | Analysis failure | 0 | 0 | 0 |
| docs / DOC010 | Missing description | 0 | 0 | 0 |
| docs / DOC011 | Stale exception documentation | 0 | 0 | 0 |
| docs / DOC012 | Stale attribute documentation | 0 | 0 | 0 |
| kwargs_typehints / ambiguous-call | Ambiguous calls | 0 | 0 | 0 |
| kwargs_typehints / bare-import | Bare imports | 0 | 0 | 0 |
| kwargs_typehints / missing-hint | Missing type hints | 0 | 0 | 0 |
| kwargs_typehints / missing-kwargs | Missing keyword arguments | 0 | 0 | 0 |
| kwargs_typehints / parse-failure | Parse failures | 0 | 0 | 0 |
| kwargs_typehints / unresolved-callee | Unresolved callees | 0 | 0 | 0 |
| lints / CMP000 | Module does not parse | 0 | 0 | 0 |
| lints / CMP001 | Suppression marker | 0 | 0 | 0 |
| lints / CMP002 | typing.Any usage | 0 | 0 | 0 |
| lints / CMP003 | object annotation | 0 | 0 | 0 |
| lints / CMP004 | Lint ignore configuration | 0 | 0 | 0 |
| lints / CMP005 | Type-check suppression | 0 | 0 | 0 |
| lints / CMP006 | pyproject.toml missing | 0 | 0 | 0 |
| readme / RDM001 | Missing README.md | 0 | 0 | 0 |
| readme / RDM002 | Undocumented subdirectory | 0 | 0 | 0 |
| readme / RDM003 | Undocumented file | 0 | 0 | 0 |



- Status: **PASS**
- Run UUID: `aa9f5f9f35a74d85857a1b2dfecca441`
- Duration: 48.024s
- Tools: 6
- Passed: 6
- Failed: 0

## Summary

| Tool | Status | Time | Findings | Headline |
| --- | --- | ---: | ---: | --- |
| `lints` | **PASS** | 11.4s | 0 | PASS: analyzer completed with exit status 0. |
| `coverage_tests` | **PASS** | 6.6s | 0 | Total coverage 100%; Total gate 90.0%; Per-file gate 80.0%: 0 file(s) below |
| `docs` | **PASS** | 1.0s | 0 | PASS: analyzer completed with exit status 0. |
| `kwargs_typehints` | **PASS** | 3.1s | 0 | PASS: analyzer completed with exit status 0. |
| `readme` | **PASS** | 0.7s | 0 | PASS: analyzer completed with exit status 0. |
| `performance` | **PASS** | 1.1s | 0 | 6 runs profiled — slowest lints 11.4s |
## Passing tools

- `lints`
- `coverage_tests`
- `docs`
- `kwargs_typehints`
- `readme`
- `performance`

## Tool resumes

- `lints`: **PASS** (11.381s) — PASS: analyzer completed with exit status 0. [markdown](../../LINTS/result.md) · [json](../../LINTS/result.json) · [web](../../LINTS/result_web/index.html)
- `coverage_tests`: **PASS** (6.568s) — PASS: 2 of 2 tests passed; Total 100.0% meets the 90.0% minimum; every file meets 80.0% [markdown](../../COVERAGE_TESTS/result.md) · [json](../../COVERAGE_TESTS/result.json) · [web](../../COVERAGE_TESTS/result_web/index.html)
- `docs`: **PASS** (0.998s) — PASS: analyzer completed with exit status 0. [markdown](../../DOCS/result.md) · [json](../../DOCS/result.json) · [web](../../DOCS/result_web/index.html)
- `kwargs_typehints`: **PASS** (3.101s) — PASS: analyzer completed with exit status 0. [markdown](../../KWARGS_TYPEHINTS/result.md) · [json](../../KWARGS_TYPEHINTS/result.json) · [web](../../KWARGS_TYPEHINTS/result_web/index.html)
- `readme`: **PASS** (0.732s) — PASS: analyzer completed with exit status 0. [markdown](../../README/result.md) · [json](../../README/result.json) · [web](../../README/result_web/index.html)
- `performance`: **PASS** (1.078s) — 6 runs profiled — slowest lints 11.4s [markdown](../../PERFORMANCE/result.md) · [json](../../PERFORMANCE/result.json) · [web](../../PERFORMANCE/result_web/index.html)
