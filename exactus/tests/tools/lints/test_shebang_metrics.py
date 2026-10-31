# Copyright (c) 2026
"""The lints shebang check counts executables, shebangs and interpreters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest

from exactus.tests.common.support import expect_equal, expect_none
from exactus.tools.lints.shebang import (
    ShebangInput,
    ShebangMetrics,
    ShebangResult,
    interpreter_of,
    metrics_data,
    scan_shebang,
)

if TYPE_CHECKING:
    from pathlib import Path

    from exactus.tools.common.json_types import JsonValue


@final
class Constants:
    """Group module-level constants.

    Attributes:
        scripts: Grouped module constant.

    """

    scripts: Final[dict[str, tuple[str, bool]]] = {
        "bin/a.py": ("#!/usr/bin/env python3\nx = 1\n", True),
        "bin/b.py": ("#!/usr/bin/python3\nx = 1\n", True),
        "bin/c.py": ("#!/usr/bin/env -S node --flag\n", True),
        "bin/d.py": ("#!/bin/bash\n", False),
        "bin/e.py": ("#!/opt/tools/custom-run -x\n", False),
        "lib/plain.py": ("x = 1\n", True),
        "lib/quiet.py": ("y = 2\n", False),
    }


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (b"#!/usr/bin/env python3\n", "python3"),
        (b"#!/bin/bash\n", "bash"),
        (b"#!/usr/bin/env -S node --x\n", "node"),
        (b"#!/usr/bin/env -Snode --x\n", "node"),
        (b"#!/usr/bin/env FOO=1 ruby\n", "ruby"),
        (b"#!/usr/bin/env -u HOME perl\n", "perl"),
        (b"#! /usr/bin/python3 -u\n", "python3"),
        (b"#!/opt/weird/tool\r\n", "tool"),
        (b"#!python\n", "python"),
        (b"#!\n", "unknown"),
        (b"#!/usr/bin/env\n", "env"),
        (b"#!/usr/bin/env -i\n", "env"),
        (b"#!/\n", "unknown"),
    ],
)
def test_interpreter_is_normalized(line: bytes, expected: str) -> None:
    """Shebang lines reduce to the program they launch.

    Args:
        line: First line of a file.
        expected: Interpreter name expected.

    """
    expect_equal(actual=interpreter_of(line=line), expected=expected)


def test_non_shebang_line_has_no_interpreter() -> None:
    """Ordinary source lines name no interpreter."""
    expect_none(value=interpreter_of(line=b"x = 1\n"))
    expect_none(value=interpreter_of(line=b""))
    expect_none(value=interpreter_of(line=b" #!/bin/sh\n"))


def _project(*, root: Path) -> None:
    """Write the scripts of ``SCRIPTS`` with their execute bits.

    Args:
        root: Project directory.

    """
    name: str
    content: str
    executable: bool
    for name, (content, executable) in Constants.scripts.items():
        path: Path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(data=content)
        path.chmod(mode=493 if executable else 420)


def _audit(*, root: Path) -> ShebangResult:
    """Scan a project with default filters, reporting only.

    Args:
        root: Project directory.

    Returns:
        The scan result.

    """
    return scan_shebang(
        inputs=ShebangInput(root=root, includes=(), excludes=()),
    )


def test_metrics_of_a_mixed_project(tmp_path: Path) -> None:
    """Counters, interpreters, mismatch lists and extensions add up.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _project(root=tmp_path)
    result: ShebangResult = _audit(root=tmp_path)
    metrics: ShebangMetrics = result.metrics
    expect_equal(actual=metrics.files_scanned, expected=result.files)
    expect_equal(actual=metrics.files_scanned, expected=7)
    expect_equal(actual=metrics.executable_files, expected=4)
    expect_equal(actual=metrics.files_with_shebang, expected=5)
    expect_equal(
        actual=metrics.interpreters,
        expected=(("python3", 2), ("bash", 1), ("custom-run", 1), ("node", 1)),
    )
    expect_equal(
        actual=metrics.executable_without_shebang,
        expected=("lib/plain.py",),
    )
    expect_equal(
        actual=metrics.shebang_without_executable,
        expected=("bin/d.py", "bin/e.py"),
    )
    expect_equal(actual=metrics.extensions, expected=((".py", 7),))
    expect_equal(
        actual=sorted(finding.file for finding in result.findings),
        expected=["bin/d.py", "bin/e.py", "lib/plain.py"],
    )


def test_metrics_payload_shape(tmp_path: Path) -> None:
    """``metrics_data`` carries rows and path lists as JSON.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _project(root=tmp_path)
    data: dict[str, JsonValue] = metrics_data(
        metrics=_audit(root=tmp_path).metrics,
    )
    expect_equal(
        actual=data,
        expected={
            "files_scanned": 7,
            "executable_files": 4,
            "files_with_shebang": 5,
            "shebang_interpreters": [
                {"interpreter": "python3", "count": 2},
                {"interpreter": "bash", "count": 1},
                {"interpreter": "custom-run", "count": 1},
                {"interpreter": "node", "count": 1},
            ],
            "executable_without_shebang": ["lib/plain.py"],
            "shebang_without_executable": ["bin/d.py", "bin/e.py"],
            "by_extension": [{"extension": ".py", "count": 7}],
        },
    )


def test_metrics_ignore_skipped_files(tmp_path: Path) -> None:
    """Symlinks, excluded files and hidden folders are not counted.

    Args:
        tmp_path: Per-test temporary directory.

    """
    _project(root=tmp_path)
    (tmp_path / ".hidden").mkdir()
    _ = (tmp_path / ".hidden" / "x.py").write_text(data="#!/bin/sh\n")
    (tmp_path / "alias.py").symlink_to(target=tmp_path / "bin" / "a.py")
    result: ShebangResult = scan_shebang(
        inputs=ShebangInput(root=tmp_path, includes=(), excludes=("bin/**",)),
    )
    expect_equal(actual=result.metrics.files_scanned, expected=2)
    expect_equal(actual=result.metrics.files_with_shebang, expected=0)
    expect_equal(actual=result.metrics.interpreters, expected=())
    expect_equal(
        actual=result.metrics.executable_without_shebang,
        expected=("lib/plain.py",),
    )


def test_metrics_of_an_empty_project(tmp_path: Path) -> None:
    """A root without Python files reports zeroes and empty tables.

    Args:
        tmp_path: Per-test temporary directory.

    """
    data: dict[str, JsonValue] = metrics_data(
        metrics=_audit(root=tmp_path).metrics,
    )
    expect_equal(
        actual=data,
        expected={
            "files_scanned": 0,
            "executable_files": 0,
            "files_with_shebang": 0,
            "shebang_interpreters": [],
            "executable_without_shebang": [],
            "shebang_without_executable": [],
            "by_extension": [],
        },
    )


def test_unreadable_file_is_counted_but_not_classified(tmp_path: Path) -> None:
    """A file that cannot be read gives EXE003 and no shebang facts.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "locked.py"
    _ = script.write_text(data="#!/bin/sh\n")
    script.chmod(mode=0)
    try:
        result: ShebangResult = _audit(root=tmp_path)
    finally:
        script.chmod(mode=420)
    expect_equal(actual=result.metrics.files_scanned, expected=1)
    expect_equal(actual=result.metrics.files_with_shebang, expected=0)
    expect_equal(
        actual=[finding.rule for finding in result.findings],
        expected=["EXE003"],
    )
