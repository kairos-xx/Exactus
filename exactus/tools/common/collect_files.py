# Copyright (c) 2026
"""Bundle report finding files into a ``FILES`` evidence folder.

When ``--collect-files`` reaches a tool — from its own command line,
from a ``[tool.exactus] collect-files = true`` setting, or forwarded by
the orchestrator — the reporting wrapper bundles every file the
report's ``result.json`` lists findings for into ``<report>/FILES``:
``files.zip`` keeps the project-relative folder structure, ``TREE.txt``
renders the archive contents through ``exactus.packages.tree``, and
``README.md``
describes the bundle.
"""

from __future__ import annotations

from json import JSONDecodeError, loads
from logging import Logger, getLogger
from os import environ
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final
from zipfile import ZIP_DEFLATED, ZipFile

from exactus.packages.argument_parser import normalized_option
from exactus.packages.tree import render_tree

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        flag: Grouped module constant.
        folded_flag: Grouped module constant.
        variable: Grouped module constant.
        directory: Grouped module constant.
        archive: Grouped module constant.
        tree: Grouped module constant.
        readme: Grouped module constant.
        finding_keys: Grouped module constant.
        logger: Grouped module constant.

    """

    flag: Final[str] = "--collect-files"
    folded_flag: Final[str] = "--collect_files"
    variable: Final[str] = "EXACTUS_COLLECT_FILES"
    directory: Final[str] = "FILES"
    archive: Final[str] = "files.zip"
    tree: Final[str] = "TREE.txt"
    readme: Final[str] = "README.md"
    finding_keys: Final[tuple[str, ...]] = ("file", "path", "target")
    logger: Final[Logger] = getLogger(name=__name__)


def requested(*, tokens: Sequence[str]) -> bool:
    """Report whether finding-file collection is enabled for this run.

    Args:
        tokens: Argument tokens a tool or worker received.

    Returns:
        ``True`` when the flag is among the tokens or the collection
        environment variable is already set.

    """
    return (
        any(
            normalized_option(argument=token) == Constants.folded_flag
            for token in tokens
        )
        or environ.get(Constants.variable) == "1"
    )


def mark(*, tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Export collection intent when the flag reached the tool.

    Args:
        tokens: Final argument tokens a tool is about to parse.

    Returns:
        The tokens unchanged.

    """
    if any(
        normalized_option(argument=token) == Constants.folded_flag
        for token in tokens
    ):
        environ[Constants.variable] = "1"
    return tokens


def collect_report_files(*, output: Path) -> bool:
    """Bundle the files a report lists findings for into ``FILES``.

    Args:
        output: Report directory holding ``result.json``.

    Returns:
        ``True`` when the ``FILES`` bundle was written; ``False`` when
        ``result.json`` is absent, unreadable, or the bundle could not
        be written.

    """
    try:
        payload: JsonValue = cast(
            typ="JsonValue",
            val=loads(s=(output / "result.json").read_text(encoding="utf-8")),
        )
    except (OSError, JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    root: Path = _payload_root(payload=payload)
    members, missing = _members(
        labels=_payload_files(payload=payload),
        root=root,
    )
    bundle: Path = output / Constants.directory
    archive: Path = bundle / Constants.archive
    try:
        if bundle.exists() and (not bundle.is_dir()):
            bundle.unlink()
        bundle.mkdir(parents=True, exist_ok=True)
        with ZipFile(
            file=archive,
            mode="w",
            compression=ZIP_DEFLATED,
        ) as target:
            for name, source in sorted(members.items()):
                target.write(filename=source, arcname=name)
        _ = (bundle / Constants.tree).write_text(
            data=_tree_listing(archive=archive),
            encoding="utf-8",
        )
        _ = (bundle / Constants.readme).write_text(
            data=_readme(members=members, missing=missing),
            encoding="utf-8",
        )
    except OSError:
        Constants.logger.exception(
            msg="Finding-file bundle could not be written",
        )
        return False
    return True


def _payload_root(*, payload: Mapping[str, JsonValue]) -> Path:
    """Resolve the project root a report payload names.

    Args:
        payload: Decoded ``result.json`` object.

    Returns:
        The recorded ``project_root``, else the exported project root,
        else the working directory.

    """
    recorded: JsonValue = payload.get("project_root")
    if isinstance(recorded, str) and recorded.strip():
        return Path(recorded).expanduser().resolve()
    configured: str = (
        environ.get("EXACTUS_PROJECT_ROOT")
        or environ.get("EXACTUS_ROOT")
        or ""
    )
    if configured.strip():
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def _payload_files(*, payload: dict[str, JsonValue]) -> list[str]:
    """Collect every distinct file label a report payload mentions.

    Args:
        payload: Decoded ``result.json`` object; pipeline aggregates
            contribute their ``report_snapshots`` findings too.

    Returns:
        File labels in first-seen order.

    """
    labels: list[str] = _finding_files(findings=payload.get("findings"))
    seen: set[str] = set(labels)
    snapshots: JsonValue = payload.get("report_snapshots")
    if not isinstance(snapshots, dict):
        return labels
    for snapshot in snapshots.values():
        if not isinstance(snapshot, dict):
            continue
        for label in _finding_files(findings=snapshot.get("findings")):
            if label not in seen:
                seen.add(label)
                labels.append(label)
    return labels


def _finding_files(*, findings: JsonValue) -> list[str]:
    """Extract distinct file labels from one findings list.

    Args:
        findings: The ``findings`` value of a report payload.

    Returns:
        Non-empty ``file``/``path``/``target`` labels, first seen wins.

    """
    labels: list[str] = []
    seen: set[str] = set()
    rows: list[JsonValue] = findings if isinstance(findings, list) else []
    for item in rows:
        if not isinstance(item, dict):
            continue
        label: str = next(
            (
                text
                for key in Constants.finding_keys
                if (text := str(object=item.get(key) or ""))
            ),
            "",
        )
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _members(
    *,
    labels: Sequence[str],
    root: Path,
) -> tuple[dict[str, Path], list[str]]:
    """Resolve finding labels to existing files and archive names.

    Args:
        labels: File labels reported by findings.
        root: Project root relative labels resolve against.

    Returns:
        ``(members, missing)``: archive name to source path for files
        present on disk, and the labels that resolved to no file.

    """
    members: dict[str, Path] = {}
    missing: list[str] = []
    for label in labels:
        candidate: Path = Path(label)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved: Path = candidate.resolve()
        if not resolved.is_file():
            missing.append(label)
            continue
        arcname: str = (
            resolved.relative_to(root).as_posix()
            if resolved.is_relative_to(root)
            else resolved.as_posix().lstrip("/").replace(":", "")
        )
        members.setdefault(arcname, resolved)
    return (members, missing)


def _tree_listing(*, archive: Path) -> str:
    """Render the archive contents through ``exactus.packages.tree``.

    Args:
        archive: ``files.zip`` path to list.

    Returns:
        ``TREE.txt`` text for the archive members.

    """
    return render_tree(source=archive)


def _readme(*, members: Mapping[str, Path], missing: Sequence[str]) -> str:
    """Render the bundle ``README.md``.

    Args:
        members: Archive name to source path of the collected files.
        missing: Reported labels that resolved to no file.

    Returns:
        Markdown describing the bundle contents.

    """
    lines: list[str] = [
        "# FILES — collected finding files",
        "",
        "`files.zip` bundles a copy of every file this report lists",
        "findings for, keeping the project-relative folder structure.",
        "`TREE.txt` renders the archive contents as a tree listing.",
        "",
        f"- Files collected: {len(members)}",
    ]
    if missing:
        lines.append(f"- Reported but not found on disk: {len(missing)}")
        lines.extend(f"  - `{label}`" for label in missing)
    return "\n".join(lines) + "\n"
