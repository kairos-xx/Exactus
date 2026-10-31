# completion/

Grammar-aware shell autocomplete for `exactus`: the engine, the catalog
describing the CLI grammar, the hidden `__complete` wire protocol, shell
adapters and user-level installation.

## How it works

1. A generated shell function intercepts completion and invokes
   `exactus __complete …` with the current words and cursor position.
2. `protocol.py` decodes the request; `engine.py` walks the grammar from
   `catalog.py`/`defaults.py` to find the expected token kind.
3. `providers.py` resolves dynamic candidates (tool names, pipeline
   names, filesystem paths, option values) deterministically.
4. Candidates return over the wire protocol; the shell renders them.

## Invariants

- Completion never mutates project state; `__complete` is read-only.
- Providers must be deterministic and must not import tool execution
  engines — the grammar, not the tools, drives completion.
- Install targets are strictly user-level profile files; nothing writes
  system shell configuration.
- Long options fold `-` and `_` exactly like the shared
  `exactus.packages.argument_parser.ExactusArgumentParser`: `--collect_`
  completes to the registered `--collect-files`, and an already typed
  `--dry_run` counts as using `--dry-run`, so it is not offered twice.
  Candidates always use the registered spelling.
- The catalog introspects each tool's public grammar
  (`tools/<tool>/arguments.py`), so every option declared there — for
  example `kwargs_typehints --python INTERPRETER` — is completable, with
  its help text, without a second hand-written list.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Shell autocomplete engine, catalog, protocol and shell adapters. |
| `__main__.py` | Completion registration CLI for commands embedding this package. |
| `catalog.py` | Completion catalog: the CLI grammar described for the engine. |
| `cli.py` | Completion registration CLI for commands embedding this package. |
| `engine.py` | Grammar-aware word scanner and candidate producer. |
| `examples/` | Runnable demonstration for `exactus/packages/completion/`. |
| `install.py` | User-level completion install, uninstall and diagnosis. |
| `json_types.py` | JSON value types shared by the exactus tools. |
| `launcher.py` | Resolve the launcher baked into generated shell adapters. |
| `model.py` | Typed shell-completion domain values. |
| `profiles.py` | Discover current-user completion profiles across supported shells. |
| `protocol.py` | Hidden ``__complete`` wire protocol. |
| `providers.py` | Dynamic completion providers. |
| `shells.py` | Shell registration-script renderers. |

Run it as a module: `python -m exactus.packages.completion`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `shell` | target shell (or 'all' for management actions) | choices=[shell.value for shell in CompletionShell] + ['all'] |
| `--command` | registered command name the adapters complete for | required=True |
| `--launcher` | executable and fixed arguments the adapters invoke at TAB time (default: this process's invocation) | nargs='+', metavar='TOKEN' |
| `--install` | install the registration into the user-level location | action='store_true' |
| `--uninstall` | remove the command's managed registration content | action='store_true' |
| `--diagnose` | report registration health for the supported shells | action='store_true' |
| `--lints` | Check source style | action='store_true' |
| `--pipeline` | Choose a pipeline |  |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Shell autocomplete engine, catalog, protocol and shell adapters.


### `__main__.py`

Completion registration CLI for commands embedding this package.


### `catalog.py`

Completion catalog: the CLI grammar described for the engine.

- `class ProviderId` — Typed identifier for a dynamic completion provider.
  - `PATH` = `'path'`
  - `DIRECTORY` = `'directory'`
  - `TOOL` = `'tool'`
  - `PIPELINE` = `'pipeline'`
  - `TOOL_ARGUMENT` = `'tool-argument'`
- `class OptionSpec` — One option accepted by a command grammar.
  - `repeatable` = `False`
  - `provider` = `None`
  - `static_values` = `()`
  - `description` = `''`
  - `hidden` = `False`
  - `mutex_group` = `None`
  - `context` = `None`
  - `required` = `False`
  - `canonical_only` = `False`
  - Fields: `names: tuple[str, ...]`, `dest: str`, `cardinality: ValueCardinality`
  - `canonical_name(self) -> str` — Preferred option string for identity checks.
  - `takes_values(self) -> bool` — Whether the option consumes at least one value.
- `class PositionalSpec` — One positional accepted by a command grammar.
  - `provider` = `None`
  - `static_values` = `()`
  - `description` = `''`
  - Fields: `dest: str`, `metavar: str`, `cardinality: ValueCardinality`
- `class CommandSpec` — One command grammar node.
  - `options` = `()`
  - `positionals` = `()`
  - `subcommands` = `()`
  - `hidden` = `False`
  - Fields: `name: str`, `description: str`
  - `option_named(self, *, word: str) -> OptionSpec | None` — Return the option named ``word``, folding ``-`` and ``_``.
  - `subcommand_named(self, *, word: str) -> CommandSpec | None` — Return the visible subcommand named ``word``.
- `class CompletionCatalog` — The whole CLI grammar reachable during completion.
  - Fields: `root: CommandSpec`, `contexts: tuple[CommandSpec, ...]`
  - `context_named(self, *, name: str) -> CommandSpec | None` — Return the grammar context registered as ``name``.
- `class Constants` — Group module-level constants.
  - `repeatable_actions` = `frozenset(('_AppendAction', '_AppendConstAction', '_CountAction', '_Exten...`
  - `nargs_cardinality` = `{0: _GroupFinalConstants.no_value, None: _GroupFinalConstants_2.one_value...`
  - `directory_dests` = `frozenset(('root', 'output_dir', 'server'))`
  - `path_metavars` = `frozenset(('FILE', 'PATH'))`
  - `name_providers` = `{'tools': ProviderId.TOOL, 'exclude_tools': ProviderId.TOOL, 'clear': Pro...`
- `spec_from_parser(*, name: str, description: str, parser: ArgumentParser, providers: dict[str, ProviderId] | None=None) -> CommandSpec` — Convert an ``ArgumentParser`` into a :class:`CommandSpec`.
- `completion_command_spec() -> CommandSpec` — Return the public ``completion`` command grammar.
- `merge_specs(*, name: str, description: str, specs: tuple[CommandSpec, ...], extra_options: tuple[OptionSpec, ...]=()) -> CommandSpec` — Combine several grammars into one, first declaration winning.

### `cli.py`

Completion registration CLI for commands embedding this package.

- `create_parser() -> ArgumentParser` — Build the argument parser for the completion command.
- `run(*, arguments: Sequence[str], out: TextIO | None=None, home: Path | None=None) -> int` — Run the completion command.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run the CLI with explicit tokens or the process arguments.

### `engine.py`

Grammar-aware word scanner and candidate producer.

- `class Constants` — Group module-level constants.
  - `max_candidates` = `500`
  - `max_description` = `200`
  - `provider_errors` = `(OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, Ru...`
  - `negative_number` = `'-\\d+(\\.\\d+)?'`
  - `kind_order` = `{CompletionKind.COMMAND: 0, CompletionKind.OPTION: 1, CompletionKind.VALU...`
- `class ScanState` — Committed CLI state after scanning completed tokens.
  - `options_enabled` = `True`
  - `pending` = `None`
  - `pending_consumed` = `0`
  - `positional_index` = `0`
  - `positional_consumed` = `0`
  - `used` = `frozenset()`
  - `used_groups` = `frozenset()`
  - `flags` = `frozenset()`
  - `values` = `()`
  - `multi_values` = `()`
  - `positionals` = `()`
  - `command_path` = `()`
  - Fields: `command: CommandSpec`
  - `recognized(self) -> RecognizedArguments` — Render the scanner's accumulators as recognized arguments.
- `class CompletionEngine` — Turn a shell's completion request into candidates.
  - `__init__(self, *, catalog: CompletionCatalog, providers: dict[ProviderId, CompletionProvider], working_directory: Path, command_name: str) -> None` — Initialize the engine.
  - `complete(self, *, request: CompletionRequest) -> tuple[CompletionCandidate, ...]` — Produce candidates for one completion request.
  - `scan(self, *, tokens: tuple[str, ...]) -> ScanState` — Replay completed tokens into committed grammar state.

### `examples/__init__.py`

Provide runnable shell completion examples.


### `examples/__main__.py`

Run the completion example with the project virtual environment.


### `examples/run.py`

Complete a standalone command without importing any exactus tools.

- `main() -> int` — Show flag and pipeline candidates from an application-owned grammar.

### `install.py`

User-level completion install, uninstall and diagnosis.

- `class Constants` — Group module-level constants.
  - `protocol_marker` = `'# Completion protocol:'`
- `class ShellInstallKind` — How a shell consumes its registration script.
  - `PROVIDER_FILE` = `'provider-file'`
  - `PROFILE_BLOCK` = `'profile-block'`
- `class InstallStatus` — Health of one shell's completion registration.
  - `HEALTHY` = `'healthy'`
  - `MISSING` = `'missing'`
  - `STALE` = `'stale'`
  - `BROKEN` = `'broken'`
  - `LAUNCHER_MISSING` = `'launcher-missing'`
- `class ShellDiagnosis` — Diagnostic result for one shell.
  - Fields: `shell: CompletionShell`, `status: InstallStatus`, `path: Path`, `detail: str`
- `class InstallResult` — Outcome of an install or uninstall operation.
  - Fields: `shell: CompletionShell`, `status: InstallStatus`, `path: Path`, `changed: bool`, `detail: str`
- `class Registration` — Describe a startup registration destination and bundle revision.
  - `aliases` = `()`
  - Fields: `path: Path`, `revision: str`
- `install(*, shell: CompletionShell, command_name: str, launcher: tuple[str, ...], home: Path, registration: Registration | None=None) -> InstallResult` — Install or refresh one shell's registration.
- `uninstall(*, shell: CompletionShell, home: Path, command_name: str, profile: Path | None=None) -> InstallResult` — Remove one shell's command-owned registration.
- `diagnose(*, launcher: tuple[str, ...], home: Path, command_name: str) -> tuple[ShellDiagnosis, ...]` — Diagnose registration health for every supported shell.

### `json_types.py`

JSON value types shared by the exactus tools.

- `class JsonDict` — Dictionary with a formatted JSON representation.
  - `tojson(self) -> str` — Formatted JSON serialization of this dictionary.

### `launcher.py`

Resolve the launcher baked into generated shell adapters.

- `resolve_launcher(*, command_name: str) -> tuple[str, ...]` — Resolve the executable the current process was invoked as.
- `is_zipapp(*, path: Path) -> bool` — Return whether an executable is a Python zipapp.

### `model.py`

Typed shell-completion domain values.

- `class CompletionShell` — Interactive shells with a generated registration adapter.
  - `BASH` = `'bash'`
  - `ZSH` = `'zsh'`
  - `FISH` = `'fish'`
  - `POWERSHELL` = `'powershell'`
- `class CompletionKind` — Semantic kind of a completion candidate.
  - `COMMAND` = `'command'`
  - `OPTION` = `'option'`
  - `VALUE` = `'value'`
  - `FILE` = `'file'`
  - `DIRECTORY` = `'directory'`
- `class CandidateFlag` — Wire-protocol bit flags describing one candidate.
  - `NONE` = `0`
  - `APPEND_SPACE` = `1`
  - `PATH` = `2`
  - `DIRECTORY` = `4`
  - `DEPRECATED` = `8`
- `class CompletionCandidate` — One value the shell may insert.
  - Fields: `value: str`, `display: str`, `description: str`, `kind: CompletionKind`, `append_space: bool`
  - `flags(self) -> int` — Encode this candidate's metadata as wire flags.
- `class CompletionRequest` — Normalized command-line state supplied by a shell adapter.
  - `protocol_version` = `1`
  - Fields: `shell: CompletionShell`, `words: tuple[str, ...]`, `active_word_index: int`, `prefix: str`
- `class RecognizedArguments` — Arguments the scanner already committed before the cursor.
  - Fields: `flags: frozenset[str]`, `values: tuple[tuple[str, str], ...]`, `multi_values: tuple[tuple[str, tuple[str, ...]], ...]`, `positionals: tuple[str, ...]`, `command_path: tuple[str, ...]`
  - `get_one(self, *, dest: str) -> str | None` — Return the last recorded single value for ``dest``.
  - `get_many(self, *, dest: str) -> tuple[str, ...]` — Return every recorded value for ``dest``.
  - `has_flag(self, *, dest: str) -> bool` — Return whether a valueless option was supplied.
- `class CompletionContext` — Context exposed to dynamic candidate providers.
  - Fields: `command_path: tuple[str, ...]`, `words: tuple[str, ...]`, `prefix: str`, `recognized: RecognizedArguments`, `working_directory: Path`
- `class CompletionProvider(Protocol)` — Contract implemented by dynamic completion providers.
  - `complete(self, *, context: CompletionContext) -> tuple[CompletionCandidate, ...]` — Return completion candidates for the supplied context.
- `class ValueCardinality` — Minimum and maximum values one argument consumes.
  - `consumes_remainder` = `False`
  - Fields: `minimum: int`, `maximum: int | None`
  - `satisfied(self, *, consumed: int) -> bool` — Return whether ``consumed`` values meet the minimum.
  - `accepts_more(self, *, consumed: int) -> bool` — Return whether the argument accepts another value.
- `class Constants` — Group module-level constants.
  - `field_separator` = `'\x1f'`
  - `no_value` = `ValueCardinality(minimum=0, maximum=0)`
  - `one_value` = `ValueCardinality(minimum=1, maximum=1)`
  - `optional_value` = `ValueCardinality(minimum=0, maximum=1)`
  - `any_values` = `ValueCardinality(minimum=0, maximum=None)`
  - `at_least_one` = `ValueCardinality(minimum=1, maximum=None)`

### `profiles.py`

Discover current-user completion profiles across supported shells.

- `profile_paths(*, home: Path, command_name: str) -> tuple[tuple[CompletionShell, Path], ...]` — Find supported user profiles without changing login-file precedence.

### `protocol.py`

Hidden ``__complete`` wire protocol.

- `class Constants` — Group module-level constants.
  - `exit_ok` = `0`
  - `exit_malformed` = `2`
  - `exit_unsupported_shell` = `3`
  - `exit_catalog_failure` = `4`
  - `exit_engine_failure` = `5`
  - `rejected` = `frozenset((chr(value) for value in (*range(32), *range(127, 160))))`
  - `protocol_version` = `1`
  - `max_words` = `1024`
  - `max_input` = `1 << 20`
  - `max_record` = `16 * 1024`
  - `debug_variable` = `'EXACTUS_COMPLETION_DEBUG'`
  - `provider_errors` = `(OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, Ru...`
- `class ParsedRequest` — Outcome of parsing the hidden request arguments.
  - Fields: `request: CompletionRequest | None`, `status: int`, `message: str`
- `parse_request(*, arguments: Sequence[str]) -> ParsedRequest` — Parse hidden-protocol arguments into a request.
- `render_record(*, candidate: CompletionCandidate) -> str | None` — Encode one candidate as a wire-protocol line.
- `run_completion(*, arguments: Sequence[str], catalog: CompletionCatalog, providers: dict[ProviderId, CompletionProvider] | None=None, out: TextIO | None=None, command_name: str='exactus') -> int` — Run the hidden completion endpoint.

### `providers.py`

Dynamic completion providers.

- `class Constants` — Group module-level constants.
  - `max_directory_entries` = `4096`
  - `max_path_candidates` = `500`
  - `path_budget_seconds` = `0.1`
- `class PathCompletionProvider` — Complete files and directories one level at a time.
  - `directories_only` = `False`
  - `complete(self, *, context: CompletionContext) -> tuple[CompletionCandidate, ...]` — Return immediate children matching the current prefix.
- `class StaticNameProvider` — Complete names from an immutable local snapshot.
  - Fields: `entries: tuple[tuple[str, str], ...]`
  - `complete(self, *, context: CompletionContext) -> tuple[CompletionCandidate, ...]` — Return snapshot names beginning with the prefix.
- `class ScopedArgumentProvider` — Complete ``NAME::`` prefixes for ``--tool-arg`` values.
  - Fields: `names: tuple[str, ...]`
  - `complete(self, *, context: CompletionContext) -> tuple[CompletionCandidate, ...]` — Return ``name::`` candidates matching the prefix.
- `default_providers(*, tools: Iterable[tuple[str, str]]=(), pipelines: Iterable[tuple[str, str]]=()) -> dict[ProviderId, CompletionProvider]` — Construct the provider registry for one completion run.

### `shells.py`

Shell registration-script renderers.

- `render_bash(*, command_name: str, launcher: tuple[str, ...]) -> str` — Render the Bash registration script.
- `render_zsh(*, command_name: str, launcher: tuple[str, ...]) -> str` — Render the Zsh registration script.
- `render_fish(*, command_name: str, launcher: tuple[str, ...]) -> str` — Render the Fish registration script.
- `render_powershell(*, command_name: str, launcher: tuple[str, ...]) -> str` — Render the PowerShell registration script.
- `render(*, shell: CompletionShell, command_name: str, launcher: tuple[str, ...]) -> str` — Dispatch to the shell-specific renderer.

## Examples

Runnable demonstration for `exactus/packages/completion/`.

Complete a standalone command without importing any exactus tools.

```bash
python -m exactus.packages.completion.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`argument_parser`](../argument_parser/DOCS.md)
- Used by: `__main__.py`, `packages/package/install.py`, `tests/packages/completion/test_catalog.py`, `tests/packages/completion/test_engine.py`, `tests/packages/completion/test_examples.py`, `tests/packages/completion/test_main.py`, `tests/packages/completion/test_protocol.py`, `tests/packages/completion/test_providers.py`, `tests/packages/completion/test_shells.py`, `tests/packages/package/test_package_install.py`, `tests/tools/completion/test_integration.py`, `tests/tools/completion/test_startup.py`, `tools/completion/defaults.py`, `tools/completion/main.py`, `tools/completion/startup.py`

## Tests

Tests live in `exactus/tests/packages/completion/`.

- `test_catalog.py` — Coverage for parser introspection in ``exactus/completion/catalog``. (12 tests)
  - `test_catalog_context_lookup`
  - `test_completion_command_spec_exposes_shells`
  - `test_long_names_lead_canonical_order`
  - `test_merge_specs_combines_options`
  - `test_provider_inference_by_metavar_and_type`
  - `test_provider_overrides_win`
  - `test_spec_from_parser_collects_choices`
  - `test_spec_from_parser_hides_suppressed_options`
  - `test_spec_from_parser_maps_cardinalities`
  - `test_spec_from_parser_marks_mutex_groups`
  - `test_spec_from_parser_positionals`
  - `test_spec_from_parser_repeatable_append`
- `test_engine.py` — Decision-tree coverage for :class:`CompletionEngine`. (23 tests)
  - `test_candidates_sorted_by_kind_then_value`
  - `test_canonical_only_offers_long_name`
  - `test_dispatch_option_switches_context`
  - `test_double_dash_disables_options`
  - `test_greedy_option_keeps_collecting`
  - `test_hidden_option_never_offered`
  - `test_inline_value_completion`
  - `test_long_options_filtered_by_prefix`
  - `test_mutex_group_suppresses_sibling`
  - `test_negative_number_is_a_value`
  - `test_option_prefix_interrupts_satisfied_pending`
  - `test_option_value_choices`
  - `test_positional_provider_used_inside_subcommand`
  - `test_repeat_values_exclude_consumed`
  - `test_repeatable_option_reoffered`
  - `test_root_offers_subcommands_and_positionals`
  - `test_short_cluster_consumes_flags`
  - `test_short_option_attached_value`
  - `test_subcommand_switches_context`
  - `test_underscore_prefix_offers_the_dashed_option`
  - `test_underscore_spelling_counts_as_a_used_option`
  - `test_used_non_repeatable_option_suppressed`
  - `test_warm_static_completion_latency`
- `test_examples.py` — Run the public completion example against the standalone grammar. (1 tests)
  - `test_completion_example`
- `test_main.py` — Cover the ``exactus.packages.completion`` command-line entry point. (6 tests)
  - `test_bootstrap_imports_standalone`
  - `test_main_accepts_explicit_arguments`
  - `test_run_diagnose_reports_missing_registrations`
  - `test_run_diagnose_requires_all_shells`
  - `test_run_install_and_uninstall_manage_profiles`
  - `test_run_rejects_conflicting_actions`
- `test_protocol.py` — Wire-protocol coverage for ``__complete`` parsing and records. (18 tests)
  - `test_parse_accepts_empty_and_dash_words`
  - `test_parse_enforces_input_limit`
  - `test_parse_enforces_word_limit`
  - `test_parse_rejects_bad_index`
  - `test_parse_rejects_bare_argument`
  - `test_parse_rejects_missing_shell`
  - `test_parse_rejects_protocol_mismatch`
  - `test_parse_rejects_unknown_argument`
  - `test_parse_rejects_unknown_shell`
  - `test_parse_valid_request`
  - `test_protocol_limits_count_utf8_bytes`
  - `test_protocol_rejects_invalid_text`
  - `test_render_record_enforces_size_limit`
  - `test_render_record_fields`
  - `test_render_record_rejects_control_characters`
  - `test_run_completion_engine_failure`
  - `test_run_completion_malformed_writes_nothing`
  - `test_run_completion_writes_only_records`
- `test_providers.py` — Coverage for the dynamic completion providers. (16 tests)
  - `test_default_providers_cover_every_id`
  - `test_default_tool_provider_uses_supplied_tools`
  - `test_directory_candidates_do_not_append_space`
  - `test_directory_provider_suppresses_files`
  - `test_path_provider_absolute_prefix`
  - `test_path_provider_caps_results`
  - `test_path_provider_filters_by_name_prefix`
  - `test_path_provider_hides_dotfiles`
  - `test_path_provider_lists_children`
  - `test_path_provider_missing_directory_is_empty`
  - `test_path_provider_preserves_relative_base`
  - `test_path_provider_stops_at_deadline`
  - `test_path_provider_stops_at_entry_budget`
  - `test_scoped_argument_provider`
  - `test_split_prefix_shapes`
  - `test_static_name_provider_prefixes`
- `test_shells.py` — Coverage for the shell registration-script renderers. (12 tests)
  - `test_bash_script_shape`
  - `test_fish_script_shape`
  - `test_function_name_sanitizes`
  - `test_generated_bash_is_syntactically_valid`
  - `test_generated_fish_is_syntactically_valid`
  - `test_generated_zsh_is_syntactically_valid`
  - `test_launcher_embedded_in_scripts`
  - `test_powershell_script_shape`
  - `test_powershell_uses_cursor_and_logical_words`
  - `test_render_dispatches_every_shell`
  - `test_scripts_are_deterministic`
  - `test_zsh_script_shape`

<!-- exactus:reference:end -->
