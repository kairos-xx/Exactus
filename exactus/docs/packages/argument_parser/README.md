# `exactus/docs/packages/argument_parser/`

Documentation for [`exactus/packages/argument_parser/`](../../../packages/argument_parser).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`DOCS.md`](DOCS.md) — `exactus.packages.argument_parser` provides `ExactusArgumentParser`, an `ArgumentParser` subclass that folds `-` and `_` in long option names at parse time, so `--dry-run` and `--dry_run` select the same option without duplicate flags or help noise. Folded names claimed by two different options fall back to exact matching, and folding stops after a bare `--`.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
