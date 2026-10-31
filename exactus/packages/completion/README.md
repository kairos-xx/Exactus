# exactus/completion

Shell completion for the `check` CLI: a grammar-aware Python engine
behind a thin, generated shell adapter per supported shell.

- `__init__.py` — Package marker.
- `model.py` — Frozen domain values: candidate/flag/kind enums, the normalized `CompletionRequest`, `CompletionContext`, `RecognizedArguments`, `ValueCardinality`, and the `CompletionProvider` protocol.
- `catalog.py` — `CommandSpec`/`OptionSpec`/`PositionalSpec` grammar model plus `spec_from_parser` introspection of the real argparse parsers — the completion grammar can never drift from the CLI it describes.
- `defaults.py` — Wiring of the real `check` grammar: tool dispatch flags, the screenshot shortcut merge, orchestrator options, and destination-to-provider mapping.
- `engine.py` — Token scanner that replays completed words into committed CLI state, then produces candidates from the active context (options, values, positionals, subcommands).
- `providers.py` — Bounded dynamic providers: one-level path/directory listing, catalog tool and pipeline names, and `TOOL::` scoped-argument prefixes.
- `protocol.py` — The hidden `check __complete` endpoint: `--name=value` request parsing (tolerant of empty and `-`-leading words), US-separated candidate records on stdout, size limits, and exit codes `0/2/3/4/5`.
- `shells.py` — Deterministic registration-script renderers for Bash, Zsh, Fish, and PowerShell. Shell code only transports context and records; every decision lives in Python.
- `install.py` — Managed user profile blocks and Fish provider files, with idempotent updates that preserve unrelated content.
- `profiles.py` — Shared discovery of interactive/login profiles and installed PowerShell editions, used by automatic setup and manual management.
- `startup.py` — Automatic portable-launcher registration for Bash login and interactive profiles, Zsh (`ZDOTDIR`), Fish (`XDG_CONFIG_HOME`), and PowerShell current-user/all-host profiles. Installed PowerShell editions supply their actual profile locations, including redirected Documents folders.
- `__main__.py` — The user-facing `python -m exactus.packages.completion <shell> --command NAME [--launcher TOK...] [--install|--uninstall|--diagnose]` command.
- `README.md` — This file.

## Automatic setup

The first ordinary invocation of `exec/exactus` installs completion for
Bash, Zsh, Fish, and PowerShell. A SHA-256 fingerprint of the bundle
refreshes managed registrations when any bundled code or catalog changes.
Launcher paths are refreshed when the executable moves. Identical content
is left untouched. PowerShell uses the current-user/all-host profile so
terminal applications share the registration; both installed editions
are queried on Windows. Profiles disabled by shell options cannot load
completion, and shells without an adapter (such as CMD) are not supported.

Open a new terminal or reload the appropriate profile after setup.
The running child process cannot modify its parent shell's functions.
The hidden `__complete` endpoint and explicit `completion` management
commands skip automatic setup, so TAB requests never write profiles and
`--uninstall` works until the next ordinary portable-launcher invocation.
Developer source invocations do not trigger automatic installation.
Failures are reported on stderr while the CLI continues; foreign Fish
providers and incomplete managed blocks are preserved.

Profile selection follows the shell startup rules:
[Bash](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html),
[Zsh](https://zsh.sourceforge.io/Doc/Release/Files.html), and
[PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles).

## How it works

Try the [runnable completion examples](examples/README.md) without changing
shell profiles.

`check completion bash` prints a registration script; `check
completion all --install` writes it to the standard user location.
At TAB time the adapter invokes `check __complete --shell=...
--active-word-index=N --prefix=P --word=W...` and formats the
returned `value<US>display<US>description<US>kind<US>flags` records
with the shell's native completion primitives. The endpoint never
prints banners or logging on stdout; `CHECK_COMPLETION_DEBUG=1`
enables stderr diagnostics.

## Maintainer rule

Whenever a CLI argument or context is added or changed, its
completion metadata/provider must be updated at the same declaration
site — the catalog introspects the real `argparse` parsers, so option
flags, `choices`, `type=Path`, `nargs`, mutex groups, and `help`
arrive automatically; provider-bound destinations are mapped in
`defaults.py` (`_COMMON_PROVIDERS`) and any
new dynamic value class gets a `ProviderId` plus an entry in
`default_providers`. `exactus/tests/exactus/completion/` asserts the catalog
against the real parsers so drift fails tests.

## Files

- `startup.py` — File.

## Subdirectories

- `examples/` — Subdirectory.

<!-- exactus:inventory:start -->
## Directory contents

### Files

- [`__init__.py`](__init__.py) — Shell autocomplete engine, catalog, protocol and shell adapters.
- [`__main__.py`](__main__.py) — Completion registration CLI for commands embedding this package.
- [`catalog.py`](catalog.py) — Completion catalog: the CLI grammar described for the engine.
- [`cli.py`](cli.py) — Completion registration CLI for commands embedding this package.
- [`engine.py`](engine.py) — Grammar-aware word scanner and candidate producer.
- [`install.py`](install.py) — User-level completion install, uninstall and diagnosis.
- [`json_types.py`](json_types.py) — JSON value types shared by the exactus tools.
- [`launcher.py`](launcher.py) — Resolve the launcher baked into generated shell adapters.
- [`model.py`](model.py) — Typed shell-completion domain values.
- [`profiles.py`](profiles.py) — Discover current-user completion profiles across supported shells.
- [`protocol.py`](protocol.py) — Hidden ``__complete`` wire protocol.
- [`providers.py`](providers.py) — Dynamic completion providers.
- [`shells.py`](shells.py) — Shell registration-script renderers.

### Subdirectories

- [`examples/`](examples/README.md) — Complete an application-owned argparse command using only files in this package.

<!-- exactus:inventory:end -->


