# Tests

Tests of `exactus/tools`: shared runtime and every tool.

- `__init__.py` — Package marker for tests mirroring `exactus/tools`.
- `common/` — Tests of `exactus/tools/common` leaf primitives and shared templates.
- `coverage_tests/` — Tests of the coverage-tests tool.
- `docs/` — Tests of the docs tool.
- `exec/` — Tests of the exec tool.
- `kwargs_typehints/` — Tests of the kwargs-typehints tool.
- `lints/` — Tests of the lints tool.
- `readme/` — Tests of the readme tool.
- `record/` — Tests of the record exactus tool.
- `frontend/` — Tests of the frontend tool.
- `test_analyzers.py` — In-process runs of every static analyzer over the toolkit and a sample.
- `test_catalog.py` — Catalog validation, alias resolution, and pipeline wave planning.
- `test_execution.py` — The shared exactus execution wrapper, fallbacks, and crash recording.
- `test_misc_entrypoints.py` — Thin dispatch modules and path-plumbing files.
- `test_models_api.py` — Result models, progress documents, the process API, and runtime.
- `test_no_bare_imports.py` — No exactus tool module imports a sibling through a bare module name.
- `test_output_tree.py` — Every tool run leaves ``@activity.json``, ``stderr.log``/``stdout.log``.
- `test_registry.py` — The cross-process run registry.
- `test_toolkit.py` — Regression tests for catalog, tree filtering, and launcher dispatch.

Shared helper tests live in [common/](common/README.md); report delivery
and renderer tests live in [reports/](reports/README.md).

## Subdirectories

- `reports/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests mirroring the exactus tools suite.
- [`test_self_test.py`](test_self_test.py) — Test self-diagnostic boundaries without running the nested tool suite.
- [`test_tools.py`](test_tools.py) — Cover the ``exactus.tools`` example-runner ``__main__`` module.

### Subdirectories

- [`actions/`](actions/README.md) — No subdirectories.
- [`common/`](common/README.md) — Tests of `exactus/tools/common` leaf primitives and shared templates.
- [`completion/`](completion/README.md) — Tests for ``exactus.tools.completion`` wiring.
- [`coverage_tests/`](coverage_tests/README.md) — Tests of the coverage-tests tool.
- [`docs/`](docs/README.md) — Tests of the docs tool.
- [`frontend/`](frontend/README.md) — Tests of the frontend tool.
- [`kwargs_typehints/`](kwargs_typehints/README.md) — Tests of the kwargs-typehints tool.
- [`lints/`](lints/README.md) — Tests of the lints tool.
- [`performance/`](performance/README.md) — No subdirectories.
- [`readme/`](readme/README.md) — Tests of the readme tool.
- [`record/`](record/README.md) — Contain record resources and their directory inventory.
- [`reports/`](reports/README.md) — Tests for \[exactus/tools/reports\](../../../../tools/reports/README.md): bundle delivery, template stamping, source excerpts, web payloads, portable links, and browser-side rendering.
- [`visual_cause/`](visual_cause/README.md) — Tests of the visual-cause tool.

<!-- exactus:inventory:end -->

