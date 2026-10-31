"""Orchestrate visual-cause targets, engines, queries, and verdicts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from shutil import copy2
from typing import TYPE_CHECKING, cast

from playwright.sync_api import Error as PlaywrightError

from exactus.packages.server.diagnostics import parse_server_log
from exactus.packages.visual_cause.analyzer import (
    AnalysisResults,
    Settings,
    analyze,
)
from exactus.tools.visual_cause.levels import (
    Level,
    LevelDecision,
    QueryMatch,
    decide,
)
from exactus.tools.visual_cause.queries import (
    QueryConfig,
    QueryResult,
    QuerySession,
    QuerySyntaxError,
)
from exactus.tools.visual_cause.service import LocalServices, ServedPage

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.packages.visual_cause.analyzer import (
        Cause,
        ChangeNode,
        ElementInfo,
    )
    from exactus.tools.common.json_types import JsonValue
    from exactus.tools.visual_cause.targets import Target, Viewport


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualCauseRequest:
    """One public visual-cause run request.

    Attributes:
        targets: Validated comparison targets to run.
        output: Directory receiving reports and artifacts.

    """

    targets: tuple[Target, ...]
    output: Path


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """One changed element or target-level failure.

    Attributes:
        id: Stable finding identifier.
        rule: Finding rule code.
        target: Target that produced the finding.
        viewport: Viewport label for the comparison.
        tag: Tag name of the changed element.
        css_path: Selector path of the changed element.
        query: Best matching configured query.
        candidates: Query candidates considered for the element.
        categories: Change categories observed on the element.
        origins: Origins attributed to the change.
        mechanisms: Mechanisms attributed to the change.
        geometry: Per-side bounding geometry.
        computed_style_changes: Style properties changed between sides.
        changed_pixels: Pixels attributed to the element.
        causes: Causal CSS declarations explaining the change.
        level: Decided verdict level.
        decided_by: Query name that decided the level.
        matched: Configured queries the element matched.
        message: Human-readable finding summary.

    """

    id: str
    rule: str
    target: str
    viewport: str
    tag: str
    css_path: str
    query: str
    candidates: tuple[dict[str, JsonValue], ...]
    categories: tuple[str, ...]
    origins: tuple[str, ...]
    mechanisms: tuple[str, ...]
    geometry: dict[str, dict[str, float]]
    computed_style_changes: dict[str, JsonValue]
    changed_pixels: int
    causes: tuple[dict[str, JsonValue], ...]
    level: Level
    decided_by: str | None
    matched: tuple[dict[str, JsonValue], ...]
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TargetResult:
    """One target and viewport result.

    Attributes:
        name: Target name.
        mode: Comparison mode that ran.
        viewport: Viewport label.
        url_a: Compared URL for side A.
        url_b: Compared URL for side B.
        changed_pixels: Pixels differing past the threshold.
        changed_element_count: Elements attributed to changes.
        counts: Finding counts per verdict level.
        artifacts: Artifact names to report-relative paths.
        server_diagnostics: Diagnostics collected from the file server.

    """

    name: str
    mode: str
    viewport: str
    url_a: str
    url_b: str
    changed_pixels: int
    changed_element_count: int
    counts: dict[str, int]
    artifacts: dict[str, str]
    server_diagnostics: tuple[dict[str, JsonValue], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualCauseResult:
    """Complete normalized tool result.

    Attributes:
        targets: Per-target and viewport results.
        findings: Findings across all targets.
        queries: Configured-query match summaries.
        failed: Whether any finding met the failure threshold.

    """

    targets: tuple[TargetResult, ...]
    findings: tuple[Finding, ...]
    queries: tuple[dict[str, JsonValue], ...]
    failed: bool


def _read_css(*, path: Path | None) -> str:
    """Read one stylesheet file or concatenate a directory of CSS.

    Args:
        path: CSS file or directory, or ``None`` for no source.

    Returns:
        Stylesheet text, empty when ``path`` is ``None``.

    Raises:
        FileNotFoundError: If the source is missing or has no CSS.

    """
    if path is None:
        return ""
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if path.is_dir():
        files: tuple[Path, ...] = tuple(sorted(path.rglob(pattern="*.css")))
        if not files:
            msg: str = f"CSS directory contains no files: {path}"
            raise FileNotFoundError(msg)
        return "\n\n".join(file.read_text(encoding="utf-8") for file in files)
    msg = f"CSS source not found: {path}"
    raise FileNotFoundError(msg)


def _queries(*, target: Target) -> tuple[tuple[Level, str], ...]:
    """Flatten configured verdict queries in precedence order.

    Args:
        target: Target carrying ``accept``/``warning``/``fail`` queries.

    Returns:
        ``(level, query)`` pairs ordered accept then warning then fail.

    """
    return (
        *(("accept", query) for query in target.accept),
        *(("warning", query) for query in target.warning),
        *(("fail", query) for query in target.fail),
    )


def _cause_data(
    *,
    causes: tuple[Cause, ...],
    selector: str,
    css_source: Path | None,
) -> tuple[dict[str, JsonValue], ...]:
    """Serialize causal declarations matching one changed element.

    Args:
        causes: Causal rules found by the analyzer.
        selector: Changed-element selector to filter by.
        css_source: Stylesheet path attached to serialized causes.

    Returns:
        JSON-ready causal evidence for the element.

    """
    return tuple(
        cast(
            typ="dict[str, JsonValue]",
            val={
                "selector": cause.selector,
                "css_text": cause.css_text,
                "declarations": list(cause.declarations),
                "source_files": (
                    [] if css_source is None else [str(object=css_source)]
                ),
                "pixels_explained": cause.pixels_explained,
                "explanation_ratio": cause.explanation_ratio,
            },
        )
        for cause in causes
        if selector in cause.matched
    )


def _style_changes(*, node: ChangeNode) -> dict[str, JsonValue]:
    """Serialize one node's grouped computed-style changes.

    Args:
        node: Change node carrying grouped style deltas.

    Returns:
        ``{group: {property: {"a": value, "b": value}}}`` mapping.

    """
    return {
        group: {
            name: {"a": change.a, "b": change.b}
            for name, change in changes.items()
        }
        for group, changes in node.computed_style_changes.items()
    }


def _element(*, results: AnalysisResults, selector: str) -> ElementInfo | None:
    """Look up one affected element by selector.

    Args:
        results: Completed analyzer results.
        selector: Selector to match against affected elements.

    Returns:
        Matching element info, or ``None`` when absent.

    """
    return next(
        (item for item in results.affected if item.selector == selector),
        None,
    )


def _findings(
    *,
    target: Target,
    viewport: Viewport,
    results: AnalysisResults,
    session: QuerySession,
) -> tuple[Finding, ...]:
    """Build findings for every changed node in one viewport.

    Args:
        target: Target supplying configured verdict queries.
        viewport: Viewport that was compared.
        results: Completed analyzer results.
        session: Query engine session matching elements to queries.

    Returns:
        Findings ordered as the analyzer reported its nodes.

    """
    configured_queries: tuple[tuple[Level, str], ...] = _queries(target=target)
    output: list[Finding] = []
    for node in results.nodes:
        element: ElementInfo | None = _element(
            results=results,
            selector=node.selector,
        )
        if element is None:
            continue
        matches: list[QueryMatch] = []
        for order, (level, query) in enumerate(iterable=configured_queries):
            matched, match_count = session.matching(
                css_path=node.selector,
                query=query,
            )
            if matched:
                matches.append(
                    QueryMatch(
                        level=level,
                        query=query,
                        match_count=match_count,
                        order=order,
                    ),
                )
        decision: LevelDecision = decide(
            matches=tuple(matches),
            default=cast(typ="Level", val=target.default_level),
        )
        best: QueryResult = session.best(css_path=node.selector)
        dom_path: str = element.dom_path or node.selector
        output.append(
            Finding(
                id=f"{target.name}/{viewport.label}/{dom_path}",
                rule="VCS001",
                target=target.name,
                viewport=viewport.label,
                tag=element.tag,
                css_path=node.selector,
                query=best.query,
                candidates=best.candidates,
                categories=node.categories,
                origins=node.origins,
                mechanisms=node.mechanisms,
                geometry=node.geometry,
                computed_style_changes=_style_changes(node=node),
                changed_pixels=node.changed_pixels,
                causes=_cause_data(
                    causes=results.causes,
                    selector=node.selector,
                    css_source=target.css_b,
                ),
                level=decision.level,
                decided_by=decision.decided_by,
                matched=tuple(
                    cast(typ="dict[str, JsonValue]", val=asdict(obj=item))
                    for item in decision.matched
                ),
                message=(
                    f"{element.tag} changed in {target.name} at "
                    f"{viewport.label}."
                ),
            ),
        )
    return tuple(output)


def _failure(
    *,
    target: Target,
    viewport: Viewport,
    error: Exception,
) -> Finding:
    """Build a target-level failure finding from an exception.

    Args:
        target: Target that failed.
        viewport: Viewport being compared when it failed.
        error: Raised error to report.

    Returns:
        ``fail``-level finding carrying the error message.

    """
    return Finding(
        id=f"{target.name}/{viewport.label}/target-error",
        rule="VCS900",
        target=target.name,
        viewport=viewport.label,
        tag="",
        css_path="",
        query="",
        candidates=(),
        categories=(),
        origins=(),
        mechanisms=(),
        geometry={},
        computed_style_changes={},
        changed_pixels=0,
        causes=(),
        level="fail",
        decided_by=None,
        matched=(),
        message=f"{type(error).__name__}: {error}",
    )


def _copy_artifacts(
    *,
    engine_output: Path,
    artifacts: Path,
    stem: str,
) -> dict[str, str]:
    """Copy analyzer screenshots and its report into ARTIFACTS.

    Args:
        engine_output: Analyzer output directory to read from.
        artifacts: Artifact directory to copy into.
        stem: File-name prefix for copied artifacts.

    Returns:
        Artifact names to report-relative copied paths.

    """
    copied: dict[str, str] = {}
    for source_name, suffix in (
        ("a.png", "a"),
        ("b.png", "b"),
        ("diff.png", "diff"),
    ):
        source: Path = engine_output / source_name
        if source.is_file():
            destination: Path = artifacts / f"{stem}-{suffix}.png"
            _ = copy2(src=source, dst=destination)
            copied[suffix] = destination.relative_to(
                artifacts.parent,
            ).as_posix()
    report: Path = engine_output / "report.json"
    if report.is_file():
        destination = artifacts / f"{stem}-engine-report.json"
        _ = copy2(src=report, dst=destination)
        copied["engine_report"] = destination.relative_to(
            artifacts.parent,
        ).as_posix()
    markdown_report: Path = engine_output / "report.md"
    if markdown_report.is_file():
        copied["engine_markdown"] = markdown_report.relative_to(
            artifacts.parent,
        ).as_posix()
    return copied


def _diagnostics(
    *,
    pages: tuple[ServedPage, ...],
) -> tuple[dict[str, JsonValue], ...]:
    """Collect diagnostics from every served-page log.

    Args:
        pages: Served pages carrying optional log paths.

    Returns:
        Serialized server diagnostics across all logs.

    """
    logs: set[Path] = {page.log for page in pages if page.log is not None}
    return tuple(
        cast(typ="dict[str, JsonValue]", val=asdict(obj=diagnostic))
        for log in logs
        for diagnostic in parse_server_log(path=log)
    )


def run(*, request: VisualCauseRequest) -> VisualCauseResult:
    """Run every target and viewport, continuing after target failures.

    Args:
        request: Run request carrying targets and the output directory.

    Returns:
        Normalized tool result covering all targets.

    Raises:
        QuerySyntaxError: If a configured verdict query fails to
            compile.

    """
    artifacts: Path = request.output / "ARTIFACTS"
    artifacts.mkdir(parents=True, exist_ok=True)
    target_results: list[TargetResult] = []
    findings: list[Finding] = []
    query_summary: list[dict[str, JsonValue]] = []
    for target in request.targets:
        with LocalServices(
            artifacts=artifacts,
            timeout_ms=target.timeout_ms,
        ) as services:
            for viewport in target.viewports:
                try:
                    page_a: ServedPage = services.page(
                        url=target.url,
                        html=target.html,
                        landing=target.landing,
                        label=f"{target.name}-a",
                    )
                    page_b: ServedPage = (
                        services.page(
                            url=target.url_b,
                            html=target.html_b,
                            landing=target.landing_b,
                            label=f"{target.name}-b",
                        )
                        if target.url_b is not None
                        or target.html_b is not None
                        else page_a
                    )
                    stem: str = f"{target.name}-{viewport.label}"
                    engine_output: Path = artifacts / "engine" / stem
                    query_config: QueryConfig = QueryConfig(
                        url=page_b.url,
                        width=viewport.width,
                        height=viewport.height,
                        timeout_ms=target.timeout_ms,
                        css=_read_css(path=target.css_b),
                        native_styles=(
                            target.css_b is None
                            or target.mode == "overlay"
                            or target.native_styles_b
                        ),
                    )
                    with QuerySession(config=query_config) as validation:
                        for _, query in _queries(target=target):
                            if diagnostics := validation.lint(query=query):
                                msg: str = (
                                    f"Invalid level query {query!r}: "
                                    f"{diagnostics[0]}"
                                )
                                raise QuerySyntaxError(msg)
                    engine_results: AnalysisResults = analyze(
                        settings=Settings(
                            url=page_a.url,
                            url_b=page_b.url,
                            css_a=target.css_a,
                            css_b=target.css_b,
                            output=engine_output,
                            width=viewport.width,
                            height=viewport.height,
                            threshold=target.threshold,
                            max_candidates=target.max_candidates,
                            timeout_ms=target.timeout_ms,
                            use_native_styles_a=(
                                target.css_a is None or target.native_styles_a
                            ),
                            use_native_styles_b=(
                                target.css_b is None
                                or target.mode == "overlay"
                                or target.native_styles_b
                            ),
                            parallel_workers=target.parallel_workers,
                            screenshot_scale=target.screenshot_scale,
                        ),
                    )
                    with QuerySession(config=query_config) as session:
                        current: tuple[Finding, ...] = _findings(
                            target=target,
                            viewport=viewport,
                            results=engine_results,
                            session=session,
                        )
                    findings.extend(current)
                    counts: dict[str, int] = {
                        level: sum(item.level == level for item in current)
                        for level in ("accept", "warning", "fail")
                    }
                    target_results.append(
                        TargetResult(
                            name=target.name,
                            mode=target.mode,
                            viewport=viewport.label,
                            url_a=page_a.url,
                            url_b=page_b.url,
                            changed_pixels=engine_results.baseline,
                            changed_element_count=len(current),
                            counts=counts,
                            artifacts=_copy_artifacts(
                                engine_output=engine_output,
                                artifacts=artifacts,
                                stem=stem,
                            ),
                            server_diagnostics=_diagnostics(
                                pages=(page_a, page_b),
                            ),
                        ),
                    )
                    query_summary.extend(
                        {
                            "target": target.name,
                            "viewport": viewport.label,
                            "level": level,
                            "query": query,
                            "matched_findings": sum(
                                any(
                                    match.get("query") == query
                                    for match in item.matched
                                )
                                for item in current
                            ),
                        }
                        for level, query in _queries(target=target)
                    )
                except (
                    OSError,
                    PlaywrightError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as error:
                    findings.append(
                        _failure(
                            target=target,
                            viewport=viewport,
                            error=error,
                        ),
                    )
    failed: bool = any(
        item.rule == "VCS900"
        or (
            item.level == "fail"
            and next(
                (
                    target.fail_on
                    for target in request.targets
                    if target.name == item.target
                ),
                "findings",
            )
            == "findings"
        )
        for item in findings
    ) or any(
        target.fail_on == "pixels"
        and any(
            result.name == target.name and result.changed_pixels > 0
            for result in target_results
        )
        for target in request.targets
    )
    return VisualCauseResult(
        targets=tuple(target_results),
        findings=tuple(findings),
        queries=tuple(query_summary),
        failed=failed,
    )
