# `exactus/tools/common/templates/markdown/examples/`

Example normalized results and golden outputs for the core report
template rendered alone with the base `mapping.json`. The inventory
below documents every direct file and child directory.

```bash
python -m exactus.tools.common.templates.markdown.examples
```

## Directory contents

### Files

#### `result.json`

Example failing result with three findings, two blocking and one with a
source excerpt.

#### `expected.md`

Golden Markdown rendered from `result.json`.

#### `empty_result.json`

Example clean result with no findings, no scope rules and optional run
fields absent.

#### `expected_empty.md`

Golden Markdown rendered from `empty_result.json`.

#### `error_result.json`

Example crash result carrying only the envelope blocks (status
`ERROR`).

#### `expected_error.md`

Golden Markdown rendered from `error_result.json`: the summary, scope
and findings render `N/A`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Provide runnable Markdown report-template fixtures.
- [`__main__.py`](__main__.py) — Validate the Markdown report-template fixture set.
- [`empty_result.json`](empty_result.json) — Provide empty result json content.
- [`error_result.json`](error_result.json) — Provide error result json content.
- [`expected.md`](expected.md) — **Run time:** N/A
- [`expected_empty.md`](expected_empty.md) — **Run time:** N/A
- [`expected_error.md`](expected_error.md) — **Run time:** N/A
- [`result.json`](result.json) — Provide result json content.
- [`run.py`](run.py) — Validate bundled Markdown report input and expected-output fixtures.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->

