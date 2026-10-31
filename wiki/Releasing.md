[Home](Home.md) › Guides › Releasing

# Releasing

## Artifacts

| Step | Command | Output |
|---|---|---|
| Zipapp + dist tree + tree file | `python exactus/scripts/build_make` | `bin/exactus`, `build/`, `TREE.txt` |
| Per-platform bundles | `python exactus/scripts/bundle_make` | `bin/release/exactus_<os>_<arch>/` (9 variants + `exactus_all`) |
| Timestamped source archive | `python exactus/scripts/package` | `packages/<ddmmyyyyHHMMSS>/exactus.zip` + README |
| Python dist | build via `hatch`/`python -m build` | `dist/*.whl`, `dist/*.tar.gz` |

## Release checklist (as done for v0.6.1)

1. **Sync** — local `main` == `origin/main`, clean tree.
2. **Docs** — update `DOCS.md` files (regenerate blocks with
   `dev/generate_docs_reference.py`), regenerate `wiki/` with
   `dev/generate_wiki.py`.
3. **Gate** — bare `exactus` must be 9/9 PASS on the tagged tree.
4. **Build** — `build_make` for the host zipapp, `bundle_make` for all
   nine `bin/release/` binaries; verify freshness signatures
   (`stale: False`).
5. **Tag + release** — `git tag vX.Y.Z <commit>`, push tag, attach all
   binaries to the GitHub release.
6. **PyPI** — upload `dist/` wheel + sdist.
7. **Install** — `python exactus --install` refreshes
   `/usr/local/bin/exactus` and shell completions.

## Freshness

The installer and `bundle/freshness.py` compare a packaged-source
fingerprint with the live tree — `stale: True` means sources changed
since the artifact was built; rebuild before shipping.

## Versioning

Version lives in `pyproject.toml` (`project.version`) and is stamped
into reports (`tool.version`). Tag format: `v<major>.<minor>.<patch>`.

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
