[Home](Home.md) > [Packages](Packages.md) > package

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

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/package/`](../exactus/packages/package/) | [`exactus/tests/packages/package/`](../exactus/tests/packages/package/) | [`DOCS.md`](../exactus/docs/packages/package/DOCS.md) |

[< Packages-organize](Packages-organize.md) · [Packages index](Packages.md) · [Packages-patcher >](Packages-patcher.md)
