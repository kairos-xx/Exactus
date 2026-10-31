# Copyright (c) 2026
"""Behavioral tests for the lints source cleaner."""

from pathlib import Path
from textwrap import dedent

from exactus.tests.common.support import expect_equal, expect_in, expect_true
from exactus.tools.lints.core import SourceCleaner


def test_normalize_drops_javascript_blank_lines() -> None:
    """JavaScript cleaning removes empty lines outside literals."""
    source: str = (
        "const a = 1;\n\n\nconst b = 2;   \n\n/* first\n\nsecond */\n"
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("app.js"), source=source),
        expected=("const a = 1;\nconst b = 2;\n/* first\n\nsecond */\n"),
    )


def test_normalize_keeps_template_literal_blank_lines() -> None:
    """Blank lines inside template literals are string content."""
    source: str = "const s = `a\n\nb`;\n\nconst c = 3;\n"
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("app.mjs"), source=source),
        expected="const s = `a\n\nb`;\nconst c = 3;\n",
    )


def test_normalize_covers_jsx_and_cjs() -> None:
    """JSX and CommonJS sources get the same blank-line removal."""
    source: str = "const a = 1;\n\nconst b = 2;\n"
    for name in ("app.jsx", "app.cjs"):
        expect_equal(
            actual=SourceCleaner.normalize(path=Path(name), source=source),
            expected="const a = 1;\nconst b = 2;\n",
        )


def test_normalize_drops_stylesheet_blank_lines() -> None:
    """CSS cleaning removes empty lines outside block comments."""
    source: str = dedent(
        text=(
            "    a {   \n        color: red;\n    }\n    \n    \n    /* banner"
            "\n    \n    end */\n    b {\n        color: blue;\n    }\n    \n "
            "   "
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("site.css"), source=source),
        expected=(
            dedent(
                text=(
                    "    a {\n        color: red;\n    }\n    /* banner\n "
                    "   \n    end */\n    b {\n        color: blue;\n    }"
                    "\n    "
                ),
            )
        ),
    )


def test_normalize_drops_markup_blank_lines() -> None:
    """HTML cleaning removes empty lines between elements."""
    source: str = (
        "<html>\n\n<body>\n<p>a</p>\n\n\n<p>b</p>\n</body>\n</html>\n"
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("index.html"), source=source),
        expected="<html>\n<body>\n<p>a</p>\n<p>b</p>\n</body>\n</html>\n",
    )


def test_normalize_keeps_preformatted_markup_blanks() -> None:
    """Blank lines inside pre, script and comments are content."""
    source: str = dedent(
        text=(
            "    <pre>\n    \n    keep me\n    \n    </pre>\n    \n    <script"
            ">\n    const s = `a\n    \n    b`;\n    \n    </script>\n    \n  "
            "  <!--\n    \n    comment\n    -->\n    <p>x</p>\n    "
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("index.htm"), source=source),
        expected=(
            dedent(
                text=(
                    "    <pre>\n    \n    keep me\n    \n    </pre>\n    <"
                    "script>\n    const s = `a\n    \n    b`;\n    \n    <"
                    "/script>\n    <!--\n    \n    comment\n    -->\n    <"
                    "p>x</p>\n    "
                ),
            )
        ),
    )


def test_normalize_drops_python_blank_lines_outside_strings() -> None:
    """Python cleaning removes blank lines but keeps docstring content."""
    source: str = dedent(
        text=(
            '    """Module.\n    \n    Longer.\n    """\n    \n    \n    x = 1'
            "\n    \n    \n    def f() -> None:\n        pass\n    \n    "
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("mod.py"), source=source),
        expected=(
            '"""Module.\n\nLonger.\n"""\nx = 1\ndef f() -> None:\n    pass\n'
        ),
    )


def test_normalize_python_pyi_and_final_newline() -> None:
    """Stub files clean like Python and end in one newline."""
    source: str = "x: int\n\n\n"
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("mod.pyi"), source=source),
        expected="x: int\n",
    )


def test_collect_includes_all_source_suffixes(tmp_path: Path) -> None:
    """Collection picks up every handled source suffix.

    Args:
        tmp_path: Per-test project directory.

    """
    names: tuple[str, ...] = (
        "a.py",
        "b.pyi",
        "c.js",
        "d.jsx",
        "e.mjs",
        "f.cjs",
        "g.css",
        "h.html",
        "i.htm",
        "j.txt",
    )
    for name in names:
        _ = (tmp_path / name).write_text(data="x\n", encoding="utf-8")
    collected: set[str] = {
        file.name
        for file in SourceCleaner.collect(
            cwd=tmp_path,
            targets=(str(object=tmp_path),),
            excludes=(),
        )
    }
    expected: set[str] = {name for name in names if name != "j.txt"}
    expect_true(
        condition=collected == expected,
        message=f"Unexpected clean scope: {sorted(collected)}",
    )


def test_collect_excludes_only_root_packages(tmp_path: Path) -> None:
    """A root ``packages/**`` pattern leaves nested packages dirs in scope.

    Args:
        tmp_path: Per-test project directory.

    """
    root_packages: Path = tmp_path / "packages"
    nested_packages: Path = tmp_path / "exactus" / "packages"
    root_packages.mkdir(parents=True)
    nested_packages.mkdir(parents=True)
    _ = (root_packages / "a.py").write_text(data="x\n", encoding="utf-8")
    _ = (nested_packages / "b.py").write_text(data="y\n", encoding="utf-8")
    collected: set[str] = {
        file.relative_to(tmp_path).as_posix()
        for file in SourceCleaner.collect(
            cwd=tmp_path,
            targets=(str(object=tmp_path),),
            excludes=("packages/**",),
        )
    }
    expect_true(
        condition=collected == {"exactus/packages/b.py"},
        message=f"Unexpected clean scope: {sorted(collected)}",
    )


def test_clean_writes_normalized_javascript(tmp_path: Path) -> None:
    """The clean pass rewrites a JavaScript file in place.

    Args:
        tmp_path: Per-test project directory.

    """
    path: Path = tmp_path / "app.js"
    _ = path.write_text(
        data="const a = 1;\n\n\nconst b = 2;\n",
        encoding="utf-8",
    )
    expect_in(member=path.suffix, container=SourceCleaner.js)
    expect_equal(
        actual=SourceCleaner.normalize(
            path=path,
            source=path.read_text(encoding="utf-8"),
        ),
        expected="const a = 1;\nconst b = 2;\n",
    )
