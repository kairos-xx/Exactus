# Copyright (c) 2026
"""The lints long-line repair keeps behavior and converges to a fixpoint."""

from __future__ import annotations

from ast import dump, parse
from functools import partial
from io import StringIO
from json import dumps
from pathlib import Path
from stat import S_IMODE
from subprocess import CompletedProcess
from sys import executable
from tokenize import (
    COMMENT,
    DEDENT,
    ENCODING,
    ENDMARKER,
    FSTRING_END,
    FSTRING_START,
    INDENT,
    NEWLINE,
    NL,
    STRING,
    TokenInfo,
    generate_tokens,
)
from typing import Final, NoReturn, final

import pytest

from exactus.tests.common.support import (
    Constant,
    expect_equal,
    expect_false,
    expect_in,
    expect_not_equal,
    expect_not_in,
    expect_true,
    private_call,
    require_type,
)
from exactus.tools.lints import long_lines as long_lines_module
from exactus.tools.lints.long_lines import (
    BatchResult,
    LongLineFixer,
    LongLineRepair,
    LongLinesAPI,
    RepairSummary,
    Result,
    Settings,
    TextResult,
)


@final
class Constants:
    """Group module-level constants.

    Attributes:
        docstring_width: Grouped module constant.
        hook_width: Grouped module constant.
        long_value: Grouped module constant.
        nl: Grouped module constant.
        repair_sources: Grouped module constant.
        concat_sources: Grouped module constant.

    """

    docstring_width: Final[int] = 70
    hook_width: Final[int] = 50
    long_value: Final[str] = 'value = "' + "word " * 30 + '"\n'
    nl: Final[str] = "\n"
    repair_sources: Final[tuple[str, ...]] = (
        'value = "' + "alpha beta gamma " * 5 + '"\n',
        'value = """' + "alpha beta gamma " * 5 + '\nsecond"""\n',
        nl.join(
            (
                (
                    "result = first.really_long_attribute.second"
                    "_method().third.fourth()"
                ),
                "",
            ),
        ),
        nl.join(
            (
                "if first_condition and second_condition and third_condition:",
                "    x = 1",
                "",
            ),
        ),
        "from package.long_name.subpackage.other_name import first, second\n",
        nl.join(
            (
                (
                    "for value in some_really_long_iterable_name_that_exceeds"
                    "_limit:"
                ),
                "    pass",
                "",
            ),
        ),
        nl.join(
            (
                (
                    "with first_context(), second_context(), third_context"
                    "_manager():"
                ),
                "    pass",
                "",
            ),
        ),
        "a = 1; b = 2; c = 3; d = 4; e = 5; f = 6; g = 7; h = 8; i = 9\n",
        "value: dict[str, tuple[int, str, bytes, float, complex, bool]]\n",
        nl.join(
            (
                "@decorator_with_a_very_long_name(first_argument, second)",
                "def f():",
                "    pass",
                "",
            ),
        ),
        nl.join(
            (
                "match value:",
                "    case x if first_condition_name and second_name:",
                "        pass",
                "",
            ),
        ),
        nl.join(
            (
                (
                    'value = f"{first} some static text that is quite long '
                    '{second} more"'
                ),
                "",
            ),
        ),
        'value = b"""' + "abcdefghij" * 10 + '"""\n',
        "value = first_value + second_value + third_value + fourth_value\n",
    )
    concat_sources: Final[tuple[str, ...]] = (
        'value = "' + "alpha beta gamma " * 5 + '"\n',
        'value = """' + "alpha beta gamma " * 5 + '\nsecond"""\n',
        'value = b"""' + "abcdefghij" * 10 + '"""\n',
        nl.join(
            (
                (
                    'value = f"{first} some static text that is quite long '
                    '{second} more"'
                ),
                "",
            ),
        ),
        'result = some_function(argument_name="""'
        + "alpha beta gamma " * 5
        + '\nsecond""", other=flag)\n',
        nl.join(
            (
                (
                    'result = some_function(argument_name=f"{first} some '
                    'static text that is quite long {second} more", '
                    "other=flag)"
                ),
                "",
            ),
        ),
    )


def _offline(**arguments: object) -> NoReturn:
    """Stand in for a Ruff launcher that is not installed.

    Args:
        **arguments: Ignored subprocess arguments.

    Raises:
        FileNotFoundError: Always.

    """
    del arguments
    raise FileNotFoundError


def _no_ruff(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every Ruff subprocess of the module fail as not installed.

    Args:
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.setattr(target=long_lines_module, name="run", value=_offline)


def _fixer(*, width: int = 40) -> LongLineFixer:
    """Build a deterministic fixer that never invokes Ruff.

    Args:
        width: Maximum physical line width.

    Returns:
        A fixer with Ruff disabled.

    """
    return LongLineFixer(settings=Settings(line_length=width, run_ruff=False))


def _same_ast(*, before: str, after: str) -> bool:
    """Compare two sources by AST, ignoring locations.

    Args:
        before: Original source.
        after: Candidate source.

    Returns:
        Whether both parse to the same tree.

    """
    return dump(node=parse(source=before), include_attributes=False) == dump(
        node=parse(source=after),
        include_attributes=False,
    )


def _implicit_concat_groups(
    *,
    source: str,
) -> tuple[
    tuple[TokenInfo | None, TokenInfo, TokenInfo, TokenInfo | None],
    ...,
]:
    """Return every run of implicitly concatenated string literals.

    Adjacent literals have nothing but whitespace between them, so a group
    is a maximal run of consecutive complete literals — one STRING token
    each, or one FSTRING_START…FSTRING_END span — in the token stream.
    Every result is ``(before, first, last, after)``: the tokens framing
    the group plus its first and last literal boundary tokens.

    Args:
        source: Python source to tokenize.

    Returns:
        One entry per implicit-concatenation group.

    """
    trivia: frozenset[int] = frozenset(
        {COMMENT, DEDENT, ENCODING, ENDMARKER, INDENT, NEWLINE, NL},
    )
    stream: list[TokenInfo] = [
        token
        for token in generate_tokens(
            readline=StringIO(initial_value=source).readline,
        )
        if token.type not in trivia
    ]
    units: list[tuple[int, int]] = []
    depth: int = 0
    start: int = -1
    for index, token in enumerate(iterable=stream):
        if token.type == FSTRING_START:
            if depth == 0:
                start = index
            depth += 1
        elif token.type == FSTRING_END:
            depth -= 1
            if depth == 0:
                units.append((start, index))
        elif token.type == STRING and depth == 0:
            units.append((index, index))
    groups: list[
        tuple[TokenInfo | None, TokenInfo, TokenInfo, TokenInfo | None]
    ] = []
    index: int = 0
    while index < len(units):
        first: int = index
        while (
            index + 1 < len(units)
            and units[index + 1][0] == units[index][1] + 1
        ):
            index += 1
        if index > first:
            start_index: int = units[first][0]
            end_index: int = units[index][1]
            groups.append(
                (
                    stream[start_index - 1] if start_index > 0 else None,
                    stream[start_index],
                    stream[end_index],
                    stream[end_index + 1]
                    if end_index + 1 < len(stream)
                    else None,
                ),
            )
        index += 1
    return tuple(groups)


@pytest.mark.parametrize("source", Constants.repair_sources)
def test_every_repair_family_preserves_the_ast(source: str) -> None:
    """Each repair rewrites a long line without changing the AST.

    Args:
        source: Source with one over-long construct.

    """
    result: TextResult = _fixer(width=40).transform_text(source=source)
    expect_true(condition=result.changed)
    expect_true(condition=_same_ast(before=source, after=result.source))
    again: TextResult = _fixer(width=40).transform_text(source=result.source)
    expect_equal(actual=again.source, expected=result.source)


def test_trailing_comment_is_hoisted_above_the_statement() -> None:
    """A comment that makes a line too long moves above its statement."""
    source: str = "value = compute(argument)  # " + "explain " * 6 + "\n"
    result: TextResult = _fixer(width=50).transform_text(source=source)
    first: str = result.source.splitlines()[0]
    expect_true(condition=first.startswith("# explain"))
    expect_in(member="value = compute(argument)", container=result.source)
    expect_true(condition=_same_ast(before=source, after=result.source))


def test_directive_comments_stay_on_their_line() -> None:
    """Pragma comments are never hoisted or wrapped."""
    source: str = (
        f"value = compute(argument)  # {'type'}: ignore[arg-type]  "
    ) + "x" * 40
    result: TextResult = _fixer(width=40).transform_text(source=source + "\n")
    expect_in(member=f"# {'type'}: ignore[arg-type]", container=result.source)
    expect_equal(actual=len(result.source.splitlines()), expected=1)


def test_standalone_comment_wraps() -> None:
    """A long standalone comment becomes several comment lines."""
    source: str = "# " + "many words " * 10 + "\n"
    result: TextResult = _fixer(width=40).transform_text(source=source)
    expect_true(condition=len(result.source.splitlines()) > 1)
    expect_true(
        condition=all(
            line.startswith("# ") for line in result.source.splitlines()
        ),
    )


def test_docstring_reflow_keeps_summary_and_fields() -> None:
    """Docstring prose wraps while the summary line stays whole."""
    source: str = Constants.nl.join(
        (
            "def sample(argument: str) -> str:",
            '    """Keep this first sentence intact even though it is long.',
            "",
            "    Args:",
            (
                "        argument: A deliberately long description that "
                "wraps without changing executable code at all."
            ),
            "",
            '    """',
            "    return argument",
            "",
        ),
    )
    result: TextResult = _fixer(
        width=Constants.docstring_width,
    ).transform_text(source=source)
    expect_in(
        member="Keep this first sentence intact even though it is long.",
        container=result.source,
    )
    expect_true(
        condition=all(
            len(line) <= Constants.docstring_width
            for line in result.source.splitlines()
        ),
    )
    expect_equal(actual=result.unresolved_lines, expected=())


def test_fmt_off_regions_are_protected() -> None:
    """Lines inside a fmt-off region are reported, never rewritten."""
    source: str = (
        "# fmt: off\n" + ("x = " + "1 + " * 12 + "1\n") + "# fmt: on\n"
    )
    result: TextResult = _fixer(width=40).transform_text(source=source)
    expect_equal(actual=result.source, expected=source)
    expect_equal(actual=result.protected_lines, expected=(2,))
    expect_equal(actual=result.unresolved_lines, expected=())
    unprotected: TextResult = LongLineFixer(
        settings=Settings(
            line_length=40,
            run_ruff=False,
            respect_fmt_off=False,
        ),
    ).transform_text(source=source)
    expect_not_equal(actual=unprotected.source, expected=source)


def test_unbreakable_line_is_reported() -> None:
    """A single long name cannot be split and is classified as unfixable."""
    source: str = "x = " + "a" * 60 + " + b\n"
    result: TextResult = _fixer(width=40).transform_text(source=source)
    expect_true(condition=bool(result.unresolved_lines))
    expect_equal(
        actual=result.unfixable_lines,
        expected=result.unresolved_lines,
    )


def test_ruff_exempt_lines_are_not_reported() -> None:
    """Single words, URL endings and trailing pragmas are exempt as in Ruff."""
    source: str = (
        "# https://example.com/"
        + "p" * 60
        + (f"\nx = 1  # {'no'}qa: E501 ")
        + "y" * 60
        + "\nword_"
        + "w" * 60
        + "\n"
    )
    result: TextResult = _fixer(width=40).transform_text(source=source)
    expect_equal(actual=result.unresolved_lines, expected=())


def test_diff_is_attached_when_requested() -> None:
    """A changed result carries a unified diff naming the source."""
    result: TextResult = LongLinesAPI.transform(
        source=Constants.long_value,
        settings=Settings(line_length=79, run_ruff=False, show_diff=True),
    )
    expect_in(member="--- stdin.py", container=result.diff)
    expect_in(member="+++ stdin.py (fixed)", container=result.diff)


def test_check_only_never_writes(tmp_path: Path) -> None:
    """A check-only run reports the change without touching the file.

    Args:
        tmp_path: Per-test directory.

    """
    path: Path = tmp_path / "a.py"
    _ = path.write_text(data=Constants.long_value, encoding="utf-8")
    result: Result = LongLinesAPI.fix_file(
        path=path,
        settings=Settings(line_length=50, run_ruff=False, check_only=True),
    )
    expect_true(condition=result.changed)
    expect_equal(
        actual=path.read_text(encoding="utf-8"),
        expected=Constants.long_value,
    )


def test_commit_preserves_mode_and_writes_backup(tmp_path: Path) -> None:
    """The atomic write keeps permissions and saves the original bytes.

    Args:
        tmp_path: Per-test directory.

    """
    path: Path = tmp_path / "a.py"
    _ = path.write_text(data=Constants.long_value, encoding="utf-8")
    path.chmod(mode=481)
    _ = LongLinesAPI.fix_file(
        path=path,
        settings=Settings(line_length=50, run_ruff=False, backup=True),
    )
    backup: Path = path.with_suffix(suffix=".py.bak")
    expect_equal(
        actual=backup.read_text(encoding="utf-8"),
        expected=Constants.long_value,
    )
    expect_equal(actual=S_IMODE(path.stat().st_mode), expected=481)
    expect_equal(actual=S_IMODE(backup.stat().st_mode), expected=481)
    expect_false(condition=any(path.parent.glob(pattern=".*.tmp")))


def test_encoding_cookie_is_preserved(tmp_path: Path) -> None:
    """A latin-1 source is read and written back in latin-1.

    Args:
        tmp_path: Per-test directory.

    """
    path: Path = tmp_path / "a.py"
    source: str = "# -*- coding: latin-1 -*-\n" + Constants.long_value.replace(
        "w",
        "á",
        count=1,
    )
    _ = path.write_bytes(data=source.encode(encoding="latin-1"))
    _ = LongLinesAPI.fix_file(
        path=path,
        settings=Settings(line_length=50, run_ruff=False),
    )
    written: bytes = path.read_bytes()
    expect_true(condition=written.startswith(b"# -*- coding: latin-1 -*-"))
    expect_in(member="á", container=written.decode(encoding="latin-1"))


def test_clean_crlf_file_is_untouched(tmp_path: Path) -> None:
    """A file without long lines keeps its exact bytes.

    Args:
        tmp_path: Per-test directory.

    """
    path: Path = tmp_path / "a.py"
    original: bytes = b"value = 1\r\nother = 2\r\n"
    _ = path.write_bytes(data=original)
    result: Result = LongLinesAPI.fix_file(
        path=path,
        settings=Settings(run_ruff=False),
    )
    expect_false(condition=result.changed)
    expect_equal(actual=path.read_bytes(), expected=original)


def test_parse_ruff_report_keeps_only_e501_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only E501 diagnostics with a usable row are kept per file.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    monkeypatch.chdir(path=tmp_path)
    report: Path = tmp_path / "ruff.json"
    entries: list[object] = [
        {"code": "F401", "filename": "a.py", "location": {"row": 1}},
        {"code": "E501", "filename": "a.py", "location": {"row": 2}},
        {"code": "E501", "filename": "a.py", "location": {"row": 2}},
        {"code": "E501", "filename": "b.py", "location": {"row": 3}},
        {"code": "E501", "filename": 4, "location": {"row": 3}},
        {"code": "E501", "filename": "c.py", "location": {"row": 0}},
        "not a diagnostic",
    ]
    _ = report.write_text(data=dumps(obj=entries), encoding="utf-8")
    expect_equal(
        actual=LongLinesAPI.parse_ruff_report(path=report),
        expected={
            (tmp_path / "a.py").resolve(): frozenset({2}),
            (tmp_path / "b.py").resolve(): frozenset({3}),
        },
    )


def test_parse_ruff_report_rejects_malformed_json(tmp_path: Path) -> None:
    """Invalid JSON and non-array JSON raise distinct documented errors.

    Args:
        tmp_path: Per-test directory.

    """
    report: Path = tmp_path / "ruff.json"
    _ = report.write_text(data="{", encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match="Invalid Ruff JSON report",
    ):
        _ = LongLinesAPI.parse_ruff_report(path=report)
    _ = report.write_text(data="{}", encoding="utf-8")
    with pytest.raises(expected_exception=TypeError, match="diagnostic array"):
        _ = LongLinesAPI.parse_ruff_report(path=report)


def test_discover_skips_hidden_and_build_directories(tmp_path: Path) -> None:
    """Directory discovery is sorted and excludes generated trees.

    Args:
        tmp_path: Per-test directory.

    """
    good: Path = tmp_path / "a.py"
    _ = good.write_text(data="x = 1\n", encoding="utf-8")
    for name in (".hidden", "build", "exactus/bundle"):
        folder: Path = tmp_path / name
        folder.mkdir(parents=True)
        _ = (folder / "skip.py").write_text(data="x = 1\n", encoding="utf-8")
    expect_equal(
        actual=LongLinesAPI.discover(paths=(tmp_path,)),
        expected=(good,),
    )
    expect_equal(actual=LongLinesAPI.discover(paths=(good,)), expected=(good,))


def test_line_length_falls_back_to_pyproject(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without Ruff the nearest pyproject supplies the width.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    _no_ruff(monkeypatch=monkeypatch)
    package: Path = tmp_path / "pkg"
    package.mkdir()
    path: Path = package / "a.py"
    _ = path.write_text(data="x = 1\n", encoding="utf-8")
    expect_equal(
        actual=LongLinesAPI.resolve_line_length(file_path=path),
        expected=79,
    )
    config: Path = tmp_path / "pyproject.toml"
    _ = config.write_text(
        data="[tool.ruff]\nline-length = 101\n",
        encoding="utf-8",
    )
    expect_equal(
        actual=LongLinesAPI.find_pyproject(file_path=path),
        expected=config,
    )
    expect_equal(
        actual=LongLinesAPI.resolve_line_length(file_path=path),
        expected=101,
    )
    _ = config.write_text(
        data="[tool.ruff.format]\nline-width = 93\n",
        encoding="utf-8",
    )
    expect_equal(
        actual=LongLinesAPI.resolve_line_length(file_path=path),
        expected=93,
    )
    _ = config.write_text(data="[tool]\nruff = 1\n", encoding="utf-8")
    expect_equal(
        actual=LongLinesAPI.resolve_line_length(file_path=path),
        expected=79,
    )


def test_line_length_reads_ruff_show_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The width is parsed from Ruff's resolved settings output.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "a.py"
    _ = path.write_text(data="x = 1\n", encoding="utf-8")
    output: str = "linter.line_length = 88\nlinter.other = 120\n"
    monkeypatch.setattr(
        target=long_lines_module,
        name="run",
        value=Constant(
            value=CompletedProcess(
                args=["ruff"],
                returncode=0,
                stdout=output,
                stderr="",
            ),
        ),
    )
    expect_equal(
        actual=LongLinesAPI.resolve_line_length(file_path=path),
        expected=88,
    )


def test_ruff_e501_rows_come_from_the_ruff_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows Ruff reports for a file seed the repair; failures yield none.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    path: Path = tmp_path / "a.py"
    _ = path.write_text(data="x = 1\n", encoding="utf-8")
    payload: str = dumps(
        obj=[
            {"code": "E501", "location": {"row": 4}},
            {"code": "F401", "location": {"row": 1}},
            {"code": "E501", "location": "bad"},
            "bad",
        ],
    )
    monkeypatch.setattr(
        target=long_lines_module,
        name="run",
        value=Constant(
            value=CompletedProcess(
                args=["ruff"],
                returncode=1,
                stdout=payload,
                stderr="",
            ),
        ),
    )
    expect_equal(
        actual=LongLinesAPI.ruff_e501_rows(path=path),
        expected=frozenset({4}),
    )
    monkeypatch.setattr(
        target=long_lines_module,
        name="run",
        value=Constant(
            value=CompletedProcess(
                args=["ruff"],
                returncode=0,
                stdout="{}",
                stderr="",
            ),
        ),
    )
    expect_equal(
        actual=LongLinesAPI.ruff_e501_rows(path=path),
        expected=frozenset[int](),
    )
    _no_ruff(monkeypatch=monkeypatch)
    expect_equal(
        actual=LongLinesAPI.ruff_e501_rows(path=path),
        expected=frozenset[int](),
    )


def test_batch_fix_resolves_width_once_per_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch seeds rows from a report and memoizes the width lookup.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    _no_ruff(monkeypatch=monkeypatch)
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.ruff]\nline-length = 50\n",
        encoding="utf-8",
    )
    paths: list[Path] = []
    for name in ("a.py", "b.py"):
        path: Path = tmp_path / name
        _ = path.write_text(data=Constants.long_value, encoding="utf-8")
        paths.append(path)
    report: Path = tmp_path / "ruff.json"
    _ = report.write_text(
        data=dumps(
            obj=[
                {
                    "code": "E501",
                    "filename": str(object=paths[0]),
                    "location": {"row": 1},
                },
            ],
        ),
        encoding="utf-8",
    )
    batch: BatchResult = LongLinesAPI.fix(
        paths=(tmp_path,),
        settings=Settings(run_ruff=True, check_only=True),
        ruff_report=report,
        resolve_line_length=True,
    )
    expect_equal(actual=len(batch.results), expected=2)
    expect_true(condition=batch.changed)
    expect_true(condition=batch.clean)
    expect_equal(actual=batch.unresolved_count, expected=0)
    empty: BatchResult = LongLinesAPI.fix(paths=())
    expect_false(condition=empty.changed)
    expect_true(condition=empty.clean)


def test_repair_hook_fixes_files_and_summarizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stabilizer hook repairs long lines and records the outcome.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    _no_ruff(monkeypatch=monkeypatch)
    _ = (tmp_path / "pyproject.toml").write_text(
        data="[tool.ruff]\nline-length = 50\n",
        encoding="utf-8",
    )
    fixable: Path = tmp_path / "fixable.py"
    clean: Path = tmp_path / "clean.py"
    stuck: Path = tmp_path / "stuck.py"
    broken: Path = tmp_path / "broken.py"
    _ = fixable.write_text(data=Constants.long_value, encoding="utf-8")
    _ = clean.write_text(data="x = 1\n", encoding="utf-8")
    _ = stuck.write_text(data="x = " + "a" * 70 + " + b\n", encoding="utf-8")
    _ = broken.write_bytes(data=b"# coding: nosuchcodec\nx = 1\n")
    repair: LongLineRepair = LongLineRepair()
    for path in (fixable, clean, stuck, broken):
        repair(path=path)
    summary: RepairSummary = require_type(
        value=repair.summary(),
        kind=RepairSummary,
    )
    expect_in(member=fixable, container=summary.repaired)
    expect_not_in(member=clean, container=summary.repaired)
    expect_equal(actual=summary.unresolved, expected=(stuck,))
    expect_equal(actual=summary.skipped, expected=(broken,))
    expect_true(
        condition=all(
            len(line) <= Constants.hook_width
            for line in fixable.read_text().splitlines()
        ),
    )
    expect_equal(
        actual=private_call(owner=repair, name="_line_length", path=fixable),
        expected=50,
    )


def test_module_source_is_a_fixpoint() -> None:
    """The engine's own source already satisfies the width it enforces."""
    source: str = Path(long_lines_module.__file__).read_text(encoding="utf-8")
    result: TextResult = _fixer(width=79).transform_text(source=source)
    expect_false(condition=result.changed)
    expect_equal(actual=result.unresolved_lines, expected=())


@pytest.mark.parametrize("source", Constants.concat_sources)
def test_split_literals_stay_parenthesized_and_multiline(source: str) -> None:
    """Every emitted implicit concatenation keeps grouping parentheses.

    Ruff's formatter joins implicitly concatenated literals whenever the
    merged literal fits on one physical line, and ISC001 merges same-line
    literals outright, so a split that loses its parentheses — or leaves
    pieces on one line — is silently reverted by the next Ruff pass. The
    repair therefore wraps every complete concatenation in ``(``…``)``
    with each piece on its own physical line.

    Args:
        source: Source with one over-long string expression.

    """
    result: TextResult = _fixer(width=50).transform_text(source=source)
    expect_true(condition=result.changed)
    expect_true(condition=_same_ast(before=source, after=result.source))
    groups: tuple[
        tuple[TokenInfo | None, TokenInfo, TokenInfo, TokenInfo | None],
        ...,
    ] = _implicit_concat_groups(source=result.source)
    expect_true(condition=bool(groups))
    for before, first, last, after in groups:
        expect_true(condition=first.start[0] < last.end[0])
        expect_equal(actual=getattr(before, "string", None), expected="(")
        expect_equal(actual=getattr(after, "string", None), expected=")")


def _ruff() -> tuple[str, ...]:
    """Return the Ruff launcher shipped in the active environment.

    Returns:
        Executable prefix that invokes Ruff.

    """
    return (str(object=Path(executable).with_name(name="ruff")),)


def _long_source() -> str:
    """Return a module with one wrappable over-long assignment.

    Returns:
        Python source with a single E501 row.

    """
    return (
        "value = "
        + " + ".join((f"first_operand_{index}") for index in range(12))
        + "\n"
    )


def test_batched_e501_rows_report_only_long_files(tmp_path: Path) -> None:
    """One Ruff call maps long files to rows and omits clean files.

    Args:
        tmp_path: Per-test directory.

    """
    long_file: Path = tmp_path / "long.py"
    clean_file: Path = tmp_path / "clean.py"
    _ = long_file.write_text(data=_long_source(), encoding="utf-8")
    _ = clean_file.write_text(data="value = 1\n", encoding="utf-8")
    rows: dict[Path, frozenset[int]] = LongLinesAPI.ruff_e501_rows_many(
        paths=(long_file, clean_file),
        ruff_command=_ruff(),
    )
    expect_equal(actual=rows, expected={long_file.resolve(): frozenset({1})})
    expect_equal(
        actual=LongLinesAPI.ruff_e501_rows_many(
            paths=(),
            ruff_command=_ruff(),
        ),
        expected={},
    )


def _fake_run(*, stdout: str, **_arguments: object) -> CompletedProcess[str]:
    """Stand in for ``subprocess.run`` with a fixed standard output.

    Args:
        stdout: Text the fake process reports.
        **_arguments: Ignored ``run`` keyword arguments.

    Returns:
        A failed completed process carrying ``stdout``.

    """
    return CompletedProcess(args=[], returncode=1, stdout=stdout)


def test_batched_e501_rows_tolerate_bad_ruff_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing launchers, bad JSON and non-array JSON yield no rows.

    Args:
        tmp_path: Per-test directory.
        monkeypatch: Pytest patching helper.

    """
    source: Path = tmp_path / "a.py"
    _ = source.write_text(data="x = 1\n", encoding="utf-8")
    expect_equal(
        actual=LongLinesAPI.ruff_e501_rows_many(
            paths=(source,),
            ruff_command=(str(object=tmp_path / "missing-ruff"),),
        ),
        expected={},
    )
    stdout: str
    for stdout in ("{", "{}"):
        monkeypatch.setattr(
            target=long_lines_module,
            name="run",
            value=partial(_fake_run, stdout=stdout),
        )
        expect_equal(
            actual=LongLinesAPI.ruff_e501_rows_many(
                paths=(source,),
                ruff_command=_ruff(),
            ),
            expected={},
        )


def test_repair_many_rewrites_long_files_only(tmp_path: Path) -> None:
    """The batched repair fixes long files and leaves clean ones alone.

    Args:
        tmp_path: Per-test directory.

    """
    long_file: Path = tmp_path / "long.py"
    clean_file: Path = tmp_path / "clean.py"
    _ = long_file.write_text(data=_long_source(), encoding="utf-8")
    _ = clean_file.write_text(data="value = 1\n", encoding="utf-8")
    repair: LongLineRepair = LongLineRepair(ruff_command=_ruff())
    repair.repair_many(paths=(long_file, clean_file))
    summary: RepairSummary = repair.summary()
    expect_in(member=long_file, container=summary.repaired)
    expect_not_in(member=clean_file, container=summary.repaired)


def test_single_file_repair_records_changes_and_skips(tmp_path: Path) -> None:
    """Calling the repair per file fixes long lines and records skips.

    Args:
        tmp_path: Per-test directory.

    """
    long_file: Path = tmp_path / "long.py"
    missing: Path = tmp_path / "missing.py"
    _ = long_file.write_text(data=_long_source(), encoding="utf-8")
    repair: LongLineRepair = LongLineRepair(ruff_command=_ruff())
    repair(path=long_file)
    repair(path=missing)
    summary: RepairSummary = repair.summary()
    expect_in(member=long_file, container=summary.repaired)
    expect_in(member=missing, container=summary.skipped)
