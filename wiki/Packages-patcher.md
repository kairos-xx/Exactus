[Home](Home.md) > [Packages](Packages.md) > patcher

# `exactus.packages.patcher`

`exactus.packages.patcher` builds deterministic executable `.pyz` filesystem deltas and
applies them transactionally.

## Sources

Either side of a delta may be a directory, ZIP archive, or a `.pyz` produced
by this package. Sources are normalized into a virtual project snapshot before
comparison.

## Basic API

```python
from exactus.packages.patcher import PyzProjectPatch

patch = PyzProjectPatch.delta(
    a="/tmp/project-before",
    b="/tmp/project-after.zip",
    project_root="/srv/project",
)
patch.build(output="update.pyz")
```

The resulting PYZ contains the changed/added content plus manifest operations
for removals, moves, directories, symlinks and metadata.

## Runtime root

Without `--root`, the embedded project root is used.

An explicit `--root` always overrides the embedded root. Absolute paths remain
absolute. Relative paths are resolved against the **process invocation working
directory**, not against the location of the `.pyz`.

For example, if the shell is currently in `/srv/project`:

```console
$ /home/me/Downloads/update.pyz --root .
```

the effective root is `/srv/project`.

The same is true for:

```console
$ python /home/me/Downloads/update.pyz --root .
```

This behavior deliberately follows normal command-line path semantics.

## Inspection and safety

```console
update.pyz --dry-run
update.pyz --verify
update.pyz --list
update.pyz --info
update.pyz --json
update.pyz --conflict abort
update.pyz --conflict overwrite
update.pyz --conflict skip
update.pyz --conflict backup
update.pyz --force
```

Application validates paths and hashes before mutation, stages changes,
commits them transactionally, verifies the resulting state, and rolls back
committed operations when application fails.

## Reversal

Reversible patches retain the required before-state blobs:

```python
rollback = patch.inverse()
rollback.build(output="rollback.pyz")
```

Set `reversible=False` at build time when minimizing archive size is more
important than standalone inversion.

## Composition

Compatible patches can be composed:

```python
ac = ab.compose(next_patch=bc)
ac.build(output="a-to-c.pyz")
```

## Filtering

Use the package include/exclude facilities when constructing snapshots to omit
cache/build/packages paths that are outside the desired patch scope.

## Example

The comprehensive example can be invoked equivalently as:

```console
exactus/packages/patcher/examples/run.py
python exactus/packages/patcher/examples
python -m exactus.packages.patcher.examples
```

Run those commands from the repository root so `exactus` is importable.

## Validation

The tests cover source normalization, delta generation/application,
reversibility, deterministic builds, and invocation-directory-relative
`--root .` behavior. Production coverage is intended to remain at or above
90%.

## Self-contained patcher CLI (`--bin`)

Build the patcher itself as a standalone executable PYZ:

```console
python -m exactus.packages.patcher --project-root . --bin
```

This creates `./bin/patcher.pyz`. `--bin-dir` defaults to `bin` under the
selected project root and may be overridden with either a project-root-relative
or absolute directory:

```console
python -m exactus.packages.patcher --project-root . --bin --bin-dir tools
python -m exactus.packages.patcher --project-root . --bin --bin-dir /opt/patch-tools
```

The generated binary exposes the same exhaustive builder CLI:

```console
./bin/patcher.pyz --help
./bin/patcher.pyz --a old --b new --project-root . --output update.pyz
```

The equivalent Python API is `PatcherCli.build_binary(...)`. Delta construction
is available through both `PatcherCli.build_delta(...)` and the lower-level
`PyzProjectPatch` API.

## No-argument behavior

Both builder entry points print the complete help text and return success when
called without arguments:

```console
python -m exactus.packages.patcher
./bin/patcher.pyz
```

`--bin` accepts an optional directory directly. Bare `--bin` creates
`PROJECT/bin/patcher.pyz`; `--bin tools` creates
`PROJECT/tools/patcher.pyz`. `--bin-dir tools` remains supported with bare
`--bin`.

## Diff preview

`--diff` is read-only. It renders everything that would change and exits
without creating or applying a patch.

Builder/source diff:

```console
python -m exactus.packages.patcher --a old --b new --diff
./bin/patcher.pyz --a old --b new --diff
```

Already-built update:

```console
./update.pyz --diff
```

Output follows conventional unified-diff structure (`diff --git`, `---`, `+++`,
`@@`, `-`, `+`). ANSI coloring distinguishes headers, hunks, removals,
additions and metadata. Builder diffs additionally apply lightweight syntax
highlighting for JavaScript, CSS, HTML, Python, JSON, TOML and XML.

Use `--no-color` for logs/CI or `--diff-context N` to change context size.
Neither diff mode mutates the destination.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/patcher/`](../exactus/packages/patcher/) | [`exactus/tests/packages/patcher/`](../exactus/tests/packages/patcher/) | [`DOCS.md`](../exactus/docs/packages/patcher/DOCS.md) |

[< Packages-package](Packages-package.md) · [Packages index](Packages.md) · [Packages-performance >](Packages-performance.md)
