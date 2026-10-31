[Home](Home.md) > [Packages](Packages.md) > argument_parser

# `exactus/packages/argument_parser/` — dash/underscore option folding

`exactus.packages.argument_parser` provides `ExactusArgumentParser`, an
`ArgumentParser` subclass that folds `-` and `_` in long option names at parse
time, so `--dry-run` and `--dry_run` select the same option without duplicate
flags or help noise. Folded names claimed by two different options fall back
to exact matching, and folding stops after a bare `--`.

```python
from exactus.packages.argument_parser import ExactusArgumentParser, normalized_option
```

## Files

| File | Description |
|---|---|
| `parser.py` | Implementation of `ExactusArgumentParser` and `normalized_option`: folds `-`/`_` in long-option spellings at parse time, falls back to exact matching on collisions and stops folding after a bare `--`. |
| `__init__.py` | Public re-exports (`ExactusArgumentParser`, `normalized_option`). |

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/argument_parser/`](../exactus/packages/argument_parser/) | [`exactus/tests/packages/argument_parser/`](../exactus/tests/packages/argument_parser/) | [`DOCS.md`](../exactus/docs/packages/argument_parser/DOCS.md) |

[< Packages-all_lints](Packages-all_lints.md) · [Packages index](Packages.md) · [Packages-browser >](Packages-browser.md)
