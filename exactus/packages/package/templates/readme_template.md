# `{name}/exactus`

Standalone Exactus package executable. Run from the project you want to check:

```shell
./{name}/exactus --help
./{name}/exactus --lints
./{name}/exactus --docs
./{name}/exactus --coverage_tests
./{name}/exactus --readme
./{name}/exactus --pipeline self
```

The source package exposes the same CLI with `python exactus` or
`PYTHONPATH=src python -m exactus`. Installing the wheel adds the `exactus`
command. Reports are written to `EXACTUS_RESULTS` in the selected project.

Bundled tools are reachable through `--external`: bare invocation lists
the toolchain grouped by runtime with versions, and a tool name forwards
the remaining command line to the offline toolchain:

```shell
./{name}/exactus --external
./{name}/exactus --external ruff check --select ALL
./{name}/exactus --external basedpyright tests
```

Executables built with `--build-self-test` also accept `--self_test`,
the self-diagnostic that probes every bundled tool and runs the
`unified` pipeline against a generated fixture:

```shell
./{name}/exactus --self_test
```

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`readme.md`](readme.md) — Standalone Exactus package executable. Run from the project you want to check:

### Subdirectories

No subdirectories.

<!-- exactus:inventory:end -->
