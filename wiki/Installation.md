[Home](Home.md) › Guides › Installation

# Installation

Exactus runs three ways: as a pip package, as a single-file zipapp, or
straight from a source checkout.

## PyPI

```bash
pip install exactus
```

Current release: **0.6.1** (`exactus-0.6.1-py3-none-any.whl` + sdist on
[PyPI](https://pypi.org/project/exactus/)).

## Zipapp binaries

`bin/release/` and the GitHub release ship one self-contained zipapp per
platform — each embeds its own partitioned toolchain bundle (ruff,
basedpyright, pyrefly, pytest, node, playwright, chromium, …), so no host
toolchain is required:

| Binary | Target |
|---|---|
| `exactus_macos_arm64` | macOS Apple Silicon |
| `exactus_macos_amd64` | macOS Intel |
| `exactus_linux_amd64` / `exactus_linux_arm64` | Linux glibc |
| `exactus_linux_musl_amd64` / `exactus_linux_musl_arm64` | Linux musl (Alpine) |
| `exactus_windows_amd64` / `exactus_windows_arm64` | Windows |
| `exactus_all` | Fat zipapp embedding every platform bundle |

## From source

```bash
git clone https://github.com/kairos-xx/Exactus.git
cd Exactus

# build bin/exactus + build/ (unzipped pyz) + TREE.txt
python exactus/scripts/build_make

# system-wide install (writes /usr/local/bin/exactus and shell
# completions for bash/zsh/fish/powershell; detects stale installs)
python exactus --install
```

## Entry points

| Invocation | Notes |
|---|---|
| `exactus --lints` | Installed executable |
| `python exactus --lints` | Source checkout (`exactus/` is a package) |
| `./bin/exactus --lints` | Locally built zipapp |
| `python build/ --lints` | Unzipped build tree — no bundle needed |

`exactus --install` compares the packaged-source fingerprint before
copying; `stale: False` means the installed binary matches the tree.

## Requirements

- Python ≥ 3.13 for building from source; zipapps are self-contained.
- A project to audit: any Python/JavaScript tree — point `--root` at it
  or run inside it.

## Upgrade / uninstall

- Upgrade: rebuild and re-run `python exactus --install`.
- Uninstall: remove `/usr/local/bin/exactus`, `~/.local/share/exactus/`
  and the generated shell-completion files (`bash`, `zsh`, `fish`,
  `powershell`).

---

[Installation](Installation.md) · [CLI](CLI.md) · [Architecture](Architecture.md) · [Reports](Reports.md) · [Testing](Testing.md) · [Releasing](Releasing.md) · [Conventions](Conventions.md)
