# Actions example

Discover the bundled page at mobile and desktop sizes, then replay the generated projects using a named output reference.

```sh
python -m exactus.tools.actions.examples --output .scratch/actions-example
```

Install Chromium with `python -m playwright install chromium` first if needed. The example serves [web/index.html](web/index.html) on an available loopback port, executes [assets/actions.json](assets/actions.json), writes reports to the selected folder, and stops its server. Actions integrates recording and the exactus API/report machinery; its recipe and demo assets live here.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Demonstrate discovery followed by functional verification.
- [`__main__.py`](__main__.py) — Run the Actions example.
- [`run.py`](run.py) — Discover and verify a bundled page using a named-output Actions recipe.

### Subdirectories

- [`assets/`](assets/README.md) — Provide actions json content.
- [`web/`](web/README.md) — Provide index html content.

<!-- exactus:inventory:end -->


