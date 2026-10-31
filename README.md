# Exactus

Standalone, project-agnostic exactus. Drop the folder anywhere and point
it at any Python/JavaScript project — nothing inside references a specific
repository.

## iCloud duplicate folders

Tool runs reconcile numbered copies such as `folder 2` when `folder` exists.
Identical files are removed and unique files are moved into the canonical folder.
Different files with the same name are preserved under `.icloud-conflicts/`
before the duplicate folder is removed. Unmatched folders and directory symlinks
are retained. Cleanup runs at exactus startup and completion, and before packaging,
building, or launching the offline bundle, so the project can remain in iCloud.

## Layout

- `bin/exactus` — executable zipapp (no extension) produced by
  `exactus/scripts/build_make`; it packages the whole `exactus/` package and runs
  the `exactus` package entry point. The `bin/exactus` file is
  generated output and is excluded from packaging.
- `exactus/scripts/build_make` — root build script; with no arguments it produces all
  three artifacts: `bin/exactus`, the `build/` dist directory (the
  zipapp unzipped, runnable directly), and `TREE.txt` (the packaged
  project tree). `--exactus`
  builds only the pyz, `--build` only `build/`, `--tree` only
  `TREE.txt`; passing all three equals passing none.
- `build/` — generated dist directory holding the `bin/exactus` zipapp
  unzipped (`exactus/` package + `__main__.py` stub; `python build/` works
  without bundling); created by `python exactus/scripts/build_make` or `python exactus/scripts/build_make --build`.
- `scripts/` — root helper scripts: `build_make/` package (artifacts),
  `package/` package (timestamped zip, ANSI `--help`), `collect/`
  (shared tree filter), and `bundle_make/` (offline
  bundle builder). See `scripts/README.md`.
- `scripts/collect/` — shared project-tree filter used by
  `exactus/scripts/package` and `exactus/scripts/build_make --tree`: prunes
  dot-folders/dotfiles, all-uppercase
  directory names, `build/`, `*.egg-info`, `__pycache__`, `exec/`,
  `packages/`, and files that are readable zip archives.
- `exactus/scripts/package` — root packaging script; each run creates a
  timestamped `packages/<ddmmyyyyHHMMSS>/` folder holding
  `<root-name>.zip` plus a generated `README.md` (instructions and the
  embedded project tree). `--output PATH` overrides the destination
  (no README is generated for custom outputs).
- `packages/` — generated archive directory holding the timestamped
  package folders; created by `python exactus/scripts/package` and itself
  excluded from packaging.
- `TREE.txt` — generated `tree`-style listing of exactly the folders
  and files `exactus/scripts/package` would zip; written by
  `python exactus/scripts/build_make --tree` (or a bare `python exactus/scripts/build_make`).
- `exactus/` — the toolkit folder:
  - `__main__.py` — internal dispatcher: tool dispatch, frontend shortcuts,
    aggregated `-h/--help`, the orchestrator (tools + pipelines,
    `EXACTUS_RESULTS/` tree, run registry, kill scripts, live progress),
    and signal-safe cleanup. `python exactus` and
    `./bin/exactus` are equivalent entrypoints.
  - `bundle/` — packaged-source fingerprints and executable freshness.
  - `server/` — loopback web-server lifecycle for the screenshot
    shortcuts (embedded `http.server` with identity ping, state files,
    port probing).
  - `tools/` — the exactus package: shared runtime (`api.py`, `catalog.py`,
    `models.py`, `registry.py`, `report_bundle.py`, `terminal.py`,
    `progress.py`, `runtime.py`, `_common.py`,
    `_entrypoint.py`, and the `common/` leaf package), the nine tool
    entrypoints (per-tool `main.py`), their cores (`core.py`), and shared report assets
    (`common/templates/`).
  - `record/` — browser recording, crawling, diagnostics, and flow replay.
    `record/studio/` hosts Flow Studio and its local browser service.
  - `screenshot/` — screenshot acquisition and similarity comparison,
    including the `js/capture_screen.js` page-side script.
  - `bundle/` — offline per-platform partitioned filesystem bundles under
    `bundle/<os>/<arch>/`
    (`data/parts/fs/catalog.json` plus immutable content-addressed packs),
    with lazy dependency-aware reconstruction and verified incremental updates;
    contains ruff, basedpyright,
    pyrefly, pytest, coverage, eslint, tsc, jslint, stylelint, htmlhint,
    prettier, node, playwright, chromium, jinja2, pillow, PyQt6, and
    PyQt6-WebEngine, used automatically when the host lacks the exactus
    tools.

## Tools

| Tool | What it exactuss |
| --- | --- |
| `lints` | Clean/fix convergence plus Ruff, BasedPyright, pyrefly, TypeScript `tsc` (strict `checkJs` over JS, honoring `jsconfig.json`/`tsconfig.json` or generating a scoped config), ESLint, stylelint, HTMLHint, and custom Python/JS/CSS/HTML checks |
| `coverage-tests` (aliases `coverage`, `tests`) | One pytest run over discovered `test_*.py` plus the `node:test` lane feeds both the combined coverage report and the per-group test reports under `EXACTUS_RESULTS/COVERAGE_TESTS/` (`COVERAGE/`, `TESTS/`, `TESTS/<group>/`, raw evidence in `ARTIFACTS/COVERAGE/` and `ARTIFACTS/TESTS/`). It validates the evidence (complete run, matching hash, `--minimum`/`--critical` floors). The run fails below 90% total coverage; override with `--fail-under PERCENT`. An optional per-file gate, `--per-file-minimum PERCENT` (80 in this repository's `pyproject.toml`), fails the run when any single source file is below it and lists those files in the report. The HTML report embeds `--context-lines N` (default 3) source lines around each uncovered run, and its "Context lines" slider chooses any value from 0 to N |
| `docs` | Python Google docstrings and JavaScript JSDoc |
| `kwargs-typehints` | Positional-call, bare-import, and explicit-type-annotation checks |
| `readme` | Per-directory README documentation inventories |
| `frontend` | Clickable-state browser capture across device/theme lanes plus console/page-error diagnostics |

## Usage

Build the standalone executable once:

```bash
python exactus/scripts/build_make            # creates bin/exactus AND build/ (unzipped pyz) AND TREE.txt
python exactus/scripts/build_make --check    # only bin/exactus
python exactus/scripts/build_make --build    # only build/
python exactus/scripts/build_make --tree     # only TREE.txt
```

Package the project into a timestamped, distributable zip:

```bash
python exactus/scripts/package                    # -> packages/<ddmmyyyyHHMMSS>/exactus.zip + README.md
python exactus/scripts/package --output dist.zip  # custom destination (no README)
```

Reports default to `<project>/EXACTUS_RESULTS/`; set `[tool.exactus] reports-dir`
to change the project-relative base folder. The exactused project is
resolved in this order:

1. `--root DIR` (or the `EXACTUS_ROOT` environment variable);
2. the project a `check` executable sits in (`<project>/check` or
   `<project>/bin/exactus`);
3. the current working directory.

`--entrypoint`/`--server` only choose which app to start; they never move
the project root.

Markdown, JSON, and web reports compare against the previous report, even
when the run cleans its output first. Comparisons include added, resolved,
and unchanged findings, deltas by source/category/rule, numeric subsection
metrics, and per-tool details in aggregate pipeline reports. Numeric deltas
use the metric's units; coverage percentages differ in percentage points.
The first run establishes a baseline. Missing historical details show `N/A`.

```bash
cd /path/to/target-project

# Aggregated help listing every tool flag
/path/to/exactus/bin/exactus       # or: ./bin/exactus, bin/exactus -h/--help

# Individual tools via --<tool> flags; each runs isolated and shows
# only its live progress bar plus the final result table (the tool's
# raw output is captured into EXACTUS_RESULTS/<TOOL>/ARTIFACTS/stdout.log
# and stderr.log, with stderr.json and the live @activity.json beside them)
/path/to/exactus/check --lints . --no-clean
/path/to/exactus/check --readme .
/path/to/exactus/check --frontend --url http://localhost:8000
/path/to/exactus/check --docs --help       # the tool's native help

# App shortcuts: --entrypoint/--server start the app and run EVERY tool
# (the unified pipeline plus frontend) against its project
/path/to/exactus/check --entrypoint ./serve.py          # all tools; free port via EXACTUS_PORT
/path/to/exactus/check --entrypoint ./serve.py --url http://localhost:8000
/path/to/exactus/check --server ./public                # serve a dir, all tools
/path/to/exactus/check --entrypoint ./serve.py --pipeline self   # another pipeline
/path/to/exactus/check --entrypoint ./serve.py --frontend-only
/path/to/exactus/check --frontend --entrypoint ./serve.py      # same: frontend only
/path/to/exactus/check --url http://localhost:8000      # existing app: frontend only
/path/to/exactus/check --server ./public --max-states 20  # extra args go to frontend
/path/to/exactus/check --root ../other-project -t lints  # exactus another project

# Orchestrator flags pass straight through to __main__.py
/path/to/exactus/check --clear             # clear EXACTUS_RESULTS, then run all
/path/to/exactus/check -t docs             # one tool via the orchestrator
/path/to/exactus/check --tools lints docs  # several tools, each with its own progress bar
/path/to/exactus/check -t readme .         # trailing args forwarded to a single tool
/path/to/exactus/check --pipeline self
/path/to/exactus/check --list-tools
/path/to/exactus/check --exclude-tools frontend
/path/to/exactus/check --kill              # terminate live run records, keep reports
/path/to/exactus/check --kill readme       # terminate only the readme tool's run
/path/to/exactus/check --kill-all          # scan every process, kill all Exactus trees

# Global file filters forwarded to every exactus tool that accepts them
/path/to/exactus/check --include 'src/**' --exclude '**/generated/**'
/path/to/exactus/check -t lints -- --include 'app/**/*.py'
```

Every long option also accepts `-` and `_` interchangeably —
`--kwargs_typehints` and `--kwargs-typehints`, `--collect_files` and
`--collect-files`, `--show_config` and `--show-config` are the same flag.
`--include GLOB` / `--exclude GLOB` are repeatable orchestrator options.
Each pair is prepended to the arguments of every tool in a pipeline (and
of a `-t` tool) **only when that tool's parser accepts the flag** — every
tool (`lints`, `coverage-tests`, `docs`, `kwargs-typehints`, `readme`, `exec`,
`frontend`) shares the common `root`/`--include`/`--exclude`
surface. Direct dispatch works too:
`./bin/exactus --lints --include 'src/**'` forwards the flag verbatim, as does
the screenshot shortcut path (`./bin/exactus --url ... --include '*.html'`).

`--server` starts a throwaway `http.server` on a free loopback port and
screenshots the served URL. A bare `--entrypoint`/`--server` keeps the app
running while the whole `unified` pipeline (or `--pipeline NAME`) runs, with
`frontend` joining the parallel wave; `--frontend-only`, an explicit
`--frontend`, or `--url` alone runs just the frontend tool. Pipelines
include `frontend` only when it receives a `--url`. `--entrypoint` runs your Python file first
(its parent directory becomes the working directory) with `EXACTUS_HOST`,
`EXACTUS_PORT`, `HOST` and `PORT` exported so the script binds a known
loopback address: the `--url` port when the URL carries one, otherwise
an assigned free port. Pass `--url` pointing at the server —
`http://` is assumed when the scheme is missing — or omit it to exactus
the assigned port. If nothing accepts connections, it exits with an
error explaining that `--url` or `--server` is needed. `--server` and
`--entrypoint` are mutually exclusive, and `--server` cannot be
combined with `--url`. Any extra flags are forwarded to the screenshot
tool. `--entrypoint`/`--server` may also follow an explicit
`--frontend` flag, which reroutes into this same shortcut flow. A second `--server` run on the same
directory reuses the surviving server — each instance answers
`GET /_exactus_check_ping` with a fixed token and records `{pid, port}`
in `~/.cache/exactus-tools/servers/<digest>.json`, so the next run adopts
it instead of stacking a duplicate. The adopted or spawned server is
terminated and its state file removed when the command exits.

`python exactus` exposes the **identical** CLI — every flag
above (`--<tool>` dispatch, `--url`/`--server`/`--entrypoint`
shortcuts, orchestrator flags, `-h` aggregated help) works there too;
`exactus/__main__.py` holds no logic of its own:

```bash
python3 /path/to/exactus/exactus                  # full `unified` pipeline
python3 /path/to/exactus/exactus --pipeline self  # lints + docs + kwargs + readme + coverage-tests
python3 /path/to/exactus/exactus -t lints         # one tool
python3 /path/to/exactus/exactus -t docs -- --fail-on error
python3 /path/to/exactus/exactus --include 'src/**' --exclude 'tests/**'
python3 /path/to/exactus/exactus --list-tools
python3 /path/to/exactus/exactus --list-pipelines
python3 /path/to/exactus/exactus --clear          # clear EXACTUS_RESULTS tree
python3 /path/to/exactus/exactus --kill           # terminate live runs, keep reports
python3 /path/to/exactus/exactus --kill_all       # kill every Exactus process found
python3 /path/to/exactus/exactus --readme .       # same as bin/exactus --readme .
python3 /path/to/exactus/exactus --server ./public
python3 -m exactus --lints .       # package entry point (package importable)
```

Every tool also runs directly, for example
`python3 exactus/tools/docs/main.py --help`.

### Shell autocomplete

The first ordinary run of `bin/exactus` automatically installs completion
for Bash, Zsh, Fish, and PowerShell user profiles. Later runs refresh it
when the bundle/catalog or launcher location changes; unchanged profiles
are left untouched. Open a new terminal or reload your profile to activate
it. Explicit management commands and TAB requests skip automatic setup.

```bash
check completion bash         # print a Bash registration script
check completion zsh          # print a Zsh registration script
check completion fish         # print a Fish registration script
check completion powershell   # print a PowerShell registration script

source <(check completion bash)      # enable for the current session
check completion all --install       # install for every supported shell
check completion all --diagnose      # verify installed registrations
check completion all --uninstall     # remove check-owned content
```

TAB completion is grammar-aware: it knows the orchestrator and tool
flags, `--tools`/`--exclude-tools` values, pipeline names, `--tool-arg`'s
`TOOL::` scopes, option `choices`, value types, mutex groups, and the
frontend-shortcut context — all derived from the real argparse
parsers, so it can never drift from the CLI.

When the target project has a virtualenv (`.venv`, `venv`, `env`, `.env`, or
any child directory with `pyvenv.cfg`) and none is already active
(`VIRTUAL_ENV`), `__main__.py` re-execs into it. A venv older than Python 3.13
cannot host the toolkit, so it is exported as `EXACTUS_PROJECT_PYTHON` and the
coverage-tests tool runs the project's tests with that interpreter instead.

## Configuration

Every tool, and `check` itself, reads `[tool.exactus]` from `pyproject.toml`.
Files are discovered by walking up from the exactused project; every file with
a `[tool.exactus]` table is loaded, the nearest wins, and `root = true` stops
the walk. Keys are the tool's own long flags without the dashes
(`fail-under` is `--fail-under`).

```toml
[tool.exactus]
reports-dir = "EXACTUS_RESULTS"  # project-relative base reports folder
root = true                  # stop discovery here
entrypoint = "demo/server.py"  # check: same as --entrypoint (pipeline runs only)
clear = true                 # check: same as --clear
exclude = ["build/**"]       # forwarded to every tool that accepts it
context-lines = 3            # every tool: source lines around finding lines

[tool.exactus.coverage-tests]  # one table per tool id
fail-under = 90
per-file-minimum = 80        # optional per-file gate
context-lines = 3            # this tool only: overrides [tool.exactus]

[tool.exactus.pipeline.self]   # one table per pipeline
exclude-tools = ["frontend"]

[tool.exactus.pipeline.self.docs]  # a tool inside one pipeline only
fail-on = "error"
```

Priority, highest first: CLI tool flags and `--tool-arg`, then common CLI
flags (`--include`, `--exclude`), `[tool.exactus.pipeline.<id>.<tool>]`,
`[tool.exactus.<tool>]`, common keys in `[tool.exactus]`, the catalog pipeline
preset, and finally each tool's built-in defaults. Scalars and booleans are
overridden by the higher layer; lists combine (config entries first).
`entrypoint`/`server`/`url` are not injected when a tool is selected with
`-t` or the command line already names a server. Paths resolve relative to
the file that sets them. Invalid TOML, unknown tables or keys, and wrong
value types stop the run with exit status 2.

The former `[tool.exactus.coverage]` table still configures `coverage-tests`
as a fallback: a key set in `[tool.exactus.coverage-tests]` wins, a key set
only in `[tool.exactus.coverage]` still applies (the same holds inside
`[tool.exactus.pipeline.<id>]`).

`--context-lines N` (default 3) is a common tool option: `exec`, `readme`,
`lints` and `docs` store an `excerpt` (the finding line plus up to N
lines on each side, read only inside the project root) on every finding
with a path and a line, shown as a numbered block in `result.md` and in the
web report's snippet viewer.

- `--config FILE` loads exactly one file; `--no-config` ignores all of them
  (both are exported to workers as `EXACTUS_CONFIG`).
- `--show-config [-t NAME... | --pipeline NAME]` prints every option with
  the layer that set it and exits; tokens after `--` count as CLI options.
- Standalone tools (`python exactus/tools/docs/main.py`) read the same files.

## Pipelines

- `self` — lints, then coverage-tests/docs/kwargs-typehints/readme in
  parallel.
- `check` / `unified` — lints first, then every other tool in parallel,
  with `readme` last and `performance` after that to export the
  `EXACTUS_RESULTS/PERFORMANCE` dashboard from the collected step traces.
- `all-fast` (`fast`) — same tools, lints in read-only mode, clears
  `EXACTUS_RESULTS/` first.

## Requirements

- Python 3.13+.
- `lints` honors the project's own configuration: Ruff keeps the rule
  selection from `ruff.toml`, `.ruff.toml` or `[tool.ruff]` (strict
  `--select ALL` only for unconfigured projects), ESLint/Stylelint use
  project configs before the bundled templates, and TypeScript uses the
  project `jsconfig.json`/`tsconfig.json` or a generated
  `.exactus_tsconfig.json` scoped to the exactused files.
- `lints` uses whatever it finds: `EXACTUS_LINTER_TOOLCHAIN` env var or
  `--toolchain` for a bundled ruff+basedpyright binary, otherwise `ruff`,
  `basedpyright`, `pyrefly`, `eslint`, `tsc` (TypeScript), `stylelint`,
  `htmlhint` on `PATH` (it can auto-install them unless
  `--read-only`/`--no-install-tools`).
- `coverage-tests` needs `pytest` + `coverage` importable in the active
  env. It
  measures `src/` when present, otherwise the project root (or pass
  `--source-root`). JavaScript tests are any `*.test.*`, `*.spec.*` or
  `*_test.*` file in the project that imports `node:test`.
- `docs` shells out to `node --check` for JSDoc validation unless
  `--no-js-check`.

## Environment variables

`EXACTUS_*` names control the runtime (`EXACTUS_ORCHESTRATED`, `EXACTUS_RUN_ID`,
`EXACTUS_PIPELINE_RUN_ID`, `EXACTUS_CONFIG`, `EXACTUS_REPORT_OUTPUT`, `EXACTUS_PROGRESS_PATH`,
`EXACTUS_TOOL`, `EXACTUS_REGISTRY`) and `EXACTUS_LINTER_TOOLCHAIN` points at a
bundled linter binary. All are optional; `__main__.py` sets them as needed.

## Debug capture

A `DEBUG.txt` marker at the exactused project root makes `sprint` calls append
capture records — see `exactus/tools/common/sprint.py` for the directive syntax.

[Implementation and acceptance queue](exactus/docs/todo/TODO.md).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`AGENTS.md`](AGENTS.md) — Provide AGENTS md content.
- [`MANIFEST.in`](MANIFEST.in) — Provide MANIFEST in content.
- [`TREE.txt`](TREE.txt) — Provide TREE txt content.
- [`config.json.example`](config.json.example) — Provide config.json example content.
- [`eslint.config.mjs`](eslint.config.mjs) — ", "*
- [`flows.pwflow.json`](flows.pwflow.json) — Provide flows.pwflow json content.
- [`jsconfig.json`](jsconfig.json) — Provide jsconfig json content.
- [`package-lock.json`](package-lock.json) — Provide package lock json content.
- [`package.json`](package.json) — Provide package json content.
- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.
- [`stylelint.config.mjs`](stylelint.config.mjs) — ", "*
- [`uv.lock`](uv.lock) — Provide uv lock content.

### Subdirectories

- [`ALL_LINTS_RESULTS/`](ALL_LINTS_RESULTS/README.md) — No direct files besides this README.
- [`EXACTUS_RESULTS_RELEASE/`](EXACTUS_RESULTS_RELEASE/README.md) — No direct files besides this README.
- [`STUDIO_SCREENSHOTS/`](STUDIO_SCREENSHOTS/README.md) — Provide 01 welcome png content.
- [`bin/`](bin/README.md) — Project executables and native tool archives.
- [`demo/`](demo/README.md) — This fixture exercises the relocatable `exec/exactus` artifact with Python, JavaScript, CSS, HTML, Python tests, JavaScript tests, browser diagnostics and server diagnostics.
- [`dev/`](dev/README.md) — Provide README txt content.
- [`docs/`](docs/README.md) — Provide 13 selector authoring detail png content.
- [`exactus/`](exactus/README.md) — Self-contained exactus package. The inventory below documents every direct file and child directory.
- [`packages/`](packages/README.md) — Generated archive directory.
- [`zip-components/`](zip-components/README.md) — Archives produced by `exactus.packages.zip_components` (`python exactus/packages/zip_components …`).

<!-- exactus:inventory:end -->
