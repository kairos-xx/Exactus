# Copyright (c) 2026
"""The ``FILES`` bundle written beside reports when collecting files."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from json import dumps
from os import environ
from typing import TYPE_CHECKING
from zipfile import ZipFile

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_true,
)
from exactus.tools.common import collect_files as cf
from exactus.tools.common.cli import add_common_arguments

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from exactus.tools.common.json_types import JsonValue


def _report(
    *,
    output: Path,
    root: Path,
    findings: list[JsonValue],
    snapshots: dict[str, JsonValue] | None = None,
) -> None:
    """Write a minimal ``result.json`` into ``output``.

    Args:
        output: Report directory.
        root: Recorded ``project_root``.
        findings: Top-level findings list.
        snapshots: Optional ``report_snapshots`` block.

    """
    output.mkdir(parents=True, exist_ok=True)
    payload: dict[str, JsonValue] = {
        "tool": "demo",
        "project_root": str(object=root),
        "findings": findings,
    }
    if snapshots is not None:
        payload["report_snapshots"] = snapshots
    _ = (output / "result.json").write_text(
        data=dumps(obj=payload),
        encoding="utf-8",
    )


def _names(*, archive: Path) -> frozenset[str]:
    """List the member names inside one zip archive.

    Args:
        archive: Archive to inspect.

    Returns:
        Member names.

    """
    with ZipFile(file=archive) as bundle:
        return frozenset(bundle.namelist())


def test_requested_flag_or_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collection is requested by the flag token or the env variable.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name=cf.Constants.variable, raising=False)
    expect_false(condition=cf.requested(tokens=()))
    expect_false(condition=cf.requested(tokens=("--dry",)))
    expect_true(condition=cf.requested(tokens=("--collect-files",)))
    monkeypatch.setenv(name=cf.Constants.variable, value="1")
    expect_true(condition=cf.requested(tokens=()))


def test_mark_exports_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    """``mark`` exports the variable only when the flag is present.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name=cf.Constants.variable, raising=False)
    expect_equal(actual=cf.mark(tokens=("--dry",)), expected=("--dry",))
    expect_false(condition=cf.Constants.variable in environ)
    tokens: tuple[str, ...] = cf.mark(tokens=("--collect-files",))
    expect_equal(actual=tokens, expected=("--collect-files",))
    expect_true(condition=cf.requested(tokens=()))


def test_collect_report_files_bundles_findings(tmp_path: Path) -> None:
    """The bundle zips every finding file keeping its folder structure.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    source: Path = root / "pkg" / "mod.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text(data="x = 1\n", encoding="utf-8")
    output: Path = tmp_path / "report"
    _report(
        output=output,
        root=root,
        findings=[{"file": "pkg/mod.py", "severity": "error"}],
    )
    expect_true(condition=cf.collect_report_files(output=output))
    bundle: Path = output / "FILES"
    expect_true(condition=(bundle / "README.md").is_file())
    expect_true(condition=(bundle / "TREE.txt").is_file())
    expect_true(condition=(bundle / "files.zip").is_file())
    expect_equal(
        actual=_names(archive=bundle / "files.zip"),
        expected=frozenset({"pkg/mod.py"}),
    )
    tree: str = (bundle / "TREE.txt").read_text(encoding="utf-8")
    expect_in(member="files.zip/", container=tree)
    expect_in(member="pkg/", container=tree)
    expect_in(member="mod.py", container=tree)
    readme: str = (bundle / "README.md").read_text(encoding="utf-8")
    expect_in(member="Files collected: 1", container=readme)


def test_collect_report_files_reads_snapshots(tmp_path: Path) -> None:
    """Pipeline aggregate findings inside ``report_snapshots`` count.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    _ = (root / "a.py").write_text(data="a = 1\n", encoding="utf-8")
    _ = (root / "b.py").write_text(data="b = 1\n", encoding="utf-8")
    output: Path = tmp_path / "report"
    _report(
        output=output,
        root=root,
        findings=[{"file": "a.py"}],
        snapshots={
            "lints": {"findings": [{"path": "b.py"}, {"file": "a.py"}]},
        },
    )
    expect_true(condition=cf.collect_report_files(output=output))
    expect_equal(
        actual=_names(archive=output / "FILES" / "files.zip"),
        expected=frozenset({"a.py", "b.py"}),
    )


def test_collect_report_files_lists_missing(tmp_path: Path) -> None:
    """Reported files absent on disk are named in the README.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    output: Path = tmp_path / "report"
    _report(output=output, root=root, findings=[{"file": "gone.py"}])
    expect_true(condition=cf.collect_report_files(output=output))
    bundle: Path = output / "FILES"
    expect_equal(
        actual=_names(archive=bundle / "files.zip"),
        expected=frozenset[str](),
    )
    readme: str = (bundle / "README.md").read_text(encoding="utf-8")
    expect_in(member="gone.py", container=readme)


def test_collect_report_files_without_report(tmp_path: Path) -> None:
    """A missing ``result.json`` skips the bundle entirely.

    Args:
        tmp_path: Per-test temporary directory.

    """
    expect_false(condition=cf.collect_report_files(output=tmp_path))
    expect_false(condition=(tmp_path / "FILES").exists())


def test_common_parser_accepts_collect_files() -> None:
    """The shared tool parser exposes ``--collect-files``."""
    parser: ArgumentParser = ArgumentParser()
    add_common_arguments(parser=parser, default_output="X")
    options: Namespace = parser.parse_args(args=())
    expect_false(condition=options.collect_files)
    options = parser.parse_args(args=("--collect-files",))
    expect_true(condition=options.collect_files)


def test_requested_and_mark_accept_underscore_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--collect_files`` enables collection like ``--collect-files``.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.delenv(name=cf.Constants.variable, raising=False)
    expect_true(condition=cf.requested(tokens=("--collect_files",)))
    tokens: tuple[str, ...] = cf.mark(tokens=("--collect_files",))
    expect_equal(actual=tokens, expected=("--collect_files",))
    expect_true(condition=cf.Constants.variable in environ)
