"""Command-line interface for :mod:`exactus.packages.package`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from exactus.packages.argument_parser import ExactusArgumentParser
from exactus.packages.package.api import run
from exactus.packages.package.config import (
    BuildConfig,
    BundleConfig,
    PackageConfig,
    PipelineConfig,
    load_config,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


def create_parser() -> ArgumentParser:
    """Create the unified CLI parser.

    Returns:
        Argument parser covering every pipeline flag.

    """
    parser: ArgumentParser = ExactusArgumentParser(
        prog="python -m exactus.packages.package",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--pyproject", type=Path)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run build stage.",
    )
    parser.add_argument(
        "--bundle",
        action="store_true",
        help="Run bundle stage.",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Run package stage.",
    )
    parser.add_argument("--build-target", action="append", default=None)
    parser.add_argument("--build-exec-target", action="append", default=None)
    parser.add_argument("--build-no-check", action="store_true")
    parser.add_argument("--build-no-dist", action="store_true")
    parser.add_argument("--build-no-tree", action="store_true")
    parser.add_argument("--build-no-exactus-results", action="store_true")
    parser.add_argument("--build-output", type=Path)
    parser.add_argument(
        "--build-self-test",
        action="store_true",
        help="Enable the self_test diagnostic on built executables.",
    )
    parser.add_argument("--bundle-target", action="append", default=None)
    parser.add_argument("--bundle-node-version")
    parser.add_argument("--bundle-optional", action="append", default=None)
    parser.add_argument("--bundle-exclude", action="append", default=None)
    parser.add_argument("--bundle-only", action="append", default=None)
    parser.add_argument("--bundle-part-bytes", type=int)
    parser.add_argument("--bundle-output", type=Path)
    parser.add_argument("--bundle-parts-dir", type=Path)
    parser.add_argument("--bundle-rebuild", action="store_true")
    parser.add_argument("--package-output", type=Path)
    parser.add_argument("--package-no-exactus-results", action="store_true")
    return parser


def main(*, arguments: tuple[str, ...] | None = None) -> int:
    """Run the unified CLI.

    Args:
        arguments: Command-line arguments excluding the program name.

    Returns:
        Exit status code.

    """
    parser: ArgumentParser = create_parser()
    args: Namespace = parser.parse_args(args=arguments)
    root: Path = args.root.resolve()
    loaded: PipelineConfig = load_config(root=root, path=args.pyproject)
    selected: bool = bool(args.build or args.bundle or args.package)
    build_config: BuildConfig = BuildConfig(
        enabled=loaded.build.enabled,
        check=False if args.build_no_check else loaded.build.check,
        dist=False if args.build_no_dist else loaded.build.dist,
        tree=False if args.build_no_tree else loaded.build.tree,
        include_exactus_results=False
        if args.build_no_exactus_results
        else loaded.build.include_exactus_results,
        targets=tuple(args.build_target)
        if args.build_target is not None
        else loaded.build.targets,
        exec_targets=tuple(args.build_exec_target)
        if args.build_exec_target is not None
        else loaded.build.exec_targets,
        output=args.build_output or loaded.build.output,
        self_test=bool(args.build_self_test or loaded.build.self_test),
    )
    bundle_config: BundleConfig = BundleConfig(
        enabled=loaded.bundle.enabled,
        targets=tuple(args.bundle_target)
        if args.bundle_target is not None
        else loaded.bundle.targets,
        node_version=args.bundle_node_version or loaded.bundle.node_version,
        optional=tuple(args.bundle_optional)
        if args.bundle_optional is not None
        else loaded.bundle.optional,
        exclude=tuple(args.bundle_exclude)
        if args.bundle_exclude is not None
        else loaded.bundle.exclude,
        only=tuple(args.bundle_only)
        if args.bundle_only is not None
        else loaded.bundle.only,
        part_bytes=args.bundle_part_bytes
        if args.bundle_part_bytes is not None
        else loaded.bundle.part_bytes,
        output=args.bundle_output or loaded.bundle.output,
        parts_dir=args.bundle_parts_dir or loaded.bundle.parts_dir,
        rebuild=bool(args.bundle_rebuild or loaded.bundle.rebuild),
    )
    package_config: PackageConfig = PackageConfig(
        enabled=loaded.package.enabled,
        output=args.package_output or loaded.package.output,
        include_exactus_results=False
        if args.package_no_exactus_results
        else loaded.package.include_exactus_results,
    )
    _ = run(
        root=root,
        build_stage=bool(args.build) if selected else None,
        bundle_stage=bool(args.bundle) if selected else None,
        package_stage=bool(args.package) if selected else None,
        build_config=build_config,
        bundle_config=bundle_config,
        package_config=package_config,
        pyproject=args.pyproject,
    )
    return 0
