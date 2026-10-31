# Visual cause

Compare pages or stylesheet variants at one or more viewports, explain the
changed elements, classify them with ExtendedSelector queries, and write the
standard Exactus Markdown, JSON, web, and artifact bundle.

Run an ad-hoc overlay comparison with:

```bash
exactus visual_cause --html site --css-b proposed.css --viewport 1440x900
```

Configured `[[tool.exactus.visual_cause.targets]]` entries can be selected with
repeatable `--target NAME` flags.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Compare rendered pages and classify causal visual changes.
- [`arguments.py`](arguments.py) — Declare the visual-cause command-line grammar.
- [`core.py`](core.py) — Orchestrate visual-cause targets, engines, queries, and verdicts.
- [`levels.py`](levels.py) — Resolve visual-cause finding levels from selector matches.
- [`main.py`](main.py) — Run the visual-cause exactus and write its report bundle.
- [`queries.py`](queries.py) — Bridge visual-cause findings to the ExtendedSelector page engine.
- [`report.py`](report.py) — Normalize visual-cause results for the shared report bundle.
- [`service.py`](service.py) — Own local HTTP services used by visual-cause targets.
- [`targets.py`](targets.py) — Normalize and validate configured visual-cause targets.

### Subdirectories

- [`templates/`](templates/README.md) — `template.md` renders normalized visual-cause targets, findings, selector queries, and image evidence. `mapping.json` exposes the tool extension blocks to the shared report renderer.

<!-- exactus:inventory:end -->
