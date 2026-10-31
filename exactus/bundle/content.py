# Copyright (c) 2026
"""Render ``CONTENT.md`` inventories for staged bundle roots.

A bundle root holds one directory per target —
``<os>/<arch>`` or ``<os>/<libc>/<arch>`` — each with a
``data/bundle.json`` manifest describing the staged components and the
exact tool versions they carry. The generated inventory lists the
operating systems, architectures, and installed tools so a staged tree
documents itself without the builder's logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from json import loads
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from pathlib import Path
CONTENT_NAME: Final[str] = "CONTENT.md"
"""Inventory file generated at each bundle root."""
_MANIFEST: Final[str] = "data/bundle.json"
"""Per-target manifest holding components and resolved versions."""
_LIBC_LAYOUT_PARTS: Final[int] = 3
"""Path depth of ``<os>/<libc>/<arch>`` target leaves."""
@final
@dataclass(frozen=True, slots=True)
class _Target:
    """Describe one staged bundle target's manifest.

    Attributes:
        platform: Canonical target name such as ``linux-glibc-amd64``.
        system: Operating system directory name.
        libc: C library variant directory name, empty when absent.
        arch: Architecture directory name.
        components: Installed component names.
        python: ``(package, version)`` pairs of bundled Python tools.
        node: Bundled Node.js runtime version.
        node_packages: ``(package, version)`` pairs of bundled npm tools.

    """

    platform: str
    system: str
    libc: str
    arch: str
    components: tuple[str, ...]
    python: tuple[tuple[str, str], ...]
    node: str
    node_packages: tuple[tuple[str, str], ...]
def _pairs(*, value: object) -> tuple[tuple[str, str], ...]:
    """Return sorted ``(name, version)`` pairs from a JSON object.

    Args:
        value: Decoded JSON member, expected to be an object of strings.

    Returns:
        Sorted string pairs; empty for non-object input.

    """
    pairs: list[tuple[str, str]] = []
    if not isinstance(value, dict):
        return ()
    members: dict[object, object] = cast("dict[object, object]", value)
    name: object
    version: object
    for name, version in members.items():
        if isinstance(name, str) and isinstance(version, str):
            pairs.append((name, version))
    return tuple(sorted(pairs))
def _leaves(*, root: Path) -> list[Path]:
    """Return target directories holding a bundle manifest.

    Args:
        root: Bundle root to scan.

    Returns:
        Sorted directories containing ``data/bundle.json``, skipping
        hidden build-cache subtrees.

    """
    leaves: list[Path] = []
    manifest: Path
    for manifest in root.glob(pattern=f"**/{_MANIFEST}"):
        hidden: bool = False
        part: str
        for part in manifest.parent.relative_to(root).parts:
            if part.startswith("."):
                hidden = True
                break
        if not hidden:
            leaves.append(manifest.parent.parent)
    return sorted(leaves)
def _target(*, root: Path, leaf: Path) -> _Target:
    """Load one target's bundle manifest.

    Args:
        root: Bundle root the leaf is relative to.
        leaf: Target directory holding ``data/bundle.json``.

    Returns:
        Parsed target description.

    """
    relative: tuple[str, ...] = leaf.relative_to(root).parts
    document: object = loads(
        s=(leaf / _MANIFEST).read_text(encoding="utf-8"),
    )
    fields: dict[str, object] = (
        cast("dict[str, object]", document)
        if isinstance(document, dict)
        else {}
    )
    versions_value: object = fields.get("versions")
    versions: dict[str, object] = (
        cast("dict[str, object]", versions_value)
        if isinstance(versions_value, dict)
        else {}
    )
    components: object = fields.get("components")
    names: list[str] = (
        sorted(cast("dict[str, object]", components))
        if isinstance(components, dict)
        else []
    )
    platform: object = fields.get("platform")
    node: object = versions.get("node")
    return _Target(
        platform=(
            platform
            if isinstance(platform, str)
            else "-".join(relative)
        ),
        system=relative[0] if relative else "",
        libc=relative[1] if len(relative) == _LIBC_LAYOUT_PARTS else "",
        arch=relative[-1] if relative else "",
        components=tuple(names),
        python=_pairs(value=versions.get("python")),
        node=node if isinstance(node, str) else "",
        node_packages=_pairs(value=versions.get("node_packages")),
    )
def _merged(
    *,
    targets: list[_Target],
) -> dict[str, dict[str, set[str]]]:
    """Merge tool versions across targets.

    Args:
        targets: Parsed bundle targets.

    Returns:
        Each tool name mapped to ``{version: {platform, ...}}``.

    """
    merged: dict[str, dict[str, set[str]]] = {}
    target: _Target
    for target in targets:
        packages: list[tuple[str, str]] = [
            *target.python,
            *target.node_packages,
        ]
        if target.node:
            packages.append(("node", target.node))
        name: str
        version: str
        for name, version in packages:
            if name not in merged:
                merged[name] = {}
            versions: dict[str, set[str]] = merged[name]
            if version not in versions:
                versions[version] = set()
            versions[version].add(target.platform)
    return merged
def content_markdown(*, targets: list[_Target]) -> str:
    """Render the inventory document for staged targets.

    Args:
        targets: Parsed bundle targets.

    Returns:
        Markdown table listing targets, operating systems,
        architectures, and installed tool versions.

    """
    lines: list[str] = [
        "# `bundle/` contents",
        "",
        "Generated inventory of the offline tool payloads staged in this",
        "directory. Regenerate with `python exactus/scripts/bundle_make`",
        "(full source bundle) or `python exactus/scripts/build_make`",
        "(staged subset).",
        "",
        "## Targets",
        "",
        "| Platform | OS | Libc | Architecture | Components |",
        "| --- | --- | --- | --- | --- |",
    ]
    all_platforms: set[str] = set()
    target: _Target
    for target in targets:
        all_platforms.add(target.platform)
        spans: list[str] = []
        component: str
        for component in target.components:
            span: str = f"`{component}`"
            spans.append(span)
        lines.append(
            f"| `{target.platform}` | {target.system} | "
            f"{target.libc or '—'} | {target.arch} | "
            f"{', '.join(spans)} |",
        )
    lines.extend(
        [
            "",
            "## Installed tools",
            "",
            "| Tool | Version | Targets |",
            "| --- | --- | --- |",
        ],
    )
    merged: dict[str, dict[str, set[str]]] = _merged(targets=targets)
    name: str
    for name in sorted(merged):
        versions: dict[str, set[str]] = merged[name]
        version: str
        for version in sorted(versions):
            platforms: set[str] = versions[version]
            scope: str = (
                "all"
                if platforms == all_platforms
                else ", ".join(sorted(platforms))
            )
            lines.append(f"| `{name}` | `{version}` | {scope} |")
    lines.append("")
    return "\n".join(lines)
def write_content(*, root: Path) -> Path | None:
    """Write ``CONTENT.md`` for a staged bundle root.

    Args:
        root: Bundle root containing per-target subdirectories.

    Returns:
        The written file path, or ``None`` when the root holds no
        bundle targets.

    """
    targets: list[_Target] = []
    leaf: Path
    for leaf in _leaves(root=root):
        target: _Target = _target(root=root, leaf=leaf)
        targets.append(target)
    if not targets:
        return None
    destination: Path = root / CONTENT_NAME
    _ = destination.write_text(
        data=content_markdown(targets=targets),
        encoding="utf-8",
    )
    return destination
