#!/usr/bin/env python3
"""Complete Python API example."""

from pathlib import Path
from sys import path as sys_path

if __package__ in (None, ""):
    sys_path.insert(0, str(object=Path(__file__).resolve().parents[5]))
from typing import TYPE_CHECKING

from exactus.packages.package import (
    BuildConfig,
    BundleConfig,
    PackageConfig,
    run,
)

if TYPE_CHECKING:
    from exactus.packages.package.api import RunResult


def main() -> int:
    """Run all stages through the Python API.

    Returns:
        Exit status code.

    """
    root: Path = Path.cwd()
    result: RunResult = run(
        root=root,
        build_stage=True,
        bundle_stage=True,
        package_stage=True,
        build_config=BuildConfig(targets=("linux-glibc-amd64",)),
        bundle_config=BundleConfig(
            targets=("linux-glibc-amd64",),
            optional=("jinja2",),
        ),
        package_config=PackageConfig(),
    )
    for _stage in result.stages:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
