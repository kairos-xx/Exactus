[Home](Home.md) > [Packages](Packages.md) > project_python

# project_python/

Shared interpreter bootstrap for repository scripts.

## Behavior

- `switch_to_project_venv()` replaces a non-project Python process with
  `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows),
  preserving the requested script and its arguments.
- It is a no-op when `.venv` is absent or already active.
- Re-execution is skipped inside `multiprocessing` spawn workers
  (`multiprocessing.parent_process()` non-`None`), so workers inheriting
  a test runner's `sys.argv` are never re-launched as the parent command.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/project_python/`](../exactus/packages/project_python/) | [`exactus/tests/packages/project_python/`](../exactus/tests/packages/project_python/) | [`DOCS.md`](../exactus/docs/packages/project_python/DOCS.md) |

[< Packages-pmanager](Packages-pmanager.md) · [Packages index](Packages.md) · [Packages-rename_project >](Packages-rename_project.md)
