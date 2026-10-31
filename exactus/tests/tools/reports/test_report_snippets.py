# Copyright (c) 2026
"""Migrated tools store finding excerpts in result.json, Markdown and web."""

from __future__ import annotations

from functools import partial
from json import loads
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_in,
    expect_not_in,
    expect_true,
    fail,
)
from exactus.tools.common import execution as ent
from exactus.tools.docs.main import main as docs_main
from exactus.tools.lints.main import main as lints_main
from exactus.tools.readme.main import main as readme_main

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        marker: Grouped module constant.
        util: Grouped module constant.

    """

    marker: Final[str] = "# " + "noqa"
    util: Final[str] = (
        '"""Helpers."""\n\nfrom pathlib import Path\n\nimport os '
        f' {marker}\n\n\ndef size(path: Path) -> int:\n    """Return the'
        " size.\n\n    Args:\n        path: File.\n\n    Returns:\n       "
        ' Bytes.\n    """\n    return path.stat().st_size\n\n\ndef'
        " helper():\n    return 1\n"
    )


@pytest.fixture(autouse=True)
def quiet_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run each test inside a throwaway project with a clean environment.

    Args:
        monkeypatch: Pytest patching helper.
        tmp_path: Pytest temporary directory.

    """
    monkeypatch.chdir(path=tmp_path)
    monkeypatch.setenv(name="EXACTUS_ORCHESTRATED", value="1")
    monkeypatch.setattr(target=ent, name="argv", value=["tool", "."])
    for name in ("EXACTUS_RUN_ID", "EXACTUS_PIPELINE_RUN_ID"):
        monkeypatch.delenv(name=name, raising=False)


def _project(*, root: Path) -> None:
    """Create a project with one finding per migrated tool.

    Args:
        root: Project directory.

    """
    (root / "pkg").mkdir(parents=True)
    _ = (root / "pkg" / "util.py").write_text(
        data=Constants.util,
        encoding="utf-8",
    )
    script: Path = root / "pkg" / "run.py"
    _ = script.write_text(data='x = 1\n"""Not a shebang."""\n')
    script.chmod(mode=493)


def _object(*, path: Path) -> dict[str, JsonValue]:
    """Read one JSON object file.

    Args:
        path: JSON file.

    Returns:
        The decoded object.

    """
    loaded: JsonValue = loads(s=path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        fail(message=f"{path} is not a JSON object")
    return loaded


def _run(
    *,
    analyzer: str,
    main: Callable[..., int],
    root: Path,
    out: Path,
    extra: tuple[str, ...] = (),
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    """Run one tool through ``execute_exactus``.

    Args:
        analyzer: Analyzer name.
        main: The tool's ``main``.
        root: Project directory.
        out: Report directory.
        extra: Additional tool arguments.

    Returns:
        ``result.json``, web ``data.json`` and ``result.md``.

    """
    _ = ent.execute_exactus(
        analyzer=analyzer,
        title=f"{analyzer} exactus",
        main=partial(
            main,
            arguments=(
                str(object=root),
                "--output-dir",
                str(object=out),
                *extra,
            ),
        ),
        output=out,
    )
    return (
        _object(path=out / "result.json"),
        _object(path=out / "result_web" / "data.json"),
        (out / "result.md").read_text(encoding="utf-8"),
    )


def _keys(*, value: object) -> list[str]:
    """Return the keys of a JSON object, or nothing for other values.

    Args:
        value: Candidate object.

    Returns:
        Its string keys.

    """
    if not isinstance(value, dict):
        return []
    return [
        str(object=key) for key in cast(typ="dict[str, object]", val=value)
    ]


def _finding(*, payload: object, rule: str, view: bool = False) -> object:
    """Return the first finding of ``rule`` in a payload or its view.

    Args:
        payload: ``result.json`` or ``data.json``.
        rule: Rule code.
        view: Read the view model's findings instead.

    Returns:
        The finding.

    """
    path: tuple[str, ...] = ("view", "findings") if view else ("findings",)
    for finding in dig_list(document=payload, path=path):
        if dig(document=finding, path=("rule",)) == rule:
            return finding
    return fail(message=f"no {rule} finding")


def test_exec_excerpt_follows_context_lines(tmp_path: Path) -> None:
    """LINTS stores the requested context; Markdown and web carry it.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    result: dict[str, JsonValue]
    web: dict[str, JsonValue]
    markdown: str
    result, web, markdown = _run(
        analyzer="lints",
        main=lints_main,
        root=root,
        out=tmp_path / "LINTS",
        extra=("--context-lines", "1", "--dry"),
    )
    finding: object = _finding(payload=result, rule="EXE002")
    expect_equal(
        actual=dig(document=finding, path=("excerpt",)),
        expected={
            "language": "python",
            "line": 1,
            "context": 1,
            "start": 1,
            "end": 2,
            "clipped": False,
            "lines": [
                {"n": 1, "text": "x = 1", "target": True},
                {"n": 2, "text": '"""Not a shebang."""', "target": False},
            ],
        },
    )
    expect_equal(
        actual=dig(
            document=_finding(payload=web, rule="EXE002", view=True),
            path=("excerpt",),
        ),
        expected=dig(document=finding, path=("excerpt",)),
    )
    expect_in(
        member='~~~python\n    1>| x = 1\n    2 | """Not a shebang."""\n~~~\n',
        container=markdown,
    )


def test_context_zero_keeps_the_target_line(tmp_path: Path) -> None:
    """``--context-lines 0`` captures the finding line alone.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    result: dict[str, JsonValue] = _run(
        analyzer="lints",
        main=lints_main,
        root=root,
        out=tmp_path / "LINTS",
        extra=("--context-lines", "0", "--dry"),
    )[0]
    expect_equal(
        actual=dig(
            document=_finding(payload=result, rule="EXE002"),
            path=("excerpt", "lines"),
        ),
        expected=[{"n": 1, "text": "x = 1", "target": True}],
    )


def test_lints_and_docs_excerpts_use_default_context(tmp_path: Path) -> None:
    """LINTS and DOCS capture three lines on each side by default.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    compliance: dict[str, JsonValue]
    compliance_web: dict[str, JsonValue]
    compliance_md: str
    compliance, compliance_web, compliance_md = _run(
        analyzer="lints",
        main=lints_main,
        root=root,
        out=tmp_path / "LINTS",
        extra=("--dry",),
    )
    marker: object = _finding(payload=compliance, rule="CMP001")
    expect_equal(
        actual=(
            dig(document=marker, path=("excerpt", "start")),
            dig(document=marker, path=("excerpt", "end")),
            dig(document=marker, path=("excerpt", "context")),
        ),
        expected=(2, 8, 3),
    )
    expect_in(
        member=f"    5>| import os  {Constants.marker}\n",
        container=compliance_md,
    )
    expect_in(
        member="excerpt",
        container=_keys(
            value=_finding(payload=compliance_web, rule="CMP001", view=True),
        ),
    )
    docs: dict[str, JsonValue]
    docs_md: str
    docs, _, docs_md = _run(
        analyzer="docs",
        main=docs_main,
        root=root,
        out=tmp_path / "DOCS",
        extra=("--language", "python"),
    )
    missing: object = _finding(payload=docs, rule="DOC001")
    expect_equal(
        actual=dig(document=missing, path=("excerpt", "line")),
        expected=dig(document=missing, path=("line",)),
    )
    expect_in(member="   20>| def helper():\n", container=docs_md)


def test_readme_findings_without_lines_get_no_excerpt(tmp_path: Path) -> None:
    """README findings point at directories or whole files: no excerpt.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    (root / "src" / "pkg").mkdir(parents=True)
    _ = (root / "src" / "pkg" / "mod.py").write_text(data="x = 1\n")
    result: dict[str, JsonValue]
    markdown: str
    result, _, markdown = _run(
        analyzer="readme",
        main=readme_main,
        root=root,
        out=tmp_path / "README",
        extra=("--dry",),
    )
    findings: list[object] = dig_list(document=result, path=("findings",))
    expect_true(condition=bool(findings))
    for finding in findings:
        expect_equal(actual=dig(document=finding, path=("line",)), expected=0)
        expect_not_in(member="excerpt", container=_keys(value=finding))
    findings_section: str = markdown.split(sep="## Findings")[1].split(
        sep="## Artifacts",
    )[0]
    expect_not_in(member="~~~", container=findings_section)


def test_web_bundle_ships_the_snippet_viewer(tmp_path: Path) -> None:
    """The bundled script renders excerpts with the context controls.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    out: Path = tmp_path / "LINTS"
    _ = _run(
        analyzer="lints",
        main=lints_main,
        root=root,
        out=out,
        extra=("--dry",),
    )
    script: str = (out / "result_web" / "report.js").read_text(
        encoding="utf-8",
    )
    for member in (
        "static snippetViewer",
        "static bindSnippets",
        "data-snippet-step",
        '"excerpt"',
    ):
        expect_in(member=member, container=script)
    styles: str = (out / "result_web" / "report.css").read_text(
        encoding="utf-8",
    )
    expect_in(member=".code-target", container=styles)
