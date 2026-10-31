# tests/

The Exactus test suite: Python (pytest) and JavaScript (Node test
runner, shared Playwright harness) coverage mirroring `exactus/packages/`
and `exactus/tools/`.

## Files

| File | Description |
|---|---|
| `conftest.py` | Shared pytest fixtures and interpreter/path setup for the whole suite. |

## Groups

| Directory | What it verifies |
|---|---|
| `bundle/` | The small runtime layer that locates and exposes the generated platform bundle — repository-root discovery, deterministic source-tree signatures, stale-bundle warnings, host/architecture candidate selection on Linux (glibc and musl), macOS and Windows, and bundle entry-point dispatch. |
| `common/` | Contracts shared across packages, tools, command-line entry points and the test infrastructure itself: typed assertion helpers, check-command parsing/reporting, example-package contracts, JSON serialization, and package-independence rules. |
| `demo/` | The demonstrator application as a real HTTP server and as browser-side JavaScript: state transitions, static assets, error conversion, CLI lifetime and rendered DOM behavior. |
| `packages/` | One directory per `exactus/packages/` package — public API, CLI and examples as applicable, plus failure and lifecycle behavior. `test_packages.py` checks the package collection itself. |
| `standalone/` | Hermetic end-to-end audit: a resolved `exactus` executable (installed or rebuilt from `bin/release` when stale) runs over the self-contained `project/` fixture and asserts the `EXACTUS_RESULTS` reports are produced. |
| `tools/` | One directory per `exactus/tools/` tool — normalized report envelopes, findings, templates, CLI wiring and fix-mode behavior. |

## Behavior

- Python suites use temporary directories and injected platform/process
  boundaries so runs stay reproducible and never depend on the
  machine's installed bundle or developer state.
- JavaScript suites use Node's test runner and, where a real DOM is
  required, the shared Playwright harness (`common/browser.mjs`), which
  starts fixtures, opens pages and supplies deterministic cleanup.
- The coverage command also discovers package-owned `.test.mjs` files
  and combines their V8 coverage with Python coverage.
- Run everything with `python -m pytest exactus/tests`, or a single
  group with `python -m pytest exactus/tests/<group>`; browser suites
  run via `node --test`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Package marker. |
| `bundle/` | Subdirectory. |
| `common/` | Subdirectory. |
| `conftest.py` | Shared pytest fixtures for the toolkit tests. |
| `demo/` | Subdirectory. |
| `packages/` | Subdirectory. |
| `standalone/` | Subdirectory. |
| `tools/` | Subdirectory. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `source` |  | metavar='FILE' |
| `--verbose` | Explain | action='store_true' |
| `--mode` |  | choices=('fast', 'safe'), default='safe', required=True |
| `--pair` |  | nargs=2, metavar=('KEY', 'VALUE') |
| `--foo-bar` |  | action='store_true' |
| `--baz-qux` |  |  |
| `--dry` |  | action='store_true' |
| `pos` |  | nargs='?' |
| `--a-b` |  | dest='dashed', action='store_true' |
| `--a_b` |  | dest='underscored', action='store_true' |
| `--no-cache` |  | action='store_true' |
| `--one` |  |  |
| `--maybe` |  | nargs='?' |
| `--any` |  | nargs='*' |
| `--some` |  | nargs='+' |
| `--flag` |  | action='store_true' |
| `--mode` |  | choices=('fast', 'slow') |
| `--left` |  | action='store_true' |
| `--right` |  | action='store_true' |
| `--tag` |  | action='append' |
| `--secret` | SUPPRESS |  |
| `target` |  | metavar='TARGET' |
| `rest` |  | nargs='*' |
| `--file` |  | metavar='FILE' |
| `--dir` |  | metavar='DIR' |
| `--path` |  | type=Path |
| `--thing` |  | metavar='FILE' |
| `-v, --verbose` |  | action='store_true' |
| `--output` |  |  |
| `-o, --output` |  | metavar='PATH' |
| `root` |  |  |
| `-o, --output` |  | metavar='PATH' |
| `root` |  |  |
| `source` | Asset source |  |
| `-o, --output` | Destination | metavar='PATH' |
| `--verbose` | More details | action='store_true' |
| `pos` | positional |  |
| `-o, --out` | opt | metavar='P' |
| `--flag` |  | action='store_true' |
| `-o, --out` |  | metavar='P' |
| `--fail-under` |  | type=float |
| `--no-branch` |  | action='store_true' |
| `--quiet` |  | action='store_true' |
| `--pytest-arg` |  | action='append', default=[] |
| `--jobs` |  | type=int |
| `--include` |  | action='append', default=[] |
| `--output-dir` |  | type=Path, default=Path('EXACTUS_RESULTS/DEMO') |
| `--actions` |  |  |
| `--workspace` |  |  |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Package marker.


### `bundle/__init__.py`

Test bundle freshness and packaging helpers.


### `bundle/test_freshness.py`

Staleness detection for the packaged ``exactus`` executable.

- `test_dev_project_root_detects_repository(tmp_path: Path) -> None` — A bundle one level below the repository root resolves it.
- `test_dev_project_root_detects_release_layout(tmp_path: Path) -> None` — Platform release dirs resolve the root two levels up.
- `test_dev_project_root_rejects_foreign_layout(tmp_path: Path) -> None` — A bundle without the build markers is not a dev checkout.
- `test_tree_signature_fingerprints_sources(tmp_path: Path) -> None` — Source files hash; caches, dotfiles, and the stamp skip.
- `test_bundle_signature_round_trip(tmp_path: Path) -> None` — A stamped bundle returns the exact fingerprint mapping.
- `test_tree_signature_skips_generated_reports(tmp_path: Path) -> None` — ``EXACTUS_RESULTS`` trees never enter the fingerprint.
- `test_bundle_signature_absent(tmp_path: Path) -> None` — Bundles predating stamping report ``None``.
- `test_warn_if_stale_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An unchanged project produces no output.
- `test_warn_if_stale_after_source_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Editing a packaged source after the build warns.
- `test_warn_if_stale_after_source_addition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Adding a packaged source file after the build warns.
- `test_warn_if_stale_missing_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A dev-project bundle without a stamp is treated as outdated.
- `test_warn_if_stale_outside_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A distributed bundle outside the dev project stays silent.
- `test_warn_if_stale_script_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Non-zipapp entry points are ignored.
- `test_warn_if_stale_extra_payload_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Source partition payloads absent from the bundle do not warn.
- `test_bundle_stale_ignores_staged_vendor(tmp_path: Path) -> None` — Staged-only ``vendor/`` shims absent from sources stay fresh.
- `test_bundle_stale_flags_every_drift(tmp_path: Path) -> None` — ``bundle_stale`` reports additions, edits, and missing stamps.
- `test_render_signature_deterministic(tmp_path: Path) -> None` — Signature JSON is stable for identical trees.

### `bundle/test_host.py`

Host routing and package dispatch for the bundled executables.

- `test_host_leaf_candidates(monkeypatch: pytest.MonkeyPatch, operating_system: str, architecture: str, *, musl: bool, expected: tuple[tuple[str, ...], ...]) -> None` — Normalize supported host names and reject unsupported combinations.
- `test_host_leaf_uses_existing_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Select the first existing candidate and derive its package name.
- `test_lazy_import_and_missing_attribute(monkeypatch: pytest.MonkeyPatch) -> None` — Cache a host module while translating only its own absence.
- `test_bundle_main_missing_and_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject a missing launcher and forward arguments and status otherwise.
- `test_dir_includes_host_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Expose host leaf modules and packages to introspection.

### `common/__init__.py`

Shared test helpers, pytest fixtures and the Playwright harness.


### `common/check/__init__.py`

Test the top-level exactus check CLI.


### `common/check/test_check_cli.py`

The ``check`` orchestrator driven in-process with isolated global state.

- `test_help_and_listings(capsys: pytest.CaptureFixture[str]) -> None` — Help text and catalog listings are rendered.
- `test_tool_help_and_unknown(capsys: pytest.CaptureFixture[str]) -> None` — Per-tool help exits cleanly and unknown tools are rejected.
- `test_run_single_tool(sample_project: Path) -> None` — A tool flag runs the analyzer and writes reports in the project.
- `test_orchestrator_tools_and_clear(sample_project: Path) -> None` — The orchestrator runs selected tools and clears results.
- `test_orchestrator_pipeline_with_exclusions(sample_project: Path) -> None` — A pipeline runs in waves honoring excluded tools.
- `test_orchestrator_bad_selections(sample_project: Path) -> None` — Invalid tool and pipeline names produce errors.
- `test_extract_root_forms() -> None` — Both ``--root DIR`` and ``--root=DIR`` are removed from argv.
- `test_application_class_constants() -> None` — Tool dispatch flags stay disjoint from help flags.
- `test_bundled_runtime_detects_zipapp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A zipapp ``argv[0]`` marks the bundled runtime.
- `test_bundled_runtime_rejects_source_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Directories, plain scripts, and misses are not bundled.
- `test_bundled_runtime_resolves_path_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A bare command name resolves through ``PATH``.
- `test_bundled_tools_omit_self_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A default build hides the self-diagnostic tool.
- `test_bundled_optin_keeps_self_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A ``--build-self-test`` build keeps the diagnostic tool.
- `test_source_tools_keep_self_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Source checkouts keep the self-diagnostic tool.
- `test_bundled_rejects_self_test_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--self_test`` is an unknown flag on a default build.
- `test_bundled_optin_accepts_self_test_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--self_test`` dispatches on an opt-in build.
- `test_self_test_dash_flag_dispatches(monkeypatch: pytest.MonkeyPatch) -> None` — ``--self-test`` dispatches to ``self_test`` like ``--self_test``.
- `test_bundled_rejects_self_test_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``-t self_test`` is refused on a default build.
- `test_bundled_optin_accepts_self_test_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``-t self_test`` is accepted on an opt-in build.
- `test_bundled_pipeline_excludes_self_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Pipelines drop ``self_test`` on a default build.
- `test_kill_dispatches_run_tools(monkeypatch: pytest.MonkeyPatch) -> None` — Bare ``--kill`` terminates every live run and exits.
- `test_kill_named_and_unknown(monkeypatch: pytest.MonkeyPatch) -> None` — ``--kill NAME`` scopes termination and rejects unknown names.
- `test_kill_all_dispatches_scanner(monkeypatch: pytest.MonkeyPatch) -> None` — ``--kill-all`` and ``--kill_all`` run the global scan once.
- `test_kill_all_terminates_verified_and_leftovers(monkeypatch: pytest.MonkeyPatch) -> None` — Global kill verifies identities then sweeps leftovers.
- `test_exactus_processes_heuristic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The leftover scan matches Exactus processes, not lookalikes.

### `common/check/test_check_extra.py`

Orchestrator internals: signals, clearing, registry and unified refresh.

- `test_unified_aggregate_refreshes_after_single_tool(sample_project: Path) -> None` — A tool run after ``unified`` rewrites the stored aggregate.
- `test_signal_guard_sets_interrupt_flag() -> None` — A termination signal flips the cooperative interrupt flag.
- `test_terminate_run_tools_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Live registered runs are signalled by output or pipeline.
- `test_clear_variants(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None` — Clearing handles tools, pipelines, folders and debug capture.
- `test_pipeline_clear_preserves_tool_outputs_until_workers_start(tmp_path: Path) -> None` — Pipeline preparation clears its report without clearing tool reports.
- `test_debug_clear_refuses_dangerous_targets(tmp_path: Path) -> None` — Project root, filesystem root and home are never emptied.
- `test_force_remove_handles_enotempty(tmp_path: Path) -> None` — Racing writers leave directories that a second walk removes.
- `test_bad_tool_arg_is_usage_error(sample_project: Path) -> None` — Malformed ``--tool-arg`` values exit with status 2.
- `test_no_server_error_and_unknown_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without any URL or server the user gets guidance.
- `test_pipeline_interrupted_before_start(sample_project: Path) -> None` — A pending interrupt synthesizes INTERRUPT results for every tool.
- `test_clear_preserves_report_history(tmp_path: Path) -> None` — Clear generated output while retaining recoverable report history.
- `test_debug_output_resolves_relative_save_directives(tmp_path: Path, directive: str, folder: str) -> None` — Resolve folder and file directives relative to the selected project.
- `test_config_arguments_preserve_tool_operands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: tuple[str, ...], remaining: tuple[str, ...], *, disabled: bool | None) -> None` — Consume global config flags without swallowing tool arguments.

### `common/check/test_check_more.py`

Venv discovery, shortcut servers, and unified pipeline runs.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `demo` = `root / 'demo'`
  - `reshebang` = `staticmethod(Check.venv_reexec)`
- `test_project_interpreter_discovery(tmp_path: Path) -> None` — Conventional and arbitrary venv names are discovered.
- `test_venv_version_parsing(tmp_path: Path) -> None` — Versions come from pyvenv.cfg when parseable.
- `test_venv_reexec_old_python_exports_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An outdated project venv is exported for test subprocesses.
- `test_venv_reexec_embedded_and_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Embedded use and an active venv never re-exec.
- `test_venv_reexec_spawns_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — When run as the script itself, the venv interpreter is executed.
- `test_clear_conflict_copies(tmp_path: Path) -> None` — Numbered duplicates of artifacts are removed.
- `test_unified_pipeline_subset(sample_project: Path) -> None` — The unified pipeline publishes its aggregate activity report.
- `test_frontend_navigation_through_local_server(sample_project: Path, demo_url: str) -> None` — The frontend selector navigates to an explicitly managed local server.
- `test_application_startup_requires_actions() -> None` — Reject removed application startup shortcuts.
- `test_history_backups_survive_cleanup_and_clear(tmp_path: Path) -> None` — Generated output cleanup preserves every archived backup byte.

### `common/check/test_check_units.py`

Focused unit coverage for the bundled CLI model and presentation helpers.

- `test_default_root_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Prefer the environment, then a packaged launcher, then the cwd.
- `test_tool_and_terminal_properties(monkeypatch: pytest.MonkeyPatch) -> None` — Create fresh parsers and apply styles only on capable terminals.
- `test_help_renderer_extracts_argument_metadata() -> None` — Render positional, optional, repeated, required and choice metadata.
- `test_completion_dispatches_without_running_tools(monkeypatch: pytest.MonkeyPatch) -> None` — Route protocol and installer commands before normal initialization.

### `common/check/test_misc_entrypoints.py`

Thin dispatch modules and path-plumbing files.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
- `test_package_entrypoint_owns_dispatcher() -> None` — The package entrypoint owns the CLI implementation directly.
- `test_module_runs_as_script() -> None` — Executing the module as ``__main__`` exits via the dispatcher.
- `test_loose_script_bootstrap(module: str) -> None` — Loose-script execution reinserts the repository root into ``sys.path``.

### `common/check/test_public_api.py`

The package facade is the controlled public API surface.

- `class Constants` — Group module-level constants.
  - `exactus` = `import_module(name='exactus')`
- `test_exports_match_catalog() -> None` — ``exactus.__all__`` is exactly the catalog's tool identifiers.
- `test_exports_are_real_callables() -> None` — Every facade export is a real function defined in the package.
- `test_exports_delegate_to_tool_mains() -> None` — Each export pipes to its ``exactus.tools.<name>.main`` module.
- `test_exports_call_tool_mains(monkeypatch: pytest.MonkeyPatch) -> None` — Each facade function calls its tool's ``main`` with the arguments.
- `test_internals_stay_private() -> None` — Tool internals are not re-exported through the package dict.

### `common/contracts/__init__.py`

Tests of repository-wide structural contracts.


### `common/contracts/test_examples_contract.py`

Enforce the runnable package contract for source-owned examples.

- `test_every_example_directory_is_a_runnable_package(filename: str) -> None` — Every source example exposes each standard package entry point.
- `test_every_example_run_script_is_executable() -> None` — Every source example supports direct executable invocation.

### `common/json_serializers/__init__.py`

Test cross-subsystem JSON serializer contracts.


### `common/json_serializers/test_json_serializers.py`

Round-trip JSON reports through every subsystem serializer.

- `class Constants` — Group module-level constants.
  - `modules` = `('exactus.tools.actions.json_types', 'exactus.packages.completion.json_ty...`
- `test_report_serializer_preserves_unicode_and_nested_values(module: str) -> None` — Keep diagnostics, booleans, null responses and Unicode unchanged.

### `common/package/__init__.py`

Test package independence and boundary rules.


### `common/package/test_no_bare_imports.py`

No exactus tool module imports a sibling through a bare module name.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `tools` = `root / 'exactus' / 'tools'`
  - `siblings` = `frozenset((path.stem for path in tools.rglob(pattern='*.py')))`
- `test_no_bare_sibling_imports() -> None` — ``from _common import x`` style imports are forbidden.

### `common/package/test_package_independence.py`

Enforce reusable package boundaries and approved integrations.

- `class Constants` — Group module-level constants.
  - `repo` = `Path(__file__).resolve().parents[4]`
  - `packages` = `('exactus/packages/completion', 'exactus/packages/markdown', 'exactus/pac...`
  - `common` = `'exactus.tools.common'`
  - `common_dependencies` = `('exactus.tools.common.process_layer', 'exactus.tools.common', 'exactus.t...`
  - `package_dependencies` = `{'exactus/packages/completion': ('exactus.packages.argument_parser',), 'e...`
- `test_packages_are_self_contained(folder: str) -> None` — Exactus packages never reach back into the project itself.
- `test_suite_tools_skip_build_scripts() -> None` — Runtime suite modules never depend on the project build scripts.
- `test_tools_common_imports_only_itself() -> None` — ``exactus.tools.common`` only touches markdown/reports helpers.

### `common/support.py`

Typed assertion, reflection and fixture helpers shared by the suite.

- `fail(*, message: str) -> NoReturn` — Fail the running test.
- `expect_true(*, condition: bool, message: str='') -> None` — Require ``condition`` to hold.
- `expect_false(*, condition: bool, message: str='') -> None` — Require ``condition`` not to hold.
- `expect_equal(*, actual: object, expected: object) -> None` — Require two values to compare equal.
- `expect_not_equal(*, actual: object, expected: object) -> None` — Require two values to compare unequal.
- `expect_in(*, member: object, container: Container[object]) -> None` — Require ``member`` to be contained in ``container``.
- `expect_not_in(*, member: object, container: Container[object]) -> None` — Require ``member`` to be absent from ``container``.
- `expect_none(*, value: object) -> None` — Require ``value`` to be ``None``.
- `require(*, value: T | None) -> T` — Require ``value`` to be present and return it narrowed.
- `require_type(*, value: object, kind: type[T]) -> T` — Require ``value`` to be an instance of ``kind`` and return it.
- `private(*, owner: object, name: str) -> object` — Read a non-public attribute of ``owner`` by name.
- `private_call(*, owner: object, name: str, **arguments: object) -> object` — Call a non-public callable of ``owner`` with keyword arguments.
- `set_private(*, owner: object, name: str, value: object) -> None` — Assign a non-public attribute of ``owner`` by name.
- `private_clear(*, owner: object, name: str) -> None` — Empty a non-public mapping or collection held by ``owner``.
- `private_as(*, owner: object, name: str, kind: type[T]) -> T` — Read a non-public attribute of ``owner`` as an instance of ``kind``.
- `class Constant` — Callable stand-in that ignores its arguments and returns one value.
  - `__init__(self, *, value: T) -> None` — Store the value every call returns.
- `private_result(*, owner: object, name: str, kind: type[T], **arguments: object) -> T` — Call a non-public callable of ``owner`` and type its result.
- `dig(*, document: object, path: tuple[str | int, ...]) -> object` — Walk a decoded JSON document along ``path``.
- `dig_list(*, document: object, path: tuple[str | int, ...]) -> list[object]` — Walk a decoded JSON document to a list.
- `stamped_markdown(*, model: dict[str, JsonValue], tool_dir: Path, base: Path) -> str` — Render ``model`` exactly as the entrypoint stamps ``result.md``.

### `common/test_support.py`

The shared assertion and reflection helpers fail loudly when violated.

- `test_helpers_pass_on_valid_input() -> None` — Valid expectations return without raising.
- `test_helpers_raise_on_violations() -> None` — Each helper reports a violated expectation.

### `conftest.py`

Shared pytest fixtures for the toolkit tests.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[2]`
  - `excludes` = `('EXACTUS_RESULTS/**', 'build/**', 'exec/**', 'packages/**', 'exactus/rec...`
  - `signals` = `tuple((Signals[name] for name in ('SIGHUP', 'SIGINT', 'SIGTERM', 'SIGQUIT...`
- `repo_args() -> tuple[str, ...]` — Return the root plus exclusion arguments for self-exactuss.
- `sample_project(tmp_path: Path) -> Path` — Create a small Python/JS/CSS/HTML project with known defects.
- `defect_project(tmp_path: Path) -> Path` — Create a project packed with lint-worthy Python, JS, CSS and HTML.
- `isolated_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]` — Restore every piece of global state the orchestrator mutates.
- `demo_url() -> Iterator[str]` — Serve the demo static site on an ephemeral loopback port.
- `echo_url() -> Iterator[str]` — Serve the echo handler on a free loopback port.

### `demo/__init__.py`

Tests of the root `demo/` fixture.


### `demo/test_server.py`

Executable Python tests for the demo fixture.

- `class Constants` — Group module-level constants.
  - `server_script` = `next((parent / 'demo' / 'server.py' for parent in Path(__file__).resolve(...`
- `class DemoLogicTest` — Validate pure Python behavior through the bundled pytest runner.
  - `test_ready_becomes_active(self) -> None` — A ready state becomes active.
  - `test_active_becomes_ready(self) -> None` — A non-ready state becomes ready.
- `class DemoServerTest` — Exercise the demo HTTP server over real loopback requests.
  - `setUp(self) -> None` — Start a throwaway server on a free loopback port.
  - `tearDown(self) -> None` — Stop the throwaway server.
  - `test_error_status_is_internal_server_error(self) -> None` — The intentional failure uses HTTP 500.
  - `test_api_error_returns_500(self) -> None` — The intentional endpoint fails with a plain-text body.
  - `test_repeated_error_request_succeeds(self) -> None` — Emit the diagnostic once across requests to the same server.
  - `test_static_request_is_served(self) -> None` — Other GET requests fall through to static file serving.
  - `test_unsupported_method_is_rejected(self) -> None` — Only GET is mapped; other methods are not implemented.
- `class DemoCliTest` — Validate the server entrypoint without binding a real port.
  - `test_parser_honors_exactus_environment(self) -> None` — ``EXACTUS_HOST``/``EXACTUS_PORT`` provide the defaults.
  - `test_main_serves_until_interrupted(self) -> None` — ``main`` announces the URL and closes the server on Ctrl-C.
  - `test_script_exits_with_main_status(self) -> None` — Running the file as a script exits with ``main``'s status.

### `packages/__init__.py`

Package marker.


### `packages/actions/__init__.py`

Tests of ``exactus/packages/actions``.


### `packages/actions/action_javascript/__init__.py`

Tests of ``exactus/packages/actions/action_javascript``.


### `packages/actions/action_javascript/test_examples.py`

Coverage for the JavaScript runner widget demo server launcher.

- `class Constants` — Group module-level constants.
  - `root` = `Path(run.__file__).resolve().parents[3]`
  - `assets` = `('actions/action_javascript/examples/web/index.html', 'actions/action_jav...`
- `test_demo_assets_exist() -> None` — Every file the demo page loads is present beside the launcher.
- `test_start_demo_reuses_a_recorded_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A recorded server short-circuits the spawn path.
- `test_start_demo_spawns_and_waits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A fresh spawn waits for readiness and returns the demo URL.
- `test_start_demo_replaces_unready_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate and clear a spawned server that never answers.
- `test_main_prints_url_and_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None` — Print the demo URL and hand it to the system browser.
- `test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the examples module forwards to ``run.main``.

### `packages/actions/action_pointer/__init__.py`

Test the shared pointer and touch action frontend.


### `packages/actions/action_pointer/test_examples.py`

Coverage for the pointer-action demo launcher.

- `class Constants` — Group module-level constants.
  - `root` = `Path(run.__file__).resolve().parents[1]`
- `test_start_demo_serves_assets_and_reuses(tmp_path: Path) -> None` — Serve the page and package from one reusable loopback server.
- `test_main_prints_url_and_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None` — Print the demo URL and open it in the managed browser.
- `test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the examples module forwards to the launcher.
- `test_start_demo_reports_unready_server_and_cleans_up(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A failed readiness check kills fresh servers and raises.

### `packages/actions/action_rest/__init__.py`

Tests of ``exactus/packages/actions/action_rest``.


### `packages/actions/action_rest/test_examples.py`

Coverage for the mini postman demo server launcher.

- `class Constants` — Group module-level constants.
  - `root` = `Path(run.__file__).resolve().parents[1]`
- `test_start_demo_serves_assets_and_reuses(tmp_path: Path) -> None` — Serve the demo and the library from one reusable loopback server.
- `test_start_demo_replaces_unready_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate and clear a spawned server that never answers.
- `test_main_prints_url_and_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None` — Print the demo URL and hand it to the system browser.
- `test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the action-rest examples module forwards to ``serve.main``.

### `packages/all_lints/__init__.py`

Test the exactus/packages/all_lints merged linter audit.


### `packages/all_lints/test_all_lints.py`

Exercise the merged linter audit: parsers, excludes, specs and report.

- `make_runner(tmp_path: Path) -> AuditRunner` — Build a runner rooted at ``tmp_path``.
- `ruff_diagnostic(*, runner: AuditRunner, payload: object) -> Diagnostic` — Parse one ruff diagnostic payload and return the first entry.
- `make_result(*, diagnostics: list[Diagnostic]) -> ToolResult` — Build a failed aggregate result for report assertions.
- `class FakeProcess` — Minimal ``Popen`` stand-in returning captured empty output.
  - `__init__(self) -> None` — Start the fake process with a successful return code.
  - `communicate() -> tuple[str, str]` — Return empty captured stdout and stderr.
  - `poll(self) -> int` — Report the stored return code.
  - `kill(self) -> None` — Pretend to kill an already finished process.
- `noop_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> None` — Pretend one Ruff invocation succeeded without touching the file.
- `fail_run(_self: RuffStabilizer, *, args: tuple[str, ...]) -> NoReturn` — Fail the test; no Ruff subprocess may be spawned.
- `fail_popen(*_args: object, **_kwargs: object) -> NoReturn` — Fail the test; no linter subprocess may be spawned.
- `class PendingProcess` — Fake process that reports running until ``kill`` is invoked.
  - `__init__(self) -> None` — Start the fake process in the running state.
  - `poll(self) -> int | None` — Report no exit status until the process is killed.
  - `kill(self) -> None` — Record that the process received a kill request.
- `missing_which(cmd: str) -> None` — Report every executable as missing from ``PATH``.
- `present_which(cmd: str) -> str` — Report every executable as present on ``PATH``.
- `collect_into(*, results: list[FileResult]) -> FinishCallback` — Build a finish callback appending results into ``results``.
- `test_severity_normalization(tmp_path: Path) -> None` — Tool-specific severities map onto the normalized scale.
- `test_ruff_parser(tmp_path: Path) -> None` — Ruff JSON entries normalize with project-relative paths.
- `test_eslint_parser(tmp_path: Path) -> None` — ESLint numeric severities split into error and warning.
- `test_typescript_parser(tmp_path: Path) -> None` — TypeScript text diagnostics match the configured pattern.
- `test_excludes_default_without_pyproject(tmp_path: Path) -> None` — Missing pyproject falls back to the built-in exclude list.
- `test_excludes_merge_pyproject(tmp_path: Path) -> None` — Per-tool pyproject ignore lists merge without duplicates.
- `test_specs_build_single_file_commands() -> None` — Specs build complete per-file command lines.
- `test_report_builder_shape(tmp_path: Path) -> None` — Aggregated reports carry summary counts and diagnostics.
- `test_report_files_list_only_files_with_issues(tmp_path: Path) -> None` — Per-tool ``files`` arrays keep only files that reported issues.
- `test_parse_pyrefly_diagnostics(tmp_path: Path) -> None` — Pyrefly errors map name, description and end position fields.
- `test_parse_dispatches_to_tool_parser(tmp_path: Path) -> None` — Spec parser names route output to the matching decoder.
- `test_summary_table() -> None` — Summary tables list per-tool file counts and issue totals.
- `test_summary_table_reports_unique_file_totals() -> None` — The footer dedupes files shared by tools and groups by suffix.
- `test_run_all_parallel(tmp_path: Path) -> None` — File tasks execute concurrently preserving spec order.
- `test_run_all_tool_durations_reflect_process_spans(tmp_path: Path) -> None` — Per-tool duration is its own task span, not the stage span.
- `test_run_all_forwards_progress_to_listener(tmp_path: Path) -> None` — Discovery and completion events reach an embedding listener.
- `test_shared_discovery_preserves_each_tool_scope(tmp_path: Path) -> None` — One inventory traversal retains suffix and exclusion semantics.
- `test_cli_defaults() -> None` — Defaults point at the packaged project root report.
- `test_progress_counts_checks_not_fully_checked_files() -> None` — One completed check advances progress while another tool is pending.
- `test_typechecker_batches_keep_diagnostics(tmp_path: Path) -> None` — Launch a type checker once and retain findings on their owning file.
- `test_batched_tool_paces_progress_during_the_run(tmp_path: Path) -> None` — A slow batch publishes finishes over time, not all at the end.
- `test_batched_tool_paces_progress_against_the_estimated_duration(tmp_path: Path) -> None` — A pace estimate spreads finishes across the expected runtime.
- `test_previous_durations_reads_the_last_report(tmp_path: Path) -> None` — Reuse stored tool durations; ignore missing or malformed reports.
- `test_batched_warning_diagnostic_fails_its_file(tmp_path: Path) -> None` — A warn diagnostic fails the owning file even when the tool exits 0.
- `test_typescript_project_run_attributes_findings(tmp_path: Path) -> None` — The tsc project check runs once and attributes findings per file.
- `test_typescript_skips_without_project_config(tmp_path: Path) -> None` — The tsc project check covers no files without a project config.
- `test_tool_spec_uses_command_prefix() -> None` — Bundled launchers may prefix a linter subcommand.
- `test_missing_file_falls_back(tmp_path: Path) -> None` — Missing diagnostic paths fall back to the linted file.
- `test_file_result_stabilizer_defaults() -> None` — Linter file results default the stabilization counters.
- `test_stabilizer_rejects_missing_files(tmp_path: Path) -> None` — Stabilization fails fast when a target file does not exist.
- `test_stabilizer_reports_stable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An already-stable file completes after one call per operation.
- `class RecordingRepair` — Repair that rewrites the file once, then leaves it alone.
  - `__init__(self) -> None` — Start with no recorded calls.
- `test_stabilizer_reruns_ruff_after_a_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A repair that changes the file forces another complete Ruff cycle.
- `test_runner_exposes_the_repair_installer(tmp_path: Path) -> None` — The audit runner stores the repair handed to ``use_repair``.
- `test_stabilizer_tracks_batch_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Batch counters advance once per file in submission order.
- `test_stabilizer_rechecks_after_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A mutating Ruff call triggers one extra stabilization cycle.
- `test_stabilizer_forwards_unsafe_fixes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Unsafe Ruff fixes are opt-in and limited to the fix command.
- `test_stabilizer_fails_when_never_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A file that keeps changing raises after exhausting cycles.
- `test_run_all_stabilize_skips_without_ruff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A missing ruff executable skips the stabilization stage.
- `test_run_all_stabilize_without_ruff_spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A spec list without ruff skips stabilization entirely.
- `test_run_all_stabilize_without_python_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An empty discovery set stabilizes no file and spawns nothing.
- `test_run_all_stabilize_runs_ruff_on_discovered_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Stabilization shares the lint display as one progress row.
- `test_run_all_stabilize_lets_other_tools_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Non-Python tools run while the Ruff stabilization pass runs.
- `test_terminate_processes_kills_registered_children(tmp_path: Path) -> None` — Interrupt cleanup kills every in-flight linter child process.
- `test_main_keyboard_interrupt_returns_130(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None` — A ``KeyboardInterrupt`` during the run exits 130 cleanly.
- `test_main_writes_lint_report_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A direct CLI run emits the ``ALL_LINTS_RESULTS`` artifact tree.
- `test_embedded_run_writes_no_lint_report(tmp_path: Path) -> None` — Embedded ``AuditRunner`` use creates no ``ALL_LINTS_RESULTS``.
- `test_main_fail_report_records_fail_activity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A failing audit records ``FAIL`` activity and exits one.
- `test_main_custom_output_also_writes_canonical_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--output`` redirects the report but ``result.json`` still lands.
- `test_main_collect_files_writes_files_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--collect-files`` enables the ``FILES`` bundle.
- `test_main_files_bundle_archives_flagged_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``FILES/files.zip`` stores flagged files in report order.
- `test_pyproject_configures_report_dir_and_collect_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``tool.all_lint`` steers the report directory and FILES bundle.
- `test_configuration_all_lints_defaults(tmp_path: Path) -> None` — Unset ``tool.all_lint`` falls back to the canonical defaults.
- `test_main_function_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None` — The module-level ``main`` delegates to :meth:`Cli.main`.
- `test_stream_tee_mirrors_and_strips_escapes() -> None` — The tee keeps the stream raw and the log escape-free.
- `test_cli_activity_lifecycle_and_interrupt(tmp_path: Path) -> None` — The activity document records runs, interrupts and crashes.
- `test_cli_activity_beats_and_drops_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The heartbeat thread rewrites the document on its interval.
- `test_cli_activity_tolerates_unwritable_path(tmp_path: Path) -> None` — A failing document write degrades the activity file silently.
- `test_progress_display_tracks_and_renders(capfd: pytest.CaptureFixture[str]) -> None` — The display tracks per-tool and global progress and renders it.
- `test_progress_display_disabled_is_silent(capfd: pytest.CaptureFixture[str]) -> None` — A disabled display renders nothing and still publishes events.
- `test_main_module_switches_to_project_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The all-lints module switches interpreter before its CLI runs.
- `test_examples_module_switches_to_project_python(monkeypatch: pytest.MonkeyPatch) -> None` — The all-lints example uses the same automatic interpreter switch.
- `test_final_compact_pass_uses_expected_ruff_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Compact formatting occurs after ordinary stabilization.
- `test_final_compact_pass_retries_after_final_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A final Ruff fix that changes content triggers another compact cycle.

### `packages/all_lints/test_example_run.py`

Cover the bundled ``all_lints`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'all_lints...`
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry for real.

### `packages/argument_parser/__init__.py`

Tests for ``exactus.packages.argument_parser``.


### `packages/argument_parser/test_parser.py`

Dash/underscore folding in the shared ``ExactusArgumentParser``.

- `test_normalized_option_folds_long_names() -> None` — Only the name part of ``--`` tokens is folded.
- `test_dash_and_underscore_parse_identically() -> None` — Both spellings populate the same destination.
- `test_equal_form_and_separator() -> None` — ``--opt=value`` folds and ``--`` stops folding.
- `test_abbrev_matching_still_works() -> None` — Unique-prefix abbreviations of registered spellings keep working.
- `test_colliding_spellings_fall_back_to_exact() -> None` — Options differing only by ``-``/``_`` keep exact matching only.
- `test_subparsers_inherit_folding() -> None` — ``add_subparsers`` children fold spellings automatically.
- `test_unmatched_tokens_pass_through() -> None` — Unknown flags and positionals are untouched.

### `packages/browser/__init__.py`

Tests for browser lifecycle monitoring.


### `packages/browser/test_browser.py`

Tests for the unified browser lifecycle API.

- `expect(*, condition: bool, message: str) -> None` — Fail the test when a condition is false.
- `class FakePage` — Minimal runtime page double.
  - `__init__(self) -> None` — Initialize page state and handlers.
  - `wait_for_timeout(timeout: float) -> None` — Accept the worker's keep-alive wait without blocking.
  - `is_closed(self) -> bool` — Return whether the page is closed.
  - `title(self) -> str` — Return the title while the page is alive.
  - `on(self, event: str, f: Callable[[Page], None]) -> None` — Record one event callback.
  - `goto(self, url: str) -> None` — Record navigation.
  - `fire(self, event: str) -> None` — Invoke a recorded callback.
- `class FakeContext` — Minimal runtime context double.
  - `__init__(self) -> None` — Initialize context state.
  - `on(self, event: str, f: Callable[[Page], None]) -> None` — Record one event callback.
  - `new_page(self) -> Page` — Create and publish a fake page.
  - `fire(self, event: str) -> None` — Invoke a recorded callback.
- `class FakeBrowser` — Minimal runtime browser double.
  - `__init__(self) -> None` — Initialize browser state.
  - `contexts(self) -> list[BrowserContext]` — Return the single fake context as the context list.
  - `on(self, event: str, f: Callable[[Page], None]) -> None` — Record one event callback.
  - `new_context(self) -> BrowserContext` — Return the fake context.
  - `is_connected(self) -> bool` — Return the connection state.
  - `close(self) -> None` — Close and publish disconnection.
- `class FakeChromium` — Minimal Chromium launcher double.
  - `__init__(self, browser: FakeBrowser) -> None` — Store the browser returned by launch.
  - `launch(self, **_kwargs: str | bool | list[str] | None) -> Browser` — Return the configured browser.
- `class FakePlaywright` — Minimal Playwright runtime double.
  - `__init__(self, browser: FakeBrowser) -> None` — Initialize the Chromium launcher.
  - `stop(self) -> None` — Record shutdown.
- `class FakeStarter` — Minimal sync_playwright context double.
  - `__init__(self, playwright: FakePlaywright) -> None` — Store the runtime returned by start.
  - `start(self) -> Playwright` — Return the configured Playwright runtime.
- `class FakeProcess` — Deterministic native process double.
  - `pid` = `42`
  - `__init__(self) -> None` — Initialize process state.
  - `poll(self) -> int | None` — Return the current exit code.
  - `wait(self) -> int` — Return a deterministic exit code and signal completion.
  - `terminate(self) -> None` — Record termination.
- `class FakeProcessFactory` — Return a configured native process double.
  - `__init__(self, process: FakeProcess) -> None` — Initialize the process factory.
- `class FakeChromeLocator` — Provide deterministic Chrome executable discovery.
  - `executable` = `Path('/fake/chrome')`
  - `find(cls, executable: Path | None=None) -> Path` — Return a deterministic executable path.
- `class TestBrowserLifecycle` — Exercise public lifecycle behavior.
  - `test_subscriptions_are_ordered_and_removable(monkeypatch: pytest.MonkeyPatch) -> None` — Specific listeners precede global listeners without duplicates.
  - `test_playwright_events_use_last_live_page_state(monkeypatch: pytest.MonkeyPatch) -> None` — Close and crash events never query a dead page.
  - `test_native_process_events_include_pid_and_exit_code(monkeypatch: pytest.MonkeyPatch) -> None` — Native process lifecycle carries backend process information.
  - `test_idle_properties_and_native_termination() -> None` — Idle state is empty and close terminates a running process.
- `test_darwin_locator_scans_application_roots(monkeypatch: pytest.MonkeyPatch) -> None` — MacOS discovery scans the usual ``.app`` installation roots.
- `test_windows_locator_uses_program_files(monkeypatch: pytest.MonkeyPatch) -> None` — Windows discovery derives paths from ``PROGRAMFILES`` values.
- `test_linux_locator_uses_generic_names(monkeypatch: pytest.MonkeyPatch) -> None` — Other platforms fall back to the generic binary names.
- `test_find_rejects_missing_explicit_executable() -> None` — An explicit missing executable raises ``FileNotFoundError``.
- `test_find_reports_missing_installation(monkeypatch: pytest.MonkeyPatch) -> None` — Exhausting every discovery strategy raises ``FileNotFoundError``.
- `test_start_playwright_runs_worker_until_pages_close(monkeypatch: pytest.MonkeyPatch) -> None` — The worker publishes readiness and exits when pages vanish.
- `test_start_playwright_rejects_a_running_worker(monkeypatch: pytest.MonkeyPatch) -> None` — A second ``start_playwright`` call raises ``RuntimeError``.

### `packages/browser/test_examples.py`

Exercise the browser lifecycle example with recorded stubs.

- `test_parser_defaults_to_the_playwright_backend() -> None` — The bundled parser selects playwright and the demo page.
- `test_run_with_explicit_url_skips_the_demo_server(monkeypatch: pytest.MonkeyPatch) -> None` — An explicit URL opens playwright without serving the bundle.
- `test_run_serves_the_bundled_demo_when_no_url(monkeypatch: pytest.MonkeyPatch) -> None` — Without a URL the example serves ``web/`` and opens playwright.
- `test_run_rejects_an_unsupported_backend(monkeypatch: pytest.MonkeyPatch) -> None` — An unknown backend raises ``ValueError`` after cleanup.
- `test_run_chrome_backend_uses_the_native_wait(monkeypatch: pytest.MonkeyPatch) -> None` — The chrome branch launches natively then sleeps briefly.
- `test_event_renderer_prints_a_snapshot(monkeypatch: pytest.MonkeyPatch) -> None` — The event hook formats one lifecycle event per line.
- `test_start_demo_reuses_the_recorded_server(monkeypatch: pytest.MonkeyPatch) -> None` — A recorded server is adopted instead of spawning a new one.
- `test_wait_native_polls_until_process_exit(monkeypatch: pytest.MonkeyPatch) -> None` — A zero duration polls the native process until it exits.
- `test_main_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry with stubs.
- `test_main_module_reports_an_unready_demo(monkeypatch: pytest.MonkeyPatch) -> None` — An unready fresh demo server raises ``RuntimeError`` after cleanup.
- `test_run_ignores_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None` — A ``KeyboardInterrupt`` during the wait still closes the browser.

### `packages/completion/__init__.py`

Tests of ``exactus/completion``.


### `packages/completion/test_catalog.py`

Coverage for parser introspection in ``exactus/completion/catalog``.

- `test_spec_from_parser_maps_cardinalities() -> None` — ``nargs`` variants map to the matching cardinalities.
- `test_spec_from_parser_collects_choices() -> None` — ``choices`` become static candidate values.
- `test_spec_from_parser_marks_mutex_groups() -> None` — Mutually exclusive members share a group identifier.
- `test_spec_from_parser_repeatable_append() -> None` — ``append`` actions are marked repeatable.
- `test_spec_from_parser_hides_suppressed_options() -> None` — ``help=SUPPRESS`` actions carry ``hidden``.
- `test_spec_from_parser_positionals() -> None` — Positional actions become positional specs.
- `test_provider_inference_by_metavar_and_type() -> None` — Metavar and ``type=Path`` drive provider inference.
- `test_provider_overrides_win() -> None` — Destination overrides beat metavar heuristics.
- `test_long_names_lead_canonical_order() -> None` — ``--`` names precede short names in spec ordering.
- `test_merge_specs_combines_options() -> None` — Merged specs keep options from every source.
- `test_completion_command_spec_exposes_shells() -> None` — The public command offers the four shells plus management.
- `test_catalog_context_lookup() -> None` — ``context_named`` resolves dispatch targets.

### `packages/completion/test_engine.py`

Decision-tree coverage for :class:`CompletionEngine`.

- `test_root_offers_subcommands_and_positionals(tmp_path: Path) -> None` — Bare tokens offer subcommand names plus positional values.
- `test_long_options_filtered_by_prefix(tmp_path: Path) -> None` — ``--`` prefixes offer only matching long option names.
- `test_used_non_repeatable_option_suppressed(tmp_path: Path) -> None` — A supplied non-repeatable option is not offered again.
- `test_repeatable_option_reoffered(tmp_path: Path) -> None` — Repeatable flags stay legal after one use.
- `test_mutex_group_suppresses_sibling(tmp_path: Path) -> None` — Using one mutex member suppresses the other.
- `test_option_value_choices(tmp_path: Path) -> None` — A pending option offers its static choices.
- `test_inline_value_completion(tmp_path: Path) -> None` — ``--name=v`` prefixes complete to ``--name=value`` insertions.
- `test_repeat_values_exclude_consumed(tmp_path: Path) -> None` — Repeatable options offer remaining values only.
- `test_double_dash_disables_options(tmp_path: Path) -> None` — After ``--`` a dash prefix hits positionals, not options.
- `test_dispatch_option_switches_context(tmp_path: Path) -> None` — A context option activates the target grammar's options.
- `test_subcommand_switches_context(tmp_path: Path) -> None` — A subcommand token activates the child grammar.
- `test_positional_provider_used_inside_subcommand(tmp_path: Path) -> None` — A positional with a provider completes provider values.
- `test_hidden_option_never_offered(tmp_path: Path) -> None` — Hidden options stay legal but are never candidates.
- `test_canonical_only_offers_long_name(tmp_path: Path) -> None` — ``canonical_only`` options offer the long name only.
- `test_short_cluster_consumes_flags(tmp_path: Path) -> None` — ``-vv`` counts as two uses of a repeatable short flag.
- `test_short_option_attached_value(tmp_path: Path) -> None` — ``-fjson`` commits the value to ``--format``.
- `test_negative_number_is_a_value(tmp_path: Path) -> None` — A negative number feeds the pending option, not options.
- `test_option_prefix_interrupts_satisfied_pending(tmp_path: Path) -> None` — After a satisfied option value, ``-`` offers options.
- `test_greedy_option_keeps_collecting(tmp_path: Path) -> None` — ``nargs='*'`` keeps consuming values until a known option.
- `test_candidates_sorted_by_kind_then_value(tmp_path: Path) -> None` — Candidate order is deterministic: kind, then value.
- `test_warm_static_completion_latency(tmp_path: Path) -> None` — Warm static completion stays within the 100 ms regression budget.
- `test_underscore_prefix_offers_the_dashed_option(tmp_path: Path) -> None` — ``--collect_`` completes to the registered ``--collect-files``.
- `test_underscore_spelling_counts_as_a_used_option(tmp_path: Path) -> None` — ``--dry_run`` suppresses a second ``--dry-run`` suggestion.

### `packages/completion/test_examples.py`

Run the public completion example against the standalone grammar.

- `test_completion_example(monkeypatch: pytest.MonkeyPatch) -> None` — The standalone grammar provides both flag and pipeline candidates.

### `packages/completion/test_main.py`

Cover the ``exactus.packages.completion`` command-line entry point.

- `class Constants` — Group module-level constants.
  - `main_module` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'completio...`
- `test_bootstrap_imports_standalone(monkeypatch: pytest.MonkeyPatch) -> None` — Re-execute the module's script bootstrap without a package.
- `test_run_rejects_conflicting_actions(tmp_path: Path) -> None` — Refuse more than one management action in a single call.
- `test_run_diagnose_requires_all_shells(tmp_path: Path) -> None` — Refuse ``--diagnose`` narrowed to one shell.
- `test_run_diagnose_reports_missing_registrations(tmp_path: Path) -> None` — Report missing registrations as healthy for an empty home.
- `test_run_install_and_uninstall_manage_profiles(tmp_path: Path) -> None` — Install then uninstall registration content under a fake home.
- `test_main_accepts_explicit_arguments() -> None` — Dispatch explicit CLI tokens through ``main``.

### `packages/completion/test_protocol.py`

Wire-protocol coverage for ``__complete`` parsing and records.

- `test_parse_valid_request() -> None` — A well-formed request parses into a normalized value.
- `test_parse_rejects_bare_argument() -> None` — Arguments must use ``--name=value`` form.
- `test_parse_rejects_unknown_argument() -> None` — Unknown protocol names are malformed.
- `test_parse_rejects_missing_shell() -> None` — ``--shell`` is required.
- `test_parse_rejects_unknown_shell() -> None` — Unsupported shell names exit ``3``.
- `test_parse_rejects_protocol_mismatch() -> None` — A foreign protocol version yields no candidates.
- `test_parse_rejects_bad_index() -> None` — Non-numeric and out-of-range active indices are malformed.
- `test_parse_accepts_empty_and_dash_words() -> None` — Empty words and ``-``-leading words survive ``--word=``.
- `test_parse_enforces_word_limit() -> None` — More than ``MAX_WORDS`` words is malformed.
- `test_parse_enforces_input_limit() -> None` — Requests above ``MAX_INPUT`` bytes are malformed.
- `test_render_record_fields() -> None` — Records are ``value US display US description US kind US flags``.
- `test_render_record_rejects_control_characters() -> None` — Fields containing separators or newlines are dropped.
- `test_render_record_enforces_size_limit() -> None` — Records above ``MAX_RECORD`` are dropped.
- `test_run_completion_writes_only_records() -> None` — Stdout carries records only, with a ``0`` exit.
- `test_run_completion_malformed_writes_nothing() -> None` — Rejections emit no stdout records and a non-zero status.
- `test_run_completion_engine_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Provider explosions surface as exit ``5`` with empty stdout.
- `test_protocol_limits_count_utf8_bytes() -> None` — Multibyte requests and records obey byte limits.
- `test_protocol_rejects_invalid_text() -> None` — Controls and unpaired surrogates cannot cross the wire.

### `packages/completion/test_providers.py`

Coverage for the dynamic completion providers.

- `test_path_provider_lists_children(tmp_path: Path) -> None` — Immediate children complete, preserving relative style.
- `test_path_provider_filters_by_name_prefix(tmp_path: Path) -> None` — Only children matching the basename prefix are offered.
- `test_path_provider_preserves_relative_base(tmp_path: Path) -> None` — ``./x`` prefixes insert ``./``-prefixed values.
- `test_path_provider_absolute_prefix(tmp_path: Path) -> None` — Absolute prefixes keep the absolute base in insertions.
- `test_path_provider_hides_dotfiles(tmp_path: Path) -> None` — Dotfiles appear only when the prefix starts with a dot.
- `test_directory_provider_suppresses_files(tmp_path: Path) -> None` — ``directories_only`` providers skip files.
- `test_path_provider_missing_directory_is_empty(tmp_path: Path) -> None` — A nonexistent lookup directory yields no candidates.
- `test_directory_candidates_do_not_append_space(tmp_path: Path) -> None` — Directory insertions continue the path — no trailing space.
- `test_split_prefix_shapes() -> None` — ``_split_prefix`` separates display base from name filter.
- `test_static_name_provider_prefixes() -> None` — Static providers emit every entry; the engine filters.
- `test_scoped_argument_provider() -> None` — ``--tool-arg`` values complete as ``name::`` prefixes.
- `test_default_providers_cover_every_id() -> None` — The default registry wires every ``ProviderId``.
- `test_default_tool_provider_uses_supplied_tools() -> None` — Tool candidates come from the caller's own catalog.
- `test_path_provider_caps_results(tmp_path: Path) -> None` — Large directories retain bounded, sorted completion results.
- `test_path_provider_stops_at_entry_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Scanning stops at its entry budget before retaining more results.
- `test_path_provider_stops_at_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An elapsed deadline stops scanning without a wall-clock sleep.

### `packages/completion/test_shells.py`

Coverage for the shell registration-script renderers.

- `class Constants` — Group module-level constants.
  - `launcher` = `('check',)`
- `test_function_name_sanitizes() -> None` — Non-identifier characters become underscores.
- `test_bash_script_shape() -> None` — Bash output registers a function and parses US records.
- `test_zsh_script_shape() -> None` — Zsh output declares compdef and splits on the separator.
- `test_fish_script_shape() -> None` — Fish output registers a ``complete`` handler.
- `test_powershell_script_shape() -> None` — PowerShell output registers a native argument completer.
- `test_render_dispatches_every_shell() -> None` — ``render`` covers all four supported shells.
- `test_scripts_are_deterministic() -> None` — Identical inputs produce byte-identical scripts.
- `test_launcher_embedded_in_scripts() -> None` — A multi-word launcher is quoted into each adapter.
- `test_generated_bash_is_syntactically_valid() -> None` — The bash adapter parses under ``bash -n``.
- `test_generated_zsh_is_syntactically_valid() -> None` — The zsh adapter parses under ``zsh -n`` when available.
- `test_generated_fish_is_syntactically_valid() -> None` — The fish adapter parses under ``fish --no-execute``.
- `test_powershell_uses_cursor_and_logical_words(tmp_path: Path) -> None` — Native completion ignores suffix tokens and decodes quoting.

### `packages/exactus_mcp/__init__.py`

Tests for the Exactus MCP and ngrok service.


### `packages/exactus_mcp/test_activity.py`

Validate Exactus MCP lifecycle and caller activity tracking.

- `test_activity_tracks_lifecycle_urls_and_calls() -> None` — Snapshots expose explicit lifecycle and protected-call activity.
- `test_activity_preserves_last_failure_until_a_new_start() -> None` — A failure remains visible until the next deliberate startup.

### `packages/exactus_mcp/test_cli.py`

Validate Exactus MCP command-line configuration.

- `private_coroutine(*, owner: object, name: str, **arguments: object) -> Coroutine[object, object, object]` — Call a private coroutine function with a typed result.
- `swallow_kwargs(**kwargs: object) -> None` — Accept and discard any keyword arguments.
- `kwargs_namespace(**kwargs: object) -> SimpleNamespace` — Convert keyword arguments into a namespace double.
- `class LoopingServer` — Uvicorn double that serves until asked to exit.
  - `__init__(self, *, config: object=None) -> None` — Accept the ASGI configuration.
  - `serve(self) -> None` — Pretend to serve until ``should_exit`` is set.
- `test_config_resolves_root_and_preserves_security_values(tmp_path: Path) -> None` — Valid arguments become a typed runtime configuration.
- `test_config_rejects_invalid_port(tmp_path: Path) -> None` — Ports outside the TCP range fail before service startup.
- `test_config_rejects_two_ngrok_modes(tmp_path: Path) -> None` — Named endpoints and requested URLs cannot run together.
- `test_main_lists_json_configuration_with_secrets_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Bare ``--config`` prints resolved values without credential text.
- `test_configuration_root_reads_both_option_forms(tmp_path: Path) -> None` — ``--root`` resolves from either CLI spelling before parsing.
- `test_config_rejects_invalid_timeouts_and_mantledb(attribute: str, value: object, match: str, tmp_path: Path) -> None` — Zero timeouts and blank MantleDB values fail validation.
- `test_config_rejects_missing_root(tmp_path: Path) -> None` — A nonexistent project root fails validation.
- `test_wait_started_reports_early_exit_and_timeout() -> None` — Uvicorn startup failures surface as runtime errors.
- `test_wait_for_stop_returns_once_event_set() -> None` — A pre-set stop event completes the stop waiter immediately.
- `test_start_tunnel_disabled_returns_none(tmp_path: Path) -> None` — A disabled tunnel skips ngrok and MantleDB entirely.
- `test_start_tunnel_publishes_url_and_mantledb_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A started tunnel updates state and stores its public URL.
- `test_run_service_serves_until_stop_requested(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The lifecycle loop serves, prints connection info, then stops.
- `test_run_service_marks_failed_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A startup failure records the error and re-raises it.
- `test_wait_for_runtime_surfaces_tunnel_exit() -> None` — An early tunnel exit aborts the runtime wait with its status.
- `test_macos_menu_bar_guard_and_dispatch(monkeypatch: pytest.MonkeyPatch) -> None` — Non-macOS platforms reject and dispatch reaches the menu module.
- `test_main_runs_service_via_run_async(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A normal invocation hands the coroutine to ``run_async``.
- `test_main_reports_errors_and_interrupts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Configuration errors return one; interrupts return zero.

### `packages/exactus_mcp/test_cloudflare.py`

Tests for Exactus Cloudflare publication.

- `await_private(*, owner: object, member: str, **arguments: object) -> object` — Call a private coroutine and return its result.
- `class Constants` — Group module-level constants.
  - `credential` = `'fixture-value'`
- `test_config_from_mapping() -> None` — Parse and normalize Cloudflare environment configuration.
- `test_config_rejects_insecure_worker() -> None` — Reject a non-HTTPS stable Worker URL.
- `test_configured_port_reads_project(tmp_path: Path) -> None` — Read the fixed local upstream port from pyproject.toml.
- `test_quick_tunnel_url_detection(tmp_path: Path) -> None` — Discover the assigned HTTPS Quick Tunnel URL from process output.
- `class FakeHttpResponse` — Stand in for an ``httpx2`` response returned by the test client.
  - `__init__(self, *, is_success: bool=True) -> None` — Store the response status.
  - `raise_for_status(self) -> None` — Accept the simulated successful response.
- `class FakeHttpClient` — Capture requests made through the injected HTTP client.
  - `__init__(self, *, timeout: float) -> None` — Store the configured timeout and empty call log.
  - `get(self, *, url: str) -> FakeHttpResponse` — Record a GET request and replay the next scripted step.
  - `post(self, *, url: str, headers: dict[str, str], json: dict[str, str]) -> FakeHttpResponse` — Record a POST request and return success.
- `call_private(*, owner: object, member: str, **arguments: object) -> object` — Call a private synchronous callable and return its result.
- `test_config_rejects_invalid_values(overrides: dict[str, str], match: str) -> None` — Numeric timing settings must parse and stay within safe bounds.
- `test_config_rejects_empty_control_secret() -> None` — The shared control credential must not be empty.
- `test_configured_port_edge_cases(tmp_path: Path, body: str | None, expected: int) -> None` — Missing, misplaced, malformed, and out-of-range ports fall back.
- `test_bootstrapper_reads_namespace_state(tmp_path: Path) -> None` — Namespace detection distinguishes missing, pending, and ready files.
- `test_bootstrapper_requires_prerequisite_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Missing prerequisites without Homebrew abort bootstrap safely.
- `test_bootstrapper_ensure_skips_provisioned_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A fully configured environment performs no provisioning work.
- `test_bootstrapper_provisions_missing_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Bootstrap creates the namespace, deploys, and stores secrets locally.
- `test_bootstrapper_requires_login_success(tmp_path: Path) -> None` — A failed Wrangler login aborts bootstrap.
- `test_bootstrapper_namespace_creation_failures(tmp_path: Path, result: tuple[int, str], body: str | None, match: str) -> None` — Namespace creation failures never silently continue bootstrap.
- `test_bootstrapper_deploy_fallback_and_failures(tmp_path: Path) -> None` — Deploy falls back to a configured URL and reports real failures.
- `test_bootstrapper_secret_upload_failure(tmp_path: Path) -> None` — A rejected secret upload reports the failing secret name.
- `test_supervisor_resolves_cloudflared(tmp_path: Path) -> None` — Executable resolution accepts real files and rejects missing tools.
- `test_supervisor_stop_is_idempotent() -> None` — Stopping ignores missing or already-exited child processes.
- `test_read_tunnel_url_requires_output_stream(tmp_path: Path) -> None` — A tunnel without stdout cannot report its assigned URL.
- `test_read_tunnel_url_reports_early_exit(tmp_path: Path) -> None` — A tunnel that exits without a URL is a startup failure.
- `test_wait_for_server_reports_early_exit(tmp_path: Path) -> None` — A server exiting during startup surfaces immediately.
- `test_wait_for_server_retries_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Transient health-check failures are retried until healthy.
- `test_wait_for_server_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A server that never becomes healthy exhausts the deadline.
- `test_publish_posts_backend_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Publishing sends the tunnel URL with the bearer credential.
- `test_require_tool_accepts_present_executable(monkeypatch: pytest.MonkeyPatch) -> None` — Tool resolution succeeds when the executable exists.
- `test_bootstrapper_installs_missing_prerequisite(monkeypatch: pytest.MonkeyPatch) -> None` — A missing tool is installed through Homebrew when available.
- `test_bootstrapper_reports_failed_prerequisite_install(monkeypatch: pytest.MonkeyPatch) -> None` — A failed Homebrew install aborts bootstrap with a clear error.
- `test_bootstrapper_login_reuses_existing_auth(tmp_path: Path) -> None` — An authenticated Wrangler session skips the login flow.
- `test_bootstrapper_wrangler_invocation_uses_pinned_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Wrangler runs through npx in the bridge directory with stdin support.
- `test_read_tunnel_url_times_out(tmp_path: Path) -> None` — A silent tunnel exhausts the startup deadline.
- `test_supervisor_stop_tolerates_vanished_process() -> None` — A child exiting between terminate and wait is not an error.
- `test_bootstrapper_writes_env_without_existing_file(tmp_path: Path) -> None` — Generated configuration is written with owner-only permissions.
- `test_main_delegates_to_async_stack(monkeypatch: pytest.MonkeyPatch, run_result: int | KeyboardInterrupt, expected: int) -> None` — The entrypoint returns the async result or a clean interrupt exit.

### `packages/exactus_mcp/test_environment.py`

Tests for deterministic .env loading.

- `expect_equal(*, actual: object, expected: object) -> None` — Fail when two test values differ.
- `test_environment_loader_preserves_existing_values(tmp_path: Path) -> None` — Process environment values take precedence over .env values.

### `packages/exactus_mcp/test_examples.py`

Validate runnable Exactus MCP examples.

- `test_self_contained_example_completes_authenticated_round_trip(tmp_path: Path) -> None` — The local example discovers tools and resources, then terminates.
- `test_client_requires_access_token(monkeypatch: pytest.MonkeyPatch) -> None` — Without ``EXACTUS_MCP_ACCESS_TOKEN`` the client exits with two.
- `test_client_prints_inspection_summary(monkeypatch: pytest.MonkeyPatch) -> None` — A successful inspection prints tools, resources, and status.

### `packages/exactus_mcp/test_macos_menu.py`

Exercise native menu lifecycle with an isolated status-library adapter.

- `class MenuItem` — Represent the native item's mutable presentation and callback.
  - `callback` = `None`
  - `hidden` = `False`
  - `children` = `field(default_factory=list)`
  - Fields: `title: str`
  - `set_callback(self, callback: MenuCallback | None) -> None` — Replace the enabled action.
  - `add(self, menuitem: NativeMenuItem) -> None` — Append a submenu entry.
- `menu_module() -> ModuleType` — Import the controller without loading platform-native bindings.
- `test_menu_renders_lifecycle_and_action_availability(menu_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str) -> None` — Display real service snapshots without stale enabled controls.
- `test_menu_actions_use_supervisor_and_preferred_connection(menu_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Dispatch controls and connection actions through their owned boundaries.
- `test_menu_quits_after_stop_or_deadline(*, menu_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, running: bool) -> None` — Quit waits for shutdown but cannot hang indefinitely.
- `test_native_timer_is_stopped_when_run_loop_exits(menu_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: RuntimeError | None) -> None` — The native refresh timer is stopped even after a run-loop failure.

### `packages/exactus_mcp/test_mantledb.py`

Validate MantleDB URL persistence without network access.

- `class FakeResponse` — Return one synthetic HTTP response body.
  - Fields: `payload: bytes`
  - `read(self) -> bytes` — Return the configured body.
- `class FakeOpener` — Record requests and return queued bodies.
  - `requests` = `field(default_factory=list)`
  - `timeouts` = `field(default_factory=list)`
  - Fields: `bodies: list[bytes]`
- `test_store_writes_and_retrieves_public_url() -> None` — The store uses escaped endpoints and JSON request bodies.
- `test_store_rejects_invalid_url_payloads(body: bytes) -> None` — Decoded values must contain a string URL.
- `test_store_rejects_unsigned_or_tampered_discovery(body: bytes) -> None` — A configured signing key requires an authentic string signature.
- `test_store_updates_unsigned_records_and_rejects_empty_urls() -> None` — Unsigned stores support updates but refuse empty records.
- `test_signature_requires_configured_key() -> None` — Signing is impossible without a configured HMAC key.
- `test_store_translates_transport_errors(operation: str) -> None` — Transport failures retain their cause without pretending success.
- `test_default_transport_rejects_untrusted_origins(url: str) -> None` — The default transport cannot be redirected to arbitrary origins.
- `test_default_transport_owns_response_and_connection(monkeypatch: pytest.MonkeyPatch, status: int) -> None` — Success and HTTP failures close both owned transport resources.

### `packages/exactus_mcp/test_ngrok.py`

Validate ngrok public URL discovery.

- `test_parse_public_url_accepts_started_https_tunnel() -> None` — A started-tunnel record yields its HTTPS origin.
- `test_parse_public_url_rejects_unrelated_or_insecure_records() -> None` — Malformed, unrelated, and HTTP records never create a public origin.
- `test_parse_public_url_rejects_incomplete_records(line: str) -> None` — Reject non-object logs and incomplete HTTPS records.
- `test_start_wait_and_close_own_the_child(monkeypatch: pytest.MonkeyPatch, endpoint: str | None) -> None` — Discover a tunnel after unrelated logs and reap it on close.
- `test_start_rejects_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None` — A missing binary fails before any child process is created.
- `test_start_failure_reaps_child(*, monkeypatch: pytest.MonkeyPatch, missing_stdout: bool) -> None` — Missing capture and early exit both clean up the owned process.
- `test_close_handles_exited_and_unresponsive_children(*, already_exited: bool) -> None` — Closing is harmless after exit and escalates a failed terminate.

### `packages/exactus_mcp/test_project_config.py`

Validate Exactus MCP project configuration loading.

- `test_service_and_wake_defaults_are_typed(tmp_path: Path) -> None` — Supported TOML settings become normalized parser defaults.
- `test_unknown_setting_is_rejected(tmp_path: Path) -> None` — A misspelled setting fails instead of silently doing nothing.
- `test_private_json_supports_service_and_wake_secrets(tmp_path: Path) -> None` — A shared private JSON document supplies both command sections.
- `test_secret_json_requires_private_posix_permissions(tmp_path: Path) -> None` — Group-readable secret configuration fails before values are used.
- `test_toml_rejects_secret_settings(tmp_path: Path) -> None` — Project TOML cannot become an accidental plaintext secret store.
- `test_config_selection_supports_listing_and_json_paths(tmp_path: Path) -> None` — The dual-form option is removed before normal argument parsing.
- `test_select_config_rejects_empty_inline_value() -> None` — A bare ``--config=`` with no path raises a clear ValueError.
- `test_select_config_rejects_bare_followed_by_flag() -> None` — A bare ``--config`` before another flag raises ValueError.
- `test_select_config_rejects_repeated_path() -> None` — Two explicit ``--config`` paths raise a clear ValueError.
- `test_select_config_allows_bare_after_path() -> None` — A path followed by a bare ``--config`` is valid listing syntax.
- `test_service_defaults_reject_invalid_toml(tmp_path: Path) -> None` — An invalid TOML document raises a clear ValueError.
- `test_service_defaults_reject_non_table_section(tmp_path: Path) -> None` — A non-table ``[tool.exactus.mcp]`` raises a clear TypeError.
- `test_service_json_defaults_reject_invalid_json(tmp_path: Path) -> None` — An invalid JSON document raises a clear ValueError.
- `test_service_json_defaults_reject_non_object(tmp_path: Path) -> None` — A JSON document that is not an object raises a clear TypeError.
- `test_service_json_defaults_reject_non_object_section(tmp_path: Path) -> None` — A named ``service`` section that is not an object raises TypeError.
- `test_service_defaults_reject_duplicate_setting(tmp_path: Path) -> None` — Two keys that normalise to the same name raise a clear ValueError.
- `test_service_defaults_reject_invalid_value_type(tmp_path: Path) -> None` — A setting with an invalid value type raises a clear ValueError.
- `test_wakeup_cli_lists_json_configuration_with_secrets_redacted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Watcher configuration listing includes no private JSON values.

### `packages/exactus_mcp/test_runner.py`

Validate the constrained Exactus runner.

- `test_report_summary_reads_status_and_findings(tmp_path: Path) -> None` — Machine report metadata is parsed without weakening JSON types.
- `test_run_rejects_parent_traversal_before_process_start(tmp_path: Path) -> None` — Remote include globs cannot escape the configured project.
- `test_report_summary_rejects_malformed_fields(tmp_path: Path, body: str, expected: tuple[str, int]) -> None` — Malformed reports never become successful checks or boolean counts.
- `test_run_rejects_unsafe_include_limits(tmp_path: Path, includes: tuple[str, ...]) -> None` — Absolute, oversized and excessive globs fail before process creation.
- `test_run_collects_reports_and_bounds_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str | None, expected_status: str) -> None` — Execute only a dry fixed-root command and return its bounded report.
- `test_report_path_rejects_unknown_tool(tmp_path: Path) -> None` — An unknown tool identifier cannot resolve a report location.
- `test_run_timeout_reaps_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, force_kill: bool) -> None` — A timed-out report terminates its child, escalating when necessary.

### `packages/exactus_mcp/test_service.py`

Validate MCP registration and the public HTTP boundary.

- `class ClientResponse(Protocol)` — Subset of the test-client response surface used by asset checks.
  - `status_code(self) -> int` — HTTP status code.
  - `headers(self) -> Mapping[str, str]` — Response headers.
- `class FakeRunner` — Deterministic runner used at the HTTP and MCP boundaries.
  - `list_tools() -> tuple[str, ...]` — Return a representative complete catalog.
  - `run(*, tool: RemoteTool, includes: tuple[str, ...]) -> CheckResult` — Return a deterministic successful result.
  - `read_report(*, tool: RemoteTool, report_format: ReportFormat) -> str` — Return deterministic report text.
- `test_server_registers_protected_exactus_tools(tmp_path: Path) -> None` — The MCP catalog contains all four intended service tools.
- `test_tool_call_updates_visible_activity(tmp_path: Path) -> None` — A protected tool call updates the menu's shared activity record.
- `test_public_page_and_bearer_boundary(tmp_path: Path) -> None` — Public metadata is safe while MCP rejects missing credentials.
- `class FailingRunner` — Runner double whose every operation fails deterministically.
  - `list_tools() -> tuple[str, ...]` — Fail catalog listing.
  - `run(*, tool: RemoteTool, includes: tuple[str, ...]) -> CheckResult` — Fail check execution.
  - `read_report(*, tool: RemoteTool, report_format: ReportFormat) -> str` — Fail report reading.
- `test_tool_error_paths_record_failures(tmp_path: Path) -> None` — Failing runner calls propagate and record activity errors.
- `test_protected_tool_calls_return_results(tmp_path: Path) -> None` — Status, checks, and reports return runner-backed results.
- `test_policy_resources_and_asset_serving(tmp_path: Path) -> None` — Policy resources read root files; assets serve allowlisted names.
- `test_origin_gateway_normalizes_authenticated_scopes() -> None` — The origin credential rewrites tunneled scopes for local auth.

### `packages/exactus_mcp/test_startup.py`

Validate native watcher lifecycle definitions without changing the host.

- `class FakeNativeRunner` — Emulate launchd, systemd, and Task Scheduler state transitions.
  - `active` = `False`
  - `commands` = `field(default_factory=list)`
- `test_native_install_status_and_uninstall(tmp_path: Path, platform_name: str, backend: str) -> None` — Every supported platform installs, reports, and removes the watcher.
- `test_linux_definition_quotes_each_argument(tmp_path: Path) -> None` — Linux startup persists a direct argument vector rather than a shell.

### `packages/exactus_mcp/test_state.py`

Validate public URL and transport allowlist state.

- `test_expose_adds_public_origin_to_transport_security() -> None` — The ngrok host and origin become admitted transport values.
- `test_expose_rejects_non_https_origin() -> None` — Public exposure requires ngrok HTTPS.

### `packages/exactus_mcp/test_supervisor.py`

Validate synchronous controls for the Exactus MCP async service.

- `class RestartProbe` — Record each deterministic service generation for restart tests.
  - `__init__(self) -> None` — Create an empty thread-safe generation queue.
- `test_supervisor_starts_and_stops_without_blocking(tmp_path: Path) -> None` — Start and Stop control one background service generation.
- `test_supervisor_serializes_restart_generations(tmp_path: Path) -> None` — Restart stops the current service before starting its replacement.

### `packages/exactus_mcp/test_wakeup.py`

Validate signed Exactus MCP wake-up behavior.

- `class FakeResponse` — Return one synthetic HTTP response body.
  - Fields: `payload: bytes`
  - `read(self) -> bytes` — Return the configured response body.
- `class FakeOpener` — Return queued bodies and capture MantleDB requests.
  - `requests` = `field(default_factory=list)`
  - Fields: `bodies: list[bytes]`
- `class FakeWakeStore` — Return one deterministic signed command and capture responses.
  - `responses` = `field(default_factory=list)`
  - Fields: `command: WakeCommand`
  - `retrieve_command(self) -> WakeCommand` — Return the configured command.
  - `publish_response(self, *, response: WakeResponse) -> None` — Capture a ready response.
- `class FakeLauncher` — Record service launch requests.
  - `calls` = `0`
  - `start_and_resolve(self) -> str` — Return one deterministic MCP URL.
- `test_signed_command_is_verified_and_ready_response_is_bound() -> None` — Only the matching fresh signed command produces a signed response.
- `test_stale_command_is_rejected() -> None` — A valid signature cannot be replayed outside the freshness window.
- `test_watcher_deduplicates_completed_uuid(tmp_path: Path) -> None` — One UUID starts the fixed service no more than once.
- `test_keep_running_starts_service_before_duplicate_check(tmp_path: Path) -> None` — Remote mode supervises the service even without a fresh wake UUID.
- `test_discovered_origin_gets_mcp_path() -> None` — Normalize an emitted public origin to the MCP endpoint.
- `test_wake_response_requires_absolute_https() -> None` — A wake response URL must be absolute, clean HTTPS.
- `test_retrieve_command_rejects_malformed_documents(document: str, match: str) -> None` — Malformed, unsigned, or non-canonical commands are rejected.
- `test_transport_failures_surface_as_wake_errors() -> None` — Transport and JSON failures become ``WakeError`` reports.
- `test_state_store_roundtrip_and_invalid_content(tmp_path: Path) -> None` — Persisted UUIDs round-trip; absent or invalid state is empty.
- `test_launcher_rejects_invalid_startup_settings() -> None` — Empty commands, bad timeouts, and bad paths are rejected.
- `class FakeStdout` — Queue output lines for a synthetic child process.
  - `__init__(self, *, lines: list[bytes], hang: bool=False) -> None` — Configure scripted output.
  - `readline(self) -> bytes` — Return the next scripted line or end-of-file.
- `class FakeProcess` — Child-process double with scripted output and exit behavior.
  - `__init__(self, *, lines: list[bytes] | None, code: int=0, hang_wait: bool=False) -> None` — Configure scripted process behavior.
  - `wait(self) -> int` — Block until termination and return the exit status.
  - `terminate(self) -> None` — Record termination and report the scripted exit status.
  - `kill(self) -> None` — Record a forced kill and unblock pending waits.
- `fake_exec_factory(*, process: FakeProcess, calls: list[tuple[object, ...]]) -> Callable[..., Coroutine[object, object, FakeProcess]]` — Build a ``create_subprocess_exec`` double returning one process.
- `test_launcher_discovers_url_and_reuses_process(monkeypatch: pytest.MonkeyPatch) -> None` — A launched service publishes its URL once and stays running.
- `test_launcher_reports_discovery_failures(monkeypatch: pytest.MonkeyPatch) -> None` — Missing output, early exit, and timeouts become ``WakeError``.
- `test_launcher_close_kills_unresponsive_process(monkeypatch: pytest.MonkeyPatch) -> None` — A child ignoring ``terminate`` is killed after the grace period.
- `test_watcher_run_retries_with_backoff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Polling failures are logged and retried with doubled delays.

### `packages/exactus_mcp/test_wakeup_cli.py`

Validate the wake watcher command-line lifecycle actions.

- `class FakeManager` — Record native watcher lifecycle operations.
  - `running` = `False`
  - `installs` = `field(default_factory=list)`
  - `uninstalls` = `0`
  - Fields: `secrets_path: Path`
  - `install(self, *, program_arguments: tuple[str, ...], secrets: WatcherSecrets) -> StartupStatus` — Record an installation request.
  - `uninstall(self) -> StartupStatus` — Record an uninstall request.
  - `status(self) -> StartupStatus` — Return the configured running state.
- `clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Isolate environment defaults and project configuration.
- `test_main_status_reports_state(monkeypatch: pytest.MonkeyPatch) -> None` — The status action prints lifecycle state and reflects running.
- `test_main_status_stopped_returns_nonzero(monkeypatch: pytest.MonkeyPatch) -> None` — A stopped watcher reports nonzero and hides the PID.
- `test_main_uninstall_removes_service(monkeypatch: pytest.MonkeyPatch) -> None` — The uninstall action removes the native service definition.
- `test_main_install_persists_secret_free_arguments(monkeypatch: pytest.MonkeyPatch) -> None` — Install persists a watcher command without inline secrets.
- `test_main_run_validates_and_starts_watcher(monkeypatch: pytest.MonkeyPatch) -> None` — The run action validates configuration before starting the watcher.
- `test_main_run_loads_secrets_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A private secrets file supplies credentials without shell history.
- `test_main_reports_validation_failures(arguments: tuple[str, ...], match: str, monkeypatch: pytest.MonkeyPatch) -> None` — Invalid lifecycle input is reported without a traceback.
- `test_main_lists_effective_config(monkeypatch: pytest.MonkeyPatch) -> None` — A bare --config prints effective settings with secrets redacted.
- `test_main_loads_json_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A JSON config file seeds watcher defaults before CLI overrides.
- `test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None` — Interrupting the watcher exits cleanly with status zero.

### `packages/extended_selector/__init__.py`

Tests of ``exactus/packages/extended_selector``.


### `packages/extended_selector/test_examples.py`

Exercise the bundled ExtendedSelector demo launcher with stubs.

- `test_start_demo_reuses_an_existing_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A recorded server short-circuits the spawn path entirely.
- `test_start_demo_spawns_and_waits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A fresh spawn waits for readiness and returns the demo URL.
- `test_start_demo_terminates_a_server_that_never_readies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A failed readiness check kills the spawned server and raises.
- `test_main_serves_then_opens_and_closes_the_browser(monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` launches the demo, opens the session, and returns zero.

### `packages/external/__init__.py`

Test package.


### `packages/external/test_cli.py`

Drive ``exactus --external`` inventory and dispatch in-process.

- `test_inventory_groups_versions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A bare ``--external`` prints OS/Python/Node version groups.
- `test_dispatch_forwards_command_line(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--external TOOL ARGS`` reaches the launcher verbatim.
- `test_missing_tool_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Unknown tool names fail before any dispatch happens.
- `test_launcher_meta_commands_dispatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Launcher subcommands like ``list-tools`` pass membership checks.
- `test_dispatch_status_passthrough(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The tool's own exit status is returned to the caller.
- `test_no_bundle_errors(monkeypatch: pytest.MonkeyPatch) -> None` — A missing toolchain reports an error without dispatching.
- `test_missing_manifest_lists_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A launcher without a manifest cannot render an inventory.
- `test_missing_manifest_defers_to_launcher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Without a manifest the launcher's own validation decides.
- `test_main_routes_external_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``exactus --external`` reaches the external dispatcher.
- `test_real_bundle_lists_tools(capfd: pytest.CaptureFixture[str]) -> None` — The real host bundle answers ``--external list-tools``.
- `test_real_bundle_runs_tool() -> None` — The real host bundle runs a binary tool end to end.

### `packages/group_final/__init__.py`

Test the exactus/packages/group_final Final constants refactoring.


### `packages/group_final/test_group_final.py`

Exercise the group_final refactoring: discovery, plans and rewrites.

- `class FakeStdout` — Stand-in stream that reports itself as a terminal.
  - `__init__(self) -> None` — Initialize the captured writes buffer.
  - `isatty() -> bool` — Report terminal status.
  - `write(self, text: str) -> int` — Record written text.
  - `flush(self) -> None` — Accept flush requests without side effects.
- `class PrintRecorder` — Stand-in for the module ``_print`` helper capturing messages.
  - `__init__(self) -> None` — Initialize the captured message list.
- `record_print(*, monkeypatch: pytest.MonkeyPatch) -> PrintRecorder` — Patch the module ``_print`` helper with a recorder.
- `make_refactor(*, root: Path, dry_run: bool=True) -> FinalConstantsRefactor` — Build a refactor rooted at ``root``.
- `assignment(*, source: str) -> AnnAssign` — Parse a single annotated assignment statement.
- `write_source(*, root: Path, relative: str, source: str) -> Path` — Create ``relative`` below ``root`` with ``source`` content.
- `test_print_writes_and_flushes() -> None` — The print helper joins arguments and flushes the stream.
- `test_paint_wraps_or_passes_through() -> None` — ANSI painting wraps text only when enabled.
- `test_progress_disabled_without_terminal() -> None` — Non-terminal output produces no progress escape sequences.
- `test_progress_renders_on_terminal(monkeypatch: pytest.MonkeyPatch) -> None` — Terminal output draws the bar with ANSI colors.
- `test_progress_no_color_keeps_plain_bar(monkeypatch: pytest.MonkeyPatch) -> None` — ``NO_COLOR`` keeps the bar but drops ANSI styling.
- `test_name_collector_loads_only() -> None` — Loaded names are collected while stored names are skipped.
- `test_uppercase_convention() -> None` — Uppercase detection accepts constant-style names only.
- `test_is_final_annotations() -> None` — Final annotation detection covers Name, Subscript and Attribute.
- `test_candidate_accepts_uppercase_final() -> None` — Supported statements produce a binding with their index.
- `test_candidate_rejects_unsupported_statements() -> None` — Non-Final, lowercase, valueless and non-assign forms are skipped.
- `test_is_excluded_matches_default_patterns() -> None` — Every default exclusion pattern rejects its subtree.
- `test_python_files_prunes_excluded_trees(tmp_path: Path) -> None` — Discovery returns only non-excluded Python files, sorted.
- `test_python_files_prunes_renamed_report_trees(tmp_path: Path) -> None` — Report trees are pruned by fingerprint, not by directory name.
- `test_parse_trees_skips_vanished_files(tmp_path: Path) -> None` — Sources deleted between collection and parsing are skipped.
- `test_module_name_resolution(tmp_path: Path) -> None` — Paths resolve to dotted names with ``__init__`` stripped.
- `test_top_level_definitions(tmp_path: Path) -> None` — Definitions map names to body indices for every form.
- `test_required_insertion_index_follows_dependencies(tmp_path: Path) -> None` — Insertion lands after the latest top-level dependency.
- `test_used_before_detects_early_reference(tmp_path: Path) -> None` — Early loads are detected unless the statement is ignored.
- `plan_for(*, refactor: FinalConstantsRefactor, source: str) -> ModulePlan | None` — Build a plan for module source text.
- `test_plan_none_without_candidates(tmp_path: Path) -> None` — Modules without Final constants produce no plan.
- `test_plan_groups_movable_constants(tmp_path: Path) -> None` — A safe module plans every uppercase Final constant.
- `test_plan_uses_first_safe_contiguous_group(tmp_path: Path) -> None` — A single class replaces one contiguous declaration block in place.
- `test_plan_does_not_move_across_intervening_statements(tmp_path: Path) -> None` — Separated constants never move across intervening statements.
- `test_module_aliases_for_import_forms(tmp_path: Path) -> None` — Import aliases map plain, aliased and dotted module imports.
- `test_rewrite_imports_splits_moved_names() -> None` — Direct imports of moved constants become Constants imports.
- `test_local_reference_transformer() -> None` — Moved constant loads are qualified; stores and others stay.
- `test_qualified_reference_transformer() -> None` — Module-qualified references gain the Constants hop.
- `test_direct_import_reference_transformer() -> None` — Directly imported names qualify through Constants.
- `test_run_dry_run_reports_without_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Dry-run reports would-be changes and leaves files untouched.
- `test_run_apply_rewrites_local_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Apply mode groups constants and rewrites local references.
- `test_run_apply_rewrites_cross_module_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Direct and qualified imports follow moved constants.
- `test_run_preserves_statement_order_and_annotation_dependencies(tmp_path: Path) -> None` — The generated class replaces its declaration at the same boundary.
- `test_run_skips_locally_shadowed_candidate(tmp_path: Path) -> None` — A parameter or local binding prevents unsafe global replacement.
- `test_run_rewrites_relative_direct_imports(tmp_path: Path) -> None` — Package-relative imports follow a moved constant.
- `test_run_leaves_star_import_provider_unchanged(tmp_path: Path) -> None` — A star-imported provider is excluded instead of breaking its API.
- `test_run_avoids_constants_and_final_name_collisions(tmp_path: Path) -> None` — Generated imports use aliases when consumer or provider names clash.
- `test_run_skips_provider_when_import_name_is_rebound(tmp_path: Path) -> None` — A module-level consumer rebind prevents an ambiguous rewrite.
- `test_run_leaves_partial_and_excluded_files_alone(tmp_path: Path) -> None` — Unsafe constants stay and excluded files are never parsed.
- `test_run_strips_private_prefix_from_member_names(tmp_path: Path) -> None` — Private-prefixed constants lose leading underscores as members.
- `test_run_renames_private_references_between_members(tmp_path: Path) -> None` — Later members use the public spelling of an earlier private member.
- `test_run_skips_underscore_member_collisions(tmp_path: Path) -> None` — Constants colliding after prefix stripping stay module level.
- `test_run_merges_typing_imports_in_member_order(tmp_path: Path) -> None` — New typing names merge into existing imports in isort order.
- `test_run_inserts_typing_import_when_absent(tmp_path: Path) -> None` — Qualified Final annotations gain a sorted bare typing import.
- `test_run_keeps_final_import_when_still_used(tmp_path: Path) -> None` — A remaining Final reference preserves the typing import name.
- `test_run_places_class_after_docstring_and_imports(tmp_path: Path) -> None` — The Constants class lands after the docstring and imports.
- `test_run_empty_directory(tmp_path: Path) -> None` — An empty tree reports zero counts and prints no updates.
- `test_summary_table_labels_modes() -> None` — The summary table switches the changed label per mode.
- `test_summary_colored_on_terminal(monkeypatch: pytest.MonkeyPatch) -> None` — Terminal output decorates the summary with ANSI codes.
- `test_cli_parser_defaults_and_dry_run(tmp_path: Path) -> None` — The parser defaults to apply mode and honors --dry-run.
- `test_run_rewrites_legacy_reference_to_snake_case_member(tmp_path: Path) -> None` — A stale uppercase reference follows an already-normalized provider.
- `test_cli_main_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The CLI entrypoint parses argv and runs the refactor.
- `test_main_delegates_to_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The module main forwards to the CLI and returns its status.
- `test_main_module_executes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``python -m group_final`` exits with the CLI status.
- `test_example_dry_run_completes() -> None` — The bundled example finishes a dry-run demonstration.
- `test_examples_main_module_executes(monkeypatch: pytest.MonkeyPatch) -> None` — ``python -m group_final.examples`` exits successfully.
- `test_run_merges_constants_into_existing_class(tmp_path: Path) -> None` — Module constants join an existing generated ``Constants`` class.
- `test_run_skips_merging_into_unrelated_constants(tmp_path: Path) -> None` — A non-generated ``Constants`` class still blocks the rewrite.
- `test_run_skips_member_name_collision_on_merge(tmp_path: Path) -> None` — A constant whose member name already exists is left alone.

### `packages/guard/__init__.py`

Tests for exactus.packages.guard.


### `packages/guard/test_example_run.py`

Cover the bundled ``guard`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'guard' /...`
- `class CleanupStub` — Stand-in for the real cleanup summary.
  - `observed` = `()`
  - `terminated` = `()`
  - `killed` = `()`
  - `survivors` = `()`
- `class ResultStub` — Stand-in for the real ``SupervisionResult``.
  - `exit_code` = `0`
  - `cleanup` = `field(default_factory=CleanupStub)`
  - `observed` = `()`
  - `survivors` = `()`
- `class ProcessStub` — Stand-in for a spawned child process.
  - `pid` = `4242`
- `class GuardStub` — Stand-in for the real ``ProcessGuard`` context manager.
  - `__init__(self, *, poll_interval: float, grace_seconds: float) -> None` — Record the guard timing options.
- `class SupervisorStub` — Stand-in for the real ``ProcessSupervisor``.
  - `__init__(self, **kwargs: object) -> None` — Accept every supervisor option without acting.
  - `run() -> ResultStub` — Return a synthetic supervision result.
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry with stubbed processes.

### `packages/guard/test_guard.py`

Behavioral tests for exactus.packages.guard.

- `expect(*, condition: bool, message: str) -> None` — Fail when a behavioral expectation is false.
- `class TestHelpers` — Provide process lifecycle assertions.
  - `assert_dead(*, pid: int, timeout: float=5.0) -> None` — Assert that a process disappears before a deadline.
- `class TestProcessSupervisor` — Verify external supervision.
  - `test_returns_target_exit_code() -> None` — Preserve a target's natural exit status.
  - `test_kills_nested_tree() -> None` — Discover and clean a nested descendant tree.
- `class TestProcessGuard` — Verify in-process guarding.
  - `test_context_cleans_child() -> None` — Terminate a child that outlives its guarded block.
  - `test_context_preserves_exception() -> None` — Never suppress an exception from guarded application code.
- `class TestExamples` — Verify every supported example invocation.
  - `test_module_example() -> None` — Run examples through Python's module execution mode.
  - `test_package_path_example() -> None` — Run the examples package by directory path.
  - `test_script_example() -> None` — Run the executable example script directly.

### `packages/http_process/__init__.py`

Tests of ``exactus/packages/http_process``.


### `packages/http_process/test_example_run.py`

Cover the bundled ``http_process`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'http_proc...`
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry with a stub runner.

### `packages/http_process/test_examples.py`

Exercise the bundled ``http_process`` examples end to end.

- `test_example_run_starts_discovers_and_stops_a_server(monkeypatch: pytest.MonkeyPatch) -> None` — The launch example discovers a real ``http.server`` instance.
- `test_inspect_existing_reports_the_endpoint(monkeypatch: pytest.MonkeyPatch) -> None` — The inspection example prints a result for ``127.0.0.1:8000``.

### `packages/http_process/test_http_process.py`

Smoke tests for the http_process package.

- `test_address_helpers() -> None` — Validate address classification and URL construction.
- `test_started_process_uses_the_requested_working_directory(tmp_path: Path) -> None` — Start a command in a chosen folder and detect the port it opens.

### `packages/http_process/test_main.py`

Cover the ``exactus.packages.http_process`` CLI and process wait paths.

- `class Constants` — Group module-level constants.
  - `loopback` = `'127.0.0.1'`
- `test_cli_inspect_reports_closed_port(monkeypatch: pytest.MonkeyPatch) -> None` — The inspect mode returns one when nothing serves HTTP.
- `test_cli_inspect_reports_live_server(monkeypatch: pytest.MonkeyPatch) -> None` — The inspect mode reports a live server and its owning process.
- `test_cli_run_discovers_spawned_http_server(monkeypatch: pytest.MonkeyPatch) -> None` — The command mode spawns, discovers, and stops an HTTP server.
- `test_main_delegates_to_cli_run(monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` forwards to ``Cli.run``.
- `test_wait_for_http_requires_a_started_process() -> None` — Waiting without a managed process raises ``RuntimeError``.
- `test_wait_for_listener_requires_a_started_process() -> None` — The TCP variant reports the same missing-process failure.
- `test_wait_for_http_reports_early_process_exit() -> None` — A process that exits before serving raises ``RuntimeError``.
- `test_wait_for_listener_times_out_without_a_socket() -> None` — A process that never listens raises ``TimeoutError``.
- `test_wait_for_times_out_on_a_closed_port() -> None` — Waiting for HTTP on a closed port raises ``TimeoutError``.
- `test_stop_terminates_a_managed_process() -> None` — ``stop`` terminates the spawned tree and clears the handle.
- `test_stop_is_safe_without_a_process() -> None` — ``stop`` is a no-op when nothing was started.
- `test_inspect_reports_process_ownership() -> None` — Inspecting a live server resolves its owning local process.
- `test_wait_for_http_discovers_and_describes_a_spawned_server() -> None` — End-to-end discovery exercises listeners, servers, and lookups.
- `test_constructor_rejects_empty_command() -> None` — An empty command list raises ``ValueError``.
- `test_start_requires_a_command_and_single_use() -> None` — ``start`` reports missing commands and double starts.
- `test_inspect_rejects_an_invalid_port() -> None` — Out-of-range ports raise ``ValueError``.

### `packages/markdown/__init__.py`

Tests for the Markdown template engine.


### `packages/markdown/test_cli.py`

The command line renders templates and reports failures with exit 2.

- `test_writes_output_file(tmp_path: Path) -> None` — ``-o`` writes the rendered Markdown.
- `test_prints_to_stdout_by_default(tmp_path: Path) -> None` — Without ``-o`` the Markdown goes to the output stream.
- `test_validate_only_and_context_output(tmp_path: Path) -> None` — ``--validate-only`` renders nothing; the context can be dumped.
- `test_errors_exit_two(tmp_path: Path) -> None` — Missing files and strict undefined variables exit with code 2.
- `test_bad_json_and_non_object_mapping_exit_two(tmp_path: Path) -> None` — Malformed JSON and a non-object mapping are reported with exit 2.
- `test_template_root_allows_includes_from_other_directories(tmp_path: Path) -> None` — ``--template-root`` adds a directory templates may include from.
- `test_default_streams_are_resolved_at_call_time(tmp_path: Path) -> None` — Redirecting stdout and stderr captures the default streams.

### `packages/markdown/test_engine.py`

The engine renders sandboxed Jinja2 templates from mapped JSON.

- `class Constants` — Group module-level constants.
  - `data` = `{'project': {'name': 'Exactus'}, 'tasks': [{'t': 'A'}, {'t': 'B'}]}`
- `test_mapping_feeds_the_template(tmp_path: Path) -> None` — Mapped names and the original ``source`` are both available.
- `test_inheritance_includes_and_filters(tmp_path: Path) -> None` — Layouts, partials and Markdown filters work together.
- `test_strict_undefined_raises_and_lenient_renders(tmp_path: Path) -> None` — Strict mode reports missing variables; lenient mode blanks them.
- `test_syntax_errors_are_wrapped(tmp_path: Path) -> None` — Jinja2 syntax errors surface as TemplateEngineError.
- `test_sandbox_blocks_unsafe_attribute_access(tmp_path: Path) -> None` — Templates cannot walk to ``__class__`` and friends.
- `test_template_outside_roots_is_rejected(tmp_path: Path) -> None` — Only templates under a configured root can be rendered.
- `test_render_report_accepts_paths_and_objects(tmp_path: Path) -> None` — ``render_report`` loads JSON paths and takes objects as-is.
- `test_render_report_extra_roots(tmp_path: Path) -> None` — Partials can live in an extra template root.
- `test_load_json_passes_values_through(tmp_path: Path) -> None` — Non-path values are returned unchanged.
- `test_render_report_rejects_non_object_mapping(tmp_path: Path) -> None` — A mapping that is not a JSON object raises MappingError.
- `test_render_report_rejects_non_object_mapping_file(tmp_path: Path) -> None` — A mapping file holding a JSON array raises MappingError.
- `test_symlink_include_outside_roots_is_refused(tmp_path: Path) -> None` — An include symlinked out of the roots is not rendered.
- `test_same_named_template_in_second_root_is_rendered(tmp_path: Path) -> None` — The file that was asked for wins over an earlier root's copy.
- `test_runtime_errors_are_wrapped(tmp_path: Path, text: str) -> None` — Runtime failures inside templates become TemplateEngineError.
- `test_bad_json_files_are_wrapped(tmp_path: Path) -> None` — Unreadable or malformed JSON raises TemplateEngineError.

### `packages/markdown/test_errors.py`

The engine exposes one exception tree rooted at TemplateEngineError.

- `test_mapping_error_is_a_template_engine_error() -> None` — Callers can catch every engine failure with one except clause.

### `packages/markdown/test_example_run.py`

Cover the bundled ``markdown`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'markdown'...`
  - `assets` = `example.parent / 'assets'`
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry against golden output.
- `test_example_module_reports_a_golden_mismatch(monkeypatch: pytest.MonkeyPatch) -> None` — A render that differs from the golden file exits with one.

### `packages/markdown/test_examples.py`

The generic engine example renders to its checked-in expected output.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `examples` = `root / 'exactus' / 'packages' / 'markdown' / 'examples' / 'assets'`
- `test_generic_example_matches_golden() -> None` — The example template reproduces the golden Markdown exactly.
- `test_run_script_returns_zero() -> None` — The runnable example renders the bundle and matches its golden.

### `packages/markdown/test_filters.py`

Markdown filters format values for templates.

- `test_text_escape_and_code() -> None` — Scalars stringify, structures dump as JSON, escapes apply.
- `test_table_preserves_dunder_paths_and_titles() -> None` — Dunder filenames stay literal instead of becoming Markdown emphasis.
- `test_codeblock_bullets_numbered() -> None` — Fences and lists render one line per item.
- `test_table_with_columns_escapes_cells() -> None` — Pipes and newlines in cells cannot break the table.
- `test_table_defaults_and_empty() -> None` — Without columns the first row's keys head the table.
- `test_json_filters_and_registration() -> None` — JSON filters keep unicode; ``register`` installs every filter.
- `test_table_filter_accepts_positional_columns_from_templates() -> None` — Jinja2 passes the rows and column specs to ``md_table`` positionally.
- `test_cell_escapes_pipes_and_every_line_break() -> None` — ``md_cell`` escapes ``|`` and turns CR, LF and CRLF into ``<br>``.
- `test_table_normalizes_crlf_cells_and_pipe_headers() -> None` — Table cells and headers are single-line and pipe-safe.

### `packages/markdown/test_mapping.py`

Mapping specs reshape a source document into a template context.

- `class Constants` — Group module-level constants.
  - `source` = `{'project': {'name': 'Exactus', 'owner': None}, 'tasks': [{'id': 1, 'titl...`
- `class StubRenderer` — Renderer that echoes its inputs instead of using Jinja2.
- `test_paths_literals_and_structures() -> None` — Strings are paths; plain dicts and lists map element-wise.
- `test_default_required_and_default_on_null() -> None` — Defaults fill absent or null paths; required paths must exist.
- `test_when_coalesce_and_merge() -> None` — Conditionals, fallbacks and object merges compose.
- `test_where_sort_each_pipeline() -> None` — Filter, numeric sort and projection run in a fixed order.
- `test_sort_is_numeric_and_text_is_case_insensitive() -> None` — Numbers sort by value, strings sort casefolded after numbers.
- `test_unique_slice_flatten_pick_omit_join() -> None` — List and object reshaping directives.
- `test_template_and_template_each() -> None` — Nested templates render once or once per item.
- `test_wrong_value_kinds_name_the_directive() -> None` — Directives report which one received the wrong value type.
- `test_context_exposes_source_and_data() -> None` — The template context always carries the original document.

### `packages/markdown/test_operators.py`

Operator edge cases for non-matching operand types.

- `test_contains_on_strings_and_scalars() -> None` — ``contains`` handles strings and rejects scalar containers.
- `test_in_on_strings_and_scalars() -> None` — ``in`` handles string operands and rejects scalar operands.
- `test_regex_requires_strings() -> None` — ``regex`` is false when either side is not a string.
- `test_type_is_distinguishes_bool_from_int() -> None` — ``type_is`` treats booleans as ``bool`` only.
- `test_ordering_rejects_bool_and_mixed_types() -> None` — Ordering operators are false for booleans and mixed operand types.

### `packages/markdown/test_paths.py`

JSON paths resolve against a current value or the document root.

- `class Constants` — Group module-level constants.
  - `root` = `{'a': {'b': [10, 20]}, 'k': 1, 'n': None}`
- `test_nested_and_indexed_path() -> None` — Dotted keys and ``[n]`` indexes are walked in order.
- `test_empty_and_dot_return_current() -> None` — Empty and ``.`` paths mean the current value.
- `test_dollar_returns_root_and_anchor_leaves_current() -> None` — ``$`` and ``$.`` anchor at the root even from a nested value.
- `test_null_value_is_found() -> None` — A present key holding null is a hit, not a miss.
- `test_missing_key_index_and_type_mismatch_are_misses() -> None` — Absent keys, bad indexes and wrong container kinds miss.

### `packages/markdown/test_predicates.py`

Predicate specs filter list items and drive conditional mapping.

- `class Constants` — Group module-level constants.
  - `row` = `{'name': 'alpha', 'score': 7, 'tags': ['x', 'y'], 'empty': [], 'none': No...`
- `test_comparison_operators() -> None` — Numeric and equality operators compare the resolved value.
- `test_membership_and_string_operators() -> None` — Containment, prefix, suffix and regex operators work on strings.
- `test_truthiness_and_type_operators() -> None` — Truthy, empty and type operators inspect the value itself.
- `test_presence_operators_and_missing_paths() -> None` — ``exists``/``missing`` test presence; others fail on absence.
- `test_logic_and_shorthand() -> None` — Boolean combinators, literals and equality shorthand compose.
- `test_invalid_specs_raise_mapping_error() -> None` — Bad predicate shapes and operators are reported, not ignored.

### `packages/meaningful/__init__.py`

Test package.


### `packages/meaningful/test_analyzer.py`

Behavioral tests for the single-file test-necessity classifier.

- `expect(*, condition: bool) -> None` — Fail when a test condition is false.
- `test_classification_levels(*, tmp_path: Path, name: str, source: str, expected: UnitTestLevel) -> None` — Classify representative structural and behavioral source files.
- `test_metrics_json_and_render(*, tmp_path: Path) -> None` — Expose stable human and machine-readable reports.
- `test_non_python_file_is_rejected(*, tmp_path: Path) -> None` — Reject paths without a Python suffix.
- `test_syntax_error_is_preserved(*, tmp_path: Path) -> None` — Surface Python syntax errors to callers.

### `packages/meaningful/test_api_cli.py`

Tests for the object-oriented API, parallel runs, metadata, and CLI.

- `class Constants` — Group module-level constants.
  - `expected_file_count` = `8`
  - `expected_callback_count` = `6`
  - `expected_percent` = `100.0`
  - `expected_workers` = `3`
  - `expected_source_lines` = `16`
  - `invalid_exit_code` = `2`
- `expect(*, condition: bool) -> None` — Fail when a test condition is false.
- `test_parallel_run_metadata_and_progress(*, tmp_path: Path) -> None` — Account for every finished worker and aggregate run metadata.
- `test_javascript_behavior_is_classified_as_needing_tests(*, tmp_path: Path) -> None` — Keep dynamically loaded JavaScript behavior in the actionable set.
- `test_policy_thresholds_evidence_and_context(*, tmp_path: Path) -> None` — Expose scores and final-level source evidence through data models.
- `test_resolution_inputs_and_filters(*, tmp_path: Path) -> None` — Support strings, Paths, folders, globs, include, and exclude.
- `test_failures_are_accounted_and_callback_isolated(*, tmp_path: Path) -> None` — Keep failed workers and callback errors from corrupting a run.
- `test_functional_api_and_overrides(*, tmp_path: Path) -> None` — Support functional convenience and per-run configuration overrides.
- `test_validation_errors(*, tmp_path: Path) -> None` — Reject invalid workers, policies, and literal selectors.
- `test_cli_json_output_file_and_errors(*, tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None` — Keep CLI a thin JSON adapter over the run model.
- `test_examples_execute(capfd: pytest.CaptureFixture[str]) -> None` — Exercise the documented Python and CLI examples.

### `packages/meaningful/test_example_run.py`

Cover the bundled ``meaningful`` CLI example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'meaningfu...`
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry with a stubbed CLI.

### `packages/meaningful/test_meaningful_sources.py`

Execute package entry points required by meaningful coverage policy.

- `test_packages_cli_entrypoint(monkeypatch: pytest.MonkeyPatch, module: str, arguments: tuple[str, ...], expected: int) -> None` — Execute one package CLI through its real ``__main__`` module.
- `test_packages_support_module_executes(module: str) -> None` — Execute one support module without invoking its guarded CLI.
- `test_rename_project_entrypoint_bootstraps(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the rename-project bootstrap and delegate to ``main``.

### `packages/model/__init__.py`

Tests of the `exactus/packages/model/` SQLite model.


### `packages/model/test_examples.py`

Coverage for the ``exactus/packages/model/examples`` demonstration.

- `test_example_main_runs_the_in_memory_demo(monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` compiles the schema, executes it, and prints the row.
- `test_example_run_py_executes_as_script() -> None` — Execute ``run.py`` with ``__name__`` equal to ``__main__``.
- `test_examples_main_module_runs_the_demo() -> None` — Execute ``examples/__main__.py`` as the ``__main__`` module.

### `packages/model/test_sqlite_architecture.py`

Architectural regression checks for application SQLite access.

- `class Constants` — Group module-level constants.
  - `application` = `('exactus/__main__.py', 'exactus/tools/common/pipeline_supervisor.py', 'e...`
  - `sql_pattern` = `compile_pattern(pattern='^\\s*(?:SELECT\\s+.+\\s+FROM\\s+|INSERT\\s+(?:OR...`
- `test_application_does_not_bypass_database_layer() -> None` — Keep direct sqlite3 execution out of application modules.
- `test_application_has_no_authored_sql_literals() -> None` — Prevent SQL grammar text from re-entering production modules.
- `test_raw_sql_escape_hatch_is_allowlisted() -> None` — Permit external schema recreation at exactly one reviewed call site.
- `test_application_never_compiles_sql_itself() -> None` — Keep compiler invocation inside the SQLite boundary.

### `packages/model/test_sqlite_hardening.py`

Hardening and torture tests for the structural SQLite layer.

- `test_schema_round_trip_and_drift_detection() -> None` — Verify a freshly created table matches its dataclass schema.
- `test_cardinality_scalar_and_batch_operations() -> None` — Exercise scalar lookups, batch inserts, and arity errors.
- `test_nested_transactions_use_savepoints() -> None` — Roll back only the inner unit when a nested transaction fails.
- `test_trace_never_contains_parameter_values() -> None` — Report only parameter counts, never values, in trace events.
- `test_constraint_translation_preserves_cause() -> None` — Wrap sqlite3 integrity failures and keep the original cause.
- `test_codec_is_explicit_and_bidirectional() -> None` — Round-trip a value through an explicit codec pair.
- `test_expression_boolean_evaluation_is_rejected() -> None` — Forbid Python truthiness checks on SQL expressions.
- `test_empty_in_has_deterministic_sqlite_semantics() -> None` — Compile an empty IN list to a portable false predicate.
- `test_randomized_identifier_and_value_round_trip() -> None` — Round-trip exotic identifiers and values through the full stack.
- `test_structural_ddl_commands_and_error_paths() -> None` — Drive DDL helpers, fixed commands, and their error paths.
- `test_decode_many_exactly_one_and_schema_drift() -> None` — Decode rows, require exactly one, and report schema drift.

### `packages/model/test_sqlite_model.py`

Behavioral tests for the typed SQLite compiler.

- `test_registry_statements_execute_end_to_end() -> None` — Insert and heartbeat a registry run through compiled statements.
- `test_upsert_preserves_key_and_updates_mutable_values() -> None` — Upsert a work row twice and keep the last mutable values.
- `test_dynamic_identifier_operations_are_safe() -> None` — Quote hostile identifiers in every structural DDL operation.
- `test_drop_rejects_non_schema_object_kinds() -> None` — Reject DROP operations outside the supported object kinds.
- `test_identifier_quoting_rejects_invalid_and_escapes_quotes() -> None` — Escape embedded quotes and reject empty or NUL identifiers.
- `test_dataclass_schema_maps_optional_and_composite_primary_key() -> None` — Derive composite keys and optional columns from a dataclass.
- `test_generated_kill_query_is_executable_sql() -> None` — Execute the generated live-process query against the registry.
- `test_identifier_torture_and_compiler_determinism() -> None` — Compile exotic identifiers deterministically with quoting.
- `test_database_decode_and_transaction() -> None` — Decode a dataclass row inside an explicit transaction.
- `test_external_sql_escape_hatch_rejects_empty() -> None` — Reject blank external schema SQL at the escape hatch.
- `test_null_predicates_and_transaction_rollback() -> None` — Roll back a transaction and compile IS NULL predicates.

### `packages/organize/__init__.py`

Tests for the organize package.


### `packages/organize/test_javascript.py`

Tests for standalone JavaScript class-method organization.

- `class Constants` — Group module-level constants.
  - `fake_espree` = `dedent(text='\n        "use strict";\n\n        const method = (\n...`
- `expect(*, condition: bool) -> None` — Fail when a test condition is false.
- `test_javascript_reorders_and_is_idempotent(tmp_path: Path) -> None` — Reorder JavaScript through the standalone public API.
- `test_javascript_reports_organizer_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Surface organizer exit failures and malformed JSON payloads.
- `test_javascript_resolves_global_espree_or_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Fall back to global npm modules before giving up on Espree.
- `test_javascript_rejects_malformed_payloads() -> None` — Reject organizer payloads that are not complete objects.

### `packages/organize/test_organize.py`

Tests for source-preserving Python class method organization.

- `expect(*, condition: bool) -> None` — Fail when a test condition is false.
- `method_names(*, source: str, class_name: str='Example') -> list[str]` — Return direct method names from a class.
- `test_reorders_every_category_stably() -> None` — Place every supported method category in canonical order.
- `test_preserves_decorators_annotations_docstrings_and_comments() -> None` — Move complex method text without reconstructing its syntax.
- `test_property_family_is_adjacent_and_accessor_order_is_normalized() -> None` — Keep a property getter, setter, and deleter together.
- `test_qualified_binding_decorators_are_recognized() -> None` — Recognize terminal names of qualified binding decorators.
- `test_blank_line_separated_comment_remains_anchored() -> None` — Do not attach a separated section comment to a moving method.
- `test_direct_comment_moves_with_method() -> None` — Move a directly adjacent comment together with its method.
- `test_nested_class_is_reordered_but_function_local_class_is_not() -> None` — Transform structural nested classes without touching runtime locals.
- `test_idempotent_and_already_ordered_source_is_byte_identical() -> None` — Return byte-identical source once canonical order is reached.
- `test_single_method_and_empty_class_are_unchanged() -> None` — Leave classes with fewer than two direct methods untouched.
- `test_file_api_reorders_and_reports_change(tmp_path: Path) -> None` — Support preview and idempotent in-place file writing.
- `test_invalid_python_propagates_syntax_error() -> None` — Reject invalid input rather than attempting a partial rewrite.
- `test_metrics_report_moved_methods_classes_and_lines() -> None` — Aggregate moved-method counts for one reordered class.
- `test_metrics_report_zero_moves_for_ordered_source() -> None` — Report zero movement when the source is already ordered.
- `test_custom_order_reorders_by_given_categories() -> None` — Reorder methods using a caller-provided category order.
- `test_validate_order_rejects_incomplete_and_unknown() -> None` — Reject orders missing categories or naming unknown categories.
- `test_configured_order_reads_pyproject(tmp_path: Path) -> None` — Resolve [tool.organize] order from the nearest pyproject.
- `test_configured_order_defaults_without_section(tmp_path: Path) -> None` — Return the canonical order when no [tool.organize] section exists.
- `test_configured_order_rejects_invalid_pyproject(tmp_path: Path) -> None` — Reject a [tool.organize] order that is not a permutation.
- `test_main_dry_run_reports_metrics_without_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Report would-change metrics under --dry-run without writing.
- `test_main_expands_globs_and_applies_exclude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Expand glob arguments and skip --exclude matches.
- `test_main_order_flag_overrides_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Apply the --order category list instead of the default.
- `test_main_rejects_an_invalid_order_flag() -> None` — Exit through the parser for an unknown category name.
- `test_main_without_paths_returns_one(monkeypatch: pytest.MonkeyPatch) -> None` — Print usage and return nonzero when no paths are given.

### `packages/package/__init__.py`

Tests for the unified package pipeline.


### `packages/package/test_inventory_cli.py`

ANSI-styled ``--help`` formatting shared by the root scripts.

- `cast_tty() -> TextIO` — Return the TTY stub as a ``TextIO`` object.
- `test_styled_is_false_without_tty(monkeypatch: pytest.MonkeyPatch) -> None` — Non-terminal stdout keeps styling disabled.
- `test_styled_is_true_on_tty(monkeypatch: pytest.MonkeyPatch) -> None` — A terminal stdout without ``NO_COLOR`` enables styling.
- `test_styled_honours_no_color(monkeypatch: pytest.MonkeyPatch) -> None` — ``NO_COLOR`` disables styling even on a terminal.
- `test_paint_wraps_text_on_tty(monkeypatch: pytest.MonkeyPatch) -> None` — On a terminal ``paint`` wraps text in the SGR code and reset.
- `test_paint_passes_empty_text(monkeypatch: pytest.MonkeyPatch) -> None` — Empty text is returned unchanged even on a terminal.
- `test_paint_passes_text_without_tty() -> None` — Without a terminal ``paint`` returns the text untouched.
- `test_format_help_styles_usage_and_prog(monkeypatch: pytest.MonkeyPatch) -> None` — Styled help bolds ``usage:`` and paints the program name.
- `test_format_help_plain_without_tty() -> None` — Without a terminal the help text carries no escapes.
- `test_format_help_styles_headings(monkeypatch: pytest.MonkeyPatch) -> None` — Styled help paints section headings bold yellow.
- `test_invocation_paints_option_flags(monkeypatch: pytest.MonkeyPatch) -> None` — Option flags render cyan with dimmed metavariables on TTYs.
- `test_invocation_paints_positionals(monkeypatch: pytest.MonkeyPatch) -> None` — Positional arguments render green on a terminal.
- `test_invocations_plain_without_tty() -> None` — Plain help lists flags and positionals without escapes.
- `test_pretty_parser_renders_dimmed_epilog(monkeypatch: pytest.MonkeyPatch) -> None` — The epilog text is dimmed when styling is enabled.
- `test_formatter_is_pretty() -> None` — ``pretty_parser`` uses the ANSI help formatter class.

### `packages/package/test_package_api.py`

Tests for the unified package Python API.

- `expect_equal(*, actual: T, expected: T) -> None` — Require equal values.
- `expect_true(*, condition: bool) -> None` — Require a true condition.
- `test_run_orders_selected_stages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Selected stages execute in canonical order.
- `test_run_defaults_to_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — No configured stages preserves package-only compatibility.
- `test_build_expands_target_aliases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Target names, groups and ``all`` expand to concrete targets.
- `test_build_falls_back_to_auto_host_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An empty target list with ``auto`` resolves to the host target.
- `test_build_raises_on_unknown_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An unknown target name raises a clear ValueError.
- `test_build_raises_when_auto_target_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Auto target detection failure raises a clear ValueError.
- `test_load_config_reads_all_stages(tmp_path: Path) -> None` — The unified TOML parser reads stage-specific settings.
- `test_build_collects_every_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Check, dist and tree outputs all appear in the stage result.
- `test_bundle_rejects_multi_target_output(tmp_path: Path) -> None` — An explicit output cannot pair with several bundle targets.
- `test_bundle_builds_requested_targets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Every requested target receives a builder with filtered options.
- `test_package_archives_project_and_documents(tmp_path: Path) -> None` — Default packaging zips the tree and regenerates README files.
- `test_package_honours_explicit_output(tmp_path: Path) -> None` — An explicit archive path skips the generated documentation.

### `packages/package/test_package_build.py`

Tests for Exactus executable staging.

- `test_stage_package_keeps_complete_package_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Every Exactus package is available to the built executable.
- `test_bundle_directory_descriptions(name: str, description: str) -> None` — Describe each asset directory and unknown hash-prefix leaves.
- `test_bundle_readmes_recurse_without_touching_private_or_linked_trees(tmp_path: Path) -> None` — Generate public inventories without following symlinks or caches.
- `test_bundle_readmes_preserve_existing_prose_and_detect_catalogs(tmp_path: Path) -> None` — Keep authored prose while generating inventories and catalog labels.
- `verify_bundle_runtime(*, catalog_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Check command resolution and recovery of a damaged local component.
- `verify_launcher_error_paths(*, runtime: Runtime) -> None` — Inject malformed metadata to reach every validation failure path.
- `verify_bundle_dispatch(*, catalog_path: Path, update: Path, cache: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None` — Run launcher metadata and maintenance commands on a real catalog.
- `verify_corrupt_state_recovery(*, cache: Path, builder: BundleBuilder) -> None` — Rebuild cleanly after corrupt, dangling, and stale state records.
- `verify_incremental_removal(*, output: Path, catalog_path: Path, staged: list[str]) -> BundleBuilder` — Verify removal emits a delta update; return the smaller builder.
- `test_bundle_build_reuses_payloads_and_emits_incremental_updates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None` — Verify real offline publication, reuse, forced rebuild and removal.
- `test_bundle_size_labels(size: int, label: str) -> None` — Format exact and fractional SI sizes without trailing zeroes.
- `test_bundle_component_and_target_selection() -> None` — Expand groups and dependencies, preserving required components.
- `test_bundle_file_config_rejects_invalid_types(tmp_path: Path, text: str) -> None` — Validate lists and scalars without accepting malformed configuration.
- `test_bundle_file_config_resolves_relative_paths(tmp_path: Path) -> None` — Read all configured defaults relative to the project file.
- `test_bundle_fetch_enforces_limits_and_retries(monkeypatch: pytest.MonkeyPatch) -> None` — Retry transient failures and enforce HTTP response limits.
- `test_bundle_filesystem_helpers(tmp_path: Path) -> None` — Exercise pruning, zip extraction, removal, and version scanning.
- `test_bundle_installers_stage_runtimes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Stage Node, Python, npm, and zstd payloads with local doubles.
- `test_bundle_browser_installers_and_dedupe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Install Playwright archives, dedupe Node binaries, and prune locales.
- `test_bundle_payload_dedupe_prune_and_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Deduplicate embedded runtimes, prune browsers, and stage metadata.
- `test_bundle_document_and_cli_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Render status documents and resolve CLI targets without building.
- `dig_text(*, document: dict[str, Json], path: tuple[str, ...]) -> object` — Walk a decoded document to a scalar value.
- `test_bundle_main_builds_selected_targets(monkeypatch: pytest.MonkeyPatch) -> None` — Dispatch configured targets through the real CLI entry point.
- `test_bundle_cache_boundaries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Cache roots fall back deterministically and locks reject abuse.
- `verify_cache_usability(*, launcher: ModuleType, tmp_path: Path) -> None` — Reject symlink, file, and non-file-lock cache candidates.
- `verify_cache_lock_failures(*, launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, identity: str) -> None` — Exhaust candidates, reject symlinked locks, and bound flock waits.
- `test_build_file_config_parses_tables_and_flags(tmp_path: Path) -> None` — ``[tool.build]`` TOML defaults parse into build file config.
- `test_build_file_config_rejects_bad_types(document: str, tmp_path: Path) -> None` — Every malformed ``[tool.build]`` key raises ``TypeError``.
- `test_bundle_target_leaf_filtering(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``_ignore`` keeps selected bundle leaves and prunes the rest.
- `verify_catalog_pack_rejections(*, package_build: ModuleType, staging: Path) -> None` — Exercise every catalog pack validation rejection branch.
- `test_build_stages_native_payloads_and_validates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Native zstd staging and catalog validation run on a real tree.
- `verify_staged_catalog_roundtrip(*, package_build: ModuleType, root: Path) -> None` — Validate a correct pack record against its staged pack file.
- `make_fake_package(*, root: Path) -> Path` — Create a minimal staged Exactus package with bundle catalogs.
- `test_build_artifacts_stage_full_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``build_check``, ``build_dist`` and ``build_tree`` run end to end.
- `test_build_rmtree_retry_restores_permissions(tmp_path: Path) -> None` — ``_rmtree_retry`` repairs permissions then retries removal.
- `noop_stage(**kwargs: object) -> None` — Accept any keyword arguments without doing anything.
- `test_build_main_dispatches_selected_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The build CLI resolves flags, config and target selections.
- `test_build_parser_and_exec_target_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``create_parser`` and ``--exec-target`` scope the pyz targets.
- `test_tool_version_resolves_each_dispatch_kind() -> None` — Python, node, binary, and probe tools map to package versions.
- `test_tool_version_prefix_matches_dist_names() -> None` — Module names prefix-match longer dist names when needed.
- `test_catalog_tools_reads_component_metadata(tmp_path: Path) -> None` — A catalog's declared tools resolve against its version map.
- `test_write_manifest_lists_targets_and_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``MANIFEST.md`` records the artifact and its bundled tools.
- `test_closure_rejects_missing_component() -> None` — Dependency resolution rejects components outside the catalog.
- `test_closure_rejects_cyclic_dependencies() -> None` — A dependency cycle raises ``FormatError`` instead of looping.
- `test_closure_orders_dependencies_first() -> None` — Resolved closures list requirements before dependents.
- `test_usable_cache_root_rejects_symlink(tmp_path: Path) -> None` — Symlinked cache roots are never trusted.
- `test_usable_cache_root_rejects_lock_dir(tmp_path: Path) -> None` — A ``.lock`` directory blocks cache publication.
- `test_usable_cache_root_accepts_writable_dir(tmp_path: Path) -> None` — A plain writable directory hosts the lock file.

### `packages/package/test_package_cli.py`

Tests for the unified package CLI.

- `expect_equal(*, actual: T, expected: T) -> None` — Require equal values.
- `class Capture` — Capture typed arguments passed from the CLI to the API.
  - `build_stage` = `None`
  - `bundle_stage` = `None`
  - `package_stage` = `None`
  - `bundle_config` = `None`
- `test_cli_stage_flags_are_exact_and_order_independent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — CLI stage flags select the exact requested set.
- `test_cli_field_override_preserves_other_pyproject_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A CLI field overrides only its matching configured field.
- `test_inventory_help_respects_terminal_and_no_color(monkeypatch: pytest.MonkeyPatch, mode: str) -> None` — Render flags, positionals and metavariables without coloring pipes.

### `packages/package/test_package_config.py`

Tests for the package pipeline configuration loader.

- `test_empty_project_returns_defaults(tmp_path: Path) -> None` — Missing pyproject.toml yields a fully default configuration.
- `test_bundle_output_path_is_resolved(tmp_path: Path) -> None` — The optional bundle output is resolved against the project root.
- `test_load_config_rejects_non_string_list_items(tmp_path: Path) -> None` — A string list containing a non-string item raises TypeError.
- `test_load_config_rejects_non_boolean(tmp_path: Path) -> None` — A boolean field with a non-boolean value raises TypeError.
- `test_load_config_rejects_non_string_path(tmp_path: Path) -> None` — A path field with a non-string value raises TypeError.
- `test_load_config_rejects_non_table_tool(tmp_path: Path) -> None` — A non-table ``tool`` entry falls back to defaults.
- `test_load_config_rejects_non_table_package(tmp_path: Path) -> None` — A non-table ``[tool.package]`` entry raises a clear TypeError.
- `test_load_config_rejects_non_table_stage(tmp_path: Path) -> None` — A non-table stage setting raises a clear TypeError.
- `test_load_config_rejects_non_integer_part_bytes(tmp_path: Path) -> None` — A non-integer ``part-bytes`` value raises a clear TypeError.
- `test_load_config_rejects_non_string_node_version(tmp_path: Path) -> None` — A non-string ``node-version`` value raises a clear TypeError.
- `test_load_config_rejects_non_list_targets(tmp_path: Path) -> None` — A non-list ``targets`` value raises a clear TypeError.
- `test_load_config_rejects_non_string_list_members(tmp_path: Path) -> None` — Non-string list members raise a clear TypeError.
- `test_load_config_rejects_non_bool_enabled(tmp_path: Path) -> None` — A non-boolean ``enabled`` flag raises a clear TypeError.
- `test_load_config_rejects_non_string_output(tmp_path: Path) -> None` — A non-string ``output`` path raises a clear TypeError.
- `test_load_config_non_dict_tool_returns_defaults(tmp_path: Path) -> None` — A scalar ``tool`` table falls back to pipeline defaults.
- `test_load_config_rejects_non_dict_package(tmp_path: Path) -> None` — A scalar ``[tool.package]`` raises a clear TypeError.
- `test_load_config_rejects_non_dict_stage(tmp_path: Path) -> None` — A scalar ``[tool.package.build]`` raises a clear TypeError.
- `test_load_config_rejects_non_int_part_bytes(tmp_path: Path) -> None` — A non-integer ``part-bytes`` raises a clear TypeError.
- `test_load_config_rejects_bool_part_bytes(tmp_path: Path) -> None` — A boolean ``part-bytes`` raises the integer TypeError.

### `packages/package/test_package_install.py`

Tests for system-wide installation of the built executable.

- `isolated_completion(monkeypatch: pytest.MonkeyPatch) -> None` — Keep completion probes away from the real user home.
- `test_host_platform_maps_known_systems(monkeypatch: pytest.MonkeyPatch) -> None` — Known ``sys.platform``/machine pairs map to release identifiers.
- `test_host_platform_rejects_unknown_system(monkeypatch: pytest.MonkeyPatch) -> None` — An unrecognized ``sys.platform`` raises ``ValueError``.
- `test_host_platform_rejects_unknown_arch(monkeypatch: pytest.MonkeyPatch) -> None` — An unrecognized machine identifier raises ``ValueError``.
- `test_host_target_selects_linux_libc(monkeypatch: pytest.MonkeyPatch) -> None` — Linux targets pick the musl or glibc bundle variant.
- `test_host_target_selects_simple_names() -> None` — Non-Linux systems map straight onto ``<system>-<arch>``.
- `test_host_target_rejects_unsupported() -> None` — A system without a bundle target raises ``ValueError``.
- `test_release_name_matches_bin_layout() -> None` — Release directories follow the ``exactus_<os>_<arch>`` scheme.
- `test_running_archive_detects_zipapp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A file zipapp entry point resolves to its archive path.
- `test_running_archive_ignores_source_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Directories and non-zip files are not treated as archives.
- `test_build_release_never_writes_archive(tmp_path: Path) -> None` — Release directories ship ``MANIFEST.md`` instead of tarballs.
- `test_build_release_produces_full_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A staged build leaves executable, archive, and README together.
- `test_install_posix_copies_into_system_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A writable system directory receives the executable.
- `test_install_posix_skips_same_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Reinstalling the running archive is a no-op copy.
- `test_install_posix_escalates_through_sudo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An unwritable destination goes through ``sudo install``.
- `test_install_posix_creates_missing_dir_via_sudo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A missing destination directory is created with ``sudo mkdir``.
- `test_remove_posix_reports_absent_and_removes(tmp_path: Path) -> None` — Removal reports a missing install and deletes a present one.
- `test_remove_posix_escalates_through_sudo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An unwritable removal escalates to ``sudo rm``.
- `test_windows_directory_prefers_program_files(monkeypatch: pytest.MonkeyPatch) -> None` — The Windows root honors ``ProgramFiles`` and its fallback.
- `test_windows_path_update_adds_and_removes(monkeypatch: pytest.MonkeyPatch) -> None` — The registry ``Path`` gains and loses the install directory.
- `test_windows_path_update_skips_existing_entry(monkeypatch: pytest.MonkeyPatch) -> None` — A directory already on ``Path`` produces no registry write.
- `test_windows_path_update_requires_write_access(monkeypatch: pytest.MonkeyPatch) -> None` — A refused registry open surfaces as ``PermissionError``.
- `test_windows_path_entries_open_failure(monkeypatch: pytest.MonkeyPatch) -> None` — An ``OSError`` during registry access returns ``None``.
- `test_install_windows_writes_pyz_and_shim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Windows install stages the pyz, the ``.cmd`` shim, and PATH.
- `test_uninstall_windows_removes_directory_and_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Windows uninstall drops the directory and its PATH entry.
- `test_install_system_uses_existing_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An up-to-date platform binary installs without rebuilding.
- `test_install_system_rebuilds_stale_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A platform binary older than the sources gets rebuilt.
- `test_install_system_rebuild_flag_forces_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--rebuild`` builds a fresh binary even when one exists.
- `test_install_system_reinstalls_running_archive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — An installed zipapp reinstalls itself without building.
- `test_install_system_rejects_bundled_rebuild(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--rebuild`` from an installed archive raises ``ValueError``.
- `test_install_system_dispatches_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Windows hosts route installation to the Program Files path.
- `test_uninstall_system_reports_missing_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Uninstalling with nothing installed returns ``None``.
- `test_uninstall_system_removes_posix_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A present POSIX install is removed and reported.
- `test_uninstall_system_dispatches_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Windows hosts route uninstall to the Program Files path.
- `test_create_parser_accepts_rebuild() -> None` — The parser exposes the ``--rebuild`` modifier.
- `test_run_reports_install_and_uninstall(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The command prints installed and removed locations.
- `test_run_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None` — Failures surface as an error line and a nonzero status.
- `test_install_completion_registers_each_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Every shell location receives the managed registration.
- `test_install_completion_reports_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Broken and failing registrations warn without aborting.
- `test_uninstall_completion_removes_registrations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Diagnosed registrations are removed and reported.
- `test_install_system_registers_completion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — System installation also installs the user completions.
- `test_uninstall_system_removes_completion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — System uninstall removes completions even with no binary.
- `test_ansi_enabled_requires_capable_terminal(monkeypatch: pytest.MonkeyPatch) -> None` — ANSI styling requires a terminal that is not ``TERM=dumb``.
- `test_install_system_paints_banner_and_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--install`` emits the banner and repaints the step checklist.
- `test_install_system_marks_failed_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A failed stage leaves its row FAIL-marked and the cursor freed.
- `test_install_system_drives_ui_sequence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``install_system`` walks the checklist steps in order.
- `test_install_completion_advances_ui(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Per-shell registration updates the checklist and returns a count.

### `packages/package/test_package_shims.py`

Tests for generated bundled-distribution import shims.

- `test_public_names_drops_startup_hook_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``pth_file``-style startup hooks are never shimmed or probed.
- `test_quiet_probe_drops_coverage_process_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Probing ``coverage.pth_file`` cannot start a nested collector.

### `packages/package/test_partition_fs.py`

Tests for the content-addressed partition filesystem.

- `component_tree(root: Path, *, payload: bytes=b'payload' * 100) -> Path` — Create one component exercising files, links, and directories.
- `scan_recipe(objects: ObjectStore, root: Path, name: str, metadata: dict[str, Json] | None=None, progress: object=None) -> Recipe` — Scan a component tree into a validated recipe.
- `recook(recipe: Recipe, *, entries: list[Entry] | None=None, metadata: dict[str, Json] | None=None, name: str | None=None, logical_bytes: int | None=None) -> Recipe` — Return a mutated recipe whose identity hashes stay consistent.
- `file_entry(recipe: Recipe) -> Entry` — Return the first regular-file entry of a recipe.
- `publish(cache: Path, recipes: dict[str, Recipe], output: Path, *, pack_target: int=64 * Constants.block) -> Catalog` — Build a real catalog and pack layout under ``output``.
- `document(path: Path) -> dict[str, Json]` — Read a JSON document as a mutable mapping.
- `fix_root(doc: dict[str, Json]) -> None` — Recompute ``root_sha256`` after mutating a catalog document.
- `load_doc(doc: dict[str, Json], tmp_path: Path) -> None` — Write a mutated catalog document and load it for validation.
- `fix_update_bytes(update: Path) -> None` — Repair ``update_bytes`` after mutating an update manifest.
- `zip_update(update: Path, artifact: Path) -> None` — Pack an update directory into a streamed ZIP artifact.
- `write_stream(path: Path, payload: bytes) -> None` — Write one raw Zstandard frame for codec fixtures.
- `test_partition_scan_pack_and_materialize(tmp_path: Path) -> None` — Scan, publish, verify, materialize, and deep-verify a real tree.
- `test_partition_scanner_rejections(tmp_path: Path) -> None` — Reject unsafe names, unsupported entries, and large-file scans.
- `test_partition_recipe_rejections(tmp_path: Path) -> None` — Exercise every recipe structural and entry rejection.
- `verify_recipe_entry_rejections(*, recipe: Recipe) -> None` — Reject duplicate, unsorted, orphaned, and mistyped entries.
- `verify_recipe_link_rejections(*, recipe: Recipe) -> None` — Reject broken hardlinks, bad symlinks, and unknown entry kinds.
- `verify_recipe_document_rejections(*, recipe: Recipe) -> None` — Round-trip and reject malformed serialized recipes.
- `test_partition_catalog_rejections(tmp_path: Path) -> None` — Exercise catalog schema, membership, and identity rejections.
- `verify_catalog_membership_rejections(*, catalog_path: Path, tmp_path: Path) -> None` — Reject name, chunker, and object-table inconsistencies.
- `verify_catalog_pack_rejections(*, catalog_path: Path, tmp_path: Path) -> None` — Reject pack path, object list, and identity inconsistencies.
- `verify_catalog_metadata_rejections(*, catalog_path: Path, tmp_path: Path, recipes: dict[str, Recipe]) -> None` — Reject dependency, environment, and tool metadata violations.
- `verify_catalog_tool_and_link_rejections(*, mutated: 'Callable[..., dict[str, Json]]', tmp_path: Path, recipes: dict[str, Recipe]) -> None` — Reject tool-schema and dependency-link violations in catalogs.
- `test_partition_coercion_and_path_rejections(tmp_path: Path) -> None` — Exercise scalar, JSON, and path safety rejections.
- `test_partition_pack_codec(tmp_path: Path) -> None` — Verify pack framing and reject corrupt pack contents.
- `verify_pack_decode_rejections(*, tmp_path: Path, digest: str) -> None` — Reject malformed magic, headers, objects, and membership.
- `test_partition_store_verify_and_recover(tmp_path: Path) -> None` — Recover objects from packs and reject corrupted pack bytes.
- `test_partition_materialize_rejections(tmp_path: Path) -> None` — Reject every reconstructed-tree integrity mismatch.
- `verify_tree_rejection_battery(*, recipe: Recipe, fresh: 'Callable[[], Path]') -> None` — Corrupt materialized trees in every distinguishable way.
- `verify_tree_content_rejection_battery(*, recipe: Recipe, fresh: 'Callable[[], Path]') -> None` — Corrupt file contents and modes in every distinguishable way.
- `verify_tree_link_rejection_battery(*, recipe: Recipe, fresh: 'Callable[[], Path]') -> None` — Corrupt link entries in every distinguishable way.
- `test_partition_update_and_rollback(tmp_path: Path) -> None` — Publish deltas, apply directory and ZIP updates, and roll back.
- `verify_update_rejections(*, tmp_path: Path, dist: Path, update: Path) -> None` — Reject malformed directory and streamed ZIP updates.
- `test_partition_zip_update_rejections(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Reject traversal, duplicates, links, and oversized ZIP members.
- `test_partition_garbage_collect(tmp_path: Path) -> None` — Remove unreachable packs while preserving dry-run behavior.

### `packages/patcher/__init__.py`

Package marker.


### `packages/patcher/test_diff.py`

Test read-only unified diff rendering and patcher diff CLI modes.

- `test_highlighted_text_diff(tmp_path: Path, suffix: str, old: str, new: str, token: str) -> None` — Verify supported textual formats receive highlighted unified diffs.
- `test_builder_diff_is_read_only(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None` — Verify builder diff mode reports changes without creating an output.
- `test_generated_update_diff_is_read_only(tmp_path: Path) -> None` — Verify generated update diff mode does not mutate its target project.
- `test_binary_diff_summary(tmp_path: Path) -> None` — Verify changed binary files are summarized without text decoding.

### `packages/patcher/test_example_run.py`

Cover the bundled ``patcher`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'patcher'...`
- `test_example_module_runs_as_a_script() -> None` — Execute the example file's ``__main__`` entry for real.

### `packages/patcher/test_patcher.py`

Test the deterministic executable project patcher.

- `test_resolve_relative_root_from_invocation_directory(tmp_path: Path) -> None` — Verify relative roots are resolved from the invocation directory.
- `test_folder_delta_and_relative_runtime_root(tmp_path: Path) -> None` — Verify a folder delta honors the runtime relative-root override.
- `test_zip_as_b_source(tmp_path: Path) -> None` — Verify an ordinary ZIP archive can provide the after-state source.
- `test_inverse_restores_before_state(tmp_path: Path) -> None` — Verify an inverse patch completely restores the original state.
- `test_deterministic_build(tmp_path: Path) -> None` — Verify identical patch inputs produce byte-identical PYZ artifacts.
- `test_relative_root_variants(tmp_path: Path, argument: str) -> None` — Verify equivalent relative-root forms resolve to the same directory.
- `test_source_filter_symlink_empty_directory_and_unsupported(tmp_path: Path) -> None` — Verify source filtering and filesystem-entry classification.
- `test_ordinary_zip_directory_file_and_symlink(tmp_path: Path) -> None` — Verify ZIP snapshots preserve supported filesystem entry kinds.
- `test_pyz_is_semantic_after_snapshot_and_nonreversible_build(tmp_path: Path) -> None` — Verify a generated PYZ exposes its semantic after-state snapshot.
- `test_move_detection_disable_and_composition(tmp_path: Path) -> None` — Verify move detection controls and compatible delta composition.
- `test_direct_constructor_removal_relative_and_outside_rejection(tmp_path: Path) -> None` — Verify direct removals and project-root path containment.
- `test_safe_relative_rejects_unsafe_values() -> None` — Verify unsafe project-relative path representations are rejected.
- `test_manifest_validation_errors_and_corrupt_blob(tmp_path: Path) -> None` — Verify malformed manifests and corrupt embedded blobs are rejected.
- `test_generated_pyz_inspection_commands(tmp_path: Path) -> None` — Verify generated PYZ inspection and validation commands execute.
- `test_builder_help_is_exhaustive() -> None` — Verify module help documents the complete supported CLI surface.
- `test_bin_default_and_generated_cli(tmp_path: Path) -> None` — Verify default binary generation and generated CLI help.
- `test_generated_patch_backs_up_overlapping_removals(tmp_path: Path) -> None` — Apply removals containing both ancestor and descendant directories.
- `test_generated_binary_builds_delta(tmp_path: Path) -> None` — Verify a generated patcher binary can build and apply a real delta.
- `test_bin_dir_is_relative_to_project_root(tmp_path: Path) -> None` — Verify relative binary directories resolve below the project root.
- `test_cli_api_run_builds_binary(tmp_path: Path) -> None` — Verify the callable CLI API supports binary-generation arguments.
- `test_cli_api_run_builds_delta(tmp_path: Path) -> None` — Verify the callable CLI API exposes complete delta construction.
- `test_parser_defaults_and_switches() -> None` — Verify parser defaults and inverse command-line switches.
- `test_bin_accepts_inline_directory(tmp_path: Path) -> None` — Verify ``--bin`` accepts its destination directory inline.
- `test_module_without_arguments_prints_help() -> None` — Verify module invocation without arguments prints exhaustive help.
- `test_generated_binary_without_arguments_prints_help(tmp_path: Path) -> None` — Verify a generated binary without arguments prints exhaustive help.
- `test_inline_bin_and_bin_dir_conflict(tmp_path: Path) -> None` — Verify conflicting binary-directory declarations are rejected.
- `test_main_module_switches_to_project_python(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the patcher module switches interpreter before its CLI runs.
- `test_examples_module_switches_to_project_python(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the patcher example uses the same automatic interpreter switch.

### `packages/patcher/test_runtime.py`

Test the standalone transactional patch runtime directly.

- `test_safe_accepts_nested_path_and_rejects_unsafe_paths(tmp_path: Path) -> None` — Verify runtime path resolution remains inside the project root.
- `test_digest_state_and_expected_cover_file_directory_and_absence(tmp_path: Path) -> None` — Verify runtime state normalization for common filesystem entries.
- `test_state_and_restore_cover_symbolic_links(tmp_path: Path) -> None` — Verify symbolic-link state and transactional restoration.
- `test_restore_copies_directory_tree(tmp_path: Path) -> None` — Verify directory backups can be restored recursively.
- `test_diff_blob_handles_absent_nonfile_and_file_payloads(tmp_path: Path) -> None` — Verify runtime diff payload loading follows manifest entry kinds.
- `test_paint_and_syntax_respect_color_controls() -> None` — Verify runtime ANSI decoration and lightweight syntax highlighting.
- `test_render_diff_covers_text_move_metadata_and_binary(tmp_path: Path) -> None` — Verify runtime rendering covers major embedded diff categories.
- `test_runtime_manifest_accessors_reject_invalid_data(tmp_path: Path) -> None` — Verify malformed runtime manifest data fails through public behavior.
- `test_main_lists_and_describes_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None` — Verify ``--info``, ``--json``, and ``--list`` inspection modes.
- `test_main_diff_modes_render_and_validate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None` — Verify ``--diff`` renders content and rejects bad context values.
- `test_main_verify_and_conflict_policies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None` — Verify ``--verify``, ``--dry-run``, and conflict policy behavior.
- `test_main_apply_commits_full_delta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None` — Verify transactional application of every operation category.
- `test_main_rolls_back_failed_postcondition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify postcondition failure restores every touched destination.
- `test_main_rejects_corrupt_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify staged payload digests are enforced during application.
- `test_main_root_resolution_variants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify destination root resolution honors overrides and types.
- `test_main_rejects_malformed_manifest_members(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify invalid manifest member types raise typed errors.
- `test_module_guard_invokes_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify the ``__main__`` guard runs the runtime entry point.
- `test_safe_rejects_symlink_parent_escape(tmp_path: Path) -> None` — Verify resolution through an escaping symlink parent is refused.

### `packages/performance/__init__.py`

Tests for :mod:`exactus.packages.performance`.


### `packages/performance/test_performance.py`

Tests for parsing, analysis, dashboard export, serving, and CLI behavior.

- `expect_equal(*, actual: T, expected: T) -> None` — Assert equality without a bare assert statement.
- `trace_text() -> str` — Return a deterministic trace covering stages, gaps, and repetition.
- `write_trace(*, root: Path, tool: str='LINTS') -> Path` — Write one Exactus-shaped trace fixture.
- `test_parser_discovers_and_parses(tmp_path: Path) -> None` — Discover nested traces and parse depth and elapsed time.
- `test_parser_ignores_malformed_lines(tmp_path: Path) -> None` — Ignore malformed input while retaining valid events.
- `test_analyzer_builds_stages_and_bottlenecks(tmp_path: Path) -> None` — Infer stages, stalls, repetition, rate, and duration.
- `test_empty_analysis_is_safe(tmp_path: Path) -> None` — Analyze an empty trace without division or indexing failures.
- `test_export_writes_assets_and_raw_lines(tmp_path: Path) -> None` — Export profiler assets and the requested tool-to-lines JSON mapping.
- `test_exporter_accepts_preanalyzed_runs(tmp_path: Path) -> None` — Export an explicitly supplied immutable run collection.
- `test_server_serves_exported_index(tmp_path: Path) -> None` — Serve the exported dashboard over an ephemeral loopback port.
- `test_cli_summary_export_and_missing(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None` — Exercise CLI summary, export, and missing-trace exit paths.
- `test_cli_serve_shutdown_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise interactive CLI serving and clean interrupt shutdown.
- `test_example_runs(capfd: pytest.CaptureFixture[str]) -> None` — Run the comprehensive example successfully.
- `test_dashboard_launcher_uses_package_lifecycles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Delegate serving, browser launch, and cleanup to package modules.
- `test_reused_dashboard_server_is_not_terminated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Leave an adopted package server running on close.
- `test_config_reads_pyproject_and_cli_precedence(tmp_path: Path) -> None` — Resolve defaults, pyproject settings, and explicit overrides.
- `test_config_defaults_without_pyproject(tmp_path: Path) -> None` — Use canonical defaults when the project has no configuration.
- `test_config_rejects_invalid_table_values(tmp_path: Path) -> None` — Reject non-conforming ``tool.performance`` values.
- `test_config_rejects_out_of_range_values(tmp_path: Path) -> None` — Reject resolved settings outside their valid ranges.
- `test_config_handles_non_table_tool_sections(tmp_path: Path) -> None` — Treat non-table ``tool`` or ``performance`` values as empty.
- `test_config_root_and_paths_expansion(tmp_path: Path) -> None` — Resolve roots from files and expand absolute and glob sources.
- `test_launcher_fails_when_server_never_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate an owned server that never reports readiness.
- `test_launcher_keeps_reused_server_when_not_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Leave an adopted server running when readiness fails.
- `test_launcher_cleans_up_when_browser_launch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate the owned server when Chrome launch raises.
- `test_parser_reads_trailers_and_embedded_durations() -> None` — Trailers, span pairs and ``in Xs`` phrases become typed fields.
- `test_analyzer_attributes_time_per_actor_template_and_thread(tmp_path: Path) -> None` — Inferred time is attributed per lane and aggregated usefully.
- `test_samples_are_parsed_and_summarized(tmp_path: Path) -> None` — ``~sample`` lines become resources and never count as events.
- `test_report_is_machine_readable_and_written_without_a_server(tmp_path: Path) -> None` — The JSON report carries the schema and is exported with the site.

### `packages/pmanager/__init__.py`

Tests for the counter orchestrator.


### `packages/pmanager/test_api.py`

Public API contract tests.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'pmanager'`
- `test_public_api_plan_and_context() -> None` — Exercise planning and the context-bound facade.
- `test_public_api_missing_status() -> None` — Expose a stable domain exception instead of transport details.
- `test_public_state_contract_includes_paused() -> None` — Keep PAUSED in the stable public lifecycle model.

### `packages/pmanager/test_api_extended.py`

Extended public API tests.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'pmanager'`
  - `spec` = `root / 'processes.json'`
- `descriptor(name: str='A', context: str='ctx') -> Descriptor` — Build a descriptor.
- `snapshot(state: str='running', progress: int=10) -> dict[str, JsonValue]` — Build an IPC snapshot.
- `test_mapping_validate_get_and_properties(monkeypatch: pytest.MonkeyPatch) -> None` — Cover mapping construction, handles, and status properties.
- `test_list_filters_and_status_conversion(monkeypatch: pytest.MonkeyPatch) -> None` — Cover discovery filtering and defensive snapshot conversion.
- `test_controls_context_and_recursive(monkeypatch: pytest.MonkeyPatch) -> None` — Cover lifecycle controls and the context facade.
- `test_create_plan_and_launcher_error(monkeypatch: pytest.MonkeyPatch) -> None` — Cover create, context create, plans, and translated errors.
- `test_wait_watch_subscribe_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None` — Cover terminal waiting and event consumption.
- `test_missing_and_transport_errors(monkeypatch: pytest.MonkeyPatch) -> None` — Cover missing-process and transport exception translation.
- `test_context_manager_ownership_and_detach(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise API ownership cleanup and explicit detach.
- `test_generation_is_exposed_in_public_status() -> None` — Preserve execution generation in public snapshots.
- `test_handle_forwarders_and_context_status(monkeypatch: pytest.MonkeyPatch) -> None` — Cover the remaining convenience facade forwarding methods.
- `test_closed_scope_and_close_cleanup() -> None` — Cover closed-scope protection and idempotent cleanup branches.

### `packages/pmanager/test_broadcast.py`

Live worker broadcast integration tests.

- `class Constants` — Group module-level constants.
  - `min_delivered` = `2`
  - `root` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'pmanager'`
- `test_context_broadcast_reaches_other_worker_and_api() -> None` — A broadcast is copied to every live worker in the same context.

### `packages/pmanager/test_class_runner.py`

Unit tests for the detached class-runner entry module.

- `class Constants` — Group module-level constants.
  - `auth_tag` = `'secret'`
  - `poll_interval` = `0.05`
  - `poll_timeout` = `5.0`
- `class RunnerStub` — Recording worker used by the class-runner tests.
  - `__init__(self) -> None` — Init.
  - `probe(self) -> dict[str, str]` — Report a fixed custom status payload.
  - `on_demo(self, payload: ModelValue) -> None` — Record a demo broadcast event.
  - `run(self, *args: ModelValue, **kwargs: ModelValue) -> int` — Record the invocation arguments and report success.
- `class SignalRecorder` — Capture signal handler registrations without installing them.
  - `__init__(self) -> None` — Init.
  - `emit(self, *, signalnum: int) -> None` — Invoke the recorded handler for a signal.
- `class ThreadStub` — Record thread construction without starting any work.
  - `__init__(self, *, target: Callable[..., ModelValue], args: tuple[ModelValue, ...]=(), daemon: bool=False) -> None` — Init.
  - `start(self) -> None` — Mark the thread as started without launching it.
- `test_resolve_returns_process_class() -> None` — A ProcessClass qualname resolves to the class object.
- `test_resolve_rejects_non_process_class() -> None` — A non-ProcessClass attribute raises ``TypeError``.
- `test_call_arguments_plain_values() -> None` — Without the call marker, argv passes through positionally.
- `test_call_arguments_parses_orchestrator_call() -> None` — The ``--orchestrator-call`` JSON supplies args and kwargs.
- `test_call_arguments_ignores_non_mapping() -> None` — A non-object call payload falls back to positional argv.
- `test_call_arguments_rejects_bad_members() -> None` — Non-list args or non-mapping kwargs fall back to argv.
- `test_control_value() -> None` — ``--orchestrator-<name>=`` values resolve or return ``None``.
- `test_run_status_hook_returns_result() -> None` — A successful hook returns its model value.
- `test_run_status_hook_translates_errors() -> None` — A failing hook yields an error mapping instead of raising.
- `test_status_server_answers_requests() -> None` — The status server authenticates and serves hook payloads.
- `test_status_server_reports_non_serializable() -> None` — A non-JSON hook result yields the serialization error payload.
- `test_broadcast_sender_delivers() -> None` — The sender posts the broadcast and returns its delivery count.
- `test_broadcast_sender_fails_closed() -> None` — An unreachable orchestrator reports zero deliveries.
- `test_event_receiver_dispatches() -> None` — The receiver polls the events endpoint and dispatches topics.
- `test_main_requires_module_and_class(monkeypatch: pytest.MonkeyPatch) -> None` — Missing ``module class`` arguments exit with usage status.
- `test_main_runs_class_with_orchestrator_arguments(monkeypatch: pytest.MonkeyPatch) -> None` — The runner wires broadcast/status threads, signals, and argv.
- `test_signal_handlers_invoke_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None` — Signal handlers drive pause/kill/cancel/reset/resume hooks.

### `packages/pmanager/test_core.py`

Behavior tests for the orchestration engine.

- `test_spec_errors_and_helpers(tmp_path: Path) -> None` — Handle test spec errors and helpers.
- `test_discovery_and_find(monkeypatch: pytest.MonkeyPatch) -> None` — Discover logical workers through the platform backend.
- `test_client_request() -> None` — Exercise the local IPC request protocol.
- `test_worker_state_counter_and_wait(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test worker state counter and wait.
- `test_worker_ensure_command_fanout_execute(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test worker ensure command fanout execute.
- `test_cli_helpers_and_main(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test cli helpers and main.
- `test_cli_loads_a_json_spec_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Load an explicit JSON specification for informational commands.
- `test_launcher_real_worker() -> None` — Exercise detached launch, discovery, IPC, and serving together.
- `test_worker_concurrency_and_fanout(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test worker concurrency and fanout.
- `test_worker_command_and_failure(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test worker command and failure.
- `test_cli_observe_create_and_errors(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test cli observe create and errors.
- `test_worker_serve_protocol(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test worker serve protocol.
- `test_cli_worker_tree_status_and_live(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test cli worker tree status and live.
- `test_module_main_success_and_error(monkeypatch: pytest.MonkeyPatch) -> None` — Handle test module main success and error.
- `test_launcher_timeout(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise launch timeout when a worker never becomes discoverable.
- `test_wait_for_disappeared_dependency(monkeypatch: pytest.MonkeyPatch) -> None` — Treat a disappeared dependency as failure.
- `test_fanout_disappearance_is_failure(monkeypatch: pytest.MonkeyPatch) -> None` — Fail a fan-out when a child disappears before completion.
- `test_obsolete_generation_cannot_publish_completion(monkeypatch: pytest.MonkeyPatch) -> None` — Prevent an obsolete execution generation from publishing state.
- `test_authenticated_serve_controls_executor(monkeypatch: pytest.MonkeyPatch) -> None` — Authenticate IPC and control a live command executor.
- `test_launcher_honors_existing_state_policy(monkeypatch: pytest.MonkeyPatch) -> None` — Reuse live dependencies while restarting direct reset-policy creates.

### `packages/pmanager/test_example_run.py`

Cover the bundled ``pmanager`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'pmanager'...`
- `test_example_module_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the example file's ``__main__`` entry with a stubbed API run.

### `packages/pmanager/test_examples.py`

Exercise the bundled pmanager examples as user-facing documentation.

- `test_example_entrypoint_delegates_to_api() -> None` — The package example shim re-exports the API example ``main``.
- `test_build_spec_defines_the_pipeline_graph() -> None` — The demo spec wires source, worker, mirror, and pipeline nodes.
- `test_cli_example_loads_a_json_specification(monkeypatch: pytest.MonkeyPatch) -> None` — The CLI demo validates and renders an explicit JSON spec.
- `test_api_example_runs_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None` — The object-API demo creates and observes a real worker.
- `test_application_worker_run_records_invocation() -> None` — The example worker accepts the documented run signature.

### `packages/pmanager/test_model.py`

Typed specification model contract tests.

- `test_mutable_validated_properties() -> None` — Every public assignment is revalidated.
- `test_round_trip_existing_specification() -> None` — Existing JSON becomes a typed lossless model.
- `test_programmatic_graph_and_orchestrator() -> None` — Build a complete graph without authoring JSON.
- `test_graph_validation_rejects_unknown_reference() -> None` — Unknown dependencies fail before runtime.
- `test_validation_branches_and_serializers(tmp_path: Path) -> None` — Exercise mutable validation and serializer branches.
- `test_reference_concurrency_resource_validation() -> None` — Exercise nested model validation branches.
- `test_global_and_process_definition_validation() -> None` — Exercise remaining global and process validation paths.

### `packages/pmanager/test_object_api.py`

Object-first API tests.

- `test_object_references_are_retained() -> None` — Dependencies retain exact process object identity.
- `test_policy_is_compiled() -> None` — Policy extension data reaches the serializable model.
- `test_lifecycle_hooks_and_kill_timeout() -> None` — Decorators resolve bound worker-side lifecycle hooks.
- `test_status_decorator_marks_status_hook() -> None` — The status decorator registers a query lifecycle hook.
- `test_lifecycle_hook_and_broadcast_dispatch() -> None` — Exercise lifecycle resolution, dispatch, timeout, and metadata.
- `test_builder_validation_and_reference_edges() -> None` — Exercise builder validation and direct-reference edge cases.

### `packages/pmanager/test_platform.py`

Cross-platform backend contract tests.

- `test_posix_backend(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise POSIX discovery, detach, and signal operations.
- `test_posix_proc_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Discover process command lines without requiring a ``ps`` binary.
- `test_windows_discovery_and_detach(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise Windows CIM discovery and detached flags.
- `test_windows_pause_resume(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise Windows suspend/resume success and failures.
- `test_windows_terminate(monkeypatch: pytest.MonkeyPatch) -> None` — Exercise Windows tree termination success and failure.

### `packages/pmanager/test_spec.py`

Specification smoke tests.

- `class Constants` — Group module-level constants.
  - `expected_children` = `2`
  - `root` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'pmanager'`
- `test_spec_has_all_examples() -> None` — Verify all demonstration processes are defined.
- `test_e_is_parallel_join() -> None` — Verify E is configured as a parallel fan-out/join process.
- `test_c_is_global_singleton_runner() -> None` — Verify C uses global single-runner concurrency.

### `packages/project_python/__init__.py`

Test the shared project virtual-environment bootstrap.


### `packages/project_python/test_examples.py`

Exercise the ``project_python`` re-exec example delegation chain.

- `test_example_switches_venv_then_runs_the_tool(monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` re-execs into the venv and invokes the real tool.
- `test_example_swaps_and_restores_build_constants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` redirects ``Constants`` paths for the demo and restores them.

### `packages/project_python/test_venv.py`

Exercise the shared project virtual-environment bootstrap.

- `class Constants` — Group module-level constants.
  - `repo` = `Path(__file__).resolve().parents[4]`
- `test_switch_to_project_venv_reexecutes_with_original_arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Use the local interpreter and preserve the requested command.
- `test_switch_to_project_venv_is_safe_without_a_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Return when the environment is missing or already active.
- `test_switch_to_project_venv_skips_multiprocessing_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Worker processes inherit a foreign ``sys.argv`` and must not re-execute.
- `test_executable_tools_and_scripts_use_project_python() -> None` — Every executable Exactus/exactus/packages boundary uses the switch.
- `test_project_root_falls_back_to_package_grandparent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Use the package grandparent when no ancestor owns ``.venv``.
- `test_switch_returns_when_argv_has_no_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Skip replacement for interpreter-only invocations like ``-c``.
- `test_switch_resolves_program_through_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Resolve a bare command name through ``PATH`` before replacing.
- `test_main_module_runs_the_requested_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Fall back to the unqualified import and ``run_path`` the script.

### `packages/rename_project/__init__.py`

Tests of the `exactus/packages/rename_project/` renamer.


### `packages/rename_project/assertions.py`

Keyword-only assertion helpers for the rename_project tests.

- `fail(*, message: str) -> NoReturn` — Fail the running test.
- `expect_true(*, condition: bool, message: str='') -> None` — Require ``condition`` to hold.
- `expect_false(*, condition: bool, message: str='') -> None` — Require ``condition`` not to hold.
- `expect_equal(*, actual: object, expected: object, message: str='') -> None` — Require two values to compare equal.
- `expect_not_equal(*, actual: object, expected: object, message: str='') -> None` — Require two values to compare unequal.
- `expect_in(*, member: object, container: Container[object], message: str='') -> None` — Require ``member`` to be contained in ``container``.
- `expect_not_in(*, member: object, container: Container[object], message: str='') -> None` — Require ``member`` to be absent from ``container``.
- `expect_none(*, value: object, message: str='') -> None` — Require ``value`` to be ``None``.
- `expect_not_none(*, value: object, message: str='') -> None` — Require ``value`` not to be ``None``.

### `packages/rename_project/test_adversarial_semantics.py`

Adversarial semantic-safety tests for rename_project.

- `class Expected` — Expected disposition of an ``abc.cde`` occurrence.
  - `SAFE` = `'safe'`
  - `GUARDED` = `'guarded'`
- `class Case` — One adversarial source specimen.
  - Fields: `name: str`, `suffix: str`, `source: str`, `expected: tuple[Expected, ...]`
- `class Constants` — Group module-level constants.
  - `dotted` = `compile_pattern(pattern='abc\\.cde')`
  - `minimum_cases` = `250`
  - `minimum_guarded` = `50`
  - `base_cases` = `(Case(name='py-attribute', suffix='.py', source='x = abc.cde\n', expected...`
  - `cases` = `base_cases + _generated_cases()`
- `test_adversarial_classification(case: Case) -> None` — Every adversarial occurrence must receive its declared disposition.
- `test_corpus_has_safety_weight() -> None` — Prevent accidental shrinking of the high-risk regression corpus.
- `test_utf8_byte_character_round_trip() -> None` — Every Unicode character boundary must map back exactly.
- `test_structural_validation_rejects_invalid_source(suffix: str, valid: str, invalid: str) -> None` — Post-rewrite parser validation must reject malformed source.
- `test_parser_contracts() -> None` — Every configured Tree-sitter grammar must load and parse a specimen.
- `test_source_file_exists() -> None` — Keep this suite colocatable with the standalone script.

### `packages/rename_project/test_assertions.py`

Every assertion helper passes on good input and fails on bad input.

- `test_helpers_accept_valid_expectations() -> None` — Helpers return quietly when the expectation holds.
- `test_helpers_raise_on_violated_expectations() -> None` — Each helper raises ``AssertionError`` when the expectation fails.

### `packages/rename_project/test_cli_behavior.py`

CLI-level behavior of the project renamer: plans, prompts, rollback.

- `class Constants` — Group module-level constants.
  - `old` = `'abc_cde'`
  - `new` = `'foo_bar'`
  - `rp` = `modules['rename_project']`
  - `cli_help` = `modules['cli_help']`
- `test_restyles_every_casing(tmp_path: Path) -> None` — Each spelling is rendered in the matching style of the new name.
- `test_markdown_heading_and_inline_code(tmp_path: Path) -> None` — Headings use Title Case while inline code keeps its style.
- `test_single_word_name_follows_file_kind(tmp_path: Path) -> None` — An ambiguous spelling resolves by whether the file is code or prose.
- `test_preserves_crlf_bom_and_mode(tmp_path: Path) -> None` — Line endings, a BOM, and the executable bit survive the rewrite.
- `test_absolute_paths(tmp_path: Path) -> None` — In-project paths become relative; external ones are shielded.
- `test_shebang_binary_and_symlink_untouched(tmp_path: Path) -> None` — Shebangs, binary payloads, and symlinks are never rewritten.
- `test_renames_files_and_directories(tmp_path: Path) -> None` — Names carrying the old name are restyled, deepest first.
- `test_pyproject_name_is_detected(tmp_path: Path) -> None` — The distribution name is an old name even if the directory differs.
- `test_dry_run_and_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--dry-run`` changes nothing and writing needs ``--yes``.
- `test_collisions_stop_before_any_change(tmp_path: Path) -> None` — Two paths mapping to one destination abort the whole rename.
- `test_existing_root_target_is_refused(tmp_path: Path) -> None` — A target directory that already exists aborts the rename.
- `test_rolls_back_when_a_step_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A failing rename restores contents and names.
- `test_invalid_and_identical_names(tmp_path: Path) -> None` — Bad targets are refused with a non-zero status.
- `test_loose_boundary_reaches_inside_identifiers(tmp_path: Path) -> None` — ``--boundary loose`` renames compounds such as ``abc_cde_core``.
- `test_gitignored_files_are_left_alone(tmp_path: Path) -> None` — Inside a repository only tracked and unignored files are rewritten.
- `test_mixed_case_spellings_are_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Spellings the matcher cannot restyle are left alone and reported.
- `test_abbreviations_are_exact_and_opt_in(tmp_path: Path) -> None` — ``AT`` is renamed only when asked, case-sensitively and standalone.
- `test_short_lowercase_abbreviation_needs_consent(tmp_path: Path) -> None` — A lowercase ``at`` is refused unless explicitly allowed.
- `class FakeGitHub` — Record GitHub CLI calls instead of contacting GitHub.
  - `__init__(self, *, fail: bool=False) -> None` — Create the recorder.
- `test_github_rename_updates_repo_remote_and_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--github`` renames the repository, the remote, and file URLs.
- `test_github_failure_rolls_back_local_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A failed repository rename leaves files, folder, and remote intact.
- `test_github_needs_a_github_remote(tmp_path: Path) -> None` — A project without a GitHub remote is refused before any change.
- `test_github_rename_is_undone_when_repointing_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — If the remote cannot be repointed, the GitHub rename is reversed.
- `class FakeTerminal` — Scripted standard input that claims to be a terminal.
  - `__init__(self, *, answers: list[str]) -> None` — Create the terminal.
  - `isatty() -> bool` — Report terminal attachment.
  - `readline(self) -> str` — Return the next scripted answer.
- `test_discovered_repository_is_offered_and_renamed_on_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without ``--github`` a found repository is offered; "y" renames it.
- `test_declining_the_github_question_keeps_the_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Answering "n" renames locally but leaves GitHub untouched.
- `test_yes_flag_never_renames_a_discovered_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without a terminal, ``--yes`` leaves a found repository alone.
- `test_no_github_flag_never_asks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--no-github`` skips both the discovery and the question.
- `test_prompt_formatting_and_retry(monkeypatch: pytest.MonkeyPatch) -> None` — The prompt is ANSI-styled on a terminal and re-asks on bad input.
- `test_dotted_python_attribute_vs_string(tmp_path: Path) -> None` — Python code and f-strings keep ``abc.cde``; plain strings change.
- `test_dotted_javascript_and_css(tmp_path: Path) -> None` — Property access and CSS selectors are kept; strings are renamed.
- `test_dotted_markdown_and_chains(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Prose is renamed; inline code and longer dotted chains are reported.
- `test_dotted_import_paths_that_exist_are_kept(tmp_path: Path) -> None` — A dotted name that addresses a real package path is never renamed.
- `test_dotted_modes_override_detection(tmp_path: Path) -> None` — ``--dotted always`` renames code too; ``never`` renames nothing.

### `packages/rename_project/test_cli_help.py`

ANSI-styled ``--help`` output of the ``cli_help`` module.

- `class Tty` — Terminal-like stdout stand-in.
  - `isatty() -> bool` — Report a terminal.
- `test_cli_help_styling() -> None` — Colors appear only on terminals without NO_COLOR.

### `packages/rename_project/test_example.py`

The ``examples/run.py`` demo renames only a throwaway copy.

- `test_example_renames_only_the_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The demo leaves a renamed ``demo_app`` and a pristine template.
- `test_template_cli_prints_the_project_banner(capsys: pytest.CaptureFixture[str]) -> None` — The template ``project.cli`` runs its banner entry point.

### `packages/rename_project/test_main_bootstrap.py`

Cover the rename_project package bootstrap entry points.

- `class Constants` — Group module-level constants.
  - `package` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'rename_pr...`
  - `main_module` = `package / '__main__.py'`
  - `cli_example` = `package / 'examples' / 'project' / 'src' / 'project' / 'cli.py'`
- `test_main_attribute_imports_the_cli_entry_point() -> None` — Resolve ``main`` through the package ``__getattr__`` hook.
- `test_getattr_rejects_unknown_attributes() -> None` — Raise ``AttributeError`` for names the package does not export.
- `test_main_module_uses_the_secondary_import_candidate(monkeypatch: pytest.MonkeyPatch) -> None` — Fall back to the unqualified ``project_python`` import candidate.
- `test_main_module_survives_without_project_python(monkeypatch: pytest.MonkeyPatch) -> None` — Set ``switch`` to ``None`` when both import candidates fail.
- `test_cli_example_runs_as_a_script(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the bundled example CLI module as ``__main__``.

### `packages/rename_project/test_next_safety_batch.py`

Regression tests for SQL, Unicode geometry, golden projects, rollback.

- `class Constants` — Group module-level constants.
  - `rp` = `modules['rename_project']`
- `test_python_ast_utf8_columns_are_character_columns() -> None` — Python AST UTF-8 columns are character columns.
- `test_sql_dotted_identifier_excludes_literal_and_comments() -> None` — SQL dotted identifier excludes literal and comments.
- `test_sql_file_rewrites_identifier_not_dotted_literal(tmp_path: Path) -> None` — SQL file rewrites identifier not dotted literal.
- `test_golden_project_updates_files_and_sqlite(tmp_path: Path) -> None` — Golden project updates files and SQLite.
- `test_failure_after_database_mutation_restores_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Failure after database mutation restores everything.
- `test_application_sql_reference_inventory(tmp_path: Path) -> None` — Application SQL reference inventory.

### `packages/rename_project/test_roundtrip.py`

Renaming forth and back reproduces the original project exactly.

- `class Constants` — Group module-level constants.
  - `old` = `'abc_cde'`
  - `new` = `'foo_bar'`
  - `files` = `{'pyproject.toml': '[project]\nname = "abc-cde"\n', 'README.md': dedent(t...`
- `test_rename_there_and_back_is_lossless(tmp_path: Path) -> None` — A→B then B→A restores every text file byte for byte.

### `packages/rename_project/test_safety_metrics.py`

Safety-oriented corpus metrics with asymmetric failure accounting.

- `class Disposition` — Simplified classification used by metric accounting.
  - `SAFE` = `'safe'`
  - `GUARDED` = `'guarded'`
- `class Metrics` — Classification quality counters.
  - Fields: `total: int`, `correct: int`, `dangerous_false_positives: int`, `conservative_false_negatives: int`
  - `accuracy(self) -> float` — Exact classification accuracy.
- `measure(expected: tuple[Disposition, ...], actual: tuple[Disposition, ...]) -> Metrics` — Measure safety errors, distinguishing dangerous from conservative.
- `test_metric_distinguishes_error_severity() -> None` — A permissive mistake must not be conflated with a conservative miss.

### `packages/rename_project/test_scanners.py`

Exercise the language-aware safe-span scanners in the renamer.

- `class Constants` — Group module-level constants.
  - `first_line` = `1`
  - `python_docstring_line` = `1`
  - `python_value_line` = `4`
  - `python_fstring_line` = `5`
  - `sql_names_line` = `1`
  - `javascript_doc_line` = `1`
  - `javascript_string_line` = `2`
  - `javascript_comment_line` = `6`
  - `javascript_block_line` = `7`
  - `css_comment_line` = `1`
  - `markdown_heading_line` = `1`
  - `markdown_prose_line` = `2`
  - `markdown_fence_body` = `5`
  - `markdown_quote_line` = `7`
  - `text_tail_line` = `2`
  - `unicode_comment_line` = `1`
  - `python_source` = `dedent(text='    """Module docstring mentioning abc.cde."""\n    import a...`
  - `sql_source` = `dedent(text='    SELECT "abc.cde", `abc.cde`, [abc.cde] FROM abc_cde\n...`
  - `javascript_source` = `dedent(text='    /** JSDoc abc.cde */\n    const s = \'abc.cde\';\n    co...`
  - `css_source` = `dedent(text='    /* abc.cde comment */\n    .abc-cde { content: \'abc.cde...`
  - `html_source` = `dedent(text='    <html><head><style>/* abc.cde */ .a { color: red }</styl...`
  - `markdown_source` = `dedent(text='    # Heading abc.cde\n    Prose paragraph with abc.cde ment...`
  - `text_source` = `'code abc.cde # comment abc.cde\nplain text\n'`
  - `unicode_source` = `"// café ☕ abc.cde\nconst s = 'abc.cde';\n"`
- `test_python_safe_spans_cover_strings_and_comments() -> None` — Python literals, docstrings, and comments are marked safe.
- `test_python_safe_spans_fail_closed_on_syntax_error() -> None` — Malformed Python produces no safe regions.
- `test_python_safe_spans_exclude_fstring_bodies() -> None` — Interpolated f-string lines keep no dotted-safe regions.
- `test_sql_safe_spans_skip_strings_and_comments() -> None` — SQL strings and comments are excluded; identifiers stay safe.
- `test_javascript_safe_offsets_marks_literals() -> None` — JavaScript strings/templates/comments are marked; DOM calls stay out.
- `test_typescript_safe_offsets_parse_ts_and_tsx() -> None` — TypeScript and TSX sources run through the JavaScript scanner.
- `test_css_safe_offsets_mark_strings_and_comments() -> None` — CSS comments and string values are marked; selectors stay out.
- `test_html_safe_offsets_mark_prose_and_attributes() -> None` — HTML prose, quoted attributes, and embedded regions are marked.
- `test_markdown_safe_offsets_mark_prose() -> None` — Markdown prose and quotes are marked; fenced code stays out.
- `test_unknown_suffix_falls_back_to_comment_spans() -> None` — Unrecognized suffixes use the generic comment-span fallback.
- `test_non_ascii_text_maps_byte_offsets_to_characters() -> None` — Multi-byte text keeps character (not byte) span offsets.
- `test_web_symbol_scanner_indexes_cross_references(tmp_path: Path) -> None` — The HTML/CSS/JS symbol scanner links classes, ids, and references.

### `packages/rename_project/test_sqlite_semantics.py`

SQLite safety tests for the project renamer.

- `class Constants` — Group module-level constants.
  - `rp` = `modules['rename_project']`
- `test_sqlite_text_updates_and_blob_is_untouched(tmp_path: Path) -> None` — SQLite text updates and blob is untouched.
- `test_sqlite_without_rowid_composite_primary_key(tmp_path: Path) -> None` — SQLite without rowid composite primary key.
- `test_sqlite_generated_column_is_not_written(tmp_path: Path) -> None` — SQLite generated column is not written.
- `test_sqlite_schema_match_is_guarded_not_rewritten(tmp_path: Path) -> None` — SQLite schema match is guarded not rewritten.
- `test_sqlite_wal_database_is_updated_consistently(tmp_path: Path) -> None` — SQLite wal database is updated consistently.
- `test_sqlite_is_restored_when_later_filesystem_step_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — SQLite is restored when later filesystem step fails.
- `test_sqlite_schema_table_column_dependencies_are_propagated(tmp_path: Path) -> None` — SQLite schema table column dependencies are propagated.
- `test_sqlite_schema_is_opt_in(tmp_path: Path) -> None` — SQLite schema is opt in.
- `test_sqlite_schema_collision_is_guarded(tmp_path: Path) -> None` — SQLite schema collision is guarded.
- `test_sqlite_ambiguous_column_rename_rolls_back(tmp_path: Path) -> None` — SQLite ambiguous column rename rolls back.
- `test_sqlite_schema_restored_after_later_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — SQLite schema restored after later failure.
- `test_sqlite_named_index_is_recreated_with_new_name(tmp_path: Path) -> None` — SQLite named index is recreated with new name.

### `packages/scene_description/__init__.py`

Tests for the scene_description package.


### `packages/scene_description/conftest.py`

Shared fixtures and fakes for the scene_description tests.

- `element(*, selector: str='#node', frame: dict[str, JsonValue] | None=None, visual_cause_selector: JsonValue=None, **fields: JsonValue) -> dict[str, JsonValue]` — Build one scene-graph element entry.
- `scene(*, elements: dict[str, dict[str, JsonValue]] | None=None, metadata: JsonValue=None, reference: JsonValue=None) -> dict[str, JsonValue]` — Build one descriptor scene manifest.
- `report(*, trees: JsonValue=None) -> dict[str, JsonValue]` — Build a minimal Visual Cause report.
- `class FakePage` — In-memory ``PageLike`` fake recording browser interactions.
  - `descriptor_installed` = `False`
  - `evaluate_result` = `None`
  - `__init__(self) -> None` — Initialize empty interaction journals.
  - `add_script_tag(self, *, content: str) -> JsonValue` — Record an injected script source.
  - `evaluate(self, *, expression: str, arg: JsonValue=None) -> JsonValue` — Record an evaluation and return the configured result.
- `make_scene() -> Callable[..., dict[str, JsonValue]]` — Expose the scene manifest builder as a fixture.

### `packages/scene_description/support.py`

Typed assertion helpers shared by the scene_description tests.

- `fail(*, message: str) -> NoReturn` — Fail the running test.
- `expect_true(*, condition: object, message: str='') -> None` — Require ``condition`` to be truthy.
- `expect_false(*, condition: object, message: str='') -> None` — Require ``condition`` to be falsy.
- `expect_equal(*, actual: object, expected: object, message: str='') -> None` — Require ``actual`` to equal ``expected``.
- `expect_in(*, member: object, container: Container[object]) -> None` — Require ``member`` to appear inside ``container``.
- `expect_none(*, value: object, message: str='') -> None` — Require ``value`` to be ``None``.
- `require_json_dict(*, value: object) -> dict[str, JsonValue]` — Require ``value`` to be a JSON object.
- `require_json_list(*, value: object) -> list[JsonValue]` — Require ``value`` to be a JSON array.
- `expect_raises(*, kind: type[BaseException], call: Callable[[], object]) -> BaseException` — Require ``call`` to raise ``kind`` and return the exception.

### `packages/scene_description/test_capture.py`

Tests for the SceneDescriptor Playwright bridge.

- `test_init_uses_bundled_runtime() -> None` — The default script path points at the packaged JS runtime.
- `test_init_accepts_custom_script_path(tmp_path: Path) -> None` — A custom script path replaces the bundled runtime source.
- `test_install_injects_when_missing() -> None` — Pages lacking globalThis.Descriptor receive the runtime.
- `test_install_skips_when_available() -> None` — Pages already exposing Descriptor are left alone.
- `test_describe_builds_browser_payload() -> None` — The evaluate call forwards selector and camelCase options.
- `test_describe_defaults() -> None` — Default selector and options are supplied.
- `test_describe_rejects_non_dict_result() -> None` — A non-object runtime result raises TypeError.
- `test_describe_installs_before_evaluate() -> None` — describe() injects the runtime when the page lacks it.

### `packages/scene_description/test_changes.py`

Tests for the deterministic SceneChangeDescriber.

- `test_describe_element_missing_in_both_scenes() -> None` — An unmatched selector yields no change.
- `test_describe_element_appeared() -> None` — An element present only in B reports as appeared.
- `test_describe_element_disappeared() -> None` — An element present only in A reports as disappeared.
- `test_describe_element_identical() -> None` — Identical elements produce no change.
- `test_describe_element_movement() -> None` — Translation deltas describe direction and distance.
- `test_describe_element_resize() -> None` — Geometry deltas describe width and height transitions.
- `test_describe_element_below_tolerance() -> None` — Sub-tolerance geometry deltas are ignored.
- `test_describe_element_missing_frames() -> None` — Elements without usable frames skip geometry entirely.
- `test_describe_element_identity_fields() -> None` — Text, name, and role changes each produce a detail line.
- `test_element_matches_visual_cause_selector() -> None` — ``visualCauseSelector`` aliases resolve elements too.
- `test_elements_requires_dict_container() -> None` — Non-dict ``elements`` payloads yield no matches.
- `test_elements_skips_non_dict_entries() -> None` — Malformed element entries are ignored.
- `test_selectors_requires_string() -> None` — Non-string selectors never join the candidate set.
- `test_describe_scene_sorted_union() -> None` — Default candidates are the sorted union of both scenes.
- `test_describe_scene_explicit_selectors() -> None` — Callers can restrict description to specific selectors.
- `test_label_falls_back_to_text() -> None` — Text evidence labels elements lacking a name.
- `test_label_falls_back_to_tag_and_selector() -> None` — Tag, then the raw selector, label anonymous elements.
- `test_label_long_text_truncates() -> None` — Long text labels collapse whitespace and truncate at 80 chars.
- `test_frame_requires_visual_and_numeric() -> None` — Frame extraction ignores missing or non-numeric geometry.
- `test_element_change_as_json() -> None` — ElementChange serializes selector, summary, and details list.
- `test_geometry_without_any_frame_keys() -> None` — A present-but-empty viewportFrame skips geometry output.
- `test_scene_b_and_a_empty_details() -> None` — describe_scene filters selectors producing no change.

### `packages/scene_description/test_examples.py`

Tests for the runnable scene_description examples.

- `test_example_main_writes_enriched_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``examples.run.main`` emits JSON and Markdown next to its inputs.
- `test_example_main_seeds_inputs_when_results_are_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` synthesizes inputs under ``.scratch`` when none exist.
- `test_examples_module_entrypoint(tmp_path: Path) -> None` — ``python -m exactus.packages.scene_description.examples`` runs the demo.

### `packages/scene_description/test_js_runtime.py`

Run the browser test suite and enforce JavaScript coverage.

- `class Constants` — Module-level paths shared by the JavaScript tests.
  - `js_root` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'scene_des...`
  - `tests_js_root` = `Path(__file__).parent / 'js'`
  - `runtime_js` = `js_root / 'unified_evidence.js'`
  - `browser_test_js` = `tests_js_root / 'browser.test.mjs'`
  - `coverage_floor` = `90.0`
- `test_runtime_js_parses() -> None` — The evidence runtime parses under Node.
- `test_browser_test_js_parses() -> None` — The in-browser test suite parses under Node.
- `test_browser_suite_and_coverage() -> None` — Run the in-browser suite and require the coverage floor.

### `packages/scene_description/test_main.py`

Tests for the scene_description command-line entry point.

- `test_load_returns_dict(tmp_path: Path) -> None` — ``_load`` returns parsed JSON objects.
- `test_load_rejects_non_object(tmp_path: Path) -> None` — ``_load`` rejects JSON documents that are not objects.
- `test_main_enriches_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The CLI writes an enriched report plus a Markdown summary.

### `packages/scene_description/test_models.py`

Tests for the DescriptionOptions model and JSON aliases.

- `test_browser_options_defaults() -> None` — Default flags serialize with the browser camelCase API.
- `test_browser_options_reflects_overrides() -> None` — Non-default flags flow through to the browser payload.
- `test_options_are_frozen() -> None` — The options dataclass rejects attribute mutation.
- `test_package_exports() -> None` — Every documented export resolves on the package namespace.

### `packages/scene_description/test_support.py`

Validate the shared scene_description assertion helpers.

- `test_fail_raises_assertion_error() -> None` — ``fail`` always raises ``AssertionError`` with the message.
- `test_expect_helpers_reject_bad_values() -> None` — Every expectation helper fails with a descriptive message.
- `test_require_json_helpers_validate_types() -> None` — JSON type helpers return values or reject non-matching types.
- `test_expect_raises_returns_exception() -> None` — ``expect_raises`` returns the exception or fails when absent.
- `test_expect_helpers_accept_good_values() -> None` — Every expectation helper passes on valid input.

### `packages/scene_description/test_visual_cause.py`

Tests for the VisualCauseDescriber report enrichment.

- `test_enrich_adds_change_description() -> None` — Enrichment always attaches the change_description block.
- `test_enrich_does_not_mutate_report() -> None` — The input report object is left untouched.
- `test_enrich_non_list_trees() -> None` — Non-list change_trees produce an empty description set.
- `test_enrich_skips_non_dict_nodes() -> None` — Malformed change-tree entries are ignored.
- `test_enrich_node_without_selector() -> None` — Nodes without a string selector receive no description.
- `test_enrich_matched_node_serializes_context() -> None` — Matched nodes carry categories, mechanisms, and root_cause.
- `test_enrich_recurses_descendants() -> None` — Descriptions propagate through relations.descendants chains.
- `test_enrich_missing_relations_or_descendants() -> None` — Nodes lacking relations or a descendant list stop recursion.
- `test_strings_filters_members() -> None` — ``strings`` keeps only string members of a list.
- `test_scene_metadata_fallbacks() -> None` — Missing or malformed metadata/reference default to empty dicts.
- `test_markdown_missing_block() -> None` — A report without change_description renders the fallback.
- `test_markdown_renders_summary_and_elements() -> None` — Markdown lists the summary plus each element summary.
- `test_markdown_without_elements_list() -> None` — A missing or malformed elements list renders just the summary.
- `test_markdown_missing_summary_fallback() -> None` — A missing summary falls back to the default sentence.

### `packages/screenshot/__init__.py`

Tests of `exactus/screenshot`.


### `packages/screenshot/test_capture_support.py`

Image similarity and the high-level screenshot capture API.

- `class Constants` — Group module-level constants.
  - `max_distinct` = `0.95`
  - `page` = `dedent(text='    <!doctype html><html><body style="margin:0">\n    <div i...`
- `test_similarity_identical_and_different() -> None` — Identical images score one and different images score lower.
- `test_similarity_sources(tmp_path: Path) -> None` — Paths, Base64 strings, data URLs, bytes, files and images load.
- `class Unseekable` — File-like object that cannot seek.
  - `__init__(self, data: bytes) -> None` — Store data.
  - `seekable() -> bool` — Report that seeking is unsupported.
  - `read(self) -> bytes` — Return all data.
- `class Broken` — File-like object whose reads fail.
  - `seekable() -> bool` — Report seekability.
  - `read() -> NoReturn` — Fail reads.
- `test_similarity_errors(tmp_path: Path) -> None` — Undecodable sources raise ``ValueError``.
- `test_similarity_history_cache() -> None` — History comparisons accumulate and can be cleared.
- `test_snapshot_capture_options(tmp_path: Path) -> None` — Expanded captures honor caps, clipping, formats and scales.
- `test_screenshot_api_sources(tmp_path: Path, demo_url: str) -> None` — The URL API works standalone and over supplied browser objects.
- `test_collector_records_websocket_diagnostics() -> None` — Socket errors and error-bearing frames become diagnostics.
- `capture_implementation(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None` — Verify both public capture implementations against the same contract.

### `packages/screenshot/test_examples.py`

Run the public screenshot example against a live demonstration site.

- `test_screenshot_example(tmp_path: Path, demo_url: str, monkeypatch: pytest.MonkeyPatch) -> None` — The screenshot CLI writes real PNGs at all documented widths.
- `test_main_module_serves_the_demo_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run ``examples/run.py`` via ``__main__`` with a stubbed server.
- `test_main_module_with_explicit_url_skips_the_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A positional URL captures directly without serving the bundle.
- `test_main_module_reuses_the_recorded_server(monkeypatch: pytest.MonkeyPatch) -> None` — An adopted demo server is not terminated afterwards.

### `packages/screenshot/test_main.py`

Cover the ``exactus.packages.screenshot`` command-line entry point.

- `class Constants` — Group module-level constants.
  - `main_module` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'screensho...`
- `test_main_captures_through_the_stubbed_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Drive ``main`` end to end with the screenshot package stubbed.

### `packages/server/__init__.py`

Tests of `exactus/server`.


### `packages/server/test_examples.py`

Coverage for the ``exactus/server/examples`` demonstration.

- `test_example_serves_pings_and_reuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run the demo end to end against the bundled site.
- `test_example_reports_unready_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exit ``1`` when the spawned server never accepts connections.
- `test_example_reports_adoption_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exit ``1`` when ``reuse_server`` cannot adopt the instance.

### `packages/server/test_main.py`

Cover the ``exactus.packages.server`` command-line entry point.

- `class Constants` — Group module-level constants.
  - `main_module` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'server' /...`
- `test_main_falls_back_to_the_unqualified_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Use ``project_python`` when the qualified import is unavailable.
- `test_main_stop_reports_missing_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--stop`` returns one when no server recorded its state.
- `test_main_stop_terminates_a_recorded_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``--stop`` terminates the adopted server and clears its state.
- `test_main_serve_reports_a_server_that_never_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Return one when the spawned server never accepts connections.
- `test_main_serve_blocks_until_signaled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Serve until the installed signal handler releases the wait loop.

### `packages/server/test_ports.py`

Exercise ownership checks and safe fixed-port replacement failures.

- `test_listener_identity(monkeypatch: pytest.MonkeyPatch, output: str, command: str, expected: int | None) -> None` — Only the requested package or factory may own a replaceable listener.
- `test_inline_factory_requires_import_and_call(command: str) -> None` — A mention, malformed snippet or unrelated factory is insufficient.
- `test_owner_query_failure_and_current_process(monkeypatch: pytest.MonkeyPatch) -> None` — Unavailable process tools and our own PID fail closed.
- `test_replacement_paths(monkeypatch: pytest.MonkeyPatch, mode: str) -> None` — Replace only verified owners, escalating only while ownership persists.

### `packages/server/test_server_lifecycle.py`

Loopback server helpers: logs, ports, probing and lifecycle.

- `test_parse_server_log(tmp_path: Path) -> None` — Access logs yield deduplicated 4xx/5xx diagnostics.
- `test_accepts_free_port_and_state(tmp_path: Path) -> None` — Port probing and state-file naming are deterministic.
- `test_probe_and_wait_for_dead_process() -> None` — A dead pid short-circuits probing and waiting.
- `test_probe_default_url_finds_listener(monkeypatch: pytest.MonkeyPatch) -> None` — The first accepting default host is reported.
- `test_serve_ping_reuse_and_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A served directory answers the identity ping and can be reused.
- `test_start_entrypoint_exports_port(tmp_path: Path) -> None` — Entrypoint scripts receive the assigned port and log output.
- `test_serve_adopts_a_recorded_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A surviving recorded server is adopted instead of respawning.
- `test_serve_retries_a_failed_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A server that dies during spawn is replaced on the next attempt.
- `test_serve_reports_persistent_spawn_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — After every spawn attempt dies, serve reports the startup error.

### `packages/shebang_update/__init__.py`

Tests of the `exactus/packages/shebang_update/` shebang updater.


### `packages/shebang_update/test_examples.py`

Cover the shebang_update examples demonstration.

- `test_example_repairs_only_the_stale_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Rebuild the demo project and fix only its stale shebang.
- `test_example_module_runs_as_a_script() -> None` — Execute ``run.py`` with ``__name__`` equal to ``__main__``.
- `test_examples_main_module_runs_the_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Execute ``examples/__main__.py`` as the ``__main__`` module.

### `packages/shebang_update/test_shebang_update.py`

Exercise the packaged virtual-environment shebang updater.

- `class Constants` — Group module-level constants.
  - `stale` = `b'#!/previous/checkout/demo_project/.venv/bin/python3\n'`
  - `body` = `b"print('demo')\n"`
- `test_settings_builds_the_project_interpreter_shebang(tmp_path: Path) -> None` — Render the absolute shebang for the configured environment.
- `test_run_rewrites_a_stale_shebang(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Rewrite the first line and preserve the remainder of the file.
- `test_run_skips_files_inside_the_environment(tmp_path: Path) -> None` — Leave files below ``.venv`` untouched even when stale.
- `test_run_ignores_non_matching_first_lines(tmp_path: Path) -> None` — Skip files without an absolute venv Python shebang.
- `test_run_leaves_current_shebangs_unchanged(tmp_path: Path) -> None` — Skip files already carrying the expected shebang, including CRLF.
- `test_run_survives_unwritable_files(tmp_path: Path) -> None` — Return ``False`` from the update when the rewrite is refused.
- `test_run_reports_zero_for_an_empty_project(tmp_path: Path) -> None` — Walk a tree without candidates without changing anything.
- `test_core_module_runs_main_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Execute ``core.py`` with ``__name__`` equal to ``__main__``.
- `test_main_updates_the_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Scan the current directory and report singular and plural counts.
- `test_main_module_switches_interpreter_and_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Switch to the project interpreter, then delegate to ``main``.
- `test_main_module_runs_without_a_bootstrap_candidate(monkeypatch: pytest.MonkeyPatch) -> None` — Skip the interpreter switch when ``project_python`` is absent.

### `packages/steps/__init__.py`

Test the exactus/packages/steps timestamped step trace.


### `packages/steps/test_examples.py`

Coverage for the ``exactus/packages/steps/examples`` demonstration.

- `test_example_writes_and_prints_the_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Emit the simulated run and print the resulting trace.
- `test_example_module_runs_as_a_script() -> None` — Execute ``run.py`` with ``__name__`` equal to ``__main__``.
- `test_examples_main_module_runs_the_demo() -> None` — Execute ``examples/__main__.py`` as the ``__main__`` module.
- `test_package_main_module_runs_the_demo() -> None` — Execute the steps entry point as the ``__main__`` module.

### `packages/steps/test_steps.py`

Exercise the reusable timestamped step trace.

- `class Constants` — Group module-level constants.
  - `stamp` = `'^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}[+-]\\d{2}:\\d{2} \\+...`
- `test_trace_is_a_noop_without_an_active_log() -> None` — Forward nothing and raise nothing when no log is active.
- `test_step_log_writes_timestamped_depth_lines(tmp_path: Path) -> None` — Write one timestamped, depth-indented line per recorded step.
- `test_nested_step_log_reuses_the_active_log(tmp_path: Path) -> None` — Reuse the outer log instead of truncating or reopening.
- `test_step_log_context_resets_active_and_closes(tmp_path: Path) -> None` — Deactivate the log and close its stream when the context exits.
- `test_step_log_degrades_when_destination_cannot_open(tmp_path: Path) -> None` — Disable the log silently when the file cannot be created.
- `test_write_failure_disables_the_stream(tmp_path: Path) -> None` — Drop the stream after one failed write without raising.
- `test_write_false_discards_every_step(tmp_path: Path) -> None` — ``[tool.steps] write = false`` never creates the trace file.
- `test_write_true_records_steps(tmp_path: Path) -> None` — ``[tool.steps] write = true`` keeps the trace file enabled.
- `test_pyproject_without_steps_section_keeps_writing(tmp_path: Path) -> None` — A pyproject without ``[tool.steps]`` leaves writing enabled.
- `test_main_writes_a_demonstration_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Write and print the package demonstration trace.
- `test_span_writes_begin_and_measured_end_lines(tmp_path: Path) -> None` — A span pairs a plain begin line with a ``@dur`` end line.
- `test_worker_threads_are_tagged_and_main_is_not(tmp_path: Path) -> None` — Only non-main threads receive an ``@thread`` trailer.
- `test_span_without_an_active_log_only_runs_the_body() -> None` — Spans are transparent when tracing is not active.
- `test_configured_sampling_writes_resource_lines(tmp_path: Path) -> None` — ``[tool.steps] sample`` adds ``~sample`` lines with usage fields.
- `test_sampling_is_off_without_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — No ``[tool.steps] sample`` key means no resource lines.

### `packages/test_packages.py`

Exercise the packages-wide example runner without spawning demos.

- `test_packages_entrypoint_forms(command: tuple[str, ...]) -> None` — Both directory and module execution expose the runner CLI.
- `test_packages_main_module_runs_the_cli(monkeypatch: pytest.MonkeyPatch) -> None` — ``exactus/packages/__main__.py`` executes the runner CLI in place.
- `test_packages_runs_every_example_without_errors() -> None` — Run every discovered example cleanly via the packages entry point.
- `test_discover_finds_sorted_runnable_examples() -> None` — Discovery lists every bundled ``examples/run.py`` once.
- `test_forms_reflects_the_script_flag() -> None` — Shebang examples gain the direct-script invocation form.
- `test_launch_reports_ok_fail_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``launch`` maps exit codes and timeouts onto report statuses.
- `test_show_prints_status_and_failure_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``show`` writes one line, plus the log tail for failures.
- `test_main_rejects_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None` — Unknown example names exit ``2`` and list the known set.
- `test_main_runs_stubbed_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` aggregates per-form reports into the exit status.

### `packages/todo_sync/__init__.py`

Tests for the reusable TODO dashboard synchronizer.


### `packages/todo_sync/test_dashboard.py`

Exercise the actual offline dashboard at desktop and mobile widths.

- `test_dashboard_controls(tmp_path: Path, width: int) -> None` — Verify offline search, filters, source links, reload and export.

### `packages/todo_sync/test_default_path.py`

The default CLI source and report live under ``exactus/docs/todo``.

- `test_default_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Running without --path writes both outputs to exactus/docs/todo.

### `packages/todo_sync/test_examples.py`

Exercise the bundled ``todo_sync`` synchronization example.

- `test_example_synchronizes_a_scratch_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The demo copies ``TODO.md`` into a scratch dir and syncs it.

### `packages/todo_sync/test_normalize.py`

Uniform headers preserve obligations and expose source metadata.

- `test_canonical_queue_schema() -> None` — Keep the real handoff queue explicit and IDs unique as it evolves.
- `test_headers_and_idempotence() -> None` — Keep IDs/states/details and allocate collision-free child IDs.
- `test_explicit_metadata_wins() -> None` — Description mentions cannot override normalized priority/category.
- `test_crlf_and_unknown_priority() -> None` — Preserve line endings and do not invent urgency.
- `test_normalization_check_is_read_only(tmp_path: Path) -> None` — Check audits legacy headers without replacing the source.
- `test_normalization_cannot_be_silently_ignored(mode: str) -> None` — Watcher control must reject a one-shot normalization flag.

### `packages/todo_sync/test_permissions.py`

Preserve private Markdown permissions and keep new HTML owner-only.

- `test_private_output(tmp_path: Path) -> None` — Atomic replacement must not make a private checklist world-readable.

### `packages/todo_sync/test_sync.py`

Validate parsing, atomic output, CLI and safe watcher lifecycle.

- `test_excluded_examples_and_parent_rollup() -> None` — Fences/comments never count and parent totals include descendants.
- `test_identifiers(ident: str) -> None` — Support Exactus and supplied roadmap ID conventions.
- `test_malformed_markers(source: str) -> None` — Reject duplicated, missing or reversed markers.
- `test_preserve_outside_managed_block() -> None` — Replacement preserves all whitespace outside the managed markers.
- `test_top_summary_updates_without_moving_detailed_tables() -> None` — Keep HTML totals at the top and detailed tables after task content.
- `test_duplicate_heading_anchor() -> None` — An empty earlier heading still consumes its slug suffix.
- `test_html_escaping() -> None` — Literal script tags cannot terminate the JSON data element.
- `test_check_and_html_repair(tmp_path: Path) -> None` — Check never writes; no-op preserves mtimes; missing HTML repairs.
- `test_concurrent_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An edit during rendering is retained instead of overwritten.
- `test_symlink_preflight(tmp_path: Path) -> None` — Reject output symlinks before changing Markdown or linked target.
- `test_cli(tmp_path: Path) -> None` — Check exit codes and mutually exclusive operations.
- `test_bad_intervals(tmp_path: Path, interval: float) -> None` — Invalid intervals cannot create a background process.
- `test_stale_state(tmp_path: Path) -> None` — Stale ownership requires inspection, never PID killing.
- `test_real_watcher(tmp_path: Path) -> None` — A detached child syncs edits and exits cooperatively.

### `packages/todo_sync/test_watch.py`

Cover the exclusive todo_sync watcher lifecycle.

- `class Constants` — Group module-level constants.
  - `document` = `'- [ ] pending\n- [x] done\n'`
  - `interval` = `0.01`
  - `wakeups` = `2`
- `test_watch_exits_on_the_token_matched_stop_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A stop file carrying the watcher token ends the loop cleanly.
- `test_watch_exits_on_keyboard_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Ctrl-C ends the loop and removes the ownership lock.
- `test_watch_records_stat_failures_and_recovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A vanished source records the error and keeps watching.
- `test_watch_rejects_a_nonpositive_interval(tmp_path: Path) -> None` — A nonpositive polling interval fails before any lock is created.
- `test_detached_child_reads_environment_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The child entry point forwards its environment to ``watch``.
- `test_start_rejects_a_nonpositive_interval(tmp_path: Path) -> None` — An invalid interval fails before touching ownership state.
- `test_start_returns_when_a_watcher_is_live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A fresh heartbeat short-circuits spawning a second watcher.
- `test_start_rejects_a_stale_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A lock without a heartbeat requires manual recovery.
- `test_start_returns_once_the_child_publishes_a_heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A spawned child whose heartbeat appears satisfies ``start``.
- `test_start_fails_when_the_child_exits_early(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A child that exits before its heartbeat raises ``ValueError``.
- `test_start_fails_when_the_heartbeat_never_arrives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A missing heartbeat past the deadline terminates the child.
- `test_stop_returns_when_no_lock_exists(tmp_path: Path) -> None` — A document without a lock has nothing to stop.
- `test_stop_rejects_a_stale_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A lock without a fresh heartbeat fails closed.
- `test_stop_writes_the_token_and_returns_when_the_lock_closes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The stop request carries the stored token and waits for cleanup.
- `test_stop_fails_when_the_watcher_ignores_the_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A persistent lock past the deadline raises ``ValueError``.

### `packages/tree/__init__.py`

Tests for ``exactus.packages.tree``.


### `packages/tree/test_example_run.py`

Cover the bundled ``tree`` example entry point.

- `class Constants` — Group module-level constants.
  - `example` = `Path(__file__).resolve().parents[4] / 'exactus' / 'packages' / 'tree' / '...`
- `test_example_module_runs_as_a_script() -> None` — Execute the example file's ``__main__`` entry for real.

### `packages/tree/test_tree.py`

Tests for TREE.txt-style directory and archive listings.

- `test_human_size_scales_units() -> None` — Format byte counts like the inventory renderer.
- `test_render_tree_lists_directory_recursively(tmp_path: Path) -> None` — Render a directory with nested ``├──``/``└──`` rows.
- `test_render_tree_lists_zip_members(tmp_path: Path) -> None` — Render an archive's members without extracting it.
- `test_render_tree_accepts_member_lists(tmp_path: Path) -> None` — Render explicit string and ``Path`` members.
- `test_render_tree_include_exclude_globs(tmp_path: Path) -> None` — Filter members through include and exclude globs.
- `test_render_tree_marks_missing_members(tmp_path: Path) -> None` — Keep absent member labels with zeroed stats.
- `test_members_for_single_file(tmp_path: Path) -> None` — Resolve a lone file argument to one member.
- `test_main_renders_sources_and_writes_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Render CLI sources, honoring globs, filters and ``-o``.
- `test_main_usage_without_sources(monkeypatch: pytest.MonkeyPatch) -> None` — Exit ``1`` with usage when nothing resolves.

### `packages/visual_cause/__init__.py`

Tests of `exactus/packages/visual_cause`.


### `packages/visual_cause/support.py`

Typed assertion and reflection helpers shared by the test suite.

- `fail(*, message: str) -> NoReturn` — Fail the running test.
- `expect_true(*, condition: object, message: str='') -> None` — Require ``condition`` to be truthy.
- `expect_false(*, condition: object, message: str='') -> None` — Require ``condition`` to be falsy.
- `expect_equal(*, actual: object, expected: object, message: str='') -> None` — Require two values to compare equal.
- `expect_not_equal(*, actual: object, expected: object) -> None` — Require two values to compare unequal.
- `expect_in(*, member: object, container: Container[object]) -> None` — Require ``member`` to be contained in ``container``.
- `expect_not_in(*, member: object, container: Container[object]) -> None` — Require ``member`` to be absent from ``container``.
- `expect_none(*, value: object) -> None` — Require ``value`` to be ``None``.
- `require(*, value: T | None) -> T` — Require ``value`` to be present and return it narrowed.
- `require_type(*, value: object, kind: type[T]) -> T` — Require ``value`` to be an instance of ``kind`` and return it.
- `private(owner: object, member: str) -> object` — Read a non-public attribute of ``owner`` by name.
- `private_call(owner: object, member: str, **arguments: object) -> object` — Call a non-public callable of ``owner`` with keyword arguments.
- `set_private(owner: object, member: str, value: object) -> None` — Assign a non-public attribute of ``owner`` by name.
- `private_clear(owner: object, member: str) -> None` — Empty a non-public mapping or collection held by ``owner``.
- `private_as(owner: object, member: str, kind: type[T]) -> T` — Read a non-public attribute of ``owner`` as an instance of ``kind``.
- `class Constant` — Callable stand-in that ignores its arguments and returns one value.
  - `__init__(self, *, value: T) -> None` — Store the value every call returns.
- `private_result(owner: object, member: str, kind: type[T], **arguments: object) -> T` — Call a non-public callable of ``owner`` and type its result.
- `dig(*, document: object, path: tuple[str | int, ...]) -> object` — Walk a decoded JSON document along ``path``.
- `dig_list(*, document: object, path: tuple[str | int, ...]) -> list[object]` — Walk a decoded JSON document and require a list at ``path``.

### `packages/visual_cause/test_advanced.py`

Tests for advanced CSS causal analysis primitives.

- `test_nested_function_ast() -> None` — Nested expressions retain exact source spans.
- `test_quoted_function_content() -> None` — Parentheses and commas inside strings do not split arguments.
- `test_minimize_joint_only() -> None` — Joint-only effects are found without relying on single ablations.
- `test_budget_and_unsatisfied() -> None` — Search correctly refuses unsupported causes and respects budgets.
- `test_layout_evidence() -> None` — Resolved grid tracks and container type changes are retained.
- `test_parser_comments_escapes_and_unclosed_constructs() -> None` — Exercise comment, escape, operator, and unclosed-parser branches.
- `test_minimizer_empty_reduction_and_cache() -> None` — Exercise empty input, cache hits, and one-by-one minimal reduction.
- `test_lossless_tokenizer_nested_strings_and_flatten() -> None` — Exercise the lossless tokenizer's recursive branches.

### `packages/visual_cause/test_analyzer_helpers.py`

Focused behavioral coverage for analyzer helper logic.

- `test_rect_url_and_declaration_helpers() -> None` — Cover geometry, URL validation, declarations, and style groups.
- `test_structural_relationships_and_ranking(tmp_path: Path) -> None` — Cover ancestor, descendant, sibling, overlap, and ranking logic.
- `test_root_cause_paint_and_contributors() -> None` — Cover root-cause selection, paint order, and interaction companions.
- `test_human_summary_and_crops(tmp_path: Path) -> None` — Cover human-readable summaries and evidence crop generation.
- `test_change_forest_serializes_relations(tmp_path: Path) -> None` — Cover recursive changed-node serialization and causal annotations.
- `test_rule_and_element_payload_validation(tmp_path: Path) -> None` — Parse valid browser JSON and reject malformed browser payloads.
- `test_variable_chains_cycles_and_content_delta() -> None` — Resolve custom-property chains, cycles, and rendered-content deltas.
- `test_candidate_order_provenance_and_numeric_helpers(tmp_path: Path) -> None` — Cover changed-rule priority and single-declaration evidence.
- `test_budget_navigation_and_side_url(tmp_path: Path) -> None` — Cover bounded-budget expiration, navigation modes, and B URL selection.
- `test_pixel_regions_and_change_classification(tmp_path: Path) -> None` — Cover image-difference regions and propagated/computed classifications.
- `test_run_failure_path_and_provenance_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Persist diagnostics from ``run`` and cover provenance filtering.
- `test_serial_rule_trials_with_recyclable_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise bounded serial rule trials without launching Chromium.
- `test_missing_target_and_trial_budget_break(tmp_path: Path) -> None` — Cover missing CSS targets and pre-expired rule-trial budgets.
- `test_structural_image_analysis_and_rich_report(tmp_path: Path) -> None` — Cover structural image analysis and CSS-first Markdown evidence.
- `test_run_analysis_orchestration_and_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise the full orchestration path with deterministic stubs.
- `test_cascade_provenance_cdp_success_and_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise Chromium CDP cascade provenance and per-node recovery.
- `test_render_page_high_density_and_interventions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Capture device-scale evidence while keeping CSS-pixel analysis geometry.
- `test_interactions_minimal_sets_and_causal_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise multi-property and cross-element causal experiments.
- `test_render_context_wrapper_and_browser_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Cover render-context cleanup and system-Chromium fallback launch.
- `test_structural_empty_and_content_delta_branches(tmp_path: Path) -> None` — Cover empty structural summaries and rich content deltas.

### `packages/visual_cause/test_browser_js.py`

Validate every browser-side JavaScript source asset.

- `class Constants` — Group module-level constants.
  - `js_root` = `Path(__file__).parents[4] / 'exactus' / 'packages' / 'visual_cause' / 'js'`
  - `js_files` = `tuple(sorted(js_root.glob(pattern='*.js')))`
- `test_all_browser_js_assets_are_discovered() -> None` — Require every browser program asset to participate in tests.
- `test_browser_js_parses(path: Path) -> None` — Require every browser JavaScript file to parse successfully.

### `packages/visual_cause/test_cli_coverage.py`

Coverage for command entry points.

- `test_settings_parses_valid_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Parse all principal command-line scalar settings.
- `test_settings_rejects_invalid_dimensions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject invalid positive-dimension constraints.
- `test_module_entrypoint_calls_analyzer_main(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the visual-cause package entry-point semantics.
- `test_module_entrypoint_dispatches_dom_diff(monkeypatch: pytest.MonkeyPatch) -> None` — Execute the generic two-URL comparison command mode.

### `packages/visual_cause/test_css_targets.py`

Tests for CSS file/directory comparison targets.

- `test_file_target(tmp_path: Path) -> None` — Load a single CSS file as one target.
- `test_directory_target_is_recursive_and_deterministic(tmp_path: Path) -> None` — Combine recursive CSS files in relative lexical order.
- `test_directory_without_css_fails(tmp_path: Path) -> None` — Reject an empty CSS target directory.
- `test_non_css_file_fails(tmp_path: Path) -> None` — Reject a non-CSS file target.

### `packages/visual_cause/test_dom_diff.py`

Coverage for generic two-URL visual DOM comparison.

- `class FakeLocator` — Return a predetermined DOM payload for ``evaluate_all``.
  - `__init__(self, *, payload: str) -> None` — Store the serialized payload.
  - `evaluate_all(self, expression: str) -> str` — Return the serialized DOM snapshot.
- `class FakePage` — Implement the narrow page surface used by ``VisualDomDiff``.
  - `__init__(self, *, image: Image.Image, elements: list[dict[str, JsonValue]]) -> None` — Store screenshot and DOM fixture data.
  - `emulate_media(*, reduced_motion: str) -> None` — Validate the deterministic media setting.
  - `evaluate(*, expression: str) -> None` — Validate that video playback is paused for deterministic captures.
  - `goto(self, *, url: str, wait_until: str, timeout: int) -> None` — Record the navigation request.
  - `screenshot(self, *, path: Path, full_page: bool, animations: str, caret: str, scale: str) -> None` — Write the predetermined screenshot image.
  - `locator(self, *, selector: str) -> FakeLocator` — Return a locator for the predetermined DOM payload.
- `class FakeContext` — Return predetermined A/B pages and record closure.
  - `__init__(self, *, pages: tuple[FakePage, FakePage]) -> None` — Store the fake pages.
  - `new_page(self) -> FakePage` — Return the next fake page.
  - `close(self) -> None` — Record context cleanup.
- `class FakeBrowser` — Create one fake browser context and record closure.
  - `__init__(self, *, pages: tuple[FakePage, FakePage]) -> None` — Store the pages used by the context.
  - `new_context(self, *, viewport: dict[str, int], device_scale_factor: float, reduced_motion: str) -> FakeContext` — Validate context settings and return a fake context.
  - `close(self) -> None` — Record browser cleanup.
- `class FakeChromium` — Launch the predetermined fake browser.
  - `__init__(self, *, pages: tuple[FakePage, FakePage]) -> None` — Store browser fixture pages.
  - `launch(self, *, headless: bool) -> FakeBrowser` — Return the fake browser.
- `class FakePlaywright` — Expose a fake Chromium launcher.
  - `__init__(self, *, pages: tuple[FakePage, FakePage]) -> None` — Store browser fixture pages.
- `class FakePlaywrightManager` — Implement the synchronous Playwright context-manager boundary.
  - `__init__(self, *, pages: tuple[FakePage, FakePage]) -> None` — Store browser fixture pages.
- `test_dom_diff_helpers_normalize_threshold_and_merge_regions(tmp_path: Path) -> None` — Cover padding, thresholding, merge-gap, min-area, and pixel counts.
- `test_dom_diff_parses_and_ranks_elements() -> None` — Cover lightweight DOM payload validation and overlap ranking.
- `test_dom_diff_cli_settings_and_validation(tmp_path: Path) -> None` — Parse generic-diff options and reject invalid numeric ranges.
- `test_dom_diff_run_writes_original_report_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise the whole comparison through a fake Playwright boundary.
- `test_dom_diff_main_writes_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Cover the standalone CLI summary path without a browser.
- `test_dom_diff_settings_are_publicly_exported(tmp_path: Path) -> None` — Require package-level access to the migrated standalone API.

### `packages/visual_cause/test_dual_url_tokens.py`

Tests for dual URL and token CSS analysis.

- `test_dual_url(tmp_path: Path) -> None` — A and B may navigate to distinct URLs.
- `test_nested_tokens() -> None` — Nested CSS functions retain literal and function nodes.

### `packages/visual_cause/test_examples.py`

Coverage and behavior tests for bundled runnable examples.

- `class Constants` — Group module-level constants.
  - `run_modules` = `(run,)`
  - `validate_modules` = `(validate_results,)`
- `test_example_run_builds_demo_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, demo: ModuleType) -> None` — Run the example orchestration without launching a real browser.
- `test_validate_results_success_and_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, validator: ModuleType) -> None` — Validate complete evidence and reject missing reports.
- `test_validate_results_rejects_incomplete_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, validator: ModuleType) -> None` — Cover malformed-report validation branches.
- `test_validate_results_rejects_incomplete_evidence_triplet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, validator: ModuleType) -> None` — Reject a structurally complete report with incomplete image evidence.
- `test_validate_results_rejects_zero_missing_and_empty_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, validator: ModuleType) -> None` — Cover zero-evidence, missing-file, and empty-file validation.
- `test_example_run_reports_a_server_that_never_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Raise ``RuntimeError`` when the demo server does not come up.
- `test_example_run_module_executes_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Execute the ``examples/run.py`` file's ``__main__`` entry point.
- `test_examples_run_module_executes_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run ``examples/run.py`` via ``__main__`` with a stubbed pipeline.
- `test_examples_run_module_reuses_the_recorded_server(monkeypatch: pytest.MonkeyPatch) -> None` — An adopted demo server skips spawning and termination.

### `packages/visual_cause/test_full_pipeline.py`

End-to-end coverage for the bounded causal-analysis pipeline.

- `test_tiny_full_pipeline(tmp_path: Path) -> None` — Exercise deep causal phases on a deliberately tiny search space.

### `packages/visual_cause/test_runtime_lifecycle.py`

Regression tests for bounded runtime and report lifecycle.

- `test_failure_report_is_always_persisted(tmp_path: Path) -> None` — A failed run must leave human and machine-readable diagnostics.
- `test_zero_candidates_is_explicit_quick_mode(tmp_path: Path) -> None` — Zero candidates must remain valid for deterministic demo smoke runs.

### `packages/visual_cause/test_support.py`

Validate the shared visual_cause test helpers.

- `test_fail_and_expectation_failures() -> None` — Assertion helpers raise descriptive ``AssertionError`` values.
- `test_expectation_helpers_accept_good_values() -> None` — Assertion helpers pass on valid input.
- `test_require_helpers_narrow_and_reject() -> None` — ``require`` and ``require_type`` narrow values or fail.
- `test_private_helpers_read_write_and_call() -> None` — Private reflection helpers read, write, clear, and call members.
- `test_constant_and_dig_helpers() -> None` — ``Constant`` ignores arguments; ``dig`` walks nested documents.

### `packages/visual_cause/test_token_cascade.py`

Tests for exact CSS value nodes.

- `test_nested_value_nodes() -> None` — Run test nested value nodes.
- `test_exact_span_replacement() -> None` — Run test exact span replacement.

### `packages/visual_cause/test_typed_parallel.py`

Tests for Typed OM and parallel settings surfaces.

- `test_parallel_defaults(tmp_path: Path) -> None` — Settings expose bounded reusable-render worker defaults.

### `packages/watch/__init__.py`

Test the exactus/packages/watch folder watcher.


### `packages/watch/test_examples.py`

Exercise the programmatic watch example and its fixtures.

- `test_main_runs_the_bundled_dual_watchers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The no-argument demo copies the fixture into both destinations.
- `test_main_runs_a_single_explicit_watcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An explicit ``source destination`` pair runs one copy watcher.
- `test_main_rejects_a_lone_source_argument(monkeypatch: pytest.MonkeyPatch) -> None` — A source without a destination is a parser error.
- `test_bundled_watchers_cover_copy_and_mirror_modes() -> None` — The bundled pair mirrors the two documented deletion policies.
- `test_stopper_expires_at_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None` — ``_stopper`` fires once ``monotonic`` reaches the deadline.
- `test_fixture_scripts_print_their_marker(capsys: pytest.CaptureFixture[str]) -> None` — Each bundled ``watched.py`` prints the documented marker.

### `packages/watch/test_watch.py`

Exercise the project-local filesystem watcher and its CLI.

- `make_watcher(tmp_path: Path, *, mirror: bool=True, settle: float=0.0) -> core.FolderWatchCopy` — Build a watcher under ``tmp_path`` with fast polling.
- `snapshot_of(watcher: core.FolderWatchCopy) -> dict[Path, core.EntryState]` — Return the watcher's private source snapshot.
- `resolve_path(*, cli: Path | None, configured: object, project_root: Path | None) -> Path` — Invoke the CLI's private ``_resolve_path`` helper.
- `test_config_validation_and_helpers(tmp_path: Path) -> None` — Reject invalid configurations and compute snapshot helpers.
- `test_snapshot_sync_activity_changes_and_delete(tmp_path: Path) -> None` — Mirror creations, edits and deletions into the destination tree.
- `test_mirror_prune_removes_excluded_destination_entries(tmp_path: Path) -> None` — Excluded destination entries are pruned under mirror deletes.
- `test_inclusions_override_exclusions(tmp_path: Path) -> None` — Included paths stay watched and protected even when excluded.
- `test_pending_change_reset_and_no_delete_mirroring(tmp_path: Path) -> None` — Reset settled entries and keep deletions when mirroring is off.
- `test_destination_type_replacement_and_entry_size(tmp_path: Path) -> None` — Replace destination entries when their type changes.
- `test_pyproject_discovery_loading_and_errors(tmp_path: Path) -> None` — Discover pyproject.toml upward and validate [tool.watch] values.
- `test_settings_precedence_and_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Prefer CLI values over [tool.watch] and reject bad resolution.
- `test_autostart_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Cover LaunchAgent install, status, uninstall and failure paths.
- `test_uid_bootstrap_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Propagate uid lookup and launchctl bootstrap failures.
- `cli_values(**overrides: object) -> core.CliArguments` — Build ``CliArguments`` with every watch setting unset.
- `test_cli_management_paths(monkeypatch: pytest.MonkeyPatch) -> None` — Dispatch the ``--autostart-status`` management operation.
- `test_run_loop_and_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run one sync iteration and exercise verbose output paths.
- `test_autostart_legacy_install_and_success_uid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Install the LaunchAgent through the legacy CLI entry point.
- `test_copy_delete_error_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Keep copying and deleting when individual entries fail.
- `test_cli_all_dispatches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Dispatch install, uninstall and watch operations from the CLI.
- `test_supervisor_restarts_for_changed_watch_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Stop the current watcher and create another after TOML changes.
- `test_run_false_pauses_until_pyproject_enables_watcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Keep the supervisor alive while ``run`` is false, then start.
- `test_more_path_and_metrics_branches(tmp_path: Path) -> None` — Cover remaining path resolution and metrics branches.

### `packages/widgets/__init__.py`

Tests of ``exactus/packages/widgets``.


### `packages/widgets/widget_clock/__init__.py`

Tests for the analog clock package.


### `packages/widgets/widget_clock/test_examples.py`

Coverage for the widget_clock demo server launcher.

- `class Constants` — Group module-level constants.
  - `root` = `Path(run.__file__).resolve().parents[1]`
- `test_start_demo_serves_assets_and_reuses(tmp_path: Path) -> None` — Serve the demo and the library from one reusable loopback server.
- `test_start_demo_replaces_unready_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate and clear a spawned server that never answers.
- `test_main_prints_url_and_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None` — Print the demo URL and hand it to the system browser.
- `test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the analog-clock examples module forwards to ``serve.main``.

### `packages/widgets/widget_console/__init__.py`

Tests of ``exactus/packages/widgets/widget_console``.


### `packages/widgets/widget_console/test_examples.py`

Coverage for the console widget demo server launcher.

- `class Constants` — Group module-level constants.
  - `root` = `Path(run.__file__).resolve().parents[3]`
  - `assets` = `('widgets/widget_console/examples/web/index.html', 'widgets/widget_consol...`
- `test_demo_assets_exist() -> None` — Every file the demo page loads is present beside the launcher.
- `test_start_demo_reuses_a_recorded_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A recorded server short-circuits the spawn path.
- `test_start_demo_spawns_and_waits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A fresh spawn waits for readiness and returns the demo URL.
- `test_start_demo_replaces_unready_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Terminate and clear a spawned server that never answers.
- `test_main_prints_url_and_opens_browser(monkeypatch: pytest.MonkeyPatch) -> None` — Print the demo URL and hand it to the system browser.
- `test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None` — Verify the examples module forwards to ``run.main``.

### `packages/widgets/widget_selector/__init__.py`

Tests of ``exactus/packages/widgets/widget_selector``.


### `packages/widgets/widget_selector/test_examples.py`

Exercise the bundled widget_selector demo launcher with stubs.

- `test_start_demo_reuses_an_existing_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A recorded server short-circuits the spawn path entirely.
- `test_start_demo_spawns_and_waits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A fresh spawn waits for readiness and returns the demo URL.
- `test_start_demo_terminates_a_server_that_never_readies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A failed readiness check kills the spawned server and raises.
- `test_main_serves_then_opens_and_closes_the_browser(monkeypatch: pytest.MonkeyPatch) -> None` — ``main`` launches the demo, opens the session, and returns zero.

### `packages/zip_components/__init__.py`

Tests for the zip_components package.


### `packages/zip_components/test_zip_components.py`

Tests for source-bundle archives of exactus tools and packages packages.

- `test_bundle_name_joins_kinds_in_request_order() -> None` — Name archives after the requested components only.
- `test_discover_components_is_transitive(tmp_path: Path) -> None` — Follow component imports until no new component appears.
- `test_discover_components_skips_missing_directories(tmp_path: Path) -> None` — Ignore imports that do not resolve to component directories.
- `test_collect_files_adds_skeleton_skips_caches(tmp_path: Path) -> None` — Bundle skeleton paths and component trees without cache noise.
- `test_collect_files_includes_results_directories(tmp_path: Path) -> None` — Bundle existing report directories of selected exactus tools.
- `test_collect_files_ignores_missing_results(tmp_path: Path) -> None` — Skip report directories that do not exist.
- `test_create_bundle_writes_a_real_archive(tmp_path: Path) -> None` — Write archive members at repository-relative paths.
- `test_create_bundle_scaffolds_readme_and_tree(tmp_path: Path) -> None` — Default bundles nest under ``zip-components/<stem>/``.
- `test_lints_selection_discovers_pipeline_components() -> None` — Expand the real lints tool into its shared dependencies.
- `test_main_writes_the_scaffolded_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Place the archive inside ``zip-components/<stem>/`` with docs.
- `test_main_output_folder_overrides_the_default_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Place the bundle under ``--output-folder`` instead.
- `test_main_root_flag_bundles_from_the_given_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Bundle from ``--root`` instead of the auto-detected root.
- `test_available_components_lists_every_package(tmp_path: Path) -> None` — List canonical exactus tools plus every packages package.
- `test_main_list_outputs_every_component(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Print every available package as JSON without writing an archive.
- `test_main_list_resolves_a_named_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Print the discovered closure for the requested components.
- `test_main_prints_usage_without_components(monkeypatch: pytest.MonkeyPatch) -> None` — Exit ``1`` when neither kind of component is requested.
- `test_main_rejects_an_unknown_component() -> None` — Exit through the parser for a component that does not exist.
- `test_main_positional_names_are_packages_shorthand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Bundle ``zip_components alpha`` exactly like ``--packages alpha``.
- `test_main_wildcard_expands_to_every_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Expand ``*``/``all`` into every package of that kind.
- `test_main_bare_star_selects_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Treat a positional ``*`` as ``--packages * --tools *``.
- `test_bundle_name_renders_wildcards_as_all() -> None` — Name wildcard bundles ``packages_all.zip`` rather than ``*.zip``.
- `test_main_accepts_both_component_kinds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Bundle exactus tools and packages packages into one archive.
- `test_create_project_archive_replaces_the_bundle(tmp_path: Path) -> None` — Archive the tree with ``build`` bundle remapped to ``exactus/bundle``.
- `test_create_project_archive_requires_the_built_bundle(tmp_path: Path) -> None` — Fail with ``FileNotFoundError`` when the built bundle is missing.
- `test_main_project_writes_the_release_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Write ``exactus-release.zip`` at the project root by default.
- `test_main_project_rejects_component_selections() -> None` — Exit through the parser when ``--project`` mixes with selections.

### `packages/zstd_portable/__init__.py`

Tests of the portable Zstandard CLI wrapper.


### `packages/zstd_portable/test_directory_inventory.py`

Cover the shared directory-inventory helper and its bundle export.

- `class Constants` — Group module-level constants.
  - `canonical` = `Path(__file__).resolve().parents[4] / 'exactus' / 'tools' / 'common' / 'd...`
- `test_exported_package_ships_the_canonical_helper(tmp_path: Path) -> None` — ``export_package`` copies the shared helper into the leaf package.
- `test_description_extracts_script_docblock(tmp_path: Path) -> None` — Strip JSDoc-style block decorations and ``@`` tags from scripts.
- `test_heal_directory_skips_history_trees(tmp_path: Path) -> None` — Leave ``.history`` snapshot directories undocumented.
- `test_heal_directory_seeds_readme_from_first_candidate(tmp_path: Path) -> None` — Synthesize a heading plus the lead candidate summary without a README.
- `test_heal_directory_marks_empty_sections(tmp_path: Path) -> None` — Emit explicit placeholders when a directory holds no files or folders.
- `test_heal_directory_replaces_managed_block_only(tmp_path: Path) -> None` — Replace stale managed rows while preserving surrounding prose.
- `test_entry_line_links_directories_to_their_readme(tmp_path: Path) -> None` — Link subdirectory rows at ``name/README.md`` and quote odd names.

### `packages/zstd_portable/test_example.py`

The ``examples/example.py`` demo round-trips a scratch binary.

- `test_progress_renders_status_and_percent(monkeypatch: pytest.MonkeyPatch) -> None` — The progress sink writes the label and formatted percent.
- `test_create_binary_writes_configured_chunks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The source writer emits the exact size in chunk-sized writes.
- `test_example_round_trips_scratch_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The demo compresses and restores a matching payload.

### `packages/zstd_portable/test_zstd.py`

Tests of the portable Zstandard CLI wrapper.

- `class Constants` — Group module-level constants.
  - `complete` = `100.0`
  - `read_chunk` = `64`
  - `payload` = `b'exactus-offline-bundle\x00' * 4096 + bytes(range(256))`
  - `source_name` = `'exactus.packages.zstd_portable'`
- `wrapper_module(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise both distributed copies through identical public IO contracts.
- `test_platform_normalization(os_name: str, machine: str, expected: tuple[str, str]) -> None` — Normalize common architecture aliases in every distributed wrapper.
- `test_platform_normalization_rejects_unknown_values() -> None` — Reject unsupported CPUs and operating systems explicitly.
- `test_options_validation(tmp_path: Path) -> None` — Reject out-of-range modes and option values.
- `test_roundtrip_and_counters(tmp_path: Path) -> None` — Compress and decompress through real ``zstd`` end to end.
- `test_zero_expected_size(tmp_path: Path) -> None` — Report full progress when the expected size is zero.
- `test_open_guards(tmp_path: Path) -> None` — Reject double-open and open-after-close.
- `test_stream_method_guards(tmp_path: Path) -> None` — Reject stream calls that violate mode or lifecycle.
- `test_missing_compressed_input(tmp_path: Path) -> None` — Raise ``FileNotFoundError`` for absent compressed input.
- `test_partial_read_close(tmp_path: Path) -> None` — Terminate the decompressor on early caller-driven close.
- `test_expected_size_mismatch(tmp_path: Path) -> None` — Fail close when written bytes differ from ``expected_size``.
- `test_corrupt_stream_fails(tmp_path: Path) -> None` — Fail close when the decompressor exits nonzero.
- `test_context_exit_failures(tmp_path: Path) -> None` — Propagate close failures and preserve active exceptions.
- `test_executable_cache(tmp_path: Path) -> None` — Extract the native binary once and reuse the digest cache.
- `test_unsupported_platforms(monkeypatch: pytest.MonkeyPatch) -> None` — Reject unknown CPU, OS, and target combinations.
- `test_invalid_payload_contents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject malformed or overfilled native payload archives.
- `test_feed_and_stderr_without_process(tmp_path: Path) -> None` — Return early when feed and drain helpers lack a process.
- `test_stderr_details_in_failure(tmp_path: Path) -> None` — Surface child stderr inside the close failure message.
- `test_large_corrupt_input_feeds_until_pipe_breaks(tmp_path: Path) -> None` — Report input-streaming failure on a dead decompressor.
- `test_export_binary(tmp_path: Path) -> None` — Stage a native CLI binary for an explicit target platform.
- `test_export_binary_rejects_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject platforms without a normalized payload entry.
- `test_exported_package_readmes(tmp_path: Path, os_name: str, machine: str) -> None` — Document the exported wrapper and its selected native payload.

### `standalone/__init__.py`

Standalone end-to-end fixture tests.


### `standalone/project/__init__.py`

Standalone fixture project root marker.


### `standalone/project/conftest.py`

Make the fixture project's ``python`` package importable in tests.


### `standalone/project/python/__init__.py`

Toy package exercised by the standalone fixture.


### `standalone/project/python/calc.py`

Minimal arithmetic for the standalone fixture project.

- `add(*, left: int, right: int) -> int` — Add two integers.
- `is_even(*, value: int) -> bool` — Report whether an integer is even.

### `standalone/project/tests/__init__.py`

Tests for the standalone fixture project.


### `standalone/project/tests/test_calc.py`

Tests for the fixture project's ``python.calc`` module.

- `class Constants` — Group module-level constants.
  - `sum_expected` = `5`
- `test_add_sums_operands() -> None` — ``add`` returns the sum of its operands.
- `test_is_even_flags_parity() -> None` — ``is_even`` reports even and odd values.

### `standalone/test_standalone.py`

Run the system ``exactus`` executable over the standalone project.

- `class Constants` — Group module-level constants.
  - `run_timeout_seconds` = `1800`
  - `stripped_prefixes` = `('EXACTUS_', 'COVERAGE_', 'PYTEST_', 'PYTHONPATH')`
  - `repository_root` = `Path(__file__).resolve().parents[3]`
  - `project_root` = `Path(__file__).resolve().parent / 'project'`
- `test_system_exactus_audits_standalone_project() -> None` — ``exactus`` produces ``EXACTUS_RESULTS`` inside the project.

### `tools/__init__.py`

Tests mirroring the exactus tools suite.


### `tools/actions/__init__.py`

Test declarative Actions orchestration.


### `tools/actions/test_actions.py`

Verify declarative tool orchestration through real discovery and replay.

- `test_actions_entrypoint_defaults_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Resolve default paths and map aggregate status to a process code.
- `test_evaluations_follow_captured_timestamps(timestamps: tuple[int, ...]) -> None` — Keep script order after slow or out-of-order discovered captures.
- `test_rejects_unknown_tools_and_forward_references() -> None` — Validate recipes before any process or tool starts.
- `test_toml_named_output_reference(tmp_path: Path) -> None` — Read the same tool recipe from TOML without shell expansion.
- `test_demo_discovery_replay_and_report(tmp_path: Path) -> None` — Launch once and replay discovered projects in two themes.
- `test_setup_failure_retains_report_and_stops_server(tmp_path: Path) -> None` — Preserve a failed tool result and clean up its owned process.
- `test_invalid_later_call_never_starts_server(tmp_path: Path, arguments: dict[str, JsonValue]) -> None` — Reject the whole recipe before executing an earlier valid call.
- `test_frontend_findings_can_be_report_only(tmp_path: Path) -> None` — Keep intentional frontend findings while allowing Actions to succeed.

### `tools/actions/test_examples.py`

Run the public actions example against its bundled recipe.

- `test_actions_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The bundled recipe discovers and verifies its owned example server.

### `tools/common/__init__.py`

Tests of `exactus/tools/common` leaf primitives and shared templates.


### `tools/common/process_layer/__init__.py`

Test authenticated process-layer access and lifecycle helpers.


### `tools/common/process_layer/test_access.py`

Shared-secret provisioning and responder lifecycle.

- `test_runtime_dir_prefers_reports_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — ``EXACTUS_REPORTS_ROOT`` wins over every other base directory.
- `test_runtime_dir_uses_output_parent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Without the env override the output parent hosts ``.runtime``.
- `test_runtime_dir_defaults_to_cwd_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — No env and no output resolve under the working directory.
- `test_authkey_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A sufficiently long ``EXACTUS_AUTHKEY`` returns as bytes.
- `test_authkey_env_override_rejects_short_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Short ``EXACTUS_AUTHKEY`` values raise ``ValueError``.
- `test_authkey_generates_and_reuses_file(tmp_path: Path) -> None` — The file secret is generated once then reused byte-for-byte.
- `test_authkey_regenerates_short_files(tmp_path: Path) -> None` — A truncated on-disk secret is replaced with a full key.
- `test_start_responder_starts_or_degrades(tmp_path: Path) -> None` — Startup either yields a responder or degrades to ``None``.
- `test_stop_responder_accepts_none() -> None` — Stopping a missing responder is a silent no-op.
- `test_authkey_honours_access_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — The module re-export keeps ``access.authkey`` in sync.

### `tools/common/process_layer/test_control.py`

Authenticated loopback identity discovery behavior.

- `class Constants` — Group module-level constants.
  - `authkey` = `b'k' * 32`
  - `wrong_key` = `b'w' * 32`
- `test_responder_rejects_invalid_configuration(tmp_path: Path) -> None` — Empty runs, short secrets, and bad timeouts are rejected.
- `test_identify_verifies_live_responder(tmp_path: Path) -> None` — A running responder answers an authenticated handshake.
- `test_identify_rejects_wrong_authkey(tmp_path: Path) -> None` — A mismatched secret never yields an identity.
- `test_identify_rejects_bad_inputs() -> None` — Nonpositive pids and bad arguments produce no identity.
- `test_responder_start_close_lifecycle(tmp_path: Path) -> None` — A responder starts once and closes idempotently.
- `test_discover_finds_responder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Discovery interrogates candidate ports and returns identities.
- `test_discover_validates_workers() -> None` — Discovery rejects out-of-range worker counts.
- `test_receive_reads_exact_bytes() -> None` — ``_receive`` accumulates fragments into an exact payload.
- `test_receive_none_on_early_close() -> None` — ``_receive`` reports truncated streams as ``None``.
- `test_listen_table_reports_own_responder_port(tmp_path: Path) -> None` — ``_listen_table`` lists this process's private loopback listener.
- `test_exactus_candidates_filters_by_process_identity() -> None` — ``_exactus_candidates`` keeps interpreters and drops dead pids.

### `tools/common/process_layer/test_termination.py`

Verified-tree process termination behavior.

- `class Constants` — Group module-level constants.
  - `tree_min` = `2`
  - `stale_pid` = `999999`
  - `schema` = `'CREATE TABLE runs (status TEXT, run_id TEXT, pipeline_run_id TEXT, pid I...`
- `test_terminator_rejects_nonfinite_timeouts() -> None` — Nonfinite grace periods are rejected at construction.
- `test_result_properties() -> None` — Result counters expose aggregate termination outcomes.
- `test_terminate_refuses_self() -> None` — The terminator never targets its own process.
- `test_terminate_absent_root_marks_exited(tmp_path: Path) -> None` — A dead root is reported as already exited, never signalled.
- `test_terminate_kills_verified_tree(tmp_path: Path) -> None` — A live verified process tree is terminated end to end.
- `test_database_pids_outside_tree_are_skipped(tmp_path: Path) -> None` — Database-listed PIDs outside the tree land in ``skipped``.
- `test_missing_database_yields_empty_pid_set(tmp_path: Path) -> None` — A nonexistent runtime database contributes no PIDs.

### `tools/common/test_activity.py`

The fixed ``@activity.json`` schema, its bounded log and atomic file.

- `class Constants` — Group module-level constants.
  - `top_keys` = `frozenset({'schema', 'kind', 'name', 'run_id', 'pipeline_run_id', 'status...`
- `test_payload_has_the_fixed_key_set() -> None` — Every document carries the same top-level and block keys.
- `test_document_round_trips_through_json() -> None` — ``from_payload(payload())`` restores an equal document.
- `test_progress_fraction_is_clamped() -> None` — Out-of-range fractions serialize inside ``[0, 1]``.
- `test_log_keeps_only_the_newest_events() -> None` — The log evicts the oldest events and counts them as dropped.
- `test_log_records_from_a_signal_handler_holding_the_lock() -> None` — A signal handler can record while the main thread holds the lock.
- `test_document_bounds_the_written_events() -> None` — Events beyond the limit are cut from the payload and counted.
- `test_foreign_payloads_are_rejected(payload: JsonValue) -> None` — Other schemas and incomplete documents decode to ``None``.
- `test_malformed_blocks_fall_back_to_defaults() -> None` — Bad block values decode to defaults; bad events are skipped.
- `test_file_write_is_atomic_and_leaves_no_temporaries(tmp_path: Path) -> None` — Writes replace the file whole and clean their temporary files.
- `test_failed_replace_keeps_the_previous_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A write that cannot be published leaves the old document intact.
- `test_concurrent_readers_never_see_partial_documents(tmp_path: Path) -> None` — A reader polling during many writes always decodes a document.
- `test_worker_progress_survives_activity_file_roundtrip(tmp_path: Path) -> None` — Retain live worker steps and actions in the on-disk heartbeat.

### `tools/common/test_analyzers.py`

In-process runs of every static analyzer over the toolkit and a sample.

- `class Constants` — Group module-level constants.
  - `analyzers` = `('kwargs_typehints', 'docs', 'readme')`
- `test_self_exactus_writes_reports(name: str, repo_args: tuple[str, ...], tmp_path: Path) -> None` — Each analyzer completes against the toolkit and emits a report.
- `test_sample_project_exactus(name: str, sample_project: Path, tmp_path: Path) -> None` — Each analyzer handles a small defective project.
- `corpus(tmp_path: Path) -> Path` — Copy two real third-party packages to exactus as a large corpus.
- `test_real_world_corpus(name: str, corpus: Path, tmp_path: Path) -> None` — Large third-party codebases are analyzed without crashing.

### `tools/common/test_catalog.py`

Catalog validation, alias resolution, and pipeline wave planning.

- `class Constants` — Group module-level constants.
  - `min_tools` = `7`
  - `min_pipelines` = `3`
  - `root` = `Path(__file__).resolve().parents[4]`
- `test_duplicate_identifiers_rejected() -> None` — Tool or pipeline ids must be unique.
- `test_alias_collisions_rejected() -> None` — Aliases may not shadow ids or each other.
- `test_unknown_references_rejected() -> None` — Dependencies, members and baked arguments must exist.
- `test_pipeline_cycle_rejected() -> None` — Self-referential pipelines are detected.
- `test_nested_pipelines_and_waves() -> None` — Nested pipelines flatten and waves run last stage first.
- `test_lookup_helpers() -> None` — Normalization, aliases and typed lookups.
- `test_coverage_tests_aliases(identifier: str) -> None` — The former ``coverage`` and ``tests`` ids resolve to one tool.
- `test_resolve_deduplicates() -> None` — Selecting overlapping tools and pipelines runs each once.
- `test_resolve_pipeline_unknown_member() -> None` — Resolving an unknown pipeline raises before wave planning.
- `test_packaged_tool_layout(identifier: str) -> None` — Every tool lives in ``exactus/tools/<id>/`` with a main and a core.
- `test_unified_pipeline_audits_readmes_after_every_other_tool() -> None` — Readme inventories run after analyzers; performance profiles last.
- `test_identifier_lookup_accepts_dash_spellings() -> None` — ``tool``/``pipeline``/``canonical`` fold ``-``/``_`` variants.

### `tools/common/test_collect_files.py`

The ``FILES`` bundle written beside reports when collecting files.

- `test_requested_flag_or_environment(monkeypatch: pytest.MonkeyPatch) -> None` — Collection is requested by the flag token or the env variable.
- `test_mark_exports_collection(monkeypatch: pytest.MonkeyPatch) -> None` — ``mark`` exports the variable only when the flag is present.
- `test_collect_report_files_bundles_findings(tmp_path: Path) -> None` — The bundle zips every finding file keeping its folder structure.
- `test_collect_report_files_reads_snapshots(tmp_path: Path) -> None` — Pipeline aggregate findings inside ``report_snapshots`` count.
- `test_collect_report_files_lists_missing(tmp_path: Path) -> None` — Reported files absent on disk are named in the README.
- `test_collect_report_files_without_report(tmp_path: Path) -> None` — A missing ``result.json`` skips the bundle entirely.
- `test_common_parser_accepts_collect_files() -> None` — The shared tool parser exposes ``--collect-files``.
- `test_requested_and_mark_accept_underscore_flag(monkeypatch: pytest.MonkeyPatch) -> None` — ``--collect_files`` enables collection like ``--collect-files``.

### `tools/common/test_common.py`

Shared helpers: output resolution, filtering, and bundle discovery.

- `class Constants` — Group module-level constants.
  - `launcher_body` = `'# Partitioned filesystem tool launcher\n'`
- `test_map_lanes_and_misc() -> None` — Lanes keep order and helpers pass values through.
- `test_parse_common_arguments() -> None` — The shared parser exposes root, output, include and exclude.
- `test_resolve_report_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The pipeline override wins over CLI and default paths.
- `test_resolve_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Relative outputs resolve against cwd or the project root.
- `test_match_path(tmp_path: Path) -> None` — Include, exclude and default exclusions combine.
- `test_is_reports_tree(tmp_path: Path) -> None` — Report trees fingerprint by content, whatever their name.
- `test_expand_paths(tmp_path: Path) -> None` — Literal and glob patterns expand to existing resolved paths.
- `test_executable_candidate(tmp_path: Path) -> None` — Non-executable files are repaired; directories are rejected.
- `test_platform_support(monkeypatch: pytest.MonkeyPatch) -> None` — Only Linux on amd64-class machines is supported.
- `test_toolchain_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Explicit option, environment and discovered toolchains resolve.
- `test_linter_command_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Toolchain, installed tool, bundle, then bare name.
- `test_bundle_resolution_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A launcher is found, executed, and exposed on the path.
- `test_bundle_cache_failures(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Invalid partitioned bundles never activate Python paths.
- `test_activate_requires_python_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A cache lacking ``python/`` is not activated.
- `test_activate_exposes_chromium_browsers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Browser activation exposes bundled Chromium paths to child processes.
- `test_embedded_bundle_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A partitioned bundle directory is found as real files.
- `test_materialize_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Nested pack and bootstrap ZIP resources copy into an atomic cache.
- `test_resolve_bundle_via_embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The embedded bundle is the last discovery fallback.
- `test_embedded_bundle_dir_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Missing or unreachable embedded bundles resolve to ``None``.
- `test_host_bundle_dirs(*, host: str, arch: str, musl: bool, expected: tuple[Path, ...], monkeypatch: pytest.MonkeyPatch) -> None` — Host OS/architecture/libc map to ordered bundle directories.

### `tools/common/test_common_package.py`

The common package is a leaf: it imports nothing else from the repo.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `common` = `root / 'exactus' / 'tools' / 'common'`
  - `allowed` = `('exactus.tools.common.process_layer', 'exactus.tools.common', 'exactus.p...`
- `test_common_modules_exist() -> None` — The three primitives live under exactus/tools/common.
- `test_common_imports_only_itself() -> None` — Common may import only itself plus its approved package helpers.
- `test_common_init_has_no_imports() -> None` — The package initializer holds only a docstring and the future import.

### `tools/common/test_config.py`

Discovery, parsing, merging and rendering of ``[tool.exactus]`` settings.

- `class Constants` — Group module-level constants.
  - `tool_toml` = `dedent(text='    \n    [tool.exactus]\n    include = ["a/**"]\n    [tool....`
- `test_discover_walks_upward_nearest_first(tmp_path: Path) -> None` — Every ancestor with ``[tool.exactus]`` is loaded, nearest first.
- `test_discover_stops_at_root_marker(tmp_path: Path) -> None` — ``root = true`` ends the upward walk after that file.
- `test_discover_skips_files_without_exactus_table(tmp_path: Path) -> None` — A ``pyproject.toml`` lacking ``[tool.exactus]`` is ignored.
- `test_explicit_and_disabled(tmp_path: Path) -> None` — ``--config`` loads one file; ``--no-config`` loads none.
- `test_invalid_toml_names_the_file(tmp_path: Path) -> None` — A parse failure raises ``ConfigError`` naming the file.
- `test_environment_variable_controls_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``EXACTUS_CONFIG`` is either ``off`` or an explicit path.
- `test_discover_boundary_contains_the_walk(tmp_path: Path) -> None` — A boundary stops the walk reaching enclosing configuration.
- `test_discover_boundary_relocates_outside_start(tmp_path: Path) -> None` — A start outside the boundary is moved inside it.
- `test_exactus_root_bounds_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``EXACTUS_ROOT`` keeps nested runs off the enclosing project.
- `test_render_kinds(tmp_path: Path) -> None` — Scalars, flags, repeats and zero are rendered exactly.
- `test_pipeline_table_overrides_tool_table(tmp_path: Path) -> None` — The pipeline-scoped table comes last so it wins.
- `test_negative_values_survive(tmp_path: Path) -> None` — Values starting with a dash are not read as flags.
- `test_common_keys_standalone_only(tmp_path: Path) -> None` — Common orchestrator keys apply to standalone runs only.
- `test_unknown_key_and_wrong_type(tmp_path: Path) -> None` — Typos and bad values raise ``ConfigError`` naming file and key.
- `test_common_key_unknown_to_a_tool_is_skipped(tmp_path: Path) -> None` — A common key the tool lacks is skipped rather than rejected.
- `test_nested_files_merge(tmp_path: Path) -> None` — Nearest scalars win; lists combine farthest first.
- `test_validate_rejects_unknown_table_and_common_key(tmp_path: Path) -> None` — Unknown tables and unclaimed common keys fail validation.
- `test_validate_accepts_package_owned_mcp_configuration(tmp_path: Path) -> None` — The MCP package owns its service and nested watcher schemas.
- `test_orchestrator_injection_rules(tmp_path: Path) -> None` — Config entrypoint/clear are injected only for pipeline-style runs.
- `test_effective_reports_the_winning_layer(tmp_path: Path) -> None` — Each option names the layer that set its final value.
- `test_canonical_section_precedence(tmp_path: Path) -> None` — Tool, pipeline and CLI gates override common defaults in order.
- `test_canonical_tool_list_extends_common_list(tmp_path: Path) -> None` — Repeated tool options extend the common options in order.
- `test_validate_rejects_legacy_sections(tmp_path: Path) -> None` — Removed legacy table names produce an explicit configuration error.
- `test_reports_directory_setting(tmp_path: Path, directory: str) -> None` — Read the project-relative reports base without forwarding a flag.
- `test_reports_directory_rejects_project_escape(tmp_path: Path, directory: str) -> None` — Prevent report cleanup from targeting the project or its parent.
- `test_standalone_reports_directory_and_cli_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Apply the reports base while preserving explicit output choices.
- `test_path_keys_resolve_against_declaring_file(tmp_path: Path) -> None` — ``actions``/``workspace`` resolve beside the file that set them.

### `tools/common/test_config_integration.py`

``pyproject.toml`` settings reaching standalone tools and ``check``.

- `class Constants` — Group module-level constants.
  - `gate` = `'[tool.exactus.coverage_tests]\nfail-under = 77\n'`
  - `zero_gate` = `'[tool.exactus.coverage_tests]\nfail-under = 0\nminimum = 0\n'`
- `test_standalone_tool_reads_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A standalone tool picks up its table; the CLI still wins.
- `test_context_lines_from_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Read ``context-lines`` from the canonical coverage configuration.
- `test_orchestrated_tool_skips_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Under ``check`` the tool does not apply config a second time.
- `test_standalone_config_error_exits_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None` — A bad key stops the tool with status 2 and names the key.
- `test_check_single_tool_uses_pyproject_gate(sample_project: Path) -> None` — ``check --coverage`` (alias) honors the legacy ``fail-under``.
- `test_check_reports_config_errors(sample_project: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An invalid key stops ``check`` with status 2 before any tool runs.
- `test_no_config_and_explicit_config(sample_project: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--no-config`` restores the built-in gate; ``--config`` selects a file.
- `test_orchestrator_settings_apply_to_pipeline_style_runs(sample_project: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Config ``clear`` runs for ``-t``; info flags and bad servers do not.
- `test_show_config_exits_cleanly(sample_project: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--show-config`` reports and exits ``0`` without running tools.

### `tools/common/test_conflict_copies.py`

Verify automatic sync cleanup preserves unique and conflicting data.

- `test_sync_merges_unique_entries_and_preserves_conflicts(tmp_path: Path) -> None` — Keep canonical bytes, merge unique data and retain conflicting copies.
- `test_sync_ignores_unmatched_hidden_and_symlink_directories(tmp_path: Path) -> None` — Avoid traversing external links and retain unmatched numbered folders.
- `test_sync_merges_numbered_hidden_directories(tmp_path: Path) -> None` — Reconcile ``.name N`` copies without traversing other hidden trees.
- `test_sync_compares_links_and_retries_busy_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Remove identical links and retry unavailable directories later.
- `subsystem_contract(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise the shared behavior in every shipped subsystem copy.
- `test_history_backups_are_never_reconciled(tmp_path: Path) -> None` — Backup folders and numbered backup copies are left untouched.

### `tools/common/test_context_lines.py`

The shared ``--context-lines`` option and its configuration layers.

- `class Constants` — Group module-level constants.
  - `parsers` = `(lints_args, readme_args, docs_args, coverage_args)`
- `project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path` — Run a standalone tool from an empty project directory.
- `test_default_is_three_for_every_tool() -> None` — Without configuration every tool captures three context lines.
- `test_common_table_sets_every_tool(project: Path) -> None` — ``[tool.exactus] context-lines`` reaches every tool.
- `test_tool_table_overrides_common_and_cli_wins(project: Path) -> None` — ``[tool.exactus.<tool>]`` beats ``[tool.exactus]``; the CLI beats both.
- `test_pipeline_table_sits_between_tool_table_and_cli(project: Path) -> None` — The pipeline-scoped tool table overrides the tool table.
- `test_negative_values_are_rejected(project: Path, capsys: pytest.CaptureFixture[str]) -> None` — A negative count stops the tool with status 2 from CLI or config.
- `test_context_lines_type() -> None` — The option type accepts non-negative integers only.

### `tools/common/test_digest.py`

Tool reports are digested into failure summaries for aggregates.

- `class Constants` — Group module-level constants.
  - `root` = `'/work/project'`
- `test_digest_counts_rules_files_and_extras() -> None` — Rules, hot files, extras, tests, and gates are all summarized.
- `test_normalized_findings_skip_the_legacy_lists() -> None` — Normalized findings hold the tool lists; none is counted twice.
- `test_render_failure_lists_tables_and_escapes_pipes() -> None` — The failure section shows rules, files, findings, and failed tests.
- `test_empty_report_yields_an_empty_digest() -> None` — A report without findings still renders and serializes.
- `test_distinct_groups_ignore_origin_and_port() -> None` — Findings differing only by origin collapse into one counted group.

### `tools/common/test_directory_inventory.py`

Verify semantic, bottom-up README inventories and idempotent repairs.

- `test_bottom_up_docstrings_child_summaries_and_updates(tmp_path: Path) -> None` — Propagate child summaries and preserve prose in refreshed rows.
- `test_repair_removes_obsolete_and_duplicate_generated_blocks(*, tmp_path: Path, legacy_first: bool) -> None` — Replace stale generated references without changing authored content.

### `tools/common/test_envelope.py`

The runner-owned envelope blocks of a normalized report.

- `test_variables_are_allowlisted_and_redacted() -> None` — Only exact allowlisted names appear, their values redacted.
- `test_unlisted_variables_never_leak(*, name: str, value: str) -> None` — Variables outside the allowlist are not reported at all.
- `test_redaction_text(*, value: str, expected: str | None) -> None` — URL userinfo and keyed secrets hide; ordinary text stays.
- `test_redaction_arguments() -> None` — A bare secret flag hides the argument that follows it.
- `test_invocation_is_redacted(tmp_path: Path) -> None` — The invocation block never shows credentials.
- `test_environment_facts(monkeypatch: pytest.MonkeyPatch) -> None` — The environment block names OS, Python, Node and CPUs.
- `test_node_version_reads_the_installed_node(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — A Node on PATH reports its version; a failing one reports none.
- `test_duration_human() -> None` — Durations read in seconds, then minutes and seconds.
- `test_gate(*, tmp_path: Path, status: str, error: str | None, findings: list[JsonValue] | None, expected: tuple[str, str]) -> None` — The gate follows status, blocking findings and crash text.
- `test_artifacts_list_visible_files(tmp_path: Path) -> None` — Artifacts list files under ARTIFACTS/ without hidden entries.
- `test_build_returns_every_envelope_block(tmp_path: Path) -> None` — The envelope carries six blocks and prefers the payload title.
- `test_tool_version_without_distribution(monkeypatch: pytest.MonkeyPatch) -> None` — A missing distribution leaves the version unknown.

### `tools/common/test_examples_run.py`

Cover the bundled ``common`` examples entry points.

- `class Constants` — Group module-level constants.
  - `repo` = `Path(__file__).resolve().parents[4]`
  - `markdown_example` = `repo / 'exactus' / 'tools' / 'common' / 'templates' / 'markdown' / 'examp...`
- `test_markdown_template_example_validates_fixtures() -> None` — The markdown example parses every bundled fixture pair.
- `test_prepare_project_builds_an_intentionally_imperfect_fixture() -> None` — ``prepare_project`` writes source files and an inventory.
- `test_prepare_project_rejects_an_empty_fixture() -> None` — ``prepare_project`` refuses a zero-file fixture.
- `test_invocations_plan_overlapping_collisions(tmp_path: Path) -> None` — ``invocations`` returns four staggered launches.
- `test_main_prepare_only_prints_commands(monkeypatch: pytest.MonkeyPatch) -> None` — ``--prepare-only`` prints the commands without launching them.
- `test_run_demo_monitors_stubbed_processes_until_settled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``run_demo`` launches, polls, and scores every stubbed invocation.
- `test_transcript_failed_detects_coordinator_markers(tmp_path: Path) -> None` — ``transcript_failed`` spots infrastructure failures in logs.
- `test_registry_snapshot_handles_missing_and_live_databases(tmp_path: Path) -> None` — ``registry_snapshot`` degrades without a database and lists rows.

### `tools/common/test_execution.py`

The shared exactus execution wrapper, fallbacks, and crash recording.

- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `class Constants` — Group module-level constants.
  - `progress_json` = `'{"progress": 5, "completed": 2, "total": 3, "step": "s", "detail": "d"}'`
- `test_exited_dependent_is_reset_without_checkpoint_wait(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An exited streaming worker cannot stall a prerequisite forever.
- `test_success_without_report_gets_fallback(tmp_path: Path) -> None` — A silent successful analyzer still produces a report bundle.
- `class FdStream` — Stream wrapper exposing a real process descriptor.
  - `__init__(self, descriptor: int) -> None` — Remember the descriptor.
  - `fileno(self) -> int` — Return the descriptor.
  - `flush(self) -> None` — Accept flushes.
- `test_output_streams_are_captured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Stdout and stderr tails land in the fallback transcript logs.
- `test_exceptions_become_failed_reports(raiser: Callable[[], int], status: int, needle: str, tmp_path: Path) -> None` — Every kind of analyzer failure is reported rather than lost.
- `test_analyzer_written_reports_are_kept(tmp_path: Path) -> None` — Reports written by the analyzer are stamped, not replaced.
- `test_web_data_payload_is_stamped(tmp_path: Path) -> None` — Analyzer-provided ``result_web/data.json`` gains run status fields.
- `test_failed_analyzer_stamps_existing_reports(tmp_path: Path) -> None` — A failing run overwrites status in analyzer-provided reports.
- `test_terminal_summary_and_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Without orchestration the wrapper prints its own summary.
- `test_run_exactus_returns_exit_code(tmp_path: Path) -> None` — ``run_exactus`` reports the analyzer exit status.
- `test_report_output_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--report-output`` is consumed from argv.
- `test_prepare_output_cleans_and_preserves(tmp_path: Path) -> None` — Old output is emptied; read-only trees are forced writable.
- `test_prepare_output_moves_aside_when_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An undeletable child forces the directory aside with a preserved name.
- `test_progress_helpers() -> None` — Progress payloads are normalized defensively.
- `test_report_snapshot_and_emitted(tmp_path: Path) -> None` — Only new or rewritten md and json pairs count as emitted.
- `test_terminate_live_run_ignores_missing_or_finished(tmp_path: Path) -> None` — Only RUNNING activity documents with integer pids are acted upon.
- `test_conflicting_run_is_terminated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Live runs conflicting on the output directory are terminated.
- `test_registry_unavailable_falls_back_to_activity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without a registry ``@activity.json`` names the process to stop.
- `test_fallback_markdown_truncates_and_lists(tmp_path: Path) -> None` — Fallback reports include errors, tails and artifacts.
- `test_stream_capture_failure_is_tolerated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Streams without descriptors are simply not captured.
- `test_crashed_exactus_records_failure(tmp_path: Path) -> None` — A dead worker still yields a report and failed result.
- `test_crashed_exactus_respects_reclaimed_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — When a newer run owns the directory nothing is rewritten.
- `test_output_reclaimed_detection(tmp_path: Path) -> None` — Activity documents of other runs mark the directory as reclaimed.
- `test_signal_during_run_records_interrupt(tmp_path: Path) -> None` — SIGTERM mid-run leaves an INTERRUPT activity and kills the run.
- `test_previous_duration_propagates_to_reports_and_activity(tmp_path: Path) -> None` — A second run records the first run's duration everywhere visible.
- `test_help_preserves_existing_exactus_evidence(tmp_path: Path) -> None` — Keep saved failures intact when a tool only displays CLI help.

### `tools/common/test_models_api.py`

Result models, progress documents, the process API, and runtime.

- `test_from_report_reads_fields_and_falls_back(tmp_path: Path) -> None` — Report payloads override the fallback only with valid types.
- `test_reconcile_variants(tmp_path: Path) -> None` — Reports from other runs mark the result as replaced.
- `test_result_stats_summarizes_files_and_severities(tmp_path: Path) -> None` — The resume stats join affected/total files and severity counts.
- `test_activity_payloads() -> None` — Activities serialize to the uniform run-document schema.
- `progress_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]` — Reset the process-local progress channel around a test.
- `test_progress_is_current_and_spanned(progress_state: None) -> None` — Published fractions reflect current work and honor spans.
- `test_progress_without_run_identity() -> None` — Standalone progress remains available in process memory.
- `test_lane_progress_counts() -> None` — Lanes share one monotonically increasing counter.
- `test_provisional_release_opens_dependent_file_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A lints release lets kwargs read a file before lints terminates.
- `worker_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]` — Isolate process-wide state mutated by the worker entry.
- `main(*, arguments: tuple[str, ...]) -> int` — Exercise a file-style thread pool inside a detached worker process.
- `test_worker_runs_tool_and_writes_result(pipeline_id: str | None, worker_env: Path) -> None` — The pmanager worker executes a tool and writes its report.
- `test_run_tool_spawns_isolated_worker(worker_env: Path) -> None` — A real worker process produces and returns a result.
- `test_detached_worker_owns_its_file_threads(worker_env: Path) -> None` — File-level threads execute inside their independent tool process.
- `test_run_tool_reports_crashed_worker(worker_env: Path) -> None` — A worker that dies before reporting yields a failed result.

### `tools/common/test_output_tree.py`

Every tool run leaves ``@activity.json``, ``stderr.log``/``stdout.log``.

- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `class FdStream` — Stream stand-in exposing a real process descriptor.
  - `__init__(self, *, descriptor: int) -> None` — Remember the descriptor.
  - `fileno(self) -> int` — Return the descriptor.
  - `flush(self) -> None` — Accept flushes.
- `class NoFdStream` — Stream stand-in without a descriptor, like an in-memory stream.
  - `fileno() -> NoReturn` — Fail like an in-memory stream.
  - `flush(self) -> None` — Accept flushes.
- `test_tool_run_writes_the_three_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A run publishes the activity and the raw stderr/stdout transcripts.
- `test_uncaptured_streams_still_get_stderr_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without descriptors the run writes an empty, uncaptured stderr.
- `test_crash_finalizes_activity_and_stderr(tmp_path: Path) -> None` — A dead worker's activity keeps its events and ends ``crashed``.
- `test_nested_reports_stay_out_of_artifacts(tmp_path: Path) -> None` — A subdirectory holding ``result.md`` is a report, not evidence.

### `tools/common/test_pipeline_output.py`

Pipeline output lives under ``EXACTUS_RESULTS/PIPELINES/``.

- `results_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path` — Point the orchestrator at a throwaway ``EXACTUS_RESULTS`` tree.
- `test_pipeline_paths(results_root: Path) -> None` — Reports, activity and the ownership record move under PIPELINES.
- `test_legacy_pipeline_output_is_removed(results_root: Path) -> None` — Only an old pipeline report directory is deleted, never a tool's.
- `test_pipeline_activity_and_ownership(results_root: Path) -> None` — The pipeline publishes the fixed activity schema and its owner file.
- `test_claim_pipeline_joins_owner_without_terminating_it(results_root: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A same-pipeline claimant requests reset without replacing its owner.
- `test_heal_reads_pipeline_activity_files(results_root: Path) -> None` — Failed entries adopt newer tool reports under PIPELINES.
- `test_unified_refresh_completes_the_progress_block(results_root: Path) -> None` — Refreshing UNIFIED marks the nested progress block complete.
- `test_pipeline_report_links_tool_web_reports(results_root: Path) -> None` — Aggregate metadata links tools relative to the pipeline web report.
- `test_live_pipeline_marks_replaced_reports(results_root: Path, before: str, after: str) -> None` — Refresh successful and failed tools when their reports change.
- `test_pipeline_does_not_wait_without_reruns(results_root: Path) -> None` — The rerun gate returns at once when no same-tool run is live.
- `test_pipeline_waits_for_same_tool_reruns(results_root: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A rerun of a pipeline tool blocks results until it finishes.
- `test_global_fraction_normalizes_each_task_before_aggregation() -> None` — Large internal work totals cannot dominate other pipeline tasks.
- `test_failed_analysis_does_not_block_ready_tool(results_root: Path) -> None` — Analysis findings do not prevent a ready dependent from running.
- `test_gate_blocks_until_the_pipeline_reaches_the_tool_group(results_root: Path) -> None` — A later-group tool launched standalone waits behind the pipeline.
- `test_pipeline_pauses_and_releases_prelaunched_tools(results_root: Path) -> None` — A pre-launched later-group run is paused until its wave arrives.
- `test_release_group_keeps_paused_run_while_lease_is_held(results_root: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A run whose pause lease another owner still holds stays tracked.
- `test_pause_tree_exclude_leaves_target_running() -> None` — ``pause_tree`` never stops pids owned by another pause mechanism.
- `test_pause_tree_suspends_then_resume_tree_continues() -> None` — ``pause_tree`` freezes a process and ``resume_tree`` frees it.
- `test_progress_rows_overlay_external_run_progress(results_root: Path) -> None` — A running external member shows live progress in its row.
- `test_wave_adopts_and_drains_an_external_run(results_root: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A live external member run is adopted instead of duplicated.
- `test_adopted_progress_resets_on_superseding_run(results_root: Path) -> None` — A newer external run resets the adopted tool's progress share.
- `test_standalone_run_waits_at_the_group_gate(results_root: Path) -> None` — A standalone later-group run holds until the pipeline catches up.

### `tools/common/test_pipeline_supervisor.py`

Verify transactional pipeline ownership and observer generations.

- `coordinator(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PipelineCoordinator` — Create a supervisor whose synthetic processes stay live.
- `test_claims_are_isolated_by_pipeline(coordinator: PipelineCoordinator) -> None` — Independent pipeline names elect independent owners.
- `test_connection_recreates_schema_after_runtime_reset(coordinator: PipelineCoordinator) -> None` — A deleted database is recreated before the next owner query.
- `test_compatible_claim_requests_a_shared_generation(coordinator: PipelineCoordinator) -> None` — A compatible collision observes its owner and requests one reset.
- `test_incompatible_and_sealed_claims_wait(coordinator: PipelineCoordinator) -> None` — Different configurations and sealed owners do not merge work.
- `test_terminal_owner_is_observable_and_replaceable(coordinator: PipelineCoordinator) -> None` — Observers see terminal state and a later run can own the pipeline.

### `tools/common/test_process_control.py`

Process-tree control and JSON state primitives.

- `test_process_json_roundtrip(tmp_path: Path) -> None` — JSON helpers write atomically and tolerate bad content.
- `test_process_exists_and_parent_map() -> None` — Liveness checks and the parent map include this process.
- `test_parent_map_without_ps(monkeypatch: pytest.MonkeyPatch) -> None` — Without /proc, ``ps`` output is parsed and failures degrade.
- `test_terminate_tree_kills_children() -> None` — A process and its descendants are terminated.
- `test_terminate_tree_escalates_to_kill(monkeypatch: pytest.MonkeyPatch) -> None` — Processes ignoring SIGTERM are killed.
- `test_parent_map_from_proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A Linux-style /proc tree is read, skipping malformed entries.
- `test_replaced_exactus_exits_with_notice() -> None` — Exit with a readable notice rather than a signal death.
- `subsystem_contract(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise the shared behavior in every shipped subsystem copy.

### `tools/common/test_progress_ownership.py`

Keep terminal progress tied to the invocation being displayed.

- `test_progress_ignores_previous_run_until_current_heartbeat(run_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A completed old run cannot pin the next run's bar at 100 percent.

### `tools/common/test_registry.py`

The cross-process run registry.

- `test_for_output_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Registry paths follow the override, ancestor, then sibling rules.
- `test_concurrent_connection_lifecycles_do_not_deadlock(tmp_path: Path) -> None` — Parallel registry clients serialize SQLite open and close safely.
- `test_claim_beat_finish_live(tmp_path: Path) -> None` — A claimed run is visible, updatable, and finishable.
- `test_activity_ledger_and_source_resource_leases(tmp_path: Path) -> None` — File releases and logical source barriers coordinate across runs.
- `test_conflicts_and_reaping(tmp_path: Path) -> None` — Live foreign runs conflict; dead and same-pid runs are reaped.
- `test_prune_old_and_trim_finished(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Old finished rows are pruned and the database compacted.
- `test_unavailable_registry_degrades(tmp_path: Path) -> None` — An unusable database path yields ``None``/empty, never an error.
- `test_record_decoding_is_defensive() -> None` — Corrupt columns degrade to inert values.
- `test_sanitize_bounds_rows_and_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``sanitize`` trims finished rows and ``beat`` clips long text.
- `test_runtime_env_limits_bound_finished_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``EXACTUS_RUNTIME_MAX_*`` bound finished rows, never live ones.

### `tools/common/test_report_comparison.py`

Exercise baseline retention and per-section report comparisons.

- `test_coverage_remains_unresolved_when_measurements_change(tmp_path: Path) -> None` — Only removing a failing gate resolves it, not a new measured value.
- `test_subsections_metrics_and_repeated_findings(tmp_path: Path) -> None` — Count repeated findings and compare each linter and coverage metric.
- `test_aggregate_deltas_use_previous_tool_snapshots(tmp_path: Path) -> None` — Compare pipeline totals and nested tools against its own baseline.
- `test_baseline_survives_cleanup_and_reaches_worker(tmp_path: Path) -> None` — Preserve canonical and named reports across cleanup and processes.
- `test_first_run_marks_delta_unavailable(tmp_path: Path) -> None` — Distinguish a first run from a real zero-change comparison.
- `test_aggregate_with_counts_but_no_finding_history(tmp_path: Path) -> None` — Use recorded totals while leaving missing finding details unavailable.
- `test_coverage_metrics_exclude_file_details(tmp_path: Path) -> None` — Keep coverage totals and findings without expanding file evidence.
- `test_sparse_count_maps_compare_missing_members_as_zero(tmp_path: Path) -> None` — Report resolved severity and rule counters as real negative deltas.
- `test_rule_categories_include_zero_counts_and_real_deltas(tmp_path: Path) -> None` — Compare declared rules, including rules with no current findings.
- `test_local_server_findings_ignore_run_time_and_ephemeral_port(tmp_path: Path) -> None` — Repeated endpoint failures retain identity across local server runs.
- `test_equal_totals_still_detect_different_endpoints(tmp_path: Path) -> None` — A different failed endpoint remains a real replacement finding.
- `test_capture_records_previous_duration(tmp_path: Path) -> None` — The duration of a captured report is available by canonical path.
- `test_apply_includes_previous_duration(tmp_path: Path) -> None` — The comparison block carries the previous run duration when known.
- `test_first_run_comparison_duration_is_none(tmp_path: Path) -> None` — A first-run comparison explicitly records no previous duration.
- `test_markdown_renders_previous_duration() -> None` — The comparison section mentions the previous run duration.
- `test_markdown_omits_missing_previous_duration() -> None` — When no previous duration is recorded the line is skipped.

### `tools/common/test_report_templates.py`

The shipped report templates render goldens and reach the bundle.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `common` = `root / 'exactus' / 'tools' / 'common' / 'templates'`
  - `template` = `common / 'markdown' / 'result_template.md'`
  - `examples` = `common / 'markdown' / 'examples'`
  - `mapping` = `common / 'markdown' / 'mapping.json'`
  - `html` = `common / 'html'`
- `test_example_matches_golden(*, data: str, expected: str) -> None` — The core template reproduces the golden Markdown exactly.
- `test_empty_example_keeps_every_section() -> None` — A clean run still states scope, findings and artifacts.
- `test_pipes_in_cells_and_globs_survive() -> None` — Pipes are escaped in table cells; globs stay literal code spans.
- `test_error_example_renders_missing_blocks_as_na() -> None` — A crash result without tool blocks renders ``N/A`` sections.
- `test_bundle_ships_the_common_web_assets(tmp_path: Path) -> None` — ``ReportBundle.write`` copies the shipped web assets verbatim.

### `tools/common/test_report_time.py`

Verify readable report timestamps and recorded-time precedence.

- `test_readable_timezone_conversion() -> None` — Show explicit UTC and preserve instants from offset timestamps.
- `test_run_time_precedence() -> None` — Prefer the run start over finish and report-generation timestamps.

### `tools/common/test_snippets.py`

Bounded, root-confined source excerpts around finding lines.

- `class Constants` — Group module-level constants.
  - `target` = `10`
- `test_middle_of_file_has_context_on_both_sides(tmp_path: Path) -> None` — A line inside the file gets ``context`` lines before and after.
- `test_start_and_end_of_file_are_clipped(tmp_path: Path) -> None` — Context never reaches before line 1 or past the last line.
- `test_last_line_without_newline_is_read(tmp_path: Path) -> None` — A final line lacking a line ending is still captured.
- `test_context_zero_and_negative_keep_only_the_target(tmp_path: Path) -> None` — Context 0 (and a negative value) captures the target line alone.
- `test_context_depth_is_capped(tmp_path: Path) -> None` — A huge context keeps the requested value but caps captured lines.
- `test_unusable_lines_and_files_give_nothing(tmp_path: Path) -> None` — Non-positive lines, lines past the end, missing files and folders.
- `test_binary_file_is_skipped(tmp_path: Path) -> None` — A file with a NUL byte in its head is not excerpted.
- `test_invalid_utf8_is_replaced(tmp_path: Path) -> None` — Undecodable bytes become replacement characters.
- `test_line_endings_follow_universal_newlines(tmp_path: Path, data: bytes) -> None` — CR-only and mixed endings number lines like Python does.
- `test_cr_at_a_buffer_boundary_pairs_with_its_lf(tmp_path: Path) -> None` — A CRLF split across read buffers still ends exactly one line.
- `test_huge_lines_are_clipped_without_breaking_numbering(tmp_path: Path) -> None` — Over-long lines are cut, marked, and later lines keep their numbers.
- `test_scan_limit_gives_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A line beyond the byte scan limit yields no excerpt.
- `test_unreadable_file_gives_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An ``OSError`` while reading yields no excerpt.
- `test_paths_outside_the_root_are_refused(tmp_path: Path) -> None` — ``..``, absolute paths and escaping symlinks are never read.
- `test_symlink_inside_the_root_is_followed(tmp_path: Path) -> None` — A symlink whose target stays inside the root is read.
- `test_language_from_file_name() -> None` — Suffixes and well-known names map to fence languages.
- `test_finding_excerpt_needs_a_path_and_a_positive_line(tmp_path: Path) -> None` — Only findings with a string path and a positive int line change.
- `test_with_excerpts_annotates_every_finding(tmp_path: Path) -> None` — ``with_excerpts`` copies the payload and adds per-finding excerpts.

### `tools/common/test_sprint.py`

Flushed printing helpers and the ``DEBUG.txt`` capture directives.

- `class SelectorShape(Protocol)` — Fields of a parsed ``include::``/``exclude::`` selector.
  - Fields: `file: str`, `functions: tuple[str, ...] | None`
- `class SpecShape(Protocol)` — Fields of a resolved ``DEBUG.txt`` specification.
  - Fields: `save: bool`, `max_age: float | None`, `streams: tuple[str, ...]`, `include: tuple[object, ...]`, `exclude: tuple[object, ...]`
- `class SiteShape(Protocol)` — Fields of a captured call site.
  - Fields: `relative: str`, `qualname: str`
- `class Tty` — A string stream pretending to be a terminal.
  - `isatty(self) -> bool` — Report terminal attachment.
- `test_levels_prefix_output(level: sp.PrintLevel, prefix: str) -> None` — Each severity level decorates non-empty output.
- `test_color_follows_terminal_detection() -> None` — ANSI colors appear for terminals or when forced.
- `test_default_streams(monkeypatch: pytest.MonkeyPatch) -> None` — Warnings and errors go to stderr, info to stdout.
- `test_save_target_resolution(tmp_path: Path) -> None` — Capture targets resolve relative to the project root.
- `test_max_age_parsing(text: str | None, seconds: float) -> None` — Ages accept units, bare seconds, and fall back to a day.
- `test_selector_parsing() -> None` — Selectors split file globs from function filters.
- `test_spec_parsing(tmp_path: Path) -> None` — A marker file is resolved into capture directives.
- `test_selector_matching() -> None` — File and function globs both constrain matches.
- `test_clear_drops_old_records(tmp_path: Path) -> None` — Records older than the limit are pruned, fresh ones kept.
- `test_record_is_written_and_filtered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Capture respects stream, include, and exclude directives.
- `test_record_survives_unwritable_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — I/O errors during capture never reach the caller.
- `test_debug_site_skips_module_frames(tmp_path: Path) -> None` — The recorded site is the first frame outside the sprint module.
- `subsystem_contract(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None` — Exercise the shared behavior in every shipped subsystem copy.

### `tools/common/test_stderr_capture.py`

Standard-error capture: line counts, levels and the mirror.

- `test_recorder_splits_chunks_into_lines() -> None` — Lines spanning chunks are counted once and classified.
- `test_pending_line_buffer_is_capped() -> None` — A newline-free flood is classified once from its bounded prefix.
- `test_recorder_lock_is_reentrant() -> None` — A signal handler may record while the main thread holds the lock.
- `test_mirror_records_and_forwards_sys_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The mirror records writes while the original stream still gets them.

### `tools/common/test_terminal.py`

ANSI terminal rendering, progress painting, and cursor probing.

- `class Tty` — A string stream that claims to be a terminal.
  - `isatty(self) -> bool` — Report terminal attachment.
  - `fileno(self) -> NoReturn` — Raise like a stream without a descriptor.
- `tty(monkeypatch: pytest.MonkeyPatch) -> Iterator[Tty]` — Replace the module stdout with a terminal-like stream.
- `plain(monkeypatch: pytest.MonkeyPatch) -> StringIO` — Replace the module stdout with a non-terminal stream.
- `class Constants` — Group module-level constants.
  - `red` = `'\x1b[31m'`
  - `yellow` = `'\x1b[33m'`
  - `reset` = `'\x1b[0m'`
  - `dim` = `'\x1b[2m'`
  - `hide_cursor` = `'\x1b[?25l'`
  - `show_cursor` = `'\x1b[?25h'`
  - `erase_screen` = `'\x1b[2J\x1b[3J\x1b[H'`
  - `min_width` = `48`
  - `max_width` = `160`
  - `tools` = `(('lints', 'RUNNING', 0.5, 'ruff', None), ('docs', 'WAITING', 0.0, '', No...`
- `test_helpers() -> None` — Width fitting, ANSI measuring, clipping and row counting.
- `test_bar_is_contiguous_and_marks_issues_red() -> None` — Aggregate bars fill continuously and propagate issue color.
- `test_results_table(plain: StringIO) -> None` — Results render a summary, rows, and report paths.
- `test_progress_requires_tty(plain: StringIO) -> None` — Non-terminal output draws nothing.
- `test_progress_paints_and_repaints(tty: Tty) -> None` — The live block is painted once and replaced on change.
- `test_progress_marks_failure_cells(tty: Tty) -> None` — A failed tool paints a red x at its failure fraction.
- `test_plain_progress_logs_transitions(tty: Tty, monkeypatch: pytest.MonkeyPatch) -> None` — Terminals without cursor control get an appended change log.
- `test_standalone_progress_and_cursor(tty: Tty) -> None` — Standalone rows hide and restore the cursor.
- `test_clear_screen_on_windows(tty: Tty, monkeypatch: pytest.MonkeyPatch) -> None` — Windows consoles clear through ``cmd /c cls``.
- `test_probe_cursor_branches(tty: Tty, monkeypatch: pytest.MonkeyPatch) -> None` — The capability probe honors platform and TERM.
- `test_probe_without_tty(plain: StringIO) -> None` — A non-terminal stdout never supports cursor control.
- `test_dsr_reply_without_descriptor(tty: Tty, monkeypatch: pytest.MonkeyPatch) -> None` — Missing /dev/tty or stdout descriptors disable cursor support.
- `test_dsr_cursor_moves(*, column: int, answer: bool, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None` — Cursor probing succeeds only against a responsive terminal.
- `test_dsr_cursor_moves_without_termios(monkeypatch: pytest.MonkeyPatch) -> None` — Missing termios support disables the probe.
- `test_dsr_cursor_moves_bad_descriptor() -> None` — A non-terminal descriptor is rejected.
- `test_refreshed_report_status_and_legend(tty: Tty, monkeypatch: pytest.MonkeyPatch, *, cursor: bool) -> None` — Explain marked reports in both live and plain terminal output.
- `test_tty_name_requires_real_terminal(tty: Tty, plain: StringIO) -> None` — ``tty_name`` only reports the device for a true terminal.
- `test_mirror_tty_attaches_and_detaches(plain: StringIO) -> None` — A replaced run's terminal keeps showing live progress.
- `test_mirror_tty_skips_own_terminal(plain: StringIO, monkeypatch: pytest.MonkeyPatch) -> None` — The new run never mirrors back onto its own display.

### `tools/common/test_terminal_progress.py`

Determinate and indeterminate terminal progress rendering.

- `test_width_expressions_and_rejections() -> None` — Responsive width expressions parse; malformed ones raise.
- `test_settings_validation() -> None` — Non-positive animation settings raise ``ValueError``.
- `test_determinate_lifecycle() -> None` — Determinate progress animates, restarts, and finishes cleanly.
- `test_indeterminate_mode_and_auto_start() -> None` — Indeterminate mode auto-starts and switches modes freely.
- `test_context_manager_closes() -> None` — Entering starts rendering; leaving closes and restores the cursor.

### `tools/common/test_toml.py`

Round-trip coverage for the dependency-free TOML serializer.

- `test_scalars_roundtrip() -> None` — Primitive values survive a serialize/parse round trip.
- `test_temporal_scalars_roundtrip() -> None` — Date, time, and datetime values serialize to ISO format.
- `test_nested_tables_emit_dotted_headers() -> None` — Nested dictionaries serialize under dotted table headers.
- `test_empty_table_keeps_header() -> None` — A table without entries still emits its header.
- `test_scalar_arrays_roundtrip() -> None` — Arrays of scalars serialize inline.
- `test_array_of_tables_roundtrip() -> None` — Arrays of dictionaries serialize as ``[[table]]`` blocks.
- `test_array_of_tables_with_nested_tables() -> None` — Array-of-table entries keep nested sub-tables.
- `test_mixed_array_rejects_tables() -> None` — An array holding dictionaries inside scalars is rejected.
- `test_unsupported_type_rejected() -> None` — Unsupported scalar types raise ``TypeError``.
- `test_non_finite_float_rejected() -> None` — NaN and infinity cannot be serialized.
- `test_non_bare_key_is_quoted() -> None` — Keys outside the bare-key pattern serialize quoted.
- `test_string_escaping() -> None` — Escapes serialize inside basic TOML strings.
- `test_generated_pyproject_shape() -> None` — The lints template serializes into a valid lint config.
- `test_array_of_tables_with_nested_array_of_tables() -> None` — Nested arrays of tables serialize recursively and round-trip.

### `tools/common/test_tool_worker.py`

Detached exactus worker specifications, results, and lifecycle hooks.

- `test_build_spec_leaves_dependency_ordering_to_the_supervisor() -> None` — Catalog dependencies never become pmanager ``depends_on`` edges.
- `test_context_and_worker_arguments_round_trip(tmp_path: Path) -> None` — Context names and structured worker arguments retain every request.
- `test_live_status_distinguishes_gone_from_ipc_timeout(monkeypatch: pytest.MonkeyPatch) -> None` — A missing descriptor is dead while an IPC error remains live.
- `test_result_from_status_prefers_report_and_crashes_when_missing(tmp_path: Path) -> None` — Terminal workers reconstruct reports; missing reports become failures.
- `test_lifecycle_hooks_publish_state_cleanup_and_reap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Every lifecycle hook performs its documented stateful behavior.
- `test_control_broadcast_and_external_descriptor_join(tmp_path: Path) -> None` — Control broadcasts acknowledge status and records join by context.

### `tools/common/test_toolkit.py`

Validate catalog, collection, and current partitioned tool dispatch.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
- `test_every_script_exists() -> None` — No catalog tool may point at a missing script.
- `test_normalize_strips_decoration() -> None` — Script-style names normalize to hyphenated identifiers.
- `test_excluded_dir_rules() -> None` — Dot, uppercase, and generated directories are pruned.
- `test_collect_files_skips_generated_output() -> None` — Only real project files are collected.
- `test_all_listed_tools_have_a_command(tmp_path: Path) -> None` — Resolve every shipped declaration from verified miniature payloads.

### `tools/completion/__init__.py`

Tests for ``exactus.tools.completion`` wiring.


### `tools/completion/test_integration.py`

End-to-end coverage against the real ``check`` catalog.

- `class Constants` — Group module-level constants.
  - `block_begin` = `_block_begin(command_name='exactus')`
  - `block_end` = `_block_end(command_name='exactus')`
  - `check_begin` = `_block_begin(command_name='check')`
  - `check_end` = `_block_end(command_name='check')`
- `test_root_offers_dispatch_and_orchestrator_flags() -> None` — ``check --`` offers tool dispatch and orchestrator flags.
- `test_aliases_not_offered_but_matchable() -> None` — Alias dispatch flags are hidden from candidates.
- `test_tool_values_after_tools_flag() -> None` — ``--tools`` offers exactus catalog identifiers.
- `test_remaining_tool_values() -> None` — Used ``--tools`` values are not re-offered.
- `test_pipeline_values() -> None` — ``--pipeline`` offers catalog pipeline identifiers.
- `test_tools_pipeline_mutex() -> None` — ``--tools`` use suppresses ``--pipeline`` (parser mutex).
- `test_dispatch_flag_switches_to_tool_grammar() -> None` — ``--lints`` activates the lints tool's options.
- `test_screenshot_shortcut_merges_grammars() -> None` — ``--url`` activates the merged shortcut grammar.
- `test_completion_subcommand_offers_shells() -> None` — ``check completion`` offers the four shells.
- `test_completion_command_at_root() -> None` — ``completion`` is offered as a root subcommand.
- `test_root_values_complete_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--root`` values complete directories.
- `test_check_main_routes_complete() -> None` — ``check __complete`` reaches the hidden endpoint.
- `test_check_main_routes_completion_command() -> None` — ``check completion bash`` prints a script to stdout.
- `test_completion_command_prints_script() -> None` — The user command emits a shell adapter on stdout.
- `test_install_and_uninstall_bash(tmp_path: Path) -> None` — Bash install manages a block inside the user's ``.bashrc``.
- `test_install_zsh_ensures_compinit(tmp_path: Path) -> None` — The zsh block enables compsys before registering.
- `test_install_refuses_foreign_file(tmp_path: Path) -> None` — A non-check provider file is never overwritten.
- `test_uninstall_refuses_foreign_file(tmp_path: Path) -> None` — A non-check provider file is never deleted.
- `test_powershell_profile_block_lifecycle(tmp_path: Path) -> None` — Profile-block install and removal preserve user content.
- `test_install_idempotent_replaces_block(tmp_path: Path) -> None` — Reinstalling replaces the managed block, never duplicates.
- `test_diagnose_missing_and_healthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Missing shells diagnose cleanly; installed ones healthy.
- `test_diagnose_missing_launcher(tmp_path: Path) -> None` — An installed provider with an unresolvable launcher fails.
- `test_diagnose_stale_protocol(tmp_path: Path) -> None` — A foreign protocol version diagnoses as stale.
- `test_diagnose_command_output(tmp_path: Path) -> None` — ``check completion all --diagnose`` prints per-shell status.
- `test_completion_command_install_action(tmp_path: Path) -> None` — ``--install`` writes the provider file through the command.
- `test_launcher_resolution_covers_module_script_and_path_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Adapters retain a runnable interpreter for modules and zipapps.
- `test_completion_launch_needs_only_standard_library(tmp_path: Path) -> None` — TAB runs with site packages disabled and leaves its cwd untouched.
- `test_canonical_registration_markers(tmp_path: Path) -> None` — Only the Exactus block is removed from a mixed user profile.
- `test_default_tool_provider_uses_exactus_catalog() -> None` — Exactus catalog entries flow into TOOL provider candidates.

### `tools/completion/test_startup.py`

Verify automatic completion without touching real user profiles.

- `class Constants` — Group module-level constants.
  - `block_begin` = `_block_begin(command_name='exactus')`
- `test_first_run_refresh_and_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str) -> None` — Install all supported profiles and refresh only changed content.
- `test_foreign_and_broken_profiles_survive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Preserve foreign files and continue after an unwritable target.
- `test_source_invocation_does_not_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Leave developer invocations free of profile mutations.
- `test_management_removes_automatic_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Remove automatic registrations through the management command.
- `test_powershell_discovers_redirected_all_host_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Query both installed editions for their redirected profile paths.

### `tools/coverage_tests/__init__.py`

Tests mirroring exactus/tests/tools/coverage_tests.


### `tools/coverage_tests/test_assertion_report.py`

Report quoted assertion values as readable multiline evidence.

- `test_missing_content_decodes_actual_markdown() -> None` — Decode a missing table row and the complete actual Markdown.
- `test_expected_actual_decodes_quotes_and_newlines() -> None` — Keep original quoting and whitespace in both assertion values.
- `test_unstructured_assertion_is_preserved() -> None` — Leave unrelated or truncated messages unparsed.

### `tools/coverage_tests/test_core_boundaries.py`

Exercise the standalone coverage CLI and malformed browser evidence.

- `test_discovery_prunes_outputs_but_keeps_nested_test_groups(tmp_path: Path) -> None` — Discovery ignores generated roots without hiding groups under tests.
- `test_collection_progress_cannot_overtake_test_execution(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Keep collection below the execution span so progress never reverses.
- `test_file_shards_are_balanced_without_duplicate_collection(tmp_path: Path) -> None` — File-level sharding assigns every module once by estimated cost.
- `test_node_shards_split_large_test_modules(tmp_path: Path) -> None` — Node-level sharding can distribute one slow module across workers.
- `test_node_collection_uses_exact_pytest_ids(tmp_path: Path) -> None` — Collection preserves parametrized node IDs for worker assignment.
- `test_node_shards_isolate_standalone_packages(tmp_path: Path) -> None` — Independent package projects never share a pytest interpreter.
- `test_package_meta_tests_require_an_exclusive_shard() -> None` — Package-wide launchers run after package-specific test processes.
- `test_child_environment_drops_live_coordination(monkeypatch: pytest.MonkeyPatch) -> None` — Coverage subprocesses cannot mutate their parent's live registry.
- `test_standalone_cli_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Resolve repeated source roots and preserve every standalone CLI option.
- `test_project_root_boundaries(tmp_path: Path) -> None` — Widen source subtrees only inside their nearest project marker.
- `test_standalone_main_preserves_exit_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int) -> None` — Exit with the runner result without performing a nested full test run.
- `test_invalid_v8_ranges_are_ignored() -> None` — Retain valid V8 intervals while rejecting malformed nested entries.
- `test_empty_and_missing_javascript_sources(tmp_path: Path) -> None` — Missing and empty files have no executable coverage ranges.
- `test_source_excludes_drop_measured_python_files(tmp_path: Path) -> None` — Exclude globs drop matching files from the measured module index.
- `test_source_excludes_drop_measured_javascript(tmp_path: Path) -> None` — Exclude globs drop matching files from the JavaScript lane.

### `tools/coverage_tests/test_coverage_tool.py`

In-process coverage-tests runs over the demo and a tiny project.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `demo` = `root / 'demo'`
  - `tree` = `frozenset({'result.md', 'result.json', 'result_web/', 'COVERAGE/result.md...`
- `test_package_does_not_shadow_third_party_coverage() -> None` — The ``coverage_tests`` package never hides the coverage library.
- `demo_copy(tmp_path: Path) -> Path` — Copy the demo fixture into a throwaway project.
- `test_parse_args_defaults() -> None` — Validation gates default to 80 percent and the run gate to 90.
- `test_demo_combined_coverage(demo_copy: Path, tmp_path: Path) -> None` — Python and JavaScript coverage run together and gates pass.
- `test_demo_flag_variants(flags: tuple[str, ...], demo_copy: Path, tmp_path: Path) -> None` — Optional flags are honored without crashing.
- `test_unmet_gates_fail(demo_copy: Path, tmp_path: Path) -> None` — Impossible floors make the analyzer return a failing status.
- `test_project_without_tests(tmp_path: Path) -> None` — A project with no tests is handled without crashing.
- `test_per_file_gates_fail(flag: str, demo_copy: Path, tmp_path: Path) -> None` — Average and per-file floors fail the run when unmet.
- `test_generated_skip_plugin_is_a_regular_package(tmp_path: Path) -> None` — Create the copied pytest helper in an explicit Python package.
- `test_skip_plugin_preserves_project_imports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Plugin discovery preserves imports in nested Python processes.
- `test_production_conftest_is_measured(tmp_path: Path) -> None` — Measure production conftests while omitting test fixtures.
- `test_owned_source_root_is_not_omitted_by_directory_name(tmp_path: Path) -> None` — Measure an explicit source root even when its name is excluded.
- `test_file_snippets_embed_context(tmp_path: Path) -> None` — Uncovered lines embed as context-windowed, flagged hunks.
- `test_file_snippets_zero_and_negative_context(tmp_path: Path) -> None` — Zero context embeds only the uncovered lines; negatives clamp to zero.
- `test_context_lines_option(sample_project: Path, tmp_path: Path) -> None` — ``--context-lines`` defaults to 3 and is embedded in the report.
- `test_file_snippets_skips_unhighlightable(tmp_path: Path) -> None` — Non-source files and missing files embed no snippets.
- `test_combined_tests_report_lists_failures_with_reasons(sample_project: Path, tmp_path: Path) -> None` — The TESTS report states what ran, what failed, and why.
- `class FdStream` — Stream stand-in exposing a real process descriptor.
  - `__init__(self, *, descriptor: int) -> None` — Remember the descriptor.
  - `fileno(self) -> int` — Return the descriptor.
  - `flush(self) -> None` — Accept flushes.
- `tiny_project(tmp_path: Path) -> Path` — Create a one-module package with one passing and one failing test.
- `test_tiny_project_output_tree(tiny_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A passing coverage gate ignores test failures and writes the tree.
- `test_playwright_greenlet_body_is_measured(tmp_path: Path) -> None` — Measure executed browser code across Playwright greenlet switches.
- `test_group_reports_do_not_inherit_other_group_failures(sample_project: Path, tmp_path: Path) -> None` — Keep passing and skipped groups green when another group fails.
- `test_v8_offsets_after_astral_unicode_keep_the_correct_line(tmp_path: Path) -> None` — Attribute UTF-16 browser ranges after emoji to their source line.
- `test_excuse_shortfalls_filters_javascript_below_minimum(tmp_path: Path) -> None` — Drop an excused JavaScript file from the manifest and totals.

### `tools/coverage_tests/test_coverage_validator.py`

Coverage evidence validation and per-file floors.

- `class Constants` — Group module-level constants.
  - `coverage` = `{'totals': {'percent_covered': 91.5}, 'files': {'src/core/a.py': {'summar...`
- `test_valid_evidence(tmp_path: Path) -> None` — Complete matching evidence passes, flat or under ``ARTIFACTS``.
- `test_invalid_evidence(overrides: dict[str, JsonValue], message: str, tmp_path: Path) -> None` — Failed runs, JS failures and tampered data are rejected.
- `test_missing_files_rejected(tmp_path: Path) -> None` — A missing marker or data file means incomplete evidence.
- `test_floors(tmp_path: Path) -> None` — Total and critical-module floors are enforced.
- `test_validate_writes_verdict(tmp_path: Path) -> None` — The verdict file records pass and failure reasons.
- `test_fail_raises() -> None` — ``_fail`` raises the coverage error type.

### `tools/coverage_tests/test_javascript_gate.py`

Gate JavaScript coverage while preserving passing test results.

- `test_javascript_gates_are_reported_as_coverage_findings(tmp_path: Path) -> None` — Keep a low-coverage JavaScript lane in the coverage part.
- `test_package_named_javascript_sources_are_measured(tmp_path: Path) -> None` — Sources under a ``packages`` directory are measured like others.
- `test_javascript_only_project_runs_tests_and_fails_low_coverage(tmp_path: Path) -> None` — Run Node tests even without Python tests and enforce both gates.
- `test_unavailable_javascript_runtime_keeps_distinct_reason(tmp_path: Path) -> None` — A missing Node runtime reports its detail, not a generic failure.

### `tools/coverage_tests/test_meaningful.py`

Meaningful classification, configuration, and coverage integration.

- `test_meaningful_parser_defaults_and_complete_policy() -> None` — Expose enforcement defaults and every Meaningful policy family.
- `test_meaningful_pyproject_and_cli_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Load Meaningful settings from pyproject and prefer explicit CLI.
- `test_meaningful_parser_accepts_all_control_families() -> None` — Map representative flags from every Meaningful option family.
- `test_meaningful_parser_rejects_invalid_policy_values(flag: str, value: str) -> None` — Fail cleanly for invalid Meaningful numeric settings.
- `test_adapter_preserves_successes_and_failures(tmp_path: Path) -> None` — Keep one canonical row for every path even when analysis fails.
- `test_adapter_respects_configured_level_boundary(tmp_path: Path) -> None` — Filter a structural file when only TEST-3 is actionable.
- `test_meaningful_detects_javascript_not_covered_by_tests(tmp_path: Path) -> None` — Require tests for behavioral JavaScript reported as uncovered.
- `test_adapter_applies_unclassified_policy(*, policy: str, actionable: bool, analysis_error: bool, tmp_path: Path) -> None` — Apply every configured policy to a retained failed analysis row.
- `test_require_counts_unreached_source_at_zero(tmp_path: Path) -> None` — Count required unreached files at zero and fail the coverage gate.
- `test_include_unreached_counts_filtered_sources_without_findings(tmp_path: Path) -> None` — Count every source at zero while Meaningful findings stay selective.
- `test_non_enforcing_modes_preserve_previous_omission(mode: str, tmp_path: Path) -> None` — Preserve omission when classification does not enforce results.
- `test_shortfall_rows_carry_origin_and_reason(tmp_path: Path) -> None` — Tag rows produced for sub-gate sources with the shortfall origin.
- `test_merge_results_combines_rows_and_counts() -> None` — Merge two classification passes with rebuilt artifact counts.
- `test_shortfall_excused_below_minimum_level(tmp_path: Path) -> None` — Exclude a sub-gate file Meaningful rates below the minimum level.
- `test_shortfall_actionable_keeps_per_file_finding(tmp_path: Path) -> None` — Keep enforcing the per-file gate on meaningful sub-gate files.
- `test_shortfall_gate_only_excused_when_meaningful_runs(mode: str, tmp_path: Path) -> None` — Excuse sub-gate files in classify mode but not when Meaningful is off.

### `tools/coverage_tests/test_report_layout.py`

Coverage reports distinguish branch measurements and focus on failures.

- `test_ranges_text_compacts_only_runs_of_three(*, lines: list[int], expected: str) -> None` — Two-line runs stay comma-separated; longer runs become spans.
- `test_coverage_report_keeps_failure_details_out_of_summary_tables(tmp_path: Path) -> None` — Render a passing overall gate with a failing per-file requirement.

### `tools/coverage_tests/test_skipped_report.py`

Preserve skipped test evidence without turning skips into failures.

- `test_skip_plugin_records_real_pytest_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None` — Exercise the production plugin during an actual skipped test.
- `test_skip_plugin_preserves_parameter_ids_and_source(tmp_path: Path) -> None` — Keep skip details in TESTS reports and out of coverage findings.
- `test_skip_plugin_skips_malformed_reports_and_writes_timings(tmp_path: Path) -> None` — Ignore malformed skip reports and aggregate per-file timings.
- `test_skip_plugin_ignores_missing_timings_option(tmp_path: Path) -> None` — Return without writing timings when the option is unset.

### `tools/coverage_tests/test_steps_trace.py`

Steps debug trace coverage for the coverage-tests tool chain.

- `test_progress_snapshots_are_traced(tmp_path: Path) -> None` — Published progress snapshots reach the active steps trace.
- `test_meaningful_bridge_traces(tmp_path: Path) -> None` — The Exactus Meaningful bridge logs selection and row counts.
- `test_meaningful_mode_off_traces(tmp_path: Path) -> None` — A disabled Meaningful run records the skip instead of silence.
- `test_packaged_meaningful_traces_lifecycle(tmp_path: Path) -> None` — Packaged Meaningful workers record each per-file analysis stage.
- `test_main_writes_steps_artifact(tmp_path: Path) -> None` — The coverage-tests entry point writes ``ARTIFACTS/steps.txt``.
- `test_write_false_suppresses_steps_artifact(tmp_path: Path) -> None` — ``[tool.steps] write = false`` leaves no trace file behind.

### `tools/coverage_tests/test_test_group_name.py`

Test paths map to stable TESTS report group names.

- `test_test_group_name(*, test: str, group: str) -> None` — Mirror directories under ``tests`` are skipped when naming the group.

### `tools/coverage_tests/test_tracebacks.py`

Tests for traceback and failure parsing helpers.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `project_file` = `'exactus/tests/tools/coverage_tests/test_coverage_tool.py'`
- `test_relative_returns_posix_path_for_project_file() -> None` — An existing project file is returned relative to the root.
- `test_relative_accepts_root_relative_path() -> None` — A root-relative path is resolved against the root.
- `test_relative_rejects_outside_root(tmp_path: Path) -> None` — Paths outside the project root are ignored.
- `test_relative_rejects_non_file() -> None` — Directories are not treated as files.
- `test_relative_rejects_foreign_parts() -> None` — Paths inside installed package directories are ignored.
- `test_relative_returns_none_for_unresolvable_path(tmp_path: Path) -> None` — A path whose resolution raises is treated as outside the project.
- `test_relative_rejects_foreign_parts_for_existing_file(tmp_path: Path) -> None` — A file under a foreign directory is still rejected.
- `test_sections_split_failure_and_error_blocks() -> None` — Sections are grouped by their banner kind.
- `test_titles_for_failed_node() -> None` — Failed nodes map to the section title matching the test name.
- `test_titles_for_error_node() -> None` — Error nodes include setup and teardown variants.
- `test_titles_for_collection_error() -> None` — Collection errors use a dedicated title.
- `test_reason_prefers_error_line() -> None` — The first E line becomes the reason when present.
- `test_reason_prepends_exception_when_not_in_error() -> None` — The exception class is prepended when the E line omits it.
- `test_reason_falls_back_to_exception_only() -> None` — The exception alone is used when no E lines are available.
- `test_reason_returns_empty_when_nothing_is_known() -> None` — An empty reason is returned with neither errors nor exception.
- `test_site_stops_at_capture_heading() -> None` — Lines after a capture heading are ignored for location and reason.
- `test_site_skips_unmatched_lines() -> None` — Lines that match no pattern are ignored while scanning.
- `test_site_picks_deepest_project_frame() -> None` — The deepest frame inside the project is selected.
- `test_sites_returns_none_for_missing_section() -> None` — Entries without a matching section produce a None site.
- `test_sites_matches_and_pops_sections_in_order() -> None` — Each entry consumes its section and later entries may miss.
- `test_frame_path_handles_file_urls() -> None` — A file:// URL is decoded and made relative to the root.
- `test_frame_path_handles_plain_paths() -> None` — A plain absolute path is made relative to the root.
- `test_entry_returns_none_without_test_at() -> None` — A group that does not start with a test-at line is ignored.
- `test_entry_reads_name_reason_and_frame() -> None` — A normal Node spec failure entry is parsed.
- `test_entry_uses_test_location_when_no_project_frame() -> None` — The test-at location is used when no stack frame maps to the project.
- `test_parse_returns_empty_when_no_banner() -> None` — Output without a failing-tests banner yields no failures.
- `test_parse_collects_multiple_failures() -> None` — Every test-at group after the banner becomes one failure.
- `test_entry_prefers_first_project_frame() -> None` — Only the first project frame updates the location.

### `tools/docs/__init__.py`

Tests of the docs tool.


### `tools/docs/test_docs_metrics.py`

DOCS reports docstring and JSDoc analysis volume.

- `class Constants` — Group module-level constants.
  - `golden` = `Path(__file__).resolve().parent / 'golden'`
  - `tool_dir` = `ReportTemplates.tool_dir(analyzer='docs')`
  - `doc` = `'"""Module."""\n'`
  - `js` = `'/** Add. */\nexport function add(a, b) {\n  return a;\n}\n'`
- `test_languages_report_files_and_lines(tmp_path: Path) -> None` — Each language lists the files and lines of the sources analyzed.
- `test_failed_and_excluded_sources_are_not_counted(tmp_path: Path) -> None` — A syntax error or an excluded file adds neither files nor lines.
- `test_legacy_language_table_is_unchanged(tmp_path: Path) -> None` — The existing ``languages`` and ``statistics`` keep their keys.
- `test_empty_sources_report_zero_code_volume(tmp_path: Path) -> None` — ``report_data`` with no sources still emits the code metrics block.
- `test_empty_metrics_say_why_nothing_is_listed() -> None` — Empty metrics render N/A with a reason in every block.
- `test_missing_metrics_render_na() -> None` — A result without ``extension.metrics`` renders N/A blocks.
- `test_code_lines_count_line_feeds(tmp_path: Path) -> None` — Code lines end at line feeds only, exactly like Markdown lines.

### `tools/docs/test_docs_report.py`

DOCS renders result.md from its normalized result.json and template.

- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_golden_result_renders_expected_markdown() -> None` — The checked-in result.json renders the checked-in result.md.
- `test_crash_render_shows_error_and_na_blocks() -> None` — An envelope-only result renders ERROR with N/A tool blocks.
- `test_report_data_is_normalized(tmp_path: Path) -> None` — ``report_data`` returns summary, scope, findings and extension.
- `test_execute_exactus_renders_docs_from_template(tmp_path: Path) -> None` — A real DOCS run writes the normalized report bundle.
- `test_clean_docs_run_states_no_findings(tmp_path: Path) -> None` — A documented project renders explicit empty-findings text.
- `test_overload_signatures_need_no_docstring(tmp_path: Path) -> None` — ``@overload`` signatures are exempt from docstring requirements.

### `tools/frontend/__init__.py`

Tests of the frontend tool.


### `tools/frontend/test_frontend.py`

Verify FRONTEND uses normal Studio projects and their capture policies.

- `test_flow_capture_policy_and_response(*, screenshot: bool, tmp_path: Path) -> None` — Preserve outcomes, JavaScript results and requested images.
- `test_url_only_has_no_implicit_screenshots(tmp_path: Path) -> None` — Navigate without discovery or implicit screenshot artifacts.
- `test_parser_accepts_workspace_without_url(tmp_path: Path) -> None` — Allow self-contained projects and reject obsolete crawler arguments.
- `test_configured_recipe_and_explicit_project(tmp_path: Path) -> None` — Resolve recipes beside their config and honor explicit projects.
- `test_frontend_cli_runs_recipe_and_writes_report(tmp_path: Path) -> None` — The Actions CLI executes an imported project and preserves responses.
- `test_frontend_legacy_markdown_retains_step_response(tmp_path: Path) -> None` — Standalone rendering preserves failed workflows and JavaScript data.

### `tools/frontend/test_frontend_progress.py`

Frontend progress uses completed work and ignores repeated attempts.

- `test_recipe_progress_advances_through_discovery_and_replay() -> None` — Publish intermediate progress across both Actions phases.
- `test_replay_counts_retries_once() -> None` — Count distinct event IDs while preserving runtime completion details.
- `test_parallel_progress_waits_for_all_workers_and_counts_retries_once() -> None` — Publish combined worker completion through the heartbeat percentage.

### `tools/frontend/test_frontend_report.py`

Frontend reports retain execution outcomes and readable evidence.

- `test_frontend_report_explains_diagnostics_and_steps(tmp_path: Path) -> None` — Preserve a failed step beside a successful workflow and its response.
- `test_artifact_paths_follow_organized_output(tmp_path: Path) -> None` — Link relocated screenshots while leaving external evidence paths alone.
- `test_empty_frontend_execution_does_not_claim_success(tmp_path: Path) -> None` — An execution with no evidence keeps an explicit unknown status.
- `test_findings_group_browser_failures_by_flow(tmp_path: Path) -> None` — Keep related browser failures together and server logs readable.

### `tools/frontend/test_parallel_flows.py`

Verify concurrent real-browser replay and ordered workflow evidence.

- `test_parallel_flows_overlap_and_preserve_isolation_and_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Overlap bounded workers with isolated pages and monotonic progress.
- `test_workers_must_be_positive(tmp_path: Path) -> None` — Reject invalid concurrency before accessing the saved workspace.

### `tools/kwargs_typehints/__init__.py`

Tests of the kwargs-typehints tool.


### `tools/kwargs_typehints/test_kwargs_report.py`

KWARGS_TYPEHINTS renders result.md and its web view from normalized data.

- `write_project(*, root: Path) -> None` — Write the tiny project every test exactuss.
- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_findings_cover_every_category(tmp_path: Path) -> None` — Each category is normalized, ordered, numbered and located.
- `test_summary_scope_and_metrics(tmp_path: Path) -> None` — Counters, scope and metrics describe what was checked.
- `test_extension_rows_link_to_their_findings(tmp_path: Path) -> None` — Unresolved, ambiguous and bare-import rows name their finding.
- `test_normalization_of_rare_categories() -> None` — Parse failures, safe bare imports and unknown reasons normalize.
- `test_golden_result_renders_expected_markdown() -> None` — The checked-in result.json renders the checked-in result.md.
- `test_crash_render_shows_na_blocks() -> None` — An envelope-only result renders ERROR with N/A tool blocks.
- `test_clean_run_states_why_tables_are_empty() -> None` — A clean run says so in the findings and every extension table.
- `test_execute_exactus_writes_the_normalized_bundle(tmp_path: Path) -> None` — A real run writes result.json/md, the web view and heuristics.json.

### `tools/kwargs_typehints/test_kwargs_typehints.py`

The kwargs-typehints analyzer on projects, flags and its artifacts.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
- `test_kwargs_strict_flag(sample_project: Path, tmp_path: Path) -> None` — Strict mode reports unannotatable bindings too.
- `test_typevar_assignments_need_no_annotation(tmp_path: Path, *, strict: bool) -> None` — Exempt typing factories but retain ordinary assignment diagnostics.
- `test_kwargs_exempts_positional_only_and_dynamic_callees(tmp_path: Path) -> None` — Dynamic and positional-only calls are counted apart, not unresolved.
- `test_kwargs_default_root_is_repository_root() -> None` — The kwargs core's ``--root`` default is the repository root.
- `test_import_roots_and_annotated_factories(tmp_path: Path) -> None` — Configured namespace roots and type aliases resolve real classes.
- `test_external_module_and_bound_classmethod_resolution(tmp_path: Path) -> None` — Imported submodules and class methods keep their actual receivers.
- `test_kwargs_writes_heuristics_under_artifacts(tmp_path: Path) -> None` — The type-fuzz heuristics land in ``ARTIFACTS/heuristics.json``.
- `test_kwargs_auto_heals_safe_findings_and_converges(tmp_path: Path) -> None` — Safe kwargs/import findings are repaired before the final report.
- `test_kwargs_dry_run_preserves_sources(tmp_path: Path) -> None` — Dry-run reports validated repairs without changing source.
- `test_kwargs_pyproject_dry_reports_without_writing(tmp_path: Path) -> None` — Tool-local pyproject dry mode validates repairs without writing.
- `test_bare_imports_require_only_attribute_access(tmp_path: Path) -> None` — Only module attribute access requires an explicit from-import.
- `test_bare_import_heal_keeps_module_value_uses(tmp_path: Path) -> None` — Auto-heal keeps a bare import required by module value uses.
- `test_stub_guards_are_decided_by_the_target_interpreter() -> None` — Version and platform guards follow the target, not the host.
- `test_target_python_reads_the_project_interpreter(tmp_path: Path) -> None` — The project's own interpreter supplies the inference facts.
- `test_target_python_falls_back_to_the_running_interpreter(tmp_path: Path) -> None` — Missing, failing, or garbled interpreters use the running one.
- `test_target_python_uses_the_configured_interpreter(tmp_path: Path) -> None` — An explicit ``python`` setting wins over the project venv.
- `test_target_python_trusts_the_project_environment(tmp_path: Path) -> None` — A project ``.venv`` is used even outside ``requires-python``.
- `test_target_python_accepts_an_environment_directory(tmp_path: Path) -> None` — The ``python`` setting may name a virtual-environment directory.
- `test_requires_python_reads_the_declared_specifier(tmp_path: Path) -> None` — ``requires-python`` is read from the project table only.
- `test_spec_clauses_and_version_ok_cover_common_operators() -> None` — Specifier parsing and evaluation cover the declared operators.
- `test_pointer_keywords_follow_the_project_python(tmp_path: Path) -> None` — ``ctypes.POINTER`` is keyword-capable only where the project says so.
- `test_pointer_keywords_hold_on_a_real_python_313(tmp_path: Path) -> None` — A real 3.13 project interpreter never yields a ``cls`` finding.
- `test_python_option_is_part_of_the_cli_grammar() -> None` — The shared grammar (help, completion) lists ``--python``.
- `test_python_option_reaches_the_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--python`` is forwarded to the engine, and omitted when unset.

### `tools/lints/__init__.py`

Tests of the lints tool.


### `tools/lints/test_compliance.py`

LINTS includes the canonical engineering rules and their source evidence.

- `class Constants` — Group module-level constants.
  - `marker` = `'# ' + 'noqa'`
- `test_source_rules_preserve_findings(tmp_path: Path, source: str, rule: str) -> None` — Preserve syntax, suppression and annotation rules in the lint scanner.
- `test_configuration_rules_preserve_findings(tmp_path: Path, settings: str | None, rule: str) -> None` — Keep configuration bans and the missing configuration diagnostic.
- `no_commands(cwd: Path, toolchain: Path | None) -> dict[str, tuple[str, ...] | None]` — Resolve no external tools for the built-in report integration test.
- `test_engineering_findings_are_part_of_lints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run the lints entry point and retain rule counts, gating and excerpts.

### `tools/lints/test_css_tokens.py`

The lints CSS token audit resolves one token graph across stylesheets.

- `class Sources` — Group stylesheet fixtures.
  - `clean` = `dedent(text='    :root {\n      --primary-length-unit: 4px;\n      --base...`
- `audit(*, root: Path, sources: dict[str, str], words: frozenset[str]=frozenset()) -> tuple[CssTokenFinding, ...]` — Write stylesheets under ``root`` and audit them as one set.
- `rules(*, findings: tuple[CssTokenFinding, ...]) -> list[str]` — Return the sorted distinct rule identifiers of findings.
- `test_conforming_layers_pass(tmp_path: Path) -> None` — A PRIMARY, BASE, CATALOG, SEMANTIC chain consumed by SEMANTIC is clean.
- `test_each_rule_reports(tmp_path: Path, text: str, rule: str) -> None` — Every ``CSS1xx`` rule is reported by a minimal stylesheet.
- `test_every_rule_has_a_name() -> None` — The rule table covers CSS100 through CSS125 without gaps.
- `test_scoped_overrides_are_not_conflicts(tmp_path: Path) -> None` — A property set under different selectors is a cascade, not a clash.
- `test_tokens_resolve_across_files(tmp_path: Path) -> None` — A token defined in one stylesheet satisfies a use in another.
- `test_dynamic_references_need_no_definition(tmp_path: Path) -> None` — ``--dynamic-*`` tokens are supplied at run time.
- `test_comments_and_strings_hide_nothing(tmp_path: Path) -> None` — Separators in comments and strings do not split declarations.
- `test_component_directories_are_matched_whole(tmp_path: Path) -> None` — A CATALOG name is flagged for the component's name, not its words.
- `test_grammar_keywords_stay_literal(tmp_path: Path) -> None` — Structural keywords need no token; their design operands still do.
- `test_finding_locates_declaration(tmp_path: Path) -> None` — A finding names the file, line and offending declaration.
- `test_layer_prefixes() -> None` — Prefixes select the layer; any other custom property is SEMANTIC.
- `lines_of(*, findings: tuple[CssTokenFinding, ...]) -> list[tuple[str, int]]` — Return the sorted ``(rule, line)`` pairs of findings.
- `test_unreadable_files_are_findings_not_crashes(tmp_path: Path) -> None` — A missing or non-UTF-8 stylesheet is reported and the rest audited.
- `test_byte_order_mark_and_crlf(tmp_path: Path) -> None` — A BOM is dropped and CRLF endings keep line numbers right.
- `test_malformed_input_degrades_locally(tmp_path: Path, text: str, expected: list[tuple[str, int]]) -> None` — Broken strings, comments, parentheses and braces hide nothing.
- `test_important_does_not_hide_a_plain_reference(tmp_path: Path) -> None` — ``var(--x) !important`` is still one plain SEMANTIC reference.
- `test_strings_are_not_references_or_literals(tmp_path: Path) -> None` — ``var()`` and measures inside strings and ``url()`` are text.
- `test_css_wide_keywords_need_no_token(tmp_path: Path) -> None` — ``inherit`` cannot pass through a custom property; it stays literal.
- `test_negative_numbers_are_literals(tmp_path: Path) -> None` — A signed measure is a design literal, not part of a name.
- `test_context_words_match_case_insensitively(tmp_path: Path) -> None` — A CATALOG name segment matches a context word in any case.
- `test_long_values_are_clipped_in_messages(tmp_path: Path) -> None` — A huge value cannot bloat a finding message.
- `test_one_line_files_scale(tmp_path: Path) -> None` — A minified single-line sheet is lexed and located in linear time.
- `test_lexer_keeps_text_length_and_lines(tmp_path: Path) -> None` — The structural view always matches the text in length and lines.
- `test_every_prefix_of_a_sheet_audits(tmp_path: Path) -> None` — Truncating a sheet anywhere never raises and keeps lines in range.
- `no_commands(cwd: Path, toolchain: Path | None) -> dict[str, tuple[str, ...] | None]` — Resolve no external tools for the built-in report integration test.
- `test_token_findings_are_part_of_lints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The lints entry point reports token findings under ``custom_css``.
- `test_studio_component_directories_have_one_uniform_contract() -> None` — Every Studio style component exposes the same three-file surface.

### `tools/lints/test_js_delimiters.py`

Behavioral tests for the JavaScript delimiter simplifier.

- `class Constants` — Group module-level constants.
  - `min_multiple_transformations` = `2`
- `expect(*, condition: bool, message: str) -> None` — Expect.
- `test_simplifies_supported_constructs(source: str, expected: str) -> None` — Simplify supported constructs and remain idempotent.
- `test_preserves_required_delimiters(source: str) -> None` — Preserve delimiters required by grammar, precedence, or scope.
- `test_preserves_object_expression_arrow_inside_call() -> None` — Keep object-expression parentheses while simplifying its parameter.
- `test_file_processing_write_backup_and_unchanged(tmp_path: Path) -> None` — Support dry runs, writes, backups, and stable unchanged files.
- `test_file_discovery_and_exclusions(tmp_path: Path) -> None` — Discover supported files respecting default and custom exclusions.
- `test_rich_metrics_and_execution(tmp_path: Path) -> None` — Expose immutable transformation, source, file, and execution metrics.
- `test_source_and_empty_transformation_metrics() -> None` — Derive source deltas and empty transformation metadata.
- `test_real_node_validation_when_available(tmp_path: Path) -> None` — Validate transformed source with Node when the runtime is available.
- `test_public_stability_corpus(source: str) -> None` — Exercise lexical and precedence paths through the public API.
- `test_scan_reports_findings_without_writing(tmp_path: Path) -> None` — Without ``fix`` each simplifiable file is a positioned finding.
- `test_scan_heals_files_with_fix(tmp_path: Path) -> None` — With ``fix`` files are rewritten, reported as heals, then stable.
- `test_scan_reports_unreadable_files(tmp_path: Path) -> None` — Non-UTF-8 sources produce ``DEL002`` error findings in both modes.
- `test_embedded_delimiters_progress_stays_in_its_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Delimiter completion must not mark the whole lint run complete.

### `tools/lints/test_js_function_blocks.py`

Behavioral tests for the Python JavaScript block analyzer API.

- `expect(*, condition: bool, message: str) -> None` — Expect.
- `executable_for(command: str, *, available: frozenset[str]) -> str | None` — Return an executable for the command.
- `source_file(*, tmp_path: Path, suffix: str='.js') -> Path` — Source file.
- `completed(*, stdout: str='', stderr: str='', code: int=0) -> CompletedProcess[str]` — Completed.
- `block_payload() -> dict[str, JsonValue]` — Block payload.
- `test_constructor_validation(*, tmp_path: Path) -> None` — Test constructor validation.
- `test_analyze_public_contract(*, tmp_path: Path) -> None` — Test analyze public contract.
- `test_analyze_failures(*, tmp_path: Path, result: CompletedProcess[str], error_type: type[Exception], message: str) -> None` — Test analyze failures.
- `test_conversion_public_wrappers(*, tmp_path: Path) -> None` — Test conversion public wrappers.
- `test_conversion_failures(*, tmp_path: Path, result: CompletedProcess[str], error_type: type[Exception], message: str) -> None` — Test conversion failures.
- `scenario_file(*, tmp_path: Path, marker: str) -> Path` — Scenario file.
- `test_end_to_end_analysis_and_conversion(*, tmp_path: Path) -> None` — Test end to end analysis and conversion.
- `test_end_to_end_reverse_and_parser_fallback(*, tmp_path: Path) -> None` — Test end to end reverse and parser fallback.
- `test_end_to_end_parse_failure(*, tmp_path: Path) -> None` — Test end to end parse failure.
- `test_public_block_field_validation(*, tmp_path: Path, key: str, value: JsonValue, message: str) -> None` — Test public block field validation.
- `test_public_node_unavailable_for_analyzer(*, tmp_path: Path) -> None` — Test public node unavailable for analyzer.
- `eslint_which(*, cmd: str) -> str | None` — Eslint which.
- `npm_which(*, cmd: str) -> str | None` — Npm which.
- `node_which(*, cmd: str) -> str | None` — Node which.
- `test_public_espree_resolution_fallbacks(*, tmp_path: Path) -> None` — Test public espree resolution fallbacks.
- `test_automatic_normalization_public_api(*, tmp_path: Path) -> None` — Test automatic normalization public api.
- `test_scan_reports_findings_without_writing(tmp_path: Path) -> None` — Without ``fix`` each modernizable file is a positioned finding.
- `test_scan_heals_files_with_fix(tmp_path: Path) -> None` — With ``fix`` files are rewritten, reported as heals, then stable.
- `test_embedded_function_blocks_progress_stays_in_its_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Function-block completion must not mark the whole lint run complete.

### `tools/lints/test_lints.py`

In-process runs of the lints analyzer over generated projects.

- `class Constants` — Group module-level constants.
  - `line_length` = `60`
- `test_weighted_progress_keeps_activity_monotonic(monkeypatch: pytest.MonkeyPatch) -> None` — Weight expensive checks and retain progress during heartbeat notes.
- `test_conventions_progress_is_uniform_and_monotonic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Each conventions sub-step fills only its own file-weighted slice.
- `test_parse_args_defaults() -> None` — Defaults leave every cleaning stage enabled.
- `test_parse_args_integrated_stage_controls() -> None` — CLI controls expose group-final and unsafe Ruff behavior.
- `test_pyproject_configures_integrated_stages(tmp_path: Path) -> None` — The lints pyproject table accepts both integrated-stage controls.
- `test_parse_args_simple_and_runtime_limits() -> None` — ``--simple`` and the runtime-registry retention flags parse.
- `test_parse_args_rejects_bad_runtime_limits() -> None` — Malformed runtime retention values fail argument parsing.
- `test_pyproject_configures_simple_and_runtime_limits(tmp_path: Path) -> None` — The lints table accepts ``simple`` and the runtime limits.
- `test_simple_progress_budgets_only_all_lints(monkeypatch: pytest.MonkeyPatch) -> None` — The all-lints-only run publishes its own spans and stage total.
- `test_pyrefly_stage_span_replaces_infer_label(monkeypatch: pytest.MonkeyPatch) -> None` — ``--no-fix`` runs report a ``pyrefly`` stage, never ``infer``.
- `test_run_organize_respects_dry_run_and_writes(tmp_path: Path) -> None` — Organize only selected Python files and honor dry-run mode.
- `test_run_organize_traces_each_file_state(tmp_path: Path) -> None` — Trace changed, unchanged, and unparseable organizer inputs.
- `test_sample_project_lints(flags: tuple[str, ...], sample_project: Path, tmp_path: Path) -> None` — Lints report findings for a defective sample project.
- `test_fixing_pass_runs_on_copy(sample_project: Path, tmp_path: Path) -> None` — The default pipeline cleans and fixes a throwaway project.
- `test_defect_project_lints(flags: tuple[str, ...], defect_project: Path, tmp_path: Path) -> None` — Lints flag defects in every supported language.
- `test_repo_lints_dry(repo_args: tuple[str, ...], tmp_path: Path) -> None` — The toolkit lints its own source tree without crashing.
- `test_template_resource_found(name: str) -> None` — The bundled linter templates resolve from the packaged lints core.
- `test_parse_args_long_line_repair_control() -> None` — The long-line repair is on by default and has its own switch.
- `test_long_line_repair_needs_fixing_ruff_and_its_switch() -> None` — The repair exists only when fixing, enabled and Ruff is resolved.
- `test_long_line_summary_is_written_to_the_status_stream(tmp_path: Path) -> None` — Repaired and skipped files are reported; an absent repair is silent.
- `test_lints_repairs_lines_ruff_cannot_wrap(tmp_path: Path) -> None` — A fixing run wraps a long string that Ruff's formatter leaves alone.
- `test_inline_style_scan_lints_generated_code_not_embedded_source(tmp_path: Path) -> None` — Lint generated code while ignoring its serialized source excerpts.
- `test_javascript_organizer_orders_safe_method_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Order JavaScript methods while leaving class fields as barriers.
- `test_uppercase_globals_exempt_generic_binders(tmp_path: Path) -> None` — ``TypeVar``-family bindings skip ``PY002``; mutable globals do not.

### `tools/lints/test_lints_install.py`

Installer paths of the lints core, exercised with fake subprocesses.

- `class FakeSystem` — Record commands and report configurable availability.
  - `__init__(self, *, present: set[str], returncode: int=0) -> None` — Store which executables exist and the install exit status.
  - `which(self, *, cmd: str) -> str | None` — Return a fake path for known executables.
  - `run(self, *, args: Sequence[str], **_: object) -> CompletedProcess[str]` — Record one command and return a canned result.
- `test_install_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None` — A failing installer command raises with its output.
- `test_ensure_node_noop_when_npm_present(monkeypatch: pytest.MonkeyPatch) -> None` — Nothing is installed when npm already exists.
- `test_ensure_node_unsupported_host(monkeypatch: pytest.MonkeyPatch) -> None` — Unknown operating systems are rejected.
- `test_node_installers_run_expected_commands(monkeypatch: pytest.MonkeyPatch, host: str, tools: set[str], needle: str) -> None` — Each platform installer issues its package-manager command.
- `test_node_installer_without_manager(monkeypatch: pytest.MonkeyPatch, host: str) -> None` — A missing package manager gives an actionable error.
- `test_ensure_tools_installs_missing(monkeypatch: pytest.MonkeyPatch) -> None` — Missing Python and Node tools are installed through pip and npm.
- `test_ensure_tools_skips_when_bundle_present(monkeypatch: pytest.MonkeyPatch) -> None` — An offline bundle short-circuits all installation.
- `test_sudo_prefix_and_refresh_path(monkeypatch: pytest.MonkeyPatch) -> None` — Privilege prefix follows euid and PATH gains Node locations.

### `tools/lints/test_lints_normalizers.py`

Diagnostic normalizers for every external tool's JSON output.

- `normalize(*, tool: str, payload: object) -> list[dict[str, JsonValue]]` — Run the lints core's private diagnostic normalizer.
- `class Constants` — Group module-level constants.
  - `ignored_notice` = `'File ignored because of a matching ignore pattern. x'`
  - `bad` = `{'ruff': [{}, [1], [{'location': 1}], [{'location': {}, 'end_location': 2...`
- `test_malformed_payloads_raise(tool: str, payload: object) -> None` — Unexpected shapes are rejected with ``TypeError``.
- `test_valid_payloads() -> None` — Representative native payloads normalize to the shared schema.
- `test_helper_conversions() -> None` — Severity labels and rule names normalize.

### `tools/lints/test_lints_report.py`

LINTS renders result.md and its web view from normalized data.

- `write_sources(*, root: Path) -> None` — Write the two project files the fake findings point into.
- `fake_report(*, root: Path) -> dict[str, JsonValue]` — Return a legacy ``LintExactus.run`` payload without running linters.
- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_report_data_normalizes_a_fake_result(tmp_path: Path) -> None` — Summary, scope, findings and metrics come from the legacy payload.
- `test_report_data_metrics(tmp_path: Path) -> None` — Per-linter rows, top rules, top files and severities per linter.
- `test_findings_carry_excerpts(tmp_path: Path) -> None` — Shared excerpts attach to findings at their root-relative path.
- `test_finding_title(message: str, expected: str) -> None` — Titles are the first sentence of the first line, shortened.
- `test_paths_and_statuses(tmp_path: Path) -> None` — Paths become root-relative; statuses name how a linter took part.
- `test_versions_and_durations_are_recorded(tmp_path: Path) -> None` — ``--version`` probes and command timings reach the tool entries.
- `test_golden_result_renders_expected_markdown() -> None` — The checked-in result.json renders the checked-in result.md.
- `test_crash_render_shows_na_blocks() -> None` — An envelope-only result renders ERROR with N/A tool blocks.
- `test_empty_findings_state_why_nothing_is_listed(tmp_path: Path) -> None` — A clean run says so in the findings and the metric tables.
- `test_execute_exactus_renders_lints_from_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A real LINTS run writes the normalized report bundle and web view.
- `test_execute_exactus_simple_reports_only_all_lints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--simple`` writes the standard bundle with all-lints tools only.
- `test_execute_exactus_dry_reports_pyrefly_not_infer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``--no-fix`` runs publish the ``pyrefly`` stage, never ``infer``.

### `tools/lints/test_long_lines.py`

The lints long-line repair keeps behavior and converges to a fixpoint.

- `class Constants` — Group module-level constants.
  - `docstring_width` = `70`
  - `hook_width` = `50`
  - `long_value` = `'value = "' + 'word ' * 30 + '"\n'`
  - `nl` = `'\n'`
  - `repair_sources` = `('value = "' + 'alpha beta gamma ' * 5 + '"\n', 'value = """' + 'alpha be...`
  - `concat_sources` = `('value = "' + 'alpha beta gamma ' * 5 + '"\n', 'value = """' + 'alpha be...`
- `test_every_repair_family_preserves_the_ast(source: str) -> None` — Each repair rewrites a long line without changing the AST.
- `test_trailing_comment_is_hoisted_above_the_statement() -> None` — A comment that makes a line too long moves above its statement.
- `test_directive_comments_stay_on_their_line() -> None` — Pragma comments are never hoisted or wrapped.
- `test_standalone_comment_wraps() -> None` — A long standalone comment becomes several comment lines.
- `test_docstring_reflow_keeps_summary_and_fields() -> None` — Docstring prose wraps while the summary line stays whole.
- `test_fmt_off_regions_are_protected() -> None` — Lines inside a fmt-off region are reported, never rewritten.
- `test_unbreakable_line_is_reported() -> None` — A single long name cannot be split and is classified as unfixable.
- `test_ruff_exempt_lines_are_not_reported() -> None` — Single words, URL endings and trailing pragmas are exempt as in Ruff.
- `test_diff_is_attached_when_requested() -> None` — A changed result carries a unified diff naming the source.
- `test_check_only_never_writes(tmp_path: Path) -> None` — A check-only run reports the change without touching the file.
- `test_commit_preserves_mode_and_writes_backup(tmp_path: Path) -> None` — The atomic write keeps permissions and saves the original bytes.
- `test_encoding_cookie_is_preserved(tmp_path: Path) -> None` — A latin-1 source is read and written back in latin-1.
- `test_clean_crlf_file_is_untouched(tmp_path: Path) -> None` — A file without long lines keeps its exact bytes.
- `test_parse_ruff_report_keeps_only_e501_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Only E501 diagnostics with a usable row are kept per file.
- `test_parse_ruff_report_rejects_malformed_json(tmp_path: Path) -> None` — Invalid JSON and non-array JSON raise distinct documented errors.
- `test_discover_skips_hidden_and_build_directories(tmp_path: Path) -> None` — Directory discovery is sorted and excludes generated trees.
- `test_line_length_falls_back_to_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Without Ruff the nearest pyproject supplies the width.
- `test_line_length_reads_ruff_show_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The width is parsed from Ruff's resolved settings output.
- `test_ruff_e501_rows_come_from_the_ruff_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Rows Ruff reports for a file seed the repair; failures yield none.
- `test_batch_fix_resolves_width_once_per_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A batch seeds rows from a report and memoizes the width lookup.
- `test_repair_hook_fixes_files_and_summarizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The stabilizer hook repairs long lines and records the outcome.
- `test_module_source_is_a_fixpoint() -> None` — The engine's own source already satisfies the width it enforces.
- `test_split_literals_stay_parenthesized_and_multiline(source: str) -> None` — Every emitted implicit concatenation keeps grouping parentheses.
- `test_batched_e501_rows_report_only_long_files(tmp_path: Path) -> None` — One Ruff call maps long files to rows and omits clean files.
- `test_batched_e501_rows_tolerate_bad_ruff_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Missing launchers, bad JSON and non-array JSON yield no rows.
- `test_repair_many_rewrites_long_files_only(tmp_path: Path) -> None` — The batched repair fixes long files and leaves clean ones alone.
- `test_single_file_repair_records_changes_and_skips(tmp_path: Path) -> None` — Calling the repair per file fixes long lines and records skips.

### `tools/lints/test_method_contracts.py`

Protect externally inherited instance methods from binding changes.

- `test_external_override_keeps_instance_binding() -> None` — Retain explicit base contracts while diagnosing ordinary helpers.

### `tools/lints/test_shebang.py`

The lints shebang check reports and heals permission mismatches.

- `test_embedded_shebang_progress_stays_in_its_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Permission completion must not mark the whole lint run complete.
- `test_check_file_permission_mismatches(tmp_path: Path) -> None` — Shebang/exec-bit mismatches produce EXE001 and EXE002 findings.
- `test_heal_adds_executable_bit_to_shebang_file(tmp_path: Path) -> None` — EXE001 heals by marking the shebang file executable.
- `test_heal_inserts_shebang_into_executable(tmp_path: Path) -> None` — EXE002 heals by prepending the suffix's interpreter line.
- `test_heal_drops_exec_bit_instead_of_shebang(tmp_path: Path) -> None` — ``drop-exec`` clears the bits of executables lacking a shebang.
- `test_heal_drops_shebang_from_non_executable(tmp_path: Path) -> None` — ``drop-shebang`` removes the shebang of non-executable files.
- `test_report_only_keeps_findings_and_files(tmp_path: Path) -> None` — Without healing the mismatches stay findings and files untouched.
- `test_heal_is_idempotent(tmp_path: Path) -> None` — A second healed scan finds nothing left to repair or report.

### `tools/lints/test_shebang_metrics.py`

The lints shebang check counts executables, shebangs and interpreters.

- `class Constants` — Group module-level constants.
  - `scripts` = `{'bin/a.py': ('#!/usr/bin/env python3\nx = 1\n', True), 'bin/b.py': ('#!/...`
- `test_interpreter_is_normalized(line: bytes, expected: str) -> None` — Shebang lines reduce to the program they launch.
- `test_non_shebang_line_has_no_interpreter() -> None` — Ordinary source lines name no interpreter.
- `test_metrics_of_a_mixed_project(tmp_path: Path) -> None` — Counters, interpreters, mismatch lists and extensions add up.
- `test_metrics_payload_shape(tmp_path: Path) -> None` — ``metrics_data`` carries rows and path lists as JSON.
- `test_metrics_ignore_skipped_files(tmp_path: Path) -> None` — Symlinks, excluded files and hidden folders are not counted.
- `test_metrics_of_an_empty_project(tmp_path: Path) -> None` — A root without Python files reports zeroes and empty tables.
- `test_unreadable_file_is_counted_but_not_classified(tmp_path: Path) -> None` — A file that cannot be read gives EXE003 and no shebang facts.

### `tools/lints/test_source_cleaner.py`

Behavioral tests for the lints source cleaner.

- `test_normalize_drops_javascript_blank_lines() -> None` — JavaScript cleaning removes empty lines outside literals.
- `test_normalize_keeps_template_literal_blank_lines() -> None` — Blank lines inside template literals are string content.
- `test_normalize_covers_jsx_and_cjs() -> None` — JSX and CommonJS sources get the same blank-line removal.
- `test_normalize_drops_stylesheet_blank_lines() -> None` — CSS cleaning removes empty lines outside block comments.
- `test_normalize_drops_markup_blank_lines() -> None` — HTML cleaning removes empty lines between elements.
- `test_normalize_keeps_preformatted_markup_blanks() -> None` — Blank lines inside pre, script and comments are content.
- `test_normalize_drops_python_blank_lines_outside_strings() -> None` — Python cleaning removes blank lines but keeps docstring content.
- `test_normalize_python_pyi_and_final_newline() -> None` — Stub files clean like Python and end in one newline.
- `test_collect_includes_all_source_suffixes(tmp_path: Path) -> None` — Collection picks up every handled source suffix.
- `test_collect_excludes_only_root_packages(tmp_path: Path) -> None` — A root ``packages/**`` pattern leaves nested packages dirs in scope.
- `test_clean_writes_normalized_javascript(tmp_path: Path) -> None` — The clean pass rewrites a JavaScript file in place.

### `tools/lints/test_string_transform.py`

Behavioral tests for source-preserving string conversion.

- `class Constants` — Group module-level constants.
  - `line_length` = `45`
  - `explicit_width` = `100`
  - `discovered_width` = `79`
  - `configured_width` = `67`
  - `default_width` = `88`
- `test_implicit() -> None` — Preserve embedded Python code and trailing newline.
- `test_docstring() -> None` — Do not convert a module docstring.
- `test_explicit_and_fstrings() -> None` — Rewrite explicit and implicit concatenation preserving output.
- `test_complex_literals() -> None` — Check carriage returns, unusual quoting, and nested format specs.
- `test_fstring_call_formatting(tmp_path: Path) -> None` — Normalize a call inside an f-string through the Ruff formatter.
- `test_fstring_nested_call_formatting(tmp_path: Path) -> None` — Keep nested calls inline while expanding the outer call.
- `test_ast_helpers_and_rejections() -> None` — Cover flattening, signature, rendering, and rejection paths.
- `test_import_variations() -> None` — Merge or insert ``dedent`` across existing textwrap imports.
- `test_options_and_error_cases(tmp_path: Path) -> None` — Cover tree validation, dry-run, and formatting toggles.
- `test_ruff_failure_paths(tmp_path: Path) -> None` — Return ``None`` or the staged call when Ruff fails or no-ops.
- `test_fstring_ruff_staging_with_fake(tmp_path: Path) -> None` — Stage multiline calls when the Ruff subprocess is a no-op.
- `test_long_literal() -> None` — A long ordinary literal is split without changing its value.
- `test_long_fstring() -> None` — An interpolated string is split without changing interpolation.
- `test_multiline_bytes_raw_and_docstrings() -> None` — Preserve exact literal values and module documentation.
- `test_rejections_and_settings() -> None` — Reject unsupported options.
- `test_nested_fstrings_and_debug_are_safe() -> None` — Unsafe f-string transformations must be rejected, never corrupted.
- `test_unicode_escapes_and_crlf() -> None` — Handle Unicode and escaped controls without changing AST semantics.
- `test_controls_and_error_paths(tmp_path: Path) -> None` — Exercise disabling switches, width constraints, and invalid sources.
- `test_literal_helpers_and_atomic_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify literal splitting, offsets, and atomic cleanup.
- `test_varied_literal_boundaries(tmp_path: Path) -> None` — Check safe skipping for unsplittable and multiline expressions.
- `test_nested_and_comment_preservation(tmp_path: Path) -> None` — Preserve nested scope docstrings and adjacent comments.
- `test_more_skip_and_conversion_branches(tmp_path: Path) -> None` — Cover insufficient budgets, docstrings, and interpolations.
- `test_indented_budget_and_empty_literals(tmp_path: Path) -> None` — Reject transformations when indentation consumes the line budget.
- `test_rejected_candidate_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject malformed generated fragments and tokenization failures.
- `test_write_failure_and_source_preservation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Verify write failures leave original bytes unchanged.
- `test_format_interpolation_and_idempotence(tmp_path: Path) -> None` — Expand long f-string calls without changing the module AST.
- `test_source_encoding_and_crlf_roundtrip(tmp_path: Path) -> None` — Respect declared legacy encodings and CRLF on disk.
- `test_interpolation_rejection(tmp_path: Path) -> None` — Report indivisible oversized interpolation arguments.
- `test_interpolation_keyword_and_single_argument(tmp_path: Path) -> None` — Cover keyword expansion and conservative single-argument rejection.
- `test_interpolation_comment_protection(tmp_path: Path) -> None` — Do not rewrite interpolation text that might contain comments.
- `test_interpolation_already_short_and_already_multiline(tmp_path: Path) -> None` — Leave fitting and previously expanded calls unchanged.
- `test_combined_transform(tmp_path: Path) -> None` — Combine dedenting and splitting without modifying the source twice.
- `test_combined_dry_run(tmp_path: Path) -> None` — Dry runs preserve original bytes while returning transformed source.
- `test_ruff_line_length_discovery(tmp_path: Path) -> None` — Use Ruff's resolved formatter setting and forward CLI overrides.
- `test_ruff_unavailable_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Use Ruff's default only when its executable cannot be discovered.

### `tools/performance/__init__.py`

Tests for the performance exactus tool.


### `tools/performance/test_main.py`

The performance tool wraps the generic analyzer for this project.

- `trace_text() -> str` — Return a deterministic two-step trace.
- `write_trace(*, root: Path, tool: str='LINTS') -> Path` — Write one Exactus-shaped trace fixture.
- `test_main_reports_missing_traces(tmp_path: Path) -> None` — An empty scan root returns status 2 and a FAIL report.
- `test_main_analyzes_and_exports(tmp_path: Path) -> None` — A trace produces the report bundle plus the exported dashboard.
- `test_parse_args_reads_repeatable_sources(tmp_path: Path) -> None` — ``--source`` accumulates into a list replacing the default scan root.

### `tools/readme/__init__.py`

Tests of the readme tool.


### `tools/readme/test_readme.py`

The README analyzer flags undocumented directory entries.

- `test_readme_directory_exactus_flags_undocumented_entries(tmp_path: Path) -> None` — Undocumented files and directories each surface a finding.
- `test_readme_exactus_repairs_missing_inventories(tmp_path: Path) -> None` — Fix mode creates missing READMEs and extends existing inventories.
- `test_readme_exactus_dry_leaves_files_unchanged(tmp_path: Path) -> None` — Dry mode reports violations without writing project files.

### `tools/readme/test_readme_metrics.py`

README owns Markdown statistics, sizes and undocumented folders.

- `class Constants` — Group module-level constants.
  - `doc` = `'"""Module."""\n'`
  - `js` = `'/** Add. */\nexport function add(a, b) {\n  return a;\n}\n'`
- `test_markdown_and_readme_statistics(tmp_path: Path) -> None` — Markdown totals, README count and the largest and smallest README.
- `test_readme_ties_resolve_to_the_first_path(tmp_path: Path) -> None` — Equal-sized READMEs report the first path in path order.
- `test_directories_without_readme(tmp_path: Path) -> None` — Only folders holding analyzed sources can lack a README.
- `test_root_without_readme_is_listed_as_dot(tmp_path: Path) -> None` — A root holding sources but no README appears as ``.``.
- `test_exclusions_apply_to_markdown(tmp_path: Path) -> None` — Excluded folders, hidden folders and exclude globs hide Markdown.
- `test_symlinked_markdown_is_ignored(tmp_path: Path) -> None` — A Markdown symlink pointing outside the root is never followed.
- `test_project_without_markdown_has_empty_readme_stats(tmp_path: Path) -> None` — No Markdown gives zero totals, ``None`` extremes and every folder.

### `tools/readme/test_readme_report.py`

README renders result.md from its normalized result.json and template.

- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_golden_result_renders_expected_markdown() -> None` — The checked-in result.json renders the checked-in result.md.
- `test_crash_render_shows_error_and_na_blocks() -> None` — An envelope-only result renders ERROR with N/A tool blocks.
- `test_report_data_is_normalized(tmp_path: Path) -> None` — ``report_data`` returns summary, scope, findings and extension.
- `test_execute_exactus_renders_readme_from_template(tmp_path: Path) -> None` — A real README run writes the normalized report bundle.
- `test_clean_readme_run_states_no_findings(tmp_path: Path) -> None` — A fully documented project renders explicit empty-findings text.

### `tools/record/__init__.py`

Tests for the Exactus Record studio.


### `tools/record/selector_support.py`

Build small projects that use selectors, for the selector tests.

- `flow_json(*, flow_id: str) -> dict[str, JsonValue]` — Return a one-click flow in the current schema.
- `project() -> Workspace` — Build two flows that use the ``card`` selector in several ways.
- `class Constants` — Group module-level constants.
  - `page_url` = `(Path(__file__).parent / 'web_selector' / 'index.html').as_uri()`

### `tools/record/test_action_schema.py`

Verify typed action bindings and stable input/output identities.

- `class Constants` — Group test constants.
  - `contract` = `Path(__file__).resolve().parent / 'fixtures' / 'contract' / 'action-contr...`
  - `added_runtime_types` = `frozenset({'url', 'selector', 'duration', 'artifact', 'list', 'void'})`
- `test_value_vocabulary_matches_the_locked_contract() -> None` — Keep the production value categories aligned with the contract.
- `test_action_output_identity_ignores_paths_and_display_metadata() -> None` — Use producer and port IDs as the only stable source identity.
- `test_binding_accepts_json_null_as_a_real_literal() -> None` — Distinguish an authored null from a missing binding payload.
- `test_binding_rejects_multiple_or_mismatched_payloads() -> None` — Reject ambiguous persisted binding documents before execution.
- `test_dependency_ids_follow_first_use_order() -> None` — Expose hard dependencies used to order and move action blocks.
- `test_slot_enforces_secret_and_retry_capabilities() -> None` — Authorize secrets by destination and retries by slot declaration.
- `test_schema_rejects_ambiguous_ports() -> None` — Keep the action's default result and source IDs unambiguous.
- `test_output_reference_rejects_empty_identity_parts() -> None` — Require usable producer, port, path and getter identities.
- `test_binding_reports_its_producer_dependency() -> None` — Name the action that must run before an output-consuming binding.
- `test_binding_rejects_blank_text_payloads() -> None` — Reject whitespace-only variable, template and prompt payloads.
- `test_slot_rejects_inconsistent_definitions() -> None` — Reject empty IDs, void types and mismatched secret/list metadata.
- `test_port_rejects_inconsistent_definitions() -> None` — Reject empty IDs, void types and non-list item metadata.
- `test_schema_rejects_empty_and_duplicate_identities() -> None` — Keep schema, slot and port identities non-empty and unique.

### `tools/record/test_assertions_causality.py`

Coverage for assertion evaluation and causal attribution.

- `spec(operator: AssertionOperator, expected: str | None='x') -> AssertionSpec` — Build an assertion spec for one operator.
- `test_assertion_operators(operator: AssertionOperator, actual: str | None, expected: str | None, *, exists: bool, outcome: AssertionOutcome) -> None` — Check one operator row of the evaluation truth table.
- `test_assertion_errors() -> None` — Check malformed specs raise evaluation errors.
- `class EventDetails` — Optional timeline-event fields used by the attribution tests.
  - `flow_id` = `'f'`
  - `url` = `None`
  - `correlation_id` = `None`
  - `initiator_url` = `None`
  - `initiator_stack` = `()`
  - `caused_by_event_id` = `None`
- `class Constants` — Group module-level constants.
  - `min_confidence` = `0.9`
  - `expected_candidates` = `2`
  - `default_details` = `EventDetails()`
- `event(event_id: str, kind: EventKind, elapsed_ms: int, *, details: EventDetails=Constants.default_details) -> TimelineEvent` — Build a timeline event with test defaults.
- `test_causal_attribution_paths() -> None` — Check causal attribution follows each evidence path.
- `test_causal_ambiguity_does_not_guess() -> None` — Check ambiguous candidates are left unattributed.

### `tools/record/test_bridge_protocol.py`

HTML-editor architecture regression tests.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `studio` = `root / 'exactus' / 'tools' / 'record' / 'studio'`
- `test_editor_assets_are_local_and_iframe_free() -> None` — Handle test editor assets are local and iframe free.

### `tools/record/test_crawler_visit.py`

The visit-plan crawler and the parallel visit replayer.

- `class Constants` — Group module-level constants.
  - `site` = `dedent(text='    <!doctype html><html lang="en"><body>\n    <nav class="s...`
- `fast_timings(monkeypatch: pytest.MonkeyPatch) -> None` — Shrink the crawler's settle and timeout delays.
- `app_url(tmp_path: Path) -> Iterator[str]` — Serve the crawler-shaped application.
- `test_slug_and_ids() -> None` — Slugs are filesystem safe and ids are stable.
- `test_device_and_theme_resolution() -> None` — Names resolve against presets and unknown names fail.
- `test_plan_parsing() -> None` — Plans decode defensively and validate required fields.
- `test_storage_seed_script() -> None` — The seed script sets theme, setup flag and optional machine.
- `test_build_plan_discovers_interfaces(app_url: str, version: ConsoleVersion) -> None` — The crawler inventories panels, dialogs, options and toggles.
- `test_dismiss_wizard_paths(app_url: str) -> None` — The wizard closes by Continue or by Escape fallback.
- `test_visit_helpers() -> None` — Pure replay helpers redact, truncate and format.
- `test_store_sync(tmp_path: Path) -> None` — Captures are written beneath new directories.
- `test_run_visits_end_to_end(app_url: str, tmp_path: Path, *, dedup: bool, server_log: bool, threshold: float) -> None` — A crawled plan replays across lanes with captures and logs.
- `test_visit_step_failure_reports_error(tmp_path: Path) -> None` — Unreachable URLs exhaust retries and report the error.
- `test_drain_events(tmp_path: Path) -> None` — Queued console and page-error events are serialized.

### `tools/record/test_diagnostic_sources.py`

Browser diagnostics retain real script locations and function stacks.

- `class Constants` — Group module-level constants.
  - `script` = `dedent(text='    function reportProblem() {\n      console.error("console...`
  - `page` = `'<script src="http://diagnostics.test/app.js"></script><img src="http://d...`
- `test_sync_console_and_exception_sources() -> None` — Capture source frames, native resource errors and exceptions.
- `test_async_console_and_exception_sources() -> None` — Discovery also retains source lines and function names.

### `tools/record/test_discovery_project.py`

Verify crawler projects open and replay in browser Studio.

- `discovery_target(tmp_path: Path) -> Iterator[str]` — Serve a deterministic target revealing two ordered click actions.
- `test_discovery_opens_a_replayable_studio_project(discovery_target: str, tmp_path: Path, *, snapshots: bool) -> None` — Discover clicks, open their project, and replay the exact sequence.

### `tools/record/test_expectations.py`

Tests for action-attributed network expectation matching.

- `test_expectation_matches_query_status_headers_and_json() -> None` — Handle test expectation matches query status headers and json.
- `test_expectation_fails_on_unexpected_status() -> None` — Handle test expectation fails on unexpected status.
- `test_expectation_failure_dimensions_and_body_modes() -> None` — Cover URL, method, query, header, and body mismatch dimensions.
- `test_expectation_url_and_json_helpers_cover_variants() -> None` — Cover URL modes, indexed JSON paths, and condition operators.
- `test_expectation_helper_edge_paths() -> None` — Check expectation helpers cover their edge paths.

### `tools/record/test_expressions_errors.py`

Error handling and operator coverage of the expression evaluator.

- `class Constants` — Group module-level constants.
  - `number` = `RuntimeVariable(name='count', value_type=ValueType.INTEGER, value=3)`
  - `secret` = `RuntimeVariable(name='token', value_type=ValueType.STRING, value='s3cret'...`
- `test_invalid_expressions_raise(expression: str) -> None` — Malformed or unsupported expressions raise ``ExpressionError``.
- `test_validate_rejects_empty_and_syntax_errors(expression: str) -> None` — Validation reports empty and unparsable expressions.
- `test_operators_evaluate(expression: str, *, expected: bool) -> None` — Comparison, boolean, and containment operators evaluate correctly.
- `test_interpolation_rejects_unknown_and_secret_variables() -> None` — Templates cannot reference unknown or secret variables.
- `test_boolean_coercion_accepts_booleans_and_rejects_text() -> None` — Booleans pass through; unrecognized text is rejected.

### `tools/record/test_expressions_execution.py`

Behavioral coverage for expression and execution engines.

- `class Constants` — Group module-level constants.
  - `expected_integer` = `4`
  - `expected_float` = `2.5`
  - `expected_variable_count` = `2`
  - `coerced_integer` = `12`
  - `coerced_float` = `1.5`
- `test_value_codec_and_expression_language() -> None` — Exercise typed coercion, helpers, comparisons, and interpolation.
- `test_expression_failures_are_explicit() -> None` — Reject unsafe, malformed, secret, and non-boolean expressions.
- `test_execution_engine_selects_condition_and_completes() -> None` — Run a conditional transition followed by terminal completion.
- `test_running_one_flow_does_not_follow_its_connections() -> None` — A single-flow run completes after the first flow, edge or not.
- `test_variable_resolution_and_execution_errors() -> None` — Cover defaults, secrets, merges, redaction, and execution guards.
- `test_variable_resolver_parameter_guards_and_defaults() -> None` — Cover required runtime values and Flow parameter resolution.
- `test_value_codec_edge_cases() -> None` — Check the codec round-trips and rejects unusual values.
- `test_value_codec_none() -> None` — Check ``None`` round-trips through the codec.

### `tools/record/test_flow_contracts.py`

Bind the locked v4 contract files to FLOW.md and the real v3 surface.

- `class Constants` — Group module-level constants.
  - `tests` = `Path(__file__).resolve().parent`
  - `record` = `tests.parents[2] / 'tools' / 'record'`
  - `spec` = `tests.parents[3] / 'docs' / 'todo' / 'FLOW.md'`
  - `document` = `tests.parents[3] / 'docs' / 'todo' / 'FLOW-CONTRACT.md'`
  - `action_count` = `48`
  - `spec_row_count` = `43`
  - `headings` = `('## Schema version', '## Persisted names', '## Unknown-field policy', '#...`
  - `limits` = `('max_program_depth', 'max_nodes_per_flow', 'max_graph_nodes', 'max_itera...`
  - `void_actions` = `frozenset({'pointer', 'input_text', 'select_option', 'check', 'uncheck',...`
  - `action_keys` = `frozenset({'id', 'label', 'status', 'spec_row', 'inputs', 'outputs', 'con...`
  - `slot_keys` = `frozenset({'slot', 'type', 'required', 'item_type', 'many', 'sensitivity'...`
  - `port_keys` = `frozenset({'port', 'type', 'item_type', 'primary', 'nullable', 'sensitivi...`
  - `type_aliases` = `(('variable reference', 'variable_ref'), ('variable type', 'variable_type...`
  - `spec_row_pattern` = `'`([a-z_./]+):\\s*([^`]+)`'`
- `test_contract_has_the_spec_counts() -> None` — Hold every spec row and the exact number of actions.
- `test_actions_are_well_formed() -> None` — Enforce the shape rules of actions, slots and ports.
- `test_interaction_actions_publish_nothing() -> None` — Forbid a pass-through output on an action that returns void.
- `test_contract_covers_exactly_the_v3_catalog() -> None` — Mark every palette id `v3` and nothing else as `v3`.
- `test_contract_agrees_with_the_spec_table() -> None` — Match each spec row's required inputs and outputs by name and type.
- `test_secret_rules_are_destination_based() -> None` — Allow secrets only where a slot declares the destination.
- `test_selector_contract_agrees_with_the_spec() -> None` — Match the selector contract to FLOW.md sections 13.5, 13.10, 13.11.
- `test_javascript_contract_agrees_with_the_spec() -> None` — Match the JavaScript contract to FLOW.md sections 14.2, 14.3, 14.11.
- `test_receipt_contract_agrees_with_the_spec() -> None` — Hold the manifest, install record, forbidden content and ownership.
- `test_decision_document_keeps_every_section_and_limit() -> None` — Fail when a locked decision disappears from the document.

### `tools/record/test_flow_inventory.py`

Keep the version-3 action inventory complete and current.

- `class Constants` — Group module-level constants.
  - `record` = `Path(__file__).resolve().parents[3] / 'tools' / 'record'`
  - `document` = `Path(__file__).resolve().parents[4] / 'docs' / 'todo' / 'FLOW-INVENTORY.md'`
- `test_every_event_kind_is_in_the_matrix() -> None` — List each event kind exactly once in the rendered matrix.
- `test_every_catalog_id_resolves_to_a_kind_or_guard() -> None` — Resolve each palette id to real event kinds, or to a guard.
- `test_inventory_document_is_current() -> None` — Fail when the committed document no longer matches the tree.

### `tools/record/test_flow_runner.py`

Real-browser coverage of Studio functional tests and screenshot evidence.

- `page() -> Iterator[Page]` — Create an isolated real Chromium page for each behavioral test.
- `test_semantic_replay_and_durable_evidence(page: Page, tmp_path: Path) -> None` — Checks stay idempotent; option values and evidence survive replay.
- `test_failed_contract_retries_then_skips_and_captures(page: Page, tmp_path: Path) -> None` — A failed assertion retries, captures images and blocks later actions.
- `test_navigation_and_ci_reports(tmp_path: Path) -> None` — A workspace navigates, verifies the page, and writes CI evidence.
- `test_empty_test_is_rejected(page: Page, tmp_path: Path) -> None` — An empty flow cannot masquerade as a passed functional test.
- `test_ui_response_expectations_and_explicit_screenshot(page: Page, tmp_path: Path) -> None` — Observe a UI-caused response and capture an authored checkpoint.
- `test_browser_state_assertions(page: Page, tmp_path: Path) -> None` — Verify DOM, storage, cookies, URL, title and JavaScript contracts.
- `test_unsupported_flow_configuration_is_rejected(page: Page, tmp_path: Path, feature: str) -> None` — Reject unsupported configuration instead of reporting a false pass.
- `test_failed_workspace_writes_junit_and_selection_error(tmp_path: Path) -> None` — Publish failed-flow evidence and reject missing flow selections.
- `test_cancelled_flows_keep_state_distinct_in_json_and_junit(tmp_path: Path) -> None` — Cancellation reports ``cancelled`` per flow, never ``failed``.
- `test_flow_cli_reports_failure_and_rejects_invalid_viewport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Return CI failure status and validate viewport CLI arguments.
- `test_console_and_invalid_selector_assertions_fail(page: Page, tmp_path: Path) -> None` — Unsupported and broken assertions fail instead of crashing the run.
- `test_output_bindings_and_unsupported_steps_fail(page: Page, tmp_path: Path) -> None` — Output bindings are skipped; non-action steps report failures.
- `test_http_call_actions_share_or_isolate_cookies(page: Page, demo_url: str, tmp_path: Path) -> None` — HTTP steps replay against shared or fresh request contexts.
- `test_http_response_capture_feeds_the_next_request(page: Page, demo_url: str, tmp_path: Path) -> None` — Publish a typed response value before the next action is expanded.
- `test_websocket_response_capture_feeds_the_next_action(page: Page, tmp_path: Path) -> None` — Collect socket frames and expose selected JSON as a typed variable.
- `test_network_expectation_timeout_is_reported(page: Page, tmp_path: Path) -> None` — A UI action whose response never matches reports a timeout.
- `test_screenshot_capture_failures_mark_the_step(page: Page, tmp_path: Path) -> None` — Artifact directories that cannot be created fail the step.
- `test_module_entrypoint_runs_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Execute the CLI module with real failed-flow evidence.

### `tools/record/test_flow_runner_actions.py`

Run data, viewport, touch and REST actions in a real Chromium page.

- `class Constants` — Group module-level constants.
  - `page` = `'<p id="label" data-x="attr-value">Hello</p><input id="number" value="42"...`
- `server() -> Iterator[str]` — Run a local HTTP server for REST actions.
- `page() -> Iterator[Page]` — Create a touch-enabled Chromium page holding the fixture markup.
- `test_extract_and_set_variable_actions(page: Page, tmp_path: Path) -> None` — Read typed values from the page and author typed variables.
- `test_viewport_actions_resize_and_rotate(page: Page, tmp_path: Path) -> None` — Resize the viewport, then swap its orientation.
- `test_touch_gestures_reach_the_page(page: Page, tmp_path: Path) -> None` — Dispatch tap, long press, swipe and pinch to one element.
- `test_rest_action_binds_validates_and_records(page: Page, tmp_path: Path, server: str) -> None` — Send a request with bindings and pass every response check.
- `test_rest_action_fails_when_a_check_does_not_hold(page: Page, tmp_path: Path, server: str) -> None` — Report a failing response check as a failed action.
- `test_wait_actions_resolve_every_condition(page: Page, tmp_path: Path) -> None` — Wait for an element, text, a script condition and a plain delay.
- `test_wait_actions_fail_on_bad_conditions(page: Page, tmp_path: Path) -> None` — Fail clearly when a wait is malformed, unsupported or times out.
- `test_binding_reads_through_an_extended_selector(page: Page, tmp_path: Path, server: str) -> None` — Resolve an extended selector binding to exact CSS before reading.
- `test_binding_fails_when_the_extended_selector_matches_nothing(page: Page, tmp_path: Path, server: str) -> None` — Fail the request when its extended selector resolves to nothing.
- `test_flow_inputs_are_variables_from_the_first_action(page: Page, tmp_path: Path) -> None` — Start a run with a typed flow input that actions can read.

### `tools/record/test_flow_runner_selectors.py`

Run actions that use stored selectors, several targets and pacing.

- `class Constants` — Group module-level constants.
  - `minimum_gap_ms` = `120`
  - `html` = `dedent(text='    \n    <button class="b" data-p="2" id="b1">one</button>\...`
  - `buttons` = `SelectorDef(selector_id='sel-b', name='buttons', expression='sort(.b, [da...`
- `page() -> Iterator[Page]` — Create a disposable page with three clickable buttons.
- `test_all_targets_run_in_the_selectors_own_order(page: Page, tmp_path: Path) -> None` — Click every match, ordered by the selector's sort.
- `test_first_target_only_acts_on_the_first_match(page: Page, tmp_path: Path) -> None` — Click only the first element in the selector's order.
- `test_inline_expressions_and_plain_selectors_expand(page: Page, tmp_path: Path) -> None` — Support ``ext=`` expressions and ``all`` on ordinary selectors.
- `test_an_unresolvable_selector_fails_with_a_cause(page: Page, tmp_path: Path) -> None` — Report the count, not a Playwright timeout, when nothing matches.
- `test_unknown_selector_ids_are_reported(page: Page, tmp_path: Path) -> None` — Fail with a clear message for a selector that was deleted.
- `test_tolerated_failures_warn_and_the_flow_continues(page: Page, tmp_path: Path) -> None` — Mark a tolerated failure as a warning and run the next action.
- `test_a_failed_target_skips_the_remaining_targets(page: Page, tmp_path: Path) -> None` — Stop after the first failing target unless failures are tolerated.
- `test_tolerated_target_failures_keep_the_rest_running(page: Page, tmp_path: Path) -> None` — Carry on with later targets when the action tolerates failure.
- `test_pause_between_targets_and_after_the_action(page: Page, tmp_path: Path) -> None` — Wait the configured time between targets.
- `test_record_payload_matches_the_json_contract(page: Page, tmp_path: Path) -> None` — Keep ``cause`` and ``unit`` present, even when empty.

### `tools/record/test_flow_runner_variables.py`

Verify that run variables expand with key and index paths.

- `test_names_with_spaces_expand_whole(tmp_path: Path) -> None` — Expand a whole variable whose name holds a space.
- `test_index_and_key_paths_expand(tmp_path: Path) -> None` — Address a nested value by index then key.
- `test_unresolved_paths_stay_untouched(tmp_path: Path) -> None` — Keep a token whose path does not exist.
- `test_getters_read_a_whole_list_or_dictionary(tmp_path: Path) -> None` — Count, list keys and list values of structured results.
- `test_ask_each_time_answers_fill_actions(tmp_path: Path) -> None` — Substitute per-run answers without touching the saved flow.
- `test_retired_receive_previous_becomes_a_variable(tmp_path: Path) -> None` — Name the earlier result and read it by name after loading an old file.
- `test_flow_inputs_are_saved_and_typed_per_run(tmp_path: Path) -> None` — Save the flow's inputs, then type the answers for one run.
- `test_fixed_capture_ignores_response(tmp_path: Path) -> None` — A fixed capture publishes its stored value, not the response's.
- `test_xml_capture_reads_path(tmp_path: Path) -> None` — An xml capture reads an attribute and converts its type.
- `test_required_path_missing_names_variable(tmp_path: Path) -> None` — A required capture whose path is absent fails with its name.
- `test_optional_path_missing_is_null(tmp_path: Path) -> None` — An optional capture whose path is absent publishes null.

### `tools/record/test_http_request.py`

Verify the shared HTTP sender used by runs and by Studio's Send.

- `api() -> Iterator[APIRequestContext]` — Open an isolated request context.
- `test_send_request_returns_parsed_json(api: APIRequestContext, echo_url: str) -> None` — A JSON response comes back with status, parsed body and timing.
- `test_explicit_cookie_rows_are_sent(api: APIRequestContext, echo_url: str) -> None` — Only enabled cookie rows reach the server.

### `tools/record/test_live_run.py`

Tests for immutable live execution-run accumulation.

- `test_live_run_starts_and_canonical_result_replaces_snapshot() -> None` — Handle test live run starts and canonical result replaces snapshot.

### `tools/record/test_model.py`

Tests for deterministic viewport, targeting, and Flow models.

- `class Constants` — Group module-level constants.
  - `mobile_width` = `390`
  - `mobile_height` = `844`
  - `desktop_width` = `1440`
  - `desktop_height` = `900`
  - `half_width` = `720`
  - `half_height` = `450`
  - `tablet_width` = `1024`
  - `tablet_height` = `1366`
  - `half_scale` = `0.5`
  - `pointer_x` = `20`
  - `pointer_y` = `30`
- `test_viewport_orientation_swaps_only_when_needed() -> None` — Handle test viewport orientation swaps only when needed.
- `test_wait_command_rejects_non_positive_duration() -> None` — Handle test wait command rejects non positive duration.
- `test_viewport_command_contains_mode_size_and_display_scale() -> None` — Handle test viewport command contains mode size and display scale.
- `test_selector_pointer_actions_require_css_selector() -> None` — Handle test selector pointer actions require css selector.
- `test_selector_action_rejects_coordinates() -> None` — Handle test selector action rejects coordinates.
- `test_explicit_position_pointer_accepts_coordinates() -> None` — Handle test explicit position pointer accepts coordinates.
- `test_flow_device_scope_supports_shared_and_selected_modes() -> None` — Handle test flow device scope supports shared and selected modes.
- `test_viewport_rejects_out_of_range_edge() -> None` — Handle test viewport rejects out of range edge.
- `test_passive_response_cannot_own_network_expectation() -> None` — Handle test passive response cannot own network expectation.
- `test_model_validation_rejects_invalid_contract_metadata() -> None` — Exercise validation guards for persisted contract metadata.

### `tools/record/test_model_selectors.py`

Verify selector references, targeting modes and lanes on actions.

- `test_a_selector_reference_satisfies_the_selector_requirement() -> None` — Let ``selector_id`` stand in for the inline selector.
- `test_selector_and_selector_id_are_exclusive() -> None` — Reject an action that names both an inline and a reusable selector.
- `test_position_pointer_cannot_use_a_selector_id() -> None` — Keep coordinate actions free of selectors.
- `test_all_targets_need_a_selector_and_pace_needs_all() -> None` — Allow ``all`` and a pause between targets only with a selector.
- `test_parallel_is_limited_to_free_lane_kinds() -> None` — Allow parallel only for kinds that do not own an input device.
- `test_sandbox_is_for_javascript_only() -> None` — Reject the sandbox flag on other kinds.
- `test_javascript_that_targets_elements_needs_the_sandbox() -> None` — Only the sandbox can hand elements to a script.
- `test_snapshot_needs_a_selector() -> None` — Require a target for snapshot actions.
- `test_lane_of_follows_the_input_device(kind: EventKind, lane: ActionLane) -> None` — Map each kind to the device it occupies.
- `test_contract_pace_and_warning_status_exist() -> None` — Expose the new contract field and run status.

### `tools/record/test_model_validation_extra.py`

Validation-path coverage for immutable domain records.

- `test_small_record_validation_failures() -> None` — Check small record types reject invalid input.
- `test_variable_assertion_and_output_validation() -> None` — Check variable, assertion and output validation rules.
- `test_flow_edge_artifact_and_run_validation() -> None` — Check flow edge, artifact and run validation rules.

### `tools/record/test_persistence_selectors.py`

Verify selectors persist beside the flows, selectors first.

- `test_save_writes_selectors_beside_the_flows(tmp_path: Path) -> None` — Keep selectors out of the flows file and in their own document.
- `test_project_round_trips_through_the_files(tmp_path: Path) -> None` — Reopen a saved project with the same selectors.
- `test_selectors_are_written_before_the_flows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Leave an unused selector, not a dangling reference, after a crash.
- `test_no_selectors_means_no_file_until_one_existed(tmp_path: Path) -> None` — Skip an empty file, but record deletion of the last selector.
- `test_external_edits_to_selectors_are_not_overwritten(tmp_path: Path) -> None` — Refuse to save over a selectors file changed behind Studio's back.
- `test_uploaded_projects_and_exports_carry_selectors(tmp_path: Path) -> None` — Move selectors inside the document when there is no sibling file.
- `test_recovery_keeps_unsaved_selectors(tmp_path: Path) -> None` — Recover selectors together with the unsaved flows.

### `tools/record/test_preview_frames.py`

Prove the live preview keeps only matching frames and acknowledges all.

- `test_only_matching_frames_replace_the_preview_and_all_are_acknowledged(tmp_path: Path) -> None` — Reject stale-size and foreign-page frames without stalling Chromium.

### `tools/record/test_profiles.py`

Validate profile settings and prove Chromium honours every accepted one.

- `test_profile_rejects_features_the_browser_cannot_set(feature: str, message: str) -> None` — Refuse derived, unsupported and unknown media features by name.
- `test_profile_validates_values_ranges_and_identity() -> None` — Reject values outside each setting's semantic range.
- `test_profiles_round_trip_and_legacy_files_get_defaults() -> None` — Persist profiles and fill defaults for projects saved without them.
- `test_field_catalog_covers_every_editable_setting() -> None` — Publish a typed control description for each setting and each choice.
- `test_chromium_honours_every_accepted_media_value() -> None` — Every value the model accepts must change what the page can see.
- `test_chromium_follows_viewport_density_and_touch_settings() -> None` — Typed size, density, screen and input settings reach media queries.
- `test_runner_scopes_a_flow_to_exactly_one_saved_profile() -> None` — Run under a profile only for a flow scoped to one existing profile.
- `test_touch_survives_full_page_screenshots_only_when_restored() -> None` — A full-page capture drops touch input; the emulator puts it back.

### `tools/record/test_project_assets.py`

Verify portable screenshot projects and transactional asset imports.

- `test_project_transfers_between_roots(tmp_path: Path) -> None` — Keep screenshots usable after moving a single exported project file.
- `test_invalid_asset_does_not_replace_project(change: str, tmp_path: Path) -> None` — Reject invalid assets before writing files or changing save metadata.

### `tools/record/test_rebase.py`

Recorded local URLs follow the target; outside addresses never move.

- `test_rebase_url_moves_only_local_addresses(url: str, origin: str | None, expected: str) -> None` — Local URLs move to the target's origin; everything else stays.
- `test_target_origin_follows_mode_and_port() -> None` — An address target and a running service both expose their origin.

### `tools/record/test_record_core.py`

Record exactus findings and normalized report data.

- `class Constants` — Group module-level constants.
  - `click` = `{'type': 'click'}`
- `test_findings_by_mode() -> None` — Failures are errors; empty and partial exports warn.
- `test_report_data_is_normalized() -> None` — ``report_data`` returns summary, scope, findings and extension.
- `test_report_data_skipped_actions() -> None` — Unexported actions become a skipped scope row and a warning.
- `test_record_cli_crawls_and_replays_project(tmp_path: Path, demo_url: str) -> None` — Discovery exports an ordinary project that the CLI can replay.
- `test_record_cli_exports_session_and_replays_program(tmp_path: Path, demo_url: str) -> None` — Captured session input exports portable assets and replay runs Chromium.
- `test_record_cli_studio_and_invalid_setup(tmp_path: Path) -> None` — A bounded real Studio session saves; invalid setup exits before launch.

### `tools/record/test_record_report.py`

RECORD renders result.md from its normalized result.json and template.

- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_golden_result_renders_expected_markdown() -> None` — The checked-in result.json renders the checked-in result.md.
- `test_empty_session_state_why_nothing_is_listed() -> None` — A session without actions or files says N/A and why.
- `test_crash_render_shows_error_and_na_blocks() -> None` — An envelope-only result renders ERROR with N/A tool blocks.
- `test_execute_exactus_renders_record_from_template(tmp_path: Path) -> None` — A real RECORD run writes the normalized report bundle.
- `test_failing_exec_renders_error_report(tmp_path: Path) -> None` — A run that crashes before reporting renders status ERROR.
- `test_crashed_exec_worker_renders_error_report(tmp_path: Path) -> None` — A dead RECORD worker gets the template report with status ERROR.

### `tools/record/test_recorder.py`

Action recording, normalization, compilation and replay.

- `test_locator_compilers(kind: str, extra: dict[str, object], python: str, javascript: str) -> None` — Each locator strategy compiles to both Playwright dialects.
- `test_normalizer_collapses_noise() -> None` — Focus/wheel events drop; repeated fills and dblclicks collapse.
- `test_key_chords() -> None` — Modifiers and aliases render as Playwright chords.
- `class Constants` — Group module-level constants.
  - `min_awaits` = `5`
  - `actions` = `[{'type': 'click', 'target': _target(), 'elapsedMs': 10}, {'type': 'doubl...`
  - `form_html` = `dedent(text='    <!doctype html><html lang="en"><body>\n    <input id="na...`
  - `hover_html` = `dedent(text='    <!doctype html><html lang="en"><body>\n    <header><h1>T...`
- `test_compile_all_actions_and_write(tmp_path: Path) -> None` — Every action kind compiles and programs are written to disk.
- `test_load_actions(tmp_path: Path) -> None` — Only JSON arrays of objects load.
- `form_url(tmp_path: Path) -> Iterator[str]` — Serve a form-rich page on an ephemeral loopback port.
- `hover_url(tmp_path: Path) -> Iterator[str]` — Serve a page mixing inert and effect-producing hover targets.
- `headless(monkeypatch: pytest.MonkeyPatch) -> Installer` — Run recorder/replayer browsers headless and script the session.
- `class Installer` — Callable registering one scripted browser interaction.
  - Fields: `add: Callable[..., None]`
- `test_recorder_preserves_fast_submit_order(form_url: str, tmp_path: Path, headless: Installer) -> None` — Record a debounced fill before the following submit click.
- `test_recorder_form_session(form_url: str, tmp_path: Path, headless: Installer) -> None` — Form interactions are recorded and compiled.
- `test_recorder_hover_filters_inert(hover_url: str, tmp_path: Path, headless: Installer) -> None` — Only hovers that run element-scoped JS or mutate the DOM record.
- `test_recorder_session(demo_url: str, tmp_path: Path, headless: Installer) -> None` — A scripted browser session produces replayable programs.
- `test_replay_session(form_url: str, headless: Installer) -> None` — Recorded programs replay against the live page.
- `test_replayer_locate_strategies(kind: str, extra: dict[str, object], form_url: str, headless: Installer) -> None` — Every locator strategy resolves against a live page.
- `test_exactus_record_cli(demo_url: str, tmp_path: Path, headless: Installer) -> None` — The record tool records, exports to Exactus Record, then replays.
- `test_exactus_record_replay_failures_fail(form_url: str, tmp_path: Path) -> None` — A replayed action that cannot be performed fails the exactus.
- `test_exactus_record_argument_errors(tmp_path: Path) -> None` — A URL is mandatory unless Studio supplies the page.

### `tools/record/test_recorder_protocol.py`

Tests for selector-first recorder NDJSON and playback protocol.

- `class Constants` — Group module-level constants.
  - `wait_ms` = `750`
  - `x` = `10`
  - `y` = `20`
- `test_command_encoder_includes_active_flow() -> None` — Handle test command encoder includes active flow.
- `test_selector_event_accepts_selector_without_coordinates() -> None` — Handle test selector event accepts selector without coordinates.
- `test_selector_event_rejects_coordinate_fallback() -> None` — Handle test selector event rejects coordinate fallback.
- `test_position_pointer_event_accepts_explicit_coordinates() -> None` — Handle test position pointer event accepts explicit coordinates.
- `test_event_decoder_accepts_websocket_keyframe() -> None` — Handle test event decoder accepts websocket keyframe.
- `test_screenshot_message_decodes_record_artifact() -> None` — Handle test screenshot message decodes record artifact.
- `test_expectation_result_message_decodes() -> None` — Handle test expectation result message decodes.
- `test_play_request_contains_flow_actions_and_capture_policy() -> None` — Handle test play request contains flow actions and capture policy.
- `test_event_decoder_rejects_unknown_kind() -> None` — Handle test event decoder rejects unknown kind.
- `test_play_request_serializes_http_post_session_and_expectation() -> None` — Handle HTTP play-request serialization.
- `test_run_started_progress_decodes() -> None` — Handle test run started progress decodes.
- `test_protocol_decodes_terminal_checkpoint_and_progress_variants() -> None` — Decode terminal and progress message variants.
- `test_protocol_encodes_execution_control_messages() -> None` — Encode execution-control messages.
- `test_dispatch_carries_the_projects_selectors() -> None` — Send the stored selectors so the player can resolve them.
- `test_protocol_rejects_malformed_message_shapes() -> None` — Reject malformed protocol messages.
- `test_protocol_scalar_validation_helpers() -> None` — Check the protocol's scalar validation helpers.

### `tools/record/test_recording_groups.py`

Persist recording parents and preserve capture ownership and cadence.

- `test_recording_parent_round_trip() -> None` — An empty parent and its captured children survive saving.
- `test_recording_parent_rename_shift_and_delete() -> None` — Group operations are atomic and keep children tied to their parent.
- `test_capture_clock_pause_resume_and_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Recording starts at zero, ignores pauses and stays pinned to its flow.
- `test_recorded_playback_waits_and_can_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Wait between captured children, but never delay ordinary authored steps.

### `tools/record/test_response_paths.py`

Verify that response values are read by JSON and XML paths.

- `test_json_path_reads_nested_index() -> None` — A dotted path with an index reaches a nested JSON value.
- `test_json_path_missing_returns_none() -> None` — A path that leaves the document yields nothing.
- `test_xml_path_reads_text() -> None` — A 1-based element index selects the matching sibling's text.
- `test_xml_path_reads_attribute() -> None` — A trailing @name step reads an attribute.
- `test_xml_with_dtd_is_rejected() -> None` — A document declaring a DTD is refused before it is parsed.

### `tools/record/test_run_gate.py`

Pause, resume and step a run between actions, in a real Chromium page.

- `class Constants` — Group module-level constants.
  - `wait_seconds` = `20.0`
- `test_a_free_gate_never_blocks_the_runner() -> None` — Return at once, without announcing, while nothing is paused.
- `test_cancellation_releases_a_held_runner() -> None` — Let a stopped run leave the gate instead of waiting forever.
- `test_pause_step_and_resume_hold_a_real_run(tmp_path: Path) -> None` — Start paused, step one action at a time, then run to the end.

### `tools/record/test_selector_conditions.py`

Wait for conditions that read selector probes, and feed connections.

- `class Constants` — Group module-level constants.
  - `minimum_wait_ms` = `250`
  - `html` = `dedent(text='    \n    <p class="row" id="r1">one</p><p class="row" id="r...`
  - `rows` = `SelectorDef(selector_id='sel-rows', name='rows', expression='.row', expec...`
  - `late` = `SelectorDef(selector_id='sel-late', name='late', expression='.late', expe...`
- `page() -> Iterator[Page]` — Create a disposable page with three rows, one hidden.
- `test_probe_references_are_found_once_in_order() -> None` — Read each probe a condition mentions a single time.
- `test_probes_measure_the_page(page: Page) -> None` — Publish count, existence, visibility, text and enabled state.
- `test_a_probe_for_a_missing_selector_is_an_error(page: Page) -> None` — Name the selector that does not exist.
- `test_a_pace_waits_for_a_condition_that_becomes_true(page: Page, tmp_path: Path) -> None` — Hold the next action until an element appears.
- `test_a_condition_that_never_holds_fails_the_gate(page: Page, tmp_path: Path) -> None` — Report a gate timeout and skip what follows.
- `test_a_tolerated_gate_failure_lets_the_flow_continue(page: Page, tmp_path: Path) -> None` — Show a warning and run the next action anyway.
- `test_an_invalid_condition_fails_at_once(page: Page, tmp_path: Path) -> None` — Do not poll for a condition that cannot be evaluated.
- `test_connection_probes_come_back_as_flow_outputs(page: Page, tmp_path: Path) -> None` — Measure what the leaving connections read, when the flow ends.
- `test_edge_probe_names_come_from_the_leaving_connections() -> None` — Ask only for the probes a flow's own connections read.

### `tools/record/test_selector_engine.py`

Verify the ExtendedSelector package engine and its loader.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[4]`
  - `package_files` = `('extended-selector.js', 'extended-selector-editor.js', 'extended-selecto...`
- `test_package_files_match_the_library(name: str) -> None` — Require each runtime resource in the ExtendedSelector package.
- `test_engine_script_is_a_plain_script() -> None` — Publish the engine as one global without module syntax.

### `tools/record/test_selector_resolver.py`

Resolve stored selectors in a real browser page.

- `page() -> Iterator[Page]` — Create a disposable Chromium page showing the selector fixture.
- `test_every_match_gets_css_that_finds_only_it(page: Page) -> None` — Compile each element to a selector Playwright resolves uniquely.
- `test_sort_order_survives_the_round_trip(page: Page) -> None` — Keep the order the expression imposed, element by element.
- `test_stored_selectors_resolve_by_name(page: Page) -> None` — Let one stored selector build on another.
- `test_waits_for_elements_that_appear_late(page: Page) -> None` — Poll until the expected element exists.
- `test_a_wrong_count_is_reported_after_the_timeout(page: Page) -> None` — Explain a count mismatch with the numbers involved.
- `test_failed_checks_name_the_element_and_the_check(page: Page) -> None` — Report which match failed which predicate.
- `test_an_invalid_expression_fails_fast(page: Page) -> None` — Do not poll for an expression that can never evaluate.
- `test_broken_stored_selectors_do_not_break_others(page: Page) -> None` — Report an undefinable selector and carry on.
- `test_shadow_elements_resolve_to_chains(page: Page) -> None` — Anchor elements inside open shadow roots to their hosts.
- `test_the_world_is_rebuilt_after_a_navigation(page: Page) -> None` — Keep working when the page is replaced.
- `test_the_page_is_left_untouched(page: Page) -> None` — Add nothing to the page's globals or DOM.
- `test_pages_with_a_strict_csp_still_resolve(page: Page) -> None` — Run without evaluating strings in the page's own security context.

### `tools/record/test_selector_sandbox.py`

Run snippets in the isolated sandbox, alone and from the flow runner.

- `class Constants` — Group module-level constants.
  - `parallel_budget_s` = `0.5`
  - `html` = `dedent(text='    \n    <p class="card" id="c1">one</p><p class="card" id=...`
  - `cards` = `SelectorDef(selector_id='sel-cards', name='cards', expression='sort(.card...`
- `page() -> Iterator[Page]` — Create a disposable page with three paragraphs.
- `test_document_resolves_stored_selector_names(page: Page) -> None` — Let a snippet use a stored selector without stamping the page.
- `test_snippets_get_the_flow_context(page: Page) -> None` — Expose ids, targets and the current target.
- `test_streams_and_vars_persist_between_snippets(page: Page) -> None` — Keep what a snippet stored and logged for the next one.
- `test_both_snippet_styles_work_and_errors_are_reported(page: Page) -> None` — Accept an expression or a function body, and surface throws.
- `test_the_sandbox_is_separate_from_the_page(page: Page) -> None` — Hide page globals from snippets and snippet globals from the page.
- `test_canonical_exactus_runtime_exposes_context_and_variables(page: Page) -> None` — Expose frozen project, flow, page and device facts to snippets.
- `test_targets_run_at_the_same_time(page: Page) -> None` — Overlap the waits of all targets inside one evaluation.
- `test_sequential_targets_each_run_the_snippet(page: Page, tmp_path: Path) -> None` — Run the snippet once per card, in order, with its own log entries.
- `test_parallel_targets_run_together_and_report_each(page: Page, tmp_path: Path) -> None` — Overlap the targets but still record one result per target.
- `test_a_throwing_snippet_fails_with_a_cause_and_an_error_entry(page: Page, tmp_path: Path) -> None` — Record the failure in both the cause and the error stream.
- `test_streams_are_persisted_on_the_record() -> None` — Round-trip streams through the record codec.

### `tools/record/test_selector_snapshot.py`

Record matched elements as snapshots and warn when they drift.

- `class Constants` — Group module-level constants.
  - `html` = `dedent(text='    \n    <button id="save" class="primary" data-testid="sav...`
  - `save` = `SelectorDef(selector_id='sel-save', name='save', expression='[data-testid...`
- `page() -> Iterator[Page]` — Create a disposable page with a positioned Save button.
- `test_a_snapshot_records_the_element(page: Page, tmp_path: Path) -> None` — Store tag, role, text, box and key attributes.
- `test_a_matching_baseline_is_quiet(page: Page, tmp_path: Path) -> None` — Report no drift when the element still matches its baseline.
- `test_drift_warns_without_failing_the_flow(page: Page, tmp_path: Path) -> None` — Show a warning with the changed fields, and carry on.
- `test_snapshots_of_all_targets_make_one_record_each(page: Page, tmp_path: Path) -> None` — Snapshot every match separately.
- `test_snapshots_need_an_extended_selector_expression(page: Page, tmp_path: Path) -> None` — Explain why a Playwright-only selector cannot be snapshotted.
- `test_evidence_comparison_tolerates_small_box_changes() -> None` — Ignore a few pixels of movement but report a real change.
- `test_a_stored_baseline_is_read_leniently() -> None` — Treat missing or broken baselines as none.

### `tools/record/test_selector_store.py`

Verify selector usage, deletion guard, renaming and dangling references.

- `test_names_are_found_in_expressions_and_conditions() -> None` — Read selector names from expressions and from probe variables.
- `test_usage_counts_actions_selectors_and_conditions() -> None` — Report who depends on each selector.
- `test_delete_is_guarded_unless_forced() -> None` — Refuse to remove a selector that is still in use.
- `test_upsert_replaces_by_identifier_and_keeps_names_unique() -> None` — Edit in place by id, and reject a name another selector holds.
- `test_rename_rewrites_references_and_flags_scripts() -> None` — Rewrite what can be rewritten and report snippets that mention it.

### `tools/record/test_selectors.py`

Verify selector models, pacing and the selectors document codec.

- `test_invalid_selectors_are_rejected(factory: Callable[[], SelectorDef], message: str) -> None` — Reject names, identifiers and counts that cannot be used.
- `test_pace_rejects_unwaitable_values() -> None` — Reject negative durations, tiny polls and blank conditions.
- `test_selector_set_needs_unique_ids_and_names() -> None` — Refuse two selectors that share an identifier or a name.
- `test_document_round_trip_is_atomic_and_stable(tmp_path: Path) -> None` — Write sorted JSON next to the flows and read it back unchanged.
- `test_malformed_documents_are_rejected(document: object) -> None` — Report a clear error instead of loading half a project.
- `test_unreadable_files_are_selector_errors(tmp_path: Path) -> None` — Wrap missing and corrupt files in the selectors error type.
- `test_pace_round_trip_and_defaults() -> None` — Keep every pace field and tolerate a missing pace.

### `tools/record/test_similarity.py`

Perceptual image similarity loading and cache contracts.

- `class Constants` — Group module-level constants.
  - `near_identical` = `0.999`
- `test_load_source_variants(tmp_path: Path) -> None` — Every ``ImageSource`` shape decodes to an RGB image.
- `test_load_rejections(tmp_path: Path) -> None` — Undecodable sources raise ``ValueError``.
- `test_history_and_cache() -> None` — ``remember``/``compare_history`` grow the fingerprint cache.
- `test_compare_scores() -> None` — Identical images score 1.0; distinct colors score lower.
- `test_compare_detailed_breakdown() -> None` — The detailed comparison exposes component scores.

### `tools/record/test_store.py`

Tests for Flow graph state and deterministic persistence.

- `class Constants` — Group module-level constants.
  - `edge_count` = `5`
- `test_flow_graph_allows_branching_and_cycles() -> None` — Handle test flow graph allows branching and cycles.
- `test_flow_graph_rejects_direct_self_loop() -> None` — Handle test flow graph rejects direct self loop.
- `test_event_append_move_and_delete_resequence() -> None` — Handle test event append move and delete resequence.
- `test_place_and_retime_keep_replay_order_and_time_aligned() -> None` — Dropping a step keeps time slots; retiming reorders by time.
- `test_edges_redefine_in_place_and_reorder() -> None` — Transitions can be redefined without moving and then reordered.
- `test_expectation_and_screenshot_round_trip(tmp_path: Path) -> None` — Handle test expectation and screenshot round trip.
- `test_workspace_rejects_unsupported_versions(tmp_path: Path, version: int) -> None` — Reject older formats instead of synthesizing compatibility defaults.
- `test_workspace_v3_comprehensive_round_trip() -> None` — Round-trip contracts, variables, checkpoints, and execution evidence.
- `test_store_mutation_surface_updates_canonical_workspace() -> None` — Exercise editor-facing store mutation operations.
- `test_store_rejects_duplicate_and_missing_references() -> None` — Exercise store duplicate and referential-integrity guards.
- `test_update_flow_rejects_empty_name() -> None` — Check updating a flow to an empty name fails.

### `tools/record/test_store_errors.py`

Workspace loading rejects unreadable, unsupported, and duplicated data.

- `test_load_rejects_unreadable_files(tmp_path: Path) -> None` — Missing files and malformed JSON become ``WorkspaceError``.
- `test_unsupported_version_is_rejected(tmp_path: Path) -> None` — Unknown workspace versions are refused.
- `test_duplicate_flow_ids_are_rejected(tmp_path: Path) -> None` — Two flows with one identifier cannot be loaded.
- `test_duplicate_variable_names_are_rejected(tmp_path: Path) -> None` — Two variables with one name cannot be loaded.
- `test_duplicate_flow_edges_are_rejected() -> None` — Duplicate transitions cannot be imported as an ambiguous graph.

### `tools/record/test_store_selectors.py`

Verify the workspace codec keeps selector fields and run causes.

- `test_old_documents_load_with_defaults() -> None` — Treat a document without the new keys as a plain first-match action.
- `test_selector_fields_round_trip() -> None` — Keep the reference, the targeting mode and both paces.
- `test_invalid_selector_fields_are_workspace_errors(change: dict[str, JsonValue]) -> None` — Report bad targeting data as a workspace error.
- `test_run_records_keep_cause_unit_and_warning_status() -> None` — Round-trip the failure cause and the target position.
- `test_a_half_described_unit_is_rejected() -> None` — Refuse a unit with an index but no count.

### `tools/record/test_studio_action_setup.py`

Verify that an action can be added first and configured afterwards.

- `service(tmp_path: Path) -> StudioService` — Create a Studio service that owns one empty project.
- `test_a_click_without_a_target_is_added_as_incomplete(service: StudioService) -> None` — Keep an unfinished action in the flow instead of refusing it.
- `test_configuring_an_incomplete_action_completes_it(service: StudioService) -> None` — Fill the target in and clear the incomplete state.
- `test_a_navigation_label_follows_its_address_until_renamed(service: StudioService) -> None` — Refresh a generated label, but never overwrite a chosen one.
- `test_a_value_that_is_wrong_not_blank_is_still_refused(service: StudioService) -> None` — Tolerate only blank settings, never an unsupported one.
- `test_a_flow_with_an_unfinished_action_will_not_run(service: StudioService) -> None` — Name the unfinished action instead of running past it.
- `test_only_an_unfinished_action_stores_the_incomplete_flag(service: StudioService) -> None` — Keep saved projects unchanged for every complete action.

### `tools/record/test_studio_boundaries.py`

Cover live-input validation and read-only target inspection boundaries.

- `test_preview_survives_missing_screencast_frames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Seed a real JPEG even when Chromium never sends a screencast frame.
- `class Constants` — Group module-level constants.
  - `ratio_tolerance` = `0.02`
  - `min_frames` = `10`
  - `stale_after_ms` = `3000`
- `jpeg_size(frame: bytes) -> tuple[int, int]` — Read pixel dimensions from a JPEG start-of-frame segment.
- `test_preview_maps_input_after_full_page_screenshot(tmp_path: Path) -> None` — Keep preview geometry and hits correct after a full-page capture.
- `test_target_url_rejects_unsafe_destinations(url: str, message: str) -> None` — Reject unsupported destinations before queuing a browser operation.
- `test_live_input_boundaries(tmp_path: Path) -> None` — Reject invalid input without dispatching it or mutating the document.
- `test_command_guards_reject_invalid_and_busy_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Reject stale revisions, malformed inputs and busy-state operations.
- `test_input_backpressure_is_reported_and_leaves_document_unchanged(tmp_path: Path) -> None` — Report a full worker queue as a retryable conflict, not a failure.
- `test_target_inspection_names_frames_and_survives_detachment() -> None` — Report nested-frame hits with page bounds and tolerate navigation.
- `test_target_inspection_is_read_only() -> None` — Inspect element identities and bounds without dispatching clicks.
- `test_shared_demo_server_survives_another_service_stop(tmp_path: Path) -> None` — Keep a borrowed demo server alive when another Studio exits.
- `test_selected_profile_reaches_the_real_page_and_bad_ones_are_refused(tmp_path: Path) -> None` — Show the target under a saved profile and refuse unusable settings.
- `test_target_is_configured_started_and_opened_through_studio(tmp_path: Path) -> None` — Save a service target, start it, and open the browser on its port.
- `test_a_still_page_never_looks_stale_while_it_is_watched(tmp_path: Path) -> None` — Keep the preview current for a page that does not repaint.
- `test_a_new_project_suggests_the_demo_server_and_start_opens_its_page(tmp_path: Path) -> None` — Offer the demo's own server, start it, and show its page.

### `tools/record/test_studio_duplicate_step.py`

Verify that a step can be duplicated in place.

- `service(tmp_path: Path) -> StudioService` — Create a Studio service that owns one empty project.
- `test_a_duplicate_follows_its_source_with_fresh_ids(service: StudioService) -> None` — Place the copy after the original, with its own identifiers.

### `tools/record/test_studio_entrypoint.py`

Launch the Studio package with a bounded real service lifetime.

- `test_studio_package_cli_stops_cleanly(tmp_path: Path) -> None` — The package CLI starts and stops its owned HTTP and browser worker.
- `test_studio_editor_link_and_shutdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — The launch opens its authorized editor URL and returns a stopped host.
- `test_studio_rejects_invalid_duration(tmp_path: Path, duration: float) -> None` — Invalid lifetimes fail before creating any service resources.
- `test_studio_replaces_previous_package_launcher(tmp_path: Path) -> None` — A second launch gracefully releases the first launch's fixed port.
- `test_studio_preserves_unrelated_listener() -> None` — A busy port must not authorize stopping an unrelated process.
- `test_studio_cli_maps_launch_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Map URL, port, duration and window flags into one launch object.
- `test_the_test_browser_has_no_window_unless_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Run headless by default so the Browser panel is the only view.

### `tools/record/test_studio_http_contract.py`

Verify browser Studio's public HTTP security and mutation contracts.

- `class Reply` — HTTP response observed by a browser client.
  - Fields: `status: int`, `body: bytes`, `headers: dict[str, str]`
- `test_clock_package_assets(service: StudioService, asset: str) -> None` — Serve the clock and demo through the packaged asset allowlist.
- `test_clock_package_asset_allowlist(service: StudioService) -> None` — Do not expose Python package files alongside browser assets.
- `test_clock_module_root_alias(service: StudioService) -> None` — Resolve the module import from both static files and Studio URLs.
- `test_extended_selector_assets_are_served(service: StudioService, asset: str) -> None` — Serve the ExtendedSelector package engine and editor to the Studio page.
- `test_package_projects_are_served_from_the_root_package_folder(service: StudioService) -> None` — Map ``/packages/...`` to the top-level package folder for browser files.
- `service(tmp_path: Path) -> Iterator[StudioService]` — Serve one isolated workspace without opening a target browser.
- `request(service: StudioService, *, path: str, headers: dict[str, str] | None=None, body: JsonValue=None) -> Reply` — Send a real HTTP request to the isolated service.
- `authorized(service: StudioService) -> dict[str, str]` — Bootstrap the same-origin cookie through the public session route.
- `document(reply: Reply) -> dict[str, JsonValue]` — Decode an observed JSON response.
- `test_raw_tab_gets_a_recovery_page_without_weakening_authorization(service: StudioService) -> None` — Explain how to recover when an unauthorized tab opens an API URL.
- `test_every_imported_stylesheet_and_module_is_served(service: StudioService) -> None` — Serve each stylesheet and module the plain Studio URL depends on.
- `test_readiness_assets_and_authorization(service: StudioService) -> None` — Serve public assets while requiring a cookie for workspace data.
- `test_bootstrap_rejects_foreign_origins(service: StudioService, headers: dict[str, str]) -> None` — Reject cross-origin and rebinding attempts even with a valid token.
- `test_duplicate_commands_and_concurrent_tabs(service: StudioService) -> None` — Deduplicate commands while allowing fresh edits from every tab.
- `test_bounded_history_requests_snapshot_after_eviction() -> None` — Retain recent ordered events and flag a client whose history expired.
- `test_invalid_commands_preserve_workspace(service: StudioService, envelope: JsonValue) -> None` — Reject malformed or unsupported requests without changing the workspace.
- `test_import_save_conflict_and_path_boundaries(service: StudioService, tmp_path: Path) -> None` — Save Unicode filenames while protecting imports and external edits.
- `test_command_header_and_payload_boundaries(service: StudioService, changes: dict[str, str], status: int, code: str) -> None` — Reject oversized bodies, incorrect media types and missing identities.
- `test_event_subscription_limit_releases_slots(service: StudioService) -> None` — Bound subscriptions and recover capacity when clients disconnect.
- `edit(*, service: StudioService, headers: dict[str, str], command: str, payload: Mapping[str, JsonValue], status: int=200) -> dict[str, JsonValue]` — Send an edit against the current public revision.
- `test_editor_flow_steps_assertions_and_connections(service: StudioService) -> None` — Save a populated flow, edit its steps and checks, and connect flows.
- `test_invalid_editor_steps_leave_document_unchanged(service: StudioService) -> None` — Validation rejects invalid waits, moves, checks and graph targets.
- `test_editor_persists_websocket_request_configuration(service: StudioService) -> None` — Create an executable socket action with response-variable mappings.
- `test_editor_rejects_non_websocket_session_urls(service: StudioService) -> None` — Reject HTTP URLs before they become WebSocket actions.
- `test_editor_reorders_and_retimes_steps(service: StudioService) -> None` — Steps drop at absolute replay positions and authored times.
- `await_state(*, service: StudioService, key: str, expected: JsonValue) -> dict[str, JsonValue]` — Wait for an asynchronous browser result through public snapshots.
- `test_recording_parent_captures_real_demo_clicks(service: StudioService, demo_url: str) -> None` — Capture actual demo clicks under one parent, including pause/resume.
- `test_managed_browser_record_replay_and_close(service: StudioService, demo_url: str) -> None` — Open a real target, record navigation, replay its flow and close it.
- `test_a_run_pauses_steps_and_resumes_in_a_real_browser(service: StudioService, demo_url: str) -> None` — Step into a run from idle, step again, then let it finish.
- `test_bundled_demo_runs_real_graph_and_retains_evidence(service: StudioService) -> None` — Open the bundled site, execute its graph and save real run evidence.
- `await_operation(*, service: StudioService) -> dict[str, JsonValue]` — Wait for the owned discovery or Actions thread to finish.
- `test_studio_discovers_and_verifies_target(service: StudioService, tmp_path: Path) -> None` — Studio imports discovered flows and runs the saved project as Actions.
- `test_event_stream_delivers_initial_snapshot(service: StudioService) -> None` — The browser event stream starts with an authenticated live snapshot.

### `tools/record/test_studio_projects.py`

Drive the project commands through a real Studio service.

- `service(tmp_path: Path) -> Iterator[StudioService]` — Run an isolated Studio service over an empty library.
- `test_creating_a_project_opens_it_with_unique_names(service: StudioService, tmp_path: Path) -> None` — Create a project in its own folder; refuse a name already in use.
- `test_switching_projects_guards_unsaved_edits(service: StudioService) -> None` — Keep edits safe until the person confirms leaving them.
- `test_details_can_be_edited_and_names_stay_unique(service: StudioService) -> None` — Edit details, split a base address's port, and refuse a taken name.
- `test_duplicate_delete_and_import(service: StudioService) -> None` — Copy, remove and bring in projects; never delete the open one.

### `tools/record/test_studio_selectors.py`

Drive the selector editor commands through a real Studio service.

- `class Constants` — Group module-level constants.
  - `live_timeout_s` = `15`
- `service(tmp_path: Path) -> Iterator[StudioService]` — Run an isolated Studio service with an empty project.
- `test_saving_creates_then_edits_a_selector(service: StudioService) -> None` — Create a selector, then change it and rename it in place.
- `test_names_and_expressions_are_validated(service: StudioService, payload: dict[str, JsonValue], message: str) -> None` — Reject a bad name, a blank expression and a duplicate name.
- `test_an_action_can_use_a_selector_and_its_targeting(service: StudioService) -> None` — Point a step at a stored selector with scope, pacing and tolerance.
- `test_a_selector_in_use_cannot_be_deleted_without_force(service: StudioService) -> None` — Guard deletion, then allow it when forced.
- `test_connection_conditions_are_checked_when_saved(service: StudioService) -> None` — Refuse a connection whose probe names no selector.
- `test_testing_a_selector_in_the_live_page(service: StudioService, demo_url: str) -> None` — Resolve an expression in the real target page and remember the page.

### `tools/record/test_studio_window.py`

Resolve the Studio window setting from CLI flag and pyproject.

- `test_default_is_false(tmp_path: Path) -> None` — No setting and no flag leaves the window disabled.
- `test_pyproject_enables_and_flag_overrides(tmp_path: Path) -> None` — The pyproject value applies unless the CLI flag says otherwise.

### `tools/record/test_target.py`

Cover the application target: its rules, file format and running service.

- `class Constants` — Group module-level constants.
  - `server` = `(executable, '-m', 'http.server', '0', '--bind', '127.0.0.1')`
- `test_url_target_builds_its_address_from_url_and_port() -> None` — Use the port field, default per scheme, and keep the path.
- `test_target_rejects_unusable_settings(fields: _TargetFields, message: str) -> None` — Refuse addresses, ports, commands and folders Studio cannot honour.
- `test_target_round_trips_and_a_typed_port_moves_to_the_port_field() -> None` — Persist the target, default old projects, and accept host:port.
- `test_port_detection_prefers_healthy_local_servers_then_lowest_port() -> None` — Pick the page a person most likely means among several listeners.
- `test_service_starts_detects_its_port_and_stops(tmp_path: Path) -> None` — Start a real server from the project folder and find its port.
- `test_service_honours_a_manually_set_port(tmp_path: Path) -> None` — Wait for the port the user named instead of detecting one.
- `test_service_reports_failures_a_person_can_act_on(tmp_path: Path) -> None` — Explain a missing program, an early exit and unsafe folders.
- `test_check_tells_reachable_closed_and_unknown_addresses_apart(tmp_path: Path) -> None` — Probe an address without starting anything.

### `tools/record/test_v3_execution.py`

Freeze what version-3 flows compute so v4 can prove equivalence.

- `class Constants` — Group module-level constants.
  - `fixture` = `Path(__file__).resolve().parent / 'fixtures' / 'v3' / 'guards-and-chain.p...`
  - `javascript_cases` = `(('sandbox expression', '__EXACTUS_FLOW__.vars.Count + 1', True, 'succeed...`
- `test_guarded_chain_results_are_frozen(tmp_path: Path) -> None` — Run the chain once and compare status, variables and per-action state.
- `test_javascript_paths_are_frozen(tmp_path: Path, case: tuple[str, str, bool, str, int | None]) -> None` — Freeze each JavaScript path: expression, body, page and template.

### `tools/record/test_v3_fixture_builder.py`

Exercise the version-3 fixture regeneration utility.

- `class Constants` — Group module-level constants.
  - `folder` = `Path(__file__).resolve().parent / 'fixtures' / 'v3'`
  - `names` = `('guards-and-chain', 'edges-all-modes', 'variables-all-scopes', 'legacy-r...`
- `test_build_returns_every_fixture() -> None` — Derive the four named fixtures from the demo workspace.
- `test_build_covers_every_edge_mode() -> None` — Emit one edge for each transition mode.
- `test_build_covers_every_variable_scope() -> None` — Emit one variable for each persisted scope.
- `test_build_chains_guarded_events() -> None` — Emit a guarded chain where later events consume earlier results.
- `test_build_keeps_legacy_receive_previous_shape() -> None` — Emit the pre-migration receive-previous event pair.
- `test_canonical_round_trips_through_the_codec() -> None` — Serialize a built fixture to the codec's canonical keys.
- `test_main_writes_the_committed_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Regenerate fixture files identical to the committed ones.

### `tools/record/test_v3_fixtures.py`

Prove the frozen version-3 workspaces load, round-trip and migrate.

- `class Constants` — Group module-level constants.
  - `folder` = `Path(__file__).resolve().parent / 'fixtures' / 'v3'`
  - `canonical` = `('guards-and-chain', 'edges-all-modes', 'variables-all-scopes')`
- `test_canonical_fixture_round_trips(name: str) -> None` — Serialize a canonical fixture back to the very document read.
- `test_edge_modes_are_all_present() -> None` — Keep one edge of every transition mode.
- `test_condition_edge_requires_an_expression() -> None` — Reject a conditional edge that carries no expression.
- `test_variable_scopes_are_all_present() -> None` — Keep one variable of every persisted scope.
- `test_receive_previous_migrates_to_a_named_result() -> None` — Name the earlier result and rewrite the reader's token.

### `tools/record/test_where.py`

Placeholder test module.

- `test_where() -> None` — Hold a placeholder assertion until real cases land.

### `tools/record/test_workspace_actions.py`

Verify current workspace interchange and selector-based actions.

- `class Constants` — Group module-level constants.
  - `min_actions` = `5`
  - `pair` = `2`
  - `studio_src` = `Path(__file__).resolve().parents[4]`
  - `actions` = `[{'type': 'focus'}, {'type': 'click', 'target': {'text': 'Go', **_css(val...`
- `test_css_selector_candidates() -> None` — CSS candidates win; others become attribute selectors.
- `test_actions_become_valid_events() -> None` — Every mapped action yields a schema-valid, ordered event.
- `test_events_roundtrip_to_actions() -> None` — Exported events convert back into replayable actions.
- `test_workspace_files(tmp_path: Path) -> None` — Workspaces are written deterministically and read back.
- `test_exports_load_in_real_flow_studio(tmp_path: Path) -> None` — The bundled Studio's own codec and protocol accept the output.
- `test_invalid_events_rejected(event: fs.Event) -> None` — Targeting invariants are enforced before sending.

### `tools/record/v3_fixture_builder.py`

Write the frozen version-3 workspace fixtures used by migration tests.

- `class Constants` — Group module-level constants.
  - `sourced` = `frozenset({'environment', 'secret'})`
  - `edge_modes` = `('always', 'condition', 'fallback', 'retry', 'finally')`
  - `condition` = `'__EXACTUS_FLOW__.vars.Count > 1'`
- `build(*, base: Document) -> dict[str, Document]` — Derive every frozen fixture from the demo workspace.
- `canonical(*, document: Document) -> Document` — Pass a document through the codec so it holds only canonical keys.
- `main() -> None` — Write fixtures to the folder named by the first argument.

### `tools/reports/__init__.py`

Shared exactus report rendering and delivery.


### `tools/reports/test_report_bundle.py`

Report-bundle validation helpers and fingerprint command plumbing.

- `test_command_output_missing_program() -> None` — An unresolvable program yields an empty fingerprint value.
- `test_validate_payload_missing_keys() -> None` — Payloads lacking required keys raise ``ValueError``.
- `test_validate_payload_markdown_heading() -> None` — Markdown without a level-one heading raises ``ValueError``.
- `test_validate_payload_empty_sections() -> None` — An empty section index raises ``ValueError``.
- `test_validate_payload_web_keys() -> None` — Web metadata missing a representation raises ``ValueError``.
- `test_validate_paths_missing_artifacts(tmp_path: Path) -> None` — Absent deliverables raise ``ValueError``.
- `test_write_emits_web_data_files(tmp_path: Path) -> None` — ``write`` emits ``data.json``/``data.js`` instead of embedding JSON.
- `test_web_data_js_escapes_template_sequences() -> None` — ``${...}`` payload text survives inside a lint-clean document.
- `test_write_compares_findings_with_previous_report(tmp_path: Path) -> None` — A repeated bundle records added, resolved and unchanged findings.
- `test_large_markdown_stays_in_one_file(tmp_path: Path) -> None` — Retain all report text even above the former pagination threshold.
- `test_normalize_markdown_adds_title() -> None` — Bodies without a heading gain the analyzer's report title.
- `test_command_output_failure_paths() -> None` — Failing or silent programs yield an empty fingerprint value.
- `test_fingerprint_reports_environment() -> None` — The fingerprint carries commit, tree, and toolchain identity.
- `test_validate_blocks_missing_block() -> None` — Absent normalized blocks raise ``ValueError``.
- `test_validate_blocks_wrong_types() -> None` — Blocks typed against the contract raise ``ValueError``.
- `test_validate_blocks_finding_keys() -> None` — Findings lacking contract keys raise ``ValueError``.
- `test_link_paths_links_existing_files(tmp_path: Path) -> None` — Backticked project paths become relative Markdown links.
- `test_table_dunder_file_is_one_literal_link(tmp_path: Path) -> None` — A package initializer stays one link with a literal code label.
- `test_artifact_names_stay_plain_and_paths_are_linked(tmp_path: Path) -> None` — Link artifact destinations without linking duplicate name cells.
- `test_link_paths_leaves_non_paths(tmp_path: Path) -> None` — Spans that do not name existing files stay untouched.
- `test_link_paths_leaves_oversized_paths(tmp_path: Path) -> None` — Oversized backticked paths stay untouched instead of aborting reports.
- `test_portable_links_cover_artifacts_and_existing_links(tmp_path: Path) -> None` — Encode local links and preserve fenced examples and external URLs.
- `test_web_link_index_uses_report_base(tmp_path: Path) -> None` — Give nested artifact cells relative links without changing raw paths.
- `test_link_paths_node_fallbacks(tmp_path: Path) -> None` — Nodes without resolvable definitions link without anchors.
- `test_normalize_markdown_variants() -> None` — Empty and headed Markdown normalize to a single document.
- `test_write_records_previous_duration(tmp_path: Path) -> None` — A repeated bundle writes the previous run duration at top level.

### `tools/reports/test_report_js_renderer.py`

The web report's Markdown renderer escapes code and refuses bad links.

- `class Constants` — Group module-level constants.
  - `script` = `Path(__file__).resolve().parents[4] / 'exactus' / 'tools' / 'common' / 't...`
  - `harness` = `dedent(text='    \n    const { readFileSync } = require("node:fs");\n...`
  - `node` = `which(cmd='node')`
  - `spread` = `harness.replace('inputs.map((input) => context.ExactusReport[method](inpu...`
- `render(*, method: str, inputs: list[str]) -> list[str]` — Call one static ``ExactusReport`` renderer on each input.
- `test_tilde_fence_renders_escaped_code() -> None` — ``~~~`` blocks are code: no emphasis, every character escaped.
- `test_backtick_fence_and_longer_closer() -> None` — A fence closes only on the same character, at least as long.
- `test_unclosed_fence_is_closed() -> None` — A fence left open at the end still yields balanced markup.
- `test_javascript_links_stay_text() -> None` — Links with schemes other than http(s) never become anchors.
- `test_markdown_paragraph_link_is_text() -> None` — The block renderer goes through the same link policy.
- `test_safe_links_render() -> None` — http(s), fragment, absolute and relative targets stay links.
- `test_code_span_has_no_inline_markup() -> None` — Code spans are escaped text; emphasis applies outside only.
- `test_code_label_links_remain_clickable() -> None` — Render a normalized source link relative to the nested web directory.
- `test_file_links_encode_reserved_characters() -> None` — Encode spaces, hashes and Unicode in file destinations.
- `test_severity_badge_escapes_label() -> None` — Unknown severities are escaped before reaching the badge.
- `call(*, method: str, arguments: list[object]) -> str` — Call one static ``ExactusReport`` function with several arguments.
- `test_findings_filter_and_group_by_source() -> None` — Several sources add a labelled source filter and one group each.
- `test_single_source_keeps_a_flat_list() -> None` — Findings without several sources get no source filter or groups.
- `test_finding_rows_link_to_their_findings() -> None` — Rows naming a finding link to it and are clickable as a whole.
- `test_prose_lists_render_as_notes() -> None` — Sentences become a note list; glob-like strings stay code chips.
- `test_tool_sections_follow_the_mapping_order() -> None` — Tool sections keep the mapping order recorded in ``view_order``.
- `test_category_filter_pluralizes_its_label() -> None` — A ``Category`` source label reads "All categories" in the filter.
- `test_ranges_compacts_only_runs_of_three() -> None` — Two-line runs stay comma-separated; longer runs become spans.
- `test_anchor_lines_pass_through_unescaped() -> None` — ``<a id>`` marker lines survive; other raw HTML stays escaped.
- `test_diagnostic_callouts_have_distinct_colors() -> None` — Console and server labels remain distinct and escape their messages.

### `tools/reports/test_report_render.py`

Tool templates extend the common template; mappings merge over base.

- `test_packaged_templates_remain_renderable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Render the complete report from templates stored inside a ZIP.
- `test_tool_template_extends_common_template(tmp_path: Path) -> None` — The tool block lands after Artifacts and before the footer.
- `test_tool_mapping_wins_over_base(tmp_path: Path) -> None` — Tool keys replace base keys; other base keys stay.
- `test_missing_tool_mapping_uses_base(tmp_path: Path) -> None` — Without a tool mapping the base mapping applies alone.
- `test_bad_mapping_is_rejected(*, tmp_path: Path, content: str) -> None` — A mapping that is not a JSON object raises ``MappingError``.
- `test_migrated_tools() -> None` — Every tool ships a Markdown template.
- `test_validate_blocks() -> None` — Missing, mistyped and incomplete blocks are rejected.
- `test_unmigrated_tool_keeps_legacy_markdown(tmp_path: Path) -> None` — Run facts do not change an unmigrated tool's stamped report.
- `test_identity_renders_previous_duration(tmp_path: Path) -> None` — The Identity table shows the previous run duration when available.
- `test_fence_markers_in_content_cannot_close_the_fence() -> None` — Error text or commands holding ``~~~~`` stay inside the fence.
- `test_render_adds_a_linked_per_file_resume(tmp_path: Path) -> None` — Findings gain anchors and a per-file resume linking to them.
- `test_render_groups_pathless_findings_as_general(tmp_path: Path) -> None` — A finding without a path lands in a ``(general)`` resume group.

### `tools/reports/test_report_snippets.py`

Migrated tools store finding excerpts in result.json, Markdown and web.

- `class Constants` — Group module-level constants.
  - `marker` = `'# ' + 'noqa'`
  - `util` = `f'"""Helpers."""\n\nfrom pathlib import Path\n\nimport os  {marker}\n\n\n...`
- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_exec_excerpt_follows_context_lines(tmp_path: Path) -> None` — LINTS stores the requested context; Markdown and web carry it.
- `test_context_zero_keeps_the_target_line(tmp_path: Path) -> None` — ``--context-lines 0`` captures the finding line alone.
- `test_lints_and_docs_excerpts_use_default_context(tmp_path: Path) -> None` — LINTS and DOCS capture three lines on each side by default.
- `test_readme_findings_without_lines_get_no_excerpt(tmp_path: Path) -> None` — README findings point at directories or whole files: no excerpt.
- `test_web_bundle_ships_the_snippet_viewer(tmp_path: Path) -> None` — The bundled script renders excerpts with the context controls.

### `tools/reports/test_report_web.py`

The web bundle carries the view model that renders ``result.md``.

- `class Constants` — Group module-level constants.
  - `base_view_keys` = `frozenset({'artifacts', 'blocking', 'environment', 'extension', 'findings...`
  - `data_js_prefix` = `'window.__REPORT_DATA__ = '`
- `quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None` — Run each test inside a throwaway project with a clean environment.
- `test_migrated_web_data_carries_the_markdown_view(tmp_path: Path) -> None` — ``data.js`` inlines the view model ``result.md`` was rendered from.
- `test_columns_follow_first_seen_row_keys() -> None` — Only list-of-object blocks get a column order, in first-seen order.
- `test_unmigrated_web_data_has_no_view(tmp_path: Path) -> None` — An unmigrated tool's web data keeps the legacy shape.
- `test_error_after_report_is_kept(tmp_path: Path) -> None` — A tool raising after writing its report keeps the traceback.
- `test_web_write_failure_keeps_the_normalized_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A failed web data write never lets legacy stamps rewrite result.md.

### `tools/test_self_test.py`

Test self-diagnostic boundaries without running the nested tool suite.

- `test_self_commands_preserve_interpreter_and_import_context(*, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, zipped: bool) -> None` — Source and zipapp probes reuse the correct interpreter and environment.
- `test_pipeline_environment_removes_only_run_scoped_state(monkeypatch: pytest.MonkeyPatch) -> None` — Nested pipelines cannot reuse outer orchestration identities.
- `test_describe_command_reports_process_outcomes(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None` — Distinguish success, nonzero exit, timeout and executable failures.
- `test_tool_probes_use_system_then_bundle(monkeypatch: pytest.MonkeyPatch, source: str) -> None` — Fallback probes preserve their selected source and failure reasons.
- `test_generated_report_requires_fresh_successful_evidence(tmp_path: Path, mode: str) -> None` — Reject stale, malformed or failed reports without masking findings.
- `test_main_writes_real_report_from_controlled_checks(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool) -> None` — Exercise report generation without invoking any diagnostic commands.
- `test_run_checks_orchestrates_boundaries_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None` — Check orchestration decisions using doubles, never a nested pipeline.
- `test_pipeline_probe_builds_scoped_command_and_records_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int) -> None` — Verify pipeline arguments and polling without starting a pipeline.
- `test_stop_process_escalates_only_after_timeout(*, force_kill: bool) -> None` — Reap helpers with terminate before escalating to kill.
- `test_chromium_probe_respects_provider_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str) -> None` — Find browsers only through controlled executable and cache paths.
- `test_browser_candidates_honor_overrides_and_deduplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Honor configured browsers while ignoring absent and duplicate files.
- `test_probe_tools_records_missing_declarations_and_sources(*, monkeypatch: pytest.MonkeyPatch, available: bool) -> None` — Bundle listings refine planned checks without hiding missing tools.
- `test_bundle_listing_uses_its_resolved_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int) -> None` — Parse only successful bundle listings and preserve sorted tool names.
- `test_demo_site_waits_for_readiness_and_kills_failed_start(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ready: bool) -> None` — Bound readiness probing and keep demo assets confined to the fixture.

### `tools/test_tools.py`

Cover the ``exactus.tools`` example-runner ``__main__`` module.

- `class Constants` — Group module-level constants.
  - `entry` = `Path(tools_main.__file__ or '').resolve()`
  - `names` = `('actions', 'common', 'common.templates.markdown', 'record')`
- `test_run_path_bootstrap_augments_import_paths() -> None` — Executing the file outside a package puts the root on the path.
- `test_discover_finds_every_tool_example() -> None` — ``discover`` enumerates the four bundled example packages.
- `test_forms_include_script_only_when_shebang_present() -> None` — The ``script`` form requires a ``run.py`` shebang.
- `test_launch_reports_success_for_each_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A zero exit status maps to ``ok`` for every invocation form.
- `test_launch_reports_failure_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A non-zero exit status maps to ``fail``.
- `test_launch_reports_timeout_and_daemon_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — Hung launches are ``timeout`` unless the example is a daemon.
- `test_show_prints_status_and_failure_log_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — ``show`` prints one line for healthy runs and tails failed logs.
- `test_main_rejects_unknown_names(monkeypatch: pytest.MonkeyPatch) -> None` — Unrecognized example names exit with usage status ``2``.
- `test_main_runs_every_form_and_reports_success(monkeypatch: pytest.MonkeyPatch) -> None` — A healthy sweep launches each form and exits zero.
- `test_main_restricts_to_named_examples(monkeypatch: pytest.MonkeyPatch) -> None` — Name arguments limit the sweep to the selected examples.
- `test_main_returns_one_when_a_form_fails(monkeypatch: pytest.MonkeyPatch) -> None` — A failing example turns the combined status into ``1``.
- `test_main_reports_guard_cleaned_descendants(monkeypatch: pytest.MonkeyPatch) -> None` — Stray descendants cleaned by the guard appear in the summary.

### `tools/visual_cause/__init__.py`

Tests of the visual-cause tool.


### `tools/visual_cause/test_levels.py`

The most severe matching query decides a finding's level.

- `test_default_level_applies_without_matches() -> None` — No match means the configured default decides, with no query.
- `test_most_severe_level_wins() -> None` — Fail outranks warning, which outranks accept.
- `test_narrowest_then_earliest_query_breaks_ties() -> None` — Among equal levels the query matching fewer elements decides.

### `tools/visual_cause/test_pipeline.py`

Visual-cause runs against real pages through Chromium.

- `class Constants` — Group module-level constants.
  - `page` = `'<!doctype html><html><head><meta charset="utf-8"><title>P</title><style>...`
  - `side_a` = `'#box{width:80px;height:40px;background:#08f}'`
  - `side_b` = `'#box{width:120px;height:40px;background:#08f}'`
  - `fast` = `('--viewport', '320x200', '--max-candidates', '5', '--parallel-workers',...`
- `test_session_queries_and_best_selectors(tmp_path: Path) -> None` — A session lints, matches and produces selectors for page elements.
- `test_session_can_drop_native_styles(tmp_path: Path) -> None` — Without native styles the page's own stylesheets are removed.
- `test_run_reports_changed_elements_by_level(tmp_path: Path) -> None` — A stylesheet comparison yields findings decided by the queries.
- `test_run_overlay_directory_css_and_pixel_gate(tmp_path: Path) -> None` — A css-b directory overlays one page; the pixel gate can fail it.
- `test_run_reports_unreadable_sources_as_target_errors(tmp_path: Path) -> None` — A missing stylesheet becomes a failing target-level finding.
- `test_invalid_level_query_raises(tmp_path: Path) -> None` — A level query the engine cannot parse aborts the run.
- `test_main_writes_the_report_bundle(tmp_path: Path) -> None` — The command compares, writes the bundle and returns the gate status.
- `test_main_rejects_bad_arguments_and_queries(tmp_path: Path) -> None` — Invalid targets and queries end the command with a usage error.

### `tools/visual_cause/test_report.py`

The visual-cause report renders findings, counts and evidence.

- `test_data_counts_findings_by_level() -> None` — The payload carries status, per-level counts and the findings.
- `test_markdown_lists_findings_and_evidence() -> None` — The rendered report names findings and embeds the three images.
- `test_markdown_handles_empty_runs() -> None` — A run without targets says so and has no evidence images.

### `tools/visual_cause/test_service.py`

Local page services reuse remote URLs and own the servers they start.

- `class FakeServers` — Record server starts, readiness probes and terminations.
  - `__init__(self, *, ready: bool, reused: bool) -> None` — Configure the outcome of every fake server.
  - `serve(self, *, path: Path, log: Path) -> tuple[int, str, bool]` — Pretend to start a server for one directory.
  - `wait_ready(self, *, url: str, pid: int, timeout: float) -> bool` — Report the configured readiness.
  - `terminate(self, *, pid: int) -> None` — Record one terminated process.
- `test_remote_url_is_used_directly(tmp_path: Path) -> None` — A URL needs no server and has no log.
- `test_missing_and_absent_sources_are_errors(tmp_path: Path) -> None` — Each unusable source raises before any server starts.
- `test_servers_are_shared_per_directory_and_terminated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — One server per directory; exit terminates only owned processes.
- `test_adopted_servers_are_never_terminated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — A reused server stays running when the registry closes.
- `test_server_that_never_becomes_ready_is_stopped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None` — An unready owned server is terminated and reported.

### `tools/visual_cause/test_targets.py`

Visual-cause targets resolve from flags and configuration.

- `test_viewport_parses_and_labels() -> None` — A ``WIDTHxHEIGHT`` string becomes an ordered viewport.
- `test_viewport_rejects_malformed_values(value: str) -> None` — Non-numeric, non-positive and wrongly shaped viewports are errors.
- `test_ad_hoc_stylesheet_target(tmp_path: Path) -> None` — One page with two stylesheets resolves to a stylesheets target.
- `test_default_viewport_and_modes(tmp_path: Path) -> None` — A B page selects page mode; css-b alone selects overlay mode.
- `test_invalid_ad_hoc_options_are_rejected(flags: tuple[str, ...], message: str, tmp_path: Path) -> None` — Contradictory or out-of-range flags raise a descriptive error.
- `test_missing_source_without_configuration(tmp_path: Path) -> None` — Without flags or configuration a target must be provided.
- `test_configured_targets_resolve_by_name(tmp_path: Path) -> None` — Named targets load from pyproject, relative to their file.
- `test_invalid_configured_targets_are_rejected(body: str, error: type[Exception], message: str, tmp_path: Path) -> None` — Each malformed configured field raises a descriptive error.
- `test_unnamed_configured_target_is_rejected(tmp_path: Path) -> None` — A configured entry without a name cannot be addressed.

## JavaScript API reference

Top-level exports, read from the source.

### `standalone/project/web/code.js`

- `add`
- `isEven`
- `sumText`

### `tools/record/js/project-harness.js`

- `settle`
- `summary`
- `makeHost`
- `openDialog`
- `press`
- `type`

## Dependencies and consumers

- Other packages: [`bundle`](../bundle/DOCS.md), [`action_javascript`](../packages/actions/action_javascript/DOCS.md), [`action_pointer`](../packages/actions/action_pointer/DOCS.md), [`action_rest`](../packages/actions/action_rest/DOCS.md), [`all_lints`](../packages/all_lints/DOCS.md), [`argument_parser`](../packages/argument_parser/DOCS.md), [`browser`](../packages/browser/DOCS.md), [`completion`](../packages/completion/DOCS.md), [`exactus_mcp`](../packages/exactus_mcp/DOCS.md), [`extended_selector`](../packages/extended_selector/DOCS.md), [`external`](../packages/external/DOCS.md), [`group_final`](../packages/group_final/DOCS.md), [`guard`](../packages/guard/DOCS.md), [`http_process`](../packages/http_process/DOCS.md), [`markdown`](../packages/markdown/DOCS.md), [`meaningful`](../packages/meaningful/DOCS.md), [`model`](../packages/model/DOCS.md), [`organize`](../packages/organize/DOCS.md), [`package`](../packages/package/DOCS.md), [`patcher`](../packages/patcher/DOCS.md), [`performance`](../packages/performance/DOCS.md), [`pmanager`](../packages/pmanager/DOCS.md), [`project_python`](../packages/project_python/DOCS.md), [`rename_project`](../packages/rename_project/DOCS.md), [`scene_description`](../packages/scene_description/DOCS.md), [`screenshot`](../packages/screenshot/DOCS.md), [`server`](../packages/server/DOCS.md), [`shebang_update`](../packages/shebang_update/DOCS.md), [`steps`](../packages/steps/DOCS.md), [`todo_sync`](../packages/todo_sync/DOCS.md), [`tree`](../packages/tree/DOCS.md), [`visual_cause`](../packages/visual_cause/DOCS.md), [`watch`](../packages/watch/DOCS.md), [`widget_clock`](../packages/widgets/widget_clock/DOCS.md), [`widget_console`](../packages/widgets/widget_console/DOCS.md), [`widget_selector`](../packages/widgets/widget_selector/DOCS.md), [`zip_components`](../packages/zip_components/DOCS.md), [`zstd_portable`](../packages/zstd_portable/DOCS.md), [`actions`](../tools/actions/DOCS.md), [`common`](../tools/common/DOCS.md), [`completion`](../tools/completion/DOCS.md), [`coverage_tests`](../tools/coverage_tests/DOCS.md), [`docs`](../tools/docs/DOCS.md), [`frontend`](../tools/frontend/DOCS.md), [`kwargs_typehints`](../tools/kwargs_typehints/DOCS.md), [`lints`](../tools/lints/DOCS.md), [`performance`](../tools/performance/DOCS.md), [`readme`](../tools/readme/DOCS.md), [`record`](../tools/record/DOCS.md), [`reports`](../tools/reports/DOCS.md), [`self_test`](../tools/self_test/DOCS.md), [`visual_cause`](../tools/visual_cause/DOCS.md)

<!-- exactus:reference:end -->
