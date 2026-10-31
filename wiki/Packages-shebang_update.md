[Home](Home.md) > [Packages](Packages.md) > shebang_update

# shebang_update/

Update Python virtual-environment shebangs to the current project path.

## Behavior

- After a project directory is moved or renamed, carried scripts still
  embed the old absolute interpreter path.
- The updater walks the project root and rewrites any file whose first
  line is an absolute `#!.../.venv/bin/python...` shebang so it points
  at this checkout's interpreter.
- Non-shebang files and relative shebangs are left untouched.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/shebang_update/`](../exactus/packages/shebang_update/) | [`exactus/tests/packages/shebang_update/`](../exactus/tests/packages/shebang_update/) | [`DOCS.md`](../exactus/docs/packages/shebang_update/DOCS.md) |

[< Packages-server](Packages-server.md) · [Packages index](Packages.md) · [Packages-steps >](Packages-steps.md)
