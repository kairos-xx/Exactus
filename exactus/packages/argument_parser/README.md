# `exactus/packages/argument_parser/`

`ExactusArgumentParser`: an `ArgumentParser` whose long options accept
dashes and underscores interchangeably (`--dry-run` = `--dry_run`).
Standalone, so any package can depend on it.

## Usage

```python
from exactus.packages.argument_parser import ExactusArgumentParser

parser = ExactusArgumentParser(prog="demo")
parser.add_argument("--dry-run", action="store_true")
parser.parse_args(["--dry_run"])
```

## Layout

- `parser.py` — option folding and the parser class.
- `tests/` — `exactus/tests/packages/argument_parser/`; docs live in `exactus/docs/packages/argument_parser/`.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Public API for the dash/underscore-folding argument parser.
- [`parser.py`](parser.py) — Shared argument parser accepting ``-`` and ``_`` interchangeably.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
