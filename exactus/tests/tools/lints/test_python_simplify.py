# Copyright (c) 2026
"""Regression tests for conservative Python simplifications."""

from pathlib import Path
from textwrap import dedent

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.lints.python_simplify import (
    PythonSimplifyResult,
    simplify_python_files,
    simplify_python_source,
)


def test_inline_annotated_immediate_return() -> None:
    """Inline an immediately returned, single-use annotated temporary."""
    source: str = "def compute():\n    value: int = 42\n    return value\n"
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=result.source,
        expected="def compute():\n    return 42\n",
    )
    expect_equal(actual=result.proposals[0].rule, expected="PYS001")


def test_walrus_in_if_and_preserve_body() -> None:
    """Introduce a named expression without re-evaluating its initializer."""
    source: str = dedent(
        text="""\
    def compute():
        value: int = calculate()
        if value:
            consume(value)
        return value
    """,
    )
    result: PythonSimplifyResult = simplify_python_source(
        source=source,
        fix=True,
    )
    expect_true(condition="if (value := calculate()):" in result.source)
    expect_true(condition="consume(value)" in result.source)
    expect_equal(actual=result.proposals[0].rule, expected="PYS002")
    expect_false(
        condition=simplify_python_source(
            source=result.source,
            fix=True,
        ).changed,
    )


def test_audit_does_not_modify_source() -> None:
    """Audit mode returns proposed edits without applying them."""
    source: str = "def compute():\n    x = 1\n    return x\n"
    result: PythonSimplifyResult = simplify_python_source(source=source)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=len(result.proposals), expected=1)
    expect_false(condition=result.changed)


def test_nonadjacent_statements_are_preserved() -> None:
    """Never move computation past statements with observable behavior."""
    source: str = (
        "def compute():\n    x = calculate()\n    notify()\n    return x\n"
    )
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_nested_read_prevents_inline() -> None:
    """Maintain variables referenced in more than one expression."""
    source: str = "def compute():\n    x = 1\n    print(x)\n    return x\n"
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_comment_prevents_rewrite() -> None:
    """Do not relocate source lines containing comments."""
    source: str = "def compute():\n    x = 1  # keep\n    return x\n"
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_walrus_can_be_disabled() -> None:
    """Explicit policy disables named-expression changes."""
    source: str = (
        "def compute():\n    x = calculate()\n    if x:\n        use(x)\n"
    )
    expect_false(
        condition=simplify_python_source(
            source=source,
            fix=True,
            walrus=False,
        ).changed,
    )


def test_multiline_assignment_is_not_moved() -> None:
    """Skip expressions that cannot be replaced as one source line."""
    source: str = dedent(
        text="""\
    def compute():
        x = (
            calculate()
        )
        if x:
            use(x)
    """,
    )
    expect_false(
        condition=simplify_python_source(source=source, fix=True).changed,
    )


def test_file_runner_audit_only(tmp_path: Path) -> None:
    """No-fix mode leaves files byte-for-byte unchanged.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "source.py"
    _ = file.write_text(
        data="def f():\n    x = 5\n    return x\n",
        encoding="utf-8",
    )
    before: bytes = file.read_bytes()
    report: dict[str, int] = simplify_python_files(files=(file,), fix=False)
    expect_equal(
        actual=report,
        expected={"files": 1, "proposals": 1, "changed": 0},
    )
    expect_equal(actual=file.read_bytes(), expected=before)


def test_file_runner_fixes_once(tmp_path: Path) -> None:
    """Repeated execution converges to one stable representation.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "source.py"
    _ = file.write_text(
        data="def f():\n    x = 5\n    return x\n",
        encoding="utf-8",
    )
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=1,
    )
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=0,
    )


def test_file_runner_preserves_utf8_bom_and_crlf(tmp_path: Path) -> None:
    """Preserve BOM and newline bytes after an atomic transform.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "crlf.py"
    original: bytes = b"\xef\xbb\xbfdef f():\r\n    x = 4\r\n    return x\r\n"
    _ = file.write_bytes(data=original)
    result: dict[str, int] = simplify_python_files(files=(file,), fix=True)
    expect_equal(actual=result["changed"], expected=1)
    expect_equal(
        actual=file.read_bytes(),
        expected=b"\xef\xbb\xbfdef f():\r\n    return 4\r\n",
    )


def test_file_runner_supports_source_encoding_cookie(tmp_path: Path) -> None:
    """Honor PEP 263 encodings instead of unconditionally using UTF-8.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "latin1.py"
    text: str = "# coding: latin-1\ndef f():\n    x = 'café'\n    return x\n"
    _ = file.write_bytes(data=text.encode(encoding="latin-1"))
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True)["changed"],
        expected=1,
    )
    expect_equal(
        actual=file.read_bytes(),
        expected="# coding: latin-1\ndef f():\n    return 'café'\n".encode(
            encoding="latin-1",
        ),
    )


def test_file_runner_skips_unreadable_python(tmp_path: Path) -> None:
    """Invalid source should be skipped without an attempted rewrite.

    Args:
        tmp_path: Per-test project directory.

    """
    file: Path = tmp_path / "invalid.py"
    _ = file.write_bytes(data=b"\xff\xfe\xff")
    expect_equal(
        actual=simplify_python_files(files=(file,), fix=True),
        expected={"files": 0, "proposals": 0, "changed": 0},
    )


def test_file_runner_preserves_symlink_target(tmp_path: Path) -> None:
    """Avoid replacing links with unrelated temporary regular files.

    Args:
        tmp_path: Per-test project directory.

    """
    target: Path = tmp_path / "actual.py"
    _ = target.write_text(data="def f():\n    x = 9\n    return x\n")
    alias: Path = tmp_path / "alias.py"
    alias.symlink_to(target=target)
    expect_equal(
        actual=simplify_python_files(files=(alias,), fix=True)["changed"],
        expected=0,
    )
    expect_true(condition=alias.is_symlink())
    expect_equal(
        actual=target.read_text(),
        expected="def f():\n    x = 9\n    return x\n",
    )
