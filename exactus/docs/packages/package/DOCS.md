# `exactus.packages.package`

`exactus.packages.package` is the unified release pipeline for the existing Exactus build,
bundle and package operations. It exposes the same three stages through Python,
CLI and `pyproject.toml` and always executes selected stages in this order:

1. `build`
2. `bundle`
3. `package`

## CLI

```sh
python -m exactus.packages.package --build
python -m exactus.packages.package --bundle
python -m exactus.packages.package --package
python -m exactus.packages.package --package --build --bundle
```

The final command still executes build, then bundle, then package. If at least one
stage flag is present, the flags are the complete requested stage set. With no
stage flags, `enabled` values under `[tool.package.build]`,
`[tool.package.bundle]`, and `[tool.package.package]` are used. If none is
enabled, package-only behavior is the compatibility default.

Stage options are namespaced (`--build-target`, `--bundle-target`,
`--package-output`) so similarly named settings can never be ambiguous.
Explicit CLI values override pyproject values field by field.

## Python API

```python
from pathlib import Path
from exactus.packages.package import BuildConfig, BundleConfig, PackageConfig, run

result = run(
    root=Path.cwd(),
    build_stage=True,
    bundle_stage=True,
    package_stage=True,
    build_config=BuildConfig(targets=("linux-glibc-amd64",)),
    bundle_config=BundleConfig(targets=("linux-glibc-amd64",)),
    package_config=PackageConfig(),
)
```

For individual stages use `build(config=..., root=...)`,
`bundle(config=..., root=...)`, or `package(config=..., root=...)`.

## Configuration

All unified settings live under `tool.package`; legacy `[tool.build]` and
`[tool.bundle]` are deliberately not mixed into the new parser, preventing two
configuration sources from silently disagreeing. See the commented template in
`pyproject.toml` for every supported setting.

`[tool.package.build]` controls `enabled`, `check`, `dist`, `tree`,
`include-exactus-results`, `targets`, and `exec-targets`.

`[tool.package.bundle]` controls `enabled`, `targets`, `node-version`,
`optional`, `exclude`, `only`, `part-bytes`, `output`, `parts-dir`, and
`rebuild`.

`[tool.package.package]` controls `enabled`, `output`, and
`include-exactus-results`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Unified project build, bundle, and package pipeline. |
| `__main__.py` | Execute process_guard as a Python module. |
| `api.py` | Python API for deterministic build, bundle, package orchestration. |
| `build.py` | Build the distributable artifacts of the exactus. |
| `bundle.py` | Build incremental partitioned offline tool bundles and catalogs. |
| `cli.py` | Command-line interface for :mod:`exactus.packages.package`. |
| `config.py` | Typed configuration for the build, bundle, and package pipeline. |
| `examples/` | Python API examples for the unified package pipeline. |
| `inventory.py` | Share project-tree filtering between package and build_make scripts. |
| `inventory_cli.py` | ANSI-styled ``--help``/``-h`` output shared by the root scripts. |
| `partition_fs.py` | Deterministic, streaming content-addressed filesystem bundles. |
| `partition_launcher.py` | Offline dependency-aware runtime for partitioned filesystem tools. |
| `process_control.py` | Cross-invocation exactus ownership and process termination primitives. |
| `progress.py` | Uniform ``exactus-run/v1`` live-run progress document schema. |
| `readmes.py` | Generate directory documentation for offline distribution assets. |
| `templates/` | Standalone Exactus package executable. |

Run it as a module: `python -m exactus.packages.package`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--exactus, --check` | Build the ./bin/exactus executable zipapp only. | action='store_true' |
| `--build` | Build the ./build dist directory (unzipped zipapp tree) only. | action='store_true' |
| `--tree` | Write ./TREE.txt with the packaged project tree only. | action='store_true' |
| `--no-exactus` | Exclude EXACTUS_RESULTS and its complete subtree from TREE.txt. | action='store_true' |
| `--target` | Limit bundled OS/architecture/libc targets staged into the zipapp and dist tree; accepts several values and may be repeated. `all` keeps every target. Group aliases expand: ' + ', '.join(sorted(TARGET_GROUPS)) + '. Default: keep every target. | default=None, choices=(*TARGETS, *TARGET_GROUPS, 'all'), action='extend', nargs='+' |
| `--exec-target` | Limit bundled targets staged into ./bin/exactus only; overrides [tool.build.exec] targets and --target for the pyz. Same values as --target. | default=None, choices=(*TARGETS, *TARGET_GROUPS, 'all'), action='extend', nargs='+' |
| `--output` | Destination launcher for a single target. Default: PROJECT_ROOT/exactus/bundle/<target>/__main__.py. | default=None, type=Path |
| `--node-version` |  | default='22.21.1' |
| `--parts-dir` | Payload-parts directory. Default: data/parts/ beside the resolved launcher. | default=None, type=Path |
| `--part-bytes` | Maximum bytes per Git payload file; must be <= 90,000,000. | default=BuildToolsDefaults.default_parts_bytes, type=int |
| `--optional` | Optional component, tool, or group; accepts several values after one flag (`--optional browser docs`) and may be repeated. Merged with `[tool.bundle] optional` from pyproject.toml. Groups: ' + ', '.join(sorted(GROUPS)) + ", all (every optional component). This project's bundle requires `browser`, `jinja2`, and `pillow`. | default=[], choices=optional_choices, action='extend', nargs='+' |
| `--exclude` | Component, tool, or group to drop from the final selection, e.g. `--exclude pillow` removes the component pulled in by `[tool.bundle] optional`. Exclusions are ignored for dependencies a kept component still requires and for the mandatory `zstd-cli` component. | default=[], choices=optional_choices, action='extend', nargs='+' |
| `--only` | Force acquisition/scanning of these selected components; reuse valid siblings. Names can include tools or groups. | default=[], choices=tuple(sorted(COMPONENTS)), action='extend', nargs='+' |
| `--rebuild` | Force all selected components to restage and rescan. | action='store_true' |
| `--root` |  | default=Path.cwd(), type=Path |
| `--pyproject` |  | type=Path |
| `--bundle` | Run bundle stage. | action='store_true' |
| `--package` | Run package stage. | action='store_true' |
| `--build-target` |  | default=None, action='append' |
| `--build-exec-target` |  | default=None, action='append' |
| `--build-no-check` |  | action='store_true' |
| `--build-no-dist` |  | action='store_true' |
| `--build-no-tree` |  | action='store_true' |
| `--build-no-exactus-results` |  | action='store_true' |
| `--bundle-target` |  | default=None, action='append' |
| `--bundle-node-version` |  |  |
| `--bundle-optional` |  | default=None, action='append' |
| `--bundle-exclude` |  | default=None, action='append' |
| `--bundle-only` |  | default=None, action='append' |
| `--bundle-part-bytes` |  | type=int |
| `--bundle-output` |  | type=Path |
| `--bundle-parts-dir` |  | type=Path |
| `--bundle-rebuild` |  | action='store_true' |
| `--package-output` |  | type=Path |
| `--package-no-exactus-results` |  | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `api.py`

Python API for deterministic build, bundle, package orchestration.

- `class StageResult` — One completed stage.
  - Fields: `name: str`, `outputs: tuple[Path, ...]`
- `class RunResult` — Ordered pipeline result.
  - Fields: `stages: tuple[StageResult, ...]`
- `class RunArguments(TypedDict)` — Optional keyword arguments accepted by :func:`run`.
- `build(*, config: BuildConfig, root: Path) -> StageResult` — Run the build stage.
- `bundle(*, config: BundleConfig, root: Path) -> StageResult` — Run the bundle stage.
- `package(*, config: PackageConfig, root: Path) -> StageResult` — Run the package archive stage.
- `run(*, root: Path, pyproject: Path | None=None, **arguments: Unpack[RunArguments]) -> RunResult` — Run selected stages in canonical build -> bundle -> package order.

### `build.py`

Build the distributable artifacts of the exactus.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[3]`
  - `package` = `root / 'exactus'`
  - `bundle` = `package / 'bundle'`
  - `packages` = `root / 'exactus' / 'packages'`
  - `package_names` = `('all_lints', 'completion', 'group_final', 'http_process', 'markdow...`
  - `bin_zstd_portable` = `root / 'bin' / 'zstd_portable'`
  - `zstd_archives` = `{('linux', 'amd64'): 'linux-x86_64.zip', ('linux', 'x86_64'): 'linu...`
  - `check` = `root / 'bin' / 'exactus'`
  - `dist` = `root / 'build'`
  - `tree` = `root / 'TREE.txt'`
  - `excluded_dirs` = `frozenset({'__pycache__'})`
  - `main_stub` = `dedent(text='\n        """Pyz entry point dispatching to the exactu...`
  - `check_readme_template` = `Path(__file__).resolve().parent / 'templates' / 'readme_template.md'`
  - `dist_readme` = `'# `build/`\n\nGenerated dist directory produced by `python exactus...`
- `class BuildFileConfig` — ``[tool.build]`` defaults layered under command-line options.
  - Fields: `build: bool`, `check: bool`, `exec_target: str | None`, `exec_targets: tuple[str, ...]`, `no_exactus: bool`, `target: str | None`, `targets: tuple[str, ...]`, `tree: bool`
- `build_file_config(*, path: Path) -> BuildFileConfig` — Read ``[tool.build]`` defaults from a ``pyproject.toml`` file.
- `kept_bundle_leaves(*, targets: list[str] | None) -> frozenset[Path] | None` — Resolve target requests into kept bundle directories.
- `build_check(*, target: Path, kept: frozenset[Path] | None=None) -> None` — Build the executable zipapp.
- `build_dist(*, kept: frozenset[Path] | None=None) -> None` — Build the unzipped ``build/`` distribution.
- `build_tree(*, target: Path, include_exactus_results: bool=True) -> None` — Write the filtered project tree.
- `create_parser() -> ArgumentParser` — Create the build CLI parser.
- `main() -> int` — Build the selected artifacts.

### `bundle.py`

Build incremental partitioned offline tool bundles and catalogs.

- `class Constants` — Group module-level constants.
  - `size_base` = `1000`
  - `heartbeat_seconds` = `1.0`
  - `node_mirror` = `'https://nodejs.org/dist'`
  - `node_mirror_unofficial` = `'https://unofficial-builds.nodejs.org/download/release'`
  - `cft_cdn` = `'https://storage.googleapis.com/chrome-for-testing-public'`
  - `node_prune_posix` = `('bin/npm', 'bin/npx', 'bin/corepack', 'include', 'share', 'lib/nod...`
  - `node_prune_windows` = `('npm', 'npm.cmd', 'npm.ps1', 'npx', 'npx.cmd', 'npx.ps1', 'corepac...`
  - `browser_prune_names` = `frozenset({'WidevineCdm', 'MEIPreload', 'PrivacySandboxAttestations...`
  - `build_steps` = `('fingerprint', 'stage', 'scan', 'membership', 'pack', 'catalog', '...`
  - `fetch_schemes` = `frozenset({'http', 'https'})`
  - `fetch_retryable` = `frozenset({408, 425, 429, 500, 502, 503, 504})`
  - `fetch_chunk` = `1024 * 1024`
  - `fetch_user_agent` = `'exactus'`
  - `max_line_length` = `79`
- `class BuildToolsDefaults` — Immutable filesystem defaults for the bundle builder.
- `stub_marker() -> str` — Return the marker embedded in generated dispatchers.
- `bundle_dir(*, target: str) -> Path` — Return the emitted bundle directory for one target identifier.
- `host_target() -> str | None` — Return the bundle target matching the build host, if any.
- `size_label(*, size: int) -> str` — Format a byte count with decimal SI units.
- `class FetchError(RuntimeError)` — Failed to download a remote resource.
- `class FetchOptions` — Optional tuning for one ``fetch`` transfer.
  - Fields: `timeout: float`, `limit: int`, `attempts: int`
- `class ResponseReader(Protocol)` — Common positional read interface of urllib response streams.
  - `read(size: int, /) -> bytes` — Read at most the requested number of response bytes.
- `fetch(*, url: str, options: FetchOptions | None=None) -> bytes` — Download ``url`` over HTTP(S) with retries and a size cap.
- `class ToolSpec` — One invocable tool a component archive provides.
  - Fields: `name: str`, `kind: ToolKind`, `target: str`, `module: str`
- `class ComponentSpec` — One logical filesystem component sharing a dependency set.
  - Fields: `name: str`, `tools: tuple[ToolSpec, ...]`, `python_packages: tuple[str, ...]`, `node_packages: tuple[str, ...]`, `requires: tuple[str, ...]`, `env: tuple[tuple[str, tuple[str, ...]], ...]`, `optional: bool`, `node_runtime: bool`, `browsers: bool`, `python_extras: bool`, `zstd_cli: bool`
- `resolve_components(*, names: tuple[str, ...], follow_requires: bool=True) -> tuple[str, ...]` — Resolve tools, groups, and component names to components.
- `class BundleConfig` — Immutable exactus-tool bundle configuration.
  - Fields: `node_version: str`, `optional: tuple[str, ...]`, `exclude: frozenset[str]`
  - `selected_optional() -> frozenset[str]` — Selected optional component names.
  - `components() -> tuple[ComponentSpec, ...]` — Components to stage, required first in table order.
  - `available_tools() -> tuple[str, ...]` — Tool names exposed by this exact bundle.
- `class NodeDistribution` — Node.js runtime source and on-disk layout for a target.
  - Fields: `suffix: str`, `mirror: str`, `archive: str`, `binary: str`, `npm: str`, `prune: tuple[str, ...]`
- `class BrowserArchive` — One Playwright browser download for a target.
  - Fields: `name: str`, `cdn_file: str`, `cft_file: str | None`
- `class BrowserDistribution` — Playwright browser archives and payload pruning for a target.
  - Fields: `archives: tuple[BrowserArchive, ...]`, `cft_dir: str | None`, `prune_names: frozenset[str]`, `locale_suffix: str`, `locale_parent: str | None`, `locale_keep: tuple[str, ...]`
- `class Distribution` — Payload layout shared by every target.
  - Fields: `status_name: str`
- `class BuildTarget` — Target platform description driving every build step.
  - Fields: `name: str`, `os: OperatingSystem`, `arch: Architecture`, `libc: Libc | None`, `node: NodeDistribution`, `wheel_platforms: tuple[str, ...]`, `browsers: BrowserDistribution`, `python_extras: tuple[str, ...]`
- `class BuildOptions(Namespace)` — Typed command-line options for the bundle builder.
  - Fields: `output: Path | None`, `exclude: list[str] | None`, `node_version: str | None`, `only: list[str] | None`, `optional: list[str] | None`, `part_bytes: int | None`, `parts_dir: Path | None`, `target: list[str] | None`, `rebuild: bool`
- `class BundleFileConfig` — ``[tool.bundle]`` defaults layered under command-line options.
  - Fields: `exclude: tuple[str, ...]`, `node_version: str | None`, `only: tuple[str, ...]`, `optional: tuple[str, ...]`, `output: Path | None`, `part_bytes: int | None`, `parts_dir: Path | None`, `rebuild: bool`, `target: str | None`, `targets: tuple[str, ...]`
- `bundle_file_config(*, path: Path) -> BundleFileConfig` — Read ``[tool.bundle]`` defaults from a ``pyproject.toml`` file.
- `class BundleBuilder` — Build one portable self-extracting exactus tool dispatcher.
  - `prune(*, payload: Path) -> None` — Remove bytecode caches and source maps from the payload.
  - `build(*, part_bytes: int=BuildToolsDefaults.default_parts_bytes, only: tuple[str, ...]=(), rebuild: bool=False, chunking: ChunkingConfig | None=None) -> Path` — Build an incremental partitioned distribution and pack update.
- `main() -> int` — Build the configured bundle.

### `cli.py`

Command-line interface for :mod:`exactus.packages.package`.

- `create_parser() -> ArgumentParser` — Create the unified CLI parser.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run the unified CLI.

### `config.py`

Typed configuration for the build, bundle, and package pipeline.

- `class BuildConfig` — Build-stage settings.
  - Fields: `enabled: bool`, `check: bool`, `dist: bool`, `tree: bool`, `include_exactus_results: bool`, `targets: tuple[str, ...]`, `exec_targets: tuple[str, ...]`
- `class BundleConfig` — Bundle-stage settings.
  - Fields: `enabled: bool`, `targets: tuple[str, ...]`, `node_version: str`, `optional: tuple[str, ...]`, `exclude: tuple[str, ...]`, `only: tuple[str, ...]`, `part_bytes: int`, `output: Path | None`, `parts_dir: Path | None`, `rebuild: bool`
- `class PackageConfig` — Package-stage settings.
  - Fields: `enabled: bool`, `output: Path | None`, `include_exactus_results: bool`
- `class PipelineConfig` — Complete three-stage configuration.
  - Fields: `root: Path`, `build: BuildConfig`, `bundle: BundleConfig`, `package: PackageConfig`
- `load_config(*, root: Path, path: Path | None=None) -> PipelineConfig` — Load ``[tool.package]`` and its stage subtables.

### `inventory.py`

Share project-tree filtering between package and build_make scripts.

- `class Constants` — Group module-level constants.
  - `exactus_results` = `'EXACTUS_RESULTS'`
- `partition_excluded(*, directory: Path, name: str) -> bool` — Exclude retained catalogs and unreachable packs from distributions.
- `excluded_dir(*, name: str, allow_uppercase: bool=False) -> bool` — Return whether a directory is pruned from the project tree.
- `is_zip(path: Path) -> bool` — Return whether a file is a zip archive by content.
- `walk_project(*, root: Path, include_exactus_results: bool=False) -> Iterator[tuple[Path, list[str], list[str]]]` — Yield the filtered project tree, directory by directory.
- `collect_files(*, root: Path, exclude: Path | None=None, include_exactus_results: bool=False) -> list[Path]` — Collect the project files eligible for archiving.
- `render_tree(*, root: Path, include_exactus_results: bool=False) -> str` — Render the filtered project tree as ``tree``-style text.

### `inventory_cli.py`

ANSI-styled ``--help``/``-h`` output shared by the root scripts.

- `class Constants` — Group module-level constants.
  - `reset` = `'\x1b[0m'`
  - `bold` = `'\x1b[1m'`
  - `dim` = `'\x1b[2m'`
  - `green` = `'\x1b[32m'`
  - `yellow` = `'\x1b[33m'`
  - `cyan` = `'\x1b[36m'`
- `styled() -> bool` — Return whether ANSI styling may be emitted on stdout.
- `paint(*, code: str, text: str) -> str` — Wrap ``text`` in an ANSI ``code`` when styling is enabled.
- `class PrettyHelpFormatter(RawDescriptionHelpFormatter)` — argparse formatter adding ANSI color to the help layout.
  - `format_help() -> str` — Return the full help with a styled leading usage line.
  - `start_section(heading: str | None) -> None` — Begin a help section with a bold heading.
- `pretty_parser(*, prog: str, description: str, epilog: str='') -> ArgumentParser` — Create an ``ArgumentParser`` with the ANSI help formatter.

### `partition_fs.py`

Deterministic, streaming content-addressed filesystem bundles.

- `class Constants` — Group module-level constants.
  - `magic` = `b'PTFS1\n'`
  - `block` = `1024 * 1024`
  - `max_update_member` = `256 * 1024 * 1024`
  - `max_header` = `4096`
  - `max_mode` = `511`
  - `format` = `'partitioned-filesystem-v1'`
  - `gear` = `tuple((int.from_bytes(bytes=sha256(data=bytes([byte])).digest()[:8]...`
- `class FormatError(ValueError)` — Invalid or corrupted partitioned filesystem data.
- `class Entry(TypedDict)` — Portable recipe entry; unused fields are absent.
- `class Recipe(TypedDict)` — One immutable logical component and its acquisition metadata.
- `class ObjectRecord(TypedDict)` — Unique chunk location and exact component membership.
- `class PackRecord(TypedDict)` — Deterministic shard and compressed transport identity.
- `class Catalog(TypedDict)` — Versioned canonical distribution identity.
- `class ChunkingConfig` — Versioned Gear CDC parameters and whole-small-file policy.
  - Fields: `minimum_bytes: int`, `target_bytes: int`, `maximum_bytes: int`, `small_file_bytes: int`
  - `document() -> dict[str, Json]` — Return the canonical, fingerprintable policy.
  - `chunks(source: BinaryIO, size: int) -> Iterator[bytes]` — Yield bounded chunks, resynchronizing after inserted content.
- `canonical(value: Json) -> bytes` — Encode portable JSON without timestamps or incidental whitespace.
- `identity(value: Json) -> str` — Hash a canonical logical identity.
- `hash_file(path: Path) -> str` — Hash a large file with bounded memory.
- `atomic_bytes(path: Path, data: bytes) -> None` — Publish bytes using a unique sibling and atomic replacement.
- `safe_path(value: str) -> PurePosixPath` — Reject traversal, aliases, drive paths, backslashes, and NULs.
- `component_name(value: str) -> str` — Validate a single portable component identifier.
- `destination(root: Path, relative: str) -> Path` — Resolve a destination without traversing symlink parents.
- `tree_identity(entries: list[Entry]) -> str` — Hash portable tree structure independently of chunk boundaries.
- `recipe_identity(recipe: Recipe) -> str` — Hash all recipe data except its self hash.
- `class ObjectStore` — Disk-backed verified chunks, atomically created under SHA-256.
  - `path(digest: str) -> Path` — Return a safe address after validating its hash syntax.
  - `valid(digest: str, size: int | None=None) -> bool` — Verify cached content before reusing it.
  - `put(data: bytes) -> str` — Store one bounded chunk; repair corrupt disposable caches.
- `class RecipeScanner` — Scan deterministic trees while writing streaming CDC objects.
  - `scan(root: Path, name: str, metadata: dict[str, Json]) -> Recipe` — Preserve dirs, modes, links, and full hashes without large reads.
- `memberships(recipes: dict[str, Recipe]) -> dict[str, list[str]]` — Compute exact content references, independently of dependencies.
- `shards(objects: list[str], sizes: dict[str, int], target: int, prefix: str='') -> Iterator[tuple[str, list[str]]]` — Split oversized groups recursively by stable hexadecimal prefixes.
- `pack_identity(members: list[str], prefix: str, objects: list[str], sizes: dict[str, int]) -> str` — Compute logical pack identity before compression.
- `class PackCodec` — Deterministic framed Zstandard packs; no host tar metadata.
  - `encode(path: Path, objects: list[str], store: ObjectStore) -> None` — Stream sorted verified objects with bounded framing.
  - `decode(path: Path, expected: dict[str, int], store: ObjectStore | None=None) -> None` — Verify every record, with optional decoded-object cache recovery.
- `validate_recipe(recipe: Recipe) -> None` — Validate identity, entry paths, types, and safe link topology.
- `load_recipe(value: Json) -> Recipe` — Parse and validate a cached or distributed recipe.
- `catalog_identity(catalog: Catalog) -> str` — Hash the full catalog body excluding its self hash.
- `load_catalog(path: Path) -> Catalog` — Validate schema, integrity hierarchy, membership, and all paths.
- `class PartitionStore` — Build, verify, and recover canonical packs from persistent caches.
  - `verify(catalog: Catalog, root: Path, store: ObjectStore | None=None) -> None` — Verify transport hashes and every framed object before trust.
  - `build(recipes: dict[str, Recipe], output: Path, platform: str, pack_target: int=64 * Constants.block, progress: Callable[[int, int, int], None] | None=None) -> Catalog` — Plan exact membership and stable shards; reuse verified packs.
  - `recover(catalog: Catalog, root: Path, recipes: dict[str, Recipe]) -> None` — Recover local objects from verified previous packs.
- `class Materializer` — Safely reconstruct immutable files with exact-file hardlink reuse.
  - `materialize(recipe: Recipe, root: Path) -> None` — Create dirs/files/hardlinks first, symlinks last; verify output.
- `verify_tree(recipe: Recipe, root: Path, *, contents: bool=True) -> None` — Check reconstructed sizes, modes, links, hashes, and extra paths.
- `write_delta(baseline: Catalog, current: Catalog, source: Path, output: Path) -> dict[str, Json]` — Write only new packs plus a self-verifying target catalog/update.
- `apply_delta(root: Path, update: Path) -> Catalog` — Verify an update fully, install immutable packs, switch catalog last.
- `rollback(root: Path, digest: str) -> Catalog` — Restore a retained catalog after verifying all reachable packs.
- `garbage_collect(root: Path, retained: list[Catalog], *, dry_run: bool=True) -> list[str]` — Explicit reachability GC; normal updates never remove old packs.
- `deep_verify(catalog: Catalog, root: Path) -> None` — Reconstruct every tree in disposable scratch storage.
- `apply_update(root: Path, artifact: Path) -> Catalog` — Apply a directory or safely streamed ZIP update artifact.

### `partition_launcher.py`

Offline dependency-aware runtime for partitioned filesystem tools.

- `closure(catalog: Catalog, name: str) -> list[str]` — Resolve dependencies once, in deterministic dependency-first order.
- `cache_lock(root: Path, timeout: float=120.0) -> Generator[None]` — Serialize cache publication across processes without stale markers.
- `class Runtime` — Per-component atomic readiness, decoded objects, and environments.
  - `readiness(catalog: Catalog, recipe: Recipe) -> dict[str, Json]` — Return the identity required before reusing a component.
  - `ensure(name: str) -> Path` — Materialize only a tool's closure; preserve valid prior trees.
  - `environment(name: str) -> dict[str, str]` — Compose original environment semantics dependency-first.
  - `tools() -> dict[str, tuple[str, dict[str, str]]]` — Discover preserved tool declarations from catalog metadata.
  - `command(tool: str, args: list[str]) -> tuple[list[str], dict[str, str]]` — Resolve original Python/Node/binary/probe invocation semantics.
- `class Constants` — Group module-level constants.
  - `maintenance_arguments` = `2`
- `class ProcessReplacement(Protocol)` — Native process replacement boundary used by dispatch tests.
- `main(catalog_path: Path, arguments: list[str] | None=None, *, replace_process: ProcessReplacement=os_execvpe) -> int` — Dispatch metadata commands or replace the process with a tool.

### `process_control.py`

Cross-invocation exactus ownership and process termination primitives.

- `class Constants` — Group module-level constants.
  - `term_wait_seconds` = `3.0`
  - `poll_seconds` = `0.05`
  - `notice_lifetime_seconds` = `30.0`
- `new_run_id() -> str` — Return new run id.
- `process_exists(*, pid: int) -> bool` — Return process exists.
- `descendants(*, pid: int) -> tuple[int, ...]` — Return descendants.
- `exit_if_replaced(*, output_fd: int=2) -> None` — Exit normally with a notice when another exactus replaced this run.
- `terminate_tree(*, pid: int, include_root: bool=True, replaced: bool=False) -> None` — Handle terminate tree.
- `read_json(*, path: Path) -> dict[str, JsonValue] | None` — Read json.
- `write_json(*, path: Path, payload: dict[str, JsonValue]) -> None` — Write json.

### `progress.py`

Uniform ``exactus-run/v1`` live-run progress document schema.

- `class Constants` — Group module-level constants.
  - `progress_schema` = `'exactus-run/v1'`
- `utc_now() -> str` — Return the current UTC wall-clock time as an ISO-8601 string.
- `class RunItem` — Describe one sub-entity record inside a uniform run document.
  - Fields: `name: str`, `status: str`, `progress: float`, `step: str`, `detail: str`, `run_id: str | None`, `started_at: str | None`, `finished_at: str | None`, `elapsed_seconds: float`, `extra: dict[str, JsonValue]`
  - `payload(: Self) -> dict[str, JsonValue]` — Serialize the record as one ``exactus-run/v1`` items entry.
- `class RunDocument` — Describe one uniform ``exactus-run/v1`` live-run document.
  - Fields: `kind: str`, `name: str`, `status: str`, `progress: float`, `completed: int`, `total: int`, `step: str`, `detail: str`, `run_id: str | None`, `pipeline_run_id: str | None`, `pid: int | None`, `started_at: str | None`, `updated_at: str | None`, `finished_at: str | None`, `elapsed_seconds: float`, `items: tuple[RunItem | dict[str, JsonValue], ...]`, `extra: dict[str, JsonValue]`
  - `payload(: Self) -> dict[str, JsonValue]` — Serialize the document for a progress artifact file.

### `readmes.py`

Generate directory documentation for offline distribution assets.

- `directory_readme(*, name: str) -> str` — Describe one generated asset directory.
- `write_directory_readmes(*, root: Path) -> None` — Document public asset directories while preserving existing docs.

## Examples

Python API examples for the unified package pipeline.

Files: `api/__init__.py`, `api/__main__.py`, `api/run.py`, `cli/__init__.py`, `cli/__main__.py`, `cli/run.py`

## Dependencies and consumers

- Other packages: [`tree`](../tree/DOCS.md), [`zstd_portable`](../zstd_portable/DOCS.md)
- Tools: `exactus.tools.actions`, `exactus.tools.common`
- Third-party: `conflict_copies`, `partition_fs`, `partition_launcher`, `readmes`, `zstd_portable`
- Used by: `../pyproject.toml`, `packages/project_python/examples/run.py`, `tests/packages/project_python/test_examples.py`, `tests/packages/project_python/test_venv.py`, `tests/tools/common/test_common.py`, `tests/tools/common/test_process_control.py`, `tests/tools/common/test_toolkit.py`

## Tests

Tests live in `exactus/tests/packages/package/`.

- `test_package_api.py` — Tests for the unified package Python API. (3 tests)
  - `test_run_orders_selected_stages`
  - `test_run_defaults_to_package`
  - `test_load_config_reads_all_stages`
- `test_package_cli.py` — Tests for the unified package CLI. (2 tests)
  - `test_cli_stage_flags_are_exact_and_order_independent`
  - `test_cli_field_override_preserves_other_pyproject_values`

<!-- exactus:reference:end -->
