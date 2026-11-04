# Copyright (c) 2026
"""Match portable project globs and directory-scoped selection rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from os import environ
from pathlib import Path
from typing import Final, final


@final
class PathFilterTables:
    """Own canonical generated-directory names and portable patterns.

    Attributes:
        directories: Generated directory names at any depth.
        patterns: Exclusions independent of a run's report destination.

    """

    directories: Final[frozenset[str]] = frozenset(
        {
            "node_modules",
            "build",
            "dist",
            "env",
            "venv",
            "site-packages",
            "__pycache__",
            "coverage_report",
            "htmlcov",
            "mutants",
        },
    )
    patterns: Final[tuple[str, ...]] = (
        ".*/**",
        "**/.*/**",
        *(f"**/{name}/**" for name in sorted(directories)),
        "*.egg-info/**",
        "*.dist-info/**",
    )


def glob_match(*, relative: str, pattern: str) -> bool:
    """Match a root-relative path, including root matches for double-star.

    Args:
        relative: POSIX-style project-relative path.
        pattern: Project glob, with either platform's path separators.

    Returns:
        Whether the path matches the glob.

    """
    name: str = relative.replace("\\", "/")
    glob: str = pattern.replace("\\", "/")
    return fnmatch(name=name, pat=glob) or (
        glob.startswith("**/") and fnmatch(name=name, pat=glob[3:])
    )


def default_excludes(
    *,
    root: Path,
    reports_dir: Path | None = None,
) -> tuple[str, ...]:
    """Resolve canonical generated-directory exclusions for one run.

    Args:
        root: Analysis root.
        reports_dir: Explicit report directory; environment then default
            supply it when omitted.

    Returns:
        Deduplicated root-relative and recursive exclusion patterns.

    """
    directory: Path = reports_dir or Path(
        environ.get("EXACTUS_REPORTS_ROOT") or "EXACTUS_RESULTS",
    )
    resolved: Path = (
        directory if directory.is_absolute() else root / directory
    ).resolve()
    relative: str = (
        resolved.relative_to(root.resolve()).as_posix()
        if resolved.is_relative_to(root.resolve())
        else resolved.name
    )
    return tuple(
        dict.fromkeys(
            (
                *PathFilterTables.patterns,
                f"{relative}/**",
                f"**/{resolved.name}/**",
            ),
        ),
    )


def default_excluded_dirs(
    *,
    root: Path,
    reports_dir: Path | None = None,
) -> frozenset[str]:
    """Resolve directory names that every source walker must prune.

    Args:
        root: Analysis root.
        reports_dir: Explicit report directory, when supplied.

    Returns:
        Generated-directory names, excluding generic hidden-directory rules.

    """
    directory: Path = reports_dir or Path(
        environ.get("EXACTUS_REPORTS_ROOT") or "EXACTUS_RESULTS",
    )
    return PathFilterTables.directories | {(root / directory).name}


@dataclass(frozen=True, slots=True)
class PathFilters:
    """Represent already anchored include and exclude patterns.

    Attributes:
        includes: Union of applicable directory-scoped include globs.
        excludes: Union of applicable directory-scoped exclude globs.

    """

    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()

    def matches(self, *, relative: str) -> bool:
        """Select a path using includes followed by exclusions.

        Args:
            relative: POSIX project-relative path.

        Returns:
            Whether the path survives both filters.

        """
        return (
            not self.includes
            or any(
                glob_match(relative=relative, pattern=pattern)
                for pattern in self.includes
            )
        ) and not any(
            glob_match(relative=relative, pattern=pattern)
            for pattern in self.excludes
        )


@dataclass(frozen=True, slots=True)
class ScopedMatcher:
    """Combine global filters with rules declared in ancestor directories.

    Attributes:
        root: Analysis root.
        filters: Global selection rules.
        scoped: Directory prefixes and their local rules.

    """

    root: Path
    filters: PathFilters = field(default_factory=PathFilters)
    scoped: tuple[tuple[str, PathFilters], ...] = ()

    def matches(self, *, path: Path) -> bool:
        """Select a file without permitting paths outside the run root.

        Args:
            path: Candidate file.

        Returns:
            Whether applicable global and scoped rules select the file.

        """
        resolved: Path = path.resolve()
        if not resolved.is_relative_to(self.root.resolve()):
            return False
        relative: str = resolved.relative_to(self.root.resolve()).as_posix()
        includes: list[str] = list(self.filters.includes)
        excludes: list[str] = list(self.filters.excludes)
        for prefix, rules in self.scoped:
            if not prefix or relative.startswith(f"{prefix}/"):
                includes.extend(
                    f"{prefix}/{pattern}" if prefix else pattern
                    for pattern in rules.includes
                )
                excludes.extend(
                    f"{prefix}/{pattern}" if prefix else pattern
                    for pattern in rules.excludes
                )
        return PathFilters(
            includes=tuple(includes),
            excludes=tuple(excludes),
        ).matches(relative=relative)
