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
| `examples/` | Runnable demonstration for `exactus/packages/screenshot/`. |
| `js/` | Subdirectory. |
| `similarity.py` | Multi-factor perceptual image similarity scoring. |

Run it as a module: `python -m exactus.packages.screenshot`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `url` | URL to capture. |  |
| `--target` | CSS selector to expose fully (default: body). | default='body' |
| `--output` | Destination PNG path. | type=Path, required=True |
| `--width` | Viewport width in CSS pixels (default: 1440). | type=int, default=1440 |
| `--height` | Viewport height in CSS pixels (default: 900). | type=int, default=900 |
| `url` | Page to capture (default: the bundled web/ demo). | nargs='?', default=None |
| `--output` |  | type=Path, default=Path(__file__).resolve().parent / 'results' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Capture script package.


### `__main__.py`

Capture a URL screenshot (``python -m exactus.packages.screenshot``).


### `capture_screen.py`

Capture screenshots with arbitrarily nested overflow fully exposed.

- `class CaptureScreenDefaults` — Store immutable scalar configuration values.
  - `max_capture_height` = `8192`
  - `max_iterations` = `30`
  - `tolerance` = `1`
- `class Js` — Store browser-side JavaScript.
  - `EXPAND` = `dedent(text='\n        root => {\n            const state = window.__snap...`
  - `MEASURE` = `dedent(text='\n        root => {\n            const {top, bottom} = root....`
  - `SETTLE` = `dedent(text='\n        () => new Promise(resolve =>\n            requestA...`
  - `RESTORE` = `dedent(text='\n        () => {\n            const state = window.__snapsh...`
- `class Capture` — Represent a captured PNG.
  - Fields: `data: bytes`, `path: Path | None`, `truncated_height: bool`
  - `b64(self: Self) -> str` — Base64-encoded PNG data.
- `class CaptureSpec` — Describe capture-time options for the high-level API.
  - `path` = `None`
  - `width` = `1440`
  - `height` = `900`
  - `timeout_seconds` = `30.0`
  - `max_height` = `CaptureScreenDefaults.max_capture_height`
  - `target_only` = `False`
  - `image_type` = `'png'`
  - `quality` = `None`
  - `scale` = `'css'`
  - `user_agent` = `None`
  - `is_mobile` = `False`
  - `has_touch` = `False`
  - `color_scheme` = `None`
- `class SnapshotOptions` — Capture options for `SnapshotCapture`.
  - `max_height` = `CaptureScreenDefaults.max_capture_height`
  - `target_only` = `False`
  - `image_type` = `'png'`
  - `quality` = `None`
  - `scale` = `'css'`
- `class SnapshotCapture` — Capture a page with all nested target overflow exposed.
  - `__init__(self: Self, page: Page, target: str, *, options: SnapshotOptions | None=None) -> None` — Initialize the capture.
  - `capture(self: Self, path: Path | None=None) -> Capture` — Capture the expanded page and optionally save it.
- `class Screenshot` — Provide a high-level URL screenshot API.
  - `capture(url: str | None, target: str, spec: CaptureSpec | None=None, *, source: Browser | BrowserContext | Page | None=None) -> Capture` — Load a URL and capture its fully exposed target.

### `cli.py`

Capture a URL screenshot (``python -m exactus.packages.screenshot``).

- `main() -> int` — Capture ``url`` into a PNG file.

### `examples/__init__.py`

Provide runnable screenshot capture examples.


### `examples/__main__.py`

Run the screenshot example with the project virtual environment.


### `examples/run.py`

Capture a served page at mobile and desktop viewport sizes.

- `start_demo(*, demo: Path, log: Path) -> tuple[int, str, bool]` — Serve the bundled demo page through the shared loopback server.
- `capture(*, url: str, output: Path) -> tuple[Path, ...]` — Capture the page's full body at three viewport widths.
- `main() -> int` — Capture screenshots of the bundled demo or a supplied URL.

### `similarity.py`

Multi-factor perceptual image similarity scoring.

- `class SimilarityResult` — Contain the components of an image similarity comparison.
  - Fields: `similarity: float`, `appearance: float`, `structure: float`, `perceptual: float`, `color: float`, `geometry: float`
- `class CachedComparison` — Contain a comparison against one previously cached image.
  - Fields: `index: int`, `result: SimilarityResult`
- `class ImageSimilarity` — Compare images and cache fingerprints for repeated comparisons.
  - `__init__(self) -> None` — Initialize an empty comparison fingerprint cache.
  - `compare(cls, first: ImageSource, second: ImageSource) -> float` — Return perceptual similarity between two images.
  - `compare_detailed(cls, first: ImageSource, second: ImageSource) -> SimilarityResult` — Return the final score and individual similarity components.
  - `cache_size(self) -> int` — The number of cached image fingerprints.
  - `clear_cache(self) -> None` — Remove all cached image fingerprints.
  - `remember(self, source: ImageSource) -> int` — Fingerprint and cache an image without comparing it.
  - `compare_history(self, source: ImageSource, *, remember: bool=True) -> tuple[CachedComparison, ...]` — Compare a new image against every cached image fingerprint.

## JavaScript API reference

Top-level exports, read from the source.

### `js/capture_screen.js`

- `SnapshotCapture`

## Examples

Runnable demonstration for `exactus/packages/screenshot/`.

Capture a served page at mobile and desktop viewport sizes.

```bash
python -m exactus.packages.screenshot.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/results/README.md`, `examples/results/page-1440.png`, `examples/results/page-1728.png`, `examples/results/page-390.png`, `examples/run.py`, `examples/web/README.md`, `examples/web/index.html`, `examples/web/style.css`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md), [`server`](../server/DOCS.md)
- Used by: `tests/packages/screenshot/test_capture_support.py`, `tests/packages/screenshot/test_examples.py`

## Tests

Tests live in `exactus/tests/packages/screenshot/`.

- `test_capture_support.py` — Image similarity and the high-level screenshot capture API. (7 tests)
  - `test_collector_records_websocket_diagnostics`
  - `test_screenshot_api_sources`
  - `test_similarity_errors`
  - `test_similarity_history_cache`
  - `test_similarity_identical_and_different`
  - `test_similarity_sources`
  - `test_snapshot_capture_options`
- `test_examples.py` — Run the public screenshot example against a live demonstration site. (4 tests)
  - `test_main_module_reuses_the_recorded_server`
  - `test_main_module_serves_the_demo_as_a_script`
  - `test_main_module_with_explicit_url_skips_the_server`
  - `test_screenshot_example`
- `test_main.py` — Cover the ``exactus.packages.screenshot`` command-line entry point. (1 tests)
  - `test_main_captures_through_the_stubbed_module`

<!-- exactus:reference:end -->
