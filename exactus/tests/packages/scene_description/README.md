# `tests/`

Tests for the scene_description package.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Tests for the scene_description package.
- [`conftest.py`](conftest.py) — Shared fixtures and fakes for the scene_description tests.
- [`support.py`](support.py) — Typed assertion helpers shared by the scene_description tests.
- [`test_capture.py`](test_capture.py) — Tests for the SceneDescriptor Playwright bridge.
- [`test_changes.py`](test_changes.py) — Tests for the deterministic SceneChangeDescriber.
- [`test_examples.py`](test_examples.py) — Tests for the runnable scene_description examples.
- [`test_js_runtime.py`](test_js_runtime.py) — Run the browser test suite and enforce JavaScript coverage.
- [`test_main.py`](test_main.py) — Tests for the scene_description command-line entry point.
- [`test_models.py`](test_models.py) — Tests for the DescriptionOptions model and JSON aliases.
- [`test_support.py`](test_support.py) — Validate the shared scene_description assertion helpers.
- [`test_visual_cause.py`](test_visual_cause.py) — Tests for the VisualCauseDescriber report enrichment.

### Subdirectories

- [`js/`](js/README.md) — Provide browser.test js content.

<!-- exactus:inventory:end -->
