# screenshot/

Screenshot capture script package: capture pages with arbitrarily nested
overflow fully exposed, and score image similarity perceptually.

## Behavior

- Overflow expansion: scroll containers of any depth are grown so hidden
  content is included rather than clipped.
- Deterministic output for the same page state — suitable for golden
  comparisons through `similarity.py`.
- Used by the server/screenshot shortcuts to produce durable visual
  evidence attached to reports.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Capture script package. |
| `__main__.py` | Capture a URL screenshot (``python -m exactus.packages.screenshot``). |
| `capture_screen.py` | Capture screenshots with arbitrarily nested overflow fully exposed. |
| `cli.py` | Capture a URL screenshot (``python -m exactus.packages.screenshot``). |
| `examples/` | [run.py](run.py) captures a served page at 390, 1440, and 1728 pixels wide using [Screenshot.capture](../capture_screen.py). |
| `js/` | Provide capture screen js content. |
| `similarity.py` | Multi-factor perceptual image similarity scoring. |

Run it as a module: `python -m exactus.packages.screenshot`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `url` | URL to capture. |  |
| `--target` | CSS selector to expose fully (default: body). | default='body' |
| `--output` | Destination PNG path. | required=True, type=Path |
| `--width` | Viewport width in CSS pixels (default: 1440). | default=1440, type=int |
| `--height` | Viewport height in CSS pixels (default: 900). | default=900, type=int |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `capture_screen.py`

Capture screenshots with arbitrarily nested overflow fully exposed.

- `class CaptureScreenDefaults` — Store immutable scalar configuration values.
- `class Js(StrEnum)` — Store browser-side JavaScript.
- `class Capture` — Represent a captured PNG.
  - Fields: `data: bytes`, `path: Path | None`, `truncated_height: bool`
  - `b64(: Self) -> str` — Base64-encoded PNG data.
- `class CaptureSpec` — Describe capture-time options for the high-level API.
  - Fields: `path: Path | None`, `width: int`, `height: int`, `timeout_seconds: float`, `max_height: int`, `target_only: bool`, `image_type: Literal['png', 'jpeg']`, `quality: int | None`, `scale: Literal['css', 'device']`, `user_agent: str | None`, `is_mobile: bool`, `has_touch: bool`, `color_scheme: Literal['light', 'dark'] | None`
- `class SnapshotOptions` — Capture options for `SnapshotCapture`.
  - Fields: `max_height: int`, `target_only: bool`, `image_type: Literal['png', 'jpeg']`, `quality: int | None`, `scale: Literal['css', 'device']`
- `class SnapshotCapture` — Capture a page with all nested target overflow exposed.
  - `async capture(: Self, path: Path | None=None) -> Capture` — Capture the expanded page and optionally save it.
- `class Screenshot` — Provide a high-level URL screenshot API.
  - `async capture(url: str | None, target: str, spec: CaptureSpec | None=None, *, source: Browser | BrowserContext | Page | None=None) -> Capture` — Load a URL and capture its fully exposed target.

### `cli.py`

Capture a URL screenshot (``python -m exactus.packages.screenshot``).

- `main() -> int` — Capture ``url`` into a PNG file.

### `similarity.py`

Multi-factor perceptual image similarity scoring.

- `class SimilarityResult` — Contain the components of an image similarity comparison.
  - Fields: `similarity: float`, `appearance: float`, `structure: float`, `perceptual: float`, `color: float`, `geometry: float`
- `class CachedComparison` — Contain a comparison against one previously cached image.
  - Fields: `index: int`, `result: SimilarityResult`
- `class ImageSimilarity` — Compare images and cache fingerprints for repeated comparisons.
  - `compare(first: ImageSource, second: ImageSource) -> float` — Return perceptual similarity between two images.
  - `compare_detailed(first: ImageSource, second: ImageSource) -> SimilarityResult` — Return the final score and individual similarity components.
  - `cache_size() -> int` — The number of cached image fingerprints.
  - `clear_cache() -> None` — Remove all cached image fingerprints.
  - `remember(source: ImageSource) -> int` — Fingerprint and cache an image without comparing it.
  - `compare_history(source: ImageSource, *, remember: bool=True) -> tuple[CachedComparison, ...]` — Compare a new image against every cached image fingerprint.

## JavaScript API reference

Exports of the package's ES modules, read from the source.

### `js/capture_screen.js`

- `class SnapshotCapture` — Capture a full-height screenshot of a target element.
  - `async capture(options = {})`

## Examples

[run.py](run.py) captures a served page at 390, 1440, and
1728 pixels wide using [Screenshot.capture](../capture_screen.py).

With no arguments it serves the bundled [demo page](web/README.md) through
`exactus.packages.server` — the page's clamped feed element forces the capture engine
to expand the hidden browser window beyond the 900px viewport — and saves
each PNG under `results/` (override with `--output`):

```sh
python -m exactus.packages.screenshot.examples
```

A URL may also be supplied to capture any other served page:

```sh
python -m exactus.packages.screenshot.examples http://127.0.0.1:8000
```

Install the Playwright Chromium browser first if needed:
`python -m playwright install chromium`. The example prints each saved PNG
path and closes the browser after each capture.

### Files

- `__init__.py` — File.
- `__main__.py` — File.
- `run.py` — File.
- `web/` — bundled demo page served by the example.

Files: `__init__.py`, `__main__.py`, `results/page-1440.png`, `results/page-1728.png`, `results/page-390.png`, `run.py`, `web/index.html`, `web/style.css`

## Dependencies and consumers

- Third-party: `PIL`, `playwright`
- Used by: `../pyproject.toml`, `tests/packages/meaningful/test_meaningful_sources.py`

## Tests

Tests live in `exactus/tests/packages/screenshot/`.

- `js/screenshot.test.mjs` — Verify viewport capture and restoration after screenshot failures. (2 tests)
  - capture rejects missing viewports and elements before mutating a page
  - nested overflow is expanded for capture and restored even after failure
- `test_capture_support.py` — Image similarity and the high-level screenshot capture API. (7 tests)
  - `test_similarity_identical_and_different`
  - `test_similarity_sources`
  - `test_similarity_errors`
  - `test_similarity_history_cache`
  - `test_snapshot_capture_options`
  - `test_screenshot_api_sources`
  - `test_collector_records_websocket_diagnostics`
- `test_examples.py` — Run the public screenshot example against a live demonstration site. (4 tests)
  - `test_screenshot_example`
  - `test_main_module_serves_the_demo_as_a_script`
  - `test_main_module_with_explicit_url_skips_the_server`
  - `test_main_module_reuses_the_recorded_server`
- `test_main.py` — Cover the ``exactus.packages.screenshot`` command-line entry point. (1 tests)
  - `test_main_captures_through_the_stubbed_module`

<!-- exactus:reference:end -->
