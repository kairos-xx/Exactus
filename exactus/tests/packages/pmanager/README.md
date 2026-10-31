# Tests

Run the complete package test suite with:

```bash
python -m pytest exactus/tests/packages/pmanager
```

The suite covers the typed configuration model, object graph API, detached
runtime, lifecycle hooks, live status, broadcasts, platform abstraction,
discovery, policies, and CLI/runtime specification behavior.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for the counter orchestrator.
- [`test_api.py`](test_api.py) — Public API contract tests.
- [`test_api_extended.py`](test_api_extended.py) — Extended public API tests.
- [`test_broadcast.py`](test_broadcast.py) — Live worker broadcast integration tests.
- [`test_class_runner.py`](test_class_runner.py) — Unit tests for the detached class-runner entry module.
- [`test_core.py`](test_core.py) — Behavior tests for the orchestration engine.
- [`test_example_run.py`](test_example_run.py) — Cover the bundled ``pmanager`` example entry point.
- [`test_examples.py`](test_examples.py) — Exercise the bundled pmanager examples as user-facing documentation.
- [`test_model.py`](test_model.py) — Typed specification model contract tests.
- [`test_object_api.py`](test_object_api.py) — Object-first API tests.
- [`test_platform.py`](test_platform.py) — Cross-platform backend contract tests.
- [`test_spec.py`](test_spec.py) — Specification smoke tests.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
