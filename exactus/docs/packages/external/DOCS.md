# packages/external/

Bundled-toolchain listing and dispatch, exposed as `exactus --external`.

## Files

| File | Description |
|---|---|
| `cli.py` | `exactus --external` prints the bundled toolchain grouped by runtime — OS payloads and binary tools, Python packages, and Node packages — with the versions recorded in the leaf manifest. `exactus --external TOOL [ARGS...]` forwards the command line to the bundle's partition launcher, which materializes the component and runs the tool under the executable's own interpreter. |
| `__main__.py` | Module entry point: executes the external bundled-tool CLI (`python -m exactus.packages.external`). |

## Behavior

- `resolve_exactus_tool_bundle` locates the host bundle leaf; when no
  bundle or manifest is available the command reports that instead of
  guessing at a toolchain.
- Dispatch materializes only the requested component through the
  partition launcher, so a cold run unpacks a single pack rather than
  the whole toolchain.
- Listing reads the leaf manifest recorded at bundle time, so reported
  versions always match the payloads the executable actually carries.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Bundled-toolchain inventory and dispatch for ``exactus --external``. |
| `__main__.py` | Execute the external bundled-tool command-line interface. |
| `cli.py` | List and dispatch the tools bundled inside an exactus executable. |

Run it as a module: `python -m exactus.packages.external`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Bundled-toolchain inventory and dispatch for ``exactus --external``.


### `__main__.py`

Execute the external bundled-tool command-line interface.


### `cli.py`

List and dispatch the tools bundled inside an exactus executable.

- `class Constants` — Group module-level constants.
  - `manifest_name` = `'data/bundle.json'`
  - `launcher_commands` = `frozenset({'--apply-update', '--help', '--list', '--list-tools', '--rollb...`
  - `no_bundle` = `'ERROR: no compatible bundled toolchain is available'`
  - `no_manifest` = `'ERROR: bundled manifest is unavailable'`
- `inventory_text(*, document: JsonValue | None) -> str` — Render the manifest inventory grouped by runtime.
- `run(*, arguments: Sequence[str] | None=None) -> int` — List the bundled toolchain or forward a command line to it.
- `main(*, arguments: Sequence[str] | None=None) -> NoReturn` — Run the CLI and terminate with its exit status.

## Dependencies and consumers

- Other packages: [`common`](../../tools/common/DOCS.md)
- Used by: `__main__.py`, `tests/packages/external/test_cli.py`

## Tests

Tests live in `exactus/tests/packages/external/`.

- `test_cli.py` — Drive ``exactus --external`` inventory and dispatch in-process. (11 tests)
  - `test_dispatch_forwards_command_line`
  - `test_dispatch_status_passthrough`
  - `test_inventory_groups_versions`
  - `test_launcher_meta_commands_dispatch`
  - `test_main_routes_external_flag`
  - `test_missing_manifest_defers_to_launcher`
  - `test_missing_manifest_lists_error`
  - `test_missing_tool_errors`
  - `test_no_bundle_errors`
  - `test_real_bundle_lists_tools`
  - `test_real_bundle_runs_tool`

<!-- exactus:reference:end -->
