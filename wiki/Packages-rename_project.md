[Home](Home.md) > [Packages](Packages.md) > rename_project

# rename_project/

Renames a project in one safe, reviewable step: the root directory, the
files and folders named after it, and every mention of its name inside
text files — each restyled to match how the name was written (lower,
upper, snake, kebab, camel and title variants). Optionally renames the
GitHub repository too.

Run as a directory: `python scripts/rename_project`.

## What it changes

- The project root directory name.
- Files and folders whose names contain the project name.
- Occurrences inside text files, restyled to each occurrence's writing
  style (`name`, `NAME`, `Name`, `name_x`, `name-x`, `nameX`).

## Safety properties

- Rename operations are ordered deepest-first so parent renames never
  invalidate pending child paths.
- Binary files and excluded directories are left untouched.
- The plan is reviewable before any mutation is applied.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/rename_project/`](../exactus/packages/rename_project/) | [`exactus/tests/packages/rename_project/`](../exactus/tests/packages/rename_project/) | [`DOCS.md`](../exactus/docs/packages/rename_project/DOCS.md) |

[< Packages-project_python](Packages-project_python.md) · [Packages index](Packages.md) · [Packages-scene_description >](Packages-scene_description.md)
