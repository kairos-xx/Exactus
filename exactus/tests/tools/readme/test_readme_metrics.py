# Copyright (c) 2026
"""README owns Markdown statistics, sizes and undocumented folders."""

from pathlib import Path
from typing import Final, final

from exactus.tests.common.support import dig, expect_equal
from exactus.tools.readme.metrics import collect_metrics


@final
class Constants:
    """Group module-level constants.

    Attributes:
        doc: Grouped module constant.
        js: Grouped module constant.

    """

    doc: Final[str] = '"""Module."""\n'
    js: Final[str] = (
        "/** Add. */\nexport function add(a, b) {\n  return a;\n}\n"
    )


def _write(*, root: Path, name: str, text: str) -> None:
    """Write one project file, creating its folder.

    Args:
        root: Project directory.
        name: Root-relative path.
        text: File content.

    """
    path: Path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(data=text)


def _project(*, root: Path) -> None:
    """Create sources and Markdown files of several sizes.

    Args:
        root: Project directory.

    """
    _write(root=root, name="README.md", text="# Root\n\nIntro.\n")
    _write(root=root, name="app.py", text=Constants.doc + "x = 1\n")
    _write(root=root, name="pkg/mod.py", text=Constants.doc)
    _write(root=root, name="pkg/inner/deep.py", text=Constants.doc)
    _write(root=root, name="pkg/inner/readme.md", text="tiny")
    _write(root=root, name="web/app.js", text=Constants.js)
    _write(root=root, name="exactus/docs/README.md", text="# Docs\n" * 40)
    _write(root=root, name="exactus/docs/guide.md", text="guide\nmore\n")
    _write(root=root, name="exactus/docs/empty.md", text="")


def _metrics(*, root: Path, excludes: tuple[str, ...] = ()) -> object:
    """Collect the README metrics for a fixture project.

    Args:
        root: Project root.
        excludes: Excluded path globs.

    Returns:
        Markdown totals and README sizes.

    """
    return collect_metrics(
        root=root,
        includes=(),
        excludes=excludes,
        excluded_dirs=frozenset({"packages", "node_modules"}),
    )


def test_markdown_and_readme_statistics(tmp_path: Path) -> None:
    """Markdown totals, README count and the largest and smallest README.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    expect_equal(
        actual=dig(document=_metrics(root=root), path=("markdown",)),
        expected={
            "files": 5,
            "bytes": 15 + 280 + 4 + 11 + 0,
            "lines": 3 + 40 + 1 + 2 + 0,
            "readme_files": 3,
            "largest_readme": {"path": "exactus/docs/README.md", "bytes": 280},
            "smallest_readme": {"path": "pkg/inner/readme.md", "bytes": 4},
        },
    )


def test_readme_ties_resolve_to_the_first_path(tmp_path: Path) -> None:
    """Equal-sized READMEs report the first path in path order.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _write(root=root, name="b/README.md", text="same")
    _write(root=root, name="a/README.md", text="same")
    metrics: object = _metrics(root=root)
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "largest_readme")),
        expected={"path": "a/README.md", "bytes": 4},
    )
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "smallest_readme")),
        expected={"path": "a/README.md", "bytes": 4},
    )


def test_directories_without_readme(tmp_path: Path) -> None:
    """Only folders holding analyzed sources can lack a README.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _project(root=root)
    expect_equal(
        actual=dig(
            document=_metrics(root=root),
            path=("directories_without_readme",),
        ),
        expected=["pkg", "web"],
    )


def test_root_without_readme_is_listed_as_dot(tmp_path: Path) -> None:
    """A root holding sources but no README appears as ``.``.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _write(root=root, name="app.py", text=Constants.doc)
    _write(root=root, name="exactus/docs/README.md", text="docs")
    expect_equal(
        actual=dig(
            document=_metrics(root=root),
            path=("directories_without_readme",),
        ),
        expected=["."],
    )


def test_exclusions_apply_to_markdown(tmp_path: Path) -> None:
    """Excluded folders, hidden folders and exclude globs hide Markdown.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _write(root=root, name="README.md", text="root")
    _write(root=root, name="app.py", text=Constants.doc)
    _write(root=root, name="node_modules/pkg/README.md", text="x" * 99)
    _write(root=root, name=".github/README.md", text="x" * 98)
    _write(root=root, name="exactus/packages/README.md", text="x" * 97)
    _write(root=root, name="exactus/docs/README.md", text="x" * 96)
    metrics: object = _metrics(root=root, excludes=("exactus/docs/**",))
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "files")),
        expected=1,
    )
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "bytes")),
        expected=4,
    )
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "readme_files")),
        expected=1,
    )


def test_symlinked_markdown_is_ignored(tmp_path: Path) -> None:
    """A Markdown symlink pointing outside the root is never followed.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _write(root=root, name="app.py", text=Constants.doc)
    _write(root=tmp_path, name="outside.md", text="outside")
    (root / "README.md").symlink_to(target=tmp_path / "outside.md")
    metrics: object = _metrics(root=root)
    expect_equal(
        actual=dig(document=metrics, path=("markdown", "files")),
        expected=0,
    )
    expect_equal(
        actual=dig(document=metrics, path=("directories_without_readme",)),
        expected=["."],
    )


def test_project_without_markdown_has_empty_readme_stats(
    tmp_path: Path,
) -> None:
    """No Markdown gives zero totals, ``None`` extremes and every folder.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    _write(root=root, name="pkg/mod.py", text=Constants.doc)
    expect_equal(
        actual=_metrics(root=root),
        expected={
            "markdown": {
                "files": 0,
                "bytes": 0,
                "lines": 0,
                "readme_files": 0,
                "largest_readme": None,
                "smallest_readme": None,
            },
            "directories_without_readme": ["pkg"],
        },
    )
