# Copyright (c) 2026 João Lopes.
"""Behavioral tests for the single-file test-necessity classifier."""

from pathlib import Path
from textwrap import dedent

import pytest

from exactus.packages.meaningful.analyzer import (
    Classification,
    ClassificationJson,
    PythonTestNeedClassifier,
    UnitTestLevel,
)


def expect(*, condition: bool) -> None:
    """Fail when a test condition is false.

    Args:
        condition: Condition that must hold.

    Raises:
        AssertionError: If ``condition`` is false.

    """
    if not condition:
        raise AssertionError


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        (
            "__init__.py",
            """\
\"""Exports.\"""
from pathlib import Path
__all__ = ("Path",)
""",
            UnitTestLevel.TEST_0,
        ),
        (
            "__main__.py",
            (
                dedent(
                    text=(
                        """\
    \"""Entrypoint.\"""
    from package import run

    def main() -> None:
        \"""Delegate.\"""
        run()

    if __name__ == "__main__":
        main()
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "delegate.py",
            (
                dedent(
                    text=(
                        """\
    \"""Delegate.\"""
    from package import run

    def execute(value: str) -> str:
        \"""Delegate.\"""
        return run(value)
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_1,
        ),
        (
            "compute.py",
            (
                dedent(
                    text=(
                        """\
    \"""Compute.\"""

    def double(value: int) -> int:
        \"""Double.\"""
        return value * 2
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "io.py",
            (
                dedent(
                    text=(
                        """\
    \"""I/O.\"""
    from pathlib import Path

    def load(path: Path) -> str:
        \"""Load.\"""
        return path.read_text(encoding="utf-8")
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "branch.py",
            (
                dedent(
                    text=(
                        """\
    \"""Branch.\"""

    def clamp(value: int) -> int:
        \"""Clamp.\"""
        if value < 0:
            return 0
        if value > 100:
            return 100
        return value
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "constants.py",
            (
                dedent(
                    text=(
                        """\
    \"""Constants.\"""
    from typing import Final

    NAMES: Final[frozenset[str]] = frozenset({"a", "b"})
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "__main__.py",
            (
                dedent(
                    text=(
                        """\
    \"""Entrypoint.\"""
    from package import cli

    def main() -> None:
        \"""Delegate.\"""
        raise SystemExit(cli())

    if __name__ == "__main__":
        main()
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "__init__.py",
            (
                dedent(
                    text=(
                        """\
    \"""Init with behavior.\"""

    def normalize(value: int) -> int:
        \"""Normalize.\"""
        if value < 0:
            return 0
        return value
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "subprocess_import.py",
            (
                dedent(
                    text=(
                        """\
    \"""Subprocess.\"""
    from subprocess import run

    def execute() -> None:
        \"""Execute.\"""
        run(args=("true",), check=True)
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "subprocess_alias.py",
            (
                dedent(
                    text=(
                        """\
    \"""Subprocess alias.\"""
    import subprocess as sp

    def execute() -> None:
        \"""Execute.\"""
        sp.run(args=("true",), check=True)
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "ambient.py",
            (
                dedent(
                    text=(
                        """\
    \"""Ambient state.\"""
    from os import environ

    def token() -> str:
        \"""Read token.\"""
        return environ["TOKEN"]
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "mutation.py",
            (
                dedent(
                    text=(
                        """\
    \"""Mutation.\"""

    def add(values: list[int], value: int) -> None:
        \"""Add one value.\"""
        values.append(value)
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_2,
        ),
        (
            "typing_only.py",
            (
                dedent(
                    text=(
                        """\
    \"""Typing only.\"""
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from package import Thing
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "model.py",
            (
                dedent(
                    text=(
                        """\
    \"""Model.\"""
    from dataclasses import dataclass, field

    @dataclass(frozen=True, slots=True)
    class Model:
        \"""Data model.\"""
        names: tuple[str, ...] = field(default_factory=tuple)
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "stubs.py",
            (
                dedent(
                    text=(
                        """\
    \"""Stubs.\"""

    def first() -> None:
        \"""Stub.\"""
        pass

    def second() -> None:
        \"""Stub.\"""
        ...
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_0,
        ),
        (
            "complex.py",
            (
                dedent(
                    text=(
                        """\
    \"""Complex.\"""

    def choose(value: int) -> int:
        \"""Choose.\"""
        if value > 0:
            if value > 1:
                if value > 2:
                    return value * 2
        if value < 0:
            return -value
        return 0
    """
                    ),
                )
            ),
            UnitTestLevel.TEST_3,
        ),
    ],
)
def test_classification_levels(
    *,
    tmp_path: Path,
    name: str,
    source: str,
    expected: UnitTestLevel,
) -> None:
    """Classify representative structural and behavioral source files.

    Args:
        tmp_path: Value supplied for ``tmp_path``.
        name: Value supplied for ``name``.
        source: Value supplied for ``source``.
        expected: Value supplied for ``expected``.

    """
    path: Path = tmp_path / name
    path.write_text(data=source, encoding="utf-8")
    expect(
        condition=PythonTestNeedClassifier(path=path).classify().level
        is expected,
    )


def test_metrics_json_and_render(*, tmp_path: Path) -> None:
    """Expose stable human and machine-readable reports.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "branch.py"
    path.write_text(
        data=(
            dedent(
                text=(
                    """\
    \"""Branch.\"""

    def choose(value: int) -> int:
        \"""Choose.\"""
        if value:
            return value + 1
        return 0
    """
                ),
            )
        ),
        encoding="utf-8",
    )
    result: Classification = PythonTestNeedClassifier(path=path).classify()
    payload: ClassificationJson = result.to_json()
    report: str = result.render()
    expect(condition=payload["level"] == "TEST-2")
    expect(condition=payload["metrics"]["branches"] == 1)
    expect(condition=payload["requires_branch_coverage"] is True)
    expect(condition="classification: TEST-2 (behavioral)" in report)
    expect(condition="branch coverage required: yes" in report)


def test_non_python_file_is_rejected(*, tmp_path: Path) -> None:
    """Reject paths without a Python suffix.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "module.txt"
    path.write_text(data="content", encoding="utf-8")
    with pytest.raises(
        expected_exception=ValueError,
        match=r"Expected a \.py file",
    ):
        PythonTestNeedClassifier(path=path)


def test_syntax_error_is_preserved(*, tmp_path: Path) -> None:
    """Surface Python syntax errors to callers.

    Args:
        tmp_path: Value supplied for ``tmp_path``.

    """
    path: Path = tmp_path / "broken.py"
    path.write_text(
        data="""\
def broken(:
""",
        encoding="utf-8",
    )
    with pytest.raises(expected_exception=SyntaxError):
        PythonTestNeedClassifier(path=path)
