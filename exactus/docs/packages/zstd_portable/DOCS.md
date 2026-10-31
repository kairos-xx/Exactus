# zstd_portable/

Portable Zstandard CLI wrapper with lazy zipped-binary extraction. Ships
compressed `zstd` binaries under `bin/` per platform and extracts the
matching one on first use, so callers get a real `zstd` executable
without a system install.

## Behavior

- Binary selection follows the host OS/architecture.
- Extraction is lazy and cached — the zip is only unpacked the first
  time the binary is needed.
- The same binaries are bundled inside the offline tool bundles under
  `exactus/bundle/<os>/<arch>/zstd_portable/bin/`, so bundled
  environments can compress/decompress packs without a system `zstd`.

<!-- exactus:reference:start -->

## Package layout

| Path | Description |
|---|---|
| `README.md` | Package readme. |
| `__init__.py` | Portable Zstandard CLI wrapper with lazy zipped-binary extraction. |
| `__main__.py` | Run the zstd_portable demo through the project virtualenv. |
| `examples/` | Runnable demonstration for `exactus/packages/zstd_portable/`. |
| `py.typed` | PEP 561 marker declaring that the package ships inline type annotations. |

Run it as a module: `python -m exactus.packages.zstd_portable`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

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

### `__main__.py`

Run the zstd_portable demo through the project virtualenv.


### `examples/__init__.py`

Runnable examples for ``exactus.packages.zstd_portable``.


### `examples/__main__.py`

Run the zstd_portable example in the project virtualenv.


### `examples/example.py`

Binary streaming compression/decompression progress demo.

- `class Constants` — Group module-level constants.
  - `mib` = `1024 * 1024`
  - `source_size` = `500 * mib`
  - `chunk_size` = `1 * mib`
- `progress(percent: float | None, status: str) -> None` — Display Zstandard operation progress.
- `create_binary(target: Path) -> None` — Create the configured binary file without a large allocation.
- `main(*, directory: Path | None=None) -> None` — Run a binary Zstandard round-trip with live progress.

### `examples/run.py`

Run the portable Zstandard round-trip example.

- `main() -> int` — Execute the example and return a successful process status.

## Examples

Runnable demonstration for `exactus/packages/zstd_portable/`.

Run the portable Zstandard round-trip example.

```bash
python -m exactus.packages.zstd_portable.examples
```

Files: `examples/README.md`, `examples/__init__.py`, `examples/__main__.py`, `examples/example.py`, `examples/run.py`

## Dependencies and consumers

- Other packages: [`common`](../../tools/common/DOCS.md)
- Used by: `bundle/linux/glibc/amd64/partition_fs.py`, `bundle/linux/glibc/arm64/partition_fs.py`, `bundle/linux/musl/amd64/partition_fs.py`, `bundle/linux/musl/arm64/partition_fs.py`, `bundle/macos/amd64/partition_fs.py`, `bundle/macos/arm64/partition_fs.py`, `bundle/windows/amd64/partition_fs.py`, `bundle/windows/arm64/partition_fs.py`, `packages/package/build.py`, `packages/package/bundle.py`, `packages/package/partition_fs.py`, `tests/packages/package/test_partition_fs.py`, `tests/packages/zstd_portable/test_directory_inventory.py`, `tests/packages/zstd_portable/test_example.py`, `tests/packages/zstd_portable/test_zstd.py`, `tests/tools/common/test_common.py`

## Tests

Tests live in `exactus/tests/packages/zstd_portable/`.

- `test_directory_inventory.py` — Cover the shared directory-inventory helper and its bundle export. (7 tests)
  - `test_description_extracts_script_docblock`
  - `test_entry_line_links_directories_to_their_readme`
  - `test_exported_package_ships_the_canonical_helper`
  - `test_heal_directory_marks_empty_sections`
  - `test_heal_directory_replaces_managed_block_only`
  - `test_heal_directory_seeds_readme_from_first_candidate`
  - `test_heal_directory_skips_history_trees`
- `test_example.py` — The ``examples/example.py`` demo round-trips a scratch binary. (3 tests)
  - `test_create_binary_writes_configured_chunks`
  - `test_example_round_trips_scratch_binary`
  - `test_progress_renders_status_and_percent`
- `test_zstd.py` — Tests of the portable Zstandard CLI wrapper. (21 tests)
  - `test_context_exit_failures`
  - `test_corrupt_stream_fails`
  - `test_executable_cache`
  - `test_expected_size_mismatch`
  - `test_export_binary`
  - `test_export_binary_rejects_unsupported`
  - `test_exported_package_readmes`
  - `test_feed_and_stderr_without_process`
  - `test_invalid_payload_contents`
  - `test_large_corrupt_input_feeds_until_pipe_breaks`
  - `test_missing_compressed_input`
  - `test_open_guards`
  - `test_options_validation`
  - `test_partial_read_close`
  - `test_platform_normalization`
  - `test_platform_normalization_rejects_unknown_values`
  - `test_roundtrip_and_counters`
  - `test_stderr_details_in_failure`
  - `test_stream_method_guards`
  - `test_unsupported_platforms`
  - `test_zero_expected_size`

<!-- exactus:reference:end -->
