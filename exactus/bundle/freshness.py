# Copyright (c) 2026
"""Detect a packaged ``exactus`` that is older than its source tree.

``exactus/scripts/build_make`` stamps the staged ``exactus/`` files into
``exactus/_signature.json`` inside the executable. When that executable
notices it still lives inside the development project it compares the
stamp against the live sources and warns. The executable is meant to
be distributed alone, so the check never fires outside this
repository.
"""
from hashlib import sha256
from json import dumps, loads
from os import stat_result, walk
from pathlib import Path
from sys import argv, stderr
from typing import Final, TextIO, cast
from zipfile import BadZipFile, ZipFile

SIGNATURE_NAME: Final[str] = "_signature.json"
"""Bundle member carrying the packaged-source fingerprint."""
_BUILD_HINT: Final[str] = (
    "exactus is outdated: project sources changed after this executable "
    "was built — rebuild it from the source checkout with "
    "`python exactus --install --rebuild`.\n"
)
"""Warning printed before dispatch when the bundle is stale."""
_LARGE_FILE: Final[int] = 1 << 20
"""Files larger than this fingerprint by ``size:mtime_ns`` instead of
content, keeping partitioned payload packs cheap."""
_PAYLOAD_PART: Final[str] = "parts/fs/"
"""Path fragment for partition payloads; members may legitimately exist
in the source tree without entering the bundle."""
_BUNDLE_DEPTH: Final[int] = 2
"""Extras nested under ``bundle/<dir>/`` sit inside a target subtree —
platform filtering keeps them out of single-target bundles, so they
never prove staleness on their own."""
_BUNDLE_INVENTORY: Final[str] = "bundle/CONTENT.md"
"""Build-generated bundle inventory; written into staging after the
tree is fingerprinted, so the live file never matches the stamp."""
_GENERATED_PREFIX: Final[str] = "vendor/"
"""Staged-only shim tree written by ``shims.generate`` after staging —
it never exists in the source checkout, so stamped members cannot be
validated against live files."""
def _ignored(*, name: str) -> bool:
    """Return whether a directory entry never enters the bundle.

    Mirrors the build's ``copytree`` filter for entries cheap to
    detect: dot-entries, bytecode caches, generated report trees, and
    ``*.py[co]``.

    Args:
        name: Directory entry name.

    Returns:
        Whether the entry is skipped.

    """
    return (
        name.startswith(".")
        or name in ("__pycache__", "EXACTUS_RESULTS")
        or name.endswith(
            (".pyc", ".pyo"),
        )
    )
def tree_signature(*, exactus_dir: Path) -> dict[str, str]:
    """Fingerprint every packaged file under ``exactus_dir``.

    Args:
        exactus_dir: ``exactus`` package directory, staged or live.

    Returns:
        ``exactus/``-relative path to fingerprint mapping. Small files
        fingerprint by content; large payloads by ``size:mtime_ns``.

    """
    entries: dict[str, str] = {}
    if not exactus_dir.is_dir():
        return entries
    for directory, dirnames, filenames in walk(top=exactus_dir):
        dirnames[:] = sorted(
            name for name in dirnames if not _ignored(name=name)
        )
        for filename in sorted(filenames):
            if _ignored(name=filename) or filename == SIGNATURE_NAME:
                continue
            path: Path = Path(directory) / filename
            relative: str = path.relative_to(exactus_dir).as_posix()
            if relative == _BUNDLE_INVENTORY:
                continue
            try:
                stat: stat_result = path.stat()
            except OSError:
                continue
            if stat.st_size > _LARGE_FILE:
                entries[relative] = f"{stat.st_size}:{stat.st_mtime_ns}"
                continue
            try:
                entries[relative] = sha256(data=path.read_bytes()).hexdigest()
            except OSError:
                continue
    return entries
def render_signature(*, exactus_dir: Path) -> bytes:
    """Serialize a directory fingerprint for the build stamp.

    Args:
        exactus_dir: Staged ``exactus`` package directory.

    Returns:
        Deterministic JSON payload written inside the bundle.

    """
    return dumps(
        obj={"files": tree_signature(exactus_dir=exactus_dir)},
        sort_keys=True,
    ).encode(encoding="utf-8")
def bundle_signature(*, bundle: Path) -> dict[str, str] | None:
    """Read the packaged-source fingerprint stored inside a zipapp.

    Args:
        bundle: Executable zipapp file.

    Returns:
        The stamped ``exactus/``-relative fingerprint mapping, or
        ``None`` when the bundle predates freshness stamping.

    """
    try:
        with ZipFile(file=bundle) as archive:
            raw: str = archive.read(
                name=f"exactus/{SIGNATURE_NAME}",
            ).decode(encoding="utf-8")
    except (OSError, BadZipFile, KeyError):
        return None
    try:
        value: object = loads(s=raw)
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    parsed: dict[str, object] = cast(
        typ="dict[str, object]",
        val=value,
    )
    files: object = parsed.get("files")
    if not isinstance(files, dict):
        return None
    entries: dict[object, object] = cast(
        typ="dict[object, object]",
        val=files,
    )
    return {
        str(object=key): str(object=member) for key, member in entries.items()
    }
def dev_project_root(*, bundle: Path) -> Path | None:
    """Locate the development project that produced an executable.

    ``bin/exactus`` and ``build/exactus`` sit one directory below the
    repository root while platform releases such as
    ``bin/release/exactus_macos_arm64/exactus`` sit three below; the
    candidate root must contain the canonical CLI and the package
    build module.

    Args:
        bundle: Executable path (``sys.argv[0]``).

    Returns:
        The repository root, or ``None`` outside the dev project.

    """
    def check(*, root: Path) -> Path | None:
        markers: tuple[Path, ...] = (
            root / "exactus" / "__main__.py",
            root / "exactus" / "packages" / "package" / "build.py",
        )
        return root if all(marker.is_file() for marker in markers) else None
    resolved: Path = bundle.resolve()
    for depth in (2, 3):
        if root := check(root=resolved.parents[depth - 1]):
            return root
    if resolved.parent.name.startswith("exactus_"):
        for depth in (3, 4):
            if root := check(root=resolved.parents[depth - 1]):
                return root
    return None
def _is_zipapp(*, bundle: Path) -> bool:
    """Return whether an executable file is a Python zipapp.

    Args:
        bundle: Candidate executable path.

    Returns:
        Whether the file carries the zip signature, optionally behind a
        shebang line.

    """
    try:
        with bundle.open(mode="rb") as stream:
            head: bytes = stream.read(4096)
    except OSError:
        return False
    offset: int = head.find(b"\n") + 1 if head.startswith(b"#!") else 0
    return head[offset : offset + 2] == b"PK"
def _extra_member(*, relative: str) -> bool:
    """Return whether an unstamped live file proves staleness.

    Args:
        relative: ``exactus/``-relative path present only in the live
            tree.

    Returns:
        Whether the file should have entered the bundle — partition
        payloads and files nested inside ``bundle/<target>/`` subtrees
        are legitimately absent from single-target bundles.

    """
    if _PAYLOAD_PART in relative:
        return False
    parts: tuple[str, ...] = tuple(relative.split("/"))
    return not (parts[0] == "bundle" and len(parts) > _BUNDLE_DEPTH)
def bundle_stale(*, bundle: Path, exactus_dir: Path) -> bool:
    """Return whether a built zipapp predates the live source tree.

    Partition payload members and per-target ``bundle/`` subtrees can
    exist in the source tree without entering a single-target bundle,
    so they never mark a bundle stale on their own.

    Args:
        bundle: Executable zipapp file to check.
        exactus_dir: Live ``exactus`` package directory to compare
            against.

    Returns:
        Whether the bundle's stamp no longer matches the sources.

    """
    stamped: dict[str, str] | None = bundle_signature(bundle=bundle)
    current: dict[str, str] = tree_signature(exactus_dir=exactus_dir)
    return (
        stamped is None
        or any(
            current.get(relative) != fingerprint
            for relative, fingerprint in stamped.items()
            if not relative.startswith(_GENERATED_PREFIX)
        )
        or any(
            relative not in stamped and _extra_member(relative=relative)
            for relative in current
        )
    )
def warn_if_stale(*, stream: TextIO | None = None) -> None:
    """Print the staleness warning when the bundle is older than sources.

    Only zipapp invocations from inside the development project are
    checked; the distributed executable is standalone and never warns.

    Args:
        stream: Diagnostic stream; ``sys.stderr`` when ``None``.

    """
    out: TextIO = stderr if stream is None else stream
    bundle: Path = Path(argv[0])
    try:
        if not bundle.is_file() or not _is_zipapp(bundle=bundle):
            return
        root: Path | None = dev_project_root(bundle=bundle)
        if root is None:
            return
        if bundle_stale(bundle=bundle, exactus_dir=root / "exactus"):
            _ = out.write(_BUILD_HINT)
    except OSError:
        return
