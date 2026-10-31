# packages/external/

Bundled-toolchain listing and dispatch, exposed as `exactus --external`.

## Files

| File | Description |
|---|---|
| `cli.py` | `exactus --external` prints the bundled toolchain grouped by runtime — OS payloads and binary tools, Python packages, and Node packages — with the versions recorded in the leaf manifest. `exactus --external TOOL [ARGS...]` forwards the command line to the bundle's partition launcher, which materializes the component and runs the tool under the executable's own interpreter. |

## Behavior

- `resolve_exactus_tool_bundle` locates the host bundle leaf; when no
  bundle or manifest is available the command reports that instead of
  guessing at a toolchain.
- Dispatch materializes only the requested component through the
  partition launcher, so a cold run unpacks a single pack rather than
  the whole toolchain.
- Listing reads the leaf manifest recorded at bundle time, so reported
  versions always match the payloads the executable actually carries.
