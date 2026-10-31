# Copyright (c) 2026
"""Tests for CSS file/directory comparison targets."""

from pathlib import Path

import pytest

from exactus.packages.visual_cause import CssTarget
from exactus.tests.packages.visual_cause.support import (
    expect_equal,
    expect_in,
    expect_true,
)


def test_file_target(tmp_path: Path) -> None:
    """Load a single CSS file as one target.

    Args:
    tmp_path: Value for tmp path.

    """
    css: Path = tmp_path / "one.css"
    css.write_text(data=".a { color: red; }", encoding="utf-8")
    target: CssTarget = CssTarget.load(source=css)
    expect_equal(actual=target.files, expected=(css.resolve(),))
    expect_in(member=".a { color: red; }", container=target.css)


def test_directory_target_is_recursive_and_deterministic(
    tmp_path: Path,
) -> None:
    """Combine recursive CSS files in relative lexical order.

    Args:
    tmp_path: Value for tmp path.

    """
    nested: Path = tmp_path / "nested"
    nested.mkdir()
    (nested / "z.css").write_text(data=".z {}", encoding="utf-8")
    (tmp_path / "a.css").write_text(data=".a {}", encoding="utf-8")
    (nested / "ignore.txt").write_text(data="no", encoding="utf-8")
    target: CssTarget = CssTarget.load(source=tmp_path)
    expect_equal(
        actual=[path.name for path in target.files],
        expected=["a.css", "z.css"],
    )
    expect_true(
        condition=target.css.index(".a {}") < target.css.index(".z {}"),
    )


def test_directory_without_css_fails(tmp_path: Path) -> None:
    """Reject an empty CSS target directory.

    Args:
    tmp_path: Value for tmp path.

    """
    with pytest.raises(expected_exception=FileNotFoundError):
        CssTarget.load(source=tmp_path)


def test_non_css_file_fails(tmp_path: Path) -> None:
    """Reject a non-CSS file target.

    Args:
    tmp_path: Value for tmp path.

    """
    source: Path = tmp_path / "x.txt"
    source.write_text(data="x", encoding="utf-8")
    with pytest.raises(expected_exception=ValueError, match="must end in"):
        CssTarget.load(source=source)
