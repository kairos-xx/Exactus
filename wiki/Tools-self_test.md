[Home](Home.md) > [Tools](Tools.md) > self_test

# tools/self_test/

The executable's self-diagnostic catalog tool, exposed as
`exactus --self_test`. The flag is hidden on normal builds; only
executables built with `--build-self-test` carry the marker that
enables it.

## Files

| File | Description |
|---|---|
| `arguments.py` | The self_test grammar, declared without importing the execution engine. |
| `main.py` | Probe every tool reachable by this exactus and report the results: generates a minimal fixture project in a temporary directory, checks each expected tool twice over — system executables on `PATH` first, the pyz's bundled toolchain as fallback — then runs the `unified` pipeline against the fixture and requires every `EXACTUS_RESULTS` report to be fresh, PASS and issue-free. |

## Behavior

- The fixture — one HTML, JS, CSS, Python, pytest and JS-test file plus
  a `pyproject.toml` — lives inside a temporary directory; the only
  artifact left behind is the standard `EXACTUS_RESULTS/SELF_TEST`
  report bundle.
- Each probe records which source answered (`system`, `bundle` or
  `none`), so the diagnostic is valid on a bare `python:3.13-slim`
  container, a development machine with a full toolchain, and anything
  in between.
- A loopback-only static site ungates `frontend`, `record` and
  `visual_cause` inside the fixture, so no network access is needed.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/tools/self_test/`](../exactus/tools/self_test/) | [`exactus/tests/tools/self_test/`](../exactus/tests/tools/self_test/) | [`DOCS.md`](../exactus/docs/tools/self_test/DOCS.md) |

[< Tools-reports](Tools-reports.md) · [Tools index](Tools.md) · [Tools-visual_cause >](Tools-visual_cause.md)
