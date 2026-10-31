# Copyright (c) 2026
"""Report-bundle validation helpers and fingerprint command plumbing."""

from __future__ import annotations

from json import loads
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    private_call,
)
from exactus.tools.common.report_comparison import clear
from exactus.tools.reports.bundle import (
    Constants,
    ReportBundle,
    ReportPaths,
    command_output,
    fingerprint,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonObject, JsonValue


def _payload(**changes: JsonValue) -> dict[str, JsonValue]:
    """Return a minimally valid report payload with overrides applied.

    Args:
        changes: Payload keys to add or replace.

    Returns:
        Payload satisfying ``Constants.required_payload_keys``.

    """
    payload: dict[str, JsonValue] = {
        "schema": Constants.schema,
        "title": "report",
        "analyzer": "test",
        "generated_at": "now",
        "fingerprint": {},
        "sections": [{"level": 1, "title": "report"}],
        "web": {"index": "i", "css": "c", "javascript": "j", "data": "d"},
    }
    payload.update(changes)
    return payload


def test_command_output_missing_program() -> None:
    """An unresolvable program yields an empty fingerprint value."""
    expect_equal(
        actual=command_output(args=("definitely-not-a-real-program-xq",)),
        expected="",
    )


def test_validate_payload_missing_keys() -> None:
    """Payloads lacking required keys raise ``ValueError``."""
    with pytest.raises(expected_exception=ValueError, match="missing keys"):
        ReportBundle.validate_payload(payload={}, markdown="# report\n")


def test_validate_payload_markdown_heading() -> None:
    """Markdown without a level-one heading raises ``ValueError``."""
    with pytest.raises(
        expected_exception=ValueError,
        match="level-one heading",
    ):
        ReportBundle.validate_payload(
            payload=_payload(),
            markdown="body without heading\n",
        )


def test_validate_payload_empty_sections() -> None:
    """An empty section index raises ``ValueError``."""
    with pytest.raises(expected_exception=ValueError, match="section index"):
        ReportBundle.validate_payload(
            payload=_payload(sections=[]),
            markdown="# report\n",
        )


def test_validate_payload_web_keys() -> None:
    """Web metadata missing a representation raises ``ValueError``."""
    with pytest.raises(expected_exception=ValueError, match="web metadata"):
        ReportBundle.validate_payload(
            payload=_payload(web={"index": "i", "css": "c"}),
            markdown="# report\n",
        )


def test_validate_paths_missing_artifacts(tmp_path: Path) -> None:
    """Absent deliverables raise ``ValueError``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    paths: ReportPaths = ReportPaths(
        markdown=tmp_path / "result.md",
        json=tmp_path / "result.json",
        web=tmp_path / "web",
    )
    with pytest.raises(expected_exception=ValueError, match=r"missing|empty"):
        ReportBundle.validate_paths(paths=paths)


def test_write_emits_web_data_files(tmp_path: Path) -> None:
    """``write`` emits ``data.json``/``data.js`` instead of embedding JSON.

    Args:
        tmp_path: Per-test temporary directory.

    """
    ReportBundle.write(
        paths=ReportPaths(
            markdown=tmp_path / "result.md",
            json=tmp_path / "result.json",
            web=tmp_path / "result_web",
        ),
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n\nBody\n",
        data={"findings": []},
    )
    web: Path = tmp_path / "result_web"
    expect_true(condition=(tmp_path / "README.md").is_file())
    expect_in(
        member="result_web/README.md",
        container=(tmp_path / "README.md").read_text(),
    )
    expect_in(member="index.html", container=(web / "README.md").read_text())
    html: str = (web / "index.html").read_text(encoding="utf-8")
    expect_not_in(member="report-data", container=html)
    expect_in(member='src="data.js"', container=html)
    data: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=(web / "data.json").read_text(encoding="utf-8")),
    )
    expect_in(member="markdown", container=data)
    script: str = (web / "data.js").read_text(encoding="utf-8")
    expect_true(condition=script.startswith("window.__REPORT_DATA__ = "))
    argument: str = (
        script.removeprefix("window.__REPORT_DATA__ = ")
        .rstrip()
        .removesuffix(";")
        .removeprefix("JSON.parse(`")
        .removesuffix("`)")
    )
    document: str = (
        argument.replace("\\${", "${")
        .replace("\\`", "`")
        .replace("\\\\", "\\")
    )
    payload: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=document),
    )
    expect_equal(actual=payload.get("analyzer"), expected="demo")


def test_web_data_js_escapes_template_sequences() -> None:
    """``${...}`` payload text survives inside a lint-clean document."""
    script: str = ReportBundle.web_data_js(
        payload=cast(
            typ="JsonObject",
            val={"excerpt": "const tag = `${name}`;"},
        ),
    )
    expect_equal(actual=script.count("${"), expected=script.count("\\${"))
    expect_in(member="\\${name}", container=script)
    argument: str = (
        script.removeprefix("window.__REPORT_DATA__ = JSON.parse(`")
        .removesuffix("`);\n")
        .replace("\\${", "${")
        .replace("\\`", "`")
        .replace("\\\\", "\\")
    )
    expect_equal(
        actual=cast(typ="dict[str, JsonValue]", val=loads(s=argument)),
        expected={"excerpt": "const tag = `${name}`;"},
    )


def test_write_compares_findings_with_previous_report(tmp_path: Path) -> None:
    """A repeated bundle records added, resolved and unchanged findings.

    Args:
        tmp_path: Per-test temporary directory.

    """
    paths: ReportPaths = ReportPaths(
        markdown=tmp_path / "result.md",
        json=tmp_path / "result.json",
        web=tmp_path / "result_web",
    )

    def finding(*, rule: str, path: str) -> dict[str, JsonValue]:
        """Build one normalized finding.

        Args:
            rule: Stable rule identifier.
            path: Finding path.

        Returns:
            Normalized finding object.

        """
        return {
            "id": rule,
            "title": f"Finding {rule}",
            "severity": "error",
            "rule": rule,
            "path": path,
            "line": 1,
            "message": f"Message {rule}",
            "blocking": True,
        }

    _ = ReportBundle.write(
        paths=paths,
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n",
        data={
            "findings": [
                finding(rule="A", path="a.py"),
                finding(rule="B", path="b.py"),
            ],
        },
    )
    payload: JsonObject = ReportBundle.write(
        paths=paths,
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n",
        data={
            "findings": [
                finding(rule="B", path="b.py"),
                finding(rule="C", path="c.py"),
            ],
        },
    )
    comparison: JsonValue = payload.get("comparison")
    expect_true(condition=isinstance(comparison, dict))
    if not isinstance(comparison, dict):
        clear()
        return
    expect_equal(actual=comparison.get("added_count"), expected=1)
    expect_equal(actual=comparison.get("resolved_count"), expected=1)
    expect_equal(actual=comparison.get("unchanged_count"), expected=1)
    findings: JsonValue = payload.get("findings")
    expect_true(condition=isinstance(findings, list))
    if not isinstance(findings, list):
        clear()
        return
    changes: list[str | None] = [
        cast(
            typ="str | None",
            val=cast(typ="dict[str, JsonValue]", val=item).get("change"),
        )
        for item in findings
        if isinstance(item, dict)
    ]
    expect_in(member="added", container=changes)
    clear()


def test_large_markdown_stays_in_one_file(tmp_path: Path) -> None:
    """Retain all report text even above the former pagination threshold.

    Args:
        tmp_path: Isolated report directory.

    """
    clear()
    paths: ReportPaths = ReportPaths(
        markdown=tmp_path / "result.md",
        json=tmp_path / "result.json",
        web=tmp_path / "result_web",
    )
    body: str = "Coverage evidence é\n" * 22000
    _ = ReportBundle.write(
        paths=paths,
        analyzer="demo",
        title="Demo",
        markdown=f"# Demo\n\n{body}Final evidence marker\n",
    )
    markdown: str = paths.markdown.read_text(encoding="utf-8")
    expect_in(member=body, container=markdown)
    expect_in(member="Final evidence marker", container=markdown)
    expect_true(
        condition=not (tmp_path / "ARTIFACTS" / "markdown-pages").exists(),
    )
    web: JsonValue = loads(
        s=(paths.web / "data.json").read_text(encoding="utf-8"),
    )
    if isinstance(web, dict):
        expect_equal(actual=markdown, expected=web["markdown"])
    clear()


def test_normalize_markdown_adds_title() -> None:
    """Bodies without a heading gain the analyzer's report title."""
    normalized: object = private_call(
        owner=ReportBundle,
        name="_normalize_markdown",
        title="Lint Report",
        markdown="findings follow\n",
    )
    expect_true(
        condition=isinstance(normalized, str)
        and normalized.startswith("# Lint Report\n"),
    )


def test_command_output_failure_paths() -> None:
    """Failing or silent programs yield an empty fingerprint value."""
    expect_equal(
        actual=command_output(args=("git", "--not-a-real-git-flag")),
        expected="",
    )
    expect_equal(actual=command_output(args=("true",)), expected="")


def test_fingerprint_reports_environment() -> None:
    """The fingerprint carries commit, tree, and toolchain identity."""
    report: JsonObject = fingerprint()
    for key in ("commit", "tree", "dirty", "python", "ruff"):
        expect_in(member=key, container=report)


def test_validate_blocks_missing_block() -> None:
    """Absent normalized blocks raise ``ValueError``."""
    with pytest.raises(expected_exception=ValueError, match="missing blocks"):
        ReportBundle.validate_blocks(payload={}, required=frozenset({"tool"}))


def test_validate_blocks_wrong_types() -> None:
    """Blocks typed against the contract raise ``ValueError``."""
    with pytest.raises(
        expected_exception=ValueError,
        match="must be a JSON list",
    ):
        ReportBundle.validate_blocks(
            payload={"findings": {}},
            required=frozenset({"findings"}),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="must be a JSON object",
    ):
        ReportBundle.validate_blocks(
            payload={"tool": []},
            required=frozenset({"tool"}),
        )


def test_validate_blocks_finding_keys() -> None:
    """Findings lacking contract keys raise ``ValueError``."""
    complete: dict[str, JsonValue] = {}
    for key in Constants.finding_keys:
        complete[key] = None
    ReportBundle.validate_blocks(
        payload={"findings": [complete]},
        required=frozenset({"findings"}),
    )
    ReportBundle.validate_blocks(
        payload={"tool": {}},
        required=frozenset({"tool"}),
    )
    with pytest.raises(
        expected_exception=ValueError,
        match="finding missing keys",
    ):
        ReportBundle.validate_blocks(
            payload={"findings": [{"id": "x"}]},
            required=frozenset({"findings"}),
        )
    with pytest.raises(
        expected_exception=ValueError,
        match="finding missing keys",
    ):
        ReportBundle.validate_blocks(
            payload={"findings": ["not-an-object"]},
            required=frozenset({"findings"}),
        )


def test_link_paths_links_existing_files(tmp_path: Path) -> None:
    """Backticked project paths become relative Markdown links.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "pkg" / "mod.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(
        data="def test_target() -> None:\n    pass\n",
        encoding="utf-8",
    )
    base: Path = tmp_path / "reports"
    base.mkdir()
    sibling: Path = base / "local.txt"
    _ = sibling.write_text(data="x", encoding="utf-8")
    markdown: str = "\n".join(
        [
            "see `pkg/mod.py:1` here",
            "inside `local.txt` report",
            f"abs `{source}`",
            "node `pkg/mod.py::test_target`",
            "```",
            "fenced `pkg/mod.py:9`",
            "```",
        ],
    )
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=base,
        root=tmp_path,
    )
    expect_in(member="[`pkg/mod.py:1`](../pkg/mod.py#L1)", container=linked)
    expect_in(member="[`local.txt`](local.txt)", container=linked)
    expect_in(member="[`pkg/mod.py`](../pkg/mod.py)", container=linked)
    expect_in(
        member="[`pkg/mod.py::test_target`](../pkg/mod.py#L1)",
        container=linked,
    )
    expect_in(member="fenced `pkg/mod.py:9`", container=linked)


def test_table_dunder_file_is_one_literal_link(tmp_path: Path) -> None:
    """A package initializer stays one link with a literal code label.

    Args:
        tmp_path: Disposable project and report directory.

    """
    source: Path = tmp_path / "pkg" / "__init__.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(data="", encoding="utf-8")
    base: Path = tmp_path / "reports"
    base.mkdir()
    expect_equal(
        actual=ReportBundle.link_paths(
            markdown="| `pkg/__init__.py` |",
            base=base,
            root=tmp_path,
        ),
        expected="| [`pkg/__init__.py`](../pkg/__init__.py) |",
    )


def test_artifact_names_stay_plain_and_paths_are_linked(
    tmp_path: Path,
) -> None:
    """Link artifact destinations without linking duplicate name cells.

    Args:
        tmp_path: Disposable project and artifact storage.

    """
    _ = (tmp_path / "README.md").write_text(data="Project", encoding="utf-8")
    artifacts: Path = tmp_path / "reports" / "ARTIFACTS"
    artifacts.mkdir(parents=True)
    for name in ("README.md", "__init__.py"):
        _ = (artifacts / name).write_text(data="", encoding="utf-8")
    markdown: str = dedent(
        text=(
            "    | Artifact | Path | Bytes |\n    | --- | --- | --- |\n    | R"
            "EADME.md | ARTIFACTS/README.md | 0 |\n    | `__init__.py` | `ARTI"
            "FACTS/__init__.py` | 0 |\n    \n    | Target |\n    | --- |\n    "
            "| README.md |"
        ),
    )
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=artifacts.parent,
        root=tmp_path,
    )
    expect_in(
        member="| README.md | [ARTIFACTS/README.md](ARTIFACTS/README.md) |",
        container=linked,
    )
    expect_in(
        member=(
            "| `__init__.py` | "
            "[`ARTIFACTS/__init__.py`](ARTIFACTS/__init__.py) |"
        ),
        container=linked,
    )
    expect_in(member="| [README.md](../README.md) |", container=linked)


def test_link_paths_leaves_non_paths(tmp_path: Path) -> None:
    """Spans that do not name existing files stay untouched.

    Args:
        tmp_path: Per-test temporary directory.

    """
    markdown: str = "\n".join(
        [
            "bare `word`",
            "gone `pkg/absent.py`",
            "up `../outside.py`",
            f"out `{tmp_path.parent / 'other.py'}`",
            "empty `pkg/mod.py::[x]`",
        ],
    )
    package: Path = tmp_path / "pkg"
    package.mkdir()
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=tmp_path,
        root=tmp_path,
    )
    expect_in(member="bare `word`", container=linked)
    expect_in(member="gone `pkg/absent.py`", container=linked)
    expect_in(member="up `../outside.py`", container=linked)
    expect_in(member="out `", container=linked)
    expect_in(member="empty `pkg/mod.py::[x]`", container=linked)


def test_link_paths_leaves_oversized_paths(tmp_path: Path) -> None:
    """Oversized backticked paths stay untouched instead of aborting reports.

    Args:
        tmp_path: Per-test temporary directory.

    """
    (tmp_path / "tests").mkdir()
    raw: str = f"exactus/tests/test_case[{'x' * 300}]"
    markdown: str = f"failed `{raw}`"
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=tmp_path,
        root=tmp_path,
    )
    expect_equal(actual=linked, expected=markdown)


def test_portable_links_cover_artifacts_and_existing_links(
    tmp_path: Path,
) -> None:
    """Encode local links and preserve fenced examples and external URLs.

    Args:
        tmp_path: Per-test temporary directory.

    """
    base: Path = tmp_path / "reports"
    base.mkdir()
    source: Path = tmp_path / "a # (é).md"
    _ = source.write_text(data="document", encoding="utf-8")
    artifact: Path = base / "ARTIFACTS" / "shot 1.png"
    artifact.parent.mkdir()
    _ = artifact.write_bytes(data=b"image")
    markdown: str = "\n".join(
        [
            f"[source](<{source.as_uri()}>)",
            f"path `{source}`",
            "| Artifact | ARTIFACTS/shot 1.png |",
            f'[ref]: <{source.as_uri()}> "Document"',
            "[web](https://example.com/docs)",
            "~~~python",
            f"[source]({source.as_uri()})",
            f"`{source}`",
            "~~~",
        ],
    )
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=base,
        root=tmp_path,
    )
    href: str = "../a%20%23%20%28%C3%A9%29.md"
    expect_in(member=f"[source]({href})", container=linked)
    expect_in(member=f"[`a # (é).md`]({href})", container=linked)
    expect_in(
        member="[ARTIFACTS/shot 1.png](ARTIFACTS/shot%201.png)",
        container=linked,
    )
    expect_in(member=f'[ref]: {href} "Document"', container=linked)
    expect_in(member="[web](https://example.com/docs)", container=linked)
    expect_in(
        member=f"~~~python\n[source]({source.as_uri()})",
        container=linked,
    )
    expect_equal(
        actual=ReportBundle.link_paths(
            markdown=linked,
            base=base,
            root=tmp_path,
        ),
        expected=linked,
    )


def test_web_link_index_uses_report_base(tmp_path: Path) -> None:
    """Give nested artifact cells relative links without changing raw paths.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "source # (é).py"
    _ = source.write_text(data="pass", encoding="utf-8")
    base: Path = tmp_path / "reports"
    base.mkdir()
    links: dict[str, JsonValue] = ReportBundle.local_links(
        value={
            "artifacts": [{"path": str(object=source)}],
            "note": "[invalid",
        },
        base=base,
        root=tmp_path,
    )
    expect_equal(
        actual=links[str(object=source)],
        expected="../source%20%23%20%28%C3%A9%29.py",
    )
    expect_equal(
        actual=ReportBundle.relative_href(
            href="https://[invalid",
            base=base,
            root=tmp_path,
        ),
        expected="https://[invalid",
    )


def test_link_paths_node_fallbacks(tmp_path: Path) -> None:
    """Nodes without resolvable definitions link without anchors.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: Path = tmp_path / "pkg" / "mod.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(data="x = 1\n", encoding="utf-8")
    document: Path = tmp_path / "notes.md"
    _ = document.write_text(data="# notes\n", encoding="utf-8")
    pseudo: Path = tmp_path / "pkg" / "fake.py"
    pseudo.mkdir()
    markdown: str = dedent(
        text=(
            "    miss `pkg/mod.py::absent`\n    doc `notes.md::section`\n    d"
            "ir `pkg/fake.py::any`"
        ),
    )
    linked: str = ReportBundle.link_paths(
        markdown=markdown,
        base=tmp_path,
        root=tmp_path,
    )
    expect_in(member="[`pkg/mod.py::absent`](pkg/mod.py)", container=linked)
    expect_in(member="[`notes.md::section`](notes.md)", container=linked)
    expect_in(member="[`pkg/fake.py::any`](pkg/fake.py)", container=linked)


def test_normalize_markdown_variants() -> None:
    """Empty and headed Markdown normalize to a single document."""
    empty: object = private_call(
        owner=ReportBundle,
        name="_normalize_markdown",
        title="T",
        markdown="",
    )
    expect_equal(actual=empty, expected="# T\n")
    headed: object = private_call(
        owner=ReportBundle,
        name="_normalize_markdown",
        title="T",
        markdown="# Given\n\nbody\n",
    )
    expect_equal(actual=headed, expected="# Given\n\nbody\n")


def test_write_records_previous_duration(tmp_path: Path) -> None:
    """A repeated bundle writes the previous run duration at top level.

    Args:
        tmp_path: Per-test temporary directory.

    """
    clear()
    paths: ReportPaths = ReportPaths(
        markdown=tmp_path / "result.md",
        json=tmp_path / "result.json",
        web=tmp_path / "result_web",
    )
    _ = ReportBundle.write(
        paths=paths,
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n",
        data={"findings": [], "duration_seconds": 9.876},
    )
    payload: JsonObject = ReportBundle.write(
        paths=paths,
        analyzer="demo",
        title="Demo",
        markdown="# Demo\n",
        data={"findings": []},
    )
    expect_equal(
        actual=payload.get("previous_duration_seconds"),
        expected=9.876,
    )
    json_payload: dict[str, JsonValue] = cast(
        typ="dict[str, JsonValue]",
        val=loads(s=paths.json.read_text(encoding="utf-8")),
    )
    expect_equal(
        actual=json_payload.get("previous_duration_seconds"),
        expected=9.876,
    )
    clear()
