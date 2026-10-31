# `common/`

Shared test helpers, pytest fixtures and the Playwright harness.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Shared test helpers, pytest fixtures and the Playwright harness.
- [`browser.mjs`](browser.mjs) — Run browser assertions and retain their V8 coverage for the exactus gate.
- [`support.py`](support.py) — Typed assertion, reflection and fixture helpers shared by the suite.
- [`test_support.py`](test_support.py) — The shared assertion and reflection helpers fail loudly when violated.

### Subdirectories

- [`check/`](check/README.md) — Test the top-level exactus check CLI.
- [`contracts/`](contracts/README.md) — Tests of repository-wide structural contracts.
- [`json_serializers/`](json_serializers/README.md) — Test cross-subsystem JSON serializer contracts.
- [`package/`](package/README.md) — Test package independence and boundary rules.

<!-- exactus:inventory:end -->
