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
| `examples/` | Run the streaming round-trip from the repository root: ```bash python -m exactus.packages.zstd_portable.examples |
| `py.typed` | — |

Run it as a module: `python -m exactus.packages.zstd_portable`.

## Python API reference

Public classes, functions and constants, read from the source. Private names (leading underscore) are omitted.

### `__init__.py`

Portable Zstandard CLI wrapper with lazy zipped-binary extraction.

- `class Constants` — Group module-level constants.
  - `version` = `'1.5.7'`
  - `max_level` = `22`
  - `targets` = `{('darwin', 'arm64'): ('macos-universal2.zip', 'zstd'), ('darwin', ...`
- `export_package(*, os_name: str, machine: str, target: Path) -> Path` — Stage this package plus the target's payload into ``target``.
- `export_binary(*, os_name: str, machine: str, target: Path) -> Path` — Extract the native CLI binary for an explicit platform.
- `class ProgressCallback(Protocol)` — Progress sink invoked with a percent and a status label.
- `class ZstdOptions` — Compression and progress options for :class:`Zstd`.
  - Fields: `level: int`, `threads: int`, `progress: ProgressCallback | None`, `expected_size: int | None`
- `class Zstd` — Stream data through a bundled native Zstandard CLI.
  - `bytes_written() -> int` — Source bytes written.
  - `progress() -> float | None` — Source-input progress from zero through one hundred.
  - `bytes_read() -> int` — Decompressed bytes read.
  - `closed() -> bool` — Whether this stream is closed.
  - `readable() -> bool` — Return whether this stream supports reading.
  - `writable() -> bool` — Return whether this stream supports writing.
  - `open() -> None` — Start the bundled compressor or decompressor.
  - `write(data: bytes | bytearray | memoryview) -> int` — Write uncompressed bytes to a compression stream.
  - `read(size: int=-1) -> bytes` — Read decompressed bytes from a decompression stream.
  - `readinto(buffer: bytearray | memoryview) -> int` — Read decompressed bytes directly into a writable buffer.
  - `flush() -> None` — Flush pending Python-side input to the compressor pipe.
  - `close() -> None` — Finalize compression or decompression.

## Examples

Run the streaming round-trip from the repository root:

```bash
python -m exactus.packages.zstd_portable.examples
```

Files: `__init__.py`, `__main__.py`, `example.py`, `run.py`

## Dependencies and consumers

- Tools: `exactus.tools.common`
- Used by: `packages/package/bundle.py`, `packages/package/partition_fs.py`, `tests/tools/common/test_common.py`

## Tests

Tests live in `exactus/tests/packages/zstd_portable/`.

- `test_directory_inventory.py` — Cover the shared directory-inventory helper and its bundle export. (7 tests)
  - `test_exported_package_ships_the_canonical_helper`
  - `test_description_extracts_script_docblock`
  - `test_heal_directory_skips_history_trees`
  - `test_heal_directory_seeds_readme_from_first_candidate`
  - `test_heal_directory_marks_empty_sections`
  - `test_heal_directory_replaces_managed_block_only`
  - `test_entry_line_links_directories_to_their_readme`
- `test_example.py` — The ``examples/example.py`` demo round-trips a scratch binary. (3 tests)
  - `test_progress_renders_status_and_percent`
  - `test_create_binary_writes_configured_chunks`
  - `test_example_round_trips_scratch_binary`
- `test_zstd.py` — Tests of the portable Zstandard CLI wrapper. (21 tests)
  - `test_platform_normalization`
  - `test_platform_normalization_rejects_unknown_values`
  - `test_options_validation`
  - `test_roundtrip_and_counters`
  - `test_zero_expected_size`
  - `test_open_guards`
  - `test_stream_method_guards`
  - `test_missing_compressed_input`
  - `test_partial_read_close`
  - `test_expected_size_mismatch`
  - `test_corrupt_stream_fails`
  - `test_context_exit_failures`
  - `test_executable_cache`
  - `test_unsupported_platforms`
  - `test_invalid_payload_contents`
  - `test_feed_and_stderr_without_process`
  - `test_stderr_details_in_failure`
  - `test_large_corrupt_input_feeds_until_pipe_breaks`
  - `test_export_binary`
  - `test_export_binary_rejects_unsupported`
  - `test_exported_package_readmes`

<!-- exactus:reference:end -->
