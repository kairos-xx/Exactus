"""Typed configuration for the build, bundle, and package pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from tomllib import load as load_toml
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path
type ConfigValue = (
    bool | float | int | str | list["ConfigValue"] | dict[str, "ConfigValue"]
)
type ConfigTable = dict[str, ConfigValue]


@dataclass(frozen=True, slots=True, kw_only=True)
class BuildConfig:
    """Build-stage settings.

    Attributes:
        enabled: Whether the stage runs by default.
        check: Produce the check executable.
        dist: Produce the unzipped dist directory.
        tree: Produce the project tree listing.
        include_exactus_results: Include EXACTUS_RESULTS in artifacts.
        targets: Bundle targets the build prepares.
        exec_targets: Targets whose executables get checked.
        output: Explicit executable output path.
        self_test: Expose the ``self_test`` diagnostic on built
            executables.

    """

    enabled: bool = False
    check: bool = True
    dist: bool = True
    tree: bool = True
    include_exactus_results: bool = True
    targets: tuple[str, ...] = ()
    exec_targets: tuple[str, ...] = ()
    output: Path | None = None
    self_test: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class BundleConfig:
    """Bundle-stage settings.

    Attributes:
        enabled: Whether the stage runs by default.
        targets: Bundle targets to produce.
        node_version: Node.js version embedded in bundles.
        optional: Optional components requested for inclusion.
        exclude: Components excluded from bundles.
        only: Components restricting the bundle payload.
        part_bytes: Maximum bytes per bundle part.
        output: Explicit bundle output path.
        parts_dir: Explicit directory for split bundle parts.
        rebuild: Force rebuilding instead of reusing artifacts.

    """

    enabled: bool = False
    targets: tuple[str, ...] = ()
    node_version: str = "22.21.1"
    optional: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    only: tuple[str, ...] = ()
    part_bytes: int = 90_000_000
    output: Path | None = None
    parts_dir: Path | None = None
    rebuild: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class PackageConfig:
    """Package-stage settings.

    Attributes:
        enabled: Whether the stage runs by default.
        output: Explicit archive output path.
        include_exactus_results: Include EXACTUS_RESULTS in the archive.

    """

    enabled: bool = False
    output: Path | None = None
    include_exactus_results: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineConfig:
    """Complete three-stage configuration.

    Attributes:
        root: Project root the configuration was loaded from.
        build: Build-stage settings.
        bundle: Bundle-stage settings.
        package: Package-stage settings.

    """

    root: Path
    build: BuildConfig = field(default_factory=BuildConfig)
    bundle: BundleConfig = field(default_factory=BundleConfig)
    package: PackageConfig = field(default_factory=PackageConfig)


def _strings(*, table: ConfigTable, key: str, source: str) -> tuple[str, ...]:
    """Read a list-of-strings field from a stage table.

    Args:
        table: Stage configuration table.
        key: Field name.
        source: Dotted TOML path used in error messages.

    Returns:
        Immutable string tuple; empty when the field is absent.

    Raises:
        TypeError: When the field is not a list of strings.

    """
    raw: ConfigValue = table.get(key, [])
    if not isinstance(raw, list) or not all(
        isinstance(item, str) for item in raw
    ):
        msg: str = f"{source}.{key} must be a list of strings"
        raise TypeError(msg)
    return tuple(cast(typ="list[str]", val=raw))


def _bool(*, table: ConfigTable, key: str, default: bool, source: str) -> bool:
    """Read a boolean field from a stage table.

    Args:
        table: Stage configuration table.
        key: Field name.
        default: Fallback when the field is absent.
        source: Dotted TOML path used in error messages.

    Returns:
        Configured boolean or the default.

    Raises:
        TypeError: When the field is not a boolean.

    """
    raw: ConfigValue = table.get(key, default)
    if not isinstance(raw, bool):
        msg: str = f"{source}.{key} must be a boolean"
        raise TypeError(msg)
    return raw


def _path(
    *,
    root: Path,
    table: ConfigTable,
    key: str,
    source: str,
) -> Path | None:
    """Read a root-relative path field from a stage table.

    Args:
        root: Project root the path resolves against.
        table: Stage configuration table.
        key: Field name.
        source: Dotted TOML path used in error messages.

    Returns:
        Resolved path or ``None`` when the field is absent.

    Raises:
        TypeError: When the field is not a string path.

    """
    raw: ConfigValue | None = table.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        msg: str = f"{source}.{key} must be a string path"
        raise TypeError(msg)
    return root / raw


def load_config(*, root: Path, path: Path | None = None) -> PipelineConfig:
    """Load ``[tool.package]`` and its stage subtables.

    Args:
        root: Project root.
        path: Optional pyproject path; defaults to ``root/pyproject.toml``.

    Returns:
        Validated pipeline configuration.

    Raises:
        TypeError: When ``[tool.package]`` or a stage table has an invalid
            shape.

    """
    config_path: Path = path or root / "pyproject.toml"
    if not config_path.is_file():
        return PipelineConfig(root=root)
    with config_path.open(mode="rb") as stream:
        document: ConfigTable = load_toml(stream)
    tool_raw: ConfigValue = document.get("tool", {})
    if not isinstance(tool_raw, dict):
        return PipelineConfig(root=root)
    section_raw: ConfigValue = tool_raw.get("package", {})
    if not isinstance(section_raw, dict):
        msg: str = "[tool.package] must be a table"
        raise TypeError(msg)
    section: ConfigTable = section_raw
    build_raw: ConfigValue = section.get("build", {})
    bundle_raw: ConfigValue = section.get("bundle", {})
    package_raw: ConfigValue = section.get("package", {})
    if not all(
        isinstance(value, dict)
        for value in (build_raw, bundle_raw, package_raw)
    ):
        msg = "[tool.package] stage settings must be tables"
        raise TypeError(msg)
    build: ConfigTable = cast(typ="ConfigTable", val=build_raw)
    bundle: ConfigTable = cast(typ="ConfigTable", val=bundle_raw)
    package: ConfigTable = cast(typ="ConfigTable", val=package_raw)
    part_bytes_raw: ConfigValue = bundle.get("part-bytes", 90_000_000)
    node_raw: ConfigValue = bundle.get("node-version", "22.21.1")
    if not isinstance(part_bytes_raw, int) or isinstance(part_bytes_raw, bool):
        msg = "[tool.package.bundle].part-bytes must be an integer"
        raise TypeError(msg)
    if not isinstance(node_raw, str):
        msg = "[tool.package.bundle].node-version must be a string"
        raise TypeError(msg)
    return PipelineConfig(
        root=root,
        build=BuildConfig(
            enabled=_bool(
                table=build,
                key="enabled",
                default=False,
                source="[tool.package.build]",
            ),
            check=_bool(
                table=build,
                key="check",
                default=True,
                source="[tool.package.build]",
            ),
            dist=_bool(
                table=build,
                key="dist",
                default=True,
                source="[tool.package.build]",
            ),
            tree=_bool(
                table=build,
                key="tree",
                default=True,
                source="[tool.package.build]",
            ),
            include_exactus_results=_bool(
                table=build,
                key="include-exactus-results",
                default=True,
                source="[tool.package.build]",
            ),
            targets=_strings(
                table=build,
                key="targets",
                source="[tool.package.build]",
            ),
            exec_targets=_strings(
                table=build,
                key="exec-targets",
                source="[tool.package.build]",
            ),
            self_test=_bool(
                table=build,
                key="self-test",
                default=False,
                source="[tool.package.build]",
            ),
        ),
        bundle=BundleConfig(
            enabled=_bool(
                table=bundle,
                key="enabled",
                default=False,
                source="[tool.package.bundle]",
            ),
            targets=_strings(
                table=bundle,
                key="targets",
                source="[tool.package.bundle]",
            ),
            node_version=node_raw,
            optional=_strings(
                table=bundle,
                key="optional",
                source="[tool.package.bundle]",
            ),
            exclude=_strings(
                table=bundle,
                key="exclude",
                source="[tool.package.bundle]",
            ),
            only=_strings(
                table=bundle,
                key="only",
                source="[tool.package.bundle]",
            ),
            part_bytes=part_bytes_raw,
            output=_path(
                root=root,
                table=bundle,
                key="output",
                source="[tool.package.bundle]",
            ),
            parts_dir=_path(
                root=root,
                table=bundle,
                key="parts-dir",
                source="[tool.package.bundle]",
            ),
            rebuild=_bool(
                table=bundle,
                key="rebuild",
                default=False,
                source="[tool.package.bundle]",
            ),
        ),
        package=PackageConfig(
            enabled=_bool(
                table=package,
                key="enabled",
                default=False,
                source="[tool.package.package]",
            ),
            output=_path(
                root=root,
                table=package,
                key="output",
                source="[tool.package.package]",
            ),
            include_exactus_results=_bool(
                table=package,
                key="include-exactus-results",
                default=True,
                source="[tool.package.package]",
            ),
        ),
    )
