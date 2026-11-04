# Copyright (c) 2026
"""Run delimiter and notation work in one bounded per-file pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from os import cpu_count
from typing import TYPE_CHECKING

from exactus.tools.common.runtime import LaneProgress
from exactus.tools.common.source_cache import SourceCache
from exactus.tools.lints.js_delimiters import (
    DelimiterFinding,
    DelimiterHeal,
    DelimiterInput,
    DelimiterResult,
    JavaScriptDelimiterSimplifier,
    audit_delimiters,
)
from exactus.tools.lints.js_function_blocks import (
    FunctionBlocksFinding,
    FunctionBlocksHeal,
    FunctionBlocksInput,
    FunctionBlocksResult,
    JavaScriptBlockAnalyzer,
    audit_function_blocks,
)

if TYPE_CHECKING:
    from pathlib import Path


def scan_javascript_conventions(
    *,
    delimiters: DelimiterInput,
    notation: FunctionBlocksInput,
    progress_span: tuple[float, float] = (0.0, 1.0),
) -> tuple[DelimiterResult, FunctionBlocksResult]:
    """Share source reads and scheduling while retaining specialist grammars.

    Args:
        delimiters: Delimiter scope and mutation policy.
        notation: Notation scope and mutation policy.
        progress_span: Parent conventions progress slice.

    Returns:
        Separate compatible reports from one per-file traversal.

    """
    files: tuple[Path, ...] = tuple(
        sorted(set(delimiters.files) | set(notation.files)),
    )
    delimiter_paths: frozenset[Path] = frozenset(delimiters.files)
    notation_paths: frozenset[Path] = frozenset(notation.files)
    espree: str | None = None
    resolution_error: FunctionBlocksFinding | None = None
    if notation.files:
        try:
            espree = JavaScriptBlockAnalyzer(
                path=notation.files[0],
            ).resolve_espree()
        except (RuntimeError, OSError, ValueError) as error:
            resolution_error = FunctionBlocksFinding(
                rule="JSN003",
                file=".",
                line=0,
                column=0,
                message=str(object=error),
                severity="error",
            )
    lanes: LaneProgress = LaneProgress(
        total=len(files),
        step="JavaScript conventions",
        span=progress_span,
    )
    simplifier: JavaScriptDelimiterSimplifier = JavaScriptDelimiterSimplifier(
        validate=delimiters.validate,
    )
    with SourceCache() as cache:

        def audit(
            path: Path,
        ) -> tuple[
            DelimiterFinding | DelimiterHeal | None,
            FunctionBlocksFinding | FunctionBlocksHeal | None,
        ]:
            """Process both conventions for one owned source.

            Args:
                path: JavaScript source candidate.

            Returns:
                Independent delimiter and notation outcomes.

            """
            label: str = str(object=path)
            lanes.begin(item=label)
            try:
                source: str | None
                try:
                    source = cache.text(path=path)
                except (OSError, UnicodeError):
                    source = None
                delimiter: DelimiterFinding | DelimiterHeal | None = (
                    audit_delimiters(
                        path=path,
                        simplifier=simplifier,
                        root=delimiters.root,
                        fix=delimiters.fix,
                        source=source,
                    )
                    if path in delimiter_paths
                    else None
                )
                if isinstance(delimiter, DelimiterHeal):
                    cache.invalidate(path=path)
                    source = cache.text(path=path)
                block: FunctionBlocksFinding | FunctionBlocksHeal | None = (
                    audit_function_blocks(
                        path=path,
                        root=notation.root,
                        fix=notation.fix,
                        espree=espree,
                        source=source,
                    )
                    if path in notation_paths and resolution_error is None
                    else None
                )
            except Exception as error:
                lanes.finish(item=label, error=str(object=error))
                raise
            lanes.finish(item=label)
            return delimiter, block

        pool: ThreadPoolExecutor
        with ThreadPoolExecutor(
            max_workers=max(1, min(cpu_count() or 1, 16, len(files))),
        ) as pool:
            results: tuple[
                tuple[
                    DelimiterFinding | DelimiterHeal | None,
                    FunctionBlocksFinding | FunctionBlocksHeal | None,
                ],
                ...,
            ] = tuple(pool.map(audit, files))
    return (
        DelimiterResult(
            files=len(delimiters.files),
            findings=tuple(
                result
                for result, _ in results
                if isinstance(result, DelimiterFinding)
            ),
            healed=tuple(
                result
                for result, _ in results
                if isinstance(result, DelimiterHeal)
            ),
        ),
        FunctionBlocksResult(
            files=len(notation.files) if resolution_error is None else 0,
            findings=(
                (resolution_error,)
                if resolution_error is not None
                else tuple(
                    result
                    for _, result in results
                    if isinstance(result, FunctionBlocksFinding)
                )
            ),
            healed=tuple(
                result
                for _, result in results
                if isinstance(result, FunctionBlocksHeal)
            ),
        ),
    )
