# `zip_components/`

`exactus.packages.zip_components` creates source-bundle archives of exactus tools and packages packages: each component's sources, tests and docs plus the shared skeleton files, unzippable back onto a repository root.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`DOCS.md`](DOCS.md) — `exactus.packages.zip_components` packages one or more exactus tools and/or packages packages into a single `.zip` whose members keep their repository-relative paths. Extracting with `unzip -o <name>.zip -d .` at a repository root drops every file back where it belongs.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
