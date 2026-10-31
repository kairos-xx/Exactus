# Copyright (c) 2026
"""Bounded, root-confined source excerpts around finding lines."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final

import pytest

from exactus.tests.common.support import (
    dig,
    dig_list,
    expect_equal,
    expect_false,
    expect_in,
    expect_none,
    expect_not_in,
    expect_true,
    require,
)
from exactus.tools.common import snippets
from exactus.tools.common.snippets import (
    Excerpt,
    SnippetLimits,
    SnippetSource,
    excerpt,
    finding_excerpt,
    with_excerpts,
)

if TYPE_CHECKING:
    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        target: Grouped module constant.

    """

    target: Final[int] = 10


def _write(*, root: Path, name: str, lines: int) -> Path:
    """Write a text file whose line ``n`` reads ``line n``.

    Args:
        root: Directory to write in.
        name: File name.
        lines: Number of lines.

    Returns:
        The written file.

    """
    path: Path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        data="".join(f"line {number}\n" for number in range(1, lines + 1)),
        encoding="utf-8",
    )
    return path


def _numbers(*, captured: Excerpt) -> list[int]:
    """Return the line numbers of an excerpt.

    Args:
        captured: Excerpt to inspect.

    Returns:
        Numbers in order.

    """
    return [row.n for row in captured.lines]


def _targets(*, captured: Excerpt) -> list[int]:
    """Return the numbers of the excerpt's target lines.

    Args:
        captured: Excerpt to inspect.

    Returns:
        Target line numbers.

    """
    return [row.n for row in captured.lines if row.target]


def test_middle_of_file_has_context_on_both_sides(tmp_path: Path) -> None:
    """A line inside the file gets ``context`` lines before and after.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="pkg/a.py", lines=20)
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="pkg/a.py", line=10, context=2),
    )
    expect_equal(
        actual=_numbers(captured=captured),
        expected=[8, 9, 10, 11, 12],
    )
    expect_equal(actual=_targets(captured=captured), expected=[10])
    expect_equal(actual=captured.lines[2].text, expected="line 10")
    expect_equal(actual=captured.language, expected="python")
    expect_false(condition=captured.clipped)
    expect_equal(
        actual=captured.payload(),
        expected={
            "language": "python",
            "line": 10,
            "context": 2,
            "start": 8,
            "end": 12,
            "clipped": False,
            "lines": [
                {
                    "n": number,
                    "text": f"line {number}",
                    "target": number == Constants.target,
                }
                for number in range(8, 13)
            ],
        },
    )


def test_start_and_end_of_file_are_clipped(tmp_path: Path) -> None:
    """Context never reaches before line 1 or past the last line.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=5)
    first: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.py", line=1, context=3),
    )
    expect_equal(actual=_numbers(captured=first), expected=[1, 2, 3, 4])
    last: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.py", line=5, context=3),
    )
    expect_equal(actual=_numbers(captured=last), expected=[2, 3, 4, 5])
    expect_equal(actual=last.payload()["end"], expected=5)


def test_last_line_without_newline_is_read(tmp_path: Path) -> None:
    """A final line lacking a line ending is still captured.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "a.txt").write_text(data="one\r\ntwo", encoding="utf-8")
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.txt", line=2, context=1),
    )
    expect_equal(
        actual=[row.text for row in captured.lines],
        expected=["one", "two"],
    )
    expect_equal(actual=captured.language, expected="text")
    expect_false(condition=captured.clipped)


def test_context_zero_and_negative_keep_only_the_target(
    tmp_path: Path,
) -> None:
    """Context 0 (and a negative value) captures the target line alone.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=9)
    for context in (0, -4):
        captured: Excerpt = require(
            value=excerpt(root=tmp_path, path="a.py", line=4, context=context),
        )
        expect_equal(actual=_numbers(captured=captured), expected=[4])
        expect_equal(actual=captured.context, expected=0)


def test_context_depth_is_capped(tmp_path: Path) -> None:
    """A huge context keeps the requested value but caps captured lines.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=500)
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.py", line=250, context=10000),
    )
    cap: int = SnippetLimits.max_context
    expect_equal(actual=captured.context, expected=10000)
    expect_equal(
        actual=_numbers(captured=captured),
        expected=list(range(250 - cap, 250 + cap + 1)),
    )


def test_unusable_lines_and_files_give_nothing(tmp_path: Path) -> None:
    """Non-positive lines, lines past the end, missing files and folders.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=3)
    (tmp_path / "folder").mkdir()
    expect_none(value=excerpt(root=tmp_path, path="a.py", line=0, context=3))
    expect_none(value=excerpt(root=tmp_path, path="a.py", line=-1, context=3))
    expect_none(value=excerpt(root=tmp_path, path="a.py", line=4, context=3))
    expect_none(
        value=excerpt(root=tmp_path, path="missing.py", line=1, context=3),
    )
    expect_none(value=excerpt(root=tmp_path, path="folder", line=1, context=3))
    expect_none(
        value=excerpt(
            root=tmp_path / "absent",
            path="a.py",
            line=1,
            context=3,
        ),
    )


def test_binary_file_is_skipped(tmp_path: Path) -> None:
    """A file with a NUL byte in its head is not excerpted.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "blob.py").write_bytes(data=b"x = 1\n\x00\x01\x02\n")
    expect_none(
        value=excerpt(root=tmp_path, path="blob.py", line=1, context=1),
    )


def test_invalid_utf8_is_replaced(tmp_path: Path) -> None:
    """Undecodable bytes become replacement characters.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = (tmp_path / "a.txt").write_bytes(data=b"caf\xe9\n")
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.txt", line=1, context=0),
    )
    expect_equal(actual=captured.lines[0].text, expected="caf�")


@pytest.mark.parametrize(
    "data",
    [
        b"one\rtwo\rthree\rfour\r",
        b"one\r\ntwo\rthree\nfour",
        b"one\ntwo\r\nthree\rfour\r\n",
    ],
)
def test_line_endings_follow_universal_newlines(
    tmp_path: Path,
    data: bytes,
) -> None:
    """CR-only and mixed endings number lines like Python does.

    Args:
        tmp_path: Per-test temporary directory.
        data: File bytes with CR, LF and CRLF endings.

    """
    _ = (tmp_path / "a.txt").write_bytes(data=data)
    expected: list[str] = (
        (tmp_path / "a.txt").read_text(encoding="utf-8").splitlines()
    )
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.txt", line=3, context=1),
    )
    expect_equal(actual=_numbers(captured=captured), expected=[2, 3, 4])
    expect_equal(
        actual=[row.text for row in captured.lines],
        expected=expected[1:4],
    )
    expect_false(condition=any("\r" in row.text for row in captured.lines))


def test_cr_at_a_buffer_boundary_pairs_with_its_lf(tmp_path: Path) -> None:
    """A CRLF split across read buffers still ends exactly one line.

    Args:
        tmp_path: Per-test temporary directory.

    """
    head: bytes = b"x" * (8192 - 1)
    _ = (tmp_path / "a.txt").write_bytes(data=head + b"\r\nsecond\r\n")
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="a.txt", line=2, context=0),
    )
    expect_equal(actual=_numbers(captured=captured), expected=[2])
    expect_equal(actual=captured.lines[0].text, expected="second")


def test_huge_lines_are_clipped_without_breaking_numbering(
    tmp_path: Path,
) -> None:
    """Over-long lines are cut, marked, and later lines keep their numbers.

    Args:
        tmp_path: Per-test temporary directory.

    """
    huge: str = "x" * (SnippetLimits.max_line_bytes * 3)
    wide: str = "y" * (SnippetLimits.max_line_chars + 10)
    _ = (tmp_path / "min.js").write_text(
        data=f"{huge}\n{wide}\nshort\n",
        encoding="utf-8",
    )
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="min.js", line=3, context=2),
    )
    expect_equal(actual=_numbers(captured=captured), expected=[1, 2, 3])
    expect_true(condition=captured.clipped)
    expect_equal(
        actual=captured.lines[0].text,
        expected="x" * SnippetLimits.max_line_chars + SnippetLimits.ellipsis,
    )
    expect_equal(
        actual=captured.lines[1].text,
        expected="y" * SnippetLimits.max_line_chars + SnippetLimits.ellipsis,
    )
    expect_equal(actual=captured.lines[2].text, expected="short")
    expect_equal(actual=captured.language, expected="javascript")


def test_scan_limit_gives_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A line beyond the byte scan limit yields no excerpt.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _write(root=tmp_path, name="a.py", lines=100)
    monkeypatch.setattr(target=SnippetLimits, name="max_scan_bytes", value=64)
    expect_none(value=excerpt(root=tmp_path, path="a.py", line=90, context=1))
    expect_true(
        condition=excerpt(root=tmp_path, path="a.py", line=2, context=1)
        is not None,
    )


def test_unreadable_file_gives_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ``OSError`` while reading yields no excerpt.

    Args:
        tmp_path: Per-test temporary directory.
        monkeypatch: Pytest patching helper.

    """
    _ = _write(root=tmp_path, name="a.py", lines=3)

    def _refuse(self: Path, mode: str) -> None:
        """Fail like a file that cannot be opened.

        Args:
            self: Path being opened.
            mode: Requested mode.

        Raises:
            PermissionError: Always.

        """
        msg: str = f"denied {self.name} {mode}"
        raise PermissionError(msg)

    monkeypatch.setattr(target=snippets.Path, name="open", value=_refuse)
    expect_none(value=excerpt(root=tmp_path, path="a.py", line=1, context=1))


def test_paths_outside_the_root_are_refused(tmp_path: Path) -> None:
    """``..``, absolute paths and escaping symlinks are never read.

    Args:
        tmp_path: Per-test temporary directory.

    """
    root: Path = tmp_path / "project"
    root.mkdir()
    outside: Path = _write(root=tmp_path, name="secret.txt", lines=3)
    (root / "link.txt").symlink_to(target=outside)
    (root / "dir").symlink_to(target=tmp_path, target_is_directory=True)
    for path in (
        "../secret.txt",
        str(object=outside),
        "link.txt",
        "dir/secret.txt",
    ):
        expect_none(value=excerpt(root=root, path=path, line=1, context=1))
        expect_none(value=SnippetSource.locate(root=root, path=path))


def test_symlink_inside_the_root_is_followed(tmp_path: Path) -> None:
    """A symlink whose target stays inside the root is read.

    Args:
        tmp_path: Per-test temporary directory.

    """
    real: Path = _write(root=tmp_path, name="real.py", lines=2)
    (tmp_path / "alias.py").symlink_to(target=real)
    captured: Excerpt = require(
        value=excerpt(root=tmp_path, path="alias.py", line=2, context=5),
    )
    expect_equal(actual=_numbers(captured=captured), expected=[1, 2])


def test_language_from_file_name() -> None:
    """Suffixes and well-known names map to fence languages."""
    expected: dict[str, str] = {
        "a.py": "python",
        "a.PYI": "python",
        "a.ts": "typescript",
        "pyproject.toml": "toml",
        "conf.yml": "yaml",
        "run.sh": "shell",
        "Dockerfile": "dockerfile",
        "Makefile": "makefile",
        "notes": "text",
        "a.unknown": "text",
    }
    for name, language in expected.items():
        expect_equal(
            actual=SnippetSource.language(path=Path(name)),
            expected=language,
        )


def test_finding_excerpt_needs_a_path_and_a_positive_line(
    tmp_path: Path,
) -> None:
    """Only findings with a string path and a positive int line change.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=4)
    skipped: list[JsonValue] = [
        "not a finding",
        {"path": "a.py"},
        {"path": "a.py", "line": 0},
        {"path": "a.py", "line": True},
        {"path": "a.py", "line": "2"},
        {"path": "", "line": 2},
        {"line": 2},
        {"path": "gone.py", "line": 2},
    ]
    for finding in skipped:
        expect_equal(
            actual=finding_excerpt(finding=finding, root=tmp_path, context=1),
            expected=finding,
        )
    added: JsonValue = finding_excerpt(
        finding={"id": "X-1", "path": "a.py", "line": 2},
        root=tmp_path,
        context=1,
    )
    expect_equal(
        actual=dig(document=added, path=("excerpt", "start")),
        expected=1,
    )
    expect_equal(actual=dig(document=added, path=("id",)), expected="X-1")


def test_with_excerpts_annotates_every_finding(tmp_path: Path) -> None:
    """``with_excerpts`` copies the payload and adds per-finding excerpts.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _ = _write(root=tmp_path, name="a.py", lines=6)
    payload: dict[str, JsonValue] = {
        "summary": {"findings_total": 2},
        "findings": [
            {"id": "X-1", "path": "a.py", "line": 3},
            {"id": "X-2", "path": "docs", "line": 0},
        ],
    }
    annotated: dict[str, JsonValue] = with_excerpts(
        payload=payload,
        root=tmp_path,
        context=1,
    )
    findings: list[object] = dig_list(document=annotated, path=("findings",))
    expect_in(
        member="excerpt",
        container=require(value=_object(value=findings[0])),
    )
    expect_not_in(
        member="excerpt",
        container=require(value=_object(value=findings[1])),
    )
    expect_equal(
        actual=dig(document=annotated, path=("findings", 0, "excerpt", "end")),
        expected=4,
    )
    expect_not_in(
        member="excerpt",
        container=require(
            value=_object(
                value=dig_list(document=payload, path=("findings",))[0],
            ),
        ),
    )
    no_findings: dict[str, JsonValue] = {"summary": {}}
    expect_true(
        condition=with_excerpts(payload=no_findings, root=tmp_path, context=1)
        is no_findings,
    )


def _object(*, value: object) -> dict[str, object] | None:
    """Return ``value`` when it is a dictionary.

    Args:
        value: Candidate.

    Returns:
        The dictionary, or ``None``.

    """
    return (
        cast(typ="dict[str, object]", val=value)
        if isinstance(value, dict)
        else None
    )
