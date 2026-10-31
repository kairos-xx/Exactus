# tools/self_test/

The executable's self-diagnostic catalog tool, exposed as
`exactus --self_test`. The flag is hidden on normal builds; only
executables built with `--build-self-test` carry the marker that
enables it.

## Files

| File | Description |
|---|---|
| `arguments.py` | The self_test grammar, declared without importing the execution engine. |
| `main.py` | Probe every tool reachable by this exactus and report the results: generates a minimal fixture project in a temporary directory, checks each expected tool twice over — system executables on `PATH` first, the pyz's bundled toolchain as fallback — then runs the `unified` pipeline against the fixture and requires every `EXACTUS_RESULTS` report to be fresh, PASS and issue-free. |

## Behavior

- The fixture — one HTML, JS, CSS, Python, pytest and JS-test file plus
  a `pyproject.toml` — lives inside a temporary directory; the only
  artifact left behind is the standard `EXACTUS_RESULTS/SELF_TEST`
  report bundle.
- Each probe records which source answered (`system`, `bundle` or
  `none`), so the diagnostic is valid on a bare `python:3.13-slim`
  container, a development machine with a full toolchain, and anything
  in between.
- A loopback-only static site ungates `frontend`, `record` and
  `visual_cause` inside the fixture, so no network access is needed.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Self-test exactus tool. |
| `arguments.py` | Declare the self_test grammar without importing its engine. |
| `main.py` | Probe every tool reachable by this exactus and report the results. |
| `py.typed` | PEP 561 marker declaring that the package ships inline type annotations. |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Self-test exactus tool.


### `arguments.py`

Declare the self_test grammar without importing its engine.

- `create_parser() -> ArgumentParser` — Create parser.

### `main.py`

Probe every tool reachable by this exactus and report the results.

- `class Constants` — Group module-level constants.
  - `cache_root` = `Path(environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'exactus-to...`
  - `probe_args` = `(('--version',), ('--help',), ('-h',), ())`
  - `tool_probes` = `{'basedpyright-langserver': ((), 'Connection input stream is not set'), '...`
  - `expected_tools` = `frozenset({'basedpyright', 'build', 'coverage', 'eslint', 'exactus-mcp',...`
  - `browser_names` = `frozenset({'chrome', 'Chromium', 'Google Chrome', 'Google Chrome for Test...`
  - `host_browsers` = `('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applic...`
  - `windows_browsers` = `('Google/Chrome/Application/chrome.exe', 'Chromium/Application/chrome.exe')`
  - `browser_envs` = `('CHROME_PATH', 'CHROMIUM_PATH', 'CHROME_BIN', 'PUPPETEER_EXECUTABLE_PATH...`
  - `system_browsers` = `('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable',...`
  - `reports` = `('COVERAGE_TESTS', 'DOCS', 'FRONTEND', 'KWARGS_TYPEHINTS', 'LINTS', 'PERF...`
  - `gated_reports` = `frozenset({'FRONTEND', 'RECORD', 'VISUAL_CAUSE'})`
  - `run_scoped_env` = `frozenset({'EXACTUS_COLLECT_FILES', 'EXACTUS_COMPARISON_BASELINE', 'EXACT...`
  - `run_scoped_prefixes` = `('EXACTUS_ACTION__', 'EXACTUS_ES__', 'EXACTUS_RECORDER_FLUSH__', 'EXACTUS...`
  - `fixture` = `{'pyproject.toml': dedent(text='\n            [project]\n            name...`
  - `site_pages` = `{'index.html': dedent(text='\n                <!doctype html>\n...`
- `say(*, text: str) -> None` — Write one report line to standard output.
- `self_command(*arguments: str) -> list[str]` — Build a command that re-invokes this exactus.
- `bundle_launcher() -> Path | None` — Return the current context's bundle dispatch launcher.
- `bundle_command(*arguments: str) -> list[str] | None` — Build a command that dispatches a bundled third-party tool.
- `subprocess_env() -> dict[str, str] | None` — Return the environment self-test subprocesses must inherit.
- `pipeline_env() -> dict[str, str]` — Return the nested pipeline's environment with a fresh context.
- `describe_command(*, command: list[str], timeout: int=120, cwd: Path | None=None, marker: str='') -> tuple[bool, str]` — Run one command and report its outcome.
- `describe(*arguments: str, timeout: int=120) -> tuple[bool, str]` — Re-invoke this exactus with ``arguments`` and report the outcome.
- `describe_bundle(*arguments: str, timeout: int=120, cwd: Path | None=None, marker: str='') -> tuple[bool, str]` — Dispatch a bundled third-party tool and report its outcome.
- `probe_tool(*, tool: str) -> tuple[bool, str, str]` — Probe one tool, system executable first, bundle as fallback.
- `probe_chromium() -> tuple[bool, str, str]` — Launch a Chromium binary — system first, then the bundle's.
- `browser_candidates() -> Iterable[Path]` — Yield configured and conventional browser paths.
- `host_browsers() -> Iterable[Path]` — Yield well-known browser install locations on this host.
- `playwright_browsers() -> Path | None` — Resolve the host's Playwright browsers directory.
- `serve_display() -> Popen[bytes] | None` — Start a virtual X display for headed browser tools.
- `free_port() -> int` — Reserve an ephemeral loopback port for the demo site.
- `serve_site(*, directory: Path, port: int) -> Popen[bytes]` — Publish a clean two-page site for the url-gated tools.
- `stop_process(*, process: Popen[bytes]) -> int | None` — Terminate one helper process, escalating to ``kill``.
- `write_fixture(*, project: Path) -> None` — Generate the seven-file fixture project in ``project``.
- `probe_pipeline(*, checks: Checks, project: Path, url: str | None, log: Path) -> tuple[bool, str]` — Run the unified pipeline against the fixture project.
- `probe_report(*, project: Path, relative: str, started: float) -> tuple[bool, str, dict[str, JsonValue]]` — Check one generated report for freshness and zero issues.
- `class Checks` — Accumulate structured check outcomes for the report.
  - `entries` = `field(default_factory=list)`
  - `failed` = `field(default_factory=list)`
  - `skipped` = `field(default_factory=list)`
  - `planned` = `len(Constants.expected_tools) + len(Constants.reports) + 5`
  - `note(self, *, kind: str, name: str, status: str, reason: str='', detail: dict[str, JsonValue] | None=None) -> None` — Print one result line and record it for the report.
  - `pulse(self, *, step: str) -> None` — Re-emit the current counts so the bar still advances.
- `bundle_tools() -> list[str] | None` — List the tools declared by the materialized bundle.
- `probe_tools(*, checks: Checks) -> list[str]` — Probe every expected tool and record per-source outcomes.
- `run_checks(*, checks: Checks, project: Path, artifacts: Path) -> None` — Run every check, recording outcomes instead of exiting.
- `create_parser() -> ArgumentParser` — Return the shared CLI grammar used by execution and completion.
- `parse_args(*, arguments: tuple[str, ...] | None=None) -> Namespace` — Parse args.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Generate the fixture, probe every tool, and emit the report.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`project_python`](../../packages/project_python/DOCS.md), [`steps`](../../packages/steps/DOCS.md), [`common`](../common/DOCS.md), [`reports`](../reports/DOCS.md)
- Used by: `__main__.py`, `tests/tools/test_self_test.py`

<!-- exactus:reference:end -->
