# macOS menu-bar assets

This directory contains static resources for the optional native Exactus MCP
menu-bar controller in `../macos_menu.py`.

## Files

- [`icons/server.svg`](icons/server.svg) is the monochrome Tabler `server`
  glyph loaded as a macOS template image.
- [`icons/LICENSE`](icons/LICENSE) records the upstream Tabler Icons MIT
  license.

The Python adapter is imported only when `--menu-bar` is active. Linux,
Windows, and headless macOS runs do not load these resources or the `rumps`
runtime.

<!-- exactus:inventory:start -->
## Directory contents

### Files

No direct files besides this README.

### Subdirectories

- [`icons/`](icons/README.md) — Provide LICENSE project content.

<!-- exactus:inventory:end -->
