# Copyright (c) 2026
# Copyright (c) 2026
"""Exactus suppression markers, escape-hatch annotations, and lint config.

The built-in lint scanner enforces the project's no-concealment rules that are
not covered by the other analyzers: diagnostic-suppression comments
(``noqa``, ``type: ignore`` and friends), ``typing.Any`` and ``object``
used as typing escape hatches, and lint/type-check suppression configured
in ``pyproject.toml``.
"""

from __future__ import annotations

from ast import (
    AST,
    AsyncFunctionDef,
    Attribute,
    FunctionDef,
    Module,
    Name,
    expr,
    parse,
    walk,
)
from dataclasses import dataclass
from re import Match, Pattern
from re import compile as compile_pattern
from typing import TYPE_CHECKING, Final

from exactus.packages.steps import trace
from exactus.tools.common.cli import ExactusCommonTables, match_path

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class Constants:
    """Compliance exactus constants.

    Attributes:
        suppression_names: Diagnostic-suppression markers rejected by the
            exactus.
        skipped_dirs: Directory names excluded from repository traversal.
        duplicate_copy: Pattern matching duplicate-copy filename suffixes.
        lint_ignore_prefixes: ``pyproject.toml`` keys that configure lint
            suppression.
        allowed_lint_ignores: Ruff rule codes approved for the shared
            ``ignore`` list (formatter and docstring-style conflicts).
        typecheck_suffixes: ``report*`` values that disable diagnostics.
        environment_table: ``[[tool.*pyright.executionEnvironments]]``
            table headers holding scoped diagnostic overrides.
        suppressions: Comment-prefixed forms of the suppression markers.
        ignore_list: Ignore list.
        quoted_code: Quoted code.
        rules: Short title and category of each rule.
        excluded_reason: Reason recorded for glob-filtered files.
        builtin_excludes: Globs describing the fixed skip rules.
        default_include: Include glob reported when none is given.

    """

    suppression_names: Final[tuple[str, ...]] = (
        "noqa",
        "type: ignore",
        "pyright: ignore",
        "ruff: noqa",
        "basedpyright: ignore",
    )
    skipped_dirs: Final[frozenset[str]] = (
        ExactusCommonTables.DEFAULT_EXCLUDED_DIRS
    )
    duplicate_copy: Final[Pattern[str]] = compile_pattern(
        pattern=r" \d+(?:\.[^.]+)?$",
    )
    lint_ignore_prefixes: Final[tuple[str, ...]] = (
        "per-file-ignores",
        "extend-ignore",
    )
    allowed_lint_ignores: Final[frozenset[str]] = frozenset(
        {"COM812", "D203", "D213"},
    )
    typecheck_suffixes: Final[tuple[str, ...]] = ("false", '"none"', "'none'")
    environment_table: Final[Pattern[str]] = compile_pattern(
        pattern=(
            r"\[\[\s*tool\.(?:based)?pyright\.executionEnvironments\s*\]\]"
        ),
    )
    suppressions: Final[tuple[str, ...]] = tuple(
        f"# {name}" for name in suppression_names
    )
    ignore_list: Final[Pattern[str]] = compile_pattern(
        pattern=r"^ignore\s*=\s*\[(?P<codes>[^\]]*)\]",
    )
    quoted_code: Final[Pattern[str]] = compile_pattern(
        pattern=r'["\'](?P<code>[^"\']+)["\']',
    )
    rules: Final[dict[str, tuple[str, str]]] = {
        "CMP000": ("Module does not parse", "Parsing"),
        "CMP001": ("Suppression marker", "Suppression"),
        "CMP002": ("typing.Any usage", "Typing"),
        "CMP003": ("object annotation", "Typing"),
        "CMP004": ("Lint ignore configuration", "Configuration"),
        "CMP005": ("Type-check suppression", "Configuration"),
        "CMP006": ("pyproject.toml missing", "Configuration"),
    }
    excluded_reason: Final[str] = "excluded by include/exclude rules"
    builtin_excludes: Final[tuple[str, ...]] = (
        "**/.*",
        "**/__pycache__/**",
        "**/build/**",
        "**/dist/**",
        "**/*.egg-info/**",
        "**/*.dist-info/**",
        "**/* <number>.py",
    )
    default_include: Final[str] = "**/*.py"


@dataclass(frozen=True, slots=True)
class ComplianceFinding:
    """One compliance violation located in a scanned file.

    Attributes:
        rule: Stable rule identifier (``CMP000``-``CMP005``).
        file: Root-relative file path.
        line: 1-based line number, or ``0`` for file-level findings.
        message: Human-readable violation description.
        severity: ``error`` for enforced bans, ``warning`` for
            discouraged-but-legal constructs.

    """

    rule: str
    file: str
    line: int
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ComplianceInput:
    """Carry the inputs of one compliance exactus run.

    Attributes:
        root: Project root directory.
        includes: Include globs narrowing scanned files.
        excludes: Exclude globs narrowing scanned files.
        source_files: Pre-discovered owned Python sources. When supplied,
            repository discovery and include/exclude filtering are skipped.

    """

    root: Path
    includes: tuple[str, ...]
    excludes: tuple[str, ...]
    source_files: tuple[Path, ...] | None = None


@dataclass(frozen=True, slots=True)
class ComplianceSkip:
    """One Python file found under the root but not exactused.

    Attributes:
        target: Root-relative file path.
        reason: Why the file was not exactused.

    """

    target: str
    reason: str


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    """Outcome of one compliance exactus run.

    Attributes:
        files: Number of Python source files scanned.
        findings: Violations in deterministic order.
        includes: Include globs the run applied.
        excludes: Exclude globs the run applied.
        skipped: Files found but not exactused, with reasons.

    """

    files: int
    findings: tuple[ComplianceFinding, ...]
    includes: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    skipped: tuple[ComplianceSkip, ...] = ()


def skipped(*, name: str) -> bool:
    """Report whether a path segment is excluded from the exactus.

    Args:
        name: File or directory name.

    Returns:
        ``True`` for caches, build output, hidden entries, and numbered
        copies.

    """
    return (
        name in Constants.skipped_dirs
        or name.startswith(".")
        or name.endswith((".egg-info", ".dist-info"))
        or Constants.duplicate_copy.search(string=name) is not None
    )


def scan(
    *,
    inputs: ComplianceInput,
) -> tuple[list[Path], list[ComplianceSkip]]:
    """Collect owned Python sources and the files left out.

    Files under the fixed skip rules (caches, build output, hidden
    entries, numbered copies) are not reported; files rejected by the
    include/exclude globs are.

    Args:
        inputs: Exactus inputs carrying the root and glob filters.

    Returns:
        Sorted exactused paths and the sorted skipped files.

    """
    if inputs.source_files is not None:
        return sorted(inputs.source_files), []
    files: list[Path] = []
    left_out: list[ComplianceSkip] = []
    path: Path
    for path in sorted(inputs.root.rglob(pattern="*.py")):
        relative: Path = path.relative_to(inputs.root)
        if any(skipped(name=part) for part in relative.parts):
            continue
        if match_path(
            path=path,
            root=inputs.root,
            includes=inputs.includes,
            excludes=inputs.excludes,
        ):
            files.append(path)
        else:
            left_out.append(
                ComplianceSkip(
                    target=relative.as_posix(),
                    reason=Constants.excluded_reason,
                ),
            )
    return files, left_out


def python_files(*, inputs: ComplianceInput) -> list[Path]:
    """Collect owned Python sources under the exactus root.

    Args:
        inputs: Exactus inputs carrying the root and glob filters.

    Returns:
        Sorted source paths surviving skip and include/exclude rules.

    """
    return scan(inputs=inputs)[0]


def suppression_findings(*, path: Path, root: Path) -> list[ComplianceFinding]:
    """Reject diagnostic-suppression comment markers in one file.

    Args:
        path: Python source file to scan.
        root: Project root for relative reporting.

    Returns:
        One finding per suppression marker occurrence.

    """
    relative: str = path.relative_to(root).as_posix()
    findings: list[ComplianceFinding] = []
    number: int
    line: str
    for number, line in enumerate(
        iterable=path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        findings.extend(
            ComplianceFinding(
                rule="CMP001",
                file=relative,
                line=number,
                message=(
                    f"suppression marker {marker!r} is forbidden; "
                    "fix the underlying diagnostic"
                ),
            )
            for marker in Constants.suppressions
            if marker in line
        )
    return findings


def _escape_hatch_annotations(
    *,
    node: FunctionDef | AsyncFunctionDef,
    test_file: bool,
) -> list[expr]:
    """Return annotation expressions eligible for the ``object`` ban.

    Test doubles patch arbitrary attributes, where ``object`` is the
    honest top type rather than an escape hatch, so annotations in test
    files are exempt.

    Args:
        node: Callable definition being exactused.
        test_file: Whether the owning file lives under ``tests``.

    Returns:
        Argument and return annotation expressions to inspect.

    """
    if test_file:
        return []
    annotations: list[expr] = [
        argument.annotation
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
        if argument.annotation is not None
    ]
    if node.args.vararg is not None and node.args.vararg.annotation:
        annotations.append(node.args.vararg.annotation)
    if node.args.kwarg is not None and node.args.kwarg.annotation:
        annotations.append(node.args.kwarg.annotation)
    if node.returns is not None:
        annotations.append(node.returns)
    return annotations


def annotation_findings(*, path: Path, root: Path) -> list[ComplianceFinding]:
    """Reject ``typing.Any`` and flag ``object`` escape-hatch annotations.

    ``Any`` is forbidden outright. ``object`` annotations are reported as
    warnings: the standard avoids ``object`` as an escape hatch, but it
    remains the honest top type for intentionally generic parameters.

    Args:
        path: Python source file to scan.
        root: Project root for relative reporting.

    Returns:
        One finding per forbidden ``Any`` usage or ``object``
        annotation.

    """
    relative: str = path.relative_to(root).as_posix()
    try:
        tree: Module = parse(
            source=path.read_text(encoding="utf-8"),
            filename=relative,
        )
    except (SyntaxError, UnicodeDecodeError, OSError) as error:
        return [
            ComplianceFinding(
                rule="CMP000",
                file=relative,
                line=0,
                message=f"module does not parse: {error}",
            ),
        ]
    test_file: bool = "tests" in path.relative_to(root).parts
    findings: list[ComplianceFinding] = []
    node: AST
    for node in walk(node=tree):
        if isinstance(node, Name) and node.id == "Any":
            findings.append(
                ComplianceFinding(
                    rule="CMP002",
                    file=relative,
                    line=node.lineno,
                    message="typing.Any is forbidden",
                ),
            )
        if isinstance(node, Attribute) and node.attr == "Any":
            findings.append(
                ComplianceFinding(
                    rule="CMP002",
                    file=relative,
                    line=node.lineno,
                    message="typing.Any is forbidden",
                ),
            )
        if not isinstance(node, FunctionDef | AsyncFunctionDef):
            continue
        annotation: expr
        for annotation in _escape_hatch_annotations(
            node=node,
            test_file=test_file,
        ):
            findings.extend(
                ComplianceFinding(
                    rule="CMP003",
                    file=relative,
                    line=getattr(inner, "lineno", node.lineno),
                    message=(
                        f"object annotation in {node.name} is an escape "
                        "hatch; prefer a precise type"
                    ),
                    severity="warning",
                )
                for inner in walk(node=annotation)
                if isinstance(inner, Name) and inner.id == "object"
            )
    return findings


def _environment_suppressions(
    *,
    table: Sequence[tuple[int, str]],
    settings: Path,
) -> list[ComplianceFinding]:
    """Flag type-check suppressions in one execution-environment table.

    An environment whose ``root`` is a real subdirectory narrows where
    diagnostics apply; an absent or project-root ``root`` is global
    suppression in disguise and stays forbidden.

    Args:
        table: ``(line number, stripped line)`` rows of the table body.
        settings: ``pyproject.toml`` path that environment roots resolve
            against.

    Returns:
        One CMP005 finding per suppressed diagnostic, or none when the
        environment is scoped to a subdirectory.

    """
    env_root: str | None = None
    pending: list[int] = []
    number: int
    stripped: str
    for number, stripped in table:
        if stripped.startswith("root"):
            env_root = stripped.partition("=")[2].strip().strip('"').strip("'")
        elif stripped.startswith("report") and stripped.endswith(
            Constants.typecheck_suffixes,
        ):
            pending.append(number)
    resolved: Path = (
        settings.parent if env_root is None else settings.parent / env_root
    ).resolve()
    if resolved.is_relative_to(settings.parent.resolve()) and (
        resolved != settings.parent.resolve()
    ):
        return []
    return [
        ComplianceFinding(
            rule="CMP005",
            file="pyproject.toml",
            line=pending_line,
            message="type-check suppression is forbidden",
        )
        for pending_line in pending
    ]


def _lint_ignore_finding(
    *,
    number: int,
    stripped: str,
) -> ComplianceFinding | None:
    """Flag lint suppression configured by one ``pyproject.toml`` line.

    Args:
        number: 1-based line number.
        stripped: Stripped line content.

    Returns:
        A CMP004 finding, or ``None`` when the line configures no
        forbidden lint suppression.

    """
    if stripped.startswith("ignore"):
        match: Match[str] | None = Constants.ignore_list.match(string=stripped)
        codes: frozenset[str] = (
            frozenset(
                Constants.quoted_code.findall(string=match.group("codes")),
            )
            if match is not None
            else frozenset()
        )
        if match is None or not codes <= Constants.allowed_lint_ignores:
            return ComplianceFinding(
                rule="CMP004",
                file="pyproject.toml",
                line=number,
                message=(
                    "lint ignore configuration is forbidden; "
                    "allowed: "
                    f"{sorted(Constants.allowed_lint_ignores)}"
                ),
            )
        return None
    if stripped.startswith(Constants.lint_ignore_prefixes):
        return ComplianceFinding(
            rule="CMP004",
            file="pyproject.toml",
            line=number,
            message="lint ignore configuration is forbidden",
        )
    return None


def configuration_findings(*, root: Path) -> list[ComplianceFinding]:
    """Reject lint and type-check suppression configuration.

    Args:
        root: Project root containing ``pyproject.toml``.

    Returns:
        One finding per suppression setting, or one finding when the
        file is missing.

    """
    settings: Path = root / "pyproject.toml"
    if not settings.is_file():
        return [
            ComplianceFinding(
                rule="CMP006",
                file="pyproject.toml",
                line=0,
                message="pyproject.toml is missing",
            ),
        ]
    findings: list[ComplianceFinding] = []
    environment: list[tuple[int, str]] = []
    scoped: bool = False
    number: int
    line: str
    for number, line in enumerate(
        iterable=settings.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped: str = line.strip()
        if stripped.startswith("["):
            if scoped:
                findings.extend(
                    _environment_suppressions(
                        table=environment,
                        settings=settings,
                    ),
                )
            environment = []
            scoped = (
                Constants.environment_table.match(string=stripped) is not None
            )
            continue
        if scoped:
            environment.append((number, stripped))
            continue
        lint_finding: ComplianceFinding | None = _lint_ignore_finding(
            number=number,
            stripped=stripped,
        )
        if lint_finding is not None:
            findings.append(lint_finding)
        if stripped.startswith("report") and stripped.endswith(
            Constants.typecheck_suffixes,
        ):
            findings.append(
                ComplianceFinding(
                    rule="CMP005",
                    file="pyproject.toml",
                    line=number,
                    message="type-check suppression is forbidden",
                ),
            )
    if scoped:
        findings.extend(
            _environment_suppressions(table=environment, settings=settings),
        )
    return findings


def scan_compliance(*, inputs: ComplianceInput) -> ComplianceResult:
    """Exactus owned Python sources and lint configuration.

    Args:
        inputs: Exactus inputs carrying the root and glob filters.

    Returns:
        Scanned-file count and every compliance finding.

    """
    findings: list[ComplianceFinding] = []
    files: list[Path]
    left_out: list[ComplianceSkip]
    files, left_out = scan(inputs=inputs)
    trace(
        step=(f"compliance: {len(files)} files, {len(left_out)} skipped"),
        depth=3,
    )
    for skip in left_out:
        trace(
            step=f"compliance: {skip.target} — skipped: {skip.reason}",
            depth=4,
        )
    path: Path
    for path in files:
        found: list[ComplianceFinding] = [
            *suppression_findings(path=path, root=inputs.root),
            *annotation_findings(path=path, root=inputs.root),
        ]
        findings.extend(found)
        if found:
            trace(step=f"compliance: {path} — {len(found)} findings", depth=4)
    trace(step="compliance: configuration check", depth=3)
    findings.extend(configuration_findings(root=inputs.root))
    return ComplianceResult(
        files=len(files),
        findings=tuple(findings),
        includes=inputs.includes,
        excludes=inputs.excludes,
        skipped=tuple(left_out),
    )
