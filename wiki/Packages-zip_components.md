[Home](Home.md) > [Packages](Packages.md) > zip_components

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/zip_components/`](../exactus/packages/zip_components/) | [`exactus/tests/packages/zip_components/`](../exactus/tests/packages/zip_components/) | [`DOCS.md`](../exactus/docs/packages/zip_components/DOCS.md) |

[< Packages-widgets-widget_styles](Packages-widgets-widget_styles.md) · [Packages index](Packages.md) · [Packages-zstd_portable >](Packages-zstd_portable.md)
