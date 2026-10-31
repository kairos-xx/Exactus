# Copyright (c) 2026
"""Behavioral tests for source-preserving string conversion."""

from ast import (
    Assign,
    Constant,
    Expr,
    FormattedValue,
    ImportFrom,
    dump,
    literal_eval,
    parse,
)
from collections.abc import Callable
from os import PathLike
from pathlib import Path
from runpy import run_path
from shutil import which
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import TYPE_CHECKING, Final, Never, cast, final

import pytest

from exactus.tests.common.support import Constant as StubConstant
from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_true,
    require_type,
)
from exactus.tools.lints import string_transform
from exactus.tools.lints.string_transform import (
    CallFormatOptions,
    ConversionResult,
    MultilineStrategy,
    SplitOptions,
    TransformOptions,
    apply,
    atomic_write,
    convert_strings,
    escape,
    flatten,
    implicit_tokens,
    insertion_offset,
    literal_parts,
    merge_dedent,
    offset,
    offsets,
    position,
    render,
    resolve_line_length,
    ruff_call,
    select,
    signature,
    split_strings,
    transform_strings,
    verified,
    with_dedent_import,
)

if TYPE_CHECKING:
    from exactus.tools.lints.string_transform import (
        SplitResult,
        TransformResult,
    )


@final
class Constants:
    """Group module-level constants.

    Attributes:
        line_length: Grouped module constant.
        explicit_width: Grouped module constant.
        discovered_width: Grouped module constant.
        configured_width: Grouped module constant.
        default_width: Grouped module constant.

    """

    line_length: Final[int] = 45
    explicit_width: Final[int] = 100
    discovered_width: Final[int] = 79
    configured_width: Final[int] = 67
    default_width: Final[int] = 88


def test_implicit() -> None:
    """Preserve embedded Python code and trailing newline."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "example.py"
        path.write_text(
            data=dedent(
                text=(
                    "    from pathlib import Path\n    from textwrap import in"
                    'dent\n    _ = Path("x").write_text(data=("def f():\\n" " '
                    '   return 42\\n"), encoding="utf-8")\n    '
                ),
            ),
            encoding="utf-8",
        )
        result: ConversionResult = convert_strings(file=path)
        expect_equal(actual=result.count, expected=1)
        expect_in(
            member="from textwrap import dedent, indent",
            container=result.source,
        )
        expect_in(member="dedent(text=", container=result.source)
        expect_equal(actual=convert_strings(file=path).count, expected=0)


def test_docstring() -> None:
    """Do not convert a module docstring."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "example.py"
        path.write_text(data='("hello\\n" "world\\n")\n', encoding="utf-8")
        expect_equal(actual=convert_strings(file=path).count, expected=0)


def test_explicit_and_fstrings() -> None:
    """Rewrite explicit and implicit concatenation preserving output."""
    for expression in (
        '"a\\n" + "b\\n"',
        '"a\\\\b\\n" + "c\\n"',
        '"a\\n" "b\\n"',
    ):
        with TemporaryDirectory() as folder:
            path: Path = Path(folder) / "sample.py"
            after_path: Path = Path(folder) / "after.py"
            path.write_text(data=f"value = {expression}\n", encoding="utf-8")
            result: ConversionResult = convert_strings(file=path, write=False)
            expect_equal(actual=result.count, expected=1)
            after_path.write_text(data=result.source, encoding="utf-8")
            namespace: dict[str, object] = {"name": "A", "age": 42}
            before: dict[str, object] = run_path(
                path_name=str(object=path),
                init_globals=namespace,
            )
            after: dict[str, object] = run_path(
                path_name=str(object=after_path),
                init_globals=namespace,
            )
            expect_equal(actual=after["value"], expected=before["value"])
            expect_equal(
                actual=convert_strings(file=path, dry_run=True).count,
                expected=1,
            )
    for expression in (
        'f"hello {name}\\n" f"age={age!r}\\n"',
        'f"hello {name}\\n" + f"age={age!r}\\n"',
        'f"value={value:{width}.{precision}f}\\n" + "end\\n"',
        'f"{{literal}} {value!r}\\n" + f"{value=}\\n"',
    ):
        with TemporaryDirectory() as folder:
            target: Path = Path(folder) / "sample.py"
            target.write_text(data=f"value = {expression}\n", encoding="utf-8")
            expect_equal(
                actual=convert_strings(file=target, write=False).count,
                expected=0,
            )


def test_complex_literals() -> None:
    """Check carriage returns, unusual quoting, and nested format specs."""
    expressions: tuple[str, ...] = (
        '"a\\rb\\n" + "c\\n"',
        '"a\\x00b\\n" + "c\\n"',
        "'one\"\"\"two\\n' + 'three\\n' ",
        '"first\\n" + "second\\n" + "third\\n"',
    )
    for expression in expressions:
        with TemporaryDirectory() as folder:
            path: Path = Path(folder) / "sample.py"
            after_path: Path = Path(folder) / "after.py"
            path.write_text(data=f"result = {expression}\n", encoding="utf-8")
            converted: ConversionResult = convert_strings(
                file=path,
                write=False,
            )
            after_path.write_text(data=converted.source, encoding="utf-8")
            namespace: dict[str, object] = {
                "value": 1.234,
                "width": 8,
                "precision": 2,
            }
            before: dict[str, object] = run_path(
                path_name=str(object=path),
                init_globals=namespace,
            )
            after: dict[str, object] = run_path(
                path_name=str(object=after_path),
                init_globals=namespace,
            )
            expect_equal(actual=after["result"], expected=before["result"])
            expect_equal(actual=converted.count, expected=1)


@pytest.mark.skipif(
    condition=which(cmd="ruff") is None,
    reason="Ruff executable not installed",
)
def test_fstring_call_formatting(tmp_path: Path) -> None:
    """Normalize a call inside an f-string through the Ruff formatter.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(data='a = f"b{c(d,e,f,g)}"\n', encoding="utf-8")
    result: ConversionResult = convert_strings(file=path, write=False)
    expect_in(member="c(d, e, f, g)", container=result.source)
    expect_equal(actual=result.count, expected=1)
    expect_false(
        condition=convert_strings(
            file=path,
            write=False,
            call_format=CallFormatOptions(enabled=False),
        ).changed,
    )
    path.write_text(data=result.source, encoding="utf-8")
    expect_false(condition=convert_strings(file=path, write=False).changed)


@pytest.mark.skipif(
    condition=which(cmd="ruff") is None,
    reason="Ruff executable not installed",
)
def test_fstring_nested_call_formatting(tmp_path: Path) -> None:
    """Keep nested calls inline while expanding the outer call.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "nested.py"
    path.write_text(
        data='a = f"{call(one,inner( 2,3 ),four):>10}"\n',
        encoding="utf-8",
    )
    result: ConversionResult = convert_strings(file=path, write=False)
    expect_in(member="inner(2, 3)", container=result.source)
    expect_equal(actual=result.count, expected=1)
    compile(source=result.source, filename=str(object=path), mode="exec")


def test_ast_helpers_and_rejections() -> None:
    """Cover flattening, signature, rendering, and rejection paths."""
    expect_equal(actual=offsets(lines=["abc\n", "xy"]), expected=[0, 4, 6])
    expect_equal(actual=position(offsets=[0, 4, 6], point=(2, 1)), expected=5)
    expect_none(value=flatten(node=parse(source='a + "b"', mode="eval").body))
    expect_none(
        value=flatten(node=parse(source='"a" + variable', mode="eval").body),
    )
    expect_none(value=flatten(node=parse(source="1", mode="eval").body))
    expect_true(
        condition=flatten(node=parse(source='f"{x}"', mode="eval").body)
        is not None,
    )
    text, expressions = signature(
        values=[
            Constant(value="a"),
            FormattedValue(
                value=parse(source="x", mode="eval").body,
                conversion=-1,
            ),
        ],
    )
    expect_equal(actual=text, expected="a\x010\x02")
    expect_equal(actual=len(expressions), expected=1)
    expect_none(
        value=escape(
            parts=[Constant(value=12)],
            is_fstring=False,
            quote='"""',
        ),
    )
    expect_false(
        condition=verified(
            candidate="invalid(",
            parts=[Constant(value="a")],
            is_fstring=False,
        ),
    )
    expect_false(
        condition=verified(
            candidate="12",
            parts=[Constant(value="a")],
            is_fstring=False,
        ),
    )
    expect_false(
        condition=verified(
            candidate='"b"',
            parts=[Constant(value="a")],
            is_fstring=False,
        ),
    )
    expect_false(
        condition=verified(
            candidate='"x"',
            parts=[Constant(value="a")],
            is_fstring=True,
        ),
    )
    expect_true(condition=render(parts=[Constant(value="a")]) is not None)
    expect_none(value=render(parts=[Constant(value=12)]))
    expect_equal(
        actual=select(patches=[(0, 5, "x"), (1, 3, "y"), (6, 8, "z")]),
        expected=[(0, 5, "x"), (6, 8, "z")],
    )
    expect_equal(
        actual=apply(source="abcdef", selected=[(1, 3, "X")]),
        expected="aXdef",
    )
    expect_false(
        condition=implicit_tokens(tokens=[], start=0, end=10, offsets=[0]),
    )


def test_import_variations() -> None:
    """Merge or insert ``dedent`` across existing textwrap imports."""
    expect_true(
        condition=with_dedent_import(
            result="from textwrap import dedent\nx = 1\n",
        ).startswith("from textwrap import dedent"),
    )
    expect_true(
        condition=with_dedent_import(
            result="from textwrap import indent as i\nx = 1\n",
        ).startswith("from textwrap import dedent\n"),
    )
    expect_true(
        condition=with_dedent_import(
            result="from textwrap import *\nx = 1\n",
        ).startswith("from textwrap import dedent\n"),
    )
    expect_true(
        condition=with_dedent_import(
            result='"""docs"""\nfrom __future__ import annotations\nx = 1\n',
        ).startswith(
            dedent(
                text=(
                    '    """docs"""\n    from __future__ import annotations\n'
                    "    from textwrap import dedent\n    "
                ),
            ),
        ),
    )
    expect_equal(
        actual=insertion_offset(
            updated=parse(source="x = 1"),
            updated_lines=["x = 1\n"],
        ),
        expected=0,
    )
    expect_in(
        member="dedent",
        container=merge_dedent(
            result="from textwrap import indent\n",
            compatible=require_type(
                value=parse(source="from textwrap import indent").body[0],
                kind=ImportFrom,
            ),
            offsets=[0, 28],
        ),
    )


def test_options_and_error_cases(tmp_path: Path) -> None:
    """Cover tree validation, dry-run, and formatting toggles.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "source.py"
    path.write_text(data='x = "a\\n" + "b\\n"\n', encoding="utf-8")
    original: str = path.read_text(encoding="utf-8")
    expect_equal(
        actual=convert_strings(
            file=path,
            tree=parse(source=original),
            write=False,
        ).count,
        expected=1,
    )
    expect_equal(actual=path.read_text(encoding="utf-8"), expected=original)
    expect_true(condition=convert_strings(file=path, dry_run=True).changed)
    expect_equal(actual=path.read_text(encoding="utf-8"), expected=original)
    path.write_text(data="x = (", encoding="utf-8")
    with pytest.raises(expected_exception=SyntaxError):
        convert_strings(file=path)
    path.write_text(data='x = "a\\n" + "b\\n"\n', encoding="utf-8")
    disabled: CallFormatOptions = CallFormatOptions(enabled=False)
    expect_true(
        condition=convert_strings(file=path, call_format=disabled).changed,
    )
    expect_false(
        condition=convert_strings(file=path, call_format=disabled).changed,
    )


def test_ruff_failure_paths(tmp_path: Path) -> None:
    """Return ``None`` or the staged call when Ruff fails or no-ops.

    Args:
        tmp_path: Per-test temporary directory.

    """
    fake: Path = tmp_path / "ruff"
    fake.write_text(data="#!/bin/sh\nexit 2\n", encoding="utf-8")
    fake.chmod(mode=493)
    expect_none(
        value=ruff_call(
            call="c(\n    a,\n    b\n)",
            executable=str(object=fake),
            line_length=88,
        ),
    )
    fake.write_text(data="#!/bin/sh\nexit 0\n", encoding="utf-8")
    expect_true(
        condition=ruff_call(
            call="c(\n    a,\n    b\n)",
            executable=str(object=fake),
            line_length=88,
        )
        is not None,
    )
    expect_true(
        condition=ruff_call(
            call="not_a_call",
            executable=str(object=fake),
            line_length=88,
        )
        is not None,
    )


def test_fstring_ruff_staging_with_fake(tmp_path: Path) -> None:
    """Stage multiline calls when the Ruff subprocess is a no-op.

    Args:
        tmp_path: Per-test temporary directory.

    """
    fake: Path = tmp_path / "ruff"
    fake.write_text(data="#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(mode=493)
    options: CallFormatOptions = CallFormatOptions(
        ruff_executable=str(object=fake),
    )
    path: Path = tmp_path / "source.py"
    for source, expected in (
        ('a = f"{call(a,b,c)}"\n', True),
        ('a = f"{call(a,b,c,d)}"\n', True),
        ('a = f"{call(a, inner(b,c), d)}"\n', True),
        ('a = f"{call(a,b)}"\n', False),
        ('a = f"{call(a,b,c):>10}"\n', True),
        ('a = f"{call(a,b,c)}" + "\\n"\n', True),
    ):
        path.write_text(data=source, encoding="utf-8")
        result: ConversionResult = convert_strings(
            file=path,
            write=False,
            call_format=options,
        )
        expect_equal(actual=result.changed, expected=expected)
        compile(source=result.source, filename=str(object=path), mode="exec")


def test_long_literal() -> None:
    """A long ordinary literal is split without changing its value."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        after_path: Path = Path(folder) / "after.py"
        path.write_text(
            data='a = "' + "verylong" * 12 + '"\n',
            encoding="utf-8",
        )
        result: SplitResult = split_strings(
            file=path,
            options=SplitOptions(max_line_size=Constants.line_length),
        )
        expect_equal(actual=result.count, expected=1)
        expect_true(
            condition=all(
                len(line) <= Constants.line_length
                for line in result.source.splitlines()
            ),
        )
        after_path.write_text(data=result.source, encoding="utf-8")
        namespace: dict[str, object] = run_path(
            path_name=str(object=after_path),
        )
        expect_equal(actual=namespace["a"], expected="verylong" * 12)
        expect_equal(
            actual=split_strings(
                file=path,
                options=SplitOptions(max_line_size=Constants.line_length),
            ).count,
            expected=0,
        )


def test_long_fstring() -> None:
    """An interpolated string is split without changing interpolation."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        after_path: Path = Path(folder) / "after.py"
        path.write_text(
            data='name = "Joe"\na = f"'
            + "verylong" * 10
            + "{name}"
            + "verylong" * 10
            + '"\n',
            encoding="utf-8",
        )
        result: SplitResult = split_strings(
            file=path,
            options=SplitOptions(max_line_size=50),
        )
        expect_equal(actual=result.count, expected=1)
        after_path.write_text(data=result.source, encoding="utf-8")
        namespace: dict[str, object] = run_path(
            path_name=str(object=after_path),
        )
        expect_equal(
            actual=namespace["a"],
            expected="verylong" * 10 + "Joe" + "verylong" * 10,
        )


def test_multiline_bytes_raw_and_docstrings() -> None:
    """Preserve exact literal values and module documentation."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        source: str = (
            '"""'
            + "doc" * 40
            + '"""\n'
            + 'a = """'
            + "z" * 60
            + "\n"
            + "ab\n" * 20
            + '"""\nb = b"'
            + "a" * 90
            + '"\nc = r"'
            + "xyz" * 30
            + '"\n'
        )
        path.write_text(data=source, encoding="utf-8")
        result: SplitResult = split_strings(
            file=path,
            tree=parse(source=source),
            dry_run=True,
            options=SplitOptions(max_line_size=Constants.line_length),
        )
        expect_true(condition=result.count > 1)
        expect_equal(actual=path.read_text(encoding="utf-8"), expected=source)
        first: Expr = require_type(
            value=parse(source=result.source).body[0],
            kind=Expr,
        )
        literal: Constant = require_type(value=first.value, kind=Constant)
        expect_equal(actual=literal.value, expected="doc" * 40)
        expect_true(
            condition=split_strings(
                file=path,
                write=False,
                options=SplitOptions(
                    max_line_size=Constants.line_length,
                    multiline_strategy="preserve",
                ),
            ).count
            >= 1,
        )
        expect_true(
            condition=split_strings(
                file=path,
                write=False,
                options=SplitOptions(
                    max_line_size=Constants.line_length,
                    split_bytes=False,
                    split_raw_strings=False,
                ),
            ).count
            >= 1,
        )


def test_rejections_and_settings() -> None:
    """Reject unsupported options."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        path.write_text(data='a = "' + "x" * 100 + '"\n', encoding="utf-8")
        with pytest.raises(expected_exception=ValueError, match="line_length"):
            split_strings(file=path, options=SplitOptions(max_line_size=10))
        with pytest.raises(
            expected_exception=ValueError,
            match="multiline strategy",
        ):
            split_strings(
                file=path,
                options=SplitOptions(
                    multiline_strategy=cast(
                        typ="MultilineStrategy",
                        val="bad",
                    ),
                ),
            )
        expect_true(
            condition=split_strings(
                file=path,
                write=False,
                options=SplitOptions(max_line_size=40),
            ).changed,
        )
        expect_true(
            condition=path.read_text(encoding="utf-8").startswith('a = "'),
        )


def test_nested_fstrings_and_debug_are_safe() -> None:
    """Unsafe f-string transformations must be rejected, never corrupted."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        source: str = (
            'value = 4\na = f"' + "a" * 70 + "{value=}" + "b" * 70 + '"\n'
        )
        path.write_text(data=source, encoding="utf-8")
        result: SplitResult = split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=42),
        )
        expect_equal(
            actual=dump(node=parse(source=source), include_attributes=False),
            expected=dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
        )


def test_unicode_escapes_and_crlf() -> None:
    """Handle Unicode and escaped controls without changing AST semantics."""
    with TemporaryDirectory() as folder:
        path: Path = Path(folder) / "sample.py"
        source: str = 'a = "' + "é\\r\\n\\x00" * 20 + '"\r\n'
        path.write_bytes(data=source.encode(encoding="utf-8"))
        result: SplitResult = split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=42),
        )
        expect_equal(
            actual=dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
            expected=dump(node=parse(source=source), include_attributes=False),
        )


def test_controls_and_error_paths(tmp_path: Path) -> None:
    """Exercise disabling switches, width constraints, and invalid sources.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(
        data='a = f"' + "a" * 100 + "{x}" + "b" * 100 + '"\n',
        encoding="utf-8",
    )
    expect_false(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(split_fstrings=False),
        ).changed,
    )
    expect_true(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=30),
        ).count
        >= 0,
    )
    path.write_text(data='a = b"' + "a" * 100 + '"\n', encoding="utf-8")
    expect_false(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(split_bytes=False),
        ).changed,
    )
    path.write_text(data='a = r"' + "a" * 100 + '"\n', encoding="utf-8")
    expect_false(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(split_raw_strings=False),
        ).changed,
    )
    path.write_text(data='a = "' + "a" * 100 + '"\n', encoding="utf-8")
    expect_true(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=30, verify_semantics=False),
        ).changed,
    )
    expect_true(
        condition=split_strings(
            file=path,
            tree=parse(source=path.read_text(encoding="utf-8")),
            write=False,
        ).changed,
    )
    path.write_text(data="a = (\n", encoding="utf-8")
    with pytest.raises(expected_exception=SyntaxError):
        split_strings(file=path)


def test_literal_helpers_and_atomic_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify literal splitting, offsets, and atomic cleanup.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    expect_equal(
        actual=literal_parts(value="abcdef", width=4),
        expected=["'ab'", "'cd'", "'ef'"],
    )
    expect_none(value=literal_parts(value="a", width=2))
    expect_true(condition=literal_parts(value=b"abcdef", width=5) is not None)
    expect_equal(
        actual=offset(lines=["éx\n"], starts=[0], line=1, column=2),
        expected=1,
    )
    path: Path = tmp_path / "file.py"
    path.write_text(data="before", encoding="utf-8")

    def fail_replace(self: Path, target: str | PathLike[str]) -> Never:
        """Simulate an atomic replacement failure.

        Args:
            self: Temporary file being relocated.
            target: Unused destination path.

        Raises:
            OSError: Always, to emulate a failed replacement.

        """
        del self, target
        msg: str = "replacement failed"
        raise OSError(msg)

    patch: pytest.MonkeyPatch
    with monkeypatch.context() as patch:
        patch.setattr(target=Path, name="replace", value=fail_replace)
        with pytest.raises(
            expected_exception=OSError,
            match="replacement failed",
        ):
            atomic_write(path=path, content="after")
    expect_equal(actual=path.read_text(encoding="utf-8"), expected="before")
    expect_equal(
        actual=sorted(item.name for item in tmp_path.iterdir()),
        expected=["file.py"],
    )


def test_varied_literal_boundaries(tmp_path: Path) -> None:
    """Check safe skipping for unsplittable and multiline expressions.

    Args:
        tmp_path: Per-test temporary directory.

    """
    cases: list[str] = [
        'a = "' + "\\U0001f600" * 25 + '"\n',
        'a = "' + "\\\\" * 55 + '"\n',
        'a = "' + "x" * 120 + '"  # important\n',
        'a = f"' + "x" * 80 + "{value!r:>20}" + "y" * 80 + '"\n',
        'a = f"'
        + "x" * 80
        + "{value:{width}.{precision}f}"
        + "y" * 80
        + '"\n',
        'a = f"' + "x" * 80 + "{value=}" + "y" * 80 + '"\n',
        'a = """' + "x" * 120 + "\n" + "y" * 120 + '"""\n',
        'a = "' + "é" * 100 + '"\n',
    ]
    path: Path = tmp_path / "sample.py"
    for source in cases:
        path.write_text(data=source, encoding="utf-8")
        result: SplitResult = split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=Constants.line_length),
        )
        expect_equal(
            actual=dump(node=parse(source=source), include_attributes=False),
            expected=dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
        )
        if result.changed:
            path.write_text(data=result.source, encoding="utf-8")
            expect_false(
                condition=split_strings(
                    file=path,
                    write=False,
                    options=SplitOptions(max_line_size=Constants.line_length),
                ).changed,
            )


def test_nested_and_comment_preservation(tmp_path: Path) -> None:
    """Preserve nested scope docstrings and adjacent comments.

    Args:
        tmp_path: Per-test temporary directory.

    """
    source: str = (
        'class C:\n    """'
        + "d" * 120
        + '"""\n    def method(self):\n        """'
        + "e" * 120
        + '"""\n        value = "'
        + "z" * 120
        + '"\n        return value\n'
    )
    path: Path = tmp_path / "sample.py"
    path.write_text(data=source, encoding="utf-8")
    result: SplitResult = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=55),
    )
    expect_equal(actual=result.count, expected=1)
    expect_equal(
        actual=dump(node=parse(source=source), include_attributes=False),
        expected=dump(
            node=parse(source=result.source),
            include_attributes=False,
        ),
    )
    expect_in(member='"""' + "d" * 120 + '"""', container=result.source)
    expect_in(member='"""' + "e" * 120 + '"""', container=result.source)


def test_more_skip_and_conversion_branches(tmp_path: Path) -> None:
    """Cover insufficient budgets, docstrings, and interpolations.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    samples: list[str] = [
        'a = """' + "a" * 110 + '"""\n',
        'a = f"' + "a" * 110 + "{value!r}" + "b" * 110 + '"\n',
        'a = f"' + "a" * 110 + "{value:{width}}" + "b" * 110 + '"\n',
        'a = f"' + "a" * 110 + "{value=}" + "b" * 110 + '"\n',
        'a = b"' + "a" * 110 + '"\n',
        'a = "' + "\\n" * 110 + '"\n',
        'a = "' + "a" * 110 + '"\n',
    ]
    strategies: tuple[MultilineStrategy, ...] = ("preserve", "smart", "split")
    for source in samples:
        path.write_text(data=source, encoding="utf-8")
        for strategy in strategies:
            result: SplitResult = split_strings(
                file=path,
                write=False,
                options=SplitOptions(
                    max_line_size=25,
                    multiline_strategy=strategy,
                    format_interpolations=True,
                    preserve_docstrings=False,
                ),
            )
            expect_equal(
                actual=dump(
                    node=parse(source=result.source),
                    include_attributes=False,
                ),
                expected=dump(
                    node=parse(source=source),
                    include_attributes=False,
                ),
            )
    path.write_text(data='a = "' + "a" * 110 + '"\n', encoding="utf-8")
    expect_true(
        condition=split_strings(
            file=path,
            write=True,
            options=SplitOptions(max_line_size=25),
        ).changed,
    )
    expect_false(
        condition=split_strings(
            file=path,
            write=True,
            options=SplitOptions(max_line_size=25),
        ).changed,
    )


def test_indented_budget_and_empty_literals(tmp_path: Path) -> None:
    """Reject transformations when indentation consumes the line budget.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    source: str = "def f():\n" + " " * 24 + 'a = "' + "a" * 100 + '"\n'
    path.write_text(data=source, encoding="utf-8")
    result: SplitResult = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=25),
    )
    expect_equal(
        actual=dump(
            node=parse(source=result.source),
            include_attributes=False,
        ),
        expected=dump(node=parse(source=source), include_attributes=False),
    )
    expect_true(condition=bool(result.skipped))


def test_rejected_candidate_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject malformed generated fragments and tokenization failures.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "sample.py"
    source: str = 'a = "' + "a" * 120 + '"\n'
    path.write_text(data=source, encoding="utf-8")
    original_parts: Callable[[str | bytes, int], list[str] | None] = (
        string_transform.literal_parts
    )
    for fragments in (
        ["'broken", "'more'"],
        ["'a'", "'b'"],
        ["'a'" * 100, "'b'"],
    ):
        monkeypatch.setattr(
            target=string_transform,
            name="literal_parts",
            value=StubConstant(value=fragments),
        )
        result: SplitResult = split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=40),
        )
        expect_equal(
            actual=dump(
                node=parse(source=result.source),
                include_attributes=False,
            ),
            expected=dump(node=parse(source=source), include_attributes=False),
        )
    monkeypatch.setattr(
        target=string_transform,
        name="literal_parts",
        value=original_parts,
    )

    def bad_tokens(readline: Callable[[], str]) -> Never:
        """Simulate a tokenization failure.

        Args:
            readline: Unused line reader for the tokenizer.

        Raises:
            TokenError: Always, to emulate a malformed source span.

        """
        del readline
        msg: str = "bad tokens"
        raise string_transform.TokenError(msg, (1, 0))

    monkeypatch.setattr(
        target=string_transform,
        name="generate_tokens",
        value=bad_tokens,
    )
    result = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=40),
    )
    expect_true(condition=bool(result.skipped))
    expect_false(condition=result.changed)


def test_write_failure_and_source_preservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify write failures leave original bytes unchanged.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "sample.py"
    source: str = 'a = "' + "a" * 120 + '"\r\n'
    path.write_bytes(data=source.encode(encoding="utf-8"))

    def fail_write(path: Path, content: str | bytes) -> Never:
        """Simulate a write failure.

        Args:
            path: Unused destination path.
            content: Unused payload.

        Raises:
            OSError: Always, to emulate a failed write.

        """
        del path, content
        msg: str = "no disk"
        raise OSError(msg)

    monkeypatch.setattr(
        target=string_transform,
        name="atomic_write",
        value=fail_write,
    )
    with pytest.raises(expected_exception=OSError, match="no disk"):
        split_strings(file=path, options=SplitOptions(max_line_size=40))
    expect_equal(
        actual=path.read_bytes(),
        expected=source.encode(encoding="utf-8"),
    )


def test_format_interpolation_and_idempotence(tmp_path: Path) -> None:
    """Expand long f-string calls without changing the module AST.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    source: str = 'a = f"prefix{func(first, second, third, fourth)}suffix"\n'
    path.write_text(data=source, encoding="utf-8")
    result: SplitResult = split_strings(
        file=path,
        options=SplitOptions(max_line_size=30, format_interpolations=True),
    )
    expect_equal(actual=result.count, expected=1)
    expect_in(member="func(\n", container=result.source)
    expect_equal(
        actual=dump(
            node=parse(source=result.source),
            include_attributes=False,
        ),
        expected=dump(node=parse(source=source), include_attributes=False),
    )
    expect_equal(
        actual=split_strings(
            file=path,
            options=SplitOptions(max_line_size=30, format_interpolations=True),
        ).count,
        expected=0,
    )


def test_source_encoding_and_crlf_roundtrip(tmp_path: Path) -> None:
    """Respect declared legacy encodings and CRLF on disk.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    source: str = '# coding: latin-1\r\na = "' + "é" * 90 + '"\r\n'
    path.write_bytes(data=source.encode(encoding="latin-1"))
    result: SplitResult = split_strings(
        file=path,
        options=SplitOptions(max_line_size=40),
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=path.read_bytes().decode(encoding="latin-1"),
        expected=result.source,
    )
    expect_in(member="\r\n", container=result.source)
    statement: Assign = require_type(
        value=parse(source=result.source).body[0],
        kind=Assign,
    )
    expect_equal(
        actual=literal_eval(node_or_string=statement.value),
        expected="é" * 90,
    )


def test_interpolation_rejection(tmp_path: Path) -> None:
    """Report indivisible oversized interpolation arguments.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    source: str = 'a = f"{func(' + "a" * 75 + ', other)}"\n'
    path.write_text(data=source, encoding="utf-8")
    result: SplitResult = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=30, format_interpolations=True),
    )
    expect_false(condition=result.changed)
    expect_true(
        condition=any(
            "argument exceeds width" in item.reason for item in result.skipped
        ),
    )


def test_interpolation_keyword_and_single_argument(tmp_path: Path) -> None:
    """Cover keyword expansion and conservative single-argument rejection.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(
        data='a = f"prefix{func(first=alpha, second=beta, **extra)}suffix"\n',
        encoding="utf-8",
    )
    result: SplitResult = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=35, format_interpolations=True),
    )
    expect_true(condition=result.changed)
    expect_in(member="**extra,", container=result.source)
    path.write_text(
        data='a = f"prefix{func(' + "a" * 50 + ')}suffix"\n',
        encoding="utf-8",
    )
    result = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=30, format_interpolations=True),
    )
    expect_true(
        condition=any(
            "cannot be expanded safely" in item.reason
            for item in result.skipped
        ),
    )


def test_interpolation_comment_protection(tmp_path: Path) -> None:
    """Do not rewrite interpolation text that might contain comments.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(
        data='a = f"prefix{func(first="#", second=other)}suffix"\n',
        encoding="utf-8",
    )
    result: SplitResult = split_strings(
        file=path,
        write=False,
        options=SplitOptions(max_line_size=30, format_interpolations=True),
    )
    expect_true(
        condition=any(
            "comment-sensitive" in item.reason for item in result.skipped
        ),
    )


def test_interpolation_already_short_and_already_multiline(
    tmp_path: Path,
) -> None:
    """Leave fitting and previously expanded calls unchanged.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "sample.py"
    path.write_text(data='a = f"{func(first, second)}"\n', encoding="utf-8")
    expect_false(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=50, format_interpolations=True),
        ).changed,
    )
    path.write_text(
        data='a = f"{func(\n    first,\n    second,\n)}"\n',
        encoding="utf-8",
    )
    expect_false(
        condition=split_strings(
            file=path,
            write=False,
            options=SplitOptions(max_line_size=30, format_interpolations=True),
        ).changed,
    )


def test_combined_transform(tmp_path: Path) -> None:
    """Combine dedenting and splitting without modifying the source twice.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "combined.py"
    source: str = 'a = "hello\\n" + "world\\n"\nb = "' + "x" * 95 + '"\n'
    path.write_text(data=source, encoding="utf-8")
    result: TransformResult = transform_strings(
        file=path,
        options=TransformOptions(max_line_size=55),
    )
    expect_true(condition=result.changed)
    expect_in(member="dedent(text=", container=result.source)
    expect_in(member="b = (", container=result.source)
    expect_false(
        condition=transform_strings(
            file=path,
            options=TransformOptions(max_line_size=55),
        ).changed,
    )


def test_combined_dry_run(tmp_path: Path) -> None:
    """Dry runs preserve original bytes while returning transformed source.

    Args:
        tmp_path: Per-test temporary directory.

    """
    path: Path = tmp_path / "combined.py"
    source: str = 'a = "first\\n" + "second\\n"\n'
    path.write_text(data=source, encoding="utf-8")
    result: TransformResult = transform_strings(file=path, dry_run=True)
    expect_true(condition=result.changed)
    expect_equal(actual=path.read_text(encoding="utf-8"), expected=source)


def test_ruff_line_length_discovery(tmp_path: Path) -> None:
    """Use Ruff's resolved formatter setting and forward CLI overrides.

    Args:
        tmp_path: Per-test temporary directory.

    """
    target: Path = tmp_path / "sample.py"
    target.write_text(data='value = "hello"\n', encoding="utf-8")
    fake: Path = tmp_path / "ruff"
    fake.write_text(
        data=dedent(
            text=(
                "    #!/usr/bin/env python3\n    import sys\n    if '--show-se"
                "ttings' not in sys.argv: sys.exit(2)\n    if '--config' in sy"
                "s.argv: print('formatter.line_width = 67')\n    else: print('"
                "formatter.line_width = 79')\n    "
            ),
        ),
        encoding="utf-8",
    )
    fake.chmod(mode=493)
    expect_equal(
        actual=resolve_line_length(
            file=target,
            ruff_executable=str(object=fake),
        ),
        expected=Constants.discovered_width,
    )
    expect_equal(
        actual=resolve_line_length(
            file=target,
            ruff_executable=str(object=fake),
            ruff_args=("--config", "line-length=67"),
        ),
        expected=Constants.configured_width,
    )
    expect_equal(
        actual=resolve_line_length(
            file=target,
            line_length=Constants.explicit_width,
        ),
        expected=Constants.explicit_width,
    )
    expect_false(
        condition=split_strings(
            file=target,
            write=False,
            options=SplitOptions(ruff_executable=str(object=fake)),
        ).changed,
    )
    expect_false(
        condition=transform_strings(
            file=target,
            write=False,
            options=TransformOptions(line_length=81),
        ).changed,
    )
    expect_false(
        condition=transform_strings(
            file=target,
            write=False,
            options=TransformOptions(max_line_size=81),
        ).changed,
    )
    with pytest.raises(expected_exception=ValueError, match="line_length"):
        resolve_line_length(file=target, line_length=0)
    fake.write_text(data="#!/bin/sh\nexit 2\n", encoding="utf-8")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="resolution failed",
    ):
        resolve_line_length(file=target, ruff_executable=str(object=fake))
    fake.write_text(data="#!/bin/sh\necho no-settings\n", encoding="utf-8")
    with pytest.raises(
        expected_exception=RuntimeError,
        match="formatter.line_width",
    ):
        resolve_line_length(file=target, ruff_executable=str(object=fake))


def test_ruff_unavailable_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use Ruff's default only when its executable cannot be discovered.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(
        target=string_transform,
        name="which",
        value=StubConstant(value=None),
    )
    expect_equal(
        actual=string_transform.resolve_line_length(file=tmp_path / "x.py"),
        expected=Constants.default_width,
    )
