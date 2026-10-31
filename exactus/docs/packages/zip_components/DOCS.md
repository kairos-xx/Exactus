# `exactus/packages/zip_components/` — source-bundle archives

`exactus.packages.zip_components` packages one or more exactus tools and/or packages
packages into a single `.zip` whose members keep their
repository-relative paths. Extracting with `unzip -o <name>.zip -d .`
at a repository root drops every file back where it belongs.

## Running

```bash
python exactus/packages/zip_components --tools lints docs
python -m exactus.packages.zip_components --packages all_lints browser
python exactus/packages/zip_components all_lints browser   # positional = --packages
python exactus/packages/zip_components --packages '*'        # every packages package
python exactus/packages/zip_components '*'                 # every component, both kinds
```

Positional names are shorthand for `--packages`; the token `all` (or a
quoted `*`) expands to every component of its kind, and a positional
`all`/`*` alone selects **both** kinds — identical to
`--packages all --tools all`.

Both kinds may be combined; the archive name is derived from the
**requested** components in request order:

| Command | Archive |
|---------|---------|
| `--tools lints docs` | `exactus_lints_docs.zip` |
| `--packages all_lints browser` | `packages_all_lints_browser.zip` |
| `all_lints browser` (positional) | `packages_all_lints_browser.zip` |
| `--tools lints docs --packages all_lints browser` | `exactus_lints_docs_packages_all_lints_browser.zip` |
| `--packages all` / `--packages '*'` | `packages_all.zip` |
| `all` / `'*'` (positional) | `exactus_all_packages_all.zip` |

By default each run scaffolds a bundle directory under
`<root>/zip-components/` (git-ignored):

```text
zip-components/
├── README.md                      # explains the folder (created once)
└── packages_steps/                  # named after the archive
    ├── packages_steps.zip           # the bundle
    ├── README.md                  # selection, metrics, extract hint
    └── TREE.txt                   # members as a size/date tree
```

`--output-folder <DIR>` substitutes another parent for
`zip-components/`; `--output` / `-o <ZIP>` writes a bare archive at an
explicit path and bypasses the scaffold entirely. Unknown component
names exit through the parser with status `2`; invoking without any
selection prints usage and returns `1`.

`--list` / `-l` prints the resolved selection as JSON instead of
writing an archive:

```bash
python exactus/packages/zip_components --list                  # every package present
python exactus/packages/zip_components --packages all_lints -l   # the discovered closure
```

```json
{"packages": ["all_lints", "group_final", "organize", "steps"], "exactus": []}
```

Without components it reports every `exactus/packages/` package plus the
canonical exactus tool list — the same identifiers `python exactus
--list-tools` prints, read through
`exactus.tools.common.catalog.Constants.exactus_catalog` rather than a
directory scan; with components it reports the discovered closure
that `--bundle` would write. Output is `{"packages": [...], "exactus":
[...]}` with each list sorted by name.

`--root <DIR>` bundles from another project root instead of the
auto-detected one (useful for foreign checkouts or fixtures):

```bash
python exactus/packages/zip_components --tools lints --root ~/other/Exactus
```

## Project release archives

`--project` switches to release mode: instead of bundling selected
components it archives the whole project tree without modifying it,
replacing the regular `exactus/bundle` directory with the contents of
`build/exactus/bundle` inside the archive.

```bash
python -m exactus.packages.zip_components --project
python -m exactus.packages.zip_components --project -o dist/release.zip
python -m exactus.packages.zip_components --project --root ~/other/Exactus
```

The archive defaults to `<root>/exactus-release.zip`; `-o`/`--output`
redirects it. `build/exactus/bundle` must exist — the mode fails with
`FileNotFoundError` otherwise. `__pycache__`, `build`, `dist`, `bin`,
`EXACTUS_RESULTS_RELEASE`, `packages`, `node_modules`,
`exactus.egg-info`, `.DS_Store` and every dot-file entry are skipped,
`exactus/bundle` is omitted from the source files, and the built
bundle's files are written at `exactus/bundle/<path>` instead.
`--project` cannot be combined with component selections, `--list` or
`--output-folder`.

## What gets bundled

For every component in the final selection:

- `exactus/tools/<name>/` or `exactus/packages/<name>/` — the full source tree
- `exactus/tests/exactus/tools/<name>/` or `exactus/tests/packages/<name>/` — its tests
- `exactus/docs/exactus/tools/<name>/` or `exactus/docs/packages/<name>/` — its docs

Plus the skeleton needed for the bundle to keep working:

- `pyproject.toml`, `exactus/tests/__init__.py`, `exactus/tests/conftest.py`,
  `exactus/tests/common/` — always
- `exactus/__init__.py`, `exactus/__main__.py`,
  `exactus/tools/__init__.py`, `exactus/tests/exactus/` package files and
  `exactus/docs/exactus/tools/{DOCS,README}.md` — when exactus components are
  bundled
- `exactus/packages/__init__.py`, `exactus/packages/__main__.py`,
  `exactus/packages/README.md`, `exactus/tests/packages/` package files,
  `exactus/tests/packages/test_packages.py` and `exactus/docs/packages/{DOCS,README}.md` —
  when packages components are bundled
- `<reports-dir>/<TOOL>/` — each selected (and discovered) exactus
  tool's existing results directory; `<reports-dir>` resolves through
  `[tool.exactus] reports-dir` (default `EXACTUS_RESULTS`) instead of
  being hardcoded, and tool subfolders use the canonical uppercase
  output name (`EXACTUS_RESULTS/LINTS`, `EXACTUS_RESULTS/DOCS`, …).
  Missing directories are skipped.

`__pycache__`, `*.pyc`, `*.pyo` and `.DS_Store` are never written.

## Dependency discovery

`discover_components()` scans every Python file in each selected
component's source and test directories for
`from exactus.packages.<name>` / `import exactus.packages.<name>` and
`from exactus.tools.<name>` / `import exactus.tools.<name>` imports —
plus quoted dotted names like `"exactus.packages.project_python"`, which is how
packages `__main__` shims reach their bootstrap through
`import_module`. Each discovered component is bundled under the same
rules, recursively, until the selection stops growing.

Example: `--tools lints` pulls in `exactus.tools.common`,
`exactus.tools.reports` and the packages pipeline packages
(`all_lints`, `group_final`, `organize`, `steps`, `project_python`,
and whatever those import in turn, e.g. `markdown`, `model`,
`pmanager`).

Imports that do not resolve to an existing component directory are
ignored.

## API

```python
from exactus.packages.zip_components import (
    BundleResult, Selection, available_components, bundle_name,
    collect_files, create_bundle, create_project_archive,
    discover_components, project_root,
)
```

- `available_components(root=) -> Selection` — the canonical exactus
  catalog tools plus every `exactus/packages/` package present, sorted by name.
- `discover_components(root=, exactus=, packages=) -> Selection` —
  requested + transitively discovered names.
- `collect_files(root=, selection=) -> tuple[str, ...]` — sorted
  unique archive member names.
- `bundle_name(exactus=, packages=) -> str` — the derived archive name.
- `create_bundle(root=, exactus=, packages=, output=None,
  output_folder=None) -> BundleResult` — discovery, collection, zip
  write and `README.md`/`TREE.txt` scaffold in one call;
  `BundleResult` carries `path`, `files` and `selection`.
- `create_project_archive(root=, output=None) -> BundleResult` — the
  whole-project release archive backing `--project`; replaces
  `exactus/bundle` with `build/exactus/bundle` inside the archive and
  raises `FileNotFoundError` when the built bundle is missing.
- `main(arguments=None) -> int` — the CLI entry point.

## Examples

`python -m exactus.packages.zip_components.examples` bundles `exactus.packages.steps` into
a temporary directory and prints the member count plus discovered
dependencies — no repository files are written.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Public API for reproducible source-bundle archives. |
| `__main__.py` | Create source-bundle archives of exactus tools and packages packages. |
| `core.py` | Create source-bundle archives of exactus tools and packages packages. |
| `examples/` | Demonstrate source-bundle creation. |

Run it as a module: `python -m exactus.packages.zip_components`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `names` | exactus/packages/<PACKAGE> components (shorthand for --packages). | nargs='*' |
| `--tools` | exactus/tools/<TOOL> components to bundle (``all``/``*`` selects every tool). | default=(), nargs='+' |
| `--packages` | exactus/packages/<PACKAGE> components to bundle (``all``/``*`` selects every package). | default=(), nargs='+' |
| `--output, -o` | Destination archive (writes a bare zip, no bundle layout). | default=None, type=Path |
| `--output-folder` | Directory holding the bundle folder (defaults to <root>/zip-components). | default=None, type=Path |
| `--list, -l` | Print the resolved selection as JSON instead of bundling; without components lists every available package. | action='store_true' |
| `--project` | Archive the whole project as a release ZIP: the regular exactus/bundle directory is replaced by the contents of build/exactus/bundle inside the archive. | action='store_true' |
| `--root` | Project root to bundle from (defaults to auto-detection). | default=None, type=Path |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `core.py`

Create source-bundle archives of exactus tools and packages packages.

- `class Constants` — Group module-level constants.
  - `component_import` = `compile_regex(pattern='^\\s*(?:from|import)\\s+exactus\\.(packages|...`
  - `quoted_module` = `compile_regex(pattern='["\\\']exactus\\.(packages|tools)\\.([a-z_][...`
  - `skipped_directories` = `frozenset({'__pycache__'})`
  - `skipped_suffixes` = `frozenset({'.pyc', '.pyo'})`
  - `skipped_names` = `frozenset({'.DS_Store'})`
  - `shared_paths` = `('pyproject.toml', 'exactus/tests/__init__.py', 'exactus/tests/conf...`
  - `exactus_paths` = `('exactus/__init__.py', 'exactus/__main__.py', 'exactus/tools/__ini...`
  - `package_paths` = `('exactus/packages/__init__.py', 'exactus/packages/__main__.py', 'e...`
  - `bundles_folder` = `'zip-components'`
  - `project_excluded_directories` = `frozenset({'__pycache__', 'build', 'dist', 'bin', 'EXACTUS_RESULTS_...`
  - `project_bundle` = `Path('exactus', 'bundle')`
  - `project_build_bundle` = `Path('build', 'exactus', 'bundle')`
  - `project_archive` = `'exactus-release.zip'`
  - `folder_readme` = `'# `zip-components/`\n\nArchives produced by `exactus.packages.zip_...`
- `class Selection` — Component names bundled by kind.
  - Fields: `exactus: tuple[str, ...]`, `packages: tuple[str, ...]`
- `class BundleResult` — Outcome of one bundle write.
  - Fields: `path: Path`, `files: tuple[str, ...]`, `selection: Selection`
- `project_root() -> Path` — Return the repository root that owns this package.
- `discover_components(*, root: Path, exactus: Sequence[str]=(), packages: Sequence[str]=()) -> Selection` — Expand a selection with every transitively imported component.
- `available_components(*, root: Path) -> Selection` — Return every bundleable component, sorted by name.
- `collect_files(*, root: Path, selection: Selection) -> tuple[str, ...]` — List every repository-relative file a selection bundles.
- `bundle_name(*, exactus: Sequence[str]=(), packages: Sequence[str]=()) -> str` — Return the archive name derived from the requested components.
- `create_bundle(*, root: Path, exactus: Sequence[str]=(), packages: Sequence[str]=(), output: Path | None=None, output_folder: Path | None=None) -> BundleResult` — Write one source-bundle archive for the requested components.
- `create_project_archive(*, root: Path, output: Path | None=None) -> BundleResult` — Write the project release ZIP with the current built bundle.
- `main(*, arguments: Sequence[str] | None=None) -> int` — Bundle the requested exactus tools and/or packages packages.

## Examples

Demonstrate source-bundle creation.

Files: `__init__.py`, `__main__.py`, `run.py`

## Dependencies and consumers

- Other packages: [`steps`](../steps/DOCS.md), [`tree`](../tree/DOCS.md)
- Tools: `exactus.tools.common`
- Used by: no other module imports it; it is run directly or through the bundle.

## Tests

Tests live in `exactus/tests/packages/zip_components/`.

- `test_zip_components.py` — Tests for source-bundle archives of exactus tools and packages packages. (26 tests)
  - `test_bundle_name_joins_kinds_in_request_order`
  - `test_discover_components_is_transitive`
  - `test_discover_components_skips_missing_directories`
  - `test_collect_files_adds_skeleton_skips_caches`
  - `test_collect_files_includes_results_directories`
  - `test_collect_files_ignores_missing_results`
  - `test_create_bundle_writes_a_real_archive`
  - `test_create_bundle_scaffolds_readme_and_tree`
  - `test_lints_selection_discovers_pipeline_components`
  - `test_main_writes_the_scaffolded_bundle`
  - `test_main_output_folder_overrides_the_default_directory`
  - `test_main_root_flag_bundles_from_the_given_directory`
  - `test_available_components_lists_every_package`
  - `test_main_list_outputs_every_component`
  - `test_main_list_resolves_a_named_selection`
  - `test_main_prints_usage_without_components`
  - `test_main_rejects_an_unknown_component`
  - `test_main_positional_names_are_packages_shorthand`
  - `test_main_wildcard_expands_to_every_package`
  - `test_main_bare_star_selects_everything`
  - `test_bundle_name_renders_wildcards_as_all`
  - `test_main_accepts_both_component_kinds`
  - `test_create_project_archive_replaces_the_bundle`
  - `test_create_project_archive_requires_the_built_bundle`
  - `test_main_project_writes_the_release_archive`
  - `test_main_project_rejects_component_selections`

<!-- exactus:reference:end -->
