# Copyright (c) 2026
"""The command line renders templates and reports failures with exit 2."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from json import dumps, loads
from typing import TYPE_CHECKING

from exactus.packages.markdown.main import main
from exactus.tests.common.support import dig, expect_equal, expect_in

if TYPE_CHECKING:
    from pathlib import Path


def _fixture(*, root: Path) -> tuple[Path, Path, Path]:
    """Create a template, data file and mapping file.

    Args:
        root: Directory to write into.

    Returns:
        Template, data and mapping paths.

    """
    template: Path = root / "t.md"
    template.write_text(data="Hello {{ who }}", encoding="utf-8")
    data: Path = root / "d.json"
    data.write_text(
        data=dumps(obj={"user": {"name": "Ada"}}),
        encoding="utf-8",
    )
    mapping: Path = root / "m.json"
    mapping.write_text(data=dumps(obj={"who": "user.name"}), encoding="utf-8")
    return template, data, mapping


def test_writes_output_file(tmp_path: Path) -> None:
    """``-o`` writes the rendered Markdown.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, mapping = _fixture(root=tmp_path)
    out: Path = tmp_path / "out.md"
    code: int = main(
        argv=[
            str(object=template),
            str(object=data),
            "-m",
            str(object=mapping),
            "-o",
            str(object=out),
        ],
    )
    expect_equal(actual=code, expected=0)
    expect_equal(actual=out.read_text(encoding="utf-8"), expected="Hello Ada")


def test_prints_to_stdout_by_default(tmp_path: Path) -> None:
    """Without ``-o`` the Markdown goes to the output stream.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, mapping = _fixture(root=tmp_path)
    out: StringIO = StringIO()
    code: int = main(
        argv=[
            str(object=template),
            str(object=data),
            "-m",
            str(object=mapping),
        ],
        out=out,
    )
    expect_equal(actual=code, expected=0)
    expect_equal(actual=out.getvalue(), expected="Hello Ada")


def test_validate_only_and_context_output(tmp_path: Path) -> None:
    """``--validate-only`` renders nothing; the context can be dumped.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, mapping = _fixture(root=tmp_path)
    context_file: Path = tmp_path / "ctx.json"
    out: StringIO = StringIO()
    code: int = main(
        argv=[
            str(object=template),
            str(object=data),
            "-m",
            str(object=mapping),
            "--validate-only",
            "--context-output",
            str(object=context_file),
        ],
        out=out,
    )
    expect_equal(actual=code, expected=0)
    expect_in(
        member="Template validation succeeded.",
        container=out.getvalue(),
    )
    dumped: object = loads(s=context_file.read_text(encoding="utf-8"))
    expect_equal(actual=dig(document=dumped, path=("who",)), expected="Ada")


def test_errors_exit_two(tmp_path: Path) -> None:
    """Missing files and strict undefined variables exit with code 2.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, _ = _fixture(root=tmp_path)
    err: StringIO = StringIO()
    missing: int = main(
        argv=[str(object=template), str(object=tmp_path / "nope.json")],
        err=err,
    )
    expect_equal(actual=missing, expected=2)
    strict: int = main(argv=[str(object=template), str(object=data)], err=err)
    expect_equal(actual=strict, expected=2)
    expect_in(member="error:", container=err.getvalue())
    lenient: int = main(
        argv=[str(object=template), str(object=data), "--lenient"],
        out=StringIO(),
    )
    expect_equal(actual=lenient, expected=0)


def test_bad_json_and_non_object_mapping_exit_two(tmp_path: Path) -> None:
    """Malformed JSON and a non-object mapping are reported with exit 2.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, _ = _fixture(root=tmp_path)
    broken: Path = tmp_path / "broken.json"
    broken.write_text(data="{not json", encoding="utf-8")
    listing: Path = tmp_path / "list.json"
    listing.write_text(data="[1, 2]", encoding="utf-8")
    err: StringIO = StringIO()
    bad_data: int = main(
        argv=[str(object=template), str(object=broken)],
        err=err,
    )
    bad_mapping: int = main(
        argv=[
            str(object=template),
            str(object=data),
            "-m",
            str(object=listing),
        ],
        err=err,
    )
    expect_equal(actual=bad_data, expected=2)
    expect_equal(actual=bad_mapping, expected=2)
    expect_in(member="JSON object", container=err.getvalue())


def test_template_root_allows_includes_from_other_directories(
    tmp_path: Path,
) -> None:
    """``--template-root`` adds a directory templates may include from.

    Args:
        tmp_path: Temporary directory.

    """
    shared: Path = tmp_path / "shared"
    shared.mkdir()
    shared.joinpath("part.md").write_text(data="shared", encoding="utf-8")
    page: Path = tmp_path / "page" / "t.md"
    page.parent.mkdir()
    page.write_text(data='{% include "part.md" %}', encoding="utf-8")
    data: Path = tmp_path / "d.json"
    data.write_text(data="{}", encoding="utf-8")
    out: StringIO = StringIO()
    code: int = main(
        argv=[
            str(object=page),
            str(object=data),
            "--template-root",
            str(object=shared),
        ],
        out=out,
    )
    expect_equal(actual=code, expected=0)
    expect_equal(actual=out.getvalue(), expected="shared")


def test_default_streams_are_resolved_at_call_time(tmp_path: Path) -> None:
    """Redirecting stdout and stderr captures the default streams.

    Args:
        tmp_path: Temporary directory.

    """
    template, data, mapping = _fixture(root=tmp_path)
    argv: list[str] = [
        str(object=template),
        str(object=data),
        "-m",
        str(object=mapping),
    ]
    captured: StringIO = StringIO()
    failed: StringIO = StringIO()
    with redirect_stdout(new_target=captured):
        expect_equal(actual=main(argv=argv), expected=0)
    with redirect_stderr(new_target=failed):
        expect_equal(
            actual=main(argv=[argv[0], str(object=tmp_path / "x.json")]),
            expected=2,
        )
    expect_equal(actual=captured.getvalue(), expected="Hello Ada")
    expect_in(member="error:", container=failed.getvalue())
