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
| `examples/` | Runnable demonstration for `exactus/packages/package/`. |
| `install.py` | Install the built ``exactus`` executable system-wide. |
| `inventory.py` | Share project-tree filtering between package and build_make scripts. |
| `inventory_cli.py` | ANSI-styled ``--help``/``-h`` output shared by the root scripts. |
| `partition_fs.py` | Deterministic, streaming content-addressed filesystem bundles. |
| `partition_launcher.py` | Offline dependency-aware runtime for partitioned filesystem tools. |
| `process_control.py` | Cross-invocation exactus ownership and process termination primitives. |
| `progress.py` | Uniform ``exactus-run/v1`` live-run progress document schema. |
| `readmes.py` | Generate directory documentation for offline distribution assets. |
| `shims.py` | Generate ``exactus.vendor.<name>`` shims for bundled distributions. |
| `templates/` | Subdirectory. |

Run it as a module: `python -m exactus.packages.package`.

## Command-line options

| Option | Description | Settings |
|---|---|---|
| `--exactus, --check` | Build the ./bin/release/exactus_all/exactus zipapp only. | dest='check', action='store_true' |
| `--build` | Build the ./build dist directory (unzipped zipapp tree) only. | action='store_true' |
| `--tree` | Write ./TREE.txt with the packaged project tree only. | action='store_true' |
| `--no-exactus` | Exclude EXACTUS_RESULTS and its complete subtree from TREE.txt. | action='store_true' |
| `--target` | 'Limit bundled OS/architecture/libc targets staged into the zipapp and dist tree; accepts several values and may be repeated. `all` keeps every target. Group aliases expand: ' + ', '.join(sorted(_GroupFinalConstants.target_groups)) + '. Default: keep every target.' | action='extend', nargs='+', choices=(*_GroupFinalConstants.targets, *_GroupFinalConstants.target_groups, 'all'), default=None |
| `--exec-target` | Limit bundled targets staged into the fat release pyz only; overrides [tool.build.exec] targets and --target for the pyz. Same values as --target. | action='extend', nargs='+', choices=(*_GroupFinalConstants.targets, *_GroupFinalConstants.target_groups, 'all'), default=None |
| `--target` | 'Target platform(s) (OS/architecture/libc); accepts several values after one flag and may be repeated. `auto` selects the build host, `all` selects every target, and group aliases expand to their members: ' + ', '.join(sorted(Constants.target_groups)) + '. Default: `[tool.bundle] targets`, else `auto`.' | action='extend', nargs='+', choices=(*Constants.targets, *Constants.target_groups, 'auto', 'all'), default=None |
| `--output` | Destination launcher for a single target. Default: PROJECT_ROOT/exactus/bundle/<target>/__main__.py. | type=Path, default=None |
| `--node-version` |  | default='22.21.1' |
| `--parts-dir` | Payload-parts directory. Default: data/parts/ beside the resolved launcher. | type=Path, default=None |
| `--part-bytes` | Maximum bytes per Git payload file; must be <= 90,000,000. | type=int, default=BuildToolsDefaults.default_parts_bytes |
| `--optional` | 'Optional component, tool, or group; accepts several values after one flag (`--optional browser docs`) and may be repeated. Merged with `[tool.bundle] optional` from pyproject.toml. Groups: ' + ', '.join(sorted(Constants.groups)) + ", all (every optional component). This project's bundle requires `browser`, `jinja2`, and `pillow`." | action='extend', nargs='+', choices=optional_choices, default=[] |
| `--exclude` | Component, tool, or group to drop from the final selection, e.g. `--exclude pillow` removes the component pulled in by `[tool.bundle] optional`. Exclusions are ignored for dependencies a kept component still requires and for the mandatory `zstd-cli` component. | action='extend', nargs='+', choices=optional_choices, default=[] |
| `--only` | Force acquisition/scanning of these selected components; reuse valid siblings. Names can include tools or groups. | action='extend', nargs='+', choices=tuple(sorted(Constants.components)), default=[] |
| `--rebuild` | Force all selected components to restage and rescan. | action='store_true' |
| `--root` |  | type=Path, default=Path.cwd() |
| `--pyproject` |  | type=Path |
| `--build` | Run build stage. | action='store_true' |
| `--bundle` | Run bundle stage. | action='store_true' |
| `--package` | Run package stage. | action='store_true' |
| `--build-target` |  | action='append', default=None |
| `--build-exec-target` |  | action='append', default=None |
| `--build-no-check` |  | action='store_true' |
| `--build-no-dist` |  | action='store_true' |
| `--build-no-tree` |  | action='store_true' |
| `--build-no-exactus-results` |  | action='store_true' |
| `--build-output` |  | type=Path |
| `--build-self-test` | Enable the self_test diagnostic on built executables. | action='store_true' |
| `--bundle-target` |  | action='append', default=None |
| `--bundle-node-version` |  |  |
| `--bundle-optional` |  | action='append', default=None |
| `--bundle-exclude` |  | action='append', default=None |
| `--bundle-only` |  | action='append', default=None |
| `--bundle-part-bytes` |  | type=int |
| `--bundle-output` |  | type=Path |
| `--bundle-parts-dir` |  | type=Path |
| `--bundle-rebuild` |  | action='store_true' |
| `--package-output` |  | type=Path |
| `--package-no-exactus-results` |  | action='store_true' |
| `--rebuild` | rebuild the platform zipapp even when its bin/release artifact already exists | action='store_true' |

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Unified project build, bundle, and package pipeline.


### `__main__.py`

Execute process_guard as a Python module.


### `api.py`

Python API for deterministic build, bundle, package orchestration.

- `class StageResult` — One completed stage.
  - Fields: `name: str`, `outputs: tuple[Path, ...]`
- `class RunResult` — Ordered pipeline result.
  - Fields: `stages: tuple[StageResult, ...]`
- `class RunArguments` — Optional keyword arguments accepted by :func:`run`.
  - Fields: `build_stage: NotRequired[bool | None]`, `bundle_stage: NotRequired[bool | None]`, `package_stage: NotRequired[bool | None]`, `build_config: NotRequired[BuildConfig | None]`, `bundle_config: NotRequired[BundleConfig | None]`, `package_config: NotRequired[PackageConfig | None]`
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
  - `bin_zstd_portable` = `root / 'bin' / 'zstd_portable'`
  - `zstd_archives` = `{('linux', 'amd64'): 'linux-x86_64.zip', ('linux', 'x86_64'): 'linux-x86_...`
  - `check` = `root / 'bin' / 'release' / 'exactus_all' / 'exactus'`
  - `dist` = `root / 'build'`
  - `tree` = `root / 'TREE.txt'`
  - `excluded_dirs` = `frozenset({'__pycache__', 'EXACTUS_RESULTS'})`
  - `main_stub` = `dedent(text='\n        """Pyz entry point dispatching to the exactus."""\...`
  - `check_readme_template` = `Path(__file__).resolve().parent / 'templates' / 'readme_template.md'`
  - `dist_readme` = `dedent(text='    # `build/`\n    \n    Generated dist directory produced...`
- `class BuildFileConfig` — ``[tool.build]`` defaults layered under command-line options.
  - `build` = `False`
  - `check` = `False`
  - `exec_target` = `None`
  - `exec_targets` = `()`
  - `no_exactus` = `False`
  - `target` = `None`
  - `targets` = `()`
  - `tree` = `False`
- `build_file_config(*, path: Path) -> BuildFileConfig` — Read ``[tool.build]`` defaults from a ``pyproject.toml`` file.
- `kept_bundle_leaves(*, targets: list[str] | None) -> frozenset[Path] | None` — Resolve target requests into kept bundle directories.
- `build_check(*, target: Path, kept: frozenset[Path] | None=None, self_test: bool=False) -> None` — Build the executable zipapp.
- `build_dist(*, kept: frozenset[Path] | None=None, self_test: bool=False) -> None` — Build the unzipped ``build/`` distribution.
- `build_tree(*, target: Path, include_exactus_results: bool=True) -> None` — Write the filtered project tree.
- `create_parser() -> ArgumentParser` — Create the build CLI parser.
- `main() -> int` — Build the selected artifacts.

### `bundle.py`

Build incremental partitioned offline tool bundles and catalogs.

- `class ToolSpec` — One invocable tool a component archive provides.
  - `module` = `''`
  - Fields: `name: str`, `kind: ToolKind`, `target: str`
- `class ComponentSpec` — One logical filesystem component sharing a dependency set.
  - `tools` = `()`
  - `python_packages` = `()`
  - `node_packages` = `()`
  - `requires` = `()`
  - `env` = `()`
  - `optional` = `True`
  - `node_runtime` = `False`
  - `browsers` = `False`
  - `python_extras` = `False`
  - `zstd_cli` = `False`
  - Fields: `name: str`
- `class BrowserArchive` — One Playwright browser download for a target.
  - `cft_file` = `None`
  - Fields: `name: str`, `cdn_file: str`
- `class BrowserDistribution` — Playwright browser archives and payload pruning for a target.
  - Fields: `archives: tuple[BrowserArchive, ...]`, `cft_dir: str | None`, `prune_names: frozenset[str]`, `locale_suffix: str`, `locale_parent: str | None`, `locale_keep: tuple[str, ...]`
- `class NodeDistribution` — Node.js runtime source and on-disk layout for a target.
  - Fields: `suffix: str`, `mirror: str`, `archive: str`, `binary: str`, `npm: str`, `prune: tuple[str, ...]`
- `class Distribution` — Payload layout shared by every target.
  - `status_name` = `'@activity.json'`
- `class BuildTarget` — Target platform description driving every build step.
  - `python_extras` = `()`
  - Fields: `name: str`, `os: OperatingSystem`, `arch: Architecture`, `libc: Libc | None`, `node: NodeDistribution`, `wheel_platforms: tuple[str, ...]`, `browsers: BrowserDistribution`
- `class Constants` — Group module-level constants.
  - `size_base` = `1000`
  - `heartbeat_seconds` = `1.0`
  - `node_mirror` = `'https://nodejs.org/dist'`
  - `node_mirror_unofficial` = `'https://unofficial-builds.nodejs.org/download/release'`
  - `cft_cdn` = `'https://storage.googleapis.com/chrome-for-testing-public'`
  - `node_prune_posix` = `('bin/npm', 'bin/npx', 'bin/corepack', 'include', 'share', 'lib/node_modu...`
  - `node_prune_windows` = `('npm', 'npm.cmd', 'npm.ps1', 'npx', 'npx.cmd', 'npx.ps1', 'corepack', 'c...`
  - `browser_prune_names` = `frozenset({'WidevineCdm', 'MEIPreload', 'PrivacySandboxAttestationsPreloa...`
  - `build_steps` = `('fingerprint', 'stage', 'scan', 'membership', 'pack', 'catalog', 'launch...`
  - `fetch_schemes` = `frozenset({'http', 'https'})`
  - `fetch_retryable` = `frozenset({408, 425, 429, 500, 502, 503, 504})`
  - `fetch_chunk` = `1024 * 1024`
  - `fetch_user_agent` = `'exactus'`
  - `max_line_length` = `79`
  - `zstd_probe` = `"import subprocess,sys;from pathlib import Path;from platform import mach...`
  - `browser_probe` = `"import glob,os,subprocess,sys;b=os.environ['PLAYWRIGHT_BROWSERS_PATH'];c...`
  - `chromium_patterns` = `'chromium-*/chrome-linux/chrome,chromium-*/chrome-mac*/Chromium.app/Conte...`
  - `headless_patterns` = `'chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell,...`
  - `ffmpeg_patterns` = `'ffmpeg-*/ffmpeg-linux,ffmpeg-*/ffmpeg-mac,ffmpeg-*/ffmpeg-mac-arm64,ffmp...`
  - `components` = `{'zstd-cli': ComponentSpec(name='zstd-cli', optional=False, zstd_cli=True...`
  - `groups` = `{'browser': ('playwright', 'chromium'), 'docs': ('jinja2', 'pillow'), 'im...`
  - `tool_component` = `{tool.name: name for name, spec in components.items() for tool in spec.to...`
  - `optional_components` = `tuple((name for name, spec in components.items() if spec.optional))`
  - `mandatory_components` = `frozenset({'zstd-cli'})`
  - `linux_browsers` = `BrowserDistribution(archives=(BrowserArchive(name='chromium', cdn_file='c...`
  - `windows_browsers` = `BrowserDistribution(archives=(BrowserArchive(name='chromium', cdn_file='c...`
  - `no_browsers` = `BrowserDistribution(archives=(), cft_dir=None, prune_names=frozenset(), l...`
  - `mac_wheels_arm64` = `('macosx_14_0_arm64', 'macosx_13_0_arm64', 'macosx_12_0_arm64', 'macosx_1...`
  - `mac_wheels_x64` = `('macosx_14_0_x86_64', 'macosx_13_0_x86_64', 'macosx_12_0_x86_64', 'macos...`
  - `targets` = `{'linux-glibc-amd64': BuildTarget(name='linux-glibc-amd64', os='linux', a...`
  - `target_groups` = `{'linux': ('linux-glibc-amd64', 'linux-glibc-arm64', 'linux-musl-amd64',...`
  - `distribution` = `Distribution()`
  - `target_unavailable` = `{'linux-musl-amd64': ('browser',), 'linux-musl-arm64': ('browser', 'tree-...`
- `class BuildToolsDefaults` — Immutable filesystem defaults for the bundle builder.
  - `script_dir` = `Path(__file__).resolve().parent`
  - `project_root` = `script_dir.parent.parent.parent`
  - `bundle_root` = `project_root / 'exactus' / 'bundle'`
  - `default_parts_bytes` = `90000000`
  - `playwright_cdn` = `'https://cdn.playwright.dev'`
- `stub_marker() -> str` — Return the marker embedded in generated dispatchers.
- `bundle_dir(*, target: str) -> Path` — Return the emitted bundle directory for one target identifier.
- `host_target() -> str | None` — Return the bundle target matching the build host, if any.
- `size_label(*, size: int) -> str` — Format a byte count with decimal SI units.
- `class FetchError` — Failed to download a remote resource.
- `class FetchOptions` — Optional tuning for one ``fetch`` transfer.
  - `timeout` = `30.0`
  - `limit` = `64 * 1024 * 1024`
  - `attempts` = `3`
- `class ResponseReader(Protocol)` — Common positional read interface of urllib response streams.
  - `read(self, size: int) -> bytes` — Read at most the requested number of response bytes.
- `fetch(*, url: str, options: FetchOptions | None=None) -> bytes` — Download ``url`` over HTTP(S) with retries and a size cap.
- `resolve_components(*, names: tuple[str, ...], follow_requires: bool=True) -> tuple[str, ...]` — Resolve tools, groups, and component names to components.
- `unavailable_components(*, target: str) -> frozenset[str]` — Return optional components that cannot stage on a target.
- `class BundleConfig` — Immutable exactus-tool bundle configuration.
  - `node_version` = `'22.21.1'`
  - `optional` = `()`
  - `exclude` = `frozenset()`
  - `selected_optional(self) -> frozenset[str]` — Selected optional component names.
  - `components(self) -> tuple[ComponentSpec, ...]` — Components to stage, required first in table order.
  - `available_tools(self) -> tuple[str, ...]` — Tool names exposed by this exact bundle.
- `class BuildOptions` — Typed command-line options for the bundle builder.
  - `output` = `None`
  - `exclude` = `None`
  - `node_version` = `None`
  - `only` = `None`
  - `optional` = `None`
  - `part_bytes` = `None`
  - `parts_dir` = `None`
  - `target` = `None`
  - `rebuild` = `False`
- `class BundleFileConfig` — ``[tool.bundle]`` defaults layered under command-line options.
  - `exclude` = `()`
  - `node_version` = `None`
  - `only` = `()`
  - `optional` = `()`
  - `output` = `None`
  - `part_bytes` = `None`
  - `parts_dir` = `None`
  - `rebuild` = `False`
  - `target` = `None`
  - `targets` = `()`
- `bundle_file_config(*, path: Path) -> BundleFileConfig` — Read ``[tool.bundle]`` defaults from a ``pyproject.toml`` file.
- `class BundleBuilder` — Build one portable self-extracting exactus tool dispatcher.
  - `__init__(self, *, config: BundleConfig, output: Path, rebuild_args: tuple[str, ...]=(), parts_dir: Path | None=None, target: BuildTarget=Constants.targets['linux-glibc-amd64']) -> None` — Initialize the builder.
  - `prune(*, payload: Path) -> None` — Remove bytecode caches and source maps from the payload.
  - `build(self, *, part_bytes: int=BuildToolsDefaults.default_parts_bytes, only: tuple[str, ...]=(), rebuild: bool=False, chunking: ChunkingConfig | None=None) -> Path` — Build an incremental partitioned distribution and pack update.
- `main() -> int` — Build the configured bundle.

### `cli.py`

Command-line interface for :mod:`exactus.packages.package`.

- `create_parser() -> ArgumentParser` — Create the unified CLI parser.
- `main(*, arguments: tuple[str, ...] | None=None) -> int` — Run the unified CLI.

### `config.py`

Typed configuration for the build, bundle, and package pipeline.

- `class BuildConfig` — Build-stage settings.
  - `enabled` = `False`
  - `check` = `True`
  - `dist` = `True`
  - `tree` = `True`
  - `include_exactus_results` = `True`
  - `targets` = `()`
  - `exec_targets` = `()`
  - `output` = `None`
  - `self_test` = `False`
- `class BundleConfig` — Bundle-stage settings.
  - `enabled` = `False`
  - `targets` = `()`
  - `node_version` = `'22.21.1'`
  - `optional` = `()`
  - `exclude` = `()`
  - `only` = `()`
  - `part_bytes` = `90000000`
  - `output` = `None`
  - `parts_dir` = `None`
  - `rebuild` = `False`
- `class PackageConfig` — Package-stage settings.
  - `enabled` = `False`
  - `output` = `None`
  - `include_exactus_results` = `True`
- `class PipelineConfig` — Complete three-stage configuration.
  - `build` = `field(default_factory=BuildConfig)`
  - `bundle` = `field(default_factory=BundleConfig)`
  - `package` = `field(default_factory=PackageConfig)`
  - Fields: `root: Path`
- `load_config(*, root: Path, path: Path | None=None) -> PipelineConfig` — Load ``[tool.package]`` and its stage subtables.

### `examples/api/__init__.py`

Python API examples for the unified package pipeline.


### `examples/api/__main__.py`

Run the API example directory.


### `examples/api/run.py`

Complete Python API example.

- `main() -> int` — Run all stages through the Python API.

### `examples/cli/__init__.py`

Command-line examples for the unified package pipeline.


### `examples/cli/__main__.py`

Run the CLI example directory.


### `examples/cli/run.py`

Complete CLI example.

- `run_example() -> int` — Run all stages through the same CLI parser used by users.

### `install.py`

Install the built ``exactus`` executable system-wide.

- `class Constants` — Group module-level constants.
  - `root` = `Path(__file__).resolve().parents[3]`
  - `bin_dir` = `root / 'bin' / 'release'`
  - `command_name` = `'exactus'`
  - `posix_install_dir` = `Path('/usr/local/bin')`
  - `windows_root_variable` = `'ProgramFiles'`
  - `windows_root_fallback` = `'C:/Program Files'`
  - `windows_shim` = `'@echo off\r\npy -3 "%~dp0exactus" %*\r\n'`
  - `systems` = `{'linux': 'linux', 'darwin': 'macos', 'win32': 'windows'}`
  - `architectures` = `{'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}`
  - `linux_libc_fallback` = `'glibc'`
  - `environment_key_path` = `'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment'`
  - `progress_steps` = `(('dependencies', 0.2), ('release', 0.45), ('install', 0.15), ('completio...`
  - `pth_name` = `'exactus-bundle.pth'`
- `host_platform() -> tuple[str, str]` — Detect the host operating system and architecture.
- `host_target(*, system: str, architecture: str) -> str` — Resolve the bundle build target matching the host platform.
- `release_name(*, system: str, architecture: str) -> str` — Render the platform release directory name.
- `build_release(*, system: str, architecture: str) -> Path` — Build the host-platform zipapp and release directory contents.
- `install_system(*, rebuild: bool=False) -> Path` — Build or reuse the release and install it system-wide.
- `uninstall_system() -> Path | None` — Remove the system-wide installation.
- `create_parser() -> ArgumentParser` — Create the install/uninstall command parser.
- `run(*, arguments: Sequence[str]=(), uninstall: bool=False) -> int` — Run the install or uninstall command.

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
- `class PrettyHelpFormatter` — argparse formatter adding ANSI color to the help layout.
  - `format_help(self) -> str` — Return the full help with a styled leading usage line.
  - `start_section(self, heading: str | None) -> None` — Begin a help section with a bold heading.
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
  - `gear` = `tuple((int.from_bytes(bytes=sha256(data=bytes([byte])).digest()[:8], byte...`
- `class FormatError` — Invalid or corrupted partitioned filesystem data.
- `class Entry` — Portable recipe entry; unused fields are absent.
  - Fields: `path: str`, `type: Literal['directory', 'file', 'symlink', 'hardlink']`, `mode: int`, `size: NotRequired[int]`, `sha256: NotRequired[str]`, `chunks: NotRequired[list[str]]`, `target: NotRequired[str]`
- `class Recipe` — One immutable logical component and its acquisition metadata.
  - Fields: `name: str`, `metadata: dict[str, Json]`, `entries: list[Entry]`, `tree_sha256: str`, `recipe_sha256: str`, `logical_bytes: int`
- `class ObjectRecord` — Unique chunk location and exact component membership.
  - Fields: `size: int`, `members: list[str]`, `pack: str`
- `class PackRecord` — Deterministic shard and compressed transport identity.
  - Fields: `path: str`, `sha256: str`, `bytes: int`, `members: list[str]`, `membership_sha256: str`, `shard: str`, `objects: list[str]`
- `class Catalog` — Versioned canonical distribution identity.
  - Fields: `schema_version: int`, `format: str`, `platform: str`, `chunking: dict[str, Json]`, `pack_target_bytes: int`, `components: dict[str, Recipe]`, `objects: dict[str, ObjectRecord]`, `packs: dict[str, PackRecord]`, `root_sha256: str`
- `class ChunkingConfig` — Versioned Gear CDC parameters and whole-small-file policy.
  - `minimum_bytes` = `65536`
  - `target_bytes` = `262144`
  - `maximum_bytes` = `1048576`
  - `small_file_bytes` = `65536`
  - `document(self) -> dict[str, Json]` — Return the canonical, fingerprintable policy.
  - `chunks(self, source: BinaryIO, size: int) -> Iterator[bytes]` — Yield bounded chunks, resynchronizing after inserted content.
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
  - `__init__(self, root: Path) -> None` — Initialize a disposable object cache.
  - `path(self, digest: str) -> Path` — Return a safe address after validating its hash syntax.
  - `valid(self, digest: str, size: int | None=None) -> bool` — Verify cached content before reusing it.
  - `put(self, data: bytes) -> str` — Store one bounded chunk; repair corrupt disposable caches.
- `class RecipeScanner` — Scan deterministic trees while writing streaming CDC objects.
  - `__init__(self, objects: ObjectStore, chunking: ChunkingConfig | None=None, progress: Callable[[int, int], None] | None=None) -> None` — Configure object storage, chunk boundaries, and live counters.
  - `scan(self, root: Path, name: str, metadata: dict[str, Json]) -> Recipe` — Preserve dirs, modes, links, and full hashes without large reads.
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
  - `__init__(self, cache: Path, chunking: ChunkingConfig | None=None) -> None` — Initialize build caches; these are never distributed wholesale.
  - `verify(catalog: Catalog, root: Path, store: ObjectStore | None=None) -> None` — Verify transport hashes and every framed object before trust.
  - `build(self, recipes: dict[str, Recipe], output: Path, platform: str, pack_target: int=64 * Constants.block, progress: Callable[[int, int, int], None] | None=None) -> Catalog` — Plan exact membership and stable shards; reuse verified packs.
  - `recover(self, catalog: Catalog, root: Path, recipes: dict[str, Recipe]) -> None` — Recover local objects from verified previous packs.
- `class Materializer` — Safely reconstruct immutable files with exact-file hardlink reuse.
  - `__init__(self, store: ObjectStore) -> None` — Initialize verified objects and optional duplicate-file index.
  - `materialize(self, recipe: Recipe, root: Path) -> None` — Create dirs/files/hardlinks first, symlinks last; verify output.
- `verify_tree(recipe: Recipe, root: Path, *, contents: bool=True, allow_extra: bool=False) -> None` — Check reconstructed sizes, modes, links, hashes, and extra paths.
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
  - `__init__(self, catalog_path: Path, cache: Path | None=None) -> None` — Load the catalog and select a writable cache for its root.
  - `readiness(catalog: Catalog, recipe: Recipe) -> dict[str, Json]` — Return the identity required before reusing a component.
  - `ensure(self, name: str) -> Path` — Materialize only a tool's closure; preserve valid prior trees.
  - `environment(self, name: str) -> dict[str, str]` — Compose original environment semantics dependency-first.
  - `tools(self) -> dict[str, tuple[str, dict[str, str]]]` — Discover preserved tool declarations from catalog metadata.
  - `command(self, tool: str, args: list[str]) -> tuple[list[str], dict[str, str]]` — Resolve original Python/Node/binary/probe invocation semantics.
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
  - `progress` = `0.0`
  - `step` = `''`
  - `detail` = `''`
  - `run_id` = `None`
  - `started_at` = `None`
  - `finished_at` = `None`
  - `elapsed_seconds` = `0.0`
  - `extra` = `field(default_factory=dict)`
  - Fields: `name: str`, `status: str`
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the record as one ``exactus-run/v1`` items entry.
- `class RunDocument` — Describe one uniform ``exactus-run/v1`` live-run document.
  - `progress` = `0.0`
  - `completed` = `0`
  - `total` = `0`
  - `step` = `''`
  - `detail` = `''`
  - `run_id` = `None`
  - `pipeline_run_id` = `None`
  - `pid` = `None`
  - `started_at` = `None`
  - `updated_at` = `None`
  - `finished_at` = `None`
  - `elapsed_seconds` = `0.0`
  - `items` = `()`
  - `extra` = `field(default_factory=dict)`
  - Fields: `kind: str`, `name: str`, `status: str`
  - `payload(self: Self) -> dict[str, JsonValue]` — Serialize the document for a progress artifact file.

### `readmes.py`

Generate directory documentation for offline distribution assets.

- `directory_readme(*, name: str) -> str` — Describe one generated asset directory.
- `write_directory_readmes(*, root: Path) -> None` — Document public asset directories while preserving existing docs.

### `shims.py`

Generate ``exactus.vendor.<name>`` shims for bundled distributions.

- `class Constants` — Group module-level constants.
  - `package` = `Path(__file__).resolve().parents[2]`
  - `bundle` = `package / 'bundle'`
  - `skip_names` = `frozenset({'__pycache__'})`
  - `skip_vendor` = `frozenset({'basedpyright', 'nodejs_wheel', 'playwright', 'pyrefly', 'ruff'})`
  - `ignore` = `('.DS_Store', '__pycache__', '*.dist-info', '*.egg-info', '*.pyc', '*.pyo...`
  - `module_overrides` = `{'jaraco.classes': 'jaraco.classes', 'jaraco_context': 'jaraco.context',...`
  - `extra_modules` = `{'attrs': ('attr',), 'python_multipart': ('multipart',)}`
  - `swap_only` = `frozenset({'pytest', 'typing_extensions'})`
  - `drop_common` = `frozenset({'benchmarks', 'conftest', 'test', 'tests'})`
  - `unstubbed` = `frozenset({'basedpyright', 'jsonschema_specifications', 'multipart', 'pyc...`
  - `drop_names` = `{'anyio': frozenset({'wait_socket_readable', 'wait_socket_writable'}), 'd...`
  - `any_names` = `{'cffi': frozenset({'gen_src'}), 'charset_normalizer': frozenset({'from_p...`
  - `builtins` = `frozenset(dir(import_module(name='builtins')))`
  - `probe_env_drop` = `frozenset({'COVERAGE_PROCESS_CONFIG', 'COVERAGE_PROCESS_START'})`
  - `startup_hooks` = `frozenset({'pth_file', 'sitecustomize', 'usercustomize'})`
  - `header` = `'# Copyright (c) 2026\n'`
  - `base_imports` = `dedent(text='    from importlib import import_module\n    from importlib....`
  - `loader_head` = `dedent(text='    if (\n        _existing := _modules.get(\n            {n...`
  - `name_stem` = `'_name := (_file := Path(__file__).resolve()).stem,'`
  - `name_literal` = `'_name := "{module}",'`
  - `file_literal` = `'_file: Path = Path(__file__).resolve()\n'`
- `bundled_distributions(*, bundle: Path) -> list[str]` — Collect the union of Python distributions in bundle manifests.
- `public_names(*, module: str) -> list[str] | None` — Return the module's re-exportable public names, or ``None``.
- `generate(*, package: Path) -> list[Path]` — Write all shim files under ``<package>/vendor``.
- `main() -> int` — Regenerate every shim and print the written file count.

## Examples

Runnable demonstration for `exactus/packages/package/`.

```bash
python -m exactus.packages.package.examples
```

Files: `examples/README.md`, `examples/api/README.md`, `examples/api/__init__.py`, `examples/api/__main__.py`, `examples/api/run.py`, `examples/cli/README.md`, `examples/cli/__init__.py`, `examples/cli/__main__.py`, `examples/cli/run.py`

## Dependencies and consumers

- Other packages: [`bundle`](../../bundle/DOCS.md), [`argument_parser`](../argument_parser/DOCS.md), [`completion`](../completion/DOCS.md), [`tree`](../tree/DOCS.md), [`zstd_portable`](../zstd_portable/DOCS.md), [`actions`](../../tools/actions/DOCS.md), [`common`](../../tools/common/DOCS.md)
- Used by: `__main__.py`, `bundle/linux/glibc/amd64/partition_launcher.py`, `bundle/linux/glibc/arm64/partition_launcher.py`, `bundle/linux/musl/amd64/partition_launcher.py`, `bundle/linux/musl/arm64/partition_launcher.py`, `bundle/macos/amd64/partition_launcher.py`, `bundle/macos/arm64/partition_launcher.py`, `bundle/windows/amd64/partition_launcher.py`, `bundle/windows/arm64/partition_launcher.py`, `tests/packages/package/test_inventory_cli.py`, `tests/packages/package/test_package_api.py`, `tests/packages/package/test_package_build.py`, `tests/packages/package/test_package_cli.py`, `tests/packages/package/test_package_config.py`, `tests/packages/package/test_package_install.py`, `tests/packages/package/test_package_shims.py`, `tests/packages/package/test_partition_fs.py`, `tests/standalone/test_standalone.py`, `tests/tools/common/test_common.py`, `tests/tools/common/test_toolkit.py`

## Tests

Tests live in `exactus/tests/packages/package/`.

- `test_inventory_cli.py` — ANSI-styled ``--help`` formatting shared by the root scripts. (14 tests)
  - `test_format_help_plain_without_tty`
  - `test_format_help_styles_headings`
  - `test_format_help_styles_usage_and_prog`
  - `test_formatter_is_pretty`
  - `test_invocation_paints_option_flags`
  - `test_invocation_paints_positionals`
  - `test_invocations_plain_without_tty`
  - `test_paint_passes_empty_text`
  - `test_paint_passes_text_without_tty`
  - `test_paint_wraps_text_on_tty`
  - `test_pretty_parser_renders_dimmed_epilog`
  - `test_styled_honours_no_color`
  - `test_styled_is_false_without_tty`
  - `test_styled_is_true_on_tty`
- `test_package_api.py` — Tests for the unified package Python API. (12 tests)
  - `test_build_collects_every_output`
  - `test_build_expands_target_aliases`
  - `test_build_falls_back_to_auto_host_target`
  - `test_build_raises_on_unknown_target`
  - `test_build_raises_when_auto_target_missing`
  - `test_bundle_builds_requested_targets`
  - `test_bundle_rejects_multi_target_output`
  - `test_load_config_reads_all_stages`
  - `test_package_archives_project_and_documents`
  - `test_package_honours_explicit_output`
  - `test_run_defaults_to_package`
  - `test_run_orders_selected_stages`
- `test_package_build.py` — Tests for Exactus executable staging. (35 tests)
  - `test_build_artifacts_stage_full_pipeline`
  - `test_build_file_config_parses_tables_and_flags`
  - `test_build_file_config_rejects_bad_types`
  - `test_build_main_dispatches_selected_artifacts`
  - `test_build_parser_and_exec_target_resolution`
  - `test_build_rmtree_retry_restores_permissions`
  - `test_build_stages_native_payloads_and_validates`
  - `test_bundle_browser_installers_and_dedupe`
  - `test_bundle_build_reuses_payloads_and_emits_incremental_updates`
  - `test_bundle_cache_boundaries`
  - `test_bundle_component_and_target_selection`
  - `test_bundle_directory_descriptions`
  - `test_bundle_document_and_cli_resolution`
  - `test_bundle_fetch_enforces_limits_and_retries`
  - `test_bundle_file_config_rejects_invalid_types`
  - `test_bundle_file_config_resolves_relative_paths`
  - `test_bundle_filesystem_helpers`
  - `test_bundle_installers_stage_runtimes`
  - `test_bundle_main_builds_selected_targets`
  - `test_bundle_payload_dedupe_prune_and_stage`
  - `test_bundle_readmes_preserve_existing_prose_and_detect_catalogs`
  - `test_bundle_readmes_recurse_without_touching_private_or_linked_trees`
  - `test_bundle_size_labels`
  - `test_bundle_target_leaf_filtering`
  - `test_catalog_tools_reads_component_metadata`
  - `test_closure_orders_dependencies_first`
  - `test_closure_rejects_cyclic_dependencies`
  - `test_closure_rejects_missing_component`
  - `test_stage_package_keeps_complete_package_tree`
  - `test_tool_version_prefix_matches_dist_names`
  - `test_tool_version_resolves_each_dispatch_kind`
  - `test_usable_cache_root_accepts_writable_dir`
  - `test_usable_cache_root_rejects_lock_dir`
  - `test_usable_cache_root_rejects_symlink`
  - `test_write_manifest_lists_targets_and_tools`
- `test_package_cli.py` — Tests for the unified package CLI. (3 tests)
  - `test_cli_field_override_preserves_other_pyproject_values`
  - `test_cli_stage_flags_are_exact_and_order_independent`
  - `test_inventory_help_respects_terminal_and_no_color`
- `test_package_config.py` — Tests for the package pipeline configuration loader. (19 tests)
  - `test_bundle_output_path_is_resolved`
  - `test_empty_project_returns_defaults`
  - `test_load_config_non_dict_tool_returns_defaults`
  - `test_load_config_rejects_bool_part_bytes`
  - `test_load_config_rejects_non_bool_enabled`
  - `test_load_config_rejects_non_boolean`
  - `test_load_config_rejects_non_dict_package`
  - `test_load_config_rejects_non_dict_stage`
  - `test_load_config_rejects_non_int_part_bytes`
  - `test_load_config_rejects_non_integer_part_bytes`
  - `test_load_config_rejects_non_list_targets`
  - `test_load_config_rejects_non_string_list_items`
  - `test_load_config_rejects_non_string_list_members`
  - `test_load_config_rejects_non_string_node_version`
  - `test_load_config_rejects_non_string_output`
  - `test_load_config_rejects_non_string_path`
  - `test_load_config_rejects_non_table_package`
  - `test_load_config_rejects_non_table_stage`
  - `test_load_config_rejects_non_table_tool`
- `test_package_install.py` — Tests for system-wide installation of the built executable. (46 tests)
  - `test_ansi_enabled_requires_capable_terminal`
  - `test_build_release_never_writes_archive`
  - `test_build_release_produces_full_directory`
  - `test_create_parser_accepts_rebuild`
  - `test_host_platform_maps_known_systems`
  - `test_host_platform_rejects_unknown_arch`
  - `test_host_platform_rejects_unknown_system`
  - `test_host_target_rejects_unsupported`
  - `test_host_target_selects_linux_libc`
  - `test_host_target_selects_simple_names`
  - `test_install_completion_advances_ui`
  - `test_install_completion_registers_each_profile`
  - `test_install_completion_reports_failures`
  - `test_install_posix_copies_into_system_dir`
  - `test_install_posix_creates_missing_dir_via_sudo`
  - `test_install_posix_escalates_through_sudo`
  - `test_install_posix_skips_same_file`
  - `test_install_system_dispatches_windows`
  - `test_install_system_drives_ui_sequence`
  - `test_install_system_marks_failed_step`
  - `test_install_system_paints_banner_and_steps`
  - `test_install_system_rebuild_flag_forces_build`
  - `test_install_system_rebuilds_stale_release`
  - `test_install_system_registers_completion`
  - `test_install_system_reinstalls_running_archive`
  - `test_install_system_rejects_bundled_rebuild`
  - `test_install_system_uses_existing_release`
  - `test_install_windows_writes_pyz_and_shim`
  - `test_release_name_matches_bin_layout`
  - `test_remove_posix_escalates_through_sudo`
  - `test_remove_posix_reports_absent_and_removes`
  - `test_run_reports_failures`
  - `test_run_reports_install_and_uninstall`
  - `test_running_archive_detects_zipapp`
  - `test_running_archive_ignores_source_entries`
  - `test_uninstall_completion_removes_registrations`
  - `test_uninstall_system_dispatches_windows`
  - `test_uninstall_system_removes_completion`
  - `test_uninstall_system_removes_posix_install`
  - `test_uninstall_system_reports_missing_install`
  - `test_uninstall_windows_removes_directory_and_path`
  - `test_windows_directory_prefers_program_files`
  - `test_windows_path_entries_open_failure`
  - `test_windows_path_update_adds_and_removes`
  - `test_windows_path_update_requires_write_access`
  - `test_windows_path_update_skips_existing_entry`
- `test_package_shims.py` — Tests for generated bundled-distribution import shims. (2 tests)
  - `test_public_names_drops_startup_hook_names`
  - `test_quiet_probe_drops_coverage_process_start`
- `test_partition_fs.py` — Tests for the content-addressed partition filesystem. (11 tests)
  - `test_partition_catalog_rejections`
  - `test_partition_coercion_and_path_rejections`
  - `test_partition_garbage_collect`
  - `test_partition_materialize_rejections`
  - `test_partition_pack_codec`
  - `test_partition_recipe_rejections`
  - `test_partition_scan_pack_and_materialize`
  - `test_partition_scanner_rejections`
  - `test_partition_store_verify_and_recover`
  - `test_partition_update_and_rollback`
  - `test_partition_zip_update_rejections`

<!-- exactus:reference:end -->
