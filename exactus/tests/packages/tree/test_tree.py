# Copyright (c) 2026 João Lopes.
"""Tests for TREE.txt-style directory and archive listings."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

from exactus.packages.tree.core import (
    human_size,
    main,
    members_for,
    render_tree,
)
from exactus.tests.common.support import expect_in, expect_not_in, expect_true

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _fake_tree(root: Path) -> Path:
    """Create a small directory tree and a zip of it.

    Args:
        root: Scratch root populated with demo files.

    Returns:
        The demo directory.

    """
    demo: Path = root / "demo"
    (demo / "pkg" / "nested").mkdir(parents=True)
    _bytes: int = (demo / "pkg" / "mod.py").write_text(
        data="X: int = 1\n",
        encoding="utf-8",
    )
    _bytes = (demo / "pkg" / "nested" / "deep.py").write_text(
        data="Y: int = 2\n",
        encoding="utf-8",
    )
    _bytes = (demo / "README.md").write_text(data="# demo\n", encoding="utf-8")
    with ZipFile(file=root / "demo.zip", mode="w") as archive:
        archive.write(demo / "pkg" / "mod.py", "pkg/mod.py")
        archive.write(
            demo / "pkg" / "nested" / "deep.py",
            "pkg/nested/deep.py",
        )
        archive.write(demo / "README.md", "README.md")
    return demo


def test_human_size_scales_units() -> None:
    """Format byte counts like the inventory renderer."""
    expect_true(condition=human_size(size=512) == "512B")
    expect_true(condition=human_size(size=23000) == "23KB")
    expect_true(condition=human_size(size=4_600_000) == "4.6MB")


def test_render_tree_lists_directory_recursively(tmp_path: Path) -> None:
    """Render a directory with nested ``├──``/``└──`` rows.

    Args:
        tmp_path: Temporary test directory.

    """
    demo: Path = _fake_tree(root=tmp_path)
    text: str = render_tree(source=demo)
    lines: list[str] = text.splitlines()
    expect_true(condition=lines[0].startswith("demo/"))
    expect_in(member="├── README.md", container=text)
    expect_in(member="└── pkg/", container=text)
    expect_in(member="    ├── mod.py", container=text)
    expect_in(member="└── deep.py", container=text)
    expect_true(condition=text.endswith("\n"))


def test_render_tree_lists_zip_members(tmp_path: Path) -> None:
    """Render an archive's members without extracting it.

    Args:
        tmp_path: Temporary test directory.

    """
    _fake_tree(root=tmp_path)
    text: str = render_tree(source=tmp_path / "demo.zip")
    expect_true(condition=text.splitlines()[0].startswith("demo.zip/"))
    expect_in(member="└── pkg/", container=text)
    expect_in(member="└── nested/", container=text)
    expect_in(member="deep.py", container=text)
    expect_in(member="README.md", container=text)


def test_render_tree_accepts_member_lists(tmp_path: Path) -> None:
    """Render explicit string and ``Path`` members.

    Args:
        tmp_path: Temporary test directory.

    """
    demo: Path = _fake_tree(root=tmp_path)
    text: str = render_tree(
        source=["pkg/mod.py", demo / "README.md"],
        root=demo,
        name="bundle",
    )
    expect_true(condition=text.splitlines()[0].startswith("bundle/"))
    expect_in(member="└── pkg/", container=text)
    expect_in(member="└── mod.py", container=text)
    expect_in(member="├── README.md", container=text)


def test_render_tree_include_exclude_globs(tmp_path: Path) -> None:
    """Filter members through include and exclude globs.

    Args:
        tmp_path: Temporary test directory.

    """
    demo: Path = _fake_tree(root=tmp_path)
    text: str = render_tree(source=demo, include=("*.py",))
    expect_in(member="mod.py", container=text)
    expect_not_in(member="README.md", container=text)
    text = render_tree(source=demo, exclude=("pkg/nested/*",))
    expect_in(member="README.md", container=text)
    expect_in(member="mod.py", container=text)
    expect_not_in(member="deep.py", container=text)


def test_render_tree_marks_missing_members(tmp_path: Path) -> None:
    """Keep absent member labels with zeroed stats.

    Args:
        tmp_path: Temporary test directory.

    """
    text: str = render_tree(
        source=["gone/file.py"],
        root=tmp_path,
        name="ghost",
    )
    expect_in(member="gone/", container=text)
    expect_in(member="file.py", container=text)
    expect_in(member="0B", container=text)


def test_members_for_single_file(tmp_path: Path) -> None:
    """Resolve a lone file argument to one member.

    Args:
        tmp_path: Temporary test directory.

    """
    file: Path = tmp_path / "solo.txt"
    content: str = "hi\n"
    _bytes: int = file.write_text(data=content, encoding="utf-8")
    members: dict[str, tuple[int, float] | None] = members_for(source=file)
    expect_true(condition=tuple(members) == ("solo.txt",))
    entry: tuple[int, float] | None = members["solo.txt"]
    expect_true(condition=entry is not None and entry[0] == len(content))


def test_main_renders_sources_and_writes_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render CLI sources, honoring globs, filters and ``-o``.

    Args:
        tmp_path: Temporary test directory.
        monkeypatch: Pytest monkeypatch fixture.

    """
    demo: Path = _fake_tree(root=tmp_path)
    monkeypatch.chdir(path=tmp_path)
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.tree.core.stdout",
        name=capture,
    )
    status: int = main(arguments=(str(object=demo),))
    expect_true(condition=status == 0)
    expect_in(member="demo/", container=capture.getvalue())
    out: Path = tmp_path / "out.txt"
    status = main(
        arguments=("demo", "--exclude", "*deep*", "-o", str(object=out)),
    )
    expect_true(condition=status == 0)
    text: str = out.read_text(encoding="utf-8")
    expect_in(member="mod.py", container=text)
    expect_not_in(member="deep.py", container=text)


def test_main_usage_without_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit ``1`` with usage when nothing resolves.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    monkeypatch.chdir(path="/")
    capture: StringIO = StringIO()
    monkeypatch.setattr(
        target="exactus.packages.tree.core.stdout",
        name=capture,
    )
    status: int = main(arguments=("definitely/missing/path",))
    expect_true(condition=status == 1)
    expect_in(member="usage", container=capture.getvalue())
