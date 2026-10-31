# Copyright (c) 2026
"""Render normalized reports from ``result.json`` through tool templates.

A migrated tool ships ``<tool>/templates/markdown/template.md`` (which
extends the common ``result_template.md``) and ``mapping.json`` (merged
over the common base mapping, tool keys winning). The stamp stage builds
the normalized model, renders ``result.md`` from it, and stores the
mapped view model in the web bundle data.
"""

from __future__ import annotations

from atexit import register
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files as resource_files
from json import JSONDecodeError, loads
from logging import Logger, getLogger
from pathlib import Path
from re import Pattern
from re import compile as compile_pattern
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final, Self, cast

from exactus.packages.markdown import MappingError
from exactus.tools.common.envelope import Envelope, RunFacts
from exactus.tools.common.json_types import JsonDict, JsonValue
from exactus.tools.common.report_time import report_times
from exactus.tools.reports.bundle import ReportBundle

if TYPE_CHECKING:
    from collections.abc import Mapping
    from importlib.resources.abc import Traversable

    from exactus.packages.markdown import MarkdownEngine


def _copy_templates(*, source: Traversable, target: Path) -> None:
    """Copy packaged template resources into an engine-readable directory.

    Args:
        source: Template resource tree.
        target: Temporary disk directory.

    """
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_templates(source=child, target=target / child.name)
    else:
        _ = target.write_bytes(data=source.read_bytes())


def _template_tools_root() -> Path:
    """Resolve template files for both a checkout and a packaged zipapp.

    Returns:
        Disk root containing common and tool Markdown template trees.

    """
    local: Path = Path(__file__).resolve().parent.parent
    if local.is_dir():
        return local
    temporary: TemporaryDirectory[str] = TemporaryDirectory(
        prefix="exactus-report-templates-",
    )
    _ = register(temporary.cleanup)
    root: Path = Path(temporary.name)
    for tool in resource_files("exactus.tools").iterdir():
        templates: Traversable = tool.joinpath("templates", "markdown")
        if templates.is_dir():
            _copy_templates(
                source=templates,
                target=root / tool.name / "templates" / "markdown",
            )
    return root


class Constants:
    """Template layout constants.

    Attributes:
        tools: Directory holding one folder per tool.
        common: Common Markdown template directory.
        relative: Markdown template directory inside a tool folder.
        template: Tool template file name.
        mapping: Mapping file name (tool and common base).
        logger: Logger of failures that leave the report usable.
        anchor_noise: Regex to normalize anchor text.

    """

    tools: Final[Path] = _template_tools_root()
    common: Final[Path] = tools / "common" / "templates" / "markdown"
    relative: Final[tuple[str, str]] = ("templates", "markdown")
    template: Final[str] = "template.md"
    mapping: Final[str] = "mapping.json"
    logger: Final[Logger] = getLogger(name=__name__)
    anchor_noise: Final[Pattern[str]] = compile_pattern(pattern=r"[^a-z0-9]+")


def _anchor_slug(*, text: str) -> str:
    """Slug one identifier into an anchor suffix.

    Args:
        text: Finding identifier or title fragment.

    Returns:
        Lowercase hyphenated slug, empty when nothing usable remains.

    """
    return Constants.anchor_noise.sub(repl="-", string=text.lower()).strip("-")


def _finding_anchor(
    *,
    finding: dict[str, JsonValue],
    index: int,
    seen: set[str],
) -> str:
    """Assign a unique ``finding-`` anchor id to one finding.

    Args:
        finding: Mapped finding, mutated in place.
        index: Position in the findings list, for fallback ids.
        seen: Anchors already assigned.

    Returns:
        The anchor id recorded on the finding.

    """
    base: str = (
        _anchor_slug(text=str(object=finding.get("id") or ""))
        or f"item-{index + 1}"
    )
    anchor: str = f"finding-{base}"
    suffix: int = 2
    while anchor in seen:
        anchor = f"finding-{base}-{suffix}"
        suffix += 1
    seen.add(anchor)
    finding["anchor"] = anchor
    return anchor


def _record_issue(
    *,
    groups: dict[str, dict[str, JsonValue]],
    order: list[str],
    finding: dict[str, JsonValue],
    anchor: str,
) -> None:
    """Fold one finding into its per-file resume group.

    Args:
        groups: Resume rows keyed by path.
        order: First-appearance order of the paths.
        finding: Mapped finding.
        anchor: Anchor id assigned to the finding.

    """
    path: str = str(object=finding.get("path") or "(general)")
    group: dict[str, JsonValue] | None = groups.get(path)
    if group is None:
        group = {"path": path, "count": 0, "severities": {}, "issues": []}
        groups[path] = group
        order.append(path)
    group["count"] = cast(typ="int", val=group["count"]) + 1
    severity: str = str(object=finding.get("severity") or "info")
    severities: JsonValue = group["severities"]
    if isinstance(severities, dict):
        severities[severity] = (
            cast(typ="int", val=severities.get(severity) or 0) + 1
        )
    issues: JsonValue = group["issues"]
    if isinstance(issues, list):
        issue: dict[str, JsonValue] = {
            "anchor": anchor,
            "id": finding.get("id"),
            "severity": severity,
            "rule": finding.get("rule"),
            "line": finding.get("line"),
        }
        issues.append(issue)


def _severity_text(*, severities: JsonValue) -> str:
    """Render ``1 error · 2 warning`` for one group's counts.

    Args:
        severities: Severity counts of one file group.

    Returns:
        Ordered severity tally, or an empty string.

    """
    if not isinstance(severities, dict):
        return ""
    levels: tuple[str, ...] = ("error", "warning", "info")
    ordered: list[str] = [
        *levels,
        *sorted(level for level in severities if level not in levels),
    ]
    return " · ".join(
        f"{severities[level]} {level}"
        for level in ordered
        if severities.get(level)
    )


def _enrich_findings(*, context: dict[str, JsonValue]) -> None:
    """Inject finding anchors and the per-file resume into the context.

    Every mapped finding gains an ``anchor`` id the report body emits
    as an HTML anchor, and ``file_summary`` groups findings per file so
    the template can render a linked resume without repeating the full
    explanations.

    Args:
        context: Mapped template context, mutated in place.

    """
    findings: JsonValue = context.get("findings")
    if not isinstance(findings, list):
        return
    seen: set[str] = set()
    groups: dict[str, dict[str, JsonValue]] = {}
    order: list[str] = []
    for index, finding in enumerate(iterable=findings):
        if not isinstance(finding, dict):
            continue
        anchor: str = _finding_anchor(finding=finding, index=index, seen=seen)
        _record_issue(
            groups=groups,
            order=order,
            finding=finding,
            anchor=anchor,
        )
    if not order:
        return
    summary: list[JsonValue] = []
    for path in sorted(order, key=lambda p: (p == "(general)", p)):
        group: dict[str, JsonValue] = groups[path]
        group["severity_text"] = _severity_text(severities=group["severities"])
        summary.append(group)
    context["file_summary"] = summary


@dataclass(frozen=True, slots=True)
class RenderedReport:
    """Markdown and the mapped view model it was rendered from.

    Attributes:
        markdown: Rendered ``result.md`` text.
        view: Mapped template context without the raw ``source``.

    """

    markdown: str
    view: dict[str, JsonValue]


class ReportTemplates:
    """Locate, merge and render the Markdown templates of a tool."""

    @classmethod
    def migrated(cls: type[Self], *, analyzer: str) -> bool:
        """Report whether a tool renders through a template.

        Args:
            analyzer: Tool identifier.

        Returns:
            ``True`` when the tool ships ``template.md``.

        """
        return (cls.tool_dir(analyzer=analyzer) / Constants.template).is_file()

    @classmethod
    def mapping(
        cls: type[Self],
        *,
        tool_dir: Path,
        common_dir: Path = Constants.common,
    ) -> dict[str, JsonValue]:
        """Merge a tool mapping over the common base mapping.

        Args:
            tool_dir: Tool Markdown template directory.
            common_dir: Common Markdown template directory.

        Returns:
            ``{**base, **tool}``; the tool mapping is optional.

        """
        merged: dict[str, JsonValue] = cls.load_mapping(
            path=common_dir / Constants.mapping,
        )
        tool_mapping: Path = tool_dir / Constants.mapping
        if tool_mapping.is_file():
            merged.update(cls.load_mapping(path=tool_mapping))
        return merged

    @classmethod
    def render(
        cls: type[Self],
        *,
        model: JsonValue,
        tool_dir: Path,
        common_dir: Path = Constants.common,
    ) -> RenderedReport:
        """Map ``model`` and render the tool template.

        Args:
            model: Normalized result document.
            tool_dir: Tool Markdown template directory.
            common_dir: Common Markdown template directory.

        Returns:
            The Markdown and the mapped view model.

        """
        engine_type: type[MarkdownEngine] = cast(
            typ="type[MarkdownEngine]",
            val=import_module(name="exactus.packages.markdown").MarkdownEngine,
        )
        engine: MarkdownEngine = engine_type(roots=(tool_dir, common_dir))
        context: dict[str, JsonValue] = engine.context(
            source=model,
            mapping=cls.mapping(tool_dir=tool_dir, common_dir=common_dir),
        )
        _enrich_findings(context=context)
        markdown: str = engine.render_context(
            template=tool_dir / Constants.template,
            context=context,
        )
        view: dict[str, JsonValue] = {
            key: value
            for key, value in context.items()
            if key not in {"source", "file_summary"}
        }
        return RenderedReport(markdown=markdown, view=view)

    @staticmethod
    def tool_dir(*, analyzer: str) -> Path:
        """Return a tool's Markdown template directory.

        Args:
            analyzer: Tool identifier (``kwargs-typehints`` style allowed).

        Returns:
            ``exactus/tools/<tool>/templates/markdown``.

        """
        return Constants.tools.joinpath(
            analyzer.replace("-", "_"),
            *Constants.relative,
        )

    @staticmethod
    def load_mapping(*, path: Path) -> dict[str, JsonValue]:
        """Read one mapping file.

        Args:
            path: Mapping JSON file.

        Returns:
            The mapping object.

        Raises:
            MappingError: The file is unreadable or not a JSON object.

        """
        try:
            loaded: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (OSError, JSONDecodeError) as exc:
            msg: str = f"Cannot load mapping {path}: {exc}"
            raise MappingError(msg) from exc
        if not isinstance(loaded, dict):
            msg = f"Mapping must be a JSON object: {path}"
            raise MappingError(msg)
        return loaded

    @staticmethod
    def columns(*, view: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        """Record the column order of every list-of-objects view block.

        The web data is written with sorted keys, which loses the order a
        mapping's ``$each`` gave each row; the web report reads this index
        to lay table columns out in mapping order.

        Args:
            view: Mapped view model.

        Returns:
            Block name to its row keys in first-seen order.

        """
        order: dict[str, JsonValue] = {}
        name: str
        block: JsonValue
        for name, block in view.items():
            if not isinstance(block, list):
                continue
            rows: list[dict[str, JsonValue]] = [
                row for row in block if isinstance(row, dict)
            ]
            if rows:
                keys: list[JsonValue] = list(
                    dict.fromkeys(key for row in rows for key in row),
                )
                order[name] = keys
        return order


class NormalizedStamp:
    """Add the envelope to a written report and re-render it."""

    @classmethod
    def apply(
        cls: type[Self],
        *,
        facts: RunFacts,
        required: frozenset[str],
    ) -> bool:
        """Stamp ``result.json``, ``result.md`` and the web data.

        Every legacy key of ``result.json`` is kept; the envelope blocks
        are added, ``result.md`` is replaced by the rendered template,
        and the web data gains the rendered Markdown, the view model, the
        column order of its table blocks and the mapping order of its
        keys (``view_order``; the data is written with sorted keys).

        Args:
            facts: Run facts filling the envelope.
            required: Blocks the payload must carry to be valid.

        Returns:
            ``False`` when ``result.json`` is absent or not an object.
            Once ``result.json`` and ``result.md`` hold the normalized
            report the result is ``True`` even if the web data cannot be
            rewritten, so the legacy stamps never overwrite it.

        """
        output: Path = facts.output
        payload: dict[str, JsonValue] | None = cls._read(
            path=output / "result.json",
        )
        if payload is None:
            return False
        payload.update(Envelope.build(facts=facts, payload=payload))
        payload.update(report_times(payload=payload))
        rendered: RenderedReport = ReportTemplates.render(
            model=payload,
            tool_dir=ReportTemplates.tool_dir(analyzer=facts.analyzer),
        )
        rendered = RenderedReport(
            markdown=ReportBundle.link_paths(
                markdown=rendered.markdown,
                base=output,
                root=Path(
                    str(object=payload.get("project_root") or facts.cwd),
                ),
            ),
            view=rendered.view,
        )
        payload["sections"] = ReportBundle.sections(markdown=rendered.markdown)
        ReportBundle.validate_payload(
            payload=payload,
            markdown=rendered.markdown,
            required_blocks=required,
        )
        _ = (output / "result.json").write_text(
            data=JsonDict(payload).tojson + "\n",
            encoding="utf-8",
        )
        _ = (output / "result.md").write_text(
            data=rendered.markdown,
            encoding="utf-8",
        )
        try:
            cls._web(
                web=output / "result_web",
                payload=payload,
                rendered=rendered,
            )
        except OSError:
            Constants.logger.exception(
                msg="Normalized web data could not be written",
            )
        return True

    @staticmethod
    def _read(*, path: Path) -> dict[str, JsonValue] | None:
        """Read a JSON object document.

        Args:
            path: JSON file.

        Returns:
            The object, or ``None`` when absent or not an object.

        """
        try:
            loaded: JsonValue = cast(
                typ="JsonValue",
                val=loads(s=path.read_text(encoding="utf-8")),
            )
        except (OSError, JSONDecodeError):
            return None
        return loaded if isinstance(loaded, dict) else None

    @staticmethod
    def _web(
        *,
        web: Path,
        payload: Mapping[str, JsonValue],
        rendered: RenderedReport,
    ) -> None:
        """Rewrite the web data from the stamped payload.

        Args:
            web: Web bundle directory.
            payload: Stamped ``result.json`` payload.
            rendered: Rendered Markdown and view model.

        """
        if not (web / "data.json").is_file():
            return
        data: JsonDict[JsonValue] = JsonDict(payload)
        data["markdown"] = rendered.markdown
        data["view"] = rendered.view
        data["view_columns"] = ReportTemplates.columns(view=rendered.view)
        data["view_order"] = cast(
            typ="list[JsonValue]",
            val=list(rendered.view),
        )
        ReportBundle.write_web_data(web=web, payload=data)
