# Report tests

Tests for [exactus/tools/reports](../../../../tools/reports/README.md):
bundle delivery, template stamping, source excerpts, web payloads,
portable links, and browser-side rendering.

## Files

- [test_report_bundle.py](test_report_bundle.py) — Report-bundle validation helpers and fingerprint command plumbing.
- [test_report_js_renderer.py](test_report_js_renderer.py) — The web report's Markdown renderer escapes code and refuses bad links.
- [test_report_render.py](test_report_render.py) — Tool templates extend the common template; mappings merge over base.
- [test_report_snippets.py](test_report_snippets.py) — Migrated tools store finding excerpts in result.json, Markdown and web.
- [test_report_web.py](test_report_web.py) — The web bundle carries the view model that renders ``result.md``.
- `__init__.py` — File.
- `test_report_bundle.py` — File.
- `test_report_js_renderer.py` — File.
- `test_report_render.py` — File.
- `test_report_snippets.py` — File.
- `test_report_web.py` — File.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Shared exactus report rendering and delivery.
- [`test_report_bundle.py`](test_report_bundle.py) — Report-bundle validation helpers and fingerprint command plumbing.
- [`test_report_js_renderer.py`](test_report_js_renderer.py) — The web report's Markdown renderer escapes code and refuses bad links.
- [`test_report_render.py`](test_report_render.py) — Tool templates extend the common template; mappings merge over base.
- [`test_report_snippets.py`](test_report_snippets.py) — Migrated tools store finding excerpts in result.json, Markdown and web.
- [`test_report_web.py`](test_report_web.py) — The web bundle carries the view model that renders ``result.md``.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


