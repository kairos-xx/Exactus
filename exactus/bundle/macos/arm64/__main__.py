#!/usr/bin/env python3
# __EXACTUS_TOOLS_PAYLOAD__
"""Offline partitioned filesystem dispatcher."""
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .partition_launcher import main
else:
    from partition_launcher import main
if __name__ == "__main__":
    catalog: Path = Path(__file__).resolve().parent
    catalog /= "data/parts/fs/catalog.json"
    raise SystemExit(main(catalog_path=catalog))
