# Project

`project` is a tiny package that exists only to be renamed by
the `rename_project` example. Every casing of the name appears somewhere
so the restyling rules can be watched live: `project` in imports,
`project` as the distribution name, `Project` as a class,
`project` in camelCase prose, and `PROJECT_VERSION` as a
constant.

Run the demo from the repository root:

```bash
python exactus/packages/rename_project/examples/run.py
```

It copies this directory into `../.scratch` and renames the copy to
`demo_app`, leaving this project untouched and ready to show again.

## Directory contents

- `pyproject.toml` — File.
- `docs/` — Subdirectory.
- `src/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.

### Subdirectories

- [`docs/`](docs/README.md) — Documentation for the `project` demo package.
- [`src/`](src/README.md) — Source layout of the `project` package.

<!-- exactus:inventory:end -->


