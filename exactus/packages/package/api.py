"""Python API for deterministic build, bundle, package orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict, Unpack
from zipfile import ZIP_DEFLATED, ZipFile

from exactus.bundle.content import write_content
from exactus.packages.package.build import Constants as BuildConstants
from exactus.packages.package.build import (
    build_check,
    build_dist,
    build_tree,
    kept_bundle_leaves,
)
from exactus.packages.package.bundle import (
    BuildTarget,
    BuildToolsDefaults,
    BundleBuilder,
    Constants,
    bundle_dir,
    host_target,
    resolve_components,
    unavailable_components,
)
from exactus.packages.package.bundle import BundleConfig as NativeBundleConfig
from exactus.packages.package.bundle import Constants as _GroupFinalConstants
from exactus.packages.package.config import (
    BuildConfig,
    BundleConfig,
    PackageConfig,
    PipelineConfig,
    load_config,
)
from exactus.packages.package.inventory import collect_files, render_tree
from exactus.tools.common.conflict_copies import clear_conflict_copies
from exactus.tools.common.directory_inventory import heal_directory

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class StageResult:
    """One completed stage.

    Attributes:
        name: Stage identifier.
        outputs: Filesystem paths produced by the stage.

    """

    name: str
    outputs: tuple[Path, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RunResult:
    """Ordered pipeline result.

    Attributes:
        stages: Completed stages in execution order.

    """

    stages: tuple[StageResult, ...]


class RunArguments(TypedDict):
    """Optional keyword arguments accepted by :func:`run`.

    Attributes:
        build_stage: Explicit build-stage selection; ``None`` uses the
            configured value.
        bundle_stage: Explicit bundle-stage selection; ``None`` uses the
            configured value.
        package_stage: Explicit package-stage selection; ``None`` uses the
            configured value.
        build_config: Explicit build-stage configuration override.
        bundle_config: Explicit bundle-stage configuration override.
        package_config: Explicit package-stage configuration override.

    """

    build_stage: NotRequired[bool | None]
    bundle_stage: NotRequired[bool | None]
    package_stage: NotRequired[bool | None]
    build_config: NotRequired[BuildConfig | None]
    bundle_config: NotRequired[BundleConfig | None]
    package_config: NotRequired[PackageConfig | None]


def _expand_targets(*, names: tuple[str, ...], auto: bool) -> tuple[str, ...]:
    """Expand target names, groups, and aliases into concrete targets.

    Args:
        names: Requested target names, group names, or ``all``/``auto``.
        auto: Allow an empty selection to mean the detected host target.

    Returns:
        Deduplicated concrete target names in request order.

    Raises:
        ValueError: When a name is unknown or ``auto`` cannot detect the
            host target.

    """
    requested: tuple[str, ...] = names or (("auto",) if auto else ())
    expanded: list[str] = []
    for name in requested:
        if name == "all":
            expanded.extend(_GroupFinalConstants.targets)
        elif name in _GroupFinalConstants.target_groups:
            expanded.extend(_GroupFinalConstants.target_groups[name])
        elif name == "auto":
            host: str | None = host_target()
            if host is None:
                msg: str = "cannot detect host bundle target"
                raise ValueError(msg)
            expanded.append(host)
        elif name in _GroupFinalConstants.targets:
            expanded.append(name)
        else:
            msg = f"unknown target: {name}"
            raise ValueError(msg)
    return tuple(dict.fromkeys(expanded))


def build(*, config: BuildConfig, root: Path) -> StageResult:
    """Run the build stage.

    Args:
        config: Build-stage settings.
        root: Project root.

    Returns:
        Completed stage result with produced outputs.

    """
    _ = clear_conflict_copies(root=root)
    names: tuple[str, ...] = _expand_targets(names=config.targets, auto=False)
    exec_names: tuple[str, ...] = (
        _expand_targets(names=config.exec_targets, auto=False) or names
    )
    kept: frozenset[Path] | None = kept_bundle_leaves(targets=list(names))
    kept_exec: frozenset[Path] | None = kept_bundle_leaves(
        targets=list(exec_names),
    )
    outputs: list[Path] = []
    if config.check:
        check: Path = config.output or BuildConstants.check
        build_check(target=check, kept=kept_exec, self_test=config.self_test)
        outputs.append(check)
    if config.dist:
        build_dist(kept=kept, self_test=config.self_test)
        outputs.append(BuildConstants.dist)
    if config.tree:
        build_tree(
            target=BuildConstants.tree,
            include_exactus_results=config.include_exactus_results,
        )
        outputs.append(BuildConstants.tree)
    return StageResult(name="build", outputs=tuple(outputs))


def bundle(*, config: BundleConfig, root: Path) -> StageResult:
    """Run the bundle stage.

    Args:
        config: Bundle-stage settings.
        root: Project root.

    Returns:
        Completed stage result with produced outputs.

    Raises:
        ValueError: When a target name is unknown or an explicit output or
            parts directory pairs with multiple targets.

    """
    _ = clear_conflict_copies(root=root)
    target_names: tuple[str, ...] = _expand_targets(
        names=config.targets,
        auto=True,
    )
    if len(target_names) > 1 and (
        config.output is not None or config.parts_dir is not None
    ):
        msg: str = "bundle output and parts_dir require one target"
        raise ValueError(msg)
    requested: tuple[str, ...] = resolve_components(names=config.optional)
    excluded: frozenset[str] = frozenset(
        resolve_components(names=config.exclude, follow_requires=False),
    )
    only: tuple[str, ...] = resolve_components(
        names=config.only,
        follow_requires=False,
    )
    optional: tuple[str, ...] = tuple(
        name
        for name in requested
        if name not in excluded and Constants.components[name].optional
    )
    native: NativeBundleConfig = NativeBundleConfig(
        node_version=config.node_version,
        optional=tuple(
            dict.fromkeys(
                (
                    *optional,
                    *(
                        name
                        for name in only
                        if Constants.components[name].optional
                    ),
                ),
            ),
        ),
        exclude=excluded,
    )
    outputs: list[Path] = []
    for name in target_names:
        target: BuildTarget = _GroupFinalConstants.targets[name]
        target_config: NativeBundleConfig = native
        unavailable: frozenset[str] = unavailable_components(
            target=target.name,
        )
        if unavailable:
            target_config = replace(
                native,
                optional=tuple(
                    item for item in native.optional if item not in unavailable
                ),
            )
        output: Path = (
            config.output or bundle_dir(target=target.name) / "__main__.py"
        )
        _ = BundleBuilder(
            config=target_config,
            output=output,
            rebuild_args=(),
            parts_dir=config.parts_dir,
            target=target,
        ).build(
            part_bytes=config.part_bytes,
            only=only,
            rebuild=config.rebuild,
        )
        outputs.append(output)
    _ = write_content(root=BuildToolsDefaults.bundle_root)
    return StageResult(name="bundle", outputs=tuple(outputs))


def package(*, config: PackageConfig, root: Path) -> StageResult:
    """Run the package archive stage.

    Args:
        config: Package-stage settings.
        root: Project root.

    Returns:
        Completed stage result with the archive path.

    """
    _ = clear_conflict_copies(root=root)
    output: Path = (
        config.output
        or root
        / "packages"
        / f"{datetime.now().astimezone():%d%m%Y%H%M%S}"
        / f"{root.name}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    files: list[Path] = collect_files(
        root=root,
        exclude=output,
        include_exactus_results=config.include_exactus_results,
    )
    with ZipFile(file=output, mode="w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(
                filename=path,
                arcname=path.relative_to(root).as_posix(),
            )
    if config.output is None:
        tree: str = render_tree(
            root=root,
            include_exactus_results=config.include_exactus_results,
        )
        _ = (output.parent / "README.md").write_text(
            data=(
                f"# `{root.name}`\n\n            "
                f"`{root.name}.zip` is the complete filtered "
                f"project archive.\n\n            "
                f"## Project tree\n\n            ```\n            "
                f"{tree}```\n            "
            ),
            encoding="utf-8",
        )
        packages: Path = root / "packages"
        folders: list[str] = sorted(
            entry.name for entry in packages.iterdir() if entry.is_dir()
        )
        listing: str = "".join(f"- `{name}/`\n" for name in folders)
        _ = (packages / "README.md").write_text(
            data=(
                "# `packages/`\n\n            Generated archive "
                "directory.\n\n            ## Subdirectories\n\n            "
            )
            + listing,
            encoding="utf-8",
        )
        heal_directory(
            directory=output.parent,
            entries=sorted(output.parent.iterdir()),
        )
        heal_directory(directory=packages, entries=sorted(packages.iterdir()))
    return StageResult(name="package", outputs=(output,))


def run(
    *,
    root: Path,
    pyproject: Path | None = None,
    **arguments: Unpack[RunArguments],
) -> RunResult:
    """Run selected stages in canonical build -> bundle -> package order.

    Args:
        root: Project root.
        pyproject: Optional pyproject path overriding the default lookup.
        arguments: Optional stage selections and configuration overrides.

    Returns:
        Ordered results for every executed stage.

    """
    loaded: PipelineConfig = load_config(root=root, path=pyproject)
    build_config: BuildConfig | None = arguments.get("build_config")
    bundle_config: BundleConfig | None = arguments.get("bundle_config")
    package_config: PackageConfig | None = arguments.get("package_config")
    build_stage: bool | None = arguments.get("build_stage")
    bundle_stage: bool | None = arguments.get("bundle_stage")
    package_stage: bool | None = arguments.get("package_stage")
    resolved_build: BuildConfig = build_config or loaded.build
    resolved_bundle: BundleConfig = bundle_config or loaded.bundle
    resolved_package: PackageConfig = package_config or loaded.package
    want_build: bool = (
        resolved_build.enabled if build_stage is None else build_stage
    )
    want_bundle: bool = (
        resolved_bundle.enabled if bundle_stage is None else bundle_stage
    )
    want_package: bool = (
        resolved_package.enabled if package_stage is None else package_stage
    )
    if not (want_build or want_bundle or want_package):
        want_package = True
    results: list[StageResult] = []
    if want_build:
        results.append(build(config=resolved_build, root=root))
    if want_bundle:
        results.append(bundle(config=resolved_bundle, root=root))
    if want_package:
        results.append(package(config=resolved_package, root=root))
    return RunResult(stages=tuple(results))
