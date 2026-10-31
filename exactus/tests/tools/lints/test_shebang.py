# Copyright (c) 2026
"""The lints shebang check reports and heals permission mismatches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exactus.tests.common.support import (
    expect_equal,
    expect_false,
    expect_true,
)
from exactus.tools.lints import shebang as shebang_module
from exactus.tools.lints.shebang import (
    ShebangInput,
    ShebangResult,
    ShebangSettings,
    check_file,
    scan_shebang,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_embedded_shebang_progress_stays_in_its_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permission completion must not mark the whole lint run complete.

    Args:
        tmp_path: Per-test project directory.
        monkeypatch: Pytest patching helper.

    """
    _ = (tmp_path / "file.py").write_text(data="x = 1\n", encoding="utf-8")
    snapshots: list[shebang_module.Progress] = []

    def publish(*, progress: shebang_module.Progress) -> None:
        """Capture permission progress.

        Args:
            progress: Published phase snapshot.

        """
        snapshots.append(progress)

    monkeypatch.setattr(
        target=shebang_module,
        name="publish_progress",
        value=publish,
    )
    _ = scan_shebang(
        inputs=ShebangInput(root=tmp_path, includes=(), excludes=()),
        progress_span=(0.12, 0.146),
    )
    expect_equal(actual=snapshots[-1].span, expected=(0.12, 0.146))
    expect_equal(actual=snapshots[-1].fraction, expected=1.0)


def _scan(
    *,
    root: Path,
    settings: ShebangSettings | None = None,
) -> ShebangResult:
    """Run the shebang scan over a project.

    Args:
        root: Project directory.
        settings: Heal policies; report-only when ``None``.

    Returns:
        The scan result.

    """
    return scan_shebang(
        inputs=ShebangInput(
            root=root,
            includes=(),
            excludes=(),
            settings=settings or ShebangSettings(),
        ),
    )


def test_check_file_permission_mismatches(tmp_path: Path) -> None:
    """Shebang/exec-bit mismatches produce EXE001 and EXE002 findings.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "tool.py"
    _ = script.write_text(data="#!/usr/bin/env python3\n")
    expect_equal(
        actual=[
            finding.rule for finding in check_file(path=script, root=tmp_path)
        ],
        expected=["EXE001"],
    )
    plain: Path = tmp_path / "plain.py"
    _ = plain.write_text(data="print('x')\n")
    plain.chmod(mode=0o755)
    expect_equal(
        actual=[
            finding.rule for finding in check_file(path=plain, root=tmp_path)
        ],
        expected=["EXE002"],
    )
    expect_equal(
        actual=check_file(path=plain, root=tmp_path)[0].file,
        expected="plain.py",
    )


def test_heal_adds_executable_bit_to_shebang_file(tmp_path: Path) -> None:
    """EXE001 heals by marking the shebang file executable.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "tool.py"
    _ = script.write_text(data="#!/usr/bin/env python3\nx = 1\n")
    script.chmod(mode=0o644)
    result: ShebangResult = _scan(
        root=tmp_path,
        settings=ShebangSettings(heal=True),
    )
    expect_equal(
        actual=[(heal.file, heal.action) for heal in result.healed],
        expected=[("tool.py", "add-exec")],
    )
    expect_equal(actual=list(result.findings), expected=[])
    expect_true(condition=bool(script.stat().st_mode & 0o111))


def test_heal_inserts_shebang_into_executable(tmp_path: Path) -> None:
    """EXE002 heals by prepending the suffix's interpreter line.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "run.py"
    _ = script.write_text(data="print('x')\n")
    script.chmod(mode=0o755)
    result: ShebangResult = _scan(
        root=tmp_path,
        settings=ShebangSettings(heal=True),
    )
    expect_equal(
        actual=[(heal.file, heal.action) for heal in result.healed],
        expected=[("run.py", "add-shebang")],
    )
    expect_equal(actual=list(result.findings), expected=[])
    expect_true(
        condition=script.read_bytes().startswith(
            b"#!/usr/bin/env python3\nprint('x')\n",
        ),
    )


def test_heal_drops_exec_bit_instead_of_shebang(tmp_path: Path) -> None:
    """``drop-exec`` clears the bits of executables lacking a shebang.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "run.py"
    _ = script.write_text(data="print('x')\n")
    script.chmod(mode=0o755)
    result: ShebangResult = _scan(
        root=tmp_path,
        settings=ShebangSettings(heal=True, exec_no_shebang="drop-exec"),
    )
    expect_equal(
        actual=[(heal.file, heal.action) for heal in result.healed],
        expected=[("run.py", "drop-exec")],
    )
    expect_equal(actual=list(result.findings), expected=[])
    expect_false(condition=bool(script.stat().st_mode & 0o111))
    expect_equal(actual=script.read_text(), expected="print('x')\n")


def test_heal_drops_shebang_from_non_executable(tmp_path: Path) -> None:
    """``drop-shebang`` removes the shebang of non-executable files.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "tool.py"
    _ = script.write_text(data="#!/usr/bin/env python3\nx = 1\n")
    script.chmod(mode=0o644)
    result: ShebangResult = _scan(
        root=tmp_path,
        settings=ShebangSettings(heal=True, shebang_no_exec="drop-shebang"),
    )
    expect_equal(
        actual=[(heal.file, heal.action) for heal in result.healed],
        expected=[("tool.py", "drop-shebang")],
    )
    expect_equal(actual=list(result.findings), expected=[])
    expect_false(condition=bool(script.stat().st_mode & 0o111))
    expect_equal(actual=script.read_text(), expected="x = 1\n")


def test_report_only_keeps_findings_and_files(tmp_path: Path) -> None:
    """Without healing the mismatches stay findings and files untouched.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "run.py"
    _ = script.write_text(data="print('x')\n")
    script.chmod(mode=0o755)
    result: ShebangResult = _scan(root=tmp_path)
    expect_equal(
        actual=[finding.rule for finding in result.findings],
        expected=["EXE002"],
    )
    expect_equal(actual=list(result.healed), expected=[])
    expect_equal(actual=script.read_text(), expected="print('x')\n")


def test_heal_is_idempotent(tmp_path: Path) -> None:
    """A second healed scan finds nothing left to repair or report.

    Args:
        tmp_path: Per-test temporary directory.

    """
    script: Path = tmp_path / "run.py"
    _ = script.write_text(data="print('x')\n")
    script.chmod(mode=0o755)
    tool: Path = tmp_path / "tool.py"
    _ = tool.write_text(data="#!/usr/bin/env python3\nx = 1\n")
    tool.chmod(mode=0o644)
    settings: ShebangSettings = ShebangSettings(heal=True)
    first: ShebangResult = _scan(root=tmp_path, settings=settings)
    expect_equal(actual=len(first.healed), expected=2)
    second: ShebangResult = _scan(root=tmp_path, settings=settings)
    expect_equal(actual=list(second.findings), expected=[])
    expect_equal(actual=list(second.healed), expected=[])
