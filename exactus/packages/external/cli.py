# Copyright (c) 2026 João Lopes.
"""List and dispatch the tools bundled inside an exactus executable.

``exactus --external`` prints the bundled toolchain grouped by
runtime — OS payloads and binary tools, Python packages, and Node
packages — with the versions recorded in the leaf manifest.
``exactus --external TOOL [ARGS...]`` forwards the command line to the
bundle's partition launcher, which materializes the component and runs
the tool under the exactus's own interpreter.
"""

from __future__ import annotations

from json import loads
from os import environ
from pathlib import Path
from subprocess import run as spawn
from sys import argv, executable, stderr, stdout
from typing import TYPE_CHECKING, Final, NoReturn, cast, final

from exactus.tools.common.cli import resolve_exactus_tool_bundle

if TYPE_CHECKING:
    from collections.abc import Sequence

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        manifest_name: Grouped module constant.
        launcher_commands: Grouped module constant.
        no_bundle: Grouped module constant.
        no_manifest: Grouped module constant.

    """

    manifest_name: Final[str] = "data/bundle.json"
    launcher_commands: Final[frozenset[str]] = frozenset(
        {
            "--apply-update",
            "--help",
            "--list",
            "--list-tools",
            "--rollback",
            "--verify",
            "--verify-deep",
            "--version",
            "-h",
            "list-tools",
        },
    )
    no_bundle: Final[str] = (
        "ERROR: no compatible bundled toolchain is available"
    )
    no_manifest: Final[str] = "ERROR: bundled manifest is unavailable"


def _preferred_python() -> str:
    """Return the interpreter that should host spawned tool work.

    Returns:
        ``EXACTUS_PROJECT_PYTHON`` when exported, else the running
        interpreter.

    """
    return environ.get("EXACTUS_PROJECT_PYTHON") or executable


def _manifest(*, launcher: Path) -> JsonValue | None:
    """Decode the bundle manifest beside the resolved launcher.

    Args:
        launcher: Bundle ``__main__.py`` whose sibling ``data/``
            directory holds the manifest.

    Returns:
        The decoded JSON document, or ``None`` when unreadable.

    """
    try:
        return loads(
            s=(launcher.parent / Constants.manifest_name).read_text(
                encoding="utf-8",
            ),
        )
    except (OSError, ValueError):
        return None


def _members(*, value: JsonValue | None) -> dict[str, JsonValue]:
    """Return ``value`` as a string-keyed mapping when it is one.

    Args:
        value: Decoded JSON member.

    Returns:
        The same value as a mapping, empty otherwise.

    """
    return (
        cast(typ="dict[str, JsonValue]", val=value)
        if isinstance(value, dict)
        else {}
    )


def _strings(*, value: JsonValue | None) -> dict[str, str]:
    """Return the string-to-string members of a JSON object.

    Args:
        value: Decoded JSON member.

    Returns:
        String keys mapped to string values.

    """
    return {
        key: item
        for key, item in _members(value=value).items()
        if isinstance(item, str)
    }


def _tool_specs(*, document: JsonValue | None) -> dict[str, dict[str, str]]:
    """Collect every tool spec declared by manifest components.

    Args:
        document: Decoded bundle manifest.

    Returns:
        Tool names mapped to their ``kind``/``target`` spec.

    """
    tools: dict[str, dict[str, str]] = {}
    components: dict[str, JsonValue] = _members(
        value=_members(value=document).get("components"),
    )
    for recipe in components.values():
        metadata: dict[str, JsonValue] = _members(
            value=_members(value=recipe).get("metadata"),
        )
        for name, spec in _members(value=metadata.get("tools")).items():
            tools[name] = _strings(value=spec)
    return tools


def _version_pairs(*, document: JsonValue | None, key: str) -> dict[str, str]:
    """Return one ``versions`` member as name/version pairs.

    Args:
        document: Decoded bundle manifest.
        key: ``versions`` member name such as ``python`` or
            ``node_packages``.

    Returns:
        Package names mapped to recorded versions.

    """
    return _strings(
        value=_members(value=_members(value=document).get("versions")).get(
            key,
        ),
    )


def _node_version(*, document: JsonValue | None) -> str:
    """Return the bundled Node.js runtime version.

    Args:
        document: Decoded bundle manifest.

    Returns:
        The ``versions.node`` string, or empty when absent.

    """
    node: JsonValue | None = _members(
        value=_members(value=document).get("versions"),
    ).get("node")
    return node if isinstance(node, str) else ""


def _payload_version(*, metadata: dict[str, JsonValue], name: str) -> str:
    """Return a payload component's recorded version.

    Args:
        metadata: Component manifest member.
        name: Component name preferred among browser descriptors.

    Returns:
        The ``version`` field, the matching (or first) browser
        descriptor's version or revision, or empty when unknown.

    """
    version: JsonValue | None = metadata.get("version")
    if isinstance(version, str):
        return version
    descriptors: dict[str, dict[str, JsonValue]] = {}
    for key, item in _members(value=metadata.get("browsers")).items():
        if isinstance(item, dict):
            descriptors[key] = cast(typ="dict[str, JsonValue]", val=item)
    if not descriptors:
        return ""
    descriptor: dict[str, JsonValue] = descriptors.get(
        name,
        descriptors[sorted(descriptors)[0]],
    )
    candidate: JsonValue | None = descriptor.get("version") or descriptor.get(
        "revision",
    )
    return candidate if isinstance(candidate, str) else ""


def _os_entries(
    *,
    document: JsonValue | None,
    tools: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Collect OS-level entries: binary tools and payload components.

    Args:
        document: Decoded bundle manifest.
        tools: Tool specs collected by :func:`_tool_specs`.

    Returns:
        Entry names mapped to resolved versions, empty allowed.

    """
    entries: dict[str, str] = {}
    python_versions: dict[str, str] = _version_pairs(
        document=document,
        key="python",
    )
    node_version: str = _node_version(document=document)
    for name, spec in tools.items():
        if spec.get("kind") != "binary":
            continue
        entries[name] = python_versions.get(
            name,
            node_version if spec.get("target", "").startswith("node/") else "",
        )
    components: dict[str, JsonValue] = _members(
        value=_members(value=document).get("components"),
    )
    for name, recipe in components.items():
        metadata: dict[str, JsonValue] = _members(
            value=_members(value=recipe).get("metadata"),
        )
        if (
            metadata.get("tools")
            or metadata.get("python_packages")
            or metadata.get("node_packages")
        ):
            continue
        entries[name] = _payload_version(metadata=metadata, name=name)
    return entries


def inventory_text(*, document: JsonValue | None) -> str:
    """Render the manifest inventory grouped by runtime.

    Args:
        document: Decoded bundle manifest.

    Returns:
        ``OS``/``Python``/``Node`` sections of ``- name [version]``
        entries, or empty text when nothing is known.

    """
    tools: dict[str, dict[str, str]] = _tool_specs(document=document)
    binaries: frozenset[str] = frozenset(
        (name for name, spec in tools.items() if spec.get("kind") == "binary"),
    )
    groups: tuple[tuple[str, dict[str, str]], ...] = (
        ("OS", _os_entries(document=document, tools=tools)),
        (
            "Python",
            {
                name: version
                for name, version in _version_pairs(
                    document=document,
                    key="python",
                ).items()
                if name not in binaries
            },
        ),
        ("Node", _version_pairs(document=document, key="node_packages")),
    )
    sections: list[str] = []
    for heading, pairs in groups:
        if not pairs:
            continue
        lines: list[str] = [f"{heading}:"]
        lines.extend(
            (
                f"- {name} [{version}]" if version else f"- {name}"
                for name, version in sorted(pairs.items())
            ),
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + ("\n" if sections else "")


def run(*, arguments: Sequence[str] | None = None) -> int:
    """List the bundled toolchain or forward a command line to it.

    Args:
        arguments: ``TOOL [ARGS...]`` after ``--external``; ``argv[1:]``
            when ``None``.

    Returns:
        The tool's exit status, or ``2`` on dispatch errors.

    """
    resolved: list[str] = list(argv[1:] if arguments is None else arguments)
    launcher: Path | None = resolve_exactus_tool_bundle(root=Path.cwd())
    if launcher is None:
        _ = stderr.write(Constants.no_bundle + "\n")
        stderr.flush()
        return 2
    document: JsonValue | None = _manifest(launcher=launcher)
    if not resolved:
        text: str = inventory_text(document=document)
        if not text:
            _ = stderr.write(Constants.no_manifest + "\n")
            stderr.flush()
            return 2
        _ = stdout.write(text)
        stdout.flush()
        return 0
    name: str = resolved[0]
    if document is not None:
        known: frozenset[str] = (
            frozenset(_tool_specs(document=document))
            | Constants.launcher_commands
        )
        if name not in known:
            _ = stderr.write(f'ERROR: no bundled tool named "{name}"\n')
            stderr.flush()
            return 2
    return spawn(
        args=[_preferred_python(), str(object=launcher), *resolved],
        check=False,
    ).returncode


def main(*, arguments: Sequence[str] | None = None) -> NoReturn:
    """Run the CLI and terminate with its exit status.

    Args:
        arguments: ``TOOL [ARGS...]`` after ``--external``;
            ``argv[1:]`` when ``None``.

    Raises:
        SystemExit: Always, with the run's exit status.

    """
    raise SystemExit(run(arguments=arguments))
