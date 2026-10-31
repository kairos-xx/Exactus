# completion/

Exactus-specific shell-completion wiring on top of
`exactus/packages/completion`.

## Files

| File | Description |
|---|---|
| `defaults.py` | Maps the real `exactus` parser grammars to providers through a structural protocol, without importing the application. |
| `main.py` | `exactus completion` command: prints the shell registration script, or installs, removes and diagnoses user-level registration. |
| `startup.py` | Installs portable-launcher completion and refreshes changed bundles. |

## Behavior

- Completion logic (grammars, providers, shell generators) lives in
  `exactus/packages/completion`; this package only wires Exactus' own parsers and
  commands into it.
- Supported shells register through the printed script or the installer;
  diagnostics report registration state per shell.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Provide Exactus-specific wiring over the completion package. |
| `defaults.py` | Wire the real ``exactus`` grammars into a completion catalog. |
| `main.py` | User-facing ``exactus completion`` command. |
| `startup.py` | Install portable-launcher completion and refresh changed bundles. |

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `shell` | target shell (or 'all' for management actions) | choices=[shell.value for shell in CompletionShell] + ['all'] |
| `--install` | install the registration into the user-level location | action='store_true' |
| `--uninstall` | remove exactus-owned registration content | action='store_true' |
| `--diagnose` | report registration health for the supported shells | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Provide Exactus-specific wiring over the completion package.


### `defaults.py`

Wire the real ``exactus`` grammars into a completion catalog.

- `class Tool(Protocol)` — Describe a dispatch tool supplied by the calling application.
  - `name(self) -> str` — Canonical tool identifier.
  - `flags(self) -> tuple[str, ...]` — Accepted dispatch flags.
  - `parser(self) -> ArgumentParser` — The application's argument parser.
- `class Constants` — Group module-level constants.
  - `common_providers` = `{'root': ProviderId.DIRECTORY, 'output_dir': ProviderId.DIRECTORY, 'sourc...`
  - `tool_descriptions` = `{'lints': 'Clean, lint, and type-check sources', 'coverage_tests': 'Run t...`
- `check_catalog(*, tools: tuple[Tool, ...], orchestrator_parser: ArgumentParser) -> CompletionCatalog` — Assemble the ``exactus`` completion catalog.

### `main.py`

User-facing ``exactus completion`` command.

- `class Constants` — Group module-level constants.
  - `command_name` = `'exactus'`
- `create_parser() -> ArgumentParser` — Build the argument parser for the completion command.
- `run(*, arguments: Sequence[str], out: TextIO | None=None, home: Path | None=None) -> int` — Run the completion command.

### `startup.py`

Install portable-launcher completion and refresh changed bundles.

- `ensure_completion(*, home: Path | None=None) -> None` — Refresh user completion on ordinary portable-launcher invocations.

## Dependencies and consumers

- Other packages: [`argument_parser`](../../packages/argument_parser/DOCS.md), [`completion`](../../packages/completion/DOCS.md)
- Used by: `__main__.py`, `tests/tools/completion/test_integration.py`, `tests/tools/completion/test_startup.py`

## Tests

Tests live in `exactus/tests/tools/completion/`.

- `test_integration.py` — End-to-end coverage against the real ``check`` catalog. (29 tests)
  - `test_aliases_not_offered_but_matchable`
  - `test_canonical_registration_markers`
  - `test_check_main_routes_complete`
  - `test_check_main_routes_completion_command`
  - `test_completion_command_at_root`
  - `test_completion_command_install_action`
  - `test_completion_command_prints_script`
  - `test_completion_launch_needs_only_standard_library`
  - `test_completion_subcommand_offers_shells`
  - `test_default_tool_provider_uses_exactus_catalog`
  - `test_diagnose_command_output`
  - `test_diagnose_missing_and_healthy`
  - `test_diagnose_missing_launcher`
  - `test_diagnose_stale_protocol`
  - `test_dispatch_flag_switches_to_tool_grammar`
  - `test_install_and_uninstall_bash`
  - `test_install_idempotent_replaces_block`
  - `test_install_refuses_foreign_file`
  - `test_install_zsh_ensures_compinit`
  - `test_launcher_resolution_covers_module_script_and_path_lookup`
  - `test_pipeline_values`
  - `test_powershell_profile_block_lifecycle`
  - `test_remaining_tool_values`
  - `test_root_offers_dispatch_and_orchestrator_flags`
  - `test_root_values_complete_directories`
  - `test_screenshot_shortcut_merges_grammars`
  - `test_tool_values_after_tools_flag`
  - `test_tools_pipeline_mutex`
  - `test_uninstall_refuses_foreign_file`
- `test_startup.py` — Verify automatic completion without touching real user profiles. (5 tests)
  - `test_first_run_refresh_and_noop`
  - `test_foreign_and_broken_profiles_survive`
  - `test_management_removes_automatic_profiles`
  - `test_powershell_discovers_redirected_all_host_profiles`
  - `test_source_invocation_does_not_install`

<!-- exactus:reference:end -->
