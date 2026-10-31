# `rename_project.py`

Rename a project in one safe, reviewable step: the root directory, the files
and folders named after it, and every mention of its name inside text files,
each restyled to match how it was written. Optionally renames the GitHub
repository too.

```bash
./rename_project.py --name foo_bar --dry-run --diff   # look first
./rename_project.py --name foo_bar                    # then apply
```

Requires Python 3.13 and nothing else. `git` is used when the project is a
repository; the GitHub CLI (`gh`) is needed only for the GitHub rename.

`__main__.py` makes the directory itself runnable: `python rename_project`
puts the directory on `sys.path`, imports `rename_project.py`, and calls its
`main()` with the same arguments. `examples/` holds a runnable demo that
duplicates a checked-in `project` and renames only the copy, so the
example project is always ready to show again.

## Contents

- [How it works](#how-it-works)
- [Naming conventions](#naming-conventions)
- [Old names and abbreviations](#old-names-and-abbreviations)
- [What is rewritten, and what is not](#what-is-rewritten-and-what-is-not)
- [Renaming the GitHub repository](#renaming-the-github-repository)
- [Questions the script asks](#questions-the-script-asks)
- [Option reference](#option-reference)
- [Recipes](#recipes)
- [Limits and caveats](#limits-and-caveats)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)

## How it works

1. **Plan.** The script finds the project root (the `root` argument, else the
   nearest ancestor of the working directory containing `.git` or
   `pyproject.toml`, else the same search from the script's own folder),
   detects the old names, selects the files, and computes every edit and
   rename in memory. Nothing is written yet.
2. **Show.** The plan is printed: `rewrite:` (with the number of
   substitutions), `rename:`, `skipped (...)`, `github:`, `warning:`, and a
   summary line. `--diff` adds a unified diff of every rewrite.
3. **Confirm.** Unless `--dry-run`, you are asked before anything changes
   (`--yes` skips the question). Without a terminal and without `--yes` the
   script refuses to continue.
4. **Apply as one transaction.** File contents are written atomically, files
   and folders are renamed deepest first, the root directory is renamed
   last, and the GitHub repository (if requested) after that. If any step
   fails, everything already done is undone: contents restored, names
   restored, the GitHub rename reversed, the remote URL put back.

Because the root directory is renamed last and the plan is checked for
collisions first, a failed run never leaves the project half-moved.

## Naming conventions

Give `--name` in any casing (`foo_bar`, `foo-bar`, `FooBar`, `Foo Bar`). The
words are extracted and each occurrence of the old name is rendered in the
style it was written in. Renaming `abc_cde` to `foo_bar`:

| Old spelling | Convention                 | New spelling |
| ------------ | -------------------------- | ------------ |
| `abc_cde`    | snake_case identifiers     | `foo_bar`    |
| `ABC_CDE`    | SCREAMING_SNAKE constants  | `FOO_BAR`    |
| `abc-cde`    | kebab-case packaging names | `foo-bar`    |
| `AbcCde`     | PascalCase class names     | `FooBar`     |
| `abcCde`     | camelCase variables        | `fooBar`     |
| `Abc Cde`    | Title Case headings        | `Foo Bar`    |
| `ABC CDE`    | uppercase prose            | `FOO BAR`    |
| `abc cde`    | lowercase prose            | `foo bar`    |
| `abccde`     | flat compound names        | `foobar`     |
| `abc.cde`    | dotted names (`--dotted`)  | `foo.bar`    |

The root directory itself is named exactly as you typed `--name`.

### Dotted spellings are syntax-aware and fail closed

`abc.cde` is **not** renamed by default. Pass `--dotted` to opt in to dotted
spellings, but that flag no longer means "blindly replace every dot form".
The renamer classifies the occurrence before changing it:

- in Python, `tokenize` distinguishes executable syntax from strings and
  comments; executable `abc.cde` is guarded, covering attribute access,
  imports, calls, decorators, annotations, chained access, assignments, and
  f-string expressions;
- in JavaScript/TypeScript and other recognized code files, dotted executable
  text is guarded by default; only conservatively recognized comments are
  considered safe without a language parser;
- in prose and data/config files, dotted names remain eligible for replacement,
  which preserves the useful cases such as reverse-DNS identifiers and dotted
  configuration keys;
- every guarded occurrence is reported with file and line number so it cannot
  disappear silently from the migration review.

This is intentionally asymmetric: a false negative leaves an old spelling for
review, while a false positive can silently change program behavior.

If the dotted form really is executable code that must be migrated (for
example an intentional Java package rename), use the separate
`--dotted-code` override. It implies `--dotted` and explicitly accepts the
higher risk. Always inspect `--dry-run --diff` before applying it.

### When a spelling is ambiguous

A single-word old name such as `exactus` reads the same as snake, kebab, and
lowercase prose. The kind of file decides:

| File kind                                   | Preference                            |
| ------------------------------------------- | ------------------------------------- |
| Code (`.py`, `.js`, `.html`, `.css`, ...)   | `snake_case`, then `PascalCase`       |
| Prose (`.md`, `.markdown`, `.rst`, `.txt`)  | lowercase words, then Title Case      |
| Data (`.toml`, `.json`, `.yaml`, `.ini`)    | `kebab-case`, then `snake_case`       |

So `import exactus` becomes `import foo_bar`, `class Exactus` becomes
`class FooBar`, and "the exactus tool" in a README becomes "the foo bar tool".

### Context rules

- Heading lines (`# ...`) in Markdown render Title Case: `# abc_cde` becomes
  `# Foo Bar`.
- `name = ...` lines in `.toml` render kebab-case, the packaging convention.
- Text inside inline code (backticks) keeps the style it was written in.
- A match touching `/` or `.` keeps its detected style, so paths and module
  references (`src/abc_cde/x.py`, `abc_cde.cli`) stay filename-accurate.

## Old names and abbreviations

The old names are detected automatically from the root directory name and
from `[project] name` in `pyproject.toml`. This matters when the checkout
directory differs from the distribution name (`checkout/` holding
`abc-cde`): both are replaced.

Add earlier names with `--from NAME` (alias `--alias`, repeatable). All
casings of each are found:

```bash
./rename_project.py --name foo_bar --from exactus-tools
```

### Abbreviations are opt-in

Short forms such as `AT` for "exactus tools" are **never** renamed unless you
list them, because they collide with ordinary text. `at` appears in
`started_at`, `finished_at`, "look at this"; renaming it blindly would break
JSON field names and prose.

```bash
--abbrev AT          # AT -> initials of the new name, same case (FB)
--abbrev AT=FB       # explicit replacement
--abbrev At --abbrev AT   # one option per spelling
```

- Matching is exact and **case-sensitive**: `AT` does not match `at`.
- By default a standalone token matches (`AT = 1`), not `AT_HOME` or
  `started_at`. Add `--boundary loose` to match inside identifiers.
- A lowercase abbreviation of three letters or fewer is refused unless you
  also pass `--allow-short-lowercase`. Combined with `--boundary loose` it
  would rename every `_at` suffix, so check the plan with `--dry-run --diff`.

### Boundaries

`--boundary word` (default) renames a name only when it does not touch a
letter, digit, or underscore: `abc_cde` matches in `import abc_cde` but not in
`abc_cde_core`. `--boundary loose` also renames inside identifiers
(`abc_cde_core` becomes `foo_bar_core`). Camel-case humps are not split in
either mode (`getAbcCdeValue` is untouched).

### Spellings it does not recognize

Mixed-case forms such as `Abc_Cde` or `abc_Cde` have no convention to restyle,
so they are left alone, but they are **reported**:

```
warning: unrecognized spelling at src/a.py:2: class Abc_Cde: ...
```

Up to three lines per file are shown, and the summary counts them. Fix those
by hand, or list the exact spelling with `--from Abc_Cde`.

## What is rewritten, and what is not

**Files considered.** Inside a git repository the script uses
`git ls-files` (tracked plus untracked, honoring `.gitignore`), so ignored
folders such as `.history`, `node_modules`, and build output are never
touched. Outside git (or with `--no-git`) it walks the tree and prunes `.git`,
`.hg`, `.svn`, virtual environments, `node_modules`, `__pycache__`, tool
caches, `.history`, `dist`, `build`, and `*.egg-info`. Narrow it further with
`--include` / `--exclude` globs (relative POSIX paths).

**Rewritten.** UTF-8 text in any language: Python, JavaScript, HTML, CSS,
JSON, TOML, YAML, XML, Markdown, plain text, shell scripts, and so on, plus
the names of files and folders.

**Preserved.**

- Line endings (CRLF stays CRLF), a leading BOM, and file permissions.
- The shebang line (`#!/usr/bin/env ...`): a relative shebang cannot run.
- Symlinks: never followed or rewritten (a link whose own name carries the
  old name is renamed).

**Skipped and reported** when they mention the old name: binary files (for
example SQLite databases or images), files that are not valid UTF-8, and
files larger than `--max-size` (5 MiB by default).

**Absolute paths.** A path inside the project (`/home/me/abc_cde/src/x.py`)
becomes relative (`src/x.py`). An existing absolute path outside the project is
left alone and shielded from restyling, so `/opt/abc_cde/bin` keeps working.
`--keep-absolute` leaves in-project absolute paths untouched too.

**Collisions.** If two paths would end up with the same name, or a destination
already exists (including the new root directory), the script stops before
changing anything and lists the clashes.

## Renaming the GitHub repository

The script looks at the git remote (`origin`, or `--remote NAME`). If it is a
`github.com` URL whose repository name contains the old name, the repository
can be renamed with the GitHub CLI and the remote repointed.

| You pass       | Behavior                                                         |
| -------------- | ---------------------------------------------------------------- |
| nothing        | A found repository is **offered** with a question (terminal only) |
| `--github`     | Renamed without asking; errors if it cannot be                   |
| `--no-github`  | Never renamed, never offered                                     |

Details:

- The new repository name is the old one **restyled by the same rules**:
  `abc_cde` becomes `foo_bar`, `abc-cde` becomes `foo-bar`. URLs inside your
  files (`https://github.com/me/abc_cde`) get the same treatment, so they point
  at the renamed repository.
- The remote URL keeps its form: HTTPS or SSH, with or without `.git`.
- `gh` must be installed and signed in (`gh auth login`); this is verified
  before anything changes.
- It runs **after** the local rename. If GitHub refuses or the remote cannot be
  repointed, the local changes are rolled back too.
- `--yes` never renames a repository by itself. Outward-facing actions need an
  explicit `--github` or a "yes" typed at the question. Without a terminal, a
  found repository is left alone with a note.
- GitHub redirects the old URL for a while. CI, webhooks, Pages, and other
  people's clones still need updating, and the redirect can break if you later
  create a repository under the old name.

## Questions the script asks

Prompts are styled with ANSI colors on a terminal (bold question, dimmed
details, a `[y/N]` hint) and are plain when output is piped or `NO_COLOR` is
set. An empty answer takes the default (always "no" for these), anything other
than `y`/`yes`/`n`/`no` is asked again, and end of input counts as "no".

```
? Apply 12 file edit(s) and 3 rename(s)?
  project: /home/me/abc_cde
  > [y/N]

? Rename GitHub repository me/abc_cde to me/foo_bar?
  remote 'origin' will point at https://github.com/me/foo_bar.git
  GitHub redirects the old URL; CI, webhooks and other clones must be updated.
  > [y/N]
```

The same coloring is used for plan lines: green `rewrite:`, cyan `rename:`,
yellow `skipped`/`warning:`, magenta `github:`, red `error:`.

## Option reference

Run `./rename_project.py -h` for the grouped, colored version.

| Option | Meaning |
| ------ | ------- |
| `root` | Repository root (positional, optional). |
| `--name NAME` | Target name in any casing; also the new root directory name (default `exactus`). |
| `--from NAME`, `--alias NAME` | Extra old name; repeatable. |
| `--abbrev OLD[=NEW]` | Rename an exact, case-sensitive abbreviation; repeatable. |
| `--allow-short-lowercase` | Permit lowercase abbreviations of 3 letters or fewer. |
| `--dotted` | Rename dotted spellings only where they are non-code or proven safe; executable code references are guarded and reported. |
| `--dotted-code` | High-risk override that also rewrites dotted executable code; implies `--dotted`. |
| `--boundary {word,loose}` | Whether names must stand alone (`word`, default) or may sit inside identifiers (`loose`). |
| `--include GLOB` | Only touch matching paths; repeatable. |
| `--exclude GLOB` | Never touch matching paths; repeatable. |
| `--no-git` | Walk the tree instead of `git ls-files`. |
| `--no-rename-root` | Rewrite files but keep the root directory name. |
| `--keep-absolute` | Leave in-project absolute paths untouched. |
| `--max-size BYTES` | Skip larger files (default 5242880). |
| `--github` / `--no-github` | Rename without asking / never offer. |
| `--remote NAME` | Git remote used for GitHub (default `origin`). |
| `--dry-run` | Print the plan; change nothing. |
| `--diff` | Include a unified diff of every rewrite. |
| `--quiet` | Print only the summary line. |
| `--yes` | Skip the apply confirmation (never implies `--github`). |

**Exit status:** `0` on success or dry run; `1` when the rename was refused
(bad name, collision, missing `gh`), declined at the question, or rolled back.

## Recipes

Preview everything, with diffs:

```bash
./rename_project.py --name foo_bar --dry-run --diff
```

Rename from another directory:

```bash
./rename_project.py ~/code/abc_cde --name foo_bar
```

Fold in an earlier name and its abbreviation (the `exactus-tools` / `AT` case):

```bash
./rename_project.py --name foo_bar --from exactus-tools --abbrev AT --dry-run --diff
```

Keep the directory name, change only the contents:

```bash
./rename_project.py --name foo_bar --no-rename-root
```

Only touch source and docs, never lockfiles or generated bundles:

```bash
./rename_project.py --name foo_bar \
    --include 'src/**' --include '*.md' --exclude '*.lock' --exclude '*.min.js'
```

Rename inside identifiers (`abc_cde_core`, `ABC_CDE_URL`, BEM classes):

```bash
./rename_project.py --name foo_bar --boundary loose --dry-run --diff
```

Non-interactive, including the GitHub repository (CI or scripts):

```bash
./rename_project.py --name foo_bar --yes --github
```

Undo a local rename in a git repository: review with `git status`/`git diff`,
then `git restore .`, `git clean -fd`, and rename the directory back. Take the
dry run seriously; it is the easiest "undo".

## Limits and caveats

- **Names inside larger identifiers** are not renamed by default
  (`abc_cde_core`, `ABC_CDE_URL`, `abc-cde__item`). Use `--boundary loose` and
  review the plan.
- **Mixed-case spellings** such as `Abc_Cde` are reported, not rewritten.
  Dotted spellings are opt-in; with `--dotted`, executable code occurrences
  that cannot be proven safe are guarded and reported instead of rewritten.
- **Camel humps** are not split: `getAbcCdeValue` is untouched in both modes.
- **Encodings:** only UTF-8 is rewritten. UTF-16 and legacy encodings are
  skipped and reported.
- **Generated and locked files** (lockfiles, minified bundles) are rewritten
  like any text; exclude them if you regenerate them instead.
- **Binary content** (databases, images, archives) is never modified, even if
  it contains the old name. The summary lists it.
- **Short single-word names** (`exactus`, `app`, `core`) match common words in
  prose. The `word` boundary and file-kind rules limit damage, but always read
  the dry run.
- **Remote effects** of the GitHub rename (other clones, CI, Pages, webhooks)
  are outside the script's reach.
- **Rewriting is single pass.** Running it twice with the same arguments after
  a successful rename finds nothing, but renaming to a name that contains the
  old one (`exactus` to `exactus_tools`) and running again would rename again.

## Troubleshooting

| Message | Cause and fix |
| ------- | ------------- |
| `refusing to change files without --yes` | No terminal to ask on. Add `--yes` or use `--dry-run`. |
| `rename would collide: ... already exists` | Another file or folder already has the new name. Move it or choose another `--name`. |
| `invalid project name` | Use letters, digits, `_ - .` or spaces, starting with a letter. |
| `the new name equals the current name` | Nothing to do. |
| `abbreviation 'at' is a lowercase word or suffix` | Intentional guard; add `--allow-short-lowercase` if you really mean it. |
| `renaming the repository needs the GitHub CLI` | Install `gh` and run `gh auth login`. |
| `remote 'origin' is not a github.com URL` | `--github` needs a GitHub remote; use `--remote NAME` or drop the flag. |
| `repository name '...' does not contain the old name` | The GitHub repo is named differently; rename it on GitHub yourself. |
| `rename failed and was rolled back` | An I/O step failed (permissions, disk full). Nothing was changed; fix the cause and retry. |
| `warning: unrecognized spelling` | A mixed-case spelling was left unchanged; edit it by hand. |

## Testing

`exactus/tests/test_rename_project.py` covers casing, context rules, single-word
names, CRLF/BOM/mode preservation, absolute paths, shebangs, binaries,
symlinks, file and folder renames, `pyproject.toml` detection, dry runs,
confirmation, collisions, rollback, boundaries, `.gitignore`, abbreviations,
unrecognized spellings, the GitHub flow (including rollback), and the
interactive prompts.

```bash
python -m pytest exactus/tests/test_rename_project.py
```

## Semantic safety engine

The rename pass is deliberately fail-closed. It does not treat every textual
match as equivalent. Before rewriting, code/document regions are classified by
language and dotted spellings are rewritten only where they are known to be
non-executable. Ambiguous executable occurrences are reported as `guarded` and
left unchanged unless `--dotted-code` is explicitly supplied.

### Python

Python uses the standard AST plus `tokenize`. Ordinary string constants and
comments are distinguished from executable syntax. In particular, member
access, imports, decorators, annotations, calls, assignment targets, and
expressions inside f-strings are not confused with text merely because the
same spelling appears nearby. Real module/class/function docstrings are string
AST nodes and are handled as documentation text. After rewriting, the complete
file is parsed again; an edit that no longer produces a valid Python AST is
rejected.

### JavaScript and JSDoc

JavaScript/JSX/MJS/TypeScript-like files use a conservative lexical scanner for
comments, quoted strings, template literals, and executable source. Dotted
member access remains guarded. Interpolated template literals are not declared
safe as a whole. Strings passed directly to selector APIs such as
`querySelector`, `querySelectorAll`, `matches`, and `closest` are treated as
selector syntax rather than generic strings.

JSDoc is mixed-mode rather than a plain comment: prose is eligible, while
`{@link ...}`, `{@linkcode ...}`, `{@linkplain ...}`, `{@code ...}`, backtick
code, typed tag braces, and symbol-bearing inheritance/member tags are excluded
from prose rewriting when the spelling is semantically ambiguous.

### HTML + CSS + JavaScript cross references

HTML is segmented into markup text, ordinary attribute values, event-handler
attributes, inline `style`, `<script>` bodies, and `<style>` bodies. Embedded
JavaScript and CSS are delegated to their own scanners. Consequently an HTML
file cannot accidentally make executable JavaScript safe merely because the
outer file extension is `.html`.

A project-wide web symbol graph correlates relevant HTML `id`/`class`
definitions with CSS `#id`/`.class` selectors and JavaScript DOM references
including `getElementById`, selector APIs, and common `classList` operations.
Linked symbol families are shown as `web-link:` entries in the plan. The graph
is corroborating evidence only: local syntax classification still has veto
power, which prevents a coincidental cross-file spelling from authorizing a
risky replacement.

### CSS

CSS comments and quoted values are distinguished from selector syntax. A
spelling such as `abc.cde` in a selector is therefore not treated like the
same characters in a quoted value or documentation comment.

### Markdown

Markdown prose is distinguished from fenced code and inline backtick code for
semantic dotted-name handling. Code examples are not automatically treated as
ordinary prose.

### TOML, CSV, XML, and text

TOML remains data-aware through the existing `name =` convention and is parsed
again after rewriting. XML is reparsed for well-formedness. CSV is parsed in
strict mode after rewriting so quoting/field structure cannot silently become
invalid. Plain `.txt` is intentionally textual because it has no stronger
syntax contract.

### Structural postconditions

For formats with deterministic parsers available in the Python standard
library, a replacement must satisfy both conditions:

1. the occurrence-level classifier permits the replacement; and
2. the complete rewritten file still parses successfully.

At present this postcondition is enforced for Python, TOML, XML, and CSV. A
failed postcondition skips the edit and reports `rewrite failed structural
validation` instead of writing questionable output.

### Recommended workflow

For a high-impact project rename, first run:

```bash
python rename_project.py --name NEW_NAME --dotted --dry-run --diff
```

Review every `guarded:` and `web-link:` entry. Use `--dotted-code` only when
you explicitly intend to rename dotted executable/package/member syntax and
have reviewed the diff. The normal `--dotted` mode is intentionally biased
toward false negatives rather than destructive false positives.

## Parser-backed semantic analysis

High-risk source formats are parsed with real grammars. Install the pinned
runtime dependency before using the tool:

```bash
python -m pip install -r requirements.txt
```

`tree-sitter-language-pack` supplies Python-hosted Tree-sitter parsers for
JavaScript, JSX, TypeScript, TSX, HTML, CSS, and Markdown. Python continues to
use the standard-library AST and tokenizer. TOML, XML, and CSV continue to use
Python structured parsers.

The renamer never re-serializes a syntax tree. Tree-sitter UTF-8 byte ranges
are translated to Python character offsets and edits are applied to the
original source, preserving formatting and unrelated text. Parser errors fail
closed: syntax-sensitive replacements are not accepted, and post-rewrite
validation reparses parser-backed files before the transaction can proceed.

HTML is recursively analyzed: `<script>` bodies and `on*` attributes are
parsed as JavaScript; `<style>` bodies and `style` attributes are parsed as
CSS. JSDoc comments are recognized from JavaScript comment CST nodes and their
symbol/type/code subregions remain guarded. Markdown code regions are excluded
using Markdown CST nodes rather than regular-expression fence detection.


## Adversarial safety validation

The distribution includes `exactus/tests/test_adversarial_semantics.py` and
`exactus/tests/test_safety_metrics.py`. The corpus declares the expected disposition
of every dangerous dotted occurrence and distinguishes dangerous false
positives from conservative false negatives. A release requires zero
dangerous false positives; parser tests being skipped is not considered a
release pass. See `SAFETY_TESTING.md`.

## SQLite databases

SQLite databases are first-class rename inputs by default for `.db`, `.db3`,
`.sqlite`, and `.sqlite3` files whose header identifies a real SQLite database.
Use `--no-sqlite` to disable database inspection and mutation.

The default policy is deliberately conservative:

- only runtime `TEXT` cell values are candidates for automatic replacement;
- `BLOB`, numeric, and `NULL` values are never rewritten;
- generated/hidden columns are never updated directly;
- ordinary rowid tables use an unshadowed SQLite rowid alias as the stable row
  locator, while `WITHOUT ROWID` tables use their declared primary key;
- tables without a provably stable locator are guarded rather than updated;
- table, column, index, view, and trigger definitions in `sqlite_schema` are
  never text-rewritten; matching schema SQL is reported as guarded;
- SQL values are bound parameters and identifiers are separately quoted;
- all changes for one database execute under `BEGIN IMMEDIATE`;
- `PRAGMA foreign_key_check` and `PRAGMA integrity_check` must succeed before
  the database transaction commits;
- SQLite's backup API captures rollback material before mutation, including
  the committed state of WAL databases;
- if a later filesystem or repository operation fails, the database is
  restored through SQLite's backup API as part of the project-wide rollback.

`--dry-run` reports each planned database cell update as
`database table.column: before -> after`. Database schema matches appear in
`guarded` output and require deliberate migration rather than search/replace.


## SQLite schema renaming

`--sqlite-schema` opt-in enables dependency-aware SQLite schema renames.
Table and column identifiers are changed only with SQLite `ALTER TABLE`
operations while `PRAGMA legacy_alter_table=OFF`. SQLite reparses and updates
dependent indexes, triggers, views, and foreign keys; semantic ambiguity aborts
the transaction. Schema-name collisions are guarded before apply. Named schema
objects are recreated only when their own names match the normal rename rules,
using SQLite's post-ALTER SQL and changing only the CREATE-object header.
`PRAGMA foreign_key_check` and `PRAGMA integrity_check` must pass before commit.
The database backup participates in the outer filesystem rollback transaction.
Without `--sqlite-schema`, schema matches remain guarded and only safe TEXT-cell
updates are applied. `PRAGMA writable_schema` is never used.

## SQL and cross-database schema safety

The renamer treats `.sql` as code. Dotted SQLite identifiers can be renamed in
structural SQL regions, while single-quoted SQL values and SQL comments are not
classified as identifier regions. Rewritten SQL must remain a complete SQLite
statement when the file contains non-whitespace SQL.

With `--sqlite-schema`, the dry-run plan also inventories static SQL-looking
references in Python, JavaScript, TypeScript, and `.sql` files for every SQLite
schema identifier that is scheduled to change. These `sql-ref` records expose
cross-file impact for review. Runtime-generated SQL remains outside the proof
boundary and should be reviewed when schema identifiers are assembled
indirectly.

Python source span handling converts AST UTF-8 byte columns to Python character
columns before combining them with `tokenize` spans. This prevents non-ASCII
text earlier on a line from shifting the safety region of a later string.

## Project layout

- `rename_project.py` — the renamer: planning, safe-region classification,
  SQLite handling, transactional apply, GitHub rename, and the CLI.
- `cli_help.py` — ANSI-styled `--help` and `paint` helpers (plain on pipes and
  when `NO_COLOR` is set).
- `pytest.ini` — pytest options and `pythonpath = .` so tests import the
  module even when run from the repository root.
- `pyproject.toml` — package metadata, dependencies (`tree-sitter`,
  `tree-sitter-language-pack`, `defusedxml`), ruff and basedpyright settings.
- `tests/` — the test suite, one module per concern:
  - `assertions.py` — Keyword-only assertion helpers for the rename_project tests.
  - `test_adversarial_semantics.py` — Adversarial semantic-safety tests for rename_project.
  - `test_assertions.py` — Every assertion helper passes on good input and fails on bad input.
  - `test_cli_behavior.py` — CLI-level behavior of the project renamer: plans, prompts, rollback.
  - `test_next_safety_batch.py` — Regression tests for SQL, Unicode geometry, golden projects, rollback.
  - `test_safety_metrics.py` — Safety-oriented corpus metrics with asymmetric failure accounting.
  - `test_sqlite_semantics.py` — SQLite safety tests for the project renamer.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Rename a project: root directory, files, and its name inside text.
- [`__main__.py`](__main__.py) — Rename a project: root directory, files, and its name inside text.
- [`cli_help.py`](cli_help.py) — ANSI-styled ``--help``/``-h`` output shared by the root scripts.
- [`pyproject.toml`](pyproject.toml) — Provide pyproject toml content.
- [`pytest.ini`](pytest.ini) — Provide pytest ini content.
- [`rename_project.py`](rename_project.py) — Rename a project: its root directory, its files, and its name in text.

### Subdirectories

- [`examples/`](examples/README.md) — `run.py` demonstrates the renamer end to end without risking a real checkout: it duplicates `project/` into the git-ignored `.scratch/` folder and renames the copy to `demo_app` with `--yes --no-git --diff --boundary loose` (loose also renames inside identifiers, so `PROJECT_VERSION` becomes `DEMO_APP_VERSION`). Because only the copy is touched, the checked-in example project stays pristine and the demo can be re-run any number of times.

<!-- exactus:inventory:end -->


