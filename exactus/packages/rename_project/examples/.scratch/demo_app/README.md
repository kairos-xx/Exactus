# Demo App

`demo app` is a tiny package that exists only to be renamed by
the `rename_demo app` example. Every casing of the name appears somewhere
so the restyling rules can be watched live: `demo app` in imports,
`demo app` as the distribution name, `Demo App` as a class,
`demo app` in camelCase prose, and `DEMO APP_VERSION` as a
constant.

Run the demo from the repository root:

```bash
python exactus/packages/rename_demo app/examples/run.py
```

It copies this directory into `../.scratch` and renames the copy to
`demo_app`, leaving this demo app untouched and ready to show again.

## Directory contents

- `pyproject.toml` — File.
- `docs/` — Subdirectory.
- `src/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.

### Subdirectories

- [`docs/`](docs/README.md) — Documentation for the `demo app` demo package.
- [`src/`](src/README.md) — Source layout of the `demo app` package.

<!-- exactus:inventory:end -->


