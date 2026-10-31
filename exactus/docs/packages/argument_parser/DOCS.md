# `exactus/packages/argument_parser/` — dash/underscore option folding

`exactus.packages.argument_parser` provides `ExactusArgumentParser`, an
`ArgumentParser` subclass that folds `-` and `_` in long option names at parse
time, so `--dry-run` and `--dry_run` select the same option without duplicate
flags or help noise. Folded names claimed by two different options fall back
to exact matching, and folding stops after a bare `--`.

```python
from exactus.packages.argument_parser import ExactusArgumentParser, normalized_option
```
