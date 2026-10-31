# bundle/

Platform-specific offline tool bundles and packaged-executable freshness
checks. `python -m exactus.bundle` dispatches to the host's leaf, and
`from exactus.bundle import <module>` routes to the same leaf's module.

## Files

| File | Description |
|---|---|
| `__init__.py` | Host detection (`host_leaf()`), musl→glibc fallback, and `__getattr__` routing so `from exactus.bundle import partition_fs` resolves the host leaf's module. |
| `__main__.py` | Host dispatch: reuses `host_leaf()` and forwards to the matching leaf's `__main__.py`. |
| `content.py` | Render `CONTENT.md` inventories for staged bundle roots: reads each target leaf's `data/bundle.json` manifest and lists the operating systems, architectures and installed tool versions so a staged tree documents itself. |
| `CONTENT.md` | Generated inventory produced by `content.py` — OS/architecture/tool-version listing for the staged bundle tree. |
| `freshness.py` | Detect when a packaged `exactus` is older than its source tree; warns the user the bundle may be stale. |

## Layout

```
bundle/
├── linux/
│   ├── glibc/<arch>/   # glibc Linux bundles
│   └── musl/<arch>/    # musl (e.g. Alpine) bundles — no browser group
├── macos/<arch>/       # macOS bundles
└── windows/<arch>/     # Windows bundles
```

Each leaf is produced by `scripts/bundle_make` and contains a schema-5
partition launcher (`__main__.py`), the `data/parts/fs/catalog.json`
component catalog, content-addressed packs, and bundled
`zstd_portable/bin/` binaries.

## Host selection

- `linux` resolves glibc vs musl via `platform.libc_ver()` and
  `ld-musl-*.so*` loader probing; musl hosts get the musl leaf, everyone
  else the glibc leaf.
- `from exactus.bundle import <name>` resolves the host leaf through a
  package `__getattr__`: `partition_fs`, `partition_launcher`,
  `conflict_copies` and `zstd_portable` import from
  `exactus.bundle.<os>.<arch>` without callers naming the platform. The
  resolved module is cached on the package; unknown names raise
  `AttributeError`, and import failures *inside* a leaf module
  propagate rather than masquerading as missing attributes.
- The same ordered candidate list is used at runtime by
  `tools/common/cli.py::_host_bundle_dirs` when resolving tool bundles
  from `root/bundle`, `root/exactus/bundle` or the packaged
  `exactus/bundle` resource anchor.
- The `lints` tool binds every `all_lints` spec to this resolved host launcher
  when a standalone command is missing. This covers Ruff/Ruff-doc checks,
  BasedPyright, Pyrefly, ESLint, Stylelint, HTMLHint and TypeScript (`tsc`)
  without duplicating their execution or parsing logic in the lints tool.

## Notes

- `<leaf>.update/` siblings hold incremental update payloads (new packs
  + identities) emitted by `bundle_make --rebuild`.
- Bundle leaves ship their `data/` catalogs via `pyproject.toml`
  package-data globbing, so they survive wheel/zipapp packaging.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `CONTENT.md` | — |
| `README.md` | Package readme. |
| `__init__.py` | Packaged executable fingerprints, freshness checks, and host routing. |
| `__main__.py` | Dispatch ``python -m exactus.bundle`` to the host platform bundle. |
| `content.py` | Render ``CONTENT.md`` inventories for staged bundle roots. |
| `freshness.py` | Detect a packaged ``exactus`` that is older than its source tree. |
| `linux/` | Subdirectory. |
| `macos/` | Subdirectory. |
| `windows/` | Subdirectory. |

Run it as a module: `python -m exactus.exactus.bundle`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Packaged executable fingerprints, freshness checks, and host routing.

- `host_leaf() -> Path | None` — Return the bundle leaf package directory matching this host.

### `__main__.py`

Dispatch ``python -m exactus.bundle`` to the host platform bundle.

- `main() -> int` — Run the host platform bundle dispatcher.

### `content.py`

Render ``CONTENT.md`` inventories for staged bundle roots.

- `content_markdown(*, targets: list[_Target]) -> str` — Render the inventory document for staged targets.
- `write_content(*, root: Path) -> Path | None` — Write ``CONTENT.md`` for a staged bundle root.

### `freshness.py`

Detect a packaged ``exactus`` that is older than its source tree.

- `tree_signature(*, exactus_dir: Path) -> dict[str, str]` — Fingerprint every packaged file under ``exactus_dir``.
- `render_signature(*, exactus_dir: Path) -> bytes` — Serialize a directory fingerprint for the build stamp.
- `bundle_signature(*, bundle: Path) -> dict[str, str] | None` — Read the packaged-source fingerprint stored inside a zipapp.
- `dev_project_root(*, bundle: Path) -> Path | None` — Locate the development project that produced an executable.
- `bundle_stale(*, bundle: Path, exactus_dir: Path) -> bool` — Return whether a built zipapp predates the live source tree.
- `warn_if_stale(*, stream: TextIO | None=None) -> None` — Print the staleness warning when the bundle is older than sources.

### `linux/__init__.py`

Provide the generated tool-bundle namespace.


### `linux/glibc/__init__.py`

Provide the generated tool-bundle namespace.


### `linux/glibc/amd64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `linux/glibc/amd64/__main__.py`

Offline partitioned filesystem dispatcher.


### `linux/glibc/amd64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `linux/glibc/amd64/partition_fs.py`

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

### `linux/glibc/amd64/partition_launcher.py`

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

### `linux/glibc/amd64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `linux/glibc/amd64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `linux/glibc/arm64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `linux/glibc/arm64/__main__.py`

Offline partitioned filesystem dispatcher.


### `linux/glibc/arm64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `linux/glibc/arm64/partition_fs.py`

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

### `linux/glibc/arm64/partition_launcher.py`

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

### `linux/glibc/arm64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `linux/glibc/arm64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `linux/musl/__init__.py`

Provide the generated tool-bundle namespace.


### `linux/musl/amd64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `linux/musl/amd64/__main__.py`

Offline partitioned filesystem dispatcher.


### `linux/musl/amd64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `linux/musl/amd64/partition_fs.py`

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

### `linux/musl/amd64/partition_launcher.py`

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

### `linux/musl/amd64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `linux/musl/amd64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `linux/musl/arm64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `linux/musl/arm64/__main__.py`

Offline partitioned filesystem dispatcher.


### `linux/musl/arm64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `linux/musl/arm64/partition_fs.py`

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

### `linux/musl/arm64/partition_launcher.py`

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

### `linux/musl/arm64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `linux/musl/arm64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `macos/__init__.py`

Provide the generated tool-bundle namespace.


### `macos/amd64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `macos/amd64/__main__.py`

Offline partitioned filesystem dispatcher.


### `macos/amd64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `macos/amd64/partition_fs.py`

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

### `macos/amd64/partition_launcher.py`

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

### `macos/amd64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `macos/amd64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `macos/arm64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `macos/arm64/__main__.py`

Offline partitioned filesystem dispatcher.


### `macos/arm64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `macos/arm64/partition_fs.py`

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

### `macos/arm64/partition_launcher.py`

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

### `macos/arm64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `macos/arm64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `windows/__init__.py`

Provide the generated tool-bundle namespace.


### `windows/amd64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `windows/amd64/__main__.py`

Offline partitioned filesystem dispatcher.


### `windows/amd64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `windows/amd64/partition_fs.py`

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

### `windows/amd64/partition_launcher.py`

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

### `windows/amd64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `windows/amd64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

### `windows/arm64/__init__.py`

Provide the generated partitioned offline tool runtime.


### `windows/arm64/__main__.py`

Offline partitioned filesystem dispatcher.


### `windows/arm64/conflict_copies.py`

Reconcile numbered sync copies without discarding unique project data.

- `class Constants` — Group module-level constants.
  - `ignored` = `frozenset({'.history', 'node_modules', 'venv', '__pycache__', 'exactus/pa...`
- `class ClearResult` — Describe reconciled sync copies and recoverable conflicts.
  - `removed_directories` = `0`
  - `merged_entries` = `0`
  - `preserved_conflicts` = `0`
  - `errors` = `0`
- `clear_conflict_copies(*, root: Path) -> ClearResult` — Reconcile numbered directories with existing canonical counterparts.

### `windows/arm64/partition_fs.py`

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

### `windows/arm64/partition_launcher.py`

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

### `windows/arm64/zstd_portable/__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', 'x86_6...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - `level` = `3`
  - `threads` = `0`
  - `progress` = `None`
  - `expected_size` = `None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `__init__(self, *, file: str | Path, mode: OpenMode='w', options: ZstdOptions | None=None, overwrite: bool=True, cache: str | Path | None=None) -> None` — Initialize a streaming Zstandard reader or writer.
  - `bytes_written(self) -> int` — Source bytes written.
  - `progress(self) -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read(self) -> int` — Decompressed bytes read.
  - `closed(self) -> bool` — Whether this stream is closed.
  - `readable(self) -> bool` — Return whether this stream supports reading.
  - `writable(self) -> bool` — Return whether this stream supports writing.
  - `open(self) -> None` — Start the bundled compressor or decompressor.
  - `write(self, data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(self, size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(self, buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush(self) -> None` — Flush pending Python-side input to the compressor pipe.
  - `close(self) -> None` — Finalize compression or decompression.

### `windows/arm64/zstd_portable/directory_inventory.py`

Maintain a managed, bottom-up directory inventory in README documents.

- `class Constants` — Group module-level constants.
  - `start` = `'<!-- exactus:inventory:start -->'`
  - `end` = `'<!-- exactus:inventory:end -->'`
  - `max_text_bytes` = `1 << 20`
  - `inventory_blocks` = `compile_pattern(pattern='<!-- (?P<owner>exactus|audit):inventory:start --...`
- `description(*, path: Path) -> str` — Summarize a file's docstring or a child directory's README introduction.
- `entry_line(*, entry: Path) -> str` — Render one relative link and description in the standard list format.
- `heal_directory(*, directory: Path, entries: list[Path]) -> None` — Consolidate generated inventories while preserving authored prose.

## Dependencies and consumers

- Other packages: [`package`](../packages/package/DOCS.md), [`zstd_portable`](../packages/zstd_portable/DOCS.md), [`common`](../tools/common/DOCS.md)
- Used by: `__main__.py`, `packages/package/api.py`, `packages/package/build.py`, `packages/package/bundle.py`, `packages/package/install.py`, `tests/bundle/test_freshness.py`, `tests/packages/zstd_portable/test_zstd.py`, `tests/standalone/test_standalone.py`, `tests/tools/common/test_conflict_copies.py`

## Tests

Tests live in `exactus/tests/bundle/`.

- `test_freshness.py` — Staleness detection for the packaged ``exactus`` executable. (17 tests)
  - `test_bundle_signature_absent`
  - `test_bundle_signature_round_trip`
  - `test_bundle_stale_flags_every_drift`
  - `test_bundle_stale_ignores_staged_vendor`
  - `test_dev_project_root_detects_release_layout`
  - `test_dev_project_root_detects_repository`
  - `test_dev_project_root_rejects_foreign_layout`
  - `test_render_signature_deterministic`
  - `test_tree_signature_fingerprints_sources`
  - `test_tree_signature_skips_generated_reports`
  - `test_warn_if_stale_after_source_addition`
  - `test_warn_if_stale_after_source_edit`
  - `test_warn_if_stale_extra_payload_ignored`
  - `test_warn_if_stale_fresh`
  - `test_warn_if_stale_missing_stamp`
  - `test_warn_if_stale_outside_project`
  - `test_warn_if_stale_script_invocation`
- `test_host.py` — Host routing and package dispatch for the bundled executables. (5 tests)
  - `test_bundle_main_missing_and_dispatch`
  - `test_dir_includes_host_modules`
  - `test_host_leaf_candidates`
  - `test_host_leaf_uses_existing_fallback`
  - `test_lazy_import_and_missing_attribute`

<!-- exactus:reference:end -->
