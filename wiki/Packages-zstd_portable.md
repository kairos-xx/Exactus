[Home](Home.md) > [Packages](Packages.md) > zstd_portable

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/zstd_portable/`](../exactus/packages/zstd_portable/) | [`exactus/tests/packages/zstd_portable/`](../exactus/tests/packages/zstd_portable/) | [`DOCS.md`](../exactus/docs/packages/zstd_portable/DOCS.md) |

[< Packages-zip_components](Packages-zip_components.md) · [Packages index](Packages.md)
