# completion/

Exactus-specific shell-completion wiring on top of
`exactus/packages/completion`.

## Files

| File | Description |
|---|---|
| `defaults.py` | Maps the real `exactus` parser grammars to providers through a structural protocol, without importing the application. |
| `main.py` | `exactus completion` command: prints the shell registration script, or installs, removes and diagnoses user-level registration. |
| `startup.py` | Installs portable-launcher completion and refreshes changed bundles. |

## Behavior

- Completion logic (grammars, providers, shell generators) lives in
  `exactus/packages/completion`; this package only wires Exactus' own parsers and
  commands into it.
- Supported shells register through the printed script or the installer;
  diagnostics report registration state per shell.
