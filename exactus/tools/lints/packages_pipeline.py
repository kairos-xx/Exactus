# Copyright (c) 2026
"""Bridge Exactus lints to packaged source-refactor and lint tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from os import cpu_count
from time import monotonic
from typing import TYPE_CHECKING, cast

from exactus.packages.all_lints import (
    AuditRunner,
    Cli,
    ReportBuilder,
    ToolResult,
    ToolSpec,
)
from exactus.packages.group_final import FinalConstantsRefactor
from exactus.packages.organize import (
    Constants,
    JavaScriptClassMethodReorderer,
    JavaScriptReorderMetrics,
    JavaScriptReorderResult,
    PythonClassMethodReorderer,
    ReorderMetrics,
    ReorderResult,
)
from exactus.packages.steps import trace

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from exactus.packages.all_lints import (
        BatchFileRepair,
        FileRepair,
        ProgressListener,
    )
type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class AllLintsRequest:
    """Inputs for one all-lints execution from the Exactus tool.

    Attributes:
        arguments: Arguments.
        batch_repair: Optional batch repair applied once per Ruff cycle.
        commands: Commands.
        excludes: Excludes.
        progress: Sink receiving each audit progress snapshot; when set,
            the embedded terminal display is suppressed.
        repair: Optional per-file repair applied inside the Ruff
            format/fix convergence loop when ``stabilize`` is set.
        root: Root.
        stabilize: Stabilize.
        targets: Targets.
        unsafe_fixes: Unsafe fixes.
        workers: Workers.

    """

    root: Path
    targets: Sequence[str]
    excludes: Sequence[str]
    commands: Mapping[str, tuple[str, ...] | None]
    arguments: Mapping[str, Sequence[str]]
    stabilize: bool
    unsafe_fixes: bool
    workers: int | None = None
    progress: ProgressListener | None = None
    repair: FileRepair | None = None
    batch_repair: BatchFileRepair | None = None


def run_group_final(*, root: Path, dry_run: bool) -> dict[str, JsonValue]:
    """Run group-final and return its report as JSON-ready data.

    Args:
        dry_run: Dry run.
        root: Root.

    Returns:
        The resulting value.

    """
    trace(
        step=(f"group final — scanning python sources (dry_run={dry_run})"),
        depth=2,
    )
    try:
        report: dict[str, JsonValue] = cast(
            typ="dict[str, JsonValue]",
            val=asdict(
                obj=FinalConstantsRefactor(root=root, dry_run=dry_run).run(),
            ),
        )
        trace(
            step=(
                f"group final — {report.get('status', 'done')}, "
                f"{report.get('constants', 0)} constants, "
                f"{report.get('changed', 0)} files changed"
            ),
            depth=2,
        )
    except SyntaxError as error:
        trace(
            step=f"group final — skipped: unparseable {error.filename}",
            depth=2,
        )
        return {
            "files": 0,
            "planned": 0,
            "constants": 0,
            "changed": 0,
            "dry_run": dry_run,
            "status": "skipped",
            "reason": f"Unparseable Python source: {error.filename}",
        }
    else:
        return report


type OrganizeResult = ReorderResult | JavaScriptReorderResult


def _organize_path(
    *,
    path: Path,
    order: Sequence[str],
) -> tuple[str, OrganizeResult]:
    """Organize one supported source file and identify its language.

    Args:
        path: Source file organized in memory.
        order: Python category order applied to Python files.

    Returns:
        Language label paired with the reorder result.

    """
    if path.suffix.lower() in {".js", ".jsx", ".mjs", ".cjs"}:
        return (
            "javascript",
            JavaScriptClassMethodReorderer(path=path).measure(),
        )
    return (
        "python",
        PythonClassMethodReorderer.reorder_source_detailed(
            order=order,
            source=path.read_text(encoding="utf-8"),
        ),
    )


def run_organize(
    *,
    paths: Sequence[Path],
    dry_run: bool,
    order: Sequence[str] = Constants.default_order,
) -> dict[str, JsonValue]:
    """Organize Python and JavaScript class methods in the resolved scope.

    JavaScript class fields and computed methods are barriers and are never
    moved because their definition-time evaluation order can be observable.

    Args:
        paths: Python and JavaScript files selected by Exactus scope
            resolution.
        dry_run: Report changes without writing files.
        order: Python category order applied to Python files.

    Returns:
        JSON-ready stage summary with reorder metrics.

    """
    scanned: int = 0
    changed: int = 0
    skipped: int = 0
    classes_seen: int = 0
    classes_reordered: int = 0
    methods_seen: int = 0
    methods_moved: int = 0
    lines_moved: int = 0
    python_files: int = 0
    javascript_files: int = 0
    trace(
        step=(
            f"organize — scanning {len(paths)} python/javascript sources "
            f"(dry_run={dry_run})"
        ),
        depth=2,
    )
    for path in sorted(paths):
        scanned += 1
        language: str = (
            "javascript"
            if path.suffix.lower() in {".js", ".jsx", ".mjs", ".cjs"}
            else "python"
        )
        try:
            language, result = _organize_path(path=path, order=order)
            if language == "javascript":
                javascript_files += 1
            else:
                python_files += 1
            result_source: str = result.source
            result_changed: bool = result.changed
            result_metrics: ReorderMetrics | JavaScriptReorderMetrics = (
                result.metrics
            )
        except (RuntimeError, SyntaxError) as error:
            skipped += 1
            message: str = (
                error.msg
                if isinstance(error, SyntaxError)
                else str(object=error)
            )
            trace(
                step=(
                    f"organize[{language}]: {path} — skipped: "
                    f"unparseable {message}"
                ),
                depth=4,
            )
            continue
        except OSError as error:
            skipped += 1
            trace(
                step=(
                    f"organize[{language}]: {path} — skipped: unreadable "
                    f"{error}"
                ),
                depth=4,
            )
            continue
        classes_seen += result_metrics.classes_seen
        classes_reordered += result_metrics.classes_reordered
        methods_seen += result_metrics.methods_seen
        methods_moved += result_metrics.methods_moved
        lines_moved += result_metrics.lines_moved
        detail: str = (
            f"{result_metrics.methods_moved} methods, "
            f"{result_metrics.classes_reordered} classes, "
            f"{result_metrics.lines_moved} lines"
        )
        if not result_changed:
            trace(step=f"organize[{language}]: {path} — unchanged", depth=4)
            continue
        changed += 1
        if dry_run:
            trace(
                step=(
                    f"organize[{language}]: {path} — would change ({detail})"
                ),
                depth=4,
            )
            continue
        _bytes_written: int = path.write_text(
            data=result_source,
            encoding="utf-8",
        )
        trace(
            step=f"organize[{language}]: {path} — changed ({detail})",
            depth=4,
        )
    trace(
        step=(
            f"organize — {scanned} files scanned "
            f"({python_files} python, {javascript_files} javascript), "
            f"{changed} changed, {skipped} skipped; "
            f"{methods_moved}/{methods_seen} methods moved across "
            f"{classes_reordered}/{classes_seen} classes ({lines_moved} lines)"
        ),
        depth=2,
    )
    return {
        "files": scanned,
        "python_files": python_files,
        "javascript_files": javascript_files,
        "changed": changed,
        "skipped": skipped,
        "classes_seen": classes_seen,
        "classes_reordered": classes_reordered,
        "methods_seen": methods_seen,
        "methods_moved": methods_moved,
        "lines_moved": lines_moved,
        "dry_run": dry_run,
    }


def _specs(
    *,
    commands: Mapping[str, tuple[str, ...] | None],
    arguments: Mapping[str, Sequence[str]],
) -> list[ToolSpec]:
    """Return all-lints specs bound to Exactus's platform tool resolver.

    Args:
        arguments: Arguments.
        commands: Commands.

    Returns:
        The resulting value.

    """
    specs: list[ToolSpec] = []
    command_names: dict[str, str] = {
        "htmlint": "htmlhint",
        "ruff_docs": "ruff",
        "typescript": "tsc",
    }
    for spec in Cli.specs():
        lookup: str = command_names.get(spec.name, spec.name)
        prefix: tuple[str, ...] | None = commands.get(lookup)
        specs.append(
            replace(
                spec,
                command_prefix=(
                    prefix
                    if prefix is not None
                    else (f"__exactus_missing_{lookup}__",)
                ),
                arguments=(*spec.arguments, *arguments.get(lookup, ())),
            ),
        )
    return specs


def run_all_lints(
    *,
    request: AllLintsRequest,
) -> tuple[dict[str, JsonValue], list[ToolResult]]:
    """Run all-lints with Exactus scope, tool arguments and bundle commands.

    Args:
        request: Request.

    Returns:
        The resulting value.

    """
    started_at: datetime = datetime.now(tz=UTC).astimezone()
    started: float = monotonic()
    specs: list[ToolSpec] = _specs(
        commands=request.commands,
        arguments=request.arguments,
    )
    trace(
        step=(
            f"all lints: specs resolved — "
            f"{', '.join(spec.name for spec in specs)}"
        ),
        depth=2,
    )
    runner: AuditRunner = AuditRunner(
        root=request.root,
        workers=request.workers or max(1, min(16, cpu_count() or 4)),
        targets=tuple(request.targets),
        excludes=tuple(request.excludes),
    )
    runner.use_repair(repair=request.repair)
    runner.use_batch_repair(repair=request.batch_repair)
    results: list[ToolResult] = runner.run_all(
        specs=specs,
        stabilize=request.stabilize,
        unsafe_fixes=request.unsafe_fixes,
        listener=request.progress,
        draw=request.progress is None,
    )
    report: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=ReportBuilder.build(
            root=request.root,
            started_at=started_at,
            duration_seconds=monotonic() - started,
            results=results,
        ),
    )
    trace(
        step=(
            f"all lints: report built — {len(results)} tools, "
            f"{sum(len(item.diagnostics) for item in results)} "
            "diagnostics"
        ),
        depth=2,
    )
    return report, results


def legacy_tools(*, results: Sequence[ToolResult]) -> dict[str, JsonValue]:
    """Adapt all-lints results to the established Exactus report schema.

    Args:
        results: Results.

    Returns:
        The resulting value.

    """
    tools: dict[str, JsonValue] = {}
    for result in results:
        name: str = "htmlhint" if result.name == "htmlint" else result.name
        findings: list[JsonValue] = [
            {
                "tool": name,
                "file": diagnostic.file or "",
                "line": diagnostic.line or 0,
                "column": diagnostic.column or 0,
                "end_line": diagnostic.end_line or 0,
                "end_column": diagnostic.end_column or 0,
                "severity": (
                    "information"
                    if diagnostic.severity in {"info", "note"}
                    else diagnostic.severity
                ),
                "rule": diagnostic.code or "",
                "message": diagnostic.message,
            }
            for diagnostic in result.diagnostics
        ]
        stderr: str = "\n".join(
            item.stderr.strip() for item in result.files if item.stderr.strip()
        )
        commands: list[list[str]] = [
            list(vector)
            for vector in sorted(
                {tuple(item.command) for item in result.files if item.command},
            )
        ]
        command: list[JsonValue] = cast(
            typ="list[JsonValue]",
            val=list(commands[0]) if commands else [],
        )
        entry: dict[str, JsonValue] = {
            "tool": name,
            "command": command,
            "commands": cast(typ="list[JsonValue]", val=commands),
            "files": cast(
                typ="list[JsonValue]",
                val=sorted({item.file for item in result.files}),
            ),
            "invocations": len(commands),
            "returncode": 0 if result.status == "passed" else 1,
            "stderr": (
                f"{name} is not installed."
                if result.status == "unavailable"
                else stderr
            ),
            "count": len(findings),
            "findings": findings,
            "skipped": result.status == "unavailable",
            "skipped_files": [],
            "duration_seconds": result.duration_seconds,
            "files_checked": result.completed_files,
        }
        tools[name] = entry
    return tools


def issue_baselines(
    *,
    results: Sequence[ToolResult],
) -> tuple[
    frozenset[tuple[str, int, int, str, str]],
    frozenset[tuple[str, int, int, str, str]],
]:
    """Return Ruff and BasedPyright issue identities for guarded inference.

    Args:
        results: Results.

    Returns:
        The resulting value.

    """
    by_name: dict[str, ToolResult] = {
        result.name: result for result in results
    }

    def keys(
        name: str,
        *,
        zero_based: bool,
    ) -> frozenset[tuple[str, int, int, str, str]]:
        """Return keys.

        Args:
            name: Name.
            zero_based: Zero based.

        Returns:
            The resulting value.

        """
        result: ToolResult | None = by_name.get(name)
        if result is None:
            return frozenset()
        return frozenset(
            (
                diagnostic.file or "",
                max(0, (diagnostic.line or 0) - int(zero_based)),
                max(0, (diagnostic.column or 0) - int(zero_based)),
                diagnostic.code or "",
                diagnostic.message,
            )
            for diagnostic in result.diagnostics
        )

    return keys(name="ruff", zero_based=False), keys(
        name="basedpyright",
        zero_based=True,
    )
