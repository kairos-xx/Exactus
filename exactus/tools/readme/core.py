# Copyright (c) 2026
# Copyright (c) 2026
"""Exactus per-directory README documentation inventories.

Every directory under the documented roots must carry a ``README.md``
that mentions each of its direct files and subdirectories, keeping the
directory inventories in sync with the tree they describe. Any other
non-skipped directory that already carries a ``README.md`` is exactused
for the same inventory completeness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from re import Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final, cast

from exactus.packages.steps import trace
from exactus.tools.common.cli import ExactusCommonTables, match_path
from exactus.tools.common.directory_inventory import heal_directory
from exactus.tools.common.runtime import emit_progress
from exactus.tools.readme.metrics import collect_metrics

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


class Constants:
    """README exactus constants.

    Attributes:
        documented_roots: Project roots requiring directory
            documentation.
        skipped_dirs: Directory names excluded from repository
            traversal.
        duplicate_copy: Pattern matching duplicate-copy filename
            suffixes.
        rule_titles: Short title of each rule.
        id_prefix: Prefix of generated finding identifiers.
        excluded_reason: Reason recorded for glob-filtered directories.
        readme_name: Name of the inventory file every directory carries.
        suffix_excludes: Globs describing the fixed directory suffix
            skip rules.
        readme_glob: Include glob for directories carrying a README.

    """

    documented_roots: Final[tuple[str, ...]] = (
        "src",
        "tests",
        "examples",
        "scripts",
        "resources",
        "docs",
    )
    skipped_dirs: Final[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS
        | frozenset({"DEBUG.txt", "debug"})
    )
    duplicate_copy: Final[Pattern[str]] = compile_pattern(
        pattern=r" \d+(?:\.[^.]+)?$",
    )
    rule_titles: Final[dict[str, str]] = {
        "RDM001": "Missing README.md",
        "RDM002": "Undocumented subdirectory",
        "RDM003": "Undocumented file",
    }
    id_prefix: Final[str] = "README"
    excluded_reason: Final[str] = "excluded by include/exclude rules"
    readme_name: Final[str] = "README.md"
    suffix_excludes: Final[tuple[str, ...]] = (
        "**/.*",
        "**/*.egg-info/**",
        "**/*.dist-info/**",
    )
    readme_glob: Final[str] = "**/README.md"


@dataclass(frozen=True, slots=True)
class ReadmeFinding:
    """One documentation-inventory violation.

    Attributes:
        rule: Stable rule identifier (``RDM001``-``RDM003``).
        file: Root-relative directory or README path.
        message: Human-readable violation description.
        severity: ``error`` for every enforced requirement.

    """

    rule: str
    file: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ReadmeExactusInput:
    """Carry the inputs of one README exactus run.

    Attributes:
        root: Project root containing the documented directories.
        includes: Include globs relative to ``root``.
        excludes: Exclude globs relative to ``root``.
        fix: Whether missing documentation is repaired before validation.

    """

    root: Path
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    fix: bool = False


@dataclass(frozen=True, slots=True)
class ReadmeDirectory:
    """Inventory outcome of one exactused directory.

    Attributes:
        path: Root-relative directory path.
        has_readme: Whether the directory carries a ``README.md``.
        readme_bytes: Size of the ``README.md``; ``0`` when absent.
        entries: Direct entries that must be documented.
        documented: Entries the README documents.
        missing: Entries the README leaves out (every entry when the
            README is absent).

    """

    path: str
    has_readme: bool
    readme_bytes: int
    entries: int
    documented: int
    missing: int


@dataclass(frozen=True, slots=True)
class ReadmeSkip:
    """One directory found under the root but not exactused.

    Attributes:
        target: Root-relative directory path.
        reason: Why the directory was not exactused.

    """

    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReadmeExactusResult:
    """Aggregate the README exactus outcome.

    Attributes:
        directories: Root-relative exactused directories.
        findings: Documentation-inventory violations.
        inventories: Per-directory inventory outcomes.
        includes: Include globs the run applied.
        excludes: Exclude globs the run applied.
        skipped: Directories found but not exactused, with reasons.
        metrics: Markdown volume, README sizes and undocumented folders.

    """

    directories: tuple[str, ...]
    findings: tuple[ReadmeFinding, ...]
    inventories: tuple[ReadmeDirectory, ...] = ()
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    skipped: tuple[ReadmeSkip, ...] = ()
    metrics: dict[str, JsonValue] = field(default_factory=dict)


def skipped(*, name: str) -> bool:
    """Return whether a directory entry is excluded from inventories.

    Args:
        name: File or directory name.

    Returns:
        Whether the entry never needs documentation.

    """
    return (
        name in Constants.skipped_dirs
        or name.startswith(".")
        or name.endswith((".egg-info", ".dist-info"))
    )


def _directory_exactus(*, directory: Path, root: Path) -> list[ReadmeFinding]:
    """Check one directory's README against its live entries.

    Args:
        directory: Directory being exactused.
        root: Project root used for relative paths.

    Returns:
        One finding for a missing README or per undocumented entry.

    """
    relative: str = directory.relative_to(root).as_posix()
    readme: Path = directory / "README.md"
    if not readme.is_file():
        return [
            ReadmeFinding(
                rule="RDM001",
                file=relative,
                message="missing README.md",
            ),
        ]
    body: str = readme.read_text(encoding="utf-8")
    readme_relative: str = readme.relative_to(root).as_posix()
    findings: list[ReadmeFinding] = []
    entry: Path
    for entry in sorted(directory.iterdir()):
        if skipped(name=entry.name):
            continue
        if entry.is_dir():
            if f"`{entry.name}/`" not in body:
                findings.append(
                    ReadmeFinding(
                        rule="RDM002",
                        file=readme_relative,
                        message=(
                            f"does not document subdirectory {entry.name}/"
                        ),
                    ),
                )
        elif entry.name != "README.md" and f"`{entry.name}`" not in body:
            findings.append(
                ReadmeFinding(
                    rule="RDM003",
                    file=readme_relative,
                    message=f"does not document file {entry.name}",
                ),
            )
    return findings


def _entries(*, directory: Path) -> list[Path]:
    """List the direct entries a directory README must document.

    Args:
        directory: Directory being exactused.

    Returns:
        Sorted direct entries, without skipped names and the README.

    """
    return [
        entry
        for entry in sorted(directory.iterdir())
        if not skipped(name=entry.name) and entry.name != Constants.readme_name
    ]


def _repair_directory(*, directory: Path) -> None:
    """Refresh the standard inventory using docstrings and child READMEs.

    Args:
        directory: Directory whose children have already been repaired.

    """
    heal_directory(directory=directory, entries=_entries(directory=directory))


def _inventory(
    *,
    directory: Path,
    root: Path,
    findings: list[ReadmeFinding],
) -> ReadmeDirectory:
    """Summarize one directory's inventory outcome.

    Args:
        directory: Directory that was exactused.
        root: Project root used for relative paths.
        findings: Findings the directory exactus produced.

    Returns:
        Entry counts and README size of the directory.

    """
    readme: Path = directory / Constants.readme_name
    entries: int = len(_entries(directory=directory))
    has_readme: bool = readme.is_file()
    missing: int = (
        sum(1 for finding in findings if finding.rule != "RDM001")
        if has_readme
        else entries
    )
    return ReadmeDirectory(
        path=directory.relative_to(root).as_posix(),
        has_readme=has_readme,
        readme_bytes=readme.stat().st_size if has_readme else 0,
        entries=entries,
        documented=entries - missing,
        missing=missing,
    )


def _accepted(
    *,
    directory: Path,
    inputs: ReadmeExactusInput,
    left_out: dict[str, ReadmeSkip],
) -> bool:
    """Apply the include/exclude globs, recording rejected directories.

    Args:
        directory: Candidate directory.
        inputs: Exactus inputs carrying the root and glob filters.
        left_out: Rejected directories collected so far, by path.

    Returns:
        Whether the directory passes the filters.

    """
    if match_path(
        path=directory,
        root=inputs.root,
        includes=inputs.includes,
        excludes=inputs.excludes,
    ):
        return True
    relative: str = directory.relative_to(inputs.root).as_posix()
    left_out.setdefault(
        relative,
        ReadmeSkip(target=relative, reason=Constants.excluded_reason),
    )
    return False


def _scan(
    *,
    inputs: ReadmeExactusInput,
) -> tuple[list[Path], list[ReadmeSkip]]:
    """Collect documented directories and the directories left out.

    Args:
        inputs: Exactus inputs.

    Returns:
        Existing documented-root directories and their children, plus
        every other non-skipped directory carrying a ``README.md``, and
        the sorted directories rejected by the include/exclude globs.

    """
    root: Path = inputs.root
    directories: list[Path] = []
    left_out: dict[str, ReadmeSkip] = {}
    pending: list[Path] = [root]
    while pending:
        directory: Path = pending.pop()
        pending.extend(
            child
            for child in sorted(directory.iterdir())
            if child.is_dir()
            and not child.is_symlink()
            and not skipped(name=child.name)
        )
        if (
            directory == root
            and not inputs.fix
            and not (root / Constants.readme_name).is_file()
        ):
            continue
        if _accepted(directory=directory, inputs=inputs, left_out=left_out):
            directories.append(directory)
    directories.sort(
        key=lambda directory: (
            -len(directory.relative_to(root).parts),
            directory.relative_to(root).as_posix(),
        ),
    )
    return directories, [left_out[key] for key in sorted(left_out)]


def readme(*, inputs: ReadmeExactusInput) -> ReadmeExactusResult:
    """Exactus every documented directory's README inventory.

    Args:
        inputs: Exactus inputs.

    Returns:
        Exactused directories and every discovered violation.

    """
    root: Path = inputs.root
    trace(step="stage: scan directories", depth=1)
    directories: list[Path]
    left_out: list[ReadmeSkip]
    directories, left_out = _scan(inputs=inputs)
    trace(
        step=(
            f"readme: {len(directories)} directories to inventory, "
            f"{len(left_out)} excluded"
        ),
        depth=2,
    )
    if inputs.fix:
        trace(step="stage: repair inventories", depth=1)
        for directory in directories:
            _repair_directory(directory=directory)
            trace(
                step=(f"repair: {directory.relative_to(root).as_posix()}"),
                depth=4,
            )
    directories.sort(
        key=lambda directory: directory.relative_to(root).as_posix(),
    )
    trace(step="stage: inventory", depth=1)
    findings: list[ReadmeFinding] = []
    inventories: list[ReadmeDirectory] = []
    total: int = max(len(directories), 1)
    for index, directory in enumerate(iterable=directories, start=1):
        emit_progress(
            state="RUNNING",
            completed=index,
            total=total,
            step="inventory",
            detail=directory.relative_to(root).as_posix(),
        )
        found: list[ReadmeFinding] = _directory_exactus(
            directory=directory,
            root=root,
        )
        if found:
            trace(
                step=(
                    f"inventory: "
                    f"{directory.relative_to(root).as_posix()} — "
                    f"{len(found)} findings"
                ),
                depth=4,
            )
        inventories.append(
            _inventory(directory=directory, root=root, findings=found),
        )
        findings.extend(found)
    trace(
        step=(
            f"readme: {len(findings)} findings across "
            f"{len(inventories)} inventories"
        ),
        depth=2,
    )
    metrics: dict[str, JsonValue] = collect_metrics(
        root=root,
        includes=inputs.includes,
        excludes=inputs.excludes,
        excluded_dirs=Constants.skipped_dirs,
    )
    trace(step="metrics: collected", depth=2)
    return ReadmeExactusResult(
        directories=tuple(
            directory.relative_to(root).as_posix() for directory in directories
        ),
        findings=tuple(findings),
        inventories=tuple(inventories),
        includes=inputs.includes,
        excludes=inputs.excludes,
        skipped=tuple(left_out),
        metrics=metrics,
    )


def _counts(*, values: list[str]) -> dict[str, JsonValue]:
    """Count occurrences of each value.

    Args:
        values: Values to count.

    Returns:
        Sorted value-to-count mapping.

    """
    return {value: values.count(value) for value in sorted(set(values))}


def _sort_key(finding: ReadmeFinding) -> tuple[str, str, str]:
    """Return the report-order key of one finding.

    The path is casefolded like the template's ``$sort_by: path``, so
    finding identifiers ascend in the rendered report.

    Args:
        finding: Inventory violation.

    Returns:
        Casefolded path, rule and message.

    """
    return (finding.file.casefold(), finding.rule, finding.message)


def _ordered(*, findings: tuple[ReadmeFinding, ...]) -> list[ReadmeFinding]:
    """Order findings by path, rule and message.

    Args:
        findings: Findings in discovery order.

    Returns:
        Findings in deterministic report order.

    """
    return sorted(findings, key=_sort_key)


def _finding(*, index: int, finding: ReadmeFinding) -> dict[str, JsonValue]:
    """Return one finding in the normalized shape.

    Args:
        index: One-based position in the ordered result.
        finding: Inventory violation.

    Returns:
        Normalized finding keeping the legacy ``file`` field.

    """
    return {
        "id": f"{Constants.id_prefix}-{index:03d}",
        "title": Constants.rule_titles.get(finding.rule, finding.rule),
        "severity": finding.severity,
        "rule": finding.rule,
        "path": finding.file,
        "file": finding.file,
        "line": 0,
        "message": finding.message,
        "blocking": finding.severity == "error",
    }


def report_data(*, result: ReadmeExactusResult) -> dict[str, JsonValue]:
    """Build the normalized JSON report payload.

    Args:
        result: Exactus outcome.

    Returns:
        ``summary``, ``scope``, ``findings`` and ``extension`` blocks
        plus the legacy ``directories`` list; ``summary`` keeps the
        legacy ``directories``, ``findings`` and ``by_rule`` counters.

    """
    ordered: list[ReadmeFinding] = _ordered(findings=result.findings)
    by_rule: dict[str, JsonValue] = _counts(
        values=[finding.rule for finding in ordered],
    )
    return {
        "summary": {
            "targets_eligible": len(result.directories) + len(result.skipped),
            "targets_analyzed": len(result.directories),
            "findings_total": len(ordered),
            "severity": _counts(
                values=[finding.severity for finding in ordered],
            ),
            "directories": len(result.directories),
            "findings": len(ordered),
            "by_rule": by_rule,
        },
        "scope": {
            "include": list(
                result.includes
                or (
                    *(f"{name}/**" for name in Constants.documented_roots),
                    Constants.readme_glob,
                ),
            ),
            "exclude": [
                *result.excludes,
                *(f"**/{name}/**" for name in sorted(Constants.skipped_dirs)),
                *Constants.suffix_excludes,
            ],
            "skipped": [
                {"target": skip.target, "reason": skip.reason}
                for skip in result.skipped
            ],
        },
        "directories": cast(typ="JsonValue", val=list(result.directories)),
        "findings": [
            _finding(index=index, finding=finding)
            for index, finding in enumerate(iterable=ordered, start=1)
        ],
        "extension": {
            "metrics": result.metrics,
            "directories": [
                cast(typ="JsonValue", val=asdict(obj=inventory))
                for inventory in result.inventories
            ],
            "rules": [
                {"rule": rule, "title": title, "count": by_rule.get(rule, 0)}
                for rule, title in Constants.rule_titles.items()
            ],
        },
    }
