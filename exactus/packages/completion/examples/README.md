# Completion example

Complete an application-owned argparse command using only files in this package.

```sh
python -m exactus.packages.completion.examples
```

The example passes its own grammar to the [completion protocol](../protocol.py), then displays flag and pipeline candidate records. It does not import the exactus dispatcher or modify terminal profiles. Applications supply their parsers through the structural protocol in [defaults.py](../defaults.py).

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Provide runnable shell completion examples.
- [`__main__.py`](__main__.py) — Run the completion example with the project virtual environment.
- [`run.py`](run.py) — Complete a standalone command without importing any exactus tools.

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->


