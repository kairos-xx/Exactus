#!/usr/bin/env python3
# Copyright (c) 2026 João Lopes.
"""Render a small temporary tree and a zip member listing."""

from __future__ import annotations

from contextlib import suppress
from importlib import import_module
from pathlib import Path
from sys import path as sys_path
from sys import stdout
from tempfile import TemporaryDirectory
from zipfile import ZipFile

if __package__ in {None, ""}:
    sys_path.append(str(object=Path(__file__).resolve().parents[4]))
    with suppress(ImportError):
        import_module(
            name="exactus.packages.project_python",
        ).switch_to_project_venv()
from exactus.packages.tree import render_tree


def main() -> int:
    """Render one directory tree and one zip member listing.

    Returns:
        Process exit status.

    """
    with TemporaryDirectory() as scratch:
        root: Path = Path(scratch)
        demo: Path = root / "demo"
        (demo / "pkg").mkdir(parents=True)
        _ = (demo / "pkg" / "mod.py").write_text(
            data="X: int = 1\n",
            encoding="utf-8",
        )
        _ = (demo / "README.md").write_text(data="# demo\n", encoding="utf-8")
        archive: Path = root / "demo.zip"
        with ZipFile(file=archive, mode="w") as bundle:
            bundle.write(
                filename=demo / "pkg" / "mod.py",
                arcname="pkg/mod.py",
            )
            bundle.write(filename=demo / "README.md", arcname="README.md")
        text: str = (
            render_tree(source=demo) + "\n" + render_tree(source=archive)
        )
        _written: int = stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
