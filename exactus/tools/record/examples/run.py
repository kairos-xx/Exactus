#!/usr/bin/env python3
# Copyright (c) 2026
"""Load and summarize the bundled branching Record workspace."""

from pathlib import Path
from sys import path as import_path
from sys import stdout
from typing import TYPE_CHECKING

if __package__ in {None, ""}:
    import_path.insert(0, str(object=Path(__file__).resolve().parents[4]))
from exactus.tools.record.store import WorkspaceCodec

if TYPE_CHECKING:
    from exactus.tools.record.model import Workspace


def main() -> int:
    """Validate the example workspace and print its graph size.

    Returns:
        Zero when the workspace is valid and nonempty.

    """
    path: Path = (
        Path(__file__).resolve().parent
        / "assets"
        / "branching-demo.pwflow.json"
    )
    workspace: Workspace = WorkspaceCodec.load(path=path)
    _ = stdout.write(
        f"workspace: {path.name}\n"
        f"flows: {len(workspace.flows)}\n"
        f"edges: {len(workspace.edges)}\n",
    )
    return int(not workspace.flows)


if __name__ == "__main__":
    raise SystemExit(main())
