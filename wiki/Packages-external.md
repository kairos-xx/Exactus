[Home](Home.md) > [Packages](Packages.md) > external

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/external/`](../exactus/packages/external/) | [`exactus/tests/packages/external/`](../exactus/tests/packages/external/) | [`DOCS.md`](../exactus/docs/packages/external/DOCS.md) |

[< Packages-extended_selector](Packages-extended_selector.md) · [Packages index](Packages.md) · [Packages-group_final >](Packages-group_final.md)
