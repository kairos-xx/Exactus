# Copyright (c) 2026
"""Write consistent Markdown, JSON, and offline web exactus reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from importlib.resources import files as resource_files
from os import environ
from os.path import relpath
from pathlib import Path
from re import MULTILINE, Match, Pattern, finditer
from re import compile as re_compile
from re import escape as re_escape
from re import search as re_search
from shutil import which
from subprocess import (
    CalledProcessError,
    CompletedProcess,
    TimeoutExpired,
    run,
)
from sys import version as python_version
from typing import TYPE_CHECKING, Final, Self
from urllib.parse import SplitResult, quote, unquote, urlsplit

from exactus.tools.common.cli import consume, linter_command
from exactus.tools.common.directory_docs import write_directory_docs
from exactus.tools.common.json_types import JsonDict, JsonObject, JsonValue
from exactus.tools.common.report_comparison import apply as apply_comparison
from exactus.tools.common.report_comparison import (
    markdown as comparison_markdown,
)
from exactus.tools.common.report_comparison import (
    previous_duration as previous_report_duration,
)
from exactus.tools.common.report_time import report_times

if TYPE_CHECKING:
    from collections.abc import Mapping


class Constants:
    """Store shared report rendering constants.

    Attributes:
        schema: Report JSON schema identifier.
        css_name: Stylesheet filename in the web bundle.
        code_span: Backticked path with optional ``:line[:column]`` or
            ``::node`` suffix.
        kit_css_name: Vendored design-system stylesheet in the web bundle.
        kit_template: Template path of the vendored design-system stylesheet.
        js_name: JavaScript filename in the web bundle.
        html_name: HTML entry-point filename in the web bundle.
        data_name: JSON data filename in the web bundle.
        data_js_name: JavaScript data filename in the web bundle.
        required_payload_keys: Required payload keys.
        object_blocks: Normalized blocks that must be JSON objects.
        list_blocks: Normalized blocks that must be JSON lists.
        envelope_blocks: Blocks the runner adds to every migrated report.
        normalized_blocks: Every block of a complete normalized report.
        finding_keys: Keys of one normalized finding.
        max_path_chars: Maximum candidate path length in web cells.
        irregular_whitespace: Regex pattern for irregular whitespace.

    """

    schema: Final[str] = "project-exactus-report/v1"
    max_path_chars: Final[int] = 4096
    css_name: Final[str] = "report.css"
    code_span: Final[Pattern[str]] = re_compile(
        pattern=r"(?<!\[)`(?P<path>[^`:\n]+?)"
        r"(?::(?P<line>\d+)(?::\d+)?|::(?P<node>[^`]+))?`",
    )
    kit_css_name: Final[str] = "cerulean.css"
    kit_template: Final[str] = "vendor/cerulean.css"
    js_name: Final[str] = "report.js"
    html_name: Final[str] = "index.html"
    data_name: Final[str] = "data.json"
    data_js_name: Final[str] = "data.js"
    required_payload_keys: Final[frozenset[str]] = frozenset(
        {
            "schema",
            "title",
            "analyzer",
            "generated_at",
            "fingerprint",
            "sections",
            "web",
        },
    )
    object_blocks: Final[frozenset[str]] = frozenset(
        {
            "tool",
            "run",
            "invocation",
            "environment",
            "gate",
            "summary",
            "scope",
            "extension",
        },
    )
    list_blocks: Final[frozenset[str]] = frozenset({"artifacts", "findings"})
    envelope_blocks: Final[frozenset[str]] = frozenset(
        {"tool", "run", "invocation", "environment", "gate", "artifacts"},
    )
    normalized_blocks: Final[frozenset[str]] = envelope_blocks | frozenset(
        {"summary", "scope", "findings", "extension"},
    )
    finding_keys: Final[frozenset[str]] = frozenset(
        {
            "id",
            "title",
            "severity",
            "rule",
            "path",
            "line",
            "message",
            "blocking",
        },
    )
    irregular_whitespace: Final[frozenset[str]] = frozenset(
        chr(point)
        for point in (
            0x0B,
            0x0C,
            0x85,
            0xA0,
            0x1680,
            0x180E,
            *range(0x2000, 0x200B),
            0x2028,
            0x2029,
            0x202F,
            0x205F,
            0x3000,
            0xFEFF,
        )
    )


# Seconds allowed for each fingerprint helper command.
FINGERPRINT_TIMEOUT: Final[float] = 15.0


def command_output(*, args: tuple[str, ...]) -> str:
    """Return a trimmed command's stdout, or an empty string on failure.

    Args:
        args: Command and arguments; the program must resolve on PATH.

    Returns:
        First line of standard output, or ``""`` when the command is
        unavailable or fails.

    """
    program: str | None = which(cmd=args[0])
    if program is None:
        return ""
    try:
        completed: CompletedProcess[str] = run(
            args=(program, *args[1:]),
            check=True,
            capture_output=True,
            text=True,
            timeout=FINGERPRINT_TIMEOUT,
        )
    except (OSError, CalledProcessError, TimeoutExpired):
        return ""
    return (
        completed.stdout.strip().splitlines()[0]
        if completed.stdout.strip()
        else ""
    )


def fingerprint() -> JsonObject:
    """Return the tree and toolchain identity of this exactus run.

    A stale report is otherwise indistinguishable from a current one, so
    every bundle records the commit it described, whether the working tree
    had uncommitted changes, and the analyzer versions that produced it.

    Returns:
        Commit, tree state and tool versions; missing values are ``""``.

    """
    status: str = command_output(args=("git", "status", "--porcelain"))
    root: Path = Path.cwd()
    return JsonDict(
        {
            "commit": command_output(args=("git", "rev-parse", "HEAD")),
            "tree": command_output(args=("git", "rev-parse", "HEAD^{tree}")),
            "dirty": bool(status),
            "python": python_version.split()[0],
            "ruff": command_output(
                args=(*linter_command(tool="ruff", root=root), "--version"),
            ),
            "basedpyright": command_output(
                args=(
                    *linter_command(tool="basedpyright", root=root),
                    "--version",
                ),
            ),
        },
    )


@dataclass(frozen=True, slots=True)
class ReportPaths:
    """Represent the three public report deliverables.

    Attributes:
        markdown: Markdown report file path.
        json: JSON report file path.
        web: Offline web bundle directory.

    """

    markdown: Path
    json: Path
    web: Path


class ReportBundle:
    """Render one analyzer result in identical Markdown/JSON/web formats."""

    @classmethod
    def sections(cls: type[Self], *, markdown: str) -> list[JsonValue]:
        """Extract a flat heading index preserving Markdown organization.

        Args:
            markdown: Markdown document to index.

        Returns:
            Heading entries with ``level`` and ``title`` keys.

        """
        sections: list[JsonValue] = list(
            map(
                cls._heading_entry,
                finditer(
                    pattern=r"^(#{1,6})\s+(.+?)\s*$",
                    string=markdown,
                    flags=MULTILINE,
                ),
            ),
        )
        return sections

    @classmethod
    def write_web_data(
        cls: type[Self],
        *,
        web: Path,
        payload: JsonObject,
    ) -> None:
        """Write the ``data.json`` and ``data.js`` payload files.

        Args:
            web: Web bundle directory receiving the data files.
            payload: Report data serialized into both documents.

        """
        payload = JsonDict(payload)
        payload["local_links"] = cls.local_links(
            value=payload,
            base=web.parent,
            root=Path(str(object=payload.get("project_root") or Path.cwd())),
        )
        _ = consume(
            value=web.joinpath(Constants.data_name).write_text(
                data=f"{JsonDict(payload).tojson}\n",
                encoding="utf-8",
            ),
        )
        _ = consume(
            value=web.joinpath(Constants.data_js_name).write_text(
                data=cls.web_data_js(payload=payload),
                encoding="utf-8",
            ),
        )

    @classmethod
    def local_links(
        cls: type[Self],
        *,
        value: JsonValue,
        base: Path,
        root: Path,
    ) -> dict[str, JsonValue]:
        """Index existing report file references for web-rendered cells.

        Args:
            value: Report payload or a nested value.
            base: Markdown report directory.
            root: Project root.

        Returns:
            File labels mapped to encoded report-relative destinations.

        """
        links: dict[str, JsonValue] = {}
        if isinstance(value, dict):
            for item in value.values():
                links.update(cls.local_links(value=item, base=base, root=root))
        elif isinstance(value, list):
            for item in value:
                links.update(cls.local_links(value=item, base=base, root=root))
        elif isinstance(value, str):
            candidates: list[str] = (
                [value] if len(value) < Constants.max_path_chars else []
            )
            candidates.extend(
                match.group("path")
                for match in Constants.code_span.finditer(string=value)
            )
            for candidate in candidates:
                href: str | None = cls._local_destination(
                    candidate=candidate,
                    base=base,
                    root=root,
                )
                if href is not None:
                    links[candidate] = href
        return links

    @classmethod
    def link_paths(
        cls: type[Self],
        *,
        markdown: str,
        base: Path,
        root: Path,
    ) -> str:
        """Turn backticked project paths into relative Markdown links.

        A code span such as `` `exactus/__main__.py:42` `` (an absolute
        path inside the project, or a path relative to the report itself
        such as ``ARTIFACTS/...``) that names an existing file or
        directory becomes a relative Markdown link such as
        `` [`exactus/__main__.py`](../../exactus/__main__.py) ``,
        so it opens from any checkout. Code blocks and spans that are
        already link text are left untouched.

        Args:
            markdown: Report Markdown.
            base: Directory the Markdown file is written to.
            root: Project root that relative paths are resolved against.

        Returns:
            Markdown with file references linked.

        """
        lines: list[str] = []
        fence: str = ""
        artifact_table: bool = False
        for line in markdown.split(sep="\n"):
            normalized_line: str = line
            marker: Match[str] | None = re_search(
                pattern=r"^\s*(`{3,}|~{3,})",
                string=line,
            )
            if marker is not None:
                artifact_table = False
                token: str = marker.group(1)
                if not fence:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = ""
                lines.append(line)
                continue
            if not fence:
                if not line.lstrip().startswith("|"):
                    artifact_table = False
                elif line.split(sep="|")[1].strip() == "Artifact":
                    artifact_table = True
                normalized_line = cls._normalize_links(
                    line=line,
                    base=base,
                    root=root,
                    artifact_table=artifact_table,
                )
            cells: list[str] = (
                normalized_line.split(sep="|")
                if artifact_table
                else [normalized_line]
            )
            lines.append(
                ("|" if artifact_table else "").join(
                    cell
                    if fence or (artifact_table and index == 1)
                    else Constants.code_span.sub(
                        repl=lambda match: cls._linked_span(
                            match=match,
                            base=base,
                            root=root,
                        ),
                        string=cell,
                    )
                    for index, cell in enumerate(iterable=cells)
                ),
            )
        return "\n".join(lines)

    @classmethod
    def relative_href(cls, *, href: str, base: Path, root: Path) -> str:
        """Return a URL-encoded local link relative to its report.

        Args:
            href: Existing Markdown link destination.
            base: Directory containing the report.
            root: Project root for project-relative references.

        Returns:
            Relative local destination, or the unchanged nonlocal URL.

        """
        literal: str | None = cls._literal_href(
            href=href,
            base=base,
            root=root,
        )
        if literal is not None:
            return literal
        try:
            parsed: SplitResult = urlsplit(url=href.strip("<>"))
        except ValueError:
            return href
        if (
            parsed.scheme not in {"", "file"}
            or parsed.netloc
            or not parsed.path
        ):
            return href
        candidate: Path = Path(unquote(string=parsed.path))
        target: Path = (
            candidate if candidate.is_absolute() else base / candidate
        )
        try:
            if not target.exists() and not candidate.is_absolute():
                target = root / candidate
            if not target.exists():
                return href
        except OSError:
            return href
        relative: str = Path(relpath(path=target, start=base)).as_posix()
        suffix: str = (f"?{parsed.query}" if parsed.query else "") + (
            f"#{parsed.fragment}" if parsed.fragment else ""
        )
        return quote(string=relative, safe="/.") + suffix

    @classmethod
    def validate_payload(
        cls: type[Self],
        *,
        payload: Mapping[str, JsonValue],
        markdown: str,
        required_blocks: frozenset[str] = frozenset(),
    ) -> None:
        """Validate the common cross-format report contract.

        Args:
            payload: JSON payload destined for disk and the web renderer.
            markdown: Canonical Markdown represented by the payload.
            required_blocks: Normalized blocks a migrated tool's payload
                must carry; empty for unmigrated tools.

        Raises:
            ValueError: If required report structure is missing or incoherent.

        """
        cls.validate_blocks(payload=payload, required=required_blocks)
        missing: frozenset[str] = Constants.required_payload_keys - frozenset(
            payload,
        )
        if missing:
            msg: str = f"report payload missing keys: {sorted(missing)}"
            raise ValueError(msg)
        if not markdown.startswith("# "):
            msg = "report Markdown must start with a level-one heading"
            raise ValueError(msg)
        sections: JsonValue | None = payload.get("sections")
        if not isinstance(sections, list) or not sections:
            msg = "report must expose a non-empty Markdown section index"
            raise ValueError(msg)
        web: JsonValue | None = payload.get("web")
        if not isinstance(web, dict) or set(web) != {
            "index",
            "css",
            "javascript",
            "data",
        }:
            msg = (
                "report web metadata must describe index, "
                "css, javascript, and data"
            )
            raise ValueError(msg)

    @classmethod
    def write(
        cls: type[Self],
        *,
        paths: ReportPaths,
        analyzer: str,
        title: str,
        markdown: str,
        data: Mapping[str, JsonValue] | None = None,
    ) -> JsonObject:
        """Write matching Markdown, JSON, and static-web reports.

        Args:
            paths: Report deliverable locations.
            analyzer: Analyzer name recorded in the payload.
            title: Human-readable report title.
            markdown: Markdown report body.
            data: Analyzer-specific JSON payload to merge in.

        Returns:
            The complete JSON payload written to disk.

        """
        output: Path = paths.markdown.parent
        paths = ReportPaths(
            markdown=output / "result.md",
            json=output / "result.json",
            web=output / "result_web",
        )
        paths.markdown.parent.mkdir(parents=True, exist_ok=True)
        paths.json.parent.mkdir(parents=True, exist_ok=True)
        paths.web.mkdir(parents=True, exist_ok=True)
        source_data: Mapping[str, JsonValue] = data or {}
        project_root: Path = Path(
            str(
                object=(
                    source_data.get("project_root")
                    or source_data.get("root")
                    or Path.cwd()
                ),
            ),
        ).resolve()
        normalized: str = cls.link_paths(
            markdown=cls._normalize_markdown(title=title, markdown=markdown),
            base=paths.markdown.parent,
            root=project_root,
        )
        metadata: JsonObject = JsonDict(
            {
                "schema": Constants.schema,
                "title": title,
                "analyzer": analyzer,
                "generated_at": datetime.now(tz=UTC).astimezone().isoformat(),
                "project_root": str(object=project_root),
                "project_href": Path(
                    relpath(path=project_root, start=paths.web.resolve()),
                ).as_posix(),
                "fingerprint": fingerprint(),
                "sections": cls.sections(markdown=normalized),
                "web": {
                    "index": Constants.html_name,
                    "css": Constants.css_name,
                    "javascript": Constants.js_name,
                    "data": Constants.data_name,
                },
            },
        )
        payload: JsonObject = JsonDict(data or {})
        payload.update(metadata)
        payload.update(report_times(payload=payload))
        lines: list[str] = [
            line
            for line in normalized.splitlines()
            if not line.startswith("**Run time:** ")
        ]
        lines[1:1] = [
            "",
            f"**Run time:** {payload['run_at_human'] or 'Not recorded'}",
        ]
        normalized = "\n".join(lines).rstrip() + "\n"
        payload["report_bundle"] = {
            "markdown": paths.markdown.name,
            "json": paths.json.name,
            "web": paths.web.name,
        }
        apply_comparison(payload=payload, path=paths.json)
        previous_duration: float | None = previous_report_duration(
            path=paths.json,
        )
        if previous_duration is not None:
            payload["previous_duration_seconds"] = round(
                number=previous_duration,
                ndigits=3,
            )
        comparison: str = comparison_markdown(
            comparison=payload.get("comparison"),
        )
        lines = normalized.splitlines()
        lines[3:3] = ["", comparison, ""]
        normalized = "\n".join(lines).rstrip() + "\n"
        payload["sections"] = cls.sections(markdown=normalized)
        cls.validate_payload(payload=payload, markdown=normalized)
        web_payload: JsonObject = JsonDict(payload)
        _ = consume(
            value=paths.markdown.write_text(data=normalized, encoding="utf-8"),
        )
        _ = consume(
            value=paths.json.write_text(
                data=f"{web_payload.tojson}\n",
                encoding="utf-8",
            ),
        )
        web_payload["markdown"] = normalized
        _ = consume(
            value=paths.web.joinpath(Constants.css_name).write_text(
                data=cls._template(name="report.css"),
                encoding="utf-8",
            ),
        )
        _ = consume(
            value=paths.web.joinpath(Constants.kit_css_name).write_text(
                data=cls._template(name=Constants.kit_template),
                encoding="utf-8",
            ),
        )
        _ = consume(
            value=paths.web.joinpath(Constants.js_name).write_text(
                data=cls._template(name="report.js"),
                encoding="utf-8",
            ),
        )
        cls.write_web_data(web=paths.web, payload=web_payload)
        _ = consume(
            value=paths.web.joinpath(Constants.html_name).write_text(
                data=cls._html(payload=web_payload),
                encoding="utf-8",
            ),
        )
        write_directory_docs(root=output)
        reports_root: str | None = environ.get("EXACTUS_REPORTS_ROOT")
        if output.parent.name == "EXACTUS_RESULTS" or (
            reports_root
            and output.parent.resolve() == Path(reports_root).resolve()
        ):
            write_directory_docs(root=output.parent)
        cls.validate_paths(paths=paths)
        return payload

    @staticmethod
    def web_data_js(*, payload: JsonObject) -> str:
        r"""Render the report payload as a script-includable JS document.

        ``file://`` pages cannot ``fetch`` sibling JSON, so the bundle
        ships the same payload twice: ``data.json`` for tools and
        ``data.js`` for ``index.html`` to load through a plain
        ``<script src>`` tag. Payload strings may legitimately carry
        ``${...}`` sequences (serialized source excerpts), so the
        serialized document is emitted inside a template literal fed
        to ``JSON.parse``: each ``${`` is backslash-escaped, cooking
        back to the exact payload text while
        ``no-template-curly-in-string`` — which inspects only regular
        string literals — never fires. Payload text can also carry
        irregular whitespace (``no-irregular-whitespace`` does inspect
        template literals), so every such character is emitted as a
        ``\\uXXXX`` escape that ``JSON.parse`` cooks back to the exact
        character.

        Args:
            payload: Report data exposed as ``window.__REPORT_DATA__``.

        Returns:
            JavaScript document assigning the payload global.

        """
        escaped: str = (
            JsonDict(payload)
            .tojson.replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
        )
        for char in Constants.irregular_whitespace:
            escaped = escaped.replace(char, f"\\\\u{ord(char):04x}")
        return f"window.__REPORT_DATA__ = JSON.parse(`{escaped}`);\n"

    @staticmethod
    def validate_blocks(
        *,
        payload: Mapping[str, JsonValue],
        required: frozenset[str],
    ) -> None:
        """Validate the normalized blocks of a migrated report.

        Args:
            payload: JSON payload destined for disk and the web renderer.
            required: Normalized blocks the payload must carry.

        Raises:
            ValueError: If a required block is missing, a present block
                has the wrong JSON type, or a finding lacks a key.

        """
        missing: list[str] = sorted(required - frozenset(payload))
        if missing:
            msg: str = f"report payload missing blocks: {missing}"
            raise ValueError(msg)
        name: str
        for name in sorted(required):
            block: JsonValue | None = payload.get(name)
            listed: bool = name in Constants.list_blocks
            if listed != isinstance(block, list) or (
                not listed and not isinstance(block, dict)
            ):
                kind: str = "list" if listed else "object"
                msg = f"report block {name!r} must be a JSON {kind}"
                raise ValueError(msg)
        findings: JsonValue | None = payload.get("findings")
        if "findings" not in required or not isinstance(findings, list):
            return
        item: JsonValue
        for item in findings:
            absent: frozenset[str] = Constants.finding_keys - (
                frozenset(item) if isinstance(item, dict) else frozenset()
            )
            if absent:
                msg = f"report finding missing keys: {sorted(absent)}"
                raise ValueError(msg)

    @staticmethod
    def validate_paths(*, paths: ReportPaths) -> None:
        """Validate that all three report representations were written.

        Args:
            paths: Report deliverable locations to validate.

        Raises:
            ValueError: If any required report artifact is absent or empty.

        """
        required: tuple[Path, ...] = (
            paths.markdown,
            paths.json,
            paths.web / Constants.html_name,
            paths.web / Constants.css_name,
            paths.web / Constants.js_name,
            paths.web / Constants.data_name,
            paths.web / Constants.data_js_name,
        )
        if missing := tuple(
            path
            for path in required
            if not path.is_file() or path.stat().st_size == 0
        ):
            msg: str = "incomplete report bundle: " + ", ".join(
                str(object=path) for path in missing
            )
            raise ValueError(msg)

    @classmethod
    def _local_destination(
        cls: type[Self],
        *,
        candidate: str,
        base: Path,
        root: Path,
    ) -> str | None:
        """Resolve one existing local file reference for a web cell.

        Args:
            candidate: Displayed path or prose value.
            base: Markdown report directory.
            root: Project root.

        Returns:
            Relative destination when the file exists, otherwise None.

        """
        if "\n" in candidate or (
            "/" not in candidate and not Path(candidate).suffix
        ):
            return None
        try:
            href: str = cls.relative_href(href=candidate, base=base, root=root)
            parsed: SplitResult = urlsplit(url=href)
            exists: bool = (base / unquote(string=parsed.path)).exists()
        except (OSError, ValueError):
            return None
        return (
            href
            if exists
            and not parsed.scheme
            and not parsed.netloc
            and not href.startswith("/")
            else None
        )

    @classmethod
    def _html(cls: type[Self], *, payload: Mapping[str, JsonValue]) -> str:
        """Render the shared HTML template for the report bundle.

        Args:
            payload: Report data supplying the document title.

        Returns:
            Complete HTML document text.

        """
        title: str = escape(
            s=str(object=payload.get("title", "Exactus Report")),
        )
        return (
            cls._template(name="report.html")
            .replace("__REPORT_TITLE__", title)
            .replace("__REPORT_KIT_CSS__", Constants.kit_css_name)
            .replace("__REPORT_CSS__", Constants.css_name)
            .replace("__REPORT_DATA_JS__", Constants.data_js_name)
            .replace("__REPORT_JS__", Constants.js_name)
        )

    @classmethod
    def _normalize_links(
        cls: type[Self],
        *,
        line: str,
        base: Path,
        root: Path,
        artifact_table: bool = False,
    ) -> str:
        """Rebase inline and reference-style Markdown destinations.

        Args:
            line: Prose line outside a fenced code block.
            base: Report directory.
            root: Project root.
            artifact_table: Keep artifact labels plain in the first column.

        Returns:
            Line with portable destinations for existing local files.

        """

        def replace(match: Match[str]) -> str:
            """Rewrite one destination while preserving its label.

            Args:
                match: Inline or reference link match.

            Returns:
                Link with a report-relative destination.

            """
            return (
                match.group("prefix")
                + cls.relative_href(
                    href=match.group("href"),
                    base=base,
                    root=root,
                )
                + match.group("suffix")
            )

        linked: str = re_compile(
            pattern=(
                "(?P<prefix>!?\\[[^\\]\\n]*\\]\\()(?P<href><[^>]+>|[^)]+)(?P<s"
                "uffix>\\))"
            ),
        ).sub(repl=replace, string=line)
        if linked.lstrip().startswith("|"):
            cells: list[str] = linked.split(sep="|")
            for index, cell in enumerate(iterable=cells):
                if artifact_table and index == 1:
                    continue
                label: str = cell.strip()
                if "`" in label or "[" in label:
                    continue
                href: str | None = cls._local_destination(
                    candidate=label,
                    base=base,
                    root=root,
                )
                if href is not None:
                    cells[index] = cell.replace(label, f"[{label}]({href})")
            linked = "|".join(cells)
        return re_compile(
            pattern=(
                "^(?P<prefix>\\s*\\[[^\\]]+\\]:\\s*)(?P<href><[^>]+>|\\S+)(?P<"
                "suffix>.*)$"
            ),
        ).sub(repl=replace, string=linked)

    @classmethod
    def _linked_span(
        cls: type[Self],
        *,
        match: Match[str],
        base: Path,
        root: Path,
    ) -> str:
        """Return one code span as a link when it names a project path.

        Args:
            match: Code-span match with ``path``/``line``
                groups.
            base: Directory the Markdown file is written to.
            root: Project root.

        Returns:
            The linked span, or the original text.

        """
        raw: str = match.group("path")
        line: str | None = match.group("line")
        node: str | None = match.group("node")
        candidate: Path = Path(raw)
        if candidate.is_absolute() and candidate.is_relative_to(root):
            candidate = candidate.relative_to(root)
        target: Path = root / candidate
        try:
            if not candidate.is_absolute() and (base / candidate).is_file():
                target = base / candidate
            exists: bool = target.exists()
        except OSError:
            return match.group(0)
        if not raw.strip() or ("/" not in raw and not candidate.suffix):
            return match.group(0)
        if not exists:
            return match.group(0)
        anchor_line: str | None = line
        if anchor_line is None and node is not None:
            anchor_line = cls._definition_line(node=node, target=target)
        suffix: str = f":{line}" if line else f"::{node}" if node else ""
        text: str = candidate.as_posix() + suffix
        href: str = Path(relpath(path=target, start=base)).as_posix()
        anchor: str = f"#L{anchor_line}" if anchor_line else ""
        return f"[`{text}`]({quote(string=href, safe='/.')}{anchor})"

    @staticmethod
    def _template(name: str) -> str:
        """Return one bundled report template's text content.

        Templates are resolved through ``importlib.resources`` so the
        report bundle keeps working when the package executes from a
        pyz archive, where ``Path(__file__)`` does not address real
        files.

        Args:
            name: Template filename inside ``templates/html/`` of the
                ``exactus.tools.common`` package.

        Returns:
            Template file contents.

        """
        return (
            resource_files("exactus.tools.common")
            .joinpath("templates", "html", *name.split(sep="/"))
            .read_text(encoding="utf-8")
        )

    @staticmethod
    def _heading_entry(match: Match[str]) -> JsonValue:
        """Return the index entry for one Markdown heading match.

        Args:
            match: Heading pattern match.

        Returns:
            Heading entry with ``level`` and ``title`` keys.

        """
        return {"level": len(match.group(1)), "title": match.group(2).strip()}

    @staticmethod
    def _literal_href(*, href: str, base: Path, root: Path) -> str | None:
        """Resolve literal filenames before interpreting URL punctuation.

        Args:
            href: Unencoded local path, possibly containing hash characters.
            base: Report directory.
            root: Project root.

        Returns:
            Encoded relative path for an existing literal destination.

        """
        candidate: Path = Path(href.strip("<>"))
        try:
            for target in (base / candidate, root / candidate):
                if target.exists():
                    return quote(
                        string=Path(
                            relpath(path=target, start=base),
                        ).as_posix(),
                        safe="/.",
                    )
        except (OSError, ValueError):
            return None
        return None

    @staticmethod
    def _definition_line(*, node: str, target: Path) -> str | None:
        """Locate a pytest node's ``def`` line inside its file.

        Args:
            node: Pytest node suffix such as ``test_x`` or
                ``TestClass::test_x`` (parametrization allowed).
            target: Resolved file the node belongs to.

        Returns:
            One-based line number of the definition, or ``None``.

        """
        if target.suffix != ".py" or not target.is_file():
            return None
        name: str = node.rsplit(sep="::", maxsplit=1)[-1].split(
            sep="[",
            maxsplit=1,
        )[0]
        if not name:
            return None
        try:
            text: str = target.read_text(encoding="utf-8")
        except OSError:
            return None
        definition: Match[str] | None = re_search(
            pattern=(
                rf"^\s*(?P<keyword>(?:async\s+)?def)"
                rf"\s+{re_escape(pattern=name)}\b"
            ),
            string=text,
            flags=MULTILINE,
        )
        if definition is None:
            return None
        return str(object=text.count("\n", 0, definition.start("keyword")) + 1)

    @staticmethod
    def _normalize_markdown(*, title: str, markdown: str) -> str:
        """Return a canonical Markdown document with one report title.

        Args:
            title: Human-readable report title.
            markdown: Analyzer-provided Markdown body.

        Returns:
            Normalized Markdown beginning with a level-one title.

        """
        normalized: str = markdown.strip()
        lines: list[str] = normalized.splitlines() if normalized else []
        if not lines or not lines[0].startswith("# "):
            lines = [f"# {title}", "", *lines]
        return "\n".join(lines).rstrip() + "\n"
