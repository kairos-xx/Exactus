# Copyright (c) 2026
"""Behavioral tests for the lints source cleaner."""

from collections.abc import Sequence
from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest

from exactus.tests.common.support import (
    expect_equal,
    expect_in,
    expect_true,
    private_call,
)
from exactus.tools.common.sprint import Writer
from exactus.tools.lints.core import (
    CleanStats,
    CommandResult,
    LintExactus,
    SourceCleaner,
)


def test_normalize_drops_javascript_blank_lines() -> None:
    """JavaScript cleaning removes empty lines outside literals."""
    source: str = """\
const a = 1;


const b = 2;

/* first

second */
"""
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("app.js"), source=source),
        expected=(
            """\
const a = 1;
const b = 2;
/* first

second */
"""
        ),
    )


def test_normalize_keeps_template_literal_blank_lines() -> None:
    """Blank lines inside template literals are string content."""
    source: str = """\
const s = `a

b`;

const c = 3;
"""
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("app.mjs"), source=source),
        expected="""\
const s = `a

b`;
const c = 3;
""",
    )


def test_normalize_covers_jsx_and_cjs() -> None:
    """JSX and CommonJS sources get the same blank-line removal."""
    source: str = """\
const a = 1;

const b = 2;
"""
    for name in ("app.jsx", "app.cjs"):
        expect_equal(
            actual=SourceCleaner.normalize(path=Path(name), source=source),
            expected="""\
const a = 1;
const b = 2;
""",
        )


def test_normalize_drops_stylesheet_blank_lines() -> None:
    """CSS cleaning removes empty lines outside block comments."""
    source: str = dedent(
        text=(
            """\
    a {
        color: red;
    }


    /* banner

    end */
    b {
        color: blue;
    }

    """
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("site.css"), source=source),
        expected=(
            dedent(
                text=(
                    """\
    a {
        color: red;
    }
    /* banner

    end */
    b {
        color: blue;
    }
    """
                ),
            )
        ),
    )


def test_normalize_drops_markup_blank_lines() -> None:
    """HTML cleaning removes empty lines between elements."""
    source: str = """\
<html>

<body>
<p>a</p>


<p>b</p>
</body>
</html>
"""
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("index.html"), source=source),
        expected="""\
<html>
<body>
<p>a</p>
<p>b</p>
</body>
</html>
""",
    )


def test_normalize_keeps_preformatted_markup_blanks() -> None:
    """Blank lines inside pre, script and comments are content."""
    source: str = dedent(
        text=(
            """\
    <pre>

    keep me

    </pre>

    <script>
    const s = `a

    b`;

    </script>

    <!--

    comment
    -->
    <p>x</p>
    """
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("index.htm"), source=source),
        expected=(
            dedent(
                text=(
                    """\
    <pre>

    keep me

    </pre>
    <script>
    const s = `a

    b`;

    </script>
    <!--

    comment
    -->
    <p>x</p>
    """
                ),
            )
        ),
    )


def test_normalize_drops_python_blank_lines_outside_strings() -> None:
    """Python cleaning removes blank lines but keeps docstring content."""
    source: str = dedent(
        text=(
            """\
    \"""Module.

    Longer.
    \"""


    x = 1


    def f() -> None:
        pass

    """
        ),
    )
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("mod.py"), source=source),
        expected=(
            """\
\"""Module.

Longer.
\"""
x = 1
def f() -> None:
    pass
"""
        ),
    )


def test_normalize_python_pyi_and_final_newline() -> None:
    """Stub files clean like Python and end in one newline."""
    source: str = """\
x: int


"""
    expect_equal(
        actual=SourceCleaner.normalize(path=Path("mod.pyi"), source=source),
        expected="""\
x: int
""",
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
        _ = (tmp_path / name).write_text(
            data="""\
x
""",
            encoding="utf-8",
        )
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
    _ = (root_packages / "a.py").write_text(
        data="""\
x
""",
        encoding="utf-8",
    )
    _ = (nested_packages / "b.py").write_text(
        data="""\
y
""",
        encoding="utf-8",
    )
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
        data="""\
const a = 1;


const b = 2;
""",
        encoding="utf-8",
    )
    expect_in(member=path.suffix, container=SourceCleaner.js)
    expect_equal(
        actual=SourceCleaner.normalize(
            path=path,
            source=path.read_text(encoding="utf-8"),
        ),
        expected="""\
const a = 1;
const b = 2;
""",
    )


def test_run_reports_formatter_failures_without_aborting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file a formatter cannot parse becomes a finding, not a crash.

    The batch run fails, the per-file retry isolates the unparsable
    file, and the remaining file is still formatted.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    good: Path = tmp_path / "ok.css"
    bad: Path = tmp_path / "broken.css"
    _ = good.write_text(
        data="""\
a { color: red; }
""",
        encoding="utf-8",
    )
    _ = bad.write_text(
        data="""\
a { color: red; }
""",
        encoding="utf-8",
    )
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_run_command(
        command: Sequence[str],
        cwd: Path,
    ) -> CommandResult:
        """Return the recorded command result without executing.

        Args:
            command: Recorded command tokens.
            cwd: Invocation working directory.

        Returns:
            Queued command result for the invocation.

        """
        calls.append((tuple(command), cwd))
        failing: bool = str(object=bad) in command
        batch: bool = (
            str(object=good) in command and str(object=bad) in command
        )
        return CommandResult(
            command=tuple(command),
            returncode=2 if batch or failing else 0,
            stdout="",
            stderr=(
                f"[error] {bad}: SyntaxError: broken css (3:5)"
                if failing
                else "batch exploded"
            ),
        )

    monkeypatch.setattr(
        target=LintExactus,
        name="run_command",
        value=staticmethod(fake_run_command),
    )
    stats: CleanStats = SourceCleaner.run(
        files=[good, bad],
        cwd=tmp_path,
        writer=StringIO(),
        commands={"prettier": ("prettier",)},
        enabled=True,
    )
    expect_equal(actual=len(stats.failures), expected=1)
    expect_equal(
        actual=stats.failures,
        expected=[
            {
                "tool": "prettier",
                "file": "broken.css",
                "line": 3,
                "column": 5,
                "end_line": 3,
                "end_column": 5,
                "rule": "formatter-failed",
                "severity": "error",
                "message": (f"[error] {bad}: SyntaxError: broken css (3:5)"),
            },
        ],
    )
    expect_true(condition=all(cwd == tmp_path for _, cwd in calls))


def test_format_report_entry_carried_into_audit_report() -> None:
    """A carried clean/format entry merges when the stage never ran.

    The transactional pipeline repeats the workflow read-only after
    freezing mutations; that pass must still surface formatter
    failures recorded by the earlier mutating pass.
    """
    carried: dict[str, object] = {
        "tool": "format",
        "command": [],
        "returncode": 1,
        "stderr": "",
        "count": 1,
        "findings": [
            {
                "tool": "prettier",
                "file": "broken.html",
                "line": 3,
                "column": 5,
                "end_line": 3,
                "end_column": 5,
                "rule": "formatter-failed",
                "severity": "error",
                "message": "SyntaxError: broken html (3:5)",
            },
        ],
        "duration_seconds": 0.5,
    }
    entry: object = private_call(
        owner=LintExactus,
        name="_format_report_entry",
        clean_stats=None,
        carried=carried,
    )
    expect_equal(actual=entry, expected={"format": carried})
    expect_equal(
        actual=private_call(
            owner=LintExactus,
            name="_format_report_entry",
            clean_stats=None,
        ),
        expected={},
    )


def test_run_reports_cleaner_failures_without_aborting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file the normalizer cannot process becomes a finding too.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    first: Path = tmp_path / "one.py"
    second: Path = tmp_path / "two.py"
    _ = first.write_text(
        data="""\
x = 1
""",
        encoding="utf-8",
    )
    _ = second.write_text(
        data="""\
y = 2
""",
        encoding="utf-8",
    )

    def explode(
        cls: type[SourceCleaner],
        path: Path,
        stats: CleanStats,
        writer: Writer,
    ) -> None:
        """Raise unconditionally to simulate a normalization failure.

        Args:
            cls: Bound SourceCleaner class.
            path: File being normalized.
            stats: Accumulated clean statistics.
            writer: Report sink.

        Raises:
            OSError: Always, to reject the clean operation.

        """
        _ = cls, stats, writer
        msg: str = f"cannot normalize {path.name}"
        raise OSError(msg)

    monkeypatch.setattr(
        target=SourceCleaner,
        name="_clean",
        value=classmethod(explode),
    )
    stats: CleanStats = SourceCleaner.run(
        files=[first, second],
        cwd=tmp_path,
        writer=StringIO(),
        commands={},
        enabled=True,
    )
    expect_equal(actual=len(stats.failures), expected=2)
    expect_equal(
        actual=stats.failures,
        expected=[
            {
                "tool": "clean",
                "file": "one.py",
                "line": 0,
                "column": 0,
                "end_line": 0,
                "end_column": 0,
                "rule": "clean-failed",
                "severity": "error",
                "message": "cannot normalize one.py",
            },
            {
                "tool": "clean",
                "file": "two.py",
                "line": 0,
                "column": 0,
                "end_line": 0,
                "end_column": 0,
                "rule": "clean-failed",
                "severity": "error",
                "message": "cannot normalize two.py",
            },
        ],
    )
